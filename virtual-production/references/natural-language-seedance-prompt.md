# Free-Form Seedance Prompt Guidance

`segment-NNN.md` is the exact model-facing Prompt. It is authored by Seedance
Master from the approved Storyboard and is not a machine-readable contract.
Runtime and audit data live in the separate private Segment plan.

## Authorship freedom

Choose the Prompt form that best communicates the intended video. There is no
mandatory:

- title, heading, label, section, paragraph order, or paragraph count;
- a total Shot count, consecutive Shot numbering, or one-to-one mapping between
  Storyboard rows and Prompt paragraphs; a dialogue cue does require its owning
  `Shot N:` label so exact line placement can be verified;
- limit of one camera movement per Shot or passage;
- word count, vocabulary allowlist/denylist, sentence pattern, or required phrase;
- ban on time ranges, seconds, beats, relative timing, or sub-second descriptions.

The author may use continuous prose, bullets, numbered shots, beat descriptions,
time windows, dialogue blocks, or another clear form. Several camera actions may
be combined when their sequence and motivation are coherent. A single continuous
Prompt passage may cover several Storyboard shots, and one Storyboard shot may be
expanded into several model-facing beats when useful.

## Creative priorities

Use judgment to communicate what matters for the current Segment: subjects,
reference roles, environment, blocking, performance, gaze, action causality,
camera behavior, dialogue and native sound, lighting/color, continuity, and the
desired end state. Prefer observable, executable detail over generic praise, but
this is authoring advice rather than a lexical rule.

Every `@ImageN`, `@VideoN`, and `@AudioN` declared by the private plan must appear
in the Prompt, with no undeclared token, and each must be introduced before the
first `Shot N:` section. Their surrounding prose and ordering remain free. The
private plan remains the transport authority for media binding.

Location and temporal references have distinct creative responsibilities. A
Location master represents the approved dressed world and embedded population;
predecessor evidence represents the recent visible state it can actually show.
Independent performers, new entrants, and transformation targets should be
described clearly enough to avoid identity duplication. Include the private plan's
exact `population_lock_en` once; no fixed heading or paragraph placement is
required for it.

Each private-plan dialogue cue must place its exact quoted text and readable
speaker inside its owning `Shot N:` section. Speaker/listener behavior, ambience,
effects, music, silence, and timing may otherwise be expressed in whatever form
best serves the generated performance.
The provider duration parameter in the private plan remains authoritative for the
task's total duration; Prompt timing language is free-form and is never parsed by
Python.

## Runtime boundary

After UTF-8 decoding, Python checks non-whitespace text and exactly three authored
bindings: provider-token set/placement, one exact population lock, and exact
dialogue/speaker placement in its owning Shot. It does not scan or reject other
Prompt prose for formatting, total or consecutive Shot numbering, camera
movements, internal terminology, JSON-like text, repetition, word count, or timing
expressions.

Python continues to validate only separate deterministic transport facts, such as
the private plan identity, provider operation and total duration, dependency
evidence, media roles, catalog resolution, capability limits, and execution
parameters. Do not extend the small binding parser into a creative prose gate.
