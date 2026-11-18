"""Parametric linear-RGB look development and 3D .cube LUT baking."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


class LookDevelopmentError(ValueError):
    """Raised for invalid look controls or RGB inputs."""


@dataclass(frozen=True, slots=True)
class LookSettings:
    exposure_stops: float = 0.0
    contrast: float = 1.0
    pivot: float = 0.18
    saturation: float = 1.0
    temperature_shift: float = 0.0
    tint_shift: float = 0.0
    luminance_coefficients: tuple[float, float, float] = (
        0.2126, 0.7152, 0.0722
    )
    master_curve: tuple[tuple[float, float], ...] = ((0.0, 0.0), (1.0, 1.0))


def validate_look(settings: LookSettings) -> None:
    scalar_ranges = {
        "exposure_stops": (-8.0, 8.0),
        "contrast": (0.0, 3.0),
        "pivot": (0.001, 1.0),
        "saturation": (0.0, 3.0),
        "temperature_shift": (-1.0, 1.0),
        "tint_shift": (-1.0, 1.0),
    }
    for name, (low, high) in scalar_ranges.items():
        value = getattr(settings, name)
        if not isfinite(value) or not low <= value <= high:
            raise LookDevelopmentError(f"{name} must be finite and within {low}..{high}.")
    coefficients = settings.luminance_coefficients
    if len(coefficients) != 3 or not all(isfinite(v) and v >= 0 for v in coefficients):
        raise LookDevelopmentError("Luminance coefficients must be three finite non-negative values.")
    if abs(sum(coefficients) - 1.0) > 1e-6:
        raise LookDevelopmentError("Luminance coefficients must sum to 1.")
    curve = settings.master_curve
    if len(curve) < 2:
        raise LookDevelopmentError("Master curve needs at least two control points.")
    previous_x = -float("inf")
    previous_y = -float("inf")
    for x, y in curve:
        if not isfinite(x) or not isfinite(y) or not 0 <= x <= 1 or not 0 <= y <= 1:
            raise LookDevelopmentError("Master curve points must be finite and within 0..1.")
        if x <= previous_x or y < previous_y:
            raise LookDevelopmentError("Master curve must be strictly increasing in x and non-decreasing in y.")
        previous_x, previous_y = x, y
    if curve[0][0] != 0 or curve[-1][0] != 1:
        raise LookDevelopmentError("Master curve must include x=0 and x=1 endpoints.")


def _curve(value: float, points: tuple[tuple[float, float], ...]) -> float:
    # Piecewise-linear interpolation with endpoint extension; LUT input domain is 0..1.
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            amount = (value - x0) / (x1 - x0)
            return y0 * (1.0 - amount) + y1 * amount
    raise LookDevelopmentError("Could not evaluate master curve.")


def apply_look_rgb(
    rgb: tuple[float, float, float],
    settings: LookSettings,
) -> tuple[float, float, float]:
    """Apply creative controls in an explicitly declared linear RGB coordinate system.

    Temperature/tint are artistic RGB gain offsets, not Kelvin or a chromatic
    adaptation transform. Values are not clipped; output LUT coordinates are
    sampled only within the declared 0..1 domain.
    """
    validate_look(settings)
    if len(rgb) != 3 or not all(isfinite(v) for v in rgb):
        raise LookDevelopmentError("RGB input must contain three finite values.")
    exposure = 2.0 ** settings.exposure_stops
    temp = settings.temperature_shift
    tint = settings.tint_shift
    gains = (
        exposure * (2.0 ** (0.35 * temp)),
        exposure * (2.0 ** (0.25 * tint)),
        exposure * (2.0 ** (-0.35 * temp)),
    )
    adjusted = [rgb[i] * gains[i] for i in range(3)]
    contrasted = [
        settings.pivot + (value - settings.pivot) * settings.contrast
        for value in adjusted
    ]
    luma = sum(contrasted[i] * settings.luminance_coefficients[i] for i in range(3))
    saturated = [
        luma + (contrasted[i] - luma) * settings.saturation for i in range(3)
    ]
    return tuple(_curve(value, settings.master_curve) for value in saturated)


def bake_3d_cube(
    settings: LookSettings,
    *,
    size: int,
    title: str,
    input_space_id: str,
) -> str:
    """Bake a parametric look into a blue-fastest 3D .cube grid."""
    validate_look(settings)
    if size not in {17, 33, 35, 65}:
        raise LookDevelopmentError("LUT size must be 17, 33, 35 or 65.")
    if not title.strip() or not input_space_id.strip():
        raise LookDevelopmentError("Look title and explicit input-space ID are required.")
    safe_title = title.replace('"', "'").replace("\\n", " ").strip()
    lines = [
        f'TITLE "{safe_title}"',
        f"# COLORIST_YRGB_INPUT_SPACE={input_space_id}",
        "# COLORIST_YRGB_PROCESSING=linear-RGB-parametric-look",
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    denominator = size - 1
    for red in range(size):
        r = red / denominator
        for green in range(size):
            g = green / denominator
            for blue in range(size):
                b = blue / denominator
                result = apply_look_rgb((r, g, b), settings)
                lines.append(" ".join(f"{value:.9f}" for value in result))
    return "\n".join(lines) + "\n"
