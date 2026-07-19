# Segment generation task

One Seed Master `segment-NNN.md` equals one Seedance task and one audiovisual
output. Ordered Shots inside that file remain internal camera/edit units.

The request uses the exact materialized model, duration, resolution, ratio,
operation-specific media, `generate_audio=true`, `watermark=false`, and
`return_last_frame=true`. Prompt tokens are never textually replaced with URLs;
the provider assigns them from the ordered media list maintained by the execution
plan.

The plan is invalid without a current semantic PASS comparing the exact final
Prompt/provider bindings with the selected `assets.json` declarations. Asset IDs
and URLs alone are insufficient when their declared roles or states conflict.

Dependent media is exactly one of: complete predecessor with preserved audio;
silent final 2.0-second predecessor tail plus provider last frame; or provider last
frame only.
