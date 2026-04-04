# AAA Procedural Terrain Texturing Research

**Domain:** Procedural terrain material creation in Blender Python (bpy) for dark fantasy game
**Researched:** 2026-04-03
**Overall Confidence:** HIGH (verified against Blender API docs, current codebase, AAA game techniques)

---

## Executive Summary

The current VeilBreakers terrain material system (`terrain_materials.py` + `procedural_materials.py`) has a solid foundation with 70+ terrain-specific material definitions across 14 biomes, a 3-layer normal chain (micro/meso/macro bump), height-based blend groups, and vertex color splatmap support. However, the actual node tree builders produce "basic paint level" results because they lack the layering complexity that makes AAA terrain materials convincing. Specifically:

1. **Single-BSDF approach** -- each material uses one Principled BSDF with noise overlay. AAA materials blend 2-4 sub-materials using Mix Shader or Mix Color nodes driven by masks.
2. **No height-aware blending in the shader** -- the `HeightBlend` node group exists but is never wired into the terrain material builders.
3. **Missing Voronoi cracking/cell patterns** in terrain (only used in stone). Terrain needs Voronoi for mud cracks, dried earth, pebble scatter.
4. **No displacement** -- all terrain is flat-shaded with bump only. Adding actual displacement via the Material Output's Displacement socket would dramatically improve silhouettes.
5. **Deprecated API** -- `_create_height_blend_group()` uses `group.inputs.new()` which was removed in Blender 4.0. Must use `group.interface.new_socket()`.
6. **No bake pipeline** -- procedural materials cannot survive the Blender-to-FBX-to-Unity pipeline without baking to image textures.

---

## 1. Procedural Material Node Tree Patterns

### 1.1 Multi-Layer Material Architecture (AAA Standard)

AAA terrain materials use a layered architecture, not a single BSDF:

```
Layer 1: Base earth/soil (Principled BSDF #1)
Layer 2: Rock/stone (Principled BSDF #2)
Layer 3: Vegetation/moss (Principled BSDF #3)
Layer 4: Special (snow/corruption/water edge) (Principled BSDF #4)
   |
   v
Mix Shader chain (driven by slope, height, vertex color, noise masks)
   |
   v
Material Output
```

**Implementation pattern in bpy:**

```python
def build_layered_terrain_material(mat, params):
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 800, 0, "Output")
    
    # --- Layer 1: Base earth ---
    bsdf_earth = _add_node(tree, "ShaderNodeBsdfPrincipled", -200, 400, "Earth BSDF")
    bsdf_earth.inputs["Base Color"].default_value = (0.09, 0.07, 0.05, 1.0)
    bsdf_earth.inputs["Roughness"].default_value = 0.92
    
    # --- Layer 2: Rock ---
    bsdf_rock = _add_node(tree, "ShaderNodeBsdfPrincipled", -200, 0, "Rock BSDF")
    bsdf_rock.inputs["Base Color"].default_value = (0.14, 0.12, 0.10, 1.0)
    bsdf_rock.inputs["Roughness"].default_value = 0.85
    
    # --- Layer 3: Moss/vegetation ---
    bsdf_moss = _add_node(tree, "ShaderNodeBsdfPrincipled", -200, -400, "Moss BSDF")
    bsdf_moss.inputs["Base Color"].default_value = (0.06, 0.08, 0.04, 1.0)
    bsdf_moss.inputs["Roughness"].default_value = 0.78
    
    # --- Slope mask (Geometry -> Separate XYZ -> Z -> ColorRamp) ---
    geometry = _add_node(tree, "ShaderNodeNewGeometry", -800, -200, "Geometry")
    sep_xyz = _add_node(tree, "ShaderNodeSeparateXYZ", -600, -200, "Sep Normal")
    links.new(geometry.outputs["Normal"], sep_xyz.inputs["Vector"])
    
    slope_ramp = _add_node(tree, "ShaderNodeValToRGB", -400, -200, "Slope Mask")
    slope_ramp.color_ramp.elements[0].position = 0.4   # cliff threshold
    slope_ramp.color_ramp.elements[1].position = 0.75  # flat threshold
    links.new(sep_xyz.outputs["Z"], slope_ramp.inputs["Fac"])
    
    # --- Mix: Earth + Rock (slope-driven) ---
    mix_earth_rock = _add_node(tree, "ShaderNodeMixShader", 200, 200, "Earth/Rock Mix")
    links.new(slope_ramp.outputs["Color"], mix_earth_rock.inputs["Fac"])
    links.new(bsdf_earth.outputs["BSDF"], mix_earth_rock.inputs[1])
    links.new(bsdf_rock.outputs["BSDF"], mix_earth_rock.inputs[2])
    
    # --- Mix: Result + Moss (noise-driven patches) ---
    moss_noise = _add_node(tree, "ShaderNodeTexNoise", -600, -600, "Moss Noise")
    moss_noise.inputs["Scale"].default_value = 3.0
    moss_noise.inputs["Detail"].default_value = 6.0
    
    moss_ramp = _add_node(tree, "ShaderNodeValToRGB", -400, -600, "Moss Mask")
    moss_ramp.color_ramp.elements[0].position = 0.55
    moss_ramp.color_ramp.elements[1].position = 0.65
    links.new(moss_noise.outputs["Fac"], moss_ramp.inputs["Fac"])
    
    mix_final = _add_node(tree, "ShaderNodeMixShader", 400, 0, "Final Mix")
    links.new(moss_ramp.outputs["Color"], mix_final.inputs["Fac"])
    links.new(mix_earth_rock.outputs["Shader"], mix_final.inputs[1])
    links.new(bsdf_moss.outputs["BSDF"], mix_final.inputs[2])
    
    links.new(mix_final.outputs["Shader"], output.inputs["Surface"])
```

**Why Mix Shader over Mix RGB:** Mix Shader blends the entire BSDF response (specular, roughness, normal) per-layer. Mix RGB only blends colors and requires manually mixing every other channel. For performance-critical game baking, Mix RGB on a single BSDF is acceptable since the final output is baked textures anyway.

### 1.2 Noise Texture Types and When to Use Each

Since Blender 4.1, Musgrave Texture was merged into Noise Texture with a `noise_type` property.

| Noise Type | Best For | Key Params | Visual Character |
|------------|----------|------------|------------------|
| `fBM` (default) | General terrain variation, grass, soil | Detail 6-12, Roughness 0.5-0.7 | Smooth, organic, homogeneous |
| `MULTIFRACTAL` | Rocky terrain, uneven ground | Detail 8-16, Roughness 0.6-0.8 | Varied, localized detail |
| `RIDGED_MULTIFRACTAL` | Mountain ridges, cracked earth | Detail 4-8, Roughness 0.4-0.6 | Sharp ridges, dramatic terrain |
| `HYBRID_MULTIFRACTAL` | Mixed terrain, natural coastlines | Detail 6-12, Roughness 0.5-0.7 | Mix of smooth and rough |
| `HETERO_TERRAIN` | Erosion patterns, river channels | Detail 4-8, Roughness 0.3-0.6 | Height-dependent variation |

**Blender 4.1+ Noise Texture with Musgrave types:**
```python
noise = _add_node(tree, "ShaderNodeTexNoise", x, y, "Terrain Noise")
noise.noise_type = 'MULTIFRACTAL'  # was separate Musgrave node pre-4.1
noise.inputs["Scale"].default_value = 4.0
noise.inputs["Detail"].default_value = 10.0  # subtract 1 from old Musgrave Detail
noise.inputs["Roughness"].default_value = 0.65
noise.inputs["Lacunarity"].default_value = 2.0
# Note: Dimension -> Roughness conversion: Roughness = Lacunarity^(-Dimension)
```

### 1.3 Voronoi for Natural Patterns

Voronoi is essential for:
- **Cracked mud/dried earth:** `voronoi.feature = 'F1'`, scale 8-15, connect Distance output to ColorRamp
- **Pebble scatter:** `voronoi.feature = 'F2'`, subtract F1 for cell edges
- **Rock faces/cliff structure:** `voronoi.feature = 'F1'`, scale 3-6, 3D mode
- **Cobblestone patterns:** `voronoi.feature = 'F1'`, scale 5-10

```python
voronoi = _add_node(tree, "ShaderNodeTexVoronoi", x, y, "Crack Pattern")
voronoi.voronoi_dimensions = '3D'
voronoi.feature = 'F1'  # F1 = distance to nearest, F2 = distance to second nearest
voronoi.distance = 'EUCLIDEAN'
voronoi.inputs["Scale"].default_value = 12.0
voronoi.inputs["Randomness"].default_value = 1.0
# Distance output -> ColorRamp -> cracks are where Distance is near 0
```

### 1.4 Micro-Detail Layers

AAA materials use 3+ frequency octaves of detail. The current `_build_normal_chain` does this for normals but NOT for color or roughness:

| Scale | Name | What It Adds | Noise Scale |
|-------|------|--------------|-------------|
| Macro (1x) | Terrain variation | Large color patches, biome transitions | 0.5-3 |
| Meso (4-8x) | Surface character | Rock chunks, grass clumps, dirt patches | 4-15 |
| Micro (20-60x) | Fine detail | Grain, pores, individual pebbles, leaf bits | 20-80 |

**Each frequency octave should affect:**
- Base Color (subtle tint variation)
- Roughness (wet/dry patches)
- Normal/Bump (surface detail)

### 1.5 Weathering and Aging

Weathering is what separates AAA from basic. Key techniques:

**Edge wear (Pointiness/AO-based):**
```python
# In Blender, use Geometry -> Pointiness for edge detection
# Or bake AO to vertex colors and use as wear mask
geometry = _add_node(tree, "ShaderNodeNewGeometry", x, y, "Geo")
# Pointiness output: high = convex edges, low = concave
ramp = _add_node(tree, "ShaderNodeValToRGB", x+200, y, "Wear Ramp")
ramp.color_ramp.elements[0].position = 0.45
ramp.color_ramp.elements[1].position = 0.55
links.new(geometry.outputs["Pointiness"], ramp.inputs["Fac"])
# Use ramp output to darken color and increase roughness at edges
```

**Moisture/dampness gradient (height-based):**
```python
# Object Info -> Position Z -> ColorRamp
# Lower areas = more moisture = lower roughness, darker color
obj_info = _add_node(tree, "ShaderNodeObjectInfo", x, y, "Obj Info")
# Or use Geometry -> Position for world-space height
```

**Moss/lichen accumulation (top-facing + noise):**
```python
# Combine: slope mask (Z > 0.7 = top-facing) * noise mask
# Result drives moss color overlay and roughness change
```

---

## 2. Terrain Texture Blending

### 2.1 Vertex Color Splatmap (Current System)

The current system in `blend_terrain_vertex_colors()` is correct in concept: R=grass, G=rock, B=dirt, A=special. However, the shader side needs to actually READ these vertex colors:

```python
# In the material node tree:
vertex_color = _add_node(tree, "ShaderNodeVertexColor", x, y, "Splatmap")
vertex_color.layer_name = "terrain_splat"  # must match the color layer name

# Separate RGB to get individual channel masks
sep_rgb = _add_node(tree, "ShaderNodeSeparateColor", x+200, y, "Sep Channels")
sep_rgb.mode = 'RGB'
links.new(vertex_color.outputs["Color"], sep_rgb.inputs["Color"])

# sep_rgb.outputs["Red"]   -> grass weight
# sep_rgb.outputs["Green"] -> rock weight
# sep_rgb.outputs["Blue"]  -> dirt weight
# vertex_color.outputs["Alpha"] -> special weight
```

### 2.2 Height-Based Blending (Physical Transitions)

Linear interpolation between terrain layers looks artificial. Height-based blending makes grass fill cracks in rock and dirt sit in low points:

**The principle:** Instead of `lerp(A, B, mask)`, use `lerp(A, B, clamp((heightA - heightB) * contrast + mask))`. This makes the "taller" texture poke through first.

The existing `_create_height_blend_group()` implements this correctly but:
1. Uses deprecated `group.inputs.new()` API (must migrate to `group.interface.new_socket()`)
2. Is never called by any material builder

**Fix: Migrate to Blender 4.0+ API:**
```python
# OLD (broken in Blender 4.0+):
group.inputs.new("NodeSocketFloat", "Height_A")

# NEW (Blender 4.0+):
group.interface.new_socket(
    name="Height_A",
    socket_type="NodeSocketFloat",
    in_out="INPUT"
)
```

### 2.3 Biome Transition Blending

For smooth biome transitions (forest -> swamp, grassland -> mountain):

| Transition Type | Technique | Width |
|----------------|-----------|-------|
| Sharp (cliff edge) | Step function via ColorRamp, 2 stops close together | 0.5-2m |
| Smooth (biome edge) | Gradient via noise-modulated lerp | 5-20m |
| Organic (shoreline) | Fractal noise mask + height blend | 3-10m |
| Path integration | World-space distance from path spline, noise-perturbed | 1-3m |

**Shoreline transition recipe (water -> mud -> grass):**
```python
# 1. Height relative to water level drives primary blend
# 2. Noise perturbation prevents straight lines
# 3. Three zones: underwater (water shader), muddy (wet dirt, low roughness),
#    dry (grass/earth, high roughness)

# Height zones:
# Z < water_level - 0.1 : full water
# Z = water_level +/- 0.3 : mud/wet zone (roughness 0.2-0.5)
# Z > water_level + 0.5 : dry terrain (roughness 0.8-0.95)
```

### 2.4 Path/Road Material Integration

Roads should blend naturally into surrounding terrain:

```python
# Technique: Use a separate vertex color channel or object attribute
# to mark "road proximity" on each vertex

# In node tree:
# 1. Read road_mask from vertex color or UV channel
# 2. Noise-perturb the mask edges for organic boundary
# 3. Mix road material (packed earth/cobblestone) with terrain material
# 4. Add edge detail: grass tufts at road edges, mud in wheel ruts

road_mask = _add_node(tree, "ShaderNodeVertexColor", x, y, "Road Mask")
road_mask.layer_name = "road_weight"

# Perturb edges with noise for natural look
edge_noise = _add_node(tree, "ShaderNodeTexNoise", x, y-200, "Edge Noise")
edge_noise.inputs["Scale"].default_value = 8.0

# Math: mask + (noise - 0.5) * 0.15  -> perturbed mask
perturb = _add_node(tree, "ShaderNodeMath", x+200, y-100, "Perturb")
perturb.operation = "ADD"
```

---

## 3. Dark Fantasy Material Recipes

All colors follow VeilBreakers palette rules: environment saturation <= 40%, value range 10-50%.

### 3.1 Forest Floor (Thornwood)

**Layers:**
1. **Dark humus base** -- (0.06, 0.05, 0.03) R0.94 -- fBM noise scale 6, detail 8
2. **Leaf litter scatter** -- (0.10, 0.07, 0.04) R0.88 -- Voronoi F1 scale 15 for individual leaf shapes
3. **Twig/root detail** -- (0.12, 0.08, 0.05) R0.85 -- Wave Texture at oblique angle for linear shapes
4. **Moss patches** -- (0.05, 0.07, 0.03) R0.78 -- Low-frequency noise (scale 2) for large patches

**Key node setup:**
- Use `HETERO_TERRAIN` noise type for the base -- gives natural height-dependent variation
- Voronoi `F2 - F1` for leaf edges visible on the ground
- Multiply a separate noise channel into roughness for wet/dry patches
- Normal strength: 0.8-1.2 for macro, 0.4-0.6 for meso, 0.2-0.3 for micro

### 3.2 Rocky Highland

**Layers:**
1. **Gray stone base** -- (0.16, 0.15, 0.13) R0.86 -- Voronoi F1 scale 4 for rock faces
2. **Lichen patches** -- (0.12, 0.14, 0.08) R0.80 -- Low noise scale 1.5 with sharp ColorRamp cutoff
3. **Sparse grass tufts** -- (0.07, 0.09, 0.05) R0.82 -- Noise scale 8 with high threshold (0.7+)
4. **Exposed gravel** -- (0.20, 0.18, 0.16) R0.92 -- High-frequency noise (scale 30) for grain

**Key technique:**
- `RIDGED_MULTIFRACTAL` noise for the rock surface -- creates natural ridge/crack patterns
- Slope mask drives rock vs sparse grass: slopes > 45 degrees = pure rock
- Height mask: higher elevation = more exposed stone, less vegetation

### 3.3 Swamp/Marshland (Corrupted Swamp)

**Layers:**
1. **Dark mud base** -- (0.04, 0.03, 0.03) R0.45 -- Very low roughness for wet appearance
2. **Standing water patches** -- (0.03, 0.04, 0.03) R0.08 -- Near-mirror roughness, slight green tint
3. **Dead vegetation debris** -- (0.08, 0.06, 0.04) R0.85 -- Scattered via high-threshold noise
4. **Corruption tint** -- (0.08, 0.04, 0.10) R0.70 -- Purple overlay via emission at very low strength (0.05)

**Key technique:**
- Low roughness is critical -- swamp surfaces are WET. Base roughness 0.3-0.5, water pools 0.05-0.15
- Use `MULTIFRACTAL` for organic, unpredictable surface
- Voronoi cracking for dried mud at edges where mud meets drier ground
- Subtle emission (strength 0.02-0.05) with purple tint for corruption zones

### 3.4 Castle Stone (Weathered)

**Layers:**
1. **Cut stone blocks** -- (0.15, 0.13, 0.11) R0.88 -- Voronoi F1 scale 3-5 for block pattern
2. **Mortar lines** -- (0.08, 0.07, 0.06) R0.95 -- Inverted Voronoi distance, narrow threshold
3. **Moss in cracks** -- (0.06, 0.08, 0.04) R0.75 -- Voronoi distance (low values = cracks) * noise
4. **Surface weathering** -- Darken via Overlay blend with low-frequency noise

**Key technique:**
- Voronoi `F1` at scale 3-5 creates convincing stone block patterns
- The Distance output through a steep ColorRamp creates mortar lines
- Moss grows WHERE mortar is + WHERE surface faces up: `mortar_mask * slope_up_mask * noise`
- Edge wear via Pointiness: convex edges get lighter (worn stone), concave get darker (dirt/moss)

### 3.5 Dirt Paths

**Layers:**
1. **Packed earth** -- (0.14, 0.11, 0.07) R0.88 -- Smooth, compressed surface
2. **Cart rut tracks** -- (0.10, 0.08, 0.05) R0.60 -- Lower, wetter, parallel lines via Wave Texture
3. **Puddle patches** -- (0.06, 0.05, 0.04) R0.10 -- Very low roughness in depressions
4. **Edge grass intrusion** -- (0.07, 0.09, 0.05) R0.82 -- At path borders only

**Key technique:**
- Wave Texture with `bands_direction = 'X'` for cart tracks (parallel lines)
- Height-based puddles: depressions (low noise areas) get low roughness
- Path edges use the road_mask vertex color, inverted and noise-perturbed

### 3.6 River Banks

**Layers:**
1. **Wet mud** -- (0.06, 0.05, 0.04) R0.25 -- Near water, very smooth/wet
2. **Pebbles** -- (0.18, 0.16, 0.14) R0.80 -- Voronoi F1 scale 20 for individual pebbles
3. **Transition grass** -- (0.06, 0.08, 0.04) R0.78 -- Above waterline
4. **Waterline foam** -- (0.22, 0.22, 0.24) R0.30 -- Thin band at exact water level

**Key technique:**
- Height relative to water_level is the primary driver
- Pebble pattern: Voronoi F1 at high scale (20-30), each cell = one pebble
- Roughness gradient: 0.15 at waterline -> 0.90 at dry ground (smooth linear transition over 0.3m)

---

## 4. Tree and Vegetation Materials

### 4.1 Bark Textures

**Node setup for convincing bark:**
```python
# Base pattern: Noise Texture (RIDGED_MULTIFRACTAL) stretched in Y
# This creates vertical ridge patterns characteristic of bark

mapping = _add_node(tree, "ShaderNodeMapping", x, y, "Bark Mapping")
mapping.inputs["Scale"].default_value = (1.0, 3.0, 1.0)  # stretch Y for vertical ridges

bark_noise = _add_node(tree, "ShaderNodeTexNoise", x+200, y, "Bark Ridges")
bark_noise.noise_type = 'RIDGED_MULTIFRACTAL'
bark_noise.inputs["Scale"].default_value = 8.0
bark_noise.inputs["Detail"].default_value = 12.0

# Secondary: Voronoi for bark plate structure
bark_plates = _add_node(tree, "ShaderNodeTexVoronoi", x+200, y-200, "Bark Plates")
bark_plates.inputs["Scale"].default_value = 4.0
bark_plates.feature = 'F1'

# Overlay blend: ridges + plates
mix = _add_node(tree, "ShaderNodeMixRGB", x+400, y, "Bark Mix")
mix.blend_type = "OVERLAY"
mix.inputs["Fac"].default_value = 0.4
```

**Bark variety per tree species:**

| Tree Type | Base Color | Roughness | Pattern | Dark Fantasy Notes |
|-----------|-----------|-----------|---------|-------------------|
| Oak (twisted) | (0.10, 0.07, 0.04) | 0.92 | Deep ridges, plate-like | Darkened, moss in crevices |
| Birch (dead) | (0.20, 0.19, 0.17) | 0.85 | Smooth with horizontal lines | Peeling, gray-white, diseased |
| Pine (corrupted) | (0.08, 0.05, 0.03) | 0.88 | Tight vertical ridges | Black sap, purple tint at base |
| Dead/hollow | (0.06, 0.05, 0.04) | 0.95 | Cracked, irregular | Holes, fungal growths, gray |

### 4.2 Leaf Materials with Subsurface Scattering

Leaves MUST have subsurface scattering to look real. Without SSS, leaves appear plastic.

```python
bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", x, y, "Leaf BSDF")
bsdf.inputs["Base Color"].default_value = (0.04, 0.06, 0.02, 1.0)  # dark green
bsdf.inputs["Roughness"].default_value = 0.5

# SSS for light transmission through leaves
sss_input = _get_bsdf_input(bsdf, "Subsurface Weight")
if sss_input is not None:
    sss_input.default_value = 0.3  # 30% subsurface

sss_radius = bsdf.inputs.get("Subsurface Radius")
if sss_radius is not None:
    sss_radius.default_value = (0.5, 0.8, 0.3)  # green-biased transmission

sss_scale = bsdf.inputs.get("Subsurface Scale")
if sss_scale is not None:
    sss_scale.default_value = 0.005  # thin leaf

# Alpha for leaf shape (use noise or image)
bsdf.inputs["Alpha"].default_value = 0.0  # will be driven by texture
```

**Dark fantasy leaf variations:**

| Type | SSS Weight | SSS Color Bias | Base Color | Notes |
|------|-----------|---------------|-----------|-------|
| Healthy (rare) | 0.3 | Green (0.5, 0.8, 0.3) | (0.04, 0.06, 0.02) | Only in protected areas |
| Dying | 0.15 | Yellow-brown (0.6, 0.4, 0.2) | (0.08, 0.06, 0.03) | Most common |
| Dead | 0.05 | Brown (0.5, 0.3, 0.2) | (0.10, 0.07, 0.04) | Crispy, high roughness 0.95 |
| Corrupted | 0.2 | Purple (0.4, 0.2, 0.6) | (0.06, 0.03, 0.07) | Purple SSS, dark base |

### 4.3 Seasonal/Corruption Variation

Drive variation with a single "corruption_factor" parameter (0.0 = healthy, 1.0 = fully corrupted):

```python
# Interpolate all material properties based on corruption_factor
corruption = params.get("corruption_factor", 0.0)

# Base color shifts from green toward gray-purple
base_r = lerp(0.04, 0.08, corruption)
base_g = lerp(0.06, 0.03, corruption)
base_b = lerp(0.02, 0.06, corruption)

# SSS shifts from green to purple
sss_r = lerp(0.5, 0.4, corruption)
sss_g = lerp(0.8, 0.2, corruption)
sss_b = lerp(0.3, 0.6, corruption)

# Roughness increases (dying leaves are drier)
roughness = lerp(0.5, 0.92, corruption)
```

---

## 5. Performance and Export Pipeline

### 5.1 Node Complexity Budget

| Material Type | Max Nodes | Max Noise/Voronoi | Render Impact |
|---------------|-----------|-------------------|---------------|
| Terrain (large area) | 40-60 | 4-6 texture nodes | HIGH -- bake required |
| Building surface | 30-50 | 3-5 texture nodes | MEDIUM -- bake for game |
| Prop/small object | 20-35 | 2-4 texture nodes | LOW -- can keep simpler |
| Vegetation (instanced) | 15-25 | 2-3 texture nodes | CRITICAL -- bake always |

**Rule of thumb:** Voronoi 3D is roughly 3x more expensive than Noise Texture. Use 2D Voronoi when 3D is not needed (flat terrain surfaces).

### 5.2 When to Bake vs Keep Procedural

**Always bake for game export (Unity pipeline):**
- Procedural node trees DO NOT survive Blender -> FBX -> Unity
- FBX format only carries image texture references, not node graphs
- Unity's Standard/URP/HDRP shaders expect image maps

**Keep procedural for:**
- Blender-side preview and iteration
- Contact sheet renders for visual QA
- Seed-based variation (different seeds = different terrain)

### 5.3 Bake Pipeline (Python)

```python
def bake_terrain_material(obj, resolution=2048):
    """Bake procedural terrain material to image textures for game export."""
    
    # 1. Ensure Cycles renderer (only renderer that supports baking)
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 16  # low samples OK for baking
    
    # 2. Create target images
    maps = {
        'diffuse': bpy.data.images.new(f"{obj.name}_diffuse", resolution, resolution),
        'normal': bpy.data.images.new(f"{obj.name}_normal", resolution, resolution,
                                        is_data=True),
        'roughness': bpy.data.images.new(f"{obj.name}_roughness", resolution, resolution,
                                          is_data=True),
        'metallic': bpy.data.images.new(f"{obj.name}_metallic", resolution, resolution,
                                         is_data=True),
    }
    
    # 3. For each map: add Image Texture node, select it, bake
    mat = obj.active_material
    nodes = mat.node_tree.nodes
    
    for map_name, image in maps.items():
        # Add image texture node (NOT connected to anything)
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.image = image
        img_node.select = True
        nodes.active = img_node
        
        # Configure bake type
        if map_name == 'diffuse':
            bpy.context.scene.cycles.bake_type = 'DIFFUSE'
            bpy.context.scene.render.bake.use_pass_direct = False
            bpy.context.scene.render.bake.use_pass_indirect = False
            bpy.context.scene.render.bake.use_pass_color = True
        elif map_name == 'normal':
            bpy.context.scene.cycles.bake_type = 'NORMAL'
        elif map_name == 'roughness':
            bpy.context.scene.cycles.bake_type = 'ROUGHNESS'
        elif map_name == 'metallic':
            # No direct metallic bake -- use EMIT with metallic isolated
            bpy.context.scene.cycles.bake_type = 'EMIT'
        
        # Bake
        bpy.ops.object.bake(type=bpy.context.scene.cycles.bake_type)
        
        # Save
        image.filepath_raw = f"//textures/{obj.name}_{map_name}.png"
        image.file_format = 'PNG'
        image.save()
        
        # Remove temp node
        nodes.remove(img_node)
```

### 5.4 Unity Material Mapping

| Blender Property | Unity URP Property | Notes |
|-----------------|-------------------|-------|
| Base Color | Base Map (albedo) | Direct 1:1 |
| Roughness | Smoothness | **INVERT**: Smoothness = 1 - Roughness |
| Metallic | Metallic Map | Packed into alpha of Metallic map |
| Normal | Normal Map | Must set texture import as "Normal map" in Unity |
| Bump/Height | Height Map | Optional, for parallax |
| Emission | Emission Map | Direct 1:1 |

**Critical:** Unity packs Metallic into R channel and Smoothness into A channel of the same texture. The bake pipeline should produce a combined MetallicSmoothness map.

### 5.5 Texture Atlas Strategy

For terrain with multiple biome materials on one mesh:

1. **UV atlas packing:** All terrain chunks share one UV space, bake all materials into one atlas
2. **Resolution:** 4096x4096 for terrain atlas (covers ~100x100m at ~2.4 texels/cm)
3. **Channel packing:** Pack metallic(R) + AO(G) + height(B) + smoothness(A) into one RGBA texture
4. **LOD textures:** Generate mip levels: 4096 (LOD0), 2048 (LOD1), 1024 (LOD2)

---

## 6. Critical Bugs and Migration Items

### 6.1 Deprecated API in _create_height_blend_group

**File:** `terrain_materials.py` lines 1560-1578
**Bug:** Uses `group.inputs.new()` and `group.outputs.new()` which were removed in Blender 4.0
**Fix:** Replace with `group.interface.new_socket()`:

```python
# BEFORE (broken):
group.inputs.new("NodeSocketFloat", "Height_A")
group.outputs.new("NodeSocketFloat", "Result")

# AFTER (Blender 4.0+):
group.interface.new_socket(
    name="Height_A", socket_type="NodeSocketFloat", in_out="INPUT"
)
group.interface.new_socket(
    name="Result", socket_type="NodeSocketFloat", in_out="OUTPUT"
)
```

Also need to update default value setting -- in the new API, socket defaults are set via the socket object returned by `new_socket()`:
```python
socket = group.interface.new_socket(name="Mask", socket_type="NodeSocketFloat", in_out="INPUT")
socket.default_value = 0.5
socket.min_value = 0.0
socket.max_value = 1.0
```

### 6.2 HeightBlend Group Never Used

The `_create_height_blend_group()` function exists but is never called by any material builder. It should be integrated into `build_terrain_material()` for physical blending.

### 6.3 Terrain Builder Lacks Layer Blending

`build_terrain_material()` creates a single BSDF with noise overlay. It does NOT:
- Read vertex colors for splatmap blending
- Mix multiple sub-materials
- Use the slope mask to drive material choice (only drives roughness)
- Apply height-based blending between layers

### 6.4 No Displacement Output

No terrain material connects to the Displacement socket of Material Output. Adding displacement would improve terrain silhouettes in renders/previews:

```python
# Add displacement
disp = _add_node(tree, "ShaderNodeDisplacement", 600, -200, "Displacement")
disp.inputs["Scale"].default_value = 0.05
disp.inputs["Midlevel"].default_value = 0.5
links.new(noise_output, disp.inputs["Height"])
links.new(disp.outputs["Displacement"], output.inputs["Displacement"])
```

---

## 7. Recommended Upgrade Path

### Phase 1: Fix Critical Bugs
1. Migrate `_create_height_blend_group` to Blender 4.0+ API
2. Wire HeightBlend into terrain material builder
3. Add vertex color reading to terrain shader

### Phase 2: Multi-Layer Terrain Shader
1. Create `build_layered_terrain_material()` with 3-4 BSDF layers
2. Slope-based blending (flat=earth, steep=rock)
3. Height-based blending (low=wet, high=dry)
4. Vertex color splatmap integration
5. Noise-perturbed transitions

### Phase 3: Material Recipes
1. Implement the 6 specific recipes (forest floor, highland, swamp, castle stone, dirt paths, river banks)
2. Each recipe = specific layer config passed to the layered builder
3. Corruption factor support for dark fantasy zones

### Phase 4: Vegetation Materials
1. Bark material builder with species variation
2. Leaf material with SSS and corruption interpolation
3. Dead vegetation materials

### Phase 5: Bake Pipeline
1. Automated procedural-to-image baking
2. Channel-packed texture output for Unity URP
3. Roughness-to-smoothness inversion
4. Texture atlas generation for terrain chunks

---

## Sources

- [Blender Python API - NodeTree](https://docs.blender.org/api/current/bpy.types.NodeTree.html) - HIGH confidence
- [Blender Python API - ShaderNodeTree](https://docs.blender.org/api/current/bpy.types.ShaderNodeTree.html) - HIGH confidence
- [Blender Python API - Material](https://docs.blender.org/api/current/bpy.types.Material.html) - HIGH confidence
- [Blender Python API - NodeTreeInterface](https://docs.blender.org/api/current/bpy.types.NodeTreeInterface.html) - HIGH confidence
- [Blender Python API - BakeSettings](https://docs.blender.org/api/current/bpy.types.BakeSettings.html) - HIGH confidence
- [Blender 4.0 Python API Changes](https://developer.blender.org/docs/release_notes/4.0/python_api/) - HIGH confidence
- [Blender 4.1 Musgrave to Noise merge](https://cgian.com/musgrave-texture-to-noise-texture-in-blender/) - HIGH confidence
- [Creating node group inputs in Blender 4.0](https://b3d.interplanety.org/en/creating-inputs-and-outputs-for-node-groups-in-blender-4-0-using-the-python-api/) - HIGH confidence
- [Coding Blender Materials With Nodes & Python](https://behreajj.medium.com/coding-blender-materials-with-nodes-python-66d950c0bc02) - MEDIUM confidence
- [Slope and altitude materials in Cycles](https://pantarei.xyz/posts/snowline-tutorial/) - MEDIUM confidence
- [Blender Render Baking Manual](https://docs.blender.org/manual/en/latest/render/cycles/baking.html) - HIGH confidence
- [Frostbite Terrain Rendering (DICE)](https://media.contentapi.ea.com/content/dam/eacom/frostbite/files/chapter5-andersson-terrain-rendering-in-frostbite.pdf) - HIGH confidence
- [Advanced Terrain Texture Splatting](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting) - MEDIUM confidence
- [Texture Splatting (Wikipedia)](https://en.wikipedia.org/wiki/Texture_splatting) - MEDIUM confidence
- [How to Bake Procedural Materials (Blender to Unity)](https://guidebook.hdyar.com/3d/textures/bake-textures-in-blender-to-unity/) - MEDIUM confidence
- Codebase analysis of `terrain_materials.py` and `procedural_materials.py` - HIGH confidence (direct source)
