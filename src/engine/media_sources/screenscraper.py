"""Secure storage for ScreenScraper account and API credentials."""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from src.engine.conversion.core import SUPPORTED_EXTENSIONS


@dataclass(frozen=True)
class ScreenScraperCredentials:
    username: str = ""
    password: str = ""
    developer_id: str = ""
    developer_password: str = ""

    def __repr__(self) -> str:
        return "ScreenScraperCredentials(<redacted>)"


@dataclass(frozen=True)
class ScreenScraperMedia:
    title: str
    media_type: str
    url: str
    extension: str

    def __repr__(self) -> str:
        return (
            f"ScreenScraperMedia(title={self.title!r}, "
            f"media_type={self.media_type!r}, url=<redacted>)"
        )


@dataclass(frozen=True)
class ScreenScraperSystem:
    system_id: str
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class ScreenScraperGame:
    game_id: str
    name: str
    system_id: str
    system_name: str

    def __str__(self) -> str:
        return f"{self.name} — {self.system_name}"


class ScreenScraperCredentialStore:
    """Keep ScreenScraper secrets in the operating system credential store."""

    SERVICE = "dmd_gif_converter.screenscraper"
    _ACCOUNTS = {
        "username": "account-username",
        "password": "account-password",
        "developer_id": "developer-id",
        "developer_password": "developer-password",
    }

    def load(self) -> ScreenScraperCredentials:
        import keyring

        values = {
            field: keyring.get_password(self.SERVICE, account) or ""
            for field, account in self._ACCOUNTS.items()
        }
        return ScreenScraperCredentials(**values)

    def save(self, credentials: ScreenScraperCredentials) -> None:
        import keyring

        for field, account in self._ACCOUNTS.items():
            value = getattr(credentials, field).strip()
            if value:
                keyring.set_password(self.SERVICE, account, value)
            elif keyring.get_password(self.SERVICE, account) is not None:
                keyring.delete_password(self.SERVICE, account)


class ScreenScraperService:
    """Search ScreenScraper game metadata and cache supported media locally."""

    API_BASE = "https://api.screenscraper.fr/api2/"
    SOFTNAME = "dmd_gif_converter"
    REQUEST_TIMEOUT = (8, 25)
    DOWNLOAD_CHUNK_SIZE = 64 * 1024
    MIN_REQUEST_INTERVAL = 1.0
    _request_lock = threading.Lock()
    _last_request_at = 0.0

    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self._default_cache_dir()

    @staticmethod
    def _default_cache_dir() -> Path:
        if sys.platform == "darwin":
            root = Path.home() / "Library/Caches"
        else:
            root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return root / "dmd_gif_converter" / "screenscraper"

    @staticmethod
    def _requests():
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "ScreenScraper benötigt requests. Installiere die UI-Abhängigkeiten."
            ) from exc
        return requests

    @staticmethod
    def _safe_error(status_code: int) -> str:
        return {
            400: "ScreenScraper hat die Suchanfrage abgelehnt (HTTP 400).",
            401: "ScreenScraper ist derzeit nicht verfügbar oder das Konto ist inaktiv (HTTP 401).",
            403: "Die API-Entwickler-Zugangsdaten wurden abgelehnt (HTTP 403).",
            404: "Kein passender Spieleintrag gefunden (HTTP 404).",
            429: "ScreenScraper meldet das Thread-Limit (HTTP 429). Bitte später erneut versuchen.",
            430: "Das tägliche ScreenScraper-Kontingent ist ausgeschöpft (HTTP 430).",
        }.get(status_code, f"ScreenScraper-Anfrage fehlgeschlagen (HTTP {status_code}).")

    def _request_json(
        self,
        endpoint: str,
        credentials: ScreenScraperCredentials,
        params: dict[str, str],
    ) -> dict:
        if not credentials.developer_id or not credentials.developer_password:
            raise ValueError(
                "Für ScreenScraper fehlen die API-Entwicklerdaten "
                "(devid und devpassword)."
            )
        query = {
            "devid": credentials.developer_id,
            "devpassword": credentials.developer_password,
            "softname": self.SOFTNAME,
            "output": "json",
            **params,
        }
        if credentials.username:
            query["ssid"] = credentials.username
            query["sspassword"] = credentials.password

        self._throttle()
        try:
            response = self._requests().get(
                self.API_BASE + endpoint,
                params=query,
                timeout=self.REQUEST_TIMEOUT,
            )
        except Exception as exc:
            raise RuntimeError(
                f"ScreenScraper konnte nicht erreicht werden ({type(exc).__name__})."
            ) from exc
        try:
            if response.status_code != 200:
                raise RuntimeError(self._safe_error(response.status_code))
            try:
                payload = response.json()
            except ValueError as exc:
                body = response.text.lower()
                if "erreur de login" in body:
                    raise RuntimeError(
                        "ScreenScraper hat die API-Entwickler-Zugangsdaten abgelehnt."
                    ) from exc
                raise RuntimeError(
                    "ScreenScraper hat keine gültige JSON-Antwort geliefert."
                ) from exc
            if not isinstance(payload, dict):
                raise RuntimeError("ScreenScraper hat eine ungültige Antwort geliefert.")
            response_data = payload.get("response")
            if isinstance(response_data, dict):
                error = response_data.get("error")
                if error:
                    raise RuntimeError(f"ScreenScraper: {str(error)[:200]}")
            return payload
        finally:
            response.close()

    @classmethod
    def _throttle(cls):
        with cls._request_lock:
            elapsed = time.monotonic() - cls._last_request_at
            delay = cls.MIN_REQUEST_INTERVAL - elapsed
            if delay > 0:
                time.sleep(delay)
            cls._last_request_at = time.monotonic()

    @staticmethod
    def _media_entries(payload: dict) -> tuple[dict, list[dict]]:
        response_data = payload.get("response")
        if not isinstance(response_data, dict):
            raise RuntimeError("In der ScreenScraper-Antwort fehlt der Spieleintrag.")
        game = response_data.get("jeu")
        if not isinstance(game, dict):
            raise RuntimeError(
                "Kein passendes Spiel gefunden. Prüfe Schreibweise und System."
            )
        raw_media = game.get("medias", [])
        if isinstance(raw_media, dict):
            raw_media = [raw_media]
        if not isinstance(raw_media, list):
            raw_media = []
        return game, [media for media in raw_media if isinstance(media, dict)]

    @staticmethod
    def _response_items(payload: dict, key: str) -> list[dict]:
        response_data = payload.get("response")
        items = response_data.get(key) if isinstance(response_data, dict) else None
        if isinstance(items, dict):
            for nested_key in (key[:-1], "systeme", "jeu"):
                nested = items.get(nested_key)
                if isinstance(nested, list):
                    items = nested
                    break
                if isinstance(nested, dict):
                    items = [nested]
                    break
            else:
                items = [items]
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _system_name(item: dict) -> str:
        names = item.get("noms")
        if isinstance(names, dict):
            for key in ("nom_eu", "nom_us", "nom_launchbox", "noms_commun"):
                value = names.get(key)
                if value:
                    return str(value).split(",")[0].strip()
        for key in ("nom", "name"):
            if item.get(key):
                return str(item[key]).strip()
        return ""

    def list_systems(
        self, credentials: ScreenScraperCredentials
    ) -> list[ScreenScraperSystem]:
        payload = self._request_json("systemesListe.php", credentials, {})
        systems = []
        for item in self._response_items(payload, "systemes"):
            system_id = str(item.get("id", "")).strip()
            name = self._system_name(item)
            if system_id.isdigit() and name:
                systems.append(ScreenScraperSystem(system_id, name))
        if not systems:
            raise RuntimeError("ScreenScraper hat keine Plattformen zurückgegeben.")
        systems.sort(key=lambda system: system.name.casefold())
        return systems

    def search_games(
        self,
        game_name: str,
        system: ScreenScraperSystem,
        credentials: ScreenScraperCredentials,
    ) -> list[ScreenScraperGame]:
        name = game_name.strip()
        if not name:
            raise ValueError("Bitte einen Spieltitel eingeben.")
        if not system.system_id.isdigit():
            raise ValueError("Bitte ein gültiges System auswählen.")
        payload = self._request_json(
            "jeuRecherche.php",
            credentials,
            {"recherche": name, "systemeid": system.system_id},
        )
        games = []
        for item in self._response_items(payload, "jeux"):
            game_id = str(item.get("id", "")).strip()
            if not game_id.isdigit():
                continue
            game_names = item.get("noms")
            resolved_name = str(item.get("nom", "")).strip()
            if isinstance(game_names, list):
                for localized_name in game_names:
                    if isinstance(localized_name, dict) and localized_name.get("text"):
                        resolved_name = str(localized_name["text"]).strip()
                        break
            if not resolved_name and isinstance(game_names, dict):
                resolved_name = str(game_names.get("text", "")).strip()
            if not resolved_name:
                resolved_name = name
            game_system = item.get("systeme")
            if isinstance(game_system, dict):
                resolved_system_id = str(game_system.get("id", system.system_id))
                system_name = str(game_system.get("noms", {}).get("nom_eu", system.name)) \
                    if isinstance(game_system.get("noms"), dict) else system.name
            else:
                resolved_system_id = str(item.get("systemeid", system.system_id))
                system_name = system.name
            games.append(
                ScreenScraperGame(
                    game_id,
                    resolved_name,
                    resolved_system_id,
                    system_name or system.name,
                )
            )
        return games

    def search_media(
        self,
        game: ScreenScraperGame,
        credentials: ScreenScraperCredentials,
    ) -> tuple[str, list[ScreenScraperMedia]]:
        payload = self._request_json(
            "jeuInfos.php",
            credentials,
            {"gameid": game.game_id},
        )
        game_details, raw_media = self._media_entries(payload)
        names = game_details.get("noms", [])
        resolved_name = game.name
        if isinstance(names, list):
            for item in names:
                if isinstance(item, dict) and item.get("text"):
                    resolved_name = str(item["text"])
                    break

        results: list[ScreenScraperMedia] = []
        seen_urls: set[str] = set()
        for item in raw_media:
            url = str(item.get("url", "")).strip()
            parsed_url = urlparse(url)
            extension = Path(parsed_url.path).suffix.lower()
            media_type = str(item.get("type", "media")).strip() or "media"
            if (
                parsed_url.scheme != "https"
                or not parsed_url.hostname
                or not self._is_screenscraper_host(parsed_url.hostname)
                or extension not in SUPPORTED_EXTENSIONS
                or url in seen_urls
            ):
                continue
            seen_urls.add(url)
            region = str(item.get("region", "")).strip()
            results.append(
                ScreenScraperMedia(
                    title=f"{resolved_name} — {media_type}"
                    + (f" ({region})" if region else ""),
                    media_type=media_type,
                    url=url,
                    extension=extension,
                )
            )
        return resolved_name, results

    @staticmethod
    def _is_screenscraper_host(hostname: str) -> bool:
        host = hostname.lower()
        return host == "screenscraper.fr" or host.endswith(".screenscraper.fr")

    def download_media(
        self,
        media: ScreenScraperMedia,
        *,
        cancel_flag: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str | None:
        if cancel_flag and cancel_flag():
            return None
        parsed_url = urlparse(media.url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or not self._is_screenscraper_host(parsed_url.hostname)
            or media.extension not in SUPPORTED_EXTENSIONS
        ):
            raise ValueError("ScreenScraper lieferte eine nicht erlaubte Medienadresse.")

        digest = hashlib.sha256(media.url.encode("utf-8")).hexdigest()
        destination = self.cache_dir / f"{digest}{media.extension}"
        if destination.is_file() and destination.stat().st_size > 0:
            return os.fspath(destination)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial_path = destination.with_suffix(destination.suffix + ".part")
        response = None
        try:
            try:
                response = self._requests().get(
                    media.url, stream=True, timeout=self.REQUEST_TIMEOUT
                )
            except Exception as exc:
                raise RuntimeError(
                    f"ScreenScraper-Medium konnte nicht geladen werden "
                    f"({type(exc).__name__})."
                ) from exc
            final_url = urlparse(response.url)
            if (
                response.status_code != 200
                or final_url.scheme != "https"
                or not final_url.hostname
                or not self._is_screenscraper_host(final_url.hostname)
            ):
                raise RuntimeError(
                    self._safe_error(response.status_code)
                    if response.status_code != 200
                    else "ScreenScraper leitete auf eine nicht erlaubte Medienadresse um."
                )
            total = int(response.headers.get("Content-Length", 0) or 0)
            completed = 0
            with partial_path.open("wb") as output:
                for chunk in response.iter_content(self.DOWNLOAD_CHUNK_SIZE):
                    if cancel_flag and cancel_flag():
                        return None
                    if chunk:
                        output.write(chunk)
                        completed += len(chunk)
                        if progress_callback:
                            progress_callback(completed, total)
            if not completed:
                raise RuntimeError("ScreenScraper hat eine leere Mediendatei geliefert.")
            if total and completed != total:
                raise RuntimeError("ScreenScraper-Medium wurde unvollständig übertragen.")
            partial_path.replace(destination)
            return os.fspath(destination)
        finally:
            if response is not None:
                response.close()
            partial_path.unlink(missing_ok=True)
