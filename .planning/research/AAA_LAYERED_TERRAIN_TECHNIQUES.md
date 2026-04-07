# AAA Layered Terrain Techniques -- Research Dump

**Researched:** 2026-04-06
**Scope:** How Witcher 3, Horizon Forbidden West, Red Dead 2, Elden Ring, and shipped AAA engines build *layered* terrain (not single heightmap sheets). Migration plan for VeilBreakers MountainPass.
**Confidence:** HIGH -- sourced from GDC presentations (REDengine 3 Gollent 2014, Frostbite BF3 2011/2012, Guerrilla HZD/HFW), Epic/Unity official docs, Blender 4.5 Python API docs, Blender Studio training, and the existing VB research file.
**Companion doc:** `.planning/research/AAA_TERRAIN_GENERATION_TECHNIQUES.md` (focuses on noise math and cliff mesh geometry -- read both together).

---

## Executive summary

AAA outdoor terrain is a **stack of 10-12 discrete layers**, not a heightmap. The heightmap is only layer 1. Every game listed above composes base geometry + displacement detail + material splats + hero meshes + scatter + ground cover + vegetation + shader overlays on top of each other. Single-sheet 300x300m heightmaps produce the "grainy blurry plane" look because they carry one scale of detail, one material, one UV projection, no hero assets, and no scatter.

The 4 non-negotiables every AAA terrain has:

1. **Triplanar (world-space) mapping** on cliff angles -- otherwise UV stretching ruins anything >45deg.
2. **Multi-scale tiling** (macro ~16m + meso ~2m + micro ~0.25m) to hide repetition.
3. **Hero rock meshes at steep slopes** -- the heightmap surface is hidden under sculpted cliff geometry wherever slope > ~55deg.
4. **GPU/CPU scatter with slope+density masks** -- rocks, scree, grass, trees all placed by rule, not by hand.

VeilBreakers MountainPass ships with only layer 1 (single heightmap, one material, no UV, no scatter). The migration plan in section 7 wires layers 2-11 into the existing `terrain_*.py` handlers without rewriting the foundation.

---

## 1. Terrain layering architecture per engine

### 1.1 Unreal Engine 5 Landscape + Landmass + Water + Nanite

Unreal's Landscape system is a **heightmap + stacked edit layers + material layer blend + RVT + Nanite tessellation** pipeline. The layer stack (top -> bottom):

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Nanite tessellation | `r.Nanite.Landscape=1` + Displacement node in material | Micro detail from displacement maps at Nanite cluster resolution |
| Runtime virtual texture (RVT) | `Runtime Virtual Texture Volume` + `RVT Output` node | Caches blended material into on-disk virtual texture; objects sample it to blend INTO the terrain |
| Landscape Edit Layers | Non-destructive edit layers on the heightmap itself (like Photoshop layers) | Erosion, splines, BP brushes, Landmass additions |
| Landscape Layer Blend node | `LandscapeLayerBlend` material node, alpha or height blend | Up to 8-16 paintable material layers (grass / dirt / rock / snow) |
| Landscape splines | Curve-based spline placed on terrain | Roads, rivers, stitched vegetation lines |
| Landmass (BP brush) | Blueprint brushes that write into edit layer | Non-destructive mountains / lakes / shaped features |
| Water plugin | Ocean/lake/river actors that stamp into heightmap AND carve channels | Hydrology-aware terrain |
| Foliage / PCG | `UFoliageType` instances, PCG graph | Grass and tree scatter on slope rules |

Key technical facts from Epic docs:
- `LandscapeLayerBlend` supports two blend types per layer: `LB_AlphaBlend` and `LB_HeightBlend`. Height blend uses the alpha channel of the texture as a displacement offset so dirt cracks naturally show through a grass layer instead of linearly fading. (Epic landscape-materials doc.)
- RVT is specifically recommended for "complex, procedurally generated, or layered materials" on Landscape. Writes to RVT via `Runtime Virtual Texture Output` node, reads via `Runtime Virtual Texture Sample`. The workflow: enable RVT in project settings -> create RVT asset with channels (BaseColor, Normal, Roughness, Mask) -> add RVT Volume -> material writes to it, meshes on top sample it for seamless blending. (Epic virtual-texturing doc.)
- **Nanite Landscape** keeps the Landscape actor but renders it as a Nanite mesh at runtime with tessellation. This is what enables true per-vertex micro-displacement on the entire terrain without tanking draw calls. Recommended workflow per Epic is Nanite-landscape + RVT + triplanar projection in the material to kill tiling on cliffs.
- Materials use the `WorldAlignedBlend` node (triplanar) for cliff angles and the `SlopeMask` or manual `DotProduct(Normal, (0,0,1))` for slope-based weight.

Triplanar in UE5 is implemented in `WorldAlignedTexture` / `WorldAlignedNormal` material functions. From Epic unrealcode.net reference: "tri-planar projection uses the world position" by sampling three plane projections (XY, YZ, XZ) and blending by surface normal orientation.

### 1.2 Unity HDRP Terrain + Terrain Tools package

Unity HDRP Terrain is simpler and more constrained:

| Layer | Mechanism | Limit |
|-------|-----------|-------|
| Heightmap | `TerrainData.heightmapResolution` | up to 4097x4097 |
| Terrain Layers | `TerrainLayer` assets (diffuse + normal + mask) | **Max 8 layers in HDRP** (hard limit) |
| Splatmaps | `TerrainData.alphamapTextures` -- one RGBA splat per 4 layers | 2 splatmaps for 8 layers |
| Terrain holes | `TerrainData.SetHoles()` | Requires `Terrain Hole` feature enabled in HDRP Asset |
| Trees | `TerrainData.treeInstances` | Instanced rendering, LOD |
| Details | `TerrainData.SetDetailLayer()` | Grass patches, 2D billboards |

Key facts:
- The Terrain Tools package adds `Erosion`, `Noise`, `Brush Mask Filter`, and the "Splatmap Import" tool that can load a pre-authored splatmap RGBA image and map its channels to 4 Terrain Layers. This is the integration point for Gaea/World Machine mask exports.
- HDRP Terrain Lit Material supports **height-based blend** per layer (layer alpha interpreted as height for pixel-level displacement blending), same concept as UE5's height blend. 8-layer ceiling is the hard limitation vs UE5 which can push 16+ via multiple `LandscapeLayerBlend` nodes.
- Holes in HDRP require explicit `Terrain Hole` feature flag in the HDRP Asset or they silently don't render in builds.
- Unity Terrain **does not support true cliffs/overhangs natively**. Cliffs must be placed as separate rock meshes on top of the heightmap, same as every other heightmap-based engine.

### 1.3 CryEngine / Lumberyard -- voxel terrain with overhangs

CryEngine 2/3 supported true **voxel objects** (a.k.a. Voxel Painter) that could add overhanging geometry, caves, and tunnels on top of the heightmap. Workflow:
- `RollupBar -> Terrain -> Voxel Painter`, type `Create` to add voxels, type `Subtract` to carve caves.
- Two-step cave creation: carve a hole in the heightmap first (`Terrain -> Holes`) to create an entrance, then switch to the voxel painter and use subtract brushes to hollow out the interior.
- **Voxels are deprecated in modern CryEngine V.** Current workflow is Designer Tool (CSG brush shapes) + rock meshes, identical to UE5/Unity.

### 1.4 Decima (Horizon Zero Dawn / Forbidden West)

From Guerrilla's 2017 GDC talk "GPU-Based Procedural Placement in Horizon Zero Dawn" and the 2022 "Scaling Tools for Millions of Assets for Horizon Forbidden West":
- The procedural placement system is **rule-graph-based**. Artists define rules in a graph editor ("place these rocks when slope > 30deg AND height > 40m AND biome == mountain AND distance from road > 5m"). The GPU evaluates the rule graph every frame around the player.
- This is not limited to rocks and trees -- "the procedural system assembles fully-fledged environments while the player walks through them, complete with sounds, effects, wildlife and gameplay elements" (Guerrilla).
- Key insight: **placement data does not live with the heightmap**. It lives in sparse rule graphs + occurrence maps (low-res density grids, 1 cell per 100m^2 in REDengine comparison). The heightmap is just "where", the rules decide "what goes there".
- HFW added "Adventures with Deferred Texturing" (GDC 2022) -- a loosely tiled deferred texturing system that allows more layers to blend without the 8-layer per-pixel limit typical engines have.

### 1.5 REDengine 3 (Witcher 3) -- the goldmine

The 2014 Marcin Gollent GDC presentation "Landscape Creation and Rendering in REDengine 3" is the most technical public writeup. Key numbers:

**Clipmap architecture** -- 3 streamed clipmaps + 3 runtime-generated clipmaps:
- Streamed: **elevation (16-bit unorm), control map (16-bit uint), color map (32-bit)**
- Runtime: **vertical errors (64x64 common case), normals (optional), terrain shadows**

**Novigrad configuration specifics:**
- 46x46 tiles at 512x512 each -> effective 23552^2 resolution
- Window resolution: 1024x1024
- 5 clipmap levels
- Inter-vertex spacing: ~0.37m (the slide says "0.37 cm" but that's a typo -- it's meters given the 74 km^2 coverage)
- Coverage: ~74 km^2

**Control map -- 16 bits packed:**
- Bits 0-4: overlay texture index (32 possible overlays)
- Bits 5-9: background texture index (32 possible backgrounds)
- Bits 10-12: UV scale index (7 scales)
- Bits 13-15: slope threshold index (7 thresholds)

This is their splatmap equivalent. Instead of RGBA splatmap weights, every terrain texel encodes "which two materials blend here" + "at what UV scale" + "at what slope threshold". The shader reads these 16 bits and does per-texel material lookup. Much denser than Unity's 4-channels-per-splatmap.

**Two-pass hole rendering** -- to avoid killing HiZ with discard:
- Pass 1: cull tessellation blocks that contain a hole (no discard, HiZ on, fast)
- Pass 2: re-draw just the hole-containing blocks with discard instruction (HiZ off, slow, but only on tiny regions)

**Shadow casting** -- store "maximum height that's in shadow" per clipmap texel. Iterative binary search with up to 13 iterations per pixel to find the exact self-shadow boundary. Classic Mark Wang / Chase shadow technique.

**Memory footprint** for 5 levels at 1024x1024 window: elevation + normal + control = 30 MB, color map = 12 MB, vertical errors = 327 KB, shadow = 10 MB -> **~53-63 MB total**.

**Vegetation scatter:** ~10 types auto-distributed per level, occurrence maps cost 125 kB per map at 100 m^2 cell size on 10 km^2 world -> the entire vegetation distribution for a massive open world fits in a few MB. Rules generate millions of instances from that.

VeilBreakers should NOT copy the clipmap/RVT architecture -- that's runtime rendering. What matters is the **control map concept**: pack material index + UV scale + slope threshold into each terrain texel (or vertex attribute), so the shader knows exactly how to texture each point.

### 1.6 Frostbite (Battlefield 3, PGA Tour)

From the 2011/2012 GDC "Terrain in Battlefield 3" and 2007 Siggraph "Terrain Rendering in Frostbite using Procedural Shader Splatting":
- **Procedural shader splatting** -- mountains, slopes, beaches are computed procedurally in the terrain shader from slope + altitude + noise, not painted by hand. "A simple ramp function can be computed with the procedural slope parameter available in the shader to mask in the mountain between a specified min and max slopes together with a linear transition." (EA Frostbite paper.)
- Procedural virtual texture caches the blended material result so the expensive splat math only runs once per tile. Prioritization allows work throttling.
- 2023 update (Frostbite Terrain Procedural Framework, GDC 2023 Julien Keable) adds full non-destructive GPU-based layer compositing with data-driven entities affecting terrain -- basically Frostbite's answer to UE5 Landscape Edit Layers. Used by Battlefield 2042 and EA Sports PGA Tour.

Key takeaway: **slope-and-altitude driven procedural material mix is the AAA default.** Hand-painted splatmaps are for overrides and hero areas only.

---

## 2. The 12 terrain layers that matter in AAA

Every AAA outdoor scene has these. Missing any of 3-11 is why a scene looks "blurry and flat".

### Layer 1 -- Base heightmap
- **Resolution:** 1 vertex per 0.5-2m in hero zones (matches REDengine's 0.37m vertex spacing). For VB's 300m^2 hero terrain, that's a 150-600 vert grid base, subdivided higher where needed.
- **Source:** Gaea (erosion simulation, best for realism), World Creator (fastest iteration), Houdini heightfield HDAs (most programmable), or multi-octave noise (procedural only, fallback).
- **Authoring output:** 16-bit grayscale PNG/EXR heightmap + RGBA splatmap + erosion/flow/deposit masks (R=rock exposure, G=sediment, B=flow, A=water).

### Layer 2 -- Displacement detail (per-vertex or per-pixel)
- **Per-vertex:** Stack Blender Displace modifiers or add a Set Position node in Geometry Nodes reading multiple Noise Texture nodes at different scales. Macro (16-32m), meso (2-4m), micro (0.25-0.5m). This is what makes terrain "not flat" at every zoom level.
- **Per-pixel:** Parallax Occlusion Mapping (POM) in the shader. POMster addon for Blender, or bake to normal + height and use the Principled BSDF displacement input. Adds fake 3D to rock surfaces without geometry cost.

### Layer 3 -- Rock strata (horizontal banding)
- The #1 thing that makes cliffs look real. Cliff faces show horizontal hard/soft rock bands.
- Generated procedurally in the shader using `abs(sin(worldZ * band_frequency))` with jitter -> mask that blends between two rock albedos and pushes the normal in/out. Or use Gaea's `Stratify` node and export it as a mask texture.
- In Blender shader: `Separate XYZ -> Z -> Math (Multiply by band_freq) -> Math (Sine) -> Math (Abs) -> ColorRamp -> Mix` between two rock textures, plus feeding the same signal into the Bump/Normal strength.

### Layer 4 -- Cliff hero meshes
- Sculpted hand-crafted rock meshes (ZBrush, Blender sculpt, or Megascans) that get placed wherever slope > ~55deg.
- Witcher 3, HZD, Elden Ring all do this. The heightmap terrain provides silhouette volume; the hero mesh provides close-up detail.
- Auto-placement: raycast down from above the slope, check ground normal, snap mesh to hit point with normal-aligned rotation. Section 3.7 covers the Blender implementation.

### Layer 5 -- Overhangs (true 3D geometry)
- Heightmaps can't do overhangs (one Z per XY). Solutions:
  - **Houdini SOPs:** heightfield -> convert to polygon -> extrude/inset -> VDB-boolean -> back to mesh. Export as Alembic or FBX.
  - **ZBrush/Blender sculpt:** sculpt as standalone asset, place like a hero mesh.
  - **Voxel (CryEngine historical, Dreams):** deprecated in most modern engines.
- In VeilBreakers: best bet is sculpted overhang hero meshes placed where the designer wants cave entries / dramatic cliffs. Don't try to procedurally overhang a heightmap.

### Layer 6 -- Scree / talus slopes
- Gravel/pebble deposits at the base of cliffs where erosion accumulated. Angle of repose = 30-38 degrees.
- **Generation:** Gaea has a `Debris` / `Deposits` node that outputs a scree mask. Alternatively, detect "directly below cliff edge within 20m" in Blender and raise terrain + mark vertices for scree material.
- **Scatter:** Distribute small rocks (0.1-0.8m diameter) at high density (50-200/m^2) on scree mask.

### Layer 7 -- Boulders (kitbash library)
- 10-30 large unique rock meshes from Megascans / sculpted. Placed sparsely (0.02-0.5/m^2) with random rotation/scale.
- Clusters: 2-5 boulders near each other feel more natural than uniform distribution.

### Layer 8 -- Pebble / detail scatter
- Small ground-cover rocks, 2-10 cm scale, 10-50/m^2. Mostly near cliff bases and stream beds.
- Can be instanced billboards at distance, real mesh up close.

### Layer 9 -- Ground cover (grass, moss, lichen)
- **Grass:** patches scattered at 50-500/m^2 on flat areas with grass material.
- **Moss:** specifically on rocks and cliff north-faces (wet side). Use slope+orientation mask.
- **Lichen:** detail scatter on rock albedos -- done in shader as noise-masked color tint, not geometry.

### Layer 10 -- Vegetation (trees, bushes, climbing plants)
- Trees placed on slope<25deg, height bands (tree line), water distance rule.
- Climbing plants (ivy) on cliff faces -- inverted slope rule (only where slope > 45deg) with rare density.

### Layer 11 -- Detail normal maps (tiled 4-8x over base)
- Base normal at 1:1 world scale, detail normal at 4-8x tile frequency blended in via `Normal Map` node + `Mix` at 0.3-0.5 strength. Adds per-pixel roughness that's always "in focus" regardless of camera distance.

### Layer 12 -- Wet/dirt streaks, vertex color overlays
- Vertex color painted dirt in valleys, wet darkening near water. Applied as a multiplier on albedo in the shader.
- Procedural alternative: Ambient Occlusion bake drives dirt accumulation mask.

---

## 3. Blender-specific implementation for layered terrain

### 3.1 Geometry Nodes scatter with surface sampler + slope mask + density

`Distribute Points on Faces` is the workhorse. It exposes Normal and Rotation outputs, supports Random or Poisson Disk distribution, and accepts a density factor attribute for per-face variable density. Basic slope-masked rock scatter:

```
Group Input (Geometry terrain)
  -> Distribute Points on Faces (method: Poisson Disk, distance_min: 0.8, density_max: 5.0)
     density_factor: attribute "slope_density" (a float field computed below)
  -> Instance on Points
     instance: Collection Info (rock kitbash collection, Pick Instance)
  -> Rotate Instances (rotation: align_to_normal + random_euler[0..30deg])
  -> Scale Instances (scale: Random Value 0.6..1.4)
  -> Realize Instances (only if exporting to FBX, else leave as instances)
  -> Group Output
```

Slope mask field computed alongside:

```
Normal (from Distribute Points output)
  -> Vector Math: Dot Product with (0,0,1)
  -> Math: Arccosine -> Math: Multiply (180/pi)        # angle in degrees
  -> Math: Greater Than 55                              # 1.0 if cliff, else 0.0
  -> (feeds density_factor for rock scatter on cliffs only)
```

The inverse (`Less Than 25`) feeds grass scatter on flats. `Between 25 and 55` feeds scree/mid-slope distribution.

Reference: `Distribute Points on Faces` node docs (Blender 5.1 manual), Blender Studio "Geometry Nodes from Scratch -- Advanced Rock Scattering" training. Blender 5.x also added a `Scatter on Surface` node which bundles Distribute + Instance + Align-to-Normal in one node (docs.blender.org/manual/en/dev/modeling/geometry_nodes/generate/scatter_on_surface.html).

### 3.2 Displacement modifier stack vs Geometry Nodes displacement

The classic Displace modifier takes **one texture per modifier**. For multi-octave terrain you stack 3-5 Displace modifiers with different texture scales:

```
Displace (Macro noise, scale 32m, strength 8m)
Displace (Meso noise, scale 4m, strength 1m)
Displace (Micro noise, scale 0.5m, strength 0.1m)
Subdivision Surface (2-3 levels, below all displaces for more verts)
```

Geometry Nodes version is better because you can sum noises with weights:

```
Position
  -> Noise Texture (Scale 0.03, Detail 4, Roughness 0.5) -> Multiply 8.0
  -> Noise Texture (Scale 0.25, Detail 2, Roughness 0.5) -> Multiply 1.0
  -> Noise Texture (Scale 2.0,  Detail 2, Roughness 0.5) -> Multiply 0.1
  -> (sum all three)
  -> Combine XYZ (0, 0, sum)
  -> Set Position (offset input)
```

The sum is a scalar height delta. You can also drive each Noise Texture by a mask (e.g., only apply micro noise where slope > 40deg) for context-aware detail.

Reference: Blender 4.5 Python API `mathutils.noise.ridged_multi_fractal()` for bmesh-side displacement, `ShaderNodeTexNoise` for shader-side, Entagma "Geometry Nodes Ep11 -- Create Noise Driven Displacement".

### 3.3 Multi-layer material via slope mask + height mask + triplanar

The canonical Blender slope+altitude material (derived from the Pantarei snowline tutorial and standard Blender practice):

```
Geometry (Normal)
  -> Vector Math: Dot Product with (0,0,1)  -> slope_fac (1=flat, 0=vertical)
Geometry (Position)
  -> Separate XYZ -> Z -> Map Range (low=water_level, high=snow_line) -> altitude_fac

# Triplanar rock: sample rock texture in X, Y, Z world planes, blend by |Normal|
Texture Coordinate (Object)
  -> Separate XYZ
    X plane: Image Texture (rock, Vector = (Y, Z))
    Y plane: Image Texture (rock, Vector = (X, Z))
    Z plane: Image Texture (rock, Vector = (X, Y))
  -> Mix three by normalize(abs(Normal))

# Material stack
Grass BSDF  --+
              +-- Mix Shader (fac = slope_fac threshold 0.7..0.9)
Rock BSDF   --+

Result -- Mix Shader (fac = altitude_fac)  -- Snow BSDF
```

Smooth transitions matter more than sharp ones. Use `Map Range` with a wide `From` range, or feed the mask through a `ColorRamp` with smoothstep interpolation. The Pantarei snowline post specifically uses a logistic function node group (sigmoid) as the transition -- smoother than linear, avoids the hard stripe artifact.

Add low-frequency noise to the slope/altitude masks before the Mix Shader to break up the line: `slope_fac + (Noise - 0.5) * 0.15` gives a natural ragged edge instead of a perfectly horizontal snowline.

### 3.4 Splatmap authoring from world-space projections

For exporting a splatmap to Unity or Unreal from Blender, bake world-space masks to a texture:

```python
# Pseudocode for baking slope/altitude masks
import bpy, bmesh

def bake_terrain_splatmap(terrain_obj, resolution=2048):
    # 1. UV unwrap the terrain top-down (smart_project fails -- use cube_project from top)
    # 2. Create image texture nodes for 4 channels (R=grass, G=dirt, B=rock, A=snow)
    # 3. For each face, compute slope and height, write weighted value to splat
    # 4. Bake Emission pass per channel, combine into RGBA
```

Better approach: use a Geometry Nodes modifier to write vertex attributes `weight_grass`, `weight_rock`, `weight_snow` based on slope/height math, then in a second pass bake those attributes to a UV texture via the `Attribute` node -> Emission -> bake. This keeps everything non-destructive.

Witcher 3 approach (control map) is overkill for VB; Unity/UE splatmap RGBA is sufficient.

### 3.5 Boolean cliff patches (local only -- the Witcher 3 overhang trick)

Witcher 3 did NOT modify the heightmap for overhangs. They placed overhang geometry as **local boolean patches** per-cliff, not as terrain modifications. Implementation in Blender:

```python
# 1. Generate base heightmap terrain
terrain_obj = make_terrain(...)
# 2. At designer-chosen hotspots, add sculpted overhang rock meshes as separate objects
overhang = bpy.data.objects["cliff_overhang_03"]
overhang.location = (150, 80, 45)
# 3. Do NOT boolean-union with terrain. Leave as separate mesh.
# 4. Optional: at the seam, scatter small rocks to hide the intersection.
```

The key is that the terrain and the overhang are separate meshes sharing the same world space. The Z-buffer handles the visual merge. This also keeps LODs clean.

### 3.6 Rock kitbash scatter from a collection

```python
# In Blender Geometry Nodes
# Collection Info (rocks, Separate Children, Reset Children)
#   -> Instance on Points (pick_instance=True)
# This picks a random rock per point from the collection.
```

Python side -- populating the rock collection:

```python
import bpy

rock_collection = bpy.data.collections.new("cliff_rock_kitbash")
bpy.context.scene.collection.children.link(rock_collection)

# Load 10-20 Megascans rocks via the Quixel Bridge API (see section 4.4)
# or import FBX directly
for rock_path in rock_files:
    bpy.ops.import_scene.fbx(filepath=str(rock_path))
    obj = bpy.context.selected_objects[0]
    # Move to kitbash collection
    for c in obj.users_collection:
        c.objects.unlink(obj)
    rock_collection.objects.link(obj)
    obj.hide_viewport = True  # Hide source, only instances visible
```

### 3.7 Hero asset placement with raycast + normal alignment

For placing hand-picked hero cliff meshes at specific locations:

```python
import bpy, mathutils

def place_hero_on_terrain(hero_obj, terrain_obj, world_xy, align_to_normal=True):
    # Raycast down from high above onto terrain
    ray_origin = mathutils.Vector((world_xy[0], world_xy[1], 1000.0))
    ray_dir = mathutils.Vector((0, 0, -1))
    mat_inv = terrain_obj.matrix_world.inverted()
    local_origin = mat_inv @ ray_origin
    local_dir = mat_inv.to_3x3() @ ray_dir

    hit, loc, normal, _ = terrain_obj.ray_cast(local_origin, local_dir)
    if not hit:
        return None

    world_loc = terrain_obj.matrix_world @ loc
    world_normal = (terrain_obj.matrix_world.to_3x3() @ normal).normalized()

    hero_obj.location = world_loc
    if align_to_normal:
        # Align hero Z-axis to terrain normal
        z_axis = world_normal
        x_axis = mathutils.Vector((1, 0, 0))
        # Re-orthogonalize
        y_axis = z_axis.cross(x_axis).normalized()
        x_axis = y_axis.cross(z_axis).normalized()
        rot_mat = mathutils.Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
        hero_obj.rotation_euler = rot_mat.to_euler()
    return hero_obj
```

`Object.ray_cast()` (bpy.types.Object.ray_cast) is the core API -- uses BVH for fast lookup. Documented in the Blender 4.5 Python API.

---

## 4. Procedural tools feeding Blender

### 4.1 Gaea 2 -> Blender

Gaea 2 exports via the `Export Mesh` and `Export heightmap` nodes:
- **Heightmap:** 16-bit RGB, non-interleaved, IBM-PC `.raw` file (or 16-bit PNG/EXR as alternative formats)
- **Mesh:** uniform grid OR optimized grid (fewer polys, preserves silhouette)
- **Masks:** any node can be exported as a grayscale 16-bit PNG -- including erosion (`Erosion` node output), flow (`Flow`), deposits (`Deposits`), strata (`Stratify`), rock exposure (`Outcrop`).

Blender import pattern:

```python
import bpy

def import_gaea_heightmap(heightmap_path, size_m=300.0, max_height_m=80.0, resolution=512):
    # Create a subdivided plane
    bpy.ops.mesh.primitive_grid_add(size=size_m,
                                     x_subdivisions=resolution,
                                     y_subdivisions=resolution)
    terrain = bpy.context.active_object

    # Load heightmap as image
    img = bpy.data.images.load(heightmap_path)

    # Add Displace modifier driven by the image
    tex = bpy.data.textures.new("heightmap", type='IMAGE')
    tex.image = img
    tex.extension = 'EXTEND'

    mod = terrain.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tex
    mod.texture_coords = 'GLOBAL'
    mod.strength = max_height_m
    mod.mid_level = 0.0

    return terrain

def import_gaea_mask_to_vertex_group(terrain, mask_path, vg_name):
    # For assigning per-vertex weights (scree, erosion) from a mask image
    img = bpy.data.images.load(mask_path)
    # Sample per vertex via uv -> pixel lookup
    # ... (bilinear sample, write to vertex group)
```

Gaea 3 (per QuadSpinner roadmap) introduces official Blender/Maya/Max plugins and USD export with masks preserved. Until then, the manual RAW/PNG + mask-to-vertex-group pattern above is the integration path.

Reference: QuadSpinner docs -- `Build and Export`, `Export Mesh`, `Exporting Elements`.

### 4.2 World Creator -> Blender

World Creator exports 16-bit heightmaps, splatmaps, and can export meshes as OBJ/FBX with vertex colors baked from masks. Less automation than Gaea but faster to iterate. Same import pattern as Gaea.

### 4.3 Houdini HDA -> Blender via Alembic

Houdini Heightfield tools (Hydro, Thermal, Flow, Debris erosion) produce high-quality terrains with cliff/overhang data as volume primitives. Workflow:

1. In Houdini: heightfield -> erosion -> `heightfield_output` -> convert to polygons via `heightfield_visualize` or `volume_convert`.
2. Extrude/inset for overhangs using SOPs.
3. Export via `ROP Alembic Output`. Set `Build Hierarchy from Attribute` using `name` attribute so Blender imports objects with correct names. Unpack before export. (SideFX docs.)
4. In Blender: `File -> Import -> Alembic (.abc)`.

The Alembic path preserves animation caches and vertex attributes, but FBX is simpler if you don't need those.

Reference: SideFX Houdini docs -- "Alembic files", "Generate a Landscape from Houdini", Entagma exporting guides.

### 4.4 Quixel Megascans Bridge -> Blender (API)

Quixel Bridge runs a local HTTP server (default port 24981) with endpoints:
- `GET http://localhost:24981/assets` -- list all assets in local library
- `GET http://localhost:24981/asset/{id}` -- metadata for one asset
- Live link: Bridge pushes to Blender via a socket when user clicks "Export"

Python-side batch download:

```python
import requests, json

def list_megascans():
    r = requests.get("http://localhost:24981/assets")
    return r.json()

def bridge_receive_socket():
    # Bridge-Python-Plugin (github.com/Quixel/Bridge-Python-Plugin)
    # opens a socket listener on port 28888 and receives JSON asset info
    # on user "Export to Blender" action
    ...
```

For truly automated download without Bridge UI, you need a Fab (Epic's successor to Megascans Store) API token + the Fab REST API. As of 2026 the Fab API is official but gated. Most studios still drive Bridge via its Custom Export socket.

Reference: `github.com/Quixel/Bridge-Python-Plugin`, Fab documentation.

### 4.5 PolyHaven -> Blender

PolyHaven has a fully public REST API at `https://api.polyhaven.com`. Examples:

```python
import requests

HEADERS = {"User-Agent": "VeilBreakers-Toolkit/1.0"}  # required

# List all textures in terrain category
r = requests.get("https://api.polyhaven.com/assets?type=textures&categories=terrain", headers=HEADERS)
assets = r.json()

# Get files for specific asset
r = requests.get("https://api.polyhaven.com/files/rock_embedded_sand", headers=HEADERS)
files = r.json()
# files -> Diffuse, nor_gl, Rough, Displacement, AO, etc -> list of resolutions

# Download a specific file
url = files["Diffuse"]["4k"]["jpg"]["url"]
r = requests.get(url, headers=HEADERS)
with open("rock_embedded_sand_diff_4k.jpg", "wb") as f:
    f.write(r.content)
```

Asset types: `hdris`, `textures`, `models`. Free for non-commercial, custom license for commercial. `polydown` (PyPI) is an existing Python CLI that wraps this for batch downloads.

Reference: `polyhaven.com/our-api`, `github.com/Poly-Haven/Public-API/blob/master/swagger.yml`, `polydown` on PyPI.

---

## 5. What separates "grainy blurry" from AAA -- the shader toolbox

For each, the specific Blender node graph.

### 5.1 Triplanar mapping (a.k.a. box projection)

**Without it:** rock texture on a vertical cliff stretches into ugly vertical streaks.
**With it:** three planar projections (XY, YZ, XZ) blend based on the absolute value of the world normal. Cliffs get their rock texture sampled from a horizontal plane instead of top-down UVs.

Blender built-in: Image Texture node -> Projection = `Box`, Blend = 0.2-0.3. Feed with `Texture Coordinate -> Generated` or `Object` for world-space. This is Blender's one-node triplanar.

Manual triplanar (for more control, separate textures per axis):

```
Texture Coordinate (Object)
  -> Separate XYZ
  Image 1: Vector = Combine XYZ(Y, Z, 0)  # X plane
  Image 2: Vector = Combine XYZ(X, Z, 0)  # Y plane
  Image 3: Vector = Combine XYZ(X, Y, 0)  # Z plane
Geometry (Normal) -> Vector Math (Absolute)
  -> Separate XYZ -> (nx, ny, nz)  # normalized blend weights
Mix Color (factor nx, nz/(nx+nz)) -> blend X and Z plane results
Mix Color (factor ny) -> blend with Y plane result
```

**Bonus:** use "snow from Z+" (a different texture for the upward face) for free snow on top of rocks.

### 5.2 World-space multi-scale tiling (macro/meso/micro)

```
Texture Coordinate -> Object
  Image Texture (rock_base, scale = 1.0 / 16.0)    # macro -- 16m tile
  Image Texture (rock_base, scale = 1.0 / 2.0)     # meso  -- 2m tile
  Image Texture (rock_base, scale = 1.0 / 0.25)    # micro -- 25cm tile
Mix Color (overlay blend mode, fac 0.5) -> combine macro+meso
Mix Color (overlay blend mode, fac 0.3) -> combine with micro
-> Base Color
```

The macro layer fights obvious repetition. The meso layer provides mid-distance detail. The micro layer makes the camera-close pixels feel sharp. Same textures at different scales, different blend strengths.

### 5.3 Detail normal maps (4-8x tiling over base)

```
Image Texture (normal_base, scale 1.0)
  -> Normal Map (strength 1.0) -> (base_normal)

Image Texture (normal_detail, scale 8.0)
  -> Normal Map (strength 0.5) -> (detail_normal)

Vector Math (Add) [base_normal, detail_normal]
  -> Vector Math (Normalize)
  -> BSDF Normal input
```

Or use the `Mix` node with `Normal Map` output. Detail normal strength 0.3-0.5 is the sweet spot -- too high looks noisy.

### 5.4 Slope-based blending (rock on steep, grass on flat)

Already covered in 3.3. Exact node chain:

```
Geometry.Normal -> Vector Math.Dot (0,0,1) -> Map Range(0.5, 0.95) -> slope_fac
grass_BSDF, rock_BSDF -> Mix Shader(fac = slope_fac)
```

Adjust `Map Range` input low/high to control the transition band. For softer transitions multiply `slope_fac` by `ColorRamp` with smoothstep interpolation.

### 5.5 Height-based fading (snow above line, grass below)

```
Geometry.Position -> Separate XYZ -> Z -> Map Range(snow_low, snow_high) -> height_fac
# Add jitter to break up line:
Position -> Noise Texture (scale 0.1) -> Map Range -> height_jitter
height_fac + (height_jitter - 0.5) * 0.2 -> final_fac
rock_BSDF, snow_BSDF -> Mix Shader(fac = final_fac)
```

### 5.6 Vertex color painting (cheap splatmap)

```
Attribute "Col" (vertex color)
  -> Separate Color -> R (dirt), G (wet), B (moss)
Mix Color (R fac) -> darken albedo by 0.6 (dirt)
Mix Color (G fac) -> raise Roughness to 0.15 (wet)
Mix Color (B fac) -> lerp to moss albedo (moss)
```

VeilBreakers can paint vertex colors procedurally: AO bake fed into R (dirt pools in concavities), curvature into G, etc.

### 5.7 Baked AO

Bake `Ambient Occlusion` pass to a texture in Blender's Bake panel -> multiply into Base Color. AO adds the illusion of crevice shadows without needing high-frequency displacement.

### 5.8 Subsurface scattering on foliage / water edges

Principled BSDF `Subsurface Weight: 0.1-0.3`, `Subsurface Color: green-tinged` for leaves. Adds translucency when backlit.

### 5.9 POM for close-up rock cracks

Use POMster addon or the manual parallax node. With a good heightmap on a rock texture, gives 3D illusion without geometry cost. Works in both Cycles and Eevee. Reference: `github.com/DreamSpoon/POMster`.

---

## 6. Modular cliff kit architecture (the Skyrim approach)

Joel Burgess's GDC 2013 "Skyrim's Modular Level Design" talk is the canonical source. Key principles:

### 6.1 Footprint rules
- Pick a base footprint (Skyrim used 512 Bethesda units). All kit pieces must be multiples or divisors. "A 512x512x512 room will always tile nicely with a 256x256x256 hallway, but a 384x384x384 room will eventually create gaps."
- Grid snap setting: **one-half of the footprint**. So 512 footprint -> 256 snap.

### 6.2 Recommended VB cliff kit sizes
- Base footprint: 4m (matches a 2m player + 2m headroom standard)
- Snap: 2m grid
- Piece sizes:
  - Cliff face tile: 4x4m horizontal, 8m tall (tiles vertically)
  - Inside corner: 4x4m footprint
  - Outside corner: 4x4m footprint
  - Short cliff (edge/lip): 4x4m, 2m tall
  - Overhang: 4x4m footprint, protrudes 2m
  - Boulder (large sculpted hero): no snap, irregular
  - Scree slope: 4x4m base, 2m rise at 35deg
- ~20-30 unique cliff pieces covers 95% of needs; Skyrim's kit was larger (~50 pieces) for variety.

### 6.3 Naming convention (Skyrim-style)

`{Kit}{SubKit}{Type}{Variant}{Side}{Index}`

Example breakdown from Joel's talk: `UtlBayCorInMidPRTT01L01` -> Utility kit, Bay sub-kit, Corner Inside Mid-tile, PRTT variant, 01, L01 (left variant 01).

VB suggestion:
```
clf_face_tile_4x4_01
clf_face_tile_4x4_02
clf_face_tile_4x4_03   # 3 variants to break repetition
clf_corner_in_4x4_01
clf_corner_out_4x4_01
clf_lip_4x4_01
clf_overhang_4x4_01
clf_boulder_lg_01 .. clf_boulder_lg_20
clf_scree_4x4_01
```

### 6.4 Snap point metadata

Blender Empties as children of each piece at the 8 snap points (N, S, E, W + 4 corners). Naming: `snap_N`, `snap_S`, etc. Placement code reads these Empties to align pieces during WFC or hand placement.

### 6.5 Seam hiding

**Critical:** modular kits always show seams at some angle. The solution is ALWAYS scatter. Place small rocks and grass tufts along every seam line automatically. Witcher 3, HZD, Skyrim all do this. In Blender: detect shared edges between adjacent kit pieces after placement, scatter 3-5 small rocks per meter of shared edge.

### 6.6 WFC (Wave Function Collapse) placement

VeilBreakers already has WFC in worldbuilding (`blender_worldbuilding` compound tool). Apply the same algorithm to cliff pieces with adjacency rules: face tiles can only touch other face tiles on their sides, overhangs only placed above face tiles, corners at direction changes, etc.

---

## 7. Current VeilBreakers state -> target migration plan

### 7.1 Current state (as of 2026-04-06)

Per the user's description and the code in `Tools/mcp-toolkit/blender_addon/handlers/terrain_*.py`:

- **Base:** 300x300m single-sheet heightmap, ~0.72 polys/m^2 (~65k tris on 300^2 = 0.72 verts per m^2)
- **Cliffs:** detected by slope then regenerated as "separate meshes" but still hard-seamed to the base
- **UVs:** missing (source bug in terrain creation)
- **Materials:** single base material, no splatmap, no triplanar
- **Scatter:** none at terrain level (vegetation handler exists but isn't invoked for MountainPass)
- **Scree/talus:** none
- **Hero rocks:** none
- **Ground cover:** none

### 7.2 Target state

Matches the 12-layer AAA stack from section 2. 300x300m hero zone.

- **Base:** 2-4 polys/m^2 (180k-360k tris on 300^2), properly UV-unwrapped (cube projection from +Z)
- **Displacement:** 3-octave noise in Geometry Nodes (macro 32m / meso 4m / micro 0.5m), context-masked by slope for detail density
- **Cliffs:** sculpted hero cliff pieces (Megascans or Blender sculpt) placed at slope>55deg by raycast+normal-align, scatter seams hidden by small rocks
- **Rocks:** Geometry Nodes scatter from `cliff_rock_kitbash` collection, slope-masked, 0.5-4/m^2 on cliffs
- **Scree:** Gaea-exported `deposits` mask -> vertex group -> small rocks at 20-60/m^2 in base of cliffs
- **Boulders:** 5-15 unique hero boulders placed by hand at designer hotspots
- **Ground cover:** grass scatter on slope<25deg, height-gated below tree line
- **Material:** multi-layer shader with slope+altitude mix, triplanar on cliff layers, detail normals, 16m/2m/0.25m multi-scale tiling
- **Vertex colors:** dirt in concavities (AO bake), wet darkening near water

### 7.3 Migration steps -- concrete phase plan

Ordered by dependency.

**Phase A -- Fix the UV bug** (blocker, 1 day)
1. Find the terrain creation function in `terrain_sculpt.py` or `terrain_advanced.py`.
2. After the final `bmesh.to_mesh()`, add a `smart_project` or cube-project-from-Z unwrap. Verify UVMap layer exists.
3. Add a test in `test_terrain_advanced.py` that asserts `obj.data.uv_layers` has at least one entry.

**Phase B -- Base poly density upgrade** (1 day)
1. Bump base plane subdivision from ~165x165 to 600x600 for 300x300m (~4 verts/m^2, matches AAA minimum from companion research doc).
2. Add an LOD tier parameter so draw cost remains manageable.
3. Re-run `game_check` via `blender_mesh` to confirm poly budget.

**Phase C -- Multi-octave displacement** (1 day)
1. Replace the single displace pass in `_terrain_noise.py` with a Geometry Nodes modifier that sums 3 noise octaves (macro/meso/micro) driven by `mathutils.noise.ridged_multi_fractal` or Blender's `Noise Texture` node.
2. Expose macro/meso/micro amplitude params in the `blender_worldbuilding` compound tool.

**Phase D -- Multi-layer terrain material** (2 days)
1. New file `terrain_material_layered.py` that builds the shader graph described in section 5.
2. Six BSDF branches: grass, dirt, rock_flat, rock_cliff (triplanar), scree, snow.
3. Slope+altitude mix with jitter noise for natural transitions.
4. Expose color palette via existing `_color_palettes.py`.
5. Assign to terrain automatically in `map_composer.compose_map`.

**Phase E -- Rock scatter via Geometry Nodes** (2 days)
1. Download 10-15 Megascans rocks (or use `blender_quality` procedural rock generator) into a `cliff_rock_kitbash` collection.
2. New handler function `scatter_rocks_on_terrain(terrain, collection, slope_range=(55, 90), density=2.0)` that builds a Geometry Nodes modifier using `Distribute Points on Faces` + `Instance on Points` with slope mask.
3. Add to `asset_pipeline.compose_map` after terrain creation.

**Phase F -- Scree and talus at cliff bases** (1 day)
1. For each cliff segment, raycast from its lower edge outward 5-20m to find flat ground.
2. Raise that ground by 0.5-2m with angle-of-repose slope (35deg) using a soft falloff.
3. Mark those verts for "scree" material weight.
4. Scatter small pebbles at 20-60/m^2 on the scree zone.

**Phase G -- Hero cliff meshes at hotspots** (2 days)
1. Add `place_hero_cliffs(terrain, hotspots)` using the raycast+normal-align code from section 3.7.
2. Designer places empty markers; pipeline reads them and instantiates hero rocks.
3. Scatter small rocks at seam between hero mesh and underlying terrain.

**Phase H -- Vegetation scatter** (1 day)
1. Wire the existing `vegetation_system.py` handler into MountainPass compose.
2. Grass on slope<25deg with density map from Gaea mask (or procedural).
3. Trees on slope<20deg, height<tree_line, distance>5m from roads.

**Phase I -- Ground cover polish** (1 day)
1. Add detail normal maps to the material.
2. Add vertex-color-based dirt via AO bake.
3. Final `game_check` + `contact_sheet` visual verification.

**Phase J -- Optional: Modular cliff kit** (3 days, if hero-mesh approach proves limiting)
1. Sculpt or import 20-30 modular cliff pieces to a library.
2. Implement WFC placement in `worldbuilding.py`.
3. Add snap-point Empty metadata per piece.

**Total: ~12-15 days of focused work** (one Opus dev stream, no parallelism).

### 7.4 Acceptance criteria

Before calling MountainPass "AAA layered":
1. `blender_mesh.game_check` shows >= 2 polys/m^2 base + UVs + correct normals
2. Terrain material has >= 4 BSDF branches (grass, rock_flat, rock_cliff_triplanar, snow)
3. Cliff zones have visible hero rock meshes (not bare heightmap)
4. Rock scatter visible on slopes > 55deg
5. Scree visible at base of major cliffs
6. `contact_sheet` from 4 angles shows no visible texture stretching on cliffs
7. `contact_sheet` from 4 angles shows no visible tiling seams (multi-scale tiling works)
8. Tree line is visible and follows height contour
9. Total draw calls reasonable (under 500 for hero area -- scatter uses instancing)
10. Visual QA pass from the user (subjective, AAA target)

### 7.5 Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Poly count explosion | LOD tiers + Nanite-ready FBX export path |
| Blender scatter performance | Use `Realize Instances` only at export, keep live scene as instances |
| Megascans asset licensing | PolyHaven as fallback (CC0), or `blender_quality` procedural rocks |
| Gaea not installed | Procedural noise+erosion in Geometry Nodes as fallback (lower quality but runs headless) |
| UV seam on triplanar | Blend param 0.2-0.4 on Box projection, tune per material |
| Hard cliff-base seam | Scatter-hide is the answer, always |

---

## 8. Quick-reference -- what to look up when implementing

| Need | Canonical source |
|------|------------------|
| Blender Distribute Points on Faces API | `docs.blender.org/manual/en/latest/modeling/geometry_nodes/point/distribute_points_on_faces.html` |
| Blender 4.5 noise functions | `docs.blender.org/api/4.5/mathutils.html#module-mathutils.noise` (ridged_multi_fractal, fractal, hybrid_multi_fractal) |
| Blender `Object.ray_cast` | Blender 4.5 Python API `bpy.types.Object.ray_cast` |
| Triplanar box projection | Blender shader node Image Texture `Projection = Box`, Blend 0.2-0.3 |
| Unreal Landscape layer blend | `dev.epicgames.com/documentation/en-us/unreal-engine/landscape-materials-in-unreal-engine` |
| Unreal RVT workflow | `dev.epicgames.com/documentation/en-us/unreal-engine/virtual-texturing-in-unreal-engine` |
| Unity HDRP Terrain Lit | `docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.0/manual/terrain-lit-material.html` |
| Unity Terrain Tools splatmap import | `docs.unity3d.com/Packages/com.unity.terrain-tools@2.0/manual/toolbox-import-splatmaps.html` |
| Witcher 3 REDengine 3 terrain | `ubm-twvideo01.s3.amazonaws.com/o1/vault/GDC2014/Presentations/Gollent_Marcin_Landscape_Creation_and.pdf` |
| Frostbite terrain BF3 | `media.contentapi.ea.com/content/dam/eacom/frostbite/files/gdc12-terrain-in-battlefield3.pdf` |
| Horizon procedural placement | `guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn` |
| Skyrim modular design | `gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design` |
| Gaea export docs | `docs.quadspinner.com/Guide/Using-Gaea/Building.html`, `docs.quadspinner.com/Guide/Build/Export-Mesh.html` |
| Quixel Bridge API | `github.com/Quixel/Bridge-Python-Plugin`, `help.quixel.com/hc/en-us/articles/360015741017-Bridge-API` |
| PolyHaven API | `polyhaven.com/our-api`, `github.com/Poly-Haven/Public-API/blob/master/swagger.yml` |
| POM in Blender | `github.com/DreamSpoon/POMster` |
| Slope+altitude material tutorial | `pantarei.xyz/posts/snowline-tutorial/` |
| Geometry Nodes rock scatter training | `studio.blender.org/training/geometry-nodes-from-scratch/example-advanced-rock-scattering/` |

---

## Sources

Primary GDC / academic sources:
- Gollent, Marcin. "Landscape Creation and Rendering in REDengine 3." GDC 2014. PDF at `ubm-twvideo01.s3.amazonaws.com/o1/vault/GDC2014/Presentations/Gollent_Marcin_Landscape_Creation_and.pdf`. Archive at `archive.org/details/GDC2014Gollent`.
- van Muijden, Jaap. "GPU-Based Procedural Placement in Horizon Zero Dawn." GDC 2017. `guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn`.
- Guerrilla. "Adventures with Deferred Texturing in Horizon Forbidden West." GDC 2022. `gdcvault.com/play/1027553/`.
- Guerrilla. "Scaling Tools for Millions of Assets for Horizon Forbidden West." GDC 2022. `gdcvault.com/play/1028848/`.
- Andersson, Johan. "Terrain Rendering in Frostbite using Procedural Shader Splatting." Siggraph 2007. `media.contentapi.ea.com/content/dam/eacom/frostbite/files/chapter5-andersson-terrain-rendering-in-frostbite.pdf`.
- DICE. "Terrain in Battlefield 3: A modern, complete and scalable system." GDC 2011/2012. `media.contentapi.ea.com/content/dam/eacom/frostbite/files/gdc12-terrain-in-battlefield3.pdf`.
- Keable, Julien. "Frostbite Terrain Procedural Framework." GDC 2023. `ea.com/frostbite/news/frostbite-presents-at-gdc-2023`.
- Burgess, Joel. "Skyrim's Modular Level Design." GDC 2013. `gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design`, slides at `slideshare.net/JoelBurgess/gdc2013-kit-buildingfinal`.

Engine documentation:
- Unreal Engine 5.7 Landscape, Landscape Materials, Nanite with Landscapes, Virtual Texturing. `dev.epicgames.com/documentation/en-us/unreal-engine/`.
- Unity HDRP 17.0 Terrain Lit Material, Terrain Tools 2.0 package. `docs.unity3d.com`.
- CryEngine V / 3 Voxel Objects, Terrain Editor, Cave creation. `docs.cryengine.com/display/CEMANUAL/`.

Blender:
- Blender 4.5 Python API (Context7): `/websites/blender_api_4_5` -- `bpy_extras.mesh_utils.triangle_random_points`, `mathutils.noise.ridged_multi_fractal`, procedural material node creation snippets.
- Blender 5.1 Manual: Distribute Points on Faces, Scatter on Surface, Noise Texture, Displace modifier, Mix Shader. `docs.blender.org/manual/en/latest/`.
- Blender Studio. "Geometry Nodes from Scratch -- Advanced Rock Scattering." `studio.blender.org/training/geometry-nodes-from-scratch/example-advanced-rock-scattering/`.
- POMster addon for Blender. `github.com/DreamSpoon/POMster`.
- Triplanar mapping in Blender (box projection). `3dsecrets.com/secrets/blender-secrets-triplanar-mapping`, `blenderartists.org/t/how-to-triplanar-box-mapping-normals-with-nodes/1130044`.
- Shader tutorial: slope and altitude based materials. Panta Rei, `pantarei.xyz/posts/snowline-tutorial/`.
- Blender-to-UE5 Geometry Nodes scatter workflow. James Roha, `medium.com/@Jamesroha/blender-geometry-nodes-to-unreal-engine-5-the-procedural-environment-art-guide-05cf8d8b4701`.

Content pipelines:
- QuadSpinner Gaea. Build/Export, Mesh export, Texture reference. `docs.quadspinner.com/Guide/Using-Gaea/Building.html`, `docs.quadspinner.com/Guide/Build/Export-Mesh.html`.
- Quixel Bridge Python Plugin sample. `github.com/Quixel/Bridge-Python-Plugin`. Bridge API docs `help.quixel.com/hc/en-us/articles/360015741017-Bridge-API`.
- Poly Haven API. `polyhaven.com/our-api`, swagger `github.com/Poly-Haven/Public-API/blob/master/swagger.yml`, CLI `polydown` on PyPI.
- SideFX Houdini Alembic/Landscape docs. `sidefx.com/docs/houdini/io/alembic.html`, `sidefx.com/docs/houdini/unreal/landscape/generate.html`.

Companion internal docs:
- `.planning/research/AAA_TERRAIN_GENERATION_TECHNIQUES.md` -- noise math, cliff geometry cross-sections, smootherstep blends, bmesh implementation details.
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_sculpt.py`, `terrain_features.py`, `terrain_advanced.py`, `terrain_materials.py`, `terrain_chunking.py` -- current VB terrain handlers (the code to upgrade).
- `Tools/mcp-toolkit/blender_addon/handlers/vegetation_system.py` -- existing scatter system to wire into MountainPass.
- `Tools/mcp-toolkit/blender_addon/handlers/map_composer.py` -- the orchestration entry point where the new layers get wired together.
