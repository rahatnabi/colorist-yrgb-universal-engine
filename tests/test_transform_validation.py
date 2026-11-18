import pytest

from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.registry import ProfileRegistry
from yrgb_engine.transform_validation import (
    ReferenceVector,
    TransformValidationError,
    apply_reference_validated_transform,
    prepare_frame_for_working_space,
    validate_reference_vectors,
)


def _vectors():
    return (
        ReferenceVector((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), "black"),
        ReferenceVector((0.18, 0.18, 0.18), (0.18, 0.18, 0.18), "middle gray"),
        ReferenceVector((1.0, 0.5, 0.25), (1.0, 0.5, 0.25), "test patch"),
    )


def _validate(config, **overrides):
    args = {
        "profile_id": "test.camera.profile",
        "transform_id": "test.camera.to.working",
        "source_space": "OCIO Camera Log",
        "destination_space": "Linear DaVinci WideGamut",
        "config_path": config,
        "reference_set_id": "independent-fixture-v1",
        "vectors": _vectors(),
        "evaluate_rgb": lambda rgb: rgb,
    }
    args.update(overrides)
    return validate_reference_vectors(**args)


def _frame(profile_id="test.camera.profile"):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B"),
        values=(0.1, 0.2, 0.3), source_path="fixture", decoder="test",
        encoding=ColorEncoding(profile_id=profile_id),
    )


def test_reference_vectors_pass_and_pin_config_hash(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("ocio-config-fixture")
    result = _validate(config)
    assert result.passed is True
    assert result.vector_count == 3
    assert result.max_absolute_error == 0
    assert len(result.config_sha256) == 64


def test_reference_vectors_fail_outside_tolerance(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("ocio-config-fixture")
    result = _validate(
        config,
        evaluate_rgb=lambda rgb: (rgb[0] + 0.01, rgb[1], rgb[2]),
        tolerance=1e-4,
    )
    assert result.passed is False
    assert result.max_absolute_error == pytest.approx(0.01)


def test_reference_validation_requires_config_vectors_and_profile_id(tmp_path):
    with pytest.raises(TransformValidationError, match="config"):
        _validate(tmp_path / "missing.ocio")
    config = tmp_path / "config.ocio"
    config.write_text("fixture")
    with pytest.raises(TransformValidationError, match="identifiers"):
        _validate(config, profile_id="")


def test_apply_rejects_failed_validation_and_config_hash_mismatch(tmp_path, monkeypatch):
    config = tmp_path / "config.ocio"
    config.write_text("config-v1")
    failed = _validate(
        config,
        evaluate_rgb=lambda rgb: (rgb[0] + 0.1, rgb[1], rgb[2]),
    )
    kwargs = dict(
        source_space="OCIO Camera Log",
        destination_space="Linear DaVinci WideGamut",
        config_path=config,
        output_transfer="Linear",
        output_primaries="Linear DaVinci WideGamut",
        profile_id="test.camera.profile",
    )
    with pytest.raises(TransformValidationError, match="did not pass"):
        apply_reference_validated_transform(_frame(), failed, **kwargs)
    passed = _validate(config)
    config.write_text("config-v2")
    with pytest.raises(TransformValidationError, match="hash"):
        apply_reference_validated_transform(_frame(), passed, **kwargs)


def test_apply_marks_frame_validated_only_after_matching_evidence(tmp_path, monkeypatch):
    config = tmp_path / "config.ocio"
    config.write_text("config-v1")
    result = _validate(config)
    monkeypatch.setattr(
        "yrgb_engine.transform_validation.transform_frame",
        lambda source, **_kwargs: source,
    )
    transformed = apply_reference_validated_transform(
        _frame(), result,
        source_space="OCIO Camera Log",
        destination_space="Linear DaVinci WideGamut",
        config_path=config,
        output_transfer="Linear",
        output_primaries="Linear DaVinci WideGamut",
        profile_id="test.camera.profile",
    )
    assert transformed.encoding.validated is True
    assert transformed.encoding.working_space_id == "Linear DaVinci WideGamut"
    assert transformed.encoding.transfer == "Linear"
    assert transformed.encoding.primaries == "Linear DaVinci WideGamut"
    assert transformed.encoding.transform_id == "test.camera.to.working"
    assert transformed.metadata["yrgb_transform_validation"]["reference_set_id"] == "independent-fixture-v1"


def test_apply_rejects_mismatched_camera_registry_profile(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("config-v1")
    result = _validate(config)
    with pytest.raises(TransformValidationError, match="same profile ID"):
        apply_reference_validated_transform(
            _frame("sony.slog3.sgamut3cine"), result,
            source_space="OCIO Camera Log",
            destination_space="Linear DaVinci WideGamut",
            config_path=config,
            output_transfer="Linear",
            output_primaries="Linear DaVinci WideGamut",
            profile_id="canon.clog3.cinema_gamut",
        )


def test_validation_result_exports_complete_registry_audit_record(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("fixture")
    record = _validate(config).to_registry_record()
    assert record["passed"] is True
    assert record["profile_id"] == "test.camera.profile"
    assert record["transform_id"] == "test.camera.to.working"
    assert record["reference_set_id"] == "independent-fixture-v1"
    assert record["source_space"] == "OCIO Camera Log"


def test_registry_pipeline_blocks_unverified_camera_profile(tmp_path):
    registry = ProfileRegistry([{
        "id": "test.camera.profile",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "status": "unverified",
        "transform_id": None,
    }])
    with pytest.raises(TransformValidationError, match="not reference-validated"):
        prepare_frame_for_working_space(
            _frame(), registry=registry, config_path=tmp_path / "missing.ocio"
        )


def test_registry_pipeline_requires_frame_profile_identity(tmp_path):
    registry = ProfileRegistry([])
    with pytest.raises(TransformValidationError, match="no exact camera profile"):
        prepare_frame_for_working_space(
            _frame(None), registry=registry, config_path=tmp_path / "missing.ocio"
        )


def test_registry_driven_prepare_applies_only_complete_approved_profile(tmp_path, monkeypatch):
    config = tmp_path / "config.ocio"
    config.write_text("pinned-config")
    validation = _validate(config).to_registry_record()
    profile = {
        "id": "test.camera.profile",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "camera_models": [],
        "status": "verified",
        "transform_id": "test.camera.to.working",
        "ocio_source_space": "OCIO Camera Log",
        "ocio_destination_space": "Linear DaVinci WideGamut",
        "output_transfer": "Linear",
        "output_primaries": "Linear DaVinci WideGamut",
        "validation": validation,
    }
    registry = ProfileRegistry([profile])
    monkeypatch.setattr(
        "yrgb_engine.transform_validation.transform_frame",
        lambda source, **_kwargs: source,
    )
    prepared = prepare_frame_for_working_space(
        _frame(), registry=registry, config_path=config
    )
    assert prepared.encoding.validated is True
    assert prepared.encoding.working_space_id == "Linear DaVinci WideGamut"
    assert prepared.encoding.transfer == "Linear"


def test_registry_driven_prepare_rejects_profile_evidence_from_other_config(tmp_path):
    config = tmp_path / "config.ocio"
    config.write_text("current-config")
    other_config = tmp_path / "other.ocio"
    other_config.write_text("different-config")
    validation = _validate(other_config).to_registry_record()
    profile = {
        "id": "test.camera.profile",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "camera_models": [],
        "status": "verified",
        "transform_id": "test.camera.to.working",
        "ocio_source_space": "OCIO Camera Log",
        "ocio_destination_space": "Linear DaVinci WideGamut",
        "output_transfer": "Linear",
        "output_primaries": "Linear DaVinci WideGamut",
        "validation": validation,
    }
    registry = ProfileRegistry([profile])
    with pytest.raises(TransformValidationError, match="hash"):
        prepare_frame_for_working_space(
            _frame(), registry=registry, config_path=config
        )
