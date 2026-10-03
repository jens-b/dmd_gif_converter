from PIL import Image
from unittest.mock import patch

from src.engine.conversion.core import DEFAULT_PARAMS, SUPPORTED_EXTENSIONS, process_file
from src.engine.conversion.ffmpeg_utils import get_metadata
from src.engine.conversion.services.job_expander import expand_conversion_jobs


def test_png_is_a_supported_source_and_has_static_metadata(tmp_path):
    image_path = tmp_path / "logo.png"
    Image.new("RGBA", (640, 160), (255, 255, 255, 128)).save(image_path)

    assert ".png" in SUPPORTED_EXTENSIONS
    assert get_metadata(str(image_path)) == (640, 160, 25.0, 1.0)


def test_auto_cutter_keeps_png_as_a_single_static_image_job(tmp_path):
    image_path = tmp_path / "logo.png"
    jobs = expand_conversion_jobs(
        [("logo-iid", str(image_path))],
        {"auto_cutter_enabled": True, "auto_cutter_top_n": 5},
    )

    assert len(jobs) == 1
    assert jobs[0][0] == "logo-iid"
    assert jobs[0][1] == str(image_path)
    assert jobs[0][3] is None


def test_png_conversion_stretches_to_exact_dmd_dimensions_without_scroll(tmp_path):
    for width, height in ((128, 32), (32, 64)):
        image_path = tmp_path / f"wide-logo-{width}x{height}.png"
        output_path = tmp_path / f"wide-logo-{width}x{height}.gif"
        Image.new("RGBA", (600, 150), (255, 255, 255, 255)).save(image_path)

        with (
            patch(
                "src.engine.conversion.core._run_ffmpeg_with_drain",
                return_value=(0, b""),
            ) as run_ffmpeg,
            patch(
                "src.engine.conversion.core.evaluate_gif_quality",
                return_value={"score": 100, "rating": "Good", "reasons": []},
            ),
        ):
            success, _ = process_file(
                str(image_path),
                str(output_path),
                params={
                    **DEFAULT_PARAMS,
                    "target_width": width,
                    "target_height": height,
                    "scroll_enabled": True,
                },
            )

        assert success
        command = run_ffmpeg.call_args.args[0]
        filter_graph = command[command.index("-filter_complex") + 1]
        assert f"scale={width}:{height}:flags=lanczos" in filter_graph
        assert "force_original_aspect_ratio" not in filter_graph
        assert "crop=" not in filter_graph
        assert command[command.index("-frames:v") + 1] == "1"


def test_png_layout_modes_generate_expected_filter_graphs(tmp_path):
    image_path = tmp_path / "layout.png"
    Image.new("RGBA", (600, 150), (255, 255, 255, 255)).save(image_path)
    expected_filters = {
        "stretch": "scale=32:64:flags=lanczos",
        "fit": "force_original_aspect_ratio=decrease",
        "fill": "force_original_aspect_ratio=increase",
    }
    expected_complements = {
        "stretch": None,
        "fit": "pad=32:64",
        "fill": "crop=32:64",
    }

    for mode, expected in expected_filters.items():
        with (
            patch(
                "src.engine.conversion.core._run_ffmpeg_with_drain",
                return_value=(0, b""),
            ) as run_ffmpeg,
            patch(
                "src.engine.conversion.core.evaluate_gif_quality",
                return_value={"score": 100, "rating": "Good", "reasons": []},
            ),
        ):
            success, _ = process_file(
                str(image_path),
                str(tmp_path / f"{mode}.gif"),
                params={
                    **DEFAULT_PARAMS,
                    "target_width": 32,
                    "target_height": 64,
                    "static_image_mode": mode,
                },
            )

        assert success
        command = run_ffmpeg.call_args.args[0]
        filter_graph = command[command.index("-filter_complex") + 1]
        assert expected in filter_graph
        complement = expected_complements[mode]
        if complement:
            assert complement in filter_graph
