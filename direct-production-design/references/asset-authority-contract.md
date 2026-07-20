# Production asset contract

Use repository-root `assets/assets.json` as the single current production-design
plan and base-design catalog. Store all asset media and generation evidence under
repository-root `assets/`, with one folder per asset. A task directory never owns,
mirrors, or symlinks asset media.
Allowed types are `character`, `costume`, `prop`, `location`, `location_master`,
`sound`, and `ensemble_roster`. Each dialogue-character record also carries the
model-authored exhaustive `body_topology` used by both still-image and Seedance
generation. Each final record has one canonical ID, one declared type, a concise
definition, and repository-owned media plus a provider-accessible URI. Transient
`planned`, `ready`, and `failed` lifecycle state exists only while the builder runs;
it is removed from the final reusable catalog.
Persist only each object's stable unsigned URL. TOS query signatures such as
`X-Tos-*` are temporary transport credentials and are forbidden in the catalog;
the upload layer derives the public URL directly from bucket, endpoint, and key.
Do not store approvals, hashes, provider attempts, cache metadata, or history in the
catalog. Briefs, prompts and provider request/response evidence belong beside the
media inside the asset folder.

`direct-production-design/production-design-plan.json` is the model-authored semantic
input to this lifecycle. It is task-specific and precedes `assets.json`; it is not an
approval, candidate, cache, or compatibility record. Generic generation code may
read this plan but may not contain branches for particular story names or objects.
The plan must bind `character_background_location_id` to one current model-authored
location. Use that location's task-authored design as the visible environment for
every character, costume-state, and ensemble image. Character-class
images must visibly retain that bound environment; never replace it with a plain,
solid-color, studio, catalogue, cutout, empty, or transparent backdrop. The embedded
background is presentation context only and never becomes a second environment
authority.
An individual character or costume-state image contains exactly one living subject:
the bound character. Its forest environment must contain no other person, animal,
insect, crowd, silhouette, reflection, or distant cameo. Ensemble images contain
only their closed roster and no background population.

The final location image is Scene-cast, never character-free or empty. Derive its
`included_role_asset_ids` from every on-screen performance entity used anywhere in
the bound Scene, generate the role assets first, then reference and visibly include
every individual and complete ensemble exactly once. A location may bind multiple
Scenes only when their exhaustive role-asset sets are identical.

## Role separation

- character images define stable identity and appearance for dialogue-owning
  entities only;
- costume plates define one character appearance state;
- prop images define object appearance and state;
- Scene-cast location masters define stable environment geometry, fixed props, and
  the exhaustive visible role set of their bound Scene;
- ensemble plates are one group portrait per explicit non-speaking cinematic role,
  may mix only the exact ordered `allowed_member_types_en` sharing that role, and
  exclude every unlisted species/type, every dialogue-owning character, and every
  anonymous member of a dialogue portrait's species/type;
- sound assets define one ambience, foley, effect, or diegetic-music role;
- required unique speaking-voice WAV/URI remains inside each dialogue character record.

Every dialogue character voice uses the natural duration determined by its exact
task-authored sample text, voice direction, and explicit Seed Audio `speech_rate`.
Those authorities live in the semantic plan and colocated `voice.brief.json`;
provider word subtitles must prove that every exact sample word lands inside the
generated audio's actual duration without anomalous internal or edge silence.
Provider output is normalized only to 48 kHz stereo 16-bit PCM, never time-scaled,
padded, or trimmed to manufacture a fixed duration.

The screenplay owns performance and story state. The Storyboard owns shot-local
performance staging and camera/light. Never make one asset silently own another
department's decisions.

The shared textual visual-style contract defines render language. The asset catalog
does not carry a global Look image or style-reference ID.

## Character and environment depth

Each character is a reusable actor card, not a role assignment for one plot. Its
`actor_profile` contains only `name_en`, `personality_en`, `screen_presence_en`, and
`acting_range_en`. Do not persist screenplay objectives, Scene/Segment behavior,
relationships, current emotional arcs, line delivery, victory, defeat, injury, or
other plot state in the character record. Those decisions remain in the task-side
screenplay, performance map, Storyboard, and appearance-state assets. Each
production-ready set uses a location master with navigable geometry and declared
fixed props.

When a fixed plot prop has an independent asset, its location master must be
generated after that prop and must use the prop image as an ordered direct reference.
The location may place the object but may not redesign its geometry or silhouette.

Generate every visual asset at the repository-local Seedream 5.0 Pro endpoint's
maximum supported 16:9 production size, currently the explicit `2816x1584` request,
through the repository-local Seedream wrapper. Do not send the unsupported `4K`
preset name to this endpoint. `assets.json` is written before
generation and updated as each asset finishes. The final media, brief, compiled
prompt, provider request and provider response stay together in that asset's own
folder. Do not create a candidate, attempt, approval, or pending asset tree.
Structurally verify the returned image and register it directly. If inspection or
the independent reviewer finds a problem, regenerate and replace the affected
current image; do not create an approval chain. Visual regeneration must preserve
the current character voice unless `--regenerate-voice` is separately requested.

A downstream Prompt/real-input compatibility failure is also an inspection
failure. Repair the task-semantic plan when the exact state asset is missing, or
force regeneration when the brief is correct but the actual media is wrong. Never
make an incompatible real image pass by relabeling its metadata.

All external calls default to 3600 seconds.
