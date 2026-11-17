"""Command-line entry point for media inspection and capability reporting."""
import argparse
import json
from .capabilities import capabilities_as_dict
from .probe import probe_media

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yrgb-probe", description="Inspect media for COLORIST YRGB.")
    parser.add_argument("legacy_file", nargs="?", help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command")
    probe_parser = subparsers.add_parser("probe", help="Inspect one media file")
    probe_parser.add_argument("file", help="Path to a media file")
    probe_parser.add_argument("--timeout", type=int, default=20)
    probe_parser.add_argument("--max-file-gb", type=float, default=100)
    subparsers.add_parser("capabilities", help="Report optional decoder/tool availability")
    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "capabilities":
        print(json.dumps(capabilities_as_dict(), indent=2, ensure_ascii=False))
        return
    if args.command == "probe":
        file_path, timeout = args.file, args.timeout
        max_bytes = int(args.max_file_gb * 1024**3)
    elif args.legacy_file:
        file_path, timeout, max_bytes = args.legacy_file, 20, 100 * 1024**3
    else:
        parser.error("provide a file path or use the probe/capabilities command")
    result = probe_media(file_path, timeout_seconds=timeout, max_file_bytes=max_bytes)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
