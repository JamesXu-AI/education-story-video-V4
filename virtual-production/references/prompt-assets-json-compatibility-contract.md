# Final Prompt / assets.json semantic compatibility contract

URL resolution is not semantic compatibility, and byte equality is not a semantic
test. Before publishing a Seedance execution plan, freeze the exact final Route B
Prompt, every provider-token responsibility, the selected `assets.json` semantic
row, and every owned Storyboard requirement in
`.pending/virtual-production/asset-compatibility-review-packets/segment-NNN.json`.
Catalog media URIs are persistent unsigned object URLs. TOS query signatures are
temporary transport credentials and must not appear in the catalog or a handoff.

For every static `@ImageN` or `@AudioN`, require the Prompt element namespace to
equal the bound `assets.json` asset ID. Compare the Prompt responsibility and
Storyboard requirements with the catalog's declared `asset_id`, `type`,
`description_en`, reusable character `actor_profile`, character ownership,
appearance/injury state, closed group member types, prop bindings, body topology,
voice identity, and sound role. Story objectives and shot-local performance never
come from the reusable catalog. Do not download provider media or compare provider/local bytes in
this gate. Hashes only bind the review to the exact Prompt and current catalog row
so stale reviews cannot be reused.

Write one
`.pending/virtual-production/asset-compatibility-reviews/segment-NNN.json` using
contract `prompt-assets-json-compatibility-review-v2`. Cover every provider token
in order and record required Prompt facts, the corresponding `assets.json` facts,
conflict domains, compatibility class, reason, every source requirement, and an
overall `PASS` or `FAIL`.

Use `exact_state_match` only when `assets.json` declares the required identity and
state. For every visible character or character-owned costume image, require the
final Prompt's canonical `body_topology_contract` to equal the owning character's
current model-authored catalog object exactly. A reference image and a generic
`anatomy errors` negative are not substitutes for that positive contract. Use
`compatible_nonconflicting_subset` only when the catalog row controls a
strict subset and declares no conflicting fact. Examples:

- Prompt requires Elephant but the binding selects asset `lion`: `FAIL` identity.
- Prompt requires injured/defeated Lion but the binding selects the normal `lion`
  asset: `FAIL` injury/body state.
- Prompt requires injured/defeated Lion and selects
  `costume-lion-defeated`, whose catalog row declares that state: compatible.
- Prompt binds a character image but omits or changes its exhaustive limb sets,
  total limb count, or non-limb appendages: `FAIL` body topology.

A second reference, Prompt prose, negative instruction, URL change, or file-byte
comparison cannot repair a semantic conflict.

On `FAIL`, name the exact provider token, required facts, `assets.json` facts,
conflict domains, affected asset IDs, and concrete repair. Validation writes
`.pending/virtual-production/asset-rework-requests/segment-NNN.json`, routes it to
`direct-production-design`, and blocks execution-plan publication, preflight,
upload, and Seedance submission. Repair the semantic plan/catalog or create the
missing exact-state asset, then rerun affected Route B binding, review,
materialization, and downstream gates.

Any final Prompt, binding namespace, `assets.json` semantic row, catalog hash,
provider URI value, or predecessor-attempt change makes the old packet/review stale.
Only a current `prompt-assets-json-compatibility-receipt-v2` with
`overall_verdict: PASS` may enter an execution plan and production record.
