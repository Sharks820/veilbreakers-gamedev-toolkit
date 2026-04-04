# V9.0 MASTER FINDINGS & IMPLEMENTATION SHEET

**Created:** 2026-04-04
**Source:** 53+ agent audits across 10 fleets, visual verification, codebase analysis
**Purpose:** Single source of truth for ALL gaps, bugs, errors, quality issues, and implementation requirements

---

## TABLE OF CONTENTS

1. [Pipeline Architecture Findings](#1-pipeline-architecture)
2. [Codebase-Wide Systemic Bugs (147 instances)](#2-codebase-wide-bugs)
3. [Terrain System Findings](#3-terrain)
4. [Water System Findings](#4-water)
5. [Vegetation System Findings](#5-vegetation)
6. [Castle/Settlement Findings](#6-castle-settlement)
7. [Weapon Generator Findings](#7-weapons)
8. [Creature Generator Findings](#8-creatures)
9. [Riggable Prop Findings](#9-riggable-props)
10. [Material/Texture Findings](#10-materials)
11. [Export Pipeline Findings](#11-export)
12. [Audio System Findings](#12-audio)
13. [Blender Tool/Camera Findings](#13-tools)
14. [Research Library Index](#14-research)
15. [Implementation Priority Order](#15-priority)

---

## 1. PIPELINE ARCHITECTURE

### 1.1 Entry Points (7 found, 1 canonical)
- `compose_map` in blender_server.py — THE canonical path (10 steps)
- `generate_map_package` — export/packaging (post-compose_map)
- `full_pipeline` — single asset processing
- `generate_and_process` — Tripo → asset pipeline
- `handle_generate_multi_biome_world` — terrain + biomes only (INCOMPLETE)
- `handle_compose_world_map` — roads + POIs only (INCOMPLETE)
- `handle_generate_location` — individual locations (sub-component)

**RULE:** All future work goes through compose_map. No new orchestration paths.

### 1.2 Pipeline Dispatch Bugs (3 CRITICAL)
| Bug | Location | Impact |
|-----|----------|--------|
| `asset_pipeline` COMMAND_HANDLERS only handles `generate_lods` — 25 other actions fail if dispatched through handler | `__init__.py:1461-1465` | Checkpoint resume can fail |
| `_LOC_HANDLERS["settlement"]` → `world_generate_town` instead of `world_generate_settlement` | `blender_server.py:2924` | Full settlement system bypassed |
| Same handler called from multiple MCP tools with different parameter shapes | Multiple locations | Silent failures from param mismatch |

### 1.3 Smart Planner Orphaned
- `compose_world_map()` in `map_composer.py` has superior biome-aware, slope-respecting, MST-road-generating placement logic
- `compose_map` in `blender_server.py` IGNORES it entirely — uses simple ring-based anchoring
- **FIX:** Wire `compose_world_map` output into compose_map Step 5

### 1.4 Canonical Pipeline (21 steps)
```
Steps 1-15:  Generation (clear → terrain → features → water → materials → roads → settlements → buildings → interiors → vegetation → props → lighting → atmosphere → corruption → export)
Steps 16-21: Export (collection organize → quality validation → LOD generation → texture bake → export meshes FBX → export terrain data)
```

### 1.5 Wiring Status Summary
| System | Code Exists | Wired into Pipeline | Fix Type |
|--------|------------|-------------------|----------|
| Hydraulic/thermal erosion | Yes | Yes (Step 2) | Already wired |
| 14 biome material palettes | Yes | Yes (Step 6) | Already wired |
| HeightBlend node group | Yes | DEAD CODE | Wire into biome material |
| L-system trees (4 species) | Yes | NOT USED (cubes placed instead) | Fix vegetation handler |
| 15+ vegetation generators | Yes | NOT USED | Fix VEGETATION_GENERATOR_MAP usage |
| Settlement generator (15 types) | Yes | Partially | Route all locations through it |
| Modular building kit (260 pieces) | Yes | NEVER CALLED | Wire into building materialization |
| Interior binding (14 types) | Yes | NEVER CALLED | Wire into settlement gen |
| 10 terrain features | Yes | 7 are DEAD CODE | Register + wire |
| MST road network | Yes | NOT USED (simple paths used) | Replace road gen |
| Coastline generator | Yes | NEVER CALLED | Wire into Step 4 |
| Light integration LIGHT_PROP_MAP | Yes | BYPASSED | Wire into Step 12 |
| Prop density/quality | Yes | NEVER CALLED | Wire into Step 11 |
| Atmospheric volumes | Yes | NEVER CALLED | Wire into Step 13 |
| Veil corruption | Partial | NOT IMPLEMENTED | Build new |

---

## 2. CODEBASE-WIDE SYSTEMIC BUGS (147+ instances)

### Pattern 1: Z=0 Hardcoding (42 instances, CRITICAL)
Objects placed at Z=0 instead of using `_sample_scene_height()` which EXISTS but isn't called.

**Files affected:**
- `worldbuilding_layout.py`: lines 67, 73, 79, 86, 125, 132, 154, 164, 174, 492, 515, 674, 677, 680, 688, 691, 701, 704
- `worldbuilding.py`: lines 3366, 3380, 6000, 6188, 6214, 6229, 6273, 6373, 7052, 7416, 7645
- `coastline.py`: lines 268, 277, 286, 335, 351, 367
- `terrain_features.py`: lines 705, 729
- `environment_scatter.py`: lines 156, 203, 289, 412
- `vegetation_scatter.py`: lines 98, 156
- `rock_scatter.py`: line 67
- `mesh.py`: line 487
- `water.py`: line 234

**FIX:** Replace all with `z = _sample_scene_height(x, y, terrain_name)`

### Pattern 2: Linear Interpolation → Smootherstep (35 instances, HIGH)
**Files affected:**
- `animation_gaits.py`: lines 1375, 1522, 1524, 1661, 1663
- `animation_combat.py`: lines 563, 576, 651, 652
- `animation_monster.py`: lines 89, 91, 208, 216
- `animation_environment.py`: lines 143, 163, 186, 208, 229, 410, 437
- `animation_locomotion.py`: lines 292, 297, 311, 316, 342, 371, 541, 542

**FIX:** Replace `(1 - t)` patterns with `smootherstep(t)` = `t * t * (3 - 2 * t)`

### Pattern 3: Hard Material Thresholds (9 instances, MEDIUM)
**Files affected:**
- `coastline.py`: lines 413, 415, 418, 422
- `terrain_features.py`: lines 977, 980, 1207
- `mesh.py`: line 612
- `environment.py`: line 145

**FIX:** Replace discrete `mat_idx` assignments with smoothstep gradient blending

### Pattern 4: Missing Water Exclusion (5 files, HIGH)
**Files missing water level checks:**
- `environment_scatter.py` — no `if z < water_level` guard
- `vegetation_scatter.py` — no water check
- `rock_scatter.py` — no water check
- `worldbuilding_layout.py` — no water boundary verification
- `terrain_features.py` — weak/incomplete water handling

### Pattern 5: Deprecated Blender API (6 instances, HIGH)
- `terrain_materials.py:1560-1563` — `group.inputs.new()` removed in Blender 4.0+
- `terrain_materials.py:1578` — `group.outputs.new()` removed in Blender 4.0+
- `geometry_nodes.py:156` — `ShaderNodeTexMusgrave` merged into Noise in Blender 4.1

**FIX:** `group.inputs.new()` → `group.interface.new_socket()`, Musgrave → Noise Texture

### Pattern 6: Missing Seed Parameters (50+ instances, MEDIUM)
**Files with unseeded randomization:**
- `coastline.py` — Random without seed
- `terrain_features.py` — inconsistent seed control
- `environment_scatter.py` — missing seed parameter
- `vegetation_scatter.py` — missing seed parameter
- `rock_scatter.py` — missing seed parameter

### Pattern 7: Y-Axis Used for Vertical Instead of Z (CRITICAL)
- `terrain_features.py` cliff outcrop — layers stack along Y instead of Z
- Blender is Z-up, Unity is Y-up — conversion at EXPORT time only
- Need full grep for vertical stacking patterns using Y where Z should be

### Pattern 8: Vegetation Scatter Creates Placeholder Cubes
- `vegetation_system.py:762-766` — `bmesh.ops.create_cube(instance_bm, size=0.5)` creates cubes
- Comment says "real meshes come from procedural generators" but they never do
- `VEGETATION_GENERATOR_MAP` in `_mesh_bridge.py` has 15+ real mesh generators that are NEVER CALLED
- `environment_scatter.py` has `handle_scatter_vegetation()` that WOULD use the generators but isn't called by compose_map

---

## 3. TERRAIN SYSTEM

### 3.1 Current State (Hearthvale Scene Audit)
- **Terrain mesh**: 16,384 verts (128x128), 200x200m, Z range 0-25m
- **Materials**: 4 slots ALL default grey (0.8, 0.8, 0.8) — names meaningless (snow/rock/dead_grass/mud all identical)
- **Vertex colors**: NONE — no splatmap blending
- **Erosion**: None visible — "low points" are just Z=0 hard floor, not gradual erosion
- **River banks**: 83.7° maximum slope — staircase of rectangular grid steps
- **Average bank slope**: 42.5° (should be 5-15° for natural banks)

### 3.2 Terrain Feature Generators — Quality Audit
| Generator | Quality | Key Gaps |
|-----------|---------|----------|
| `generate_canyon` | MEDIUM | Z=0 hardcoded, no scree at floor edges, linear wall taper |
| `generate_waterfall` | MEDIUM | Z=0, no foam, hard threshold wet zone at x=0.4 |
| `generate_cliff_face` | MEDIUM | Z=0, no scree at base, no undercut detail, discrete material bands |
| `generate_swamp_terrain` | MEDIUM | Z=0, double-squared falloff (hyper-steep islands) |
| `generate_natural_arch` | MEDIUM | Z=0, linear pillar taper, no scree at base |
| `generate_geyser` | BASIC | Z=0, minimal vent placement, no temperature gradient |
| `generate_sinkhole` | UNAUDITED | Not read due to file size constraints |
| `generate_floating_rocks` | UNAUDITED | Not read |
| `generate_ice_formation` | UNAUDITED | Not read |
| `generate_lava_flow` | UNAUDITED | Not read |

### 3.3 Terrain Quality Gaps
- **No micro-undulation** — ground is perfectly smooth between noise samples. AAA terrain has 5-15cm variation per meter
- **No terrain skirt geometry** — paper-thin heightmap edge visible from angles
- **No macro variation** — same texture pattern repeats visibly
- **No height-based blending** — linear alpha creates mushy transitions. Need displacement-based rock-through-grass
- **Missing scree/talus at EVERY cliff base** — geological realism demands it
- **All terrain features use linear interpolation** — need smootherstep everywhere
- **Heightmaps can't represent >70° cliffs** — need hybrid overlay mesh approach
- **No spline-terrain deformation** — terrain_advanced.py has splines, road_network.py has paths, NOT CONNECTED

### 3.4 Erosion Status
- `apply_hydraulic_erosion` — EXISTS, AAA quality, auto-scales to 150K+ droplets
- `apply_thermal_erosion` — EXISTS, AAA quality, vectorized numpy
- Both ARE wired into terrain generation (Step 2) — working correctly
- **Perlin noise fade curve IS correct** (proper smootherstep at `_terrain_noise.py:103`)

---

## 4. WATER SYSTEM

### 4.1 Current State
- **Water mesh**: 4 vertices — single flat quad spanning entire 200x200m terrain
- **Material**: bare Principled BSDF, dark navy (0.05, 0.15, 0.30), transmission 0.8 but alpha 1.0
- **Coverage**: floods EVERYTHING below Z=3 — dry land areas underwater
- **No separate water bodies** — no lakes, ponds, streams. One plane.
- **River banks**: 594 terrain edges cross water line with staircase profile

### 4.2 What Exists But Isn't Used
- `handle_create_water` in environment.py — creates spline-following water mesh with flow vertex colors (AAA quality)
- `handle_carve_river` — A* pathfinding river carving with smooth blending (AAA quality)
- Coastline feature specs (sea stacks, tide pools, outcrops) — METADATA ONLY, no mesh generators

### 4.3 Gaps
- No shaped river mesh following terrain contours
- No natural shoreline geometry
- No lake/pond generation
- No waterfall plunge pools
- No ford/shallow crossing points
- No wet rock material (referenced but never created)
- Wet rock PBR formulas documented (Lagarde) but not implemented

---

## 5. VEGETATION SYSTEM

### 5.1 Current State (Hearthvale Audit)
- **1,985 objects** using **6 mesh templates**
- **Trees**: 513 objects, 1 unique mesh (946 verts lollipop), ALL identical copies
- **Bushes**: 622 objects, 2 meshes
- **Grass**: 788 objects, 1 mesh (14 faces)
- **Rocks**: 62 objects, 2 meshes
- **30 trees growing IN water**
- **79 grass objects at Z=0** (never placed on terrain)
- **47 floating objects** (up to 6.75m above terrain)
- **47 buried objects** (up to 6.59m below terrain)
- **76 objects outside terrain bounds**
- **9 template objects visible at origin**
- **ZERO undergrowth variety** — no fallen logs, mushrooms, ferns, flowers, vines, moss

### 5.2 What EXISTS But Is Dead Code
- `VEGETATION_GENERATOR_MAP` in `_mesh_bridge.py` — 15+ entries:
  - `_lsystem_tree_generator` with oak/birch/twisted/dead types
  - `generate_shrub_mesh`, `generate_grass_clump_mesh`, `generate_mushroom_mesh`, `generate_rock_mesh`
- `handle_scatter_vegetation()` in environment_scatter.py — WOULD create real meshes
- `BIOME_VEGETATION_SETS` — 14 biomes with tree/ground_cover/rock rules per biome
- L-system tree generator — proper branching, bark, leaves, wind vertex colors

### 5.3 Vegetation Quality Issues (from code audit)
- L-system iteration cap uniform at 6 (dead trees should allow 7)
- VEGETATION_GENERATOR_MAP hardcodes iterations=4 (should be 5)
- No slope enforcement for forest placement (trees on 45° cliff faces)
- Building exclusion uses axis-aligned bounding boxes (curved buildings leak trees)
- All vegetation gets "bark" material fallback (leaves/grass need different materials)
- Branch mesh uses 6 ring segments (too low for closeup — need 8)
- Leaf card density hardcoded per leaf_type, ignores canopy_style
- No terrain-normal baking (grass on slopes doesn't tilt)
- Combat clearing radius hardcoded 15-40m regardless of encounter size

---

## 6. CASTLE/SETTLEMENT SYSTEM

### 6.1 Current State (Blender Visual Audit)
- **Castle split into 2 groups 85m apart** — keep at (-60, 60), ramparts at (0, 0)
- **40 of 44 objects have NO materials** — render as default grey
- **All 44 pieces below terrain** — 5-12m underground
- **Gate is 0.06m thick flat plane** — no archway, no opening
- **Ramparts are 1.43m tall** — waist height, not defensible walls
- **Keep base color (0.8, 0.8, 0.8)** — near-white, not weathered stone
- **Castle roughness textures ALL BLACK** (value 0.0 = perfect mirror)
- **No city infrastructure** — no streets, no market, no housing

### 6.2 Visual Verification Findings (Sword — representative of all generators)
- **Hilt disconnected from blade** — gap between guard and blade geometry
- **Blade and hilt oriented differently** — should extend as one piece
- **Pommel has ugly cylinder balls** — blocky, not properly meshed
- **Guard frame is blocky rectangles** — not rounded, not ornate
- **ZERO materials on ANY weapon** — all default white
- **Previous "AAA" code-based scoring was WRONG** — visual output is BASIC-DECENT at best

### 6.3 Architecture Quality Gaps (vs AAA standards)
- Castle walls must be 2-3m thick (ours: 1.5m, under-spec)
- Merlons follow one-third rule (ours: 0.6m wide / 0.8m tall, undersized)
- FromSoft uses 3-5 stone types per structure (ours: ONE "stone_fortified")
- Gatehouse needs arch geometry (ours: rectangular)
- Missing: portcullis mesh, arrow slits, hanging shop signs
- generate_castle_spec uses `type: "box"` for ALL geometry
- Castle BYPASSES settlement_generator entirely — uses boxes instead of modular kit

### 6.4 Settlement System (What Works)
- `settlement_generator.py` — FULLY WIRED, comprehensive
- 15 settlement types defined
- Interiors: multi-floor, 14 room types, furniture, lighting
- Roads: L-system organic, MST connectivity, curb geometry
- Props: narrative clusters, building-cluster associations
- Terrain foundations: heightmap-aware, terracing
- BUT: castle generation DOES NOT USE any of this

### 6.5 Modular Building Kit (260 pieces, NEVER USED)
- 52 core pieces x 5 styles (medieval, gothic, fortress, organic, ruined)
- Includes: wall_section, corner, archway, window, door, roof_section, turret_base, battlement
- Complete `generate_modular_piece()` dispatch function
- Complete `assemble_building()` for combining pieces
- **COMPLETELY UNWIRED from any generation pipeline**

---

## 7. WEAPON GENERATORS (Visual Verification)

### 7.1 Sword (VISUALLY VERIFIED)
- **Score**: BASIC-DECENT geometry, PLACEHOLDER materials
- **Verts/Tris**: 586 / 1108
- **Materials applied**: ZERO
- **Issues found visually**:
  - Hilt disconnected from blade (gap visible)
  - Blade and hilt oriented differently
  - Pommel is ugly cylinder balls, not properly meshed
  - Guard is blocky rectangular frame
  - All white/grey default material
  - No metal texture, no leather grip, no color differentiation
  - No dark fantasy character (no wear, scratches, patina)
- **vs Elden Ring**: NOT CLOSE

### 7.2-7.6 Axe, Mace, Bow, Shield, Staff
- **NOT YET VISUALLY VERIFIED** — need to generate and photograph each
- Previous code-based "AAA" scores are UNRELIABLE and must be reverified visually

---

## 8. CREATURE GENERATORS
- **NOT YET VISUALLY VERIFIED**
- Quadruped reported generating upside-down (animal on head, not feet)
- Previous code-based scores unreliable
- Known issue: wing topology may use N-gons in deformation zones
- Known issue: fantasy creature has hard transitions at body part junctions

---

## 9. RIGGABLE PROPS

### 9.1 Quality Status (Code Audit — needs visual reverification)
| Prop | Code Quality | Key Gap |
|------|-------------|---------|
| Door | Claimed AAA | Needs visual verification — hinge topology? |
| Chain | MEDIUM | 288 tris/link (should be 80), no catenary curve |
| Flag | MEDIUM | Insufficient vertex density for cloth sim |
| Chest | Claimed AAA | Visually verified: 102 verts, white, no materials |
| Drawbridge | Claimed AAA | Needs visual verification |
| Cage | MEDIUM | Bar topology too low density, door hinge issues |
| Chandelier | MEDIUM | Candle socket simplified, chain flat |
| Hanging Sign | MEDIUM | No carved lettering, basic hinge |
| Windmill | MEDIUM | Flat blade planes, simplified gear teeth |
| Rope Bridge | MEDIUM | Simplified rope cylinders, not braided |

### 9.2 Missing Generators
- Curtains, window shutters, window bars, rope (separate from chain), tapestries

### 9.3 Physics Pipeline Gaps
- No cloth material presets (heavy canvas vs silk vs tattered)
- No wind force auto-setup
- No cloth-to-bone bake pipeline (FBX can't export vertex animation)

---

## 10. MATERIAL/TEXTURE SYSTEM

### 10.1 What Works
- MATERIAL_LIBRARY: 52 named materials with full PBR parameters
- 6 procedural GENERATORS: stone, wood, metal, organic, terrain, fabric — all create full node graphs
- build_stone_material: Voronoi blocks, noise mortar, surface variation, roughness maps, 3-layer normals
- BIOME_PALETTES_V2: 14 biomes with 4 layers each (ground/slope/cliff/special)
- auto_assign_terrain_layers: RGBA vertex color splatmap computation
- handle_create_biome_terrain: fully wired biome material assignment

### 10.2 What's Broken
- HeightBlend node group: DEFINED but DEAD CODE (never called from anywhere)
- Deprecated API: `group.inputs.new()` at lines 1560-1563 (Blender 4.0+ crash)
- Castle roughness textures: ALL BLACK (value 0.0 = mirror) — source unknown
- Terrain materials in current scene: 4 identical default grey, none using procedural generators
- No height-based texture blending (rocks through grass)
- No macro variation layer (visible tiling)
- No curvature-driven wear
- No micro-detail normal maps
- No wet rock material (referenced but never created)

### 10.3 Texture Bake Pipeline
- Texture baking functions EXIST (diffuse, normal, AO, curvature, thickness)
- Channel packing EXISTS (texture_channel_pack)
- BUT: no pipeline step calls any of them during compose_map
- No splatmap-to-image export for Unity Terrain alphamap

---

## 11. EXPORT PIPELINE

### 11.1 What Works (AAA Quality)
- FBX export with roughness→smoothness inversion
- UV2 lightmap layer auto-generation
- Collision mesh naming (UCX_ prefix for Unity)
- Material texture type classification
- LOD pipeline with silhouette-preserving decimation (14-view analysis)
- Pipeline state checkpoint/resume with atomic writes

### 11.2 Gaps
- No FBX export step in compose_map (only heightmap export)
- No texture bake step in pipeline
- No LOD generation step in pipeline
- No collision mesh generation step
- No game_check validation before export
- No visual QA contact sheet step
- No vegetation instance serialization (Blender scatter → Unity TreeInstance)
- No splatmap transfer (vertex colors → Unity alphamap)
- No per-chunk heightmap export
- No prefab deduplication
- No interior mesh export with streaming trigger metadata

---

## 12. AUDIO SYSTEM

### 12.1 Current State
- FootstepManager exists — PhysicMaterial path only, no splatmap detection
- Reverb zones, spatial audio, occlusion, audio LOD — all exist
- Adaptive music, audio pool — exist
- ~60% of audio needs covered

### 12.2 Gaps
- No terrain splatmap-based footstep detection (biggest gap)
- No ambient zone crossfading
- No weather audio layers
- No water spline emitters
- No movement speed/armor weight modifiers
- No audio metadata export from Blender (JSON sidecar needed)
- 14 surface types needed, ~518 audio samples minimum
- Biome-coordinated fog/atmosphere not linked to audio zones

---

## 13. BLENDER TOOL/CAMERA FINDINGS

### 13.1 Tool Verification (169 actions tested)
- 15/16 tools PASS
- 1 partial failure: `set_shading` screenshot capture crashes (enum error)
- Camera manipulation: WORKS via blender_execute + forced camera view
- `blender_viewport navigate`: WORKS when camera exists in scene
- `contact_sheet`: WORKS for multi-angle views

### 13.2 Camera Issues
- No camera in scene by default — must create one
- Viewport capture capped at 1024px by MCP tool
- Camera view not applied by blender_execute unless forced via `region_3d.view_perspective = 'CAMERA'`

### 13.3 Security Sandbox
- `os`, `pathlib`, `io`, `tempfile`, `glob`, `fnmatch` added to ALLOWED_IMPORTS
- Removed from BLOCKED_IMPORTS
- Both copies updated (addon + server)
- **Server needs restart** for changes to take effect — use `bpy.app.tempdir` as workaround

---

## 14. RESEARCH LIBRARY (22 documents)

See `.planning/research/RESEARCH_INDEX.md` for full index with phase-to-doc mapping.

Key docs:
1. AAA Procedural City/Terrain Best Practices
2. AAA Procedural Terrain Research
3. AAA Terrain Texturing Research
4. AAA Texture Topology Quality
5. AAA Weapon Visual Standards (IN PROGRESS)
6. AAA Terrain Visual Standards
7. AAA Architecture Visual Standards
8. Biome Visual Reference Guide (13 biomes)
9. Boulder/Rock Formation Design
10. Canonical Pipeline Design (21 steps)
11. Cliff/Cave/Canyon Design
12. Mountain Pass/Canyon Design
13. Riggable Physics Mesh Quality
14. Spline Terrain Deformation
15. Terrain Audio System
16. Terrain Feature Visual Details (exact measurements)
17. Terrain Final Polish
18. Terrain Meshing Techniques
19. Terrain Transition Best Practices
20. Water-Rock Interaction Design
21. Web Research Terrain Pipeline
22. Research Index (phase-to-doc mapping)

---

## 15. IMPLEMENTATION PRIORITY ORDER

### Tier 0: Pipeline Fixes (DO FIRST — everything else depends on this)
1. Fix `_LOC_HANDLERS` dispatch bugs (3 routing issues)
2. Fix Z=0 hardcoding (42 instances across 9 files)
3. Fix deprecated Blender API (6 instances)
4. Fix Y-axis vertical stacking (grep entire codebase)
5. Wire smart planner `compose_world_map` into compose_map

### Tier 1: Core Systems (highest visual impact)
6. Fix vegetation scatter — use VEGETATION_GENERATOR_MAP instead of cubes
7. Fix castle generation — route through settlement_generator + modular kit
8. Wire HeightBlend + fix terrain materials (14 biome palettes exist but unused in scene)
9. Fix water system — shaped river mesh, not flat quad
10. Wire spline-terrain deformation (rivers + roads)
11. Add smootherstep to ALL terrain feature transitions (14+ locations)
12. Add scree/talus at every cliff base

### Tier 2: Quality Upgrades
13. Add micro-undulation to terrain
14. Add height-based texture blending (rocks through grass)
15. Add macro variation layer (break tiling)
16. Add wet rock material
17. Implement density noise modulation for scatter
18. Add object embedding (sink rocks 10-30%)
19. Fix boulder generation — convex hull, not icosphere
20. Add 6+ missing rock types
21. Fix weapon geometry — hilt connection, guard quality, materials
22. Fix creature orientation (animals upside down)

### Tier 3: New Systems
23. Veil corruption system
24. Per-biome atmosphere
25. Zone classification + encounters
26. World traversal infrastructure (bridges, caves, passes)
27. Audio metadata export
28. Missing riggable prop generators (curtains, shutters, ropes)

### Tier 4: Export Pipeline
29. Add texture bake step to pipeline
30. Add FBX export step for all non-terrain objects
31. Add LOD generation step
32. Add game_check validation step
33. Add visual QA contact sheet step
34. Vegetation instance serialization for Unity
35. Splatmap-to-image export for Unity

### Tier 5: Polish
36. Fix chain poly count (288 → 80 tris/link)
37. Fix flag cloth density
38. Add cloth-to-bone bake pipeline
39. Add terrain skirt geometry
40. Add micro-detail normal maps
41. Add curvature-driven wear to all materials
42. Web research pipeline for biome reference images

---

## 16. ITEMS MISSING FROM INITIAL DRAFT (added during scan)

### 16.1 Pipeline Gaps Not Yet Documented
- `_LOC_HANDLERS["castle"]` routes to `world_generate_castle` (box generator) instead of `world_generate_settlement` with castle type — this is THE reason castles are boxes
- `_LOC_HANDLERS["hearthvale"]` routes to `world_generate_hearthvale` (simplified) instead of full settlement pipeline
- `handle_spline_deform` EXISTS but has bug: no `bm.normal_update()` after vertex deformation — stale normals/lighting
- `building_interior_binding.py` is NOT IMPORTED in `__init__.py` — not just "not called", it's not even loadable as a handler
- `compose_map` calls `handle_create_water` which IS AAA-quality with spline-following mesh + flow vertex colors — but the CURRENT SCENE has a flat quad, meaning compose_map either called a DIFFERENT water function or parameters were wrong

### 16.2 Terrain Bugs Not Yet Documented
- **18 specific terrain feature bugs** from detailed scan (all filed in agent output but not in master doc):
  - coastline.py:411-422 — material zone boundary discontinuity (hard thresholds)
  - coastline.py:98-139 — shoreline profile uses linear amplitude, no smootherstep
  - coastline.py:180 — land_factor uses linear zone interpolation
  - terrain_features.py:131-145 — canyon floor has no scree at wall-floor junction
  - terrain_features.py:160,186 — canyon wall uses linear taper
  - terrain_features.py:333 — waterfall wet zone hard threshold at x=0.4
  - terrain_features.py:372-391 — pool surface has no physics-based deformation
  - terrain_features.py:320 — cliff face noise displacement without fade curve
  - terrain_features.py:530-535 — cliff face material zones use discrete thresholds
  - terrain_features.py:446-630 — cliff face has NO scree at base
  - terrain_features.py:742-743 — swamp island falloff double-squared (hyper-steep)
  - terrain_features.py:776-787 — swamp material zones hard thresholds
  - terrain_features.py:1008 — natural arch pillar uses linear taper
  - terrain_features.py:983-1032 — natural arch NO scree at pillar base
  - terrain_features.py:977-981 — arch ring discrete segment material assignment
  - _terrain_erosion.py:285 — thermal erosion 50% transfer rate potential instability
- **4 UNAUDITED terrain features** that likely have identical issues: generate_sinkhole, generate_floating_rocks, generate_ice_formation, generate_lava_flow
- **Ford crossings** completely absent (no shallow water gravel-bed crossing option)
- **Bridge approach terrain** missing (no abutments, retaining walls, approach ramps)
- **Cave/dungeon entrance** terrain deformation missing (placed as POIs without cutting into hillsides)
- **Waterfall mist zone** missing from generator (no downstream channel, no spray vegetation density)

### 16.3 Vegetation Bugs Not Yet Documented
- Poisson disk sampling is O(n²) — should use Bridson's algorithm with grid acceleration
- Wind vertex colors baked ON CUBES (useless data on placeholder geometry)
- LOD metadata set on cubes (meaningless)
- Grass cards ignore terrain slope (float vertically on hillsides instead of tilting)
- Leaf card canopy fixed at 6-12 planes regardless of tree size (small trees too bushy, large trees too sparse)
- Root generation always radial — no directional bias toward water/slope
- Wind vertex colors use deterministic hash, not seed — identical trees sway in sync
- `_CATEGORY_MATERIAL_MAP["vegetation"]` = "bark" — leaves, grass, bushes ALL get bark material

### 16.4 Settlement/Interior Bugs Not Yet Documented
- **Interior spec missing critical data**: floor heights for multi-floor buildings, wall/ceiling thicknesses, vertical door constraints
- **Door generation disconnected**: `generate_door_metadata()` creates doors at wall positions but DOES NOT verify they match actual building openings — doors could be placed outside building bounds
- **Room spatial validation missing**: `align_rooms_to_building()` doesn't verify rooms fit within building bounds — can produce zero/negative room dimensions
- **Internal room-to-room doorways not threaded through pipeline**: `_building_grammar.py` can generate same-floor internal doors, but `building_interior_binding` / compose pipeline only carry exterior door metadata forward
- **Settlement scaling mismatch**: code has village=4-8 (plan says 15), city=20-40 (plan says 100+), no "hamlet" type at all
- **NPC spawn points absent**: settlement generates buildings+props but no NPC markers (position, role, patrol area) — DEFERRED to future milestone
- **Interior streaming metadata missing**: door_metadata produces interior_scene_name but no streaming volume bounds or loading zone trigger geometry for Unity
- **Coastline materials NEVER APPLIED**: coastline.py:426 returns mesh spec and material indices but DOES NOT generate actual materials — integration completely lost

### 16.5 Weapon/Generator Bugs Not Yet Documented
- quality_sword handler may generate terrain alongside sword (shared handler issue — found by killed agent, not verified)
- Chest confirmed: 102 verts, white, ZERO materials
- ALL generators produce ZERO materials — geometry only, no PBR assignment
- Armor generators lack anatomical fit validation — no integration with player character skeleton
- Clothing system lacks cloth simulation geometry — simple mesh shells, no proper vertex density for deformation

### 16.6 Material Bugs Not Yet Documented
- Castle roughness textures ALL BLACK despite code defining correct roughness values — the TEXTURE CREATION step generates blank black images, not that materials aren't assigned
- 8 biomes referenced in BIOME_VISUAL_REFERENCE_GUIDE.md lack palette definitions in terrain_materials.py: River Valley, Cliff/Canyon, Lake/Pond, Rocky Highland, Volcanic/Ashen, Frozen/Tundra, Castle Approach, Rolling Plains
- Wet rock material referenced as zone name in terrain_features and coastline but NEVER CREATED as actual material

### 16.7 Tool/Infrastructure Bugs Not Yet Documented  
- Viewport capture capped at 1024px by MCP tool — cannot increase for quality inspection
- `set_shading` action: changes shading OK but screenshot callback crashes with enum error `bpy_struct: item.attr = val: enum "" not found in ()`
- Security sandbox fix applied but MCP server needs restart — `bpy.app.tempdir` workaround available
- No auto-camera creation — every fresh scene needs manual camera setup before screenshots work

### 16.8 Research Gaps
- AAA_WEAPON_VISUAL_STANDARDS.md — agent killed before completing, needs relaunch
- No AAA_CREATURE_VISUAL_STANDARDS.md — creatures never visually benchmarked against Monster Hunter/Elden Ring
- No AAA_RIGGABLE_PROP_VISUAL_STANDARDS.md — props never benchmarked against Skyrim/Dark Souls environmental props
- Spelling/grammatical errors in GSD agent research documents — need proofreading pass across all 22 docs

### 16.9 Missing Prop Categories (from terrain gap checker)
Not in any scatter system — these props are needed for a complete game world:
- Road signs / signposts at intersections
- Campfire sites (bandit camps, traveler rest stops)
- Fences / field boundaries around farms
- Gravestones / graveyard generation (religious quarter)
- Animal pens / stables (near farms/inns)
- Siege equipment near castle (catapults, ballistae)
- Corruption-themed props (twisted roots, glowing crystals, dead animals near Veil)
- Wayfinding markers (totems, cairns, ruined statues marking paths)

### 16.10 Additional Code Bugs Not Yet Documented
- **ARCH-028 tag** in `worldbuilding.py:2595-2637` — documented known issue in terrain height sampling, unresolved
- **terrain_advanced.py:1622-1666** — NaN handling fallback chain could propagate invalid data if all column values are NaN
- **terrain_advanced.py:189, 197** — Infinity return values in distance tracking without validation
- **_terrain_depth.py:544** — Import dependency on compute_slope_map without error handling
- **encounter_spaces.py** — ENCOUNTER_TEMPLATES hardcode XY positions with no water body awareness — arenas can be placed in rivers/lakes
- **light_integration.py:365** — No ambient light: only prop-based lights, no baseline ambient or biome-specific ambient color (forest green, dungeon purple)
- **light_integration.py:27-101** — LIGHT_PROP_MAP doesn't account for biome-specific lighting
- **atmospheric_volumes.py:110-159** — Only 10 of 21 biomes have atmosphere rules — 11 biomes fall back to DEFAULT_ATMOSPHERE
- **atmospheric_volumes.py** — No time-of-day integration (fireflies nocturnal, god_rays vary with sun angle)
- **road_network.py:151-206** — switchback_width not validated positive, zigzag can self-intersect
- **road_network.py:260-300** — Intersection classification exists but no intersection GEOMETRY (no curbing, turnouts, plazas)
- **building_quality.py** — `generate_battlements` merlons undersized: 0.6m wide / 0.8m tall vs historical 1.2-1.5m wide / 0.9-2.1m tall
- **generate_rock_mesh()** — Hardcoded seeds: every boulder is identical regardless of position
- **generate_cave_map** — Produces ZERO 3D geometry: grid-based topology ONLY, needs wrapper for 3D cavity meshes + terrain-integrated entrance
- **Coastline feature system** — METADATA ONLY: sea stacks, tide pools, rock outcrops all specced with sizes/positions but ZERO mesh generators built
- **Blender sandbox** — Blocks `class` definitions in blender_execute code
- **Blender collections** — Don't persist between separate blender_execute calls within same session

### 16.11 Important Nuances Missing from Main Sections
- **Material pipeline IS partially wired** through `handle_generate_multi_biome_world()` → `handle_create_biome_terrain()`, but the live multi-biome call passes `name` while the handler reads `object_name` — material creation can succeed while assignment still fails
- **Only 1 genuine duplicate** exists in entire codebase (two vegetation scatter functions). Everything else is proper layered architecture — we DON'T need to rip out duplicates
- **Erosion auto-scales to 150K+ minimum droplets** not 1000 — the erosion IS already AAA quality, just needs to be verified it's actually invoked during generation
- **A* road pathfinder** needs only a **quadratic steepness penalty** (not linear) to naturally produce switchback trails — small code change, huge visual impact
- **Dark fantasy cliff-ledge-slope rhythm** from FromSoftware — ridged multifractal generator ALREADY SUPPORTS this with right parameters
- **Canyon walls must share same strata profile** on both sides for geological consistency — not just independent cliff faces
- **mathutils.noise** provides multi_fractal, turbulence, VORONOI_CRACKLE directly — no external dependencies needed for rock displacement
- **scikit-learn CANNOT run inside Blender Python** — all image analysis (KMeans color extraction) must happen on MCP server side

### 16.12 Missing from Pipeline Steps
- **No collection organization step** — collection handlers (create_collection, move_to_collection, organize_by_type) exist but pipeline doesn't organize objects into collections
- **Atlas strategy not defined in pipeline** — per-chunk terrain atlas (2K), per-building-type (1K), vegetation billboard (512) 
- **Performance budget numbers** not enforced — 50K tris/chunk LOD0, 200 draw calls/chunk, 3x3 streaming window, 2M tris total loaded
- **NavMesh consideration** — terrain must be navmesh-friendly geometry, handled Unity-side after import
- **1-segment bevels on building geometry** — most visual quality per polygon invested, not in implementation priority list
- **Impostor/billboard atlas generation** — needs dedicated Blender render pass to capture 8 views per tree variant

### 16.13 Environmental Storytelling Terrain Types (missing from terrain system)
- **Battle aftermath**: scorched earth, impact craters, broken weapons in ground
- **Abandoned camp**: flattened grass, fire-blackened circle, cart tracks
- **Ancient ruins**: buried foundations visible, paving stone fragments, overgrown paths
- **Corrupted terrain**: cracked earth, glowing fissures, dead vegetation patterns

### 16.14 Weather Effects on Terrain Appearance (missing from materials)
- **Wet terrain**: darker base color, more reflective (lower roughness), pooling in depressions
- **Snow accumulation**: wind-sheltered areas first, north-facing, flat surfaces, gradual coverage
- **Fog interaction**: pools in valleys, thins on ridges, corruption fog wall at Veil boundary

### 16.15 Wiring Verification Checklist (user demanded NO MORE wiring issues)
Before declaring any phase complete, verify ALL of these:
- [ ] Handler registered in COMMAND_HANDLERS (__init__.py)
- [ ] Handler imported in __init__.py
- [ ] compose_map step calls the handler
- [ ] Handler uses _sample_scene_height() for Z placement
- [ ] Handler checks water_level before placement
- [ ] Handler accepts and threads seed parameter
- [ ] Handler applies materials (not leaving default grey)
- [ ] Handler uses smootherstep for transitions (not linear)
- [ ] Handler uses Z-up (not Y-up) for vertical
- [ ] Handler output verified visually in Blender with screenshot
- [ ] Handler output compared against AAA reference game

### 16.16 Missing AAA Visual Standards Research
- `AAA_WEAPON_VISUAL_STANDARDS.md` — agent killed before completing
- `AAA_CREATURE_VISUAL_STANDARDS.md` — never created, creatures not benchmarked
- `AAA_RIGGABLE_PROP_VISUAL_STANDARDS.md` — never created, props not benchmarked
- `AAA_INTERIOR_VISUAL_STANDARDS.md` — never created, interiors not benchmarked
- Need proofreading pass for spelling/grammar errors across all 22 research docs

### 16.17 Audio System Details Missing
- **FMOD recommended** as middleware (free under $500K revenue)
- **Existing VB audio covers ~60%**: footstep manager (PhysicMaterial only), reverb zones, spatial audio with occlusion, audio LOD, adaptive music, audio pool
- **Missing ~40%**: splatmap footstep detection, ambient zone crossfading, weather layers, water spline emitters, movement speed/armor weight modifiers

### 16.18 Implementation Utilities Needed
- `smootherstep(t)` utility function — used by 35+ locations, should be ONE shared function
- `safe_place_object(x, y, terrain_name)` wrapper — calls `_sample_scene_height()` + water exclusion check + bounds check, replaces 42+ Z=0 hardcodings
- Auto-camera setup function — creates camera + light + forces camera view, called at start of every visual QA step
- Render-to-file function — renders full resolution to disk bypassing 1024px viewport cap

### 16.19 Additional Full-Codebase Deep Scan Findings (2026-04-04)
- **`aaa_verify` can score stale screenshots** — `render_angle` / `viewport_screenshot` are aliases to the plain screenshot handler, yaw/pitch are ignored, the handler reads `filepath` not `output_path`, and old temp PNGs can be reused across runs
- **`compose_interior` discards binding geometry** — `building_interior_binding.py` returns room positions and `building_bounds`, but `_plan_interior_rooms()` replans from width/depth only and recomputes bounds, so binding-generated spatial alignment is lost
- **Multi-floor interior semantics not implemented in compose path** — examples advertise `below_ground`, `cellar`, `upstairs`, trapdoor, and staircase semantics, but composed room bounds and door defs remain effectively flat at Z=0
- **Interior quality passes silently no-op** — `compose_interior` sends room root `EMPTY` objects into `mesh_enhance_geometry` and `validate_prop_quality`; both expect mesh data and skip
- **`generate_map_package` group export is broken** — `derive_addressable_groups()` emits empty terrain/interiors groups, and `export_fbx` ignores `object_names`, so package exports are neither complete nor truly per-group
- **Settlement interiors are lost in canonical pipeline** — `compose_map` only consumes `map_spec.locations[].interiors`, while `handle_generate_settlement()` reduces interior data to furnishing props and strips real interior payload from its return
- **Linked interiors still fall back to fake 10x10 shells** — `compose_map` does not pass `building_exterior_bounds`, so `world_generate_linked_interior` uses its hardcoded fallback footprint
- **`scene_hierarchy.json` is not map-scoped** — manifest generation iterates all `bpy.data.objects` and uses name-substring district tagging, so reused scenes can leak helpers and unrelated objects into package metadata
- **`asset_pipeline action=performance_check` is a false capability** — MCP surface advertises it, but addon handler still returns `not_implemented`
- **Canonical location routing still bypasses advanced settlement types** — compose routing cannot reach richer `settlement_generator.py` types such as `medieval_town`, `city`, `wizard_fortress`, `cliff_keep`, or district-heavy layouts
- **Castle/world feature grounding remains incomplete** — drawbridge and fountain placement in castle flow still use hardcoded `Z=0`, and `handle_compose_world_map()` still places features with `pz = 0.0`
- **Terrain material builder duplicates materials on repeated runs** — biome material creation always makes new `VB_Terrain_<biome>` materials instead of reusing existing ones
- **`terrain_sculpt.py` world-space claim is false** — brush centers are evaluated against local vertex coordinates, so translated terrain sculpts the wrong area
- **`terrain_advanced.py` layers / erosion / stamps still use local or square assumptions** — multiple handlers normalize against dimensions/grid indices rather than true world coordinates
- **`handle_terrain_layers(add_layer)` still assumes square terrain** — layer sizing uses `sqrt(vertex_count)`, which breaks rectangular terrains
- **`terrain_chunking.compute_terrain_chunks()` drops remainder rows/cols** — heightmaps whose dimensions are not divisible by `chunk_size` are silently truncated
- **`terrain_sculpt.py` is not actually pure-logic/testable** — module imports `bpy` / `bmesh` at import time and has no direct terrain sculpt tests
- **`env_scatter_vegetation` can crash on its normal success path** — `side` is defined only inside the square-grid fallback, then used unconditionally later for placement and normal alignment
- **Scatter stack still assumes square, origin-centered terrain** — height sampling and vegetation placement use `max(dims.x, dims.y)` and ignore terrain object translation, so rectangular or moved terrains drift
- **Road mesh materialization still warps on non-square terrain** — road generation uses X extent for both axes when converting mask/grid coordinates to world space
- **`env_export_heightmap(unity_compat=True)` silently squashes rectangular terrains to square** — export size is chosen from columns only, then both axes are resampled to that square target
- **`env_scatter_props` has an API wiring bug** — `area_name` is documented as the scatter/output area name but also used as the terrain object lookup key, so direct calls with a real area/collection name fall back to `Z=0`
- **Test coverage still misses live Blender-side handler failures** — current scatter/export/terrain tests emphasize pure logic or square-only cases and do not exercise the canonical Blender handler path for these bugs
- **Research index is incomplete for architecture/interiors/render/texturing** — `RESEARCH_INDEX.md` does not index several already-present architecture, interior, shader, castle-terrain, and texturing docs, so the research spine is narrower than the codebase scope
- **No explicit render QA research phase** — today’s research set still lacks a defined 3D model/contact-sheet validation workflow for buildings, interiors, castles, props, and textured assets

---

## SCORING METHODOLOGY (CORRECTED — EVIDENCE-BASED)

Previous scoring was based on CODE QUALITY — this is WRONG.
Correct scoring must be based on VISUAL OUTPUT in Blender.
**No philosophy. Count what you see.**

| Score | Definition | Visual Test |
|-------|-----------|-------------|
| PLACEHOLDER | Untextured primitives, white/grey, <500 verts for small assets | Can you tell what it IS without being told? |
| BASIC | Recognizable shape, 0 materials, no detail geometry | Does it have the right silhouette from 10m? |
| DECENT | Has materials, some detail, but flat/repetitive | Would a player screenshot it? No. |
| GOOD | PBR materials, edge wear, detail elements, correct proportions | Could this ship in an indie game? |
| AAA | Weathered, story-telling detail, unique silhouette, full PBR | Would this pass FromSoft/Bethesda art review? |

**Every score must include (NO ESSAYS):**
1. Material count (0 = instant PLACEHOLDER/BASIC cap)
2. Vertex count vs AAA reference range
3. LIST of visible detail features (not code claims — what you SEE)
4. LIST of missing features vs named AAA reference asset
5. One-line verdict

**zai prompt template for future scoring:**
```
Score this [asset type] as PLACEHOLDER/BASIC/DECENT/GOOD/AAA.
Rules: NO essays. Answer ONLY these 5 lines:
1. MATERIALS: [count] — [list what's visible: metal/wood/leather/none]
2. DETAIL I CAN SEE: [bullet list of visible geometry features]
3. DETAIL MISSING vs [specific AAA game asset]: [bullet list]
4. PROPORTION CHECK: [correct/wrong — specifics]
5. SCORE: [X] because [one reason]
```

---

## 17. COMPLETE VISUAL VERIFICATION SCORECARD (2026-04-04)

**Methodology:** Each generator called in clean Blender 5.0.1 scene, rendered at 1920x1080 with 3-point studio lighting via `blender_execute` (capture_viewport=false to avoid context bloat), saved to `C:/tmp/vb_visual_test/`, analyzed by zai AI art director against FromSoftware/Bethesda AAA standards.

### 17.1 WEAPONS (6/6 tested)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Sword | 586 | 0 | PLACEHOLDER | Disconnected hilt, blocky guard, no materials |
| Axe | 325 | 0 | PLACEHOLDER | Paper-thin pancake head, 2D cutout |
| Mace | 462 | 0 | BASIC | Some 3D form, undersized head |
| Bow | 356 | 0 | PLACEHOLDER | Simple curve, string is a line |
| Shield | 360 | 0 | PLACEHOLDER | Half-size (0.5m vs ~1m needed), flat, no heraldry |
| Staff | 330 | 0 | PLACEHOLDER | Straight cylinder, no orb |

### 17.2 ARMOR (3/3 tested)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Pauldron | 289 | 0 | PLACEHOLDER | Generic curved plate, no material zones |
| Chestplate | 347 | 0 | PLACEHOLDER | Simple rounded shape, no anatomical contour |
| Gauntlet | 281 | 0 | PLACEHOLDER | Amorphous form, unarticulated fingers |

### 17.3 CREATURES (2/7 work, 5 BROKEN)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Fantasy (chimera) | 2552 | 0 | BASIC | Distinct silhouette, no anatomy/musculature |
| Wolf (quadruped) | 2278 | 0 | BASIC | Generated UPSIDE DOWN, stick legs, smooth tubes |
| creature_mouth | — | — | **CRASHED** | `'tuple' object has no attribute 'get'` |
| creature_eyelid | — | — | **CRASHED** | Same error |
| creature_paw | — | — | **CRASHED** | Same error |
| creature_wing | — | — | **CRASHED** | Same error |
| creature_serpent | — | — | **CRASHED** | Same error |

### 17.4 RIGGABLE PROPS (10/10 tested)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Chest | 102 | 0 | PLACEHOLDER | Rounded box, no iron banding, no lock |
| Door | 72 | 0 | PLACEHOLDER | Flat slab, no handle/hinges, generated lying flat |
| Chain | 576 | 0 | BASIC | Recognizable links but uniform, no rust/wear |
| Flag | 205 | 0 | BASIC | Flat plane + pole, no heraldry, no cloth detail |
| Chandelier | 2480 | 0 | BASIC | Ring frame with candle arms, no ornament |
| Drawbridge | 208 | 0 | PLACEHOLDER | Flat planks, no hinge mechanism, no chains |
| Rope Bridge | 1024 | 0 | PLACEHOLDER | Uniform posts, no sag/wear/rope braid |
| Hanging Sign | 158 | 0 | PLACEHOLDER | Abstract panels, no carved lettering |
| Windmill | 676 | 0 | BASIC | Tower + blades recognizable, thin/flat blades |
| Cage | 916 | 0 | BASIC | Clean symmetric bars, no rust/dents/bending |

### 17.5 CLOTHING (1/1 tested)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Tunic (peasant) | 320 | 0 | BASIC | Generic primitive, not cloth-sim ready topology |

### 17.6 VEGETATION (0/2 — BOTH BROKEN)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| vegetation_tree | ? | 0 | **BROKEN** | Returns raw vertex JSON, never creates Blender object |
| vegetation_leaf_cards | 0 | 0 | **BROKEN** | 0 vertices, 0 cards generated |

### 17.7 WORLDBUILDING (6/9 tested, 1 API crash, 2 Blender crash)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Dungeon | 22152 | 0 | BASIC | Box rooms + hallways, 128x128m but only 3m tall, no environmental detail |
| Cave | 15576 | 0 | BASIC | Blocky voxel layout, 126x122m but only 4m tall, no stalactites |
| Building | 54246 | **11** | PLACEHOLDER | Most advanced generator — has walls/roof/windows but pristine white, no weathering |
| Castle | 14357 | 1 | BASIC | Curtain walls + towers + keep, solid layout but flat white, generic merlons |
| Ruins | 248 | 0 | PLACEHOLDER | Tiny wall fragments, 248 total verts |
| Interior (tavern) | 2196 | 1 | BASIC | Room shell + box furniture (bar, fireplace, tables), sterile |
| Modular Kit | 64 | 0 | PLACEHOLDER | 8 cubes (8 verts each), 260-piece system NOT generating |
| Boss Arena | — | — | **CRASHED** | `cap_fill` keyword invalid — Blender 5.0 API break |
| Town | — | — | **CRASHED BLENDER** | Crashes even at building_count=3, unstable handler |

### 17.8 ENVIRONMENT (3/3 tested)
| Asset | Verts | Mats | zai Score | Key Finding |
|-------|-------|------|-----------|-------------|
| Terrain | 4096 | 0 | PLACEHOLDER | White heightmap, no texturing, no micro-undulation |
| Water | — | 1 | PLACEHOLDER | Flat blue plane, hard jagged shoreline, no waves/foam |
| Road | — | 0 | **INVISIBLE** | path_length=1, painted on untextured terrain = invisible |

### 17.9 AGGREGATE SCORES
| Category | Tested | Working | PLACEHOLDER | BASIC | DECENT+ | BROKEN/CRASHED |
|----------|--------|---------|-------------|-------|---------|-----------------|
| Weapons | 6 | 6 | 5 | 1 | 0 | 0 |
| Armor | 3 | 3 | 3 | 0 | 0 | 0 |
| Creatures | 7 | 2 | 0 | 2 | 0 | **5** |
| Props | 10 | 10 | 4 | 6 | 0 | 0 |
| Clothing | 1 | 1 | 0 | 1 | 0 | 0 |
| Vegetation | 2 | 0 | 0 | 0 | 0 | **2** |
| Worldbuilding | 9 | 6 | 3 | 3 | 0 | **3** |
| Environment | 3 | 2 | 2 | 0 | 0 | **1** |
| **TOTAL** | **41** | **30** | **17** | **13** | **0** | **11** |

**ZERO assets scored DECENT or higher.**

### 17.10 UNIVERSAL FAILURES (confirmed across ALL generators)
1. **ZERO MATERIALS on 90%+ of assets** — building (11 mats) and castle (1 mat) are sole exceptions
2. **Material library (52 materials, 6 procedural generators) EXISTS but is NEVER CALLED** after mesh generation
3. **No dark fantasy character on ANY asset** — everything is pristine white, zero wear/weathering/story
4. **Orientation bugs** — wolf upside-down, door lying flat, shield horizontal
5. **Geometry is BASIC at best** — simple primitives, no sculpt detail, no edge wear
6. **Code claims don't match visual output** — variable names describe features that don't exist in mesh
7. **Proportion bugs** — shield half-size, axe paper-thin, mace head undersized, dungeon/cave only 3-4m tall
8. **260-piece modular kit generates 8 cubes** — the system exists but isn't wired
9. **Both vegetation generators are non-functional** — tree returns raw data, leaf_cards generates nothing
10. **5/7 creature part generators crash** with identical tuple error
11. **Town generator crashes Blender** — even at minimum parameters
12. **Boss arena uses deprecated Blender 5.0 API** — cap_fill keyword removed

---

## 18. AAA READINESS ASSESSMENT — DO WE HAVE WHAT WE NEED?

### 18.1 READY (infrastructure exists, mostly wiring fixes)

| System | Why Ready | What Exists | Fix Type | Effort |
|--------|-----------|-------------|----------|--------|
| **Terrain** | 8+ research docs, erosion is AAA quality, 14 biome palettes exist, HeightBlend node exists | Hydraulic/thermal erosion (auto-scales 150K+ droplets), BIOME_PALETTES_V2 (14 biomes x 4 layers), auto_assign_terrain_layers splatmap | Wire materials + HeightBlend + micro-undulation | MEDIUM |
| **Water** | AAA spline-following code already written | handle_create_water (spline mesh + flow vertex colors), handle_carve_river (A* pathfinding), Lagarde wet-rock PBR formulas documented | Fix compose_map to call correct water function with correct params | LOW |
| **Vegetation** | 15+ real mesh generators exist in code | VEGETATION_GENERATOR_MAP: L-system trees (4 species), shrubs, grass, mushrooms, rocks. BIOME_VEGETATION_SETS (14 biomes). Wind vertex colors. | Wire VEGETATION_GENERATOR_MAP into scatter, fix tree object creation | MEDIUM |
| **Modular Kit** | 260-piece system fully coded | 52 core pieces x 5 styles (medieval/gothic/fortress/organic/ruined), generate_modular_piece() dispatch, assemble_building() | Wire into generation pipeline, fix generate_modular_kit handler | MEDIUM |
| **Castle** | Settlement generator + modular kit exist but castle bypasses them | settlement_generator.py (15 types), modular building kit (260 pieces), road L-system, interior binding | Route castle through settlement_generator + modular kit instead of box generator | MEDIUM |
| **Building** | Already most advanced generator (54K verts, 11 mats) | Rubble stone walls, gable roof, windows/doors, multi-floor, facade modules, chimney | Add weathering, wire modular kit for variety, improve materials | LOW-MEDIUM |

### 18.2 PARTIALLY READY (code exists, needs significant work)

| System | What Exists | What's Missing | Effort |
|--------|-------------|----------------|--------|
| **Dungeon/Cave** | BSP room generation, cave cellular automata, door/loot placement | Modular kit integration for walls, height variation (>3m!), environmental detail, rock meshes, materials | HIGH |
| **Interior** | 14 room types, furniture placement, interior binding | Furniture quality (cubes→real meshes), material application, atmospheric props (candles, mugs, soot) | HIGH |
| **Road** | MST network, A* pathfinder, switchback generation | Depends on terrain materials first, needs mesh materialization fix for non-square terrain | MEDIUM (blocked by terrain) |
| **Weapons** | MATERIAL_LIBRARY (52 materials), PBR generators, attachment empties | Geometry needs 3-10x more verts, blade/guard/pommel shapes need redesign, material wiring | HIGH |
| **Ruins** | Damage system concept, debris generation | Only 248 verts output — needs building generator as base + destruction algorithm | HIGH |

### 18.3 NEEDS GEOMETRY REWRITE (research EXISTS — no missing docs)

| System | What's Missing | Research That Covers It | Effort |
|--------|---------------|------------------------|--------|
| **Creatures** | 5/7 crash (tuple bug), anatomy = smooth tubes | TEXTURING_CHARACTERS_RESEARCH, AAA_TOOLS_CHARACTER_EDITING_RESEARCH, AAA_PROCEDURAL_QUALITY_RESEARCH (Rigify templates for 6 creature types, PBR standards, SSS) | HIGH |
| **Armor** | Basic plates, no anatomical fit | TEXTURING_WEAPONS_ITEMS_RESEARCH, TEXTURING_CHARACTERS_RESEARCH (armor fitting with shape keys, modular assembly, PBR metallics) | HIGH |
| **Clothing** | Generic shell, not cloth-sim ready | TEXTURING_CHARACTERS_RESEARCH, RIGGABLE_PHYSICS_MESH_QUALITY (cloth topology, wind physics, cloth-to-bone bake) | HIGH |
| **Riggable Props** | Basic primitives | RIGGABLE_PHYSICS_MESH_QUALITY, TEXTURING_WEAPONS_ITEMS_RESEARCH (hinge rigging, constraint systems, deformable topology) | HIGH |

### 18.4 RESEARCH COVERAGE (CORRECTED — 61 docs, ALL 14 categories covered)

Previous assessment claimed 6 missing research docs. **This was WRONG.** Deep audit found 61 research documents (31 main + 28 phase-specific + 2 supplemental) covering ALL 14 generator categories:

| Category | Coverage | Key Research Docs |
|----------|----------|-------------------|
| Terrain texturing | EXCELLENT | AAA_TERRAIN_TEXTURING, terrain_materials_shader, terrain_gaea, BIOME_VISUAL_REFERENCE_GUIDE |
| Water systems | GOOD | WATER_ROCK_INTERACTION_DESIGN, terrain_opensource_algorithms, TERRAIN_FEATURE_VISUAL_DETAILS |
| Vegetation/trees | GOOD | AAA_PROCEDURAL_QUALITY, BIOME_VISUAL_REFERENCE_GUIDE, terrain_unity_performance |
| Castle/fortress | GOOD | castle_terrain_medieval_landscape, modular_building_kits, procedural_city_generation |
| Medieval buildings | GOOD | modular_building_kits, TEXTURING_ENVIRONMENTS, procedural_city_generation |
| Dungeon/cave | GOOD | CLIFF_CAVE_CANYON_DESIGN, castle_terrain_medieval_landscape |
| Weapons | EXCELLENT | TEXTURING_WEAPONS_ITEMS, AAA_PROCEDURAL_QUALITY (PBR material-tier system, damage viz) |
| Armor | EXCELLENT | TEXTURING_WEAPONS_ITEMS, TEXTURING_CHARACTERS (shape keys, weathering, PBR metallics) |
| Creatures | EXCELLENT | TEXTURING_CHARACTERS, AAA_TOOLS_CHARACTER_EDITING (Rigify 6 types, SSS, animation) |
| Riggable props | GOOD | RIGGABLE_PHYSICS_MESH_QUALITY (cloth sim, hinge rigging, wind physics) |
| Clothing | GOOD | TEXTURING_CHARACTERS, RIGGABLE_PHYSICS_MESH_QUALITY (cloth topology, wrinkle maps) |
| Interior design | GOOD | modular_building_kits, AI_INTERIOR_GENERATION, TEXTURING_ENVIRONMENTS |
| Road/path | GOOD | SPLINE_TERRAIN_DEFORMATION, MOUNTAIN_PASS_CANYON_DESIGN, TERRAIN_TRANSITION |
| Boss arena | GOOD | castle_terrain_medieval_landscape, terrain_lighting_atmosphere, CLIFF_CAVE_CANYON |

**NO MISSING RESEARCH. We have everything we need. The problem is execution, not knowledge.**

### 18.5 BOTTOM LINE

**CAN we get to AAA?** Yes, for ALL categories. We have:
- 61 research documents covering every generator category
- 52 materials + 6 procedural generators (unwired)
- 15+ vegetation generators (unwired)
- 260-piece modular building kit (unwired)
- AAA erosion system (already working)
- AAA water spline system (wrong function called)
- Settlement generator with 15 types (castle bypasses it)

**Priority order for maximum visual impact:**
1. **Wire material library** into ALL generators → every asset gets PBR (HIGHEST ROI)
2. **Fix vegetation** → wire VEGETATION_GENERATOR_MAP (code exists)
3. **Fix terrain materials** → wire 14 biome palettes + HeightBlend
4. **Fix water** → call correct AAA handler
5. **Wire modular kit** → 260 pieces for buildings/castles
6. **Fix creature crashes** → tuple error likely one shared handler bug
7. **Fix boss arena** → Blender 5.0 API (cap_fill → fill_type)
8. **Fix town generator** → crashes Blender, needs stability investigation
9. **Geometry overhaul** → weapons/armor/props need mesh redesign using existing research
10. **Fix orientation bugs** → wolf upside-down, door flat, shield horizontal

**What this means:** ~40% WIRING (connecting existing code), ~30% MATERIAL APPLICATION (calling existing generators), ~25% GEOMETRY REWRITE (redesigning meshes using existing research), ~5% BUG FIXES (API compat, crashes, tuple errors).

---

## 19. CROSS-SESSION FINDINGS (missing from previous sections)

### 19.1 Foundational Rules (must be codified globally)

| Rule | Detail | Source |
|------|--------|--------|
| **Coordinate system** | Z-up in Blender, Y-up in Unity. Conversion at EXPORT time ONLY. Never use Y for vertical in Blender code. | v5-v9 recurring bug |
| **Furniture rotation** | R = atan2(px - tx, py - ty) — derived from Blender's -Y forward convention | v8 interior fix |
| **Material creation** | When creating ANY Blender material, ALWAYS set Base Color. 6 sites found that create Principled BSDF without color. Use _assign_procedural_material() or create_material_from_library(). | v8 material color bug |
| **Dark fantasy palette** | Saturation <40%, Value 10-50%. Weathering: moss on north-facing, stone darkening at base, rust patina, timber grain exposure. | Style reference |
| **Smootherstep everywhere** | Replace ALL `(1 - t)` linear interpolation with `t * t * (3 - 2 * t)`. 35+ locations need this. Create ONE shared utility function. | v9 terrain audit |
| **Safe placement** | Create `safe_place_object(x, y, terrain_name)` wrapper: _sample_scene_height() + water exclusion + bounds check. Replaces 42+ Z=0 hardcodings. | v9 systemic bugs |

### 19.2 Data Loss Vulnerabilities

| Bug | Impact | Location |
|-----|--------|----------|
| **Tripo texture overwrite** | cleanup() OVERWRITES embedded textures with BLANK IMAGES — silent asset corruption | Tripo pipeline cleanup function |
| **Save data SAVE-02** | DeleteFile(oldSavePath) BEFORE replacement write completes — crash = permanent save loss | Unity save system |
| **Checkpoint atomicity** | interior_results = [] wipe not inside checkpoint guard — no atomic writes via temp+rename | compose_interior pipeline |

### 19.3 Integration & Capability Gaps

| Gap | Detail | Impact |
|-----|--------|--------|
| **Code reviewer FP rate** | 69% false positive rate (976 FPs from BUG-25 ClassLevel scope). 7 root cause P-levels documented but not fixed. | Quality gate unreliable |
| **Real-time Unity bridge** | Only 10 real-time commands, everything else generates scripts requiring recompile. Need 16+ CRUD/component operations. | Iteration speed |
| **MCP permission blocks** | Tools denied during autonomous background agent execution | Automation blocker |
| **Material auto-assignment** | 45+ procedural materials exist. Building grammar stamps material_category. mesh_from_spec needs to assign materials to faces. Integration gap. | All generators white |

### 19.4 Quality Parameters

| Parameter | Current | Required | Location |
|-----------|---------|----------|----------|
| Terrain erosion droplets | 1,000 | 50,000+ | _terrain_erosion.py (NOTE: v9 audit says auto-scales to 150K — VERIFY which is correct) |
| Tree canopy | Sphere clusters | L-system branching | vegetation_system.py |
| Branch ring segments | 6 | 8 (for closeup) | L-system tree generator |
| L-system iterations | Hardcoded 4 | Should be 5 (dead trees: 7) | VEGETATION_GENERATOR_MAP |
| Merlon dimensions | 0.6m wide / 0.8m tall | 1.2-1.5m wide / 0.9-2.1m tall (historical) | building_quality.py |
| Chain tris/link | 288 | 80 | Chain generator |
| Dungeon ceiling height | 3m | 6-8m minimum for dark fantasy | Dungeon generator |
| Cave ceiling height | 4m | Variable 3-20m with stalactites | Cave generator |

### 19.5 Tripo Studio Integration

Reverse-engineered subscription API unlocks 8000/month free credits (vs pay-per-API):
- Endpoints: /v2/web/ prefix
- Auth: JWT with auto-refresh
- Features: 4 variants per generation, balance tracking via /v2/web/user/profile/payment
- This is THE integration method for Tripo — documented in project_tripo_studio_client memory

### 19.6 Building Foundation System (added v8, must be preserved)

5-point terrain sampling + flatten_terrain_zone + foundation mesh generation prevents floating buildings. This is an ARCHITECTURAL PATTERN for all future terrain-integrated structures.

### 18.7 CONTEXT BLOAT SOLUTION (discovered during this audit)
All MCP tools support `capture_viewport: false` parameter. Combined with render-to-disk via `blender_execute` + `zai analyze_image` for grading, this keeps ZERO images in conversation context. Use this workflow for all future visual QA:
1. Generate with `capture_viewport: false`
2. Render to disk: `bpy.ops.render.render(write_still=True)`
3. Grade with `mcp__zai-mcp-server__analyze_image` (text-only response)
4. Use `blender_viewport quick_preview` ONLY for camera framing verification
