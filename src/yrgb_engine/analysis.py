"""Encoding-aware numerical analysis primitives for still frames and video frames.

This module reports sample-domain measurements. It never assumes that decoder
RGB is linear, Rec.709, or a display-referred signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .precision import PrecisionFrame


class FrameAnalysisError(ValueError):
    """Raised when frame analysis inputs are ambiguous or invalid."""


@dataclass(frozen=True, slots=True)
class ChannelStatistics:
    minimum: float
    maximum: float
    mean: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class Histogram:
    minimum: float
    maximum: float
    counts: tuple[int, ...]
    underflow: int
    overflow: int


@dataclass(frozen=True, slots=True)
class ScopeRaster:
    """Counts indexed as [horizontal_pixel_bin][vertical_value_bin]."""
    minimum: float
    maximum: float
    width: int
    height: int
    counts: tuple[tuple[int, ...], ...]
    underflow: int
    overflow: int


@dataclass(frozen=True, slots=True)
class LuminanceStatistics:
    coefficients: tuple[float, float, float]
    minimum: float
    maximum: float
    mean: float
    sample_count: int
    gray_reference: float
    gray_mean_error: float


@dataclass(frozen=True, slots=True)
class FrameAnalysis:
    channels: dict[str, ChannelStatistics]
    histograms: dict[str, Histogram]
    waveform: ScopeRaster | None
    rgb_parade: dict[str, ScopeRaster]
    luminance: LuminanceStatistics | None
    clipping: dict[str, int] | None
    vectorscope_points: tuple[tuple[float, float], ...] | None


def _rgb_indices(frame: PrecisionFrame) -> tuple[int, int, int]:
    names = [name.upper() for name in frame.channel_names]
    if not all(name in names for name in ("R", "G", "B")):
        raise FrameAnalysisError("Analysis requires named R, G and B channels.")
    return tuple(names.index(name) for name in ("R", "G", "B"))


def _channel_values(frame: PrecisionFrame, index: int) -> list[float]:
    return [frame.samples[offset + index]
            for offset in range(0, len(frame.samples), frame.channel_count)]


def _statistics(values: Sequence[float]) -> ChannelStatistics:
    return ChannelStatistics(min(values), max(values), sum(values) / len(values), len(values))


def _histogram(values: Sequence[float], bins: int, minimum: float,
               maximum: float) -> Histogram:
    counts = [0] * bins
    underflow = overflow = 0
    span = maximum - minimum
    for value in values:
        if value < minimum:
            underflow += 1
        elif value > maximum:
            overflow += 1
        else:
            index = min(bins - 1, int((value - minimum) / span * bins))
            counts[index] += 1
    return Histogram(minimum, maximum, tuple(counts), underflow, overflow)


def _scope(values: Sequence[float], width: int, height: int,
           minimum: float, maximum: float, source_width: int) -> ScopeRaster:
    counts = [[0] * height for _ in range(width)]
    underflow = overflow = 0
    span = maximum - minimum
    for pixel_index, value in enumerate(values):
        if value < minimum:
            underflow += 1
        elif value > maximum:
            overflow += 1
        else:
            source_x = pixel_index % source_width
            x = min(width - 1, int(source_x / source_width * width))
            y = min(height - 1, int((value - minimum) / span * height))
            counts[x][height - 1 - y] += 1
    return ScopeRaster(minimum, maximum, width, height,
                       tuple(tuple(column) for column in counts), underflow, overflow)


def analyze_frame(
    frame: PrecisionFrame,
    *,
    histogram_bins: int = 256,
    scope_width: int = 256,
    scope_height: int = 256,
    value_range: tuple[float, float] = (0.0, 1.0),
    luminance_coefficients: tuple[float, float, float] | None = None,
    linear_rgb: bool = False,
    gray_reference: float = 0.18,
    clipping_thresholds: tuple[float, float] | None = None,
    vectorscope_coefficients: tuple[float, float, float] | None = None,
    waveform_coefficients: tuple[float, float, float] | None = None,
    max_vectorscope_points: int = 100_000,
) -> FrameAnalysis:
    """Analyze one decoded image or video frame without implicit color transforms.

    Luminance is calculated only when the caller explicitly declares linear RGB
    and supplies RGB-to-Y coefficients. Vectorscope coordinates require explicit
    luma coefficients and are derived from the supplied RGB signal values.
    Scope ranges and clipping thresholds are caller-defined, not inferred.
    """
    if histogram_bins < 2 or scope_width < 1 or scope_height < 1:
        raise FrameAnalysisError("Histogram and scope dimensions must be positive.")
    if max_vectorscope_points < 1:
        raise FrameAnalysisError("max_vectorscope_points must be positive.")
    low, high = value_range
    if not low < high:
        raise FrameAnalysisError("value_range minimum must be below maximum.")
    if gray_reference <= 0:
        raise FrameAnalysisError("gray_reference must be positive.")

    ri, gi, bi = _rgb_indices(frame)
    values = {
        "R": _channel_values(frame, ri),
        "G": _channel_values(frame, gi),
        "B": _channel_values(frame, bi),
    }
    stats = {name: _statistics(channel) for name, channel in values.items()}
    histograms = {
        name: _histogram(channel, histogram_bins, low, high)
        for name, channel in values.items()
    }
    parade = {
        name: _scope(channel, scope_width, scope_height, low, high, frame.width)
        for name, channel in values.items()
    }

    waveform = None
    if waveform_coefficients is not None:
        kr_w, kg_w, kb_w = waveform_coefficients
        if min(kr_w, kg_w, kb_w) < 0 or abs(kr_w + kg_w + kb_w - 1.0) > 1e-6:
            raise FrameAnalysisError("Waveform coefficients must be non-negative and sum to 1.")
        waveform_values = [
            kr_w * values["R"][i] + kg_w * values["G"][i] + kb_w * values["B"][i]
            for i in range(frame.width * frame.height)
        ]
        waveform = _scope(
            waveform_values, scope_width, scope_height, low, high, frame.width
        )

    luminance = None
    if luminance_coefficients is not None:
        if not linear_rgb:
            raise FrameAnalysisError(
                "Luminance exposure measurement requires linear_rgb=True; "
                "Log or display-encoded RGB must be transformed explicitly first."
            )
        kr, kg, kb = luminance_coefficients
        if min(kr, kg, kb) < 0 or abs(kr + kg + kb - 1.0) > 1e-6:
            raise FrameAnalysisError("Luminance coefficients must be non-negative and sum to 1.")
        ys = [
            kr * values["R"][i] + kg * values["G"][i] + kb * values["B"][i]
            for i in range(frame.width * frame.height)
        ]
        ystats = _statistics(ys)
        ymean = ystats.mean
        luminance = LuminanceStatistics(
            (kr, kg, kb), ystats.minimum, ystats.maximum, ymean,
            ystats.sample_count, gray_reference, ymean - gray_reference,
        )

    clipping = None
    if clipping_thresholds is not None:
        clip_low, clip_high = clipping_thresholds
        if clip_low >= clip_high:
            raise FrameAnalysisError("Clipping low threshold must be below high threshold.")
        clipping = {
            "below_low": sum(v < clip_low for channel in values.values() for v in channel),
            "above_high": sum(v > clip_high for channel in values.values() for v in channel),
        }

    vectorscope = None
    if vectorscope_coefficients is not None:
        kr, kg, kb = vectorscope_coefficients
        if min(kr, kg, kb) < 0 or abs(kr + kg + kb - 1.0) > 1e-6:
            raise FrameAnalysisError("Vectorscope luma coefficients must be non-negative and sum to 1.")
        if kb >= 1.0 or kr >= 1.0:
            raise FrameAnalysisError("Vectorscope coefficients require non-zero Cb and Cr scales.")
        cb_scale, cr_scale = 2.0 * (1.0 - kb), 2.0 * (1.0 - kr)
        stride = max(1, (frame.width * frame.height + max_vectorscope_points - 1)
                     // max_vectorscope_points)
        points = []
        for i in range(0, frame.width * frame.height, stride):
            r, g, b = values["R"][i], values["G"][i], values["B"][i]
            y = kr * r + kg * g + kb * b
            points.append(((b - y) / cb_scale, (r - y) / cr_scale))
        vectorscope = tuple(points)

    return FrameAnalysis(stats, histograms, waveform, parade, luminance, clipping, vectorscope)
