# Still-image rendering

`apply_cube_to_frame` applies a parsed .cube LUT only when a frame carries a
validated working-space declaration that exactly matches the caller-supplied
LUT input-space ID. It preserves alpha and auxiliary channels. The resulting
frame is marked unvalidated because a .cube file does not prove its own color
space contract.

`save_frame_image` writes 8-bit JPEG, PNG or TIFF through the optional Pillow
dependency. It requires an explicit output-space ID and transfer-function
label, preserves alpha for PNG/TIFF, and rejects alpha for JPEG rather than
silently discarding it. Clamping to [0, 1] occurs only at this rendered-image
boundary; the float32 grading buffer remains unclamped.

RAW decoding remains an input-stage operation (rawpy/LibRaw or a compatible
OpenImageIO plugin). A RAW capture cannot be re-exported as the original sensor
RAW after demosaic, color transforms and grading. The rendered result must be
written as TIFF/PNG/JPEG/EXR. Camera-specific RAW-to-working-space transforms
must be explicitly selected and validated before applying a creative LUT.
