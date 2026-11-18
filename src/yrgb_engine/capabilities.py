"""Runtime capability discovery for optional still-image dependencies."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Capability:
    name: str
    available: bool
    version: str | None
    purpose: str
    limitation: str


def _module_version(distribution_name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None


def _python_capability(
    module_name: str, distribution_name: str, purpose: str, limitation: str
) -> Capability:
    available = importlib.util.find_spec(module_name) is not None
    return Capability(
        module_name,
        available,
        _module_version(distribution_name) if available else None,
        purpose,
        limitation,
    )


def detect_capabilities() -> list[Capability]:
    """Report still-image dependencies without implying complete format support."""
    return [
        _python_capability(
            "PIL",
            "Pillow",
            "Browser-oriented still-image preview decoding",
            "Not a production RAW decoder; format and bit-depth support varies.",
        ),
        _python_capability(
            "rawpy",
            "rawpy",
            "Optional LibRaw-backed RAW still decoding",
            "Camera support depends on LibRaw; a validated camera color transform is still required.",
        ),
        _python_capability(
            "OpenImageIO",
            "OpenImageIO",
            "High-bit-depth still-image float32 decode and TIFF/OpenEXR export",
            "Plugin support depends on the OpenImageIO build; decode does not infer or apply camera Log transforms.",
        ),
        _python_capability(
            "PyOpenColorIO",
            "opencolorio",
            "Camera input transforms and explicit color-space conversion",
            "A transform is usable only when its exact profile is independently reference-validated.",
        ),
    ]


def capabilities_as_dict() -> list[dict[str, object]]:
    return [asdict(item) for item in detect_capabilities()]
