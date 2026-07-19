#!/usr/bin/env python3
"""Validate the screenplay-owned Scene/Segment character performance map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for script_root in (REPOSITORY_ROOT / "screenplay-writer" / "scripts",):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

from story_video.character_performance_map import (  # noqa: E402
    MAP_RELATIVE_PATH,
    load_character_performance_map,
    role_asset_scope_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        value = load_character_performance_map(args.task_dir)
        scope = role_asset_scope_gate(args.task_dir)
        result = {
            "status": "PASS",
            "path": str(args.task_dir.expanduser().resolve() / MAP_RELATIVE_PATH),
            "entity_count": len(value["performance_entities"]),
            "segment_count": len(value["scene_segment_calls"]),
            "role_asset_scope_gate": scope["status"],
            "image_asset_generation": scope["image_asset_generation"],
            "detailed_screenplay_review": scope["detailed_screenplay_review"],
        }
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
