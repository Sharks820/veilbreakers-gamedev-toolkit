# Phase 6: Environment & World Building - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a complete environment generation pipeline. Claude can generate terrain with erosion, auto-paint biome textures, create caves/dungeons, carve rivers/roads, generate buildings/castles/towers, scatter vegetation and props, create modular architecture kits, generate ruins, and produce interior layouts. All geometry is textured and export-ready for Unity.

</domain>

<decisions>
## Implementation Decisions

### Terrain Generation
- Heightmap-based terrain using noise functions (Perlin, Simplex, Voronoi, fBm)
- Erosion simulation: hydraulic (water flow) and thermal (slope collapse) applied as post-process
- Terrain features are parameterized: mountains (high amplitude), canyons (subtracted ridges), cliffs (step functions), volcanic (crater radial falloff)
- Auto texture painting based on slope/altitude/moisture rules mapped to terrain material slots

### Building & Structure Generation
- Procedural building from grammar rules: foundation -> walls -> floors -> roof -> details
- Configurable style parameters: medieval, gothic, rustic, fortress, organic
- Interior generation places furniture, wall decorations, lighting based on room type
- Castle/tower/bridge/fortress use specialized generation templates

### Dungeon & Cave Systems
- BSP (Binary Space Partition) for room placement with corridor connections
- Cave systems use cellular automata for natural formations
- Connected graph ensures navigability (no orphan rooms)
- Spawn points, loot positions, and door placements are part of the layout

### Vegetation & Props
- Biome-aware scatter: tree types by altitude band, grass density by slope, rocks by terrain roughness
- Context-aware props: barrels near taverns, crates near docks, lanterns near paths
- Particle system or collection instances for performance

### Modular Architecture
- Snap-together pieces: walls (straight, corner, T), floors, doors, windows, stairs
- Grid-based placement system with configurable cell size
- Ruins variant: damaged versions of modular pieces (broken walls, collapsed roofs, overgrown)

### Claude's Discretion
All implementation choices are at Claude's discretion — autonomous execution mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `blender_addon/handlers/` - Handler pattern for Blender commands
- `blender_server.py` - Compound MCP tool pattern (13 tools)
- `blender_addon/handlers/objects.py` - Object creation handler pattern
- `shared/texture_ops.py` - Texture operations for terrain painting
- `shared/pipeline_runner.py` - Batch processing pipeline

### Established Patterns
- Handler functions: `handle_*(params: dict) -> dict`
- Pure-logic extraction for testable algorithms (noise, BSP, layout)
- Compound tools with Literal action params

### Integration Points
- New handlers register in COMMAND_HANDLERS
- New compound tools: `blender_environment` and `blender_worldbuilding`
- Terrain heightmaps export as raw files for Unity Terrain import

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers is a dark fantasy/horror game - environments should support that aesthetic
- Unity terrain system uses raw heightmap files (16-bit)
- Modular pieces should work with Unity's grid snapping
- LOD support for vegetation scatter (LOD0-LOD2 for trees)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
