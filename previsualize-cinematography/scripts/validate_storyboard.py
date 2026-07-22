#!/usr/bin/env python3
"""Validate the single-file cinematic Storyboard release without authoring it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


REQUIRED_HEADINGS = (
    "## Project Direction",
    "## Generation Plan",
    "## Location State Plan",
    "## Continuity Review",
)
SEGMENT_HEADING_RE = re.compile(r"^## Generation Segment ([1-9][0-9]*) — .+$", re.M)
JSONISH_RE = re.compile(r"```(?:json|yaml|yml)|\{\s*[\"']|\[\s*\{", re.I)
REQUIRED_SEGMENT_SUBHEADINGS = (
    "### Segment Direction",
    "### Reference Plan",
    "### Ordered Shots",
    "### Prompt Translation Notes",
)
LOCATION_STATE_HEADERS = (
    "Location State Chain",
    "Segment",
    "Relationship",
    "State Source",
    "Temporal Evidence",
    "World and Population Evidence",
    "Persistent Anchors",
    "Allowed Changes",
)
LOCATION_RELATIONSHIPS = {
    "independent",
    "adjacent_continuation",
    "nonadjacent_revisit",
    "reset_with_reason",
}


class StoryboardValidationError(RuntimeError):
    pass


def _storyboard_shot_ids(text: str) -> list[str]:
    return re.findall(r"\|\s*(A-[0-9]{3})\s*\|", text)


def _screenplay_shot_ids(text: str) -> list[str]:
    return re.findall(r"^\|\s*(A-[0-9]{3})\s*\|", text, re.M)


def _table_after_heading(text: str, heading: str) -> tuple[list[str], list[list[str]]]:
    start = text.find(heading)
    if start < 0:
        raise StoryboardValidationError(f"Missing {heading}")
    section = text[start + len(heading):]
    next_heading = re.search(r"^## ", section, re.M)
    if next_heading:
        section = section[:next_heading.start()]
    lines = section.splitlines()
    table_start = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("|")),
        None,
    )
    if table_start is None or table_start + 1 >= len(lines):
        raise StoryboardValidationError(f"{heading} must contain one Markdown table")

    def cells(line: str) -> list[str]:
        return [item.strip() for item in line.strip().strip("|").split("|")]

    headers = cells(lines[table_start])
    separator = cells(lines[table_start + 1])
    if len(separator) != len(headers) or any(not re.fullmatch(r":?-{3,}:?", item) for item in separator):
        raise StoryboardValidationError(f"{heading} has an invalid table separator")
    rows: list[list[str]] = []
    for line in lines[table_start + 2:]:
        if not line.strip().startswith("|"):
            if rows:
                break
            continue
        row = cells(line)
        if len(row) != len(headers):
            raise StoryboardValidationError(f"{heading} has an invalid table row")
        rows.append(row)
    if not rows:
        raise StoryboardValidationError(f"{heading} table must not be empty")
    return headers, rows


def _validate_location_state_plan(text: str, segment_count: int) -> None:
    headers, rows = _table_after_heading(text, "## Location State Plan")
    if tuple(headers) != LOCATION_STATE_HEADERS:
        raise StoryboardValidationError(
            "Location State Plan columns differ from the current contract"
        )
    expected_segments = [f"segment-{index:03d}" for index in range(1, segment_count + 1)]
    segments = [row[1] for row in rows]
    if segments != expected_segments:
        raise StoryboardValidationError(
            "Location State Plan must contain every Generation Segment exactly once in order"
        )
    prior_by_chain: dict[str, str] = {}
    for index, row in enumerate(rows):
        (
            chain,
            segment,
            relationship,
            source,
            temporal_evidence,
            world_evidence,
            anchors,
            allowed,
        ) = row
        if not chain or relationship not in LOCATION_RELATIONSHIPS:
            raise StoryboardValidationError(f"{segment} has an invalid location-state relationship")
        if not world_evidence or world_evidence.casefold() == "none":
            raise StoryboardValidationError(
                f"{segment} lacks world and population evidence"
            )
        previous_in_chain = prior_by_chain.get(chain)
        if previous_in_chain is None:
            if relationship not in {"independent", "reset_with_reason"} or source.casefold() != "none":
                raise StoryboardValidationError(
                    f"{segment} starts location state chain {chain!r} without an independent/reset origin"
                )
        elif relationship in {"independent"}:
            raise StoryboardValidationError(
                f"{segment} revisits location state chain {chain!r} but is marked independent"
            )
        elif relationship in {"adjacent_continuation", "nonadjacent_revisit"}:
            if source != previous_in_chain:
                raise StoryboardValidationError(
                    f"{segment} must inherit the latest prior Segment in location state chain {chain!r}"
                )
            previous_global = expected_segments[index - 1] if index else None
            if relationship == "adjacent_continuation" and source != previous_global:
                raise StoryboardValidationError(f"{segment} is not an adjacent continuation")
            if relationship == "nonadjacent_revisit" and source == previous_global:
                raise StoryboardValidationError(f"{segment} is adjacent, not a nonadjacent revisit")
            if temporal_evidence.casefold() == "none" or not temporal_evidence:
                raise StoryboardValidationError(f"{segment} lacks temporal evidence")
        if anchors.casefold() == "none" or not anchors:
            raise StoryboardValidationError(f"{segment} lacks persistent anchors")
        if relationship == "reset_with_reason" and (not allowed or allowed.casefold() == "none"):
            raise StoryboardValidationError(f"{segment} reset has no authored reason")
        prior_by_chain[chain] = segment


def validate_storyboard(task_dir: Path) -> dict:
    task_dir = task_dir.expanduser().resolve(strict=True)
    release_dir = task_dir / "previsualize-cinematography"
    storyboard = release_dir / "storyboard.md"
    if not storyboard.is_file():
        raise StoryboardValidationError(f"Missing sole release: {storyboard}")
    files = sorted(path.name for path in release_dir.iterdir() if path.is_file())
    if files != ["storyboard.md"]:
        raise StoryboardValidationError(
            "previsualize-cinematography must contain only storyboard.md"
        )
    text = storyboard.read_text(encoding="utf-8")
    if not re.match(r"^# Cinematic Storyboard: .+", text):
        raise StoryboardValidationError("Storyboard title is missing or invalid")
    if JSONISH_RE.search(text):
        raise StoryboardValidationError("Storyboard contains JSON or YAML")
    positions = [text.find(heading) for heading in REQUIRED_HEADINGS]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise StoryboardValidationError("Required top-level sections are missing or out of order")
    matches = list(SEGMENT_HEADING_RE.finditer(text))
    numbers = [int(match.group(1)) for match in matches]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        raise StoryboardValidationError("Generation Segment headings must be consecutive from 1")
    _validate_location_state_plan(text, len(numbers))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else positions[-1]
        section = text[match.end():end]
        sub_positions = [section.find(heading) for heading in REQUIRED_SEGMENT_SUBHEADINGS]
        if any(position < 0 for position in sub_positions) or sub_positions != sorted(sub_positions):
            raise StoryboardValidationError(
                f"Generation Segment {numbers[index]} sections are missing or out of order"
            )
        for field in (
            "Location State Chain",
            "Temporal Continuity Evidence",
            "World and Population Evidence",
            "Authorized Population",
            "Persistent Anchors",
            "Anchor Visibility Requirement",
        ):
            if not re.search(rf"^\|\s*{re.escape(field)}\s*\|\s*\S", section, re.M):
                raise StoryboardValidationError(
                    f"Generation Segment {numbers[index]} lacks {field}"
                )
        ordered_shots = section.split("### Ordered Shots", 1)[1].split(
            "### Prompt Translation Notes", 1
        )[0]
        if "| Persistent Anchors |" not in ordered_shots:
            raise StoryboardValidationError(
                f"Generation Segment {numbers[index]} Ordered Shots lack Persistent Anchors"
            )
    screenplay = task_dir / "screenplay-writer/screenplay.md"
    if screenplay.is_file():
        expected = _screenplay_shot_ids(screenplay.read_text(encoding="utf-8"))
        actual = _storyboard_shot_ids(text)
        if expected != actual:
            raise StoryboardValidationError(
                "Storyboard Shot coverage or order differs from the approved screenplay"
            )
    return {
        "status": "PASS",
        "storyboard": str(storyboard),
        "generation_segment_count": len(numbers),
        "screenplay_shot_count": len(_storyboard_shot_ids(text)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_storyboard(args.task_dir)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
