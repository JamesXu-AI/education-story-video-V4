#!/usr/bin/env python3
"""Generate audiovisual clips from materialized Seed Master Route B Scripts."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
PRODUCTION_DESIGN_SCRIPT_ROOT = REPOSITORY_ROOT / "direct-production-design" / "scripts"
SCREENPLAY_SCRIPT_ROOT = REPOSITORY_ROOT / "screenplay-writer" / "scripts"
for script_root in (SCRIPT_ROOT, PRODUCTION_DESIGN_SCRIPT_ROOT, SCREENPLAY_SCRIPT_ROOT):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

import providers  # noqa: E402

SHARED_PROVIDER_PATH = REPOSITORY_ROOT / "direct-production-design" / "scripts" / "providers"
if str(SHARED_PROVIDER_PATH) not in providers.__path__:
    providers.__path__.append(str(SHARED_PROVIDER_PATH))

from story_video.seed_master_runtime import (  # noqa: E402
    SCRIPT_DIR_RELATIVE,
    load_execution_plan,
    storyboard_segment_rows,
    parse_segment_script as parse_seed_master_script,
    sha256_file,
    token_sort_key,
)
from preflight_segment import preflight_segment  # noqa: E402
from providers import seedance  # noqa: E402
from validate_segment_scripts import validate_task as validate_segment_scripts  # noqa: E402
from incremental_boundary_precheck import (  # noqa: E402
    prepare_adjacent_boundary_prechecks,
)


PENDING_DIRNAME = ".pending"
DEPARTMENT_DIRNAME = "virtual-production"
SCRIPTS_DIRNAME = "seedance-segment-scripts"
GENERATION_DIRNAME = "generation-segments"
PROVIDER_ATTEMPTS_DIRNAME = "provider-attempts"
ACTIVE_ATTEMPT_DIRNAME = "active"
EXECUTION_LOCK_FILENAME = "generation.lock"
SUMMARY_FILENAME = "segment-generation-summary.json"
SCRIPT_RE = re.compile(r"^segment-([0-9]{3,})\.md$")
TERMINAL_STATES = {"succeeded", "failed", "cancelled", "expired"}
MAX_PROVIDER_ATTEMPTS = 3
MAX_MODERATION_ATTEMPTS = 2
MODERATION_FAILURE_RE = re.compile(
    r"moderation|unsafe|content[-_ ]?policy|output[-_ ]?(?:filter|moderation)",
    re.IGNORECASE,
)
PRINT_LOCK = threading.Lock()


class SegmentGenerationError(RuntimeError):
    pass


def announce(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SegmentGenerationError(f"Missing or invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SegmentGenerationError(f"Expected one JSON object: {path}")
    return value


def parse_segment_script(path: Path, *, task_dir: Path | None = None) -> dict[str, Any]:
    path = path.expanduser().resolve()
    task_root = task_dir.expanduser().resolve() if task_dir else path.parents[3]
    parsed = parse_seed_master_script(path)
    plan = load_execution_plan(task_root, parsed["segment_id"])
    if plan.get("source_script_sha256") != parsed["script_sha256"]:
        raise SegmentGenerationError(f"{path.name} execution plan is stale")
    media = plan.get("media_bindings")
    if not isinstance(media, list):
        raise SegmentGenerationError(f"{path.name} execution plan has no media bindings")
    static_images = [
        item
        for item in media
        if item.get("source_kind") == "asset_catalog"
        and item.get("provider_role") == "reference_image"
    ]
    static_audio = [
        item
        for item in media
        if item.get("source_kind") == "asset_catalog"
        and item.get("provider_role") == "reference_audio"
    ]
    runtime_media = [item for item in media if item.get("source_kind") != "asset_catalog"]
    shooting = plan["shooting_plan"]
    return {
        "number": parsed["number"],
        "generation_task_id": parsed["segment_id"],
        "duration": parsed["duration"],
        "prompt": parsed["prompt"],
        "script_path": path,
        "script_sha256": parsed["script_sha256"],
        "execution_plan": plan,
        "execution_plan_path": (
            task_root
            / ".pending/virtual-production/seedance-execution-plans"
            / f"{parsed['segment_id']}.json"
        ),
        "references": static_images,
        "audio_references": static_audio,
        "runtime_media": runtime_media,
        "shooting_schedule_mode": shooting["schedule_mode"],
        "planned_wave": shooting["planned_wave"],
        "depends_on_segment_ids": shooting["depends_on_segment_ids"],
        "operation": shooting["operation"],
        "required_predecessor_evidence": shooting["required_predecessor_evidence"],
        "seedance_parameters": plan["seedance_parameters"],
    }


def _task_contract(task_dir: Path) -> dict[str, str]:
    task = read_json(task_dir / "task.json")
    expected_audio_sources = {
        "voice_audio_source": "speaker_reference_audio",
        "dialogue_source": "seedance",
    }
    for field, expected in expected_audio_sources.items():
        if task.get(field) != expected:
            raise SegmentGenerationError(f"task.json {field} must be {expected}.")
    task_input = task.get("input")
    if not isinstance(task_input, dict):
        raise SegmentGenerationError("task.json input must be an object.")
    supported_resolutions = {"480p", "720p", "1080p", "4k"}
    resolution = str(task_input.get("resolution") or "").strip().lower()
    ratio = task_input.get("aspect_ratio")
    if resolution not in supported_resolutions:
        raise SegmentGenerationError("task.json input.resolution is unsupported.")
    if ratio not in {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"}:
        raise SegmentGenerationError("task.json input.aspect_ratio is unsupported.")
    return {"resolution": resolution, "ratio": str(ratio)}


def discover_segments(
    task_dir: Path, *, segment_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    validate_segment_scripts(task_dir, segment_ids=segment_ids)
    all_ids = [str(item["segment_id"]) for item in storyboard_segment_rows(task_dir)]
    selected_ids = all_ids if segment_ids is None else segment_ids
    script_dir = task_dir / SCRIPT_DIR_RELATIVE
    paths = [script_dir / f"{segment_id}.md" for segment_id in selected_ids]
    segments = [parse_segment_script(path, task_dir=task_dir) for path in paths]
    if [segment["generation_task_id"] for segment in segments] != selected_ids:
        raise SegmentGenerationError("Seed Master Segment Script order is not authoritative")
    if segment_ids is None and sum(segment["duration"] for segment in segments) > 240:
        raise SegmentGenerationError("Complete Seedance picture exceeds 240 seconds.")
    return segments


def _extract_silent_tail(source_video: Path, output: Path) -> float:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SegmentGenerationError("ffmpeg and ffprobe are required for matched-cut evidence")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-sseof",
                "-2.000",
                "-i",
                str(source_video),
                "-t",
                "2.000",
                "-map",
                "0:v:0",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "0",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(output),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        probe = json.loads(completed.stdout)
        duration = float((probe.get("format") or {}).get("duration"))
        stream_types = {
            item.get("codec_type")
            for item in probe.get("streams") or []
            if isinstance(item, dict)
        }
    except (
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise SegmentGenerationError(f"Could not prepare final 2.0s evidence: {exc}") from exc
    if not output.is_file() or not 1.95 <= duration <= 2.05 or stream_types != {"video"}:
        raise SegmentGenerationError("Matched-cut evidence must be an exact silent 2.0s video tail")
    return duration


def _runtime_reference_media_content(
    segment: dict[str, Any], *, task_dir: Path
) -> list[dict[str, Any]]:
    bindings = segment["runtime_media"]
    if not bindings:
        return []
    source_ids = {item["source_segment_id"] for item in bindings}
    attempt_ids = {item["source_provider_attempt_id"] for item in bindings}
    if len(source_ids) != 1 or len(attempt_ids) != 1:
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} runtime bindings must use one predecessor attempt"
        )
    source_id = next(iter(source_ids))
    source_attempt_id = next(iter(attempt_ids))
    source_dir = (
        task_dir / PENDING_DIRNAME / DEPARTMENT_DIRNAME / GENERATION_DIRNAME / source_id
    )
    source_record = read_json(source_dir / "production-record.json")
    source_artifacts = read_json(source_dir / "artifacts.json")
    if (
        source_record.get("status") != "GENERATED"
        or source_record.get("provider_attempt_id") != source_attempt_id
        or source_artifacts.get("provider_attempt_id") != source_attempt_id
    ):
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} is not locked to the current {source_id} attempt"
        )
    input_root = (
        task_dir
        / PENDING_DIRNAME
        / DEPARTMENT_DIRNAME
        / "runtime-reference-inputs"
        / segment["generation_task_id"]
    )
    input_root.mkdir(parents=True, exist_ok=True)
    record_path = input_root / "execution-media.json"
    expected_identity = {
        "contract": "seedance-runtime-reference-input-v1",
        "segment_id": segment["generation_task_id"],
        "source_segment_id": source_id,
        "source_provider_attempt_id": source_attempt_id,
        "execution_plan_sha256": sha256_file(segment["execution_plan_path"]),
    }
    if record_path.is_file():
        record = read_json(record_path)
        media = record.get("media")
        if (
            any(record.get(key) != value for key, value in expected_identity.items())
            or not isinstance(media, list)
            or len(media) != len(bindings)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("url"), str)
                or not (input_root / str(item.get("local_filename") or "")).is_file()
                for item in media
            )
        ):
            raise SegmentGenerationError(
                f"{segment['generation_task_id']} cached runtime media is stale"
            )
    else:
        media: list[dict[str, Any]] = []
        for binding in sorted(bindings, key=lambda item: token_sort_key(item["provider_token"])):
            source_kind = binding["source_kind"]
            token = binding["provider_token"]
            if source_kind == "provider_last_frame":
                source = source_dir / "last-frame.png"
                local = input_root / f"{token.removeprefix('@').lower()}-provider-last-frame.png"
                shutil.copy2(source, local)
                provider_type = "image_url"
                duration = 0.0
                audio_included = False
            elif source_kind == "complete_predecessor_video":
                source = source_dir / "video.mp4"
                local = input_root / f"{token.removeprefix('@').lower()}-complete-predecessor.mp4"
                shutil.copy2(source, local)
                probe = _probe_media(local)
                provider_type = "video_url"
                duration = float(probe["duration_seconds"])
                audio_included = True
            elif source_kind == "final_2s_silent_video":
                source = source_dir / "video.mp4"
                local = input_root / f"{token.removeprefix('@').lower()}-final-2s-silent.mp4"
                duration = _extract_silent_tail(source, local)
                provider_type = "video_url"
                audio_included = False
            else:
                raise SegmentGenerationError(f"Unsupported runtime source kind: {source_kind}")
            if not source.is_file() or not local.is_file():
                raise SegmentGenerationError(f"Missing runtime evidence for {token}")
            upload = seedance.core.tos_upload_path(
                local, kind=f"inputs/{source_kind.replace('_', '-')}"
            )
            media.append(
                {
                    "provider_token": token,
                    "provider_type": provider_type,
                    "source_kind": source_kind,
                    "local_filename": local.name,
                    "duration_seconds": duration,
                    "audio_included": audio_included,
                    "url": upload["public_url"],
                    "tos": upload,
                }
            )
        record = {**expected_identity, "media": media}
        write_json(record_path, record)
    content: list[dict[str, Any]] = []
    for item in record["media"]:
        if item["provider_type"] == "image_url":
            payload = {
                "type": "image_url",
                "image_url": {"url": item["url"]},
                "role": "reference_image",
            }
        elif item["provider_type"] == "video_url":
            payload = {
                "type": "video_url",
                "video_url": {"url": item["url"]},
                "role": "reference_video",
            }
        else:
            raise SegmentGenerationError("Unsupported persisted runtime provider type")
        payload["_provider_token"] = item["provider_token"]
        content.append(payload)
    return content


def request_payload(
    segment: dict[str, Any], *, task_dir: Path, resolution: str, ratio: str
) -> dict[str, Any]:
    parameters = segment["seedance_parameters"]
    if parameters["resolution"] != resolution or parameters["ratio"] != ratio:
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} task output settings changed after materialization"
        )
    media_content: list[dict[str, Any]] = []
    media_content.extend(
        {
            "type": "image_url",
            "image_url": {"url": reference["uri"]},
            "role": "reference_image",
            "_provider_token": reference["provider_token"],
        }
        for reference in segment["references"]
    )
    media_content.extend(
        {
            "type": "audio_url",
            "audio_url": {"url": reference["uri"]},
            "role": "reference_audio",
            "_provider_token": reference["provider_token"],
        }
        for reference in segment["audio_references"]
    )
    media_content.extend(_runtime_reference_media_content(segment, task_dir=task_dir))
    expected_tokens = [
        item["provider_token"]
        for item in segment["execution_plan"]["media_bindings"]
    ]
    actual_tokens = sorted(
        [item["_provider_token"] for item in media_content], key=token_sort_key
    )
    if actual_tokens != expected_tokens or len(actual_tokens) != len(set(actual_tokens)):
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} runtime media differs from the private plan"
        )
    content: list[dict[str, Any]] = [{"type": "text", "text": segment["prompt"]}]
    for item in sorted(media_content, key=lambda value: token_sort_key(value["_provider_token"])):
        content.append({key: value for key, value in item.items() if key != "_provider_token"})
    return {**parameters, "content": content}


def _probe_media(path: Path, *, timeout: int = 60) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise SegmentGenerationError("ffprobe is required to verify generated media.")
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        payload = json.loads(completed.stdout)
        duration = float((payload.get("format") or {}).get("duration"))
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SegmentGenerationError(f"Could not probe generated media {path}: {exc}") from exc
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    result = {
        "duration_seconds": duration,
        "has_video_stream": any(
            isinstance(stream, dict) and stream.get("codec_type") == "video"
            for stream in streams
        ),
        "has_audio_stream": any(
            isinstance(stream, dict) and stream.get("codec_type") == "audio"
            for stream in streams
        ),
        "streams": streams,
    }
    if not result["has_video_stream"] or not result["has_audio_stream"]:
        raise SegmentGenerationError(
            f"Generated Segment must contain video and Seedance native audio: {path}"
        )
    return result


def _provider_task_id(response: dict[str, Any]) -> str:
    task_id = response.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise SegmentGenerationError("Seedance create response has no task ID.")
    return task_id


def _wait_for_task(
    task_id: str,
    *,
    segment_id: str,
    output_dir: Path,
    poll_interval: float,
    wait_timeout: float,
    request_timeout: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + wait_timeout
    while True:
        result = seedance.get_video_task(task_id, timeout=request_timeout)
        write_json(output_dir / "seedance-poll-response.json", result)
        status = str(result.get("status") or "unknown")
        announce(f"STATUS {segment_id} task={task_id} status={status}")
        if status in TERMINAL_STATES:
            return result
        if time.monotonic() >= deadline:
            raise SegmentGenerationError(
                f"Timed out waiting for {segment_id} provider task {task_id}."
            )
        time.sleep(poll_interval)


def _retry_or_fail(
    *, active_dir: Path, segment_id: str, attempt_number: int,
    moderation_failures: int, failure_text: str
) -> tuple[int, int]:
    next_moderation_failures = moderation_failures + int(
        bool(MODERATION_FAILURE_RE.search(failure_text))
    )
    if attempt_number >= MAX_PROVIDER_ATTEMPTS:
        raise SegmentGenerationError(
            f"{segment_id} reached the maximum of {MAX_PROVIDER_ATTEMPTS} attempts: "
            f"{failure_text}"
        )
    if next_moderation_failures >= MAX_MODERATION_ATTEMPTS:
        raise SegmentGenerationError(
            f"{segment_id} failed moderation twice with the unchanged request."
        )
    if active_dir.exists():
        shutil.rmtree(active_dir)
    return attempt_number + 1, next_moderation_failures


def _load_resumable_attempt(
    segment: dict[str, Any], active_dir: Path, request: dict[str, Any]
) -> dict[str, Any] | None:
    if not active_dir.exists():
        return None
    required = (
        active_dir / "segment-script.md",
        active_dir / "seedance-request.json",
        active_dir / "seedance-submission.json",
    )
    if not all(path.is_file() for path in required):
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} active attempt is incomplete."
        )
    if (active_dir / "segment-script.md").read_text(encoding="utf-8") != segment[
        "script_path"
    ].read_text(encoding="utf-8"):
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} active attempt uses an older Segment Script."
        )
    if read_json(active_dir / "seedance-request.json") != request:
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} active attempt uses a different request."
        )
    submission = read_json(active_dir / "seedance-submission.json")
    if submission.get("generation_task_id") != segment["generation_task_id"]:
        raise SegmentGenerationError("Active provider task belongs to another Segment.")
    return submission


def _completed_result(
    segment: dict[str, Any], directory: Path, submission: dict[str, Any]
) -> dict[str, Any] | None:
    if submission.get("status") != "succeeded":
        return None
    video_path = directory / "video.mp4"
    record_path = directory / "production-record.json"
    last_frame_path = directory / "last-frame.png"
    if not video_path.is_file() or not last_frame_path.is_file() or not record_path.is_file():
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} succeeded attempt lacks video, final frame, or record."
        )
    record = read_json(record_path)
    attempt_number = submission.get("attempt_number")
    expected_attempt_id = (
        f"{segment['generation_task_id']}__attempt-{int(attempt_number):04d}"
        if isinstance(attempt_number, int) and attempt_number > 0
        else None
    )
    if (
        record.get("status") != "GENERATED"
        or record.get("segment_id") != segment["generation_task_id"]
        or record.get("provider_attempt_id") != expected_attempt_id
        or record.get("seed_master_script_sha256") != segment["script_sha256"]
        or record.get("seedance_execution_plan_sha256")
        != sha256_file(segment["execution_plan_path"])
        or record.get("operation") != segment["operation"]
    ):
        raise SegmentGenerationError(
            f"{segment['generation_task_id']} production record is invalid."
        )
    return {
        "segment_id": segment["generation_task_id"],
        "provider_task_id": submission["provider_task_id"],
        "status": "succeeded",
        "video_path": str(video_path.resolve()),
        "last_frame_path": str(last_frame_path.resolve()),
        "provider_attempt_id": expected_attempt_id,
        "seed_master_script_sha256": segment["script_sha256"],
        "seedance_execution_plan_sha256": sha256_file(
            segment["execution_plan_path"]
        ),
        "operation": segment["operation"],
    }


def generate_one(
    segment: dict[str, Any],
    *,
    task_dir: Path,
    resolution: str,
    ratio: str,
    poll_interval: float,
    wait_timeout: float,
    request_timeout: int,
    attempt_number: int = 1,
    moderation_failures: int = 0,
) -> dict[str, Any]:
    segment_id = segment["generation_task_id"]
    published_dir = (
        task_dir / PENDING_DIRNAME / DEPARTMENT_DIRNAME / GENERATION_DIRNAME / segment_id
    )
    preflight_segment(
        task_dir=task_dir, segment_script_path=segment["script_path"]
    )
    request = request_payload(
        segment, task_dir=task_dir, resolution=resolution, ratio=ratio
    )
    if published_dir.is_dir():
        submission = _load_resumable_attempt(segment, published_dir, request)
        if submission is None:
            raise SegmentGenerationError(f"{segment_id} published directory is incomplete.")
        completed = _completed_result(segment, published_dir, submission)
        if completed is None:
            raise SegmentGenerationError(f"{segment_id} published directory is not successful.")
        announce(f"SKIP {segment_id} generated video already exists")
        return completed

    attempt_parent = (
        task_dir
        / PENDING_DIRNAME
        / DEPARTMENT_DIRNAME
        / PROVIDER_ATTEMPTS_DIRNAME
        / segment_id
    )
    attempt_parent.mkdir(parents=True, exist_ok=True)
    active_dir = attempt_parent / ACTIVE_ATTEMPT_DIRNAME
    submission = _load_resumable_attempt(segment, active_dir, request)
    if submission is not None:
        status = str(submission.get("status") or "")
        if status == "succeeded":
            completed = _completed_result(segment, active_dir, submission)
            if completed is None:
                raise SegmentGenerationError(f"{segment_id} succeeded attempt is incomplete.")
            published_dir.parent.mkdir(parents=True, exist_ok=True)
            active_dir.replace(published_dir)
            completed["video_path"] = str((published_dir / "video.mp4").resolve())
            completed["last_frame_path"] = str(
                (published_dir / "last-frame.png").resolve()
            )
            return completed
        if status in TERMINAL_STATES:
            current_attempt = int(submission.get("attempt_number") or attempt_number)
            attempt_number, moderation_failures = _retry_or_fail(
                active_dir=active_dir,
                segment_id=segment_id,
                attempt_number=current_attempt,
                moderation_failures=moderation_failures,
                failure_text="\n".join(
                    path.read_text(encoding="utf-8", errors="replace")
                    for path in active_dir.glob("*.json")
                ),
            )
            announce(f"RETRY {segment_id} next_attempt={attempt_number}")
            return generate_one(
                segment,
                task_dir=task_dir,
                resolution=resolution,
                ratio=ratio,
                poll_interval=poll_interval,
                wait_timeout=wait_timeout,
                request_timeout=request_timeout,
                attempt_number=attempt_number,
                moderation_failures=moderation_failures,
            )
        task_id = str(submission.get("provider_task_id") or "")
        if not task_id:
            raise SegmentGenerationError(f"{segment_id} active attempt has no provider task ID.")
        announce(f"RESUME {segment_id} task={task_id}")
    else:
        if not 1 <= attempt_number <= MAX_PROVIDER_ATTEMPTS:
            raise SegmentGenerationError(f"{segment_id} has invalid attempt number")
        active_dir.mkdir(parents=False, exist_ok=False)
        shutil.copy2(segment["script_path"], active_dir / "segment-script.md")
        write_json(active_dir / "seedance-request.json", request)
        try:
            response = seedance.create_video_task(request, timeout=request_timeout)
            write_json(active_dir / "seedance-create-response.json", response)
            task_id = _provider_task_id(response)
        except Exception as exc:
            attempt_number, moderation_failures = _retry_or_fail(
                active_dir=active_dir,
                segment_id=segment_id,
                attempt_number=attempt_number,
                moderation_failures=moderation_failures,
                failure_text=str(exc),
            )
            announce(f"RETRY {segment_id} create_failure next_attempt={attempt_number}")
            return generate_one(
                segment,
                task_dir=task_dir,
                resolution=resolution,
                ratio=ratio,
                poll_interval=poll_interval,
                wait_timeout=wait_timeout,
                request_timeout=request_timeout,
                attempt_number=attempt_number,
                moderation_failures=moderation_failures,
            )
        submission = {
            "contract": "seedance-submission",
            "generation_task_id": segment_id,
            "provider_task_id": task_id,
            "attempt_number": attempt_number,
            "status": str(response.get("status") or "submitted"),
            "generate_audio": True,
        }
        write_json(active_dir / "seedance-submission.json", submission)
        announce(f"SUBMITTED {segment_id} task={task_id}")

    result = _wait_for_task(
        task_id,
        segment_id=segment_id,
        output_dir=active_dir,
        poll_interval=poll_interval,
        wait_timeout=wait_timeout,
        request_timeout=request_timeout,
    )
    status = str(result.get("status") or "unknown")
    submission = read_json(active_dir / "seedance-submission.json")
    submission["status"] = status
    write_json(active_dir / "seedance-submission.json", submission)
    if status != "succeeded":
        attempt_number, moderation_failures = _retry_or_fail(
            active_dir=active_dir,
            segment_id=segment_id,
            attempt_number=int(submission["attempt_number"]),
            moderation_failures=moderation_failures,
            failure_text=json.dumps(result, ensure_ascii=False),
        )
        announce(
            f"RETRY {segment_id} terminal={status} next_attempt={attempt_number}"
        )
        return generate_one(
            segment,
            task_dir=task_dir,
            resolution=resolution,
            ratio=ratio,
            poll_interval=poll_interval,
            wait_timeout=wait_timeout,
            request_timeout=request_timeout,
            attempt_number=attempt_number,
            moderation_failures=moderation_failures,
        )

    content = result.get("content")
    video_url = content.get("video_url") if isinstance(content, dict) else None
    last_frame_url = content.get("last_frame_url") if isinstance(content, dict) else None
    if not isinstance(video_url, str) or not video_url:
        raise SegmentGenerationError(f"{segment_id} provider returned no video URL.")
    if not isinstance(last_frame_url, str) or not last_frame_url:
        raise SegmentGenerationError(
            f"{segment_id} provider returned no final frame despite return_last_frame=true."
        )
    video_path = active_dir / "video.mp4"
    seedance.core.download_url(video_url, video_path, timeout=request_timeout)
    last_frame_path = active_dir / "last-frame.png"
    seedance.core.download_url(last_frame_url, last_frame_path, timeout=request_timeout)
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise SegmentGenerationError(f"Downloaded video is empty: {video_path}")
    if not last_frame_path.is_file() or last_frame_path.stat().st_size <= 0:
        raise SegmentGenerationError(f"Downloaded final frame is empty: {last_frame_path}")
    media_probe = _probe_media(video_path, timeout=min(request_timeout, 60))
    attempt_number = int(submission["attempt_number"])
    provider_attempt_id = f"{segment_id}__attempt-{attempt_number:04d}"
    write_json(
        active_dir / "artifacts.json",
        {
            "contract": "generated-segment-artifacts",
            "segment_id": segment_id,
            "provider_task_id": task_id,
            "provider_attempt_id": provider_attempt_id,
            "video_path": "video.mp4",
            "video_source_url": seedance.core.persistent_tos_url(video_url),
            "last_frame_path": "last-frame.png",
            "last_frame_source_url": seedance.core.persistent_tos_url(last_frame_url),
            "video_bytes": video_path.stat().st_size,
            "last_frame_bytes": last_frame_path.stat().st_size,
            "media_probe": media_probe,
        },
    )
    write_json(
        active_dir / "production-record.json",
        {
            "contract": "generated-segment-production-record",
            "segment_id": segment_id,
            "provider_task_id": task_id,
            "provider_attempt_id": provider_attempt_id,
            "seed_master_script_sha256": segment["script_sha256"],
            "seedance_execution_plan_sha256": sha256_file(
                segment["execution_plan_path"]
            ),
            "operation": segment["operation"],
            "submission_revision": attempt_number,
            "segment_script_path": "segment-script.md",
            "request_path": "seedance-request.json",
            "video_path": "video.mp4",
            "last_frame_path": "last-frame.png",
            "artifacts_path": "artifacts.json",
            "generate_audio": True,
            "status": "GENERATED",
        },
    )
    published_dir.parent.mkdir(parents=True, exist_ok=True)
    active_dir.replace(published_dir)
    announce(
        f"DOWNLOADED {segment_id} task={task_id} "
        f"bytes={(published_dir / 'video.mp4').stat().st_size}"
    )
    return {
        "segment_id": segment_id,
        "provider_task_id": task_id,
        "status": "succeeded",
        "video_path": str((published_dir / "video.mp4").resolve()),
        "last_frame_path": str((published_dir / "last-frame.png").resolve()),
        "provider_attempt_id": provider_attempt_id,
        "seed_master_script_sha256": segment["script_sha256"],
        "seedance_execution_plan_sha256": sha256_file(
            segment["execution_plan_path"]
        ),
        "operation": segment["operation"],
    }


def _published_segment_ready(task_dir: Path, segment_id: str) -> bool:
    directory = (
        task_dir / PENDING_DIRNAME / DEPARTMENT_DIRNAME / GENERATION_DIRNAME / segment_id
    )
    record_path = directory / "production-record.json"
    if not record_path.is_file():
        return False
    try:
        record = read_json(record_path)
    except SegmentGenerationError:
        return False
    return (
        record.get("status") == "GENERATED"
        and record.get("segment_id") == segment_id
        and (directory / "video.mp4").is_file()
        and (directory / "last-frame.png").is_file()
    )


def _storyboard_topological_waves(
    segments: list[dict[str, Any]], *, task_dir: Path
) -> list[list[str]]:
    """Execute the exact Seed Master planned waves and dependency edges."""

    order = [segment["generation_task_id"] for segment in segments]
    segment_by_id = {
        segment["generation_task_id"]: segment for segment in segments
    }
    selected = set(order)
    dependencies = {
        segment["generation_task_id"]: set(segment["depends_on_segment_ids"])
        for segment in segments
    }
    external = {
        dependency
        for values in dependencies.values()
        for dependency in values
        if dependency not in selected
    }
    missing_external = sorted(
        dependency
        for dependency in external
        if not _published_segment_ready(task_dir, dependency)
    )
    if missing_external:
        raise SegmentGenerationError(
            "Selected serial Segments require generated continuity sources: "
            + ", ".join(missing_external)
        )
    completed = set(external)
    if any(
        isinstance(segment.get("planned_wave"), bool)
        or not isinstance(segment.get("planned_wave"), int)
        or segment["planned_wave"] < 0
        for segment in segments
    ):
        raise SegmentGenerationError("Every Segment requires one non-negative planned_wave")
    waves: list[list[str]] = []
    for planned_wave in sorted({segment["planned_wave"] for segment in segments}):
        ready = [
            segment_id
            for segment_id in order
            if segment_by_id[segment_id]["planned_wave"] == planned_wave
        ]
        blocked = [
            segment_id
            for segment_id in ready
            if not dependencies[segment_id] <= completed
        ]
        if blocked:
            raise SegmentGenerationError(
                f"Seed Master planned wave {planned_wave} has unresolved dependencies: "
                + ", ".join(blocked)
            )
        waves.append(ready)
        completed.update(ready)
    return waves


def run(args: argparse.Namespace) -> int:
    if args.max_concurrency < 1:
        raise SegmentGenerationError("--max-concurrency must be positive.")
    if args.poll_interval <= 0 or args.wait_timeout <= 0 or args.timeout <= 0:
        raise SegmentGenerationError("Provider timing values must be positive.")
    task_dir = args.task_dir.expanduser().resolve()
    if not task_dir.is_dir():
        raise SegmentGenerationError(f"Task directory does not exist: {task_dir}")
    task = _task_contract(task_dir)
    all_segment_ids = [
        str(item["segment_id"]) for item in storyboard_segment_rows(task_dir)
    ]
    if args.segments:
        unknown = sorted(set(args.segments) - set(all_segment_ids))
        if unknown:
            raise SegmentGenerationError(
                f"Unknown --segments values: {', '.join(unknown)}"
            )
    segments = discover_segments(task_dir, segment_ids=args.segments)
    pending_root = task_dir / PENDING_DIRNAME / DEPARTMENT_DIRNAME
    waves = _storyboard_topological_waves(segments, task_dir=task_dir)
    announce(
        f"START segments={len(segments)} resolution={task['resolution']} "
        f"ratio={task['ratio']} scheduler=storyboard_shooting_plan_waves"
    )
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    boundary_precheck_failures: list[dict[str, str]] = []
    boundary_prechecks: dict[str, dict[str, Any]] = {}
    boundary_review_holds: dict[str, dict[str, Any]] = {}
    segment_by_id = {
        segment["generation_task_id"]: segment for segment in segments
    }
    for wave_number, wave_ids in enumerate(waves, start=1):
        announce(f"WAVE {wave_number} segments={','.join(wave_ids)}")
        with ThreadPoolExecutor(max_workers=args.max_concurrency) as executor:
            futures = {
                executor.submit(
                    generate_one,
                    segment_by_id[segment_id],
                    task_dir=task_dir,
                    resolution=task["resolution"],
                    ratio=task["ratio"],
                    poll_interval=args.poll_interval,
                    wait_timeout=args.wait_timeout,
                    request_timeout=args.timeout,
                ): segment_id
                for segment_id in wave_ids
            }
            for future in as_completed(futures):
                segment_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    failures.append({"segment_id": segment_id, "error": str(exc)})
                    announce(f"FAIL {segment_id} error={exc}")
                    continue
                results.append(result)
                try:
                    checks = prepare_adjacent_boundary_prechecks(
                        task_dir,
                        segment_id,
                        all_segment_ids,
                    )
                    for check in checks:
                        boundary_id = str(check["boundary_id"])
                        boundary_prechecks[boundary_id] = check
                        announce(
                            "BOUNDARY_REVIEW_READY "
                            f"boundary={boundary_id} "
                            f"technical_status={check['technical_status']} "
                            f"record={check.get('record_path', 'pending')}"
                        )
                        if check.get("blocks_downstream") is True:
                            boundary_review_holds[boundary_id] = {
                                "boundary_id": boundary_id,
                                "segment_id": str(check["to"]),
                                "technical_status": str(check["technical_status"]),
                                "reason": str(check.get("technical_reason") or ""),
                                "recommended_owner": str(
                                    check.get("recommended_owner") or "virtual-production"
                                ),
                                "record_path": str(check.get("record_path") or ""),
                            }
                except Exception as exc:
                    boundary_precheck_failures.append(
                        {"segment_id": segment_id, "error": str(exc)}
                    )
                    announce(f"BOUNDARY_PRECHECK_FAIL {segment_id} error={exc}")
        if failures or boundary_precheck_failures or boundary_review_holds:
            if failures or boundary_precheck_failures:
                announce("STOP downstream waves because an upstream wave failed")
            else:
                announce(
                    "STOP downstream waves because an incremental boundary needs "
                    "direct picture-and-sound review"
                )
            break
    results.sort(key=lambda item: item["segment_id"])
    failures.sort(key=lambda item: item["segment_id"])
    boundary_precheck_failures.sort(key=lambda item: item["segment_id"])
    summary_status = (
        "failed"
        if failures or boundary_precheck_failures
        else "boundary_review_required"
        if boundary_review_holds
        else "succeeded"
    )
    summary = {
        "status": summary_status,
        "segment_count": len(segments),
        "project_segment_count": len(all_segment_ids),
        "succeeded_count": len(results),
        "failed_count": len(failures),
        "generate_audio": True,
        "results": results,
        "failures": failures,
        "boundary_precheck_failed_count": len(boundary_precheck_failures),
        "boundary_precheck_failures": boundary_precheck_failures,
        "incremental_boundary_precheck_count": len(boundary_prechecks),
        "incremental_boundary_prechecks": [
            {
                "boundary_id": boundary_id,
                "from": check.get("from"),
                "to": check.get("to"),
                "technical_status": check.get("technical_status"),
                "blocks_downstream": check.get("blocks_downstream"),
                "recommended_owner": check.get("recommended_owner"),
                "record_path": check.get("record_path"),
            }
            for boundary_id, check in sorted(boundary_prechecks.items())
        ],
        "boundary_review_hold_count": len(boundary_review_holds),
        "boundary_review_holds": [
            boundary_review_holds[key] for key in sorted(boundary_review_holds)
        ],
    }
    summary_path = pending_root / SUMMARY_FILENAME
    write_json(summary_path, summary)
    if not failures and not boundary_precheck_failures and not boundary_review_holds:
        state_path = task_dir / "virtual-production" / "generation-state.json"
        full_generation = len(segments) == len(all_segment_ids)
        write_json(
            state_path,
            {
                "contract": "virtual-production-generation-state",
                "state": "GENERATED" if full_generation else "CANARY_GENERATED",
                "segments": [
                    {
                        "segment_id": item["segment_id"],
                        "provider_task_id": item["provider_task_id"],
                        "provider_attempt_id": item["provider_attempt_id"],
                        "seed_master_script_sha256": item[
                            "seed_master_script_sha256"
                        ],
                        "seedance_execution_plan_sha256": item[
                            "seedance_execution_plan_sha256"
                        ],
                        "operation": item["operation"],
                        "video_path": Path(item["video_path"])
                        .resolve()
                        .relative_to(task_dir)
                        .as_posix(),
                        "last_frame_path": Path(item["last_frame_path"])
                        .resolve()
                        .relative_to(task_dir)
                        .as_posix(),
                    }
                    for item in results
                ],
                "remaining_segment_ids": (
                    []
                    if full_generation
                    else [
                        segment_id
                        for segment_id in all_segment_ids
                        if segment_id
                        not in {item["segment_id"] for item in results}
                    ]
                ),
            },
        )
        summary["state"] = "GENERATED" if full_generation else "CANARY_GENERATED"
        write_json(summary_path, summary)
    announce(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return (
        0
        if not failures and not boundary_precheck_failures and not boundary_review_holds
        else 1
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--max-concurrency", type=int, default=3)
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--wait-timeout", type=float, default=3600.0)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument(
        "--segments",
        nargs="+",
        metavar="SEGMENT_ID",
        help=(
            "Generate only these Segment IDs in current plan order. Partial runs "
            "write CANARY_GENERATED and cannot enter postproduction."
        ),
    )
    return parser


@contextmanager
def task_execution_lock(task_dir: Path):
    pending_root = task_dir / PENDING_DIRNAME / DEPARTMENT_DIRNAME
    pending_root.mkdir(parents=True, exist_ok=True)
    lock_path = pending_root / EXECUTION_LOCK_FILENAME
    handle = lock_path.open("a+", encoding="utf-8")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            raise SegmentGenerationError(
                f"Another Seedance generation process already owns this task: {task_dir}"
            ) from exc
        yield
    finally:
        try:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            if acquired:
                lock_path.unlink(missing_ok=True)


def main() -> int:
    try:
        args = build_parser().parse_args()
        task_dir = args.task_dir.expanduser().resolve()
        with task_execution_lock(task_dir):
            return run(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
