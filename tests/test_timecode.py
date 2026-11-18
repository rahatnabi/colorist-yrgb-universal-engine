from fractions import Fraction
import pytest
from yrgb_engine.timecode import format_timecode, parse_timecode, timecode_at_frame

def test_25fps_frame_offsets_match_expected_labels():
    assert timecode_at_frame("00:12:47:08", 48, 25) == "00:12:49:06"
    assert timecode_at_frame("00:12:47:08", 96, 25) == "00:12:51:04"
    assert timecode_at_frame("00:12:47:08", 191, 25) == "00:12:54:24"

def test_non_drop_round_trip():
    for frame in (0, 1, 24, 25, 1799, 90000, 2_000_000):
        assert parse_timecode(format_timecode(frame, 25), 25) == frame

def test_drop_frame_round_trip_at_2997():
    rate = Fraction(30000, 1001)
    for frame in (0, 1798, 17982, 107892, 1_000_000):
        label = format_timecode(frame, rate, drop_frame=True)
        assert ";" in label
        assert parse_timecode(label, rate) == frame

def test_drop_frame_rejects_skipped_labels():
    with pytest.raises(ValueError, match="skipped"):
        parse_timecode("00:01:00;00", Fraction(30000, 1001))

def test_drop_frame_rejects_unsupported_rate():
    with pytest.raises(ValueError, match="supported only"):
        parse_timecode("00:00:01;00", 25)

def test_invalid_fields_are_rejected():
    with pytest.raises(ValueError):
        parse_timecode("00:60:00:00", 25)
    with pytest.raises(ValueError):
        parse_timecode("00:00:00:25", 25)

def test_negative_offsets_are_supported_when_result_remains_nonnegative():
    assert timecode_at_frame("00:00:01:00", -10, 25) == "00:00:00:15"
    with pytest.raises(ValueError, match="precedes"):
        timecode_at_frame("00:00:00:00", -1, 25)
