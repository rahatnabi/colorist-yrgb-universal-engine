"""Explicit OpenColorIO CPU transforms for precision frames.

The caller must supply exact source and destination color-space names. This
module never guesses a camera profile and never silently applies a default.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .precision import PrecisionFrame


class ColorTransformError(RuntimeError):
    """Raised when an explicit color transform cannot be created or applied."""


def _load_ocio(config_path: str | Path | None) -> Any:
    try:
        import PyOpenColorIO as ocio
    except ImportError as exc:
        raise ColorTransformError(
            "PyOpenColorIO is not installed. Install the ocio optional dependency."
        ) from exc
    if config_path is None:
        try:
            config = ocio.GetCurrentConfig()
        except Exception as exc:
            raise ColorTransformError(f"Cannot load the current OCIO config: {exc}") from exc
    else:
        path = Path(config_path)
        if not path.is_file():
            raise ColorTransformError(f"OCIO config does not exist: {path}")
        try:
            config = ocio.Config.CreateFromFile(str(path))
        except Exception as exc:
            raise ColorTransformError(f"Cannot load OCIO config '{path}': {exc}") from exc
    return ocio, config


def transform_frame(
    frame: PrecisionFrame,
    *,
    source_space: str,
    destination_space: str,
    config_path: str | Path | None = None,
) -> PrecisionFrame:
    """Transform RGB pixels using explicit OCIO config and color-space names.

    Alpha and auxiliary channels are preserved. The input is not mutated.
    Reference validation remains false until independently measured.
    """
    if not source_space.strip() or not destination_space.strip():
        raise ValueError("Source and destination color-space names are required.")
    names = [name.upper() for name in frame.channel_names]
    if not all(name in names for name in ("R", "G", "B")):
        raise ColorTransformError("OCIO transforms require named R, G and B channels.")

    ocio, config = _load_ocio(config_path)
    try:
        processor = config.getProcessor(source_space, destination_space)
        cpu = processor.getDefaultCPUProcessor()
    except Exception as exc:
        raise ColorTransformError(
            f"OCIO cannot build '{source_space}' -> '{destination_space}': {exc}"
        ) from exc

    indices = tuple(names.index(channel) for channel in ("R", "G", "B"))
    output = frame.samples[:]
    try:
        for offset in range(0, len(output), frame.channel_count):
            rgb = [output[offset + index] for index in indices]
            cpu.applyRGB(rgb)
            for index, value in zip(indices, rgb):
                output[offset + index] = value
    except Exception as exc:
        raise ColorTransformError(f"OCIO failed while processing frame pixels: {exc}") from exc

    encoding = replace(
        frame.encoding,
        profile_id=destination_space,
        metadata_source="explicit OpenColorIO transform",
        validated=False,
    )
    metadata = dict(frame.metadata)
    metadata.update({
        "ocio_source_space": source_space,
        "ocio_destination_space": destination_space,
        "ocio_config": str(config_path) if config_path is not None else "current-config",
        "ocio_reference_validated": False,
    })
    return PrecisionFrame(
        width=frame.width,
        height=frame.height,
        channel_names=frame.channel_names,
        samples=output,
        source_path=frame.source_path,
        decoder=f"{frame.decoder}+OpenColorIO",
        encoding=encoding,
        sample_domain="ocio_transformed_float32",
        purpose=frame.purpose,
        metadata=metadata,
    )
