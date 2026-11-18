from fastapi.testclient import TestClient
import pytest

from yrgb_engine.api import create_app
from yrgb_engine.registry import ProfileRegistry


def test_batch_analyze_compares_adjacent_still_images(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    values = {
        "first.tif": [0.1, 0.2, 0.3],
        "second.tif": [0.2, 0.3, 0.4],
    }

    def fake_decode(path):
        name = str(path)
        selected = values["first.tif"] if "yrgb-batch-" in name and len(calls) == 0 else values["second.tif"]
        calls.append(name)
        return PrecisionFrame.from_interleaved(
            width=1, height=1, channel_names=("R", "G", "B"),
            values=selected, source_path=name, decoder="test-oiio",
            sample_domain="test_encoded_values",
        )

    calls = []
    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/batch-analyze",
        files=[
            ("files", ("first.tif", b"first", "image/tiff")),
            ("files", ("second.tif", b"second", "image/tiff")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["image_count"] == 2
    assert [item["filename"] for item in payload["images"]] == ["first.tif", "second.tif"]
    assert payload["images"][0]["sample_domain"] == "test_encoded_values"
    assert payload["adjacent_comparisons"][0]["channel_mean_delta"] == pytest.approx({
        "R": 0.1, "G": 0.1, "B": 0.1,
    }, abs=2e-8)
    assert payload["adjacent_comparisons"][0]["measurement_domain"] == "decoded_sample_domain_not_linear_light"


def test_batch_analyze_rejects_empty_batch():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post("/v1/media/batch-analyze", files=[])
    assert response.status_code == 422
