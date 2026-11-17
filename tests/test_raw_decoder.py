from unittest.mock import patch

import pytest

from yrgb_engine.oiio_decoder import HighPrecisionDecodeError
from yrgb_engine.raw_decoder import decode_raw_camera_rgb


def test_raw_decoder_rejects_missing_file(tmp_path):
    with pytest.raises(HighPrecisionDecodeError, match="File not found"):
        decode_raw_camera_rgb(tmp_path / "missing.dng")


def test_raw_decoder_reports_missing_optional_dependency(tmp_path):
    raw_file = tmp_path / "placeholder.dng"
    raw_file.write_bytes(b"not a real DNG")
    with patch.dict("sys.modules", {"rawpy": None}):
        with pytest.raises(HighPrecisionDecodeError, match="raw extra"):
            decode_raw_camera_rgb(raw_file)
