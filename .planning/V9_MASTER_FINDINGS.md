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
- **Internal room-to-room doorways missing**: only exterior doors generated, no connections between kitchen→bedroom within same building
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
- **Material pipeline IS wired** through `handle_generate_multi_biome_world()` → `handle_create_biome_terrain()`. The current scene's grey materials suggest compose_map invoked a DIFFERENT code path or wrong parameters — not that materials are fundamentally broken
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

---

## SCORING METHODOLOGY (CORRECTED)

Previous scoring was based on CODE QUALITY — this is WRONG.
Correct scoring must be based on VISUAL OUTPUT in Blender.

| Score | Definition | Reference |
|-------|-----------|-----------|
| PLACEHOLDER | Flat untextured shapes, grey/white, no detail | 3D mockup / greybox |
| BASIC | Correct general shape but flat materials, obviously procedural | First-pass blockout |
| DECENT | Textured, some detail elements, but wouldn't pass studio review | Student project level |
| GOOD | Proper materials, good detail, but missing wear/weathering/micro-detail | Indie game level |
| AAA | Would ship in Elden Ring/Dark Souls/Skyrim | FromSoft/Bethesda level |

**Every score must be backed by:**
1. Visual screenshot from Blender
2. Named AAA game reference for comparison
3. Specific gap list preventing higher score
