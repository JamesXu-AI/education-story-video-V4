#!/usr/bin/env python3
"""Run the complete current picture, native-sound, subtitle, and delivery finish."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from assemble_segment_videos import assemble  # noqa: E402
from build_subtitles import DEFAULT_STYLE, build  # noqa: E402
from post_timeline import TimelineError, probe_media  # noqa: E402


class FinishError(RuntimeError):
    """Raised when a task cannot be promoted to final delivery."""


def _load_task(task_dir: Path) -> dict[str, object]:
    path = task_dir / "task.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinishError(f"Invalid task.json: {path}") from exc
    if not isinstance(payload, dict):
        raise FinishError("task.json must contain one JSON object")
    if payload.get("voice_audio_source") != "speaker_reference_audio":
        raise FinishError(
            "task.json voice_audio_source must be speaker_reference_audio"
        )
    if payload.get("dialogue_source") != "seedance":
        raise FinishError("task.json dialogue_source must be seedance")
    return payload


def _promote_clean_master(task_dir: Path, picture_lock: Path) -> Path:
    if not picture_lock.is_file() or picture_lock.stat().st_size <= 0:
        raise FinishError("Native picture lock is missing")
    probe = probe_media(picture_lock)
    if not probe.has_audio:
        raise FinishError("Native picture lock lacks Seedance native audio")
    delivery_root = task_dir / "finish-postproduction"
    delivery_root.mkdir(parents=True, exist_ok=True)
    clean = delivery_root / "final-clean-master.mp4"
    temporary = (
        task_dir
        / ".pending"
        / "finish-postproduction"
        / "post-production"
        / ".final-clean-master.mp4.tmp"
    )
    temporary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(picture_lock, temporary)
    temporary.replace(clean)
    return clean


def finish(task_dir: Path, *, style_path: Path = DEFAULT_STYLE) -> dict[str, object]:
    task_dir = task_dir.expanduser().resolve()
    _load_task(task_dir)
    picture_lock = assemble(task_dir)
    clean = _promote_clean_master(task_dir, picture_lock)
    result = build(task_dir, style_path, render=True)
    if result.get("status") != "FINAL_MASTER_READY":
        raise FinishError("Subtitle/delivery finish did not produce FINAL_MASTER_READY")
    delivery_root = task_dir / "finish-postproduction"
    manifest_path = delivery_root / "final-delivery-manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size <= 0:
        raise FinishError("Final delivery manifest is missing")
    delivery_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audio_sources = delivery_manifest.get("audio_sources")
    if not isinstance(audio_sources, dict):
        raise FinishError("Final delivery manifest lacks audio source declarations")
    if (
        audio_sources.get("seedance_background_music") is not False
        or audio_sources.get("background_music_source") != "none"
    ):
        raise FinishError(
            "Main final delivery must contain no background music source"
        )
    boundary_qc = delivery_manifest.get("boundary_qc")
    if (
        not isinstance(boundary_qc, dict)
        or boundary_qc.get("pre_assembly_status") != "ready_for_picture_lock"
        or boundary_qc.get("final_timeline_status")
        != "technical_audit_complete"
        or boundary_qc.get("source_segments_mutated") is not False
    ):
        raise FinishError("Final delivery lacks a completed reversible boundary QC audit")
    return {
        "status": "FINAL_MASTER_READY",
        "clean_master": str(clean.resolve()),
        "captioned_master": str((delivery_root / "final-captioned-master.mp4").resolve()),
        "srt": str((delivery_root / "subtitles" / "master.srt").resolve()),
        "vtt": str((delivery_root / "subtitles" / "master.vtt").resolve()),
        "manifest": str(manifest_path.resolve()),
        "voice_audio_source": "speaker_reference_audio",
        "dialogue_source": "seedance",
        "native_background_audio_source": audio_sources.get(
            "native_background_audio_source"
        ),
        "seedance_background_music": audio_sources.get(
            "seedance_background_music"
        ),
        "background_music_source": audio_sources.get("background_music_source"),
        "boundary_qc_manifest": boundary_qc.get("manifest"),
        "boundary_repair_count": boundary_qc.get("planned_repair_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--style", type=Path, default=DEFAULT_STYLE)
    args = parser.parse_args()
    try:
        result = finish(args.task_dir, style_path=args.style.expanduser().resolve())
    except (FinishError, TimelineError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
