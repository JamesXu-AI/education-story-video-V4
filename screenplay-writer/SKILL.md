---
name: screenplay-writer
description: "Think as a master animation screenwriter and turn task.json plus story.md into story-treatment.md, structured screenplay.md, audio-timeline.json, and character-performance-map.json. Own audience/dramatic strategy, exact dialogue, effect-first Scene/Segment packing, Seedance-feasible cast/group scope, and story-level boundary semantics. Force every adjacent same-Scene Segment pair into one of two serial continuation classes: soft first-frame reference after a settled or motivated cut, or predecessor-video reference for unfinished action, performance, blocking, or camera motion. Use for screenplay creation or repair where cinematic action, facing, eyelines, or dramatic continuity must survive later Seedance generation."
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
dialogue, performance entities, Scene/Segment boundaries, narrative continuity,
and the dramatic purpose of every transition. It does not pre-empt the director:
cinematography and Seedance compilation may choose a stronger executable cut,
reference, operation, or serial dependency that preserves the same story facts,
dialogue, performance obligations, and dramatic purpose. A downstream semantic
review may return a boundary for writer repair when the authored split damages the
finished result.

It is also the first owner of cinematic viability. Every Scene must have a concrete
purpose, central objective, obstacle, opening power relation, turning point,
changed outcome, visible spatial/action progression, and exit impulse. Every
Dramatic Beat must contain one perceptible change, one physical objective, visible
action, important reaction, spatial change, dialogue/sound behavior, entry/exit
state, and one visual focus. Screenplay does not choose final camera parameters,
but it may not defer conflict, behavior, dynamic space, or ensemble differentiation
to Storyboard.

## Inputs

Read only `task.json`, `story.md`, and the screenplay-owned `story-treatment.md`.
Do not read the visual standard, visual bible, asset catalog, generated images,
location packages, Storyboards, or any production-design output. Stop on missing,
contradictory, or unparseable story authority; never invent missing facts. Only
`task.json` and `story.md` live at task root.

## Outputs

Write:

- `story-treatment.md`: audience promise, point of view, dramatic/dialogue
  strategy, effect-first Segment and boundary strategy, transition grammar,
  safety, and ending;
- `screenplay.md`: story, cinematic Scene contracts, Dramatic Beat-to-block
  mappings, performance, exact dialogue, transitions, Segment boundaries, and
  narrative start/end states;
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

Before Segment packing, run the Screenplay Gate internally as a combined
screenwriter/dramaturg, director, performance-blocking, cinematography-editor, and
continuity review. Reject and rewrite a Scene if it lacks objective/obstacle or a
changed result; mainly consists of stationary information exchange; detaches
dialogue from action/reaction; keeps everyone in one undifferentiated spatial
layer; gives an ensemble no distinct action/reaction/support/atmosphere duties; or
starts and ends in effectively the same visible state. Store the exact Scene
contract in `scene_dramatic_contract_json`. Run the semantic Screenplay Gate
internally and repair every failure, but do not persist a pass/fail review object;
a self-declared `pass` cannot override a script-false reading.

Store ordered `dramatic_beats_json` in every Segment. Beat quantity follows real
dramatic changes, never punctuation or a fixed quota. Each Beat uniquely owns one
or more 1-based screenplay `block_indexes`; together the Beats partition every
Action and Dialogue block exactly once. A Beat that owns dialogue must also own an
Action block so speech stays embedded in behavior. For group material, every Beat
names action subject, reaction subject, supporting group, atmosphere presence, and
one visual focus; reactions must be differentiated rather than synchronized.

Obvious cast-lineup, semicircle, camera-facing, or take-turns-speaking Action is a
deterministic blocker, but semantic review remains authoritative. The proper repair
is character objective, tactic, reaction, and spatial progression—not decorative
movement or camera language.

A Scene is the continuous dramatic event defined by its primary time and place. A
Scene may and usually will contain several Segments. Decide Scenes before splitting
them into Seedance-sized Segments. Never create a new Scene merely because 15
seconds elapsed, a new character speaks, the dramatic tactic changes, a reaction or
fight beat begins, the camera should cut, or another Segment starts. Create a new
Scene only when the primary time, place, or enclosing narrative event genuinely
changes. Scene Segment ranges must be consecutive, exhaustive, and non-overlapping.

One Segment is one future Seedance video: integer 4–15 seconds and total film at
most 240 seconds. Design the strongest finished scene and performance flow before
thinking about independent generation. Use the fewest Segments that remain
performable and controllable; do not optimize for Segment count, parallel waves,
or provider convenience. Treat 4–7-second Segments as exceptional.

Classify every incoming boundary from the actual dramatic and visual state; never
default all rows to one mode:

- `incoming_visual_requirement: independent`: only a genuine Scene, primary-time, primary-place,
  or enclosing-event discontinuity; never an adjacent same-Scene boundary;
- `incoming_visual_requirement: state_match`: every retained same-Scene boundary after the
  outgoing action reaches a readable settled phase. This requires serial
  `first_frame_reference`: downstream uses the approved predecessor last frame as
  an ordinary soft `reference_image`, not a strict/API first-frame lock. Preserve
  identity, body/prop state, blocking/facing, eyeline, light, and composition
  relationships while allowing the motivated new Shot to evolve;
- `incoming_visual_requirement: continuous_motion`: one unfinished visual action,
  performance tactic, entrance/contact, blocking/facing phase, or camera phase
  deliberately continues through serial `predecessor_video_reference`.

These are mandatory semantic and dependency classes. Cinematography later resolves
the approved predecessor attempt and executable binding, but cannot turn a retained
same-Scene boundary into independent generation or reinterpret
`first_frame_reference` as `strict_first_frame`. Never bind an asset URL here. Never split
one spoken line, lip-synchronization phrase, or indivisible native-sound event, but
visual action, performance, blocking, facing, eyeline, or camera motion may cross
the boundary when `continuous_motion` explicitly names the inherited phase.

A complete micro-plot or micro-conflict must survive at the Scene or dependency-
chain level. An independent Segment normally lands a readable turn; a serial
Segment may own only the performable portion that fits before the 15-second limit
and may end on an intentional moving handoff. Each Segment still needs a concrete
opening Action, development, and boundary Action. It may contain several internal
Shots, cuts, reactions, and compatible action waves; one beat, line, reaction,
camera change, or crowd pass is not automatically a Segment.

Before locking any same-Scene boundary, audit the two adjacent Segments as one
candidate Segment. Merge them when their complete combined micro-plot fits within
15 seconds, the same cast/group and continuity envelope can govern them, and no
operation/reference or performance-complexity conflict requires separate
generation. Keep the boundary only when the merged task would exceed time or
performability, violate the role/reference budget, require incompatible generation
    inputs, or combine two complete dramatic turns whose joint generation would be
    unreliable. A new internal
Shot, reaction, speaker, or isolated action wave is never sufficient justification.

Do not pad a Segment to its target duration. Every sustained look, hold, silence,
breath, or still pose must actively change pressure, information, relationship,
expectation, or the readability of a result. A static profile, empty stare,
repeated breathing, redundant reaction, or settled pose held for several seconds
without a new dramatic event is meaningless waiting and must be removed, shortened,
or replaced by causal behavior. Keep only story-motivated silence and a boundary-
appropriate handle: a readable landing for `independent`, a matchable state for
`state_match`, or useful terminal motion for `continuous_motion`. Never force a
character to freeze merely to manufacture an independent cut.

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
cinematography chooses reference bindings, Shots, and cameras. The screenplay fixes
same-Scene execution as serial; downstream may schedule genuine Scene/time/event
discontinuities independently.

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
`dialogue_words / 2.6 + dialogue_turns * 0.25 + 1.0` seconds. Every Segment must
contain at least three blocks with a concrete opening Action and an explicit
boundary Action. Complete every Dialogue block and indivisible native-sound event
inside the Segment. Complete the primary action and causal result only when the
boundary is `independent`; for `state_match` expose the exact settled match state;
for `continuous_motion` expose the unfinished phase that the successor must
inherit. Each Segment has one clear primary event or continuous phase; do not
overload it with unrelated complex action chains.

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

State why it occurs, what the outgoing clip completes or intentionally leaves in
motion, how the successor establishes or inherits its opening, and how narrative,
performance, blocking/facing, action, space, and sound connect. Describe story and
performance semantics rather than media files. Production design chooses visual
form; cinematography chooses implementation and may strengthen the edit or serial
inheritance without changing its story purpose.

## Collaboration-owned validation and handoff

The writer collaboration owns the complete release judgment. Before handoff, audit
every Segment and adjacent boundary for duration, total runtime, dialogue occupancy,
action density, causal flow, boundary-appropriate terminal state, continuity,
mandatory same-Scene merging, and meaningless waiting. This is an internal semantic
gate, not a keyword count. For every boundary, reason in turn as screenwriter/
dramaturg, director, performance-and-blocking director, cinematographer/editor,
continuity supervisor, and Seedance generation specialist. Each role must inspect
both adjacent dramatic states and answer whether a same-Scene boundary must merge,
use `state_match` / soft `first_frame_reference`, use `continuous_motion` /
`predecessor_video_reference`, or be rewritten. `independent` is categorically
invalid inside one Scene, even when action has settled or a coverage cut is
motivated. For a true Scene/time/event change, independent execution still requires
unanimous approval. Do not persist a separate analysis artifact.

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
dialogue occupancy and available action/reaction/boundary-handle time, audit every
adjacent same-Scene pair for mandatory merging and the correct single
`incoming_visual_requirement`, and
repair the formal files until the semantic preflight passes. Then run the
deterministic check and fast role gate.

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
