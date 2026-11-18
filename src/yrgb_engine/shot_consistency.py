"""Shot grouping from sampled histogram-change candidates.

Groups are provisional: a histogram distribution change is not proof of a semantic
scene cut. The module only segments the sampled timeline and preserves evidence.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite


class ShotGroupingError(ValueError):
    """Raised for invalid sampled shot signals."""


@dataclass(frozen=True, slots=True)
class ShotFrameSignal:
    frame_index: int
    timestamp_seconds: float
    histogram_distance: float | None
    change_candidate: bool


@dataclass(frozen=True, slots=True)
class ShotGroup:
    shot_index: int
    start_frame_index: int
    end_frame_index: int
    start_seconds: float
    end_seconds: float
    sampled_frame_count: int
    boundary_candidate: bool
    boundary_histogram_distance: float | None


def group_sampled_shots(signals: Iterable[ShotFrameSignal]) -> tuple[ShotGroup, ...]:
    """Group ordered sampled frames; candidate frames begin provisional new groups."""
    items = list(signals)
    if not items:
        return ()
    for index, item in enumerate(items):
        if item.frame_index < 0 or not isfinite(item.timestamp_seconds) or item.timestamp_seconds < 0:
            raise ShotGroupingError("Frame indices and timestamps must be non-negative and finite.")
        if item.histogram_distance is not None and (
            not isfinite(item.histogram_distance) or not 0 <= item.histogram_distance <= 1
        ):
            raise ShotGroupingError("Histogram distances must be finite and within 0..1.")
        if index and (
            item.frame_index <= items[index - 1].frame_index
            or item.timestamp_seconds <= items[index - 1].timestamp_seconds
        ):
            raise ShotGroupingError("Shot signals must have increasing frame indices and timestamps.")

    groups: list[ShotGroup] = []
    start = 0
    shot_index = 0

    def append_group(end: int) -> None:
        first, last = items[start], items[end]
        boundary = first.change_candidate if start > 0 else False
        groups.append(ShotGroup(
            shot_index=shot_index,
            start_frame_index=first.frame_index,
            end_frame_index=last.frame_index,
            start_seconds=first.timestamp_seconds,
            end_seconds=last.timestamp_seconds,
            sampled_frame_count=end - start + 1,
            boundary_candidate=boundary,
            boundary_histogram_distance=first.histogram_distance if boundary else None,
        ))

    for index in range(1, len(items)):
        if items[index].change_candidate:
            append_group(index - 1)
            start = index
            shot_index += 1
    append_group(len(items) - 1)
    return tuple(groups)
