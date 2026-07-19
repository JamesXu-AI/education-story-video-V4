#!/usr/bin/env python3
"""Run the fast role/image-scope gate that unlocks parallel asset generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "screenplay-writer" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from story_video.character_performance_map import role_asset_scope_gate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = role_asset_scope_gate(args.task_dir)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "contract": "role-asset-scope-gate/v1",
                    "status": "FAIL",
                    "image_asset_generation": "BLOCKED",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
