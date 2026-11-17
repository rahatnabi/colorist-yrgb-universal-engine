# Development Setup

## Requirements
- Python 3.11 or newer
- Git
- FFmpeg/ffprobe for video metadata probing and preview decoding
- macOS, Linux, and Windows are intended targets; platform-specific behavior must be tested.

## Create an environment
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,images]"
```

For the optional OpenImageIO float32 image decoder and float32 video decoder:
```bash
python -m pip install -e ".[high-precision]"
```

For the optional LibRaw-backed RAW still decoder:
```bash
python -m pip install -e ".[raw]"
```
OpenImageIO and rawpy wheels/plugins vary by platform. Confirm installed format support with actual test assets. FFmpeg must include the `gbrpf32le` pixel format for the high-precision video adapter.

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

## Current limitations
- Pillow preview decoding is 8-bit RGB and is not a production RAW/high-bit-depth decoder.
- OpenImageIO and LibRaw adapters are initial decode paths; source colorimetry and numerical behavior require reference validation.
- The FFmpeg float32 adapter is a candidate path, not a verified scene-linear or DWG transform.
- Camera Log/gamut is never inferred from filenames.
- LUT parsing, color transforms, grading, scopes, and export remain later milestones.
