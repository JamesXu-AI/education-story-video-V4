#!/usr/bin/env python3
"""Prepare strict seam evidence and safe, reversible boundary color corrections."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_ROOT.parent / "assets" / "boundary-qc.json"


class BoundaryQCError(RuntimeError):
    """Raised when deterministic boundary evidence or repair cannot be built."""


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundaryQCError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise BoundaryQCError(f"{label} must contain one JSON object: {path}")
    return payload


def _positive_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise BoundaryQCError(f"{label} must be a positive number")
    return float(value)


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load and validate the narrow automatic-repair policy."""
    config = _load_json(path.expanduser().resolve(), label="boundary QC config")
    if config.get("contract") != "finish-boundary-qc-config/v1":
        raise BoundaryQCError("Unsupported boundary QC config contract")
    for key in ("enabled", "auto_apply_safe_color_match"):
        if not isinstance(config.get(key), bool):
            raise BoundaryQCError(f"boundary QC config {key} must be boolean")
    strict = config.get("strict_sample")
    analysis = config.get("analysis")
    detection = config.get("detection")
    limits = config.get("safe_limits")
    repair = config.get("repair")
    for label, value in (
        ("strict_sample", strict),
        ("analysis", analysis),
        ("detection", detection),
        ("safe_limits", limits),
        ("repair", repair),
    ):
        if not isinstance(value, dict):
            raise BoundaryQCError(f"boundary QC config {label} must be an object")
    frame_rate = int(_positive_number(strict.get("frame_rate"), label="frame_rate"))
    tail = _positive_number(strict.get("tail_seconds"), label="tail_seconds")
    head = _positive_number(strict.get("head_seconds"), label="head_seconds")
    frame_count = int(_positive_number(strict.get("frame_count"), label="frame_count"))
    if abs(tail - 1.0) > 1e-9 or abs(head - 1.0) > 1e-9:
        raise BoundaryQCError("Strict cut seam must be final 1.0s plus opening 1.0s")
    if frame_rate != 24 or frame_count != 48:
        raise BoundaryQCError("Strict seam evidence must be exactly 48 frames at 24 fps")
    _positive_number(strict.get("evidence_frame_width"), label="evidence_frame_width")
    _positive_number(analysis.get("width"), label="analysis.width")
    _positive_number(analysis.get("anchor_frame_count"), label="anchor_frame_count")
    similarity = _positive_number(
        analysis.get("minimum_match_similarity"),
        label="minimum_match_similarity",
    )
    if similarity > 1:
        raise BoundaryQCError("minimum_match_similarity cannot exceed 1")
    for key, value in detection.items():
        _positive_number(value, label=f"detection.{key}")
    for key, value in limits.items():
        _positive_number(value, label=f"safe_limits.{key}")
    if float(limits["minimum_saturation_factor"]) >= float(
        limits["maximum_saturation_factor"]
    ):
        raise BoundaryQCError("Saturation factor limits are reversed")
    _positive_number(repair.get("fade_seconds"), label="repair.fade_seconds")
    strengths = repair.get("candidate_strengths")
    if not isinstance(strengths, dict) or set(strengths) != {
        "soft",
        "matched",
        "strong",
    }:
        raise BoundaryQCError("candidate_strengths must define soft/matched/strong")
    for key, value in strengths.items():
        _positive_number(value, label=f"candidate_strengths.{key}")
    return config


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _run(command: list[str], *, label: str) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise BoundaryQCError(f"{label} failed") from exc


def _analysis_geometry(record: object, width: int) -> tuple[int, int]:
    probe = getattr(record, "probe")
    source_width = int(getattr(probe, "width"))
    source_height = int(getattr(probe, "height"))
    if source_width <= 0 or source_height <= 0:
        raise BoundaryQCError("Boundary source has invalid dimensions")
    height = max(2, round(source_height * width / source_width))
    height += height % 2
    return width, height


def _extract_yuv_frames(
    path: Path,
    *,
    start_seconds: float,
    frame_count: int,
    frame_rate: int,
    width: int,
    height: int,
) -> list[tuple[bytes, bytes, bytes]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, start_seconds):.6f}",
        "-i",
        str(path),
        "-vf",
        f"fps={frame_rate},scale={width}:{height}:flags=area,format=yuv444p",
        "-frames:v",
        str(frame_count),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "yuv444p",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise BoundaryQCError(f"Could not analyze boundary frames: {path}") from exc
    plane_size = width * height
    frame_size = plane_size * 3
    decoded = len(result.stdout) // frame_size
    if decoded != frame_count or len(result.stdout) != frame_count * frame_size:
        raise BoundaryQCError(
            f"Expected {frame_count} analysis frames from {path}, decoded {decoded}"
        )
    frames: list[tuple[bytes, bytes, bytes]] = []
    for index in range(frame_count):
        offset = index * frame_size
        frame = result.stdout[offset : offset + frame_size]
        frames.append(
            (
                frame[:plane_size],
                frame[plane_size : plane_size * 2],
                frame[plane_size * 2 :],
            )
        )
    return frames


def _extract_tail_yuv_frames(
    path: Path,
    *,
    frame_count: int,
    frame_rate: int,
    width: int,
    height: int,
) -> list[tuple[bytes, bytes, bytes]]:
    """Decode the exact final frames without relying on container-duration rounding."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vf",
        f"fps={frame_rate},scale={width}:{height}:flags=area,format=yuv444p,"
        f"reverse,trim=end_frame={frame_count},reverse",
        "-frames:v",
        str(frame_count),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "yuv444p",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise BoundaryQCError(f"Could not analyze final boundary frames: {path}") from exc
    plane_size = width * height
    frame_size = plane_size * 3
    decoded = len(result.stdout) // frame_size
    if decoded != frame_count or len(result.stdout) != frame_count * frame_size:
        raise BoundaryQCError(
            f"Expected {frame_count} final analysis frames from {path}, decoded {decoded}"
        )
    return [
        (
            result.stdout[offset : offset + plane_size],
            result.stdout[offset + plane_size : offset + plane_size * 2],
            result.stdout[offset + plane_size * 2 : offset + frame_size],
        )
        for offset in range(0, len(result.stdout), frame_size)
    ]


def _plane_stats(frames: Iterable[tuple[bytes, bytes, bytes]]) -> dict[str, Any]:
    materialized = list(frames)
    if not materialized:
        raise BoundaryQCError("Cannot measure an empty frame set")
    y_plane = b"".join(frame[0] for frame in materialized)
    u_plane = b"".join(frame[1] for frame in materialized)
    v_plane = b"".join(frame[2] for frame in materialized)
    ordered_y = sorted(y_plane)
    sample_count = len(y_plane)
    u_mean = sum(u_plane) / sample_count
    v_mean = sum(v_plane) / sample_count
    saturation = sum(
        math.hypot(u_value - 128, v_value - 128)
        for u_value, v_value in zip(u_plane, v_plane)
    ) / sample_count
    frame_means = [sum(frame[0]) / len(frame[0]) for frame in materialized]
    return {
        "luma_q10": ordered_y[int(sample_count * 0.10)],
        "luma_mean": round(sum(y_plane) / sample_count, 6),
        "luma_q90": ordered_y[int(sample_count * 0.90)],
        "u_mean": round(u_mean, 6),
        "v_mean": round(v_mean, 6),
        "saturation_mean": round(saturation, 6),
        "hue_degrees": round(
            math.degrees(math.atan2(v_mean - 128, u_mean - 128)),
            6,
        ),
        "per_frame_luma_mean": [round(value, 6) for value in frame_means],
    }


def _normalized_luma_correlation(left: bytes, right: bytes) -> float:
    if len(left) != len(right) or not left:
        raise BoundaryQCError("Cannot compare differently sized boundary frames")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = 0.0
    left_energy = 0.0
    right_energy = 0.0
    for left_value, right_value in zip(left, right):
        left_centered = left_value - left_mean
        right_centered = right_value - right_mean
        numerator += left_centered * right_centered
        left_energy += left_centered * left_centered
        right_energy += right_centered * right_centered
    denominator = math.sqrt(left_energy * right_energy)
    if denominator <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, numerator / denominator))


def measure_boundary(
    outgoing: object,
    incoming: object,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Measure a short robust endpoint window without making a picture verdict."""
    analysis = config["analysis"]
    strict = config["strict_sample"]
    width, height = _analysis_geometry(outgoing, int(analysis["width"]))
    frame_count = int(analysis["anchor_frame_count"])
    frame_rate = int(strict["frame_rate"])
    outgoing_probe = getattr(outgoing, "probe")
    outgoing_path = Path(getattr(outgoing, "video_path"))
    incoming_path = Path(getattr(incoming, "video_path"))
    outgoing_frames = _extract_tail_yuv_frames(
        outgoing_path,
        frame_count=frame_count,
        frame_rate=frame_rate,
        width=width,
        height=height,
    )
    incoming_frames = _extract_yuv_frames(
        incoming_path,
        start_seconds=0.0,
        frame_count=frame_count,
        frame_rate=frame_rate,
        width=width,
        height=height,
    )
    outgoing_stats = _plane_stats(outgoing_frames)
    incoming_stats = _plane_stats(incoming_frames)
    saturation_factor = outgoing_stats["saturation_mean"] / max(
        1e-6, incoming_stats["saturation_mean"]
    )
    delta_u = outgoing_stats["u_mean"] - incoming_stats["u_mean"]
    delta_v = outgoing_stats["v_mean"] - incoming_stats["v_mean"]
    return {
        "analysis_role": "technical_detection_evidence_only",
        "analysis_frame_width": width,
        "analysis_frame_height": height,
        "analysis_frame_count_per_side": frame_count,
        "outgoing": outgoing_stats,
        "incoming": incoming_stats,
        "delta_target_minus_incoming": {
            "luma_q10": round(
                outgoing_stats["luma_q10"] - incoming_stats["luma_q10"], 6
            ),
            "luma_mean": round(
                outgoing_stats["luma_mean"] - incoming_stats["luma_mean"], 6
            ),
            "luma_q90": round(
                outgoing_stats["luma_q90"] - incoming_stats["luma_q90"], 6
            ),
            "u_mean": round(delta_u, 6),
            "v_mean": round(delta_v, 6),
            "chroma_center_distance": round(math.hypot(delta_u, delta_v), 6),
            "saturation_factor": round(saturation_factor, 6),
            "saturation_ratio_delta": round(saturation_factor - 1.0, 6),
        },
        "luma_shape_correlation": round(
            _normalized_luma_correlation(
                outgoing_frames[-1][0], incoming_frames[0][0]
            ),
            6,
        ),
    }


def _has_detectable_mismatch(
    metrics: dict[str, Any], config: dict[str, Any]
) -> bool:
    delta = metrics["delta_target_minus_incoming"]
    threshold = config["detection"]
    return any(
        (
            abs(float(delta["luma_mean"])) >= float(threshold["mean_luma_delta"]),
            abs(float(delta["luma_q10"])) >= float(threshold["shadow_luma_delta"]),
            abs(float(delta["luma_q90"]))
            >= float(threshold["highlight_luma_delta"]),
            abs(float(delta["saturation_ratio_delta"]))
            >= float(threshold["saturation_ratio_delta"]),
            float(delta["chroma_center_distance"])
            >= float(threshold["chroma_center_distance"]),
        )
    )


def build_repair_plan(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    incoming = metrics["incoming"]
    delta = metrics["delta_target_minus_incoming"]
    saturation_factor = float(delta["saturation_factor"])
    u_shift = float(metrics["outgoing"]["u_mean"]) - (
        128.0 + (float(incoming["u_mean"]) - 128.0) * saturation_factor
    )
    v_shift = float(metrics["outgoing"]["v_mean"]) - (
        128.0 + (float(incoming["v_mean"]) - 128.0) * saturation_factor
    )
    return {
        "contract": "finish-boundary-color-repair/v1",
        "repair_scope": "incoming_luma_chroma_only",
        "source_mutation": False,
        "fade_seconds": float(config["repair"]["fade_seconds"]),
        "incoming_luma_knots": {
            "q10": float(incoming["luma_q10"]),
            "mean": float(incoming["luma_mean"]),
            "q90": float(incoming["luma_q90"]),
        },
        "luma_delta": {
            "q10": float(delta["luma_q10"]),
            "mean": float(delta["luma_mean"]),
            "q90": float(delta["luma_q90"]),
        },
        "saturation_factor": round(saturation_factor, 6),
        "u_shift": round(u_shift, 6),
        "v_shift": round(v_shift, 6),
    }


def _repair_is_safe(plan: dict[str, Any], config: dict[str, Any]) -> bool:
    limits = config["safe_limits"]
    luma = plan["luma_delta"]
    return all(
        (
            abs(float(luma["mean"])) <= float(limits["mean_luma_delta"]),
            abs(float(luma["q10"])) <= float(limits["quantile_luma_delta"]),
            abs(float(luma["q90"])) <= float(limits["quantile_luma_delta"]),
            float(limits["minimum_saturation_factor"])
            <= float(plan["saturation_factor"])
            <= float(limits["maximum_saturation_factor"]),
            abs(float(plan["u_shift"])) <= float(limits["maximum_chroma_shift"]),
            abs(float(plan["v_shift"])) <= float(limits["maximum_chroma_shift"]),
        )
    )


def triage_boundary(
    boundary: dict[str, Any],
    metrics: dict[str, Any],
    config: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    """Return technical routing only, never a semantic approval decision."""
    if boundary.get("transition_class") in {"designed_transition", "scene_change"}:
        return (
            "authored_transition_evidence_only",
            "Authored transition or scene change is not eligible for automatic color matching.",
            None,
        )
    if boundary.get("picture_edit") not in {"hard_cut"}:
        return (
            "non_cut_evidence_only",
            "Only a hard cut can receive an automatic boundary color correction.",
            None,
        )
    similarity = float(metrics["luma_shape_correlation"])
    minimum = float(config["analysis"]["minimum_match_similarity"])
    if similarity < minimum:
        return (
            "authored_cut_no_auto_match",
            "The two sides are not a high-confidence visual match; color difference may be authored.",
            None,
        )
    if not _has_detectable_mismatch(metrics, config):
        return (
            "no_technical_correction_needed",
            "High-confidence visual match is already inside the technical detection thresholds.",
            None,
        )
    plan = build_repair_plan(metrics, config)
    if not _repair_is_safe(plan, config):
        return (
            "review_required",
            "The matched boundary exceeds the narrow automatic color-repair limits.",
            plan,
        )
    if not config["auto_apply_safe_color_match"]:
        return (
            "repair_candidate_review_required",
            "A safe correction candidate exists, but automatic application is disabled.",
            plan,
        )
    return (
        "safe_color_match_planned",
        "A high-confidence matched cut has a small correctable luma/chroma discrepancy.",
        plan,
    )


def _piecewise_luma_expression(plan: dict[str, Any], strength: float) -> str:
    knots = plan["incoming_luma_knots"]
    x1 = max(1.0, min(252.0, float(knots["q10"])))
    x2 = max(x1 + 1.0, min(253.0, float(knots["mean"])))
    x3 = max(x2 + 1.0, min(254.0, float(knots["q90"])))
    delta = plan["luma_delta"]
    d1 = float(delta["q10"]) * strength
    d2 = float(delta["mean"]) * strength
    d3 = float(delta["q90"]) * strength
    expression = (
        f"if(lt(val,{x1:.6f}),val+({d1:.6f})*val/{x1:.6f},"
        f"if(lt(val,{x2:.6f}),val+({d1:.6f})+"
        f"(({d2:.6f})-({d1:.6f}))*(val-{x1:.6f})/{x2 - x1:.6f},"
        f"if(lt(val,{x3:.6f}),val+({d2:.6f})+"
        f"(({d3:.6f})-({d2:.6f}))*(val-{x2:.6f})/{x3 - x2:.6f},"
        f"val+({d3:.6f})*(255-val)/{255.0 - x3:.6f})))"
    )
    return f"clip({expression},0,255)"


def repair_lut_filter(plan: dict[str, Any], *, strength: float = 1.0) -> str:
    saturation = 1.0 + (float(plan["saturation_factor"]) - 1.0) * strength
    u_shift = float(plan["u_shift"]) * strength
    v_shift = float(plan["v_shift"]) * strength
    y_expression = _piecewise_luma_expression(plan, strength)
    u_expression = f"clip(128+(val-128)*{saturation:.6f}+({u_shift:.6f}),0,255)"
    v_expression = f"clip(128+(val-128)*{saturation:.6f}+({v_shift:.6f}),0,255)"
    return (
        f"lutyuv=y='{y_expression}':u='{u_expression}':v='{v_expression}'"
    )


def append_segment_repair_filter(
    filters: list[str],
    *,
    input_label: str,
    output_label: str,
    label_prefix: str,
    plan: dict[str, Any],
) -> None:
    """Append a boundary-local correction that decays from the Segment opening."""
    original = f"{label_prefix}original"
    grade_input = f"{label_prefix}gradeinput"
    graded = f"{label_prefix}graded"
    fade = float(plan["fade_seconds"])
    filters.append(f"[{input_label}]split=2[{original}][{grade_input}]")
    filters.append(f"[{grade_input}]{repair_lut_filter(plan)}[{graded}]")
    blend = f"max(0,min(1,({fade:.6f}-T)/{fade:.6f}))"
    filters.append(
        f"[{original}][{graded}]blend=all_expr='A+(B-A)*{blend}'[{output_label}]"
    )


def _boundary_directory(root: Path, boundary: dict[str, Any]) -> Path:
    return root / f"{boundary['from']}--{boundary['to']}"


def _render_strict_sample(
    outgoing: object,
    incoming: object,
    boundary: dict[str, Any],
    output: Path,
    config: dict[str, Any],
) -> None:
    strict = config["strict_sample"]
    frame_rate = int(strict["frame_rate"])
    tail = float(strict["tail_seconds"])
    head = float(strict["head_seconds"])
    outgoing_probe = getattr(outgoing, "probe")
    incoming_probe = getattr(incoming, "probe")
    width = int(getattr(outgoing_probe, "width"))
    height = int(getattr(outgoing_probe, "height"))
    if width <= 0 or height <= 0:
        raise BoundaryQCError("Strict seam source has invalid dimensions")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(Path(getattr(outgoing, "video_path"))),
        "-i",
        str(Path(getattr(incoming, "video_path"))),
    ]
    filters: list[str] = []
    picture_edit = str(boundary.get("picture_edit"))
    overlap = float(boundary.get("overlap_seconds") or 0.0)
    if picture_edit in {"dissolve", "fade"}:
        handle = 1.0 + overlap / 2.0
        outgoing_start = max(
            0.0, float(getattr(outgoing_probe, "duration_seconds")) - handle
        )
        filters.extend(
            [
                f"[0:v]trim=start={outgoing_start:.6f}:duration={handle:.6f},"
                f"setpts=PTS-STARTPTS,fps={frame_rate},scale={width}:{height},"
                "setsar=1,format=yuv420p[v0]",
                f"[1:v]trim=start=0:duration={handle:.6f},setpts=PTS-STARTPTS,"
                f"fps={frame_rate},scale={width}:{height},setsar=1,format=yuv420p[v1]",
                f"[0:a]atrim=start={outgoing_start:.6f}:duration={handle:.6f},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0]",
                f"[1:a]atrim=start=0:duration={handle:.6f},asetpts=PTS-STARTPTS,"
                "aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a1]",
            ]
        )
        transition = "fade" if picture_edit == "dissolve" else "fadeblack"
        offset = handle - overlap
        filters.extend(
            [
                f"[v0][v1]xfade=transition={transition}:duration={overlap:.6f}:"
                f"offset={offset:.6f},fps={frame_rate},"
                f"tpad=stop_mode=clone:stop_duration={1.0 / frame_rate:.6f},"
                f"trim=end_frame={strict['frame_count']},setpts=PTS-STARTPTS[vout]",
                f"[a0][a1]acrossfade=d={overlap:.6f}:c1=qsin:c2=qsin[aout]",
            ]
        )
    else:
        outgoing_start = max(
            0.0, float(getattr(outgoing_probe, "duration_seconds")) - tail
        )
        filters.extend(
            [
                f"[0:v]trim=start={outgoing_start:.6f}:duration={tail:.6f},"
                f"setpts=PTS-STARTPTS,fps={frame_rate},scale={width}:{height},"
                "setsar=1,format=yuv420p[v0]",
                f"[1:v]trim=start=0:duration={head:.6f},setpts=PTS-STARTPTS,"
                f"fps={frame_rate},scale={width}:{height},setsar=1,format=yuv420p[v1]",
                f"[0:a]atrim=start={outgoing_start:.6f}:duration={tail:.6f},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0]",
                f"[1:a]atrim=start=0:duration={head:.6f},asetpts=PTS-STARTPTS,"
                "aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a1]",
                f"[v0][v1]concat=n=2:v=1:a=0,fps={frame_rate},"
                f"tpad=stop_mode=clone:stop_duration={1.0 / frame_rate:.6f},"
                f"trim=end_frame={strict['frame_count']},setpts=PTS-STARTPTS[vout]",
                "[a0][a1]concat=n=2:v=0:a=1[aout]",
            ]
        )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-frames:v",
            str(strict["frame_count"]),
            "-t",
            "2.000000",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    _run(command, label=f"Strict seam render {boundary['from']}->{boundary['to']}")


def _extract_frame_evidence(
    sample: Path,
    directory: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    strict = config["strict_sample"]
    frame_rate = int(strict["frame_rate"])
    frame_count = int(strict["frame_count"])
    evidence_width = int(strict["evidence_frame_width"])
    frames_dir = directory / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()
    pattern = frames_dir / "frame-%06d.png"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(sample),
            "-vf",
            f"fps={frame_rate},scale={evidence_width}:-2:flags=lanczos",
            "-frames:v",
            str(frame_count),
            str(pattern),
        ],
        label="Strict seam frame extraction",
    )
    frames = sorted(frames_dir.glob("frame-*.png"))
    if len(frames) != frame_count:
        raise BoundaryQCError(
            f"Strict seam must decode to {frame_count} frames, found {len(frames)}"
        )
    manifest = {
        "contract": "finish-boundary-frame-manifest/v1",
        "sample": str(sample.resolve()),
        "frame_rate": frame_rate,
        "frame_count": frame_count,
        "frames": [
            {
                "frame_index": index,
                "timestamp_seconds": round(index / frame_rate, 6),
                "path": str(path.resolve()),
            }
            for index, path in enumerate(frames)
        ],
    }
    manifest_path = directory / "frame-manifest.json"
    _write_json(manifest_path, manifest)
    contact_sheet = directory / "contact-sheet-48.jpg"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(sample),
            "-vf",
            f"fps={frame_rate},scale=320:-2:flags=lanczos,"
            "tile=8x6:padding=2:margin=2:color=black",
            "-frames:v",
            "1",
            str(contact_sheet),
        ],
        label="Strict seam contact sheet render",
    )
    return {
        "sample": str(sample.resolve()),
        "frame_manifest": str(manifest_path.resolve()),
        "contact_sheet": str(contact_sheet.resolve()),
        "frames_directory": str(frames_dir.resolve()),
        "frame_count": frame_count,
    }


def _render_repaired_sample(
    source: Path,
    output: Path,
    plan: dict[str, Any],
    *,
    strength: float,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fade = float(plan["fade_seconds"])
    correction_end = 1.0 + fade
    weight = (
        f"if(gte(T,1.000000),"
        f"max(0,min(1,({correction_end:.6f}-T)/{fade:.6f})),0)"
    )
    filters = (
        "[0:v]split=2[original][gradeinput];"
        f"[gradeinput]{repair_lut_filter(plan, strength=strength)}[graded];"
        f"[original][graded]blend=all_expr='A+(B-A)*{weight}'[vout]"
    )
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            filters,
            "-map",
            "[vout]",
            "-map",
            "0:a:0?",
            "-frames:v",
            "48",
            "-t",
            "2.000000",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        label="Boundary repair candidate render",
    )


def _render_comparison(original: Path, repaired: Path, output: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(original),
            "-i",
            str(repaired),
            "-filter_complex",
            "[0:v]scale=960:-2[left];[1:v]scale=960:-2[right];"
            "[left][right]hstack=inputs=2[vout]",
            "-map",
            "[vout]",
            "-map",
            "0:a:0?",
            "-t",
            "2.000000",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        label="Original/repaired boundary comparison render",
    )


def _matches_selected(boundary: dict[str, Any], selected: str | None) -> bool:
    if not selected:
        return True
    normalized = selected.replace("->", ":")
    return normalized == f"{boundary['from']}:{boundary['to']}"


def prepare_boundary_qc(
    task_dir: Path,
    records: list[object],
    picture_edl: dict[str, Any],
    *,
    config_path: Path = DEFAULT_CONFIG,
    selected_boundary: str | None = None,
    generate_candidates: bool = True,
) -> tuple[Path, dict[str, dict[str, Any]], dict[str, Any]]:
    """Create pre-assembly evidence and return safe plans keyed by incoming Segment."""
    task_dir = task_dir.expanduser().resolve()
    config = load_config(config_path)
    root = task_dir / ".pending" / "finish-postproduction" / "boundary-qc"
    pre_root = root / "pre-assembly"
    manifest_path = root / "boundary-qc-manifest.json"
    record_by_name = {
        str(getattr(record, "segment_name")): record for record in records
    }
    manifest: dict[str, Any] = {
        "contract": "finish-boundary-qc/v1",
        "enabled": bool(config["enabled"]),
        "source_policy": "generated_segments_read_only",
        "decision_scope": "technical_detection_and_repair_candidates_only",
        "semantic_review_authority": "seedance-video-review",
        "config_path": str(config_path.expanduser().resolve()),
        "task_dir": str(task_dir),
        "picture_edl_contract": picture_edl.get("contract"),
        "pre_assembly_status": "disabled" if not config["enabled"] else "running",
        "boundaries": [],
    }
    repair_plans: dict[str, dict[str, Any]] = {}
    if not config["enabled"]:
        _write_json(manifest_path, manifest)
        return manifest_path, repair_plans, manifest
    boundaries = picture_edl.get("boundaries")
    if not isinstance(boundaries, list):
        raise BoundaryQCError("Picture EDL boundaries must be a list")
    for boundary in boundaries:
        if not isinstance(boundary, dict) or not _matches_selected(
            boundary, selected_boundary
        ):
            continue
        try:
            outgoing = record_by_name[str(boundary["from"])]
            incoming = record_by_name[str(boundary["to"])]
        except KeyError as exc:
            raise BoundaryQCError("Boundary references an unknown Segment") from exc
        directory = _boundary_directory(pre_root, boundary)
        original_sample = directory / "original-strict-seam.mp4"
        _render_strict_sample(outgoing, incoming, boundary, original_sample, config)
        evidence = _extract_frame_evidence(original_sample, directory, config)
        metrics = measure_boundary(outgoing, incoming, config)
        status, reason, plan = triage_boundary(boundary, metrics, config)
        item: dict[str, Any] = {
            "boundary_id": f"{boundary['from']}--{boundary['to']}",
            "from": boundary["from"],
            "to": boundary["to"],
            "timeline_seconds": boundary.get("timeline_seconds"),
            "authored_transition_type": boundary.get("authored_transition_type"),
            "transition_class": boundary.get("transition_class"),
            "picture_edit": boundary.get("picture_edit"),
            "overlap_seconds": boundary.get("overlap_seconds"),
            "source_paths": {
                "outgoing": str(Path(getattr(outgoing, "video_path")).resolve()),
                "incoming": str(Path(getattr(incoming, "video_path")).resolve()),
            },
            "pre_assembly_evidence": evidence,
            "metrics": metrics,
            "technical_triage": status,
            "technical_triage_reason": reason,
            "repair": None,
            "final_timeline_audit": None,
        }
        if plan is not None:
            plan.update(
                {
                    "boundary_id": item["boundary_id"],
                    "from": boundary["from"],
                    "to": boundary["to"],
                    "applied_to_picture_lock": status == "safe_color_match_planned",
                }
            )
            candidate_paths: dict[str, str] = {}
            if generate_candidates:
                candidates = directory / "candidates"
                for name, strength in config["repair"]["candidate_strengths"].items():
                    candidate = candidates / f"{name}.mp4"
                    _render_repaired_sample(
                        original_sample,
                        candidate,
                        plan,
                        strength=float(strength),
                    )
                    candidate_paths[str(name)] = str(candidate.resolve())
                comparison = directory / "original-vs-matched.mp4"
                _render_comparison(
                    original_sample,
                    Path(candidate_paths["matched"]),
                    comparison,
                )
                plan["comparison_preview"] = str(comparison.resolve())
            plan["candidate_previews"] = candidate_paths
            item["repair"] = plan
            if status == "safe_color_match_planned":
                repair_plans[str(boundary["to"])] = plan
        manifest["boundaries"].append(item)
        _write_json(manifest_path, manifest)
    if selected_boundary and not manifest["boundaries"]:
        raise BoundaryQCError(f"Selected boundary was not found: {selected_boundary}")
    blocking = [
        item["boundary_id"]
        for item in manifest["boundaries"]
        if item["technical_triage"]
        in {"review_required", "repair_candidate_review_required"}
    ]
    manifest["pre_assembly_status"] = (
        "review_required" if blocking else "ready_for_picture_lock"
    )
    manifest["blocking_boundaries"] = blocking
    manifest["planned_repair_count"] = len(repair_plans)
    _write_json(manifest_path, manifest)
    return manifest_path, repair_plans, manifest


def _render_master_sample(
    picture_lock: Path,
    boundary: dict[str, Any],
    output: Path,
) -> None:
    picture_edit = boundary.get("picture_edit")
    if picture_edit in {"dissolve", "fade"}:
        center = (
            float(boundary["transition_start_seconds"])
            + float(boundary["transition_end_seconds"])
        ) / 2.0
    else:
        center = float(boundary["timeline_seconds"])
    start = max(0.0, center - 1.0)
    coarse_start = max(0.0, start - 2.0)
    precise_offset = start - coarse_start
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{coarse_start:.6f}",
    ]
    if picture_edit == "hard_cut":
        command.append("-copyts")
    command.extend(["-i", str(picture_lock)])
    if picture_edit == "hard_cut":
        authored_cut = float(boundary["timeline_seconds"])
        cut = math.ceil(authored_cut * 24.0 - 1e-9) / 24.0
        left_start = max(0.0, cut - 1.0)
        right_end = cut + 1.0
        frame_pad = 1.0 / 24.0
        filters = (
            "[0:v]split=2[vleftin][vrightin];"
            f"[vleftin]trim=start={left_start:.6f}:end={cut:.6f},"
            f"setpts=PTS-STARTPTS,fps=24,tpad=stop_mode=clone:stop_duration={frame_pad:.6f},"
            "trim=end_frame=24,setpts=PTS-STARTPTS[vleft];"
            f"[vrightin]trim=start={cut:.6f}:end={right_end:.6f},"
            f"setpts=PTS-STARTPTS,fps=24,tpad=stop_mode=clone:stop_duration={frame_pad:.6f},"
            "trim=end_frame=24,setpts=PTS-STARTPTS[vright];"
            "[vleft][vright]concat=n=2:v=1:a=0[vout];"
            "[0:a]asplit=2[aleftin][arightin];"
            f"[aleftin]atrim=start={left_start:.6f}:end={cut:.6f},"
            "asetpts=PTS-STARTPTS,aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aleft];"
            f"[arightin]atrim=start={cut:.6f}:end={right_end:.6f},"
            "asetpts=PTS-STARTPTS,aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aright];"
            "[aleft][aright]concat=n=2:v=0:a=1[aout]"
        )
        command.extend(
            [
                "-filter_complex",
                filters,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
            ]
        )
    else:
        command.extend(
            [
                "-ss",
                f"{precise_offset:.6f}",
                "-t",
                "2.000000",
                "-vf",
                "fps=24",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
            ]
        )
    command.extend(
        [
            "-frames:v",
            "48",
            "-t",
            "2.000000",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    _run(
        command,
        label="Final timeline strict seam render",
    )


class _AuditProbe:
    def __init__(self, width: int, height: int, duration_seconds: float = 2.0):
        self.width = width
        self.height = height
        self.duration_seconds = duration_seconds


class _AuditRecord:
    def __init__(self, path: Path, width: int, height: int):
        self.video_path = path
        self.probe = _AuditProbe(width, height)


class _StandaloneProbe(_AuditProbe):
    def __init__(
        self,
        width: int,
        height: int,
        duration_seconds: float,
        has_audio: bool,
        frame_rate: str,
    ):
        super().__init__(width, height, duration_seconds)
        self.has_audio = has_audio
        self.frame_rate = frame_rate


class _StandaloneRecord(_AuditRecord):
    def __init__(
        self,
        segment_name: str,
        path: Path,
        probe: _StandaloneProbe,
    ):
        self.segment_name = segment_name
        self.video_path = path
        self.probe = probe


def _probe_dimensions(path: Path) -> tuple[int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise BoundaryQCError(f"Could not probe final seam: {path}") from exc


def _probe_standalone(path: Path) -> _StandaloneProbe:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,duration,width,height,avg_frame_rate,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        video = next(
            item
            for item in payload["streams"]
            if item.get("codec_type") == "video"
        )
        return _StandaloneProbe(
            int(video["width"]),
            int(video["height"]),
            float(video.get("duration") or payload["format"]["duration"]),
            any(item.get("codec_type") == "audio" for item in payload["streams"]),
            str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "24/1"),
        )
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        StopIteration,
        TypeError,
        ValueError,
    ) as exc:
        raise BoundaryQCError(f"Could not probe standalone Segment: {path}") from exc


def standalone_records_from_edl(
    task_dir: Path, picture_edl: dict[str, Any]
) -> list[object]:
    """Load media named by an existing EDL without requiring current project schemas."""
    records: list[object] = []
    events = picture_edl.get("picture_events")
    if not isinstance(events, list) or not events:
        raise BoundaryQCError("Standalone picture EDL has no picture events")
    for event in events:
        if not isinstance(event, dict):
            raise BoundaryQCError("Standalone picture EDL event is invalid")
        segment_name = str(event.get("segment_id") or "")
        source = Path(str(event.get("source") or "")).expanduser()
        if not source.is_file():
            source = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "generation-segments"
                / segment_name
                / "video.mp4"
            )
        if not source.is_file():
            raise BoundaryQCError(
                f"Could not resolve standalone Segment source: {segment_name}"
            )
        probe = _probe_standalone(source.resolve())
        if not probe.has_audio:
            raise BoundaryQCError(f"Standalone Segment has no native audio: {source}")
        records.append(_StandaloneRecord(segment_name, source.resolve(), probe))
    return records


def _measure_master_sample(sample: Path, config: dict[str, Any]) -> dict[str, Any]:
    width, height = _probe_dimensions(sample)
    analysis_width = int(config["analysis"]["width"])
    analysis_height = max(2, round(height * analysis_width / width))
    analysis_height += analysis_height % 2
    count = int(config["analysis"]["anchor_frame_count"])
    rate = int(config["strict_sample"]["frame_rate"])
    all_frames = _extract_yuv_frames(
        sample,
        start_seconds=0.0,
        frame_count=int(config["strict_sample"]["frame_count"]),
        frame_rate=rate,
        width=analysis_width,
        height=analysis_height,
    )
    expected_incoming_index = int(config["strict_sample"]["frame_count"]) // 2
    candidate_indices = range(
        expected_incoming_index - 2,
        expected_incoming_index + 4,
    )
    pair_correlations = {
        index: _normalized_luma_correlation(
            all_frames[index - 1][0], all_frames[index][0]
        )
        for index in candidate_indices
    }
    incoming_index = min(pair_correlations, key=pair_correlations.get)
    outgoing = all_frames[incoming_index - count : incoming_index]
    incoming = all_frames[incoming_index : incoming_index + count]
    outgoing_stats = _plane_stats(outgoing)
    incoming_stats = _plane_stats(incoming)
    saturation_factor = outgoing_stats["saturation_mean"] / max(
        1e-6, incoming_stats["saturation_mean"]
    )
    delta_u = outgoing_stats["u_mean"] - incoming_stats["u_mean"]
    delta_v = outgoing_stats["v_mean"] - incoming_stats["v_mean"]
    return {
        "analysis_role": "post_assembly_technical_detection_evidence_only",
        "analysis_frame_width": analysis_width,
        "analysis_frame_height": analysis_height,
        "analysis_frame_count_per_side": count,
        "located_cut": {
            "expected_incoming_frame_index": expected_incoming_index,
            "located_incoming_frame_index": incoming_index,
            "located_pair": [incoming_index - 1, incoming_index],
            "candidate_pair_correlations": {
                f"{index - 1}-{index}": round(value, 6)
                for index, value in pair_correlations.items()
            },
        },
        "outgoing": outgoing_stats,
        "incoming": incoming_stats,
        "delta_target_minus_incoming": {
            "luma_q10": round(outgoing_stats["luma_q10"] - incoming_stats["luma_q10"], 6),
            "luma_mean": round(outgoing_stats["luma_mean"] - incoming_stats["luma_mean"], 6),
            "luma_q90": round(outgoing_stats["luma_q90"] - incoming_stats["luma_q90"], 6),
            "u_mean": round(delta_u, 6),
            "v_mean": round(delta_v, 6),
            "chroma_center_distance": round(math.hypot(delta_u, delta_v), 6),
            "saturation_factor": round(saturation_factor, 6),
            "saturation_ratio_delta": round(saturation_factor - 1.0, 6),
        },
        "luma_shape_correlation": round(
            _normalized_luma_correlation(outgoing[-1][0], incoming[0][0]), 6
        ),
    }


def audit_picture_lock(
    picture_lock: Path,
    picture_edl: dict[str, Any],
    manifest_path: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Re-extract every selected seam from the rendered picture lock."""
    config = load_config(config_path)
    manifest = _load_json(manifest_path, label="boundary QC manifest")
    root = manifest_path.parent / "final-timeline"
    boundary_by_id = {
        f"{item['from']}--{item['to']}": item
        for item in picture_edl.get("boundaries", [])
        if isinstance(item, dict)
    }
    blocking: list[str] = []
    for item in manifest.get("boundaries", []):
        boundary_id = str(item["boundary_id"])
        try:
            boundary = boundary_by_id[boundary_id]
        except KeyError as exc:
            raise BoundaryQCError(
                f"Final timeline no longer contains boundary {boundary_id}"
            ) from exc
        directory = root / boundary_id
        sample = directory / "final-strict-seam.mp4"
        _render_master_sample(picture_lock, boundary, sample)
        evidence = _extract_frame_evidence(sample, directory, config)
        metrics = None
        if boundary.get("picture_edit") == "hard_cut":
            metrics = _measure_master_sample(sample, config)
            high_match = float(metrics["luma_shape_correlation"]) >= float(
                config["analysis"]["minimum_match_similarity"]
            )
            residual = high_match and _has_detectable_mismatch(metrics, config)
            if item.get("repair") and item["repair"].get("applied_to_picture_lock"):
                technical_status = (
                    "residual_review_required"
                    if residual
                    else "correction_within_detection_thresholds"
                )
            elif item.get("technical_triage") == "no_technical_correction_needed":
                technical_status = (
                    "matched_cut_review_required"
                    if residual
                    else "no_high_confidence_flash_signature"
                )
            else:
                technical_status = "authored_cut_evidence_only"
            if technical_status.endswith("review_required"):
                blocking.append(boundary_id)
        else:
            technical_status = "authored_transition_rendered_for_review"
        item["final_timeline_audit"] = {
            "evidence": evidence,
            "metrics": metrics,
            "technical_status": technical_status,
        }
    manifest["picture_lock"] = str(picture_lock.resolve())
    manifest["final_timeline_status"] = (
        "review_required" if blocking else "technical_audit_complete"
    )
    manifest["final_timeline_blocking_boundaries"] = blocking
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--picture-edl",
        type=Path,
        help="Use an existing picture EDL without requiring current task schemas.",
    )
    parser.add_argument(
        "--boundary",
        help="Optional FROM:TO selector, for example segment-005:segment-006.",
    )
    parser.add_argument("--no-candidates", action="store_true")
    args = parser.parse_args()
    if str(SCRIPT_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPT_ROOT))
    try:
        from post_timeline import compile_timelines, discover_segments

        task_dir = args.task_dir.expanduser().resolve()
        if args.picture_edl is not None:
            picture_edl = _load_json(
                args.picture_edl.expanduser().resolve(),
                label="standalone picture EDL",
            )
            records = standalone_records_from_edl(task_dir, picture_edl)
        else:
            records = discover_segments(task_dir)
            picture_edl, _ = compile_timelines(task_dir, records)
        manifest_path, repairs, manifest = prepare_boundary_qc(
            task_dir,
            records,
            picture_edl,
            config_path=args.config.expanduser().resolve(),
            selected_boundary=args.boundary,
            generate_candidates=not args.no_candidates,
        )
    except (BoundaryQCError, OSError, subprocess.CalledProcessError) as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": manifest["pre_assembly_status"],
                "manifest": str(manifest_path.resolve()),
                "boundary_count": len(manifest["boundaries"]),
                "planned_repair_count": len(repairs),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
