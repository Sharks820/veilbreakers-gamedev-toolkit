---
phase: 31-terrain-environment
plan: 03
subsystem: terrain
tags: [numpy, heightmap, voronoi, biome, flatten-zone, cliff-overlay, splatmap, moisture]

# Dependency graph
requires:
  - phase: 31-01
    provides: Domain-warped heightmap generation with heavy erosion
provides:
  - flatten_terrain_zone pure-logic function for building foundation placement
  - flatten_multiple_zones for sequential zone application
  - voronoi_biome_distribution with domain-warped boundaries and softmax blend weights
  - detect_cliff_edges for automatic steep region identification
  - Cliff overlay mesh placement in handle_generate_terrain
  - Moisture-aware splatmap painting via auto_assign_terrain_layers moisture_map param
  - D8 flow accumulation -> moisture map pipeline wired in environment handler
affects: [32-building-system, 34-multi-biome-terrain, 38-starter-town]

# Tech tracking
tech-stack:
  added: []
  patterns: [smoothstep-blend-zone, voronoi-softmax-weights, flood-fill-cluster-detection, moisture-from-flow-accumulation]

key-files:
  created:
    - Tools/mcp-toolkit/tests/test_terrain_flatten.py
    - Tools/mcp-toolkit/tests/test_terrain_biome_voronoi.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py
    - Tools/mcp-toolkit/tests/test_terrain_depth.py
    - Tools/mcp-toolkit/tests/test_terrain_materials.py

key-decisions:
  - "Smoothstep (3t^2-2t^2) blend for flatten zones provides C1 continuity -- no visible seam at building foundations"
  - "Voronoi biome distribution uses jittered grid seed placement + domain-warped distances + softmax for organic boundaries"
  - "Cliff edge detection uses flood-fill connected components with min_cluster_size filter to avoid noise"
  - "Moisture derived from log-normalized D8 flow accumulation after erosion -- natural drainage patterns drive splatmap"

patterns-established:
  - "Flatten zone pattern: center_x/y + radius + blend_width + optional target_height for building placement"
  - "Voronoi softmax pattern: distance-based blend weights normalized per cell for smooth biome transitions"
  - "Moisture pipeline: erosion -> compute_flow_map -> log1p normalize -> pass as moisture_map to splatmap"

requirements-completed: [MESH-05, MESH-09]

# Metrics
duration: 11min
completed: 2026-03-31
---

# Phase 31 Plan 03: Terrain Flatten Zones, Voronoi Biomes, Cliff Overlays, Moisture Splatmap Summary

**Building foundation flatten zones with smoothstep blending, 5+ Voronoi biome distribution with domain-warped boundaries, automatic cliff mesh overlays at steep edges, and moisture-aware splatmap painting from D8 flow accumulation**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-31T13:00:02Z
- **Completed:** 2026-03-31T13:11:02Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- flatten_terrain_zone() creates level building foundations with C1-continuous smoothstep blending to surrounding terrain
- voronoi_biome_distribution() distributes 5+ biomes across terrain using jittered grid seeds, domain-warped Voronoi boundaries, and softmax blend weights summing to 1.0
- detect_cliff_edges() identifies steep terrain regions via connected-component flood fill and returns cliff overlay placement parameters
- handle_generate_terrain wired with flatten_zones, cliff_overlays, and moisture-based splatmap painting
- 27 new tests across 4 test files, all passing (508 total terrain tests green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Terrain flatten zones + Voronoi biome distribution** - `a47f4a2` (feat, TDD)
2. **Task 2: Cliff overlays + moisture splatmap + handler wiring** - `ad0c8fc` (feat)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py` - Added flatten_terrain_zone() and flatten_multiple_zones() pure-logic functions
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` - Added voronoi_biome_distribution() with domain-warped boundaries and softmax weights
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py` - Added detect_cliff_edges() with flood-fill connected component clustering
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py` - Extended auto_assign_terrain_layers() with moisture_map parameter for height+slope+moisture blending
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py` - Wired flatten_zones, cliff_overlays, and moisture map computation into handle_generate_terrain
- `Tools/mcp-toolkit/tests/test_terrain_flatten.py` - 9 tests for flatten zone behavior (flat area, smooth blend, auto target, preserve outside, multiple zones)
- `Tools/mcp-toolkit/tests/test_terrain_biome_voronoi.py` - 9 tests for Voronoi distribution (multi-biome, weight sum, determinism, transitions, shapes)
- `Tools/mcp-toolkit/tests/test_terrain_depth.py` - 5 new tests for cliff edge detection
- `Tools/mcp-toolkit/tests/test_terrain_materials.py` - 4 new tests for moisture-aware splatmap

## Decisions Made
- Used smoothstep (3t^2 - 2t^3) for flatten zone blending instead of linear or cosine -- provides C1 continuity with zero derivative at boundaries, eliminating visible seams
- Voronoi seed points placed on jittered grid (not pure random) for more even spatial coverage -- avoids biome clustering
- Domain warping applied to Voronoi distances (not seed positions) for organic boundary shapes while maintaining cell ownership stability
- Cliff detection uses 4-connected flood fill with min_cluster_size=4 filter -- simple, correct, avoids scipy dependency
- Moisture map computed as log1p(flow_accumulation) / max -- log scale prevents river channels from dominating the entire moisture signal
- Cliff overlay threshold defaults to 60 degrees in handler but tests use 10 degrees because normalized heightmaps produce modest slope values through np.gradient

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cliff edge detection threshold calibration**
- **Found during:** Task 2 (cliff edge tests)
- **Issue:** Normalized heightmap values [0,1] produce maximum slopes of ~26 degrees through np.gradient central differences, so the planned 60-degree threshold finds no cliffs in test data
- **Fix:** Test heightmaps use 10-degree threshold with full 0.0->1.0 drops; handler default stays at 60 degrees since real terrain with height_scale multiplier produces steeper gradients
- **Files modified:** tests/test_terrain_depth.py
- **Verification:** All 5 cliff detection tests pass
- **Committed in:** ad0c8fc

**2. [Rule 1 - Bug] Smooth blend test using noisy heightmap**
- **Found during:** Task 1 (TDD RED->GREEN)
- **Issue:** Test checked max adjacent-cell step across entire grid including noisy terrain far from blend zone, always failing
- **Fix:** Changed test to use smooth gradient heightmap to isolate blend behavior, check radial profile only
- **Files modified:** tests/test_terrain_flatten.py
- **Verification:** Smooth blend test passes with max_step < 0.05
- **Committed in:** a47f4a2

---

**Total deviations:** 2 auto-fixed (2 bugs in test design)
**Impact on plan:** Both fixes corrected test methodology without changing implementation. No scope creep.

## Issues Encountered
None beyond the test calibration issues documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully implemented with real logic, no placeholder data or TODO markers.

## Next Phase Readiness
- Terrain system now supports building foundation placement (flatten_zones), multi-biome distribution (voronoi), cliff overlays, and moisture-aware splatmap painting
- Phase 32 (Building System) can use flatten_zones to create level building sites
- Phase 34 (Multi-biome Terrain) can use voronoi_biome_distribution for biome layout
- All 508 terrain tests passing -- no regressions

## Self-Check: PASSED

- All 9 files FOUND
- Commits a47f4a2 and ad0c8fc FOUND
- flatten_terrain_zone present in terrain_advanced.py
- voronoi_biome_distribution present in _terrain_noise.py
- detect_cliff_edges present in _terrain_depth.py
- moisture_map references present in terrain_materials.py
- 508 terrain tests passing

---
*Phase: 31-terrain-environment*
*Completed: 2026-03-31*
