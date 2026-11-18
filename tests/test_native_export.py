import pytest

from yrgb_engine.native_export import (
    NativeExportError,
    native_frame_sha256,
    validate_native_export_frame,
)
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def make_grade(**overrides):
    values = {
        "width": 2,
        "height": 1,
        "channel_names": ("R", "G", "B"),
        "values": (-0.25, 0.18, 1.5, 2.0, 0.5, 0.0),
        "source_path": "fixture.exr",
        "decoder": "test",
        "encoding": ColorEncoding(
            primaries="DaVinci Wide Gamut",
            transfer="Linear",
            profile_id="test.camera.profile",
            validated=True,
            working_space_id="Linear DaVinci WideGamut",
            transform_id="test.camera.to.linear",
        ),
        "sample_domain": "validated_linear_native_grade_float32",
        "purpose": "graded_still_candidate",
    }
    values.update(overrides)
    return PrecisionFrame.from_interleaved(**values)


def test_native_export_accepts_validated_linear_rgb_and_preserves_hdr_domain_hash():
    frame = make_grade()
    validate_native_export_frame(frame)
    digest = native_frame_sha256(frame)
    assert len(digest) == 64
    assert frame.pixel(0, 0) == pytest.approx((-0.25, 0.18, 1.5))
    assert frame.pixel(1, 0) == pytest.approx((2.0, 0.5, 0.0))


def test_native_export_rejects_unvalidated_transform():
    frame = make_grade(encoding=ColorEncoding(
        primaries="DaVinci Wide Gamut", transfer="Linear",
        working_space_id="Linear DaVinci WideGamut",
        transform_id="unvalidated.transform", validated=False,
    ))
    with pytest.raises(NativeExportError, match="reference-validated"):
        validate_native_export_frame(frame)


def test_native_export_rejects_non_linear_working_data():
    frame = make_grade(encoding=ColorEncoding(
        primaries="DaVinci Wide Gamut", transfer="DaVinci Intermediate",
        working_space_id="DaVinci WideGamut/Intermediate",
        transform_id="test.encoded", validated=True,
    ))
    with pytest.raises(NativeExportError, match="scene-linear"):
        validate_native_export_frame(frame)


def test_native_export_requires_named_rgb_channels():
    frame = make_grade(
        channel_names=("Y", "Cb", "Cr"),
        values=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
    )
    with pytest.raises(NativeExportError, match="named R, G and B"):
        validate_native_export_frame(frame)


def test_native_export_requires_graded_still_purpose():
    frame = make_grade(purpose="display_preview_only")
    with pytest.raises(NativeExportError, match="graded still"):
        validate_native_export_frame(frame)
