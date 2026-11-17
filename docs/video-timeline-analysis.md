# Video timeline analysis

`yrgb_engine.timeline.iter_analyze_video_frames` consumes an iterable of
(timestamp, `PrecisionFrame`) pairs and yields one report at a time. It works
with frames decoded from video or numbered still-image sequences, so the same
temporal analysis path can be reused by either source.

Each report includes the frame index, timestamp, full per-frame analysis,
adjacent-frame RGB histogram distance, and an optional shot-change candidate.
The histogram distance is the mean total-variation distance across R, G and B
histograms, including underflow and overflow buckets. It ranges from 0 (same
distribution) to 1 (fully disjoint distributions).

## Important interpretation limits

- The module does not decode video, seek timestamps, or retain the whole clip.
- A caller supplies decoded frames and timestamps; the decoder remains
  responsible for accurate presentation timestamps and frame order.
- Shot-change output is a statistical candidate, not semantic scene detection.
  Fast lighting changes, flashes, dissolves, and motion can trigger it.
- The threshold is caller-selected and disabled by default; it must be tuned
  against representative footage.
- Histogram comparison operates in the current frame sample domain. It does
  not compare perceptual color difference and does not normalize unknown Log
  encodings into a common working space.
- Per-frame exposure interpretation remains governed by
  `analysis.py`: linear-light luminance requires explicit coefficients and an
  explicit linear-RGB declaration.
- Streaming retains only the previous analysis report, not all decoded frames.
  Consumers may persist reports externally if they need a full timeline table.

This is the first temporal foundation for later shot-boundary refinement,
exposure continuity reports, and color-consistency diagnostics.
