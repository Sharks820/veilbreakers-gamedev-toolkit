# Phase 36: World Composer - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Settlement generation producing complete town layouts with road networks, lot subdivision, district zoning, building placement on lots, and street-level props. A generated town is walkable and visually coherent from ground level.

</domain>

<decisions>
## Implementation Decisions

### Road Network Style
- **D-01:** Organic medieval road layout — winding streets radiating from central square, irregularly curved, narrow alleys. Skyrim Whiterun / Novigrad style. L-system with noise perturbation on existing MST backbone.
- **D-02:** Full detail road meshes — extruded curb geometry (raised edges), cobblestone PBR material with proper UV tiling, gutters at building edges. Main roads 4m wide, alleys 2m wide.

### District Zoning
- **D-03:** Concentric ring layout — market square at center → civic ring → residential → industrial → outskirts/walls. Distance from center determines zone.
- **D-04:** Soft gradient boundaries — building types blend at zone boundaries via probabilistic assignment based on distance to zone center. A tavern may appear in residential zone near market edge.

### Lot Subdivision + Building Placement
- **D-05:** OBB recursive split — each road-bounded block splits recursively along longest axis into lots with street frontage. Lot sizes vary by district (market=large, residential=small).
- **D-06:** District-dependent fill rate — market 100%, residential 80% (gardens/courtyards), industrial 95%, outskirts 60% (farmland). Empty lots become open spaces, not marker boxes.

### Street-Level Props
- **D-07:** ALL small, medium, and street-level props are generated through Tripo AI — not procedural geometry. Use asset_pipeline generate_3d with dark fantasy art style prompts. Cache results for reuse across towns.
- **D-08:** Corruption-scaled density — Veil pressure determines prop density AND condition:
  - Low pressure (0.0-0.2): Skyrim-dense (3-5m spacing), pristine condition
  - Medium (0.2-0.5): Moderate (5-8m), weathered condition
  - High (0.5-0.8): Sparse (8-15m), damaged/corrupted
  - Extreme (0.8-1.0): Minimal + desolate — corruption consumes most objects, remaining ones heavily corrupted
- **D-09:** Performance-conscious — fewer high-quality props over many cheap ones. Every prop must be AAA quality, texturally coherent with surroundings, properly integrated into terrain. LOD awareness required.
- **D-10:** Tripo prompts must specify art style matching: "dark fantasy, hand-crafted medieval, PBR-ready" plus corruption level for visual variant generation.

### Claude's Discretion
- Town sizing (number of buildings, radius, generation time)
- Perimeter/wall generation approach (existing _generate_perimeter() can be reused)
- Specific Tripo prompt templates for each prop type
- LOD strategy for prop performance

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Settlement Code
- `Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py` — generate_settlement(), generate_city_districts(), _place_buildings(), _generate_roads(), _scatter_settlement_props(), _voronoi_assign()
- `Tools/mcp-toolkit/blender_addon/handlers/road_network.py` — compute_road_network(), MST edges, road classification, intersection detection, bridge detection
- `Tools/mcp-toolkit/blender_addon/handlers/map_composer.py` — compose_world_map(), _veil_pressure_at(), _pressure_band(), _corruption_variant_for_pressure(), compute_biome_map()
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` — layout helpers

### Upstream Dependencies (completed)
- `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` — Phase 32+33: building system (52 piece types), interior system (spatial graphs, clutter, lighting)
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_grammar.py` — Phase 31+34: terrain generation, biome system
- `Tools/mcp-toolkit/blender_addon/handlers/asset_pipeline.py` — Phase 35: Tripo AI pipeline with texture extraction + post-processing

### Game Context
- VeilBreakers 10 brands: IRON/SAVAGE/SURGE/VENOM/DREAD/LEECH/GRACE/MEND/RUIN/VOID
- Corruption system: Veil proximity affects visual state of everything in the area

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `settlement_generator.py` (2,386 lines): Full settlement generation with building placement, roads, props, interior furnishing, perimeter walls
- `road_network.py` (562 lines): MST-based road computation with switchbacks, bridges, intersection classification
- `map_composer.py` (1,380 lines): World composition with biome maps, Veil pressure, corruption variants
- Poisson disk sampling: Already used in Phase 33 clutter scatter and Phase 31 vegetation — reuse for prop placement
- `_veil_pressure_at()`: Existing corruption calculation for map positions

### Established Patterns
- Pure-logic grammars in `_*_grammar.py` files for testability (no bpy dependency)
- Blender handler functions in `worldbuilding.py` wire grammar output to scene objects
- Seed-based deterministic generation throughout

### Integration Points
- `blender_worldbuilding` action=`generate_settlement` already exists — this phase enhances it
- `asset_pipeline` action=`generate_3d` for Tripo prop generation
- `compose_world_map()` in map_composer.py for full pipeline composition

</code_context>

<specifics>
## Specific Ideas

- Roads should feel like Whiterun/Novigrad — organic medieval winding streets, not grid-based
- Near the Veil, streets should feel desolate and eerie, not cluttered-but-broken
- Props must sit on terrain properly, match surrounding material palette, cast appropriate shadows
- The Tripo pipeline from Phase 35 (texture extraction + delight + validation) ensures props meet quality bar

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 36-world-composer*
*Context gathered: 2026-03-31*
