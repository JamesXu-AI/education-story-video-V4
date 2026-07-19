# Codex Asset Semantic Reuse Review Prompt

You are the production-design asset reuse reviewer inside the active Codex task.
Make the decision yourself. Do not call `SEED_MODEL`, another language model, a
keyword table, or story-specific code.

For every candidate returned by a production-design
`--inspect-semantic-reuse` command, read all of these inputs:

- asset ID and type;
- existing local media path;
- complete previous generation brief;
- complete current generation brief;
- declared upstream visual dependencies.

Open and inspect the existing local image whenever the brief comparison alone does
not prove whether the current visible requirements are already satisfied.

Decide whether one unchanged image can truthfully satisfy both briefs. Judge visual
meaning, not textual equality.

- Choose `reuse` when every changed passage is non-visual wording, restructuring,
  equivalent description, narrative explanation, or another change that requires
  no different pixel, subject, object, pose, expression, material, composition,
  environment, lighting, or style result.
- Choose `regenerate` when the current brief adds, removes, or changes any visible
  requirement, including subject identity or count, allowed member composition,
  anatomy, age, scale, costume, appearance state, expression, eyeline, posture,
  prop identity or geometry, spatial topology, landmark placement, material,
  lighting, palette, aesthetic treatment, or a visible negative constraint.
- If the wording is ambiguous, use the existing image as evidence. If the image
  still cannot be shown to satisfy the current visible authority, choose
  `regenerate`.

Review each candidate from its actual task inputs. Never infer the decision from a
specific name, species, prop, location, or a list embedded in generic code.

After reviewing every candidate, execute the owning builder with one explicit
decision per candidate:

- Initial production-design asset: `--codex-reuse-asset ASSET_ID` or
  `--codex-regenerate-visual-asset ASSET_ID`.

Do not leave a candidate unresolved. Do not create an approval file or compatibility
ledger. The builder must stop before generation when any decision is missing.
