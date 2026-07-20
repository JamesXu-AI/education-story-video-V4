#!/usr/bin/env python3
"""Generate production-design assets from a task-authored semantic design plan."""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from pkgutil import extend_path
import re
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for script_root in (
    REPOSITORY_ROOT / "screenplay-writer" / "scripts",
    REPOSITORY_ROOT / "direct-production-design" / "scripts",
):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

import story_video  # noqa: E402

story_video.__path__ = extend_path(story_video.__path__, story_video.__name__)

from story_video.aesthetic_reference import load_aesthetic_reference  # noqa: E402
from story_video.asset_briefing import (  # noqa: E402
    brief_file_matches,
    character_portrait_performance_brief,
    group_portrait_subject_count,
    ordered_ensemble_member_types,
    reusable_visual_from_current_record,
    reusable_visual_candidate_from_current_record,
    silent_group_portrait_brief,
)
from story_video.character_performance_map import (  # noqa: E402
    load_character_performance_map,
    role_asset_scope_gate,
)
from story_video.production_design_plan import (  # noqa: E402
    PLAN_RELATIVE_PATH,
    load_production_design_plan,
)
from story_video.screenplay_contract import load_screenplay_file  # noqa: E402
from story_video.visual_asset_generation import (  # noqa: E402
    DEFAULT_IMAGE_SIZE,
    DEFAULT_TIMEOUT,
    generate_visual_asset,
)
from story_video.visual_style_contract import (  # noqa: E402
    VISUAL_STYLE_PROFILE,
    visual_style_contract,
)
from story_video.voice_reference_generation import (  # noqa: E402
    ensure_voice_references,
)


class InitialProductionDesignError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InitialProductionDesignError(f"Missing or invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise InitialProductionDesignError(f"{label} must contain one JSON object")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if isinstance(value, str):
        temporary.write_text(value.rstrip() + "\n", encoding="utf-8")
    else:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    temporary.replace(path)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def _speaking_entity_ids(performance: dict[str, Any]) -> set[str]:
    return {
        call["entity_id"]
        for segment in performance["scene_segment_calls"]
        for call in segment["calls"]
        if call["speaks"]
    }


def _silent_role_groups(
    entities: list[dict[str, Any]], speaking_ids: set[str]
) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        entity_id = entity["entity_id"]
        role_type = entity["group_role_type_en"]
        if entity_id in speaking_ids:
            if role_type != "none":
                raise InitialProductionDesignError(
                    f"Speaking entity {entity_id} cannot enter a group portrait"
                )
            continue
        if role_type == "none":
            raise InitialProductionDesignError(
                f"Silent entity {entity_id} lacks group_role_type_en"
            )
        grouped[role_type].append(entity)
    return list(grouped.items())


def _performance(entity: dict[str, Any]) -> dict[str, str]:
    label = entity["entity_label_en"]
    return {
        "core_desire_en": f"{label} pursues the exact story objective assigned in each Segment and never performs decorative business.",
        "core_belief_en": f"{label} interprets events through the stable moral and relationship facts recorded by the locked screenplay.",
        "fear_or_pressure_en": f"{label} responds to immediate story pressure with readable attention, breath and weight rather than random gestures.",
        "emotional_arc_en": f"{label} moves only through screenplay-authored emotional states and preserves every earned change across editorial cuts.",
        "attention_logic_en": f"{label} looks first at the current speaker or action cause, then at its consequence, and never scans without motivation.",
        "listening_behavior_en": f"{label} keeps the mouth closed while listening and responds through eyes, breath and anatomically appropriate posture.",
        "speech_preparation_en": f"{label} establishes the correct eyeline, takes one grounded breath and prepares the face before exact dialogue begins.",
        "embodied_acting_en": f"{label} uses the approved species-appropriate body plan with grounded balance, readable weight transfer and believable prop contact.",
        "settle_behavior_en": f"{label} completes every action, closes the mouth and holds the changed state for the authored safe edit handle.",
        "forbidden_performance_en": f"{label} never loops, mugs, waves randomly, changes identity, teleports, continues across an editorial cut or invents extra action.",
    }


def _asset_job(
    *,
    asset_id: str,
    kind: str,
    prompt: str,
    relative_path: Path,
    references: list[str],
    depends_on: list[str],
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "kind": kind,
        "prompt": prompt,
        "relative_path": relative_path,
        "references": references,
        "depends_on": depends_on,
    }


def _role_asset_ids_by_entity(
    *,
    entities: list[dict[str, Any]],
    speaking_ids: set[str],
    silent_groups: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, str]:
    """Map performance entities to visual role assets without story-name branches."""

    result = {
        entity["entity_id"]: entity["entity_id"]
        for entity in entities
        if entity["entity_id"] in speaking_ids
    }
    for role_type, group_entities in silent_groups:
        asset_id = "group-" + _slug(role_type)
        for entity in group_entities:
            entity_id = entity["entity_id"]
            if entity_id in result:
                raise InitialProductionDesignError(
                    f"Performance entity {entity_id} resolves to multiple role assets"
                )
            result[entity_id] = asset_id
    if set(result) != {entity["entity_id"] for entity in entities}:
        raise InitialProductionDesignError(
            "Every current performance entity must resolve to one visual role asset"
        )
    return result


def _scene_role_assets_by_location(
    *,
    plan: dict[str, Any],
    performance: dict[str, Any],
    entities: list[dict[str, Any]],
    role_asset_by_entity: dict[str, str],
) -> dict[str, list[str]]:
    """Derive the exhaustive on-screen Scene cast for every location asset."""

    entity_order = [entity["entity_id"] for entity in entities]
    scene_entity_ids: dict[str, set[str]] = defaultdict(set)
    for segment in performance["scene_segment_calls"]:
        scene_id = segment["scene_id"]
        for call in segment["calls"]:
            if call.get("presence_mode") == "on_screen":
                scene_entity_ids[scene_id].add(call["entity_id"])

    result: dict[str, list[str]] = {}
    for location in plan["locations"]:
        location_id = location["location_id"]
        ordered_role_sets: list[list[str]] = []
        for scene_id in location["scene_ids"]:
            entity_ids = scene_entity_ids.get(scene_id, set())
            if not entity_ids:
                raise InitialProductionDesignError(
                    f"Scene {scene_id} has no on-screen role for {location_id}"
                )
            ordered_role_sets.append(
                list(
                    dict.fromkeys(
                        role_asset_by_entity[entity_id]
                        for entity_id in entity_order
                        if entity_id in entity_ids
                    )
                )
            )
        first = ordered_role_sets[0]
        if any(role_ids != first for role_ids in ordered_role_sets[1:]):
            raise InitialProductionDesignError(
                f"Location {location_id} binds Scenes with different on-screen casts; "
                "author one location asset per distinct Scene cast"
            )
        result[location_id] = first
    return result


def _write_asset_plan(
    root: Path,
    jobs: list[dict[str, Any]],
    planning_sources: list[str],
    *,
    force_regenerate: set[str],
    codex_reuse: set[str],
    voice_references: dict[str, dict[str, Any]],
) -> None:
    path = root / "direct-production-design" / "assets.json"
    previous_assets: dict[str, Any] = {}
    if path.is_file():
        previous = _load(path, "production design asset plan")
        if previous.get("contract") not in {
            "production-design-asset-plan",
            "production-design-assets",
        }:
            raise InitialProductionDesignError(
                "assets.json is not the current production-design lifecycle contract"
            )
        if not isinstance(previous.get("assets"), dict):
            raise InitialProductionDesignError("assets.json assets must be an object")
        previous_assets = previous["assets"]

    assets: dict[str, Any] = {}
    jobs_by_id = {job["asset_id"]: job for job in jobs}
    if len(jobs_by_id) != len(jobs):
        raise InitialProductionDesignError("Production-design plan repeats an asset ID")
    for job in jobs:
        output = job["relative_path"].with_suffix(".png")
        record: dict[str, Any] = {
            "type": job["kind"],
            "status": "planned",
            "folder": output.parent.as_posix(),
            "image_path": output.as_posix(),
        }
        previous_record = previous_assets.get(job["asset_id"])
        if job["kind"] == "character":
            record["voice"] = voice_references[job["asset_id"]]
        reusable = None
        if job["asset_id"] not in force_regenerate:
            reusable = reusable_visual_from_current_record(
                root=root,
                record=previous_record,
                asset_type=job["kind"],
                output=output,
                prompt=job["prompt"],
            )
            if reusable is None and job["asset_id"] in codex_reuse:
                reusable = reusable_visual_candidate_from_current_record(
                    root=root,
                    record=previous_record,
                    asset_type=job["kind"],
                    output=output,
                )
        if reusable is not None:
            record.update(status="ready", visual=reusable)
        assets[job["asset_id"]] = record

    # If any binding source is stale, its consumers are stale too even if their
    # own textual prompt and output path did not change.
    changed = True
    while changed:
        changed = False
        for asset_id, job in jobs_by_id.items():
            if assets[asset_id]["status"] != "ready":
                continue
            if any(assets[dep]["status"] != "ready" for dep in job["depends_on"]):
                assets[asset_id].pop("visual", None)
                assets[asset_id]["status"] = "planned"
                changed = True

    _write(
        path,
        {
            "contract": "production-design-asset-plan",
            "planning_order": "task_semantics_then_dependency_waves",
            "planning_sources": planning_sources,
            "assets": assets,
        },
    )
    for asset_id in codex_reuse:
        if assets[asset_id]["status"] != "ready":
            continue
        job = jobs_by_id[asset_id]
        output = job["relative_path"].with_suffix(".png")
        brief_path = (root / output).parent / f"{output.stem}.brief.txt"
        _write(brief_path, job["prompt"])


def _semantic_reuse_review(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    force_regenerate: set[str],
) -> list[dict[str, Any]]:
    """Expose prompt changes for direct Codex review without making a decision."""

    path = root / "direct-production-design" / "assets.json"
    if not path.is_file():
        return []
    previous = _load(path, "production design asset plan")
    if previous.get("contract") not in {
        "production-design-asset-plan",
        "production-design-assets",
    } or not isinstance(previous.get("assets"), dict):
        raise InitialProductionDesignError(
            "assets.json is not the current production-design lifecycle contract"
        )
    previous_assets = previous["assets"]
    review: list[dict[str, Any]] = []
    for job in jobs:
        asset_id = job["asset_id"]
        if asset_id in force_regenerate:
            continue
        output = job["relative_path"].with_suffix(".png")
        visual = reusable_visual_candidate_from_current_record(
            root=root,
            record=previous_assets.get(asset_id),
            asset_type=job["kind"],
            output=output,
        )
        if visual is None:
            continue
        brief_path = (root / output).parent / f"{output.stem}.brief.txt"
        try:
            previous_brief = brief_path.read_text(encoding="utf-8").rstrip("\n")
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            previous_brief = None
        if previous_brief is not None and brief_file_matches(brief_path, job["prompt"]):
            continue
        review.append(
            {
                "asset_id": asset_id,
                "asset_type": job["kind"],
                "existing_media_path": visual["path"],
                "depends_on": list(job["depends_on"]),
                "previous_brief": previous_brief,
                "current_brief": job["prompt"].rstrip(),
            }
        )
    return review


def _require_codex_semantic_decisions(
    review: list[dict[str, Any]],
    *,
    codex_reuse: set[str],
    codex_regenerate_visual: set[str],
) -> None:
    """Require Codex to resolve every semantic change before generation starts."""

    review_ids = {item["asset_id"] for item in review}
    contradictory_decisions = sorted(codex_reuse & codex_regenerate_visual)
    if contradictory_decisions:
        raise InitialProductionDesignError(
            "The same semantic-review candidate cannot be both reused and regenerated: "
            + ", ".join(contradictory_decisions)
        )
    invalid_decisions = sorted(
        (codex_reuse | codex_regenerate_visual) - review_ids
    )
    if invalid_decisions:
        raise InitialProductionDesignError(
            "Codex semantic decisions are valid only for the current "
            "--inspect-semantic-reuse candidates: "
            + ", ".join(invalid_decisions)
        )
    unresolved_review = sorted(
        review_ids - codex_reuse - codex_regenerate_visual
    )
    if unresolved_review:
        raise InitialProductionDesignError(
            "Codex semantic reuse decision required before any visual generation. "
            "Run with --inspect-semantic-reuse, let Codex judge every listed old/current "
            "brief and existing image, then pass each equivalent asset with "
            "--codex-reuse-asset or each materially changed asset with "
            "--codex-regenerate-visual-asset. Unresolved asset(s): "
            + ", ".join(unresolved_review)
        )


def _update_asset_plan(
    root: Path,
    asset_id: str,
    *,
    status: str,
    visual: dict[str, str] | None = None,
    error: str | None = None,
) -> None:
    path = root / "direct-production-design" / "assets.json"
    plan = _load(path, "production design asset plan")
    record = plan["assets"][asset_id]
    record["status"] = status
    if visual is not None:
        record["visual"] = visual
    if error is not None:
        record["error"] = error
    _write(path, plan)


def _generate_job(root: Path, job: dict[str, Any], timeout: int) -> dict[str, str]:
    target = root / job["relative_path"].with_suffix(".png")
    brief_path = target.parent / f"{target.stem}.brief.txt"
    _write(brief_path, job["prompt"])
    result = generate_visual_asset(
        task_root=root,
        asset_id=job["asset_id"],
        asset_kind=job["kind"],
        prompt_file=brief_path,
        output_path=target,
        reference_images=job["references"],
        size=DEFAULT_IMAGE_SIZE,
        timeout=timeout,
    )
    return {
        "path": target.relative_to(root).as_posix(),
        "uri": result["source_url"],
    }


def _run_jobs(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    timeout: int,
    max_workers: int,
) -> dict[str, dict[str, str]]:
    plan = _load(
        root / "direct-production-design" / "assets.json",
        "production design asset plan",
    )
    results: dict[str, dict[str, str]] = {}
    pending: list[dict[str, Any]] = []
    for job in jobs:
        record = plan["assets"].get(job["asset_id"], {})
        visual = record.get("visual")
        if (
            record.get("status") == "ready"
            and isinstance(visual, dict)
            and set(visual) == {"path", "uri"}
            and (root / visual["path"]).is_file()
        ):
            results[job["asset_id"]] = dict(visual)
        else:
            pending.append(job)
    if not pending:
        return results
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(pending))) as executor:
        futures = {
            executor.submit(_generate_job, root, job, timeout): job["asset_id"]
            for job in pending
        }
        for future in as_completed(futures):
            asset_id = futures[future]
            try:
                visual = future.result()
                results[asset_id] = visual
                _update_asset_plan(root, asset_id, status="ready", visual=visual)
            except Exception as exc:
                _update_asset_plan(root, asset_id, status="failed", error=str(exc))
                failures.append(f"{asset_id}: {exc}")
    if failures:
        raise InitialProductionDesignError(
            "Seedream asset wave failed: " + " | ".join(sorted(failures))
        )
    return results


def _run_dependency_graph(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    timeout: int,
    max_workers: int,
) -> dict[str, dict[str, str]]:
    remaining = {job["asset_id"]: job for job in jobs}
    completed: dict[str, dict[str, str]] = {}
    all_ids = set(remaining)
    for job in jobs:
        unknown = set(job["depends_on"]) - all_ids
        if unknown:
            raise InitialProductionDesignError(
                f"{job['asset_id']} has unknown dependencies {sorted(unknown)}"
            )
    while remaining:
        ready = [
            job
            for job in remaining.values()
            if set(job["depends_on"]).issubset(completed)
        ]
        if not ready:
            blocked = {
                asset_id: job["depends_on"]
                for asset_id, job in remaining.items()
            }
            raise InitialProductionDesignError(
                f"Production-design asset dependency cycle: {blocked}"
            )
        wave = _run_jobs(
            root, ready, timeout=timeout, max_workers=max_workers
        )
        completed.update(wave)
        for job in ready:
            remaining.pop(job["asset_id"])
    return completed


def _aesthetic_prompt(aesthetic_reference: dict[str, Any] | None) -> str:
    if aesthetic_reference is None:
        return ""
    return (
        " Apply only the task's offline textual aesthetic translation: "
        + aesthetic_reference["prompt_core_en"]
        + " Preserve these higher authorities: "
        + " ".join(aesthetic_reference["preserve_project_locks_en"])
        + " Reject these imports: "
        + " ".join(aesthetic_reference["forbidden_imports_en"])
        + " No source video frame or derived global-style image is supplied."
    )


def build_task(
    task_dir: Path,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int = 4,
    regenerate_asset_ids: set[str] | None = None,
    regenerate_voice_asset_ids: set[str] | None = None,
    codex_reuse_asset_ids: set[str] | None = None,
    codex_regenerate_visual_asset_ids: set[str] | None = None,
    inspect_semantic_reuse: bool = False,
) -> dict[str, Any]:
    root = task_dir.expanduser().resolve(strict=True)
    if not 1 <= max_workers <= 8:
        raise InitialProductionDesignError("max_workers must be 1-8")
    role_scope = role_asset_scope_gate(root)
    performance = load_character_performance_map(root)
    screenplay_path = root / "screenplay-writer" / "screenplay.md"
    screenplay = load_screenplay_file(screenplay_path)
    plan = load_production_design_plan(
        root, performance=performance, screenplay=screenplay
    )
    entities = performance["performance_entities"]
    speaking_ids = _speaking_entity_ids(performance)
    speakers = [entity for entity in entities if entity["entity_id"] in speaking_ids]
    silent_groups = _silent_role_groups(entities, speaking_ids)
    entity_by_id = {entity["entity_id"]: entity for entity in entities}
    screenplay_characters = {
        character["name_en"]: character for character in screenplay["characters"]
    }
    character_plan_by_id = {
        item["entity_id"]: item for item in plan["characters"]
    }
    aesthetic_reference = load_aesthetic_reference(root)
    aesthetic_text = _aesthetic_prompt(aesthetic_reference)

    role_asset_by_entity = _role_asset_ids_by_entity(
        entities=entities,
        speaking_ids=speaking_ids,
        silent_groups=silent_groups,
    )
    scene_role_assets_by_location = _scene_role_assets_by_location(
        plan=plan,
        performance=performance,
        entities=entities,
        role_asset_by_entity=role_asset_by_entity,
    )
    background_location = next(
        location
        for location in plan["locations"]
        if location["location_id"] == plan["character_background_location_id"]
    )
    character_background_design = {
        "location_id": background_location["location_id"],
        "description_en": background_location["description_en"],
        "environment_state_en": background_location["environment_state_en"],
        "lighting_state_en": background_location["lighting_state_en"],
        "palette_materials_en": background_location["palette_materials_en"],
    }
    character_background_location_id = plan["character_background_location_id"]

    jobs: list[dict[str, Any]] = []
    output_by_asset: dict[str, Path] = {}
    for prop in plan["props"]:
        asset_id = prop["asset_id"]
        output = (
            Path("direct-production-design/assets/props")
            / asset_id.removeprefix("prop-")
            / "image"
        )
        output_by_asset[asset_id] = output.with_suffix(".png")
        jobs.append(
            _asset_job(
                asset_id=asset_id,
                kind="prop",
                prompt=(
                    "Generate one isolated final design reference for exactly one "
                    "story-significant prop. Preserve the task-authored object identity, "
                    "geometry, proportions, materials, contact zones, and negative "
                    "constraints exactly. No character, scene, text, grid, duplicate, "
                    "body-part substitution, or logo. TASK-AUTHORED PROP DESIGN: "
                    + prop["description_en"]
                    + aesthetic_text
                ),
                relative_path=output,
                references=[],
                depends_on=[],
            )
        )

    for speaker in speakers:
        entity_id = speaker["entity_id"]
        design = character_plan_by_id[entity_id]
        prop_ids = design["portrait_prop_ids"]
        output = (
            Path("direct-production-design/assets/characters")
            / entity_id
            / "identity"
        )
        output_by_asset[entity_id] = output.with_suffix(".png")
        prop_instruction = (
            " Ordered reference images correspond exactly to these approved portrait "
            "props: "
            + json.dumps(prop_ids, ensure_ascii=False)
            + ". Preserve each referenced prop's exact identity and do not redesign it."
            if prop_ids
            else " No independent portrait prop is approved; do not invent one."
        )
        jobs.append(
            _asset_job(
                asset_id=entity_id,
                kind="character",
                prompt=(
                    "Generate one full-body final-look portrait of exactly one "
                    "dialogue-owning subject inside the task-bound environment "
                    "described below. Never "
                    "use a plain, solid-color, studio, catalogue, cutout, empty, or "
                    "transparent background. The portrait subject must be the only "
                    "living being anywhere in the image: no other person, animal, "
                    "insect, crowd, silhouette, reflection, statue-like character, or "
                    "distant background cameo. Use the exact "
                    "task-authored identity and costume below. Show a motivated expression, "
                    "active eyeline, visible attention and readable thought; never a blank "
                    "stare or catalogue smile. For every non-human, use the exact natural "
                    "species body plan below: no humanized upright stance, human arms, "
                    "hands, feet, or extra gestural limbs. "
                    "Preserve this model-authored body topology exactly; every listed limb "
                    "set is exhaustive, every listed non-limb appendage must remain a "
                    "non-limb, and no natural-animal limb pair may be retained in addition: "
                    + json.dumps(design["body_topology"], ensure_ascii=False)
                    + ". "
                    "Use a grounded actor-ready styling pose, not a story action. No "
                    "contact sheet, turntable, multiple view, duplicate, text or logo."
                    + prop_instruction
                    + " TASK-AUTHORED CHARACTER DESIGN: "
                    + design["design_description_en"]
                    + " WRITER PERFORMANCE ENTITY: "
                    + speaker["description_en"]
                    + " TASK-BOUND CHARACTER BACKGROUND DESIGN JSON: "
                    + json.dumps(character_background_design, ensure_ascii=False)
                    + " "
                    + character_portrait_performance_brief(
                        screenplay=screenplay,
                        character_name_en=speaker["screenplay_character_name_en"],
                    )
                    + aesthetic_text
                ),
                relative_path=output,
                references=[output_by_asset[prop_id].as_posix() for prop_id in prop_ids],
                depends_on=list(prop_ids),
            )
        )

    excluded_dialogue_characters = [
        screenplay_characters[speaker["screenplay_character_name_en"]]
        for speaker in speakers
    ]
    for role_type, group_entities in silent_groups:
        asset_id = "group-" + _slug(role_type)
        group_character_names = list(
            dict.fromkeys(
                entity["screenplay_character_name_en"] for entity in group_entities
            )
        )
        group_brief, _, _ = silent_group_portrait_brief(
            role_type_en=role_type,
            entities=group_entities,
            screenplay_characters=[
                screenplay_characters[name] for name in group_character_names
            ],
            excluded_dialogue_characters=excluded_dialogue_characters,
        )
        output = (
            Path("direct-production-design/assets/role-groups")
            / asset_id.removeprefix("group-")
            / "group"
        )
        output_by_asset[asset_id] = output.with_suffix(".png")
        jobs.append(
            _asset_job(
                asset_id=asset_id,
                kind="ensemble_roster",
                prompt=(
                    group_brief
                    + " TASK-BOUND CHARACTER BACKGROUND DESIGN JSON: "
                    + json.dumps(character_background_design, ensure_ascii=False)
                    + aesthetic_text
                ),
                relative_path=output,
                references=[],
                depends_on=[],
            )
        )

    for costume in plan["costumes"]:
        asset_id = costume["asset_id"]
        character_id = costume["character_id"]
        output = (
            Path("direct-production-design/assets/costumes")
            / asset_id.removeprefix("costume-")
            / "image"
        )
        output_by_asset[asset_id] = output.with_suffix(".png")
        jobs.append(
            _asset_job(
                asset_id=asset_id,
                kind="costume",
                prompt=(
                    "Generate one isolated appearance-state reference for the same character "
                    "shown in reference image 1. Preserve identity, anatomy, scale, base "
                    "costume and approved accessories exactly; change only the task-authored "
                    "state. Preserve the task-bound environment declared below. "
                    "Never use a plain, solid-color, studio, catalogue, cutout, "
                    "empty, or transparent background. The referenced character must be "
                    "the only living being anywhere in the image: no other person, animal, "
                    "insect, crowd, silhouette, reflection, or distant background cameo. "
                    "No second subject, attacker, text, "
                    "grid or logo. "
                    "TASK-AUTHORED APPEARANCE STATE: "
                    + costume["description_en"]
                    + " TASK-BOUND CHARACTER BACKGROUND DESIGN JSON: "
                    + json.dumps(character_background_design, ensure_ascii=False)
                    + aesthetic_text
                ),
                relative_path=output,
                references=[output_by_asset[character_id].as_posix()],
                depends_on=[character_id],
            )
        )

    for location in plan["locations"]:
        asset_id = location["location_id"]
        prop_ids = location["fixed_prop_ids"]
        role_asset_ids = scene_role_assets_by_location[asset_id]
        output = (
            Path("direct-production-design/assets/locations")
            / asset_id.removeprefix("loc-")
            / "master"
        )
        output_by_asset[asset_id] = output.with_suffix(".png")
        prop_binding = (
            " Ordered reference images correspond exactly to these fixed plot props: "
            + json.dumps(prop_ids, ensure_ascii=False)
            + ". Reproduce every referenced object's exact geometry, proportions, "
            "silhouette, carving, material and contact zones; place it according to the "
            "task-authored set plan but never redesign, reinterpret, replace, duplicate, "
            "or omit it."
            if prop_ids
            else " No independent fixed plot prop is bound to this location."
        )
        role_binding = (
            " After any fixed-prop references, the remaining ordered reference images "
            "correspond exactly to these exhaustive current Scene role assets: "
            + json.dumps(role_asset_ids, ensure_ascii=False)
            + ". Include every individual role exactly once. For an ensemble-roster "
            "reference, include its complete approved group and every subject inside "
            "that group exactly once. Preserve identity, natural species anatomy, "
            "costume, proportions, markings, and closed roster. Omit none, substitute "
            "none, duplicate none, and invent no additional person, animal, silhouette, "
            "reflection, or cameo."
        )
        jobs.append(
            _asset_job(
                asset_id=asset_id,
                kind="location_master",
                prompt=(
                    "Generate one finished wide 16:9 Scene-cast location reference from "
                    "the exact "
                    "task-authored design below. Preserve navigable geography, entrances, "
                    "zones, landmarks, scale, materials and motivated light. This must not "
                    "be an empty or pure background: render the complete exhaustive current "
                    "Scene cast visibly inside the environment. No text, logos, grids, or "
                    "split layout."
                    + prop_binding
                    + role_binding
                    + " TASK-AUTHORED LOCATION DESIGN: "
                    + location["generation_prompt_en"]
                    + " TOPOLOGY JSON: "
                    + json.dumps(location["topology"], ensure_ascii=False, sort_keys=True)
                    + " LANDMARKS JSON: "
                    + json.dumps(location["landmarks"], ensure_ascii=False, sort_keys=True)
                    + aesthetic_text
                ),
                relative_path=output,
                references=[output_by_asset[prop_id].as_posix() for prop_id in prop_ids]
                + [output_by_asset[role_id].as_posix() for role_id in role_asset_ids],
                depends_on=[*prop_ids, *role_asset_ids],
            )
        )

    force_regenerate = set(regenerate_asset_ids or set())
    force_voice_regenerate = set(regenerate_voice_asset_ids or set())
    codex_reuse = set(codex_reuse_asset_ids or set())
    codex_regenerate_visual = set(codex_regenerate_visual_asset_ids or set())
    contradictory_decisions = sorted(
        (force_regenerate & codex_reuse)
        | (force_regenerate & codex_regenerate_visual)
        | (codex_reuse & codex_regenerate_visual)
    )
    if contradictory_decisions:
        raise InitialProductionDesignError(
            "The same asset cannot be both Codex-reused and regenerated: "
            + ", ".join(contradictory_decisions)
        )
    job_ids = {job["asset_id"] for job in jobs}
    unknown_regeneration = sorted(
        force_regenerate - job_ids
    )
    if unknown_regeneration:
        raise InitialProductionDesignError(
            "Unknown --regenerate-asset value(s); repair production-design-plan.json "
            "first when a required state asset does not yet exist: "
            + ", ".join(unknown_regeneration)
        )
    character_ids = {item["entity_id"] for item in plan["characters"]}
    unknown_voice_regeneration = sorted(
        force_voice_regenerate - character_ids
    )
    if unknown_voice_regeneration:
        raise InitialProductionDesignError(
            "Unknown --regenerate-voice character value(s): "
            + ", ".join(unknown_voice_regeneration)
        )
    unknown_reuse = sorted(codex_reuse - job_ids)
    if unknown_reuse:
        raise InitialProductionDesignError(
            "Unknown --codex-reuse-asset value(s): " + ", ".join(unknown_reuse)
        )
    unknown_visual_regeneration = sorted(codex_regenerate_visual - job_ids)
    if unknown_visual_regeneration:
        raise InitialProductionDesignError(
            "Unknown --codex-regenerate-visual-asset value(s): "
            + ", ".join(unknown_visual_regeneration)
        )

    semantic_review = _semantic_reuse_review(
        root,
        jobs,
        force_regenerate=force_regenerate,
    )
    if inspect_semantic_reuse:
        return {
            "status": "REVIEW_REQUIRED" if semantic_review else "PASS",
            "review_authority": "codex_direct_semantic_judgment",
            "review_prompt": (
                "direct-production-design/references/"
                "codex-asset-semantic-reuse-review.md"
            ),
            "decision_rule": (
                "Codex must compare visible meaning rather than wording. Reuse only "
                "when the existing media can satisfy the current brief without any "
                "visible change; otherwise regenerate."
            ),
            "candidates": semantic_review,
        }
    _require_codex_semantic_decisions(
        semantic_review,
        codex_reuse=codex_reuse,
        codex_regenerate_visual=codex_regenerate_visual,
    )

    planning_sources = [
        screenplay_path.relative_to(root).as_posix(),
        PLAN_RELATIVE_PATH.as_posix(),
    ]
    voice_references = ensure_voice_references(
        root,
        plan["characters"],
        timeout=timeout,
        max_workers=max_workers,
        force_regenerate=force_voice_regenerate,
    )
    _write_asset_plan(
        root,
        jobs,
        planning_sources,
        force_regenerate=force_regenerate | codex_regenerate_visual,
        codex_reuse=codex_reuse,
        voice_references=voice_references,
    )
    visuals = _run_dependency_graph(
        root, jobs, timeout=timeout, max_workers=max_workers
    )

    assets: dict[str, Any] = {}
    for speaker in speakers:
        entity_id = speaker["entity_id"]
        design = character_plan_by_id[entity_id]
        prop_ids = design["portrait_prop_ids"]
        assets[entity_id] = {
            "type": "character",
            "status": "ready",
            "description_en": design["design_description_en"]
            + (
                " Approved portrait props: " + ", ".join(prop_ids) + "."
                if prop_ids
                else " No independent portrait prop is approved."
            ),
            "body_topology": design["body_topology"],
            "visual": visuals[entity_id],
            "performance": _performance(speaker),
            "voice": voice_references[entity_id],
        }

    excluded_speaking_ids = [
        entity["entity_id"] for entity in entities if entity["entity_id"] in speaking_ids
    ]
    excluded_dialogue_names = [
        entity["screenplay_character_name_en"]
        for entity in entities
        if entity["entity_id"] in speaking_ids
    ]
    for role_type, group_entities in silent_groups:
        asset_id = "group-" + _slug(role_type)
        member_types = ordered_ensemble_member_types(group_entities)
        subject_count = group_portrait_subject_count(member_types)
        assets[asset_id] = {
            "type": "ensemble_roster",
            "status": "ready",
            "description_en": (
                f"One group portrait for silent role type {role_type}; closed member "
                "types: " + ", ".join(member_types) + "."
            ),
            "members": [
                {
                    "member_type_id": _slug(role_type) + "-silent-role-type",
                    "group_role_type_en": role_type,
                    "roster_asset": {
                        **visuals[asset_id],
                        "subject_count": subject_count,
                    },
                    "included_entity_ids": [
                        entity["entity_id"] for entity in group_entities
                    ],
                    "excluded_speaking_entity_ids": excluded_speaking_ids,
                    "excluded_dialogue_character_names_en": excluded_dialogue_names,
                    "allowed_member_types_en": member_types,
                    "variation_profile": {
                        "locked_traits_en": (
                            f"Preserve the approved {role_type} silhouettes and these exact "
                            "member types without substitution: " + ", ".join(member_types)
                        ),
                        "allowed_variation_en": (
                            "Allow only small natural variation inside an approved member "
                            "type; never introduce another species/type or any dialogue "
                            "portrait identity/species."
                        ),
                    },
                    "authority": "silent_cinematic_role_group_portrait",
                }
            ],
        }

    for prop in plan["props"]:
        assets[prop["asset_id"]] = {
            "type": "prop",
            "status": "ready",
            "description_en": prop["description_en"],
            "visual": visuals[prop["asset_id"]],
        }
    for costume in plan["costumes"]:
        assets[costume["asset_id"]] = {
            "type": "costume",
            "status": "ready",
            "description_en": costume["description_en"],
            "visual": visuals[costume["asset_id"]],
            "character_id": costume["character_id"],
            "appearance_state_en": costume["description_en"],
            "authority": "character_costume_and_appearance_state",
        }
    for location in plan["locations"]:
        assets[location["location_id"]] = {
            "type": "location_master",
            "status": "ready",
            "description_en": location["description_en"],
            "visual": visuals[location["location_id"]],
            "included_prop_ids": location["fixed_prop_ids"],
            "included_role_asset_ids": scene_role_assets_by_location[
                location["location_id"]
            ],
            "authority": "scene_cast_location_with_current_props_and_roles",
        }

    catalog = {
        "contract": "production-design-assets",
        "visual_style_profile": VISUAL_STYLE_PROFILE,
        "visual_style_contract": visual_style_contract(),
        "path_resolution": "task_root_relative",
        "cross_segment_policy": "narrative_state_through_independent_edits",
        "assets": assets,
    }
    _write(root / "direct-production-design" / "assets.json", catalog)

    semantic_summary = {
        "character_background_location_id": character_background_location_id,
        "character_designs": plan["characters"],
        "prop_designs": plan["props"],
        "costume_states": plan["costumes"],
        "location_designs": [
            {
                "location_id": item["location_id"],
                "scene_ids": item["scene_ids"],
                "description_en": item["description_en"],
                "fixed_prop_ids": item["fixed_prop_ids"],
                "included_role_asset_ids": scene_role_assets_by_location[
                    item["location_id"]
                ],
            }
            for item in plan["locations"]
        ],
    }
    aesthetic_spec = (
        "\n\n## Task Aesthetic Reference\n\n"
        "The task-local aesthetic study is offline analysis evidence only. Only its "
        "textual translation enters generation; source frames never become references.\n"
        if aesthetic_reference is not None
        else ""
    )
    spec = (
        "# Visual Production Specification\n\n"
        "## Project Look\n\n"
        "Use the current repository visual-style contract for every independently "
        "generated asset.\n\n"
        "## Dynamic task semantics\n\n"
        "The task-specific facts below were authored from the current story and "
        "screenplay before generation. Generic pipeline code does not infer or branch "
        "on their names. Dialogue portraits, silent role groups, props, appearance "
        "states, the character-background location, locations, and fixed-prop bindings "
        "must preserve them exactly.\n\n```json\n"
        + json.dumps(semantic_summary, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        "## Dependency rule\n\n"
        "Every asset with a declared dependency is generated only after its sources. "
        "A referenced prop's exact geometry and material bind every portrait or location "
        "that includes it. Scene-cast location references are generated only after every "
        "current Scene role asset, and must include the exhaustive bound cast.\n\n"
        "## Environment reference\n\n"
        "The Scene-cast location reference is the single full-frame environment image "
        "authority and includes every role used by its bound Scene. The task-semantic "
        "character_background_location_id supplies textual forest environment design to "
        "every character, costume, and ensemble reference without creating a generation "
        "cycle. Reuse the Scene-cast location reference directly for every bound Scene "
        "and Segment. Never generate "
        "a Scene background, global background, camera background, or other full-frame "
        "derivative of the location master."
        + aesthetic_spec
    )
    _write(root / "direct-production-design" / "visual-production-spec.md", spec)

    location_packages = [
        {
            key: value
            for key, value in location.items()
            if key
            not in {
                "description_en",
                "generation_prompt_en",
                "fixed_prop_ids",
            }
        }
        for location in plan["locations"]
    ]
    _write(
        root / "direct-production-design" / "location-continuity-packages.json",
        {
            "contract": "location_continuity_packages/location-master-only",
            "path_resolution": "task_root_relative",
            "locations": location_packages,
        },
    )
    return {
        "status": "PASS",
        "role_asset_scope_gate": role_scope["status"],
        "detailed_screenplay_review": role_scope["detailed_screenplay_review"],
        "asset_count": len(assets),
        "seedream_asset_job_count": len(jobs),
        "dependency_wave_count": max(
            (len(job["depends_on"]) > 0 for job in jobs), default=0
        )
        + 1,
        "aesthetic_reference_frame_count": (
            aesthetic_reference["reference_count"]
            if aesthetic_reference is not None
            else 0
        ),
        "max_workers": max_workers,
        "forced_regeneration_asset_ids": sorted(force_regenerate),
        "forced_voice_regeneration_asset_ids": sorted(force_voice_regenerate),
        "codex_semantic_reuse_asset_ids": sorted(codex_reuse),
        "codex_semantic_visual_regeneration_asset_ids": sorted(
            codex_regenerate_visual
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--inspect-semantic-reuse",
        action="store_true",
        help=(
            "Print every existing visual whose old and current briefs differ, then "
            "exit without generating, uploading, or changing task files. Codex must "
            "make the semantic decision."
        ),
    )
    parser.add_argument(
        "--codex-reuse-asset",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help=(
            "Reuse one existing visual after Codex directly judged that its old and "
            "current briefs require no visible change; repeat for multiple assets."
        ),
    )
    parser.add_argument(
        "--codex-regenerate-visual-asset",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help=(
            "Regenerate one existing visual after Codex directly judged that the "
            "current brief requires visible changes. Character voice is preserved."
        ),
    )
    parser.add_argument(
        "--regenerate-voice",
        action="append",
        default=[],
        metavar="CHARACTER_ID",
        help=(
            "Regenerate only one character voice without regenerating that character's "
            "visual asset; repeat for multiple rejected voices."
        ),
    )
    parser.add_argument(
        "--regenerate-asset",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help=(
            "Force one current visual asset and every dependent visual asset to "
            "regenerate while preserving character voice; repeat for multiple "
            "current visual failures."
        ),
    )
    args = parser.parse_args()
    try:
        result = build_task(
            args.task_dir,
            timeout=args.timeout,
            max_workers=args.max_workers,
            regenerate_asset_ids=set(args.regenerate_asset),
            regenerate_voice_asset_ids=set(args.regenerate_voice),
            codex_reuse_asset_ids=set(args.codex_reuse_asset),
            codex_regenerate_visual_asset_ids=set(
                args.codex_regenerate_visual_asset
            ),
            inspect_semantic_reuse=args.inspect_semantic_reuse,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "REVIEW_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
