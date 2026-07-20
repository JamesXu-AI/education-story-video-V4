from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.runtime_support import StoryVideoError  # noqa: E402
from story_video import character_performance_map  # noqa: E402
from story_video.screenplay_contract import parse_screenplay_markdown  # noqa: E402


VALID_SCREENPLAY = """# Cinematic Widescreen Production Script: Map Lesson

## Production Information

| Field | Value |
| --- | --- |
| Production Type | cinematic_widescreen |
| Genre | Children's educational adventure |
| Estimated Runtime Seconds | 8 |
| Target Language | English |
| Target Age Band | younger_5_8 |
| Educational Theme | Careful observation supports safer choices. |
| Story Premise | Owl must compare two river marks before choosing a route. |
| Dramatic Strategy | One physical comparison turns uncertainty into a confident decision. |
| Safety and Culture | Keep the lesson gentle, respectful, and free from imitable danger. |
| Opening Event | Two similar marks leave Owl poised over the wrong route. |
| Ending Event and Obligation | Owl traces the verified path and settles on the supported answer. |

## Characters

| Entity ID | Character | Story Role | Narrative Function | Kind | Recurring | Group Role | Member Types | Narration | Description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| owl | Owl | lead | Discovers and applies the useful river clue. | individual | no | none | none | allowed | A patient learner who checks physical evidence before deciding. |

## Script

## Scene Unit 1 — The River Clue

### Scene Unit Information

| Field | Value |
| --- | --- |
| Segment ID | segment-001 |
| Scene ID | scene-001 |
| Slugline | INT. FOREST CLASSROOM - MORNING |
| Duration Seconds | 8 |
| Workload | mixed_dialogue_action |
| Environment | A quiet forest classroom centered on a low map table. |
| Dramatic Purpose | Owl turns a confusing mark into a usable route decision. |
| Start State | state-001 |
| End State | state-002 |
| Incoming Boundary | opening |

### Shot Execution

| Shot ID | Beat ID | Scale / View | Duration Seconds | Performers | Dramatic Change | Objective / Tactic | Visual Action | Important Reaction | Blocking / Movement | Gaze / Addressee | Completion State | Audience Focus | BGM / SFX / Ambience | Dialogue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-001 | BEAT-001A | close_up | 4 | owl | Two confusing curves become one testable comparison. | Owl rotates the map to align the river bends. | Owl turns the map clockwise and stops his finger where the two curves match. | Owl's hesitation tightens into focused certainty. | Owl remains at the near table edge, rotates the map toward himself, then settles his hand above the matched bends. | owl -> self (facing=down toward the map surface, gaze=tracks the paired river bends) | completed: The bends align beneath Owl's still finger. | The audience registers the exact physical clue that resolves the confusion. | AMBIENCE: Leaves tap softly against the classroom window. | L-001; speaker=owl; gate=The paired river bends align under Owl's finger; delivery=quietly certain; text="The river bends behind us." |
| A-002 | BEAT-001B | insert | 4 | owl | The comparison becomes a committed route choice. | Owl traces the verified path to record his decision. | Owl draws one continuous line from the matched bend to the wooden route marker. | Owl releases a small breath when the line reaches the marker. | Owl's finger travels from the map center to the right-edge marker and stops there, leaving his body anchored at the near edge. | owl -> route-marker (facing=angled across the table toward the right edge, gaze=follows his finger to the wooden marker) | completed: Owl's finger rests on the verified route marker. | The audience sees the observation produce a concrete and repeatable choice. | BGM ENTERS: A light wooden pulse confirms the completed reasoning without overpowering the room. | none |

### Character Staging

| Entity ID | Presence | Appearance | Trigger | Entry Path / Opening Position | First Visible Shot | First Visible Moment | Landing Shot | Landing Moment / Result | Speaks | Lines | State Change | Action Shots |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| owl | on_screen | present_at_open | opening | Owl stands at the near edge of the low map table with both river marks within reach. | A-001 | t=0.0s: Owl is already visible at the near table edge. | A-001 | t=0.6s: Owl remains visibly settled before rotating the map. | yes | L-001 | yes | A-001,A-002 |

## Continuity Appendix

### Environments

| Environment ID | Logical Environment | Scene IDs | INT/EXT | Time Context | Environment Facts | Story Function |
| --- | --- | --- | --- | --- | --- | --- |
| environment-001 | Forest classroom | scene-001 | INT | morning | A low map table anchors a quiet room beside one leaf-brushed window. | The fixed map lets observation produce a visible decision. |

### Scenes

| Scene ID | Segment IDs | Primary Time | Primary Place | Narrative Event | Entry Boundary | Entry Reason | Continuity Reference Segment | Continuity Reference Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scene-001 | segment-001 | morning | forest classroom | Owl aligns the river bends and commits to the supported route. | opening | The film begins at the unresolved comparison. | none | none |

### Scene Dramatic Contracts

| Scene ID | Purpose | Character Objective | Obstacle | Power Relationship | Turning Point | Outcome | Spatial Progression | Exit Impulse |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scene-001 | Turn observation into a practical route choice. | Owl must identify which trail follows the mapped river. | Two similar marks initially support different paths. | The confusing map controls Owl until he physically compares the bends. | Rotating the map aligns the two matching curves. | Owl chooses the route supported by visible evidence. | Attention travels from the map center to the right-edge route marker. | Owl's finger settles on the verified route marker. |

### Continuity States

| State ID | Parent State | Changed Facts | Change Reason |
| --- | --- | --- | --- |
| state-001 | none | Owl studies an unresolved map beside an unchosen route marker. | The film opens before Owl recognizes the matching river bend. |
| state-002 | state-001 | Owl knows and physically marks the evidence-supported route. | Aligning the bends resolves the route decision. |

### Continuity Boundaries

| Boundary ID | From Segment | To Segment | From State | To State | Handoff | Transition | Dramatic Reason | Audio Handoff | Continuity Handoff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""


class StagingContractTests(unittest.TestCase):
    def test_complete_table_script_parses_without_filling_content(self) -> None:
        parsed = parse_screenplay_markdown(VALID_SCREENPLAY)
        segment = parsed["segments"][0]
        self.assertEqual(segment["shots"][0]["scale_view"], "close_up")
        self.assertEqual(segment["shots"][0]["duration_seconds"], 4.0)
        self.assertEqual(
            segment["performance_calls"][0]["appearance_trigger_en"], "opening"
        )
        self.assertEqual(
            segment["performance_calls"][0]["first_visible_moment_en"],
            "t=0.0s: Owl is already visible at the near table edge.",
        )
        self.assertEqual(
            segment["shots"][0]["gaze_relations"]["owl"]["target"], "self"
        )
        self.assertEqual(
            segment["shots"][-1]["completion_state_en"],
            "completed: Owl's finger rests on the verified route marker.",
        )

    def test_authored_tables_feed_the_downstream_performance_map(self) -> None:
        parsed = parse_screenplay_markdown(VALID_SCREENPLAY)
        with patch.object(
            character_performance_map, "load_screenplay_file", return_value=parsed
        ):
            result = character_performance_map.load_character_performance_map(
                Path("/tmp/table-script-contract-test")
            )
        call = result["scene_segment_calls"][0]["calls"][0]
        self.assertEqual(call["line_ids"], ["L-001"])
        self.assertEqual(
            call["action_shot_ids"], ["A-001", "A-002"]
        )

    def test_present_at_open_requires_authored_opening_trigger(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "| owl | on_screen | present_at_open | opening |",
            "| owl | on_screen | present_at_open | none |",
        )
        with self.assertRaisesRegex(StoryVideoError, "Trigger must be opening"):
            parse_screenplay_markdown(invalid)

    def test_landing_result_cannot_be_missing_or_filled_by_code(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "| A-001 | t=0.6s: Owl remains visibly settled before rotating the map. |",
            "| A-001 | none |",
        )
        with self.assertRaisesRegex(StoryVideoError, "Landing Moment / Result"):
            parse_screenplay_markdown(invalid)

    def test_present_at_open_must_be_visible_at_zero_seconds(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "t=0.0s: Owl is already visible at the near table edge.",
            "t=0.8s: Owl becomes visible at the near table edge.",
        )
        with self.assertRaisesRegex(StoryVideoError, "first visible at t=0.0s"):
            parse_screenplay_markdown(invalid)

    def test_entrance_cannot_claim_first_visibility_at_zero_seconds(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "| owl | on_screen | present_at_open | opening |",
            "| owl | on_screen | enters | A branch snap draws Owl into the room. |",
        )
        with self.assertRaisesRegex(StoryVideoError, "must follow t=0.0s"):
            parse_screenplay_markdown(invalid)

    def test_first_visible_time_must_fall_inside_referenced_shot(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "t=0.0s: Owl is already visible at the near table edge.",
            "t=5.0s: Owl becomes visible at the near table edge.",
        ).replace(
            "t=0.6s: Owl remains visibly settled before rotating the map.",
            "t=5.5s: Owl settles at the near table edge.",
        ).replace(
            "present_at_open | opening", "enters | A branch snap draws Owl inside"
        )
        with self.assertRaisesRegex(StoryVideoError, "outside its referenced Shot"):
            parse_screenplay_markdown(invalid)

    def test_gaze_table_must_cover_every_visible_performer(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "owl -> self (facing=down toward the map surface, gaze=tracks the paired river bends)",
            "none",
        )
        with self.assertRaisesRegex(StoryVideoError, "Gaze / Addressee"):
            parse_screenplay_markdown(invalid)

    def test_dialogue_requires_same_shot_speaker_gaze_and_addressee(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "speaker=owl", "speaker=rabbit", 1
        )
        with self.assertRaisesRegex(StoryVideoError, "speaker staging or gaze"):
            parse_screenplay_markdown(invalid)

    def test_final_action_cannot_remain_open(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "completed: Owl's finger rests on the verified route marker.",
            "open: Owl's finger is still traveling toward the route marker.",
        )
        with self.assertRaisesRegex(StoryVideoError, "final Scene Unit"):
            parse_screenplay_markdown(invalid)

    def test_scene_unit_requires_authored_native_audio(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "AMBIENCE: Leaves tap softly against the classroom window.", "none"
        ).replace(
            "BGM ENTERS: A light wooden pulse confirms the completed reasoning without overpowering the room.",
            "none",
        )
        with self.assertRaisesRegex(StoryVideoError, "authored audio event"):
            parse_screenplay_markdown(invalid)

    def test_shot_durations_must_equal_scene_unit_duration(self) -> None:
        invalid = VALID_SCREENPLAY.replace(
            "| A-002 | BEAT-001B | insert | 4 |",
            "| A-002 | BEAT-001B | insert | 3 |",
        )
        with self.assertRaisesRegex(StoryVideoError, "Shot durations"):
            parse_screenplay_markdown(invalid)


if __name__ == "__main__":
    unittest.main()
