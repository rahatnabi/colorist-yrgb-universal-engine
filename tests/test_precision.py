from array import array
import pytest

from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def test_precision_frame_keeps_values_outside_display_range():
    frame = PrecisionFrame.from_interleaved(
        width=2,
        height=1,
        channel_names=("R", "G", "B"),
        values=(-0.25, 0.18, 1.5, 2.0, 0.5, 0.0),
        source_path="synthetic.exr",
        decoder="test",
        encoding=ColorEncoding(primaries="unknown", transfer="unknown"),
    )
    assert frame.pixel(0, 0) == pytest.approx((-0.25, 0.18, 1.5))
    assert frame.pixel(1, 0) == pytest.approx((2.0, 0.5, 0.0))
    assert frame.bytes_per_sample == 4


def test_precision_frame_requires_exact_buffer_size():
    with pytest.raises(ValueError, match="Expected"):
        PrecisionFrame(1, 1, ("R", "G", "B"), array("f", [0.1]), "x", "test")


def test_precision_frame_rejects_non_finite_samples():
    with pytest.raises(ValueError, match="finite"):
        PrecisionFrame.from_interleaved(
            width=1, height=1, channel_names=("Y",), values=[float("nan")],
            source_path="x", decoder="test"
        )


def test_precision_frame_requires_unique_channels():
    with pytest.raises(ValueError, match="unique"):
        PrecisionFrame.from_interleaved(
            width=1, height=1, channel_names=("R", "R"), values=[0.1, 0.2],
            source_path="x", decoder="test"
        )
