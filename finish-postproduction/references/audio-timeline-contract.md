# Native Audio Timeline Contract

## Main-flow sources

The default and only main-flow audio layer is:

```text
Seedance native-sync = synchronized dialogue + breaths + reactions + room tone
                       + ambience + foley + effects + diegetic sound
background_music_source = none
```

Every Seedance Segment must contain a real native audio stream generated with
`generate_audio=true`. Each speaking character's fixed
`speaker_reference_audio` constrains voice identity; Seedance still generates the
actual synchronized words. Never replace that stream, shift it away from picture,
or use the identity-reference WAV as delivered dialogue.

Seedance must not generate non-diegetic background music. Both the current Segment
Script and submitted provider Prompt must explicitly declare `No background music`.
`seedance_background_music: false` is accepted in the Segment Script, but the
submitted Prompt must still contain the textual prohibition.

## Timeline behavior

`.pending/finish-postproduction/audio-timeline.json` contains exactly one
`native-sync` track with one sample-aligned event per Segment. It declares:

```text
music_provider: none
seedance_background_music: false
background_music_source: none
```

Do not pre-create a SeedAudio track, score policy, or score anchors in this main-flow
artifact. Motivated cuts use a synchronized edge de-click. Authored dissolve/fade
boundaries may overlap picture and native audio by the exact authored duration.
Native dialogue, effects, and ambience never move across a Segment boundary.

## Delivery

The final delivery manifest declares:

```text
voice_audio_source: speaker_reference_audio
dialogue_source: seedance
native_background_audio_source: seedance_ambience_and_foley_no_music
seedance_background_music: false
background_music_source: none
```

SeedAudio scripts and prior experimental artifacts may remain under `.pending`, but
the main workflow never reads, mixes, promotes, or declares them.
