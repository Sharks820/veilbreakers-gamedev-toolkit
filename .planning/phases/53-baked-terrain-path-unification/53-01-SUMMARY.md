---
phase: 53-baked-terrain-path-unification
plan: 01
subsystem: terrain-pipeline
tags: [baked-terrain, dag-unification, cliff-overlay-removal]
dependency_graph:
  requires: [52-01]
  provides: [baked-terrain-dataclass, compose-terrain-node, dag-mesh-builder]
  affects: [environment.py, terrain_pipeline.py, blender_server.py]
tech_stack:
  added: [terrain_baked.py]
  patterns: [dataclass-contract, dag-to-mesh-builder, bilinear-sampling]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_baked.py
    - Tools/mcp-toolkit/tests/test_baked_terrain.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_pipeline.py
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py
    - Tools/mcp-toolkit/blender_addon/handlers/__init__.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
decisions:
  - BakedTerrain uses bilinear interpolation for world-coordinate sampling
  - Material masks collected from 13 DAG channels (slope, curvature, erosion, biome, etc.)
  - Legacy cliff overlay removed; cliff_overlays_enabled param retained for compat but ignored
  - compose_map LOD dispatch switched from asset_pipeline wrapper to pipeline_generate_lods direct
metrics:
  duration_seconds: 1291
  completed: 2026-04-12T12:06:33Z
  tasks_completed: 5
  tasks_total: 5
  tests_added: 11
  tests_passing: 11
  lines_added: ~470
  lines_removed: ~70
---

# Phase 53 Plan 01: BakedTerrain Dataclass and DAG Unification Summary

BakedTerrain dataclass as single contract between pass DAG and mesh builder, with compose_terrain_node and compose_map wired to consume it via full pipeline execution.

## Tasks Completed

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | BakedTerrain dataclass (TDD) | c47eeff (RED), d003834 (GREEN) | terrain_baked.py: dataclass + sampling + serialization, 11 tests |
| 2 | DAG produces BakedTerrain | fa6d555 | get_baked_terrain() on TerrainPassController |
| 3 | compose_terrain_node consumes BakedTerrain | 842bc13 | New function + _build_mesh_from_baked, no erosion bypass |
| 4 | compose_map uses full DAG | 02b6ccf | env_compose_terrain_node replaces env_generate_terrain, LOD fix |
| 5 | Remove legacy cliff overlay | 1a523f8 | 55 lines of cliff overlay code deleted (F145) |

## Implementation Details

### BakedTerrain Dataclass (terrain_baked.py)
- Fields: height_grid, ridge_map, gradient_x, gradient_z, material_masks, metadata
- `sample_height(x, z)`: bilinear interpolation at world coordinates
- `get_gradient(x, z)`: returns (dh/dx, dh/dz) tuple
- `get_slope(x, z)`: gradient magnitude
- `to_npz(path)` / `from_npz(path)`: compressed serialization with material mask prefix encoding

### TerrainPassController.get_baked_terrain()
- Extracts BakedTerrain from completed mask stack
- Computes gradients via np.gradient if not on stack
- Collects 13 material-relevant channels into material_masks dict
- Populates metadata from pipeline state (seed, tile coords, cell_size, height range)

### compose_terrain_node
- Initializes mask stack, intent, scene_read
- Runs full pass pipeline (macro_world -> structural_masks -> erosion -> validation)
- Calls get_baked_terrain() then _build_mesh_from_baked()
- Registered as env_compose_terrain_node handler

### compose_map Changes
- Step 2 now calls env_compose_terrain_node instead of env_generate_terrain
- No erosion="none" bypass
- Step 13 LOD dispatch uses pipeline_generate_lods directly (R7 P0 fix)

### Legacy Cliff Overlay Removal
- Deleted 55 lines from _create_terrain_mesh_from_heightmap
- cliff_overlays_enabled parameter retained but always returns 0
- All cliffs now exclusively via pass_cliffs pipeline pass

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All functions are fully implemented.

## Self-Check: PASSED
