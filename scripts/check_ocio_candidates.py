"""Smoke-test mapped camera color spaces against pinned ACES Studio config."""
from __future__ import annotations

import json
import sys

import PyOpenColorIO as ocio

from yrgb_engine.registry import ProfileRegistry


CONFIG_NAME = "studio-config-v4.0.0_aces-v2.0_ocio-v2.5"


def main() -> int:
    config = ocio.Config.CreateFromBuiltinConfig(CONFIG_NAME)
    names = set(config.getColorSpaceNames())
    report = []
    failed = False
    for profile in ProfileRegistry.load().list_profiles():
        source = profile.get("ocio_source_space")
        destination = profile.get("ocio_destination_space")
        if not source and not destination:
            continue
        source_exists = isinstance(source, str) and source in names
        destination_exists = isinstance(destination, str) and destination in names
        processor_ok = False
        error = None
        if source_exists and destination_exists:
            try:
                config.getProcessor(source, destination).getDefaultCPUProcessor()
                processor_ok = True
            except Exception as exc:  # OCIO provides config-specific exception types.
                error = str(exc)
        else:
            error = "Source or destination color-space name is absent from the pinned config."
        passed = source_exists and destination_exists and processor_ok
        failed = failed or not passed
        report.append({
            "profile_id": profile["id"],
            "source_space": source,
            "source_available": source_exists,
            "destination_space": destination,
            "destination_available": destination_exists,
            "processor_builds": processor_ok,
            "candidate_only": profile.get("status") != "verified",
            "error": error,
        })
    print(json.dumps({
        "config": CONFIG_NAME,
        "ocio_version": str(ocio.GetVersion()),
        "color_space_count": len(names),
        "all_mapped_candidates_build": not failed,
        "profiles": report,
    }, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
