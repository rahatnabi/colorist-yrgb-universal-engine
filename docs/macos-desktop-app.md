# COLORIST YRGB macOS Desktop App

## Architecture

- **Desktop shell:** Tauri 2 (Rust)
- **Interface:** existing React + TypeScript + Vite application
- **Grading and measurement:** existing Python engine and FastAPI service
- **Local learning persistence:** existing SQLite-backed learning store
- **Primary hardware target:** Apple Silicon, including MacBook Pro M3

The desktop app reuses the existing web interface rather than maintaining a second UI implementation.

## Milestone 1 — Desktop shell

The initial shell is located in `web/src-tauri/`. It provides a native macOS window and local `.app` / `.dmg` bundle configuration. Run `npm run desktop:dev` from `web/` for development, or `npm run desktop:build` to build locally.

At this milestone, the Python API is started separately on loopback at `127.0.0.1:8000`. The Tauri shell is not yet a self-contained installer.

## Milestone 2 — Python sidecar

Package the FastAPI engine as an Apple Silicon sidecar using a reproducible Python build environment. The sidecar must:
- bind only to loopback;
- use an application-owned data directory;
- pin and verify the OCIO config and required color-space names;
- include only tested image dependencies;
- start and stop with the desktop app;
- expose a health endpoint before the UI enables native processing.

Do not silently substitute an unverified transform or claim objective accuracy when the reference data is not validated.

## Milestone 3 — Release engineering

- Build and test on Apple Silicon macOS.
- Verify app permissions and local file access.
- Sign with a Developer ID certificate.
- Notarize and staple the release.
- Test installation on a clean macOS user account.

## Product scope

The desktop application is for still-image grading, analysis, learning, and still-image export. It does not add video-grading or video-timeline features.
