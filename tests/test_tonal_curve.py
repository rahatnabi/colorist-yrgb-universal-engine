import pytest

from yrgb_engine.accuracy import AccuracyTarget, measure_correction_accuracy
from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.tonal_curve import ReferenceTonalCurve, TONAL_PERCENTILES, measure_reference_tonal_curve

def frame(values, validated=True):
    return PrecisionFrame.from_interleaved(
        width=7, height=1, channel_names=("R", "G", "B"), values=values,
        source_path="synthetic", decoder="test",
        encoding=ColorEncoding(
            primaries="rec709", transfer="linear", validated=validated,
            working_space_id="test-linear-rec709", transform_id="test-transform-v1",
        ), sample_domain="validated_scene_linear",
    )

def neutral_pixels(levels):
    return [channel for level in levels for channel in (level, level, level)]

def test_reference_tonal_curve_exact_match_is_integrated_into_correction_score():
    levels = [0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85]
    baseline = measure_reference_tonal_curve(frame(neutral_pixels(levels)), ReferenceTonalCurve(tuple([0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85])))
    reference = ReferenceTonalCurve(baseline.candidate_luminance, tolerance_stops=0.1)
    result = measure_correction_accuracy(
        frame(neutral_pixels(levels)), PixelRegion(0, 0, 7, 1),
        AccuracyTarget(reference_tonal_curve=reference),
    )
    curve = result.measurement.reference_tonal_curve
    assert curve is not None
    assert curve.percentiles == TONAL_PERCENTILES
    assert len(curve.deviation_stops) == 7
    assert result.score.label == "correction_accuracy"
    assert result.score.score == 100.0
    assert [c.metric for c in result.score.components[-7:]] == [
        f"tonal_curve_p{p}_deviation" for p in TONAL_PERCENTILES
    ]

def test_reference_curve_detects_one_stop_tonal_shift():
    reference_levels = [0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85]
    candidate_levels = [value * 2 for value in reference_levels]
    baseline_frame = frame(neutral_pixels(reference_levels))
    baseline = measure_reference_tonal_curve(baseline_frame, ReferenceTonalCurve(tuple(reference_levels)))
    reference = ReferenceTonalCurve(baseline.candidate_luminance, tolerance_stops=0.1)
    result = measure_correction_accuracy(
        frame(neutral_pixels(candidate_levels)), PixelRegion(0, 0, 7, 1),
        AccuracyTarget(reference_tonal_curve=reference),
    )
    assert result.measurement.reference_tonal_curve is not None
    assert result.measurement.reference_tonal_curve.deviation_stops == pytest.approx((1.0,) * 7, abs=1e-5)
    assert all(c.score == 0.0 for c in result.score.components[-7:])

def test_reference_curve_requires_seven_positive_monotonic_anchors():
    with pytest.raises(ValueError, match="seven values"):
        ReferenceTonalCurve((0.1, 0.2)).validate()
    with pytest.raises(ValueError, match="non-decreasing"):
        ReferenceTonalCurve((0.1, 0.2, 0.3, 0.4, 0.35, 0.6, 0.7)).validate()
    with pytest.raises(ValueError, match="positive"):
        ReferenceTonalCurve((0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)).validate()

def test_reference_curve_rejects_unvalidated_pipeline():
    reference = ReferenceTonalCurve((0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85))
    with pytest.raises(ValueError, match="validated"):
        measure_correction_accuracy(
            frame(neutral_pixels([0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85]), validated=False),
            PixelRegion(0, 0, 7, 1), AccuracyTarget(reference_tonal_curve=reference),
        )

def test_reference_curve_is_not_scored_when_no_reference_is_supplied():
    result = measure_correction_accuracy(
        frame(neutral_pixels([0.01, 0.03, 0.07, 0.18, 0.32, 0.55, 0.85])),
        PixelRegion(0, 0, 7, 1), AccuracyTarget(),
    )
    assert result.measurement.reference_tonal_curve is None
    assert not any(c.metric.startswith("tonal_curve_") for c in result.score.components)