"""Load Seed Master Route B duration/boundary ledgers without a Storyboard companion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DIALOGUE_LEDGER_RELATIVE = Path(
    ".pending/virtual-production/dialogue-duration-ledger.json"
)
BOUNDARY_REPORT_RELATIVE = Path(
    ".pending/virtual-production/boundary-continuity-report.json"
)
STORYBOARD_RELATIVE = Path("previsualize-cinematography/storyboard.md")
MANIFEST_RELATIVE = Path(
    "previsualize-cinematography/storyboard-compile-manifest.json"
)


class RouteBHandoffError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RouteBHandoffError(f"Missing or invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RouteBHandoffError(f"{label} must contain one JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RouteBHandoffError(f"Cannot read required authority: {path}") from exc


def _validate_identity(
    value: dict[str, Any], *, storyboard_sha: str, manifest_sha: str, label: str
) -> None:
    if (
        value.get("schema_version") != "1.0"
        or value.get("storyboard_sha256") != storyboard_sha
        or value.get("source_manifest_sha256") != manifest_sha
    ):
        raise RouteBHandoffError(f"{label} is stale or has the wrong contract")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteBHandoffError(f"{label} must be numeric")
    return float(value)


def load_route_b_handoff(task_dir: Path) -> dict[str, dict[str, Any]]:
    """Return a read-only postproduction view from native Route A/B artifacts."""

    task_dir = task_dir.expanduser().resolve()
    storyboard_sha = _sha(task_dir / STORYBOARD_RELATIVE)
    manifest_path = task_dir / MANIFEST_RELATIVE
    manifest_sha = _sha(manifest_path)
    manifest = _load(manifest_path, "Storyboard compile manifest")
    dialogue = _load(task_dir / DIALOGUE_LEDGER_RELATIVE, "Route B dialogue-duration ledger")
    boundary = _load(task_dir / BOUNDARY_REPORT_RELATIVE, "Route B boundary report")
    _validate_identity(
        dialogue,
        storyboard_sha=storyboard_sha,
        manifest_sha=manifest_sha,
        label="dialogue-duration ledger",
    )
    _validate_identity(
        boundary,
        storyboard_sha=storyboard_sha,
        manifest_sha=manifest_sha,
        label="boundary-continuity report",
    )
    manifest_segments = manifest.get("segments")
    manifest_lines = manifest.get("lines")
    dialogue_segments = dialogue.get("segments")
    boundary_segments = boundary.get("segments")
    if not all(
        isinstance(value, list)
        for value in (
            manifest_segments,
            manifest_lines,
            dialogue_segments,
            boundary_segments,
        )
    ):
        raise RouteBHandoffError("Route A/B Segment ledgers must be arrays")
    expected_ids = [
        row.get("segment_id") for row in manifest_segments if isinstance(row, dict)
    ]
    if (
        not expected_ids
        or len(expected_ids) != len(set(expected_ids))
        or [row.get("segment_id") for row in dialogue_segments if isinstance(row, dict)]
        != expected_ids
        or [row.get("segment_id") for row in boundary_segments if isinstance(row, dict)]
        != expected_ids
    ):
        raise RouteBHandoffError("Route B ledgers differ from Storyboard Segment order")
    dialogue_by_id = {row["segment_id"]: row for row in dialogue_segments}
    boundary_by_id = {row["segment_id"]: row for row in boundary_segments}
    result: dict[str, dict[str, Any]] = {}
    for manifest_row in manifest_segments:
        if not isinstance(manifest_row, dict):
            raise RouteBHandoffError("Storyboard manifest contains an invalid Segment")
        segment_id = str(manifest_row["segment_id"])
        duration = _number(
            manifest_row.get("target_duration_seconds"),
            f"{segment_id} target duration",
        )
        dialogue_row = dialogue_by_id[segment_id]
        if _number(dialogue_row.get("duration_seconds"), f"{segment_id} ledger duration") != duration:
            raise RouteBHandoffError(f"{segment_id} dialogue ledger duration differs")
        cues = dialogue_row.get("dialogue_cues")
        if not isinstance(cues, list):
            raise RouteBHandoffError(f"{segment_id} dialogue_cues must be an array")
        blocks: list[dict[str, Any]] = []
        expected_lines = [
            row
            for row in manifest_lines
            if isinstance(row, dict) and row.get("segment_id") == segment_id
        ]
        expected_line_ids = [row.get("line_id") for row in expected_lines]
        actual_line_ids = [
            row.get("line_id") for row in cues if isinstance(row, dict)
        ]
        if actual_line_ids != expected_line_ids:
            raise RouteBHandoffError(
                f"{segment_id} dialogue ledger differs from manifest Line ownership/order"
            )
        expected_by_id = {str(row["line_id"]): row for row in expected_lines}
        seen_lines: set[str] = set()
        prior_end = 0.0
        for index, cue in enumerate(cues, start=1):
            if not isinstance(cue, dict):
                raise RouteBHandoffError(f"{segment_id} has an invalid dialogue cue")
            line_id = cue.get("line_id")
            start = _number(cue.get("start_seconds"), f"{segment_id} cue start")
            end = _number(cue.get("end_seconds"), f"{segment_id} cue end")
            exact_text = cue.get("exact_text")
            expected_line = expected_by_id.get(str(line_id))
            if (
                not isinstance(line_id, str)
                or not line_id
                or line_id in seen_lines
                or not isinstance(exact_text, str)
                or not exact_text.strip()
                or not isinstance(expected_line, dict)
                or exact_text != expected_line.get("exact_text")
                or (cue.get("speaker_entity_id") or cue.get("speaker"))
                != expected_line.get("speaker")
                or start < prior_end
                or end <= start
                or end > duration
            ):
                raise RouteBHandoffError(f"{segment_id} dialogue timing/identity is invalid")
            seen_lines.add(line_id)
            prior_end = end
            normalized = {
                "cue_id": line_id,
                "line_id": line_id,
                "shot_id": cue.get("shot_id"),
                "screenplay_reference": cue.get("screenplay_reference") or line_id,
                "speaker_entity_id": cue.get("speaker_entity_id") or cue.get("speaker"),
                "speaker_screenplay_identity_en": cue.get("speaker_screenplay_identity_en")
                or cue.get("speaker"),
                "exact_text": exact_text.strip(),
                "start_seconds": start,
                "end_seconds": end,
            }
            blocks.append(
                {
                    "block_id": f"{segment_id}-dialogue-{index:02d}",
                    "timeline_blocks_source": "seed_master_route_b_dialogue_duration_ledger",
                    "dialogue_cues": [normalized],
                }
            )
        boundary_row = boundary_by_id[segment_id]
        editable_hold = _number(
            boundary_row.get("editable_hold_seconds"),
            f"{segment_id} editable hold",
        )
        if editable_hold < 0 or editable_hold > duration:
            raise RouteBHandoffError(f"{segment_id} editable hold is invalid")
        for field in ("final_visible_state", "final_sound_state"):
            if not isinstance(boundary_row.get(field), str) or not boundary_row[field].strip():
                raise RouteBHandoffError(f"{segment_id} boundary report lacks {field}")
        result[segment_id] = {
            "segment_id": segment_id,
            "duration_seconds": duration,
            "timeline_blocks": blocks,
            "segment_safe_cut_design": {
                "editable_hold_seconds": editable_hold,
                "final_visible_state_en": boundary_row.get("final_visible_state"),
                "final_sound_state_en": boundary_row.get("final_sound_state"),
            },
        }
    return result
