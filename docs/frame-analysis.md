# Frame analysis core

The `yrgb_engine.analysis` module analyzes the same `PrecisionFrame` contract
used by still-image decoders and video-frame decoders. It is a numerical data
engine, not a GUI scope renderer.

## Available measurements

- Per-channel RGB minimum, maximum, mean, and sample count.
- Per-channel histograms with explicit value range and separate underflow/overflow.
- RGB Parade raster counts and an optional luma waveform raster.
- Optional linear-light luminance statistics and a numeric 18% gray-reference
  comparison, only when the caller explicitly declares linear RGB and supplies
  RGB-to-Y coefficients.
- Optional clipping counts using caller-supplied thresholds.
- Optional Cb/Cr vectorscope points using caller-supplied luma coefficients.

## Color-science guardrails

No source transfer function, primaries, matrix, range, or camera Log profile is
inferred. The default waveform is absent until explicit waveform coefficients
are provided. RGB Parade and histogram values remain in the frame's sample
domain; they are not automatically IRE or legal/video levels.

The luminance path is deliberately stricter: it requires `linear_rgb=True`
and explicit coefficients. A Log-encoded or display-encoded frame must first
receive a verified transform into a known linear working space. The 18% gray
reference is then compared numerically against mean calculated luminance; it
is not a universal encoded RGB code value or a per-pixel gray detector.

Clipping counts are only meaningful relative to thresholds selected for the
known source domain. Negative and above-one float values are retained and are
not inherently classified as clipped. Vectorscope coordinates are derived
from explicit coefficients; choosing the wrong coefficients produces the
wrong chroma interpretation.

## Current limitations

- No GUI rendering, GPU acceleration, temporal scopes, or video playback UI.
- No automatic camera-profile selection or implicit Log-to-Rec.709 conversion.
- Waveform is a horizontal raster of the explicitly weighted signal, not yet
  calibrated to IRE.
- Vectorscope point sampling is capped by `max_vectorscope_points` for large
  frames; it is a point-cloud payload, not a density-rendered scope.
- The 18% gray metric is a frame-average comparison, not a spatial gray-card
  detector or exposure recommendation.

The module can consume decoded stills and individual decoded video frames
without changing the decoder's sample values or source metadata.
