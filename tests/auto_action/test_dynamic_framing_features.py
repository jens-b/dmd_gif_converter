from src.engine.config.auto_action_config import AutoActionConfig
from src.plugins.detectors.detector import _union_rois


def test_group_framing_unions_separate_subject_boxes():
    assert _union_rois([(10, 20, 15, 30), (60, 40, 20, 25), (30, 5, 10, 10)]) == (
        10, 5, 70, 60
    )


def test_group_framing_handles_no_subjects():
    assert _union_rois([]) is None


def test_new_framing_options_round_trip_through_conversion_params():
    config = AutoActionConfig.from_params({
        "action_subject_framing": "primary",
        "action_dynamic_zoom_all_sizes": True,
    })

    assert config.subject_framing == "primary"
    assert config.dynamic_zoom_all_sizes is True
    assert config.to_params_dict()["action_subject_framing"] == "primary"
    assert config.to_params_dict()["action_dynamic_zoom_all_sizes"] is True
