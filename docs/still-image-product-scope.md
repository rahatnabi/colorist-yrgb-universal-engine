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
9. Build a browser-local contact sheet, compare selected stills side by side, and inspect decoded sample-domain channel mean differences.

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


## Contact sheet and shot comparison workspace

The frontend contact sheet creates temporary object URLs for the selected local files and displays browser-decodable previews. It does not upload images just to make thumbnails. Browser preview support varies by format; RAW, EXR, TIFF or other formats may not render in the browser even when the analysis backend can decode them.

The comparison workspace lets the user select two images and view them side by side. After batch analysis, it shows the difference between the selected images' decoded RGB channel means (B − A). These numbers are not exposure stops, white-balance differences, perceptual color distances, or a shot-match score. No image registration, crop alignment, subject tracking, or color-space normalization is performed.

Object URLs are temporary and revoked when the selected image list changes or the component is unmounted. The source files are not modified.


## Feature-based image alignment and reference comparison

The `POST /v1/media/align-compare` endpoint accepts two still images: a reference and a candidate. It decodes both through the configured OpenImageIO adapter, detects ORB features, matches descriptors, and estimates a candidate-to-reference homography with RANSAC. It reports feature inliers, inlier ratio, overlap area, and the 3×3 transform matrix. It also returns a 50/50 reference/candidate overlay preview using a shared 1st–99th percentile sample-value scale; this is a diagnostic preview, not a color-managed rendering. The analysis raster is downscaled to a maximum dimension of 1280 pixels for registration and comparison.

RGB comparison is calculated only over the warped overlap area. Per channel, the response reports reference mean, aligned candidate mean, candidate-minus-reference mean delta, mean absolute difference and root-mean-square difference. The operation is non-destructive; original uploaded files are not rewritten.

Install the optional dependencies with `pip install -e ".[vision,high-precision,api]"`. OpenCV is not a mandatory base dependency. Without it, the endpoint returns a clear dependency error.

Important limitations:
- ORB/RANSAC estimates geometric correspondence; it is not a guarantee of semantic subject alignment. Repeated patterns, low texture, large occlusions, moving subjects and strong perspective changes can fail or produce misleading matches.
- The homography matrix maps candidate analysis-raster coordinates to reference analysis-raster coordinates. It is not a full-resolution camera calibration.
- RGB metrics are decoded sample-value comparisons, not Delta E, exposure stops, calibrated luminance or white-balance measurements.
- Matching sample-domain labels do not prove matching primaries, transfer functions, ICC profiles, camera transforms or display rendering.
- No automatic color normalization or display transform is applied. Users should compare images with verified matching colorimetry before interpreting the channel metrics as color consistency.
