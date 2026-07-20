from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import story_video.asset_briefing as asset_briefing  # noqa: E402
from story_video.asset_briefing import (  # noqa: E402
    reusable_visual_from_current_record,
    silent_group_portrait_brief,
)


class AssetBriefingTests(unittest.TestCase):
    def test_group_brief_uses_closed_exact_species_roster(self) -> None:
        entities = [
            {
                "entity_id": "minister_collective",
                "screenplay_character_name_en": "Predatory Ministers",
                "description_en": "The Lion's silent predatory courtiers.",
                "ensemble_member_types_en": [
                    "tigers",
                    "leopards",
                    "hyenas",
                    "vultures",
                ],
            }
        ]
        characters = [
            {
                "screenplay_character_name_en": "Predatory Ministers",
                "narrative_function_en": "The Lion's enablers who later desert him.",
                "description_en": "A silent predatory court.",
            }
        ]

        brief, member_types, subject_count = silent_group_portrait_brief(
            role_type_en="predatory_minister_collective",
            entities=entities,
            screenplay_characters=characters,
            excluded_dialogue_characters=[
                {
                    "screenplay_character_name_en": "Lion",
                    "description_en": "An independently portrayed lion ruler.",
                },
                {
                    "screenplay_character_name_en": "Elephant",
                    "description_en": "An independently portrayed elephant witness.",
                },
            ],
        )

        self.assertEqual(
            member_types, ["tigers", "leopards", "hyenas", "vultures"]
        )
        self.assertEqual(subject_count, 4)
        self.assertIn("CAST COMPOSITION IS CLOSED AND EXHAUSTIVE", brief)
        self.assertIn("domestic analogue", brief)
        self.assertIn("cute filler animal is not equivalent", brief)
        self.assertIn("same species/type", brief)
        self.assertIn("exactly one coherent body plan", brief)
        self.assertIn("Characterful inner life belongs in expression", brief)
        self.assertIn("no upright animal biped", brief)
        self.assertIn("natural quadruped has exactly four total limbs", brief)
        self.assertIn("bird has exactly two legs and two wings", brief)
        self.assertIn("No subject may have extra, duplicated, missing", brief)
        self.assertIn("FORBIDDEN DIALOGUE PORTRAIT IDENTITIES", brief)
        self.assertIn('"name_en": "Elephant"', brief)
        self.assertNotIn("anonymous variations of that same silent role type", brief)

    def test_story_bound_character_portrait_helpers_do_not_exist(self) -> None:
        self.assertFalse(
            hasattr(asset_briefing, "character_portrait_performance_brief")
        )
        self.assertFalse(hasattr(asset_briefing, "first_dialogue_delivery"))

    def test_ready_asset_is_reused_only_when_colocated_brief_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = Path("assets/role-groups/ministers/group.png")
            media = root / output
            media.parent.mkdir(parents=True)
            media.write_bytes(b"image")
            brief_path = media.parent / "group.brief.txt"
            brief_path.write_text("current brief\n", encoding="utf-8")
            record = {
                "type": "ensemble_roster",
                "status": "ready",
                "members": [
                    {
                        "roster_asset": {
                            "path": output.as_posix(),
                            "uri": "https://example.test/group.png",
                            "subject_count": 4,
                        }
                    }
                ],
            }

            reusable = reusable_visual_from_current_record(
                root=root,
                record=record,
                asset_type="ensemble_roster",
                output=output,
                prompt="current brief",
            )
            stale = reusable_visual_from_current_record(
                root=root,
                record=record,
                asset_type="ensemble_roster",
                output=output,
                prompt="changed roster brief",
            )

            self.assertEqual(
                reusable,
                {
                    "path": output.as_posix(),
                    "uri": "https://example.test/group.png",
                },
            )
            self.assertIsNone(stale)


if __name__ == "__main__":
    unittest.main()
