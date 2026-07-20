from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_initial_production_design import (  # noqa: E402
    InitialProductionDesignError,
    _role_asset_ids_by_entity,
    _scene_role_assets_by_location,
)


class SceneCastLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entities = [
            {"entity_id": "speaker-a"},
            {"entity_id": "speaker-b"},
            {"entity_id": "silent-pack"},
        ]
        self.silent_groups = [
            ("watchful pack", [{"entity_id": "silent-pack"}])
        ]

    def test_scene_cast_is_derived_from_performance_entities(self) -> None:
        binding = _role_asset_ids_by_entity(
            entities=self.entities,
            speaking_ids={"speaker-a", "speaker-b"},
            silent_groups=self.silent_groups,
        )
        result = _scene_role_assets_by_location(
            plan={
                "locations": [
                    {"location_id": "loc-one", "scene_ids": ["scene-a"]}
                ]
            },
            performance={
                "scene_segment_calls": [
                    {
                        "scene_id": "scene-a",
                        "calls": [
                            {"entity_id": "speaker-a", "presence_mode": "on_screen"},
                            {"entity_id": "silent-pack", "presence_mode": "on_screen"},
                            {"entity_id": "speaker-b", "presence_mode": "voice_only"},
                        ],
                    }
                ]
            },
            entities=self.entities,
            role_asset_by_entity=binding,
        )
        self.assertEqual(
            result["loc-one"], ["speaker-a", "group-watchful-pack"]
        )

    def test_one_location_cannot_hide_different_scene_casts(self) -> None:
        binding = _role_asset_ids_by_entity(
            entities=self.entities,
            speaking_ids={"speaker-a", "speaker-b"},
            silent_groups=self.silent_groups,
        )
        with self.assertRaisesRegex(
            InitialProductionDesignError, "different on-screen casts"
        ):
            _scene_role_assets_by_location(
                plan={
                    "locations": [
                        {
                            "location_id": "loc-one",
                            "scene_ids": ["scene-a", "scene-b"],
                        }
                    ]
                },
                performance={
                    "scene_segment_calls": [
                        {
                            "scene_id": "scene-a",
                            "calls": [
                                {
                                    "entity_id": "speaker-a",
                                    "presence_mode": "on_screen",
                                }
                            ],
                        },
                        {
                            "scene_id": "scene-b",
                            "calls": [
                                {
                                    "entity_id": "speaker-b",
                                    "presence_mode": "on_screen",
                                }
                            ],
                        },
                    ]
                },
                entities=self.entities,
                role_asset_by_entity=binding,
            )


if __name__ == "__main__":
    unittest.main()
