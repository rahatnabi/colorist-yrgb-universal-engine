"""Explicit camera profile registry lookup.

Candidate records are metadata only. A profile can drive a transform only
when its status is verified and a transform_id is declared.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "camera_profiles.json"
_ALLOWED_STATUSES = {"unverified", "verified", "deprecated"}


class ProfileRegistryError(ValueError):
    """Raised when a camera profile registry is invalid."""


class ProfileRegistry:
    def __init__(self, profiles: list[dict[str, Any]]) -> None:
        self._profiles = [dict(item) for item in profiles]
        ids: list[str] = []
        for index, profile in enumerate(self._profiles):
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
        return [dict(profile) for profile in self._profiles]

    def get_by_id(self, profile_id: str) -> dict[str, Any] | None:
        """Find a profile by its stable registry identifier."""
        for profile in self._profiles:
            if profile["id"] == profile_id:
                return self._resolved_record(profile)
        return None

    @staticmethod
    def _resolved_record(profile: dict[str, Any]) -> dict[str, Any]:
        record = dict(profile)
        usable = record.get("status") == "verified" and bool(record.get("transform_id"))
        record["usable_for_transform"] = usable
        if not usable:
            record["resolution_note"] = (
                "Profile is catalogued but its transform is not verified."
            )
        return record

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
