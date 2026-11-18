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
