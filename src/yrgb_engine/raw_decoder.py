"""Optional LibRaw-backed RAW still decoder.

The adapter requests a linear, camera-native demosaiced RGB result. This is not
the original Bayer/CFA sensor mosaic and is not a finished color-managed image.
"""
from __future__ import annotations

from pathlib import Path

from .oiio_decoder import HighPrecisionDecodeError
from .precision import ColorEncoding, PrecisionFrame


def decode_raw_camera_rgb(file_path: str | Path) -> PrecisionFrame:
    """Demosaic a supported RAW still to float32 camera-native RGB code values."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise HighPrecisionDecodeError(f"File not found: {path}")

    try:
        import numpy as np
        import rawpy
    except ImportError as exc:
        raise HighPrecisionDecodeError(
            "rawpy (LibRaw) and NumPy are required. Install the 'raw' extra."
        ) from exc

    try:
        with rawpy.imread(str(path)) as raw:
            rgb16 = raw.postprocess(
                output_bps=16,
                output_color=rawpy.ColorSpace.raw,
                gamma=(1, 1),
                no_auto_bright=True,
                use_camera_wb=False,
                user_wb=(1.0, 1.0, 1.0, 1.0),
            )
            camera = str(getattr(raw, "camera_model", "") or "unknown")
            make = str(getattr(raw, "camera_make", "") or "unknown")
            black_level = getattr(raw, "black_level_per_channel", None)
            white_level = getattr(raw, "white_level", None)

        pixels = np.asarray(rgb16)
        if pixels.ndim != 3 or pixels.shape[2] != 3:
            raise HighPrecisionDecodeError(
                f"LibRaw returned an unexpected pixel shape: {pixels.shape}."
            )
        height, width, _ = pixels.shape
        # Preserve 16-bit output code values as float32; do not normalize to [0, 1].
        values = pixels.astype(np.float32, copy=False).reshape(-1)
        metadata: dict[str, str | int | float | bool | None] = {
            "camera_model": camera,
            "camera_make": make,
            "libraw_output_bits": 16,
            "demosaiced": True,
            "camera_white_balance_applied": False,
            "black_level_per_channel": str(black_level) if black_level is not None else None,
            "white_level": int(white_level) if white_level is not None else None,
        }
        return PrecisionFrame.from_interleaved(
            width=int(width),
            height=int(height),
            channel_names=("R_camera", "G_camera", "B_camera"),
            values=values,
            source_path=str(path),
            decoder=f"LibRaw/{getattr(rawpy, '__version__', 'unknown')}",
            encoding=ColorEncoding(
                primaries="camera_native_uncharacterized",
                transfer="linear_candidate",
                matrix="unknown",
                range="unknown",
                reference="unknown",
                metadata_source="LibRaw",
                validated=False,
            ),
            sample_domain="rawpy_linear_camera_rgb_uint16_code_values",
            purpose="grading_candidate",
            metadata=metadata,
        )
    except HighPrecisionDecodeError:
        raise
    except Exception as exc:
        raise HighPrecisionDecodeError(f"LibRaw RAW decode failed: {exc}") from exc
