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

from story_video.seed_master_runtime import (  # noqa: E402
    ACCEPTANCE_FIREWALL,
    PRESENTATION_FIREWALL,
    build_execution_plan,
    parse_segment_script,
)


def _script(*, serial: bool = False) -> str:
    if serial:
        status = "observed_adapted"
        schedule = "serial_after_predecessor_review"
        wave = 1
        dependencies = "[segment-001]"
        review = "true"
        evidence = "approved_final_2s_silent_plus_provider_last_frame"
        recompile = "true"
        editorial = "matched_cut"
        video_scope = "exact_final_2s_real_motion"
        video_audio = "stripped_for_matched_cut"
        bindings = (
            "- B01 | @Image1 | provider_role=reference_image | element=continuity.selected_boundary_visual_state | shot_scope=Shot 1 | authority=provider last frame only | forbidden=new action\n"
            "- B02 | @Video1 | provider_role=reference_video | element=continuity.selected_boundary_motion | shot_scope=Shot 1 | authority=terminal real motion only | forbidden=audio or replay"
        )
        binding_ids = "[B01, B02]"
        binding_count = 2
    else:
        status = "planned"
        schedule = "parallel"
        wave = 0
        dependencies = "[]"
        review = "false"
        evidence = "none"
        recompile = "false"
        editorial = "none"
        video_scope = "none"
        video_audio = "none"
        bindings = (
            "- B01 | @Image1 | provider_role=reference_image | element=location-001.architecture_material_light | shot_scope=Shot 1 | authority=set only | forbidden=people\n"
            "- B02 | @Audio1 | provider_role=reference_audio | element=hero.voice_timbre | shot_scope=Shot 1 | authority=timbre only | forbidden=source words"
        )
        binding_ids = "[B01, B02]"
        binding_count = 2
    return f"""# segment-002 — Test

```yaml
scene_ids: [scene-001]
segment_id: segment-002
source_storyboard_revision: approved-r1
source_storyboard_sha256: {'a' * 64}
source_manifest_sha256: {'b' * 64}
storyboard_line_ids: []
storyboard_beat_ids: [BEAT-01A]
storyboard_shot_ids: [SH-001]
storyboard_requirement_ids: [REQ-001]
shooting_plan_status: {status}
schedule_mode: {schedule}
planned_wave: {wave}
depends_on_segment_ids: {dependencies}
dependency_reason: exact authored seam requirement
predecessor_review_required: {review}
required_predecessor_evidence: {evidence}
successor_recompile_required: {recompile}
fallback_operation_and_story_cost: motivated cut with reduced motion continuity
operation: multimodal_reference
seam_class: motivated_coverage_cut
seam_resynthesis_allowed: true
seam_story_reason: transfer attention on the authored consequence
editorial_intent: {editorial}
reference_video_scope: {video_scope}
reference_video_audio: {video_audio}
camera_ensemble_color_resynthesis_allowed: true
target_duration: 8s
internal_shot_count: 1
internal_shot_order: [Shot 1]
reference_binding_count: {binding_count}
reference_binding_ids: {binding_ids}
continuity_status: planned
```

## Part 1 — Overall setup

### 1.0 Storyboard source coverage

- requirement_contract: {{"requirement_id":"REQ-001","source_text_sha256":"{'3' * 64}","target_part":"Part 1","target_shot_ids":[],"implementation":"Preserve the consequence."}}

### 1.1 Generation contract

Preserve the consequence.

{PRESENTATION_FIREWALL}

### 1.2 Task-local reference manifest

```text
{bindings}
```

### 1.3 Shot-reference matrix

- Shot 1 | active=B01=@Image1>asset,B02=@Audio1>asset | inactive=none

### 1.4 Continuity, space, performance, and sound contract

Maintain the authored state and native audio.

## Part 2 — Ordered internal shots and performance

### Shot 1 — shot_id=SH-001 | location_id=LOC-001 | camera_id=CAM-001 | panel_id=PNL-001

#### Active References

- bindings repeated exactly

#### Inactive/Forbidden References

- none

#### Storyboard Line Contracts

- none

#### Dramatic Action and Spatial Trace

- action_contract: source_beat=BEAT-01A; subject=hero; dramatic_cause=truth; objective_tactic=hold; body_part=eyes; action=active stillness; range=small; speed=still; force=controlled; continuity=held; audience_effect=understanding; landing=resolved
- facing_contract: source_beat=BEAT-01A; required=false; dramatic_function=orientation is irrelevant; start=not_applicable; relation=not_applicable; path=not_applicable; end=not_applicable; audience_effect=attention stays on the eyes

#### Direction

Hold the authored state with native synchronized sound, then settle.

## Part 3 — Continuity, audio, quality, and duration acceptance

{ACCEPTANCE_FIREWALL}
"""


class SeedMasterRuntimeTests(unittest.TestCase):
    def test_parallel_script_resolves_asset_catalog_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "segment-002.md"
            path.write_text(_script(), encoding="utf-8")
            parsed = parse_segment_script(path)
            plan = build_execution_plan(
                task_dir=root,
                parsed=parsed,
                catalog={
                    "assets": {
                        "location-001": {
                            "type": "location_master",
                            "visual": {"uri": "https://example.test/location.png"},
                        },
                        "hero": {
                            "type": "character",
                            "voice": {
                                "reference": {"uri": "https://example.test/hero.wav"}
                            },
                        },
                    }
                },
                capability_profile={
                    "contract": "seedance-capability-profile",
                    "profile_status": "VERIFIED",
                    "model_id": "seedance-test",
                    "provider_capabilities": {
                        "maximum_reference_images": 9,
                        "maximum_reference_videos": 3,
                        "maximum_reference_audios": 3,
                    },
                },
                task={"input": {"resolution": "1080p", "aspect_ratio": "16:9"}},
            )
        self.assertEqual(
            [item["provider_token"] for item in plan["media_bindings"]],
            ["@Image1", "@Audio1"],
        )
        self.assertEqual(
            plan["media_bindings"][0]["uri"],
            "https://example.test/location.png",
        )

    def test_dependent_script_locks_exact_predecessor_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "segment-002.md"
            path.write_text(_script(serial=True), encoding="utf-8")
            source = root / ".pending/virtual-production/generation-segments/segment-001"
            source.mkdir(parents=True)
            (source / "video.mp4").write_bytes(b"video")
            (source / "last-frame.png").write_bytes(b"frame")
            source_script = root / ".pending/virtual-production/seedance-segment-scripts/segment-001.md"
            source_script.parent.mkdir(parents=True)
            source_script.write_text("source Script", encoding="utf-8")
            source_plan = root / ".pending/virtual-production/seedance-execution-plans/segment-001.json"
            source_plan.parent.mkdir(parents=True)
            source_plan.write_text("{}", encoding="utf-8")
            script_sha = hashlib.sha256(source_script.read_bytes()).hexdigest()
            plan_sha = hashlib.sha256(source_plan.read_bytes()).hexdigest()
            for filename, value in (
                (
                    "production-record.json",
                    {
                        "status": "GENERATED",
                        "segment_id": "segment-001",
                        "provider_attempt_id": "segment-001__attempt-0002",
                        "seed_master_script_sha256": script_sha,
                        "seedance_execution_plan_sha256": plan_sha,
                    },
                ),
                (
                    "artifacts.json",
                    {"provider_attempt_id": "segment-001__attempt-0002"},
                ),
            ):
                (source / filename).write_text(json.dumps(value), encoding="utf-8")
            parsed = parse_segment_script(path)
            plan = build_execution_plan(
                task_dir=root,
                parsed=parsed,
                catalog={"assets": {}},
                capability_profile={
                    "contract": "seedance-capability-profile",
                    "profile_status": "VERIFIED",
                    "model_id": "seedance-test",
                    "provider_capabilities": {
                        "maximum_reference_images": 9,
                        "maximum_reference_videos": 3,
                        "maximum_reference_audios": 3,
                    },
                },
                task={"input": {"resolution": "1080p", "aspect_ratio": "16:9"}},
            )
        self.assertEqual(
            {item["source_kind"] for item in plan["media_bindings"]},
            {"provider_last_frame", "final_2s_silent_video"},
        )
        self.assertEqual(
            {item["source_provider_attempt_id"] for item in plan["media_bindings"]},
            {"segment-001__attempt-0002"},
        )


if __name__ == "__main__":
    unittest.main()
