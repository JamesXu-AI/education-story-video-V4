"""Derive and validate performance authority from the single screenplay.md source."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from story_video.runtime_support import StoryVideoError
from story_video.screenplay_contract import load_screenplay_file


MAP_RELATIVE_PATH = Path("screenplay-writer/screenplay.md")
ROOT_KEYS = {
    "contract",
    "performance_entities",
    "scene_segment_calls",
}
ENTITY_KEYS = {
    "entity_id",
    "screenplay_character_name_en",
    "story_role",
    "narrative_function_en",
    "entity_kind",
    "recurring",
    "group_role_type_en",
    "ensemble_member_types_en",
    "narration_eligibility",
    "description_en",
}
SEGMENT_KEYS = {
    "scene_id",
    "segment_id",
    "duration_seconds",
    "screenplay_participants",
    "calls",
}
CALL_KEYS = {
    "entity_id",
    "screenplay_character_name_en",
    "entity_kind",
    "presence_mode",
    "speaks",
    "line_ids",
    "state_changing_action",
    "recurring",
    "group_role_type_en",
    "action_shot_ids",
}
ENTITY_KINDS = {"individual", "anonymous_ensemble"}
PRESENCE_MODES = {"on_screen", "off_screen", "voice_over"}
ASSET_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _english_identity_forms(name: str) -> set[str]:
    """Return exact word forms that cannot reappear in a silent roster."""

    words = re.findall(r"[a-z0-9]+", name.casefold())
    if not words:
        return set()
    identity = words[-1]
    forms = {identity, identity + "s"}
    if identity.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(identity + "es")
    if len(identity) > 1 and identity.endswith("y") and identity[-2] not in "aeiou":
        forms.add(identity[:-1] + "ies")
    return forms


def _dialogue_identity_named_in_member_type(
    member_type: str, dialogue_character_names: list[str]
) -> str | None:
    words = set(re.findall(r"[a-z0-9]+", member_type.casefold()))
    for name in dialogue_character_names:
        if words & _english_identity_forms(name):
            return name
    return None


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise StoryVideoError(f"{label} must use exact keys: {sorted(keys)}")
    return value


def validate_character_performance_map(
    value: dict[str, Any],
    *,
    screenplay_path: Path,
) -> dict[str, Any]:
    """Validate exact screenplay coverage and role-call integrity."""

    _exact(value, ROOT_KEYS, "character-performance-map root")
    if value["contract"] != "character-performance-map":
        raise StoryVideoError("character-performance-map fixed fields are invalid")

    screenplay = load_screenplay_file(screenplay_path)

    screenplay_entities = {
        item["entity_id"]: item for item in screenplay["characters"]
    }
    raw_entities = value["performance_entities"]
    if not isinstance(raw_entities, list) or not raw_entities:
        raise StoryVideoError("performance_entities must be non-empty")
    entities: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_entities, start=1):
        entity = _exact(raw, ENTITY_KEYS, f"performance entity {index}")
        entity_id = entity["entity_id"]
        if not isinstance(entity_id, str) or not entity_id or entity_id in entities:
            raise StoryVideoError("performance entity IDs must be unique text")
        if screenplay_entities.get(entity_id) != entity:
            raise StoryVideoError(f"{entity_id} differs from screenplay Character authority")
        if entity["entity_kind"] not in ENTITY_KINDS or not isinstance(
            entity["recurring"], bool
        ):
            raise StoryVideoError(f"{entity_id} kind/recurring fields are invalid")
        if entity["entity_kind"] == "anonymous_ensemble" and entity["recurring"]:
            raise StoryVideoError(f"{entity_id} anonymous ensemble cannot be recurring")
        for field in (
            "screenplay_character_name_en",
            "group_role_type_en",
            "description_en",
        ):
            if not isinstance(entity[field], str) or not entity[field].strip():
                raise StoryVideoError(f"{entity_id} {field} must be non-empty text")
        member_types = entity["ensemble_member_types_en"]
        if not isinstance(member_types, list):
            raise StoryVideoError(
                f"{entity_id} ensemble_member_types_en must be an array"
            )
        if entity["entity_kind"] == "anonymous_ensemble" and (
            not member_types
            or any(not isinstance(item, str) or not item.strip() for item in member_types)
            or len({item.strip().casefold() for item in member_types})
            != len(member_types)
        ):
            raise StoryVideoError(
                f"{entity_id} anonymous ensemble requires unique concrete "
                "ensemble_member_types_en"
            )
        entities[entity_id] = entity

    raw_segments = value["scene_segment_calls"]
    if not isinstance(raw_segments, list) or len(raw_segments) != len(screenplay["segments"]):
        raise StoryVideoError("scene_segment_calls must exactly cover screenplay Segments")
    speaking_entity_ids = {
        call.get("entity_id")
        for segment in raw_segments
        if isinstance(segment, dict) and isinstance(segment.get("calls"), list)
        for call in segment["calls"]
        if isinstance(call, dict) and call.get("speaks") is True
    }
    used_entities: set[str] = set()
    called_segments_by_entity: dict[str, list[str]] = {
        entity_id: [] for entity_id in entities
    }
    for index, (raw, screenplay_segment) in enumerate(
        zip(raw_segments, screenplay["segments"]), start=1
    ):
        segment = _exact(raw, SEGMENT_KEYS, f"performance Segment {index}")
        plan = screenplay_segment["story_plan"]
        expected_fixed = {
            "scene_id": plan["scene_id"],
            "segment_id": plan["segment_id"],
            "duration_seconds": plan["estimated_duration_seconds"],
            "screenplay_participants": [
                call["entity_id"]
                for call in screenplay_segment["performance_calls"]
            ],
        }
        for field, expected in expected_fixed.items():
            if segment[field] != expected:
                raise StoryVideoError(f"{plan['segment_id']} {field} differs from screenplay")
        calls = segment["calls"]
        if not isinstance(calls, list) or not calls:
            raise StoryVideoError(f"{plan['segment_id']} calls must be non-empty")
        called_ids: set[str] = set()
        represented_participants: set[str] = set()
        referenced_line_ids: set[str] = set()
        for call_index, raw_call in enumerate(calls, start=1):
            call = _exact(raw_call, CALL_KEYS, f"{plan['segment_id']} call {call_index}")
            entity = entities.get(call["entity_id"])
            if entity is None or call["entity_id"] in called_ids:
                raise StoryVideoError(f"{plan['segment_id']} repeats or invents an entity")
            called_ids.add(call["entity_id"])
            used_entities.add(call["entity_id"])
            called_segments_by_entity[call["entity_id"]].append(plan["segment_id"])
            represented_participants.add(entity["entity_id"])
            for field in (
                "screenplay_character_name_en",
                "entity_kind",
                "recurring",
                "group_role_type_en",
            ):
                if call[field] != entity[field]:
                    raise StoryVideoError(
                        f"{plan['segment_id']} call {call['entity_id']} differs from entity authority"
                    )
            if call["presence_mode"] not in PRESENCE_MODES:
                raise StoryVideoError(f"{call['entity_id']} presence mode is invalid")
            for flag in ("speaks", "state_changing_action"):
                if not isinstance(call[flag], bool):
                    raise StoryVideoError(f"{call['entity_id']} {flag} must be boolean")
            line_ids = call["line_ids"]
            if not isinstance(line_ids, list) or call["speaks"] != bool(line_ids):
                raise StoryVideoError(f"{call['entity_id']} speech flag/lines differ")
            if any(line_id in referenced_line_ids for line_id in line_ids):
                raise StoryVideoError("Dialogue Line ownership is repeated")
            referenced_line_ids.update(line_ids)
            action_shot_ids = call["action_shot_ids"]
            if not isinstance(action_shot_ids, list):
                raise StoryVideoError(f"{call['entity_id']} action_shot_ids must be a list")
            if call["entity_kind"] == "anonymous_ensemble" and (
                call["presence_mode"] != "on_screen"
                or call["speaks"]
                or call["state_changing_action"]
            ):
                raise StoryVideoError(
                    "anonymous ensemble may only own shared on-screen group performance"
                )
        if represented_participants != {
            call["entity_id"]
            for call in screenplay_segment["performance_calls"]
        }:
            raise StoryVideoError(f"{plan['segment_id']} participant call coverage differs")
        expected_line_ids = {
            shot["dialogue"]["line_id"]
            for shot in screenplay_segment["shots"]
            if shot["dialogue"] is not None
        }
        if referenced_line_ids != expected_line_ids:
            raise StoryVideoError(f"{plan['segment_id']} dialogue call coverage differs")
        dialogue_character_ids = called_ids & speaking_entity_ids
        visible_dialogue_ids = {
            call["entity_id"]
            for call in calls
            if call["entity_id"] in speaking_entity_ids
            and call["presence_mode"] == "on_screen"
        }
        nonvisible_dialogue_ids = {
            call["entity_id"]
            for call in calls
            if call["entity_id"] in speaking_entity_ids
            and call["presence_mode"] != "on_screen"
        }
        group_roles = {
            call["group_role_type_en"]
            for call in calls
            if call["presence_mode"] == "on_screen"
            and call["entity_id"] not in speaking_entity_ids
        }
        if len(dialogue_character_ids) > 3:
            raise StoryVideoError(
                f"{plan['segment_id']} exceeds three dialogue character images"
            )
        if len(visible_dialogue_ids) > 2 or len(nonvisible_dialogue_ids) > 1:
            raise StoryVideoError(
                f"{plan['segment_id']} exceeds two visible plus one non-visible "
                "dialogue characters"
            )
        if len(group_roles) > 2:
            raise StoryVideoError(
                f"{plan['segment_id']} exceeds two background group images"
            )
        if 1 + len(dialogue_character_ids) + len(group_roles) > 6:
            raise StoryVideoError(
                f"{plan['segment_id']} exceeds six static reference images"
            )
        dialogue_turn_count = sum(len(call["line_ids"]) for call in calls)
        if dialogue_turn_count > 3:
            raise StoryVideoError(
                f"{plan['segment_id']} exceeds three dialogue turns"
            )
    if used_entities != set(entities):
        raise StoryVideoError("performance entity authority contains unused entities")
    if set(entities) != set(screenplay_entities):
        raise StoryVideoError(
            "performance entities must cover every screenplay Character"
        )
    for entity_id, entity in entities.items():
        group_role = entity["group_role_type_en"]
        if not isinstance(group_role, str) or not group_role.strip():
            raise StoryVideoError(f"{entity_id} group_role_type_en must be text")
        if (entity_id in speaking_entity_ids) != (group_role == "none"):
            raise StoryVideoError(
                f"{entity_id} dialogue ownership and group_role_type_en disagree"
            )
        if entity_id in speaking_entity_ids and entity["ensemble_member_types_en"]:
            raise StoryVideoError(
                f"{entity_id} dialogue owner must use empty ensemble_member_types_en"
            )
        if entity_id not in speaking_entity_ids and not entity["ensemble_member_types_en"]:
            raise StoryVideoError(
                f"{entity_id} silent entity requires ensemble_member_types_en"
            )
        if (
            entity["entity_kind"] == "individual"
            and len(called_segments_by_entity[entity_id]) > 1
            and entity["recurring"] is not True
        ):
            raise StoryVideoError(
                f"{entity_id} appears in multiple Segments and must be recurring"
            )
    member_type_owner: dict[tuple[str, str], str] = {}
    dialogue_character_names = [
        entities[entity_id]["screenplay_character_name_en"]
        for entity_id in speaking_entity_ids
    ]
    for entity_id, entity in entities.items():
        for member_type in entity["ensemble_member_types_en"]:
            forbidden_name = _dialogue_identity_named_in_member_type(
                member_type, dialogue_character_names
            )
            if forbidden_name is not None:
                raise StoryVideoError(
                    f"Silent member type {member_type!r} repeats dialogue portrait "
                    f"identity/species {forbidden_name!r}; an independently portrayed "
                    "identity/species is forbidden from every group roster"
                )
            key = (entity["group_role_type_en"].casefold(), member_type.strip().casefold())
            if key in member_type_owner:
                raise StoryVideoError(
                    f"Silent group role {entity['group_role_type_en']} repeats member type "
                    f"{member_type} across {member_type_owner[key]} and {entity_id}"
                )
            member_type_owner[key] = entity_id
    dialogue_asset_slugs: dict[str, str] = {}
    for entity_id in speaking_entity_ids:
        label = entities[entity_id]["screenplay_character_name_en"]
        slug = ASSET_SLUG_RE.sub("-", label.casefold()).strip("-")
        if not slug or slug in dialogue_asset_slugs:
            owner = dialogue_asset_slugs.get(slug, "none")
            raise StoryVideoError(
                f"Dialogue identity labels cannot produce unique asset names: "
                f"{owner}, {entity_id}"
            )
        dialogue_asset_slugs[slug] = entity_id
    group_asset_slugs: dict[str, str] = {}
    for role in {
        entity["group_role_type_en"]
        for entity_id, entity in entities.items()
        if entity_id not in speaking_entity_ids
    }:
        slug = ASSET_SLUG_RE.sub("-", role.casefold()).strip("-")
        if not slug or slug in group_asset_slugs:
            owner = group_asset_slugs.get(slug, "none")
            raise StoryVideoError(
                f"Silent group roles cannot produce unique asset names: "
                f"{owner}, {role}"
            )
        group_asset_slugs[slug] = role
    return {
        "status": "PASS",
        "entity_count": len(entities),
        "segment_count": len(raw_segments),
    }


def role_asset_scope_gate(task_dir: Path) -> dict[str, Any]:
    """Return the fast, non-persistent role/image scope that unlocks art work."""

    task_dir = task_dir.expanduser().resolve()
    value = load_character_performance_map(task_dir)
    screenplay = load_screenplay_file(
        task_dir / "screenplay-writer/screenplay.md"
    )
    entities = {
        item["entity_id"]: item for item in value["performance_entities"]
    }
    speaking_ids = {
        call["entity_id"]
        for segment in value["scene_segment_calls"]
        for call in segment["calls"]
        if call["speaks"]
    }
    dialogue_entity_ids = [
        item["entity_id"]
        for item in value["performance_entities"]
        if item["entity_id"] in speaking_ids
    ]
    silent_groups: dict[str, list[str]] = {}
    silent_group_member_types: dict[str, list[str]] = {}
    for item in value["performance_entities"]:
        if item["entity_id"] in speaking_ids:
            continue
        silent_groups.setdefault(item["group_role_type_en"], []).append(
            item["entity_id"]
        )
        silent_group_member_types.setdefault(item["group_role_type_en"], []).extend(
            member_type.strip() for member_type in item["ensemble_member_types_en"]
        )
    segment_scopes: list[dict[str, Any]] = []
    for segment in value["scene_segment_calls"]:
        calls = segment["calls"]
        dialogue_ids = [
            call["entity_id"]
            for call in calls
            if call["entity_id"] in speaking_ids
        ]
        visible_dialogue_ids = [
            call["entity_id"]
            for call in calls
            if call["entity_id"] in speaking_ids
            and call["presence_mode"] == "on_screen"
        ]
        nonvisible_dialogue_ids = [
            call["entity_id"]
            for call in calls
            if call["entity_id"] in speaking_ids
            and call["presence_mode"] != "on_screen"
        ]
        group_roles = list(
            dict.fromkeys(
                call["group_role_type_en"]
                for call in calls
                if call["entity_id"] not in speaking_ids
                and call["presence_mode"] == "on_screen"
            )
        )
        segment_scopes.append(
            {
                "segment_id": segment["segment_id"],
                "scene_id": segment["scene_id"],
                "dialogue_entity_ids": dialogue_ids,
                "visible_dialogue_entity_ids": visible_dialogue_ids,
                "offscreen_or_voiceover_dialogue_entity_ids": nonvisible_dialogue_ids,
                "silent_group_role_types": group_roles,
                "dialogue_turn_count": sum(
                    len(call["line_ids"]) for call in calls
                ),
                "static_reference_image_count": 1
                + len(dialogue_ids)
                + len(group_roles),
            }
        )
    environment_by_scene = {
        scene_id: environment["environment_id"]
        for environment in screenplay["environments"]
        for scene_id in environment["scene_ids_json"]
    }
    return {
        "contract": "role-asset-scope-gate/v1",
        "status": "PASS",
        "image_asset_generation": "UNLOCKED",
        "detailed_screenplay_review": "COMPLETED_IN_WRITER_PREFLIGHT",
        "dialogue_entities": [
            {
                "entity_id": entity_id,
                "character_name_en": entities[entity_id][
                    "screenplay_character_name_en"
                ],
                "entity_kind": entities[entity_id]["entity_kind"],
            }
            for entity_id in dialogue_entity_ids
        ],
        "silent_role_groups": [
            {
                "group_role_type_en": role,
                "entity_ids": entity_ids,
                "member_types_en": silent_group_member_types[role],
            }
            for role, entity_ids in silent_groups.items()
        ],
        "scene_environment_scopes": [
            {
                "scene_id": scene["scene_id"],
                "environment_id": environment_by_scene[scene["scene_id"]],
                "primary_time_en": scene["primary_time_en"],
                "primary_place_en": scene["primary_place_en"],
                "segment_ids": scene["segment_ids_json"],
            }
            for scene in screenplay["scenes"]
        ],
        "segment_scopes": segment_scopes,
        "scope_change_policy": (
            "Detailed review may change dialogue, action, timing, transitions, or "
            "same-Scene Segment boundaries without stopping image work only while "
            "dialogue entity ownership, silent group-role membership, exact ordered "
            "silent member-type composition, Scene environment scope, and story-significant "
            "appearance/prop facts stay fixed."
        ),
    }


def load_character_performance_map(task_dir: Path) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    path = task_dir / "screenplay-writer/screenplay.md"
    screenplay = load_screenplay_file(path)
    entities = {
        item["entity_id"]: item for item in screenplay["characters"]
    }
    scene_segment_calls: list[dict[str, Any]] = []
    for segment in screenplay["segments"]:
        plan = segment["story_plan"]
        calls: list[dict[str, Any]] = []
        for compact in segment["performance_calls"]:
            entity = entities[compact["entity_id"]]
            calls.append(
                {
                    "entity_id": entity["entity_id"],
                    "screenplay_character_name_en": entity[
                        "screenplay_character_name_en"
                    ],
                    "entity_kind": entity["entity_kind"],
                    "presence_mode": compact["presence_mode"],
                    "speaks": compact["speaks"],
                    "line_ids": compact["line_ids"],
                    "state_changing_action": compact["state_changing_action"],
                    "recurring": entity["recurring"],
                    "group_role_type_en": entity["group_role_type_en"],
                    "action_shot_ids": compact["action_block_ids"],
                }
            )
        scene_segment_calls.append(
            {
                "scene_id": plan["scene_id"],
                "segment_id": plan["segment_id"],
                "duration_seconds": plan["estimated_duration_seconds"],
                "screenplay_participants": [
                    call["entity_id"] for call in segment["performance_calls"]
                ],
                "calls": calls,
            }
        )
    value = {
        "contract": "character-performance-map",
        "performance_entities": screenplay["characters"],
        "scene_segment_calls": scene_segment_calls,
    }
    validate_character_performance_map(
        value,
        screenplay_path=path,
    )
    return value
