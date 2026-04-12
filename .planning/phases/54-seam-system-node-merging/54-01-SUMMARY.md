---
phase: "54"
plan: "01"
subsystem: terrain-seam-system
tags: [seam, stitching, node-registry, fault-lines, erosion, poisson-blend]
dependency_graph:
  requires: [terrain_semantics, terrain_chunking, _terrain_erosion]
  provides: [terrain_seam_guards, terrain_node_registry, terrain_seam_stitcher, terrain_fault_lines, terrain_pipe_erosion]
  affects: [terrain_pipeline, environment]
tech_stack:
  added: [pipe-model-erosion, poisson-blending, fault-displacement]
  patterns: [guard-band-masks, edge-fade-weights, adaptive-tolerance]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_seam_guards.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_node_registry.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_seam_stitcher.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_fault_lines.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_pipe_erosion.py
    - Tools/mcp-toolkit/tests/test_terrain_seam_system.py
  modified: []
decisions:
  - "Gauss-Seidel (omega=1.0) for Poisson blend stability over SOR (omega>1 diverges on small grids)"
  - "A-wins deterministic tie-breaking for material ID conflicts at seams"
  - "Guard bands use ProtectedZoneSpec with allowed_mutations whitelist"
metrics:
  duration_seconds: 597
  completed: "2026-04-12T12:45:53Z"
  tasks_completed: 6
  tasks_total: 6
  tests_added: 57
  files_created: 6
---

# Phase 54 Plan 01: Seam System and Node Merging Summary

Seam guard zones, TerrainNodeRegistry, stitch bug fixes (F164-F169, F813-F818), fault line displacement with rock hardness wiring, pipe-model erosion for hero nodes, and Poisson blending for seamless hero patch compositing.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Seam guard zones | 8561ec9 | terrain_seam_guards.py |
| 2 | TerrainNodeRegistry | 2f9c240 | terrain_node_registry.py |
| 3 | Stitch bug fixes F164-F169, F813-F818 | 80266fd | terrain_seam_stitcher.py |
| 4 | Fault line displacement system | 7787a5a | terrain_fault_lines.py |
| 5 | Pipe-model erosion + Poisson blend | b082ed6 | terrain_pipe_erosion.py |
| 6 | Integration tests (57 tests) | 956643a | test_terrain_seam_system.py |

## Implementation Details

### Seam Guard Zones (terrain_seam_guards.py)
- `compute_guard_band_mask`: Boolean mask marking N-cell border as protected
- `compute_edge_fade_weights`: Float [0,1] mask that decays hero deltas to zero at edges
- `apply_hero_delta_with_fade`: Applies hero displacement multiplied by fade weights
- `create_seam_guard_zones`: Factory producing 4 ProtectedZoneSpec per tile edge

### TerrainNodeRegistry (terrain_node_registry.py)
- Config consistency validation: rejects tiles with mismatched tile_size/cell_size/coordinate_system
- 4-directional neighbor lookup with shared edge pair enumeration
- Edge height caching and cross-tile validation (atol=1e-12)
- Hero node tracking with feature IDs

### Stitch Bug Fixes (terrain_seam_stitcher.py)
- **F164**: Idempotent stitching -- early return when edges already match
- **F165**: Adaptive tolerance scaled by max world coordinate magnitude
- **F166**: Material ID snap at seams using deterministic A-wins tie-breaking
- **F167**: `safe_height_scale` with epsilon guard prevents divide-by-zero on flat terrain
- **F168**: `validate_stitched_export` checks all adjacent tile edges before export
- **F169**: `resize_heightmap_bilinear` + vectorized fast variant replace nearest-neighbor
- **F813**: `repair_seam_heights` with blend-band linear interpolation
- **F814**: `validate_protected_zone_seam_integrity` detects guard-cell mutations
- **F818**: `compute_triplanar_continuity_weights` for cross-tile material blending

### Fault Line Displacement (terrain_fault_lines.py)
- Normal, reverse, and strike-slip fault types with smoothstep displacement profile
- Rock hardness modulation: soft rock (0.0) = 100% displacement, hard rock (1.0) = 20%
- Roughness noise along fault trace with distance-based fade
- Guard mask integration prevents displacement in seam zones

### Pipe-Model Erosion + Poisson Blend (terrain_pipe_erosion.py)
- Shallow water pipe-model: flux computation, water depth update, velocity field, sediment transport
- Guard mask prevents erosion/deposition in protected cells
- Poisson blend (Gauss-Seidel solver): preserves patch gradients while matching base at boundary
- `poisson_blend_patch`: convenience wrapper for compositing smaller hero patches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Poisson SOR divergence**
- **Found during:** Task 5
- **Issue:** SOR with omega=1.6 diverged on small grids (17x17), producing -1e98 values
- **Fix:** Changed default omega to 1.0 (standard Gauss-Seidel)
- **Files modified:** terrain_pipe_erosion.py
- **Commit:** b082ed6

## Decisions Made

1. Used Gauss-Seidel (omega=1.0) instead of SOR for Poisson blend -- stable on all grid sizes at the cost of slower convergence on large grids.
2. Material ID conflicts at seams resolved with deterministic A-wins (tile A's material takes precedence) rather than neighborhood voting -- simpler and reproducible.
3. Guard bands implemented as ProtectedZoneSpec with allowed_mutations whitelist rather than forbidden_mutations blacklist -- more secure against new pass types.

## Success Criteria Verification

- [x] Adjacent tiles identical height at shared boundary (atol=1e-12) -- verified in test_stitched_tiles_match_at_boundary
- [x] Hero deltas fade to zero at tile edges -- verified in test_hero_deltas_fade_to_zero_at_edges
- [x] Seam guard zones block mutations -- verified in test_zones_forbid_erosion, test_apply_fault_lines_respects_guard_mask, test_respects_guard_mask
- [x] TerrainNodeRegistry tracks tiles -- verified in test_register_and_get, test_neighbor_lookup, test_shared_edge_pairs
- [x] All F164-F169 stitch bugs fixed -- each has a dedicated test
- [x] Fault lines produce visible displacement -- verified in test_displacement_produces_visible_offset
- [x] 57 tests pass -- all pass
- [x] SUMMARY.md created

## Self-Check: PASSED

All 6 created files exist on disk. All 6 commit hashes verified in git log.
