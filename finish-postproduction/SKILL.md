---
name: finish-postproduction
description: Assemble current audiovisual Seedance Segments, preserve synchronized dialogue, foley, and ambience while enforcing No background music upstream, execute authored transitions, create exact subtitles, and render verified clean and captioned masters. Keep SeedAudio score code available only as a manually invoked experiment and never connect it to the default finishing workflow.
---

# Finish Postproduction · 剪辑、声音与后期

## Skill invocation boundary

While executing a production task under this Skill, never invoke, load, delegate
to, or depend on any Skill outside this repository. Repository-local department
Skills explicitly named by this project remain internal and may collaborate under
their declared ownership boundaries. The sole system-Skill exception is
`skill-creator`, and only when the user explicitly asks to create or maintain this
project's own Skill files; never use it to perform story or media-production work.

Own picture assembly, synchronized native-sound finish, exact
subtitles, clean/captioned masters, and deterministic delivery integrity. This is
the only postproduction department.

## Entry condition

Before assembly, require `virtual-production/generation-state.json` to report
`GENERATED` with exactly one complete audiovisual output and matching operational
production record for every current screenplay Segment. Require each record to
match the current Seed Master Script, execution plan, operation, provider attempt,
and final-Prompt/`assets.json` semantic compatibility review hash. Probe the actual
media and stop on missing, stale, failed, corrupt, silent, or reordered coverage.
Independent review is callable for diagnosis but never a required approval file.

## Required authorities

Read:

1. `task.json` and its format, language, voice, and dialogue source settings;
2. screenplay, its ordered Segment plans, audio timeline, and exact dialogue;
3. the native `previsualize-cinematography/storyboard.md` and
   `storyboard-compile-manifest.json` (never `storyboard.data.json`);
4. Route B `dialogue-duration-ledger.json` and `boundary-continuity-report.json`;
5. all current Segment Scripts, execution plans, videos, and completed production
   records and submitted Seedance requests;
6. production-design assets.

Read [finishing-contract.md](references/finishing-contract.md),
[boundary-qc-contract.md](references/boundary-qc-contract.md),
[audio-timeline-contract.md](references/audio-timeline-contract.md), and
[seedaudio-score-contract.md](references/seedaudio-score-contract.md), and
[subtitle-style.json](assets/subtitle-style.json). Preserve the current
[Soft & Cute 3D Healing Animation Visual Standard](../direct-production-design/references/soft-cute-3d-healing-visual-standard.md).

## Audio policy

Use this fixed source separation:

```text
voice_audio_source: speaker_reference_audio
dialogue_source: seedance
native_background_audio_source: seedance_ambience_and_foley_no_music
seedance_background_music: false
background_music_source: none
generate_audio: true
```

Every dialogue character has one fixed, unique speaker-reference audio identity.
Seedance uses it to generate the Segment's actual synchronized words and native
dialogue, breath, reaction, room tone, ambience, foley, effects, and diegetic sound.
Every submitted Segment Prompt must explicitly say `No background music`.
Postproduction preserves the native track; it never substitutes the reference WAV,
shares one reference across characters, revoices a line, disables native ambience,
or replaces missing audio with silence.

## Isolated SeedAudio experiment

Do not read `music-production.json`, call SeedAudio, create a score track, select a
scored master, or promote any SeedAudio artifact while running
`finish_postproduction.py`. The main workflow always delivers native synchronized
sound with `background_music_source: none`.

Retain [music-production.json](assets/music-production.json),
`generate_seedaudio_score.py`, `evaluate_seedaudio_score_only.py`, and
[seedaudio-score-contract.md](references/seedaudio-score-contract.md) only for a
future manually requested experiment. Run them solely when the user explicitly asks
for another SeedAudio experiment. Keep every result under `.pending`, label it
experimental, and never use it as a main-flow input or final master.

## Picture and sound finish

- Assemble exactly one accepted video per Segment in screenplay order.
- Before picture-lock render, run `Boundary QC & Repair` on every external seam.
  Create the strict two-second audiovisual evidence, all 48 ordered frames at
  24 fps, deterministic technical measurements, and a reversible manifest. Apply
  only configured safe luma/chroma corrections to high-confidence matched cuts;
  never overwrite generated Segment media.
- Render Soft/Matched/Strong previews for each planned correction. A large required
  correction, identity/action/geometry issue, or unresolved final-timeline residual
  must stop delivery for visual review or upstream regeneration.
- Derive and execute the screenplay transition boundary contract exactly: motivated cuts remain
  hard cuts; dissolve/fade use their authored overlap and matching native-audio
  acrossfade; animation/effects transitions must already be completed clip-locally.
- Do not invent a transition, reorder, repeat, or trim away authored action/dialogue.
- Normalize canvas, SAR, frame rate, codec, and color metadata without recomposing
  shots or redesigning assets.
- Keep every Segment native audio track sample-aligned with its picture. Never move
  dialogue or lip sync across a Segment boundary.
- Preserve the accepted synchronized native sound without adding a music layer.
- Keep the final runtime at or below 240 seconds.
- After picture-lock render, extract and audit every seam again from the final
  timeline. Subtitle burn-in and final promotion require
  `final_timeline_status: technical_audit_complete`.

Run:

```text
python3 finish-postproduction/scripts/finish_postproduction.py \
  --task-dir TASK_DIR
```

Rebuildable work lives only under
`TASK_DIR/.pending/finish-postproduction/`. Deliverables live under:

```text
finish-postproduction/final-clean-master.mp4
finish-postproduction/final-captioned-master.mp4
finish-postproduction/final-delivery-manifest.json
finish-postproduction/subtitles/subtitle-cues.json
finish-postproduction/subtitles/master.srt
finish-postproduction/subtitles/master.vtt
```

Boundary evidence and repair records live under:

```text
.pending/finish-postproduction/boundary-qc/boundary-qc-manifest.json
.pending/finish-postproduction/boundary-qc/pre-assembly/FROM--TO/
.pending/finish-postproduction/boundary-qc/final-timeline/FROM--TO/
```

## Subtitle authority

Build exact captions from the Seed Master Route B exact-dialogue duration ledger
and actual picture-EDL offsets. Do not transcribe, paraphrase, translate, omit, duplicate, or
reorder authority text. Whitespace wrapping is the only permitted textual change.
When one authored dialogue cue exceeds the current per-screen line limit, split it
into the fewest ordered caption events that fit, preferring sentence boundaries and
allocating the original cue interval by exact word/character share. Preserve the
source cue identity and prove that normalized concatenation reconstructs the exact
authority text; every split event must independently pass line-count, minimum-time,
and reading-speed limits.
When an authored speech window is shorter than the minimum caption display time,
extend only the caption event—prefer its following silence, then its preceding
silence—while remaining inside the owning Segment and never overlapping an adjacent
caption. Record both authored speech timing and final caption timing. If no safe
interval exists, return the timing defect upstream.
Interpret font size, outline, and bottom margin as percentages of the delivered
frame. Convert those values into the subtitle renderer's native script-resolution
coordinates before burn-in, then visually inspect at least one active-caption frame;
never allow renderer-default scaling to enlarge captions a second time.
For dissolve/fade boundaries, derive each Segment offset from the EDL's authored
overlap; never force overlapping picture events into a hard-cut-contiguous model.
If exact text does not fit its authored interval, stop and return the timing defect
to `virtual-production` for Seed Master Route B recompilation.

## Delivery check

The final delivery manifest describes all masters, subtitle files, EDL/audio timeline,
duration, resolution, streams, native audio declarations, and
`background_music_source: none`. After checking the actual files, this department
emits:

```text
FINAL_MASTER_READY
```

Any module may ask `seedance-video-review` to watch either complete master when a
visual or sound problem needs independent diagnosis. If it finds a problem, send the
smallest correction to the owning module and rebuild only affected output. No review
file or approval record is created.

## Hard boundaries

- Do not change story, dialogue, design, performance, Storyboard, or Segment Scripts.
- Do not use postproduction to hide generation defects.
- Do not treat boundary metrics, similarity, or a successful repair render as a
  semantic picture approval. They are technical detection and routing evidence.
- Do not connect SeedAudio experiment code or artifacts to the main finishing flow.
- Do not create approval records for individual videos or the final film.
- Always deliver a clean master and external SRT/VTT in addition to the captioned
  master.
