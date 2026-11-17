# Decoder Layer — Initial Preview Adapters

## Purpose

The decoder layer turns media into a common frame-buffer interface while keeping still-image and video decoding separate. The first implementation is deliberately limited to interactive previews.

## Current adapters

- **Still images:** Pillow converts supported image files to RGB24.
- **Video:** FFprobe reads first-stream dimensions and color metadata; FFmpeg decodes one timestamp-selected frame to RGB24.
- **Common output:** `DecodedFrame` carries width, height, pixel format, byte buffer, source path, decoder identity, purpose, and source metadata.

## Important precision limitation

RGB24 is an 8-bit preview representation. Conversion to RGB24 may discard source bit depth, chroma precision, RAW sensor data, and source color encoding characteristics. It is not the authoritative grading buffer and must not feed final color transforms or high-quality export.

The production grading path must add a precision-preserving frame representation (for example, documented 16-bit integer or 32-bit floating-point channels), explicit transfer/gamut metadata, and validated color conversions. OpenImageIO and LibRaw adapters remain planned; this preview decoder does not claim full TIFF/DPX/EXR/RAW support.

## Video color metadata

The video adapter records FFprobe fields such as pixel format, color range, matrix/colorspace, transfer, and primaries. FFmpeg's RGB24 conversion is only for viewing. No claim is made that this conversion is a color-managed transform into a scene-referred working space.

## Limits and safeguards

- Default maximum frame size: 40 million pixels.
- Video decoding is limited to one requested frame per call.
- FFprobe/FFmpeg operations have timeouts.
- The source file is never modified.
- Unsupported codec, corrupt file, missing binary, and size-limit errors are reported rather than silently ignored.
