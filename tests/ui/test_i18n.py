import json
from unittest.mock import patch

import pytest

from src.ui import i18n


def test_english_is_the_default_language(tmp_path):
    with patch.object(i18n, "language_path", return_value=tmp_path / "preferences.json"):
        assert i18n.load_language() == "en"


def test_language_preference_is_saved_without_discarding_other_settings(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    with patch.object(i18n, "language_path", return_value=path):
        i18n.save_language("de")
        assert i18n.load_language() == "de"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "theme": "dark",
        "language": "de",
    }


def test_unknown_saved_language_uses_english(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"language": "fr"}), encoding="utf-8")
    with patch.object(i18n, "language_path", return_value=path):
        assert i18n.load_language() == "en"


def test_translations_follow_selected_language():
    i18n.set_language("de")
    assert i18n.tr("Choose output folder") == "Ausgabeordner auswählen"
    i18n.set_language("en")
    assert i18n.tr("Ausgabeordner auswählen") == "Choose output folder"


def test_unsupported_language_is_rejected():
    with pytest.raises(ValueError, match="Unsupported UI language"):
        i18n.set_language("fr")
