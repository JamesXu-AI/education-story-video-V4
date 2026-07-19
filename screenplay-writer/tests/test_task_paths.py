from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.task_paths import TaskPathError, validate_root_files  # noqa: E402


class TaskRootFileValidationTests(unittest.TestCase):
    def test_operating_system_metadata_does_not_block_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "task.json").write_text("{}", encoding="utf-8")
            (root / "story.md").write_text("story", encoding="utf-8")
            for filename in (".DS_Store", "Thumbs.db", "desktop.ini", "._story.md"):
                (root / filename).write_bytes(b"metadata")

            validate_root_files(root)

    def test_real_extra_task_root_file_is_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "task.json").write_text("{}", encoding="utf-8")
            (root / "story.md").write_text("story", encoding="utf-8")
            (root / "notes.txt").write_text("not an authority", encoding="utf-8")

            with self.assertRaisesRegex(TaskPathError, "notes.txt"):
                validate_root_files(root)


if __name__ == "__main__":
    unittest.main()
