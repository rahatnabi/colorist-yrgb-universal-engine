"""Verify provenance metadata for pinned upstream GitHub resources."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/fetch_aces_config.py"
SPEC = importlib.util.spec_from_file_location("fetch_aces_config", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
FETCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FETCH_MODULE)
ASSETS = FETCH_MODULE.ASSETS

ROOT = Path(__file__).resolve().parents[1]


def test_github_resource_manifest_has_pinned_aces_configs() -> None:
    manifest = json.loads(
        (ROOT / "data/reference_sources/github_resources.json").read_text()
    )
    resources = {item["id"]: item for item in manifest["resources"]}

    for variant, resource_id in (
        ("studio", "aces-ocio-v4-studio"),
        ("studio-all-views", "aces-ocio-v4-studio-all-views"),
        ("reference", "aces-ocio-v4-reference"),
    ):
        url, digest = ASSETS[variant]
        record = resources[resource_id]
        assert record["url"] == url
        assert record["sha256"] == digest
        assert len(digest) == 64
        assert record["size_bytes"] > 0
        assert "not camera reference validation" in record["validation_scope"].lower()


def test_sony_transform_source_is_not_camera_validation() -> None:
    manifest = json.loads(
        (ROOT / "data/reference_sources/github_resources.json").read_text()
    )
    record = next(
        item for item in manifest["resources"]
        if item["id"] == "ocio-sony-camera-transform-source"
    )
    assert record["license"] == "BSD-3-Clause"
    assert "not manufacturer-published" in record["validation_scope"]


def test_clf_fixture_is_not_mislabeled_as_camera_reference() -> None:
    manifest = json.loads(
        (ROOT / "data/reference_sources/github_resources.json").read_text()
    )
    record = next(
        item for item in manifest["resources"]
        if item["id"] == "ocio-clf-test-image"
    )
    assert record["kind"] == "software-conformance-fixture"
    assert "not camera footage" in record["validation_scope"]
    assert "not separately confirmed" in record["license"]
