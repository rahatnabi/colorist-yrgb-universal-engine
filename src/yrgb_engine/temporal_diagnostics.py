"""Descriptive within-shot temporal trends for sampled decoder RGB.

This module reports sample-domain statistics only. It does not infer exposure,
flicker, luminance, or camera behavior from nonlinear decoder RGB.
"""
from __future__ import annotations

from math import isfinite
from statistics import median
from typing import Any


class TemporalDiagnosticsError(ValueError):
    """Raised when sampled temporal inputs are malformed."""


def _linear_slope(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def analyze_sampled_temporal_trends(
    frames: list[dict[str, Any]],
    shot_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize per-channel sample means within provisional shot groups."""
    previous_time: float | None = None
    normalized: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        timestamp = frame.get("timestamp_seconds")
        frame_index = frame.get("frame_index")
        channels = frame.get("channels")
        if (
            isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
            or not isfinite(timestamp) or timestamp < 0
        ):
            raise TemporalDiagnosticsError(f"Frame {index} has an invalid timestamp.")
        if previous_time is not None and timestamp <= previous_time:
            raise TemporalDiagnosticsError("Sample timestamps must be strictly increasing.")
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise TemporalDiagnosticsError(f"Frame {index} has an invalid frame_index.")
        if not isinstance(channels, dict):
            raise TemporalDiagnosticsError(f"Frame {index} is missing channel statistics.")
        means: dict[str, float] = {}
        for channel in ("R", "G", "B"):
            stats = channels.get(channel)
            value = stats.get("mean") if isinstance(stats, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise TemporalDiagnosticsError(f"Frame {index} has invalid {channel} mean.")
            means[channel] = float(value)
        normalized.append({
            "frame_index": frame_index,
            "timestamp_seconds": float(timestamp),
            "means": means,
        })
        previous_time = float(timestamp)

    segments = []
    for group in shot_groups:
        start = group.get("start_frame_index")
        end = group.get("end_frame_index")
        shot_index = group.get("shot_index")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end, shot_index)):
            raise TemporalDiagnosticsError("Shot group indices must be integers.")
        if start < 0 or end < start or shot_index < 0:
            raise TemporalDiagnosticsError("Shot group indices are out of range.")
        selected = [item for item in normalized if start <= item["frame_index"] <= end]
        if not selected:
            continue
        channel_report = {}
        for channel in ("R", "G", "B"):
            values = [item["means"][channel] for item in selected]
            points = [(item["timestamp_seconds"], item["means"][channel]) for item in selected]
            channel_report[channel] = {
                "sample_count": len(values),
                "first_to_last_delta": values[-1] - values[0] if len(values) > 1 else None,
                "median": median(values),
                "minimum": min(values),
                "maximum": max(values),
                "linear_slope_per_second": _linear_slope(points),
            }
        segments.append({
            "shot_index": shot_index,
            "start_frame_index": start,
            "end_frame_index": end,
            "sample_count": len(selected),
            "channels": channel_report,
            "interpretation": (
                "descriptive_sample_domain_trend"
                if len(selected) >= 3 else "insufficient_samples_for_trend"
            ),
        })

    return {
        "status": "reported" if normalized else "unavailable",
        "measurement_domain": "nonlinear_rgb_code_values",
        "segments": segments,
        "flicker_assessment": {
            "status": "unavailable",
            "reason": (
                "Sparse timestamp samples do not establish frame-rate temporal behavior; "
                "dense frame sampling and a fixed region of interest are required."
            ),
        },
        "exposure_drift_assessment": {
            "status": "unavailable",
            "reason": (
                "Nonlinear decoder RGB means are not calibrated scene-linear exposure "
                "measurements; validated linear RGB and a fixed region of interest are required."
            ),
        },
        "limitations": [
            "Shot groups are provisional histogram-change segments, not confirmed semantic cuts.",
            "Channel trends can be caused by subject motion, reframing, lighting, or scene content.",
            "No exposure stops, flicker frequency, or camera auto-exposure behavior is inferred.",
        ],
    }
