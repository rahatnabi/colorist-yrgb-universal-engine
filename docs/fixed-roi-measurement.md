# Fixed ROI measurement

The ROI helper measures per-channel means over a normalized rectangle on a
decoded `PrecisionFrame`. Geometry is validated and returned in both
normalized coordinates and integer pixel bounds. The result includes the
sample count and preserves the decoder's declared sample-domain label.

This is a fixed image-coordinate ROI, not an object tracker. Camera motion or
subject movement can move content into or out of the rectangle. The values
remain decoder sample-domain RGB; this helper does not linearize pixels,
apply a camera transform, calculate exposure stops, or detect flicker.

The video sample endpoint exposes an optional normalized ROI rectangle. Its
default is a centered 50% x 50% rectangle. Per-frame ROI means can be compared
only as descriptive sample-domain values unless a separately validated
scene-linear transform and suitable reference evidence exist.
