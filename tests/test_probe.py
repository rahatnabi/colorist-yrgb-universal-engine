from yrgb_engine.probe import probe_media


def test_missing_file(tmp_path):
    result = probe_media(tmp_path / "missing.mov")
    assert result.status == "not_found"
    assert result.exists is False


def test_png_signature_detected_without_optional_decoder(tmp_path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 24)
    result = probe_media(image)
    assert result.detected_type == "image"
    assert result.signature == "png"
    assert result.status == "signature_detected"


def test_size_limit(tmp_path):
    asset = tmp_path / "large.bin"
    asset.write_bytes(b"123456")
    result = probe_media(asset, max_file_bytes=3)
    assert result.status == "rejected_size_limit"
