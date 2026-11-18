"""Traceable reference-vector manifests for real camera transform validation."""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any

from .registry import ProfileRegistry
from .transform_validation import (
    ReferenceVector,
    TransformValidationError,
    TransformValidationResult,
    validate_ocio_config,
)


class ReferenceManifestError(ValueError):
    """Raised when a reference-vector manifest is incomplete or inconsistent."""


def _finite_rgb(value: Any, field: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ReferenceManifestError(f"{field} must contain exactly three numeric RGB values.")
    if any(
        isinstance(channel, bool)
        or not isinstance(channel, (int, float))
        or not isfinite(channel)
        for channel in value
    ):
        raise ReferenceManifestError(f"{field} values must be finite numbers.")
    return tuple(float(channel) for channel in value)


def load_reference_manifest(path: str | Path) -> dict[str, Any]:
    """Load a JSON manifest and reject missing provenance or synthetic empty sets."""
    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Invalid JSON numeric constant: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ReferenceManifestError(f"Cannot load reference manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ReferenceManifestError("Reference manifest must be an object with schema_version 1.")

    required_text = (
        "profile_id", "transform_id", "source_space", "destination_space",
        "reference_set_id", "reference_source", "measurement_method",
    )
    for field in required_text:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ReferenceManifestError(f"Reference manifest requires non-empty {field}.")

    raw_vectors = payload.get("vectors")
    if not isinstance(raw_vectors, list) or not raw_vectors:
        raise ReferenceManifestError(
            "Reference manifest needs measured vectors; an empty template cannot validate a transform."
        )
    vectors: list[dict[str, Any]] = []
    for index, item in enumerate(raw_vectors):
        if not isinstance(item, dict):
            raise ReferenceManifestError(f"Vector {index} must be an object.")
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ReferenceManifestError(f"Vector {index} requires a label.")
        vectors.append({
            "label": label,
            "source_rgb": _finite_rgb(item.get("source_rgb"), f"vectors[{index}].source_rgb"),
            "expected_rgb": _finite_rgb(item.get("expected_rgb"), f"vectors[{index}].expected_rgb"),
        })
    payload["vectors"] = vectors
    return payload


def validate_reference_manifest(
    manifest_path: str | Path,
    *,
    config_path: str | Path,
    registry: ProfileRegistry,
    tolerance: float = 1e-5,
) -> TransformValidationResult:
    """Validate a traceable manifest against the exact candidate registry mapping."""
    manifest = load_reference_manifest(manifest_path)
    profile = registry.get_by_id(manifest["profile_id"])
    if profile is None:
        raise ReferenceManifestError("Manifest profile_id is not present in the camera registry.")
    if profile.get("status") == "deprecated":
        raise ReferenceManifestError("Deprecated camera profiles cannot be validated for production use.")
    expected = {
        "transform_id": profile.get("transform_id"),
        "source_space": profile.get("ocio_source_space"),
        "destination_space": profile.get("ocio_destination_space"),
    }
    for field, value in expected.items():
        if not value or manifest[field] != value:
            raise ReferenceManifestError(
                f"Manifest {field} does not exactly match the selected registry candidate."
            )

    vectors = tuple(
        ReferenceVector(
            source_rgb=item["source_rgb"],
            expected_rgb=item["expected_rgb"],
            label=item["label"],
        )
        for item in manifest["vectors"]
    )
    try:
        return validate_ocio_config(
            profile_id=manifest["profile_id"],
            transform_id=manifest["transform_id"],
            source_space=manifest["source_space"],
            destination_space=manifest["destination_space"],
            config_path=config_path,
            reference_set_id=manifest["reference_set_id"],
            vectors=vectors,
            tolerance=tolerance,
        )
    except TransformValidationError as exc:
        raise ReferenceManifestError(str(exc)) from exc
