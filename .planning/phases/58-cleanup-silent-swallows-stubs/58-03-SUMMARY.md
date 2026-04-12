---
phase: "58"
plan: "03"
subsystem: "generators-geology"
tags: [z-up, settlement, dungeon, geology, biome, silent-swallow]
dependency_graph:
  requires: [58-01, 58-02]
  provides: [geology-generators, terrain-height-fn, dungeon-worldspace]
  affects: [_dungeon_gen, _settlement_grammar, _biome_grammar, _mesh_bridge]
tech_stack:
  added: []
  patterns: [height-callback, grid-to-worldspace-conversion, pure-numpy-geology]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_generators_58_03.py
    - Tools/mcp-toolkit/tests/test_geology_gaps_58_03.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py
    - Tools/mcp-toolkit/blender_addon/handlers/_settlement_grammar.py
    - Tools/mcp-toolkit/blender_addon/handlers/_biome_grammar.py
    - Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py
decisions:
  - "Pure numpy for all geology generators -- no scipy dependency"
  - "HeightFn callback pattern for terrain-aware Z in settlement/road code"
  - "Dungeon props use _world() helper for grid-to-Blender conversion"
metrics:
  duration_seconds: 476
  completed: "2026-04-12T14:52:52Z"
  tasks_completed: 4
  tasks_total: 4
  tests_added: 59
  tests_total_passing: 564
---

# Phase 58 Plan 03: Clusters L-P (Generators + Geology Gaps) Summary

Non-terrain generators fixed for Blender Z-up world-space; settlement roads and props terrain-aware via height callback; 8 geology feature generators added to biome grammar; silent swallow in mesh bridge replaced with logging.

## Completed Tasks

| Task | Description | Commit | Key Files |
|------|-------------|--------|-----------|
| 1 | Dungeon prop Z-up + mesh_bridge logging | b9410bb | _dungeon_gen.py, _mesh_bridge.py |
| 2 | Settlement height_fn terrain-aware Z | 0663a92 | _settlement_grammar.py |
| 3 | 8 geology gap generators | abc2f21 | _biome_grammar.py |
| 4 | 59 tests + scipy removal | 3f7a4fe | test_generators_58_03.py, test_geology_gaps_58_03.py |

## Changes Detail

### Dungeon Generator Z-Up Fix (Task 1)
- `generate_dungeon_prop_placements` now accepts `cell_size` and `floor_z` parameters
- Internal `_world(gx, gy, z_off)` helper converts grid coordinates to Blender world-space
- All prop positions multiplied by cell_size for X/Y, offset by floor_z for Z
- Torch sconces get 1.8m Z offset for wall-mount height
- Backward compatible: defaults match previous behavior (cell_size=2.0, floor_z=0.0)

### Mesh Bridge Silent Swallow Fix (Task 1)
- Line 963: replaced `except (ValueError, IndexError): pass` with debug-level logging
- Degenerate/duplicate face indices now logged for diagnostic visibility

### Settlement Grammar Height Callback (Task 2)
- Added `HeightFn = Optional[Callable[[float, float], float]]` type alias
- Added `_z_at(x, y, height_fn)` helper returning terrain Z or 0.0
- `generate_road_network_organic`: all waypoints sample terrain height via callback
- `generate_prop_manifest`: prop Z positions use terrain height instead of hardcoded 0.0
- Both functions backward compatible (height_fn=None defaults to flat ground)

### Geology Gap Generators (Task 3)
Eight pure-numpy heightmap processors added to `_biome_grammar.py`:
1. **apply_periglacial_patterns** -- Voronoi-cell frost heave polygon micro-relief
2. **apply_desert_pavement** -- flat/low-area smoothing + material mask (reg surface)
3. **compute_spring_line_mask** -- geological layer boundary water emergence points
4. **apply_landslide_scars** -- concave scar excavation + convex runout deposit fan
5. **apply_hot_spring_features** -- pool depression + travertine terrace rings + VFX info
6. **apply_reef_platform** -- fringing reef at coastline via distance transform
7. **apply_tafoni_weathering** -- honeycomb erosion pits on steep rock faces
8. **apply_geological_folds** -- anticline/syncline/chevron tectonic folding

### Infrastructure Fixes (Task 4)
- Replaced deprecated `ndarray.ptp()` with `(arr.max() - arr.min())` in all geology code
- Replaced scipy.ndimage dependencies with pure-numpy implementations:
  - `_box_filter_2d`: cumulative-sum based uniform filter
  - `_distance_from_mask`: two-pass Manhattan distance transform

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] scipy not available in test environment**
- Found during: Task 4 (test execution)
- Issue: `apply_desert_pavement` and `apply_reef_platform` imported scipy.ndimage
- Fix: Replaced with pure-numpy `_box_filter_2d` and `_distance_from_mask`
- Files modified: _biome_grammar.py

**2. [Rule 1 - Bug] numpy .ptp() deprecated/removed**
- Found during: Task 4 (test execution)
- Issue: `ndarray.ptp()` removed in newer numpy versions
- Fix: Replaced 4 occurrences with explicit `(arr.max() - arr.min())`
- Files modified: _biome_grammar.py

## Verification

- 564 tests pass across all exclusive files (505 existing + 59 new)
- All 8 geology generators: correct shape, modifies terrain, deterministic, handles edge cases
- Dungeon props: world-space scaled, floor_z offset works, backward compatible
- Settlement: height_fn wires through to road waypoints and prop positions
- Mesh bridge: logging confirmed via source inspection

## Self-Check: PASSED

All 6 key files exist on disk. All 4 commit hashes verified in git log.
