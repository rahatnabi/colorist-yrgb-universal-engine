# Timecode Validation

The engine preserves embedded/source timecode labels verbatim and calculates expected labels independently from a clip-relative frame index.

## Supported arithmetic

- Non-drop-frame labels at positive integer or rational frame rates.
- SMPTE drop-frame labels at 30000/1001 and 60000/1001 fps.
- Explicit frame offsets, including negative offsets when the resulting frame count remains non-negative.
- 24-hour label wrap when formatting a frame count.

## Rules

- HH:MM:SS:FF denotes non-drop-frame timecode.
- HH:MM:SS;FF denotes drop-frame timecode.
- Drop-frame skips frame labels, not video frames. The implementation rejects labels skipped at the start of non-tenth minutes.
- Frame-rate interpretation is always explicit. Do not infer 25, 29.97, or 30 fps from a timecode string alone.
- Source labels and calculated labels must be stored separately. A mismatch should be recorded as a conflict in the media-analysis report; never silently rewrite source metadata.

## Example: 25 fps

For source start timecode 00:12:47:08, frame offset 48 calculates to 00:12:49:06. If an external report says 00:12:48:23, preserve that report as a conflicting source claim until the original media and its timecode mapping are independently inspected.
