"""Dense fixed-ROI temporal metrics with strict evidence gates.

The module accepts per-frame ROI means, not full decoded frames. It only
computes exposure-stop metrics when the caller proves that samples are
reference-validated scene-linear RGB from a stable ROI.
"""
from __future__ import annotations

from math import isfinite, log2
from statistics import median
from typing import Any


class DenseTemporalError(ValueError):
    """Raised when dense temporal samples are malformed."""


def analyze_dense_roi_samples(
    samples: list[dict[str, Any]],
    *,
    expected_interval_seconds: float,
    minimum_samples: int = 24,
    luminance_coefficients: tuple[float, float, float] = (0.2126, 0.7152, 0.0722),
) -> dict[str, Any]:
    """Analyze a fixed ROI; scene-linear exposure metrics require validated evidence."""
    if isinstance(expected_interval_seconds, bool) or not isinstance(expected_interval_seconds, (int, float)) or not isfinite(expected_interval_seconds) or expected_interval_seconds <= 0:
        raise DenseTemporalError("expected_interval_seconds must be finite and positive.")
    if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or minimum_samples < 3:
        raise DenseTemporalError("minimum_samples must be an integer of at least 3.")
    if len(luminance_coefficients) != 3 or any(not isfinite(v) or v < 0 for v in luminance_coefficients) or abs(sum(luminance_coefficients) - 1.0) > 1e-6:
        raise DenseTemporalError("Luminance coefficients must be three non-negative values summing to 1.")

    normalized = []
    previous_time = None
    previous_frame = None
    roi_id = None
    domain = None
    transform_validated = True
    for index, sample in enumerate(samples):
        timestamp = sample.get("timestamp_seconds")
        frame_index = sample.get("frame_index")
        current_roi = sample.get("roi_id")
        current_domain = sample.get("measurement_domain")
        channels = sample.get("roi_mean")
        validated = sample.get("reference_validated_transform") is True
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not isfinite(timestamp) or timestamp < 0:
            raise DenseTemporalError(f"Sample {index} has an invalid timestamp.")
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise DenseTemporalError(f"Sample {index} has an invalid frame index.")
        if previous_time is not None and (timestamp <= previous_time or frame_index <= previous_frame):
            raise DenseTemporalError("Timestamps and frame indices must be strictly increasing.")
        if not isinstance(current_roi, str) or not current_roi:
            raise DenseTemporalError(f"Sample {index} is missing roi_id.")
        if roi_id is None:
            roi_id, domain = current_roi, current_domain
        elif current_roi != roi_id:
            raise DenseTemporalError("ROI identity changed during the temporal sample sequence.")
        if current_domain != domain:
            raise DenseTemporalError("Measurement domain changed during the temporal sample sequence.")
        if not isinstance(channels, dict):
            raise DenseTemporalError(f"Sample {index} is missing roi_mean.")
        rgb = []
        for channel in ("R", "G", "B"):
            value = channels.get(channel)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise DenseTemporalError(f"Sample {index} has invalid {channel} mean.")
            rgb.append(float(value))
        normalized.append((float(timestamp), frame_index, tuple(rgb)))
        previous_time, previous_frame = float(timestamp), frame_index
        transform_validated = transform_validated and validated

    if not normalized:
        return {
            "status": "unavailable",
            "sample_count": 0,
            "flicker_assessment": {"status": "unavailable", "reason": "No samples supplied."},
            "exposure_drift_assessment": {"status": "unavailable", "reason": "No samples supplied."},
        }

    intervals = [normalized[i][0] - normalized[i - 1][0] for i in range(1, len(normalized))]
    median_interval = median(intervals) if intervals else None
    interval_tolerance = expected_interval_seconds * 0.05
    dense_sampling = (
        len(normalized) >= minimum_samples
        and median_interval is not None
        and abs(median_interval - expected_interval_seconds) <= interval_tolerance
        and all(abs(value - expected_interval_seconds) <= interval_tolerance for value in intervals)
    )
    stable_roi = True  # ROI identity was enforced above.
    linear_evidence = domain == "linear_light_rgb" and transform_validated
    luminance = [
        sum(channel * coefficient for channel, coefficient in zip(rgb, luminance_coefficients, strict=True))
        for _, _, rgb in normalized
    ]
    positive = all(value > 0 for value in luminance)
    first_last_stops = log2(luminance[-1] / luminance[0]) if len(luminance) > 1 and positive else None

    flicker = {
        "status": "inconclusive",
        "reason": "Dense samples alone do not establish periodic flicker; frequency-domain and motion/scene controls are still required.",
    }
    if not dense_sampling:
        flicker = {
            "status": "unavailable",
            "reason": "Insufficient sample count or irregular frame intervals for dense temporal analysis.",
        }

    exposure = {
        "status": "unavailable",
        "reason": "Requires reference-validated scene-linear RGB, a fixed ROI, and positive luminance samples.",
    }
    if linear_evidence and stable_roi and positive and len(normalized) >= minimum_samples:
        exposure = {
            "status": "reported",
            "first_to_last_delta_stops": first_last_stops,
            "sample_count": len(normalized),
            "interpretation": "ROI luminance change in scene-linear measurement domain; not proof of camera auto-exposure behavior.",
        }
    elif domain == "linear_light_rgb" and not transform_validated:
        exposure["reason"] = "Linear-light label is insufficient: reference_validated_transform must be true for every sample."

    return {
        "status": "reported",
        "measurement_domain": domain,
        "roi_id": roi_id,
        "sample_count": len(normalized),
        "median_interval_seconds": median_interval,
        "dense_sampling": dense_sampling,
        "luminance_coefficients": list(luminance_coefficients),
        "flicker_assessment": flicker,
        "exposure_drift_assessment": exposure,
        "limitations": [
            "ROI means cannot distinguish illumination changes from moving content inside the ROI.",
            "Flicker frequency and confidence are not estimated by this foundation.",
            "Exposure drift is reported only as first-to-last scene-linear ROI luminance delta in stops.",
        ],
    }
