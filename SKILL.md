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
explicit entry points. `previsualize-cinematography` invokes Route A and transports
its Storyboard package unchanged. `virtual-production` invokes Route B and any
shooting-plan-required observed successor recompilation, then resolves provider
tokens and executes the returned Scripts. No other department may invoke Seed
Master.

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
the semantic authority declared in `direct-production-design/assets.json`. Treat a
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
2. Execute `screenplay-writer`. Build and check the screenplay package, then run
   the fast role/asset-scope gate. Do not proceed unless every Scene has its current
   cinematic dramatic contract and passed semantic Screenplay Gate, every Dramatic
   Beat has one visual focus and complete block coverage, dialogue is embedded in
   action/reaction, and the Scene changes visual/spatial state. A failure returns to
   Screenplay; no downstream camera or Prompt patch may disguise it. Every retained
   adjacent same-Scene Segment boundary must already be classified for serial soft
   first-frame reference after a settled motivated cut, or serial predecessor-video
   reference for an unfinished action/performance/blocking/camera phase. Same-Scene
   `independent` is a screenplay failure.
3. The screenplay collaboration must directly complete its generatability, action
   density, dialogue occupancy, closure, continuity, merge, and waiting audit before
   the fast role/asset-scope gate. After that gate returns `PASS` with image
   generation unlocked, start `direct-production-design`; do not launch a separate
   Codex screenplay reviewer.
   Before production-design generation, run `build_initial_production_design.py
   --inspect-semantic-reuse`. For every returned candidate, Codex directly decides
   whether the old and current visual meanings are equivalent by applying
   `direct-production-design/references/codex-asset-semantic-reuse-review.md`.
   Rerun the builder
   with `--codex-reuse-asset ASSET_ID` for each equivalent candidate and
   `--codex-regenerate-visual-asset ASSET_ID` for each materially changed candidate.
   The visual-only decision must preserve a current character voice. This review is
   part of the active Codex task and is never delegated to a provider model.
4. Require the current deterministic screenplay package, fast role-gate PASS, and
   current valid production-design authorities before executing
   `previsualize-cinematography`.
   Pass the original request and complete upstream inputs to that shell. It invokes
   `seedance-master-skill` and returns the result unchanged. Persist Seed Master's
   returned `storyboard.md` and `storyboard-compile-manifest.json` bytes verbatim at
   `TASK_DIR/previsualize-cinematography/`; do not add a local schema, converted
   companion, wrapper, or acceptance layer. `storyboard.data.json` does not exist
   and is forbidden throughout the repository. Route A must return any missing
   action/spatial/visual focus to Screenplay; it must convert approved Dramatic
   Beats into one-task Shots with motivated camera, layered blocking, selective
   ensemble control, and passed five-question cinematic reviews. Route A must make
   every overlapping `scene_ids` pair directly serial: `multimodal_reference` plus
   provider-last-frame soft reference image for settled cuts, or complete-predecessor
   `video_extension` for unfinished phases. Soft reference is not strict/API
   first-frame control, and matched-tail evidence is not a third same-Scene mode.
5. Require that final Route A package, then execute `virtual-production`. It invokes
   Seed Master Route B and persists its Segment Scripts/trace/ledgers. Before URL
   materialization, compare every provider-token responsibility and owned
   Storyboard requirement with the selected semantic row in `assets.json`. Only a
   current Prompt/assets.json semantic compatibility PASS may enter an execution
   plan. SHA values bind the decision to current Prompt/catalog data but never
   substitute for the semantic comparison. Route B may clarify execution language
   but may not reinvent Scene conflict, blocking, Shot focus, camera logic, or
   continuity. A Prompt missing exact Shot translation or the fixed cinematic
   direction firewall is blocked before provider submission. Before materialization
   or any provider call, virtual production must reject same-Scene parallel,
   strict-first-frame substitution, matched-tail substitution, missing direct
   predecessor dependency, or a mismatch between settled/unfinished phase and the
   selected one of the two serial contracts.
6. If that gate emits
   `.pending/virtual-production/asset-rework-requests/segment-NNN.json`, stop all
   affected Seedance submissions and return to `direct-production-design`. Use the
   required/catalog facts, conflict domains, and asset IDs to repair
   `production-design-plan.json`, `assets.json`, or the Route B binding. Never bind
   the normal/healthy `lion` row when the Prompt requires an injured, transformed,
   or alternate-costume asset. If semantic asset inventory changes, regenerate
   affected Route A and Route B artifacts. Media-byte equality is outside this
   gate; a transport URL change requires plan rematerialization but not a semantic
   FAIL when the selected `assets.json` declaration is unchanged.
7. When a serial shooting-plan row requires observed predecessor evidence, use
   `seedance-video-review` on that exact provider attempt. After `NO_ISSUES`, let
   virtual production invoke Seed Master for the required observed successor
   recompilation; correct any issue through its owning department.
8. Execute `finish-postproduction` after every current Segment has one valid
   audiovisual result and production record. Deliver clean and captioned masters,
   exact subtitle files, and the final delivery manifest.

## Current-contract-only rule

Every department artifact handed downstream must use the latest contract currently
defined by its owning department. When an existing task contains a complete but
older artifact, perform a one-way in-place upgrade through the owning department's
current publisher or writer before continuing. Verify that creative and execution
data are unchanged except for required contract metadata, derived fingerprints,
and newly required current-contract fields.

Do not add legacy compatibility branches, fallback parsers, version aliases, gate
exceptions, or downstream acceptance paths. Do not preserve shadow legacy copies
or emit legacy-version compatibility records. The explicitly required current
Prompt/`assets.json` semantic review and receipt are execution gates, not legacy
compatibility shims. If an older artifact cannot be upgraded losslessly,
regenerate that artifact with the current owning department instead of teaching
current code to accept the older contract.

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
