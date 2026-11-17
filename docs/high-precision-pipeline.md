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

Important: requesting float32 does not by itself prove that the returned values are scene-linear, normalized, or in a particular gamut. The adapter labels the sample domain as uncharacterized and does not infer colorimetry from filenames.

## Not yet implemented

- LibRaw sensor/RAW decode adapter.
- Precision-preserving video frame decoder.
- Color-managed input transforms and OCIO configuration.
- Reference-image comparisons for every supported format.
- High-precision export and round-trip tests.

## Validation requirement

Before a decoder is promoted to the production grading path, validate known test assets for channel order, alpha behavior, sample-value interpretation, orientation, metadata preservation, and numerical agreement against a trusted reference decoder.
