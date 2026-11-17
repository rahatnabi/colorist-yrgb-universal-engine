from unittest.mock import patch
import pytest

from yrgb_engine.oiio_decoder import HighPrecisionDecodeError, decode_oiio_float


def test_oiio_decoder_rejects_missing_file(tmp_path):
    with pytest.raises(HighPrecisionDecodeError, match="File not found"):
        decode_oiio_float(tmp_path / "missing.exr")


def test_oiio_decoder_reports_missing_optional_dependencies(tmp_path):
    asset = tmp_path / "placeholder.exr"
    asset.write_bytes(b"not a real EXR")
    with patch.dict("sys.modules", {"OpenImageIO": None}):
        with pytest.raises(HighPrecisionDecodeError, match="high-precision"):
            decode_oiio_float(asset)
