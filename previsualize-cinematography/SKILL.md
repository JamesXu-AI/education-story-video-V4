---
name: previsualize-cinematography
description: Transparently invoke seedance-master-skill for cinematography and return its output unchanged. Use when this repository routes screenplay-to-storyboard, camera, blocking, lighting, sound, editing, or other Seedance previsualization work through the cinematography department; this Skill is only a compatibility shell and owns no creative, routing, schema, validation, or publishing logic.
---

# Cinematography Previsualization · 摄影预演

Act only as a transparent alias for `seedance-master-skill`.

1. Invoke `seedance-master-skill` once with the user's original request and the
   complete upstream inputs supplied to this Skill.
2. Let Seed Master select and execute its own route, workflow, authoring,
   validation, and delivery contract.
3. Return Seed Master's complete output unchanged.

Do not interpret, summarize, rewrite, enrich, repair, constrain, normalize,
validate, fingerprint, cache, convert, render, or wrap either the inputs or the
output. Do not define local cinematography rules, schemas, prompts, scripts,
validators, publishers, fallbacks, or acceptance gates.

When the repository requires artifact paths, save Seed Master's returned Route A
`storyboard.md` and `storyboard-compile-manifest.json` bytes verbatim at
`TASK_DIR/previsualize-cinematography/`. Creating the directory and writing those
unchanged files are transport operations only. The manifest is Seed Master's own
mandatory Route A output, not a local companion. Do not create `storyboard.data.json`,
an envelope, a compatibility artifact, or an alternate Storyboard representation.

If `seedance-master-skill` cannot be invoked, report the invocation failure as the
blocker. Never substitute local reasoning or another Skill.
