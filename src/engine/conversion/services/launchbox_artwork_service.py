"""LaunchBox Game Database service for downloading Clear Logo artwork."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import quote

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaunchBoxLogo:
    database_id: str
    name: str
    platform: str
    filename: str


class LaunchBoxArtworkService:
    """Loads LaunchBox metadata and downloads Clear Logos as validated PNGs."""

    METADATA_URL = "https://gamesdb.launchbox-app.com/Metadata.zip"
    IMAGE_BASE_URL = "https://images.launchbox-app.com/"
    REQUEST_TIMEOUT = (8, 20)
    DOWNLOAD_WORKERS = 6

    def __init__(self, cache_dir: Optional[str | Path] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self._default_cache_dir()
        self.metadata_path = self.cache_dir / "Metadata.zip"
        self.index_path = self.cache_dir / "Metadata.index.sqlite"

    @staticmethod
    def _default_cache_dir() -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        elif os.uname().sysname == "Darwin":
            base = Path.home() / "Library/Caches"
        else:
            base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return base / "dmd_gif_converter" / "launchbox"

    @staticmethod
    def _requests():
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "LaunchBox downloads require the requests package. "
                "Install the UI dependencies with pip install -r requirements_ui.txt."
            ) from exc
        return requests

    @staticmethod
    def _cancelled(cancel_flag: Optional[Callable[[], bool]]) -> bool:
        return bool(cancel_flag and cancel_flag())

    def _ensure_metadata(
        self,
        refresh: bool = False,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> Path:
        if self.metadata_path.is_file() and not refresh:
            return self.metadata_path

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.metadata_path.with_suffix(".zip.part")
        response = None
        try:
            if self._cancelled(cancel_flag):
                raise InterruptedError("LaunchBox metadata download cancelled.")

            response = self._requests().get(
                self.METADATA_URL, stream=True, timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            with temp_path.open("wb") as archive_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if self._cancelled(cancel_flag):
                        raise InterruptedError("LaunchBox metadata download cancelled.")
                    if chunk:
                        archive_file.write(chunk)

            if not zipfile.is_zipfile(temp_path):
                raise ValueError("LaunchBox returned an invalid Metadata.zip archive.")
            os.replace(temp_path, self.metadata_path)
            return self.metadata_path
        finally:
            if response is not None:
                response.close()
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _element_values(cls, element: ET.Element) -> dict[str, str]:
        return {
            cls._local_name(child.tag): (child.text or "").strip()
            for child in element
        }

    @staticmethod
    def _metadata_member(archive: zipfile.ZipFile) -> str:
        for member in archive.namelist():
            if Path(member).name.lower() == "metadata.xml":
                return member
        raise ValueError("Metadata.zip does not contain Metadata.xml.")

    def _ensure_index(
        self,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> Path:
        metadata_path = self._ensure_metadata(cancel_flag=cancel_flag)
        archive_stat = metadata_path.stat()
        signature = f"{archive_stat.st_size}:{archive_stat.st_mtime_ns}"

        if self.index_path.is_file():
            try:
                with sqlite3.connect(self.index_path) as connection:
                    row = connection.execute(
                        "SELECT value FROM metadata WHERE key = 'archive_signature'"
                    ).fetchone()
                    if row and row[0] == signature:
                        return self.index_path
            except sqlite3.DatabaseError:
                logger.warning("Discarding invalid cached LaunchBox metadata index.")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.index_path.with_suffix(".sqlite.part")
        try:
            if temp_path.exists():
                temp_path.unlink()
            with sqlite3.connect(temp_path) as connection:
                connection.execute("PRAGMA journal_mode = OFF")
                connection.execute("PRAGMA synchronous = OFF")
                connection.executescript(
                    """
                    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE games (
                        database_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        platform TEXT NOT NULL
                    );
                    CREATE INDEX games_platform ON games(platform COLLATE NOCASE);
                    CREATE TABLE logos (
                        database_id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('archive_signature', ?)",
                    (signature,),
                )
                with zipfile.ZipFile(metadata_path) as archive:
                    with archive.open(self._metadata_member(archive)) as xml_file:
                        for _, element in ET.iterparse(xml_file, events=("end",)):
                            tag = self._local_name(element.tag)
                            if tag == "Game":
                                values = self._element_values(element)
                                database_id = values.get("DatabaseID", "")
                                name = values.get("Name", "")
                                platform = values.get("Platform", "")
                                if database_id and name and platform:
                                    connection.execute(
                                        "INSERT OR REPLACE INTO games VALUES (?, ?, ?)",
                                        (database_id, name, platform),
                                    )
                            elif tag == "GameImage":
                                values = self._element_values(element)
                                database_id = values.get("DatabaseID", "")
                                filename = values.get("FileName", "")
                                if (
                                    values.get("Type") == "Clear Logo"
                                    and database_id
                                    and filename
                                ):
                                    connection.execute(
                                        """
                                        INSERT OR IGNORE INTO logos(database_id, filename)
                                        SELECT database_id, ? FROM games WHERE database_id = ?
                                        """,
                                        (filename, database_id),
                                    )
                            if tag in {"Game", "GameImage"}:
                                element.clear()
                            if self._cancelled(cancel_flag):
                                raise InterruptedError(
                                    "LaunchBox metadata indexing cancelled."
                                )
                connection.commit()
            os.replace(temp_path, self.index_path)
            return self.index_path
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def get_platforms(
        self,
        refresh: bool = False,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> list[str]:
        """Return sorted platform names from a locally cached LaunchBox index."""
        if refresh and self.index_path.is_file():
            self.index_path.unlink()
        index_path = self._ensure_index(cancel_flag)
        with sqlite3.connect(index_path) as connection:
            rows = connection.execute(
                "SELECT DISTINCT platform FROM games ORDER BY platform COLLATE NOCASE"
            )
            return [row[0] for row in rows]

    def _logos_for_platforms(
        self,
        platforms: set[str],
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> list[LaunchBoxLogo]:
        selected = {platform.casefold() for platform in platforms}
        if not selected:
            return []
        index_path = self._ensure_index(cancel_flag)
        placeholders = ",".join("?" for _ in selected)
        with sqlite3.connect(index_path) as connection:
            rows = connection.execute(
                f"""
                SELECT games.database_id, games.name, games.platform, logos.filename
                FROM games
                JOIN logos USING (database_id)
                WHERE games.platform COLLATE NOCASE IN ({placeholders})
                ORDER BY games.name COLLATE NOCASE
                """,
                tuple(selected),
            )
            return [LaunchBoxLogo(*row) for row in rows]

    @staticmethod
    def _safe_component(value: str) -> str:
        component = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
        return component or "Unknown"

    def _output_path(self, logo: LaunchBoxLogo, destination: Path) -> Path:
        filename = f"{self._safe_component(logo.name)} [{self._safe_component(logo.database_id)}].png"
        return destination / self._safe_component(logo.platform) / filename

    def _download_logo(
        self,
        logo: LaunchBoxLogo,
        destination: Path,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> str:
        output_path = self._output_path(logo, destination)
        if output_path.is_file():
            return str(output_path)
        if self._cancelled(cancel_flag):
            raise InterruptedError("LaunchBox logo download cancelled.")

        remote_name = logo.filename.strip().replace("\\", "/")
        if not remote_name or remote_name.startswith("/") or ".." in Path(remote_name).parts:
            raise ValueError(f"Invalid LaunchBox image filename: {logo.filename!r}")

        url = self.IMAGE_BASE_URL + quote(remote_name, safe="/")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        download_path = None
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".download", dir=output_path.parent, delete=False
            ) as temp_file:
                download_path = Path(temp_file.name)
                response = self._requests().get(
                    url, stream=True, timeout=self.REQUEST_TIMEOUT
                )
                try:
                    response.raise_for_status()
                    chunks = response.iter_content(chunk_size=64 * 1024)
                    for chunk in chunks:
                        if self._cancelled(cancel_flag):
                            raise InterruptedError("LaunchBox logo download cancelled.")
                        if chunk:
                            temp_file.write(chunk)
                finally:
                    response.close()

            if self._cancelled(cancel_flag):
                raise InterruptedError("LaunchBox logo download cancelled.")
            with Image.open(download_path) as image:
                image.load()
                with tempfile.NamedTemporaryFile(
                    suffix=".png", dir=output_path.parent, delete=False
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                image.convert("RGBA").save(temp_path, format="PNG")
            os.replace(temp_path, output_path)
        finally:
            for temp_file_path in (temp_path, download_path):
                if temp_file_path is not None:
                    try:
                        temp_file_path.unlink()
                    except FileNotFoundError:
                        pass
        return str(output_path)

    def download_logos(
        self,
        platforms: Iterable[str],
        destination: Optional[str | Path] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[list[str], list[str]]:
        """Download one Clear Logo per selected game, returning paths and errors."""
        selected = {platform.strip() for platform in platforms if platform.strip()}
        if not selected:
            raise ValueError("Select at least one LaunchBox platform.")

        output_root = Path(destination) if destination else self.cache_dir / "logos"
        logos = self._logos_for_platforms(selected, cancel_flag)
        downloaded = [
            str(output_path)
            for logo in logos
            if (output_path := self._output_path(logo, output_root)).is_file()
        ]
        pending = [
            logo for logo in logos
            if not self._output_path(logo, output_root).is_file()
        ]
        errors: list[str] = []
        total = len(logos)
        completed = len(downloaded)
        if progress_callback:
            progress_callback(completed, total)
        progress_interval = max(1, total // 100)

        with ThreadPoolExecutor(max_workers=self.DOWNLOAD_WORKERS) as executor:
            futures = {
                executor.submit(self._download_logo, logo, output_root, cancel_flag): logo
                for logo in pending
            }
            for future in as_completed(futures):
                logo = futures[future]
                try:
                    downloaded.append(future.result())
                except InterruptedError:
                    pass
                except Exception as exc:
                    errors.append(f"{logo.platform}/{logo.name}: {exc}")
                    logger.warning("Could not download LaunchBox logo %s: %s", logo.name, exc)
                completed += 1
                if progress_callback and (
                    completed == total or completed % progress_interval == 0
                ):
                    progress_callback(completed, total)

        return downloaded, errors
