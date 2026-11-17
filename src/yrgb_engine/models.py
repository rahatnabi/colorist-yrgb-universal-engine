"""Typed result models for media inspection."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MediaProbeResult:
    path: str
    exists: bool
    size_bytes: int | None = None
    detected_type: str = "unknown"
    extension: str = ""
    signature: str = "unknown"
    status: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)
