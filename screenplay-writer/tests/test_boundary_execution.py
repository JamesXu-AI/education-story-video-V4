from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.boundary_execution import (  # noqa: E402
    BoundaryExecutionError,
    build_boundary_execution,
    build_story_plan_boundaries,
)
from story_video.screenplay_contract import (  # noqa: E402
    FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE,
    INHERITED_VISUAL_PHASE_RE,
    validate_adjacent_visual_boundary_contract,
    validate_cinematic_segment_contract,
)
from story_video.runtime_support import StoryVideoError  # noqa: E402


def transition(kind: str = "action_cut") -> dict[str, str]:
    return {
        "type": kind,
        "reason_en": "The cut preserves one accelerating reversal.",
    }


def cinematic_scene_contract() -> dict[str, object]:
    return {
        "scene_id": "scene-001",
        "scene_purpose": "Force the animals to choose between obedience and resistance.",
        "character_objective": "Lion wants visible submission from the gathered animals.",
        "obstacle": "Elephant refuses to yield the path through the clearing.",
        "power_relationship": "Lion controls the central path while Elephant guards the forest exit.",
        "turning_point": "Elephant steps across the path before Lion can advance.",
        "outcome": "Lion loses uncontested control and the animals gain an escape route.",
        "visual_progression": "A blocked crowd separates into a retreating flank and a protected corridor.",
        "exit_impulse": "A branch snaps beyond the open corridor and pulls attention deeper into the forest.",
    }


def cinematic_beat(block_indexes: list[int]) -> dict[str, object]:
    return {
        "beat_id": "BEAT-001A",
        "narrative_change": "Lion's command stops controlling the whole clearing.",
        "active_character": "Elephant becomes the active resisting character.",
        "physical_objective": "Elephant must keep Lion away from the retreat path.",
        "visible_action": "Elephant crosses the path and lowers one forefoot.",
        "important_reaction": "The nearest animals split toward cover instead of answering.",
        "spatial_change": "The center closes while a side corridor opens.",
        "dialogue_or_sound": "Lion's command is interrupted by feet scraping backward.",
        "entry_state": "Lion owns the center and blocks every route.",
        "exit_state": "Elephant owns the center and protects one route.",
        "action_subject": "Elephant drives the blocking action in this beat.",
        "reaction_subject": "Lion's arrested advance carries the key reaction.",
        "supporting_group": "Nearby animals retreat in two uneven waves.",
        "atmosphere_presence": "Hidden animals remain present through broken branches and breath.",
        "visual_focus": "Elephant's crossing changes control of the path.",
        "block_indexes": block_indexes,
    }


class BoundaryExecutionTests(unittest.TestCase):
    def test_cinematic_screenplay_gate_rejects_stage_tableau_input(self) -> None:
        blocks = [
            {
                "type": "action",
                "text_en": "All the animals stand in a semicircle before Lion while waiting to speak.",
            }
        ]
        with self.assertRaisesRegex(StoryVideoError, "stage-tableau"):
            validate_cinematic_segment_contract(
                segment_id="segment-001",
                scene_id="scene-001",
                scene_contract=cinematic_scene_contract(),
                dramatic_beats=[cinematic_beat([1])],
                blocks=blocks,
            )

    def test_cinematic_screenplay_gate_accepts_action_led_ensemble(self) -> None:
        blocks = [
            {
                "type": "action",
                "text_en": "Elephant crosses the path as smaller animals retreat behind roots and brush.",
            }
        ]
        validate_cinematic_segment_contract(
            segment_id="segment-001",
            scene_id="scene-001",
            scene_contract=cinematic_scene_contract(),
            dramatic_beats=[cinematic_beat([1])],
            blocks=blocks,
        )

    def test_scene_change_can_be_independent(self) -> None:
        result = build_boundary_execution(
            transition_design=transition(),
            from_scene_id="scene-001",
            to_scene_id="scene-002",
            successor_incoming_visual_requirement="independent",
        )

        self.assertEqual(result["schema_version"], "boundary-execution/v2")
        self.assertEqual(result["transition_class"], "scene_change")
        self.assertEqual(result["media_dependency"], "none")
        self.assertEqual(result["continuation_reference_mode"], "none")

    def test_same_scene_independent_is_rejected(self) -> None:
        with self.assertRaisesRegex(BoundaryExecutionError, "must be serial"):
            build_boundary_execution(
                transition_design=transition("reaction_cut"),
                from_scene_id="scene-001",
                to_scene_id="scene-001",
                successor_incoming_visual_requirement="independent",
            )

    def test_missing_visual_requirement_cannot_default_to_independent(self) -> None:
        with self.assertRaisesRegex(BoundaryExecutionError, "authored explicitly"):
            build_boundary_execution(
                transition_design=transition("reaction_cut"),
                from_scene_id="scene-001",
                to_scene_id="scene-001",
            )

    def test_state_match_is_not_downgraded_to_no_dependency(self) -> None:
        result = build_boundary_execution(
            transition_design=transition("reaction_cut"),
            from_scene_id="scene-001",
            to_scene_id="scene-001",
            successor_incoming_visual_requirement="state_match",
        )

        self.assertEqual(result["transition_class"], "motivated_cut")
        self.assertEqual(
            result["visual_dependency_mode"],
            "screenplay_state_match_requirement",
        )
        self.assertEqual(
            result["media_dependency"],
            "predecessor_provider_last_frame_reference_image",
        )
        self.assertEqual(
            result["continuation_reference_mode"], "first_frame_reference"
        )
        self.assertEqual(
            result["reference_authority"],
            "soft_reference_image_not_strict_first_frame",
        )

    def test_scene_return_dissolve_can_keep_state_match_authority(self) -> None:
        result = build_boundary_execution(
            transition_design=transition("dissolve"),
            from_scene_id="scene-002",
            to_scene_id="scene-003",
            successor_incoming_visual_requirement="state_match",
        )

        self.assertEqual(result["transition_class"], "designed_transition")
        self.assertEqual(result["picture_edit_mode"], "dissolve")
        self.assertEqual(
            result["visual_dependency_mode"],
            "screenplay_state_match_requirement",
        )
        self.assertEqual(
            result["media_dependency"],
            "storyboard_decides_nonadjacent_state_authority",
        )
        self.assertEqual(result["continuation_reference_mode"], "state_reference")

    def test_continuous_motion_is_a_reachable_serial_visual_contract(self) -> None:
        result = build_boundary_execution(
            transition_design=transition(),
            from_scene_id="scene-001",
            to_scene_id="scene-001",
            successor_incoming_visual_requirement="continuous_motion",
        )

        self.assertEqual(result["transition_class"], "continuous_action")
        self.assertEqual(
            result["visual_dependency_mode"],
            "screenplay_continuous_motion_requirement",
        )
        self.assertEqual(result["media_dependency"], "predecessor_video")
        self.assertEqual(
            result["continuation_reference_mode"],
            "predecessor_video_reference",
        )
        self.assertEqual(result["picture_edit_mode"], "hard_cut")

    def test_continuous_motion_cannot_cross_scene_boundary(self) -> None:
        with self.assertRaisesRegex(BoundaryExecutionError, "Scene boundary"):
            build_boundary_execution(
                transition_design=transition(),
                from_scene_id="scene-001",
                to_scene_id="scene-002",
                successor_incoming_visual_requirement="continuous_motion",
            )

    def test_story_plan_compilation_preserves_state_match(self) -> None:
        plans = [
            {
                "segment_id": "segment-001",
                "scene_id": "scene-001",
                "transition_design_json": transition("reaction_cut"),
                "incoming_visual_requirement": "independent",
            },
            {
                "segment_id": "segment-002",
                "scene_id": "scene-001",
                "transition_design_json": transition("final_end"),
                "incoming_visual_requirement": "state_match",
            },
        ]

        boundaries = build_story_plan_boundaries(plans)

        self.assertEqual(
            boundaries[0]["execution"]["incoming_visual_requirement"],
            "state_match",
        )
        self.assertEqual(
            boundaries[0]["execution"]["media_dependency"],
            "predecessor_provider_last_frame_reference_image",
        )
        self.assertEqual(
            boundaries[0]["execution"]["continuation_reference_mode"],
            "first_frame_reference",
        )

    def test_visual_inheritance_language_is_allowed_but_audio_split_is_not(self) -> None:
        visual = (
            "The successor continues the same unfinished movement, facing, and "
            "camera phase from the boundary."
        )
        audio = "The same dialogue carries across the boundary."

        self.assertIsNone(FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE.search(visual))
        self.assertIsNotNone(INHERITED_VISUAL_PHASE_RE.search(visual))
        self.assertIsNotNone(FORBIDDEN_CROSS_CLIP_DEPENDENCY_RE.search(audio))

    def test_screenplay_contract_accepts_explicit_continuous_visual_phase(self) -> None:
        predecessor = {
            "scene_id": "scene-001",
            "transition_design_json": {
                "type": "action_cut",
                "outgoing_visible_en": "The paw is still moving left.",
                "incoming_visible_en": (
                    "The successor inherits the same motion and Lion facing."
                ),
                "action_link_en": "One unfinished action phase continues.",
                "spatial_link_en": "The same facing and screen direction persist.",
            },
        }
        current = {
            "scene_id": "scene-001",
            "incoming_visual_requirement": "continuous_motion",
        }

        validate_adjacent_visual_boundary_contract(
            segment_id="segment-002",
            predecessor_plan=predecessor,
            current_plan=current,
        )

    def test_screenplay_contract_rejects_same_scene_independent(self) -> None:
        predecessor = {
            "scene_id": "scene-001",
            "transition_design_json": {"type": "reaction_cut"},
        }
        current = {
            "scene_id": "scene-001",
            "incoming_visual_requirement": "independent",
        }

        with self.assertRaisesRegex(StoryVideoError, "cannot be independent"):
            validate_adjacent_visual_boundary_contract(
                segment_id="segment-002",
                predecessor_plan=predecessor,
                current_plan=current,
            )

    def test_screenplay_contract_accepts_same_scene_first_frame_reference(self) -> None:
        predecessor = {
            "scene_id": "scene-001",
            "transition_design_json": {"type": "reaction_cut"},
        }
        current = {
            "scene_id": "scene-001",
            "incoming_visual_requirement": "state_match",
        }

        validate_adjacent_visual_boundary_contract(
            segment_id="segment-002",
            predecessor_plan=predecessor,
            current_plan=current,
        )

    def test_screenplay_contract_rejects_unexplained_continuous_motion_label(self) -> None:
        predecessor = {
            "scene_id": "scene-001",
            "transition_design_json": {
                "type": "action_cut",
                "outgoing_visible_en": "The first beat remains readable.",
                "incoming_visible_en": "The next beat begins.",
                "action_link_en": "The second event follows the first.",
                "spatial_link_en": "Both occur in the clearing.",
            },
        }
        current = {
            "scene_id": "scene-001",
            "incoming_visual_requirement": "continuous_motion",
        }

        with self.assertRaisesRegex(StoryVideoError, "must name the inherited"):
            validate_adjacent_visual_boundary_contract(
                segment_id="segment-002",
                predecessor_plan=predecessor,
                current_plan=current,
            )


if __name__ == "__main__":
    unittest.main()
