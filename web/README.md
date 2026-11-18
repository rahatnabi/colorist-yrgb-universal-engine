# COLORIST YRGB Web Workspace

Early React + Vite interface for the Universal Color Engine.

## Run

Terminal 1 — API:

```bash
python -m pip install -e ".[dev,api]"
uvicorn yrgb_engine.api:app --reload
```

Terminal 2 — web app:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Set `VITE_YRGB_API_URL` when the API is hosted elsewhere.

## Current capabilities

- Local browser preview for browser-decodable image/video files.
- Server-side metadata probe through `POST /v1/media/probe`.
- Camera profile candidate discovery without auto-selecting transforms.
- Responsive grading-workspace shell and scope panel placeholders.

## Not implemented yet

- Color-managed reference preview and browser-to-engine frame transfer.
- Decoding all advertised RAW/professional video formats in the browser.
- Live numerical scopes, grading controls, LUT application UI, timeline playback and export.
- Authentication, durable project storage and production deployment hardening.

The UI does not fabricate scope data or apply unverified input transforms.

Temporal video sampling: the Media Analysis workspace can sample 1–24 evenly spaced frames from a clip and report adjacent-frame histogram-change candidates. These are statistical candidates, not confirmed scene cuts.


### Reference-gated transform preview

The Camera Profile panel lets you select an exact registry candidate. For still images and a selected video timestamp, the preview action calls the reference-gated transform preview endpoint. Unverified profiles are deliberately blocked with an API conflict response; the UI never falls back to a guessed camera transform. The rendered PNG is a preview only, not a color-managed mastering reference or final delivery.


### Optional OCIO transform preview setup

Install the OCIO, image and high-precision extras on the API server:

```bash
python -m pip install -e ".[dev,api,ocio,images,high-precision]"
```

Download an explicitly versioned OCIO config from the official [OpenColorIO-Config-ACES v4.0.0 release](https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/tag/v4.0.0), then configure the API process with exact color-space names present in that config. For example, for a Rec.709 Gamma 2.4 preview, set `YRGB_PREVIEW_SPACE` to the config's exact `Gamma 2.4 Encoded Rec.709` color-space name, `YRGB_PREVIEW_TRANSFER` to `Gamma 2.4`, and `YRGB_PREVIEW_PRIMARIES` to `BT.709`.

```bash
export YRGB_OCIO_CONFIG="/absolute/path/to/pinned-config.ocio"
export YRGB_PREVIEW_SPACE="Gamma 2.4 Encoded Rec.709"
export YRGB_PREVIEW_TRANSFER="Gamma 2.4"
export YRGB_PREVIEW_PRIMARIES="BT.709"
```

Check `/v1/ocio/status` before previewing. A config containing a candidate color-space name does not independently validate that camera transform. All camera profiles remain blocked until their own reference evidence is attached and approved. The display conversion is preview-only, not a final mastering transform.
