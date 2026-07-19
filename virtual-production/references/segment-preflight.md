# Segment preflight

Immediately before a provider call, verify the exact Seed Master Script and
execution-plan hashes, Route A hashes, trace status, shooting-plan fields,
predecessor attempt lock, model capability limits, media counts, duration, native
audio, watermark, last-frame values, and the current final-Prompt/`assets.json`
compatibility receipt. Preflight never rewrites a Script or
chooses another operation.
