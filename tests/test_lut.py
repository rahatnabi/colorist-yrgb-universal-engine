import pytest

from yrgb_engine.cube import parse_cube_text
from yrgb_engine.lut import LUTApplicationError, apply_cube_rgb


def test_identity_3d_lut_preserves_rgb():
    lut = parse_cube_text("""LUT_3D_SIZE 2
0 0 0
0 0 1
0 1 0
0 1 1
1 0 0
1 0 1
1 1 0
1 1 1
""")
    assert apply_cube_rgb((0.2, 0.4, 0.8), lut) == pytest.approx((0.2, 0.4, 0.8))


def test_lut_intensity_zero_returns_original():
    lut = parse_cube_text("""LUT_3D_SIZE 2
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
""")
    assert apply_cube_rgb((0.2, 0.4, 0.8), lut, intensity=0) == (0.2, 0.4, 0.8)


def test_lut_intensity_half_blends_result():
    lut = parse_cube_text("""LUT_3D_SIZE 2
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
1 1 1
""")
    assert apply_cube_rgb((0.2, 0.4, 0.8), lut, intensity=0.5) == pytest.approx(
        (0.6, 0.7, 0.9)
    )


def test_invalid_intensity_is_rejected():
    lut = parse_cube_text("LUT_1D_SIZE 2\n0 0 0\n1 1 1\n")
    with pytest.raises(LUTApplicationError):
        apply_cube_rgb((0, 0, 0), lut, intensity=1.1)
