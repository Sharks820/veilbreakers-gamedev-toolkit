---
phase: "55"
plan: "01"
subsystem: scatter-vegetation
tags: [scatter, vegetation, slope, gradient, bugfix]
dependency_graph:
  requires: [_scatter_engine, vegetation_system, terrain_vegetation_depth]
  provides: [fixed-prop-scatter, category-slope-filtering, per-type-gradient-alignment]
  affects: [environment_scatter, _scatter_pass]
tech_stack:
  added: []
  patterns: [category-aware-slope, per-type-alignment-factors]
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_scatter_fixes.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py
decisions:
  - Rocks get 0.0 slope alignment (sit flat), trees 0.25-0.35, grass 0.85
  - Prop scatter auto-detects terrain by name when terrain_name not provided
  - Slope thresholds sourced from vegetation_system._max_slope_for_category
metrics:
  duration_seconds: 1003
  completed: "2026-04-12T13:09:30Z"
  tasks_completed: 4
  tasks_total: 4
  tests_added: 60
  tests_passing: 60
---

# Phase 55 Plan 01: Scatter, Slope Filtering, and Gradient Wiring Summary

Fixed three prop scatter bugs, wired category-aware slope filtering into _scatter_pass, added per-vegetation-type gradient alignment factors, and wrote 60 comprehensive tests covering scatter engine, vegetation depth, and alignment.

## Completed Tasks

| Task | Description | Commit | Key Changes |
|------|------------|--------|-------------|
| 1 | Fix prop scatter terrain lookup | 8d57097 | Added terrain_name param with auto-detect fallback |
| 2 | Wire category-aware slope filtering | 8d57097 | Replaced hardcoded 30/35/40 with _max_slope_for_category |
| 3 | Per-type gradient alignment | 8d57097 | Added _SLOPE_ALIGNMENT_FACTORS dict and _slope_alignment_factor() |
| 4 | Comprehensive test suite | 1368486 | 60 tests across 15 test classes |

## Bug Fixes

### 1. Prop Scatter Terrain Lookup (Critical)

**Bug:** `handle_scatter_props` called `_terrain_height_sampler(bpy.data.objects.get(area_name))` where `area_name` defaults to "PropScatter" -- the output collection name, not the terrain object. This meant the height sampler was always None and all props were placed at z=0.

**Fix:** Added `terrain_name` parameter. When omitted, auto-detects by scanning `bpy.data.objects` for the first MESH with "terrain" in its name. Falls back to z=0 if no terrain found.

**Files:** `environment_scatter.py` (handle_scatter_props)

### 2. Hardcoded Slope Thresholds in _scatter_pass

**Bug:** `_scatter_pass` used hardcoded slope limits: trees at 30 degrees, bushes at 35, grass at 40. These were inconsistent with the category-aware system in `vegetation_system.py` (trees=45, ground_cover=55, rocks=75).

**Fix:** Imported `_max_slope_for_category` from `vegetation_system` and replaced all three hardcoded thresholds. The import was moved to function top-level to avoid UnboundLocalError across pass branches.

**Files:** `environment_scatter.py` (_scatter_pass)

### 3. Per-Type Gradient Alignment

**Bug:** All vegetation types used a hardcoded 0.7 slope alignment factor. This meant rocks tilted 70% to follow terrain slope (should sit flat), and grass only tilted 70% (should follow terrain closely at 85%).

**Fix:** Added `_SLOPE_ALIGNMENT_FACTORS` dict mapping 18 vegetation types to alignment values:
- Rocks: 0.0 (perfectly flat)
- Trees: 0.25-0.35 (mostly upright, slight lean)
- Bushes/shrubs: 0.4-0.5 (moderate follow)
- Grass/weeds: 0.85 (close terrain follow)
- Fallen logs: 0.9 (near-full alignment)
- Mushrooms: 0.1 (nearly upright)
- Unknown types: 0.5 (midrange default)

**Files:** `environment_scatter.py` (_slope_alignment_factor, _SLOPE_ALIGNMENT_FACTORS)

## Tests Added

60 tests in `test_scatter_fixes.py` across 15 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestSlopeCategoryThresholds | 6 | Category slope limit values and ordering |
| TestSlopeAlignmentFactors | 13 | Per-type factors, ranges, ordering |
| TestBiomeFilterSlopeRejection | 3 | Max tilt rejection, flat acceptance, per-rule slope |
| TestMoistureMapFiltering | 2 | Wet/dry rule filtering |
| TestScatterPassSlopeConsistency | 4 | Category thresholds in _scatter_pass |
| TestVegetationDepthLayers | 4 | 4-layer computation, range, biome variants |
| TestDisturbancePatches | 2 | Determinism and bounds |
| TestEdgeEffects | 2 | Boundary boost and cultivation suppression |
| TestAllelopathicExclusion | 1 | Species suppression |
| TestPoissonDiskSampling | 5 | Min distance, bounds, determinism |
| TestContextScatter | 2 | Building exclusion, affinity props |
| TestBreakableVariants | 7 | All prop types, material darkening, invalid type |
| TestVegetationPlacement | 4 | Flat/steep terrain, all biomes, exclusion zones |
| TestWindVertexColors | 2 | RGB range, height-based sway |
| TestClearings | 2 | Determinism and no-overlap |
| TestFallenLogs | 2 | Forest mask and empty forest |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None found. All functions are fully wired with real logic.

## Self-Check: PASSED

- [x] `environment_scatter.py` modified with 3 bug fixes
- [x] `test_scatter_fixes.py` created with 60 tests
- [x] Commit 8d57097 exists (bug fixes)
- [x] Commit 1368486 exists (tests)
- [x] Full test suite: 21,306 passed (17 pre-existing failures in unrelated animal mesh tests)
