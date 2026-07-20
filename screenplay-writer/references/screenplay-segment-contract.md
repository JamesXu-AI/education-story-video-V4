# Screenplay Segment contract

The task root contains only `task.json` and `story.md`. Current writer outputs live
under `screenplay-writer/`; there is no second screenplay source or persisted
feasibility-analysis artifact.

## Outputs

```text
story-treatment.md
screenplay.md
audio-timeline.json
character-performance-map.json
```

`screenplay.md` owns story facts, exact dialogue, performance, transitions,
narrative/state continuity, and generation boundaries. It is not a Storyboard,
cinematography plan, visual bible, asset catalog, or Seedance prompt.

It also owns the cinematic Scene foundation and Dramatic Beats. Every Segment
repeats its Scene's exact `scene_dramatic_contract_json` with scene purpose,
character objective, obstacle, opening power relationship, turning point, outcome,
visual progression, and exit impulse. The multi-role screenplay gate runs internally
and persists no pass/fail object. Every
Segment carries `dramatic_beats_json`; each Beat records one narrative change,
physical objective, visible action, important reaction, spatial change,
dialogue/sound event, entry/exit state, action/reaction/support/atmosphere roles, one
visual focus, and a unique partition of screenplay block indexes. These are
dramatic and spatial semantics, not camera instructions.

Author `screenplay.md` and `character-performance-map.json` directly. The repository
builder validates them and derives only `audio-timeline.json`. Downstream modules
read ordered Segment `story_plan` data directly from `screenplay.md`. Do not create a task-local Python builder, compatibility
branch, duplicate screenplay source, or analysis report.

## Header and performance map

The screenplay Header contains separate Characters, Environments, Scenes,
Continuity States, and Continuity Boundaries tables. Characters declare
lead/supporting/NPC role and narration eligibility. Scenes may explicitly name an
earlier same-environment Segment whose final frame is needed for a later return.
The performance map states exactly who appears, performs, and speaks in every Scene
and Segment.

Any entity that speaks, owns an independent route/contact/reaction, changes story
state, or recurs is `individual`. Only unnamed, silent, non-state-changing group
behavior may be `anonymous_ensemble`.

Performance granularity is a story decision. `individual` means the entity owns an
independent action, reaction, state change, dialogue turn, or recurring identity;
`anonymous_ensemble` means only shared group behavior. Every silent entity declares
one `group_role_type_en`; dialogue owners declare `none`. This is dramatic grouping,
not species grouping or asset selection.

Every silent entity also declares non-empty `ensemble_member_types_en`; every
dialogue owner declares an empty list. The combined ordered member types for one
dramatic group role must preserve every story-explicit species/type without a
generic umbrella, omission, substitution, or invented filler. These exact member
types stay inside one dramatic group and therefore still consume one image slot.
An identity/species/type represented by any independent dialogue-character portrait
is forbidden from all silent member-type lists, even as an anonymous variation.

## Segment and transition rules

Before Segment packing, reject any Scene that has no objective/obstacle, no
turning point or changed result, static start/end visual state, dialogue detached
from behavior, all characters occupying one undifferentiated spatial layer, or a
group without differentiated action/reaction/support/atmosphere roles. A Scene or
Beat that is only information transfer returns to writer revision; Storyboard may
not disguise it with decorative coverage. The writer's semantic gate is primary;
the parser additionally requires the current contract, complete Beat-to-block
coverage, dialogue Beats with owned Action blocks, and rejects obvious cast-lineup,
turn-taking, or camera-facing Action language.

Determine Scene structure before Segment structure. One Scene is one continuous
primary time, place, and enclosing dramatic event, and may contain many Segments.
Changing speaker, tactic, action beat, shot, transition, or reaching the Seedance
duration limit does not create a new Scene. The `## Scenes` authority must partition
all Segments once, in order, into non-empty consecutive ranges; each Segment's
`scene_id` must match that authority.

Every Segment is one 4–15 second Seedance generation video; total runtime is at
most 240 seconds. Design the strongest finished scene flow before selecting one of
the two same-Scene serial continuation classes. Use the fewest Segments that remain
performable. Each Segment
declares `dramatic_workload` as `action_led`, `mixed_dialogue_action`, or
`dialogue_led`; the derived audio timeline enforces the matching 45%, 60%, or 72%
dialogue-occupancy ceiling before semantic review. Classification follows the real
dramatic workload and is not a permissive label. Every Segment also declares the
current `scene_dramatic_contract_json` and ordered `dramatic_beats_json`; all
Segments in one Scene repeat an identical Scene contract, Beat IDs are
project-unique, and Beat block-index sets partition its Action/Dialogue blocks
exactly once. Each Segment
preserves a complete micro-plot or micro-conflict at either Segment or serial-chain
level. An independent Segment lands a readable result; a serial Segment may end on
an intentional unfinished visual/performance/camera phase. It may contain several
performance beats, compatible action waves, internal Shots, and cuts; none of those
elements alone requires another Segment. Treat 4–7-second Segments as exceptional,
not the default rhythm.

Pairwise-audit every adjacent same-Scene boundary before release. Merge the pair
when the combined complete dramatic unit fits within 15 seconds and one compatible
cast/group, continuity, operation/reference, dialogue/audio, and performance load
can govern it. Retain a boundary only for a genuine time/place/Scene reset, duration
or performability overflow, role/reference-budget conflict, incompatible generation
input, or another concrete reliability constraint. A speaker change, reaction,
internal cut, coverage change, or isolated action/crowd wave is not sufficient.

Never pad runtime. Every sustained look, hold, silence, breath, or still pose must
change pressure, information, relationship, expectation, or result readability.
A static profile, empty stare, repeated breathing, redundant reaction, or settled
pose held for several seconds without a new dramatic event is invalid meaningless
waiting. Keep only story-motivated silence and a brief editable post-result handle.

The screenplay department declares every transition's dramatic purpose, boundary
state, and incoming visual requirement without defaulting to independence:

- `incoming_visual_requirement: independent` only for a genuine Scene, primary-time,
  primary-place, or enclosing-event discontinuity; never between adjacent Segments
  with the same `scene_id`;
- `incoming_visual_requirement: state_match` for every retained same-Scene boundary whose
  outgoing action has settled. It deterministically requires serial
  `first_frame_reference`: the approved predecessor last frame is a soft ordinary
  `reference_image`, not `strict_first_frame`, so a motivated new Shot may evolve
  while identity, state, facing, eyelines, blocking, light, and spatial composition
  remain continuous;
- `incoming_visual_requirement: continuous_motion` when unfinished action,
  performance, entrance/contact, blocking/facing, or camera phase must be inherited
  through serial `predecessor_video_reference`.

Cinematography resolves the executable predecessor attempt and binding but cannot
make a same-Scene boundary independent or convert a soft first-frame reference into
a strict first-frame/API lock. A Scene return may name an earlier semantic state.
Never bind provider URLs in the screenplay or
split one Dialogue block, lip-sync phrase, or indivisible native-sound event.

Preserve narrative/state continuity: identity, relationships, appearance, knowledge,
emotion, injuries, prop ownership/state, location facts, chronology, causality, and
story logic. Also state any story-critical action phase, facing, eyeline, entrance/
exit, contact, or performance phase that the Storyboard must stage or inherit.

Every Segment must be feasible with one reusable character-free location master;
at most three project-level dialogue-owning characters involved in that Segment,
including at most two on-screen and at most one O.S./V.O.; and at most two silent
group-role types. This is a per-Segment limit, not a limit on the total number of
dialogue-owning characters across the complete screenplay. The screenplay contract
contains no visual-standard input, asset IDs, camera plan, or production-design
output.

Run the current builder and validators. They return `PASS` or a concrete error and
create no approvals or analysis files. Correct the responsible formal authority
directly.

After build/check, `validate_role_asset_scope.py` is the final deterministic
screenplay handoff. Its PASS unlocks production-design image generation immediately.
The writer collaboration must already have applied the internal multi-role semantic
boundary review, generatability, action-density, boundary-handle, adjacent-
continuity, mandatory-merge, and meaningless-waiting rules directly; no persisted
separate review file is created. Every retained same-Scene boundary must use
`state_match`, `continuous_motion`, or writer repair; independent is invalid there.
Later writer changes preserve
running image work only when dialogue ownership, silent group membership, Scene
environment scope, and story-significant appearance/prop facts remain unchanged.
