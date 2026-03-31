# Phase 30 (P0): Mesh Foundation — Plan 1 (Superseded)

**Created:** 2026-03-30
**Status:** SUPERSEDED by 30-02-PLAN.md (v2, 2026-03-31)
**Reason:** Plan 1 contained incorrect generator counts (cited "127+" from v3.0 era), proposed creating infrastructure that already exists (LOD presets, silhouette validation), and used the wrong acceptance criterion ("no primitives" instead of output quality metrics). See 30-RESEARCH.md for actual codebase state and 30-02-PLAN.md for corrected execution plan.

## What Was Wrong in Plan 1

1. **Generator count:** Said "127+" — actual count is 267 `generate_*` functions
2. **Plans 1.2-1.4:** Proposed creating parametric generators, material presets, and LOD presets as greenfield — but generators already exist (267 of them), procedural_materials.py has 45+ AAA presets, and lod_pipeline.py has 7 preset tiers with silhouette preservation
3. **Plans 1.1-1.7:** Used undefined sub-plan IDs (MESH-01.1 through MESH-01.7) that don't exist in REQUIREMENTS.md
4. **Acceptance criterion:** "No cubes, cones, spheres" is wrong — primitive composition is a valid method (Houdini does it). The correct gate is output quality, topology, and visual verification

## Preserved Content (for reference only)

The 7 sub-plans from Plan 1 are preserved below for historical reference. See 30-02-PLAN.md for the corrected 6-plan execution strategy.

---

<details>
<summary>Original Plan 1 Content (superseded)</summary>

## Phase Boundary from ROADMAP

Execute 20+ parametric mesh generators (tables, chairs, barrels, chests, shelves, beds, rocks, trees, bushes) replacing all placeholder primitives. Create material presets with roughness variation (never single float - always use roughness texture maps with procedural noise and curvature-based wear maps). Implement LOD presets per asset type (hero characters: 40K-60K/20K-30K/8K-15K/2K-5K; building modular pieces: 2K-8K/1K-4K/500-2K/cull; vegetation with billboard fallback). Add boolean cleanup pipeline and silhouette validation. Ensure scene-level polygon budget validator (50K-150K per room interior, 200K-500K per town block).

## Success Criteria from ROADMAP (v1 — replaced by v2 criteria)

1. 20+ parametric mesh generators exist and produce real mesh geometry (no cubes, cones, spheres)
2. Material presets include roughness variation (texture maps, not single float values)
3. LOD presets defined per asset type with silhouette preservation
4. Boolean cleanup pipeline implemented
5. Scene-level budget validator exists
6. All generators pass quality gate tests

## Plans 1.1-1.7

Plans 1.1 through 1.7 covered: audit, parametric generators, material presets, LOD presets, boolean cleanup, silhouette validation, scene budget validator. All have been revised and corrected in 30-02-PLAN.md.

</details>

---

*Superseded 2026-03-31 — see 30-02-PLAN.md for corrected execution plan*
