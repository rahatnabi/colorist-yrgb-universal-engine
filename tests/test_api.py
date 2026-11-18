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


def test_analyze_returns_real_sample_domain_histogram_and_parade(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    def fake_decode(_path):
        return PrecisionFrame.from_interleaved(
            width=2,
            height=1,
            channel_names=("R", "G", "B"),
            values=[0.0, 0.5, 1.0, 0.25, 0.5, 0.75],
            source_path="fixture",
            decoder="test-decoder",
            sample_domain="test_encoded_values",
        )

    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/analyze",
        files={"file": ("sample.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decoder"] == "test-decoder"
    assert payload["sample_domain"] == "test_encoded_values"
    assert payload["analysis"]["channels"]["R"]["mean"] == 0.125
    assert sum(payload["analysis"]["histograms"]["R"]["counts"]) == 2
    assert payload["analysis"]["waveform"] is None
    assert payload["analysis"]["luminance"] is None
    assert payload["analysis"]["vectorscope_points"] is None

def test_video_frame_endpoint_returns_timestamped_sample_domain_analysis(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    seen = {}
    def fake_decode(_path, *, timestamp_seconds=0.0):
        seen["timestamp"] = timestamp_seconds
        return PrecisionFrame.from_interleaved(
            width=2, height=1, channel_names=("R", "G", "B"),
            values=[0.1, 0.2, 0.3, 0.7, 0.6, 0.5],
            source_path="fixture", decoder="test-ffmpeg",
            sample_domain="test_video_source_values",
        )

    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-frame?timestamp_seconds=2.5",
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert seen["timestamp"] == 2.5
    assert payload["timestamp_seconds"] == 2.5
    assert payload["decoder"] == "test-ffmpeg"
    assert payload["sample_domain"] == "test_video_source_values"
    assert sum(payload["analysis"]["histograms"]["R"]["counts"]) == 2
    assert payload["analysis"]["waveform"] is None
    assert payload["analysis"]["luminance"] is None


def test_video_frame_endpoint_rejects_negative_timestamp():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-frame?timestamp_seconds=-0.5",
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 422


def test_video_sample_endpoint_analyzes_bounded_frames_and_cut_candidates(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    timestamps = []
    values_by_time = {
        1.0: [0.0, 0.0, 0.0, 0.1, 0.1, 0.1],
        2.5: [0.0, 0.0, 0.0, 0.1, 0.1, 0.1],
        4.0: [0.9, 0.9, 0.9, 1.0, 1.0, 1.0],
    }

    def fake_decode(_path, *, timestamp_seconds=0.0):
        timestamps.append(timestamp_seconds)
        return PrecisionFrame.from_interleaved(
            width=2, height=1, channel_names=("R", "G", "B"),
            values=values_by_time[timestamp_seconds], source_path="fixture",
            decoder="test-ffmpeg", sample_domain="test_video_source_values",
        )

    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-sample?start_seconds=1&interval_seconds=1.5&frame_count=3&shot_change_threshold=0.5",
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert timestamps == [1.0, 2.5, 4.0]
    assert payload["frame_count"] == 3
    assert [item["timestamp_seconds"] for item in payload["frames"]] == timestamps
    assert payload["frames"][0]["histogram_distance"] is None
    assert payload["frames"][0]["shot_change_candidate"] is False
    assert payload["frames"][1]["histogram_distance"] == 0.0
    assert payload["frames"][2]["histogram_distance"] > 0.5
    assert payload["frames"][2]["shot_change_candidate"] is True
    assert payload["frames"][2]["mean_luminance_delta"] is None


def test_video_sample_endpoint_rejects_more_than_24_frames():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-sample?frame_count=25",
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 422


def test_lut_export_endpoint_resamples_cube_to_requested_size():
    source = (
        "TITLE \"Tiny identity\"\nLUT_3D_SIZE 2\n"
        "0 0 0\n0 0 1\n0 1 0\n0 1 1\n"
        "1 0 0\n1 0 1\n1 1 0\n1 1 1\n"
    )
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/lut/export?size=35&title=Test Look",
        files={"file": ("source.cube", source, "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert 'filename="Test_Look_35pt.cube"' in response.headers["content-disposition"]
    from yrgb_engine.cube import parse_cube_text
    parsed = parse_cube_text(response.text)
    assert parsed.size_3d == 35
    assert len(parsed.values_3d) == 35 ** 3


def test_lut_export_endpoint_rejects_non_cube_upload():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/lut/export?size=35",
        files={"file": ("look.png", b"not a lut", "image/png")},
    )
    assert response.status_code == 415


def test_lut_export_endpoint_rejects_unsupported_grid_size():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/lut/export?size=64",
        files={"file": ("look.cube", b"LUT_3D_SIZE 2", "text/plain")},
    )
    assert response.status_code == 422
