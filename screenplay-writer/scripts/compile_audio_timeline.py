#!/usr/bin/env python3
"""Compile and validate the screenplay-owned dialogue and sound-intent timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for script_root in (REPOSITORY_ROOT / "screenplay-writer" / "scripts",):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

from story_video.runtime_support import StoryVideoError
from story_video.screenplay_contract import (
    DIALOGUE_OCCUPANCY_LIMITS,
    DIALOGUE_TURN_ALLOWANCE_SECONDS,
    DIALOGUE_WORDS_PER_SECOND,
    load_screenplay_file,
)


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*")


def _round(value: float) -> float:
    return round(value + 1e-9, 3)


def _block_minimum_seconds(
    block: dict[str, Any], *, action_block_count: int
) -> float:
    if block["type"] == "dialogue":
        return max(
            0.75,
            len(WORD_RE.findall(block["spoken_text_en"]))
            / DIALOGUE_WORDS_PER_SECOND
            + DIALOGUE_TURN_ALLOWANCE_SECONDS,
        )
    return 1.0 / max(1, action_block_count)


def validate_dialogue_occupancy(
    *,
    segment_id: str,
    dramatic_workload: str,
    duration_seconds: float,
    block_windows: list[dict[str, Any]],
) -> tuple[float, float]:
    dialogue_window_seconds = sum(
        item["end_seconds"] - item["start_seconds"]
        for item in block_windows
        if item["block_type"] == "dialogue"
    )
    dialogue_occupancy = dialogue_window_seconds / duration_seconds
    occupancy_limit = DIALOGUE_OCCUPANCY_LIMITS[dramatic_workload]
    if dialogue_occupancy > occupancy_limit + 1e-9:
        raise StoryVideoError(
            f"{segment_id} dialogue occupancy "
            f"{dialogue_occupancy:.1%} exceeds the {occupancy_limit:.0%} "
            f"{dramatic_workload} limit"
        )
    return dialogue_occupancy, occupancy_limit


def build_audio_timeline(screenplay_path: Path) -> dict[str, Any]:
    screenplay_path = screenplay_path.expanduser().resolve()
    screenplay = load_screenplay_file(screenplay_path)
    segments: list[dict[str, Any]] = []
    cue_count = 0
    for segment in screenplay["segments"]:
        plan = segment["story_plan"]
        duration = float(plan["estimated_duration_seconds"])
        blocks = segment["blocks"]
        action_block_count = sum(block["type"] == "action" for block in blocks)
        minimums = [
            _block_minimum_seconds(
                block, action_block_count=action_block_count
            )
            for block in blocks
        ]
        minimum_total = sum(minimums)
        if minimum_total > duration + 1e-9:
            raise StoryVideoError(
                f"{plan['segment_id']} cannot fit its dialogue/action audio intent"
            )
        extra_per_block = (duration - minimum_total) / len(blocks)
        cursor = 0.0
        dialogue_cues: list[dict[str, Any]] = []
        action_sound_sources: list[dict[str, Any]] = []
        block_windows: list[dict[str, Any]] = []
        for block_index, (block, minimum) in enumerate(
            zip(blocks, minimums), start=1
        ):
            block_start = cursor
            block_end = cursor + minimum + extra_per_block
            block_windows.append(
                {
                    "block_index": block_index,
                    "block_type": block["type"],
                    "start_seconds": _round(block_start),
                    "end_seconds": _round(
                        duration if block_index == len(blocks) else block_end
                    ),
                }
            )
            if block["type"] == "dialogue":
                cue_count += 1
                spoken_seconds = (
                    len(WORD_RE.findall(block["spoken_text_en"]))
                    / DIALOGUE_WORDS_PER_SECOND
                )
                cue_start = block_start + min(0.2, (block_end - block_start) * 0.1)
                cue_end = min(block_end, cue_start + spoken_seconds)
                dialogue_cues.append(
                    {
                        "cue_id": f"dialogue-{cue_count:03d}",
                        "block_index": block_index,
                        "speaker_en": block["speaker_en"],
                        "speaker_mode": block["speaker_mode"] or "on_screen_or_storyboard_decides",
                        "exact_text_en": block["spoken_text_en"],
                        "delivery_en": block["delivery_en"] or "not_specified",
                        "estimated_start_seconds": _round(cue_start),
                        "estimated_end_seconds": _round(cue_end),
                        "timing_authority": "screenplay_estimate_storyboard_must_refine",
                        "dialogue_source": "seedance",
                    }
                )
            else:
                action_sound_sources.append(
                    {
                        "block_index": block_index,
                        "estimated_start_seconds": _round(block_start),
                        "estimated_end_seconds": _round(block_end),
                        "action_text_en": block["text_en"],
                    }
                )
            cursor = block_end
        dramatic_workload = plan["dramatic_workload"]
        dialogue_occupancy, occupancy_limit = validate_dialogue_occupancy(
            segment_id=plan["segment_id"],
            dramatic_workload=dramatic_workload,
            duration_seconds=duration,
            block_windows=block_windows,
        )
        transition = plan["transition_design_json"]
        segments.append(
            {
                "segment_id": plan["segment_id"],
                "scene_id": plan["scene_id"],
                "duration_seconds": int(duration),
                "dramatic_workload": dramatic_workload,
                "dialogue_occupancy": _round(dialogue_occupancy),
                "dialogue_occupancy_limit": occupancy_limit,
                "voice_audio_source": "speaker_reference_audio",
                "dialogue_source": "seedance",
                "seedance_background_audio": True,
                "dialogue_cues": dialogue_cues,
                "block_windows": block_windows,
                "action_sound_source_blocks": action_sound_sources,
                "outgoing_audio_intent_en": transition["outgoing_audio_en"],
                "incoming_audio_intent_en": transition["incoming_audio_en"],
                "sound_link_intent_en": transition["sound_link_en"],
                "native_audio_closure_required": True,
            }
        )
    return {
        "contract": "screenplay-audio-timeline",
        "authority_owner": "screenplay-writer",
        "timeline_scope": "screenplay_dialogue_and_sound_intent",
        "source_screenplay": screenplay_path.name,
        "timing_policy": "screenplay_estimates_storyboard_refines_finish_retimes_from_accepted_media",
        "segment_count": len(segments),
        "planned_runtime_seconds": screenplay["total_duration_seconds"],
        "dialogue_cue_count": cue_count,
        "segments": segments,
    }


def validate_audio_timeline(
    value: dict[str, Any], *, screenplay_path: Path
) -> dict[str, Any]:
    expected = build_audio_timeline(screenplay_path)
    if value != expected:
        raise StoryVideoError(
            "audio-timeline.json differs from the current screenplay dialogue/sound projection"
        )
    return {
        "status": "PASS",
        "segment_count": value["segment_count"],
        "dialogue_cue_count": value["dialogue_cue_count"],
        "planned_runtime_seconds": value["planned_runtime_seconds"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenplay", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        screenplay = args.screenplay.expanduser().resolve()
        output = args.output or screenplay.parent / "audio-timeline.json"
        if args.validate_only:
            payload = json.loads(output.read_text(encoding="utf-8"))
        else:
            payload = build_audio_timeline(screenplay)
            output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(validate_audio_timeline(payload, screenplay_path=screenplay), indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
