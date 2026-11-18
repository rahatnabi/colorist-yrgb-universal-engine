import pytest

from yrgb_engine.color_matching import (
    ColorMatchingError,
    analyze_color_region,
    compare_color_regions,
)
from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


MATRIX = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
WHITE = (1.0, 1.0, 1.0)
COEFFS = (0.2126, 0.7152, 0.0722)
ROI = PixelRegion(0, 0, 1, 1)


def frame(rgb, *, working_space="DWG/Intermediate", transform="camera-a"):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"), values=rgb,
        source_path="synthetic", decoder="test",
        encoding=ColorEncoding(
            primaries="working-space", transfer="linear", validated=True,
            working_space_id=working_space, transform_id=transform,
        ),
    )


def measure(image):
    return analyze_color_region(
        image, ROI, rgb_to_xyz_matrix=MATRIX,
        reference_white_xyz=WHITE, luminance_coefficients=COEFFS,
    )


def test_identical_regions_have_zero_delta_e_and_rgb_delta():
    first = measure(frame((0.18, 0.18, 0.18)))
    second = measure(frame((0.18, 0.18, 0.18), transform="other-camera-transform"))
    report = compare_color_regions(first, second, delta_e_threshold=2.0)
    assert report.delta_e76 == pytest.approx(0.0, abs=1e-9)
    assert report.delta_rgb == pytest.approx((0.0, 0.0, 0.0))
    assert report.threshold_exceeded is False


def test_color_difference_reports_lab_and_threshold_flag():
    reference = measure(frame((0.18, 0.18, 0.18)))
    candidate = measure(frame((0.18, 0.12, 0.08)))
    report = compare_color_regions(reference, candidate, delta_e_threshold=1.0)
    assert report.delta_e76 > 1.0
    assert report.threshold_exceeded is True
    assert report.channel_balance_delta is not None


def test_exposure_delta_is_reported_separately_from_color_difference():
    reference = measure(frame((0.18, 0.18, 0.18)))
    candidate = measure(frame((0.36, 0.36, 0.36)))
    report = compare_color_regions(reference, candidate)
    assert report.exposure_delta_stops == pytest.approx(1.0, abs=1e-6)


def test_mismatched_working_spaces_are_rejected():
    reference = measure(frame((0.18, 0.18, 0.18)))
    candidate = measure(frame((0.18, 0.18, 0.18), working_space="ACEScct"))
    with pytest.raises(ColorMatchingError, match="same working space"):
        compare_color_regions(reference, candidate)


def test_unvalidated_or_missing_working_space_is_rejected():
    invalid = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"), values=(0.18, 0.18, 0.18),
        source_path="synthetic", decoder="test",
        encoding=ColorEncoding(transfer="linear", validated=True),
    )
    with pytest.raises(ColorMatchingError, match="working_space_id"):
        measure(invalid)


def test_singular_rgb_to_xyz_matrix_is_rejected():
    with pytest.raises(ColorMatchingError, match="invertible"):
        analyze_color_region(
            frame((0.18, 0.18, 0.18)), ROI,
            rgb_to_xyz_matrix=((1.0, 1.0, 1.0),) * 3,
            reference_white_xyz=WHITE, luminance_coefficients=COEFFS,
        )


def test_invalid_delta_e_threshold_is_rejected():
    stats = measure(frame((0.18, 0.18, 0.18)))
    with pytest.raises(ColorMatchingError, match="threshold"):
        compare_color_regions(stats, stats, delta_e_threshold=-1.0)
