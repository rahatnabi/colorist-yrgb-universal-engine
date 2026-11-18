"""Small, clearly synthetic still-image practice assets."""
from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def neutral_practice_chart_png() -> bytes:
    """Build a deterministic educational chart; never a measured reference target."""
    width, height = 640, 360
    rows = []
    swatches = (
        (32, 32, 32), (64, 64, 64), (118, 118, 118),
        (180, 180, 180), (224, 224, 224), (240, 190, 150),
        (110, 150, 190), (145, 170, 120),
    )
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if y < 150:
                value = int(16 + 220 * x / (width - 1))
                rgb = (value, value, value)
            elif y < 300:
                index = min(len(swatches) - 1, x * len(swatches) // width)
                rgb = swatches[index]
            else:
                checker = 36 if ((x // 24) + (y // 20)) % 2 else 72
                rgb = (checker, checker, checker)
            row.extend(rgb)
        rows.append(bytes(row))
    raw = b"".join(rows)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
