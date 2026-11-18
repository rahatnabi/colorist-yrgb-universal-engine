# Interactive scope engine foundation

The `yrgb_engine.scopes` module packages the existing frame-analysis primitives
into a UI-ready, JSON-compatible snapshot for still images and individual video
frames. It is a data contract for a future browser scope renderer, not a GUI.

## Build a snapshot

`build_scope_snapshot(frame, ScopeConfig(...))` returns:

- RGB histograms and RGB Parade rasters.
- An optional weighted waveform when explicit RGB coefficients are supplied.
- An optional Cb/Cr vectorscope point cloud when explicit luma coefficients
  are supplied.
- Source dimensions, sample-domain label, source encoding metadata, optional
  working-space and transform identifiers, and optional video frame timing.
- `to_payload()` for JSON-compatible lists and dictionaries.

## Important display contract

The value axis is labelled **Source sample value** and the scale kind is
`sample-domain`. This engine does not convert values to IRE, legal-range code
values, or display-referred percentages. The frontend must retain that label
unless a separately validated signal mapping is added.

Unknown transfer functions remain unknown. No camera Log profile is guessed,
no transform is applied, and no source samples are modified. Negative and
above-one values are retained and represented as histogram/raster underflow
and overflow where applicable.

## Video use

Call the builder for each decoded frame and pass its frame index and timestamp.
The payload is bounded by the configured raster dimensions and vectorscope
point cap. A playback application can update the scope view as frames arrive;
this module itself does not decode media, schedule playback, or retain a
timeline buffer.

## Not yet implemented

- Browser/React scope panels and interactive zoom/pan.
- GPU/WebGL density rendering and vectorscope persistence.
- Calibrated IRE/legal-range axes and selectable signal standards.
- Temporal waveform/parade accumulation and playback synchronization.
- Performance benchmarking on Apple Silicon and large-resolution footage.

Those features require separate implementation and validation; the payload
here deliberately avoids pretending they already exist.
