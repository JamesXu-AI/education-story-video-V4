# Location Continuity Package Contract

`direct-production-design/location-continuity-packages.json` is the current textual
authority for recurring set geography. The initial production-design builder writes
one package for every `location_master` in `assets.json`.

Each package contains only:

- the screenplay Scenes bound to the location;
- the model-authored `embedded_npc_asset_ids` and
  `independent_performer_asset_ids` role-treatment partition;
- the model-authored `fixed_set_elements_en` list of necessary fixed furniture,
  installed props, and stable dressing visibly built into the Location master;
- environment, lighting, palette, and material state;
- named zones, capacities, paths, travel times, entrances, and exits;
- fixed obstacles and fixed-prop placements;
- immutable landmarks and their world relationships.

Production design derives the fixed-set list by understanding the screenplay's
interactions, routes, staging needs, and recurring continuity. It is not a quota,
keyword lookup, or Python-generated inventory. The compiled package list must
exactly match the Location row in `assets.json`.

These records are also the persistent-anchor authority. Every fixed-set element,
fixed obstacle, fixed prop, or landmark remains present through every Scene bound
to this location unless the screenplay visibly changes or removes it. A tight frame
may place an anchor offscreen; offscreen is not absent. Route A must carry these
anchors into its Location State Plan, and Route B must use the latest approved
readable evidence when a predecessor final frame is too tight to prove them.

Mutable story props are not promoted to fixed topology. Their last approved
on-screen state travels through the location state chain until an authored action
changes it. Production design defines the object; cinematography owns state
inheritance and visibility; virtual production may not reset either by convenience.

The package has no `view_family`, camera position, framing, derived visual, or
Seedream generation phase. The matching `location_master` in `assets.json` is the
only full-frame dressed-set image and declares exact `fixed_set_elements_en`,
`embedded_npc_asset_ids`, and `independent_performer_asset_ids`. The Location image
contains the embedded NPC population but excludes independent performers.
Storyboard and Segment prompts reuse that master with the package's topology text,
then bind the required independent performers separately.

Any material change in time, weather, lighting, set state, topology, fixed props,
embedded population, or landmarks requires a distinct location master in the
task-authored production-design plan. A change only in independent performers does
not. Neither case may be represented as a derived view of an incompatible master.
