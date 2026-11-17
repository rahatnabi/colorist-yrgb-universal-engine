from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from yrgb_engine.oiio_decoder import HighPrecisionDecodeError
from yrgb_engine.video_precision import decode_video_float_frame


def test_video_float_decoder_rejects_missing_file(tmp_path):
    with pytest.raises(HighPrecisionDecodeError, match="File not found"):
        decode_video_float_frame(tmp_path / "missing.mov")


def test_video_float_decoder_rejects_negative_timestamp(tmp_path):
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"placeholder")
    with pytest.raises(ValueError, match="zero or greater"):
        decode_video_float_frame(clip, timestamp_seconds=-1)


def test_video_float_decoder_reorders_gbr_planes_to_rgb(tmp_path):
    np = pytest.importorskip("numpy")
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"placeholder")
    # One pixel: G=0.2, B=0.3, R=0.1 in FFmpeg's planar GBR order.
    payload = np.array([0.2, 0.3, 0.1], dtype="<f4").tobytes()
    stream = {
        "width": 1, "height": 1, "codec_name": "test", "pix_fmt": "yuv444p",
        "color_range": "tv", "color_space": "bt709",
        "color_transfer": "bt709", "color_primaries": "bt709",
        "bits_per_raw_sample": "10",
    }
    completed = CompletedProcess(args=[], returncode=0, stdout=payload, stderr=b"")
    with (
        patch("yrgb_engine.video_precision._probe_video_stream", return_value=stream),
        patch("yrgb_engine.video_precision.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch("yrgb_engine.video_precision.subprocess.run", return_value=completed),
    ):
        frame = decode_video_float_frame(clip)
    assert frame.pixel(0, 0) == pytest.approx((0.1, 0.2, 0.3))
    assert frame.encoding.primaries == "bt709"
    assert frame.encoding.transfer == "bt709"
    assert frame.encoding.source_bit_depth == 10
    assert frame.metadata["source_matrix"] == "bt709"


def test_video_float_decoder_enforces_pixel_limit(tmp_path):
    pytest.importorskip("numpy")
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"placeholder")
    stream = {"width": 4, "height": 4}
    with patch("yrgb_engine.video_precision._probe_video_stream", return_value=stream):
        with pytest.raises(HighPrecisionDecodeError, match="configured limit"):
            decode_video_float_frame(clip, max_pixels=8)
