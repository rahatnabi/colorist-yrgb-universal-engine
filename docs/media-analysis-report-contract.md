# Media Analysis Report Contract

This contract defines the evidence required before COLORIST YRGB can treat a media-analysis result as verified. It is deliberately separate from the footage-asset manifest: the manifest tracks the asset and acquisition lifecycle; this report tracks technical claims and measurements.

Schema: `data/footage_library/media_analysis_report.schema.json`

## Verification states

- `verified`: supported by acquired source bytes or a reproducible measurement with its method and provenance.
- `reported`: copied from a user, sidecar, container tag, or external report but not independently confirmed.
- `estimated`: inferred or approximated; never a substitute for measured data.
- `conflict`: two or more sources disagree.
- `unresolved`: evidence is insufficient to choose between plausible interpretations.
- `unavailable`: the value could not be obtained.
- `not_validated`: no validation has been performed.

Do not promote a claim from `reported` to `verified` merely because multiple reports repeat it.

## Separate measurement domains

Every analysis must preserve these domains independently:

1. **Original YUV code values** — decoded Y, Cb and Cr plane samples in the decoder's declared pixel format. Record bit depth, plane dimensions, range and sample denominator.
2. **Nonlinear RGB code values** — RGB after a documented matrix/range conversion and before transfer-function decoding. Record matrix coefficients, range handling, clipping policy and output numeric scale.
3. **Linear-light RGB** — obtained by applying the confirmed inverse transfer function to every pixel sample before calculating statistics. Never inverse-transfer channel means or medians.

A YUV-to-RGB matrix does not establish the transfer function. Matrix coefficients, range, transfer function and primaries are separate properties.

## Range excursions and clipping

Do not combine these metrics:

- Legal-range excursions: samples outside the declared nominal video range.
- Hard code saturation: samples at the representable minimum or maximum code values.
- Display clipping: values clipped by a specified display transform or output boundary.

For every count, include the threshold, channel/plane, denominator and fraction. YUV luma/chroma and RGB channel counts use their own sample populations. Do not label an excursion as hard digital clipping.

## Color metadata conflicts

Keep camera-sidecar acquisition claims and container/bitstream signaling in separate fields. If S-Log3/S-Gamut3.Cine is declared in a sidecar while stream tags signal BT.709, mark the resolution `conflict` or `unresolved` until bitstream inspection and a documented decode/reference test support a conclusion. A related monitoring LUT filename does not prove the LUT was applied.

## Timecode

Store source timecode values verbatim. Store calculated frame-offset timecodes separately, including frame rate and mapping method. A mismatch is a conflict, not an invitation to silently rewrite source metadata. Distinguish clip-relative frame index from embedded timecode labels.

## Evidence required for a verified report

- Original media and sidecar bytes, SHA-256 hashes and byte sizes.
- Raw ffprobe and MediaInfo outputs, including tool versions.
- Exact decoder command/options and decoded pixel format.
- Measurement script and dependency versions.
- Extracted frame identifiers and a CSV covering the claimed frame range.
- Explicit measurement domains, ranges, thresholds and denominators.
- Independent reference data for any color-transform validation claim.

A decoder success validates neither a camera transform nor colorimetric accuracy. `reference_validated` requires traceable independent reference vectors or measured chart data and a documented tolerance.
