#!/usr/bin/env python3
"""Validate voices in ``direct-production-design/assets.json``."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import wave
from pathlib import Path, PurePosixPath
from typing import Any, Dict


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
SHARED_RUNTIME_ROOT = SCRIPT_ROOT.parents[1] / "scripts"
for script_root in (SCRIPT_ROOT, SHARED_RUNTIME_ROOT):
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))

from story_video.asset_support import StoryVideoError  # noqa: E402
from story_video.asset_catalog import (  # noqa: E402
    ASSET_CATALOG_RELATIVE_PATH,
    load_asset_catalog,
)


class VoiceAuthorityError(StoryVideoError):
    """Raised when task-local voice evidence is missing or inconsistent."""


EXPECTED_SAMPLE_RATE_HZ = 48000
EXPECTED_CHANNELS = 2
EXPECTED_CODEC = "pcm_s16le"
EXPECTED_BRIEF_CONTRACT = "voice-reference-brief/dynamic-duration"
EXPECTED_RESPONSE_CONTRACT = "voice-reference-generation-response/dynamic-duration"
EXPECTED_DURATION_POLICY = "natural_duration_from_exact_sample_text"
MAX_EDGE_SILENCE_SECONDS = 1.0
MAX_INTERNAL_WORD_GAP_SECONDS = 0.6
DURATION_TOLERANCE_SECONDS = 0.02


def _catalog_reference_file(task_root: Path, raw_path: Any, label: str) -> Path:
    """Resolve a path already admitted by the strict asset-catalog loader."""

    if not isinstance(raw_path, str) or not raw_path:
        raise VoiceAuthorityError(f"{label} is missing from the normalized asset catalog.")
    portable = PurePosixPath(raw_path)
    try:
        resolved = task_root.joinpath(*portable.parts).resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise VoiceAuthorityError(f"{label} cannot be inspected: {raw_path}") from exc
    if not resolved.is_file():
        raise VoiceAuthorityError(f"{label} must identify a regular file: {raw_path}")
    return resolved


def _pcm_data_size(path: Path) -> int:
    """Return real PCM payload bytes, including streamed WAVs with 0xffffffff sizes."""
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12 or header[:4] not in (b"RIFF", b"RF64") or header[8:] != b"WAVE":
            raise VoiceAuthorityError("Not a RIFF/RF64 WAV file: %s" % path)
        while source.tell() + 8 <= file_size:
            chunk_id = source.read(4)
            size_bytes = source.read(4)
            if len(chunk_id) != 4 or len(size_bytes) != 4:
                break
            declared_size = struct.unpack("<I", size_bytes)[0]
            payload_offset = source.tell()
            if chunk_id == b"data":
                available = file_size - payload_offset
                return available if declared_size == 0xFFFFFFFF else min(declared_size, available)
            if declared_size == 0xFFFFFFFF:
                raise VoiceAuthorityError("Indeterminate non-audio WAV chunk in %s." % path)
            source.seek(declared_size + (declared_size % 2), 1)
    raise VoiceAuthorityError("WAV evidence has no audio data chunk: %s" % path)


def _wav_evidence(path: Path) -> Dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_rate = source.getframerate()
            sample_width = source.getsampwidth()
            compression = source.getcomptype()
    except (OSError, EOFError, wave.Error) as exc:
        raise VoiceAuthorityError("Invalid WAV evidence at %s: %s" % (path, exc))
    if compression != "NONE":
        raise VoiceAuthorityError("Voice evidence must be uncompressed PCM WAV: %s" % path)
    codec_by_width = {1: "pcm_u8", 2: "pcm_s16le", 3: "pcm_s24le", 4: "pcm_s32le"}
    codec = codec_by_width.get(sample_width)
    block_align = channels * sample_width
    pcm_data_size = _pcm_data_size(path)
    if codec is None or sample_rate <= 0 or block_align <= 0 or pcm_data_size <= 0:
        raise VoiceAuthorityError("Unsupported or empty WAV evidence at %s." % path)
    if pcm_data_size % block_align:
        raise VoiceAuthorityError("PCM payload is not aligned to complete sample frames: %s" % path)
    sample_frames = pcm_data_size // block_align
    return {
        "duration_seconds": round(sample_frames / float(sample_rate), 6),
        "byte_size": path.stat().st_size,
        "audio_stream": {
            "codec": codec,
            "sample_rate_hz": sample_rate,
            "channels": channels,
        },
    }


def _expected_words(text: str) -> list[str]:
    return [
        "".join(character.casefold() for character in token if character.isalnum())
        for token in re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text, flags=re.UNICODE)
    ]


def _validate_dynamic_timing(
    *, asset_id: str, sample_text: str, response: Any, audio_duration: float
) -> None:
    if not isinstance(response, dict) or (
        response.get("contract") != EXPECTED_RESPONSE_CONTRACT
        or response.get("entity_id") != asset_id
        or response.get("duration_policy") != EXPECTED_DURATION_POLICY
        or response.get("time_scale_factor") != 1.0
    ):
        raise VoiceAuthorityError(
            f"character {asset_id} lacks current dynamic-duration response evidence"
        )
    final_duration = response.get("final_duration_seconds")
    if (
        isinstance(final_duration, bool)
        or not isinstance(final_duration, (int, float))
        or abs(float(final_duration) - audio_duration) > DURATION_TOLERANCE_SECONDS
    ):
        raise VoiceAuthorityError(
            f"character {asset_id} response duration does not match its voice WAV"
        )
    timing = response.get("word_timing")
    words = timing.get("words") if isinstance(timing, dict) else None
    if (
        not isinstance(timing, dict)
        or timing.get("expected_text") != sample_text
        or not isinstance(words, list)
        or not words
    ):
        raise VoiceAuthorityError(
            f"character {asset_id} lacks exact sample word timing"
        )
    actual_words: list[str] = []
    previous_end = 0.0
    previous_start = 0.0
    max_gap = 0.0
    first_start = None
    last_end = None
    for index, word in enumerate(words):
        if not isinstance(word, dict) or not isinstance(word.get("text"), str):
            raise VoiceAuthorityError(
                f"character {asset_id} has invalid sample word timing"
            )
        start = word.get("start_seconds")
        end = word.get("end_seconds")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or start < 0
            or end <= start
            or end > audio_duration + DURATION_TOLERANCE_SECONDS
            or (index and start < previous_start)
        ):
            raise VoiceAuthorityError(
                f"character {asset_id} has word timing outside its voice WAV"
            )
        if index:
            max_gap = max(max_gap, float(start) - previous_end)
        else:
            first_start = float(start)
        previous_end = float(end)
        previous_start = float(start)
        last_end = float(end)
        actual_words.append(
            "".join(
                character.casefold()
                for character in word["text"]
                if character.isalnum()
            )
        )
    if actual_words != _expected_words(sample_text):
        raise VoiceAuthorityError(
            f"character {asset_id} spoken words differ from its sample text"
        )
    trailing_silence = audio_duration - float(last_end)
    if (
        float(first_start) > MAX_EDGE_SILENCE_SECONDS
        or trailing_silence > MAX_EDGE_SILENCE_SECONDS
        or max_gap > MAX_INTERNAL_WORD_GAP_SECONDS
    ):
        raise VoiceAuthorityError(
            f"character {asset_id} has an anomalous pause around or inside its sample text"
        )


def validate_voice_authority(task_root: Path) -> Dict[str, Any]:
    task_root = task_root.expanduser().resolve()
    try:
        catalog = load_asset_catalog(task_root)
    except StoryVideoError as exc:
        raise VoiceAuthorityError(str(exc)) from exc

    validated: list[Dict[str, Any]] = []
    for asset_id, asset in sorted(catalog["assets"].items()):
        if asset.get("type") != "character" or "voice" not in asset:
            continue
        voice = asset["voice"]
        reference = voice["reference"]
        audio_path = _catalog_reference_file(
            task_root,
            reference.get("path"),
            f"character {asset_id} voice.reference.path",
        )
        evidence = _wav_evidence(audio_path)
        stream = evidence["audio_stream"]
        if (
            stream["codec"] != EXPECTED_CODEC
            or stream["sample_rate_hz"] != EXPECTED_SAMPLE_RATE_HZ
            or stream["channels"] != EXPECTED_CHANNELS
        ):
            raise VoiceAuthorityError(
                f"character {asset_id} voice must be {EXPECTED_CODEC}, "
                f"{EXPECTED_SAMPLE_RATE_HZ} Hz, {EXPECTED_CHANNELS} channels"
            )
        brief_path = audio_path.parent / "voice.brief.json"
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VoiceAuthorityError(
                f"character {asset_id} lacks current voice sample brief"
            ) from exc
        if (
            not isinstance(brief, dict)
            or brief.get("contract") != EXPECTED_BRIEF_CONTRACT
            or brief.get("entity_id") != asset_id
            or not isinstance(brief.get("sample_text_en"), str)
            or not brief["sample_text_en"].strip()
            or brief.get("output", {}).get("duration_policy")
            != EXPECTED_DURATION_POLICY
            or "duration_seconds" in brief.get("output", {})
        ):
            raise VoiceAuthorityError(
                f"character {asset_id} voice sample brief is stale or incomplete"
            )
        response_path = audio_path.parent / "voice.response.json"
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VoiceAuthorityError(
                f"character {asset_id} lacks current voice response evidence"
            ) from exc
        _validate_dynamic_timing(
            asset_id=asset_id,
            sample_text=brief["sample_text_en"],
            response=response,
            audio_duration=evidence["duration_seconds"],
        )
        validated.append(
            {
                "asset_id": asset_id,
                "name": asset_id,
                "reference_path": reference["path"],
                "sample_text_en": brief["sample_text_en"],
                "evidence": evidence,
            }
        )

    return {
        "result": "PASS",
        "catalog_path": str((task_root / ASSET_CATALOG_RELATIVE_PATH).resolve()),
        "speaker_count": len(validated),
        "remote_service_calls": 0,
        "speakers": validated,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_voice_authority(args.task_dir)
    except VoiceAuthorityError as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
