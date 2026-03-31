# Technology Stack: AAA Procedural 3D Architecture

**Project:** VeilBreakers v4.0 -- AAA Procedural 3D Architecture
**Researched:** 2026-03-30
**Overall Confidence:** HIGH (cross-verified across official docs, AAA studio references, existing research files)

## Context

This stack covers the AAA procedural 3D generation pipeline for v4.0: procedural buildings, interior mapping/furnishing, terrain/building mesh integration, biome-aware generation, high-level geometry with clean edges, and AAA-quality texturing. It builds on the existing MCP toolkit (37 compound tools, 127 procedural mesh generators) and the established Blender-to-Unity pipeline.

The existing STACK.md covers MCP server infrastructure (Python SDK, transports, HTTP clients). This document covers the procedural 3D architecture dimension specifically.

---

## Recommended Stack

### Core Procedural Engine

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Blender Geometry Nodes | 5.1 | Declarative procedural geometry, node-based systems | Geometry Nodes 5.1 introduces Repeat Zones, For Each Geometry Element zones, Closures, Bake nodes, and new Generate nodes (Array, Scatter on Surface, Curve to Tube). These enable complex procedural buildings, facade generation, and scatter systems without Python scripting. The Bake node enables caching expensive computations. Array node replaces manual duplication. Scatter on Surface replaces custom Poisson disk for many cases. | HIGH |
| Blender Python (bpy) | 4.x/5.x | Imperative procedural generators, bridge handlers, mesh manipulation | The existing 127+ generators use bpy/bmesh/mathutils directly. bpy is required for operations Geometry Nodes cannot express: custom topology construction, vertex group creation, UV manipulation beyond basic unwrapping, armature/rig generation, and the TCP socket bridge handlers. bpy and Geometry Nodes complement each other -- bpy for precise control, Geo Nodes for declarative patterns. | HIGH |
| bmesh | 4.x/5.x | Low-level mesh construction, topology operations | bmesh provides BMesh API for direct vertex/edge/face manipulation. Used for boolean operations, hole filling, edge loop creation, and custom topology generation that the higher-level bpy ops cannot achieve. Critical for procedural building construction where every vertex position matters. | HIGH |
| mathutils | 4.x/5.x | Vector/matrix math, noise, interpolation | Vector, Matrix, Quaternion, Euler, Color, kdtree, noise modules. Used for all spatial calculations in procedural generators. noise.fractal, noise.voronoi, noise.cell provide deterministic procedural variation from seeds. | HIGH |

### AI 3D Generation APIs

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Tripo3D v3.0 | v3.0 API | Primary AI 3D generator (characters, monsters, props) | Already integrated. v3.0 upgrade brings quad mesh mode, 2M polygon output, improved PBR materials, style transforms, auto-rigging. Best topology of commercial APIs. Cost: ~$0.10-0.25/model. Use for: characters, enemies, weapons, armor, key props. | HIGH |
| Hunyuan3D 2.1 | 2.1 | Self-hosted secondary generator (bulk props, environment) | Open-source (Tencent), zero marginal cost per generation, 8K PBR textures (highest resolution), 6GB VRAM minimum, PolyGen quad topology mode. Use for: bulk furniture, environmental objects, vegetation props, rock formations. Eliminates per-model API cost for bulk assets. | HIGH |
| Rodin Gen-2 (Hyper3D) | Gen-2 | Hero/boss asset generation (maximum quality) | 10B parameter model, native quad mesh mode (up to 200K quad faces), best overall quality. Cost: $0.30-1.50/model via WaveSpeedAI/fal.ai. Reserve for: hero characters, boss creatures, legendary weapons, key architectural focal points. NOT for bulk generation. | HIGH |
| fal.ai FLUX | latest | Concept art, reference images, texture source material | Already integrated via `concept_art generate`. FLUX provides high-quality concept art for directing 3D generation and texture creation. Use for: building reference sheets, material reference, texture source images for inpainting. | HIGH |

### Interior / Room Generation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| World Labs Marble | current | Hero interior room generation (cloud SaaS) | Only available-now tool that generates full 3D rooms with walls/floors/ceilings/furniture as exportable GLB mesh (~600K tris). "Chisel" editor for wall/room layout. Cloud-based (no local GPU). Exports to GLB for Blender import pipeline. Use for: tavern halls, throne rooms, boss chambers, key interior locations. | MEDIUM |
| compose_interior (existing) | v4.0 | Bulk interior pipeline (procedural room shells + Tripo furniture) | Existing `asset_pipeline compose_interior` action chains: linked room shells -> door triggers -> occlusion zones -> per-room geometry -> storytelling props -> Tripo prop queue. Supports 9 room types. Use for: bulk interior generation, dungeon rooms, generic buildings, procedural dungeons. | HIGH |
| Tripo Studio (subscription) | current | Small/medium furniture and prop generation | User has active Tripo subscription with Studio access. Generate furniture pieces, decorative props, clutter items via the Tripo Studio web interface, then import via `asset_pipeline import_model`. Use for: chairs, tables, barrels, crates, shelves, candlesticks, chandeliers. | HIGH |

### Texture Pipeline

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Blender Shader Nodes | 4.x/5.x | Procedural texture generation, material authoring | Full procedural material system: Noise Texture, Voronoi, Musgrave, Wave, Brick, Checker for pattern generation. ColorRamp, MixRGB, Math for combination. Baking to image textures for Unity export. Use for: PBR material creation, trim sheet generation, smart materials, macro variation maps. | HIGH |
| xatlas (via blender_uv) | current | UV unwrapping for procedural meshes | Automatic UV unwrapping with chart packing. Already integrated via `blender_uv unwrap`. Produces clean UV layouts suitable for PBR texturing. Use for: all procedural meshes that need texture application. | HIGH |
| Real-ESRGAN (via blender_texture) | current | Texture upscaling (AI super-resolution) | Already integrated via `blender_texture upscale`. Upscales textures 2x-4x with AI. Use for: upscaling AI-generated textures, enhancing procedural textures, increasing resolution of baked textures. | HIGH |
| fal.ai inpainting | latest | Texture inpainting, seam healing, region replacement | Already integrated via `blender_texture inpaint`. fal.ai FLUX-based inpainting for repairing texture seams, extending textures, replacing regions. Use for: healing UV seam artifacts, extending tiled textures, removing baked-in lighting. | HIGH |
| Scenario.gg | current | AI PBR texture generation (full channel sets) | REST API generates complete PBR sets: albedo, normal, roughness, metallic, height, AO. Custom model training from 10-50 reference images for style consistency. Seamless/tileable output. Use for: generating dark fantasy material sets (stone, wood, metal, leather) with consistent art style. | MEDIUM |

### Mesh Processing & Optimization

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| trimesh | 4.11.x | Mesh validation, format conversion, analysis | Already in stack. Loads/exports OBJ, GLB, STL, PLY, FBX (via assimp). Polygon count analysis, mesh repair, simplification. Use for: validating AI-generated meshes, checking poly budgets, format conversion between Blender and Unity. | HIGH |
| pymeshlab | 2025.07 | Advanced remeshing, decimation, surface reconstruction | Wraps full MeshLab engine. Quadric Edge Collapse decimation (better quality than trimesh), isotropic remeshing, Poisson surface reconstruction, texture parameterization. Use for: retopology of AI-generated meshes, LOD chain generation, high-quality decimation. | MEDIUM |
| Quadriflow (Blender built-in) | built-in | Auto-retopology to quad mesh | `bpy.ops.mesh.quadriflow_remesh()` -- Blender's built-in auto-retopology. Produces quad-dominant topology with configurable target face count. Use for: retopology of AI-generated meshes to game-ready topology, creating clean base meshes for sculpting. | HIGH |
| pygltflib | 1.16.x | Direct glTF/GLB manipulation, PBR material editing | Low-level glTF control: edit PBR material properties, swap textures, read/write extensions. Use for: post-processing AI-generated GLB files before Blender import, embedding PBR textures, fixing glTF metadata. | MEDIUM |

### Terrain & World Building

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| OpenSimplex noise | Python lib | Deterministic terrain generation, biome variation | Already used in toolkit. Provides 2D/3D/4D simplex noise for terrain heightmaps, biome distribution, density maps. Superior to Perlin noise (no directional artifacts). Seed-based for reproducibility. Use for: terrain heightmaps, biome noise, macro variation maps. | HIGH |
| Hydraulic/thermal erosion | custom (existing) | Terrain erosion simulation | Existing `_terrain_erosion.py` implements hydraulic + thermal erosion. Produces realistic terrain features (ridges, valleys, sediment deposits). Use for: all terrain generation, post-processing procedural heightmaps. | HIGH |
| WFC (Wave Function Collapse) | Python implementation | Procedural dungeon layout, tile-based level design | Algorithm for constraint-based procedural generation. Define tile set with adjacency constraints, collapse from lowest entropy. Use for: dungeon room layouts, city street networks, building interior layouts. 20-40 unique tiles for convincing variety. Already exposed via `unity_world create_wfc_dungeon`. | MEDIUM |
| L-Systems | custom (existing) | Road networks, branching structures, vegetation | Already used in `vegetation_tree` generator. L-System grammar rules generate branching road networks (main roads branch at 30-90 degrees, width decreases with depth), tree structures, river tributaries. Use for: town road networks, vegetation branching, decorative elements. | HIGH |

### LOD & Performance

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| LOD chain generation (existing) | v4.0 | Automated LOD level creation | `asset_pipeline generate_lods` creates LOD chain from ratios (e.g., [1.0, 0.5, 0.25, 0.1]). Use for: all environment meshes, buildings, props, vegetation. Bethesda-style 3-type LOD (terrain, object, tree) for large world rendering. | HIGH |
| Occlusion culling | Unity built-in | Runtime visibility optimization | Unity URP occlusion culling via baked occlusion data. `unity_world setup_occlusion` configures. Use for: interior rooms (prevent rendering unseen rooms), dense city areas, dungeon corridors. Critical for interior/dungeon performance. | HIGH |
| GPU instancing | Unity built-in | Efficient rendering of repeated meshes | Unity `Graphics.DrawMeshInstanced()` or terrain detail system. All instances of same mesh+material rendered in single draw call. Use for: vegetation, props, building modular pieces, furniture. MaterialPropertyBlock for per-instance variation. | HIGH |
| Addressables | Unity package | Asset streaming, memory management | `unity_build configure_addressables` sets up Unity Addressables for asset bundling and streaming. Use for: interior streaming (load rooms on demand), large world chunking, texture streaming. Enables seamless interior/exterior transitions without loading screens. | HIGH |

### Unity-Side Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| URP (Universal Render Pipeline) | 2022.3+ | Rendering pipeline for dark fantasy visuals | Project constraint (Unity 2022.3+, URP). Use Forward+ rendering for many point/spot lights (torches, braziers, magic effects). Configure: 4 shadow cascades, 2048 shadow resolution, 80-120m shadow distance, SRP Batcher enabled. | HIGH |
| UI Toolkit | 2022.3+ | Runtime UI framework | Project constraint. Use for: minimap, damage numbers, HUD, inventory UI, loading screens. | HIGH |
| Cinemachine | 3.x | Camera system, cutscenes, lock-on targeting | `unity_camera` tools already integrated. Cinemachine 3.x for: state-driven cameras, lock-on targeting (Souls-like), cinematic sequences, camera shake. | HIGH |
| NavMesh | Unity built-in | AI pathfinding, navigation | `unity_scene bake_navmesh` for runtime pathfinding. Use for: enemy AI navigation in procedural interiors, NPC pathing in towns, boss arena navigation. | HIGH |

---

## Architecture: How the Stack Fits Together

```
GENERATION LAYER
================================================================
|                                                                |
|  Blender bpy/bmesh          Geometry Nodes 5.1                 |
|  (imperative generators)    (declarative systems)              |
|  - Buildings, interiors     - Facade scattering                |
|  - Terrain, biomes          - Detail instancing                |
|  - Mesh repair/retopo       - Trim sheet UV mapping            |
|  - UV/texturing             - Procedural materials             |
|                                                                |
|  AI Generation APIs                                            |
|  - Tripo v3.0 (primary, all asset types)                       |
|  - Hunyuan3D 2.1 (self-hosted, bulk props/env)                |
|  - Rodin Gen-2 (hero/boss assets)                              |
|  - World Labs Marble (hero interior rooms)                     |
|                                                                |
OPTIMIZATION LAYER
================================================================
|                                                                |
|  Mesh Processing        LOD Generation        UV/Texture       |
|  - trimesh (validate)   - LOD chains          - xatlas unwrap  |
|  - pymeshlab (remesh)   - Quadric decimation  - PBR baking     |
|  - Quadriflow (retopo)  - Billboards          - Real-ESRGAN    |
|                                                                |
EXPORT LAYER
================================================================
|                                                                |
|  Blender Export (FBX/GLB) -> Unity Import                      |
|  - game_check validation                                       |
|  - poly budget enforcement                                     |
|                                                                |
RUNTIME LAYER (Unity)
================================================================
|                                                                |
|  URP Forward+   Addressables    NavMesh     Cinemachine 3.x   |
|  Occlusion      GPU Instancing  LOD Groups  Interior Streaming |
|                                                                |
```

---

## Triangle Budget Standards (AAA Reference)

Enforce these budgets via `blender_mesh game_check` before any export.

| Asset Category | LOD0 Tris | LOD1 | LOD2 | LOD3/Cull | Notes |
|---|---|---|---|---|---|
| Hero Character | 40K-60K | 20K-30K | 8K-15K | 2K-5K | Player + equipped gear total |
| Boss Monster | 30K-80K | 15K-40K | 5K-15K | 2K-5K | Phase-specific meshes multiply |
| Common Enemy | 15K-35K | 7K-20K | 3K-8K | 1K-2K | Budget for 10+ on screen |
| Building (modular piece) | 2K-8K | 1K-4K | 500-2K | Cull | Per module, not whole building |
| Interior Room Shell | 4K-12K | 2K-6K | 1K-3K | Cull | Walls + floor + ceiling |
| Furniture Prop | 500-3K | 200-1.5K | 100-500 | Cull | Tables, chairs, shelves |
| Tree (full mesh) | 3K-8K | 1K-3K | 200-500 (cards) | 2 (billboard) | LOD2 = intersecting planes |
| Weapon | 1K-4K | 500-2K | 200-1K | Cull | Higher for hero weapons |
| Rock/Clutter | 200-1K | 100-500 | Cull | Cull | Instanced heavily |
| **Scene Total @ 60fps** | **2M-6M** | | | | PC target |

---

## Procedural Building Workflow (Recommended)

### Modular Kit Approach (Bethesda/FromSoftware Pattern)

The standard AAA approach uses modular kit pieces, not monolithic buildings:

1. **Create kit pieces** (25-40 per architectural style): wall_straight_1m, wall_corner, floor_1x1, ceiling_1x1, pillar, arch, stairs, door_frame, window_frame, trim pieces, damaged variants. Grid: 1m primary, 0.5m secondary.

2. **Author trim sheets** (1-2 per kit): 2048x2048 or 4096x4096 texture atlas with horizontal strips for moldings, stone courses, brick patterns, wood planks. All kit pieces UV-mapped to the shared trim sheet. Single material = single draw call per building.

3. **Compose buildings** from kit pieces: place wall modules at grid positions, snap corners, add doors/windows, stack floors. Rules ensure structural coherence.

4. **Add variation**: damaged variants, different material swaps (stone/wood/brick), vertex color blending (moss/dirt/damage overlays), storytelling props.

### Geometry Nodes for Composition

Geometry Nodes 5.1 nodes for procedural building assembly:

| Node | Building Use |
|------|-------------|
| **Array** | Repeat wall/floor modules along axes |
| **Extrude Mesh** | Create wall thickness from floor plan curves |
| **Mesh Boolean** | Cut door/window openings in wall panels |
| **Instance on Points** | Place window/door props along facade |
| **Scatter on Surface** | Scatter damage, moss, debris on surfaces |
| **Repeat Zone** | Iterate floors, windows, decorative elements |
| **For Each Element** | Apply per-piece variation (scale, rotation, damage) |
| **Subdivision Surface** | Smooth architectural curves (arches, domes) |
| **UV Unwrap + Pack UV Islands** | Automated UV mapping for trim sheets |
| **Bake** | Cache expensive procedural computations |
| **Curve to Tube** | Generate pillars, columns, railings from curves |
| **Closure + Evaluate Closure** | Reusable building component generators |

### Python bpy for Custom Topology

Use bpy/bmesh for operations Geometry Nodes cannot handle:

- Custom vertex group creation for rigging
- Vertex color painting for material blending masks
- Edge loop construction for clean topology
- Face set creation for sculpt masking
- Shape key creation for building damage states
- Vertex weight painting for terrain blending

---

## Texture Pipeline (Recommended)

### Procedural Material Workflow

```
1. DEFINE: Blender Shader Nodes (procedural pattern + PBR channels)
   - Noise/Voronoi/Brick/Wave for base patterns
   - ColorRamp for color mapping
   - Separate XYZ + Math for height-based effects
   - MixRGB for combining layers

2. BAKE: blender_texture bake (COMBINED/NORMAL/AO/ROUGHNESS/METALLIC)
   - Bake each PBR channel to 2048x2048 or 4096x4096 image
   - Use Cycles for baking (more accurate than Eevee)

3. VALIDATE: blender_texture validate_palette (dark fantasy palette rules)
   - Check albedo against dark fantasy color constraints
   - Validate PBR channel ranges (roughness 0.3-0.95, metallic 0 or 1)

4. PROCESS: Optional post-processing
   - Real-ESRGAN upscale if resolution insufficient
   - Inpainting for seam healing
   - make_tileable for repeating textures
   - delight for removing baked-in lighting

5. EXPORT: Apply to Unity material
   - unity_settings configure for texture import settings
   - unity_shader create_shader for custom URP shaders
```

### Terrain Splatmap Strategy

4-channel splatmap with height-based blending (NOT linear interpolation):

| Channel | Material | Slope Range | Height Range |
|---------|----------|-------------|--------------|
| R | Ground cover (grass/dirt) | 0-25 degrees | Valley to mid |
| G | Dirt/mud/paths | 15-40 degrees | Low areas |
| B | Rock/cliff | 30-90 degrees | Mid to peak |
| A | Biome-specific (snow/moss/sand) | Varies | Varies |

Height-blend algorithm (per-pixel):
```
for each pixel:
    adjusted[i] = weight[i] * heightmap[i]
    max_h = max(adjusted)
    threshold = max_h - blend_depth
    output[i] = max(0, adjusted[i] - threshold)
    normalize(output)
```

### Macro Variation Maps

Anti-tiling technique: 256-512px low-frequency noise map covering entire terrain. Modulates color tint, roughness offset, and brightness. Generated via:
```
Noise Texture (scale 0.02, detail 4, roughness 0.5)
-> ColorRamp (3 stops: 0.85/1.0/0.9)
-> multiply with base terrain color
```

### Trim Sheet Standard

Per architectural kit, one 2048x2048 or 4096x4096 trim sheet:

| Strip | Content | Height |
|-------|---------|--------|
| 0 | Crown molding | 64px |
| 1 | Large stone course | 128px |
| 2 | Small stone course | 128px |
| 3 | Brick pattern | 256px |
| 4 | Wood planks | 128px |
| 5 | Window/door frame | 256px |
| 6 | Foundation stone | 128px |
| 7 | Roof tiles | 256px |

All kit pieces UV-mapped to appropriate strips. Single shared material per kit.

---

## LOD Strategy (AAA Reference)

### 3-Type LOD (Bethesda Pattern)

| LOD Type | What | Technique | Update |
|----------|------|-----------|--------|
| **Terrain LOD** | Heightmap terrain | Quadtree LOD, reduce resolution with distance | Continuous |
| **Object LOD** | Buildings, props, rocks | Mesh LOD chain (4 levels), impostor at max distance | On threshold |
| **Tree LOD** | Vegetation | Full mesh -> cards -> billboard | On threshold |

### LOD Chain Per Asset Type

**Buildings (modular pieces):**
- LOD0 (>15% screen): Full detail, all geometry, 2K-8K tris
- LOD1 (8-15%): Simplified, merged detail, 1K-4K tris
- LOD2 (3-8%): Low-poly shell, 500-2K tris
- LOD3 (<3%): Billboard impostor

**Vegetation:**
- LOD0 (>15%): Full 3D mesh, 3K-8K tris
- LOD1 (8-15%): Simplified mesh, 1K-3K tris
- LOD2 (3-8%): Card-based (6-12 intersecting planes), 100-500 tris
- LOD3 (<3%): Single billboard quad, 2 tris

**Interior Streaming (not LOD):**
- Interior rooms loaded/unloaded via Addressables
- Occlusion culling prevents rendering unseen rooms
- Door triggers initiate load/unload
- Load adjacent rooms, unload distant rooms

---

## Biome System

### Biome Mapping

Use OpenSimplex noise with seed-based deterministic distribution:

| Biome | Height Range | Noise Threshold | Primary Materials |
|-------|-------------|-----------------|-------------------|
| Deep Forest | Low-mid | <0.3 | Dark wood, moss, ferns |
| Dark Plains | Low | 0.3-0.5 | Dead grass, mud, scattered ruins |
| Volcanic | Mid | 0.5-0.65 | Basalt, lava rock, ash |
| Corrupted | Any | 0.65-0.8 | Purple-black crystal, decay, void |
| Mountain | High | >0.8 | Snow, ice, bare rock |

### Corruption-Aware Distribution

Corruption zones overlay biome system:
- Corruption level 0-100% affects material choices, prop placement, vegetation density
- 0-30%: Subtle corruption (discolored plants, occasional crystal growth)
- 30-60%: Moderate corruption (dead vegetation, void fissures, corrupted enemies)
- 60-100%: Heavy corruption (crystal terrain, void tears, no natural vegetation, boss-level enemies)

### Transition Rules

- Transition zone width: 20-50 meters
- Blend: smoothstep based on distance from biome boundary
- Layer order: ground texture first, then vegetation, then skybox/fog
- Scatter transition props: dead trees at forest-desert boundary, frost crystals at volcanic-corrupt boundary

---

## Performance Targets

| Metric | Target | Technique |
|---------|--------|-----------|
| Frame time | 16.67ms (60fps) | Budget: 2M-6M scene tris total |
| Draw calls | <2000 | SRP Batcher + GPU instancing + shared materials |
| VRAM (textures) | <2GB | Texture streaming, Addressables, LOD-appropriate resolution |
| VRAM (meshes) | <1GB | LOD chains, occlusion culling, interior streaming |
| Set pass calls | <500 | Shared materials per kit, MaterialPropertyBlock for variation |
| Batch count | <1000 | SRP Batcher groups by shader variant |

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| Houdini | Too expensive for indie team. Blender Geometry Nodes + Python covers equivalent procedural capability. Project constraint explicitly excludes Houdini. |
| HDRP | Project uses URP. HDRP entering maintenance per Unity 2026 strategy. URP Forward+ handles dark fantasy lighting requirements (many point lights, volumetrics). |
| Virtual Texturing | URP does not support Virtual Texturing (HDRP-only). Use texture streaming via Addressables instead. |
| Google Genie 3 / Neural rendering | No mesh export. Neural rendering output cannot be used in game engines. Fundamentally incompatible with game development pipeline. |
| Shap-E / Point-E / DreamFusion | Abandoned research tools. Completely superseded by Tripo, Hunyuan3D, Rodin. |
| Single AI generator strategy | The quality gap between generators makes multi-tool mandatory. Tripo for topology, Hunyuan for bulk, Rodin for hero quality. |
| aiohttp | Redundant with httpx (already in MCP SDK). Adds ~15MB dependencies for zero additional capability. |
| OpenCV (cv2) | 100+ MB. Designed for computer vision, not texture processing. Pillow + numpy handles all texture operations. |
| Per-building unique textures | Memory nightmare. Use trim sheets and shared materials per kit. One 4096x4096 trim sheet per architectural style, not per building. |
| Monolithic building meshes | No LOD flexibility, no interior streaming, no modular variation. Use kit pieces at 1m grid. |
| Linear terrain blending | Height-based blending is the AAA standard. Linear interpolation creates obvious material borders. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Procedural Engine | bpy + Geometry Nodes | Pure Geometry Nodes | Geo Nodes cannot create vertex groups, vertex colors, shape keys, or complex topology. bpy is required for these operations. Hybrid approach is correct. |
| AI Generator (primary) | Tripo v3.0 | Meshy 4 | Tripo produces better topology for animation. Meshy excels at props but our cleanup pipeline handles that. |
| AI Generator (bulk) | Hunyuan3D 2.1 (self-hosted) | TRELLIS.2 | Hunyuan has better PBR (8K textures), lower VRAM (6GB), and proven production track record. TRELLIS.2 is newer with less production history. Consider as future backup. |
| AI Generator (hero) | Rodin Gen-2 | Kaedim | Kaedim requires $299+/mo enterprise subscription. Rodin achieves comparable quality at $0.30-1.50 per asset via API. |
| Interior Gen (hero) | World Labs Marble | Meta WorldGen | Meta WorldGen not yet released (research paper only, possible 2026 release). Marble is available now. |
| Interior Gen (bulk) | compose_interior pipeline | Holodeck (Allen AI) | Holodeck requires AI2-THOR framework + GPT-4o API. compose_interior is already integrated, uses our existing tools, no external framework dependency. |
| Texture Gen (AI) | Scenario.gg | Leonardo.AI | Scenario.gg has better PBR channel support and custom model training. Leonardo has broader model selection but less PBR focus. Both are viable; Scenario.gg is more game-dev specific. |
| Terrain Gen | OpenSimplex (custom) | Gaea 2.2 | Gaea produces better erosion but requires separate application + export workflow. OpenSimplex + custom erosion keeps everything in Blender pipeline. |
| Level Design | Modular kits + WFC | Full procedural generation | Full procedural lacks hand-crafted feel that Souls-like games require. Modular kits + WFC for layout + manual composition for quality. |
| LOD Decimation | pymeshlab (Quadric Edge Collapse) | trimesh simplify | pymeshlab's Quadric Edge Collapse preserves silhouette better. trimesh's simplification is adequate for quick LODs but lower quality. |

---

## Installation

### AI Generation APIs

```bash
# Tripo3D (existing - upgrade model version)
# No new install needed. Update model_version parameter to v3.0 in tripo_client.py

# Hunyuan3D 2.1 (new - self-hosted)
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git
cd Hunyuan3D-2.1
pip install -r requirements.txt
# Download model weights (~6GB)
python app.py  # Starts Gradio server on localhost

# Rodin Gen-2 (new - API only, no install)
# REST API via developer.hyper3d.ai - no local install required
# Add RODIN_API_KEY to .env

# World Labs Marble (new - SaaS, no install)
# Sign up at worldlabs.ai, use web interface for generation
# Export GLB files for Blender import pipeline
```

### Python Dependencies

```bash
# Already in stack (no new installs needed for core):
# trimesh, pygltflib, pymeshlab, Pillow, numpy, httpx

# New dependency for Scenario.gg (if added):
uv add "httpx>=0.27.1"  # Already installed - use for REST calls

# New dependency for Hunyuan3D client (if self-hosting):
# Gradio client for Python API calls
uv add "gradio-client>=1.0"
```

### Environment Variables

```bash
# Existing (keep):
TRIPO_API_KEY=...
FAL_KEY=...

# New:
RODIN_API_KEY=...          # Hyper3D API key (hero assets)
HUNYUAN_URL=http://localhost:7860  # Local Hunyuan3D Gradio server
WORLDLABS_API_KEY=...      # World Labs Marble (hero interiors)
SCENARIO_API_KEY=...       # Scenario.gg (PBR textures, optional)
```

---

## Integration with Existing Pipeline

The existing `asset_pipeline` and related tools form the backbone. New capabilities layer on top:

| Existing Tool | New Capability | How |
|---------------|---------------|-----|
| `asset_pipeline compose_map` | Enhanced biome system | Add corruption-aware biome noise to map_spec |
| `asset_pipeline compose_interior` | World Labs Marble hero rooms | Add Marble GLB import as room geometry source |
| `asset_pipeline generate_3d` | Multi-backend AI generation | Add backend parameter (tripo/hunyuan/rodin) |
| `asset_pipeline generate_building` | Geometry Nodes facade system | Build GNG facade generators for building exteriors |
| `blender_texture create_pbr` | Scenario.gg PBR sets | Add AI texture generation as PBR source |
| `blender_texture validate_palette` | Dark fantasy enforcement | Already exists, use for all procedural materials |
| `blender_mesh game_check` | Poly budget enforcement | Already exists, use for all generated meshes |
| `blender_quality` generators | Enhanced AAA quality | Upgrade existing 32 generators with better topology |
| `blender_worldbuilding` | Corruption variants | Add corruption_level parameter to all generators |

---

## Sources

### Official Documentation (HIGH confidence)
- Blender 5.1 Geometry Nodes: https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html
- Tripo3D API: https://platform.tripo3d.ai/docs
- Hunyuan3D-2.1 GitHub: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Hyper3D Rodin Gen-2 API: https://developer.hyper3d.ai
- World Labs Marble: https://docs.worldlabs.ai/marble/export/mesh
- Unity URP Docs: https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0

### Existing Research Files (HIGH confidence, project-verified)
- `.planning/research/AI_3D_GENERATION_TOOLS_RESEARCH.md` -- 15+ AI 3D tools compared
- `.planning/research/AI_INTERIOR_GENERATION_RESEARCH.md` -- Interior generation tools
- `.planning/research/AAA_TOOLS_MODELING_RESEARCH.md` -- 14 industry tools analyzed
- `.planning/research/AAA_TOOLS_TERRAIN_ENVIRONMENT_RESEARCH.md` -- Studio terrain techniques
- `.planning/research/AAA_BEST_PRACTICES_COMPREHENSIVE.md` -- Triangle budgets, LOD, equipment
- `.planning/research/TEXTURING_ENVIRONMENTS_RESEARCH.md` -- Terrain/building texturing pipeline
- `.planning/research/MAP_BUILDING_TECHNIQUES.md` -- Level design, modular kits, streaming

### AAA Studio References (MEDIUM-HIGH confidence)
- FromSoftware level design: interconnected world, 30-second rule, prop density 10-20 per room
- Bethesda: cell grid, 3-type LOD, modular kit system
- Guerrilla Games: GPU-based procedural placement, graph editor
- CDPR: 16384x16384 heightmaps, 40-second POI rule
- DOOM 2016 Graphics Study (Adrian Courreges): performance reference
