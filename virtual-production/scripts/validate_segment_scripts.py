#!/usr/bin/env python3
"""Validate Seed Master Route B Scripts and their materialized execution plans."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from pkgutil import extend_path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
DESIGN_SCRIPT_ROOT = REPOSITORY_ROOT / "direct-production-design" / "scripts"
for script_root in (SCRIPT_ROOT, DESIGN_SCRIPT_ROOT):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

import story_video  # noqa: E402

story_video.__path__ = extend_path(story_video.__path__, story_video.__name__)

from story_video.asset_catalog import load_asset_catalog  # noqa: E402
from story_video.asset_compatibility import (  # noqa: E402
    RECEIPT_CONTRACT,
    validate_compatibility_review,
)
from story_video.seed_master_runtime import (  # noqa: E402
    CAPABILITY_PROFILE_RELATIVE,
    EXECUTION_PLAN_DIR_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    TRACE_RELATIVE,
    SeedMasterRuntimeError,
    build_execution_plan,
    load_execution_plan,
    manifest_segment_rows,
    parse_segment_script,
    read_json,
    sha256_file,
    token_sort_key,
    validate_source_identity,
)
from route_b_handoff import load_route_b_handoff  # noqa: E402


def _validate_trace(task_dir: Path) -> None:
    trace = read_json(task_dir / TRACE_RELATIVE, label="Storyboard-to-Prompt trace")
    semantic = trace.get("semantic_review")
    if (
        trace.get("storyboard_sha256")
        != sha256_file(task_dir / "previsualize-cinematography/storyboard.md")
        or trace.get("source_manifest_sha256")
        != sha256_file(
            task_dir
            / "previsualize-cinematography/storyboard-compile-manifest.json"
        )
        or not isinstance(semantic, dict)
        or semantic.get("overall_verdict") != "pass"
        or semantic.get("omitted_source_items") != []
        or semantic.get("duplicated_source_items") != []
        or semantic.get("unapproved_rewrites") != []
    ):
        raise SeedMasterRuntimeError("Storyboard-to-Prompt trace is stale or incomplete")


def _validate_full_trace_coverage(task_dir: Path) -> None:
    manifest = read_json(
        task_dir
        / "previsualize-cinematography/storyboard-compile-manifest.json",
        label="Storyboard compile manifest",
    )
    trace = read_json(task_dir / TRACE_RELATIVE, label="Storyboard-to-Prompt trace")
    expected: set[tuple[str, str]] = set()
    for key, source_type, id_field in (
        ("segments", "segment", "segment_id"),
        ("shots", "shot", "shot_id"),
        ("lines", "line", "line_id"),
        ("beats", "beat", "beat_id"),
        ("requirements", "requirement", "requirement_id"),
    ):
        rows = manifest.get(key)
        if not isinstance(rows, list):
            raise SeedMasterRuntimeError(f"Storyboard compile manifest lacks {key}")
        for row in rows:
            source_id = row.get(id_field) if isinstance(row, dict) else None
            if not isinstance(source_id, str) or not source_id:
                raise SeedMasterRuntimeError(
                    f"Storyboard compile manifest has an invalid {source_type} ID"
                )
            expected.add((source_type, source_id))
    mappings = trace.get("mappings")
    if not isinstance(mappings, list):
        raise SeedMasterRuntimeError("Storyboard-to-Prompt trace has no mappings")
    actual = [
        (row.get("source_type"), row.get("source_id"))
        for row in mappings
        if isinstance(row, dict)
    ]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise SeedMasterRuntimeError(
            "Storyboard-to-Prompt trace coverage is omitted, duplicated, or extraneous"
        )


def _validate_execution_plan(
    task_dir: Path, parsed: dict[str, Any], plan: dict[str, Any]
) -> None:
    segment_id = parsed["segment_id"]
    if (
        plan.get("source_script_sha256") != parsed["script_sha256"]
        or plan.get("source_storyboard_sha256")
        != parsed["metadata"]["source_storyboard_sha256"]
        or plan.get("source_manifest_sha256")
        != parsed["metadata"]["source_manifest_sha256"]
    ):
        raise SeedMasterRuntimeError(f"{segment_id} execution plan is stale")
    shooting = plan.get("shooting_plan")
    if not isinstance(shooting, dict):
        raise SeedMasterRuntimeError(f"{segment_id} execution plan lacks shooting_plan")
    for field in (
        "shooting_plan_status",
        "schedule_mode",
        "planned_wave",
        "depends_on_segment_ids",
        "required_predecessor_evidence",
        "operation",
        "seam_class",
        "editorial_intent",
        "reference_video_scope",
        "reference_video_audio",
    ):
        if shooting.get(field) != parsed["metadata"].get(field):
            raise SeedMasterRuntimeError(
                f"{segment_id} execution plan changes shooting-plan field {field}"
            )
    parameters = plan.get("seedance_parameters")
    if not isinstance(parameters, dict) or parameters.get("duration") != parsed["duration"]:
        raise SeedMasterRuntimeError(f"{segment_id} execution parameters are invalid")
    fixed = {
        "generate_audio": True,
        "watermark": False,
        "return_last_frame": True,
        "execution_expires_after": 172800,
        "priority": 0,
    }
    if any(parameters.get(key) != value for key, value in fixed.items()):
        raise SeedMasterRuntimeError(f"{segment_id} changes fixed Seedance values")
    media = plan.get("media_bindings")
    if not isinstance(media, list):
        raise SeedMasterRuntimeError(f"{segment_id} media_bindings must be an array")
    tokens = [item.get("provider_token") for item in media if isinstance(item, dict)]
    expected_tokens = sorted(
        set(item["provider_token"] for item in parsed["bindings"]),
        key=token_sort_key,
    )
    if tokens != expected_tokens:
        raise SeedMasterRuntimeError(
            f"{segment_id} execution media does not exactly replace Prompt tokens"
        )
    if any(
        item.get("source_kind") == "asset_catalog"
        and not str(item.get("uri") or "").startswith(("https://", "http://"))
        for item in media
    ):
        raise SeedMasterRuntimeError(f"{segment_id} has an unresolved asset URL")
    source_attempts = {
        item.get("source_provider_attempt_id")
        for item in media
        if isinstance(item, dict) and item.get("source_kind") != "asset_catalog"
    }
    if len(source_attempts) > 1:
        raise SeedMasterRuntimeError(f"{segment_id} mixes predecessor provider attempts")
    if source_attempts:
        dependency = parsed["metadata"]["depends_on_segment_ids"][0]
        record = read_json(
            task_dir
            / ".pending/virtual-production/generation-segments"
            / dependency
            / "production-record.json",
            label="predecessor production record",
        )
        if record.get("provider_attempt_id") not in source_attempts:
            raise SeedMasterRuntimeError(
                f"{segment_id} is not locked to the current predecessor attempt"
            )
    compatibility = plan.get("asset_compatibility")
    if (
        not isinstance(compatibility, dict)
        or compatibility.get("contract")
        != RECEIPT_CONTRACT
        or compatibility.get("overall_verdict") != "PASS"
        or compatibility.get("final_prompt_sha256")
        != hashlib.sha256(parsed["prompt"].encode("utf-8")).hexdigest()
    ):
        raise SeedMasterRuntimeError(
            f"{segment_id} lacks a current final-Prompt/assets.json semantic compatibility PASS"
        )


def validate_task(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    _validate_trace(task_dir)
    manifest_rows = manifest_segment_rows(task_dir)
    all_ids = [str(item["segment_id"]) for item in manifest_rows]
    if segment_ids is None:
        selected = all_ids
    else:
        if not segment_ids or len(segment_ids) != len(set(segment_ids)):
            raise SeedMasterRuntimeError("Selected Segment IDs must be unique")
        if any(item not in all_ids for item in segment_ids):
            raise SeedMasterRuntimeError("Selected Segment IDs are not in the Storyboard manifest")
        selected = segment_ids
    script_root = task_dir / SCRIPT_DIR_RELATIVE
    plan_root = task_dir / EXECUTION_PLAN_DIR_RELATIVE
    catalog = load_asset_catalog(task_dir)
    task = read_json(task_dir / "task.json", label="task.json")
    capability_profile = read_json(
        task_dir / CAPABILITY_PROFILE_RELATIVE,
        label="Seedance capability profile",
    )
    if segment_ids is None:
        actual_scripts = sorted(path.stem for path in script_root.glob("segment-*.md"))
        actual_plans = sorted(path.stem for path in plan_root.glob("segment-*.json"))
        if actual_scripts != all_ids or actual_plans != all_ids:
            raise SeedMasterRuntimeError(
                "Complete Route B Script/execution-plan coverage differs from the Storyboard manifest"
            )
    total_duration = 0
    parsed_by_id: dict[str, dict[str, Any]] = {}
    for segment_id in selected:
        parsed = parse_segment_script(script_root / f"{segment_id}.md")
        validate_source_identity(task_dir, parsed)
        plan = load_execution_plan(task_dir, segment_id)
        _validate_execution_plan(task_dir, parsed, plan)
        expected_plan = build_execution_plan(
            task_dir=task_dir,
            parsed=parsed,
            catalog=catalog,
            capability_profile=capability_profile,
            task=task,
        )
        expected_plan["asset_compatibility"] = validate_compatibility_review(
            task_dir=task_dir,
            parsed=parsed,
            provisional_plan=expected_plan,
            catalog=catalog,
        )
        if plan != expected_plan:
            raise SeedMasterRuntimeError(
                f"{segment_id} execution plan does not contain current asset/provider values"
            )
        parsed_by_id[segment_id] = parsed
        total_duration += parsed["duration"]
    if segment_ids is None and total_duration > 240:
        raise SeedMasterRuntimeError("Complete Seedance source-video duration exceeds 240s")
    if segment_ids is None:
        _validate_full_trace_coverage(task_dir)
        wave_by_id: dict[str, int] = {}
        for index, segment_id in enumerate(all_ids):
            metadata = parsed_by_id[segment_id]["metadata"]
            dependencies = metadata["depends_on_segment_ids"]
            if any(
                dependency not in wave_by_id
                or all_ids.index(dependency) >= index
                for dependency in dependencies
            ):
                raise SeedMasterRuntimeError(
                    f"{segment_id} has a forward, missing, or cyclic shooting-plan dependency"
                )
            expected_wave = (
                0
                if not dependencies
                else 1 + max(wave_by_id[item] for item in dependencies)
            )
            if metadata["planned_wave"] != expected_wave:
                raise SeedMasterRuntimeError(
                    f"{segment_id} planned_wave differs from the dependency DAG"
                )
            wave_by_id[segment_id] = expected_wave
        handoff = load_route_b_handoff(task_dir)
        if list(handoff) != all_ids:
            raise SeedMasterRuntimeError(
                "Route B dialogue/boundary handoff differs from the Storyboard manifest"
            )
    return {
        "status": "PASS",
        "segment_count": len(selected),
        "segments": selected,
        "generate_audio": True,
        "script_root": str(script_root),
        "execution_plan_root": str(plan_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--segments", nargs="+", metavar="SEGMENT_ID")
    args = parser.parse_args()
    try:
        result = validate_task(args.task_dir, segment_ids=args.segments)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
