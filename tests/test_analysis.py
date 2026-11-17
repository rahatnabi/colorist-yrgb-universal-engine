import pytest

from yrgb_engine.analysis import FrameAnalysisError, analyze_frame
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def make_frame(values, width=None, height=1, encoding=None):
    pixels = len(values) // 3
    return PrecisionFrame.from_interleaved(
        width=width or pixels, height=height, channel_names=("R", "G", "B"),
        values=values, source_path="synthetic", decoder="test",
        encoding=encoding or ColorEncoding(),
    )


def test_statistics_histogram_and_rgb_parade_preserve_headroom():
    frame = make_frame([0.0, 0.5, 1.5, -0.2, 0.25, 2.0])
    result = analyze_frame(
        frame, histogram_bins=4, scope_width=2, scope_height=4,
        value_range=(0.0, 1.0), clipping_thresholds=(0.0, 1.0),
    )
    assert result.channels["R"].minimum == pytest.approx(-0.2)
    assert result.channels["B"].maximum == pytest.approx(2.0)
    assert result.histograms["R"].underflow == 1
    assert result.histograms["B"].overflow == 1
    assert result.rgb_parade["B"].overflow == 1
    assert result.clipping == {"below_low": 1, "above_high": 1}
    assert result.waveform is None


def test_linear_luminance_requires_explicit_declaration_and_coefficients():
    gray = make_frame([0.18, 0.18, 0.18])
    with pytest.raises(FrameAnalysisError, match="linear_rgb=True"):
        analyze_frame(gray, luminance_coefficients=(0.2126, 0.7152, 0.0722))
    result = analyze_frame(
        gray, luminance_coefficients=(0.2126, 0.7152, 0.0722),
        linear_rgb=True, gray_reference=0.18,
    )
    assert result.luminance is not None
    assert result.luminance.mean == pytest.approx(0.18)
    assert result.luminance.gray_mean_error == pytest.approx(0.0)


def test_waveform_and_vectorscope_require_explicit_coefficients():
    frame = make_frame([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    result = analyze_frame(
        frame, waveform_coefficients=(0.2126, 0.7152, 0.0722),
        vectorscope_coefficients=(0.2126, 0.7152, 0.0722),
    )
    assert result.waveform is not None
    assert len(result.vectorscope_points) == 2
    assert result.vectorscope_points[0] != result.vectorscope_points[1]


def test_ambiguous_channels_and_invalid_ranges_are_rejected():
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("Y",), values=[0.5],
        source_path="x", decoder="test",
    )
    with pytest.raises(FrameAnalysisError, match="R, G and B"):
        analyze_frame(frame)
    rgb = make_frame([0.1, 0.2, 0.3])
    with pytest.raises(FrameAnalysisError, match="value_range"):
        analyze_frame(rgb, value_range=(1.0, 0.0))


def test_scope_horizontal_bins_follow_image_coordinates():
    frame = make_frame([0.1, 0.1, 0.1, 0.9, 0.9, 0.9], width=2)
    result = analyze_frame(
        frame, scope_width=2, scope_height=10,
        value_range=(0.0, 1.0),
    )
    red = result.rgb_parade["R"]
    assert sum(red.counts[0]) == 1
    assert sum(red.counts[1]) == 1
