---
name: virtual-production
description: "Use Seedance Master Route B to compile the approved single-file storyboard.md into free-form Seedance prompts, resolve provider media from a separate private plan, and execute dependency-aware video generation. Use for Seedance prompt writing, prompt repair, materialization, or Segment generation. Python validates only non-empty text plus provider-token placement, exact population lock, and exact dialogue ownership; it does not impose a creative prose template."
---

# Virtual Production

## Inputs and outputs

Read the sole Route A authority:

```text
TASK_DIR/previsualize-cinematography/storyboard.md
```

Invoke `seedance-master-skill` Route B with the original request, that Storyboard,
current `assets/assets.json`, and provider capabilities.

For each Generation Segment, Route B writes:

```text
TASK_DIR/.pending/virtual-production/seedance-segment-scripts/segment-NNN.md
TASK_DIR/.pending/virtual-production/seedance-segment-plans/segment-NNN.json
```

The Markdown file is the exact provider Prompt. The JSON file is private transport
metadata for validation, asset resolution, scheduling, and API parameters. Never
copy private-plan fields into the Prompt.

## Provider Prompt contract

Read [natural-language-seedance-prompt.md](references/natural-language-seedance-prompt.md).
This repository-local contract overrides generic Route B guidance that prescribes
fixed Prompt headings/order, consecutive `Shot N` prose, one movement per Shot, a
word limit, wording bans, or forbidden timing formats.
Route B authors the Prompt by cinematic and model-facing judgment. There is no
required heading, section order, paragraph count, total Shot count, consecutive
Shot numbering, camera movement count, word count, vocabulary list, sentence
pattern, or timing notation. A private dialogue cue is the sole Shot-label
exception: its exact line and readable speaker must occur inside the matching
`Shot N:` section.
The author may use prose, bullets, numbered Shots, continuous action, cuts,
compound camera behavior, time ranges, or another form when it best communicates
the intended result. The Storyboard is creative authority, not a template for
Prompt paragraph count.

Prompt authorship still aims to communicate the intended subjects, action,
performance, space, references, continuity, dialogue/audio, visual finish, and
landing. Most are semantic directing goals evaluated by Seedance Master and human
review. Python searches only the three auditable bindings defined below: provider
tokens, the exact population lock, and exact dialogue ownership.

For every Segment set in a Location, including `video_extension`, bind its approved dressed master together with the required
independent performer identity/state references. The Location image owns
architecture, materials, topology, every production-design-authored fixed-set
element, and its embedded NPC population. Express those responsibilities in the
Prompt only when and where Seedance Master judges useful; no sentence, placement,
or repetition rule applies. Do not bind an embedded NPC
again as a separate character, and never let a speaking or story-active performer
inherit identity from the Location image. Never rely on Seedance to invent fixed set
elements or embedded population, and never treat a close-up
crop as their removal from the set.

Also bind temporal evidence when the Segment continues or revisits state. Keep the
authorities separate: predecessor video/last frame owns only the recent action,
pose, gaze, mutable-prop, and camera phase it can prove; the Location master owns
the full set and embedded population, including what the predecessor crop does not
show. Preserve the approved embedded population and independent-performer
authority by including the private plan's exact `population_lock_en` sentence once
in the Prompt.

Temporal evidence is the sole visual identity authority for performers and movable
props already present in that evidence. Do not rebind those same subjects as
standalone images in a continuation or nonadjacent revisit; Seedance may interpret
overlapping authorities as additional instances. Bind only a genuinely new entrant
or an explicit post-action appearance target separately. A closed roster that is
authorized by continuity but is not visibly carried by the selected temporal
evidence counts as a returning entrant, not as an already-carried subject: bind its
roster reference when it must re-enter, identify every unique member in natural
language, and state that each member may first appear once and may not be generated
again after that reveal. Apply the same rule to an offscreen court or crowd that
must become visible only to exit. Keep the same-subject intent unambiguous without
requiring any particular Prompt phrase.
Provider reference media is request-wide and cannot be deactivated by a later Shot.
When one closed roster must exit and another must enter with mutually exclusive
visual authority, place the completed exit at a Generation Segment boundary. The
first Segment binds only the exiting roster; the dependent successor omits that
reference and binds only the entering roster. Never claim that Shot wording can
turn off a reference that was submitted with the same provider request.

## Private execution plan

The private JSON plan may contain only deterministic execution authority:

- source Storyboard hash and Segment identity;
- duration, operation, dependency, seam, and predecessor evidence;
- location state chain and relationship, exact temporal/world binding roles,
  embedded NPC roster, Segment-authorized independent performers, and one readable
  population-lock sentence;
- provider-token to asset-namespace mapping;
- exact dialogue ownership needed for validation;
- final visible/sound state and editable hold;
- fixed provider parameters.

Seedance Master authors this plan from `storyboard.md`. Python may parse, validate,
hash, resolve catalog URLs, and reject disagreement. Python may not invent, copy
into place, summarize, rewrite, or fill missing Prompt prose, Shots, dialogue,
references, continuity, or creative fields. The private plan may retain storyboard
Shot traceability for scheduling and media scope, but its `shot_count` does not
prescribe the Prompt's total Shot count. Python validates only that every declared
provider token appears and is introduced before the first Shot section, the exact
population lock appears once, and each dialogue cue's quoted text plus speaker is
inside its matching `Shot N:` section. It does not validate other headings,
paragraphs, Shot numbering/count, movement descriptions, words, or time expressions.

## Materialization and generation

Run capability validation, materialization, preflight, and generation only after
the Prompt passes those three binding checks and the private plan passes its
transport checks.
Materialization may resolve the
manually authored token mapping to current catalog URLs, but it must reject missing
or mistyped assets directly. It must not create compatibility packets, review
drafts, rework JSON, or Prompt text. Machine-readable catalog facts remain
transport authority and do not define a required provider-prose structure.

Use the Storyboard's two same-Scene temporal modes unchanged: soft predecessor-last-frame
reference image after a settled motivated cut, or complete predecessor-video
extension for unfinished action, performance, blocking, gaze, entrance, or camera
phase. Neither mode replaces the Location master. Dependent work waits for the
exact predecessor review.

That review evaluates semantic completion, not frame-exact obedience to every
planned internal-cut second or centimetre-level movable-prop mark. A Segment may be
accepted when Shot order, causality, exact speaker/dialogue, required actions,
identity, fixed set, population, and usable ending are intact even if an internal
cut lands earlier/later or a movable prop settles at an adjacent, stable, reachable
position. Do not regenerate only to force an otherwise valid take onto the planned
timestamp or prop coordinate. Timing remains hard when it controls a causal gate,
dialogue/action completion, authored transition or sound synchronization. Placement
remains hard when it changes ownership or story function, loses/duplicates the prop,
breaks a fixed anchor, creates impossible geography, or prevents the next action.

After an accepted variation, the observed predecessor tail becomes temporal
authority. Recompile or explicitly revalidate the successor Prompt so its incoming
action and mutable-prop description use the actual final state; never preserve a
planned landing in prose when the accepted video visibly landed elsewhere.

Also enforce nonadjacent location-state dependencies. A Segment returning to a
continuing set after an insert, imagined sequence, flashback, or another location
must wait for the last Segment in that location state chain. Bind the approved final
state for current performance, the Location master for complete world/population
authority, and the latest approved wide state when a visible set change makes that
additional evidence necessary. Choosing the readable anchor
frame is a continuity judgment made from direct review; Python may extract an
explicitly chosen frame and validate bindings, but may not choose, infer, or fill it.

An editorial dissolve or scene change does not by itself permit a set reset. New
camera coverage is allowed; unexplained furniture, landmark, wardrobe, injury, or
mutable-prop loss is not.

## Hard failures

Stop before provider submission when:

- the Prompt is empty or unreadable as UTF-8;
- Prompt provider tokens differ from the private plan or first appear after a Shot
  section;
- the exact population lock is missing or repeated;
- exact quoted dialogue and its readable speaker are outside the owning `Shot N:`
  section;
- the private plan and Storyboard disagree;
- a recurring location is scheduled as independent despite an unfinished location
  state chain, or a nonadjacent revisit is submitted before its state source review;
- the Location master is missing from any Segment set there, including an
  extension, or a tight predecessor frame/video is allowed to own the offscreen
  world or complete population;
- the embedded NPC roster differs from the Location authority or the Segment
  permits an undeclared independent performer;
- an embedded NPC is also bound independently, or a dialogue/story-active performer
  is missing its separate identity/state reference;
- an asset's identity, injury, wardrobe, group, prop, location, or voice state
  conflicts with the Storyboard.

Do not add deterministic Prompt-prose validators beyond these binding checks.
Creative review may request a better Prompt, but it must judge the generated video
and authored intent rather than enforce a textual template.

Do not repair upstream story or Storyboard authority locally. Do not assemble the
final film, replace native dialogue, mix final sound, or create subtitles.
