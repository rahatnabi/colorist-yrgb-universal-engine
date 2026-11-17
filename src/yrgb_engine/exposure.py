"""Exposure and neutral-region diagnostics for explicitly validated linear RGB.

This module deliberately does not decode Log values, detect gray cards automatically,
or infer a camera transform. Callers must provide a validated linear-RGB frame and
an explicitly selected pixel region.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log2

from .precision import PrecisionFrame


class ExposureAnalysisError(ValueError):
    """Raised when exposure measurements are ambiguous or invalid."""


@dataclass(frozen=True, slots=True)
class PixelRegion:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ExposureRegionMeasurement:
    region: PixelRegion
    gray_reference: float
    luminance_coefficients: tuple[float, float, float]
    sample_count: int
    mean_rgb: tuple[float, float, float]
    mean_luminance: float
    median_luminance: float
    percentile_10_luminance: float
    percentile_90_luminance: float
    exposure_stops_from_gray: float | None
    channel_balance: tuple[float, float, float] | None
    neutral_spread: float | None
    neutral_candidate: bool | None


@dataclass(frozen=True, slots=True)
class TonalDistribution:
    pixel_count: int
    shadow_fraction: float
    highlight_fraction: float
    luminance_percentiles: tuple[float, float, float, float, float]


@dataclass(frozen=True, slots=True)
class RegionConsistency:
    exposure_delta_stops: float
    channel_balance_delta: tuple[float, float, float] | None


def _require_validated_linear_rgb(frame: PrecisionFrame) -> tuple[int, int, int]:
    names = [name.upper() for name in frame.channel_names]
    if not all(name in names for name in ("R", "G", "B")):
        raise ExposureAnalysisError("Exposure measurement requires named R, G and B channels.")
    if frame.encoding.transfer.casefold() not in {"linear", "linear-light", "scene-linear"}:
        raise ExposureAnalysisError("Frame transfer must explicitly identify linear RGB.")
    if not frame.encoding.validated:
        raise ExposureAnalysisError("Linear-RGB encoding must be marked validated.")
    return tuple(names.index(name) for name in ("R", "G", "B"))


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _luminance_samples(
    frame: PrecisionFrame,
    region: PixelRegion,
    coefficients: tuple[float, float, float],
) -> tuple[list[tuple[float, float, float]], list[float]]:
    ri, gi, bi = _require_validated_linear_rgb(frame)
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise ExposureAnalysisError("Region coordinates and dimensions must be positive.")
    if region.x + region.width > frame.width or region.y + region.height > frame.height:
        raise ExposureAnalysisError("Region extends outside the frame.")
    if any(not isfinite(value) or value < 0 for value in coefficients):
        raise ExposureAnalysisError("Luminance coefficients must be finite and non-negative.")
    if abs(sum(coefficients) - 1.0) > 1e-6:
        raise ExposureAnalysisError("Luminance coefficients must sum to 1.")

    rgb: list[tuple[float, float, float]] = []
    ys: list[float] = []
    for y in range(region.y, region.y + region.height):
        for x in range(region.x, region.x + region.width):
            offset = (y * frame.width + x) * frame.channel_count
            pixel = (
                float(frame.samples[offset + ri]),
                float(frame.samples[offset + gi]),
                float(frame.samples[offset + bi]),
            )
            if min(pixel) < 0:
                raise ExposureAnalysisError(
                    "Negative RGB values are not valid for this luminance exposure metric."
                )
            rgb.append(pixel)
            ys.append(sum(c * v for c, v in zip(coefficients, pixel, strict=True)))
    return rgb, ys


def measure_exposure_region(
    frame: PrecisionFrame,
    region: PixelRegion,
    *,
    luminance_coefficients: tuple[float, float, float],
    gray_reference: float = 0.18,
    neutral_tolerance: float = 0.02,
) -> ExposureRegionMeasurement:
    """Measure a user-selected region; gray-card identity is not inferred."""
    if not isfinite(gray_reference) or gray_reference <= 0:
        raise ExposureAnalysisError("gray_reference must be finite and positive.")
    if not isfinite(neutral_tolerance) or neutral_tolerance < 0:
        raise ExposureAnalysisError("neutral_tolerance must be finite and non-negative.")
    rgb, ys = _luminance_samples(frame, region, luminance_coefficients)
    mean_y = sum(ys) / len(ys)
    mean_rgb = tuple(sum(pixel[c] for pixel in rgb) / len(rgb) for c in range(3))
    channel_mean = sum(mean_rgb) / 3.0
    balance = None
    spread = None
    neutral_candidate = None
    if channel_mean > 0:
        ratios = tuple(value / channel_mean for value in mean_rgb)
        spread = max(ratios) - min(ratios)
        balance = tuple(value - 1.0 for value in ratios)
        neutral_candidate = spread <= neutral_tolerance
    stops = log2(mean_y / gray_reference) if mean_y > 0 else None
    return ExposureRegionMeasurement(
        region, gray_reference, luminance_coefficients, len(ys), mean_rgb,
        mean_y, _percentile(ys, 50), _percentile(ys, 10), _percentile(ys, 90),
        stops, balance, spread, neutral_candidate,
    )


def analyze_tonal_distribution(
    frame: PrecisionFrame,
    *,
    luminance_coefficients: tuple[float, float, float],
    shadow_threshold: float,
    highlight_threshold: float,
) -> TonalDistribution:
    """Report caller-defined linear-luminance shadow/highlight fractions."""
    if not all(isfinite(v) and v >= 0 for v in (shadow_threshold, highlight_threshold)):
        raise ExposureAnalysisError("Tonal thresholds must be finite and non-negative.")
    if shadow_threshold >= highlight_threshold:
        raise ExposureAnalysisError("Shadow threshold must be below highlight threshold.")
    _, ys = _luminance_samples(
        frame, PixelRegion(0, 0, frame.width, frame.height), luminance_coefficients
    )
    count = len(ys)
    return TonalDistribution(
        count,
        sum(value <= shadow_threshold for value in ys) / count,
        sum(value >= highlight_threshold for value in ys) / count,
        tuple(_percentile(ys, p) for p in (1, 10, 50, 90, 99)),
    )


def compare_exposure_regions(
    reference: ExposureRegionMeasurement,
    candidate: ExposureRegionMeasurement,
) -> RegionConsistency:
    """Compare two measurements made with the same gray reference convention."""
    if (reference.gray_reference != candidate.gray_reference
            or reference.luminance_coefficients != candidate.luminance_coefficients):
        raise ExposureAnalysisError("Measurements must use identical gray reference and luminance coefficients.")
    if reference.exposure_stops_from_gray is None or candidate.exposure_stops_from_gray is None:
        raise ExposureAnalysisError("Cannot compare a region with zero mean luminance.")
    if reference.channel_balance is None or candidate.channel_balance is None:
        balance_delta = None
    else:
        balance_delta = tuple(
            candidate.channel_balance[i] - reference.channel_balance[i]
            for i in range(3)
        )
    return RegionConsistency(
        candidate.exposure_stops_from_gray - reference.exposure_stops_from_gray,
        balance_delta,
    )
