"""Command-line entry point for media inspection."""

import argparse
import json

from .probe import probe_media


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yrgb-probe",
        description="Inspect media files for the COLORIST YRGB Universal Color Engine.",
    )
    parser.add_argument("file", help="Path to a media file")
    parser.add_argument("--timeout", type=int, default=20, help="ffprobe timeout in seconds")
    parser.add_argument(
        "--max-file-gb",
        type=float,
        default=100,
        help="Maximum accepted file size in GiB (default: 100)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = probe_media(
        args.file,
        timeout_seconds=args.timeout,
        max_file_bytes=int(args.max_file_gb * 1024**3),
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
