# LUT Export

The cube export module samples an explicit RGB transform into a portable 3D
`.cube` LUT. Supported grid sizes are 17, 33, 35 and 65.
A 35-point LUT contains 42,875 RGB entries; a 65-point LUT contains 274,625.
The export order is blue-fastest, then green, then red, matching the reader and
CPU reference sampler.

`generate_cube_text` accepts a callable RGB transform and explicit domain.
`resample_cube_text` converts an imported 1D, 3D or combined .cube LUT to a
3D LUT at the requested grid size. Resampling cannot recover detail absent
from the source LUT. Values are not clamped; display mapping belongs to the
explicit output transform.

A LUT is only portable when its input/output color-space contract is documented.
This exporter does not infer camera Log, gamut, working space or display output.
