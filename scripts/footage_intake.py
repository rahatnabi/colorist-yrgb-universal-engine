"""Non-destructive media and sidecar intake with conservative metadata reconciliation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from yrgb_engine.metadata_reconcile import reconcile_color_metadata


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_xml_sidecar(path: Path, *, max_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    size = path.stat().st_size
    if size > max_bytes:
        return {"status": "rejected_size_limit", "size_bytes": size, "max_bytes": max_bytes, "values": {}}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"status": "parse_error", "error": str(exc), "values": {}}
    values: dict[str, list[str]] = {}
    for element in root.iter():
        key = element.tag.rsplit("}", 1)[-1]
        if len(element) == 0 and element.text and element.text.strip():
            values.setdefault(key, []).append(element.text.strip())
        for attr, value in element.attrib.items():
            values.setdefault(f"{key}@{attr}", []).append(value)
    return {"status": "parsed", "root_element": root.tag.rsplit("}", 1)[-1], "values": values}


def _sidecar_clip_stem(path: Path) -> str:
    """Normalize common Sony sidecar suffixes such as C1382M01.XML."""
    return re.sub(r"M[0-9]{2}$", "", path.stem, flags=re.IGNORECASE)


def _stream_color_declarations(probe: dict[str, Any]) -> dict[str, Any]:
    metadata = probe.get("metadata") or {}
    capture = metadata.get("capture_metadata") or {}
    streams = metadata.get("stream_summary") or []
    stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    return {
        "color_transfer": capture.get("color_transfer", stream.get("color_transfer")),
        "color_primaries": capture.get("color_primaries", stream.get("color_primaries")),
        "color_space": capture.get("color_matrix", stream.get("color_space")),
    }


def _attach_sidecar_reconciliation(files: list[dict[str, Any]]) -> None:
    sidecars = [
        item for item in files
        if Path(item.get("filename", "")).suffix.lower() == ".xml"
        and item.get("sidecar", {}).get("status") == "parsed"
    ]
    video_extensions = {".mp4", ".mov", ".mxf", ".mkv", ".avi"}
    for media in files:
        if Path(media.get("filename", "")).suffix.lower() not in video_extensions:
            continue
        probe = media.get("probe")
        if not isinstance(probe, dict):
            continue
        stem = Path(media["filename"]).stem
        candidates = [item for item in sidecars if _sidecar_clip_stem(Path(item["filename"])) == stem]
        if len(candidates) != 1:
            media["sidecar_reconciliation"] = {
                "status": "unresolved",
                "candidate_sidecars": [item["filename"] for item in candidates],
                "reason": "No unique XML sidecar matched this media filename.",
            }
            continue
        sidecar = candidates[0]
        comparison = reconcile_color_metadata(
            sidecar["sidecar"]["values"], _stream_color_declarations(probe)
        )
        media["sidecar_reconciliation"] = {
            "status": comparison["resolution_status"],
            "sidecar_filename": sidecar["filename"],
            "comparison": comparison,
        }


def inspect_file(path: Path, *, run_probe: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return {"filename": path.name, "status": "not_found"}
    stat = path.stat()
    record: dict[str, Any] = {
        "filename": path.name, "path": str(path.resolve()),
        "size_bytes": stat.st_size, "sha256": sha256_file(path),
        "status": "bytes_acquired",
    }
    if path.suffix.lower() == ".xml":
        record["sidecar"] = parse_xml_sidecar(path)
    elif run_probe:
        try:
            from yrgb_engine.probe import probe_media
            result = probe_media(path)
            record["probe"] = result.to_dict()
            record["status"] = "probed" if result.status == "probed" else result.status
        except ImportError as exc:
            record["probe_error"] = f"YRGB engine is not installed: {exc}"
            record["status"] = "probe_unavailable"
        except Exception as exc:
            record["probe_error"] = f"{type(exc).__name__}: {exc}"
            record["status"] = "probe_error"
    return record


def build_report(paths: list[Path], *, run_probe: bool = True) -> dict[str, Any]:
    files = [inspect_file(path, run_probe=run_probe) for path in paths]
    _attach_sidecar_reconciliation(files)
    return {
        "schema_version": 1,
        "report_type": "yrgb-footage-intake",
        "source_files_modified": False,
        "files": files,
        "summary": {
            "file_count": len(files),
            "bytes_acquired_count": sum(item.get("status") != "not_found" for item in files),
            "probe_error_count": sum(item.get("status") in {"probe_error", "probe_unavailable", "probe_failed", "probe_timeout"} for item in files),
            "xml_parse_error_count": sum(item.get("sidecar", {}).get("status") == "parse_error" for item in files),
            "xml_size_rejected_count": sum(item.get("sidecar", {}).get("status") == "rejected_size_limit" for item in files),
            "metadata_conflict_count": sum(item.get("sidecar_reconciliation", {}).get("status") == "conflict" for item in files),
            "metadata_unresolved_count": sum(item.get("sidecar_reconciliation", {}).get("status") == "unresolved" for item in files),
        },
        "limitations": [
            "Container metadata is not proof of a camera Log/gamut profile.",
            "XML leaf values are preserved as vendor metadata; field meanings are not guessed.",
            "A successful probe or decode does not validate a color transform.",
            "Sidecar matching uses the clip basename and common Sony M## suffix; ambiguous matches remain unresolved.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash and inspect footage/sidecars without modifying originals.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON report to this path; stdout if omitted.")
    parser.add_argument("--skip-probe", action="store_true", help="Hash files and parse XML without ffprobe.")
    args = parser.parse_args()
    report = build_report(args.files, run_probe=not args.skip_probe)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if all(item.get("status") != "not_found" for item in report["files"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
