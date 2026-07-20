#!/usr/bin/env python3
"""JSON-first CLI for Seedance video generation, polling, and cancellation."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
import time
import urllib.parse
from typing import Any

try:
    from . import tos_storage as core
except ImportError:
    production_design_scripts = (
        pathlib.Path(__file__).resolve().parents[3]
        / "direct-production-design"
        / "scripts"
    )
    sys.path.insert(0, str(production_design_scripts))
    from providers import tos_storage as core  # type: ignore


TERMINAL_VIDEO_STATES = {"succeeded", "failed", "cancelled", "expired"}
DEFAULT_POLL_INTERVAL = 10.0
DEFAULT_WAIT_TIMEOUT = float(core.DEFAULT_TIMEOUT)
MAX_REFERENCE_IMAGES = 9
MAX_REFERENCE_AUDIOS = 3
MAX_REFERENCE_VIDEOS = 3
SEEDANCE_CREATE_ENV = ("ARK_BASE_URL", "SEEDANCE_API_KEY", "SEEDANCE_MODEL")
SEEDANCE_TASK_ENV = ("ARK_BASE_URL", "SEEDANCE_API_KEY")


def api_key() -> str:
    value = core.env("SEEDANCE_API_KEY", required=True)
    assert value is not None
    return value


def model_id() -> str:
    value = core.env("SEEDANCE_MODEL", required=True)
    assert value is not None
    return value


def create_video_task(
    payload: dict[str, Any], *, timeout: int = core.DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Create a Seedance task from an already validated workflow payload."""
    core.require_environment(*SEEDANCE_CREATE_ENV)
    request_payload = dict(payload)
    request_payload.setdefault("model", model_id())
    return core.request_json(
        "POST",
        "contents/generations/tasks",
        key=api_key(),
        body=request_payload,
        timeout=timeout,
    )


def get_video_task(
    task_id: str, *, timeout: int = core.DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Retrieve one Seedance task without exposing transport details to workflows."""
    core.require_environment(*SEEDANCE_TASK_ENV)
    return core.request_json(
        "GET",
        f"contents/generations/tasks/{urllib.parse.quote(task_id, safe='')}",
        key=api_key(),
        timeout=timeout,
    )


def cancel_video_task(
    task_id: str, *, timeout: int = core.DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Cancel one Seedance task when its current state permits cancellation."""
    core.require_environment(*SEEDANCE_TASK_ENV)
    return core.request_json(
        "DELETE",
        f"contents/generations/tasks/{urllib.parse.quote(task_id, safe='')}",
        key=api_key(),
        timeout=timeout,
    )


def command_config(_: argparse.Namespace) -> dict[str, Any]:
    capabilities = {
        "seedance_create": SEEDANCE_CREATE_ENV,
        "seedance_task": SEEDANCE_TASK_ENV,
        "tos_storage": core.TOS_ENV,
    }
    missing = core.missing_environment(SEEDANCE_CREATE_ENV)
    return {
        "environment_source": "host_process_environment",
        "configured": not missing,
        "missing_environment_variables": missing,
        "capabilities": {
            name: {
                "configured": not core.missing_environment(names),
                "missing_environment_variables": core.missing_environment(names),
            }
            for name, names in capabilities.items()
        },
        "ark": {
            "base_url": os.getenv("ARK_BASE_URL"),
            "model": os.getenv("SEEDANCE_MODEL"),
            "credentials": bool(os.getenv("SEEDANCE_API_KEY")),
        },
    }


def validate_video_inputs(args: argparse.Namespace) -> None:
    if len(args.reference_image) > MAX_REFERENCE_IMAGES:
        raise core.SeedMediaError(
            f"Seedance 2.0 supports at most {MAX_REFERENCE_IMAGES} reference images"
        )
    if len(args.reference_audio) > MAX_REFERENCE_AUDIOS:
        raise core.SeedMediaError(
            f"Seedance 2.0 supports at most {MAX_REFERENCE_AUDIOS} reference audios"
        )
    if len(args.reference_video) > MAX_REFERENCE_VIDEOS:
        raise core.SeedMediaError(
            f"Seedance 2.0 supports at most {MAX_REFERENCE_VIDEOS} reference videos"
        )
    if args.reference_audio and not args.reference_image:
        raise core.SeedMediaError(
            "Reference audio requires at least one reference image"
        )
    if args.duration != -1 and not 4 <= args.duration <= 15:
        raise core.SeedMediaError(
            "Seedance 2.0 duration must be -1 or an integer from 4 to 15"
        )
    if not 3600 <= args.execution_expires_after <= 259200:
        raise core.SeedMediaError(
            "execution_expires_after must be between 3600 and 259200 seconds"
        )


def wait_video_task(
    task_id: str, *, interval: float, timeout: float, request_timeout: int
) -> dict[str, Any]:
    if interval <= 0 or timeout <= 0:
        raise core.SeedMediaError("Polling interval and wait timeout must be positive")
    deadline = time.monotonic() + timeout
    while True:
        result = get_video_task(task_id, timeout=request_timeout)
        status = result.get("status")
        if status in TERMINAL_VIDEO_STATES:
            return result
        if time.monotonic() >= deadline:
            raise core.SeedMediaError(
                f"Timed out waiting for video task {task_id}; last status: {status}"
            )
        time.sleep(interval)


def persist_video_result(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if result.get("status") != "succeeded" or (not args.save_dir and not args.store):
        return result
    content = result.get("content") or {}
    urls = [
        ("video", content.get("video_url"), ".mp4"),
        ("last_frame", content.get("last_frame_url"), ".png"),
    ]
    artifacts: list[dict[str, Any]] = []
    save_dir = pathlib.Path(args.save_dir).expanduser() if args.save_dir else None
    for label, url, suffix in urls:
        if not url:
            continue
        default_name = f"{result.get('id', 'seedance')}-{label}{suffix}"
        name = core.safe_filename(url, default_name)
        local: pathlib.Path | None = None
        if save_dir:
            local = core.download_url(url, save_dir / name, timeout=args.timeout)
        artifact: dict[str, Any] = {"type": label}
        if local:
            artifact["local_path"] = str(local.resolve())
        if args.store:
            if local:
                stored = core.tos_upload_path(local, kind=f"outputs/{label}")
            else:
                with tempfile.TemporaryDirectory(prefix="seed-media-") as temp_dir:
                    temp = core.download_url(
                        url, pathlib.Path(temp_dir) / name, timeout=args.timeout
                    )
                    stored = core.tos_upload_path(temp, kind=f"outputs/{label}")
            artifact["tos"] = stored
        artifacts.append(artifact)
    result["artifacts"] = artifacts
    return result


def build_video_payload(args: argparse.Namespace) -> dict[str, Any]:
    validate_video_inputs(args)
    content: list[dict[str, Any]] = []
    if args.prompt:
        content.append({"type": "text", "text": args.prompt})
    core.add_media_content(
        content,
        args.reference_image,
        kind="image",
        role="reference_image",
        upload_local=args.upload_local,
    )
    core.add_media_content(
        content,
        args.reference_audio,
        kind="audio",
        role="reference_audio",
        upload_local=args.upload_local,
    )
    core.add_media_content(
        content,
        args.reference_video,
        kind="video",
        role="reference_video",
        upload_local=args.upload_local,
    )
    if not content:
        raise core.SeedMediaError("Video generation requires a prompt or input media")
    payload: dict[str, Any] = {
        "model": model_id(),
        "content": content,
        "resolution": args.resolution,
        "ratio": args.ratio,
        "duration": args.duration,
        "generate_audio": args.generate_audio,
        "watermark": args.watermark,
        "return_last_frame": args.return_last_frame,
        "execution_expires_after": args.execution_expires_after,
        "priority": args.priority,
    }
    merged = core.deep_merge(payload, core.parse_json_value(args.extra_json))
    if not isinstance(merged.get("return_last_frame"), bool):
        raise core.SeedMediaError("return_last_frame must be boolean")
    forbidden_top_level = {"first_frame", "last_frame", "reference_video", "extend"}
    present_forbidden = sorted(forbidden_top_level & set(merged))
    if present_forbidden:
        raise core.SeedMediaError(
            "Segment generation forbids continuation inputs: "
            + ", ".join(present_forbidden)
        )
    merged_content = merged.get("content")
    if not isinstance(merged_content, list) or not merged_content:
        raise core.SeedMediaError("Video generation requires non-empty content")
    allowed_type_roles = {
        ("text", None),
        ("image_url", "reference_image"),
        ("audio_url", "reference_audio"),
        ("video_url", "reference_video"),
    }
    for item in merged_content:
        if (
            not isinstance(item, dict)
            or (item.get("type"), item.get("role")) not in allowed_type_roles
        ):
            raise core.SeedMediaError(
                "Segment generation accepts only text and reference image/audio/video content"
            )
    return merged


def command_create(args: argparse.Namespace) -> dict[str, Any]:
    required = list(SEEDANCE_CREATE_ENV)
    local_images = any(not core.is_remote(item) for item in args.reference_image)
    local_audio = any(not core.is_remote(item) for item in args.reference_audio)
    local_video = any(not core.is_remote(item) for item in args.reference_video)
    if (
        local_audio
        or local_video
        or (args.upload_local and local_images)
        or (args.wait and args.store)
    ):
        required.extend(core.TOS_ENV)
    core.require_environment(*required)
    result = create_video_task(build_video_payload(args), timeout=args.timeout)
    if args.wait:
        task_id = result.get("id")
        if not task_id:
            raise core.SeedMediaError("Create response did not include a task ID")
        result = wait_video_task(
            str(task_id),
            interval=args.poll_interval,
            timeout=args.wait_timeout,
            request_timeout=args.timeout,
        )
        result = persist_video_result(result, args)
    return result


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    return get_video_task(args.task_id, timeout=args.timeout)


def command_wait(args: argparse.Namespace) -> dict[str, Any]:
    required = list(SEEDANCE_TASK_ENV)
    if args.store:
        required.extend(core.TOS_ENV)
    core.require_environment(*required)
    result = wait_video_task(
        args.task_id,
        interval=args.poll_interval,
        timeout=args.wait_timeout,
        request_timeout=args.timeout,
    )
    return persist_video_result(result, args)


def command_cancel(args: argparse.Namespace) -> dict[str, Any]:
    return cancel_video_task(args.task_id, timeout=args.timeout)


def add_persistence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--save-dir", help="Download outputs into this local directory")
    parser.add_argument("--store", action="store_true", help="Persist outputs into configured TOS")


def add_wait_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--wait-timeout", type=float, default=DEFAULT_WAIT_TIMEOUT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=core.DEFAULT_TIMEOUT)
    parser.add_argument("--pretty", action="store_true")
    root = parser.add_subparsers(dest="command", required=True)

    config = root.add_parser("config", help="Show non-secret Seedance configuration status")
    config.set_defaults(handler=command_config)

    create = root.add_parser("create", help="Create an asynchronous video task")
    create.add_argument("--prompt")
    create.add_argument("--reference-image", action="append", default=[])
    create.add_argument("--reference-audio", action="append", default=[])
    create.add_argument("--reference-video", action="append", default=[])
    create.add_argument(
        "--resolution", choices=("480p", "720p", "1080p", "4k"), default="720p"
    )
    create.add_argument(
        "--ratio",
        choices=("16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"),
        default="adaptive",
    )
    create.add_argument("--duration", type=int, default=5)
    create.add_argument("--generate-audio", action=argparse.BooleanOptionalAction, default=True)
    create.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=False)
    create.add_argument(
        "--return-last-frame", action=argparse.BooleanOptionalAction, default=False
    )
    create.add_argument("--priority", type=int, choices=range(10), default=0)
    create.add_argument("--execution-expires-after", type=int, default=172800)
    create.add_argument("--upload-local", action=argparse.BooleanOptionalAction, default=True)
    create.add_argument("--extra-json", help="JSON object or @path merged into the request")
    create.add_argument("--wait", action="store_true")
    add_wait_arguments(create)
    add_persistence_arguments(create)
    create.set_defaults(handler=command_create)

    status = root.add_parser("status", help="Retrieve a video task")
    status.add_argument("task_id")
    status.set_defaults(handler=command_status)

    wait = root.add_parser("wait", help="Wait for a video task")
    wait.add_argument("task_id")
    add_wait_arguments(wait)
    add_persistence_arguments(wait)
    wait.set_defaults(handler=command_wait)

    cancel = root.add_parser("cancel", help="Cancel or delete a video task")
    cancel.add_argument("task_id")
    cancel.set_defaults(handler=command_cancel)
    return parser


def main(argv: list[str] | None = None) -> int:
    return core.run_cli(build_parser(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
