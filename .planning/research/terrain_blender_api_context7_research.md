# Terrain Mesh Manipulation via Blender Python API (bpy) -- Best Practices Research

**Researched:** 2026-04-02
**Domain:** bpy mesh creation, bmesh operations, numpy/scipy heightmap processing, material node trees
**Confidence:** HIGH (verified against official Blender docs, scipy docs, numpy docs, and existing VB codebase patterns)

---

## Summary

This document covers best practices for terrain mesh manipulation in Blender via Python, specifically for the VeilBreakers MCP toolkit. The codebase already has a mature terrain pipeline (`_terrain_noise.py`, `_terrain_erosion.py`, `terrain_materials.py`, `terrain_sculpt.py`, `terrain_advanced.py`, `terrain_chunking.py`, `environment.py`) using numpy-vectorized heightmaps, bmesh grid creation, bilinear vertex displacement, and RGBA vertex color splatmaps. This research codifies the API patterns, verifies current Blender 4.x compatibility, and documents scipy/numpy operations for terrain processing.

**Primary recommendation:** Continue using the established bmesh.ops.create_grid + vertex Z displacement pattern for terrain mesh creation. Use `color_attributes` (not deprecated `vertex_colors`) for Blender 4.x splatmaps. Use scipy.ndimage.gaussian_filter for terrain smoothing and numpy.gradient + numpy.roll for erosion/slope computation.

---

## 1. Mesh Creation Patterns

### 1.1 High-Level: `from_pydata()` (Simple, Slower)

```python
# Source: Blender Python API - bpy.types.Mesh
mesh = bpy.data.meshes.new("terrain")
verts = [(x, y, z) for ...]  # list of (x,y,z) tuples
faces = [(0,1,2,3), ...]     # list of vertex index tuples
mesh.from_pydata(verts, [], faces)
mesh.update()

obj = bpy.data.objects.new("Terrain", mesh)
bpy.context.collection.objects.link(obj)
```

**When to use:** Small meshes, prototyping, <10K vertices.
**Pitfall:** from_pydata does NOT accept numpy arrays directly for edges/faces (Blender issue #90268). Convert to Python lists first.
**Pitfall (Blender 4.x):** from_pydata silently produces corrupt data if quads and tris are mixed in certain orderings (issue #111117). Use validate() afterward.

### 1.2 Low-Level: `foreach_set()` (Fast, for Large Meshes)

```python
# Source: Blender Python API - Performance best practices
import numpy as np

mesh = bpy.data.meshes.new("terrain")
num_verts = rows * cols
num_faces = (rows - 1) * (cols - 1)

mesh.vertices.add(num_verts)
mesh.loops.add(num_faces * 4)       # quads = 4 loops per face
mesh.polygons.add(num_faces)

# Flat coordinate array: [x0, y0, z0, x1, y1, z1, ...]
coords = np.zeros(num_verts * 3, dtype=np.float32)
coords[0::3] = x_flat  # all X values
coords[1::3] = y_flat  # all Y values
coords[2::3] = z_flat  # all Z values (from heightmap)
mesh.vertices.foreach_set('co', coords)

# Loop vertex indices: [v0, v1, v2, v3, v0, v1, ...]
loop_verts = np.zeros(num_faces * 4, dtype=np.int32)
# ... build quad indices ...
mesh.loops.foreach_set('vertex_index', loop_verts)

# Polygon loop start + total
loop_starts = np.arange(0, num_faces * 4, 4, dtype=np.int32)
loop_totals = np.full(num_faces, 4, dtype=np.int32)
mesh.polygons.foreach_set('loop_start', loop_starts)
mesh.polygons.foreach_set('loop_total', loop_totals)

mesh.update()
mesh.validate()
```

**When to use:** Terrain grids >10K vertices, performance-critical paths.
**Blender 4.1 change:** `foreach_set` now performs strict bounds checks and raises TypeError for incorrect sizes (previously silently wrote garbage). Always ensure array length matches exactly.

### 1.3 BMesh: `create_grid` + Vertex Displacement (VB Standard Pattern)

This is the pattern used throughout the VeilBreakers codebase (environment.py, terrain_advanced.py).

```python
# Source: VB codebase - environment.py line 431-472
import bmesh
import bpy

mesh = bpy.data.meshes.new(name)
bm = bmesh.new()

# Create grid with UVs
bmesh.ops.create_grid(
    bm,
    x_segments=cols - 1,
    y_segments=rows - 1,
    size=terrain_size / 2.0,
    calc_uvs=True,
)

bm.verts.ensure_lookup_table()

# Displace Z from heightmap with bilinear interpolation
for vert in bm.verts:
    u = (vert.co.x + terrain_size / 2.0) / terrain_size
    v = (vert.co.y + terrain_size / 2.0) / terrain_size
    col_f = u * (cols - 1)
    row_f = v * (rows - 1)
    c0 = max(0, min(int(col_f), cols - 2))
    r0 = max(0, min(int(row_f), rows - 2))
    c1 = c0 + 1
    r1 = r0 + 1
    cf = col_f - c0
    rf = row_f - r0
    h = (heightmap[r0, c0] * (1 - cf) * (1 - rf)
         + heightmap[r0, c1] * cf * (1 - rf)
         + heightmap[r1, c0] * (1 - cf) * rf
         + heightmap[r1, c1] * cf * rf)
    vert.co.z = h * height_scale

bm.to_mesh(mesh)
bm.free()

# Enable smooth shading
for poly in mesh.polygons:
    poly.use_smooth = True

obj = bpy.data.objects.new(name, mesh)
bpy.context.collection.objects.link(obj)
```

**Why this is standard:** bmesh.ops.create_grid generates a clean quad grid with UVs in one call. Vertex displacement loop is straightforward. bmesh handles topology correctly.

**Performance note for large terrains:** The per-vertex Python loop is the bottleneck. For 512x512 grids (262K vertices), this takes ~2-5 seconds. For extreme sizes, consider the foreach_set pattern (1.2) or numpy vectorized vertex assignment.

---

## 2. Vertex Displacement for Heightmaps

### 2.1 Direct Z Assignment (Current VB Pattern)

```python
# Per-vertex in bmesh (used in environment.py)
for vert in bm.verts:
    # Map XY to heightmap UV coordinates
    u = (vert.co.x + size/2) / size
    v = (vert.co.y + size/2) / size
    vert.co.z = sample_heightmap_bilinear(heightmap, u, v) * height_scale
```

### 2.2 Vectorized Z Assignment (Faster for Large Meshes)

```python
# Extract all Z values from heightmap in one numpy operation
# Used in terrain_advanced.py line 1324
heightmap_flat = heightmap.ravel()
for i, v in enumerate(bm.verts):
    v.co.z = float(heightmap_flat[i])
```

**Best practice:** When heightmap resolution matches mesh resolution exactly, use ravel() for direct mapping. When they differ (mesh has more/fewer verts than heightmap pixels), use bilinear interpolation.

### 2.3 Heightmap Extraction from Existing Mesh

```python
# Source: terrain_advanced.py line 1324
heightmap = np.array([v.co.z for v in bm.verts]).reshape(res, -1)
```

---

## 3. Modifiers via Python

### 3.1 Adding Modifiers

```python
# Source: Blender Python API - Object.modifiers
mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
mod.levels = 2           # viewport subdivision
mod.render_levels = 3    # render subdivision
mod.subdivision_type = 'SIMPLE'  # or 'CATMULL_CLARK'
```

### 3.2 Subdivision Surface (Terrain Detail)

```python
# SIMPLE subdivision for terrain (does NOT smooth, just adds geometry)
mod = obj.modifiers.new(name="VB_Subdiv", type='SUBSURF')
mod.subdivision_type = 'SIMPLE'
mod.levels = 1  # doubles face count per level
```

**Important:** Use `SIMPLE` for terrain, not `CATMULL_CLARK`. Catmull-Clark smooths geometry, losing heightmap detail. Simple subdivision adds vertices at midpoints without smoothing.

### 3.3 Decimate (LOD Reduction)

```python
# Collapse decimation for terrain LOD
mod = obj.modifiers.new(name="VB_Decimate", type='DECIMATE')
mod.decimate_type = 'COLLAPSE'
mod.ratio = 0.5  # 50% of original faces

# Planar decimation (better for terrain -- removes flat areas)
mod = obj.modifiers.new(name="VB_Decimate", type='DECIMATE')
mod.decimate_type = 'DISSOLVE'
mod.angle_limit = 0.087  # radians (~5 degrees) -- dissolve near-flat regions
```

**Terrain best practice:** Use DISSOLVE mode for terrain LOD. It preserves detail on steep slopes and removes unnecessary vertices in flat areas. COLLAPSE treats all faces equally and can destroy cliff detail.

### 3.4 Smooth Modifier

```python
# Laplacian smooth for terrain (preserves volume better)
mod = obj.modifiers.new(name="VB_Smooth", type='LAPLACIANSMOOTH')
mod.lambda_factor = 1.0
mod.lambda_border = 0.0  # don't smooth edges
mod.iterations = 2

# Simple smooth (for subtle final pass)
mod = obj.modifiers.new(name="VB_Smooth", type='SMOOTH')
mod.factor = 0.5
mod.iterations = 3
```

### 3.5 Displace Modifier (Alternative to Vertex Displacement)

```python
# Texture-based displacement
mod = obj.modifiers.new(name="VB_Displace", type='DISPLACE')
mod.direction = 'NORMAL'  # or 'Z' for terrain
mod.strength = 10.0
mod.mid_level = 0.0
# Assign a texture for the displacement map
tex = bpy.data.textures.new("HeightTex", type='IMAGE')
tex.image = heightmap_image
mod.texture = tex
```

### 3.6 Applying Modifiers

```python
# Apply modifier (destructive -- bakes into mesh data)
# Blender 4.x context override pattern:
with bpy.context.temp_override(object=obj):
    bpy.ops.object.modifier_apply(modifier="VB_Subdiv")

# Or using depsgraph (non-destructive evaluation):
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = obj.evaluated_get(depsgraph)
eval_mesh = eval_obj.to_mesh()
# Copy evaluated mesh to original
obj.data = eval_mesh
```

**Blender 4.x note:** `bpy.context.temp_override()` replaces the old `override = context.copy(); override['object'] = obj` pattern. The old pattern still works but is deprecated.

---

## 4. Material Node Tree Creation

### 4.1 Basic Material Setup

```python
# Source: VB codebase - procedural_materials.py
mat = bpy.data.materials.new(name="TerrainMaterial")
mat.use_nodes = True
tree = mat.node_tree
nodes = tree.nodes
links = tree.links

# Clear defaults
nodes.clear()

# Create output node
output = nodes.new("ShaderNodeOutputMaterial")
output.location = (400, 0)

# Create Principled BSDF
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (0, 0)
links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
```

### 4.2 Slope-Based Material Blending

```python
# Geometry Normal -> Separate XYZ -> Z component = steepness
geom = nodes.new("ShaderNodeNewGeometry")
geom.location = (-800, 0)

separate = nodes.new("ShaderNodeSeparateXYZ")
separate.location = (-600, 0)
links.new(geom.outputs["Normal"], separate.inputs["Vector"])

# Z component: 1.0 = flat, 0.0 = vertical cliff
# Use Map Range to convert to blend factor
map_range = nodes.new("ShaderNodeMapRange")
map_range.location = (-400, 0)
map_range.inputs["From Min"].default_value = 0.3   # cliff threshold
map_range.inputs["From Max"].default_value = 0.7   # grass threshold
map_range.inputs["To Min"].default_value = 0.0     # full cliff
map_range.inputs["To Max"].default_value = 1.0     # full grass
links.new(separate.outputs["Z"], map_range.inputs["Value"])

# Mix between cliff and grass materials
mix = nodes.new("ShaderNodeMixShader")
mix.location = (200, 0)
links.new(map_range.outputs["Result"], mix.inputs["Fac"])
links.new(bsdf_cliff.outputs["BSDF"], mix.inputs[1])
links.new(bsdf_grass.outputs["BSDF"], mix.inputs[2])
```

### 4.3 Height-Based Material Blending

```python
# Object position Z -> height factor
geom = nodes.new("ShaderNodeNewGeometry")
tex_coord = nodes.new("ShaderNodeTexCoord")
separate_pos = nodes.new("ShaderNodeSeparateXYZ")
links.new(geom.outputs["Position"], separate_pos.inputs["Vector"])

# Map world Z to 0..1 range based on terrain height range
height_range = nodes.new("ShaderNodeMapRange")
height_range.inputs["From Min"].default_value = 0.0    # sea level
height_range.inputs["From Max"].default_value = 100.0   # max height
height_range.inputs["To Min"].default_value = 0.0
height_range.inputs["To Max"].default_value = 1.0
links.new(separate_pos.outputs["Z"], height_range.inputs["Value"])

# Color ramp for height zones (beach -> grass -> rock -> snow)
ramp = nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0    # beach
ramp.color_ramp.elements[0].color = (0.8, 0.7, 0.5, 1.0)
elem1 = ramp.color_ramp.elements.new(0.3)     # grass
elem1.color = (0.2, 0.4, 0.1, 1.0)
elem2 = ramp.color_ramp.elements.new(0.6)     # rock
elem2.color = (0.4, 0.35, 0.3, 1.0)
ramp.color_ramp.elements[1].position = 1.0    # snow
ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.95, 1.0)
links.new(height_range.outputs["Result"], ramp.inputs["Fac"])
```

### 4.4 Vertex Color Splatmap Reading in Shader

```python
# Source: VB codebase - terrain_materials.py create_biome_terrain_material()
# Read vertex color attribute as splatmap (R=ground, G=slope, B=cliff, A=special)
vc_node = nodes.new("ShaderNodeVertexColor")
vc_node.layer_name = "VB_TerrainSplatmap"
vc_node.location = (-800, -200)

# Separate RGBA channels
sep_rgb = nodes.new("ShaderNodeSeparateColor")
sep_rgb.location = (-600, -200)
links.new(vc_node.outputs["Color"], sep_rgb.inputs["Color"])

# Each channel drives a Mix Shader
# R channel -> ground material weight
# G channel -> slope material weight
# B channel -> cliff material weight
# A channel -> special material weight (from Alpha output)
```

### 4.5 Triplanar Mapping

```python
# Triplanar projection: avoids UV stretching on steep terrain
tex_coord = nodes.new("ShaderNodeTexCoord")
tex_coord.location = (-1200, 0)

mapping = nodes.new("ShaderNodeMapping")
mapping.location = (-1000, 0)
mapping.inputs["Scale"].default_value = (0.1, 0.1, 0.1)  # texture scale
links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

# Create 3 texture samples (XY, XZ, YZ planes)
tex_xy = nodes.new("ShaderNodeTexImage")
tex_xz = nodes.new("ShaderNodeTexImage")
tex_yz = nodes.new("ShaderNodeTexImage")

# Use geometry normal to blend between projections
geom = nodes.new("ShaderNodeNewGeometry")
sep = nodes.new("ShaderNodeSeparateXYZ")
links.new(geom.outputs["Normal"], sep.inputs["Vector"])

# Abs(normal) for blend weights
abs_x = nodes.new("ShaderNodeMath")
abs_x.operation = 'ABSOLUTE'
links.new(sep.outputs["X"], abs_x.inputs[0])

abs_y = nodes.new("ShaderNodeMath")
abs_y.operation = 'ABSOLUTE'
links.new(sep.outputs["Y"], abs_y.inputs[0])

abs_z = nodes.new("ShaderNodeMath")
abs_z.operation = 'ABSOLUTE'
links.new(sep.outputs["Z"], abs_z.inputs[0])
```

---

## 5. Vertex Color Painting via Python

### 5.1 Blender 4.x: `color_attributes` (Current Standard)

```python
# Blender 4.0+ uses color_attributes instead of deprecated vertex_colors
mesh = obj.data

# Create color attribute (BYTE_COLOR or FLOAT_COLOR domain)
if "VB_TerrainSplatmap" not in mesh.color_attributes:
    color_attr = mesh.color_attributes.new(
        name="VB_TerrainSplatmap",
        type='FLOAT_COLOR',     # or 'BYTE_COLOR' for 8-bit
        domain='CORNER',        # per-loop-corner (matches UVs)
    )
else:
    color_attr = mesh.color_attributes["VB_TerrainSplatmap"]

# Set as active for rendering
mesh.color_attributes.active_color = color_attr
mesh.color_attributes.render_color_index = mesh.color_attributes.find("VB_TerrainSplatmap")

# Paint per-corner colors
for poly in mesh.polygons:
    for loop_idx in poly.loop_indices:
        color_attr.data[loop_idx].color = (r, g, b, a)
```

### 5.2 Legacy Compatibility: `vertex_colors` (Blender 3.x)

```python
# Deprecated but still works in Blender 4.x (may be removed in future)
if not mesh.vertex_colors:
    mesh.vertex_colors.new(name="VB_TerrainSplatmap")
vc_layer = mesh.vertex_colors["VB_TerrainSplatmap"]

for poly in mesh.polygons:
    for loop_idx in poly.loop_indices:
        vc_layer.data[loop_idx].color = (r, g, b, a)
```

### 5.3 BMesh Vertex Colors

```python
# BMesh approach (used during mesh construction)
bm = bmesh.new()
# ... create geometry ...

color_layer = bm.loops.layers.color.new("VB_TerrainSplatmap")
for face in bm.faces:
    for loop in face.loops:
        loop[color_layer] = (r, g, b, a)

bm.to_mesh(mesh)
bm.free()
```

### 5.4 VB Splatmap Painting Pattern

The VeilBreakers codebase uses a pure-logic function to compute splatmap RGBA values, then applies them to the mesh:

```python
# Source: terrain_materials.py - compute_splatmap_weights_v2()
# Computes per-vertex RGBA from slope + height + moisture
# R=ground, G=slope, B=cliff, A=special
# Slope thresholds: flat_deg=30, cliff_deg=60
# Height thresholds: special_low_pct=0.15, special_high_pct=0.85
```

---

## 6. UV Manipulation

### 6.1 Auto-Generated UVs (from create_grid)

`bmesh.ops.create_grid(..., calc_uvs=True)` generates UVs automatically. They map 0..1 across the grid.

### 6.2 Custom UV Assignment

```python
# Access UV layer
uv_layer = bm.loops.layers.uv.verify()  # get or create default UV layer

for face in bm.faces:
    for loop in face.loops:
        # Map vertex position to UV
        u = (loop.vert.co.x + size/2) / size
        v = (loop.vert.co.y + size/2) / size
        loop[uv_layer].uv = (u, v)
```

### 6.3 UV Layer Operations on Mesh Data

```python
# Create named UV layer
if "TerrainUV" not in mesh.uv_layers:
    mesh.uv_layers.new(name="TerrainUV")
uv_layer = mesh.uv_layers["TerrainUV"]

# Set UVs per-loop
for poly in mesh.polygons:
    for i, loop_idx in enumerate(poly.loop_indices):
        uv_layer.data[loop_idx].uv = (u, v)
```

---

## 7. Mesh Cleanup Operations

### 7.1 Remove Doubles (Merge by Distance)

```python
# Source: VB codebase - autonomous_loop.py, environment.py
bm = bmesh.new()
bm.from_mesh(obj.data)

removed = bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
merged_count = len(removed.get("verts", []))

bm.to_mesh(obj.data)
bm.free()
```

**Important:** Pass `bm.verts[:]` (slice copy), not `bm.verts` directly. BMesh element sequences must be copied before passing to operators that modify geometry.

### 7.2 Recalculate Normals

```python
# Source: VB codebase - environment.py
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# After converting to mesh:
mesh.calc_normals_split()  # for split/custom normals
# or
mesh.normals_split_custom_set_from_vertices(normals_array)
```

### 7.3 Full Cleanup Pipeline

```python
bm = bmesh.new()
bm.from_mesh(obj.data)

# 1. Remove doubles
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)

# 2. Recalculate normals
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

# 3. Dissolve degenerate faces (zero-area)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=0.0001)

# 4. Remove interior faces (if present)
# bmesh.ops.delete(bm, geom=interior_faces, context='FACES')

bm.to_mesh(obj.data)
bm.free()

# 5. Validate
obj.data.validate(verbose=True)

# 6. Update normals
obj.data.update()
```

---

## 8. scipy.ndimage.gaussian_filter for Terrain Smoothing

### 8.1 Function Signature

```python
scipy.ndimage.gaussian_filter(
    input,           # 2D heightmap array
    sigma,           # smoothing radius (float or (sigma_y, sigma_x))
    order=0,         # 0 = Gaussian, 1+ = derivatives
    output=None,     # output array or dtype
    mode='reflect',  # edge handling: 'reflect', 'constant', 'nearest', 'mirror', 'wrap'
    cval=0.0,        # fill value for 'constant' mode
    truncate=4.0,    # kernel truncation in sigmas
    *,
    radius=None,     # explicit kernel radius (overrides truncate)
    axes=None,       # axes to filter along
)
# Returns: ndarray (same shape as input)
```

Source: [scipy.ndimage.gaussian_filter docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html)

### 8.2 Terrain Smoothing Patterns

```python
from scipy.ndimage import gaussian_filter
import numpy as np

# Light smoothing (preserve detail, remove noise)
smoothed = gaussian_filter(heightmap, sigma=1.0)

# Medium smoothing (rolling hills)
smoothed = gaussian_filter(heightmap, sigma=3.0)

# Heavy smoothing (gentle terrain)
smoothed = gaussian_filter(heightmap, sigma=8.0)

# Anisotropic smoothing (smooth more in one direction)
smoothed = gaussian_filter(heightmap, sigma=(2.0, 5.0))  # more X smoothing

# Edge handling for tileable terrain
smoothed = gaussian_filter(heightmap, sigma=2.0, mode='wrap')

# Edge handling for non-tileable (reflect at borders)
smoothed = gaussian_filter(heightmap, sigma=2.0, mode='reflect')
```

### 8.3 Selective Smoothing (Smooth Only Flat Areas)

```python
# Compute slope, only smooth where slope < threshold
slope_map = compute_slope_map(heightmap)  # from _terrain_noise.py
mask = slope_map < 15.0  # degrees

smoothed = gaussian_filter(heightmap, sigma=2.0)
# Blend: use smoothed where flat, original where steep
result = np.where(mask, smoothed, heightmap)
```

### 8.4 Multi-Pass Smoothing (Simulate Weathering)

```python
# Progressive smoothing with decreasing sigma (coarse to fine)
result = heightmap.copy()
for sigma in [8.0, 4.0, 2.0, 1.0]:
    result = gaussian_filter(result, sigma=sigma)
    result = 0.5 * result + 0.5 * heightmap  # blend back original detail
```

---

## 9. numpy Operations for Heightmap Erosion

### 9.1 numpy.gradient for Slope Computation

```python
# Source: numpy docs
# Returns (dy, dx) gradient arrays
dy, dx = np.gradient(heightmap)

# Slope magnitude (steepness)
slope = np.sqrt(dx**2 + dy**2)

# Slope in degrees
slope_deg = np.degrees(np.arctan(slope))

# Flow direction (aspect)
aspect = np.arctan2(-dy, -dx)  # downhill direction
```

This is the pattern used in VB's `_terrain_noise.py:compute_slope_map()`.

### 9.2 numpy.roll for Neighbor Access (Erosion Kernels)

```python
# Source: numpy docs
# roll shifts array elements along an axis (wraps around edges)

# 4-neighbor height differences for thermal erosion
h_up    = np.roll(heightmap, -1, axis=0)  # shift up
h_down  = np.roll(heightmap,  1, axis=0)  # shift down
h_left  = np.roll(heightmap, -1, axis=1)  # shift left
h_right = np.roll(heightmap,  1, axis=1)  # shift right

# Height differences to each neighbor
diff_up    = heightmap - h_up
diff_down  = heightmap - h_down
diff_left  = heightmap - h_left
diff_right = heightmap - h_right

# Max height difference (steepest neighbor)
max_diff = np.maximum(np.maximum(diff_up, diff_down),
                      np.maximum(diff_left, diff_right))
```

### 9.3 Thermal Erosion (Vectorized numpy)

```python
def thermal_erosion_step(heightmap: np.ndarray, talus: float = 0.01) -> np.ndarray:
    """One step of thermal erosion using numpy.roll.
    
    Material slides from steep slopes to lower neighbors when
    slope exceeds talus angle threshold.
    """
    result = heightmap.copy()
    
    # 4-connected neighbor differences
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for dy, dx in shifts:
        neighbor = np.roll(np.roll(heightmap, dy, axis=0), dx, axis=1)
        diff = heightmap - neighbor
        
        # Only erode where slope exceeds talus
        excess = np.maximum(0, diff - talus)
        transfer = excess * 0.5  # transfer half of excess
        
        result -= transfer
        # Deposit at neighbor (shift back)
        result += np.roll(np.roll(transfer, -dy, axis=0), -dx, axis=1)
    
    return result
```

### 9.4 Hydraulic Flow Accumulation (D8 Algorithm)

```python
# D8 flow accumulation using numpy (used in terrain_advanced.py)
def compute_d8_flow(heightmap: np.ndarray) -> np.ndarray:
    """Compute D8 flow accumulation map."""
    rows, cols = heightmap.shape
    flow_acc = np.ones((rows, cols), dtype=np.float64)
    
    # Compute flow direction to steepest neighbor
    dy, dx = np.gradient(heightmap)
    flow_dir = np.arctan2(-dy, -dx)  # downhill direction
    
    # Sort cells by height (highest first for top-down accumulation)
    sorted_indices = np.argsort(-heightmap.ravel())
    
    for idx in sorted_indices:
        r, c = divmod(idx, cols)
        # Find steepest downhill neighbor
        best_r, best_c = r, c
        best_drop = 0
        for dr, dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                drop = heightmap[r, c] - heightmap[nr, nc]
                if drop > best_drop:
                    best_drop = drop
                    best_r, best_c = nr, nc
        if (best_r, best_c) != (r, c):
            flow_acc[best_r, best_c] += flow_acc[r, c]
    
    return flow_acc
```

### 9.5 scipy.ndimage.convolve for Custom Kernels

```python
from scipy.ndimage import convolve

# Laplacian kernel (edge detection / curvature)
laplacian = np.array([[0, 1, 0],
                       [1, -4, 1],
                       [0, 1, 0]], dtype=np.float64)
curvature = convolve(heightmap, laplacian, mode='reflect')

# Emboss kernel (ridge detection)
emboss = np.array([[-2, -1, 0],
                    [-1,  1, 1],
                    [ 0,  1, 2]], dtype=np.float64)
ridges = convolve(heightmap, emboss, mode='reflect')

# Sharpening kernel (enhance detail)
sharpen = np.array([[ 0, -1,  0],
                     [-1,  5, -1],
                     [ 0, -1,  0]], dtype=np.float64)
sharpened = convolve(heightmap, sharpen, mode='reflect')
```

---

## 10. Bilateral Filtering Implementation in numpy

Bilateral filtering smooths flat areas while preserving edges (cliff faces, river channels). scipy does not include a bilateral filter. Implementation options:

### 10.1 Pure numpy Implementation

```python
def bilateral_filter_2d(
    heightmap: np.ndarray,
    sigma_space: float = 3.0,
    sigma_range: float = 0.1,
    kernel_size: int = 7,
) -> np.ndarray:
    """Edge-preserving bilateral filter for heightmaps.
    
    Args:
        heightmap: 2D float array, values typically in [0, 1].
        sigma_space: Spatial Gaussian sigma (larger = wider smoothing).
        sigma_range: Range/intensity Gaussian sigma (larger = less edge preservation).
        kernel_size: Must be odd. Window size for the filter.
    
    Returns:
        Filtered heightmap preserving sharp edges.
    """
    padded = np.pad(heightmap, kernel_size // 2, mode='reflect')
    result = np.zeros_like(heightmap)
    rows, cols = heightmap.shape
    half = kernel_size // 2
    
    # Precompute spatial Gaussian weights
    y_offsets, x_offsets = np.mgrid[-half:half+1, -half:half+1]
    spatial_weights = np.exp(-(x_offsets**2 + y_offsets**2) / (2 * sigma_space**2))
    
    for r in range(rows):
        for c in range(cols):
            # Extract local window
            window = padded[r:r + kernel_size, c:c + kernel_size]
            center_val = heightmap[r, c]
            
            # Range weights based on intensity difference
            range_weights = np.exp(-(window - center_val)**2 / (2 * sigma_range**2))
            
            # Combined bilateral weights
            weights = spatial_weights * range_weights
            weights_sum = weights.sum()
            
            if weights_sum > 0:
                result[r, c] = (window * weights).sum() / weights_sum
            else:
                result[r, c] = center_val
    
    return result
```

**Performance:** The naive implementation above is O(N^2 * K^2) where N=resolution and K=kernel_size. For 256x256 with kernel_size=7, this takes ~5-10 seconds in pure Python/numpy.

### 10.2 Vectorized Approximation (Faster)

```python
def fast_bilateral_approx(
    heightmap: np.ndarray,
    sigma_space: float = 3.0,
    sigma_range: float = 0.1,
    iterations: int = 3,
) -> np.ndarray:
    """Fast bilateral filter approximation using iterative Gaussian + edge clamp.
    
    Not a true bilateral filter but produces similar edge-preserving smoothing
    at much higher speed. Suitable for real-time terrain editing.
    """
    result = heightmap.copy()
    for _ in range(iterations):
        smoothed = gaussian_filter(result, sigma=sigma_space)
        # Only apply smoothing where intensity difference is small
        diff = np.abs(smoothed - result)
        blend = np.exp(-(diff**2) / (2 * sigma_range**2))
        result = result * (1 - blend) + smoothed * blend
    return result
```

### 10.3 OpenCV (If Available)

```python
try:
    import cv2
    # cv2.bilateralFilter is highly optimized C++ implementation
    filtered = cv2.bilateralFilter(
        heightmap.astype(np.float32),
        d=9,               # diameter of each pixel neighborhood
        sigmaColor=0.1,    # range sigma
        sigmaSpace=3.0,    # spatial sigma
    )
except ImportError:
    # Fallback to numpy implementation
    filtered = bilateral_filter_2d(heightmap, sigma_space=3.0, sigma_range=0.1)
```

---

## 11. Common Pitfalls

### Pitfall 1: BMesh Element Sequence Reference After Modification
**What goes wrong:** Passing `bm.verts` directly to bmesh.ops that modify geometry causes crashes.
**Why:** BMesh element sequences are invalidated when geometry changes.
**How to avoid:** Always use `bm.verts[:]` (slice copy) when passing to operators.

### Pitfall 2: Missing `ensure_lookup_table()` After BMesh Creation
**What goes wrong:** Accessing `bm.verts[i]` by index crashes or returns wrong vertex.
**Why:** BMesh uses internal hash tables that must be explicitly built.
**How to avoid:** Call `bm.verts.ensure_lookup_table()` after any geometry creation or modification.

### Pitfall 3: foreach_set Array Size Mismatch (Blender 4.1+)
**What goes wrong:** TypeError raised when array doesn't exactly match expected size.
**Why:** Blender 4.1 added strict bounds checking.
**How to avoid:** Always verify `len(array) == len(mesh.vertices) * 3` for coordinates.

### Pitfall 4: vertex_colors Deprecated in Blender 4.0+
**What goes wrong:** Code works but prints deprecation warnings; may break in future versions.
**Why:** Blender 4.0 unified all per-element data under the `attributes` system.
**How to avoid:** Use `mesh.color_attributes.new(name, type='FLOAT_COLOR', domain='CORNER')`.

### Pitfall 5: Gaussian Filter Edge Artifacts
**What goes wrong:** Terrain edges show visible seams or flat strips after smoothing.
**Why:** Default `mode='reflect'` mirrors values at edges, causing artificial plateaus.
**How to avoid:** Use `mode='wrap'` for tileable terrain, `mode='nearest'` for non-tileable terrain edges.

### Pitfall 6: numpy.roll Wrapping at Edges
**What goes wrong:** Erosion algorithms produce artifacts at terrain borders.
**Why:** `np.roll` wraps values around -- the left edge reads from the right edge.
**How to avoid:** After roll operations, mask or clamp border rows/columns. Or pad the heightmap before processing and crop afterward.

### Pitfall 7: Smooth Shading Without Custom Normals
**What goes wrong:** Terrain has faceted appearance despite `use_smooth = True`.
**Why:** Smooth shading interpolates face normals but doesn't account for displacement.
**How to avoid:** After displacing vertices, recalculate normals: `mesh.calc_normals_split()` or use Auto Smooth with angle threshold.

### Pitfall 8: Large Terrain Memory Consumption
**What goes wrong:** 1024x1024 terrain grid = 1M vertices = ~120MB mesh data; Blender becomes unresponsive.
**Why:** Each vertex stores position, normal, and per-loop UV + color data.
**How to avoid:** Use terrain chunking (existing `terrain_chunking.py`). Keep chunks at 256x256 max. Use LOD via Decimate modifier for distant chunks.

---

## 12. Performance Guidelines

| Operation | 128x128 | 256x256 | 512x512 | 1024x1024 |
|-----------|---------|---------|---------|-----------|
| Heightmap generation (numpy fBm) | <0.01s | ~0.05s | ~0.2s | ~0.8s |
| gaussian_filter | <0.01s | <0.01s | ~0.05s | ~0.2s |
| Hydraulic erosion (1000 drops) | ~0.1s | ~0.2s | ~0.3s | ~0.5s |
| bmesh create_grid + Z displace | ~0.1s | ~0.5s | ~3s | ~15s |
| Vertex color painting (per-loop) | ~0.05s | ~0.2s | ~1s | ~5s |
| Material node tree creation | <0.01s | <0.01s | <0.01s | <0.01s |

**Bottleneck:** The bmesh per-vertex Python loop for Z displacement. For 512x512+, consider:
1. foreach_set pattern (Section 1.2)
2. Displace modifier with texture (Section 3.5) 
3. Geometry Nodes displacement (non-destructive)

---

## 13. Additional scipy.ndimage Filters for Terrain

### 13.1 median_filter (Outlier Removal)

```python
from scipy.ndimage import median_filter

# Remove spike artifacts from erosion
cleaned = median_filter(heightmap, size=3)
```

### 13.2 uniform_filter (Box Blur / Averaging)

```python
from scipy.ndimage import uniform_filter

# Fast average smoothing (cheaper than Gaussian)
smoothed = uniform_filter(heightmap, size=5)
```

### 13.3 generic_filter (Custom Operations)

```python
from scipy.ndimage import generic_filter

# Custom: max-minus-min in neighborhood (edge detection)
def local_range(values):
    return values.max() - values.min()

edge_map = generic_filter(heightmap, local_range, size=5)
```

---

## Sources

### Primary (HIGH confidence)
- [Blender Python API - Mesh](https://docs.blender.org/api/current/bpy.types.Mesh.html) - from_pydata, vertices, polygons, foreach_set
- [Blender Python API - BMesh Operators](https://docs.blender.org/api/current/bmesh.ops.html) - create_grid, remove_doubles, recalc_face_normals
- [scipy.ndimage.gaussian_filter](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.gaussian_filter.html) - full signature verified
- [numpy.gradient](https://numpy.org/doc/stable/reference/generated/numpy.gradient.html) - 2D array usage verified
- [scipy.ndimage reference](https://docs.scipy.org/doc/scipy/reference/ndimage.html) - filter catalog
- [numpy array manipulation](https://numpy.org/doc/stable/reference/routines.array-manipulation.html) - roll, pad, reshape

### Codebase (HIGH confidence -- verified in VB source)
- `environment.py` lines 427-478: terrain mesh creation pattern
- `_terrain_noise.py`: heightmap generation, slope computation
- `_terrain_erosion.py`: hydraulic + thermal erosion algorithms
- `terrain_materials.py`: splatmap painting, biome material system
- `terrain_sculpt.py`: brush-based vertex editing
- `terrain_advanced.py`: spline deformation, flow maps, stamps
- `procedural_materials.py`: shader node tree creation patterns

### Secondary (MEDIUM confidence)
- [Blender 4.1 Python API changes](https://developer.blender.org/docs/release_notes/4.1/python_api/) - foreach_set bounds checks
- [Blender Issue #90268](https://developer.blender.org/T90268) - from_pydata numpy array limitation
- [Blender Issue #111117](https://projects.blender.org/blender/blender/issues/111117) - from_pydata quad/tri regression

### Tertiary (LOW confidence -- needs validation)
- Bilateral filter pure-numpy implementation: custom code, no authoritative source. Performance estimates are approximate.
- Performance timings in Section 12: based on general experience with similar operations, not benchmarked on VB codebase specifically.
