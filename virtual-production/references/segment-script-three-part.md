# Seed Master Route B Segment Script

The canonical Script is the unchanged Seed Master fixed-format `segment-NNN.md`:
YAML shooting-plan/source metadata followed by Part 1 overall setup and atomic
manifest, Part 2 ordered internal Shots, and Part 3 acceptance.

Virtual production does not wrap, summarize, convert, or locally compile this
file. It validates source hashes and builds a separate execution plan containing
actual asset/provider values.
