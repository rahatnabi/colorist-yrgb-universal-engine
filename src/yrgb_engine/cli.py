"""Command-line entry point for media inspection and capability reporting."""

import argparse
import json

from .capabilities import capabilities_as_dict
from .probe import probe_media

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yrgb-probe", description="Inspect media for COLORIST YRGB.")
    parser.add_argument("target", nargs="?", help="File path, 'probe', or 'capabilities'")
    parser.add_argument("file", nargs="?", help="File path when using the probe subcommand")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-file-gb", type=float, default=100)
    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.target == "capabilities" and args.file is None:
        print(json.dumps(capabilities_as_dict(), indent=2, ensure_ascii=False))
        return
    if args.target == "probe":
        if not args.file:
            parser.error("probe requires a file path")
        file_path = args.file
    elif args.target and args.file is None:
        file_path = args.target
    else:
        parser.error("use yrgb-probe FILE, yrgb-probe probe FILE, or yrgb-probe capabilities")
    result = probe_media(
        file_path,
        timeout_seconds=args.timeout,
        max_file_bytes=int(args.max_file_gb * 1024**3),
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
