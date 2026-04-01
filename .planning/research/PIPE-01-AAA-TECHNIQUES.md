# PIPE-01: AAA Procedural Techniques Research

**Date:** 2026-03-31
**Scope:** VeilBreakers procedural pipeline -- 7 core techniques for AAA-quality world generation
**Audience:** Pipeline engineers working on v7.0 world composer phases

---

## 1. CGA Split Grammars -- Building Facade Generation

### What It Is

CGA (Computer Generated Architecture) split grammars decompose a building mass model into progressively smaller pieces using split, repeat, and component operations. Each rule subdivides a shape (usually a box) along an axis into sub-shapes, which are then refined by further rules. The result is architecturally plausible facades with plinths, stringcourses, cornices, pilasters, window surrounds, sills, and lintels -- all derived from a small rule set and per-style parameters.

### AAA Game Reference

**Spider-Man (2018, Insomniac)** uses CGA-based procedural buildings to generate thousands of Manhattan facades. Each building is split into floors, each floor into bays, and each bay receives a window/door terminal shape. Style parameters vary by neighborhood (Midtown glass towers vs. Harlem brownstones). The system produces convincing urban architecture at scale without manual authoring of each building. **Assassin's Creed Unity (Ubisoft)** similarly used procedural facades for revolutionary Paris.

### Current Implementation Status: **IMPLEMENTED**

The file `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` contains a complete facade grammar system:

- `FACADE_STYLE_RULES` (line 129): Per-style facade parameters (plinth, stringcourse, cornice, bay divisor, pilaster, opening frame dimensions, and boolean flags for balcony/awning/shutters/buttress).
- `plan_modular_facade()` (line 244): Core split-grammar engine. Generates plinth bands, inter-floor stringcourses, top cornice, corner pilasters/quoins, rhythm pilasters at bay guide positions, opening surrounds with sills and lintels, buttresses (gothic/fortress), awnings (market/waterfront), balconies, and chimneys.
- `evaluate_building_grammar()` (line 564): Full building shell generator applying foundation, walls, floor slabs, roof, windows, doors, and style-specific details as a `BuildingSpec` operation list.
- 5 architectural styles: `medieval`, `gothic`, `rustic`, `fortress`, `organic`.

### VeilBreakers Adaptation Notes

The current system already matches VeilBreakers' dark fantasy setting well. The `organic` style with cob walls and living thatch covers corrupted/nature-reclaimed areas. Potential improvements for v7.0:

- **Site-responsive rules**: The `site_profile` parameter exists but only affects awnings. Expand to influence window density (narrow alleys vs. open squares), facade ornament density, and ground-floor shopfront generation.
- **Conditional terminal shapes**: Add `has_shutter` variants with open/closed states, `has_flower_box` for pastoral villages, and corruption-specific terminals (bricked-up windows, boarded doors).
- **Non-rectangular footprints**: Current grammar assumes rectangular buildings. L-shaped, T-shaped, and courtyard buildings would need multi-mass splitting.

---

## 2. Wave Function Collapse (WFC) -- Tile-Based Layout Generation

### What It Is

Wave Function Collapse is a constraint-solving algorithm inspired by quantum mechanics. Given a set of tiles with adjacency constraints (which tile can neighbor which), WFC initializes a grid in "superposition" (all tiles possible everywhere) then iteratively collapses cells to a single tile, propagating constraints to neighbors. The result is a locally consistent global pattern. WFC excels at generating dungeons, city blocks, and organic patterns from small example sets.

### AAA Game Reference

**Caves of Qud** and **Crown Trick** use WFC for dungeon generation. **Townscaper** by Oskar Stalberg uses a WFC variant to generate cohesive, colorful island towns from a single tileset. In the AAA space, **Bad North** uses WFC for island terrain generation, and the technique has been adopted by multiple procedural tools (Tiled WFC plugin, WaveFunctionCollapse Unity asset).

### Current Implementation Status: **PARTIAL**

WFC is referenced in MCP tool definitions but no core algorithm exists in the Blender handlers:

- `blender_worldbuilding` tool has a `generate_wfc_dungeon` action declared in the MCP schema.
- `unity_world` tool has a `create_wfc_dungeon` action that generates a Unity C# WFC dungeon script.
- Neither the Blender addon handlers nor a dedicated `_wfc_solver.py` contain a WFC constraint solver implementation. The Unity side generates a script template but the actual WFC algorithm would run at Unity runtime, not in the pipeline.

### VeilBreakers Adaptation Notes

A dedicated WFC solver (`_wfc_solver.py`) should be implemented in the handlers directory for v7.0. Recommended approach:

- **Overlapping WFC** for terrain texture synthesis and biome boundary blending (train from a 16x16 sample bitmap).
- **Simple tiled WFC** for dungeon room layout (define room tiles with N/S/E/W connection constraints).
- **Integration point**: The `map_composer.py` handler should accept WFC-generated layouts as input for settlement block generation and dungeon floor plans.
- **Tile catalog**: Create a dungeon tile catalog compatible with the existing `MODULAR_CATALOG` in `_building_grammar.py` (line 3314) so WFC outputs snap to the modular kit system.

---

## 3. L-Systems -- Road Networks and Vegetation

### What It Is

Lindenmayer systems (L-systems) are parallel rewriting systems that generate complex structures from simple rules. A string axiom is iteratively expanded using production rules, then interpreted as geometric operations by a turtle graphics interpreter. Stochastic L-systems add randomness, parametric L-systems add conditions, and context-sensitive L-systems add neighbor awareness. They produce natural-looking branching structures ideal for trees, rivers, and road networks.

### AAA Game Reference

**No Man's Sky (Hello Games)** uses L-systems extensively for alien flora generation, producing billions of unique plant species. **The Witcher 3 (CD Projekt Red)** used L-systems for tree generation in their SpeedTree-integrated vegetation pipeline. **Cities: Skylines** uses L-system-inspired algorithms for road network growth, where roads branch from a center following growth rules that respond to terrain and existing infrastructure.

### Current Implementation Status: **IMPLEMENTED (vegetation), PARTIAL (roads)**

**Vegetation -- IMPLEMENTED:**
`Tools/mcp-toolkit/blender_addon/handlers/vegetation_lsystem.py` contains a complete L-system tree generator:

- `LSYSTEM_GRAMMARS` (line 34): Grammar definitions for 8+ tree types (oak, pine, birch, willow, dead, dark_oak, thorn, elder) with axiom, production rules, branch angles, ratios, gravity, and randomness parameters.
- `expand_lsystem()` (line 126): String expansion engine applying production rules for N iterations.
- `interpret_lsystem()` (line 246): Turtle graphics interpreter converting L-system strings into `BranchSegment` objects with position, direction, radius, and depth.
- Includes leaf card placement, wind vertex color baking, billboard impostor generation, and GPU instancing export.

**Road Networks -- PARTIAL:**
`Tools/mcp-toolkit/blender_addon/handlers/road_network.py` uses MST (Minimum Spanning Tree) with Kruskal's algorithm for connectivity, not L-system growth:

- Roads are computed between pre-placed waypoints rather than grown organically.
- The system handles road widths, intersections, bridge placement, and switchbacks.
- Missing: organic road growth from a seed point with branching rules influenced by terrain slope and settlement proximity.

### VeilBreakers Adaptation Notes

- The vegetation L-system is production-ready and well-suited to dark fantasy. Consider adding corrupted tree variants (twisted angles, no leaves, thorn-heavy rules).
- Road networks should stay with MST for the planning phase (it guarantees connectivity) but could layer an L-system growth pass for secondary paths, alleys, and trails that branch organically from main roads.
- The dead tree grammar already provides a good foundation for corrupted vegetation.

---

## 4. Hydraulic Erosion -- Terrain Realism

### What It Is

Hydraulic erosion simulates the effect of water on terrain over geological time. Droplet-based methods spawn rain drops that flow downhill following the terrain gradient, picking up sediment from steep slopes (erosion) and depositing it in flat areas or when the droplet slows (deposition). This produces realistic valley carving, ridge sharpening, sediment fans, and river-like channels. Thermal erosion simulates material sliding when slope exceeds a talus angle. Combined, these produce terrain that reads as geologically plausible rather than obviously noise-generated.

### AAA Game Reference

**Ghost Recon Wildlands (Ubisoft)** used erosion simulation on procedurally generated terrain for their open-world Bolivia. **Horizon Zero Dawn (Guerrilla Games)** applied erosion passes to hand-sculpted terrain to add geological realism. **Minecraft** terrain generation uses a simplified erosion pass. The technique is standard in AAA terrain pipelines -- any open-world game with realistic terrain uses some form of erosion post-processing on heightmaps.

### Current Implementation Status: **IMPLEMENTED**

`Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py` contains a complete erosion system:

- `apply_hydraulic_erosion()` (line 23): Droplet-based hydraulic erosion with configurable iterations, inertia, sediment capacity, deposition rate, erosion rate, evaporation, min slope, brush radius, and max droplet lifetime. Uses bilinear interpolation for gradient computation and applies erosion/deposition within a configurable brush radius.
- `apply_thermal_erosion()`: Talus-angle thermal weathering that slides material downhill when slope exceeds threshold.
- Both functions are pure-logic (numpy arrays in, numpy arrays out), fully testable without Blender.
- Integrated into the terrain pipeline via `terrain_advanced.py` and `environment.py` handlers.

### VeilBreakers Adaptation Notes

The erosion system is production-ready. Key considerations for v7.0:

- **Performance**: For large world maps (1024x1024+), the Python droplet simulation is the bottleneck. Consider a numpy-vectorized erosion approximation or a C extension for maps larger than 512x512.
- **River carving**: The `_terrain_noise.py` file has `carve_river_path()` using A* pathfinding. Post-erosion river reinforcement (deepening the A* channel with a erosive pass) would produce more convincing watercourses.
- **Corrupted terrain**: Add a "corrosive erosion" variant that produces jagged, non-natural erosion patterns -- steeper than hydraulic, less uniform than thermal.

---

## 5. Poisson Disk Sampling -- Prop/Vegetation Scatter

### What It Is

Poisson disk sampling generates random points with a guaranteed minimum distance between any two points (blue-noise distribution). Bridson's algorithm achieves this efficiently by maintaining an active list and testing candidate points against neighbors in a spatial grid. The result is natural-looking scatter patterns without clumping or obvious regularity. This is the standard technique for placing props, vegetation, rocks, and other scattered elements in game environments.

### AAA Game Reference

**Every AAA open-world game** uses Poisson disk sampling or a variant for vegetation and prop scatter. **The Elder Scrolls V: Skyrim** uses distance-constrained scatter for its flora placement. **The Witcher 3** layers multiple Poisson passes at different densities for grass, bushes, and trees. **Assassin's Creed Valhalla** uses density-mapped Poisson scatter where the minimum distance varies by biome, slope, and altitude. The technique is so fundamental it is built into Unity's terrain detail system and Unreal's foliage editor.

### Current Implementation Status: **IMPLEMENTED**

Two independent Poisson disk implementations exist:

1. **`_building_grammar.py` `_poisson_disk_scatter_2d()`** (line 2821): Bridson's algorithm for interior clutter placement. Used by `generate_clutter_layout()` to scatter 5-15 decorative props per room on furniture surfaces and floor areas with configurable density.

2. **`_scatter_engine.py` `poisson_disk_sample()`** (line 26): Full Bridson's algorithm for environment scatter. Supports configurable minimum distance, seed, max points, and area size. Integrated with `context_scatter()` (line 305) which combines Poisson sampling with biome filtering and slope constraints.

Additionally, `environment_scatter.py` and `vegetation_system.py` consume the scatter engine output for Blender object creation.

### VeilBreakers Adaptation Notes

Both implementations are functional but duplicated. For v7.0:

- **Consolidate**: The `_scatter_engine.py` version is more general-purpose and should be the single source. The `_building_grammar.py` version can import from it.
- **Variable-density Poisson**: Upgrade to support a density map (numpy array) where minimum distance varies spatially. This enables dense vegetation near water, sparse on ridges.
- **Multi-class scatter**: Generate points for multiple object types simultaneously with inter-type distance constraints (e.g., trees must be 3m from rocks, but rocks can be 1m from each other).

---

## 6. Straight Skeleton Roofs -- Roof Geometry from Building Footprints

### What It Is

The straight skeleton of a polygon is computed by shrinking the polygon inward (parallel offset) and tracing the edges as they meet, forming a roof-like ridge structure. For a rectangular footprint, this produces a gabled roof. For an L-shaped footprint, it produces a hip roof with a valley. For any convex or concave polygon, the straight skeleton generates the mathematically correct roof geometry with proper drainage slopes. It is the standard computational geometry approach for automatic roof generation from floor plans.

### AAA Game Reference

**Cities: Skylines** uses straight skeleton algorithms for procedural roof generation on player-placed buildings. **CityEngine (Esri)**, used in AAA game prototyping and film previz, implements straight skeleton roofs as its primary roof generation method. **Assassin's Creed Unity** used a similar approach for the rooftops of Paris, which were critical for gameplay (parkour). The technique is essential for any game where buildings are generated from footprints rather than hand-authored.

### Current Implementation Status: **PARTIAL**

`Tools/mcp-toolkit/blender_addon/handlers/building_quality.py` contains `generate_roof()` (line 1140) which produces detailed roofs with individual tiles/shingles for 6 styles (gable, hip, gambrel, mansard, shed, conical_tower). However, this is not a straight skeleton algorithm:

- Roofs are generated for **rectangular footprints only** with parametric pitch and style.
- The building grammar (`_building_grammar.py`) also generates roofs via simple pitch calculations for rectangular shapes (gabled, pointed, flat, domed).
- No straight skeleton solver exists for arbitrary convex/concave polygon footprints.
- The `worldbuilding.py` handler calls `generate_roof()` but only for rectangular building specs.

### VeilBreakers Adaptation Notes

For v7.0, a straight skeleton solver should be implemented for the world composer:

- **Algorithm**: Use the Eppstein-Erickson O(n log n) algorithm or the simpler Aichholzer-Aurenhammer 1995 incremental method. For typical building footprints (4-12 vertices), even an O(n^2 log n) approach is fast enough.
- **Integration**: Accept building footprint polygons from the settlement generator, compute straight skeleton, and generate roof mesh with tile/shingle detail from `building_quality.py`.
- **Roof variety**: Use the skeleton ridgeline to determine natural hip/gable transitions rather than forcing a single style. Gothic buildings get steeper pitches, medieval buildings get shallower.
- **Corruption**: Damaged roofs can be generated by selectively removing skeleton faces (similar to the existing `apply_ruins_damage()` approach in `_building_grammar.py`).

---

## 7. Domain Warping -- Noise-on-Noise for Organic Biome Boundaries

### What It Is

Domain warping feeds the output of one noise function into the input coordinates of another, creating organic, distorted patterns. Instead of sampling noise at (x, y), you sample at (x + noise_a(x,y), y + noise_b(x,y)). The result is that regular noise patterns are twisted and stretched into forms that resemble cloud formations, marble veins, or natural biome boundaries. Multiple warping layers (warp the warp) produce increasingly organic results. Inigo Quilez popularized the technique with his domain warping article.

### AAA Game Reference

**No Man's Sky** uses domain warping for the organic variation in terrain features and biome blending. **Spore (Maxis)** used domain-warped noise for continent shapes and biome boundaries. **Valheim** applies domain warping to create its distinctive biome transition zones that feel natural rather than hard-edged. The technique is ubiquitous in terrain generation wherever smooth biome blending is needed.

### Current Implementation Status: **IMPLEMENTED**

`Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` contains a complete domain warping implementation:

- `domain_warp()` (line ~1144): Distorts 2D coordinates using noise-based domain warping with configurable `warp_strength` and `warp_scale` parameters.
- `generate_heightmap()` (line ~310): Accepts `warp_strength` and `warp_scale` parameters. When `warp_strength > 0`, applies domain warping to the coordinate array before fBm noise evaluation, producing organic terrain features.
- The function is numpy-vectorized for performance.
- Integrated into the full terrain pipeline via `environment.py` and `map_composer.py`.

### VeilBreakers Adaptation Notes

The domain warping system is production-ready. For v7.0 world composer:

- **Biome boundaries**: Use domain warping on the biome assignment map (not just the heightmap) to create organic biome transition zones. A warped Voronoi diagram would produce natural-looking biome patches.
- **Multi-layer warp**: For world maps, apply two levels of warping -- a large-scale warp for continent/region shapes and a fine-scale warp for local biome edges.
- **Corrupted zones**: Apply asymmetric domain warping (different strength in X vs Y) to create the jagged, unnatural boundaries of corruption zones. Combine with a noise function that has higher frequency near corruption sources.

---

## Summary Table

| # | Technique | Status | Primary File | Key Function |
|---|-----------|--------|-------------|-------------|
| 1 | CGA Split Grammars | **IMPLEMENTED** | `_building_grammar.py` | `plan_modular_facade()` |
| 2 | Wave Function Collapse | **PARTIAL** | MCP schema only (no solver) | `generate_wfc_dungeon` (declared) |
| 3 | L-Systems (vegetation) | **IMPLEMENTED** | `vegetation_lsystem.py` | `expand_lsystem()`, `interpret_lsystem()` |
| 3 | L-Systems (roads) | **PARTIAL** | `road_network.py` | MST only, no L-system growth |
| 4 | Hydraulic Erosion | **IMPLEMENTED** | `_terrain_erosion.py` | `apply_hydraulic_erosion()` |
| 5 | Poisson Disk Sampling | **IMPLEMENTED** | `_scatter_engine.py`, `_building_grammar.py` | `poisson_disk_sample()` (both) |
| 6 | Straight Skeleton Roofs | **PARTIAL** | `building_quality.py` | `generate_roof()` (rectangular only) |
| 7 | Domain Warping | **IMPLEMENTED** | `_terrain_noise.py` | `domain_warp()` |

**Overall**: 4 of 7 techniques are fully implemented. WFC needs a new solver module. Road L-systems need a growth algorithm layered on the existing MST planner. Straight skeleton roofs need a computational geometry solver for arbitrary polygon footprints.

---

## Recommended Implementation Priority for v7.0

1. **Straight Skeleton Roofs** -- High visual impact, required for non-rectangular settlement buildings.
2. **WFC Solver** -- Enables constraint-based dungeon and settlement layout generation.
3. **L-System Road Growth** -- Secondary path branching for organic settlement layouts.
4. **Variable-density Poisson** -- Enhances scatter quality with density maps.
5. **Site-responsive CGA** -- Expands existing facade grammar with context awareness.
6. **Biome Domain Warping** -- Apply existing warping to biome maps.
7. **Corrupted Terrain Erosion** -- Specialized erosion variant for corruption zones.
