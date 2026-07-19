"""Load the task-authored, story-specific production-design generation plan."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


PLAN_RELATIVE_PATH = Path("direct-production-design/production-design-plan.json")
ROOT_KEYS = {"contract", "characters", "props", "costumes", "locations"}
CHARACTER_KEYS = {
    "entity_id",
    "design_description_en",
    "body_topology",
    "portrait_prop_ids",
    "voice_description_en",
    "voice_sample_text_en",
    "voice_speech_rate",
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
PROP_KEYS = {"asset_id", "description_en"}
COSTUME_KEYS = {"asset_id", "character_id", "description_en"}
LOCATION_KEYS = {
    "location_id",
    "scene_ids",
    "description_en",
    "generation_prompt_en",
    "fixed_prop_ids",
    "environment_state_en",
    "lighting_state_en",
    "palette_materials_en",
    "topology",
    "landmarks",
}
ASSET_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProductionDesignPlanError(ValueError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProductionDesignPlanError(
            f"{label} must use exact keys: {sorted(keys)}"
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionDesignPlanError(f"{label} must be non-empty text")
    return value.strip()


def _unique_ids(values: Any, label: str, *, prefix: str | None = None) -> list[str]:
    if not isinstance(values, list):
        raise ProductionDesignPlanError(f"{label} must be an array")
    result: list[str] = []
    for index, raw in enumerate(values, start=1):
        value = _text(raw, f"{label}[{index}]")
        if not ASSET_ID_RE.fullmatch(value) or (prefix and not value.startswith(prefix)):
            raise ProductionDesignPlanError(f"{label} contains invalid ID {value!r}")
        if value in result:
            raise ProductionDesignPlanError(f"{label} repeats {value!r}")
        result.append(value)
    return result


def _positive_count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProductionDesignPlanError(f"{label} must be a positive integer")
    return value


def _body_topology(value: Any, label: str) -> dict[str, Any]:
    """Validate one model-authored body plan without species/name branching."""

    topology = _exact(value, BODY_TOPOLOGY_KEYS, label)
    raw_limb_sets = topology["limb_sets"]
    if not isinstance(raw_limb_sets, list) or not raw_limb_sets:
        raise ProductionDesignPlanError(f"{label}.limb_sets must be a non-empty array")
    limb_sets: list[dict[str, Any]] = []
    limb_kinds: set[str] = set()
    for index, raw in enumerate(raw_limb_sets, start=1):
        item = _exact(raw, LIMB_SET_KEYS, f"{label}.limb_sets[{index}]")
        kind = _text(item["kind_en"], f"{label}.limb_sets[{index}].kind_en")
        if kind.casefold() in limb_kinds:
            raise ProductionDesignPlanError(f"{label}.limb_sets repeats {kind!r}")
        limb_kinds.add(kind.casefold())
        limb_sets.append(
            {
                "kind_en": kind,
                "count": _positive_count(
                    item["count"], f"{label}.limb_sets[{index}].count"
                ),
                "function_en": _text(
                    item["function_en"],
                    f"{label}.limb_sets[{index}].function_en",
                ),
            }
        )
    total_limb_count = _positive_count(
        topology["total_limb_count"], f"{label}.total_limb_count"
    )
    if total_limb_count != sum(item["count"] for item in limb_sets):
        raise ProductionDesignPlanError(
            f"{label}.total_limb_count must equal the sum of limb_sets counts"
        )

    raw_appendages = topology["non_limb_appendages"]
    if not isinstance(raw_appendages, list):
        raise ProductionDesignPlanError(f"{label}.non_limb_appendages must be an array")
    appendages: list[dict[str, Any]] = []
    appendage_kinds: set[str] = set()
    for index, raw in enumerate(raw_appendages, start=1):
        item = _exact(
            raw,
            NON_LIMB_APPENDAGE_KEYS,
            f"{label}.non_limb_appendages[{index}]",
        )
        kind = _text(
            item["kind_en"], f"{label}.non_limb_appendages[{index}].kind_en"
        )
        if kind.casefold() in appendage_kinds:
            raise ProductionDesignPlanError(
                f"{label}.non_limb_appendages repeats {kind!r}"
            )
        appendage_kinds.add(kind.casefold())
        appendages.append(
            {
                "kind_en": kind,
                "count": _positive_count(
                    item["count"],
                    f"{label}.non_limb_appendages[{index}].count",
                ),
            }
        )
    return {
        "body_plan_en": _text(topology["body_plan_en"], f"{label}.body_plan_en"),
        "total_limb_count": total_limb_count,
        "limb_sets": limb_sets,
        "non_limb_appendages": appendages,
        "topology_lock_en": _text(
            topology["topology_lock_en"], f"{label}.topology_lock_en"
        ),
    }


def load_production_design_plan(
    task_root: Path,
    *,
    performance: dict[str, Any],
    screenplay: dict[str, Any],
) -> dict[str, Any]:
    """Validate a model-authored plan against current writer-owned authority."""

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
    raw_characters = plan["characters"]
    if not isinstance(raw_characters, list):
        raise ProductionDesignPlanError("characters must be an array")
    characters: list[dict[str, Any]] = []
    seen_character_ids: set[str] = set()
    for index, raw in enumerate(raw_characters, start=1):
        item = _exact(raw, CHARACTER_KEYS, f"character plan {index}")
        entity_id = _text(item["entity_id"], f"character plan {index}.entity_id")
        if entity_id in seen_character_ids:
            raise ProductionDesignPlanError(f"characters repeats {entity_id}")
        seen_character_ids.add(entity_id)
        characters.append(
            {
                "entity_id": entity_id,
                "design_description_en": _text(
                    item["design_description_en"],
                    f"character plan {entity_id}.design_description_en",
                ),
                "body_topology": _body_topology(
                    item["body_topology"],
                    f"character plan {entity_id}.body_topology",
                ),
                "portrait_prop_ids": _unique_ids(
                    item["portrait_prop_ids"],
                    f"character plan {entity_id}.portrait_prop_ids",
                    prefix="prop-",
                ),
                "voice_description_en": _text(
                    item["voice_description_en"],
                    f"character plan {entity_id}.voice_description_en",
                ),
                "voice_sample_text_en": _text(
                    item["voice_sample_text_en"],
                    f"character plan {entity_id}.voice_sample_text_en",
                ),
                "voice_speech_rate": item["voice_speech_rate"],
            }
        )
        if (
            isinstance(item["voice_speech_rate"], bool)
            or not isinstance(item["voice_speech_rate"], int)
            or not -50 <= item["voice_speech_rate"] <= 100
        ):
            raise ProductionDesignPlanError(
                f"character plan {entity_id}.voice_speech_rate must be an integer "
                "from -50 through 100"
            )
    if seen_character_ids != speaking_ids:
        raise ProductionDesignPlanError(
            "character plans must exactly cover dialogue portrait entities; "
            f"expected={sorted(speaking_ids)}, actual={sorted(seen_character_ids)}"
        )

    raw_props = plan["props"]
    if not isinstance(raw_props, list):
        raise ProductionDesignPlanError("props must be an array")
    props: list[dict[str, str]] = []
    prop_ids: set[str] = set()
    for index, raw in enumerate(raw_props, start=1):
        item = _exact(raw, PROP_KEYS, f"prop plan {index}")
        asset_id = _text(item["asset_id"], f"prop plan {index}.asset_id")
        if (
            not ASSET_ID_RE.fullmatch(asset_id)
            or not asset_id.startswith("prop-")
            or asset_id in prop_ids
        ):
            raise ProductionDesignPlanError(f"Invalid or repeated prop ID {asset_id}")
        prop_ids.add(asset_id)
        props.append(
            {
                "asset_id": asset_id,
                "description_en": _text(
                    item["description_en"], f"prop plan {asset_id}.description_en"
                ),
            }
        )
    for character in characters:
        unknown = set(character["portrait_prop_ids"]) - prop_ids
        if unknown:
            raise ProductionDesignPlanError(
                f"{character['entity_id']} names unknown portrait props {sorted(unknown)}"
            )

    raw_costumes = plan["costumes"]
    if not isinstance(raw_costumes, list):
        raise ProductionDesignPlanError("costumes must be an array")
    costumes: list[dict[str, str]] = []
    costume_ids: set[str] = set()
    for index, raw in enumerate(raw_costumes, start=1):
        item = _exact(raw, COSTUME_KEYS, f"costume plan {index}")
        asset_id = _text(item["asset_id"], f"costume plan {index}.asset_id")
        character_id = _text(
            item["character_id"], f"costume plan {asset_id}.character_id"
        )
        if (
            not ASSET_ID_RE.fullmatch(asset_id)
            or not asset_id.startswith("costume-")
            or asset_id in costume_ids
            or character_id not in speaking_ids
        ):
            raise ProductionDesignPlanError(
                f"Invalid costume ID or character binding for {asset_id}"
            )
        costume_ids.add(asset_id)
        costumes.append(
            {
                "asset_id": asset_id,
                "character_id": character_id,
                "description_en": _text(
                    item["description_en"],
                    f"costume plan {asset_id}.description_en",
                ),
            }
        )

    raw_locations = plan["locations"]
    if not isinstance(raw_locations, list) or not raw_locations:
        raise ProductionDesignPlanError("locations must be a non-empty array")
    locations: list[dict[str, Any]] = []
    location_ids: set[str] = set()
    covered_scene_ids: list[str] = []
    for index, raw in enumerate(raw_locations, start=1):
        item = _exact(raw, LOCATION_KEYS, f"location plan {index}")
        location_id = _text(item["location_id"], f"location plan {index}.location_id")
        if (
            not ASSET_ID_RE.fullmatch(location_id)
            or not location_id.startswith("loc-")
            or location_id in location_ids
        ):
            raise ProductionDesignPlanError(
                f"Invalid or repeated location ID {location_id}"
            )
        location_ids.add(location_id)
        scene_ids = _unique_ids(
            item["scene_ids"], f"location plan {location_id}.scene_ids", prefix="scene-"
        )
        if not scene_ids:
            raise ProductionDesignPlanError(f"{location_id} must cover at least one Scene")
        fixed_prop_ids = _unique_ids(
            item["fixed_prop_ids"],
            f"location plan {location_id}.fixed_prop_ids",
            prefix="prop-",
        )
        unknown_props = set(fixed_prop_ids) - prop_ids
        if unknown_props:
            raise ProductionDesignPlanError(
                f"{location_id} names unknown fixed props {sorted(unknown_props)}"
            )
        covered_scene_ids.extend(scene_ids)
        locations.append(
            {
                **item,
                "location_id": location_id,
                "scene_ids": scene_ids,
                "description_en": _text(
                    item["description_en"], f"{location_id}.description_en"
                ),
                "generation_prompt_en": _text(
                    item["generation_prompt_en"], f"{location_id}.generation_prompt_en"
                ),
                "fixed_prop_ids": fixed_prop_ids,
                "environment_state_en": _text(
                    item["environment_state_en"], f"{location_id}.environment_state_en"
                ),
                "lighting_state_en": _text(
                    item["lighting_state_en"], f"{location_id}.lighting_state_en"
                ),
                "palette_materials_en": _text(
                    item["palette_materials_en"], f"{location_id}.palette_materials_en"
                ),
            }
        )
    expected_scene_ids = [scene["scene_id"] for scene in screenplay["scenes"]]
    if (
        len(covered_scene_ids) != len(set(covered_scene_ids))
        or set(covered_scene_ids) != set(expected_scene_ids)
    ):
        raise ProductionDesignPlanError(
            "locations must partition every current screenplay Scene exactly once; "
            f"expected={expected_scene_ids}, actual={covered_scene_ids}"
        )

    return {
        "contract": "production-design-plan",
        "characters": characters,
        "props": props,
        "costumes": costumes,
        "locations": locations,
    }
