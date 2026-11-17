"""Canonical preview-frame container.

The initial decoder adapters emit 8-bit RGB preview buffers. This is deliberately
not the precision-preserving grading representation planned for the color core.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class DecodedFrame:
    width: int
    height: int
    pixel_format: str
    data: bytes
    source_path: str
    decoder: str
    purpose: str = "preview"
    source_metadata: dict[str, str | int | float | None] | None = None

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Frame dimensions must be positive.")
        if self.pixel_format == "rgb24" and len(self.data) != self.width * self.height * 3:
            raise ValueError("RGB24 buffer length does not match frame dimensions.")
