---
phase: "56"
plan: "01"
subsystem: "terrain-materials"
tags: [materials, pbr, triplanar, splatmap, displacement, smoothstep]
dependency_graph:
  requires: [terrain_materials_v2, terrain_semantics, terrain_pipeline]
  provides: [unified-material-engine, pbr-terrain-shader, triplanar-projection, dag-splatmap-bridge]
  affects: [terrain_materials, terrain_materials_v2, terrain_materials_ext]
tech_stack:
  added: [triplanar-projection-node-group, pbr-layer-builder, dag-to-rgba-bridge]
  patterns: [smoothstep-delegation, v2-weight-engine, height-blend-shader]
key_files:
  created: []
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_materials_v2.py
    - Tools/mcp-toolkit/tests/test_terrain_materials.py
    - Tools/mcp-toolkit/tests/test_terrain_materials_v2.py
    - Tools/mcp-toolkit/tests/test_environment_handlers.py
decisions:
  - "Map 5-channel v2 weights to 4-channel RGBA: ground->R, scree->G, cliff->B, wet_rock+snow->A"
  - "Cliff and slope layers auto-enable triplanar projection"
  - "Roughness variation via noise-driven MapRange per layer instead of flat values"
metrics:
  duration_seconds: 867
  completed: "2026-04-12T13:31:08Z"
  tasks_completed: 4
  tasks_total: 4
  tests_before: 883
  tests_after: 896
  files_modified: 5
---

# Phase 56 Plan 01: Material Pipeline Shaders Summary

Unified terrain material engine: killed split-brain between v1 hard thresholds and v2 smoothstep, wired real PBR textures with roughness variation, connected DAG splatmap output to Blender materials, added triplanar projection for cliff/slope layers and displacement output.

## Tasks Completed

| Task | Description | Commit | Key Changes |
|------|------------|--------|-------------|
| 1 | Kill split-brain (v1 delegates to v2 smoothstep) | fe620f5 | Replace hard 30/60-deg thresholds with _smoothstep_band in auto_assign_terrain_layers and compute_world_splatmap_weights |
| 2 | Wire real PBR textures | caf451e | Add _build_pbr_layer_nodes with roughness variation overlay, normal maps, image texture slots, displacement output |
| 3 | Connect DAG splatmap to Blender | 29a36cb | Add dag_weights_to_rgba (5->4 channel mapping) and apply_dag_splatmap_to_mesh bridge |
| 4 | Add triplanar + displacement | b618ea2 | Add _create_triplanar_group node group, _apply_triplanar_to_layer, auto-enable for cliff/slope |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_larger_cell_size with appropriate slope range**
- **Found during:** Task 1
- **Issue:** Test used linspace(0,1) heightmap producing ~14-degree slopes, entirely within ground zone for both cell sizes after smoothstep transition. Old hard-threshold linear ramps created artificial differences.
- **Fix:** Changed to linspace(0,5) producing ~51 deg (fine) vs ~17 deg (coarse), properly testing the slope/ground transition.
- **Files modified:** tests/test_environment_handlers.py
- **Commit:** fe620f5

## Architecture Decisions

### Split-Brain Resolution
The v1 `terrain_materials.py` had hard 30/60-degree slope thresholds creating visible banding. The v2 `terrain_materials_v2.py` used smoothstep envelopes but was disconnected from Blender. Resolution: v1 now imports and uses v2 primitives (`_smoothstep_band`) directly, with configurable falloff widths (8-10 degrees) for smooth Hermite transitions.

### 5-to-4 Channel Mapping
V2 produces 5 channels (ground, cliff, scree, wet_rock, snow). These map to RGBA as:
- R = ground
- G = scree (slope proxy)
- B = cliff
- A = wet_rock + snow (special proxy)

### Triplanar Projection
Cliff and slope layers auto-enable triplanar mapping. The node group computes `abs(normal)^blend` per axis, normalizes, then samples noise from 3 orthogonal UVs and blends. This eliminates stretching on faces steeper than ~45 degrees.

## Verification

- 896 tests pass (up from 883 baseline)
- 13 new tests added across test_terrain_materials.py and test_terrain_materials_v2.py
- All pre-existing tests continue to pass (backward compatible)

## Self-Check: PASSED

All 4 commits verified, all 5 modified files present, SUMMARY.md created.
