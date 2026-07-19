"""Parse Seed Master Route B scripts and materialize provider execution values.

Seed Master owns every creative word in ``segment-NNN.md``.  This module owns the
strict, non-creative boundary between those scripts, the production-design asset
catalog, and the Seedance API request.  Literal ``@ImageN/@VideoN/@AudioN`` tokens
remain unchanged in the Prompt; their concrete URLs are carried in a separate
execution plan.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as exc:  # pragma: no cover - deployment dependency guard
    raise RuntimeError("PyYAML is required to read Seed Master Segment metadata") from exc


SCRIPT_DIR_RELATIVE = Path(
    ".pending/virtual-production/seedance-segment-scripts"
)
EXECUTION_PLAN_DIR_RELATIVE = Path(
    ".pending/virtual-production/seedance-execution-plans"
)
STORYBOARD_RELATIVE = Path("previsualize-cinematography/storyboard.md")
COMPILE_MANIFEST_RELATIVE = Path(
    "previsualize-cinematography/storyboard-compile-manifest.json"
)
TRACE_RELATIVE = Path(
    ".pending/virtual-production/storyboard-to-prompt-trace.json"
)
CAPABILITY_PROFILE_RELATIVE = Path(
    "virtual-production/seedance-capability-profile.json"
)

SEGMENT_RE = re.compile(r"^segment-([0-9]{3,})$")
SCRIPT_RE = re.compile(r"^segment-([0-9]{3,})\.md$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^@(Image|Video|Audio)([1-9][0-9]*)$")
HEADER_RE = re.compile(
    r"\A#\s+(segment-[0-9]{3,})\s+[^\n]*\n\s*```yaml\n(.*?)\n```\s*\n",
    re.DOTALL,
)
SHOT_RE = re.compile(
    r"^### Shot ([1-9][0-9]*) — shot_id=([^|\n]+) \| "
    r"location_id=([^|\n]+) \| camera_id=([^|\n]+) \| panel_id=([^\n]+)$",
    re.MULTILINE,
)
MANIFEST_ROW_RE = re.compile(
    r"^- (B[0-9]{2,}) \| (@(?:Image|Video|Audio)[1-9][0-9]*) \| "
    r"provider_role=(reference_(?:image|video|audio)) \| element=([^|\n]+) \| "
    r"shot_scope=([^|\n]+) \| authority=([^|\n]+) \| forbidden=([^\n]+)$",
    re.MULTILINE,
)
PRESENTATION_FIREWALL = (
    "Visual style, cinematography, lighting, production design, and rendering are "
    "presentation-only; preserve every approved narrative fact, participant, visible "
    "count, exact dialogue, action, entrance/exit, causality, consequence, and required "
    "result state."
)
ACCEPTANCE_FIREWALL = (
    "Reject any output whose aesthetic treatment changes an approved narrative fact, "
    "causal event, consequence, or ending."
)

REQUIRED_METADATA = {
    "scene_ids",
    "segment_id",
    "source_storyboard_revision",
    "source_storyboard_sha256",
    "source_manifest_sha256",
    "storyboard_line_ids",
    "storyboard_beat_ids",
    "storyboard_shot_ids",
    "storyboard_requirement_ids",
    "shooting_plan_status",
    "schedule_mode",
    "planned_wave",
    "depends_on_segment_ids",
    "dependency_reason",
    "predecessor_review_required",
    "required_predecessor_evidence",
    "successor_recompile_required",
    "fallback_operation_and_story_cost",
    "operation",
    "seam_class",
    "seam_resynthesis_allowed",
    "seam_story_reason",
    "editorial_intent",
    "reference_video_scope",
    "reference_video_audio",
    "camera_ensemble_color_resynthesis_allowed",
    "target_duration",
    "internal_shot_count",
    "internal_shot_order",
    "reference_binding_count",
    "reference_binding_ids",
    "continuity_status",
}

ROLE_FOR_TOKEN_KIND = {
    "Image": "reference_image",
    "Video": "reference_video",
    "Audio": "reference_audio",
}
ALLOWED_OPERATIONS = {
    "multimodal_reference",
    "video_extension",
    "strict_first_frame",
    "strict_first_last",
    "text_to_video",
}
ALLOWED_EVIDENCE = {
    "none",
    "approved_complete_predecessor",
    "approved_final_2s_silent_plus_provider_last_frame",
    "approved_provider_last_frame",
}


class SeedMasterRuntimeError(RuntimeError):
    """Raised when a Route B script cannot become one exact Seedance request."""


def read_json(path: Path, *, label: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SeedMasterRuntimeError(
            f"Missing or invalid {label or 'JSON'}: {path}"
        ) from exc
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
        raise SeedMasterRuntimeError(f"{segment_id} target_duration must be 4s-15s")
    if isinstance(value, int):
        duration = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+s", value.strip()):
        duration = int(value.strip()[:-1])
    else:
        raise SeedMasterRuntimeError(f"{segment_id} target_duration must be an integer Ns value")
    if not 4 <= duration <= 15:
        raise SeedMasterRuntimeError(f"{segment_id} target_duration must be 4s-15s")
    return duration


def _prompt_from_text(text: str, path: Path) -> str:
    marker = "## Part 1 — Overall setup"
    if text.count(marker) != 1:
        raise SeedMasterRuntimeError(f"{path.name} must contain one fixed Part 1 heading")
    prompt = text.split(marker, 1)[1]
    prompt = marker + prompt
    if prompt.count("## Part 2 — Ordered internal shots and performance") != 1:
        raise SeedMasterRuntimeError(f"{path.name} must contain one fixed Part 2 heading")
    if prompt.count("## Part 3 — Continuity, audio, quality, and duration acceptance") != 1:
        raise SeedMasterRuntimeError(f"{path.name} must contain one fixed Part 3 heading")
    if prompt.count(PRESENTATION_FIREWALL) != 1:
        raise SeedMasterRuntimeError(f"{path.name} is missing the exact presentation firewall")
    if prompt.count(ACCEPTANCE_FIREWALL) != 1:
        raise SeedMasterRuntimeError(f"{path.name} is missing the exact acceptance firewall")
    return prompt.strip()


def _manifest_section(prompt: str, path: Path) -> str:
    start = "### 1.2 Task-local reference manifest"
    end = "### 1.3 Shot-reference matrix"
    if prompt.count(start) != 1 or prompt.count(end) != 1:
        raise SeedMasterRuntimeError(f"{path.name} lacks the fixed reference manifest/matrix")
    return prompt.split(start, 1)[1].split(end, 1)[0]


def _parse_bindings(prompt: str, path: Path) -> list[dict[str, Any]]:
    section = _manifest_section(prompt, path)
    rows = []
    for match in MANIFEST_ROW_RE.finditer(section):
        binding_id, token, role, element, shot_scope, authority, forbidden = (
            item.strip() for item in match.groups()
        )
        token_match = TOKEN_RE.fullmatch(token)
        assert token_match is not None
        if role != ROLE_FOR_TOKEN_KIND[token_match.group(1)]:
            raise SeedMasterRuntimeError(f"{path.name} {token} has the wrong provider role")
        shots = [item.strip() for item in shot_scope.split(",")]
        if any(not re.fullmatch(r"Shot [1-9][0-9]*", item) for item in shots):
            raise SeedMasterRuntimeError(f"{path.name} {binding_id} has invalid explicit Shot scope")
        rows.append(
            {
                "binding_id": binding_id,
                "provider_token": token,
                "provider_role": role,
                "element": element,
                "shot_scope": shots,
                "authority": authority,
                "forbidden": forbidden,
            }
        )
    if "- none" in section and rows:
        raise SeedMasterRuntimeError(f"{path.name} mixes - none with real reference bindings")
    if not rows and "- none" not in section:
        raise SeedMasterRuntimeError(f"{path.name} has no parseable reference manifest")
    binding_ids = [item["binding_id"] for item in rows]
    if binding_ids != [f"B{index:02d}" for index in range(1, len(rows) + 1)]:
        raise SeedMasterRuntimeError(f"{path.name} binding IDs must be ordered B01..Bn")
    return rows


def _validate_token_sequence(bindings: list[dict[str, Any]], path: Path) -> None:
    tokens = list(dict.fromkeys(item["provider_token"] for item in bindings))
    for kind in ("Image", "Video", "Audio"):
        numbers = sorted(
            int(match.group(2))
            for token in tokens
            if (match := TOKEN_RE.fullmatch(token)) and match.group(1) == kind
        )
        if numbers != list(range(1, len(numbers) + 1)):
            raise SeedMasterRuntimeError(
                f"{path.name} @{kind} tokens must be contiguous from 1"
            )


def _validate_shooting_plan(metadata: dict[str, Any], segment_id: str) -> None:
    operation = metadata["operation"]
    if operation not in ALLOWED_OPERATIONS:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported operation {operation!r}")
    evidence = metadata["required_predecessor_evidence"]
    if evidence not in ALLOWED_EVIDENCE:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported predecessor evidence")
    dependencies = _unique_string_list(
        metadata["depends_on_segment_ids"],
        f"{segment_id}.depends_on_segment_ids",
    )
    if any(not SEGMENT_RE.fullmatch(item) for item in dependencies):
        raise SeedMasterRuntimeError(f"{segment_id} has an invalid dependency ID")
    schedule = metadata["schedule_mode"]
    if schedule == "parallel":
        if (
            dependencies
            or metadata["planned_wave"] != 0
            or metadata["predecessor_review_required"] is not False
            or evidence != "none"
            or metadata["shooting_plan_status"] != "planned"
        ):
            raise SeedMasterRuntimeError(f"{segment_id} parallel shooting plan is contradictory")
    elif schedule == "serial_after_predecessor_review":
        if (
            len(dependencies) != 1
            or not isinstance(metadata["planned_wave"], int)
            or metadata["planned_wave"] < 1
            or metadata["predecessor_review_required"] is not True
            or metadata["successor_recompile_required"] is not True
            or metadata["shooting_plan_status"] != "observed_adapted"
            or evidence == "none"
        ):
            raise SeedMasterRuntimeError(
                f"{segment_id} dependent Script must be observed_adapted after predecessor review"
            )
    else:
        raise SeedMasterRuntimeError(f"{segment_id} has unsupported schedule_mode {schedule!r}")

    scope = metadata["reference_video_scope"]
    audio = metadata["reference_video_audio"]
    editorial = metadata["editorial_intent"]
    seam = metadata["seam_class"]
    if operation == "video_extension":
        if not (
            evidence == "approved_complete_predecessor"
            and scope == "full_predecessor_for_extension"
            and audio == "preserved_for_extension"
            and seam == "continuous_extension"
            and editorial == "none"
        ):
            raise SeedMasterRuntimeError(f"{segment_id} video extension contract is contradictory")
    elif editorial in {"matched_cut", "keyframed_matched_cut"}:
        if not (
            evidence == "approved_final_2s_silent_plus_provider_last_frame"
            and scope == "exact_final_2s_real_motion"
            and audio == "stripped_for_matched_cut"
            and operation == "multimodal_reference"
        ):
            raise SeedMasterRuntimeError(f"{segment_id} matched-cut contract is contradictory")
    elif evidence == "approved_provider_last_frame":
        if scope != "none" or audio != "none":
            raise SeedMasterRuntimeError(f"{segment_id} last-frame-only contract is contradictory")
    elif evidence == "none" and (scope != "none" or audio != "none"):
        raise SeedMasterRuntimeError(f"{segment_id} independent plan declares predecessor video")


def parse_segment_script(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise SeedMasterRuntimeError(f"Unreadable Seed Master Segment Script: {path}") from exc
    filename_match = SCRIPT_RE.fullmatch(path.name)
    header_match = HEADER_RE.search(text)
    if not filename_match or not header_match:
        raise SeedMasterRuntimeError(f"Invalid Seed Master Segment filename/header: {path}")
    segment_id = f"segment-{int(filename_match.group(1)):03d}"
    if header_match.group(1) != segment_id:
        raise SeedMasterRuntimeError(f"{path.name} heading identity differs from filename")
    try:
        metadata = yaml.safe_load(header_match.group(2))
    except yaml.YAMLError as exc:
        raise SeedMasterRuntimeError(f"{path.name} has invalid YAML metadata") from exc
    if not isinstance(metadata, dict):
        raise SeedMasterRuntimeError(f"{path.name} YAML metadata must be one object")
    missing = sorted(REQUIRED_METADATA - set(metadata))
    if missing:
        raise SeedMasterRuntimeError(f"{path.name} metadata is missing: {', '.join(missing)}")
    if metadata["segment_id"] != segment_id:
        raise SeedMasterRuntimeError(f"{path.name} metadata segment_id differs")
    for field in ("source_storyboard_sha256", "source_manifest_sha256"):
        if not isinstance(metadata[field], str) or not HASH_RE.fullmatch(metadata[field]):
            raise SeedMasterRuntimeError(f"{path.name} {field} must be lowercase SHA-256")
    for field in (
        "scene_ids",
        "storyboard_line_ids",
        "storyboard_beat_ids",
        "storyboard_shot_ids",
        "storyboard_requirement_ids",
        "internal_shot_order",
        "reference_binding_ids",
    ):
        _unique_string_list(
            metadata[field],
            f"{segment_id}.{field}",
            allow_empty=field in {"storyboard_line_ids", "reference_binding_ids"},
        )
    _nonempty_string(metadata["source_storyboard_revision"], "source_storyboard_revision")
    for field in ("dependency_reason", "fallback_operation_and_story_cost", "seam_story_reason"):
        _nonempty_string(metadata[field], f"{segment_id}.{field}")
    _validate_shooting_plan(metadata, segment_id)
    duration = _target_duration(metadata["target_duration"], segment_id)
    if isinstance(metadata["internal_shot_count"], bool) or not isinstance(
        metadata["internal_shot_count"], int
    ) or metadata["internal_shot_count"] < 1:
        raise SeedMasterRuntimeError(f"{segment_id} internal_shot_count must be positive")

    prompt = _prompt_from_text(text, path)
    shots = [
        {
            "shot_number": int(match.group(1)),
            "shot_id": match.group(2).strip(),
            "location_id": match.group(3).strip(),
            "camera_id": match.group(4).strip(),
            "panel_id": match.group(5).strip(),
        }
        for match in SHOT_RE.finditer(prompt)
    ]
    expected_order = [f"Shot {index}" for index in range(1, len(shots) + 1)]
    if (
        [item["shot_number"] for item in shots] != list(range(1, len(shots) + 1))
        or len(shots) != metadata["internal_shot_count"]
        or metadata["internal_shot_order"] != expected_order
        or [item["shot_id"] for item in shots] != metadata["storyboard_shot_ids"]
    ):
        raise SeedMasterRuntimeError(f"{segment_id} internal Shot metadata differs from Prompt")

    bindings = _parse_bindings(prompt, path)
    if (
        metadata["reference_binding_count"] != len(bindings)
        or metadata["reference_binding_ids"]
        != [item["binding_id"] for item in bindings]
    ):
        raise SeedMasterRuntimeError(f"{segment_id} reference binding metadata differs")
    _validate_token_sequence(bindings, path)
    shot_names = set(expected_order)
    if any(not set(item["shot_scope"]) <= shot_names for item in bindings):
        raise SeedMasterRuntimeError(f"{segment_id} binding scope names an unknown Shot")

    return {
        "segment_id": segment_id,
        "number": int(filename_match.group(1)),
        "path": path,
        "text": text,
        "script_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "metadata": metadata,
        "duration": duration,
        "prompt": prompt,
        "shots": shots,
        "bindings": bindings,
    }


def token_sort_key(token: str) -> tuple[int, int]:
    match = TOKEN_RE.fullmatch(token)
    if not match:
        raise SeedMasterRuntimeError(f"Invalid provider token: {token}")
    return ({"Image": 0, "Video": 1, "Audio": 2}[match.group(1)], int(match.group(2)))


def _asset_namespace(bindings: list[dict[str, Any]], token: str) -> str:
    namespaces = {
        str(item["element"]).split(".", 1)[0]
        for item in bindings
        if item["provider_token"] == token
    }
    if len(namespaces) != 1:
        raise SeedMasterRuntimeError(
            f"{token} atomic elements must resolve to one asset or continuity namespace"
        )
    namespace = next(iter(namespaces))
    if not namespace:
        raise SeedMasterRuntimeError(f"{token} has an empty media namespace")
    return namespace


def _require_http_uri(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise SeedMasterRuntimeError(f"{label} has no concrete HTTP(S) URI")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise SeedMasterRuntimeError(f"{label} has no concrete HTTP(S) URI")
    return value


def _resolve_roster_visual(
    namespace: str, assets: dict[str, Any]
) -> tuple[str, str, str] | None:
    if "--" not in namespace:
        return None
    roster_id, member_type_id = namespace.split("--", 1)
    roster = assets.get(roster_id)
    if not isinstance(roster, dict) or roster.get("type") != "ensemble_roster":
        return None
    matches = [
        item
        for item in roster.get("members", [])
        if isinstance(item, dict) and item.get("member_type_id") == member_type_id
    ]
    if len(matches) != 1:
        raise SeedMasterRuntimeError(f"Ambiguous ensemble asset namespace: {namespace}")
    media = matches[0].get("roster_asset")
    uri = media.get("uri") if isinstance(media, dict) else None
    return namespace, "ensemble_roster_member", _require_http_uri(uri, namespace)


def resolve_catalog_media(
    *, namespace: str, provider_role: str, catalog: dict[str, Any]
) -> dict[str, Any]:
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
        return {
            "asset_id": namespace,
            "asset_type": str(asset.get("type")),
            "uri": _require_http_uri(uri, namespace),
        }
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
        return {
            "asset_id": namespace,
            "asset_type": asset_type,
            "uri": _require_http_uri(uri, namespace),
        }
    raise SeedMasterRuntimeError(f"Catalog cannot resolve provider role {provider_role}")


def _source_attempt(task_dir: Path, source_segment_id: str) -> str:
    source_root = (
        task_dir
        / ".pending/virtual-production/generation-segments"
        / source_segment_id
    )
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
        raise SeedMasterRuntimeError(
            f"Dependent Script requires the current generated attempt for {source_segment_id}"
        )
    return attempt_id


def _runtime_binding(
    *,
    token: str,
    role: str,
    namespace: str,
    metadata: dict[str, Any],
    task_dir: Path,
) -> dict[str, Any]:
    dependencies = metadata["depends_on_segment_ids"]
    if len(dependencies) != 1:
        raise SeedMasterRuntimeError(f"{token} continuity media requires one predecessor")
    source_segment_id = dependencies[0]
    attempt_id = _source_attempt(task_dir, source_segment_id)
    evidence = metadata["required_predecessor_evidence"]
    if role == "reference_video":
        if evidence == "approved_complete_predecessor":
            source_kind = "complete_predecessor_video"
            audio_policy = "preserved"
        elif evidence == "approved_final_2s_silent_plus_provider_last_frame":
            source_kind = "final_2s_silent_video"
            audio_policy = "stripped"
        else:
            raise SeedMasterRuntimeError(f"{token} is not authorized by the shooting plan")
    elif role == "reference_image":
        if evidence not in {
            "approved_final_2s_silent_plus_provider_last_frame",
            "approved_provider_last_frame",
        }:
            raise SeedMasterRuntimeError(f"{token} is not authorized by the shooting plan")
        source_kind = "provider_last_frame"
        audio_policy = "none"
    else:
        raise SeedMasterRuntimeError(f"Continuity namespace cannot bind {role}")
    return {
        "provider_token": token,
        "provider_role": role,
        "source_kind": source_kind,
        "source_segment_id": source_segment_id,
        "source_provider_attempt_id": attempt_id,
        "namespace": namespace,
        "audio_policy": audio_policy,
    }


def build_execution_plan(
    *,
    task_dir: Path,
    parsed: dict[str, Any],
    catalog: dict[str, Any],
    capability_profile: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
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
        if role == "reference_video" and namespace != "continuity":
            raise SeedMasterRuntimeError(
                f"{token} predecessor video must use the reserved continuity namespace"
            )
        if role == "reference_video" or namespace == "continuity":
            media = _runtime_binding(
                token=token,
                role=role,
                namespace=namespace,
                metadata=metadata,
                task_dir=task_dir,
            )
        else:
            resolved = resolve_catalog_media(
                namespace=namespace,
                provider_role=role,
                catalog=catalog,
            )
            media = {
                "provider_token": token,
                "provider_role": role,
                "source_kind": "asset_catalog",
                "namespace": namespace,
                **resolved,
            }
        media["binding_ids"] = [item["binding_id"] for item in rows]
        media_bindings.append(media)

    evidence = metadata["required_predecessor_evidence"]
    source_kinds = {item["source_kind"] for item in media_bindings}
    required_runtime_kinds = {
        "none": set(),
        "approved_complete_predecessor": {"complete_predecessor_video"},
        "approved_final_2s_silent_plus_provider_last_frame": {
            "final_2s_silent_video",
            "provider_last_frame",
        },
        "approved_provider_last_frame": {"provider_last_frame"},
    }[evidence]
    actual_runtime_kinds = source_kinds - {"asset_catalog"}
    if actual_runtime_kinds != required_runtime_kinds:
        raise SeedMasterRuntimeError(
            f"{parsed['segment_id']} Prompt tokens do not match required predecessor evidence"
        )

    if capability_profile.get("contract") != "seedance-capability-profile" or capability_profile.get(
        "profile_status"
    ) != "VERIFIED":
        raise SeedMasterRuntimeError("Seedance capability profile is not verified")
    model_id = _nonempty_string(capability_profile.get("model_id"), "Seedance model_id")
    task_input = task.get("input")
    if not isinstance(task_input, dict):
        raise SeedMasterRuntimeError("task.json input must be an object")
    resolution = _nonempty_string(task_input.get("resolution"), "task input resolution").lower()
    ratio = _nonempty_string(task_input.get("aspect_ratio"), "task input aspect_ratio")
    counts = {
        role: sum(item["provider_role"] == role for item in media_bindings)
        for role in ("reference_image", "reference_video", "reference_audio")
    }
    capabilities = capability_profile.get("provider_capabilities")
    if not isinstance(capabilities, dict):
        raise SeedMasterRuntimeError("Seedance capability profile lacks provider_capabilities")
    limits = {
        "reference_image": capabilities.get("maximum_reference_images"),
        "reference_video": capabilities.get("maximum_reference_videos"),
        "reference_audio": capabilities.get("maximum_reference_audios"),
    }
    for role, count in counts.items():
        limit = limits[role]
        if isinstance(limit, bool) or not isinstance(limit, int) or count > limit:
            raise SeedMasterRuntimeError(
                f"{parsed['segment_id']} exceeds the verified {role} limit"
            )
    return {
        "contract": "seedance-segment-execution-plan-v1",
        "segment_id": parsed["segment_id"],
        "source_segment_script": parsed["path"].relative_to(task_dir).as_posix(),
        "source_script_sha256": parsed["script_sha256"],
        "source_storyboard_sha256": metadata["source_storyboard_sha256"],
        "source_manifest_sha256": metadata["source_manifest_sha256"],
        "shooting_plan": {
            field: metadata[field]
            for field in (
                "shooting_plan_status",
                "schedule_mode",
                "planned_wave",
                "depends_on_segment_ids",
                "dependency_reason",
                "predecessor_review_required",
                "required_predecessor_evidence",
                "successor_recompile_required",
                "fallback_operation_and_story_cost",
                "operation",
                "seam_class",
                "seam_resynthesis_allowed",
                "seam_story_reason",
                "editorial_intent",
                "reference_video_scope",
                "reference_video_audio",
                "camera_ensemble_color_resynthesis_allowed",
            )
        },
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
    storyboard_path = task_dir / STORYBOARD_RELATIVE
    manifest_path = task_dir / COMPILE_MANIFEST_RELATIVE
    metadata = parsed["metadata"]
    if sha256_file(storyboard_path) != metadata["source_storyboard_sha256"]:
        raise SeedMasterRuntimeError(f"{parsed['segment_id']} Storyboard hash is stale")
    if sha256_file(manifest_path) != metadata["source_manifest_sha256"]:
        raise SeedMasterRuntimeError(f"{parsed['segment_id']} compile-manifest hash is stale")


def load_execution_plan(task_dir: Path, segment_id: str) -> dict[str, Any]:
    if not SEGMENT_RE.fullmatch(segment_id):
        raise SeedMasterRuntimeError(f"Invalid Segment ID: {segment_id}")
    path = task_dir / EXECUTION_PLAN_DIR_RELATIVE / f"{segment_id}.json"
    plan = read_json(path, label="Seedance execution plan")
    if plan.get("contract") != "seedance-segment-execution-plan-v1" or plan.get(
        "segment_id"
    ) != segment_id:
        raise SeedMasterRuntimeError(f"Invalid Seedance execution plan: {path}")
    return plan


def manifest_segment_rows(task_dir: Path) -> list[dict[str, Any]]:
    manifest = read_json(
        task_dir / COMPILE_MANIFEST_RELATIVE,
        label="Storyboard compile manifest",
    )
    rows = manifest.get("segments")
    if not isinstance(rows, list) or not rows:
        raise SeedMasterRuntimeError("Storyboard compile manifest has no Segments")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        segment_id = row.get("segment_id") if isinstance(row, dict) else None
        if not isinstance(segment_id, str) or not SEGMENT_RE.fullmatch(segment_id) or segment_id in seen:
            raise SeedMasterRuntimeError("Storyboard compile manifest has invalid Segment IDs")
        seen.add(segment_id)
        result.append(row)
    return result
