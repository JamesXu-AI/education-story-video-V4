---
name: previsualize-cinematography
description: "Use Seedance Master Route A to turn the approved all-table screenplay into one self-contained cinematic storyboard.md. Use for directing, shot design, blocking, gaze, camera, lighting, sound, editing, reference planning, generation-segment packing, and continuity. Release only storyboard.md; never create a compile manifest, data companion, storyboard JSON, or generated media."
---

# Cinematography Previsualization

## Purpose

Invoke `seedance-master-skill` Route A to add direction and cinematography without
rewriting screenplay meaning. The sole release is:

```text
TASK_DIR/previsualize-cinematography/storyboard.md
```

Read [storyboard-contract.md](references/storyboard-contract.md) before invoking
Seedance Master. This project contract overrides older Route A packaging that asks
for a compile manifest or any storyboard companion.

## Authority

- Preserve every screenplay Scene Unit, Shot, Line, duration, entrance, movement,
  gaze, completion state, audience focus, sound cue, and continuity handoff.
- Add only directing, camera, composition, movement, light, color, production
  design treatment, edit logic, reference purpose, and Generation Segment packing.
- Choose Shot count and camera behavior by cinematic judgment. No fixed Shot quota,
  single-movement rule, or one-to-one Route B Prompt paragraph mapping exists.
- Build a location state chain across the whole film. An inserted story, flashback,
  imagined sequence, or different location does not reset the last physical state
  of a recurring set.
- Return missing or contradictory dramatic authority to `screenplay-writer`.
- Use IDs only for traceability inside `storyboard.md`; never let IDs replace
  readable character names, actions, spatial relationships, or cinematic choices.

## Workflow

1. Read the complete approved `screenplay.md` and production-design authorities.
2. Understand the film before choosing shots or Generation Segments. For every
   recurring location, identify its separate temporal evidence and world/population
   evidence, production-design-authored fixed-set elements, embedded NPC
   population, independent performers, persistent anchors, mutable props, and
   allowed changes. Bind the Location master in every Segment set there, including
   video extensions; a predecessor frame or video never owns the offscreen set or
   full population. Never assign dialogue or independently directed behavior to
   an embedded NPC; return that role-treatment conflict to production design.
   In a continuation or revisit, do not also bind standalone identity/prop images
   for a subject already carried by the temporal video/frame: overlapping subject
   authority can create duplicate instances. Add a separate visual reference only
   for a genuinely new entrant or the explicit target state of an on-screen
   transformation, and say that it is the same subject rather than another one.
   Treat a continuity-authorized closed roster that is absent from the selected
   temporal evidence as a returning entrant when the Segment makes it visible
   again. Bind the roster, enumerate its unique members, give each one a single
   first-visible event, and prohibit any second instance after that event.
   Provider reference media applies to the whole Generation Segment; a later Shot
   cannot deactivate it. If an exiting roster and an entering roster require
   mutually exclusive visual authority, end a Generation Segment after the visible
   exits and start a dependent successor that omits the exited roster reference
   and binds only the entering roster.
3. Invoke Seedance Master Route A with the original request, upstream authorities,
   and the project storyboard contract.
4. Author one coherent `storyboard.md` by judgment; never generate missing creative
   fields with Python or templates.
5. Validate without rewriting it:

   ```bash
   python3 previsualize-cinematography/scripts/validate_storyboard.py --task-dir TASK_DIR
   ```

6. Reread it as director, cinematographer, editor,
   performer, sound designer, continuity supervisor, and Seedance specialist.

## Release Gate

Release only when `storyboard.md` is self-contained, executable, concise, and
contains no JSON, YAML metadata block, compile manifest, trace object, or companion
authority. The release directory must contain only `storyboard.md`.

Do not continue to Route B, write Seedance Prompts, generate images or video, or
publish any other artifact.
