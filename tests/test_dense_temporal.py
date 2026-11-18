import pytest

from yrgb_engine.dense_temporal import DenseTemporalError, analyze_dense_roi_samples


def samples(count=30, *, domain="linear_light_rgb", validated=True, irregular=False):
    result = []
    for i in range(count):
        t = i / 25
        if irregular and i == count - 1:
            t += 0.02
        value = 0.18 * (2 ** (i / (count - 1) * 0.5))
        result.append({
            "timestamp_seconds": t,
            "frame_index": i,
            "roi_id": "center-subject",
            "measurement_domain": domain,
            "reference_validated_transform": validated,
            "roi_mean": {"R": value, "G": value, "B": value},
        })
    return result


def test_scene_linear_validated_roi_reports_exposure_delta_in_stops():
    result = analyze_dense_roi_samples(samples())
    assert result["dense_sampling"] is True
    assert result["exposure_drift_assessment"]["status"] == "reported"
    assert result["exposure_drift_assessment"]["first_to_last_delta_stops"] == pytest.approx(0.5)
    assert result["flicker_assessment"]["status"] == "inconclusive"


def test_unvalidated_linear_label_does_not_enable_exposure_metrics():
    result = analyze_dense_roi_samples(samples(validated=False))
    assert result["exposure_drift_assessment"]["status"] == "unavailable"
    assert "reference_validated_transform" in result["exposure_drift_assessment"]["reason"]


def test_nonlinear_rgb_never_claims_exposure_stops():
    result = analyze_dense_roi_samples(samples(domain="nonlinear_rgb_code_values"))
    assert result["exposure_drift_assessment"]["status"] == "unavailable"


def test_irregular_sampling_blocks_dense_assessment():
    result = analyze_dense_roi_samples(samples(irregular=True))
    assert result["dense_sampling"] is False
    assert result["flicker_assessment"]["status"] == "unavailable"


def test_roi_identity_must_remain_constant():
    data = samples()
    data[-1]["roi_id"] = "different-region"
    with pytest.raises(DenseTemporalError, match="ROI identity changed"):
        analyze_dense_roi_samples(data)


def test_timestamps_and_frame_indices_must_increase():
    data = samples()
    data[3]["frame_index"] = 2
    with pytest.raises(DenseTemporalError, match="strictly increasing"):
        analyze_dense_roi_samples(data)


def test_invalid_coefficients_are_rejected():
    with pytest.raises(DenseTemporalError, match="summing to 1"):
        analyze_dense_roi_samples(samples(), luminance_coefficients=(1, 1, 1))
