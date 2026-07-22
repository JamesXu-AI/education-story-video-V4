"""Parse and validate the authored, all-table cinematic screenplay contract."""

from __future__ import annotations

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
TITLE_RE = re.compile(r"^# Cinematic Widescreen Production Script: (.+)$")
SCENE_UNIT_RE = re.compile(r"^## Scene Unit ([1-9][0-9]*) — (.+)$")
SCENE_ID_RE = re.compile(r"^scene-[0-9]{3,}$")
SEGMENT_ID_RE = re.compile(r"^segment-[0-9]{3,}$")
STATE_ID_RE = re.compile(r"^state-[0-9]{3,}$")
BOUNDARY_ID_RE = re.compile(r"^boundary-[0-9]{3,}$")
ENVIRONMENT_ID_RE = re.compile(r"^environment-[0-9]{3,}$")
ENTITY_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ACTION_ID_RE = re.compile(r"^A-[0-9]{3,}$")
LINE_ID_RE = re.compile(r"^L-[0-9]{3,}$")
BEAT_ID_RE = re.compile(r"^BEAT-[A-Za-z0-9_.-]+$")
SLUGLINE_RE = re.compile(r"^(INT|EXT)\. .+ - .+$")
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*")
GAZE_RE = re.compile(
    r"^([a-z0-9]+(?:-[a-z0-9]+)*) -> ([^()]+?) "
    r"\(facing=(.+?), gaze=(.+)\)$"
)
DIALOGUE_RE = re.compile(
    r'^((?:L)-[0-9]{3,}); speaker=([a-z0-9]+(?:-[a-z0-9]+)*); '
    r'gate=([^;]+); delivery=([^;]+); text="([^"]+)"$'
)
AUDIO_RE = re.compile(
    r"^(BGM (?:ENTERS|EVOLVES|STOPS|STING)|SFX|AMBIENCE|SILENCE):\s*(.+)$"
)

DRAMATIC_WORKLOADS = {
    "action_led",
    "mixed_dialogue_action",
    "dialogue_led",
}
DIALOGUE_WORDS_PER_SECOND = 2.6
DIALOGUE_TURN_ALLOWANCE_SECONDS = 0.25
MINIMUM_ACTION_REACTION_SECONDS = 1.0

PRODUCTION_INFORMATION_FIELDS = (
    "Production Type",
    "Genre",
    "Estimated Runtime Seconds",
    "Target Language",
    "Target Age Band",
    "Educational Theme",
    "Story Premise",
    "Dramatic Strategy",
    "Safety and Culture",
    "Opening Event",
    "Ending Event and Obligation",
)
CHARACTER_TABLE_COLUMNS = (
    "Entity ID",
    "Character",
    "Story Role",
    "Narrative Function",
    "Kind",
    "Recurring",
    "Group Role",
    "Member Types",
    "Narration",
    "Description",
)
SCENE_UNIT_INFORMATION_FIELDS = (
    "Segment ID",
    "Scene ID",
    "Slugline",
    "Duration Seconds",
    "Workload",
    "Environment",
    "Dramatic Purpose",
    "Start State",
    "End State",
    "Incoming Boundary",
)
SHOT_EXECUTION_COLUMNS = (
    "Shot ID",
    "Beat ID",
    "Scale / View",
    "Duration Seconds",
    "Performers",
    "Dramatic Change",
    "Objective / Tactic",
    "Visual Action",
    "Important Reaction",
    "Blocking / Movement",
    "Gaze / Addressee",
    "Completion State",
    "Audience Focus",
    "BGM / SFX / Ambience",
    "Dialogue",
)
CHARACTER_STAGING_COLUMNS = (
    "Entity ID",
    "Presence",
    "Appearance",
    "Trigger",
    "Entry Path / Opening Position",
    "First Visible Shot",
    "First Visible Moment",
    "Landing Shot",
    "Landing Moment / Result",
    "Speaks",
    "Lines",
    "State Change",
    "Action Shots",
)
ENVIRONMENT_TABLE_COLUMNS = (
    "Environment ID",
    "Logical Environment",
    "Scene IDs",
    "INT/EXT",
    "Time Context",
    "Environment Facts",
    "Story Function",
)
SCENE_TABLE_COLUMNS = (
    "Scene ID",
    "Segment IDs",
    "Primary Time",
    "Primary Place",
    "Narrative Event",
    "Entry Boundary",
    "Entry Reason",
    "Continuity Reference Segment",
    "Continuity Reference Reason",
)
SCENE_CONTRACT_TABLE_COLUMNS = (
    "Scene ID",
    "Purpose",
    "Character Objective",
    "Obstacle",
    "Power Relationship",
    "Turning Point",
    "Outcome",
    "Spatial Progression",
    "Exit Impulse",
)
CONTINUITY_STATE_TABLE_COLUMNS = (
    "State ID",
    "Parent State",
    "Changed Facts",
    "Change Reason",
)
CONTINUITY_BOUNDARY_TABLE_COLUMNS = (
    "Boundary ID",
    "From Segment",
    "To Segment",
    "From State",
    "To State",
    "Handoff",
    "Transition",
    "Dramatic Reason",
    "Audio Handoff",
    "Continuity Handoff",
)

SCALE_VIEWS = {
    "establishing",
    "wide",
    "medium",
    "close_up",
    "extreme_close_up",
    "insert",
    "reaction",
    "pov",
}
CHARACTER_STORY_ROLES = {"lead", "supporting", "npc"}
NARRATION_ELIGIBILITIES = {"allowed", "conditional", "not_allowed"}
ENTITY_KINDS = {"individual", "anonymous_ensemble"}
PRESENCE_MODES = {"on_screen", "off_screen", "voice_over"}
APPEARANCE_MODES = {"present_at_open", "enters", "not_visible"}
DIALOGUE_ADDRESSEE_SPECIALS = {"self", "narration"}
ENVIRONMENT_KINDS = {"INT", "EXT", "MIXED"}
SCENE_ENTRY_BOUNDARIES = {
    "opening",
    "time_change",
    "place_change",
    "time_and_place_change",
    "narrative_event_change",
}
INCOMING_VISUAL_REQUIREMENTS = {"independent", "state_match", "continuous_motion"}
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
STAGE_TABLEAU_RISK_RE = re.compile(
    r"\b(?:all\s+(?:the\s+)?(?:animals|characters|people|villagers|students|guests|"
    r"workers|soldiers|courtiers)|everyone|the\s+(?:animals|characters|group|cast|crowd))\b"
    r"[^.!?]{0,100}\b(?:stand|stands|stood|standing|line\s+up|lined\s+up|semicircle)\b|"
    r"\b(?:take|takes|took)\s+turns?\s+(?:speaking|talking|answering)\b|"
    r"\b(?:face|faces|facing|look|looks|looking)\s+(?:at|toward)?\s*(?:the\s+)?camera\b",
    re.I,
)
FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE = re.compile(
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
    r"screen\s+direction|eyeline|blocking|performance\s+phase)\b|"
    r"\b(?:same|exact|unfinished|inherited)\b[^.]{0,80}\b"
    r"(?:motion|movement|pose|position|facing|blocking|performance\s+phase)\b",
    re.I,
)


def fixed_screenplay_prompt() -> tuple[Path, str]:
    path = fixed_prompt_path("screenplay", SCREENPLAY_PROMPT_FILENAME)
    try:
        prompt = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoryVideoError(f"Cannot read fixed Screenplay Prompt: {path}") from exc
    if "# Cinematic Widescreen Production Script Prompt" not in prompt:
        raise StoryVideoError(f"Invalid fixed Screenplay Prompt: {path}")
    return path, prompt


def _next_nonempty(lines: list[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _concrete(value: Any, *, allow_none: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    if allow_none and normalized == "none":
        return True
    if normalized in {"", "none", "n/a", "na", "same", "consistent", "tbd"}:
        return False
    return len(WORD_RE.findall(value)) >= 3


def _present(value: Any, *, allow_none: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    if allow_none and normalized == "none":
        return True
    return normalized not in {"", "none", "n/a", "na", "same", "consistent", "tbd"}


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
        if character == "\\" and cursor + 1 < len(body) and body[cursor + 1] in {"\\", "|"}:
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
        if stripped.startswith("#"):
            break
        cells = _table_cells(lines[index], label=label)
        if len(cells) != len(columns) or any(not cell for cell in cells):
            raise StoryVideoError(f"{label} contains an invalid row")
        rows.append(dict(zip(columns, cells)))
        index += 1
    if not rows and not allow_empty:
        raise StoryVideoError(f"{label} must contain at least one row")
    return rows, index


def _parse_field_table(
    lines: list[str], index: int, fields: tuple[str, ...], *, label: str
) -> tuple[dict[str, str], int]:
    rows, index = _parse_table(
        lines, index, columns=("Field", "Value"), label=label
    )
    actual = [row["Field"] for row in rows]
    if tuple(actual) != fields:
        raise StoryVideoError(f"{label} must use the exact ordered Field rows")
    return {
        row["Field"]: require_utf8_text(row["Value"], f"{label} {row['Field']}")
        for row in rows
    }, index


def _expect_heading(lines: list[str], index: int, heading: str) -> int:
    index = _next_nonempty(lines, index)
    if index >= len(lines) or lines[index].strip() != heading:
        raise StoryVideoError(f"screenplay.md must declare {heading}")
    return index + 1


def _ids(
    value: str,
    pattern: re.Pattern[str],
    *,
    label: str,
    allow_none: bool = False,
) -> list[str]:
    if value == "none" and allow_none:
        return []
    result = [item.strip() for item in value.split(",")]
    if (
        not result
        or any(not pattern.fullmatch(item) for item in result)
        or len(result) != len(set(result))
    ):
        raise StoryVideoError(f"{label} contains invalid or repeated IDs")
    return result


def _yes_no(value: str, *, label: str) -> bool:
    if value not in {"yes", "no"}:
        raise StoryVideoError(f"{label} must be yes or no")
    return value == "yes"


def _positive_number(value: str, *, label: str) -> float:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9])?", value):
        raise StoryVideoError(f"{label} must be a positive number with at most one decimal")
    result = float(value)
    if result <= 0:
        raise StoryVideoError(f"{label} must be positive")
    return result


def _split_br(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"\s*<br\s*/?>\s*", value) if item.strip()]


def _parse_gaze(value: str, *, label: str) -> dict[str, dict[str, str]]:
    if value == "none":
        return {}
    result: dict[str, dict[str, str]] = {}
    for item in _split_br(value):
        match = GAZE_RE.fullmatch(item)
        if not match:
            raise StoryVideoError(
                f"{label} must use '<entity> -> <target> (facing=..., gaze=...)'"
            )
        source, target, facing, gaze = (part.strip() for part in match.groups())
        if source in result:
            raise StoryVideoError(f"{label} repeats gaze authority for {source}")
        if not _concrete(facing) or not _concrete(gaze):
            if not (facing == "not_visible" and gaze == "not_visible"):
                raise StoryVideoError(f"{label} requires concrete facing and gaze")
        if re.search(r"\bcamera\b", target + " " + facing + " " + gaze, re.I):
            raise StoryVideoError(f"{label} may not address the camera")
        result[source] = {"target": target, "facing": facing, "gaze": gaze}
    return result


def _parse_audio(value: str, *, label: str) -> list[dict[str, str]]:
    if value == "none":
        return []
    result: list[dict[str, str]] = []
    for item in _split_br(value):
        match = AUDIO_RE.fullmatch(item)
        if not match or not _concrete(match.group(2)):
            raise StoryVideoError(f"{label} contains an invalid or generic audio cue")
        result.append({"type": match.group(1), "description_en": match.group(2)})
    return result


def _parse_dialogue(value: str, *, label: str) -> dict[str, str] | None:
    if value == "none":
        return None
    match = DIALOGUE_RE.fullmatch(value)
    if not match:
        raise StoryVideoError(f"{label} does not use the exact Dialogue syntax")
    line_id, speaker, gate, delivery, spoken = (part.strip() for part in match.groups())
    if not _concrete(gate) or not _present(spoken):
        raise StoryVideoError(f"{label} requires a concrete gate and exact spoken text")
    if delivery != "none" and not _present(delivery):
        raise StoryVideoError(f"{label} Delivery must be concrete or none")
    return {
        "line_id": line_id,
        "speaker_entity_id": speaker,
        "gate_en": gate,
        "delivery_en": delivery,
        "spoken_text_en": spoken,
    }


def _parse_shot_rows(
    rows: list[dict[str, str]], *, label: str
) -> list[dict[str, Any]]:
    shots: list[dict[str, Any]] = []
    for row in rows:
        shot_id = row["Shot ID"]
        if not ACTION_ID_RE.fullmatch(shot_id):
            raise StoryVideoError(f"{label} has an invalid Shot ID")
        scale = row["Scale / View"]
        if scale not in SCALE_VIEWS:
            raise StoryVideoError(f"{shot_id} has an invalid Scale / View")
        performers = _ids(
            row["Performers"], ENTITY_ID_RE, label=f"{shot_id} Performers", allow_none=True
        )
        if any(
            not _concrete(row[field], allow_none=field == "Important Reaction")
            for field in (
                "Dramatic Change",
                "Objective / Tactic",
                "Visual Action",
                "Important Reaction",
                "Blocking / Movement",
                "Audience Focus",
            )
        ):
            raise StoryVideoError(f"{shot_id} contains missing or generic dramatic content")
        if performers and row["Blocking / Movement"] == "none":
            raise StoryVideoError(f"{shot_id} performers require explicit Blocking / Movement")
        completion = row["Completion State"]
        completion_match = re.fullmatch(r"(completed|open):\s*(.+)", completion)
        if not completion_match or not _concrete(completion_match.group(2)):
            raise StoryVideoError(f"{shot_id} has an invalid Completion State")
        beat_id = row["Beat ID"]
        if not BEAT_ID_RE.fullmatch(beat_id):
            raise StoryVideoError(f"{shot_id} has an invalid Beat ID")
        shots.append(
            {
                "shot_id": shot_id,
                "beat_id": beat_id,
                "scale_view": scale,
                "duration_seconds": _positive_number(
                    row["Duration Seconds"], label=f"{shot_id} Duration Seconds"
                ),
                "performer_ids": performers,
                "dramatic_change_en": row["Dramatic Change"],
                "objective_tactic_en": row["Objective / Tactic"],
                "visual_action_en": row["Visual Action"],
                "important_reaction_en": row["Important Reaction"],
                "blocking_movement_en": row["Blocking / Movement"],
                "gaze_relations": _parse_gaze(
                    row["Gaze / Addressee"], label=f"{shot_id} Gaze / Addressee"
                ),
                "completion_mode": completion_match.group(1),
                "completion_state_en": completion,
                "audience_focus_en": row["Audience Focus"],
                "audio_cues": _parse_audio(
                    row["BGM / SFX / Ambience"],
                    label=f"{shot_id} BGM / SFX / Ambience",
                ),
                "audio_cell_en": row["BGM / SFX / Ambience"],
                "dialogue": _parse_dialogue(
                    row["Dialogue"], label=f"{shot_id} Dialogue"
                ),
            }
        )
    return shots


def parse_screenplay_markdown(text: str) -> dict[str, Any]:
    if "```json" in text.casefold() or "_json" in text or "{" in text or "}" in text:
        raise StoryVideoError(
            "screenplay.md must contain Markdown tables only, with no embedded JSON"
        )
    lines = text.lstrip("\ufeff").splitlines()
    if not lines:
        raise StoryVideoError("screenplay.md is empty")
    title = TITLE_RE.fullmatch(lines[0].strip())
    if not title:
        raise StoryVideoError(
            "screenplay.md must begin with "
            "'# Cinematic Widescreen Production Script: <title>'"
        )

    index = _expect_heading(lines, 1, "## Production Information")
    production_information, index = _parse_field_table(
        lines,
        index,
        PRODUCTION_INFORMATION_FIELDS,
        label="Production Information",
    )

    index = _expect_heading(lines, index, "## Characters")
    character_rows, index = _parse_table(
        lines, index, columns=CHARACTER_TABLE_COLUMNS, label="Characters table"
    )
    characters: list[dict[str, Any]] = []
    entity_map: dict[str, dict[str, Any]] = {}
    character_names: set[str] = set()
    for row in character_rows:
        entity_id = row["Entity ID"]
        name = row["Character"]
        if not ENTITY_ID_RE.fullmatch(entity_id) or entity_id in entity_map:
            raise StoryVideoError("Characters table repeats or invalidates an Entity ID")
        if name.casefold() in character_names:
            raise StoryVideoError("Characters table repeats a Character name")
        character_names.add(name.casefold())
        member_types = (
            []
            if row["Member Types"] == "none"
            else [item.strip() for item in row["Member Types"].split(";")]
        )
        entity = {
            "entity_id": entity_id,
            "screenplay_character_name_en": name,
            "story_role": row["Story Role"],
            "narrative_function_en": row["Narrative Function"],
            "entity_kind": row["Kind"],
            "recurring": _yes_no(row["Recurring"], label=f"{entity_id} Recurring"),
            "group_role_type_en": row["Group Role"],
            "ensemble_member_types_en": member_types,
            "narration_eligibility": row["Narration"],
            "description_en": row["Description"],
        }
        characters.append(entity)
        entity_map[entity_id] = entity

    index = _expect_heading(lines, index, "## Script")
    raw_units: list[dict[str, Any]] = []
    while True:
        index = _next_nonempty(lines, index)
        if index >= len(lines) or lines[index].strip() == "## Continuity Appendix":
            break
        match = SCENE_UNIT_RE.fullmatch(lines[index].strip())
        if not match or int(match.group(1)) != len(raw_units) + 1:
            raise StoryVideoError(f"Unexpected screenplay line: {lines[index].strip()}")
        unit_number = int(match.group(1))
        index = _expect_heading(lines, index + 1, "### Scene Unit Information")
        fields, index = _parse_field_table(
            lines,
            index,
            SCENE_UNIT_INFORMATION_FIELDS,
            label=f"Scene Unit {unit_number} Information",
        )
        index = _expect_heading(lines, index, "### Shot Execution")
        shot_rows, index = _parse_table(
            lines,
            index,
            columns=SHOT_EXECUTION_COLUMNS,
            label=f"Scene Unit {unit_number} Shot Execution",
        )
        shots = _parse_shot_rows(shot_rows, label=f"Scene Unit {unit_number}")
        index = _expect_heading(lines, index, "### Character Staging")
        staging_rows, index = _parse_table(
            lines,
            index,
            columns=CHARACTER_STAGING_COLUMNS,
            label=f"Scene Unit {unit_number} Character Staging",
        )
        calls = []
        for row in staging_rows:
            calls.append(
                {
                    "entity_id": row["Entity ID"],
                    "presence_mode": row["Presence"],
                    "appearance_mode": row["Appearance"],
                    "appearance_trigger_en": row["Trigger"],
                    "entry_path_or_opening_position_en": row[
                        "Entry Path / Opening Position"
                    ],
                    "first_visible_block_id": row["First Visible Shot"],
                    "first_visible_moment_en": row["First Visible Moment"],
                    "landing_block_id": row["Landing Shot"],
                    "landing_result_en": row["Landing Moment / Result"],
                    "speaks": _yes_no(row["Speaks"], label=f"{row['Entity ID']} Speaks"),
                    "line_ids": _ids(
                        row["Lines"],
                        LINE_ID_RE,
                        label=f"{row['Entity ID']} Lines",
                        allow_none=True,
                    ),
                    "state_changing_action": _yes_no(
                        row["State Change"], label=f"{row['Entity ID']} State Change"
                    ),
                    "action_block_ids": _ids(
                        row["Action Shots"],
                        ACTION_ID_RE,
                        label=f"{row['Entity ID']} Action Shots",
                        allow_none=True,
                    ),
                }
            )
        raw_units.append(
            {
                "id": unit_number,
                "label_en": match.group(2).strip(),
                "fields": fields,
                "shots": shots,
                "performance_calls": calls,
            }
        )

    index = _expect_heading(lines, index, "## Continuity Appendix")
    index = _expect_heading(lines, index, "### Environments")
    rows, index = _parse_table(
        lines, index, columns=ENVIRONMENT_TABLE_COLUMNS, label="Environments table"
    )
    environments = [
        {
            "environment_id": row["Environment ID"],
            "logical_name_en": row["Logical Environment"],
            "scene_ids_json": _ids(
                row["Scene IDs"], SCENE_ID_RE, label="Environment Scene IDs"
            ),
            "int_ext": row["INT/EXT"],
            "time_context_en": row["Time Context"],
            "environment_facts_en": row["Environment Facts"],
            "story_function_en": row["Story Function"],
        }
        for row in rows
    ]

    index = _expect_heading(lines, index, "### Scenes")
    rows, index = _parse_table(lines, index, columns=SCENE_TABLE_COLUMNS, label="Scenes table")
    scenes = [
        {
            "scene_id": row["Scene ID"],
            "segment_ids_json": _ids(
                row["Segment IDs"], SEGMENT_ID_RE, label="Scene Segment IDs"
            ),
            "primary_time_en": row["Primary Time"],
            "primary_place_en": row["Primary Place"],
            "narrative_event_en": row["Narrative Event"],
            "entry_boundary": row["Entry Boundary"],
            "entry_reason_en": row["Entry Reason"],
            "continuity_reference_segment_id": row["Continuity Reference Segment"],
            "continuity_reference_reason_en": row["Continuity Reference Reason"],
        }
        for row in rows
    ]

    index = _expect_heading(lines, index, "### Scene Dramatic Contracts")
    rows, index = _parse_table(
        lines,
        index,
        columns=SCENE_CONTRACT_TABLE_COLUMNS,
        label="Scene Dramatic Contracts table",
    )
    scene_contracts = {
        row["Scene ID"]: {
            "scene_id": row["Scene ID"],
            "scene_purpose": row["Purpose"],
            "character_objective": row["Character Objective"],
            "obstacle": row["Obstacle"],
            "power_relationship": row["Power Relationship"],
            "turning_point": row["Turning Point"],
            "outcome": row["Outcome"],
            "visual_progression": row["Spatial Progression"],
            "exit_impulse": row["Exit Impulse"],
        }
        for row in rows
    }

    index = _expect_heading(lines, index, "### Continuity States")
    rows, index = _parse_table(
        lines,
        index,
        columns=CONTINUITY_STATE_TABLE_COLUMNS,
        label="Continuity States table",
    )
    continuity_states = [
        {
            "state_id": row["State ID"],
            "parent_state_ref": row["Parent State"],
            "changed_facts_en": row["Changed Facts"],
            "change_reason_en": row["Change Reason"],
        }
        for row in rows
    ]
    state_map = {item["state_id"]: item for item in continuity_states}

    index = _expect_heading(lines, index, "### Continuity Boundaries")
    rows, index = _parse_table(
        lines,
        index,
        columns=CONTINUITY_BOUNDARY_TABLE_COLUMNS,
        label="Continuity Boundaries table",
        allow_empty=True,
    )
    continuity_boundaries = [
        {
            "boundary_id": row["Boundary ID"],
            "from_segment_id": row["From Segment"],
            "to_segment_id": row["To Segment"],
            "from_state_ref": row["From State"],
            "to_state_ref": row["To State"],
            "handoff": row["Handoff"],
            "transition_type": row["Transition"],
            "dramatic_reason_en": row["Dramatic Reason"],
            "audio_handoff_en": row["Audio Handoff"],
            "continuity_handoff_en": row["Continuity Handoff"],
        }
        for row in rows
    ]
    if _next_nonempty(lines, index) != len(lines):
        raise StoryVideoError("screenplay.md contains content after the appendix")

    boundary_map = {item["boundary_id"]: item for item in continuity_boundaries}
    segments: list[dict[str, Any]] = []
    for unit_index, raw in enumerate(raw_units, start=1):
        fields = raw["fields"]
        expected_segment_id = f"segment-{unit_index:03d}"
        if fields["Segment ID"] != expected_segment_id:
            raise StoryVideoError(
                f"Scene Unit {unit_index} Segment ID must be {expected_segment_id}"
            )
        scene_id = fields["Scene ID"]
        if not SCENE_ID_RE.fullmatch(scene_id):
            raise StoryVideoError(f"{expected_segment_id} has an invalid Scene ID")
        if not SLUGLINE_RE.fullmatch(fields["Slugline"]):
            raise StoryVideoError(f"{expected_segment_id} has an invalid Slugline")
        if not re.fullmatch(r"[0-9]+", fields["Duration Seconds"]):
            raise StoryVideoError(
                f"{expected_segment_id} Duration Seconds must be an integer"
            )
        if not _concrete(fields["Environment"]) or not _concrete(
            fields["Dramatic Purpose"]
        ):
            raise StoryVideoError(
                f"{expected_segment_id} requires concrete Environment and Dramatic Purpose"
            )
        contract = scene_contracts.get(scene_id)
        if contract is None:
            raise StoryVideoError(f"{expected_segment_id} references an unknown Scene")
        start_ref = fields["Start State"]
        end_ref = fields["End State"]
        if start_ref not in state_map or end_ref not in state_map:
            raise StoryVideoError(f"{expected_segment_id} references an unknown continuity state")
        incoming_ref = fields["Incoming Boundary"]
        if unit_index == 1:
            if incoming_ref != "opening":
                raise StoryVideoError("segment-001 Incoming Boundary must be opening")
        else:
            incoming = boundary_map.get(incoming_ref)
            if incoming is None:
                raise StoryVideoError(
                    f"{expected_segment_id} references an unknown Incoming Boundary"
                )
        for call in raw["performance_calls"]:
            if call["entity_id"] not in entity_map:
                raise StoryVideoError(
                    f"{expected_segment_id} stages an undeclared Entity ID"
                )
        plan = {
            "segment_id": expected_segment_id,
            "scene_id": scene_id,
            "estimated_duration_seconds": int(fields["Duration Seconds"]),
            "dramatic_workload": fields["Workload"],
            "location_time_environment_en": fields["Environment"],
            "narrative_purpose_en": fields["Dramatic Purpose"],
            "scene_dramatic_contract": contract,
            "start_state_ref": start_ref,
            "end_state_ref": end_ref,
            "incoming_boundary_ref": incoming_ref,
        }
        segments.append(
            {
                "id": unit_index,
                "heading_en": fields["Slugline"],
                "label_en": raw["label_en"],
                "shots": raw["shots"],
                "story_plan": plan,
                "performance_calls": raw["performance_calls"],
            }
        )

    screenplay = {
        "screenplay_title_en": title.group(1).strip(),
        "production_information": production_information,
        "characters": characters,
        "environments": environments,
        "scenes": scenes,
        "scene_dramatic_contracts": scene_contracts,
        "continuity_states": continuity_states,
        "continuity_boundaries": continuity_boundaries,
        "segments": segments,
    }
    validate_screenplay(screenplay)
    return screenplay


def validate_cinematic_segment_contract(
    *,
    segment_id: str,
    scene_id: str,
    scene_contract: Any,
    shots: list[dict[str, Any]],
    known_beat_ids: set[str] | None = None,
) -> None:
    if not isinstance(scene_contract, dict) or scene_contract.get("scene_id") != scene_id:
        raise StoryVideoError(f"{segment_id} has an invalid Scene dramatic contract")
    for field in (
        "scene_purpose",
        "character_objective",
        "obstacle",
        "power_relationship",
        "turning_point",
        "outcome",
        "visual_progression",
        "exit_impulse",
    ):
        if not _concrete(scene_contract.get(field)):
            raise StoryVideoError(f"{segment_id} Scene contract {field} must be concrete")
    if not isinstance(shots, list) or not shots:
        raise StoryVideoError(f"{segment_id} must contain at least one authored Shot Beat")
    known = known_beat_ids if known_beat_ids is not None else set()
    for shot in shots:
        beat_id = shot.get("beat_id")
        if not isinstance(beat_id, str) or not BEAT_ID_RE.fullmatch(beat_id) or beat_id in known:
            raise StoryVideoError(f"{segment_id} repeats or invalidates a Beat ID")
        known.add(beat_id)
        if STAGE_TABLEAU_RISK_RE.search(str(shot.get("visual_action_en", ""))):
            raise StoryVideoError(f"{segment_id} contains stage-tableau action language")


def validate_adjacent_visual_boundary_contract(
    *,
    segment_id: str,
    predecessor_scene_id: str,
    current_scene_id: str,
    boundary: dict[str, Any],
    predecessor_final_shot: dict[str, Any],
) -> None:
    incoming = boundary["handoff"]
    same_scene = predecessor_scene_id == current_scene_id
    if same_scene and incoming == "independent":
        raise StoryVideoError(f"{segment_id} shares a Scene with its predecessor and must be serial")
    if not same_scene and incoming == "continuous_motion":
        raise StoryVideoError(f"{segment_id} cannot carry continuous_motion across a Scene boundary")
    if incoming == "continuous_motion":
        combined = " ".join(
            [
                boundary["continuity_handoff_en"],
                predecessor_final_shot["completion_state_en"],
                predecessor_final_shot["blocking_movement_en"],
            ]
        )
        if not INHERITED_VISUAL_PHASE_RE.search(combined):
            raise StoryVideoError(
                f"{segment_id} continuous_motion must name its unfinished inherited phase"
            )


def _validate_performance(screenplay: dict[str, Any]) -> None:
    entities = {item["entity_id"]: item for item in screenplay["characters"]}
    used_entities: set[str] = set()
    speaking_entities: set[str] = set()
    for segment in screenplay["segments"]:
        segment_id = segment["story_plan"]["segment_id"]
        shots = segment["shots"]
        shot_map = {shot["shot_id"]: shot for shot in shots}
        calls = segment["performance_calls"]
        call_map = {call["entity_id"]: call for call in calls}
        if len(call_map) != len(calls) or any(entity_id not in entities for entity_id in call_map):
            raise StoryVideoError(f"{segment_id} repeats or invents Character Staging")
        used_entities.update(call_map)

        expected_performers = {
            entity_id for shot in shots for entity_id in shot["performer_ids"]
        }
        expected_speakers = {
            shot["dialogue"]["speaker_entity_id"]
            for shot in shots
            if shot["dialogue"] is not None
        }
        if set(call_map) != expected_performers | expected_speakers:
            raise StoryVideoError(
                f"{segment_id} Character Staging must cover exactly its performers and speakers"
            )

        line_owner: dict[str, str] = {}
        for call in calls:
            entity_id = call["entity_id"]
            entity = entities[entity_id]
            presence = call["presence_mode"]
            appearance = call["appearance_mode"]
            if presence not in PRESENCE_MODES or appearance not in APPEARANCE_MODES:
                raise StoryVideoError(f"{entity_id} has invalid Presence or Appearance")
            if call["speaks"] != bool(call["line_ids"]):
                raise StoryVideoError(f"{entity_id} Speaks and Lines disagree")
            if call["speaks"]:
                speaking_entities.add(entity_id)
            for line_id in call["line_ids"]:
                if line_id in line_owner:
                    raise StoryVideoError(f"{line_id} has repeated Character Staging ownership")
                line_owner[line_id] = entity_id

            action_ids = call["action_block_ids"]
            if any(shot_id not in shot_map for shot_id in action_ids):
                raise StoryVideoError(f"{entity_id} references an unknown Action Shot")
            actual_action_ids = [
                shot["shot_id"] for shot in shots if entity_id in shot["performer_ids"]
            ]
            if action_ids != actual_action_ids:
                raise StoryVideoError(
                    f"{entity_id} Action Shots must exactly match authored Shot performers"
                )

            appearance_fields = (
                call["appearance_trigger_en"],
                call["entry_path_or_opening_position_en"],
                call["first_visible_block_id"],
                call["first_visible_moment_en"],
                call["landing_block_id"],
                call["landing_result_en"],
            )
            if presence != "on_screen":
                if appearance != "not_visible" or any(
                    value != "not_visible" for value in appearance_fields
                ):
                    raise StoryVideoError(
                        f"{entity_id} O.S./V.O. staging must use not_visible throughout"
                    )
                if action_ids:
                    raise StoryVideoError(f"{entity_id} O.S./V.O. cannot own visible Action Shots")
            else:
                if appearance not in {"present_at_open", "enters"}:
                    raise StoryVideoError(
                        f"{entity_id} on-screen staging requires present_at_open or enters"
                    )
                if appearance == "present_at_open":
                    if call["appearance_trigger_en"] != "opening":
                        raise StoryVideoError(
                            f"{entity_id} present_at_open Trigger must be opening"
                        )
                elif not _concrete(call["appearance_trigger_en"]):
                    raise StoryVideoError(f"{entity_id} entrance Trigger must be concrete")
                if not _concrete(call["entry_path_or_opening_position_en"]):
                    raise StoryVideoError(
                        f"{entity_id} requires a concrete Entry Path / Opening Position"
                    )
                first_id = call["first_visible_block_id"]
                landing_id = call["landing_block_id"]
                if first_id not in action_ids or landing_id not in action_ids:
                    raise StoryVideoError(
                        f"{entity_id} First Visible and Landing Shots must be owned Action Shots"
                    )
                positions = {shot["shot_id"]: i for i, shot in enumerate(shots)}
                if positions[first_id] > positions[landing_id]:
                    raise StoryVideoError(
                        f"{entity_id} First Visible Shot must not follow Landing Shot"
                    )
                if not _concrete(call["first_visible_moment_en"]):
                    raise StoryVideoError(
                        f"{entity_id} First Visible Moment must describe an observable event"
                    )
                if not _concrete(call["landing_result_en"]):
                    raise StoryVideoError(
                        f"{entity_id} Landing Moment / Result must describe an observable event"
                    )
                if shot_map[landing_id]["completion_mode"] != "completed":
                    raise StoryVideoError(
                        f"{entity_id} Landing Shot must have a completed action state"
                    )

            if entity["entity_kind"] == "anonymous_ensemble" and call["speaks"]:
                raise StoryVideoError(f"{entity_id} anonymous ensemble cannot own dialogue")

        expected_line_owner = {
            shot["dialogue"]["line_id"]: shot["dialogue"]["speaker_entity_id"]
            for shot in shots
            if shot["dialogue"] is not None
        }
        if line_owner != expected_line_owner:
            raise StoryVideoError(
                f"{segment_id} Character Staging must own every Dialogue Line exactly once"
            )

        for shot in shots:
            relations = shot["gaze_relations"]
            dialogue = shot["dialogue"]
            nonvisible_speaker_ids = set()
            if dialogue is not None:
                dialogue_call = call_map[dialogue["speaker_entity_id"]]
                if dialogue_call["presence_mode"] != "on_screen":
                    nonvisible_speaker_ids.add(dialogue["speaker_entity_id"])
            if set(relations) != set(shot["performer_ids"]) | nonvisible_speaker_ids:
                raise StoryVideoError(
                    f"{shot['shot_id']} Gaze / Addressee must cover every visible Performer and non-visible speaker once"
                )
            for performer_id, relation in relations.items():
                if performer_id not in call_map:
                    raise StoryVideoError(
                        f"{shot['shot_id']} gives gaze authority to an unstaged entity"
                    )
                if call_map[performer_id]["presence_mode"] == "on_screen" and (
                    relation["facing"] == "not_visible" or relation["gaze"] == "not_visible"
                ):
                    raise StoryVideoError(
                        f"{shot['shot_id']} visible performer requires concrete facing and gaze"
                    )
                if call_map[performer_id]["presence_mode"] != "on_screen" and (
                    relation["facing"] != "not_visible" or relation["gaze"] != "not_visible"
                ):
                    raise StoryVideoError(
                        f"{shot['shot_id']} non-visible speaker must use not_visible facing and gaze"
                    )
            if dialogue is None:
                continue
            speaker_id = dialogue["speaker_entity_id"]
            call = call_map[speaker_id]
            relation = relations.get(speaker_id)
            if call["presence_mode"] == "on_screen":
                if speaker_id not in shot["performer_ids"] or relation is None:
                    raise StoryVideoError(
                        f"{dialogue['line_id']} on-screen speaker lacks same-Shot performance and gaze"
                    )
            else:
                if relation is None or relation["facing"] != "not_visible" or relation["gaze"] != "not_visible":
                    raise StoryVideoError(
                        f"{dialogue['line_id']} O.S./V.O. requires not_visible facing and gaze"
                    )
            target = relation["target"]
            if target not in call_map and target not in DIALOGUE_ADDRESSEE_SPECIALS:
                raise StoryVideoError(f"{dialogue['line_id']} has an undeclared dialogue Addressee")
            if target == speaker_id:
                raise StoryVideoError(f"{dialogue['line_id']} must use self for self-address")

    if used_entities != set(entities):
        raise StoryVideoError("Characters table contains unused entities")
    for entity_id, entity in entities.items():
        member_types = entity["ensemble_member_types_en"]
        if entity["entity_kind"] == "anonymous_ensemble":
            if entity["recurring"] or entity["group_role_type_en"] == "none" or not member_types:
                raise StoryVideoError(
                    f"{entity_id} anonymous ensemble needs a non-recurring Group Role and Member Types"
                )
            if entity_id in speaking_entities:
                raise StoryVideoError(f"{entity_id} anonymous ensemble cannot speak")
        elif entity["group_role_type_en"] != "none" or member_types:
            raise StoryVideoError(
                f"{entity_id} individual must use none for Group Role and Member Types"
            )


def validate_screenplay(screenplay: dict[str, Any]) -> None:
    production = screenplay["production_information"]
    if production["Production Type"] != "cinematic_widescreen":
        raise StoryVideoError("screenplay.md Production Type must be cinematic_widescreen")
    if production["Target Language"] != "English":
        raise StoryVideoError("screenplay.md Target Language must be English")
    if production["Target Age Band"] not in TARGET_AGE_BANDS:
        raise StoryVideoError("screenplay.md Target Age Band is invalid")
    if not _present(production["Genre"]):
        raise StoryVideoError("Production Information Genre must be present")
    for field in (
        "Educational Theme",
        "Story Premise",
        "Dramatic Strategy",
        "Safety and Culture",
        "Opening Event",
        "Ending Event and Obligation",
    ):
        if not _concrete(production[field]):
            raise StoryVideoError(f"Production Information {field} must be concrete")

    characters = screenplay["characters"]
    if not characters or not any(item["story_role"] == "lead" for item in characters):
        raise StoryVideoError("screenplay.md needs at least one lead Character")
    for item in characters:
        if item["story_role"] not in CHARACTER_STORY_ROLES:
            raise StoryVideoError(
                f"{item['screenplay_character_name_en']} has an invalid Story Role"
            )
        if item["narration_eligibility"] not in NARRATION_ELIGIBILITIES:
            raise StoryVideoError(
                f"{item['screenplay_character_name_en']} has invalid Narration authority"
            )
        if not _concrete(item["narrative_function_en"]) or not _concrete(item["description_en"]):
            raise StoryVideoError(
                f"{item['screenplay_character_name_en']} Character fields must be concrete"
            )
    for entity in characters:
        if entity["entity_kind"] not in ENTITY_KINDS:
            raise StoryVideoError(f"{entity['entity_id']} has an invalid Kind")

    environments = screenplay["environments"]
    scene_environment: dict[str, dict[str, Any]] = {}
    for index, environment in enumerate(environments, start=1):
        expected = f"environment-{index:03d}"
        if environment["environment_id"] != expected or environment["int_ext"] not in ENVIRONMENT_KINDS:
            raise StoryVideoError(f"Environment {index} must be {expected} with valid INT/EXT")
        for field in ("logical_name_en", "time_context_en"):
            if not _present(environment[field]):
                raise StoryVideoError(f"{expected} {field} must be present")
        for field in ("environment_facts_en", "story_function_en"):
            if not _concrete(environment[field]):
                raise StoryVideoError(f"{expected} {field} must be concrete")
        for scene_id in environment["scene_ids_json"]:
            if scene_id in scene_environment:
                raise StoryVideoError(f"{scene_id} appears in multiple Environments")
            scene_environment[scene_id] = environment

    scenes = screenplay["scenes"]
    scene_segments: list[str] = []
    scene_by_segment: dict[str, str] = {}
    for index, scene in enumerate(scenes, start=1):
        expected = f"scene-{index:03d}"
        if scene["scene_id"] != expected or scene["entry_boundary"] not in SCENE_ENTRY_BOUNDARIES:
            raise StoryVideoError(f"Scene {index} must be {expected} with valid Entry Boundary")
        if (index == 1) != (scene["entry_boundary"] == "opening"):
            raise StoryVideoError("Only scene-001 may use opening")
        for field in ("primary_time_en", "primary_place_en"):
            if not _present(scene[field]):
                raise StoryVideoError(f"{expected} {field} must be present")
        for field in (
            "narrative_event_en",
            "entry_reason_en",
            "continuity_reference_reason_en",
        ):
            if not _concrete(
                scene[field], allow_none=field == "continuity_reference_reason_en"
            ):
                raise StoryVideoError(f"{expected} {field} must be concrete")
        for segment_id in scene["segment_ids_json"]:
            if segment_id in scene_by_segment:
                raise StoryVideoError(f"{segment_id} appears in multiple Scenes")
            scene_by_segment[segment_id] = expected
            scene_segments.append(segment_id)
    if set(scene_environment) != {item["scene_id"] for item in scenes}:
        raise StoryVideoError("Scenes and Environment bindings differ")
    if set(screenplay["scene_dramatic_contracts"]) != {item["scene_id"] for item in scenes}:
        raise StoryVideoError("Every Scene needs exactly one Scene Dramatic Contract")

    states = screenplay["continuity_states"]
    for index, state in enumerate(states, start=1):
        expected = f"state-{index:03d}"
        expected_parent = "none" if index == 1 else f"state-{index - 1:03d}"
        if state["state_id"] != expected or state["parent_state_ref"] != expected_parent:
            raise StoryVideoError(
                f"Continuity State {index} must be {expected} with parent {expected_parent}"
            )
        if not _concrete(state["changed_facts_en"]) or not _concrete(state["change_reason_en"]):
            raise StoryVideoError(f"{expected} needs concrete changed facts and reason")

    segments = screenplay["segments"]
    boundaries = screenplay["continuity_boundaries"]
    if not segments:
        raise StoryVideoError("screenplay.md requires at least one Scene Unit")
    if len(boundaries) != len(segments) - 1:
        raise StoryVideoError("Continuity Boundaries must cover every adjacent Segment once")
    state_ids = {item["state_id"] for item in states}
    for index, boundary in enumerate(boundaries, start=1):
        expected = f"boundary-{index:03d}"
        if (
            boundary["boundary_id"] != expected
            or boundary["from_segment_id"] != f"segment-{index:03d}"
            or boundary["to_segment_id"] != f"segment-{index + 1:03d}"
            or boundary["from_state_ref"] not in state_ids
            or boundary["to_state_ref"] not in state_ids
            or boundary["handoff"] not in INCOMING_VISUAL_REQUIREMENTS
            or boundary["transition_type"] not in TRANSITION_DESIGN_TYPES - {"final_end"}
        ):
            raise StoryVideoError(f"Continuity Boundary {index} is invalid")
        for field in ("dramatic_reason_en", "audio_handoff_en", "continuity_handoff_en"):
            if not _concrete(boundary[field]):
                raise StoryVideoError(f"{expected} {field} must be concrete")

    runtime = 0
    known_beats: set[str] = set()
    action_ids: list[str] = []
    line_ids: list[str] = []
    for index, segment in enumerate(segments, start=1):
        plan = segment["story_plan"]
        expected = f"segment-{index:03d}"
        if segment["id"] != index or plan["segment_id"] != expected:
            raise StoryVideoError("Scene Units and Segment IDs must be consecutive")
        if scene_by_segment.get(expected) != plan["scene_id"]:
            raise StoryVideoError(f"{expected} disagrees with Scenes table")
        if not SLUGLINE_RE.fullmatch(segment["heading_en"]):
            raise StoryVideoError(f"{expected} has an invalid Slugline")
        environment = scene_environment.get(plan["scene_id"])
        slug_kind = segment["heading_en"].split(".", 1)[0]
        if environment is None or (
            environment["int_ext"] != "MIXED" and environment["int_ext"] != slug_kind
        ):
            raise StoryVideoError(f"{expected} Slugline conflicts with its Environment")
        if plan["dramatic_workload"] not in DRAMATIC_WORKLOADS:
            raise StoryVideoError(f"{expected} has an invalid Workload")
        duration = plan["estimated_duration_seconds"]
        if isinstance(duration, bool) or not 4 <= duration <= 15:
            raise StoryVideoError(f"{expected} Duration Seconds must be 4-15")
        runtime += duration
        if not any(shot["audio_cues"] for shot in segment["shots"]):
            raise StoryVideoError(f"{expected} requires at least one authored audio event")
        for shot in segment["shots"]:
            action_ids.append(shot["shot_id"])
            if shot["dialogue"] is not None:
                line_ids.append(shot["dialogue"]["line_id"])
        validate_cinematic_segment_contract(
            segment_id=expected,
            scene_id=plan["scene_id"],
            scene_contract=plan["scene_dramatic_contract"],
            shots=segment["shots"],
            known_beat_ids=known_beats,
        )
        spoken_entries = [
            shot["dialogue"]
            for shot in segment["shots"]
            if shot["dialogue"] is not None
        ]
        dialogue_words = sum(
            len(WORD_RE.findall(item["spoken_text_en"])) for item in spoken_entries
        )
        minimum_playable_seconds = (
            dialogue_words / DIALOGUE_WORDS_PER_SECOND
            + len(spoken_entries) * DIALOGUE_TURN_ALLOWANCE_SECONDS
            + MINIMUM_ACTION_REACTION_SECONDS
        )
        if duration + 1e-6 < minimum_playable_seconds:
            raise StoryVideoError(
                f"{expected} duration is below its 2.6 words-per-second "
                "dialogue/action floor"
            )
        call_map = {
            call["entity_id"]: call for call in segment["performance_calls"]
        }
        character_map = {item["entity_id"]: item for item in characters}
        for entry in spoken_entries:
            speaker_id = entry["speaker_entity_id"]
            if speaker_id not in call_map or speaker_id not in character_map:
                raise StoryVideoError(
                    f"{entry['line_id']} lacks declared speaker staging or gaze/addressee"
                )
            if (
                call_map[speaker_id]["presence_mode"] == "voice_over"
                and character_map[speaker_id]["narration_eligibility"]
                == "not_allowed"
            ):
                raise StoryVideoError(
                    f"{character_map[speaker_id]['screenplay_character_name_en']} cannot narrate V.O."
                )

        completion_mode = segment["shots"][-1]["completion_mode"]
        if index < len(segments):
            handoff = boundaries[index - 1]["handoff"]
            if (completion_mode == "open") != (handoff == "continuous_motion"):
                raise StoryVideoError(
                    f"{expected} final Completion State must agree with its Handoff"
                )
        elif completion_mode != "completed":
            raise StoryVideoError("The final Scene Unit must end with completed action")
        if index > 1:
            validate_adjacent_visual_boundary_contract(
                segment_id=expected,
                predecessor_scene_id=segments[index - 2]["story_plan"]["scene_id"],
                current_scene_id=plan["scene_id"],
                boundary=boundaries[index - 2],
                predecessor_final_shot=segments[index - 2]["shots"][-1],
            )

    expected_actions = [f"A-{index:03d}" for index in range(1, len(action_ids) + 1)]
    expected_lines = [f"L-{index:03d}" for index in range(1, len(line_ids) + 1)]
    if action_ids != expected_actions:
        raise StoryVideoError("Shot IDs must be globally consecutive in screenplay order")
    if line_ids != expected_lines:
        raise StoryVideoError("Dialogue Line IDs must be globally consecutive in screenplay order")
    try:
        declared_runtime = int(production["Estimated Runtime Seconds"])
    except ValueError as exc:
        raise StoryVideoError("Estimated Runtime Seconds must be an integer") from exc
    if runtime != declared_runtime or runtime > 240:
        raise StoryVideoError("Screenplay runtime is invalid or disagrees across tables")
    if scene_segments != [f"segment-{index:03d}" for index in range(1, len(segments) + 1)]:
        raise StoryVideoError("Scenes must partition Segments once in order")
    _validate_performance(screenplay)


def load_screenplay_file(path: str | Path) -> dict[str, Any]:
    screenplay_path = Path(path).expanduser().resolve()
    if screenplay_path.name != "screenplay.md":
        raise StoryVideoError("Screenplay file must be named screenplay.md")
    try:
        text = screenplay_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise StoryVideoError(f"Invalid screenplay file: {screenplay_path}") from exc
    return parse_screenplay_markdown(text)
