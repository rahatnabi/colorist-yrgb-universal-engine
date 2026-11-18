# Native YUV frame measurements

`yrgb_engine.video_yuv` adds a separate video decode path for native
planar YUV code values. It uses `ffprobe` to read the stream's pixel
format and color signaling, then asks FFmpeg to emit one frame in that same
pixel format. Supported formats currently include planar 4:2:0, 4:2:2 and
4:4:4 at 8, 9, 10, 12, 14 and 16 bits per component.

## Measurement contract

- Y, U and V are measured independently as integer code values.
- Chroma plane dimensions follow the stream's reported subsampling.
- The report records pixel format, bit depth, byte order, range signaling,
  matrix signaling, transfer signaling and primaries signaling separately.
- Threshold counts are optional and require caller-supplied low/high thresholds.
  Each threshold report includes its own sample denominator.
- No legal-range expansion, YUV-to-RGB matrix conversion, transfer decode,
  camera Log inference or linear-light conversion occurs in this module.

This path is separate from `video_precision.decode_video_float_frame`,
which produces decoder-converted float RGB samples. The latter should be
labelled as nonlinear/decoder RGB unless a separately validated transform
establishes another domain. It must not be called `linear_light_rgb`
merely because the output is float32.

## Limits and validation

The first version extracts one timestamp-selected frame, not a complete clip.
It is a measurement foundation, not yet an automated temporal report. Exact
decoder behavior can vary by FFmpeg build; record the FFmpeg version and
command when creating a production report. A successful decode verifies
technical decodability, not camera transform accuracy.
