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
    result = analyze_dense_roi_samples(samples(), expected_interval_seconds=1/25)
    assert result["dense_sampling"] is True
    assert result["exposure_drift_assessment"]["status"] == "reported"
    assert result["exposure_drift_assessment"]["first_to_last_delta_stops"] == pytest.approx(0.5)
    assert result["flicker_assessment"]["status"] == "inconclusive"


def test_unvalidated_linear_label_does_not_enable_exposure_metrics():
    result = analyze_dense_roi_samples(samples(validated=False), expected_interval_seconds=1/25)
    assert result["exposure_drift_assessment"]["status"] == "unavailable"
    assert "reference_validated_transform" in result["exposure_drift_assessment"]["reason"]


def test_nonlinear_rgb_never_claims_exposure_stops():
    result = analyze_dense_roi_samples(samples(domain="nonlinear_rgb_code_values"), expected_interval_seconds=1/25)
    assert result["exposure_drift_assessment"]["status"] == "unavailable"


def test_irregular_sampling_blocks_dense_assessment():
    result = analyze_dense_roi_samples(samples(irregular=True), expected_interval_seconds=1/25)
    assert result["dense_sampling"] is False
    assert result["flicker_assessment"]["status"] == "unavailable"


def test_roi_identity_must_remain_constant():
    data = samples()
    data[-1]["roi_id"] = "different-region"
    with pytest.raises(DenseTemporalError, match="ROI identity changed"):
        analyze_dense_roi_samples(data, expected_interval_seconds=1/25)


def test_timestamps_and_frame_indices_must_increase():
    data = samples()
    data[3]["frame_index"] = 2
    with pytest.raises(DenseTemporalError, match="strictly increasing"):
        analyze_dense_roi_samples(data, expected_interval_seconds=1/25)


def test_invalid_coefficients_are_rejected():
    with pytest.raises(DenseTemporalError, match="summing to 1"):
        analyze_dense_roi_samples(samples(), expected_interval_seconds=1/25, luminance_coefficients=(1, 1, 1))


def test_periodic_roi_signal_produces_frequency_candidate_not_confirmed_flicker():
    import math
    data = samples(count=128, domain="nonlinear_rgb_code_values", validated=False)
    for item in data:
        value = 0.4 + 0.02 * math.sin(2 * math.pi * 5 * item["timestamp_seconds"])
        item["roi_mean"] = {"R": value, "G": value, "B": value}
        item["tile_means"] = [{"R": value, "G": value, "B": value} for _ in range(4)]
    result = analyze_dense_roi_samples(data, expected_interval_seconds=1 / 25)
    assert result["frequency_analysis"]["status"] == "periodic_variation_candidate"
    assert result["frequency_analysis"]["frequency_hz"] == pytest.approx(5.0, abs=0.3)
    assert result["flicker_assessment"]["status"] == "candidate"
    assert result["spatial_coherence"]["coherence_fraction"] == 1.0


def test_abrupt_rgb_mean_step_is_reported_as_scene_boundary_candidate():
    data = samples(count=40, domain="nonlinear_rgb_code_values", validated=False)
    for item in data[20:]:
        item["roi_mean"] = {"R": 0.9, "G": 0.9, "B": 0.9}
    result = analyze_dense_roi_samples(data, expected_interval_seconds=1 / 25)
    assert any(item["sample_index"] == 20 for item in result["scene_boundary_candidates"])


def test_invalid_tile_measurements_are_rejected():
    data = samples(count=40)
    data[4]["tile_means"] = [{"R": 0.1, "G": 0.2, "B": 0.3}]
    with pytest.raises(DenseTemporalError, match="exactly four"):
        analyze_dense_roi_samples(data, expected_interval_seconds=1 / 25)
