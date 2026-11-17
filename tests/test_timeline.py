import pytest

from yrgb_engine.precision import PrecisionFrame
from yrgb_engine.timeline import TimelineAnalysisError, iter_analyze_video_frames


def frame(rgb):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"), values=rgb,
        source_path="synthetic", decoder="test",
    )


def test_timeline_streams_frame_reports_and_detects_histogram_change():
    frames = [
        (0.0, frame([0.0, 0.0, 0.0])),
        (1.0, frame([0.0, 0.0, 0.0])),
        (2.0, frame([1.0, 1.0, 1.0])),
    ]
    reports = list(iter_analyze_video_frames(
        frames, shot_change_threshold=0.8, analysis_options={"histogram_bins": 16},
    ))
    assert [report.frame_index for report in reports] == [0, 1, 2]
    assert reports[0].histogram_distance is None
    assert reports[1].histogram_distance == pytest.approx(0.0)
    assert reports[1].shot_change_candidate is False
    assert reports[1].channel_mean_delta == pytest.approx((0.0, 0.0, 0.0))
    assert reports[2].channel_mean_delta == pytest.approx((1.0, 1.0, 1.0))
    assert reports[2].histogram_distance == pytest.approx(1.0)
    assert reports[2].shot_change_candidate is True


def test_timeline_threshold_is_optional_and_timestamp_must_increase():
    reports = list(iter_analyze_video_frames([
        (0.0, frame([0.0, 0.0, 0.0])),
        (1.0, frame([1.0, 1.0, 1.0])),
    ]))
    assert reports[1].histogram_distance == pytest.approx(1.0)
    assert reports[1].shot_change_candidate is False

    with pytest.raises(TimelineAnalysisError, match="strictly increasing"):
        list(iter_analyze_video_frames([
            (1.0, frame([0.0, 0.0, 0.0])),
            (1.0, frame([1.0, 1.0, 1.0])),
        ]))


def test_timeline_rejects_invalid_threshold_and_timestamp():
    with pytest.raises(TimelineAnalysisError, match="between 0 and 1"):
        list(iter_analyze_video_frames([], shot_change_threshold=1.1))
    with pytest.raises(TimelineAnalysisError, match="finite and non-negative"):
        list(iter_analyze_video_frames([(-0.1, frame([0.0, 0.0, 0.0]))]))
