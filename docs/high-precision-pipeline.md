# High-Precision Decode Pipeline — Foundation

## Canonical frame contract

`PrecisionFrame` stores interleaved float32 samples in an `array('f')` buffer. It records dimensions, channel names, decoder identity, source path, and a separate `ColorEncoding` descriptor.

The frame model deliberately:
- preserves finite negative and greater-than-one values;
- does not clamp, normalize, apply a LUT, or perform a color-space transform;
- rejects NaN and infinity;
- requires an exact buffer size and unique channel names;
- keeps unknown primaries, transfer, matrix, range, and reference state explicitly unknown.

## OpenImageIO adapter

The optional `decode_oiio_float` adapter requests float32 pixels from OpenImageIO. It is intended as the first high-bit-depth still-image path for formats supported by the user's OpenImageIO build and plugins.

Requesting float32 does not prove that returned values are scene-linear, normalized, or in a particular gamut. The adapter labels the sample domain as uncharacterized and does not infer colorimetry from filenames.

## LibRaw adapter

The optional `decode_raw_camera_rgb` adapter asks LibRaw to demosaic supported RAW stills into 16-bit camera-native RGB with a linear gamma request and no automatic brightness. Values are represented as float32 while retaining the 16-bit output code-value scale; they are not normalized to [0, 1].

This output is **not** the original sensor mosaic. It is a demosaiced camera-native candidate and still requires camera-specific characterization, white-balance policy, and validated transforms before grading. Camera model metadata is recorded when available; a camera Log profile is never guessed from a RAW filename.

## Image sequences

`decode_oiio_sequence_float` streams numbered sequence frames in index order and yields one `PrecisionFrame` at a time. It rejects missing frame indices by default and verifies that dimensions and channel names remain consistent across the sequence.

## Not yet implemented

- Precision-preserving video frame decoder.
- Color-managed input transforms and OCIO configuration.
- Reference-image comparisons for every supported format.
- High-precision export and round-trip tests.

## Validation requirement

Before a decoder is promoted to the production grading path, validate known test assets for channel order, alpha behavior, sample-value interpretation, orientation, metadata preservation, and numerical agreement against a trusted reference decoder.
