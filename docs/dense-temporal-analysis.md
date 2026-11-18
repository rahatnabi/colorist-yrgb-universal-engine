# Dense temporal ROI analysis foundation

`yrgb_engine.dense_temporal.analyze_dense_roi_samples` accepts ordered,
per-frame RGB means for one explicitly identified ROI. It validates strictly
increasing timestamps and frame indices, stable ROI identity, consistent
measurement domain, and sampling regularity against a caller-specified frame
interval.

The analyzer only reports an exposure delta in stops when every sample is
marked `linear_light_rgb` and carries
`reference_validated_transform=true`. The metric is the first-to-last ratio
of ROI mean luminance using explicitly supplied coefficients. This is a
measurement of the selected ROI, not proof of camera auto-exposure behavior.

Dense, regular samples are a prerequisite but not sufficient evidence for
flicker. Flicker remains `inconclusive` until periodicity analysis and controls
for motion, scene changes, and lighting variation are implemented. Sparse or
irregular sampling makes the assessment `unavailable`.

This module is a tested analysis foundation, not yet a video decoder or API
endpoint. It does not extract a tracked ROI, compute frequency spectra, or
claim flicker confidence. The next integration step is to decode dense frames,
apply a fixed ROI mask, and pass measured per-frame means into this interface.


## Dense fixed-ROI video endpoint

`POST /v1/media/video-roi-temporal-report` decodes a bounded sequence of
RGB frames and measures the same normalized image-coordinate rectangle in
each frame. Defaults are 48 samples at 25 samples/second; callers can select
an interval and up to 240 samples. Each output sample includes the ROI pixel
bounds, pixel count, RGB means, timestamp, and sample ordinal.

The endpoint passes per-frame means into
`analyze_dense_roi_samples`. The sample ordinal is used only to enforce
ordering; it is not a source frame index. Dense regular sampling can make the
flicker assessment eligible for further analysis, but the current result
remains inconclusive because no frequency-domain estimator or motion/scene
controls are implemented. Exposure drift remains unavailable because this
endpoint does not apply a reference-validated scene-linear transform.

ROI coordinates are fixed in image space. They do not follow moving subjects.
The upload limit remains the service-wide bounded upload limit, and the
sampling count is capped at 240 to limit decode work.


## Periodic variation and scene-boundary candidates

The dense analyzer removes a fitted linear trend, applies a Hann window, and
evaluates an FFT peak in the 1 Hz to min(30 Hz, Nyquist) band when at least 32
regular samples are available. A peak is surfaced as a
`periodic_variation_candidate` only when its peak-to-median spectral-floor
ratio is at least 6 and relative modulation amplitude is at least 0.2%.
This is a decoder-sample-domain candidate, not a confirmed flicker diagnosis
or identification of mains frequency.

The endpoint also measures a fixed 2×2 set of ROI tiles. Agreement of spectral
peaks across tiles is reported as spatial coherence. This is supporting
evidence only: it is not optical flow, subject tracking, or motion compensation.
Camera motion, moving content, rolling shutter, exposure control, compression,
and mixed lighting can still create or mask periodic signals.

Large adjacent RGB ROI mean steps are emitted as scene-boundary candidates.
They are not confirmed cuts and should be cross-checked with existing frame
histogram diagnostics. No exposure-stop result is enabled for nonlinear
decoder RGB. The implementation deliberately avoids calling this
motion-compensated flicker detection.
