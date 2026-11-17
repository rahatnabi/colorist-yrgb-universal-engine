"""Precision-preserving in-memory frame model for grading operations.

Samples are stored as native float32 values. Values are never clamped to [0, 1]:
scene-referred/HDR workflows may legitimately contain negative or >1 values.
This model is a buffer contract, not a color transform.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass, field
from math import isfinite
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ColorEncoding:
    """Explicit source encoding description; unknown values remain unknown."""

    primaries: str = "unknown"
    transfer: str = "unknown"
    matrix: str = "unknown"
    range: str = "unknown"
    reference: str = "unknown"  # scene_referred | display_referred | unknown
    source_bit_depth: int | None = None
    chroma_subsampling: str | None = None
    profile_id: str | None = None
    metadata_source: str = "unspecified"
    validated: bool = False


@dataclass(slots=True)
class PrecisionFrame:
    """Interleaved float32 image frame with explicit channel and color metadata."""

    width: int
    height: int
    channel_names: tuple[str, ...]
    samples: array
    source_path: str
    decoder: str
    encoding: ColorEncoding = field(default_factory=ColorEncoding)
    sample_domain: str = "decoder_float_output"
    purpose: str = "grading_candidate"
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Frame dimensions must be positive.")
        if not self.channel_names:
            raise ValueError("At least one channel name is required.")
        if len(set(self.channel_names)) != len(self.channel_names):
            raise ValueError("Channel names must be unique.")
        if self.samples.typecode != "f":
            raise TypeError("Samples must use array('f') float32 storage.")
        expected = self.width * self.height * len(self.channel_names)
        if len(self.samples) != expected:
            raise ValueError(f"Expected {expected} samples, received {len(self.samples)}.")
        if not all(isfinite(value) for value in self.samples):
            raise ValueError("Frame samples must be finite; NaN and infinity are not accepted.")

    @property
    def channel_count(self) -> int:
        return len(self.channel_names)

    @property
    def bytes_per_sample(self) -> int:
        return self.samples.itemsize

    @property
    def buffer_bytes(self) -> int:
        return len(self.samples) * self.samples.itemsize

    def pixel(self, x: int, y: int) -> tuple[float, ...]:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError("Pixel coordinates are outside the frame.")
        start = (y * self.width + x) * self.channel_count
        return tuple(self.samples[start : start + self.channel_count])

    @classmethod
    def from_interleaved(
        cls,
        *,
        width: int,
        height: int,
        channel_names: Iterable[str],
        values: Iterable[float],
        source_path: str,
        decoder: str,
        encoding: ColorEncoding | None = None,
        sample_domain: str = "decoder_float_output",
        purpose: str = "grading_candidate",
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> "PrecisionFrame":
        """Construct a float32 frame without clamping or applying color transforms."""
        return cls(
            width=width,
            height=height,
            channel_names=tuple(channel_names),
            samples=array("f", values),
            source_path=source_path,
            decoder=decoder,
            encoding=encoding or ColorEncoding(),
            sample_domain=sample_domain,
            purpose=purpose,
            metadata=metadata or {},
        )
