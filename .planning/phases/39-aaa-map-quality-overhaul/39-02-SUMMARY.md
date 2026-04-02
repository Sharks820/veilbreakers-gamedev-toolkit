---
phase: 39-aaa-map-quality-overhaul
plan: "02"
subsystem: worldbuilding
tags: [vegetation, scatter, terrain-noise, water, bmesh, vertex-colors, ridged-multifractal, auto-splatting, leaf-cards, grass-cards]

requires:
  - phase: 39-01
    provides: foundation quality systems (mesh bridge, scatter engine, terrain erosion)

provides:
  - Leaf card tree canopies (6-12 intersecting planes, wind RGBA vertex colors)
  - 6-biome grass card system with V-bend geometry and wind_vc layer
  - Multi-pass vegetation scatter (trees->grass->rocks) with building exclusion AABBs
  - Combat clearing generator (15-40m diameter, 2-4 entry paths, tree ring)
  - Rock power-law size distribution (70% small / 25% medium / 5% large)
  - Spline-based water mesh following path_points with 8-16 cross-sections
  - Flow vertex colors on loop layer (RGBA: speed/dir_x/dir_z/foam)
  - Shore alpha gradient; AAA water material (IOR 1.333, roughness 0.05, alpha 0.6)
  - Ridged multifractal noise (Musgrave 1994) with noise_type routing
  - Auto-splatting 5-layer system (grass/rock/cliff/snow/mud) driven by slope/height/curvature/moisture
  - 81 passing tests (47 terrain+vegetation, 34 water+splat)

affects: [39-03, 39-04, environment_scatter, environment, _terrain_noise, handle_scatter_vegetation, handle_create_water]

tech-stack:
  added: []
  patterns:
    - "Leaf card canopy: 3 vertical planes at 0/60/120deg + angled planes, all share wind_vc layer"
    - "Wind RGBA convention: R=flutter(0-1 base-to-tip), G=per-cluster phase, B=branch sway, A=trunk sway"
    - "Multi-pass scatter: Pass 1=structure, Pass 2=ground_cover, Pass 3=debris, all exclude building AABBs"
    - "Spline water mesh: cross-section rings along path_points, fallback grid when no path given"
    - "Flow VC on loop layer not vert layer: bm.loops.layers.float_color.new('flow_vc')"
    - "Ridged multifractal: invert+square per octave, cascade weights (Musgrave 1994)"
    - "Curvature Laplacian sign: convex peak = negative (center > neighbors), concave = positive"
    - "Test stub fix: force sys.modules['bpy'] = stub (not setdefault) to override conftest bare module"

key-files:
  created:
    - Tools/mcp-toolkit/tests/test_aaa_terrain_vegetation.py
    - Tools/mcp-toolkit/tests/test_aaa_water_scatter.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py

key-decisions:
  - "Loop-layer flow vertex colors (bm.loops) instead of vert-layer: enables per-face-corner foam/shore data"
  - "noise_type param routes to perlin/ridged/hybrid; ValueError on unknown type rather than silent fallback"
  - "auto_splat_terrain curvature from discrete 3x3 Laplacian; convex peak = negative value (corrected sign)"
  - "Force-install bpy stub (sys.modules assignment) not setdefault to prevent conftest bare module winning"

patterns-established:
  - "Biome grass specs in _GRASS_BIOME_SPECS dict: height_min/max/color per biome key"
  - "Rock power-law: random() < 0.70 -> small, < 0.95 -> medium, else large; returns (scale_m, size_class)"
  - "Combat clearing: center + radius, entry_points list, tree_positions list, cleared_area_m2"

requirements-completed: [AAA-MAP-02, AAA-MAP-07, AAA-MAP-08, AAA-MAP-09]

duration: ~55min
completed: 2026-04-02
---

# Phase 39 Plan 02: AAA Terrain, Vegetation & Water Systems Summary

**Replaced UV sphere tree blobs with 6-12-plane leaf card canopies, added 6-biome grass card scatter, spline water mesh with flow vertex colors, ridged multifractal terrain noise, and 5-layer auto-splatting — 81 tests all passing.**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-04-02T00:53:05Z
- **Tasks:** 2/2
- **Files modified:** 5 (3 handlers + 2 new test files)

## Accomplishments

### Task 1: Vegetation scatter overhaul (commit a0af48a)

- `create_leaf_card_tree`: trunk (6-sided tapered cylinder) + `_add_leaf_card_canopy` (3 vertical planes at 0/60/120 deg + angled planes at 30-45 deg elevation). `num_planes` clamped to [6,12].
- Wind RGBA vertex colors on all geometry: R=flutter, G=cluster phase, B=branch sway, A=trunk sway.
- `_create_grass_card`: 2 crossing V-bent quads, `wind_vc` loop layer, 6 biome variants via `_GRASS_BIOME_SPECS`.
- `_rock_size_from_power_law`: 70/25/5 distribution returning `(scale_m, size_class)`.
- `_generate_combat_clearing`: 15-40m diameter, `num_entries` (2-4) evenly-spaced path gaps in tree ring, returns dict with `entry_points`, `tree_positions`, `cleared_area_m2`.
- `_scatter_pass`: three pass types (`structure`, `ground_cover`, `debris`), all respect building exclusion AABBs, returns `list[dict]` with `"position"` key.

### Task 2: Water, noise, and auto-splatting (commit 1ef4ff5)

- `handle_create_water`: spline mesh following `path_points` (cross-sections clamped to [8,16], default 12); fallback axis-aligned grid when no path. Returns `has_flow_vertex_colors: True`, `has_shore_alpha: True`, `cross_sections`, `path_point_count`.
- Flow VC on `bm.loops.layers.float_color` (loop layer, not vert layer): each face-corner stores `(flow_speed, flow_dir_x, flow_dir_z, foam)`.
- AAA water material: `Base Color = linear(0.021, 0.046, 0.031)`, `Roughness = 0.05`, `Alpha = 0.6`, `IOR = 1.333`, `Transmission Weight = 1.0`.
- `ridged_multifractal(x, y, ...)` scalar + `ridged_multifractal_array` vectorized + `generate_heightmap_ridged` 2D — all normalized [0,1].
- `generate_heightmap_with_noise_type(noise_type=...)`: routes `"perlin"` / `"ridged_multifractal"` / `"hybrid"` (blend_ratio); raises `ValueError` for unknown type.
- `auto_splat_terrain`: 5-layer splat driven by slope/height/curvature(Laplacian)/moisture; curvature adjusts roughness ±0.15/0.20; weights summed to 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Curvature Laplacian sign inverted in roughness adjustment**
- **Found during:** Task 2 — `test_convex_peak_is_smoother_than_flat` failed
- **Issue:** Discrete Laplacian of a convex peak is **negative** (center > neighbors), but roughness_adj applied `-0.15` when `curvature > 0.1` (positive). Result: peaks were assigned +0.20 roughness instead of -0.15.
- **Fix:** Swapped condition — `curvature < -0.1` → `-0.15` (convex smoother), `curvature > 0.1` → `+0.20` (concave rougher).
- **Files modified:** `blender_addon/handlers/_terrain_noise.py`
- **Commit:** 1ef4ff5 (included in Task 2 commit)

**2. [Rule 1 - Bug] Test bpy stub overridden by conftest bare ModuleType**
- **Found during:** Task 2 test run — `obj.name` returned MagicMock instead of string
- **Issue:** `conftest.py` installs a bare `types.ModuleType("bpy")` before test module runs; `sys.modules.setdefault(...)` in test file was a no-op, so `scatter_mod` got the bare module.
- **Fix:** Changed `sys.modules.setdefault("bpy", bpy_stub)` to `sys.modules["bpy"] = bpy_stub` (forced assignment) in `test_aaa_terrain_vegetation.py`.
- **Files modified:** `tests/test_aaa_terrain_vegetation.py`
- **Commit:** 1ef4ff5

**3. [Rule 1 - Bug] `to_mesh` stub didn't populate `mesh.vertices`**
- **Found during:** Task 2 — `test_vertex_count_positive` returned 0
- **Issue:** `_BMesh.to_mesh()` in water test stub populated `mesh.polygons` but not `mesh.vertices`, so `len(mesh.vertices)` = 0.
- **Fix:** Added `mesh.vertices = list(self._verts)` in `to_mesh`.
- **Files modified:** `tests/test_aaa_water_scatter.py`
- **Commit:** 1ef4ff5

## Self-Check: PASSED

All files found on disk. Both commits (a0af48a, 1ef4ff5) confirmed in git log. 81 tests passing.
