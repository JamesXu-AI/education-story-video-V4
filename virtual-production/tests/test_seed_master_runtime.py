from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Optional


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.seed_master_runtime import (  # noqa: E402
    SeedMasterRuntimeError,
    _validate_continuity_bindings,
    parse_segment_script,
    storyboard_segment_rows,
)


def _plan(segment_id: str = "segment-001", *, scene: str = "forest clearing") -> dict:
    return {
        "contract": "seedance-natural-language-plan-v1",
        "segment_id": segment_id,
        "source_storyboard_sha256": "a" * 64,
        "scene_ids": [scene],
        "target_duration": 8,
        "shot_count": 2,
        "operation": "multimodal_reference",
        "shooting_plan_status": "planned",
        "schedule_mode": "parallel",
        "planned_wave": 0,
        "depends_on_segment_ids": [],
        "dependency_reason": "independent opening",
        "predecessor_review_required": False,
        "required_predecessor_evidence": "none",
        "successor_recompile_required": False,
        "fallback_operation_and_story_cost": "none",
        "seam_class": "authored_discontinuity",
        "seam_resynthesis_allowed": True,
        "seam_story_reason": "new scene",
        "editorial_intent": "open on calm attention, end on the listener response",
        "reference_video_scope": "none",
        "reference_video_audio": "none",
        "camera_ensemble_color_resynthesis_allowed": True,
        "continuity": {
            "location_state_chain": scene,
            "relationship": "independent",
            "state_source_segment_id": "none",
            "world_binding_ids": ["B01"],
            "temporal_binding_ids": [],
            "embedded_npc_asset_ids": [],
            "authorized_independent_performer_asset_ids": ["grandfather", "uthman"],
            "population_lock_en": "Only Grandfather and Uthman may appear; introduce no other person, animal, silhouette, reflection, or distant bystander.",
        },
        "bindings": [
            {
                "binding_id": "B01",
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "asset_namespace": "forest-clearing",
                "readable_subject": "forest clearing",
                "purpose": "architecture and daylight only",
                "shot_scope": [1, 2],
                "forbidden_inheritance": "people, text, or camera angle",
            }
        ],
        "dialogue_cues": [
            {
                "line_id": "line-1",
                "speaker_entity_id": "grandfather",
                "speaker_name": "Grandfather",
                "exact_text": "Then listen closely.",
                "shot_number": 2,
                "start_seconds": 4.5,
                "end_seconds": 6.0,
            }
        ],
        "editable_hold_seconds": 1.0,
        "final_visible_state": "Uthman sits still and meets Grandfather's eyes.",
        "final_sound_state": "The final word fades into quiet room tone.",
    }


def _prompt() -> str:
    return """Operation: Multimodal reference, 8 seconds, 16:9, 1080p, native audio on.

Use @Image1 only for the forest clearing's architecture and daylight, not for characters, text, or camera angle.

Only Grandfather and Uthman may appear; introduce no other person, animal, silhouette, reflection, or distant bystander.

Scene: A warm forest clearing at Eid, with soft daylight through broad leaves and an open path between the crowd and a root throne.

Shot 1: The locked camera frames Uthman seated beside Grandfather. Uthman closes the book on his lap, leans across the low table, and stops with both hands on the cover while Grandfather lowers his cup and meets his eyes. Quiet room tone and a faint clock tick remain audible.

Shot 2: Cut closer as the camera slowly pushes toward Grandfather. He sets the cup on its saucer, waits until Uthman sits upright, looks directly at him, and says in a warm deliberate voice, \"Then listen closely.\" Uthman keeps his mouth closed, stills his hands, and holds Grandfather's gaze as the porcelain click fades.

Style and image quality: Warm low-contrast evening light, tactile natural materials, stable motion, and crisp eyes and hands at 1080p.

Constraints and end state: Subtitle-free, no logo, no watermark; preserve both identities and end with Uthman settled and attentive.
"""


def _write_fixture(
    root: Path, prompt: Optional[str] = None, plan: Optional[dict] = None
) -> Path:
    script = root / "segment-001.md"
    script.write_text(_prompt() if prompt is None else prompt, encoding="utf-8")
    script.with_suffix(".plan.json").write_text(
        json.dumps(plan or _plan()), encoding="utf-8"
    )
    return script


class NaturalPromptRuntimeTests(unittest.TestCase):
    def test_accepts_natural_language_prompt_without_parsing_its_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parsed = parse_segment_script(_write_fixture(Path(directory)))
        self.assertEqual(parsed["segment_id"], "segment-001")
        self.assertNotIn("shots", parsed)
        self.assertNotIn("binding_id", parsed["prompt"])
        self.assertNotIn("{", parsed["prompt"])

    def test_prompt_form_remains_free_after_binding_checks(self) -> None:
        population_lock = _plan()["continuity"]["population_lock_en"]
        prompt = (
            "A free-form Seedance request with no prescribed operation or scene headings.\n\n"
            "Let @Image1 supply the approved forest-clearing reference.\n"
            f"{population_lock}\n\n"
            "Shot 2: From 0–3s the camera pans, tilts, cranes, and pushes toward CHR-001; "
            'the prose may contain {"author_choice": true}, internal terminology, '
            'or any other wording the author deliberately chooses. Grandfather says, '
            '"Then listen closely."\n\n'
            + "Unrestricted descriptive wording. " * 1100
        )
        with tempfile.TemporaryDirectory() as directory:
            parsed = parse_segment_script(_write_fixture(Path(directory), prompt))
        self.assertEqual(parsed["prompt"], prompt.strip())

    def test_rejects_provider_token_after_the_first_shot_section(self) -> None:
        bad = _prompt().replace(
            "Use @Image1 only for the forest clearing's architecture and daylight, not for characters, text, or camera angle.",
            "Use the approved forest clearing only for architecture and daylight.",
        ).replace(
            "Shot 1:",
            "Shot 1: Use @Image1 only for the approved forest clearing.",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SeedMasterRuntimeError, "before its first Shot"):
                parse_segment_script(_write_fixture(Path(directory), bad))

    def test_rejects_provider_token_set_that_differs_from_private_plan(self) -> None:
        bad = _prompt().replace("@Image1", "@Image2")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SeedMasterRuntimeError, "tokens differ"):
                parse_segment_script(_write_fixture(Path(directory), bad))

    def test_rejects_dialogue_placed_in_the_wrong_shot(self) -> None:
        bad = _prompt().replace('"Then listen closely."', '"Listen."', 1).replace(
            "Quiet room tone and a faint clock tick remain audible.",
            'Grandfather says, "Then listen closely." Quiet room tone remains audible.',
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SeedMasterRuntimeError, "inside Shot 2"):
                parse_segment_script(_write_fixture(Path(directory), bad))

    def test_rejects_missing_population_lock(self) -> None:
        population_lock = _plan()["continuity"]["population_lock_en"]
        bad = _prompt().replace(population_lock + "\n", "")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SeedMasterRuntimeError, "population lock exactly once"):
                parse_segment_script(_write_fixture(Path(directory), bad))

    def test_rejects_only_an_empty_prompt_at_the_text_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SeedMasterRuntimeError, "must not be empty"):
                parse_segment_script(_write_fixture(Path(directory), " \n\t"))

    def test_private_plans_replace_compile_manifest_as_segment_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_root = root / ".pending/virtual-production/seedance-segment-plans"
            plan_root.mkdir(parents=True)
            first = _plan()
            second = _plan("segment-002", scene="family room")
            for row in (first, second):
                (plan_root / f"{row['segment_id']}.json").write_text(
                    json.dumps(row), encoding="utf-8"
                )
            rows = storyboard_segment_rows(root)
        self.assertEqual([row["segment_id"] for row in rows], ["segment-001", "segment-002"])

    def test_rejects_serial_temporal_evidence_without_location_world_binding(self) -> None:
        plan = _plan()
        parsed = {
            "segment_id": "segment-001",
            "metadata": plan,
            "bindings": [
                {
                    "binding_id": "B01",
                    "provider_token": "@Image1",
                    "provider_role": "reference_image",
                    "asset_namespace": "continuity",
                    "shot_scope": ["Shot 1", "Shot 2"],
                }
            ],
        }
        media = [
            {
                "source_kind": "provider_last_frame",
                "binding_ids": ["B01"],
            }
        ]
        catalog = {
            "assets": {
                "forest-clearing": {
                    "type": "location_master",
                    "embedded_npc_asset_ids": [],
                    "independent_performer_asset_ids": ["grandfather", "uthman"],
                }
            }
        }
        with self.assertRaisesRegex(SeedMasterRuntimeError, "Location master"):
            _validate_continuity_bindings(
                parsed=parsed, catalog=catalog, media_bindings=media
            )

    def test_accepts_separate_world_and_temporal_authorities(self) -> None:
        plan = _plan()
        plan["shot_count"] = 2
        plan["continuity"] = {
            **plan["continuity"],
            "relationship": "adjacent_continuation",
            "state_source_segment_id": "segment-001",
            "world_binding_ids": ["B01"],
            "temporal_binding_ids": ["B02"],
        }
        parsed = {
            "segment_id": "segment-002",
            "metadata": plan,
            "bindings": [
                {
                    "binding_id": "B01",
                    "provider_token": "@Image1",
                    "provider_role": "reference_image",
                    "asset_namespace": "forest-clearing",
                    "shot_scope": ["Shot 1", "Shot 2"],
                },
                {
                    "binding_id": "B02",
                    "provider_token": "@Video1",
                    "provider_role": "reference_video",
                    "asset_namespace": "continuity",
                    "shot_scope": ["Shot 1", "Shot 2"],
                },
            ],
        }
        catalog = {
            "assets": {
                "forest-clearing": {
                    "type": "location_master",
                    "embedded_npc_asset_ids": [],
                    "independent_performer_asset_ids": ["grandfather", "uthman"],
                }
            }
        }
        media = [
            {"source_kind": "asset_catalog", "binding_ids": ["B01"]},
            {
                "source_kind": "complete_predecessor_video",
                "binding_ids": ["B02"],
            },
        ]
        _validate_continuity_bindings(
            parsed=parsed, catalog=catalog, media_bindings=media
        )

    def test_rejects_nonadjacent_revisit_with_wrong_state_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_root = root / ".pending/virtual-production/seedance-segment-plans"
            plan_root.mkdir(parents=True)
            first = _plan("segment-001", scene="room")
            middle = _plan("segment-002", scene="forest")
            revisit = _plan("segment-003", scene="room")
            revisit["continuity"] = {
                **revisit["continuity"],
                "relationship": "nonadjacent_revisit",
                "state_source_segment_id": "segment-002",
                "temporal_binding_ids": ["B01"],
                "world_binding_ids": ["B01"],
            }
            revisit["depends_on_segment_ids"] = ["segment-002"]
            for row in (first, middle, revisit):
                (plan_root / f"{row['segment_id']}.json").write_text(
                    json.dumps(row), encoding="utf-8"
                )
            with self.assertRaisesRegex(SeedMasterRuntimeError, "latest state"):
                storyboard_segment_rows(root)


if __name__ == "__main__":
    unittest.main()
