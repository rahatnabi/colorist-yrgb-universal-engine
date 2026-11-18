"""Reference-to-candidate color matching diagnostics.

All measurements operate on explicitly validated linear RGB frames in the same
declared working space. No camera transform is selected or applied here.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from .exposure import ExposureAnalysisError, PixelRegion, _luminance_samples, _require_validated_linear_rgb
from .precision import PrecisionFrame


class ColorMatchingError(ValueError):
    """Raised when color matching inputs are ambiguous or invalid."""


@dataclass(frozen=True, slots=True)
class ColorRegionStats:
    region: PixelRegion
    working_space_id: str
    transform_id: str | None
    mean_rgb: tuple[float, float, float]
    mean_xyz: tuple[float, float, float]
    mean_lab: tuple[float, float, float]
    rgb_chromaticity: tuple[float, float, float] | None
    channel_balance: tuple[float, float, float] | None
    neutral_spread: float | None
    mean_luminance: float


@dataclass(frozen=True, slots=True)
class ColorMatchReport:
    reference: ColorRegionStats
    candidate: ColorRegionStats
    delta_rgb: tuple[float, float, float]
    delta_lab: tuple[float, float, float]
    delta_e76: float
    exposure_delta_stops: float | None
    channel_balance_delta: tuple[float, float, float] | None


def _validate_matrix(matrix: tuple[tuple[float, float, float], ...]) -> None:
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ColorMatchingError("RGB-to-XYZ matrix must be 3x3.")
    if any(not isfinite(value) for row in matrix for value in row):
        raise ColorMatchingError("RGB-to-XYZ matrix values must be finite.")
    determinant = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if abs(determinant) < 1e-12:
        raise ColorMatchingError("RGB-to-XYZ matrix must be invertible.")


def _lab_f(value: float) -> float:
    delta = 6.0 / 29.0
    if value > delta ** 3:
        return value ** (1.0 / 3.0)
    return value / (3.0 * delta * delta) + 4.0 / 29.0


def _xyz_to_lab(
    xyz: tuple[float, float, float],
    white_point: tuple[float, float, float],
) -> tuple[float, float, float]:
    if any(not isfinite(v) or v <= 0 for v in white_point):
        raise ColorMatchingError("XYZ reference white must contain finite positive values.")
    fx, fy, fz = (_lab_f(xyz[i] / white_point[i]) for i in range(3))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def analyze_color_region(
    frame: PrecisionFrame,
    region: PixelRegion,
    *,
    rgb_to_xyz_matrix: tuple[tuple[float, float, float], ...],
    reference_white_xyz: tuple[float, float, float],
    luminance_coefficients: tuple[float, float, float],
) -> ColorRegionStats:
    """Measure mean linear RGB, XYZ, Lab and neutral balance in an explicit ROI.

    The matrix and reference white must describe the declared common working space.
    XYZ/Lab output is a diagnostic approximation based on mean RGB, not a pixelwise
    perceptual average. Negative RGB is rejected by the current Lab metric contract.
    """
    _require_validated_linear_rgb(frame)
    if not frame.encoding.working_space_id:
        raise ColorMatchingError("A validated working_space_id is required.")
    _validate_matrix(rgb_to_xyz_matrix)
    if len(reference_white_xyz) != 3:
        raise ColorMatchingError("Reference white must contain three XYZ values.")
    try:
        rgb_samples, ys = _luminance_samples(frame, region, luminance_coefficients)
    except ExposureAnalysisError as exc:
        raise ColorMatchingError(str(exc)) from exc
    mean_rgb = tuple(
        sum(pixel[channel] for pixel in rgb_samples) / len(rgb_samples)
        for channel in range(3)
    )
    if min(mean_rgb) < 0:
        raise ColorMatchingError("Lab diagnostics require non-negative mean RGB.")
    xyz = tuple(
        sum(rgb_to_xyz_matrix[row][column] * mean_rgb[column] for column in range(3))
        for row in range(3)
    )
    if min(xyz) < 0:
        raise ColorMatchingError("RGB-to-XYZ matrix produced negative XYZ values.")
    lab = _xyz_to_lab(xyz, reference_white_xyz)
    total = sum(mean_rgb)
    chromaticity = tuple(value / total for value in mean_rgb) if total > 0 else None
    mean_channel = total / 3.0
    balance = (
        tuple(value / mean_channel - 1.0 for value in mean_rgb)
        if mean_channel > 0 else None
    )
    spread = max(balance) - min(balance) if balance is not None else None
    return ColorRegionStats(
        region, frame.encoding.working_space_id, frame.encoding.transform_id,
        mean_rgb, xyz, lab, chromaticity, balance, spread,
        sum(ys) / len(ys),
    )


def compare_color_regions(
    reference: ColorRegionStats,
    candidate: ColorRegionStats,
    *,
    delta_e_threshold: float | None = None,
) -> ColorMatchReport:
    """Compare two measured regions; optional threshold is caller-defined only."""
    if reference.working_space_id != candidate.working_space_id:
        raise ColorMatchingError("Color regions must share the same working space.")
    if delta_e_threshold is not None and (
        not isfinite(delta_e_threshold) or delta_e_threshold < 0
    ):
        raise ColorMatchingError("delta_e_threshold must be finite and non-negative.")
    delta_rgb = tuple(candidate.mean_rgb[i] - reference.mean_rgb[i] for i in range(3))
    delta_lab = tuple(candidate.mean_lab[i] - reference.mean_lab[i] for i in range(3))
    delta_e76 = sqrt(sum(value * value for value in delta_lab))
    exposure_delta = None
    if reference.mean_luminance > 0 and candidate.mean_luminance > 0:
        from math import log2
        exposure_delta = log2(candidate.mean_luminance / reference.mean_luminance)
    balance_delta = None
    if reference.channel_balance is not None and candidate.channel_balance is not None:
        balance_delta = tuple(
            candidate.channel_balance[i] - reference.channel_balance[i]
            for i in range(3)
        )
    return ColorMatchReport(
        reference, candidate, delta_rgb, delta_lab, delta_e76,
        exposure_delta, balance_delta,
    )
