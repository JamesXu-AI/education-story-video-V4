from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from validate_storyboard import (  # noqa: E402
    StoryboardValidationError,
    _validate_location_state_plan,
    validate_storyboard,
)


STORYBOARD = """# Cinematic Storyboard: Test

## Project Direction

| Field | Value |
| --- | --- |
| Runtime | 8 seconds |

## Generation Plan

| Segment | Screenplay Range | Scene | Duration Seconds | Operation | Predecessor | Seam | Internal Shots | Packing Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A-001 | room | 8 | multimodal_reference | none | opening | 1 | one dramatic beat |

## Location State Plan

| Location State Chain | Segment | Relationship | State Source | Temporal Evidence | World and Population Evidence | Persistent Anchors | Allowed Changes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| family-room-evening | segment-001 | independent | none | none | approved location master with its embedded population | low table; armchair; window | book may close on screen |

## Generation Segment 1 — Request

### Segment Direction

| Field | Value |
| --- | --- |
| Segment ID | 1 |
| Location State Chain | family-room-evening |
| Temporal Continuity Evidence | None; this is the chain origin. |
| World and Population Evidence | The approved family-room Location master remains authoritative in every Shot. |
| Authorized Population | Uthman and Grandfather are independent performers; no embedded or additional people. |
| Persistent Anchors | Low table, armchair, and window. |
| Anchor Visibility Requirement | The table remains visible throughout. |

### Reference Plan

| Provider Token | Provider Role | Asset Namespace | Readable Subject | Purpose | Shot Scope | Forbidden Inheritance |
| --- | --- | --- | --- | --- | --- | --- |
| @Image1 | reference image | room | family room | layout | Shot 1 | people |

### Ordered Shots

| Shot | Screenplay Shot | Transition and Camera | Subject Action and Expression | Space, Blocking and Gaze | Persistent Anchors | Lighting and Color | Dialogue and Native Audio | Landing and Edit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Shot 1 | A-001 | Locked medium frame. | Uthman closes a book. | He looks at Grandfather. | Low table and armchair remain visible. | Warm side light. | Quiet room tone. | He settles. |

### Prompt Translation Notes

Prioritize the completed look and settled book.

## Continuity Review

| Boundary | From | To | Handoff Mode | Visible Inheritance | Audio Inheritance | Editorial Reason |
| --- | --- | --- | --- | --- | --- | --- |
| opening | none | 1 | independent | room | none | opening |
"""


class SingleStoryboardReleaseTests(unittest.TestCase):
    def _task(self, root: Path) -> Path:
        release = root / "previsualize-cinematography"
        release.mkdir()
        (release / "storyboard.md").write_text(STORYBOARD, encoding="utf-8")
        return root

    def test_accepts_exactly_one_markdown_storyboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = validate_storyboard(self._task(Path(directory)))
        self.assertEqual(result["status"], "PASS")

    def test_rejects_companion_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._task(Path(directory))
            (root / "previsualize-cinematography/manifest.json").write_text("{}")
            with self.assertRaisesRegex(StoryboardValidationError, "only storyboard.md"):
                validate_storyboard(root)

    def test_rejects_embedded_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._task(Path(directory))
            path = root / "previsualize-cinematography/storyboard.md"
            path.write_text(STORYBOARD + '\n{"id":"x"}\n', encoding="utf-8")
            with self.assertRaisesRegex(StoryboardValidationError, "JSON or YAML"):
                validate_storyboard(root)

    def test_rejects_nonadjacent_location_revisit_marked_independent(self) -> None:
        state_plan = """## Location State Plan

| Location State Chain | Segment | Relationship | State Source | Temporal Evidence | World and Population Evidence | Persistent Anchors | Allowed Changes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| room | segment-001 | independent | none | none | room location master | low table | none |
| forest | segment-002 | independent | none | none | forest location master | throne | none |
| room | segment-003 | independent | none | none | room location master | low table | none |
"""
        with self.assertRaisesRegex(StoryboardValidationError, "marked independent"):
            _validate_location_state_plan(state_plan, 3)

    def test_accepts_nonadjacent_location_revisit_with_latest_state_source(self) -> None:
        state_plan = """## Location State Plan

| Location State Chain | Segment | Relationship | State Source | Temporal Evidence | World and Population Evidence | Persistent Anchors | Allowed Changes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| room | segment-001 | independent | none | none | room location master | low table | none |
| forest | segment-002 | independent | none | none | forest location master | throne | none |
| room | segment-003 | nonadjacent_revisit | segment-001 | approved final state from segment-001 | room location master with its embedded population | low table | new camera only |
"""
        _validate_location_state_plan(state_plan, 3)

    def test_rejects_continuation_without_world_population_evidence(self) -> None:
        state_plan = """## Location State Plan

| Location State Chain | Segment | Relationship | State Source | Temporal Evidence | World and Population Evidence | Persistent Anchors | Allowed Changes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| room | segment-001 | independent | none | none | room location master | low table | none |
| room | segment-002 | adjacent_continuation | segment-001 | approved final state | none | low table | book closes |
"""
        with self.assertRaisesRegex(
            StoryboardValidationError, "world and population evidence"
        ):
            _validate_location_state_plan(state_plan, 2)


if __name__ == "__main__":
    unittest.main()
