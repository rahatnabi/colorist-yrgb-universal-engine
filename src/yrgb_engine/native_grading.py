"""Native float32 still-image grading operations for validated linear frames.

This module is deliberately independent of browser canvas and display encoding.
It preserves scene values (including negative and >1 values) and never clamps
pixels. Clamping belongs only at an explicitly selected display/export boundary.
"""
from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass
from math import isfinite

from .precision import PrecisionFrame


class NativeGradingError(ValueError):
    """Raised when a frame or grading setting is outside the supported contract."""


@dataclass(frozen=True, slots=True)
class NativeGradeSettings:
    exposure_stops: float = 0.0
    contrast: float = 1.0
    pivot: float = 0.18
    saturation: float = 1.0
    temperature_shift: float = 0.0
    tint_shift: float = 0.0
    curve_midpoint: float = 0.5


def _validate_settings(settings: NativeGradeSettings) -> None:
    bounds = {
        "exposure_stops": (-10.0, 10.0),
        "contrast": (0.0, 3.0),
        "pivot": (0.001, 4.0),
        "saturation": (0.0, 3.0),
        "temperature_shift": (-1.0, 1.0),
        "tint_shift": (-1.0, 1.0),
        "curve_midpoint": (0.1, 0.9),
    }
    for name, (minimum, maximum) in bounds.items():
        value = getattr(settings, name)
        if not isfinite(value) or not minimum <= value <= maximum:
            raise NativeGradingError(
                f"{name} must be finite and between {minimum} and {maximum}."
            )


def _master_curve(value: float, midpoint: float) -> float:
    if value <= 0.5:
        return value * (midpoint / 0.5)
    return midpoint + ((value - 0.5) / 0.5) * (1.0 - midpoint)


def apply_native_grade(
    frame: PrecisionFrame,
    settings: NativeGradeSettings,
    *,
    working_space_id: str,
) -> PrecisionFrame:
    """Apply the interactive look math to a validated linear RGB still image.

    Supported working spaces are linear Rec.709 and ACEScg. RGB values remain
    float32 and unclamped; alpha and auxiliary channels are copied unchanged.
    """
    if not working_space_id or frame.encoding.working_space_id != working_space_id:
        raise NativeGradingError("Frame working-space identity does not match the selected grading space.")
    if not frame.encoding.validated:
        raise NativeGradingError("Native grading requires a reference-validated input transform.")
    if frame.encoding.transfer.casefold() != "linear":
        raise NativeGradingError("Native grading requires linear-light RGB samples.")
    if working_space_id not in {"scene-linear-rec709", "acescg-linear"}:
        raise NativeGradingError(f"Unsupported native grading working space: {working_space_id}")

    _validate_settings(settings)
    channel_indices = {name.upper(): index for index, name in enumerate(frame.channel_names)}
    if not all(channel in channel_indices for channel in ("R", "G", "B")):
        raise NativeGradingError("Native grading requires named R, G and B channels.")

    r_index, g_index, b_index = (channel_indices[name] for name in ("R", "G", "B"))
    exposure = 2.0 ** settings.exposure_stops
    gains = (
        exposure * 2.0 ** (0.35 * settings.temperature_shift),
        exposure * 2.0 ** (0.25 * settings.tint_shift),
        exposure * 2.0 ** (-0.35 * settings.temperature_shift),
    )
    if working_space_id == "acescg-linear":
        luma = (0.2722287, 0.6740818, 0.0536895)
    else:
        luma = (0.2126, 0.7152, 0.0722)

    output = frame.samples[:]
    channels = frame.channel_count
    for offset in range(0, len(output), channels):
        rgb = [
            output[offset + r_index],
            output[offset + g_index],
            output[offset + b_index],
        ]
        rgb = [
            settings.pivot + (rgb[index] * gains[index] - settings.pivot) * settings.contrast
            for index in range(3)
        ]
        luminance = sum(rgb[index] * luma[index] for index in range(3))
        rgb = [
            _master_curve(
                luminance + (rgb[index] - luminance) * settings.saturation,
                settings.curve_midpoint,
            )
            for index in range(3)
        ]
        output[offset + r_index] = rgb[0]
        output[offset + g_index] = rgb[1]
        output[offset + b_index] = rgb[2]

    metadata = dict(frame.metadata)
    metadata["yrgb_native_grade"] = "float32_linear_v1"
    metadata["yrgb_grade_working_space"] = working_space_id
    return PrecisionFrame(
        width=frame.width,
        height=frame.height,
        channel_names=frame.channel_names,
        samples=output,
        source_path=frame.source_path,
        decoder=f"{frame.decoder}+YRGBNativeGrade",
        encoding=replace(frame.encoding),
        sample_domain="validated_linear_native_grade_float32",
        purpose="graded_still_candidate",
        metadata=metadata,
    )
