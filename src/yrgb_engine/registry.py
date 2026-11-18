"""Explicit camera profile registry lookup.

Candidate records are metadata only. A profile can drive a transform only
when its status is verified and a transform_id is declared.
"""
from __future__ import annotations

import json
from math import isfinite
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "camera_profiles.json"
_ALLOWED_STATUSES = {"unverified", "verified", "deprecated"}


class ProfileRegistryError(ValueError):
    """Raised when a camera profile registry is invalid."""


class ProfileRegistry:
    def __init__(self, profiles: list[dict[str, Any]]) -> None:
        ids: list[str] = []
        for index, profile in enumerate(profiles):
            if not isinstance(profile, dict):
                raise ProfileRegistryError(f"Profile at index {index} must be an object.")
            profile_id = profile.get("id")
            if not isinstance(profile_id, str) or not profile_id.strip():
                raise ProfileRegistryError("Every profile must have a unique, non-empty id.")
            ids.append(profile_id)
            for field in ("manufacturer", "encoding"):
                if not isinstance(profile.get(field), str) or not profile[field].strip():
                    raise ProfileRegistryError(
                        f"Profile '{profile_id}' requires a non-empty {field}."
                    )
            status = profile.get("status", "unverified")
            if status not in _ALLOWED_STATUSES:
                raise ProfileRegistryError(
                    f"Profile '{profile_id}' has unsupported status '{status}'."
                )
            models = profile.get("camera_models", [])
            if not isinstance(models, list) or not all(
                isinstance(model, str) and model.strip() for model in models
            ):
                raise ProfileRegistryError(
                    f"Profile '{profile_id}' camera_models must be a list of names."
                )
        if len(ids) != len(set(ids)):
            raise ProfileRegistryError("Every profile must have a unique, non-empty id.")
        self._profiles = deepcopy(profiles)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_REGISTRY_PATH) -> "ProfileRegistry":
        registry_path = Path(path)
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ProfileRegistryError(f"Cannot read profile registry: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ProfileRegistryError(f"Invalid profile registry JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProfileRegistryError("Registry root must be a JSON object.")
        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            raise ProfileRegistryError("Registry must contain a 'profiles' array.")
        return cls(profiles)

    def list_profiles(self) -> list[dict[str, Any]]:
        """Return copies of candidate profile records."""
        return deepcopy(self._profiles)

    def get_by_id(self, profile_id: str) -> dict[str, Any] | None:
        """Find a profile by its stable registry identifier."""
        for profile in self._profiles:
            if profile["id"] == profile_id:
                return self._resolved_record(profile)
        return None

    @staticmethod
    def _resolved_record(profile: dict[str, Any]) -> dict[str, Any]:
        record = deepcopy(profile)
        validation = record.get("validation")
        has_validation = (
            isinstance(validation, dict)
            and validation.get("passed") is True
            and validation.get("profile_id") == record.get("id")
            and validation.get("transform_id") == record.get("transform_id")
            and isinstance(validation.get("config_sha256"), str)
            and len(validation["config_sha256"]) == 64
            and all(character in "0123456789abcdef" for character in validation["config_sha256"].casefold())
            and isinstance(validation.get("reference_set_id"), str)
            and bool(validation["reference_set_id"].strip())
            and isinstance(validation.get("vector_count"), int)
            and not isinstance(validation.get("vector_count"), bool)
            and validation["vector_count"] > 0
            and isinstance(validation.get("tolerance"), (int, float))
            and not isinstance(validation.get("tolerance"), bool)
            and isfinite(validation["tolerance"])
            and validation["tolerance"] > 0
            and isinstance(validation.get("max_absolute_error"), (int, float))
            and not isinstance(validation.get("max_absolute_error"), bool)
            and isfinite(validation["max_absolute_error"])
            and 0 <= validation["max_absolute_error"] <= validation["tolerance"]
            and isinstance(validation.get("source_space"), str)
            and bool(validation["source_space"].strip())
            and isinstance(validation.get("destination_space"), str)
            and bool(validation["destination_space"].strip())
            and validation.get("source_space") == record.get("ocio_source_space")
            and validation.get("destination_space") == record.get("ocio_destination_space")
        )
        usable = (
            record.get("status") == "verified"
            and bool(record.get("transform_id"))
            and bool(record.get("ocio_source_space"))
            and bool(record.get("ocio_destination_space"))
            and bool(record.get("output_transfer"))
            and bool(record.get("output_primaries"))
            and has_validation
        )
        has_mapping = all(
            isinstance(record.get(field), str) and bool(record[field].strip())
            for field in (
                "transform_id", "ocio_source_space", "ocio_destination_space",
                "output_transfer", "output_primaries",
            )
        )
        record["usable_for_transform"] = usable
        record["transform_mapping_status"] = (
            "mapped_unvalidated" if has_mapping and not has_validation
            else "reference_validated" if usable
            else "mapping_unavailable"
        )
        record["validation_status"] = (
            "reference_validated" if has_validation else "not_reference_validated"
        )
        if not usable:
            record["resolution_note"] = (
                "Profile requires verified status, transform_id, and a passing "
                "reference-validation record before it can drive a transform."
            )
        return record

    def find_candidates(
        self,
        *,
        manufacturer: str,
        encoding: str | None = None,
        gamut: str | None = None,
        camera_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return possible profile choices without selecting or guessing one.

        When gamut is omitted, matching gamut variants are returned as separate
        choices and each record carries a gamut_choice requirement. Profiles
        restricted to named camera models require an explicit compatible model.
        """
        if not isinstance(manufacturer, str) or not manufacturer.strip():
            return []
        if encoding is not None and (
            not isinstance(encoding, str) or not encoding.strip()
        ):
            return []
        if gamut is not None and (
            not isinstance(gamut, str) or not gamut.strip()
        ):
            return []

        candidates = []
        for profile in self._profiles:
            if profile["manufacturer"].casefold() != manufacturer.casefold():
                continue
            if encoding is not None and profile["encoding"].casefold() != encoding.casefold():
                continue
            if gamut is not None and (profile.get("gamut") or "").casefold() != gamut.casefold():
                continue
            models = profile.get("camera_models", [])
            if camera_model is not None and models and not any(
                camera_model.casefold() == model.casefold() for model in models
            ):
                continue
            record = self._resolved_record(profile)
            requirements = []
            if gamut is None:
                requirements.append("gamut_choice")
            if models and camera_model is None:
                requirements.append("camera_model")
            record["selection_requirements"] = requirements
            candidates.append(record)
        return candidates

    def resolve(
        self,
        *,
        manufacturer: str,
        encoding: str,
        gamut: str | None,
        camera_model: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve exact declared metadata; never infer missing gamut/model data."""
        if not manufacturer.strip() or not encoding.strip():
            return None

        matches = [
            profile
            for profile in self._profiles
            if profile["manufacturer"].casefold() == manufacturer.casefold()
            and profile["encoding"].casefold() == encoding.casefold()
            and (profile.get("gamut") or "").casefold() == (gamut or "").casefold()
            and (
                not profile.get("camera_models")
                or (
                    camera_model is not None
                    and any(
                        camera_model.casefold() == model.casefold()
                        for model in profile["camera_models"]
                    )
                )
            )
        ]
        if len(matches) != 1:
            return None
        return self._resolved_record(matches[0])
