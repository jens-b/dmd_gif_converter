from io import BytesIO
import zipfile

from PIL import Image

from src.engine.conversion.services.launchbox_artwork_service import (
    LaunchBoxArtworkService,
)


METADATA_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<LaunchBox>
  <Game>
    <Name>Game: One</Name><DatabaseID>101</DatabaseID><Platform>Arcade</Platform>
  </Game>
  <Game>
    <Name>Game Two</Name><DatabaseID>202</DatabaseID><Platform>Console</Platform>
  </Game>
  <GameImage>
    <DatabaseID>101</DatabaseID><FileName>arcade-logo.png</FileName>
    <Type>Clear Logo</Type>
  </GameImage>
  <GameImage>
    <DatabaseID>101</DatabaseID><FileName>arcade-box.png</FileName>
    <Type>Box - Front</Type>
  </GameImage>
  <GameImage>
    <DatabaseID>202</DatabaseID><FileName>console-logo.png</FileName>
    <Type>Clear Logo</Type>
  </GameImage>
</LaunchBox>
"""


def _write_metadata_zip(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("LaunchBox/Metadata.xml", METADATA_XML)


def test_get_platforms_and_select_clear_logos(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_metadata_zip(cache_dir / "Metadata.zip")
    service = LaunchBoxArtworkService(cache_dir)

    assert service.get_platforms() == ["Arcade", "Console"]
    logos = service._logos_for_platforms({"arcade"})

    assert [(logo.database_id, logo.name, logo.filename) for logo in logos] == [
        ("101", "Game: One", "arcade-logo.png")
    ]
    assert service.index_path.is_file()

    def unexpected_metadata_read(_archive):
        raise AssertionError("Cached index should avoid reparsing Metadata.xml")

    service._metadata_member = unexpected_metadata_read
    assert service.get_platforms() == ["Arcade", "Console"]
    assert service._logos_for_platforms({"arcade"}) == logos


def test_download_logos_sanitizes_names_and_writes_png(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_metadata_zip(cache_dir / "Metadata.zip")
    image_data = BytesIO()
    Image.new("RGBA", (3, 2), (20, 40, 60, 128)).save(image_data, format="PNG")

    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield image_data.getvalue()

        def close(self):
            pass

    class Requests:
        @staticmethod
        def get(url, stream, timeout):
            assert stream is True
            assert timeout == service.REQUEST_TIMEOUT
            assert url == "https://images.launchbox-app.com/arcade-logo.png"
            return Response()

    monkeypatch.setattr(LaunchBoxArtworkService, "_requests", lambda _self: Requests)
    service = LaunchBoxArtworkService(cache_dir)

    paths, errors = service.download_logos(["Arcade"])

    assert errors == []
    assert len(paths) == 1
    assert paths[0].endswith("Arcade/Game_ One [101].png")
    with Image.open(paths[0]) as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (20, 40, 60, 128)

    def unexpected_request(*_args, **_kwargs):
        raise AssertionError("Cached LaunchBox logo should not be downloaded again")

    monkeypatch.setattr(Requests, "get", unexpected_request)
    cached_paths, cached_errors = service.download_logos(["Arcade"])
    assert cached_errors == []
    assert cached_paths == paths


def test_download_logos_requires_platform_selection(tmp_path):
    service = LaunchBoxArtworkService(tmp_path)

    try:
        service.download_logos(["  "])
    except ValueError as exc:
        assert "Select at least one" in str(exc)
    else:
        raise AssertionError("Expected empty platform selection to fail")


def test_download_cancellation_removes_partial_files(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_metadata_zip(cache_dir / "Metadata.zip")

    class Response:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"partial"
            cancel_state["cancelled"] = True
            yield b"more"

        def close(self):
            pass

    class Requests:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    cancel_state = {"cancelled": False}
    monkeypatch.setattr(LaunchBoxArtworkService, "_requests", lambda _self: Requests)
    service = LaunchBoxArtworkService(cache_dir)
    logo = service._logos_for_platforms({"arcade"})[0]

    try:
        service._download_logo(
            logo, cache_dir / "logos", cancel_flag=lambda: cancel_state["cancelled"]
        )
    except InterruptedError:
        pass
    else:
        raise AssertionError("Expected logo download to stop after cancellation")

    assert list((cache_dir / "logos").rglob("*")) == [
        cache_dir / "logos" / "Arcade"
    ]


def test_metadata_index_build_can_be_cancelled(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_metadata_zip(cache_dir / "Metadata.zip")
    service = LaunchBoxArtworkService(cache_dir)
    checks = {"count": 0}

    def cancel_during_index():
        checks["count"] += 1
        return checks["count"] > 2

    try:
        service.get_platforms(cancel_flag=cancel_during_index)
    except InterruptedError:
        pass
    else:
        raise AssertionError("Expected index parsing to stop after cancellation")

    assert not service.index_path.exists()
    assert not service.index_path.with_suffix(".sqlite.part").exists()
