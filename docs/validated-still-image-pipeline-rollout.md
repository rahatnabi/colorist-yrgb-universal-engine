# Validated Still-Image Pipeline Rollout

## Scope

This rollout is for still-image grading only. It covers image decode, explicit source-profile selection, validated input transforms, neutral-region measurement, exercise targets, and live Correction Accuracy reporting. It does not add video or temporal processing.

## Camera-family rollout order

The architecture is multi-family, but production approval is profile-by-profile:

1. Sony S-Log3 / S-Gamut3.Cine — first reference-validation target.
2. ARRI LogC3 / AWG3.
3. ARRI LogC4 / AWG4.
4. Canon C-Log3 / Cinema Gamut.

The first profile is the implementation and validation template. The remaining families reuse the same pipeline contracts, but each requires its own exact camera/recording-mode compatibility, OCIO source-space mapping, independently sourced reference manifest, and passing validation record. No family inherits another family's approval.

## Hard validation gates

A profile is eligible for transform use only when all of the following match:

- Exact profile ID and transform ID from the registry.
- Exact source and destination color-space names.
- A pinned OCIO config whose SHA-256 matches the validation record.
- A traceable reference set with source, measurement method, camera model, recording mode, codec, bit depth, and labeled measured vectors.
- Passing independent reference-vector comparison within the declared tolerance.
- Explicit output transfer and primaries.
- The decoded still image is explicitly assigned that exact profile; metadata suggestions alone never authorize conversion.

Synthetic vectors may test validator mechanics, but cannot approve a production camera transform. Empty/example manifests and manually supplied `validated=true` flags are not evidence.

## Linear-light working data

The scoring pipeline requires scene-linear / linear-light RGB in the declared working space. The transform implementation must explicitly produce that domain. A destination label such as “DaVinci Intermediate WideGamut” is not by itself proof of linear-light output; the transfer characteristic must be verified independently.

For the first implementation, preserve source samples and provenance, apply the validated source transform to a linear-light working representation, and record profile ID, transform ID, OCIO config hash, reference-set ID, OCIO version, and validation evidence with the processed frame. Reject unsupported or ambiguous source encodings rather than guessing.

## Neutral ROI and exercise configuration

The still-image UI will provide a normalized image-coordinate rectangle with pointer-based draw, move, resize, clear, and reselect operations. Convert it to pixel coordinates only against the current image dimensions; clamp to image bounds and reject empty or too-small selections.

Exercise configuration is explicit and versioned:

- Gray reference (default 18% linear reflectance where appropriate).
- Exposure target and tolerance in stops.
- Neutral WB target and tolerance, measured from the selected neutral ROI.
- Seven full-frame linear-luminance percentile anchors: P1, P10, P25, P50, P75, P90, P99.
- Per-criterion weights, tolerances, falloff, and working-space identity.

A neutral ROI is learner-selected and is not automatically assumed to be neutral. Provide a minimum sample count and neutral-spread validity check; invalid selections yield NOT SCORED with a reason.

## Live report contract

On each grading update, measure the current processed still image and return the existing CorrectionAccuracyReport shape. The panel displays exposure, R/G/B neutral balance, seven tonal anchors, component deviations, and the overall exercise-weighted Correction Accuracy score.

Do not blend Creative Look Similarity into Correction Accuracy. Do not compute a headline score when a required measurement is missing, the transform evidence is stale, the ROI is invalid, or the image/target working spaces differ. Debounce UI requests and cancel stale responses so older measurements cannot overwrite a newer grading state.

## Acceptance tests

- Exact source-profile and transform identity mismatch is rejected.
- OCIO config hash mismatch invalidates approval.
- Missing, synthetic-only, empty, or untraceable reference manifests cannot promote a profile.
- A passing reference set approves only its own profile/transform/config tuple.
- Output transfer is verified as linear-light before scoring is enabled.
- Neutral ROI coordinates map correctly across image resize and device pixel ratio.
- Out-of-bounds, empty, too-small, clipped, and non-neutral ROIs return explicit not-scored states.
- Exposure and WB measurements respond deterministically to controlled image changes.
- Tonal percentile measurements use the full frame and match known linear-light fixtures.
- Live API responses are tied to the exact image revision, grading revision, target revision, and transform evidence.
- Missing required metrics suppress the overall score.
- Creative Look Similarity remains a separate metric and report.

## Current approval status

The registry candidates for Sony S-Log3 / S-Gamut3.Cine, ARRI LogC3 / AWG3, ARRI LogC4 / AWG4, and Canon C-Log3 / Cinema Gamut remain unverified until independent traceable reference manifests are supplied and pass against the pinned OCIO config. This document does not approve any transform.
