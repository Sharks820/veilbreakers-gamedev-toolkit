# VeilBreakers 3D Modeling Gap Analysis
## Deep Dive: What AAA Dark Fantasy Action RPG Needs vs. What We Have

**Date**: 2026-03-21
**Scope**: All Blender MCP tools (15 compound tools, ~100+ operations)
**Files Analyzed**:
- `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` (1900+ lines)
- `Tools/mcp-toolkit/blender_addon/handlers/` (30 files)
- `.claude/skills/game-developer.md`

---

## Severity Legend

| Rating | Meaning |
|--------|---------|
| **CRITICAL** | Would block production -- cannot ship without this |
| **HIGH** | Would significantly reduce quality below AAA bar |
| **MEDIUM** | Would be nice to have, workaround exists |

---

## 1. CHARACTER MODELING

### What We Have
- `asset_pipeline generate_3d`: Tripo3D text/image-to-3D (AI-generated meshes)
- `asset_pipeline cleanup`: Auto repair + UV + PBR on AI model
- `blender_mesh retopo`: Quadriflow retopology with target face count
- `blender_mesh analyze`: A-F topology grading
- `blender_rig analyze_mesh`: Proportion analysis, template recommendation
- `blender_rig apply_template`: Rigify templates (humanoid/quadruped/bird/dragon/insect/serpent/floating/amorphous)
- `blender_rig add_shape_keys`: Expression/damage shape keys
- `asset_pipeline split_character`: Modular body splitting by vertex groups (EQUIP-03)
- `asset_pipeline fit_armor`: Surface deform + weight transfer for armor fitting (EQUIP-04)

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| C-01 | **Body proportion validation system** | **CRITICAL** | No tool to enforce hero vs. monster vs. NPC scale ratios. A hero at 1.8m, a boss at 4m, an NPC at 1.7m -- nothing validates these. `rig_analyze` checks aspect ratios for template recommendation but does not enforce game-world scale constraints. Production needs a "character scale spec" with enforced height ranges per archetype. |
| C-02 | **Face topology checker** | **HIGH** | `mesh analyze` grades overall topology (ngons, non-manifold, poles) but has zero face-specific checks: no edge loop detection around eyes/mouth, no deformation zone analysis for facial animation. Without proper edge loops, facial rigs produce artifacts. Tripo3D outputs have random face topology -- cleanup does not fix this. |
| C-03 | **Hand/foot detail enforcement** | **HIGH** | No validation that hands have separate fingers or feet have proper topology for walk deformation. Tripo3D often produces mitten-hands. The `retopo` action (Quadriflow) cannot enforce finger separation -- it optimizes globally. |
| C-04 | **Hair card mesh generation** | **CRITICAL** | Zero support. No tool generates hair card strips (the actual technique used in AAA games). Hair cards are planar mesh strips with alpha-tested hair textures arranged around the head. This requires: card placement curves, strand grouping, UV layout for hair texture atlases, and proper normal direction. Currently must be done 100% manually in Blender or with external addons. |
| C-05 | **Armor slot split point validation** | **HIGH** | `split_character` splits by vertex groups but does not validate that split points create clean seam lines (no visible gaps at neck/wrist/ankle boundaries). No overlap geometry generation for hiding seams during animation. AAA games use "seam-hiding" overlap rings. |
| C-06 | **Skin weight preparation topology** | **MEDIUM** | `auto_weight` + `fix_weights` exist and handle weight painting, but there is no pre-rigging topology check that verifies edge flow follows joint deformation directions (elbows need horizontal edge loops, knees need them, etc.). `mesh analyze` does not distinguish deformation-critical zones. |
| C-07 | **Character LOD-aware retopo** | **MEDIUM** | `retopo` uses Quadriflow globally. No character-aware mode that preserves face detail while aggressively reducing body/feet poly count. AAA characters need non-uniform LOD -- face stays high-poly even at LOD2. |

### Summary
**Current coverage**: ~40%. AI generation + retopo + rig templates + modular splitting gives a workflow but lacks face topology, hair, and scale validation.

---

## 2. WEAPON MODELING

### What We Have
- `asset_pipeline generate_weapon`: Procedural bmesh generation for 7 weapon types (sword, axe, mace, staff, bow, dagger, shield)
- Each weapon has: grip_point empty, trail_attach_top empty, trail_attach_bottom empty, collision mesh (convex hull)
- Sword: tapered blade + cross-guard + hilt + pommel
- Axe: handle cylinder + wedge head
- Mace: handle + UV-sphere head
- Staff: tapered cylinder + ornamental orb
- Bow: curved arc + string
- Dagger: short wide blade + guard + hilt
- Shield: kite shape + center boss

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| W-01 | **Missing weapon types: hammer, spear, crossbow, flail, halberd, greataxe, greatsword, wand, tome, scythe** | **CRITICAL** | Only 7 of 17+ dark fantasy weapon types exist. `VALID_WEAPON_TYPES` is hardcoded to `{sword, axe, mace, staff, bow, dagger, shield}`. A dark fantasy RPG needs at minimum hammers, spears, and crossbows. Greatsword vs. sword distinction matters for two-handed vs. one-handed combat. |
| W-02 | **Engraving/rune surface detail** | **HIGH** | No tool generates etched patterns, rune channels, or engraving geometry on weapon surfaces. Dark fantasy weapons need visible magical markings. This would be boolean cuts or displacement mapped surface detail. `blender_mesh boolean` exists but there is no rune pattern generator to feed it. |
| W-03 | **Gem socket placement** | **HIGH** | No tool creates gem indentations on weapon surfaces. An action RPG with equipment upgrading needs gem sockets -- an indentation mesh + a gem mesh that fits inside. Related to equipment upgrade system. |
| W-04 | **Sheathe/scabbard generation** | **MEDIUM** | No scabbard generator. When weapons are holstered on the character, they need a matching scabbard mesh. This is a separate mesh that matches the blade profile with a slight offset. |
| W-05 | **Weapon component separation** | **HIGH** | Weapons are generated as single meshes. AAA games need separate submeshes for pommel/guard/grip/blade so materials can be applied independently and components can be swapped (e.g., upgrade the blade but keep the hilt). The bmesh generators create monolithic geometry. |
| W-06 | **Weapon variant system** | **HIGH** | No parameter for quality tiers (common/rare/epic/legendary). Same sword generator makes one shape. Needs: variant geometry (simple guard vs. ornate guard), material tier presets, and increasing detail levels per rarity. |
| W-07 | **Two-handed vs. one-handed grip** | **MEDIUM** | `_compute_grip_point` returns a single grip point. Two-handed weapons (greatswords, staves, halberds) need two grip empties. |

### Summary
**Current coverage**: ~45%. Good foundation with 7 types + empties + collision, but missing weapon diversity, component separation, and dark fantasy detail (runes, gems).

---

## 3. FURNITURE/PROP MODELING

### What We Have
- `blender_worldbuilding generate_interior`: 16 room types (tavern, throne_room, dungeon_cell, bedroom, kitchen, library, armory, chapel, blacksmith, guard_barracks, treasury, war_room, alchemy_lab, torture_chamber, crypt, dining_hall)
- Each room type has furniture lists with type/placement/scale
- Furniture items are created as **scaled cubes** (bmesh `create_cube` with scale applied)
- `blender_environment scatter_props`: Context-aware prop placement near buildings with PROP_AFFINITY table
- `blender_environment create_breakable`: Intact + damaged variant pairs
- `blender_environment add_storytelling_props`: Narrative clutter (corpses, notes, tracks)

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| P-01 | **Furniture is placeholder cubes, not actual meshes** | **CRITICAL** | `handle_generate_interior` creates scaled cubes for every furniture item. A "table" is a cube scaled to 1.2x1.2x0.75. A "throne" is a cube scaled to 1.5x1.2x2.0. These are layout placeholders, not game-ready geometry. There are zero actual furniture mesh generators (table with legs, chair with back, bed with frame, etc.). |
| P-02 | **No parametric prop generators** | **CRITICAL** | No procedural generators for common props: candelabras, goblets, books, scrolls, potions, skulls, barrels (with staves), crates (with planks), chests (with hinged lid), torches, lanterns, keys, coins, food items, mugs, plates. The scatter engine references these types but the actual geometry is missing. |
| P-03 | **Material variant system for props** | **HIGH** | No system for generating material variants (oak table, stone table, iron table). The `_ROOM_CONFIGS` define furniture type and scale but not material. All furniture gets default material or none. |
| P-04 | **Wear/damage state variants for props** | **HIGH** | `create_breakable` generates intact + damaged variants for crates/barrels/pots only. No general-purpose damage state system that applies to all props (pristine -> worn -> damaged -> destroyed). No crack generation, no edge chipping. |
| P-05 | **Interactive prop states (open/closed/activated)** | **HIGH** | No tool generates state variants for interactive objects: chests (closed/open/looted), doors (closed/open/broken), levers (up/down), drawbridges (raised/lowered). These need separate meshes + pivot points + animation blend shapes. |
| P-06 | **Decorative set dressing props** | **MEDIUM** | No generators for ambiance props: cobwebs, dust particles, scattered papers, ink stains, wax drips, candle holders with melted wax, hanging chains, rope coils, fishing nets, animal pelts, mounted antler trophies. The storytelling prop system places narrative items but not general ambiance detail. |

### Summary
**Current coverage**: ~20%. Room layouts and placement logic exist but produce placeholder cubes. Zero actual prop mesh generation.

---

## 4. TERRAIN MODELING

### What We Have
- `blender_environment generate_terrain`: 6+ terrain presets (mountains, hills, plains, canyon, volcanic, coastal), configurable resolution up to 1024, noise-based heightmap
- `blender_environment paint_terrain`: Slope/altitude biome material assignment
- `blender_environment carve_river`: A*-path river channel carving
- `blender_environment generate_road`: Waypoint-based road with grading
- `blender_environment create_water`: Water plane with shoreline
- `blender_environment export_heightmap`: 16-bit RAW for Unity
- Erosion: hydraulic + thermal erosion algorithms
- Biome rules: altitude/slope-based vegetation assignment

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| T-01 | **Multi-biome terrain transitions** | **HIGH** | `paint_terrain` assigns materials per-face based on altitude/slope rules, but the transitions are hard boundaries. No blending, no splatmap-style weight painting, no gradual forest-to-swamp-to-mountain transitions. Unity side uses splatmap layers but Blender side produces sharp biome cuts. |
| T-02 | **Cliff face generation** | **CRITICAL** | Terrain is a heightmap grid -- it cannot represent vertical or overhanging cliff faces. Heightmaps are inherently 2.5D (one height per XY position). Dark fantasy needs dramatic cliff walls, overhangs, cave mouths. This requires separate mesh objects placed at terrain edges, not just heightmap manipulation. |
| T-03 | **Cave entrance geometry** | **CRITICAL** | No tool generates cave entrance meshes that transition seamlessly from terrain surface into underground spaces. The `generate_cave` tool creates standalone cave layouts but there is no terrain-to-cave transition piece. |
| T-04 | **Waterfall geometry** | **HIGH** | `create_water` makes flat water planes. No stepped cascade mesh, no waterfall mesh (thin curved surface from cliff to pool), no splash zone geometry. |
| T-05 | **Bridge generation (terrain-aware)** | **HIGH** | `_building_grammar.py` has `generate_bridge_spec` that creates a standalone stone bridge with arches, piers, and railings. However, it is NOT exposed as a blender_worldbuilding action -- it is an internal function only. And even if exposed, it is not terrain-aware (does not snap to terrain surface at endpoints). Also missing: rope bridges, drawbridges, natural log bridges. |
| T-06 | **Terrain detail meshes** | **MEDIUM** | No embedded terrain detail (rocks poking through ground, exposed roots, mushroom clusters). `scatter_vegetation` places instances ON terrain but does not modify terrain geometry to integrate them (no rock partially embedded in ground). |
| T-07 | **Terrain chunking for streaming** | **MEDIUM** | No tool to split large terrain into streamable chunks for Unity. Single monolithic terrain mesh. Unity terrain can be configured with sectors, but Blender exports one mesh. |

### Summary
**Current coverage**: ~55%. Solid heightmap terrain + erosion + rivers + roads + water. Major gaps in vertical geometry (cliffs, caves, overhangs) and terrain transitions.

---

## 5. CITY/SETTLEMENT MODELING

### What We Have
- `blender_worldbuilding generate_town`: Voronoi-based town layout with districts, roads, building plots, landmarks
- `blender_worldbuilding generate_building`: Grammar-based buildings in 5 styles (medieval, gothic, rustic, fortress, organic)
- `blender_worldbuilding generate_location`: Composed location with terrain + buildings + paths + POIs
- `blender_worldbuilding generate_world_graph`: MST-connected location network with 30-second walking rule
- Road cells as flat quads, building plots as marker boxes

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| S-01 | **Street/alley/plaza geometry** | **HIGH** | `generate_town` produces road CELLS (grid squares marked as road). No actual street geometry -- no curbs, no drainage channels, no cobblestone patterns, no stepped plazas, no narrow alleys with overhead arches. Roads are flat 2D tiles. |
| S-02 | **Market stall/shop front generation** | **HIGH** | No market or shop-front generator. A town needs stalls with canopies, display counters, signage, hanging goods. The building grammar produces full buildings but not the specialized half-open shop fronts common in fantasy markets. |
| S-03 | **Town wall/gate/defense system** | **HIGH** | `generate_castle` has curtain walls + gatehouse. But a TOWN wall is different -- it surrounds an irregular settlement boundary, has multiple gates at road entrances, and guard towers at intervals. No tool wraps a wall around a generated town layout. |
| S-04 | **Fountain/statue/monument generation** | **MEDIUM** | `generate_town` places "landmarks" but as marker columns (boxes). No actual fountain mesh (basin + water + figure), no statue generator, no monument/obelisk. |
| S-05 | **Signage/banner/flag placement** | **MEDIUM** | Interior room configs include "banner" items, but no sign generation (text on hanging boards), no flag physics mesh, no guild/faction heraldry. |
| S-06 | **Sewer/underground passage generation** | **HIGH** | Zero support. Dark fantasy cities need underground levels -- sewer tunnels, smuggler passages, undead catacombs beneath the town. No tool generates underground networks that connect to surface buildings. |
| S-07 | **Port/dock generation** | **MEDIUM** | No waterfront infrastructure: docks, piers, warehouses, cranes, ships at berth. If the game has coastal settlements, this is a significant content gap. |

### Summary
**Current coverage**: ~35%. Town layout + buildings + world graph exist but produce abstract geometry. Missing all urban detail: streets, markets, walls, underground.

---

## 6. DUNGEON MODELING

### What We Have
- `blender_worldbuilding generate_dungeon`: BSP room partitioning with corridors, doors, spawn/loot points
- `blender_worldbuilding generate_cave`: Cellular automata cave system
- `blender_worldbuilding generate_multi_floor_dungeon`: Vertical stacking with stair/ladder/pit connections
- `blender_worldbuilding generate_boss_arena`: Arena with cover objects, hazard zones, fog gate, phase triggers
- `blender_worldbuilding generate_easter_egg`: Secret rooms, hidden paths, lore items
- Room types: generic, spawn, boss, treasure, entrance, exit
- Geometry: floor quads + wall columns per grid cell

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| D-01 | **Trap geometry generation** | **CRITICAL** | Zero trap support. A dungeon crawler needs: spike pit meshes (retracted/extended states), swinging blade pendulums, dart wall launchers, crushing ceiling plates, floor tile triggers, arrow slit mechanisms. None of these exist. Only BSP rooms with flat floors. |
| D-02 | **Puzzle room layouts** | **HIGH** | No puzzle room generator. Needs: pressure plate arrays (grid of activatable tiles), rotating pillar puzzles, lock-and-key geometry (locked door + key pedestal), beam-reflection puzzle surfaces, movable block geometry. |
| D-03 | **Boss arena detail enhancement** | **HIGH** | `generate_boss_arena` produces basic arena shape with cover boxes and hazard zone markers, but missing: pillar cover with destructible sections, elevated platforms for phase transitions, environmental hazard meshes (lava pools, poison vents, electrified floors), breakable arena walls for surprise reveals. |
| D-04 | **Transition corridor variety** | **MEDIUM** | All corridors are uniform-width grid cells. No variation: no narrow squeeze passages, no grand hallways with columns, no collapsed rubble partial-blockages, no slope ramps, no underwater passages. |
| D-05 | **Treasure room designs** | **HIGH** | Room type "treasure" exists but gets the same flat floor + walls as every other room. No elevated platform for treasure display, no trapped chest geometry, no vault door, no guarded alcove design. |
| D-06 | **Prison cell detail** | **MEDIUM** | "dungeon_cell" room config has cot + chains + bucket as placeholder cubes. No barred door geometry, no wall-mounted shackle geometry, no torture devices (beyond the torture_chamber room type which also uses cubes). Dark fantasy needs atmospheric prison areas. |
| D-07 | **Dungeon dressing/atmosphere** | **HIGH** | No dungeon-specific detail: crumbling wall sections, moss/water drip stains, cobweb meshes, rubble piles, scattered bones, bloodstains, wall sconces, drainage grates. The room geometry is completely bare boxes. |

### Summary
**Current coverage**: ~35%. BSP layout + multi-floor + boss arena + caves gives good structural variety, but rooms are empty boxes with no gameplay-specific geometry (traps, puzzles, treasure, atmosphere).

---

## 7. CASTLE/FORTRESS MODELING

### What We Have
- `blender_worldbuilding generate_castle`: Curtain walls + corner towers + keep (3-floor fortress building) + gatehouse with opening
- `generate_fortress_spec`: Larger fortress variant with outer walls, 4 corner towers, central keep, courtyard marker, gatehouse
- `generate_tower_spec`: Standalone cylindrical tower with battlements, arrow slits, spiral stair placeholder, floor slabs
- Tower battlements: merlon ring at top
- Castle gatehouse: Box with opening (portcullis placeholder)

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| F-01 | **Portcullis mechanism mesh** | **HIGH** | Gatehouse has an "opening" but no actual portcullis geometry (iron grid that slides vertically). No winch mechanism, no gate tracks. The opening is just a hole in the wall. |
| F-02 | **Proper battlement geometry** | **HIGH** | Battlements are square boxes placed in a ring. Real crenellations need: merlons (raised) + crenels (gaps) alternating pattern along wall tops, plus machicolations (overhanging gallery with floor holes) on fortress style. The current boxes float at tower tops without connecting to the wall geometry. |
| F-03 | **Tower type variants** | **MEDIUM** | Only one tower template (cylindrical with battlements). Need: square watchtower, siege tower (mobile), bell tower (with belfry opening), wizard tower (with observatory dome), ruined tower (partially collapsed). |
| F-04 | **Courtyard detail** | **HIGH** | Courtyard is a flat box marker (0.05 height). No well, no training dummy geometry, no stable, no garden beds, no smith area. A castle courtyard is the player's hub and needs actual detail. |
| F-05 | **Throne room / great hall** | **MEDIUM** | `generate_interior` has a throne_room config with placeholder cubes. No actual throne mesh, no raised dais geometry, no column arcade, no tapestry hanging points. The throne_room is just a room layout. |
| F-06 | **Underground/crypt connection** | **HIGH** | No tool connects castle to underground dungeon/crypt. A dark fantasy castle needs a descent path from keep to underground levels. `generate_multi_floor_dungeon` creates vertical connections but cannot connect to castle geometry above. |
| F-07 | **Curtain wall walkway** | **MEDIUM** | Curtain walls are solid boxes. No walkway on top (wall-walk) with proper floor and parapet. Players/NPCs need to patrol the wall tops. |

### Summary
**Current coverage**: ~40%. Castle structure (walls, towers, keep, gatehouse) is present but all components are geometric primitives without game-functional detail.

---

## 8. ENVIRONMENTAL DETAIL

### What We Have
- `blender_environment scatter_vegetation`: Poisson disk + biome rules, 4 types (tree=cone, bush=icosphere, grass=plane, rock=cube), collection instances for performance
- `blender_environment scatter_props`: Context-aware placement near buildings using PROP_AFFINITY table
- `blender_environment create_breakable`: Intact/damaged pairs (crate, barrel, pot, bench, cart)
- `blender_environment add_storytelling_props`: Narrative environmental clutter
- `blender_texture generate_wear`: Curvature-based wear map
- `blender_texture delight`: Remove baked-in lighting
- `concept_art silhouette_test`: Shape readability at distances

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| E-01 | **Vegetation templates are primitives** | **CRITICAL** | "tree" is a cone, "bush" is an icosphere, "grass" is a flat plane, "rock" is a cube. These are placeholders, not game-ready vegetation. Need: tree generators with trunk + branch structure (L-system or space colonization), bush meshes with leaf card clusters, grass billboard strips, and actual rock meshes with irregular surface. |
| E-02 | **Rock/boulder formation generator** | **HIGH** | No rock mesh generator. `scatter_vegetation` places "rock" as cubes. Need: parametric rock generator with erosion detail, crystal formation generator, cliff face rock panels, boulder clusters with moss coverage. |
| E-03 | **Foliage generation** | **HIGH** | No foliage mesh tools: ivy growth on walls (following surface), hanging moss strands, fern fronds, dead leaf litter, mushroom clusters, thorny vine meshes. Dark fantasy needs dense, oppressive vegetation. |
| E-04 | **Ruin/decay overlay** | **HIGH** | `generate_ruins` applies damage by removing operations and adding debris boxes. No actual decay mesh effects: crack patterns on walls, crumbling edges (geometry noise on mesh edges), moss growth patches (displacement), root intrusion (roots breaking through stone). |
| E-05 | **Weather-affected variants** | **MEDIUM** | No snow-covered, rain-wet, or sun-bleached mesh variants. This is mostly a material/shader concern on the Unity side, but Blender needs to generate snow accumulation geometry (snow caps on roofs, icicles on eaves) and material presets. |
| E-06 | **Atmospheric props** | **MEDIUM** | No particle-emitting prop meshes: brazier with fire point, torch sconce with flame position, chimney with smoke emission point. These need empties at emission positions for Unity particle systems. The interior configs include "brazier" but as a cube without emission point empties. |
| E-07 | **Tree variety for biomes** | **HIGH** | One tree template (cone) for all biomes. Dark fantasy forest needs: dead twisted trees, massive ancient trees, fungal trees, willow-like drooping trees, petrified trees. Each biome should have distinct tree silhouettes. |

### Summary
**Current coverage**: ~25%. Scatter engine and placement logic are solid but all scattered objects are geometric primitives. The placement is AAA-grade; the meshes are prototype-grade.

---

## 9. QUALITY & BEAUTY CHECKS

### What We Have
- `blender_mesh analyze`: A-F topology grading (ngons, non-manifold, poles, loose geometry)
- `blender_mesh game_check`: Poly budget, UV check, material check, transform check, naming check, scale check
- `concept_art silhouette_test`: Shape readability at game distances via fal.ai
- `blender_texture validate`: Texture dimension, format, channel validation
- `blender_texture validate_palette`: Dark fantasy palette rule checking
- `blender_texture delight`: Remove baked-in lighting from albedo
- `blender_rig validate`: A-F rig grading (unweighted verts, symmetry, bone rolls)
- `FURNITURE_SCALE_REFERENCE`: Real-world scale validation for furniture dimensions

### Gaps

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| Q-01 | **Silhouette distinctness between assets** | **HIGH** | `silhouette_test` checks ONE asset's readability. No tool compares silhouettes of multiple assets to ensure they are distinguishable (e.g., "can the player tell a mace from a hammer at 20m?"). An AAA game needs silhouette uniqueness across the entire asset library. |
| Q-02 | **Visual complexity/noise analysis** | **MEDIUM** | No tool measures visual complexity balance. Too simple = boring; too noisy = visual clutter. Need: contrast ratio analysis, detail frequency measurement, "visual rest" zone detection. |
| Q-03 | **Scale consistency validation across scene** | **HIGH** | `game_check` validates individual object scale. No scene-wide check that compares object scales to each other (is this door the right size relative to the character? Is this sword proportional to the hand bone?). FURNITURE_SCALE_REFERENCE validates individual dimensions but not relationships. |
| Q-04 | **Art style consistency checker** | **HIGH** | `validate_palette` checks color rules. No geometry-level style check: does this asset match the dark fantasy aesthetic in terms of edge sharpness, surface detail density, proportion language? AI-generated assets from Tripo3D may have inconsistent style. |
| Q-05 | **Detail density gradient validation** | **MEDIUM** | No check that assets follow the AAA principle of more detail at eye-level/interaction distance, less at extremes (floor, high ceiling). Character faces should have more detail than boots. Currently all topology grading is uniform. |
| Q-06 | **Cross-asset polycount budgeting** | **HIGH** | `game_check` validates per-object poly budgets. No scene-level budget tracker that sums all visible objects and validates against frame budget. A room with 50 props each under budget can still be over scene budget. |
| Q-07 | **UV density consistency across asset set** | **MEDIUM** | `uv equalize` normalizes texel density within one object. No cross-object texel density validation to ensure the sword has similar pixel density to the shield. |

### Summary
**Current coverage**: ~50%. Strong per-asset validation exists. Missing cross-asset comparisons, scene-level budgets, and style consistency checks.

---

## CROSS-CUTTING GAPS

These gaps span multiple categories and represent systemic issues.

| # | Gap | Severity | Details |
|---|-----|----------|---------|
| X-01 | **Procedural mesh generation library** | **CRITICAL** | The toolkit can PLACE objects (scatter, interior layout, dungeon BSP) but almost never CREATES actual mesh geometry for them. Furniture = cubes, trees = cones, rocks = cubes, bushes = icospheres. The only real mesh generators are weapons (7 types) and buildings (box/cylinder primitives). Need a procedural mesh library for: tables, chairs, barrels, chests, trees, rocks, fences, walls, arches, columns, stairs. |
| X-02 | **Mesh decoration/detail system** | **HIGH** | No general-purpose system for adding surface detail to meshes: edge bevels for catch lights, panel lines/inset detail, rivets/bolts placement, surface pattern stamps. Dark fantasy metal needs rivets; stone needs chisel marks; wood needs grain direction. |
| X-03 | **Modular connection validation** | **HIGH** | `generate_modular_kit` creates pieces with connection_points as custom properties, but no tool validates that pieces actually snap together correctly, that seams are hidden, or that there are no T-junction artifacts. |
| X-04 | **Asset pipeline: AI-to-game quality bridge** | **HIGH** | The Tripo3D -> cleanup -> retopo -> UV -> PBR pipeline exists, but AI-generated meshes have random topology that retopo cannot always fix to game-quality. No intermediate step for: marking sharp edges, defining UV seam hints, identifying and fixing degenerate geometry, or applying style-corrective sculpting. |
| X-05 | **Mesh boolean cleanup** | **MEDIUM** | `blender_mesh boolean` exists but boolean operations often produce dirty geometry (non-manifold edges, degenerate faces). No automatic post-boolean cleanup step. |

---

## PRIORITY MATRIX

### Tier 1: Production Blockers (CRITICAL)
1. **P-01/P-02**: Furniture/prop is all cubes -- no actual mesh generation
2. **E-01**: Vegetation templates are primitives (cone/cube/sphere)
3. **C-04**: Hair card mesh generation (zero support)
4. **X-01**: No procedural mesh generation library (systemic)
5. **T-02**: Cliff face generation (heightmap limitation)
6. **T-03**: Cave entrance geometry (terrain-to-cave transition)
7. **D-01**: Trap geometry (zero dungeon gameplay support)
8. **W-01**: Missing weapon types (only 7 of 17+)

### Tier 2: Quality Reducers (HIGH, blocking AAA)
9. **C-02**: Face topology checker
10. **W-02/W-03**: Weapon detail (runes, gem sockets)
11. **W-05/W-06**: Weapon components and variants
12. **P-04/P-05**: Prop damage states and interactive states
13. **S-01/S-06**: Street geometry and underground passages
14. **D-02/D-03/D-05/D-07**: Dungeon detail (puzzles, boss arena, treasure, dressing)
15. **F-01/F-02/F-04**: Castle detail (portcullis, battlements, courtyard)
16. **E-02/E-03/E-07**: Rock/foliage/tree mesh generation
17. **Q-01/Q-03/Q-04/Q-06**: Cross-asset quality validation
18. **X-02/X-04**: Mesh decoration and AI quality bridge

### Tier 3: Polish (MEDIUM)
19. C-06, C-07: Weight prep topology, character-aware LOD
20. W-04, W-07: Scabbards, two-handed grips
21. P-03, P-06: Material variants, decorative props
22. T-06, T-07: Terrain detail meshes, chunking
23. S-04, S-05, S-07: Fountains, signs, ports
24. D-04, D-06: Corridor variety, prison detail
25. F-03, F-05, F-07: Tower variants, throne room, wall walkways
26. E-05, E-06: Weather variants, atmospheric props
27. Q-02, Q-05, Q-07: Visual complexity, detail gradient, UV density

---

## RECOMMENDED IMPLEMENTATION ORDER

### Phase A: Procedural Mesh Foundation (Unblocks everything)
Build a procedural mesh generation library that the entire toolkit can use:
- Parametric primitives: arch, column, stairs, fence, wall segment
- Furniture generators: table, chair, barrel, chest, crate, shelf, bed
- Natural form generators: rock, tree trunk/branches, bush, crystal
- Decoration patterns: rivets, panel lines, beveled edges

### Phase B: Dark Fantasy Essential Detail
- Weapon type expansion (hammer, spear, crossbow, greatsword, halberd, flail, wand, scythe)
- Weapon component separation + variant tiers
- Trap geometry library (spike pit, pendulum blade, dart wall, crusher, floor trigger)
- Cliff/overhang mesh generation (break heightmap limitation)
- Cave entrance transition pieces

### Phase C: World Quality
- Prop damage/interaction states
- Street/alley/plaza geometry
- Castle interior detail (portcullis, courtyard, battlement walkways)
- Dungeon dressing (wall decay, rubble, atmosphere)
- Underground passage system

### Phase D: Character & Validation
- Hair card generation pipeline
- Face topology validation
- Cross-asset quality checks (silhouette, scale, style, budget)
- Character proportion system with archetype enforcement

---

## TOTAL GAP COUNT

| Category | Gaps Found | Critical | High | Medium |
|----------|-----------|----------|------|--------|
| Character | 7 | 2 | 3 | 2 |
| Weapons | 7 | 1 | 4 | 2 |
| Furniture/Props | 6 | 2 | 3 | 1 |
| Terrain | 7 | 2 | 2 | 3 |
| City/Settlement | 7 | 0 | 4 | 3 |
| Dungeons | 7 | 1 | 4 | 2 |
| Castle/Fortress | 7 | 0 | 4 | 3 |
| Environmental Detail | 7 | 1 | 4 | 2 |
| Quality Checks | 7 | 0 | 4 | 3 |
| Cross-Cutting | 5 | 1 | 3 | 1 |
| **TOTAL** | **67** | **10** | **35** | **22** |

The toolkit has strong architecture and placement logic but its 3D mesh generation capability sits at approximately **35-40% of what an AAA dark fantasy action RPG requires**. The single biggest systemic issue is that placement systems output cubes/cones instead of actual game-ready meshes.
