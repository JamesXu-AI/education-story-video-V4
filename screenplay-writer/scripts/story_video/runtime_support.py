"""Screenplay-owned task input and text validation helpers."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
TARGET_AGE_BANDS = frozenset(
    {"preschool_3_4", "younger_5_8", "older_9_12", "teen_13_16"}
)
LABEL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
VIDEO_RESOLUTIONS = frozenset({"480p", "720p", "1080p", "4k"})


class StoryVideoError(RuntimeError):
    """Raised when current screenplay inputs or outputs are invalid."""


def require_utf8_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoryVideoError(f"{field} must be non-empty UTF-8 text.")
    normalized = value.strip()
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise StoryVideoError(f"{field} must be valid UTF-8 text.") from exc
    return normalized


def normalize_video_resolution(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VIDEO_RESOLUTIONS:
        raise StoryVideoError("Resolution must be 480p, 720p, 1080p, or 4k.")
    return normalized


def fixed_prompt_path(owner: str, filename: str) -> Path:
    if owner != "screenplay":
        raise StoryVideoError(f"Unsupported fixed Prompt owner: {owner}")
    path = WORKSPACE_ROOT / "screenplay-writer" / "references" / "prompts" / filename
    if not path.is_file():
        raise StoryVideoError(f"Missing fixed Prompt: {path}")
    return path.resolve()
