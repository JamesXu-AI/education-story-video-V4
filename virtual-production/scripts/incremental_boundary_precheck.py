#!/usr/bin/env python3
"""Prepare and route one newly available predecessor/current Segment seam."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    REPOSITORY_ROOT
    / "virtual-production"
    / "assets"
    / "incremental-boundary-precheck.json"
)
EVIDENCE_HELPER = (
    REPOSITORY_ROOT
    / "seedance-video-review"
    / "scripts"
    / "prepare_review_evidence.py"
)
TRANSITION_LINE_RE = re.compile(
    r"^- `transition_design_json`: (?P<payload>\{.*\})\s*$"
)


class IncrementalBoundaryPrecheckError(RuntimeError):
    """Raised when immediate seam evidence cannot be prepared safely."""


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncrementalBoundaryPrecheckError(f"Missing or invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise IncrementalBoundaryPrecheckError(f"{label} must contain one JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _read_json(path.expanduser().resolve(), label="incremental precheck config")
    if (
        config.get("contract")
        != "virtual-production-incremental-boundary-precheck-config/v1"
        or not isinstance(config.get("enabled"), bool)
    ):
        raise IncrementalBoundaryPrecheckError(
            "Unsupported incremental boundary precheck config"
        )
    similarity = config.get("minimum_matched_endpoint_ssim")
    if (
        isinstance(similarity, bool)
        or not isinstance(similarity, (int, float))
        or not 0 < float(similarity) <= 1
    ):
        raise IncrementalBoundaryPrecheckError(
            "minimum_matched_endpoint_ssim must be in (0, 1]"
        )
    for section_name in ("detection", "technical_hold_limits"):
        section = config.get(section_name)
        if not isinstance(section, dict):
            raise IncrementalBoundaryPrecheckError(
                f"{section_name} must be an object"
            )
        for key in (
            "absolute_luma_average_delta",
            "absolute_saturation_average_delta",
            "chroma_vector_delta",
        ):
            value = section.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
            ):
                raise IncrementalBoundaryPrecheckError(
                    f"{section_name}.{key} must be positive"
                )
    durations = config.get("transition_duration_seconds")
    if not isinstance(durations, dict):
        raise IncrementalBoundaryPrecheckError(
            "transition_duration_seconds must be an object"
        )
    return config


def _segment_dir(task_dir: Path, segment_id: str) -> Path:
    return (
        task_dir
        / ".pending"
        / "virtual-production"
        / "generation-segments"
        / segment_id
    )


def _published_identity(task_dir: Path, segment_id: str) -> dict[str, Any] | None:
    directory = _segment_dir(task_dir, segment_id)
    video = directory / "video.mp4"
    record_path = directory / "production-record.json"
    if not video.is_file() or not record_path.is_file():
        return None
    record = _read_json(record_path, label=f"{segment_id} production record")
    attempt_id = record.get("provider_attempt_id")
    if (
        record.get("contract") != "generated-segment-production-record"
        or record.get("status") != "GENERATED"
        or record.get("segment_id") != segment_id
        or not isinstance(attempt_id, str)
        or not attempt_id
    ):
        raise IncrementalBoundaryPrecheckError(
            f"{segment_id} is not a current generated Segment"
        )
    return {
        "segment_id": segment_id,
        "provider_attempt_id": attempt_id,
        "video": video.resolve(),
        "production_record": record_path.resolve(),
    }


def _storyboard_transition_designs(task_dir: Path) -> list[dict[str, Any]] | None:
    """Read authored Generation Plan seams from the current single-file Storyboard."""

    path = task_dir / "previsualize-cinematography" / "storyboard.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise IncrementalBoundaryPrecheckError(
            f"Could not read Storyboard: {path}"
        ) from exc
    start = text.find("## Generation Plan")
    if start < 0:
        raise IncrementalBoundaryPrecheckError(
            "Storyboard contains no Generation Plan"
        )
    section = text[start + len("## Generation Plan"):]
    next_heading = re.search(r"^## ", section, re.M)
    if next_heading:
        section = section[:next_heading.start()]
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        raise IncrementalBoundaryPrecheckError(
            "Storyboard Generation Plan has no Segment rows"
        )

    def cells(line: str) -> list[str]:
        return [item.strip() for item in line.strip("|").split("|")]

    headers = cells(table_lines[0])
    try:
        segment_index = headers.index("Segment")
        seam_index = headers.index("Seam")
    except ValueError as exc:
        raise IncrementalBoundaryPrecheckError(
            "Storyboard Generation Plan lacks Segment or Seam"
        ) from exc
    rows = [cells(line) for line in table_lines[2:]]
    if any(len(row) != len(headers) for row in rows):
        raise IncrementalBoundaryPrecheckError(
            "Storyboard Generation Plan has an invalid row"
        )

    def transition_type(seam: str) -> str:
        value = seam.casefold()
        for marker, authored_type in (
            ("dissolve", "dissolve"),
            ("fade to black", "fade_to_black"),
            ("fade", "fade"),
            ("eyeline", "eyeline_cut"),
            ("reaction", "reaction_cut"),
            ("match", "match_cut"),
            ("action", "action_cut"),
            ("wipe", "effects_wipe"),
        ):
            if marker in value:
                return authored_type
        return "editorial_cut"

    designs = [
        {
            "type": transition_type(row[seam_index]),
            "reason_en": row[seam_index],
            "source": "storyboard_generation_plan",
            "incoming_segment": row[segment_index],
        }
        for row in rows[1:]
    ]
    designs.append(
        {
            "type": "final_end",
            "reason_en": "End of the final Generation Segment.",
            "source": "storyboard_generation_plan",
            "incoming_segment": "none",
        }
    )
    return designs


def _story_transition_designs(task_dir: Path) -> list[dict[str, Any]]:
    storyboard_designs = _storyboard_transition_designs(task_dir)
    if storyboard_designs is not None:
        return storyboard_designs
    path = task_dir / "screenplay-writer" / "screenplay.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        raise IncrementalBoundaryPrecheckError(f"Could not read screenplay: {path}") from exc
    transitions: list[dict[str, Any]] = []
    for line in lines:
        match = TRANSITION_LINE_RE.fullmatch(line.strip())
        if not match:
            continue
        try:
            payload = json.loads(match.group("payload"))
        except json.JSONDecodeError as exc:
            raise IncrementalBoundaryPrecheckError(
                "screenplay transition_design_json is invalid"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
            raise IncrementalBoundaryPrecheckError(
                "screenplay transition design lacks a type"
            )
        transitions.append(payload)
    if not transitions:
        raise IncrementalBoundaryPrecheckError(
            "screenplay contains no transition_design_json records"
        )
    return transitions


def boundary_contract(
    task_dir: Path,
    incoming_segment_id: str,
    ordered_segment_ids: list[str],
    *,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        incoming_index = ordered_segment_ids.index(incoming_segment_id)
    except ValueError as exc:
        raise IncrementalBoundaryPrecheckError(
            f"Unknown Segment for boundary precheck: {incoming_segment_id}"
        ) from exc
    if incoming_index == 0:
        return None
    transitions = _story_transition_designs(task_dir)
    if len(transitions) != len(ordered_segment_ids):
        raise IncrementalBoundaryPrecheckError(
            "Screenplay transition coverage differs from Segment order"
        )
    transition = transitions[incoming_index - 1]
    transition_type = str(transition["type"])
    duration = float(
        config["transition_duration_seconds"].get(transition_type, 0.0)
    )
    return {
        "boundary_id": (
            f"{ordered_segment_ids[incoming_index - 1]}--{incoming_segment_id}"
        ),
        "from": ordered_segment_ids[incoming_index - 1],
        "to": incoming_segment_id,
        "outgoing_segment_number": incoming_index,
        "incoming_segment_number": incoming_index + 1,
        "authored_transition_type": transition_type,
        "transition_duration_seconds": duration,
        "transition_design": transition,
    }


def classify_technical_precheck(
    evidence: dict[str, Any], config: dict[str, Any]
) -> tuple[str, str, bool, str]:
    metrics = evidence.get("metrics")
    if not isinstance(metrics, dict):
        raise IncrementalBoundaryPrecheckError("Review evidence has no metrics")
    transition = metrics.get("boundary_transition_contract")
    if not isinstance(transition, dict):
        raise IncrementalBoundaryPrecheckError(
            "Review evidence has no transition contract"
        )
    transition_class = transition.get("transition_class")
    if transition_class in {"dissolve", "fade", "baked_effect"}:
        return (
            "authored_transition_evidence_ready",
            "The authored transition is rendered for direct picture-and-sound review; no endpoint color match is attempted.",
            False,
            "seedance-video-review",
        )
    signal = metrics.get("boundary_signalstats")
    similarity = metrics.get("boundary_ssim")
    if not isinstance(signal, dict) or not isinstance(similarity, (int, float)):
        raise IncrementalBoundaryPrecheckError(
            "Cut-like boundary evidence lacks SSIM or signal statistics"
        )
    matched = float(similarity) >= float(config["minimum_matched_endpoint_ssim"])
    detection = config["detection"]
    values = {
        "absolute_luma_average_delta": float(
            signal["absolute_luma_average_delta"]
        ),
        "absolute_saturation_average_delta": float(
            signal["absolute_saturation_average_delta"]
        ),
        "chroma_vector_delta": float(signal["chroma_vector_delta"]),
    }
    detectable = any(
        values[key] >= float(detection[key]) for key in values
    )
    if not matched or not detectable:
        return (
            "visual_review_ready",
            "No high-confidence matched-endpoint flash signature was detected; direct semantic review is still required.",
            False,
            "seedance-video-review",
        )
    limits = config["technical_hold_limits"]
    exceeds_hold = any(values[key] > float(limits[key]) for key in values)
    if exceeds_hold:
        return (
            "technical_hold_for_visual_review",
            "A visually matched boundary has a color/exposure jump above the automatic postproduction safety limits.",
            True,
            "virtual-production",
        )
    return (
        "postproduction_color_match_candidate",
        "A visually matched boundary has a small color/exposure jump suitable for reversible postproduction matching.",
        False,
        "finish-postproduction",
    )


def _cached_precheck(
    record_path: Path,
    *,
    predecessor_attempt_id: str,
    current_attempt_id: str,
    config_sha256: str,
) -> dict[str, Any] | None:
    if not record_path.is_file():
        return None
    record = _read_json(record_path, label="incremental boundary technical precheck")
    identity = record.get("source_identity")
    evidence = record.get("review_evidence")
    artifacts = evidence.get("artifacts") if isinstance(evidence, dict) else None
    required_artifacts = (
        artifacts.get("boundary_preview") if isinstance(artifacts, dict) else None,
        artifacts.get("boundary_frame_manifest") if isinstance(artifacts, dict) else None,
        artifacts.get("boundary_all_frames_contact_sheet")
        if isinstance(artifacts, dict)
        else None,
    )
    if (
        record.get("contract")
        != "virtual-production-incremental-boundary-precheck/v1"
        or not isinstance(identity, dict)
        or identity.get("predecessor_provider_attempt_id")
        != predecessor_attempt_id
        or identity.get("current_provider_attempt_id") != current_attempt_id
        or identity.get("config_sha256") != config_sha256
        or not all(
            isinstance(path, str) and Path(path).is_file()
            for path in required_artifacts
        )
    ):
        return None
    return record


def prepare_incremental_boundary_precheck(
    task_dir: Path,
    incoming_segment_id: str,
    ordered_segment_ids: list[str],
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    config_path = config_path.expanduser().resolve()
    config = load_config(config_path)
    contract = boundary_contract(
        task_dir,
        incoming_segment_id,
        ordered_segment_ids,
        config=config,
    )
    if contract is None:
        return {
            "boundary_id": None,
            "to": incoming_segment_id,
            "technical_status": "opening_segment_not_applicable",
            "blocks_downstream": False,
        }
    predecessor = _published_identity(task_dir, contract["from"])
    current = _published_identity(task_dir, contract["to"])
    if current is None:
        return {
            **contract,
            "technical_status": "waiting_for_current_segment",
            "blocks_downstream": False,
        }
    if predecessor is None:
        return {
            **contract,
            "technical_status": "waiting_for_predecessor_segment",
            "blocks_downstream": False,
        }
    if not config["enabled"]:
        return {
            **contract,
            "technical_status": "disabled",
            "blocks_downstream": False,
        }
    output_dir = _segment_dir(task_dir, incoming_segment_id) / "boundary-precheck"
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "technical-boundary-precheck.json"
    config_sha256 = _sha256(config_path)
    cached = _cached_precheck(
        record_path,
        predecessor_attempt_id=predecessor["provider_attempt_id"],
        current_attempt_id=current["provider_attempt_id"],
        config_sha256=config_sha256,
    )
    if cached is not None:
        return cached
    if not EVIDENCE_HELPER.is_file():
        raise IncrementalBoundaryPrecheckError(
            f"Missing repository-local review evidence helper: {EVIDENCE_HELPER}"
        )
    command = [
        sys.executable,
        str(EVIDENCE_HELPER),
        "--scene-id",
        str(contract["incoming_segment_number"]),
        "--scene-video",
        str(current["video"]),
        "--output-dir",
        str(output_dir),
        "--previous-scene-id",
        str(contract["outgoing_segment_number"]),
        "--previous-video",
        str(predecessor["video"]),
        "--transition-type",
        str(contract["authored_transition_type"]),
        "--transition-seconds",
        f"{contract['transition_duration_seconds']:.6f}",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        evidence = json.loads(completed.stdout)
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        detail = (
            completed.stderr.strip()
            if "completed" in locals() and completed.stderr
            else str(exc)
        )
        raise IncrementalBoundaryPrecheckError(
            f"Could not prepare {contract['boundary_id']} evidence: {detail}"
        ) from exc
    if not isinstance(evidence, dict):
        raise IncrementalBoundaryPrecheckError(
            "Review evidence helper returned a non-object payload"
        )
    status, reason, blocks, owner = classify_technical_precheck(evidence, config)
    record = {
        "contract": "virtual-production-incremental-boundary-precheck/v1",
        **contract,
        "source_identity": {
            "predecessor_provider_attempt_id": predecessor["provider_attempt_id"],
            "current_provider_attempt_id": current["provider_attempt_id"],
            "predecessor_video": str(predecessor["video"]),
            "current_video": str(current["video"]),
            "config_path": str(config_path),
            "config_sha256": config_sha256,
        },
        "review_evidence": evidence,
        "technical_status": status,
        "technical_reason": reason,
        "blocks_downstream": blocks,
        "recommended_owner": owner,
        "semantic_review_handoff": {
            "reviewer": "repository-local seedance-video-review",
            "result_transport": "active_task_only",
            "persisted_approval_forbidden": True,
            "required_action": (
                "Watch the complete current Segment and strict boundary with sound; "
                "return NO_ISSUES or a concrete issue list before regeneration routing."
            ),
        },
        "record_path": str(record_path.resolve()),
    }
    _write_json(record_path, record)
    return record


def prepare_adjacent_boundary_prechecks(
    task_dir: Path,
    completed_segment_id: str,
    ordered_segment_ids: list[str],
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> list[dict[str, Any]]:
    """Prepare the incoming seam and a previously generated successor seam."""
    try:
        index = ordered_segment_ids.index(completed_segment_id)
    except ValueError as exc:
        raise IncrementalBoundaryPrecheckError(
            f"Unknown completed Segment: {completed_segment_id}"
        ) from exc
    targets = [completed_segment_id]
    if index + 1 < len(ordered_segment_ids):
        targets.append(ordered_segment_ids[index + 1])
    results: list[dict[str, Any]] = []
    for target in targets:
        result = prepare_incremental_boundary_precheck(
            task_dir,
            target,
            ordered_segment_ids,
            config_path=config_path,
        )
        if result.get("boundary_id") is not None:
            results.append(result)
    return results
