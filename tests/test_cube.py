import pytest

from yrgb_engine.cube import CubeLUTError, parse_cube_text


def test_parse_3d_cube_metadata_and_values():
    lut = parse_cube_text('''TITLE "Test LUT"
LUT_3D_SIZE 2
DOMAIN_MIN 0 0 0
DOMAIN_MAX 1 1 1
0 0 0
1 0 0
0 1 0
1 1 0
0 0 1
1 0 1
0 1 1
1 1 1
''')
    assert lut.title == "Test LUT"
    assert lut.kind == "3d"
    assert lut.size_3d == 2
    assert len(lut.values_3d) == 8


def test_parse_combined_1d_and_3d_cube():
    text = "LUT_1D_SIZE 2\nLUT_3D_SIZE 2\n" + "0 0 0\n1 1 1\n" + "0 0 0\n" * 8
    lut = parse_cube_text(text)
    assert lut.kind == "1d+3d"
    assert len(lut.values_1d) == 2
    assert len(lut.values_3d) == 8


def test_reject_incomplete_cube():
    with pytest.raises(CubeLUTError, match="Expected"):
        parse_cube_text("LUT_3D_SIZE 2\n0 0 0\n")


def test_reject_invalid_domain():
    with pytest.raises(CubeLUTError, match="DOMAIN_MIN"):
        parse_cube_text("LUT_1D_SIZE 2\nDOMAIN_MIN 1 0 0\nDOMAIN_MAX 1 1 1\n0 0 0\n1 1 1\n")
