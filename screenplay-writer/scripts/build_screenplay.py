#!/usr/bin/env python3
"""Build or check the formal package directly from screenplay.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "screenplay-writer" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compile_audio_timeline import (  # noqa: E402
    build_audio_timeline,
    validate_audio_timeline,
)
from story_video.character_performance_map import (  # noqa: E402
    load_character_performance_map,
)
from story_video.runtime_support import StoryVideoError  # noqa: E402
from story_video.screenplay_contract import load_screenplay_file  # noqa: E402
from story_video.task_paths import task_root, validate_root_files  # noqa: E402
from task_input import load_task_json  # noqa: E402


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _require_nonempty_text(path: Path, label: str) -> None:
    try:
        value = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StoryVideoError(f"Missing {label}: {path}") from exc
    except UnicodeDecodeError as exc:
        raise StoryVideoError(f"{label} must be valid UTF-8: {path}") from exc
    if not value.strip():
        raise StoryVideoError(f"{label} must not be empty: {path}")


def _authorities(task_dir: Path) -> tuple[Path, dict[str, Any]]:
    root = task_root(task_dir)
    validate_root_files(root)
    task = load_task_json(root / "task.json")
    _require_nonempty_text(root / "story.md", "story.md")
    _require_nonempty_text(
        root / "screenplay-writer" / "story-treatment.md", "story-treatment.md"
    )
    screenplay_path = root / "screenplay-writer" / "screenplay.md"
    screenplay = load_screenplay_file(screenplay_path)
    if screenplay["screenplay_title_en"] != task["title"]:
        raise StoryVideoError("screenplay.md title conflicts with task.json title")
    if screenplay["target_age_band"] != task["target_age_band"]:
        raise StoryVideoError(
            "screenplay.md target age band conflicts with task.json"
        )
    return screenplay_path, screenplay


def build_or_check(task_dir: Path, *, check_only: bool) -> dict[str, Any]:
    root = task_root(task_dir)
    screenplay_path, screenplay = _authorities(root)
    output_root = root / "screenplay-writer"
    audio_path = output_root / "audio-timeline.json"

    audio = build_audio_timeline(screenplay_path)
    audio_validation = validate_audio_timeline(
        audio, screenplay_path=screenplay_path
    )

    expected = {
        audio_path: _json_bytes(audio),
    }
    if check_only:
        for path, data in expected.items():
            if not path.is_file() or path.read_bytes() != data:
                raise StoryVideoError(
                    f"{path.name} differs from the current screenplay.md projection"
                )
    else:
        for path, data in expected.items():
            _atomic_write(path, data)

    performance_map = load_character_performance_map(root)
    segments = screenplay["segments"]
    return {
        "status": "PASS",
        "mode": "check" if check_only else "build",
        "screenplay": str(screenplay_path),
        "segment_count": len(segments),
        "planned_runtime_seconds": sum(
            item["story_plan"]["estimated_duration_seconds"] for item in segments
        ),
        "dialogue_cue_count": audio_validation["dialogue_cue_count"],
        "performance_entity_count": len(
            performance_map["performance_entities"]
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "check"):
        child = commands.add_parser(command)
        child.add_argument("--task-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_or_check(
            args.task_dir, check_only=args.command == "check"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
