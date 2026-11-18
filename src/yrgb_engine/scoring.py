"""Deterministic, exercise-configured scoring for still-image grading practice.

This module scores supplied measurements; it does not decode images, infer color
spaces, or claim perceptual validity. Callers must validate the measurement
pipeline before constructing scored criteria.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal, Sequence


ScoreLabel = Literal["correction_accuracy", "creative_look_similarity"]


class ScoringError(ValueError):
    """Raised when an exercise scoring definition is invalid."""


@dataclass(frozen=True, slots=True)
class ScoringCriterion:
    """One measured exercise criterion.

    measured and target must use the same declared units/domain. The caller
    supplies the absolute error after applying any metric-specific comparison.
    """

    metric: str
    measured: float | None
    target: float
    tolerance: float
    weight: float = 1.0
    falloff: float = 1.0
    required: bool = True
    unit: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CriterionScore:
    metric: str
    status: Literal["scored", "not_scored"]
    measured: float | None
    target: float
    error: float | None
    tolerance: float
    weight: float
    score: float | None
    unit: str | None
    required: bool
    note: str | None


@dataclass(frozen=True, slots=True)
class ScoreReport:
    label: ScoreLabel
    status: Literal["scored", "not_scored"]
    score: float | None
    components: tuple[CriterionScore, ...]
    reason: str | None
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable report dictionary."""
        return asdict(self)


def _finite_non_negative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0:
        raise ScoringError(f"{name} must be finite and non-negative.")


def score_criterion(criterion: ScoringCriterion) -> CriterionScore:
    """Score one criterion using its exercise-defined tolerance and falloff."""
    if not criterion.metric.strip():
        raise ScoringError("Criterion metric name is required.")
    _finite_non_negative("target absolute value", abs(criterion.target))
    _finite_non_negative("tolerance", criterion.tolerance)
    _finite_non_negative("weight", criterion.weight)
    _finite_non_negative("falloff", criterion.falloff)
    if criterion.weight == 0:
        raise ScoringError("Criterion weight must be greater than zero.")
    if criterion.falloff == 0:
        raise ScoringError("Criterion falloff must be greater than zero.")
    if criterion.measured is None:
        return CriterionScore(
            criterion.metric, "not_scored", None, criterion.target, None,
            criterion.tolerance, criterion.weight, None, criterion.unit,
            criterion.required, criterion.note,
        )
    if not isfinite(criterion.measured):
        raise ScoringError("Measured value must be finite or None.")
    error = abs(criterion.measured - criterion.target)
    if error <= criterion.tolerance:
        value = 100.0
    elif criterion.tolerance == 0:
        value = 0.0
    else:
        value = max(
            0.0,
            100.0 * (
                1.0 - (error - criterion.tolerance)
                / (criterion.falloff * criterion.tolerance)
            ),
        )
    return CriterionScore(
        criterion.metric, "scored", criterion.measured, criterion.target,
        error, criterion.tolerance, criterion.weight, value, criterion.unit,
        criterion.required, criterion.note,
    )


def build_score_report(
    label: ScoreLabel,
    criteria: Sequence[ScoringCriterion],
    *,
    pipeline_verified: bool,
    limitations: Sequence[str] = (),
) -> ScoreReport:
    """Aggregate one score independently; never blends the two score types.

    If the color pipeline is unverified, or any required criterion is missing,
    the report is not_scored. Optional missing criteria are excluded from the
    weighted mean; the report retains them as not_scored components.
    """
    if label not in {"correction_accuracy", "creative_look_similarity"}:
        raise ScoringError("Unsupported score label.")
    if not criteria:
        return ScoreReport(
            label, "not_scored", None, (),
            "No scoring criteria were supplied.", tuple(limitations),
        )
    components = tuple(score_criterion(item) for item in criteria)
    if not pipeline_verified:
        return ScoreReport(
            label, "not_scored", None, components,
            "The required color-management and measurement pipeline is not verified.",
            tuple(limitations),
        )
    missing_required = [
        item.metric for item in components
        if item.required and item.status == "not_scored"
    ]
    if missing_required:
        return ScoreReport(
            label, "not_scored", None, components,
            "Required measurements are missing: " + ", ".join(missing_required),
            tuple(limitations),
        )
    valid = [item for item in components if item.status == "scored"]
    if not valid:
        return ScoreReport(
            label, "not_scored", None, components,
            "No measurable scoring criteria remain.", tuple(limitations),
        )
    total_weight = sum(item.weight for item in valid)
    score = sum(item.score * item.weight for item in valid if item.score is not None) / total_weight
    return ScoreReport(
        label, "scored", round(score, 2), components, None, tuple(limitations),
    )
