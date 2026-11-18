"""Explicit luma coefficient presets for sample-domain scopes.

These presets are user-selected assumptions, not metadata detection or transforms.
"""
from __future__ import annotations

from typing import Literal

ScopeStandard = Literal["bt709", "bt2020"]

_SCOPE_COEFFICIENTS: dict[str, tuple[float, float, float]] = {
    "bt709": (0.2126, 0.7152, 0.0722),
    "bt2020": (0.2627, 0.6780, 0.0593),
}


def get_scope_coefficients(standard: ScopeStandard) -> tuple[float, float, float]:
    """Return normalized luma coefficients for an explicitly selected standard."""
    try:
        return _SCOPE_COEFFICIENTS[standard]
    except KeyError as exc:
        raise ValueError("Scope standard must be 'bt709' or 'bt2020'.") from exc


def available_scope_standards() -> tuple[str, ...]:
    """Return supported manual scope presets."""
    return tuple(_SCOPE_COEFFICIENTS)
