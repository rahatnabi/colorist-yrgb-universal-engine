from array import array

import pytest

from yrgb_engine.native_grading import (
    NativeGradeSettings,
    NativeGradingError,
    apply_native_grade,
)
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def make_frame(*, validated=True, transfer="Linear", working_space="scene-linear-rec709"):
    return PrecisionFrame(
        width=2,
        height=1,
        channel_names=("R", "G", "B", "A"),
        samples=array("f", [0.18, 0.18, 0.18, 0.4, 1.5, 0.5, 0.25, 0.8]),
        source_path="fixture.exr",
        decoder="test",
        encoding=ColorEncoding(
            primaries="Rec.709",
            transfer=transfer,
            profile_id="test-profile",
            validated=validated,
            working_space_id=working_space,
            transform_id="test-transform",
        ),
    )


def test_native_grade_identity_preserves_linear_samples_and_alpha():
    frame = make_frame()
    result = apply_native_grade(
        frame, NativeGradeSettings(), working_space_id="scene-linear-rec709"
    )
    assert result.samples == frame.samples
    assert result.samples[3] == pytest.approx(0.4)
    assert result.samples[7] == pytest.approx(0.8)
    assert result.sample_domain == "validated_linear_native_grade_float32"


def test_native_grade_exposure_doubles_rgb_without_clamping():
    frame = make_frame()
    result = apply_native_grade(
        frame,
        NativeGradeSettings(exposure_stops=1.0, contrast=1.0, saturation=1.0),
        working_space_id="scene-linear-rec709",
    )
    assert result.samples[0] == pytest.approx(0.36)
    assert result.samples[4] > 1.0
    assert result.samples[3] == pytest.approx(0.4)


def test_native_grade_requires_validated_linear_frame():
    with pytest.raises(NativeGradingError, match="reference-validated"):
        apply_native_grade(
            make_frame(validated=False),
            NativeGradeSettings(),
            working_space_id="scene-linear-rec709",
        )
    with pytest.raises(NativeGradingError, match="linear-light"):
        apply_native_grade(
            make_frame(transfer="S-Log3"),
            NativeGradeSettings(),
            working_space_id="scene-linear-rec709",
        )


def test_native_grade_requires_exact_working_space_identity():
    with pytest.raises(NativeGradingError, match="does not match"):
        apply_native_grade(
            make_frame(),
            NativeGradeSettings(),
            working_space_id="acescg-linear",
        )


def test_native_grade_rejects_non_finite_or_out_of_range_controls():
    frame = make_frame()
    with pytest.raises(NativeGradingError, match="exposure_stops"):
        apply_native_grade(
            frame,
            NativeGradeSettings(exposure_stops=float("nan")),
            working_space_id="scene-linear-rec709",
        )
    with pytest.raises(NativeGradingError, match="contrast"):
        apply_native_grade(
            frame,
            NativeGradeSettings(contrast=4.0),
            working_space_id="scene-linear-rec709",
        )


def test_native_grade_supports_acescg_luminance_coefficients():
    frame = make_frame(working_space="acescg-linear")
    result = apply_native_grade(
        frame,
        NativeGradeSettings(saturation=0.0),
        working_space_id="acescg-linear",
    )
    assert result.samples[0] == pytest.approx(result.samples[1])
    assert result.samples[1] == pytest.approx(result.samples[2])
