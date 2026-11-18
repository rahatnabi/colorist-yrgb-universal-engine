"""Conservative matching of reported capture metadata to camera profiles."""
from __future__ import annotations

from typing import Any

from .registry import ProfileRegistry


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _find_tag(tags: Any, *names: str) -> str | None:
    if not isinstance(tags, dict):
        return None
    folded = {str(key).casefold(): value for key, value in tags.items()}
    for name in names:
        value = _text(folded.get(name.casefold()))
        if value:
            return value
    return None


def match_capture_profile(
    capture_metadata: dict[str, Any],
    registry: ProfileRegistry,
) -> dict[str, Any]:
    """Return candidates and a fail-closed status; never infer a missing gamut.

    Only explicit capture metadata is used. FFprobe's BT.2020 primaries are not
    treated as proof of Sony S-Gamut3 or S-Gamut3.Cine.
    """
    if not isinstance(capture_metadata, dict):
        raise TypeError("capture_metadata must be an object")

    tags = capture_metadata.get("metadata_tags", {})
    make = _text(capture_metadata.get("camera_make")) or _find_tag(
        tags, "make", "manufacturer", "camera_make"
    )
    model = _text(capture_metadata.get("camera_model")) or _find_tag(
        tags, "model", "camera_model"
    )
    transfer = _text(capture_metadata.get("color_transfer")) or _find_tag(
        tags, "transfer", "gamma", "log_curve", "camera_gamma"
    )
    gamut = _text(capture_metadata.get("camera_gamut")) or _find_tag(
        tags, "camera_gamut", "gamut", "color_gamut", "colour_gamut"
    )

    if not make:
        return {
            "status": "needs_camera_make",
            "selection_made": False,
            "camera_make": None,
            "camera_model": model,
            "encoding": transfer,
            "gamut": gamut,
            "candidates": [],
            "note": "Camera manufacturer is absent from explicit metadata.",
        }

    candidates = registry.find_candidates(
        manufacturer=make,
        encoding=transfer,
        gamut=gamut,
        camera_model=model,
    )
    if not candidates:
        return {
            "status": "no_exact_candidate",
            "selection_made": False,
            "camera_make": make,
            "camera_model": model,
            "encoding": transfer,
            "gamut": gamut,
            "candidates": [],
            "note": "No exact registry candidate matches the reported metadata. No profile was guessed.",
        }

    requirements = sorted({
        requirement
        for candidate in candidates
        for requirement in candidate.get("selection_requirements", [])
    })
    if "camera_model" in requirements:
        status = "needs_camera_model"
    elif "gamut_choice" in requirements:
        status = "needs_gamut_confirmation"
    elif any(candidate.get("usable_for_transform") for candidate in candidates):
        status = "reference_validated_candidate"
    else:
        status = "candidate_unvalidated"

    return {
        "status": status,
        "selection_made": False,
        "camera_make": make,
        "camera_model": model,
        "encoding": transfer,
        "gamut": gamut,
        "candidates": candidates,
        "note": (
            "Candidate discovery is not transform approval. Only a profile with "
            "independent passing reference validation can be used for conversion."
        ),
    }
