"""Reference CPU application for parsed .cube LUTs (1D, 3D, and combined)."""
from __future__ import annotations

from math import isfinite

from .cube import CubeLUT


class LUTApplicationError(ValueError):
    """Raised when LUT application inputs are invalid."""


def _domain_coordinate(value: float, low: float, high: float) -> float:
    return min(1.0, max(0.0, (value - low) / (high - low)))


def _sample_1d(
    values: tuple[tuple[float, float, float], ...],
    rgb: tuple[float, float, float],
    domain_min: tuple[float, float, float],
    domain_max: tuple[float, float, float],
) -> tuple[float, float, float]:
    size = len(values)
    result = []
    for channel, value in enumerate(rgb):
        position = _domain_coordinate(value, domain_min[channel], domain_max[channel]) * (size - 1)
        lower = int(position)
        upper = min(lower + 1, size - 1)
        fraction = position - lower
        result.append(
            values[lower][channel] * (1.0 - fraction)
            + values[upper][channel] * fraction
        )
    return tuple(result)


def _sample_3d(
    values: tuple[tuple[float, float, float], ...],
    size: int,
    rgb: tuple[float, float, float],
    domain_min: tuple[float, float, float],
    domain_max: tuple[float, float, float],
) -> tuple[float, float, float]:
    coords = [
        _domain_coordinate(rgb[i], domain_min[i], domain_max[i]) * (size - 1)
        for i in range(3)
    ]
    lows = [int(value) for value in coords]
    highs = [min(value + 1, size - 1) for value in lows]
    fractions = [coords[i] - lows[i] for i in range(3)]

    def entry(r: int, g: int, b: int) -> tuple[float, float, float]:
        # .cube ordering: blue varies fastest, then green, then red.
        return values[(r * size + g) * size + b]

    result = []
    for channel in range(3):
        red_slices = []
        for r, wr in ((lows[0], 1.0 - fractions[0]), (highs[0], fractions[0])):
            green_slices = []
            for g, wg in ((lows[1], 1.0 - fractions[1]), (highs[1], fractions[1])):
                blue_value = (
                    entry(r, g, lows[2])[channel] * (1.0 - fractions[2])
                    + entry(r, g, highs[2])[channel] * fractions[2]
                )
                green_slices.append((blue_value, wg))
            red_slices.append((
                green_slices[0][0] * green_slices[0][1]
                + green_slices[1][0] * green_slices[1][1],
                wr,
            ))
        result.append(
            red_slices[0][0] * red_slices[0][1]
            + red_slices[1][0] * red_slices[1][1]
        )
    return tuple(result)


def apply_cube_rgb(
    rgb: tuple[float, float, float],
    lut: CubeLUT,
    *,
    intensity: float = 1.0,
) -> tuple[float, float, float]:
    """Apply a parsed LUT using linear 1D interpolation and trilinear 3D interpolation.

    For combined LUTs, the 1D stage runs before the 3D stage. Intensity blends
    the original input with the final LUT result. LUT coordinates are clamped
    to the declared domain; output values themselves are not clamped.
    """
    if len(rgb) != 3 or not all(isfinite(value) for value in rgb):
        raise LUTApplicationError("RGB input must contain three finite values.")
    if not isfinite(intensity) or not 0.0 <= intensity <= 1.0:
        raise LUTApplicationError("Intensity must be between 0 and 1.")

    original = tuple(float(value) for value in rgb)
    result = original
    if lut.values_1d:
        result = _sample_1d(lut.values_1d, result, lut.domain_min, lut.domain_max)
    if lut.values_3d:
        result = _sample_3d(
            lut.values_3d, lut.size_3d or 0, result, lut.domain_min, lut.domain_max
        )
    return tuple(
        original[i] * (1.0 - intensity) + result[i] * intensity
        for i in range(3)
    )
