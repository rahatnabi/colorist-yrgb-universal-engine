"""Non-delivery display preview rendering for already transformed frames."""
from __future__ import annotations

from pathlib import Path

from .precision import PrecisionFrame


class PreviewRenderError(ValueError):
    """Raised when a frame cannot be safely rendered as a preview."""


def save_preview_png(
    frame: PrecisionFrame,
    output_path: str | Path,
    *,
    display_space_id: str,
    output_transfer: str,
) -> Path:
    """Render a preview-only PNG after an explicit display-space transform.

    This is not a mastering/export function. Values are clamped only at this
    display boundary; the source float frame remains unchanged.
    """
    if not display_space_id.strip() or not output_transfer.strip():
        raise PreviewRenderError("Explicit preview display space and transfer are required.")
    if frame.encoding.profile_id != display_space_id:
        raise PreviewRenderError("Frame does not declare the requested preview display space.")
    if frame.encoding.transfer.casefold() != output_transfer.casefold():
        raise PreviewRenderError("Preview transfer does not match the transformed frame.")
    channels = {name.upper(): index for index, name in enumerate(frame.channel_names)}
    if not all(name in channels for name in ("R", "G", "B")):
        raise PreviewRenderError("Preview frame must contain named R, G and B channels.")
    try:
        from PIL import Image
    except ImportError as exc:
        raise PreviewRenderError("Pillow is required. Install the 'images' extra.") from exc

    indices = tuple(channels[name] for name in ("R", "G", "B"))
    alpha_index = channels.get("A")
    pixels = []
    for offset in range(0, len(frame.samples), frame.channel_count):
        rgb = tuple(
            round(max(0.0, min(1.0, frame.samples[offset + index])) * 255.0)
            for index in indices
        )
        if alpha_index is not None:
            alpha = round(max(0.0, min(1.0, frame.samples[offset + alpha_index])) * 255.0)
            rgb += (alpha,)
        pixels.append(rgb)

    mode = "RGBA" if alpha_index is not None else "RGB"
    image = Image.new(mode, (frame.width, frame.height))
    image.putdata(pixels)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG")
    return destination
