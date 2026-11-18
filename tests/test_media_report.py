from array import array

import pytest

from yrgb_engine.media_report import build_single_frame_measurement_report
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def _rgb_frame():
    return PrecisionFrame(
        width=2,
        height=1,
        channel_names=("R", "G", "B"),
        samples=array("f", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
        source_path="sample.mp4",
        decoder="FFmpeg/gbrpf32le",
        encoding=ColorEncoding(
            primaries="bt709", transfer="bt709", matrix="RGB",
            range="full", source_bit_depth=10, metadata_source="ffprobe+ffmpeg",
            validated=False,
        ),
        sample_domain="ffmpeg_gbrpf32le_rgb_float_source_transfer_retained",
    )


def _yuv_report():
    return {
        "measurement_domain": "original_yuv_code_values",
        "timestamp_seconds": 1.0,
        "pixel_format": "yuv422p10le",
        "bit_depth": 10,
        "range_signaling": "tv",
        "matrix_signaling": "bt709",
        "transfer_signaling": "bt709",
        "primaries_signaling": "bt709",
        "planes": {
            "Y": {"minimum_code_value": 64, "maximum_code_value": 940,
                  "mean_code_value": 400.0, "sample_count": 2},
            "U": {"minimum_code_value": 512, "maximum_code_value": 513,
                  "mean_code_value": 512.5, "sample_count": 1},
            "V": {"minimum_code_value": 510, "maximum_code_value": 511,
                  "mean_code_value": 510.5, "sample_count": 1},
        },
    }


def test_report_keeps_yuv_rgb_and_linear_domains_separate():
    report = build_single_frame_measurement_report(
        asset_id="clip-01", source_reference="sample.mp4", source_sha256="a" * 64,
        frame_index=25, timestamp_seconds=1.0, yuv_measurement=_yuv_report(),
        rgb_frame=_rgb_frame(), frame_rate="25/1",
    )
    domains = report["measurement_domains"]
    assert domains["original_yuv_code_values"]["status"] == "reported"
    assert domains["original_yuv_code_values"]["frames"][0]["sample_count"] == 4
    assert domains["nonlinear_rgb_code_values"]["status"] == "reported"
    assert "not original integer RGB" in domains["nonlinear_rgb_code_values"]["numeric_domain"]
    assert domains["linear_light_rgb"]["status"] == "unavailable"
    assert report["reference_validation"]["status"] == "not_validated"
    assert report["color_metadata"]["resolution_status"] == "unresolved"


def test_report_rejects_mismatched_timestamps():
    with pytest.raises(ValueError, match="same timestamp"):
        build_single_frame_measurement_report(
            asset_id="clip-01", source_reference="sample.mp4", source_sha256=None,
            frame_index=0, timestamp_seconds=2.0, yuv_measurement=_yuv_report(),
            rgb_frame=_rgb_frame(),
        )


def test_report_rejects_invalid_source_hash():
    with pytest.raises(ValueError, match="SHA-256"):
        build_single_frame_measurement_report(
            asset_id="clip-01", source_reference="sample.mp4", source_sha256="bad",
            frame_index=0, timestamp_seconds=1.0, yuv_measurement=_yuv_report(),
            rgb_frame=_rgb_frame(),
        )
