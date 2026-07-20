# Seed Master Route B Segment Script

The canonical Script is the unchanged Seed Master fixed-format `segment-NNN.md`:
YAML shooting-plan/source metadata followed by Part 1 overall setup and atomic
manifest, Part 2 ordered internal Shots, and Part 3 acceptance.

Part 1 includes one scene-specific `[CINEMATIC DIRECTION]` selection that names all
ordered Shots without mechanically copying a rule library. Every Part 2 Shot
contains one exact full `cinematic_shot_contract`, followed by its concise exact
provider-core `staging_implementation` once in Direction. Runtime rejects the Script before
asset materialization if that coverage is absent or misbound.

The Route B Script is the audit artifact. After validation, runtime removes the
redundant source-coverage, cinematic-contract, and line-contract sections from the
provider text. It never removes their proved setup/Direction implementations.

For adjacent Segments sharing a Scene, runtime accepts exactly two serial contracts:

- settled motivated cut: `multimodal_reference` plus
  `approved_provider_last_frame`, bound as an ordinary soft `reference_image`, with
  no reference video/audio and no strict first-frame role;
- unfinished action/performance/blocking/camera phase: `video_extension` plus the
  approved complete predecessor with preserved audio.

The manifest gate rejects same-Scene parallel execution, `strict_first_frame`, and
matched-cut tail evidence before materialization or any provider call.

Virtual production does not wrap, summarize, convert, or locally compile this
file. It validates source hashes and builds a separate execution plan containing
actual asset/provider values.
