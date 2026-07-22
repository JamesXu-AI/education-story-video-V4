"""Minimal visual-profile identity and prohibited shortcut validation."""

from __future__ import annotations

import re
from typing import Any


VISUAL_STYLE_PROFILE = "soft_cute_3d_healing_animation"

# Provider prompts carry their complete model-authored style section. This module
# intentionally contains no prose blocks that Python could prepend or append.
PROHIBITED_STYLE_SHORTCUT_RE = re.compile(
    r"\b(?:pixar|disney|dreamworks|illumination|ghibli|unreal engine|octane render)\b",
    re.IGNORECASE,
)


def contains_prohibited_style_shortcut(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PROHIBITED_STYLE_SHORTCUT_RE.search(value))
    if isinstance(value, dict):
        return any(contains_prohibited_style_shortcut(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_prohibited_style_shortcut(item) for item in value)
    return False
