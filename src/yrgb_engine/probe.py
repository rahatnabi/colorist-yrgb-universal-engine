"""Media probing with conservative signature checks and optional ffprobe/Pillow."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import MediaProbeResult
from .signatures import detect_signature

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024 * 1024


def _read_header(path: Path, length: int = 32) -> bytes:
    with path.open("rb") as stream:
        return stream.read(length)


def _run_ffprobe(path: Path, timeout: int) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise FileNotFoundError("ffprobe executable was not found on PATH")

    command = [
        executable,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "ffprobe could not parse this file"
        raise ValueError(detail)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("ffprobe returned an unexpected data structure")
    return payload


def _image_metadata(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        return {"metadata_reader": "unavailable", "note": "Install the 'images' extra for Pillow metadata."}

    try:
        with Image.open(path) as image:
            return {
                "metadata_reader": "Pillow",
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "frames": getattr(image, "n_frames", 1),
                "icc_profile_present": bool(image.info.get("icc_profile")),
            }
    except Exception as exc:  # Pillow raises format-specific exceptions.
        return {"metadata_reader": "Pillow", "metadata_error": str(exc)}


def probe_media(
    file_path: str | Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> MediaProbeResult:
    """Inspect a media asset without assuming its extension is truthful."""
    path = Path(file_path).expanduser()
    suffix = path.suffix.lower()
    result = MediaProbeResult(
        path=str(path),
        exists=path.is_file(),
        extension=suffix,
    )

    if not result.exists:
        result.status = "not_found"
        result.warnings.append("Path does not point to an existing regular file.")
        return result

    try:
        result.size_bytes = path.stat().st_size
        if result.size_bytes > max_file_bytes:
            result.status = "rejected_size_limit"
            result.warnings.append(f"File exceeds configured limit of {max_file_bytes} bytes.")
            return result
        header = _read_header(path)
    except OSError as exc:
        result.status = "read_error"
        result.warnings.append(str(exc))
        return result

    family, signature = detect_signature(header, suffix)
    result.detected_type = family
    result.signature = signature

    if family == "video":
        if signature == "unverified-extension":
            result.warnings.append("Video extension is unverified; container signature was not recognized.")
        try:
            payload = _run_ffprobe(path, timeout_seconds)
            result.metadata = payload
            streams = payload.get("streams", [])
            result.status = "probed"
            result.metadata["stream_summary"] = [
                {
                    "index": stream.get("index"),
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "pix_fmt": stream.get("pix_fmt"),
                    "bit_rate": stream.get("bit_rate"),
                    "avg_frame_rate": stream.get("avg_frame_rate"),
                    "color_space": stream.get("color_space"),
                    "color_transfer": stream.get("color_transfer"),
                    "color_primaries": stream.get("color_primaries"),
                    "color_range": stream.get("color_range"),
                }
                for stream in streams
            ]
            if not any(s.get("codec_type") == "video" for s in streams):
                result.warnings.append("No video stream was reported by ffprobe.")
        except FileNotFoundError as exc:
            result.status = "probe_unavailable"
            result.warnings.append(str(exc))
        except subprocess.TimeoutExpired:
            result.status = "probe_timeout"
            result.warnings.append(f"ffprobe exceeded {timeout_seconds} seconds.")
        except (ValueError, OSError) as exc:
            result.status = "probe_failed"
            result.warnings.append(str(exc))
        return result

    if family == "image":
        if signature == "unverified-extension":
            result.warnings.append("Image extension is unverified; content signature was not recognized.")
        result.metadata = _image_metadata(path)
        result.status = "signature_detected" if signature != "unverified-extension" else "needs_validation"
        if signature == "dng-tiff":
            result.warnings.append("DNG is TIFF-based; RAW decode support must be verified separately.")
        if signature == "tiff":
            result.warnings.append("TIFF signature alone cannot distinguish ordinary TIFF from every TIFF-based RAW variant.")
        return result

    if family == "lut":
        result.status = "candidate"
        result.warnings.append("LUT parsing and input/output color-space validation are not implemented yet.")
        return result

    result.status = "unsupported_or_unknown"
    result.warnings.append("No supported media signature or recognized extension was found.")
    return result
