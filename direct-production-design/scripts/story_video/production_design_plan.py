"""Validate the model-authored production-design plan without completing it."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


PLAN_RELATIVE_PATH = Path("direct-production-design/production-design-plan.json")
ROOT_KEYS = {
    "contract",
    "characters",
    "ensemble_rosters",
    "props",
    "costumes",
    "locations",
}
PROMPT_KEYS = {
    "intent_en",
    "subject_en",
    "background_en",
    "composition_en",
    "continuity",
    "style_en",
    "exclusions_en",
}
PROMPT_CONTINUITY_KEYS = {"reference_asset_ids", "locks_en"}
CHARACTER_KEYS = {
    "type",
    "entity_id",
    "actor_profile",
    "description_en",
    "body_topology",
    "voice_description_en",
    "voice_sample_text_en",
    "voice_speech_rate",
    "voice_generation_prompt",
    "media_path",
    "generation_prompt",
}
ENSEMBLE_KEYS = {
    "type",
    "asset_id",
    "group_role_type_en",
    "description_en",
    "member_type_id",
    "allowed_member_types_en",
    "subject_count",
    "variation_profile",
    "media_path",
    "generation_prompt",
}
VARIATION_PROFILE_KEYS = {"locked_traits_en", "allowed_variation_en"}
ACTOR_PROFILE_KEYS = {
    "name_en",
    "personality_en",
    "screen_presence_en",
    "acting_range_en",
}
BODY_TOPOLOGY_KEYS = {
    "body_plan_en",
    "total_limb_count",
    "limb_sets",
    "non_limb_appendages",
    "topology_lock_en",
}
LIMB_SET_KEYS = {"kind_en", "count", "function_en"}
NON_LIMB_APPENDAGE_KEYS = {"kind_en", "count"}
PROP_KEYS = {
    "type",
    "asset_id",
    "description_en",
    "media_path",
    "generation_prompt",
}
COSTUME_KEYS = {
    "type",
    "asset_id",
    "character_id",
    "description_en",
    "appearance_state_en",
    "media_path",
    "generation_prompt",
}
LOCATION_KEYS = {
    "type",
    "location_id",
    "scene_ids",
    "description_en",
    "included_prop_ids",
    "embedded_npc_asset_ids",
    "independent_performer_asset_ids",
    "fixed_set_elements_en",
    "environment_state_en",
    "lighting_state_en",
    "palette_materials_en",
    "topology",
    "landmarks",
    "media_path",
    "generation_prompt",
}
VOICE_PROMPT_KEYS = {
    "text_en",
    "voice_direction_en",
    "delivery_en",
    "exclusions_en",
}
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
STORY_BOUND_ACTOR_PROFILE_RE = re.compile(
    r"\b(?:screenplay|segment|current story|story objective|narrative function|"
    r"plot event|scene-specific)\b",
    re.IGNORECASE,
)
STORY_BOUND_CHARACTER_PROMPT_RE = re.compile(
    r"\b(?:screenplay|segment|current story|plot event|narrative function|"
    r"first dialogue|line delivery|victory|defeat|injury state)\b",
    re.IGNORECASE,
)
PROMPT_PATCH_LANGUAGE_RE = re.compile(
    r"\b(?:append(?:ed)?|supplemental|emergency correction|ignore previous|"
    r"override previous|despite previous|additional negative block)\b",
    re.IGNORECASE,
)
MAX_GENERATION_PROMPT_CHARS = 3500
MAX_VOICE_PROMPT_CHARS = 2000
PURE_WHITE_BACKGROUND_EN = (
    "Seamless pure-white (#FFFFFF) studio backdrop; no environment, horizon, "
    "floor line, texture, gradient, tint, or background cast shadow."
)
STYLE_AUTHORITY_EN = (
    "Original Soft & Cute 3D Healing Animation; rounded child-safe forms, tactile "
    "matte materials, warm low-saturation color, soft diffused light, and no brand "
    "or IP imitation."
)


class ProductionDesignPlanError(ValueError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProductionDesignPlanError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        raise ProductionDesignPlanError(
            f"{label} must use exact keys; missing={missing}, unknown={unknown}"
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionDesignPlanError(f"{label} must be non-empty text")
    return value.strip()


def _text_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ProductionDesignPlanError(f"{label} must be a text array")
    result = [_text(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len({item.casefold() for item in result}) != len(result):
        raise ProductionDesignPlanError(f"{label} must not repeat values")
    return result


def _asset_ids(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    result = _text_list(value, label, allow_empty=allow_empty)
    invalid = [item for item in result if not ASSET_ID_RE.fullmatch(item)]
    if invalid:
        raise ProductionDesignPlanError(f"{label} has invalid IDs {invalid}")
    return result


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProductionDesignPlanError(f"{label} must be a positive integer")
    return value


def _media_path(value: Any, label: str) -> str:
    raw = _text(value, label)
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "assets"
        or path.suffix.casefold() != ".png"
    ):
        raise ProductionDesignPlanError(
            f"{label} must be a repository-relative PNG path under assets/"
        )
    return path.as_posix()


def _actor_profile(value: Any, label: str) -> dict[str, str]:
    profile = _exact(value, ACTOR_PROFILE_KEYS, label)
    result: dict[str, str] = {}
    for key in sorted(ACTOR_PROFILE_KEYS):
        text = _text(profile[key], f"{label}.{key}")
        if STORY_BOUND_ACTOR_PROFILE_RE.search(text):
            raise ProductionDesignPlanError(
                f"{label}.{key} must describe a reusable actor, not one story"
            )
        result[key] = text
    return result


def _body_topology(value: Any, label: str) -> dict[str, Any]:
    topology = _exact(value, BODY_TOPOLOGY_KEYS, label)
    raw_limb_sets = topology["limb_sets"]
    if not isinstance(raw_limb_sets, list) or not raw_limb_sets:
        raise ProductionDesignPlanError(f"{label}.limb_sets must be non-empty")
    limb_sets: list[dict[str, Any]] = []
    seen_limb_kinds: set[str] = set()
    for index, raw in enumerate(raw_limb_sets):
        item = _exact(raw, LIMB_SET_KEYS, f"{label}.limb_sets[{index}]")
        kind = _text(item["kind_en"], f"{label}.limb_sets[{index}].kind_en")
        if kind.casefold() in seen_limb_kinds:
            raise ProductionDesignPlanError(f"{label}.limb_sets repeats {kind!r}")
        seen_limb_kinds.add(kind.casefold())
        limb_sets.append(
            {
                "kind_en": kind,
                "count": _positive_int(
                    item["count"], f"{label}.limb_sets[{index}].count"
                ),
                "function_en": _text(
                    item["function_en"], f"{label}.limb_sets[{index}].function_en"
                ),
            }
        )
    total = _positive_int(topology["total_limb_count"], f"{label}.total_limb_count")
    if total != sum(item["count"] for item in limb_sets):
        raise ProductionDesignPlanError(
            f"{label}.total_limb_count must equal the limb-set sum"
        )
    raw_appendages = topology["non_limb_appendages"]
    if not isinstance(raw_appendages, list):
        raise ProductionDesignPlanError(
            f"{label}.non_limb_appendages must be an array"
        )
    appendages: list[dict[str, Any]] = []
    seen_appendages: set[str] = set()
    for index, raw in enumerate(raw_appendages):
        item = _exact(
            raw,
            NON_LIMB_APPENDAGE_KEYS,
            f"{label}.non_limb_appendages[{index}]",
        )
        kind = _text(
            item["kind_en"], f"{label}.non_limb_appendages[{index}].kind_en"
        )
        if kind.casefold() in seen_appendages:
            raise ProductionDesignPlanError(
                f"{label}.non_limb_appendages repeats {kind!r}"
            )
        seen_appendages.add(kind.casefold())
        appendages.append(
            {
                "kind_en": kind,
                "count": _positive_int(
                    item["count"], f"{label}.non_limb_appendages[{index}].count"
                ),
            }
        )
    return {
        "body_plan_en": _text(topology["body_plan_en"], f"{label}.body_plan_en"),
        "total_limb_count": total,
        "limb_sets": limb_sets,
        "non_limb_appendages": appendages,
        "topology_lock_en": _text(
            topology["topology_lock_en"], f"{label}.topology_lock_en"
        ),
    }


def _generation_prompt(
    value: Any, *, label: str, asset_type: str
) -> dict[str, Any]:
    prompt = _exact(value, PROMPT_KEYS, label)
    continuity = _exact(
        prompt["continuity"], PROMPT_CONTINUITY_KEYS, f"{label}.continuity"
    )
    result = {
        "intent_en": _text(prompt["intent_en"], f"{label}.intent_en"),
        "subject_en": _text(prompt["subject_en"], f"{label}.subject_en"),
        "background_en": _text(prompt["background_en"], f"{label}.background_en"),
        "composition_en": _text(
            prompt["composition_en"], f"{label}.composition_en"
        ),
        "continuity": {
            "reference_asset_ids": _asset_ids(
                continuity["reference_asset_ids"],
                f"{label}.continuity.reference_asset_ids",
            ),
            "locks_en": _text_list(
                continuity["locks_en"], f"{label}.continuity.locks_en"
            ),
        },
        "style_en": _text(prompt["style_en"], f"{label}.style_en"),
        "exclusions_en": _text_list(
            prompt["exclusions_en"], f"{label}.exclusions_en"
        ),
    }
    if result["style_en"] != STYLE_AUTHORITY_EN:
        raise ProductionDesignPlanError(
            f"{label}.style_en must exactly equal the single visual-style authority"
        )
    if asset_type == "location_master":
        if result["background_en"] == PURE_WHITE_BACKGROUND_EN:
            raise ProductionDesignPlanError(
                f"{label}.background_en must describe the actual location"
            )
    elif result["background_en"] != PURE_WHITE_BACKGROUND_EN:
        raise ProductionDesignPlanError(
            f"{label}.background_en must exactly equal the pure-white asset backdrop"
        )
    if asset_type == "character" and STORY_BOUND_CHARACTER_PROMPT_RE.search(
        json.dumps(result, ensure_ascii=False)
    ):
        raise ProductionDesignPlanError(
            f"{label} must present a reusable actor, not a story performance state"
        )
    serialized = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > MAX_GENERATION_PROMPT_CHARS:
        raise ProductionDesignPlanError(
            f"{label} exceeds the {MAX_GENERATION_PROMPT_CHARS}-character limit"
        )
    if PROMPT_PATCH_LANGUAGE_RE.search(serialized):
        raise ProductionDesignPlanError(
            f"{label} contains patch/override language instead of one coherent Prompt"
        )
    return result


def _fixed_set_elements(
    value: Any,
    *,
    label: str,
    topology: Any,
    prompt: dict[str, Any],
) -> list[str]:
    """Validate authored fixed-set authority without inventing prompt prose."""

    elements = _text_list(value, label, allow_empty=True)
    if not isinstance(topology, dict):
        raise ProductionDesignPlanError(f"{label} requires an authored topology")
    obstacles = topology.get("fixed_obstacles")
    placements = topology.get("fixed_prop_placements")
    if not isinstance(obstacles, list) or not isinstance(placements, list):
        raise ProductionDesignPlanError(
            f"{label} requires topology.fixed_obstacles and "
            "topology.fixed_prop_placements arrays"
        )
    if (obstacles or placements) and not elements:
        raise ProductionDesignPlanError(
            f"{label} must name every necessary fixed furniture, set piece, and "
            "installed prop visible in the location master"
        )
    locks = prompt["continuity"]["locks_en"]
    missing_locks = [element for element in elements if element not in locks]
    if missing_locks:
        raise ProductionDesignPlanError(
            f"{label} entries must appear verbatim in generation_prompt.continuity."
            f"locks_en; missing={missing_locks}"
        )
    return elements


def _voice_generation_prompt(
    value: Any,
    *,
    label: str,
    sample_text_en: str,
    voice_description_en: str,
) -> dict[str, Any]:
    prompt = _exact(value, VOICE_PROMPT_KEYS, label)
    result = {
        "text_en": _text(prompt["text_en"], f"{label}.text_en"),
        "voice_direction_en": _text(
            prompt["voice_direction_en"], f"{label}.voice_direction_en"
        ),
        "delivery_en": _text(prompt["delivery_en"], f"{label}.delivery_en"),
        "exclusions_en": _text_list(
            prompt["exclusions_en"], f"{label}.exclusions_en"
        ),
    }
    if result["text_en"] != sample_text_en:
        raise ProductionDesignPlanError(
            f"{label}.text_en must exactly equal voice_sample_text_en"
        )
    if result["voice_direction_en"] != voice_description_en:
        raise ProductionDesignPlanError(
            f"{label}.voice_direction_en must exactly equal voice_description_en"
        )
    serialized = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > MAX_VOICE_PROMPT_CHARS:
        raise ProductionDesignPlanError(
            f"{label} exceeds the {MAX_VOICE_PROMPT_CHARS}-character limit"
        )
    if PROMPT_PATCH_LANGUAGE_RE.search(serialized):
        raise ProductionDesignPlanError(
            f"{label} contains patch/override language instead of one coherent Prompt"
        )
    return result


def render_generation_prompt(prompt: dict[str, Any]) -> str:
    """Serialize the validated model prompt verbatim; add no prose or constraints."""

    return json.dumps(prompt, ensure_ascii=False, indent=2)


def validate_generation_prompt_text(text: str, *, asset_type: str) -> str:
    """Accept only one canonical JSON prompt object, with no prefix or suffix."""

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProductionDesignPlanError(
            "Generation prompt must be one structured JSON object"
        ) from exc
    prompt = _generation_prompt(
        raw, label="generation prompt", asset_type=asset_type
    )
    canonical = render_generation_prompt(prompt)
    if text.strip() != canonical:
        raise ProductionDesignPlanError(
            "Generation prompt must use canonical JSON formatting with no appended prose"
        )
    return canonical


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductionDesignPlanError(f"{label} must be an array")
    return value


def load_production_design_plan(
    task_root: Path,
    *,
    performance: dict[str, Any],
    screenplay: dict[str, Any],
) -> dict[str, Any]:
    """Reject missing or contradictory model fields; never infer replacements."""

    path = task_root / PLAN_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionDesignPlanError(
            f"Missing or invalid current production-design plan: {path}"
        ) from exc
    plan = _exact(payload, ROOT_KEYS, "production-design plan")
    if plan["contract"] != "production-design-plan":
        raise ProductionDesignPlanError(
            "production-design plan contract must be production-design-plan"
        )

    speaking_ids = {
        call["entity_id"]
        for segment in performance["scene_segment_calls"]
        for call in segment["calls"]
        if call["speaks"]
    }
    entities = performance["performance_entities"]
    silent_by_role: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        if entity["entity_id"] in speaking_ids:
            continue
        role_type = _text(
            entity.get("group_role_type_en"),
            f"performance entity {entity['entity_id']}.group_role_type_en",
        )
        if role_type == "none":
            raise ProductionDesignPlanError(
                f"Silent entity {entity['entity_id']} lacks a group role type"
            )
        if role_type not in silent_by_role:
            silent_by_role[role_type] = []
        silent_by_role[role_type].append(entity)

    characters: list[dict[str, Any]] = []
    character_ids: set[str] = set()
    for index, raw in enumerate(_list(plan["characters"], "characters")):
        item = _exact(raw, CHARACTER_KEYS, f"characters[{index}]")
        entity_id = _text(item["entity_id"], f"characters[{index}].entity_id")
        if entity_id in character_ids:
            raise ProductionDesignPlanError(f"characters repeats {entity_id}")
        character_ids.add(entity_id)
        speech_rate = item["voice_speech_rate"]
        if (
            isinstance(speech_rate, bool)
            or not isinstance(speech_rate, int)
            or not -50 <= speech_rate <= 100
        ):
            raise ProductionDesignPlanError(
                f"character {entity_id}.voice_speech_rate must be -50..100"
            )
        if item["type"] != "character":
            raise ProductionDesignPlanError(
                f"character {entity_id}.type must be character"
            )
        voice_description = _text(
            item["voice_description_en"],
            f"character {entity_id}.voice_description_en",
        )
        voice_sample_text = _text(
            item["voice_sample_text_en"],
            f"character {entity_id}.voice_sample_text_en",
        )
        characters.append(
            {
                "type": "character",
                "entity_id": entity_id,
                "actor_profile": _actor_profile(
                    item["actor_profile"], f"character {entity_id}.actor_profile"
                ),
                "description_en": _text(
                    item["description_en"], f"character {entity_id}.description_en"
                ),
                "body_topology": _body_topology(
                    item["body_topology"], f"character {entity_id}.body_topology"
                ),
                "voice_description_en": voice_description,
                "voice_sample_text_en": voice_sample_text,
                "voice_speech_rate": speech_rate,
                "voice_generation_prompt": _voice_generation_prompt(
                    item["voice_generation_prompt"],
                    label=f"character {entity_id}.voice_generation_prompt",
                    sample_text_en=voice_sample_text,
                    voice_description_en=voice_description,
                ),
                "media_path": _media_path(
                    item["media_path"], f"character {entity_id}.media_path"
                ),
                "generation_prompt": _generation_prompt(
                    item["generation_prompt"],
                    label=f"character {entity_id}.generation_prompt",
                    asset_type="character",
                ),
            }
        )
    if character_ids != speaking_ids:
        raise ProductionDesignPlanError(
            "characters must exactly cover speaking entities; "
            f"expected={sorted(speaking_ids)}, actual={sorted(character_ids)}"
        )

    ensembles: list[dict[str, Any]] = []
    ensemble_ids: set[str] = set()
    ensemble_by_role: dict[str, str] = {}
    for index, raw in enumerate(
        _list(plan["ensemble_rosters"], "ensemble_rosters")
    ):
        item = _exact(raw, ENSEMBLE_KEYS, f"ensemble_rosters[{index}]")
        asset_id = _text(item["asset_id"], f"ensemble_rosters[{index}].asset_id")
        role_type = _text(
            item["group_role_type_en"],
            f"ensemble_roster {asset_id}.group_role_type_en",
        )
        if (
            not ASSET_ID_RE.fullmatch(asset_id)
            or asset_id in ensemble_ids
            or role_type in ensemble_by_role
        ):
            raise ProductionDesignPlanError(
                f"Invalid/repeated ensemble ID or role: {asset_id}/{role_type}"
            )
        ensemble_ids.add(asset_id)
        if item["type"] != "ensemble_roster":
            raise ProductionDesignPlanError(
                f"ensemble_roster {asset_id}.type must be ensemble_roster"
            )
        ensemble_by_role[role_type] = asset_id
        allowed = _text_list(
            item["allowed_member_types_en"],
            f"ensemble_roster {asset_id}.allowed_member_types_en",
        )
        if role_type not in silent_by_role:
            raise ProductionDesignPlanError(
                f"ensemble_roster {asset_id} names an unknown silent role type"
            )
        authored_allowed = [
            member
            for entity in silent_by_role[role_type]
            for member in entity["ensemble_member_types_en"]
        ]
        if allowed != authored_allowed:
            raise ProductionDesignPlanError(
                f"ensemble_roster {asset_id} member types differ from writer authority; "
                f"expected={authored_allowed}, actual={allowed}"
            )
        variation = _exact(
            item["variation_profile"],
            VARIATION_PROFILE_KEYS,
            f"ensemble_roster {asset_id}.variation_profile",
        )
        ensembles.append(
            {
                "type": "ensemble_roster",
                "asset_id": asset_id,
                "group_role_type_en": role_type,
                "description_en": _text(
                    item["description_en"],
                    f"ensemble_roster {asset_id}.description_en",
                ),
                "member_type_id": _text(
                    item["member_type_id"],
                    f"ensemble_roster {asset_id}.member_type_id",
                ),
                "allowed_member_types_en": allowed,
                "subject_count": _positive_int(
                    item["subject_count"],
                    f"ensemble_roster {asset_id}.subject_count",
                ),
                "variation_profile": {
                    "locked_traits_en": _text(
                        variation["locked_traits_en"],
                        f"ensemble_roster {asset_id}.variation_profile.locked_traits_en",
                    ),
                    "allowed_variation_en": _text(
                        variation["allowed_variation_en"],
                        f"ensemble_roster {asset_id}.variation_profile.allowed_variation_en",
                    ),
                },
                "media_path": _media_path(
                    item["media_path"], f"ensemble_roster {asset_id}.media_path"
                ),
                "generation_prompt": _generation_prompt(
                    item["generation_prompt"],
                    label=f"ensemble_roster {asset_id}.generation_prompt",
                    asset_type="ensemble_roster",
                ),
            }
        )
    if set(ensemble_by_role) != set(silent_by_role):
        raise ProductionDesignPlanError(
            "ensemble_rosters must exactly cover silent role types; "
            f"expected={sorted(silent_by_role)}, actual={sorted(ensemble_by_role)}"
        )

    props: list[dict[str, Any]] = []
    prop_ids: set[str] = set()
    for index, raw in enumerate(_list(plan["props"], "props")):
        item = _exact(raw, PROP_KEYS, f"props[{index}]")
        asset_id = _text(item["asset_id"], f"props[{index}].asset_id")
        if not ASSET_ID_RE.fullmatch(asset_id) or asset_id in prop_ids:
            raise ProductionDesignPlanError(f"Invalid/repeated prop ID {asset_id}")
        prop_ids.add(asset_id)
        if item["type"] != "prop":
            raise ProductionDesignPlanError(f"prop {asset_id}.type must be prop")
        props.append(
            {
                "type": "prop",
                "asset_id": asset_id,
                "description_en": _text(
                    item["description_en"], f"prop {asset_id}.description_en"
                ),
                "media_path": _media_path(
                    item["media_path"], f"prop {asset_id}.media_path"
                ),
                "generation_prompt": _generation_prompt(
                    item["generation_prompt"],
                    label=f"prop {asset_id}.generation_prompt",
                    asset_type="prop",
                ),
            }
        )

    costumes: list[dict[str, Any]] = []
    costume_ids: set[str] = set()
    for index, raw in enumerate(_list(plan["costumes"], "costumes")):
        item = _exact(raw, COSTUME_KEYS, f"costumes[{index}]")
        asset_id = _text(item["asset_id"], f"costumes[{index}].asset_id")
        character_id = _text(
            item["character_id"], f"costume {asset_id}.character_id"
        )
        if (
            not ASSET_ID_RE.fullmatch(asset_id)
            or asset_id in costume_ids
            or character_id not in character_ids
        ):
            raise ProductionDesignPlanError(
                f"Invalid/repeated costume or owner for {asset_id}"
            )
        costume_ids.add(asset_id)
        if item["type"] != "costume":
            raise ProductionDesignPlanError(
                f"costume {asset_id}.type must be costume"
            )
        costumes.append(
            {
                "type": "costume",
                "asset_id": asset_id,
                "character_id": character_id,
                "description_en": _text(
                    item["description_en"], f"costume {asset_id}.description_en"
                ),
                "appearance_state_en": _text(
                    item["appearance_state_en"],
                    f"costume {asset_id}.appearance_state_en",
                ),
                "media_path": _media_path(
                    item["media_path"], f"costume {asset_id}.media_path"
                ),
                "generation_prompt": _generation_prompt(
                    item["generation_prompt"],
                    label=f"costume {asset_id}.generation_prompt",
                    asset_type="costume",
                ),
            }
        )

    role_asset_by_entity = {
        entity["entity_id"]: (
            entity["entity_id"]
            if entity["entity_id"] in speaking_ids
            else ensemble_by_role[entity["group_role_type_en"]]
        )
        for entity in entities
    }
    on_screen_by_scene: dict[str, set[str]] = {}
    state_changing_by_scene: dict[str, set[str]] = {}
    for segment in performance["scene_segment_calls"]:
        scene_id = segment["scene_id"]
        if scene_id not in on_screen_by_scene:
            on_screen_by_scene[scene_id] = set()
            state_changing_by_scene[scene_id] = set()
        on_screen_by_scene[scene_id].update(
            call["entity_id"]
            for call in segment["calls"]
            if call.get("presence_mode") == "on_screen"
        )
        state_changing_by_scene[scene_id].update(
            role_asset_by_entity[call["entity_id"]]
            for call in segment["calls"]
            if call.get("presence_mode") == "on_screen"
            and call.get("state_changing_action") is True
        )
    entity_order = [entity["entity_id"] for entity in entities]

    locations: list[dict[str, Any]] = []
    location_ids: set[str] = set()
    covered_scene_ids: list[str] = []
    for index, raw in enumerate(_list(plan["locations"], "locations")):
        item = _exact(raw, LOCATION_KEYS, f"locations[{index}]")
        location_id = _text(item["location_id"], f"locations[{index}].location_id")
        if not ASSET_ID_RE.fullmatch(location_id) or location_id in location_ids:
            raise ProductionDesignPlanError(
                f"Invalid/repeated location ID {location_id}"
            )
        location_ids.add(location_id)
        if item["type"] != "location_master":
            raise ProductionDesignPlanError(
                f"location {location_id}.type must be location_master"
            )
        scene_ids = _asset_ids(
            item["scene_ids"], f"location {location_id}.scene_ids", allow_empty=False
        )
        covered_scene_ids.extend(scene_ids)
        included_props = _asset_ids(
            item["included_prop_ids"], f"location {location_id}.included_prop_ids"
        )
        if not set(included_props).issubset(prop_ids):
            raise ProductionDesignPlanError(
                f"location {location_id} contains unknown included_prop_ids"
            )
        expected_role_lists: list[list[str]] = []
        for scene_id in scene_ids:
            if scene_id not in on_screen_by_scene:
                raise ProductionDesignPlanError(
                    f"location {location_id} names Scene {scene_id} without calls"
                )
            current = on_screen_by_scene[scene_id]
            expected_role_lists.append(
                list(
                    dict.fromkeys(
                        role_asset_by_entity[entity_id]
                        for entity_id in entity_order
                        if entity_id in current
                    )
                )
            )
        expected_role_union = list(
            dict.fromkeys(
                role_asset_id
                for roles in expected_role_lists
                for role_asset_id in roles
            )
        )
        embedded_npcs = _asset_ids(
            item["embedded_npc_asset_ids"],
            f"location {location_id}.embedded_npc_asset_ids",
        )
        independent_performers = _asset_ids(
            item["independent_performer_asset_ids"],
            f"location {location_id}.independent_performer_asset_ids",
        )
        overlap = set(embedded_npcs).intersection(independent_performers)
        if overlap:
            raise ProductionDesignPlanError(
                f"location {location_id} role treatments overlap: {sorted(overlap)}"
            )
        expected_embedded_order = [
            role_asset_id
            for role_asset_id in expected_role_union
            if role_asset_id in set(embedded_npcs)
        ]
        expected_independent_order = [
            role_asset_id
            for role_asset_id in expected_role_union
            if role_asset_id not in set(embedded_npcs)
        ]
        if embedded_npcs != expected_embedded_order:
            raise ProductionDesignPlanError(
                f"location {location_id}.embedded_npc_asset_ids must be an ordered "
                f"subset of writer-owned on-screen roles; expected order="
                f"{expected_embedded_order}, actual={embedded_npcs}"
            )
        if independent_performers != expected_independent_order:
            raise ProductionDesignPlanError(
                f"location {location_id} role treatments must exactly cover writer "
                f"on-screen authority; expected independent performers="
                f"{expected_independent_order}, actual={independent_performers}"
            )
        unstable_embedded = [
            role_asset_id
            for role_asset_id in embedded_npcs
            if any(role_asset_id not in roles for roles in expected_role_lists)
        ]
        if unstable_embedded:
            raise ProductionDesignPlanError(
                f"location {location_id} embeds NPCs absent from one or more bound "
                f"Scenes: {unstable_embedded}; split the Location master or keep the "
                "role independent"
            )
        speaking_embedded = [
            role_asset_id
            for role_asset_id in embedded_npcs
            if role_asset_id in speaking_ids
        ]
        if speaking_embedded:
            raise ProductionDesignPlanError(
                f"location {location_id} embeds dialogue performers "
                f"{speaking_embedded}; every speaking role must remain independent"
            )
        active_embedded = [
            role_asset_id
            for role_asset_id in embedded_npcs
            if any(
                role_asset_id in state_changing_by_scene[scene_id]
                for scene_id in scene_ids
            )
        ]
        if active_embedded:
            raise ProductionDesignPlanError(
                f"location {location_id} embeds state-changing performers "
                f"{active_embedded}; story-active roles must remain independent"
            )
        topology = item["topology"]
        landmarks = item["landmarks"]
        if not isinstance(topology, dict) or not topology:
            raise ProductionDesignPlanError(
                f"location {location_id}.topology must be a non-empty object"
            )
        if not isinstance(landmarks, list) or not landmarks:
            raise ProductionDesignPlanError(
                f"location {location_id}.landmarks must be a non-empty array"
            )
        generation_prompt = _generation_prompt(
            item["generation_prompt"],
            label=f"location {location_id}.generation_prompt",
            asset_type="location_master",
        )
        fixed_set_elements = _fixed_set_elements(
            item["fixed_set_elements_en"],
            label=f"location {location_id}.fixed_set_elements_en",
            topology=topology,
            prompt=generation_prompt,
        )
        locations.append(
            {
                "type": "location_master",
                "location_id": location_id,
                "scene_ids": scene_ids,
                "description_en": _text(
                    item["description_en"], f"location {location_id}.description_en"
                ),
                "included_prop_ids": included_props,
                "embedded_npc_asset_ids": embedded_npcs,
                "independent_performer_asset_ids": independent_performers,
                "fixed_set_elements_en": fixed_set_elements,
                "environment_state_en": _text(
                    item["environment_state_en"],
                    f"location {location_id}.environment_state_en",
                ),
                "lighting_state_en": _text(
                    item["lighting_state_en"],
                    f"location {location_id}.lighting_state_en",
                ),
                "palette_materials_en": _text(
                    item["palette_materials_en"],
                    f"location {location_id}.palette_materials_en",
                ),
                "topology": topology,
                "landmarks": landmarks,
                "media_path": _media_path(
                    item["media_path"], f"location {location_id}.media_path"
                ),
                "generation_prompt": generation_prompt,
            }
        )
    expected_scene_ids = [scene["scene_id"] for scene in screenplay["scenes"]]
    if (
        len(covered_scene_ids) != len(set(covered_scene_ids))
        or set(covered_scene_ids) != set(expected_scene_ids)
    ):
        raise ProductionDesignPlanError(
            "locations must partition every screenplay Scene exactly once; "
            f"expected={expected_scene_ids}, actual={covered_scene_ids}"
        )

    all_assets = [*characters, *ensembles, *props, *costumes, *locations]
    ids = [
        asset.get("entity_id") or asset.get("asset_id") or asset.get("location_id")
        for asset in all_assets
    ]
    if len(ids) != len(set(ids)):
        raise ProductionDesignPlanError("production-design plan repeats an asset ID")
    paths = [asset["media_path"] for asset in all_assets]
    if len(paths) != len(set(paths)):
        raise ProductionDesignPlanError("production-design plan repeats a media_path")
    known_ids = set(ids)
    for asset in all_assets:
        asset_id = asset.get("entity_id") or asset.get("asset_id") or asset.get(
            "location_id"
        )
        references = asset["generation_prompt"]["continuity"][
            "reference_asset_ids"
        ]
        if not set(references).issubset(known_ids):
            raise ProductionDesignPlanError(
                f"asset {asset_id} references unknown assets {sorted(set(references)-known_ids)}"
            )
        if asset in props or asset in ensembles:
            expected_references: list[str] = []
        elif asset in costumes:
            expected_references = [asset["character_id"]]
        elif asset in locations:
            expected_references = [
                *asset["included_prop_ids"],
                *asset["embedded_npc_asset_ids"],
            ]
        else:
            expected_references = [
                reference for reference in references if reference in prop_ids
            ]
            if references != expected_references:
                raise ProductionDesignPlanError(
                    f"character {asset_id} may reference only independent props"
                )
        if references != expected_references:
            raise ProductionDesignPlanError(
                f"asset {asset_id} reference order must be fully model-authored and "
                f"consistent; expected={expected_references}, actual={references}"
            )

    return {
        "contract": "production-design-plan",
        "characters": characters,
        "ensemble_rosters": ensembles,
        "props": props,
        "costumes": costumes,
        "locations": locations,
    }
