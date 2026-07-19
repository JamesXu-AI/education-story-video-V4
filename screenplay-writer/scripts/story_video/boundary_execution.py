"""Compile authored transition semantics into executable boundary behavior.

The screenplay owns why an edit exists.  This module is the single deterministic
projection from that authored meaning to generation, finishing, and review
contracts.  It deliberately does not judge generated pixels or sound.
"""

from __future__ import annotations

from typing import Any


EDITORIAL_CUT_TYPES = {
    "hard_cut",
    "action_cut",
    "match_cut",
    "eyeline_cut",
    "reaction_cut",
}
TEMPORAL_TRANSITION_TYPES = {"dissolve", "fade"}
BAKED_TRANSITION_TYPES = {
    "animated_wipe",
    "animated_morph",
    "animated_match",
    "effects_wipe",
    "light_flash_transition",
    "particle_bridge",
    "environmental_transition",
}
DESIGNED_TRANSITION_TYPES = TEMPORAL_TRANSITION_TYPES | BAKED_TRANSITION_TYPES
TRANSITION_CLASSES = {
    "continuous_action",
    "motivated_cut",
    "designed_transition",
    "scene_change",
}

DEFAULT_TRANSITION_SECONDS = {
    "dissolve": 0.8,
    "fade": 0.6,
}

MOTIVATED_CUT_ALLOWED_CHANGES = [
    "camera_angle",
    "lens",
    "shot_size",
    "composition",
    "focus",
    "visible_background",
    "exposure",
]

SEMANTIC_CONTINUITY_CHECKS = [
    "character_identity",
    "character_relationships",
    "costume_and_appearance_state",
    "injury_and_body_state",
    "prop_ownership_and_state",
    "emotional_and_knowledge_state",
    "event_causality_and_time_order",
    "location_screen_geography",
    "eyeline_and_axis_legibility",
    "motivated_light_direction",
    "native_audio_no_click_dropout_or_restart",
]


class BoundaryExecutionError(ValueError):
    """Raised when authored transition data cannot produce a safe execution."""


def classify_boundary(
    *,
    transition_type: str,
    from_scene_id: str,
    to_scene_id: str,
    successor_continuity_mode: str = "editorial_cut",
) -> str:
    """Return the semantic boundary class without inspecting generated media."""

    if successor_continuity_mode == "continuous_action":
        if transition_type not in EDITORIAL_CUT_TYPES:
            raise BoundaryExecutionError(
                "continuous_action requires a cut-like authored transition"
            )
        return "continuous_action"
    if transition_type in DESIGNED_TRANSITION_TYPES:
        return "designed_transition"
    if from_scene_id != to_scene_id:
        return "scene_change"
    if transition_type in EDITORIAL_CUT_TYPES:
        return "motivated_cut"
    raise BoundaryExecutionError(f"Unsupported boundary transition: {transition_type}")


def build_boundary_execution(
    *,
    transition_design: dict[str, Any],
    from_scene_id: str,
    to_scene_id: str,
    successor_continuity_mode: str = "editorial_cut",
) -> dict[str, Any]:
    """Project one authored boundary into generation, finishing, and review rules."""

    transition_type = str(transition_design.get("type") or "")
    transition_class = classify_boundary(
        transition_type=transition_type,
        from_scene_id=from_scene_id,
        to_scene_id=to_scene_id,
        successor_continuity_mode=successor_continuity_mode,
    )
    duration = DEFAULT_TRANSITION_SECONDS.get(transition_type, 0.0)

    if transition_class == "continuous_action":
        visual_dependency = "screenplay_continuous_motion_requirement"
        picture_edit = "cinematography_selected_reference_or_cut"
        audio_edit = "native_clean_cut"
        media_dependency = "storyboard_decides"
    elif transition_class == "motivated_cut":
        visual_dependency = "same_scene_location_master_context"
        picture_edit = "hard_cut"
        audio_edit = "native_continuity_declick"
        media_dependency = "none"
    elif transition_class == "scene_change":
        visual_dependency = "new_scene_location_master_context"
        picture_edit = "hard_cut"
        audio_edit = "native_clean_cut"
        media_dependency = "none"
    else:
        visual_dependency = "clip_local_transition_handle"
        media_dependency = "none"
        if transition_type == "dissolve":
            picture_edit = "dissolve"
            audio_edit = "equal_power_acrossfade"
        elif transition_type == "fade":
            picture_edit = "fade"
            audio_edit = "equal_power_acrossfade"
        else:
            picture_edit = "baked_effect"
            audio_edit = "native_clean_cut"

    return {
        "schema_version": "boundary-execution/v1",
        "authored_transition_type": transition_type,
        "transition_class": transition_class,
        "visual_dependency_mode": visual_dependency,
        "media_dependency": media_dependency,
        "picture_edit_mode": picture_edit,
        "audio_edit_mode": audio_edit,
        "transition_duration_seconds": duration,
        "audio_edge_fade_seconds": (
            0.01 if audio_edit == "native_continuity_declick" else 0.0
        ),
        "allowed_visual_changes": (
            list(MOTIVATED_CUT_ALLOWED_CHANGES)
            if transition_class in {"motivated_cut", "scene_change"}
            else []
        ),
        "required_semantic_continuity_checks": list(SEMANTIC_CONTINUITY_CHECKS),
    }


def incoming_boundary_mode(
    story_plans: list[dict[str, Any]], segment_index: int
) -> str:
    """Derive one Segment's incoming semantic boundary directly from screenplay plans."""

    if not 0 <= segment_index < len(story_plans):
        raise BoundaryExecutionError("Segment index is outside screenplay coverage")
    if segment_index == 0:
        return "opening"
    predecessor = story_plans[segment_index - 1]
    current = story_plans[segment_index]
    return build_boundary_execution(
        transition_design=predecessor["transition_design_json"],
        from_scene_id=predecessor["scene_id"],
        to_scene_id=current["scene_id"],
        successor_continuity_mode=current["continuity_mode"],
    )["transition_class"]


def build_story_plan_boundaries(
    story_plans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive ordered executable boundaries without creating an intermediate file."""

    boundaries: list[dict[str, Any]] = []
    for index in range(1, len(story_plans)):
        predecessor = story_plans[index - 1]
        current = story_plans[index]
        boundaries.append(
            {
                "from": predecessor["segment_id"],
                "to": current["segment_id"],
                "transition_design": predecessor["transition_design_json"],
                "execution": build_boundary_execution(
                    transition_design=predecessor["transition_design_json"],
                    from_scene_id=predecessor["scene_id"],
                    to_scene_id=current["scene_id"],
                    successor_continuity_mode=current["continuity_mode"],
                ),
                "native_audio_dependency": "none",
            }
        )
    return boundaries


def topological_waves(
    segment_ids: list[str], edges: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Build stable topological waves for immediate predecessor dependencies."""

    predecessors: dict[str, set[str]] = {segment_id: set() for segment_id in segment_ids}
    successors: dict[str, set[str]] = {segment_id: set() for segment_id in segment_ids}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source not in predecessors or target not in predecessors or source == target:
            raise BoundaryExecutionError(f"Invalid DAG edge: {edge}")
        predecessors[target].add(source)
        successors[source].add(target)

    remaining = set(segment_ids)
    completed: set[str] = set()
    result: list[dict[str, Any]] = []
    wave = 0
    while remaining:
        ready = [
            segment_id
            for segment_id in segment_ids
            if segment_id in remaining and predecessors[segment_id] <= completed
        ]
        if not ready:
            raise BoundaryExecutionError("Generation DAG contains a cycle")
        result.append({"wave": wave, "segment_ids": ready})
        completed.update(ready)
        remaining.difference_update(ready)
        wave += 1
    return result
