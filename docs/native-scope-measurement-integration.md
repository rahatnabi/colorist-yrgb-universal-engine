# Native Scope & Correction Measurement Integration

## Endpoint

`POST /v1/media/native-measurements` accepts one still image, an exact camera profile ID, a full-resolution pixel ROI, and the interactive look controls.

The endpoint refuses unknown or unverified profiles. It requires the pinned server OCIO config and preview output configuration, decodes the uploaded still to float32, and delegates input conversion plus grading to `process_validated_still()`.

## One authoritative measurement frame

Both measurement groups are derived from the exact same `StillGradingResult.graded_frame`:

- **Scopes:** RGB histograms, RGB parade, luma waveform and vectorscope points.
- **Correction Accuracy:** exposure relative to the exercise gray reference and RGB channel balance from the explicitly selected neutral ROI.

The endpoint returns the working-space ID, transform ID, validation state, image dimensions, ROI, scope payload and the structured Correction Accuracy report. The API does not derive a Creative Look Similarity score.

## Measurement conventions

- The frame must carry a reference-validated transform and linear-light transfer.
- The ROI is expressed in full-resolution source pixels and must be fully inside the decoded still.
- The neutral ROI is learner-selected. The engine measures it but does not claim to recognize a gray card or prove that the selected patch is neutral.
- The scope range is explicitly `[-0.25, 4.0]` in linear working-space sample values. This preserves negative values and highlight headroom for diagnostics.
- Waveform and vectorscope use working-space luminance coefficients (Rec.709 or ACEScg as selected by the profile's destination space).
- These scopes are **not IRE, legal video levels, or calibrated nits**. Clipping counts use explicit linear thresholds 0.0 and 1.0; values above 1.0 are still preserved in the measured frame.
- Correction Accuracy uses exercise-provided exposure target, gray reference, and tolerances. No objective score is returned for unvalidated data.
- Tonal-curve scoring remains unscored unless an exercise supplies a reference curve through a separate target configuration.

## UI

The Interactive Grading Preview now includes a Native Scope & Correction Measurements panel. Learners enter ROI x/y/width/height in full-resolution source pixels, then request measurements. Results include the independent Correction Accuracy headline, exposure deviation, RGB balance, and scope signal summary.

The browser canvas scopes remain separately labelled as approximate browser sRGB preview data. They are not silently replaced or merged with native linear measurements.

## Safeguards and limitations

- Sony S-Log3/S-Gamut3.Cine remains unverified until traceable measured reference vectors are supplied and explicitly approved.
- The endpoint does not infer source Log encoding from EXIF, filenames, or sidecars.
- A learner-selected ROI can be unsuitable; the report carries that limitation.
- Display PNG preview and full-resolution mastering export remain separate work.
- Creative Look Similarity is not calculated here and must remain separate from Correction Accuracy.

## Tests

API tests cover: same validated graded frame feeding both measurement paths, a neutral 18% fixture producing a full correction score, out-of-bounds ROI rejection, and rejection of an unverified Sony candidate. Tests must execute in CI before this integration is treated as verified.
