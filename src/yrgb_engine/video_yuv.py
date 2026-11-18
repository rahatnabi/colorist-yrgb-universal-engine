"""Native planar YUV frame extraction and code-value measurements.

The decoder requests the stream's reported planar YUV pixel format from FFmpeg.
Measurements remain in integer code-value domains; no range expansion, matrix
conversion, transfer-function decode, or camera Log interpretation is applied.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .oiio_decoder import HighPrecisionDecodeError

_PIXEL_FORMAT = re.compile(r"^yuv(j?)(420|422|444)p(?:(9|10|12|14|16)(le|be))?$")
_SUBSAMPLING = {"420": (2, 2), "422": (2, 1), "444": (1, 1)}


@dataclass(frozen=True, slots=True)
class YUVPlaneStatistics:
    minimum_code_value: int
    maximum_code_value: int
    mean_code_value: float
    sample_count: int
    below_threshold_count: int | None
    above_threshold_count: int | None
    threshold_denominator: int | None


@dataclass(frozen=True, slots=True)
class DecodedYUVFrame:
    width: int
    height: int
    pixel_format: str
    bit_depth: int
    byte_order: str
    range_signaling: str
    matrix_signaling: str
    transfer_signaling: str
    primaries_signaling: str
    timestamp_seconds: float
    decoder: str
    planes: Mapping[str, Any]

    def to_report(self, *, thresholds: Mapping[str, tuple[int, int]] | None = None) -> dict:
        """Return auditable per-plane code-value statistics and denominators."""
        try:
            import numpy as np
        except ImportError as exc:
            raise HighPrecisionDecodeError("NumPy is required for YUV measurements.") from exc
        plane_stats: dict[str, dict] = {}
        for name, plane in self.planes.items():
            low_high = (thresholds or {}).get(name)
            below = above = denominator = None
            if low_high is not None:
                low, high = low_high
                if low >= high:
                    raise ValueError(f"{name} threshold low must be below high.")
                below = int(np.count_nonzero(plane < low))
                above = int(np.count_nonzero(plane > high))
                denominator = int(plane.size)
            stats = YUVPlaneStatistics(
                minimum_code_value=int(plane.min()),
                maximum_code_value=int(plane.max()),
                mean_code_value=float(plane.mean(dtype=np.float64)),
                sample_count=int(plane.size),
                below_threshold_count=below,
                above_threshold_count=above,
                threshold_denominator=denominator,
            )
            plane_stats[name] = asdict(stats)
        return {
            "measurement_domain": "original_yuv_code_values",
            "status": "decoded_measurement",
            "width": self.width, "height": self.height,
            "pixel_format": self.pixel_format, "bit_depth": self.bit_depth,
            "byte_order": self.byte_order,
            "range_signaling": self.range_signaling,
            "matrix_signaling": self.matrix_signaling,
            "transfer_signaling": self.transfer_signaling,
            "primaries_signaling": self.primaries_signaling,
            "timestamp_seconds": self.timestamp_seconds,
            "decoder": self.decoder, "planes": plane_stats,
            "interpretation_limits": [
                "Values are decoded integer YUV code values, not RGB or linear-light values.",
                "Range signaling is reported separately; no legal-range normalization is applied.",
                "Threshold counts are emitted only for caller-supplied per-plane thresholds.",
                "Decoder success does not validate camera Log, gamut, or colorimetric accuracy.",
            ],
        }


def _probe_stream(path: Path, timeout_seconds: int) -> dict:
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
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HighPrecisionDecodeError("ffprobe timed out while inspecting the video.") from exc
    if result.returncode:
        raise HighPrecisionDecodeError(result.stderr.strip() or "ffprobe failed.")
    try:
        streams = json.loads(result.stdout).get("streams", [])
        stream = streams[0]
        stream["width"], stream["height"] = int(stream["width"]), int(stream["height"])
        return stream
    except (json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError) as exc:
        raise HighPrecisionDecodeError("No valid first video stream was reported.") from exc


def _pixel_layout(pixel_format: str) -> tuple[int, str, int, int]:
    match = _PIXEL_FORMAT.fullmatch(pixel_format or "")
    if not match:
        raise HighPrecisionDecodeError(
            f"Unsupported pixel format {pixel_format!r}; supports planar 4:2:0, 4:2:2 "
            "and 4:4:4 at 8/9/10/12/14/16-bit."
        )
    _, subsampling, depth_text, endian = match.groups()
    bit_depth = int(depth_text) if depth_text else 8
    byte_order = endian or "8-bit"
    sx, sy = _SUBSAMPLING[subsampling]
    return bit_depth, byte_order, sx, sy


def decode_video_yuv_frame(
    file_path: str | Path,
    *,
    timestamp_seconds: float = 0.0,
    max_pixels: int = 40_000_000,
    timeout_seconds: int = 30,
) -> DecodedYUVFrame:
    """Decode one frame in its reported planar YUV format without RGB conversion."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise HighPrecisionDecodeError(f"File not found: {path}")
    if not math.isfinite(timestamp_seconds) or timestamp_seconds < 0:
        raise ValueError("timestamp_seconds must be finite and zero or greater.")
    try:
        import numpy as np
    except ImportError as exc:
        raise HighPrecisionDecodeError("NumPy is required. Install the 'high-precision' extra.") from exc

    stream = _probe_stream(path, timeout_seconds)
    width, height = stream["width"], stream["height"]
    if width <= 0 or height <= 0:
        raise HighPrecisionDecodeError("Video dimensions must be positive.")
    if width * height > max_pixels:
        raise HighPrecisionDecodeError(
            f"Video frame has {width * height} pixels; configured limit is {max_pixels}."
        )
    pixel_format = str(stream.get("pix_fmt") or "")
    bit_depth, byte_order, sx, sy = _pixel_layout(pixel_format)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HighPrecisionDecodeError("ffmpeg was not found on PATH; install FFmpeg.")
    command = [
        ffmpeg, "-v", "error", "-ss", str(timestamp_seconds), "-i", str(path),
        "-map", "0:v:0", "-frames:v", "1", "-f", "rawvideo",
        "-pix_fmt", pixel_format, "pipe:1",
    ]
    try:
        result = subprocess.run(command, capture_output=True,
                                timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HighPrecisionDecodeError("FFmpeg timed out while decoding the YUV frame.") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise HighPrecisionDecodeError(detail or "FFmpeg could not decode native YUV frame.")

    chroma_width = (width + sx - 1) // sx
    chroma_height = (height + sy - 1) // sy
    shapes = {"Y": (height, width), "U": (chroma_height, chroma_width),
              "V": (chroma_height, chroma_width)}
    bytes_per_sample = 1 if bit_depth == 8 else 2
    expected = sum(h * w for h, w in shapes.values()) * bytes_per_sample
    if len(result.stdout) != expected:
        raise HighPrecisionDecodeError(
            f"Native YUV frame size mismatch: expected {expected} bytes, received {len(result.stdout)}."
        )

    dtype = np.dtype("u1") if bit_depth == 8 else np.dtype("<u2" if byte_order == "le" else ">u2")
    samples = np.frombuffer(result.stdout, dtype=dtype)
    planes: dict[str, Any] = {}
    offset = 0
    for name, shape in shapes.items():
        count = shape[0] * shape[1]
        planes[name] = samples[offset:offset + count].reshape(shape).copy()
        offset += count

    return DecodedYUVFrame(
        width, height, pixel_format, bit_depth, byte_order,
        str(stream.get("color_range") or "unknown"),
        str(stream.get("color_space") or "unknown"),
        str(stream.get("color_transfer") or "unknown"),
        str(stream.get("color_primaries") or "unknown"),
        timestamp_seconds, "FFmpeg/native-planar-YUV", planes,
    )
