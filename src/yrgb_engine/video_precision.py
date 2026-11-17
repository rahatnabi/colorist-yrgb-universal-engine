"""Optional FFmpeg float32 video-frame decoder.

This converts the decoded video frame to RGB float samples but does not apply a
camera Log-to-working-space transform. Source transfer and primaries are retained
as metadata; matrix/range conversion details are explicitly recorded.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .oiio_decoder import HighPrecisionDecodeError
from .precision import ColorEncoding, PrecisionFrame

DEFAULT_TIMEOUT_SECONDS = 30


def _probe_video_stream(path: Path, timeout_seconds: int) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise HighPrecisionDecodeError("ffprobe was not found on PATH; install FFmpeg.")
    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,codec_name,pix_fmt,bits_per_raw_sample,color_range,color_space,color_transfer,color_primaries",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise HighPrecisionDecodeError("ffprobe timed out while inspecting the video.") from exc
    if result.returncode != 0:
        raise HighPrecisionDecodeError(result.stderr.strip() or "ffprobe could not inspect video.")
    try:
        streams = json.loads(result.stdout).get("streams", [])
        stream = streams[0]
        stream["width"] = int(stream["width"])
        stream["height"] = int(stream["height"])
        return stream
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise HighPrecisionDecodeError("No valid first video stream was reported.") from exc


def decode_video_float_frame(
    file_path: str | Path,
    *,
    timestamp_seconds: float = 0.0,
    max_pixels: int = 40_000_000,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> PrecisionFrame:
    """Decode one video frame into float32 RGB without applying an input transform."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise HighPrecisionDecodeError(f"File not found: {path}")
    if timestamp_seconds < 0:
        raise ValueError("timestamp_seconds must be zero or greater.")

    try:
        import numpy as np
    except ImportError as exc:
        raise HighPrecisionDecodeError(
            "NumPy is required. Install the 'high-precision' extra."
        ) from exc

    stream = _probe_video_stream(path, timeout_seconds)
    width, height = stream["width"], stream["height"]
    if width <= 0 or height <= 0:
        raise HighPrecisionDecodeError("Video stream dimensions must be positive.")
    if width * height > max_pixels:
        raise HighPrecisionDecodeError(
            f"Video frame has {width * height} pixels; configured limit is {max_pixels}."
        )

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HighPrecisionDecodeError("ffmpeg was not found on PATH; install FFmpeg.")
    command = [
        ffmpeg, "-v", "error", "-ss", str(timestamp_seconds), "-i", str(path),
        "-map", "0:v:0", "-frames:v", "1", "-f", "rawvideo",
        "-pix_fmt", "gbrpf32le", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise HighPrecisionDecodeError("FFmpeg timed out while decoding the video frame.") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise HighPrecisionDecodeError(detail or "FFmpeg could not decode float32 RGB frame.")

    expected = width * height * 3 * 4
    if len(result.stdout) != expected:
        raise HighPrecisionDecodeError(
            f"Float frame size mismatch: expected {expected} bytes, received {len(result.stdout)}."
        )

    # FFmpeg gbrpf32le is planar G, B, R. Reorder to interleaved R, G, B.
    planes = np.frombuffer(result.stdout, dtype="<f4").reshape(3, height, width)
    rgb = np.stack((planes[2], planes[0], planes[1]), axis=-1)

    source_primaries = str(stream.get("color_primaries") or "unknown")
    source_transfer = str(stream.get("color_transfer") or "unknown")
    source_matrix = str(stream.get("color_space") or "unknown")
    source_range = str(stream.get("color_range") or "unknown")
    bits_raw = stream.get("bits_per_raw_sample")
    try:
        source_bit_depth = int(bits_raw) if bits_raw not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        source_bit_depth = None

    return PrecisionFrame.from_interleaved(
        width=width,
        height=height,
        channel_names=("R", "G", "B"),
        values=rgb.reshape(-1),
        source_path=str(path),
        decoder="FFmpeg/gbrpf32le",
        encoding=ColorEncoding(
            primaries=source_primaries,
            transfer=source_transfer,
            matrix="RGB",
            range="full",
            reference="unknown",
            source_bit_depth=source_bit_depth,
            metadata_source="ffprobe+ffmpeg",
            validated=False,
        ),
        sample_domain="ffmpeg_gbrpf32le_rgb_float_source_transfer_retained",
        purpose="grading_candidate",
        metadata={
            "source_codec": stream.get("codec_name"),
            "source_pixel_format": stream.get("pix_fmt"),
            "source_matrix": source_matrix,
            "source_range": source_range,
            "source_color_primaries": source_primaries,
            "source_color_transfer": source_transfer,
            "timestamp_seconds": timestamp_seconds,
            "ffmpeg_pixel_format": "gbrpf32le",
        },
    )
