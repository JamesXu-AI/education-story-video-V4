from __future__ import annotations

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace


DEPARTMENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = DEPARTMENT_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from assemble_segment_videos import _render_filter  # noqa: E402
from boundary_qc import (  # noqa: E402
    append_segment_repair_filter,
    build_repair_plan,
    load_config,
    repair_lut_filter,
    triage_boundary,
)


def _metrics(
    *,
    similarity: float = 0.98,
    luma_mean: float = 3.1,
    luma_q10: float = 4.0,
    luma_q90: float = 2.0,
    saturation_factor: float = 1.057,
    chroma_distance: float = 1.4,
) -> dict[str, object]:
    incoming = {
        "luma_q10": 48.0,
        "luma_mean": 107.0,
        "luma_q90": 173.0,
        "u_mean": 113.2,
        "v_mean": 140.2,
        "saturation_mean": 20.7,
    }
    outgoing = {
        "luma_q10": incoming["luma_q10"] + luma_q10,
        "luma_mean": incoming["luma_mean"] + luma_mean,
        "luma_q90": incoming["luma_q90"] + luma_q90,
        "u_mean": 111.9,
        "v_mean": 140.9,
        "saturation_mean": incoming["saturation_mean"] * saturation_factor,
    }
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "delta_target_minus_incoming": {
            "luma_q10": luma_q10,
            "luma_mean": luma_mean,
            "luma_q90": luma_q90,
            "u_mean": -1.3,
            "v_mean": 0.7,
            "chroma_center_distance": chroma_distance,
            "saturation_factor": saturation_factor,
            "saturation_ratio_delta": saturation_factor - 1.0,
        },
        "luma_shape_correlation": similarity,
    }


def _hard_boundary() -> dict[str, object]:
    return {
        "from": "segment-005",
        "to": "segment-006",
        "picture_edit": "hard_cut",
        "transition_class": "motivated_cut",
    }


class BoundaryQCContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(DEPARTMENT_ROOT / "assets" / "boundary-qc.json")

    def test_matched_small_color_jump_creates_safe_repair(self) -> None:
        status, reason, plan = triage_boundary(
            _hard_boundary(), _metrics(), self.config
        )
        self.assertEqual(status, "safe_color_match_planned")
        self.assertIn("small correctable", reason)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertAlmostEqual(plan["fade_seconds"], 0.75)
        self.assertFalse(plan["source_mutation"])

    def test_dissimilar_authored_cut_is_not_automatically_graded(self) -> None:
        status, _, plan = triage_boundary(
            _hard_boundary(), _metrics(similarity=0.2, luma_mean=10.0), self.config
        )
        self.assertEqual(status, "authored_cut_no_auto_match")
        self.assertIsNone(plan)

    def test_authored_transition_is_evidence_only(self) -> None:
        boundary = _hard_boundary()
        boundary.update(
            {"picture_edit": "dissolve", "transition_class": "designed_transition"}
        )
        status, _, plan = triage_boundary(boundary, _metrics(), self.config)
        self.assertEqual(status, "authored_transition_evidence_only")
        self.assertIsNone(plan)

    def test_large_matched_jump_requires_review_instead_of_hidden_fix(self) -> None:
        status, _, plan = triage_boundary(
            _hard_boundary(),
            _metrics(luma_mean=18.0, luma_q10=20.0, luma_q90=20.0),
            self.config,
        )
        self.assertEqual(status, "review_required")
        self.assertIsNotNone(plan)

    def test_repair_filter_is_luma_chroma_only_and_time_decays(self) -> None:
        plan = build_repair_plan(_metrics(), self.config)
        lut = repair_lut_filter(plan)
        self.assertTrue(lut.startswith("lutyuv="))
        self.assertIn("saturation", str(plan))
        filters: list[str] = []
        append_segment_repair_filter(
            filters,
            input_label="vbase",
            output_label="vout",
            label_prefix="repair",
            plan=plan,
        )
        graph = ";".join(filters)
        self.assertIn("split=2", graph)
        self.assertIn("blend=all_expr", graph)
        self.assertIn("0.750000-T", graph)

    def test_picture_assembly_uses_repair_only_on_incoming_segment(self) -> None:
        records = [
            SimpleNamespace(
                segment_name="segment-005",
                probe=SimpleNamespace(
                    duration_seconds=10.0,
                    has_audio=True,
                    frame_rate="24/1",
                ),
            ),
            SimpleNamespace(
                segment_name="segment-006",
                probe=SimpleNamespace(
                    duration_seconds=10.0,
                    has_audio=True,
                    frame_rate="24/1",
                ),
            ),
        ]
        plan = build_repair_plan(_metrics(), self.config)
        graph = _render_filter(
            records,
            1920,
            1080,
            [
                {
                    "from": "segment-005",
                    "to": "segment-006",
                    "picture_edit": "hard_cut",
                    "audio_edit": "native_continuity_declick",
                    "audio_edge_fade_seconds": 0.01,
                    "overlap_seconds": 0.0,
                }
            ],
            {"segment-006": plan},
        )
        self.assertNotIn("repair0original", graph)
        self.assertIn("repair1original", graph)
        self.assertIn("[v0][v1]concat", graph)


if __name__ == "__main__":
    unittest.main()
