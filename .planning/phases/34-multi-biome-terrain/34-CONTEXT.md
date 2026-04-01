# Phase 34: Multi-biome Terrain -- Context

**Auto-generated:** 2026-03-31
**Status:** Ready for planning

## Phase Goal

Biome system distributes distinct terrain types across the world map using Voronoi-based zoning with corruption-aware tinting, smooth biome transitions, and terrain-conforming building foundations -- no floating buildings or sharp biome boundaries.

## Requirements

- **MESH-05**: Terrain-building integration with foundation meshes, terrain flatten/cutout zones, and material blending at contact edges. Zero visible gaps in side-view verification.
- **MESH-09**: Voronoi-based biome distribution with 5+ biome types, corruption-aware tinting (0-100%), smooth 10-20m blend zones between biomes. Uses existing 14 biome palettes.
- **MESH-10**: Vegetation uses L-system branching for trees (not sphere clusters), 3+ species with leaf card geometry, billboard LOD fallback. Poisson disk scatter (Bridson's algorithm) for natural distribution.

## Existing Code (Pure Logic, No bpy)

### Voronoi Distribution
- `_terrain_noise.py`: `voronoi_biome_distribution(width, height, biome_count, transition_width, seed, biome_names)` -- returns `(biome_ids, biome_weights)`. Uses jittered grid seeding + domain warping for organic boundaries. **4 tests passing.**

### Biome Palettes and Materials
- `terrain_materials.py`:
  - `BIOME_PALETTES` -- 14 named biomes (thornwood_forest, corrupted_swamp, mountain_pass, ruined_fortress, abandoned_village, veil_crack_zone, cemetery, battlefield, desert, coastal, grasslands, mushroom_forest, crystal_cavern, deep_forest)
  - `BIOME_PALETTES_V2` -- full per-layer material definitions (subset of V1, exact keys need audit)
  - `apply_corruption_tint(vertex_colors, corruption_level)` -- lerps toward purple/black, pushes A toward 1.0
  - `compute_biome_transition(vertices, face_normals, faces, biome_a, biome_b, transition_width, ...)` -- per-vertex splatmap weights with noise-based boundary jitter
  - `auto_assign_terrain_layers(vertices, face_normals, faces, biome_name)` -- slope/height rules to RGBA weights
  - `handle_setup_terrain_biome(params)` -- Blender handler
  - `handle_create_biome_terrain(params)` -- Blender handler

### Terrain Flattening (Building Foundations)
- `terrain_advanced.py`:
  - `flatten_terrain_zone(heightmap, center_x, center_y, radius, target_height, blend_width, seed)` -- smoothstep circular flatten. Normalized coordinates.
  - `flatten_multiple_zones(heightmap, zones)` -- iterates over list of zone dicts
  - `handle_snap_to_terrain(params)` -- raycast snap for object placement

### Vegetation
- `vegetation_system.py`: `handle_scatter_biome_vegetation(params)` -- combines `BIOME_VEGETATION_SETS`, Poisson disk sampling, slope/height filtering. Requires terrain mesh in Blender scene.
- `vegetation_lsystem.py`: `LSYSTEM_GRAMMARS` with oak, pine, birch, willow, corrupted_tree, thornwood, fern, mushroom_tree. Leaf card geometry. Billboard impostor LOD.
- `_scatter_engine.py`: `poisson_disk_sample()` -- Bridson's algorithm.

### Building Foundations (Height Calculation)
- `settlement_generator.py`:
  - `_compute_foundation_height(heightmap, building_x, building_y, footprint_w, footprint_d)` -- finds min/max height under footprint
  - `_compute_foundation_profile(heightmap, building_x, building_y, footprint_w, footprint_d, world_size)` -- returns `{foundation_height, platform_elevation, foundation_profile}`

### Existing Terrain Handler
- `environment.py`:
  - `handle_generate_terrain(params)` -- creates heightmap, applies erosion, applies flatten_zones (MESH-05 wired), cliff overlays
  - `VB_BIOME_PRESETS` -- per-biome terrain type, resolution, height_scale, scatter_rules

## What Does NOT Exist (Must Write)

1. **`_biome_grammar.py`** (new pure-logic file, ~350 lines):
   - `WorldMapSpec` dataclass: biome_ids, biome_weights, biome_names, corruption_map, flatten_zones, cell_params
   - `generate_world_map_spec(width, height, biome_count, biomes, seed, corruption_level, building_plots, world_size)` -- calls `voronoi_biome_distribution()` + generates corruption noise + builds flatten_zones from building_plots
   - Biome name validation and alias mapping (volcanic_wastes -> desert, frozen_tundra -> mountain_pass for palettes)
   - Temperature/moisture/elevation parameter tables per biome for success criterion SC-1

2. **`handle_generate_multi_biome_world(params)`** in `environment.py` (~200 lines):
   - Calls `generate_world_map_spec()` from `_biome_grammar.py`
   - Calls `handle_generate_terrain()` for the base mesh
   - Calls `handle_create_biome_terrain()` per biome zone
   - Calls `flatten_multiple_zones()` for building plots
   - Calls `handle_scatter_biome_vegetation()` per biome
   - Writes corruption tint as vertex color attribute
   - Returns full result dict with biome_count, corruption_zones, vegetation_count, etc.

3. **`generate_multi_biome_world` MCP action** in `blender_server.py`:
   - Added to `blender_environment` Literal action list
   - Parameters: `biomes`, `world_size`, `biome_count`, `corruption_level`, `building_plots`
   - Dispatches to `env_generate_multi_biome_world` Blender command

4. **`tests/test_biome_grammar.py`** (~150 lines):
   - TestWorldMapSpec: biome_names length, biome_ids unique count, corruption_map range
   - TestTransitionWidth: blend zone covers 10-20m at default settings
   - TestFoundationPlacements: flatten_zones coords normalized, count matches building_plots
   - TestVegetationSpec: vegetation spec includes 3+ species

## Success Criteria

1. Voronoi biome distribution creates 5+ distinct biome regions from 14 existing palettes, with temperature/moisture/elevation parameters per cell.
2. Biome transition zones span 10-20m with material blending (splatmap alpha gradient), vegetation density fade, prop palette interpolation -- no hard edges in overhead contact sheet.
3. Corruption system tints affected biome regions (purple/black overlay 0-100%), affects vegetation (dead/twisted variants), modulates material properties.
4. Building foundations generate terrain-conforming meshes flattening terrain in a radius around the building footprint, with material blending at contact edge -- zero visible gaps in side-view contact sheet.
5. Multi-biome terrain renders as a single coherent world map (512m x 512m minimum) with 3+ biome types visible, terrain height variation >50m, at least one river/road cutting across biome boundaries.
