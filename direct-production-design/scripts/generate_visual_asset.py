#!/usr/bin/env python3
"""Generate one Seedream image directly into its final production asset folder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.visual_asset_generation import (  # noqa: E402
    ASSET_KINDS,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_TIMEOUT,
    VisualAssetGenerationError,
    generate_visual_asset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-kind", required=True, choices=sorted(ASSET_KINDS))
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--reference-image", action="append")
    parser.add_argument("--size", default=DEFAULT_IMAGE_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = generate_visual_asset(
            task_root=args.task_dir,
            asset_id=args.asset_id,
            asset_kind=args.asset_kind,
            prompt_file=args.prompt_file,
            output_path=args.output_path,
            reference_images=args.reference_image,
            size=args.size,
            dry_run=args.dry_run,
            timeout=args.timeout,
        )
    except VisualAssetGenerationError as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
