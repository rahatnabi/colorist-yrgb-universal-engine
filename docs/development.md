# Development Setup

## Requirements

- Python 3.11 or newer
- Git
- FFmpeg/ffprobe for video metadata probing (optional for image-only development)
- macOS, Linux, and Windows are intended targets; platform-specific behavior must be tested.

## Create an environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,images]"
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run tests

```bash
pytest
```

## Probe a file

```bash
yrgb-probe "/path/to/your/clip.mov"
yrgb-probe "/path/to/your/still.dng"
```

For video, install FFmpeg so `ffprobe` is available on PATH. The current probe reports container/stream metadata only; it does not decode frames or apply a camera Log transform.

## Current limitations

- Image signature detection is intentionally conservative and does not fully validate/decode every image format.
- Pillow metadata is optional and does not replace a production RAW decoder.
- Video probing depends on the local FFmpeg build and enabled codecs.
- Camera Log/gamut identification is not inferred from filenames.
- LUT parsing, color transforms, grading, scopes, and export are later milestones.
