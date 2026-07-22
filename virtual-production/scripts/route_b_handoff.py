"""Build the postproduction handoff from private Seedance Segment plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from story_video.seed_master_runtime import storyboard_segment_rows


class RouteBHandoffError(RuntimeError):
    pass


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteBHandoffError(f"{label} must be numeric")
    return float(value)


def load_route_b_handoff(task_dir: Path) -> dict[str, dict[str, Any]]:
    """Return a read-only timing and safe-cut view without companion ledgers."""

    task_dir = task_dir.expanduser().resolve()
    result: dict[str, dict[str, Any]] = {}
    for plan in storyboard_segment_rows(task_dir):
        segment_id = str(plan["segment_id"])
        duration = _number(plan.get("target_duration"), f"{segment_id} duration")
        cues = plan.get("dialogue_cues")
        if not isinstance(cues, list):
            raise RouteBHandoffError(f"{segment_id} dialogue_cues must be an array")
        blocks: list[dict[str, Any]] = []
        seen_lines: set[str] = set()
        prior_end = 0.0
        for index, cue in enumerate(cues, start=1):
            if not isinstance(cue, dict):
                raise RouteBHandoffError(f"{segment_id} has an invalid dialogue cue")
            line_id = cue.get("line_id")
            speaker_id = cue.get("speaker_entity_id")
            speaker_name = cue.get("speaker_name")
            exact_text = cue.get("exact_text")
            shot_number = cue.get("shot_number")
            start = _number(cue.get("start_seconds"), f"{segment_id} cue start")
            end = _number(cue.get("end_seconds"), f"{segment_id} cue end")
            if (
                not isinstance(line_id, str)
                or not line_id
                or line_id in seen_lines
                or not isinstance(speaker_id, str)
                or not speaker_id
                or not isinstance(speaker_name, str)
                or not speaker_name
                or not isinstance(exact_text, str)
                or not exact_text.strip()
                or not isinstance(shot_number, int)
                or shot_number < 1
                or start < prior_end
                or end <= start
                or end > duration
            ):
                raise RouteBHandoffError(f"{segment_id} dialogue timing or ownership is invalid")
            seen_lines.add(line_id)
            prior_end = end
            normalized = {
                "cue_id": line_id,
                "line_id": line_id,
                "shot_id": f"Shot {shot_number}",
                "screenplay_reference": line_id,
                "speaker_entity_id": speaker_id,
                "speaker_screenplay_identity_en": speaker_name,
                "exact_text": exact_text.strip(),
                "start_seconds": start,
                "end_seconds": end,
            }
            blocks.append(
                {
                    "block_id": f"{segment_id}-dialogue-{index:02d}",
                    "timeline_blocks_source": "private_seedance_segment_plan",
                    "dialogue_cues": [normalized],
                }
            )
        editable_hold = _number(
            plan.get("editable_hold_seconds"), f"{segment_id} editable hold"
        )
        final_visible = plan.get("final_visible_state")
        final_sound = plan.get("final_sound_state")
        if (
            editable_hold < 0
            or editable_hold > duration
            or not isinstance(final_visible, str)
            or not final_visible.strip()
            or not isinstance(final_sound, str)
            or not final_sound.strip()
        ):
            raise RouteBHandoffError(f"{segment_id} has an invalid safe-cut state")
        result[segment_id] = {
            "segment_id": segment_id,
            "duration_seconds": duration,
            "timeline_blocks": blocks,
            "segment_safe_cut_design": {
                "editable_hold_seconds": editable_hold,
                "final_visible_state_en": final_visible,
                "final_sound_state_en": final_sound,
            },
        }
    return result
