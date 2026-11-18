"""Scene-linear float export without inventing a display transform."""
from __future__ import annotations

from pathlib import Path

from .precision import PrecisionFrame


class LinearExportError(ValueError):
    """Raised when a scene-linear float export cannot be written."""


def save_linear_float_exr(frame: PrecisionFrame, output_path: str | Path) -> Path:
    """Write float32 RGB(A)/multi-channel samples to OpenEXR via OpenImageIO.

    Values are not clamped, normalized or display-transformed. The caller must
    preserve the explicit working-space contract alongside the EXR.
    """
    try:
        import numpy as np
        import OpenImageIO as oiio
    except ImportError as exc:
        raise LinearExportError(
            "OpenImageIO and NumPy are required for float EXR export. Install the 'high-precision' extra."
        ) from exc
    if frame.width * frame.height > 40_000_000:
        raise LinearExportError("EXR export is limited to 40 megapixels.")
    if not all(name and name != "unknown" for name in frame.channel_names):
        raise LinearExportError("EXR export requires explicit channel names.")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    spec = oiio.ImageSpec(frame.width, frame.height, frame.channel_count, oiio.FLOAT)
    spec.channelnames = list(frame.channel_names)
    image_output = oiio.ImageOutput.create(str(destination))
    if image_output is None:
        raise LinearExportError(oiio.geterror() or "OpenImageIO could not create EXR output.")
    try:
        if not image_output.open(str(destination), spec):
            raise LinearExportError(image_output.geterror() or "Could not open EXR output.")
        pixels = np.asarray(frame.samples, dtype=np.float32).reshape(
            frame.height, frame.width, frame.channel_count
        )
        if not image_output.write_image(pixels):
            raise LinearExportError(image_output.geterror() or "Could not write EXR pixels.")
    finally:
        image_output.close()
    return destination
