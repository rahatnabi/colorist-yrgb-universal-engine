# Reference-Validated Camera Transform Gate

An OCIO processor running without error does not prove that a camera transform is colorimetrically correct. The engine therefore keeps the camera registry unverified until an exact transform is compared with independently sourced reference vectors.

## Validation record

`TransformValidationResult` captures the exact transform ID, source and destination spaces, SHA-256 of a pinned OCIO config, reference-set ID, vector count, maximum absolute RGB error, tolerance, and OCIO version.

Use `validate_ocio_config` with:
- a pinned OCIO config file,
- exact source/destination color-space names,
- independently measured or vendor-published input/output reference vectors,
- a documented tolerance appropriate to the reference data.

A synthetic identity test is useful for unit testing the gate only. It is not a valid camera transform reference set and must never be used to mark a production camera profile verified.

## Applying a passing transform

`apply_reference_validated_transform` checks that the record passed, the exact source/destination names match, and the config file hash is unchanged. Only then does it apply OCIO and mark the resulting frame validated in the declared destination space.

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
- a positive reference-vector count.

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
