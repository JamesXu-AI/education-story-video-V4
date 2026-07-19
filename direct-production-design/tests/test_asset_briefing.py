from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_briefing import (  # noqa: E402
    character_portrait_performance_brief,
    reusable_visual_from_current_record,
    silent_group_portrait_brief,
)


class AssetBriefingTests(unittest.TestCase):
    def test_group_brief_uses_closed_exact_species_roster(self) -> None:
        entities = [
            {
                "entity_id": "minister_collective",
                "entity_label_en": "Predatory minister collective",
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
                "name_en": "Predatory Ministers",
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
                    "name_en": "Lion",
                    "description_en": "An independently portrayed lion ruler.",
                },
                {
                    "name_en": "Elephant",
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
        self.assertIn("Anthropomorphic inner life belongs in expression", brief)
        self.assertIn("natural quadruped has exactly four total limbs", brief)
        self.assertIn("bird has exactly two legs and two wings", brief)
        self.assertIn("No subject may have extra, duplicated, missing", brief)
        self.assertIn("FORBIDDEN DIALOGUE PORTRAIT IDENTITIES", brief)
        self.assertIn('"name_en": "Elephant"', brief)
        self.assertNotIn("anonymous variations of that same silent role type", brief)

    def test_character_brief_uses_first_authored_dialogue_delivery(self) -> None:
        screenplay = {
            "characters": [
                {
                    "name_en": "Lion",
                    "narrative_function_en": "A tyrant whose power is reversed.",
                    "description_en": "Arrogant and coercive before his defeat.",
                }
            ],
            "segments": [
                {
                    "blocks": [
                        {
                            "type": "dialogue",
                            "speaker_en": "Lion",
                            "delivery_en": "contemptuous and absolute",
                        }
                    ]
                },
                {
                    "blocks": [
                        {
                            "type": "dialogue",
                            "speaker_en": "Lion",
                            "delivery_en": "desperate and shaken",
                        }
                    ]
                },
            ],
        }

        brief = character_portrait_performance_brief(
            screenplay=screenplay, character_name_en="Lion"
        )

        self.assertIn("'contemptuous and absolute'", brief)
        self.assertIn("mouth naturally closed", brief)
        self.assertNotIn("'desperate and shaken'", brief)
        self.assertIn("Do not replace it with a neutral face", brief)

    def test_ready_asset_is_reused_only_when_colocated_brief_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = Path("direct-production-design/assets/role-groups/ministers/group.png")
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
