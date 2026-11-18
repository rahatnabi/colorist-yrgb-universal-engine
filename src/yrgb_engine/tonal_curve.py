"""Reference-based tonal percentile curve measurement for still images."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log2

from .exposure import _luminance_samples, _percentile
from .precision import PrecisionFrame
from .scoring import ScoringCriterion

TONAL_PERCENTILES = (1, 10, 25, 50, 75, 90, 99)

@dataclass(frozen=True, slots=True)
class ReferenceTonalCurve:
    """Exercise-authored linear-luminance values at fixed percentile anchors."""
    luminance_values: tuple[float, ...]
    tolerance_stops: float = 0.15
    weight: float = 1.0
    falloff: float = 2.0
    luminance_floor: float = 1e-6

    def validate(self) -> None:
        if len(self.luminance_values) != len(TONAL_PERCENTILES):
            raise ValueError("Reference curve requires seven values for percentiles 1, 10, 25, 50, 75, 90 and 99.")
        if any(not isfinite(v) or v <= 0 for v in self.luminance_values):
            raise ValueError("Reference curve luminance values must be finite and positive.")
        if any(a > b for a, b in zip(self.luminance_values, self.luminance_values[1:])):
            raise ValueError("Reference curve luminance values must be non-decreasing.")
        if not isfinite(self.tolerance_stops) or self.tolerance_stops < 0:
            raise ValueError("Curve tolerance must be finite and non-negative.")
        if not isfinite(self.weight) or self.weight <= 0:
            raise ValueError("Curve weight must be finite and positive.")
        if not isfinite(self.falloff) or self.falloff <= 0:
            raise ValueError("Curve falloff must be finite and positive.")
        if not isfinite(self.luminance_floor) or self.luminance_floor <= 0:
            raise ValueError("Luminance floor must be finite and positive.")

@dataclass(frozen=True, slots=True)
class TonalCurveMeasurement:
    percentiles: tuple[int, ...]
    candidate_luminance: tuple[float, ...]
    reference_luminance: tuple[float, ...]
    deviation_stops: tuple[float, ...]
    sample_count: int

def measure_reference_tonal_curve(
    frame: PrecisionFrame,
    reference: ReferenceTonalCurve,
    *,
    luminance_coefficients: tuple[float, float, float] = (0.2126, 0.7152, 0.0722),
) -> TonalCurveMeasurement:
    """Compare full-frame luminance quantiles in validated linear-light RGB."""
    reference.validate()
    if not frame.encoding.validated:
        raise ValueError("Tonal curve comparison requires a validated color pipeline.")
    if frame.encoding.transfer.casefold() not in {"linear", "linear-light", "scene-linear"}:
        raise ValueError("Tonal curve comparison requires linear-light RGB.")
    if not frame.encoding.working_space_id or not frame.encoding.transform_id:
        raise ValueError("Tonal curve comparison requires working_space_id and transform_id.")
    _, ys = _luminance_samples(
        frame, __import__("yrgb_engine.exposure", fromlist=["PixelRegion"]).PixelRegion(0, 0, frame.width, frame.height),
        luminance_coefficients,
    )
    candidate = tuple(_percentile(ys, p) for p in TONAL_PERCENTILES)
    floor = reference.luminance_floor
    deviations = tuple(
        log2(max(value, floor) / max(target, floor))
        for value, target in zip(candidate, reference.luminance_values, strict=True)
    )
    return TonalCurveMeasurement(
        TONAL_PERCENTILES, candidate, reference.luminance_values, deviations, len(ys)
    )

def tonal_curve_criteria(
    measurement: TonalCurveMeasurement, reference: ReferenceTonalCurve,
) -> tuple[ScoringCriterion, ...]:
    """Create independent percentile criteria; aggregation remains in Correction Accuracy."""
    reference.validate()
    return tuple(
        ScoringCriterion(
            metric=f"tonal_curve_p{percentile}_deviation",
            measured=abs(deviation), target=0.0,
            tolerance=reference.tolerance_stops,
            weight=reference.weight / len(TONAL_PERCENTILES),
            falloff=reference.falloff, unit="stops",
            note=f"Absolute linear-luminance percentile deviation at P{percentile}.",
        )
        for percentile, deviation in zip(TONAL_PERCENTILES, measurement.deviation_stops, strict=True)
    )
