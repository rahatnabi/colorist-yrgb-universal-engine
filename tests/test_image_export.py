import pytest

from yrgb_engine.cube import parse_cube_text
from yrgb_engine.image_export import ImageExportError, apply_cube_to_frame, save_frame_image
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def _identity_lut():
    return parse_cube_text(
        "LUT_3D_SIZE 2\n0 0 0\n0 0 1\n0 1 0\n0 1 1\n"
        "1 0 0\n1 0 1\n1 1 0\n1 1 1\n"
    )


def _frame(channels=("R", "G", "B"), values=(0.2, 0.4, 0.6)):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=channels, values=values,
        source_path="fixture", decoder="test",
        encoding=ColorEncoding(
            primaries="test", transfer="linear", validated=True,
            working_space_id="test-linear",
        ),
    )


def test_apply_cube_requires_exact_validated_input_space():
    graded = apply_cube_to_frame(
        _frame(), _identity_lut(),
        lut_input_space_id="test-linear",
        lut_output_space_id="display-test",
        lut_output_transfer="sRGB",
    )
    assert graded.encoding.working_space_id == "display-test"
    assert graded.encoding.transfer == "sRGB"
    assert graded.encoding.validated is False
    assert list(graded.samples) == pytest.approx([0.2, 0.4, 0.6])


def test_apply_cube_rejects_unknown_or_mismatched_space():
    unknown = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6), source_path="x", decoder="x",
    )
    with pytest.raises(ImageExportError, match="validated"):
        apply_cube_to_frame(
            unknown, _identity_lut(), lut_input_space_id="x",
            lut_output_space_id="y", lut_output_transfer="sRGB",
        )
    with pytest.raises(ImageExportError, match="does not match"):
        apply_cube_to_frame(
            _frame(), _identity_lut(), lut_input_space_id="wrong",
            lut_output_space_id="y", lut_output_transfer="sRGB",
        )


def test_apply_cube_preserves_auxiliary_channels():
    frame = _frame(("R", "G", "B", "A"), (0.2, 0.4, 0.6, 0.75))
    graded = apply_cube_to_frame(
        frame, _identity_lut(), lut_input_space_id="test-linear",
        lut_output_space_id="display-test", lut_output_transfer="sRGB",
    )
    assert graded.pixel(0, 0) == pytest.approx((0.2, 0.4, 0.6, 0.75))


def test_save_frame_image_requires_matching_output_space():
    with pytest.raises(ImageExportError, match="Output space"):
        save_frame_image(
            _frame(), "out.png", image_format="PNG",
            output_space_id="wrong", output_transfer="sRGB",
        )


def test_save_frame_image_png_round_trip(tmp_path):
    pytest.importorskip("PIL")
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B", "A"),
        values=(0.2, 0.4, 0.6, 0.5), source_path="fixture", decoder="test",
        encoding=ColorEncoding(working_space_id="sRGB", transfer="sRGB"),
    )
    path = save_frame_image(
        frame, tmp_path / "graded.png", image_format="PNG",
        output_space_id="sRGB", output_transfer="sRGB",
    )
    from PIL import Image
    with Image.open(path) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (51, 102, 153, 128)
