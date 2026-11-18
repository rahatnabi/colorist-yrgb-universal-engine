from fastapi.testclient import TestClient

from yrgb_engine.api import create_app
from yrgb_engine.registry import ProfileRegistry


def test_practice_chart_download_is_explicitly_synthetic():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.get("/v1/learning/assets/neutral-practice-chart.png")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers["x-yrgb-asset-status"] == "synthetic-instructional-sample"


def test_lesson_completion_and_progress_are_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("YRGB_LEARNING_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    learner_id = "learner-test-0001"
    response = client.post(
        "/v1/learning/lessons/B01-pipeline/complete",
        data={"learner_id": learner_id},
    )
    assert response.status_code == 200
    progress = client.get("/v1/learning/progress", params={"learner_id": learner_id})
    assert progress.status_code == 200
    assert progress.json()["completed_lesson_count"] == 1
    assert progress.json()["completed_lessons"][0]["lesson_id"] == "B01-pipeline"


def test_correction_accuracy_submission_is_saved_but_not_scored_without_validated_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("YRGB_LEARNING_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/learning/submissions",
        data={
            "learner_id": "learner-test-0002",
            "exercise_id": "EX-I02-01",
            "evidence": "I selected a neutral patch and reviewed the exposure measurement.",
            "profile_id": "sony.slog3.sgamut3cine",
            "roi_x": "10", "roi_y": "10", "roi_width": "20", "roi_height": "20",
        },
        files={"file": ("graded.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["submission"]["image_attached"] is True
    assert payload["assessment"]["status"] == "not_scored_reference_or_measurement_validation_missing"
    assert payload["assessment"]["correction_accuracy_score"] is None
    progress = client.get(
        "/v1/learning/progress",
        params={"learner_id": "learner-test-0002"},
    ).json()
    assert progress["submission_count"] == 1


def test_practical_submission_requires_a_still_image(tmp_path, monkeypatch):
    monkeypatch.setenv("YRGB_LEARNING_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/learning/submissions",
        data={
            "learner_id": "learner-test-0003",
            "exercise_id": "EX-I02-01",
            "evidence": "Here is my correction process and the reasoning behind it.",
        },
    )
    assert response.status_code == 422


def test_submission_rejects_non_image_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("YRGB_LEARNING_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/learning/submissions",
        data={
            "learner_id": "learner-test-0004",
            "exercise_id": "EX-I02-01",
            "evidence": "Here is my correction process and the reasoning behind it.",
        },
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_submission_requires_complete_roi_coordinates(tmp_path, monkeypatch):
    monkeypatch.setenv("YRGB_LEARNING_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/learning/submissions",
        data={
            "learner_id": "learner-test-0005",
            "exercise_id": "EX-I02-01",
            "evidence": "Here is my correction process and the reasoning behind it.",
            "roi_x": "0",
            "roi_y": "0",
        },
        files={"file": ("graded.png", b"fixture", "image/png")},
    )
    assert response.status_code == 422
