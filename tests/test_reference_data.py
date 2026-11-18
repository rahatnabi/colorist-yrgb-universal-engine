import json

import pytest

from yrgb_engine.reference_data import (
    ReferenceManifestError,
    load_reference_manifest,
    validate_reference_manifest,
)
from yrgb_engine.registry import ProfileRegistry
from yrgb_engine.transform_validation import TransformValidationResult


def _registry():
    return ProfileRegistry([{
        "id": "sony.slog3.sgamut3cine",
        "manufacturer": "Sony",
        "encoding": "S-Log3",
        "gamut": "S-Gamut3.Cine",
        "status": "unverified",
        "transform_id": "sony.slog3.to.dwg",
        "ocio_source_space": "S-Log3 S-Gamut3.Cine",
        "ocio_destination_space": "DaVinci Intermediate WideGamut",
    }])


def _manifest():
    return {
        "schema_version": 1,
        "profile_id": "sony.slog3.sgamut3cine",
        "transform_id": "sony.slog3.to.dwg",
        "source_space": "S-Log3 S-Gamut3.Cine",
        "destination_space": "DaVinci Intermediate WideGamut",
        "reference_set_id": "sony-independent-chart-v1",
        "reference_source": "Independent measured chart dataset, accession REF-001",
        "measurement_method": "Documented camera capture and spectrophotometer workflow",
        "vectors": [{
            "label": "neutral-patch-18",
            "source_rgb": [0.4, 0.4, 0.4],
            "expected_rgb": [0.18, 0.18, 0.18],
        }],
    }


def test_manifest_loads_traceable_reference_vectors(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(_manifest()))
    loaded = load_reference_manifest(path)
    assert loaded["reference_set_id"] == "sony-independent-chart-v1"
    assert loaded["vectors"][0]["source_rgb"] == (0.4, 0.4, 0.4)


def test_empty_template_cannot_validate_transform(tmp_path):
    manifest = _manifest()
    manifest["vectors"] = []
    path = tmp_path / "template.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ReferenceManifestError, match="empty template"):
        load_reference_manifest(path)


def test_manifest_requires_reference_provenance(tmp_path):
    manifest = _manifest()
    manifest["reference_source"] = ""
    path = tmp_path / "missing-provenance.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ReferenceManifestError, match="reference_source"):
        load_reference_manifest(path)


def test_manifest_rejects_non_finite_rgb_values(tmp_path):
    manifest = _manifest()
    manifest["vectors"][0]["source_rgb"][0] = float("nan")
    path = tmp_path / "nan.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ReferenceManifestError, match="finite"):
        load_reference_manifest(path)


def test_manifest_must_match_exact_registry_transform_mapping(tmp_path):
    manifest = _manifest()
    manifest["source_space"] = "S-Log3 S-Gamut3"
    path = tmp_path / "wrong-space.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ReferenceManifestError, match="source_space"):
        validate_reference_manifest(path, config_path=tmp_path / "config.ocio", registry=_registry())


def test_manifest_runs_pinned_ocio_validation_and_returns_audit(tmp_path, monkeypatch):
    manifest_path = tmp_path / "reference.json"
    manifest_path.write_text(json.dumps(_manifest()))
    config = tmp_path / "studio.ocio"
    config.write_text("pinned config fixture")
    captured = {}

    def fake_validate(**kwargs):
        captured.update(kwargs)
        return TransformValidationResult(
            profile_id=kwargs["profile_id"],
            transform_id=kwargs["transform_id"],
            source_space=kwargs["source_space"],
            destination_space=kwargs["destination_space"],
            config_sha256="a" * 64,
            reference_set_id=kwargs["reference_set_id"],
            vector_count=len(kwargs["vectors"]),
            max_absolute_error=0.000001,
            tolerance=kwargs["tolerance"],
            passed=True,
            ocio_version="test",
        )

    monkeypatch.setattr("yrgb_engine.reference_data.validate_ocio_config", fake_validate)
    result = validate_reference_manifest(
        manifest_path, config_path=config, registry=_registry(), tolerance=0.0001
    )
    assert result.passed is True
    assert captured["source_space"] == "S-Log3 S-Gamut3.Cine"
    assert captured["vectors"][0].label == "neutral-patch-18"
    assert captured["tolerance"] == 0.0001
