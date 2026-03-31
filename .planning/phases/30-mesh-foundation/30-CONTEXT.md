# Phase 30: Mesh Foundation - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Execute 20+ parametric mesh generators (tables, chairs, barrels, chests, shelves, beds, rocks, trees, bushes) replacing all placeholder primitives. Create material presets with roughness variation (never single float - always use roughness texture maps with procedural noise and curvature-based wear maps). Implement LOD presets per asset type (hero characters: 40K-60K/20K-30K/8K-15K/2K-5K; building modular pieces: 2K-8K/1K-4K/500-2K/cull; vegetation with billboard fallback). Add boolean cleanup pipeline and silhouette validation. Ensure scene-level polygon budget validator (50K-150K per room interior, 200K-500K per town block).
</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.
</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

## Existing Systems
- 127+ procedural mesh generators across 21 categories (procedural_meshes.py)
- Pure-logic/bpy-guarded split: generators return MeshSpec dicts, only _mesh_bridge.py touches bpy/bmesh
- xatlas for UV unwrapping
- pymeshlab for high-quality remeshing/decimation
- LOD pipeline with per-asset-type presets

## Key Patterns
- All generators must accept `seed` parameter and use `random.Random(seed)`, never global state
- Return MeshSpec dicts: {vertices, faces, uvs, metadata}
- Quality gate at every stage: Generate → validate → next step
- Never output primitives (cubes, cones, spheres) as final mesh geometry

## Integration Points
- blender_mesh tool for validation and game_check
- blender_uv tool for UV unwrapping
- blender_export for Unity-ready FBX export
</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

Critical Rules (from v4.0 PITFALLS.md):
- NO PLACEHOLDER PRIMITIVES — every generator must produce real mesh geometry
- NO UNIFORM ROUGHNESS — always use roughness texture maps with variation
- NO GLOBAL RANDOM STATE — always use seed-based RNG
- QUALITY GATE AFTER EVERY STEP — generate → validate → next step
</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.
</deferred>
