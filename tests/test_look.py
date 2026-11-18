import pytest

from yrgb_engine.look import (
    LookDevelopmentError,
    LookSettings,
    apply_look_rgb,
    bake_3d_cube,
)


def test_default_look_is_identity():
    assert apply_look_rgb((0.2, 0.4, 0.6), LookSettings()) == pytest.approx((0.2, 0.4, 0.6))


def test_exposure_is_measured_in_stops_for_linear_rgb():
    result = apply_look_rgb((0.1, 0.2, 0.3), LookSettings(exposure_stops=1))
    assert result == pytest.approx((0.2, 0.4, 0.6))


def test_saturation_zero_maps_channels_to_weighted_luma():
    result = apply_look_rgb((0.8, 0.2, 0.1), LookSettings(saturation=0))
    expected = 0.8 * 0.2126 + 0.2 * 0.7152 + 0.1 * 0.0722
    assert result == pytest.approx((expected, expected, expected))


def test_temperature_and_tint_are_documented_rgb_gain_offsets():
    warm = apply_look_rgb((0.2, 0.2, 0.2), LookSettings(temperature_shift=1))
    assert warm[0] > warm[2]
    green = apply_look_rgb((0.2, 0.2, 0.2), LookSettings(tint_shift=1))
    assert green[1] > green[0]


def test_master_curve_interpolates_and_preserves_monotonicity():
    settings = LookSettings(master_curve=((0, 0), (0.5, 0.25), (1, 1)))
    assert apply_look_rgb((0.5, 0.5, 0.5), settings) == pytest.approx((0.25,)*3)


def test_invalid_curve_and_controls_rejected():
    with pytest.raises(LookDevelopmentError, match="non-decreasing"):
        apply_look_rgb((0.5,)*3, LookSettings(master_curve=((0, 0), (0.5, 0.8), (1, 0.7))))
    with pytest.raises(LookDevelopmentError, match="exposure_stops"):
        apply_look_rgb((0.5,)*3, LookSettings(exposure_stops=9))


def test_cube_bake_has_expected_header_and_grid_entries():
    result = bake_3d_cube(
        LookSettings(), size=17, title="YRGB Neutral", input_space_id="scene-linear-rec709"
    )
    assert 'TITLE "YRGB Neutral"' in result
    assert "LUT_3D_SIZE 17" in result
    assert result.count("\n") == 17**3 + 6
    assert "0.500000000" in result


def test_look_preserves_linear_highlights_above_one_and_negative_values():
    result = apply_look_rgb((0.75, -0.1, 0.25), LookSettings(exposure_stops=1))
    assert result == pytest.approx((1.5, -0.2, 0.5))
