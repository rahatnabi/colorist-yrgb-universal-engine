from subprocess import CompletedProcess
from unittest.mock import patch

import numpy as np
import pytest

from yrgb_engine.oiio_decoder import HighPrecisionDecodeError
from yrgb_engine.video_yuv import decode_video_yuv_frame


def _stream(pixel_format="yuv420p10le", width=4, height=2):
    return {"width": width, "height": height, "pix_fmt": pixel_format,
            "color_range": "tv", "color_space": "bt709",
            "color_transfer": "bt709", "color_primaries": "bt709"}


def test_native_yuv_10bit_planes_and_threshold_denominators(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    payload = np.array([64, 100, 200, 940, 65, 66, 67, 68,
                        512, 513, 510, 511], dtype="<u2").tobytes()
    completed = CompletedProcess([], 0, payload, b"")
    with (
        patch("yrgb_engine.video_yuv._probe_stream", return_value=_stream()),
        patch("yrgb_engine.video_yuv.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("yrgb_engine.video_yuv.subprocess.run", return_value=completed),
    ):
        frame = decode_video_yuv_frame(clip)
    report = frame.to_report(thresholds={"Y": (64, 940), "U": (64, 960)})
    assert frame.planes["Y"].shape == (2, 4)
    assert frame.planes["U"].shape == (1, 2)
    assert report["measurement_domain"] == "original_yuv_code_values"
    assert report["planes"]["Y"]["minimum_code_value"] == 64
    assert report["planes"]["Y"]["maximum_code_value"] == 940
    assert report["planes"]["Y"]["below_threshold_count"] == 0
    assert report["planes"]["Y"]["above_threshold_count"] == 0
    assert report["planes"]["Y"]["threshold_denominator"] == 8
    assert report["range_signaling"] == "tv"
    assert report["matrix_signaling"] == "bt709"


def test_native_yuv_422_subsampling_dimensions(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    payload = np.zeros(16, dtype="<u2").tobytes()
    with (
        patch("yrgb_engine.video_yuv._probe_stream", return_value=_stream("yuv422p10le")),
        patch("yrgb_engine.video_yuv.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("yrgb_engine.video_yuv.subprocess.run",
              return_value=CompletedProcess([], 0, payload, b"")),
    ):
        frame = decode_video_yuv_frame(clip)
    assert frame.planes["U"].shape == (2, 2)
    assert frame.planes["V"].shape == (2, 2)


def test_yuv_decoder_rejects_unsupported_pixel_format(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    with patch("yrgb_engine.video_yuv._probe_stream", return_value=_stream("nv12")):
        with pytest.raises(HighPrecisionDecodeError, match="Unsupported pixel format"):
            decode_video_yuv_frame(clip)


def test_yuv_decoder_rejects_short_native_buffer(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    with (
        patch("yrgb_engine.video_yuv._probe_stream", return_value=_stream()),
        patch("yrgb_engine.video_yuv.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("yrgb_engine.video_yuv.subprocess.run",
              return_value=CompletedProcess([], 0, b"short", b"")),
    ):
        with pytest.raises(HighPrecisionDecodeError, match="size mismatch"):
            decode_video_yuv_frame(clip)


def test_yuv_thresholds_are_explicit_and_validate_order(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    payload = np.zeros(12, dtype="<u2").tobytes()
    with (
        patch("yrgb_engine.video_yuv._probe_stream", return_value=_stream()),
        patch("yrgb_engine.video_yuv.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("yrgb_engine.video_yuv.subprocess.run",
              return_value=CompletedProcess([], 0, payload, b"")),
    ):
        frame = decode_video_yuv_frame(clip)
    report = frame.to_report()
    assert report["planes"]["Y"]["threshold_denominator"] is None
    with pytest.raises(ValueError, match="below high"):
        frame.to_report(thresholds={"Y": (940, 64)})


def test_yuv_decoder_rejects_non_finite_timestamp(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"mock")
    with pytest.raises(ValueError, match="finite"):
        decode_video_yuv_frame(clip, timestamp_seconds=float("nan"))
