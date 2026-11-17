# Development Setup

## Requirements
- Python 3.11 or newer
- Git
- FFmpeg/ffprobe for video metadata probing and preview decoding (optional for image-only development)
- macOS, Linux, and Windows are intended targets; platform-specific behavior must be tested.

## Create an environment
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,images]"
```

Windows PowerShell activation:
```powershell
.venv\Scripts\Activate.ps1
```

## Run tests
```bash
pytest
```

## Inspect available tools
```bash
yrgb-probe capabilities
```
This reports discoverable optional tools. It does not mean all formats are supported.

## Probe a file
```bash
yrgb-probe probe "/path/to/your/clip.mov"
yrgb-probe probe "/path/to/your/still.dng"
```
The original shorthand yrgb-probe FILE remains available. Install FFmpeg so ffprobe and ffmpeg are on PATH.

## Current limitations
- Image signatures do not fully validate/decode every format.
- Pillow preview decoding is 8-bit RGB and is not a production RAW/high-bit-depth decoder.
- Video behavior depends on the local FFmpeg build and enabled codecs.
- Camera Log/gamut is not inferred from filenames.
- LUT parsing, color transforms, grading, scopes, and export are later milestones.
