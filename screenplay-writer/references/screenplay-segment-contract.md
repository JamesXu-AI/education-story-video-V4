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

Determine Scene structure before Segment structure. One Scene is one continuous
primary time, place, and enclosing dramatic event, and may contain many Segments.
Changing speaker, tactic, action beat, shot, transition, or reaching the Seedance
duration limit does not create a new Scene. The `## Scenes` authority must partition
all Segments once, in order, into non-empty consecutive ranges; each Segment's
`scene_id` must match that authority.

Every Segment is one independently generated 4–15 second video; total runtime is at
most 240 seconds. Use the fewest Segments that remain performable. Each Segment
declares `dramatic_workload` as `action_led`, `mixed_dialogue_action`, or
`dialogue_led`; the derived audio timeline enforces the matching 45%, 60%, or 72%
dialogue-occupancy ceiling before semantic review. Classification follows the real
dramatic workload and is not a permissive label. Each Segment
contains a complete micro-plot or micro-conflict: established pressure or situation,
a dramatic need, an obstacle/complication/resistance, action and response, and a
readable turn/result/changed state before the safe edit ending. It may contain
several performance beats, compatible action waves, internal Shots, and cuts; none
of those elements alone requires another Segment. Treat 4–7-second Segments as
exceptional naturally short dramatic units, not the default rhythm.

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

The screenplay department selects every transition directly and declares its
semantic purpose, boundary state, and incoming visual requirement:
`independent`, `state_match`, or `continuous_motion`. Cinematography decides the
executable reference (`none`, `final_frame`, or the immediate predecessor's final
two seconds) and serial/parallel schedule. A Scene return may explicitly point to
any earlier Segment in the same environment for a final-frame reference. Never
inherit source dialogue, lip sync, or audio.

Preserve narrative/state continuity: identity, relationships, appearance, knowledge,
emotion, injuries, prop ownership/state, location facts, chronology, causality, and
story logic. Each Storyboard stages the screenplay-authored action inside its own
independent clip.

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
The writer collaboration must already have applied the semantic generatability,
action-density, closure, adjacent-continuity, mandatory-merge, and meaningless-
waiting rules directly; no separate model review runs. Later writer changes preserve
running image work only when dialogue ownership, silent group membership, Scene
environment scope, and story-significant appearance/prop facts remain unchanged.
