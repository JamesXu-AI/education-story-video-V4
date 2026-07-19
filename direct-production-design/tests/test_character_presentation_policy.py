from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_catalog import (  # noqa: E402
    ASSET_KEYS_BY_TYPE,
)


class CharacterPresentationPolicyTests(unittest.TestCase):
    def test_presentation_is_not_character_catalog_schema(self) -> None:
        character_keys = ASSET_KEYS_BY_TYPE["character"]
        for forbidden_key in (
            "presentation",
            "included_prop_ids",
            "thought_expression_required",
            "upright_bipedal_required",
        ):
            self.assertNotIn(forbidden_key, character_keys)

if __name__ == "__main__":
    unittest.main()
