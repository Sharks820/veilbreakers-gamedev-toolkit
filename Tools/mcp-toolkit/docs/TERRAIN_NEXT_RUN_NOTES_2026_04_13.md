## Terrain Next Run Notes

- Split direction: `terrain-core` should own terrain, hydrology, waterfalls, caves, terrain materials, validation, and Unity export.
- `worldbuilding` / architecture should consume terrain outputs, not mutually call terrain back and forth.
- Keep one orchestration boundary. Avoid bidirectional MCP dependency between terrain and architecture.

### Landed in this pass

- `env_generate_waterfall` now publishes the 7-name functional waterfall contract and can materialize those named anchors.
- `compose_map` now forwards waterfall functional-object diagnostics.
- Behavioral coverage added for waterfall contract publication and validation.

### Highest-value next steps

- Wire Quixel ingest metadata from `stack.populated_by_pass["quixel_layer[...]"]` into `terrain_materials.py`.
- Terrain materials still do not consume Quixel/PBR channels, wetness, or wet-rock masks.
- The stricter volumetric validator in `terrain_waterfalls_volumetric.py` is still not enforced in the live runtime path.
- Rivers are still mostly surface/strip based, not a true varying-width volumetric river path with proper bank taper, flow direction, and dedicated foam geometry.
- Add behavioral tests for `_river_requests_waterfall` and `_derive_waterfall_placement_from_path`.
- Clean up remaining terrain lint debt, especially direct `stack.height` writers and the frozen-mutable terrain semantic findings.
- Continue the terrain/architecture split by moving terrain handlers and controller-owned passes behind a stable API boundary.

### Continuation Memory

- Pushed terrain runtime cleanup commit: `708a013` on `feature/terrain-audit-implementation-plan`.
- Landed runtime fixes are terrain-only; unrelated dirty files remain outside the pushed terrain patch set.
- Do not reintroduce bidirectional terrain <-> architecture MCP calls during the split. Keep terrain as a dependency, not a peer caller.
