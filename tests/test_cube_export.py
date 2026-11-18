import pytest

from yrgb_engine.cube import parse_cube_text
from yrgb_engine.cube_export import CubeExportError, generate_cube_text, resample_cube_text


def test_generate_identity_35_point_cube_round_trips():
    text = generate_cube_text(lambda rgb: rgb, size=35, title="Identity")
    parsed = parse_cube_text(text)
    assert parsed.size_3d == 35
    assert parsed.title == "Identity"
    assert len(parsed.values_3d) == 35 ** 3
    assert parsed.values_3d[0] == (0.0, 0.0, 0.0)
    assert parsed.values_3d[-1] == (1.0, 1.0, 1.0)


def test_generate_65_point_cube_has_correct_entry_count():
    text = generate_cube_text(lambda rgb: rgb, size=65)
    parsed = parse_cube_text(text)
    assert parsed.size_3d == 65
    assert len(parsed.values_3d) == 274625


def test_generate_cube_rejects_unsupported_size_and_bad_output():
    with pytest.raises(CubeExportError, match="Unsupported"):
        generate_cube_text(lambda rgb: rgb, size=64)
    with pytest.raises(CubeExportError, match="finite"):
        generate_cube_text(lambda rgb: (float("nan"), 0.0, 0.0), size=17)


def test_resample_existing_cube_to_35_points():
    source = parse_cube_text(
        "LUT_3D_SIZE 2\n" +
        "0 0 0\n0 0 1\n0 1 0\n0 1 1\n"
        "1 0 0\n1 0 1\n1 1 0\n1 1 1\n"
    )
    parsed = parse_cube_text(resample_cube_text(source, size=35))
    assert parsed.size_3d == 35
    assert len(parsed.values_3d) == 35 ** 3
