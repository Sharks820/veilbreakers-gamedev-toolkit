# VeilBreakers Master Research & Gap Analysis
## Complete Findings from 27 Research Streams

**Date:** 2026-04-02
**Research Streams:** 30 completed (22 Opus + 5 Wave 3 + 3 Final Sweep)
**Research Files:** 60+ documents, ~2MB total
**Gaps Identified:** ~125 unique across all categories
**Bugs Found:** 72 (8 crash, 22 high, 28 medium, 14 low)
**Tests Passing:** 19,348

### Bug Scan Files
- codebase_bug_scan.md (5 bugs - initial scan)
- bug_scan_handlers_deep.md (20 bugs - all 24 handler files)
- bug_scan_unity_tests_deep.md (7 bugs - Unity server + C# gen)
- bug_scan_worldbuilding_deep.md (20 bugs - settlement/interior/worldbuilding)
- bug_scan_materials_mesh_deep.md (20 bugs - materials/LOD/vegetation/mesh)

### Gap Analysis Files
- terrain_gap_analysis.md (40 gaps)
- toolkit_full_gap_analysis.md (67 gaps)
- final_gap_scan.md (31 NEW gaps)

### TOP 10 MOST CRITICAL BUGS
1. Billboard quads face +Z (flat on ground) — ALL distant tree LODs invisible
2. Hearthvale concentric_organic layout falls through to random scatter — town layout broken
3. pipeline_state import triggers import bpy outside Blender — compose_map crashes
4. Water mesh double-height (vertex Z + obj.location both set to water_level)
5. Slope angles wrong everywhere (compute_slope_map ignores cell size)
6. Terrain reshape crashes on non-square meshes (4 locations)
7. TripoStudioClient wrong param name (jwt_token vs session_token)
8. TripoStudioClient not imported in generate_prop action
9. Floor height hardcoded 3.5m but buildings range 3.4-6.0m — interior clipping
10. Two incompatible wind vertex color functions — Unity shaders break

### TOP 10 NEW GAPS (from final_gap_scan.md)
1. Corruption/weather/time-of-day are ALL visual-only — zero gameplay effects
2. Footstep system can't work on Unity Terrain (reads PhysicMaterial, terrain uses splatmaps)
3. All enemies share single FSM pattern — no archetype library
4. No hardware auto-detect for quality presets on first launch
5. Animation retargeting missing — can't share anims across different creature sizes
6. Quest system generates data but no in-game tracking/waypoints
7. No automated performance benchmark suite
8. No crash recovery (resume from last checkpoint)
9. Environmental storytelling placement is random (not designed)
10. Dialogue choices have no consequences

---

## TABLE OF CONTENTS

1. [Terrain Generation](#1-terrain-generation)
2. [Erosion Algorithms](#2-erosion-algorithms)
3. [Terrain Materials & Texturing](#3-terrain-materials--texturing)
4. [Performance Architecture](#4-performance-architecture)
5. [Model Size Budgets](#5-model-size-budgets)
6. [Tripo Asset Pipeline](#6-tripo-asset-pipeline)
7. [Vegetation & Foliage](#7-vegetation--foliage)
8. [Water Systems](#8-water-systems)
9. [Lighting & Atmosphere](#9-lighting--atmosphere)
10. [VFX Systems](#10-vfx-systems)
11. [Physics, Collision & NavMesh](#11-physics-collision--navmesh)
12. [Shader & Rendering Pipeline](#12-shader--rendering-pipeline)
13. [Asset Pipeline & Build](#13-asset-pipeline--build)
14. [Dark Fantasy RPG Design](#14-dark-fantasy-rpg-design)
15. [The Veil Mechanic](#15-the-veil-mechanic)
16. [Toolkit Gap Analysis](#16-toolkit-gap-analysis)
17. [Codebase Bugs](#17-codebase-bugs)
18. [UI/UX & Player Systems](#18-uiux--player-systems)
19. [Critical Blockers Summary](#19-critical-blockers-summary)
20. [Style Reference](#20-style-reference)

---

## 1. TERRAIN GENERATION

**Sources:** terrain_gaea_research.md, terrain_worldmachine_research.md, terrain_blender_tools_research.md, terrain_opensource_algorithms_research.md, terrain_blender_api_context7_research.md, codebase terrain audit

### Current State
- OpenSimplex noise with fBm, 8 terrain presets, domain warping at 0.4 strength
- Single 3x3 box blur smoothing pass (INADEQUATE)
- Particle-based hydraulic erosion at 150K iterations (TOO LOW)
- Thermal erosion at 10 iterations (TOO LOW)
- 14 biome palettes, vertex color splatmaps

### What Must Change

**Noise Generation (_terrain_noise.py):**
- Domain warp: 0.4 → 0.7 strength, 2-octave warp with different noise for warp vs base
- Smoothing: Replace single 3x3 box blur with 3-5 pass gaussian_filter (pure numpy kernel since scipy unavailable in Blender Python)
- Coordinate jittering to break grid alignment
- Add per-octave random offset jittering
- Adaptive octave count based on resolution

**Key Algorithms from Gaea:**
- Multi-pass erosion is THE technique (not single pass)
- Pass 1: 30% duration, altitude bias → macro drainage
- Pass 2: 100% downcutting → deep channels
- Pass 3: Default settings → homogenize
- Pass 4: Thermal → talus and debris
- Pass 5: Fluvial polish (optional)
- Data-driven texturing from heightfield properties, NOT noise-based

**Key Algorithms from World Machine:**
- Flow-based erosion (shallow-water equations, cell-based, NOT particle)
- Geological Time Intensifier (deepen erosion without proportional compute)
- Uplift simulation (raise terrain around rivers to keep rivers in valleys)
- All erosion parameters accept spatial maps for localized control

**Key Algorithms from Open Source:**
- Grid-based Mei et al. (2007) is highest-value: whole-heightmap numpy ops, no per-particle loops
- Numba JIT would give 50-100x speedup (BUT not available in Blender Python)
- Bilateral filtering for anti-jagging (smooth flats, preserve edges)
- dandrino/terrain-erosion-3-ways (MIT license, directly portable)

**Blender API Best Practices:**
- Use bmesh.ops.create_grid + vertex Z displacement (existing VB standard)
- SIMPLE subdivision (not Catmull-Clark) for terrain
- DISSOLVE decimation mode preserves cliff detail
- LAPLACIANSMOOTH modifier for better volume preservation
- foreach_set has strict bounds checking in Blender 4.1+
- vertex_colors deprecated → use color_attributes

**DEPENDENCY BLOCKER:** scipy and Numba are NOT available in Blender's bundled Python. Must use pure numpy implementations for gaussian_filter, bilateral filter, and all erosion.

---

## 2. EROSION ALGORITHMS

**Sources:** terrain_gaea_research.md, terrain_worldmachine_research.md, terrain_opensource_algorithms_research.md, codebase audit

### Grid-Based Hydraulic Erosion (Mei et al. 2007)
Per-cell state: terrain height (b), water height (d), sediment (s), outflow flux (fL,fR,fT,fB)
Steps per iteration:
1. Water increment: d += dt * rain_rate
2. Flow simulation (pipe model): flux based on hydrostatic pressure differentials
3. Water surface update from net flux
4. Velocity field from flux
5. Erosion/deposition: capacity = Kc * |velocity| * sin(slope)
6. Sediment transport via advection
7. Water evaporation

**Fully numpy-vectorizable using np.roll for neighbor access.**

### Multi-Pass Erosion Pipeline (Gaea-style)
```
1. Thermal pre-pass (30 iterations) → natural talus, break ridgelines
2. Hydraulic macro (low detail, high water volume) → major drainage networks
3. Hydraulic detail (high downcutting, low volume) → deep gullies
4. Homogenization pass (light erosion) → blend everything
5. Optional fluvial polish → secondary carved channels
```

### Anti-Jagging Techniques
- 3-5 pass Gaussian blur after noise generation
- Domain warp at 2-3 octaves before main noise
- Per-octave random offset jittering
- Bilateral filter (smooth while preserving edges)
- Conservative smoothing: result = smooth(smooth(hmap))

### Erosion Parameter Fixes
- Hydraulic iterations: 150K → min(500K, resolution^2)
- Thermal iterations: 10 → 30-50
- Domain warp strength: 0.4 → 0.6-0.8
- Per-material angle-of-repose: sand 30-35deg, grass 40-50deg, mud 15-25deg, rock unlimited

---

## 3. TERRAIN MATERIALS & TEXTURING

**Sources:** terrain_materials_shader_research.md, terrain_unity_context7_research.md, terrain_unity_performance_research.md

### Data-Driven Texturing (replaces hardcoded thresholds)
Compute these maps from heightfield:
- **Slope map**: smoothstep transitions (NOT hard 55deg cutoff)
- **Curvature map**: Laplacian filter → concave=moss/dirt, convex=exposed rock/snow
- **Flow map**: water travel paths → staining, algae
- **Wear map**: where erosion removed material → exposed bedrock
- **Deposit map**: where sediment settled → soft soil/sand
- **Altitude map**: height-based zones

### Unity URP Terrain Constraints
- **4 terrain layers per tile** (HARD LIMIT - every 4 extra = another full render pass)
- Terrain textures do NOT support Texture Streaming (always fully resident in VRAM)
- URP terrain shaders are NOT SRP Batcher compatible
- Unity 6.3 added Shader Graph terrain templates (custom terrain materials without HLSL)
- Unity 6 Terrain Quality Overrides: per-preset params without scripting

### Material Blending
- Smoothstep interpolation with 5-10 degree transition zones
- Per-material angle-of-repose replaces universal thresholds
- Height blending already partially in shader_templates.py (extend to Python splatmap gen)
- Triplanar projection for cliff faces (eliminates UV stretching)
- Macro-variation noise to break texture tiling

### Splatmap Transfer (CRITICAL GAP)
Blender computes splatmaps as vertex colors → Unity expects TerrainLayer alphamaps.
**Fix:** Export splatmap as PNG from Blender OR compute alphamaps in Unity from same rules.

---

## 4. PERFORMANCE ARCHITECTURE

**Sources:** terrain_unity_performance_research.md, terrain_unity_context7_research.md, terrain_openworld_streaming_research.md, terrain_vegetation_perf_research.md

### Unity 6 Performance Stack
- **Forward+ rendering path** (required for GPU Resident Drawer)
- **GPU Resident Drawer**: 43,500 → 128 draw calls (99.7% reduction) in 35K foliage scene
- **HLOD**: 83% draw call reduction + 51% triangle reduction for distant objects
- **SRP Batcher**: handles all non-instanced materials
- **GPU Instancing**: vegetation, rocks (intentionally SRP-incompatible shaders)
- **DrawMeshInstancedIndirect**: grass (compute shader path, 10M+ instances)

### Batching Rules (CRITICAL - don't mix)
| Object Type | Batching Method | Static Flag? |
|-------------|----------------|-------------|
| Vegetation (trees, bushes) | GPU Instancing | NO |
| Rocks/boulders | GPU Instancing | NO |
| Grass | DrawMeshInstancedIndirect | NO |
| Buildings | Static Batching | YES |
| Unique props | SRP Batcher | YES |
| Characters/enemies | SRP Batcher | NO |

### 4-Tier Quality System

| Setting | Low (2GB) | Medium (4GB) | High (8GB) | Ultra (16GB) |
|---------|-----------|-------------|-----------|-------------|
| Render scale | 0.5x | 0.75x | 1.0x | 1.0x |
| Shadow distance | 20m | 60m | 120m | 200m |
| Shadow cascades | 1 | 2 | 3 | 4 |
| LOD bias | 0.5 | 1.0 | 1.5 | 2.0 |
| Vegetation density | 0.25x | 0.5x | 0.75x | 1.0x |
| Terrain pixel error | 16 | 8 | 4 | 2 |
| Tree distance | 60m | 120m | 200m | 400m |
| Grass distance | 30m | 60m | 80m | 120m |
| MSAA | Off | 2x | Off (TAA) | Off (TAA) |
| Anti-aliasing | FXAA | MSAA+FXAA | TAA | TAA |
| SSAO | Off | Half-res | Full | Full |
| Volumetric fog | Off | Low | Medium | High |
| Mipmap streaming | 512MB | 768MB | 1024MB | 2048MB |

### Terrain Streaming
- 3x3 additive scene loading (each 1km tile = own scene)
- 1025x1025 heightmap per tile (~4MB, ~36MB for 9 active)
- Low-poly impostor meshes for distant terrain beyond active grid
- Async loading with background thread

### Frame Budget (60fps = 16.67ms)
| Pass | Budget |
|------|--------|
| Shadow | ~2ms |
| Depth prepass | ~1ms |
| Forward lit | ~4ms |
| Transparent | ~1.5ms |
| Post-processing | ~1.5ms |
| CPU game logic | ~4ms |
| Render prep | ~2ms |

---

## 5. MODEL SIZE BUDGETS

**Source:** model_size_budgets_research.md

### Per-Asset Triangle Budgets

| Asset | Low | Medium | High | Ultra | Tripo face_limit |
|-------|-----|--------|------|-------|-----------------|
| Player character | 25K | 40K | 55K | 70K | 50000 |
| Standard mob | 6K | 10K | 15K | 20K | 15000 |
| Elite/mini-boss | 12K | 18K | 25K | 35K | 25000 |
| Boss | 25K | 40K | 55K | 80K | 60000 |
| NPC (townfolk) | 4K | 7K | 10K | 15K | 10000 |
| Building (house) | 3K | 6K | 10K | 15K | 10000 |
| Building (castle/monastery) | 10K | 20K | 35K | 50K | 35000 |
| Castle wall (10m) | 1K | 2K | 3.5K | 5K | 3000 |
| Gate/portcullis | 2K | 4K | 6K | 8K | 6000 |
| Tower | 3K | 6K | 10K | 15K | 10000 |
| Tree (trunk+branches) | 2K | 4K | 6K | 8K | 5000 |
| Rock small (<1m) | 200 | 400 | 600 | 1K | 800 |
| Rock large (>2m) | 500 | 1K | 2K | 3K | 2000 |
| Dead tree/stump | 500 | 1K | 2K | 3K | 2000 |
| Log | 200 | 500 | 800 | 1.2K | 1000 |
| Barrel/crate | 300 | 500 | 1K | 1.5K | 1500 |
| Cart/bench | 500 | 1K | 2K | 3K | 2000 |
| Market stall | 1K | 2K | 3.5K | 5K | 3000 |
| Weapon | 3K | 5K | 7K | 10K | 5000 |
| Shield | 1.5K | 3K | 4K | 6K | 4000 |
| Armor piece | 4K | 7K | 10K | 15K | 10000 |
| Furniture | 500 | 1K | 1.5K | 2.5K | 2000 |
| Door | 300 | 600 | 1K | 1.5K | 1000 |
| Torch sconce | 200 | 400 | 600 | 1K | 800 |
| Lantern post | 400 | 800 | 1.2K | 2K | 1500 |
| Well | 800 | 1.5K | 2.5K | 4K | 3000 |
| Grass blade | 1 | 4 | 6 | 8 | N/A |

### Texture Resolution Per Asset

| Asset | Low | Medium | High | Ultra |
|-------|-----|--------|------|-------|
| Player/boss | 1024 | 2048 | 2048 | 4096 |
| Standard mob | 512 | 1024 | 1024 | 2048 |
| Building exterior | 512 | 1024 | 2048 | 2048 |
| Small prop | 256 | 512 | 512 | 1024 |
| Medium prop | 512 | 512 | 1024 | 1024 |
| Weapon | 512 | 1024 | 1024 | 2048 |
| Terrain layer | 1024 | 1024 | 2048 | 2048 |

### Scene Triangle Budgets

| Tier | Max Visible Tris | Max Draw Calls | Max Instances |
|------|-----------------|----------------|---------------|
| Low | 500K-1M | 200-400 | 5K |
| Medium | 1.5M-2.5M | 500-800 | 15K |
| High | 3M-5M | 1000-1500 | 30K |
| Ultra | 4M-8M | 1500-3000 | 50K+ |

### VRAM Texture Budget

| Tier | Total VRAM | Terrain | Characters | Props | UI/VFX |
|------|-----------|---------|------------|-------|--------|
| Low (2GB) | 600MB | 150MB | 150MB | 200MB | 100MB |
| Medium (4GB) | 1.5GB | 300MB | 400MB | 500MB | 300MB |
| High (8GB) | 3.5GB | 600MB | 800MB | 1.2GB | 900MB |
| Ultra (16GB) | 6GB | 1GB | 1.5GB | 2GB | 1.5GB |

### LOD Chain Specs

| Asset | LOD0 | LOD1 | LOD2 | LOD3 | Billboard? |
|-------|------|------|------|------|-----------|
| Tree | 100% @0-30m | 50% @30-80m | 15% @80-150m | 4 tris @150m+ | YES (cross) |
| Building | 100% @0-50m | 50% @50-120m | 25% @120-250m | - | Optional |
| Rock large | 100% @0-30m | 40% @30-80m | 15% @80-150m | - | NO |
| Small prop | 100% @0-15m | 50% @15-40m | - (cull) | - | NO |
| Character | 100% @0-20m | 50% @20-40m | 25% @40-60m | - (cull) | NEVER |

### Crossfade Settings
- Band width: 10-15% of transition distance
- Fade duration: 0.5s
- Hysteresis: 5% to prevent LOD thrashing

---

## 6. TRIPO ASSET PIPELINE

**Source:** terrain_tripo_optimization_research.md

### Current Pipeline (80% exists)
- Auto-repair (non-manifold, floating verts) ✅
- Decimation (silhouette-preserving) ✅
- Retopology (QuadriFlow) ✅
- UV unwrapping (xatlas) ✅
- LOD chain generation ✅
- PBR texture extraction ✅
- De-lighting ✅

### Missing (20%)
- **Internal face removal** (AI models have 10-30% hidden internal geometry)
- **Normal map baking** (high-to-low-poly)
- **Tripo API face_limit** not used (wastes credits on geometry that gets decimated)
- **Disconnected component cleanup**
- **Batch processing orchestrator** (process 50-100 models)

### Tripo Output Characteristics
- v3.1: 10K-200K tris depending on mode
- Smart Mesh P1.0: already game-ready at 500-5K tris
- Baked-in lighting artifacts requiring de-lighting
- PBR textures at configurable 512-4K resolution

### Batch Processing Estimate
- ~25-90 seconds per model
- 100 models = 40-150 minutes total
- Texture extraction parallelizable; Blender mesh ops sequential

---

## 7. VEGETATION & FOLIAGE

**Sources:** terrain_vegetation_perf_research.md, codebase LOD/scatter audit

### The Leaf Problem
Tripo generates solid mesh leaves = 50K-200K+ triangles per tree. Game-ready tree = 3K-15K tris using alpha-cutout leaf cards.

### Vegetation Strategy

| Asset | Source | Technique | Tris Budget |
|-------|--------|-----------|-------------|
| Tree trunk/branches | Tripo or L-system | Solid mesh | 2K-8K |
| Leaves/canopy | Generated | Alpha-cutout leaf cards | 50-200 |
| Grass | Procedural | Billboard quads + DrawMeshInstancedIndirect | 1-8 per blade |
| Bushes | Tripo base + cards | Solid base + alpha cards | 500-2K |
| Rocks/boulders | Tripo | Solid mesh (perfect candidate) | 200-3K |
| Dead trees/stumps/logs | Tripo | Solid mesh (no leaves) | 500-3K |

### Wind Animation
- Vertex shader with vertex color channels
- R = radial distance from trunk
- G = height (stronger sway at top)
- B = branch level (leaf flutter)
- No skeletal animation needed

### Existing Toolkit Strengths
- L-system tree generation (7 types: oak, pine, birch, willow, dead, ancient, twisted)
- generate_leaf_cards() exists
- generate_billboard_impostor() exists (cross, octahedral)
- LOD vegetation preset (1.0→0.5→0.15→billboard)
- Poisson disk scatter with slope/altitude/density filtering
- Biome-specific vegetation rules (13 biomes)
- Building/road exclusion zones
- GPU instancing export preparation

### Grass System Requirements
- DrawMeshInstancedIndirect (compute shader path)
- 10M+ instances possible
- Render distance: 80-120m max
- Density fade by distance
- Interaction: player pushes grass aside (vertex displacement)

---

## 8. WATER SYSTEMS

**Source:** terrain_water_systems_research.md

### Current State
- carve_river_path() (A* pathfinding) ✅
- handle_create_water() (spline mesh with flow vertex colors) ✅
- generate_waterfall() (step-down cascade) ✅
- generate_swamp_terrain() ✅
- Basic Unity water shader (sine waves + normal maps) ✅

### Missing
- **River meander simulation** (~20 lines to add to erosion loop, momentum-based)
- **Flood-fill lake generation** from terrain depressions
- **Unity water shader upgrades**: depth coloring, foam, caustics, flow maps, Gerstner waves, refraction
- **Shoreline material transitions**: grass → mud → sand → wet sand → water
- **Dark fantasy water presets**: corrupted (purple emissive, slow), swamp (murky green, opaque), cave (dark, still, bioluminescent)

### Water Shader Performance
- Estimated 4 Gerstner waves at ~0.2ms
- Requires Depth Texture + Opaque Texture enabled in URP

---

## 9. LIGHTING & ATMOSPHERE

**Sources:** terrain_lighting_atmosphere_research.md, dark_fantasy_lighting_vfx_deep_dive.md

### Soulsborne Lighting Formula
1. Single dominant directional light
2. Deep shadows (close shadow distance, high darkness)
3. Warm light islands (torches, fires) in cold ambient darkness
4. Colored light = supernatural (corruption = purple/green)
5. Light guides the player (brighter path = correct direction)
6. Corruption actively absorbs light ("negative light sources" - Diablo IV)

### Unity 6 URP Lighting Setup
- **Forward+ rendering** (mandatory for 15-24 lights in Gothic interiors)
- **Adaptive Probe Volumes** for GI (replaces legacy LightProbeGroup)
  - 1m min brick size for settlements, 27m max for open terrain
- **No built-in volumetric lighting** in URP → use Unity-URP-Volumetric-Light (open source)
- **Light cookies** for Gothic window patterns (stained glass light shafts)
- **Light layers** for interior/exterior separation

### Post-Processing (Dark Fantasy)
- ACES tonemapping
- Post exposure: -0.3 to -0.5
- Saturation: -15 to -25
- Blue-shifted shadows (Lift/Gamma/Gain: shadow hue 220)
- Amber highlights (highlight hue 35)
- SSAO: 1.5-2.5 intensity
- Bloom threshold: 0.9 (only bright sources: magic, fire, sun)

### Biome-Specific Lighting Moods
10 biomes each with: ambient color, fog tint, sun tint, corruption modifier

### Per-Light-Source Specifications
| Light Type | Color Temp | Intensity | Range | Flicker |
|-----------|-----------|-----------|-------|---------|
| Candle | 1850K | 0.5 | 3m | Fast, subtle |
| Torch | 2200K | 1.5 | 6m | Medium, irregular |
| Fireplace | 2400K | 2.0 | 8m | Slow, warm |
| Chandelier | 2700K | 3.0 | 12m | None |
| Moonlight | 6500K | 0.3 | Directional | None |
| Corruption | 8000K purple | 1.0 | 5m | Pulsing, slow |

### Particle Budgets
- Fire: 500 max particles
- Corruption: 1000
- Rain: 3000
- Total scene: ~6300 at 60fps

---

## 10. VFX SYSTEMS

**Source:** dark_fantasy_lighting_vfx_deep_dive.md, toolkit_full_gap_analysis.md

### Existing VFX (19 actions)
- Particle systems, shaders, post-processing, flipbooks
- VFX Graph composition, boss transitions
- Corruption shader, dissolve shader, force field, water, foliage
- Outline, damage overlay, hair, terrain blend, ice crystal, SSS skin, parallax eye

### Missing VFX
- **Building weathering shader** (moss growth, moisture darkening, patina)
- **Weapon/armor rune emission** (emissive patterns, damage states)
- **Cloth/fabric shader** (wind animation, subsurface)
- **VFX fire/smoke** (proper flame particles + heat distortion)
- **Height fog renderer feature** (exponential height fog per biome)
- **Decal system** (blood, scorch, corruption stains)

### Corruption/Veil VFX Architecture
- World-space noise dissolve shader with global `_CorruptionRadius` and `_CorruptionOrigin`
- Spreads across ANY surface organically
- Particle overlay: dark motes, purple wisps complement shader
- 4-stage visual: Taint → Spread → Transformation → Consumed

---

## 11. PHYSICS, COLLISION & NAVMESH

**Source:** physics_collision_navmesh_research.md

### NavMesh (CRITICAL GAP)
- Unity 6 uses component-based NavMeshSurface (AI Navigation 2.0)
- Legacy Navigation window Bake button is removed
- One NavMeshSurface per terrain tile, pre-baked
- Adjacent tiles auto-stitch edges
- Walkable slope: 45deg default, adjust per biome
- Mark water/cliff/void as non-walkable
- NavMeshLink for gaps/jumps/ladders

### Collision Strategy
- **Compound primitive colliders** for buildings (6-12 BoxColliders each)
- **Non-convex MeshColliders** only on static geometry
- **V-HACD/CoACD** for automatic convex decomposition of complex shapes
- **NEVER** use high-poly Tripo mesh directly as collider

### Physics Budget
- 200-300 active dynamic Rigidbodies at 60fps
- Kinematic bodies 30-40% cheaper than dynamic
- Max 2-3 simultaneous ragdolls, auto-disable after 3-5 seconds
- Physics LOD: disable simulation on distant objects (manual implementation)

### Camera System
- Cinemachine 3.x Third Person Follow has built-in collision resolution
- No custom camera-terrain collision needed

### Save/Load
- Atomic write pattern: temp file → verify → backup → rename
- JSON for dev, binary for release
- ~15-50KB per save file
- Steam Cloud from Application.persistentDataPath
- **35 known save bugs must be fixed first**

---

## 12. SHADER & RENDERING PIPELINE

**Source:** shader_rendering_pipeline_research.md

### Existing Shaders (12)
corruption, dissolve, force field, water, foliage, outline, damage overlay, hair, terrain blend, ice crystal, SSS skin, parallax eye

### Shaders Needing Upgrade
- **Water**: no Gerstner/depth/caustics
- **Corruption**: no world-space Veil dissolve
- **Vegetation**: no GPU instancing compatibility
- **Terrain**: no triplanar for cliffs

### Missing Shaders (6)
1. Building weathering (moss, moisture, patina)
2. Weapon/armor rune emission
3. Cloth/fabric
4. VFX fire/smoke
5. Height fog renderer feature
6. Decal system

### Critical Rendering Rules
- **SRP Batcher compatibility mandatory** - all properties in single CBUFFER_START(UnityPerMaterial). Breaking = 10x draw call overhead silently.
- **MSAA and TAA mutually exclusive** in URP
- **PSO Tracing** for shader warmup in Unity 6 (legacy WarmUp broken on DX12/Vulkan)

### Texture Compression
- BC7: albedo, metallic (PC)
- BC5: normal maps
- BC6H: HDR, lightmaps
- BC4: roughness, AO, masks
- ASTC: mobile fallback

---

## 13. ASSET PIPELINE & BUILD

**Source:** asset_pipeline_build_research.md

### Export Format
- **GLB primary** for static PBR assets (metallic-roughness → URP Lit directly)
- **FBX** for animated/rigged characters (Mecanim support)
- **glTFast 6.8.0** recommended Unity package for GLB import

### 14 Pipeline Gaps Identified
Top 4 critical:
1. No automated Blender export → Unity Assets folder transfer
2. No GLB import configuration tool (only FBX handled)
3. No LODGroup auto-setup despite LOD chains in Blender
4. No automated prefab creation from imported models

### Build Optimization
- IL2CPP for release builds
- Shader variant stripping
- Managed code stripping
- Addressable asset bundles per zone
- Target install size: 8-15GB

---

## 14. DARK FANTASY RPG DESIGN

**Source:** dark_fantasy_rpg_best_practices.md

### Player Attraction Pillars
1. Atmosphere and environmental storytelling (items/corpses tell stories)
2. Sense of discovery and exploration reward
3. World that feels lived-in and ancient
4. Danger around every corner
5. Verticality and hidden paths
6. Memorable landmarks visible from far away
7. Earning progress through skill, not grinding

### Architecture Scale
- Standard buildings: 1.25-1.5x real-world proportions
- Religious/ancient: 2.0-3.0x real scale
- Doors: 1.25m × 2.5m minimum
- Wall height: 3.0m per floor
- Hallway width: 2.0m minimum

### Starter Town Design (Firelink Shrine Model)
- Intimate central hub with dangerous routes radiating outward
- Shortcuts that loop back (spatial "aha" moments)
- Hybrid safe-haven/town-under-threat as Veil encroaches
- 7 critical emotional moments to design in

### 4-Stage Veil Corruption Progression
1. **Taint**: Subtle color shift, wilted plants, uneasy atmosphere
2. **Spread**: Visible corruption tendrils, damaged structures, hostile wildlife
3. **Transformation**: Architecture distorts (Bloodborne Mannerist influence), alien geometry
4. **Consumed**: Full corruption, unreality, boss-arena-level threat

---

## 15. THE VEIL MECHANIC

**Source:** veilbreakers_game_gaps_research.md

### Current State: DOES NOT EXIST
The game's namesake mechanic has zero implementation:
- No dual-world shader
- No lantern/reveal tool
- No world-variant generation
- No corruption intensity map
- No Veil boundary effects

### Blueprint: Lords of the Fallen Axiom/Umbral
- Shader-based visibility layers (two world states in same geometry)
- Screen-space mask for lantern peek (see the other world through a lens)
- Escalating threat tied to time in veiled world
- Different enemies/loot in each world state

### Implementation Requirements
- Corruption intensity map (0-1) per terrain vertex
- Additional splatmap channel for corruption material
- Vertex displacement in corruption zones
- Veil boundary VFX trigger volumes
- Dynamic corruption expansion at runtime
- Negative light sources in corrupted areas
- World-space dissolve shader with _CorruptionRadius

---

## 16. TOOLKIT GAP ANALYSIS

**Source:** toolkit_full_gap_analysis.md

### 67 Gaps Total

**CRITICAL (8):**
1. No automated Blender-to-Unity round-trip
2. No end-to-end character pipeline
3. No scene composition tool (Blender worldbuilding → Unity scene)
4. No multiplayer networking
5. No cross-tool state persistence
6. scipy/Numba dependency blocker
7. Splatmap transfer Blender→Unity
8. Terrain streaming Unity-side consumer

**HIGH (19):** Including:
- No Shader Graph templates
- No facial animation/lipsync
- No VFX Graph asset generation
- Behavior tree nodes are stubs
- No trigger volumes
- No Blender/Unity bridge auto-install

**Strengths:**
- Modeling: 32 sculpt brushes, booleans, retopology, 175 modular pieces, AAA generators
- Audio: 20 actions (AI generation, spatial, dynamic music, portal propagation, foley)
- Worldbuilding: Dungeons, caves, towns, castles, boss arenas, world graphs
- VFX: 19 actions (particles, shaders, post-processing, VFX Graph)
- Rigging: 13 actions (8 creature templates, IK, spring bones, ragdoll, facial)

**#1 Fix:** Scene composition tool bridging Blender worldbuilding output to configured Unity scene

---

## 17. CODEBASE BUGS

**Source:** codebase_bug_scan.md

### Test Suite: 19,348 passed, 1 skipped

### CRASH Bugs (3)
1. **BUG-01**: `blender_server.py:2558` - TripoStudioClient called with `jwt_token=` but constructor expects `session_token=` → TypeError
2. **BUG-02**: `blender_server.py:2556` - TripoStudioClient not imported in `generate_prop` action → NameError
3. **BUG-03**: `blender_server.py:2681,2708,3122` - pipeline_state import triggers `import bpy` outside Blender → ModuleNotFoundError. **Completely breaks compose_map and generate_map_package.**

### LOGIC Bugs (2)
4. **BUG-04**: `interior_results` reset to `[]` when resuming from checkpoint → loses previous interior data
5. **BUG-10**: Prop scatter throws ValueError when compose_map has no locations (terrain-only maps)

---

## 18. UI/UX & PLAYER SYSTEMS

**Source:** ui_ux_player_systems_research.md

### Current State
- 28+ template generators exist (HUD, menus, accessibility, analytics, etc.)
- Gap is NOT missing generators - it's wiring into cohesive experience

### Accessibility (Partially Implemented)
- Colorblind simulation ✅ (3 LMS matrices)
- Subtitle scaling ✅
- Screen reader toggle ✅
- Motor accessibility ✅
- Missing: subtitle background, high-contrast mode, assist modes, FOV slider, UI scale

### Platform Integration
- Steam Cloud: requires save system fix first (35 bugs)
- Discord: Game SDK deprecated → use Social SDK (2024-2025)
- Unity Cloud Diagnostics: deprecated → use built-in (6.2+)

### Content Volume Needed (20-40h ARPG)
- ~50 enemy types
- ~60 weapons
- ~25 armor sets
- 5 biomes
- 10 bosses
- Unknown voice acting volume

---

## 19. CRITICAL BLOCKERS SUMMARY

### Must Fix Before Implementation (Priority Order)

| # | Blocker | Impact | Fix |
|---|---------|--------|-----|
| 1 | scipy/Numba not in Blender Python | All erosion improvements dead | Pure numpy Gaussian kernel + vectorized ops |
| 2 | Splatmap never transfers Blender→Unity | All material work thrown away | Export as PNG or compute in Unity |
| 3 | Chunk boundary stitching metadata-only | Visible terrain seams | Shared-edge constraint + skirt meshes |
| 4 | LOD meshes don't map to Unity LODGroups | All assets single-LOD | Define export format + Unity setup script |
| 5 | Terrain streaming no Unity consumer | Can't load/unload tiles | Build TerrainStreamingManager |
| 6 | No NavMesh generation | Zero AI pathfinding | Add NavMesh bake step |
| 7 | Veil mechanic doesn't exist | Core game identity missing | Design corruption intensity system |
| 8 | No end-to-end pipeline test | Silent breakage | Full chain integration test |
| 9 | 3 crash bugs in blender_server.py | Pipeline broken | Fix BUG-01, BUG-02, BUG-03 |
| 10 | No scene composition tool | Manual Blender→Unity handoff | Build world→scene bridge |
| 11 | SRP Batcher silent breakage | 10x draw call overhead | Validate every custom shader |
| 12 | 35 save system bugs | Data loss | Fix before any platform integration |

### Must Fix During Implementation

| # | Gap | Category |
|---|-----|----------|
| 13 | Roads don't deform terrain | Integration |
| 14 | Buildings don't terrace terrain | Integration |
| 15 | Vegetation grows through buildings | Integration |
| 16 | No collision mesh for buildings | Physics |
| 17 | Water not integrated with terrain | Integration |
| 18 | No audio zones/reverb | Audio |
| 19 | No occlusion culling data | Performance |
| 20 | 6 missing shaders | Rendering |
| 21 | Boss arenas lack terrain sculpting | Gameplay |
| 22 | No interaction/loot point placement | Gameplay |
| 23 | Building weathering shader | Visual |
| 24 | LOD pop-in on vegetation | Visual |
| 25 | Terrain-to-building ground seam | Visual |

---

## 20. STYLE REFERENCE

**Source:** User-provided concept art (3 reference sheets)

### Architecture Style: Late Medieval Gothic
- Pointed arches, rose windows, flying buttresses
- Crenellated battlements with machicolations
- Stone-timber hybrid construction
- Arrow slits, portcullis mechanisms, drawbridge pivots

### Material Palette
- Mossy Stone Blocks (primary walls)
- Aged Shingle Pattern (dark slate roofs)
- Patinaed Iron Plate (hardware, gates)
- Worn Timber Planks (structural beams, doors)
- Weathered Masonry (varied block sizes)
- Leaded Glass Windowpanes (warm amber interior glow)

### Weathering Rules
- Heavy moss on north-facing walls and roof edges
- Stone darkening at base from ground moisture
- Iron rust patina on all metal
- Timber grain exposure from weather
- NOTHING is pristine - everything shows age

### Color Palette
- Extremely desaturated earth tones
- Dark olive greens (moss), cold stone greys, warm timber browns
- Near-black roof slate
- Saturation <40%, value 10-50%

### Modular Tripo Targets
- Castle: walls (straight/corner/T), towers, portcullis gatehouse, buttresses, drawbridge
- Religious: monastery/chapel with rose window, Gothic arches
- Residential: 2-story stone-timber buildings
- Dungeon: stone corridors, arch doorways, iron gates, torch sconces

---

## RESEARCH FILE INDEX

### Terrain (13 files)
1. terrain_gaea_research.md (26KB)
2. terrain_worldmachine_research.md (36KB)
3. terrain_blender_tools_research.md (35KB)
4. terrain_opensource_algorithms_research.md (38KB)
5. terrain_blender_api_context7_research.md (34KB)
6. terrain_unity_context7_research.md (27KB)
7. terrain_unity_performance_research.md (32KB)
8. terrain_vegetation_perf_research.md (34KB)
9. terrain_tripo_optimization_research.md (35KB)
10. terrain_openworld_streaming_research.md (33KB)
11. terrain_materials_shader_research.md (31KB)
12. terrain_water_systems_research.md (37KB)
13. terrain_lighting_atmosphere_research.md (34KB)

### Gap Analysis (2 files)
14. terrain_gap_analysis.md (31KB) - 40 gaps, 8 critical
15. toolkit_full_gap_analysis.md (40KB) - 67 gaps

### Game Design (3 files)
16. dark_fantasy_rpg_best_practices.md (38KB)
17. dark_fantasy_lighting_vfx_deep_dive.md (50KB)
18. veilbreakers_game_gaps_research.md (24KB)

### Systems (5 files)
19. codebase_bug_scan.md (10KB)
20. model_size_budgets_research.md
21. physics_collision_navmesh_research.md
22. shader_rendering_pipeline_research.md
23. asset_pipeline_build_research.md

### UI/UX (1 file)
24. ui_ux_player_systems_research.md

### Legacy Research (29 files from earlier milestones)
25-53. AAA_BEST_PRACTICES_COMPREHENSIVE.md, WORLD_DESIGN.md, VFX_SKILL_EFFECTS_REFERENCE.md, etc.

---

*Total research investment: 27 dedicated research agents, 53 research documents, ~1.7MB of findings, 107+ gaps identified and prioritized.*
