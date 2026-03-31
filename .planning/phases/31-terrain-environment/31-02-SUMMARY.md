---
phase: 31-terrain-environment
plan: 02
subsystem: vegetation
tags: [lsystem, tree-generation, poisson-disk, scatter, leaf-cards, mesh-bridge]

# Dependency graph
requires:
  - phase: 30-mesh-foundation
    provides: "procedural_meshes generators, _mesh_bridge mapping tables, conftest bpy mocking"
provides:
  - "L-system tree generation wired into VEGETATION_GENERATOR_MAP (7 tree types)"
  - "_lsystem_tree_generator adapter bridging dict-params to MeshSpec with leaf card merging"
  - "Scatter-optimized tree templates with iterations=3 and ring_segments=4"
  - "PROP_GENERATOR_MAP dead_tree/tree_twisted entries using L-system"
affects: [31-terrain-environment, 34-multi-biome-terrain, 38-starter-town]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "L-system adapter pattern: _lsystem_tree_generator wraps dict-params generate_lsystem_tree into (func, kwargs) MeshSpec interface"
    - "Leaf card merging: vertex/face arrays concatenated with offset indexing"
    - "Scatter LOD override: tree templates default iterations=3, ring_segments=4 for instanced performance"

key-files:
  created: []
  modified:
    - "Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py"
    - "Tools/mcp-toolkit/tests/test_vegetation_lsystem.py"

key-decisions:
  - "Used _lsystem_tree_generator adapter pattern to bridge dict-params L-system API to the (func, kwargs) convention used by all generator maps"
  - "Capped iterations=4 in VEGETATION_GENERATOR_MAP entries (scatter map), defaulting to 3 in _create_vegetation_template (scatter templates) to prevent exponential geometry growth"
  - "Mapped 5 distinct L-system species across 7 tree type keys: oak (tree/tree_healthy), birch (tree_boundary), twisted (tree_blighted/tree_twisted), dead (tree_dead), pine (pine_tree)"
  - "Dead trees (tree_dead) have leaf_type=None -- no leaf card geometry generated"

patterns-established:
  - "L-system adapter pattern: wrap pure-logic generator into MeshSpec-compatible (func, kwargs) tuple for generator map dispatch"
  - "Leaf card merging: append leaf vertices/faces with v_offset to main tree MeshSpec"

requirements-completed: [MESH-10]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 31 Plan 02: L-System Vegetation Scatter Summary

**Replaced sphere-cluster tree generation with L-system branching trees across 7 vegetation types, with leaf card geometry at branch tips and Poisson disk scatter integration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T12:51:15Z
- **Completed:** 2026-03-31T12:54:24Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Rewired all 7 tree entries in VEGETATION_GENERATOR_MAP from generate_tree_mesh (sphere clusters) to _lsystem_tree_generator (L-system branching)
- Leaf card geometry (broadleaf, needle, vine) merged into tree MeshSpec at branch tips via vertex/face concatenation
- 5 distinct L-system species with unique branching patterns: oak (broad spreading canopy), birch (slender delicate branches), twisted (wind-swept asymmetric), dead (bare twisted, no foliage), pine (tall conical with regular whorls)
- Scatter template optimization: iterations=3 and ring_segments=4 for instanced tree performance
- 9 new integration tests verifying L-system wiring, leaf attachment, iteration caps, and species diversity
- All 184 vegetation/scatter/vegetation_system tests pass

## Task Commits

Each task was committed atomically (TDD flow):

1. **Task 1 RED: Failing L-system scatter integration tests** - `1eb53de` (test)
   - 9 tests verifying VEGETATION_GENERATOR_MAP uses _lsystem_tree_generator
   - Tests for all 7 tree types, leaf card attachment, iteration caps, PROP_GENERATOR_MAP entries
2. **Task 1 GREEN: Rewire VEGETATION_GENERATOR_MAP to L-system trees** - `bd6a02e` (feat)
   - _lsystem_tree_generator adapter function with leaf card merging
   - All 7 tree entries replaced, PROP_GENERATOR_MAP dead_tree/tree_twisted updated
   - environment_scatter.py scatter template overrides for L-system trees

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py` - Added _lsystem_tree_generator adapter, replaced 7 tree entries + 2 prop entries with L-system generators
- `Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py` - Updated _create_vegetation_template with L-system scatter LOD overrides (iterations=3, ring_segments=4)
- `Tools/mcp-toolkit/tests/test_vegetation_lsystem.py` - Added TestLsystemScatterIntegration class with 9 integration tests

## Decisions Made
- Used adapter pattern (_lsystem_tree_generator) rather than modifying generate_lsystem_tree's interface, preserving backward compatibility
- Capped iterations at 4 for scatter map entries and 3 for scatter templates to prevent exponential geometry growth (L-system rule like "F -> FF[+F][-F]F[+F]" doubles segments per iteration)
- Dead trees explicitly have leaf_type=None so no leaf card geometry is generated (matching botanical accuracy)
- PROP_GENERATOR_MAP also updated for dead_tree and tree_twisted entries for consistency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all tree types produce complete L-system geometry with leaf cards where appropriate.

## Next Phase Readiness
- L-system vegetation scatter pipeline fully wired and tested
- Ready for biome-specific vegetation configuration in Phase 34 (multi-biome terrain)
- Poisson disk scatter engine already exists and integrates with biome filter -- no additional wiring needed
- Billboard LOD fallback (generate_billboard_impostor) available but not yet wired into automatic LOD switching

## Self-Check: PASSED

- [x] _mesh_bridge.py exists
- [x] environment_scatter.py exists
- [x] test_vegetation_lsystem.py exists
- [x] 31-02-SUMMARY.md exists
- [x] Commit 1eb53de (test) found
- [x] Commit bd6a02e (feat) found
- [x] 184 tests pass (vegetation + scatter + vegetation_system)

---
*Phase: 31-terrain-environment*
*Completed: 2026-03-31*
