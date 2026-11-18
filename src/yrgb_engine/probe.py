"""Media probing with conservative signature checks and optional ffprobe/Pillow."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import MediaProbeResult
from .signatures import detect_signature

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024 * 1024
_BIT_DEPTH_SUFFIX = re.compile(r"(?:p|rgb|gbr)(9|10|12|14|16)(?:le|be)?$", re.IGNORECASE)


def _read_header(path: Path, length: int = 32) -> bytes:
    with path.open("rb") as stream:
        return stream.read(length)


def _run_ffprobe(path: Path, timeout: int) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise FileNotFoundError("ffprobe executable was not found on PATH")
    command = [executable, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=timeout)
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


def _scalar_tags(*tag_sets: Any) -> dict[str, str]:
    """Merge metadata tags as strings without interpreting vendor-specific names."""
    merged: dict[str, str] = {}
    for tags in tag_sets:
        if not isinstance(tags, dict):
            continue
        for key, value in tags.items():
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                merged[str(key).casefold()] = str(value)
    return merged


def _first_tag(tags: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = tags.get(name.casefold())
        if value and value.strip():
            return value.strip()
    return None


def _reported_bit_depth(stream: dict[str, Any]) -> int | None:
    for key in ("bits_per_raw_sample", "bits_per_coded_sample", "bits_per_sample"):
        try:
            depth = int(stream.get(key))
        except (TypeError, ValueError):
            continue
        if 1 <= depth <= 64:
            return depth
    pixel_format = stream.get("pix_fmt")
    if isinstance(pixel_format, str):
        match = _BIT_DEPTH_SUFFIX.search(pixel_format)
        if match:
            return int(match.group(1))
    return None


def extract_capture_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract only explicitly reported camera/capture facts; unknowns stay null."""
    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        streams = []
    video_stream = next(
        (stream for stream in streams if isinstance(stream, dict)
         and stream.get("codec_type") == "video"),
        {},
    )
    format_info = payload.get("format")
    if not isinstance(format_info, dict):
        format_info = {}
    tags = _scalar_tags(format_info.get("tags"), video_stream.get("tags"))
    codec = video_stream.get("codec_name")
    pixel_format = video_stream.get("pix_fmt")
    model = _first_tag(tags, "model", "camera_model")
    recording_mode = _first_tag(
        tags, "recording_mode", "record_mode", "shooting_mode", "video_mode"
    )
    bit_depth = _reported_bit_depth(video_stream)
    return {
        "camera_make": _first_tag(tags, "make", "manufacturer", "camera_make"),
        "camera_model": model,
        "recording_mode": recording_mode,
        "codec": codec if isinstance(codec, str) and codec else None,
        "codec_profile": video_stream.get("profile") if isinstance(video_stream.get("profile"), str) else None,
        "codec_tag": video_stream.get("codec_tag_string") if isinstance(video_stream.get("codec_tag_string"), str) else None,
        "pixel_format": pixel_format if isinstance(pixel_format, str) else None,
        "bit_depth": bit_depth,
        "color_transfer": video_stream.get("color_transfer"),
        "color_primaries": video_stream.get("color_primaries"),
        "color_matrix": video_stream.get("color_space"),
        "color_range": video_stream.get("color_range"),
        "firmware_version": _first_tag(tags, "firmware_version", "firmware", "camera_firmware"),
        "metadata_tags": tags,
        "metadata_completeness": {
            "camera_model": model is not None,
            "recording_mode": recording_mode is not None,
            "codec": isinstance(codec, str) and bool(codec),
            "bit_depth": bit_depth is not None,
        },
        "interpretation": (
            "Metadata reported by the container/stream only. Missing values are unknown; "
            "camera model, recording mode, Log curve, and gamut are never inferred."
        ),
    }


def _image_metadata(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        return {"metadata_reader": "unavailable", "note": "Install the 'images' extra for Pillow metadata."}
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            tags = {str(key): value for key, value in exif.items()}
            make, model = exif.get(271), exif.get(272)
            def text_value(value: Any) -> str | None:
                if value is None:
                    return None
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="replace").strip() or None
                return str(value).strip() or None
            def rational(value: Any) -> str | None:
                try:
                    return f"{float(value):.4g}"
                except (TypeError, ValueError, ZeroDivisionError):
                    return text_value(value)
            capture = {
                "camera_make": text_value(make), "camera_model": text_value(model),
                "recording_mode": None, "codec": None, "bit_depth": None,
                "lens_model": text_value(exif.get(42036)),
                "iso": text_value(exif.get(34855)),
                "shutter_speed": rational(exif.get(33434)),
                "aperture": rational(exif.get(33437)),
                "focal_length_mm": rational(exif.get(37386)),
                "white_balance": text_value(exif.get(41987)),
                "capture_datetime": text_value(exif.get(36867) or exif.get(306)),
                "firmware_version": text_value(exif.get(305)),
                "color_space": text_value(exif.get(40961)),
                "metadata_tags": tags,
                "interpretation": "EXIF values only. Log/gamut tags may be absent; missing values are unknown and are never inferred.",
            }
            return {
                "metadata_reader": "Pillow", "format": image.format,
                "width": image.width, "height": image.height, "mode": image.mode,
                "frames": getattr(image, "n_frames", 1),
                "icc_profile_present": bool(image.info.get("icc_profile")),
                "capture_metadata": capture,
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
    result = MediaProbeResult(path=str(path), exists=path.is_file(), extension=suffix)
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
    result.detected_type, result.signature = family, signature
    if family == "video":
        if signature == "unverified-extension":
            result.warnings.append("Video extension is unverified; container signature was not recognized.")
        try:
            payload = _run_ffprobe(path, timeout_seconds)
            result.metadata = payload
            streams = payload.get("streams", [])
            result.status = "probed"
            result.metadata["capture_metadata"] = extract_capture_metadata(payload)
            result.metadata["stream_summary"] = [
                {
                    "index": stream.get("index"), "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name"), "profile": stream.get("profile"),
                    "codec_tag_string": stream.get("codec_tag_string"),
                    "width": stream.get("width"), "height": stream.get("height"),
                    "pix_fmt": stream.get("pix_fmt"), "bit_depth": _reported_bit_depth(stream),
                    "bit_rate": stream.get("bit_rate"), "avg_frame_rate": stream.get("avg_frame_rate"),
                    "color_space": stream.get("color_space"),
                    "color_transfer": stream.get("color_transfer"),
                    "color_primaries": stream.get("color_primaries"),
                    "color_range": stream.get("color_range"),
                }
                for stream in streams if isinstance(stream, dict)
            ]
            if not any(isinstance(s, dict) and s.get("codec_type") == "video" for s in streams):
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
