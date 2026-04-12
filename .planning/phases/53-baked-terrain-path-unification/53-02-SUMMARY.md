---
phase: 53-baked-terrain-path-unification
plan: 02
subsystem: terrain
tags: [bugfix, geological-generators, legacy-fixes]
dependency_graph:
  requires: [53-01]
  provides: [geological-generators, parse-bool, cleanup-on-exception]
  affects: [environment.py, terrain_features.py, terrain_morphology.py]
tech_stack:
  added: []
  patterns: [_parse_bool-for-string-booleans, try-finally-cleanup, curvature-weighted-wetness]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_legacy_fixes.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_morphology.py
decisions:
  - "F141 (warp params) already configurable -- no change needed"
  - "F146 (seed in preset merge) already correct -- presets use seed=None"
  - "F147 (heightmap erosion disable) subsumed by Wave 1 BakedTerrain"
metrics:
  duration_seconds: 1081
  completed: 2026-04-12T12:30:53Z
  tasks_completed: 7
  tasks_total: 7
  tests_added: 50
  files_modified: 4
  files_created: 1
---

# Phase 53 Plan 02: Round 3 Legacy Fixes + Geological Generators Summary

Fix F139-F153 Round 3 legacy path bugs and implement 7 geological generators with curvature-weighted wetness

## Commits

| Task | Commit  | Description |
|------|---------|-------------|
| 1    | 2e3f9ef | F150: try/finally cleanup in handle_run_terrain_pass |
| 2    | 68ee255 | F152: _parse_bool replaces bool() for string booleans |
| 3    | dabaa97 | F140: erosion iterations caller-controllable |
| 4    | a02fc2e | F143/F144: flatten_zones after moisture, unconditional moisture |
| 5    | e6d4551 | F141-F153 batch: terrain_size separation, single erosion call, registrar logging |
| 6    | ad35fef | 7 geological generators (caldera, basalt, fan, cirque, strata, debris, wetness) |
| 7    | 16246bf | 50 tests covering all fixes and generators |

## Bug Fixes (F139-F153)

| Finding | Status | Resolution |
|---------|--------|------------|
| F139    | Subsumed | BakedTerrain (Wave 1) eliminates legacy path |
| F140    | Fixed | Caller-controllable erosion iterations, no auto-escalation when explicit |
| F141    | Already fixed | warp_strength/warp_scale already read from params |
| F142    | Fixed | terrain_size param separated from noise scale |
| F143    | Fixed | flatten_zones reordered AFTER moisture map in both handlers |
| F144    | Fixed | Moisture computed unconditionally (not gated by erosion_applied) |
| F145    | Subsumed | BakedTerrain (Wave 1) |
| F146    | Already correct | Preset seed=None, caller seed preserved in merge |
| F147    | Subsumed | BakedTerrain pass-through handles caller heightmaps |
| F148    | Fixed | Single erode_world_heightmap call for erosion="both" |
| F149    | Fixed | flatten_zones now runs after erosion_margin crop |
| F150    | Fixed | try/finally cleanup of leaked bpy meshes/objects on exception |
| F151    | Fixed | register_all_terrain_passes return value logged, missing passes warned |
| F152    | Fixed | _parse_bool helper handles string "false"/"true" correctly |
| F153    | Fixed | Single _estimate_tile_height_range path, no divergence |

## Geological Generators

| Generator | File | Geometry |
|-----------|------|----------|
| Volcanic caldera | terrain_features.py | Ring mesh with crater profile, lava pool disc, noise-perturbed rim |
| Columnar basalt | terrain_features.py | Hexagonal prism cluster, varying heights/radii |
| Alluvial fan | terrain_features.py | Fan-shaped heightfield with braided channel incisions |
| Glacial cirque | terrain_features.py | Half-bowl with steep headwall, optional tarn |
| Cliff stratigraphy | terrain_features.py | Layered cliff face, hardness-based protrusion |
| Debris cone | terrain_features.py | Conical talus mound with boulder scatter data |
| Curvature-weighted wetness | terrain_morphology.py | Laplacian curvature + moisture blending |

## Test Results

- 50 new tests added (all passing)
- Full suite: 21296 passed, 17 failed (pre-existing animal metadata), 2 skipped
- No regressions introduced

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- all generators produce real geometry with vertices, faces, and materials.

## Self-Check: PASSED

All 4 files found. All 7 commits verified.
