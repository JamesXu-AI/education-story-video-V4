"""Production-design validation helpers shared by its asset tools."""

from __future__ import annotations

from typing import Any


class StoryVideoError(RuntimeError):
    """Raised when current production-design inputs or assets are invalid."""


def require_utf8_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoryVideoError(f"{field} must be non-empty UTF-8 text.")
    normalized = value.strip()
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise StoryVideoError(f"{field} must be valid UTF-8 text.") from exc
    return normalized
