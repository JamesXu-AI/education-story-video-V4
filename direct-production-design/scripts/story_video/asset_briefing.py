"""Mechanical reuse checks for already model-authored asset briefs."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def brief_file_matches(path: Path, expected_brief: str) -> bool:
    try:
        actual = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return False
    return actual == expected_brief.rstrip() + "\n"


def reusable_visual_from_current_record(
    *,
    root: Path,
    record: Any,
    asset_type: str,
    output: Path,
    prompt: str,
) -> dict[str, str] | None:
    visual = reusable_visual_candidate_from_current_record(
        root=root,
        record=record,
        asset_type=asset_type,
        output=output,
    )
    if visual is None:
        return None
    brief_path = (root / output).parent / f"{output.stem}.brief.txt"
    if not brief_file_matches(brief_path, prompt):
        return None
    return visual


def reusable_visual_candidate_from_current_record(
    *,
    root: Path,
    record: Any,
    asset_type: str,
    output: Path,
) -> dict[str, str] | None:
    if not isinstance(record, dict) or record.get("type") != asset_type:
        return None
    visual = record.get("visual")
    if not isinstance(visual, dict) and asset_type == "ensemble_roster":
        members = record.get("members")
        if isinstance(members, list) and len(members) == 1:
            roster_asset = members[0].get("roster_asset")
            if isinstance(roster_asset, dict):
                visual = {
                    "path": roster_asset.get("path"),
                    "uri": roster_asset.get("uri"),
                }
    if (
        not isinstance(visual, dict)
        or set(visual) != {"path", "uri"}
        or visual.get("path") != output.as_posix()
        or not isinstance(visual.get("uri"), str)
        or not visual["uri"].strip()
        or not (root / output).is_file()
    ):
        return None
    return {"path": visual["path"], "uri": visual["uri"]}
