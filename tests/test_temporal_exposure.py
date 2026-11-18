import pytest

from yrgb_engine.exposure import PixelRegion
from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.temporal_exposure import (
    TemporalExposureError,
    iter_temporal_exposure,
)


COEFFS = (0.2126, 0.7152, 0.0722)
ROI = PixelRegion(0, 0, 1, 1)


def make_frame(value, *, working_space_id="DWG/Intermediate", transform_id="camera-a"):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(value, value, value), source_path="synthetic", decoder="test",
        encoding=ColorEncoding(
            primaries="rec709", transfer="linear", validated=True,
            working_space_id=working_space_id, transform_id=transform_id,
        ),
    )


def analyze(values, **kwargs):
    frames = [(index / 24, make_frame(value)) for index, value in enumerate(values)]
    return list(iter_temporal_exposure(
        frames, region=ROI, luminance_coefficients=COEFFS, **kwargs
    ))


def test_stable_sequence_has_zero_temporal_drift():
    reports = analyze([0.18, 0.18, 0.18])
    assert [item.drift_from_shot_reference_stops for item in reports] == pytest.approx(
        [0.0, 0.0, 0.0], abs=1e-6
    )
    assert reports[1].delta_from_previous_stops == pytest.approx(0.0, abs=1e-6)


def test_exposure_ramp_reports_one_stop_drift():
    reports = analyze([0.18, 0.36, 0.72])
    assert reports[1].delta_from_previous_stops == pytest.approx(1.0, abs=1e-6)
    assert reports[2].drift_from_shot_reference_stops == pytest.approx(2.0, abs=1e-6)


def test_confirmed_shot_boundary_resets_reference_and_delta():
    reports = analyze([0.18, 0.36, 0.72], shot_boundary_indices={2})
    assert reports[1].drift_from_shot_reference_stops == pytest.approx(1.0, abs=1e-6)
    assert reports[2].shot_index == 1
    assert reports[2].shot_reference_reset is True
    assert reports[2].delta_from_previous_stops is None
    assert reports[2].drift_from_shot_reference_stops == pytest.approx(0.0, abs=1e-6)


def test_camera_specific_transform_ids_can_share_same_working_space():
    frames = [
        (0.0, make_frame(0.18, transform_id="sony-slog3-to-dwg")),
        (1.0, make_frame(0.18, transform_id="arri-logc4-to-dwg")),
    ]
    reports = list(iter_temporal_exposure(
        frames, region=ROI, luminance_coefficients=COEFFS
    ))
    assert reports[1].delta_from_previous_stops == pytest.approx(0.0, abs=1e-6)


def test_mismatched_working_space_is_rejected():
    frames = [
        (0.0, make_frame(0.18)),
        (1.0, make_frame(0.18, working_space_id="ACEScct")),
    ]
    iterator = iter_temporal_exposure(frames, region=ROI, luminance_coefficients=COEFFS)
    next(iterator)
    with pytest.raises(TemporalExposureError, match="same validated destination"):
        next(iterator)


def test_missing_working_space_identity_is_rejected():
    frame = make_frame(0.18, working_space_id=None)
    with pytest.raises(TemporalExposureError, match="working_space_id"):
        next(iter_temporal_exposure(
            [(0.0, frame)], region=ROI, luminance_coefficients=COEFFS
        ))


def test_non_monotonic_timestamps_are_rejected():
    frames = [(1.0, make_frame(0.18)), (1.0, make_frame(0.18))]
    iterator = iter_temporal_exposure(frames, region=ROI, luminance_coefficients=COEFFS)
    next(iterator)
    with pytest.raises(TemporalExposureError, match="strictly increasing"):
        next(iterator)


def test_negative_boundary_index_is_rejected():
    with pytest.raises(TemporalExposureError, match="non-negative"):
        next(iter_temporal_exposure(
            [(0.0, make_frame(0.18))], region=ROI,
            luminance_coefficients=COEFFS, shot_boundary_indices={-1},
        ))
