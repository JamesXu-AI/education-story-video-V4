"""Production-design authority for the current default visual profile."""

from __future__ import annotations

import re
from typing import Any


VISUAL_STYLE_PROFILE = "soft_cute_3d_healing_animation"

NEGATIVE_CONSTRAINT_IDS = (
    "brand_studio_movie_creator_renderer_or_named_ip_style_shortcut",
    "text_logo_or_watermark",
    "duplicate_clone_or_extra_character",
    "anatomy_deformation_or_visible_limb_joint",
    "plastic_gloss_or_mirror_like_material",
    "sharp_corner_or_unsafe_prop_contact",
    "cold_dirty_gray_palette",
    "hard_overhead_back_or_rim_light",
    "harsh_shadow",
    "chaotic_camera_rapid_rotation_or_sudden_zoom",
    "multiple_competing_primary_actions_or_camera_moves",
    "large_uncontrolled_action",
    "low_resolution_blur_flicker_or_background_collapse",
)

POSITIVE_LOOK_LOCKS = (
    "Use an original soft, cute, healing 3D animation look with a warm, low-saturation palette and a clean, uncluttered performance space.",
    "Keep each principal character's head-to-body ratio between 1:1.5 and 1:2; eyes occupy 25-35% of the face with round wet highlights; limbs are short, round and thick with no visible joints.",
    "Every character asset is a full-body final-look portrait; show props or accessories only when production design has selected them for current story, identity or continuity needs. The face, gaze and posture show motivated anthropomorphic expression, attention and thought rather than a neutral catalogue pose.",
    "Every lead, supporting role and other dialogue-owning main story character uses an upright bipedal actor body standing on two legs; non-human characters retain unmistakable species head, surface, markings, ears, tail, trunk, wings or other defining anatomy.",
    "Use rounded silhouettes, generous bevels and soft curves for characters, sets and props; preserve graspable contact zones and avoid every sharp corner.",
    "Render plush as high-roughness matte, ceramic and wood as medium-roughness matte, and creamy surfaces as low-roughness but non-reflective; never use plastic gloss.",
    "Light with one soft diffused key at 45 degrees front-side and a weak opposite fill; use no cold, hard, overhead, back or rim light and no harsh shadow.",
    "Use shallow depth of field with an f/1.8-f/2.8 aperture intent: the performance subject is sharp and the background is softly separated.",
    "Keep character colors, costume and accessory placement, pattern placement, eye shape and highlight count, ears, tail and body proportions consistent with current production-design assets.",
    "Use one primary action and one primary camera strategy in the Segment; for object interaction preserve look, approach, contact, object feedback and emotional change in that order.",
)

NEGATIVE_PROMPT_LOCKS = (
    "Do not use any brand, studio, movie, franchise, creator, renderer or named-IP style shortcut.",
    "No text, logo or watermark; no duplicate, clone, extra character or unexplained population change.",
    "No anatomy deformation, visible limb joints, extra, duplicated, missing, fused, detached or hybrid limbs, identity drift, costume drift or pattern drift.",
    "No neutral-model character portrait, blank wildlife stare, fixed catalogue smile, missing thought, or quadrupedal main story character; a deliberately prop-free final-look portrait is valid.",
    "No plastic gloss, mirror-like material, sharp corner, unsafe prop contact or contact failure.",
    "No cold dirty-gray palette, hard light, overhead key, back light, rim light or harsh shadow.",
    "No chaotic camera, rapid rotation, sudden zoom, multiple competing primary actions or camera moves, or large uncontrolled action.",
    "No low-resolution softness, accidental blur, flicker or background collapse.",
)

# These are prohibited prompt shortcuts, not an exhaustive list of protected names.
# The generic phrase check below also rejects direct "in the style of ..." shortcuts.
_PROHIBITED_SHORTCUT_RE = re.compile(
    r"(?:\b(?:pixar|disney|dreamworks|blender|cycles)\b|"
    r"\b(?:in|like|copy|imitate|mimic)\s+(?:the\s+)?style\s+of\b)",
    re.IGNORECASE,
)


def visual_style_contract() -> dict[str, Any]:
    """Return the canonical JSON-serializable visual-style contract."""

    return {
        "profile_id": VISUAL_STYLE_PROFILE,
        "character_geometry": {
            "head_to_body_ratio_min": 1.5,
            "head_to_body_ratio_max": 2.0,
            "eye_face_coverage_percent_min": 25,
            "eye_face_coverage_percent_max": 35,
            "limb_shape": "short_round_thick_no_visible_joints",
            "edge_shape": "rounded_beveled_no_sharp_corners",
        },
        "material_response": {
            "plush": "high_roughness_matte",
            "ceramic_and_wood": "medium_roughness_matte",
            "creamy_surface": "low_roughness_non_reflective",
            "plastic_gloss": "forbidden",
        },
        "palette_and_space": {
            "palette": "low_saturation_warm",
            "scene_density": "clean_uncluttered_clear_performance_space",
        },
        "lighting": {
            "key_angle_degrees": 45,
            "key_position": "front_side",
            "key_quality": "soft_diffused",
            "opposite_fill": "weak",
            "overhead_key": "forbidden",
            "back_or_rim_light": "forbidden",
            "harsh_shadow": "forbidden",
        },
        "camera": {
            "aperture_f_stop_min": 1.8,
            "aperture_f_stop_max": 2.8,
            "depth_of_field": "shallow_subject_sharp_background_soft",
            "primary_action_count": 1,
            "primary_camera_strategy_count": 1,
        },
        "interaction_beats": [
            "look",
            "approach",
            "contact",
            "object_feedback",
            "emotional_change",
        ],
        "negative_constraint_ids": list(NEGATIVE_CONSTRAINT_IDS),
    }


def contains_prohibited_style_shortcut(value: Any) -> bool:
    """Detect prohibited named-style shortcuts in any nested authored value."""

    if isinstance(value, str):
        return _PROHIBITED_SHORTCUT_RE.search(value) is not None
    if isinstance(value, dict):
        return any(contains_prohibited_style_shortcut(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_prohibited_style_shortcut(item) for item in value)
    return False


def assert_visual_style_contract(value: Any, *, label: str) -> dict[str, Any]:
    """Reject any weakened, extended or partially copied style contract."""

    expected = visual_style_contract()
    if value != expected:
        raise ValueError(f"{label} must exactly match {VISUAL_STYLE_PROFILE}.")
    if contains_prohibited_style_shortcut(value):
        raise ValueError(f"{label} contains a prohibited named-style shortcut.")
    return expected
