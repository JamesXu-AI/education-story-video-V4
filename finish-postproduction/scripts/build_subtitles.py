#!/usr/bin/env python3
"""Build exact Storyboard-timed SRT/VTT subtitles and an optional captioned master."""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STORYBOARD_SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
if str(STORYBOARD_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(STORYBOARD_SCRIPT_ROOT))

from route_b_handoff import load_route_b_handoff  # noqa: E402

DEFAULT_STYLE = SKILL_ROOT / "assets" / "subtitle-style.json"
ASS_PLAY_RESOLUTION_HEIGHT = 288.0
SEGMENT_RE = re.compile(r"^segment-([0-9]{3,})$")
STYLE_KEYS = {
    "contract",
    "text_authority",
    "timing_authority",
    "max_lines",
    "max_characters_per_line_cjk",
    "max_characters_per_line_latin",
    "minimum_cue_duration_seconds",
    "maximum_characters_per_second_cjk",
    "maximum_words_per_minute_latin",
    "position",
    "bottom_margin_percent",
    "font_family",
    "font_size_percent_of_frame_height",
    "font_weight",
    "text_color",
    "outline_color",
    "outline_width_percent_of_frame_height",
    "shadow",
    "background_box",
    "speaker_labels",
    "burn_in_required",
    "external_srt_required",
    "external_vtt_required",
}


class SubtitleBuildError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SubtitleBuildError(f"Missing required file: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SubtitleBuildError(f"Invalid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SubtitleBuildError(f"{path} must contain one JSON object.")
    return value


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise SubtitleBuildError(f"{label} must be numeric and >= {minimum}.")
    return float(value)


def _validate_style(style: dict[str, Any]) -> None:
    if set(style) != STYLE_KEYS:
        raise SubtitleBuildError(
            f"Subtitle style must use exact keys: {sorted(STYLE_KEYS)}"
        )
    if style["contract"] != "finish-subtitle-style":
        raise SubtitleBuildError("Unsupported subtitle-style contract.")
    if style["text_authority"] != "seed_master_route_b_exact_dialogue_ledger":
        raise SubtitleBuildError("Subtitle text authority must be the Route B exact-dialogue ledger.")
    if (
        style["timing_authority"]
        != "seed_master_route_b_dialogue_duration_ledger_plus_picture_edl"
    ):
        raise SubtitleBuildError("Subtitle timing authority is invalid.")
    for field in (
        "shadow",
        "background_box",
        "speaker_labels",
        "burn_in_required",
        "external_srt_required",
        "external_vtt_required",
    ):
        if not isinstance(style[field], bool):
            raise SubtitleBuildError(f"subtitle style {field} must be boolean.")


def _segment_name(value: Any) -> str:
    if isinstance(value, bool):
        raise SubtitleBuildError("EDL Segment ID cannot be boolean.")
    if isinstance(value, int):
        name = f"segment-{value:03d}"
    else:
        raw = str(value).strip()
        name = raw if raw.startswith("segment-") else f"segment-{int(raw):03d}"
    if not SEGMENT_RE.fullmatch(name):
        raise SubtitleBuildError(f"Invalid EDL Segment ID: {value!r}")
    return name


def _target_language(task: dict[str, Any]) -> str:
    translation = task.get("translation")
    if not isinstance(translation, dict):
        raise SubtitleBuildError("task.json translation authority is missing.")
    value = translation.get("output_language")
    if not isinstance(value, str) or not value.strip():
        raise SubtitleBuildError("task.json translation.output_language is invalid.")
    return value.strip()


def _is_cjk(text: str) -> bool:
    return any(
        "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\u3040" <= char <= "\u30ff"
        or "\uac00" <= char <= "\ud7af"
        for char in text
    )


def _wrap_cjk(text: str, limit: int, max_lines: int) -> str:
    compact = "".join(text.split())
    lines = [compact[index : index + limit] for index in range(0, len(compact), limit)]
    if len(lines) > max_lines:
        raise SubtitleBuildError(
            f"Subtitle needs {len(lines)} CJK lines; maximum is {max_lines}: {text!r}"
        )
    return "\n".join(lines)


def _wrap_words(text: str, limit: int, max_lines: int) -> str:
    normalized = " ".join(text.split())
    words = normalized.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise SubtitleBuildError(
            f"Subtitle needs {len(lines)} lines; maximum is {max_lines}: {text!r}"
        )
    return "\n".join(lines)


def _try_wrap(
    text: str,
    *,
    is_cjk: bool,
    line_limit: int,
    max_lines: int,
) -> str | None:
    try:
        if is_cjk:
            return _wrap_cjk(text, line_limit, max_lines)
        return _wrap_words(text, line_limit, max_lines)
    except SubtitleBuildError as exc:
        if not str(exc).startswith("Subtitle needs "):
            raise
        return None


def _split_oversized_unit(
    text: str,
    *,
    is_cjk: bool,
    line_limit: int,
    max_lines: int,
) -> list[str]:
    units = list("".join(text.split())) if is_cjk else " ".join(text.split()).split(" ")
    separator = "" if is_cjk else " "
    chunks: list[str] = []
    cursor = 0
    while cursor < len(units):
        best_end: int | None = None
        for end in range(cursor + 1, len(units) + 1):
            candidate = separator.join(units[cursor:end])
            if _try_wrap(
                candidate,
                is_cjk=is_cjk,
                line_limit=line_limit,
                max_lines=max_lines,
            ) is None:
                break
            best_end = end
        if best_end is None:
            raise SubtitleBuildError(
                f"Subtitle contains a unit wider than the current line limit: {text!r}"
            )
        chunks.append(separator.join(units[cursor:best_end]))
        cursor = best_end

    # The greedy pass above establishes the minimum number of screens, but it
    # can leave a one-word (or one-character) final screen. Redistribute the
    # same exact units across that minimum screen count so every screen carries
    # a comparable reading load while still satisfying the line limits.
    screen_count = len(chunks)
    if screen_count <= 1:
        return chunks
    target_units = len(units) / screen_count

    @lru_cache(maxsize=None)
    def balanced_split(cursor: int, screens_left: int) -> tuple[float, tuple[int, ...]] | None:
        if screens_left == 0:
            return (0.0, ()) if cursor == len(units) else None
        last_end = len(units) - (screens_left - 1)
        best: tuple[float, tuple[int, ...]] | None = None
        for end in range(cursor + 1, last_end + 1):
            candidate = separator.join(units[cursor:end])
            if _try_wrap(
                candidate,
                is_cjk=is_cjk,
                line_limit=line_limit,
                max_lines=max_lines,
            ) is None:
                break
            remainder = balanced_split(end, screens_left - 1)
            if remainder is None:
                continue
            cost = (end - cursor - target_units) ** 2 + remainder[0]
            proposal = (cost, (end,) + remainder[1])
            if best is None or proposal[0] < best[0]:
                best = proposal
        return best

    split = balanced_split(0, screen_count)
    if split is None:
        return chunks
    balanced: list[str] = []
    cursor = 0
    for end in split[1]:
        balanced.append(separator.join(units[cursor:end]))
        cursor = end
    return balanced


def _caption_chunks(
    text: str,
    *,
    is_cjk: bool,
    line_limit: int,
    max_lines: int,
) -> list[tuple[str, str]]:
    normalized = "".join(text.split()) if is_cjk else " ".join(text.split())
    rendered = _try_wrap(
        normalized,
        is_cjk=is_cjk,
        line_limit=line_limit,
        max_lines=max_lines,
    )
    if rendered is not None:
        return [(normalized, rendered)]

    if is_cjk:
        semantic_units = [
            value
            for value in re.findall(r".*?[。！？!?](?:[”’\"])?|.+$", normalized)
            if value
        ]
        separator = ""
    else:
        semantic_units = [
            value
            for value in re.split(r"(?<=[.!?])\s+", normalized)
            if value
        ]
        separator = " "

    pieces: list[str] = []
    for unit in semantic_units:
        if _try_wrap(
            unit,
            is_cjk=is_cjk,
            line_limit=line_limit,
            max_lines=max_lines,
        ) is not None:
            pieces.append(unit)
        else:
            pieces.extend(
                _split_oversized_unit(
                    unit,
                    is_cjk=is_cjk,
                    line_limit=line_limit,
                    max_lines=max_lines,
                )
            )

    chunks: list[str] = []
    for piece in pieces:
        candidate = piece if not chunks else separator.join((chunks[-1], piece))
        if chunks and _try_wrap(
            candidate,
            is_cjk=is_cjk,
            line_limit=line_limit,
            max_lines=max_lines,
        ) is not None:
            chunks[-1] = candidate
        else:
            chunks.append(piece)

    result: list[tuple[str, str]] = []
    for chunk in chunks:
        wrapped = _try_wrap(
            chunk,
            is_cjk=is_cjk,
            line_limit=line_limit,
            max_lines=max_lines,
        )
        if wrapped is None:
            raise SubtitleBuildError(f"Could not fit subtitle chunk: {chunk!r}")
        result.append((chunk, wrapped))
    reconstructed = separator.join(chunk for chunk, _ in result)
    if reconstructed != normalized:
        raise SubtitleBuildError("Caption splitting changed exact dialogue text.")
    return result


def _caption_intervals(
    start: float,
    end: float,
    chunks: list[tuple[str, str]],
    *,
    is_cjk: bool,
    minimum_duration: float,
) -> list[tuple[float, float]]:
    duration = end - start
    weights = [
        len("".join(text.split())) if is_cjk else len(text.split())
        for text, _ in chunks
    ]
    total_weight = sum(weights)
    if not weights or total_weight <= 0:
        raise SubtitleBuildError("Caption splitting produced an empty cue.")
    durations = [duration * weight / total_weight for weight in weights]
    if any(value + 1e-6 < minimum_duration for value in durations):
        raise SubtitleBuildError(
            "Exact subtitle needs multiple screens but its authored interval is too short."
        )
    intervals: list[tuple[float, float]] = []
    cursor = start
    for index, value in enumerate(durations):
        chunk_end = end if index == len(durations) - 1 else cursor + value
        intervals.append((cursor, chunk_end))
        cursor = chunk_end
    return intervals


def _minimum_display_interval(
    start: float,
    end: float,
    *,
    previous_end: float,
    next_start: float,
    minimum_duration: float,
) -> tuple[float, float]:
    if end - start + 1e-6 >= minimum_duration:
        return start, end
    missing = minimum_duration - (end - start)
    extend_after = min(missing, max(0.0, next_start - end))
    end += extend_after
    missing -= extend_after
    extend_before = min(missing, max(0.0, start - previous_end))
    start -= extend_before
    missing -= extend_before
    if missing > 1e-6:
        raise SubtitleBuildError(
            "Short subtitle cannot reach the current minimum display time without "
            "overlap or crossing its Segment boundary."
        )
    return start, end


def _required_display_duration(
    text: str,
    chunks: list[tuple[str, str]],
    *,
    is_cjk: bool,
    minimum_duration: float,
    style: dict[str, Any],
) -> float:
    """Return the shortest proportional caption interval that passes every limit."""

    weights = [
        len("".join(chunk_text.split())) if is_cjk else len(chunk_text.split())
        for chunk_text, _ in chunks
    ]
    total_weight = sum(weights)
    if not weights or any(weight <= 0 for weight in weights) or total_weight <= 0:
        raise SubtitleBuildError("Caption duration calculation produced an empty cue.")
    minimum_for_each_chunk = max(
        minimum_duration * total_weight / weight for weight in weights
    )
    if is_cjk:
        units_per_second = _number(
            style["maximum_characters_per_second_cjk"],
            "maximum_characters_per_second_cjk",
            minimum=0.1,
        )
    else:
        words_per_minute = _number(
            style["maximum_words_per_minute_latin"],
            "maximum_words_per_minute_latin",
            minimum=1,
        )
        units_per_second = words_per_minute / 60.0
    minimum_for_readability = total_weight / units_per_second
    return max(
        minimum_duration,
        minimum_for_each_chunk,
        minimum_for_readability,
    )


def _readability(text: str, duration: float, style: dict[str, Any]) -> dict[str, Any]:
    if duration <= 0:
        raise SubtitleBuildError("Subtitle duration must be positive.")
    if _is_cjk(text):
        count = len("".join(text.split()))
        rate = count / duration
        limit = _number(
            style["maximum_characters_per_second_cjk"],
            "maximum_characters_per_second_cjk",
            minimum=0.1,
        )
        mode = "characters_per_second"
    else:
        count = len(text.split())
        rate = count / duration * 60.0
        limit = _number(
            style["maximum_words_per_minute_latin"],
            "maximum_words_per_minute_latin",
            minimum=1,
        )
        mode = "words_per_minute"
    if rate > limit + 1e-6:
        raise SubtitleBuildError(
            f"Exact subtitle exceeds reading-speed limit: {rate:.2f} {mode}, "
            f"limit {limit:.2f}; increase the authored cue interval upstream."
        )
    return {
        "mode": mode,
        "unit_count": count,
        "rate": round(rate, 3),
        "limit": round(limit, 3),
        "status": "PASS",
    }


def _format_srt(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt(seconds: float) -> str:
    return _format_srt(seconds).replace(",", ".")


def _picture_events(edl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = edl.get("picture_events")
    if not isinstance(raw, list) or not raw:
        raise SubtitleBuildError("picture-audio-edl.json has no picture events.")
    boundaries = edl.get("boundaries")
    if not isinstance(boundaries, list) or len(boundaries) != len(raw) - 1:
        raise SubtitleBuildError(
            "picture-audio-edl.json has invalid boundary coverage."
        )
    result: dict[str, dict[str, Any]] = {}
    previous_out = 0.0
    previous_segment_id: str | None = None
    for index, event in enumerate(raw):
        if not isinstance(event, dict):
            raise SubtitleBuildError("Picture event must be an object.")
        segment_id = _segment_name(event.get("segment_id"))
        if segment_id in result:
            raise SubtitleBuildError(f"EDL repeats {segment_id}.")
        start = _number(event.get("timeline_in_seconds"), f"{segment_id} EDL in")
        end = _number(event.get("timeline_out_seconds"), f"{segment_id} EDL out")
        if end <= start:
            raise SubtitleBuildError(f"EDL timing is invalid at {segment_id}.")
        overlap = 0.0
        if index == 0:
            if abs(start) > 0.001:
                raise SubtitleBuildError("The first EDL picture event must start at zero.")
        else:
            boundary = boundaries[index - 1]
            if not isinstance(boundary, dict):
                raise SubtitleBuildError(f"Invalid incoming boundary for {segment_id}.")
            if (
                boundary.get("from") != previous_segment_id
                or boundary.get("to") != segment_id
            ):
                raise SubtitleBuildError(
                    f"EDL boundary order is invalid before {segment_id}."
                )
            overlap = _number(
                boundary.get("overlap_seconds"),
                f"{segment_id} incoming overlap",
            )
            if overlap < 0 or overlap >= end - start:
                raise SubtitleBuildError(
                    f"EDL overlap is invalid before {segment_id}."
                )
            expected_start = previous_out - overlap
            if abs(start - expected_start) > 0.001:
                raise SubtitleBuildError(
                    f"EDL timing does not match its authored boundary at {segment_id}."
                )
        result[segment_id] = {
            **event,
            "start": start,
            "end": end,
            "incoming_overlap_seconds": overlap,
        }
        previous_out = end
        previous_segment_id = segment_id
    return result


def compile_cues(task_dir: Path, style_path: Path) -> dict[str, Any]:
    task = _load_json(task_dir / "task.json")
    style = _load_json(style_path)
    _validate_style(style)
    edl_path = (
        task_dir
        / ".pending"
        / "finish-postproduction"
        / "post-production"
        / "picture-audio-edl.json"
    )
    edl = _load_json(edl_path)
    events = _picture_events(edl)
    storyboards = load_route_b_handoff(task_dir)
    storyboard_ids = list(storyboards)
    if storyboard_ids != list(events):
        raise SubtitleBuildError("Storyboard coverage/order differs from picture EDL.")
    language = _target_language(task)
    max_lines = int(style["max_lines"])
    if max_lines < 1:
        raise SubtitleBuildError("subtitle max_lines must be positive.")
    cues: list[dict[str, Any]] = []
    source_cue_count = 0
    editorial_refinement = edl.get("editorial_refinement")
    subtitle_timing_overrides = (
        editorial_refinement.get("subtitle_timing_overrides", {})
        if isinstance(editorial_refinement, dict)
        else {}
    )
    if not isinstance(subtitle_timing_overrides, dict):
        raise SubtitleBuildError("EDL subtitle_timing_overrides must be an object.")
    for segment_id, storyboard in storyboards.items():
        if storyboard.get("segment_id") != segment_id:
            raise SubtitleBuildError(f"Storyboard identity mismatch: {segment_id}")
        event = events[segment_id]
        event_duration = event["end"] - event["start"]
        storyboard_duration = _number(
            storyboard.get("duration_seconds"), f"{segment_id} Storyboard duration"
        )
        source_in = _number(
            event.get("source_in_seconds", 0.0), f"{segment_id} EDL source in"
        )
        source_out = _number(
            event.get("source_out_seconds"), f"{segment_id} EDL source out"
        )
        if source_in < 0 or source_out <= source_in:
            raise SubtitleBuildError(f"{segment_id} EDL source range is invalid.")
        if source_out > storyboard_duration + 0.25:
            raise SubtitleBuildError(
                f"{segment_id} EDL source out exceeds the Storyboard duration."
            )
        if abs(event_duration - (source_out - source_in)) > 0.05:
            raise SubtitleBuildError(
                f"{segment_id} EDL duration differs from its editorial source range."
            )
        ordered_source_cues = [
            cue
            for source_block in storyboard.get("timeline_blocks", [])
            if isinstance(source_block, dict)
            for cue in source_block.get("dialogue_cues", [])
            if isinstance(cue, dict)
        ]
        source_cue_positions = {
            id(source_cue): index
            for index, source_cue in enumerate(ordered_source_cues)
        }

        def source_interval(source_cue: dict[str, Any]) -> tuple[float, float, bool]:
            cue_id = str(source_cue.get("cue_id") or "")
            authored_start = _number(source_cue.get("start_seconds"), "cue start")
            authored_end = _number(source_cue.get("end_seconds"), "cue end")
            override = subtitle_timing_overrides.get(cue_id)
            if override is None:
                return authored_start, authored_end, False
            if not isinstance(override, dict):
                raise SubtitleBuildError(
                    f"Subtitle timing override must be an object: {cue_id}"
                )
            return (
                _number(
                    override.get("source_start_seconds"),
                    f"{cue_id} overridden source start",
                ),
                _number(
                    override.get("source_end_seconds"),
                    f"{cue_id} overridden source end",
                ),
                True,
            )

        for block in storyboard.get("timeline_blocks", []):
            if not isinstance(block, dict):
                raise SubtitleBuildError(f"{segment_id} contains an invalid block.")
            for cue in block.get("dialogue_cues", []):
                if not isinstance(cue, dict):
                    raise SubtitleBuildError(f"{segment_id} contains an invalid cue.")
                authored_start = _number(cue.get("start_seconds"), "cue start")
                authored_end = _number(cue.get("end_seconds"), "cue end")
                source_start, source_end, timing_overridden = source_interval(cue)
                if source_end <= source_start:
                    raise SubtitleBuildError(f"{segment_id} cue timing is invalid.")
                if source_start < source_in - 0.05 or source_end > source_out + 0.05:
                    raise SubtitleBuildError(
                        f"{segment_id} editorial trim intersects dialogue cue {cue.get('cue_id')}."
                    )
                relative_start = max(0.0, source_start - source_in)
                relative_end = min(event_duration, source_end - source_in)
                text = str(cue.get("exact_text", "")).strip()
                if not text:
                    raise SubtitleBuildError(f"{segment_id} cue has no exact text.")
                is_cjk = _is_cjk(text)
                line_limit = int(
                    style[
                        "max_characters_per_line_cjk"
                        if is_cjk
                        else "max_characters_per_line_latin"
                    ]
                )
                chunks = _caption_chunks(
                    text,
                    is_cjk=is_cjk,
                    line_limit=line_limit,
                    max_lines=max_lines,
                )
                minimum = _number(
                    style["minimum_cue_duration_seconds"],
                    "minimum_cue_duration_seconds",
                )
                required_duration = _required_display_duration(
                    text,
                    chunks,
                    is_cjk=is_cjk,
                    minimum_duration=minimum,
                    style=style,
                )
                source_position = source_cue_positions[id(cue)]
                previous_end = (
                    max(
                        0.0,
                        source_interval(ordered_source_cues[source_position - 1])[1]
                        - source_in,
                    )
                    if source_position > 0
                    else 0.0
                )
                next_start = (
                    min(
                        event_duration,
                        source_interval(ordered_source_cues[source_position + 1])[0]
                        - source_in,
                    )
                    if source_position + 1 < len(ordered_source_cues)
                    else event_duration
                )
                relative_start, relative_end = _minimum_display_interval(
                    relative_start,
                    relative_end,
                    previous_end=previous_end,
                    next_start=next_start,
                    minimum_duration=required_duration,
                )
                source_cue_count += 1
                intervals = _caption_intervals(
                    relative_start,
                    relative_end,
                    chunks,
                    is_cjk=is_cjk,
                    minimum_duration=minimum,
                )
                source_cue_id = str(cue.get("cue_id"))
                for part_index, ((chunk_text, rendered_text), interval) in enumerate(
                    zip(chunks, intervals), start=1
                ):
                    part_start, part_end = interval
                    part_duration = part_end - part_start
                    timeline_start = event["start"] + part_start
                    timeline_end = event["start"] + part_end
                    cues.append(
                        {
                            "cue_index": len(cues) + 1,
                            "segment_id": segment_id,
                            "block_id": block.get("block_id"),
                            "cue_id": (
                                source_cue_id
                                if len(chunks) == 1
                                else f"{source_cue_id}-caption-{part_index:02d}"
                            ),
                            "source_cue_id": source_cue_id,
                            "source_cue_part_index": part_index,
                            "source_cue_part_count": len(chunks),
                            "screenplay_reference": cue.get("screenplay_reference"),
                            "speaker_entity_id": cue.get("speaker_entity_id"),
                            "speaker_screenplay_identity_en": cue.get(
                                "speaker_screenplay_identity_en"
                            ),
                            "source_exact_text": text,
                            "exact_text": chunk_text,
                            "rendered_text": rendered_text,
                            "language": language,
                            "authored_segment_start_seconds": round(authored_start, 3),
                            "authored_segment_end_seconds": round(authored_end, 3),
                            "source_segment_start_seconds": round(source_start, 3),
                            "source_segment_end_seconds": round(source_end, 3),
                            "editorial_timing_override_applied": timing_overridden,
                            "segment_start_seconds": round(part_start, 3),
                            "segment_end_seconds": round(part_end, 3),
                            "timeline_start_seconds": round(timeline_start, 3),
                            "timeline_end_seconds": round(timeline_end, 3),
                            "readability": _readability(
                                chunk_text, part_duration, style
                            ),
                        }
                    )
    for previous, current in zip(cues, cues[1:]):
        if current["timeline_start_seconds"] < previous["timeline_end_seconds"] - 0.001:
            raise SubtitleBuildError(
                f"Subtitle cues overlap: {previous['cue_id']} and {current['cue_id']}."
            )
    return {
        "contract": "finish-subtitle-cues-v2",
        "text_authority": "seed_master_route_b_exact_dialogue_ledger",
        "timing_authority": "seed_master_route_b_dialogue_duration_ledger_plus_picture_edl",
        "language": language,
        "style_path": str(style_path.resolve()),
        "picture_edl_path": str(edl_path.resolve()),
        "source_cue_count": source_cue_count,
        "cue_count": len(cues),
        "cues": cues,
    }


def _write_subtitle_files(output_dir: Path, authority: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cues_path = output_dir / "subtitle-cues.json"
    srt_path = output_dir / "master.srt"
    vtt_path = output_dir / "master.vtt"
    cues_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    srt_blocks = []
    vtt_blocks = ["WEBVTT", ""]
    for cue in authority["cues"]:
        index = cue["cue_index"]
        start = cue["timeline_start_seconds"]
        end = cue["timeline_end_seconds"]
        text = cue["rendered_text"]
        srt_blocks.append(
            f"{index}\n{_format_srt(start)} --> {_format_srt(end)}\n{text}"
        )
        vtt_blocks.append(
            f"{index}\n{_format_vtt(start)} --> {_format_vtt(end)}\n{text}\n"
        )
    srt_path.write_text("\n\n".join(srt_blocks) + ("\n" if srt_blocks else ""), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_blocks), encoding="utf-8")
    return cues_path, srt_path, vtt_path


def _probe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        value = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SubtitleBuildError(f"Could not probe media: {path}") from exc
    streams = value.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    return {
        "duration_seconds": float(value.get("format", {}).get("duration", 0)),
        "width": int(video.get("width", 0)) if isinstance(video, dict) else 0,
        "height": int(video.get("height", 0)) if isinstance(video, dict) else 0,
        "video_stream_present": isinstance(video, dict),
        "audio_stream_present": any(item.get("codec_type") == "audio" for item in streams),
    }


def _clean_master(task_dir: Path) -> Path:
    candidate = task_dir / "finish-postproduction" / "final-clean-master.mp4"
    if not candidate.is_file() or candidate.stat().st_size <= 0:
        raise SubtitleBuildError("Missing final-clean-master.mp4.")
    return candidate.resolve()


def _ass_color(rgb: str) -> str:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", rgb):
        raise SubtitleBuildError(f"Invalid subtitle color: {rgb}")
    red, green, blue = rgb[1:3], rgb[3:5], rgb[5:7]
    return f"&H00{blue}{green}{red}".upper()


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_captioned_master(
    task_dir: Path,
    *,
    style: dict[str, Any],
    srt_path: Path,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    source = _clean_master(task_dir)
    source_probe = _probe(source)
    if not source_probe["video_stream_present"] or not source_probe["audio_stream_present"]:
        raise SubtitleBuildError("Clean master must contain video and audio streams.")
    delivery_root = task_dir / "finish-postproduction"
    delivery_root.mkdir(parents=True, exist_ok=True)
    clean_output = delivery_root / "final-clean-master.mp4"
    height = source_probe["height"]
    if height <= 0:
        raise SubtitleBuildError("Clean master has an invalid frame height.")
    # SRT is converted by libass on its 384x288 script canvas, then scaled to the
    # output frame. Express percentage-based style values in that coordinate space
    # so they are not multiplied by the output-height/script-height ratio twice.
    ass_scale = ASS_PLAY_RESOLUTION_HEIGHT / height
    font_size = max(
        12.0 * ass_scale,
        ASS_PLAY_RESOLUTION_HEIGHT
        * float(style["font_size_percent_of_frame_height"])
        / 100,
    )
    outline = max(
        1.0 * ass_scale,
        ASS_PLAY_RESOLUTION_HEIGHT
        * float(style["outline_width_percent_of_frame_height"])
        / 100,
    )
    margin_v = max(
        0.0,
        ASS_PLAY_RESOLUTION_HEIGHT * float(style["bottom_margin_percent"]) / 100,
    )
    force_style = ",".join(
        (
            f"FontName={style['font_family']}",
            f"FontSize={font_size:.3f}",
            f"PrimaryColour={_ass_color(str(style['text_color']))}",
            f"OutlineColour={_ass_color(str(style['outline_color']))}",
            f"Outline={outline:.3f}",
            "BorderStyle=1",
            "Alignment=2",
            f"MarginV={margin_v:.3f}",
        )
    )
    captioned = delivery_root / "final-captioned-master.mp4"
    filter_value = f"subtitles=filename='{_filter_path(srt_path)}':force_style='{force_style}'"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(clean_output),
        "-vf",
        filter_value,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(captioned),
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SubtitleBuildError("Captioned-master render failed.") from exc
    captioned_probe = _probe(captioned)
    if (
        not captioned_probe["video_stream_present"]
        or not captioned_probe["audio_stream_present"]
        or abs(captioned_probe["duration_seconds"] - source_probe["duration_seconds"]) > 0.1
    ):
        raise SubtitleBuildError("Captioned master does not match clean-master duration/streams.")
    return clean_output, captioned, source_probe, captioned_probe


def build(task_dir: Path, style_path: Path, *, render: bool) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    style_path = style_path.expanduser().resolve()
    authority = compile_cues(task_dir, style_path)
    subtitle_dir = task_dir / "finish-postproduction" / "subtitles"
    cues_path, srt_path, vtt_path = _write_subtitle_files(subtitle_dir, authority)
    result: dict[str, Any] = {
        "status": "SUBTITLES_READY",
        "cue_count": authority["cue_count"],
        "subtitle_cues": str(cues_path),
        "srt": str(srt_path),
        "vtt": str(vtt_path),
    }
    if render:
        style = _load_json(style_path)
        _validate_style(style)
        clean, captioned, clean_probe, captioned_probe = render_captioned_master(
            task_dir, style=style, srt_path=srt_path
        )
        task = _load_json(task_dir / "task.json")
        if (
            task.get("voice_audio_source") != "speaker_reference_audio"
            or task.get("dialogue_source") != "seedance"
        ):
            raise SubtitleBuildError(
                "task.json must use speaker_reference_audio for voice identity and seedance for dialogue."
            )
        audio_timeline_path = (
            task_dir / ".pending" / "finish-postproduction" / "audio-timeline.json"
        )
        audio_timeline = _load_json(audio_timeline_path)
        if audio_timeline.get("seedance_background_music") is not False:
            raise SubtitleBuildError(
                "audio-timeline.json must declare seedance_background_music=false"
            )
        music_provider = audio_timeline.get("music_provider")
        if music_provider != "none":
            raise SubtitleBuildError(
                "Main final delivery requires music_provider=none"
            )
        boundary_qc_path = (
            task_dir
            / ".pending"
            / "finish-postproduction"
            / "boundary-qc"
            / "boundary-qc-manifest.json"
        )
        boundary_qc = _load_json(boundary_qc_path)
        if (
            boundary_qc.get("pre_assembly_status") != "ready_for_picture_lock"
            or boundary_qc.get("final_timeline_status")
            != "technical_audit_complete"
        ):
            raise SubtitleBuildError(
                "Boundary QC must complete before clean/captioned delivery"
            )
        manifest = {
            "contract": "finish-final-delivery",
            "state": "FINAL_MASTER_READY",
            "clean_master": {"path": str(clean.resolve())},
            "captioned_master": {"path": str(captioned.resolve())},
            "subtitles": {
                "cue_count": authority["cue_count"],
                "cues_path": str(cues_path.resolve()),
                "srt_path": str(srt_path.resolve()),
                "vtt_path": str(vtt_path.resolve()),
            },
            "duration_seconds": round(clean_probe["duration_seconds"], 3),
            "resolution": {
                "width": clean_probe["width"],
                "height": clean_probe["height"],
            },
            "video_stream_present": captioned_probe["video_stream_present"],
            "audio_stream_present": captioned_probe["audio_stream_present"],
            "audio_sources": {
                "voice_audio_source": "speaker_reference_audio",
                "dialogue_source": "seedance",
                "native_background_audio_source": "seedance_ambience_and_foley_no_music",
                "seedance_background_music": False,
                "background_music_source": music_provider,
                "generate_audio": True,
            },
            "audio_timeline": str(audio_timeline_path.resolve()),
            "boundary_qc": {
                "manifest": str(boundary_qc_path.resolve()),
                "pre_assembly_status": boundary_qc["pre_assembly_status"],
                "final_timeline_status": boundary_qc["final_timeline_status"],
                "planned_repair_count": boundary_qc.get(
                    "planned_repair_count", 0
                ),
                "source_segments_mutated": False,
            },
            "clean_captioned_duration_match": True,
        }
        manifest_path = task_dir / "finish-postproduction" / "final-delivery-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result.update(
            {
                "status": "FINAL_MASTER_READY",
                "clean_master": str(clean),
                "captioned_master": str(captioned),
                "delivery_manifest": str(manifest_path),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--style", type=Path, default=DEFAULT_STYLE)
    parser.add_argument(
        "--render-captioned",
        action="store_true",
        help="Render final-clean-master.mp4 and final-captioned-master.mp4 after subtitle compilation.",
    )
    args = parser.parse_args()
    try:
        result = build(args.task_dir, args.style, render=args.render_captioned)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
