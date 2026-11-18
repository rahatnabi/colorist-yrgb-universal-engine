import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_footage_library_schema_is_valid_json_schema_document():
    schema = json.loads((ROOT / "data/footage_library/schema.json").read_text())
    assert schema["$schema"].endswith("/2020-12/schema")
    assert schema["type"] == "object"
    assert "asset_id" in schema["required"]
    assert "provenance" in schema["required"]
    assert "files" in schema["required"]
    assert "profile_claim" in schema["required"]


def test_two_sony_clips_are_registered_independently_and_not_falsely_verified():
    manifest = json.loads((ROOT / "data/footage_library/assets.json").read_text())
    assert manifest["schema_version"] == 1
    assert len(manifest["assets"]) == 2

    by_id = {asset["asset_id"]: asset for asset in manifest["assets"]}
    assert set(by_id) == {"sony-slog3cine-c1382", "sony-slog3cine-c1383"}
    for clip in ("C1382", "C1383"):
        asset = by_id[f"sony-slog3cine-{clip.lower()}"]
        assert asset["asset_kind"] == "camera_original"
        assert asset["asset_state"] == "registered"
        assert asset["profile_claim"] == {
            "transfer_function": "Sony S-Log3",
            "gamut": "Sony S-Gamut3.Cine",
            "claim_source": "user_asserted",
            "verification_state": "unverified",
        }
        assert {item["filename"] for item in asset["files"]} == {
            f"{clip}.MP4", f"{clip}M01.XML"
        }
        assert all(item["acquisition_state"] == "pending" for item in asset["files"])
        assert all(item["sha256"] is None for item in asset["files"])
        assert asset["provenance"]["rights_status"] == "unknown"
        metadata = asset["capture_metadata"]
        assert metadata["camera_model"] == "ILME-FX30"
        assert metadata["codec"] == "AVC/H.264 (user-reported)"
        assert metadata["width"] == 3840 and metadata["height"] == 2160
        assert metadata["chroma_subsampling"] == "4:2:2 (reported)"
        assert metadata["frame_rate"] == "25/1 fps (25.00p)"
        assert metadata["transfer"] == "S-Log3"
        assert metadata["primaries"] == "S-Gamut3.Cine"
        # Bit depth and range remain unknown until the original stream is probed.
        assert metadata["bit_depth"] is None
        assert metadata["range"] is None
