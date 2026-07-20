#!/usr/bin/env python3
"""Validate the current production-design outputs without approval records."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parent
for script_root in (
    REPOSITORY_ROOT / "screenplay-writer" / "scripts",
    SKILL_ROOT / "scripts",
):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

from story_video.asset_catalog import load_asset_catalog  # noqa: E402
from story_video.asset_briefing import (  # noqa: E402
    group_portrait_subject_count,
    ordered_ensemble_member_types,
)
from story_video.aesthetic_reference import load_aesthetic_reference  # noqa: E402
from story_video.location_continuity_packages import (  # noqa: E402
    load_location_continuity_packages,
)
from story_video.character_performance_map import (  # noqa: E402
    load_character_performance_map,
)
from story_video.validate_voice_authority import validate_voice_authority  # noqa: E402


class ProductionDesignError(RuntimeError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def _validate_silent_group_authority(
    performance: dict[str, object], catalog: dict[str, object]
) -> int:
    entities = performance["performance_entities"]
    segments = performance["scene_segment_calls"]
    speaking_ids = {
        call["entity_id"]
        for segment in segments
        for call in segment["calls"]
        if call["speaks"]
    }
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entity in entities:
        if entity["entity_id"] not in speaking_ids:
            grouped[entity["group_role_type_en"]].append(entity)
    assets = catalog["assets"]
    expected_ids: set[str] = set()
    for role_type, role_entities in grouped.items():
        asset_id = "group-" + _slug(role_type)
        expected_ids.add(asset_id)
        asset = assets.get(asset_id)
        if not isinstance(asset, dict) or asset.get("type") != "ensemble_roster":
            raise ProductionDesignError(
                f"Missing current ensemble roster for silent role {role_type}: {asset_id}"
            )
        members = asset.get("members")
        if not isinstance(members, list) or len(members) != 1:
            raise ProductionDesignError(
                f"{asset_id} must contain exactly one current role-group record"
            )
        member = members[0]
        expected_member_types = ordered_ensemble_member_types(role_entities)
        expected_subject_count = group_portrait_subject_count(expected_member_types)
        if member.get("allowed_member_types_en") != expected_member_types:
            raise ProductionDesignError(
                f"{asset_id} allowed member types differ from current performance authority"
            )
        if member.get("roster_asset", {}).get("subject_count") != expected_subject_count:
            raise ProductionDesignError(
                f"{asset_id} subject count differs from its closed member-type roster"
            )
    actual_ids = {
        asset_id
        for asset_id, asset in assets.items()
        if isinstance(asset, dict) and asset.get("type") == "ensemble_roster"
    }
    if actual_ids != expected_ids:
        raise ProductionDesignError(
            "Ensemble roster set differs from current performance authority; "
            f"expected={sorted(expected_ids)}, actual={sorted(actual_ids)}"
        )
    return len(expected_ids)


def validate_task(task_dir: Path) -> dict[str, object]:
    task_dir = task_dir.expanduser().resolve(strict=True)
    for relative in ("screenplay-writer/screenplay.md",):
        path = task_dir / relative
        if not path.is_file() or path.stat().st_size <= 0:
            raise ProductionDesignError(f"Missing current screenplay input: {relative}")
    visual_spec_path = task_dir / "direct-production-design" / "visual-production-spec.md"
    try:
        visual_spec = visual_spec_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise ProductionDesignError(
            f"Missing or invalid visual production specification: {visual_spec_path}"
        ) from exc
    if "# Visual Production Specification" not in visual_spec:
        raise ProductionDesignError("visual-production-spec.md lacks its required heading")
    catalog = load_asset_catalog(task_dir)
    performance = load_character_performance_map(task_dir)
    silent_group_count = _validate_silent_group_authority(performance, catalog)
    aesthetic_reference = load_aesthetic_reference(task_dir)
    location_packages = load_location_continuity_packages(task_dir)
    expected_scene_ids = {
        segment["scene_id"] for segment in performance["scene_segment_calls"]
    }
    packaged_scene_ids = {
        scene_id
        for location in location_packages["locations"]
        for scene_id in location["scene_ids"]
    }
    if packaged_scene_ids != expected_scene_ids:
        raise ProductionDesignError(
            "Location continuity packages must cover every current screenplay Scene "
            "exactly once; "
            f"expected={sorted(expected_scene_ids)}, actual={sorted(packaged_scene_ids)}"
        )
    voice_result = validate_voice_authority(task_dir)
    return {
        "status": "PASS",
        "asset_count": len(catalog["assets"]),
        "silent_group_count": silent_group_count,
        "speaker_voice_count": voice_result["speaker_count"],
        "location_package_count": len(location_packages["locations"]),
        "location_master_count": len(location_packages["locations"]),
        "aesthetic_reference_frame_count": (
            aesthetic_reference["reference_count"]
            if aesthetic_reference is not None
            else 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_task(args.task_dir)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
