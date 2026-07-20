from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.screenplay_contract import parse_screenplay_markdown  # noqa: E402
from test_staging_contract import VALID_SCREENPLAY  # noqa: E402


WRITER_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_FIELDS = {
    "action_blocks",
    "blocks",
    "character_entity_ids",
    "characters_json",
    "compact_refs",
    "derived_continuity",
    "dialogue_addresses",
    "dramatic_beats_json",
    "entity_label_en",
    "end_state_json",
    "episode_information",
    "incoming_visual_requirement",
    "narration_scope_en",
    "scene_dramatic_contract_json",
    "seedance_mapping",
    "segment_boundary_policy",
    "segment_duration_policy",
    "speaker_cue_en",
    "spoken_entries",
    "start_state_json",
    "story_contract",
    "total_duration_seconds",
    "transition_design_json",
}


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result.update(nested_keys(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(nested_keys(child))
        return result
    return set()


class NoAutomaticAuthorshipTests(unittest.TestCase):
    def test_parser_does_not_create_legacy_or_composed_screenplay_fields(self) -> None:
        screenplay = parse_screenplay_markdown(VALID_SCREENPLAY)

        self.assertFalse(SYNTHETIC_FIELDS & nested_keys(screenplay))
        self.assertNotIn("performance_entities", screenplay)
        self.assertNotIn("total_duration_seconds", screenplay)

    def test_writer_validation_code_never_writes_screenplay_markdown(self) -> None:
        for relative in (
            "scripts/build_screenplay.py",
            "scripts/story_video/screenplay_contract.py",
            "scripts/story_video/character_performance_map.py",
        ):
            with self.subTest(relative=relative):
                source = (WRITER_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn("write_text(", source)
                self.assertNotIn("write_bytes(", source)
                self.assertNotIn("_authored_transition", source)
                self.assertNotIn("_authored_final_transition", source)

    def test_current_prompt_layers_contain_no_retired_requirement_history(self) -> None:
        sources = (
            WRITER_ROOT / "SKILL.md",
            WRITER_ROOT / "references/prompts/story_to_screenplay_gen.md",
            WRITER_ROOT / "references/screenplay-segment-contract.md",
        )
        retired = (
            "spec screenplay",
            "audio-timeline.json",
            "superseded requirement",
            "compatibility prose",
            "template filler",
        )
        for path in sources:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8").casefold()
                for phrase in retired:
                    self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
