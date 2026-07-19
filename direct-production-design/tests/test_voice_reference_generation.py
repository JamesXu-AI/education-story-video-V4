from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import wave


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from story_video.voice_reference_generation import (  # noqa: E402
    VoiceReferenceGenerationError,
    _normalize_to_contract,
    _subtitle_alignment,
    _wav_evidence,
)


class VoiceReferenceGenerationTests(unittest.TestCase):
    def _subtitle(
        self,
        *,
        first_start_ms: int = 200,
        last_end_ms: int = 2700,
        second_start_ms: int = 900,
    ):
        return {
            "text": "Every word fits now.",
            "sentences": [
                {
                    "words": [
                        {"text": "Every", "start_time": first_start_ms, "end_time": 800},
                        {"text": "word", "start_time": second_start_ms, "end_time": 1400},
                        {"text": "fits", "start_time": 1550, "end_time": 2100},
                        {"text": "now", "start_time": 2250, "end_time": last_end_ms},
                    ]
                }
            ],
        }

    def test_exact_words_use_the_provider_audios_dynamic_duration(self) -> None:
        alignment = _subtitle_alignment(
            self._subtitle(),
            expected_text="Every word fits now.",
            provider_duration_seconds=3.1,
        )

        self.assertEqual(alignment["word_count"], 4)
        self.assertEqual(alignment["audio_duration_seconds"], 3.1)
        self.assertEqual(alignment["first_word_start_seconds"], 0.2)
        self.assertEqual(alignment["last_word_end_seconds"], 2.7)
        self.assertEqual(alignment["trailing_silence_seconds"], 0.4)
        self.assertNotIn("normalization_speed_factor", alignment)

    def test_same_words_may_have_a_different_natural_total_duration(self) -> None:
        shorter = _subtitle_alignment(
            self._subtitle(last_end_ms=2500),
            expected_text="Every word fits now.",
            provider_duration_seconds=2.8,
        )
        longer = _subtitle_alignment(
            self._subtitle(last_end_ms=3100),
            expected_text="Every word fits now.",
            provider_duration_seconds=3.5,
        )

        self.assertEqual(shorter["audio_duration_seconds"], 2.8)
        self.assertEqual(longer["audio_duration_seconds"], 3.5)

    def test_pcm_normalization_preserves_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            source = Path(temporary_dir) / "source.wav"
            target = Path(temporary_dir) / "target.wav"
            source_rate = 24000
            source_duration = 2.375
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(source_rate)
                output.writeframes(b"\0\0" * int(source_rate * source_duration))

            final_duration = _normalize_to_contract(source, target)
            evidence = _wav_evidence(target)

        self.assertIsNotNone(evidence)
        self.assertAlmostEqual(final_duration, source_duration, places=3)
        self.assertAlmostEqual(evidence["duration_seconds"], source_duration, places=3)

    def test_missing_or_changed_sample_word_is_rejected(self) -> None:
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(),
                expected_text="Every changed word fits now.",
                provider_duration_seconds=3.1,
            )

    def test_word_timing_past_generated_audio_is_rejected(self) -> None:
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(last_end_ms=3100),
                expected_text="Every word fits now.",
                provider_duration_seconds=3.0,
            )

    def test_overlong_internal_pause_is_rejected(self) -> None:
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(second_start_ms=1450),
                expected_text="Every word fits now.",
                provider_duration_seconds=3.1,
            )

    def test_overlong_edge_silence_is_rejected(self) -> None:
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(first_start_ms=1100),
                expected_text="Every word fits now.",
                provider_duration_seconds=3.1,
            )
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(),
                expected_text="Every word fits now.",
                provider_duration_seconds=3.8,
            )

    def test_empty_provider_audio_is_rejected(self) -> None:
        with self.assertRaises(VoiceReferenceGenerationError):
            _subtitle_alignment(
                self._subtitle(),
                expected_text="Every word fits now.",
                provider_duration_seconds=0.0,
            )


if __name__ == "__main__":
    unittest.main()
