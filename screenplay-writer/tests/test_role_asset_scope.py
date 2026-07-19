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
from compile_audio_timeline import validate_dialogue_occupancy  # noqa: E402
from story_video.runtime_support import StoryVideoError  # noqa: E402


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
                    "entity_label_en": "Brave Hero",
                    "entity_kind": "individual",
                    "group_role_type_en": "none",
                    "ensemble_member_types_en": [],
                },
                {
                    "entity_id": "crowd",
                    "screenplay_character_name_en": "Crowd",
                    "entity_label_en": "Village Crowd",
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
                            "dialogue_refs": [{"block_index": 2}],
                            "group_role_type_en": "none",
                        },
                        {
                            "entity_id": "crowd",
                            "presence_mode": "on_screen",
                            "speaks": False,
                            "dialogue_refs": [],
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

        self.assertIn("dialogue_turn_count <= 3", generation_prompt)
        self.assertIn(
            "一个实体只要在任意 Segment 说过一句话", generation_prompt
        )
        self.assertIn("static_reference_image_count", generation_prompt)
        self.assertIn("dramatic_workload", generation_prompt)
        self.assertIn("这些检查是编剧协作本身的发布责任", generation_prompt)
        self.assertIn("至少约 0.8 秒", generation_prompt)
        self.assertIn(
            f"dialogue_words / {DIALOGUE_WORDS_PER_SECOND}", generation_prompt
        )
        self.assertIn(
            f"dialogue_turn_count * {DIALOGUE_TURN_ALLOWANCE_SECONDS}",
            generation_prompt,
        )
        self.assertIn(
            f"+ {MINIMUM_ACTION_REACTION_SECONDS}", generation_prompt
        )
        self.assertIn("ensemble_member_types_en", generation_prompt)
        self.assertIn("老虎不授权家猫", generation_prompt)
        for shared_threshold in (
            "动作主导段：45%；",
            "对白与动作混合段：60%；",
            "对白主导段：72%。",
        ):
            self.assertIn(shared_threshold, generation_prompt)

    def test_dialogue_occupancy_uses_declared_workload_limit(self) -> None:
        windows = [
            {"block_type": "action", "start_seconds": 0.0, "end_seconds": 2.0},
            {"block_type": "dialogue", "start_seconds": 2.0, "end_seconds": 8.5},
            {"block_type": "action", "start_seconds": 8.5, "end_seconds": 10.0},
        ]
        occupancy, limit = validate_dialogue_occupancy(
            segment_id="segment-001",
            dramatic_workload="dialogue_led",
            duration_seconds=10.0,
            block_windows=windows,
        )
        self.assertAlmostEqual(occupancy, 0.65)
        self.assertEqual(limit, 0.72)
        with self.assertRaisesRegex(StoryVideoError, "exceeds the 60%"):
            validate_dialogue_occupancy(
                segment_id="segment-001",
                dramatic_workload="mixed_dialogue_action",
                duration_seconds=10.0,
                block_windows=windows,
            )

if __name__ == "__main__":
    unittest.main()
