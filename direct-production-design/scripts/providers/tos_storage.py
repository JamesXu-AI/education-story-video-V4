#!/usr/bin/env python3
"""JSON-first TOS CLI and shared provider runtime for BytePlus media services."""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import importlib.util
import json
import mimetypes
import os
import pathlib
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Iterable


# Every outbound provider/API request gets a one-hour default window.  Individual
# callers may still supply an explicit positive timeout when a task requires it.
DEFAULT_TIMEOUT = 60 * 60
SECRET_MARKERS = ("key", "secret", "password", "authorization", "token")
TOS_ENV = (
    "STORAGE_TOS_REGION",
    "STORAGE_TOS_ENDPOINT",
    "STORAGE_TOS_BUCKET",
    "STORAGE_TOS_ACCESS_KEY_ID",
    "STORAGE_TOS_SECRET_ACCESS_KEY",
    "STORAGE_TOS_KEY_PREFIX",
)


class SeedMediaError(RuntimeError):
    """Expected user-facing error without credential-bearing context."""


class MissingEnvironmentError(SeedMediaError):
    """Raised when required host process environment variables are absent."""

    def __init__(self, variables: Iterable[str]):
        self.variables = sorted(set(variables))
        super().__init__(
            "Host environment variable(s) not configured: " + ", ".join(self.variables)
        )


def emit(value: Any, *, pretty: bool = False, stream: Any = sys.stdout) -> None:
    json.dump(value, stream, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty)
    stream.write("\n")


def missing_environment(names: Iterable[str]) -> list[str]:
    return sorted(name for name in set(names) if not os.environ.get(name))


def require_environment(*names: str) -> None:
    missing = missing_environment(names)
    if missing:
        raise MissingEnvironmentError(missing)


def env(name: str, *, required: bool = False) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if required:
        raise MissingEnvironmentError([name])
    return None


def ark_base_url() -> str:
    value = env("ARK_BASE_URL", required=True)
    assert value is not None
    value = value.rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SeedMediaError("ARK_BASE_URL must be an https URL")
    return value


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lower = str(key).lower()
            result[key] = "<redacted>" if any(marker in lower for marker in SECRET_MARKERS) else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def parse_json_value(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    if value.startswith("@"):
        path = pathlib.Path(value[1:]).expanduser()
        raw = path.read_text(encoding="utf-8")
    else:
        raw = value
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SeedMediaError(f"Invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SeedMediaError("Extra JSON must be an object")
    return parsed


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def request_json(
    method: str,
    path: str,
    *,
    key: str,
    body: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    url = f"{ark_base_url()}/{path.lstrip('/')}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "education-story-video/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        request_id = exc.headers.get("x-request-id") or exc.headers.get("x-tt-logid")
        try:
            detail = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            detail = {"message": raw.decode("utf-8", errors="replace")[:1000]}
        raise SeedMediaError(
            json.dumps(
                {"http_status": exc.code, "request_id": request_id, "error": redact(detail)},
                ensure_ascii=False,
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise SeedMediaError(f"Network request failed: {exc.reason}") from exc
    if not raw:
        return {"ok": True}
    try:
        result = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SeedMediaError("Server returned non-JSON data") from exc
    if not isinstance(result, dict):
        raise SeedMediaError("Server returned an unexpected JSON shape")
    return result


def is_remote(value: str) -> bool:
    return value.startswith(("https://", "http://", "data:", "asset://"))


def local_data_uri(path_value: str) -> str:
    path = pathlib.Path(path_value).expanduser()
    if not path.is_file():
        raise SeedMediaError(f"Input file not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        raise SeedMediaError(f"Local image input has an unsupported type: {path.name}")
    if path.stat().st_size > 30 * 1024 * 1024:
        raise SeedMediaError("A Seedream/Seedance input image must not exceed 30 MiB")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def safe_filename(value: str, default_name: str) -> str:
    parsed = urllib.parse.urlparse(value)
    name = pathlib.PurePosixPath(parsed.path).name or default_name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name or default_name


def download_url(
    url: str,
    destination: pathlib.Path,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> pathlib.Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "education-story-video/1.0"})
    temp_path = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temp_path.open("wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)
        temp_path.replace(destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return destination


def tos_module() -> Any:
    try:
        import tos  # type: ignore
    except ImportError as exc:
        raise SeedMediaError(
            "TOS support requires the official Python package. Install with: python3 -m pip install 'tos>=2.9,<3'"
        ) from exc
    return tos


def tos_settings() -> dict[str, str]:
    names = {
        "region": "STORAGE_TOS_REGION",
        "endpoint": "STORAGE_TOS_ENDPOINT",
        "bucket": "STORAGE_TOS_BUCKET",
        "access_key": "STORAGE_TOS_ACCESS_KEY_ID",
        "secret_key": "STORAGE_TOS_SECRET_ACCESS_KEY",
        "prefix": "STORAGE_TOS_KEY_PREFIX",
    }
    values = {key: env(name, required=True) for key, name in names.items()}
    return {key: str(value) for key, value in values.items()}


def tos_client() -> tuple[Any, Any, dict[str, str]]:
    tos = tos_module()
    settings = tos_settings()
    client = tos.TosClientV2(
        settings["access_key"],
        settings["secret_key"],
        settings["endpoint"],
        settings["region"],
    )
    return tos, client, settings


def normalize_tos_key(key: str | None, source_name: str, kind: str) -> str:
    settings = tos_settings()
    if key:
        normalized = key.lstrip("/")
    else:
        date = dt.datetime.now(dt.timezone.utc).strftime("%Y/%m/%d")
        clean = safe_filename(source_name, f"asset-{uuid.uuid4().hex}")
        normalized = f"{settings['prefix'].strip('/')}/{kind}/{date}/{uuid.uuid4().hex[:12]}-{clean}"
    if ".." in pathlib.PurePosixPath(normalized).parts:
        raise SeedMediaError("TOS key must not contain '..'")
    return normalized


def tos_public_url(key: str) -> str:
    """Return the stable public object URL; never persist a presigned URL."""

    settings = tos_settings()
    normalized_key = str(key).lstrip("/")
    if not normalized_key or ".." in pathlib.PurePosixPath(normalized_key).parts:
        raise SeedMediaError("TOS key must be a non-empty safe object key")
    endpoint = settings["endpoint"].strip().rstrip("/")
    if "://" not in endpoint:
        endpoint = "https://" + endpoint
    parsed = urllib.parse.urlsplit(endpoint)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise SeedMediaError(
            "STORAGE_TOS_ENDPOINT must be one HTTPS origin without path or query"
        )
    bucket = settings["bucket"].strip()
    host = parsed.netloc
    if not host.casefold().startswith(bucket.casefold() + "."):
        host = f"{bucket}.{host}"
    encoded_key = urllib.parse.quote(normalized_key, safe="/-._~")
    return urllib.parse.urlunsplit(("https", host, "/" + encoded_key, "", ""))


def _is_tos_http_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    hostname = (parsed.hostname or "").casefold()
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(hostname)
        and any(label == "tos" or label.startswith("tos-") for label in hostname.split("."))
    )


def persistent_tos_url(value: str) -> str:
    """Normalize a provider TOS URL to its unsigned, persistent identity."""

    if not isinstance(value, str) or not _is_tos_http_url(value.strip()):
        raise SeedMediaError("Expected an absolute TOS HTTP(S) URL")
    parsed = urllib.parse.urlsplit(value.strip())
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def without_tos_signatures(value: Any) -> Any:
    """Recursively remove transient TOS query signatures from persisted evidence."""

    if isinstance(value, str) and _is_tos_http_url(value):
        return persistent_tos_url(value)
    if isinstance(value, dict):
        return {key: without_tos_signatures(item) for key, item in value.items()}
    if isinstance(value, list):
        return [without_tos_signatures(item) for item in value]
    return value


def tos_presign(key: str, *, method: str = "get", expires: int = 86400) -> str:
    if expires < 1 or expires > 604800:
        raise SeedMediaError("Presigned URL expiry must be between 1 and 604800 seconds")
    tos, client, settings = tos_client()
    method_map = {
        "get": tos.HttpMethodType.Http_Method_Get,
        "put": tos.HttpMethodType.Http_Method_Put,
    }
    output = client.pre_signed_url(
        method_map[method], bucket=settings["bucket"], key=key, expires=expires
    )
    return output.signed_url


def tos_upload_path(
    path: pathlib.Path, *, key: str | None = None, kind: str = "assets"
) -> dict[str, Any]:
    if not path.is_file():
        raise SeedMediaError(f"Upload file not found: {path}")
    _, client, settings = tos_client()
    object_key = normalize_tos_key(key, path.name, kind)
    with path.open("rb") as handle:
        output = client.put_object(settings["bucket"], object_key, content=handle)
    return {
        "bucket": settings["bucket"],
        "key": object_key,
        "etag": getattr(output, "etag", None),
        "request_id": getattr(output, "request_id", None),
        "tos_uri": f"tos://{settings['bucket']}/{object_key}",
        "public_url": tos_public_url(object_key),
    }


def tos_upload_bytes(
    data: bytes, *, name: str, key: str | None = None, kind: str = "assets"
) -> dict[str, Any]:
    _, client, settings = tos_client()
    object_key = normalize_tos_key(key, name, kind)
    output = client.put_object(settings["bucket"], object_key, content=data)
    return {
        "bucket": settings["bucket"],
        "key": object_key,
        "etag": getattr(output, "etag", None),
        "request_id": getattr(output, "request_id", None),
        "tos_uri": f"tos://{settings['bucket']}/{object_key}",
        "public_url": tos_public_url(object_key),
    }


def resolve_input(value: str, *, kind: str, upload_local: bool) -> str:
    if is_remote(value):
        return value
    path = pathlib.Path(value).expanduser()
    if not path.is_file():
        raise SeedMediaError(f"Input file not found: {path}")
    size_limits = {"image": 30, "video": 200, "audio": 15}
    if path.stat().st_size > size_limits[kind] * 1024 * 1024:
        raise SeedMediaError(f"A Seedance {kind} input must not exceed {size_limits[kind]} MiB")
    if kind == "image" and not upload_local:
        return local_data_uri(str(path))
    uploaded = tos_upload_path(path, kind=f"inputs/{kind}")
    return uploaded["public_url"]


def add_media_content(
    content: list[dict[str, Any]],
    values: Iterable[str],
    *,
    kind: str,
    role: str,
    upload_local: bool,
) -> None:
    for value in values:
        url = resolve_input(
            value,
            kind=kind,
            upload_local=upload_local,
        )
        content.append({"type": f"{kind}_url", f"{kind}_url": {"url": url}, "role": role})


def command_config(_: argparse.Namespace) -> dict[str, Any]:
    missing = missing_environment(TOS_ENV)
    return {
        "environment_source": "host_process_environment",
        "configured": not missing,
        "missing_environment_variables": missing,
        "tos": {
            "region": os.getenv("STORAGE_TOS_REGION"),
            "endpoint": os.getenv("STORAGE_TOS_ENDPOINT"),
            "bucket": os.getenv("STORAGE_TOS_BUCKET"),
            "prefix": os.getenv("STORAGE_TOS_KEY_PREFIX"),
            "credentials": bool(os.getenv("STORAGE_TOS_ACCESS_KEY_ID"))
            and bool(os.getenv("STORAGE_TOS_SECRET_ACCESS_KEY")),
            "sdk_installed": importlib.util.find_spec("tos") is not None,
        },
    }


def command_upload(args: argparse.Namespace) -> dict[str, Any]:
    require_environment(*TOS_ENV)
    return tos_upload_path(pathlib.Path(args.file).expanduser(), key=args.key, kind=args.kind)


def command_presign(args: argparse.Namespace) -> dict[str, Any]:
    require_environment(*TOS_ENV)
    settings = tos_settings()
    return {
        "bucket": settings["bucket"],
        "key": args.key,
        "method": args.method,
        "expires": args.expires,
        "url": tos_presign(args.key, method=args.method, expires=args.expires),
    }


def command_download(args: argparse.Namespace) -> dict[str, Any]:
    require_environment(*TOS_ENV)
    destination = pathlib.Path(args.output).expanduser()
    url = tos_presign(args.key, expires=args.expires)
    download_url(url, destination, timeout=args.timeout)
    return {
        "key": args.key,
        "local_path": str(destination.resolve()),
        "bytes": destination.stat().st_size,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--pretty", action="store_true")
    root = parser.add_subparsers(dest="command", required=True)

    config = root.add_parser("config", help="Show non-secret TOS configuration status")
    config.set_defaults(handler=command_config)

    upload = root.add_parser("upload", help="Upload a local file")
    upload.add_argument("file")
    upload.add_argument("--key")
    upload.add_argument("--kind", default="assets")
    upload.set_defaults(handler=command_upload)

    presign = root.add_parser("presign", help="Create a temporary signed URL")
    presign.add_argument("key")
    presign.add_argument("--method", choices=("get", "put"), default="get")
    presign.add_argument("--expires", type=int, default=86400)
    presign.set_defaults(handler=command_presign)

    download = root.add_parser("download", help="Download an object using a signed URL")
    download.add_argument("key")
    download.add_argument("output")
    download.add_argument("--expires", type=int, default=3600)
    download.set_defaults(handler=command_download)
    return parser


def run_cli(parser: argparse.ArgumentParser, argv: list[str] | None = None) -> int:
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        emit(result, pretty=args.pretty)
        return 0
    except MissingEnvironmentError as exc:
        emit(
            {
                "ok": False,
                "error": "Host environment variable(s) not configured: "
                + ", ".join(exc.variables),
                "error_code": "missing_environment_variables",
                "missing_environment_variables": exc.variables,
            },
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return 2
    except SeedMediaError as exc:
        emit({"ok": False, "error": str(exc)}, pretty=args.pretty, stream=sys.stderr)
        return 2
    except KeyboardInterrupt:
        emit({"ok": False, "error": "Interrupted"}, pretty=args.pretty, stream=sys.stderr)
        return 130
    except Exception as exc:
        emit(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    return run_cli(build_parser(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
