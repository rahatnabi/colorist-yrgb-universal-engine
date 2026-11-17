"""Preview decoding adapters for still images and video.

These adapters are for thumbnails and interactive previews only. They convert
source media to 8-bit RGB and must not be used as the precision path for grading.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .frame import DecodedFrame

DEFAULT_MAX_PIXELS = 40_000_000
DEFAULT_TIMEOUT_SECONDS = 30


class DecodeError(RuntimeError):
    """Raised when a media asset cannot be decoded by an available adapter."""


def decode_still_preview(
    file_path: str | Path,
    *,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> DecodedFrame:
    """Decode the first still-image frame to an 8-bit RGB preview."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise DecodeError(f"File not found: {path}")

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise DecodeError("Pillow is required. Install with: pip install -e '.[images]'") from exc

    try:
        with Image.open(path) as source:
            frame = ImageOps.exif_transpose(source)
            width, height = frame.size
            if width * height > max_pixels:
                raise DecodeError(
                    f"Image has {width * height} pixels; configured limit is {max_pixels}."
                )
            # Convert to RGB for preview only; preserve original file untouched.
            rgb = frame.convert("RGB")
            return DecodedFrame(
                width=width,
                height=height,
                pixel_format="rgb24",
                data=rgb.tobytes(),
                source_path=str(path),
                decoder=f"Pillow/{Image.__version__ if hasattr(Image, '__version__') else 'unknown'}",
                source_metadata={
                    "source_format": source.format,
                    "source_mode": source.mode,
                    "icc_profile_present": bool(source.info.get("icc_profile")),
                },
            )
    except DecodeError:
        raise
    except Exception as exc:
        raise DecodeError(f"Still-image preview decode failed: {exc}") from exc


def _probe_video_dimensions(path: Path, timeout: int) -> tuple[int, int, dict[str, str | int | None]]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise DecodeError("ffprobe was not found on PATH; install FFmpeg.")
    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,pix_fmt,color_range,color_space,color_transfer,color_primaries",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise DecodeError(f"ffprobe timed out after {timeout} seconds.") from exc
    if result.returncode != 0:
        raise DecodeError(result.stderr.strip() or "ffprobe could not inspect the video.")
    try:
        streams = json.loads(result.stdout).get("streams", [])
        stream = streams[0]
        width, height = int(stream["width"]), int(stream["height"])
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise DecodeError("No readable first video stream or dimensions were found.") from exc
    metadata = {
        key: stream.get(key)
        for key in ("codec_name", "pix_fmt", "color_range", "color_space", "color_transfer", "color_primaries")
    }
    return width, height, metadata


def decode_video_preview_frame(
    file_path: str | Path,
    *,
    timestamp_seconds: float = 0.0,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> DecodedFrame:
    """Decode one video frame to RGB24 for preview, not final grading."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise DecodeError(f"File not found: {path}")
    if timestamp_seconds < 0:
        raise ValueError("timestamp_seconds must be zero or greater.")

    width, height, metadata = _probe_video_dimensions(path, timeout_seconds)
    if width * height > max_pixels:
        raise DecodeError(
            f"Video frame has {width * height} pixels; configured limit is {max_pixels}."
        )
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise DecodeError("ffmpeg was not found on PATH; install FFmpeg.")

    command = [
        ffmpeg, "-v", "error", "-ss", str(timestamp_seconds), "-i", str(path),
        "-map", "0:v:0", "-frames:v", "1", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise DecodeError(f"ffmpeg frame decode timed out after {timeout_seconds} seconds.") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise DecodeError(detail or "ffmpeg could not decode a preview frame.")

    expected_bytes = width * height * 3
    if len(result.stdout) != expected_bytes:
        raise DecodeError(
            f"Decoded frame size mismatch: expected {expected_bytes} bytes, got {len(result.stdout)}."
        )

    return DecodedFrame(
        width=width,
        height=height,
        pixel_format="rgb24",
        data=result.stdout,
        source_path=str(path),
        decoder="FFmpeg",
        purpose="preview",
        source_metadata=metadata,
    )
