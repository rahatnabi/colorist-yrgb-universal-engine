"""Compact, explainable report for still-image correction accuracy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .accuracy import AccuracyTarget, CorrectionAccuracyResult
from .tonal_curve import TONAL_PERCENTILES


ReportStatus = Literal["scored", "not_scored"]


@dataclass(frozen=True, slots=True)
class ReportMetric:
    name: str
    status: ReportStatus
    measured: float | None
    target: float | None
    deviation: float | None
    unit: str
    score: float | None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReportSection:
    status: ReportStatus
    score: float | None
    metrics: tuple[ReportMetric, ...]
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectionAccuracyReport:
    """Three transparent measurement groups plus the independent overall score."""

    label: Literal["correction_accuracy"]
    status: ReportStatus
    score: float | None
    working_space_id: str
    transform_id: str
    sample_count: int
    exposure: ReportSection
    white_balance: ReportSection
    reference_tonal_curve: ReportSection
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable compact report."""
        return asdict(self)


def _section_score(metrics: tuple[ReportMetric, ...]) -> float | None:
    scored = [metric.score for metric in metrics if metric.status == "scored" and metric.score is not None]
    if len(scored) != len(metrics) or not scored:
        return None
    return round(sum(scored) / len(scored), 2)


def build_correction_accuracy_report(
    result: CorrectionAccuracyResult,
    target: AccuracyTarget,
) -> CorrectionAccuracyReport:
    """Present raw measurements, targets, deviations and component scores together.

    The overall score is the engine's existing weighted Correction Accuracy
    result. Section scores are simple, transparent means of their own component
    scores and are diagnostic only; they are not re-weighted into the headline.
    """
    measurement = result.measurement
    criteria = {item.metric: item for item in result.score.components}

    exposure_criterion = criteria.get("exposure_stops_from_target")
    exposure_value = measurement.measured_exposure_stops
    exposure_metric = ReportMetric(
        name="Exposure",
        status="scored" if exposure_criterion and exposure_criterion.score is not None else "not_scored",
        measured=exposure_value,
        target=target.exposure_stops,
        deviation=(abs(exposure_value - target.exposure_stops) if exposure_value is not None else None),
        unit="stops",
        score=exposure_criterion.score if exposure_criterion else None,
        note="Measured from the explicitly selected neutral ROI against the exercise gray reference.",
    )
    exposure = ReportSection(
        exposure_metric.status, exposure_metric.score, (exposure_metric,),
        None if exposure_metric.status == "scored" else "Exposure measurement unavailable.",
    )

    wb_metrics: list[ReportMetric] = []
    channel_values = measurement.measured_white_balance
    for index, channel in enumerate(("Red", "Green", "Blue")):
        criterion = criteria.get(f"white_balance_{channel.casefold()}_deviation")
        measured = channel_values[index] if channel_values is not None else None
        wb_metrics.append(ReportMetric(
            name=channel,
            status="scored" if criterion and criterion.score is not None else "not_scored",
            measured=measured,
            target=target.white_balance_target[index],
            deviation=(abs(measured - target.white_balance_target[index]) if measured is not None else None),
            unit="normalized channel ratio",
            score=criterion.score if criterion else None,
            note="Neutral-ROI channel balance; the ROI must genuinely be neutral.",
        ))
    wb_tuple = tuple(wb_metrics)
    wb_score = _section_score(wb_tuple)
    white_balance = ReportSection(
        "scored" if wb_score is not None else "not_scored", wb_score, wb_tuple,
        None if wb_score is not None else "One or more white-balance channels are unavailable.",
    )

    curve_metrics: list[ReportMetric] = []
    curve_measurement = measurement.reference_tonal_curve
    if curve_measurement is not None and target.reference_tonal_curve is not None:
        for index, percentile in enumerate(TONAL_PERCENTILES):
            criterion = criteria.get(f"tonal_curve_p{percentile}_deviation")
            curve_metrics.append(ReportMetric(
                name=f"P{percentile}",
                status="scored" if criterion and criterion.score is not None else "not_scored",
                measured=curve_measurement.candidate_luminance[index],
                target=curve_measurement.reference_luminance[index],
                deviation=abs(curve_measurement.deviation_stops[index]),
                unit="linear luminance / stops deviation",
                score=criterion.score if criterion else None,
                note="Full-frame percentile anchor; deviation is absolute stops.",
            ))
        curve_tuple = tuple(curve_metrics)
        curve_score = _section_score(curve_tuple)
        curve = ReportSection(
            "scored" if curve_score is not None else "not_scored", curve_score, curve_tuple,
            None if curve_score is not None else "Reference curve comparison is incomplete.",
        )
    else:
        curve = ReportSection(
            "not_scored", None, (),
            "No exercise reference tonal curve was supplied; no curve score is inferred.",
        )

    return CorrectionAccuracyReport(
        label="correction_accuracy",
        status=result.score.status,
        score=result.score.score,
        working_space_id=measurement.working_space_id,
        transform_id=measurement.transform_id or "",
        sample_count=measurement.sample_count,
        exposure=exposure,
        white_balance=white_balance,
        reference_tonal_curve=curve,
        limitations=result.score.limitations,
    )
