---
phase: 31-terrain-environment
plan: 02
subsystem: vegetation
tags: [lsystem, vegetation, scatter, poisson-disk, leaf-cards, mesh-generation, blender]

# Dependency graph
requires:
  - phase: 30-mesh-foundation
    provides: procedural mesh generator mapping pattern, MeshSpec convention
provides:
  - L-system tree adapter (_lsystem_tree_generator) for VEGETATION_GENERATOR_MAP
  - 7 tree type entries wired to L-system grammars with leaf cards
  - Iteration-capped scatter templates for performance
  - PROP_GENERATOR_MAP dead_tree/tree_twisted L-system wiring
affects: [31-terrain-environment, 34-multi-biome-terrain, 38-starter-town]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_lsystem_tree_generator adapter pattern: bridges (func, kwargs) map to dict-params L-system generator"
    - "Leaf card merge pattern: offset vertex indices when combining tree + leaf geometry"

key-files:
  created: []
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py
    - Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py
    - Tools/mcp-toolkit/tests/test_vegetation_lsystem.py

key-decisions:
  - "Used adapter function pattern instead of modifying generate_lsystem_tree signature"
  - "Capped iterations=4 in map, default 3 in scatter templates for performance"
  - "Merged leaf card vertices directly into tree MeshSpec rather than separate objects"

patterns-established:
  - "_lsystem_tree_generator adapter: kwargs->dict bridge with optional leaf card merge"
  - "Scatter template LOD: iterations=3, ring_segments=4 for instanced trees"

requirements-completed: [MESH-10]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 31 Plan 02: L-System Vegetation Scatter Summary

**Rewired 7 tree types from sphere-cluster to L-system branching with leaf cards, iteration-capped for scatter performance**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T12:42:48Z
- **Completed:** 2026-03-31T12:48:25Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Replaced all sphere-cluster tree generation with L-system branching in VEGETATION_GENERATOR_MAP
- 7 tree types mapped: oak, birch, twisted, dead, pine with distinct branching patterns per grammar
- Leaf card geometry merged at branch tips (broadleaf, vine, needle per species)
- Dead trees correctly have leaf_type=None (no leaves)
- Iterations capped at 4 for map entries, 3 for scatter templates (prevents exponential geometry growth)
- 10 new integration tests verify L-system wiring, all 185 vegetation/scatter tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: L-system scatter integration tests** - `1eb53de` (test)
2. **Task 1 GREEN: Rewire VEGETATION_GENERATOR_MAP to L-system** - `bd6a02e` (feat)
3. **Task 1 REFACTOR: Fix prop scatter L-system params + species diversity test** - `da5a868` (fix)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py` - Added _lsystem_tree_generator adapter, replaced 7 tree entries + 2 prop entries with L-system generators
- `Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py` - Updated _create_vegetation_template to use iterations/ring_segments overrides for L-system trees
- `Tools/mcp-toolkit/tests/test_vegetation_lsystem.py` - Added TestLsystemScatterIntegration class with 10 tests (including 3+ species diversity check)

## Decisions Made
- Used adapter function pattern (_lsystem_tree_generator) rather than modifying generate_lsystem_tree's interface -- preserves backward compatibility
- iterations=4 in VEGETATION_GENERATOR_MAP (balanced quality/performance), iterations=3 in scatter templates (maximum performance for instanced trees)
- Leaf cards merged into single MeshSpec via vertex index offset -- keeps tree+leaves as one mesh object for collection instancing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Updated PROP_GENERATOR_MAP tree entries**
- **Found during:** Task 1 (L-system wiring)
- **Issue:** PROP_GENERATOR_MAP had dead_tree and tree_twisted entries still using generate_tree_mesh (sphere clusters)
- **Fix:** Updated both entries to use _lsystem_tree_generator with appropriate tree_type/leaf_type params
- **Files modified:** Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py
- **Verification:** test_prop_map_tree_entries_use_lsystem passes
- **Committed in:** bd6a02e (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed prop scatter template using old branch_count param**
- **Found during:** Task 1 (refactor pass)
- **Issue:** `_create_prop_template` in environment_scatter.py still set `branch_count=3` for dead_tree -- a parameter from the old sphere-cluster generator, ignored by the L-system adapter
- **Fix:** Replaced with `iterations=3, ring_segments=4` for dead_tree and tree_twisted prop types
- **Files modified:** Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py
- **Verification:** All 185 tests pass
- **Committed in:** da5a868 (Task 1 REFACTOR commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Essential for consistency -- all tree entries across all maps now use L-system with correct params. No scope creep.

## Issues Encountered
None

## Known Stubs
None -- all tree types produce real L-system geometry with leaf cards.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- L-system trees wired into scatter pipeline, ready for biome-aware terrain scatter (31-03)
- Poisson disk scatter engine already functional with biome filtering
- All vegetation/scatter tests passing (185 total)

## Self-Check: PASSED

- FOUND: Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py
- FOUND: Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py
- FOUND: Tools/mcp-toolkit/tests/test_vegetation_lsystem.py
- FOUND: .planning/phases/31-terrain-environment/31-02-SUMMARY.md
- FOUND: commit 1eb53de (TDD RED)
- FOUND: commit bd6a02e (TDD GREEN)
- FOUND: commit da5a868 (TDD REFACTOR)

---
*Phase: 31-terrain-environment*
*Completed: 2026-03-31*
