"""Streaming high-precision image-sequence decoding through OpenImageIO."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .oiio_decoder import decode_oiio_float
from .precision import PrecisionFrame
from .sequences import discover_image_sequence


class ImageSequenceDecodeError(RuntimeError):
    """Raised when an image sequence cannot be decoded consistently."""


def decode_oiio_sequence_float(
    pattern: str | Path,
    *,
    allow_gaps: bool = False,
) -> Iterator[tuple[int, PrecisionFrame]]:
    """Yield float32 frames in index order without retaining the full sequence in memory.

    Frames are decoded independently. The caller controls downstream buffering.
    """
    sequence = discover_image_sequence(pattern)
    if not sequence.frames:
        raise ImageSequenceDecodeError(f"No frames found for sequence pattern: {pattern}")
    if sequence.missing_indices and not allow_gaps:
        preview = ", ".join(str(index) for index in sequence.missing_indices[:10])
        raise ImageSequenceDecodeError(
            f"Sequence contains missing frame indices ({preview}). "
            "Set allow_gaps=True only if gaps are intentional."
        )

    reference_shape: tuple[int, int, tuple[str, ...]] | None = None
    for index, path in sequence.frames:
        try:
            frame = decode_oiio_float(path)
        except Exception as exc:
            raise ImageSequenceDecodeError(f"Failed to decode frame {index} ({path}): {exc}") from exc
        shape = (frame.width, frame.height, frame.channel_names)
        if reference_shape is None:
            reference_shape = shape
        elif shape != reference_shape:
            raise ImageSequenceDecodeError(
                f"Frame {index} has dimensions/channels {shape}; expected {reference_shape}."
            )
        frame.metadata["sequence_index"] = index
        frame.metadata["sequence_pattern"] = str(pattern)
        yield index, frame
