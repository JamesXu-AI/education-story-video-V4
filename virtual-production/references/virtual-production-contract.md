# Virtual-Production Contract

The sole creative input is `previsualize-cinematography/storyboard.md`. For each
Generation Segment, Seedance Master Route B authors one exact natural-language
provider Prompt and one private execution plan. The Prompt is creative prose; the
plan is machine-readable transport authority. Neither may substitute for the other.

The exact provider Prompt is stored at:

```text
.pending/virtual-production/seedance-segment-scripts/segment-NNN.md
```

It follows the free-form authorship boundary in
`natural-language-seedance-prompt.md`. No general heading, section, total Shot,
camera, word, wording, or timing syntax is prescribed. Matching `Shot N:` labels
are required only for dialogue cues whose exact ownership must be verified.

The private plan is stored at:

```text
.pending/virtual-production/seedance-segment-plans/segment-NNN.json
```

It must hold Segment identity, Storyboard hash, duration, operation, dependency,
provider-token mappings, dialogue ownership, final continuity state, and this
model-authored continuity authority:

```text
continuity:
  location_state_chain
  relationship
  state_source_segment_id
  world_binding_ids
  temporal_binding_ids
  embedded_npc_asset_ids
  authorized_independent_performer_asset_ids
  population_lock_en
```

The exact `population_lock_en` appears once in the provider Prompt. Other private
continuity values do not have to appear verbatim or in any fixed place. Every
Segment has one Location-master world
binding active in every Shot. A continuation/revisit additionally has temporal
binding(s) to the reviewed predecessor. The embedded roster must exactly equal the
Location catalog; Segment-authorized independent performers must be a subset of
that Location's independent-performer treatment. The plan is never sent as Prompt
prose.

Python may reject an invalid or stale private transport artifact and resolve
approved media URLs. At the Prompt text layer it checks UTF-8 readability,
non-whitespace content, provider-token set/placement, exact population lock, and
exact dialogue/speaker ownership. It must never invent, fill, summarize,
translate, repair, or otherwise constrain creative Prompt content.
