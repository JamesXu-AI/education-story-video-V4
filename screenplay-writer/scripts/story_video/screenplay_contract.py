"""Parse and validate the effect-first Seedance Segment screenplay contract."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from story_video.runtime_support import (
    StoryVideoError,
    TARGET_AGE_BANDS,
    fixed_prompt_path,
    require_utf8_text,
)


SCREENPLAY_PROMPT_FILENAME = "story_to_screenplay_gen.md"
TITLE_RE = re.compile(r"^# Seedance Screenplay: (.+)$")
META_RE = re.compile(
    r"^- (Target language|Target age band|Seedance mapping|Segment duration policy|"
    r"Segment boundary policy):\s*(.+)$"
)
SEGMENT_RE = re.compile(r"^## Segment ([1-9][0-9]*)$")
SLUGLINE_RE = re.compile(r"^\*\*((?:INT|EXT)\. .+ - .+)\*\*$")
BOLD_RE = re.compile(r"^\*\*(.+)\*\*$")
PLAN_FIELD_RE = re.compile(r"^- `([a-z][a-z0-9_]*)`:\s*(.+)$")
SCENE_ID_RE = re.compile(r"^scene-[0-9]{3,}$")
SEGMENT_ID_RE = re.compile(r"^segment-[0-9]{3,}$")
STATE_ID_RE = re.compile(r"^state-[0-9]{3,}$")
BOUNDARY_ID_RE = re.compile(r"^boundary-[0-9]{3,}$")
ENVIRONMENT_ID_RE = re.compile(r"^environment-[0-9]{3,}$")
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*")

# Shared deterministic timing/structure limits. The screenplay validator and the
# screenplay-owned audio projection must use the same values.
DIALOGUE_WORDS_PER_SECOND = 2.6
DIALOGUE_TURN_ALLOWANCE_SECONDS = 0.25
MINIMUM_ACTION_REACTION_SECONDS = 1.0
MINIMUM_SEGMENT_BLOCK_COUNT = 3
DIALOGUE_OCCUPANCY_LIMITS = {
    "action_led": 0.45,
    "mixed_dialogue_action": 0.60,
    "dialogue_led": 0.72,
}

META_ORDER = (
    "Target language",
    "Target age band",
    "Seedance mapping",
    "Segment duration policy",
    "Segment boundary policy",
)
CHARACTER_TABLE_COLUMNS = (
    "Character",
    "Story Role",
    "Narrative Function",
    "Narration Eligibility",
    "Narration Scope",
    "Description",
)
CHARACTER_STORY_ROLES = {"lead", "supporting", "npc"}
NARRATION_ELIGIBILITIES = {"allowed", "conditional", "not_allowed"}
ENVIRONMENT_TABLE_COLUMNS = (
    "Environment ID",
    "Logical Environment",
    "Scene IDs JSON",
    "INT/EXT",
    "Time Context",
    "Environment Facts",
    "Story Function",
)
ENVIRONMENT_KINDS = {"INT", "EXT", "MIXED"}
SCENE_TABLE_COLUMNS = (
    "Scene ID",
    "Segment IDs JSON",
    "Primary Time",
    "Primary Place",
    "Narrative Event",
    "Entry Boundary",
    "Entry Reason",
    "Continuity Reference Segment",
    "Continuity Reference Reason",
)
SCENE_ENTRY_BOUNDARIES = {
    "opening",
    "time_change",
    "place_change",
    "time_and_place_change",
    "narrative_event_change",
}
CONTINUITY_STATE_TABLE_COLUMNS = (
    "State ID",
    "Character Identity",
    "Character Relationships",
    "Costume and Appearance State",
    "Character Knowledge",
    "Emotional State",
    "Injury and Body State",
    "Prop Ownership",
    "Prop State",
    "Location Facts",
    "Time Order",
    "Event Causality",
    "Story Logic",
)
CONTINUITY_BOUNDARY_TABLE_COLUMNS = (
    "Boundary ID",
    "From Segment",
    "To Segment",
    "From State",
    "To State",
    "Anchor Policy JSON",
)
STATE_REF_KEYS = frozenset({"state_ref"})
ANCHOR_POLICY_KEYS = frozenset({"default", "overrides"})
ANCHOR_POLICY_DEFAULT_KEYS = frozenset({"status", "reason_en"})
ANCHOR_POLICY_OVERRIDE_KEYS = frozenset({"status", "reason_en"})
SCREENPLAY_SEGMENT_FIELDS = (
    "segment_id",
    "scene_id",
    "estimated_duration_seconds",
    "dramatic_workload",
    "location_time_environment_en",
    "characters_json",
    "narrative_purpose_en",
    "scene_dramatic_contract_json",
    "dramatic_beats_json",
    "start_state_json",
    "end_state_json",
    "transition_design_json",
    "incoming_visual_requirement",
)
SCENE_DRAMATIC_FIELDS = (
    "scene_id",
    "scene_purpose",
    "character_objective",
    "obstacle",
    "power_relationship",
    "turning_point",
    "outcome",
    "visual_progression",
    "exit_impulse",
)
DRAMATIC_BEAT_FIELDS = (
    "beat_id",
    "narrative_change",
    "active_character",
    "physical_objective",
    "visible_action",
    "important_reaction",
    "spatial_change",
    "dialogue_or_sound",
    "entry_state",
    "exit_state",
    "action_subject",
    "reaction_subject",
    "supporting_group",
    "atmosphere_presence",
    "visual_focus",
    "block_indexes",
)
DRAMATIC_BEAT_ID_RE = re.compile(r"^BEAT-[A-Za-z0-9_.-]+$")
STAGE_TABLEAU_RISK_RE = re.compile(
    r"\b(?:all\s+(?:the\s+)?(?:animals|characters|people|villagers|students|guests|"
    r"workers|soldiers|courtiers)|everyone|the\s+(?:animals|characters|group|cast|crowd))\b"
    r"[^.!?]{0,100}\b(?:stand|stands|stood|standing|line\s+up|lined\s+up|semicircle)\b|"
    r"\b(?:take|takes|took)\s+turns?\s+(?:speaking|talking|answering)\b|"
    r"\b(?:face|faces|facing|look|looks|looking)\s+(?:at|toward)?\s*(?:the\s+)?camera\b",
    re.I,
)
INCOMING_VISUAL_REQUIREMENTS = {
    "independent",
    "state_match",
    "continuous_motion",
}
TRANSITION_DESIGN_TYPES = {
    "hard_cut",
    "action_cut",
    "match_cut",
    "eyeline_cut",
    "reaction_cut",
    "dissolve",
    "fade",
    "animated_wipe",
    "animated_morph",
    "animated_match",
    "effects_wipe",
    "light_flash_transition",
    "particle_bridge",
    "environmental_transition",
    "final_end",
}
TRANSITION_DESIGN_FIELDS = (
    "type",
    "reason_en",
    "outgoing_visible_en",
    "outgoing_audio_en",
    "incoming_visible_en",
    "incoming_audio_en",
    "narrative_link_en",
    "action_link_en",
    "spatial_link_en",
    "sound_link_en",
)
TRANSITION_DESIGN_KEYS = frozenset(TRANSITION_DESIGN_FIELDS)
CONTINUITY_CATEGORIES = (
    "character_identity",
    "character_relationships",
    "costume_and_appearance_state",
    "character_knowledge",
    "emotional_state",
    "injury_and_body_state",
    "prop_ownership",
    "prop_state",
    "location_facts",
    "time_order",
    "event_causality",
    "story_logic",
)
CONTINUITY_ANCHOR_STATUSES = {
    "preserve",
    "evolve",
    "intentional_change",
    "not_applicable",
}
CONTINUITY_ANCHOR_FIELDS = (
    "category",
    "status",
    "from_en",
    "to_en",
    "reason_en",
)
CONTINUITY_ANCHOR_KEYS = frozenset(CONTINUITY_ANCHOR_FIELDS)
FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE = re.compile(
    r"\b(?:previous|predecessor)\s+(?:last|final)\s+frame\b|"
    r"\b(?:previous|predecessor)\s+(?:full\s+)?video\b|"
    r"\b(?:dialogue|spoken\s+line|lip\s*sync|native\s+sound)\s+"
    r"(?:continues|carries|bridges|crosses|spans)\b|"
    r"\b(?:continue|carry|bridge|split)\s+(?:the\s+)?"
    r"(?:same\s+)?(?:dialogue|spoken\s+line|lip\s*sync|native\s+sound)\b",
    re.I,
)
INHERITED_VISUAL_PHASE_RE = re.compile(
    r"\b(?:continue|continues|continued|continuing|resume|resumes|inherit|inherits|"
    r"preserve|preserves|match|matches)\b[^.]{0,100}\b"
    r"(?:motion|movement|action\s+phase|body\s+phase|pose|position|facing|"
    r"screen\s+direction|eyeline|blocking|camera\s+(?:move|motion|phase)|"
    r"performance\s+phase)\b|"
    r"\b(?:same|exact|unfinished|inherited)\b[^.]{0,80}\b"
    r"(?:motion|movement|pose|position|facing|blocking|camera|performance\s+phase)\b",
    re.I,
)


def fixed_screenplay_prompt() -> tuple[Path, str]:
    path = fixed_prompt_path("screenplay", SCREENPLAY_PROMPT_FILENAME)
    try:
        prompt = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoryVideoError(f"Cannot read fixed Screenplay Prompt: {path}") from exc
    if "# Seedance-Native Screenplay Generation Prompt" not in prompt:
        raise StoryVideoError(f"Invalid fixed Screenplay Prompt: {path}")
    return path, prompt


def _next_nonempty(lines: list[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _paragraph(lines: list[str], index: int) -> tuple[str, int]:
    chunks: list[str] = []
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            break
        if line.startswith("## ") or BOLD_RE.fullmatch(line):
            break
        chunks.append(line)
        index += 1
    if not chunks:
        raise StoryVideoError("screenplay.md contains an empty action/dialogue paragraph")
    return " ".join(chunks), index


def _table_cells(line: str, *, label: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise StoryVideoError(f"{label} must use a Markdown table row")
    body = stripped[1:-1]
    cells: list[str] = []
    current: list[str] = []
    cursor = 0
    while cursor < len(body):
        character = body[cursor]
        if (
            character == "\\"
            and cursor + 1 < len(body)
            and body[cursor + 1] in {"\\", "|"}
        ):
            current.append(body[cursor + 1])
            cursor += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        cursor += 1
    cells.append("".join(current).strip())
    return cells


def _parse_table(
    lines: list[str],
    index: int,
    *,
    columns: tuple[str, ...],
    label: str,
    allow_empty: bool = False,
) -> tuple[list[dict[str, str]], int]:
    index = _next_nonempty(lines, index)
    if index >= len(lines) or tuple(_table_cells(lines[index], label=label)) != columns:
        raise StoryVideoError(f"{label} must use the exact ordered columns")
    index += 1
    if index >= len(lines):
        raise StoryVideoError(f"{label} is missing its separator row")
    separator = _table_cells(lines[index], label=label)
    if len(separator) != len(columns) or any(
        not re.fullmatch(r":?-{3,}:?", cell) for cell in separator
    ):
        raise StoryVideoError(f"{label} has an invalid separator row")
    index += 1
    rows: list[dict[str, str]] = []
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            break
        if stripped.startswith("## "):
            break
        cells = _table_cells(lines[index], label=label)
        if len(cells) != len(columns):
            raise StoryVideoError(f"{label} row has the wrong column count")
        if any(not cell for cell in cells):
            raise StoryVideoError(f"{label} cells must not be empty")
        rows.append(dict(zip(columns, cells)))
        index += 1
    if not rows and not allow_empty:
        raise StoryVideoError(f"{label} must contain at least one row")
    return rows, index


def _json_value(raw: str, *, segment_id: int, field: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StoryVideoError(
            f"screenplay.md Segment {segment_id} `{field}` must be one-line JSON: {exc.msg}"
        ) from exc


def _parse_story_plan(
    lines: list[str], index: int, segment_id: int
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    for expected in SCREENPLAY_SEGMENT_FIELDS:
        index = _next_nonempty(lines, index)
        if index >= len(lines):
            raise StoryVideoError(
                f"screenplay.md Segment {segment_id} is missing `{expected}`"
            )
        match = PLAN_FIELD_RE.fullmatch(lines[index].strip())
        if not match or match.group(1) != expected:
            actual = match.group(1) if match else lines[index].strip()
            raise StoryVideoError(
                f"screenplay.md Segment {segment_id} expected `{expected}` before `{actual}`"
            )
        raw = require_utf8_text(match.group(2), f"Segment {segment_id} {expected}")
        if expected == "estimated_duration_seconds":
            if not raw.isdigit():
                raise StoryVideoError(
                    f"screenplay.md Segment {segment_id} duration must be an integer"
                )
            value: Any = int(raw)
        elif expected.endswith("_json"):
            value = _json_value(raw, segment_id=segment_id, field=expected)
        else:
            value = raw
        result[expected] = value
        index += 1
    return result, index


def _parse_segment_content(
    lines: list[str], index: int, characters: dict[str, str]
) -> tuple[list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    while True:
        index = _next_nonempty(lines, index)
        if index >= len(lines) or SEGMENT_RE.fullmatch(lines[index].strip()):
            break
        line = lines[index].strip()
        speaker_match = BOLD_RE.fullmatch(line)
        if speaker_match:
            raw_speaker = speaker_match.group(1).strip()
            speaker_mode_match = re.search(r"\s+\((V\.O\.|O\.S\.)\)$", raw_speaker, re.I)
            normalized = re.sub(
                r"\s+\((?:V\.O\.|O\.S\.)\)$", "", raw_speaker, flags=re.I
            ).strip()
            display = characters.get(normalized.casefold(), "")
            if not display:
                raise StoryVideoError(
                    f"screenplay.md speaker '{raw_speaker}' is not declared in the Characters table"
                )
            index = _next_nonempty(lines, index + 1)
            delivery: str | None = None
            if index < len(lines) and re.fullmatch(r"\(.+\)", lines[index].strip()):
                delivery = lines[index].strip()[1:-1].strip()
                index = _next_nonempty(lines, index + 1)
            spoken, index = _paragraph(lines, index)
            blocks.append(
                {
                    "type": "dialogue",
                    "speaker_en": display,
                    "speaker_cue_en": raw_speaker,
                    "speaker_mode": (
                        speaker_mode_match.group(1).upper() if speaker_mode_match else None
                    ),
                    "delivery_en": delivery,
                    "spoken_text_en": spoken,
                }
            )
        else:
            action, index = _paragraph(lines, index)
            blocks.append({"type": "action", "text_en": action})
    return blocks, index


def _expect_section(lines: list[str], index: int, heading: str) -> int:
    index = _next_nonempty(lines, index)
    if index >= len(lines) or lines[index].strip() != heading:
        raise StoryVideoError(f"screenplay.md must declare {heading}")
    return index + 1


def _parse_characters_header(
    lines: list[str], index: int
) -> tuple[list[dict[str, str]], dict[str, str], int]:
    rows, index = _parse_table(
        lines,
        index,
        columns=CHARACTER_TABLE_COLUMNS,
        label="Characters table",
    )
    characters: list[dict[str, str]] = []
    character_map: dict[str, str] = {}
    for row_index, row in enumerate(rows, start=1):
        name = require_utf8_text(row["Character"], f"Characters row {row_index}")
        folded = name.casefold()
        if folded in character_map:
            raise StoryVideoError(f"screenplay.md repeats character {name}")
        character_map[folded] = name
        characters.append(
            {
                "name_en": name,
                "story_role": row["Story Role"],
                "narrative_function_en": row["Narrative Function"],
                "narration_eligibility": row["Narration Eligibility"],
                "narration_scope_en": row["Narration Scope"],
                "description_en": row["Description"],
            }
        )
    return characters, character_map, index


def _parse_environments_header(
    lines: list[str], index: int
) -> tuple[list[dict[str, Any]], int]:
    rows, index = _parse_table(
        lines,
        index,
        columns=ENVIRONMENT_TABLE_COLUMNS,
        label="Environments table",
    )
    environments: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        try:
            scene_ids = json.loads(row["Scene IDs JSON"])
        except json.JSONDecodeError as exc:
            raise StoryVideoError(
                f"Environments row {row_index} Scene IDs JSON is invalid"
            ) from exc
        environments.append(
            {
                "environment_id": row["Environment ID"],
                "logical_name_en": row["Logical Environment"],
                "scene_ids_json": scene_ids,
                "int_ext": row["INT/EXT"],
                "time_context_en": row["Time Context"],
                "environment_facts_en": row["Environment Facts"],
                "story_function_en": row["Story Function"],
            }
        )
    return environments, index


def _parse_scenes_header(
    lines: list[str], index: int
) -> tuple[list[dict[str, Any]], int]:
    rows, index = _parse_table(
        lines,
        index,
        columns=SCENE_TABLE_COLUMNS,
        label="Scenes table",
    )
    scenes: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        try:
            segment_ids = json.loads(row["Segment IDs JSON"])
        except json.JSONDecodeError as exc:
            raise StoryVideoError(
                f"Scenes row {row_index} Segment IDs JSON is invalid"
            ) from exc
        scenes.append(
            {
                "scene_id": row["Scene ID"],
                "segment_ids_json": segment_ids,
                "primary_time_en": row["Primary Time"],
                "primary_place_en": row["Primary Place"],
                "narrative_event_en": row["Narrative Event"],
                "entry_boundary": row["Entry Boundary"],
                "entry_reason_en": row["Entry Reason"],
                "continuity_reference_segment_id": row[
                    "Continuity Reference Segment"
                ],
                "continuity_reference_reason_en": row[
                    "Continuity Reference Reason"
                ],
            }
        )
    return scenes, index


def _parse_continuity_states_header(
    lines: list[str], index: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], int]:
    rows, index = _parse_table(
        lines,
        index,
        columns=CONTINUITY_STATE_TABLE_COLUMNS,
        label="Continuity States table",
    )
    states: list[dict[str, Any]] = []
    state_map: dict[str, dict[str, str]] = {}
    for row_index, row in enumerate(rows, start=1):
        state_id = row["State ID"]
        if state_id in state_map:
            raise StoryVideoError(f"Continuity States repeats {state_id}")
        values = {
            category: row[column]
            for category, column in zip(
                CONTINUITY_CATEGORIES, CONTINUITY_STATE_TABLE_COLUMNS[1:]
            )
        }
        state_map[state_id] = values
        states.append({"state_id": state_id, "state_json": values})
    return states, state_map, index


def _parse_continuity_boundaries_header(
    lines: list[str], index: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], int]:
    rows, index = _parse_table(
        lines,
        index,
        columns=CONTINUITY_BOUNDARY_TABLE_COLUMNS,
        label="Continuity Boundaries table",
        allow_empty=True,
    )
    boundaries: list[dict[str, Any]] = []
    boundary_map: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(rows, start=1):
        boundary_id = row["Boundary ID"]
        if boundary_id in boundary_map:
            raise StoryVideoError(f"Continuity Boundaries repeats {boundary_id}")
        try:
            policy = json.loads(row["Anchor Policy JSON"])
        except json.JSONDecodeError as exc:
            raise StoryVideoError(
                f"Continuity Boundaries row {row_index} Anchor Policy JSON is invalid"
            ) from exc
        boundary = {
            "boundary_id": boundary_id,
            "from_segment_id": row["From Segment"],
            "to_segment_id": row["To Segment"],
            "from_state_ref": row["From State"],
            "to_state_ref": row["To State"],
            "anchor_policy_json": policy,
        }
        boundary_map[boundary_id] = boundary
        boundaries.append(boundary)
    return boundaries, boundary_map, index


def _state_reference(
    value: Any,
    *,
    state_map: dict[str, dict[str, str]],
    label: str,
) -> tuple[str, dict[str, str]]:
    if not isinstance(value, dict) or set(value) != STATE_REF_KEYS:
        raise StoryVideoError(f"{label} must contain only state_ref")
    state_ref = value.get("state_ref")
    if not isinstance(state_ref, str) or state_ref not in state_map:
        raise StoryVideoError(f"{label} references an unknown continuity state")
    return state_ref, dict(state_map[state_ref])


def _expand_anchor_policy(
    boundary: dict[str, Any],
    *,
    from_state: dict[str, str],
    to_state: dict[str, str],
) -> list[dict[str, str]]:
    policy = boundary.get("anchor_policy_json")
    if not isinstance(policy, dict) or set(policy) != ANCHOR_POLICY_KEYS:
        raise StoryVideoError(
            f"{boundary.get('boundary_id')} Anchor Policy JSON has invalid keys"
        )
    default = policy.get("default")
    overrides = policy.get("overrides")
    if not isinstance(default, dict) or set(default) != ANCHOR_POLICY_DEFAULT_KEYS:
        raise StoryVideoError(
            f"{boundary.get('boundary_id')} Anchor Policy default is invalid"
        )
    if not isinstance(overrides, dict) or any(
        category not in CONTINUITY_CATEGORIES for category in overrides
    ):
        raise StoryVideoError(
            f"{boundary.get('boundary_id')} Anchor Policy overrides are invalid"
        )
    anchors: list[dict[str, str]] = []
    for category in CONTINUITY_CATEGORIES:
        decision = overrides.get(category, default)
        if not isinstance(decision, dict) or set(decision) != ANCHOR_POLICY_OVERRIDE_KEYS:
            raise StoryVideoError(
                f"{boundary.get('boundary_id')} Anchor Policy {category} is invalid"
            )
        anchors.append(
            {
                "category": category,
                "status": decision.get("status"),
                "from_en": from_state[category],
                "to_en": to_state[category],
                "reason_en": decision.get("reason_en"),
            }
        )
    return anchors


def _resolve_compact_story_plans(
    segments: list[dict[str, Any]],
    *,
    state_map: dict[str, dict[str, str]],
    boundary_map: dict[str, dict[str, Any]],
) -> None:
    for segment in segments:
        plan = segment["story_plan"]
        compact = dict(plan)
        start_ref, start_state = _state_reference(
            plan["start_state_json"],
            state_map=state_map,
            label=f"{plan['segment_id']}.start_state_json",
        )
        end_ref, end_state = _state_reference(
            plan["end_state_json"],
            state_map=state_map,
            label=f"{plan['segment_id']}.end_state_json",
        )
        plan["start_state_json"] = start_state
        plan["end_state_json"] = end_state
        segment["compact_refs"] = {
            "start_state_ref": start_ref,
            "end_state_ref": end_ref,
            "story_plan_json": compact,
        }

    for index, segment in enumerate(segments):
        plan = segment["story_plan"]
        refs = segment["compact_refs"]
        if index + 1 < len(segments):
            successor_refs = segments[index + 1]["compact_refs"]
            next_ref = successor_refs["start_state_ref"]
            next_state = segments[index + 1]["story_plan"]["start_state_json"]
        else:
            next_ref = None
            next_state = None
        if index == 0:
            boundary_ref = None
            anchors: list[dict[str, str]] = []
        else:
            boundary_ref = f"boundary-{index:03d}"
            boundary = boundary_map.get(boundary_ref)
            if boundary is None:
                raise StoryVideoError(
                    f"{plan['segment_id']} lacks its canonical adjacent continuity boundary"
                )
            previous_plan = segments[index - 1]["story_plan"]
            previous_refs = segments[index - 1]["compact_refs"]
            if (
                boundary["from_segment_id"] != previous_plan["segment_id"]
                or boundary["to_segment_id"] != plan["segment_id"]
                or boundary["from_state_ref"] != previous_refs["end_state_ref"]
                or boundary["to_state_ref"] != refs["start_state_ref"]
            ):
                raise StoryVideoError(
                    f"{boundary_ref} does not bind the actual adjacent Segments and states"
                )
            from_state = state_map[boundary["from_state_ref"]]
            to_state = state_map[boundary["to_state_ref"]]
            anchors = _expand_anchor_policy(
                boundary, from_state=from_state, to_state=to_state
            )
        refs.update(
            {
                "next_state_ref": next_ref,
                "boundary_ref": boundary_ref,
            }
        )
        segment["derived_continuity"] = {
            "next_segment_start_state": next_state,
            "incoming_boundary_id": boundary_ref,
            "anchors": anchors,
        }


def parse_screenplay_markdown(text: str) -> dict[str, Any]:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines:
        raise StoryVideoError("screenplay.md is empty")
    title_match = TITLE_RE.fullmatch(lines[0].strip())
    if not title_match:
        raise StoryVideoError("screenplay.md must begin with '# Seedance Screenplay: <title>'")
    index = 1
    metadata: dict[str, str] = {}
    for expected in META_ORDER:
        index = _next_nonempty(lines, index)
        if index >= len(lines):
            raise StoryVideoError(f"screenplay.md is missing metadata '{expected}'")
        match = META_RE.fullmatch(lines[index].strip())
        if not match or match.group(1) != expected:
            actual = match.group(1) if match else lines[index].strip()
            raise StoryVideoError(
                f"screenplay.md expected metadata '{expected}' before '{actual}'"
            )
        metadata[expected] = require_utf8_text(match.group(2), expected)
        index += 1
    index = _expect_section(lines, index, "## Characters")
    characters, character_map, index = _parse_characters_header(lines, index)
    index = _expect_section(lines, index, "## Environments")
    environments, index = _parse_environments_header(lines, index)
    index = _expect_section(lines, index, "## Scenes")
    scenes, index = _parse_scenes_header(lines, index)
    index = _expect_section(lines, index, "## Continuity States")
    continuity_states, state_map, index = _parse_continuity_states_header(
        lines, index
    )
    index = _expect_section(lines, index, "## Continuity Boundaries")
    continuity_boundaries, boundary_map, index = (
        _parse_continuity_boundaries_header(lines, index)
    )

    segments: list[dict[str, Any]] = []
    while index < len(lines):
        index = _next_nonempty(lines, index)
        if index >= len(lines):
            break
        match = SEGMENT_RE.fullmatch(lines[index].strip())
        if not match:
            raise StoryVideoError(f"Unexpected screenplay line: {lines[index].strip()}")
        numeric_id = int(match.group(1))
        if numeric_id != len(segments) + 1:
            raise StoryVideoError("screenplay.md Segment numbers must be consecutive from 1")
        index = _next_nonempty(lines, index + 1)
        if index >= len(lines):
            raise StoryVideoError(f"Segment {numeric_id} is missing its slugline")
        slugline = SLUGLINE_RE.fullmatch(lines[index].strip())
        if not slugline:
            raise StoryVideoError(f"Segment {numeric_id} has an invalid INT./EXT. slugline")
        story_plan, index = _parse_story_plan(lines, index + 1, numeric_id)
        blocks, index = _parse_segment_content(lines, index, character_map)
        spoken = [block for block in blocks if block["type"] == "dialogue"]
        actions = [block["text_en"] for block in blocks if block["type"] == "action"]
        segments.append(
            {
                "id": numeric_id,
                "heading_en": slugline.group(1),
                "blocks": blocks,
                "action_blocks": actions,
                "spoken_entries": spoken,
                "story_plan": story_plan,
            }
        )
    _resolve_compact_story_plans(
        segments, state_map=state_map, boundary_map=boundary_map
    )
    screenplay = {
        "screenplay_title_en": title_match.group(1).strip(),
        "target_language_en": metadata["Target language"],
        "target_age_band": metadata["Target age band"],
        "seedance_mapping": metadata["Seedance mapping"],
        "segment_duration_policy": metadata["Segment duration policy"],
        "segment_boundary_policy": metadata["Segment boundary policy"],
        "characters": characters,
        "environments": environments,
        "scenes": scenes,
        "continuity_states": continuity_states,
        "continuity_boundaries": continuity_boundaries,
        "segments": segments,
        "total_duration_seconds": sum(
            int(segment["story_plan"]["estimated_duration_seconds"])
            for segment in segments
        ),
    }
    validate_screenplay(screenplay)
    return screenplay


def _concrete(value: Any, *, allow_not_applicable: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    if allow_not_applicable and normalized == "not_applicable":
        return True
    if normalized in {"", "none", "n/a", "na", "same", "consistent", "natural", "tbd"}:
        return False
    return len(WORD_RE.findall(value)) >= 4


def _validate_state(value: Any, *, label: str) -> None:
    if not isinstance(value, dict) or tuple(value) != CONTINUITY_CATEGORIES:
        raise StoryVideoError(
            f"{label} must contain the exact ordered narrative/state categories"
        )
    for category in CONTINUITY_CATEGORIES:
        if not _concrete(value[category], allow_not_applicable=True):
            raise StoryVideoError(f"{label}.{category} must be concrete")


def _validate_scene_dramatic_contract(
    value: Any, *, scene_id: str, label: str
) -> None:
    if not isinstance(value, dict) or tuple(value) != SCENE_DRAMATIC_FIELDS:
        raise StoryVideoError(
            f"{label} must contain the exact ordered cinematic Scene fields"
        )
    if value["scene_id"] != scene_id:
        raise StoryVideoError(f"{label}.scene_id must equal {scene_id}")
    for field in SCENE_DRAMATIC_FIELDS[1:]:
        if not _concrete(value[field]):
            raise StoryVideoError(f"{label}.{field} must be concrete")
    if value["visual_progression"].strip().casefold() == value["outcome"].strip().casefold():
        raise StoryVideoError(
            f"{label}.visual_progression must describe visible spatial/action change, not restate outcome"
        )


def _validate_dramatic_beats(
    value: Any,
    *,
    segment_id: str,
    blocks: list[dict[str, Any]],
    known_beat_ids: set[str],
) -> None:
    label = f"{segment_id}.dramatic_beats_json"
    if not isinstance(value, list) or not value:
        raise StoryVideoError(f"{label} must contain at least one Dramatic Beat")
    covered_blocks: list[int] = []
    for index, beat in enumerate(value, start=1):
        beat_label = f"{label}[{index}]"
        if not isinstance(beat, dict) or tuple(beat) != DRAMATIC_BEAT_FIELDS:
            raise StoryVideoError(
                f"{beat_label} must contain the exact ordered Dramatic Beat fields"
            )
        beat_id = beat["beat_id"]
        if not isinstance(beat_id, str) or not DRAMATIC_BEAT_ID_RE.fullmatch(beat_id):
            raise StoryVideoError(f"{beat_label}.beat_id must be one stable BEAT-* ID")
        if beat_id in known_beat_ids:
            raise StoryVideoError(f"screenplay.md repeats Dramatic Beat {beat_id}")
        known_beat_ids.add(beat_id)
        for field in DRAMATIC_BEAT_FIELDS[1:-1]:
            if not _concrete(beat[field]):
                raise StoryVideoError(f"{beat_label}.{field} must be concrete")
        block_indexes = beat["block_indexes"]
        if (
            not isinstance(block_indexes, list)
            or not block_indexes
            or any(isinstance(item, bool) or not isinstance(item, int) for item in block_indexes)
            or len(block_indexes) != len(set(block_indexes))
        ):
            raise StoryVideoError(
                f"{beat_label}.block_indexes must be a nonempty unique integer list"
            )
        if any(item < 1 or item > len(blocks) for item in block_indexes):
            raise StoryVideoError(f"{beat_label}.block_indexes contains an out-of-range block")
        covered_blocks.extend(block_indexes)
        owned_blocks = [blocks[item - 1] for item in block_indexes]
        if any(block.get("type") == "dialogue" for block in owned_blocks) and not any(
            block.get("type") == "action" for block in owned_blocks
        ):
            raise StoryVideoError(
                f"{beat_label} contains dialogue without an owned action/reaction block"
            )
    expected_blocks = list(range(1, len(blocks) + 1))
    if sorted(covered_blocks) != expected_blocks:
        raise StoryVideoError(
            f"{label} must partition every screenplay block exactly once"
        )


def validate_cinematic_segment_contract(
    *,
    segment_id: str,
    scene_id: str,
    scene_contract: Any,
    dramatic_beats: Any,
    blocks: list[dict[str, Any]],
    known_beat_ids: set[str] | None = None,
) -> None:
    """Gate one screenplay Segment before Storyboard without choosing cameras."""

    _validate_scene_dramatic_contract(
        scene_contract,
        scene_id=scene_id,
        label=f"{segment_id}.scene_dramatic_contract_json",
    )
    _validate_dramatic_beats(
        dramatic_beats,
        segment_id=segment_id,
        blocks=blocks,
        known_beat_ids=known_beat_ids if known_beat_ids is not None else set(),
    )
    for block in blocks:
        if block.get("type") == "action" and STAGE_TABLEAU_RISK_RE.search(
            str(block.get("text_en") or "")
        ):
            raise StoryVideoError(
                f"{segment_id} contains stage-tableau action language; rewrite character objectives, spatial roles, and visible behavior before Storyboard"
            )


def _validate_transition(value: Any, *, final: bool, segment_id: str) -> None:
    if not isinstance(value, dict) or set(value) != TRANSITION_DESIGN_KEYS:
        raise StoryVideoError(f"{segment_id} transition_design_json has invalid keys")
    kind = value.get("type")
    if kind not in TRANSITION_DESIGN_TYPES:
        raise StoryVideoError(f"{segment_id} transition type is invalid")
    if final != (kind == "final_end"):
        raise StoryVideoError(f"{segment_id} final/non-final transition type is invalid")
    for field in TRANSITION_DESIGN_KEYS - {"type"}:
        if not _concrete(value[field], allow_not_applicable=final and field.startswith("incoming_")):
            raise StoryVideoError(f"{segment_id} transition field {field} must be concrete")
    combined = " ".join(str(value[field]) for field in TRANSITION_DESIGN_KEYS)
    if FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE.search(combined):
        raise StoryVideoError(f"{segment_id} transition contains forbidden cross-clip dependency")


def validate_adjacent_visual_boundary_contract(
    *,
    segment_id: str,
    predecessor_plan: dict[str, Any],
    current_plan: dict[str, Any],
) -> None:
    """Validate deterministic prerequisites for an authored visual inheritance."""

    incoming_requirement = current_plan["incoming_visual_requirement"]
    same_scene = predecessor_plan["scene_id"] == current_plan["scene_id"]
    if same_scene and incoming_requirement == "independent":
        raise StoryVideoError(
            f"{segment_id} shares a Scene with its predecessor and cannot be "
            "independent; use state_match for soft first-frame reference or "
            "continuous_motion for predecessor-video reference"
        )
    if not same_scene and incoming_requirement == "continuous_motion":
        raise StoryVideoError(
            f"{segment_id} continuous_motion cannot cross a Scene boundary"
        )
    if incoming_requirement != "continuous_motion":
        return
    predecessor_transition = predecessor_plan["transition_design_json"]
    if predecessor_transition["type"] not in {
        "hard_cut",
        "action_cut",
        "match_cut",
        "eyeline_cut",
        "reaction_cut",
    }:
        raise StoryVideoError(
            f"{segment_id} continuous_motion requires a cut-like predecessor transition"
        )
    inherited_phase_text = " ".join(
        str(value)
        for value in (
            predecessor_transition["outgoing_visible_en"],
            predecessor_transition["incoming_visible_en"],
            predecessor_transition["action_link_en"],
            predecessor_transition["spatial_link_en"],
        )
    )
    if not INHERITED_VISUAL_PHASE_RE.search(inherited_phase_text):
        raise StoryVideoError(
            f"{segment_id} continuous_motion must name the inherited visual, "
            "performance, blocking, or camera phase"
        )


def validate_screenplay(screenplay: dict[str, Any]) -> None:
    fixed = {
        "target_language_en": "English",
        "seedance_mapping": "one_segment_one_video",
        "segment_duration_policy": "natural_4_to_15_seconds",
        "segment_boundary_policy": "semantic_boundary_execution",
    }
    for field, expected in fixed.items():
        if screenplay.get(field) != expected:
            raise StoryVideoError(f"screenplay.md {field} must be {expected}")
    if screenplay.get("target_age_band") not in TARGET_AGE_BANDS:
        raise StoryVideoError("screenplay.md target age band is invalid")
    characters = screenplay.get("characters")
    if not isinstance(characters, list) or not characters:
        raise StoryVideoError("screenplay.md must contain Characters")
    character_fields = {
        "name_en",
        "story_role",
        "narrative_function_en",
        "narration_eligibility",
        "narration_scope_en",
        "description_en",
    }
    character_by_name: dict[str, dict[str, Any]] = {}
    for character in characters:
        if not isinstance(character, dict) or set(character) != character_fields:
            raise StoryVideoError("screenplay.md Characters table schema is invalid")
        name = character["name_en"]
        if not isinstance(name, str) or not name.strip() or name in character_by_name:
            raise StoryVideoError("screenplay.md Character names must be unique")
        if character["story_role"] not in CHARACTER_STORY_ROLES:
            raise StoryVideoError(f"Character {name} story_role is invalid")
        if character["narration_eligibility"] not in NARRATION_ELIGIBILITIES:
            raise StoryVideoError(f"Character {name} narration eligibility is invalid")
        for field in (
            "narrative_function_en",
            "narration_scope_en",
            "description_en",
        ):
            if not _concrete(character[field]):
                raise StoryVideoError(f"Character {name} {field} must be concrete")
        character_by_name[name] = character
    if not any(item["story_role"] == "lead" for item in characters):
        raise StoryVideoError("screenplay.md must identify at least one lead character")
    character_names = set(character_by_name)

    environments = screenplay.get("environments")
    environment_fields = {
        "environment_id",
        "logical_name_en",
        "scene_ids_json",
        "int_ext",
        "time_context_en",
        "environment_facts_en",
        "story_function_en",
    }
    if not isinstance(environments, list) or not environments:
        raise StoryVideoError("screenplay.md must contain an Environments table")
    scene_environment: dict[str, dict[str, Any]] = {}
    for index, environment in enumerate(environments, start=1):
        expected_id = f"environment-{index:03d}"
        if not isinstance(environment, dict) or set(environment) != environment_fields:
            raise StoryVideoError("screenplay.md Environments table schema is invalid")
        if (
            environment["environment_id"] != expected_id
            or not ENVIRONMENT_ID_RE.fullmatch(str(environment["environment_id"]))
        ):
            raise StoryVideoError(f"Environment {index} must be {expected_id}")
        if environment["int_ext"] not in ENVIRONMENT_KINDS:
            raise StoryVideoError(f"{expected_id} INT/EXT value is invalid")
        for field in (
            "logical_name_en",
            "time_context_en",
            "environment_facts_en",
            "story_function_en",
        ):
            if not _concrete(environment[field]):
                raise StoryVideoError(f"{expected_id} {field} must be concrete")
        scene_ids = environment["scene_ids_json"]
        if not isinstance(scene_ids, list) or not scene_ids:
            raise StoryVideoError(f"{expected_id} scene_ids_json must be non-empty")
        for scene_id in scene_ids:
            if not isinstance(scene_id, str) or not SCENE_ID_RE.fullmatch(scene_id):
                raise StoryVideoError(f"{expected_id} contains an invalid scene_id")
            if scene_id in scene_environment:
                raise StoryVideoError(f"Scene {scene_id} appears in multiple environments")
            scene_environment[scene_id] = environment

    scenes = screenplay.get("scenes")
    scene_fields = {
        "scene_id",
        "segment_ids_json",
        "primary_time_en",
        "primary_place_en",
        "narrative_event_en",
        "entry_boundary",
        "entry_reason_en",
        "continuity_reference_segment_id",
        "continuity_reference_reason_en",
    }
    if not isinstance(scenes, list) or not scenes:
        raise StoryVideoError("screenplay.md must contain a Scenes table")
    scene_segment_ids: list[str] = []
    scene_by_segment: dict[str, str] = {}
    for index, scene in enumerate(scenes, start=1):
        expected_id = f"scene-{index:03d}"
        if not isinstance(scene, dict) or set(scene) != scene_fields:
            raise StoryVideoError("screenplay.md Scenes table schema is invalid")
        if scene["scene_id"] != expected_id or not SCENE_ID_RE.fullmatch(
            str(scene["scene_id"])
        ):
            raise StoryVideoError(f"Scene {index} must be {expected_id}")
        entry_boundary = scene["entry_boundary"]
        if entry_boundary not in SCENE_ENTRY_BOUNDARIES:
            raise StoryVideoError(f"{expected_id} entry_boundary is invalid")
        if (index == 1) != (entry_boundary == "opening"):
            raise StoryVideoError(
                "Only scene-001 may use entry_boundary opening"
            )
        for field in (
            "primary_time_en",
            "primary_place_en",
            "narrative_event_en",
            "entry_reason_en",
        ):
            if not _concrete(scene[field]):
                raise StoryVideoError(f"{expected_id} {field} must be concrete")
        continuity_reference_segment_id = scene[
            "continuity_reference_segment_id"
        ]
        if continuity_reference_segment_id != "none" and not SEGMENT_ID_RE.fullmatch(
            str(continuity_reference_segment_id)
        ):
            raise StoryVideoError(
                f"{expected_id} continuity reference Segment is invalid"
            )
        segment_ids = scene["segment_ids_json"]
        if not isinstance(segment_ids, list) or not segment_ids:
            raise StoryVideoError(f"{expected_id} segment_ids_json must be non-empty")
        for segment_id in segment_ids:
            if not isinstance(segment_id, str) or not SEGMENT_ID_RE.fullmatch(segment_id):
                raise StoryVideoError(f"{expected_id} contains an invalid segment_id")
            if segment_id in scene_by_segment:
                raise StoryVideoError(
                    f"{segment_id} appears in multiple Scenes"
                )
            scene_by_segment[segment_id] = expected_id
            scene_segment_ids.append(segment_id)
    if set(scene_environment) != {scene["scene_id"] for scene in scenes}:
        raise StoryVideoError(
            "Scenes table and Environments Scene bindings must match exactly"
        )

    continuity_states = screenplay.get("continuity_states")
    if not isinstance(continuity_states, list) or not continuity_states:
        raise StoryVideoError("screenplay.md must contain Continuity States")
    state_by_id: dict[str, dict[str, str]] = {}
    for index, state_record in enumerate(continuity_states, start=1):
        expected_id = f"state-{index:03d}"
        if (
            not isinstance(state_record, dict)
            or set(state_record) != {"state_id", "state_json"}
            or state_record["state_id"] != expected_id
            or not STATE_ID_RE.fullmatch(str(state_record["state_id"]))
        ):
            raise StoryVideoError(f"Continuity State {index} must be {expected_id}")
        _validate_state(state_record["state_json"], label=expected_id)
        state_by_id[expected_id] = state_record["state_json"]

    segments = screenplay.get("segments")
    if not isinstance(segments, list) or not segments:
        raise StoryVideoError("screenplay.md must contain at least one Segment")
    boundaries = screenplay.get("continuity_boundaries")
    if not isinstance(boundaries, list) or len(boundaries) != len(segments) - 1:
        raise StoryVideoError(
            "screenplay.md Continuity Boundaries must cover every adjacent pair once"
        )
    for index, boundary in enumerate(boundaries, start=1):
        expected_id = f"boundary-{index:03d}"
        if (
            not isinstance(boundary, dict)
            or boundary.get("boundary_id") != expected_id
            or not BOUNDARY_ID_RE.fullmatch(str(boundary.get("boundary_id") or ""))
        ):
            raise StoryVideoError(f"Continuity Boundary {index} must be {expected_id}")
        if (
            boundary.get("from_segment_id") != f"segment-{index:03d}"
            or boundary.get("to_segment_id") != f"segment-{index + 1:03d}"
            or boundary.get("from_state_ref") not in state_by_id
            or boundary.get("to_state_ref") not in state_by_id
        ):
            raise StoryVideoError(f"{expected_id} Segment or State binding is invalid")
        _expand_anchor_policy(
            boundary,
            from_state=state_by_id[boundary["from_state_ref"]],
            to_state=state_by_id[boundary["to_state_ref"]],
        )
    runtime = 0
    known_dramatic_beat_ids: set[str] = set()
    scene_dramatic_contracts: dict[str, dict[str, Any]] = {}
    for index, segment in enumerate(segments, start=1):
        if segment.get("id") != index:
            raise StoryVideoError("screenplay.md Segment ids must be consecutive")
        blocks = segment.get("blocks")
        actions = segment.get("action_blocks")
        if (
            not isinstance(blocks, list)
            or len(blocks) < MINIMUM_SEGMENT_BLOCK_COUNT
            or blocks[0].get("type") != "action"
            or blocks[-1].get("type") != "action"
            or not isinstance(actions, list)
            or len(actions) < 2
        ):
            raise StoryVideoError(
                f"screenplay.md Segment {index} must contain at least "
                f"{MINIMUM_SEGMENT_BLOCK_COUNT} beats, open with a concrete Action, "
                "develop the assigned dramatic phase, and close with an explicit "
                "boundary Action"
            )
        plan = segment.get("story_plan")
        if not isinstance(plan, dict) or tuple(plan) != SCREENPLAY_SEGMENT_FIELDS:
            raise StoryVideoError(f"screenplay.md Segment {index} story_plan schema is invalid")
        segment_id = f"segment-{index:03d}"
        if plan["segment_id"] != segment_id or not SEGMENT_ID_RE.fullmatch(plan["segment_id"]):
            raise StoryVideoError(f"screenplay.md Segment {index} segment_id is invalid")
        if not SCENE_ID_RE.fullmatch(str(plan["scene_id"])):
            raise StoryVideoError(f"{segment_id} scene_id is invalid")
        environment = scene_environment.get(plan["scene_id"])
        if environment is None:
            raise StoryVideoError(
                f"{segment_id} scene_id is missing from the Environments table"
            )
        heading_kind = str(segment.get("heading_en") or "").split(".", 1)[0]
        if environment["int_ext"] != "MIXED" and environment["int_ext"] != heading_kind:
            raise StoryVideoError(
                f"{segment_id} slugline conflicts with {environment['environment_id']} INT/EXT"
            )
        duration = plan["estimated_duration_seconds"]
        if isinstance(duration, bool) or not isinstance(duration, int) or not 4 <= duration <= 15:
            raise StoryVideoError(f"{segment_id} duration must be 4-15 seconds")
        runtime += duration
        if plan["dramatic_workload"] not in DIALOGUE_OCCUPANCY_LIMITS:
            raise StoryVideoError(
                f"{segment_id} dramatic_workload must be one of "
                f"{sorted(DIALOGUE_OCCUPANCY_LIMITS)}"
            )
        validate_cinematic_segment_contract(
            segment_id=segment_id,
            scene_id=plan["scene_id"],
            scene_contract=plan["scene_dramatic_contract_json"],
            dramatic_beats=plan["dramatic_beats_json"],
            blocks=blocks,
            known_beat_ids=known_dramatic_beat_ids,
        )
        prior_scene_contract = scene_dramatic_contracts.get(plan["scene_id"])
        if prior_scene_contract is None:
            scene_dramatic_contracts[plan["scene_id"]] = plan[
                "scene_dramatic_contract_json"
            ]
        elif prior_scene_contract != plan["scene_dramatic_contract_json"]:
            raise StoryVideoError(
                f"{segment_id} must repeat the same Scene dramatic contract across its Scene"
            )
        incoming_visual_requirement = plan["incoming_visual_requirement"]
        if incoming_visual_requirement not in INCOMING_VISUAL_REQUIREMENTS:
            raise StoryVideoError(
                f"{segment_id} incoming_visual_requirement is invalid"
            )
        if index == 1 and incoming_visual_requirement != "independent":
            raise StoryVideoError(
                "segment-001 must use independent as the project opening"
            )
        if index > 1:
            predecessor_plan = segments[index - 2]["story_plan"]
            validate_adjacent_visual_boundary_contract(
                segment_id=segment_id,
                predecessor_plan=predecessor_plan,
                current_plan=plan,
            )
        for field in (
            "location_time_environment_en",
            "narrative_purpose_en",
        ):
            if not _concrete(plan[field]):
                raise StoryVideoError(f"{segment_id} {field} must be concrete")
            if FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE.search(plan[field]):
                raise StoryVideoError(
                    f"{segment_id} contains forbidden previous-frame/video dependency"
                )
        present = plan["characters_json"]
        if (
            not isinstance(present, list)
            or any(not isinstance(name, str) or name not in character_names for name in present)
        ):
            raise StoryVideoError(f"{segment_id} characters_json is invalid")
        _validate_state(plan["start_state_json"], label=f"{segment_id}.start_state_json")
        _validate_state(plan["end_state_json"], label=f"{segment_id}.end_state_json")
        final = index == len(segments)
        _validate_transition(plan["transition_design_json"], final=final, segment_id=segment_id)
        if (
            plan["transition_design_json"]["outgoing_visible_en"]
            != blocks[-1].get("text_en")
        ):
            raise StoryVideoError(
                f"{segment_id} transition outgoing visible state must equal its closing Action"
            )
        anchors = segment["derived_continuity"]["anchors"]
        if index == 1:
            if anchors != []:
                raise StoryVideoError("segment-001 derived continuity anchors must be []")
        else:
            if not isinstance(anchors, list) or len(anchors) != len(CONTINUITY_CATEGORIES):
                raise StoryVideoError(f"{segment_id} must anchor every continuity category")
            categories: list[str] = []
            for anchor in anchors:
                if not isinstance(anchor, dict) or set(anchor) != CONTINUITY_ANCHOR_KEYS:
                    raise StoryVideoError(f"{segment_id} has an invalid continuity Anchor")
                category = anchor["category"]
                categories.append(category)
                if anchor["status"] not in CONTINUITY_ANCHOR_STATUSES:
                    raise StoryVideoError(f"{segment_id} Anchor status is invalid")
                if not all(
                    _concrete(anchor[field], allow_not_applicable=field != "reason_en")
                    for field in ("from_en", "to_en", "reason_en")
                ):
                    raise StoryVideoError(f"{segment_id} Anchor facts must be concrete")
                if anchor["status"] == "preserve" and anchor["from_en"] != anchor["to_en"]:
                    raise StoryVideoError(f"{segment_id} preserve Anchor changes state")
                if anchor["status"] == "not_applicable" and (
                    anchor["from_en"] != "not_applicable"
                    or anchor["to_en"] != "not_applicable"
                ):
                    raise StoryVideoError(
                        f"{segment_id} not_applicable Anchor must bind literal not_applicable facts"
                    )
            if tuple(categories) != CONTINUITY_CATEGORIES:
                raise StoryVideoError(f"{segment_id} Anchor categories are out of order")
        for entry in segment.get("spoken_entries") or []:
            speaker = entry.get("speaker_en")
            if speaker not in present:
                raise StoryVideoError(f"{segment_id} dialogue speaker must appear in characters_json")
            if entry.get("speaker_mode") == "V.O." and character_by_name[speaker][
                "narration_eligibility"
            ] == "not_allowed":
                raise StoryVideoError(
                    f"{segment_id} uses {speaker} as V.O. despite not_allowed narration eligibility"
                )
        dialogue_words = sum(
            len(WORD_RE.findall(str(entry.get("spoken_text_en") or "")))
            for entry in segment.get("spoken_entries") or []
        )
        minimum_seconds = (
            dialogue_words / DIALOGUE_WORDS_PER_SECOND
            + len(segment.get("spoken_entries") or [])
            * DIALOGUE_TURN_ALLOWANCE_SECONDS
            + MINIMUM_ACTION_REACTION_SECONDS
        )
        if duration + 1e-6 < minimum_seconds:
            raise StoryVideoError(
                f"{segment_id} duration is below its dialogue/action floor of {minimum_seconds:.1f}s"
            )
    if screenplay.get("total_duration_seconds") != runtime or runtime > 240:
        raise StoryVideoError("screenplay.md total duration is inconsistent or exceeds 240 seconds")
    for current, successor in zip(segments, segments[1:]):
        if (
            current["story_plan"]["transition_design_json"]["incoming_visible_en"]
            != successor["blocks"][0].get("text_en")
        ):
            raise StoryVideoError(
                f"{current['story_plan']['segment_id']} transition incoming visible state "
                "must equal the successor opening Action"
            )
    used_scene_ids = {segment["story_plan"]["scene_id"] for segment in segments}
    if set(scene_environment) != used_scene_ids:
        unused = sorted(set(scene_environment) - used_scene_ids)
        raise StoryVideoError(
            "Environments table contains unused Scene IDs: " + ", ".join(unused)
        )
    expected_segment_ids = [
        f"segment-{index:03d}" for index in range(1, len(segments) + 1)
    ]
    if scene_segment_ids != expected_segment_ids:
        raise StoryVideoError(
            "Scenes must partition all Segments once, in screenplay order, using "
            "contiguous Segment ranges"
        )
    segment_index_by_id = {
        segment_id: index for index, segment_id in enumerate(expected_segment_ids)
    }
    for scene in scenes:
        reference_id = scene["continuity_reference_segment_id"]
        reason = scene["continuity_reference_reason_en"]
        entry_id = scene["segment_ids_json"][0]
        if reference_id == "none":
            if reason != "none":
                raise StoryVideoError(
                    f"{scene['scene_id']} without a continuity reference must use reason 'none'"
                )
            continue
        if (
            reference_id not in segment_index_by_id
            or segment_index_by_id[reference_id] >= segment_index_by_id[entry_id]
        ):
            raise StoryVideoError(
                f"{scene['scene_id']} continuity reference must name an earlier Segment"
            )
        source_scene_id = scene_by_segment[reference_id]
        if (
            scene_environment[source_scene_id]["environment_id"]
            != scene_environment[scene["scene_id"]]["environment_id"]
        ):
            raise StoryVideoError(
                f"{scene['scene_id']} continuity reference must return to the same environment"
            )
        if len(reason.split()) < 5:
            raise StoryVideoError(
                f"{scene['scene_id']} continuity reference reason must be concrete"
            )
        entry_segment = segments[segment_index_by_id[entry_id]]
        if entry_segment["story_plan"]["incoming_visual_requirement"] != "state_match":
            raise StoryVideoError(
                f"{entry_id} must use state_match for its Scene continuity reference"
            )
    for segment in segments:
        segment_id = segment["story_plan"]["segment_id"]
        scene_id = segment["story_plan"]["scene_id"]
        if scene_by_segment.get(segment_id) != scene_id:
            raise StoryVideoError(
                f"{segment_id} scene_id disagrees with the Scenes table"
            )


def load_screenplay_file(path: str | Path) -> dict[str, Any]:
    screenplay_path = Path(path).expanduser().resolve()
    if screenplay_path.name != "screenplay.md":
        raise StoryVideoError("Screenplay file must be named screenplay.md")
    try:
        text = screenplay_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise StoryVideoError(f"Invalid screenplay file: {screenplay_path}") from exc
    return parse_screenplay_markdown(text)


def screenplay_spoken_entries(screenplay: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "speaker_en": entry["speaker_en"],
            "delivery_en": screenplay_delivery_cue(entry),
            "spoken_text_en": entry["spoken_text_en"],
        }
        for segment in screenplay["segments"]
        for entry in segment.get("spoken_entries", [])
    ]


def screenplay_delivery_cue(entry: dict[str, Any]) -> str | None:
    cues: list[str] = []
    mode = entry.get("speaker_mode")
    if isinstance(mode, str) and mode:
        cues.append(mode)
    delivery = entry.get("delivery_en")
    if isinstance(delivery, str) and delivery.strip():
        cues.append(delivery.strip())
    return "; ".join(cues) or None


def screenplay_action_blocks(screenplay: dict[str, Any]) -> list[str]:
    return [
        action
        for segment in screenplay["segments"]
        for action in segment.get("action_blocks", [])
    ]
