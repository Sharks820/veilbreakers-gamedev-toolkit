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
- Add behavioral tests for `_river_requests_waterfall` and `_derive_waterfall_placement_from_path`.
- Continue the terrain/architecture split by moving terrain handlers and controller-owned passes behind a stable API boundary.
