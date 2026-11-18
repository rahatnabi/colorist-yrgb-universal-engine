# Video frame report API

`POST /v1/media/video-report` accepts one bounded video upload.

Query parameters:
- `timestamp_seconds`: timestamp used for both decoders, default `0.0`.
- `frame_index`: caller-supplied frame index label, default `0`. It is not independently reconciled to source timecode.

The endpoint performs two independent decodes at the same timestamp:
1. Native planar YUV integer code values in `original_yuv_code_values`.
2. FFmpeg float32 RGB output in `nonlinear_rgb_code_values`; this is not described as original integer RGB or linear light.

It calculates SHA-256 over the uploaded bytes. This identifies the received byte sequence but does not authenticate camera origin. Stream tags remain separate from sidecar XML declarations. Linear-light RGB remains unavailable, and no camera transform, timecode mapping, legal-range normalization, or reference validation is inferred.

This is a single-frame measurement endpoint, not a full temporal scan. The caller-supplied frame index is a label; timestamp-to-frame/timecode reconciliation is separate.

## Bounded temporal sampling

`POST /v1/media/video-temporal-report` decodes a bounded sequence of 1–24 timestamps. `start_seconds` and `interval_seconds` define sample positions. Each sample includes native YUV plane statistics and decoder RGB channel statistics; the two domains are not merged. The endpoint reports first-to-last mean deltas and maximum absolute step deltas as descriptive sample statistics only. These values are not exposure-drift, flicker, or scene-cut classifications. Source frame indices and timecode remain unresolved because this endpoint samples by timestamp only. Linear-light RGB remains unavailable without a validated per-pixel transform.


## Sampled temporal diagnostics

The bounded video-sample endpoint also returns per-shot, per-channel sample-mean
trends. These are descriptive decoder-domain statistics, not exposure-stop or
flicker measurements. See temporal-diagnostics.md for the metric definitions
and validation limits. Flicker and exposure drift remain explicitly unavailable
until dense fixed-ROI sampling and validated scene-linear RGB are available.
