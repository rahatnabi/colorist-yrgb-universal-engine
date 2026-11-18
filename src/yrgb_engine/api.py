"""FastAPI service boundary for the COLORIST YRGB media engine.

The API exposes probing and registry discovery first. It deliberately does not
claim that preview decodes or unverified camera profiles are grading-ready.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

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

    return app


app = create_app()
