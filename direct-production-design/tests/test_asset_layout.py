from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.asset_catalog import (  # noqa: E402
    ASSET_CATALOG_RELATIVE_PATH,
    ASSET_MEDIA_RELATIVE_PATH,
)


class AssetLayoutTests(unittest.TestCase):
    def test_catalog_and_media_have_single_non_shared_roots(self) -> None:
        self.assertEqual(
            ASSET_CATALOG_RELATIVE_PATH,
            Path("direct-production-design/assets.json"),
        )
        self.assertEqual(
            ASSET_MEDIA_RELATIVE_PATH,
            Path("direct-production-design/assets"),
        )


if __name__ == "__main__":
    unittest.main()
