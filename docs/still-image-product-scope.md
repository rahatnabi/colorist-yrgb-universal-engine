# COLORIST YRGB — Still-image-only product scope

COLORIST YRGB is a still-image inspection, color-analysis, grading and delivery workspace. Video clips, video-frame analysis, temporal diagnostics, motion analysis and video export are explicitly outside the product scope.

## Supported workflow

1. Import still images and image sequences.
2. Inspect file signatures and available metadata without inventing missing camera settings.
3. Decode supported still formats at the highest available precision.
4. Analyze RGB histograms, RGB parade, luma waveform and vectorscope under explicitly selected scope assumptions.
5. Inspect camera/profile candidates; never apply an unvalidated transform.
6. Render a reference-gated color-managed preview when a validated transform is available.
7. Build and export creative looks / LUTs where the selected processing domain is valid.
8. Analyze bounded still-image batches and compare adjacent images.
9. Build contact sheets, compare shots, and export image analysis reports (planned milestones).

## Image support principles

- JPEG, PNG, TIFF, EXR and DPX are target still formats, subject to installed decoder support.
- Camera RAW formats (including DNG and vendor RAW variants) require explicit decoder availability and format-specific validation. A filename extension alone is not proof of decode or metadata support.
- Preserve high bit depth and floating-point values where the decoder supports them.
- Preserve alpha and extra channels; do not silently discard channels without reporting it.
- Respect orientation, embedded ICC profiles, chromaticities and metadata provenance.
- Keep source samples, scene-linear values, display-referred values and transformed preview values clearly separated.
- Never infer a camera Log transform solely from file tags or a LUT filename.
- Scope coefficient selection is an explicit assumption, not a color-space conversion.

## Product boundary and legacy research code

The repository contains earlier video/temporal research modules and API routes. They are retained temporarily so existing automated tests and research notes remain reproducible, but they are not part of the supported product workflow and must not be exposed in the user interface, documentation as active features, or future roadmap. Future work should prioritize still-image functionality only.

## Quality gates

A feature is not complete merely because it compiles. Each image workflow needs:
- unit and API tests;
- decoder availability and unsupported-format handling;
- real-image validation across bit depths and channel layouts;
- explicit measurement-domain labels;
- non-destructive source handling;
- clear error messages and resource limits;
- verified export/re-import behavior where applicable.
