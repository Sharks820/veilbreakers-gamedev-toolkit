---
phase: 31-terrain-environment
plan: 01
subsystem: terrain
tags: [domain-warp, erosion, opensimplex, heightmap, fbm, terrain-noise]

# Dependency graph
requires:
  - phase: none
    provides: existing terrain pipeline (_terrain_noise.py, _terrain_erosion.py, terrain_features.py)
provides:
  - Domain-warped heightmap generation (warp_strength/warp_scale params on generate_heightmap)
  - Auto-scaled erosion to 50K+ droplets in handle_generate_terrain
  - Opensimplex noise in terrain_features.py replacing sin-hash artifacts
affects: [31-02, 31-03, 32-building-system, 34-multi-biome-terrain]

# Tech tracking
tech-stack:
  added: []
  patterns: [domain-warp-before-fbm, erosion-auto-scaling, module-cached-noise-generator]

key-files:
  created: []
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py
    - Tools/mcp-toolkit/blender_addon/handlers/environment.py
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py

key-decisions:
  - "Domain warp defaults to 0.0 in generate_heightmap (backward compat) but 0.4 in handle_generate_terrain (organic by default for terrain handler)"
  - "Erosion auto-scaling uses max(50000, resolution^2/5) for proportional scaling"
  - "terrain_features.py _hash_noise uses module-level cached generator to avoid per-call overhead"

patterns-established:
  - "Domain warp insertion point: between meshgrid creation and fBm octave loop in generate_heightmap"
  - "Erosion auto-scaling guard: minimum 50K when erosion mode is not 'none'"
  - "Noise generator caching: global _features_gen/_features_seed pattern for single-file modules"

requirements-completed: [MESH-05, MESH-09, MESH-10]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 31 Plan 01: Terrain Quality Foundations Summary

**Domain warping wired into heightmap generation, erosion auto-scaled to 50K+ droplets, sin-hash noise replaced with opensimplex across terrain_features.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T12:45:02Z
- **Completed:** 2026-03-31T12:49:09Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- generate_heightmap now accepts warp_strength/warp_scale and calls domain_warp_array conditionally, producing organic non-repetitive terrain
- handle_generate_terrain auto-scales erosion to >= 50K droplets when erosion is enabled, ensuring visible river channels
- terrain_features.py _hash_noise and _fbm now use opensimplex via _make_noise_generator, eliminating periodic sin-hash artifacts across all 10 terrain feature generators
- Backward compatibility preserved: warp_strength=0.0 produces identical output to pre-change behavior
- All 134 terrain tests pass (56 noise + erosion, 78 features_v2)

## Task Commits

Each task was committed atomically:

1. **Task 1: Domain warp integration + erosion escalation + noise fix** - `97e6790` (feat)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` - Added warp_strength/warp_scale params to generate_heightmap, domain_warp_array call before fBm loop
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py` - Auto-scale erosion to 50K+, pass warp params through to generate_heightmap
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py` - Replaced sin-hash _hash_noise/_fbm with opensimplex via _make_noise_generator import

## Decisions Made
- Domain warp default is 0.0 in generate_heightmap (API backward compat) but 0.4 in handle_generate_terrain (organic terrain by default for the handler path) -- this means direct API callers opt-in while the Blender handler gets quality by default
- Used seed offset +7919 (prime) for warp noise to avoid correlation with heightmap noise
- Module-level generator caching in terrain_features.py (_features_gen/_features_seed globals) to avoid recreating opensimplex generator on every _hash_noise call

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Domain-warped heightmaps ready for downstream biome distribution (Plan 02/03)
- 50K+ erosion creates drainage patterns usable as moisture proxy for splatmap painting
- Opensimplex noise in terrain_features.py means all canyon/cliff/waterfall/arch features have organic noise without artifacts

## Self-Check: PASSED

- [x] _terrain_noise.py exists with warp_strength/warp_scale params
- [x] environment.py exists with erosion auto-scaling
- [x] terrain_features.py exists with opensimplex import
- [x] 31-01-SUMMARY.md created
- [x] Commit 97e6790 found in git log

---
*Phase: 31-terrain-environment*
*Completed: 2026-03-31*
