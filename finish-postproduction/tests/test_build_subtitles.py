from __future__ import annotations

import sys
from pathlib import Path
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_subtitles import _caption_chunks, _caption_intervals  # noqa: E402


class SubtitleChunkingTests(unittest.TestCase):
    def test_oversized_latin_sentence_is_balanced(self) -> None:
        text = (
            "You are strong and king here, my lord, but strength gives you no right "
            "to oppress the weak."
        )
        chunks = _caption_chunks(
            text,
            is_cjk=False,
            line_limit=42,
            max_lines=2,
        )
        self.assertEqual(" ".join(chunk for chunk, _ in chunks), text)
        self.assertEqual(len(chunks), 2)
        word_counts = [len(chunk.split()) for chunk, _ in chunks]
        self.assertLessEqual(max(word_counts) - min(word_counts), 1)
        intervals = _caption_intervals(
            1.976,
            8.899,
            chunks,
            is_cjk=False,
            minimum_duration=0.8,
        )
        self.assertTrue(all(end - start >= 0.8 for start, end in intervals))


if __name__ == "__main__":
    unittest.main()
