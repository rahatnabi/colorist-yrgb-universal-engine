# COLORIST YRGB — Universal Color Engine

**An interactive still-image color grading school and precision analysis workspace.**

> **Product scope:** COLORIST YRGB is for still photographs, rendered still frames, and still-image sequences. Video editing, video grading, temporal analysis, and video export are not product features. Legacy video code may remain temporarily for reproducibility, but it is outside the product roadmap.

## Product principles

- Grade still images interactively and preserve a path to full-resolution float processing.
- Treat camera Log as an encoding/profile, never as a file extension or a guess from a filename.
- Use explicit camera gamut/gamma profiles; never silently guess a source transform.
- Keep decode, input transform, working-space grading, display preview, scopes, measurement, and master export as separate stages.
- Prefer fewer, explainable controls and scientifically grounded measurement.
- Keep **Correction Accuracy** separate from **Creative Look Similarity**. The former evaluates exercise-defined technical targets; the latter compares a creative result against a chosen visual reference.
- Do not publish numerical objective scores for unvalidated source data.

## Implemented foundation

- Float32 precision frame model with explicit source encoding and validation metadata.
- Still-image metadata inspection and optional OpenImageIO float decode.
- Exact-match camera profile registry and traceable transform-validation workflow.
- OpenColorIO transform adapter with reference-validation gates.
- Interactive browser still preview with Exposure, Contrast, Pivot, Saturation, Temperature, Tint and Master Curve controls.
- Native still grading pipeline using a validated input transform and scene-linear working space.
- Native scopes and Correction Accuracy API based on the same graded float32 still frame.
- Full-resolution float32 TIFF and OpenEXR export path with no display-range clamping.
- Preview/export metadata including working-space identity, transform identity, image dimensions and a float-sample SHA-256 digest.
- Post-export round-trip verification and optional Correction Accuracy delivery QC measured from the decoded TIFF/OpenEXR master using an explicit neutral ROI.
- Separate LUT import workflow; LUT files are not treated as image inputs.

These features are an active foundation, not a claim that every camera transform or format is production-certified. Camera profiles remain blocked until their exact capture mode and transform are independently validated with traceable measured reference data. In particular, the Sony FX30 S-Log3/S-Gamut3.Cine candidate remains unverified.

## Native master export

The API endpoint `POST /v1/media/native-grade-export` supports:

- OpenEXR (`.exr`) float32
- TIFF (`.tif` / `.tiff`) float32

Exports are scene-linear working-space masters, not display-referred Rec.709 viewing files. The native engine does not clamp negative values or highlight headroom above 1.0. See [Native float export](docs/native-float-export.md).

## Native scopes and assessment

The endpoint `POST /v1/media/native-measurements` calculates scopes and Correction Accuracy from one validated native graded still. Scope values are linear working-space samples, not IRE or calibrated nits. Neutral ROI selection is explicit and learner-controlled. See [Native scope and measurement integration](docs/native-scope-measurement-integration.md) and [Dual accuracy scoring](docs/dual-accuracy-scoring.md).

## Transform validation

The endpoint `POST /v1/transforms/validate-reference` accepts traceable measured reference-vector manifests and produces an audit report. A passing audit does not automatically promote a camera profile. See [Camera transform validation workflow](docs/camera-transform-validation-workflow.md).

## Development

Install the API and development dependencies:

```bash
python -m pip install -e ".[dev,api,images,high-precision,ocio]"
uvicorn yrgb_engine.api:app --reload
```

Run the frontend in a second terminal:

```bash
cd web
npm install
npm run dev
```

The native float decoder/exporter requires OpenImageIO and NumPy. Actual TIFF/OpenEXR plugin support depends on the server build. Browser preview is a responsive display preview and is not a substitute for the native float master.

## Quality gates

- Run backend tests and frontend TypeScript/Vite build before treating a change as verified.
- Do not mark a camera transform verified using synthetic fixtures alone.
- Do not conflate browser sRGB scopes with native linear scopes.
- Do not conflate Correction Accuracy with Creative Look Similarity.
- Do not label a format or camera mode supported until representative decode, metadata, color-transform, and export round-trip tests pass.
- Work on the feature branch until explicitly asked to merge.

## Repository layout

- `src/yrgb_engine/` — Python engine, transforms, grading, scopes, API and export.
- `web/` — React/Vite interactive grading school interface.
- `tests/` — numerical, API and integration contract tests.
- `docs/` — architecture, validation and workflow documentation.
