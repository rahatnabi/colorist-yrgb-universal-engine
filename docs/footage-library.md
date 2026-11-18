# COLORIST YRGB — Footage Library (Milestone 2)

Status: **library foundation and non-destructive intake tooling implemented; first user-supplied Sony S-Log3/S-Gamut3.Cine intake remains registered but pending original-byte access and metadata verification.**

## Purpose

Build a traceable, reusable media library for still-image and video training, decoder testing, camera-profile evaluation, exposure exercises, shot matching, and export/QC. A library item must have a known provenance and a clearly stated validation scope.

## Evidence classes

1. **Camera-original media** — unaltered camera files and associated metadata/sidecars.
2. **Training media** — footage licensed for teaching and learner redistribution.
3. **Decoder conformance fixtures** — files used to test container/codec/decoder behavior.
4. **Color-science reference media** — chart captures or measured patch data with traceable measurement provenance.
5. **Synthetic media** — generated test patterns used only for controlled numerical tests.

These classes must never be silently substituted for one another. A decoder fixture is not a camera transform reference. A camera-original clip is not colorimetry ground truth unless measured references accompany it.

## Library layout

Large media binaries should not be committed to ordinary Git history. Store them in a controlled object store or Git LFS only after reviewing quota, access, and redistribution rights.

```text
footage-library/
  manifest/
    schema.json
    assets.json
  originals/              # immutable camera originals; access-controlled
  sidecars/               # XML, JSON, camera reports, checksums
  proxies/                # generated review copies; never replace originals
  frame-stills/           # extracted frames with source timecode/frame index
  reference-data/         # measured chart patches and validation vectors
  exercises/              # learner-ready copies with license clearance
  reports/                # probe, decode, color, and QC reports
```

## Non-destructive intake reporter

The new `scripts/footage_intake.py` utility hashes supplied files with SHA-256, reports byte sizes, parses XML leaf values/attributes without assigning undocumented vendor meanings, and invokes the existing media probe for non-XML files. It never modifies or copies the source files.

After installing the project dependencies, run:

```bash
python scripts/footage_intake.py /path/to/C1382.MP4 /path/to/C1382M01.XML \
  /path/to/C1383.MP4 /path/to/C1383M01.XML \
  --output reports/sony-slog3-intake.json
```

For a hash + XML-only pass without ffprobe:

```bash
python scripts/footage_intake.py /path/to/C1382M01.XML --skip-probe
```

The report records each file independently. A video may report `probe_unavailable`, `probe_failed`, or `probe_timeout`; these are explicit states, not evidence that the file is corrupt. Preserve the original report and tool versions with the dataset.

## Intake pipeline

1. Register the asset and source/provenance before processing.
2. Preserve the original bytes; calculate SHA-256 and byte size.
3. Probe container, streams, codec/profile, pixel format, dimensions, frame rate, range, transfer, primaries, matrix, and bit depth when available.
4. Parse sidecars (Sony XML, camera reports, timecode) without treating missing fields as known.
5. Record camera make/model, recording mode, firmware, ISO/EI, white balance, gamut, and Log curve only when supported by metadata or explicit user confirmation.
6. Decode a small set of frames and record decoder/version and warnings.
7. Compare decoded frame metadata and image properties against the probe report.
8. Generate review proxies separately; preserve originals.
9. Assign a validation state and review the asset before using it in exercises or transform validation.

## First intake candidate: Sony S-Log3 / S-Gamut3.Cine

The user supplied a Google Drive folder link and identified the clips as Sony S-Log3.Cine. The initial folder listing was reported to contain:
- `C1382.MP4`
- `C1382M01.XML`
- `C1383.MP4`
- `C1383M01.XML`

**Important:** these names and the user-declared profile are intake leads, not verified media metadata. The actual media bytes have not yet been imported or hashed by this repository. The exact camera model, recording mode, codec, bit depth, frame rate, firmware, and embedded color tags remain unverified until the MP4 and XML bytes can be read.

For the initial intake, preserve the user-declared S-Log3 / S-Gamut3.Cine as an annotation with provenance `user_asserted`; do not let it automatically approve or apply a transform. The capture matcher must still check exact camera model and available metadata, and the camera transform remains unverified until independent reference vectors pass the validation gate.

## Licensing and privacy

- Record the source URL or owner-provided reference, license/permission, allowed uses, attribution, and redistribution status.
- A share link is not a license.
- Do not publish private or identifiable footage, metadata, or sidecars without permission.
- Do not mirror third-party media into GitHub merely because it is downloadable.
- If redistribution is not explicitly allowed, keep the source private and publish only permitted metadata or derived, non-identifying technical reports.

## Asset states

- `registered`: asset identity/provenance recorded.
- `bytes_acquired`: original bytes received and checksum recorded.
- `probed`: container and stream metadata extracted.
- `decoded`: representative frames decoded and inspected.
- `metadata_reviewed`: camera/recording metadata checked against sidecars.
- `training_cleared`: rights allow the intended learner access/use.
- `reference_qualified`: independent measurements and traceability support a stated validation use.

A state must not be skipped by inference. Each asset may have multiple purpose-specific approvals; `decoded` does not mean `color-verified`.

## First dataset acceptance checks

- [ ] Original MP4 bytes acquired without recompression.
- [ ] XML sidecars acquired and parsed.
- [ ] SHA-256 and byte sizes recorded.
- [ ] ffprobe report saved with decoder/tool versions.
- [ ] Exact camera model and recording mode confirmed.
- [ ] S-Log3 transfer and S-Gamut3.Cine primaries confirmed, not inferred from filename.
- [ ] Bit depth, chroma subsampling, codec profile, frame rate, and range recorded.
- [ ] Representative frames decode and retain expected metadata.
- [ ] Usage/redistribution permission recorded.
- [ ] Any color-transform reference claims supported by separate measured vectors.

## Current blocker

The Google Drive folder link is available as a user-provided source reference, but the Drive connector is not available in this workspace and the binary contents have not been fetched. Do not mark this dataset acquired or validated. The next intake step is to obtain the original MP4 and XML bytes through an accessible direct download/share route, then run the checksum and probe pipeline.
