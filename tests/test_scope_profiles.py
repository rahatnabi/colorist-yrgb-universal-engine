import pytest

from yrgb_engine.scope_profiles import (
    available_scope_standards,
    get_scope_coefficients,
)


def test_scope_presets_are_explicit_and_normalized():
    assert available_scope_standards() == ("bt709", "bt2020")
    for standard in available_scope_standards():
        coefficients = get_scope_coefficients(standard)
        assert len(coefficients) == 3
        assert sum(coefficients) == pytest.approx(1.0)
        assert all(value >= 0 for value in coefficients)


def test_bt709_and_bt2020_presets_are_distinct():
    assert get_scope_coefficients("bt709") != get_scope_coefficients("bt2020")


def test_unknown_scope_standard_is_rejected():
    with pytest.raises(ValueError, match="Scope standard"):
        get_scope_coefficients("guess")
