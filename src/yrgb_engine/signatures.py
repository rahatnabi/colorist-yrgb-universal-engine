"""Conservative file-signature detection.

Extensions are treated as hints, never as proof of a media type.
"""

from pathlib import Path

SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image", "png"),
    (b"\xff\xd8\xff", "image", "jpeg"),
    (b"\x76\x2f\x31\x01", "image", "exr"),
    (b"MM\x00*", "image", "tiff"),
    (b"II*\x00", "image", "tiff"),
    (b"SDPX", "image", "dpx"),
    (b"XPDS", "image", "dpx"),
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".dpx", ".dng"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".mxf", ".mkv", ".avi", ".webm", ".m4v"}
LUT_EXTENSIONS = {".cube"}


def detect_signature(header: bytes, suffix: str) -> tuple[str, str]:
    """Return (media_family, signature_name) using header bytes where possible."""
    suffix = suffix.lower()

    # ISO Base Media File Format family used by MP4/MOV and related containers.
    if len(header) >= 8 and header[4:8] == b"ftyp":
        brand = header[8:12].decode("ascii", errors="replace") if len(header) >= 12 else ""
        return "video", f"isobmff:{brand or 'unknown'}"

    for magic, family, name in SIGNATURES:
        if header.startswith(magic):
            if suffix == ".dng" and name == "tiff":
                return "image", "dng-tiff"
            return family, name

    if suffix in VIDEO_EXTENSIONS:
        return "video", "unverified-extension"
    if suffix in IMAGE_EXTENSIONS:
        return "image", "unverified-extension"
    if suffix in LUT_EXTENSIONS:
        return "lut", "text-cube-candidate"
    return "unknown", "unknown"
