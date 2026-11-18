# Reference-Validated Camera Transform Gate

An OCIO processor running without error does not prove that a camera transform is colorimetrically correct. The engine therefore keeps the camera registry unverified until an exact transform is compared with independently sourced reference vectors.

## Validation record

`TransformValidationResult` captures the exact camera registry profile ID, transform ID, OCIO source/destination spaces, SHA-256 of a pinned OCIO config, reference-set ID, vector count, maximum absolute RGB error, tolerance, and OCIO version. Camera profile IDs and OCIO color-space names are separate identities; they must never be assumed to be the same string.

Use `validate_ocio_config` with:
- a pinned OCIO config file,
- exact source/destination color-space names,
- independently measured or vendor-published input/output reference vectors,
- a documented tolerance appropriate to the reference data.

A synthetic identity test is useful for unit testing the gate only. It is not a valid camera transform reference set and must never be used to mark a production camera profile verified.

## Applying a passing transform

`apply_reference_validated_transform` checks the frame's camera registry profile ID, validation profile ID, transform ID, exact OCIO source/destination names, and unchanged config hash. It also requires explicit destination transfer and primaries. Only then does it apply OCIO and mark the resulting frame validated in the declared destination space. `prepare_frame_for_working_space` performs the registry-driven orchestration and blocks unknown, unverified, or incomplete profiles.

The caller must still declare the destination transfer function accurately. For DWG/Intermediate, the transfer is DaVinci Intermediate, not scene-linear. Exposure and linear-light operations must use an explicitly linear destination or a separate, validated conversion to linear light.

## Current catalogue status

The initial camera profile catalogue intentionally remains unverified. No manufacturer profile is promoted based on a successful OCIO execution alone. Each production profile needs its own camera/generation-specific reference vectors and validation record.


## Registry integration

A passing result exposes `to_registry_record()`. The returned audit fields can be stored under a profile's `validation` object together with the matching `transform_id`. The registry only reports `usable_for_transform=true` when all of the following are present:

- profile status is `verified`,
- a non-empty `transform_id`,
- `validation.passed=true`,
- a 64-character config SHA-256,
- a non-empty reference-set ID,
- a positive reference-vector count,
- validation evidence bound to the same registry profile and transform IDs,
- exact OCIO source/destination spaces matching the profile record,
- declared output transfer and primaries.

The web profile discovery panel displays whether a profile has independent reference-validation evidence. It does not provide a button to self-certify a profile. Registry catalogue entries remain unverified until real reference sets are added and reviewed.


## Expanded camera profile catalogue

The candidate registry now includes:
- Insta360 Luna Ultra / Luna Pro: I-Log with Rec.2020 input gamut.
- Insta360 X5 / X6: separate 10-bit I-Log / BT.2020 candidate. This is intentionally not merged with the Luna-series I-Log curve.
- DJI D-Log / D-Gamut, kept separate from D-Log M and D-Log2.
- Nikon N-Log / N-Gamut.
- RED Log3G12 / REDWideGamutRGB, kept separate from the existing Log3G10 entry.
- Blackmagic Pocket Cinema Camera 4K and 6K family: separate Gen 4 and Gen 5 candidates, tied to explicit camera-model lists.

These are catalogue entries, not validated conversion transforms. Every new/updated entry remains `unverified` and cannot drive a transform until independent reference vectors, a pinned OCIO configuration, and a passing validation record are supplied. Camera mode, codec, firmware, and RAW decode metadata may still affect the correct interpretation. In particular, never apply a Luna I-Log curve to X-series I-Log simply because the display label is similar.


### Apple Log family

Apple is represented by two distinct candidate records:
- `Apple Log / BT.2020`: Apple-defined Log transfer function with BT.2020 primaries; recording support begins with iPhone 15 Pro.
- `Apple Log 2 / Apple Gamut`: a separate Apple-defined Log transfer function with Apple Gamut primaries; recording support begins with iPhone 17 Pro.

Do not substitute Apple Log for Apple Log 2 or vice versa. Preserve transfer-function and color-primaries metadata from the media when available. Both registry entries remain unverified until independently checked against authoritative reference vectors and a pinned transform configuration.


## Current implementation boundary

The registry-driven preparation function is implemented and covered by synthetic unit tests. Those tests prove identity matching, config pinning, and fail-closed behavior; they do not validate any real camera transform. The current production catalogue still contains no approved camera-to-DWG/Intermediate transforms, so real media conversion correctly remains blocked until independent reference sets and approved OCIO configurations are supplied. DWG/Intermediate is not tagged as scene-linear; linear-light exposure tools must use a separate validated linear transform.


## Upstream OCIO transform candidates

The registry now records candidate OCIO color-space names aligned with the AcademySoftwareFoundation OpenColorIO-Config-ACES v4.0.0 release (ACES 2.0 / OCIO 2.5) for these families:

- Sony S-Log3 / S-Gamut3 and S-Gamut3.Cine
- ARRI LogC3 (EI800) and LogC4
- Canon Log3 / Cinema Gamut
- Panasonic V-Log / V-Gamut
- RED Log3G10 / REDWideGamutRGB
- Blackmagic Film Gen 5 / Blackmagic Wide Gamut
- Apple Log
- DJI D-Log / D-Gamut (`D-Log D-Gamut` source space; OCIO processor compatibility confirmed, reference validation pending)

The candidate destination is DaVinci Intermediate WideGamut, with declared DaVinci Intermediate transfer and DaVinci Wide Gamut primaries. These names are intended for an explicitly pinned, compatible upstream OCIO config; the engine does not silently download or substitute a config. The ACES config is an upstream transform implementation, not by itself independent camera reference measurements. Therefore every mapped profile still reports mapped_unvalidated and remains blocked from automatic conversion until its exact config hash and independent reference-vector set pass.

Profiles not represented by this upstream mapping (including the current Insta360 I-Log variants, Nikon N-Log, RED Log3G12, and Blackmagic Gen 4) remain mapping-unavailable until an exact, documented transform source is identified.


## Sony S-Log3 / S-Gamut3.Cine reference-validation workflow

A machine-readable manifest template is provided at `data/reference_vectors/sony_slog3_sgamut3cine.template.json`. It is intentionally empty: no measured camera/reference values are fabricated or supplied as production evidence.

1. Confirm the exact Sony camera model, recording mode, codec, bit depth, and S-Gamut3.Cine metadata for the source material.
2. Obtain independently measured reference values with a documented source, chart/patch identity, capture conditions, and measurement method. Values must be expressed in the manifest's exact source and destination OCIO spaces.
3. Copy the template, fill `reference_source`, `measurement_method`, and the measured `vectors` array. Do not use identity vectors or guessed values.
4. Install the OCIO 2.5-compatible Studio config from the official ACES v4.0.0 release and keep that exact config file unchanged for the run.
5. Run:

```bash
python -m pip install -e ".[ocio]"
yrgb-validate-transform \
  --manifest data/reference_vectors/sony_slog3_sgamut3cine.json \
  --config /absolute/path/to/studio-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio \
  --tolerance 0.00001 \
  --output sony-slog3-reference-validation.json
```

The command checks that manifest profile/transform/space names exactly match the registry, evaluates every vector through the pinned OCIO processor, records the config SHA-256 and OCIO version, and writes an audit record. Exit code `0` means the numeric comparison passed; exit code `2` means validation failed or required evidence is missing.

A passing report is a candidate audit artifact, not automatic approval. A reviewer must inspect the reference provenance, capture metadata, vector coverage, tolerance, and transform behavior before adding the report to the profile's `validation` record and changing its status to `verified`. The tool never edits the registry or enables a camera transform automatically.

The official ACES v4.0.0 release identifies the Studio config as an OCIO 2.5 config and lists the Sony S-Log3 / S-Gamut3.Cine and DaVinci Intermediate WideGamut spaces. It also notes DJI D-Log / D-Gamut transform support. Space-name availability is a compatibility check, not independent camera validation. See the [official ACES config release](https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/tag/v4.0.0).
