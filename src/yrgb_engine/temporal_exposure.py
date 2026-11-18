"""Streaming temporal exposure consistency in a validated linear working space.

Camera-specific transforms may differ, but every compared frame must declare the
same validated destination working-space identity. User-confirmed ROIs are supplied
by the caller; shot boundaries are explicit frame indices, never inferred here.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import isfinite

from .exposure import (
    ExposureAnalysisError,
    ExposureRegionMeasurement,
    PixelRegion,
    measure_exposure_region,
)
from .precision import PrecisionFrame


class TemporalExposureError(ValueError):
    """Raised for invalid temporal exposure inputs or comparisons."""


@dataclass(frozen=True, slots=True)
class TemporalExposureReport:
    timestamp_seconds: float
    frame_index: int
    shot_index: int
    measurement: ExposureRegionMeasurement
    delta_from_previous_stops: float | None
    drift_from_shot_reference_stops: float | None
    channel_balance_delta_from_previous: tuple[float, float, float] | None
    shot_reference_reset: bool


def iter_temporal_exposure(
    frames: Iterable[tuple[float, PrecisionFrame]],
    *,
    region: PixelRegion,
    luminance_coefficients: tuple[float, float, float],
    shot_boundary_indices: Iterable[int] = (),
    gray_reference: float = 0.18,
) -> Iterator[TemporalExposureReport]:
    """Yield bounded-memory exposure consistency reports for a video sequence.

    shot_boundary_indices contains zero-based frame indices confirmed by the
    caller. A boundary resets the shot reference and prevents cross-shot deltas.
    One user-confirmed ROI is used throughout; callers should segment analysis or
    choose a suitable ROI when subject placement changes.
    """
    boundaries = frozenset(shot_boundary_indices)
    if any(not isinstance(index, int) or index < 0 for index in boundaries):
        raise TemporalExposureError("Shot boundary indices must be non-negative integers.")
    if not isfinite(gray_reference) or gray_reference <= 0:
        raise TemporalExposureError("gray_reference must be finite and positive.")

    previous_timestamp: float | None = None
    previous_measurement: ExposureRegionMeasurement | None = None
    shot_reference: ExposureRegionMeasurement | None = None
    working_space_id: str | None = None
    shot_index = -1

    for frame_index, (timestamp, frame) in enumerate(frames):
        if not isfinite(timestamp) or timestamp < 0:
            raise TemporalExposureError("Frame timestamps must be finite and non-negative.")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise TemporalExposureError("Frame timestamps must be strictly increasing.")
        encoding = frame.encoding
        if not encoding.validated or not encoding.working_space_id:
            raise TemporalExposureError(
                "Every frame must declare a validated working_space_id."
            )
        if working_space_id is None:
            working_space_id = encoding.working_space_id
        elif encoding.working_space_id != working_space_id:
            raise TemporalExposureError(
                "Frames must share the same validated destination working space."
            )

        reset = frame_index == 0 or frame_index in boundaries
        if reset:
            shot_index += 1
            previous_measurement = None
            shot_reference = None

        try:
            measurement = measure_exposure_region(
                frame, region,
                luminance_coefficients=luminance_coefficients,
                gray_reference=gray_reference,
            )
        except ExposureAnalysisError as exc:
            raise TemporalExposureError(str(exc)) from exc

        delta_previous = None
        balance_delta = None
        if previous_measurement is not None:
            if (previous_measurement.exposure_stops_from_gray is not None
                    and measurement.exposure_stops_from_gray is not None):
                delta_previous = (
                    measurement.exposure_stops_from_gray
                    - previous_measurement.exposure_stops_from_gray
                )
            if (previous_measurement.channel_balance is not None
                    and measurement.channel_balance is not None):
                balance_delta = tuple(
                    measurement.channel_balance[channel]
                    - previous_measurement.channel_balance[channel]
                    for channel in range(3)
                )

        if shot_reference is None:
            shot_reference = measurement
        drift = None
        if (shot_reference.exposure_stops_from_gray is not None
                and measurement.exposure_stops_from_gray is not None):
            drift = (
                measurement.exposure_stops_from_gray
                - shot_reference.exposure_stops_from_gray
            )

        yield TemporalExposureReport(
            timestamp_seconds=timestamp,
            frame_index=frame_index,
            shot_index=shot_index,
            measurement=measurement,
            delta_from_previous_stops=delta_previous,
            drift_from_shot_reference_stops=drift,
            channel_balance_delta_from_previous=balance_delta,
            shot_reference_reset=reset,
        )
        previous_timestamp = timestamp
        previous_measurement = measurement
