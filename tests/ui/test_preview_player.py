import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from src.ui.preview.preview_player import PreviewPlayer
import customtkinter as ctk

def _make_player():
    with patch.object(ctk.CTkScrollableFrame, "__init__", return_value=None), \
         patch.object(PreviewPlayer, "_build_preview_area", return_value=None), \
         patch.object(PreviewPlayer, "grid_columnconfigure", return_value=None), \
         patch.object(PreviewPlayer, "grid_rowconfigure", return_value=None), \
         patch.object(PreviewPlayer, "bind", return_value=None):
        player = PreviewPlayer(MagicMock(), MagicMock())
        player._canvas = MagicMock()
        return player

def test_preview_player_instantiation():
    player = _make_player()
    assert player is not None


def test_single_source_frame_stays_visible_without_black_blink():
    player = _make_player()
    player._src_pil_frames = [Image.new("RGB", (16, 8))]
    player._src_frames = [object()]
    player._src_delays = [1000]
    player._src_idx = 0
    player._src_canvas = MagicMock()
    player._last_src_w = 300
    player._last_src_h = 170
    player.after = MagicMock()

    player._animate_src()

    player._src_canvas.create_image.assert_called_once()
    player._src_canvas.create_rectangle.assert_not_called()
    player.after.assert_not_called()


def test_static_auto_preview_draws_the_source_image(tmp_path, monkeypatch):
    player = _make_player()
    player._auto_canvas = MagicMock()
    player._auto_canvas.winfo_width.return_value = 300
    player._auto_canvas.winfo_height.return_value = 170
    photo_image = object()
    monkeypatch.setattr(
        "src.ui.preview.preview_player.ImageTk.PhotoImage",
        lambda _image: photo_image,
    )
    image_path = tmp_path / "logo.png"
    Image.new("RGBA", (600, 150), (255, 255, 255, 255)).save(image_path)

    player._show_static_auto_preview(str(image_path))

    player._auto_canvas.create_image.assert_called_once_with(
        150, 85, anchor="center", image=photo_image
    )
