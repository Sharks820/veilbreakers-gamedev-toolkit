---
phase: "55"
plan: "02"
subsystem: "terrain-water"
tags: [river, lake, waterfall, A-star, meander, mesh-generation, volumetric]
dependency_graph:
  requires: [_terrain_noise.py A* pathfinding]
  provides: [prefer_downhill A* mode, add_meander, generate_river_mesh, generate_lake_mesh, generate_waterfall_volumetric_mesh]
  affects: [carve_river_path, terrain_water_variants, terrain_waterfalls]
tech_stack:
  added: []
  patterns: [asymmetric A* cost, multi-harmonic sinusoidal meander, quad-strip river mesh, radial-disc lake mesh, tapered-prism volumetric waterfall]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_rivers_astar_meander.py
    - Tools/mcp-toolkit/tests/test_water_mesh_integration.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py
decisions:
  - "Asymmetric A* cost: downhill 0.1x, uphill 10x slope_weight (root cause fix for straight rivers)"
  - "Multi-harmonic meander: 3 sine waves at 1x/0.5x/2x wavelength with quadratic taper"
  - "Waterfall volumetric mesh uses back+front cross-sections with sinusoidal front curvature"
metrics:
  duration_seconds: 507
  completed: "2026-04-12T12:58:26Z"
  tasks_completed: 3
  tests_added: 43
  files_modified: 1
  files_created: 2
---

# Phase 55 Plan 02: Rivers/Water/Waterfalls Mesh and A* Fix Summary

Asymmetric A* river cost function (prefer_downhill), meander perturbation, river/lake/waterfall mesh generators with 43 tests.

## Tasks Completed

### Task 1: Fix A* Cost + Mesh Generators (cd1f1fc)

**ROOT CAUSE FIX**: The A* pathfinder used `abs(h_diff) * slope_weight` which penalized downhill movement equally to uphill. Rivers should strongly prefer downhill flow.

**Fix**: Added `prefer_downhill` parameter to `_astar()`:
- Downhill steps: slope cost = `abs(h_diff) * slope_weight * 0.1` (very cheap)
- Uphill steps: slope cost = `h_diff * slope_weight * 10.0` (very expensive)
- Valley preference: `h_next * height_weight * 0.5`
- Legacy mode (roads) untouched via `prefer_downhill=False` default

**New functions added to `_terrain_noise.py`:**
- `add_meander()`: Multi-harmonic sinusoidal lateral perturbation (3 harmonics at 0.6/0.3/0.1 amplitude weights), quadratic endpoint taper, optional heightmap-aware uphill rejection
- `generate_river_mesh()`: Quad-strip surface mesh from grid path with configurable width, depth offset, and tessellation density
- `generate_lake_mesh()`: Radial disc with 3-ring tessellation, organic shore noise (2 harmonics), center-draping water surface
- `generate_waterfall_volumetric_mesh()`: Thick tapered prism with rounded front (sinusoidal curvature), per-section back+front cross-sections, surface noise for organic appearance. Satisfies MUST-be-volumetric requirement.

### Task 2: Unit Tests (910bed0)

36 tests covering:
- A* prefer_downhill: valley following, lower terrain preference, uphill avoidance, legacy compatibility
- Meander: endpoint preservation, amplitude scaling, heightmap awareness, determinism
- River mesh: structure, width, quad faces, water-below-terrain, index validity
- Lake mesh: structure, center, shore noise, determinism
- Waterfall volumetric: 3D non-flat check, taper, density, straight-down case

### Task 3: Integration Tests (ebfb58c)

7 end-to-end pipeline tests:
- A* -> meander -> river mesh (full pipeline)
- Carve + mesh coherence (water below carved terrain)
- Depression -> lake mesh (correct center placement)
- Cliff -> waterfall volumetric (3D extent in all axes)
- Degenerate face detection for river and waterfall meshes

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Asymmetric cost factors**: 0.1x downhill / 10.0x uphill chosen after testing on valley heightmap. The 100:1 ratio produces strong drainage-following behavior without making the pathfinder avoid all height changes.

2. **Meander wavelength harmonics**: 3 harmonics (1x, 0.5x, 2x) with amplitude weights (0.6, 0.3, 0.1) produce visually natural curves that match real river meander patterns without being perfectly periodic.

3. **Waterfall front curvature**: Sinusoidal `sin(pi * wt)` profile across width creates a smooth rounded front that satisfies the "never flat plane" requirement while keeping vertex count manageable.

## Self-Check: PASSED
