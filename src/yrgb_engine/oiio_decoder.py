"""Optional OpenImageIO decoder for high-bit-depth still images.

This adapter requests float32 pixels and records source metadata separately.
It does not infer camera Log profiles or apply an input/display transform.
"""
from __future__ import annotations

from pathlib import Path

from .precision import ColorEncoding, PrecisionFrame


class HighPrecisionDecodeError(RuntimeError):
    """Raised when a high-precision decoder cannot read an asset."""


def decode_oiio_float(file_path: str | Path) -> PrecisionFrame:
    """Decode one image to an interleaved float32 PrecisionFrame using OpenImageIO."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise HighPrecisionDecodeError(f"File not found: {path}")

    try:
        import numpy as np
        import OpenImageIO as oiio
    except ImportError as exc:
        raise HighPrecisionDecodeError(
            "OpenImageIO and NumPy are required. Install the 'high-precision' extra."
        ) from exc

    image_input = oiio.ImageInput.open(str(path))
    if image_input is None:
        detail = oiio.geterror() if hasattr(oiio, "geterror") else "OpenImageIO could not open file."
        raise HighPrecisionDecodeError(str(detail))

    try:
        spec = image_input.spec()
        width, height, channels = int(spec.width), int(spec.height), int(spec.nchannels)
        if width <= 0 or height <= 0 or channels <= 0:
            raise HighPrecisionDecodeError("Decoder returned invalid image dimensions or channels.")

        try:
            pixels = image_input.read_image(format=oiio.FLOAT)
        except TypeError:
            # Compatibility with bindings that expose the format as a positional argument.
            pixels = image_input.read_image(oiio.FLOAT)
        if pixels is None:
            detail = image_input.geterror() if hasattr(image_input, "geterror") else "Pixel read failed."
            raise HighPrecisionDecodeError(str(detail))

        buffer = np.asarray(pixels, dtype=np.float32)
        expected = width * height * channels
        if buffer.size != expected:
            raise HighPrecisionDecodeError(
                f"Unexpected pixel buffer size: expected {expected}, received {buffer.size}."
            )
        values = buffer.reshape(-1)

        raw_channel_names = list(getattr(spec, "channelnames", []) or [])
        if len(raw_channel_names) == channels and all(raw_channel_names):
            channel_names = tuple(str(name) for name in raw_channel_names)
        else:
            channel_names = tuple(f"channel_{index}" for index in range(channels))

        # Only preserve metadata that is safe to report. Do not guess colorimetry.
        metadata = {
            "oiio_format": str(getattr(spec, "format", "unknown")),
            "oiio_nchannels": channels,
            "oiio_alpha_channel": int(getattr(spec, "alpha_channel", -1)),
            "oiio_deep": bool(getattr(spec, "deep", False)),
        }
        return PrecisionFrame.from_interleaved(
            width=width,
            height=height,
            channel_names=channel_names,
            values=values,
            source_path=str(path),
            decoder="OpenImageIO",
            encoding=ColorEncoding(metadata_source="source_metadata_not_yet_resolved"),
            sample_domain="oiio_float_conversion_uncharacterized",
            purpose="grading_candidate",
            metadata=metadata,
        )
    except HighPrecisionDecodeError:
        raise
    except Exception as exc:
        raise HighPrecisionDecodeError(f"OpenImageIO decode failed: {exc}") from exc
    finally:
        image_input.close()
