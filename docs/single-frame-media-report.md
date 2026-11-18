# Single-frame media analysis report composition

`yrgb_engine.media_report.build_single_frame_measurement_report` composes one timestamp-matched native YUV decode and FFmpeg decoder RGB frame into the media-analysis report contract.

- Native YUV integer plane measurements are kept in `original_yuv_code_values`.
- FFmpeg RGB float output is labelled decoder-converted RGB, not original integer RGB and not linear light.
- `linear_light_rgb` remains unavailable until an explicit per-pixel inverse-transfer path is validated.
- Stream tags are retained separately from sidecar XML declarations; unresolved metadata remains unresolved.
- Source SHA-256 is validated when supplied; no timecode or camera transform is inferred.

This is a report composition layer for one sampled frame, not a full-clip temporal scan or camera-transform validation.
