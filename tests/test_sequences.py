from pathlib import Path

import pytest

from yrgb_engine.sequences import discover_image_sequence


def test_hash_pattern_discovers_frames_and_gaps(tmp_path: Path):
    for name in ("shot.0001.png", "shot.0002.png", "shot.0004.png"):
        (tmp_path / name).write_bytes(b"frame")
    sequence = discover_image_sequence(tmp_path / "shot.####.png")
    assert sequence.frame_count == 3
    assert sequence.start_index == 1
    assert sequence.end_index == 4
    assert sequence.missing_indices == [3]
    assert sequence.frame_path(2).name == "shot.0002.png"


def test_printf_pattern_discovers_frames(tmp_path: Path):
    for name in ("plate_0010.exr", "plate_0011.exr"):
        (tmp_path / name).write_bytes(b"frame")
    sequence = discover_image_sequence(tmp_path / "plate_%04d.exr")
    assert sequence.frame_count == 2
    assert sequence.missing_indices == []


def test_invalid_pattern_requires_frame_token(tmp_path: Path):
    with pytest.raises(ValueError, match="frame token"):
        discover_image_sequence(tmp_path / "still.png")


def test_missing_directory_returns_empty_sequence(tmp_path: Path):
    sequence = discover_image_sequence(tmp_path / "absent" / "frame.####.png")
    assert sequence.frame_count == 0
