"""Streaming temporal analysis for decoded video frames.

Frames are supplied by a decoder. This module does not decode media or apply
color transforms; it compares analysis payloads in their existing sample domain.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import isfinite
from typing import Any

from .analysis import FrameAnalysis, analyze_frame
from .precision import PrecisionFrame


class TimelineAnalysisError(ValueError):
    """Raised when temporal frame inputs are invalid or inconsistent."""


@dataclass(frozen=True, slots=True)
class VideoFrameAnalysis:
    timestamp_seconds: float
    frame_index: int
    analysis: FrameAnalysis
    histogram_distance: float | None
    shot_change_candidate: bool


def _histogram_distance(previous: FrameAnalysis, current: FrameAnalysis) -> float:
    """Mean RGB total-variation distance, including histogram under/overflow."""
    distances = []
    for channel in ("R", "G", "B"):
        left = previous.histograms[channel]
        right = current.histograms[channel]
        if (left.minimum, left.maximum, len(left.counts)) != (
            right.minimum, right.maximum, len(right.counts)
        ):
            raise TimelineAnalysisError(
                "Histogram configurations changed between adjacent frames."
            )
        left_total = left.underflow + left.overflow + sum(left.counts)
        right_total = right.underflow + right.overflow + sum(right.counts)
        if left_total == 0 or right_total == 0:
            raise TimelineAnalysisError("Cannot compare an empty frame histogram.")
        left_bins = (left.underflow, *left.counts, left.overflow)
        right_bins = (right.underflow, *right.counts, right.overflow)
        distance = 0.5 * sum(
            abs(a / left_total - b / right_total)
            for a, b in zip(left_bins, right_bins, strict=True)
        )
        distances.append(distance)
    return sum(distances) / len(distances)


def iter_analyze_video_frames(
    frames: Iterable[tuple[float, PrecisionFrame]],
    *,
    shot_change_threshold: float | None = None,
    analysis_options: dict[str, Any] | None = None,
) -> Iterator[VideoFrameAnalysis]:
    """Analyze decoded frames incrementally, retaining only the previous analysis.

    The caller supplies (timestamp_seconds, PrecisionFrame) pairs, typically from
    FFmpeg or an image-sequence decoder. Shot-change scores are histogram
    distribution distances in [0, 1], not a semantic scene detector.
    """
    if shot_change_threshold is not None and not 0.0 <= shot_change_threshold <= 1.0:
        raise TimelineAnalysisError("shot_change_threshold must be between 0 and 1.")
    options = dict(analysis_options or {})
    previous_analysis: FrameAnalysis | None = None
    previous_timestamp: float | None = None

    for index, (timestamp, frame) in enumerate(frames):
        if not isfinite(timestamp) or timestamp < 0:
            raise TimelineAnalysisError("Frame timestamps must be finite and non-negative.")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise TimelineAnalysisError("Frame timestamps must be strictly increasing.")
        current = analyze_frame(frame, **options)
        distance = (
            _histogram_distance(previous_analysis, current)
            if previous_analysis is not None else None
        )
        yield VideoFrameAnalysis(
            timestamp_seconds=timestamp,
            frame_index=index,
            analysis=current,
            histogram_distance=distance,
            shot_change_candidate=(
                shot_change_threshold is not None
                and distance is not None
                and distance >= shot_change_threshold
            ),
        )
        previous_analysis = current
        previous_timestamp = timestamp
