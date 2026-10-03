import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from src.ui.preview.preview_panel import PreviewPanel
from src.ui.models.application_state import ApplicationState
import customtkinter as ctk

def _make_panel():
    with patch.object(ctk.CTkFrame, "__init__", return_value=None), \
         patch.object(PreviewPanel, "_collect_params", return_value=None, create=True), \
         patch.object(PreviewPanel, "grid_columnconfigure", return_value=None), \
         patch.object(PreviewPanel, "grid_rowconfigure", return_value=None), \
         patch.object(PreviewPanel, "bind", return_value=None), \
         patch('src.ui.preview.preview_controls.PreviewControls.build_top_bar', return_value=MagicMock()), \
         patch('src.ui.preview.preview_controls.PreviewControls.build_bottom_bar', return_value=MagicMock()), \
         patch('src.ui.preview.preview_player.PreviewPlayer', return_value=MagicMock()):
        panel = PreviewPanel(MagicMock(), ApplicationState())
        panel._preview_player = MagicMock()
        return panel

def test_preview_panel_instantiation():
    panel = _make_panel()
    assert panel is not None


def test_output_path_uses_only_the_explicit_output_folder():
    panel = _make_panel()
    with tempfile.TemporaryDirectory() as output_dir:
        panel.app_state.v_output_dir.get.return_value = output_dir
        assert panel._out_path("/source/gameplay.mp4") == os.path.join(
            output_dir, "gameplay_dmd.gif"
        )


def test_output_path_requires_an_explicit_existing_folder(tmp_path):
    panel = _make_panel()
    source = tmp_path / "gameplay.mp4"
    with pytest.raises(ValueError, match="Choose an existing output folder"):
        panel._out_path(str(source))
    assert not (tmp_path / "dmd_tmp").exists()


def test_output_path_avoids_existing_files_and_collisions(tmp_path):
    panel = _make_panel()
    panel.app_state.v_output_dir.get.return_value = str(tmp_path)
    (tmp_path / "game_dmd.gif").touch()
    reserved = set()

    first = panel._out_path("/source/game.mp4", reserved=reserved)
    second = panel._out_path("/another/game.avi", reserved=reserved)

    assert first.endswith("game_dmd_2.gif")
    assert second.endswith("game_dmd_3.gif")


class _FakeThread:
    """Runs the target synchronously so tests can inspect the submitted tasks
    without dealing with real background threads."""
    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _with_multi_select(panel, tmp_path, iids_to_paths):
    lp = MagicMock()
    lp._tree.selection.return_value = list(iids_to_paths.keys())
    lp._file_data = dict(iids_to_paths)
    panel._left_panel = lp
    panel.app_state.v_output_dir.get.return_value = str(tmp_path)
    panel.app_state.v_per_gif_config.get.return_value = False
    # Avoid popping a real OS file-picker dialog during the test.
    panel._choose_output_folder = MagicMock(return_value=str(tmp_path))
    # _collect_params normally reads real tk widgets; stub it for this unit test.
    panel._collect_params = MagicMock(return_value={})
    return lp


class TestConvertSelectedMultiSelection:
    def test_no_selection_shows_info(self):
        panel = _make_panel()
        lp = MagicMock()
        lp._tree.selection.return_value = ()
        panel._left_panel = lp
        with patch("src.ui.preview.preview_panel.messagebox") as mock_msg:
            panel.convert_selected()
        mock_msg.showinfo.assert_called_once()

    def test_busy_shows_warning_and_does_not_convert(self, tmp_path):
        panel = _make_panel()
        panel._busy = True
        _with_multi_select(panel, tmp_path, {"iid1": "/a.mp4"})
        with patch("src.ui.preview.preview_panel.messagebox") as mock_msg, \
             patch("src.ui.preview.preview_panel.threading.Thread", _FakeThread), \
             patch.object(panel, "_run_tasks") as mock_run:
            panel.convert_selected()
        mock_msg.showwarning.assert_called_once()
        mock_run.assert_not_called()

    def test_single_file_selected_builds_one_task_with_trim(self, tmp_path):
        panel = _make_panel()
        _with_multi_select(panel, tmp_path, {"iid1": "/a.mp4"})
        panel._get_trim = MagicMock(return_value=(1.0, 2.0))
        captured = {}

        def fake_run_tasks(tasks, params):
            captured["tasks"] = tasks

        with patch("src.ui.preview.preview_panel.threading.Thread", _FakeThread), \
             patch.object(panel, "_run_tasks", side_effect=fake_run_tasks):
            panel.convert_selected()

        tasks = captured["tasks"]
        assert len(tasks) == 1
        src, out, start_s, end_s, iid = tasks[0]
        assert src == "/a.mp4"
        assert (start_s, end_s) == (1.0, 2.0)
        assert iid == "iid1"

    def test_multiple_files_selected_converts_all_ignoring_trim(self, tmp_path):
        panel = _make_panel()
        _with_multi_select(
            panel, tmp_path, {"iid1": "/a.mp4", "iid2": "/b.mp4", "iid3": "/c.mp4"}
        )
        panel._get_trim = MagicMock(return_value=(1.0, 2.0))
        captured = {}

        def fake_run_tasks(tasks, params):
            captured["tasks"] = tasks

        with patch("src.ui.preview.preview_panel.threading.Thread", _FakeThread), \
             patch.object(panel, "_run_tasks", side_effect=fake_run_tasks):
            panel.convert_selected()

        tasks = captured["tasks"]
        assert len(tasks) == 3
        assert {t[0] for t in tasks} == {"/a.mp4", "/b.mp4", "/c.mp4"}
        # No per-file trim applied when converting a multi-selection.
        assert all(start_s is None and end_s is None for (_, _, start_s, end_s, _) in tasks)

    def test_multiple_files_selected_avoid_output_name_collisions(self, tmp_path):
        panel = _make_panel()
        _with_multi_select(
            panel, tmp_path,
            {"iid1": "/dirA/game.mp4", "iid2": "/dirB/game.mp4"},
        )
        captured = {}

        def fake_run_tasks(tasks, params):
            captured["tasks"] = tasks

        with patch("src.ui.preview.preview_panel.threading.Thread", _FakeThread), \
             patch.object(panel, "_run_tasks", side_effect=fake_run_tasks):
            panel.convert_selected()

        out_names = sorted(os.path.basename(t[1]) for t in captured["tasks"])
        assert out_names == ["game_dmd.gif", "game_dmd_2.gif"]


class TestConvertSelectedButtonLabel:
    def test_single_selection_shows_singular_label(self):
        panel = _make_panel()
        panel.controls._btn_conv_sel = MagicMock()
        panel.controls.update_convert_selected_button(1)
        panel.controls._btn_conv_sel.configure.assert_called_once()
        _, kwargs = panel.controls._btn_conv_sel.configure.call_args
        assert "selected files" not in kwargs["text"]

    def test_multi_selection_shows_count_in_label(self):
        panel = _make_panel()
        panel.controls._btn_conv_sel = MagicMock()
        panel.controls.update_convert_selected_button(3)
        _, kwargs = panel.controls._btn_conv_sel.configure.call_args
        assert "3" in kwargs["text"]
