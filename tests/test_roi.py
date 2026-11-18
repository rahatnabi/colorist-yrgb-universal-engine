from array import array

import pytest

from yrgb_engine.precision import PrecisionFrame
from yrgb_engine.roi import ROIAnalysisError, measure_normalized_rgb_roi


def frame():
    # 2x2 RGB pixels: (1,2,3), (3,4,5), (5,6,7), (7,8,9)
    return PrecisionFrame.from_interleaved(
        width=2, height=2, channel_names=("R", "G", "B"),
        values=array("f", [1,2,3, 3,4,5, 5,6,7, 7,8,9]),
        source_path="memory", decoder="test", sample_domain="test-decoder-domain",
    )


def test_full_frame_roi_reports_channel_means_and_pixel_count():
    result = measure_normalized_rgb_roi(frame(), x=0, y=0, width=1, height=1)
    assert result["pixel_count"] == 4
    assert result["channels"]["R"]["mean"] == pytest.approx(4)
    assert result["channels"]["G"]["mean"] == pytest.approx(5)
    assert result["channels"]["B"]["mean"] == pytest.approx(6)
    assert result["measurement_domain"] == "test-decoder-domain"


def test_single_pixel_roi_uses_valid_pixel_bounds():
    result = measure_normalized_rgb_roi(frame(), x=0, y=0, width=0.5, height=0.5)
    assert result["pixel_count"] == 1
    assert result["channels"]["R"]["mean"] == pytest.approx(1)


@pytest.mark.parametrize("geometry", [
    (-0.1, 0, 0.5, 0.5), (0, 0, 0, 0.5), (0.8, 0.8, 0.3, 0.3),
])
def test_invalid_geometry_is_rejected(geometry):
    with pytest.raises(ROIAnalysisError):
        measure_normalized_rgb_roi(frame(), x=geometry[0], y=geometry[1], width=geometry[2], height=geometry[3])


def test_non_rgb_frame_is_rejected():
    gray = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("Y",), values=array("f", [0.5]),
        source_path="memory", decoder="test",
    )
    with pytest.raises(ROIAnalysisError, match="R, G, and B"):
        measure_normalized_rgb_roi(gray, x=0, y=0, width=1, height=1)
