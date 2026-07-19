from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest


DEPARTMENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = DEPARTMENT_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

class CodexSemanticReuseTests(unittest.TestCase):
    def test_project_owns_the_direct_codex_review_prompt(self) -> None:
        prompt_path = (
            DEPARTMENT_ROOT
            / "references"
            / "codex-asset-semantic-reuse-review.md"
        )
        prompt = prompt_path.read_text(encoding="utf-8")
        normalized = " ".join(prompt.split())

        self.assertIn("Judge visual meaning, not textual equality", normalized)
        self.assertIn("Make the decision yourself", normalized)
        self.assertIn("--codex-reuse-asset", prompt)
        self.assertNotIn("--codex-reuse-view", prompt)

    def test_generic_reuse_code_contains_no_current_story_examples_or_model_api(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                SCRIPT_ROOT / "build_initial_production_design.py",
                SCRIPT_ROOT / "story_video" / "asset_briefing.py",
            )
        )
        self.assertIsNone(
            re.search(
                r"\b(?:lion|elephant|tiger|throne)\b",
                sources,
                flags=re.IGNORECASE,
            )
        )
        self.assertNotIn("SEED_MODEL", sources)
        self.assertNotIn("chat/completions", sources)


if __name__ == "__main__":
    unittest.main()
