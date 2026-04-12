---
phase: "55"
plan: "05"
subsystem: terrain-caves
tags: [caves, perlin-worm, marching-cubes, stalactites, water-pools, lighting, portals, entrance-asymmetry]
dependency_graph:
  requires: [terrain_semantics, terrain_pipeline, terrain_masks]
  provides: [cave-deep-dive-analysis, cave-mesh-generation, cave-interior-features]
  affects: [terrain_caves.py, test_caves_deep_dive.py]
tech_stack:
  added: [perlin-worm-paths, marching-cubes-isosurface, cave-lighting-zones]
  patterns: [SDF-volume-field, exponential-light-falloff, Z-minima-pool-detection]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_caves_deep_dive.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_caves.py
decisions:
  - Used Jenkins integer hash mix for Perlin noise instead of weak linear hash
  - Simplified marching cubes (face-crossing approach) instead of full 256-entry LUT
  - Exponential light falloff with half-life tuned per archetype
  - Water pools detected at path Z-minima rather than volume-based analysis
metrics:
  duration_seconds: 558
  completed: "2026-04-12T12:59:29Z"
  tasks_completed: 2
  tests_added: 61
  tests_total_pass: 88
---

# Phase 55 Plan 05: Cave Deep-Dive (Sub-phase 6E) Summary

Pure-numpy cave deep-dive with Perlin worm paths, marching cubes mesh extraction, stalactite/stalagmite placement, water pool detection, lighting zones with bioluminescence, portal placement, and asymmetric entrance geometry.

## What Was Built

### 1. Perlin Worm Cave Paths (`generate_perlin_worm_path`)
- Noise-driven 3D tunnel path generation using layered value noise
- Configurable vertical bias, horizontal wander, segment count
- Jenkins 32-bit integer hash for robust noise variation
- Helper `_hash_int` and `_perlin_1d` functions

### 2. Marching Cubes Mesh (`marching_cubes_cave_mesh`)
- 3D signed distance field construction from cave path (`_build_cave_volume_field`)
- Isosurface extraction at configurable threshold
- Edge interpolation with vertex caching for deduplication
- Capped grid dimensions (64x64x64) to prevent memory blowout
- Returns `CaveMeshSpec` with vertices, triangles, counts

### 3. Stalactite/Stalagmite Placement (`place_stalactites`)
- 60/40 ceiling/floor split for stalactites vs stalagmites
- Mineral type selection: calcite, iron_oxide, wet_calcite (dampness-influenced)
- Drip activation probability scales with damp_intensity
- Size variation via noise, density and max_count controls

### 4. Water Pool Detection (`detect_cave_water_pools`)
- Local Z-minima detection along cave path polyline
- Pool depth = minimum of left/right wall heights above minimum
- Flow direction computed when path continues descending
- Connected-to-stream probability scales with dampness
- Returns `CaveWaterPool` with center, radius, depth, surface_z

### 5. Cave Lighting Zones (`compute_cave_lighting_zones`)
- Exponential intensity falloff from entrance (half-life: 5-12m per archetype)
- Four zone types: entrance, twilight, dark, deep_dark
- Color temperature shifts from 6500K (daylight) to 2000K (deep)
- God rays at entrance only
- Bioluminescence in deep zones (higher probability for wet archetypes)

### 6. Portal Placement (`place_cave_portals`)
- End-of-path exit portal always present
- Karst sinkholes get vertical shaft at deepest Z point
- Sea grottos may get underwater portal
- Optional secret passages at path midpoints
- Blockage and discovery difficulty classification

### 7. Asymmetric Entrance (`generate_asymmetric_entrance`)
- Left/right height asymmetry (10-30% difference)
- Overhang geometry (always for sea_grotto/lava_tube, probabilistic otherwise)
- Irregular top-edge profile via angular sampling
- Rock shelf placement on sides

### 8. Unified Composition (`analyze_deep_cave`)
- Composes all 7 features into `DeepCaveAnalysis` dataclass
- Per-archetype parameter tuning
- Optional mesh generation toggle
- Deterministic via seed XOR mixing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken Perlin noise hash function**
- **Found during:** Task 2 (test execution)
- **Issue:** Linear hash `n * 127 + seed * 311` was dominated by seed term, producing near-constant output across all t values
- **Fix:** Replaced with Jenkins 32-bit integer mix using large prime XOR: `n * 73856093 ^ seed * 19349663 ^ o * 83492791`
- **Files modified:** terrain_caves.py
- **Commit:** ceb0987

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Cave deep-dive features | f68e8c8 | terrain_caves.py |
| 2 | Tests + hash fix | ceb0987 | test_caves_deep_dive.py, terrain_caves.py |

## Test Results

- **New tests:** 61 (all passing)
- **Existing cave tests:** 27 (all passing, no regressions)
- **Total cave tests:** 88

### Test Coverage by Feature

| Feature | Tests | Status |
|---------|-------|--------|
| Perlin worm paths | 7 | PASS |
| Perlin 1D noise | 3 | PASS |
| Marching cubes mesh | 6 | PASS |
| Stalactites | 9 | PASS |
| Water pools | 8 | PASS |
| Lighting zones | 10 | PASS |
| Portals | 7 | PASS |
| Asymmetric entrance | 6 | PASS |
| Unified analysis | 5 | PASS |

## Self-Check: PASSED

- terrain_caves.py: FOUND
- test_caves_deep_dive.py: FOUND
- 55-05-SUMMARY.md: FOUND
- Commit f68e8c8: FOUND
- Commit ceb0987: FOUND
