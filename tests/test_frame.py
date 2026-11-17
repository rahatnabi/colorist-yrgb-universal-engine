import pytest

from yrgb_engine.frame import DecodedFrame


def test_rgb24_frame_accepts_exact_buffer():
    frame = DecodedFrame(2, 1, "rgb24", bytes(6), "sample.png", "test")
    assert frame.width == 2
    assert frame.purpose == "preview"


def test_rgb24_frame_rejects_wrong_buffer_length():
    with pytest.raises(ValueError, match="buffer length"):
        DecodedFrame(2, 1, "rgb24", bytes(5), "sample.png", "test")


def test_frame_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="positive"):
        DecodedFrame(0, 1, "rgb24", b"", "sample.png", "test")
