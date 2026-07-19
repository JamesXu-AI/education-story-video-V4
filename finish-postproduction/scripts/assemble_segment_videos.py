#!/usr/bin/env python3
"""Assemble current Seedance Segment outputs into a task-local picture lock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from post_timeline import (  # noqa: E402
    MAX_FINAL_RUNTIME_SECONDS,
    SegmentRecord,
    TimelineError,
    compile_timelines,
    discover_segments,
    probe_media,
    write_timeline_artifacts,
)
from boundary_qc import (  # noqa: E402
    BoundaryQCError,
    append_segment_repair_filter,
    audit_picture_lock,
    prepare_boundary_qc,
)


def _load_task(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "task.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TimelineError(f"Invalid task.json: {path}") from exc
    if not isinstance(payload, dict):
        raise TimelineError("task.json must contain one JSON object")
    return payload


def _delivery_dimensions(task: dict[str, Any], first: SegmentRecord) -> tuple[int, int]:
    task_input = task.get("input")
    if not isinstance(task_input, dict):
        raise TimelineError("task.json input is missing")
    resolution = str(task_input.get("resolution") or "").lower().removesuffix("p")
    short_side_by_resolution = {"480": 480, "720": 720, "1080": 1080, "4k": 2160}
    if resolution not in short_side_by_resolution:
        raise TimelineError("task.json input.resolution is invalid")
    aspect = str(task_input.get("aspect_ratio") or "")
    if aspect == "adaptive":
        if first.probe.width <= 0 or first.probe.height <= 0:
            raise TimelineError("Adaptive delivery requires valid generated dimensions")
        return first.probe.width, first.probe.height
    try:
        width_ratio, height_ratio = (int(value) for value in aspect.split(":", 1))
    except (ValueError, TypeError) as exc:
        raise TimelineError("task.json input.aspect_ratio is invalid") from exc
    if width_ratio <= 0 or height_ratio <= 0:
        raise TimelineError("task.json input.aspect_ratio must be positive")
    short_side = short_side_by_resolution[resolution]
    if width_ratio >= height_ratio:
        height = short_side
        width = round(short_side * width_ratio / height_ratio)
    else:
        width = short_side
        height = round(short_side * height_ratio / width_ratio)
    width += width % 2
    height += height % 2
    return width, height


def _render_filter(
    records: list[SegmentRecord],
    width: int,
    height: int,
    boundaries: list[dict[str, Any]],
    repair_plans: dict[str, dict[str, Any]] | None = None,
) -> str:
    if len(boundaries) != max(0, len(records) - 1):
        raise TimelineError("Rendered boundary coverage differs from Segment coverage")
    frame_rate = records[0].probe.frame_rate
    filters: list[str] = []
    repair_plans = repair_plans or {}
    for index, record in enumerate(records):
        duration = record.probe.duration_seconds
        if not record.probe.has_audio:
            raise TimelineError(f"{record.segment_name} has no Seedance native audio")
        repair_plan = repair_plans.get(record.segment_name)
        base_video_label = f"vbase{index}" if repair_plan is not None else f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=duration={duration:.6f},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={frame_rate},format=yuv420p,settb=AVTB[{base_video_label}]"
        )
        if repair_plan is not None:
            append_segment_repair_filter(
                filters,
                input_label=base_video_label,
                output_label=f"v{index}",
                label_prefix=f"repair{index}",
                plan=repair_plan,
            )
        audio_filters = [
            "aresample=48000",
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
            f"apad=pad_dur={duration:.6f}",
            f"atrim=duration={duration:.6f}",
            "asetpts=PTS-STARTPTS",
        ]
        incoming = boundaries[index - 1] if index else None
        outgoing = boundaries[index] if index < len(boundaries) else None
        if incoming and incoming["audio_edit"] == "native_continuity_declick":
            fade = float(incoming["audio_edge_fade_seconds"])
            audio_filters.append(f"afade=t=in:st=0:d={fade:.6f}")
        if outgoing and outgoing["audio_edit"] == "native_continuity_declick":
            fade = float(outgoing["audio_edge_fade_seconds"])
            audio_filters.append(
                f"afade=t=out:st={max(0.0, duration - fade):.6f}:d={fade:.6f}"
            )
        filters.append(f"[{index}:a:0]{','.join(audio_filters)}[a{index}]")

    current_video = "v0"
    current_audio = "a0"
    current_duration = records[0].probe.duration_seconds
    for index, boundary in enumerate(boundaries, start=1):
        next_video = f"v{index}"
        next_audio = f"a{index}"
        output_video = f"vjoin{index}"
        output_audio = f"ajoin{index}"
        picture_edit = boundary["picture_edit"]
        overlap = float(boundary["overlap_seconds"])
        if picture_edit in {"dissolve", "fade"}:
            if overlap <= 0 or overlap >= min(
                current_duration, records[index].probe.duration_seconds
            ):
                raise TimelineError(
                    f"{boundary['from']}->{boundary['to']} has invalid transition overlap"
                )
            transition = "fade" if picture_edit == "dissolve" else "fadeblack"
            offset = current_duration - overlap
            filters.append(
                f"[{current_video}][{next_video}]xfade=transition={transition}:"
                f"duration={overlap:.6f}:offset={offset:.6f}[{output_video}]"
            )
            filters.append(
                f"[{current_audio}][{next_audio}]acrossfade=d={overlap:.6f}:"
                f"c1=qsin:c2=qsin[{output_audio}]"
            )
            current_duration += records[index].probe.duration_seconds - overlap
        elif picture_edit in {"hard_cut", "baked_effect"}:
            if overlap != 0:
                raise TimelineError(
                    f"{boundary['from']}->{boundary['to']} hard boundary cannot overlap"
                )
            filters.append(
                f"[{current_video}][{next_video}]concat=n=2:v=1:a=0[{output_video}]"
            )
            filters.append(
                f"[{current_audio}][{next_audio}]concat=n=2:v=0:a=1[{output_audio}]"
            )
            current_duration += records[index].probe.duration_seconds
        else:
            raise TimelineError(f"Unsupported picture edit: {picture_edit}")
        current_video = output_video
        current_audio = output_audio
    filters.append(f"[{current_video}]null[vout]")
    filters.append(f"[{current_audio}]anull[aout]")
    return ";".join(filters)


def render_picture_lock(
    records: list[SegmentRecord],
    output: Path,
    task: dict[str, Any],
    picture_edl: dict[str, Any],
    repair_plans: dict[str, dict[str, Any]] | None = None,
) -> None:
    width, height = _delivery_dimensions(task, records[0])
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for record in records:
        command.extend(["-i", str(record.video_path)])
    command.extend(
        [
            "-filter_complex",
            _render_filter(
                records,
                width,
                height,
                picture_edl["boundaries"],
                repair_plans,
            ),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    subprocess.run(command, check=True)


def assemble(task_dir: Path, *, edl_only: bool = False) -> Path:
    task_dir = task_dir.expanduser().resolve()
    records = discover_segments(task_dir)
    picture_edl, audio_timeline = compile_timelines(task_dir, records)
    output = (
        task_dir
        / ".pending"
        / "finish-postproduction"
        / "post-production"
        / "native-picture-lock.mp4"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not edl_only:
        try:
            qc_manifest_path, repair_plans, qc_manifest = prepare_boundary_qc(
                task_dir,
                records,
                picture_edl,
            )
        except BoundaryQCError as exc:
            raise TimelineError(f"Boundary QC preparation failed: {exc}") from exc
        if qc_manifest.get("pre_assembly_status") == "review_required":
            blockers = ", ".join(qc_manifest.get("blocking_boundaries", []))
            raise TimelineError(
                "Boundary QC requires visual review before picture lock: " + blockers
            )
        render_picture_lock(
            records,
            output,
            _load_task(task_dir),
            picture_edl,
            repair_plans,
        )
        rendered = probe_media(output)
        expected = float(picture_edl["duration_seconds"])
        if not rendered.has_audio:
            raise TimelineError("Native picture lock has no audio stream")
        if rendered.duration_seconds > MAX_FINAL_RUNTIME_SECONDS + 1e-3:
            raise TimelineError("Native picture lock exceeds 240 seconds")
        if abs(rendered.duration_seconds - expected) > 0.25:
            raise TimelineError("Native picture-lock duration differs from its EDL")
        picture_edl.update(
            {
                "rendered_output": str(output.resolve()),
                "rendered_output_role": "native_picture_lock",
                "final_delivery_status": "ready_for_clean_master",
                "rendered_duration_seconds": round(rendered.duration_seconds, 6),
                "resolution": {"width": rendered.width, "height": rendered.height},
                "audio_stream_present": True,
                "boundary_qc": {
                    "manifest": str(qc_manifest_path.resolve()),
                    "planned_repair_count": len(repair_plans),
                    "source_segments_mutated": False,
                },
            }
        )
        try:
            final_qc = audit_picture_lock(
                output,
                picture_edl,
                qc_manifest_path,
            )
        except BoundaryQCError as exc:
            raise TimelineError(f"Final-timeline boundary audit failed: {exc}") from exc
        picture_edl["boundary_qc"].update(
            {
                "final_timeline_status": final_qc.get("final_timeline_status"),
                "final_timeline_blocking_boundaries": final_qc.get(
                    "final_timeline_blocking_boundaries", []
                ),
            }
        )
        if final_qc.get("final_timeline_status") == "review_required":
            blockers = ", ".join(
                final_qc.get("final_timeline_blocking_boundaries", [])
            )
            raise TimelineError(
                "Rendered picture lock has a residual boundary anomaly requiring "
                f"visual review: {blockers}"
            )
    edl_path, audio_path = write_timeline_artifacts(task_dir, picture_edl, audio_timeline)
    print(f"picture/audio EDL: {edl_path}", flush=True)
    print(f"audio timeline: {audio_path}", flush=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--edl-only", action="store_true")
    args = parser.parse_args()
    try:
        print(assemble(args.task_dir, edl_only=args.edl_only))
    except (TimelineError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
