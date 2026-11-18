from fastapi.testclient import TestClient

import pytest

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
    assert [frame["shot_index"] for frame in payload["frames"]] == [0, 0, 1]
    assert len(payload["shot_groups"]) == 2
    assert payload["shot_groups"][1]["start_frame_index"] == 2
    assert payload["shot_groups"][1]["boundary_candidate"] is True
    temporal = payload["temporal_diagnostics"]
    assert temporal["measurement_domain"] == "nonlinear_rgb_code_values"
    assert temporal["segments"][0]["interpretation"] == "insufficient_samples_for_trend"
    assert temporal["flicker_assessment"]["status"] == "unavailable"
    assert temporal["exposure_drift_assessment"]["status"] == "unavailable"
    assert payload["consistency_status"]["exposure_drift"].startswith("unavailable")


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


def test_linear_look_exr_endpoint_applies_controls_and_returns_float_exr(monkeypatch):
    from pathlib import Path
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6), source_path="fixture.exr", decoder="mock",
        encoding=ColorEncoding(transfer="unknown"),
    )

    def fake_decode(_path):
        return frame

    def fake_save(graded, output_path):
        assert graded.pixel(0, 0) == pytest.approx((0.4, 0.8, 1.2))
        Path(output_path).write_bytes(b"mock-openexr-float-data")
        return Path(output_path)

    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", fake_decode)
    monkeypatch.setattr("yrgb_engine.linear_export.save_linear_float_exr", fake_save)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/look-linear-exr",
        data={
            "input_space_id": "scene-linear-rec709",
            "linear_input_confirmed": "true",
            "settings_json": '{"exposure_stops": 1.0}',
        },
        files={"file": ("plate.exr", b"source-image", "image/x-exr")},
    )
    assert response.status_code == 200, response.text
    assert response.content == b"mock-openexr-float-data"
    assert response.headers["x-yrgb-transform-validated"] == "false"
    assert response.headers["x-yrgb-output-transfer"] == "scene-linear"


def test_linear_look_exr_endpoint_requires_linear_confirmation(monkeypatch):
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/look-linear-exr",
        data={"input_space_id": "scene-linear-rec709"},
        files={"file": ("plate.exr", b"source-image", "image/x-exr")},
    )
    assert response.status_code == 422
    assert "Confirm" in response.json()["detail"]


def test_transform_preview_blocks_unverified_camera_profile(monkeypatch):
    registry = ProfileRegistry([{
        "id": "sony.slog3.sgamut3cine",
        "manufacturer": "Sony",
        "encoding": "S-Log3",
        "gamut": "S-Gamut3.Cine",
        "status": "unverified",
        "transform_id": None,
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/transform-preview",
        data={"profile_id": "sony.slog3.sgamut3cine"},
        files={"file": ("frame.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 409
    assert "not reference-validated" in response.json()["detail"]


def test_transform_preview_rejects_unknown_camera_profile():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/transform-preview",
        data={"profile_id": "unknown.profile"},
        files={"file": ("frame.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 404


def test_transform_preview_runs_registry_gated_pipeline_for_approved_profile(tmp_path, monkeypatch):
    import hashlib
    from dataclasses import replace
    from pathlib import Path
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned.ocio"
    config.write_text("pinned-config-fixture")
    profile_id = "test.camera.profile"
    transform_id = "test.camera.to.dwg"
    source_space = "Test Camera Log"
    working_space = "DaVinci Wide Gamut"
    validation = {
        "passed": True,
        "profile_id": profile_id,
        "transform_id": transform_id,
        "source_space": source_space,
        "destination_space": working_space,
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "reference_set_id": "test-independent-reference",
        "vector_count": 12,
        "max_absolute_error": 0.00001,
        "tolerance": 0.0001,
        "ocio_version": "test",
    }
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Test",
        "encoding": "Test Log",
        "gamut": "Test Gamut",
        "status": "verified",
        "transform_id": transform_id,
        "ocio_source_space": source_space,
        "ocio_destination_space": working_space,
        "output_transfer": "DaVinci Intermediate",
        "output_primaries": working_space,
        "validation": validation,
    }])
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6), source_path="fixture", decoder="test",
        encoding=ColorEncoding(),
    )
    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", lambda _path: frame)
    monkeypatch.setattr(
        "yrgb_engine.transform_validation.transform_frame",
        lambda source, **_kwargs: source,
    )
    monkeypatch.setattr(
        "yrgb_engine.ocio.transform_frame",
        lambda source, **_kwargs: replace(
            source,
            encoding=replace(source.encoding, profile_id="Preview sRGB"),
        ),
    )
    monkeypatch.setattr(
        "yrgb_engine.preview.save_preview_png",
        lambda _frame, path, **_kwargs: Path(path).write_bytes(b"preview-png-fixture") or Path(path),
    )
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    monkeypatch.setenv("YRGB_PREVIEW_SPACE", "Preview sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_TRANSFER", "sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_PRIMARIES", "BT.709")

    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/transform-preview",
        data={"profile_id": profile_id},
        files={"file": ("frame.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200, response.text
    assert response.content == b"preview-png-fixture"
    assert response.headers["x-yrgb-camera-transform-validated"] == "true"
    assert response.headers["x-yrgb-display-transform-validated"] == "false"
    assert response.headers["x-yrgb-preview-only"] == "true"


def test_video_transform_preview_blocks_unverified_profile_before_decode():
    registry = ProfileRegistry([{
        "id": "apple.applelog",
        "manufacturer": "Apple",
        "encoding": "Apple Log",
        "gamut": "BT.2020",
        "status": "unverified",
        "transform_id": None,
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/video-transform-preview?timestamp_seconds=3.5",
        data={"profile_id": "apple.applelog"},
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 409
    assert "not reference-validated" in response.json()["detail"]


def test_ocio_status_reports_missing_server_config(monkeypatch):
    monkeypatch.delenv("YRGB_OCIO_CONFIG", raising=False)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.get("/v1/ocio/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["status"] == "not_configured"


def test_ocio_status_reports_missing_config_file(monkeypatch, tmp_path):
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(tmp_path / "missing.ocio"))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.get("/v1/ocio/status")
    assert response.status_code == 200
    assert response.json()["status"] == "config_file_missing"


def test_video_transform_preview_uses_requested_timestamp_for_approved_profile(tmp_path, monkeypatch):
    import hashlib
    from dataclasses import replace
    from pathlib import Path
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned.ocio"
    config.write_text("video-pinned-config")
    profile_id = "test.video.profile"
    source_space = "Test Video Log"
    working_space = "DaVinci Intermediate WideGamut"
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Test",
        "encoding": "Test Video Log",
        "gamut": "Test Gamut",
        "status": "verified",
        "transform_id": "test.video.to.dwg",
        "ocio_source_space": source_space,
        "ocio_destination_space": working_space,
        "output_transfer": "DaVinci Intermediate",
        "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True,
            "profile_id": profile_id,
            "transform_id": "test.video.to.dwg",
            "source_space": source_space,
            "destination_space": working_space,
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-video-reference",
            "vector_count": 10,
            "max_absolute_error": 0.00001,
            "tolerance": 0.0001,
            "ocio_version": "test",
        },
    }])
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.3, 0.4, 0.5), source_path="fixture", decoder="test-ffmpeg",
        encoding=ColorEncoding(),
    )
    seen = {}
    def fake_decode(_path, *, timestamp_seconds):
        seen["timestamp"] = timestamp_seconds
        return frame

    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_decode)
    monkeypatch.setattr("yrgb_engine.transform_validation.transform_frame", lambda source, **_kwargs: source)
    monkeypatch.setattr(
        "yrgb_engine.ocio.transform_frame",
        lambda source, **_kwargs: replace(
            source, encoding=replace(source.encoding, profile_id="Preview sRGB")
        ),
    )
    monkeypatch.setattr(
        "yrgb_engine.preview.save_preview_png",
        lambda _frame, path, **_kwargs: (Path(path).write_bytes(b"video-preview-fixture"), Path(path))[1],
    )
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    monkeypatch.setenv("YRGB_PREVIEW_SPACE", "Preview sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_TRANSFER", "sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_PRIMARIES", "BT.709")

    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/video-transform-preview?timestamp_seconds=4.25",
        data={"profile_id": profile_id},
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 200, response.text
    assert seen["timestamp"] == 4.25
    assert response.headers["x-yrgb-frame-timestamp"] == "4.25"
    assert response.headers["x-yrgb-preview-only"] == "true"


def test_transform_preview_requires_model_for_model_restricted_profile(tmp_path):
    import hashlib

    config = tmp_path / "pinned.ocio"
    config.write_text("model-check-config")
    profile_id = "test.model.restricted"
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Test",
        "encoding": "Test Log",
        "gamut": "Test Gamut",
        "camera_models": ["Test Camera X"],
        "status": "verified",
        "transform_id": "test.model.to.working",
        "ocio_source_space": "Test Camera Log",
        "ocio_destination_space": "DaVinci Intermediate WideGamut",
        "output_transfer": "DaVinci Intermediate",
        "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True,
            "profile_id": profile_id,
            "transform_id": "test.model.to.working",
            "source_space": "Test Camera Log",
            "destination_space": "DaVinci Intermediate WideGamut",
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-model-reference",
            "vector_count": 8,
            "max_absolute_error": 0.00001,
            "tolerance": 0.0001,
        },
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/transform-preview",
        data={"profile_id": profile_id},
        files={"file": ("frame.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 422
    assert "exact supported camera model" in response.json()["detail"]


def test_video_report_endpoint_composes_yuv_and_rgb_domains(monkeypatch):
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    class FakeYUVFrame:
        width = 2
        height = 1
        def to_report(self):
            return {
                "measurement_domain": "original_yuv_code_values",
                "timestamp_seconds": 1.5, "pixel_format": "yuv422p10le", "bit_depth": 10,
                "range_signaling": "tv", "matrix_signaling": "bt709",
                "transfer_signaling": "bt709", "primaries_signaling": "bt709",
                "planes": {
                    "Y": {"minimum_code_value": 64, "maximum_code_value": 940, "mean_code_value": 400.0, "sample_count": 2},
                    "U": {"minimum_code_value": 512, "maximum_code_value": 513, "mean_code_value": 512.5, "sample_count": 1},
                    "V": {"minimum_code_value": 510, "maximum_code_value": 511, "mean_code_value": 510.5, "sample_count": 1},
                },
            }

    rgb = PrecisionFrame.from_interleaved(
        width=2, height=1, channel_names=("R", "G", "B"),
        values=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6), source_path="clip.mp4", decoder="mock-ffmpeg",
        encoding=ColorEncoding(transfer="bt709", primaries="bt709"),
    )
    monkeypatch.setattr("yrgb_engine.video_yuv.decode_video_yuv_frame", lambda *_a, **_k: FakeYUVFrame())
    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", lambda *_a, **_k: rgb)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-report?timestamp_seconds=1.5&frame_index=38",
        files={"file": ("clip.mp4", b"mock-original-video", "video/mp4")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    report = payload["report"]
    assert payload["frame_index"] == 38
    assert len(payload["source_sha256"]) == 64
    assert report["measurement_domains"]["original_yuv_code_values"]["status"] == "reported"
    assert report["measurement_domains"]["nonlinear_rgb_code_values"]["status"] == "reported"
    assert report["measurement_domains"]["linear_light_rgb"]["status"] == "unavailable"
    assert report["reference_validation"]["status"] == "not_validated"
    assert report["color_metadata"]["resolution_status"] == "unresolved"


def test_video_report_endpoint_rejects_empty_upload():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post("/v1/media/video-report", files={"file": ("empty.mp4", b"", "video/mp4")})
    assert response.status_code == 400

def test_video_temporal_report_keeps_domains_separate_and_reports_sample_deltas(monkeypatch):
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    class FakeYUVFrame:
        width = 1
        height = 1
        def __init__(self, timestamp):
            self.timestamp = timestamp
            self.range_signaling = "tv"
            self.matrix_signaling = "bt709"
            self.transfer_signaling = "bt709"
            self.primaries_signaling = "bt709"
        def to_report(self):
            value = 100 + int(self.timestamp * 10)
            return {
                "measurement_domain": "original_yuv_code_values",
                "timestamp_seconds": self.timestamp, "pixel_format": "yuv444p10le",
                "bit_depth": 10, "planes": {
                    "Y": {"minimum_code_value": value, "maximum_code_value": value, "mean_code_value": float(value), "sample_count": 1},
                    "U": {"minimum_code_value": 512, "maximum_code_value": 512, "mean_code_value": 512.0, "sample_count": 1},
                    "V": {"minimum_code_value": 512, "maximum_code_value": 512, "mean_code_value": 512.0, "sample_count": 1},
                },
            }

    def fake_yuv(_path, *, timestamp_seconds):
        return FakeYUVFrame(timestamp_seconds)
    def fake_rgb(_path, *, timestamp_seconds):
        value = 0.1 + timestamp_seconds * 0.1
        return PrecisionFrame.from_interleaved(
            width=1, height=1, channel_names=("R", "G", "B"),
            values=(value, value + 0.1, value + 0.2), source_path="clip.mp4",
            decoder="mock-ffmpeg", encoding=ColorEncoding(transfer="bt709"),
        )
    monkeypatch.setattr("yrgb_engine.video_yuv.decode_video_yuv_frame", fake_yuv)
    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_rgb)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-temporal-report?start_seconds=0&interval_seconds=1&frame_count=3",
        files={"file": ("clip.mp4", b"mock-original-video", "video/mp4")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sampling"]["sample_count"] == 3
    domains = payload["measurement_domains"]
    assert len(domains["original_yuv_code_values"]["frames"]) == 3
    assert len(domains["nonlinear_rgb_code_values"]["frames"]) == 3
    assert domains["linear_light_rgb"]["status"] == "unavailable"
    assert payload["temporal_analysis"]["classification"] == "not_classified"
    assert payload["temporal_analysis"]["first_to_last_mean_delta"]["rgb_R"] == pytest.approx(0.2)


def test_video_temporal_report_rejects_frame_count_over_limit():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-temporal-report?frame_count=25",
        files={"file": ("clip.mp4", b"mock-video", "video/mp4")},
    )
    assert response.status_code == 422

def test_video_roi_temporal_report_returns_dense_fixed_roi_samples(monkeypatch):
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    def fake_decode(_path, *, timestamp_seconds):
        value = 0.1 + timestamp_seconds
        return PrecisionFrame.from_interleaved(
            width=2, height=2, channel_names=("R", "G", "B"),
            values=(value, value, value, value, value, value,
                    value, value, value, value, value, value),
            source_path="clip.mp4", decoder="mock-ffmpeg",
            encoding=ColorEncoding(transfer="bt709"),
        )

    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-roi-temporal-report?interval_seconds=0.04&frame_count=24&minimum_samples=24",
        files={"file": ("clip.mp4", b"mock-original-video", "video/mp4")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sampling"]["sample_count"] == 24
    assert payload["sampling"]["frame_index_semantics"].startswith("sample ordinal")
    assert payload["temporal_analysis"]["dense_sampling"] is True
    assert payload["temporal_analysis"]["flicker_assessment"]["status"] == "inconclusive"
    assert payload["temporal_analysis"]["exposure_drift_assessment"]["status"] == "unavailable"
    assert len(payload["samples"]) == 24
    assert payload["samples"][0]["roi_measurement"]["pixel_count"] == 4
    assert payload["measurement_domain"] == "decoder_float_output"


def test_video_roi_temporal_report_rejects_roi_outside_frame():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-roi-temporal-report?roi_x=0.8&roi_width=0.3",
        files={"file": ("clip.mp4", b"mock-video", "video/mp4")},
    )
    assert response.status_code == 422
    assert "ROI rectangle" in response.json()["detail"]


def test_video_roi_temporal_report_rejects_more_than_240_samples():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-roi-temporal-report?frame_count=241",
        files={"file": ("clip.mp4", b"mock-video", "video/mp4")},
    )
    assert response.status_code == 422



def test_still_analyze_exposes_waveform_and_vectorscope_only_when_standard_selected(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    def fake_decode(_path):
        return PrecisionFrame.from_interleaved(
            width=2, height=1, channel_names=("R", "G", "B"),
            values=[0.1, 0.2, 0.3, 0.7, 0.6, 0.5],
            source_path="fixture", decoder="test-decoder",
            sample_domain="test_encoded_values",
        )

    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/analyze?scope_standard=bt709",
        files={"file": ("sample.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["scope_standard"] == "bt709"
    assert analysis["waveform"]["width"] == 128
    assert analysis["waveform"]["height"] == 96
    assert len(analysis["vectorscope_points"]) == 2
    assert "manually selected BT709 coefficients" in analysis["scope_note"]


def test_video_frame_exposes_manual_bt2020_scopes(monkeypatch):
    from yrgb_engine.precision import PrecisionFrame

    def fake_decode(_path, *, timestamp_seconds=0.0):
        return PrecisionFrame.from_interleaved(
            width=1, height=1, channel_names=("R", "G", "B"),
            values=[0.2, 0.4, 0.8], source_path="fixture",
            decoder="test-ffmpeg", sample_domain="test_video_source_values",
        )

    monkeypatch.setattr("yrgb_engine.video_precision.decode_video_float_frame", fake_decode)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/video-frame?scope_standard=bt2020",
        files={"file": ("clip.mov", b"fake-video", "video/quicktime")},
    )
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["scope_standard"] == "bt2020"
    assert analysis["waveform"] is not None
    assert len(analysis["vectorscope_points"]) == 1


def test_invalid_scope_standard_is_rejected():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/analyze?scope_standard=rec709",
        files={"file": ("sample.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 422



def test_reference_transform_validation_endpoint_returns_audit_without_promoting_profile(tmp_path, monkeypatch):
    import json
    from yrgb_engine.transform_validation import TransformValidationResult

    config = tmp_path / "pinned.ocio"
    config.write_text("pinned-config")
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    profile_id = "sony.slog3.sgamut3cine"
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Sony",
        "encoding": "S-Log3",
        "gamut": "S-Gamut3.Cine",
        "camera_models": ["ILME-FX30"],
        "status": "unverified",
        "transform_id": "test.sony.transform",
        "ocio_source_space": "Sony S-Log3",
        "ocio_destination_space": "Linear Working",
        "output_transfer": "Linear",
        "output_primaries": "Test Wide Gamut",
    }])

    def fake_validate(manifest_path, *, config_path, registry, tolerance):
        return TransformValidationResult(
            profile_id=profile_id,
            transform_id="test.sony.transform",
            source_space="Sony S-Log3",
            destination_space="Linear Working",
            config_sha256="a" * 64,
            reference_set_id="sony-measured-reference-v1",
            vector_count=24,
            max_absolute_error=0.000001,
            tolerance=tolerance,
            passed=True,
            ocio_version="test",
        )

    monkeypatch.setattr("yrgb_engine.reference_data.validate_reference_manifest", fake_validate)
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/transforms/validate-reference",
        files={"manifest_file": ("reference.json", json.dumps({"schema_version": 1}), "application/json")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["passed"] is True
    assert payload["reference_set_id"] == "sony-measured-reference-v1"
    assert payload["promotion_status"] == "not_promoted"
    assert registry.get_by_id(profile_id)["usable_for_transform"] is False


def test_reference_transform_validation_endpoint_requires_pinned_ocio_config(monkeypatch):
    monkeypatch.delenv("YRGB_OCIO_CONFIG", raising=False)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/transforms/validate-reference",
        files={"manifest_file": ("reference.json", b"{}", "application/json")},
    )
    assert response.status_code == 503
    assert "pinned" in response.json()["detail"]


def test_reference_transform_validation_endpoint_rejects_non_json_manifest(tmp_path, monkeypatch):
    config = tmp_path / "pinned.ocio"
    config.write_text("pinned-config")
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/transforms/validate-reference",
        files={"manifest_file": ("reference.txt", b"{}", "text/plain")},
    )
    assert response.status_code == 415



def test_native_grade_preview_blocks_unverified_camera_profile():
    registry = ProfileRegistry([{
        "id": "sony.slog3.sgamut3cine",
        "manufacturer": "Sony",
        "encoding": "S-Log3",
        "gamut": "S-Gamut3.Cine",
        "status": "unverified",
        "transform_id": None,
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-grade-preview",
        data={"profile_id": "sony.slog3.sgamut3cine", "exposure_stops": "1.0"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 409
    assert "not reference-validated" in response.json()["detail"]


def test_native_grade_preview_rejects_unknown_camera_profile():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/native-grade-preview",
        data={"profile_id": "unknown.profile"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 404



def test_native_grade_preview_uses_shared_pipeline_and_returns_preview_only(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from types import SimpleNamespace
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned-native.ocio"
    config.write_text("native-pinned-config")
    profile_id = "test.linear.camera.profile"
    transform_id = "test.camera.to.linear"
    source_space = "Test Camera Log"
    working_space = "Linear DaVinci WideGamut"
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Test",
        "encoding": "Test Log",
        "gamut": "Test Gamut",
        "status": "verified",
        "transform_id": transform_id,
        "ocio_source_space": source_space,
        "ocio_destination_space": working_space,
        "output_transfer": "Linear",
        "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True,
            "profile_id": profile_id,
            "transform_id": transform_id,
            "source_space": source_space,
            "destination_space": working_space,
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-independent-linear-reference",
            "vector_count": 12,
            "max_absolute_error": 0.00001,
            "tolerance": 0.0001,
            "ocio_version": "test",
        },
    }])
    source = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6), source_path="fixture", decoder="test",
        encoding=ColorEncoding(),
    )
    preview = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6), source_path="fixture", decoder="test",
        encoding=ColorEncoding(
            transfer="sRGB", profile_id="Preview sRGB",
            working_space_id="Preview sRGB", validated=False,
        ),
    )
    seen = {}

    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", lambda _path: source)

    def fake_pipeline(frame, settings, **kwargs):
        seen["settings"] = settings
        seen["working_space"] = kwargs["working_space_id"]
        return SimpleNamespace(display_preview_frame=preview)

    monkeypatch.setattr("yrgb_engine.grading_pipeline.process_validated_still", fake_pipeline)
    monkeypatch.setattr(
        "yrgb_engine.preview.save_preview_png",
        lambda _frame, path, **_kwargs: Path(path).write_bytes(b"native-preview-fixture") or Path(path),
    )
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    monkeypatch.setenv("YRGB_PREVIEW_SPACE", "Preview sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_TRANSFER", "sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_PRIMARIES", "BT.709")

    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-grade-preview",
        data={
            "profile_id": profile_id,
            "exposure_stops": "1.5",
            "contrast": "1.2",
            "curve_midpoint": "0.58",
        },
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200, response.text
    assert response.content == b"native-preview-fixture"
    assert response.headers["x-yrgb-native-grade"] == "float32-linear"
    assert response.headers["x-yrgb-preview-only"] == "true"
    assert seen["working_space"] == working_space
    assert seen["settings"].exposure_stops == pytest.approx(1.5)
    assert seen["settings"].master_curve == ((0.0, 0.0), (0.5, 0.58), (1.0, 1.0))


def test_native_measurements_uses_same_validated_graded_frame_for_scopes_and_accuracy(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from types import SimpleNamespace
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned-measure.ocio"
    config.write_text("measure-pinned-config")
    profile_id = "test.measure.camera"
    transform_id = "test.camera.to.linear"
    source_space = "Test Camera Log"
    working_space = "Linear DaVinci WideGamut"
    registry = ProfileRegistry([{
        "id": profile_id,
        "manufacturer": "Test",
        "encoding": "Test Log",
        "gamut": "Test Gamut",
        "status": "verified",
        "transform_id": transform_id,
        "ocio_source_space": source_space,
        "ocio_destination_space": working_space,
        "output_transfer": "Linear",
        "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True,
            "profile_id": profile_id,
            "transform_id": transform_id,
            "source_space": source_space,
            "destination_space": working_space,
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-independent-measurement-reference",
            "vector_count": 16,
            "max_absolute_error": 0.00001,
            "tolerance": 0.0001,
            "ocio_version": "test",
        },
    }])
    source = PrecisionFrame.from_interleaved(
        width=4, height=4, channel_names=("R", "G", "B"),
        values=(0.18, 0.18, 0.18) * 16, source_path="fixture", decoder="test",
        encoding=ColorEncoding(),
    )
    graded = PrecisionFrame.from_interleaved(
        width=4, height=4, channel_names=("R", "G", "B"),
        values=(0.18, 0.18, 0.18) * 16, source_path="fixture", decoder="test",
        encoding=ColorEncoding(
            primaries="DaVinci Wide Gamut", transfer="Linear",
            profile_id=profile_id, validated=True,
            working_space_id=working_space, transform_id=transform_id,
        ),
        sample_domain="validated_linear_native_grade_float32",
        purpose="graded_still_candidate",
    )
    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", lambda _path: source)
    monkeypatch.setattr(
        "yrgb_engine.grading_pipeline.process_validated_still",
        lambda *_args, **_kwargs: SimpleNamespace(graded_frame=graded),
    )
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    monkeypatch.setenv("YRGB_PREVIEW_SPACE", "Preview sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_TRANSFER", "sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_PRIMARIES", "BT.709")

    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-measurements",
        data={
            "profile_id": profile_id,
            "roi_x": "0", "roi_y": "0", "roi_width": "4", "roi_height": "4",
            "exposure_stops": "0.0",
        },
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["measurement_source"] == "same_validated_native_graded_float32_frame"
    assert payload["validated"] is True
    assert payload["scopes"]["sample_domain"] == "validated_linear_native_grade_float32"
    assert payload["scopes"]["analysis"]["waveform"] is not None
    assert payload["scopes"]["analysis"]["vectorscope_points"] is not None
    assert payload["correction_accuracy"]["status"] == "scored"
    assert payload["correction_accuracy"]["score"] == pytest.approx(100.0)
    assert payload["correction_accuracy"]["exposure"]["metrics"][0]["measured"] == pytest.approx(0.0)


def test_native_measurements_reject_roi_outside_still_before_processing(tmp_path, monkeypatch):
    import hashlib
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned-roi.ocio"
    config.write_text("roi-pinned-config")
    profile_id = "test.roi.camera"
    transform_id = "test.roi.transform"
    source_space = "ROI Camera Log"
    working_space = "Linear DaVinci WideGamut"
    registry = ProfileRegistry([{
        "id": profile_id, "manufacturer": "Test", "encoding": "Test Log",
        "gamut": "Test Gamut", "status": "verified", "transform_id": transform_id,
        "ocio_source_space": source_space, "ocio_destination_space": working_space,
        "output_transfer": "Linear", "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True, "profile_id": profile_id, "transform_id": transform_id,
            "source_space": source_space, "destination_space": working_space,
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-roi-reference", "vector_count": 8,
            "max_absolute_error": 0.00001, "tolerance": 0.0001, "ocio_version": "test",
        },
    }])
    frame = PrecisionFrame.from_interleaved(
        width=2, height=2, channel_names=("R", "G", "B"),
        values=(0.18, 0.18, 0.18) * 4, source_path="fixture", decoder="test",
        encoding=ColorEncoding(),
    )
    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", lambda _path: frame)
    monkeypatch.setenv("YRGB_OCIO_CONFIG", str(config))
    monkeypatch.setenv("YRGB_PREVIEW_SPACE", "Preview sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_TRANSFER", "sRGB")
    monkeypatch.setenv("YRGB_PREVIEW_PRIMARIES", "BT.709")
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-measurements",
        data={
            "profile_id": profile_id, "roi_x": "3", "roi_y": "3",
            "roi_width": "2", "roi_height": "2",
        },
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 422
    assert "inside the decoded still" in response.json()["detail"]


def test_native_measurements_blocks_unverified_profile():
    registry = ProfileRegistry([{
        "id": "sony.slog3.sgamut3cine", "manufacturer": "Sony",
        "encoding": "S-Log3", "gamut": "S-Gamut3.Cine",
        "status": "unverified", "transform_id": None,
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-measurements",
        data={"profile_id": "sony.slog3.sgamut3cine", "roi_x": "0",
              "roi_y": "0", "roi_width": "1", "roi_height": "1"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 409
    assert "not reference-validated" in response.json()["detail"]


def test_native_grade_export_returns_full_resolution_float32_master(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from types import SimpleNamespace
    from yrgb_engine.precision import ColorEncoding, PrecisionFrame

    config = tmp_path / "pinned-export.ocio"
    config.write_text("export-pinned-config")
    profile_id = "test.export.camera"
    transform_id = "test.export.transform"
    source_space = "Export Camera Log"
    working_space = "Linear DaVinci WideGamut"
    registry = ProfileRegistry([{
        "id": profile_id, "manufacturer": "Test", "encoding": "Test Log",
        "gamut": "Test Gamut", "status": "verified", "transform_id": transform_id,
        "ocio_source_space": source_space, "ocio_destination_space": working_space,
        "output_transfer": "Linear", "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True, "profile_id": profile_id, "transform_id": transform_id,
            "source_space": source_space, "destination_space": working_space,
            "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "reference_set_id": "test-export-reference", "vector_count": 12,
            "max_absolute_error": 0.00001, "tolerance": 0.0001, "ocio_version": "test",
        },
    }])
    source = PrecisionFrame.from_interleaved(
        width=2, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6, 1.5, -0.1, 2.0),
        source_path="fixture", decoder="test", encoding=ColorEncoding(),
    )
    graded = PrecisionFrame.from_interleaved(
        width=2, height=1, channel_names=("R", "G", "B"),
        values=(0.2, 0.4, 0.6, 1.5, -0.1, 2.0),
        source_path="fixture", decoder="test",
        encoding=ColorEncoding(
            primaries="DaVinci Wide Gamut", transfer="Linear",
            profile_id=profile_id, validated=True,
            working_space_id=working_space, transform_id=transform_id,
        ),
        sample_domain="validated_linear_native_grade_float32",
        purpose="graded_still_candidate",
    )
    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", lambda _path: source)
    seen = {}
    def fake_pipeline(_frame, settings, **kwargs):
        seen["settings"] = settings
        seen["kwargs"] = kwargs
        return SimpleNamespace(graded_frame=graded)

    monkeypatch.setattr("yrgb_engine.grading_pipeline.process_validated_still", fake_pipeline)
    def fake_writer(frame, path):
        seen["export_frame"] = frame
        Path(path).write_bytes(b"float32-master-fixture")
        return Path(path)
    monkeypatch.setattr("yrgb_engine.native_export.save_native_float_image", fake_writer)
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-grade-export",
        data={"profile_id": profile_id, "export_format": "exr", "exposure_stops": "1.25", "contrast": "1.1", "pivot": "0.2", "curve_midpoint": "0.6"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 200, response.text
    assert response.content == b"float32-master-fixture"
    assert response.headers["x-yrgb-export-scope"] == "full-resolution"
    assert response.headers["x-yrgb-sample-format"] == "float32"
    assert response.headers["x-yrgb-sample-domain"] == "validated-scene-linear"
    assert response.headers["x-yrgb-clamped"] == "false"
    assert response.headers["x-yrgb-frame-width"] == "2"
    assert response.headers["x-yrgb-frame-height"] == "1"
    from yrgb_engine.native_export import native_frame_sha256
    assert seen["export_frame"] is graded
    assert seen["settings"].exposure_stops == pytest.approx(1.25)
    assert seen["settings"].contrast == pytest.approx(1.1)
    assert seen["settings"].pivot == pytest.approx(0.2)
    assert seen["settings"].master_curve == ((0.0, 0.0), (0.5, 0.6), (1.0, 1.0))
    assert seen["kwargs"]["working_space_id"] == working_space
    assert seen["kwargs"]["display_space_id"] == working_space
    assert response.headers["x-yrgb-float-samples-sha256"] == native_frame_sha256(graded)


def test_native_grade_export_blocks_unverified_camera_profile():
    registry = ProfileRegistry([{
        "id": "sony.slog3.sgamut3cine", "manufacturer": "Sony",
        "encoding": "S-Log3", "gamut": "S-Gamut3.Cine",
        "status": "unverified", "transform_id": None,
    }])
    client = TestClient(create_app(registry=registry))
    response = client.post(
        "/v1/media/native-grade-export",
        data={"profile_id": "sony.slog3.sgamut3cine", "export_format": "exr"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 409
    assert "not reference-validated" in response.json()["detail"]


def test_native_grade_export_rejects_unsupported_format():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/native-grade-export",
        data={"profile_id": "missing", "export_format": "png"},
        files={"file": ("still.tif", b"fake-image", "image/tiff")},
    )
    assert response.status_code == 422


def test_cors_exposes_native_master_metadata_headers():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.options(
        "/v1/media/native-grade-export",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "").casefold()
    assert "x-yrgb-frame-width" in exposed
    assert "x-yrgb-frame-height" in exposed
    assert "x-yrgb-float-samples-sha256" in exposed
