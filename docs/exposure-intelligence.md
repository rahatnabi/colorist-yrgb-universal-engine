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
