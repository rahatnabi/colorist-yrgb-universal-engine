"SMPTE timecode arithmetic with explicit frame-rate and drop-frame handling."
from __future__ import annotations
import re
from fractions import Fraction

_TIMECODE = re.compile(r"^(\d{2,}):(\d{2}):(\d{2})([:;])(\d{2})$")

def _rate(value: str | int | float | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        rate = value
    elif isinstance(value, int):
        rate = Fraction(value, 1)
    elif isinstance(value, float):
        rate = Fraction(str(value)).limit_denominator(100_000)
    else:
        numerator, separator, denominator = value.partition("/")
        rate = Fraction(int(numerator), int(denominator)) if separator else Fraction(int(numerator), 1)
    if rate <= 0:
        raise ValueError("Frame rate must be positive.")
    return rate

def _nominal_rate(rate: Fraction) -> int:
    return round(float(rate))

def parse_timecode(timecode: str, frame_rate: str | int | float | Fraction) -> int:
    """Convert a SMPTE label to a zero-based frame number."""
    match = _TIMECODE.fullmatch(timecode.strip())
    if not match:
        raise ValueError("Timecode must use HH:MM:SS:FF or HH:MM:SS;FF.")
    hours, minutes, seconds, separator, frames = match.groups()
    hh, mm, ss, ff = map(int, (hours, minutes, seconds, frames))
    if mm >= 60 or ss >= 60:
        raise ValueError("Minutes and seconds must be between 00 and 59.")
    rate = _rate(frame_rate)
    nominal = _nominal_rate(rate)
    if ff >= nominal:
        raise ValueError(f"Frame field must be between 00 and {nominal - 1:02d}.")
    total_minutes = hh * 60 + mm
    label_frames = ((hh * 3600 + mm * 60 + ss) * nominal) + ff
    if separator == ";":
        if rate == Fraction(30000, 1001):
            drop = 2
        elif rate == Fraction(60000, 1001):
            drop = 4
        else:
            raise ValueError("Drop-frame labels are supported only at 30000/1001 or 60000/1001 fps.")
        if mm % 10 != 0 and ss == 0 and ff < drop:
            raise ValueError("This drop-frame label is skipped at the start of the minute.")
        label_frames -= drop * (total_minutes - total_minutes // 10)
    return label_frames

def format_timecode(frame_number: int, frame_rate: str | int | float | Fraction, *, drop_frame: bool = False) -> str:
    """Format a zero-based frame number as a 24-hour SMPTE timecode label."""
    if not isinstance(frame_number, int) or isinstance(frame_number, bool) or frame_number < 0:
        raise ValueError("Frame number must be a non-negative integer.")
    rate = _rate(frame_rate)
    nominal = _nominal_rate(rate)
    frames = frame_number
    separator = ":"
    if drop_frame:
        if rate == Fraction(30000, 1001):
            drop = 2
        elif rate == Fraction(60000, 1001):
            drop = 4
        else:
            raise ValueError("Drop-frame labels are supported only at 30000/1001 or 60000/1001 fps.")
        frames_per_10_minutes = nominal * 600 - drop * 9
        frames_per_minute = nominal * 60 - drop
        blocks, remainder = divmod(frames, frames_per_10_minutes)
        frames += drop * 9 * blocks
        if remainder >= drop:
            frames += drop * ((remainder - drop) // frames_per_minute)
        separator = ";"
    frames %= nominal * 60 * 60 * 24
    ff = frames % nominal
    total_seconds = frames // nominal
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = (total_seconds // 3600) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}{separator}{ff:02d}"

def timecode_at_frame(start_timecode: str, frame_offset: int, frame_rate: str | int | float | Fraction) -> str:
    """Calculate a clip-relative timecode without changing the source label."""
    if not isinstance(frame_offset, int) or isinstance(frame_offset, bool):
        raise ValueError("Frame offset must be an integer.")
    target = parse_timecode(start_timecode, frame_rate) + frame_offset
    if target < 0:
        raise ValueError("Calculated timecode precedes frame zero.")
    return format_timecode(target, frame_rate, drop_frame=";" in start_timecode)
