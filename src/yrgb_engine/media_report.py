"""Compose domain-separated single-frame measurements into the report contract.

This module combines decoded observations without treating decoder RGB as linear
light or treating container color tags as proof of camera acquisition encoding.
"""
from __future__ import annotations

from typing import Any

from .analysis import analyze_frame
from .precision import PrecisionFrame


def build_single_frame_measurement_report(
    *,
    asset_id: str,
    source_reference: str,
    source_sha256: str | None,
    frame_index: int,
    timestamp_seconds: float,
    yuv_measurement: dict[str, Any],
    rgb_frame: PrecisionFrame,
    frame_rate: str = "unknown",
) -> dict[str, Any]:
    """Build a schema-shaped report for one decoded frame.

    YUV observations remain native integer code values. FFmpeg RGB output is
    retained as decoder-converted float RGB with source transfer signaling;
    it is not promoted to linear light. No camera transform is inferred.
    """
    if not asset_id.strip() or not source_reference.strip():
        raise ValueError("asset_id and source_reference must be non-empty.")
    if frame_index < 0 or timestamp_seconds < 0:
        raise ValueError("frame_index and timestamp_seconds must be zero or greater.")
    if source_sha256 is not None:
        digest = source_sha256.lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("source_sha256 must be a 64-character hexadecimal SHA-256.")
    if yuv_measurement.get("measurement_domain") != "original_yuv_code_values":
        raise ValueError("YUV measurement must identify the original_yuv_code_values domain.")
    if yuv_measurement.get("timestamp_seconds") != timestamp_seconds:
        raise ValueError("YUV and RGB measurements must refer to the same timestamp.")

    yuv_planes = yuv_measurement.get("planes", {})
    if not {"Y", "U", "V"} <= set(yuv_planes):
        raise ValueError("YUV measurement must contain Y, U and V plane statistics.")
    yuv_channels = {
        name: {
            "min": values["minimum_code_value"],
            "max": values["maximum_code_value"],
            "mean": values["mean_code_value"],
        }
        for name, values in yuv_planes.items()
    }
    yuv_count = sum(int(values["sample_count"]) for values in yuv_planes.values())

    rgb_analysis = analyze_frame(
        rgb_frame,
        histogram_bins=16,
        scope_width=16,
        scope_height=16,
        value_range=(0.0, 1.0),
    )
    rgb_channels = {
        name: {"min": stats.minimum, "max": stats.maximum, "mean": stats.mean}
        for name, stats in rgb_analysis.channels.items()
    }
    pixel_count = rgb_frame.width * rgb_frame.height
    encoding = rgb_frame.encoding

    return {
        "report_version": 1,
        "asset_id": asset_id,
        "report_state": "reported",
        "evidence": [
            {
                "kind": "camera_original",
                "reference": source_reference,
                "sha256": source_sha256,
                "status": "reported",
                "tool": None,
                "tool_version": None,
            },
            {
                "kind": "decoded_frame",
                "reference": f"frame={frame_index};timestamp_seconds={timestamp_seconds}",
                "status": "reported",
                "tool": "FFmpeg",
                "tool_version": None,
            },
        ],
        "color_metadata": {
            "xml_declared": {},
            "stream_signaled": {
                "color_range": yuv_measurement.get("range_signaling", "unknown"),
                "matrix_coefficients": yuv_measurement.get("matrix_signaling", "unknown"),
                "transfer": yuv_measurement.get("transfer_signaling", "unknown"),
                "primaries": yuv_measurement.get("primaries_signaling", "unknown"),
            },
            "resolution_status": "unresolved",
            "resolution_notes": [
                "Stream signaling is retained as evidence, not treated as proof of camera acquisition encoding.",
                "Sidecar XML has not been reconciled in this single-frame report builder.",
            ],
        },
        "measurement_domains": {
            "original_yuv_code_values": {
                "status": "reported",
                "description": "Decoded native planar Y, U and V integer code values; decoder output not independently reference-validated.",
                "numeric_domain": (
                    f"{yuv_measurement.get('bit_depth')} bit integer code values; "
                    f"pixel format {yuv_measurement.get('pixel_format')}."
                ),
                "transfer_function": yuv_measurement.get("transfer_signaling", "unknown"),
                "matrix_coefficients": yuv_measurement.get("matrix_signaling", "unknown"),
                "range_interpretation": yuv_measurement.get("range_signaling", "unknown"),
                "conversion_method": "FFmpeg native planar YUV decode; no RGB conversion or range expansion.",
                "frames": [{
                    "frame_index": frame_index,
                    "sample_count": yuv_count,
                    "channels": yuv_channels,
                }],
            },
            "nonlinear_rgb_code_values": {
                "status": "reported",
                "description": "FFmpeg decoder-converted RGB float samples with source transfer signaling retained.",
                "numeric_domain": "float32 decoder RGB samples; not original integer RGB code values.",
                "transfer_function": encoding.transfer,
                "matrix_coefficients": yuv_measurement.get("matrix_signaling", "unknown"),
                "range_interpretation": yuv_measurement.get("range_signaling", "unknown"),
                "conversion_method": (
                    "FFmpeg gbrpf32le decode; YUV-to-RGB conversion is decoder-managed "
                    "and not reference-validated by this report."
                ),
                "frames": [{
                    "frame_index": frame_index,
                    "sample_count": pixel_count,
                    "channels": rgb_channels,
                }],
            },
            "linear_light_rgb": {
                "status": "unavailable",
                "description": "No independently validated per-pixel inverse-transfer transform was applied.",
                "numeric_domain": "not measured",
                "transfer_function": None,
                "matrix_coefficients": None,
                "range_interpretation": None,
                "conversion_method": None,
                "frames": [],
            },
        },
        "timecode": {
            "status": "unresolved",
            "frame_rate": frame_rate,
            "source_start_timecode": None,
            "mapping_method": None,
            "samples": [],
        },
        "temporal_analysis": None,
        "reference_validation": {
            "status": "not_validated",
            "reference_type": None,
            "reference_id": None,
            "notes": [
                "Decoder output and stream signaling do not validate a camera transform.",
                "A reference chart or known reference vectors are required for colorimetric validation.",
            ],
        },
    }
