---
name: direct-production-design
description: "Own the visual bible and derive the current Seedance reference system from story/performance facts: dialogue identities, exact appearance/injury states, silent-role groups, props, and location masters. Consume virtual-production Prompt/assets.json semantic incompatibility requests, repair the semantic plan or exact asset binding, and keep every catalog declaration unambiguous. Never require the screenplay module to read or plan art, and never change story, performance, or cinematography."
---

# Direct Production Design

## Skill invocation boundary

While executing a production task under this Skill, never invoke, load, delegate
to, or depend on any Skill outside this repository. Repository-local department
Skills explicitly named by this project remain internal and may collaborate under
their declared ownership boundaries. The sole system-Skill exception is
`skill-creator`, and only when the user explicitly asks to create or maintain this
project's own Skill files; never use it to perform story or media-production work.

Own art direction, production design, the visual bible, and image-asset execution.
Use only the repository-local Seedream adapter. Every external call has a one-hour
timeout. Never call another image Skill.

## Inputs and authority

Asset planning starts only after
`screenplay-writer/scripts/validate_role_asset_scope.py` returns `status: PASS` and
`image_asset_generation: UNLOCKED`. Read `task.json`, `story.md`, the current
screenplay package, the current Storyboard when present, and the
[Soft & Cute 3D Healing Animation Visual Standard](references/soft-cute-3d-healing-visual-standard.md).
When
`direct-production-design/aesthetic-reference/manifest.json` exists inside the
current task, also read its complete study and validated frame bindings before
authoring the visual bible or any image request. The task story, cultural locks,
screenplay, performance map and current approved asset authorities always outrank
that aesthetic evidence.

The source video, selected source frames and contact sheets are offline analysis
evidence only and never enter any provider request. Translate only general shape,
material, palette and atmosphere observations into the project's shared textual
visual contract and direct asset prompts. Never create or wait for a global Look
image. Never copy a reference identity, costume, prop, location, exact composition,
story action or omission.
Production design owns appearance and environment design, but cannot change story,
presence, dialogue, action, camera, light, or Segment boundaries.

Understand the screenplay and current Storyboard before deciding the complete asset
set. Write `direct-production-design/assets.json` before the first provider call,
then update each asset record from `planned` to `ready` or `failed` as execution
finishes. Every asset entry script re-evaluates the fast role gate before any
external image call.

When
`.pending/virtual-production/asset-rework-requests/segment-NNN.json` exists, treat
it as a current blocking defect report from the final Prompt/`assets.json` semantic
gate. Read its required versus catalog facts, conflict domains, affected asset IDs,
and repair actions before changing the asset plan. Repair the semantic plan,
catalog row, or exact-state asset binding; never bind a generic/normal character
row when the Prompt requires a distinct injured, transformed, disguised, wet,
dirty, or alternate-costume state.

## Outputs

Maintain:

- `visual-production-spec.md`;
- the task-local aesthetic-reference manifest and study when an aesthetic source
  is supplied;
- the model-authored task-semantic `production-design-plan.json`;
- the single plan/catalog `assets.json` and the single media root `assets/`;
- one full-body final-look character portrait and one unique speaker voice WAV/URI
  for every dialogue-owning entity; a portrait includes a prop/accessory only when
  production design determines that the current story, identity or continuity
  requires it, plus a motivated anthropomorphic expression, active attention and
  readable thought; one art-derived group portrait per silent
  screenplay narrative role; appearance states, costumes, props, and location
  masters;
- `location-continuity-packages.json`, containing topology and landmark text only.

The location master is the only full-frame character-free environment image
authority. Reuse it directly for every Scene and Segment bound to that location.
Do not generate a Scene background, global background, camera background, or other
full-frame derivative of a location master. When time, weather, light, set state,
topology, or fixed props materially change, author a distinct location master in
`production-design-plan.json` and bind only the affected Scenes to it.

Each character folder owns its image, voice WAV, brief, prompt, provider request
and provider response together; voice description and URI live only in `assets.json`.
There is no shared directory,
speaker manifest, cast-binding manifest, candidate directory, pending directory or
intermediate character-name mapping. A dialogue character's asset ID is exactly its
performance `entity_id`; silent entity membership is declared directly by its
ensemble-roster record in `assets.json`. Every project-level speaker still requires
one unique, provider-accessible PCM WAV. Never reuse one speaker audio for another
character.

Every task-semantic character plan also owns a model-authored `body_topology` with
one body plan, exhaustive counted limb sets, counted non-limb appendages, total limb
count, and a positive topology lock. Codex derives this from the actual character
and approved portrait; generic code must never infer it from a name or species
keyword. Every downstream character or character-owned appearance-state image
binding must carry this exact topology into its Seedance Prompt.

Every task-semantic character plan also owns `voice_description_en`, one exact
`voice_sample_text_en`, and an explicit provider `voice_speech_rate`. Generate the
sample through the repository Seed Audio provider at the natural duration determined
by that exact text, voice direction, and speech rate. Normalize only the transport
format to 48 kHz, stereo, 16-bit PCM; never pad, trim, stretch, compress, or otherwise
time-scale it to a fixed duration. The sample text must be a short line or excerpt
faithful to that current character. Persist `voice.brief.json`, provider
request/response evidence, the canonical `voice.wav`, and its fresh URI together in
the character folder. Different sample texts are expected to produce different total
durations.

Before running the deterministic builder, the active production-design model must
read the current `story.md`, screenplay, performance map, and aesthetic translation,
then author `direct-production-design/production-design-plan.json`. This is the only
task-specific design authority for dialogue-character appearance, independently
useful props, voice direction/sample/rate, appearance states, locations, topology,
landmarks, and fixed-prop bindings. It must describe the actual current story rather than
fill categories or copy examples.

Repository scripts are generic executors. They may validate IDs and cross-file
coverage, compile prompts, build an asset dependency graph, and schedule generation,
but must never branch on a project character, species, object, country, room, or
location name. Examples in documentation are explanatory only and may not become
keyword logic. If the semantic plan is absent, stale, contradictory, or incomplete,
stop before image generation and have the production-design model rewrite it; do not
fall back to hardcoded defaults.

Aggregate speech ownership across the full current screenplay before generating any
cast image. Only entities with at least one dialogue line receive a single-character
image. Treat every `lead`, every `supporting` role and every other dialogue-owning
individual as a main story character. Every non-human main story character must use
an upright bipedal anthropomorphic performance body standing on two legs, while
retaining unmistakable species head, markings, surface, ears, tail, trunk, wings or
other defining anatomy. Do not generate a quadrupedal or neutral wildlife-form
portrait for a main story character.

All characters, including silent group members, must show anthropomorphic inner
life through gaze, expression, posture, attention and intention. Silent NPC groups
need not share the main-character bipedal body plan unless separately promoted by
the screenplay, but every member must use exactly one coherent species-appropriate
body plan. Anthropomorphic expression must never add arms or hands to a quadruped,
retain extra legs on a biped, or add arms to a bird beyond its two wings and two
legs. Extra, duplicated, missing, fused, detached, or hybrid limbs are forbidden.
Blank wildlife portraits are forbidden. A final-look portrait
may be prop-free. Production design decides whether an independent prop asset is
needed by asking whether the object carries story action, ownership/state change,
repeat continuity, character recognition, or fixed-location interaction. Do not
generate a prop merely to decorate a portrait, fill an asset category, or satisfy a
per-character quota. Ordinary wardrobe and set dressing remain inside character or
location design unless a separate reference is materially useful.

Every silent performance entity already declares `group_role_type_en` as a
dramatic classification; production design creates exactly one portrait per used
role type. Compile the portrait from the complete ordered
`ensemble_member_types_en` authority: include one recognizable subject per exact
member type, duplicate only a lone broad type to make a real group, and forbid
unlisted species, broader relatives, domestic/pet analogues, hybrids, or cute
fillers. A group portrait may mix species sharing that dramatic role, but must
contain only its declared silent member types and entities and must exclude every
dialogue-owning character and every anonymous member of the same species/type, as
well as every lookalike, duplicate, silhouette, reflection, and cameo. Record the
complete forbidden dialogue-character name list beside the roster evidence.

For a dialogue-character portrait, compile its exact expression and thought from
the first writer-authored Dialogue `delivery_en`, together with the Character's
narrative function and behavior. Keep the mouth naturally closed for the still
portrait. Do not substitute a neutral face, catalogue smile, random cuteness,
unrelated emotion, or a later injury state. This presentation expression guides the
portrait only and does not become immutable identity or Segment-state authority.

## Location continuity

Build one topology package per location master following the
[Location Continuity Package Contract](references/location-continuity-package-contract.md).
It owns zones, connections, entrances/exits, obstacles, fixed props, immutable
landmarks, time/weather, palette/materials, and primary light direction. It owns no
view family and produces no derived image. The catalog location master is the only
full-frame environment authority.

A location master containing a fixed plot prop is not independent. Generate the
canonical prop image first, then supply it as an ordered direct Seedream reference
to the location master and require exact geometry, proportions, material, and
silhouette. No secondary environment plate is generated from that master.

The current deterministic screenplay build/check and fast role-gate PASS are
required before this department's assets may be handed to cinematography. There is
no separate screenplay-review response. If later writer collaboration changes
dialogue ownership, silent group membership, Scene environment scope, or
story-significant appearance/prop facts, stop using the affected results, rerun the
role gate, and regenerate affected assets. Never silently bind an image created for
an older role/Scene scope.

## Current execution

```text
python3 screenplay-writer/scripts/validate_role_asset_scope.py \
  --task-dir TASK_DIR
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --inspect-semantic-reuse
# Codex reads references/codex-asset-semantic-reuse-review.md, directly judges every
# returned old/current brief pair and, when needed, opens the existing image. It then
# supplies one explicit decision per candidate:
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --max-workers 4 \
  [--codex-reuse-asset ASSET_ID ...] \
  [--codex-regenerate-visual-asset ASSET_ID ...]
python3 direct-production-design/scripts/validate_production_design.py \
  --task-dir TASK_DIR
```

For real image or character-voice media that contradicts its already-correct
current brief, force that asset and every dependent asset through generation again.
For a character ID this also forces a fresh voice reference without conditioning
on the rejected audio:

```text
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --max-workers 4 \
  --regenerate-asset ASSET_ID [--regenerate-asset ASSET_ID ...]
```

When only a character voice is rejected, preserve the current portrait and use the
voice-only path. Require provider word subtitles to match the complete sample text
exactly. Every word interval must fit inside the provider audio's actual dynamic
duration; the lead-in and trailing silence may each be at most 1.0 second, and no
internal word gap may exceed 0.6 seconds. Reject and retry an incomplete sample or
one with anomalous pauses. Never alter playback speed or add silence to manufacture
a target length:

```text
python3 direct-production-design/scripts/build_initial_production_design.py \
  --task-dir TASK_DIR --max-workers 4 \
  --regenerate-voice CHARACTER_ID [--regenerate-voice CHARACTER_ID ...]
```

If the required state asset is missing or the semantic brief itself is wrong,
first rewrite `production-design-plan.json` from the defect evidence, then run the
builder. For example, a visibly injured Lion requires a Lion-owned injury/appearance
state asset; the normal identity portrait cannot be renamed or reused as that state.
Inspect the new real media and rerun production-design validation. Hand control
back so affected Route B Scripts, compatibility packets/reviews, and execution
plans are rebuilt. Do not clear or ignore the defect merely because generation
returned a URL.

Validators return `PASS` or concrete errors. Correct current files directly. Do not
create hashes, approval records, review ledgers, migration files, or historical
archives.

Exact `.brief.txt` equality allows immediate mechanical reuse. A textual difference
does not mechanically prove staleness: the builder must expose it with
`--inspect-semantic-reuse` and stop before generation. Codex itself compares the
old/current visual meaning and inspects the current image when needed. If the same
pixels satisfy both authorities, pass `--codex-reuse-asset`; if member composition,
portrait expression, identity, aesthetic, geometry, appearance state, or any other
visible requirement materially changes, pass `--codex-regenerate-visual-asset`.
Visual semantic invalidation never regenerates a still-current character voice;
the broader `--regenerate-asset` remains reserved for a directly rejected real
asset, including voice rework for a character ID. This judgment must not call
`SEED_MODEL` or another provider model, and generic code must not contain
task-specific names, species, props, or story branches. Missing Codex decisions are
blockers, never permission to overwrite. The single `assets.json`
may move from its final catalog state back into the current plan state during an
approved repair.

All asset types follow the same storage rule: one asset folder contains all of that
asset's images, audio/video when applicable, briefs, prompts, requests and responses.
`assets.json` is the only asset inventory and status authority.

Expression, thought, and optional portrait props remain generation and visual-review
requirements. Body topology is different: it is a required asset-contract field
because downstream video generation must preserve one exhaustive limb plan across
motion. Reject a catalog that lacks the current model-authored topology; do not
manufacture one with keyword logic.

An aesthetic-reference manifest is provenance evidence rather than an approval
ledger. Its frame hashes protect the selected stills from accidental replacement.
The builder validates that package for offline analysis integrity, exposes no frame
paths to generation, and uses only its written aesthetic translation in direct
asset prompts.

## Boundaries

Do not write dialogue, story events, performance calls, camera/lens/light
design, Storyboards, Seedance Prompts, video, edits, subtitles, or final sound.
