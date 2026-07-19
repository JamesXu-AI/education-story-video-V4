"""Validate one task-local offline aesthetic-analysis package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


CONTRACT = "task-aesthetic-reference"
MANIFEST_RELATIVE_PATH = Path(
    "direct-production-design/aesthetic-reference/manifest.json"
)
MAX_SELECTED_FRAMES = 8
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AestheticReferenceError(RuntimeError):
    """Raised when a task-local aesthetic reference package is unsafe or invalid."""


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AestheticReferenceError(f"{label} must be non-empty text")
    return value.strip()


def _require_sha256(value: Any, label: str) -> str:
    digest = _require_text(value, label)
    if not SHA256_RE.fullmatch(digest):
        raise AestheticReferenceError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AestheticReferenceError(
            f"Missing or invalid aesthetic reference manifest: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise AestheticReferenceError("Aesthetic reference manifest must be one object")
    return value


def _task_local_file(root: Path, value: Any, label: str) -> Path:
    relative = Path(_require_text(value, label))
    if relative.is_absolute():
        raise AestheticReferenceError(f"{label} must be task-root relative")
    try:
        path = (root / relative).resolve(strict=True)
        path.relative_to(root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise AestheticReferenceError(
            f"{label} must resolve to a file inside the task root"
        ) from exc
    if not path.is_file():
        raise AestheticReferenceError(f"{label} must resolve to a regular file")
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_aesthetic_reference(task_root: Path) -> dict[str, Any] | None:
    """Return validated task-local references, or ``None`` when none is declared."""

    root = task_root.expanduser().resolve(strict=True)
    manifest_path = root / MANIFEST_RELATIVE_PATH
    if not manifest_path.exists():
        return None
    value = _load_json(manifest_path)
    if value.get("contract") != CONTRACT or value.get("version") != 1:
        raise AestheticReferenceError(
            "Aesthetic reference manifest must use task-aesthetic-reference v1"
        )

    task_id = _require_text(value.get("task_id"), "task_id")
    if task_id != root.name:
        raise AestheticReferenceError(
            f"Aesthetic reference task_id must equal task directory name {root.name!r}"
        )

    study_path = _task_local_file(root, value.get("study_path"), "study_path")
    if study_path.suffix.casefold() != ".md":
        raise AestheticReferenceError("study_path must identify a Markdown file")

    source = value.get("source_video")
    if not isinstance(source, dict):
        raise AestheticReferenceError("source_video must be one object")
    _require_text(source.get("path"), "source_video.path")
    _require_sha256(source.get("sha256"), "source_video.sha256")
    if source.get("usage") != "offline-aesthetic-analysis-only-never-generation-input":
        raise AestheticReferenceError(
            "source_video usage must prohibit every generation input"
        )

    policy = value.get("reference_policy")
    required_policy = {
        "source_video_generation_allowed": False,
        "selected_frame_generation_allowed": False,
        "selected_frame_direct_downstream_allowed": False,
        "downstream_reference_authority": "project-textual-visual-contract-only",
        "copy_reference_identity_composition_or_story_action": False,
    }
    if policy != required_policy:
        raise AestheticReferenceError(
            "reference_policy must enforce the offline-analysis-only boundary"
        )

    frames = value.get("selected_frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_SELECTED_FRAMES:
        raise AestheticReferenceError(
            f"selected_frames must contain 1-{MAX_SELECTED_FRAMES} records"
        )
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    last_timestamp = -1.0
    for index, frame in enumerate(frames, start=1):
        if not isinstance(frame, dict):
            raise AestheticReferenceError(f"selected frame {index} must be one object")
        frame_id = _require_text(frame.get("frame_id"), f"selected frame {index} id")
        if frame_id in seen_ids:
            raise AestheticReferenceError(f"Duplicate aesthetic frame id: {frame_id}")
        seen_ids.add(frame_id)
        timestamp = frame.get("timestamp_seconds")
        if not isinstance(timestamp, (int, float)) or timestamp <= last_timestamp:
            raise AestheticReferenceError(
                "selected frame timestamps must be numeric and strictly increasing"
            )
        last_timestamp = float(timestamp)
        path = _task_local_file(
            root, frame.get("path"), f"selected frame {frame_id} path"
        )
        if path.suffix.casefold() not in IMAGE_SUFFIXES:
            raise AestheticReferenceError(
                f"selected frame {frame_id} must use a supported image extension"
            )
        if path in seen_paths:
            raise AestheticReferenceError(f"Duplicate aesthetic frame path: {path}")
        seen_paths.add(path)
        expected_digest = _require_sha256(
            frame.get("sha256"), f"selected frame {frame_id} sha256"
        )
        if _file_sha256(path) != expected_digest:
            raise AestheticReferenceError(
                f"selected frame {frame_id} failed its SHA-256 integrity check"
            )
        roles = frame.get("reference_roles_en")
        if not isinstance(roles, list) or not roles:
            raise AestheticReferenceError(
                f"selected frame {frame_id} requires reference_roles_en"
            )
        for role_index, role in enumerate(roles, start=1):
            _require_text(role, f"selected frame {frame_id} role {role_index}")
    translation = value.get("style_translation")
    if not isinstance(translation, dict):
        raise AestheticReferenceError("style_translation must be one object")
    prompt_core = _require_text(
        translation.get("prompt_core_en"), "style_translation.prompt_core_en"
    )
    for field in ("preserve_project_locks_en", "forbidden_imports_en"):
        items = translation.get(field)
        if not isinstance(items, list) or not items:
            raise AestheticReferenceError(f"style_translation.{field} must be non-empty")
        for item_index, item in enumerate(items, start=1):
            _require_text(item, f"style_translation.{field}[{item_index}]")

    return {
        "manifest_path": str(manifest_path),
        "study_path": str(study_path),
        "prompt_core_en": prompt_core,
        "preserve_project_locks_en": list(translation["preserve_project_locks_en"]),
        "forbidden_imports_en": list(translation["forbidden_imports_en"]),
        "reference_count": len(frames),
    }
