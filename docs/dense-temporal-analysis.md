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
