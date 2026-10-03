from src.ui.dialogs.batocera_system_dialog import BatoceraSystemDialog


def test_system_prefix_search_is_case_insensitive_and_wraps():
    systems = ["arcade", "atari2600", "mame", "mame-advmame", "nes"]

    assert BatoceraSystemDialog._find_system_prefix(systems, "m") == 2
    assert BatoceraSystemDialog._find_system_prefix(systems, "M", 3) == 3
    assert BatoceraSystemDialog._find_system_prefix(systems, "m", 4) == 2
    assert BatoceraSystemDialog._find_system_prefix(systems, "zz") is None
