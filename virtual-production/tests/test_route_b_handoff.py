from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from route_b_handoff import RouteBHandoffError, load_route_b_handoff  # noqa: E402


def _plan() -> dict:
    return {
        "contract": "seedance-natural-language-plan-v1",
        "segment_id": "segment-001",
        "scene_ids": ["forest clearing"],
        "target_duration": 8,
        "continuity": {
            "location_state_chain": "forest-clearing",
            "relationship": "independent",
            "state_source_segment_id": "none",
            "world_binding_ids": ["B01"],
            "temporal_binding_ids": [],
            "embedded_npc_asset_ids": [],
            "authorized_independent_performer_asset_ids": ["grandfather"],
            "population_lock_en": "Only Grandfather may appear; add no other person or animal.",
        },
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
        "final_visible_state": "Uthman is still and attentive.",
        "final_sound_state": "Quiet room tone after the final word.",
    }


def _write(root: Path, plan: dict) -> None:
    path = root / ".pending/virtual-production/seedance-segment-plans/segment-001.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan), encoding="utf-8")


class RouteBHandoffTests(unittest.TestCase):
    def test_builds_read_only_handoff_directly_from_private_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write(root, _plan())
            handoff = load_route_b_handoff(root)
            self.assertFalse((root / "dialogue-duration-ledger.json").exists())
            self.assertFalse((root / "boundary-continuity-report.json").exists())
        self.assertEqual(handoff["segment-001"]["duration_seconds"], 8.0)
        cue = handoff["segment-001"]["timeline_blocks"][0]["dialogue_cues"][0]
        self.assertEqual(cue["exact_text"], "Then listen closely.")

    def test_rejects_dialogue_outside_segment_duration(self) -> None:
        plan = _plan()
        plan["dialogue_cues"][0]["end_seconds"] = 9.0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write(root, plan)
            with self.assertRaisesRegex(RouteBHandoffError, "timing or ownership"):
                load_route_b_handoff(root)


if __name__ == "__main__":
    unittest.main()
