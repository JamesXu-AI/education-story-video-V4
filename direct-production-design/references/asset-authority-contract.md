# Production asset authority

`direct-production-design/production-design-plan.json` is the complete
model-authored semantic and Prompt authority. `assets/assets.json` is the final
repository-owned reusable catalog. Media and provider evidence live under
repository-root `assets/`; task-local asset state is forbidden.

## No Python authorship

The plan explicitly supplies every asset ID, description, media path, catalog
semantic field, ordered reference asset ID, and structured generation Prompt.
Python validates and copies these values. It may attach only observed media results:
the local path and stable provider URI. Missing or contradictory semantic values are
errors; code must never infer or fill them.

Every `generation_prompt` uses exactly:

- `intent_en`
- `subject_en`
- `background_en`
- `composition_en`
- `continuity.reference_asset_ids`
- `continuity.locks_en`
- `style_en`
- `exclusions_en`

The provider receives this object as canonical JSON with no added prefix, suffix,
negative block, style wrapper, or repair sentence.
The serialized object is capped at 3,500 characters and rejects patch/override
language. Replace a wrong field; never append a corrective paragraph.

Character, costume/state, prop, and ensemble assets use the contract's exact
pure-white studio background. Location masters use their actual environment.

## Reusable characters

A character is an actor card. `actor_profile` contains only name, personality,
screen presence, and acting range. Story goals, first-line delivery, temporary
emotion, relationships, plot outcomes, injuries, and Scene/Segment actions are not
identity fields. A temporary visible state is a separate appearance-state asset.

`body_topology` is model-authored and exhaustive. Code validates its counts but does
not guess anatomy.

## Groups and Location role treatment

An ensemble row is model-authored for one writer-owned silent role type. Its ordered
member types and subject count are closed. A location row explicitly provides
model-authored `embedded_npc_asset_ids`, `independent_performer_asset_ids`, and
`fixed_set_elements_en`. Production design derives the fixed set and classifies the
role treatment by understanding the screenplay. Dialogue and story-active roles
remain independent; only stable incidental population may be embedded. The
Location Prompt references fixed props and embedded NPCs, never independent
performers. Code compares and copies the authored values; it does not classify a
role, construct either list, or infer furniture from keywords.

## URLs and evidence

Catalog URIs are stable unsigned object URLs. TOS query signatures are temporary
transport credentials and must not enter the catalog or handoff. Prompts, provider
requests, responses, and voice timing evidence remain beside the media, not in the
catalog.

## Reuse

Exact Prompt equality allows direct reuse. Textual change requires direct Codex
semantic review of the old Prompt, current Prompt, and existing image. Generic code
must not decide equivalence or contain task names, species, props, or story examples.
