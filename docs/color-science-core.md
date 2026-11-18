# Color Science Core — Initial Contract

The color-science layer is deliberately separate from media decoding.

## OpenColorIO transforms

Install the optional dependency with:

```bash
python -m pip install -e ".[ocio]"
```

Call `yrgb_engine.ocio.transform_frame` with exact source and destination
space names. A config path may be supplied explicitly; otherwise the process's
current OCIO config is used. The function does not infer a camera profile,
choose a default transform, clamp values, or mutate the source frame.

The output is tagged with the destination space name, but its
`validated` flag remains false. A transform being executable is not proof
that it is the correct camera transform. Reference-chart and known-value tests
are still required before a profile can be promoted to verified.

## .cube LUT parsing

`yrgb_engine.cube.load_cube` reads a UTF-8 .cube file and validates:
- 1D and/or 3D LUT size declarations
- RGB triplet data and expected entry count
- finite values
- domain minimum/maximum

The parser retains LUT entries and metadata. `yrgb_engine.lut.apply_cube_rgb`
provides a CPU reference implementation with linear 1D interpolation and
trilinear 3D interpolation. Combined LUTs run the 1D stage before the 3D stage.
Intensity blends the original RGB input with the final LUT result. Input
coordinates are clamped to the declared domain; output values are not clamped.
This is a correctness-oriented CPU reference, not yet a GPU implementation.

## Current status

Implemented: explicit OCIO CPU transform adapter and strict .cube parser.

Not yet implemented or validated: bundled DWG/Intermediate-to-Rec.709 config,
verified manufacturer camera transforms, LUT interpolation/application,
LUT intensity/A-B controls, GPU acceleration, and reference-chart validation.


## Color matching diagnostics

`yrgb_engine.color_matching.analyze_color_region` measures a caller-selected ROI
in validated linear RGB and reports mean RGB, XYZ, CIE Lab, RGB chromaticity,
channel balance and luminance. The caller must supply the RGB-to-XYZ matrix and
XYZ reference white for the declared working space. The engine checks that the
matrix is finite, 3x3 and invertible; it cannot independently prove that the
matrix/white-point pair actually belongs to the named space.

`compare_color_regions` requires identical `working_space_id` values and
reports RGB/Lab deltas, CIE76 Delta E, separate exposure-stop delta, and channel
balance delta. A Delta E threshold is optional and caller-defined; no universal
pass/fail threshold is assumed. This is a mean-RGB-to-Lab diagnostic approximation,
not pixelwise Delta E averaging and not a replacement for a validated chart-based
camera characterization workflow.

Different `transform_id` values are allowed when the upstream transforms have
been independently validated to the same destination working space. The engine
does not select, apply, or validate camera transforms. Negative RGB is not
supported by this Lab diagnostic path and is rejected rather than silently clipped.

## Selected-region skin-tone workflow diagnostics

`yrgb_engine.skin_tone.analyze_selected_region` reports hue, saturation and
value statistics for an operator-selected ROI in an explicitly named signal
domain. It does not detect faces, classify skin, infer identity or demographics,
or impose a universal skin-tone hue target. Hue uses circular statistics, and
achromatic samples are excluded from hue summaries. This is descriptive grading
feedback, not a pass/fail judgment or automatic correction.

See [skin-tone-diagnostics.md](skin-tone-diagnostics.md) for the measurement
contract and limitations.

## Camera profile candidate discovery

`ProfileRegistry.find_candidates` returns possible profile variants without
choosing among them. If gamut is unspecified, each gamut variant remains a
separate candidate and the result declares a `gamut_choice` requirement.
Camera-model-restricted entries similarly declare a `camera_model` requirement.
Candidate discovery does not promote an unverified record to a usable transform;
exact resolution and verified transform status remain separate gates.

The initial catalogue is intentionally conservative. Candidate entries must be
expanded and verified against manufacturer documentation, reference transforms,
and known-value tests before they can be used in automatic input conversion.
