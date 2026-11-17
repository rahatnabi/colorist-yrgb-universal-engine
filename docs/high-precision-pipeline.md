# High-Precision Decode Pipeline — Foundation

## Canonical frame contract

`PrecisionFrame` stores interleaved float32 samples in an `array('f')` buffer. It records dimensions, channel names, decoder identity, source path, and a separate `ColorEncoding` descriptor.

The frame model preserves finite negative and greater-than-one values; does not clamp, normalize, apply a LUT, or perform a color-space transform; rejects NaN and infinity; and keeps unknown colorimetry explicitly unknown.

## OpenImageIO still-image adapter

The optional `decode_oiio_float` adapter requests float32 pixels from OpenImageIO for formats supported by the installed build/plugins. Requesting float32 does not prove the values are scene-linear, normalized, or in a particular gamut. Colorimetry is not inferred from filenames.

## LibRaw adapter

The optional `decode_raw_camera_rgb` adapter asks LibRaw to demosaic supported RAW stills into 16-bit camera-native RGB with a linear gamma request and no automatic brightness. Values are represented as float32 while retaining the 16-bit output code-value scale; they are not normalized to [0, 1].

This is not the original sensor mosaic. It is a demosaiced camera-native candidate and still requires camera-specific characterization, white-balance policy, and validated transforms before grading.

## Video adapter

The optional `decode_video_float_frame` adapter asks FFmpeg for one float32 planar GBR frame and reorders it into interleaved RGB. It preserves source transfer and primaries as metadata and records the original matrix/range separately. It does **not** convert Log to linear or to DaVinci Wide Gamut / Intermediate. FFmpeg's RGB conversion behavior must be verified against known test clips for each supported codec and color range before production use.

## Image sequences

`decode_oiio_sequence_float` streams numbered sequence frames in index order and yields one `PrecisionFrame` at a time. It rejects missing frame indices by default and verifies that dimensions and channel names remain consistent.

## Not yet production-validated

- Numerical parity against trusted decoders for EXR, DPX, TIFF, RAW, and video.
- OCIO input transforms and a pinned, versioned configuration.
- Alpha, chroma, interlacing, HDR metadata, orientation, and range edge-case validation.
- High-precision export and round-trip tests.

Every adapter remains a grading candidate until these validations pass.
