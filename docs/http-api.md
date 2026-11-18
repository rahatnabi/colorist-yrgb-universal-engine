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

## Important boundaries

Media probing is not high-precision decoding. It does not transform camera Log,
create a proxy, or make a camera profile usable. Capability availability is not
proof of complete format support. Production deployment still needs authentication,
rate limiting, storage policy, request-size limits at the reverse proxy, and
isolated media workers with CPU/time limits.
