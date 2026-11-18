"""Full-resolution float32 still-image export for validated native grades."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .precision import PrecisionFrame


class NativeExportError(RuntimeError):
    """Raised when a native float export cannot be safely produced."""


def validate_native_export_frame(frame: PrecisionFrame) -> None:
    """Refuse unvalidated, non-linear, or incomplete image data."""
    if not frame.encoding.validated:
        raise NativeExportError("Native export requires a reference-validated camera transform.")
    if frame.encoding.transfer.casefold() not in {"linear", "linear-light", "scene-linear"}:
        raise NativeExportError("Native float export requires a scene-linear graded frame.")
    if not frame.encoding.working_space_id or not frame.encoding.transform_id:
        raise NativeExportError("Working-space and transform identities are required for export.")
    channels = {name.upper() for name in frame.channel_names}
    if not {"R", "G", "B"}.issubset(channels):
        raise NativeExportError("Native export requires named R, G and B channels.")
    if frame.purpose != "graded_still_candidate":
        raise NativeExportError("Only a graded still frame may be exported.")


def native_frame_sha256(frame: PrecisionFrame) -> str:
    """Hash the exact interleaved float32 samples before container encoding."""
    validate_native_export_frame(frame)
    return hashlib.sha256(frame.samples.tobytes()).hexdigest()


def save_native_float_image(frame: PrecisionFrame, output_path: str | Path) -> Path:
    """Write unclamped float32 RGB(A) samples to TIFF or OpenEXR."""
    validate_native_export_frame(frame)
    destination = Path(output_path)
    suffix = destination.suffix.casefold()
    if suffix not in {".tif", ".tiff", ".exr"}:
        raise NativeExportError("Supported native float exports are TIFF (.tif/.tiff) and OpenEXR (.exr).")

    try:
        import numpy as np
        import OpenImageIO as oiio
    except ImportError as exc:
        raise NativeExportError(
            "OpenImageIO and NumPy are required. Install the 'high-precision' extra."
        ) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    spec = oiio.ImageSpec(frame.width, frame.height, frame.channel_count, oiio.FLOAT)
    spec.channelnames = list(frame.channel_names)
    spec.attribute("oiio:ColorSpace", frame.encoding.working_space_id)
    spec.attribute("YRGB:WorkingSpace", frame.encoding.working_space_id)
    spec.attribute("YRGB:TransformID", frame.encoding.transform_id)
    spec.attribute("YRGB:Transfer", "Linear")
    spec.attribute("YRGB:Export", "Full-resolution float32; unclamped")
    spec.attribute("Software", "COLORIST YRGB Universal Engine")
    if suffix == ".exr":
        spec.attribute("compression", "zip")
    else:
        spec.attribute("compression", "deflate")

    output = oiio.ImageOutput.create(str(destination))
    if output is None:
        detail = oiio.geterror() if hasattr(oiio, "geterror") else "OpenImageIO could not create output."
        raise NativeExportError(str(detail))
    try:
        if not output.open(str(destination), spec):
            raise NativeExportError(output.geterror() or "Could not open native export destination.")
        pixels = np.asarray(frame.samples, dtype=np.float32).reshape(
            frame.height, frame.width, frame.channel_count
        )
        if not output.write_image(pixels):
            raise NativeExportError(output.geterror() or "Could not write native float image.")
    finally:
        output.close()
    return destination
