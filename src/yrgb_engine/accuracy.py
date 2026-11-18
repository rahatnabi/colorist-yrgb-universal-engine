"""Image-derived correction measurements connected to the deterministic score engine.

Only explicitly validated linear-RGB frames are accepted. The exercise must
supply the ROI, luminance coefficients, targets and tolerances; no gray card,
camera transform, or creative intent is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .exposure import PixelRegion, measure_exposure_region
from .precision import PrecisionFrame
from .scoring import ScoreReport, ScoringCriterion, build_score_report


@dataclass(frozen=True, slots=True)
class AccuracyTarget:
    """Exercise-authored targets in the declared linear working-space domain."""

    exposure_stops: float = 0.0
    exposure_tolerance_stops: float = 0.15
    neutral_spread: float = 0.03
    neutral_tolerance: float = 0.02
    gray_reference: float = 0.18
    luminance_coefficients: tuple[float, float, float] = (0.2126, 0.7152, 0.0722)
    exposure_weight: float = 2.0
    neutral_weight: float = 1.0
    falloff: float = 2.0


@dataclass(frozen=True, slots=True)
class AccuracyMeasurement:
    working_space_id: str
    transform_id: str | None
    region: PixelRegion
    measured_exposure_stops: float | None
    measured_neutral_spread: float | None
    sample_count: int


@dataclass(frozen=True, slots=True)
class CorrectionAccuracyResult:
    measurement: AccuracyMeasurement
    score: ScoreReport


def measure_correction_accuracy(
    frame: PrecisionFrame,
    region: PixelRegion,
    target: AccuracyTarget = AccuracyTarget(),
) -> CorrectionAccuracyResult:
    """Measure an explicitly selected neutral/exposure ROI and score it.

    A validated transform ID and working-space ID are mandatory. This is a
    technical correction exercise, not a general image-quality or aesthetic score.
    """
    if not frame.encoding.validated:
        raise ValueError("Correction accuracy requires a validated color pipeline.")
    if frame.encoding.transfer.casefold() not in {"linear", "linear-light", "scene-linear"}:
        raise ValueError("Correction accuracy requires validated linear-light RGB.")
    if not frame.encoding.working_space_id:
        raise ValueError("A declared working_space_id is required.")
    if not frame.encoding.transform_id:
        raise ValueError("A validated transform_id is required.")
    if len(target.luminance_coefficients) != 3:
        raise ValueError("Exactly three luminance coefficients are required.")
    if any(not isfinite(v) or v < 0 for v in target.luminance_coefficients):
        raise ValueError("Luminance coefficients must be finite and non-negative.")
    if abs(sum(target.luminance_coefficients) - 1.0) > 1e-6:
        raise ValueError("Luminance coefficients must sum to 1.")
    for name, value in (
        ("exposure target", target.exposure_stops),
        ("exposure tolerance", target.exposure_tolerance_stops),
        ("neutral target", target.neutral_spread),
        ("neutral tolerance", target.neutral_tolerance),
        ("gray reference", target.gray_reference),
        ("falloff", target.falloff),
        ("exposure weight", target.exposure_weight),
        ("neutral weight", target.neutral_weight),
    ):
        if not isfinite(value):
            raise ValueError(f"{name} must be finite.")
    if target.exposure_tolerance_stops < 0 or target.neutral_tolerance < 0:
        raise ValueError("Measurement tolerances must be non-negative.")
    if target.gray_reference <= 0 or target.falloff <= 0:
        raise ValueError("Gray reference and falloff must be positive.")
    if target.exposure_weight <= 0 or target.neutral_weight <= 0:
        raise ValueError("Criterion weights must be positive.")

    measured = measure_exposure_region(
        frame,
        region,
        luminance_coefficients=target.luminance_coefficients,
        gray_reference=target.gray_reference,
        neutral_tolerance=target.neutral_spread,
    )
    measurement = AccuracyMeasurement(
        working_space_id=frame.encoding.working_space_id,
        transform_id=frame.encoding.transform_id,
        region=region,
        measured_exposure_stops=measured.exposure_stops_from_gray,
        measured_neutral_spread=measured.neutral_spread,
        sample_count=measured.sample_count,
    )
    criteria = [
        ScoringCriterion(
            metric="exposure_stops_from_target",
            measured=(
                abs(measured.exposure_stops_from_gray - target.exposure_stops)
                if measured.exposure_stops_from_gray is not None else None
            ),
            target=0.0,
            tolerance=target.exposure_tolerance_stops,
            weight=target.exposure_weight,
            falloff=target.falloff,
            unit="stops",
            note="Absolute exposure deviation measured in validated linear light.",
        ),
        ScoringCriterion(
            metric="neutral_channel_spread",
            measured=measured.neutral_spread,
            target=target.neutral_spread,
            tolerance=target.neutral_tolerance,
            weight=target.neutral_weight,
            falloff=target.falloff,
            unit="normalized channel ratio",
            note="ROI neutrality diagnostic; the selected ROI must genuinely be neutral.",
        ),
    ]
    score = build_score_report(
        "correction_accuracy",
        criteria,
        pipeline_verified=True,
        limitations=(
            "Only the explicitly selected ROI is measured.",
            "The learner or exercise author must confirm that the ROI is a neutral reference.",
            "This score does not assess creative look similarity or overall image quality.",
        ),
    )
    return CorrectionAccuracyResult(measurement, score)
