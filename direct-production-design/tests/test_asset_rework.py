from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_initial_production_design import (  # noqa: E402
    InitialProductionDesignError,
    _require_codex_semantic_decisions,
    _reusable_visuals,
    _semantic_reuse_review,
)


class AssetReworkTests(unittest.TestCase):
    def _ready_asset(
        self,
        root: Path,
        *,
        old_prompt: str,
        asset_id: str = "subject-a",
    ) -> tuple[Path, Path, dict[str, object]]:
        output = Path(f"assets/characters/{asset_id}/identity.png")
        media = root / output
        media.parent.mkdir(parents=True)
        media.write_bytes(b"existing image")
        (media.parent / "identity.brief.txt").write_text(
            old_prompt.rstrip() + "\n", encoding="utf-8"
        )
        catalog_path = root / "assets/assets.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                {
                    "contract": "production-design-assets",
                    "assets": {
                        asset_id: {
                            "type": "character",
                            "visual": {
                                "path": output.as_posix(),
                                "uri": "https://example.test/existing.png",
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        job: dict[str, object] = {
            "asset_id": asset_id,
            "kind": "character",
            "prompt": "Current exact model prompt.",
            "relative_path": output,
            "references": [],
            "depends_on": [],
        }
        return output, catalog_path, job

    def test_forced_asset_is_not_reused_and_catalog_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, catalog_path, job = self._ready_asset(
                root, old_prompt="Current exact model prompt."
            )
            before = catalog_path.read_text(encoding="utf-8")
            reusable = _reusable_visuals(
                root,
                [job],
                force_regenerate={"subject-a"},
                codex_reuse=set(),
            )
            after = catalog_path.read_text(encoding="utf-8")

        self.assertEqual(reusable, {})
        self.assertEqual(after, before)

    def test_prompt_change_is_exposed_without_code_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, _, job = self._ready_asset(
                root, old_prompt="Previous model prompt."
            )
            review = _semantic_reuse_review(root, [job], force_regenerate=set())

        self.assertEqual(review[0]["asset_id"], "subject-a")
        self.assertEqual(review[0]["existing_media_path"], output.as_posix())
        self.assertEqual(review[0]["current_brief"], job["prompt"])

    def test_unresolved_change_blocks_without_catalog_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, catalog_path, job = self._ready_asset(
                root, old_prompt="Previous model prompt."
            )
            before = catalog_path.read_text(encoding="utf-8")
            review = _semantic_reuse_review(root, [job], force_regenerate=set())
            with self.assertRaises(InitialProductionDesignError):
                _require_codex_semantic_decisions(
                    review, codex_reuse=set(), codex_regenerate_visual=set()
                )
            after = catalog_path.read_text(encoding="utf-8")

        self.assertEqual(after, before)

    def test_codex_reuse_accepts_pixels_and_updates_only_colocated_brief(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, catalog_path, job = self._ready_asset(
                root, old_prompt="Equivalent previous wording."
            )
            before = catalog_path.read_text(encoding="utf-8")
            reusable = _reusable_visuals(
                root,
                [job],
                force_regenerate=set(),
                codex_reuse={"subject-a"},
            )
            brief = (root / output).parent.joinpath(
                "identity.brief.txt"
            ).read_text(encoding="utf-8")
            after = catalog_path.read_text(encoding="utf-8")

        self.assertIn("subject-a", reusable)
        self.assertEqual(brief, "Current exact model prompt.\n")
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
