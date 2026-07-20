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
    emit_resolution_rework,
    rework_path,
    review_path,
    validate_compatibility_review,
    write_review_packet,
)
from story_video.seed_master_runtime import SeedMasterRuntimeError, sha256_file  # noqa: E402


BODY_TOPOLOGY = {
    "body_plan_en": "upright bipedal anthropomorphic actor",
    "total_limb_count": 4,
    "limb_sets": [
        {"kind_en": "legs", "count": 2, "function_en": "support"},
        {"kind_en": "upper paws", "count": 2, "function_en": "gesture"},
    ],
    "non_limb_appendages": [{"kind_en": "tail", "count": 1}],
    "topology_lock_en": "Exactly two legs and two upper paws; four total limbs.",
}


def _fixture(root: Path, *, asset_id: str, asset: dict) -> tuple[dict, dict, dict]:
    assets = {asset_id: asset}
    if asset["type"] == "character":
        asset["body_topology"] = BODY_TOPOLOGY
        owner_id = asset_id
    else:
        owner_id = asset["character_id"]
        assets[owner_id] = {
            "type": "character",
            "description_en": "Owning character identity.",
            "body_topology": BODY_TOPOLOGY,
        }
    catalog = {"assets": assets}
    catalog_path = root / "assets/assets.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    manifest_path = root / "previsualize-cinematography/storyboard-compile-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement_id": "REQ-LION-STATE",
                        "category": "wardrobe_prop",
                        "segment_id": "segment-001",
                        "shot_ids": ["SH-001"],
                        "source_text": "The visibly injured defeated Lion remains injured.",
                        "preservation": "semantic",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    topology_contract = {
        "asset_id": asset_id,
        "body_topology": BODY_TOPOLOGY,
        "character_id": owner_id,
    }
    prompt = (
        "Show the visibly injured defeated Lion and preserve the injury state.\n"
        "- body_topology_contract: "
        + json.dumps(
            topology_contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    parsed = {
        "segment_id": "segment-001",
        "script_sha256": hashlib.sha256(b"script").hexdigest(),
        "prompt": prompt,
        "metadata": {
            "source_storyboard_sha256": "a" * 64,
            "source_manifest_sha256": "b" * 64,
            "storyboard_requirement_ids": ["REQ-LION-STATE"],
        },
        "bindings": [
            {
                "binding_id": "B01",
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "element": f"{asset_id}.identity_and_visible_state",
                "shot_scope": ["Shot 1"],
                "authority": "Lion identity and exact visible state",
                "forbidden": "contradictory injury or costume state",
            }
        ],
    }
    plan = {
        "media_bindings": [
            {
                "provider_token": "@Image1",
                "provider_role": "reference_image",
                "source_kind": "asset_catalog",
                "namespace": asset_id,
                "asset_id": asset_id,
                "uri": asset["visual"]["uri"],
            }
        ]
    }
    return parsed, plan, catalog


def _write_review(
    root: Path,
    packet: dict,
    *,
    compatible: bool,
    required: str,
    catalog_fact: str,
) -> None:
    packet_file = write_review_packet(root, packet)
    asset_id = packet["media_inputs"][0]["catalog_semantics"]["asset_id"]
    review = {
        "contract": REVIEW_CONTRACT,
        "segment_id": "segment-001",
        "packet_sha256": sha256_file(packet_file),
        "reviewer_role": "virtual_production_prompt_asset_semantic_reviewer",
        "review_scope": "final_seedance_prompt_against_assets_json_semantics",
        "media_reviews": [
            {
                "provider_token": "@Image1",
                "catalog_semantics_sha256": packet["media_inputs"][0][
                    "semantic_authority"
                ]["catalog_semantics_sha256"],
                "inspection_method": "assets_json_semantic_comparison",
                "required_facts": [required],
                "catalog_facts": [catalog_fact],
                "compatibility_class": (
                    "exact_state_match" if compatible else "conflicting"
                ),
                "conflict_domains": [] if compatible else ["injury_body_state"],
                "verdict": "compatible" if compatible else "incompatible",
                "reason": (
                    "assets.json declares the exact defeated injury state required by the Prompt."
                    if compatible
                    else "assets.json declares a normal healthy Lion and contradicts the required injury state."
                ),
            }
        ],
        "source_requirement_reviews": [
            {
                "requirement_id": "REQ-LION-STATE",
                "asset_relevance": "relevant",
                "provider_tokens": ["@Image1"],
                "verdict": "compatible" if compatible else "incompatible",
                "reason": (
                    "The assets.json appearance-state declaration satisfies the requirement."
                    if compatible
                    else "The assets.json character declaration contradicts the injury requirement."
                ),
            }
        ],
        "overall_verdict": "PASS" if compatible else "FAIL",
        "failures": [] if compatible else [{"reason": "injury state mismatch"}],
        "rework": (
            {
                "owner_department": "none",
                "restart_from": "none",
                "affected_asset_ids": [],
                "required_actions": [],
            }
            if compatible
            else {
                "owner_department": "direct-production-design",
                "restart_from": "production-design-plan",
                "affected_asset_ids": [asset_id],
                "required_actions": [
                    "Create and bind the Lion's exact injured appearance-state asset in assets.json."
                ],
            }
        ),
    }
    path = review_path(root, "segment-001")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review), encoding="utf-8")


class AssetCompatibilityTests(unittest.TestCase):
    def test_visible_character_binding_without_exact_body_topology_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = {
                "type": "character",
                "description_en": "Normal healthy Lion portrait.",
                "visual": {"uri": "https://example.test/lion.png"},
            }
            parsed, plan, catalog = _fixture(root, asset_id="lion", asset=asset)
            parsed["prompt"] = "Show the current Lion and reject anatomy errors."
            with self.assertRaisesRegex(
                SeedMasterRuntimeError, "does not carry the exact current body topology"
            ):
                build_review_packet(
                    task_dir=root,
                    parsed=parsed,
                    provisional_plan=plan,
                    catalog=catalog,
                    repository_root=root,
                )

    def test_wrong_lion_binding_is_blocked_when_prompt_binding_requires_elephant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = {
                "type": "character",
                "description_en": "Normal healthy Lion portrait.",
                "visual": {"uri": "https://example.test/lion.png"},
            }
            parsed, plan, catalog = _fixture(root, asset_id="lion", asset=asset)
            parsed["bindings"][0]["element"] = "elephant.identity_and_visible_state"
            parsed["bindings"][0]["authority"] = "Elephant identity"
            with self.assertRaisesRegex(
                SeedMasterRuntimeError,
                "Prompt expects assets.*elephant.*selects assets.json asset 'lion'",
            ) as raised:
                build_review_packet(
                    task_dir=root,
                    parsed=parsed,
                    provisional_plan=plan,
                    catalog=catalog,
                    repository_root=root,
                )
            path = emit_resolution_rework(
                task_dir=root,
                parsed=parsed,
                error=raised.exception,
            )
            rework = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(rework["status"], "BLOCKED_ASSET_SEMANTICS_INCOMPATIBLE")
        self.assertEqual(rework["failures"][0]["provider_token"], "@Image1")
        self.assertEqual(rework["affected_asset_ids"], ["elephant", "lion"])

    def test_exact_injured_lion_assets_json_row_can_receive_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = {
                "type": "costume",
                "description_en": "Defeated Lion with visible non-graphic injury.",
                "character_id": "lion",
                "appearance_state_en": "Injured and defeated.",
                "authority": "character_costume_and_appearance_state",
                "visual": {"uri": "https://example.test/lion-defeated.png"},
            }
            parsed, plan, catalog = _fixture(
                root, asset_id="costume-lion-defeated", asset=asset
            )
            packet = build_review_packet(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
            _write_review(
                root,
                packet,
                compatible=True,
                required="The Lion is visibly injured and defeated.",
                catalog_fact="appearance_state_en declares Injured and defeated.",
            )
            receipt = validate_compatibility_review(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
        self.assertEqual(receipt["overall_verdict"], "PASS")
        self.assertEqual(receipt["contract"], RECEIPT_CONTRACT)

    def test_normal_lion_assets_json_row_is_blocked_for_injured_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = {
                "type": "character",
                "description_en": "Normal healthy final-look Lion portrait.",
                "visual": {"uri": "https://example.test/lion-normal.png"},
            }
            parsed, plan, catalog = _fixture(root, asset_id="lion", asset=asset)
            packet = build_review_packet(
                task_dir=root,
                parsed=parsed,
                provisional_plan=plan,
                catalog=catalog,
                repository_root=root,
            )
            _write_review(
                root,
                packet,
                compatible=False,
                required="The Lion is visibly injured and defeated.",
                catalog_fact="description_en declares a normal healthy final-look Lion.",
            )
            with self.assertRaises(SeedMasterRuntimeError):
                validate_compatibility_review(
                    task_dir=root,
                    parsed=parsed,
                    provisional_plan=plan,
                    catalog=catalog,
                    repository_root=root,
                )
            rework = json.loads(
                rework_path(root, "segment-001").read_text(encoding="utf-8")
            )
        self.assertEqual(rework["status"], "BLOCKED_ASSET_SEMANTICS_INCOMPATIBLE")
        self.assertEqual(rework["owner_department"], "direct-production-design")
        self.assertEqual(rework["affected_asset_ids"], ["lion"])
        self.assertIn("injury_body_state", rework["failures"][0]["conflict_domains"])


if __name__ == "__main__":
    unittest.main()
