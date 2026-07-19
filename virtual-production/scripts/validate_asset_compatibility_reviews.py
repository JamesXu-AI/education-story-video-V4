#!/usr/bin/env python3
"""Validate final Seedance Prompts against exact inspected real provider inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from pkgutil import extend_path
import sys
from typing import Any


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
from story_video.asset_compatibility import (  # noqa: E402
    emit_resolution_rework,
    validate_compatibility_review,
)
from story_video.seed_master_runtime import (  # noqa: E402
    CAPABILITY_PROFILE_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    SeedMasterRuntimeError,
    build_execution_plan,
    manifest_segment_rows,
    parse_segment_script,
    read_json,
    validate_source_identity,
)


def validate(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    all_ids = [str(row["segment_id"]) for row in manifest_segment_rows(task_dir)]
    selected = all_ids if segment_ids is None else segment_ids
    if not selected or len(selected) != len(set(selected)):
        raise SeedMasterRuntimeError("Selected Segment IDs must be unique")
    unknown = sorted(set(selected) - set(all_ids))
    if unknown:
        raise SeedMasterRuntimeError(
            "Unknown --segments values: " + ", ".join(unknown)
        )
    catalog = load_asset_catalog(task_dir)
    capability_profile = read_json(
        task_dir / CAPABILITY_PROFILE_RELATIVE,
        label="Seedance capability profile",
    )
    task = read_json(task_dir / "task.json", label="task.json")
    receipts: list[dict[str, Any]] = []
    for segment_id in selected:
        parsed = parse_segment_script(
            task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md"
        )
        validate_source_identity(task_dir, parsed)
        try:
            plan = build_execution_plan(
                task_dir=task_dir,
                parsed=parsed,
                catalog=catalog,
                capability_profile=capability_profile,
                task=task,
            )
        except Exception as exc:
            rework = emit_resolution_rework(
                task_dir=task_dir,
                parsed=parsed,
                error=exc,
            )
            raise SeedMasterRuntimeError(
                f"{segment_id} cannot resolve compatible assets.json semantics; "
                f"rework request: {rework}"
            ) from exc
        receipt = validate_compatibility_review(
            task_dir=task_dir,
            parsed=parsed,
            provisional_plan=plan,
            catalog=catalog,
        )
        receipts.append(
            {
                "segment_id": segment_id,
                "review_sha256": receipt["review_sha256"],
                "semantic_input_fingerprint": receipt[
                    "semantic_input_fingerprint"
                ],
            }
        )
    return {
        "status": "PASS",
        "segment_count": len(selected),
        "segments": selected,
        "receipts": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--segments", nargs="+", metavar="SEGMENT_ID")
    args = parser.parse_args()
    try:
        result = validate(args.task_dir, segment_ids=args.segments)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
