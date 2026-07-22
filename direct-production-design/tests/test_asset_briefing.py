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
)


class AssetBriefingTests(unittest.TestCase):
    def test_module_contains_no_prompt_authoring_helper(self) -> None:
        for removed in (
            "silent_group_portrait_brief",
            "character_portrait_performance_brief",
            "first_dialogue_delivery",
            "ordered_ensemble_member_types",
            "group_portrait_subject_count",
        ):
            self.assertFalse(hasattr(asset_briefing, removed))

    def test_asset_reuse_requires_exact_colocated_model_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = Path("assets/characters/actor/identity.png")
            media = root / output
            media.parent.mkdir(parents=True)
            media.write_bytes(b"image")
            (media.parent / "identity.brief.txt").write_text(
                "exact model prompt\n", encoding="utf-8"
            )
            record = {
                "type": "character",
                "visual": {
                    "path": output.as_posix(),
                    "uri": "https://example.test/identity.png",
                },
            }

            self.assertIsNotNone(
                reusable_visual_from_current_record(
                    root=root,
                    record=record,
                    asset_type="character",
                    output=output,
                    prompt="exact model prompt",
                )
            )
            self.assertIsNone(
                reusable_visual_from_current_record(
                    root=root,
                    record=record,
                    asset_type="character",
                    output=output,
                    prompt="python-added suffix",
                )
            )


if __name__ == "__main__":
    unittest.main()
