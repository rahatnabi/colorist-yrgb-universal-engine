# COLORIST YRGB macOS Desktop

This is the Tauri 2 desktop shell for the existing React/Vite workspace.

## Development prerequisites

- macOS 13 or newer (Apple Silicon is the primary target)
- Xcode Command Line Tools
- Rust stable toolchain
- Node.js 20+
- Python 3.11+

Install the Rust target and JavaScript dependencies:

```bash
xcode-select --install
rustup update stable
cd web
npm install
```

Run the desktop shell:

```bash
npm run desktop:dev
```

Build a local macOS app and DMG:

```bash
npm run desktop:build
```

Tauri writes the app bundles beneath `web/src-tauri/target/release/bundle/`.

## Backend status

The current Tauri shell hosts the web interface. The Python API is still a separate local service during this first integration milestone:

```bash
# From the repository root, in another terminal
python -m pip install -e ".[api]"
uvicorn yrgb_engine.api:app --host 127.0.0.1 --port 8000
```

The production Python sidecar (including pinned OCIO configuration and optional OpenImageIO/RAW dependencies), automatic lifecycle management, signing and notarization are follow-up packaging milestones. A successful shell build must not be interpreted as a complete standalone grading-engine installer.

The desktop product scope is still-image grading and learning only.
