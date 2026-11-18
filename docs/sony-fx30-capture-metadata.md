# Sony FX30 Capture Metadata Record

## Evidence source

This record is transcribed from a user-supplied Sony non-real-time metadata XML file named `C1382M01.XML`. It records one capture's metadata only. It is **not** a measured color-reference chart, a transform-validation manifest, or proof that an OCIO transform is accurate.

## Camera and image signal

| Field | XML value |
|---|---|
| Manufacturer | Sony |
| Camera model | ILME-FX30 |
| Lens | E 17–70mm F2.8 B070 |
| Capture gamma | `s-log3-cine` |
| Capture color primaries | `s-gamut3-cine` |
| Coding equations metadata | `rec709` |
| Video codec descriptor | `AVC140_3840_2160_H422P@L51` |
| Raster | 3840 × 2160 |
| Capture / format rate | 25.00p / 25p |
| Aspect ratio | 16:9 |
| Duration | 192 frames (7.68 seconds at 25 fps) |
| Recording mode | normal |
| Audio | 2-channel LPCM16 |

The XML's `CodingEquations=rec709` value is preserved verbatim. It is not interpreted here as a display transform, a complete matrix/range declaration, or evidence that the recorded picture is Rec.709 display-referred.

The XML does not explicitly provide a bit-depth field, ISO, shutter, aperture, white-balance setting, or a measured chart patch set. Do not infer these missing values from the codec descriptor or lens metadata.

## Related LUT

The XML references `SL3SG3Ctos709.cube` as a related LUT. This is recorded as a file association only. The LUT itself was not supplied with this XML and must not be treated as a scene-linear camera input transform or independent camera-reference data.

## Profile mapping decision

The exact observed camera/gamma/gamut tuple matches the candidate registry profile:

- Profile ID: `sony.slog3.sgamut3cine`
- Camera model alias added: `ILME-FX30`
- OCIO source-space candidate: `S-Log3 S-Gamut3.Cine`
- OCIO destination-space candidate: `Linear DaVinci WideGamut`
- Status: **UNVERIFIED**

The FX30 model match is useful for identifying the correct candidate profile. It does not authorize conversion or numerical Correction Accuracy. The profile remains blocked until the pinned OCIO transform is compared against independently measured, traceable camera reference patches.

## Remaining capture evidence

For a real still-image transform test, retain an original ungraded frame extracted from the camera original without transcoding or a display LUT. Keep its source metadata alongside it. For production validation, also obtain an independently measured chart/reference set with documented chart identity, camera model, recording settings, codec, bit depth, measurement method, and expected scene-linear values.

A single natural-scene still can test decoding, metadata association, transform execution, and visual plausibility. It cannot by itself establish objective transform accuracy.
