"""UI-ready scope payloads for still-image and video-frame analysis.

This layer packages numerical analysis for a frontend. It does not render
pixels, infer IRE, or apply color transforms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

from .analysis import FrameAnalysis, analyze_frame
from .precision import PrecisionFrame


class ScopeEngineError(ValueError):
    """Raised when scope configuration or frame timing is invalid."""


@dataclass(frozen=True, slots=True)
class ScopeConfig:
    """Explicit scope configuration in the source frame's sample domain."""

    value_range: tuple[float, float] = (0.0, 1.0)
    histogram_bins: int = 256
    raster_width: int = 512
    raster_height: int = 256
    waveform_coefficients: tuple[float, float, float] | None = None
    vectorscope_coefficients: tuple[float, float, float] | None = None
    max_vectorscope_points: int = 100_000
    clipping_thresholds: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class ScopeSnapshot:
    """One frame's scope measurements and enough metadata to label them safely."""

    frame_width: int
    frame_height: int
    sample_domain: str
    primaries: str
    transfer: str
    matrix: str
    signal_range: str
    working_space_id: str | None
    transform_id: str | None
    value_range: tuple[float, float]
    value_axis_label: str
    scale_kind: str
    frame_index: int | None
    timestamp_seconds: float | None
    analysis: FrameAnalysis

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-compatible lists/dicts for a browser visualization."""
        def convert(value: Any) -> Any:
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, list):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value

        return convert(asdict(self))


def build_scope_snapshot(
    frame: PrecisionFrame,
    config: ScopeConfig = ScopeConfig(),
    *,
    frame_index: int | None = None,
    timestamp_seconds: float | None = None,
) -> ScopeSnapshot:
    """Build histogram, RGB parade and optional waveform/vectorscope payloads.

    The axis is always explicitly identified as source sample values. The
    frontend must not label it IRE or legal video levels unless a separate,
    validated signal-domain mapping is supplied.
    """
    if frame_index is not None and frame_index < 0:
        raise ScopeEngineError("frame_index must be non-negative.")
    if timestamp_seconds is not None and (
        not isfinite(timestamp_seconds) or timestamp_seconds < 0
    ):
        raise ScopeEngineError("timestamp_seconds must be finite and non-negative.")

    try:
        analysis = analyze_frame(
            frame,
            histogram_bins=config.histogram_bins,
            scope_width=config.raster_width,
            scope_height=config.raster_height,
            value_range=config.value_range,
            clipping_thresholds=config.clipping_thresholds,
            waveform_coefficients=config.waveform_coefficients,
            vectorscope_coefficients=config.vectorscope_coefficients,
            max_vectorscope_points=config.max_vectorscope_points,
        )
    except (ValueError, TypeError) as exc:
        raise ScopeEngineError(str(exc)) from exc

    encoding = frame.encoding
    return ScopeSnapshot(
        frame.width,
        frame.height,
        frame.sample_domain,
        encoding.primaries,
        encoding.transfer,
        encoding.matrix,
        encoding.range,
        encoding.working_space_id,
        encoding.transform_id,
        config.value_range,
        "Source sample value",
        "sample-domain",
        frame_index,
        timestamp_seconds,
        analysis,
    )
