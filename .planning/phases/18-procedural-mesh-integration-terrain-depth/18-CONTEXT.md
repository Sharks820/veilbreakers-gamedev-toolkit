# Phase 18: Procedural Mesh Integration + Terrain Depth - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning
**Source:** Auto-generated (autonomous mode)

<domain>
## Phase Boundary

Wire the 127 procedural mesh generators into the existing worldbuilding/environment handlers so they produce REAL game-ready meshes instead of primitive cubes/cones. Add vertical terrain features (cliffs, caves, waterfalls, bridges) that go beyond 2.5D heightmap limitations. Generate LOD variants of all meshes for performance budgets.

Requirements: MESH3-01, MESH3-02, MESH3-03, MESH3-04, MESH3-05, TERR-01, TERR-02, TERR-03, TERR-04, TERR-05.

</domain>

<decisions>
## Implementation Decisions

### Mesh Integration Strategy
- **Replace primitives at the handler level**: Modify `_building_grammar.py` interior generation to call `procedural_meshes.generate_table_mesh()` etc. instead of creating scaled cubes
- **Replace scatter primitives**: Modify `_scatter_engine.py` to use `procedural_meshes.generate_rock_mesh()`, `generate_tree_mesh()` instead of icospheres/cones
- **Replace dungeon props**: Modify `_dungeon_gen.py` to place actual trap meshes, altar meshes, torch sconces from procedural library
- **Replace castle elements**: Modify worldbuilding handlers to use gate, rampart, drawbridge, fountain meshes
- **Blender mesh conversion**: Create a `_mesh_from_spec(spec_dict)` helper that converts procedural_meshes output (vertices/faces) into actual Blender mesh objects via bmesh

### Terrain Depth
- **Cliff face geometry**: Generate vertical rock wall meshes using noise-displaced cylinder segments — not heightmap-based
- **Cave entrance transitions**: Generate archway/tunnel entrance meshes that blend seamlessly with terrain at the opening
- **Multi-biome blending**: Generate transition zone meshes (e.g., mossy rocks at forest/swamp boundary, snow-dusted trees at mountain/forest boundary) using procedural variation
- **Waterfall geometry**: Generate stepped water surface meshes with cascade drop-offs
- **Bridge generation**: Detect river/chasm gaps in terrain and generate spanning bridge meshes (stone arch, rope, drawbridge)

### LOD Strategy
- **3 LOD levels**: LOD0 (full detail), LOD1 (50% faces), LOD2 (25% faces)
- **Automatic via Blender decimate modifier**: Apply decimate modifier at ratios for each LOD level
- **Export all LODs**: Each mesh exports with LOD0/LOD1/LOD2 variants in the same FBX

### Claude's Discretion
- Exact vertex counts for each LOD level
- Noise parameters for cliff face displacement
- Cave entrance arch profile curve
- Biome transition zone width
- Waterfall step heights and widths
- Bridge structural detail level

</decisions>

<canonical_refs>
## Canonical References

### Implementation
- `Tools/mcp-toolkit/blender_addon/handlers/procedural_meshes.py` — 127 generators to integrate
- `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` — Interior furnishing (currently places cubes)
- `Tools/mcp-toolkit/blender_addon/handlers/_scatter_engine.py` — Vegetation/prop scatter (currently uses primitives)
- `Tools/mcp-toolkit/blender_addon/handlers/_dungeon_gen.py` — Dungeon generation (needs real props)
- `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` — Castle/building handlers
- `Tools/mcp-toolkit/blender_addon/handlers/environment.py` — Terrain/scatter handlers

### Requirements
- `.planning/REQUIREMENTS.md` — MESH3-01 through MESH3-05, TERR-01 through TERR-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `procedural_meshes.GENERATORS` dict: Registry of all 127 generators by category
- `procedural_meshes._merge_meshes()`: Combine multiple mesh specs into one
- `procedural_meshes._make_result()`: Standard output format
- Existing `_building_grammar.py` furniture placement logic (positions, rotations, scales)
- Existing `_scatter_engine.py` Poisson disk distribution

### Established Patterns
- Handlers receive Blender `bpy` context and create objects via `bpy.data.meshes.new()` + `bpy.data.objects.new()`
- All handlers return structured dict results
- Contact sheets for visual verification after creation

### Integration Points
- `_mesh_from_spec()` bridge function: procedural_meshes → bmesh → Blender object
- Interior generation calls in `_building_grammar.py` line ~180-250
- Scatter placement in `_scatter_engine.py`
- Terrain generation in `environment.py`

</code_context>

<specifics>
## Specific Ideas

- The key bridge is `_mesh_from_spec()` — once this converts vertex/face data to Blender objects, ALL 127 generators become usable in any handler
- Furniture placement already has position/rotation/scale logic — just need to swap the primitive creation for procedural mesh creation
- Scatter engine already distributes points — replace `bpy.ops.mesh.primitive_cube_add()` with actual rock/tree meshes
- Cliffs should use Blender's noise texture node for displacement
- Cave entrances need to be placed at specific terrain edge positions

</specifics>

<deferred>
## Deferred Ideas

None — autonomous mode stayed within phase scope

</deferred>

---

*Phase: 18-procedural-mesh-integration-terrain-depth*
*Context gathered: 2026-03-21 via autonomous mode*
