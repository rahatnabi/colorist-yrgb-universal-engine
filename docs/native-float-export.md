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
