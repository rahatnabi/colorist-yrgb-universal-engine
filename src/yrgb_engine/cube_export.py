"""Generate portable 3D .cube LUTs from an explicit RGB transform."""
from __future__ import annotations

from collections.abc import Callable
from math import isfinite

from .cube import CubeLUT
from .lut import apply_cube_rgb

RGBTransform = Callable[[tuple[float, float, float]], tuple[float, float, float]]
SUPPORTED_3D_SIZES = (17, 33, 35, 65)


class CubeExportError(ValueError):
    """Raised when a requested .cube export is invalid."""


def generate_cube_text(
    transform: RGBTransform,
    *,
    size: int = 33,
    title: str = "COLORIST YRGB Look",
    domain_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
    domain_max: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> str:
    """Sample an RGB transform into a 3D LUT.

    Entries are written in .cube order: blue varies fastest, then green, then red.
    Transform outputs are not clamped; a downstream display/export transform is
    responsible for mapping values to the destination display range.
    """
    if size not in SUPPORTED_3D_SIZES:
        raise CubeExportError(f"Unsupported LUT size {size}; choose one of {SUPPORTED_3D_SIZES}.")
    if len(domain_min) != 3 or len(domain_max) != 3:
        raise CubeExportError("LUT domains must contain three RGB values.")
    if not all(isfinite(v) for v in (*domain_min, *domain_max)):
        raise CubeExportError("LUT domain values must be finite.")
    if any(low >= high for low, high in zip(domain_min, domain_max)):
        raise CubeExportError("Each DOMAIN_MIN value must be lower than DOMAIN_MAX.")
    safe_title = title.replace('"', "'").replace("\\n", " ").strip() or "COLORIST YRGB Look"
    lines = [
        f'TITLE "{safe_title}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN " + " ".join(f"{v:.9g}" for v in domain_min),
        "DOMAIN_MAX " + " ".join(f"{v:.9g}" for v in domain_max),
    ]
    for red_index in range(size):
        red = domain_min[0] + (domain_max[0] - domain_min[0]) * red_index / (size - 1)
        for green_index in range(size):
            green = domain_min[1] + (domain_max[1] - domain_min[1]) * green_index / (size - 1)
            for blue_index in range(size):
                blue = domain_min[2] + (domain_max[2] - domain_min[2]) * blue_index / (size - 1)
                output = transform((red, green, blue))
                if len(output) != 3 or not all(isfinite(v) for v in output):
                    raise CubeExportError("Transform must return three finite RGB values.")
                lines.append(" ".join(f"{v:.9g}" for v in output))
    return "\n".join(lines) + "\n"


def resample_cube_text(
    source: CubeLUT,
    *,
    size: int = 33,
    title: str = "COLORIST YRGB Look",
) -> str:
    """Resample an imported 1D/3D/combined .cube LUT to a portable 3D LUT."""
    return generate_cube_text(
        lambda rgb: apply_cube_rgb(rgb, source),
        size=size,
        title=title,
        domain_min=source.domain_min,
        domain_max=source.domain_max,
    )
