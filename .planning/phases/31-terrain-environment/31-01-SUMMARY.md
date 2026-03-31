---
phase: 31-terrain-environment
plan: 01
subsystem: terrain
tags: [domain-warp, erosion, opensimplex, heightmap, fbm, noise]

# Dependency graph
requires: []
provides:
  - "generate_heightmap with warp_strength/warp_scale params for organic terrain"
  - "Auto-scaled erosion to 50K+ droplets for visible river channels"
  - "Opensimplex noise in terrain_features.py replacing sin-hash artifacts"
affects: [31-02, 31-03, 32-building-system, 34-multi-biome]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Domain warp integration: conditional call to domain_warp_array before fBm loop"
    - "Erosion auto-scaling: min 50K droplets when erosion enabled, proportional to resolution"
    - "Noise generator caching: module-level _features_gen/_features_seed for hot-path reuse"

key-files:
  created: []
  modified:
    - "Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/environment.py"
    - "Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py"

key-decisions:
  - "Default warp_strength=0.0 in generate_heightmap for backward compat, 0.4 in environment.py handler for organic default"
  - "Erosion auto-scale uses max(50000, resolution^2/5) formula for proportional scaling"
  - "Replaced _hash_noise/_fbm in terrain_features.py with opensimplex via _make_noise_generator, keeping same function signatures for all 40+ call sites"

patterns-established:
  - "Domain warp before fBm: always warp coordinate grids, not noise output"
  - "Noise generator caching with seed tracking for terrain_features module"

requirements-completed: [MESH-05, MESH-09, MESH-10]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 31 Plan 01: Terrain Foundation Quality Summary

**Domain warping wired into heightmap generation, erosion auto-scaled to 50K+ droplets, sin-hash noise replaced with opensimplex across terrain_features.py**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T12:50:06Z
- **Completed:** 2026-03-31T12:55:11Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Domain warp integration in generate_heightmap with warp_strength/warp_scale parameters; calls domain_warp_array between meshgrid creation and fBm loop when warp_strength > 0
- Erosion auto-scaling in handle_generate_terrain: minimum 50,000 droplets when hydraulic erosion enabled, with resolution-proportional formula
- Replaced all sin-hash _hash_noise and _fbm functions in terrain_features.py with opensimplex-backed implementations via _make_noise_generator import
- All 134 terrain tests pass (63 noise+erosion + 71 features)

## Task Commits

Each task was committed atomically:

1. **Task 1: Domain warp integration + erosion escalation + noise fix** - `efe86f0` (feat)

## Files Created/Modified
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` - Added warp_strength/warp_scale params to generate_heightmap, domain_warp_array call before fBm loop
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py` - Auto-scale erosion to 50K+, pass warp_strength/warp_scale through to generate_heightmap
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py` - Replaced sin-hash _hash_noise/_fbm with opensimplex via _make_noise_generator, added generator caching

## Decisions Made
- Default warp_strength=0.0 in generate_heightmap signature preserves backward compatibility; environment.py handler uses 0.4 as the organic default when not specified by caller
- Erosion auto-scale formula: max(50000, resolution*resolution//5) ensures proportional scaling for larger terrains while maintaining 50K minimum
- Kept _hash_noise/_fbm function signatures identical (same name, same positional args) so all 40+ call sites in terrain_features.py required zero changes

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all implementations are fully wired with real data sources.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Heightmap generation now supports organic domain warping for all downstream terrain features
- Erosion produces visible river channels at 50K+ droplets for splatmap moisture estimation
- terrain_features.py noise is artifact-free for canyon/cliff/waterfall generation
- Ready for Plan 02 (splatmap painting with slope/altitude/moisture) and Plan 03 (vegetation scatter)

---
*Phase: 31-terrain-environment*
*Completed: 2026-03-31*
