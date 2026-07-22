"""Transport natural-language Seedance prompts and resolve private execution plans.

``segment-NNN.md`` is the exact model-facing Prompt. Deterministic transport
authority lives in a private ``segment-NNN.json`` plan beside the Prompt
collection. Code may
verify that Prompt text exists, hash it, and resolve media; it never parses,
constrains, authors, or repairs Prompt prose.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


SCRIPT_DIR_RELATIVE = Path(".pending/virtual-production/seedance-segment-scripts")
PLAN_DIR_RELATIVE = Path(".pending/virtual-production/seedance-segment-plans")
EXECUTION_PLAN_DIR_RELATIVE = Path(
    ".pending/virtual-production/seedance-execution-plans"
)
STORYBOARD_RELATIVE = Path("previsualize-cinematography/storyboard.md")
CAPABILITY_PROFILE_RELATIVE = Path("virtual-production/seedance-capability-profile.json")

SEGMENT_RE = re.compile(r"^segment-([0-9]{3,})$")
SCRIPT_RE = re.compile(r"^segment-([0-9]{3,})\.md$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^@(Image|Video|Audio)([1-9][0-9]*)$")
TOKEN_SCAN_RE = re.compile(r"@(Image|Video|Audio)([1-9][0-9]*)")
SHOT_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]+)?Shot[ \t]+([1-9][0-9]*)[ \t]*:[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)

REQUIRED_PLAN_FIELDS = {
    "contract",
    "segment_id",
    "source_storyboard_sha256",
    "scene_ids",
    "target_duration",
    "shot_count",
    "operation",
    "shooting_plan_status",
    "schedule_mode",
    "planned_wave",
    "depends_on_segment_ids",
    "dependency_reason",
    "predecessor_review_required",
    "required_predecessor_evidence",
    "successor_recompile_required",
    "fallback_operation_and_story_cost",
    "seam_class",
    "seam_resynthesis_allowed",
    "seam_story_reason",
    "editorial_intent",
    "reference_video_scope",
    "reference_video_audio",
    "camera_ensemble_color_resynthesis_allowed",
    "continuity",
    "bindings",
    "dialogue_cues",
    "editable_hold_seconds",
    "final_visible_state",
    "final_sound_state",
}

ROLE_FOR_TOKEN_KIND = {
    "Image": "reference_image",
    "Video": "reference_video",
    "Audio": "reference_audio",
}
ALLOWED_OPERATIONS = {"multimodal_reference", "video_extension", "text_to_video"}
ALLOWED_EVIDENCE = {
    "none",
    "approved_complete_predecessor",
    "approved_provider_last_frame",
}
CONTINUITY_FIELDS = {
    "location_state_chain",
    "relationship",
    "state_source_segment_id",
    "world_binding_ids",
    "temporal_binding_ids",
    "embedded_npc_asset_ids",
    "authorized_independent_performer_asset_ids",
    "population_lock_en",
}
LOCATION_RELATIONSHIPS = {
    "independent",
    "adjacent_continuation",
    "nonadjacent_revisit",
    "reset_with_reason",
}


class SeedMasterRuntimeError(RuntimeError):
    """Raised when a natural Prompt or its private plan is invalid."""


def read_json(path: Path, *, label: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SeedMasterRuntimeError(f"Missing or invalid {label or 'JSON'}: {path}") from exc
    if not isinstance(value, dict):
        raise SeedMasterRuntimeError(f"{label or 'JSON'} must contain one object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise SeedMasterRuntimeError(f"Cannot hash required file: {path}") from exc


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SeedMasterRuntimeError(f"{label} must be a non-empty string")
    return value.strip()


def _unique_string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise SeedMasterRuntimeError(f"{label} must be a unique string array")
    return [item.strip() for item in value]


def _target_duration(value: Any, segment_id: str) -> int:
    if isinstance(value, bool):
        raise SeedMasterRuntimeError(f"{segment_id} target duration must be 4-15 seconds")
    if isinstance(value, int):
        duration = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+s", value.strip()):
        duration = int(value.strip()[:-1])
    else:
        raise SeedMasterRuntimeError(f"{segment_id} target duration must be an integer or Ns")
    if not 4 <= duration <= 15:
        raise SeedMasterRuntimeError(f"{segment_id} target duration must be 4-15 seconds")
    return duration


def _private_plan_path(path: Path) -> Path:
    if path.parent.name == "seedance-segment-scripts":
        return path.parent.parent / "seedance-segment-plans" / f"{path.stem}.json"
    return path.with_suffix(".plan.json")


def _validate_prompt(text: str, path: Path, plan: dict[str, Any]) -> str:
    """Validate authored binding placement without constraining creative prose."""

    prompt = text.strip()
    if not prompt:
        raise SeedMasterRuntimeError(f"{path.name} Seedance Prompt must not be empty")

    shot_matches = list(SHOT_HEADING_RE.finditer(prompt))
    shot_sections: dict[int, str] = {}
    for index, match in enumerate(shot_matches):
        shot_number = int(match.group(1))
        if shot_number in shot_sections:
            raise SeedMasterRuntimeError(
                f"{path.name} repeats Shot {shot_number}, so dialogue ownership is ambiguous"
            )
        end = shot_matches[index + 1].start() if index + 1 < len(shot_matches) else len(prompt)
        shot_sections[shot_number] = prompt[match.end() : end].strip()

    prompt_tokens = sorted(
        {match.group(0) for match in TOKEN_SCAN_RE.finditer(prompt)},
        key=token_sort_key,
    )
    plan_tokens = sorted(
        {item["provider_token"] for item in plan["bindings"]},
        key=token_sort_key,
    )
    if prompt_tokens != plan_tokens:
        raise SeedMasterRuntimeError(
            f"{path.name} provider tokens differ from the private plan"
        )
    pre_shot = prompt[: shot_matches[0].start()] if shot_matches else prompt
    if any(token not in pre_shot for token in plan_tokens):
        raise SeedMasterRuntimeError(
            f"{path.name} must introduce every provider token before its first Shot section"
        )

    population_lock = plan["continuity"]["population_lock_en"]
    if prompt.count(population_lock) != 1:
        raise SeedMasterRuntimeError(
            f"{path.name} must contain its population lock exactly once"
        )

    for cue in plan["dialogue_cues"]:
        if not isinstance(cue, dict):
            raise SeedMasterRuntimeError(f"{path.name} has an invalid dialogue cue")
        speaker = _nonempty_string(cue.get("speaker_name"), "dialogue speaker_name")
        exact_text = _nonempty_string(cue.get("exact_text"), "dialogue exact_text")
        shot_number = cue.get("shot_number")
        if not isinstance(shot_number, int) or shot_number not in shot_sections:
            raise SeedMasterRuntimeError(
                f"{path.name} dialogue cue has no matching Shot section"
            )
        section = shot_sections[shot_number]
        if f'"{exact_text}"' not in section or speaker not in section:
            raise SeedMasterRuntimeError(
                f"{path.name} must place exact quoted dialogue beside its readable speaker "
                f"inside Shot {shot_number}"
            )
    return prompt


def _parse_bindings(value: Any, path: Path, shot_count: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise SeedMasterRuntimeError(f"{path.name} private bindings must be an array")
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            raise SeedMasterRuntimeError(f"{path.name} has an invalid private binding")
        binding_id = raw.get("binding_id")
        token = raw.get("provider_token")
        role = raw.get("provider_role")
        namespace = raw.get("asset_namespace")
        subject = raw.get("readable_subject")
        purpose = raw.get("purpose")
        scope = raw.get("shot_scope")
        forbidden = raw.get("forbidden_inheritance")
        match = TOKEN_RE.fullmatch(str(token or ""))
        if (
            binding_id != f"B{index:02d}"
            or binding_id in seen_ids
            or match is None
            or role != ROLE_FOR_TOKEN_KIND[match.group(1)]
            or not isinstance(scope, list)
            or not scope
            or any(not isinstance(item, int) or not 1 <= item <= shot_count for item in scope)
        ):
            raise SeedMasterRuntimeError(f"{path.name} private binding {index} is invalid")
        for label, item in (
            ("asset_namespace", namespace),
            ("readable_subject", subject),
            ("purpose", purpose),
            ("forbidden_inheritance", forbidden),
        ):
            _nonempty_string(item, f"{path.name} binding {index} {label}")
        seen_ids.add(binding_id)
        result.append(
            {
                "binding_id": binding_id,
                "provider_token": token,
                "provider_role": role,
                "asset_namespace": namespace,
                "readable_subject": subject,
                "purpose": purpose,
                "shot_scope": [f"Shot {item}" for item in scope],
                "element": f"{namespace}.{purpose}",
                "authority": purpose,
                "forbidden": forbidden,
            }
        )
    _validate_token_sequence(result, path)
    return result


def _validate_token_sequence(bindings: list[dict[str, Any]], path: Path) -> None:
    tokens = list(dict.fromkeys(item["provider_token"] for item in bindings))
    for kind in ("Image", "Video", "Audio"):
        numbers = sorted(
            int(match.group(2))
            for token in tokens
            if (match := TOKEN_RE.fullmatch(token)) and match.group(1) == kind
        )
        if numbers != list(range(1, len(numbers) + 1)):
            raise SeedMasterRuntimeError(f"{path.name} @{kind} tokens must be contiguous from 1")


def _validate_shooting_plan(plan: dict[str, Any], segment_id: str) -> None:
    if plan["operation"] not in ALLOWED_OPERATIONS:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported operation")
    evidence = plan["required_predecessor_evidence"]
    if evidence not in ALLOWED_EVIDENCE:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported predecessor evidence")
    dependencies = _unique_string_list(plan["depends_on_segment_ids"], f"{segment_id} dependencies")
    if any(not SEGMENT_RE.fullmatch(item) for item in dependencies):
        raise SeedMasterRuntimeError(f"{segment_id} has an invalid dependency")
    schedule = plan["schedule_mode"]
    if schedule == "parallel":
        if dependencies or plan["planned_wave"] != 0 or plan["predecessor_review_required"] is not False or evidence != "none" or plan["shooting_plan_status"] != "planned":
            raise SeedMasterRuntimeError(f"{segment_id} parallel plan is contradictory")
    elif schedule == "serial_after_predecessor_review":
        if len(dependencies) != 1 or not isinstance(plan["planned_wave"], int) or plan["planned_wave"] < 1 or plan["predecessor_review_required"] is not True or plan["successor_recompile_required"] is not True or plan["shooting_plan_status"] != "observed_adapted" or evidence == "none":
            raise SeedMasterRuntimeError(f"{segment_id} serial plan is contradictory")
    else:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported schedule mode")
    if plan["operation"] == "video_extension" and not (
        evidence == "approved_complete_predecessor"
        and plan["reference_video_scope"] == "full_predecessor_for_extension"
        and plan["reference_video_audio"] == "preserved_for_extension"
        and plan["seam_class"] == "continuous_extension"
    ):
        raise SeedMasterRuntimeError(f"{segment_id} video-extension plan is contradictory")
    if evidence == "approved_provider_last_frame" and not (
        plan["operation"] == "multimodal_reference"
        and schedule == "serial_after_predecessor_review"
        and plan["reference_video_scope"] == "none"
        and plan["reference_video_audio"] == "none"
    ):
        raise SeedMasterRuntimeError(f"{segment_id} soft last-frame plan is contradictory")


def _validate_continuity_plan(
    value: Any, *, segment_id: str, bindings: list[dict[str, Any]]
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CONTINUITY_FIELDS:
        raise SeedMasterRuntimeError(
            f"{segment_id} continuity must use the exact current fields"
        )
    chain = _nonempty_string(
        value["location_state_chain"], f"{segment_id} location_state_chain"
    )
    relationship = value["relationship"]
    if relationship not in LOCATION_RELATIONSHIPS:
        raise SeedMasterRuntimeError(f"{segment_id} has invalid location relationship")
    source = value["state_source_segment_id"]
    if source != "none" and (
        not isinstance(source, str)
        or not SEGMENT_RE.fullmatch(source)
        or source == segment_id
    ):
        raise SeedMasterRuntimeError(f"{segment_id} has invalid location state source")
    world_ids = _unique_string_list(
        value["world_binding_ids"], f"{segment_id} world_binding_ids", allow_empty=False
    )
    temporal_ids = _unique_string_list(
        value["temporal_binding_ids"], f"{segment_id} temporal_binding_ids"
    )
    if set(world_ids) & set(temporal_ids):
        raise SeedMasterRuntimeError(
            f"{segment_id} world and temporal binding responsibilities overlap"
        )
    binding_ids = {item["binding_id"] for item in bindings}
    unknown = (set(world_ids) | set(temporal_ids)) - binding_ids
    if unknown:
        raise SeedMasterRuntimeError(
            f"{segment_id} continuity names unknown bindings: {sorted(unknown)}"
        )
    embedded = _unique_string_list(
        value["embedded_npc_asset_ids"],
        f"{segment_id} embedded_npc_asset_ids",
    )
    independent = _unique_string_list(
        value["authorized_independent_performer_asset_ids"],
        f"{segment_id} authorized_independent_performer_asset_ids",
    )
    if set(embedded) & set(independent):
        raise SeedMasterRuntimeError(
            f"{segment_id} embeds and independently directs the same role"
        )
    population_lock = _nonempty_string(
        value["population_lock_en"], f"{segment_id} population_lock_en"
    )
    if relationship in {"independent", "reset_with_reason"}:
        if source != "none" or temporal_ids:
            raise SeedMasterRuntimeError(
                f"{segment_id} independent/reset state cannot inherit temporal evidence"
            )
    elif source == "none" or not temporal_ids:
        raise SeedMasterRuntimeError(
            f"{segment_id} continuation/revisit requires a state source and temporal evidence"
        )
    return {
        "location_state_chain": chain,
        "relationship": relationship,
        "state_source_segment_id": source,
        "world_binding_ids": world_ids,
        "temporal_binding_ids": temporal_ids,
        "embedded_npc_asset_ids": embedded,
        "authorized_independent_performer_asset_ids": independent,
        "population_lock_en": population_lock,
    }


def parse_segment_script(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise SeedMasterRuntimeError(f"Unreadable Seedance Prompt: {path}") from exc
    filename_match = SCRIPT_RE.fullmatch(path.name)
    if filename_match is None:
        raise SeedMasterRuntimeError(f"Invalid Seedance Prompt filename: {path.name}")
    segment_id = f"segment-{int(filename_match.group(1)):03d}"
    plan_path = _private_plan_path(path)
    plan = read_json(plan_path, label="private Seedance Segment plan")
    missing = sorted(REQUIRED_PLAN_FIELDS - set(plan))
    if missing:
        raise SeedMasterRuntimeError(f"{plan_path.name} is missing: {', '.join(missing)}")
    if plan.get("contract") != "seedance-natural-language-plan-v1" or plan.get("segment_id") != segment_id:
        raise SeedMasterRuntimeError(f"{plan_path.name} has invalid Segment identity")
    if not HASH_RE.fullmatch(str(plan.get("source_storyboard_sha256") or "")):
        raise SeedMasterRuntimeError(f"{plan_path.name} has invalid Storyboard hash")
    _unique_string_list(plan["scene_ids"], f"{segment_id} scene_ids", allow_empty=False)
    _validate_shooting_plan(plan, segment_id)
    duration = _target_duration(plan["target_duration"], segment_id)
    if isinstance(plan["shot_count"], bool) or not isinstance(plan["shot_count"], int) or plan["shot_count"] < 1:
        raise SeedMasterRuntimeError(f"{plan_path.name} shot_count must be positive")
    bindings = _parse_bindings(plan["bindings"], plan_path, plan["shot_count"])
    continuity = _validate_continuity_plan(
        plan["continuity"], segment_id=segment_id, bindings=bindings
    )
    normalized_plan = {**plan, "bindings": bindings, "continuity": continuity}
    prompt = _validate_prompt(text, path, normalized_plan)
    return {
        "segment_id": segment_id,
        "number": int(filename_match.group(1)),
        "path": path,
        "plan_path": plan_path,
        "text": text,
        "script_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "private_plan_sha256": sha256_file(plan_path),
        "metadata": normalized_plan,
        "duration": duration,
        "prompt": prompt,
        "bindings": bindings,
    }


def token_sort_key(token: str) -> tuple[int, int]:
    match = TOKEN_RE.fullmatch(token)
    if not match:
        raise SeedMasterRuntimeError(f"Invalid provider token: {token}")
    return ({"Image": 0, "Video": 1, "Audio": 2}[match.group(1)], int(match.group(2)))


def _asset_namespace(bindings: list[dict[str, Any]], token: str) -> str:
    namespaces = {item["asset_namespace"] for item in bindings if item["provider_token"] == token}
    if len(namespaces) != 1:
        raise SeedMasterRuntimeError(f"{token} must resolve to one private asset namespace")
    return next(iter(namespaces))


def _require_http_uri(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise SeedMasterRuntimeError(f"{label} has no concrete HTTP(S) URI")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise SeedMasterRuntimeError(f"{label} has no concrete HTTP(S) URI")
    return value


def _resolve_roster_visual(namespace: str, assets: dict[str, Any]) -> tuple[str, str, str] | None:
    if "--" not in namespace:
        return None
    roster_id, member_type_id = namespace.split("--", 1)
    roster = assets.get(roster_id)
    if not isinstance(roster, dict) or roster.get("type") != "ensemble_roster":
        return None
    matches = [item for item in roster.get("members", []) if isinstance(item, dict) and item.get("member_type_id") == member_type_id]
    if len(matches) != 1:
        raise SeedMasterRuntimeError(f"Ambiguous ensemble asset namespace: {namespace}")
    media = matches[0].get("roster_asset")
    uri = media.get("uri") if isinstance(media, dict) else None
    return namespace, "ensemble_roster_member", _require_http_uri(uri, namespace)


def resolve_catalog_media(*, namespace: str, provider_role: str, catalog: dict[str, Any]) -> dict[str, Any]:
    assets = catalog.get("assets") if isinstance(catalog, dict) else None
    if not isinstance(assets, dict):
        raise SeedMasterRuntimeError("Asset catalog has no assets object")
    if provider_role == "reference_image":
        roster = _resolve_roster_visual(namespace, assets)
        if roster is not None:
            asset_id, asset_type, uri = roster
            return {"asset_id": asset_id, "asset_type": asset_type, "uri": uri}
        asset = assets.get(namespace)
        if not isinstance(asset, dict) or asset.get("type") in {"sound", "ensemble_roster"}:
            raise SeedMasterRuntimeError(f"Image token cannot resolve asset {namespace!r}")
        visual = asset.get("visual")
        uri = visual.get("uri") if isinstance(visual, dict) else None
        return {"asset_id": namespace, "asset_type": str(asset.get("type")), "uri": _require_http_uri(uri, namespace)}
    if provider_role == "reference_audio":
        asset = assets.get(namespace)
        if not isinstance(asset, dict):
            raise SeedMasterRuntimeError(f"Audio token cannot resolve asset {namespace!r}")
        if asset.get("type") == "character":
            voice = asset.get("voice")
            reference = voice.get("reference") if isinstance(voice, dict) else None
            uri = reference.get("uri") if isinstance(reference, dict) else None
            asset_type = "character_voice"
        elif asset.get("type") == "sound":
            audio = asset.get("audio")
            uri = audio.get("uri") if isinstance(audio, dict) else None
            asset_type = "sound"
        else:
            raise SeedMasterRuntimeError(f"Audio token {namespace!r} is not a voice/sound asset")
        return {"asset_id": namespace, "asset_type": asset_type, "uri": _require_http_uri(uri, namespace)}
    raise SeedMasterRuntimeError(f"Catalog cannot resolve provider role {provider_role}")


def _source_attempt(task_dir: Path, source_segment_id: str) -> str:
    source_root = task_dir / ".pending/virtual-production/generation-segments" / source_segment_id
    record = read_json(source_root / "production-record.json", label="predecessor production record")
    artifacts = read_json(source_root / "artifacts.json", label="predecessor artifacts")
    attempt_id = record.get("provider_attempt_id")
    source_script = task_dir / SCRIPT_DIR_RELATIVE / f"{source_segment_id}.md"
    source_plan = task_dir / EXECUTION_PLAN_DIR_RELATIVE / f"{source_segment_id}.json"
    if (
        record.get("status") != "GENERATED"
        or record.get("segment_id") != source_segment_id
        or not isinstance(attempt_id, str)
        or artifacts.get("provider_attempt_id") != attempt_id
        or record.get("seed_master_script_sha256") != sha256_file(source_script)
        or record.get("seedance_execution_plan_sha256") != sha256_file(source_plan)
        or not (source_root / "video.mp4").is_file()
        or not (source_root / "last-frame.png").is_file()
    ):
        raise SeedMasterRuntimeError(f"Dependent Prompt requires the current generated attempt for {source_segment_id}")
    return attempt_id


def _runtime_binding(*, token: str, role: str, namespace: str, metadata: dict[str, Any], task_dir: Path) -> dict[str, Any]:
    dependencies = metadata["depends_on_segment_ids"]
    if len(dependencies) != 1:
        raise SeedMasterRuntimeError(f"{token} continuity media requires one predecessor")
    source_segment_id = dependencies[0]
    attempt_id = _source_attempt(task_dir, source_segment_id)
    evidence = metadata["required_predecessor_evidence"]
    if role == "reference_video" and evidence == "approved_complete_predecessor":
        source_kind, audio_policy = "complete_predecessor_video", "preserved"
    elif role == "reference_image" and evidence == "approved_provider_last_frame":
        source_kind, audio_policy = "provider_last_frame", "none"
    else:
        raise SeedMasterRuntimeError(f"{token} is not authorized by the private shooting plan")
    return {
        "provider_token": token,
        "provider_role": role,
        "source_kind": source_kind,
        "source_segment_id": source_segment_id,
        "source_provider_attempt_id": attempt_id,
        "namespace": namespace,
        "audio_policy": audio_policy,
    }


def _validate_continuity_bindings(
    *, parsed: dict[str, Any], catalog: dict[str, Any], media_bindings: list[dict[str, Any]]
) -> None:
    segment_id = parsed["segment_id"]
    metadata = parsed["metadata"]
    continuity = metadata["continuity"]
    assets = catalog.get("assets") if isinstance(catalog, dict) else None
    if not isinstance(assets, dict):
        raise SeedMasterRuntimeError("Asset catalog has no assets object")
    binding_by_id = {item["binding_id"]: item for item in parsed["bindings"]}
    world_rows = [binding_by_id[item] for item in continuity["world_binding_ids"]]
    location_rows = [
        item
        for item in world_rows
        if isinstance(assets.get(item["asset_namespace"]), dict)
        and assets[item["asset_namespace"]].get("type") == "location_master"
    ]
    if len(world_rows) != 1 or len(location_rows) != 1:
        raise SeedMasterRuntimeError(
            f"{segment_id} world evidence must be exactly one Location master binding"
        )
    location_binding = location_rows[0]
    if location_binding["provider_role"] != "reference_image":
        raise SeedMasterRuntimeError(
            f"{segment_id} Location master must be a reference image"
        )
    expected_scope = [f"Shot {index}" for index in range(1, metadata["shot_count"] + 1)]
    if location_binding["shot_scope"] != expected_scope:
        raise SeedMasterRuntimeError(
            f"{segment_id} Location master must remain authoritative in every Shot"
        )
    location = assets[location_binding["asset_namespace"]]
    for field, continuity_field in (
        ("embedded_npc_asset_ids", "embedded_npc_asset_ids"),
        (
            "independent_performer_asset_ids",
            "authorized_independent_performer_asset_ids",
        ),
    ):
        catalog_ids = location.get(field)
        if not isinstance(catalog_ids, list):
            raise SeedMasterRuntimeError(
                f"{segment_id} Location master lacks {field} authority"
            )
        authored_ids = continuity[continuity_field]
        if field == "embedded_npc_asset_ids" and authored_ids != catalog_ids:
            raise SeedMasterRuntimeError(
                f"{segment_id} embedded population differs from the Location master"
            )
        if field == "independent_performer_asset_ids" and not set(authored_ids).issubset(
            catalog_ids
        ):
            raise SeedMasterRuntimeError(
                f"{segment_id} authorizes a performer outside the Location treatment"
            )
    runtime_binding_ids = {
        binding_id
        for item in media_bindings
        if item["source_kind"] != "asset_catalog"
        for binding_id in item["binding_ids"]
    }
    if runtime_binding_ids != set(continuity["temporal_binding_ids"]):
        raise SeedMasterRuntimeError(
            f"{segment_id} runtime predecessor media differs from temporal evidence"
        )


def build_execution_plan(*, task_dir: Path, parsed: dict[str, Any], catalog: dict[str, Any], capability_profile: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    metadata = parsed["metadata"]
    token_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in parsed["bindings"]:
        token_rows[binding["provider_token"]].append(binding)
    media_bindings: list[dict[str, Any]] = []
    for token in sorted(token_rows, key=token_sort_key):
        rows = token_rows[token]
        roles = {item["provider_role"] for item in rows}
        if len(roles) != 1:
            raise SeedMasterRuntimeError(f"{token} is assigned more than one provider role")
        role = next(iter(roles))
        namespace = _asset_namespace(parsed["bindings"], token)
        if role == "reference_video" or namespace == "continuity":
            media = _runtime_binding(token=token, role=role, namespace=namespace, metadata=metadata, task_dir=task_dir)
        else:
            resolved = resolve_catalog_media(namespace=namespace, provider_role=role, catalog=catalog)
            media = {"provider_token": token, "provider_role": role, "source_kind": "asset_catalog", "namespace": namespace, **resolved}
        media["binding_ids"] = [item["binding_id"] for item in rows]
        media_bindings.append(media)

    evidence = metadata["required_predecessor_evidence"]
    expected_runtime = {
        "none": set(),
        "approved_complete_predecessor": {"complete_predecessor_video"},
        "approved_provider_last_frame": {"provider_last_frame"},
    }[evidence]
    actual_runtime = {item["source_kind"] for item in media_bindings} - {"asset_catalog"}
    if actual_runtime != expected_runtime:
        raise SeedMasterRuntimeError(f"{parsed['segment_id']} reference tokens do not match predecessor evidence")
    _validate_continuity_bindings(
        parsed=parsed, catalog=catalog, media_bindings=media_bindings
    )
    if capability_profile.get("contract") != "seedance-capability-profile" or capability_profile.get("profile_status") != "VERIFIED":
        raise SeedMasterRuntimeError("Seedance capability profile is not verified")
    model_id = _nonempty_string(capability_profile.get("model_id"), "Seedance model_id")
    task_input = task.get("input")
    if not isinstance(task_input, dict):
        raise SeedMasterRuntimeError("task.json input must be an object")
    resolution = _nonempty_string(task_input.get("resolution"), "task input resolution").lower()
    ratio = _nonempty_string(task_input.get("aspect_ratio"), "task input aspect_ratio")
    counts = {role: sum(item["provider_role"] == role for item in media_bindings) for role in ("reference_image", "reference_video", "reference_audio")}
    capabilities = capability_profile.get("provider_capabilities")
    if not isinstance(capabilities, dict):
        raise SeedMasterRuntimeError("Seedance capability profile lacks provider capabilities")
    limits = {
        "reference_image": capabilities.get("maximum_reference_images"),
        "reference_video": capabilities.get("maximum_reference_videos"),
        "reference_audio": capabilities.get("maximum_reference_audios"),
    }
    for role, count in counts.items():
        limit = limits[role]
        if isinstance(limit, bool) or not isinstance(limit, int) or count > limit:
            raise SeedMasterRuntimeError(f"{parsed['segment_id']} exceeds the verified {role} limit")
    return {
        "contract": "seedance-segment-execution-plan-v2",
        "segment_id": parsed["segment_id"],
        "source_segment_script": parsed["path"].relative_to(task_dir).as_posix(),
        "source_script_sha256": parsed["script_sha256"],
        "source_private_plan_sha256": parsed["private_plan_sha256"],
        "source_storyboard_sha256": metadata["source_storyboard_sha256"],
        "continuity": metadata["continuity"],
        "shooting_plan": {field: metadata[field] for field in (
            "shooting_plan_status", "schedule_mode", "planned_wave", "depends_on_segment_ids",
            "dependency_reason", "predecessor_review_required", "required_predecessor_evidence",
            "successor_recompile_required", "fallback_operation_and_story_cost", "operation",
            "seam_class", "seam_resynthesis_allowed", "seam_story_reason", "editorial_intent",
            "reference_video_scope", "reference_video_audio", "camera_ensemble_color_resynthesis_allowed",
        )},
        "seedance_parameters": {
            "model": model_id,
            "duration": parsed["duration"],
            "resolution": resolution,
            "ratio": ratio,
            "generate_audio": True,
            "watermark": False,
            "return_last_frame": True,
            "execution_expires_after": 172800,
            "priority": 0,
        },
        "media_bindings": media_bindings,
        "media_counts": counts,
    }


def validate_source_identity(task_dir: Path, parsed: dict[str, Any]) -> None:
    if sha256_file(task_dir / STORYBOARD_RELATIVE) != parsed["metadata"]["source_storyboard_sha256"]:
        raise SeedMasterRuntimeError(f"{parsed['segment_id']} Storyboard hash is stale")


def load_execution_plan(task_dir: Path, segment_id: str) -> dict[str, Any]:
    if not SEGMENT_RE.fullmatch(segment_id):
        raise SeedMasterRuntimeError(f"Invalid Segment ID: {segment_id}")
    path = task_dir / EXECUTION_PLAN_DIR_RELATIVE / f"{segment_id}.json"
    plan = read_json(path, label="Seedance execution plan")
    if plan.get("contract") != "seedance-segment-execution-plan-v2" or plan.get("segment_id") != segment_id:
        raise SeedMasterRuntimeError(f"Invalid Seedance execution plan: {path}")
    return plan


def storyboard_segment_rows(task_dir: Path) -> list[dict[str, Any]]:
    plan_root = task_dir / PLAN_DIR_RELATIVE
    paths = sorted(plan_root.glob("segment-*.json"))
    if not paths:
        raise SeedMasterRuntimeError("No private Seedance Segment plans are available")
    rows: list[dict[str, Any]] = []
    for path in paths:
        row = read_json(path, label="private Seedance Segment plan")
        segment_id = row.get("segment_id")
        if row.get("contract") != "seedance-natural-language-plan-v1" or not isinstance(segment_id, str) or not SEGMENT_RE.fullmatch(segment_id) or path.name != f"{segment_id}.json":
            raise SeedMasterRuntimeError(f"Invalid private Segment plan: {path}")
        _unique_string_list(row.get("scene_ids"), f"{segment_id} scene_ids", allow_empty=False)
        rows.append(row)
    expected = [f"segment-{index:03d}" for index in range(1, len(rows) + 1)]
    if [row["segment_id"] for row in rows] != expected:
        raise SeedMasterRuntimeError("Private Segment plans must be consecutive from segment-001")
    _validate_location_state_chains(rows)
    _validate_same_scene_serial(rows)
    return rows


def _validate_location_state_chains(rows: list[dict[str, Any]]) -> None:
    latest_by_chain: dict[str, str] = {}
    for index, row in enumerate(rows):
        segment_id = row["segment_id"]
        continuity = row.get("continuity")
        if not isinstance(continuity, dict):
            raise SeedMasterRuntimeError(f"{segment_id} lacks continuity authority")
        chain = continuity.get("location_state_chain")
        relationship = continuity.get("relationship")
        source = continuity.get("state_source_segment_id")
        if not isinstance(chain, str) or not chain.strip() or relationship not in LOCATION_RELATIONSHIPS:
            raise SeedMasterRuntimeError(f"{segment_id} has invalid continuity authority")
        previous_in_chain = latest_by_chain.get(chain)
        previous_global = rows[index - 1]["segment_id"] if index else None
        if previous_in_chain is None:
            if relationship not in {"independent", "reset_with_reason"} or source != "none":
                raise SeedMasterRuntimeError(
                    f"{segment_id} must originate location state chain {chain!r}"
                )
        elif relationship == "independent":
            raise SeedMasterRuntimeError(
                f"{segment_id} revisits location state chain {chain!r} as independent"
            )
        elif relationship in {"adjacent_continuation", "nonadjacent_revisit"}:
            if source != previous_in_chain:
                raise SeedMasterRuntimeError(
                    f"{segment_id} must source the latest state in chain {chain!r}"
                )
            if source not in row.get("depends_on_segment_ids", []):
                raise SeedMasterRuntimeError(
                    f"{segment_id} dependency plan omits location state source {source}"
                )
            if relationship == "adjacent_continuation" and source != previous_global:
                raise SeedMasterRuntimeError(f"{segment_id} is not adjacent to its state source")
            if relationship == "nonadjacent_revisit" and source == previous_global:
                raise SeedMasterRuntimeError(f"{segment_id} state source is adjacent, not a revisit")
        latest_by_chain[chain] = segment_id


def _validate_same_scene_serial(rows: list[dict[str, Any]]) -> None:
    for predecessor, successor in zip(rows, rows[1:]):
        shared = sorted(set(predecessor["scene_ids"]) & set(successor["scene_ids"]))
        if not shared:
            continue
        predecessor_wave = predecessor.get("planned_wave")
        if not (
            successor.get("schedule_mode") == "serial_after_predecessor_review"
            and successor.get("depends_on_segment_ids") == [predecessor["segment_id"]]
            and successor.get("planned_wave") == (predecessor_wave + 1 if isinstance(predecessor_wave, int) else None)
            and successor.get("predecessor_review_required") is True
            and successor.get("successor_recompile_required") is True
        ):
            raise SeedMasterRuntimeError(f"{successor['segment_id']} shares a Scene with {predecessor['segment_id']} and must directly depend on it")
        soft = (
            successor.get("operation") == "multimodal_reference"
            and successor.get("required_predecessor_evidence") == "approved_provider_last_frame"
            and successor.get("reference_video_scope") == "none"
            and successor.get("reference_video_audio") == "none"
        )
        extension = (
            successor.get("operation") == "video_extension"
            and successor.get("required_predecessor_evidence") == "approved_complete_predecessor"
            and successor.get("reference_video_scope") == "full_predecessor_for_extension"
            and successor.get("reference_video_audio") == "preserved_for_extension"
        )
        if not (soft or extension):
            raise SeedMasterRuntimeError(f"{successor['segment_id']} must use soft last-frame continuity or complete predecessor video extension")
