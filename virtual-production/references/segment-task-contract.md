# Segment generation task

One Seed Master `segment-NNN.md` equals one Seedance task and one audiovisual
output. Its prose may represent shots, beats, transitions, or continuous action in
any form and does not have to expose the private plan's Shot count.

The request uses the exact materialized model, duration, resolution, ratio,
operation-specific media, `generate_audio=true`, `watermark=false`, and
`return_last_frame=true`. Prompt tokens are never textually replaced with URLs;
the provider assigns them from the ordered media list maintained by the execution
plan.

The plan is invalid when its private provider bindings conflict with the selected
`assets.json` declarations or approved Storyboard. Prompt parsing is limited to
the declared token set/placement, exact population lock, and dialogue ownership;
other prose does not make the transport decision.

Temporal dependent media is exactly one of: the complete approved predecessor with preserved
audio for a true unfinished extension, or the approved provider last frame for a
settled motivated cut. It is always combined with the current Location-master
image. The temporal source owns recent action state; the Location owns the complete
set and population outside the crop.
