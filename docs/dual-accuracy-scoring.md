# COLORIST YRGB — Dual Accuracy Scoring

Status: **validated image-measurement integration for exposure, neutral-ROI white balance, and optional tonal fractions**. The scoring path accepts only explicitly validated linear-RGB PrecisionFrames.

## Product rule

Every exercise may report two independent results:

1. **Correction Accuracy** — objective technical correction against declared, measurable targets.
2. **Creative Look Similarity** — perceptual similarity to an explicitly selected creative reference.

Never combine these into one headline score.

## 1. Correction Accuracy

### Exposure
A learner- or exercise-selected ROI is measured in validated linear-light RGB. Mean luminance is compared with the exercise's declared gray reference in stops. No gray card or target exposure is inferred.

### White balance
The same explicitly selected neutral ROI is measured for per-channel balance. Red, green and blue channel deviations from the exercise's declared neutral target are scored independently, then weighted as one white-balance family. The ROI must genuinely be neutral; the engine cannot determine that from RGB values alone.

### Tonal structure
The full frame is measured for shadow and highlight pixel fractions using exercise-defined thresholds in the declared linear-luminance domain. These fractions are scored only when the exercise supplies both thresholds and both target fractions. This is a compact tonal-distribution measure, not a complete artistic contrast judgement or a substitute for a calibrated display-referred waveform.

The measurement also reports luminance percentiles (1st, 10th, 50th, 90th, 99th) for diagnostics. Percentiles are not yet scored against a reference curve.

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
- Show component-level exposure, white-balance and tonal feedback.
- Label tonal fractions and thresholds; do not present them as universal clipping limits.
- Preserve the learner's grade; scoring never modifies pixels or controls.
- A score is not_scored when required pipeline or reference data is unverified.

## Explicit non-goals

No video or temporal scoring, no universal aesthetic score, no inferred gray card/skin ROI, and no score based on unverified decoded RGB.
