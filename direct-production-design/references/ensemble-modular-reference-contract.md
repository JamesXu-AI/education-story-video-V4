# Silent Role-Type Group Portrait Contract

An `ensemble_roster` now contains exactly one real group portrait for one
non-speaking screenplay role type. The image contains at least two subjects, records
the complete allowed non-speaking entity set, and records the complete excluded
dialogue-entity set. A speaking character, its lookalike, duplicate, silhouette,
reflection, or background cameo is forbidden from every group portrait.
The complete `excluded_dialogue_character_names_en` list is also recorded. The
exclusion applies to the identity's entire species/type, including an anonymous,
recolored, resized, or otherwise restyled individual—not only to a literal lookalike.

Each roster record also carries `allowed_member_types_en`, copied exactly from the
writer authority. Group composition is closed: the portrait contains one subject
per ordered type, except that a single broad type is duplicated only once to meet
the two-subject minimum. No unlisted species/type, taxonomic relative, domestic or
pet analogue, hybrid, or decorative filler is permitted. For example, an authored
tiger never authorizes a cat. The recorded `subject_count` must equal this compiled
closed roster count.

`screenplay-writer/screenplay.md` Performance Entity and Performance Call tables own speech, performance
granularity, narrative-role membership, and obligations. Production design derives
one silent visual group per narrative role; each roster member in `assets.json` lists every
non-speaking entity in that role to the same approved group portrait. A silent `individual`
remains independently blockable even though it receives no single-character photo.
The Segment Storyboard owns the selected entity, population instruction, activity
area, and screen occupancy while preserving those authorities.

Virtual production may bind the group portrait as silent role-type appearance
authority, but must explicitly tell Seedance to render only the Storyboard-selected
silent entity or count. It must never reproduce the reference image's photographed
population automatically and must never introduce an excluded dialogue character.
If the requested population cannot be expressed within the verified reference
budget, return the Storyboard for simplification; do not silently omit an entity.
