from fastapi.testclient import TestClient

from yrgb_engine.api import create_app
from yrgb_engine.learning import EXERCISES, curriculum_payload, get_exercise, get_lesson, list_exercises
from yrgb_engine.registry import ProfileRegistry


def test_curriculum_is_still_image_only_and_has_three_levels():
    payload = curriculum_payload()
    assert payload["product_scope"] == "still_image_grading_only"
    assert [item["id"] for item in payload["levels"]] == ["beginner", "intermediate", "advanced"]
    assert len(payload["lessons"]) == 9
    assert all("video" not in lesson["title"].casefold() for lesson in payload["lessons"])


def test_exercise_ids_are_unique_and_assessment_modes_are_separate():
    ids = [item.id for item in EXERCISES]
    assert len(ids) == len(set(ids))
    modes = {item.assessment_mode for item in EXERCISES}
    assert "correction_accuracy" in modes
    assert "creative_look_similarity" in modes
    assert all(item.reference_asset_status != "measured_reference" for item in EXERCISES)


def test_learning_catalogue_lookup_and_level_filter():
    assert get_lesson("B01-pipeline")["level"] == "beginner"
    assert get_lesson("missing") is None
    assert get_exercise("EX-I02-01")["assessment_mode"] == "correction_accuracy"
    assert get_exercise("missing") is None
    assert all(item["level"] == "advanced" for item in list_exercises(level="advanced"))


def test_learning_api_routes():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    curriculum = client.get("/v1/learning/curriculum")
    assert curriculum.status_code == 200
    assert curriculum.json()["product_scope"] == "still_image_grading_only"

    exercises = client.get("/v1/learning/exercises", params={"level": "intermediate"})
    assert exercises.status_code == 200
    assert exercises.json()["count"] == 2

    lesson = client.get("/v1/learning/lessons/B03-exposure")
    assert lesson.status_code == 200
    assert lesson.json()["title"] == "Exposure and neutral balance"

    missing = client.get("/v1/learning/exercises/not-real")
    assert missing.status_code == 404


def test_learning_api_rejects_unknown_level():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    assert client.get("/v1/learning/exercises", params={"level": "expert"}).status_code == 422
