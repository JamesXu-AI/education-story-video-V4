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

from story_video.aesthetic_reference import (  # noqa: E402
    AestheticReferenceError,
    load_aesthetic_reference,
)


POLICY = {
    "source_video_generation_allowed": False,
    "selected_frame_generation_allowed": False,
    "selected_frame_direct_downstream_allowed": False,
    "downstream_reference_authority": "project-textual-visual-contract-only",
    "copy_reference_identity_composition_or_story_action": False,
}


class AestheticReferenceTests(unittest.TestCase):
    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "story-task"
        package = root / "direct-production-design" / "aesthetic-reference"
        frames = package / "source-frames"
        frames.mkdir(parents=True)
        study = package / "study.md"
        study.write_text("# Study\n", encoding="utf-8")
        frame = frames / "frame.png"
        frame.write_bytes(b"stable-frame-evidence")
        digest = hashlib.sha256(frame.read_bytes()).hexdigest()
        manifest = {
            "contract": "task-aesthetic-reference",
            "version": 1,
            "task_id": "story-task",
            "study_path": "direct-production-design/aesthetic-reference/study.md",
            "source_video": {
                "path": "/offline/reference.mp4",
                "sha256": "1" * 64,
                "usage": "offline-aesthetic-analysis-only-never-generation-input",
            },
            "reference_policy": dict(POLICY),
            "selected_frames": [
                {
                    "frame_id": "frame-01",
                    "timestamp_seconds": 1.0,
                    "path": "direct-production-design/aesthetic-reference/source-frames/frame.png",
                    "sha256": digest,
                    "reference_roles_en": ["general material and palette evidence"],
                }
            ],
            "style_translation": {
                "prompt_core_en": "Translate only general aesthetic evidence.",
                "preserve_project_locks_en": ["Story outranks reference."],
                "forbidden_imports_en": ["Do not copy identity."],
            },
        }
        (package / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return temporary, root, frame

    def test_valid_package_validates_frames_without_exposing_generation_paths(self) -> None:
        temporary, root, _ = self._fixture()
        self.addCleanup(temporary.cleanup)
        value = load_aesthetic_reference(root)
        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value["reference_count"], 1)
        self.assertNotIn("selected_frames", value)
        self.assertNotIn("resolved_reference_images", value)

    def test_relaxed_source_policy_is_rejected(self) -> None:
        temporary, root, _ = self._fixture()
        self.addCleanup(temporary.cleanup)
        path = root / "direct-production-design/aesthetic-reference/manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["reference_policy"]["selected_frame_generation_allowed"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(
            AestheticReferenceError, "offline-analysis-only boundary"
        ):
            load_aesthetic_reference(root)

    def test_frame_tampering_is_rejected(self) -> None:
        temporary, root, frame = self._fixture()
        self.addCleanup(temporary.cleanup)
        frame.write_bytes(b"replaced-frame")
        with self.assertRaisesRegex(AestheticReferenceError, "integrity check"):
            load_aesthetic_reference(root)

if __name__ == "__main__":
    unittest.main()
