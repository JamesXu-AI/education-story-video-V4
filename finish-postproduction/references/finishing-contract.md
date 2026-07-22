# Finishing Contract

## Current picture and sound authority

`screenplay-writer/screenplay.md` defines story order and authored editorial
transitions. Seed Master's native `storyboard.md` plus
`storyboard-compile-manifest.json` define Segment authority; no
`storyboard.data.json` exists. Route B Segment Scripts, execution plans, generated
media, dialogue-duration ledger, and boundary-continuity report live below
`.pending/virtual-production/`.

`virtual-production/generation-state.json` must report `GENERATED`, cover every
compile-manifest Segment, and bind each output to its exact Seed Master Script,
execution plan, provider attempt, current resolved media bindings, and
production record. Postproduction executes
the authored edit and may normalize technical delivery, but cannot recompose a
Shot, rewrite dialogue, or synthesize silence for missing native audio.

`.pending/finish-postproduction/post-production/picture-audio-edl.json` is the
final-timeline offset authority. `.pending/finish-postproduction/audio-timeline.json`
records one synchronized native event per Segment with Seedance dialogue, foley,
ambience, and effects but no non-diegetic background music. The main flow never
reads a music plan or adds a SeedAudio track.

Before the picture lock is rendered, every EDL boundary passes through
[boundary-qc-contract.md](boundary-qc-contract.md). High-confidence matched cuts
may receive only a bounded, decaying luma/chroma correction. Generated Segment
files remain read-only. The rendered picture lock is then scanned again at every
EDL boundary before clean-master promotion. The authoritative technical evidence
and reversible correction record is:

```text
.pending/finish-postproduction/boundary-qc/boundary-qc-manifest.json
```

Boundary measurements never approve performance, identity, action, dialogue, or
semantic continuity. Unsafe corrections and unresolved residuals stop delivery for
visual review or upstream regeneration.

## Subtitle authority

```text
Seed Master Route B dialogue-duration-ledger.json exact text and local timing
-> picture-audio-edl.json Segment offset
-> subtitle-cues.json + master.srt + master.vtt
-> final-captioned-master.mp4
```

ASR is never subtitle authority. Every Route B dialogue cue appears once in ledger
order. Cue times stay inside the owning Segment and Segment offsets come from the
actual EDL. Long cues may split only for layout/readability while normalized
concatenation remains exact Unicode authority text. Caption display may extend only
into adjacent silence inside the same Segment and never changes audio.

## Delivery

All rebuildable work stays under `.pending/finish-postproduction/`. Release the
clean master, captioned master, subtitle cues, SRT, VTT, and final delivery manifest
under `finish-postproduction/`. Both masters must have equal timing and synchronized
native audio; the captioned master adds only subtitle pixels. Both declare
`background_music_source: none`. Their delivery manifest also binds a completed
Boundary QC manifest whose generated sources remained read-only. Final state is
`FINAL_MASTER_READY`.
