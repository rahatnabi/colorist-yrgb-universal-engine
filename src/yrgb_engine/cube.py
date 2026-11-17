"""Strict reader for the common Iridas .cube 1D/3D LUT text format."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path


class CubeLUTError(ValueError):
    """Raised when a .cube LUT is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class CubeLUT:
    title: str | None
    size_1d: int | None
    size_3d: int | None
    domain_min: tuple[float, float, float]
    domain_max: tuple[float, float, float]
    values_1d: tuple[tuple[float, float, float], ...]
    values_3d: tuple[tuple[float, float, float], ...]

    @property
    def kind(self) -> str:
        if self.size_1d and self.size_3d:
            return "1d+3d"
        return "1d" if self.size_1d else "3d"


def parse_cube_text(text: str) -> CubeLUT:
    """Parse LUT metadata and RGB entries; this does not interpolate or apply."""
    title = None
    size_1d = None
    size_3d = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    data: list[tuple[float, float, float]] = []
    seen_data = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        key = parts[0].upper()
        try:
            if key == "TITLE":
                if seen_data or title is not None:
                    raise CubeLUTError("TITLE must appear once before LUT data.")
                title = line[len(parts[0]):].strip().strip('"')
            elif key in {"LUT_1D_SIZE", "LUT_3D_SIZE"}:
                if seen_data or len(parts) != 2:
                    raise CubeLUTError(f"Invalid {key} declaration.")
                size = int(parts[1])
                if size < 2:
                    raise CubeLUTError(f"{key} must be at least 2.")
                if key == "LUT_1D_SIZE":
                    if size_1d is not None:
                        raise CubeLUTError("Duplicate LUT_1D_SIZE.")
                    size_1d = size
                else:
                    if size_3d is not None:
                        raise CubeLUTError("Duplicate LUT_3D_SIZE.")
                    size_3d = size
            elif key in {"DOMAIN_MIN", "DOMAIN_MAX"}:
                if seen_data or len(parts) != 4:
                    raise CubeLUTError(f"Invalid {key} declaration.")
                values = tuple(float(value) for value in parts[1:])
                if not all(isfinite(value) for value in values):
                    raise CubeLUTError(f"{key} values must be finite.")
                if key == "DOMAIN_MIN":
                    domain_min = values
                else:
                    domain_max = values
            else:
                if len(parts) != 3:
                    raise CubeLUTError("LUT entries must contain exactly three values.")
                values = tuple(float(value) for value in parts)
                if not all(isfinite(value) for value in values):
                    raise CubeLUTError("LUT values must be finite.")
                seen_data = True
                data.append(values)
        except CubeLUTError as exc:
            raise CubeLUTError(f"Line {line_number}: {exc}") from exc
        except (ValueError, OverflowError) as exc:
            raise CubeLUTError(f"Invalid value on line {line_number}: {raw_line}") from exc

    if size_1d is None and size_3d is None:
        raise CubeLUTError("A LUT_1D_SIZE or LUT_3D_SIZE declaration is required.")
    if any(low >= high for low, high in zip(domain_min, domain_max)):
        raise CubeLUTError("Each DOMAIN_MIN value must be lower than DOMAIN_MAX.")
    expected = (size_1d or 0) + ((size_3d or 0) ** 3)
    if len(data) != expected:
        raise CubeLUTError(f"Expected {expected} RGB entries, found {len(data)}.")

    split = size_1d or 0
    return CubeLUT(
        title=title,
        size_1d=size_1d,
        size_3d=size_3d,
        domain_min=domain_min,
        domain_max=domain_max,
        values_1d=tuple(data[:split]),
        values_3d=tuple(data[split:]),
    )


def load_cube(path: str | Path) -> CubeLUT:
    """Read and parse a UTF-8 .cube file."""
    lut_path = Path(path)
    try:
        return parse_cube_text(lut_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise CubeLUTError(f"Cannot read LUT file '{lut_path}': {exc}") from exc
