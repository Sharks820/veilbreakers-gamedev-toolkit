---
phase: 18-procedural-mesh-integration-terrain-depth
plan: 02
subsystem: blender-terrain-depth
tags: [terrain, procedural-mesh, pure-logic, cliff, cave, waterfall, bridge, biome]
dependency_graph:
  requires: [procedural_meshes.py (_make_result, _merge_meshes, generate_bridge_mesh)]
  provides: [_terrain_depth.py (5 terrain depth generators)]
  affects: [blender_environment (future terrain composition)]
tech_stack:
  added: []
  patterns: [MeshSpec pure-logic generators, seed-deterministic geometry, _merge_meshes composition]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py
    - Tools/mcp-toolkit/tests/test_terrain_depth.py
  modified: []
decisions:
  - "Cliff face uses noise-displaced partial cylinder (not heightmap projection)"
  - "Bridge generator wraps existing generate_bridge_mesh with world-space transform"
  - "Cave entrance uses ring-based profile extrusion for tunnel depth"
  - "Biome transition stores blend weights in metadata vertex_groups list"
metrics:
  duration: ~5 minutes
  completed: 2026-03-21
  tasks_completed: 1
  tasks_total: 1
  tests_added: 47
  tests_passing: 47
  files_created: 2
  files_modified: 0
---

# Phase 18 Plan 02: Terrain Depth Generators Summary

5 pure-logic terrain depth generators producing vertical/3D geometry (cliffs, caves, waterfalls, biome blends, bridges) with zero bpy imports and 47 passing tests.

## What Was Built

### _terrain_depth.py (5 generators, ~310 lines)

| Generator | Purpose | Key Parameters | Geometry |
|-----------|---------|----------------|----------|
| `generate_cliff_face_mesh` | Vertical rock wall | width, height, noise_amplitude, seed, style | Curved grid surface (partial cylinder + Gaussian noise) |
| `generate_cave_entrance_mesh` | Archway + tunnel | width, height, depth, terrain_edge_height, seed | Ring-profile extrusion (semicircle arch + rectangular sides) |
| `generate_biome_transition_mesh` | Blend zone strip | biome_a, biome_b, zone_width, zone_depth, seed | Subdivided ground plane with height noise + blend weights |
| `generate_waterfall_mesh` | Stepped cascade | width, height, steps, pool_radius, seed | Horizontal ledges + vertical curtains + circular pool disk |
| `generate_terrain_bridge_mesh` | World-space bridge | start_pos, end_pos, width, style, seed | Wraps generate_bridge_mesh with yaw rotation + translation |

### test_terrain_depth.py (47 tests)

- **TestCliffFaceMesh** (8 tests): MeshSpec validity, width/height span, vertical geometry (y > 10m), seed determinism, metadata category, custom dimensions, style metadata
- **TestCaveEntranceMesh** (6 tests): MeshSpec validity, opening dimensions, terrain_edge_height shifting, depth parameter, seed determinism, metadata
- **TestBiomeTransitionMesh** (7 tests): MeshSpec validity, biome parameter acceptance, zone_width/zone_depth matching, biome metadata, vertex_groups blend weights
- **TestWaterfallMesh** (7 tests): MeshSpec validity, height matching, cascade step count, pool existence, seed determinism, custom step count, metadata
- **TestTerrainBridgeMesh** (9 tests): MeshSpec validity, start/end positions, span distance, 3 style variants, rotated endpoints, elevated endpoints, metadata
- **TestAllGenerators** (10 parametrized tests): Face index validity and category across all 5 generators

## Architecture Decisions

1. **Cliff face**: Partial cylinder with Gaussian noise per-vertex creates natural rock look without heightmap dependency. Base curve uses `sin(x_frac * pi)` for concavity.

2. **Cave entrance**: Ring-profile extrusion technique -- build arch profile (semicircle + sides) at multiple Z-depth slices, connect rings with quad faces. Supports "natural" style with random displacement.

3. **Biome transition**: Ground plane with per-vertex blend weights stored in metadata `vertex_groups` list (0.0 = biome_a, 1.0 = biome_b across width). Material system can use these for shader blending.

4. **Waterfall**: Composition of horizontal ledge grids + vertical curtain strips + circular pool disk, all merged via `_merge_meshes`. Each step has independent noise for non-uniform water surface.

5. **Bridge wrapper**: Reuses existing `generate_bridge_mesh` (all 3 styles: stone_arch, rope, drawbridge) with yaw rotation and midpoint translation to place between arbitrary world positions.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- all generators produce complete geometry with full metadata.

## Verification

```
47 passed in 0.77s
```

All face indices valid across all generators. All metadata categories are "terrain_depth". Seed determinism confirmed.

## Self-Check: PASSED

- FOUND: Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py
- FOUND: Tools/mcp-toolkit/tests/test_terrain_depth.py
- FOUND: .planning/phases/18-procedural-mesh-integration-terrain-depth/18-02-SUMMARY.md
- FOUND: bef6117 (RED test commit)
- FOUND: f70932f (GREEN implementation commit)
