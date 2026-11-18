"""FastAPI service boundary for the COLORIST YRGB media engine.

The API exposes probing and registry discovery first. It deliberately does not
claim that preview decodes or unverified camera profiles are grading-ready.
"""
from __future__ import annotations

import json
import hashlib
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
from .capture_matching import match_capture_profile
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
        expose_headers=[
            "X-YRGB-Camera-Transform-Validated",
            "X-YRGB-Native-Grade",
            "X-YRGB-Preview-Only",
            "X-YRGB-Working-Space",
            "X-YRGB-Export-Scope",
            "X-YRGB-Sample-Format",
            "X-YRGB-Sample-Domain",
            "X-YRGB-Transform-ID",
            "X-YRGB-Frame-Width",
            "X-YRGB-Frame-Height",
            "X-YRGB-Float-Samples-SHA256",
            "X-YRGB-Clamped",
            "X-YRGB-Roundtrip-Verified",
            "X-YRGB-Roundtrip-Max-Absolute-Error",
            "X-YRGB-Roundtrip-RMSE",
            "X-YRGB-Roundtrip-Sample-Count",
            "X-YRGB-Roundtrip-SHA256-Matches",
            "X-YRGB-Delivery-QC-Status",
            "X-YRGB-Correction-Accuracy-Score",
            "X-YRGB-Delivery-QC-Report",
        ],
    )

    @app.get("/v1/learning/curriculum")
    async def learning_curriculum() -> dict[str, Any]:
        """Return the beginner-to-advanced still-image grading curriculum."""
        from .learning import curriculum_payload
        return curriculum_payload()

    @app.get("/v1/learning/exercises")
    async def learning_exercises(
        level: str | None = Query(default=None, pattern="^(beginner|intermediate|advanced)$"),
    ) -> dict[str, Any]:
        """List available still-image learning exercises."""
        from .learning import list_exercises
        return {"count": len(list_exercises(level=level)), "exercises": list_exercises(level=level)}

    @app.get("/v1/learning/lessons/{lesson_id}")
    async def learning_lesson(lesson_id: str) -> dict[str, Any]:
        """Fetch one still-image lesson by stable identifier."""
        from .learning import get_lesson
        lesson = get_lesson(lesson_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="Learning lesson not found.")
        return lesson

    @app.get("/v1/learning/exercises/{exercise_id}")
    async def learning_exercise(exercise_id: str) -> dict[str, Any]:
        """Fetch one still-image exercise by stable identifier."""
        from .learning import get_exercise
        exercise = get_exercise(exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="Learning exercise not found.")
        return exercise

    @app.get("/v1/learning/assets/neutral-practice-chart.png")
    async def learning_practice_chart() -> Response:
        """Download a synthetic practice still, explicitly not a measured reference."""
        from .practice_assets import neutral_practice_chart_png
        return Response(
            content=neutral_practice_chart_png(),
            media_type="image/png",
            headers={
                "Content-Disposition": 'attachment; filename="yrgb-neutral-practice-chart.png"',
                "X-YRGB-Asset-Status": "synthetic-instructional-sample",
            },
        )

    @app.post("/v1/learning/lessons/{lesson_id}/complete")
    async def complete_learning_lesson(
        lesson_id: str,
        learner_id: str = Form(min_length=8, max_length=80),
    ) -> dict[str, Any]:
        from .learning import get_lesson
        from .learning_store import complete_lesson
        if get_lesson(lesson_id) is None:
            raise HTTPException(status_code=404, detail="Learning lesson not found.")
        return complete_lesson(learner_id=learner_id, lesson_id=lesson_id)

    @app.get("/v1/learning/progress")
    async def learning_progress(
        learner_id: str = Query(min_length=8, max_length=80),
    ) -> dict[str, Any]:
        from .learning_store import get_progress
        return get_progress(learner_id)

    @app.post("/v1/learning/submissions")
    async def submit_learning_exercise(
        exercise_id: str = Form(min_length=1, max_length=80),
        learner_id: str = Form(min_length=8, max_length=80),
        evidence: str = Form(min_length=10, max_length=12000),
        file: UploadFile | None = File(default=None),
        profile_id: str | None = Form(default=None, max_length=160),
        roi_x: int | None = Form(default=None, ge=0),
        roi_y: int | None = Form(default=None, ge=0),
        roi_width: int | None = Form(default=None, ge=1),
        roi_height: int | None = Form(default=None, ge=1),
    ) -> dict[str, Any]:
        """Persist a still-image exercise submission without inventing scores."""
        from .learning import get_exercise
        from .learning_store import save_submission
        exercise = get_exercise(exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="Learning exercise not found.")
        roi_values = (roi_x, roi_y, roi_width, roi_height)
        if any(value is not None for value in roi_values) and any(value is None for value in roi_values):
            raise HTTPException(status_code=422, detail="Provide all four ROI values together.")
        if file is None and exercise["kind"] != "knowledge":
            raise HTTPException(status_code=422, detail="Attach a still image for this practical exercise.")
        image_bytes = None
        filename = None
        if file is not None:
            filename = file.filename or "submission-image"
            suffix = Path(filename).suffix.casefold()
            allowed_suffixes = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".dng", ".dpx", ".webp"}
            if not (file.content_type or "").startswith("image/") and suffix not in allowed_suffixes:
                raise HTTPException(status_code=415, detail="Submission must be a supported still-image file.")
            image_bytes = await file.read(100 * 1024 * 1024 + 1)
            if not image_bytes or len(image_bytes) > 100 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Still-image submission must be between 1 byte and 100 MiB.")
        assessment_status = "submitted"
        if exercise["assessment_mode"] == "correction_accuracy":
            profile = profile_registry.get_by_id(profile_id) if profile_id else None
            profile_validated = bool(profile and profile.get("usable_for_transform"))
            reference_validated = exercise["reference_asset_status"] == "measured_reference"
            roi_provided = all(value is not None for value in roi_values)
            assessment_status = (
                "eligible_for_native_assessment"
                if profile_validated and reference_validated and roi_provided and image_bytes is not None
                else "not_scored_reference_or_measurement_validation_missing"
            )
        elif exercise["assessment_mode"] == "creative_look_similarity":
            assessment_status = "awaiting_creative_reference_review"
        stored = save_submission(
            learner_id=learner_id,
            exercise_id=exercise_id,
            evidence={"text": evidence.strip(), "profile_id": profile_id, "roi": {
                "x": roi_x, "y": roi_y, "width": roi_width, "height": roi_height,
            } if roi_x is not None else None},
            image_bytes=image_bytes,
            image_filename=filename,
            assessment_status=assessment_status,
        )
        return {
            "submission": stored,
            "assessment": {
                "status": assessment_status,
                "correction_accuracy_score": None,
                "note": (
                    "No objective score was issued. A measured exercise reference, validated camera transform, "
                    "and verified native measurement are required."
                    if assessment_status == "not_scored_reference_or_measurement_validation_missing"
                    else "Submission saved. Creative comparison is a separate review track."
                    if assessment_status == "awaiting_creative_reference_review"
                    else "Submission saved for this exercise."
                ),
            },
        }

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


    @app.post("/v1/profiles/match-capture")
    async def match_capture(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Match explicitly reported capture metadata without guessing missing gamut."""
        try:
            return match_capture_profile(payload, profile_registry)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/transforms/validate-reference")
    async def validate_transform_reference(
        manifest_file: UploadFile = File(...),
        tolerance: float = Query(default=1e-5, gt=0, le=0.01),
    ) -> dict[str, Any]:
        """Validate one camera candidate against uploaded traceable measured vectors.

        A passing report is audit evidence only: it never edits or promotes the
        bundled camera registry. Production approval remains an explicit review.
        """
        from .reference_data import ReferenceManifestError, validate_reference_manifest

        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        if not config_value or not Path(config_value).is_file():
            await manifest_file.close()
            raise HTTPException(
                status_code=503,
                detail="A pinned server-managed YRGB_OCIO_CONFIG file is required for transform validation.",
            )

        filename = Path(manifest_file.filename or "reference.json").name
        if Path(filename).suffix.lower() != ".json":
            await manifest_file.close()
            raise HTTPException(status_code=415, detail="Upload a JSON reference-vector manifest.")
        temporary_path: str | None = None
        try:
            raw = await manifest_file.read(1_048_577)
            if len(raw) > 1_048_576:
                raise HTTPException(status_code=413, detail="Reference manifest exceeds the 1 MiB limit.")
            if not raw:
                raise HTTPException(status_code=400, detail="Reference manifest is empty.")
            with tempfile.NamedTemporaryFile(prefix="yrgb-reference-", suffix=".json", delete=False) as temp:
                temporary_path = temp.name
                temp.write(raw)
            try:
                result = await run_in_threadpool(
                    validate_reference_manifest,
                    temporary_path,
                    config_path=config_value,
                    registry=profile_registry,
                    tolerance=tolerance,
                )
            except ReferenceManifestError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            return {
                **result.to_registry_record(),
                "promotion_status": "not_promoted",
                "next_step": (
                    "Passing reference evidence must be reviewed and explicitly added to the "
                    "camera registry; this endpoint never changes profile status."
                ),
            }
        finally:
            await manifest_file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @app.get("/v1/ocio/status")
    async def ocio_config_status() -> dict[str, Any]:
        """Report exact OCIO config availability without applying any transforms."""
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        if not config_value:
            return {
                "configured": False,
                "status": "not_configured",
                "note": "Set YRGB_OCIO_CONFIG to a server-managed pinned OCIO config file.",
            }
        config_path = Path(config_value)
        if not config_path.is_file():
            return {
                "configured": False,
                "status": "config_file_missing",
                "note": "Configured OCIO file is not readable on this server.",
            }
        try:
            import PyOpenColorIO as ocio
            config = ocio.Config.CreateFromFile(str(config_path))
            names = set(config.getColorSpaceNames())
            version = str(ocio.GetVersion())
        except ImportError:
            return {
                "configured": False,
                "status": "ocio_dependency_missing",
                "note": "Install the ocio optional dependency on the API server.",
            }
        except Exception as exc:
            return {
                "configured": False,
                "status": "invalid_config",
                "note": f"OCIO config could not be loaded: {exc}",
            }

        mapped_profiles = []
        for profile in profile_registry.list_profiles():
            source = profile.get("ocio_source_space")
            destination = profile.get("ocio_destination_space")
            if source or destination:
                mapped_profiles.append({
                    "profile_id": profile["id"],
                    "source_space": source,
                    "source_available": source in names if isinstance(source, str) else False,
                    "destination_space": destination,
                    "destination_available": destination in names if isinstance(destination, str) else False,
                    "reference_validated": bool(
                        profile_registry.get_by_id(profile["id"]).get("usable_for_transform")
                    ),
                })
        preview_space = os.getenv("YRGB_PREVIEW_SPACE", "").strip()
        return {
            "configured": True,
            "status": "ready" if preview_space and preview_space in names else "config_loaded_preview_space_unavailable",
            "config_name": config_path.name,
            "config_sha256": __import__("hashlib").sha256(config_path.read_bytes()).hexdigest(),
            "ocio_version": version,
            "color_space_count": len(names),
            "preview_space": preview_space or None,
            "preview_space_available": preview_space in names if preview_space else False,
            "mapped_profiles": mapped_profiles,
            "note": "Config name availability does not certify camera transform accuracy; reference validation remains a separate gate.",
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
    async def media_analyze(
        file: UploadFile = File(...),
        scope_standard: str | None = Query(default=None, pattern="^(bt709|bt2020)$"),
    ) -> dict[str, Any]:
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

            from .scope_profiles import get_scope_coefficients
            coefficients = get_scope_coefficients(scope_standard) if scope_standard else None
            result = await run_in_threadpool(
                analyze_frame,
                frame,
                histogram_bins=128,
                scope_width=128,
                scope_height=96,
                value_range=(0.0, 1.0),
                waveform_coefficients=coefficients,
                vectorscope_coefficients=coefficients,
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
                    "waveform": asdict(result.waveform) if result.waveform else None,
                    "luminance": None,
                    "vectorscope_points": [list(point) for point in result.vectorscope_points] if result.vectorscope_points else None,
                    "scope_standard": scope_standard,
                    "scope_note": (
                        f"Waveform and vectorscope use manually selected {scope_standard.upper()} coefficients "
                        "on decoded sample-domain RGB; this does not validate the source color encoding."
                        if scope_standard else
                        "Select BT.709 or BT.2020 explicitly to calculate luma-based waveform and vectorscope."
                    ),
                    "note": "Source sample-domain analysis only; no IRE, linear-light luminance or camera transform is inferred.",
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
        scope_standard: str | None = Query(default=None, pattern="^(bt709|bt2020)$"),
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

            from .scope_profiles import get_scope_coefficients
            coefficients = get_scope_coefficients(scope_standard) if scope_standard else None
            result = await run_in_threadpool(
                analyze_frame, frame, histogram_bins=128, scope_width=128,
                scope_height=96, value_range=(0.0, 1.0),
                waveform_coefficients=coefficients,
                vectorscope_coefficients=coefficients,
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
                    "waveform": asdict(result.waveform) if result.waveform else None,
                    "luminance": None,
                    "vectorscope_points": [list(point) for point in result.vectorscope_points] if result.vectorscope_points else None,
                    "scope_standard": scope_standard,
                    "scope_note": (
                        f"Waveform and vectorscope use manually selected {scope_standard.upper()} coefficients "
                        "on decoded sample-domain RGB; this does not validate the source color encoding."
                        if scope_standard else
                        "Select BT.709 or BT.2020 explicitly to calculate luma-based waveform and vectorscope."
                    ),
                    "note": "Source sample-domain analysis only; no camera transform, IRE or linear-light luminance is inferred.",
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

    @app.post("/v1/media/video-report")
    async def media_video_report(
        file: UploadFile = File(...),
        timestamp_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
        frame_index: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        """Build a domain-separated report for one sampled video frame."""
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-report-", suffix=suffix, delete=False) as temp:
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
            from .video_yuv import decode_video_yuv_frame
            from .media_report import build_single_frame_measurement_report

            try:
                yuv_frame = await run_in_threadpool(decode_video_yuv_frame, temporary_path, timestamp_seconds=timestamp_seconds)
                rgb_frame = await run_in_threadpool(decode_video_float_frame, temporary_path, timestamp_seconds=timestamp_seconds)
                yuv_report = await run_in_threadpool(yuv_frame.to_report)
            except HighPrecisionDecodeError as exc:
                message = str(exc)
                if "required" in message.lower() or "install ffmpeg" in message.lower() or "not found on path" in message.lower():
                    raise HTTPException(status_code=503, detail=message) from exc
                raise HTTPException(status_code=422, detail=message) from exc

            digest = await run_in_threadpool(lambda: hashlib.sha256(Path(temporary_path).read_bytes()).hexdigest())
            report = await run_in_threadpool(
                build_single_frame_measurement_report,
                asset_id=Path(filename).stem or filename,
                source_reference=filename,
                source_sha256=digest,
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
                yuv_measurement=yuv_report,
                rgb_frame=rgb_frame,
            )
            return {
                "filename": filename, "size_bytes": total, "source_sha256": digest,
                "frame_index": frame_index, "timestamp_seconds": timestamp_seconds,
                "dimensions": {"width": yuv_frame.width, "height": yuv_frame.height},
                "report": report,
                "notes": [
                    "SHA-256 identifies uploaded bytes; it does not authenticate camera origin.",
                    "YUV and RGB are separate decoder outputs, not colorimetric validation.",
                    "Linear-light RGB and camera transform validation are not claimed.",
                ],
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
    @app.post("/v1/media/video-temporal-report")
    async def media_video_temporal_report(
        file: UploadFile = File(...),
        start_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
        interval_seconds: float = Query(default=1.0, gt=0.0, le=60.0),
        frame_count: int = Query(default=8, ge=1, le=24),
    ) -> dict[str, Any]:
        """Measure domain-separated YUV and RGB statistics across bounded samples.

        Samples are sequentially decoded; this endpoint does not classify flicker,
        scene cuts, or camera exposure drift as a definitive result.
        """
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-temporal-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            if start_seconds + (frame_count - 1) * interval_seconds > 86400.0:
                raise HTTPException(status_code=422, detail="Requested sample timestamps exceed the 86400-second limit.")

            from .oiio_decoder import HighPrecisionDecodeError
            from .video_precision import decode_video_float_frame
            from .video_yuv import decode_video_yuv_frame

            samples: list[dict[str, Any]] = []
            previous: dict[str, float] | None = None
            max_step_delta: dict[str, float] = {}
            first_means: dict[str, float] | None = None
            last_means: dict[str, float] | None = None
            stream_signaling: dict[str, str] | None = None
            for sample_index in range(frame_count):
                timestamp = start_seconds + sample_index * interval_seconds
                try:
                    yuv_frame = await run_in_threadpool(decode_video_yuv_frame, temporary_path, timestamp_seconds=timestamp)
                    rgb_frame = await run_in_threadpool(decode_video_float_frame, temporary_path, timestamp_seconds=timestamp)
                    yuv = await run_in_threadpool(yuv_frame.to_report)
                except HighPrecisionDecodeError as exc:
                    message = str(exc)
                    if "required" in message.lower() or "install ffmpeg" in message.lower() or "not found on path" in message.lower():
                        raise HTTPException(status_code=503, detail=message) from exc
                    raise HTTPException(status_code=422, detail=message) from exc

                rgb = await run_in_threadpool(
                    analyze_frame, rgb_frame, histogram_bins=64, scope_width=64,
                    scope_height=48, value_range=(0.0, 1.0),
                )
                rgb_means = {name: stats.mean for name, stats in rgb.channels.items()}
                yuv_means = {name: stats["mean_code_value"] for name, stats in yuv["planes"].items()}
                combined = {f"rgb_{key}": value for key, value in rgb_means.items()}
                combined.update({f"yuv_{key}": value for key, value in yuv_means.items()})
                if first_means is None:
                    first_means = combined
                    stream_signaling = {
                        "range": yuv_frame.range_signaling, "matrix": yuv_frame.matrix_signaling,
                        "transfer": yuv_frame.transfer_signaling, "primaries": yuv_frame.primaries_signaling,
                    }
                if previous is not None:
                    for key, value in combined.items():
                        delta = value - previous[key]
                        max_step_delta[key] = max(max_step_delta.get(key, 0.0), abs(delta))
                previous = combined
                last_means = combined
                samples.append({
                    "sample_index": sample_index, "source_frame_index": None,
                    "timestamp_seconds": timestamp,
                    "dimensions": {"width": yuv_frame.width, "height": yuv_frame.height},
                    "yuv": yuv,
                    "nonlinear_rgb": {
                        "sample_domain": rgb_frame.sample_domain,
                        "channels": {name: asdict(stats) for name, stats in rgb.channels.items()},
                    },
                })

            digest = await run_in_threadpool(lambda: hashlib.sha256(Path(temporary_path).read_bytes()).hexdigest())
            drift = {key: last_means[key] - first_means[key] for key in first_means} if len(samples) > 1 else {}
            return {
                "filename": filename, "size_bytes": total, "source_sha256": digest,
                "sampling": {
                    "start_seconds": start_seconds, "interval_seconds": interval_seconds,
                    "sample_count": len(samples), "source_frame_indices": "unresolved; timestamps only",
                },
                "color_metadata": {
                    "stream_signaled": stream_signaling, "xml_declared": {},
                    "resolution_status": "unresolved",
                },
                "measurement_domains": {
                    "original_yuv_code_values": {
                        "status": "reported", "frames": [item["yuv"] for item in samples],
                    },
                    "nonlinear_rgb_code_values": {
                        "status": "reported", "frames": [item["nonlinear_rgb"] for item in samples],
                    },
                    "linear_light_rgb": {
                        "status": "unavailable",
                        "reason": "No validated per-pixel inverse-transfer transform was applied.",
                    },
                },
                "temporal_analysis": {
                    "status": "reported", "classification": "not_classified",
                    "first_to_last_mean_delta": drift,
                    "maximum_absolute_step_delta": max_step_delta,
                    "notes": [
                        "Deltas compare decoded sample means only; they are not exposure or flicker measurements.",
                        "No scene-cut classification or source timecode/frame-index mapping is performed.",
                        "YUV code values and decoder RGB values remain separate measurement domains.",
                    ],
                },
                "samples": samples,
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
    @app.post("/v1/media/video-roi-temporal-report")
    async def media_video_roi_temporal_report(
        file: UploadFile = File(...),
        start_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
        interval_seconds: float = Query(default=1 / 25, gt=0.0, le=1.0),
        frame_count: int = Query(default=48, ge=3, le=240),
        minimum_samples: int = Query(default=24, ge=3, le=240),
        roi_x: float = Query(default=0.25, ge=0.0, le=1.0),
        roi_y: float = Query(default=0.25, ge=0.0, le=1.0),
        roi_width: float = Query(default=0.5, gt=0.0, le=1.0),
        roi_height: float = Query(default=0.5, gt=0.0, le=1.0),
    ) -> dict[str, Any]:
        """Run bounded dense fixed-ROI RGB sampling and conservative temporal analysis.

        Frame indices in this report are sample ordinals, not source frame indices.
        The decoder RGB domain is preserved; no linearization or camera transform
        is applied, so exposure-stop metrics remain unavailable.
        """
        filename = Path(file.filename or "upload.bin").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-roi-temporal-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            if start_seconds + (frame_count - 1) * interval_seconds > 86400.0:
                raise HTTPException(status_code=422, detail="Requested sample timestamps exceed the 86400-second limit.")
            if roi_x + roi_width > 1.0 or roi_y + roi_height > 1.0:
                raise HTTPException(status_code=422, detail="ROI rectangle must remain inside normalized frame bounds.")

            from .dense_temporal import analyze_dense_roi_samples
            from .oiio_decoder import HighPrecisionDecodeError
            from .roi import measure_normalized_rgb_roi
            from .video_precision import decode_video_float_frame

            roi_id = f"normalized:{roi_x:.9f},{roi_y:.9f},{roi_width:.9f},{roi_height:.9f}"
            measured_samples: list[dict[str, Any]] = []
            sample_reports: list[dict[str, Any]] = []
            for sample_index in range(frame_count):
                timestamp = start_seconds + sample_index * interval_seconds
                try:
                    frame = await run_in_threadpool(
                        decode_video_float_frame, temporary_path, timestamp_seconds=timestamp
                    )
                    measurement = await run_in_threadpool(
                        measure_normalized_rgb_roi, frame,
                        x=roi_x, y=roi_y, width=roi_width, height=roi_height,
                    )
                except HighPrecisionDecodeError as exc:
                    message = str(exc)
                    if "required" in message.lower() or "install ffmpeg" in message.lower() or "not found on path" in message.lower():
                        raise HTTPException(status_code=503, detail=message) from exc
                    raise HTTPException(status_code=422, detail=message) from exc
                means = {name: measurement["channels"][name]["mean"] for name in ("R", "G", "B")}
                tile_means = []
                for tile_y in range(2):
                    for tile_x in range(2):
                        tile_measurement = await run_in_threadpool(
                            measure_normalized_rgb_roi, frame,
                            x=roi_x + roi_width * tile_x / 2,
                            y=roi_y + roi_height * tile_y / 2,
                            width=roi_width / 2,
                            height=roi_height / 2,
                        )
                        tile_means.append({
                            name: tile_measurement["channels"][name]["mean"]
                            for name in ("R", "G", "B")
                        })
                measured_samples.append({
                    "timestamp_seconds": timestamp,
                    "frame_index": sample_index,
                    "roi_id": roi_id,
                    "measurement_domain": measurement["measurement_domain"],
                    "reference_validated_transform": False,
                    "roi_mean": means,
                    "tile_means": tile_means,
                })
                sample_reports.append({
                    "sample_index": sample_index,
                    "source_frame_index": None,
                    "timestamp_seconds": timestamp,
                    "roi_measurement": measurement,
                })

            analysis = await run_in_threadpool(
                analyze_dense_roi_samples, measured_samples,
                expected_interval_seconds=interval_seconds,
                minimum_samples=minimum_samples,
            )
            digest = await run_in_threadpool(
                lambda: hashlib.sha256(Path(temporary_path).read_bytes()).hexdigest()
            )
            return {
                "filename": filename,
                "size_bytes": total,
                "source_sha256": digest,
                "sampling": {
                    "start_seconds": start_seconds,
                    "interval_seconds": interval_seconds,
                    "sample_count": len(sample_reports),
                    "minimum_samples_for_dense_analysis": minimum_samples,
                    "frame_index_semantics": "sample ordinal only; source frame index and timecode unresolved",
                },
                "roi": {
                    "x": roi_x, "y": roi_y, "width": roi_width, "height": roi_height,
                    "coordinate_space": "normalized", "identity": roi_id,
                },
                "measurement_domain": measured_samples[0]["measurement_domain"],
                "temporal_analysis": analysis,
                "samples": sample_reports,
                "limitations": [
                    "ROI is fixed in image coordinates and does not track a moving subject.",
                    "Two-by-two tile spectral coherence is supporting evidence only; no optical-flow motion compensation is performed.",
                    "Periodic spectral peaks and RGB mean-step boundaries are candidates, not confirmed flicker or scene cuts.",
                    "Exposure stops are unavailable because no reference-validated scene-linear transform is applied.",
                    "Source frame indices and timecode are not independently resolved from timestamps.",
                ],
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
        roi_x: float = Query(default=0.25, ge=0.0, le=1.0),
        roi_y: float = Query(default=0.25, ge=0.0, le=1.0),
        roi_width: float = Query(default=0.5, gt=0.0, le=1.0),
        roi_height: float = Query(default=0.5, gt=0.0, le=1.0),
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
            if roi_x + roi_width > 1.0 or roi_y + roi_height > 1.0:
                raise HTTPException(status_code=422, detail="ROI rectangle must remain inside normalized frame bounds.")

            def analyze_sample() -> dict[str, Any]:
                from .roi import measure_normalized_rgb_roi
                roi_measurements = []
                def decoded_frames():
                    for index in range(frame_count):
                        timestamp = start_seconds + index * interval_seconds
                        frame = decode_video_float_frame(temporary_path, timestamp_seconds=timestamp)
                        roi_measurements.append(measure_normalized_rgb_roi(
                            frame, x=roi_x, y=roi_y, width=roi_width, height=roi_height
                        ))
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
                        "roi_measurement": roi_measurements[report.frame_index],
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
                from .temporal_diagnostics import analyze_sampled_temporal_trends

                group_payload = [asdict(group) for group in groups]
                diagnostics = analyze_sampled_temporal_trends(output, group_payload)
                return {
                    "frames": output,
                    "shot_groups": group_payload,
                    "temporal_diagnostics": diagnostics,
                }

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
                "roi": {"x": roi_x, "y": roi_y, "width": roi_width, "height": roi_height, "coordinate_space": "normalized"},
                "sample_domain": "source sample-domain; no input transform applied",
                "frames": frames,
                "shot_groups": shot_groups,
                "temporal_diagnostics": sample_result["temporal_diagnostics"],
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
        camera_model: str | None = Form(default=None, max_length=120),
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
        required_models = profile.get("camera_models", [])
        if required_models and (
            not camera_model
            or not any(camera_model.casefold() == model.casefold() for model in required_models)
        ):
            raise HTTPException(
                status_code=422,
                detail="Select an exact supported camera model for this profile before previewing.",
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
                background=BackgroundTask(lambda cleanup_path=preview_path: Path(cleanup_path).unlink(missing_ok=True)),
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


    @app.post("/v1/media/native-measurements")
    async def media_native_measurements(
        file: UploadFile = File(...),
        profile_id: str = Form(..., min_length=1, max_length=160),
        roi_x: int = Form(..., ge=0),
        roi_y: int = Form(..., ge=0),
        roi_width: int = Form(..., gt=0),
        roi_height: int = Form(..., gt=0),
        camera_model: str | None = Form(default=None, max_length=120),
        exposure_stops: float = Form(default=0.0, ge=-8.0, le=8.0),
        contrast: float = Form(default=1.0, ge=0.0, le=3.0),
        pivot: float = Form(default=0.18, ge=0.001, le=1.0),
        saturation: float = Form(default=1.0, ge=0.0, le=3.0),
        temperature_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        tint_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        curve_midpoint: float = Form(default=0.5, ge=0.1, le=0.9),
        exposure_target_stops: float = Form(default=0.0, ge=-8.0, le=8.0),
        gray_reference: float = Form(default=0.18, gt=0.0, le=1.0),
        exposure_tolerance_stops: float = Form(default=0.15, ge=0.0, le=4.0),
        neutral_tolerance: float = Form(default=0.02, ge=0.0, le=1.0),
        white_balance_tolerance: float = Form(default=0.02, ge=0.0, le=1.0),
    ) -> dict[str, Any]:
        """Measure scopes and correction accuracy from the same native graded still."""
        from dataclasses import replace
        from .accuracy import AccuracyTarget, measure_correction_accuracy
        from .correction_report import build_correction_accuracy_report
        from .exposure import PixelRegion
        from .grading_pipeline import GradingPipelineError, process_validated_still
        from .look import LookSettings
        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
        from .scopes import ScopeConfig, build_scope_snapshot

        profile = profile_registry.get_by_id(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Selected camera profile is not in the registry.")
        if not profile.get("usable_for_transform"):
            raise HTTPException(status_code=409, detail="Selected camera profile is not reference-validated; native measurements are blocked.")
        required_models = profile.get("camera_models", [])
        if required_models and (
            not camera_model
            or not any(camera_model.casefold() == model.casefold() for model in required_models)
        ):
            raise HTTPException(status_code=422, detail="Select the exact supported camera model for this profile.")
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        preview_space = os.getenv("YRGB_PREVIEW_SPACE", "").strip()
        preview_transfer = os.getenv("YRGB_PREVIEW_TRANSFER", "").strip()
        preview_primaries = os.getenv("YRGB_PREVIEW_PRIMARIES", "").strip()
        working_space = str(profile.get("ocio_destination_space", ""))
        if not all((config_value, preview_space, preview_transfer, preview_primaries, working_space)):
            raise HTTPException(status_code=503, detail="Configure the pinned OCIO config and preview output settings on the server.")

        filename = Path(file.filename or "still.tif").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-measure-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded still image is empty.")
            try:
                frame = await run_in_threadpool(decode_oiio_float, temporary_path)
            except HighPrecisionDecodeError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded still exceeds the 40 megapixel limit.")
            if roi_x + roi_width > frame.width or roi_y + roi_height > frame.height:
                raise HTTPException(status_code=422, detail="Neutral ROI must lie entirely inside the decoded still.")
            if roi_width * roi_height < 16:
                raise HTTPException(status_code=422, detail="Neutral ROI must contain at least 16 pixels for a stable measurement.")

            frame = replace(
                frame,
                encoding=replace(frame.encoding, profile_id=profile_id),
                metadata={**frame.metadata, "yrgb_selected_camera_profile": profile_id},
            )
            coefficients = (
                (0.2722287, 0.6740818, 0.0536895)
                if "aces" in working_space.casefold()
                else (0.2126, 0.7152, 0.0722)
            )
            settings = LookSettings(
                exposure_stops=exposure_stops, contrast=contrast, pivot=pivot,
                saturation=saturation, temperature_shift=temperature_shift,
                tint_shift=tint_shift, luminance_coefficients=coefficients,
                master_curve=((0.0, 0.0), (0.5, curve_midpoint), (1.0, 1.0)),
            )
            try:
                result = await run_in_threadpool(
                    process_validated_still,
                    frame,
                    settings,
                    registry=profile_registry,
                    config_path=config_value,
                    working_space_id=working_space,
                    display_space_id=preview_space,
                    display_transfer=preview_transfer,
                    display_primaries=preview_primaries,
                )
                graded = result.graded_frame
                region = PixelRegion(roi_x, roi_y, roi_width, roi_height)
                accuracy_target = AccuracyTarget(
                    exposure_stops=exposure_target_stops,
                    exposure_tolerance_stops=exposure_tolerance_stops,
                    gray_reference=gray_reference,
                    neutral_tolerance=neutral_tolerance,
                    white_balance_tolerance=white_balance_tolerance,
                    luminance_coefficients=coefficients,
                )
                accuracy = await run_in_threadpool(
                    measure_correction_accuracy, graded, region, accuracy_target
                )
                report = build_correction_accuracy_report(accuracy, accuracy_target)
                scope_config = ScopeConfig(
                    value_range=(-0.25, 4.0),
                    histogram_bins=256,
                    raster_width=512,
                    raster_height=256,
                    waveform_coefficients=coefficients,
                    vectorscope_coefficients=coefficients,
                    clipping_thresholds=(0.0, 1.0),
                )
                scopes = await run_in_threadpool(
                    build_scope_snapshot, graded, scope_config
                )
            except GradingPipelineError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=422, detail=f"Native measurement failed: {exc}") from exc

            return {
                "filename": filename,
                "measurement_source": "same_validated_native_graded_float32_frame",
                "working_space_id": graded.encoding.working_space_id,
                "transform_id": graded.encoding.transform_id,
                "validated": graded.encoding.validated,
                "transfer": graded.encoding.transfer,
                "frame": {"width": graded.width, "height": graded.height, "sample_count": graded.width * graded.height},
                "roi": {"x": roi_x, "y": roi_y, "width": roi_width, "height": roi_height},
                "scope_axis": "linear working-space sample values; not IRE or nits",
                "scope_range": [-0.25, 4.0],
                "scopes": scopes.to_payload(),
                "correction_accuracy": report.to_dict(),
                "limitations": [
                    "The neutral ROI is learner-selected and must genuinely represent a neutral reference.",
                    "Scope values are linear working-space samples, not display-referred IRE or calibrated nits.",
                    "Clipping counts use explicit linear thresholds 0.0 and 1.0; values above 1.0 are retained as scene headroom.",
                    "No creative-look similarity score is calculated by this endpoint.",
                ],
            }
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)


    @app.post("/v1/media/native-grade-export")
    async def media_native_grade_export(
        file: UploadFile = File(...),
        profile_id: str = Form(..., min_length=1, max_length=160),
        export_format: str = Form(default="exr"),
        camera_model: str | None = Form(default=None, max_length=120),
        exposure_stops: float = Form(default=0.0, ge=-8.0, le=8.0),
        contrast: float = Form(default=1.0, ge=0.0, le=3.0),
        pivot: float = Form(default=0.18, ge=0.001, le=1.0),
        saturation: float = Form(default=1.0, ge=0.0, le=3.0),
        temperature_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        tint_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        curve_midpoint: float = Form(default=0.5, ge=0.1, le=0.9),
        roi_x: int | None = Form(default=None, ge=0),
        roi_y: int | None = Form(default=None, ge=0),
        roi_width: int | None = Form(default=None, ge=1),
        roi_height: int | None = Form(default=None, ge=1),
        exposure_target_stops: float = Form(default=0.0, ge=-8.0, le=8.0),
        gray_reference: float = Form(default=0.18, gt=0.0, le=4.0),
    ) -> FileResponse:
        """Export a validated float master and optionally assess its verified round-trip ROI."""
        from dataclasses import replace
        from .grading_pipeline import GradingPipelineError, process_validated_still
        from .look import LookSettings
        from .accuracy import AccuracyTarget, measure_correction_accuracy
        from .correction_report import build_correction_accuracy_report
        from .exposure import PixelRegion
        from .native_export import (
            NativeExportError, native_frame_sha256, save_native_float_image,
            verify_native_float_export,
        )
        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float

        normalized_format = export_format.casefold().lstrip(".")
        if normalized_format not in {"exr", "tif", "tiff"}:
            raise HTTPException(status_code=422, detail="Choose EXR or TIFF float32 export.")
        roi_values = (roi_x, roi_y, roi_width, roi_height)
        if any(value is not None for value in roi_values) and not all(value is not None for value in roi_values):
            raise HTTPException(status_code=422, detail="Delivery QC ROI requires x, y, width and height together.")
        extension = ".exr" if normalized_format == "exr" else ".tiff"
        media_type = "image/x-exr" if normalized_format == "exr" else "image/tiff"
        profile = profile_registry.get_by_id(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Selected camera profile is not in the registry.")
        if not profile.get("usable_for_transform"):
            raise HTTPException(status_code=409, detail="Selected camera profile is not reference-validated; native export is blocked.")
        required_models = profile.get("camera_models", [])
        if required_models and (
            not camera_model
            or not any(camera_model.casefold() == model.casefold() for model in required_models)
        ):
            raise HTTPException(status_code=422, detail="Select the exact supported camera model for this profile.")
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        working_space = str(profile.get("ocio_destination_space", ""))
        if not config_value or not working_space:
            raise HTTPException(status_code=503, detail="Configure the pinned YRGB OCIO config on the server.")

        filename = Path(file.filename or "still.tif").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        export_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-native-export-source-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded still image is empty.")
            try:
                frame = await run_in_threadpool(decode_oiio_float, temporary_path)
            except HighPrecisionDecodeError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded still exceeds the 40 megapixel limit.")
            frame = replace(
                frame,
                encoding=replace(frame.encoding, profile_id=profile_id),
                metadata={**frame.metadata, "yrgb_selected_camera_profile": profile_id},
            )
            coefficients = (
                (0.2722287, 0.6740818, 0.0536895)
                if "aces" in working_space.casefold()
                else (0.2126, 0.7152, 0.0722)
            )
            settings = LookSettings(
                exposure_stops=exposure_stops, contrast=contrast, pivot=pivot,
                saturation=saturation, temperature_shift=temperature_shift,
                tint_shift=tint_shift, luminance_coefficients=coefficients,
                master_curve=((0.0, 0.0), (0.5, curve_midpoint), (1.0, 1.0)),
            )
            try:
                result = await run_in_threadpool(
                    process_validated_still,
                    frame,
                    settings,
                    registry=profile_registry,
                    config_path=config_value,
                    working_space_id=working_space,
                    display_space_id=working_space,
                    display_transfer="Linear",
                    display_primaries=str(profile.get("output_primaries", "unknown")),
                )
                graded = result.graded_frame
                digest = native_frame_sha256(graded)
            except (GradingPipelineError, NativeExportError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Native full-resolution grading failed: {exc}") from exc

            with tempfile.NamedTemporaryFile(prefix="yrgb-native-master-", suffix=extension, delete=False) as output:
                export_path = output.name
            try:
                await run_in_threadpool(save_native_float_image, graded, export_path)
                roundtrip = await run_in_threadpool(verify_native_float_export, graded, export_path)
            except NativeExportError as exc:
                raise HTTPException(status_code=422, detail=f"Native export round-trip verification failed: {exc}") from exc
            delivery_report = None
            if all(value is not None for value in roi_values):
                assert roi_x is not None and roi_y is not None and roi_width is not None and roi_height is not None
                if roi_x + roi_width > graded.width or roi_y + roi_height > graded.height:
                    raise HTTPException(status_code=422, detail="Delivery QC ROI must be fully inside the exported still.")
                if roi_width * roi_height < 16:
                    raise HTTPException(status_code=422, detail="Delivery QC ROI must contain at least 16 pixels.")
                target = AccuracyTarget(
                    exposure_stops=exposure_target_stops,
                    gray_reference=gray_reference,
                    luminance_coefficients=coefficients,
                )
                region = PixelRegion(roi_x, roi_y, roi_width, roi_height)
                try:
                    exported_frame = await run_in_threadpool(decode_oiio_float, export_path)
                    if (
                        exported_frame.width != graded.width
                        or exported_frame.height != graded.height
                        or exported_frame.channel_names != graded.channel_names
                    ):
                        raise HTTPException(status_code=422, detail="Decoded export metadata does not match the graded source frame.")
                    # The round-trip verifier has already compared every sample.
                    # Only now carry the validated pipeline identity onto the decoded
                    # export so assessment is performed on the actual written file.
                    exported_frame = replace(
                        exported_frame,
                        encoding=graded.encoding,
                        sample_domain=graded.sample_domain,
                        purpose=graded.purpose,
                        metadata={**exported_frame.metadata, "yrgb_roundtrip_verified": True},
                    )
                    accuracy = await run_in_threadpool(measure_correction_accuracy, exported_frame, region, target)
                    delivery_report = build_correction_accuracy_report(accuracy, target)
                except HighPrecisionDecodeError as exc:
                    raise HTTPException(status_code=422, detail=f"Could not decode exported master for delivery QC: {exc}") from exc
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=f"Delivery QC measurement failed: {exc}") from exc
            response_headers = {
                "X-YRGB-Export-Scope": "full-resolution",
                "X-YRGB-Sample-Format": "float32",
                "X-YRGB-Sample-Domain": "validated-scene-linear",
                "X-YRGB-Working-Space": working_space,
                "X-YRGB-Transform-ID": str(graded.encoding.transform_id or ""),
                "X-YRGB-Frame-Width": str(graded.width),
                "X-YRGB-Frame-Height": str(graded.height),
                "X-YRGB-Float-Samples-SHA256": digest,
                "X-YRGB-Clamped": "false",
                "X-YRGB-Roundtrip-Verified": str(bool(roundtrip["verified"])).lower(),
                "X-YRGB-Roundtrip-Max-Absolute-Error": str(roundtrip["max_absolute_error"]),
                "X-YRGB-Roundtrip-RMSE": str(roundtrip["rmse"]),
                "X-YRGB-Roundtrip-Sample-Count": str(roundtrip["sample_count"]),
                "X-YRGB-Roundtrip-SHA256-Matches": str(bool(roundtrip["sample_sha256_matches"])).lower(),
                "X-YRGB-Delivery-QC-Status": "not_requested",
            }
            if delivery_report is not None:
                report_payload = asdict(delivery_report)
                response_headers["X-YRGB-Delivery-QC-Status"] = delivery_report.status
                response_headers["X-YRGB-Correction-Accuracy-Score"] = (
                    "" if delivery_report.score is None else str(delivery_report.score)
                )
                response_headers["X-YRGB-Delivery-QC-Report"] = __import__("base64").urlsafe_b64encode(
                    json.dumps(report_payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
                ).decode("ascii")
            response = FileResponse(
                export_path,
                media_type=media_type,
                filename=f"{Path(filename).stem}_YRGB_master{extension}",
                headers=response_headers,
                background=BackgroundTask(lambda cleanup_path=export_path: Path(cleanup_path).unlink(missing_ok=True)),
            )
            export_path = None
            return response
        except HTTPException:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
            if export_path:
                Path(export_path).unlink(missing_ok=True)


    @app.post("/v1/media/native-grade-preview")
    async def media_native_grade_preview(
        file: UploadFile = File(...),
        profile_id: str = Form(..., min_length=1, max_length=160),
        camera_model: str | None = Form(default=None, max_length=120),
        exposure_stops: float = Form(default=0.0, ge=-8.0, le=8.0),
        contrast: float = Form(default=1.0, ge=0.0, le=3.0),
        pivot: float = Form(default=0.18, ge=0.001, le=1.0),
        saturation: float = Form(default=1.0, ge=0.0, le=3.0),
        temperature_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        tint_shift: float = Form(default=0.0, ge=-1.0, le=1.0),
        curve_midpoint: float = Form(default=0.5, ge=0.1, le=0.9),
    ) -> FileResponse:
        """Grade one still in native float32 after a reference-validated input transform.

        The returned PNG is a display preview, not a full-resolution float master.
        """
        from dataclasses import replace
        from .grading_pipeline import GradingPipelineError, process_validated_still
        from .look import LookSettings
        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
        from .preview import PreviewRenderError, save_preview_png

        profile = profile_registry.get_by_id(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Selected camera profile is not in the registry.")
        if not profile.get("usable_for_transform"):
            raise HTTPException(status_code=409, detail="Selected camera profile is not reference-validated; native grading is blocked.")
        required_models = profile.get("camera_models", [])
        if required_models and (
            not camera_model
            or not any(camera_model.casefold() == model.casefold() for model in required_models)
        ):
            raise HTTPException(status_code=422, detail="Select the exact supported camera model for this profile.")
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        preview_space = os.getenv("YRGB_PREVIEW_SPACE", "").strip()
        preview_transfer = os.getenv("YRGB_PREVIEW_TRANSFER", "").strip()
        preview_primaries = os.getenv("YRGB_PREVIEW_PRIMARIES", "").strip()
        working_space = str(profile.get("ocio_destination_space", ""))
        if not all((config_value, preview_space, preview_transfer, preview_primaries, working_space)):
            raise HTTPException(status_code=503, detail="Configure the pinned OCIO config and preview output settings on the server.")

        filename = Path(file.filename or "still.tif").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        preview_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-native-grade-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded still image is empty.")
            try:
                frame = await run_in_threadpool(decode_oiio_float, temporary_path)
            except HighPrecisionDecodeError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded still exceeds the 40 megapixel limit.")
            frame = replace(
                frame,
                encoding=replace(frame.encoding, profile_id=profile_id),
                metadata={**frame.metadata, "yrgb_selected_camera_profile": profile_id},
            )
            try:
                coefficients = (
                    (0.2722287, 0.6740818, 0.0536895)
                    if "aces" in working_space.casefold()
                    else (0.2126, 0.7152, 0.0722)
                )
                grade = LookSettings(
                    exposure_stops=exposure_stops, contrast=contrast, pivot=pivot,
                    saturation=saturation, temperature_shift=temperature_shift,
                    tint_shift=tint_shift, luminance_coefficients=coefficients,
                    master_curve=((0.0, 0.0), (0.5, curve_midpoint), (1.0, 1.0)),
                )
                result = await run_in_threadpool(
                    process_validated_still,
                    frame,
                    grade,
                    registry=profile_registry,
                    config_path=config_value,
                    working_space_id=working_space,
                    display_space_id=preview_space,
                    display_transfer=preview_transfer,
                    display_primaries=preview_primaries,
                )
                display_frame = result.display_preview_frame
            except GradingPipelineError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Native still grading failed: {exc}") from exc

            with tempfile.NamedTemporaryFile(prefix="yrgb-native-preview-", suffix=".png", delete=False) as output:
                preview_path = output.name
            await run_in_threadpool(
                save_preview_png, display_frame, preview_path,
                display_space_id=preview_space, output_transfer=preview_transfer,
            )
            response = FileResponse(
                preview_path, media_type="image/png",
                filename=f"{Path(filename).stem}_yrgb_native_grade_preview.png",
                headers={
                    "X-YRGB-Camera-Transform-Validated": "true",
                    "X-YRGB-Native-Grade": "float32-linear",
                    "X-YRGB-Preview-Only": "true",
                    "X-YRGB-Working-Space": working_space,
                },
                background=BackgroundTask(lambda cleanup_path=preview_path: Path(cleanup_path).unlink(missing_ok=True)),
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


    @app.post("/v1/media/video-transform-preview")
    async def media_video_transform_preview(
        file: UploadFile = File(...),
        profile_id: str = Form(..., min_length=1, max_length=160),
        camera_model: str | None = Form(default=None, max_length=120),
        timestamp_seconds: float = Query(default=0.0, ge=0.0, le=86400.0),
    ) -> FileResponse:
        """Render one video frame through the same reference-gated preview path."""
        from dataclasses import replace
        from .video_precision import decode_video_float_frame
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
        required_models = profile.get("camera_models", [])
        if required_models and (
            not camera_model
            or not any(camera_model.casefold() == model.casefold() for model in required_models)
        ):
            raise HTTPException(
                status_code=422,
                detail="Select an exact supported camera model for this profile before previewing.",
            )
        config_value = os.getenv("YRGB_OCIO_CONFIG", "").strip()
        preview_space = os.getenv("YRGB_PREVIEW_SPACE", "").strip()
        preview_transfer = os.getenv("YRGB_PREVIEW_TRANSFER", "").strip()
        preview_primaries = os.getenv("YRGB_PREVIEW_PRIMARIES", "").strip()
        if not all((config_value, preview_space, preview_transfer, preview_primaries)):
            raise HTTPException(
                status_code=503,
                detail="Configure the YRGB OCIO and preview-space environment variables on the server.",
            )

        filename = Path(file.filename or "upload.mov").name
        suffix = Path(filename).suffix[:16]
        temporary_path: str | None = None
        preview_path: str | None = None
        total = 0
        try:
            with tempfile.NamedTemporaryFile(prefix="yrgb-video-transform-", suffix=suffix, delete=False) as temp:
                temporary_path = temp.name
                while chunk := await file.read(CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Upload exceeds the 512 MiB limit.")
                    temp.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="Uploaded video is empty.")
            try:
                frame = await run_in_threadpool(
                    decode_video_float_frame,
                    temporary_path,
                    timestamp_seconds=timestamp_seconds,
                )
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Video frame decode failed: {exc}") from exc
            if frame.width * frame.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Decoded video frame exceeds 40 megapixel preview limit.")
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
                        "yrgb_preview_timestamp_seconds": timestamp_seconds,
                    },
                )
            except TransformValidationError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"OCIO preview transform failed: {exc}") from exc
            with tempfile.NamedTemporaryFile(prefix="yrgb-video-preview-", suffix=".png", delete=False) as output:
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
                filename=f"{Path(filename).stem}_{timestamp_seconds:.3f}s_yrgb_preview.png",
                headers={
                    "X-YRGB-Camera-Profile": profile_id,
                    "X-YRGB-Camera-Transform-Validated": "true",
                    "X-YRGB-Preview-Only": "true",
                    "X-YRGB-Display-Transform-Validated": "false",
                    "X-YRGB-Working-Space": str(profile["ocio_destination_space"]),
                    "X-YRGB-Frame-Timestamp": str(timestamp_seconds),
                },
                background=BackgroundTask(
                    lambda cleanup_path=preview_path: Path(cleanup_path).unlink(missing_ok=True)
                ),
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

    @app.post("/v1/media/batch-analyze")
    async def media_batch_analyze(
        files: list[UploadFile] = File(...),
        scope_standard: str | None = Query(default=None, pattern="^(bt709|bt2020)$"),
    ) -> dict[str, Any]:
        """Analyze a bounded still-image sequence and compare sample-domain channel means."""
        if not 1 <= len(files) <= 24:
            raise HTTPException(status_code=422, detail="Batch must contain between 1 and 24 images.")

        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
        from .scope_profiles import get_scope_coefficients

        coefficients = get_scope_coefficients(scope_standard) if scope_standard else None
        temporary_paths: list[str] = []
        reports: list[dict[str, Any]] = []
        try:
            for index, upload in enumerate(files):
                filename = Path(upload.filename or f"image-{index + 1}.bin").name
                suffix = Path(filename).suffix[:16]
                total = 0
                with tempfile.NamedTemporaryFile(prefix="yrgb-batch-", suffix=suffix, delete=False) as temp:
                    temporary_paths.append(temp.name)
                    while chunk := await upload.read(CHUNK_BYTES):
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=f"{filename} exceeds the 512 MiB per-image limit.",
                            )
                        temp.write(chunk)
                if total == 0:
                    raise HTTPException(status_code=400, detail=f"{filename} is empty.")
                try:
                    frame = await run_in_threadpool(decode_oiio_float, temporary_paths[-1])
                    if frame.width * frame.height > 40_000_000:
                        raise HTTPException(status_code=413, detail=f"{filename} exceeds 40 megapixels.")
                    if not all(name.upper() in {c.upper() for c in frame.channel_names} for name in ("R", "G", "B")):
                        raise HTTPException(status_code=422, detail=f"{filename} does not expose named RGB channels.")
                    result = await run_in_threadpool(
                        analyze_frame, frame, histogram_bins=128, scope_width=128, scope_height=96,
                        value_range=(0.0, 1.0), waveform_coefficients=coefficients,
                        vectorscope_coefficients=coefficients,
                    )
                except HighPrecisionDecodeError as exc:
                    raise HTTPException(status_code=422, detail=f"{filename}: {exc}") from exc
                reports.append({
                    "index": index,
                    "filename": filename,
                    "width": frame.width,
                    "height": frame.height,
                    "decoder": frame.decoder,
                    "sample_domain": frame.sample_domain,
                    "channels": {key: asdict(value) for key, value in result.channels.items()},
                    "scope_standard": scope_standard,
                })

            comparisons = []
            for previous, current in zip(reports, reports[1:]):
                comparisons.append({
                    "from_index": previous["index"],
                    "to_index": current["index"],
                    "channel_mean_delta": {
                        channel: current["channels"][channel]["mean"] - previous["channels"][channel]["mean"]
                        for channel in ("R", "G", "B")
                    },
                    "measurement_domain": "decoded_sample_domain_not_linear_light",
                })
            return {
                "image_count": len(reports),
                "images": reports,
                "adjacent_comparisons": comparisons,
                "scope_standard": scope_standard,
                "comparison_note": (
                    "Adjacent channel-mean differences are descriptive decoded sample-domain comparisons. "
                    "They are not exposure stops, luminance differences, or proof of shot matching."
                ),
            }
        finally:
            for upload in files:
                await upload.close()
            for temporary_path in temporary_paths:
                Path(temporary_path).unlink(missing_ok=True)


    @app.post("/v1/media/align-compare")
    async def media_align_compare(
        reference: UploadFile = File(...),
        candidate: UploadFile = File(...),
    ) -> dict[str, Any]:
        """Register a candidate still image to a reference and compare overlap RGB samples."""
        from .oiio_decoder import HighPrecisionDecodeError, decode_oiio_float
        from .shot_comparison import ShotAlignmentError, align_and_compare

        temporary_paths: list[str] = []
        uploads = (reference, candidate)
        try:
            decoded = []
            for upload in uploads:
                filename = Path(upload.filename or "image.bin").name
                suffix = Path(filename).suffix[:16]
                total = 0
                with tempfile.NamedTemporaryFile(prefix="yrgb-align-", suffix=suffix, delete=False) as temp:
                    temporary_paths.append(temp.name)
                    while chunk := await upload.read(CHUNK_BYTES):
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=f"{filename} exceeds the 512 MiB per-image limit.",
                            )
                        temp.write(chunk)
                if total == 0:
                    raise HTTPException(status_code=400, detail=f"{filename} is empty.")
                try:
                    frame = await run_in_threadpool(decode_oiio_float, temporary_paths[-1])
                except HighPrecisionDecodeError as exc:
                    raise HTTPException(status_code=422, detail=f"{filename}: {exc}") from exc
                if frame.width * frame.height > 12_000_000:
                    raise HTTPException(status_code=413, detail=f"{filename} exceeds the 12 megapixel alignment limit.")
                decoded.append(frame)

            try:
                result = await run_in_threadpool(align_and_compare, decoded[0], decoded[1])
            except ShotAlignmentError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            result["reference_filename"] = Path(reference.filename or "reference").name
            result["candidate_filename"] = Path(candidate.filename or "candidate").name
            return result
        finally:
            for upload in uploads:
                await upload.close()
            for temporary_path in temporary_paths:
                Path(temporary_path).unlink(missing_ok=True)

    return app


app = create_app()
