---
name: virtual-production
description: Invoke seedance-master-skill Route B on the native upstream storyboard.md and storyboard-compile-manifest.json, persist its ordered segment-NNN.md Seedance Scripts unchanged, compare every final Prompt and provider binding with assets.json semantic authority, resolve literal provider tokens, route incompatible assets back to production design, and execute the Seed Master shooting plan with internally maintained Seedance parameters. Use for virtual production, Seedance Script compilation, asset-semantic compatibility, asset-link resolution, dependency-wave generation, or resuming generated Segment clips. Never read or recreate storyboard.data.json.
---

# Virtual Production · 虚拟制片

## Authority boundary

Invoke the external `seedance-master-skill` only for Route B Script authorship and
observed successor recompilation. This is the second authorized Seed Master entry
point in the project; `previsualize-cinematography` remains the Route A entry point.
Do not invoke any other external production Skill.

Consume these upstream authorities directly:

- `TASK_DIR/previsualize-cinematography/storyboard.md`;
- `TASK_DIR/previsualize-cinematography/storyboard-compile-manifest.json`;
- `TASK_DIR/direct-production-design/assets.json`;
- the current screenplay and production-design bibles named by the Storyboard.

`storyboard.data.json` does not exist. Never request, infer, regenerate, convert,
cache, or accept it. Never author a local Storyboard schema or local Prompt compiler.

## Seed Master Route B

Pass Seed Master the original request, exact Storyboard, compile manifest, current
asset catalog semantics (including every visible character's model-authored
`body_topology`), and current provider capability profile. Require its fixed
Route B outputs:

- ordered `.pending/virtual-production/seedance-segment-scripts/segment-NNN.md`;
- `.pending/virtual-production/storyboard-to-prompt-trace.json`;
- `.pending/virtual-production/dialogue-duration-ledger.json`;
- `.pending/virtual-production/boundary-continuity-report.json`.

Persist every `segment-NNN.md` exactly as returned. Each file is one Seedance task
and may contain multiple ordered internal Shots. Preserve literal
`@ImageN/@VideoN/@AudioN`; never place actual URLs inside the provider Prompt.
Require Seed Master to run its own `validate_segment_prompt.py` and
`validate_storyboard_prompt_translation.py` gates before handing Route B back.

Every returned Prompt must contain one scene-specific
`### 1.5 [CINEMATIC DIRECTION]` section and exactly one
full internal `cinematic_shot_contract` for each ordered Shot. The selected direction names all
owned Shot IDs and applies only relevant anti-stage rules; it may not be a pasted
generic paragraph. Each Shot contract must copy the complete approved Storyboard
record and its concise exact provider-core `staging_implementation` must occur once in Direction. Missing,
misordered, or unbound cinematic contracts block materialization. Virtual
production never repairs a theatrical Scene or Shot locally: missing action returns
to Screenplay, false spatial focus/camera motive returns to Route A, and only clear
provider wording returns to Route B.

The persisted Seed Master Script retains source-coverage, Line, and cinematic Shot
contract rows for audit. After every validator and runtime binding check passes,
materialization strips those redundant metadata sections from the actual provider
text; their exact implementations remain in Generation setup or Shot Direction.
This prevents the real Seedance Prompt from becoming a duplicated schema wall while
preserving proof that no approved fact was omitted.

For every active `reference_image` bound to a character or a character-owned
costume/appearance state, require the final provider Prompt to contain exactly one
canonical line using the current catalog values:

```text
- body_topology_contract: {"asset_id":"<bound asset>","body_topology":<exact model-authored object>,"character_id":"<owner>"}
```

Serialize JSON with sorted keys and no insignificant spaces. This is generated from
the task's semantic plan, never from a character/species keyword table. The
contract's limb sets are exhaustive; non-limb appendages must not be reinterpreted
as limbs, and a natural-animal limb pair may not be retained in addition. Generic
phrases such as `preserve anatomy` or `reject anatomy errors` do not replace this
positive topology contract.

For repository handoff, keep the two Route B ledgers at schema version `1.0`, bind
them to the exact Storyboard and manifest hashes, keep Segment order identical to
the compile manifest, and include:

- dialogue ledger: `segment_id`, `duration_seconds`, and ordered `dialogue_cues`
  with `line_id`, `shot_id`, speaker identity, exact text, start, and end;
- boundary report: `segment_id`, `editable_hold_seconds`, `final_visible_state`,
  and `final_sound_state`.

## Asset and value materialization

Require every static manifest element namespace (the text before its first `.`) to
be an exact `assets.json` asset ID. For an ensemble roster member use
`roster-id--member-type-id`. Reserve the namespace `continuity` for provider output
from the one predecessor named by the shooting plan.

Refresh the capability profile, then follow
[Final Prompt / assets.json compatibility](references/prompt-assets-json-compatibility-contract.md):

```text
python3 virtual-production/scripts/refresh_seedance_capability_profile.py \
  --task-dir TASK_DIR
python3 virtual-production/scripts/prepare_asset_compatibility_reviews.py \
  --task-dir TASK_DIR [--segments segment-NNN ...]
```

Read every selected semantic row directly from `assets.json`. Compare its asset ID,
type, description, character ownership, appearance/injury state, authority, group,
prop, body topology, performance, voice and sound declarations with the complete final Prompt and
its owned Storyboard requirements. Author one current
`prompt-assets-json-compatibility-review-v2` per Segment in the generated review
file. Do not download media or compare provider/local file bytes in this gate. Then
run:

```text
python3 virtual-production/scripts/validate_asset_compatibility_reviews.py \
  --task-dir TASK_DIR [--segments segment-NNN ...]
```

Treat identity, declared story state, injury/body state, wardrobe/costume, prop
state, occupancy, group membership/count, location, time/weather, light/color,
voice, sound role, and action phase as compatibility domains. A normal healthy
asset is incompatible when the Prompt requires that character injured or in
another appearance state. Do not attempt to repair a conflicting input with
Prompt wording, a second reference, or negative instructions.

On incompatibility, write `overall_verdict: FAIL`, name the exact conflicting
binding, required versus `assets.json` facts, conflict domains, affected asset IDs, and
repair actions. The validator emits
`.pending/virtual-production/asset-rework-requests/segment-NNN.json`; stop before
execution-plan publication, upload, preflight, or Seedance submission. Route that
request to `direct-production-design`, then rerun every affected downstream gate.

After every selected Segment has a current compatibility PASS, resolve values:

```text
python3 virtual-production/scripts/materialize_seed_master_scripts.py \
  --task-dir TASK_DIR [--segments segment-NNN ...]
python3 virtual-production/scripts/validate_segment_scripts.py \
  --task-dir TASK_DIR [--segments segment-NNN ...]
```

Materialization queries the current asset catalog for real HTTP(S) image/audio
links and writes one internal
`.pending/virtual-production/seedance-execution-plans/segment-NNN.json`. It also
locks `model`, duration, resolution, ratio, native-audio flags, watermark,
last-frame return, task expiry, priority, operation, dependency wave, and the exact
token-to-value replacement. The execution plan is transport authority only; it may
not change a Prompt, dialogue, Shot, reference responsibility, or shooting-plan
decision.
Every plan must carry a current `prompt-assets-json-compatibility-receipt-v2` PASS
binding the final Prompt, provider-token responsibilities, and current
`assets.json` semantic rows. Any Prompt, binding namespace, catalog semantic row,
URI value, or predecessor-attempt change invalidates the packet, review, and plan.
SHA values detect stale artifacts only; they never decide semantic compatibility.

## Shooting-plan execution

Read
[incremental-boundary-precheck.md](references/incremental-boundary-precheck.md).

Generate only Scripts whose Seed Master shooting-plan gate is ready:

```text
python3 virtual-production/scripts/preflight_segment.py \
  --task-dir TASK_DIR \
  --segment-script TASK_DIR/.pending/virtual-production/seedance-segment-scripts/segment-NNN.md
python3 virtual-production/scripts/generate_segment_videos.py \
  --task-dir TASK_DIR --segments segment-NNN ...
```

- `parallel`: compile/materialize all ready wave members and generate them with
  bounded concurrency, but only when adjacent manifest `scene_ids` do not overlap.
- `serial_after_predecessor_review`: wait for the exact predecessor provider
  attempt, call repository-local `seedance-video-review`, and proceed only after it
  returns `NO_ISSUES`. Invoke Seed Master again with that observed attempt; require
  `shooting_plan_status: observed_adapted`; then materialize and generate.
- `video_extension`: bind the complete predecessor video with audio preserved.
- soft first-frame reference: for a settled motivated same-Scene cut, use
  `multimodal_reference` and bind only the provider-returned last frame as an
  ordinary `reference_image`; do not set `strict_first_frame` and do not promise
  identical opening pixels.
- predecessor-video reference: for unfinished same-Scene action, performance,
  blocking/facing/eyeline, entrance/contact, or camera motion, bind the complete
  predecessor video with audio preserved through `video_extension`.
- matched cut: only across an authored Scene/time/state discontinuity, bind exactly
  the predecessor's final 2.0 seconds with all audio removed plus its
  provider-returned last frame; it is not a third same-Scene mode.

Before materialization or provider submission, runtime compares every adjacent
manifest pair. Overlapping `scene_ids` must directly depend on the predecessor and
match exactly one of the two same-Scene contracts above. Parallel, matched-tail, or
strict-first-frame substitutions are hard failures.

Runtime media must match the exact predecessor attempt frozen in the execution
plan. No dependent Prompt, preflight, media upload, or Seedance call may precede
review and Seed Master recompilation. After all waves exist, run generation once
without `--segments` so the complete state is consolidated as `GENERATED`.

Every output must contain readable video, Seedance-native synchronized audio, and
the requested provider last frame. Technical retries may repeat only the identical
request and remain capped at three.

Immediately after each provider result is published, prepare the current incoming
boundary when its editorial predecessor exists. Also prepare a previously generated
successor boundary when the predecessor finishes later. Print
`BOUNDARY_REVIEW_READY` with the strict audiovisual preview, all-frame evidence, and
technical routing record. Small high-confidence color/exposure jumps route to
`finish-postproduction`; a jump above safe correction limits stops later waves for
direct picture-and-sound review. Metrics never decide identity, action, performance,
dialogue, or semantic continuity and never create an approval record.

The active task calls repository-local `seedance-video-review` as soon as the
evidence is ready. If it reports a generation-owned defect, regenerate only the
current Segment before allowing dependent downstream work. If it returns
`NO_ISSUES`, keep that result transient and continue; do not write a PASS file.

## Boundaries

Never change upstream story, dialogue, performance, design, Storyboard, shooting
plan, or Seed Master Script. Never assemble the final film, replace native dialogue,
mix final sound, or create subtitles. Those belong to postproduction.
