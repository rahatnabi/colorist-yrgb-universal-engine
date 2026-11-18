# COLORIST YRGB — UNIVERSAL COLOR ENGINE

**Image + Video · RAW + LOG · LUT + Color Science**

An extensible color workflow and learning platform for still images and video. The project is designed around a shared, scene-referred color-processing core with separate media-ingest paths.

## Project status

**Foundation stage — media-intelligence and color-analysis core in active development.** Numerical analysis, LUT parsing/application, profile registry, and diagnostic APIs have automated coverage. A production browser grading UI, complete production decoder matrix, full grading/render engine, and export pipeline are not yet implemented.

## Product principles

- Support still images and video through dedicated ingest/decode adapters.
- Treat camera Log as an encoding/profile, not as a file extension.
- Use explicit, verifiable camera gamut/gamma profiles; never silently guess an unknown transform.
- Keep decode, color management, analysis, grading, display, and export as separate layers.
- Prefer open standards and libraries; isolate proprietary camera SDK integrations behind optional adapters.
- Use proxies for responsive browser video review; preserve a path to high-quality local/server rendering.
- Make format and camera-profile support testable and versioned.

## Planned architecture

1. Media ingest and validation
2. Still-image and video decode adapters
3. Camera / input-profile registry
4. Color-management layer (OpenColorIO)
5. Shared image-processing and grading core
6. Analysis and scopes
7. LUT import, validation, and application
8. Preview, export, and QC
9. Academy lessons, exercises, and assessment

See [Architecture](docs/architecture.md) and [Format support policy](docs/format-support-matrix.md).

## Proposed technology choices

- Python for orchestration and API services
- C++ for performance-sensitive processing where profiling justifies it
- FFmpeg / ffprobe for video probing, decode integration, and proxy workflows
- OpenImageIO for image I/O and image-sequence workflows
- LibRaw for compatible RAW still-image decoding
- OpenColorIO for color configuration and transforms
- FastAPI for the initial service API
- React / Next.js for the web interface (to be added in a later phase)

These are candidate dependencies, not a claim that every codec or camera format is already supported. Licensing, platform availability, bit depth, metadata fidelity, and build compatibility must be checked before adoption.

## Implemented foundation

- Precision-preserving float32 frame model and explicit color-encoding metadata.
- Optional still-image, RAW, video-frame, and image-sequence decode adapters.
- Exact-match camera profile registry with explicit candidate discovery; no automatic profile guessing.
- OpenColorIO transform adapter and .cube parsing/application reference implementation.
- Frame histograms, RGB Parade, optional waveform/vectorscope data, and JSON-ready scope snapshots.
- Exposure, spatial exposure, temporal exposure, color matching, and operator-selected ROI chroma diagnostics.
- Initial FastAPI service boundary for health, capability discovery, camera-profile candidate lookup, and bounded media probing.
- Automated tests and CI checks for the implemented numerical contracts.

These are engine foundations, not a claim that every decoder, camera transform, scope visualization, or real-time workflow is production-ready. Camera profile entries remain unverified until reference transforms and known-value tests are completed.

## HTTP API

Install with `python -m pip install -e ".[dev,api]"` and run `uvicorn yrgb_engine.api:app --reload`. The initial API provides `/health`, `/v1/capabilities`, `/v1/profiles`, `/v1/profiles/candidates`, and `/v1/media/probe`. See [HTTP API](docs/http-api.md) for limits and deployment caveats. The browser grading interface is still planned, not implemented.

## Development

Add features behind tests and explicit capability flags. Do not label a format as supported until a representative fixture passes decode, metadata, color, and export checks. Do not label a camera profile as transform-ready until its exact camera/gamut/encoding combination is independently validated.

## License

License selection is pending. Do not assume this repository grants permission to redistribute third-party SDKs, sample footage, LUTs, or camera profiles.


## Web workspace

The early React/Vite interface is in [`web/`](web/README.md). Run the API with `uvicorn yrgb_engine.api:app --reload`, then in another terminal run `cd web && npm install && npm run dev`. The UI currently supports local browser previews, media metadata probing, and camera-profile candidate discovery. Numerical scope rendering and grading controls are not yet connected.
