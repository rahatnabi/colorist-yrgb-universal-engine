"""User-selected ROI chroma diagnostics for color grading.

This module does not detect faces, identify people, infer demographics, or define
a universal target for skin appearance. It reports signal-domain measurements
for a region selected by the operator.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, isfinite, pi, sin

from .exposure import PixelRegion
from .precision import PrecisionFrame


class SkinToneDiagnosticError(ValueError):
    """Raised when an ROI or its declared signal domain is invalid."""


@dataclass(frozen=True, slots=True)
class SkinToneDiagnostics:
    region: PixelRegion
    signal_domain: str
    sample_count: int
    mean_rgb: tuple[float, float, float]
    mean_hue_degrees: float | None
    hue_resultant_strength: float
    mean_saturation: float
    median_saturation: float
    mean_value: float
    median_value: float
    hue_percentiles_degrees: tuple[float, float, float] | None
    note: str


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _rgb_to_hsv(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    red, green, blue = rgb
    maximum, minimum = max(rgb), min(rgb)
    delta = maximum - minimum
    if delta == 0:
        hue = 0.0
    elif maximum == red:
        hue = 60.0 * (((green - blue) / delta) % 6.0)
    elif maximum == green:
        hue = 60.0 * (((blue - red) / delta) + 2.0)
    else:
        hue = 60.0 * (((red - green) / delta) + 4.0)
    saturation = delta / maximum if maximum > 0 else 0.0
    return hue % 360.0, saturation, maximum


def analyze_selected_region(
    frame: PrecisionFrame,
    region: PixelRegion,
    *,
    signal_domain: str,
    achromatic_saturation_epsilon: float = 1e-6,
) -> SkinToneDiagnostics:
    """Measure hue/chroma/value in an explicitly selected region.

    RGB samples are interpreted in the caller-declared signal domain; no transfer
    conversion is performed. Hue statistics use circular means. Percentiles are
    omitted when the region is entirely achromatic. The label 'skin tone' is a
    workflow name only: the function does not determine whether pixels are skin.
    """
    if not isinstance(signal_domain, str) or not signal_domain.strip():
        raise SkinToneDiagnosticError("An explicit signal_domain label is required.")
    if not isfinite(achromatic_saturation_epsilon) or achromatic_saturation_epsilon < 0:
        raise SkinToneDiagnosticError("achromatic_saturation_epsilon must be finite and non-negative.")
    names = [name.upper() for name in frame.channel_names]
    if not all(name in names for name in ("R", "G", "B")):
        raise SkinToneDiagnosticError("Region diagnostics require named R, G and B channels.")
    if region.x < 0 or region.y < 0 or region.width <= 0 or region.height <= 0:
        raise SkinToneDiagnosticError("Region coordinates and dimensions must be positive.")
    if region.x + region.width > frame.width or region.y + region.height > frame.height:
        raise SkinToneDiagnosticError("Region extends outside the frame.")

    ri, gi, bi = (names.index(name) for name in ("R", "G", "B"))
    hues: list[float] = []
    saturations: list[float] = []
    values: list[float] = []
    rgb_values: list[tuple[float, float, float]] = []
    for y in range(region.y, region.y + region.height):
        for x in range(region.x, region.x + region.width):
            offset = (y * frame.width + x) * frame.channel_count
            rgb = (
                float(frame.samples[offset + ri]),
                float(frame.samples[offset + gi]),
                float(frame.samples[offset + bi]),
            )
            if min(rgb) < 0:
                raise SkinToneDiagnosticError(
                    "HSV diagnostics require non-negative RGB samples in the declared domain."
                )
            hue, saturation, value = _rgb_to_hsv(rgb)
            rgb_values.append(rgb)
            saturations.append(saturation)
            values.append(value)
            if saturation > achromatic_saturation_epsilon:
                hues.append(hue)

    count = len(rgb_values)
    mean_rgb = tuple(sum(pixel[c] for pixel in rgb_values) / count for c in range(3))
    mean_saturation = sum(saturations) / count
    mean_value = sum(values) / count
    if hues:
        angles = [hue * pi / 180.0 for hue in hues]
        mean_sin = sum(sin(angle) for angle in angles) / len(angles)
        mean_cos = sum(cos(angle) for angle in angles) / len(angles)
        resultant = min(1.0, (mean_sin * mean_sin + mean_cos * mean_cos) ** 0.5)
        mean_hue = degrees(atan2(mean_sin, mean_cos)) % 360.0
        sorted_hues = sorted(hues)
        hue_percentiles = tuple(_percentile(sorted_hues, p) for p in (10, 50, 90))
    else:
        resultant = 0.0
        mean_hue = None
        hue_percentiles = None

    return SkinToneDiagnostics(
        region=region,
        signal_domain=signal_domain.strip(),
        sample_count=count,
        mean_rgb=mean_rgb,
        mean_hue_degrees=mean_hue,
        hue_resultant_strength=resultant,
        mean_saturation=mean_saturation,
        median_saturation=_percentile(saturations, 50),
        mean_value=mean_value,
        median_value=_percentile(values, 50),
        hue_percentiles_degrees=hue_percentiles,
        note=(
            "Operator-selected ROI statistics only; no skin classification or "
            "universal hue target is applied."
        ),
    )
