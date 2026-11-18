"""Reference-vector validation gate and registry-driven camera transforms."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Callable, Sequence

from .ocio import transform_frame
from .precision import PrecisionFrame
from .registry import ProfileRegistry


class TransformValidationError(ValueError):
    """Raised when a transform cannot be independently reference-validated."""


@dataclass(frozen=True, slots=True)
class ReferenceVector:
    source_rgb: tuple[float, float, float]
    expected_rgb: tuple[float, float, float]
    label: str


@dataclass(frozen=True, slots=True)
class TransformValidationResult:
    profile_id: str
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
            "profile_id": self.profile_id,
            "transform_id": self.transform_id,
            "source_space": self.source_space,
            "destination_space": self.destination_space,
        }


def validate_reference_vectors(
    *,
    profile_id: str,
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
    """Compare a transform with independently sourced reference RGB vectors.

    Passing synthetic fixtures verifies the validator mechanics only. Production
    profile approval requires independent, traceable camera/reference measurements.
    """
    path = Path(config_path)
    if not path.is_file():
        raise TransformValidationError("A readable, pinned OCIO config file is required.")
    identifiers = (profile_id, transform_id, source_space, destination_space, reference_set_id)
    if not all(isinstance(value, str) and value.strip() for value in identifiers):
        raise TransformValidationError("Profile, transform, color-space and reference-set identifiers are required.")
    if not isfinite(tolerance) or tolerance <= 0:
        raise TransformValidationError("Tolerance must be a finite positive value.")
    if not vectors:
        raise TransformValidationError("At least one independent reference vector is required.")

    errors: list[float] = []
    for vector in vectors:
        if (
            not isinstance(vector.label, str)
            or not vector.label.strip()
            or len(vector.source_rgb) != 3
            or len(vector.expected_rgb) != 3
        ):
            raise TransformValidationError("Each reference vector needs a label and three RGB values.")
        if not all(isfinite(value) for value in (*vector.source_rgb, *vector.expected_rgb)):
            raise TransformValidationError("Reference RGB values must be finite.")
        actual = evaluate_rgb(vector.source_rgb)
        if len(actual) != 3 or not all(isfinite(value) for value in actual):
            raise TransformValidationError("Transform evaluator returned invalid RGB values.")
        errors.extend(abs(actual[index] - vector.expected_rgb[index]) for index in range(3))

    maximum = max(errors)
    try:
        config_hash = sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TransformValidationError(f"Cannot read pinned OCIO config: {exc}") from exc
    return TransformValidationResult(
        profile_id=profile_id,
        transform_id=transform_id,
        source_space=source_space,
        destination_space=destination_space,
        config_sha256=config_hash,
        reference_set_id=reference_set_id,
        vector_count=len(vectors),
        max_absolute_error=maximum,
        tolerance=tolerance,
        passed=maximum <= tolerance,
        ocio_version=ocio_version,
    )


def validate_ocio_config(
    *,
    profile_id: str,
    transform_id: str,
    source_space: str,
    destination_space: str,
    config_path: str | Path,
    reference_set_id: str,
    vectors: Sequence[ReferenceVector],
    tolerance: float = 1e-5,
) -> TransformValidationResult:
    """Run a pinned OCIO transform against independent reference vectors."""
    try:
        import PyOpenColorIO as ocio

        config = ocio.Config.CreateFromFile(str(config_path))
        processor = config.getProcessor(source_space, destination_space)
        cpu = processor.getDefaultCPUProcessor()
    except Exception as exc:
        raise TransformValidationError(
            f"Cannot initialize the requested OCIO transform: {exc}"
        ) from exc

    def evaluate(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
        values = list(rgb)
        cpu.applyRGB(values)
        return tuple(float(value) for value in values)

    try:
        version = str(ocio.GetVersion())
    except Exception:
        version = "unknown"
    return validate_reference_vectors(
        profile_id=profile_id,
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


def _result_from_profile(profile: dict[str, object]) -> TransformValidationResult:
    validation = profile.get("validation")
    if not isinstance(validation, dict):
        raise TransformValidationError("Camera profile has no reference-validation evidence.")
    try:
        result = TransformValidationResult(
            profile_id=str(validation["profile_id"]),
            transform_id=str(validation["transform_id"]),
            source_space=str(validation["source_space"]),
            destination_space=str(validation["destination_space"]),
            config_sha256=str(validation["config_sha256"]),
            reference_set_id=str(validation["reference_set_id"]),
            vector_count=int(validation["vector_count"]),
            max_absolute_error=float(validation["max_absolute_error"]),
            tolerance=float(validation["tolerance"]),
            passed=validation["passed"] is True,
            ocio_version=str(validation.get("ocio_version", "unknown")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TransformValidationError("Camera profile validation evidence is incomplete.") from exc
    if (
        not result.passed
        or result.profile_id != profile.get("id")
        or result.transform_id != profile.get("transform_id")
        or result.source_space != profile.get("ocio_source_space")
        or result.destination_space != profile.get("ocio_destination_space")
        or result.vector_count <= 0
        or not isfinite(result.max_absolute_error)
        or result.max_absolute_error < 0
        or not isfinite(result.tolerance)
        or result.tolerance <= 0
        or result.max_absolute_error > result.tolerance
        or len(result.config_sha256) != 64
        or any(character not in "0123456789abcdef" for character in result.config_sha256.casefold())
    ):
        raise TransformValidationError("Camera profile and reference-validation evidence do not match or are invalid.")
    return result


def apply_reference_validated_transform(
    frame: PrecisionFrame,
    result: TransformValidationResult,
    *,
    source_space: str,
    destination_space: str,
    config_path: str | Path,
    output_transfer: str,
    profile_id: str,
    output_primaries: str,
) -> PrecisionFrame:
    """Apply only the exact profile/config/space tuple that passed validation."""
    if not result.passed:
        raise TransformValidationError("Reference vectors did not pass; transform remains unverified.")
    if (source_space, destination_space) != (result.source_space, result.destination_space):
        raise TransformValidationError("Requested spaces do not match the validated transform record.")
    if not all(isinstance(value, str) and value.strip() for value in (
        result.profile_id, result.transform_id, result.reference_set_id,
        output_transfer, output_primaries, profile_id,
    )):
        raise TransformValidationError("Complete profile, transform, and output encoding identities are required.")
    if result.profile_id != profile_id or frame.encoding.profile_id != profile_id:
        raise TransformValidationError("Frame, selected camera profile, and validation evidence must have the same profile ID.")
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
        primaries=output_primaries,
        transfer=output_transfer,
        profile_id=profile_id,
        working_space_id=destination_space,
        transform_id=result.transform_id,
        validated=True,
        metadata_source="OCIO transform with passing independent reference-vector validation",
    )
    metadata = dict(transformed.metadata)
    metadata["yrgb_transform_validation"] = {
        "profile_id": result.profile_id,
        "transform_id": result.transform_id,
        "source_space": result.source_space,
        "destination_space": result.destination_space,
        "reference_set_id": result.reference_set_id,
        "vector_count": result.vector_count,
        "max_absolute_error": result.max_absolute_error,
        "tolerance": result.tolerance,
        "config_sha256": result.config_sha256,
        "ocio_version": result.ocio_version,
    }
    return PrecisionFrame(
        width=transformed.width,
        height=transformed.height,
        channel_names=transformed.channel_names,
        samples=transformed.samples,
        source_path=transformed.source_path,
        decoder=f"{transformed.decoder}+reference-validation",
        encoding=encoding,
        sample_domain="reference_validated_ocio_float32",
        purpose="validated_working_space_candidate",
        metadata=metadata,
    )


def prepare_frame_for_working_space(
    frame: PrecisionFrame,
    *,
    registry: ProfileRegistry,
    config_path: str | Path,
) -> PrecisionFrame:
    """Resolve the frame's exact camera profile and apply its approved transform."""
    profile_id = frame.encoding.profile_id
    if not profile_id:
        raise TransformValidationError("Frame has no exact camera profile ID; automatic conversion is blocked.")
    profile = registry.get_by_id(profile_id)
    if profile is None:
        raise TransformValidationError(f"Camera profile '{profile_id}' is not present in the registry.")
    if not profile.get("usable_for_transform"):
        raise TransformValidationError("Selected camera profile is not reference-validated and cannot drive conversion.")
    result = _result_from_profile(profile)
    output_transfer = profile.get("output_transfer")
    output_primaries = profile.get("output_primaries")
    if not isinstance(output_transfer, str) or not isinstance(output_primaries, str):
        raise TransformValidationError("Approved profile must declare its output transfer and primaries.")
    return apply_reference_validated_transform(
        frame,
        result,
        source_space=str(profile["ocio_source_space"]),
        destination_space=str(profile["ocio_destination_space"]),
        config_path=config_path,
        output_transfer=output_transfer,
        output_primaries=output_primaries,
        profile_id=profile_id,
    )
