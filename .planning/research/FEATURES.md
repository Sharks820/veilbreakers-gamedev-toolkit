# Feature Research: AAA Procedural 3D Architecture

**Domain:** AAA procedural 3D content generation for open-world dark fantasy RPG
**Milestone:** v4.0 -- AAA Procedural 3D Architecture
**Researched:** 2026-03-30
**Confidence:** MEDIUM-HIGH (training data on AAA game techniques cross-referenced with existing toolkit gap analysis and prior research files)

---

## Scope

This research covers features required for the v4.0 milestone: upgrading the VeilBreakers MCP toolkit from placeholder-grade procedural generation (cubes, cones, spheres) to AAA-quality procedural 3D architecture benchmarked against Skyrim, Fable, AC Valhalla, Witcher 3, and Elden Ring. The focus areas are:

1. **Procedural city/town generation** -- Street geometry, market stalls, fortifications, district zoning
2. **Interior mapping and furnishing** -- Room shells, prop meshes, interactive states, storytelling props
3. **Terrain/building mesh integration** -- Seamless blending, cliff faces, cave entrances, foundation conforming
4. **Biome-aware generation** -- Corruption zones, seasonal variation, Whittaker diagram placement, wind moisture
5. **Road/path/shop mapping** -- L-system roads, terrain-deforming paths, signage, wayfinding
6. **LOD and optimization strategies** -- Scene budgets, LOD chains, occlusion, streaming chunks
7. **Storyline-aware building placement** -- Narrative-driven layouts, quest markers, environmental storytelling

Benchmark games:

| Game | Key Technique |
|------|-------------|
| **Skyrim** | Modular kit system (grid-snapped pieces), ~200 kit pieces serve entire game, Radiant Story for procedural quest variation |
| **Witcher 3** | Hand-crafted Novigrad with modular building kits, interior/exterior streaming, POI density rules (no empty space) |
| **AC Valhalla** | Procedural world blending, biome transitions, settlement building, massive scale with performance budgets |
| **Elden Ring** | Legacy dungeons (hand-crafted) + open world (modular), distinct biome identity per region, landmark visibility |
| **Fable** | Region-based world, hero interaction with environment, reactive world changes based on player alignment |

---

## Table Stakes (Must Have or Users Notice Missing)

Features players expect from any AAA open-world dark fantasy game. Missing any of these makes the world feel unfinished or artificial.

### T1. Procedural Mesh Foundation

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Actual mesh geometry, not primitives** | Every shipped game uses real geometry. Cubes/cones/spheres as furniture and vegetation scream "prototype." | HIGH | 67 gaps identified in gap analysis. Systemic issue X-01: placement systems output cubes instead of meshes. Need parametric generators for 20+ prop types. |
| **Parametric furniture generators** | Tables with legs, chairs with backs, beds with frames, barrels with staves, chests with lids. Every interior needs these. | HIGH | 16 room types produce placeholder cubes currently. Need at minimum: table, chair, barrel, crate, chest, shelf, bed, stool, bench, desk, wardrobe, cauldron. |
| **Vegetation mesh generators** | Trees with trunk/branch structure, bushes with leaf clusters, grass billboard strips, rocks with irregular surfaces. Open worlds without real vegetation look barren. | HIGH | Current: tree=cone, bush=icosphere, grass=plane, rock=cube. Need L-system trees (already have `vegetation_tree`), rock formation generators, leaf card systems, biome-specific variants. |
| **Modular architectural kit pieces** | Walls, floors, ceilings, doorways, windows, columns, stairs that snap together on a grid. Skyrim uses ~200 kit pieces for its entire game. | HIGH | `generate_modular_kit` exists but lacks connection validation. Need snap-to-grid geometry with standardized dimensions (4m x 4m x 3.5m cells per Skyrim GDC 2013). |
| **Parametric weapon generators (complete set)** | At minimum 15 weapon types with separate submesh components (blade, guard, grip, pommel). Dark fantasy RPGs need weapon variety. | MEDIUM | 7 types exist. Missing: hammer, spear, crossbow, greatsword, halberd, flail, wand, scythe. Need component separation for material assignment. |

### T2. City/Town Infrastructure

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Street geometry with surfaces** | Roads are the connective tissue of settlements. Flat quads feel like debug visualization. Need cobblestone, dirt, gravel surfaces with curbs. | MEDIUM | Current: road cells as flat 2D tiles. Need road mesh generation with surface texture, width variation, intersection handling, cosine-blended terrain deformation (UE Landscape Spline approach). |
| **District zoning with distinct architecture** | Market districts look different from noble quarters. Players navigate by visual district identity. | MEDIUM | Voronoi district zoning exists but buildings use same grammar. Need per-district building style (market: half-open stalls, noble: stone manors, slums: lean-tos, religious: spires). |
| **Market stall/shop front generation** | Towns need commerce. Stalls with canopies, display counters, hanging goods. Without these, towns feel like residential blocks. | MEDIUM | Zero support. Need canopy mesh (cloth over frame), counter geometry, hanging merchandise hooks, signage attachment points. |
| **Town wall and gate system** | Medieval towns have walls. Players expect fortifications as navigation landmarks and gameplay boundaries. | MEDIUM | Castle walls exist but town-specific walls (irregular boundary, multiple gates, guard towers at intervals) do not. Need perimeter-following wall generation. |
| **Building variety within style** | Cookie-cutter buildings break immersion. Skyrim uses modular kits to create variety from ~200 pieces. | HIGH | Building grammar produces 5 styles but similar output per style. Need parameter space expansion: roof angle, stories, wing count, dormer placement, chimney, window pattern. |

### T3. Interior Systems

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Walkable interior geometry** | Players enter buildings. Interior needs walls, floor, ceiling with doorways, windows, and proper scale. | HIGH | `compose_interior` orchestrates room shells but geometry is box primitives. Need proper room shells with wall thickness, doorway openings, window recesses, ceiling beams. |
| **Furniture placement with purpose** | Furniture follows function: bed against wall, table in center, shelves against walls. Random placement looks wrong. | MEDIUM | Room configs specify type/position but not placement rules. Need constraint-based placement: wall-hugging, center-clearing, traffic-flow awareness. |
| **Interactive prop states** | Chests open, doors swing, levers pull. Static props are non-interactive decoration. | HIGH | `create_breakable` gives intact/damaged for 5 types. Need open/closed/locked for chests, open/closed/broken for doors, up/down for levers, raised/lowered for drawbridges. Each needs pivot points and animation ranges. |
| **Interior lighting points** | Rooms need torches, candles, fireplaces. Without light sources, interiors are dark boxes. | LOW | Need empty markers at sconce, fireplace, candle positions with metadata for Unity light placement. |
| **Occlusion zones per room** | Only the room the player is in should render. Without occlusion, 20 interior rooms kills framerate. | MEDIUM | Door triggers and occlusion zones planned in `compose_interior`. Need proper implementation with Unity streaming integration. |

### T4. Terrain and Biome Integration

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-biome terrain transitions** | Walking from forest to swamp should be gradual. Sharp biome boundaries look like debug output. | HIGH | Current: per-face altitude/slope assignment. Need splatmap-based blending with height-based transitions. Height blend algorithm documented in MAP_BUILDING_TECHNIQUES.md. |
| **Cliff face and vertical geometry** | Dramatic cliff faces, overhangs, cave mouths. Heightmap-only terrain cannot represent vertical features. | HIGH | Heightmaps are 2.5D (one height per XY). Need separate mesh objects for vertical features placed at terrain edges. |
| **Terrain-conforming buildings** | Buildings should follow terrain slope or flatten terrain beneath them. Floating buildings break immersion immediately. | MEDIUM | No terrain-conforming foundation generation exists. Need: terrain sampling under building footprint, foundation walls to fill gaps, or terrain flattening with cosine falloff blend. |
| **Corruption zone visual transformation** | VeilBreakers has 0-100% corruption. Corrupted areas must look corrupted: darkened vegetation, cracked earth, twisted architecture. | MEDIUM | `generate_overrun_variant` exists for basic overlay. Need: vegetation state changes, ground texture darkening, building decay escalation, corruption boundary transition zone. |
| **Water bodies with shorelines** | Lakes, rivers, ocean need water surfaces with foam lines, depth coloring, and shore transitions. | MEDIUM | `create_water` exists with basic water plane. Need shoreline detection, foam line mesh, depth gradient, river bank geometry. |

### T5. Performance and Optimization

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Scene-level polygon budgets** | A room with 50 under-budget props can still exceed frame budget. Need per-scene tracking. | MEDIUM | `game_check` validates individual objects. Need scene budget manager that sums all visible objects against target (500K tris indoor, 2M outdoor). |
| **LOD chain generation per asset type** | Objects at distance need lower detail. Without LOD, far objects waste GPU. Every shipped game uses LOD. | MEDIUM | `generate_lods` exists with ratio-based reduction. Need per-asset-type presets: hero 50K/25K/12K/5K, prop 3K/1.5K/500, building 15K/7K/3K. Budgets in AAA_QUALITY_ASSETS.md. |
| **Occlusion culling data** | Interior rooms, dungeon corridors, city alleys must cull unseen geometry. | MEDIUM | Unity handles runtime occlusion but needs properly marked occluders/occludees and baking data. Export occlusion volumes with interiors. |
| **Terrain chunking for streaming** | Large terrain as single mesh is unstreamable. Need chunked export for Unity streaming. | MEDIUM | No terrain chunking tool. Need heightmap export as tiles (512x512 per chunk) with seamless edge matching. Unity terrain sectors as target format. |

---

## Differentiators (Competitive Advantage)

Features that set VeilBreakers apart from typical procedural generation. Not expected by players, but make the world feel handcrafted.

### D1. Storyline-Aware Generation

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Corruption-aware biome progression** | Corruption does not just tint terrain -- it changes what generates. Corrupted forest spawns different trees, creatures, props. Unique to VeilBreakers. | HIGH | Need per-corruption-level biome overrides: 0% healthy forest, 50% dying/withered, 100% dead trees/void-touched geometry. Corruption parameter threaded through all generators. |
| **Narrative debris layer** | After story events, the world shows scars: battle damage, burned sections, abandoned camps. | MEDIUM | `add_storytelling_props` places narrative clutter. Extend with event-state-aware prop sets: pre-battle, during-battle, post-battle variants. |
| **Quest-driven building placement** | Place quest-relevant buildings near quest-giver NPCs. Makes world feel designed, not random. | HIGH | Requires quest dependency graph feeding into building placement priority. Defer to v5.0. |

### D2. Architectural Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Non-cookie-cutter building design** | Buildings influenced by local materials, climate, wealth, function. Mountain town uses stone; forest town uses timber. | HIGH | Need location-context parameters: biome, elevation, resource proximity, wealth level. Feed into building grammar for material selection, roof style, wall construction. |
| **Defensible settlement layout** | Towns in dangerous areas (near dungeons, corruption) have more fortifications, narrower streets, watchtowers. Safe areas are more open. | MEDIUM | Need threat-level parameter per location driving wall presence, tower density, street width, gate count, guard post placement. |
| **Economic zone generation** | Towns near mines have smithies; near water have docks; on trade routes have large markets. Economic logic makes world feel lived-in. | MEDIUM | Need resource proximity detection: nearest biome type, water, dungeon. Drive district specialization from this. |

### D3. Visual Quality Systems

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Cross-asset silhouette validation** | Every asset distinguishable from every other at gameplay distance. A mace and hammer must read differently at 20m. | MEDIUM | `silhouette_test` checks one asset. Need batch comparison: generate all silhouettes, compute overlap metrics, flag conflicts. |
| **Art style consistency checker** | AI-generated assets vary in style. Geometric checker validates shared edge sharpness, detail density, proportion language. | HIGH | Needs reference geometry library and comparison metrics. Defer to v5.0. |
| **Weather-affected mesh variants** | Snow on roofs, icicles on eaves, rain-wet surfaces. Seasonal variation makes world feel alive. | MEDIUM | Mostly shader/material work on Unity side. Blender needs snow cap geometry, icicle meshes, material presets per weather state. |
| **Smart material system** | Procedural materials that respond to context: age, weather, corruption, damage state. Like Substance Painter smart materials in Blender. | MEDIUM | Curvature + AO + noise-driven masking. `smart_material` action exists in blender_quality. Extend with context parameters. |

### D4. Advanced Procedural Techniques

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **WFC dungeon generation** | Wave Function Collapse produces more organic, varied layouts than BSP. Encodes architectural style rules directly. | HIGH | Algorithm fully documented in AAA_MAP_WORLD_DUNGEON_RESEARCH.md. ~150 lines Python. Produces tile-based layouts mapping to modular kit pieces. |
| **Cyclic dungeon generation** | Lock-and-key cycles, shortcut loops, secret paths. Dark Souls design language. Produces dungeons that FEEL designed. | HIGH | Algorithm in AAA_MAP_WORLD_DUNGEON_RESEARCH.md section 2.2. 24 cycle types from Unexplored. |
| **L-system road networks** | Roads that grow organically like medieval paths, not grid-planned. Follows terrain contours, avoids steep slopes. | MEDIUM | Algorithm in AAA_MAP_WORLD_DUNGEON_RESEARCH.md section 3.1. Use "organic" axiom with angle randomization (70-110 degrees). |
| **Agent-based city growth** | Simulate city expansion over time for organic district formation. Roads extend, builders fill lots, districts emerge. | HIGH | CityGrowthSimulation in section 3.2. More believable than Voronoi zoning alone. Defer to v5.0. |

---

## Anti-Features (Things to Deliberately NOT Build)

| Anti-Feature | Why It Seems Good | Why Avoid | What to Do Instead |
|--------------|-------------------|-----------|-------------------|
| **Fully autonomous city generation** | "Press button, get city" | Without art direction, procedural cities look generic. Witcher 3's Novigrad took years of hand-crafting with modular kits. Full autonomy produces detectable repetition. | Generate layouts and blockouts procedurally, allow human-guided refinement. Modular kits where each piece is hand-quality. |
| **Real-time procedural generation at runtime** | "Infinite content!" | Runtime proc gen adds CPU cost, requires streaming infrastructure, produces LOD pop-in, makes QA impossible. Minecraft works because its style is intentionally blocky. | Generate at development time in Blender, export as static assets. Procedural generation for authoring, not runtime. |
| **Neural radiance field / Gaussian splat environments** | "Photorealistic 3D capture!" | Not game-ready: no collision, no LOD, no material separation, huge memory, no animation. World Labs Marble outputs 600K tri meshes needing full reprocessing. | Generate clean polygon meshes with proper topology. Use Tripo3D for individual props, not environment capture. |
| **Cross-engine abstraction** | "Works in Unity AND Unreal!" | Each engine has fundamentally different terrain, material, lighting systems. Abstracting produces mediocre output for both. | Build for Unity URP specifically. Export FBX/glTF with Unity naming (_LOD0, _LOD1). Optimize for URP material pipeline. |
| **Photogrammetry-quality assets** | "Real-world scanned quality!" | Massive textures (10K-100K per object), incompatible with dark fantasy style, requires proprietary pipelines. | AI generation (Tripo3D) + hand-tuned PBR + dark fantasy palette enforcement. Quality from art direction, not scan fidelity. |
| **Procedural quest/narrative generation** | "Infinite quests like Radiant Story!" | Radiant quests are widely criticized as Skyrim's weakest feature. Procedural quests feel repetitive and meaningless. | Focus on world geometry quality. Quest systems are separate. Storyline-aware placement (which buildings where) is the right scope boundary. |
| **Physics-based destruction for all geometry** | "Every wall breakable!" | Pre-fractured meshes per asset, physics simulation, debris particles. Enormous performance cost. Only Battlefield/Fortnite invest here. | Selective destruction via `create_breakable` for predefined props (crates, barrels, pots). Structures remain static. |
| **Per-building unique textures** | "Every building looks unique!" | Memory explosion: 100 buildings x 6 textures x 2048px = GBs of VRAM. | Trim sheets: 1-2 per architectural style (4096x4096), shared across all buildings. UV-mapped to trim sheet layout. |
| **Virtual Texturing** | "Infinite texture detail!" | URP does not support VT. HDRP-only feature. | Texture streaming via Addressables, LOD-appropriate resolution selection. |
| **Houdini integration** | "Industry standard procedural!" | $4,495/year. Blender Geometry Nodes covers equivalent capability for our scope. | Geo Nodes + bpy scripting. Already decided in Key Decisions. |

---

## Feature Dependencies

```
[Parametric Mesh Foundation]
    |
    +--enables--> [Furniture Generators] (table, chair, barrel, chest, shelf, bed)
    |                 |
    |                 +--enables--> [Interior Furnishing] (place real meshes in rooms)
    |                 |                 |
    |                 |                 +--requires--> [Room Shell Geometry] (walls, floors, ceilings)
    |                 |                 +--requires--> [Interactive Prop States] (open/closed/locked)
    |                 |                 +--requires--> [Occlusion Zones] (per-room culling)
    |                 |
    |                 +--enables--> [Market Stall Generation] (shop fronts, canopies)
    |
    +--enables--> [Vegetation Generators] (trees, bushes, grass, rocks)
    |                 |
    |                 +--requires--> [Biome Rules System] (what grows where)
    |                 |                 |
    |                 |                 +--requires--> [Corruption Overrides] (corruption-aware variants)
    |                 |
    |                 +--enables--> [Terrain Scatter] (place vegetation on terrain)
    |
    +--enables--> [Modular Kit Pieces] (walls, floors, doorways, stairs)
    |                 |
    |                 +--enables--> [Building Grammar v2] (assemble from real pieces)
    |                 |                 |
    |                 |                 +--requires--> [Terrain Conforming] (foundations follow terrain)
    |                 |                 +--requires--> [District Style Parameters] (per-district materials/shapes)
    |                 |
    |                 +--enables--> [WFC Dungeon Generation] (tile-based from kit pieces)
    |                 +--enables--> [Interior Room Shells] (room geometry from kit pieces)
    |
    +--enables--> [Weapon Type Expansion] (8 missing weapon types)

[Terrain Foundation]
    |
    +--requires--> [Height-based Biome Blending] (splatmap transitions)
    |                 |
    |                 +--requires--> [Whittaker Diagram System] (temperature + moisture biomes)
    |
    +--requires--> [Cliff/Cave Mesh Generation] (vertical geometry beyond heightmap)
    |
    +--requires--> [L-System Road Networks] (organic road growth following terrain)
    |                 |
    |                 +--enables--> [Street Geometry] (cobblestone, curbs, intersections)
    |                 +--enables--> [Terrain Deformation Under Roads] (cosine-blended carving)
    |
    +--requires--> [Terrain Chunking] (streamable export tiles)

[LOD and Optimization]
    |
    +--requires--> [Per-Asset-Type LOD Presets] (character, prop, building budgets)
    +--requires--> [Scene Budget Validator] (cross-object polygon tracking)
    +--requires--> [Occlusion Data Export] (Unity culling integration)

[Storyline Integration]
    |
    +--enhances--> [Corruption Zone Transformation] (0-100% visual progression)
    +--enhances--> [Narrative Debris Layer] (post-event world state)
    +--enhances--> [Economic Zone Generation] (resource-proximity building logic)
```

### Critical Dependency Notes

1. **Parametric Mesh Foundation unblocks everything.** Without actual mesh generators, no other system can produce AAA output. Single biggest blocker (gap X-01). Every other feature depends on having real geometry to place.

2. **Furniture generators depend on mesh foundation but block interiors.** Interior furnishing is the second most impactful feature (affects 16 room types). Must come after mesh foundation but before advanced interior features.

3. **Modular kit pieces serve buildings AND dungeons.** One kit system serves both exterior building grammar and interior dungeon generation. Skyrim uses this approach (~200 pieces serve both). Dual-use makes kit pieces the highest ROI investment.

4. **Terrain blending requires splatmap generation in Blender.** Current biome assignment is per-cell index. Need RGBA weight maps for Unity terrain import. Blender-side pipeline change.

5. **LOD chains depend on target budgets per asset type.** Budget tables exist in AAA_QUALITY_ASSETS.md. Encode as presets in the LOD generation tool.

6. **Corruption awareness must thread through ALL generation.** Not a separate system -- it modifies parameters in vegetation, terrain, buildings, props, and lighting. The corruption parameter needs to be a standard argument in every generator.

---

## MVP Definition

### v4.0 Launch With (Phase Core)

Minimum for "AAA procedural 3D architecture" milestone:

1. **Parametric mesh generation library** -- 20+ prop generators replacing cubes with real geometry. Tables, chairs, barrels, chests, shelves, beds, rocks, trees, bushes. Single most impactful deliverable.
2. **Modular kit piece system with snap validation** -- Wall, floor, ceiling, doorway, stair, column pieces on standardized grid with connection point validation. Enables buildings and dungeons.
3. **Interior room shells with real geometry** -- Walls with thickness, doorways with frames, window recesses, ceiling beams. Not box primitives.
4. **Multi-biome terrain blending** -- Splatmap-based transitions using height-blend algorithm. No more hard biome lines.
5. **Terrain-conforming building foundations** -- Buildings follow terrain slope without floating. Foundation walls fill gaps.
6. **Per-asset-type LOD presets** -- Budget tables from AAA_QUALITY_ASSETS.md encoded as generator defaults. One-call LOD chain generation.
7. **Starter town for testing** -- Complete gameplay-ready settlement with district variety, market area, fortifications, and furnished interiors. Validates all systems together.

### v4.0 Add After Core (Phase Polish)

8. **WFC dungeon generation** -- Wave Function Collapse as alternative to BSP for more organic dungeons.
9. **Corruption zone visual system** -- Corruption parameter modifying vegetation, terrain, and building appearance.
10. **L-system road networks** -- Organic road generation replacing waypoint-based system.
11. **Street geometry with surfaces** -- Cobblestone, dirt, gravel road meshes replacing flat quads.
12. **Market stall/shop front generation** -- Commerce-specific building additions.
13. **Interactive prop states** -- Open/closed/locked chests, doors, levers.

### Defer to v5.0

14. **Agent-based city growth simulation** -- Complex, marginal improvement over Voronoi zoning for v4.0.
15. **Art style consistency checker** -- Requires reference geometry library and comparison metrics.
16. **Ecosystem-aware vegetation competition** -- Growth simulation overkill for v4.0. Poisson disk + biome rules is sufficient.
17. **Quest-driven building placement** -- Requires quest system integration. v4.0 handles geometry, not game systems.
18. **Weather-affected mesh variants** -- Mostly shader work. Snow/icicle geometry can wait.
19. **AI-directed building variation** -- LLM integration for room composition. Start with rule-based.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Phase |
|---------|------------|---------------------|----------|-------|
| Parametric mesh library (20+ generators) | CRITICAL | HIGH | P0 | Core |
| Modular kit pieces with snap validation | CRITICAL | HIGH | P0 | Core |
| Interior room shells (real geometry) | CRITICAL | MEDIUM | P0 | Core |
| Multi-biome terrain blending | HIGH | MEDIUM | P0 | Core |
| Terrain-conforming building foundations | HIGH | MEDIUM | P0 | Core |
| LOD presets per asset type | HIGH | LOW | P0 | Core |
| Scene-level polygon budget validator | HIGH | LOW | P0 | Core |
| Starter town (integration test) | HIGH | MEDIUM | P1 | Core |
| Interactive prop states (open/closed) | HIGH | MEDIUM | P1 | Polish |
| Cliff face and cave entrance geometry | HIGH | HIGH | P1 | Polish |
| Corruption-aware generation parameter | HIGH | MEDIUM | P1 | Polish |
| Vegetation mesh generators | HIGH | HIGH | P1 | Core |
| WFC dungeon generation | MEDIUM | MEDIUM | P2 | Polish |
| L-system road networks | MEDIUM | MEDIUM | P2 | Polish |
| Street geometry with surfaces | MEDIUM | MEDIUM | P2 | Polish |
| Market stall generation | MEDIUM | LOW | P2 | Polish |
| Weapon type expansion (8 types) | MEDIUM | MEDIUM | P2 | Polish |
| District-specific architecture | MEDIUM | MEDIUM | P2 | Polish |
| Town wall/gate system | MEDIUM | MEDIUM | P2 | Polish |
| Occlusion data export | MEDIUM | MEDIUM | P2 | Polish |

**Priority key:**
- P0: Must have for v4.0 -- without these the world does not look AAA
- P1: Should have -- difference between "good" and "great"
- P2: Nice to have -- adds polish and depth

---

## Competitor Feature Analysis

| Feature | Skyrim | Witcher 3 | AC Valhalla | Elden Ring | VB v3 (current) | VB v4 (target) |
|---------|--------|-----------|-------------|------------|-----------------|----------------|
| Modular kit pieces | 200+ grid-snapped | Custom modular buildings | Large modular set | Hand-crafted + modular | 7 weapon types, building grammar | Full kit system with snap validation |
| Interior cell system | Separate interior cells | Interior/exterior streaming | Building interiors | Legacy dungeon interiors | Room configs (placeholder cubes) | Real room geometry with furnishing |
| Terrain blending | Per-region splatmaps | Hand-painted terrain | Procedural biome blend | Distinct biome zones | Hard altitude/slope boundaries | Height-blended splatmap transitions |
| Biome variety | 5 main biomes | 7 distinct regions | Multiple climate zones | 6+ distinct regions | 6 presets (simple rules) | Whittaker diagram + corruption overrides |
| City layout | 5 major cities, hand-placed | Novigrad (handcrafted modular) | Settlement building | Limited towns | Voronoi districts (abstract) | District-zoned real geometry |
| LOD system | 3-4 LOD levels per asset | Multiple LOD levels | Aggressive LOD + culling | Distance-based LOD | Basic ratio-based LOD | Per-asset-type LOD presets |
| Vegetation | SpeedTree forests | Hand-placed foliage | Procedural scatter | Hand-placed per region | Cone/sphere/cube placeholders | L-system trees + biome-aware scatter |
| Corruption/decay | N/A | N/A (war damage hand-placed) | Settlement destruction | Scarlet rot zones | Basic overrun variant | Corruption-parameter-driven generation |

---

## Sources

### Primary Research (HIGH confidence -- verified against existing toolkit code)
- `.planning/research/3d-modeling-gap-analysis.md` -- 67 gaps across 10 categories, systemic issue X-01
- `.planning/research/AAA_MAP_WORLD_DUNGEON_RESEARCH.md` -- Terrain erosion, city generation L-systems, WFC dungeons, cyclic dungeons, Whittaker biomes, vegetation scatter
- `.planning/research/MAP_BUILDING_TECHNIQUES.md` -- UE terrain blending, ProBuilder CSG, Houdini terrain tools, modular kit design, foliage painting
- `.planning/research/AAA_QUALITY_ASSETS.md` -- Polygon budgets per asset type, AI post-processing pipeline, PBR quality standards
- `.planning/research/AI_INTERIOR_GENERATION_RESEARCH.md` -- World Labs Marble, Meta WorldGen, Holodeck, interior generation options
- `.planning/PROJECT.md` -- v4.0 milestone requirements MESH-01 through PIPE-01

### Game Technique References (MEDIUM confidence -- from training data and GDC talks)
- Joel Burgess, Skyrim Modular Level Design (GDC 2013) -- Grid-snapped kit pieces, ~200 pieces serve entire game
- CD Projekt Red, Witcher 3 Novigrad architecture -- Modular building kits hand-assembled for interiors
- Ubisoft, AC Valhalla World Building -- Procedural terrain blending with hand-placed POIs
- FromSoftware, Elden Ring world design -- Legacy dungeons hand-crafted, open world modular
- Level Design Book, Modular Kit Design -- Kit piece types, naming conventions, grid metrics

### Algorithm References (HIGH confidence -- cross-referenced with implementations)
- Parish & Mueller 2001, Procedural Modeling of Cities -- L-system road networks
- Maxim Gumin, WaveFunctionCollapse -- Constraint-solving tile generation
- Joris Dormans, Cyclic Dungeon Generation -- Lock-and-key cycles for gameplay
- Sebastian Lague, Hydraulic Erosion -- Particle-based droplet simulation
- Vanegas et al. 2012, Procedural Generation of Parcels -- OBB lot subdivision

---
*Feature research for: AAA Procedural 3D Architecture (v4.0)*
*Researched: 2026-03-30*
