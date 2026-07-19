from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from route_b_handoff import load_route_b_handoff  # noqa: E402


class RouteBHandoffTests(unittest.TestCase):
    def test_ledgers_replace_the_retired_storyboard_companion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "previsualize-cinematography"
            pending = root / ".pending/virtual-production"
            upstream.mkdir(parents=True)
            pending.mkdir(parents=True)
            storyboard = upstream / "storyboard.md"
            storyboard.write_text("# Native Seed Master Storyboard\n", encoding="utf-8")
            manifest = {
                "schema_version": "1.0",
                "segments": [
                    {
                        "segment_id": "segment-001",
                        "target_duration_seconds": 8,
                    }
                ],
                "lines": [
                    {
                        "line_id": "L01",
                        "segment_id": "segment-001",
                        "shot_id": "SH-001",
                        "speaker": "hero",
                        "addressee": "listener",
                        "exact_text": "We begin.",
                        "treatment": "on_screen",
                    }
                ],
            }
            manifest_path = upstream / "storyboard-compile-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            storyboard_sha = hashlib.sha256(storyboard.read_bytes()).hexdigest()
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            identity = {
                "schema_version": "1.0",
                "storyboard_sha256": storyboard_sha,
                "source_manifest_sha256": manifest_sha,
            }
            dialogue = {
                **identity,
                "segments": [
                    {
                        "segment_id": "segment-001",
                        "duration_seconds": 8,
                        "dialogue_cues": [
                            {
                                "line_id": "L01",
                                "shot_id": "SH-001",
                                "speaker": "hero",
                                "exact_text": "We begin.",
                                "start_seconds": 1.0,
                                "end_seconds": 2.2,
                            }
                        ],
                    }
                ],
            }
            boundary = {
                **identity,
                "segments": [
                    {
                        "segment_id": "segment-001",
                        "editable_hold_seconds": 0.8,
                        "final_visible_state": "Hero settles closed-mouth.",
                        "final_sound_state": "Room tone continues.",
                    }
                ],
            }
            (pending / "dialogue-duration-ledger.json").write_text(
                json.dumps(dialogue), encoding="utf-8"
            )
            (pending / "boundary-continuity-report.json").write_text(
                json.dumps(boundary), encoding="utf-8"
            )
            handoff = load_route_b_handoff(root)
        self.assertEqual(list(handoff), ["segment-001"])
        cue = handoff["segment-001"]["timeline_blocks"][0]["dialogue_cues"][0]
        self.assertEqual(cue["exact_text"], "We begin.")
        self.assertEqual(
            handoff["segment-001"]["segment_safe_cut_design"]["editable_hold_seconds"],
            0.8,
        )


if __name__ == "__main__":
    unittest.main()
