"""Validate final Seedance Prompts against assets.json semantic authority.

Compatibility is semantic, not a byte comparison.  This module freezes the exact
final Prompt, its provider-token responsibilities, the selected assets.json rows,
and every owned Storyboard requirement.  A current semantic PASS is required
before an execution plan may be published.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .seed_master_runtime import (
    COMPILE_MANIFEST_RELATIVE,
    SCRIPT_DIR_RELATIVE,
    SeedMasterRuntimeError,
    read_json,
    sha256_file,
    token_sort_key,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ASSET_CATALOG_RELATIVE = Path("assets/assets.json")
PACKET_DIR_RELATIVE = Path(
    ".pending/virtual-production/asset-compatibility-review-packets"
)
REVIEW_DIR_RELATIVE = Path(
    ".pending/virtual-production/asset-compatibility-reviews"
)
REWORK_DIR_RELATIVE = Path(
    ".pending/virtual-production/asset-rework-requests"
)

PACKET_CONTRACT = "prompt-assets-json-compatibility-packet-v2"
REVIEW_CONTRACT = "prompt-assets-json-compatibility-review-v2"
RECEIPT_CONTRACT = "prompt-assets-json-compatibility-receipt-v2"
REWORK_CONTRACT = "prompt-asset-semantics-rework-request-v2"

CONFLICT_DOMAINS = {
    "identity",
    "character_state",
    "injury_body_state",
    "wardrobe_costume",
    "prop_state",
    "occupancy",
    "location_geography",
    "lighting_color",
    "time_weather",
    "ensemble_membership_count",
    "voice_identity",
    "sound_role",
    "action_phase",
    "body_topology",
    "other",
}
PASS_CLASSES = {"exact_state_match", "compatible_nonconflicting_subset"}
FAIL_CLASSES = {"conflicting", "ambiguous", "missing_required_state"}
ASSET_RELEVANT_CATEGORIES = {
    "character_identity",
    "occupancy_appearance",
    "production_design",
    "wardrobe_prop",
    "voice_mouth",
    "lighting_color",
    "continuity",
    "forbidden_change",
}


class AssetCompatibilityResolutionError(SeedMasterRuntimeError):
    """A semantic binding failure tied to one or more concrete asset IDs."""

    def __init__(
        self,
        message: str,
        *,
        affected_asset_ids: list[str],
        required_actions: list[str],
        provider_token: str | None = None,
    ) -> None:
        super().__init__(message)
        self.affected_asset_ids = affected_asset_ids
        self.required_actions = required_actions
        self.provider_token = provider_token


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SeedMasterRuntimeError(f"{label} must be non-empty text")
    return value.strip()


def _string_list(
    value: Any, label: str, *, allow_empty: bool = False
) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise SeedMasterRuntimeError(f"{label} must be a string array")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise SeedMasterRuntimeError(f"{label} must not contain duplicates")
    return normalized


def _asset_record(
    catalog: dict[str, Any], namespace: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    assets = catalog.get("assets")
    if not isinstance(assets, dict):
        raise SeedMasterRuntimeError("assets.json has no assets object")
    if "--" not in namespace:
        value = assets.get(namespace)
        if not isinstance(value, dict):
            raise SeedMasterRuntimeError(
                f"assets.json has no semantic authority for {namespace!r}"
            )
        return value, None
    roster_id, member_type_id = namespace.split("--", 1)
    roster = assets.get(roster_id)
    if not isinstance(roster, dict) or roster.get("type") != "ensemble_roster":
        raise SeedMasterRuntimeError(
            f"assets.json has no ensemble authority for {namespace!r}"
        )
    matches = [
        item
        for item in roster.get("members", [])
        if isinstance(item, dict) and item.get("member_type_id") == member_type_id
    ]
    if len(matches) != 1:
        raise SeedMasterRuntimeError(
            f"assets.json ensemble authority is ambiguous for {namespace!r}"
        )
    return roster, matches[0]


def _catalog_semantics(
    catalog: dict[str, Any], namespace: str
) -> dict[str, Any]:
    asset, member = _asset_record(catalog, namespace)
    result: dict[str, Any] = {
        "asset_id": namespace,
        "asset_type": (
            "ensemble_roster_member" if member is not None else asset.get("type")
        ),
        "description_en": asset.get("description_en"),
    }
    for field in (
        "character_id",
        "appearance_state_en",
        "sound_role",
        "owner_character_id",
        "included_prop_ids",
        "included_role_asset_ids",
        "actor_profile",
        "body_topology",
    ):
        if field in asset:
            result[field] = asset[field]
    if asset.get("type") == "costume":
        assets = catalog.get("assets")
        owner = (
            assets.get(asset.get("character_id"))
            if isinstance(assets, dict)
            else None
        )
        if isinstance(owner, dict) and isinstance(owner.get("body_topology"), dict):
            result["owner_body_topology"] = owner["body_topology"]
    voice = asset.get("voice")
    if isinstance(voice, dict) and isinstance(voice.get("description_en"), str):
        result["voice_description_en"] = voice["description_en"]
    if member is not None:
        for field in (
            "member_type_id",
            "allowed_member_types_en",
            "variation_profile",
        ):
            if field in member:
                result[field] = member[field]
    return result


def _body_topology_contract(
    catalog: dict[str, Any], namespace: str, provider_role: str
) -> dict[str, Any] | None:
    """Return the visible character topology selected by an image binding."""

    if provider_role != "reference_image":
        return None
    asset, member = _asset_record(catalog, namespace)
    if member is not None:
        return None
    owner_id: str | None = None
    if asset.get("type") == "character":
        owner_id = namespace
        topology = asset.get("body_topology")
    elif asset.get("type") == "costume":
        owner_id = asset.get("character_id")
        assets = catalog.get("assets")
        owner = assets.get(owner_id) if isinstance(assets, dict) else None
        topology = owner.get("body_topology") if isinstance(owner, dict) else None
    else:
        return None
    if not isinstance(owner_id, str) or not isinstance(topology, dict):
        raise AssetCompatibilityResolutionError(
            f"{namespace!r} has no model-authored body topology authority",
            affected_asset_ids=[namespace],
            required_actions=[
                f"Author the owning character body_topology for {namespace!r} in the production-design plan and rebuild assets.json without replacing valid media."
            ],
        )
    return {
        "asset_id": namespace,
        "character_id": owner_id,
        "body_topology": topology,
    }


def _require_prompt_body_topology(
    *,
    prompt: str,
    catalog: dict[str, Any],
    namespace: str,
    provider_role: str,
    token: str,
) -> dict[str, Any] | None:
    contract = _body_topology_contract(catalog, namespace, provider_role)
    if contract is None:
        return None
    serialized = json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    required_line = f"- body_topology_contract: {serialized}"
    if prompt.count(required_line) != 1:
        raise AssetCompatibilityResolutionError(
            f"{token} final Seedance Prompt does not carry the exact current body topology for {namespace!r}",
            affected_asset_ids=[namespace],
            required_actions=[
                f"Recompile the Route B Segment Prompt and include exactly once: {required_line}"
            ],
            provider_token=token,
        )
    return contract


def _prompt_namespaces(prompt_rows: list[dict[str, Any]]) -> list[str]:
    namespaces = sorted(
        {
            _text(row.get("element"), "Prompt binding element").split(".", 1)[0]
            for row in prompt_rows
        }
    )
    if not namespaces:
        raise SeedMasterRuntimeError("Prompt binding has no asset namespace")
    return namespaces


def _owned_requirements(task_dir: Path, parsed: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = read_json(
        task_dir / COMPILE_MANIFEST_RELATIVE,
        label="Storyboard compile manifest",
    )
    rows = manifest.get("requirements")
    if not isinstance(rows, list):
        raise SeedMasterRuntimeError("Storyboard compile manifest lacks requirements")
    segment_id = parsed["segment_id"]
    owned = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("segment_id") == segment_id
    ]
    expected_ids = parsed["metadata"]["storyboard_requirement_ids"]
    if [row.get("requirement_id") for row in owned] != expected_ids:
        raise SeedMasterRuntimeError(
            f"{segment_id} asset review requirements differ from the Route B Script"
        )
    result: list[dict[str, Any]] = []
    for row in owned:
        requirement_id = _text(row.get("requirement_id"), "requirement_id")
        category = _text(row.get("category"), f"{requirement_id}.category")
        source_text = _text(row.get("source_text"), f"{requirement_id}.source_text")
        shot_ids = row.get("shot_ids")
        if not isinstance(shot_ids, list) or any(
            not isinstance(item, str) or not item for item in shot_ids
        ):
            raise SeedMasterRuntimeError(f"{requirement_id}.shot_ids must be an array")
        result.append(
            {
                "requirement_id": requirement_id,
                "category": category,
                "source_text": source_text,
                "preservation": _text(
                    row.get("preservation"), f"{requirement_id}.preservation"
                ),
                "shot_ids": list(shot_ids),
                "asset_relevance_expected": category in ASSET_RELEVANT_CATEGORIES,
            }
        )
    return result


def build_review_packet(
    *,
    task_dir: Path,
    parsed: dict[str, Any],
    provisional_plan: dict[str, Any],
    catalog: dict[str, Any],
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Freeze the final Prompt and selected assets.json semantic rows."""

    task_dir = task_dir.expanduser().resolve()
    repository_root = (repository_root or REPOSITORY_ROOT).expanduser().resolve()
    media_inputs: list[dict[str, Any]] = []
    plan_media = provisional_plan.get("media_bindings")
    if not isinstance(plan_media, list):
        raise SeedMasterRuntimeError("Provisional plan lacks media_bindings")
    for binding in plan_media:
        if not isinstance(binding, dict):
            raise SeedMasterRuntimeError("Provisional plan has an invalid media binding")
        token = _text(binding.get("provider_token"), "provider token")
        prompt_rows = [
            row for row in parsed["bindings"] if row["provider_token"] == token
        ]
        if not prompt_rows:
            raise SeedMasterRuntimeError(f"{token} has no final Prompt binding")
        expected_namespaces = _prompt_namespaces(prompt_rows)
        source_kind = binding.get("source_kind")
        if source_kind == "asset_catalog":
            namespace = _text(binding.get("namespace"), f"{token} asset namespace")
            if expected_namespaces != [namespace]:
                affected = sorted(set(expected_namespaces + [namespace]))
                raise AssetCompatibilityResolutionError(
                    f"{token} Prompt expects assets {expected_namespaces}, but the execution binding selects assets.json asset {namespace!r}",
                    affected_asset_ids=affected,
                    required_actions=[
                        f"Bind {token} to the exact assets.json asset required by the Prompt instead of {namespace!r}.",
                    ],
                    provider_token=token,
                )
            try:
                semantics = _catalog_semantics(catalog, namespace)
            except SeedMasterRuntimeError as exc:
                raise AssetCompatibilityResolutionError(
                    f"{token} cannot resolve assets.json semantics for {namespace!r}: {exc}",
                    affected_asset_ids=[namespace],
                    required_actions=[
                        f"Create or repair semantic asset {namespace!r} in assets.json, then rerun Route B compatibility review.",
                    ],
                    provider_token=token,
                ) from exc
            body_topology_contract = _require_prompt_body_topology(
                prompt=parsed["prompt"],
                catalog=catalog,
                namespace=namespace,
                provider_role=str(binding.get("provider_role")),
                token=token,
            )
            semantic_authority = {
                "authority_kind": "assets_json",
                "asset_id": namespace,
                "catalog_semantics_sha256": _canonical_sha(semantics),
                "provider_uri_sha256": hashlib.sha256(
                    _text(binding.get("uri"), f"{token} provider URI").encode("utf-8")
                ).hexdigest(),
            }
        else:
            if expected_namespaces != ["continuity"]:
                raise SeedMasterRuntimeError(
                    f"{token} runtime continuity binding contradicts Prompt namespaces {expected_namespaces}"
                )
            semantics = {
                "asset_id": "continuity",
                "asset_type": source_kind,
                "source_segment_id": binding.get("source_segment_id"),
                "source_provider_attempt_id": binding.get(
                    "source_provider_attempt_id"
                ),
                "audio_policy": binding.get("audio_policy"),
            }
            semantic_authority = {
                "authority_kind": "predecessor_continuity_contract",
                "asset_id": "continuity",
                "catalog_semantics_sha256": _canonical_sha(semantics),
                "provider_uri_sha256": None,
            }
            body_topology_contract = None
        media_inputs.append(
            {
                "provider_token": token,
                "provider_role": binding["provider_role"],
                "binding_ids": [row["binding_id"] for row in prompt_rows],
                "prompt_elements": [row["element"] for row in prompt_rows],
                "prompt_element_namespaces": expected_namespaces,
                "shot_scope": [
                    {"binding_id": row["binding_id"], "shots": row["shot_scope"]}
                    for row in prompt_rows
                ],
                "prompt_authorities": [row["authority"] for row in prompt_rows],
                "prompt_forbidden": [row["forbidden"] for row in prompt_rows],
                "catalog_semantics": semantics,
                "body_topology_contract": body_topology_contract,
                "semantic_authority": semantic_authority,
            }
        )
    media_inputs.sort(key=lambda row: token_sort_key(row["provider_token"]))
    return {
        "contract": PACKET_CONTRACT,
        "segment_id": parsed["segment_id"],
        "source_storyboard_sha256": parsed["metadata"]["source_storyboard_sha256"],
        "source_manifest_sha256": parsed["metadata"]["source_manifest_sha256"],
        "source_script_path": (
            task_dir / SCRIPT_DIR_RELATIVE / f"{parsed['segment_id']}.md"
        ).relative_to(task_dir).as_posix(),
        "source_script_sha256": parsed["script_sha256"],
        "final_prompt_sha256": hashlib.sha256(
            parsed["prompt"].encode("utf-8")
        ).hexdigest(),
        "asset_catalog_sha256": sha256_file(repository_root / ASSET_CATALOG_RELATIVE),
        "media_inputs": media_inputs,
        "source_requirements": _owned_requirements(task_dir, parsed),
    }


def packet_path(task_dir: Path, segment_id: str) -> Path:
    return task_dir / PACKET_DIR_RELATIVE / f"{segment_id}.json"


def review_path(task_dir: Path, segment_id: str) -> Path:
    return task_dir / REVIEW_DIR_RELATIVE / f"{segment_id}.json"


def rework_path(task_dir: Path, segment_id: str) -> Path:
    return task_dir / REWORK_DIR_RELATIVE / f"{segment_id}.json"


def write_review_packet(task_dir: Path, packet: dict[str, Any]) -> Path:
    path = packet_path(task_dir, str(packet["segment_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def write_review_draft(
    task_dir: Path, packet: dict[str, Any], *, packet_file: Path
) -> Path:
    """Create a semantic-review skeleton without overwriting a current decision."""

    path = review_path(task_dir, str(packet["segment_id"]))
    packet_sha = sha256_file(packet_file)
    if path.is_file():
        try:
            existing = read_json(path, label="asset compatibility review")
        except SeedMasterRuntimeError:
            existing = {}
        if (
            existing.get("contract") == REVIEW_CONTRACT
            and existing.get("packet_sha256") == packet_sha
            and existing.get("overall_verdict") in {"PASS", "FAIL"}
        ):
            return path
    draft = {
        "contract": REVIEW_CONTRACT,
        "segment_id": packet["segment_id"],
        "packet_sha256": packet_sha,
        "reviewer_role": "virtual_production_prompt_asset_semantic_reviewer",
        "review_scope": "final_seedance_prompt_against_assets_json_semantics",
        "media_reviews": [
            {
                "provider_token": row["provider_token"],
                "catalog_semantics_sha256": row["semantic_authority"][
                    "catalog_semantics_sha256"
                ],
                "inspection_method": (
                    "assets_json_semantic_comparison"
                    if row["semantic_authority"]["authority_kind"] == "assets_json"
                    else "predecessor_continuity_contract_comparison"
                ),
                "required_facts": [],
                "catalog_facts": [],
                "compatibility_class": "REVIEW_REQUIRED",
                "conflict_domains": [],
                "verdict": "REVIEW_REQUIRED",
                "reason": "REVIEW_REQUIRED",
            }
            for row in packet["media_inputs"]
        ],
        "source_requirement_reviews": [
            {
                "requirement_id": row["requirement_id"],
                "asset_relevance": (
                    "relevant" if row["asset_relevance_expected"] else "REVIEW_REQUIRED"
                ),
                "provider_tokens": [],
                "verdict": "REVIEW_REQUIRED",
                "reason": "REVIEW_REQUIRED",
            }
            for row in packet["source_requirements"]
        ],
        "overall_verdict": "REVIEW_REQUIRED",
        "failures": [],
        "rework": {
            "owner_department": "REVIEW_REQUIRED",
            "restart_from": "REVIEW_REQUIRED",
            "affected_asset_ids": [],
            "required_actions": [],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _write_rework(
    *,
    task_dir: Path,
    parsed: dict[str, Any],
    packet: dict[str, Any] | None,
    failures: list[dict[str, Any]],
    affected_asset_ids: list[str],
    required_actions: list[str],
) -> Path:
    path = rework_path(task_dir, parsed["segment_id"])
    current_packet = packet_path(task_dir, parsed["segment_id"])
    current_review = review_path(task_dir, parsed["segment_id"])
    payload = {
        "contract": REWORK_CONTRACT,
        "status": "BLOCKED_ASSET_SEMANTICS_INCOMPATIBLE",
        "source_department": "virtual-production",
        "owner_department": "direct-production-design",
        "earliest_restart": "production-design-plan",
        "segment_id": parsed["segment_id"],
        "source_storyboard_sha256": parsed["metadata"]["source_storyboard_sha256"],
        "source_manifest_sha256": parsed["metadata"]["source_manifest_sha256"],
        "source_script_sha256": parsed["script_sha256"],
        "final_prompt_sha256": hashlib.sha256(
            parsed["prompt"].encode("utf-8")
        ).hexdigest(),
        "asset_catalog_sha256": (
            packet.get("asset_catalog_sha256") if isinstance(packet, dict) else None
        ),
        "compatibility_packet_sha256": (
            sha256_file(current_packet)
            if packet is not None and current_packet.is_file()
            else None
        ),
        "compatibility_review_sha256": (
            sha256_file(current_review)
            if packet is not None and current_review.is_file()
            else None
        ),
        "affected_asset_ids": sorted(set(affected_asset_ids)),
        "failures": failures,
        "required_actions": list(dict.fromkeys(required_actions)),
        "invalidated_downstream": [
            f".pending/virtual-production/seedance-execution-plans/{parsed['segment_id']}.json",
            f".pending/virtual-production/asset-compatibility-reviews/{parsed['segment_id']}.json",
            "affected Route B asset bindings and translation trace after assets.json repair",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def emit_resolution_rework(
    *, task_dir: Path, parsed: dict[str, Any], error: Exception | str
) -> Path:
    if isinstance(error, AssetCompatibilityResolutionError):
        namespaces = sorted(set(error.affected_asset_ids))
        required_actions = error.required_actions
        provider_token = error.provider_token
    else:
        namespaces = sorted(
            {
                str(row["element"]).split(".", 1)[0]
                for row in parsed.get("bindings", [])
                if str(row.get("element", "")).split(".", 1)[0] != "continuity"
            }
        )
        required_actions = [
            "Inspect the final Prompt bindings and the current assets.json semantic rows.",
            "Repair missing or incompatible asset semantics, then rerun Route B compatibility review.",
        ]
        provider_token = None
    return _write_rework(
        task_dir=task_dir,
        parsed=parsed,
        packet=None,
        failures=[
            {
                "failure_id": f"{parsed['segment_id']}-asset-resolution",
                "provider_token": provider_token,
                "asset_id": namespaces[0] if len(namespaces) == 1 else None,
                "conflict_domains": ["other"],
                "reason": str(error),
            }
        ],
        affected_asset_ids=namespaces,
        required_actions=required_actions,
    )


def _validate_media_reviews(
    *, packet: dict[str, Any], review: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    expected_inputs = packet["media_inputs"]
    rows = review.get("media_reviews")
    if not isinstance(rows, list) or len(rows) != len(expected_inputs):
        raise SeedMasterRuntimeError(
            "Compatibility review must cover every assets.json input binding"
        )
    expected_by_token = {row["provider_token"]: row for row in expected_inputs}
    if [row.get("provider_token") for row in rows if isinstance(row, dict)] != [
        row["provider_token"] for row in expected_inputs
    ]:
        raise SeedMasterRuntimeError("Compatibility review order/coverage differs")
    failures: list[dict[str, Any]] = []
    affected: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise SeedMasterRuntimeError("Compatibility review row is invalid")
        token = row["provider_token"]
        expected = expected_by_token[token]
        semantics_sha = expected["semantic_authority"]["catalog_semantics_sha256"]
        if row.get("catalog_semantics_sha256") != semantics_sha:
            raise SeedMasterRuntimeError(
                f"{token} review targets stale assets.json semantics"
            )
        expected_method = (
            "assets_json_semantic_comparison"
            if expected["semantic_authority"]["authority_kind"] == "assets_json"
            else "predecessor_continuity_contract_comparison"
        )
        if row.get("inspection_method") != expected_method:
            raise SeedMasterRuntimeError(
                f"{token} was not compared against its declared semantic authority"
            )
        required = _string_list(row.get("required_facts"), f"{token}.required_facts")
        catalog_facts = _string_list(
            row.get("catalog_facts"), f"{token}.catalog_facts"
        )
        conflicts = _string_list(
            row.get("conflict_domains"),
            f"{token}.conflict_domains",
            allow_empty=True,
        )
        if any(item not in CONFLICT_DOMAINS for item in conflicts):
            raise SeedMasterRuntimeError(f"{token} has an unknown conflict domain")
        verdict = row.get("verdict")
        compatibility_class = row.get("compatibility_class")
        reason = _text(row.get("reason"), f"{token}.reason")
        if verdict == "compatible":
            if compatibility_class not in PASS_CLASSES or conflicts:
                raise SeedMasterRuntimeError(f"{token} compatible verdict is contradictory")
        elif verdict == "incompatible":
            if compatibility_class not in FAIL_CLASSES or not conflicts:
                raise SeedMasterRuntimeError(
                    f"{token} incompatible verdict lacks conflict evidence"
                )
            asset_id = expected["catalog_semantics"].get("asset_id")
            if isinstance(asset_id, str) and asset_id != "continuity":
                affected.append(asset_id)
            failures.append(
                {
                    "failure_id": f"{packet['segment_id']}-{token.removeprefix('@')}",
                    "provider_token": token,
                    "asset_id": asset_id,
                    "prompt_elements": expected["prompt_elements"],
                    "required_facts": required,
                    "assets_json_facts": catalog_facts,
                    "conflict_domains": conflicts,
                    "reason": reason,
                }
            )
        else:
            raise SeedMasterRuntimeError(f"{token} compatibility verdict is invalid")
    return failures, affected


def _validate_requirement_reviews(
    *, packet: dict[str, Any], review: dict[str, Any]
) -> list[dict[str, Any]]:
    expected = packet["source_requirements"]
    rows = review.get("source_requirement_reviews")
    if not isinstance(rows, list) or [
        row.get("requirement_id") for row in rows if isinstance(row, dict)
    ] != [row["requirement_id"] for row in expected]:
        raise SeedMasterRuntimeError(
            "Compatibility review must cover every Prompt-affecting source requirement"
        )
    valid_tokens = {row["provider_token"] for row in packet["media_inputs"]}
    failures: list[dict[str, Any]] = []
    for source, row in zip(expected, rows):
        if not isinstance(row, dict):
            raise SeedMasterRuntimeError("Invalid source requirement review row")
        relevance = row.get("asset_relevance")
        tokens = _string_list(
            row.get("provider_tokens"),
            f"{source['requirement_id']}.provider_tokens",
            allow_empty=True,
        )
        if any(token not in valid_tokens for token in tokens):
            raise SeedMasterRuntimeError(
                f"{source['requirement_id']} names an unknown provider token"
            )
        verdict = row.get("verdict")
        reason = _text(row.get("reason"), f"{source['requirement_id']}.reason")
        if relevance not in {"relevant", "not_relevant"}:
            raise SeedMasterRuntimeError(
                f"{source['requirement_id']} asset_relevance is invalid"
            )
        if source["asset_relevance_expected"] and relevance != "relevant":
            raise SeedMasterRuntimeError(
                f"{source['requirement_id']} category {source['category']} requires an assets.json compatibility decision"
            )
        if relevance == "not_relevant":
            if tokens or verdict != "not_applicable":
                raise SeedMasterRuntimeError(
                    f"{source['requirement_id']} not-relevant verdict is contradictory"
                )
        elif verdict not in {"compatible", "incompatible"}:
            raise SeedMasterRuntimeError(
                f"{source['requirement_id']} relevant verdict is invalid"
            )
        if verdict == "incompatible":
            failures.append(
                {
                    "failure_id": f"{packet['segment_id']}-{source['requirement_id']}",
                    "provider_token": tokens,
                    "asset_id": None,
                    "source_requirement_id": source["requirement_id"],
                    "source_requirement": source["source_text"],
                    "conflict_domains": ["other"],
                    "reason": reason,
                }
            )
    return failures


def validate_compatibility_review(
    *,
    task_dir: Path,
    parsed: dict[str, Any],
    provisional_plan: dict[str, Any],
    catalog: dict[str, Any],
    emit_rework: bool = True,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Require a current semantic PASS over Prompt and assets.json."""

    task_dir = task_dir.expanduser().resolve()
    expected_packet = build_review_packet(
        task_dir=task_dir,
        parsed=parsed,
        provisional_plan=provisional_plan,
        catalog=catalog,
        repository_root=repository_root,
    )
    stored_packet_path = packet_path(task_dir, parsed["segment_id"])
    stored_packet = read_json(stored_packet_path, label="asset compatibility packet")
    if stored_packet != expected_packet:
        raise SeedMasterRuntimeError(
            f"{parsed['segment_id']} compatibility packet is missing or stale"
        )
    stored_review_path = review_path(task_dir, parsed["segment_id"])
    review = read_json(stored_review_path, label="asset compatibility review")
    fixed = {
        "contract": REVIEW_CONTRACT,
        "segment_id": parsed["segment_id"],
        "packet_sha256": sha256_file(stored_packet_path),
        "reviewer_role": "virtual_production_prompt_asset_semantic_reviewer",
        "review_scope": "final_seedance_prompt_against_assets_json_semantics",
    }
    if any(review.get(key) != value for key, value in fixed.items()):
        raise SeedMasterRuntimeError(
            f"{parsed['segment_id']} compatibility review identity is stale"
        )
    media_failures, affected = _validate_media_reviews(
        packet=expected_packet, review=review
    )
    requirement_failures = _validate_requirement_reviews(
        packet=expected_packet, review=review
    )
    failures = media_failures + requirement_failures
    declared_failures = review.get("failures")
    if not isinstance(declared_failures, list):
        raise SeedMasterRuntimeError("Compatibility review failures must be an array")
    overall = review.get("overall_verdict")
    rework = review.get("rework")
    if not isinstance(rework, dict):
        raise SeedMasterRuntimeError("Compatibility review lacks rework routing")
    if overall == "PASS":
        if (
            failures
            or declared_failures
            or rework
            != {
                "owner_department": "none",
                "restart_from": "none",
                "affected_asset_ids": [],
                "required_actions": [],
            }
        ):
            raise SeedMasterRuntimeError(
                f"{parsed['segment_id']} PASS compatibility review is contradictory"
            )
        stale_rework = rework_path(task_dir, parsed["segment_id"])
        if stale_rework.is_file():
            stale_rework.unlink()
    elif overall == "FAIL":
        if not failures or not declared_failures:
            raise SeedMasterRuntimeError(
                f"{parsed['segment_id']} FAIL compatibility review lacks evidence"
            )
        if (
            rework.get("owner_department") != "direct-production-design"
            or rework.get("restart_from") != "production-design-plan"
        ):
            raise SeedMasterRuntimeError(
                f"{parsed['segment_id']} incompatible assets must route to production design"
            )
        declared_assets = _string_list(
            rework.get("affected_asset_ids"),
            "rework.affected_asset_ids",
            allow_empty=True,
        )
        actions = _string_list(
            rework.get("required_actions"), "rework.required_actions"
        )
        affected = sorted(set(affected) | set(declared_assets))
        if emit_rework:
            path = _write_rework(
                task_dir=task_dir,
                parsed=parsed,
                packet=expected_packet,
                failures=failures,
                affected_asset_ids=affected,
                required_actions=actions,
            )
            raise SeedMasterRuntimeError(
                f"{parsed['segment_id']} assets.json semantics are incompatible with the final Prompt; rework request: {path}"
            )
        raise SeedMasterRuntimeError(
            f"{parsed['segment_id']} assets.json semantics are incompatible with the final Prompt"
        )
    else:
        raise SeedMasterRuntimeError("Compatibility review overall_verdict is invalid")

    semantic_fingerprint = _canonical_sha(
        [row["semantic_authority"] for row in expected_packet["media_inputs"]]
    )
    return {
        "contract": RECEIPT_CONTRACT,
        "overall_verdict": "PASS",
        "packet_path": stored_packet_path.relative_to(task_dir).as_posix(),
        "packet_sha256": sha256_file(stored_packet_path),
        "review_path": stored_review_path.relative_to(task_dir).as_posix(),
        "review_sha256": sha256_file(stored_review_path),
        "asset_catalog_sha256": expected_packet["asset_catalog_sha256"],
        "final_prompt_sha256": expected_packet["final_prompt_sha256"],
        "semantic_input_fingerprint": semantic_fingerprint,
    }
