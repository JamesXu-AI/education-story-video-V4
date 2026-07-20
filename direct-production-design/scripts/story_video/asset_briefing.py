"""Compile story/performance authority into exact portrait-generation briefs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


class AssetBriefingError(ValueError):
    """Raised when writer authority is too vague to compile a safe visual brief."""


def ordered_ensemble_member_types(
    entities: Iterable[dict[str, Any]],
) -> list[str]:
    """Return the exact, ordered silent member types without broadening the cast."""

    result: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        entity_id = str(entity.get("entity_id", "<unknown>"))
        values = entity.get("ensemble_member_types_en")
        if not isinstance(values, list) or not values:
            raise AssetBriefingError(
                f"Silent ensemble entity {entity_id} lacks ensemble_member_types_en."
            )
        for index, raw in enumerate(values, start=1):
            if not isinstance(raw, str) or not raw.strip():
                raise AssetBriefingError(
                    f"Silent ensemble entity {entity_id} member type {index} "
                    "must be non-empty text."
                )
            value = raw.strip()
            folded = value.casefold()
            if folded in seen:
                raise AssetBriefingError(
                    f"Silent ensemble member type is repeated: {value}."
                )
            seen.add(folded)
            result.append(value)
    if not result:
        raise AssetBriefingError("A silent group requires at least one member type.")
    return result


def group_portrait_subject_count(member_types: list[str]) -> int:
    """Use one representative per exact type, duplicating only a lone broad type."""

    if not member_types:
        raise AssetBriefingError("A silent group requires at least one member type.")
    return max(2, len(member_types))


def first_dialogue_delivery(
    screenplay: dict[str, Any], *, character_name_en: str
) -> str:
    """Select the writer-authored first-impression performance for a portrait."""

    for segment in screenplay.get("segments", []):
        for block in segment.get("blocks", []):
            if (
                block.get("type") == "dialogue"
                and block.get("speaker_en") == character_name_en
            ):
                delivery = block.get("delivery_en")
                if isinstance(delivery, str) and delivery.strip():
                    return delivery.strip()
                raise AssetBriefingError(
                    f"First dialogue for {character_name_en} lacks delivery_en."
                )
    raise AssetBriefingError(
        f"Dialogue-owning character {character_name_en} has no authored delivery."
    )


def character_portrait_performance_brief(
    *,
    screenplay: dict[str, Any],
    character_name_en: str,
) -> str:
    """Compile a concrete closed-mouth portrait expression from screenplay authority."""

    characters = {
        item.get("name_en"): item
        for item in screenplay.get("characters", [])
        if isinstance(item, dict)
    }
    character = characters.get(character_name_en)
    if not isinstance(character, dict):
        raise AssetBriefingError(
            f"Missing screenplay Character authority for {character_name_en}."
        )
    delivery = first_dialogue_delivery(
        screenplay, character_name_en=character_name_en
    )
    narrative_function = character.get("narrative_function_en")
    description = character.get("description_en")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (narrative_function, description)
    ):
        raise AssetBriefingError(
            f"Screenplay Character authority for {character_name_en} is incomplete."
        )
    return (
        "EXACT PORTRAIT PERFORMANCE AUTHORITY — The face, eyes, eyeline, brow or "
        "species-equivalent facial features, and grounded posture must read as "
        f"'{delivery}'. Keep the mouth naturally closed because this is a still "
        "portrait, while preserving the thought and emotional pressure of that exact "
        "writer-authored first dialogue delivery. Do not replace it with a neutral "
        "face, generic smile, random cuteness, unrelated anger, or a later injury "
        f"state. Dramatic function: {narrative_function.strip()} Character behavior: "
        f"{description.strip()}"
    )


def silent_group_portrait_brief(
    *,
    role_type_en: str,
    entities: list[dict[str, Any]],
    screenplay_characters: list[dict[str, Any]],
    excluded_dialogue_characters: list[dict[str, Any]],
) -> tuple[str, list[str], int]:
    """Compile a closed, species-safe group portrait brief from writer authority."""

    member_types = ordered_ensemble_member_types(entities)
    subject_count = group_portrait_subject_count(member_types)
    allowed_cast = [
        {
            "entity_id": entity["entity_id"],
            "label_en": entity["entity_label_en"],
            "description_en": entity["description_en"],
            "ensemble_member_types_en": entity["ensemble_member_types_en"],
        }
        for entity in entities
    ]
    character_authority = [
        {
            "name_en": character["name_en"],
            "narrative_function_en": character["narrative_function_en"],
            "description_en": character["description_en"],
        }
        for character in screenplay_characters
    ]
    excluded_dialogue_authority = [
        {
            "name_en": character["name_en"],
            "description_en": character["description_en"],
        }
        for character in excluded_dialogue_characters
    ]
    # Local import keeps this pure module dependency-light for validation and tests.
    import json

    brief = (
        "Generate exactly one clean full-body group portrait for one silent cinematic "
        f"role type ({role_type_en}), containing exactly {subject_count} subjects "
        "together in one coherent image. This is a group portrait, not a contact "
        "sheet, lineup grid, turntable, split screen, or separate panels. "
        "CAST COMPOSITION IS CLOSED AND EXHAUSTIVE. Render one clearly recognizable "
        "subject for every ordered member type below. Only when the list contains a "
        "single broad member type, render the minimum second subject as a restrained "
        "variation inside that exact type. Do not introduce, substitute, hybridize, "
        "or imply any unlisted species or member type. A broader taxonomic relative, "
        "domestic analogue, pet analogue, or cute filler animal is not equivalent. "
        "Before rendering, infer the real species-appropriate base anatomy for each "
        "declared member type and commit that subject to exactly one coherent body "
        "plan. Characterful inner life belongs in expression, gaze, attention, and "
        "species-appropriate pose; it never authorizes humanized posture or extra limbs. "
        "A natural quadruped has exactly four "
        "total limbs: its two forelegs are already its front limb pair and must not "
        "coexist with added arms or hands. A biped has exactly two legs and no retained "
        "second hind-leg pair. A bird has exactly two legs and two wings, with no extra "
        "arms, hands, forelegs, or duplicate wings. Preserve the corresponding real "
        "feet, paws, hooves, wings, or hands for the selected body plan. No subject may "
        "have extra, duplicated, missing, fused, detached, or hybrid limbs. "
        "Every project "
        "character with dialogue is forbidden. The prohibition covers the same "
        "identity AND the same species/type, even when anonymous, recolored, resized, "
        "restyled, or claimed to be a different individual; it also covers lookalikes, "
        "duplicates, silhouettes, reflections, and background cameos. Every subject "
        "must show the "
        "role's writer-authored inner life through motivated expression, active "
        "eyeline, attention, and visible thought; no blank wildlife stare or fixed "
        "catalogue smile. Keep every animal in its natural species body plan; no upright "
        "animal biped, arms, hands, human torso, or human feet. Use readable poses inside "
        "the separately bound character "
        "background location, preserving that reference's environment, palette, and "
        "light without adding unlisted subjects. Never use a plain, solid-color, "
        "studio, catalogue, cutout, or empty backdrop. No story action, text, border, "
        "or logo. EXACT ORDERED MEMBER TYPES JSON: "
        + json.dumps(member_types, ensure_ascii=False)
        + ". ALLOWED PERFORMANCE ENTITIES JSON: "
        + json.dumps(allowed_cast, ensure_ascii=False, sort_keys=True)
        + ". SCREENPLAY CHARACTER AUTHORITY JSON: "
        + json.dumps(character_authority, ensure_ascii=False, sort_keys=True)
        + ". FORBIDDEN DIALOGUE PORTRAIT IDENTITIES AND SPECIES/TYPES JSON: "
        + json.dumps(
            excluded_dialogue_authority, ensure_ascii=False, sort_keys=True
        )
    )
    return brief, member_types, subject_count


def brief_file_matches(path: Path, expected_brief: str) -> bool:
    """Check reusable current evidence without adding cache or hash metadata."""

    try:
        actual = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return False
    return actual == expected_brief.rstrip() + "\n"


def reusable_visual_from_current_record(
    *,
    root: Path,
    record: Any,
    asset_type: str,
    output: Path,
    prompt: str,
) -> dict[str, str] | None:
    """Reuse only media whose final path and colocated authority brief are current."""

    visual = reusable_visual_candidate_from_current_record(
        root=root,
        record=record,
        asset_type=asset_type,
        output=output,
    )
    if visual is None:
        return None
    brief_path = (root / output).parent / f"{output.stem}.brief.txt"
    if not brief_file_matches(brief_path, prompt):
        return None
    return visual


def reusable_visual_candidate_from_current_record(
    *,
    root: Path,
    record: Any,
    asset_type: str,
    output: Path,
) -> dict[str, str] | None:
    """Return structurally reusable media without deciding prompt semantics."""

    if (
        not isinstance(record, dict)
        or record.get("type") != asset_type
        or record.get("status") != "ready"
    ):
        return None
    visual = record.get("visual")
    if not isinstance(visual, dict) and asset_type == "ensemble_roster":
        members = record.get("members")
        if isinstance(members, list) and len(members) == 1:
            roster_asset = members[0].get("roster_asset")
            if isinstance(roster_asset, dict):
                visual = {
                    "path": roster_asset.get("path"),
                    "uri": roster_asset.get("uri"),
                }
    if (
        not isinstance(visual, dict)
        or set(visual) != {"path", "uri"}
        or visual.get("path") != output.as_posix()
        or not isinstance(visual.get("uri"), str)
        or not visual["uri"].strip()
        or not (root / output).is_file()
    ):
        return None
    return {"path": visual["path"], "uri": visual["uri"]}
