"""Import already-scraped video media from a mounted Batocera SMB share."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.engine.conversion.core import SUPPORTED_EXTENSIONS


@dataclass(frozen=True)
class BatoceraImportResult:
    media_paths: tuple[str, ...]
    skipped_media: int = 0
    cancelled: bool = False
    games_seen: int = 0
    video_references: int = 0
    image_references: int = 0
    unresolved_references: int = 0
    unsupported_references: int = 0
    missing_gamelists: tuple[str, ...] = ()


class BatoceraMediaService:
    """Reads video references from Batocera gamelist.xml files on mounted shares."""

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _resolve_media_path(value: str, gamelist_path: Path) -> Path | None:
        value = value.strip()
        if not value or "://" in value:
            return None

        media_path = Path(value).expanduser()
        if not media_path.is_absolute():
            candidate = (gamelist_path.parent / media_path).resolve()
            return candidate if candidate.is_file() else None

        if media_path.is_file():
            return media_path.resolve()

        parts = media_path.parts
        if len(parts) > 2 and parts[1].lower() == "userdata":
            relative_to_userdata = Path(*parts[2:])
            for mount_ancestor in (gamelist_path.parent, *gamelist_path.parents):
                candidate = (mount_ancestor / relative_to_userdata).resolve()
                if candidate.is_file():
                    return candidate
        return None

    def import_videos(
        self,
        gamelist_paths: Iterable[str | Path],
        *,
        cancel_flag: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, Path], None] | None = None,
    ) -> BatoceraImportResult:
        """Resolve supported ``<video>`` entries to existing files on the share."""
        lists = [Path(path).expanduser() for path in gamelist_paths]
        resolved_paths: list[str] = []
        seen: set[str] = set()
        skipped_media = 0

        for index, gamelist_path in enumerate(lists, start=1):
            if cancel_flag and cancel_flag():
                return BatoceraImportResult(
                    tuple(resolved_paths), skipped_media, cancelled=True
                )
            if not gamelist_path.is_file():
                raise FileNotFoundError(f"Batocera gamelist not found: {gamelist_path}")
            if progress_callback:
                progress_callback(index, len(lists), gamelist_path)

            try:
                for _, element in ET.iterparse(gamelist_path, events=("end",)):
                    if cancel_flag and cancel_flag():
                        return BatoceraImportResult(
                            tuple(resolved_paths), skipped_media, cancelled=True
                        )
                    if self._local_name(element.tag).lower() != "game":
                        continue

                    for child in element:
                        if self._local_name(child.tag).lower() != "video":
                            continue
                        value = child.text or ""
                        media_path = self._resolve_media_path(value, gamelist_path)
                        if (
                            media_path is None
                            or media_path.suffix.lower() not in SUPPORTED_EXTENSIONS
                        ):
                            skipped_media += 1
                            continue
                        normalized_path = os.fspath(media_path)
                        if normalized_path not in seen:
                            seen.add(normalized_path)
                            resolved_paths.append(normalized_path)
                    element.clear()
            except ET.ParseError as exc:
                raise ValueError(
                    f"Invalid Batocera gamelist XML at {gamelist_path}: {exc}"
                ) from exc

        return BatoceraImportResult(tuple(resolved_paths), skipped_media)
