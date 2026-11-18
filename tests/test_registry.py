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
    )
    assert profile is not None
    assert profile["usable_for_transform"] is False


def test_wrong_gamut_resolves_only_its_own_candidate():
    registry = ProfileRegistry.load()
    profile = registry.resolve(
        manufacturer="Sony",
        encoding="S-Log3",
        gamut="S-Gamut3",
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
        item["selection_requirements"] == ["gamut_choice"]
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
    )
    assert [item["id"] for item in candidates] == ["sony.slog3.sgamut3cine"]
    assert candidates[0]["selection_requirements"] == []
