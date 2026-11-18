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


def test_first_sony_intake_is_registered_but_not_falsely_verified():
    manifest = json.loads((ROOT / "data/footage_library/assets.json").read_text())
    assert manifest["schema_version"] == 1
    assert len(manifest["assets"]) == 1

    asset = manifest["assets"][0]
    assert asset["asset_kind"] == "camera_original"
    assert asset["asset_state"] == "registered"
    assert asset["profile_claim"] == {
        "transfer_function": "Sony S-Log3",
        "gamut": "Sony S-Gamut3.Cine",
        "claim_source": "user_asserted",
        "verification_state": "unverified",
    }
    assert {item["filename"] for item in asset["files"]} == {
        "C1382.MP4",
        "C1382M01.XML",
        "C1383.MP4",
        "C1383M01.XML",
    }
    assert all(item["acquisition_state"] == "pending" for item in asset["files"])
    assert all(item["sha256"] is None for item in asset["files"])
    assert asset["provenance"]["rights_status"] == "unknown"
