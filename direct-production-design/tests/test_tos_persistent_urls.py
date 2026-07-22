from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from providers import tos_storage  # noqa: E402
from story_video.asset_catalog import _require_http_uri  # noqa: E402
from story_video.asset_support import StoryVideoError  # noqa: E402


class TosPersistentUrlTests(unittest.TestCase):
    def test_provider_tos_signature_is_removed_from_persistent_url(self) -> None:
        signed = (
            "https://bucket.tos-ap-southeast-1.volces.com/folder/image.png"
            "?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Signature=secret"
        )
        self.assertEqual(
            tos_storage.persistent_tos_url(signed),
            "https://bucket.tos-ap-southeast-1.volces.com/folder/image.png",
        )

    def test_public_url_is_derived_from_bucket_endpoint_and_key(self) -> None:
        environment = {
            "STORAGE_TOS_REGION": "ap-southeast-3",
            "STORAGE_TOS_ENDPOINT": "tos-ap-southeast-3.bytepluses.com",
            "STORAGE_TOS_BUCKET": "project-assets",
            "STORAGE_TOS_ACCESS_KEY_ID": "test-access",
            "STORAGE_TOS_SECRET_ACCESS_KEY": "test-secret",
            "STORAGE_TOS_KEY_PREFIX": "seed",
        }
        with patch.dict("os.environ", environment, clear=False):
            self.assertEqual(
                tos_storage.tos_public_url("inputs/audio/voice sample.wav"),
                "https://project-assets.tos-ap-southeast-3.bytepluses.com/"
                "inputs/audio/voice%20sample.wav",
            )
            self.assertEqual(
                tos_storage.production_asset_key(
                    "character", "actor-a", "identity.png"
                ),
                "seed/production-assets/character/actor-a/identity.png",
            )

    def test_uploaded_provider_input_uses_public_url_without_presigning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "voice.wav"
            source.write_bytes(b"RIFF")
            with patch.object(
                tos_storage,
                "tos_upload_path",
                return_value={
                    "key": "inputs/audio/voice.wav",
                    "public_url": (
                        "https://bucket.tos-ap-southeast-3.bytepluses.com/"
                        "inputs/audio/voice.wav"
                    ),
                },
            ), patch.object(
                tos_storage,
                "tos_presign",
                side_effect=AssertionError("asset flows must not presign"),
            ):
                resolved = tos_storage.resolve_input(
                    str(source), kind="audio", upload_local=True
                )
        self.assertEqual(
            resolved,
            "https://bucket.tos-ap-southeast-3.bytepluses.com/inputs/audio/voice.wav",
        )

    def test_catalog_rejects_query_signed_uri(self) -> None:
        with self.assertRaisesRegex(StoryVideoError, "persistent unsigned URL"):
            _require_http_uri(
                "https://bucket.tos-ap-southeast-3.bytepluses.com/image.png"
                "?X-Tos-Signature=secret",
                "asset visual.uri",
            )


if __name__ == "__main__":
    unittest.main()
