from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_initial_production_design import (  # noqa: E402
    _final_catalog,
    _final_location_packages,
    _jobs_from_model_plan,
)
from story_video.production_design_plan import (  # noqa: E402
    PURE_WHITE_BACKGROUND_EN,
    STYLE_AUTHORITY_EN,
    render_generation_prompt,
)


class ExplicitPlanExecutionTests(unittest.TestCase):
    def test_job_copies_exact_model_prompt_and_reference_order(self) -> None:
        prompt = {
            "intent_en": "Create one exact asset.",
            "subject_en": "A model-authored subject.",
            "background_en": PURE_WHITE_BACKGROUND_EN,
            "composition_en": "A model-authored composition.",
            "continuity": {
                "reference_asset_ids": ["prop-a", "actor-a"],
                "locks_en": ["A model-authored lock."],
            },
            "style_en": STYLE_AUTHORITY_EN,
            "exclusions_en": ["A model-authored exclusion."],
        }
        plan = {
            "characters": [],
            "ensemble_rosters": [],
            "props": [
                {
                    "type": "prop",
                    "asset_id": "asset-a",
                    "media_path": "assets/props/asset-a/image.png",
                    "generation_prompt": prompt,
                }
            ],
            "costumes": [],
            "locations": [],
        }

        job = _jobs_from_model_plan(plan)[0]

        self.assertEqual(job["prompt"], render_generation_prompt(prompt))
        self.assertEqual(job["references"], ["prop-a", "actor-a"])
        self.assertEqual(job["depends_on"], ["prop-a", "actor-a"])

    def test_builder_contains_no_scene_cast_or_prompt_deriver(self) -> None:
        source = (SCRIPT_ROOT / "build_initial_production_design.py").read_text(
            encoding="utf-8"
        )
        for removed in (
            "_scene_role_assets_by_location",
            "_role_asset_ids_by_entity",
            "silent_group_portrait_brief",
            "_aesthetic_prompt",
            "TASK-AUTHORED",
            "Generate one full-body",
        ):
            self.assertNotIn(removed, source)

    def test_location_semantics_are_copied_without_python_authorship(self) -> None:
        location = {
            "type": "location_master",
            "location_id": "loc-room",
            "scene_ids": ["scene-001"],
            "description_en": "One stable room.",
            "included_prop_ids": [],
            "embedded_npc_asset_ids": ["background-neighbors"],
            "independent_performer_asset_ids": ["actor-a"],
            "fixed_set_elements_en": [
                "A low wooden table remains fixed between both chairs."
            ],
            "environment_state_en": "Quiet evening room.",
            "lighting_state_en": "Warm practical light.",
            "palette_materials_en": "Cream textile and matte wood.",
            "topology": {
                "zones": [],
                "connections": [],
                "entrances_exits": [],
                "fixed_obstacles": [],
                "fixed_prop_placements": [],
            },
            "landmarks": [{"landmark_id": "table"}],
            "media_path": "assets/locations/room/master.png",
            "generation_prompt": {},
        }
        plan = {
            "characters": [],
            "ensemble_rosters": [],
            "props": [],
            "costumes": [],
            "locations": [location],
        }
        visual = {
            "loc-room": {
                "path": "assets/locations/room/master.png",
                "uri": "https://example.test/room.png",
            }
        }

        catalog = _final_catalog(plan, visuals=visual, voice_references={})
        package = _final_location_packages(plan)

        self.assertEqual(
            catalog["assets"]["loc-room"]["fixed_set_elements_en"],
            location["fixed_set_elements_en"],
        )
        self.assertEqual(
            catalog["assets"]["loc-room"]["embedded_npc_asset_ids"],
            ["background-neighbors"],
        )
        self.assertEqual(
            catalog["assets"]["loc-room"]["independent_performer_asset_ids"],
            ["actor-a"],
        )
        self.assertEqual(
            package["locations"][0]["fixed_set_elements_en"],
            location["fixed_set_elements_en"],
        )
        self.assertEqual(
            package["locations"][0]["embedded_npc_asset_ids"],
            ["background-neighbors"],
        )
        self.assertEqual(
            package["locations"][0]["independent_performer_asset_ids"],
            ["actor-a"],
        )
        self.assertEqual(package["locations"][0]["topology"], location["topology"])


if __name__ == "__main__":
    unittest.main()
