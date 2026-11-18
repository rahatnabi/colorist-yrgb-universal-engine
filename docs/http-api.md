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
