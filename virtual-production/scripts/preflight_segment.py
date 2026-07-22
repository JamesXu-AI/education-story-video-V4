#!/usr/bin/env python3
"""Run the immediate Seedance preflight for one materialized Route B Script."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.seed_master_runtime import (  # noqa: E402
    CAPABILITY_PROFILE_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    SeedMasterRuntimeError,
    load_execution_plan,
    parse_segment_script,
    read_json,
)
from validate_segment_scripts import validate_task as validate_segment_scripts  # noqa: E402


def preflight_segment(
    *, task_dir: Path, segment_script_path: Path
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    segment_script_path = segment_script_path.expanduser().resolve(strict=True)
    segment_id = segment_script_path.stem
    expected = (task_dir / SCRIPT_DIR_RELATIVE / f"{segment_id}.md").resolve()
    if segment_script_path != expected:
        raise SeedMasterRuntimeError(f"Segment Script must use the current path: {expected}")
    validate_segment_scripts(task_dir, segment_ids=[segment_id])
    parsed = parse_segment_script(segment_script_path)
    plan = load_execution_plan(task_dir, segment_id)
    profile = read_json(
        task_dir / CAPABILITY_PROFILE_RELATIVE,
        label="Seedance capability profile",
    )
    capabilities = profile.get("provider_capabilities")
    parameters = plan["seedance_parameters"]
    media_counts = plan["media_counts"]
    if not isinstance(capabilities, dict):
        raise SeedMasterRuntimeError("Seedance capability profile is incomplete")
    if (
        parameters.get("model") != profile.get("model_id")
        or parameters.get("duration") != parsed["duration"]
        or capabilities.get("native_audio_generation") is not True
        or capabilities.get("native_background_audio_generation") is not True
    ):
        raise SeedMasterRuntimeError(f"{segment_id} is incompatible with the verified model")
    limits = {
        "reference_image": capabilities.get("maximum_reference_images"),
        "reference_video": capabilities.get("maximum_reference_videos"),
        "reference_audio": capabilities.get("maximum_reference_audios"),
    }
    for role, count in media_counts.items():
        limit = limits.get(role)
        if isinstance(count, bool) or not isinstance(count, int):
            raise SeedMasterRuntimeError(f"{segment_id} has invalid {role} count")
        if isinstance(limit, bool) or not isinstance(limit, int) or count > limit:
            raise SeedMasterRuntimeError(f"{segment_id} exceeds the {role} capability")
    return {
        "status": "PASS",
        "segment_id": segment_id,
        "model_id": parameters["model"],
        "duration_seconds": parameters["duration"],
        "operation": plan["shooting_plan"]["operation"],
        "shooting_plan_status": plan["shooting_plan"]["shooting_plan_status"],
        "planned_wave": plan["shooting_plan"]["planned_wave"],
        "reference_image_count": media_counts["reference_image"],
        "reference_video_count": media_counts["reference_video"],
        "reference_audio_count": media_counts["reference_audio"],
        "media_bindings_resolved": True,
        "generate_audio": True,
        "return_last_frame": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--segment-script", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = preflight_segment(
            task_dir=args.task_dir,
            segment_script_path=args.segment_script,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
