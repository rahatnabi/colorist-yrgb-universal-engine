"""FastAPI service boundary for the COLORIST YRGB media engine.

The API exposes probing and registry discovery first. It deliberately does not
claim that preview decodes or unverified camera profiles are grading-ready.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from dataclasses import asdict

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .analysis import analyze_frame
from .capabilities import capabilities_as_dict
from .probe import probe_media
from .registry import ProfileRegistry

MAX_UPLOAD_BYTES = 512 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def create_app(*, registry: ProfileRegistry | None = None) -> FastAPI:
    """Create an API instance; registry injection keeps tests deterministic."""
    app = FastAPI(
        title="COLORIST YRGB Universal Color Engine",
        version="0.1.0",
        description=(
            "Media probing and camera-profile discovery API. "
            "Unknown transforms are never selected automatically."
        ),
    )
    profile_registry = registry or ProfileRegistry.load()
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("YRGB_CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "colorist-yrgb-engine"}

    @app.get("/v1/capabilities")
    async def get_capabilities() -> dict[str, Any]:
        return {
            "capabilities": capabilities_as_dict(),
            "note": "Availability does not guarantee complete codec or camera support.",
        }

    @app.get("/v1/profiles")
    async def list_profiles() -> dict[str, Any]:
        profiles = profile_registry.list_profiles()
        return {"count": len(profiles), "profiles": profiles}

    @app.get("/v1/profiles/candidates")
    async def profile_candidates(
        manufacturer: str = Query(min_length=1, max_length=80),
        encoding: str | None = Query(default=None, max_length=120),
        gamut: str | None = Query(default=None, max_length=120),
        camera_model: str | None = Query(default=None, max_length=120),
    ) -> dict[str, Any]:
        candidates = profile_registry.find_candidates(
            manufacturer=manufacturer,
            encoding=encoding,
            gamut=gamut,
            camera_model=camera_model,
        )
        return {
            "count": len(candidates),
            "selection_made": False,
            "candidates": candidates,
            "note": "Choose the exact camera model, encoding and gamut; no transform is inferred.",
        }

    @app.post("/v1/media/probe")
    async def media_probe(file: UploadFile = File(...)) -> dict[str, Any]:
        """Probe one bounded upload; temporary bytes are removed after inspection."""
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.",
                        )
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            result = await run_in_threadpool(probe_media, temporary_path)
            payload = result.to_dict() if hasattr(result, "to_dict") else result.__dict__
            return {"filename": filename, "size_bytes": total, "probe": payload}
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @app.post("/v1/media/analyze")
    async def media_analyze(file: UploadFile = File(...)) -> dict[str, Any]:
        """Decode a still through OpenImageIO and return sample-domain scopes.

        No camera transform, transfer-function assumption, IRE mapping, or
        exposure interpretation is applied by this endpoint.
        """
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-analysis-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.",
                        )
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float

            try:
                frame = await run_in_threadpool(decode_oiio_float, temporary_path)
            except HighPrecisionDecodeError as exc:
                if "required. Install" in str(exc):
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded image exceeds 40 megapixel analysis limit.")
            if not all(name.upper() in {c.upper() for c in frame.channel_names} for name in ("R", "G", "B")):
                raise HTTPException(status_code=422, detail="Decoded image does not expose named R, G and B channels.")

            result = await run_in_threadpool(
                analyze_frame,
                frame,
                histogram_bins=128,
                scope_width=128,
                scope_height=96,
                value_range=(0.0, 1.0),
            )
            return {
                "filename": filename,
                "decoder": frame.decoder,
                "width": frame.width,
                "height": frame.height,
                "sample_domain": frame.sample_domain,
                "encoding": asdict(frame.encoding),
                "analysis": {
                    "channels": {key: asdict(value) for key, value in result.channels.items()},
                    "histograms": {key: asdict(value) for key, value in result.histograms.items()},
                    "rgb_parade": {key: asdict(value) for key, value in result.rgb_parade.items()},
                    "waveform": None,
                    "luminance": None,
                    "vectorscope_points": None,
                    "note": "Code-value analysis only. No IRE, luminance, vectorscope or camera transform is inferred.",
                },
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @app.post("/v1/media/video-frame")
    async def media_video_frame(
        file: UploadFile = File(...),
        timestamp_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
    ) -> dict[str, Any]:
        """Decode and analyze one video frame at an explicit timestamp.

        The decoder preserves source transfer/primaries metadata and does not
        apply a camera input transform or infer display-referred measurements.
        """
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-video-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            from .oiio_decoder import HighPrecisionDecodeError
            from .video_precision import decode_video_float_frame

            try:
                frame = await run_in_threadpool(
                    decode_video_float_frame, temporary_path, timestamp_seconds=timestamp_seconds
                )
            except HighPrecisionDecodeError as exc:
                if "required" in str(exc).lower() or "install ffmpeg" in str(exc).lower():
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            result = await run_in_threadpool(
                analyze_frame, frame, histogram_bins=128, scope_width=128,
                scope_height=96, value_range=(0.0, 1.0),
            )
            return {
                "filename": filename, "timestamp_seconds": timestamp_seconds,
                "decoder": frame.decoder, "width": frame.width, "height": frame.height,
                "sample_domain": frame.sample_domain, "encoding": asdict(frame.encoding),
                "metadata": frame.metadata,
                "analysis": {
                    "channels": {key: asdict(value) for key, value in result.channels.items()},
                    "histograms": {key: asdict(value) for key, value in result.histograms.items()},
                    "rgb_parade": {key: asdict(value) for key, value in result.rgb_parade.items()},
                    "waveform": None, "luminance": None, "vectorscope_points": None,
                    "note": "Source sample-domain analysis only; no camera transform, IRE or luminance interpretation is inferred.",
                },
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @app.post("/v1/media/video-sample")
    async def media_video_sample(
        file: UploadFile = File(...),
        start_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
        interval_seconds: float = Query(default=1.0, gt=0.0, le=60.0),
        frame_count: int = Query(default=8, ge=1, le=24),
        shot_change_threshold: float | None = Query(default=0.35, ge=0.0, le=1.0),
    ) -> dict[str, Any]:
        """Analyze a bounded set of evenly spaced video frames.

        Shot-change flags are histogram-distance candidates, not semantic cuts.
        Frames are decoded sequentially and are not retained after analysis.
        """
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-sample-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            from .oiio_decoder import HighPrecisionDecodeError
            from .video_precision import decode_video_float_frame
            from .timeline import iter_analyze_video_frames

            def analyze_sample() -> list[dict[str, Any]]:
                def decoded_frames():
                    for index in range(frame_count):
                        timestamp = start_seconds + index * interval_seconds
                        frame = decode_video_float_frame(temporary_path, timestamp_seconds=timestamp)
                        yield timestamp, frame

                reports = iter_analyze_video_frames(
                    decoded_frames(),
                    shot_change_threshold=shot_change_threshold,
                    analysis_options={
                        "histogram_bins": 128,
                        "scope_width": 128,
                        "scope_height": 96,
                        "value_range": (0.0, 1.0),
                    },
                )
                output = []
                for report in reports:
                    output.append({
                        "timestamp_seconds": report.timestamp_seconds,
                        "frame_index": report.frame_index,
                        "histogram_distance": report.histogram_distance,
                        "channel_mean_delta": report.channel_mean_delta,
                        "mean_luminance_delta": report.mean_luminance_delta,
                        "shot_change_candidate": report.shot_change_candidate,
                        "channels": {key: asdict(value) for key, value in report.analysis.channels.items()},
                    })
                return output

            try:
                frames = await run_in_threadpool(analyze_sample)
            except HighPrecisionDecodeError as exc:
                if "required" in str(exc).lower() or "install ffmpeg" in str(exc).lower():
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            return {
                "filename": filename,
                "decoder": "FFmpeg/gbrpf32le",
                "frame_count": len(frames),
                "start_seconds": start_seconds,
                "interval_seconds": interval_seconds,
                "shot_change_threshold": shot_change_threshold,
                "sample_domain": "source sample-domain; no input transform applied",
                "frames": frames,
                "note": "Histogram distance is a distribution-change candidate, not a semantic cut detector. Channel mean deltas are sample-domain values, not exposure stops.",
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    return app


app = create_app()
