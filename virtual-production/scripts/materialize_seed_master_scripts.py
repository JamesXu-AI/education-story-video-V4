#!/usr/bin/env python3
"""Resolve Seed Master Route B tokens to current Seedance execution values."""

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
    COMPILE_MANIFEST_RELATIVE,
    EXECUTION_PLAN_DIR_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    TRACE_RELATIVE,
    SeedMasterRuntimeError,
    build_execution_plan,
    manifest_segment_rows,
    parse_segment_script,
    read_json,
    sha256_file,
    validate_source_identity,
    write_json,
)


def _validate_trace(task_dir: Path) -> dict[str, Any]:
    trace = read_json(
        task_dir / TRACE_RELATIVE,
        label="Storyboard-to-Prompt trace",
    )
    storyboard_hash = sha256_file(
        task_dir / "previsualize-cinematography/storyboard.md"
    )
    manifest_hash = sha256_file(task_dir / COMPILE_MANIFEST_RELATIVE)
    semantic = trace.get("semantic_review")
    if (
        trace.get("schema_version") != "1.0"
        or trace.get("storyboard_sha256") != storyboard_hash
        or trace.get("source_manifest_sha256") != manifest_hash
        or not isinstance(semantic, dict)
        or semantic.get("overall_verdict") != "pass"
        or semantic.get("omitted_source_items") != []
        or semantic.get("duplicated_source_items") != []
        or semantic.get("unapproved_rewrites") != []
    ):
        raise SeedMasterRuntimeError(
            "Seed Master translation trace is missing, stale, or not semantically approved"
        )
    return trace


def _route_value_matches(field: str, route_a: Any, route_b: Any) -> bool:
    """Treat manifest boolean literals and YAML booleans as one semantic value."""

    if field == "camera_ensemble_color_resynthesis_allowed":
        normalized = {
            True: "true",
            False: "false",
        }
        return normalized.get(route_a, route_a) == normalized.get(route_b, route_b)
    return route_a == route_b


def materialize(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    _validate_trace(task_dir)
    manifest_rows = manifest_segment_rows(task_dir)
    manifest_ids = [str(item["segment_id"]) for item in manifest_rows]
    if segment_ids is None:
        selected_ids = [
            segment_id
            for segment_id in manifest_ids
            if (task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md").is_file()
        ]
        if not selected_ids:
            raise SeedMasterRuntimeError(
                "Seed Master has not produced any Route B segment-NNN.md Scripts"
            )
    else:
        if len(segment_ids) != len(set(segment_ids)):
            raise SeedMasterRuntimeError("--segments values must be unique")
        unknown = [item for item in segment_ids if item not in manifest_ids]
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
    row_by_id = {str(item["segment_id"]): item for item in manifest_rows}
    output_root = task_dir / EXECUTION_PLAN_DIR_RELATIVE
    outputs: list[str] = []
    for segment_id in selected_ids:
        script_path = task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md"
        parsed = parse_segment_script(script_path)
        validate_source_identity(task_dir, parsed)
        manifest_row = row_by_id[segment_id]
        metadata = parsed["metadata"]
        comparisons = {
            "scene_ids": metadata["scene_ids"],
            "target_duration_seconds": parsed["duration"],
            "operation": metadata["operation"],
            "seam_class": metadata["seam_class"],
            "editorial_intent": metadata["editorial_intent"],
            "schedule_mode": metadata["schedule_mode"],
            "planned_wave": metadata["planned_wave"],
            "depends_on_segment_ids": metadata["depends_on_segment_ids"],
            "predecessor_review_required": metadata["predecessor_review_required"],
            "required_predecessor_evidence": metadata[
                "required_predecessor_evidence"
            ],
            "reference_video_scope": metadata["reference_video_scope"],
            "reference_video_audio": metadata["reference_video_audio"],
            "camera_ensemble_color_resynthesis_allowed": metadata[
                "camera_ensemble_color_resynthesis_allowed"
            ],
            "successor_recompile_required": metadata[
                "successor_recompile_required"
            ],
        }
        mismatches = [
            field
            for field, value in comparisons.items()
            if not _route_value_matches(field, manifest_row.get(field), value)
        ]
        if mismatches:
            raise SeedMasterRuntimeError(
                f"{segment_id} Route B shooting plan differs from Route A: "
                + ", ".join(mismatches)
            )
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
        plan["asset_compatibility"] = validate_compatibility_review(
            task_dir=task_dir,
            parsed=parsed,
            provisional_plan=plan,
            catalog=catalog,
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
