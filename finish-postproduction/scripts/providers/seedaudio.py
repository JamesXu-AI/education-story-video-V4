#!/usr/bin/env python3
"""JSON-first CLI for Seed Audio 1.0 prompt-based audio generation."""

from __future__ import annotations

import argparse
import base64
import binascii
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

shared_storage_path = (
    pathlib.Path(__file__).resolve().parents[3]
    / "direct-production-design"
    / "scripts"
    / "providers"
    / "tos_storage.py"
)
storage_spec = importlib.util.spec_from_file_location(
    "film_shared_tos_storage", shared_storage_path
)
if storage_spec is None or storage_spec.loader is None:
    raise RuntimeError(f"Cannot load shared TOS provider: {shared_storage_path}")
core = importlib.util.module_from_spec(storage_spec)
storage_spec.loader.exec_module(core)


SEEDAUDIO_ENV = ("SEEDAUDIO_API", "SEEDAUDIO_API_KEY", "SEEDAUDIO_MODEL")
SUPPORTED_AUDIO_FORMATS = ("wav", "mp3", "pcm", "ogg_opus")
SUPPORTED_SAMPLE_RATES = (8000, 16000, 24000, 32000, 44100, 48000)


def api_key() -> str:
    value = core.env("SEEDAUDIO_API_KEY", required=True)
    assert value is not None
    return value


def model_id() -> str:
    value = core.env("SEEDAUDIO_MODEL", required=True)
    assert value is not None
    return value


def api_url() -> str:
    value = core.env("SEEDAUDIO_API", required=True)
    assert value is not None
    value = value.strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise core.SeedMediaError("SEEDAUDIO_API must be a complete https URL")
    return value


def command_config(_: argparse.Namespace) -> dict[str, Any]:
    capabilities = {
        "seedaudio_generate": SEEDAUDIO_ENV,
        "tos_storage": core.TOS_ENV,
    }
    missing = core.missing_environment(SEEDAUDIO_ENV)
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
        "seed_speech": {
            "endpoint": os.getenv("SEEDAUDIO_API"),
            "model": os.getenv("SEEDAUDIO_MODEL"),
            "credentials": bool(os.getenv("SEEDAUDIO_API_KEY")),
        },
    }


def request_audio(body: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    client_request_id = str(uuid.uuid4())
    request = urllib.request.Request(
        api_url(),
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Api-Key": api_key(),
            "X-Api-Request-Id": client_request_id,
            "User-Agent": "education-story-video/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            log_id = response.headers.get("X-Tt-Logid")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        log_id = exc.headers.get("X-Tt-Logid")
        try:
            detail = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            detail = {"message": raw.decode("utf-8", errors="replace")[:1000]}
        raise core.SeedMediaError(
            json.dumps(
                {"http_status": exc.code, "request_id": log_id, "error": core.redact(detail)},
                ensure_ascii=False,
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise core.SeedMediaError(f"Network request failed: {exc.reason}") from exc
    try:
        result = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise core.SeedMediaError("Seed Audio returned non-JSON data") from exc
    if not isinstance(result, dict):
        raise core.SeedMediaError("Seed Audio returned an unexpected JSON shape")
    if result.get("code") not in (None, 0):
        raise core.SeedMediaError(
            json.dumps(
                {
                    "request_id": log_id or client_request_id,
                    "code": result.get("code"),
                    "message": result.get("message"),
                },
                ensure_ascii=False,
            )
        )
    result["request_id"] = log_id or client_request_id
    return result


def read_reference_file(value: str, *, kind: str) -> bytes:
    path = pathlib.Path(value).expanduser()
    if not path.is_file():
        raise core.SeedMediaError(f"Reference file not found: {path}")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise core.SeedMediaError(f"A Seed Audio reference {kind} must not exceed 10 MiB")
    suffix = path.suffix.lower().lstrip(".")
    allowed = {
        "audio": {"wav", "mp3", "pcm", "ogg", "opus", "ogg_opus"},
        "image": {"jpg", "jpeg", "png", "webp"},
    }[kind]
    if suffix not in allowed:
        raise core.SeedMediaError(
            f"Unsupported Seed Audio reference {kind} format: {path.suffix or '(none)'}"
        )
    return path.read_bytes()


def resolve_audio_reference(value: str) -> dict[str, str]:
    if value.startswith("speaker:"):
        speaker = value.removeprefix("speaker:").strip()
        if not speaker:
            raise core.SeedMediaError("speaker: reference requires a speaker ID")
        return {"speaker": speaker}
    if value.startswith(("https://", "http://")):
        return {"audio_url": value}
    encoded = base64.b64encode(read_reference_file(value, kind="audio")).decode("ascii")
    return {"audio_data": encoded}


def resolve_image_reference(value: str) -> dict[str, str]:
    if value.startswith(("https://", "http://")):
        return {"image_url": value}
    encoded = base64.b64encode(read_reference_file(value, kind="image")).decode("ascii")
    return {"image_data": encoded}


def validate_generate_args(args: argparse.Namespace) -> None:
    if len(args.prompt) > 3000:
        raise core.SeedMediaError("Seed Audio text_prompt must not exceed 3000 characters")
    if len(args.audio_ref) > 3:
        raise core.SeedMediaError("Seed Audio supports at most 3 ordered audio references")
    if args.audio_ref and args.image_ref:
        raise core.SeedMediaError("Seed Audio audio and image references are mutually exclusive")
    if args.speech_rate is not None and not -50 <= args.speech_rate <= 100:
        raise core.SeedMediaError("speech_rate must be between -50 and 100")
    if args.loudness_rate is not None and not -50 <= args.loudness_rate <= 100:
        raise core.SeedMediaError("loudness_rate must be between -50 and 100")
    if args.pitch_rate is not None and not -12 <= args.pitch_rate <= 12:
        raise core.SeedMediaError("pitch_rate must be between -12 and 12")


def build_audio_payload(args: argparse.Namespace) -> dict[str, Any]:
    validate_generate_args(args)
    audio_config: dict[str, Any] = {
        "format": args.output_format,
        "enable_subtitle": args.enable_subtitle,
    }
    for name in ("sample_rate", "speech_rate", "loudness_rate", "pitch_rate"):
        value = getattr(args, name)
        if value is not None:
            audio_config[name] = value
    payload: dict[str, Any] = {
        "model": model_id(),
        "text_prompt": args.prompt,
        "audio_config": audio_config,
    }
    if args.audio_ref:
        payload["references"] = [resolve_audio_reference(value) for value in args.audio_ref]
    elif args.image_ref:
        payload["references"] = [resolve_image_reference(args.image_ref)]
    return core.deep_merge(payload, core.parse_json_value(args.extra_json))


def persist_audio_result(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    encoded = result.pop("audio", None) or result.pop("data", None)
    if encoded:
        result["audio_base64_omitted"] = True
        result["audio_base64_characters"] = len(encoded)
    if not args.save_dir and not args.store:
        return result

    raw: bytes | None = None
    if encoded:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise core.SeedMediaError("Seed Audio returned invalid Base64 audio data") from exc
    name = f"seed-audio-{int(time.time())}.{args.output_format}"
    local: pathlib.Path | None = None
    if args.save_dir:
        local = pathlib.Path(args.save_dir).expanduser() / name
        if raw is not None:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(raw)
        elif result.get("url"):
            core.download_url(str(result["url"]), local, timeout=args.timeout)
        else:
            raise core.SeedMediaError("Seed Audio response did not include audio data or a URL")

    artifact: dict[str, Any] = {"type": "audio", "format": args.output_format}
    if local:
        artifact["local_path"] = str(local.resolve())
    if args.store:
        if raw is not None:
            stored = core.tos_upload_bytes(raw, name=name, kind="outputs/audio")
        elif local:
            stored = core.tos_upload_path(local, kind="outputs/audio")
        elif result.get("url"):
            with tempfile.TemporaryDirectory(prefix="seed-media-") as temp_dir:
                temp = core.download_url(
                    str(result["url"]), pathlib.Path(temp_dir) / name, timeout=args.timeout
                )
                stored = core.tos_upload_path(temp, kind="outputs/audio")
        else:
            raise core.SeedMediaError("Seed Audio response did not include audio data or a URL")
        artifact["tos"] = stored
    result["artifacts"] = [artifact]
    return result


def command_generate(args: argparse.Namespace) -> dict[str, Any]:
    required = list(SEEDAUDIO_ENV)
    if args.store:
        required.extend(core.TOS_ENV)
    core.require_environment(*required)
    result = request_audio(build_audio_payload(args), timeout=args.timeout)
    return persist_audio_result(result, args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=core.DEFAULT_TIMEOUT)
    parser.add_argument("--pretty", action="store_true")
    root = parser.add_subparsers(dest="command", required=True)

    config = root.add_parser("config", help="Show non-secret Seed Audio configuration status")
    config.set_defaults(handler=command_config)

    generate = root.add_parser("generate", help="Generate audio from a prompt")
    generate.add_argument("--prompt", required=True, help="Pass text_prompt unchanged")
    generate.add_argument(
        "--audio-ref",
        action="append",
        default=[],
        help="Ordered URL, local file, or speaker:ID; use @Audio1..@Audio3 in the prompt",
    )
    generate.add_argument("--image-ref", help="One image URL or local file; cannot mix with audio")
    generate.add_argument("--output-format", choices=SUPPORTED_AUDIO_FORMATS, default="wav")
    generate.add_argument("--sample-rate", type=int, choices=SUPPORTED_SAMPLE_RATES)
    generate.add_argument("--speech-rate", type=int)
    generate.add_argument("--loudness-rate", type=int)
    generate.add_argument("--pitch-rate", type=int)
    generate.add_argument("--enable-subtitle", action="store_true")
    generate.add_argument("--save-dir", help="Save generated audio into this local directory")
    generate.add_argument("--store", action="store_true", help="Persist generated audio into TOS")
    generate.add_argument("--extra-json", help="JSON object or @path merged into the request")
    generate.set_defaults(handler=command_generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    return core.run_cli(build_parser(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
