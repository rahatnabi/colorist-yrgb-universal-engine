
import pytest

from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.transform_validation import (
    ReferenceVector,
    TransformValidationError,
    apply_reference_validated_transform,
    validate_reference_vectors,
)


def _vectors():
    return (
        ReferenceVector((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), "black"),
        ReferenceVector((0.18, 0.18, 0.18), (0.18, 0.18, 0.18), "middle gray"),
        ReferenceVector((1.0, 0.5, 0.25), (1.0, 0.5, 0.25), "neutral test patch"),
    )


def test_reference_vectors_pass_and_pin_config_hash(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("ocio-config-fixture")
    result = validate_reference_vectors(
        transform_id="test.identity",
        source_space="CameraLog",
        destination_space="LinearWorking",
        config_path=config,
        reference_set_id="fixture-v1",
        vectors=_vectors(),
        evaluate_rgb=lambda rgb: rgb,
    )
    assert result.passed is True
    assert result.vector_count == 3
    assert result.max_absolute_error == 0


def test_reference_vectors_fail_outside_tolerance(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("ocio-config-fixture")
    result = validate_reference_vectors(
        transform_id="test.offset",
        source_space="CameraLog",
        destination_space="LinearWorking",
        config_path=config,
        reference_set_id="fixture-v1",
        vectors=_vectors(),
        evaluate_rgb=lambda rgb: (rgb[0] + 0.01, rgb[1], rgb[2]),
        tolerance=1e-4,
    )
    assert result.passed is False
    assert result.max_absolute_error == pytest.approx(0.01)


def test_reference_validation_requires_config_and_vectors(tmp_path):
    with pytest.raises(TransformValidationError, match="config"):
        validate_reference_vectors(
            transform_id="x", source_space="a", destination_space="b",
            config_path=tmp_path / "missing.ocio", reference_set_id="r",
            vectors=_vectors(), evaluate_rgb=lambda rgb: rgb,
        )


def test_apply_rejects_failed_validation_and_config_hash_mismatch(tmp_path, monkeypatch):
    config = tmp_path / "config.ocio"
    config.write_text("config-v1")
    failed = validate_reference_vectors(
        transform_id="test.transform", source_space="CameraLog",
        destination_space="DWG-Linear", config_path=config, reference_set_id="bad",
        vectors=_vectors(), evaluate_rgb=lambda rgb: (rgb[0] + 0.1, rgb[1], rgb[2]),
    )
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.1, 0.2, 0.3), source_path="fixture", decoder="test",
        encoding=ColorEncoding(profile_id="test.camera.profile"),
    )
    with pytest.raises(TransformValidationError, match="did not pass"):
        apply_reference_validated_transform(
            frame, failed, source_space="CameraLog", destination_space="DWG-Linear",
            config_path=config, output_transfer="linear", profile_id="test.camera.profile",
        )
    passed = validate_reference_vectors(
        transform_id="test.transform", source_space="CameraLog",
        destination_space="DWG-Linear", config_path=config, reference_set_id="good",
        vectors=_vectors(), evaluate_rgb=lambda rgb: rgb,
    )
    config.write_text("config-v2")
    with pytest.raises(TransformValidationError, match="hash"):
        apply_reference_validated_transform(
            frame, passed, source_space="CameraLog", destination_space="DWG-Linear",
            config_path=config, output_transfer="linear", profile_id="test.camera.profile",
        )


def test_apply_marks_frame_validated_only_after_matching_reference_record(tmp_path, monkeypatch):
    config = tmp_path / "config.ocio"
    config.write_text("config-v1")
    result = validate_reference_vectors(
        transform_id="camera-to-dwg",
        source_space="CameraLog",
        destination_space="DWG-Linear",
        config_path=config,
        reference_set_id="vendor-patches-v1",
        vectors=_vectors(),
        evaluate_rgb=lambda rgb: rgb,
    )
    frame = PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.1, 0.2, 0.3), source_path="fixture", decoder="test",
        encoding=ColorEncoding(profile_id="CameraLog"),
    )
    monkeypatch.setattr(
        "yrgb_engine.transform_validation.transform_frame",
        lambda source, **_kwargs: source,
    )
    transformed = apply_reference_validated_transform(
        frame, result, source_space="CameraLog", destination_space="DWG-Linear",
        config_path=config, output_transfer="linear", profile_id="test.camera.profile",
    )
    assert transformed.encoding.validated is True
    assert transformed.encoding.working_space_id == "DWG-Linear"
    assert transformed.encoding.transform_id == "camera-to-dwg"
    assert transformed.metadata["yrgb_transform_validation"]["reference_set_id"] == "vendor-patches-v1"


def test_validation_result_exports_registry_audit_record(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("ocio-config-fixture")
    result = validate_reference_vectors(
        transform_id="test.camera-to-working",
        source_space="CameraLog",
        destination_space="DWG-Linear",
        config_path=config,
        reference_set_id="independent-chart-v2",
        vectors=_vectors(),
        evaluate_rgb=lambda rgb: rgb,
    )
    record = result.to_registry_record()
    assert record["passed"] is True
    assert record["transform_id"] == "test.camera-to-working"
    assert record["reference_set_id"] == "independent-chart-v2"
    assert len(record["config_sha256"]) == 64
