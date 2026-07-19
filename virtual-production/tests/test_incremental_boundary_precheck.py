from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from incremental_boundary_precheck import (  # noqa: E402
    boundary_contract,
    classify_technical_precheck,
    load_config,
    prepare_incremental_boundary_precheck,
)


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "incremental-boundary-precheck.json"
)


def _evidence(*, ssim: float, y: float, saturation: float, chroma: float) -> dict:
    return {
        "metrics": {
            "boundary_transition_contract": {"transition_class": "motivated_cut"},
            "boundary_ssim": ssim,
            "boundary_signalstats": {
                "absolute_luma_average_delta": y,
                "absolute_saturation_average_delta": saturation,
                "chroma_vector_delta": chroma,
            },
        }
    }


def _write_screenplay(root: Path) -> None:
    target = root / "screenplay-writer" / "screenplay.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            (
                "# Screenplay",
                '- `transition_design_json`: {"type":"action_cut","reason_en":"continue"}',
                '- `transition_design_json`: {"type":"final_end","reason_en":"finish"}',
            )
        ),
        encoding="utf-8",
    )


class IncrementalBoundaryPrecheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_boundary_contract_uses_predecessor_authored_transition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_screenplay(root)
            contract = boundary_contract(
                root,
                "segment-002",
                ["segment-001", "segment-002"],
                config=self.config,
            )
        assert contract is not None
        self.assertEqual(contract["boundary_id"], "segment-001--segment-002")
        self.assertEqual(contract["authored_transition_type"], "action_cut")

    def test_small_matched_jump_routes_to_postproduction(self) -> None:
        status, _, blocks, owner = classify_technical_precheck(
            _evidence(ssim=0.9, y=3.2, saturation=1.2, chroma=1.4),
            self.config,
        )
        self.assertEqual(status, "postproduction_color_match_candidate")
        self.assertFalse(blocks)
        self.assertEqual(owner, "finish-postproduction")

    def test_dissimilar_cut_remains_direct_visual_review(self) -> None:
        status, _, blocks, owner = classify_technical_precheck(
            _evidence(ssim=0.3, y=30.0, saturation=10.0, chroma=15.0),
            self.config,
        )
        self.assertEqual(status, "visual_review_ready")
        self.assertFalse(blocks)
        self.assertEqual(owner, "seedance-video-review")

    def test_large_matched_jump_holds_downstream_wave_for_review(self) -> None:
        status, _, blocks, owner = classify_technical_precheck(
            _evidence(ssim=0.95, y=18.0, saturation=8.0, chroma=10.0),
            self.config,
        )
        self.assertEqual(status, "technical_hold_for_visual_review")
        self.assertTrue(blocks)
        self.assertEqual(owner, "virtual-production")

    def test_current_segment_waits_cleanly_when_predecessor_is_not_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_screenplay(root)
            current = (
                root
                / ".pending"
                / "virtual-production"
                / "generation-segments"
                / "segment-002"
            )
            current.mkdir(parents=True)
            (current / "video.mp4").write_bytes(b"video")
            (current / "production-record.json").write_text(
                json.dumps(
                    {
                        "contract": "generated-segment-production-record",
                        "status": "GENERATED",
                        "segment_id": "segment-002",
                        "provider_attempt_id": "segment-002__attempt-0001",
                    }
                ),
                encoding="utf-8",
            )
            result = prepare_incremental_boundary_precheck(
                root,
                "segment-002",
                ["segment-001", "segment-002"],
                config_path=CONFIG_PATH,
            )
        self.assertEqual(result["technical_status"], "waiting_for_predecessor_segment")
        self.assertFalse(result["blocks_downstream"])


if __name__ == "__main__":
    unittest.main()
