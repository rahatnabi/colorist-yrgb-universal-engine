# COLORIST YRGB — Dual Accuracy Scoring

Status: **image-derived exposure, neutral-ROI white balance, tonal distribution, and optional reference percentile-curve scoring**. All scored measurements require an explicitly validated linear-RGB frame.

## Product rule

Every exercise may report two independent results:
1. **Correction Accuracy** — objective technical correction against declared, measurable targets.
2. **Creative Look Similarity** — perceptual similarity to an explicitly selected creative reference.

Never combine these into one headline score.

## 1. Correction Accuracy

### Exposure
A learner- or exercise-selected ROI is measured in validated linear-light RGB. Mean luminance is compared with the exercise's declared gray reference in stops. No gray card or target exposure is inferred.

### White balance
The same explicitly selected neutral ROI is measured for per-channel balance. Red, green and blue channel deviations from the exercise's declared neutral target are scored independently. The ROI must genuinely be neutral; the engine cannot determine that from RGB values alone.

### Reference-based tonal curve
An exercise may provide a reference curve as seven monotonically non-decreasing linear-luminance values at fixed full-frame percentile anchors: P1, P10, P25, P50, P75, P90 and P99.

The candidate image is measured at the same anchors in the same validated linear working space. Each anchor is compared using absolute stop deviation:

    abs(log2(candidate_luminance / reference_luminance))

Each anchor receives its own component result; the seven components share the exercise-defined tonal-curve weight. The exercise controls tolerance, falloff, weight and a positive luminance floor. The floor stabilizes comparisons near black and must be selected deliberately for the exercise.

This measures the distribution of luminance values, not spatial placement of tones. It does not establish that the subject, lighting, or artistic contrast is correct. Two images with different spatial arrangements can have similar percentile curves. For that reason, the feature is labelled **Reference Tonal Curve Accuracy**, not a full-image perceptual similarity score.

If no reference curve is supplied, no curve score is emitted. The engine does not invent a target curve. Invalid, non-monotonic or incomplete reference anchors are rejected.

### Shadow/highlight distribution
The full frame may also be measured for shadow and highlight pixel fractions using exercise-defined thresholds in linear luminance. These are optional distribution diagnostics, not universal clipping limits or a substitute for a calibrated display-referred waveform.

### Scoring
Each exercise supplies its own target values, ROI, thresholds, weights and tolerances. For an error e, tolerance tau, and exercise falloff k:
- 100 when e <= tau.
- Otherwise max(0, 100 * (1 - (e - tau) / (k * tau))).

Required measurements that are unavailable make the report not_scored. No inferred targets, hidden fallback weights, or automatic grade changes are permitted.

The current upload decoder still marks source output uncharacterized; decoded uploads do not receive this score automatically until a validated transform is applied.

## 2. Creative Look Similarity

This remains a separate future implementation. It requires validated color-managed reference and candidate images, reliable alignment/masks, and pixelwise perceptual color comparison such as CIEDE2000 (Delta E 00). Existing decoded-RGB diagnostics or mean-Lab Delta E 76 must not be presented as Delta E 00.

## 3. UI rules

- Show Correction Accuracy and Creative Look Similarity separately.
- Show exposure, white-balance, tonal-distribution and reference-curve component feedback.
- Label the reference curve's working space, transform, percentile anchors, tolerance and luminance floor.
- Preserve the learner's grade; scoring never modifies pixels or controls.
- A score is not_scored when required pipeline or reference data is unverified.

## Explicit non-goals

No video or temporal scoring, no universal aesthetic score, no inferred gray card/skin ROI, and no score based on unverified decoded RGB.