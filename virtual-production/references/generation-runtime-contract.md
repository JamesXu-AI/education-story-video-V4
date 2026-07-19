# Generation runtime

Provider attempts and clips live under `.pending/virtual-production/`. Every
execution plan freezes its Seed Master Script hash, Storyboard/manifest hashes,
Seedance parameters, token ordering, asset URLs, dependency wave, and predecessor
attempt identity. It also freezes the PASS review hash for the exact final Prompt
and selected `assets.json` semantic rows; a changed Prompt, binding, or semantic
row invalidates resume/reuse.

Prepare runtime media only after preflight. A complete predecessor preserves its
audio for true video extension. A matched-cut tail is exactly 2.0 seconds and has
no audio stream; the provider last frame is uploaded separately. Cached runtime
media is rejected when its execution-plan hash or predecessor attempt changes.

Retries repeat the identical request at most three times. A successful output has
readable video, Seedance-native audio, and a provider-returned last frame.
