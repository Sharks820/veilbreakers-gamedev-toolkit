---
phase: 39-pipeline-systemic-fixes
plan: "01"
subsystem: infra
tags: [blender, pipeline, dispatch, bmesh, smoothstep, terrain-placement, deprecated-api]

# Dependency graph
requires:
  - phase: 30-mesh-foundation
    provides: procedural mesh generators and handler architecture
provides:
  - smoothstep() and safe_place_object() shared utilities in _shared_utils.py
  - Fixed settlement dispatch routing (world_generate_settlement)
  - Fixed asset_pipeline addon handler (multi-action routing)
  - Blender 4.0+ node group interface API compatibility
  - Removed deprecated ShaderNodeTexMusgrave from whitelist
  - Fixed bmesh cap_fill -> cap_ends at 3 call sites
affects: [39-02 Z=0 bulk replacement, 39-03 smoothstep bulk replacement, 39-04 smart planner wiring, 39-05 rectangular terrain]

# Tech tracking
tech-stack:
  added: []
  patterns: [hasattr-based Blender version compat, lazy import for circular avoidance, shared utility module]

key-files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py
    - Tools/mcp-toolkit/tests/test_shared_utils.py
    - .planning/phases/39-pipeline-systemic-fixes/39-01-PLAN.md
  modified:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
    - Tools/mcp-toolkit/blender_addon/handlers/__init__.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py
    - Tools/mcp-toolkit/blender_addon/handlers/geometry_nodes.py
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py

key-decisions:
  - "Lazy import pattern for _sample_scene_height in safe_place_object to avoid circular imports"
  - "hasattr(group, 'interface') for Blender 4.0+ API with fallback to old API for backwards compat"
  - "Named function smoothstep() not smootherstep() to match standard Hermite terminology"
  - "asset_pipeline addon handler provides informative error for MCP-server-only actions"

patterns-established:
  - "_shared_utils.py: central utility module with zero handler imports at top level"
  - "hasattr-based version detection for Blender API compatibility"

requirements-completed: [PIPE-01, PIPE-03, PIPE-06]

# Metrics
duration: 11min
completed: 2026-04-04
---

# Phase 39 Plan 01: Utilities Foundation + Dispatch Fixes + Deprecated API Summary

**Shared smoothstep/safe_place_object utilities, 3 dispatch bug fixes, 6 deprecated Blender API replacements with version-compat fallbacks, 38 new tests**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-04T11:07:36Z
- **Completed:** 2026-04-04T11:18:09Z
- **Tasks:** 4
- **Files modified:** 7

## Accomplishments
- Created _shared_utils.py with smoothstep(), inverse_smoothstep(), lerp(), smooth_lerp(), and safe_place_object() -- foundation for plans 39-02 and 39-03
- Fixed settlement dispatch bug: _LOC_HANDLERS now routes to world_generate_settlement instead of world_generate_town, enabling full 15-type settlement system
- Replaced all 6 deprecated Blender API calls: node group interface (4.0+), Musgrave removal (4.1+), bmesh cap_fill->cap_ends
- Added 38 tests covering utilities, dispatch routing, and static analysis for deprecated patterns

## Task Commits

Each task was committed atomically:

1. **Task 1: Create _shared_utils.py** - `755674d` (feat)
2. **Task 2: Fix pipeline dispatch bugs** - `86699c3` (fix)
3. **Task 3: Fix deprecated Blender API calls** - `76dc281` (fix)
4. **Task 4: Write tests** - `218a1a8` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py` - Shared utilities: smoothstep, safe_place_object, lerp
- `Tools/mcp-toolkit/tests/test_shared_utils.py` - 38 tests for utilities, dispatch, deprecated API
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` - Fixed settlement routing, added settlement param shaping
- `Tools/mcp-toolkit/blender_addon/handlers/__init__.py` - Expanded asset_pipeline handler to multi-action routing
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py` - Blender 4.0+ interface API with hasattr fallback
- `Tools/mcp-toolkit/blender_addon/handlers/geometry_nodes.py` - Removed ShaderNodeTexMusgrave from whitelist
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` - cap_fill -> cap_ends at 3 sites

## Decisions Made
- Used lazy import pattern for `_sample_scene_height` in `safe_place_object` to avoid circular imports -- `_shared_utils.py` only imports from standard library at module level
- Named utility `smoothstep()` (not `smootherstep`) to match standard Hermite terminology (3t^2 - 2t^3); quintic version already exists in `_terrain_noise.py`
- Used `hasattr(group, "interface")` for Blender version detection rather than checking `bpy.app.version` -- more robust and self-documenting
- Made asset_pipeline addon handler return informative error for MCP-server-only actions instead of generic "Unknown action"
- Added settlement_type and radius param shaping in `_build_location_generation_params` for the newly-routed settlement handler

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added settlement param shaping**
- **Found during:** Task 2 (dispatch fixes)
- **Issue:** After fixing settlement routing to world_generate_settlement, the _build_location_generation_params function had no branch for loc_type=="settlement", so settlement-specific params (settlement_type, radius, center) would not be passed
- **Fix:** Added elif branch for settlement type in _build_location_generation_params
- **Files modified:** blender_server.py
- **Verification:** Code review confirms params reach handler
- **Committed in:** 86699c3 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for correctness -- without param shaping, the dispatch fix alone would send empty params to the settlement handler.

## Issues Encountered
- Regex lookbehind in test_no_cap_fill used variable-width pattern unsupported by Python 3.13 re module -- switched to line-by-line string check

## Known Stubs
None -- all utilities are fully implemented with complete logic.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- _shared_utils.py smoothstep() ready for plan 39-03 (35-site bulk replacement across animation handlers)
- safe_place_object() ready for plan 39-02 (42-site Z=0 replacement across 9 files)
- Dispatch fixes unblock plan 39-04 (smart planner wiring into compose_map)
- All deprecated API calls eliminated, no warnings on Blender 4.0+

---
## Self-Check: PASSED

All 4 created/modified files verified on disk. All 4 task commits verified in git log.

---
*Phase: 39-pipeline-systemic-fixes*
*Completed: 2026-04-04*
