# Decoder Layer — Initial Preview Adapters

## Current adapters
- Still images: Pillow converts supported files to RGB24.
- Video: FFprobe reads first-stream dimensions and color metadata; FFmpeg decodes one selected frame to RGB24.
- Common output: DecodedFrame carries dimensions, pixel format, bytes, source path, decoder identity, purpose, and source metadata.
- Capability report: detects FFmpeg, FFprobe, Pillow, rawpy, OpenImageIO, and PyOpenColorIO. Availability does not mean a decoder adapter or full format support exists.

## Precision limitation
RGB24 is an 8-bit preview representation. Conversion may discard source bit depth, chroma precision, RAW sensor data, and source color encoding. It is not the authoritative grading buffer and must not feed final color transforms or high-quality export.

The production path needs a precision-preserving representation (for example, documented 16-bit integer or 32-bit floating-point channels), explicit transfer/gamut metadata, and validated color conversions. OpenImageIO and LibRaw adapters remain planned.

## Video color metadata
The video adapter records FFprobe fields such as pixel format, color range, matrix/colorspace, transfer, and primaries. FFmpeg RGB24 conversion is only for viewing, not a color-managed scene-referred transform.

## Safeguards
- Default maximum frame size: 40 million pixels.
- Video decoding is limited to one requested frame per call.
- FFprobe/FFmpeg operations have timeouts.
- Source files are never modified.
- Unsupported codec, corrupt file, missing binary, and size-limit errors are reported.
