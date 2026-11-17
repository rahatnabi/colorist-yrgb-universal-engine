# COLORIST YRGB — UNIVERSAL COLOR ENGINE

**Image + Video · RAW + LOG · LUT + Color Science**

An extensible color workflow and learning platform for still images and video. The project is designed around a shared, scene-referred color-processing core with separate media-ingest paths.

## Project status

**Foundation stage — architecture and repository scaffold.** No production decoder, grading engine, or export pipeline is claimed to be implemented yet.

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

## Development

The first milestone is a reliable media-probing and profile-identification foundation. Add features behind tests and explicit capability flags. Do not label a format as supported until a representative fixture passes decode, metadata, color, and export checks.

## License

License selection is pending. Do not assume this repository grants permission to redistribute third-party SDKs, sample footage, LUTs, or camera profiles.
