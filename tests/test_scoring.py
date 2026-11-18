import pytest

from yrgb_engine.scoring import (
    ScoringCriterion,
    ScoringError,
    build_score_report,
    score_criterion,
)


def test_criterion_within_tolerance_scores_full_marks():
    result = score_criterion(
        ScoringCriterion("exposure_stops", 0.08, 0.0, 0.1, unit="stops")
    )
    assert result.status == "scored"
    assert result.score == 100.0
    assert result.error == pytest.approx(0.08)


def test_criterion_falloff_is_exercise_configured():
    result = score_criterion(
        ScoringCriterion("white_balance_delta", 4.0, 0.0, 2.0, falloff=2.0)
    )
    assert result.score == 50.0


def test_zero_tolerance_requires_exact_match():
    assert score_criterion(
        ScoringCriterion("neutral_error", 0.0, 0.0, 0.0)
    ).score == 100.0
    assert score_criterion(
        ScoringCriterion("neutral_error", 0.01, 0.0, 0.0)
    ).score == 0.0


def test_required_missing_measurement_blocks_total_score():
    report = build_score_report(
        "correction_accuracy",
        [ScoringCriterion("exposure", None, 0.0, 0.1)],
        pipeline_verified=True,
    )
    assert report.status == "not_scored"
    assert report.score is None
    assert "exposure" in report.reason


def test_unverified_pipeline_never_produces_a_score():
    report = build_score_report(
        "creative_look_similarity",
        [ScoringCriterion("delta_e00", 1.0, 0.0, 2.0)],
        pipeline_verified=False,
    )
    assert report.status == "not_scored"
    assert report.score is None


def test_optional_missing_measurement_is_excluded_and_reported():
    report = build_score_report(
        "correction_accuracy",
        [
            ScoringCriterion("exposure", 0.0, 0.0, 0.1, weight=2.0),
            ScoringCriterion("optional_roi", None, 0.0, 1.0, required=False),
        ],
        pipeline_verified=True,
    )
    assert report.status == "scored"
    assert report.score == 100.0
    assert report.components[1].status == "not_scored"


def test_criteria_are_weighted():
    report = build_score_report(
        "creative_look_similarity",
        [
            ScoringCriterion("color", 0.0, 0.0, 1.0, weight=3.0),
            ScoringCriterion("tone", 2.0, 0.0, 1.0, falloff=1.0, weight=1.0),
        ],
        pipeline_verified=True,
    )
    assert report.score == 75.0


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_tolerance_is_rejected(value):
    with pytest.raises(ScoringError):
        score_criterion(ScoringCriterion("metric", 0.0, 0.0, value))


def test_report_serializes_to_plain_dictionary():
    report = build_score_report(
        "correction_accuracy",
        [ScoringCriterion("exposure", 0.0, 0.0, 0.1)],
        pipeline_verified=True,
    )
    payload = report.to_dict()
    assert payload["label"] == "correction_accuracy"
    assert payload["score"] == 100.0
