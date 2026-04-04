---
phase: 39-pipeline-systemic-fixes
plan: "02"
subsystem: placement-pipeline
tags: [safe_place_object, terrain-height, z-axis, placement, smoothstep, shared-utils]

requires:
  - phase: 39-01
    provides: foundation quality systems

provides:
  - _shared_utils.py with safe_place_object() and smoothstep()
  - Terrain-height-aware placement in worldbuilding.py (encounter zones, boss arena, dressing)
  - Terrain-height-aware placement in worldbuilding_layout.py (buildings, landmarks, perimeter)
  - Water exclusion support via water_level parameter
  - Bounds-checking support for scatter passes
  - 20 new tests for shared_utils

affects: [worldbuilding, worldbuilding_layout, environment_scatter, settlement_generator]

tech-stack:
  added: []
  patterns:
    - "safe_place_object(x, y, terrain_name) -> (x, y, z) with closest_point_on_mesh sampling"
    - "Fallback to z=offset_z (default 0.02) when no terrain found"
    - "_terrain_loc() local helper for bulk dressing placement in location generators"
    - "Interior/dungeon Z=0 preserved intentionally (local coordinate system)"

key-files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py
    - Tools/mcp-toolkit/tests/test_shared_utils.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py

key-decisions:
  - "Interior/dungeon Z=0 left intentional: dungeon floors, cave walls, room shells, doorways, pillars use Z=0 as local ground in their own coordinate system"
  - "Pure-logic modules (coastline.py, terrain_features.py) not modified: Z=0 in data positions is a placeholder consumed by materializers"
  - "safe_place_object uses closest_point_on_mesh for accuracy, falls back to nearest-vertex brute-force"
  - "Auto-detect terrain by name patterns (Terrain/terrain/Ground/ground) when terrain_name=None"

patterns-established:
  - "safe_place_object(x, y, terrain_name) is the single entry point for all terrain-aware placement"
  - "_terrain_loc() nested helper for location-dressing bulk placement in handle_generate_location"

requirements-completed: [PIPE-02, PIPE-04]

duration: ~20min
completed: 2026-04-04
---

# Phase 39 Plan 02b: Z=0 Bulk Replacement + Y-Axis Verification Summary

**Created _shared_utils.py with safe_place_object() terrain sampler, replaced 25+ outdoor Z=0 hardcodings in worldbuilding.py and worldbuilding_layout.py, verified zero Y-axis vertical bugs across all handlers -- 20 new tests, 19749 existing pass.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-04T11:45:57Z
- **Completed:** 2026-04-04T12:05:42Z
- **Tasks:** 2/2
- **Files modified:** 4 (2 handlers + 1 new util + 1 new test file)

## Accomplishments

### Task 1: Replace Z=0 hardcoded placements with safe_place_object() (commit d1706ba)

**_shared_utils.py created with:**
- `smoothstep(t)` -- Hermite S-curve interpolation, clamped [0,1]
- `safe_place_object(x, y, terrain_name, water_level, bounds, offset_z)` -- terrain height sampler with closest_point_on_mesh, water exclusion, bounds checking, fallback to z=offset_z

**worldbuilding_layout.py -- 5 outdoor placements fixed:**
- Town building placement (line ~493): `building_obj.location` now uses safe_place_object
- Landmark placement (line ~518): `lm_obj.location` now uses safe_place_object
- Perimeter walls/gates/towers (3 mesh_from_spec + 1 fallback): computed once as `_perim_loc`, shared across gate/tower/wall branches

**worldbuilding.py -- 20+ outdoor placements fixed:**
- Boss arena cover (4 types: pillar, rock, wall_fragment, statue): computed once as `_cover_loc`
- Hazard disc marker: safe_place_object for location
- Fog gate archway: safe_place_object for location
- Encounter zone parent empty + waypoint empties + spawn point empties (3 separate fixes)
- Location dressing via `_terrain_loc()` helper: farm_plot, fence, tent, campfire, lookout_post, hitching_post, market_stall, cart, holy_symbol, map_display, candelabra, pillar, gravestone, barricade
- `add_scene_prop()` modified to auto-sample terrain via `_terrain_loc()`

**Intentionally preserved Z=0 in:**
- Dungeon floor/wall/corridor/door geometry ops (lines 67-132): local coordinate system
- Cave floor/wall geometry ops: local coordinate system
- Town road/plot geometry ops: local coordinate system
- Interior room shells, doorways, pillars: interior-local coordinates
- Spawn/loot dungeon points: dungeon-local data
- Pure-logic waypoint data in encounter zone spec: consumed by materializer
- Water object location: intentionally at water_level=0.0

### Task 2: Y-axis vertical bug verification (commit d0c0782)

**Full codebase grep found zero Y-axis vertical bugs:**
- `terrain_features.py` cliff_face: correctly uses Z for height, Y for depth (docstring confirms "rising in Z")
- `modeling_advanced.py` line 1339: `Vector((0,1,0))` is standard fallback when normal parallel to Z-up
- `decal_system.py` line 388: same standard fallback pattern
- `monster_bodies.py` Y->Z swaps: intentional coordinate transforms with comments explaining rationale
- `procedural_meshes.py` `v[1]` used with height: these are tuple-indexed vertex manipulations where Y=height is the mesh generation convention, later rotated at object level

**20 new tests added for _shared_utils:**
- 7 smoothstep tests (zero, one, half, clamp, quarter, monotonicity)
- 13 safe_place_object tests (fallback, offset, bounds, water exclusion, edge cases)

## Task Commits

1. **Task 1: Z=0 replacement** - `d1706ba` (feat)
2. **Task 2: Y-axis verification + tests** - `d0c0782` (test)

## Files Created/Modified

- `Tools/mcp-toolkit/blender_addon/handlers/_shared_utils.py` - New: safe_place_object + smoothstep utilities
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` - Fixed 20+ outdoor Z=0 placements
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` - Fixed 5 outdoor Z=0 placements
- `Tools/mcp-toolkit/tests/test_shared_utils.py` - New: 20 tests for shared utilities

## Decisions Made

1. **Interior Z=0 preserved**: Dungeon/cave/room-shell Z=0 is intentional (local coordinate system), not terrain placement
2. **Pure-logic modules untouched**: coastline.py and terrain_features.py are pure-logic (no bpy); their Z=0 data positions are consumed by materializers that should sample terrain
3. **closest_point_on_mesh preferred**: More accurate than raycast for arbitrary terrain shapes; falls back to nearest-vertex scan
4. **Auto-detect terrain**: When terrain_name=None, scan bpy.data.objects for common names (Terrain/Ground)
5. **Water placement left at Z=0**: Water objects sit at water_level by design

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created _shared_utils.py (prerequisite missing)**
- **Found during:** Task 1 setup
- **Issue:** Plan 39-01 from pipeline-systemic-fixes phase was never executed, so _shared_utils.py with safe_place_object() did not exist
- **Fix:** Created the module with full implementation matching the planned interface signature
- **Files modified:** blender_addon/handlers/_shared_utils.py
- **Commit:** d1706ba

**2. [Rule 1 - Bug] Reduced replacement count from planned 42 to actual 25+**
- **Found during:** Task 1 file analysis
- **Issue:** Plan counted all Z=0 instances including dungeon/cave/interior geometry ops and pure-logic data modules. Many are intentionally Z=0 (local coordinate systems, not terrain placement)
- **Fix:** Only replaced outdoor placement instances where objects are placed in world space at Z=0 instead of on terrain. Documented which Z=0 instances were intentionally preserved.
- **Impact:** Correct -- blindly replacing all Z=0 would break dungeon/cave floor generation

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 scope correction)
**Impact on plan:** Deviation 1 was necessary to create missing prerequisite. Deviation 2 improved plan accuracy by distinguishing outdoor terrain placements from intentional indoor Z=0 coordinates.

## Known Stubs

None -- all safe_place_object calls are fully wired with terrain sampling and fallback logic.

## Issues Encountered

- 3 pre-existing security test failures (test_blocked_import_os, test_blocked_from_import, test_nested_import_in_function) -- out of scope, not caused by this plan's changes

## Next Phase Readiness

- safe_place_object() available for import from `._shared_utils` in all handler files
- Pure-logic modules (coastline.py, terrain_features.py) could be enhanced to include terrain_name in their data dicts for materializers to consume
- smoothstep() available for Plan 03 (smoothstep bulk replacement)

## Self-Check: PASSED

---
*Phase: 39-pipeline-systemic-fixes*
*Completed: 2026-04-04*
