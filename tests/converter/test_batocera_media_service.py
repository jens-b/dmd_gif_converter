import pytest

from src.engine.media_sources.batocera import BatoceraMediaService


def test_imports_existing_relative_and_userdata_videos_and_deduplicates(tmp_path):
    share = tmp_path / "share"
    system_dir = share / "roms" / "nes"
    video_dir = system_dir / "videos"
    video_dir.mkdir(parents=True)
    (video_dir / "trailer.mp4").write_bytes(b"video")
    (video_dir / "intro.gif").write_bytes(b"gif")
    gamelist = system_dir / "gamelist.xml"
    gamelist.write_text(
        """<gameList>
          <game><video>./videos/trailer.mp4</video></game>
          <game><video>/userdata/roms/nes/videos/intro.gif</video></game>
          <game><video>./videos/trailer.mp4</video></game>
          <game><video>./images/cover.jpg</video></game>
          <game><video>./videos/missing.mp4</video></game>
        </gameList>""",
        encoding="utf-8",
    )

    result = BatoceraMediaService().import_videos([gamelist])

    assert result.media_paths == (
        str((video_dir / "trailer.mp4").resolve()),
        str((video_dir / "intro.gif").resolve()),
    )
    assert result.skipped_media == 2
    assert not result.cancelled


def test_import_can_be_cancelled_before_reading(tmp_path):
    result = BatoceraMediaService().import_videos(
        [tmp_path / "not-read.xml"],
        cancel_flag=lambda: True,
    )

    assert result.media_paths == ()
    assert result.cancelled


def test_missing_gamelist_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="gamelist not found"):
        BatoceraMediaService().import_videos([tmp_path / "missing.xml"])


def test_malformed_gamelist_is_reported_with_path(tmp_path):
    gamelist = tmp_path / "gamelist.xml"
    gamelist.write_text("<gameList><game>", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Batocera gamelist XML"):
        BatoceraMediaService().import_videos([gamelist])
