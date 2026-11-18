"""Create a non-destructive intake report for original media and sidecars.

This tool reads source files, computes SHA-256, and optionally invokes the existing
YRGB media probe. It never modifies or copies the supplied originals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def parse_xml_sidecar(path: Path, *, max_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    """Extract simple XML leaf values; do not interpret unknown vendor fields."""
    size = path.stat().st_size
    if size > max_bytes:
        return {"status": "rejected_size_limit", "size_bytes": size, "max_bytes": max_bytes, "values": {}}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"status": "parse_error", "error": str(exc), "values": {}}
    values: dict[str, list[str]] = {}
    for element in root.iter():
        if len(element) == 0 and element.text and element.text.strip():
            key = element.tag.rsplit("}", 1)[-1]
            values.setdefault(key, []).append(element.text.strip())
        for key, value in element.attrib.items():
            values.setdefault(f"{element.tag.rsplit('}', 1)[-1]}@{key}", []).append(value)
    return {"status": "parsed", "root_element": root.tag.rsplit("}", 1)[-1], "values": values}


def inspect_file(path: Path, *, run_probe: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return {"filename": path.name, "status": "not_found"}
    stat = path.stat()
    record: dict[str, Any] = {
        "filename": path.name,
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
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
        except Exception as exc:  # keep a failed probe visible without losing the checksum
            record["probe_error"] = f"{type(exc).__name__}: {exc}"
            record["status"] = "probe_error"
    return record


def build_report(paths: list[Path], *, run_probe: bool = True) -> dict[str, Any]:
    files = [inspect_file(path, run_probe=run_probe) for path in paths]
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
        },
        "limitations": [
            "Container metadata is not proof of a camera Log/gamut profile.",
            "XML leaf values are preserved as vendor metadata; field meanings are not guessed.",
            "A successful probe or decode does not validate a color transform.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash and inspect original footage/sidecars without modifying them.")
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
