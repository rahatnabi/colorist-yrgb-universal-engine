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