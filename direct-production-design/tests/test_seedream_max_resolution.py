from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from providers.seedream import SEEDREAM_MAX_IMAGE_SIZE, build_parser  # noqa: E402
from story_video.visual_asset_generation import (  # noqa: E402
    DEFAULT_IMAGE_SIZE,
    build_provider_request,
)


class SeedreamMaximumResolutionTests(unittest.TestCase):
    def test_project_visual_assets_default_to_provider_maximum(self) -> None:
        self.assertEqual(SEEDREAM_MAX_IMAGE_SIZE, "2816x1584")
        self.assertEqual(DEFAULT_IMAGE_SIZE, SEEDREAM_MAX_IMAGE_SIZE)
        request = build_provider_request(
            prompt="A current task-authored visual asset.",
            reference_images=[],
            size=DEFAULT_IMAGE_SIZE,
        )
        self.assertEqual(request["size"], "2816x1584")
        self.assertEqual(request["output_format"], "png")

    def test_seedream_cli_uses_same_maximum_default(self) -> None:
        args = build_parser().parse_args(["generate", "--prompt", "test"])
        self.assertEqual(args.size, SEEDREAM_MAX_IMAGE_SIZE)


if __name__ == "__main__":
    unittest.main()
