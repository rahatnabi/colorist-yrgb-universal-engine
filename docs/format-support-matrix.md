# Media Format Support Matrix

This is a **planned capability matrix**, not a declaration that these formats already work. A format becomes supported only after representative fixtures pass probe, decode, metadata, color-management, and export tests on the target platform.

| Media family | Examples | Planned adapter | Important constraints |
|---|---|---|---|
| Still image | JPEG, PNG 8/16-bit, TIFF | OpenImageIO / native image adapters | Profile metadata, bit depth, alpha, orientation |
| High-dynamic-range still | OpenEXR, DPX | OpenImageIO | Channel layouts, precision, transfer/primaries metadata |
| RAW still | DNG and supported camera RAW | LibRaw / optional vendor SDK | Camera-model support varies; RAW is not guaranteed by extension alone |
| Video containers | MOV, MP4, MXF, MKV | FFmpeg / ffprobe | Container is not codec; streams and metadata vary |
| Video codecs | H.264/AVC, HEVC, ProRes, DNxHD/DNxHR | FFmpeg and platform codecs where available | Licensing/build flags, profile, chroma subsampling, bit depth |
| Image sequences | DPX, EXR, TIFF, PNG sequences | OpenImageIO + sequence reader | Frame numbering, missing frames, timebase |
| Cinema camera RAW | CinemaDNG and selected proprietary RAW | Dedicated adapters | Vendor SDK/license and platform restrictions |
| LUTs | .cube initially | Internal parser + validation | Input/output color space must be declared or confirmed |
| Resolve grade metadata | .drx | Future interoperability adapter | Not an image format; requires compatible still/reference workflow |

## Critical terminology

- **Container:** MOV, MP4, MXF, MKV.
- **Codec:** ProRes, H.264, HEVC, DNxHR.
- **Camera encoding/profile:** S-Log3, LogC4, V-Log, Apple Log, etc.
- **Gamut:** S-Gamut3.Cine, ARRI Wide Gamut, REDWideGamutRGB, etc.
- **RAW:** Sensor-derived data requiring a camera-aware decode process.
- **LUT:** A transform asset; its intended input/output spaces must be known.
- **DRX:** DaVinci Resolve grading metadata, not a standalone picture format.

## Support states

- `planned`: identified for future work
- `probing`: container/metadata detection implemented and tested
- `decode-tested`: representative fixture decodes correctly
- `color-verified`: transform behavior validated against trusted references
- `export-verified`: round-trip/export checks pass
- `supported`: all required checks pass for a documented platform/build
- `unsupported`: known limitation or unavailable dependency

Every support claim must state platform, decoder version, tested profile/bit depth, and known limitations.
