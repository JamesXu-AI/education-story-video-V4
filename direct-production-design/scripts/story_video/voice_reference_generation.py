"""Generate dialogue-identity voice references at their natural authored duration."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
import wave


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ASSET_CATALOG_RELATIVE_PATH = Path("assets/assets.json")
ASSET_MEDIA_RELATIVE_PATH = Path("assets")
PROVIDER_PATH = (
    REPOSITORY_ROOT
    / "finish-postproduction"
    / "scripts"
    / "providers"
    / "seedaudio.py"
)
PROVIDER_SPEC = importlib.util.spec_from_file_location(
    "story_video_voice_seedaudio", PROVIDER_PATH
)
if PROVIDER_SPEC is None or PROVIDER_SPEC.loader is None:
    raise RuntimeError(f"Cannot load repository Seed Audio provider: {PROVIDER_PATH}")
seedaudio = importlib.util.module_from_spec(PROVIDER_SPEC)
PROVIDER_SPEC.loader.exec_module(seedaudio)


VOICE_SAMPLE_RATE_HZ = 48000
VOICE_CHANNELS = 2
VOICE_SAMPLE_WIDTH_BYTES = 2
VOICE_MAX_GENERATION_ATTEMPTS = 3
VOICE_MAX_EDGE_SILENCE_SECONDS = 1.0
VOICE_MAX_INTERNAL_WORD_GAP_SECONDS = 0.6
VOICE_DURATION_TOLERANCE_SECONDS = 0.02
VOICE_BRIEF_CONTRACT = "voice-reference-brief/dynamic-duration"
VOICE_REQUEST_CONTRACT = "voice-reference-generation-request/dynamic-duration"
VOICE_RESPONSE_CONTRACT = "voice-reference-generation-response/dynamic-duration"
VOICE_DURATION_POLICY = "natural_duration_from_exact_sample_text"


class VoiceReferenceGenerationError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _wav_evidence(path: Path) -> dict[str, Any] | None:
    try:
        with wave.open(str(path), "rb") as source:
            if (
                source.getcomptype() != "NONE"
                or source.getframerate() != VOICE_SAMPLE_RATE_HZ
                or source.getnchannels() != VOICE_CHANNELS
                or source.getsampwidth() != VOICE_SAMPLE_WIDTH_BYTES
                or source.getnframes() <= 0
            ):
                return None
            return {
                "duration_seconds": source.getnframes() / float(source.getframerate()),
                "sample_frames": source.getnframes(),
            }
    except (FileNotFoundError, OSError, wave.Error):
        return None


def _existing_voice_is_current(
    path: Path,
    response: dict[str, Any] | None,
    *,
    entity_id: str,
    expected_text: str,
) -> bool:
    evidence = _wav_evidence(path)
    if evidence is None or not isinstance(response, dict):
        return False
    if (
        response.get("contract") != VOICE_RESPONSE_CONTRACT
        or response.get("entity_id") != entity_id
        or response.get("duration_policy") != VOICE_DURATION_POLICY
    ):
        return False
    final_duration = response.get("final_duration_seconds")
    if (
        isinstance(final_duration, bool)
        or not isinstance(final_duration, (int, float))
        or final_duration <= 0
        or abs(final_duration - evidence["duration_seconds"])
        > VOICE_DURATION_TOLERANCE_SECONDS
    ):
        return False
    timing = response.get("word_timing")
    if not isinstance(timing, dict) or timing.get("expected_text") != expected_text:
        return False
    words = timing.get("words")
    if not isinstance(words, list):
        return False
    actual_words = [
        "".join(character.casefold() for character in word.get("text", "") if character.isalnum())
        for word in words
        if isinstance(word, dict)
    ]
    if actual_words != _expected_words(expected_text):
        return False
    last_word_end = timing.get("last_word_end_seconds")
    return (
        isinstance(last_word_end, (int, float))
        and not isinstance(last_word_end, bool)
        and 0 < last_word_end <= evidence["duration_seconds"] + VOICE_DURATION_TOLERANCE_SECONDS
    )


def _brief(character: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": VOICE_BRIEF_CONTRACT,
        "entity_id": character["entity_id"],
        "voice_description_en": character["voice_description_en"],
        "sample_text_en": character["voice_sample_text_en"],
        "speech_rate": character["voice_speech_rate"],
        "output": {
            "sample_rate_hz": VOICE_SAMPLE_RATE_HZ,
            "channels": VOICE_CHANNELS,
            "codec": "pcm_s16le",
            "duration_policy": VOICE_DURATION_POLICY,
            "timing_authority": "provider_exact_word_subtitles",
            "max_lead_in_seconds": VOICE_MAX_EDGE_SILENCE_SECONDS,
            "max_trailing_silence_seconds": VOICE_MAX_EDGE_SILENCE_SECONDS,
            "max_internal_word_gap_seconds": VOICE_MAX_INTERNAL_WORD_GAP_SECONDS,
        },
    }


def _expected_words(text: str) -> list[str]:
    return [
        "".join(character.casefold() for character in token if character.isalnum())
        for token in re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text, flags=re.UNICODE)
    ]


def _subtitle_alignment(
    subtitle: Any, *, expected_text: str, provider_duration_seconds: float
) -> dict[str, Any]:
    """Validate exact spoken words against the provider audio's own duration."""

    if provider_duration_seconds <= 0:
        raise VoiceReferenceGenerationError("Seed Audio returned empty audio")

    if not isinstance(subtitle, dict) or not isinstance(subtitle.get("sentences"), list):
        raise VoiceReferenceGenerationError(
            "Seed Audio returned no word-timing subtitle authority"
        )
    words: list[dict[str, Any]] = []
    for sentence in subtitle["sentences"]:
        if not isinstance(sentence, dict) or not isinstance(sentence.get("words"), list):
            raise VoiceReferenceGenerationError(
                "Seed Audio returned invalid word-timing subtitle authority"
            )
        for raw in sentence["words"]:
            if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
                raise VoiceReferenceGenerationError(
                    "Seed Audio returned an invalid subtitle word"
                )
            normalized = "".join(
                character.casefold()
                for character in raw["text"]
                if character.isalnum()
            )
            if not normalized:
                continue
            start_ms = raw.get("start_time")
            end_ms = raw.get("end_time")
            if (
                isinstance(start_ms, bool)
                or isinstance(end_ms, bool)
                or not isinstance(start_ms, (int, float))
                or not isinstance(end_ms, (int, float))
                or start_ms < 0
                or end_ms <= start_ms
            ):
                raise VoiceReferenceGenerationError(
                    "Seed Audio returned an invalid subtitle word interval"
                )
            words.append(
                {
                    "text": raw["text"],
                    "normalized": normalized,
                    "provider_start_seconds": float(start_ms) / 1000.0,
                    "provider_end_seconds": float(end_ms) / 1000.0,
                }
            )
    expected_words = _expected_words(expected_text)
    actual_words = [word["normalized"] for word in words]
    if not expected_words or actual_words != expected_words:
        raise VoiceReferenceGenerationError(
            "Seed Audio subtitle words differ from the exact sample text: "
            f"expected={expected_words}, actual={actual_words}"
        )
    for index, word in enumerate(words):
        if word["provider_end_seconds"] > (
            provider_duration_seconds + VOICE_DURATION_TOLERANCE_SECONDS
        ):
            raise VoiceReferenceGenerationError(
                "Seed Audio word timing exceeds the generated audio duration: "
                f"word={word['text']!r}, end={word['provider_end_seconds']:.3f}s, "
                f"audio={provider_duration_seconds:.3f}s"
            )
        if index and (
            word["provider_start_seconds"] < words[index - 1]["provider_start_seconds"]
            or word["provider_end_seconds"] < words[index - 1]["provider_end_seconds"]
        ):
            raise VoiceReferenceGenerationError(
                "Seed Audio returned non-monotonic word timing"
            )
    gaps = [
        max(
            0.0,
            words[index]["provider_start_seconds"]
            - words[index - 1]["provider_end_seconds"],
        )
        for index in range(1, len(words))
    ]
    max_gap = max(gaps, default=0.0)
    if max_gap > VOICE_MAX_INTERNAL_WORD_GAP_SECONDS:
        raise VoiceReferenceGenerationError(
            "Seed Audio inserted an overlong pause between sample words: "
            f"{max_gap:.3f}s"
        )
    first_word_start = words[0]["provider_start_seconds"]
    last_word_end = words[-1]["provider_end_seconds"]
    trailing_silence = max(0.0, provider_duration_seconds - last_word_end)
    if first_word_start > VOICE_MAX_EDGE_SILENCE_SECONDS:
        raise VoiceReferenceGenerationError(
            "Seed Audio inserted an overlong lead-in before the sample text: "
            f"lead_in={first_word_start:.3f}s"
        )
    if trailing_silence > VOICE_MAX_EDGE_SILENCE_SECONDS:
        raise VoiceReferenceGenerationError(
            "Seed Audio inserted an overlong tail after the sample text: "
            f"trailing_silence={trailing_silence:.3f}s"
        )
    timed_words = [
        {
            "text": word["text"],
            "start_seconds": round(word["provider_start_seconds"], 6),
            "end_seconds": round(word["provider_end_seconds"], 6),
        }
        for word in words
    ]
    return {
        "expected_text": expected_text,
        "provider_text": subtitle.get("text"),
        "word_count": len(timed_words),
        "audio_duration_seconds": round(provider_duration_seconds, 6),
        "first_word_start_seconds": round(first_word_start, 6),
        "last_word_end_seconds": round(last_word_end, 6),
        "trailing_silence_seconds": round(trailing_silence, 6),
        "max_internal_word_gap_seconds": round(max_gap, 6),
        "words": timed_words,
    }


def _duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as source:
            return source.getnframes() / float(source.getframerate())
    except (OSError, wave.Error) as exc:
        raise VoiceReferenceGenerationError(
            f"Cannot inspect generated voice WAV {path}: {exc}"
        ) from exc


def _normalize_to_contract(source: Path, target: Path) -> float:
    """Normalize only the PCM transport format; preserve the authored timeline."""

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp.wav")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ar",
        str(VOICE_SAMPLE_RATE_HZ),
        "-ac",
        str(VOICE_CHANNELS),
        "-c:a",
        "pcm_s16le",
        str(temporary),
    ]
    try:
        subprocess.run(command, check=True)
        evidence = _wav_evidence(temporary)
        if evidence is None:
            raise VoiceReferenceGenerationError(
                f"Normalized voice does not meet the PCM transport contract: {target}"
            )
        temporary.replace(target)
        return evidence["duration_seconds"]
    finally:
        temporary.unlink(missing_ok=True)


def _provider_prompt(character: dict[str, Any], *, has_identity_reference: bool) -> str:
    reference_instruction = (
        "@Audio1 supplies only speaker identity, age, timbre, accent, and vocal texture; "
        "do not copy its wording, silence, tempo, or long pauses. "
        if has_identity_reference
        else "Create one original speaker identity from the voice direction. "
    )
    return (
        reference_instruction
        + "Speak exactly the sample text once at the natural pace implied by the wording "
        "and voice direction. The text determines the total duration; do not target, "
        "pad, stretch, compress, or trim to any fixed duration. Use connected phrasing "
        "with no pause longer than 0.35 seconds and only a very short clean lead-in and "
        "tail. "
        "Do not add, omit, repeat, paraphrase, whisper, sing, announce stage directions, "
        "or name the speaker. VOICE DIRECTION: "
        + character["voice_description_en"]
        + " EXACT SAMPLE TEXT: "
        + character["voice_sample_text_en"]
    )


def _generate_one(
    task_root: Path,
    repository_root: Path,
    character: dict[str, Any],
    timeout: int,
    *,
    force_regenerate: bool,
) -> tuple[str, dict[str, Any]]:
    entity_id = character["entity_id"]
    folder = repository_root / ASSET_MEDIA_RELATIVE_PATH / "characters" / entity_id
    target = folder / "voice.wav"
    brief_path = folder / "voice.brief.json"
    request_path = folder / "voice.request.json"
    response_path = folder / "voice.response.json"
    expected_brief = _brief(character)
    existing_response = _load_json(response_path)
    if (
        not force_regenerate
        and _load_json(brief_path) == expected_brief
        and _existing_voice_is_current(
            target,
            existing_response,
            entity_id=entity_id,
            expected_text=character["voice_sample_text_en"],
        )
        and isinstance(existing_response, dict)
        and isinstance(existing_response.get("uri"), str)
        and existing_response["uri"].strip()
    ):
        return entity_id, {
            "description_en": character["voice_description_en"],
            "reference": {
                "path": target.relative_to(repository_root).as_posix(),
                "uri": existing_response["uri"],
            },
        }

    identity_reference = target if target.is_file() and not force_regenerate else None
    provider_prompt = _provider_prompt(
        character, has_identity_reference=identity_reference is not None
    )
    request_record = {
        "contract": VOICE_REQUEST_CONTRACT,
        "entity_id": entity_id,
        "provider": "seed-audio-1.0",
        "prompt": provider_prompt,
        "identity_reference": (
            target.relative_to(repository_root).as_posix()
            if identity_reference is not None
            else "none"
        ),
        "audio_config": {
            "format": "wav",
            "sample_rate": VOICE_SAMPLE_RATE_HZ,
            "speech_rate": character["voice_speech_rate"],
        },
        "normalization": {
            "policy": "technical_format_only_preserve_natural_duration",
            "duration_policy": VOICE_DURATION_POLICY,
            "codec": "pcm_s16le",
            "channels": VOICE_CHANNELS,
            "sample_rate_hz": VOICE_SAMPLE_RATE_HZ,
            "time_scale_factor": 1.0,
            "timing_authority": "provider_exact_word_subtitles",
        },
        "acceptance": {
            "exact_sample_words_required": True,
            "word_timings_must_fit_generated_audio": True,
            "max_lead_in_seconds": VOICE_MAX_EDGE_SILENCE_SECONDS,
            "max_trailing_silence_seconds": VOICE_MAX_EDGE_SILENCE_SECONDS,
            "max_internal_word_gap_seconds": VOICE_MAX_INTERNAL_WORD_GAP_SECONDS,
            "maximum_generation_attempts": VOICE_MAX_GENERATION_ATTEMPTS,
        },
    }
    _atomic_json(brief_path, expected_brief)
    _atomic_json(request_path, request_record)

    attempt_errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix=f"voice-{entity_id}-") as temporary_dir:
        for attempt in range(1, VOICE_MAX_GENERATION_ATTEMPTS + 1):
            args = argparse.Namespace(
                prompt=provider_prompt,
                audio_ref=[str(identity_reference)] if identity_reference else [],
                image_ref=None,
                output_format="wav",
                sample_rate=VOICE_SAMPLE_RATE_HZ,
                speech_rate=character["voice_speech_rate"],
                loudness_rate=None,
                pitch_rate=None,
                enable_subtitle=True,
                extra_json=None,
                save_dir=temporary_dir,
                store=False,
                timeout=timeout,
            )
            result = seedaudio.command_generate(args)
            artifacts = result.get("artifacts")
            if not isinstance(artifacts, list) or len(artifacts) != 1:
                attempt_errors.append(
                    f"attempt {attempt}: Seed Audio returned no unique artifact"
                )
                continue
            source = Path(artifacts[0]["local_path"])
            provider_duration = _duration(source)
            try:
                alignment = _subtitle_alignment(
                    result.get("subtitle"),
                    expected_text=character["voice_sample_text_en"],
                    provider_duration_seconds=provider_duration,
                )
                final_duration = _normalize_to_contract(source, target)
                if abs(final_duration - provider_duration) > VOICE_DURATION_TOLERANCE_SECONDS:
                    raise VoiceReferenceGenerationError(
                        "Technical PCM conversion changed the authored duration: "
                        f"provider={provider_duration:.6f}s, final={final_duration:.6f}s"
                    )
            except VoiceReferenceGenerationError as exc:
                attempt_errors.append(f"attempt {attempt}: {exc}")
                continue
            accepted_attempt = attempt
            break
        else:
            raise VoiceReferenceGenerationError(
                f"Seed Audio could not align every sample word for {entity_id}: "
                + " | ".join(attempt_errors)
            )

    stored = seedaudio.core.tos_upload_path(target, kind="inputs/audio")
    uri = stored["public_url"]
    response_record = {
        "contract": VOICE_RESPONSE_CONTRACT,
        "entity_id": entity_id,
        "request_id": result.get("request_id"),
        "duration_policy": VOICE_DURATION_POLICY,
        "provider_duration_seconds": round(provider_duration, 6),
        "final_duration_seconds": round(final_duration, 6),
        "time_scale_factor": 1.0,
        "accepted_generation_attempt": accepted_attempt,
        "word_timing": alignment,
        "path": target.relative_to(repository_root).as_posix(),
        "uri": uri,
    }
    _atomic_json(response_path, response_record)
    return entity_id, {
        "description_en": character["voice_description_en"],
        "reference": {
            "path": target.relative_to(repository_root).as_posix(),
            "uri": uri,
        },
    }


def ensure_voice_references(
    task_root: Path,
    characters: list[dict[str, Any]],
    *,
    repository_root: Path = REPOSITORY_ROOT,
    timeout: int,
    max_workers: int,
    force_regenerate: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Generate/reuse natural-duration voice samples in deterministic plan order."""

    results: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(
        max_workers=min(max_workers, len(characters)),
        thread_name_prefix="voice-reference",
    ) as executor:
        forced = set(force_regenerate or set())
        futures = {
            executor.submit(
                _generate_one,
                task_root,
                repository_root.expanduser().resolve(),
                character,
                timeout,
                force_regenerate=character["entity_id"] in forced,
            ): character["entity_id"]
            for character in characters
        }
        for future in as_completed(futures):
            entity_id = futures[future]
            try:
                _, voice = future.result()
                results[entity_id] = voice
            except Exception as exc:
                failures.append(f"{entity_id}: {exc}")
    if failures:
        raise VoiceReferenceGenerationError(
            "Voice reference generation failed: " + " | ".join(sorted(failures))
        )
    return {
        character["entity_id"]: results[character["entity_id"]]
        for character in characters
    }


def publish_voice_references_to_catalog(
    task_root: Path,
    voices: dict[str, dict[str, Any]],
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> None:
    """Replace character voice bindings in the current catalog atomically."""

    catalog_path = repository_root.expanduser().resolve() / ASSET_CATALOG_RELATIVE_PATH
    catalog = _load_json(catalog_path)
    if not isinstance(catalog, dict) or catalog.get("contract") != "production-design-assets":
        raise VoiceReferenceGenerationError(
            "A final current production-design-assets catalog is required before "
            "publishing voice references"
        )
    assets = catalog.get("assets")
    if not isinstance(assets, dict):
        raise VoiceReferenceGenerationError("assets.json assets must be an object")
    character_ids = {
        asset_id
        for asset_id, asset in assets.items()
        if isinstance(asset, dict) and asset.get("type") == "character"
    }
    if set(voices) != character_ids:
        raise VoiceReferenceGenerationError(
            "Generated voice set differs from current character set; "
            f"expected={sorted(character_ids)}, actual={sorted(voices)}"
        )
    for entity_id, voice in voices.items():
        assets[entity_id]["voice"] = voice
    _atomic_json(catalog_path, catalog)
