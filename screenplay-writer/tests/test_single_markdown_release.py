from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_screenplay import _require_single_release_file  # noqa: E402
from story_video.runtime_support import StoryVideoError  # noqa: E402
from story_video.screenplay_contract import parse_screenplay_markdown  # noqa: E402


class SingleMarkdownReleaseTests(unittest.TestCase):
    def test_current_release_accepts_only_screenplay_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "screenplay.md").write_text("screenplay", encoding="utf-8")

            _require_single_release_file(output)

    def test_check_rejects_any_second_release_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "screenplay.md").write_text("screenplay", encoding="utf-8")
            (output / "notes.md").write_text("duplicate authority", encoding="utf-8")

            with self.assertRaisesRegex(StoryVideoError, "only screenplay.md"):
                _require_single_release_file(output)

    def test_screenplay_rejects_embedded_json_before_schema_parse(self) -> None:
        with self.assertRaisesRegex(StoryVideoError, "no embedded JSON"):
            parse_screenplay_markdown(
                '# Seedance Screenplay: Example\n\nA serialized object follows: {"key": "value"}\n'
            )


if __name__ == "__main__":
    unittest.main()
