"""Load the single, strict production-design asset catalog.

The persisted catalog is deliberately smaller than provider request/response
metadata and is the only shared asset authority.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
from urllib.parse import urlsplit

from story_video.asset_support import StoryVideoError, require_utf8_text
from story_video.visual_style_contract import (
    contains_prohibited_style_shortcut,
)
ASSET_CATALOG_FILENAME = "assets.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ASSET_MEDIA_RELATIVE_PATH = Path("assets")
ASSET_CATALOG_RELATIVE_PATH = ASSET_MEDIA_RELATIVE_PATH / ASSET_CATALOG_FILENAME
LEGACY_TASK_ASSET_PATHS = (
    Path("direct-production-design/assets.json"),
    Path("direct-production-design/assets"),
)
ASSET_TYPES = frozenset(
    {
        "character",
        "costume",
        "prop",
        "location_master",
        "sound",
        "ensemble_roster",
    }
)
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

ROOT_KEYS = frozenset(
    {
        "contract",
        "path_resolution",
        "assets",
    }
)
COMMON_ASSET_KEYS = frozenset({"type", "description_en", "visual"})
ACTOR_PROFILE_KEYS = frozenset(
    {"name_en", "personality_en", "screen_presence_en", "acting_range_en"}
)
BODY_TOPOLOGY_KEYS = frozenset(
    {
        "body_plan_en",
        "total_limb_count",
        "limb_sets",
        "non_limb_appendages",
        "topology_lock_en",
    }
)
LIMB_SET_KEYS = frozenset({"kind_en", "count", "function_en"})
NON_LIMB_APPENDAGE_KEYS = frozenset({"kind_en", "count"})
COSTUME_ASSET_KEYS = COMMON_ASSET_KEYS | {
    "character_id",
    "appearance_state_en",
}
LOCATION_MASTER_ASSET_KEYS = COMMON_ASSET_KEYS | {
    "included_prop_ids",
    "embedded_npc_asset_ids",
    "independent_performer_asset_ids",
    "fixed_set_elements_en",
}
SOUND_ASSET_KEYS = frozenset(
    {
        "type",
        "description_en",
        "sound_role",
        "owner_character_id",
        "audio",
    }
)
ASSET_KEYS_BY_TYPE = {
    # Final-look props and visible thought remain visual-review concerns. The
    # exhaustive model-authored body topology is catalog authority because video
    # generation must preserve it across motion.
    "character": COMMON_ASSET_KEYS | {"actor_profile", "body_topology", "voice"},
    "costume": COSTUME_ASSET_KEYS,
    "prop": COMMON_ASSET_KEYS,
    "location_master": LOCATION_MASTER_ASSET_KEYS,
    "sound": SOUND_ASSET_KEYS,
    "ensemble_roster": frozenset({"type", "description_en", "members"}),
}
VISUAL_KEYS = frozenset({"path", "uri"})
ROSTER_ASSET_KEYS = frozenset({"path", "uri", "subject_count"})
ROSTER_MEMBER_KEYS = frozenset(
    {
        "member_type_id",
        "roster_asset",
        "allowed_member_types_en",
        "variation_profile",
    }
)
VARIATION_PROFILE_KEYS = frozenset({"locked_traits_en", "allowed_variation_en"})
VOICE_KEYS = frozenset({"description_en", "reference"})
AUDIO_REFERENCE_KEYS = frozenset({"path", "uri"})
SOUND_ROLES = frozenset(
    {"ambience", "foley", "sound_effect", "diegetic_music"}
)
STORY_BOUND_ACTOR_PROFILE_RE = re.compile(
    r"\b(?:screenplay|segment|current story|story objective|narrative function|"
    r"plot event|scene-specific)\b",
    re.IGNORECASE,
)

FORBIDDEN_TRANSPORT_FIELDS = frozenset(
    {
        "image",
        "cache",
        "bucket",
        "region",
        "endpoint",
        "image_prompt_en",
        "image_tos",
    }
)


def reject_task_local_asset_state(task_root: Path) -> None:
    """Reject the deleted task-owned asset contract instead of reviving it."""

    root = task_root.expanduser().resolve()
    stale = [
        path.as_posix()
        for path in LEGACY_TASK_ASSET_PATHS
        if (root / path).exists()
    ]
    if stale:
        raise StoryVideoError(
            "Task-local production assets are forbidden; remove the obsolete path(s): "
            + ", ".join(stale)
        )


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StoryVideoError(f"assets.json contains duplicate JSON key {key!r}.")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StoryVideoError(f"Missing required asset catalog: {path}") from exc
    except UnicodeDecodeError as exc:
        raise StoryVideoError(f"Asset catalog must be valid UTF-8 JSON: {path}") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_object_keys)
    except StoryVideoError:
        raise
    except json.JSONDecodeError as exc:
        raise StoryVideoError(f"Asset catalog must be valid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise StoryVideoError(
            "assets/assets.json must contain one JSON object."
        )
    return payload


def _require_exact_keys(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StoryVideoError(f"{label} must be an object.")
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise StoryVideoError(f"{label} must use exact keys ({'; '.join(details)}).")
    return value


def _reject_transport_fields(
    value: Any,
    location: str = "assets/assets.json",
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_TRANSPORT_FIELDS:
                raise StoryVideoError(
                    f"{location}.{key} is a forbidden provider-transport field in assets.json."
                )
            _reject_transport_fields(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_transport_fields(nested, f"{location}[{index}]")


def _require_http_uri(value: Any, label: str) -> str:
    uri = require_utf8_text(value, label)
    parsed = urlsplit(uri)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise StoryVideoError(f"{label} must be an absolute HTTP(S) URI.")
    if parsed.query or parsed.fragment:
        raise StoryVideoError(
            f"{label} must be a persistent unsigned URL without query or fragment."
        )
    return uri


def _require_asset_file(
    repository_root: Path,
    asset_dir: Path,
    value: Any,
    label: str,
) -> tuple[str, Path]:
    raw = require_utf8_text(value, label)
    if "\x00" in raw:
        raise StoryVideoError(f"{label} contains a NUL byte.")
    portable = PurePosixPath(raw)
    if portable.is_absolute() or ".." in portable.parts:
        raise StoryVideoError(
            f"{label} must be repository-root-relative inside assets/."
        )
    expected_prefix = ASSET_MEDIA_RELATIVE_PATH.parts
    if portable.parts[: len(expected_prefix)] != expected_prefix:
        raise StoryVideoError(
            f"{label} must be repository-root-relative inside assets/."
        )

    declared_path = repository_root.joinpath(*portable.parts)
    try:
        resolved = declared_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise StoryVideoError(f"{label} does not identify an existing file: {raw}") from exc
    try:
        asset_resolved = asset_dir.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise StoryVideoError(f"Missing required asset directory: {asset_dir}") from exc
    if (
        asset_resolved != repository_root
        and repository_root not in asset_resolved.parents
    ):
        raise StoryVideoError(
            "repository_root/assets may not resolve outside the repository root."
        )
    if resolved != asset_resolved and asset_resolved not in resolved.parents:
        raise StoryVideoError(
            f"{label} escapes repository-root assets/ through a path "
            f"or symlink: {raw}"
        )
    try:
        mode = resolved.stat().st_mode
    except OSError as exc:
        raise StoryVideoError(f"{label} cannot be inspected: {raw}") from exc
    if not stat.S_ISREG(mode):
        raise StoryVideoError(f"{label} must identify a real regular file: {raw}")
    return portable.as_posix(), resolved


def _require_wav(path: Path, label: str) -> None:
    if path.suffix.casefold() != ".wav":
        raise StoryVideoError(f"{label} must identify a WAV file.")
    try:
        header = path.read_bytes()[:12]
    except OSError as exc:
        raise StoryVideoError(f"{label} cannot be read as WAV evidence.") from exc
    if len(header) != 12 or header[:4] not in {b"RIFF", b"RF64"} or header[8:] != b"WAVE":
        raise StoryVideoError(f"{label} must identify a valid RIFF/RF64 WAV file.")


def _validate_visual(
    raw: Any,
    *,
    asset_id: str,
    task_root: Path,
    asset_dir: Path,
) -> tuple[dict[str, str], Path]:
    value = _require_exact_keys(raw, VISUAL_KEYS, f"asset {asset_id} visual")
    path, resolved = _require_asset_file(
        task_root, asset_dir, value["path"], f"asset {asset_id} visual.path"
    )
    uri = _require_http_uri(value["uri"], f"asset {asset_id} visual.uri")
    return {"path": path, "uri": uri}, resolved


def _validate_roster_members(
    raw: Any,
    *,
    asset_id: str,
    task_root: Path,
    asset_dir: Path,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, str], Path]]]:
    if not isinstance(raw, list) or not raw:
        raise StoryVideoError(f"ensemble_roster {asset_id} members must be a non-empty array.")
    normalized: list[dict[str, Any]] = []
    visual_evidence: list[tuple[dict[str, str], Path]] = []
    seen_member_types: set[str] = set()
    for index, raw_member in enumerate(raw, start=1):
        member = _require_exact_keys(
            raw_member,
            ROSTER_MEMBER_KEYS,
            f"ensemble_roster {asset_id} member {index}",
        )
        member_type_id = require_utf8_text(
            member["member_type_id"],
            f"ensemble_roster {asset_id} member {index} member_type_id",
        )
        if not ASSET_ID_RE.fullmatch(member_type_id):
            raise StoryVideoError(
                f"ensemble_roster {asset_id} member {index} has invalid member_type_id."
            )
        if member_type_id in seen_member_types:
            raise StoryVideoError(
                f"ensemble_roster {asset_id} repeats member_type_id {member_type_id}."
            )
        seen_member_types.add(member_type_id)
        roster_asset = _require_exact_keys(
            member["roster_asset"],
            ROSTER_ASSET_KEYS,
            f"ensemble_roster {asset_id} member {member_type_id} roster_asset",
        )
        subject_count = roster_asset.get("subject_count")
        if (
            isinstance(subject_count, bool)
            or not isinstance(subject_count, int)
            or subject_count < 1
        ):
            raise StoryVideoError(
                f"ensemble_roster {asset_id} member {member_type_id} roster_asset must "
                "declare a positive subject_count; one-shot silent roles may use an exact one-subject closed roster."
            )
        visual, resolved = _validate_visual(
            {"path": roster_asset["path"], "uri": roster_asset["uri"]},
            asset_id=f"{asset_id}/{member_type_id}",
            task_root=task_root,
            asset_dir=asset_dir,
        )
        variation = _require_exact_keys(
            member["variation_profile"],
            VARIATION_PROFILE_KEYS,
            f"ensemble_roster {asset_id} member {member_type_id} variation_profile",
        )
        locked_traits = require_utf8_text(
            variation["locked_traits_en"],
            f"ensemble_roster {asset_id} member {member_type_id} locked_traits_en",
        )
        allowed_variation = require_utf8_text(
            variation["allowed_variation_en"],
            f"ensemble_roster {asset_id} member {member_type_id} allowed_variation_en",
        )
        allowed_member_types = member["allowed_member_types_en"]
        if (
            not isinstance(allowed_member_types, list)
            or not allowed_member_types
            or any(
                not isinstance(value, str) or not value.strip()
                for value in allowed_member_types
            )
            or len({value.strip().casefold() for value in allowed_member_types})
            != len(allowed_member_types)
        ):
            raise StoryVideoError(
                f"ensemble_roster {asset_id} member {member_type_id} "
                "allowed_member_types_en must be a non-empty unique text array."
            )
        normalized.append(
            {
                "member_type_id": member_type_id,
                "roster_asset": {**visual, "subject_count": subject_count},
                "allowed_member_types_en": [
                    value.strip() for value in allowed_member_types
                ],
                "variation_profile": {
                    "locked_traits_en": locked_traits,
                    "allowed_variation_en": allowed_variation,
                },
            }
        )
        visual_evidence.append((visual, resolved))
    return normalized, visual_evidence


def _validate_voice(
    raw: Any,
    *,
    asset_id: str,
    task_root: Path,
    asset_dir: Path,
) -> dict[str, Any]:
    voice = _require_exact_keys(raw, VOICE_KEYS, f"character {asset_id} voice")
    description = require_utf8_text(
        voice["description_en"], f"character {asset_id} voice.description_en"
    )
    reference = _require_exact_keys(
        voice["reference"], AUDIO_REFERENCE_KEYS, f"character {asset_id} voice.reference"
    )
    audio_path, audio_resolved = _require_asset_file(
        task_root,
        asset_dir,
        reference["path"],
        f"character {asset_id} voice.reference.path",
    )
    _require_wav(audio_resolved, f"character {asset_id} voice.reference.path")
    uri = _require_http_uri(
        reference["uri"], f"character {asset_id} voice.reference.uri"
    )
    return {
        "description_en": description,
        "reference": {"path": audio_path, "uri": uri},
    }


def _validate_audio_reference(
    raw: Any,
    *,
    asset_id: str,
    task_root: Path,
    asset_dir: Path,
) -> tuple[dict[str, str], Path]:
    reference = _require_exact_keys(
        raw, AUDIO_REFERENCE_KEYS, f"sound {asset_id} audio"
    )
    audio_path, audio_resolved = _require_asset_file(
        task_root,
        asset_dir,
        reference["path"],
        f"sound {asset_id} audio.path",
    )
    _require_wav(audio_resolved, f"sound {asset_id} audio.path")
    uri = _require_http_uri(reference["uri"], f"sound {asset_id} audio.uri")
    return {"path": audio_path, "uri": uri}, audio_resolved


def _validate_actor_profile(raw: Any, *, asset_id: str) -> dict[str, str]:
    """Validate a reusable casting-card profile with no story assignment."""

    value = _require_exact_keys(
        raw,
        ACTOR_PROFILE_KEYS,
        f"character {asset_id} actor_profile",
    )
    normalized: dict[str, str] = {}
    for field in sorted(ACTOR_PROFILE_KEYS):
        text = require_utf8_text(
            value[field], f"character {asset_id} actor_profile.{field}"
        )
        if STORY_BOUND_ACTOR_PROFILE_RE.search(text):
            raise StoryVideoError(
                f"character {asset_id} actor_profile.{field} must describe the reusable "
                "actor, not one screenplay assignment."
            )
        normalized[field] = text
    return normalized


def _validate_body_topology(raw: Any, *, asset_id: str) -> dict[str, Any]:
    value = _require_exact_keys(
        raw, BODY_TOPOLOGY_KEYS, f"character {asset_id} body_topology"
    )
    limb_sets = value["limb_sets"]
    if not isinstance(limb_sets, list) or not limb_sets:
        raise StoryVideoError(
            f"character {asset_id} body_topology.limb_sets must be non-empty."
        )
    normalized_limb_sets: list[dict[str, Any]] = []
    seen_limb_kinds: set[str] = set()
    for index, raw_set in enumerate(limb_sets, start=1):
        item = _require_exact_keys(
            raw_set,
            LIMB_SET_KEYS,
            f"character {asset_id} body_topology.limb_sets[{index}]",
        )
        kind = require_utf8_text(
            item["kind_en"],
            f"character {asset_id} body_topology.limb_sets[{index}].kind_en",
        )
        count = item["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise StoryVideoError(
                f"character {asset_id} body_topology.limb_sets[{index}].count "
                "must be a positive integer."
            )
        if kind.casefold() in seen_limb_kinds:
            raise StoryVideoError(
                f"character {asset_id} body_topology repeats limb kind {kind!r}."
            )
        seen_limb_kinds.add(kind.casefold())
        normalized_limb_sets.append(
            {
                "kind_en": kind,
                "count": count,
                "function_en": require_utf8_text(
                    item["function_en"],
                    f"character {asset_id} body_topology.limb_sets[{index}].function_en",
                ),
            }
        )
    total = value["total_limb_count"]
    if (
        isinstance(total, bool)
        or not isinstance(total, int)
        or total < 1
        or total != sum(item["count"] for item in normalized_limb_sets)
    ):
        raise StoryVideoError(
            f"character {asset_id} body_topology.total_limb_count must be positive "
            "and equal the sum of limb-set counts."
        )

    appendages = value["non_limb_appendages"]
    if not isinstance(appendages, list):
        raise StoryVideoError(
            f"character {asset_id} body_topology.non_limb_appendages must be an array."
        )
    normalized_appendages: list[dict[str, Any]] = []
    seen_appendage_kinds: set[str] = set()
    for index, raw_appendage in enumerate(appendages, start=1):
        item = _require_exact_keys(
            raw_appendage,
            NON_LIMB_APPENDAGE_KEYS,
            f"character {asset_id} body_topology.non_limb_appendages[{index}]",
        )
        kind = require_utf8_text(
            item["kind_en"],
            f"character {asset_id} body_topology.non_limb_appendages[{index}].kind_en",
        )
        count = item["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise StoryVideoError(
                f"character {asset_id} body_topology.non_limb_appendages[{index}].count "
                "must be a positive integer."
            )
        if kind.casefold() in seen_appendage_kinds:
            raise StoryVideoError(
                f"character {asset_id} body_topology repeats appendage {kind!r}."
            )
        seen_appendage_kinds.add(kind.casefold())
        normalized_appendages.append({"kind_en": kind, "count": count})
    return {
        "body_plan_en": require_utf8_text(
            value["body_plan_en"],
            f"character {asset_id} body_topology.body_plan_en",
        ),
        "total_limb_count": total,
        "limb_sets": normalized_limb_sets,
        "non_limb_appendages": normalized_appendages,
        "topology_lock_en": require_utf8_text(
            value["topology_lock_en"],
            f"character {asset_id} body_topology.topology_lock_en",
        ),
    }


def load_asset_catalog(
    task_root: Path, *, repository_root: Path | None = None
) -> dict[str, Any]:
    """Load the repository-owned ``assets/assets.json`` catalog.

    ``task_root`` remains an input only so callers keep validating one concrete
    production task. Media ownership is deliberately independent of that task.
    """

    task_root = task_root.expanduser().resolve()
    reject_task_local_asset_state(task_root)
    repository_root = (repository_root or REPOSITORY_ROOT).expanduser().resolve()
    asset_dir = repository_root / ASSET_MEDIA_RELATIVE_PATH
    catalog_path = repository_root / ASSET_CATALOG_RELATIVE_PATH
    if not catalog_path.is_file():
        raise StoryVideoError(f"Missing required asset catalog: {catalog_path}")
    if catalog_path.is_symlink():
        raise StoryVideoError(
            "assets/assets.json must be a real file, "
            "not a symlink."
        )

    payload = _load_json(catalog_path)
    _reject_transport_fields(payload)
    _require_exact_keys(
        payload, ROOT_KEYS, "assets/assets.json root"
    )

    fixed = {
        "contract": "production-design-assets",
        "path_resolution": "repository_root_relative",
    }
    invalid = [
        key
        for key, expected in fixed.items()
        if type(payload.get(key)) is not type(expected) or payload.get(key) != expected
    ]
    if invalid:
        raise StoryVideoError(
            "assets/assets.json has invalid fixed fields: "
            + ", ".join(invalid)
        )
    if contains_prohibited_style_shortcut(payload):
        raise StoryVideoError(
            "assets/assets.json contains a prohibited "
            "brand/IP visual-style shortcut."
        )

    raw_assets = payload["assets"]
    if not isinstance(raw_assets, dict) or not raw_assets:
        raise StoryVideoError(
            "assets/assets.json assets must be a non-empty "
            "object keyed by ID."
        )

    assets: dict[str, dict[str, Any]] = {}
    visual_paths: dict[Path, str] = {}
    visual_uris: dict[str, str] = {}
    audio_paths: dict[Path, str] = {}
    audio_uris: dict[str, str] = {}
    for asset_id, raw in raw_assets.items():
        if not isinstance(asset_id, str) or not ASSET_ID_RE.fullmatch(asset_id):
            raise StoryVideoError(f"Invalid canonical asset ID: {asset_id!r}.")
        if not isinstance(raw, dict):
            raise StoryVideoError(f"asset {asset_id} must be an object.")
        asset_type = raw.get("type")
        if asset_type not in ASSET_TYPES:
            raise StoryVideoError(f"asset {asset_id} has invalid type {asset_type!r}.")
        expected_keys = ASSET_KEYS_BY_TYPE[asset_type]
        value = _require_exact_keys(raw, expected_keys, f"asset {asset_id}")
        description = require_utf8_text(
            value["description_en"], f"asset {asset_id} description_en"
        )
        normalized: dict[str, Any] = {
            "type": asset_type,
            "description_en": description,
        }
        if asset_type == "sound":
            sound_role = require_utf8_text(
                value["sound_role"], f"sound {asset_id} sound_role"
            )
            if sound_role not in SOUND_ROLES:
                raise StoryVideoError(
                    f"sound {asset_id} sound_role must be one of: "
                    + ", ".join(sorted(SOUND_ROLES))
                )
            owner_character_id = require_utf8_text(
                value["owner_character_id"], f"sound {asset_id} owner_character_id"
            )
            if owner_character_id != "none" and not ASSET_ID_RE.fullmatch(
                owner_character_id
            ):
                raise StoryVideoError(
                    f"sound {asset_id} owner_character_id must be a canonical asset ID or none."
                )
            if owner_character_id != "none":
                raise StoryVideoError(
                    f"sound {asset_id} must use owner_character_id none; named voice "
                    "authority belongs inside its character record."
                )
            audio, audio_resolved = _validate_audio_reference(
                value["audio"],
                asset_id=asset_id,
                task_root=repository_root,
                asset_dir=asset_dir,
            )
            if audio_resolved in audio_paths:
                raise StoryVideoError(
                    f"Audio media path is reused by assets {audio_paths[audio_resolved]} "
                    f"and {asset_id}."
                )
            if audio["uri"] in audio_uris:
                raise StoryVideoError(
                    f"Audio media URI is reused by assets {audio_uris[audio['uri']]} "
                    f"and {asset_id}."
                )
            audio_paths[audio_resolved] = asset_id
            audio_uris[audio["uri"]] = asset_id
            normalized.update(
                {
                    "sound_role": sound_role,
                    "owner_character_id": owner_character_id,
                    "audio": audio,
                }
            )
            assets[asset_id] = normalized
            continue
        if asset_type == "ensemble_roster":
            members, roster_visuals = _validate_roster_members(
                value["members"],
                asset_id=asset_id,
                task_root=repository_root,
                asset_dir=asset_dir,
            )
            for member, (visual, visual_resolved) in zip(members, roster_visuals):
                label = f"{asset_id}/{member['member_type_id']}"
                if visual_resolved in visual_paths:
                    raise StoryVideoError(
                        f"Visual media path is reused by assets {visual_paths[visual_resolved]} "
                        f"and {label}."
                    )
                if visual["uri"] in visual_uris:
                    raise StoryVideoError(
                        f"Visual media URI is reused by assets {visual_uris[visual['uri']]} "
                        f"and {label}."
                    )
                visual_paths[visual_resolved] = label
                visual_uris[visual["uri"]] = label
            normalized["members"] = members
            assets[asset_id] = normalized
            continue

        visual, visual_resolved = _validate_visual(
            value["visual"],
            asset_id=asset_id,
            task_root=repository_root,
            asset_dir=asset_dir,
        )
        if visual_resolved in visual_paths:
            raise StoryVideoError(
                f"Visual media path is reused by assets {visual_paths[visual_resolved]} "
                f"and {asset_id}."
            )
        if visual["uri"] in visual_uris:
            raise StoryVideoError(
                f"Visual media URI is reused by assets {visual_uris[visual['uri']]} and {asset_id}."
            )
        visual_paths[visual_resolved] = asset_id
        visual_uris[visual["uri"]] = asset_id
        normalized["visual"] = visual
        if asset_type == "costume":
            character_id = require_utf8_text(
                value["character_id"], f"costume {asset_id} character_id"
            )
            if not ASSET_ID_RE.fullmatch(character_id):
                raise StoryVideoError(
                    f"costume {asset_id} character_id must be a canonical asset ID."
                )
            appearance_state = require_utf8_text(
                value["appearance_state_en"],
                f"costume {asset_id} appearance_state_en",
            )
            normalized.update(
                {
                    "character_id": character_id,
                    "appearance_state_en": appearance_state,
                }
            )
        if asset_type == "location_master":
            included_prop_ids = value["included_prop_ids"]
            if (
                not isinstance(included_prop_ids, list)
                or any(not isinstance(item, str) for item in included_prop_ids)
                or len(included_prop_ids) != len(set(included_prop_ids))
            ):
                raise StoryVideoError(
                    f"location_master {asset_id} included_prop_ids must be a unique string array."
                )
            role_partitions: dict[str, list[str]] = {}
            for field in (
                "embedded_npc_asset_ids",
                "independent_performer_asset_ids",
            ):
                role_asset_ids = value[field]
                if (
                    not isinstance(role_asset_ids, list)
                    or any(not isinstance(item, str) for item in role_asset_ids)
                    or len(role_asset_ids) != len(set(role_asset_ids))
                ):
                    raise StoryVideoError(
                        f"location_master {asset_id} {field} must be a unique string array."
                    )
                role_partitions[field] = list(role_asset_ids)
            role_overlap = set(role_partitions["embedded_npc_asset_ids"]).intersection(
                role_partitions["independent_performer_asset_ids"]
            )
            if role_overlap:
                raise StoryVideoError(
                    f"location_master {asset_id} role partitions overlap: "
                    f"{sorted(role_overlap)}."
                )
            fixed_set_elements_en = value["fixed_set_elements_en"]
            if (
                not isinstance(fixed_set_elements_en, list)
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in fixed_set_elements_en
                )
                or len(fixed_set_elements_en)
                != len({item.strip() for item in fixed_set_elements_en})
            ):
                raise StoryVideoError(
                    f"location_master {asset_id} fixed_set_elements_en must be a "
                    "unique text array."
                )
            normalized.update(
                {
                    "included_prop_ids": list(included_prop_ids),
                    **role_partitions,
                    "fixed_set_elements_en": [
                        item.strip() for item in fixed_set_elements_en
                    ],
                }
            )
        if asset_type == "character":
            normalized["actor_profile"] = _validate_actor_profile(
                value["actor_profile"], asset_id=asset_id
            )
            normalized["body_topology"] = _validate_body_topology(
                value["body_topology"], asset_id=asset_id
            )
        if asset_type == "character":
            voice = _validate_voice(
                value["voice"],
                asset_id=asset_id,
                task_root=repository_root,
                asset_dir=asset_dir,
            )
            audio_path = (
                repository_root / voice["reference"]["path"]
            ).resolve(strict=True)
            audio_uri = voice["reference"]["uri"]
            if audio_path in audio_paths:
                raise StoryVideoError(
                    f"Audio media path is reused by characters {audio_paths[audio_path]} "
                    f"and {asset_id}."
                )
            if audio_uri in audio_uris:
                raise StoryVideoError(
                    f"Audio media URI is reused by characters {audio_uris[audio_uri]} and {asset_id}."
                )
            audio_paths[audio_path] = asset_id
            audio_uris[audio_uri] = asset_id
            normalized["voice"] = voice
        assets[asset_id] = normalized

    for asset_id, asset in assets.items():
        asset_type = asset["type"]
        if asset_type == "costume":
            owner = assets.get(asset["character_id"])
            if not owner or owner.get("type") != "character":
                raise StoryVideoError(
                    f"costume {asset_id} character_id must reference a current character."
                )
        elif asset_type == "location_master":
            for prop_id in asset["included_prop_ids"]:
                prop = assets.get(prop_id)
                if not prop or prop.get("type") != "prop":
                    raise StoryVideoError(
                        f"location_master {asset_id} included_prop_ids contains non-prop {prop_id!r}."
                    )
            for field in (
                "embedded_npc_asset_ids",
                "independent_performer_asset_ids",
            ):
                for role_asset_id in asset[field]:
                    role_asset = assets.get(role_asset_id)
                    if not role_asset or role_asset.get("type") not in {
                        "character",
                        "ensemble_roster",
                    }:
                        raise StoryVideoError(
                            f"location_master {asset_id} {field} contains non-role "
                            f"asset {role_asset_id!r}."
                        )
        elif asset_type == "sound" and asset["owner_character_id"] != "none":
            owner = assets.get(asset["owner_character_id"])
            if not owner or owner.get("type") != "character":
                raise StoryVideoError(
                    f"sound {asset_id} owner_character_id must reference a current character."
                )

    return {
        "contract": "production-design-assets",
        "path_resolution": "repository_root_relative",
        "assets": assets,
    }
