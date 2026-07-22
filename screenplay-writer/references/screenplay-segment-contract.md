# Cinematic Widescreen Production Script Contract

This file owns the exact `screenplay.md` table syntax. Creative decisions belong
to `references/prompts/story_to_screenplay_gen.md`.

The writer releases exactly one UTF-8 file:

```text
screenplay-writer/screenplay.md
```

Apart from the title and section headings, all content is in Markdown tables.

## Authorship Boundary

The writer authors every cell. Code may map authored values into validation records
and calculate pass/fail facts; it may not add, copy, compose, infer, default, or
alter creative content.

## Required order

1. title;
2. `## Production Information` table;
3. `## Characters` table;
4. `## Script` with consecutive Scene Unit sections;
5. `## Continuity Appendix` tables.

Use globally consecutive IDs: `segment-001`, `scene-001`, `state-001`,
`boundary-001`, `A-001`, and `L-001`.

## Title

Begin with:

```markdown
# Cinematic Widescreen Production Script: <title>
```

## Production Information

Use a two-column table with the exact header `Field | Value` and these exact rows:

```text
Production Type
Genre
Estimated Runtime Seconds
Target Language
Target Age Band
Educational Theme
Story Premise
Dramatic Strategy
Safety and Culture
Opening Event
Ending Event and Obligation
```

`Production Type` is `cinematic_widescreen`; `Target Language` is `English`.
Opening and ending rows describe authored screen events, not promotional slogans.

## Characters

Use these exact columns:

```text
Entity ID | Character | Story Role | Narrative Function | Kind | Recurring | Group Role | Member Types | Narration | Description
```

`Story Role` is `lead`, `supporting`, or `npc`. `Kind` is `individual` or
`anonymous_ensemble`. `Recurring` is `yes` or `no`. `Narration` is `allowed`,
`conditional`, or `not_allowed`. Dialogue owners use `none` for Group Role and
Member Types. A silent ensemble uses one concrete Group Role and a
semicolon-separated exact member-type list.

## Script

After `## Script`, write consecutive units:

```markdown
## Scene Unit 1 — <dramatic label>
```

A Scene Unit is a 4–15 second screenplay planning unit. Route A may pack or refine
it for generation, and its Shot rows do not prescribe the number or formatting of
future Seedance Prompt passages. Several adjacent units may share one `Scene ID`;
a new unit does not imply a change of scene, place, or time.

### Scene Unit Information

Use a two-column `Field | Value` table with these exact rows:

```text
Segment ID
Scene ID
Slugline
Duration Seconds
Workload
Environment
Dramatic Purpose
Start State
End State
Incoming Boundary
```

`Slugline` uses `INT.` or `EXT.` plus a specific place and time. `Workload` is
`action_led`, `mixed_dialogue_action`, or `dialogue_led`. `Duration Seconds` is an
integer from 4 through 15.

### Shot Execution

Use these exact columns:

```text
Shot ID | Beat ID | Scale / View | Duration Seconds | Performers | Dramatic Change | Objective / Tactic | Visual Action | Important Reaction | Blocking / Movement | Gaze / Addressee | Completion State | Audience Focus | BGM / SFX / Ambience | Dialogue
```

One row is one story-facing shot.

#### Shot ID and duration

- `Shot ID` uses the globally consecutive Action ID sequence: `A-001`, `A-002`, …
- `Beat ID` is a globally unique ID such as `BEAT-001A`; it identifies the same
  row's dramatic change.
- `Duration Seconds` is a positive editorial estimate. It need not sum exactly to
  the Scene Unit duration and is not compiled into mandatory Prompt time windows.

#### Scale / View

Use one of:

```text
establishing | wide | medium | close_up | extreme_close_up | insert | reaction | pov
```

Choose the scale or viewpoint only when it serves spatial understanding, action,
reaction, revelation, concealment, emotional emphasis, or educational legibility.
Do not write lens, focal length, camera height, coordinates, equipment, lighting,
routine camera movement, or edit implementation. Seedance Master owns those.

#### Performers, action, reaction, and movement

- `Performers` is a comma-separated list of declared Entity IDs, or `none` for a
  pure environment/object shot.
- `Dramatic Change` states what becomes different in story knowledge, pressure,
  relationship, expectation, decision, or result during this shot.
- `Objective / Tactic` states what the active performer is trying to achieve and
  the playable tactic used now.
- `Visual Action` contains only visible, filmable present-tense behavior.
- `Important Reaction` identifies the reacting entity and its readable response;
  use `none` only when the shot genuinely contains no important reaction.
- `Blocking / Movement` states origins, destinations, screen-space relationships,
  crossings, stops, turns, and resulting positions. `none` is valid only for a
  truly static object/environment shot.

#### Gaze / Addressee

Declare every visible performer's meaningful gaze as:

```text
<entity-id> -> <entity-id|object|place|self|narration> (<facing and gaze behavior>)
```

Write each relation exactly as
`owl -> rabbit (facing=across the table toward Rabbit, gaze=holds Rabbit's eyes)`.
Separate multiple relations with `<br>`. The camera is never an addressee.
For O.S./V.O. dialogue use `not_visible` facing/gaze language. The dialogue
speaker's target here is the authoritative addressee for that Line.

#### Completion State

Use exactly one prefix:

```text
completed: <observable settled result>
open: <unfinished action phase that must continue>
```

This cell answers whether the shot action has completed. The final shot of a unit
may use `open:` only when the outgoing boundary requires `continuous_motion`.

#### Audience Focus

State the one action, reaction, clue, relationship change, or consequence the
audience must register now. Do not restate the Scale / View cell.

#### BGM / SFX / Ambience

Use `none` or one or more authored cues separated with `<br>`:

```text
BGM ENTERS: <character and dramatic function>
BGM EVOLVES: <audible change and reason>
BGM STOPS: <dramatic stop point>
BGM STING: <brief accent and event>
SFX: <source and exact audible event>
AMBIENCE: <specific environmental bed or change>
SILENCE: <what drops out and why the silence matters>
```

Every Scene Unit contains at least one non-`none` audio cell.

#### Dialogue

Use `none` or exactly:

```text
L-001; speaker=<entity-id>; gate=<visible or audible trigger inside this shot>; delivery=<playable cue or none>; text="<exact spoken words>"
```

Each shot holds at most one Line. The `gate` states why speech begins at that
moment. The speaker must be a Performer for on-screen dialogue or have an
off-screen/voice-over staging declaration. Its addressee comes from the same row's
`Gaze / Addressee` cell. Dialogue is exact production authority.

### Character Staging

Use these exact columns:

```text
Entity ID | Presence | Appearance | Trigger | Entry Path / Opening Position | First Visible Shot | First Visible Moment | Landing Shot | Landing Moment / Result | Speaks | Lines | State Change | Action Shots
```

Every character used by the Scene Unit appears once.

- `Presence` is `on_screen`, `off_screen`, or `voice_over`.
- `Appearance` is `present_at_open`, `enters`, or `not_visible`.
- `present_at_open` uses `opening` as Trigger, a concrete opening position, and
  points First Visible and Landing to the first shot where the character is already
  visibly settled.
- `enters` names the causal Trigger, physical entry path, First Visible Shot,
  First Visible Moment, Landing Shot, and observable Landing Moment / Result. The
  referenced shot cells must
  actually show the trigger-to-entry-to-landing chain.
- Both moment cells describe observable events. They may use exact seconds,
  relative timing, event order, or no numeric timing. Python does not require or
  interpret a timing notation.
- O.S./V.O. uses `not_visible` for Trigger, path/position, First Visible, Landing,
  both moment fields, and Landing Result.
- `Speaks` and `State Change` use `yes` or `no`. `Lines` and `Action Shots` contain
  comma-separated IDs or `none`.

## Continuity Appendix

The appendix contains reference mappings only. It never repeats shot descriptions,
dialogue, movement, gaze, audience focus, or audio cues.

### Environments

```text
Environment ID | Logical Environment | Scene IDs | INT/EXT | Time Context | Environment Facts | Story Function
```

### Scenes

```text
Scene ID | Segment IDs | Primary Time | Primary Place | Narrative Event | Entry Boundary | Entry Reason | Continuity Reference Segment | Continuity Reference Reason
```

### Scene Dramatic Contracts

```text
Scene ID | Purpose | Character Objective | Obstacle | Power Relationship | Turning Point | Outcome | Spatial Progression | Exit Impulse
```

### Continuity States

```text
State ID | Parent State | Changed Facts | Change Reason
```

`state-001` establishes the complete opening. Each later state names its immediate
parent and records only changed story facts and their cause.

### Continuity Boundaries

```text
Boundary ID | From Segment | To Segment | From State | To State | Handoff | Transition | Dramatic Reason | Audio Handoff | Continuity Handoff
```

`Handoff` is `independent`, `state_match`, or `continuous_motion`. Same-Scene units
are serial. Use `state_match` after a settled motivated cut; use
`continuous_motion` when unfinished action, entry, movement, facing, eyeline, or
performance crosses the unit boundary. A Scene/time/place discontinuity may use
`independent`.
