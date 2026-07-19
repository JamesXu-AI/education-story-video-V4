from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.production_design_plan import (  # noqa: E402
    PLAN_RELATIVE_PATH,
    load_production_design_plan,
)


class ProductionDesignPlanTests(unittest.TestCase):
    def test_loader_accepts_arbitrary_task_semantics_without_named_story_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / PLAN_RELATIVE_PATH
            path.parent.mkdir(parents=True)
            payload = {
                "contract": "production-design-plan",
                "characters": [
                    {
                        "entity_id": "navigator",
                        "design_description_en": "A precise task-authored navigator design.",
                        "body_topology": {
                            "body_plan_en": "upright bipedal human actor",
                            "total_limb_count": 4,
                            "limb_sets": [
                                {
                                    "kind_en": "legs",
                                    "count": 2,
                                    "function_en": "grounded locomotion and support",
                                },
                                {
                                    "kind_en": "arms",
                                    "count": 2,
                                    "function_en": "gesture and prop handling",
                                },
                            ],
                            "non_limb_appendages": [],
                            "topology_lock_en": "Exactly two legs and two arms; four total limbs.",
                        },
                        "portrait_prop_ids": ["prop-compass"],
                        "voice_description_en": "A focused adult navigator voice.",
                        "voice_sample_text_en": "The tide is turning beyond the harbor wall.",
                        "voice_speech_rate": 5,
                    }
                ],
                "props": [
                    {
                        "asset_id": "prop-compass",
                        "description_en": "A brass compass with one stable needle design.",
                    }
                ],
                "costumes": [],
                "locations": [
                    {
                        "location_id": "loc-harbor",
                        "scene_ids": ["scene-001"],
                        "description_en": "One stable empty harbor set.",
                        "generation_prompt_en": "An empty navigable harbor at dawn.",
                        "fixed_prop_ids": [],
                        "environment_state_en": "Stable dry harbor weather.",
                        "lighting_state_en": "Soft dawn light from camera left.",
                        "palette_materials_en": "Weathered wood and muted blue stone.",
                        "topology": {},
                        "landmarks": [],
                    }
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            performance = {
                "performance_entities": [{"entity_id": "navigator"}],
                "scene_segment_calls": [
                    {"calls": [{"entity_id": "navigator", "speaks": True}]}
                ],
            }
            screenplay = {"scenes": [{"scene_id": "scene-001"}]}

            plan = load_production_design_plan(
                root, performance=performance, screenplay=screenplay
            )

            self.assertEqual(plan["characters"][0]["entity_id"], "navigator")
            self.assertEqual(plan["props"][0]["asset_id"], "prop-compass")
            self.assertEqual(plan["locations"][0]["location_id"], "loc-harbor")

    def test_generic_builder_contains_no_current_story_identity_branch(self) -> None:
        source = (
            SCRIPT_ROOT.parent / "scripts" / "build_initial_production_design.py"
        ).read_text(encoding="utf-8").casefold()
        for forbidden in (
            "uthman",
            "grandfather",
            "lion",
            "elephant",
            "zebra",
            "mosquito",
            "forest-throne",
            "forest-clearing",
            "saudi-home",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
