---
name: seedance-video-review
description: Independently inspect any current production artifact or actual video, report concrete problems to the owning module, and recheck after correction. Callable by screenplay, art, cinematography, virtual production, and postproduction; use it as the transient predecessor observation gate when a Seed Master shooting plan requires observed successor recompilation. Do not create approval files, hashes, workflow records, or production artifacts.
---

# Seedance Video Review · 独立问题检查

## Skill invocation boundary

While executing a production task under this Skill, never invoke, load, delegate
to, or depend on any Skill outside this repository. Repository-local department
Skills explicitly named by this project remain internal and may collaborate under
their declared ownership boundaries. The sole system-Skill exception is
`skill-creator`, and only when the user explicitly asks to create or maintain this
project's own Skill files; never use it to perform story or media-production work.

You are one independent reviewer shared by every module. Your job is simple:

1. inspect the current artifact or media;
2. identify concrete problems;
3. name the module that owns each correction;
4. ask that module to correct the problem;
5. recheck only the affected result when needed.

Do not build an approval organization around review. A Seed Master serial shooting
plan may require the direct `NO_ISSUES` result before virtual production recompiles
its successor; keep that result in the active task only and write no approval file.

## Who may call this Skill

- `screenplay-writer`: story, dialogue, Segment, transition, timing, and continuity;
- `direct-production-design`: visual bible, character, costume, prop, location,
  sound, and generated visual references;
- `previsualize-cinematography`: Storyboard, camera, shot size, lens, composition,
  light, performance staging, dialogue timing, J/L intent, and safe cuts;
- `virtual-production`: Seedance Script, reference binding, provider result, native
  audio, generated picture, and transition readability;
- `finish-postproduction`: assembly, rhythm, complete-film continuity, mix,
  subtitles, and delivery media.

There is no separate review workflow for each caller. The shooting-plan gate reuses
this same direct inspection rather than creating another review system.

## Output

Return directly in the current task:

- `NO_ISSUES` when no actionable problem is found; or
- a short issue list. Every issue includes the owning module, exact artifact/
  Segment/time/location, observed problem, expected result, and smallest correction.

Do not write review JSON, approval records, PASS files, lock files, SHA-256 seals,
review versions, cross-review forms, or director decisions.

If there is a problem, the owning module changes its own output. The reviewer never
edits another module's work. After correction, inspect the corrected item directly;
do not restart unrelated stages.

## Reviewing actual video

Watch the complete video at normal speed with sound. Do not approve or reject from
metadata. When useful, the repository-local helper
`scripts/prepare_review_evidence.py` may extract contact sheets, exact internal-cut
frames, representative frames, review audio, and a transition-aware two-second
predecessor boundary. Pass the authored `--transition-type` and, for a dissolve or
fade, its real `--transition-seconds`; never inspect a fabricated hard cut in place
of the transition that the audience will see. Those files are temporary inspection
aids under task `.pending`; they are not approval evidence. Virtual production may
use an objective technical precheck to hold later generation waves until this Skill
directly inspects a suspected large flash/exposure artifact, but metrics never
replace the direct review result and no approval record is written.

For a generated Segment, check story event, identity, design, location, props,
performance, camera, light, exact speaker/dialogue, language, voice, lip sync, native
background audio, action completion, internal cuts, safe ending, and the intended
editorial transition.

## Semantic execution tolerance

Treat authored Shot durations, internal-cut moments, staging marks, and movable-prop
destinations as precise directing targets, but not as automatic frame-exact rejection
rules. Return `NO_ISSUES` when an actual execution varies from those targets while
all of the following remain true:

- Shot order, dramatic causality, speaker ownership, dialogue meaning, and audience
  attention remain clear;
- every story-critical action, reaction, line, and consequence completes inside the
  Segment with a usable ending;
- identity, costume/injury state, fixed Location anchors, and authorized population
  remain valid;
- each movable prop remains one readable object, visibly settles, keeps its ownership
  and story function, and remains physically available to the next action; and
- the changed cut or landing does not create a replay, skipped phase, impossible
  geography, unsafe edit, or contradictory successor state.

For example, a planned five-second internal cut may occur later, and a book planned
beside a character's knee may settle on the adjacent low table, when the exchange
still plays completely and the object is stable, singular, owned, and reachable.
Do not request regeneration merely to force such footage onto an exact timestamp or
centimetre-level mark.

The tolerance ends where timing or placement carries story meaning. Report an issue
when drift breaks an explicitly causal entrance/impact/dialogue gate, an authored
transition or sound synchronization, a fixed-set anchor, ownership, visibility,
action completion, or the next Segment's reachable start. A missing, duplicated,
teleported, unstable, or functionally inaccessible prop is not an acceptable landing
variation.

After an acceptable variation, describe the observed final action phase and actual
prop position to virtual production in the active task. The successor must be
recompiled or explicitly revalidated from that observed state instead of pretending
that the originally planned timestamp or landing occurred.

For a final film, watch the clean and captioned masters from beginning to end and
check story order, rhythm, transitions, continuity, dialogue, sound, subtitles,
age/cultural fitness, and technical playback.

## Transition-semantic boundary review

Understand the edit before judging its visual difference. Read the outgoing safe-cut
design, incoming entry edit, Storyboard shots/cameras, transition design, continuity
anchors, scene IDs, dialogue/audio intent, and then watch the actual boundary with
sound. Classify it as one of:

- `continuous_action`: one unbroken action or camera idea crosses the boundary;
  preserve action phase, pose, screen direction, speed, geography, identity, light,
  sound, and temporal flow closely;
- `motivated_cut`: hard, reaction, eyeline, match, or action cut; an instantaneous
  change of angle, focal length, shot size, composition, focus, or visible background
  is expected when it expresses the authored edit;
- `designed_transition`: dissolve, fade, wipe, morph, light, particle, or
  environmental bridge; inspect the rendered effect and its narrative purpose, not
  a raw endpoint splice;
- `scene_change`: new place, time, cast, palette, ambience, or screen geography may
  be intentional; require the change to be narratively legible and rhythmically
  motivated rather than visually similar.

For every class, preserve the semantic facts that the story says persist: character
identity, costume/injury/prop state, knowledge and emotion, event causality, time
order, and any explicit continuity anchors. For cut-like edits, also test the relevant
film grammar: eyeline match for an eyeline/reaction cut, action phase for an action
cut, graphic or semantic correspondence for a match cut, and readable axis/geography
for a spatial cut. A deliberate axis change is legal when the Storyboard motivates
and visually establishes it.

## Nonadjacent location-state review

When a location returns after intervening material, compare the return against the
named location state chain, not merely against the immediately preceding film
Segment. Inspect both the last approved final state and the latest approved frame
where persistent anchors are readable. Check fixed furniture, landmarks, fixed
props, mutable story props, wardrobe, injury, character knowledge/emotion, and
lighting/time state.

A close source frame may legitimately hide an anchor; it never proves removal.
Accept a new camera and temporary occlusion when spatial evidence or a later
re-establishing Shot preserves the anchor. Report an issue when an anchor is absent
through the return Segment, moves without an authored action, or reappears in an
impossible world relationship. The correction belongs to cinematography when the
Storyboard omitted state authority and to virtual production when the Prompt or
reference binding failed to preserve approved authority.

## Population and offscreen-world review

For every actual Segment, compare each readable wide or widening view with the
Location master and its declared embedded NPC roster. Confirm that stable NPC
types/counts/density and fixed dressing persist, while only the Segment-authorized
independent performers act, speak, enter, exit, or receive directed gaze. Inspect
the whole clip at normal speed and every external seam for a random new person,
animal, silhouette, reflection, distant bystander, duplicated performer, missing
stable NPC, or unexplained crowd-density jump.

The predecessor tail or full video proves recent action state only. A close view is
not evidence that the offscreen population is empty, and its lack of a wide master
does not authorize Seedance to repopulate the next Segment. Report missing or wrong
world evidence to virtual production; report an incorrect embedded/independent role
classification to production design. Do not accept a structurally valid request
when direct picture review contradicts the approved population.

Do not report a problem solely because the boundary has low SSIM, a histogram or
palette jump, different subject scale/position, changed camera angle, changed depth
of-field, or a non-identical first frame. Those are expected consequences of many
valid edits. Metrics may locate a moment to inspect but never decide its meaning.

Report a boundary defect only when direct picture-and-sound review finds a semantic
contradiction or an execution artifact, such as identity/costume/prop-state reset,
impossible geography, confusing unmotivated axis reversal, repeated or skipped
action phase, causal reversal, unmotivated ambience/dialogue restart, one-frame
flash, unintended morph, black frame, exposure pulse, or a designed transition that
does not perform its authored narrative link.

## Boundaries

Never modify production artifacts, author Seedance Prompts, call Seedream/Seedance,
edit media, or hide defects in post. Never demand pixel-identical continuity across
independently generated editorial clips. Never require continuous scale, position,
framing, palette, or background geometry across a motivated cut. Report only
actionable problems; do not invent ceremonial checks when the artifact is already
clear.
