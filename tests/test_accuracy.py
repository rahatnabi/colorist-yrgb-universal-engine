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
    result = measure_correction_accuracy(
        frame, PixelRegion(0, 0, 2, 1), AccuracyTarget()
    )
    assert result.measurement.measured_exposure_stops == pytest.approx(0.0, abs=1e-6)
    assert result.measurement.measured_neutral_spread == pytest.approx(0.0, abs=1e-6)
    assert result.score.label == "correction_accuracy"
    assert result.score.status == "scored"
    assert result.score.score == 100.0
    assert len(result.score.components) == 2


def test_exposure_deviation_reduces_correction_score():
    frame = make_frame([0.36, 0.36, 0.36])
    result = measure_correction_accuracy(
        frame, PixelRegion(0, 0, 2, 1),
        AccuracyTarget(exposure_tolerance_stops=0.1, falloff=2.0),
    )
    exposure = result.score.components[0]
    assert exposure.measured == pytest.approx(1.0, abs=1e-6)
    assert exposure.score == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"validated": False},
        {"transfer": "unknown"},
    ],
)
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
