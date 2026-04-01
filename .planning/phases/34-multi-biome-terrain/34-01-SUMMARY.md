---
phase: 34
plan: 01
subsystem: terrain
tags: [biome, voronoi, corruption, vegetation, world-generation, terrain]
requirements: [MESH-05, MESH-09, MESH-10]
dependency_graph:
  requires: [phase-31-terrain, phase-32-buildings]
  provides: [multi-biome-world-generation, biome-grammar, corruption-tinting, foundation-flatten]
  affects: [blender_environment-MCP-tool, environment.py-handler]
tech_stack:
  added: [_biome_grammar.py, test_biome_grammar.py]
  patterns: [WorldMapSpec-dataclass, Voronoi-composition, fBm-corruption-noise, biome-alias-table]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_biome_grammar.py
    - Tools/mcp-toolkit/tests/test_biome_grammar.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
decisions:
  - "biome aliases resolve volcanic_wastes->desert, frozen_tundra->mountain_pass to avoid palette changes"
  - "corruption_level=0.0 fast-path returns all-zeros numpy array without noise generation"
  - "vertex colors written via color_attributes API (Blender 3.2+), not legacy vertex_colors"
  - "vegetation scatter is best-effort per-biome: exceptions silently skipped (biome may have no set)"
  - "primary biome material assigned by sampling biome_ids at terrain center cell"
metrics:
  duration_minutes: 8
  completed_date: "2026-04-01"
  tasks_completed: 4
  tasks_total: 4
  files_created: 2
  files_modified: 2
  tests_added: 46
  lines_added: ~640
---

# Phase 34 Plan 01: Multi-biome Terrain Summary

**One-liner:** Voronoi world map composer with fBm corruption tinting, biome alias table, and foundation flatten zones wired to MCP action `blender_environment generate_multi_biome_world`.

## What Was Built

### Task 1+2: `_biome_grammar.py` + `test_biome_grammar.py`

Pure-logic composition layer (no bpy). `WorldMapSpec` dataclass carries all fields needed to drive the Blender handler: `biome_ids` (int32 height×width), `biome_weights` (float64 height×width×N), `corruption_map` (float64), `flatten_zones` (list of normalized-coord dicts), `cell_params` (temperature/moisture/elevation per biome).

`generate_world_map_spec()` composes:
- `voronoi_biome_distribution()` from `_terrain_noise.py` for biome cell layout
- `_generate_corruption_map()` (fBm, 4 octaves, seed offset +7919 to decouple from biome pattern)
- Biome alias resolution (volcanic_wastes → desert, frozen_tundra → mountain_pass, etc.)
- Building plot → normalized flatten zone conversion with 20% radius padding

`BIOME_CLIMATE_PARAMS` table covers 14 biomes with temperature/moisture/elevation (req SC-1).

46 tests cover: WorldMapSpec invariants, corruption range/determinism, transition blend cells, flatten zone normalization, alias resolution, cell_params keys and values, integration smoke test.

### Task 3: `handle_generate_multi_biome_world()` in `environment.py`

Blender handler that orchestrates:
1. `generate_world_map_spec()` (pure logic)
2. `handle_generate_terrain()` with merged heightmap + erosion + flatten_zones
3. `_compute_vertex_colors_for_biome_map()` — samples biome palette base color per vertex, applies `apply_corruption_tint()`, writes to `mesh.color_attributes["BiomeColor"]`
4. `handle_create_biome_terrain()` for dominant center biome material
5. `handle_scatter_biome_vegetation()` per biome (best-effort, silently skips missing sets)

Returns: `biome_names`, `corruption_zones` (cells > 30%), `vegetation_count`, `flatten_zones_applied`, `vertex_count`, `world_size_m`.

### Task 4: MCP action in `blender_server.py`

Added `"generate_multi_biome_world"` to `blender_environment` Literal. New parameters: `biome_count`, `biomes`, `world_size`, `corruption_level`, `building_plots`, `scatter_vegetation`, `min_veg_distance`, `max_veg_instances`, `transition_width_m`. Dispatches to `env_generate_multi_biome_world`. `next_steps` summarizes biomes, vegetation, corruption zones, and next pipeline steps.

## Success Criteria Status

- [x] Biome grammar module with Voronoi zoning for 6+ biome types (`_biome_grammar.py`)
- [x] Corruption-aware tinting integrated (`apply_corruption_tint` via `_compute_vertex_colors_for_biome_map`)
- [x] Building foundation terrain conforming (`flatten_zones` in WorldMapSpec, passed to `handle_generate_terrain`)
- [x] Smooth biome transitions (Voronoi softmax blend weights, configurable `transition_width_m`)
- [x] All 46 new tests passing (plus 393 terrain regression tests green)
- [x] SUMMARY.md created

## Commits

| Hash | Message |
|------|---------|
| `3b9859f` | feat(34-01): add _biome_grammar.py with WorldMapSpec and generate_world_map_spec |
| `79516c5` | feat(34-01): add handle_generate_multi_biome_world Blender handler in environment.py |
| `7edaeec` | feat(34-01): wire generate_multi_biome_world MCP action in blender_server.py |

## Deviations from Plan

None — plan executed exactly as written.

The one pre-existing test failure (`test_building_quality_wiring.py::TestDetailWiring::test_medieval_details_not_uniform_cubes`) was present before Phase 34 work began (verified via git stash). Out of scope for this plan.

## Known Stubs

None. All data paths are wired: `generate_world_map_spec` → `handle_generate_multi_biome_world` → MCP action. Vegetation scatter and biome material assignment are best-effort (exceptions silently caught) but not stubs — they call real sub-handlers that may return empty results for biomes without defined vegetation sets.

## Self-Check: PASSED

Files created:
- `Tools/mcp-toolkit/blender_addon/handlers/_biome_grammar.py` — FOUND
- `Tools/mcp-toolkit/tests/test_biome_grammar.py` — FOUND

Commits: `3b9859f`, `79516c5`, `7edaeec` — all present in git log.

Tests: 46 new pass, 393 terrain/materials regression pass (487 total for biome+terrain suite).
