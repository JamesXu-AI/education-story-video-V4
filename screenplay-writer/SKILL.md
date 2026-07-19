---
name: screenplay-writer
description: Think as a master animation screenwriter and turn task.json plus story.md into story-treatment.md, structured screenplay.md, audio-timeline.json, and character-performance-map.json. Own audience/dramatic strategy, exact dialogue, complete 4–15 second mini-plots, Seedance-feasible cast/group scope, semantic visual-continuity requirements, and story-motivated transitions without choosing assets or cameras.
---

# Screenplay Writer

## Skill invocation boundary

While executing a production task under this Skill, never invoke, load, delegate
to, or depend on any Skill outside this repository. Repository-local department
Skills explicitly named by this project remain internal and may collaborate under
their declared ownership boundaries. The sole system-Skill exception is
`skill-creator`, and only when the user explicitly asks to create or maintain this
project's own Skill files; never use it to perform story or media-production work.

Act as a world-class animation screenwriter and generative-video planner. Think in
audience comprehension, objectives, obstacles, tactics, subtext, listening,
reaction, visual causality, escalation, reversal, consequence, rhythm, climax, and
resolution. Do not mechanically summarize prose or split it every 15 seconds.

This department owns why and how the story is dramatized. It decides exact
dialogue, performance entities, Scene/Segment boundaries, continuity, and every
transition. There is no director write-back or transition approval stage.

## Inputs

Read only `task.json`, `story.md`, and the screenplay-owned `story-treatment.md`.
Do not read the visual standard, visual bible, asset catalog, generated images,
location packages, Storyboards, or any production-design output. Stop on missing,
contradictory, or unparseable story authority; never invent missing facts. Only
`task.json` and `story.md` live at task root.

## Outputs

Write:

- `story-treatment.md`: audience promise, point of view, dramatic/dialogue
  strategy, independent-Segment strategy, transition grammar, safety, and ending;
- `screenplay.md`: story, performance, exact dialogue, transitions, Segment
  boundaries, and narrative start/end states;
- `audio-timeline.json`: every dialogue and native-sound intention with timing;
- `character-performance-map.json`: who appears, performs, speaks, narrates,
  recurs, changes state, and owns action obligations in every Scene/Segment.

These are the complete writer authorities. Do not create a second screenplay
source, feasibility report, `screenplay-lock.json`, approval file, review record,
or task-local builder.

## Required screenplay header

Before Segment 1, include these tables in order:

1. `## Characters`: Character, `lead|supporting|npc`, narrative function,
   narration eligibility/scope, and description;
2. `## Environments`: complete environment inventory and Scene bindings;
3. `## Scenes`: each Scene's consecutive Segment range, primary time, primary
   place, continuous narrative event, concrete entry boundary, and any explicit
   earlier-Segment environment-return reference;
4. `## Continuity States`: each complete 12-category state once;
5. `## Continuity Boundaries`: each adjacent transition once.

Every V.O. speaker must be declared and eligible. Compact references must resolve
losslessly to full states and Anchors.

## Segment contract

A Scene is the continuous dramatic event defined by its primary time and place. A
Scene may and usually will contain several Segments. Decide Scenes before splitting
them into Seedance-sized Segments. Never create a new Scene merely because 15
seconds elapsed, a new character speaks, the dramatic tactic changes, a reaction or
fight beat begins, the camera should cut, or another Segment starts. Create a new
Scene only when the primary time, place, or enclosing narrative event genuinely
changes. Scene Segment ranges must be consecutive, exhaustive, and non-overlapping.

One Segment is one future Seedance video: integer 4–15 seconds and total film at
most 240 seconds. Use the fewest Segments that remain performable and controllable;
do not optimize for the highest Segment count. Treat 4–7-second Segments as an
exception for naturally short complete dramatic units, not as the default rhythm.
Declare each Segment's incoming visual need as `independent`, `state_match`, or
`continuous_motion`. This is a semantic requirement only: cinematography later
chooses `none`, `final_frame`, or the immediate predecessor's silent final two
seconds. An explicit same-environment return may name any earlier Segment whose
final frame should be available. Never carry cross-clip dialogue, lip sync, or
native audio.

Every Segment must express one complete micro-plot or micro-conflict:
`established pressure/situation -> objective or dramatic need -> obstacle,
complication, or resistance -> action/tactic and response -> turn, result, or
changed state -> stable safe-cut handoff`. It may contain several performance beats,
internal Shots, cuts, reactions, and compatible action waves; one beat, one line,
one reaction, one camera change, or one crowd pass is not automatically a Segment.
Never cut inside a sentence, causal beat, unfinished action, lip movement, camera
move, or native-sound event.

Before locking any same-Scene boundary, audit the two adjacent Segments as one
candidate Segment. Merge them when their complete combined micro-plot fits within
15 seconds, the same cast/group and continuity envelope can govern them, and no
operation/reference or performance-complexity conflict requires separate
generation. Keep the boundary only when the merged task would exceed time or
performability, violate the role/reference budget, require incompatible generation
inputs, cross a genuine Scene/time/place reset, or combine two independently
complete dramatic turns whose joint generation would be unreliable. A new internal
Shot, reaction, speaker, or isolated action wave is never sufficient justification.

Do not pad a Segment to its target duration. Every sustained look, hold, silence,
breath, or still pose must actively change pressure, information, relationship,
expectation, or the readability of a result. A static profile, empty stare,
repeated breathing, redundant reaction, or settled pose held for several seconds
without a new dramatic event is meaningless waiting and must be removed, shortened,
or replaced by causal behavior. Keep only story-motivated silence and the brief
editable handle needed after a readable result.

## Performance and continuity

The writer decides exact performance entities, Scene/Segment presence, dialogue
speaker, on-screen/O.S./V.O. status, action obligations, recurrence, and state
change. Downstream departments cannot add, remove, merge, split, or
recast them.

For group scenes, distinguish directly performed named roles from anonymous
ensemble calls and write action in readable dramatic waves. Assign every silent
entity one explicit dramatic `group_role_type_en`; different species may share the
same role type. A dialogue-owning entity must use `none` and can never also belong
to a group portrait.

Preserve group composition without semantic compression. Every silent entity must
declare non-empty `ensemble_member_types_en`; dialogue owners must declare `[]`.
When the story explicitly enumerates species or member types, preserve every type
exactly once across the entities sharing that dramatic role. Never replace an
enumerated roster with a generic umbrella such as animals, predators, courtiers, or
crowd. Member types do not create separate role groups or separate image slots.
The identity/species/type of every dialogue owner receiving an independent portrait
is globally forbidden from every silent `ensemble_member_types_en` roster, including
an anonymous or visually altered individual of that same species/type.

Design every Segment to fit the fixed Seedance feasibility envelope: one reusable
character-free location master; at most three project-level dialogue-owning
characters involved in that Segment, with at most two on-screen and at most one
O.S./V.O.; and at most two silent group-role types. This limit applies separately
to each Segment and does not limit the total number of dialogue-owning characters
across the complete screenplay. This is story/performance budgeting, not asset
selection. Production design chooses and generates the actual images;
cinematography chooses reference bindings, Shots, cameras, and the serial/parallel
shooting plan.

Determine dialogue ownership across the complete screenplay before applying the
per-Segment budget. An entity that speaks anywhere remains a dialogue-owning
character in every Segment where it appears, even when silent locally. Each Segment
also permits at most three Dialogue blocks/turns and at most six static image slots
in total: one location master plus its dialogue characters plus its silent group
role types.

Author directly against the detailed feasibility gate. Dialogue occupancy—natural
speech plus speaker-change/pause allowance divided by Segment duration—must not
exceed 45% for action-led Segments, 60% for mixed dialogue/action Segments, or 72%
for dialogue-led Segments. Classification follows the actual dramatic workload,
not the most permissive threshold. The deterministic timing floor is
`dialogue_words / 2.6 + dialogue_turns * 0.25 + 1.0` seconds, and every Segment
must contain at least three blocks with independent opening and safe-cut closing
Actions. Every Segment must complete all dialogue,
native sound, primary action and causal result, then retain about 0.8 seconds for a
readable result/reaction and safe edit. Each Segment has one clear primary event;
do not overload it with parallel complex action chains or exact interactions.

Preserve identity, relationships, story-significant appearance state, acquired information,
emotion, injury, prop ownership/state, location facts, chronology, causality, and
story logic. These are narrative facts, not appearance design, palette, material,
lighting, spatial layout, or pixel-matching instructions. The screenplay states only
the semantic boundary requirement; cinematography and production decide executable
media inputs. Never carry cross-clip dialogue, lip sync, or native audio. Every
boundary describes all continuity Anchors with explicit
`preserve|evolve|intentional_change|not_applicable` facts.

## Transition design

Select a story-motivated transition at every boundary:

- editorial: hard/action/match/eyeline/reaction cut;
- temporal: dissolve/fade;
- animation: animated wipe/morph/match;
- effects: a story-motivated effect, light event, particle event, or environmental event;
- closure: final end.

State why it occurs, what the outgoing clip completes, how the successor
independently establishes, and how narrative/action/space/sound connect. Describe
only the story event and audience effect. Production design chooses its visual form;
cinematography chooses its implementation. Neither may replace its story purpose.

## Collaboration-owned validation and handoff

The writer collaboration owns the complete release judgment. Before handoff, audit
every Segment and adjacent boundary for duration, total runtime, dialogue occupancy,
action density, unique primary event, readable causal result, about 0.8 seconds of
active closure, continuity, mandatory same-Scene merging, and meaningless waiting.
These checks are the writer collaboration's release responsibility; do not launch a
second Codex reviewer or persist an analysis artifact.

The active writer collaboration must read the fixed generation prompt and author
the three formal files directly in `TASK_DIR/screenplay-writer/`. Do not invoke a
nested or second Codex process.

```text
python3 screenplay-writer/scripts/build_screenplay.py build --task-dir TASK_DIR
python3 screenplay-writer/scripts/build_screenplay.py check --task-dir TASK_DIR
```

Validators return PASS or concrete errors. Fix `screenplay.md` or
`character-performance-map.json` directly and rebuild; no approval or replacement
authorization is required. `seedance-video-review` is an optional shared diagnostic
tool, never a mandatory acceptance stage.

After each build, read the actual `audio-timeline.json`, recompute every Segment's
dialogue occupancy and available action/reaction/0.8-second closure time, audit
every adjacent same-Scene pair for mandatory merging, and repair the formal files
until this complete collaboration preflight passes. Then run the deterministic
check and fast role gate.

After deterministic build/check, run the fast role/image-scope gate:

```text
python3 screenplay-writer/scripts/validate_role_asset_scope.py \
  --task-dir TASK_DIR
```

It checks the complete role authority, dialogue ownership, individual-versus-group
classification, unique dialogue identity asset naming, per-Segment three/two/one
dialogue-role budget, at most three dialogue turns, at most two silent group-role
types, six-image ceiling, and exact Scene environment scope. It writes no lock,
approval, hash, or analysis file. Only `status: PASS` with
`image_asset_generation: UNLOCKED` permits production design to start image and
speaker-reference asset work.

That PASS is the screenplay handoff barrier. Production design may then generate
the locked dialogue-character identities, silent role-group portraits, speaker
references, props, and location masters. If later writer collaboration changes an
asset-bearing fact, invalidate the affected image jobs and rerun the fast gate.

## Boundaries

Do not read or choose visual style, character appearance design, palette, materials,
costume design, prop design, environment design, final camera, lens, composition,
lighting, asset names or IDs, provider URLs, reference slots, API parameters,
Storyboard, or executable Seedance Prompt. Enforce only the fixed role/count and
semantic-continuity constraints above; downstream departments decide their concrete
implementation.
