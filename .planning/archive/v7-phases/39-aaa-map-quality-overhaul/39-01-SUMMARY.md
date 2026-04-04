---
phase: 39-aaa-map-quality-overhaul
plan: 01
subsystem: visual-quality
tags: [aaa-verification, pbr-pipeline, battlements, wear-maps, curvature-roughness, regression-testing]
dependency_graph:
  requires: []
  provides:
    - aaa_verify_map (visual_validation.py)
    - capture_regression_baseline (screenshot_diff.py)
    - aaa_verify action (blender_server.py asset_pipeline)
    - screenshot_regression action (blender_server.py asset_pipeline)
    - apply_curvature_roughness (mesh_enhance.py)
    - generate_battlements wired into handle_generate_castle
    - handle_generate_wear_map wired into handle_generate_settlement
  affects:
    - blender_server.py asset_pipeline tool
    - handle_generate_castle (worldbuilding.py)
    - handle_generate_settlement (worldbuilding.py)
    - mesh_enhance.py PBR pipeline
tech_stack:
  added: []
  patterns:
    - Multi-angle AAA scoring with floating-geometry and default-material detection
    - PBR curvature-to-roughness: convex -0.15, concave +0.20 delta
    - Building-type wear age mapping (tavern/residential/military/religious/slums ranges)
    - Screenshot regression baseline capture and pixel-level diff
key_files:
  created:
    - Tools/mcp-toolkit/tests/test_aaa_visual_verification.py
    - Tools/mcp-toolkit/tests/test_aaa_foundation_wiring.py
  modified:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/screenshot_diff.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py
    - Tools/mcp-toolkit/blender_addon/handlers/mesh_enhance.py
    - Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py
decisions:
  - aaa_verify action renders 10 angles via Blender commands then calls aaa_verify_map() for scoring
  - floating_geometry_suspected: bottom 20% mean brightness > 200 threshold
  - default_material_detected: avg std_dev < 8.0 across all RGB channels
  - apply_curvature_roughness returns computed adjustments even when bpy unavailable (safe for tests)
  - wear map age assigned per building object found in bpy.data.objects with fallback to debug-log skip
  - generate_battlements wired non-fatally (try/except) so castle generation never fails on battlement error
  - blender_quality module does not exist as a handlers module; test updated to use building_quality
metrics:
  duration: ~8 minutes
  completed: "2026-04-02T00:37:40Z"
  tasks_completed: 2
  tests_added: 50
  files_modified: 5
  files_created: 2
---

# Phase 39 Plan 01: AAA Foundation Quality Systems Summary

**One-liner:** Multi-angle AAA verification scoring + PBR curvature-roughness pipeline + castle battlements wiring + settlement wear maps, all validated by 50 new tests.

## What Was Built

### Task 1: AAA Verification Protocol + Quality Detection Systems

**`aaa_verify_map()` in `visual_validation.py`:**
- Accepts up to 10 screenshot paths (one per camera angle)
- Calls `analyze_render_image()` on each and adds two AAA-specific quality checks:
  - **Floating geometry detection**: bottom 20% mean brightness > 200 flags `floating_geometry_suspected`
  - **Default material detection**: avg RGB std_dev < 8.0 flags `default_material_detected`
- Returns `{passed, total_score, per_angle, failed_angles}` — an angle fails if score < min_score OR either AAA flag is set

**`capture_regression_baseline()` in `screenshot_diff.py`:**
- Copies screenshots to `baseline_dir/baseline_{angle_id}.png`
- Returns `{baseline_count, baseline_dir, paths}`

**`aaa_verify` action in `blender_server.py` `asset_pipeline`:**
- Params: `angles` (default 10), `min_score` (default 60), `capture_baseline` (default False)
- Renders 10 camera angles (front/back/left/right/top/NE/NW/SW/SE/ground-level)
- Calls `aaa_verify_map()` on collected screenshots
- Optionally runs `capture_regression_baseline()` if `capture_baseline=True`

**`screenshot_regression` action:**
- Params: `baseline_dir`, `current_screenshots`
- Calls `compare_screenshots()` per angle pair with 1% threshold
- Returns `{all_match, results, total_angles, passed_angles}`

### Task 2: PBR Pipelines + Castle Battlements + Quality Tests

**`apply_curvature_roughness()` in `mesh_enhance.py`:**
- Calls `handle_bake_curvature_map()` to get convex/concave curvature values
- Applies research-spec adjustments: convex edges `base - curvature * 0.15`, concave cavities `base + curvature * 0.20`
- When bpy available: wires a ColorRamp node into the material's Principled BSDF Roughness input
- Returns `{applied, base_roughness, convex_adjustment, concave_adjustment, final_roughness_convex, final_roughness_concave}`

**Castle battlements wiring in `worldbuilding.py`:**
- `from .building_quality import generate_battlements` added at top
- `handle_generate_castle()` now calls `generate_battlements()` for all 4 wall sides after rampart placement
- Params: `wall_length=outer_size`, `wall_height`, `wall_thickness=1.5`, `merlon_style="squared"`, non-fatally wrapped

**Settlement wear map wiring in `worldbuilding.py`:**
- `from .texture import handle_generate_wear_map` added at top
- `handle_generate_settlement()` now applies wear map to each placed building mesh
- `_WEAR_AGE_BY_TYPE` dict maps building type → age range (0-1): tavern/shop (0.3-0.5), residential/house (0.2-0.4), military/barracks (0.4-0.6), religious (0.5-0.7), slums (0.6-0.8), ruin (0.7-0.9)
- Non-fatally wrapped with `debug` log skip when object not yet in scene

## Test Results

```
50 passed in 0.87s
```

- `test_aaa_visual_verification.py`: 27 tests — analyze_render_image, aaa_verify_map, regression baseline/comparison, curvature-roughness, wear age, battlements, wiring checks
- `test_aaa_foundation_wiring.py`: 23 tests — handler importability, source-level wiring assertions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `blender_quality` module does not exist**
- **Found during:** Task 2 test run
- **Issue:** Plan referenced `blender_quality` handler but no such module exists in `blender_addon/handlers/`. The smart_material capability is implemented across `building_quality.py` and other quality modules.
- **Fix:** Updated `test_smart_material_callable` to import `building_quality` instead — matches actual file structure.
- **Files modified:** `tests/test_aaa_foundation_wiring.py`
- **Commit:** 20ae896

## Self-Check: PASSED

Files verified:
- FOUND: Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_validation.py — contains `def aaa_verify_map`
- FOUND: Tools/mcp-toolkit/src/veilbreakers_mcp/shared/screenshot_diff.py — contains `def capture_regression_baseline`
- FOUND: Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py — contains `"aaa_verify"` action
- FOUND: Tools/mcp-toolkit/blender_addon/handlers/mesh_enhance.py — contains `def apply_curvature_roughness`
- FOUND: Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py — contains `generate_battlements(` call and `handle_generate_wear_map(`
- FOUND: Tests — 50/50 passing

Commits verified:
- 51579c6: feat(39-01): add aaa_verify_map, capture_regression_baseline, aaa_verify+screenshot_regression actions
- 20ae896: feat(39-01): wire battlements+wear maps+curvature-roughness pipeline + 50 tests
