"""Generate one Seedream image directly into its final production asset folder."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit
import uuid

from story_video.asset_support import StoryVideoError
from story_video.production_design_plan import (
    ProductionDesignPlanError,
    validate_generation_prompt_text,
)
from story_video.visual_style_contract import VISUAL_STYLE_PROFILE
from providers import seedream


ASSET_KINDS = frozenset(
    {
        "character",
        "costume",
        "location_master",
        "prop",
        "ensemble_roster",
    }
)
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SIZE_RE = re.compile(r"^(?:[1-9][0-9]{2,4}x[1-9][0-9]{2,4}|[1-9][0-9]*[Kk])$")
MAX_REFERENCE_IMAGES = 10
DEFAULT_IMAGE_SIZE = seedream.SEEDREAM_MAX_IMAGE_SIZE
DEFAULT_TIMEOUT = seedream.core.DEFAULT_TIMEOUT


class VisualAssetGenerationError(StoryVideoError):
    """Raised when direct visual-asset generation input or output is invalid."""


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisualAssetGenerationError(f"{label} must be non-empty text.")
    return value.strip()


def _validate_asset_identity(asset_id: str, asset_kind: str) -> tuple[str, str]:
    normalized_id = _require_text(asset_id, "asset_id")
    if not ASSET_ID_RE.fullmatch(normalized_id):
        raise VisualAssetGenerationError(
            "asset_id must use lowercase letters, digits, underscores, or hyphens."
        )
    normalized_kind = _require_text(asset_kind, "asset_kind")
    if normalized_kind not in ASSET_KINDS:
        raise VisualAssetGenerationError(
            "asset_kind must be one of: " + ", ".join(sorted(ASSET_KINDS)) + "."
        )
    return normalized_id, normalized_kind


def load_visual_prompt(prompt_file: Path) -> tuple[str, Path]:
    source = prompt_file.expanduser()
    try:
        source = source.resolve(strict=True)
        prompt = source.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError) as exc:
        raise VisualAssetGenerationError(
            f"prompt_file must identify readable UTF-8 text: {prompt_file}"
        ) from exc
    if not source.is_file():
        raise VisualAssetGenerationError(
            f"prompt_file must identify a regular file: {prompt_file}"
        )
    return _require_text(prompt, "prompt_file content"), source


def validate_provider_prompt(
    task_root: Path, *, asset_kind: str, asset_prompt: str
) -> str:
    task_path = task_root / "task.json"
    try:
        task = json.loads(task_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisualAssetGenerationError(
            f"Invalid task.json visual authority: {task_path}"
        ) from exc
    if (
        not isinstance(task, dict)
        or task.get("visual_style_profile") != VISUAL_STYLE_PROFILE
    ):
        raise VisualAssetGenerationError(
            "task.json visual_style_profile must be soft_cute_3d_healing_animation."
        )
    brief = _require_text(asset_prompt, "asset-specific prompt")
    try:
        return validate_generation_prompt_text(brief, asset_type=asset_kind)
    except ProductionDesignPlanError as exc:
        raise VisualAssetGenerationError(str(exc)) from exc


def _reference_values(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise VisualAssetGenerationError(
            "reference_images must be an ordered array, not one string."
        )
    references = list(values)
    if len(references) > MAX_REFERENCE_IMAGES:
        raise VisualAssetGenerationError(
            "Visual asset generation accepts 0-10 ordered reference images."
        )
    return [
        _require_text(value, f"reference image {index}")
        for index, value in enumerate(references, start=1)
    ]


def _normalize_reference(
    task_root: Path, value: str, *, index: int
) -> tuple[str, str]:
    parsed = urlsplit(value)
    if parsed.scheme:
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise VisualAssetGenerationError(
                f"Reference image {index} must be a local file or absolute HTTP(S) URL."
            )
        return (
            urlunsplit(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path or "/",
                    parsed.query,
                    "",
                )
            ),
            "http_url",
        )
    local = Path(value).expanduser()
    if not local.is_absolute():
        local = task_root / local
    try:
        local = local.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise VisualAssetGenerationError(
            f"Reference image {index} does not identify an existing local file: {value}"
        ) from exc
    if not local.is_file():
        raise VisualAssetGenerationError(
            f"Reference image {index} must identify a regular local file: {value}"
        )
    return str(local), "local_file"


def resolve_ordered_references(
    task_root: Path, values: Iterable[str] | None
) -> tuple[list[str], list[dict[str, Any]]]:
    resolved: list[str] = []
    audit: list[dict[str, Any]] = []
    for index, declared in enumerate(_reference_values(values), start=1):
        normalized, source_kind = _normalize_reference(
            task_root, declared, index=index
        )
        try:
            provider_value = seedream.core.resolve_input(
                normalized,
                kind="image",
                upload_local=False,
            )
        except seedream.core.SeedMediaError as exc:
            raise VisualAssetGenerationError(str(exc)) from exc
        resolved.append(provider_value)
        audit.append(
            {
                "order": index,
                "provider_image_index": index - 1,
                "declared_source": declared,
                "normalized_source": normalized,
                "source_kind": source_kind,
            }
        )
    return resolved, audit


def build_provider_request(
    *, prompt: str, reference_images: Iterable[str], size: str
) -> dict[str, Any]:
    image_size = _require_text(size, "size")
    if not SIZE_RE.fullmatch(image_size):
        raise VisualAssetGenerationError(
            "size must be WIDTHxHEIGHT or a provider-supported resolution token."
        )
    images = list(reference_images)
    request: dict[str, Any] = {
        "model": seedream.SEEDREAM_MODEL_ID,
        "prompt": _require_text(prompt, "prompt"),
        "size": image_size,
        "output_format": "png",
        "response_format": "url",
        "watermark": False,
    }
    if images:
        request["image"] = images[0] if len(images) == 1 else images
    return request


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_text_atomic(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _final_output_path(asset_root: Path, output_path: Path) -> Path:
    asset_root = asset_root.expanduser().resolve()
    value = output_path.expanduser()
    if not value.is_absolute():
        value = asset_root / value
    value = value.resolve()
    if value == asset_root or asset_root not in value.parents:
        raise VisualAssetGenerationError(
            "output_path must be a file inside the repository-owned assets directory."
        )
    value.parent.mkdir(parents=True, exist_ok=True)
    return value


def _single_output_url(response: dict[str, Any]) -> str:
    data = response.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise VisualAssetGenerationError(
            "Seedream visual asset generation must return exactly one image result."
        )
    item = data[0]
    if item.get("error"):
        raise VisualAssetGenerationError("Seedream returned an image generation error.")
    url = item.get("url")
    if not isinstance(url, str) or not url.strip():
        raise VisualAssetGenerationError("Seedream response lacks the image URL.")
    url = url.strip()
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise VisualAssetGenerationError(
            "Seedream image URL must be absolute HTTP(S)."
        )
    return url


def generate_visual_asset(
    *,
    task_root: Path,
    asset_id: str,
    asset_kind: str,
    prompt_file: Path,
    output_path: Path,
    asset_root: Path,
    reference_images: Iterable[str] | None = None,
    size: str = DEFAULT_IMAGE_SIZE,
    dry_run: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Generate directly to the declared final image and keep evidence beside it."""

    try:
        root = task_root.expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise VisualAssetGenerationError(
            f"task_root must identify an existing directory: {task_root}"
        ) from exc
    normalized_id, normalized_kind = _validate_asset_identity(asset_id, asset_kind)
    prompt_input = prompt_file.expanduser()
    if not prompt_input.is_absolute():
        prompt_input = root / prompt_input
    prompt, prompt_source = load_visual_prompt(prompt_input)
    provider_prompt = validate_provider_prompt(
        root, asset_kind=normalized_kind, asset_prompt=prompt
    )
    references, reference_plan = resolve_ordered_references(root, reference_images)
    provider_request = build_provider_request(
        prompt=provider_prompt, reference_images=references, size=size
    )
    if not dry_run and (
        isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1
    ):
        raise VisualAssetGenerationError("timeout must be a positive integer.")

    final_path = _final_output_path(asset_root, output_path)
    stem = final_path.stem
    prompt_path = final_path.parent / f"{stem}.prompt.txt"
    request_path = final_path.parent / f"{stem}.request.json"
    response_path = final_path.parent / f"{stem}.response.json"
    _write_text_atomic(prompt_path, provider_prompt)
    _write_json_atomic(
        request_path,
        {
            "request_type": "visual_asset_seedream_generation",
            "asset": {"id": normalized_id, "kind": normalized_kind},
            "output_path": final_path.relative_to(asset_root.parent).as_posix(),
            "prompt_source": str(prompt_source),
            "reference_plan": reference_plan,
            "provider_request": provider_request,
        },
    )
    result: dict[str, Any] = {
        "status": "planned" if dry_run else "ready",
        "asset_id": normalized_id,
        "asset_kind": normalized_kind,
        "output_path": str(final_path),
        "prompt_path": str(prompt_path),
        "request_path": str(request_path),
        "response_path": None,
        "source_url": None,
        "seedream_generation_calls": 0 if dry_run else 1,
    }
    if dry_run:
        return result

    try:
        response = seedream.generate_image(provider_request, timeout=timeout)
    except seedream.core.SeedMediaError as exc:
        raise VisualAssetGenerationError(
            f"Seedream visual asset generation failed: {exc}"
        ) from exc
    if not isinstance(response, dict):
        raise VisualAssetGenerationError(
            "Seedream visual asset response must be a JSON object."
        )
    source_download_url = _single_output_url(response)
    temporary = final_path.with_name(f".{final_path.name}.download")
    temporary.unlink(missing_ok=True)
    try:
        downloaded = Path(
            seedream.core.download_url(
                source_download_url, temporary, timeout=max(timeout, 300)
            )
        )
        if not downloaded.is_file() or downloaded.stat().st_size <= 0:
            raise VisualAssetGenerationError(
                "Downloaded Seedream visual asset is missing or empty."
            )
        downloaded.replace(final_path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, VisualAssetGenerationError):
            raise
        raise VisualAssetGenerationError(
            f"Failed to download Seedream visual asset: {exc}"
        ) from exc
    stored = seedream.core.tos_upload_path(
        final_path,
        key=seedream.core.production_asset_key(
            normalized_kind, normalized_id, final_path.name
        ),
    )
    source_url = stored["public_url"]
    _write_json_atomic(response_path, seedream.core.without_tos_signatures(response))
    result.update(
        {
            "response_path": str(response_path),
            "source_url": source_url,
        }
    )
    return result
