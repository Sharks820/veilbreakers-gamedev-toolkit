# Phase 31: Terrain & Environment - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Terrain generation produces dramatic, eroded landscapes with multi-biome blending, cliff mesh overlays beyond heightmap limitations, and vegetation scattered by Poisson disk sampling -- visually comparable to Skyrim's overworld.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

## Existing Systems (from 30-RESEARCH.md)
- Terrain noise: `_terrain_noise.py` — fBm with opensimplex, 8 octaves, numpy-vectorized
- Hydraulic erosion: `_terrain_erosion.py` — proper droplet-based with bilinear gradient, BUT only 1000 droplets default
- Thermal erosion: `_terrain_erosion.py` — talus-angle based, 8-connected
- Terrain features: `terrain_features.py` — canyon generator, BUT uses sin-hash noise (not real Perlin)
- Terrain materials: `terrain_materials.py` — 14 biome palettes, splatmap blending, corruption tint
- Terrain sculpt: `terrain_sculpt.py` — brush-based vertex ops
- Terrain advanced: `terrain_advanced.py` — spline deformation, flow maps
- Vegetation: `generate_tree_mesh` — trunk lathe OK, canopy is sphere clusters (needs L-system)

## Key Patterns
- All generators must accept `seed` parameter and use `random.Random(seed)`
- Return MeshSpec dicts: {vertices, faces, uvs, metadata}
- Quality gate at every stage

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

Key techniques from research:
- Hydraulic erosion: increase to 50K+ droplets (Sebastian Lague particle-based approach)
- Domain warping: f(p + fbm(p + fbm(p))) for organic terrain
- Poisson disk sampling: Bridson's O(n) algorithm for vegetation scatter
- L-system trees: string rewriting + turtle interpreter for realistic branching
- Cliff meshes: vertical geometry extending beyond heightmap limitations

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
