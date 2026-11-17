import pytest

from yrgb_engine.exposure import (
    ExposureAnalysisError, PixelRegion, analyze_tonal_distribution,
    compare_exposure_regions, measure_exposure_region,
)
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


COEFFS = (0.2126, 0.7152, 0.0722)


def frame(values, width=None, height=1, *, transfer="linear", validated=True):
    return PrecisionFrame.from_interleaved(
        width=width or (len(values) // 3), height=height, channel_names=("R", "G", "B"), values=values,
        source_path="synthetic", decoder="test",
        encoding=ColorEncoding(primaries="rec709", transfer=transfer,
                               validated=validated),
    )


def test_region_at_18_percent_gray_measures_zero_stops_and_neutral():
    image = frame([0.18, 0.18, 0.18, 0.18, 0.18, 0.18])
    result = measure_exposure_region(
        image, PixelRegion(0, 0, 2, 1), luminance_coefficients=COEFFS
    )
    assert result.mean_luminance == pytest.approx(0.18)
    assert result.exposure_stops_from_gray == pytest.approx(0.0, abs=1e-6)
    assert result.neutral_spread == pytest.approx(0.0, abs=1e-6)
    assert result.neutral_candidate is True


def test_one_stop_above_gray_and_region_bounds():
    image = frame([0.36, 0.36, 0.36])
    result = measure_exposure_region(
        image, PixelRegion(0, 0, 1, 1), luminance_coefficients=COEFFS
    )
    assert result.exposure_stops_from_gray == pytest.approx(1.0, abs=1e-6)
    with pytest.raises(ExposureAnalysisError, match="outside"):
        measure_exposure_region(
            image, PixelRegion(1, 0, 1, 1), luminance_coefficients=COEFFS
        )


def test_unknown_or_unvalidated_transfer_is_rejected():
    for image in (frame([0.18, 0.18, 0.18], transfer="unknown"),
                  frame([0.18, 0.18, 0.18], validated=False)):
        with pytest.raises(ExposureAnalysisError, match="linear|validated"):
            measure_exposure_region(
                image, PixelRegion(0, 0, 1, 1), luminance_coefficients=COEFFS
            )


def test_tonal_distribution_uses_explicit_thresholds():
    image = frame([0.01, 0.01, 0.01, 0.18, 0.18, 0.18])
    result = analyze_tonal_distribution(
        image, luminance_coefficients=COEFFS,
        shadow_threshold=0.02, highlight_threshold=0.15,
    )
    assert result.shadow_fraction == pytest.approx(0.5)
    assert result.highlight_fraction == pytest.approx(0.5)
    assert result.luminance_percentiles[2] == pytest.approx(0.095)


def test_region_consistency_reports_stop_delta():
    base = frame([0.18, 0.18, 0.18])
    brighter = frame([0.36, 0.36, 0.36])
    first = measure_exposure_region(
        base, PixelRegion(0, 0, 1, 1), luminance_coefficients=COEFFS
    )
    second = measure_exposure_region(
        brighter, PixelRegion(0, 0, 1, 1), luminance_coefficients=COEFFS
    )
    assert compare_exposure_regions(first, second).exposure_delta_stops == pytest.approx(1.0)


def test_negative_samples_rejected_for_this_exposure_metric():
    image = frame([-0.1, 0.2, 0.2])
    with pytest.raises(ExposureAnalysisError, match="Negative"):
        measure_exposure_region(
            image, PixelRegion(0, 0, 1, 1), luminance_coefficients=COEFFS
        )
