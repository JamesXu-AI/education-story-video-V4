#!/usr/bin/env python3
"""JSON-first CLI for Seedream image generation and editing."""

from __future__ import annotations

import argparse
import base64
import os
import pathlib
import tempfile
import time
from typing import Any

try:
    from . import tos_storage as core
except ImportError:  # Direct script execution keeps providers/ on sys.path.
    import tos_storage as core  # type: ignore


SEEDREAM_ENV = ("ARK_BASE_URL", "SEEDREAM_API_KEY", "SEEDREAM_MODEL")
SEEDREAM_MODEL_ID = "dola-seedream-5-0-pro-260628"
# Seedream 5.0 Pro's ModelArk endpoint accepts only the 1K/2K preset names.
# Use an explicit 16:9 size near the documented 4,624,220-pixel ceiling for
# maximum-resolution production assets.
SEEDREAM_MAX_IMAGE_SIZE = "2816x1584"


def seedream_task_image_size(video_resolution: str) -> str:
    """Return the fixed 16:9 Seedream reference size for a task resolution."""
    resolution = str(video_resolution).strip().lower()
    if resolution in {"480", "480p", "720", "720p", "1080", "1080p"}:
        return "2560x1440"
    if resolution == "4k":
        return "2816x1584"
    raise core.SeedMediaError(
        "Video resolution must be 480, 720, 1080, or 4k before selecting "
        "the Seedream image size."
    )


def api_key() -> str:
    value = core.env("SEEDREAM_API_KEY", required=True)
    assert value is not None
    return value


def model_id() -> str:
    value = core.env("SEEDREAM_MODEL", required=True)
    assert value is not None
    if value != SEEDREAM_MODEL_ID:
        raise core.SeedMediaError(
            "SEEDREAM_MODEL must be exactly "
            f"{SEEDREAM_MODEL_ID}; no other model ID is accepted"
        )
    return SEEDREAM_MODEL_ID


def generate_image(
    payload: dict[str, Any], *, timeout: int = core.DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Generate an image without exposing ModelArk transport details to workflows."""
    core.require_environment(*SEEDREAM_ENV)
    required_model = model_id()
    request_payload = dict(payload)
    requested_model = request_payload.get("model")
    if requested_model is not None and requested_model != required_model:
        raise core.SeedMediaError(
            f"Seedream request model must be exactly {required_model}; received "
            f"{requested_model!r}"
        )
    request_payload["model"] = required_model
    return core.request_json(
        "POST",
        "images/generations",
        key=api_key(),
        body=request_payload,
        timeout=timeout,
    )


def command_config(_: argparse.Namespace) -> dict[str, Any]:
    capabilities = {
        "seedream": SEEDREAM_ENV,
        "tos_storage": core.TOS_ENV,
    }
    missing = core.missing_environment(SEEDREAM_ENV)
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
            "model": os.getenv("SEEDREAM_MODEL"),
            "credentials": bool(os.getenv("SEEDREAM_API_KEY")),
        },
    }


def persist_image_result(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if not args.save_dir and not args.store:
        return result
    artifacts: list[dict[str, Any]] = []
    save_dir = pathlib.Path(args.save_dir).expanduser() if args.save_dir else None
    for index, item in enumerate(result.get("data", []), 1):
        if not isinstance(item, dict) or item.get("error"):
            continue
        raw: bytes | None = None
        suffix = ".png" if args.output_format == "png" else ".jpg"
        name = f"seedream-{int(time.time())}-{index}{suffix}"
        local: pathlib.Path | None = None
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            name = core.safe_filename(item["url"], name)
        if save_dir:
            local = save_dir / name
            if raw is not None:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(raw)
            else:
                core.download_url(item["url"], local, timeout=args.timeout)
        artifact: dict[str, Any] = {"index": index}
        if local:
            artifact["local_path"] = str(local.resolve())
        if args.store:
            if raw is not None:
                stored = core.tos_upload_bytes(raw, name=name, kind="outputs/images")
            elif local:
                stored = core.tos_upload_path(local, kind="outputs/images")
            else:
                with tempfile.TemporaryDirectory(prefix="seed-media-") as temp_dir:
                    temp = core.download_url(
                        item["url"], pathlib.Path(temp_dir) / name, timeout=args.timeout
                    )
                    stored = core.tos_upload_path(temp, kind="outputs/images")
            artifact["tos"] = stored
        artifacts.append(artifact)
    result["artifacts"] = artifacts
    return result


def command_generate(args: argparse.Namespace) -> dict[str, Any]:
    required = list(SEEDREAM_ENV)
    if args.store or (args.upload_local and any(not core.is_remote(item) for item in args.image)):
        required.extend(core.TOS_ENV)
    core.require_environment(*required)
    if args.max_images and len(args.image) + args.max_images > 15:
        raise core.SeedMediaError(
            "Reference image count plus generated image count must not exceed 15"
        )
    payload: dict[str, Any] = {
        "model": model_id(),
        "prompt": args.prompt,
        "size": args.size,
        "response_format": args.response_format,
        "watermark": args.watermark,
    }
    if args.output_format:
        payload["output_format"] = args.output_format
    if args.image:
        resolved = [
            core.resolve_input(
                item,
                kind="image",
                upload_local=args.upload_local,
                presign_expires=args.presign_expires,
            )
            for item in args.image
        ]
        payload["image"] = resolved[0] if len(resolved) == 1 else resolved
    if args.max_images:
        payload["sequential_image_generation"] = "auto"
        payload["sequential_image_generation_options"] = {"max_images": args.max_images}
    payload = core.deep_merge(payload, core.parse_json_value(args.extra_json))
    result = generate_image(payload, timeout=args.timeout)
    return persist_image_result(result, args)


def add_persistence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--save-dir", help="Download outputs into this local directory")
    parser.add_argument("--store", action="store_true", help="Persist outputs into configured TOS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=core.DEFAULT_TIMEOUT)
    parser.add_argument("--pretty", action="store_true")
    root = parser.add_subparsers(dest="command", required=True)

    config = root.add_parser("config", help="Show non-secret Seedream configuration status")
    config.set_defaults(handler=command_config)

    generate = root.add_parser("generate", help="Generate or edit images")
    generate.add_argument("--prompt", required=True)
    generate.add_argument(
        "--image", action="append", default=[], help="Reference URL, data URI, asset URI, or file"
    )
    generate.add_argument("--size", default=SEEDREAM_MAX_IMAGE_SIZE)
    generate.add_argument("--output-format", choices=("png", "jpeg"), default="png")
    generate.add_argument("--response-format", choices=("url", "b64_json"), default="url")
    generate.add_argument("--max-images", type=int, choices=range(1, 16), metavar="1..15")
    generate.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=False)
    generate.add_argument("--upload-local", action="store_true", help="Upload local references to TOS")
    generate.add_argument("--presign-expires", type=int, default=86400)
    generate.add_argument("--extra-json", help="JSON object or @path merged into the request")
    add_persistence_arguments(generate)
    generate.set_defaults(handler=command_generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    return core.run_cli(build_parser(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
