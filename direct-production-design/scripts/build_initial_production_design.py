#!/usr/bin/env python3
"""Execute an exact model-authored production-design plan."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from pkgutil import extend_path
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
    reusable_visual_candidate_from_current_record,
    reusable_visual_from_current_record,
)
from story_video.asset_catalog import (  # noqa: E402
    ASSET_CATALOG_RELATIVE_PATH,
    ASSET_MEDIA_RELATIVE_PATH,
    reject_task_local_asset_state,
)
from story_video.character_performance_map import (  # noqa: E402
    load_character_performance_map,
    role_asset_scope_gate,
)
from story_video.location_continuity_packages import (  # noqa: E402
    PACKAGE_CONTRACT,
    PACKAGE_RELATIVE_PATH,
)
from story_video.production_design_plan import (  # noqa: E402
    PLAN_RELATIVE_PATH,
    load_production_design_plan,
    render_generation_prompt,
)
from story_video.screenplay_contract import load_screenplay_file  # noqa: E402
from story_video.visual_asset_generation import (  # noqa: E402
    DEFAULT_IMAGE_SIZE,
    DEFAULT_TIMEOUT,
    generate_visual_asset,
)
from story_video.voice_reference_generation import (  # noqa: E402
    ensure_voice_references,
)


class InitialProductionDesignError(RuntimeError):
    pass


def _asset_repository_root(
    task_root: Path, repository_root: Path | None = None
) -> Path:
    return (repository_root or task_root).expanduser().resolve()


def _asset_catalog_path(task_root: Path, repository_root: Path | None = None) -> Path:
    return (
        _asset_repository_root(task_root, repository_root)
        / ASSET_CATALOG_RELATIVE_PATH
    )


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InitialProductionDesignError(f"Missing or invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise InitialProductionDesignError(f"{label} must contain one JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _plan_asset_id(asset: dict[str, Any]) -> str:
    if asset["type"] == "character":
        return str(asset["entity_id"])
    if asset["type"] == "location_master":
        return str(asset["location_id"])
    return str(asset["asset_id"])


def _jobs_from_model_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Copy exact model fields into execution jobs; author no prompt or dependency."""

    groups = (
        plan["characters"],
        plan["ensemble_rosters"],
        plan["props"],
        plan["costumes"],
        plan["locations"],
    )
    jobs: list[dict[str, Any]] = []
    for assets in groups:
        for asset in assets:
            jobs.append(
                {
                    "asset_id": _plan_asset_id(asset),
                    "kind": asset["type"],
                    "prompt": render_generation_prompt(asset["generation_prompt"]),
                    "relative_path": Path(asset["media_path"]),
                    "references": list(
                        asset["generation_prompt"]["continuity"][
                            "reference_asset_ids"
                        ]
                    ),
                    "depends_on": list(
                        asset["generation_prompt"]["continuity"][
                            "reference_asset_ids"
                        ]
                    ),
                }
            )
    return jobs


def _existing_assets(
    root: Path, *, repository_root: Path | None = None
) -> dict[str, Any]:
    path = _asset_catalog_path(root, repository_root)
    if not path.is_file():
        return {}
    catalog = _load(path, "production design asset catalog")
    if catalog.get("contract") != "production-design-assets" or not isinstance(
        catalog.get("assets"), dict
    ):
        raise InitialProductionDesignError(
            "assets.json must be the exact final production-design-assets contract"
        )
    return catalog["assets"]


def _semantic_reuse_review(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    force_regenerate: set[str],
    repository_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Expose semantic changes for Codex; never make or persist a decision."""

    asset_repository_root = _asset_repository_root(root, repository_root)
    previous_assets = _existing_assets(root, repository_root=asset_repository_root)
    review: list[dict[str, Any]] = []
    for job in jobs:
        asset_id = job["asset_id"]
        if asset_id in force_regenerate:
            continue
        output = job["relative_path"]
        visual = reusable_visual_candidate_from_current_record(
            root=asset_repository_root,
            record=previous_assets.get(asset_id),
            asset_type=job["kind"],
            output=output,
        )
        if visual is None:
            continue
        brief_path = (
            asset_repository_root / output
        ).parent / f"{output.stem}.brief.txt"
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
                "current_brief": job["prompt"],
            }
        )
    return review


def _require_codex_semantic_decisions(
    review: list[dict[str, Any]],
    *,
    codex_reuse: set[str],
    codex_regenerate_visual: set[str],
) -> None:
    review_ids = {item["asset_id"] for item in review}
    if codex_reuse & codex_regenerate_visual:
        raise InitialProductionDesignError(
            "A semantic-review candidate cannot be both reused and regenerated"
        )
    invalid = (codex_reuse | codex_regenerate_visual) - review_ids
    if invalid:
        raise InitialProductionDesignError(
            "Codex decisions do not match the current review candidates: "
            + ", ".join(sorted(invalid))
        )
    unresolved = review_ids - codex_reuse - codex_regenerate_visual
    if unresolved:
        raise InitialProductionDesignError(
            "Codex semantic reuse decision required for: "
            + ", ".join(sorted(unresolved))
        )


def _reusable_visuals(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    force_regenerate: set[str],
    codex_reuse: set[str],
    repository_root: Path | None = None,
) -> dict[str, dict[str, str]]:
    asset_repository_root = _asset_repository_root(root, repository_root)
    previous_assets = _existing_assets(root, repository_root=asset_repository_root)
    reusable: dict[str, dict[str, str]] = {}
    for job in jobs:
        asset_id = job["asset_id"]
        if asset_id in force_regenerate:
            continue
        visual = reusable_visual_from_current_record(
            root=asset_repository_root,
            record=previous_assets.get(asset_id),
            asset_type=job["kind"],
            output=job["relative_path"],
            prompt=job["prompt"],
        )
        if visual is None and asset_id in codex_reuse:
            visual = reusable_visual_candidate_from_current_record(
                root=asset_repository_root,
                record=previous_assets.get(asset_id),
                asset_type=job["kind"],
                output=job["relative_path"],
            )
            if visual is not None:
                brief_path = (
                    asset_repository_root / job["relative_path"]
                ).parent / f"{job['relative_path'].stem}.brief.txt"
                _write_text(brief_path, job["prompt"])
        if visual is not None:
            reusable[asset_id] = visual

    changed = True
    jobs_by_id = {job["asset_id"]: job for job in jobs}
    while changed:
        changed = False
        for asset_id in list(reusable):
            if any(dep not in reusable for dep in jobs_by_id[asset_id]["depends_on"]):
                reusable.pop(asset_id)
                changed = True
    return reusable


def _generate_job(
    root: Path,
    job: dict[str, Any],
    timeout: int,
    *,
    output_by_asset: dict[str, Path],
    repository_root: Path | None = None,
) -> dict[str, str]:
    asset_repository_root = _asset_repository_root(root, repository_root)
    target = asset_repository_root / job["relative_path"]
    brief_path = target.parent / f"{target.stem}.brief.txt"
    _write_text(brief_path, job["prompt"])
    result = generate_visual_asset(
        task_root=root,
        asset_id=job["asset_id"],
        asset_kind=job["kind"],
        prompt_file=brief_path,
        output_path=target,
        reference_images=[
            str(asset_repository_root / output_by_asset[reference])
            for reference in job["references"]
        ],
        asset_root=asset_repository_root / ASSET_MEDIA_RELATIVE_PATH,
        size=DEFAULT_IMAGE_SIZE,
        timeout=timeout,
    )
    return {
        "path": job["relative_path"].as_posix(),
        "uri": result["source_url"],
    }


def _run_dependency_graph(
    root: Path,
    jobs: list[dict[str, Any]],
    *,
    reusable: dict[str, dict[str, str]],
    timeout: int,
    max_workers: int,
    repository_root: Path | None = None,
) -> dict[str, dict[str, str]]:
    completed = dict(reusable)
    remaining = {
        job["asset_id"]: job for job in jobs if job["asset_id"] not in completed
    }
    output_by_asset = {
        job["asset_id"]: job["relative_path"] for job in jobs
    }
    while remaining:
        ready = [
            job
            for job in remaining.values()
            if set(job["depends_on"]).issubset(completed)
        ]
        if not ready:
            blocked = {
                asset_id: job["depends_on"] for asset_id, job in remaining.items()
            }
            raise InitialProductionDesignError(
                f"Production-design dependency cycle or missing reference: {blocked}"
            )
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(ready))) as executor:
            futures = {
                executor.submit(
                    _generate_job,
                    root,
                    job,
                    timeout,
                    output_by_asset=output_by_asset,
                    repository_root=repository_root,
                ): job["asset_id"]
                for job in ready
            }
            for future in as_completed(futures):
                asset_id = futures[future]
                try:
                    completed[asset_id] = future.result()
                except Exception as exc:
                    failures.append(f"{asset_id}: {exc}")
        if failures:
            raise InitialProductionDesignError(
                "Seedream asset wave failed: " + " | ".join(sorted(failures))
            )
        for job in ready:
            remaining.pop(job["asset_id"])
    return completed


def _final_catalog(
    plan: dict[str, Any],
    *,
    visuals: dict[str, dict[str, str]],
    voice_references: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Copy model semantic fields and attach only observed provider media facts."""

    assets: dict[str, Any] = {}
    for character in plan["characters"]:
        asset_id = character["entity_id"]
        assets[asset_id] = {
            "type": character["type"],
            "description_en": character["description_en"],
            "actor_profile": character["actor_profile"],
            "body_topology": character["body_topology"],
            "visual": visuals[asset_id],
            "voice": voice_references[asset_id],
        }
    for ensemble in plan["ensemble_rosters"]:
        asset_id = ensemble["asset_id"]
        assets[asset_id] = {
            "type": ensemble["type"],
            "description_en": ensemble["description_en"],
            "members": [
                {
                    "member_type_id": ensemble["member_type_id"],
                    "roster_asset": {
                        **visuals[asset_id],
                        "subject_count": ensemble["subject_count"],
                    },
                    "allowed_member_types_en": ensemble[
                        "allowed_member_types_en"
                    ],
                    "variation_profile": ensemble["variation_profile"],
                }
            ],
        }
    for prop in plan["props"]:
        asset_id = prop["asset_id"]
        assets[asset_id] = {
            "type": prop["type"],
            "description_en": prop["description_en"],
            "visual": visuals[asset_id],
        }
    for costume in plan["costumes"]:
        asset_id = costume["asset_id"]
        assets[asset_id] = {
            "type": costume["type"],
            "description_en": costume["description_en"],
            "character_id": costume["character_id"],
            "appearance_state_en": costume["appearance_state_en"],
            "visual": visuals[asset_id],
        }
    for location in plan["locations"]:
        asset_id = location["location_id"]
        assets[asset_id] = {
            "type": location["type"],
            "description_en": location["description_en"],
            "included_prop_ids": location["included_prop_ids"],
            "embedded_npc_asset_ids": location["embedded_npc_asset_ids"],
            "independent_performer_asset_ids": location[
                "independent_performer_asset_ids"
            ],
            "fixed_set_elements_en": location["fixed_set_elements_en"],
            "visual": visuals[asset_id],
        }
    return {
        "contract": "production-design-assets",
        "path_resolution": "repository_root_relative",
        "assets": assets,
    }


def _final_location_packages(plan: dict[str, Any]) -> dict[str, Any]:
    """Serialize only exact model-authored location fields into the task package."""

    return {
        "contract": PACKAGE_CONTRACT,
        "path_resolution": "task_root_relative",
        "locations": [
            {
                "location_id": location["location_id"],
                "scene_ids": location["scene_ids"],
                "embedded_npc_asset_ids": location["embedded_npc_asset_ids"],
                "independent_performer_asset_ids": location[
                    "independent_performer_asset_ids"
                ],
                "fixed_set_elements_en": location["fixed_set_elements_en"],
                "environment_state_en": location["environment_state_en"],
                "lighting_state_en": location["lighting_state_en"],
                "palette_materials_en": location["palette_materials_en"],
                "topology": location["topology"],
                "landmarks": location["landmarks"],
            }
            for location in plan["locations"]
        ],
    }


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
    reject_task_local_asset_state(root)
    if not 1 <= max_workers <= 8:
        raise InitialProductionDesignError("max_workers must be 1-8")
    role_scope = role_asset_scope_gate(root)
    performance = load_character_performance_map(root)
    screenplay_path = root / "screenplay-writer" / "screenplay.md"
    screenplay = load_screenplay_file(screenplay_path)
    plan = load_production_design_plan(
        root, performance=performance, screenplay=screenplay
    )
    # Validate optional aesthetic evidence. Its authored translation must already be
    # inside each model prompt; Python never appends it.
    aesthetic_reference = load_aesthetic_reference(root)
    jobs = _jobs_from_model_plan(plan)
    job_ids = {job["asset_id"] for job in jobs}
    character_ids = {character["entity_id"] for character in plan["characters"]}

    force_regenerate = set(regenerate_asset_ids or set())
    force_voice = set(regenerate_voice_asset_ids or set())
    codex_reuse = set(codex_reuse_asset_ids or set())
    codex_regenerate = set(codex_regenerate_visual_asset_ids or set())
    if (force_regenerate | codex_reuse | codex_regenerate) - job_ids:
        raise InitialProductionDesignError("Asset decision names an unknown plan asset")
    if force_voice - character_ids:
        raise InitialProductionDesignError("Voice regeneration names a non-character")
    if (
        force_regenerate & codex_reuse
        or force_regenerate & codex_regenerate
        or codex_reuse & codex_regenerate
    ):
        raise InitialProductionDesignError("An asset has contradictory decisions")

    review = _semantic_reuse_review(
        root,
        jobs,
        force_regenerate=force_regenerate,
        repository_root=REPOSITORY_ROOT,
    )
    if inspect_semantic_reuse:
        return {
            "status": "REVIEW_REQUIRED" if review else "PASS",
            "review_authority": "codex_direct_semantic_judgment",
            "review_prompt": (
                "direct-production-design/references/"
                "codex-asset-semantic-reuse-review.md"
            ),
            "candidates": review,
        }
    _require_codex_semantic_decisions(
        review,
        codex_reuse=codex_reuse,
        codex_regenerate_visual=codex_regenerate,
    )
    reusable = _reusable_visuals(
        root,
        jobs,
        force_regenerate=force_regenerate | codex_regenerate,
        codex_reuse=codex_reuse,
        repository_root=REPOSITORY_ROOT,
    )
    voice_references = ensure_voice_references(
        root,
        plan["characters"],
        repository_root=REPOSITORY_ROOT,
        timeout=timeout,
        max_workers=max_workers,
        force_regenerate=force_voice,
    )
    visuals = _run_dependency_graph(
        root,
        jobs,
        reusable=reusable,
        timeout=timeout,
        max_workers=max_workers,
        repository_root=REPOSITORY_ROOT,
    )
    catalog = _final_catalog(
        plan, visuals=visuals, voice_references=voice_references
    )
    _write_json(REPOSITORY_ROOT / ASSET_CATALOG_RELATIVE_PATH, catalog)
    _write_json(root / PACKAGE_RELATIVE_PATH, _final_location_packages(plan))
    return {
        "status": "PASS",
        "role_asset_scope_gate": role_scope["status"],
        "detailed_screenplay_review": role_scope["detailed_screenplay_review"],
        "asset_count": len(catalog["assets"]),
        "seedream_asset_job_count": len(jobs),
        "aesthetic_reference_frame_count": (
            aesthetic_reference["reference_count"]
            if aesthetic_reference is not None
            else 0
        ),
        "max_workers": max_workers,
        "forced_regeneration_asset_ids": sorted(force_regenerate),
        "forced_voice_regeneration_asset_ids": sorted(force_voice),
        "codex_semantic_reuse_asset_ids": sorted(codex_reuse),
        "codex_semantic_visual_regeneration_asset_ids": sorted(codex_regenerate),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--inspect-semantic-reuse", action="store_true")
    parser.add_argument("--codex-reuse-asset", action="append", default=[])
    parser.add_argument(
        "--codex-regenerate-visual-asset", action="append", default=[]
    )
    parser.add_argument("--regenerate-voice", action="append", default=[])
    parser.add_argument("--regenerate-asset", action="append", default=[])
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
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "REVIEW_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
