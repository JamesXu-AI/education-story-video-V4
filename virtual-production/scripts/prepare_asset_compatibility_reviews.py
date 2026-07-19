#!/usr/bin/env python3
"""Freeze final Prompts and assets.json semantics for compatibility review."""

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
    build_review_packet,
    emit_resolution_rework,
    write_review_draft,
    write_review_packet,
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


def prepare(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    manifest_ids = [
        str(row["segment_id"]) for row in manifest_segment_rows(task_dir)
    ]
    if segment_ids is None:
        selected = [
            segment_id
            for segment_id in manifest_ids
            if (task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md").is_file()
        ]
    else:
        if not segment_ids or len(segment_ids) != len(set(segment_ids)):
            raise SeedMasterRuntimeError("--segments values must be unique")
        unknown = sorted(set(segment_ids) - set(manifest_ids))
        if unknown:
            raise SeedMasterRuntimeError(
                "Unknown --segments values: " + ", ".join(unknown)
            )
        selected = segment_ids
    if not selected:
        raise SeedMasterRuntimeError("No current Route B Scripts are available")
    catalog = load_asset_catalog(task_dir)
    capability_profile = read_json(
        task_dir / CAPABILITY_PROFILE_RELATIVE,
        label="Seedance capability profile",
    )
    task = read_json(task_dir / "task.json", label="task.json")
    packets: list[str] = []
    reviews: list[str] = []
    failures: list[dict[str, str]] = []
    for segment_id in selected:
        parsed = parse_segment_script(
            task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md"
        )
        try:
            validate_source_identity(task_dir, parsed)
            provisional_plan = build_execution_plan(
                task_dir=task_dir,
                parsed=parsed,
                catalog=catalog,
                capability_profile=capability_profile,
                task=task,
            )
            packet = build_review_packet(
                task_dir=task_dir,
                parsed=parsed,
                provisional_plan=provisional_plan,
                catalog=catalog,
            )
            path = write_review_packet(task_dir, packet)
            packets.append(path.relative_to(task_dir).as_posix())
            draft = write_review_draft(task_dir, packet, packet_file=path)
            reviews.append(draft.relative_to(task_dir).as_posix())
        except Exception as exc:
            rework = emit_resolution_rework(
                task_dir=task_dir,
                parsed=parsed,
                error=exc,
            )
            failures.append(
                {
                    "segment_id": segment_id,
                    "error": str(exc),
                    "rework_request": rework.relative_to(task_dir).as_posix(),
                }
            )
    if failures:
        raise SeedMasterRuntimeError(
            "Asset compatibility preparation failed: "
            + " | ".join(
                f"{row['segment_id']}: {row['error']}" for row in failures
            )
        )
    return {
        "status": "REVIEW_REQUIRED",
        "segments": selected,
        "packet_count": len(packets),
        "review_packets": packets,
        "review_files": reviews,
        "next_gate": "compare every final Prompt binding with assets.json and author one prompt-assets-json-compatibility-review-v2 per Segment",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--segments", nargs="+", metavar="SEGMENT_ID")
    args = parser.parse_args()
    try:
        result = prepare(args.task_dir, segment_ids=args.segments)
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
