from __future__ import annotations

from pathlib import Path
import sys
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_catalog import ASSET_TYPES  # noqa: E402
import story_video.location_continuity_packages as location_packages  # noqa: E402
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

    def test_python_does_not_derive_storyboard_authority_fields(self) -> None:
        self.assertFalse(
            hasattr(location_packages, "location_continuity_authority_for_storyboard")
        )
        self.assertFalse(hasattr(location_packages, "location_models_by_id"))


if __name__ == "__main__":
    unittest.main()
