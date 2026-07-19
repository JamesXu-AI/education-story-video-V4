#!/usr/bin/env python3
"""Generate a story-arc SeedAudio score and mix it with an existing Segment cut."""

from __future__ import annotations

import argparse
import base64
import binascii
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


POST_SCRIPTS = Path(__file__).resolve().parent
if str(POST_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(POST_SCRIPTS))

from post_timeline import (  # noqa: E402
    MAX_FINAL_RUNTIME_SECONDS,
    TimelineError,
    load_timeline_artifacts,
    probe_media,
)


provider_path = Path(__file__).resolve().parent / "providers" / "seedaudio.py"
provider_spec = importlib.util.spec_from_file_location("project_seedaudio", provider_path)
if provider_spec is None or provider_spec.loader is None:
    raise RuntimeError(f"Cannot load SeedAudio provider: {provider_path}")
seedaudio = importlib.util.module_from_spec(provider_spec)
provider_spec.loader.exec_module(seedaudio)


SEGMENT_RE = re.compile(r"^segment-([0-9]{3})$")
MAX_TIME_STRETCH_FRACTION = 0.06
FINAL_SCORE_FADE_SECONDS = 2.0
MUSIC_PRODUCTION_FILENAME = "music-production.json"
NO_BACKGROUND_MUSIC_TEXT = "no background music"
SAFE_SEEDAUDIO_PROMPT_CHARACTERS = 2900
SEEDAUDIO_CREATIVE_ROLE = (
    "You are a world-class cinematic soundtrack master, award-winning film composer, "
    "music director, and re-recording mixer. "
)
SEEDAUDIO_IMPACT_STANDARD = (
    "Make the result emotionally breathtaking, deeply moving, and unforgettable through "
    "story precision, thematic transformation, dynamics, silence, and earned musical payoff; "
    "never substitute raw loudness, wall-to-wall density, generic trailer bombast, or dialogue "
    "masking for genuine impact. "
)


class MusicProductionError(RuntimeError):
    """Raised for an invalid music plan or generation result."""


def load_music_production(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MusicProductionError(f"Invalid music-production.json: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "contract",
        "music_provider",
        "seedance_background_music",
        "theme",
        "seedaudio",
        "mix",
        "cues",
    }:
        raise MusicProductionError("music-production.json has an invalid current schema")
    if payload["contract"] != "finish-music-production/v2":
        raise MusicProductionError("music-production.json fixed fields are invalid")
    if payload["music_provider"] != "seedaudio":
        raise MusicProductionError("music_provider must be seedaudio")
    if payload["seedance_background_music"] != "forbidden_and_absent":
        raise MusicProductionError(
            "seedance_background_music must be forbidden_and_absent"
        )
    theme = payload["theme"]
    if not isinstance(theme, dict) or set(theme) != {
        "dramatic_thesis_en",
        "motif_en",
        "instrumentation_en",
        "production_character_en",
        "forbidden_en",
    }:
        raise MusicProductionError("music-production.json theme has an invalid schema")
    for field in (
        "dramatic_thesis_en",
        "motif_en",
        "instrumentation_en",
        "production_character_en",
    ):
        if not isinstance(theme[field], str) or not theme[field].strip():
            raise MusicProductionError(f"theme.{field} must be nonempty")
    if (
        not isinstance(theme["forbidden_en"], list)
        or not theme["forbidden_en"]
        or any(
            not isinstance(item, str) or not item.strip()
            for item in theme["forbidden_en"]
        )
    ):
        raise MusicProductionError("theme.forbidden_en must contain nonempty strings")
    if not isinstance(payload["seedaudio"], dict) or set(payload["seedaudio"]) != {
        "output_format",
        "sample_rate",
        "theme_palette_seconds",
    }:
        raise MusicProductionError("music-production.json seedaudio settings are invalid")
    if payload["seedaudio"]["output_format"] != "wav":
        raise MusicProductionError("SeedAudio score output_format must be wav")
    if payload["seedaudio"]["sample_rate"] != 48000:
        raise MusicProductionError("SeedAudio score sample_rate must be 48000")
    theme_seconds = payload["seedaudio"]["theme_palette_seconds"]
    if (
        isinstance(theme_seconds, bool)
        or not isinstance(theme_seconds, (int, float))
        or not 4 <= float(theme_seconds) <= 60
    ):
        raise MusicProductionError("theme_palette_seconds must be within 4-60")
    if not isinstance(payload["mix"], dict) or set(payload["mix"]) != {
        "cue_crossfade_seconds",
        "music_gain_db",
        "native_gain_db",
        "dialogue_ducking",
        "program_loudness_lufs",
        "true_peak_dbtp",
    }:
        raise MusicProductionError("music-production.json mix settings are invalid")
    mix = payload["mix"]
    for field, lower, upper in (
        ("cue_crossfade_seconds", 0.25, 5.0),
        ("music_gain_db", -36.0, 0.0),
        ("native_gain_db", -12.0, 6.0),
        ("program_loudness_lufs", -24.0, -12.0),
        ("true_peak_dbtp", -6.0, -0.5),
    ):
        value = mix[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not lower <= float(value) <= upper
        ):
            raise MusicProductionError(
                f"mix.{field} must be numeric within {lower}-{upper}"
            )
    ducking = mix["dialogue_ducking"]
    if not isinstance(ducking, dict) or set(ducking) != {
        "enabled",
        "threshold",
        "ratio",
        "attack_ms",
        "release_ms",
    }:
        raise MusicProductionError("mix.dialogue_ducking has an invalid schema")
    if not isinstance(ducking["enabled"], bool):
        raise MusicProductionError("mix.dialogue_ducking.enabled must be boolean")
    for field, lower, upper in (
        ("threshold", 0.001, 1.0),
        ("ratio", 1.0, 20.0),
        ("attack_ms", 0.01, 2000.0),
        ("release_ms", 0.01, 9000.0),
    ):
        value = ducking[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not lower <= float(value) <= upper
        ):
            raise MusicProductionError(
                f"mix.dialogue_ducking.{field} must be numeric within {lower}-{upper}"
            )
    cues = payload["cues"]
    if not isinstance(cues, list) or not cues:
        raise MusicProductionError("SeedAudio music requires at least one authored cue")
    cue_ids: set[str] = set()
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {
            "cue_id",
            "segment_ids",
            "narrative_role_en",
            "dramatic_arc_en",
            "music_state_in_en",
            "music_state_out_en",
            "dialogue_and_effect_space_en",
            "direction_en",
            "cadence",
        }:
            raise MusicProductionError("music-production.json contains an invalid cue")
        cue_id = cue["cue_id"]
        if (
            not isinstance(cue_id, str)
            or not re.fullmatch(r"cue-[0-9]{3}", cue_id)
            or cue_id in cue_ids
        ):
            raise MusicProductionError("Cue IDs must be unique cue-NNN values")
        cue_ids.add(cue_id)
        segment_ids = cue["segment_ids"]
        if (
            not isinstance(segment_ids, list)
            or not segment_ids
            or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 1
                for item in segment_ids
            )
            or segment_ids != list(range(segment_ids[0], segment_ids[-1] + 1))
        ):
            raise MusicProductionError(
                f"{cue_id} segment_ids must be one nonempty consecutive range"
            )
        for field in (
            "narrative_role_en",
            "dramatic_arc_en",
            "music_state_in_en",
            "music_state_out_en",
            "dialogue_and_effect_space_en",
            "direction_en",
        ):
            if not isinstance(cue[field], str) or not cue[field].strip():
                raise MusicProductionError(f"{cue_id}.{field} must be nonempty")
        if cue["cadence"] not in {"carry", "final"}:
            raise MusicProductionError(f"{cue_id}.cadence must be carry or final")
    if any(cue["cadence"] != "carry" for cue in cues[:-1]):
        raise MusicProductionError("Only the final SeedAudio cue may resolve")
    if cues[-1]["cadence"] != "final":
        raise MusicProductionError("The final SeedAudio cue must declare final cadence")
    return payload


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def require_complete_file(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise MusicProductionError(f"{label} is missing or empty: {path}")
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
    }


def validate_native_audio_track(
    audio_timeline: dict[str, Any],
    *,
    segment_count: int,
    picture_duration: float,
) -> dict[str, Any]:
    native_track = next(
        (
            track
            for track in audio_timeline.get("tracks", [])
            if track.get("track_id") == "native-sync"
        ),
        None,
    )
    if not isinstance(native_track, dict):
        raise MusicProductionError("audio-timeline.json has no native-sync track")
    events = native_track.get("events")
    if not isinstance(events, list) or len(events) != segment_count:
        raise MusicProductionError(
            "native-sync track must contain exactly one event per Segment"
        )
    expected_ids = [f"segment-{index:03d}" for index in range(1, segment_count + 1)]
    actual_ids = [event.get("segment_id") for event in events]
    if actual_ids != expected_ids:
        raise MusicProductionError("native-sync Segment coverage is incomplete or reordered")
    if any(event.get("has_source_audio") is not True for event in events):
        raise MusicProductionError(
            "Every Segment must retain a real native dialogue/foley/ambience audio stream"
        )
    if any(event.get("preserve_lip_sync") is not True for event in events):
        raise MusicProductionError(
            "Every native-sync event must explicitly preserve dialogue lip sync"
        )
    cursor = 0.0
    for event in events:
        source = Path(str(event.get("source") or ""))
        require_complete_file(source, label="native Segment media")
        start = float(event.get("timeline_in_seconds", -1))
        end = float(event.get("timeline_out_seconds", -1))
        if start > cursor + 0.001 or end <= start:
            raise MusicProductionError(
                "native-sync events must cover picture lock continuously without gaps"
            )
        if (
            start < cursor - 0.001
            and event.get("transition_overlap_allowed") is not True
        ):
            raise MusicProductionError(
                "native-sync overlap is present without an authored transition"
            )
        cursor = max(cursor, end)
    if abs(cursor - picture_duration) > 0.25:
        raise MusicProductionError(
            "native-sync track duration does not cover the complete picture lock"
        )
    return {
        "status": "complete",
        "segment_ids": expected_ids,
        "event_count": len(events),
        "timeline_out_seconds": round(cursor, 6),
        "lip_sync_preserved": all(
            event.get("preserve_lip_sync") is True for event in events
        ),
    }


def detect_baked_seedance_music(
    task_dir: Path,
    *,
    scripts_dir: Path,
    segment_ids: list[int],
) -> list[dict[str, Any]]:
    """Return only explicit script/config or persisted media-analysis evidence."""

    evidence: list[dict[str, Any]] = []
    for segment_id in segment_ids:
        script = scripts_dir / f"segment-{segment_id:03d}.md"
        if script.is_file() and re.search(
            r"^-\s*`?seedance_background_music`?:\s*true\s*$",
            script.read_text(encoding="utf-8"),
            re.MULTILINE | re.IGNORECASE,
        ):
            evidence.append(
                {
                    "segment_id": segment_id,
                    "source": str(script.resolve()),
                    "kind": "segment_script_configuration",
                }
            )
        artifacts_path = (
            task_dir
            / ".pending"
            / "virtual-production"
            / "generation-segments"
            / f"segment-{segment_id:03d}"
            / "artifacts.json"
        )
        if not artifacts_path.is_file():
            continue
        try:
            artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        audio_analysis = artifacts.get("audio_analysis")
        detected = artifacts.get("baked_seedance_music_detected") is True or (
            isinstance(audio_analysis, dict)
            and audio_analysis.get("baked_seedance_music_detected") is True
        )
        if detected:
            evidence.append(
                {
                    "segment_id": segment_id,
                    "source": str(artifacts_path.resolve()),
                    "kind": "persisted_media_analysis",
                }
            )
    return evidence


def _declares_no_background_music(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return NO_BACKGROUND_MUSIC_TEXT in normalized or any(
        phrase in normalized
        for phrase in (
            "do not generate background music",
            "without background music",
            "background music is forbidden",
        )
    )


def _request_text(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MusicProductionError(f"Invalid Seedance request: {path}") from exc
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, list):
        raise MusicProductionError(f"Seedance request has no content list: {path}")
    return "\n".join(
        str(item.get("text") or "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def validate_no_seedance_background_music(
    task_dir: Path,
    *,
    scripts_dir: Path,
    segment_ids: list[int],
) -> list[dict[str, Any]]:
    """Require the submitted Seedance Prompt to forbid non-diegetic music."""

    generation_root = (
        task_dir / ".pending" / "virtual-production" / "generation-segments"
    )
    evidence: list[dict[str, Any]] = []
    defects = detect_baked_seedance_music(
        task_dir,
        scripts_dir=scripts_dir,
        segment_ids=segment_ids,
    )
    for segment_id in segment_ids:
        segment_name = f"segment-{segment_id:03d}"
        script_path = scripts_dir / f"{segment_name}.md"
        try:
            script_text = script_path.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError) as exc:
            raise MusicProductionError(
                f"Invalid Seed Master Segment Script: {script_path}"
            ) from exc
        explicit_false = bool(
            re.search(
                r"^-\s*`?seedance_background_music`?:\s*false\s*$",
                script_text,
                re.MULTILINE | re.IGNORECASE,
            )
        )
        if not explicit_false and not _declares_no_background_music(script_text):
            defects.append(
                {
                    "segment_id": segment_id,
                    "source": str(script_path.resolve()),
                    "kind": "missing_segment_no_background_music_contract",
                }
            )
        request_path = generation_root / segment_name / "seedance-request.json"
        request_text = _request_text(request_path)
        if not _declares_no_background_music(request_text):
            defects.append(
                {
                    "segment_id": segment_id,
                    "source": str(request_path.resolve()),
                    "kind": "submitted_prompt_allows_background_music",
                }
            )
        evidence.append(
            {
                "segment_id": segment_id,
                "segment_script": str(script_path.resolve()),
                "seedance_request": str(request_path.resolve()),
                "script_contract": "explicit_false" if explicit_false else "prompt_text",
                "submitted_prompt_contract": "no_background_music",
            }
        )
    if defects:
        raise MusicProductionError(
            "SeedAudio scoring requires every submitted Seedance Segment to forbid "
            "background music; defects="
            + json.dumps(defects, ensure_ascii=False)
        )
    return evidence


def verify_final_master(
    *,
    music_provider: str,
    final_master: Path,
    native_picture_lock: Path,
    picture_duration: float,
    segment_count: int,
    audio_timeline: dict[str, Any],
    config: dict[str, Any],
    cue_records: list[dict[str, Any]] | None = None,
    final_score: Path | None = None,
) -> dict[str, Any]:
    if music_provider != "seedaudio":
        raise MusicProductionError("The No-BGM finish supports only SeedAudio score")
    final_integrity = require_complete_file(final_master, label="final master")
    native_integrity = require_complete_file(
        native_picture_lock, label="native picture lock"
    )
    final_probe = probe_media(final_master)
    native_probe = probe_media(native_picture_lock)
    if not final_probe.has_audio or not native_probe.has_audio:
        raise MusicProductionError(
            "Final master and native picture lock must both contain audio streams"
        )
    if final_probe.width <= 0 or final_probe.height <= 0:
        raise MusicProductionError("Final master has no valid video stream")
    if abs(final_probe.duration_seconds - picture_duration) > 0.25:
        raise MusicProductionError("Final master duration does not match picture lock")
    if abs(native_probe.duration_seconds - picture_duration) > 0.25:
        raise MusicProductionError("Native picture-lock duration is inconsistent")
    if final_probe.duration_seconds > MAX_FINAL_RUNTIME_SECONDS + 1e-3:
        raise MusicProductionError("Final master exceeds the 240-second limit")
    native_track = validate_native_audio_track(
        audio_timeline,
        segment_count=segment_count,
        picture_duration=picture_duration,
    )
    checks: dict[str, Any] = {
        "duration_match": True,
        "video_stream_present": True,
        "audio_stream_present": True,
        "native_dialogue_track": native_track,
        "file_integrity": {
            "final_master": final_integrity,
            "native_picture_lock": native_integrity,
        },
    }
    cue_records = cue_records or []
    validate_cue_coverage(config, segment_count)
    rendered_coverage = [
        segment_id
        for cue in cue_records
        for segment_id in cue.get("segment_ids", [])
    ]
    if rendered_coverage != list(range(1, segment_count + 1)):
        raise MusicProductionError(
            "Rendered SeedAudio cues do not cover every Segment exactly once"
        )
    if not cue_records or cue_records[-1].get("final_cadence_required") is not True:
        raise MusicProductionError(
            "The final SeedAudio cue lacks verified final-cadence instruction"
        )
    if final_score is None:
        raise MusicProductionError("Final SeedAudio score is missing")
    if audio_timeline.get("score_cues") != cue_records:
        raise MusicProductionError(
            "audio-timeline.json score_cues do not match the rendered cue records"
        )
    score_track = next(
        (
            track
            for track in audio_timeline.get("tracks", [])
            if track.get("track_id") == "seedaudio-score"
        ),
        None,
    )
    score_events = score_track.get("events") if isinstance(score_track, dict) else None
    if not isinstance(score_events, list) or len(score_events) != 1:
        raise MusicProductionError(
            "audio-timeline.json must bind exactly one picture-lock SeedAudio score event"
        )
    score_event = score_events[0]
    if (
        Path(str(score_event.get("source") or "")).resolve()
        != final_score.resolve()
        or abs(float(score_event.get("timeline_in_seconds", -1))) > 0.001
        or abs(float(score_event.get("timeline_out_seconds", -1)) - picture_duration)
        > 0.25
        or score_event.get("preserve_across_segment_cuts") is not True
    ):
        raise MusicProductionError(
            "SeedAudio score event is not bound to the complete picture-lock timeline"
        )
    score_integrity = require_complete_file(final_score, label="final SeedAudio score")
    if abs(media_duration(final_score) - picture_duration) > 0.25:
        raise MusicProductionError("Final SeedAudio score duration does not match picture lock")
    checks.update(
        {
            "cue_coverage": {
                "status": "complete",
                "segment_ids": rendered_coverage,
            },
            "final_fade": {
                "status": "verified_render_instruction",
                "duration_seconds": FINAL_SCORE_FADE_SECONDS,
            },
            "final_cadence": {
                "status": "verified_prompt_instruction",
                "cue_id": cue_records[-1]["cue_id"],
            },
        }
    )
    checks["file_integrity"]["score"] = score_integrity
    return checks


def segment_videos(task_dir: Path) -> list[tuple[int, Path, float]]:
    root = task_dir / ".pending" / "virtual-production" / "generation-segments"
    records: list[tuple[int, Path, float]] = []
    if not root.is_dir():
        raise MusicProductionError(f"Missing generated Segments: {root}")
    for directory in root.iterdir():
        match = SEGMENT_RE.fullmatch(directory.name) if directory.is_dir() else None
        if not match:
            continue
        video = directory / "video.mp4"
        if not video.is_file():
            raise MusicProductionError(f"Missing Segment video: {video}")
        records.append((int(match.group(1)), video.resolve(), media_duration(video)))
    records.sort()
    ids = [record[0] for record in records]
    if not ids or ids != list(range(1, len(ids) + 1)):
        raise MusicProductionError("Segment videos must be consecutive from segment-001")
    return records


def validate_cue_coverage(config: dict[str, Any], segment_count: int) -> None:
    covered: list[int] = []
    for cue in config["cues"]:
        covered.extend(cue["segment_ids"])
    expected = list(range(1, segment_count + 1))
    if covered != expected:
        raise MusicProductionError(
            f"Music cues must cover every Segment exactly once in order; got {covered}"
        )


def create_contact_sheet(
    final_video: Path,
    *,
    timestamps_seconds: list[float],
    output: Path,
) -> Path:
    segment_count = len(timestamps_seconds)
    if not timestamps_seconds:
        raise MusicProductionError("Picture timeline has no Segment anchors")
    columns = min(4, segment_count)
    rows = math.ceil(segment_count / columns)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="seedaudio-contact-") as temporary:
        frame_root = Path(temporary)
        for index, timestamp in enumerate(timestamps_seconds):
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{timestamp:.6f}",
                    "-i",
                    str(final_video),
                    "-vf",
                    "scale=480:-2",
                    "-frames:v",
                    "1",
                    str(frame_root / f"frame-{index:03d}.jpg"),
                ]
            )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                "1",
                "-i",
                str(frame_root / "frame-%03d.jpg"),
                "-vf",
                f"tile={columns}x{rows}:nb_frames={segment_count}:padding=6:margin=6",
                "-frames:v",
                "1",
                str(output),
            ]
        )
    if not output.is_file() or output.stat().st_size == 0:
        raise MusicProductionError("Could not create the picture-lock contact sheet")
    return output


def compact_segment_performance(script_path: Path, limit: int = 520) -> str:
    text = script_path.read_text(encoding="utf-8")
    try:
        section = text.split(
            "Part 2 — Ordered internal shots and performance", 1
        )[1].split(
            "Part 3 — Continuity, audio, quality, and duration acceptance", 1
        )[0]
    except IndexError as exc:
        raise MusicProductionError(
            f"Invalid Seed Master Route B Segment Script: {script_path}"
        ) from exc
    kept: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or line.startswith("###"):
            continue
        kept.append(line)
    compact = " ".join(kept)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def theme_prompt(
    title: str,
    duration: float,
    theme: dict[str, Any],
    cues: list[dict[str, Any]],
) -> str:
    cue_roles = " ".join(
        f"{cue['cue_id']}: {cue['narrative_role_en']}"
        for cue in cues
    )
    forbidden = "; ".join(str(item) for item in theme["forbidden_en"])

    def compose(current_cue_roles: str) -> str:
        return (
            f"{SEEDAUDIO_CREATIVE_ROLE}{SEEDAUDIO_IMPACT_STANDARD}"
            f"Create an instrumental cinematic theme palette lasting exactly {duration:.1f} "
            f"seconds for project {title!r}, guided by the supplied picture-lock contact sheet. "
            f"Dramatic thesis: {theme['dramatic_thesis_en']} Motif contract: "
            f"{theme['motif_en']} Instrumentation: {theme['instrumentation_en']} Production "
            f"character: {theme['production_character_en']} Planned story transformations: "
            f"{current_cue_roles} Present one memorable motif that can transform across the "
            "complete dramatic arc without resolving at internal picture cuts. Instrumental "
            "music only: absolutely no speech, narration, singing, chanting, vocalization, "
            f"dialogue, ambience, foley, or sound effects. Forbidden: {forbidden}. Present the "
            "motif clearly and end with a clean reusable decay."
        )

    prompt = compose(cue_roles)
    if len(prompt) > SAFE_SEEDAUDIO_PROMPT_CHARACTERS:
        overflow = len(prompt) - SAFE_SEEDAUDIO_PROMPT_CHARACTERS
        retained = len(cue_roles) - overflow - 1
        if retained >= 120:
            cue_roles = cue_roles[:retained].rstrip() + "…"
            prompt = compose(cue_roles)
    if len(prompt) > SAFE_SEEDAUDIO_PROMPT_CHARACTERS:
        raise MusicProductionError(
            "SeedAudio theme Prompt exceeds the safe 2900-character budget; shorten "
            "theme fields or forbidden items"
        )
    return prompt


def cue_prompt(
    *,
    cue: dict[str, Any],
    rendered_duration: float,
    segment_summaries: list[str],
    segment_anchors: list[dict[str, Any]],
    cue_timeline_in: float,
    cue_timeline_out: float,
    overlap_seconds: float,
    is_final_cue: bool,
) -> str:
    segment_text = " ".join(
        f"Segment {segment_id} [{float(anchor['timeline_in_seconds']):.3f}-"
        f"{float(anchor['timeline_out_seconds']):.3f}s]: {summary}"
        for segment_id, summary, anchor in zip(
            cue["segment_ids"], segment_summaries, segment_anchors
        )
    )
    ending_instruction = (
        "Land the score's sole complete cadence exactly at the authored film ending, "
        "then allow only the controlled final decay. "
        if is_final_cue and cue["cadence"] == "final"
        else "Do not cadence or resolve at this picture cut; carry harmonic and rhythmic "
        "momentum through the closing handle for the next story-arc cue. "
    )
    def compose(current_segment_text: str) -> str:
        return (
            f"{SEEDAUDIO_CREATIVE_ROLE}{SEEDAUDIO_IMPACT_STANDARD}"
            f"@Audio1 is the project theme palette: inherit only its four-note motif, "
            f"instrument family, tonal world, and production character. Create exactly "
            f"{rendered_duration:.3f} seconds of instrumental cinematic underscore for "
            f"{cue['cue_id']}, covering Screenplay Segments "
            f"{','.join(str(item) for item in cue['segment_ids'])}. Narrative role: "
            f"{cue['narrative_role_en']} Dramatic arc: {cue['dramatic_arc_en']} Music state "
            f"in: {cue['music_state_in_en']} Music state out: {cue['music_state_out_en']} "
            f"Detailed direction: {cue['direction_en']} Dialogue and effects space: "
            f"{cue['dialogue_and_effect_space_en']} The picture-locked cue occupies absolute "
            f"timeline {cue_timeline_in:.3f}-{cue_timeline_out:.3f} seconds. Picture-locked "
            f"story material: {current_segment_text} Provide musical material through the "
            f"opening and closing {overlap_seconds:.1f}-second handles so adjacent story-arc "
            f"cues can use an equal-power crossfade. {ending_instruction}Use only the "
            "project-derived instrument family, tonal world, and production character "
            "established in @Audio1. Keep the track a clean music stem."
        )

    prompt = compose(segment_text)
    if len(prompt) > SAFE_SEEDAUDIO_PROMPT_CHARACTERS:
        overflow = len(prompt) - SAFE_SEEDAUDIO_PROMPT_CHARACTERS
        retained = len(segment_text) - overflow
        if retained >= 160:
            segment_text = segment_text[: retained - 1].rstrip() + "…"
            prompt = compose(segment_text)
    if len(prompt) > SAFE_SEEDAUDIO_PROMPT_CHARACTERS:
        raise MusicProductionError(
            f"SeedAudio prompt for {cue['cue_id']} exceeds the safe 2900-character budget"
        )
    return prompt


def save_provider_audio(
    result: dict[str, Any], output: Path, *, timeout: int
) -> dict[str, Any]:
    encoded = result.get("audio") or result.get("data")
    if isinstance(encoded, str) and encoded:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MusicProductionError("SeedAudio returned invalid Base64 audio") from exc
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_bytes(raw)
        temporary.replace(output)
    elif isinstance(result.get("url"), str) and result["url"]:
        seedaudio.core.download_url(str(result["url"]), output, timeout=timeout)
    else:
        raise MusicProductionError("SeedAudio response did not contain audio data or a URL")
    if not output.is_file() or output.stat().st_size == 0:
        raise MusicProductionError(f"SeedAudio output is empty: {output}")
    persisted = dict(result)
    for key in ("audio", "data"):
        value = persisted.pop(key, None)
        if isinstance(value, str):
            persisted[f"{key}_base64_characters"] = len(value)
    persisted["local_path"] = str(output.resolve())
    return persisted


def generate_audio(
    *,
    prompt: str,
    output: Path,
    request_path: Path,
    response_path: Path,
    reference_kind: str,
    reference_path: Path,
    sample_rate: int,
    timeout: int,
    regenerate: bool,
) -> dict[str, Any]:
    if output.is_file() and output.stat().st_size > 0 and not regenerate:
        print(f"REUSE {output.name}", flush=True)
        return {"status": "reused", "local_path": str(output.resolve())}
    if reference_kind == "image":
        references = [seedaudio.resolve_image_reference(str(reference_path))]
    elif reference_kind == "audio":
        references = [seedaudio.resolve_audio_reference(str(reference_path))]
    else:
        raise MusicProductionError(f"Unsupported SeedAudio reference kind: {reference_kind}")
    payload = {
        "model": seedaudio.model_id(),
        "text_prompt": prompt,
        "audio_config": {
            "format": "wav",
            "sample_rate": sample_rate,
            "enable_subtitle": False,
        },
        "references": references,
    }
    write_json(
        request_path,
        {
            "model": payload["model"],
            "text_prompt": prompt,
            "audio_config": payload["audio_config"],
            "reference_kind": reference_kind,
            "reference_path": str(reference_path.resolve()),
        },
    )
    result: dict[str, Any] | None = None
    provider_attempt = 0
    for provider_attempt in range(1, 4):
        print(
            f"GENERATE {output.stem} reference={reference_kind} "
            f"attempt={provider_attempt}/3",
            flush=True,
        )
        try:
            result = seedaudio.request_audio(payload, timeout=timeout)
            break
        except Exception as exc:
            detail = str(exc).lower()
            transient = any(
                marker in detail
                for marker in (
                    '"http_status": 500',
                    "audio risk audit",
                    "network request failed",
                    "timed out",
                    "connection reset",
                )
            )
            if not transient or provider_attempt == 3:
                raise
            print(
                f"RETRY {output.stem} transient_provider_failure "
                f"next_attempt={provider_attempt + 1}/3",
                flush=True,
            )
            time.sleep(2)
    if result is None:
        raise MusicProductionError("SeedAudio provider returned no result")
    persisted = save_provider_audio(result, output, timeout=timeout)
    persisted["provider_attempt_count"] = provider_attempt
    write_json(response_path, persisted)
    print(
        f"GENERATED {output.name} duration={media_duration(output):.3f}s "
        f"bytes={output.stat().st_size}",
        flush=True,
    )
    return persisted


def atempo_chain(ratio: float) -> str:
    if ratio <= 0:
        raise MusicProductionError("Invalid audio tempo ratio")
    factors: list[float] = []
    while ratio < 0.5:
        factors.append(0.5)
        ratio /= 0.5
    while ratio > 2.0:
        factors.append(2.0)
        ratio /= 2.0
    factors.append(ratio)
    return ",".join(f"atempo={factor:.9f}" for factor in factors)


def safe_tempo_ratio(
    source_duration: float,
    target_duration: float,
    *,
    context: str,
) -> float:
    if source_duration <= 0 or target_duration <= 0:
        raise MusicProductionError(f"Invalid duration while fitting {context}")
    ratio = source_duration / target_duration
    lower = 1.0 - MAX_TIME_STRETCH_FRACTION
    upper = 1.0 + MAX_TIME_STRETCH_FRACTION
    if ratio < lower or ratio > upper:
        delta_percent = abs(ratio - 1.0) * 100
        raise MusicProductionError(
            f"{context} requires {delta_percent:.2f}% time-stretch, beyond the ±6% safety cap. "
            "Regenerate that SeedAudio asset to the requested picture-lock duration; do not "
            "force-fit or truncate it."
        )
    return ratio


def audio_conform_plan(
    source_duration: float,
    target_duration: float,
    *,
    context: str,
    trim_strategy: str,
) -> dict[str, float | str]:
    """Prefer exact trimming for SeedAudio's long fixed output; tempo only small drift."""

    if trim_strategy not in {"head", "center", "tail"}:
        raise MusicProductionError(f"Invalid SeedAudio trim strategy: {trim_strategy}")
    if source_duration <= 0 or target_duration <= 0:
        raise MusicProductionError(f"Invalid duration while fitting {context}")
    if source_duration > target_duration * (1.0 + MAX_TIME_STRETCH_FRACTION):
        if trim_strategy == "head":
            start = 0.0
        elif trim_strategy == "center":
            start = (source_duration - target_duration) / 2
        else:
            start = source_duration - target_duration
        return {
            "mode": "trim",
            "source_start_seconds": start,
            "tempo_ratio": 1.0,
        }
    return {
        "mode": "tempo",
        "source_start_seconds": 0.0,
        "tempo_ratio": safe_tempo_ratio(
            source_duration,
            target_duration,
            context=context,
        ),
    }


def normalize_cue(
    source: Path,
    output: Path,
    *,
    target_duration: float,
    sample_rate: int,
    overlap_seconds: float,
    fade_edges: bool = True,
    trim_strategy: str = "head",
) -> None:
    source_duration = media_duration(source)
    conform = audio_conform_plan(
        source_duration,
        target_duration,
        context=f"SeedAudio asset {source.name}",
        trim_strategy=trim_strategy,
    )
    fade = min(max(overlap_seconds * 0.5, 0.35), target_duration / 4)
    filters = [
        f"aresample={sample_rate}",
        "aformat=sample_fmts=fltp:channel_layouts=stereo",
    ]
    if conform["mode"] == "trim":
        filters.append(
            f"atrim=start={float(conform['source_start_seconds']):.6f}:"
            f"duration={target_duration:.6f}"
        )
    else:
        filters.extend(
            [
                atempo_chain(float(conform["tempo_ratio"])),
                f"apad=pad_dur={target_duration:.6f}",
                f"atrim=duration={target_duration:.6f}",
            ]
        )
    filters.append("asetpts=PTS-STARTPTS")
    if fade_edges:
        filters.extend(
            [
                f"afade=t=in:st=0:d={fade:.6f}",
                f"afade=t=out:st={max(0.0, target_duration - fade):.6f}:d={fade:.6f}",
            ]
        )
    audio_filter = ",".join(filters)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            audio_filter,
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )


def join_cues(cues: list[Path], output: Path, crossfade_seconds: float) -> None:
    if not cues:
        raise MusicProductionError("No SeedAudio cues were generated")
    if len(cues) == 1:
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(cues[0]),
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )
        return
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for cue in cues:
        command.extend(["-i", str(cue)])
    chains: list[str] = []
    previous = "[0:a]"
    for index in range(1, len(cues)):
        label = f"score{index}"
        chains.append(
            f"{previous}[{index}:a]acrossfade=d={crossfade_seconds:.6f}:c1=qsin:c2=qsin[{label}]"
        )
        previous = f"[{label}]"
    command.extend(
        [
            "-filter_complex",
            ";".join(chains),
            "-map",
            previous,
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    run(command)


def fit_score_to_picture(source: Path, output: Path, picture_duration: float) -> None:
    tempo = safe_tempo_ratio(
        media_duration(source),
        picture_duration,
        context="joined SeedAudio score",
    )
    fade_start = max(0.0, picture_duration - FINAL_SCORE_FADE_SECONDS)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            (
                f"{atempo_chain(tempo)},apad=pad_dur=5,"
                f"atrim=duration={picture_duration:.6f},"
                f"afade=t=out:st={fade_start:.6f}:d={FINAL_SCORE_FADE_SECONDS:.6f}"
            ),
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )


def render_score_preview(final_video: Path, score: Path, output: Path) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(final_video),
            "-i",
            str(score),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )


def build_mix_filter(mix: dict[str, Any]) -> str:
    music_gain_db = float(mix["music_gain_db"])
    native_gain_db = float(mix["native_gain_db"])
    ducking = mix["dialogue_ducking"]
    native_format = (
        "aresample=48000,"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    )
    chains: list[str] = []
    if ducking["enabled"]:
        chains.extend(
            [
                f"[0:a]{native_format},asplit=2[nativebase][keysource]",
                f"[nativebase]volume={native_gain_db:.3f}dB[native]",
                (
                    "[keysource]dialoguenhance=original=0:enhance=3:voice=16,"
                    "pan=mono|c0=c2[dialoguekey]"
                ),
                f"[1:a]{native_format},volume={music_gain_db:.3f}dB[scorepre]",
                (
                    "[scorepre][dialoguekey]sidechaincompress="
                    f"threshold={float(ducking['threshold']):.6f}:"
                    f"ratio={float(ducking['ratio']):.3f}:"
                    f"attack={float(ducking['attack_ms']):.3f}:"
                    f"release={float(ducking['release_ms']):.3f}:"
                    "knee=4:link=maximum:detection=rms[score]"
                ),
            ]
        )
    else:
        chains.extend(
            [
                f"[0:a]{native_format},volume={native_gain_db:.3f}dB[native]",
                f"[1:a]{native_format},volume={music_gain_db:.3f}dB[score]",
            ]
        )
    limiter = 10 ** (float(mix["true_peak_dbtp"]) / 20.0)
    chains.append(
        "[native][score]amix=inputs=2:duration=first:normalize=0,"
        f"loudnorm=I={float(mix['program_loudness_lufs']):.2f}:LRA=11:"
        f"TP={float(mix['true_peak_dbtp']):.2f},"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
        f"alimiter=limit={limiter:.6f}:level=false[mix]"
    )
    return ";".join(chains)


def render_mix_test(
    final_video: Path,
    score: Path,
    output: Path,
    *,
    mix: dict[str, Any],
) -> None:
    filter_complex = build_mix_filter(mix)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(final_video),
            "-i",
            str(score),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[mix]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )


def build_cue_schedule(
    config: dict[str, Any],
    score_anchors: list[dict[str, Any]],
    *,
    picture_duration: float,
) -> list[dict[str, Any]]:
    """Partition picture lock into continuous story-cue ranges with xfade handles."""

    anchor_by_id = {
        int(str(anchor["segment_id"]).removeprefix("segment-")): anchor
        for anchor in score_anchors
    }
    cues = config["cues"]
    crossfade = float(config["mix"]["cue_crossfade_seconds"])
    schedule: list[dict[str, Any]] = []
    for cue_index, cue in enumerate(cues):
        try:
            cue_anchors = [anchor_by_id[item] for item in cue["segment_ids"]]
        except KeyError as exc:
            raise MusicProductionError(
                f"{cue['cue_id']} references a missing picture-lock Segment"
            ) from exc
        timeline_in = float(cue_anchors[0]["timeline_in_seconds"])
        if cue_index + 1 < len(cues):
            next_first_segment = cues[cue_index + 1]["segment_ids"][0]
            timeline_out = float(
                anchor_by_id[next_first_segment]["timeline_in_seconds"]
            )
        else:
            timeline_out = picture_duration
        timeline_duration = timeline_out - timeline_in
        if timeline_duration <= 0:
            raise MusicProductionError(
                f"{cue['cue_id']} has a non-positive picture-lock duration"
            )
        if len(cues) == 1:
            handle = 0.0
        else:
            handle = crossfade / 2 if cue_index in {0, len(cues) - 1} else crossfade
        rendered_duration = timeline_duration + handle
        if len(cues) > 1 and rendered_duration <= crossfade:
            raise MusicProductionError(
                f"{cue['cue_id']} is too short for the authored cue crossfade"
            )
        schedule.append(
            {
                "cue": cue,
                "cue_anchors": cue_anchors,
                "timeline_in_seconds": timeline_in,
                "timeline_out_seconds": timeline_out,
                "timeline_duration_seconds": timeline_duration,
                "rendered_duration_seconds": rendered_duration,
            }
        )
    if abs(float(schedule[0]["timeline_in_seconds"])) > 0.001:
        raise MusicProductionError("SeedAudio cue schedule must begin at picture-lock zero")
    for previous, current in zip(schedule, schedule[1:]):
        if abs(
            float(previous["timeline_out_seconds"])
            - float(current["timeline_in_seconds"])
        ) > 0.001:
            raise MusicProductionError("SeedAudio cue schedule contains a gap or overlap")
    if abs(float(schedule[-1]["timeline_out_seconds"]) - picture_duration) > 0.001:
        raise MusicProductionError("SeedAudio cue schedule must end at picture lock")
    return schedule


def execute(args: argparse.Namespace) -> int:
    task_dir = args.task_dir.expanduser().resolve()
    finish_root = task_dir / "finish-postproduction"
    finish_pending = task_dir / ".pending" / "finish-postproduction"
    virtual_pending = task_dir / ".pending" / "virtual-production"
    config_path = finish_root / MUSIC_PRODUCTION_FILENAME
    config = load_music_production(config_path)
    picture_lock = (
        args.video.expanduser().resolve()
        if args.video
        else finish_pending / "post-production" / "native-picture-lock.mp4"
    )
    if not picture_lock.is_file():
        raise MusicProductionError(f"Missing native picture lock: {picture_lock}")
    records = segment_videos(task_dir)
    validate_cue_coverage(config, len(records))
    try:
        picture_edl, audio_timeline = load_timeline_artifacts(task_dir)
    except TimelineError as exc:
        raise MusicProductionError(str(exc)) from exc
    picture_events = picture_edl.get("picture_events")
    if not isinstance(picture_events, list):
        raise MusicProductionError("Invalid picture timeline artifact")
    score_anchors = [
        {
            "segment_id": event.get("segment_id"),
            "timeline_in_seconds": event.get("timeline_in_seconds"),
            "timeline_out_seconds": event.get("timeline_out_seconds"),
            "midpoint_seconds": (
                float(event.get("timeline_in_seconds", 0))
                + float(event.get("timeline_out_seconds", 0))
            )
            / 2,
        }
        for event in picture_events
    ]
    expected_ids = [f"segment-{index:03d}" for index in range(1, len(records) + 1)]
    timeline_ids = [event.get("segment_id") for event in picture_events]
    anchor_ids = [anchor.get("segment_id") for anchor in score_anchors]
    if timeline_ids != expected_ids or anchor_ids != expected_ids:
        raise MusicProductionError(
            "Picture/audio timeline Segment ids do not match generated media; rerun assembly"
        )
    timeline_duration = float(picture_edl.get("duration_seconds", 0))
    if timeline_duration <= 0 or timeline_duration > MAX_FINAL_RUNTIME_SECONDS + 1e-6:
        raise MusicProductionError(
            f"Picture timeline runtime must be within 0-{MAX_FINAL_RUNTIME_SECONDS:.0f}s"
        )
    picture_duration = media_duration(picture_lock)
    if picture_duration > MAX_FINAL_RUNTIME_SECONDS + 1e-3:
        raise MusicProductionError(
            f"Assembled picture runtime {picture_duration:.3f}s exceeds 240 seconds"
        )
    if abs(picture_duration - timeline_duration) > 0.25:
        raise MusicProductionError(
            "Assembled picture duration does not match picture-audio EDL; rerun assembly "
            f"({picture_duration:.3f}s versus {timeline_duration:.3f}s)"
        )
    scripts_dir = virtual_pending / "seedance-segment-scripts"
    if not scripts_dir.is_dir():
        raise MusicProductionError(f"Missing Segment scripts under {task_dir}")
    no_background_music_evidence = validate_no_seedance_background_music(
        task_dir,
        scripts_dir=scripts_dir,
        segment_ids=[record[0] for record in records],
    )
    native_audio_check = validate_native_audio_track(
        audio_timeline,
        segment_count=len(records),
        picture_duration=picture_duration,
    )
    schedule = build_cue_schedule(
        config,
        score_anchors,
        picture_duration=picture_duration,
    )
    if args.validate_only:
        validation = {
            "status": "MUSIC_PLAN_VALID",
            "contract": config["contract"],
            "music_provider": "seedaudio",
            "seedance_background_music": "forbidden_and_absent",
            "segment_count": len(records),
            "picture_duration_seconds": round(picture_duration, 6),
            "native_audio_check": native_audio_check,
            "no_background_music_evidence": no_background_music_evidence,
            "cue_schedule": [
                {
                    "cue_id": item["cue"]["cue_id"],
                    "segment_ids": item["cue"]["segment_ids"],
                    "timeline_in_seconds": round(
                        float(item["timeline_in_seconds"]), 6
                    ),
                    "timeline_out_seconds": round(
                        float(item["timeline_out_seconds"]), 6
                    ),
                    "rendered_duration_seconds": round(
                        float(item["rendered_duration_seconds"]), 6
                    ),
                    "cadence": item["cue"]["cadence"],
                }
                for item in schedule
            ],
        }
        print(json.dumps(validation, ensure_ascii=False, indent=2), flush=True)
        return 0
    output_dir = finish_pending / "music-production"
    cue_dir = output_dir / "cues"
    cue_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet = create_contact_sheet(
        picture_lock,
        timestamps_seconds=[
            float(anchor["midpoint_seconds"]) for anchor in score_anchors
        ],
        output=output_dir / "picture-lock-contact-sheet.jpg",
    )
    sample_rate = int(config["seedaudio"]["sample_rate"])
    theme_seconds = float(config["seedaudio"]["theme_palette_seconds"])
    title = task_dir.name.replace("-", " ")
    cues = config["cues"]
    theme_raw = output_dir / "theme-palette.raw.wav"
    generate_audio(
        prompt=theme_prompt(
            title,
            theme_seconds,
            config["theme"],
            cues,
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
        overlap_seconds=float(config["mix"]["cue_crossfade_seconds"]),
    )
    if theme_reference.stat().st_size > 10 * 1024 * 1024:
        raise MusicProductionError(
            "Normalized SeedAudio theme reference still exceeds the 10 MiB provider limit"
        )

    crossfade = float(config["mix"]["cue_crossfade_seconds"])
    normalized_cues: list[Path] = []
    cue_records: list[dict[str, Any]] = []
    for cue_index, scheduled in enumerate(schedule):
        cue = scheduled["cue"]
        cue_anchors = scheduled["cue_anchors"]
        cue_timeline_in = float(scheduled["timeline_in_seconds"])
        cue_timeline_out = float(scheduled["timeline_out_seconds"])
        cue_timeline_duration = float(scheduled["timeline_duration_seconds"])
        rendered_duration = float(scheduled["rendered_duration_seconds"])
        summaries = [
            compact_segment_performance(
                scripts_dir / f"segment-{segment_id:03d}.md"
            )
            for segment_id in cue["segment_ids"]
        ]
        prompt = cue_prompt(
            cue=cue,
            rendered_duration=rendered_duration,
            segment_summaries=summaries,
            segment_anchors=cue_anchors,
            cue_timeline_in=cue_timeline_in,
            cue_timeline_out=cue_timeline_out,
            overlap_seconds=crossfade,
            is_final_cue=cue_index == len(cues) - 1,
        )
        raw_path = cue_dir / f"{cue['cue_id']}.raw.wav"
        cue_reference = (
            normalized_cues[0]
            if cue_index == len(cues) - 1 and normalized_cues
            else theme_reference
        )
        generate_audio(
            prompt=prompt,
            output=raw_path,
            request_path=cue_dir / f"{cue['cue_id']}.request.json",
            response_path=cue_dir / f"{cue['cue_id']}.response.json",
            reference_kind="audio",
            reference_path=cue_reference,
            sample_rate=sample_rate,
            timeout=args.timeout,
            regenerate=args.regenerate,
        )
        normalized_path = cue_dir / f"{cue['cue_id']}.wav"
        normalize_cue(
            raw_path,
            normalized_path,
            target_duration=rendered_duration,
            sample_rate=sample_rate,
            overlap_seconds=crossfade,
            fade_edges=False,
            trim_strategy="tail" if cue["cadence"] == "final" else "head",
        )
        normalized_cues.append(normalized_path)
        cue_records.append(
            {
                "cue_id": cue["cue_id"],
                "segment_ids": cue["segment_ids"],
                "timeline_in_seconds": cue_timeline_in,
                "timeline_out_seconds": cue_timeline_out,
                "timeline_duration_seconds": cue_timeline_duration,
                "rendered_duration_seconds": media_duration(normalized_path),
                "raw_duration_seconds": media_duration(raw_path),
                "path": str(normalized_path.resolve()),
                "music_state_in_en": cue["music_state_in_en"],
                "music_state_out_en": cue["music_state_out_en"],
                "cadence": cue["cadence"],
                "final_cadence_required": cue["cadence"] == "final",
            }
        )

    joined_score = output_dir / "seedaudio-score-joined.wav"
    join_cues(normalized_cues, joined_score, crossfade)
    final_score = output_dir / "seedaudio-score.wav"
    fit_score_to_picture(joined_score, final_score, picture_duration)
    score_track = next(
        (
            track
            for track in audio_timeline["tracks"]
            if track.get("track_id") == "seedaudio-score"
        ),
        None,
    )
    if score_track is None:
        score_track = {
            "track_id": "seedaudio-score",
            "source": "seedaudio",
            "role": "non_diegetic_story_score",
            "preserve_across_segment_cuts": True,
            "events": [],
        }
        audio_timeline["tracks"].append(score_track)
    score_track["events"] = [
        {
            "event_id": "seedaudio-score-picture-lock",
            "source": str(final_score.resolve()),
            "source_in_seconds": 0.0,
            "source_out_seconds": round(media_duration(final_score), 6),
            "timeline_in_seconds": 0.0,
            "timeline_out_seconds": round(picture_duration, 6),
            "duration_seconds": round(picture_duration, 6),
            "preserve_across_segment_cuts": True,
        }
    ]
    audio_timeline["music_provider"] = "seedaudio"
    audio_timeline["seedance_background_music"] = False
    audio_timeline["background_music_source"] = "seedaudio"
    audio_timeline["score_policy"] = {
        "source": "seedaudio",
        "role": "non_diegetic_story_score",
        "preserve_across_segment_cuts": True,
        "cue_boundary_policy": "story_arc_equal_power_crossfade",
        "status": "generated",
    }
    audio_timeline["score_cues"] = cue_records
    write_json(finish_pending / "audio-timeline.json", audio_timeline)
    score_preview = output_dir / "final-seedaudio-score-only-preview.mp4"
    render_score_preview(picture_lock, final_score, score_preview)
    mix_test = output_dir / "final-seedaudio-mix-test.mp4"
    render_mix_test(
        picture_lock,
        final_score,
        mix_test,
        mix=config["mix"],
    )
    final_scored_master = output_dir / "scored-picture-lock.mp4"
    render_mix_test(
        picture_lock,
        final_score,
        final_scored_master,
        mix=config["mix"],
    )
    checks = verify_final_master(
        music_provider="seedaudio",
        final_master=final_scored_master,
        native_picture_lock=picture_lock,
        picture_duration=picture_duration,
        segment_count=len(records),
        audio_timeline=audio_timeline,
        config=config,
        cue_records=cue_records,
        final_score=final_score,
    )
    manifest = {
        "contract": "finish-score-manifest/v2",
        "status": "SEEDAUDIO_SCORE_VERIFIED",
        "music_provider": "seedaudio",
        "seedance_background_music": False,
        "background_music_source": "seedaudio",
        "master_role": "final_scored_master",
        "native_picture_lock": str(picture_lock.resolve()),
        "final_master": str(final_scored_master.resolve()),
        "picture_audio_edl": str(
            (finish_pending / "post-production" / "picture-audio-edl.json").resolve()
        ),
        "audio_timeline": str((finish_pending / "audio-timeline.json").resolve()),
        "picture_duration_seconds": picture_duration,
        "score_duration_seconds": media_duration(final_score),
        "contact_sheet": str(contact_sheet.resolve()),
        "theme_palette_raw": str(theme_raw.resolve()),
        "theme_palette_reference": str(theme_reference.resolve()),
        "cues": cue_records,
        "score": str(final_score.resolve()),
        "score_only_preview": str(score_preview.resolve()),
        "mixed_test": str(mix_test.resolve()),
        "no_background_music_evidence": no_background_music_evidence,
        "checks": checks,
        "warnings": [],
    }
    write_json(output_dir / "score-manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--timeout", type=int, default=seedaudio.core.DEFAULT_TIMEOUT)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the No-BGM gate, timeline, and cue plan without SeedAudio calls",
    )
    return parser


def main() -> int:
    try:
        return execute(build_parser().parse_args())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
