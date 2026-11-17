"""Runtime capability discovery for optional media dependencies."""
from __future__ import annotations
import importlib.util
import shutil
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

def _python_capability(module_name: str, distribution_name: str, purpose: str, limitation: str) -> Capability:
    available = importlib.util.find_spec(module_name) is not None
    return Capability(module_name, available, _module_version(distribution_name) if available else None, purpose, limitation)

def _binary_capability(binary: str, purpose: str, limitation: str) -> Capability:
    path = shutil.which(binary)
    return Capability(binary, path is not None, None, purpose, f"{limitation} Executable: {path}" if path else limitation)

def detect_capabilities() -> list[Capability]:
    """Report installed optional tools without implying complete format support."""
    return [
        _binary_capability("ffprobe", "Video container and stream metadata inspection", "Codecs and metadata depend on the FFmpeg build."),
        _binary_capability("ffmpeg", "Video preview-frame decoding and proxy generation", "Codec, bit-depth, hardware acceleration, and color behavior are build-dependent."),
        _python_capability("PIL", "Pillow", "Still-image preview decoding", "Not a production RAW decoder; format and bit-depth support varies."),
        _python_capability("rawpy", "rawpy", "Optional LibRaw-backed RAW still decoding", "Camera support depends on LibRaw; no RAW adapter is enabled yet."),
        _python_capability("OpenImageIO", "OpenImageIO", "High-bit-depth image and sequence I/O", "No OpenImageIO adapter is enabled yet; plugin support depends on build."),
        _python_capability("PyOpenColorIO", "opencolorio", "Color-management integration", "No production transform is enabled until config and reference tests exist."),
    ]

def capabilities_as_dict() -> list[dict[str, object]]:
    return [asdict(item) for item in detect_capabilities()]
