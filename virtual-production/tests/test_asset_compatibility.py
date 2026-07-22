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

from story_video.asset_compatibility import (  # noqa: E402
    RECEIPT_CONTRACT,
    REVIEW_CONTRACT,
    build_review_packet,
    review_path,
    validate_compatibility_review,
    write_review_packet,
)
from story_video.seed_master_runtime import SeedMasterRuntimeError, sha256_file  # noqa: E402


def _fixture(root: Path) -> tuple:
    catalog = {
        "assets": {
            "lion-injured": {
                "type": "character",
                "description_en": "Lion with a swollen right eyelid and light bleeding at the outer corner.",
                "appearance_state_en": "right eyelid swollen after the mosquito sting",
                "body_topology": {
                    "total_limb_count": 4,
                    "limb_sets": [{"kind_en": "legs", "count": 4}],
                },
                "visual": {"uri": "https://example.test/lion-injured.png"},
            }
        }
    }
    catalog_path = root / "assets/assets.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    prompt = (
        "Operation: Multimodal reference, 8 seconds, 16:9, 1080p, native audio on.\n\n"
        "Use @Image1 for Lion's identity and swollen right eyelid only.\n\n"
        "Scene: A daylight forest clearing below a root throne.\n\n"
        "Shot 1: The locked camera watches Lion cover his swollen right eye and kneel.\n\n"
        "Style and image quality: Warm daylight and crisp eye detail.\n\n"
        "Constraints and end state: Subtitle-free, no logo, no watermark; end with Lion kneeling."
    )
    parsed = {
        "segment_id": "segment-001",
        "script_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "private_plan_sha256": "b" * 64,
        "prompt": prompt,
        "metadata": {"source_storyboard_sha256": "a" * 64},
        "bindings": [
            {
                "binding_id": "B01",
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "element": "lion-injured.identity_and_visible_state",
                "shot_scope": ["Shot 1"],
                "authority": "Lion identity and swollen right eyelid",
                "forbidden": "healthy eye or different character",
            }
        ],
    }
    plan = {
        "media_bindings": [
            {
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "source_kind": "asset_catalog",
                "namespace": "lion-injured",
                "asset_id": "lion-injured",
                "uri": "https://example.test/lion-injured.png",
            }
        ]
    }
    return parsed, plan, catalog


class AssetCompatibilityTests(unittest.TestCase):
    def test_body_topology_stays_private_and_is_not_required_in_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parsed, plan, catalog = _fixture(root)
            packet = build_review_packet(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
        self.assertNotIn("body_topology_contract", parsed["prompt"])
        self.assertEqual(
            packet["media_inputs"][0]["catalog_semantics"]["body_topology"]["total_limb_count"],
            4,
        )

    def test_location_fixed_set_semantics_reach_compatibility_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parsed, plan, catalog = _fixture(root)
            catalog["assets"]["loc-room"] = {
                "type": "location_master",
                "description_en": "A stable family sitting room.",
                "included_prop_ids": [],
                "embedded_npc_asset_ids": [],
                "independent_performer_asset_ids": ["lion-injured"],
                "fixed_set_elements_en": [
                    "A low wooden table remains fixed between both seats."
                ],
                "visual": {"uri": "https://example.test/room.png"},
            }
            parsed["bindings"][0]["element"] = "loc-room.fixed_set"
            plan["media_bindings"][0].update(
                namespace="loc-room",
                asset_id="loc-room",
                uri="https://example.test/room.png",
            )
            packet = build_review_packet(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )

        self.assertEqual(
            packet["media_inputs"][0]["catalog_semantics"][
                "fixed_set_elements_en"
            ],
            ["A low wooden table remains fixed between both seats."],
        )
        self.assertEqual(
            packet["media_inputs"][0]["catalog_semantics"][
                "independent_performer_asset_ids"
            ],
            ["lion-injured"],
        )

    def test_legacy_location_role_list_is_rejected_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parsed, plan, catalog = _fixture(root)
            catalog["assets"]["loc-room"] = {
                "type": "location_master",
                "description_en": "A stale room master with an ambiguous cast.",
                "included_prop_ids": [],
                "included_role_asset_ids": ["lion-injured"],
                "fixed_set_elements_en": [],
                "visual": {"uri": "https://example.test/room.png"},
            }
            parsed["bindings"][0]["element"] = "loc-room.dressed_set"
            plan["media_bindings"][0].update(
                namespace="loc-room",
                asset_id="loc-room",
                uri="https://example.test/room.png",
            )
            with self.assertRaisesRegex(
                SeedMasterRuntimeError, "lacks current production-design role treatment"
            ):
                build_review_packet(
                    task_dir=root,
                    parsed=parsed,
                    provisional_plan=plan,
                    catalog=catalog,
                    repository_root=root,
                )

    def test_wrong_private_namespace_is_rejected_without_rewriting_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parsed, plan, catalog = _fixture(root)
            plan["media_bindings"][0]["namespace"] = "elephant"
            with self.assertRaisesRegex(SeedMasterRuntimeError, "Prompt expects assets"):
                build_review_packet(
                    task_dir=root,
                    parsed=parsed,
                    provisional_plan=plan,
                    catalog=catalog,
                    repository_root=root,
                )

    def test_current_semantic_pass_returns_v3_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parsed, plan, catalog = _fixture(root)
            packet = build_review_packet(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
            packet_file = write_review_packet(root, packet)
            media = packet["media_inputs"][0]
            review = {
                "contract": REVIEW_CONTRACT,
                "segment_id": "segment-001",
                "packet_sha256": sha256_file(packet_file),
                "reviewer_role": "virtual_production_prompt_asset_semantic_reviewer",
                "review_scope": "final_seedance_prompt_against_assets_json_semantics",
                "media_reviews": [
                    {
                        "provider_token": "@Image1",
                        "catalog_semantics_sha256": media["semantic_authority"]["catalog_semantics_sha256"],
                        "inspection_method": "assets_json_semantic_comparison",
                        "required_facts": ["Lion has a swollen right eyelid."],
                        "catalog_facts": ["The selected asset declares the swollen right eyelid."],
                        "compatibility_class": "exact_state_match",
                        "conflict_domains": [],
                        "verdict": "compatible",
                        "reason": "The declared identity and injury state match.",
                    }
                ],
                "source_requirement_reviews": [],
                "overall_verdict": "PASS",
                "failures": [],
                "rework": {
                    "owner_department": "none",
                    "restart_from": "none",
                    "affected_asset_ids": [],
                    "required_actions": [],
                },
            }
            path = review_path(root, "segment-001")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(review), encoding="utf-8")
            receipt = validate_compatibility_review(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
        self.assertEqual(receipt["contract"], RECEIPT_CONTRACT)


if __name__ == "__main__":
    unittest.main()
