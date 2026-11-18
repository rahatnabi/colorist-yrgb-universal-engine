import pytest

from yrgb_engine.accuracy import AccuracyTarget, measure_correction_accuracy
from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def make_frame(rgb, *, validated=True, transfer="linear"):
    return PrecisionFrame.from_interleaved(
        width=2,
        height=1,
        channel_names=("R", "G", "B"),
        values=rgb * 2,
        source_path="synthetic",
        decoder="test",
        encoding=ColorEncoding(
            primaries="rec709",
            transfer=transfer,
            validated=validated,
            working_space_id="test-linear-rec709",
            transform_id="fixture-transform-v1",
        ),
        sample_domain="validated_scene_linear",
    )


def test_neutral_18_percent_roi_scores_full_correction_accuracy():
    frame = make_frame([0.18, 0.18, 0.18])
    result = measure_correction_accuracy(frame, PixelRegion(0, 0, 2, 1))
    assert result.measurement.measured_exposure_stops == pytest.approx(0.0, abs=1e-6)
    assert result.measurement.measured_neutral_spread == pytest.approx(0.0, abs=1e-6)
    assert result.measurement.measured_white_balance == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)
    assert result.score.label == "correction_accuracy"
    assert result.score.status == "scored"
    assert result.score.score == 100.0
    assert len(result.score.components) == 4


def test_exposure_deviation_reduces_correction_score():
    frame = make_frame([0.36, 0.36, 0.36])
    result = measure_correction_accuracy(
        frame, PixelRegion(0, 0, 2, 1),
        AccuracyTarget(exposure_tolerance_stops=0.1, falloff=2.0),
    )
    exposure = result.score.components[0]
    assert exposure.measured == pytest.approx(1.0, abs=1e-6)
    assert exposure.score == 0.0


def test_white_balance_channel_deviation_is_measured_and_scored():
    frame = make_frame([0.20, 0.18, 0.16])
    result = measure_correction_accuracy(
        frame, PixelRegion(0, 0, 2, 1),
        AccuracyTarget(white_balance_tolerance=0.001),
    )
    assert result.measurement.measured_white_balance is not None
    assert result.score.components[1].metric == "white_balance_red_deviation"
    assert result.score.components[1].score < 100.0
    assert result.score.components[3].metric == "white_balance_blue_deviation"


def test_tonal_structure_is_measured_and_scored_only_with_exercise_targets():
    frame = make_frame([0.18, 0.18, 0.18])
    target = AccuracyTarget(
        shadow_threshold=0.1,
        highlight_threshold=0.8,
        shadow_fraction_target=0.0,
        highlight_fraction_target=0.0,
    )
    result = measure_correction_accuracy(frame, PixelRegion(0, 0, 2, 1), target)
    assert result.measurement.tonal_shadow_fraction == 0.0
    assert result.measurement.tonal_highlight_fraction == 0.0
    assert len(result.score.components) == 6
    assert result.score.score == 100.0


def test_tonal_targets_must_be_complete():
    frame = make_frame([0.18, 0.18, 0.18])
    target = AccuracyTarget(shadow_threshold=0.1)
    with pytest.raises(ValueError, match="both thresholds and both target fractions"):
        measure_correction_accuracy(frame, PixelRegion(0, 0, 2, 1), target)


@pytest.mark.parametrize("kwargs", [{"validated": False}, {"transfer": "unknown"}])
def test_unvalidated_source_cannot_receive_accuracy_score(kwargs):
    frame = make_frame([0.18, 0.18, 0.18], **kwargs)
    with pytest.raises(ValueError, match="validated"):
        measure_correction_accuracy(frame, PixelRegion(0, 0, 2, 1))


def test_transform_and_working_space_identifiers_are_required():
    frame = make_frame([0.18, 0.18, 0.18])
    frame.encoding = ColorEncoding(
        primaries="rec709", transfer="linear", validated=True,
        working_space_id="test-linear-rec709",
    )
    with pytest.raises(ValueError, match="transform_id"):
        measure_correction_accuracy(frame, PixelRegion(0, 0, 2, 1))


def test_invalid_luminance_coefficients_are_rejected():
    frame = make_frame([0.18, 0.18, 0.18])
    with pytest.raises(ValueError, match="sum to 1"):
        measure_correction_accuracy(
            frame, PixelRegion(0, 0, 2, 1),
            AccuracyTarget(luminance_coefficients=(1.0, 1.0, 1.0)),
        )


def test_invalid_white_balance_target_is_rejected():
    frame = make_frame([0.18, 0.18, 0.18])
    with pytest.raises(ValueError, match="finite"):
        measure_correction_accuracy(
            frame, PixelRegion(0, 0, 2, 1),
            AccuracyTarget(white_balance_target=(0.0, float("nan"), 0.0)),
        )
