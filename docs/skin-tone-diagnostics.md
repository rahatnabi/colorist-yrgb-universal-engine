# Selected-region skin-tone workflow diagnostics

The `yrgb_engine.skin_tone` module provides numeric hue, saturation and value
statistics for a **user-selected ROI**. It is a grading diagnostic, not a skin
detector or a person-analysis feature.

## Measurements

- Mean RGB in the declared signal domain.
- Circular mean hue and hue percentiles for chromatic samples.
- Hue resultant strength, indicating how concentrated the sampled hue angles are.
- Mean/median saturation and value.
- Explicit ROI and signal-domain label.

## Required operator decisions

The caller must supply the ROI and a non-empty `signal_domain` label, such as a
known camera encoding or a display-referred working signal. The module does not
decode Log, apply a camera transform, or assume that numeric RGB values are
linear. The selected domain is included in the result so a UI can label it.

## Guardrails

- No face detection, skin classification, identity inference, or demographic inference.
- No fixed skin-tone hue line, universal target, or automatic correction.
- Hue is a circular quantity; the mean uses circular statistics to avoid the
  0/360-degree wraparound error.
- Achromatic pixels are excluded from hue statistics but included in saturation
  and value summaries.
- Negative RGB samples are rejected by this HSV diagnostic; use a suitable
  explicitly transformed non-negative domain if this measurement is needed.

Skin appearance varies with illumination, exposure, camera response, creative
intent and display pipeline. Treat these measurements as descriptive feedback,
not a pass/fail judgment or a substitute for visual evaluation.
