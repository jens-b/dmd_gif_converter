import io
import sys
import threading
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from PIL import Image
from smbprotocol.exceptions import SMBOSError

from src.engine.media_sources.batocera_smb import (
    BatoceraConnectionConfig,
    BatoceraConnectionStore,
    BatoceraSmbMediaService,
)


def test_smb_import_scans_gamelists_caches_media_and_deduplicates(
    tmp_path, monkeypatch
):
    share_root = r"\\batocera\share\roms"
    gamelist_path = share_root + r"\nes\gamelist.xml"
    video_path = share_root + r"\nes\videos\trailer.mp4"
    cover_path = share_root + r"\nes\images\cover.jpg"
    marquee_path = share_root + r"\nes\images\marquee.png"
    cover_buffer = io.BytesIO()
    Image.new("RGB", (4, 3), (200, 20, 40)).save(cover_buffer, format="JPEG")
    cover = cover_buffer.getvalue()
    marquee_buffer = io.BytesIO()
    Image.new("RGBA", (3, 4), (10, 200, 20, 128)).save(
        marquee_buffer, format="PNG"
    )
    marquee = marquee_buffer.getvalue()
    xml = (
        b"<gameList><game><name>Space Quest</name>"
        b"<video>./videos/trailer.mp4</video></game>"
        b"<game><name>Cover Art</name><image>./images/cover.jpg</image>"
        b"<marquee>./images/marquee.png</marquee></game>"
        b"<game><video>/userdata/roms/nes/videos/trailer.mp4</video></game>"
        b"<game><video>./videos/missing.mp4</video></game></gameList>"
    )
    video = b"sample video"
    calls = []

    def open_file(path, mode, **kwargs):
        calls.append(("open", path))
        if path == gamelist_path:
            return io.BytesIO(xml)
        if path in {video_path, cover_path, marquee_path}:
            content = {
                video_path: video,
                cover_path: cover,
                marquee_path: marquee,
            }[path]
            return io.BytesIO(content)
        raise SMBOSError(0xC0000034, path)

    remote_media = {
        video_path: video,
        cover_path: cover,
        marquee_path: marquee,
    }
    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: calls.append(("register", args)),
        open_file=open_file,
        stat=lambda path, **kwargs: (
            SimpleNamespace(st_size=len(remote_media[path]), st_mtime=123.0)
            if path in remote_media
            else (_ for _ in ()).throw(SMBOSError(0xC0000034, path))
        ),
        delete_session=lambda server: calls.append(("delete", server)),
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)

    progress = []
    result = BatoceraSmbMediaService(tmp_path / "cache").import_media(
        BatoceraConnectionConfig("batocera", "share", "user", "secret"),
        ["nes"],
        progress_callback=lambda current, total, path: progress.append(
            (current, total, path)
        ),
    )

    assert len(result.media_paths) == 3
    assert any(open(path, "rb").read() == video for path in result.media_paths)
    image_paths = [path for path in result.media_paths if path.endswith(".png")]
    assert len(image_paths) == 2
    assert all(Image.open(path).format == "PNG" for path in image_paths)
    assert any("nes-Space-Quest-video-" in path for path in result.media_paths)
    assert all(len(path.rsplit("/", 1)[-1]) > 20 for path in result.media_paths)
    assert result.skipped_media == 1
    assert result.games_seen == 4
    assert result.video_references == 3
    assert result.image_references == 2
    assert result.unresolved_references == 1
    assert result.unsupported_references == 0
    assert result.missing_gamelists == ()
    assert (1, 1, "nes") in progress
    assert ("register", ("batocera",)) in calls
    assert ("delete", "batocera") in calls


def test_import_can_limit_selected_media_categories(tmp_path, monkeypatch):
    share_root = r"\\batocera\share\roms"
    gamelist_path = share_root + r"\mame\gamelist.xml"
    video_path = share_root + r"\mame\trailer.mp4"
    xml = (
        b"<gameList><game><video>./trailer.mp4</video>"
        b"<image>./cover.jpg</image></game></gameList>"
    )
    video = b"video"
    opened = []

    def open_file(path, mode, **kwargs):
        opened.append(path)
        if path == gamelist_path:
            return io.BytesIO(xml)
        if path == video_path:
            return io.BytesIO(video)
        raise FileNotFoundError(path)

    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: None,
        open_file=open_file,
        stat=lambda path, **kwargs: SimpleNamespace(
            st_size=len(video), st_mtime=123.0
        ),
        delete_session=lambda server: None,
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)

    result = BatoceraSmbMediaService(tmp_path / "cache").import_media(
        BatoceraConnectionConfig("batocera", "share", "root", "linux"),
        ["mame"],
        include_images=False,
    )

    assert len(result.media_paths) == 1
    assert opened == [gamelist_path, video_path]


def test_lists_only_system_directories_under_roms(tmp_path, monkeypatch):
    calls = []

    class Entry:
        def __init__(self, name, is_dir):
            self.name = name
            self._is_dir = is_dir

        def is_dir(self):
            return self._is_dir

    entries = [Entry("nes", True), Entry("gamelist.xml", False), Entry("arcade", True)]
    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: calls.append(("register", args)),
        scandir=lambda path, **kwargs: (
            calls.append(("scandir", path)) or nullcontext(iter(entries))
        ),
        delete_session=lambda server: calls.append(("delete", server)),
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)

    systems = BatoceraSmbMediaService(tmp_path / "cache").list_systems(
        BatoceraConnectionConfig("batocera", "share", "root", "linux")
    )

    assert systems == ["arcade", "nes"]
    assert ("scandir", r"\\batocera\share\roms") in calls
    assert not any(call[0] == "walk" for call in calls)
    assert ("delete", "batocera") in calls


def test_import_requires_and_validates_selected_systems(tmp_path):
    service = BatoceraSmbMediaService(tmp_path / "cache")
    config = BatoceraConnectionConfig("batocera", "share", "root", "linux")

    with pytest.raises(ValueError, match="mindestens ein"):
        service.import_media(config, [])
    with pytest.raises(ValueError, match="Ungültiger"):
        service.import_media(config, ["../nes"])


def test_import_reports_missing_gamelist_instead_of_silent_empty_result(
    tmp_path, monkeypatch
):
    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: None,
        open_file=lambda *args, **kwargs: (_ for _ in ()).throw(
            SMBOSError(0xC0000034, args[0])
        ),
        delete_session=lambda server: None,
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)

    result = BatoceraSmbMediaService(tmp_path / "cache").import_media(
        BatoceraConnectionConfig("batocera", "share", "root", "linux"),
        ["mame"],
    )

    assert result.media_paths == ()
    assert result.missing_gamelists == ("mame",)


def test_import_skips_missing_smb_artwork_without_aborting_system(
    tmp_path, monkeypatch
):
    share_root = r"\\batocera\share\roms"
    gamelist_path = share_root + r"\mame\gamelist.xml"
    present_path = share_root + r"\mame\good.mp4"
    missing_path = share_root + r"\mame\housemn2-image.png"
    xml = (
        b"<gameList><game><name>House of the Dead</name>"
        b"<image>./housemn2-image.png</image></game>"
        b"<game><name>Working video</name><video>./good.mp4</video></game>"
        b"</gameList>"
    )
    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: None,
        open_file=lambda path, mode, **kwargs: (
            io.BytesIO(xml)
            if path == gamelist_path
            else io.BytesIO(b"video")
            if path == present_path
            else (_ for _ in ()).throw(SMBOSError(0xC0000034, path))
        ),
        stat=lambda path, **kwargs: (
            SimpleNamespace(st_size=5, st_mtime=123.0)
            if path == present_path
            else (_ for _ in ()).throw(SMBOSError(0xC0000034, path))
        ),
        delete_session=lambda server: None,
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)

    result = BatoceraSmbMediaService(tmp_path / "cache").import_media(
        BatoceraConnectionConfig("batocera", "share", "root", "linux"),
        ["mame"],
    )

    assert len(result.media_paths) == 1
    assert result.media_paths[0].endswith(".mp4")
    assert result.unresolved_references == 1


def test_import_reports_media_progress_without_parallel_smb_requests(
    tmp_path, monkeypatch
):
    share_root = r"\\batocera\share\roms"
    gamelist_path = share_root + r"\mame\gamelist.xml"
    images = {
        share_root + rf"\mame\image-{index}.png": io.BytesIO()
        for index in range(4)
    }
    for image in images.values():
        Image.new("RGB", (4, 3), (20, 40, 60)).save(image, format="PNG")
    image_data = {path: image.getvalue() for path, image in images.items()}
    xml = "<gameList>" + "".join(
        f"<game><name>Game {index}</name><image>./image-{index}.png</image></game>"
        for index in range(4)
    ) + "</gameList>"
    lock = threading.Lock()
    active = 0
    max_active = 0

    def stat(path, **kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return SimpleNamespace(st_size=len(image_data[path]), st_mtime=123.0)

    def open_file(path, mode, **kwargs):
        if path == gamelist_path:
            return io.BytesIO(xml.encode())
        return io.BytesIO(image_data[path])

    fake_smb = SimpleNamespace(
        register_session=lambda *args, **kwargs: None,
        open_file=open_file,
        stat=stat,
        delete_session=lambda server: None,
    )
    monkeypatch.setitem(sys.modules, "smbclient", fake_smb)
    progress = []

    result = BatoceraSmbMediaService(tmp_path / "cache").import_media(
        BatoceraConnectionConfig("batocera", "share", "root", "linux"),
        ["mame"],
        include_videos=False,
        media_progress_callback=lambda completed, total, remote, cached: progress.append(
            (completed, total, remote, cached)
        ),
    )

    assert len(result.media_paths) == 4
    assert max_active == 1
    assert [event[:2] for event in progress] == [(1, 1), (2, 2), (3, 3), (4, 4)]
    assert all(event[3] in result.media_paths for event in progress)


def test_smb_path_resolution_rejects_paths_outside_the_share():
    assert BatoceraSmbMediaService._share_relative_path(
        "../../../outside.mp4", "roms/nes/gamelist.xml"
    ) is None
    assert BatoceraSmbMediaService._share_relative_path(
        "../../bios/file.mp4", "roms/nes/gamelist.xml"
    ) is None
    assert BatoceraSmbMediaService._share_relative_path(
        "/userdata/roms/nes/videos/intro.gif", "roms/nes/gamelist.xml"
    ) == "roms/nes/videos/intro.gif"
    assert BatoceraSmbMediaService._share_relative_path(
        "/userdata/system/configs/video.mp4", "roms/nes/gamelist.xml"
    ) == "system/configs/video.mp4"
    assert BatoceraSmbMediaService._share_relative_path(
        "/userdata/../../outside.mp4", "roms/nes/gamelist.xml"
    ) is None


def test_connection_store_keeps_password_out_of_config_file(tmp_path, monkeypatch):
    passwords = {}
    fake_keyring = SimpleNamespace(
        set_password=lambda service, user, password: passwords.__setitem__(
            (service, user), password
        ),
        get_password=lambda service, user: passwords.get((service, user)),
        delete_password=lambda service, user: passwords.pop((service, user), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = BatoceraConnectionStore(tmp_path / "settings.json")

    store.save("batocera", "share", "player", "hidden", True)

    assert store.load() == {
        "server": "batocera",
        "share": "share",
        "username": "player",
    }
    assert store.load_password("batocera", "share", "player") == "hidden"
    assert "hidden" not in store.settings_path.read_text(encoding="utf-8")
