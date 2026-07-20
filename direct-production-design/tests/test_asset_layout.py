from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_catalog import (  # noqa: E402
    ASSET_CATALOG_RELATIVE_PATH,
    ASSET_MEDIA_RELATIVE_PATH,
    reject_task_local_asset_state,
)
from story_video.asset_support import StoryVideoError  # noqa: E402
from story_video.visual_asset_generation import (  # noqa: E402
    VisualAssetGenerationError,
    _final_output_path,
)


class AssetLayoutTests(unittest.TestCase):
    def test_catalog_and_media_have_one_repository_owned_root(self) -> None:
        self.assertEqual(
            ASSET_CATALOG_RELATIVE_PATH,
            Path("assets/assets.json"),
        )
        self.assertEqual(
            ASSET_MEDIA_RELATIVE_PATH,
            Path("assets"),
        )

    def test_deleted_task_local_contract_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "direct-production-design/assets.json"
            stale.parent.mkdir(parents=True)
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaises(StoryVideoError):
                reject_task_local_asset_state(root)

    def test_generator_can_write_only_inside_repository_asset_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset_root = root / "assets"
            accepted = _final_output_path(
                asset_root, asset_root / "characters/subject/identity.png"
            )
            self.assertEqual(
                accepted,
                (asset_root / "characters/subject/identity.png").resolve(),
            )
            with self.assertRaises(VisualAssetGenerationError):
                _final_output_path(
                    asset_root,
                    root / "runtime/tasks/example/direct-production-design/assets/image.png",
                )


if __name__ == "__main__":
    unittest.main()
