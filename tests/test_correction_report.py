import pytest

from yrgb_engine.accuracy import AccuracyTarget, measure_correction_accuracy
from yrgb_engine.correction_report import build_correction_accuracy_report
from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.tonal_curve import ReferenceTonalCurve, measure_reference_tonal_curve


def frame(rgb):
    return PrecisionFrame.from_interleaved(
        width=2, height=1, channel_names=("R", "G", "B"), values=rgb * 2,
        source_path="synthetic", decoder="test",
        encoding=ColorEncoding(
            primaries="rec709", transfer="linear", validated=True,
            working_space_id="test-linear-rec709", transform_id="fixture-transform-v1",
        ),
        sample_domain="validated_scene_linear",
    )


def test_compact_report_groups_exposure_white_balance_and_reference_curve():
    image = frame([0.18, 0.18, 0.18])
    curve_measurement = measure_reference_tonal_curve(
        image,
        ReferenceTonalCurve((0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18)),
    )
    target = AccuracyTarget(
        reference_tonal_curve=ReferenceTonalCurve(curve_measurement.candidate_luminance),
    )
    result = measure_correction_accuracy(image, PixelRegion(0, 0, 2, 1), target)
    report = build_correction_accuracy_report(result, target)

    payload = report.to_dict()
    assert payload["label"] == "correction_accuracy"
    assert payload["status"] == "scored"
    assert payload["score"] == 100.0
    assert payload["exposure"]["metrics"][0]["measured"] == pytest.approx(0.0, abs=1e-6)
    assert payload["white_balance"]["score"] == 100.0
    assert [item["name"] for item in payload["reference_tonal_curve"]["metrics"]] == [
        "P1", "P10", "P25", "P50", "P75", "P90", "P99"
    ]
    assert payload["reference_tonal_curve"]["score"] == 100.0
    assert payload["working_space_id"] == "test-linear-rec709"


def test_report_marks_missing_reference_curve_not_scored_without_inventing_values():
    image = frame([0.18, 0.18, 0.18])
    target = AccuracyTarget()
    result = measure_correction_accuracy(image, PixelRegion(0, 0, 2, 1), target)
    report = build_correction_accuracy_report(result, target)

    assert report.exposure.status == "scored"
    assert report.white_balance.status == "scored"
    assert report.reference_tonal_curve.status == "not_scored"
    assert report.reference_tonal_curve.score is None
    assert report.reference_tonal_curve.metrics == ()
