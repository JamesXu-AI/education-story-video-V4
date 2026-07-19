#!/usr/bin/env python3
"""Extract the translated English story-generation input from task.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from story_video.runtime_support import (  # noqa: E402
    LABEL_RE,
    StoryVideoError,
    TARGET_AGE_BANDS,
    fixed_prompt_path,
    normalize_video_resolution,
    require_utf8_text,
)


STORY_PROMPT_FILENAME = "story_gen.md"
TASK_METADATA_FIELDS = {
    "task_id",
    "title",
    "country_en",
    "source_input",
    "input",
    "source_context",
    "translation",
    "voice_audio_source",
    "dialogue_source",
    "target_age_band",
    "created_at",
    "updated_at",
}
TASK_INPUT_FIELDS = {"resolution", "aspect_ratio", "title", "content"}
ASPECT_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"}
TASK_SOURCE_CONTEXT_FIELDS = {
    "source_language_en",
    "cultural_context_en",
    "cultural_invariants_en",
}
TASK_TRANSLATION_FIELDS = {"prompt_path", "output_language"}
CURRENT_VOICE_AUDIO_SOURCE = "speaker_reference_audio"
CURRENT_DIALOGUE_SOURCE = "seedance"
COUNTRY_EN_RE = re.compile(r"^[A-Za-z][A-Za-z .&'()-]{1,79}$")


def validate_country_en(value: Any, context: str = "task.json country_en") -> str:
    country_en = require_utf8_text(value, context)
    if not COUNTRY_EN_RE.fullmatch(country_en):
        raise StoryVideoError(
            f"{context} must be one English country name using Latin letters."
        )
    return country_en


def story_input_script_path() -> Path:
    return Path(__file__).resolve()


def fixed_story_prompt() -> tuple[Path, str]:
    path = fixed_prompt_path("screenplay", STORY_PROMPT_FILENAME)
    try:
        prompt = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoryVideoError(f"Cannot read fixed story Prompt: {path}") from exc
    if "# Complete Story Generation Prompt" not in prompt:
        raise StoryVideoError(f"Invalid fixed story Prompt: {path}")
    return path, prompt


def validate_task_metadata(
    payload: Any,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the only task.json contract accepted by every workflow entry point."""
    context = str(Path(path).expanduser().resolve()) if path is not None else "task.json"
    if not isinstance(payload, dict) or not TASK_METADATA_FIELDS <= set(payload):
        raise StoryVideoError(
            f"Task metadata is missing required story fields: {context}"
        )

    task_id = require_utf8_text(payload.get("task_id"), "task.json task_id")
    if not LABEL_RE.fullmatch(task_id):
        raise StoryVideoError(f"task.json task_id must match {LABEL_RE.pattern}.")
    require_utf8_text(payload.get("title"), "task.json title")
    validate_country_en(payload.get("country_en"))
    require_utf8_text(payload.get("created_at"), "task.json created_at")
    require_utf8_text(payload.get("updated_at"), "task.json updated_at")

    for field_name in ("source_input", "input"):
        task_input = payload.get(field_name)
        if not isinstance(task_input, dict) or set(task_input) != TASK_INPUT_FIELDS:
            raise StoryVideoError(
                f"task.json {field_name} must contain exactly resolution, aspect_ratio, title, and content."
            )
        try:
            normalize_video_resolution(task_input.get("resolution"))
        except StoryVideoError as exc:
            raise StoryVideoError(
                f"task.json {field_name}.resolution is invalid: {exc}"
            ) from exc
        require_utf8_text(task_input.get("title"), f"task.json {field_name}.title")
        require_utf8_text(task_input.get("content"), f"task.json {field_name}.content")
        if task_input.get("aspect_ratio") not in ASPECT_RATIOS:
            raise StoryVideoError(
                f"task.json {field_name}.aspect_ratio must be one of: "
                + ", ".join(sorted(ASPECT_RATIOS))
            )

    source_context = payload.get("source_context")
    if (
        not isinstance(source_context, dict)
        or set(source_context) != TASK_SOURCE_CONTEXT_FIELDS
    ):
        raise StoryVideoError(
            "task.json source_context must contain exactly source_language_en, "
            "cultural_context_en, and cultural_invariants_en."
        )
    require_utf8_text(
        source_context.get("source_language_en"),
        "task.json source_context.source_language_en",
    )
    require_utf8_text(
        source_context.get("cultural_context_en"),
        "task.json source_context.cultural_context_en",
    )
    invariants = source_context.get("cultural_invariants_en")
    if not isinstance(invariants, list) or any(
        not isinstance(item, str) or not item.strip() for item in invariants
    ):
        raise StoryVideoError(
            "task.json source_context.cultural_invariants_en must be a list of non-empty strings."
        )

    translation = payload.get("translation")
    if not isinstance(translation, dict) or set(translation) != TASK_TRANSLATION_FIELDS:
        raise StoryVideoError(
            "task.json translation must contain exactly prompt_path and output_language."
        )
    require_utf8_text(
        translation.get("prompt_path"), "task.json translation.prompt_path"
    )
    if translation.get("output_language") != "English":
        raise StoryVideoError(
            "task.json translation.output_language must be English before story generation."
        )

    if payload.get("voice_audio_source") != CURRENT_VOICE_AUDIO_SOURCE:
        raise StoryVideoError(
            "task.json voice_audio_source must currently be speaker_reference_audio."
        )
    if payload.get("dialogue_source") != CURRENT_DIALOGUE_SOURCE:
        raise StoryVideoError(
            "task.json dialogue_source must currently be seedance."
        )
    target_age_band = payload.get("target_age_band")
    if not isinstance(target_age_band, str) or target_age_band not in TARGET_AGE_BANDS:
        raise StoryVideoError(
            "task.json target_age_band must be one of: "
            + ", ".join(sorted(TARGET_AGE_BANDS))
        )
    return payload


def load_task_json(path: str | Path) -> dict[str, Any]:
    task_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(task_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoryVideoError(f"Task JSON not found: {task_path}") from exc
    except UnicodeDecodeError as exc:
        raise StoryVideoError(f"Task JSON must be valid UTF-8: {task_path}") from exc
    except json.JSONDecodeError as exc:
        raise StoryVideoError(f"Task JSON is invalid: {task_path}: {exc}") from exc
    return validate_task_metadata(payload, path=task_path)


def extract_story_input(path: str | Path) -> dict[str, str]:
    """Return the exact three inputs owned by story_gen.md."""
    task = load_task_json(path)
    task_input = task.get("input")
    if not isinstance(task_input, dict):
        raise StoryVideoError("task.json input must be a JSON object.")

    translation = task.get("translation")
    if not isinstance(translation, dict) or translation.get("output_language") != "English":
        raise StoryVideoError(
            "task.json translation.output_language must be English before story generation."
        )

    target_age_band = task.get("target_age_band")
    if not isinstance(target_age_band, str) or target_age_band not in TARGET_AGE_BANDS:
        raise StoryVideoError(
            "task.json target_age_band must be one of: "
            + ", ".join(sorted(TARGET_AGE_BANDS))
        )

    return {
        "title_en": require_utf8_text(task_input.get("title"), "task.json input.title"),
        "content_en": require_utf8_text(
            task_input.get("content"), "task.json input.content"
        ),
        "target_age_band": str(target_age_band),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract translated English story input from task.json."
    )
    parser.add_argument("--task-json", required=True, help="Path to the current task.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(
            json.dumps(
                extract_story_input(args.task_json),
                ensure_ascii=False,
                indent=2,
            )
        )
    except StoryVideoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
