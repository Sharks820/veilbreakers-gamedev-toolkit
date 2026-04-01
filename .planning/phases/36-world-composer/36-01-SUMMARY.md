---
phase: 36
plan: 01
subsystem: world-composer
tags: [settlement, grammar, road-network, districts, lots, props, medieval-town]
dependency_graph:
  requires: [_building_grammar.py, _terrain_grammar.py, asset_pipeline.py, road_network.py]
  provides: [_settlement_grammar.py, generate_concentric_districts, medieval_town settlement type]
  affects: [settlement_generator.py, road_network.py, blender_worldbuilding handler]
tech_stack:
  added: [numpy PCA for OBB lot subdivision, Kruskal inline MST, Poisson-disk prop placement]
  patterns: [pure-grammar no-bpy module, concentric ring zoning, OBB recursive split, corruption tier scaling]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_settlement_grammar.py
    - Tools/mcp-toolkit/tests/test_settlement_grammar.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/road_network.py
    - Tools/mcp-toolkit/blender_addon/handlers/settlement_generator.py
    - Tools/mcp-toolkit/tests/test_settlement_generator.py
decisions:
  - "Inline Kruskal MST in _settlement_grammar.py to keep grammar pure (no cross-handler imports)"
  - "veil_pressure added as explicit param to generate_settlement() instead of **kwargs"
  - "prop position stored as 3-tuple in grammar; settlement_generator unpacks x,y by index"
  - "Block polygons formed as triangular wedges (center + 2 anchor points) for simple OBB recursion"
metrics:
  duration_minutes: ~90
  tasks_completed: 5
  files_created: 2
  files_modified: 3
  tests_added: 42
  tests_passing: 201
  completed_date: "2026-04-01"
---

# Phase 36 Plan 01: Settlement Grammar Data Layer Summary

**One-liner:** Pure-logic `_settlement_grammar.py` implementing concentric ring districts, organic L-system MST roads, OBB lot subdivision with PCA, corruption-scaled prop manifests, and full `medieval_town` wiring into `settlement_generator.py`.

## What Was Built

### `_settlement_grammar.py` (689 lines, no bpy)

8 public functions implementing the complete data layer:

| Function | Purpose |
|---|---|
| `ring_for_position(pos, center, radius)` | Concentric zone lookup (market_square→outskirts) |
| `weighted_building_type(district, neighbor, dist_boundary, seed)` | 30% boundary blending |
| `perturb_road_points(start, end, rng, amplitude, steps)` | L-system perpendicular noise |
| `generate_road_network_organic(center, radius, seed, points)` | Inline Kruskal MST + branch alleys |
| `subdivide_block_to_lots(block_polygon, district, seed)` | Recursive OBB split via numpy PCA |
| `assign_buildings_to_lots(lots, center, radius, veil_pressure, seed)` | District fill rates + building types |
| `prop_tier_for_pressure(pressure)` | Maps veil_pressure → (band, spacing_min, spacing_max) |
| `generate_prop_manifest(road_segments, center, radius, veil_pressure, seed)` | Poisson-disk-like prop list with Tripo cache keys |

Constants locked from decisions D-01 to D-10:
- `RING_THRESHOLDS`: 5 zones (market 0.15r → outskirts 1.01r)
- `DISTRICT_FILL_RATES`: market 100%, residential 80%, outskirts 60%
- `CORRUPTION_TIERS`: pristine 3-5m, weathered 5-8m, damaged 8-15m, corrupted 15-50m
- `ROAD_PROP_TYPES`: per-district prop type lists for Tripo manifest

### `road_network.py` — Curb Geometry Extension

Added `_road_segment_mesh_spec_with_curbs(start, end, width, curb_height=0.15, gutter_width=0.3)`:
- 6-column cross-section: outer-left gutter, curb-top-left, inner road (×2), curb-top-right, outer-right gutter
- 5 quad strips per segment step covering gutter + curb + road surface
- 2 UV layers: `road_surface` (full span V) and `curb` (curb face height V)
- `compute_road_network()` now dispatches main/cobblestone to curb mesh, paths/trails to flat strip

### `settlement_generator.py` — `medieval_town` Integration

- Imported 5 grammar functions at top of file
- Added `"medieval_town"` to `SETTLEMENT_TYPES` (40-80 buildings, cobblestone, `concentric_organic` layout, radius 150)
- Added `veil_pressure: float = 0.0` param to `generate_settlement()`
- Added `generate_concentric_districts(center, radius, seed, veil_pressure, heightmap, wall_height)` (~200 lines): full pipeline from anchor point placement → organic roads → OBB lots → building assignment → prop manifest → perimeter walls → interior furnishing
- Dispatch block in `generate_settlement()` routes `concentric_organic` to new function, returns standard output dict

### `test_settlement_grammar.py` (630 lines, 38 tests)

8 test classes: TestConstants, TestRingDistrictAssignment, TestPropTierForPressure, TestWeightedBuildingType, TestOBBLotSubdivision, TestAssignBuildingsToLots, TestGeneratePropManifest, TestGenerateRoadNetworkOrganic, TestRoadCurbGeometry — all 38 pass.

### `test_settlement_generator.py` — 2 new tests

- `test_medieval_town_generates_roads`: verifies roads, buildings, district field, determinism
- `test_medieval_town_veil_pressure_scales_props`: verifies high pressure produces fewer props

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] prop position 3-tuple unpack**
- **Found during:** Task 5 integration testing
- **Issue:** `generate_prop_manifest` returns positions as `(x, y, z)` tuples but `generate_concentric_districts` tried `px, py = pm["position"]`
- **Fix:** Changed to `px, py = pos[0], pos[1]` to handle both 2- and 3-tuple positions
- **Files modified:** `settlement_generator.py`
- **Commit:** included in c629962

### Workflow Note

Tasks 1-4 were implemented as a single write (full implementation rather than stubs-first) since all logic was well-specified in the plan. This produced cleaner commits. Task 5 changes were auto-merged into the Wave 2 agent's commit `c629962`.

## Known Stubs

None — all grammar functions are fully implemented. Prop manifest entries include `cache_key` for Tripo materialization in Plan 02; the manifest itself is the stub boundary (data layer complete, Tripo calls are Plan 02 scope by design).

## Self-Check: PASSED

Files exist:
- `Tools/mcp-toolkit/blender_addon/handlers/_settlement_grammar.py` — FOUND
- `Tools/mcp-toolkit/tests/test_settlement_grammar.py` — FOUND
- `_road_segment_mesh_spec_with_curbs` in `road_network.py` — FOUND (line ~420)
- `medieval_town` in `SETTLEMENT_TYPES` — FOUND (line 181)
- `generate_concentric_districts` in `settlement_generator.py` — FOUND (line 2078)

Commits:
- `c2ad8e4` feat(36-01): add settlement grammar, 38 tests, and curb road geometry — FOUND
- `c629962` feat(36): merge settlement grammar updates + phase 34 summary — FOUND

Tests: 201 passed (settlement grammar + settlement generator), 57 pre-existing failures unchanged.
