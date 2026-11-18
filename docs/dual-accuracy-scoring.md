# COLORIST YRGB — Dual Accuracy Scoring

Status: **scoring contract / implementation specification**. Scores must not be displayed as validated until the required color pipeline and reference data are available.

## Product rule

Every exercise may report two independent results:

1. **Correction Accuracy** — objective technical correction against declared, measurable targets.
2. **Creative Look Similarity** — perceptual similarity to an explicitly selected creative reference.

Never combine these into one headline score. A learner may correct an image accurately and intentionally create a different look; that must not reduce the correction score.

## 1. Correction Accuracy

Only score criteria that the exercise explicitly defines and that can be measured from the supplied reference/target data.

Candidate criteria:

- Exposure / luminance deviation, in stops, only in a declared linear-light or otherwise validated measurement domain.
- White-balance / neutral-region chromaticity deviation, using a declared neutral ROI.
- RGB balance deviation in a declared common working space.
- Tonal-structure deviation across configured shadow, midtone and highlight regions.
- Optional color-patch or selected-ROI difference, after both images have valid transforms into the same comparison space.

Each exercise supplies its own target values, ROI masks, criterion weights and tolerance bands. Do not infer a neutral patch, 18% gray card, skin ROI, or target exposure when the exercise has not supplied one.

### Criterion scoring

For a measured error e, target t, and exercise-defined tolerance τ, the criterion score is:

- 100 when e <= τ.
- Otherwise, max(0, 100 * (1 - (e - τ) / (k * τ))), where k is a documented exercise-level falloff factor.

This is a transparent training rubric, not a universal perceptual law. The exercise author must set and document τ and k; do not silently apply one global tolerance to every image or camera.

The Correction Accuracy score is the weighted mean of valid criterion scores. If a required criterion cannot be measured, return not_scored with a reason rather than guessing or silently redistributing its weight. Optional criteria may be omitted only when the exercise definition marks them optional.

## 2. Creative Look Similarity

This score compares the learner's exported/rendered still with a designated target-look reference. It is not a judgement of whether the creative choice is aesthetically good.

Required conditions:

- Both images are decoded correctly.
- Both are transformed using known, validated color-management paths into the same comparison space and viewing/display condition.
- Alignment is reliable and the comparison mask excludes invalid/non-overlapping pixels.
- Any resizing, crop, ROI weighting and alpha handling are declared and reproducible.

Recommended comparison signals:

- Pixel/ROI perceptual color difference using **CIEDE2000 (ΔE00)** in an appropriate Lab comparison domain.
- Luminance / tonal-distribution similarity.
- Hue and chroma distribution similarity.
- Optional region-weighted similarity for important areas such as subject, background or skin, only when masks are supplied or explicitly approved.

Do not use the current decoded-RGB sample-difference or mean-Lab ΔE76 diagnostic as if it were a validated ΔE00 creative similarity score. Mean RGB converted once to Lab is not equivalent to pixelwise perceptual comparison.

### Similarity scoring

The exercise defines the metric weights, ROI weights, and acceptable error ranges. Convert each metric to a 0–100 score using documented exercise-specific thresholds, then calculate a weighted mean. The report must expose the component scores and measured errors so the learner can understand the result.

Creative Look Similarity is not_scored if colorimetry, display condition, alignment, or required reference metadata is not verified. Do not invent a similarity percentage.

## 3. Result contract

Each score returns:

- status: scored or not_scored
- score: number from 0 to 100, or null
- label: Correction Accuracy or Creative Look Similarity
- components: per-metric measured value, target, error, tolerance, weight and component score
- color_pipeline: source/reference IDs, working/comparison space, transforms and validation state
- limitations: concise explanation of any excluded data or assumptions

A not_scored result must include a learner-readable reason and the action needed to make it measurable.

## 4. UI rules

- Show the two scores side by side, never as a blended total.
- Clearly label a demonstration/example score as illustrative.
- Show component-level feedback and the largest correctable deviations.
- Preserve the learner's creative grade; scoring must not automatically alter pixels or grading controls.
- Export the two results independently in the grading report.

## 5. Implementation sequence

1. Define exercise target/ROI/weight schema.
2. Implement a deterministic scoring module with unit tests for tolerances, missing data, invalid transforms and score bounds.
3. Add validated pixelwise ΔE00 support; keep current ΔE76 diagnostics explicitly labelled.
4. Add a score-report API contract.
5. Connect the report to the still-image grading workspace and export.
6. Validate against synthetic color patches and a curated, color-managed real-image set.

## Explicit non-goals

- No single universal score for every image or creative style.
- No AI aesthetic judgement presented as objective accuracy.
- No score based solely on unverified decoded RGB values.
- No automatic grading adjustment based on the score.
- No video or temporal scoring.
