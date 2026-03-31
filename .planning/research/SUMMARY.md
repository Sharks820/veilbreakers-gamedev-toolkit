# Project Research Summary

**Project:** VeilBreakers v4.0 -- AAA Procedural 3D Architecture
**Domain:** Procedural 3D content generation for open-world dark fantasy RPG (Blender + Unity pipeline)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

The AAA procedural 3D generation pipeline in 2026 converges on a proven stack: Blender (bpy + Geometry Nodes 5.1) for procedural generation, multi-backend AI generation (Tripo v3.0, Hunyuan3D 2.1, Rodin Gen-2) for mesh creation at scale, trim sheet-based modular kits for buildings, height-blended splatmaps for terrain, and Unity URP with Addressables for runtime rendering and streaming. This is not experimental -- it is the production approach used by Bethesda (modular kits), FromSoftware (interconnected modular worlds), and Guerrilla Games (GPU-based procedural placement). The recommended approach is a hybrid imperative-declarative split: bpy/bmesh for precise topology construction and Geometry Nodes 5.1 for declarative patterns (facade scattering, repeat zones for floors/windows, instancing). Neither alone covers the full pipeline.

The single biggest risk is execution discipline around mesh quality. The existing toolkit has 127+ generators, but the v3.0 gap analysis identified 67 systemic gaps with furniture/props at only 20% coverage -- because generators produce geometric primitives (cubes for tables, cones for trees, spheres for bushes) instead of real mesh geometry. The v4.0 milestone must enforce a "no primitives in production" rule with quality gates at every pipeline stage. Research identified 10 critical pitfalls, with placeholder primitives and uniform roughness ("everything looks like plastic") as the top two causes of visual quality failure. The mitigation strategy is clear: build the parametric mesh generation library first, before any placement or scattering system. If a table generator outputs a box, it fails the quality gate.

## Key Findings

### Recommended Stack

The stack extends the existing MCP toolkit (37 compound tools, 350 operations) with proven AAA patterns. No changes to the MCP server infrastructure; this research covers the procedural 3D content generation dimension specifically.

**Core technologies:**
- **Blender bpy + bmesh + mathutils (4.x/5.x):** Imperative mesh generation, custom topology, vertex groups, UV manipulation -- all the operations Geometry Nodes cannot express. Already used by 127+ generators. Confidence: HIGH.
- **Blender Geometry Nodes 5.1:** Declarative procedural systems -- Repeat Zones, For Each Element zones, Closures, Bake nodes, Array, Scatter on Surface, Curve to Tube. Essential for facade scattering, floor/window iteration, detail instancing. Confidence: HIGH.
- **Tripo v3.0 API:** Primary AI 3D generator. Quad mesh mode, auto-rigging, 2M polygon output. Best topology of commercial APIs (~$0.10-0.25/model). For characters, enemies, weapons, armor, key props. Confidence: HIGH.
- **Hunyuan3D 2.1 (self-hosted):** Secondary generator. Zero marginal cost, 8K PBR textures, 6GB VRAM minimum. For bulk furniture, environmental objects, vegetation. Eliminates per-model API cost for bulk assets. Confidence: HIGH.
- **Rodin Gen-2 (Hyper3D):** Hero/boss generator. 10B parameters, best overall quality ($0.30-1.50/model). Reserve for hero characters, bosses, legendary weapons only. Confidence: HIGH.
- **xatlas + pymeshlab + Quadriflow:** UV unwrapping, high-quality remeshing/decimation, auto-retopology. Already in the stack. Confidence: HIGH.
- **Unity URP Forward+ + Addressables + Cinemachine 3.x + NavMesh:** Runtime rendering (many point lights via Forward+), asset streaming, camera system, pathfinding. Project constraint. Confidence: HIGH.

**What NOT to use:** Houdini ($4,495/yr, Blender covers equivalent scope), HDRP (entering maintenance per Unity 2026), Virtual Texturing (URP incompatible), Neural rendering/NeRFs (no mesh export), per-building unique textures (draw call explosion), monolithic building meshes (no LOD flexibility).

### Expected Features

**Must have (table stakes):**

- **Parametric mesh generators (20+ types):** Tables, chairs, barrels, chests, shelves, beds, rocks, trees, bushes -- replacing all cube/cone/sphere placeholders. Single biggest unblocker for every other system. Without this, nothing else produces AAA output.
- **Modular architectural kit pieces:** Walls, floors, ceilings, doorways, windows, columns, stairs snapped to standardized grid (4m x 4m x 3.5m cells per Skyrim GDC 2013). 25-40 pieces per architectural style. One kit system serves both buildings and dungeons.
- **Interior room shells with real geometry:** Walls with thickness, doorways with frames, window recesses, ceiling beams. Not box primitives. Enables the 16 room types in the interior system.
- **Multi-biome terrain blending:** Splatmap-based transitions using height-blend algorithm (not linear interpolation). Smooth transitions between forest, swamp, volcanic, corrupted, mountain biomes.
- **Terrain-conforming building foundations:** Buildings follow terrain slope without floating or clipping. Foundation walls fill gaps. Terrain flattening with cosine falloff at building sites.
- **Per-asset-type LOD presets:** Hero character 40K-60K/20K-30K/8K-15K/2K-5K, building modular pieces 2K-8K/1K-4K/500-2K/cull, vegetation with billboard fallback. Silhouette-preserving decimation, not uniform ratios.
- **Scene-level polygon budget validator:** Sums all visible objects against frame budget (2M-6M tris at 60fps PC). Per-object game_check is necessary but not sufficient.

**Should have (competitive differentiators):**

- **Corruption-aware biome progression:** Corruption parameter (0-100%) threaded through all generators -- changes vegetation, terrain, building appearance, prop placement. Unique to VeilBreakers.
- **Trim sheet material sharing:** One 2048x2048 or 4096x4096 texture atlas per architectural style. All kit pieces UV-mapped to shared trim sheet. Single material = single draw call per building.
- **WFC dungeon generation:** Wave Function Collapse produces more organic, varied layouts than BSP. Encodes architectural style rules directly via tile adjacency constraints.
- **Storytelling prop placement:** Context-specific clutter (horseshoes at blacksmith, tankards at tavern, weapons at guard barracks). Breaks visual monotony.
- **Non-cookie-cutter buildings:** Location-context parameters (biome, elevation, wealth) feed into building grammar for material selection, roof style, wall construction.

**Defer (v2+ / v5.0):**
- Agent-based city growth simulation (complex, marginal improvement over Voronoi zoning)
- Art style consistency checker (requires reference geometry library)
- Quest-driven building placement (requires quest system integration)
- Weather-affected mesh variants (mostly shader work)
- AI-directed building variation (LLM integration for room composition)

### Architecture Approach

The system follows a layered pipeline architecture where each stage produces serializable spec dicts that downstream stages consume. The existing codebase already implements the critical pure-logic / bpy-guarded split: all generation logic runs without Blender imports, producing MeshSpec dicts, and only the final materialization step in `_mesh_bridge.py` touches bpy/bmesh. This enables 13,616+ pytest tests without Blender running.

**Major components:**
1. **Procedural Mesh Generator** (`procedural_meshes.py`, 838KB) -- Creates mesh geometry from blueprint parameters. Returns MeshSpec dicts (vertices, faces, UVs, metadata). 127+ existing generators need quality upgrade.
2. **Building Grammar** (`_building_grammar.py`, 103KB) -- Grammar-based composition from rules. Takes style config + seed + constraints, produces list of geometry operations. 5 style configs exist.
3. **Modular Kit** (`modular_building_kit.py`, 55KB) -- 175 snap-together pieces across 5 styles. Needs expansion to 300+ pieces with corrupted/ruined variants.
4. **Terrain System** (`_terrain_noise.py`, `_terrain_erosion.py`, `terrain_features.py`, `terrain_materials.py`) -- Heightmap generation, erosion, biome mapping, splatmap generation. Needs height-blend algorithm and cliff mesh overlays.
5. **Settlement System** (`settlement_generator.py`, 90KB) -- Composes buildings + roads + props into locations. Needs terrain-conforming foundations and district-specific architecture.
6. **Interior System** -- Room layout, furniture, lighting, doors, occlusion. Needs real room shell geometry instead of box primitives.
7. **Scatter Engine** (`_scatter_engine.py`) -- Poisson disk sampling, biome filtering, context scatter. Needs biome-aware rules and LOD on instances.
8. **Material System** (`procedural_materials.py`, 68KB) -- Procedural PBR materials, weathering, trim sheets. Needs roughness variation (never single float) and macro variation maps.
9. **LOD Pipeline** (`lod_pipeline.py`, 31KB) -- Silhouette-preserving decimation per asset type, collision meshes. Needs per-type presets and silhouette validation.
10. **World Composer** (`map_composer.py`, 48KB) -- Places settlements/dungeons/POIs on terrain. Orchestrates the full generation pipeline.

**Key patterns to follow:**
- **Pure-logic / bpy-guarded split:** Every generator returns MeshSpec dicts. Only bridge/handler functions touch bpy. Non-negotiable.
- **Grammar-based composition (not monolithic):** Buildings from kit pieces, not single mesh objects. Enables LOD, streaming, variation.
- **Trim sheet over unique textures:** Single material per building style. Dramatic draw call reduction.
- **Quality gate at every pipeline stage:** Generate -> validate -> next step. Never skip validation.
- **Seed-based deterministic generation:** Every function accepts `seed`. Uses `random.Random(seed)`, not global state.
- **File-based state over context-based:** Prevents context window bloat during long generation sessions.

### Critical Pitfalls

1. **Placeholder primitives masquerading as AAA assets** -- Cubes for furniture, cones for trees, spheres for bushes. This is the single largest systemic issue from the gap analysis (67 gaps, furniture at 20% coverage). Prevention: build mesh generation library FIRST. Enforce "no primitives in production" rule. Every generator must produce real mesh geometry.
2. **Uniform roughness makes everything look like plastic** -- Single roughness value per material produces the "plastic look" regardless of geometry quality. Prevention: never assign a single roughness float. Always use roughness texture maps with procedural noise and curvature-based wear maps.
3. **Heightmap terrain cannot represent vertical geometry** -- Cliffs, overhangs, cave mouths are fundamentally impossible with single-height-per-XY heightmaps. Prevention: accept heightmap limitation for base surface, add separate mesh layer for vertical features (cliff kits, cave entrance pieces).
4. **Per-object budget passes but scene budget fails** -- 50 under-budget props in one room totals 100K+ triangles. Prevention: define scene-level budgets (50K-150K per room interior, 200K-500K per town block). Build scene budget auditor.
5. **Cookie-cutter buildings from identical modules** -- Same 5-10 pieces in same combinations. Prevention: 25-40 module pieces minimum per kit style, narrative dressing layer, vertex color randomization per instance, variant sub-kits (pristine/weathered/damaged/corrupted/ruined).

Additional pitfalls: Tripo pipeline style mismatch with procedural output (solved by unified art style validation), LOD decimation destroying silhouettes (solved by per-asset-type presets), boolean operations producing dirty geometry (solved by mandatory post-boolean cleanup), and context window bloat during generation sessions (solved by file-based state persistence).

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Procedural Mesh Foundation
**Rationale:** The mesh generation library unblocks every other system. Without real mesh generators for furniture, props, and vegetation, no placement, interior, or scatter system can produce AAA output. The gap analysis identifies this as the single biggest blocker (systemic issue X-01). Architecture research confirms the pure-logic / bpy-guarded split pattern must be enforced from the start.
**Delivers:** 20+ parametric mesh generators (tables, chairs, barrels, chests, shelves, beds, rocks, trees, bushes), material presets with roughness variation (never single float), LOD presets per asset type, boolean cleanup pipeline, silhouette validation.
**Addresses:** FEATURES: Parametric mesh library, furniture generators, vegetation generators, LOD presets, scene budget validator. ARCHITECTURE: Mesh Generator component quality upgrade. STACK: bpy + bmesh pattern enforcement.
**Avoids:** PITFALLS: Placeholder primitives (#1), plastic materials (#2), LOD silhouette destruction (#8), boolean dirty geometry (#9), context window bloat (#10).

### Phase 2: Terrain and Environment
**Rationale:** Buildings sit on terrain. Terrain-building integration (foundations, flattening, height probing) must be solved before town generation. Biome system must exist before vegetation scatter can be biome-aware. The terrain system is already well-structured in the codebase and needs targeted upgrades rather than a rewrite.
**Delivers:** Height-blended splatmap terrain (4-channel with macro variation maps), cliff face mesh overlays (separate from heightmap), biome noise system (OpenSimplex + Whittaker diagram), vegetation scatter with LOD and collection instancing, terrain flattening at building sites with cosine falloff.
**Addresses:** FEATURES: Multi-biome terrain blending, cliff/cave geometry, terrain-conforming foundations, water bodies with shorelines. ARCHITECTURE: Terrain System upgrades, Scatter Engine biome awareness.
**Avoids:** PITFALLS: No vertical terrain (#3), scene budget overflow (#4), terrain-building seam gaps (#6).

### Phase 3: Building and Architecture
**Rationale:** With terrain ready and mesh generators producing real geometry, buildings can be composed from modular kit pieces. Interior room shells need real geometry (not boxes). The modular kit expansion (175 to 300+ pieces) enables both building grammar upgrades and dungeon generation. Kit pieces serve dual purpose (buildings AND dungeons), maximizing ROI.
**Delivers:** Dark fantasy modular kit expansion (300+ pieces across 5 styles), trim sheet authoring (2048x2048 or 4096x4096 per kit), building composition with district-specific parameters, interior room shells with wall thickness/doorways/window recesses, storytelling prop placement system, corruption-aware building variants.
**Addresses:** FEATURES: Modular kit with snap validation, building variety, interior room shells, market stalls, district zoning, corruption zone visual transformation. ARCHITECTURE: Building Grammar upgrade, Modular Kit expansion, Interior System.
**Avoids:** PITFALLS: Cookie-cutter buildings (#5).

### Phase 4: Pipeline Integration and Starter Town
**Rationale:** All individual systems must be connected into the full map composition pipeline. Multi-backend AI generation (Tripo + Hunyuan + Rodin) needs style normalization so procedural and AI assets look consistent in the same scene. The starter town is the integration test that validates the entire pipeline end-to-end.
**Delivers:** Multi-backend AI generation integration with unified art style validation, style normalization pipeline (de-lighting, palette enforcement, texel density standardization), starter town generation (10-15 buildings with district variety, market area, fortifications, furnished interiors), Unity Addressables streaming setup, state persistence system for long generation sessions.
**Addresses:** FEATURES: Starter town, scene-level budgets, WFC dungeons, interactive prop states. ARCHITECTURE: World Composer integration, AI Generation multi-backend, state persistence.
**Avoids:** PITFALLS: Style mismatch between AI and procedural (#7), context window bloat (#10).

### Phase 5: Research and Polish
**Rationale:** Deep AAA technique analysis and performance optimization after the pipeline is functional. Research phase by nature -- document techniques from Skyrim, Witcher 3, AC Valhalla, Elden Ring and implement applicable patterns. Performance profiling with real populated town scene.
**Delivers:** AAA technique documentation, performance optimization pass (draw call reduction, texture streaming tuning, occlusion culling validation), visual quality review against benchmark games, additional polish features (L-system roads, street geometry, town walls).
**Addresses:** FEATURES: L-system road networks, street geometry, town wall/gate system, weapon type expansion. STACK: Performance targets validated against real scenes.

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Cannot scatter vegetation on terrain without vegetation mesh generators. Cannot validate terrain performance without scene budget tools.
- **Phase 2 before Phase 3:** Buildings require terrain-conforming foundations. Terrain biome system must exist before district-specific architecture makes sense.
- **Phase 3 before Phase 4:** Buildings and interiors must exist before the starter town can compose them. WFC dungeons need kit pieces.
- **Phase 4 before Phase 5:** Integration validates the pipeline works end-to-end. Research and optimization require a working system to analyze.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Geometry Nodes 5.1 Repeat Zone / Closure / Bake node patterns need hands-on validation with actual building generation in Blender 5.1. Official docs verified but no hands-on testing done. Also: Hunyuan3D 2.1 self-hosting needs validation on user's GPU hardware (6GB VRAM minimum).
- **Phase 3:** World Labs Marble integration complexity is uncertain. Start with compose_interior pipeline, add Marble for hero rooms only after basic interior pipeline works.
- **Phase 5:** By definition -- deep AAA technique analysis is the phase purpose. Requires benchmarking against shipped games.

Phases with standard patterns (skip research-phase):
- **Phase 2:** Terrain generation, erosion, biome mapping are well-established in the codebase with proven algorithms (OpenSimplex, hydraulic/thermal erosion). Height-blend splatmap algorithm is documented.
- **Phase 4:** Multi-backend AI integration follows existing Tripo pipeline pattern. Unity Addressables streaming has standard setup.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified against official docs (Blender 5.1, Tripo, Hunyuan3D, Rodin, Unity URP), AAA studio references, and existing project research. AI API pricing cross-verified. |
| Features | HIGH | Table stakes derived from AAA benchmark games (Skyrim, Witcher 3, AC Valhalla, Elden Ring, Fable). Differentiators unique to VeilBreakers (corruption system, 10 brands). Gap analysis cross-referenced with game feature comparison table. |
| Architecture | HIGH | Modular kit pattern is industry standard (Bethesda, FromSoftware, CDPR). Hybrid bpy + Geo Nodes approach confirmed correct. Existing codebase architecture analyzed against 100+ handler files and 838KB of procedural generator code. Pure-logic/bpy-guarded split already proven with 13,616 tests. |
| Pitfalls | HIGH | 10 pitfalls verified against existing gap analysis (67 gaps), project memory files (visual quality crisis, template quality audit at 72% AAA readiness), and AAA production post-mortems. Recovery strategies documented with cost estimates. |

**Overall confidence:** HIGH

### Gaps to Address

- **Geometry Nodes 5.1 hands-on validation:** Repeat Zones, Closures, and Bake nodes need testing with actual building generation to confirm they work as documented. Official docs were verified but no hands-on testing done during research. Validate in Phase 1.
- **Hunyuan3D 2.1 self-hosting on user hardware:** 6GB VRAM minimum requirement needs validation against user's GPU. If insufficient, fall back to API-only approach using Tripo for bulk (higher cost but zero local requirements). Validate before Phase 1 begins.
- **World Labs Marble quality after pipeline processing:** 600K tri GLB output from Marble needs full cleanup -> retopo -> UV -> retexture pipeline. Uncertain whether quality justifies integration complexity for non-hero rooms. Start with compose_interior, evaluate Marble for Phase 3.
- **Dark fantasy style consistency across AI backends:** Tripo, Hunyuan, and Rodin have different style tendencies. Prompt engineering may not achieve consistent dark fantasy aesthetic across all three. Test with a small set of props from each backend early in Phase 4.
- **Performance at town scale with real scene:** 2-6M triangle budget at 60fps is theoretical. Actual performance depends on draw call count (shared materials via trim sheets), material complexity (SRP Batcher effectiveness), and culling effectiveness (occlusion data). Profile with a real populated town in Phase 4.

## Sources

### Primary (HIGH confidence)
- Blender 5.1 Geometry Nodes official docs -- Repeat Zones, For Each Element, Closures, Bake, Array, Scatter on Surface
- Tripo3D API platform docs -- v3.0 quad mesh mode, auto-rigging, PBR materials
- Hunyuan3D-2.1 GitHub (Tencent) -- 8K PBR, PolyGen quad topology, 6GB VRAM
- Hyper3D Rodin Gen-2 API docs -- 10B params, quad mesh, quality tiers
- Unity URP 14.0 documentation -- Forward+ rendering, SRP Batcher, LOD Groups
- `.planning/research/AI_3D_GENERATION_TOOLS_RESEARCH.md` -- 15+ AI 3D tools compared
- `.planning/research/AI_INTERIOR_GENERATION_RESEARCH.md` -- World Labs Marble, interior generation tools
- `.planning/research/AAA_BEST_PRACTICES_COMPREHENSIVE.md` -- Triangle budgets, LOD, modular kit design
- `.planning/research/AAA_QUALITY_ASSETS.md` -- Per-asset-type polygon budgets, PBR quality standards
- `.planning/research/MAP_BUILDING_TECHNIQUES.md` -- UE terrain blending, modular kits, level streaming
- `.planning/research/TEXTURING_ENVIRONMENTS_RESEARCH.md` -- Splatmap blending, anti-tiling, weathering
- `.planning/research/AAA_MAP_WORLD_DUNGEON_RESEARCH.md` -- WFC dungeons, L-system roads, Whittaker biomes
- `.planning/research/3d-modeling-gap-analysis.md` -- 67 gaps identified, systemic issue X-01

### Secondary (MEDIUM confidence)
- Joel Burgess, Skyrim Modular Level Design (GDC 2013) -- Grid-snapped kit pieces, ~200 pieces serve entire game
- CD Projekt Red, Witcher 3 Novigrad architecture -- Modular building kits hand-assembled
- Ubisoft, AC Valhalla World Building -- Procedural terrain blending with hand-placed POIs
- FromSoftware, Elden Ring world design -- Legacy dungeons hand-crafted, open world modular
- Polycount Wiki -- Triangle budgets, LOD strategy, modular kit design
- Google Filament PBR documentation -- Roughness variation importance
- DOOM 2016 Graphics Study (Adrian Courreges) -- Scene budget management
- `project_visual_quality_crisis.md` -- "Generated 3D is primitive boxes with flat colors"
- `project_v5_gap_analysis.md` -- 192 gaps: 63 equipment, 83 world, 46 visual

### Tertiary (LOW confidence)
- World Labs Marble -- Available now but quality after full pipeline processing untested
- Scenario.gg PBR textures -- API exists but not yet integrated; custom model training quality untested
- Guerrilla Games GPU-based procedural placement -- Technique documented but implementation details sparse

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
