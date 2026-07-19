# Production asset contract

Use `direct-production-design/assets.json` as the single current production-design
plan and base-design catalog. Store all asset media and generation evidence under
`direct-production-design/assets/`, with one folder per asset.
Allowed types are `character`, `costume`, `prop`, `location`, `location_master`,
`sound`, and `ensemble_roster`. Each dialogue-character record also carries the
model-authored exhaustive `body_topology` used by both still-image and Seedance
generation. Each record has one canonical ID,
one declared type, a current `planned`, `ready`, or `failed` status, a concise
definition, and task-local media plus a provider-accessible URI after generation.
Do not store approvals, hashes, provider attempts, cache metadata, or history in the
catalog. Briefs, prompts and provider request/response evidence belong beside the
media inside the asset folder.

`direct-production-design/production-design-plan.json` is the model-authored semantic
input to this lifecycle. It is task-specific and precedes `assets.json`; it is not an
approval, candidate, cache, or compatibility record. Generic generation code may
read this plan but may not contain branches for particular story names or objects.

## Role separation

- character images define stable identity and appearance for dialogue-owning
  entities only;
- costume plates define one character appearance state;
- prop images define object appearance and state;
- location masters define stable environment geometry and fixed props;
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

Each character includes stable identity and a concrete performance definition:
core desire/belief/pressure, emotional arc, attention, listening, speech
preparation, embodied acting, settling, and forbidden empty behavior. Each
production-ready set uses a location master with navigable geometry and declared
fixed props.

When a fixed plot prop has an independent asset, its location master must be
generated after that prop and must use the prop image as an ordered direct reference.
The location may place the object but may not redesign its geometry or silhouette.

Generate with the repository-local Seedream wrapper. `assets.json` is written before
generation and updated as each asset finishes. The final media, brief, compiled
prompt, provider request and provider response stay together in that asset's own
folder. Do not create a candidate, attempt, approval, or pending asset tree.
Structurally verify the returned image and register it directly. If inspection or
the independent reviewer finds a problem, regenerate and replace the affected
current image; do not create an approval chain.

A downstream Prompt/real-input compatibility failure is also an inspection
failure. Repair the task-semantic plan when the exact state asset is missing, or
force regeneration when the brief is correct but the actual media is wrong. Never
make an incompatible real image pass by relabeling its metadata.

All external calls default to 3600 seconds.
