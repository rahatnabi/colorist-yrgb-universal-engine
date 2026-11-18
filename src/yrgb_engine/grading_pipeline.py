"""Native, precision-preserving still-image grading pipeline.

This orchestration layer keeps camera input conversion, creative grading and
display preview as explicit stages. It never guesses source profiles and never
promotes a display preview to a validated mastering export.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .look import LookSettings, apply_look_to_frame
from .ocio import transform_frame
from .precision import PrecisionFrame
from .registry import ProfileRegistry
from .transform_validation import prepare_frame_for_working_space


class GradingPipelineError(ValueError):
    """Raised when a still cannot pass the requested grading pipeline stages."""


@dataclass(frozen=True, slots=True)
class StillGradingResult:
    """Precision frames at each stage; display output is preview-only."""

    working_frame: PrecisionFrame
    graded_frame: PrecisionFrame
    display_preview_frame: PrecisionFrame
    working_space_id: str
    display_space_id: str
    display_transfer: str


def process_validated_still(
    source_frame: PrecisionFrame,
    settings: LookSettings,
    *,
    registry: ProfileRegistry,
    config_path: str | Path,
    working_space_id: str,
    display_space_id: str,
    display_transfer: str,
    display_primaries: str,
) -> StillGradingResult:
    """Convert, grade and prepare one still for display using explicit spaces.

    Camera conversion is allowed only through the profile registry's
    independently reference-validated transform. The look is evaluated in the
    resulting validated scene-linear working space. The display transform is
    explicit but remains an unvalidated preview candidate: a display preview
    transform is not evidence for mastering/export certification.
    """
    required = (
        working_space_id,
        display_space_id,
        display_transfer,
        display_primaries,
    )
    if not all(isinstance(value, str) and value.strip() for value in required):
        raise GradingPipelineError(
            "Working space, display space, display transfer and display primaries are required."
        )

    try:
        working = prepare_frame_for_working_space(
            source_frame, registry=registry, config_path=config_path
        )
    except Exception as exc:
        raise GradingPipelineError(f"Camera input transform was not approved: {exc}") from exc

    if not working.encoding.validated:
        raise GradingPipelineError("Camera input transform did not produce validated output.")
    if working.encoding.transfer.casefold() not in {
        "linear", "linear-light", "scene-linear"
    }:
        raise GradingPipelineError(
            "The approved camera transform must output scene-linear RGB for this grading path."
        )
    if working.encoding.working_space_id != working_space_id:
        raise GradingPipelineError(
            "Approved camera transform destination does not match the selected working space."
        )

    try:
        graded = apply_look_to_frame(
            working, settings, input_space_id=working_space_id
        )
        display_candidate = transform_frame(
            graded,
            source_space=working_space_id,
            destination_space=display_space_id,
            config_path=config_path,
        )
    except Exception as exc:
        raise GradingPipelineError(f"Grading or display preview transform failed: {exc}") from exc

    preview_encoding = replace(
        display_candidate.encoding,
        primaries=display_primaries,
        transfer=display_transfer,
        profile_id=display_space_id,
        working_space_id=display_space_id,
        validated=False,
        metadata_source="explicit OCIO display transform; preview only",
        transform_id=f"preview:{working.encoding.transform_id or working_space_id}->{display_space_id}",
    )
    preview = PrecisionFrame(
        width=display_candidate.width,
        height=display_candidate.height,
        channel_names=display_candidate.channel_names,
        samples=display_candidate.samples,
        source_path=display_candidate.source_path,
        decoder=display_candidate.decoder,
        encoding=preview_encoding,
        sample_domain="unvalidated_display_preview_candidate",
        purpose="display_preview_only",
        metadata={
            **display_candidate.metadata,
            "yrgb_preview_only": True,
            "yrgb_mastering_export_allowed": False,
        },
    )
    return StillGradingResult(
        working_frame=working,
        graded_frame=graded,
        display_preview_frame=preview,
        working_space_id=working_space_id,
        display_space_id=display_space_id,
        display_transfer=display_transfer,
    )
