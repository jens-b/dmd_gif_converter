import pytest
from unittest.mock import patch, MagicMock
from src.ui.panels.left_panel import LeftPanel
from src.ui.models.application_state import ApplicationState

def _make_panel():
    import customtkinter as ctk
    with patch.object(ctk.CTkFrame, "__init__", return_value=None), \
         patch.object(LeftPanel, "_build_ui", return_value=None, create=True), \
         patch.object(LeftPanel, "_style_treeview", return_value=None):
        panel = LeftPanel(MagicMock(), ApplicationState())
        panel._tree = MagicMock()
        panel._btn_add_files = MagicMock()
        panel._btn_add_folder = MagicMock()
        panel._btn_clear = MagicMock()
        return panel

def test_left_panel_instantiation():
    panel = _make_panel()
    assert panel is not None

@patch('src.ui.panels.left_panel.filedialog.askopenfilenames')
def test_left_panel_add_files(mock_askfiles):
    mock_askfiles.return_value = ("/test/file1.mp4", "/test/file2.gif")
    panel = _make_panel()
    with patch.object(panel, '_batch_insert') as mock_add:
        panel.add_files()
        assert mock_add.call_count == 1


class TestTreeSelectPublishesSelectionCount:
    def test_empty_selection_publishes_zero(self):
        panel = _make_panel()
        panel._tree.selection.return_value = ()
        with patch('src.ui.panels.left_panel.EventBus') as mock_bus:
            panel._on_tree_select()
        mock_bus.publish.assert_called_once_with(
            mock_bus.publish.call_args[0][0], {"count": 0}
        )

    def test_multi_selection_publishes_count(self):
        panel = _make_panel()
        panel._tree.selection.return_value = ("iid1", "iid2")
        panel._tree.focus.return_value = "iid2"
        panel._file_data = {"iid1": "/a.gif", "iid2": "/b.gif"}
        panel.app_state.v_per_gif_config.get.return_value = False
        panel.app_state.v_auto_color_enabled.get.return_value = False
        panel._adv_refresh_job = None
        with patch('src.ui.panels.left_panel.EventBus') as mock_bus, \
             patch.object(panel, '_load_preview'):
            panel._on_tree_select()
        found = [c for c in mock_bus.publish.call_args_list if c[0][1] == {"count": 2}]
        assert found, "Expected a SELECTION_CHANGED publish with count=2"
