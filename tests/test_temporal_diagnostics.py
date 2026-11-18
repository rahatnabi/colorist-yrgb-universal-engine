import pytest

from yrgb_engine.temporal_diagnostics import (
    TemporalDiagnosticsError,
    analyze_sampled_temporal_trends,
)


def frame(index, means, timestamp=None):
    return {
        "frame_index": index,
        "timestamp_seconds": float(index if timestamp is None else timestamp),
        "channels": {
            name: {"mean": value} for name, value in zip(("R", "G", "B"), means, strict=True)
        },
    }


def group(start, end, shot=0):
    return {"shot_index": shot, "start_frame_index": start, "end_frame_index": end}


def test_reports_per_channel_trends_inside_shot_groups():
    frames = [
        frame(0, (0.1, 0.2, 0.3)),
        frame(1, (0.2, 0.3, 0.4)),
        frame(2, (0.3, 0.4, 0.5)),
        frame(3, (0.8, 0.7, 0.6)),
    ]
    result = analyze_sampled_temporal_trends(frames, [group(0, 2), group(3, 3, 1)])
    first = result["segments"][0]
    assert first["interpretation"] == "descriptive_sample_domain_trend"
    assert first["channels"]["R"]["first_to_last_delta"] == pytest.approx(0.2)
    assert first["channels"]["R"]["linear_slope_per_second"] == pytest.approx(0.1)
    assert result["segments"][1]["interpretation"] == "insufficient_samples_for_trend"
    assert result["flicker_assessment"]["status"] == "unavailable"
    assert result["exposure_drift_assessment"]["status"] == "unavailable"


def test_rejects_non_monotonic_timestamps():
    frames = [frame(0, (0.1, 0.1, 0.1), 1.0), frame(1, (0.2, 0.2, 0.2), 1.0)]
    with pytest.raises(TemporalDiagnosticsError, match="strictly increasing"):
        analyze_sampled_temporal_trends(frames, [group(0, 1)])


def test_rejects_missing_or_nonfinite_channel_means():
    bad = frame(0, (0.1, 0.2, 0.3))
    bad["channels"]["G"]["mean"] = float("nan")
    with pytest.raises(TemporalDiagnosticsError, match="invalid G mean"):
        analyze_sampled_temporal_trends([bad], [group(0, 0)])
