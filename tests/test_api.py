from fastapi.testclient import TestClient

from yrgb_engine.api import create_app
from yrgb_engine.registry import ProfileRegistry


def test_health_and_capabilities():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    assert "capabilities" in response.json()


def test_profile_candidates_do_not_select_transform():
    registry = ProfileRegistry([
        {
            "id": "sony-slog3-cine",
            "manufacturer": "Sony",
            "encoding": "S-Log3",
            "gamut": "S-Gamut3.Cine",
            "status": "unverified",
            "camera_models": [],
        },
        {
            "id": "sony-slog3",
            "manufacturer": "Sony",
            "encoding": "S-Log3",
            "gamut": "S-Gamut3",
            "status": "unverified",
            "camera_models": [],
        },
    ])
    client = TestClient(create_app(registry=registry))
    response = client.get("/v1/profiles/candidates", params={
        "manufacturer": "Sony", "encoding": "S-Log3"
    })
    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 2
    assert payload["selection_made"] is False
    assert all(not item["usable_for_transform"] for item in payload["candidates"])


def test_probe_rejects_empty_upload():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/probe",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400


def test_probe_accepts_unknown_file_as_unknown_not_supported():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/probe",
        files={"file": ("sample.bin", b"not a media file", "application/octet-stream")},
    )
    assert response.status_code == 200
    assert response.json()["probe"]["status"] == "unsupported_or_unknown"
