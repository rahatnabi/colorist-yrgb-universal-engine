"""Explicit camera profile registry lookup.

The registry intentionally refuses to guess transforms. Candidate entries are
catalogued separately from profiles whose transforms have been verified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "profiles" / "camera_profiles.json"


class ProfileRegistryError(ValueError):
    """Raised when a camera profile registry is invalid."""


class ProfileRegistry:
    def __init__(self, profiles: list[dict[str, Any]]) -> None:
        self._profiles = profiles
        ids = [item.get("id") for item in profiles]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
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

        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            raise ProfileRegistryError("Registry must contain a 'profiles' array.")
        return cls(profiles)

    def list_profiles(self) -> list[dict[str, Any]]:
        """Return a shallow copy of the candidate profile records."""
        return [dict(profile) for profile in self._profiles]

    def resolve(
        self,
        *,
        manufacturer: str,
        encoding: str,
        gamut: str | None,
        camera_model: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve an exact declared profile; never infer missing gamut/model data."""
        matches = [
            profile
            for profile in self._profiles
            if profile.get("manufacturer", "").casefold() == manufacturer.casefold()
            and profile.get("encoding", "").casefold() == encoding.casefold()
            and (profile.get("gamut") or None) == (gamut or None)
            and (
                not profile.get("camera_models")
                or (camera_model is not None and camera_model in profile["camera_models"])
            )
        ]
        if len(matches) != 1:
            return None

        profile = dict(matches[0])
        if profile.get("status") != "verified" or not profile.get("transform_id"):
            profile["usable_for_transform"] = False
            profile["resolution_note"] = "Profile is catalogued but its transform is not verified."
            return profile

        profile["usable_for_transform"] = True
        return profile
