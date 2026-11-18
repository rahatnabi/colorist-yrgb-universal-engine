"""Normalized fixed-ROI statistics for decoded RGB frames.

Coordinates are normalized to [0, 1] and mapped to pixel bounds. Values are
reported in the decoder's existing sample domain; no color transform is applied.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

import numpy as np

from .precision import PrecisionFrame


class ROIAnalysisError(ValueError):
    """Raised for invalid ROI geometry or unsupported frame channels."""


def measure_normalized_rgb_roi(
    frame: PrecisionFrame,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict[str, Any]:
    values = (x, y, width, height)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in values):
        raise ROIAnalysisError("ROI coordinates must be finite numbers.")
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ROIAnalysisError("ROI must have positive size and remain inside normalized frame bounds.")
    channel_map = {name.upper(): index for index, name in enumerate(frame.channel_names)}
    if not all(name in channel_map for name in ("R", "G", "B")):
        raise ROIAnalysisError("Frame must contain named R, G, and B channels.")

    left = min(frame.width - 1, int(x * frame.width))
    top = min(frame.height - 1, int(y * frame.height))
    right = min(frame.width, max(left + 1, int((x + width) * frame.width + 0.999999)))
    bottom = min(frame.height, max(top + 1, int((y + height) * frame.height + 0.999999)))
    pixels = np.frombuffer(frame.samples, dtype=np.float32).reshape(
        frame.height, frame.width, frame.channel_count
    )[top:bottom, left:right, :]
    means = {
        name: float(pixels[:, :, channel_map[name]].mean(dtype=np.float64))
        for name in ("R", "G", "B")
    }
    return {
        "roi": {"x": x, "y": y, "width": width, "height": height, "coordinate_space": "normalized"},
        "pixel_bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
        "pixel_count": int((right - left) * (bottom - top)),
        "measurement_domain": frame.sample_domain,
        "channels": {name: {"mean": value} for name, value in means.items()},
        "interpretation": "decoder_sample_domain_roi_mean; no camera transform or scene-linear interpretation",
    }
