import pytest

from yrgb_engine.shot_consistency import (
    ShotFrameSignal,
    ShotGroupingError,
    group_sampled_shots,
)


def signal(index, distance=None, candidate=False):
    return ShotFrameSignal(index, index * 1.5, distance, candidate)


def test_groups_sampled_frames_at_candidate_boundaries():
    groups = group_sampled_shots([
        signal(0), signal(1, 0.05), signal(2, 0.62, True),
        signal(3, 0.08), signal(4, 0.71, True), signal(5, 0.02),
    ])
    assert [(g.shot_index, g.start_frame_index, g.end_frame_index) for g in groups] == [
        (0, 0, 1), (1, 2, 3), (2, 4, 5),
    ]
    assert groups[1].boundary_candidate is True
    assert groups[1].boundary_histogram_distance == pytest.approx(0.62)
    assert groups[0].boundary_candidate is False


def test_empty_and_single_sample_groups():
    assert group_sampled_shots([]) == ()
    groups = group_sampled_shots([signal(0)])
    assert len(groups) == 1
    assert groups[0].sampled_frame_count == 1


def test_rejects_non_monotonic_and_invalid_histogram_signal():
    with pytest.raises(ShotGroupingError, match="increasing"):
        group_sampled_shots([signal(1), signal(1)])
    with pytest.raises(ShotGroupingError, match="0..1"):
        group_sampled_shots([signal(0, 1.2)])
