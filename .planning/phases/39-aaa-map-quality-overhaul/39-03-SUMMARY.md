---
phase: 39
plan: 03
subsystem: worldbuilding
tags: [castle, settlement, combat, district-zoning, trim-sheet, boss-arena, mob-zones, interior-validation]
dependency_graph:
  requires: [39-01, 39-02]
  provides: [concentric-castle, gatehouse, market-square, district-zones, boss-arena-cover, mob-encounter-zones, interior-pathability, trim-sheet-uv]
  affects: [worldbuilding_layout.py, building_quality.py, worldbuilding.py]
tech_stack:
  added: []
  patterns: [pure-logic-spec-functions, proximity-voronoi-zoning, trim-sheet-atlas-uv, density-tier-mob-spawning]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_aaa_castle_settlement.py
    - Tools/mcp-toolkit/tests/test_aaa_combat_interiors.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py
    - Tools/mcp-toolkit/blender_addon/handlers/building_quality.py
decisions:
  - "Ring dict uses 'height'/'thickness' keys (not 'wall_height'/'wall_thickness') for brevity"
  - "assign_district_zones bounds format: {'min': (x,y), 'max': (x,y)} — not flat keys"
  - "Portcullis stores metallic/material_srgb directly (not nested 'material' sub-dict)"
  - "Sentry patrol produces 2-3 waypoints (back-and-forth pattern), other types produce 4-8"
  - "generate_encounter_zone_spec center param is (x,y) 2-tuple matching pure-logic convention"
metrics:
  duration_minutes: 45
  completed_date: "2026-04-02"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
  tests_added: 82
  tests_passing: 82
---

# Phase 39 Plan 03: AAA Castle, Settlement, and Combat Systems Summary

**One-liner:** Concentric 2-3 ring castle (6-16m height progression) with gatehouse, Voronoi district zoning for 5 zone types, 2048-atlas trim sheet UV, boss arena cover + fog gate, mob encounter zones with 4 patrol patterns and 5 density tiers, interior NPC pathability validation — 82 tests all passing.

## What Was Built

### Task 1: Concentric Castle + Gatehouse + Market Square + District Zoning + Trim Sheet

**`worldbuilding_layout.py`** — 7 new pure-logic functions appended:

1. **`generate_concentric_castle_spec`** — 2-3 ring castle: outer 6-8m, middle 10-12m, inner 12-16m; tower every 25-40m; material progression dark→light granite; calls `_generate_gatehouse_spec`.

2. **`_generate_gatehouse_spec`** — Passage 3-4m wide × 8-15m deep; two flanking towers 5-6m diameter; iron portcullis (bar_spacing=0.15m, metallic=1.0); 4-6 murder holes in ceiling; 3 arrow slits per tower face.

3. **`generate_market_square`** — Small(400m²)/medium(900m²)/large(2500m²) sizes; central feature: well/fountain/market_cross; stall count = floor(perimeter × 0.3 / 4); returns shape_verts, stall_positions.

4. **`assign_district_zones`** — 5-zone Voronoi-like placement from seed points: market(center), residential(near castle), military(near walls 60% radius), religious(center offset), slums(outermost 80% radius). 8-sided polygon approximation per zone.

5. **`generate_encounter_zone_spec`** — 4 patrol patterns: circuit(4-8 perimeter WPs), figure_eight(6-8 lemniscate WPs), sentry(2-3 edge WPs), wander(4-8 random WPs); 5 density tiers sparse→swarm (1-2/3-4/5-7/8-12/13-20 mobs); spawn point names `spawn_mob_{zone_id}_{n}`.

6. **`validate_interior_pathability_spec`** — Checks doorways ≥1.2m×2.2m, corridors ≥1.0m; counts blocked entries; verifies NPC spawn presence per room.

7. **`generate_trim_sheet_uv_spec`** — Maps mesh_type to 2048×2048 atlas bands: stone Y 0-256, wood Y 384-640, roof Y 1024-1280, ground Y 1280-1408; returns pixel range + normalised UV.

**`building_quality.py`** — 4 additions:

- `TRIM_SHEET_ATLAS_SIZE = 2048`
- `TRIM_SHEET_BANDS` dict mapping surface keywords to pixel ranges
- `get_trim_sheet_uv_band(surface_type)` — looks up band by keyword
- `apply_trim_sheet_uvs(mesh_spec)` — annotates MeshSpec.components with UV band assignments by keyword matching (wall/stone/battlement → stone, timber/wood → wood, roof/tile → roof, ground/floor → ground)

### Task 2: Tests (82 passing)

**`test_aaa_castle_settlement.py`** — 50 tests:
- `TestCastleConcentricRings` (9): ring count, height progression, range checks, tower spacing, radii decrease, gatehouse present
- `TestCastleGatehouse` (7): passage depth/width, portcullis present/iron material, murder holes, arrow slits, flanking towers
- `TestMarketSquare` (8): area ranges for small/medium/large, central feature, stall count/positions, center preserved
- `TestDistrictZoning` (6): 5 zone types, market near center, slums at edge (≥60m), polygon verts, zone count, non-empty
- `TestTrimSheetUV` (13): atlas size, all band pixel ranges, normalised values, apply_trim_sheet_uvs annotation, component mapping
- `TestRoadHierarchyWidths` (1): main 5-6m / secondary 3-4m / alley 1.5-2m width validation

**`test_aaa_combat_interiors.py`** — 32 tests:
- `TestBossArenaSize` (4): small/medium/large diameter ranges, radius = diameter/2
- `TestBossArenaCover` (6): cover count min/max/exact, spacing ≥6m, within radius, valid types
- `TestBossArenaFogGate` (4): presence, width 3-5m, position at entrance, disabled=None
- `TestBossArenaHazardZones` (4): zones present, count 2-3, valid types, within radius
- `TestMobEncounterZone` (11): waypoint counts per patrol type, density tiers (all 5), spawn points, naming convention, within radius
- `TestInteriorPathability` (9): passable/blocked detection, min width/height/exact-min, corridor clearance, NPC spawns, room count, empty edge case

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dict key mismatches in tests**

- **Found during:** Task 2 test execution
- **Issue:** Ring dicts use `"height"` and `"thickness"` (not `"wall_height"` / `"wall_thickness"`); gatehouse uses `"arrow_slits_per_tower_face"` count + `flanking_towers[n]["arrow_slits"]` list (not top-level `"arrow_slits"`); portcullis stores `"metallic"` directly (not nested `"material"` dict); `assign_district_zones` uses `"seed_pos"` (not `"seed_point"`)
- **Fix:** Updated all test assertions to match actual return dict keys
- **Files modified:** `test_aaa_castle_settlement.py`
- **Commit:** b00f4df

**2. [Rule 1 - Bug] Bounds format mismatch**

- **Found during:** Task 2 test execution
- **Issue:** Tests passed `{"min_x":..., "max_x":..., "min_y":..., "max_y":...}` but `assign_district_zones` expects `{"min": (x,y), "max": (x,y)}` — causing fallback to default bounds and slums distance test to fail with 0.0m
- **Fix:** Updated test bounds format to `{"min": (x,y), "max": (x,y)}`; adjusted slums distance threshold from 50m to 60m (correct for radius=100 → slums at 80% = 80m)
- **Files modified:** `test_aaa_castle_settlement.py`
- **Commit:** b00f4df

**3. [Rule 1 - Bug] Sentry patrol waypoint count**

- **Found during:** Task 2 test execution
- **Issue:** Test assumed all patrol types produce 4-8 waypoints; sentry produces 2-3 by design (back-and-forth pattern)
- **Fix:** Split patrol waypoint test to check circuit/figure_eight/wander (4-8) and sentry (2-3) separately
- **Files modified:** `test_aaa_combat_interiors.py`
- **Commit:** b00f4df

**4. [Rule 1 - Bug] `generate_encounter_zone_spec` center is 2-tuple**

- **Found during:** Task 2 test execution
- **Issue:** Tests passed `center=(0.0, 0.0, 0.0)` (3-tuple) but function signature is `center: tuple[float, float]`
- **Fix:** Changed test calls to `center=(0.0, 0.0)`
- **Files modified:** `test_aaa_combat_interiors.py`
- **Commit:** b00f4df

## Known Stubs

None. All spec functions return complete data structures. `worldbuilding.py` handler wiring for `handle_generate_castle` concentric ring data was completed in the prior session context and is committed.

## Self-Check: PASSED

All 6 items verified:
- FOUND: test_aaa_castle_settlement.py
- FOUND: test_aaa_combat_interiors.py
- FOUND: worldbuilding_layout.py
- FOUND: building_quality.py
- FOUND: commit 5bd1bc0 (Task 1 source)
- FOUND: commit b00f4df (Task 2 tests)
