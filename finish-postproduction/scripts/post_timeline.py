#!/usr/bin/env python3
"""Compile the authored semantic-boundary picture and native-audio timeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from pkgutil import extend_path
import re
import subprocess
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STORYBOARD_SCRIPT_ROOT = REPOSITORY_ROOT / "virtual-production" / "scripts"
SCREENPLAY_SCRIPT_ROOT = REPOSITORY_ROOT / "screenplay-writer" / "scripts"
for script_root in (STORYBOARD_SCRIPT_ROOT, SCREENPLAY_SCRIPT_ROOT):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))
if "story_video" in sys.modules:
    sys.modules["story_video"].__path__ = extend_path(  # type: ignore[attr-defined]
        sys.modules["story_video"].__path__,  # type: ignore[attr-defined]
        "story_video",
    )

from route_b_handoff import load_route_b_handoff  # noqa: E402
from story_video.seed_master_runtime import (  # noqa: E402
    load_execution_plan,
    manifest_segment_rows,
    parse_segment_script,
    sha256_file,
)
from story_video.boundary_execution import (  # noqa: E402
    build_story_plan_boundaries,
)
from story_video.screenplay_contract import load_screenplay_file  # noqa: E402

SEGMENT_RE = re.compile(r"^segment-([0-9]{3})$")
MAX_FINAL_RUNTIME_SECONDS = 240.0


class TimelineError(RuntimeError):
    """Raised when current task media cannot form a valid final timeline."""


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: float
    has_audio: bool
    width: int
    height: int
    frame_rate: str


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: int
    segment_name: str
    video_path: Path
    script_path: Path
    probe: MediaProbe
    fields: dict[str, Any]


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TimelineError(f"Missing {label}: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TimelineError(f"Invalid UTF-8 JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise TimelineError(f"{label} must contain one JSON object: {path}")
    return payload


def _fraction_as_float(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


def probe_media(path: Path) -> MediaProbe:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,duration,width,height,avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise TimelineError(f"Could not probe media: {path}") from exc
    video_stream = next(
        (item for item in payload.get("streams", []) if item.get("codec_type") == "video"),
        None,
    )
    if not isinstance(video_stream, dict):
        raise TimelineError(f"Segment media has no video stream: {path}")
    try:
        duration = float(video_stream.get("duration") or payload["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TimelineError(f"Could not read media duration: {path}") from exc
    frame_rate = str(
        video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "25/1"
    )
    try:
        if _fraction_as_float(frame_rate) <= 0:
            raise ValueError
    except (ValueError, ZeroDivisionError):
        raise TimelineError(f"Segment media has invalid frame rate: {path}")
    return MediaProbe(
        duration_seconds=duration,
        has_audio=any(
            item.get("codec_type") == "audio" for item in payload.get("streams", [])
        ),
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        frame_rate=frame_rate,
    )


def _screenplay_story_plans(task_dir: Path) -> list[dict[str, Any]]:
    screenplay = load_screenplay_file(task_dir / "screenplay-writer" / "screenplay.md")
    story_plans = [segment["story_plan"] for segment in screenplay["segments"]]
    if not story_plans:
        raise TimelineError("screenplay.md contains no Segments")
    expected = [f"segment-{index:03d}" for index in range(1, len(story_plans) + 1)]
    actual = [item["segment_id"] for item in story_plans]
    if actual != expected:
        raise TimelineError("screenplay.md Segment order is invalid")
    return story_plans


def _validate_task_audio(task_dir: Path) -> dict[str, Any]:
    task = _load_json(task_dir / "task.json", label="task")
    if task.get("voice_audio_source") != "speaker_reference_audio":
        raise TimelineError(
            "task.json voice_audio_source must be speaker_reference_audio"
        )
    if task.get("dialogue_source") != "seedance":
        raise TimelineError("task.json dialogue_source must be seedance")
    return task


def discover_segments(task_dir: Path) -> list[SegmentRecord]:
    task_dir = task_dir.expanduser().resolve()
    _validate_task_audio(task_dir)
    story_plans = _screenplay_story_plans(task_dir)
    expected = [str(item["segment_id"]) for item in manifest_segment_rows(task_dir)]
    if [item["segment_id"] for item in story_plans] != expected:
        raise TimelineError(
            "screenplay.md Segment order differs from the native Storyboard compile manifest"
        )
    generation_state = _load_json(
        task_dir / "virtual-production" / "generation-state.json",
        label="generation state",
    )
    state_segments = generation_state.get("segments")
    if (
        generation_state.get("contract") != "virtual-production-generation-state"
        or generation_state.get("state") != "GENERATED"
        or not isinstance(state_segments, list)
        or [item.get("segment_id") for item in state_segments if isinstance(item, dict)]
        != expected
    ):
        raise TimelineError("Virtual production has not completed every current Segment")
    virtual_pending = task_dir / ".pending" / "virtual-production"
    media_root = virtual_pending / "generation-segments"
    scripts_root = virtual_pending / "seedance-segment-scripts"
    if not media_root.is_dir() or not scripts_root.is_dir():
        raise TimelineError("Missing current .pending Segment media or Segment Scripts")
    actual_media = sorted(
        item.name for item in media_root.iterdir() if item.is_dir() and SEGMENT_RE.fullmatch(item.name)
    )
    actual_scripts = sorted(path.stem for path in scripts_root.glob("segment-*.md"))
    if actual_media != expected or actual_scripts != expected:
        raise TimelineError("Segment media/Script coverage differs from screenplay.md")
    records: list[SegmentRecord] = []
    for segment_name in expected:
        video = media_root / segment_name / "video.mp4"
        script = scripts_root / f"{segment_name}.md"
        if not video.is_file() or not script.is_file():
            raise TimelineError(f"Incomplete generated Segment: {segment_name}")
        production_record = _load_json(
            media_root / segment_name / "production-record.json",
            label=f"{segment_name} production record",
        )
        if (
            production_record.get("contract")
            != "generated-segment-production-record"
            or production_record.get("segment_id") != segment_name
            or production_record.get("status") != "GENERATED"
        ):
            raise TimelineError(f"{segment_name} is not a completed generated Segment")
        generated_script = media_root / segment_name / "segment-script.md"
        if (
            not generated_script.is_file()
            or generated_script.read_text(encoding="utf-8")
            != script.read_text(encoding="utf-8")
        ):
            raise TimelineError(
                f"{segment_name} video was generated from a stale Segment Script"
            )
        submission = _load_json(
            media_root / segment_name / "seedance-submission.json",
            label=f"{segment_name} Seedance submission",
        )
        attempt_number = submission.get("attempt_number")
        if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number < 1:
            raise TimelineError(f"{segment_name} has invalid provider attempt identity")
        provider_attempt_id = f"{segment_name}__attempt-{attempt_number:04d}"
        recorded_attempt = production_record.get("provider_attempt_id")
        if recorded_attempt not in {None, provider_attempt_id}:
            raise TimelineError(f"{segment_name} production attempt identity is stale")
        parsed_script = parse_segment_script(script)
        execution_plan_path = (
            virtual_pending
            / "seedance-execution-plans"
            / f"{segment_name}.json"
        )
        execution_plan = load_execution_plan(task_dir, segment_name)
        compatibility = execution_plan.get("asset_compatibility")
        if (
            production_record.get("seed_master_script_sha256")
            != parsed_script["script_sha256"]
            or production_record.get("seedance_execution_plan_sha256")
            != sha256_file(execution_plan_path)
            or not isinstance(compatibility, dict)
            or compatibility.get("overall_verdict") != "PASS"
            or production_record.get("asset_compatibility_review_sha256")
            != compatibility.get("review_sha256")
            or production_record.get("operation")
            != parsed_script["metadata"]["operation"]
        ):
            raise TimelineError(
                f"{segment_name} production record differs from its Seed Master Script"
            )
        fields = parsed_script["metadata"]
        probe = probe_media(video)
        if not probe.has_audio:
            raise TimelineError(
                f"{segment_name} lacks required Seedance native dialogue/foley/ambience audio"
            )
        if probe.duration_seconds <= 0 or probe.duration_seconds > 15.25:
            raise TimelineError(f"{segment_name} has invalid generated duration")
        records.append(
            SegmentRecord(
                segment_id=int(segment_name.removeprefix("segment-")),
                segment_name=segment_name,
                video_path=video.resolve(),
                script_path=script.resolve(),
                probe=probe,
                fields=fields,
            )
        )
    return records


def compile_timelines(
    task_dir: Path,
    records: list[SegmentRecord] | None = None,
    *,
    runtime_limit_seconds: float = MAX_FINAL_RUNTIME_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    task_dir = task_dir.expanduser().resolve()
    records = records if records is not None else discover_segments(task_dir)
    if not records:
        raise TimelineError("No generated Segment media found")
    picture_events: list[dict[str, Any]] = []
    native_events: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    plan_boundaries = build_story_plan_boundaries(
        _screenplay_story_plans(task_dir)
    )
    storyboards = load_route_b_handoff(task_dir)
    cursor = 0.0
    for index, record in enumerate(records):
        duration = record.probe.duration_seconds
        incoming_execution = (
            plan_boundaries[index - 1]["execution"] if index else None
        )
        incoming_overlap = (
            float(incoming_execution["transition_duration_seconds"])
            if incoming_execution is not None
            and incoming_execution["picture_edit_mode"] in {"dissolve", "fade"}
            else 0.0
        )
        if incoming_overlap < 0 or incoming_overlap >= duration:
            raise TimelineError(
                f"{record.segment_name} has an invalid incoming transition duration"
            )
        start = cursor - incoming_overlap
        end = start + duration
        common = {
            "segment_id": record.segment_name,
            "source": str(record.video_path),
            "source_in_seconds": 0.0,
            "source_out_seconds": round(duration, 6),
            "timeline_in_seconds": round(start, 6),
            "timeline_out_seconds": round(end, 6),
            "duration_seconds": round(duration, 6),
        }
        picture_events.append(
            {
                **common,
                "edit": (
                    incoming_execution["picture_edit_mode"]
                    if incoming_execution is not None
                    else "opening"
                ),
                "script": str(record.script_path),
            }
        )
        native_events.append(
            {
                **common,
                "event_id": f"native-{record.segment_name}",
                "purpose": "seedance_native_dialogue_foley_and_ambience_without_background_music",
                "has_source_audio": True,
                "voice_audio_source": "speaker_reference_audio",
                "dialogue_source": "seedance",
                "native_ambience_source": "seedance",
                "background_music_source": "none",
                "seedance_background_music": False,
                "preserve_lip_sync": True,
                "cross_boundary_copy_allowed": False,
                "transition_overlap_allowed": incoming_overlap > 0,
                "gain_db": 0.0,
            }
        )
        if index + 1 < len(records):
            boundary_plan = plan_boundaries[index]
            execution = boundary_plan["execution"]
            overlap = (
                float(execution["transition_duration_seconds"])
                if execution["picture_edit_mode"] in {"dissolve", "fade"}
                else 0.0
            )
            if overlap:
                try:
                    storyboard = storyboards[record.segment_name]
                except KeyError as exc:
                    raise TimelineError(
                        f"{record.segment_name} is absent from the Route B handoff"
                    ) from exc
                safe = storyboard.get("segment_safe_cut_design")
                available = (
                    float(safe.get("editable_hold_seconds", -1))
                    if isinstance(safe, dict)
                    else -1
                )
                if available + 1e-6 < overlap:
                    raise TimelineError(
                        f"{record.segment_name} provides {available:.3f}s transition "
                        f"handle but {execution['authored_transition_type']} requires "
                        f"{overlap:.3f}s"
                    )
            boundaries.append(
                {
                    "from": record.segment_name,
                    "to": records[index + 1].segment_name,
                    "authored_transition_type": execution[
                        "authored_transition_type"
                    ],
                    "transition_class": execution["transition_class"],
                    "timeline_seconds": round(end - overlap, 6),
                    "transition_start_seconds": round(end - overlap, 6),
                    "transition_end_seconds": round(end, 6),
                    "picture_edit": execution["picture_edit_mode"],
                    "audio_edit": execution["audio_edit_mode"],
                    "audio_edge_fade_seconds": execution[
                        "audio_edge_fade_seconds"
                    ],
                    "overlap_seconds": round(overlap, 6),
                }
            )
        cursor = end
    if cursor > runtime_limit_seconds + 1e-6:
        raise TimelineError(
            f"Final runtime {cursor:.3f}s exceeds {runtime_limit_seconds:.3f}s"
        )
    picture_edl = {
        "contract": "finish-picture-audio-edl",
        "edit_policy": "authored_semantic_boundaries",
        "segment_count": len(records),
        "duration_seconds": round(cursor, 6),
        "picture_events": picture_events,
        "boundaries": boundaries,
    }
    audio_timeline = {
        "contract": "finish-native-audio-timeline",
        "duration_seconds": round(cursor, 6),
        "native_audio_policy": {
            "generate_audio": True,
            "voice_audio_source": "speaker_reference_audio",
            "dialogue_source": "seedance",
            "native_ambience_source": "seedance",
            "seedance_background_music": False,
            "background_music_source": "none",
            "preserve_clip_sync": True,
            "cross_segment_native_audio": any(
                boundary["overlap_seconds"] > 0 for boundary in boundaries
            ),
        },
        "tracks": [
            {
                "track_id": "native-sync",
                "source": "seedance",
                "role": "synchronized_dialogue_foley_and_ambience",
                "events": native_events,
            }
        ],
        "music_provider": "none",
        "seedance_background_music": False,
        "background_music_source": "none",
    }
    return picture_edl, audio_timeline


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_timeline_artifacts(
    task_dir: Path,
    picture_edl: dict[str, Any],
    audio_timeline: dict[str, Any],
) -> tuple[Path, Path]:
    pending = task_dir.expanduser().resolve() / ".pending" / "finish-postproduction"
    edl_path = pending / "post-production" / "picture-audio-edl.json"
    audio_path = pending / "audio-timeline.json"
    _write_json(edl_path, picture_edl)
    _write_json(audio_path, audio_timeline)
    return edl_path, audio_path


def load_timeline_artifacts(task_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = task_dir.expanduser().resolve() / ".pending" / "finish-postproduction"
    return (
        _load_json(pending / "post-production" / "picture-audio-edl.json", label="picture EDL"),
        _load_json(pending / "audio-timeline.json", label="audio timeline"),
    )
