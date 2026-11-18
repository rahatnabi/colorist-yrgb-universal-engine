# Native still-image grading pipeline

## Purpose

The native pipeline connects the existing float32 still-image decoder, camera
profile registry, validated OCIO input transform, linear-RGB look operations
and explicit display preview transform. It is a still-image pipeline; it does
not introduce video, timeline or temporal processing.

## Processing stages

1. **Decode** — decode_oiio_float() preserves float32 samples and reports
   source metadata without guessing the source color space.
2. **Identify** — the caller must attach an exact registered camera profile ID.
   Metadata matching is a candidate selection, not transform approval.
3. **Input transform** — prepare_frame_for_working_space() only applies a
   profile whose reference-vector evidence and pinned OCIO config hash match.
4. **Linear grading** — apply_look_to_frame() applies the shared look controls
   to validated scene-linear RGB in the exact selected working space.
5. **Display preview** — an explicit OCIO transform creates a display preview
   candidate. The candidate is marked unvalidated and preview-only.
6. **Mastering/export** — existing export guards remain in force. A preview
   candidate is not eligible for a certified still-image export.

## API for native callers

Use process_validated_still() from yrgb_engine.grading_pipeline. It returns
three distinct precision frames:

- working_frame: reference-validated camera-to-working-space output.
- graded_frame: the creative grade in that same validated linear space.
- display_preview_frame: explicitly transformed for display, but unvalidated
  and marked display_preview_only.

The display space, transfer and primaries are required arguments. The pipeline
does not assume Rec.709, sRGB, DWG or ACEScg when those values have not been
selected by the caller.

## Current limitations

- No camera profile becomes verified merely because the orchestration code
  exists. Sony S-Log3/S-Gamut3.Cine remains blocked until traceable measured
  reference vectors are supplied and independently pass validation.
- Browser preview processing is still separate from this native float32 path;
  this module establishes the native backend contract, not a completed browser
  integration or GPU renderer.
- Display preview conversion is not a mastering-output certification.
- The native path is CPU-based through OpenImageIO and OpenColorIO; performance
  profiling and tiled/streamed processing remain follow-up work.
