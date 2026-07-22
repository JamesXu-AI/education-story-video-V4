---
name: education-story-video-v4
description: Orchestrate the complete repository-local educational story-video pipeline from task input and story preparation through screenplay, production design, cinematography, Seedance generation, review, automatic postproduction handoff, subtitles, and verified final masters. Use when Codex must run, resume, coordinate, or diagnose the full project rather than execute only one department, including requests to continue until the final captioned video is ready.
---

# Education Story Video V4

Act as the sole top-level orchestrator for this project. Route work to the
repository-local departments, enforce their gates and ownership boundaries, and
continue until the requested production outcome is complete.

## Non-negotiable Skill boundary

While executing a production task under this main Skill, use no Skill outside this
repository except the two explicit exceptions below. Apply this prohibition to
explicit calls, implicit triggering, suggested helpers, and fallback Skills. Never
use an unlisted external image, video, audio, browser, document, presentation,
spreadsheet, review, visualization, or media-production Skill.

The sole system-Skill exception is `skill-creator`. Use it only when the user
explicitly asks to create, update, or validate this project's own Skill files.
Never use `skill-creator` to perform story, design, cinematography, generation,
review, sound, editing, or delivery work.

The sole external production-Skill exception is `seedance-master-skill`, with two
explicit entry points. `previsualize-cinematography` invokes Route A and releases
only one self-contained `storyboard.md`. `virtual-production` invokes Route B and
any shooting-plan-required observed successor recompilation, then resolves provider
tokens and executes the returned natural-language Scripts. No other department may
invoke Seed Master.

Treat only these repository-local Skills as internal production departments:

- `screenplay-writer/SKILL.md`;
- `direct-production-design/SKILL.md`;
- `previsualize-cinematography/SKILL.md`;
- `virtual-production/SKILL.md`;
- `seedance-video-review/SKILL.md`;
- `finish-postproduction/SKILL.md`.

Do not discover, introduce, or substitute another Skill beyond those two explicit
exceptions. Repository-local scripts,
provider adapters, and tools explicitly authorized by an internal department are
implementation mechanisms, not permission to invoke an external Skill.

## Orchestration rules

Before executing a department, read its complete `SKILL.md` and follow its declared
inputs, outputs, commands, gates, and hard boundaries. Read only the references it
directly requires for the current work. Keep every authority with its owning
department; never repair an upstream fact inside a downstream artifact.

Operate inside one explicit `TASK_DIR`. Inspect current artifacts and validator
results before resuming. Reuse valid current work, restart at the earliest invalid
or incomplete gate, and rebuild only affected downstream outputs. Stop on missing,
contradictory, stale, or unparseable authority instead of inventing replacements.
Treat dialogue ownership, silent group-role membership, exact ordered silent
member-type composition, first-dialogue portrait-expression authority, Scene scope,
the current model-authored `production-design-plan.json`, and story-significant
appearance/prop facts as asset-bearing invalidation inputs.
A textual difference between a ready image's colocated brief and the newly compiled
current brief is a semantic-review candidate, not proof that the image is stale.
Run the production-design semantic-reuse inspection before generation. Codex itself
must compare the complete old/current briefs and inspect the existing image whenever
the visible result is uncertain. Reuse it when both briefs can be satisfied by the
same visible pixels; regenerate it only when the current authority requires a
materially different visible result. Do not call `SEED_MODEL`, another text model,
or hard-coded story/species/object rules for this decision. Pass every direct Codex
decision explicitly to the builder; unresolved candidates must stop before any
visual generation or overwrite.
Before Seedance materialization, compare every final Prompt/provider binding with
the semantic authority declared in repository-root `assets/assets.json`. Treat a
wrong identity, role, appearance/injury state, costume, group, prop, location or
voice declaration as a blocker, route it to production design, and invalidate its
Prompt compatibility receipt and affected execution plans. Do not download assets
or compare provider/local file bytes for this semantic gate.

Use repository-local `seedance-video-review` to diagnose a specific artifact or
completed video and whenever a Seed Master serial shooting-plan row requires direct
predecessor observation before successor recompilation. Send each actionable issue
to its owning department and recheck only the corrected result. Keep `NO_ISSUES` in
the active task; never turn review into a separate approval-file workflow.

## Production sequence

1. Establish `TASK_DIR`, validate `task.json`, and require the current `story.md`.
   When story preparation is part of the request, use only the repository-local
   prompts and scripts under `screenplay-writer`; do not use another Skill. Story
   must provide goals, obstacles, visible/audible triggers, actions, reactions,
   differentiated ensemble behavior, causal turns, and changed results without
   choosing cameras.
2. Execute `screenplay-writer`. Build and check its single all-table,
   cinematic-widescreen `screenplay.md` release, then run every check defined by
   that department. Its Prompt owns creative decisions and its production-script
   contract owns syntax; do not restate, weaken, or supplement either here. Any
   structural, semantic, staging, timing, dialogue, sound, or continuity failure
   returns to Screenplay. Downstream departments may not repair it indirectly.
3. After the role/asset-scope gate returns `PASS` with image generation unlocked,
   start `direct-production-design`; do not launch a separate Codex screenplay
   reviewer.
   Production design also owns semantic scene dressing: it interprets playable
   action, interactions, routes, geography, and recurrence to author each
   Location's necessary fixed furniture, installed props, and stable dressing.
   It also understands the screenplay well enough to separate stable incidental
   NPC population from independent performers. The Location master visibly contains
   its fixed set and embedded NPCs only; every dialogue or story-active role remains
   a separate performer reference. Both role lists are model-authored and carried
   into `assets.json`; Python validates and copies them but never classifies a role
   or infers content from keywords.
   Before production-design generation, run `build_initial_production_design.py
   --inspect-semantic-reuse`. For every returned candidate, Codex directly decides
   whether the old and current visual meanings are equivalent by applying
   `direct-production-design/references/codex-asset-semantic-reuse-review.md`.
   Rerun the builder
   with `--codex-reuse-asset ASSET_ID` for each equivalent candidate and
   `--codex-regenerate-visual-asset ASSET_ID` for each materially changed candidate.
   The visual-only decision must preserve a current character voice. This review is
   part of the active Codex task and is never delegated to a provider model.
4. Require the current deterministic `screenplay.md`, fast role-gate PASS, and
   current valid production-design authorities before executing
   `previsualize-cinematography`.
   Pass the original request and complete upstream inputs to that shell. It invokes
   `seedance-master-skill` under the repository-local single-file Storyboard
   contract. Persist only the returned `storyboard.md` at
   `TASK_DIR/previsualize-cinematography/`; compile manifests, Storyboard JSON,
   traces, ledgers, companions, wrappers, and alternate representations are
   forbidden. Route A must return missing or contradictory screenplay authority to
   its owner, then convert accepted story-facing Shot rows into final one-task Shots
   with motivated camera, layered blocking, selective ensemble control, and passed
   cinematic reviews. Route A must also author one Location State Plan inside
   `storyboard.md`. Every recurring location declares adjacent or nonadjacent
   inheritance, its latest temporal state source, separate Location-owned
   world/population evidence, persistent
   anchors, and allowed changes. Intervening inserts or imagined Scenes do not
   reset a physical set. Route A must make
   every overlapping `scene_ids` pair directly serial: `multimodal_reference` plus
   provider-last-frame soft reference image for settled cuts, or complete-predecessor
   `video_extension` for unfinished phases. Soft reference is not strict/API
   first-frame control, and matched-tail evidence is not a third same-Scene mode.
5. Require the current `storyboard.md`, then execute `virtual-production`. It
   invokes Seed Master Route B and persists one exact natural-language Prompt plus
   one private execution plan per Segment. Seed Master freely authors the Prompt's
   structure, Shot/beat representation, camera language, length, wording, and time
   expressions. Python checks only non-empty text plus the private plan's provider
   tokens before the first Shot, one exact population lock, and exact quoted
   dialogue/speaker placement in the owning `Shot N:` section; it does not apply a
   general creative-prose template. The separate private plan carries deterministic
   transport authority.
   Before URL materialization,
   directly reject any provider token whose declared media kind or asset namespace
   cannot resolve to the matching current row in `assets.json`. Do not create
   compatibility packets, review drafts, rework JSON, or another hidden creative
   authority. Route B
   may clarify execution language but may not reinvent Scene conflict, blocking,
   Shot focus, camera logic, or continuity. Before materialization
   or any provider call, virtual production must reject same-Scene parallel,
   strict-first-frame substitution, matched-tail substitution, missing direct
   predecessor dependency, or a mismatch between settled/unfinished phase and the
   selected one of the two serial contracts.
   Every Segment set in a Location, including video extension, must bind that
   Location master in every Shot. Predecessor media is temporal evidence only and
   cannot authorize the offscreen set or complete population. Route B must also
   author one readable population lock whose embedded roster exactly matches the
   Location authority and whose independent performers are explicitly permitted.
   A performer or movable prop already carried by temporal evidence must not also
   receive a standalone identity reference in the successor. Separate visual
   references are reserved for genuinely new entrants or explicit transformation
   target states and must be described as the same subject, preventing duplicate
   instances. A continuity-authorized closed roster that is not visibly carried by
   the selected temporal evidence is a returning entrant when it must reappear:
   bind its roster reference, enumerate every unique member in the natural-language
   Prompt, assign one first-visible event per member, and forbid any member from
   being generated again after that reveal.
   Provider references apply request-wide; Shot prose cannot deactivate one. When
   an exiting roster and an entering roster require mutually exclusive authority,
   make the completed exit a Generation Segment boundary. Bind only the exiting
   roster before that boundary and only the entering roster in its dependent
   successor.
6. On a direct asset-resolution failure, stop the affected Seedance submission and
   return to `direct-production-design`. Report the failure in command output only;
   never create a substitute Prompt, asset, review packet, or rework artifact. Fix
   the authoritative production design or the manually authored Route B binding,
   then rerun from current sources.
   For a nonadjacent location revisit, virtual production must wait for the named
   location-state source review and bind current temporal evidence plus the
   Location-master world/population authority, adding the latest human-approved
   readable wide state when visible set changes require it.
   Code may validate or extract an explicitly selected frame; it may not select or
   invent continuity evidence.
7. When a serial shooting-plan row requires observed predecessor evidence, use
   `seedance-video-review` on that exact provider attempt. After `NO_ISSUES`, let
   virtual production invoke Seed Master for the required observed successor
   recompilation; correct any issue through its owning department. `NO_ISSUES` may
   include a semantically equivalent internal-cut shift or adjacent movable-prop
   landing when the complete dramatic exchange, identities, fixed set, authorized
   population, ownership, action completion, and safe ending remain valid. Never
   regenerate solely for frame-exact timing or centimetre-level prop placement.
   Instead, make the observed final action phase and actual prop position the
   successor's temporal authority. Missing, duplicated, teleported, inaccessible,
   story-changing, or causally mistimed state remains a blocking issue.
8. Execute `finish-postproduction` after every current Segment has one valid
   audiovisual result and production record. Deliver clean and captioned masters,
   exact subtitle files, and the final delivery manifest.

## Automatic postproduction handoff

For a full-pipeline production request, treat `generation-state.json` reporting
`GENERATED` as an intermediate handoff, never as completion. In the same active
run, immediately execute:

```text
python3 finish-postproduction/scripts/finish_postproduction.py \
  --task-dir TASK_DIR
```

Do not return control merely to ask whether postproduction should continue. Reuse
the current generated Segment media and resume the smallest failed finishing step
until postproduction emits `FINAL_MASTER_READY`. Stop at raw Segment videos only
when the user explicitly limits the requested deliverable to raw Segment clips.

The automatic handoff must produce and validate all of the following:

- `finish-postproduction/final-clean-master.mp4`;
- `finish-postproduction/final-captioned-master.mp4`;
- `finish-postproduction/subtitles/master.srt`;
- `finish-postproduction/subtitles/master.vtt`;
- `finish-postproduction/final-delivery-manifest.json`.

Probe both masters as real media. Require a readable video stream and synchronized
audio stream, a non-empty captioned master, complete subtitle files, and a final
runtime no greater than 240 seconds before reporting success.

Do not skip a gate because a later artifact already exists. Do not create extra
approval files, hashes, compatibility records, intermediate authorities, or
parallel department variants unless an internal Skill explicitly requires them.

## Completion

Treat a full production request as complete only after the clean master, captioned
master, SRT, VTT, and delivery manifest exist, their owning validators pass, both
master media streams are readable, and postproduction emits `FINAL_MASTER_READY`.
Report concrete blockers with the owning department, failed gate, affected
artifact, and smallest valid next action.
