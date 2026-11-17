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
