"""Image-derived correction measurements and exercise-based accuracy scoring."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .exposure import PixelRegion, analyze_tonal_distribution, measure_exposure_region
from .precision import PrecisionFrame
from .scoring import ScoreReport, ScoringCriterion, build_score_report
from .tonal_curve import (
    ReferenceTonalCurve,
    TonalCurveMeasurement,
    measure_reference_tonal_curve,
    tonal_curve_criteria,
)


@dataclass(frozen=True, slots=True)
class AccuracyTarget:
    """Exercise-authored targets in the declared linear working-space domain."""
    exposure_stops: float = 0.0
    exposure_tolerance_stops: float = 0.15
    neutral_spread: float = 0.03
    neutral_tolerance: float = 0.02
    gray_reference: float = 0.18
    luminance_coefficients: tuple[float, float, float] = (0.2126, 0.7152, 0.0722)
    white_balance_target: tuple[float, float, float] = (0.0, 0.0, 0.0)
    white_balance_tolerance: float = 0.02
    exposure_weight: float = 2.0
    white_balance_weight: float = 1.0
    falloff: float = 2.0
    shadow_threshold: float | None = None
    highlight_threshold: float | None = None
    shadow_fraction_target: float | None = None
    highlight_fraction_target: float | None = None
    tonal_fraction_tolerance: float = 0.05
    tonal_weight: float = 1.0
    reference_tonal_curve: ReferenceTonalCurve | None = None


@dataclass(frozen=True, slots=True)
class AccuracyMeasurement:
    working_space_id: str
    transform_id: str | None
    region: PixelRegion
    measured_exposure_stops: float | None
    measured_neutral_spread: float | None
    measured_white_balance: tuple[float, float, float] | None
    tonal_shadow_fraction: float | None
    tonal_highlight_fraction: float | None
    tonal_luminance_percentiles: tuple[float, float, float, float, float] | None
    sample_count: int
    reference_tonal_curve: TonalCurveMeasurement | None = None


@dataclass(frozen=True, slots=True)
class CorrectionAccuracyResult:
    measurement: AccuracyMeasurement
    score: ScoreReport


def _validate_target(target: AccuracyTarget) -> None:
    values = (
        ("exposure target", target.exposure_stops),
        ("exposure tolerance", target.exposure_tolerance_stops),
        ("neutral target", target.neutral_spread),
        ("neutral tolerance", target.neutral_tolerance),
        ("gray reference", target.gray_reference),
        ("white-balance tolerance", target.white_balance_tolerance),
        ("falloff", target.falloff),
        ("exposure weight", target.exposure_weight),
        ("white-balance weight", target.white_balance_weight),
        ("tonal fraction tolerance", target.tonal_fraction_tolerance),
        ("tonal weight", target.tonal_weight),
    )
    for name, value in values:
        if not isfinite(value):
            raise ValueError(f"{name} must be finite.")
    if len(target.luminance_coefficients) != 3 or len(target.white_balance_target) != 3:
        raise ValueError("Luminance coefficients and white-balance target require three values.")
    if any(not isfinite(v) or v < 0 for v in target.luminance_coefficients):
        raise ValueError("Luminance coefficients must be finite and non-negative.")
    if abs(sum(target.luminance_coefficients) - 1.0) > 1e-6:
        raise ValueError("Luminance coefficients must sum to 1.")
    if any(not isfinite(v) for v in target.white_balance_target):
        raise ValueError("White-balance targets must be finite.")
    if target.exposure_tolerance_stops < 0 or target.neutral_tolerance < 0:
        raise ValueError("Measurement tolerances must be non-negative.")
    if target.white_balance_tolerance < 0 or target.tonal_fraction_tolerance < 0:
        raise ValueError("White-balance and tonal tolerances must be non-negative.")
    if target.gray_reference <= 0 or target.falloff <= 0:
        raise ValueError("Gray reference and falloff must be positive.")
    if min(target.exposure_weight, target.white_balance_weight, target.tonal_weight) <= 0:
        raise ValueError("Criterion weights must be positive.")

    tonal_values = (
        target.shadow_threshold, target.highlight_threshold,
        target.shadow_fraction_target, target.highlight_fraction_target,
    )
    if any(value is not None for value in tonal_values):
        if any(value is None for value in tonal_values):
            raise ValueError("Tonal scoring requires both thresholds and both target fractions.")
        assert target.shadow_threshold is not None and target.highlight_threshold is not None
        assert target.shadow_fraction_target is not None and target.highlight_fraction_target is not None
        if target.shadow_threshold < 0 or target.highlight_threshold <= target.shadow_threshold:
            raise ValueError("Tonal thresholds must be non-negative and shadow must be below highlight.")
        if not (0 <= target.shadow_fraction_target <= 1 and 0 <= target.highlight_fraction_target <= 1):
            raise ValueError("Tonal fraction targets must be between 0 and 1.")
    if target.reference_tonal_curve is not None:
        target.reference_tonal_curve.validate()


def measure_correction_accuracy(
    frame: PrecisionFrame,
    region: PixelRegion,
    target: AccuracyTarget = AccuracyTarget(),
) -> CorrectionAccuracyResult:
    """Measure exposure/WB in a selected neutral ROI and optional full-frame tonal structure."""
    if not frame.encoding.validated:
        raise ValueError("Correction accuracy requires a validated color pipeline.")
    if frame.encoding.transfer.casefold() not in {"linear", "linear-light", "scene-linear"}:
        raise ValueError("Correction accuracy requires validated linear-light RGB.")
    if not frame.encoding.working_space_id:
        raise ValueError("A declared working_space_id is required.")
    if not frame.encoding.transform_id:
        raise ValueError("A validated transform_id is required.")
    _validate_target(target)

    measured = measure_exposure_region(
        frame, region,
        luminance_coefficients=target.luminance_coefficients,
        gray_reference=target.gray_reference,
        neutral_tolerance=target.neutral_spread,
    )
    tonal = None
    if target.shadow_threshold is not None and target.highlight_threshold is not None:
        tonal = analyze_tonal_distribution(
            frame,
            luminance_coefficients=target.luminance_coefficients,
            shadow_threshold=target.shadow_threshold,
            highlight_threshold=target.highlight_threshold,
        )
    curve = None
    if target.reference_tonal_curve is not None:
        curve = measure_reference_tonal_curve(
            frame, target.reference_tonal_curve,
            luminance_coefficients=target.luminance_coefficients,
        )

    measurement = AccuracyMeasurement(
        working_space_id=frame.encoding.working_space_id,
        transform_id=frame.encoding.transform_id,
        region=region,
        measured_exposure_stops=measured.exposure_stops_from_gray,
        measured_neutral_spread=measured.neutral_spread,
        measured_white_balance=measured.channel_balance,
        tonal_shadow_fraction=tonal.shadow_fraction if tonal else None,
        tonal_highlight_fraction=tonal.highlight_fraction if tonal else None,
        tonal_luminance_percentiles=tonal.luminance_percentiles if tonal else None,
        sample_count=measured.sample_count,
        reference_tonal_curve=curve,
    )

    criteria = [ScoringCriterion(
        metric="exposure_stops_from_target",
        measured=(abs(measured.exposure_stops_from_gray - target.exposure_stops)
                  if measured.exposure_stops_from_gray is not None else None),
        target=0.0, tolerance=target.exposure_tolerance_stops,
        weight=target.exposure_weight, falloff=target.falloff, unit="stops",
        note="Absolute exposure deviation measured in validated linear light.",
    )]
    balance = measured.channel_balance
    for index, channel in enumerate(("red", "green", "blue")):
        criteria.append(ScoringCriterion(
            metric=f"white_balance_{channel}_deviation",
            measured=abs(balance[index] - target.white_balance_target[index]) if balance else None,
            target=0.0, tolerance=target.white_balance_tolerance,
            weight=target.white_balance_weight / 3.0, falloff=target.falloff,
            unit="normalized channel ratio",
            note="Neutral-ROI channel balance; the selected ROI must genuinely be neutral.",
        ))

    if tonal is not None:
        assert target.shadow_fraction_target is not None and target.highlight_fraction_target is not None
        criteria.extend((
            ScoringCriterion(
                metric="shadow_fraction_deviation", measured=tonal.shadow_fraction,
                target=target.shadow_fraction_target, tolerance=target.tonal_fraction_tolerance,
                weight=target.tonal_weight / 2.0, falloff=target.falloff, unit="fraction",
                note="Full-frame shadow fraction at the exercise-defined linear-luminance threshold.",
            ),
            ScoringCriterion(
                metric="highlight_fraction_deviation", measured=tonal.highlight_fraction,
                target=target.highlight_fraction_target, tolerance=target.tonal_fraction_tolerance,
                weight=target.tonal_weight / 2.0, falloff=target.falloff, unit="fraction",
                note="Full-frame highlight fraction at the exercise-defined linear-luminance threshold.",
            ),
        ))
    if curve is not None:
        assert target.reference_tonal_curve is not None
        criteria.extend(tonal_curve_criteria(curve, target.reference_tonal_curve))

    score = build_score_report(
        "correction_accuracy", criteria, pipeline_verified=True,
        limitations=(
            "Exposure and white balance are measured only in the explicitly selected ROI.",
            "The learner or exercise author must confirm that the ROI genuinely represents a neutral reference.",
            "Tonal fractions and reference percentile curves use exercise-defined linear-luminance targets.",
            "The percentile curve compares full-frame luminance distribution; it is not a semantic or artistic contrast judgement.",
            "This score does not assess creative look similarity or overall image quality.",
        ),
    )
    return CorrectionAccuracyResult(measurement, score)
