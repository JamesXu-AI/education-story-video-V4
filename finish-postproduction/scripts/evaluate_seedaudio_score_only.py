#!/usr/bin/env python3
"""Evaluate the real SeedAudio score workflow on an existing video with all old audio removed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from generate_seedaudio_score import (  # noqa: E402
    MusicProductionError,
    build_cue_schedule,
    create_contact_sheet,
    cue_prompt,
    fit_score_to_picture,
    generate_audio,
    join_cues,
    load_music_production,
    media_duration,
    normalize_cue,
    render_score_preview,
    require_complete_file,
    theme_prompt,
    validate_cue_coverage,
    write_json,
)
from post_timeline import probe_media  # noqa: E402


class ScoreEvaluationError(RuntimeError):
    """Raised when score-only evaluation inputs or outputs are invalid."""


def _load_anchors(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreEvaluationError(f"Invalid score anchors: {path}") from exc
    anchors = payload.get("score_anchors") if isinstance(payload, dict) else None
    if not isinstance(anchors, list) or not anchors:
        raise ScoreEvaluationError("Score anchors must contain one nonempty list")
    expected = [f"segment-{index:03d}" for index in range(1, len(anchors) + 1)]
    if [item.get("segment_id") for item in anchors] != expected:
        raise ScoreEvaluationError("Score anchors must be consecutive from segment-001")
    return anchors


def _strip_old_audio(source: Path, output: Path, *, regenerate: bool) -> None:
    if output.is_file() and output.stat().st_size > 0 and not regenerate:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )
    if probe_media(output).has_audio:
        raise ScoreEvaluationError("Silent evaluation picture unexpectedly has audio")


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    source_video = args.video.expanduser().resolve()
    music_plan = args.music_plan.expanduser().resolve()
    anchors_path = args.anchors.expanduser().resolve()
    scripts_dir = args.segment_scripts.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    require_complete_file(source_video, label="source final video")
    config = load_music_production(music_plan)
    anchors = _load_anchors(anchors_path)
    validate_cue_coverage(config, len(anchors))
    for index in range(1, len(anchors) + 1):
        script = scripts_dir / f"segment-{index:02d}.md"
        if not script.is_file():
            script = scripts_dir / f"segment-{index:03d}.md"
        if not script.is_file():
            raise ScoreEvaluationError(f"Missing Segment Script {index}: {scripts_dir}")

    picture_duration = media_duration(source_video)
    if picture_duration <= 0 or picture_duration > 240:
        raise ScoreEvaluationError("Evaluation video runtime must be within 0-240 seconds")
    output_dir.mkdir(parents=True, exist_ok=True)
    silent_picture = output_dir / "picture-lock-with-old-audio-removed.mp4"
    _strip_old_audio(source_video, silent_picture, regenerate=args.regenerate)
    schedule = build_cue_schedule(
        config,
        anchors,
        picture_duration=picture_duration,
    )
    contact_sheet = create_contact_sheet(
        silent_picture,
        timestamps_seconds=[float(anchor["midpoint_seconds"]) for anchor in anchors],
        output=output_dir / "picture-lock-contact-sheet.jpg",
    )

    sample_rate = int(config["seedaudio"]["sample_rate"])
    theme_seconds = float(config["seedaudio"]["theme_palette_seconds"])
    crossfade = float(config["mix"]["cue_crossfade_seconds"])
    theme_raw = output_dir / "theme-palette.raw.wav"
    generate_audio(
        prompt=theme_prompt(
            source_video.stem,
            theme_seconds,
            config["theme"],
            config["cues"],
        ),
        output=theme_raw,
        request_path=output_dir / "theme-palette.request.json",
        response_path=output_dir / "theme-palette.response.json",
        reference_kind="image",
        reference_path=contact_sheet,
        sample_rate=sample_rate,
        timeout=args.timeout,
        regenerate=args.regenerate,
    )
    theme_reference = output_dir / "theme-palette.reference.wav"
    normalize_cue(
        theme_raw,
        theme_reference,
        target_duration=theme_seconds,
        sample_rate=sample_rate,
        overlap_seconds=crossfade,
    )

    normalized_cues: list[Path] = []
    raw_sources: list[Path] = []
    cue_records: list[dict[str, Any]] = []
    for cue_index, scheduled in enumerate(schedule):
        cue = scheduled["cue"]
        segment_summaries = [
            (
                f"Segment {segment_id} follows the authored narrative role and dramatic arc "
                "above; translate only its emotional movement into instrumental music."
            )
            for segment_id in cue["segment_ids"]
        ]
        prompt = cue_prompt(
            cue=cue,
            rendered_duration=float(scheduled["rendered_duration_seconds"]),
            segment_summaries=segment_summaries,
            segment_anchors=scheduled["cue_anchors"],
            cue_timeline_in=float(scheduled["timeline_in_seconds"]),
            cue_timeline_out=float(scheduled["timeline_out_seconds"]),
            overlap_seconds=crossfade,
            is_final_cue=cue_index == len(schedule) - 1,
        )
        cue_id = str(cue["cue_id"])
        raw_path = output_dir / "cues" / f"{cue_id}.raw.wav"
        reference = (
            normalized_cues[0]
            if cue_index == len(schedule) - 1 and normalized_cues
            else theme_reference
        )
        fallback_reason: str | None = None
        force_fallback = cue_id in set(args.force_fallback_cue)
        if force_fallback:
            if not raw_sources:
                raise ScoreEvaluationError(
                    f"Cannot force fallback for {cue_id} without a prior generated Cue"
                )
            raw_source = raw_sources[-1]
            fallback_reason = "operator_selected_after_exhausted_provider_risk_audit"
        else:
            try:
                generate_audio(
                    prompt=prompt,
                    output=raw_path,
                    request_path=output_dir / "cues" / f"{cue_id}.request.json",
                    response_path=output_dir / "cues" / f"{cue_id}.response.json",
                    reference_kind="audio",
                    reference_path=reference,
                    sample_rate=sample_rate,
                    timeout=args.timeout,
                    regenerate=args.regenerate,
                )
                raw_source = raw_path
            except Exception as exc:
                detail = str(exc).lower()
                risk_audit_failure = (
                    "audio risk audit" in detail and '"http_status": 500' in detail
                )
                if (
                    not args.fallback_on_provider_failure
                    or not risk_audit_failure
                    or not raw_sources
                ):
                    raise
                raw_source = raw_sources[-1]
                fallback_reason = "provider_risk_audit_exhausted_reuse_previous_theme_material"
        normalized = output_dir / "cues" / f"{cue_id}.wav"
        normalize_cue(
            raw_source,
            normalized,
            target_duration=float(scheduled["rendered_duration_seconds"]),
            sample_rate=sample_rate,
            overlap_seconds=crossfade,
            fade_edges=False,
            trim_strategy=(
                "tail"
                if cue["cadence"] == "final"
                else "center" if fallback_reason else "head"
            ),
        )
        raw_sources.append(raw_source)
        normalized_cues.append(normalized)
        cue_records.append(
            {
                "cue_id": cue_id,
                "segment_ids": cue["segment_ids"],
                "timeline_in_seconds": scheduled["timeline_in_seconds"],
                "timeline_out_seconds": scheduled["timeline_out_seconds"],
                "rendered_duration_seconds": media_duration(normalized),
                "cadence": cue["cadence"],
                "path": str(normalized.resolve()),
                "provider_generation": (
                    "independent" if fallback_reason is None else "fallback_edit"
                ),
                "fallback_source": (
                    str(raw_source.resolve()) if fallback_reason else None
                ),
                "fallback_reason": fallback_reason,
            }
        )

    joined = output_dir / "seedaudio-score-joined.wav"
    join_cues(normalized_cues, joined, crossfade)
    score = output_dir / "seedaudio-background-music.wav"
    fit_score_to_picture(joined, score, picture_duration)
    evaluation_video = output_dir / "seedaudio-background-music-evaluation.mp4"
    render_score_preview(silent_picture, score, evaluation_video)
    evaluation_probe = probe_media(evaluation_video)
    if not evaluation_probe.has_audio:
        raise ScoreEvaluationError("Score evaluation video has no audio")
    if abs(evaluation_probe.duration_seconds - picture_duration) > 0.25:
        raise ScoreEvaluationError("Score evaluation duration differs from source video")
    manifest = {
        "contract": "finish-score-only-evaluation/v1",
        "status": "SEEDAUDIO_SCORE_ONLY_EVALUATION_READY",
        "source_video": str(source_video),
        "source_audio_policy": "all_old_audio_removed_before_scoring",
        "silent_picture_lock": str(silent_picture.resolve()),
        "picture_duration_seconds": picture_duration,
        "theme_reference": str(theme_reference.resolve()),
        "cues": cue_records,
        "score": str(score.resolve()),
        "evaluation_video": str(evaluation_video.resolve()),
        "warning": "This artifact evaluates background music only; it is not a dialogue/native-sound final mix.",
    }
    write_json(output_dir / "evaluation-manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--music-plan", required=True, type=Path)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--segment-scripts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--fallback-on-provider-failure", action="store_true")
    parser.add_argument("--force-fallback-cue", action="append", default=[])
    return parser


def main() -> int:
    try:
        manifest = evaluate(build_parser().parse_args())
    except (MusicProductionError, ScoreEvaluationError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
