---
phase: "33"
plan: "01"
subsystem: interior-system
status: complete
tags: [interior, furniture-placement, spatial-graphs, activity-zones, clutter, lighting, MESH-03]
dependency_graph:
  requires: [32-01]
  provides: [interior-layout, clutter-scatter, room-lighting]
  affects: [worldbuilding, building-grammar]
tech_stack:
  added: []
  patterns: [spatial-graph-placement, poisson-disk-scatter, constraint-solver, activity-zone-partitioning]
key_files:
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py
    - Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py
  created:
    - Tools/mcp-toolkit/tests/test_interior_system.py
decisions:
  - item_height parameter added to _check_collision and _door_corridor_clear so floor-level items (rugs, carpets) skip collision and walkable items are placed freely
  - _find_config_index hoisted above generate_interior_layout so spatial-graph placement phases can call it
  - Clutter fallback uses 1x1x1 cube when no FURNITURE_GENERATOR_MAP entry exists
  - Lighting color temperature approximated via linear RGB blend (2700K warm orange to 3500K cool white)
metrics:
  duration: "~2h (worktree execution)"
  completed: "2026-04-01"
  tasks: 5
  files_modified: 4
---

# Phase 33 Plan 01 Summary: Interior System

**One-liner:** Spatial-graph furniture placement, activity zones for 14 room types, Poisson disk clutter scatter, and 22-room-type lighting engine with color temperature — fully wired into worldbuilding.py handle_generate_interior.

## What Was Built

### Task 1 — Spatial Graphs + Constraint Solver (7779c36)

Added `ROOM_SPATIAL_GRAPHS` dict (1,561+ lines into `_building_grammar.py`) defining per-room-type furniture relationships as a graph:
- `focal_points`: primary items with wall preference (e.g. fireplace on north wall)
- `clusters`: items that orbit an anchor (chairs around a table, nightstand near bed)
- `wall_preferences`: per-item wall-side hints

Three-phase constraint solver inside `generate_interior_layout`:
1. Place focal points on preferred walls (20 attempts per wall)
2. Place clustered items relative to anchors (30 attempts per member)
3. Place remaining items by rule (wall/center/corner/row) with wall preferences

### Task 2 — Activity Zones for 14 Room Types (3b23d05)

Added `ROOM_ACTIVITY_ZONES` dict defining functional zone partitions per room (dining, sleeping, working, storage zones). Helper functions:
- `get_zone_for_item(room_type, item_type)` — maps item to its functional zone
- `get_zone_bounds(room_type, zone_name, width, depth)` — returns XY bounds for a zone
- `compute_zone_coverage(room_type)` — validates zone fractions sum ≤ 1.0

### Task 3 — Decorative Clutter Scatter with Poisson Disk (018837d)

Added `CLUTTER_POOLS` dict (12+ room types, 5-8 props each) and:
- `_poisson_disk_scatter_2d(width, depth, min_dist, count, rng)` — Bridson-style sampling
- `generate_clutter_layout(room_type, width, depth, layout, seed, density)` — places 5-15 props on furniture surfaces and floor, avoids furniture collision

24 clutter type mappings added to `FURNITURE_GENERATOR_MAP` in `_mesh_bridge.py` (mugs, books, pots, scrolls, coins, bones, tools, sacks, etc.).

### Task 4 — Lighting Placement Engine for 22 Room Types (5760299)

Added `LIGHTING_SCHEMAS` dict (all 22 room types) where each entry is a list of `(light_type, placement_rule, warm|neutral|cool)` tuples. Then `generate_lighting_layout` converts the schema into positioned lights with:
- Color temperature (2700K–3500K range, warm orange → cool white RGB approximation)
- Intensity and radius from light type (fireplace = 2.0, torch = 1.2, candle = 0.4...)
- Door-flanking torches, candles on table surfaces, ceiling lanterns at room center
- Returns list of dicts with `light_type`, `position`, `intensity`, `radius`, `color_temperature`, `emissive`

### Task 5 — 63 Integration Tests + Clutter Wiring (a4a7e0c)

Created `tests/test_interior_system.py` with 63 tests across 5 test classes:
- `TestRoomSpatialGraphs` — graph structure validation
- `TestSpatialPlacement` — chair-near-table, bed-near-nightstand, wall clearance, door corridor, no-overlap, determinism
- `TestActivityZones` — zone coverage ≥ 80%, zone bounds, item-to-zone mapping
- `TestClutterScatter` — Poisson disk bounds, count 5-15, density 0/1 edge cases, per-room pools
- `TestLightingPlacement` — 22 room type coverage, min 2 lights/room, temperature range, doorway torches, fireplace emissive
- `TestFullPipeline` — end-to-end for 6 room types + edge cases (tiny 3x3, huge 20x20, no furniture overlap)

Clutter and lighting fully wired into `worldbuilding.py` `handle_generate_interior` — both are generated and instantiated as Blender objects under the room's empty parent, tagged with `vb_room_type` and `vb_editable_role`.

## Key Files

- Modified: `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` (4,150 lines — added spatial graphs, activity zones, clutter, lighting)
- Modified: `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` (+82 lines — clutter + lighting wiring in handle_generate_interior)
- Modified: `Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py` (+24 lines — 24 clutter type mappings)
- Created: `Tools/mcp-toolkit/tests/test_interior_system.py` (669 lines, 63 tests)

## Test Results

```
tests/test_interior_system.py          63 passed
tests/test_building_grammar.py        (part of 121 total with interior_binding)
tests/test_building_interior_binding.py

Total: 184 passed, 0 failed (0.84s)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] item_height-aware collision for floor items**
- **Found during:** Merge conflict resolution (Task 5)
- **Issue:** `_check_collision` and `_door_corridor_clear` in the worktree version added `item_height` parameter so rugs/carpets (height < 0.1m) skip collision checks (walkable surfaces). HEAD lacked this parameter.
- **Fix:** Accepted worktree version in full for `_building_grammar.py`, retaining the `item_height` improvements across all 3 conflict sites.
- **Files modified:** `_building_grammar.py`
- **Commit:** `478ba99` (merge commit)

**2. [Rule 1 - Bug] _find_config_index position in file**
- **Found during:** Merge conflict resolution
- **Issue:** HEAD defined `_find_config_index` after `generate_interior_layout`, but the spatial-graph placement phases call it during execution. The worktree hoisted it before the function.
- **Fix:** Accepted worktree version which places `_find_config_index` before `generate_interior_layout` (at line 3619).
- **Commit:** `478ba99`

## Known Stubs

None — all clutter and lighting types are either wired to real generator functions or use a documented cube fallback. The fallback is intentional (some prop types like `food_scrap`, `spilled_drink` have no dedicated generator yet) and does not block the plan's goal.

## Self-Check: PASSED

- `tests/test_interior_system.py` — EXISTS, 63 tests pass
- `_building_grammar.py` — FOUND (4,150 lines)
- `worldbuilding.py` — FOUND, clutter + lighting wired
- `_mesh_bridge.py` — FOUND, 24 clutter mappings added
- Commits `7779c36`, `3b23d05`, `018837d`, `5760299`, `a4a7e0c`, `478ba99` — all exist in git log
