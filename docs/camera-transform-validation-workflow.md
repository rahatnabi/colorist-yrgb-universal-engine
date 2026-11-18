# Camera transform validation workflow

This workflow validates one exact camera profile against traceable, independently
measured RGB reference vectors. A candidate mapping or a successful OCIO lookup
is not validation.

## Safety gates

- Keep the camera profile `status` as `unverified` until independent evidence
  has been reviewed and explicitly added to the registry.
- Never use synthetic identity vectors to approve a production camera transform.
  Synthetic vectors may test the validator only.
- Pin the exact OCIO config file and retain its SHA-256 hash with the audit.
- Keep camera model, recording mode, codec, bit depth, and source gamut exact.
  Do not fill missing capture metadata by guessing.
- The transform destination for objective correction scoring must be scene-linear.
  `DaVinci Intermediate WideGamut` is an encoded working space, not linear light.
- A passing camera transform does not validate the separate display transform.

## Required measured manifest

The JSON manifest must use schema version 1 and include:

- `profile_id`, `transform_id`, `source_space`, `destination_space`
- unique `reference_set_id`
- traceable `reference_source` and documented `measurement_method`
- exact `camera_model`, `recording_mode`, `codec`, and integer `bit_depth`
- one or more measured vectors with unique labels, `source_rgb`, and
  independently established `expected_rgb`

Do not create values for the vectors from a guessed Log curve, a creative LUT,
a monitor LUT, or an unverified conversion. The validator needs measured input
and expected output values in the declared source/destination domains.

## Sony FX30 note

The supplied FX30 XML sidecar identifies S-Log3 / S-Gamut3.Cine and the AVC
recording descriptor. It does not state bit depth or provide measured chart
patch RGB values. Therefore it is useful for profile identification, but it
cannot by itself form a valid transform-validation manifest. Obtain the
missing capture facts and a traceable measured reference set before attempting
approval.

Sony documentation:
- [FX30 Picture Profile](https://helpguide.sony.net/ilc/2220/v1/en/contents/TP1000876510.html)
- [FX30 Log Shooting Setting](https://helpguide.sony.net/ilc/2220/v1/en/contents/TP1000888942.html)
- [Sony LUT package](https://www.sony.com/electronics/support/software/00263050)

OCIO reference:
- [ACES OCIO Config v4.0.0](https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/tag/v4.0.0)

## Run validation locally

Install the optional dependencies and use the exact pinned config:

```bash
pip install -e ".[ocio]"
yrgb-validate-transform \
  --manifest path/to/measured-reference.json \
  --config path/to/pinned-studio-config.ocio \
  --tolerance 0.00001 \
  --output transform-validation-audit.json
```

Exit code 0 means the vectors passed the configured tolerance. Exit code 2
means validation failed or could not be completed. Preserve the audit output.

## Run through the API

Configure `YRGB_OCIO_CONFIG` on the API server, then upload the manifest:

```bash
curl -X POST "http://localhost:8000/v1/transforms/validate-reference?tolerance=0.00001" \
  -F "manifest_file=@measured-reference.json"
```

The endpoint returns the validation audit and `promotion_status: not_promoted`.
It never edits the registry or enables the transform. A human review must verify
the reference provenance, camera mode, bit depth, OCIO config identity, and
measurement procedure before the registry can be changed.

## Next production approval checklist

1. Confirm the source values represent the exact camera encoding and recording mode.
2. Confirm expected values come from an independent, traceable measurement workflow.
3. Validate with a pinned OCIO config and inspect maximum absolute RGB error.
4. Review the evidence independently; do not approve based on synthetic tests.
5. Add the audit record to the exact profile and only then set `status: verified`.
6. Run the still-image transform preview and verify that the output transfer is
   explicitly linear before enabling objective Correction Accuracy scoring.
