from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video import character_performance_map as performance_map  # noqa: E402
from story_video.screenplay_contract import (  # noqa: E402
    DIALOGUE_TURN_ALLOWANCE_SECONDS,
    DIALOGUE_WORDS_PER_SECOND,
    MINIMUM_ACTION_REACTION_SECONDS,
    fixed_screenplay_prompt,
)


class RoleAssetScopeTests(unittest.TestCase):
    def test_silent_member_type_cannot_repeat_dialogue_portrait_species(self) -> None:
        self.assertEqual(
            performance_map._dialogue_identity_named_in_member_type(
                "anonymous elephants distinct from the hero", ["Elephant", "Zebra"]
            ),
            "Elephant",
        )
        self.assertEqual(
            performance_map._dialogue_identity_named_in_member_type(
                "small green forest songbirds", ["Elephant", "Zebra"]
            ),
            None,
        )

    def test_fast_gate_projects_only_asset_bearing_role_scope(self) -> None:
        authority = {
            "performance_entities": [
                {
                    "entity_id": "hero",
                    "screenplay_character_name_en": "Hero",
                    "entity_kind": "individual",
                    "group_role_type_en": "none",
                    "ensemble_member_types_en": [],
                },
                {
                    "entity_id": "crowd",
                    "screenplay_character_name_en": "Crowd",
                    "entity_kind": "anonymous_ensemble",
                    "group_role_type_en": "village_witnesses",
                    "ensemble_member_types_en": ["adult village witnesses"],
                },
            ],
            "scene_segment_calls": [
                {
                    "scene_id": "scene-001",
                    "segment_id": "segment-001",
                    "calls": [
                        {
                            "entity_id": "hero",
                            "presence_mode": "on_screen",
                            "speaks": True,
                            "line_ids": ["L-001"],
                            "group_role_type_en": "none",
                        },
                        {
                            "entity_id": "crowd",
                            "presence_mode": "on_screen",
                            "speaks": False,
                            "line_ids": [],
                            "group_role_type_en": "village_witnesses",
                        },
                    ],
                }
            ],
        }
        screenplay = {
            "environments": [
                {
                    "environment_id": "environment-001",
                    "scene_ids_json": ["scene-001"],
                }
            ],
            "scenes": [
                {
                    "scene_id": "scene-001",
                    "primary_time_en": "day",
                    "primary_place_en": "village square",
                    "segment_ids_json": ["segment-001"],
                }
            ],
        }
        with patch.object(
            performance_map, "load_character_performance_map", return_value=authority
        ), patch.object(
            performance_map, "load_screenplay_file", return_value=screenplay
        ):
            result = performance_map.role_asset_scope_gate(Path("/tmp/task"))

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["image_asset_generation"], "UNLOCKED")
        self.assertEqual(
            result["detailed_screenplay_review"],
            "COMPLETED_IN_WRITER_PREFLIGHT",
        )
        self.assertEqual(
            [item["entity_id"] for item in result["dialogue_entities"]], ["hero"]
        )
        self.assertEqual(
            result["silent_role_groups"],
            [
                {
                    "group_role_type_en": "village_witnesses",
                    "entity_ids": ["crowd"],
                    "member_types_en": ["adult village witnesses"],
                }
            ],
        )
        self.assertEqual(
            result["segment_scopes"][0]["static_reference_image_count"], 3
        )

    def test_generation_prompt_contains_complete_release_requirements(self) -> None:
        _, generation_prompt = fixed_screenplay_prompt()

        for heading in (
            "## Task",
            "## Input Contract",
            "## Decision Rules",
            "## Output Contract",
            "## Release Gate",
        ):
            self.assertEqual(generation_prompt.count(heading), 1)
        self.assertIn("TASK_DIR/screenplay-writer/screenplay.md", generation_prompt)
        self.assertIn("children's educational", generation_prompt)
        self.assertIn("screenplay-segment-contract.md", generation_prompt)
        self.assertIn("horizontal", generation_prompt)
        self.assertIn("large-screen film script", generation_prompt)
        self.assertIn("author the complete chain required by the contract", generation_prompt)
        self.assertIn("BGM", generation_prompt)
        self.assertIn("Validator behavior is governed", generation_prompt)
        self.assertIn("present_at_open", generation_prompt)
        self.assertIn("First visibility", generation_prompt)
        self.assertIn("landing result", generation_prompt)
        self.assertIn("speech gate", generation_prompt)
        self.assertIn("Understand the film before authoring tables", generation_prompt)
        self.assertIn("state_match", generation_prompt)
        self.assertIn("continuous_motion", generation_prompt)
        self.assertIn("no timing notation is mandatory", generation_prompt)
        self.assertIn("a fixed Shot count", " ".join(generation_prompt.split()))
        self.assertIn(
            f"dialogue_words / {DIALOGUE_WORDS_PER_SECOND}", generation_prompt
        )
        self.assertIn(
            f"dialogue_line_count * {DIALOGUE_TURN_ALLOWANCE_SECONDS}",
            generation_prompt,
        )
        self.assertIn(f"+ {MINIMUM_ACTION_REACTION_SECONDS}", generation_prompt)
        for removed_restriction in (
            "45% for `action_led`",
            "72% for `dialogue_led`",
            "at most three per Scene Unit",
        ):
            self.assertNotIn(removed_restriction, generation_prompt)
        for stale_clause in (
            "spec screenplay",
            "audio-timeline.json",
            "Do not manufacture text merely to satisfy a column",
            "not generators",
        ):
            self.assertNotIn(stale_clause, generation_prompt)

if __name__ == "__main__":
    unittest.main()
