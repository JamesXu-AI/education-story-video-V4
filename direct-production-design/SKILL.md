---
name: direct-production-design
description: "Understand the approved story and screenplay, then author exact visual-asset plans for characters, silent groups, props, appearance states, dressed Location masters, and the semantic split between embedded background NPCs and independent performers. Execute those plans without changing story, performance, or cinematography."
---

# Direct Production Design

## Boundary

Own production design, the visual bible, model-authored image prompts, image assets,
and character voice references. Do not write story, dialogue, performance calls,
camera design, Storyboards, Seedance Prompts, editing, subtitles, or final sound.
Use only repository-local providers. Do not call another image Skill.

Begin only after the screenplay role-asset gate returns `PASS` and image generation
is unlocked. Read `task.json`, `story.md`, the current screenplay and performance
tables, the current Storyboard when present, and the visual standard. An optional
aesthetic study is offline evidence only; its source frames never enter a provider
request.

## Single model-authored plan

Before any provider call, the production-design model must author the complete
`direct-production-design/production-design-plan.json`. It must contain every
semantic catalog field, media path, exact ordered reference binding, and complete
structured `generation_prompt` for every asset.

Python is an executor and validator only. It may:

- reject missing, unknown, contradictory, or stale fields;
- compare model fields with writer-owned role and Scene coverage;
- serialize the exact `generation_prompt` JSON object;
- schedule the explicitly authored reference graph;
- attach observed local paths and provider URLs after generation.

Python must not infer, default, complete, rewrite, merge, prepend, append, or repair
any semantic field or Prompt content. It must not derive an asset ID, description,
member roster, appearance state, role treatment, reference list, background,
expression, anatomy, style instruction, exclusion, or location fact. If any such
field is absent or wrong, stop and rewrite the model plan.

## Prompt contract

Every asset owns exactly one structured `generation_prompt` with these exact keys:

- `intent_en`
- `subject_en`
- `background_en`
- `composition_en`
- `continuity.reference_asset_ids`
- `continuity.locks_en`
- `style_en`
- `exclusions_en`

The provider receives the canonical JSON serialization of this object, unchanged.
No wrapper, suffix, global negative block, emergency correction, story example, or
second style paragraph may be added by code or by a later department.
The complete serialized image Prompt is limited to 3,500 characters. Patch or
override language is invalid; rewrite the object coherently instead of adding a
correction.

Character, appearance-state, prop, and ensemble assets use the single exact
pure-white background authority declared by the plan contract. A dressed Location
master describes its real environment instead. Do not mention a forest,
room, or other Scene environment in a pure-white asset Prompt.

The style section uses the single exact project style authority. Do not imitate a
brand, studio, franchise, artist, renderer, or protected identity.

## Character actors

Create one full-body identity image and one unique voice WAV/URI for every speaking
entity. A character record is a reusable actor card, not one plot assignment. Its
`actor_profile` contains only:

- `name_en`
- `personality_en`
- `screen_presence_en`
- `acting_range_en`

Do not place story objectives, relationships, first-line delivery, current emotion,
victory, defeat, injury, death, repentance, or Scene/Segment behavior in the actor
profile or identity Prompt. Temporary visible states belong in explicit
character-owned appearance-state assets.

Every character plan carries a model-authored exhaustive `body_topology`. Natural
quadrupeds remain four-legged; birds retain two legs and two wings; insects retain
their authored leg and wing plan. Expression never authorizes extra arms, hands,
legs, wings, tails, trunks, or hybrid anatomy. Code validates counts but never
guesses anatomy from a name or species word.

## Silent role groups

The model authors one `ensemble_roster` plan row for every writer-owned silent
`group_role_type_en`. Its ordered `allowed_member_types_en` must exactly equal the
writer authority. The Prompt and catalog row must state the closed roster and exact
positive subject count. A writer-owned one-shot silent individual may use an exact
one-subject closed roster; never inflate it to two subjects to satisfy a group
assumption. Do not introduce a relative, pet analogue, hybrid, filler, speaking
character, duplicate, reflection, silhouette, or background cameo.

An ensemble asset is not automatically a background NPC. It is a reusable visual
role asset. Production design must read the role's actions, entrances, exits,
interactions, gaze relationships, state changes, recurrence, and continuity needs
before choosing how that asset participates in a Location.

## Props, states, and locations

Create an independent prop only when it materially controls recognition, action,
state, repeat continuity, or fixed-location interaction. Do not create quota props.
Fixed furniture, installed objects, and stable set dressing belong to the Location;
do not create separate prop assets merely to keep them from disappearing.

An appearance-state asset references exactly its owning character and changes only
the model-authored visible state.

A dressed Location master is production design's complete environment and stable
population decision, not a generic background. After understanding the screenplay's
actions, interactions, routes, blocking needs, recurring geography, and continuity,
the production-design model authors `fixed_set_elements_en`: the necessary fixed
furniture, installed props, and stable dressing visibly built into the master.
Every sentence must already appear in that Location's
`generation_prompt.continuity.locks_en`; Python checks and copies it but never
derives a set element from an object word or story example.

Production design then partitions every writer-owned on-screen role asset into two
ordered, disjoint, model-authored lists:

- `embedded_npc_asset_ids`: incidental, non-speaking scene population whose stable
  presence is part of the Location. It has no individually controlled entrance,
  exit, action, interaction, gaze/addressee relationship, state change, or identity
  continuity that the story must direct.
- `independent_performer_asset_ids`: every speaking role and every silent role that
  performs a story action, enters or exits on cue, interacts, changes state, carries
  a reaction or gaze, or needs independent identity and continuity control.

The Location image visibly contains its fixed set, independent fixed props, and
`embedded_npc_asset_ids` only. Its generation Prompt references exactly the ordered
fixed props followed by embedded NPC assets. Independent performers must not appear
in the Location image; their character or ensemble references are added beside the
Location at Seedance generation. A change only in independent performers does not
require a new Location master. A changed embedded population does. An NPC that later
needs individual performance must be reclassified upstream and the affected
Location master regenerated.

Python validates coverage, ordering, disjointness, stable Scene presence, and the
hard ban on embedding dialogue or explicitly state-changing performers. It never
classifies a role, infers NPC status from keywords, or fills either list.

## Voice references

Each character plan owns an exact voice description, sample text, and provider
speech rate, plus a complete structured `voice_generation_prompt`. The provider
receives that object unchanged; Python adds no delivery instruction or identity
reference prose. Duration follows the exact text and natural delivery; never force
a fixed duration. Normalize only to 48 kHz stereo 16-bit PCM. Provider word timing
must cover every sample word without anomalous gaps. Do not share a voice file
between characters.

## Storage and reuse

Store the single reusable catalog at repository-root `assets/assets.json` and all
media/evidence under repository-root `assets/`. Task-local asset catalogs or media
are forbidden. Persist stable unsigned object URLs; never persist TOS query
signatures.

Exact Prompt equality permits mechanical reuse. When an old/current Prompt differs,
run `--inspect-semantic-reuse`; Codex itself decides visible equivalence using
`references/codex-asset-semantic-reuse-review.md`. Code never makes that semantic
decision. A changed dependency invalidates its consumers.

## Execution

```text
python3 screenplay-writer/scripts/validate_role_asset_scope.py \
  --task-dir TASK_DIR
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --inspect-semantic-reuse
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --max-workers 4 \
  [--codex-reuse-asset ASSET_ID ...] \
  [--codex-regenerate-visual-asset ASSET_ID ...]
python3 direct-production-design/scripts/validate_production_design.py \
  --task-dir TASK_DIR
```

Use `--regenerate-asset` for a rejected image and its dependent images. Use
`--regenerate-voice` only for a rejected character voice. If the Prompt or semantic
row is wrong, rewrite `production-design-plan.json` first.

Validators return `PASS` or concrete errors. Correct current files directly. Do not
create compatibility shims, migration contracts, approval ledgers, or history.
