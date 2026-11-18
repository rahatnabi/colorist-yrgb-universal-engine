# Exposure & Shot Consistency Intelligence

The first exposure-intelligence layer is deliberately measurement-first.

## Region measurement

`measure_exposure_region` measures a caller-selected pixel ROI. It reports RGB means,
luminance mean/median and 10th/90th percentiles, plus the region's mean-luminance
offset from a configurable gray reference in stops:

`stops = log2(region_mean_luminance / gray_reference)`

The default gray reference is 0.18. This is a comparison reference, not a claim that
the selected region is a gray card. The application must let the user select or confirm
the region; automatic gray-card detection is not implemented.

## Required signal contract

Exposure APIs require RGB channels, a transfer explicitly named linear/linear-light/
scene-linear, and `ColorEncoding.validated=True`. The caller supplies RGB-to-Y
coefficients. Unknown Log, display-referred, or unvalidated frames are rejected.
No implicit camera transform or Rec.709 IRE interpretation is performed.

## Tonal distribution

`analyze_tonal_distribution` reports luminance percentiles and the fractions below
a caller-supplied shadow threshold and above a caller-supplied highlight threshold.
Thresholds are not universal clipping points. Values are not silently clamped.

## Neutral / white-balance diagnostics

The ROI measurement includes mean channel balance normalized around the mean RGB
channel value and a max-minus-min spread. This is a neutral-region diagnostic only;
it is not a camera white-balance correction or a color-temperature estimate. The
caller must select a genuinely neutral reference patch for meaningful interpretation.

## Shot comparison

`compare_exposure_regions` reports exposure-stop and channel-balance deltas between
two independently measured regions. The caller is responsible for ensuring both
frames were transformed into the same validated linear working space and measured
with the same coefficients and gray-reference convention. Mixed-camera comparisons
must not happen before exact, validated input transforms.

## Not yet implemented

Automatic gray-card detection, face/skin exposure, spatial highlight masks, semantic
shot detection, camera matching recommendations, and GPU acceleration remain future
work. The current implementation is a deterministic CPU measurement foundation.


## Spatial exposure map

`analyze_spatial_exposure` divides a validated linear-RGB frame into a configurable
rectangular grid (8×8 by default). Each cell reports its ROI, mean luminance, and
stops from the selected gray reference. Cells cover the full frame, including
non-divisible edge dimensions.

## Neutral-region candidate scan

`find_neutral_region_candidates` ranks grid cells using two explicit heuristics:
normalized RGB channel spread and proximity to the gray reference in stops. Its
confidence is a deterministic ranking score, not a calibrated probability. A
neutral wall, clothing, or other object can score as a candidate; the scanner
cannot prove that a region is a gray card or that it is correctly illuminated.
The user must confirm the selected region before treating it as a reference.

The scanner is CPU-based and grid-resolution dependent. Small patches may be missed
if they fall across cell boundaries; higher grid density improves localization at
additional computational cost. Automatic segmentation and learned object detection
are not part of this phase.


## Temporal exposure consistency

`iter_temporal_exposure` streams frame measurements and retains only the prior
measurement plus the current shot reference. It reports per-frame exposure change,
cumulative drift from the start of the current shot, and RGB channel-balance change.
The caller supplies a confirmed ROI and zero-based confirmed shot-boundary indices.
A boundary resets the reference and suppresses a cross-shot delta; histogram-based
shot-change candidates are advisory and are not automatically treated as boundaries.

Every frame must be explicitly marked as validated linear RGB and carry the same
`working_space_id`. Camera-specific `transform_id` values may differ because
different validated camera transforms can map into one common working space.
The engine does not verify transform correctness; it trusts the upstream validation
flag and declared destination identity. Unknown or mismatched working spaces are
rejected. Timestamps must be finite, non-negative, and strictly increasing.

A single ROI is applied across the supplied sequence. This is appropriate only when
the same reference patch remains in the same image coordinates. For reframing,
camera movement, subject movement, or a new neutral patch, segment the analysis and
supply a newly confirmed ROI. No automatic tracking or semantic shot detection is
claimed. The engine is CPU-based and makes no automatic exposure correction.
