from fastapi.testclient import TestClient

from yrgb_engine.api import create_app
from yrgb_engine.registry import ProfileRegistry


def test_capture_profile_match_endpoint_requires_gamut_confirmation_for_sony_slog3():
    client = TestClient(create_app(registry=ProfileRegistry.load()))
    response = client.post("/v1/profiles/match-capture", json={
        "camera_make": "Sony",
        "camera_model": "ILME-FX6",
        "color_transfer": "S-Log3",
        "color_primaries": "bt2020",
        "metadata_tags": {},
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_gamut_confirmation"
    assert payload["selection_made"] is False
    assert len(payload["candidates"]) == 2


def test_capture_profile_match_endpoint_matches_explicit_fx3_cine_candidate():
    client = TestClient(create_app(registry=ProfileRegistry.load()))
    response = client.post("/v1/profiles/match-capture", json={
        "camera_make": "Sony",
        "camera_model": "ILME-FX3",
        "color_transfer": "S-Log3",
        "camera_gamut": "S-Gamut3.Cine",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "candidate_unvalidated"
    assert [item["id"] for item in payload["candidates"]] == [
        "sony.slog3.sgamut3cine"
    ]
    assert payload["candidates"][0]["usable_for_transform"] is False


def test_capture_profile_match_endpoint_rejects_non_object_json():
    client = TestClient(create_app(registry=ProfileRegistry.load()))
    response = client.post("/v1/profiles/match-capture", json=["not", "an", "object"])
    assert response.status_code == 422
