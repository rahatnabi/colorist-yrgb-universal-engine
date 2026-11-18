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


def verify_native_float_export(
    frame: PrecisionFrame,
    output_path: str | Path,
    *,
    absolute_tolerance: float = 1e-7,
    relative_tolerance: float = 1e-6,
) -> dict[str, float | int | bool | str]:
    """Read a written TIFF/EXR back and compare every float32 channel sample."""
    validate_native_export_frame(frame)
    if absolute_tolerance < 0 or relative_tolerance < 0:
        raise NativeExportError("Round-trip tolerances must be non-negative.")
    try:
        import numpy as np
        import OpenImageIO as oiio
    except ImportError as exc:
        raise NativeExportError(
            "OpenImageIO and NumPy are required for export round-trip verification."
        ) from exc

    source = np.asarray(frame.samples, dtype=np.float32).reshape(
        frame.height, frame.width, frame.channel_count
    )
    image_input = oiio.ImageInput.open(str(output_path))
    if image_input is None:
        detail = oiio.geterror() if hasattr(oiio, "geterror") else "Could not reopen exported image."
        raise NativeExportError(str(detail))
    try:
        spec = image_input.spec()
        if int(spec.width) != frame.width or int(spec.height) != frame.height:
            raise NativeExportError("Export round-trip dimensions do not match the graded still.")
        if int(spec.nchannels) != frame.channel_count:
            raise NativeExportError("Export round-trip channel count does not match the graded still.")
        names = tuple(str(name) for name in (getattr(spec, "channelnames", []) or []))
        if names and names != frame.channel_names:
            raise NativeExportError("Export round-trip channel names do not match the graded still.")
        try:
            decoded = image_input.read_image(format=oiio.FLOAT)
        except TypeError:
            decoded = image_input.read_image(oiio.FLOAT)
        if decoded is None:
            detail = image_input.geterror() if hasattr(image_input, "geterror") else "Export read-back failed."
            raise NativeExportError(str(detail))
        actual = np.asarray(decoded, dtype=np.float32)
        if actual.size != source.size:
            raise NativeExportError("Export round-trip sample count does not match the graded still.")
        actual = actual.reshape(source.shape)
        delta = np.abs(actual - source)
        allowed = absolute_tolerance + relative_tolerance * np.abs(source)
        mismatches = int(np.count_nonzero(delta > allowed))
        max_absolute_error = float(np.max(delta)) if delta.size else 0.0
        rmse = float(np.sqrt(np.mean(np.square(actual - source)))) if delta.size else 0.0
        if mismatches:
            raise NativeExportError(
                f"Export round-trip failed: {mismatches} samples exceed tolerance; "
                f"maximum absolute error is {max_absolute_error:.9g}."
            )
        actual_digest = hashlib.sha256(np.ascontiguousarray(actual).tobytes()).hexdigest()
        expected_digest = native_frame_sha256(frame)
        return {
            "verified": True,
            "sample_count": int(source.size),
            "mismatch_count": mismatches,
            "max_absolute_error": max_absolute_error,
            "rmse": rmse,
            "sample_sha256_matches": actual_digest == expected_digest,
            "sample_sha256": actual_digest,
        }
    finally:
        image_input.close()
