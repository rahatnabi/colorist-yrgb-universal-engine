"""Reference-vector validation gate for camera-to-working-space transforms.

An OCIO transform executing successfully is not evidence of colorimetric accuracy.
This module only marks a transform validated after explicit reference vectors pass.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Callable, Sequence

from .ocio import transform_frame
from .precision import PrecisionFrame


class TransformValidationError(ValueError):
    """Raised when a transform cannot be independently reference-validated."""


@dataclass(frozen=True, slots=True)
class ReferenceVector:
    source_rgb: tuple[float, float, float]
    expected_rgb: tuple[float, float, float]
    label: str


@dataclass(frozen=True, slots=True)
class TransformValidationResult:
    transform_id: str
    source_space: str
    destination_space: str
    config_sha256: str
    reference_set_id: str
    vector_count: int
    max_absolute_error: float
    tolerance: float
    passed: bool
    ocio_version: str

    def to_registry_record(self) -> dict[str, object]:
        """Return the auditable validation fields expected by ProfileRegistry."""
        return {
            "passed": self.passed,
            "config_sha256": self.config_sha256,
            "reference_set_id": self.reference_set_id,
            "vector_count": self.vector_count,
            "max_absolute_error": self.max_absolute_error,
            "tolerance": self.tolerance,
            "ocio_version": self.ocio_version,
            "source_space": self.source_space,
            "destination_space": self.destination_space,
            "transform_id": self.transform_id,
        }


def validate_reference_vectors(
    *,
    transform_id: str,
    source_space: str,
    destination_space: str,
    config_path: str | Path,
    reference_set_id: str,
    vectors: Sequence[ReferenceVector],
    evaluate_rgb: Callable[[tuple[float, float, float]], tuple[float, float, float]],
    tolerance: float = 1e-5,
    ocio_version: str = "unspecified",
) -> TransformValidationResult:
    """Compare transform output to independently sourced reference RGB vectors."""
    path = Path(config_path)
    if not path.is_file():
        raise TransformValidationError("A readable, pinned OCIO config file is required.")
    if not all(value.strip() for value in (transform_id, source_space, destination_space, reference_set_id)):
        raise TransformValidationError("Transform and reference-set identifiers are required.")
    if not isfinite(tolerance) or tolerance <= 0:
        raise TransformValidationError("Tolerance must be a finite positive value.")
    if not vectors:
        raise TransformValidationError("At least one independent reference vector is required.")

    errors: list[float] = []
    for vector in vectors:
        if not vector.label.strip() or len(vector.source_rgb) != 3 or len(vector.expected_rgb) != 3:
            raise TransformValidationError("Each reference vector needs a label and three RGB values.")
        if not all(isfinite(value) for value in (*vector.source_rgb, *vector.expected_rgb)):
            raise TransformValidationError("Reference RGB values must be finite.")
        actual = evaluate_rgb(vector.source_rgb)
        if len(actual) != 3 or not all(isfinite(value) for value in actual):
            raise TransformValidationError("Transform evaluator returned invalid RGB values.")
        errors.extend(abs(actual[i] - vector.expected_rgb[i]) for i in range(3))

    maximum = max(errors)
    return TransformValidationResult(
        transform_id=transform_id,
        source_space=source_space,
        destination_space=destination_space,
        config_sha256=sha256(path.read_bytes()).hexdigest(),
        reference_set_id=reference_set_id,
        vector_count=len(vectors),
        max_absolute_error=maximum,
        tolerance=tolerance,
        passed=maximum <= tolerance,
        ocio_version=ocio_version,
    )


def validate_ocio_config(
    *,
    transform_id: str,
    source_space: str,
    destination_space: str,
    config_path: str | Path,
    reference_set_id: str,
    vectors: Sequence[ReferenceVector],
    tolerance: float = 1e-5,
) -> TransformValidationResult:
    """Run reference vectors through an explicitly pinned OCIO config."""
    try:
        import PyOpenColorIO as ocio
        config = ocio.Config.CreateFromFile(str(config_path))
        processor = config.getProcessor(source_space, destination_space)
        cpu = processor.getDefaultCPUProcessor()
    except Exception as exc:
        raise TransformValidationError(f"Cannot initialize the requested OCIO transform: {exc}") from exc

    def evaluate(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
        values = list(rgb)
        cpu.applyRGB(values)
        return tuple(float(value) for value in values)

    try:
        version = str(ocio.GetVersion())
    except Exception:
        version = "unknown"
    return validate_reference_vectors(
        transform_id=transform_id,
        source_space=source_space,
        destination_space=destination_space,
        config_path=config_path,
        reference_set_id=reference_set_id,
        vectors=vectors,
        evaluate_rgb=evaluate,
        tolerance=tolerance,
        ocio_version=version,
    )


def apply_reference_validated_transform(
    frame: PrecisionFrame,
    result: TransformValidationResult,
    *,
    source_space: str,
    destination_space: str,
    config_path: str | Path,
    output_transfer: str,
) -> PrecisionFrame:
    """Apply only the exact config/transform pair that passed reference vectors."""
    if not result.passed:
        raise TransformValidationError("Reference vectors did not pass; transform remains unverified.")
    if (source_space, destination_space) != (result.source_space, result.destination_space):
        raise TransformValidationError("Requested spaces do not match the validated transform record.")
    if not output_transfer.strip():
        raise TransformValidationError("An explicit destination transfer function is required.")
    if frame.encoding.profile_id != source_space:
        raise TransformValidationError("Frame profile ID must exactly match the validated source space.")
    path = Path(config_path)
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != result.config_sha256:
        raise TransformValidationError("OCIO config hash differs from the validated config.")
    transformed = transform_frame(
        frame,
        source_space=source_space,
        destination_space=destination_space,
        config_path=path,
    )
    encoding = replace(
        transformed.encoding,
        transfer=output_transfer,
        working_space_id=destination_space,
        transform_id=result.transform_id,
        validated=True,
        metadata_source="OCIO transform with passing independent reference-vector validation",
    )
    metadata = dict(transformed.metadata)
    metadata.update({
        "yrgb_transform_validation": {
            "reference_set_id": result.reference_set_id,
            "vector_count": result.vector_count,
            "max_absolute_error": result.max_absolute_error,
            "tolerance": result.tolerance,
            "config_sha256": result.config_sha256,
            "ocio_version": result.ocio_version,
        }
    })
    return PrecisionFrame(
        width=transformed.width,
        height=transformed.height,
        channel_names=transformed.channel_names,
        samples=transformed.samples,
        source_path=transformed.source_path,
        decoder=transformed.decoder,
        encoding=encoding,
        sample_domain="reference_validated_ocio_float32",
        purpose="validated_working_space_candidate",
        metadata=metadata,
    )
