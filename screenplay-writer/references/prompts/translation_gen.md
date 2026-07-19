# Story Input Translation Prompt

Use this fixed prompt for every task, including input already written in English.
Convert the parsed source input into the exact translation JSON contract below.
Do not recreate, shorten, or replace this prompt in conversation.

## Input Contract

The source input contains only these values:

```json
{
  "resolution": "<480|720|1080|4k>",
  "country_en": "<English country name>",
  "title": "<title in any language>",
  "content": "<complete story in any language>"
}
```

Treat `title` and `content` as authoritative source text. `resolution` and
`country_en` are validated production fields, not translation fields, and must not
appear in the output. Do not use `country_en` to relocate, rewrite, or add facts to
the source; downstream `direct-production-design` owns that task-level country lock.

## Translation Rules

Translate the complete title and content into accurate, natural English. Preserve
the source order, plot, causal relationships, character identities, names,
kinship, social roles, dialogue speakers, beliefs, values, lesson, emotional
framing, setting, historical context, holidays, rituals, objects, gestures,
symbols, and ending.

This stage is translation and cultural analysis only. Do not summarize, censor,
soften, age-adapt, moralize, modernize, relocate, add events, remove repetition,
resolve ambiguity, or turn the story into Segments. Preserve disturbing or unsafe
source facts accurately in `content_en`; child-safe adaptation belongs only to the
later Story stage after the fixed age-band classification stage.

Keep paragraph and dialogue order. Preserve direct speech as direct speech. Use
consistent English transliteration for names and culture-specific terms.
Retain an established English form when one is unambiguous; otherwise transliterate
instead of replacing the term with a different culture's equivalent. Briefly
clarify an untranslatable term inside the English sentence only when its meaning
would otherwise be lost.

Identify the source language in English. If the content mixes languages, name the
primary language and mention the meaningful secondary language in
`cultural_context_en`. If the input is already English, preserve its meaning and
structure while correcting only clear grammar or encoding defects.

Write `cultural_context_en` as a concise factual description of the cultural,
religious, geographic, historical, and family context that the story must preserve.
When the source supports them, include binding facts about region, era, domestic
life, clothing, craft, holiday or ceremonial state, social formality, and everyday
objects. Explicitly leave specifics unknown when the source does not establish
them; never invent culture to make the field more colorful.
Write 3-12 distinct `cultural_invariants_en`: only binding facts that a
later age-safe adaptation must preserve. Include relevant names, relationships,
beliefs, holidays, forms of respect, setting, symbols, values, and the source
lesson. Do not put generic video-production or child-safety rules in this list.

Every output string must be English and the JSON file must use UTF-8 encoding.
Valid Unicode punctuation, names, and transliterations are allowed. JSON-escape
line breaks and quotation marks correctly. Do not include Markdown, commentary,
confidence scores, alternative translations, or fields outside the exact contract.

## Exact Output Contract

```json
{
  "title_en": "<complete accurate English title>",
  "content_en": "<complete accurate English translation with escaped line breaks>",
  "source_language_en": "<source language name in English>",
  "cultural_context_en": "<concise source-culture context in English>",
  "cultural_invariants_en": [
    "<binding cultural fact>",
    "<binding cultural fact>",
    "<binding cultural fact>"
  ]
}
```

## Validation

Before returning JSON, compare the translation against the source from beginning
to end. Confirm that no event, dialogue turn, relationship, cultural or religious
meaning, consequence, or ending was omitted or invented; names and key terms are
translated consistently; all values are English in valid UTF-8; the cultural invariants
are source-specific; and the output contains exactly the five required fields.
