# Sony S-Log3 / S-Gamut3.Cine Reference Acquisition

## Acquisition status

**Profile status: UNVERIFIED.** This note records authoritative source material found for the first Sony profile. It does not approve a camera transform or enable numerical Correction Accuracy.

## Official Sony material

Sony's official "Sony Look Profile (3D LUT)" support package is published at:

- https://www.sony.com/electronics/support/software/00263050
- Package release date shown by Sony: 2016-02-26.
- Sony lists a 448 KB Sony Look Profiles Summary PDF.
- Sony lists an 867 KB Technical Summary for S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3.
- Sony lists a 3.01 MB Look Profile for S-Gamut3.Cine/S-Log3 LUT download.
- Sony's applicable-model list on this package page includes F65RS, VENICE / VENICE 2, PMW-F5/F55, NEX-FS700R, PXW-FS5/FS5M2 and PXW-FS7/FS7M2.

Sony's LUT import guidance:

- https://www.sony.com/electronics/support/articles/00253964
- Sony specifies 17-point or 33-point 3D LUTs in .cube format for the documented import workflow.
- The declared input options include S-Gamut3.Cine/S-Log3 and S-Gamut3/S-Log3.

Sony's monitor-LUT guidance:

- https://www.sony.com/electronics/support/articles/00253956
- Sony describes s709, 709(800%) and S-Log3 as monitor-LUT/base-look choices. These are not interchangeable with a scene-linear camera input transform.

## OpenColorIO / ACES candidate transform source

The Academy Software Foundation's official OpenColorIO-Config-ACES v4.0.0 release is:

- https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/tag/v4.0.0
- Release asset: `studio-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio`
- Asset size: 93,402 bytes.
- Published asset SHA-256: `0f19d42caab7213be71decd92edd802e67df737b438471013819b01b23238e9d`
- Release page: https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/tag/v4.0.0

The v4.0.0 Studio config documents these distinct Sony spaces:

- `S-Log3 S-Gamut3.Cine`
- `Linear S-Gamut3.Cine`
- `S-Log3 S-Gamut3`
- `Linear S-Gamut3`
- Separate Venice S-Gamut3 and Venice S-Gamut3.Cine variants.

It also includes a scene-linear DaVinci Wide Gamut space (`Linear DaVinci WideGamut`) as distinct from the encoded `DaVinci Intermediate WideGamut` space.

This gives us a traceable candidate transform configuration and correct linear destination candidate. The release config must still be downloaded into the project, hash-checked locally, loaded with the matching OCIO runtime, and tested for exact space availability before use.

## Critical distinctions

1. Sony Look Profile LUTs are creative/monitoring transforms. They are useful for visual QC and comparison, but they are not by themselves a camera-to-linear reference dataset.
2. The S-Log3/S-Gamut3.Cine and S-Log3/S-Gamut3 pairings must remain separate.
3. Venice-specific color-space variants must not be silently treated as generic Sony S-Gamut3.Cine.
4. The existing registry's `DaVinci Intermediate WideGamut` destination is encoded, not scene-linear. It must not be labelled as linear-light for exposure/WB/tonal measurement.
5. A Sony-published LUT package and an ACES config mapping do not constitute independent measured camera-patch vectors. No camera profile may be promoted to verified on that basis alone.

## What remains necessary for production approval

- Pin and vendor the exact ACES v4.0.0 Studio config with its published SHA-256, or select another exact approved config and pin that instead.
- Confirm the installed PyOpenColorIO version supports the config.
- Confirm exact source and destination space names using the loaded config.
- Transform S-Log3/S-Gamut3.Cine to a verified scene-linear working space before objective measurements.
- Acquire an independently traceable reference set containing actual measured patches for a named Sony camera model and exact recording mode, codec and bit depth. Preserve source documentation, measurement method, patch labels, input RGB values and expected linear RGB values.
- Compare the OCIO transform against that reference set at a declared tolerance.
- Keep the profile unverified until the above checks pass.

## Current decision

Sony S-Log3 / S-Gamut3.Cine remains **UNVERIFIED**. The official Sony LUT and documentation sources plus the pinned ACES config are useful inputs to implementation, but they do not replace independent camera/reference measurements. No fabricated vectors or synthetic fixtures are included in this record.
