"""Numbered image-sequence discovery for frame-based media workflows."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

@dataclass(slots=True)
class ImageSequence:
    pattern: str
    frames: list[tuple[int, Path]]
    missing_indices: list[int]

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def start_index(self) -> int | None:
        return self.frames[0][0] if self.frames else None

    @property
    def end_index(self) -> int | None:
        return self.frames[-1][0] if self.frames else None

    def frame_path(self, index: int) -> Path:
        for frame_index, path in self.frames:
            if frame_index == index:
                return path
        raise KeyError(f"Frame index {index} is not present in this sequence.")

def _pattern_regex(pattern: str) -> tuple[re.Pattern[str], int]:
    path = Path(pattern)
    name = path.name
    match = re.search(r"%(0?)(\d*)d", name)
    if match:
        width = int(match.group(2) or 0)
        token = match.group(0)
    else:
        hash_match = re.search(r"#+", name)
        if not hash_match:
            raise ValueError("Sequence pattern must contain a %0Nd or #### frame token.")
        width = len(hash_match.group(0))
        token = hash_match.group(0)
    replacement = rf"(\d{{{width}}})" if width else r"(\d+)"
    escaped = re.escape(name).replace(re.escape(token), replacement)
    return re.compile(rf"^{escaped}$"), width

def discover_image_sequence(pattern: str | Path) -> ImageSequence:
    """Find matching sibling frames and report gaps without decoding them."""
    pattern_text = str(pattern)
    pattern_path = Path(pattern_text).expanduser()
    regex, _ = _pattern_regex(pattern_path)
    parent = pattern_path.parent if str(pattern_path.parent) else Path(".")
    if not parent.is_dir():
        return ImageSequence(pattern_text, [], [])

    frames: list[tuple[int, Path]] = []
    for candidate in parent.iterdir():
        match = regex.match(candidate.name)
        if match and candidate.is_file():
            frames.append((int(match.group(1)), candidate))
    frames.sort(key=lambda item: item[0])

    missing: list[int] = []
    if frames:
        present = {index for index, _ in frames}
        missing = [index for index in range(frames[0][0], frames[-1][0] + 1) if index not in present]
    return ImageSequence(pattern_text, frames, missing)
