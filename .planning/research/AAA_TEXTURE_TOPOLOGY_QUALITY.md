# AAA Texture, Blending & Topology Quality Research

**Domain:** Procedural PBR material systems in Blender Python (bpy) for dark fantasy game  
**Researched:** 2026-04-03  
**Overall Confidence:** HIGH (verified against Blender docs, Adobe PBR Guide, physicallybased.info, industry practice)

---

## 1. Highest Quality Terrain Textures

### How AAA Games Create Photorealistic Terrain

AAA terrain texturing is built on **layered PBR splatmaps** with 4-8 material channels blended per tile. The key insight: it is NOT one texture stretched across terrain. It is multiple tiled materials blended by splatmap weights, with macro variation breaking repetition.

**The AAA terrain texture pipeline:**

1. **Base Layer:** 4-channel splatmap (RGBA) where each channel weights a different tiled PBR material (grass/rock/dirt/snow)
2. **Height-Based Blending:** Instead of linear alpha blending between materials, use the height map of each material to determine which "pokes through" -- rocks poke through grass, pebbles poke through mud
3. **Macro Variation:** Large-scale (50-200m) Perlin noise modulating hue/value/saturation by +/-10% to break visible tiling patterns
4. **Micro Detail:** Per-material detail normal maps at 2-4x the base tiling rate, adding pore-level detail (pebble surfaces, individual dirt grains, grass blade ridges)
5. **Distance Blending:** Switch from detail tiling to macro tiling at camera distance, preventing moire patterns

### Multi-Layer PBR with Micro-Detail

**Three-frequency normal chain** (already partially implemented in `procedural_materials.py`):

| Layer | Scale | Detail Type | Bump Distance | Purpose |
|-------|-------|-------------|---------------|---------|
| Micro | 40-80x base | Noise (high detail=12) | 0.001-0.003 | Pores, grain, scratches |
| Meso | 10-20x base | Voronoi 3D | 0.003-0.008 | Cracks, veins, cell patterns |
| Macro | 2-5x base | Noise (low detail=4) | 0.01-0.03 | Large undulations, worn areas |

**Enhancement over current implementation:** Add a 4th layer for **object-space curvature** using the Geometry node's Pointiness output to drive edge highlighting and cavity darkening. This gives materials awareness of the mesh they sit on.

### Parallax Occlusion Mapping

POM is NOT natively supported in Blender's Principled BSDF. For game export to Unity URP, POM must be implemented in the Unity shader, not Blender. In Blender, use **real displacement** (Cycles Adaptive Subdivision) for previewing, then bake to normal+height maps for Unity.

**For procedural Blender workflow:**
- Use Bump nodes for preview (fast, no geometry change)
- Use Displacement node on Material Output for final bake (requires Cycles + Adaptive Subdivision)
- Bake height map separately for Unity POM shader consumption

### Macro Variation (Breaking Tiling)

**The single most important technique for photorealistic terrain:**

```
Technique: Multi-octave noise overlay
- Create a large-scale Noise Texture (Scale 0.5-2.0, Detail 2-3)
- Use it to shift base color HSV by small amounts (+/- 0.05 value, +/- 0.02 saturation)
- Apply as multiplicative overlay on the base albedo
- Result: no two 10m patches look identical even with same tiling texture
```

**Stochastic texturing** (random rotation/offset per cell) is the gold standard but requires shader-level implementation in Unity. For Blender procedural generation, use Voronoi-cell-based UV offsets to approximate this.

### Blender Node Setups for Specific Terrain Types

#### Forest Floor (dark_leaf_litter, forest_soil)
```
Nodes: 3x Noise Texture (different scales) + Voronoi (leaf shapes)
- Noise 1 (Scale 15, Detail 8): base soil variation
- Noise 2 (Scale 40, Detail 12): micro grain detail  
- Noise 3 (Scale 3, Detail 4): macro color patches
- Voronoi (Scale 8, Randomness 1.0): scattered leaf/debris shapes
- Color: Mix dark brown base with Voronoi-masked slightly lighter patches
- Roughness: 0.85-0.95 (very rough, organic debris)
- Normal: 3-layer chain, meso uses Voronoi Distance for leaf edges
```

#### Rocky Cliff (exposed_rock, layered_sedimentary)
```
Nodes: Wave Texture (bands) + Noise (surface) + Voronoi (cracks)
- Wave Texture (Bands, Scale 3, Distortion 4): sedimentary layering
- Noise (Scale 8, Detail 10): surface roughness variation
- Voronoi (Scale 12, Crackle): crack network
- Color: Wave drives subtle color banding (dark/light stone alternation)
- Roughness: 0.75-0.90 (rough but some smooth faces)
- Normal: Strong meso (1.2-1.8) for crack depth, wave-driven macro
```

#### Muddy Riverbank (black_mud, murky_green)
```
Nodes: Noise (mud texture) + Wave (water ripple marks) + Voronoi (dried cracks)
- Primary Noise (Scale 6, Detail 6): mud surface
- Wave (Scale 2, Distortion 8): dried ripple marks in mud
- Voronoi (Scale 10, F2-F1 for Crackle): dried mud crack patterns
- Color: Very dark (0.04-0.09 value), slight green/brown shift
- Roughness: 0.30-0.50 (wet mud is somewhat reflective)
- Normal: moderate, emphasize crackle network
- CRITICAL: Wet mud roughness is LOW (0.1-0.3), dry mud is HIGH (0.8-0.95)
```

#### Packed Dirt Path (rubble_dirt, gravel)
```
Nodes: Noise (compacted surface) + Voronoi (embedded pebbles)
- Noise (Scale 12, Detail 8): packed surface texture
- Voronoi (Scale 20, Randomness 0.8): individual pebble shapes
- Color Ramp on Voronoi: select pebble tops vs gaps
- Color: medium-dark earth tones (0.12-0.18 value)
- Roughness: 0.85-0.95 (very rough)
- Normal: Voronoi bumps for pebbles (strength 0.8-1.2)
```

#### Snowy Peak (snow_patches, ice, frozen_edge)
```
Nodes: Noise (snow surface) + Voronoi (ice crystal facets)
- Noise (Scale 8, Detail 4): gentle snow surface undulation
- Voronoi (Scale 30, Smooth F1): subsurface ice crystal sparkle
- Color: 0.40-0.50 value (snow is NOT white=1.0, it is medium-light gray)
- Roughness: 0.5-0.7 for fresh snow (surprisingly rough due to crystal facets)
-          0.05-0.15 for ice (very smooth, reflective)
- Subsurface: Enable Subsurface for snow (weight 0.1-0.2, radius (0.5,0.3,0.2))
- CRITICAL: Snow base color should be ~0.42-0.48, NOT bright white
```

### Export to Unity URP

**What survives export:**
- Base Color texture (bake from Blender procedural nodes)
- Normal map (bake from Bump chain)
- Roughness map (bake)
- Metallic map (bake -- will be mostly black for terrain)
- Height map (bake for Unity POM/tessellation)
- AO map (bake)

**What does NOT survive:**
- Blender node graphs themselves (Unity cannot read .blend shader trees)
- Procedural noise parameters (must be baked to image)
- Multi-layer bump chains (flattened to single normal map)

**Bake resolution guidelines:**
| Surface Type | Bake Resolution | Reason |
|-------------|----------------|--------|
| Terrain tiles (2m) | 1024x1024 | Viewed from distance |
| Building walls | 2048x2048 | Close inspection |
| Props/weapons | 1024x1024 | Small objects |
| Hero assets | 4096x4096 | Player character, key items |

---

## 2. Texture Blending/Meshing Techniques

### Height-Based Blending (CRITICAL -- This Is What Separates AAA from Indie)

Standard alpha blending creates mushy transitions where materials mix as linear gradients. Height-based blending uses each material's height map to determine which material is "on top" at any given blend region.

**Algorithm (implement in bpy vertex color painting or Unity shader):**

```python
def height_blend(weight_a, height_a, weight_b, height_b, blend_sharpness=0.1):
    """AAA height-based material blending.
    
    weight_a/b: splatmap weights (0-1) from vertex colors
    height_a/b: per-texel height from material height maps
    blend_sharpness: lower = sharper transitions (0.05-0.2)
    """
    ha = height_a + weight_a
    hb = height_b + weight_b
    ma = max(ha, hb) - blend_sharpness
    
    ba = max(ha - ma, 0.0)
    bb = max(hb - ma, 0.0)
    total = ba + bb + 0.0001  # avoid div by zero
    
    return ba / total, bb / total  # final blend weights
```

**Result:** Rocks poke through grass realistically. Grass fills gaps between stones. Dirt settles in low areas. This is the single biggest visual quality improvement for terrain materials.

### Slope-Based Blending

Use mesh face normals to automatically assign materials:

| Slope Angle | Material | Rationale |
|-------------|----------|-----------|
| 0-20 degrees | Grass/soil | Flat ground grows vegetation |
| 20-45 degrees | Mixed grass/rock | Transition zone |
| 45-70 degrees | Rock/cliff | Too steep for soil |
| 70-90 degrees | Bare rock/cliff face | Vertical surfaces |

**Implementation in bpy:**

```python
import math
import mathutils

def classify_slope(face_normal, up=mathutils.Vector((0, 0, 1))):
    """Return slope angle in degrees from vertical."""
    dot = face_normal.normalized().dot(up)
    angle_deg = math.degrees(math.acos(max(-1, min(1, dot))))
    return angle_deg

# In vertex color painting loop:
for face in bm.faces:
    angle = classify_slope(face.normal)
    if angle < 20:
        # paint grass (R channel high)
        color = (1.0, 0.0, 0.0, 1.0)
    elif angle < 45:
        # blend grass/rock
        t = (angle - 20) / 25.0
        color = (1.0 - t, t, 0.0, 1.0)
    else:
        # paint rock (G channel high)
        color = (0.0, 1.0, 0.0, 1.0)
```

### Tri-Planar Mapping

**Purpose:** Eliminate UV stretching on vertical cliff faces. Standard UV projection stretches horribly on steep surfaces.

**Blender implementation:** Use the Texture Coordinate node's "Object" output with Box Mapping on Image Texture nodes (Projection: Box, Blend: 0.2-0.4). For procedural textures, use 3D noise (all Noise/Voronoi nodes set to 3D) which inherently avoids UV stretching.

**Key insight for this project:** Since VeilBreakers uses procedural textures (Noise, Voronoi, Wave) rather than image textures, tri-planar mapping is already implicitly handled when using 3D texture coordinates via Object output. The current implementation correctly uses `tex_coord.outputs["Object"]` which provides 3D coordinates.

### Vertex Color Driven Blending

The current terrain system uses RGBA vertex colors for splatmap blending (R=grass, G=rock, B=dirt, A=special). This is the correct approach.

**Enhancement: smooth transitions with noise-displaced boundaries:**

```python
# Instead of sharp vertex-color-based transitions, add noise displacement
# to the boundary between materials:

# In shader nodes:
# 1. Read vertex color (Attribute node, name="splatmap")
# 2. Add Noise Texture (Scale 15, Detail 6) * 0.15 to each channel
# 3. Renormalize channels so they sum to 1.0
# 4. Use displaced channels as material blend weights

# This creates organic, irregular material boundaries instead of
# vertex-resolution blocky transitions
```

### Blending 4+ Materials Without Visible Seams

**The technique: weighted index blending with per-pixel normalization.**

1. Store 4 material weights in RGBA vertex colors
2. At each pixel, compute `weight[i] * height[i]` for each material
3. Take the top 2-3 contributors (discard materials with near-zero weight)
4. Normalize remaining weights to sum to 1.0
5. Blend all PBR channels (color, roughness, normal, AO) using these weights

**For more than 4 materials:** Use a second vertex color layer (Blender supports multiple). Layer 1 RGBA = materials 1-4, Layer 2 RGBA = materials 5-8.

### Transition Zone Techniques

**Noise-displaced boundaries:**
- Add Noise Texture output * 0.1-0.2 to splatmap weights before normalization
- Creates organic, fractal-like material boundaries

**Edge dirt/debris:**
- At transition zones (where two materials have similar weights, e.g., both 0.3-0.5), inject a third "debris" material
- Darkened color, higher roughness, represents accumulated dirt at material boundaries
- Detection: `abs(weight_a - weight_b) < threshold` marks transition zone

**Gradient mapping:**
- Use a ColorRamp with 3+ stops at material boundaries
- Position 0.0: pure material A color
- Position 0.45: material A with slight darkening
- Position 0.50: transition debris color (dark, rough)
- Position 0.55: material B with slight darkening  
- Position 1.0: pure material B color

---

## 3. Model Topology Best Practices

### Optimal Edge Flow for Game-Ready Meshes

**Core rule:** Edges must follow the direction of curvature changes. Every edge loop should serve one of three purposes:
1. **Define silhouette** -- edges that affect the outline of the object
2. **Support deformation** -- edges around joints, hinges, flex points
3. **Hold sharp features** -- edges that maintain creases and hard edges

**If an edge loop does none of these, it is wasted geometry and should be removed.**

### Clean Topology with Low Poly Count

| Asset Type | Triangle Budget | Key Topology Rules |
|-----------|----------------|-------------------|
| Terrain tile (10m) | 500-2000 tris | Regular grid, denser near features |
| Building wall | 50-200 tris | Quads following brick/stone courses |
| Castle tower | 1000-3000 tris | Cylindrical loop cuts at height changes |
| Tree trunk | 200-600 tris | 6-8 sided cylinder, taper toward top |
| Rock (medium) | 100-400 tris | Irregular but quad-dominant |
| Door (deformable) | 200-500 tris | Hinge edge loop, quad flow from frame |
| Flag/cloth | 200-800 tris | Regular grid for cloth sim, denser at attachment |
| Character | 5000-15000 tris | Loops at joints, face topology for expressions |
| Weapon | 500-2000 tris | Hard surface, bevel-supported edges |

### Topology for Deformable Objects

**Doors:** Place a vertical edge loop exactly at the hinge axis. All quads on the door panel should flow perpendicular to the hinge. No triangles near the hinge -- they deform unpredictably.

**Flags/cloth:** Use a regular quad grid (minimum 8x12 subdivisions for a flag). Denser grid at the attachment edge (where stress concentrates). All quads, zero triangles -- cloth simulation requires uniform quad grids.

**Chains:** Each link is a torus with 8-12 segments around the ring, 6-8 segments around the tube. Keep link geometry separate (no merged vertices between links) so they can rotate independently.

### N-gon vs Quad Considerations for Game Export

**Rule:** QUADS for modeling, TRIANGLES for export. Never N-gons in final export.

| Polygon Type | Modeling Phase | Export Phase | Why |
|-------------|---------------|-------------|-----|
| Quads | YES (primary) | Convert to tris | Clean subdivision, predictable deformation |
| Triangles | Only where unavoidable | YES (final) | GPU renders triangles natively |
| N-gons | NEVER in game assets | NEVER | Unpredictable triangulation, normal errors |

**Exception:** Flat, non-deforming surfaces (floors, walls) can tolerate N-gons that get triangulated on export, but it is still better practice to quad them.

### Hard Surface Topology (Castle Walls, Stone Blocks)

**Bevel vs. Edge Crease for sharp edges:**

| Technique | When to Use | Poly Cost | Visual Quality |
|-----------|-------------|-----------|----------------|
| Bevel (geometry) | Hero assets, close-up | +4-8 tris per edge | Best -- real geometry catches light |
| Edge crease + SubSurf | Modeling workflow only | 0 extra tris | Good in Blender, lost on export |
| Normal map baked bevels | All game-ready assets | 0 extra tris | Good -- baked from high-poly |
| Weighted normals | Low-poly hard surface | 0 extra tris | Good -- adjusts face normal weights |

**For VeilBreakers procedural generation:**
- Use 1-segment bevels (chamfers) on sharp edges of buildings and props
- Width: 0.02-0.05m for stone blocks, 0.01-0.02m for wood planks
- This adds minimal geometry but catches specular highlights realistically
- In bpy: `bmesh.ops.bevel(bm, geom=edges, offset=0.03, segments=1)`

### Organic Topology (Trees, Rocks, Terrain Features)

**Trees:** 
- Trunk: 6-sided cylinder base, reduce to 4-sided at top branches
- Branches: 4-sided cylinders with 3-4 loop cuts for bend points
- Leaf clusters: flat quads with alpha-tested leaf textures (billboard approach)
- Root flares: use bmesh extrude from bottom trunk verts

**Rocks:**
- Start with icosphere (2-3 subdivisions = 80-320 faces)
- Apply random vertex displacement (Displace modifier with Noise texture)
- Decimate to target poly count
- Use Weighted Normals modifier before export

**Terrain features:**
- Regular grid base with adaptive density near features
- In bpy: use `bmesh.ops.subdivide_edges()` selectively near rivers, cliffs, paths
- Keep minimum edge length > 0.5m to avoid micro-triangles that waste GPU

### Edge Crease vs Bevel for Sharp Edges in Low-Poly

**Use bevel geometry (1 segment) because:**
1. Edge creases are lost on FBX export (they only affect SubSurf in Blender)
2. Auto-smooth + sharp edges also get lost on export to Unity
3. A single bevel segment adds only 2 triangles per edge but creates real geometry
4. The specular highlight on a beveled edge is the single biggest "quality" signal in hard surface rendering

**In procedural generation:**
```python
import bmesh

# After creating geometry:
bm = bmesh.new()
bm.from_mesh(obj.data)

# Select sharp edges (angle > 30 degrees between faces)
sharp_edges = [e for e in bm.edges if e.calc_face_angle() > math.radians(30)]

# Apply 1-segment bevel
bmesh.ops.bevel(bm, geom=sharp_edges, offset=0.03, segments=1, 
                affect='EDGES', profile=0.5)

bm.to_mesh(obj.data)
bm.free()
```

---

## 4. Procedural Texture Detail

### Micro-Normal Detail (Stone Grain, Wood Fiber, Rust Pitting)

The existing 3-layer normal chain in `procedural_materials.py` covers this well. Specific enhancements:

**Stone grain:** Noise Texture at Scale 60-100, Detail 15, Roughness 0.8. Very fine, very subtle (Bump Strength 0.05-0.15). This is the "sandy" feel of stone surfaces.

**Wood fiber:** Wave Texture at Scale 3-5 (Bands type), with Noise Texture (Scale 80) mixed in at 10% to break the perfect regularity. Bump Strength 0.1-0.2.

**Rust pitting:** Voronoi Texture at Scale 30-50, F2-F1 distance metric. Creates small crater-like pits. Bump Strength 0.3-0.5. Mix with Noise for irregular distribution.

### Procedural Wear/Damage at Edges and Corners (Curvature-Based)

**The Pointiness node** (Geometry > Pointiness in Cycles) detects mesh curvature:
- Convex edges (Pointiness > 0.5): Edge wear, paint chipping, exposed material underneath
- Concave areas (Pointiness < 0.5): Dirt accumulation, moss, darker values

**Implementation pattern:**
```
Geometry Node (Pointiness output)
  -> ColorRamp (position 0.48=black, 0.52=white) -- isolate edges
  -> MixRGB (Fac from ColorRamp):
     Color1: base material color
     Color2: exposed/worn material color (lighter, rougher)
  -> Principled BSDF Base Color

Same mask -> Mix roughness:
  Roughness1: base roughness
  Roughness2: worn roughness (usually higher, more matte)
```

**CRITICAL LIMITATION:** Pointiness requires adequate mesh density. For low-poly game meshes, it may not detect edges well. Solution: **bake Pointiness/curvature to a texture** from a higher-resolution mesh, or use AO baking as a proxy.

**AO Node alternative (works in Eevee too with limitations):**
- AO node with Distance 0.1-0.5 (short range for cavity detection)
- "Inside" checkbox: ON for cavity/crevice detection, OFF for ambient occlusion
- Slower than Pointiness but geometry-density independent

### Dirt Accumulation in Crevices (AO-Driven)

```
AO Node (Inside=True, Distance=0.3)
  -> ColorRamp (0.0=dark_dirt_color, 1.0=transparent)
  -> MixRGB (multiply mode, Fac=0.3-0.5)
  -> into base color chain

Effect: Dark dirt color accumulates in crevices, under overhangs,
in corners where two surfaces meet.

Dark fantasy appropriate dirt colors:
  - Near-black brown: (0.03, 0.02, 0.02)
  - Dark moss:        (0.02, 0.04, 0.02)
  - Corruption grime: (0.04, 0.02, 0.05)
```

### Water Stain / Moss Growth Patterns

**Height + orientation driven:**
```
Separate XYZ (from Object coordinates)
  -> Z component = height
  -> ColorRamp: 0.0-0.3 = water stain zone (low areas)
  
Geometry Normal Y component (or Z in Blender's coord system)
  -> ColorRamp: faces pointing up = moss growth potential
  
Multiply height mask * orientation mask * Noise(Scale 5, Detail 4)
  = final moss/water stain mask

Water stain: darken base color by 20-40%, reduce roughness by 0.1-0.2
Moss: shift color toward (0.06, 0.10, 0.04), increase roughness by 0.1
```

### Making Procedural Textures NOT Look Procedural

**The 7 rules for breaking procedural repetition:**

1. **Multi-scale noise overlay:** Always use at least 3 noise scales (detail, medium, large). Never one.

2. **Non-uniform scaling:** Apply slight random Scale variation (0.8-1.2x) via Object coordinates. Different objects get slightly different texture scales.

3. **Color variation injection:** After computing base color, add per-object random HSV shift (Hue +/-0.02, Sat +/-0.05, Val +/-0.08) using Object Info > Random.

4. **Detail rotation:** Use the Object Info > Random output to rotate the detail noise layer by a random amount per object. The macro pattern stays consistent, but micro detail varies.

5. **Voronoi cell breaking:** For any repeating pattern (bricks, stones, tiles), use Voronoi cells to slightly shift the tiling in each cell region.

6. **Edge-aware variation:** Use Pointiness/AO to drive additional variation at geometric features. Real materials change at edges; procedural ones don't unless you add this.

7. **Imperfection layer:** Always add a faint (5-15% opacity) large-scale Musgrave/Noise overlay that simulates dirt, water marks, or age staining. This is the "it lived in the real world" signal.

---

## 5. PBR Accuracy Rules

### Roughness Reference Values

All values in linear space (0.0=mirror, 1.0=fully diffuse). Based on Allegorithmic PBR Guide, physicallybased.info, and industry consensus.

| Material | Roughness Range | Typical | Notes |
|----------|----------------|---------|-------|
| **Stone (rough)** | 0.75 - 0.95 | 0.85 | Higher for sandstone, lower for granite |
| **Stone (polished)** | 0.15 - 0.40 | 0.25 | Marble, polished granite |
| **Wood (rough/aged)** | 0.60 - 0.90 | 0.80 | Aged timber, bark |
| **Wood (polished)** | 0.20 - 0.45 | 0.30 | Varnished, lacquered |
| **Iron/Steel (clean)** | 0.25 - 0.50 | 0.35 | Forged, machined |
| **Iron (rusted)** | 0.70 - 0.95 | 0.85 | Rust is a dielectric! |
| **Gold** | 0.20 - 0.40 | 0.30 | Polished ornamental |
| **Bronze** | 0.30 - 0.55 | 0.40 | Patinated higher |
| **Copper (patina)** | 0.50 - 0.75 | 0.60 | Green patina is rougher |
| **Water (still)** | 0.00 - 0.05 | 0.02 | Nearly perfect mirror |
| **Water (rippled)** | 0.05 - 0.15 | 0.08 | Normal map adds apparent roughness |
| **Leather** | 0.50 - 0.80 | 0.65 | Tanned lower, raw higher |
| **Cloth (rough)** | 0.80 - 1.00 | 0.90 | Burlap, wool |
| **Cloth (silk)** | 0.30 - 0.50 | 0.40 | Smooth fabrics |
| **Brick** | 0.75 - 0.90 | 0.82 | Similar to rough stone |
| **Concrete** | 0.70 - 0.95 | 0.85 | Polished can be 0.15-0.30 |
| **Soil/dirt** | 0.80 - 0.95 | 0.88 | Wet soil drops to 0.3-0.5 |
| **Grass** | 0.70 - 0.85 | 0.78 | Waxy leaves lower |
| **Snow (fresh)** | 0.50 - 0.70 | 0.60 | Crystal facets scatter light |
| **Ice** | 0.02 - 0.15 | 0.08 | Very smooth, reflective |
| **Glass** | 0.00 - 0.05 | 0.02 | Frosted glass 0.3-0.6 |
| **Mud (wet)** | 0.10 - 0.35 | 0.20 | Highly reflective when wet |
| **Mud (dry)** | 0.80 - 0.95 | 0.88 | Cracked, matte |
| **Bone** | 0.40 - 0.65 | 0.50 | Aged bone is rougher |
| **Wax/candle** | 0.30 - 0.50 | 0.40 | Subsurface scattering applies |
| **Thatch/straw** | 0.85 - 1.00 | 0.92 | Very rough, diffuse |
| **Rope** | 0.75 - 0.90 | 0.82 | Hemp/fiber |

### Metallic Values

**Binary rule:** Metallic is NOT a gradient. It is either 0.0 (dielectric) or 1.0 (conductor).

| Material | Metallic | Rationale |
|----------|----------|-----------|
| Stone, wood, leather, cloth, bone | **0.0** | All dielectrics |
| Soil, grass, snow, ice, water | **0.0** | All dielectrics |
| Brick, concrete, glass, wax | **0.0** | All dielectrics |
| **Rust** | **0.0** | Rust is iron oxide, a DIELECTRIC |
| **Painted metal** | **0.0** | Paint is a dielectric coating |
| **Dirty metal** | **0.0 to 0.3** | Only where bare metal shows through |
| Clean iron, steel, gold, silver | **1.0** | Pure metal conductors |
| Bronze, copper, brass | **1.0** | Metal alloys |
| Chrome, aluminum | **1.0** | Metal |

**Common mistake: making rust metallic.** Rust (iron oxide) is a ceramic/dielectric. Metallic must be 0.0. Only the bare metal underneath (if exposed) should be 1.0. Use a rust mask to blend between metallic=1.0 (bare) and metallic=0.0 (rusted).

**Transition zone (0.0-1.0):** Only valid for partial rust/paint where bare metal shows through at sub-texel resolution. Values of 0.3-0.7 look physically wrong in nearly all cases. Keep transitions sharp (within 2-3 texels).

### Base Color Energy Conservation

**The 30/240 rule (sRGB) or 0.02/0.90 rule (linear):**

| Constraint | sRGB Value | Linear Value | Reason |
|-----------|-----------|-------------|--------|
| Darkest non-metal | 30-50 | 0.02-0.04 | Below this, energy conservation breaks |
| Lightest non-metal | 240 | 0.90 | Above this, too much energy reflected |
| Typical range | 50-200 | 0.04-0.60 | Most real materials fall here |
| Fresh snow | 200-230 | 0.60-0.80 | One of the brightest natural materials |
| Coal/charcoal | 40-50 | 0.02-0.04 | One of the darkest |
| Metal base color | Reflectance color | Varies | Metals use base color for reflectance tint |

**VeilBreakers dark fantasy palette compliance:**
- Environment value range: 10-50% = linear 0.01-0.25 -- well within PBR limits
- The darkest materials (black_mud at 0.04) are at the physical limit; do not go darker
- The lightest (snow at 0.42-0.48) is comfortably within bounds

### Normal Map Intensity Guidelines

| Material | Normal Strength | Rationale |
|----------|----------------|-----------|
| Smooth surfaces (metal, glass) | 0.1 - 0.4 | Subtle surface imperfections only |
| Medium surfaces (wood, leather) | 0.4 - 0.8 | Grain and texture visible |
| Rough surfaces (stone, brick) | 0.8 - 1.5 | Strong surface relief |
| Heavily textured (rubble, bark) | 1.2 - 2.0 | Deep crevices, large features |
| Terrain (macro) | 0.5 - 1.0 | Gentle undulation |
| Terrain (detail) | 0.3 - 0.6 | Pebbles, grass tufts |

**Common mistakes:**
- Normal strength > 2.0 creates unrealistic "plastic wrap" appearance
- Using bump where displacement is needed (bump cannot create silhouette changes)
- Not flipping green channel between DirectX (Unity) and OpenGL (Blender) normal maps

### Common PBR Mistakes That Make Materials Look Wrong

1. **Metallic on non-metals:** Makes materials look like chrome-plated plastic. Rust, painted surfaces, dirty metal -- all should be metallic 0.0.

2. **Roughness too uniform:** Real materials have roughness variation of +/- 10-20%. A stone wall with flat roughness=0.8 everywhere looks like rubber. Add Noise-driven variation.

3. **Base color too saturated:** Real materials are desaturated. A "green" mossy stone is actually (0.08, 0.12, 0.06) not (0.1, 0.5, 0.1). VeilBreakers palette already handles this with the 40% saturation cap.

4. **Base color contains lighting:** Base color/albedo must NOT contain shadows, ambient occlusion, or directional light. Those come from separate maps. If your procedural base color darkens in crevices, you are baking AO into albedo -- incorrect.

5. **Normal strength too high:** Creates a "wet plastic" look. Most materials need 0.5-1.2 strength. Only extreme surfaces (rubble, tree bark) go above 1.5.

6. **No roughness variation between materials:** Different materials on the same object must have different roughness values. A wood frame on a stone wall: wood roughness != stone roughness. Many procedural systems set one roughness for the whole object.

7. **Snow/ice too bright:** Fresh snow is ~0.8 linear at most, not 1.0. Ice is even darker (0.3-0.5) and transparent. Current codebase values (0.42-0.48) are actually well-calibrated.

8. **Ignoring Fresnel:** The Principled BSDF handles Fresnel automatically via the IOR parameter (default 1.5, good for most dielectrics). Do NOT override Specular to 0.0 -- this removes physically correct rim reflections. Leave it at default (0.5 = IOR 1.5).

9. **Wet surface = just lower roughness:** Correct, but also darken base color by 20-40% (wet surfaces absorb more light). And add a clear coat (Coat Weight 0.3-0.6) for the water film on top.

---

## 6. Current Codebase Assessment

### What Is Already Good

1. **3-layer micro/meso/macro normal chain** in `_build_normal_chain()` -- correct approach, well-implemented
2. **Dark fantasy palette** with saturation capping -- physically plausible values
3. **Vertex color splatmap system** (RGBA blending) -- correct architecture
4. **Binary metallic values** -- all materials correctly use 0.0 except metals
5. **Material library** with 45+ presets covering all needed surface types
6. **Per-material roughness variation** -- avoids the "flat roughness" mistake

### What Needs Improvement

1. **No height-based blending** -- terrain transitions use linear alpha blending, not height-based. This is the single biggest quality gap.

2. **No macro variation** -- no large-scale noise overlay to break tiling repetition across terrain. Materials tile identically everywhere.

3. **No curvature-driven wear** -- Pointiness/AO-based edge wear is not implemented. All surfaces have uniform wear regardless of geometry.

4. **No wet surface handling** -- no coat weight for rain/water effects, no roughness reduction for wet areas.

5. **Missing transition debris** -- material boundaries are clean blends with no accumulated dirt/debris at transition zones.

6. **No per-object random variation** -- Object Info > Random not used to break uniformity between instances of same material.

7. **No bevel on procedural geometry** -- hard surface props (buildings, walls) have perfectly sharp edges with no bevels, missing specular highlight.

8. **Terrain normal chain lacks meso detail** -- terrain builder uses simpler normal setup than stone/wood builders.

---

## 7. Implementation Priority for VeilBreakers

### Phase 1: Critical Quality Improvements
1. **Height-based blending** in terrain splatmap system
2. **Macro variation layer** (large Noise overlay on all terrain materials)
3. **1-segment bevels** on procedural building geometry edges

### Phase 2: Visual Polish
4. **Curvature-driven edge wear** using Pointiness + AO
5. **Per-object random variation** via Object Info node
6. **Transition zone debris** at material boundaries
7. **Wet surface handling** (coat weight + darkened base color)

### Phase 3: Export Quality
8. **Texture baking pipeline** (procedural nodes -> image textures for Unity)
9. **Normal map green channel flip** (OpenGL -> DirectX)
10. **Resolution-appropriate baking** per asset type

---

## Sources

- [Physically Based Database](https://physicallybased.info/) -- IOR and reflectance reference values
- [Adobe PBR Guide Part 2](https://substance3d.adobe.com/tutorials/courses/the-pbr-guide-part-2) -- Industry-standard PBR workflow reference
- [Marmoset PBR Guide](https://marmoset.co/posts/physically-based-rendering-and-you-can-too/) -- Material setup best practices
- [Unity Procedural Stochastic Texturing](https://unity.com/blog/engine-platform/procedural-stochastic-texturing-in-unity) -- Tile repetition breaking
- [Advanced Terrain Texture Splatting](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting) -- Height-based blending technique
- [Polycount Topology Wiki](http://wiki.polycount.com/wiki/Topology) -- Game topology standards
- [Blender Procedural Edge Wear (Blender 4.2)](https://www.artstation.com/blogs/jsabbott/rD6Ql/how-to-make-procedural-edge-wear-in-blender-42-tutorial) -- Pointiness/curvature wear technique
- [Tri-planar Mapping in Blender Cycles](https://www.gamedev.net/blogs/entry/2254942-tri-planar-texture-mapping-in-blender-cycles/) -- UV-free texturing
- [CG-Wire Blender Shaders Guide](https://blog.cg-wire.com/blender-shaders-explained/) -- bpy node tree creation
- [Blender Principled BSDF Manual](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html) -- Official Blender docs
- [DONTNOD PBR Chart for UE4](https://seblagarde.wordpress.com/2014/04/14/dontnod-physically-based-rendering-chart-for-unreal-engine-4/) -- Studio-calibrated material values
- [Evolving 3D Model Topology Practices](https://medium.com/@Jamesroha/evolving-3d-model-topology-practices-in-modern-game-development-d81c47ecde3c) -- Modern topology standards
- [Topology for Game-Ready Assets](https://www.gameaningstudios.com/topology-for-game-ready-assets/) -- Industry topology guidelines
