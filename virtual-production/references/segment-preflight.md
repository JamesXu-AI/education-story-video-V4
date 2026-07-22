# Segment preflight

Immediately before a provider call, verify the exact natural-language Prompt,
private Segment plan, execution-plan hashes, Storyboard hash, shooting-plan fields,
predecessor attempt lock, model capability limits, media counts, duration, native
audio, watermark, last-frame values, and current private binding/catalog
compatibility. Prompt validation is limited to UTF-8 readability, non-empty text,
provider-token set/placement, one exact population lock, and exact dialogue/speaker
placement in the owning Shot. Preflight never rewrites a Prompt or chooses another
operation.
