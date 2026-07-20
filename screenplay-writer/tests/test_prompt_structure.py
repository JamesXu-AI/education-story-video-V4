from __future__ import annotations

from pathlib import Path
import unittest


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "references" / "prompts"
PROMPT_FILES = (
    "translation_gen.md",
    "age_band_gen.md",
    "story_gen.md",
    "story_to_screenplay_gen.md",
)
REQUIRED_SECTIONS = (
    "## Task",
    "## Input Contract",
    "## Decision Rules",
    "## Output Contract",
    "## Release Gate",
)


class PromptStructureTests(unittest.TestCase):
    def test_every_prompt_uses_the_same_five_part_structure(self) -> None:
        for filename in PROMPT_FILES:
            with self.subTest(filename=filename):
                text = (PROMPT_ROOT / filename).read_text(encoding="utf-8")
                positions = [text.index(section) for section in REQUIRED_SECTIONS]
                self.assertEqual(positions, sorted(positions))
                for section in REQUIRED_SECTIONS:
                    self.assertEqual(text.count(section), 1)

    def test_prompts_stay_concise(self) -> None:
        for filename in PROMPT_FILES:
            with self.subTest(filename=filename):
                line_count = len(
                    (PROMPT_ROOT / filename).read_text(encoding="utf-8").splitlines()
                )
                self.assertLessEqual(line_count, 240)

    def test_each_prompt_has_one_distinct_output_contract(self) -> None:
        expected = {
            "translation_gen.md": '"title_en"',
            "age_band_gen.md": '"target_age_band"',
            "story_gen.md": "TASK_DIR/story.md",
            "story_to_screenplay_gen.md": "TASK_DIR/screenplay-writer/screenplay.md",
        }
        for filename, marker in expected.items():
            with self.subTest(filename=filename):
                text = (PROMPT_ROOT / filename).read_text(encoding="utf-8")
                self.assertIn(marker, text)

    def test_story_prompts_require_semantic_understanding_before_structure(self) -> None:
        story = (PROMPT_ROOT / "story_gen.md").read_text(encoding="utf-8")
        screenplay = (PROMPT_ROOT / "story_to_screenplay_gen.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Understand before drafting", story)
        self.assertIn("internal semantic model", story)
        self.assertIn("Understand the film before authoring tables", screenplay)
        self.assertIn("internal model", screenplay)


if __name__ == "__main__":
    unittest.main()
