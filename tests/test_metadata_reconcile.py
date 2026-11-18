from yrgb_engine.metadata_reconcile import reconcile_color_metadata


def test_sony_log_sidecar_conflicts_with_bt709_stream_transfer():
    result = reconcile_color_metadata(
        {
            "CaptureGammaEquation": ["s-log3-cine"],
            "CaptureColorPrimaries": ["s-gamut3-cine"],
            "CodingEquations": ["rec709"],
        },
        {
            "color_transfer": "bt709",
            "color_primaries": "bt709",
            "color_space": "bt709",
        },
    )
    assert result["resolution_status"] == "conflict"
    assert result["comparisons"]["camera_transfer"]["status"] == "conflict"
    assert result["comparisons"]["camera_primaries"]["status"] == "conflict"
    assert result["comparisons"]["coding_equations"]["status"] == "reported"
    assert result["xml_declared"]["camera_transfer"] == "s-log3-cine"
    assert result["stream_signaled"]["camera_transfer"] == "bt709"


def test_matching_declarations_are_reported_not_verified():
    result = reconcile_color_metadata(
        {
            "CaptureGammaEquation": ["S-Log3"],
            "CaptureColorPrimaries": ["S-Gamut3.Cine"],
            "CodingEquations": ["Rec.709"],
        },
        {
            "color_transfer": "s-log3",
            "color_primaries": "s-gamut3-cine",
            "color_space": "bt709",
        },
    )
    assert result["resolution_status"] == "reported"
    assert {item["status"] for item in result["comparisons"].values()} == {"reported"}


def test_missing_values_remain_unresolved_and_are_not_guessed():
    result = reconcile_color_metadata(
        {"CaptureGammaEquation": ["s-log3-cine"]},
        {"color_transfer": "s-log3"},
    )
    assert result["resolution_status"] == "unresolved"
    assert result["xml_declared"]["camera_primaries"] is None
    assert result["stream_signaled"]["camera_primaries"] is None


def test_empty_metadata_is_unresolved():
    result = reconcile_color_metadata({}, {})
    assert result["resolution_status"] == "unresolved"
    assert all(item["status"] == "unresolved" for item in result["comparisons"].values())
