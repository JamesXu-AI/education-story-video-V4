#!/usr/bin/env python3
"""Write the task's verified capability profile from the active local adapter."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
SHARED_PROVIDER_ROOT = REPOSITORY_ROOT / "direct-production-design" / "scripts"
for root in (SCRIPT_ROOT, SHARED_PROVIDER_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import providers  # noqa: E402

SHARED_PROVIDER_PATH = SHARED_PROVIDER_ROOT / "providers"
if str(SHARED_PROVIDER_PATH) not in providers.__path__:
    providers.__path__.append(str(SHARED_PROVIDER_PATH))

from providers import seedance  # noqa: E402


def refresh(task_dir: Path) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    adapter_path = REPOSITORY_ROOT / "virtual-production" / "scripts" / "providers" / "seedance.py"
    if not adapter_path.is_file():
        raise RuntimeError("Current repository Seedance adapter is missing")
    model_id = seedance.model_id()
    value = {
        "contract": "seedance-capability-profile",
        "profile_status": "VERIFIED",
        "provider": "seedance",
        "model_id": model_id,
        "verified_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider_capabilities": {
            "minimum_segment_seconds": 4,
            "maximum_segment_seconds": 15,
            "maximum_reference_images": seedance.MAX_REFERENCE_IMAGES,
            "maximum_reference_videos": seedance.MAX_REFERENCE_VIDEOS,
            "maximum_reference_audios": seedance.MAX_REFERENCE_AUDIOS,
            "native_audio_generation": True,
            "native_background_audio_generation": True,
            "supported_reference_roles": [
                "reference_image", "reference_audio", "reference_video"
            ],
        },
        "project_generation_policy": {
            "maximum_total_seconds": 240,
            "one_task_per_segment": True,
            "seed_master_operations": [
                "text_to_video",
                "multimodal_reference",
                "video_extension",
                "strict_first_frame",
                "strict_first_last",
            ],
            "predecessor_evidence_modes": [
                "none",
                "approved_complete_predecessor",
                "approved_final_2s_silent_plus_provider_last_frame",
                "approved_provider_last_frame",
            ],
            "matched_cut_tail_seconds": 2.0,
            "continuity_reference_audio_policy": "preserve_for_extension_strip_for_matched_cut",
            "return_last_frame_required": True,
            "cross_clip_lipsync_dependency": False,
            "cross_clip_dialogue_dependency": False,
            "cross_clip_native_audio_dependency": "continuous_extension_only",
            "maximum_inherited_video_hops": 1,
        },
        "provider_adapter_path": adapter_path.relative_to(REPOSITORY_ROOT).as_posix(),
    }
    output = task_dir / "virtual-production" / "seedance-capability-profile.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
    return {
        "status": "PASS",
        "output": output.relative_to(task_dir).as_posix(),
        "model_id": model_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = refresh(args.task_dir)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
