import pytest

from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.skin_tone import (
    SkinToneDiagnosticError,
    analyze_selected_region,
)


def make_frame(values, *, width=2, channel_names=("R", "G", "B")):
    return PrecisionFrame.from_interleaved(
        width=width,
        height=1,
        channel_names=channel_names,
        values=values,
        source_path="synthetic",
        decoder="test",
        encoding=ColorEncoding(transfer="camera-log", validated=False),
    )


def test_selected_roi_returns_signal_domain_chroma_statistics():
    frame = make_frame([0.7, 0.4, 0.3, 0.6, 0.35, 0.25])
    result = analyze_selected_region(
        frame, PixelRegion(0, 0, 2, 1), signal_domain="S-Log3 / S-Gamut3.Cine"
    )
    assert result.sample_count == 2
    assert result.signal_domain == "S-Log3 / S-Gamut3.Cine"
    assert result.mean_hue_degrees is not None
    assert 0 <= result.mean_hue_degrees < 360
    assert 0 <= result.mean_saturation <= 1
    assert "no skin classification" in result.note


def test_circular_hue_mean_handles_wraparound():
    # Red hues close to 0/360 degrees must average near the red axis, not 180.
    frame = make_frame([1.0, 0.01, 0.0, 1.0, 0.0, 0.01])
    result = analyze_selected_region(
        frame, PixelRegion(0, 0, 2, 1), signal_domain="test RGB"
    )
    assert result.mean_hue_degrees < 10 or result.mean_hue_degrees > 350


def test_achromatic_roi_has_no_mean_hue():
    frame = make_frame([0.3, 0.3, 0.3, 0.5, 0.5, 0.5])
    result = analyze_selected_region(
        frame, PixelRegion(0, 0, 2, 1), signal_domain="Rec.709"
    )
    assert result.mean_hue_degrees is None
    assert result.hue_percentiles_degrees is None
    assert result.mean_saturation == pytest.approx(0.0)


def test_requires_explicit_domain_and_valid_roi():
    frame = make_frame([0.1, 0.2, 0.3], width=1)
    with pytest.raises(SkinToneDiagnosticError, match="signal_domain"):
        analyze_selected_region(frame, PixelRegion(0, 0, 1, 1), signal_domain=" ")
    with pytest.raises(SkinToneDiagnosticError, match="outside"):
        analyze_selected_region(
            frame, PixelRegion(1, 0, 1, 1), signal_domain="linear RGB"
        )


def test_rejects_non_rgb_and_negative_values():
    mono = make_frame([0.5], width=1, channel_names=("Y",))
    with pytest.raises(SkinToneDiagnosticError, match="R, G and B"):
        analyze_selected_region(mono, PixelRegion(0, 0, 1, 1), signal_domain="Y")
    negative = make_frame([-0.1, 0.2, 0.3], width=1)
    with pytest.raises(SkinToneDiagnosticError, match="non-negative"):
        analyze_selected_region(
            negative, PixelRegion(0, 0, 1, 1), signal_domain="linear RGB"
        )
