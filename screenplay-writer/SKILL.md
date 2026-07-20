---
name: screenplay-writer
description: "Create or repair English children's educational stories and horizontal cinematic production scripts. Use for translation, age classification, story.md, or an all-table screenplay.md whose drama, visible action, character staging, entrances, gaze, dialogue, sound, timing, and continuity must be explicit."
---

# Children's Educational Film Writer

## Purpose

Turn supplied story material into an age-appropriate educational story or one
executable horizontal large-screen screenplay. The screenplay release is:

```text
TASK_DIR/screenplay-writer/screenplay.md
```

Age-appropriate does not mean hiding every injury. When injury or death is causal,
show the contact, wound, physical condition, and consequence clearly enough to
understand; do not routinely replace them with occlusion, dust, reaction-only
coverage, or vague aftermath. Keep the depiction non-exploitative: no gore,
dismemberment, exposed tissue, wound fetish, or prolonged suffering as spectacle.

## Stage Router

Select one stage and read only its Prompt:

| Stage | Authority | Result | Prompt |
| --- | --- | --- | --- |
| Translate | parsed source input | validated English translation object | [translation_gen.md](references/prompts/translation_gen.md) |
| Classify audience | translated title and story | one age-band value | [age_band_gen.md](references/prompts/age_band_gen.md) |
| Prepare story | title, content, age band | `story.md` | [story_gen.md](references/prompts/story_gen.md) |
| Write screenplay | `task.json`, `story.md` | `screenplay-writer/screenplay.md` | [story_to_screenplay_gen.md](references/prompts/story_to_screenplay_gen.md) |

Stages do not borrow one another's work. Translation preserves meaning;
classification selects an audience; story preparation shapes narrative; screenplay
authoring converts the approved story into dramatic production authority.

For screenplay work, also read the
[production-script contract](references/screenplay-segment-contract.md). The Prompt
owns creative decisions; the contract owns Markdown structure, columns, values,
timing syntax, and IDs.

## Screenplay Ownership

| Screenplay Writer | Seedance Master |
| --- | --- |
| Scene drama and Scene-Unit packing | final Shot and Segment implementation |
| story-required scale/view and audience focus | lens, focal length, composition, and camera placement |
| visible action, reaction, objectives, and completion | camera path, support, speed, and edit execution |
| entrances, movement, spatial relationships, facing, gaze, and addressee | blocking refinement and cinematographic realization |
| exact dialogue, speech gates, delivery, BGM, SFX, ambience, and silence | lighting, exposure, color, provider Prompt, and asset bindings |

The Writer can require a story-facing view such as `wide`, `reaction`, `close_up`,
`insert`, or `pov`. It does not prescribe how the camera department executes it.

## Workflow

1. Read the active authority and Prompt completely.
2. At screenplay stage, understand the whole film before authoring the contract
   tables by hand.
3. Run the structural validators below.
4. Repair authored Markdown manually, then reread the tables as one film for
   causality, performance, spatial clarity, age suitability, rhythm, and repetition.

All commands are subject to the production-script contract's Authorship Boundary.

## Execution

```text
python3 screenplay-writer/scripts/build_screenplay.py build --task-dir TASK_DIR
python3 screenplay-writer/scripts/build_screenplay.py check --task-dir TASK_DIR
python3 screenplay-writer/scripts/validate_role_asset_scope.py --task-dir TASK_DIR
```

Release only after all commands pass, the role gate reports
`image_asset_generation: UNLOCKED`, and semantic rereading finds no filler or
contradiction.

## Scope Boundary

Do not choose visual style, appearance design, palette, materials, costume/prop
design, asset IDs, generated media, detailed cinematography, lighting, provider
parameters, Storyboards, or executable Seedance Prompts.
