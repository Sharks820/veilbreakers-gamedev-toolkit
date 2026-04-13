# Terrain Deep Research — 2026-04-13

## Executive Summary

6-agent deep dive across GitHub research + full codebase audit. The terrain pipeline has **strong foundation code** (WaterNetwork graph, cave archetypes, material channels, waterfall hydrology) but **critical wiring failures** that mean none of this actually produces visible results in Blender.

**3 CRITICAL blockers** prevent procedural terrain generation:
1. Caves are mask-stack metadata only — no 3D mesh carving
2. Waterfalls are flat billboard planes — volumetric profile never consumed
3. Water pipeline has 6 disconnection points — graph → mesh never bridged

---

## Part 1: Codebase Audit (20 Bugs/Gaps)

### Critical (Block ALL terrain generation)

| # | Area | File:Line | Bug |
|---|------|-----------|-----|
| 4 | Waterfall | terrain_waterfalls.py + _terrain_depth.py | Volumetric mesh is mandated but NEVER built — all meshes are flat curtain planes |
| 9 | Caves | terrain_caves.py:867 | cave_height_delta is recorded but never applied — caves are mask-stack metadata, not 3D geometry |

### High (Block specific features)

| # | Area | File:Line | Bug |
|---|------|-----------|-----|
| 2 | Water | environment.py:4050 | Water meshes don't use WaterNetwork tile contracts — no cross-tile continuity |
| 5 | Waterfall | terrain_waterfalls.py:745 | waterfall_pool_delta written but never applied to geometry |
| 6 | Waterfall | terrain_waterfalls_volumetric.py:60 | 7 functional objects named/validated but never instantiated |
| 8 | Water | _water_network.py:394 | Tile contracts computed but never consumed by mesh generators |
| 18 | Pipeline | terrain_twelve_step.py:44,47 | Steps 4 (flatten) and 5 (river carves) are stubs returning input |

### Medium (Quality issues)

| # | Area | File:Line | Bug |
|---|------|-----------|-----|
| 1 | Water | environment.py:4292 | Foam is vertex-color only — no foam mesh/particles |
| 3 | Water | environment.py:3756 | Lake water is flat plane with no depth/flow |
| 7 | River | environment.py:2439 | River width is fixed — flow-accumulation width exists but unwired |
| 12 | Materials | terrain_materials_v2.py:39 | Materials are scalar hex colors, not PBR textures |
| 13 | Materials | environment.py:2301 | 5-layer splatmap has no Blender node tree consumer |
| 14 | River | _terrain_noise.py:844 | Carved geometry follows jagged A* grid, smoothing only affects display |
| 16 | Stitching | environment.py:2280 | Seam stitching has no blending band |
| 19 | Water | terrain_water_variants.py:581 | 6 variant detectors defined but never called by pass |

### 6 Pipeline Breaks (Water System)

1. **pass_waterfalls** passes `river_network=None` — ignores WaterNetwork
2. **Wet-rock mask** passes `water_network=None` — ignores WaterNetwork
3. **pass_water_variants** ignores its own detect_* functions
4. **handle_create_water** ignores WaterNetwork entirely
5. **Volumetric functional objects** never created
6. **compose_map** doesn't bridge graph to geometry

### Flow Speed Bug
Flow speed IS calculated per-vertex but stored as `shore_proximity` in R channel, not actual speed. Shaders cannot animate based on flow velocity.

---

## Part 2: GitHub Research — Best Open-Source Tools

### Terrain Generation & Erosion

| Project | Stars | Lang | Use Case |
|---------|-------|------|----------|
| **Infinigen** (Princeton) | 6,900 | Python/Blender | Full world gen — code extraction for terrain/water algorithms |
| **terrain-erosion-3-ways** | 924 | Python/NumPy | **DROP-IN**: River-first terrain gen (Method 3), erosion |
| **SimpleHydrology** (weigert) | 701 | C++ | Gold standard procedural rivers — port algorithms |
| **SebLague/Hydraulic-Erosion** | 1,000 | C#/HLSL | Compute shader erosion reference |
| **TerraForge3D** | 1,200 | C++/GLSL | External terrain+texturing tool with node editor |
| **terrain-diffusion** | 123 | Python | AI-based heightmap generation (diffusion models) |
| **pydelatin** | 84 | C/Python | pip-installable optimized terrain mesh from heightmaps |

### Water & River Systems

| Project | Stars | Lang | Use Case |
|---------|-------|------|----------|
| **meanderpy** | 158 | Python | **DROP-IN**: Natural river meanders, oxbow lakes |
| **RiverBuilder** (Pasternack Lab) | 17 | Python | River valley + cross-section geometry |
| **UnityTerrainErosionGPU** | 152 | C#/HLSL | Shallow water equation erosion |

### Cave Generation

| Project | Stars | Lang | Use Case |
|---------|-------|------|----------|
| **fogleman/sdf** | 1,900 | Python | SDF mesh gen + boolean ops — **CORE TOOL** |
| **trimesh** | 3,500 | Python | `boolean.difference()` for cave carving |
| **P.L.U.M.E** | ~5 | Python/Blender | Blender-native cave gen with graph skeleton |
| **Caveworm** | 13 | Java | Simplex worm tunnel algorithm |
| **AK-Saigyouji/Procedural-Cave-Generator** | 315 | C# | Three-tiered floor/ceiling/wall meshes |
| **SebLague/Procedural-Cave-Generation** | 460 | C# | Cellular automata + marching squares reference |
| **scikit-image marching_cubes** | stdlib | Python | 3D numpy → mesh extraction |

### Terrain Texturing

| Project | Stars | Lang | Use Case |
|---------|-------|------|----------|
| **txa_ant** | 138 | Python/Blender | **DROP-IN** slope-based terrain texturing addon |
| **BlenderGIS** | 8,900 | Python | Real terrain import + shader nodes |

---

## Part 3: Implementation Strategy

### Priority 1: Water Connectivity (Wire the existing code)

**Problem**: 3 layers of water code exist but don't connect.
**Solution**: Bridge WaterNetwork graph → mesh generation.

1. In `pass_waterfalls`, pass the actual WaterNetwork instead of None
2. In `compose_map`, build WaterNetwork from heightmap FIRST, then use it to:
   - Route rivers (replace manual A* with network paths)
   - Place waterfalls (at network-detected steep drops)
   - Carve basins (at network-detected pits)
3. Store flow speed in vertex colors (currently only shore proximity is stored)
4. Wire pass_water_variants to call its own detect_* functions
5. Apply waterfall_pool_delta to geometry (currently dead code)

**External code needed**: meanderpy for natural river curves.

### Priority 2: 3D Cave Generation (New code + libraries)

**Problem**: Current caves are 2D heightmap masks only.
**Solution**: Voxel-based 3D cave volumes with mesh extraction.

Algorithm:
1. Use existing archetype paths from terrain_caves.py as cave centerlines
2. Create 3D numpy voxel grid matching terrain bounds
3. For each cave path point: carve spheres/ellipsoids along centerline
4. Apply 3D cellular automata (26-neighbor rule) for organic smoothing
5. Use `scikit-image marching_cubes` to extract mesh
6. Use `trimesh.boolean.difference(terrain_mesh, cave_mesh)` to cut entrances
7. Flip interior normals for inside viewing

**External code needed**: scikit-image, trimesh (or fogleman/sdf).

### Priority 3: Waterfall Volumetric Mesh (Implement existing spec)

**Problem**: WaterfallVolumetricProfile spec exists but is never consumed.
**Solution**: Build the mesh generator that the validators already check.

1. Consume WaterfallVolumetricProfile from terrain_waterfalls.py
2. Generate thick tapered prism mesh (48 verts/m, curved front)
3. Create all 7 functional objects (sheet_volume, foam_layer, mist_volume, etc.)
4. Place at waterfall chain lip→pool positions

### Priority 4: Water Flow Animation Shader

**Problem**: Flow data in vertex colors but no shader reads it.
**Solution**: Create Blender shader node tree reading flow_vc.

1. Fix vertex color encoding: R=flow_speed (not shore proximity), G=dir_x, B=dir_z, A=foam
2. Build shader: UV offset driven by flow direction × time
3. Procedural foam breakup at shore edges (noise × foam alpha)
4. Shore wave direction matching flow direction
5. Depth-based color (clear shallow → dark deep)

### Priority 5: Terrain Texturing (Wire existing + addon)

**Problem**: Materials V2 splatmap exists but no Blender shader consumes it.
**Solution**: Build 5-layer terrain shader reading splatmap vertex colors.

1. Extract approach from txa_ant Blender addon (slope-based vertex groups)
2. Build Blender node tree with 5 material channels from Materials V2
3. Triplanar mapping for cliff channel
4. Height-blended transitions using MaterialChannelExt gamma curves
5. Wetness overlay from wet_rock mask channel

### Priority 6: Terrain Node Stitching (Blending band)

**Problem**: Edge stitching only averages Z at boundary, no blend zone.
**Solution**: Add N-cell blending band that feathers heights.

### Priority 7: Forest & Clearing Generation

**Problem**: Needed for gameplay areas.
**Solution**: Scatter system with density map from biome data.

1. Forest placement from vegetation density + terrain slope
2. Clearing detection from open-area analysis
3. Monster combat arena placement on clearings
4. Tree LOD system for performance

---

## Part 4: Recommended Execution Order

### Phase A: Fix Water Pipeline (1-2 days)
- Wire WaterNetwork to compose_map mesh generation
- Fix flow speed vertex color encoding
- Wire pass_water_variants to call its detectors
- Apply waterfall_pool_delta to geometry
- Integrate meanderpy for natural river curves

### Phase B: Water Flow Shader (0.5 day)
- Build animated water shader reading flow_vc
- Foam breakup, shore waves, depth color

### Phase C: Volumetric Waterfalls (1 day)
- Implement volumetric mesh from existing WaterfallVolumetricProfile
- Create 7 functional objects per chain
- Connect to compose_map pipeline

### Phase D: 3D Cave System (2-3 days)
- pip install scikit-image trimesh
- Build voxel carver consuming existing cave paths
- Marching cubes → boolean difference pipeline
- Test with each archetype

### Phase E: Terrain Texturing (1 day)
- Build 5-layer shader from Materials V2 splatmap
- Triplanar for cliffs, height-blended transitions
- Wetness overlay

### Phase F: Multi-Terrain Connection (0.5 day)
- Blending band for edge stitching
- Matching heightmap edges across tiles

### Phase G: Forest & Clearings (1 day)
- Vegetation scatter with density map
- Combat arena clearing placement
