# Location Continuity Package Contract

`direct-production-design/location-continuity-packages.json` is the current textual
authority for recurring set geography. The initial production-design builder writes
one package for every `location_master` in `assets.json`.

Each package contains only:

- the screenplay Scenes bound to the location;
- environment, lighting, palette, and material state;
- named zones, capacities, paths, travel times, entrances, and exits;
- fixed obstacles and fixed-prop placements;
- immutable landmarks and their world relationships.

The package has no `view_family`, camera position, framing, derived visual, or
Seedream generation phase. The matching `location_master` in `assets.json` is the
only full-frame Scene-cast environment image and declares the exhaustive
`included_role_asset_ids`. Storyboard and Segment prompts reuse that master with the
package's topology text; they may choose cameras but may not request or persist
empty or character-free camera-background plates.

Any material change in time, weather, lighting, set state, topology, fixed props, or
landmarks requires a distinct location master in the task-authored production-design
plan. It must not be represented as a derived view of an incompatible master.
