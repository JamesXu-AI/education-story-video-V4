#!/usr/bin/env python3
"""Resolve Seed Master Route B tokens to current Seedance execution values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from pkgutil import extend_path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for script_root in (
    REPOSITORY_ROOT / "screenplay-writer" / "scripts",
    REPOSITORY_ROOT / "direct-production-design" / "scripts",
    REPOSITORY_ROOT / "virtual-production" / "scripts",
):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

import story_video  # noqa: E402

story_video.__path__ = extend_path(story_video.__path__, story_video.__name__)

from story_video.asset_catalog import load_asset_catalog  # noqa: E402
from story_video.seed_master_runtime import (  # noqa: E402
    CAPABILITY_PROFILE_RELATIVE,
    EXECUTION_PLAN_DIR_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    SeedMasterRuntimeError,
    build_execution_plan,
    parse_segment_script,
    read_json,
    storyboard_segment_rows,
    validate_source_identity,
    write_json,
)


def materialize(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    plan_rows = storyboard_segment_rows(task_dir)
    planned_ids = [str(item["segment_id"]) for item in plan_rows]
    if segment_ids is None:
        selected_ids = [
            segment_id
            for segment_id in planned_ids
            if (task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md").is_file()
        ]
        if not selected_ids:
            raise SeedMasterRuntimeError(
                "Seed Master has not produced any Route B segment-NNN.md Scripts"
            )
    else:
        if len(segment_ids) != len(set(segment_ids)):
            raise SeedMasterRuntimeError("--segments values must be unique")
        unknown = [item for item in segment_ids if item not in planned_ids]
        if unknown:
            raise SeedMasterRuntimeError(
                "Unknown --segments values: " + ", ".join(unknown)
            )
        selected_ids = segment_ids

    catalog = load_asset_catalog(task_dir)
    task = read_json(task_dir / "task.json", label="task.json")
    capability_profile = read_json(
        task_dir / CAPABILITY_PROFILE_RELATIVE,
        label="Seedance capability profile",
    )
    output_root = task_dir / EXECUTION_PLAN_DIR_RELATIVE
    outputs: list[str] = []
    for segment_id in selected_ids:
        script_path = task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md"
        parsed = parse_segment_script(script_path)
        validate_source_identity(task_dir, parsed)
        plan = build_execution_plan(
            task_dir=task_dir,
            parsed=parsed,
            catalog=catalog,
            capability_profile=capability_profile,
            task=task,
        )
        output_path = output_root / f"{segment_id}.json"
        write_json(output_path, plan)
        outputs.append(output_path.relative_to(task_dir).as_posix())
    return {
        "status": "PASS",
        "segment_count": len(outputs),
        "segments": selected_ids,
        "execution_plans": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--segments", nargs="+", metavar="SEGMENT_ID")
    args = parser.parse_args()
    try:
        result = materialize(args.task_dir, segment_ids=args.segments)
    except Exception as exc:
        print(
            json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2)
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
