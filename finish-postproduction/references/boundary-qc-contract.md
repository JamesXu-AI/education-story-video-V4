# Boundary QC & Repair Contract

## Position in the finishing workflow

Boundary QC runs after the current generated Segment set and authored picture EDL
are available, before the native picture lock is rendered. A second deterministic
audit runs against the rendered picture lock before it is promoted to the clean
master. Caption burn-in always happens after this stage.

```text
generated Segments + authored EDL
-> pre-assembly boundary evidence and technical triage
-> safe local correction plans
-> native picture-lock render
-> final-timeline boundary audit
-> clean master
-> subtitles and captioned master
```

## Evidence

For every cut-like boundary, create exactly the predecessor's final 1.0 second plus
the current Segment's opening 1.0 second, with synchronized native audio. At 24 fps
the sample contains exactly 48 ordered frames. For a dissolve or fade, render the
authored effect in a two-second sample centered on that transition instead of
substituting a raw splice.

Each boundary directory contains the strict sample, 48 readable frames, frame
manifest, contact sheet, deterministic color/similarity measurements, and any
repair candidates. The final-timeline audit creates the same evidence from the
rendered picture lock. These measurements are detection evidence only; they never
approve picture, performance, identity, action, dialogue, or semantic continuity.

## Automatic repair scope

Automatic repair is permitted only when a cut has a high-confidence visual match
and the measured discrepancy fits the configured safe bounds. The correction may
change luma and chroma only. It is strongest on the incoming boundary frame and
decays to zero over the configured short window. The generated source Segment is
never overwritten.

The system must not attempt to hide identity drift, redraws, geometry changes,
repeated/skipped action, scene-state resets, or any authored transition. A
high-confidence match whose required correction exceeds safe bounds becomes
`review_required`. Dissimilar motivated cuts and scene changes receive evidence but
no automatic color match.

## Artifacts and reversibility

All rebuildable artifacts live below:

```text
TASK_DIR/.pending/finish-postproduction/boundary-qc/
  boundary-qc-manifest.json
  pre-assembly/FROM--TO/
  final-timeline/FROM--TO/
```

The manifest records source paths, EDL semantics, measurements, correction
parameters, fade duration, generated previews, final-timeline measurements, and
whether a correction was used in the picture-lock render. Rebuilding with boundary
QC disabled or removing a recorded correction plan restores the unmodified source
assembly; no generated Segment media is mutated.
