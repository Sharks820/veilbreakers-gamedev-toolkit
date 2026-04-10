# AAA Terrain Generation Techniques for Procedural Blender/bmesh Implementation

**Researched:** 2026-04-05
**Domain:** Terrain geometry, cliff meshes, scatter systems, material layering
**Confidence:** HIGH (cross-referenced GDC postmortems, shipped game analysis, existing VB codebase research)

---

## 1. Layered Terrain Geometry

AAA terrain is NEVER a single displaced plane. Studios use 4-5 noise layers simultaneously:

| Layer | Frequency | Amplitude | Purpose |
|-------|-----------|-----------|---------|
| Continental | 500-2000m | 50-500m | Mountain ranges, major valleys |
| Regional | 50-200m | 5-50m | Hills, ridges, basins |
| Local | 10-50m | 0.5-5m | Mounds, gullies, depressions |
| Micro | 1-5m | 5-30cm | Ground undulation (the "never flat" rule) |
| Surface | 0.1-0.5m | 1-5cm | Pebble bumps, soil texture |

**bmesh implementation:** Build a subdivided grid (4-8 subdivisions per meter in hero areas, 1-2 for distance). Apply FBM noise with 4-6 octaves using opensimplex. Each octave = one layer. Use persistence 0.45-0.55 and lacunarity 2.0.

**Chunking:** Break terrain into 64x64m or 128x128m tiles. Stitch edges by sharing boundary vertex positions. LOD: reduce subdivision by 2x per distance tier (LOD0=full, LOD1=half, LOD2=quarter). Guerrilla Games (Horizon) uses GPU-based composition of multiple maps with painted rules -- everything updates procedurally.

**Detail overlays:** After base heightmap, add secondary displacement passes: erosion channels (flow-based simulation or directional noise along slope gradient), thermal erosion (flatten peaks above angle-of-repose ~35 degrees), and hydraulic deposits in valleys.

---

## 2. Cliff Generation

The fundamental problem: heightmaps map one height per (x,y) -- they CANNOT represent true cliffs (>70 degrees), overhangs, or caves. Every AAA studio uses a hybrid approach.

### The Hybrid Method (Use This)

1. Generate base heightmap terrain normally
2. Detect steep zones (slope > 60 degrees threshold)
3. Replace steep zones with separate cliff-face meshes as overlay geometry
4. Cliff meshes are proper 3D -- vertical quads with horizontal extent, allowing overhangs

### Cliff Mesh Cross-Section Profile

A realistic cliff has three zones in cross-section:

- **Convex break** (top 10%): gradual slope steepens to near-vertical over 1-3m. Use smootherstep (6t^5 - 15t^4 + 10t^3) for zero second-derivative at endpoints.
- **Vertical face** (middle 60%): 85-100 degree angle, slight random overhang offset (0.2-0.5m inward). This is where strata layers live.
- **Talus/scree base** (bottom 30%): debris slope at 30-38 degrees (angle of repose). Scatter boulder meshes here.

### Rock Strata Layering (The #1 Visual Feature)

Real cliffs show alternating hard/soft rock bands. Hard layers protrude 0.3-0.8m; soft layers recess 0.2-0.8m. Implementation:

```python
# Define strata as 1D height profile
for each vertex on cliff face:
    layer = lookup_strata(vertex.z)  # which rock band
    if layer.is_hard:
        offset vertex outward by layer.protrusion
        apply low-frequency noise (scale 2-4m)
    else:  # soft layer
        offset vertex inward by layer.recession
        apply high-frequency noise (scale 0.3-0.8m) for erosion channels
        add vertical groove displacement for water-carved channels
```

Vary layer thickness: hard layers 0.3-1.2m thick, soft layers 0.8-2.5m thick. 8-15 layers per 20m cliff.

### Overhang Generation

At soft-to-hard layer boundaries, offset the hard layer's lower edge outward by 0.3-1.0m while the soft layer beneath recedes. This creates natural undercuts. For dramatic overhangs, extrude a shelf from any hard layer edge, tapering to zero thickness over 1-2m horizontal extent.

### Cliff Detail Meshes

Scatter on cliff faces: exposed root meshes (2-4 per 10m^2), small rock protrusions (5-8 per 10m^2), vegetation tufts in crevices where soft layers meet hard (3-5 per 10m^2). Use face normal dot product with UP vector to find horizontal ledges for placement.

---

## 3. Environmental Scatter Systems

### Placement: Poisson Disk Sampling

Bridson's algorithm generates blue-noise distributed points -- natural-looking, no clumping, no grid artifacts. The VB codebase already has this in `_scatter_engine.py`.

**Density control:** Multiply Poisson min_distance by an inverse density map value. Dense forest = small min_distance (1-2m between trees), sparse ridge = large min_distance (8-15m).

### LOD Chain for Scatter Props

| LOD | Distance | Technique | Tri Budget |
|-----|----------|-----------|------------|
| LOD0 | 0-20m | Full mesh | 100% |
| LOD1 | 20-50m | Simplified mesh | 30-50% of LOD0 |
| LOD2 | 50-100m | Billboard cross (2 planes) | 4-8 tris |
| LOD3 | 100m+ | Single billboard or fade out | 2 tris |

### Typical Vertex Budgets (Per Instance, LOD0)

| Category | Tris | Unique Variants | Notes |
|----------|------|-----------------|-------|
| Hero tree | 8K-15K | 3-5 species, 5-10 per species | Different age, lean, damage |
| Bush/shrub | 500-2K | 4-6 types | Alpha-cutout leaves |
| Grass clump | 20-80 | 3-4 blade patterns | GPU instanced, 50-200/m^2 |
| Large rock | 500-2K | 5-8 shapes | Reuse with random rotation/scale |
| Small rock | 50-200 | 4-6 shapes | Dense scatter near paths/water |
| Fallen log | 1K-3K | 3-4 variants | Near trees, across paths |
| Mushroom cluster | 100-400 | 3-5 types | Damp areas, tree bases |

### Placement Rules

- Trees: avoid slopes > 40 degrees, min 3m from paths, cluster in groups of 3-7
- Rocks: denser on ridgelines and near water, random rotation 0-360, scale 0.7-1.3x
- Grass: density from biome mask, zero on paths/rock surfaces, sparser on slopes > 25 degrees
- Debris (leaves, twigs): wind-accumulated against obstacles, under trees, 5-15/m^2

---

## 4. Terrain Material Layering

### Splatmap System

Use vertex colors as splatmap channels: R=grass, G=rock, B=dirt, A=special (snow/moss/corruption). Assign per-vertex based on rules:

- **Slope**: 0-25 degrees = grass dominant, 25-50 = dirt/rock blend, 50+ = rock only
- **Height**: valley floor = lush grass, mid-altitude = sparse grass + rock, peaks = bare rock + snow
- **Moisture**: near water = mud/moss, dry ridges = bare rock/dead grass
- **Erosion**: flow accumulation zones = darker soil, exposed ridges = lighter rock

The VB codebase already implements this in `terrain_materials.py` with 14 biome palettes.

### Triplanar Mapping for Cliffs

Standard UV projection stretches horribly on vertical faces. Triplanar mapping projects textures from X, Y, and Z axes simultaneously, blending based on face normal direction. For cliff faces where normal points mostly horizontal, the Y-axis projection dominates, eliminating stretch.

**Blender implementation:** In shader nodes, use Object coordinates split into XY, XZ, YZ planes. Blend using `abs(normal)` as weights with sharpness factor 2-8 (higher = sharper transitions between projection planes).

### Height-Based Material Blending (NOT Linear Alpha)

Linear blending creates muddy 50/50 mush zones. Height blending uses a per-material height map so rocks poke through grass at their highest points first, dirt fills crevices between rocks. Transition sharpness: 0.15-0.3, blend zone width: 0.5-2.0m.

### Macro/Micro Detail

- **Macro** (50-200m period): color/value noise overlay, shifts hue 5-15% to break tiling
- **Meso** (5-20m): terrain feature coloring -- darker in valleys, lighter on ridges
- **Micro** (0.1-0.5m): detail normal map for soil granularity, individual pebble bumps
- **Procedural overlays**: moss on north-facing surfaces (dot product normal vs north < -0.3), snow accumulation on upward faces (dot product normal vs up > 0.7), dirt in concavities (ambient occlusion proxy)

---

## Sources

- [Guerrilla Games: GPU-Based Procedural Placement in HZD](https://www.guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn)
- [NVIDIA GPU Gems: Complex Procedural Terrains](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1-generating-complex-procedural-terrains-using-gpu)
- [ResearchGate: Procedural Landscapes with Overhangs](https://www.researchgate.net/publication/2948853_Procedural_Landscapes_with_Overhangs)
- [Ben Golus: Normal Mapping for Triplanar Shader](https://bgolus.medium.com/normal-mapping-for-a-triplanar-shader-10bf39dca05a)
- [Catlike Coding: Triplanar Mapping (Unity)](https://catlikecoding.com/unity/tutorials/advanced-rendering/triplanar-mapping/)
- [Envato: Tri-Planar Texture Mapping for Terrain](https://gamedevelopment.tutsplus.com/articles/use-tri-planar-texture-mapping-for-better-terrain--gamedev-13821)
- VeilBreakers existing research: AAA_TERRAIN_VISUAL_STANDARDS.md, CLIFF_CAVE_CANYON_DESIGN.md, TERRAIN_MESHING_TECHNIQUES.md
