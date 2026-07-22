# Single-File Cinematic Storyboard Contract

Route A releases exactly one UTF-8 file:

```text
previsualize-cinematography/storyboard.md
```

The Storyboard is human-readable production authority and the sole Route B source.
Do not create `storyboard-compile-manifest.json`, `storyboard.data.json`, a trace,
ledger, review object, or any second representation.

## Required order

1. `# Cinematic Storyboard: <title>`
2. `## Project Direction`
3. `## Generation Plan`
4. `## Location State Plan`
5. consecutive `## Generation Segment N — <dramatic label>` sections
6. `## Continuity Review`

Use Markdown tables for exact mappings and concise prose for integrated direction.
Do not embed JSON or YAML.

## Project Direction

Use a `Field | Value` table that states runtime, aspect ratio, audience point of
view, visual progression, camera grammar, lighting/color grammar, production-design
motifs, performance grammar, native-audio grammar, and editorial rhythm. Every
value must be a chosen production decision, not a menu, slogan, or generic
adjective such as `cinematic`, `epic`, or `beautiful`.

## Generation Plan

Use one row per future Seedance video task:

```text
Segment | Screenplay Range | Scene | Duration Seconds | Operation | Predecessor | Seam | Internal Shots | Packing Reason
```

The Segment ID is internal traceability. Duration is an integer from 4 through 15.
`Operation` is `multimodal_reference`, `video_extension`, or `text_to_video`.
Several compatible internal shots may belong to one Segment. Do not create one
Segment merely because the view, speaker, reaction, or scale changes.
Choose the number of internal Shots by cinematic judgment. No fixed quota and no
downstream Prompt paragraph count follows from this table.

## Location State Plan

Use one row per Generation Segment:

```text
Location State Chain | Segment | Relationship | State Source | Temporal Evidence | World and Population Evidence | Persistent Anchors | Allowed Changes
```

`Relationship` is `independent`, `adjacent_continuation`,
`nonadjacent_revisit`, or `reset_with_reason`. A location returning after an
insert, flashback, imagined sequence, or another location is not independent when
its diegetic set state continues. It must name the latest prior Segment in the same
state chain as `State Source`.

The two evidence columns separate facts that one image or video may not show
together:

- `Temporal Evidence` names the latest approved final state for current action
  phase, performance, gaze, character, and mutable-prop state;
- `World and Population Evidence` names the approved Location master and, after a
  visible set-state change, any latest approved readable wide state needed for
  furniture, fixed props, landmarks, embedded NPC roster, population density, and
  offscreen world objects.

For an independent opening, temporal evidence is `none` and world evidence is the
approved Location master. Every continuation and revisit retains that world
authority in addition to its temporal source. A predecessor video or close final
frame proves only the recently visible action state; it never owns the offscreen
set or complete population and never proves that an offscreen anchor or NPC
disappeared. When a visible change makes the original Location image stale, add the
latest approved readable wide state without dropping the Location identity.
`Persistent Anchors`
comes from the location continuity package's `fixed_set_elements_en`, fixed
obstacles, fixed-prop placements, landmarks, and any screenplay-owned mutable prop
that has not been moved or removed on screen. `Allowed Changes` names only changes
caused by an approved visible action or an explicit reset reason.

## Generation Segment

Each Segment contains these sections in order.

### Segment Direction

Use a `Field | Value` table with:

```text
Segment ID
Screenplay Scene and Units
Duration Seconds
Dramatic Change
Audience Point of View
Scene and Environment
Incoming State
Outgoing State
Operation
Predecessor and Evidence
Continuity Requirement
Location State Chain
Temporal Continuity Evidence
World and Population Evidence
Authorized Population
Persistent Anchors
Anchor Visibility Requirement
Style and Image Quality
Concise Constraints
```

### Reference Plan

Use:

```text
Provider Token | Provider Role | Asset Namespace | Readable Subject | Purpose | Shot Scope | Forbidden Inheritance
```

Provider tokens use `@ImageN`, `@VideoN`, or `@AudioN`. Each token gets one clear
purpose stated in natural language. `Asset Namespace` is internal runtime mapping;
`Readable Subject` is the human-facing character, place, prop, or voice name Route B
must use. A token may be repeated only when it has genuinely separate purposes.

The Location token owns the dressed set and its production-design-approved embedded
NPC population. Do not bind those NPC assets again. Bind every required
`independent_performer_asset_ids` character or ensemble separately for identity,
state, and performance. If an embedded NPC must speak, enter or exit on cue,
interact, change state, carry a directed gaze/reaction, or preserve individual
identity, stop and return the classification to production design.

Every Segment set in a Location binds that Location master across every internal
Shot, including a video extension. `Authorized Population` names the exact embedded
population already inside the Location plus the independent performers allowed in
this Segment. No predecessor frame or video may authorize a new person, animal,
silhouette, reflection, or distant bystander.

### Ordered Shots

Use one row per ordered internal shot:

```text
Shot | Screenplay Shot | Transition and Camera | Subject Action and Expression | Space, Blocking and Gaze | Persistent Anchors | Lighting and Color | Dialogue and Native Audio | Landing and Edit
```

For every Shot:

- author the transition and camera behavior the event needs; a Shot may be locked,
  use one move, or combine several causally connected moves;
- name the readable subject and exact visible action;
- refine story-bearing movement by body part, range, speed, force, and causal
  transition or inertia when relevant;
- preserve entrances, landing positions, gaze, addressees, listener reactions,
  wounds, props, and action completion from the screenplay;
- name which persistent set/prop anchors remain visible, which are temporarily
  outside the frame or occluded, and which later Shot re-establishes them;
- place exact dialogue in quotation marks beside its speaker and trigger;
- state native ambience, effects, music, silence, and the settled landing;
- use editorial or exact timing descriptions when they clarify the event. Route B
  may keep, revise, or omit that timing language by model-facing judgment.

### Prompt Translation Notes

Use a short prose paragraph that states what Route B must prioritize and what may
be compressed. It must not introduce new story action or repeat every Shot row.
It must not prescribe Prompt headings, paragraphs, Shot labels/count, movement
count, word count, vocabulary, or timing syntax.

## Continuity Review

Use one compact table covering adjacent edits and nonadjacent location revisits:

```text
Boundary or Revisit | From | To | Relationship | State Evidence | Persistent Inheritance | Audio Inheritance | Editorial Reason
```

Use a soft predecessor-last-frame image for a settled same-Scene cut and complete
predecessor video extension for an unfinished phase. Use independent generation
only at a genuine discontinuity. A nonadjacent revisit waits for its named state
source review even when the edit itself is a dissolve or a time-and-place return.
The return may choose a new camera, but it may not reset furniture, landmarks,
wardrobe, injury, mutable props, or character state without an authored cause.

## Acceptance

Accept only when:

- every approved screenplay Shot and Line appears exactly once;
- action, blocking, gaze, camera, light, sound, and landing describe one reachable
  event rather than separate checklists;
- entrances retain trigger, first visibility, path, landing, and witness response;
- injuries and consequences remain as clear as the screenplay requires;
- every camera behavior has a story reason and compound movement remains spatially
  and temporally legible;
- every Segment appears once in the Location State Plan;
- every Segment supplies Location-owned world/population evidence; every
  continuing or revisited location also names the latest earlier source in the
  same state chain and supplies temporal evidence;
- no persistent anchor disappears across a revisit without a visible action,
  explicit reset reason, or a later re-establishing Shot after temporary occlusion;
- Generation packing serves the finished edit rather than bookkeeping;
- no field is mechanically filled, generic, repeated, or contradictory;
- the release directory contains only `storyboard.md`.
