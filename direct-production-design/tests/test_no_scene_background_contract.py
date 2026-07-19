from __future__ import annotations

from pathlib import Path
import sys
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_catalog import ASSET_TYPES  # noqa: E402
from story_video.location_continuity_packages import (  # noqa: E402
    location_continuity_authority_for_storyboard,
)
from story_video.visual_asset_generation import ASSET_KINDS  # noqa: E402


class NoSceneBackgroundContractTests(unittest.TestCase):
    def test_scene_background_is_not_an_asset_or_generation_kind(self) -> None:
        self.assertNotIn("scene_background", ASSET_TYPES)
        self.assertNotIn("scene_background", ASSET_KINDS)
        self.assertNotIn("location_continuity_view", ASSET_TYPES)
        self.assertNotIn("location_continuity_view", ASSET_KINDS)

    def test_scene_background_generators_do_not_exist(self) -> None:
        self.assertFalse((SCRIPT_ROOT / "build_scene_background_request.py").exists())
        self.assertFalse(
            (SCRIPT_ROOT / "execute_scene_background_requests.py").exists()
        )
        self.assertFalse(
            (SCRIPT_ROOT / "story_video/scene_background_packages.py").exists()
        )
        self.assertFalse(
            (SCRIPT_ROOT / "build_location_continuity_packages.py").exists()
        )

    def test_storyboard_environment_authority_uses_location_master(self) -> None:
        authority = location_continuity_authority_for_storyboard(
            {"scene_id": "scene-001", "segment_id": "segment-001"},
            {
                "locations": [
                    {
                        "location_id": "location-001",
                        "scene_ids": ["scene-001"],
                        "environment_state_en": "Stable room.",
                        "lighting_state_en": "Stable daylight.",
                        "palette_materials_en": "Warm matte plaster.",
                        "topology": {"zones": [{"zone_id": "room"}]},
                        "landmarks": [
                            {
                                "landmark_id": "door",
                                "world_relationship_en": "Door stays world-right.",
                            }
                        ],
                    }
                ]
            },
        )
        self.assertEqual(
            authority["reference_mode"],
            "location_master_image_with_topology_text",
        )
        self.assertEqual(authority["location_master_asset_id"], "location-001")
        self.assertNotIn("selected_view_ids", authority)
        self.assertNotIn("screen_geography", authority)


if __name__ == "__main__":
    unittest.main()
