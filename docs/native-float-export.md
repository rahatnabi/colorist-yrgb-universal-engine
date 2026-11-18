# Full-Resolution Native Float Export

## API

`POST /v1/media/native-grade-export` accepts one still image, a reference-validated camera profile, the native grading controls, and `export_format=exr|tif|tiff`.

Supported master containers:

- OpenEXR (`.exr`) with float32 samples and ZIP compression.
- TIFF (`.tif` / `.tiff`) with float32 samples and Deflate compression.

## Processing

The endpoint decodes the original still using OpenImageIO float32, applies the registry-approved camera-to-linear transform, then calls the same `process_validated_still()` grading path used by the native preview and measurement routes. The export writer receives the full-resolution `graded_frame`, not the browser canvas, resized preview, or display-transformed PNG.

The output writer does not clamp sample values. Negative values and highlight values above 1.0 remain in the float image buffer. The API response includes image dimensions, working-space ID, transform ID, a SHA-256 digest of the exact interleaved float32 samples before container encoding, and explicit `X-YRGB-Clamped: false` metadata.

## Embedded metadata

The writer stores the working-space name, transform ID, linear transfer declaration, export description and software identifier in the image header where supported by the output plugin. The API headers repeat the authoritative engine-side identifiers.

## Safety gates

- Only profiles whose registry status and reference-validation record make them usable for transforms are accepted.
- Exact camera model selection is required whenever the profile declares supported camera models.
- Output must be validated scene-linear RGB with explicit working-space and transform IDs.
- Unverified Sony FX30 S-Log3/S-Gamut3.Cine remains blocked.
- Export does not apply a display rendering transform. The output is a scene-linear grading master, not a Rec.709 viewing file.
- Creative Look Similarity is not calculated here.

## Preview/export consistency

Native preview, native measurements and master export all use the same native still grading function and the same grade parameters. The preview applies a display transform and clamps only at its display boundary; native scopes/accuracy inspect the linear graded frame; the master exporter writes that same class of linear graded frame without display clamping. The float-sample digest enables downstream verification of the engine frame represented by an export operation.

The digest is calculated before container encoding; it is not a claim that every TIFF/EXR reader will reproduce byte-identical sample serialization. A future round-trip verifier should decode the written file and compare per-pixel float values within a format-specific tolerance.

## Runtime requirement

Install the `high-precision` optional dependencies (`OpenImageIO` and `NumPy`) on the API server. Export tests use a controlled fake writer and do not replace integration testing against the actual OpenImageIO TIFF and OpenEXR plugins.

## Round-trip verification

After writing a TIFF or OpenEXR master, the engine reopens the file with OpenImageIO and reads it back as float32. It checks dimensions, channel count and channel names, then compares every sample against the original graded frame using:

`allowed_error = absolute_tolerance + relative_tolerance × abs(source_sample)`

Defaults are absolute tolerance `1e-7` and relative tolerance `1e-6`. An export that exceeds tolerance is rejected and is not returned as a successful master. The API reports sample count, maximum absolute error, RMSE and whether the read-back sample digest matches the in-memory float32 frame.

This verifies the actual output file rather than merely trusting the writer call. It does not certify colorimetric correctness of the camera input transform or the monitor/display transform; those remain separate validation responsibilities.

## Post-export delivery QC

The export endpoint accepts an optional full-resolution pixel ROI (`roi_x`, `roi_y`, `roi_width`, `roi_height`). Supply all four values together; the region must be inside the exported still and contain at least 16 pixels.

When an ROI is supplied, the engine first writes the master, reopens it and verifies every float32 sample against the in-memory graded frame. Only after that succeeds does it decode the actual exported file again, confirm dimensions and channel layout, and carry the already-validated pipeline identity onto that decoded frame. Correction Accuracy is then measured from the decoded export—not from the browser preview or an assumed display transform.

The optional exercise target includes exposure target stops and the linear gray reference (default 18%). The report is returned in the `X-YRGB-Delivery-QC-Report` response header (URL-safe base64-encoded JSON), with the overall Correction Accuracy score and QC status in separate headers. If no ROI is provided, export remains available and QC is explicitly marked `not_requested`.

The ROI must genuinely represent a neutral reference for exposure and white-balance measurements to be meaningful. The engine does not infer neutrality from pixel values. A technically valid file round-trip is not proof that the camera transform itself is colorimetrically correct; transform validation remains a separate gate.
