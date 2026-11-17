from pathlib import Path
from unittest.mock import patch

import pytest

from yrgb_engine.oiio_sequence import ImageSequenceDecodeError, decode_oiio_sequence_float
from yrgb_engine.precision import PrecisionFrame


def _frame(path: Path, width: int = 2) -> PrecisionFrame:
    return PrecisionFrame.from_interleaved(
        width=width, height=1, channel_names=("R", "G", "B"),
        values=[0.0] * width * 3, source_path=str(path), decoder="test"
    )


def test_sequence_decoder_refuses_gaps_by_default(tmp_path):
    (tmp_path / "shot.0001.exr").write_bytes(b"a")
    (tmp_path / "shot.0003.exr").write_bytes(b"b")
    with pytest.raises(ImageSequenceDecodeError, match="missing frame"):
        list(decode_oiio_sequence_float(tmp_path / "shot.####.exr"))


def test_sequence_decoder_yields_in_order_and_checks_shape(tmp_path):
    for name in ("shot.0001.exr", "shot.0002.exr"):
        (tmp_path / name).write_bytes(b"placeholder")
    pattern = tmp_path / "shot.####.exr"
    with patch("yrgb_engine.oiio_sequence.decode_oiio_float", side_effect=lambda p: _frame(Path(p))):
        frames = list(decode_oiio_sequence_float(pattern))
    assert [index for index, _ in frames] == [1, 2]
    assert frames[0][1].metadata["sequence_index"] == 1


def test_sequence_decoder_rejects_inconsistent_dimensions(tmp_path):
    for name in ("shot.0001.exr", "shot.0002.exr"):
        (tmp_path / name).write_bytes(b"placeholder")
    pattern = tmp_path / "shot.####.exr"
    with patch(
        "yrgb_engine.oiio_sequence.decode_oiio_float",
        side_effect=[_frame(tmp_path / "one.exr", 2), _frame(tmp_path / "two.exr", 3)],
    ):
        with pytest.raises(ImageSequenceDecodeError, match="expected"):
            list(decode_oiio_sequence_float(pattern))
