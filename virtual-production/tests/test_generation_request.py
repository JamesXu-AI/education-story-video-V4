from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import generate_segment_videos as generation_module  # noqa: E402
from generate_segment_videos import (  # noqa: E402
    _storyboard_topological_waves,
    request_payload,
)


class GenerationRequestTests(unittest.TestCase):
    def test_video_extension_request_keeps_location_image_and_predecessor_video(self) -> None:
        prompt = "Continue the action in the approved room with no additional people."
        parameters = {
            "model": "seedance-test-model",
            "duration": 8,
            "resolution": "720p",
            "ratio": "16:9",
            "generate_audio": True,
            "watermark": False,
            "return_last_frame": True,
            "execution_expires_after": 172800,
            "priority": 0,
        }
        media_bindings = [
            {
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "source_kind": "asset_catalog",
            },
            {
                "provider_token": "@Video1",
                "provider_role": "reference_video",
                "source_kind": "complete_predecessor_video",
            },
        ]
        segment = {
            "generation_task_id": "segment-002",
            "prompt": prompt,
            "references": [
                {
                    **media_bindings[0],
                    "asset_id": "location-room",
                    "uri": "https://example.test/location-room.png",
                }
            ],
            "audio_references": [],
            "runtime_media": [media_bindings[1]],
            "execution_plan": {
                "media_bindings": media_bindings,
                "asset_compatibility": {
                    "contract": "prompt-assets-json-compatibility-receipt-v3",
                    "overall_verdict": "PASS",
                    "final_prompt_sha256": hashlib.sha256(
                        prompt.encode("utf-8")
                    ).hexdigest(),
                },
            },
            "seedance_parameters": parameters,
        }
        runtime_content = [
            {
                "type": "video_url",
                "video_url": {"url": "https://example.test/predecessor.mp4"},
                "role": "reference_video",
                "_provider_token": "@Video1",
            }
        ]
        with tempfile.TemporaryDirectory() as directory, patch.object(
            generation_module,
            "_runtime_reference_media_content",
            return_value=runtime_content,
        ):
            payload = request_payload(
                segment,
                task_dir=Path(directory),
                resolution="720p",
                ratio="16:9",
            )
        self.assertEqual(
            [item.get("role") for item in payload["content"][1:]],
            ["reference_image", "reference_video"],
        )

    def test_request_uses_materialized_values_and_provider_token_order(self) -> None:
        parameters = {
            "model": "seedance-test-model",
            "duration": 8,
            "resolution": "1080p",
            "ratio": "16:9",
            "generate_audio": True,
            "watermark": False,
            "return_last_frame": True,
            "execution_expires_after": 172800,
            "priority": 0,
        }
        media_bindings = [
            {
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "source_kind": "asset_catalog",
            },
            {
                "provider_token": "@Audio1",
                "provider_role": "reference_audio",
                "source_kind": "asset_catalog",
            },
        ]
        prompt = (
            "Operation: Multimodal reference, 8 seconds, 16:9, 1080p, native audio on.\n\n"
            "Use the room in @Image1 for layout. Use @Audio1 only for the hero's voice.\n\n"
            "Scene: A warm family room at evening.\n\n"
            "Shot 1: The locked camera watches the hero close a book and look up.\n\n"
            "Style and image quality: Warm natural contrast and clean facial detail.\n\n"
            "Constraints and end state: Subtitle-free, no logo, no watermark; end on the closed book."
        )
        segment = {
            "generation_task_id": "segment-001",
            "duration": 8,
            "prompt": prompt,
            "references": [
                {
                    **media_bindings[0],
                    "asset_id": "background-001",
                    "uri": "https://example.test/background.png",
                }
            ],
            "audio_references": [
                {
                    **media_bindings[1],
                    "asset_id": "hero",
                    "uri": "https://example.test/voice.wav",
                }
            ],
            "runtime_media": [],
            "execution_plan": {
                "media_bindings": media_bindings,
                "asset_compatibility": {
                    "contract": "prompt-assets-json-compatibility-receipt-v3",
                    "overall_verdict": "PASS",
                    "final_prompt_sha256": hashlib.sha256(
                        prompt.encode("utf-8")
                    ).hexdigest(),
                },
            },
            "seedance_parameters": parameters,
        }
        with tempfile.TemporaryDirectory() as directory:
            payload = request_payload(
                segment,
                task_dir=Path(directory),
                resolution="1080p",
                ratio="16:9",
            )
        self.assertEqual(payload["model"], "seedance-test-model")
        self.assertTrue(payload["generate_audio"])
        self.assertTrue(payload["return_last_frame"])
        self.assertEqual(payload["duration"], 8)
        self.assertEqual(
            [item["role"] for item in payload["content"] if "role" in item],
            ["reference_image", "reference_audio"],
        )

    def test_request_does_not_require_a_prompt_semantic_receipt(self) -> None:
        prompt = "Final Prompt requiring an injured exact-state character."
        segment = {
            "generation_task_id": "segment-001",
            "prompt": prompt,
            "references": [],
            "audio_references": [],
            "runtime_media": [],
            "execution_plan": {"media_bindings": []},
            "seedance_parameters": {
                "resolution": "1080p",
                "ratio": "16:9",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            payload = request_payload(
                segment,
                task_dir=Path(directory),
                resolution="1080p",
                ratio="16:9",
            )
        self.assertEqual(payload["content"], [{"type": "text", "text": prompt}])

    def test_scheduler_uses_only_seed_master_shooting_plan_dependencies(self) -> None:
        segments = [
            {
                "generation_task_id": "segment-001",
                "depends_on_segment_ids": [],
                "planned_wave": 0,
            },
            {
                "generation_task_id": "segment-002",
                "depends_on_segment_ids": ["segment-001"],
                "planned_wave": 1,
            },
            {
                "generation_task_id": "segment-003",
                "depends_on_segment_ids": [],
                "planned_wave": 0,
            },
            {
                "generation_task_id": "segment-004",
                "depends_on_segment_ids": ["segment-001"],
                "planned_wave": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            waves = _storyboard_topological_waves(
                segments, task_dir=Path(directory)
            )
        self.assertEqual(
            waves,
            [
                ["segment-001", "segment-003"],
                ["segment-002", "segment-004"],
            ],
        )

    def test_generation_completion_immediately_prepares_boundary_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            video = task_dir / "video.mp4"
            frame = task_dir / "last-frame.png"
            video.write_bytes(b"video")
            frame.write_bytes(b"frame")
            segment = {
                "generation_task_id": "segment-001",
                "planned_wave": 0,
                "depends_on_segment_ids": [],
            }
            result = {
                "segment_id": "segment-001",
                "provider_task_id": "task-1",
                "provider_attempt_id": "segment-001__attempt-0001",
                "seed_master_script_sha256": "a" * 64,
                "seedance_execution_plan_sha256": "b" * 64,
                "asset_compatibility_review_sha256": "c" * 64,
                "operation": "multimodal_reference",
                "video_path": str(video),
                "last_frame_path": str(frame),
                "status": "succeeded",
            }
            args = SimpleNamespace(
                task_dir=task_dir,
                max_concurrency=1,
                poll_interval=1.0,
                wait_timeout=10.0,
                timeout=10,
                segments=None,
            )
            check = {
                "boundary_id": "segment-000--segment-001",
                "from": "segment-000",
                "to": "segment-001",
                "technical_status": "postproduction_color_match_candidate",
                "blocks_downstream": False,
                "recommended_owner": "finish-postproduction",
                "record_path": str(task_dir / "technical-boundary-precheck.json"),
            }
            with (
                patch.object(
                    generation_module,
                    "_task_contract",
                    return_value={"resolution": "1080p", "ratio": "16:9"},
                ),
                patch.object(
                    generation_module,
                    "storyboard_segment_rows",
                    return_value=[{"segment_id": "segment-001"}],
                ),
                patch.object(
                    generation_module,
                    "discover_segments",
                    return_value=[segment],
                ),
                patch.object(
                    generation_module,
                    "_storyboard_topological_waves",
                    return_value=[["segment-001"]],
                ),
                patch.object(
                    generation_module,
                    "generate_one",
                    return_value=result,
                ),
                patch.object(
                    generation_module,
                    "prepare_adjacent_boundary_prechecks",
                    return_value=[check],
                ) as prepare,
            ):
                exit_code = generation_module.run(args)
            self.assertEqual(exit_code, 0)
            prepare.assert_called_once_with(
                task_dir.resolve(), "segment-001", ["segment-001"]
            )
            summary = json.loads(
                (
                    task_dir
                    / ".pending"
                    / "virtual-production"
                    / "segment-generation-summary.json"
                ).read_text()
            )
            self.assertEqual(summary["incremental_boundary_precheck_count"], 1)

    def test_large_incremental_jump_holds_later_generation_waves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            video = task_dir / "video.mp4"
            frame = task_dir / "last-frame.png"
            video.write_bytes(b"video")
            frame.write_bytes(b"frame")
            segment = {
                "generation_task_id": "segment-001",
                "planned_wave": 0,
                "depends_on_segment_ids": [],
            }
            result = {
                "segment_id": "segment-001",
                "provider_task_id": "task-1",
                "provider_attempt_id": "segment-001__attempt-0001",
                "seed_master_script_sha256": "a" * 64,
                "seedance_execution_plan_sha256": "b" * 64,
                "asset_compatibility_review_sha256": "c" * 64,
                "operation": "multimodal_reference",
                "video_path": str(video),
                "last_frame_path": str(frame),
                "status": "succeeded",
            }
            args = SimpleNamespace(
                task_dir=task_dir,
                max_concurrency=1,
                poll_interval=1.0,
                wait_timeout=10.0,
                timeout=10,
                segments=None,
            )
            hold = {
                "boundary_id": "segment-000--segment-001",
                "from": "segment-000",
                "to": "segment-001",
                "technical_status": "technical_hold_for_visual_review",
                "technical_reason": "large matched color jump",
                "blocks_downstream": True,
                "recommended_owner": "virtual-production",
                "record_path": str(task_dir / "technical-boundary-precheck.json"),
            }
            with (
                patch.object(
                    generation_module,
                    "_task_contract",
                    return_value={"resolution": "1080p", "ratio": "16:9"},
                ),
                patch.object(
                    generation_module,
                    "storyboard_segment_rows",
                    return_value=[{"segment_id": "segment-001"}],
                ),
                patch.object(
                    generation_module,
                    "discover_segments",
                    return_value=[segment],
                ),
                patch.object(
                    generation_module,
                    "_storyboard_topological_waves",
                    return_value=[["segment-001"]],
                ),
                patch.object(
                    generation_module,
                    "generate_one",
                    return_value=result,
                ),
                patch.object(
                    generation_module,
                    "prepare_adjacent_boundary_prechecks",
                    return_value=[hold],
                ),
            ):
                exit_code = generation_module.run(args)
            self.assertEqual(exit_code, 1)
            self.assertFalse(
                (task_dir / "virtual-production" / "generation-state.json").exists()
            )
            summary = json.loads(
                (
                    task_dir
                    / ".pending"
                    / "virtual-production"
                    / "segment-generation-summary.json"
                ).read_text()
            )
            self.assertEqual(summary["status"], "boundary_review_required")
            self.assertEqual(summary["boundary_review_hold_count"], 1)


if __name__ == "__main__":
    unittest.main()
