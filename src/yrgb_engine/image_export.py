"""Apply a .cube look to a validated RGB frame and render still-image files."""
from __future__ import annotations

from array import array
from pathlib import Path
from typing import Literal

from .cube import CubeLUT
from .lut import apply_cube_rgb
from .precision import ColorEncoding, PrecisionFrame

ImageFormat = Literal["JPEG", "PNG", "TIFF"]


class ImageExportError(ValueError):
    """Raised when a graded still cannot be safely rendered."""


def apply_cube_to_frame(
    frame: PrecisionFrame,
    lut: CubeLUT,
    *,
    lut_input_space_id: str,
    lut_output_space_id: str,
) -> PrecisionFrame:
    """Apply a LUT only when the frame's declared working space matches its input.

    The resulting frame is deliberately marked unvalidated: .cube files do not
    carry a reliable color-space contract, and matching a user-supplied label
    alone cannot certify the LUT's colorimetric correctness.
    """
    if not lut_input_space_id.strip() or not lut_output_space_id.strip():
        raise ImageExportError("Explicit LUT input and output space IDs are required.")
    if not frame.encoding.validated or not frame.encoding.working_space_id:
        raise ImageExportError("Input frame must have a validated working-space transform.")
    if frame.encoding.working_space_id != lut_input_space_id:
        raise ImageExportError(
            f"Frame space '{frame.encoding.working_space_id}' does not match LUT input "
            f"space '{lut_input_space_id}'."
        )
    channel_indices = {name.upper(): index for index, name in enumerate(frame.channel_names)}
    if not all(name in channel_indices for name in ("R", "G", "B")):
        raise ImageExportError("Frame must contain named R, G and B channels.")
    indices = tuple(channel_indices[name] for name in ("R", "G", "B"))
    output = array("f")
    for offset in range(0, len(frame.samples), frame.channel_count):
        pixel = list(frame.samples[offset : offset + frame.channel_count])
        rgb = tuple(pixel[index] for index in indices)
        graded = apply_cube_rgb(rgb, lut)
        for index, value in zip(indices, graded):
            pixel[index] = value
        output.extend(pixel)
    encoding = ColorEncoding(
        primaries="unknown",
        transfer="unknown",
        matrix="unknown",
        range="unknown",
        reference="unknown",
        source_bit_depth=frame.encoding.source_bit_depth,
        chroma_subsampling=frame.encoding.chroma_subsampling,
        profile_id=frame.encoding.profile_id,
        metadata_source="cube_lut_application",
        validated=False,
        working_space_id=lut_output_space_id,
        transform_id=f"cube:{lut.title or 'unnamed'}",
    )
    return PrecisionFrame(
        width=frame.width,
        height=frame.height,
        channel_names=frame.channel_names,
        samples=output,
        source_path=frame.source_path,
        decoder=frame.decoder,
        encoding=encoding,
        sample_domain="cube_lut_output_float32",
        purpose="render_candidate",
        metadata={**frame.metadata, "lut_title": lut.title or "unnamed"},
    )


def save_frame_image(
    frame: PrecisionFrame,
    output_path: str | Path,
    *,
    image_format: ImageFormat,
    output_space_id: str,
    output_transfer: str,
    quality: int = 95,
) -> Path:
    """Write an already output-transformed frame as an 8-bit JPEG, PNG or TIFF.

    This is a display/render boundary: values are clamped to [0, 1] here only.
    It does not create a missing output transform or certify the output profile.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImageExportError("Pillow is required. Install the 'images' extra.") from exc

    normalized_format = image_format.upper()
    if normalized_format not in {"JPEG", "PNG", "TIFF"}:
        raise ImageExportError("Supported still-image exports are JPEG, PNG and TIFF.")
    if not output_space_id.strip() or frame.encoding.working_space_id != output_space_id:
        raise ImageExportError("Output space ID must match the frame's declared working space.")
    if not output_transfer.strip():
        raise ImageExportError("An explicit output transfer function is required.")
    if not 1 <= quality <= 100:
        raise ImageExportError("JPEG quality must be between 1 and 100.")
    channels = {name.upper(): index for index, name in enumerate(frame.channel_names)}
    if not all(name in channels for name in ("R", "G", "B")):
        raise ImageExportError("Frame must contain named R, G and B channels.")
    alpha_index = channels.get("A")
    if normalized_format == "JPEG" and alpha_index is not None:
        raise ImageExportError("JPEG cannot preserve alpha; choose PNG or TIFF.")
    rgb_indices = tuple(channels[name] for name in ("R", "G", "B"))
    pixels: list[tuple[int, ...]] = []
    for offset in range(0, len(frame.samples), frame.channel_count):
        rgb = tuple(
            max(0.0, min(1.0, frame.samples[offset + index])) for index in rgb_indices
        )
        pixel = tuple(round(value * 255.0) for value in rgb)
        if alpha_index is not None:
            alpha = max(0.0, min(1.0, frame.samples[offset + alpha_index]))
            pixel += (round(alpha * 255.0),)
        pixels.append(pixel)
    mode = "RGBA" if alpha_index is not None else "RGB"
    image = Image.new(mode, (frame.width, frame.height))
    image.putdata(pixels)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    options = {"quality": quality, "subsampling": 0} if normalized_format == "JPEG" else {}
    image.save(destination, format=normalized_format, **options)
    return destination
