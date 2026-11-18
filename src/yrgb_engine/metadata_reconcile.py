"""Conservative reconciliation of camera sidecar and stream color declarations."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_FIELD_MAP = {
    "camera_transfer": ("CaptureGammaEquation", "color_transfer"),
    "camera_primaries": ("CaptureColorPrimaries", "color_primaries"),
    "coding_equations": ("CodingEquations", "color_space"),
}

_ALIASES = {
    "rec709": "bt709",
    "bt.709": "bt709",
    "slog3": "s-log3",
    "s-log3-cine": "s-log3",
    "sgamut3cine": "s-gamut3-cine",
    "s-gamut3.cine": "s-gamut3-cine",
    "s-gamut3-cine": "s-gamut3-cine",
    "bt2020": "bt2020",
    "bt.2020": "bt2020",
}


def _first_value(values: Mapping[str, Any], key: str) -> str | None:
    value = values.get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        cleaned = str(value).strip()
        return cleaned or None
    return None


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip().casefold().replace("_", "-").replace(" ", "")
    return _ALIASES.get(token, token)


def reconcile_color_metadata(
    xml_values: Mapping[str, Any] | None,
    stream_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare sidecar declarations with stream tags without choosing a winner.

    Values are retained verbatim. Agreement means declarations agree, not that
    the declared transform is colorimetrically correct.
    """
    xml_values = xml_values or {}
    stream_metadata = stream_metadata or {}
    comparisons: dict[str, dict[str, Any]] = {}
    for field, (xml_key, stream_key) in _FIELD_MAP.items():
        xml_value = _first_value(xml_values, xml_key)
        stream_value = _first_value(stream_metadata, stream_key)
        if xml_value is None or stream_value is None:
            status = "unresolved"
        elif _normalise(xml_value) == _normalise(stream_value):
            status = "reported"
        else:
            status = "conflict"
        comparisons[field] = {
            "xml_field": xml_key,
            "xml_value": xml_value,
            "stream_field": stream_key,
            "stream_value": stream_value,
            "xml_normalized": _normalise(xml_value),
            "stream_normalized": _normalise(stream_value),
            "status": status,
        }
    statuses = [item["status"] for item in comparisons.values()]
    overall = "conflict" if "conflict" in statuses else (
        "unresolved" if "unresolved" in statuses else "reported"
    )
    notes = [
        "Agreement confirms only that declarations match; it does not validate the camera transform.",
        "Missing declarations remain unresolved and are never inferred from a camera model or filename.",
    ]
    if overall == "conflict":
        notes.append("At least one sidecar/stream color declaration disagrees; preserve both values.")
    return {
        "xml_declared": {
            field: item["xml_value"] for field, item in comparisons.items()
        },
        "stream_signaled": {
            field: item["stream_value"] for field, item in comparisons.items()
        },
        "comparisons": comparisons,
        "resolution_status": overall,
        "resolution_notes": notes,
    }
