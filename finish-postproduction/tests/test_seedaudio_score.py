from __future__ import annotations

import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


DEPARTMENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = DEPARTMENT_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import generate_seedaudio_score as score_module  # noqa: E402
import finish_postproduction as finish_module  # noqa: E402
from generate_seedaudio_score import (  # noqa: E402
    MusicProductionError,
    build_cue_schedule,
    build_mix_filter,
    audio_conform_plan,
    cue_prompt,
    load_music_production,
    theme_prompt,
    validate_native_audio_track,
    validate_no_seedance_background_music,
)


class SeedAudioScoreContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_music_production(
            DEPARTMENT_ROOT / "assets" / "music-production.json"
        )

    def test_asset_is_valid_v2_story_score_plan(self) -> None:
        self.assertEqual(self.config["contract"], "finish-music-production/v2")
        self.assertEqual(self.config["music_provider"], "seedaudio")
        self.assertEqual(self.config["cues"][-1]["cadence"], "final")

    def test_fixed_length_seedaudio_output_is_trimmed_without_large_tempo_shift(self) -> None:
        head = audio_conform_plan(
            63.0,
            20.0,
            context="carry cue",
            trim_strategy="head",
        )
        tail = audio_conform_plan(
            63.0,
            20.0,
            context="final cue",
            trim_strategy="tail",
        )
        self.assertEqual(head["mode"], "trim")
        self.assertEqual(head["source_start_seconds"], 0.0)
        self.assertEqual(tail["mode"], "trim")
        self.assertEqual(tail["source_start_seconds"], 43.0)

    def test_schedule_partitions_picture_lock_at_next_cue_start(self) -> None:
        anchors = [
            {
                "segment_id": "segment-001",
                "timeline_in_seconds": 0.0,
                "timeline_out_seconds": 10.0,
            },
            {
                "segment_id": "segment-002",
                "timeline_in_seconds": 9.5,
                "timeline_out_seconds": 20.0,
            },
            {
                "segment_id": "segment-003",
                "timeline_in_seconds": 20.0,
                "timeline_out_seconds": 30.0,
            },
        ]
        schedule = build_cue_schedule(
            self.config,
            anchors,
            picture_duration=30.0,
        )
        self.assertEqual(schedule[0]["timeline_out_seconds"], 9.5)
        self.assertEqual(schedule[1]["timeline_in_seconds"], 9.5)
        self.assertEqual(schedule[-1]["timeline_out_seconds"], 30.0)
        rendered_total = sum(
            float(item["rendered_duration_seconds"]) for item in schedule
        )
        crossfade_total = (
            len(schedule) - 1
        ) * self.config["mix"]["cue_crossfade_seconds"]
        self.assertAlmostEqual(rendered_total - crossfade_total, 30.0)

    def test_no_background_music_gate_requires_script_and_submitted_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            scripts = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "seedance-segment-scripts"
            )
            generation = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "generation-segments"
                / "segment-001"
            )
            scripts.mkdir(parents=True)
            generation.mkdir(parents=True)
            (scripts / "segment-001.md").write_text(
                "# Segment\n- `seedance_background_music`: false\n",
                encoding="utf-8",
            )
            (generation / "seedance-request.json").write_text(
                json.dumps(
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": "Generate synchronized dialogue and ambience. No background music.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            evidence = validate_no_seedance_background_music(
                task_dir,
                scripts_dir=scripts,
                segment_ids=[1],
            )
            self.assertEqual(evidence[0]["submitted_prompt_contract"], "no_background_music")

            (generation / "seedance-request.json").write_text(
                json.dumps({"content": [{"type": "text", "text": "Add ambience."}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MusicProductionError, "submitted_prompt_allows_background_music"
            ):
                validate_no_seedance_background_music(
                    task_dir,
                    scripts_dir=scripts,
                    segment_ids=[1],
                )

    def test_explicit_baked_seedance_music_blocks_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            scripts = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "seedance-segment-scripts"
            )
            generation = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "generation-segments"
                / "segment-001"
            )
            scripts.mkdir(parents=True)
            generation.mkdir(parents=True)
            (scripts / "segment-001.md").write_text(
                "- seedance_background_music: true\nNo background music.\n",
                encoding="utf-8",
            )
            (generation / "seedance-request.json").write_text(
                json.dumps(
                    {
                        "content": [
                            {"type": "text", "text": "No background music."}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MusicProductionError, "segment_script_configuration"
            ):
                validate_no_seedance_background_music(
                    task_dir,
                    scripts_dir=scripts,
                    segment_ids=[1],
                )

    def test_native_track_accepts_only_authored_overlap_and_no_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source1 = root / "segment-001.mp4"
            source2 = root / "segment-002.mp4"
            source1.write_bytes(b"media-one")
            source2.write_bytes(b"media-two")
            timeline = {
                "tracks": [
                    {
                        "track_id": "native-sync",
                        "events": [
                            {
                                "segment_id": "segment-001",
                                "source": str(source1),
                                "has_source_audio": True,
                                "preserve_lip_sync": True,
                                "transition_overlap_allowed": False,
                                "timeline_in_seconds": 0.0,
                                "timeline_out_seconds": 10.0,
                            },
                            {
                                "segment_id": "segment-002",
                                "source": str(source2),
                                "has_source_audio": True,
                                "preserve_lip_sync": True,
                                "transition_overlap_allowed": True,
                                "timeline_in_seconds": 9.5,
                                "timeline_out_seconds": 20.0,
                            },
                        ],
                    }
                ]
            }
            result = validate_native_audio_track(
                timeline,
                segment_count=2,
                picture_duration=20.0,
            )
            self.assertEqual(result["status"], "complete")
            timeline["tracks"][0]["events"][1]["timeline_in_seconds"] = 10.5
            with self.assertRaisesRegex(MusicProductionError, "without gaps"):
                validate_native_audio_track(
                    timeline,
                    segment_count=2,
                    picture_duration=20.0,
                )

    def test_mix_filter_ducks_only_score_and_normalizes_program(self) -> None:
        filter_graph = build_mix_filter(self.config["mix"])
        self.assertIn("[scorepre][dialoguekey]sidechaincompress=", filter_graph)
        self.assertIn("[native][score]amix=", filter_graph)
        self.assertIn("loudnorm=I=-16.00", filter_graph)
        self.assertNotIn("[native]dialoguenhance", filter_graph)

    def test_theme_and_cue_prompts_assign_soundtrack_master_role(self) -> None:
        theme = theme_prompt(
            "Test Story",
            15.0,
            self.config["theme"],
            self.config["cues"],
        )
        cue = self.config["cues"][0]
        cue_text = cue_prompt(
            cue=cue,
            rendered_duration=11.0,
            segment_summaries=["The character discovers the story's central question."],
            segment_anchors=[
                {
                    "timeline_in_seconds": 0.0,
                    "timeline_out_seconds": 10.0,
                }
            ],
            cue_timeline_in=0.0,
            cue_timeline_out=10.0,
            overlap_seconds=2.0,
            is_final_cue=False,
        )
        for prompt in (theme, cue_text):
            self.assertTrue(
                prompt.startswith("You are a world-class cinematic soundtrack master")
            )
            self.assertIn("emotionally breathtaking", prompt)
            self.assertIn("never substitute raw loudness", prompt)
            self.assertNotIn("dubbing master", prompt.lower())
            self.assertLessEqual(len(prompt), 2900)

    def test_validate_only_executes_complete_pre_provider_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            finish_root = task_dir / "finish-postproduction"
            scripts = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "seedance-segment-scripts"
            )
            generation = (
                task_dir
                / ".pending"
                / "virtual-production"
                / "generation-segments"
            )
            finish_root.mkdir(parents=True)
            scripts.mkdir(parents=True)
            (finish_root / "music-production.json").write_text(
                json.dumps(self.config),
                encoding="utf-8",
            )
            picture_lock = task_dir / "native-picture-lock.mp4"
            picture_lock.write_bytes(b"picture-lock")
            records = []
            native_events = []
            anchors = []
            for segment_id in range(1, 4):
                segment_name = f"segment-{segment_id:03d}"
                source = task_dir / f"{segment_name}.mp4"
                source.write_bytes(b"segment-media")
                records.append((segment_id, source, 10.0))
                start = float((segment_id - 1) * 10)
                end = float(segment_id * 10)
                native_events.append(
                    {
                        "segment_id": segment_name,
                        "source": str(source),
                        "has_source_audio": True,
                        "preserve_lip_sync": True,
                        "transition_overlap_allowed": False,
                        "timeline_in_seconds": start,
                        "timeline_out_seconds": end,
                    }
                )
                anchors.append(
                    {
                        "segment_id": segment_name,
                        "timeline_in_seconds": start,
                        "timeline_out_seconds": end,
                        "midpoint_seconds": start + 5.0,
                    }
                )
                (scripts / f"{segment_name}.md").write_text(
                    "- `seedance_background_music`: false\n",
                    encoding="utf-8",
                )
                request_dir = generation / segment_name
                request_dir.mkdir(parents=True)
                (request_dir / "seedance-request.json").write_text(
                    json.dumps(
                        {
                            "content": [
                                {"type": "text", "text": "No background music."}
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
            picture_edl = {
                "duration_seconds": 30.0,
                "picture_events": [
                    {
                        "segment_id": anchor["segment_id"],
                        "timeline_in_seconds": anchor["timeline_in_seconds"],
                        "timeline_out_seconds": anchor["timeline_out_seconds"],
                    }
                    for anchor in anchors
                ],
            }
            audio_timeline = {
                "tracks": [
                    {"track_id": "native-sync", "events": native_events}
                ],
            }
            args = SimpleNamespace(
                task_dir=task_dir,
                video=picture_lock,
                timeout=60,
                regenerate=False,
                validate_only=True,
            )
            output = io.StringIO()
            with (
                patch.object(score_module, "segment_videos", return_value=records),
                patch.object(
                    score_module,
                    "load_timeline_artifacts",
                    return_value=(picture_edl, audio_timeline),
                ),
                patch.object(score_module, "media_duration", return_value=30.0),
                redirect_stdout(output),
            ):
                result = score_module.execute(args)
            self.assertEqual(result, 0)
            validation = json.loads(output.getvalue())
            self.assertEqual(validation["status"], "MUSIC_PLAN_VALID")
            self.assertEqual(len(validation["cue_schedule"]), 3)

    def test_main_finish_ignores_music_plan_and_promotes_native_picture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory).resolve()
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "voice_audio_source": "speaker_reference_audio",
                        "dialogue_source": "seedance",
                    }
                ),
                encoding="utf-8",
            )
            delivery_root = task_dir / "finish-postproduction"
            delivery_root.mkdir()
            (delivery_root / "music-production.json").write_text(
                "this deliberately invalid experimental plan must not be read",
                encoding="utf-8",
            )
            manifest = {
                "audio_sources": {
                    "voice_audio_source": "speaker_reference_audio",
                    "dialogue_source": "seedance",
                    "native_background_audio_source": "seedance_ambience_and_foley_no_music",
                    "seedance_background_music": False,
                    "background_music_source": "none",
                },
                "boundary_qc": {
                    "manifest": str(task_dir / "boundary-qc-manifest.json"),
                    "pre_assembly_status": "ready_for_picture_lock",
                    "final_timeline_status": "technical_audit_complete",
                    "planned_repair_count": 0,
                    "source_segments_mutated": False,
                },
            }
            (delivery_root / "final-delivery-manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            picture_lock = task_dir / "native-picture-lock.mp4"
            clean_master = delivery_root / "final-clean-master.mp4"
            with (
                patch.object(finish_module, "assemble", return_value=picture_lock),
                patch.object(
                    finish_module,
                    "_promote_clean_master",
                    return_value=clean_master,
                ) as promote,
                patch.object(
                    finish_module,
                    "build",
                    return_value={"status": "FINAL_MASTER_READY"},
                ),
            ):
                result = finish_module.finish(task_dir)
            promote.assert_called_once_with(task_dir, picture_lock)
            self.assertEqual(result["background_music_source"], "none")


if __name__ == "__main__":
    unittest.main()
