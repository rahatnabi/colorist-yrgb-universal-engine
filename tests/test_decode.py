from unittest.mock import patch

import pytest

from yrgb_engine.decode import DecodeError, decode_still_preview, decode_video_preview_frame


def test_still_decoder_rejects_missing_file(tmp_path):
    with pytest.raises(DecodeError, match="File not found"):
        decode_still_preview(tmp_path / "missing.png")


def test_video_decoder_rejects_missing_file(tmp_path):
    with pytest.raises(DecodeError, match="File not found"):
        decode_video_preview_frame(tmp_path / "missing.mov")


def test_video_decoder_rejects_negative_timestamp(tmp_path):
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"not a real video")
    with pytest.raises(ValueError, match="zero or greater"):
        decode_video_preview_frame(clip, timestamp_seconds=-0.1)


def test_still_decoder_pixel_limit(tmp_path):
    image_path = tmp_path / "tiny.png"
    pytest.importorskip("PIL")
    from PIL import Image
    Image.new("RGB", (4, 4)).save(image_path)
    with pytest.raises(DecodeError, match="configured limit"):
        decode_still_preview(image_path, max_pixels=4)
