"""Direct SMB access to media already scraped by Batocera."""

from __future__ import annotations

import errno
import concurrent.futures
import hashlib
import json
import os
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.engine.conversion.core import SUPPORTED_EXTENSIONS
from src.engine.media_sources.batocera import BatoceraImportResult


@dataclass(frozen=True)
class BatoceraConnectionConfig:
    server: str
    share: str
    username: str
    password: str


class BatoceraConnectionStore:
    """Persist non-secret connection fields and optionally use the OS keychain."""

    KEYRING_SERVICE = "dmd_gif_converter.batocera"

    def __init__(self, settings_path: str | Path | None = None):
        self.settings_path = Path(settings_path) if settings_path else self._default_settings_path()

    @staticmethod
    def _default_settings_path() -> Path:
        if sys.platform == "darwin":
            base = Path.home() / "Library/Application Support"
        elif os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "dmd_gif_converter" / "batocera.json"

    def load(self) -> dict[str, str]:
        if not self.settings_path.exists():
            return {"server": "", "share": "share", "username": "root"}
        try:
            values = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Batocera-Einstellungen konnten nicht gelesen werden: {exc}") from exc
        return {
            "server": str(values.get("server", "")),
            "share": str(values.get("share", "share")),
            "username": str(values.get("username", "")),
        }

    def load_password(self, server: str, share: str, username: str) -> str:
        import keyring

        return keyring.get_password(self._keyring_account(server, share), username) or ""

    def save(
        self,
        server: str,
        share: str,
        username: str,
        password: str,
        remember_password: bool,
    ) -> None:
        import keyring

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.settings_path.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps(
                    {"server": server, "share": share, "username": username},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary_path.replace(self.settings_path)
            account = self._keyring_account(server, share)
            if remember_password and password:
                keyring.set_password(account, username, password)
            else:
                if keyring.get_password(account, username) is not None:
                    keyring.delete_password(account, username)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @classmethod
    def _keyring_account(cls, server: str, share: str) -> str:
        return f"{server.strip().lower()}\\{share.strip()}"


class BatoceraSmbMediaService:
    """Import selected scraped videos and artwork over SMB."""

    CHUNK_SIZE = 1024 * 1024
    MAX_DOWNLOAD_WORKERS = 1
    IMAGE_FIELDS = {"image", "thumbnail", "marquee", "fanart"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self._default_cache_dir()

    @staticmethod
    def _default_cache_dir() -> Path:
        if sys.platform == "darwin":
            base = Path.home() / "Library/Caches"
        else:
            base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return base / "dmd_gif_converter" / "batocera-media"

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _share_relative_path(value: str, gamelist_relative: str) -> str | None:
        value = value.strip().replace("\\", "/")
        if not value or "://" in value:
            return None
        if value.startswith("/userdata/"):
            candidate = value.removeprefix("/userdata/")
            allow_userdata_path = True
        elif value.startswith("/roms/"):
            candidate = value.lstrip("/")
            allow_userdata_path = False
        elif value.startswith("/"):
            return None
        else:
            candidate = posixpath.join(posixpath.dirname(gamelist_relative), value)
            allow_userdata_path = False
        candidate = posixpath.normpath(candidate)
        if candidate in ("", ".") or candidate == ".." or candidate.startswith("../"):
            return None
        if not allow_userdata_path and candidate != "roms" and not candidate.startswith("roms/"):
            return None
        return candidate

    @staticmethod
    def _unc_path(server: str, share: str, relative: str) -> str:
        return "\\\\" + server + "\\" + share + "\\" + relative.replace("/", "\\")

    @staticmethod
    def _cache_name(
        remote_path: str,
        size: int,
        modified: float,
        display_name: str = "",
    ) -> str:
        identity = f"{remote_path}\0{size}\0{modified}".encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()
        readable = re.sub(r"[^A-Za-z0-9._-]+", "-", display_name).strip("._-")
        readable = readable[:72].rstrip("._-") or "batocera"
        return f"{readable}-{digest[:12]}{Path(remote_path).suffix.lower()}"

    @staticmethod
    def _smb_client():
        try:
            import smbclient
        except ImportError as exc:
            raise RuntimeError(
                "SMB-Unterstützung fehlt. Bitte die App-Abhängigkeiten aktualisieren."
            ) from exc
        return smbclient

    @classmethod
    def _register(cls, config: BatoceraConnectionConfig):
        if not config.server.strip() or not config.share.strip():
            raise ValueError("Server und Freigabe müssen angegeben werden.")
        smbclient = cls._smb_client()
        server = config.server.strip()
        smbclient.register_session(
            server,
            username=config.username or None,
            password=config.password or None,
            connection_timeout=15,
        )
        return smbclient, server, config.share.strip().strip("\\/")

    def list_systems(
        self,
        config: BatoceraConnectionConfig,
        *,
        cancel_flag: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """List immediate directories under ``roms`` without scanning their contents."""
        smbclient, server, share = self._register(config)
        roms_path = self._unc_path(server, share, "roms")
        try:
            systems = []
            with smbclient.scandir(
                roms_path,
                username=config.username or None,
                password=config.password or None,
            ) as entries:
                for entry in entries:
                    if cancel_flag and cancel_flag():
                        return []
                    if entry.name in {".", ".."} or not entry.is_dir():
                        continue
                    if "/" in entry.name or "\\" in entry.name:
                        continue
                    systems.append(entry.name)
                    if progress_callback:
                        progress_callback(len(systems), 0)
            return sorted(systems, key=str.casefold)
        finally:
            smbclient.delete_session(server)

    def import_media(
        self,
        config: BatoceraConnectionConfig,
        systems: Iterable[str],
        *,
        include_videos: bool = True,
        include_images: bool = True,
        cancel_flag: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        media_progress_callback: Callable[[int, int, str, str | None], None] | None = None,
    ) -> BatoceraImportResult:
        """Import supported media referenced by selected systems' game lists."""
        selected = sorted({system.strip() for system in systems if system.strip()}, key=str.casefold)
        if not selected:
            raise ValueError("Bitte mindestens ein Batocera-System auswählen.")
        if not include_videos and not include_images:
            raise ValueError("Bitte Videos/GIFs und/oder Artwork auswählen.")
        if any(
            system in {".", ".."} or "/" in system or "\\" in system
            for system in selected
        ):
            raise ValueError("Ungültiger Batocera-Systemname.")

        smbclient, server, share = self._register(config)
        try:
            resolved_paths: list[str] = []
            seen: set[str] = set()
            seen_remote: set[str] = set()
            skipped = 0
            games_seen = 0
            video_references = 0
            image_references = 0
            unresolved_references = 0
            unsupported_references = 0
            missing_gamelists: list[str] = []
            total_media = 0
            completed_media = 0

            def result(cancelled: bool = False) -> BatoceraImportResult:
                return BatoceraImportResult(
                    media_paths=tuple(resolved_paths),
                    skipped_media=skipped,
                    cancelled=cancelled,
                    games_seen=games_seen,
                    video_references=video_references,
                    image_references=image_references,
                    unresolved_references=unresolved_references,
                    unsupported_references=unsupported_references,
                    missing_gamelists=tuple(missing_gamelists),
                )

            cancelled = False
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.MAX_DOWNLOAD_WORKERS
            ) as executor:
                for index, system in enumerate(selected, start=1):
                    if cancel_flag and cancel_flag():
                        cancelled = True
                        break
                    if progress_callback:
                        progress_callback(index, len(selected), system)
                    gamelist_relative = posixpath.join("roms", system, "gamelist.xml")
                    gamelist_path = self._unc_path(server, share, gamelist_relative)
                    try:
                        with smbclient.open_file(
                            gamelist_path,
                            mode="rb",
                            username=config.username or None,
                            password=config.password or None,
                        ) as remote_xml:
                            for _, element in ET.iterparse(remote_xml, events=("end",)):
                                if cancel_flag and cancel_flag():
                                    cancelled = True
                                    break
                                if self._local_name(element.tag).lower() != "game":
                                    continue
                                games_seen += 1
                                game_name = next(
                                    (
                                        (child.text or "").strip()
                                        for child in element
                                        if self._local_name(child.tag).lower() == "name"
                                        and (child.text or "").strip()
                                    ),
                                    "",
                                )
                                for child in element:
                                    field = self._local_name(child.tag).lower()
                                    is_video = field == "video" and include_videos
                                    is_image = field in self.IMAGE_FIELDS and include_images
                                    if not is_video and not is_image:
                                        continue
                                    value = child.text or ""
                                    if is_video:
                                        video_references += 1
                                    elif is_image:
                                        image_references += 1
                                    source_extension = Path(value.strip()).suffix.lower()
                                    if is_image and source_extension == ".gif":
                                        is_video = True
                                        is_image = False
                                    if is_image and source_extension not in self.IMAGE_EXTENSIONS:
                                        skipped += 1
                                        unsupported_references += 1
                                        continue
                                    relative = self._share_relative_path(
                                        value, gamelist_relative,
                                    )
                                    if relative is None:
                                        skipped += 1
                                        unresolved_references += 1
                                        continue
                                    if is_video and Path(relative).suffix.lower() not in SUPPORTED_EXTENSIONS:
                                        skipped += 1
                                        unsupported_references += 1
                                        continue
                                    remote_media_path = self._unc_path(server, share, relative)
                                    if remote_media_path in seen_remote:
                                        continue
                                    seen_remote.add(remote_media_path)
                                    total_media += 1
                                    cached_path = None
                                    try:
                                        cached_path = executor.submit(
                                            self._load_remote_media,
                                            smbclient,
                                            remote_media_path,
                                            cancel_flag,
                                            config,
                                            is_image,
                                            f"{system}-{game_name or Path(relative).stem}-{field}",
                                        ).result()
                                    except OSError as exc:
                                        if exc.errno != errno.ENOENT:
                                            raise
                                        skipped += 1
                                        unresolved_references += 1
                                    except ValueError:
                                        skipped += 1
                                        unsupported_references += 1
                                    if cached_path is None and cancel_flag and cancel_flag():
                                        cancelled = True
                                    elif cached_path is not None:
                                        normalized = os.fspath(cached_path)
                                        if normalized not in seen:
                                            seen.add(normalized)
                                            resolved_paths.append(normalized)
                                    completed_media += 1
                                    if media_progress_callback:
                                        media_progress_callback(
                                            completed_media,
                                            total_media,
                                            remote_media_path,
                                            os.fspath(cached_path) if cached_path else None,
                                        )
                                    if cancelled:
                                        break
                                element.clear()
                                if cancelled:
                                    break
                    except ET.ParseError as exc:
                        raise ValueError(
                            f"Ungültige Batocera-gamelist.xml für {system}: {exc}"
                        ) from exc
                    except OSError as exc:
                        if exc.errno != errno.ENOENT:
                            raise
                        missing_gamelists.append(system)

            return result(cancelled=cancelled)
        finally:
            smbclient.delete_session(server)

    def _load_remote_media(
        self,
        smbclient,
        remote_path: str,
        cancel_flag: Callable[[], bool] | None,
        config: BatoceraConnectionConfig,
        convert_to_png: bool,
        display_name: str,
    ) -> Path | None:
        if cancel_flag and cancel_flag():
            return None
        stat = smbclient.stat(
            remote_path,
            username=config.username or None,
            password=config.password or None,
        )
        return self._cache_remote_file(
            smbclient,
            remote_path,
            stat.st_size,
            stat.st_mtime,
            cancel_flag,
            config,
            convert_to_png=convert_to_png,
            display_name=display_name,
        )

    def _cache_remote_file(
        self,
        smbclient,
        remote_path: str,
        size: int,
        modified: float,
        cancel_flag: Callable[[], bool] | None,
        config: BatoceraConnectionConfig,
        *,
        convert_to_png: bool = False,
        display_name: str = "",
    ) -> Path | None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_name = self._cache_name(remote_path, size, modified, display_name)
        cached_path = self.cache_dir / cache_name
        if convert_to_png:
            cached_path = cached_path.with_suffix(".png")
        if cached_path.is_file() and (
            (convert_to_png and cached_path.stat().st_size > 0)
            or cached_path.stat().st_size == size
        ):
            return cached_path

        partial_path = cached_path.with_suffix(cached_path.suffix + ".part")
        try:
            with smbclient.open_file(
                remote_path,
                mode="rb",
                username=config.username or None,
                password=config.password or None,
            ) as source, partial_path.open("wb") as destination:
                while True:
                    if cancel_flag and cancel_flag():
                        return None
                    chunk = source.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    destination.write(chunk)
            if partial_path.stat().st_size != size:
                raise OSError(
                    f"Unvollständiger SMB-Download für {Path(remote_path).name}"
                )
            if convert_to_png:
                try:
                    from PIL import Image, UnidentifiedImageError

                    png_partial_path = cached_path.with_suffix(".png.part")
                    try:
                        with Image.open(partial_path) as image:
                            image.load()
                            image.convert("RGBA").save(png_partial_path, format="PNG")
                        png_partial_path.replace(cached_path)
                    except (OSError, UnidentifiedImageError) as exc:
                        raise ValueError(
                            f"Ungültiges Batocera-Bild: {Path(remote_path).name}"
                        ) from exc
                    finally:
                        png_partial_path.unlink(missing_ok=True)
                except ImportError as exc:
                    raise RuntimeError(
                        "Artwork-Import benötigt Pillow."
                    ) from exc
            else:
                partial_path.replace(cached_path)
            return cached_path
        finally:
            partial_path.unlink(missing_ok=True)
