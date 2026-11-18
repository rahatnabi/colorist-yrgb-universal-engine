"""FastAPI service boundary for the COLORIST YRGB media engine.

The API exposes probing and registry discovery first. It deliberately does not
claim that preview decodes or unverified camera profiles are grading-ready.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from dataclasses import asdict

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask
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

            if start_seconds + (frame_count - 1) * interval_seconds > 86400.0:
                raise HTTPException(status_code=422, detail="Requested sample timestamps exceed the 86400-second limit.")

            def analyze_sample() -> dict[str, Any]:
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
                from .shot_consistency import ShotFrameSignal, group_sampled_shots

                signals = [
                    ShotFrameSignal(
                        frame_index=item["frame_index"],
                        timestamp_seconds=item["timestamp_seconds"],
                        histogram_distance=item["histogram_distance"],
                        change_candidate=item["shot_change_candidate"],
                    )
                    for item in output
                ]
                groups = group_sampled_shots(signals)
                for group in groups:
                    for item in output:
                        if group.start_frame_index <= item["frame_index"] <= group.end_frame_index:
                            item["shot_index"] = group.shot_index
                return {"frames": output, "shot_groups": [asdict(group) for group in groups]}

            try:
                sample_result = await run_in_threadpool(analyze_sample)
                frames = sample_result["frames"]
                shot_groups = sample_result["shot_groups"]
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
                "shot_groups": shot_groups,
                "consistency_status": {
                    "exposure_drift": "unavailable_without_validated_linear_rgb_and_user_roi",
                    "neutral_region": "unavailable_without_validated_linear_rgb",
                    "mixed_camera_color": "requires_validated_common_working_space_and_explicit_colorimetric_parameters",
                },
                "note": "Shot groups are provisional histogram-change groups, not confirmed semantic cuts. Histogram distance is a distribution-change candidate, not a semantic cut detector. Channel mean deltas are sample-domain values, not exposure stops.",
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @app.post("/v1/media/look-linear-exr")
    async def media_look_linear_exr(
        file: UploadFile = File(...),
        input_space_id: str = Form(..., min_length=1, max_length=120),
        linear_input_confirmed: bool = Form(default=False),
        settings_json: str = Form(default="{}"),
    ) -> Response:
        """Apply a creative look to an explicitly operator-declared linear still and export float EXR."""
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_input: str | None = None
        temporary_output: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-look-in-", suffix=suffix, delete=False) as temp:
                temporary_input = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded image is empty.")
            if not linear_input_confirmed:
                raise HTTPException(
                    status_code=422,
                    detail="Confirm that the source pixels are scene-linear RGB in the selected working space.",
                )
            from .look import (
                LookDevelopmentError,
                LookSettings,
                apply_look_to_declared_linear_frame,
            )
            from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
            from .linear_export import LinearExportError, save_linear_float_exr

            try:
                raw_settings = json.loads(settings_json)
                if not isinstance(raw_settings, dict):
                    raise ValueError("Look settings must be a JSON object.")
                allowed = {
                    "exposure_stops", "contrast", "pivot", "saturation",
                    "temperature_shift", "tint_shift", "luminance_coefficients",
                    "master_curve",
                }
                unknown = set(raw_settings) - allowed
                if unknown:
                    raise ValueError(f"Unknown look settings: {', '.join(sorted(unknown))}.")
                if "luminance_coefficients" in raw_settings:
                    raw_settings["luminance_coefficients"] = tuple(raw_settings["luminance_coefficients"])
                if "master_curve" in raw_settings:
                    raw_settings["master_curve"] = tuple(tuple(point) for point in raw_settings["master_curve"])
                settings = LookSettings(**raw_settings)
                frame = await run_in_threadpool(decode_oiio_float, temporary_input)
                if frame.width * frame.height > 40_000_000:
                    raise ValueError("Decoded image exceeds the 40-megapixel processing limit.")
                graded = await run_in_threadpool(
                    apply_look_to_declared_linear_frame,
                    frame,
                    settings,
                    input_space_id=input_space_id,
                    linear_input_confirmed=True,
                )
                with tempfile.NamedTemporaryFile(prefix="yrgb-look-out-", suffix=".exr", delete=False) as output:
                    temporary_output = output.name
                await run_in_threadpool(save_linear_float_exr, graded, temporary_output)
                safe_name = "".join(
                    char for char in Path(filename).stem if char.isalnum() or char in "-_ "
                ).strip().replace(" ", "_") or "YRGB_Graded"
                output_path = Path(temporary_output)
                response = FileResponse(
                    output_path,
                    media_type="image/x-exr",
                    filename=f"{safe_name}_graded_linear.exr",
                    headers={
                        "X-YRGB-Working-Space": input_space_id,
                        "X-YRGB-Transform-Validated": "false",
                        "X-YRGB-Output-Transfer": "scene-linear",
                    },
                    background=BackgroundTask(output_path.unlink, missing_ok=True),
                )
                temporary_output = None
                return response
            except HTTPException:
                raise
            except (HighPrecisionDecodeError, LinearExportError, LookDevelopmentError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_input:
                Path(temporary_input).unlink(missing_ok=True)
            if temporary_output:
                Path(temporary_output).unlink(missing_ok=True)

    @app.post("/v1/look/export-cube")
    async def export_parametric_look(payload: dict[str, Any] = Body(...)) -> Response:
        """Bake user-specified linear-RGB look controls into a 3D .cube LUT."""
        from .look import LookDevelopmentError, LookSettings, bake_3d_cube

        try:
            size = int(payload.get("size", 35))
            title = str(payload.get("title", "COLORIST YRGB Look"))
            input_space_id = str(payload.get("input_space_id", "")).strip()
            input_transfer = str(payload.get("input_transfer", "")).casefold()
            if input_transfer not in {"linear", "linear-light", "scene-linear"}:
                raise HTTPException(
                    status_code=422,
                    detail="Look LUT baking requires an explicitly declared linear RGB input transfer.",
                )
            raw_settings = payload.get("settings", {})
            if not isinstance(raw_settings, dict):
                raise HTTPException(status_code=422, detail="Settings must be a JSON object.")
            allowed = {
                "exposure_stops", "contrast", "pivot", "saturation",
                "temperature_shift", "tint_shift", "luminance_coefficients",
                "master_curve",
            }
            unknown = set(raw_settings) - allowed
            if unknown:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown look settings: {', '.join(sorted(unknown))}.",
                )
            if "luminance_coefficients" in raw_settings:
                raw_settings["luminance_coefficients"] = tuple(raw_settings["luminance_coefficients"])
            if "master_curve" in raw_settings:
                raw_settings["master_curve"] = tuple(
                    tuple(point) for point in raw_settings["master_curve"]
                )
            settings = LookSettings(**raw_settings)
            content = await run_in_threadpool(
                bake_3d_cube,
                settings,
                size=size,
                title=title,
                input_space_id=input_space_id,
            )
            safe_name = "".join(
                char for char in title if char.isalnum() or char in "-_ "
            ).strip().replace(" ", "_") or "YRGB_Look"
            return Response(
                content=content,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_name}_{size}pt.cube"',
                    "X-YRGB-Input-Space": input_space_id,
                    "X-YRGB-Input-Transfer": input_transfer,
                },
            )
        except HTTPException:
            raise
        except (LookDevelopmentError, TypeError, ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/lut/export")
    async def export_cube_lut(
        file: UploadFile = File(...),
        size: int = Query(default=33, ge=2, le=65),
        title: str = Query(default="COLORIST YRGB Look", min_length=1, max_length=120),
    ) -> Response:
        """Resample an uploaded .cube look into a standard 3D LUT grid."""
        filename = Path(file.filename or "look.cube").name
        try:
            if Path(filename).suffix.lower() != ".cube":
                raise HTTPException(status_code=415, detail="Upload a .cube LUT source file.")
            raw = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(raw) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="LUT upload exceeds the 512 MiB limit.")
            if not raw:
                raise HTTPException(status_code=400, detail="Uploaded LUT is empty.")
            from .cube import CubeLUTError, parse_cube_text
            from .cube_export import CubeExportError, SUPPORTED_3D_SIZES, resample_cube_text

            if size not in SUPPORTED_3D_SIZES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported LUT size. Choose one of {SUPPORTED_3D_SIZES}.",
                )
            try:
                source_lut = parse_cube_text(raw.decode("utf-8-sig"))
                exported = await run_in_threadpool(
                    resample_cube_text, source_lut, size=size, title=title
                )
            except (UnicodeDecodeError, CubeLUTError, CubeExportError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            safe_name = "".join(c for c in title if c.isalnum() or c in "-_ ").strip().replace(" ", "_") or "YRGB_Look"
            return Response(
                content=exported,
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{safe_name}_{size}pt.cube"'},
            )
        finally:
            await file.close()


    @app.post("/v1/media/transform-preview")
    async def media_transform_preview(
        file: UploadFile = File(...),
        profile_id: str = Form(..., min_length=1, max_length=160),
    ) -> FileResponse:
        """Prepare a still through an approved camera transform and render a preview.

        Camera profile selection is explicit. The camera transform must be
        reference-validated and the OCIO config is supplied by server settings.
        The display transform is preview-only, not a mastering/export approval.
        """
        from dataclasses import replace
        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
        from .ocio import transform_frame
        from .preview import PreviewRenderError, save_preview_png
        from .transform_validation import (
            TransformValidationError,
            prepare_frame_for_working_space,
        )

        profile = profile_registry.get_by_id(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Selected camera profile is not in the registry.")
        if not profile.get("usable_for_transform"):
            raise HTTPException(
                status_code=409,
                detail="Selected camera profile is not reference-validated; automatic conversion is blocked.",
            )
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        preview_space = os.getenv("YRGB_PREVIEW_SPACE", "").strip()
        preview_transfer = os.getenv("YRGB_PREVIEW_TRANSFER", "").strip()
        preview_primaries = os.getenv("YRGB_PREVIEW_PRIMARIES", "").strip()
        if not all((config_value, preview_space, preview_transfer, preview_primaries)):
            raise HTTPException(
                status_code=503,
                detail="Configure YRGB_OCIO_CONFIG, YRGB_PREVIEW_SPACE, YRGB_PREVIEW_TRANSFER and YRGB_PREVIEW_PRIMARIES on the server.",
            )

        filename = Path(file.filename or "upload.tif").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        preview_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-transform-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            try:
                frame = await run_in_threadpool(decode_oiio_float, temporary_path)
            except HighPrecisionDecodeError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded image exceeds 40 megapixel preview limit.")
            if not all(channel in {name.upper() for name in frame.channel_names} for channel in ("R", "G", "B")):
                raise HTTPException(status_code=422, detail="Decoded image must expose named R, G and B channels.")

            frame = replace(
                frame,
                encoding=replace(frame.encoding, profile_id=profile_id),
                metadata={**frame.metadata, "yrgb_selected_camera_profile": profile_id},
            )
            try:
                working_frame = await run_in_threadpool(
                    prepare_frame_for_working_space,
                    frame,
                    registry=profile_registry,
                    config_path=config_value,
                )
                display_frame = await run_in_threadpool(
                    transform_frame,
                    working_frame,
                    source_space=str(profile["ocio_destination_space"]),
                    destination_space=preview_space,
                    config_path=config_value,
                )
                display_frame = replace(
                    display_frame,
                    encoding=replace(
                        display_frame.encoding,
                        primaries=preview_primaries,
                        transfer=preview_transfer,
                        profile_id=preview_space,
                        working_space_id=preview_space,
                        transform_id=None,
                        validated=False,
                        metadata_source="preview-only OCIO display transform; not delivery validated",
                    ),
                    metadata={
                        **display_frame.metadata,
                        "yrgb_preview_only": True,
                        "yrgb_display_transform_validated": False,
                        "yrgb_camera_transform_id": profile["transform_id"],
                    },
                )
            except TransformValidationError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"OCIO preview transform failed: {exc}") from exc

            with tempfile.NamedTemporaryFile(prefix="yrgb-preview-", suffix=".png", delete=False) as output:
                preview_path = output.name
            await run_in_threadpool(
                save_preview_png,
                display_frame,
                preview_path,
                display_space_id=preview_space,
                output_transfer=preview_transfer,
            )
            response = FileResponse(
                preview_path,
                media_type="image/png",
                filename=f"{Path(filename).stem}_yrgb_preview.png",
                headers={
                    "X-YRGB-Camera-Profile": profile_id,
                    "X-YRGB-Camera-Transform-Validated": "true",
                    "X-YRGB-Preview-Only": "true",
                    "X-YRGB-Display-Transform-Validated": "false",
                    "X-YRGB-Working-Space": str(profile["ocio_destination_space"]),
                },
                background=BackgroundTask(lambda: Path(preview_path).unlink(missing_ok=True)),
            )
            preview_path = None
            return response
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError, PreviewRenderError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
            if preview_path:
                Path(preview_path).unlink(missing_ok=True)

    return app


app = create_app()
