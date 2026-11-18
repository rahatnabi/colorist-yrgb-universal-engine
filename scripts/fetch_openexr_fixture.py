"""Fetch pinned OpenEXR conformance fixtures from an immutable GitHub revision."""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

FIXTURES = {
    "line-order-increasing": {"url": "https://raw.githubusercontent.com/AcademySoftwareFoundation/openexr/49a84f33e675ad4457c8487293eee35622a0c9fd/src/test/OpenEXRTest/lineOrder_increasing.exr", "size": 144543, "git_blob_sha1": "6d7ed0c0fdfefae6e4b73ccd1c3e5cc9f6321b50"},
    "line-order-decreasing": {"url": "https://raw.githubusercontent.com/AcademySoftwareFoundation/openexr/49a84f33e675ad4457c8487293eee35622a0c9fd/src/test/OpenEXRTest/lineOrder_decreasing.exr", "size": 144543, "git_blob_sha1": "cc95ecc73abb5d186a4b7e0958a97c854fe624f4"},
}

def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def fetch_fixture(name: str, output: Path, timeout: int = 30) -> Path:
    if name not in FIXTURES:
        raise ValueError("Unknown fixture: " + name + "; choose from: " + ", ".join(FIXTURES))
    spec = FIXTURES[name]
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "COLORIST-YRGB-Universal-Engine/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(spec["size"] + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Could not fetch " + name + ": " + str(exc)) from exc
    if len(data) != spec["size"]:
        raise RuntimeError("Unexpected fixture size for " + name + ": expected " + str(spec["size"]) + ", got " + str(len(data)))
    actual = git_blob_sha1(data)
    if actual != spec["git_blob_sha1"]:
        raise RuntimeError("Git blob checksum mismatch for " + name + ": expected " + spec["git_blob_sha1"] + ", got " + actual)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=sorted(FIXTURES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        path = fetch_fixture(args.fixture, args.output)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Verified " + args.fixture + ": " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
