# Initial HTTP API

The first service boundary exposes capability discovery, camera-profile candidate
discovery, and bounded temporary media probing.

## Run locally

Install the optional API dependencies and start the development server:

```bash
python -m pip install -e ".[dev,api]"
uvicorn yrgb_engine.api:app --reload
```

OpenAPI documentation is available at `/docs` while the server is running.

## Endpoints

- `GET /health` — process health.
- `GET /v1/capabilities` — installed optional decoder/color dependencies.
- `GET /v1/profiles` — profile catalog, including verification status.
- `GET /v1/profiles/candidates` — candidates filtered by manufacturer,
  encoding, gamut and camera model. This endpoint never chooses a transform.
- `POST /v1/media/probe` — upload a media file for conservative signature and
  metadata probing. The upload is limited to 512 MiB and removed after probing.
- `POST /v1/media/analyze` — decode a still image with the optional OpenImageIO
  adapter and return RGB channel statistics, a 128-bin histogram and RGB parade
  raster. Uploads are limited to 512 MiB; decoded frames are limited to 40 MP.
  Measurements remain in the decoder's sample domain; no camera transform, IRE,
  luminance, waveform or vectorscope interpretation is inferred. Install the
  `high-precision` extra to enable this endpoint.
- `POST /v1/media/video-frame?timestamp_seconds=2.5` — decode one frame from a
  video at the requested timestamp using FFmpeg and return the same channel
  statistics, histogram and RGB parade data. Timestamp must be between 0 and
  86,400 seconds. Uploads are limited to 512 MiB and decoded frames to 40 MP.
  Install FFmpeg and NumPy. Source transfer, primaries, matrix and range metadata
  are retained; no Log-to-working-space transform, IRE scale or calibrated
  luminance interpretation is applied. This is single-frame analysis, not yet a
  real-time playback or temporal-scope stream.

## Important boundaries

Media probing is not high-precision decoding. It does not transform camera Log,
create a proxy, or make a camera profile usable. Capability availability is not
proof of complete format support. Production deployment still needs authentication,
rate limiting, storage policy, request-size limits at the reverse proxy, and
isolated media workers with CPU/time limits.


## Browser development CORS

The API allows `http://localhost:5173` by default for local Vite development. Set `YRGB_CORS_ORIGINS` to a comma-separated allowlist of exact trusted origins when deploying the API. Credentials are disabled. Do not use a wildcard origin in a production deployment.


## Bounded temporal video sampling

`POST /v1/media/video-sample?start_seconds=0&interval_seconds=1&frame_count=8`
decodes evenly spaced frames sequentially and returns per-frame channel means,
adjacent-frame histogram distance, and statistical shot-change candidates.
Frame count is limited to 1–24; interval must be greater than 0 and at most
60 seconds; start time is limited to 0–86,400 seconds. The optional
`shot_change_threshold` is in the 0–1 range and defaults to 0.35.

This is bounded sampling, not real-time playback or a full-frame-rate scan.
Histogram changes are candidates, not confirmed semantic cuts. Channel mean
deltas remain in the source sample domain and are not exposure-stop measurements.
The upload remains limited to 512 MiB and each decoded frame to 40 MP.


## LUT export

`POST /v1/lut/export?size=35&title=My%20Look` accepts an uploaded source
`.cube` file and returns a resampled 3D `.cube` download. Supported target
grid sizes are 17, 33, 35 and 65. The endpoint preserves the source LUT domain
and evaluates its existing 1D/3D/combined transform while resampling. Resampling
does not create new look detail beyond the source LUT. The .cube format does not
reliably carry a color-space contract, so users must keep track of the intended
input and output color spaces separately.


## Provisional shot grouping

The bounded `POST /v1/media/video-sample` response now includes `shot_groups`
and a `shot_index` on each sampled frame. A frame flagged as a histogram-change
candidate begins a new provisional group. Each group includes sampled start/end
indices and timestamps, sample count, and the boundary histogram distance.
These are not confirmed semantic shots; flashes, camera movement, exposure
changes or lighting changes can also trigger a candidate.

The response also includes `consistency_status`. Exposure drift is unavailable
until frames have validated linear RGB and a user-selected ROI. Neutral-region
analysis likewise requires validated linear RGB. Mixed-camera comparison
requires validated frames in one common working space and explicit colorimetric
parameters. The current video sampler does not claim any of these prerequisites.


## Parametric look-to-LUT export

`POST /v1/look/export-cube` accepts JSON containing `size`, `title`,
`input_space_id`, `input_transfer` and a `settings` object. The first look
engine requires an explicitly declared `linear`, `linear-light` or
`scene-linear` input transfer. It supports exposure stops, contrast, pivot,
saturation, artistic temperature/tint RGB gains and a monotonic master curve.
The API returns a baked 3D .cube file at 17, 33, 35 or 65 points.

The engine's temperature/tint controls are artistic channel-gain offsets, not
Kelvin white balance. The default luma coefficients are Rec.709; callers using
another linear RGB set must supply appropriate coefficients. This endpoint
does not decode camera Log, validate a camera transform or create a display
output transform. Do not label a non-linear DaVinci Intermediate signal as
linear RGB.


## Scene-linear still look render

`POST /v1/media/look-linear-exr` accepts multipart form data:
`file`, `input_space_id`, `linear_input_confirmed=true`, and optional
`settings_json`. It decodes via OpenImageIO, applies the parametric look and
streams a float32 OpenEXR response. Values are not clamped; negative and
above-one headroom are retained.

This endpoint is deliberately restricted to source images the operator knows
are scene-linear RGB in the selected space. It rejects recognized non-linear
transfer metadata. Its output header explicitly reports
`X-YRGB-Transform-Validated: false`: operator confirmation is not independent
colorimetric validation. It does not convert camera Log, apply DWG/Intermediate
or generate Rec.709 output. Install the `high-precision` extra to enable it.


## Reference-gated still transform preview

`POST /v1/media/transform-preview` accepts a still-image upload and an explicit `profile_id` form field. It only runs when that exact registry profile has verified status, a matching independent reference-validation record, a pinned OCIO config hash, and explicit source/destination space metadata.

Server configuration:
- `YRGB_OCIO_CONFIG`: absolute path to the server-managed pinned OCIO config.
- `YRGB_PREVIEW_SPACE`: exact OCIO display/preview destination space name.
- `YRGB_PREVIEW_TRANSFER`: transfer declaration for the preview destination.
- `YRGB_PREVIEW_PRIMARIES`: primaries declaration for the preview destination.

The response is a PNG preview with headers identifying the selected camera profile, camera-transform validation status, and preview-only status. The display transform is explicitly **not** certified as a mastering/export transform. The current public camera catalogue contains unverified profiles, so those profiles correctly receive HTTP 409 until independent reference data is added and reviewed. The endpoint never infers a camera profile from a filename.


POST /v1/media/video-transform-preview?timestamp_seconds=... performs the same reference-gated camera-to-working-space preparation on one FFmpeg-decoded video frame, then renders a preview-only PNG. It uses the same explicit profile_id and server-managed OCIO/preview environment settings. The returned timestamp header identifies the sampled frame. This is not continuous playback or video delivery.
