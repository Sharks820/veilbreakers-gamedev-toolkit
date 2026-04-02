# Cutting-Edge Procedural Generation Techniques (2025-2026)

**Researched:** 2026-04-01
**Purpose:** Latest AI/ML and algorithmic advances for the VeilBreakers procedural world toolkit
**Sources:** GDC 2024-2025, arXiv papers, SideFX talks, studio blogs, open-source projects

---

## 1. AI TERRAIN GENERATION

### Terrain Diffusion (Dec 2025) — Successor to Perlin Noise
- **Repo:** github.com/xandergos/terrain-diffusion (open source)
- Hierarchical diffusion stack: planetary context → local detail
- Compact Laplacian encoding for Earth-scale dynamic ranges
- Infinite seamless extent, seed-consistent, constant-time random access
- Outpaces orbital velocity 9x on consumer GPU
- **Implementation:** Heightmap generator node, train on DEM data, few-step distillation

### TerraFusion (May 2025) — Joint Height + Texture Generation
- Dual-VAE architecture (custom heightmap VAE + SD pretrained texture VAE)
- Latents concatenated, single U-Net processes both modalities
- Training: 4,119 paired samples (NASADEM 30m + Sentinel-2 10m), 276 global locations
- FID_CLIP 9.8 (fine-tuned) vs 22.1 for PSGAN
- ~2 seconds per 512x512 on RTX A6000 (20 steps)
- ControlNet sketch input: red=valleys, green=ridgelines, blue=cliffs

### Earthbender (SIGGRAPH MIG 2025) — Sketch-Conditioned Terrain
- Extends Stable Diffusion with ControlNet for terrain from sketches
- Multi-channel input: Canny edges (structure), R (mountains), G (lakes), B (roads/rivers)

### Hatchling's Mathematical Erosion (2025) — Fastest Known
- Threshold-based mathematical approximation (not physical simulation)
- **1024x1024 in 100-300ms on RTX 3060**
- Slab-like functions with layered thresholds + distance lookups
- Params: window_size (slope steepness), layer_count (200 smooth, 120 for 512x512)
- O(n²) optimizable with min-max quad trees

---

## 2. PROCEDURAL VEGETATION

### Natsura (2025) — Growth Simulation Engine
- Houdini-native, 100+ nodes, growth graph engine
- Core nodes: Grow/Split/Repeat with effectors (gravity, light, collision)
- Mapping system: parameters driven by custom graphs
- Nanite-native foliage output
- **Portable to Blender geometry nodes**

### SpeedTree 10 (2024)
- Vine Generator: procedural surface-crawling vines
- Mesh Spines: additional geometry off meshes
- Trim Brush: viewport sculpting of tree forms
- Rules System: Lua scripting for automation

### Multi-Pass Vegetation Scattering
- Pass 1: Large trees + bushes (primary structure)
- Pass 2: Grasses, ivy, roots, flowers (respecting primary)
- Pass 3: Non-biome debris (rocks, sticks)
- Biome matrix: height × humidity × temperature → biome type
- Humidity = precipitation + water_proximity
- Temperature = base - (latitude_factor + elevation_factor) + water_proximity_factor

---

## 3. WORLD GENERATION AT SCALE

### Infinigen (Princeton, BSD License)
- **Repo:** github.com/princeton-vl/infinigen
- Full procedural Blender world generator, zero external assets
- Generates: terrain, plants, creatures (carnivores, herbivores, birds, beetles, fish), coral, water (FLIP), weather, sky (Nishita)
- Infinigen Indoors (2025): complete interior scenes
- Export: OBJ, FBX, STL, PLY, USD
- Installable as Blender Python script

### Meta WorldGen (Nov 2025)
- Text → interactive 50x50m fully textured 3D worlds
- LLM-driven scene layout + procedural gen + diffusion 3D + scene decomposition

### Ruinify (SideFX Elderwood 2025)
- Converts blockout geometry into detailed ruins
- Fractures, edge damage, dirt deposition
- Planar Inflate node for cliff/rock generation (Houdini 20.5)
- Free download with complete UE5 project

---

## 4. ADVANCED WFC VARIANTS

### Hierarchical Semantic WFC (2023-2024)
- Operates beyond flat tile sets using semantic hierarchies
- Complex structured environments with meaningful relationships

### Chunked Hierarchical WFC (2024)
- Generates large worlds by chunking the WFC domain
- Infinite/streaming generation without memory limits

### Space-Time WFC (AAAI Nov 2024)
- WFC extended into temporal dimension
- Generates layout AND valid solution paths simultaneously

### WFC + Genetic Algorithm Hybrid (2025)
- GA optimizes WFC parameters and constraint weights
- Improved success rates for complex constraint sets

---

## 5. LLM-DRIVEN PROCEDURAL GENERATION

### LatticeWorld (FDG 2025)
- Natural language → GLDL → Facility Layout Optimization → 3D scene
- **~90x reduction in artist-days** for high-fidelity 3D production

### PCGRLLM
- LLM-driven reward design with iterative feedback
- 415% accuracy improvement over zero-shot baselines

### Word2World
- Story → entity/goal/tile extraction → iterative map composition → asset retrieval

---

## 6. BLENDER ECOSYSTEM (2025)

| Tool | Purpose | Key Feature |
|------|---------|-------------|
| World Blender 2025 | GN landscape generator | Sculpt-to-procedural, particle erosion |
| Hydra | Hydraulic erosion addon | OpenGL particle + pipe erosion |
| Botaniq v7.1 | Vegetation library | 405 new assets (2025) |
| Geo-Scatter | Biome scattering | 80+ biome presets |
| SkyscrapX | Procedural buildings | 100+ floors in seconds |
| SceneCity | City generator | Roads + mass building placement |

### External Terrain Tools
| Tool | 2025 Feature |
|------|-------------|
| Gaea 2.2 | Selective precipitation erosion, GPU Erosion_2, Glacier nodes |
| Gaea 3.0 (2026) | Vector roads/rivers, sand/snow sim, 2.7D displacement |
| World Creator 2025.1 | Hundreds of millions of objects, biome painting |

### Blender 5.0 Geometry Nodes (Nov 2025)
- Bundles, closures, 27 new volume grid nodes
- New modifiers: Array, Scatter on Surface, Instance on Elements, Randomize Instances
- Now rivals Houdini for procedural workflows

---

## 7. RENDERING FRONTIERS

### 3D Gaussian Splatting for Games
- Formally recognized as viable production tech in 2025
- Millions of Gaussian points with color/orientation/radius/opacity
- Interactive physics-driven splat environments in Unity
- Use case: distant scenery, cinematic sequences

### NeRF Hybrid Rendering
- NeRFs for background/mid-distance, traditional meshes for gameplay
- Heightmaps/biomes generated procedurally, NeRFs as detailed skins

---

## KEY IMPLEMENTATION PRIORITIES FOR VEILBREAKERS

1. **Hatchling's fast erosion** (100-300ms) — immediate terrain quality upgrade
2. **Multi-pass vegetation scattering** with biome matrix — systematic vegetation
3. **Ruinify-style post-processing** — dark fantasy ruins from blockouts
4. **Infinigen reference** — BSD-licensed, adapt creature/plant generators
5. **Terrain Diffusion** — AI heightmaps as alternative to Perlin noise
6. **Hierarchical Chunked WFC** — infinite dungeon/settlement generation
7. **LLM-driven layout** — natural language to structured world data
8. **Growth-graph vegetation** — Natsura-style Grow/Split/Repeat in GN
