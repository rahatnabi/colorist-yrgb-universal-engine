# Shot consistency intelligence

The first shot grouping layer segments a bounded sampled timeline whenever the
histogram-distance detector flags a candidate. Each group reports sampled start
and end frame indices/timestamps, sample count and the histogram distance that
triggered its provisional boundary. These are candidate groups, not confirmed
semantic shots; flashes, motion, exposure changes and lighting changes can also
trigger histogram differences.

Temporal exposure analysis is already available as a separate streaming core in
`temporal_exposure.py`. It requires explicitly validated linear RGB, a shared
working-space identity, caller-confirmed shot boundary indices and a user-selected
ROI. Camera-specific transform IDs may differ only when all frames have been
validated into the same destination working space.

Neutral-region candidate scanning is also available in the exposure core, but it
is heuristic and requires validated linear RGB. It cannot certify a gray card or
illumination. The current FFmpeg sample endpoint emits source sample-domain frames
without a validated camera transform, so it deliberately reports exposure drift
and neutral-region consistency as unavailable rather than inventing measurements.

Mixed-camera color comparison is available in `color_matching.py` for explicitly
validated linear frames in a common working space. It requires explicit RGB-to-XYZ
matrix and reference white; it does not select camera transforms.
