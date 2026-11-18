from yrgb_engine.probe import extract_capture_metadata, probe_media


def test_missing_file(tmp_path):
    result = probe_media(tmp_path / "missing.mov")
    assert result.status == "not_found"
    assert result.exists is False


def test_png_signature_detected_without_optional_decoder(tmp_path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + b"0" * 24)
    result = probe_media(image)
    assert result.detected_type == "image"
    assert result.signature == "png"
    assert result.status == "signature_detected"


def test_size_limit(tmp_path):
    asset = tmp_path / "large.bin"
    asset.write_bytes(b"123456")
    result = probe_media(asset, max_file_bytes=3)
    assert result.status == "rejected_size_limit"


def test_capture_metadata_extracts_reported_sony_camera_and_recording_facts():
    payload = {
        "format": {"tags": {"make": "SONY", "model": "ILME-FX6V"}},
        "streams": [{
            "codec_type": "video", "codec_name": "prores", "profile": "Standard",
            "codec_tag_string": "apcn", "pix_fmt": "yuv422p10le",
            "color_transfer": "s-log3", "color_primaries": "bt2020",
            "tags": {"recording_mode": "XAVC-I", "firmware_version": "3.00"},
        }],
    }
    metadata = extract_capture_metadata(payload)
    assert metadata["camera_make"] == "SONY"
    assert metadata["camera_model"] == "ILME-FX6V"
    assert metadata["recording_mode"] == "XAVC-I"
    assert metadata["codec"] == "prores"
    assert metadata["bit_depth"] == 10
    assert metadata["firmware_version"] == "3.00"
    assert metadata["color_transfer"] == "s-log3"
    assert metadata["metadata_completeness"]["camera_model"] is True


def test_capture_metadata_does_not_guess_missing_camera_details():
    metadata = extract_capture_metadata({
        "format": {},
        "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}],
    })
    assert metadata["camera_model"] is None
    assert metadata["recording_mode"] is None
    assert metadata["bit_depth"] is None
    assert metadata["color_transfer"] is None
    assert metadata["metadata_completeness"]["camera_model"] is False


def test_capture_metadata_prefers_explicit_bit_depth_over_pixel_format():
    metadata = extract_capture_metadata({
        "streams": [{
            "codec_type": "video", "bits_per_raw_sample": "12",
            "pix_fmt": "yuv422p10le",
        }],
    })
    assert metadata["bit_depth"] == 12
