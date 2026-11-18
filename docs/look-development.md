# Look Development Engine

The parametric look core applies exposure (stops), contrast/pivot, saturation,
artistic temperature/tint RGB gains and a monotonic master curve. It is defined
for linear RGB values and requires explicit luma coefficients. It does not
perform camera decoding, input transforms, display rendering or output
transforms.

Temperature and tint are deliberately named artistic RGB gain offsets, not
Kelvin controls or a standards-based chromatic adaptation. The initial master
curve is piecewise-linear. No channel clipping occurs in the floating-point
look math.

`bake_3d_cube` samples the look into 17, 33, 35 or 65 point .cube grids in
blue-fastest ordering. The generated LUT includes comments naming its expected
linear RGB input-space ID; .cube consumers may ignore those comments, so the
color-space contract must also travel with delivery metadata.

This first version is a deterministic look/LUT engine, not yet a complete
interactive pixel preview or a validated camera-to-display pipeline. Camera
input transforms and Rec.709 output transforms must be explicitly selected and
validated separately before production use.
