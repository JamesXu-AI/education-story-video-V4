# SeedAudio Story Score Contract

> Experimental code only. `finish_postproduction.py` never reads a music plan,
> invokes SeedAudio, creates a score track, or promotes a scored master. Use this
> contract solely after an explicit user request for a separate experiment, and
> keep all results outside the main delivery path.

## Contents

1. [Goal](#goal)
2. [Entry gate](#entry-gate)
3. [Authoring the theme](#authoring-the-theme)
4. [Authoring story Cues](#authoring-story-cues)
5. [Generation and continuity](#generation-and-continuity)
6. [Mix and verification](#mix-and-verification)
7. [Commands and artifacts](#commands-and-artifacts)

## Goal

Create one coherent, story-reactive background score after picture assembly. The
score must recognize the production's visual world, follow screenplay turns, stay
out of the way of dialogue and native effects, and feel continuous across separately
generated Seedance Segments.

Do not ask Seedance to make this score. Seedance owns synchronized native sound and
must explicitly make no background music. SeedAudio owns the separate music stem in
postproduction.

## Entry gate

Before any SeedAudio provider call, require all of the following:

1. every current generated Segment, production record, and native audio stream is
   present and bound to current authority;
2. every current Segment Script forbids Seedance background music;
3. every persisted submitted `seedance-request.json` Prompt contains `No background
   music` or an accepted equivalent;
4. no Segment Script, provider artifact, or persisted media analysis says that
   Seedance music is baked into the native track;
5. the picture/audio EDL and audio timeline cover the complete picture lock;
6. a task-local `finish-postproduction/music-production.json` passes the v2 schema
   and covers every Segment exactly once in order.

Treat a failed gate as upstream regeneration work. Do not attempt vocal/music source
separation, spectral masking, or another score on top of baked music.

## Authoring the theme

Start from [music-production.json](../assets/music-production.json) and author a
task-local copy. Replace every example value. Keep all provider-facing musical
fields in clear English.

The `theme` object is the project-level music identity:

- `dramatic_thesis_en`: the emotional question and its final answer;
- `motif_en`: one compact, recognizable motif that survives transformation;
- `instrumentation_en`: one bounded instrument family compatible with the visual
  and cultural world;
- `production_character_en`: density, warmth, scale, dynamics, and sonic finish;
- `forbidden_en`: vocals, stylistic clichés, masking behavior, premature cadence,
  and any project-specific exclusions.

SeedAudio first receives a picture-lock contact sheet and generates a short theme
palette. This palette is a reference identity, not the final music. Every final Cue
uses it as an audio reference so the motif, orchestration, tonal world, and production
character stay related.

Begin both the theme and Cue Prompt by assigning SeedAudio the role of a world-class
cinematic soundtrack master, film composer, music director, and re-recording mixer.
Require an emotionally breathtaking, deeply moving, unforgettable result achieved
through story precision, motif transformation, dynamics, silence, and earned payoff.
Never describe it as a voice-dubbing generator and never equate impact with raw
loudness, wall-to-wall density, trailer bombast, or dialogue masking.

## Authoring story Cues

A Cue is a dramatic phase, not automatically one Segment. Merge adjacent Segments
when the same emotional intention continues. Start a new Cue only when the story's
music state materially changes: setup to complication, discovery to understanding,
danger to relief, or payoff to coda.

Each Cue must declare:

- a consecutive `segment_ids` range;
- `narrative_role_en` and `dramatic_arc_en`;
- explicit incoming and outgoing music states;
- space reserved for dialogue and important effects;
- detailed beat-responsive direction;
- `cadence: carry`, except the last Cue which must use `cadence: final`.

The flattened Cue Segment list must be exactly `1..N`. Never omit, repeat, or reorder
a Segment. Do not force Cue boundaries onto every shot or Segment cut. The scheduler
partitions picture-lock time continuously and uses the next Cue's first Segment start
as the boundary, including authored visual overlap correctly.

## Generation and continuity

Generate in this order:

```text
picture-lock contact sheet
  -> SeedAudio theme palette
  -> normalized theme audio reference
  -> story Cue WAVs using the same reference identity
  -> equal-power Cue crossfades
  -> one exact-duration picture-lock score stem
```

Cue prompts contain absolute timeline ranges, compact performance summaries from the
current Segment Scripts, music-state transitions, dialogue/effect space, and cadence
rules. Interior Cues must carry harmonic and rhythmic motion into their closing
handles. Only the final Cue may land a complete cadence, exactly at the authored film
ending, followed by a controlled decay.

The first and final Cues receive half-crossfade handles; interior Cues receive a
full-crossfade handle. Removing the authored overlaps after joining yields exactly
one continuous picture-lock score. SeedAudio may return a fixed long render (the
current real endpoint returns about 63 seconds) despite a shorter requested duration.
When the render is longer, trim a carry Cue from its head and the final-cadence Cue
from its tail, preserving musical tempo; use pitch-preserving time correction only
for residual drift within 6%, and reject a materially short render.

## Mix and verification

Produce and inspect both:

- `final-seedaudio-score-only-preview.mp4` for motif, Cue logic, continuity, and
  unwanted vocals/effects;
- `final-seedaudio-mix-test.mp4` for dialogue intelligibility, native-effects space,
  pumping, loudness, and end behavior.

The delivery mix preserves Seedance native dialogue, foley, and ambience. Optional
sidechain compression uses the extracted dialogue center only as a control key and
attenuates only the SeedAudio score. Then normalize the combined program to
`program_loudness_lufs`, enforce `true_peak_dbtp`, and retain one exact-duration audio
stream in the scored master.

Verification requires:

- one native event per Segment with no gaps and only authored overlaps;
- exact ordered Cue coverage;
- one continuous score event spanning the entire picture lock;
- equal picture/native/score/final-master duration within tolerance;
- explicit no-Seedance-music evidence for every submitted Segment;
- one comprehensive `finish-score-manifest/v2` with all artifacts and checks.

## Commands and artifacts

Validate before spending provider credits:

```text
python3 finish-postproduction/scripts/generate_seedaudio_score.py \
  --task-dir TASK_DIR \
  --validate-only
```

Generate or resume the score directly:

```text
python3 finish-postproduction/scripts/generate_seedaudio_score.py \
  --task-dir TASK_DIR
```

Use `--regenerate` only when intentionally replacing reusable provider outputs.
Final score work appears under:

```text
TASK_DIR/.pending/finish-postproduction/music-production/
  picture-lock-contact-sheet.jpg
  theme-palette.reference.wav
  cues/cue-NNN.wav
  seedaudio-score.wav
  final-seedaudio-score-only-preview.mp4
  final-seedaudio-mix-test.mp4
  scored-picture-lock.mp4
  score-manifest.json
```

For an explicitly requested background-music-only audition of a legacy master whose
old audio cannot be cleanly separated, remove the complete old audio stream and run:

```text
python3 finish-postproduction/scripts/evaluate_seedaudio_score_only.py \
  --video LEGACY_MASTER \
  --music-plan MUSIC_PLAN \
  --anchors SCORE_ANCHORS \
  --segment-scripts SEGMENT_SCRIPTS \
  --output-dir EVALUATION_OUTPUT
```

This diagnostic output contains no dialogue, native effects, ambience, or old music.
Never treat it as a final mix. Retry only transient network, HTTP 500, or audio-risk
audit failures, at most three provider attempts. If the user accepts a diagnostic
fallback after exhausted audio-risk review, reuse a different window from prior
approved same-theme material, mark the Cue `fallback_edit`, and disclose it in the
evaluation manifest.
