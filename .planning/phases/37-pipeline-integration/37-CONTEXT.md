# Phase 37: Pipeline Integration - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire every procedural system (Phases 30-36) into a single resumable pipeline with state checkpointing, Unity Addressables streaming group auto-generation per district, occlusion portal geometry at all interior/exterior boundaries, and a Unity-importable map package export.

</domain>

<decisions>
## Implementation Decisions

All decisions are derived from the existing codebase (no user discussion file exists for this phase).

### Checkpoint / Resume
- **D-01:** State persistence uses a plain JSON checkpoint file written to a `checkpoint_dir` param (defaults to `~/.veilbreakers/checkpoints/{map_name}/`). File written after each compose_map step completes.
- **D-02:** Resume is opt-in via a `resume=True` param on `asset_pipeline action=compose_map`. Without it, always runs fresh.
- **D-03:** Spec drift guard: on resume, compare seed + location count. If mismatch, require `force_restart=True`.

### Export Package Format
- **D-04:** Export is per-Addressable-group, not per-object. One FBX per group (terrain, each district, each building-with-interior). This prevents Blender's per-object selection/export loop performance problem.
- **D-05:** Scene hierarchy JSON emitted alongside FBX files. Format: flat list of object entries with name, type, district, world transform, fbx_path, LOD variants, has_interior flag.
- **D-06:** `generate_map_package` always runs `blender_mesh action=game_check` on all created objects before any FBX export. Export aborts if game_check reports failures.

### Addressable Groups
- **D-07:** Group naming: `Map_{MapName}_Terrain_Near`, `Map_{MapName}_Terrain_Mid`, `Map_{MapName}_Terrain_Far`, `Map_{MapName}_District_{Type}`, `Map_{MapName}_Building_{Name}`.
- **D-08:** Distance thresholds: Near=0-80m, Mid=80-200m, Far=200m+. Applied to terrain tile objects by distance from map center.
- **D-09:** The `setup_map_streaming` Unity action reads the scene hierarchy JSON and calls `generate_addressables_config_script()` with derived group list -- no manual group entry.

### Occlusion Zones
- **D-10:** Portal quad geometry (thin 0.1m-depth quad matching door opening) created at every interior doorway during `compose_interior` step. Named `{building}_Portal_{idx}`.
- **D-11:** `{building}_OcclusionZone` convex box (room bounds inset 0.1m) created per room as Unity static occluder hint.
- **D-12:** Unity `setup_occlusion` action (already referenced in next_steps of compose_interior) generates `StaticOcclusionCulling.Compute()` call in the C# script. New `setup_map_streaming` action includes occlusion bake instruction.

### MESH-16 (Process Requirement)
- **D-13:** MESH-16 is a process requirement satisfied by: atomic commits after each task, STATE.md updated at phase completion. No new tooling required.

### PIPE-01 (Research Document)
- **D-14:** PIPE-01 requires a research document covering: CGA split grammars, WFC, L-systems, hydraulic erosion, Poisson disk sampling, straight skeleton roofs, domain warping. This is Task 5 of the plan -- a standalone `PIPE-01-AAA-TECHNIQUES.md` written to `.planning/research/`.

### Claude's Discretion
- Exact checkpoint file schema fields beyond the minimum defined above
- Whether LOD generation for `generate_map_package` runs inline or calls existing `lod_pipeline` handler directly
- Specific C# property names in the `setup_map_streaming` Unity script
- Whether `setup_map_streaming` also handles LOD Group component configuration

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before implementing.**

### Pipeline Orchestration (Blender-side)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` lines 2412-2714 -- complete `compose_map` implementation (9 steps, error isolation, result schema)
- `Tools/mcp-toolkit/blender_addon/handlers/map_composer.py` lines 1002-1160 -- `compose_world_map()` return schema: `{"pois": [...], "roads": [...], "world_features": [...], "metadata": {...}}`
- `Tools/mcp-toolkit/blender_addon/handlers/export.py` -- `handle_export_fbx()`, `handle_export_gltf()`
- `Tools/mcp-toolkit/blender_addon/handlers/lod_pipeline.py` -- LOD chain generation

### Unity Side
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/build_templates.py` lines 279-397 -- `generate_addressables_config_script(groups, build_remote, namespace)` -- already generates BundledAssetGroupSchema C# code
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` -- add new `setup_map_streaming` action here

### Existing Tests
- `Tools/mcp-toolkit/tests/test_map_composer.py` -- `compose_world_map()` integration tests (do not break)
- `Tools/mcp-toolkit/tests/test_compose_planners.py` -- `_plan_map_location_anchors` tests

### Phase 36 Context
- `.planning/phases/36-world-composer/36-CONTEXT.md` -- Phase 36 design decisions; compose_map location data shape

</canonical_refs>

<code_context>
## Existing Code Insights

### What compose_map Already Does
`asset_pipeline action=compose_map` (blender_server.py 2412-2714) runs 9 sequential steps:
1. `clear_scene`
2. `env_generate_terrain` (with hydraulic erosion)
3. `env_carve_river` + `env_create_water` (per river/water spec)
4. `env_generate_road` (per road waypoint set)
5. Location generation: `world_generate_town|castle|dungeon|cave|ruins|building|boss_arena`
6. `env_paint_terrain` + `terrain_create_biome_material`
7. `env_scatter_vegetation`
8. `env_scatter_props`
9. `world_generate_linked_interior` (per location with `interiors` key)

Returns: `{status, map_name, steps_completed, steps_failed, objects_created, locations, interiors, budget_applied, quality_report, next_steps}`

**What it does NOT do today:**
- Write any checkpoint JSON to disk
- Support resume from a failed step
- Export FBX or scene hierarchy JSON
- Generate occlusion portal geometry
- Derive Addressable groups from location data

### Addressable Config Generator (build_templates.py)
`generate_addressables_config_script(groups, build_remote, namespace)` at line 287:
- Accepts a list of `{"name": str, "packing": str, "local": bool}` dicts
- Generates complete C# editor script with `BundledAssetGroupSchema` + `ContentUpdateGroupSchema`
- Handles create-or-find semantics (idempotent)
- Optionally calls `AddressableAssetSettings.BuildPlayerContent()` if `build_remote=True`

This function is exactly what `setup_map_streaming` needs to call -- just needs the group list derived from compose_map output.

### Occlusion References
`compose_interior` next_steps already references `unity_world action=setup_occlusion` (line 2878). The Unity action does not yet exist -- it is listed as a next_step instruction, not a real MCP action. Phase 37 implements it properly as part of `setup_map_streaming`.

### Export Handlers
`handle_export_fbx()` in export.py:
- Takes `filepath`, `selected_only=False`, `apply_modifiers=True`
- Unity-optimised: `axis_forward="-Z"`, `axis_up="Y"`, `apply_unit_scale=True`, `FBX_SCALE_ALL`
- No LOD awareness -- caller must ensure LODs are generated before calling

### State of checkpoint_dir
No `checkpoint_dir` parameter exists anywhere in the codebase today. This is new in Phase 37.

</code_context>

<specifics>
## Specific Ideas

- The `pipeline_state.py` module should have zero bpy dependency -- pure Python so tests run without Blender
- `generate_map_package` should accept a list of object names (from `compose_map` result `objects_created`) so it can be called after an existing compose_map run without re-running the full pipeline
- Scene hierarchy JSON should be written to the same `checkpoint_dir` so it travels with the checkpoint
- Unity `setup_map_streaming` action should produce a single C# script that: (1) creates Addressable groups, (2) assigns assets to groups from a provided JSON manifest, (3) configures LOD Groups, (4) sets Static flags on buildings, (5) calls `StaticOcclusionCulling.Compute()`

</specifics>

<deferred>
## Deferred Ideas

- Runtime LOD switching via Unity LOD Group driven by player distance (Phase 38 concern)
- Streaming audio zones tied to district boundaries (already handled by `unity_audio action=setup_portal_audio`)
- Per-building NavMesh baking (Phase 38 or later)
- Automatic CI build triggering after Addressables are configured

</deferred>

---

*Phase: 37-pipeline-integration*
*Context gathered: 2026-03-31*
