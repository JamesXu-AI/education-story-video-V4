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
    _semantic_reuse_review,
    _write_asset_plan,
)


class AssetReworkTests(unittest.TestCase):
    def _ready_asset(
        self,
        root: Path,
        *,
        old_prompt: str,
        asset_id: str = "subject-a",
    ) -> tuple[Path, Path, dict[str, object]]:
        output = Path(
            f"direct-production-design/assets/characters/{asset_id}/identity.png"
        )
        media = root / output
        media.parent.mkdir(parents=True)
        media.write_bytes(b"existing image")
        (media.parent / "identity.brief.txt").write_text(
            old_prompt.rstrip() + "\n", encoding="utf-8"
        )
        catalog_path = root / "direct-production-design/assets.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                {
                    "contract": "production-design-assets",
                    "assets": {
                        asset_id: {
                            "type": "character",
                            "status": "ready",
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
            "prompt": "Current visible design authority.",
            "relative_path": output.with_suffix(""),
            "references": [],
            "depends_on": [],
        }
        return output, catalog_path, job

    def test_forced_asset_rework_does_not_reuse_matching_old_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = Path(
                "direct-production-design/assets/costumes/lion-defeated/image.png"
            )
            media = root / output
            media.parent.mkdir(parents=True)
            media.write_bytes(b"wrong real image")
            prompt = "Generate the exact injured defeated Lion state."
            (media.parent / "image.brief.txt").write_text(
                prompt + "\n", encoding="utf-8"
            )
            catalog_path = root / "direct-production-design/assets.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "contract": "production-design-assets",
                        "assets": {
                            "costume-lion-defeated": {
                                "type": "costume",
                                "status": "ready",
                                "visual": {
                                    "path": output.as_posix(),
                                    "uri": "https://example.test/wrong.png",
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            job = {
                "asset_id": "costume-lion-defeated",
                "kind": "costume",
                "prompt": prompt,
                "relative_path": output.with_suffix(""),
                "references": [],
                "depends_on": [],
            }
            _write_asset_plan(
                root,
                [job],
                ["direct-production-design/production-design-plan.json"],
                force_regenerate={"costume-lion-defeated"},
                codex_reuse=set(),
                voice_references={},
            )
            plan = json.loads(catalog_path.read_text(encoding="utf-8"))
        record = plan["assets"]["costume-lion-defeated"]
        self.assertEqual(record["status"], "planned")
        self.assertNotIn("visual", record)

    def test_prompt_change_is_exposed_for_codex_without_code_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, _, job = self._ready_asset(
                root, old_prompt="Previous wording with the same or different meaning."
            )
            review = _semantic_reuse_review(
                root, [job], force_regenerate=set()
            )

        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]["asset_id"], "subject-a")
        self.assertEqual(review[0]["existing_media_path"], output.as_posix())
        self.assertEqual(
            review[0]["previous_brief"],
            "Previous wording with the same or different meaning.",
        )
        self.assertEqual(review[0]["current_brief"], job["prompt"])

    def test_unresolved_prompt_change_cannot_overwrite_existing_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, catalog_path, job = self._ready_asset(
                root, old_prompt="Previous visible design authority."
            )
            original_catalog = catalog_path.read_text(encoding="utf-8")
            with self.assertRaises(InitialProductionDesignError):
                review = _semantic_reuse_review(
                    root, [job], force_regenerate=set()
                )
                _require_codex_semantic_decisions(
                    review,
                    codex_reuse=set(),
                    codex_regenerate_visual=set(),
                )

            self.assertEqual(
                catalog_path.read_text(encoding="utf-8"), original_catalog
            )

    def test_codex_semantic_reuse_preserves_media_and_accepts_current_brief(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, catalog_path, job = self._ready_asset(
                root, old_prompt="Previous semantically equivalent wording."
            )
            _write_asset_plan(
                root,
                [job],
                ["screenplay-writer/screenplay.md"],
                force_regenerate=set(),
                codex_reuse={"subject-a"},
                voice_references={"subject-a": {"path": "voice.wav", "uri": "voice"}},
            )
            plan = json.loads(catalog_path.read_text(encoding="utf-8"))
            current_brief = (
                root / output
            ).parent.joinpath("identity.brief.txt").read_text(encoding="utf-8")

        record = plan["assets"]["subject-a"]
        self.assertEqual(record["status"], "ready")
        self.assertEqual(record["visual"]["path"], output.as_posix())
        self.assertEqual(current_brief, "Current visible design authority.\n")

    def test_codex_can_choose_visual_regeneration_without_hardcoded_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, catalog_path, job = self._ready_asset(
                root, old_prompt="Previous visible design authority."
            )
            review = _semantic_reuse_review(
                root, [job], force_regenerate=set()
            )
            _require_codex_semantic_decisions(
                review,
                codex_reuse=set(),
                codex_regenerate_visual={"subject-a"},
            )
            _write_asset_plan(
                root,
                [job],
                ["screenplay-writer/screenplay.md"],
                force_regenerate={"subject-a"},
                codex_reuse=set(),
                voice_references={"subject-a": {"path": "voice.wav", "uri": "voice"}},
            )
            plan = json.loads(catalog_path.read_text(encoding="utf-8"))

        record = plan["assets"]["subject-a"]
        self.assertEqual(record["status"], "planned")
        self.assertNotIn("visual", record)


if __name__ == "__main__":
    unittest.main()
