from yrgb_engine.capture_matching import match_capture_profile
from yrgb_engine.registry import ProfileRegistry


def test_sony_slog3_without_gamut_returns_both_variants_and_blocks_selection():
    result = match_capture_profile({
        "camera_make": "SONY",
        "camera_model": "ILME-FX6",
        "color_transfer": "S-Log3",
        "color_primaries": "bt2020",
        "metadata_tags": {},
    }, ProfileRegistry.load())
    assert result["status"] == "needs_gamut_confirmation"
    assert result["selection_made"] is False
    assert {item["id"] for item in result["candidates"]} == {
        "sony.slog3.sgamut3cine", "sony.slog3.sgamut3"
    }
    assert all(item["usable_for_transform"] is False for item in result["candidates"])


def test_explicit_s_gamut3_cine_matches_only_cine_candidate():
    result = match_capture_profile({
        "camera_make": "Sony",
        "camera_model": "ILME-FX3",
        "color_transfer": "S-Log3",
        "camera_gamut": "S-Gamut3.Cine",
    }, ProfileRegistry.load())
    assert result["status"] == "candidate_unvalidated"
    assert [item["id"] for item in result["candidates"]] == [
        "sony.slog3.sgamut3cine"
    ]


def test_bt2020_primaries_are_not_misread_as_camera_gamut():
    result = match_capture_profile({
        "camera_make": "Sony",
        "camera_model": "ILME-FX9",
        "color_transfer": "S-Log3",
        "color_primaries": "bt2020",
        "metadata_tags": {},
    }, ProfileRegistry.load())
    assert result["gamut"] is None
    assert result["status"] == "needs_gamut_confirmation"
    assert len(result["candidates"]) == 2


def test_unknown_model_does_not_match_fx_family_restricted_profile():
    result = match_capture_profile({
        "camera_make": "Sony",
        "camera_model": "Unknown Sony Camera",
        "color_transfer": "S-Log3",
        "camera_gamut": "S-Gamut3.Cine",
    }, ProfileRegistry.load())
    assert result["status"] == "no_exact_candidate"
    assert result["candidates"] == []


def test_missing_manufacturer_fails_closed():
    result = match_capture_profile({
        "camera_model": "ILME-FX6",
        "color_transfer": "S-Log3",
    }, ProfileRegistry.load())
    assert result["status"] == "needs_camera_make"
    assert result["selection_made"] is False


def test_gamut_can_be_read_only_from_explicit_vendor_tag():
    result = match_capture_profile({
        "camera_make": "Sony",
        "camera_model": "ILME-FX9",
        "color_transfer": "S-Log3",
        "metadata_tags": {"Camera_Gamut": "S-Gamut3"},
    }, ProfileRegistry.load())
    assert result["status"] == "candidate_unvalidated"
    assert [item["id"] for item in result["candidates"]] == [
        "sony.slog3.sgamut3"
    ]
