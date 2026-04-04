# Terrain Final Polish: What Separates "Good" from "AAA"

**Project:** VeilBreakers GameDev Toolkit
**Researched:** 2026-04-03
**Overall Confidence:** HIGH (multiple AAA postmortems, official docs, existing codebase audit)

---

## Current Toolkit State (What We Already Have)

Before listing what to add, here is what the toolkit already provides:

- **Scatter engine** (`_scatter_engine.py`): Poisson disk sampling, biome filtering, context-aware placement
- **Vegetation system** (`vegetation_system.py`): 14 biomes, per-biome vegetation sets, slope/height filtering, wind vertex colors
- **Environment scatter** (`environment_scatter.py`): Leaf card canopies, 6-biome grass cards, combat clearings, rock power-law distribution
- **Decal system** (`decal_system.py`): 10 decal types (blood, cracks, moss, water stains, scorch marks, runes, etc.)
- **Terrain materials** (`terrain_materials.py`): 14 biome palettes, vertex color splatmaps, corruption tint overlay, biome transitions
- **Terrain chunking** (`terrain_chunking.py`): Streamable chunks, LOD via bilinear downsampling, neighbor stitching, Unity metadata export
- **Terrain features** (`terrain_features.py`): Canyons, waterfalls, cliff faces, swamps, natural arches, sinkholes, lava flows
- **Terrain advanced** (`terrain_advanced.py`): Spline deformation, non-destructive layers, erosion painting, flow maps, snap-to-terrain
- **Prop density** (`prop_density.py`): 12 room types, 50-200 props per room, surface-zone classification

**Gaps this research targets:** The micro-details and integration polish that make the difference between "technically correct procedural terrain" and "terrain that feels hand-crafted by an art team."

---

## 1. Ground Clutter and Micro-Detail

### What AAA Games Actually Do

AAA terrain detail uses a layered approach with 4 distinct systems running simultaneously:

**Layer 1: Terrain Material (base)**
The splatmap-blended terrain material itself. Our toolkit handles this well with 14 biome palettes and vertex color blending. The polish gap: **micro-normal detail maps.** Every AAA terrain material uses a tiled detail normal map (scale ~2-5m) layered on top of the macro normal map. This adds the feeling of individual pebbles, soil grain, and surface roughness without any geometry cost.

**Layer 2: Grass Cards (near-ground vegetation)**
Two rendering approaches exist:

| Approach | Geometry | Performance | Visual Quality | When to Use |
|----------|----------|-------------|----------------|-------------|
| **Billboard quads** | 4 verts per instance | Excellent | Acceptable at distance, obvious up close | Distance > 15m from camera |
| **Cross-quad (X-pattern)** | 8 verts, two intersecting quads | Good | Much better parallax | 5-15m from camera |
| **Mesh grass** | 10-30 verts per blade cluster | Poor at density | Best | < 5m from camera (hero areas only) |

**Recommendation for VeilBreakers:** Use cross-quads as the primary grass representation. Billboard LOD at distance. Our `environment_scatter.py` already generates grass cards -- the gap is that we do not generate LOD variants or specify camera-distance thresholds for the Unity side.

**Key performance trick (Ghost Recon Wildlands, Horizon Zero Dawn):** GPU instancing with indirect draw calls. Compute shader culls instances against frustum + occlusion buffer, then emits an indirect draw buffer. This lets you scatter 500K+ grass instances and only draw the 20K-50K that are actually visible. Unity URP supports `Graphics.DrawMeshInstancedIndirect` for this.

**Layer 3: Ground scatter particles (leaves, twigs, pebbles)**
Small geometry instances placed via Poisson disk sampling (which we already have). The polish detail most games add that we are missing:

- **Size variation follows power-law distribution** -- we do this for rocks but not for ground debris
- **Rotation should include slight Z-axis tilt** (0-8 degrees) to break the "perfectly flat on ground" look
- **Clustering:** Natural debris clumps. Instead of pure Poisson spacing, add a secondary pass that clusters 3-7 items together at 30% of placement points. Leaves gather in wind shadows, twigs collect near trees.
- **Color variation per-instance:** 15-25% hue/value shift via vertex color or material property block to break tiling

**Layer 4: Decals (puddles, cracks, moss, roots)**
Our decal system has 10 types. The AAA polish missing:

- **Puddle decals need a wetness mask** that darkens surrounding terrain material roughness in a falloff radius (not just the decal quad itself)
- **Moss decals should follow moisture flow lines** -- place them where water would accumulate (concave terrain, north-facing slopes, wall bases). Our flow map computation in `terrain_advanced.py` could feed moss placement.
- **Root decals** at tree bases are almost universal in AAA -- radial pattern of 3-6 root decals projecting outward from trunk, with height displacement
- **Layering order matters:** Ground material -> crack decals -> moss decals -> puddle decals (puddles cover moss, moss grows in cracks). Unity URP Decal Projector supports sort order via the rendering layer.

### When to Use Geometry vs Normal Maps vs Decals

| Detail Type | Size | Geometry | Normal Map | Decal |
|-------------|------|----------|------------|-------|
| Individual pebbles | < 3cm | Never | Detail normal on terrain mat | Never |
| Cracks in ground | 5-50cm | Never | Never | Yes (normal-only decal) |
| Moss patches | 20cm-2m | Never | Never | Yes (albedo + normal decal) |
| Puddles | 30cm-3m | Never | Never | Yes (albedo + roughness decal) |
| Rocks | 10cm-2m | Yes (instanced) | Never | Never |
| Tree roots | 5cm-1m visible | Geometry for large | Normal map baked | Decal for surface detail |
| Fallen logs | 30cm-3m | Yes (instanced) | Never | Never |
| Grass | 5-30cm | Cross-quad cards | Never | Never |
| Terrain grain | < 1cm | Never | Detail normal tiling | Never |

---

## 2. Edge and Border Polish

### Terrain Skirt Meshes

Every shipped terrain system uses skirt geometry -- a vertical strip of triangles extending downward from the terrain edge. Without it, camera angles that look toward the terrain boundary reveal the paper-thin edge of the heightmap.

**Implementation:** For each edge vertex, duplicate it and offset downward by 10-20 units. Connect with triangles. Apply the same material as the terrain edge. Cost: negligible (one strip of tris per edge).

**Our gap:** `terrain_chunking.py` handles chunk neighbors and edge stitching but does not generate skirt geometry for world-edge chunks. Add a `generate_terrain_skirt()` function that takes edge vertices and produces a downward-extending strip.

### Distance Fog and Atmospheric Falloff

AAA games use layered fog to hide terrain boundaries:

1. **Height fog** (exponential, denser near ground): Obscures distant ground-level detail, making the terrain edge disappear into atmosphere. Critical for dark fantasy -- gives valleys a misty, ominous feel.
2. **Distance fog** (linear or exponential): Fades everything beyond a threshold. For VeilBreakers' dark fantasy, use a desaturating fog that shifts toward cool blue-grey rather than white.
3. **Volumetric fog** (particle-based or ray-marched): Most expensive but most convincing. Unity URP supports volumetric fog in Unity 6. Use sparingly -- full-screen volumetric fog at high quality costs 1-2ms GPU.

**Recommendation:** Height fog (always on, cheap) + distance fog (always on, cheap) + volumetric fog (opt-in for hero areas like swamps, veil cracks). Our Unity scene templates should emit fog configuration per biome.

### Edge-of-World Strategies

| Strategy | Visual Quality | Cost | Best For |
|----------|---------------|------|----------|
| **Ocean surrounding** | High | Low | Coastal/island maps |
| **Mountain wall ring** | High | Medium | Valley/basin maps |
| **Dense fog wall** | Medium | Low | Any map, dark fantasy fits well |
| **Invisible wall + fog** | Medium | Low | Quick solution |
| **Skybox distant terrain** | High | Low | Large open worlds |
| **Kill volume + narrative** | Context-dependent | None | "Corrupted wasteland" beyond boundary |

**Recommendation for VeilBreakers:** Use a corruption fog wall. The Veil itself is the narrative boundary -- thick, swirling dark fog with particle effects that damages the player. This is both a game mechanic and a visual edge-hider. The corruption tint system in `terrain_materials.py` already supports graduated corruption -- extend it to full-opacity at world edges.

---

## 3. Lighting Integration

### Terrain Normal Maps and Directional Light

The most common terrain lighting mistake: **terrain splatmap blending that averages normals incorrectly.** When blending between grass and rock materials via vertex color weights, the normal maps must use **Reoriented Normal Mapping (RNM)** blend, not linear interpolation. Linear blend flattens normals at transitions, creating a visible "soft band" between materials.

**RNM blend formula (shader):**
```hlsl
float3 BlendNormals_RNM(float3 n1, float3 n2) {
    n1.z += 1.0;
    n2.xy = -n2.xy;
    return normalize(n1 * dot(n1, n2) - n2 * n1.z);
}
```

**Detail normal maps** should tile at 5-10x the terrain UV scale and blend multiplicatively with the macro normal. This ensures directional light catches micro-surface detail (gravel texture catching low-angle sunset light, for example).

### Shadow Quality from Terrain Features

Terrain features (cliffs, valleys, overhangs) need proper shadow resolution:

- **Cascaded Shadow Maps (CSM):** Unity URP defaults to 4 cascades. For terrain, ensure cascade 3-4 extend far enough to cover distant cliff shadows. Typical: 10m / 25m / 60m / 150m split distances.
- **Self-shadowing from heightmap:** Cliffs should cast shadows on adjacent valleys. This requires the terrain mesh to be in the shadow caster list (it is by default in Unity terrain, but custom mesh terrain may need explicit shadow caster pass).
- **Contact shadows:** For small terrain features (rocks, roots, slight height changes), enable screen-space contact shadows in URP. Adds ~0.3ms but dramatically improves grounding of small objects.

### Light Probes and Terrain

Light probe placement for terrain is often wrong in procedural systems:

- **Do not place probes in a uniform grid.** Place them at height transitions (hilltop, valley floor, cave entrance, under overhangs) and at biome boundaries.
- **Probe density near terrain surface:** At least one probe layer 0.5m above terrain, one at 2m. Objects between probes interpolate.
- **Terrain bounce color:** Light probes near green grass terrain will have green bounce fill. Near dark rock, they will be much darker. This is correct behavior but means probe placement must account for material zones -- a probe placed at a grass/rock boundary will have incorrect interpolation for both.

### Global Illumination Bounce

For pre-baked GI (lightmaps), terrain albedo significantly affects bounce lighting:

- Dark fantasy terrain (value 10-50%) produces very little bounce light. This is correct and atmospheric.
- The risk: interiors near terrain (cave entrances, building doorways) get almost no bounce fill and appear pitch black. Add fill light probes or emissive accent lighting at these transition zones.
- Unity 6 URP: Use Adaptive Probe Volumes (APV) instead of legacy light probes for terrain. APV auto-places probes at density proportional to lighting variation.

---

## 4. Performance Tricks

### Texture Streaming for Large Terrain

Unity's Streaming Virtual Texturing (SVT) slices textures into tiles streamed on demand. For terrain:

- **Splatmap textures** (control maps): Should NOT be streamed -- they are small and always needed.
- **Layer albedo/normal textures:** CAN be streamed. Use `Texture Streaming` quality setting per texture.
- **Custom virtual texturing for unique areas:** Where hand-painted terrain detail exists, runtime virtual texturing avoids loading full-resolution textures. Open-source URP implementations exist (github.com/haolange/InfinityTexture).

**Practical recommendation:** For VeilBreakers' scale (city-sized maps, not continent-sized), standard mipmapping with streaming enabled is sufficient. Virtual texturing is overkill unless maps exceed 4km x 4km.

### GPU Instancing for Repeated Props

The single most impactful performance technique for terrain detail:

```
Without instancing: 10,000 rocks = 10,000 draw calls = unplayable
With instancing:    10,000 rocks = 1-5 draw calls (per unique mesh) = fine
```

**Requirements for instancing to work in Unity URP:**
1. All instances share the same Mesh + Material
2. Material has "Enable GPU Instancing" checked
3. Use `Graphics.DrawMeshInstanced` or `Graphics.DrawMeshInstancedIndirect`
4. Per-instance variation via `MaterialPropertyBlock` (color tint, scale) -- but this breaks SRP Batcher. For URP, prefer shader-side per-instance data via `UNITY_ACCESS_INSTANCED_PROP`.

**Our toolkit gap:** The scatter system places objects as individual Blender objects. When exported to Unity, each becomes a separate GameObject. The Unity-side setup needs a `ScatterInstanceRenderer` component that converts placed markers into instanced draw calls. Our Unity templates should generate this.

### Impostor/Billboard Rendering for Distant Vegetation

Trees beyond 80-100m should switch to billboard impostors:

- **Octahedral impostor:** 8 pre-rendered views baked into a single atlas. Interpolates between views based on camera angle. Much better than single-plane billboard.
- **Our toolkit:** `vegetation_lsystem.py` already has `generate_billboard_impostor()`. The gap is that we do not generate octahedral atlases (8 views), only single-view billboards.
- **LOD chain:** Mesh tree (0-30m) -> Reduced mesh (30-60m) -> Cross-billboard (60-100m) -> Impostor card (100m+) -> Fade out (150m+)

### Draw Call Batching

| Strategy | Unity URP Support | When to Use |
|----------|-------------------|-------------|
| **SRP Batcher** | Built-in | All shader graph materials (automatic) |
| **GPU Instancing** | Built-in | Repeated identical meshes (rocks, grass, debris) |
| **Static Batching** | Built-in | Non-moving terrain props (rocks, stumps, walls) |
| **Dynamic Batching** | Built-in but limited | Small meshes < 300 verts (rarely useful for terrain) |
| **Indirect Instancing** | Custom compute shader | 50K+ instances (grass, leaves) |

**Priority order:** SRP Batcher (free) -> Static Batching (cheap) -> GPU Instancing (medium setup) -> Indirect (complex but necessary for grass density).

---

## 5. Common Procedural Generation Anti-Patterns

### Anti-Pattern 1: Tile Seam Visibility at Chunk Boundaries

**What goes wrong:** Adjacent terrain chunks have mismatched heights at shared edges, creating visible seams or cracks.

**Our current mitigation:** `terrain_chunking.py` computes neighbor references for edge stitching. But stitching only fixes geometry -- **material seams** are the real problem. When two chunks use different splatmap weights at their shared edge, the material visually "pops" at the boundary.

**Fix:** Ensure splatmap weights are computed globally (or at least with a 1-cell overlap border per chunk) so adjacent chunks agree on material blending at shared edges. Add a `blend_chunk_borders()` function that averages splatmap weights in a 2-3 meter strip along chunk boundaries.

### Anti-Pattern 2: Uniform Density (Nature is Patchy)

**What goes wrong:** Poisson disk sampling produces evenly-spaced objects. Real nature is clustered: trees grow in groves, rocks accumulate at slope bases, grass is thick in some areas and bare in others.

**Our current state:** We have biome filtering and slope/height rules, which helps. But within valid zones, placement is still uniform-density.

**Fix:** Add a **density noise map** (Perlin, scale ~20-50m) that modulates local placement density by 0.3x to 1.5x. Areas where noise is low get sparse placement; areas where noise is high get dense clusters. This single change transforms "obviously procedural" into "organic."

**Additional clustering technique:** After Poisson sampling, run a secondary pass that adds 2-5 child objects within 1-3m of 20% of parent objects. Trees get saplings, rocks get smaller rocks, mushrooms get mushroom clusters.

### Anti-Pattern 3: Scale Inconsistency

**What goes wrong:** Mixing assets modeled at different scales. A tree that is 3m tall next to a building door that is 2.5m tall looks wrong because real trees are 8-25m and real doors are 2.1m.

**Our dark fantasy scale:** VeilBreakers uses slightly exaggerated proportions (doors are 2.5-3m for gameplay readability, buildings are tall and imposing). The key is internal consistency:

| Element | VeilBreakers Scale | Real World | Ratio |
|---------|-------------------|------------|-------|
| Door height | 2.8m | 2.1m | 1.33x |
| Ceiling height | 3.5-4.0m | 2.7m | 1.33x |
| Tree height | 10-35m | 8-25m | 1.3x |
| Rock boulder | 1-4m | 0.5-3m | ~1.5x |
| Grass blade | 0.15-0.4m | 0.1-0.3m | ~1.3x |

**Rule:** Maintain 1.3x scale multiplier consistently across ALL elements. When one category breaks this ratio, the whole scene feels wrong.

### Anti-Pattern 4: Over-Generation (Visual Noise)

**What goes wrong:** Filling every square meter with objects. The result is visual noise where nothing reads as important, and performance suffers.

**Rules of thumb from AAA postmortems:**
- **Trees:** Max 0.1-0.2 per square meter (dense forest). 0.02-0.05 for sparse woodland.
- **Ground scatter:** Max 2-4 items per square meter for dense areas. Leave 30-50% of ground visible.
- **Rocks:** Max 0.05-0.1 per square meter.
- **Decals:** Max 0.02-0.05 per square meter. Decals are accent, not coverage.
- **Performance budget:** Total visible scatter objects should stay under 50K instances on mid-range hardware. Under 100K on high-end.
- **Negative space is design:** Empty patches of ground between clusters create visual rhythm. Paths should be naturally clear.

### Anti-Pattern 5: Floating Objects Syndrome

**What goes wrong:** Scattered objects placed at terrain height but terrain is curved, so objects hover above or sink into the surface.

**Our current state:** `terrain_advanced.py` has `snap_to_terrain` functionality. But the polish details:

- **Snap is not enough -- you need embed.** Objects should sink 2-5% of their height into terrain to avoid the "sitting on top" look. Rocks should be 10-30% embedded.
- **Normal alignment:** Objects must rotate to match terrain surface normal, not just snap Y position. Our scatter engine does biome filtering but the actual Blender placement in `environment_scatter.py` needs to raycast terrain normal and align object Z-axis.
- **Multi-point grounding for large objects:** A fallen log needs to follow terrain contour, not just snap at its center. Sample terrain height at object bbox corners and interpolate.
- **Edge case: steep slopes.** Objects on slopes > 35 degrees should not be placed at all (they would slide in reality). Our biome filter has slope limits but the specific threshold matters.

---

## 6. Player Navigation Aids

### Natural Leading Lines

**Important finding:** Traditional "leading line" theory (draw literal lines from screenshot to prove player eye movement) is partially debunked by gaze-tracking research. Players do NOT follow lines on the ground. What actually works:

- **Contrast and brightness:** Players look at the brightest or most contrasting element in their field of view. A lit doorway in a dark wall draws the eye.
- **Motion:** Moving elements (swaying flags, flowing water, particle effects) attract attention before static elements.
- **Paths as navigable space, not visual guides:** Cleared paths work because players seek the path of least resistance, not because the path "leads their eye."

**For VeilBreakers terrain generation:**
- Roads and paths should be generated as cleared corridors with lower vegetation density (which our road network already does)
- Rivers serve as natural boundaries AND navigation aids -- follow a river downstream and you find civilization
- Ridge lines provide vantage points -- procedurally place lookout spots at terrain high points

### Landmark Visibility

Landmarks serve two purposes: orientation (where am I?) and goal-setting (where should I go?).

**Implementation rules:**
- At least one landmark visible from any point on the map above tree canopy
- Landmarks should be tall (2-3x tree height minimum), unique silhouette, lit differently from surroundings
- **Distance LOD for landmarks:** Must remain visible at max draw distance. Use billboard impostor that never fades out for key landmarks even when other objects are culled.
- Our `settlement_generator.py` and `worldbuilding.py` create castles, towers, churches -- these should be flagged as "landmark" objects that get special LOD treatment.

**Procedural landmark placement:** Use terrain analysis to find high points (local maxima in heightmap) and place landmarks there. Ensure minimum spacing of 200-400m between landmarks to avoid cluttering the skyline.

### Color Temperature for Area Mood

This is a lighting/post-processing concern more than terrain, but terrain materials contribute:

| Area Type | Color Temperature | Terrain Material Shift | Fog Color |
|-----------|-------------------|----------------------|-----------|
| Safe (town, road) | Warm (5000-6000K) | Slightly warmer browns/greens | Warm grey |
| Neutral (wilderness) | Neutral (6500K) | Standard palette | Cool grey |
| Dangerous (corrupted) | Cool (7000-9000K) | Desaturated, blue-shifted | Blue-purple |
| Boss area | Very cool or warm accent | High contrast, dark base | Deep color |

**Our toolkit gap:** The corruption tint system modifies material color but does not coordinate with lighting or fog. A biome should define not just terrain materials but also associated fog color, ambient light tint, and post-processing LUT. This is a Unity-side concern -- our Unity scene templates should emit per-biome lighting presets.

### Architectural Framing

Natural and built structures that frame views and subtly direct player movement:

- **Canyon walls** funneling toward an opening (our canyon generator does this)
- **Archways and gates** as transition markers between areas
- **Tree canopy gaps** creating natural "windows" to distant landmarks
- **Bridge approaches** with railings that point toward the crossing direction

**Procedural implementation:** When generating paths between points of interest, occasionally place "framing" elements 5-15m before arrival. Rock formations flanking a path, leaning trees creating a canopy arch, ruined pillars marking an entrance.

---

## 7. Specific Implementation Priorities for VeilBreakers

### High Priority (biggest visual impact for effort)

1. **Density noise modulation** -- Add Perlin-based density variation to scatter engine. Single function change, massive visual improvement. Transforms uniform scatter into organic-feeling placement.

2. **Terrain skirt geometry** -- Add `generate_terrain_skirt()` to `terrain_chunking.py`. Prevents edge-of-world visual glitches. 30 minutes of work.

3. **Micro-detail normal maps on terrain materials** -- Add a tiled detail normal map layer to the terrain shader node tree in `terrain_materials.py`. Adds surface grain without geometry. Most terrain materials already have `detail_scale` parameter but it is only used for color noise, not normal detail.

4. **Object embedding depth** -- Modify scatter placement to sink objects 2-5% into terrain (10-30% for rocks). Single parameter addition to scatter system.

5. **Per-biome fog and atmosphere presets** -- Extend biome definitions to include fog color, density, height falloff, and ambient light tint. Unity templates emit matching configuration.

### Medium Priority (noticeable improvement)

6. **Grass LOD tiers** -- Generate billboard variants of grass cards for distance rendering. Hook into LOD pipeline.

7. **Moss placement following flow maps** -- Connect `terrain_advanced.py` flow map output to `decal_system.py` moss placement.

8. **Chunk border splatmap blending** -- Add border-averaging pass to prevent material seams at chunk boundaries.

9. **Scatter clustering pass** -- Secondary placement pass adding child objects near 20% of parent scatter points.

10. **Corruption fog wall at world edges** -- Extend corruption system to act as world boundary visual treatment.

### Lower Priority (polish for later phases)

11. Octahedral impostor atlas generation for trees
12. GPU indirect instancing compute shader for Unity grass
13. Puddle wetness radius falloff in terrain material
14. Landmark auto-detection from heightmap analysis
15. Per-biome post-processing LUT generation

---

## Sources

- [Unity Terrain Grass Documentation](https://docs.unity3d.com/Manual/terrain-Grass.html)
- [Six Grass Rendering Techniques in Unity - Daniel Ilett](https://danielilett.com/2022-12-05-tut6-2-six-grass-techniques/)
- [Unity GPU Instancing Manual](https://docs.unity3d.com/Manual/GPUInstancing.html)
- [Unity GPU Grass Instancer (open source)](https://github.com/MangoButtermilch/Unity-Grass-Instancer)
- [Terrain Rendering Overview and Tricks - Kosmonaut](https://kosmonautblog.wordpress.com/2017/06/04/terrain-rendering-overview-and-tricks/)
- [Terrain Edge Fading - Wolfire Games](http://blog.wolfire.com/2009/02/terrain-edge-fading/)
- [Unity Streaming Virtual Texturing](https://docs.unity3d.com/Manual/svt-streaming-virtual-texturing.html)
- [Runtime Virtual Texture for URP (open source)](https://github.com/haolange/InfinityTexture)
- [Procedural Stochastic Texture Terrain Shader for URP](https://github.com/JuniorDjjr/Unity-Procedural-Stochastic-Texture-Terrain-Shader)
- [Ghost Recon Wildlands Landscape Pipeline - 80.lv](https://80.lv/articles/landscape-and-material-pipeline-of-ghost-recon-wildlands)
- [URP Decal Renderer Feature](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0/manual/renderer-feature-decal.html)
- [URP Decal Projector Reference (Unity 6)](https://docs.unity3d.com/6000.1/Documentation/Manual/urp/renderer-feature-decal-projector-reference.html)
- [Scalable Real-Time GI for Large Scenes - GDC Vault](https://gdcvault.com/play/1026469/Scalable-Real-Time-Global-Illumination)
- [Level Design Composition - The Level Design Book](https://book.leveldesignbook.com/process/blockout/massing/composition)
- [Mastering Spatial Movement in Game Level Design](https://www.scout.id/mastering-spatial-movement-and-player-pathfinding-in-gaming-level-architecture-environment-layout)
- [GPU-Optimized Terrain Erosion Models](https://www.daydreamsoft.com/blog/gpu-optimized-terrain-erosion-models-for-procedural-worlds-building-hyper-realistic-landscapes-at-scale)
- [Handling Huge Open Worlds in Unity](https://gamedevacademy.org/how-to-handle-huge-worlds-in-unity-part-1-deactivating-distant-regions-to-improve-performance/)
- [Efficient Rendering in The Division 2 - GDC Vault](https://gdcvault.com/play/1026293/Advanced-Graphics-Techniques-Tutorial-Efficient)
