import pytest

from yrgb_engine.registry import ProfileRegistry, ProfileRegistryError


def test_registry_loads_candidate_profiles():
    registry = ProfileRegistry.load()
    assert len(registry.list_profiles()) >= 10


def test_exact_profile_is_not_assumed_verified():
    registry = ProfileRegistry.load()
    profile = registry.resolve(
        manufacturer="Sony",
        encoding="S-Log3",
        gamut="S-Gamut3.Cine",
        camera_model="ILME-FX6",
    )
    assert profile is not None
    assert profile["usable_for_transform"] is False


def test_wrong_gamut_resolves_only_its_own_candidate():
    registry = ProfileRegistry.load()
    profile = registry.resolve(
        manufacturer="Sony",
        encoding="S-Log3",
        gamut="S-Gamut3",
        camera_model="ILME-FX6",
    )
    assert profile is not None
    assert profile["id"] == "sony.slog3.sgamut3"


def test_unknown_profile_does_not_guess():
    registry = ProfileRegistry.load()
    assert registry.resolve(
        manufacturer="Unknown",
        encoding="Mystery Log",
        gamut=None,
    ) is None


def test_camera_model_matching_is_case_insensitive():
    registry = ProfileRegistry([
        {
            "id": "test.camera.log",
            "manufacturer": "Example",
            "encoding": "Log",
            "gamut": "Wide",
            "camera_models": ["Model X"],
            "status": "unverified",
            "transform_id": None,
        }
    ])
    assert registry.resolve(
        manufacturer="example",
        encoding="log",
        gamut="wide",
        camera_model="model x",
    ) is not None
    assert registry.resolve(
        manufacturer="example",
        encoding="log",
        gamut="wide",
        camera_model="other",
    ) is None


def test_verified_status_requires_transform_id():
    registry = ProfileRegistry([
        {
            "id": "test.no.transform",
            "manufacturer": "Example",
            "encoding": "Log",
            "gamut": "Wide",
            "camera_models": [],
            "status": "verified",
            "transform_id": None,
        }
    ])
    assert registry.get_by_id("test.no.transform")["usable_for_transform"] is False


def test_invalid_profile_status_is_rejected():
    with pytest.raises(ProfileRegistryError, match="unsupported status"):
        ProfileRegistry([
            {
                "id": "test.bad",
                "manufacturer": "Example",
                "encoding": "Log",
                "status": "magic",
            }
        ])


def test_duplicate_profile_ids_are_rejected():
    profile = {
        "id": "duplicate",
        "manufacturer": "Example",
        "encoding": "Log",
        "status": "unverified",
    }
    with pytest.raises(ProfileRegistryError, match="unique"):
        ProfileRegistry([profile, profile])


def test_returned_profile_records_do_not_mutate_registry():
    registry = ProfileRegistry.load()
    profiles = registry.list_profiles()
    profiles[0]["camera_models"].append("Injected Model")
    assert "Injected Model" not in registry.list_profiles()[0]["camera_models"]


def test_non_object_profile_is_rejected():
    with pytest.raises(ProfileRegistryError, match="must be an object"):
        ProfileRegistry([None])



def test_candidate_discovery_returns_distinct_gamut_choices_without_guessing():
    registry = ProfileRegistry.load()
    candidates = registry.find_candidates(
        manufacturer="Sony",
        encoding="S-Log3",
    )
    assert {item["gamut"] for item in candidates} == {
        "S-Gamut3", "S-Gamut3.Cine"
    }
    assert all(
        item["selection_requirements"] == ["gamut_choice", "camera_model"]
        for item in candidates
    )
    assert all(item["usable_for_transform"] is False for item in candidates)


def test_candidate_discovery_marks_required_camera_model():
    registry = ProfileRegistry([
        {
            "id": "model-specific",
            "manufacturer": "Example",
            "encoding": "Log",
            "gamut": "Wide",
            "camera_models": ["Camera A"],
            "status": "unverified",
            "transform_id": None,
        }
    ])
    candidates = registry.find_candidates(manufacturer="Example", encoding="Log")
    assert len(candidates) == 1
    assert candidates[0]["selection_requirements"] == [
        "gamut_choice", "camera_model"
    ]
    assert registry.find_candidates(
        manufacturer="Example", encoding="Log", camera_model="Camera B"
    ) == []


def test_candidate_discovery_can_narrow_to_exact_profile_variant():
    registry = ProfileRegistry.load()
    candidates = registry.find_candidates(
        manufacturer="Sony",
        encoding="S-Log3",
        gamut="S-Gamut3.Cine",
        camera_model="ILME-FX3",
    )
    assert [item["id"] for item in candidates] == ["sony.slog3.sgamut3cine"]
    assert candidates[0]["selection_requirements"] == []


def test_verified_profile_requires_reference_validation_record():
    registry = ProfileRegistry([{
        "id": "test.claimed.verified",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "camera_models": [],
        "status": "verified",
        "transform_id": "example.log-to-wide",
    }])
    profile = registry.get_by_id("test.claimed.verified")
    assert profile["usable_for_transform"] is False
    assert profile["validation_status"] == "not_reference_validated"


def test_verified_profile_with_passing_reference_record_is_usable():
    registry = ProfileRegistry([{
        "id": "test.reference.validated",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "camera_models": [],
        "status": "verified",
        "transform_id": "example.log-to-wide",
        "ocio_source_space": "Example Camera Log",
        "ocio_destination_space": "DaVinci Wide Gamut",
        "output_transfer": "DaVinci Intermediate",
        "output_primaries": "DaVinci Wide Gamut",
        "validation": {
            "passed": True,
            "profile_id": "test.reference.validated",
            "transform_id": "example.log-to-wide",
            "source_space": "Example Camera Log",
            "destination_space": "DaVinci Wide Gamut",
            "config_sha256": "a" * 64,
            "reference_set_id": "vendor-chart-v1",
            "vector_count": 24,
            "max_absolute_error": 0.00001,
            "tolerance": 0.0001,
        },
    }])
    profile = registry.get_by_id("test.reference.validated")
    assert profile["usable_for_transform"] is True
    assert profile["validation_status"] == "reference_validated"


def test_failed_reference_record_never_enables_profile():
    registry = ProfileRegistry([{
        "id": "test.reference.failed",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "camera_models": [],
        "status": "verified",
        "transform_id": "example.log-to-wide",
        "validation": {
            "passed": False,
            "profile_id": "test.reference.failed",
            "transform_id": "example.log-to-wide",
            "source_space": "Example Camera Log",
            "destination_space": "DaVinci Wide Gamut",
            "config_sha256": "a" * 64,
            "reference_set_id": "vendor-chart-v1",
            "vector_count": 24,
        },
    }])
    assert registry.get_by_id("test.reference.failed")["usable_for_transform"] is False


def test_requested_camera_families_are_in_catalogue():
    registry = ProfileRegistry.load()
    profiles = {item["id"]: item for item in registry.list_profiles()}
    expected = {
        "insta360.ilog.luna_rec2020",
        "insta360.ilog.x5_x6_bt2020",
        "red.log3g12.redwidegamutrgb",
        "blackmagic.film_gen4.pocket_4k_6k",
        "blackmagic.film_gen5.bmd_wide_gamut",
        "nikon.nlog",
        "dji.dlog",
    }
    assert expected.issubset(profiles)
    assert all(profiles[item]["status"] == "unverified" for item in expected)


def test_insta360_ilog_variants_remain_model_specific():
    registry = ProfileRegistry.load()
    luna = registry.resolve(
        manufacturer="Insta360",
        encoding="I-Log",
        gamut="Rec.2020",
        camera_model="Insta360 Luna Pro",
    )
    x_series = registry.resolve(
        manufacturer="Insta360",
        encoding="I-Log 10-bit",
        gamut="BT.2020",
        camera_model="Insta360 X5",
    )
    assert luna["id"] == "insta360.ilog.luna_rec2020"
    assert x_series["id"] == "insta360.ilog.x5_x6_bt2020"
    assert registry.resolve(
        manufacturer="Insta360",
        encoding="I-Log",
        gamut="Rec.2020",
        camera_model="Insta360 X5",
    ) is None


def test_pocket_cinema_camera_gen4_and_gen5_are_distinct():
    registry = ProfileRegistry.load()
    gen4 = registry.resolve(
        manufacturer="Blackmagic Design",
        encoding="Blackmagic Film Gen 4",
        gamut="Blackmagic Design",
        camera_model="Blackmagic Pocket Cinema Camera 4K",
    )
    gen5 = registry.resolve(
        manufacturer="Blackmagic Design",
        encoding="Blackmagic Film Gen 5",
        gamut="Blackmagic Wide Gamut",
        camera_model="Blackmagic Pocket Cinema Camera 6K",
    )
    assert gen4["id"] == "blackmagic.film_gen4.pocket_4k_6k"
    assert gen5["id"] == "blackmagic.film_gen5.bmd_wide_gamut"
    assert gen4["usable_for_transform"] is False
    assert gen5["usable_for_transform"] is False


def test_nikon_dji_and_red_gamut_pairs_are_explicit():
    registry = ProfileRegistry.load()
    assert registry.resolve(
        manufacturer="Nikon", encoding="N-Log", gamut="N-Gamut"
    )["id"] == "nikon.nlog"
    assert registry.resolve(
        manufacturer="DJI", encoding="D-Log", gamut="D-Gamut"
    )["id"] == "dji.dlog"
    assert registry.resolve(
        manufacturer="RED", encoding="Log3G12", gamut="REDWideGamutRGB"
    )["id"] == "red.log3g12.redwidegamutrgb"


def test_apple_log_and_apple_log2_are_distinct_exact_profiles():
    registry = ProfileRegistry.load()
    apple_log = registry.resolve(
        manufacturer="Apple",
        encoding="Apple Log",
        gamut="BT.2020",
    )
    apple_log2 = registry.resolve(
        manufacturer="Apple",
        encoding="Apple Log 2",
        gamut="Apple Gamut",
    )
    assert apple_log["id"] == "apple.applelog"
    assert apple_log2["id"] == "apple.applelog2.apple_gamut"
    assert apple_log["usable_for_transform"] is False
    assert apple_log2["usable_for_transform"] is False
    assert registry.resolve(
        manufacturer="Apple",
        encoding="Apple Log",
        gamut="Apple Gamut",
    ) is None


def test_aces_candidate_mappings_are_not_mistaken_for_validated_transforms():
    registry = ProfileRegistry.load()
    sony = registry.get_by_id("sony.slog3.sgamut3cine")
    apple = registry.get_by_id("apple.applelog")
    assert sony["ocio_source_space"] == "S-Log3 S-Gamut3.Cine"
    assert sony["ocio_destination_space"] == "Linear DaVinci WideGamut"
    assert sony["transform_mapping_status"] == "mapped_unvalidated"
    assert sony["usable_for_transform"] is False
    assert apple["ocio_source_space"] == "Apple Log"
    assert apple["usable_for_transform"] is False


def test_profile_mapping_without_independent_reference_evidence_is_blocked():
    registry = ProfileRegistry([{
        "id": "test.mapped.only",
        "manufacturer": "Example",
        "encoding": "Log",
        "gamut": "Wide",
        "status": "unverified",
        "transform_id": "test.transform",
        "ocio_source_space": "Example Log",
        "ocio_destination_space": "DaVinci Intermediate WideGamut",
        "output_transfer": "DaVinci Intermediate",
        "output_primaries": "DaVinci Wide Gamut",
    }])
    profile = registry.get_by_id("test.mapped.only")
    assert profile["transform_mapping_status"] == "mapped_unvalidated"
    assert profile["usable_for_transform"] is False


def test_dji_dlog_candidate_uses_exact_aces_studio_space_name():
    profile = ProfileRegistry.load().get_by_id("dji.dlog")
    assert profile["ocio_source_space"] == "D-Log D-Gamut"
    assert profile["usable_for_transform"] is False
