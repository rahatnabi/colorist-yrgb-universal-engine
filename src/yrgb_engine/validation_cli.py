"""CLI for running reference-vector validation against a pinned OCIO config."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import ProfileRegistry
from .reference_data import ReferenceManifestError, validate_reference_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yrgb-validate-transform",
        description="Validate one camera transform against traceable reference RGB vectors.",
    )
    parser.add_argument("--manifest", required=True, help="JSON reference-vector manifest")
    parser.add_argument("--config", required=True, help="Pinned OCIO config file")
    parser.add_argument("--registry", help="Camera registry JSON (defaults to bundled registry)")
    parser.add_argument("--tolerance", type=float, default=1e-5)
    parser.add_argument("--output", help="Optional path for the validation audit JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        registry = ProfileRegistry.load(args.registry) if args.registry else ProfileRegistry.load()
        result = validate_reference_manifest(
            args.manifest,
            config_path=args.config,
            registry=registry,
            tolerance=args.tolerance,
        )
    except (ReferenceManifestError, ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2))
        return 2

    audit = result.to_registry_record()
    rendered = json.dumps(audit, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
