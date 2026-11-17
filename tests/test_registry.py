from yrgb_engine.registry import ProfileRegistry


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


def test_wrong_gamut_does_not_resolve():
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
