---
phase: 41-broken-generator-fixes
plan: 01
subsystem: blender-handlers
tags: [creature-anatomy, vegetation-lsystem, mesh-builder, orientation, bmesh]

# Dependency graph
requires:
  - phase: 30-mesh-foundation
    provides: _build_quality_object pipeline and mesh_from_spec bridge
provides:
  - _creature_tuple_to_meshspec adapter for 5 creature generators
  - _default_branch_tips helper for standalone leaf card generation
  - vegetation_lsystem_tree wired through _build_quality_object
  - vegetation_leaf_cards standalone generation with default tips
  - Shield orientation detection (boss/grip_bar/arm_strap vertex groups)
affects: [creature-generators, vegetation-pipeline, weapon-shield-orientation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tuple-to-MeshSpec adapter pattern for generators that return raw tuples"
    - "Default fallback helper pattern for optional handler parameters"

key-files:
  created: []
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/__init__.py
    - Tools/mcp-toolkit/tests/test_creature_anatomy.py
    - Tools/mcp-toolkit/tests/test_vegetation_lsystem.py
    - Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py

key-decisions:
  - "cap_fill is correct API for bmesh.ops.create_circle (not cap_ends which is for create_cone) -- plan had incorrect assumption"
  - "Adapter pattern chosen over modifying 5 creature generators to return dicts -- less invasive, preserves backward compat"

patterns-established:
  - "_creature_tuple_to_meshspec: convert (verts, faces, groups[, bones]) tuples to MeshSpec dicts"
  - "_default_branch_tips: generate synthetic tips when handler called without branch_tips param"

requirements-completed: [GEN-01, GEN-02, GEN-03, GEN-04, GEN-06]

# Metrics
duration: 10min
completed: 2026-04-04
---

# Phase 41 Plan 01: Creature Generator Fixes Summary

**Adapter wraps 5 creature tuple returns into MeshSpec dicts, vegetation tree wired through object builder, leaf cards generate standalone, shield orientation detected**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-04T13:59:17Z
- **Completed:** 2026-04-04T14:09:42Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- 5 creature handlers (mouth, eyelid, paw, wing, serpent) no longer crash with "'tuple' object has no attribute 'get'" -- adapter converts tuples to MeshSpec dicts
- vegetation_lsystem_tree now creates Blender objects via _build_quality_object instead of returning raw JSON
- vegetation_leaf_cards generates geometry when called standalone (uses _default_branch_tips for synthetic tip positions)
- Shield objects get -90deg X rotation (same as weapons) via boss/grip_bar/arm_strap vertex group detection
- Boss arena cap_fill usage confirmed correct via regression test (cap_fill is the right bmesh API for create_circle)

## Task Commits

Each task was committed atomically (TDD flow):

1. **Task 1 RED: Failing tests** - `1c40a24` (test)
2. **Task 1 GREEN: Implementation** - `95c05ac` (feat)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` - Added _creature_tuple_to_meshspec adapter, _default_branch_tips helper, expanded shield orientation detection, wrapped 5 creature lambdas, wired vegetation through _build_quality_object
- `Tools/mcp-toolkit/tests/test_creature_anatomy.py` - 5 new tests verifying creature generators produce valid MeshSpec dicts via adapter
- `Tools/mcp-toolkit/tests/test_vegetation_lsystem.py` - 4 new tests for _default_branch_tips structure/determinism and standalone leaf card generation
- `Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py` - 1 regression test confirming boss arena uses correct cap_fill API

## Decisions Made
- **cap_fill vs cap_ends:** Plan assumed boss arena needed `cap_ends` instead of `cap_fill`. Research confirmed `cap_fill` IS the correct parameter for `bmesh.ops.create_circle` (cap_ends is for `create_cone`). Wrote regression test asserting the correct API instead of the incorrect one.
- **Adapter pattern:** Rather than modifying 5 creature generators to return dicts (which would break other callers), added a lightweight adapter function that wraps tuples at the handler dispatch level.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected cap_fill regression test direction**
- **Found during:** Task 1 (test writing)
- **Issue:** Plan instructed to verify lines use `cap_ends` not `cap_fill`, but `cap_fill` IS the correct Blender API for `bmesh.ops.create_circle`. Using `cap_ends` would crash at runtime.
- **Fix:** Wrote regression test asserting `cap_fill` is used (correct API), not `cap_ends` (wrong API for create_circle)
- **Files modified:** Tools/mcp-toolkit/tests/test_worldbuilding_handlers.py
- **Verification:** Test passes, confirmed against Blender bmesh API docs
- **Committed in:** 1c40a24

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan specification)
**Impact on plan:** Prevented a test that would assert wrong behavior. No scope change.

## Issues Encountered
None -- all generators worked as documented, adapter pattern applied cleanly.

## Known Stubs
None -- all handlers now produce real geometry through _build_quality_object pipeline.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 8 handler paths now produce valid Blender objects
- 19,759 tests passing (4 pre-existing security test failures out of scope)
- Ready for subsequent broken generator fix plans (41-02, 41-03)

## Self-Check: PASSED

---
*Phase: 41-broken-generator-fixes*
*Completed: 2026-04-04*
