"""Fetch a pinned ACES 2.0 / OCIO 2.5 config from its GitHub release.

The downloaded file is verified against the SHA-256 digest published by the
upstream GitHub release API. This is a reference config, not camera validation.
"""
from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

ASSETS = {
    "studio": (
        "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/"
        "releases/download/v4.0.0/studio-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
        "eda5b0008a43b72b98ad540e32eb0eb83b340dde54e35bddba64ccbafac1029a",
    ),
    "studio-all-views": (
        "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/"
        "releases/download/v4.0.0/studio-config-all-views-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
        "0f19d42caab7213be71decd92edd802e67df737b438471013819b01b23238e9d",
    ),
    "reference": (
        "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/"
        "releases/download/v4.0.0/reference-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
        "dc50a0881cb5724e714bc37759a26396e9ab46cfe85934ade708f316dd980f38",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=ASSETS, default="studio")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    url, expected_digest = ASSETS[args.variant]
    request = urllib.request.Request(
        url, headers={"User-Agent": "COLORIST-YRGB-Universal-Engine"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()

    actual_digest = hashlib.sha256(payload).hexdigest()
    if actual_digest != expected_digest:
        raise SystemExit(
            "Downloaded ACES config SHA-256 mismatch; refusing to save it. "
            f"Expected {expected_digest}, got {actual_digest}."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"Verified ACES v4.0.0 config: {args.output}")
    print(f"SHA-256: {actual_digest}")
    print("Note: config compatibility is not independent camera-transform validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
