from yrgb_engine.signatures import detect_signature


def test_png_signature():
    assert detect_signature(b"\x89PNG\r\n\x1a\nrest", ".png") == ("image", "png")


def test_jpeg_signature():
    assert detect_signature(b"\xff\xd8\xffrest", ".jpg") == ("image", "jpeg")


def test_mp4_signature():
    header = b"\x00\x00\x00\x18ftypisom"
    assert detect_signature(header, ".mp4") == ("video", "isobmff:isom")


def test_extension_is_not_proof():
    assert detect_signature(b"not actually a png", ".png") == ("image", "unverified-extension")


def test_dng_is_identified_as_tiff_based():
    assert detect_signature(b"II*\x00rest", ".dng") == ("image", "dng-tiff")


def test_unknown_file():
    assert detect_signature(b"random bytes", ".bin") == ("unknown", "unknown")
