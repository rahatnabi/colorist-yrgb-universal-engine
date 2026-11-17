# Universal Color Engine — Architecture

## 1. System boundary

The engine accepts still-image files, video files, image sequences, and LUT assets. It probes each asset, selects a compatible decoder, resolves or requests an explicit input color profile, processes frames in a shared color pipeline, and produces previews or validated exports.

## 2. High-level flow

```text
Asset Upload
    |
    v
Ingest + Security/Size Validation
    |
    v
Probe + Metadata Extraction
    |
    +-------------------------+
    |                         |
    v                         v
Still Image Decoder      Video / Sequence Decoder
    |                         |
    +------------+------------+
                 |
                 v
        Canonical Frame Buffer
                 |
                 v
       Input Profile Resolution
                 |
                 v
       OpenColorIO Transform
                 |
                 v
       Working Space (initial target:
       DaVinci Wide Gamut / Intermediate
       where a validated config is available)
                 |
        +--------+---------+
        |                  |
        v                  v
   Analysis / Scopes   Grading Operations
        |                  |
        +--------+---------+
                 |
                 v
          Output Transform
                 |
                 v
          Preview / Export / QC
```

## 3. Core modules

### Ingest
- Validate file size, extension, container signature, and content.
- Treat extensions as hints only; inspect actual file/container data.
- Prevent path traversal and unsafe archive expansion.
- Record a stable asset ID and source metadata.

### Probe and profile resolution
- Extract dimensions, frame rate, bit depth, pixel format, codec, stream metadata, and available camera tags.
- Resolve an input transform only when camera model, recording mode, gamut, gamma/log generation, and other required parameters are sufficiently known.
- If evidence is incomplete or conflicting, mark the profile as unresolved and ask for user selection. Never silently apply a guessed camera transform.

### Decode adapters
- Still-image adapters and video adapters remain separate because their decode, metadata, timing, and color semantics differ.
- Normalize decoded data into a documented internal frame representation without discarding source precision prematurely.
- Preserve alpha, orientation, timecode, and relevant metadata where the source and decoder expose them.

### Color management
- Use OpenColorIO as the transform/configuration layer.
- Keep input, working, display, and output transforms explicit.
- Store the exact OCIO config/version and transform identifiers with project state.
- A DaVinci Wide Gamut / DaVinci Intermediate working path is a target integration, not an assumption that Resolve's proprietary configuration is bundled or licensed.

### Analysis and grading
- Build deterministic, testable operations: exposure, balance, contrast, saturation, channel controls, curves, and LUT application.
- Separate measurement from creative rendering.
- Document whether each metric is computed in encoded, scene-linear, or display-referred values.

### Preview and export
- Generate lower-resolution proxies for interactive browser playback.
- Preserve a high-quality processing path for final output.
- Validate output color tags, bit depth, dimensions, frame rate, and audio preservation where applicable.

## 4. Still image and video behavior

### Still images
- Preserve source bit depth and color profile when possible.
- RAW decoding requires a compatible decoder and camera support.
- JPEG is generally display-referred and does not retain the same highlight-recovery latitude as sensor RAW.
- Multi-page/multi-frame formats must be handled deliberately rather than treated as ordinary single images.

### Video
- Containers (MOV, MP4, MXF, MKV) are distinct from codecs (ProRes, H.264, HEVC, DNxHR, etc.).
- Log is an encoding/profile, not a container or extension.
- A video may contain multiple streams, audio, timecode, metadata, and variable frame rate.
- Browser playback should use proxies where direct browser decode is not reliable.

## 5. Camera profile registry

Each profile entry should include:
- Manufacturer and camera family/model scope
- Profile identifier and generation
- Camera gamut / color space
- Transfer function / Log curve
- Required metadata (EI/ISO, white-balance assumptions, firmware constraints, etc.)
- Source and license/provenance
- OCIO transform identifier or implementation
- Test fixtures and expected tolerances
- Status: experimental, verified, deprecated

Initial candidate families: Sony S-Log, ARRI LogC, Canon Log, RED Log3G10, Blackmagic Film, Panasonic V-Log, Fujifilm F-Log, Nikon N-Log, DJI D-Log, and Apple Log. Exact camera/generation compatibility must be verified before marking any entry supported.

## 6. Non-goals for the first milestone

- Claiming universal proprietary RAW support
- Reproducing DaVinci Resolve's internal processing
- Bundling unlicensed camera SDKs, LUTs, or footage
- Claiming film-stock emulation from a simple contrast curve or print LUT alone
- Applying transforms based only on a filename or guessed camera model
