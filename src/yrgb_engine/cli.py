"""Command-line entry point for media inspection and capability reporting."""
import argparse
import json
from .capabilities import capabilities_as_dict
from .probe import probe_media

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yrgb-probe", description="Inspect media for COLORIST YRGB.")
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
    elif args.command is None and getattr(args, "command", None) is None:
        parser.error("provide a file path or use the 'capabilities' command")
    else:
        # Backwards-compatible yrgb-probe FILE form.
        file_path, timeout, max_bytes = args.command, 20, 100 * 1024**3
    result = probe_media(file_path, timeout_seconds=timeout, max_file_bytes=max_bytes)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
