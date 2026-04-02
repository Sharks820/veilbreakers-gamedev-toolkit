# Procedural 3D Modeling Best Practices for Blender Python

Research date: 2026-04-01
Sources: Blender Python API docs (Context7), Blender source/manual, web research (2025-2026)

---

## 1. BMesh Best Practices

### 1.1 Efficient Vertex/Face Creation Patterns

**Current toolkit approach**: Pure-Python generators produce `MeshSpec` dicts (vertices + faces lists), then `mesh_from_spec()` in `_mesh_bridge.py` creates BMesh vertex-by-vertex. This is the CORRECT architecture but has optimization opportunities.

**Key pattern - Batch vertex creation with deduplication** (we already do this):
```python
# GOOD: Our current mesh_from_spec pattern with tolerance-based dedup
_WELD_TOLERANCE = 0.005
_vert_dedup: dict[tuple[int, int, int], int] = {}
bm_verts: list = []
for v in verts:
    key = (
        round(v[0] / _WELD_TOLERANCE),
        round(v[1] / _WELD_TOLERANCE),
        round(v[2] / _WELD_TOLERANCE),
    )
    if key in _vert_dedup:
        _remap.append(_vert_dedup[key])
    else:
        idx = len(bm_verts)
        _vert_dedup[key] = idx
        bm_verts.append(bm.verts.new(v))
        _remap.append(idx)
```

**Optimization opportunity - `from_pydata` for initial bulk creation**:
When the mesh has no need for vertex dedup (already clean), `from_pydata` is faster for initial creation because it avoids per-vertex Python function call overhead:
```python
# FASTER for clean data: Use from_pydata, then convert to BMesh for editing
mesh_data = bpy.data.meshes.new(name)
mesh_data.from_pydata(verts, [], faces)
mesh_data.update()

# Only convert to BMesh if you need further manipulation
bm = bmesh.new()
bm.from_mesh(mesh_data)
# ... edits ...
bm.to_mesh(mesh_data)
bm.free()
```

**ACTION**: Add a `clean_geometry=True` flag to `mesh_from_spec()` that uses `from_pydata` path for generators known to produce clean geometry (e.g., parametric weapons, simple furniture), reserving BMesh dedup path for generators that produce overlapping components (stone walls, terrain patches).

### 1.2 Edge Flow for Smooth Shading

**Critical principles**:
- Edges that define silhouette need supporting edge loops within 1-2 edges for SubD compatibility
- Consistent quad flow across curved surfaces prevents shading artifacts
- Edge creases (0.0-1.0) on BMesh provide SubD-friendly hard edges without extra geometry

**Our current support**: `mesh_from_spec` handles `sharp_edges` and `crease_edges` from MeshSpec. Generators should USE these more.

**Actionable pattern for generators**:
```python
# In a generator, mark edges between distinct components as sharp
sharp_edges = []
for i, face in enumerate(faces):
    for j in range(len(face)):
        v_a = face[j]
        v_b = face[(j + 1) % len(face)]
        # If edge connects two components at different angles, mark sharp
        if _angle_between_adjacent_faces(v_a, v_b, faces) > 35.0:
            sharp_edges.append([v_a, v_b])
```

**ACTION**: The `_auto_detect_sharp_edges()` function in `procedural_meshes.py` already does this. Ensure ALL generators call it and include results in their MeshSpec output. Currently many generators skip this.

### 1.3 Avoiding Degenerate Geometry

**Common procedural generation pitfalls**:
- Zero-area faces from coincident vertices (our weld tolerance handles this)
- Flipped normals from inconsistent winding order
- Non-manifold edges from T-junctions where components meet
- Self-intersecting faces from math errors in lathe/extrude operations

**Validation pattern for generators**:
```python
def _validate_mesh_spec(verts, faces):
    """Call before returning MeshSpec to catch issues early."""
    issues = []
    for i, f in enumerate(faces):
        # Check minimum vertex count
        if len(f) < 3:
            issues.append(f"Face {i}: fewer than 3 vertices")
        # Check for duplicate vertex indices in face
        if len(set(f)) != len(f):
            issues.append(f"Face {i}: duplicate vertex indices")
        # Check for valid vertex indices
        for vi in f:
            if vi < 0 or vi >= len(verts):
                issues.append(f"Face {i}: vertex index {vi} out of range")
    return issues
```

**ACTION**: Add `_validate_mesh_spec()` as a debug helper in `procedural_meshes.py` that generators can call during development.

### 1.4 Boolean Operations That Produce Clean Topology

**Blender's Boolean modifier** has two solvers:
- **Fast**: Quick but produces errors with complex shapes
- **Exact**: Robust, accurate, slower -- USE THIS for game assets

**Post-boolean cleanup pipeline** (we have `post_boolean_cleanup` in `_mesh_bridge.py`):
1. Remove doubles (`bmesh.ops.remove_doubles`)
2. Recalculate normals (`bmesh.ops.recalc_face_normals`)
3. Dissolve degenerate faces (`bmesh.ops.dissolve_degenerate`)
4. Fill holes if needed (`bmesh.ops.holes_fill`)
5. Optionally: Limited dissolve to reduce unnecessary geometry (`bmesh.ops.dissolve_limit`)

**Best practice for procedural booleans**:
```python
# Use exact solver
bool_mod = obj.modifiers.new("Bool", 'BOOLEAN')
bool_mod.solver = 'EXACT'
bool_mod.operation = 'DIFFERENCE'  # or UNION, INTERSECT
bool_mod.object = cutter_obj

# Apply and clean up
bpy.ops.object.modifier_apply(modifier=bool_mod.name)

# Post-cleanup with BMesh
bm = bmesh.new()
bm.from_mesh(obj.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bmesh.ops.dissolve_degenerate(bm, dist=0.001, edges=bm.edges[:])
bm.to_mesh(obj.data)
bm.free()
```

**ACTION**: Ensure `handle_boolean_op` in `mesh.py` uses `solver='EXACT'` by default. Add `dissolve_degenerate` to cleanup pipeline.

### 1.5 Bevel/Chamfer for Hard Surface Modeling

**bmesh.ops.bevel parameters** (from Blender API docs):
```python
result = bmesh.ops.bevel(
    bm,
    geom=edges_to_bevel,       # Selected edges/verts
    offset=0.02,                # Bevel width
    offset_type='WIDTH',        # WIDTH, OFFSET, DEPTH, PERCENT, ABSOLUTE
    segments=3,                 # Smoothness (3 is good for game assets, 1 for hard chamfer)
    profile=0.5,                # 0.5 = round, <0.5 = concave, >0.5 = convex
    affect='EDGES',             # EDGES or VERTICES
    clamp_overlap=True,         # Prevent self-intersection
    harden_normals=True,        # Critical for smooth shading on hard edges
    mark_seam=True,             # UV seam along bevel
    mark_sharp=False,           # Don't mark bevel edges sharp (defeats purpose)
    miter_outer='ARC',          # ARC for clean outer corners
    miter_inner='ARC',          # ARC for clean inner corners
)
```

**Profile values for game assets**:
- `0.5` = standard round bevel (default, most common)
- `1.0` = sharp convex bevel (catches light on edges)
- `0.25` = concave chamfer (grooves, channels)

**ACTION**: Create a utility function `bevel_hard_edges()` that applies bmesh bevel to edges detected by dihedral angle:
```python
def bevel_hard_edges(bm, angle_threshold=30.0, offset=0.02, segments=2):
    """Bevel edges with dihedral angle > threshold."""
    threshold = math.radians(angle_threshold)
    edges_to_bevel = []
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            angle = edge.calc_face_angle(0)
            if angle > threshold:
                edges_to_bevel.append(edge)
    if edges_to_bevel:
        bmesh.ops.bevel(
            bm, geom=edges_to_bevel,
            offset=offset, offset_type='WIDTH',
            segments=segments, profile=0.5,
            affect='EDGES', clamp_overlap=True,
            harden_normals=True, mark_seam=True,
        )
```

### 1.6 Subdivision Surface Friendly Topology

**Rules for SubD-friendly procedural meshes**:
1. All quads (no triangles, no n-gons)
2. Even edge distribution (no extreme size differences between adjacent faces)
3. Edge loops that define features must be closed
4. Support loops (holding edges) 1-2 edges from hard edges
5. Maximum 5-valence poles (vertices with 5 connected edges)

**Practical pattern for generators**:
```python
# BAD: Triangle fan at top of cylinder (common in lathe operations)
# Creates an n-gon pole that subdivides poorly
for i in range(segments):
    faces.append((top_vert, ring[i], ring[(i+1) % segments]))

# GOOD: Quad cap using concentric rings
# Create inner ring at 50% radius for quad cap
inner_ring_start = len(verts)
for i in range(segments):
    cos_a, sin_a = trig_table[i]
    verts.append((cos_a * radius * 0.3, sin_a * radius * 0.3, height))
# Connect outer ring to inner ring with quads
for i in range(segments):
    next_i = (i + 1) % segments
    faces.append((ring[i], ring[next_i],
                   inner_ring_start + next_i, inner_ring_start + i))
# Then fill inner ring with smaller quad ring or a small n-gon (acceptable if <6 sides)
```

**ACTION**: Audit all lathe/revolution generators in `procedural_meshes.py` for triangle fan caps. Replace with quad-cap pattern where segment count > 6.

---

## 2. Geometry Nodes vs BMesh

### 2.1 When to Use Each

| Use Case | BMesh (Python) | Geometry Nodes |
|----------|---------------|----------------|
| Parametric single-asset generation | BEST | Good |
| Batch scene population (scatter) | Poor | BEST |
| Complex boolean/bevel operations | BEST | Limited |
| Runtime/game-engine compatible | N/A | Depends |
| Instancing thousands of objects | Poor | BEST (10-100x faster) |
| Precise vertex-level control | BEST | Possible but verbose |
| Animation-driven deformation | Limited | BEST |
| Asset pipeline automation | BEST | Needs Python bridge |

### 2.2 Performance Comparison

- **Geometry Nodes**: Up to 4x improvement with Set Position node, 100x memory reduction for large fields, 10x improvement from multi-threading. Ideal for scatter, instancing, and procedural placement.
- **BMesh Python**: Each mesh element creation is a separate Python call. Slower for bulk creation but provides precise control. Best for generators that need exact vertex placement.

### 2.3 Driving Geometry Nodes from Python

Yes, fully possible and we already have `geometry_nodes.py` handler:
```python
import bpy

# Create a Geometry Nodes modifier
obj = bpy.context.active_object
mod = obj.modifiers.new("GeoNodes", 'NODES')

# Create node tree
tree = bpy.data.node_groups.new("Procedural_Scatter", 'GeometryNodeTree')

# Create nodes programmatically
input_node = tree.nodes.new('NodeGroupInput')
output_node = tree.nodes.new('NodeGroupOutput')
distribute = tree.nodes.new('GeometryNodeDistributePointsOnFaces')
instance = tree.nodes.new('GeometryNodeInstanceOnPoints')

# Connect nodes
tree.links.new(input_node.outputs[0], distribute.inputs[0])
tree.links.new(distribute.outputs[0], instance.inputs[0])
tree.links.new(instance.outputs[0], output_node.inputs[0])

# Set parameters
distribute.inputs['Density'].default_value = 10.0

# Assign to modifier
mod.node_group = tree
```

### 2.4 Recommended Hybrid Approach

**For our toolkit**:
1. **BMesh/MeshSpec generators** for individual asset creation (weapons, furniture, architecture)
2. **Geometry Nodes** for scene composition (vegetation scatter, prop placement, dungeon layout)
3. **Python-driven Geometry Nodes** for parametric scatter systems that need seed control

**ACTION**: Our `environment_scatter.py` and `vegetation_system.py` should use Geometry Nodes for scatter operations instead of creating individual objects. This would give 10-100x performance improvement for populated scenes.

---

## 3. Game-Ready Topology

### 3.1 Quad-Dominant Mesh Requirements

- Work in quads, triangulate at export time (much easier to convert quads->tris than reverse)
- Avoid n-gons entirely in deforming meshes (characters, creatures, doors)
- Triangles acceptable in non-deforming props if they don't cause shading artifacts
- Edge loops must follow deformation paths (joints, hinges, muscles)

### 3.2 Poly Budget Guidelines

| Asset Type | Mobile (tris) | PC/Console (tris) | Next-Gen (tris) |
|------------|---------------|--------------------|--------------------|
| Small prop (potion, key) | 100-500 | 500-2,000 | 2,000-5,000 |
| Medium prop (chair, chest) | 500-2,000 | 2,000-8,000 | 8,000-15,000 |
| Large prop (cart, fountain) | 2,000-5,000 | 5,000-15,000 | 15,000-30,000 |
| Weapon (equipped, visible) | 1,000-3,000 | 3,000-10,000 | 10,000-25,000 |
| Character (full body) | 5,000-15,000 | 15,000-50,000 | 50,000-100,000 |
| Building exterior | 3,000-10,000 | 10,000-30,000 | 30,000-80,000 |
| Environment hero piece | 5,000-15,000 | 15,000-50,000 | 50,000-150,000 |

**ACTION**: Add these budgets to our `game_check` handler as configurable quality targets. Our `SceneBudgetValidator` in `lod_pipeline.py` should reference these.

### 3.3 LOD Generation Techniques

**Decimate Modifier** (automated, good for props):
```python
# Collapse-based decimation (best for organic shapes)
mod = obj.modifiers.new("Decimate_LOD", 'DECIMATE')
mod.decimate_type = 'COLLAPSE'
mod.ratio = 0.5  # 50% reduction
# Optional: Protect UV seams and sharp edges
mod.use_collapse_triangulate = False

# Planar decimation (best for architectural assets)
mod.decimate_type = 'DISSOLVE'
mod.angle_limit = math.radians(5.0)  # Dissolve faces within 5 degrees
```

**QuadriFlow Remesh** (best for characters/organic, we already support this in mesh.py):
```python
bpy.ops.object.quadriflow_remesh(
    target_faces=5000,
    use_preserve_sharp=True,
    use_preserve_boundary=True,
    use_mesh_symmetry=True,
)
```

**Voxel Remesh** (fastest, uniform grid, good for quick LODs):
```python
bpy.context.object.data.remesh_voxel_size = 0.05
bpy.ops.object.voxel_remesh()
```

**LOD chain generation pattern**:
```python
def generate_lod_chain(obj, ratios=[1.0, 0.5, 0.25, 0.1]):
    """Generate LOD0-LOD3 from a source mesh."""
    lods = [obj]  # LOD0 is original
    for i, ratio in enumerate(ratios[1:], 1):
        lod = obj.copy()
        lod.data = obj.data.copy()
        lod.name = f"{obj.name}_LOD{i}"
        bpy.context.collection.objects.link(lod)
        mod = lod.modifiers.new("Decimate", 'DECIMATE')
        mod.ratio = ratio
        bpy.context.view_layer.objects.active = lod
        bpy.ops.object.modifier_apply(modifier=mod.name)
        lods.append(lod)
    return lods
```

**ACTION**: Our `lod_pipeline.py` should expose a `generate_lod_chain` action that creates all LODs in one call.

### 3.4 Normal Map Baking (High to Low Poly)

**Pipeline for procedural assets**:
1. Generate high-poly mesh (full detail, SubD)
2. Generate low-poly mesh (game-ready budget)
3. UV unwrap low-poly
4. Bake normals from high to low

```python
# Set up bake
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.bake_type = 'NORMAL'
bpy.context.scene.render.bake.use_selected_to_active = True
bpy.context.scene.render.bake.cage_extrusion = 0.02

# Select high-poly, make low-poly active
high_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly

# Create image for bake target
img = bpy.data.images.new("Normal_Bake", 2048, 2048)
# Assign to material node (Image Texture node must be selected)

bpy.ops.object.bake(type='NORMAL')
```

### 3.5 UV Island Strategies for Game Assets

- **Hard edges = UV seams**: Every sharp edge should be a UV seam
- **Minimize UV island count**: Fewer islands = less texture waste
- **Consistent texel density**: All UV islands should have similar pixel/unit ratios
- **Padding**: 4-8 pixels between islands at 2K resolution to prevent bleeding
- **Straighten UV islands**: For architectural assets, straight UV edges reduce texture waste

**ACTION**: Our `blender_uv` handlers should auto-mark sharp edges as seams before unwrapping. This is standard AAA practice.

---

## 4. Procedural Detailing Techniques

### 4.1 Surface Detail Without Excessive Geometry

**Principle**: Use geometry for silhouette, normal/displacement maps for surface detail.

**Normal map from procedural shader** (no extra geometry):
```python
# Create bump node chain for surface detail
mat = bpy.data.materials.new("Surface_Detail")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Noise texture -> Bump -> Normal input
noise = nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 50.0
noise.inputs['Detail'].default_value = 8.0

bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.3

links.new(noise.outputs['Fac'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], nodes['Principled BSDF'].inputs['Normal'])
```

**Displacement modifier for medium-scale detail**:
```python
# Add displacement modifier driven by texture
mod = obj.modifiers.new("Detail_Disp", 'DISPLACE')
mod.strength = 0.05
tex = bpy.data.textures.new("Detail_Tex", 'CLOUDS')
tex.noise_scale = 0.5
mod.texture = tex
```

### 4.2 Procedural Wear/Damage

**Edge wear using Pointiness attribute** (shader-based, zero geometry cost):
```python
# In shader nodes:
# Geometry node (Pointiness output) -> ColorRamp -> Mix with worn material
geom = nodes.new('ShaderNodeNewGeometry')
ramp = nodes.new('ShaderNodeValToRGB')
# Narrow ramp to isolate edges
ramp.color_ramp.elements[0].position = 0.45
ramp.color_ramp.elements[1].position = 0.55
links.new(geom.outputs['Pointiness'], ramp.inputs['Fac'])
```

**Procedural scratches** (Voronoi + Wave textures):
```python
# Voronoi texture in "Distance to Edge" mode creates scratch-like patterns
voronoi = nodes.new('ShaderNodeTexVoronoi')
voronoi.feature = 'DISTANCE_TO_EDGE'
voronoi.inputs['Scale'].default_value = 20.0
# Stretch along one axis using Mapping node for directional scratches
mapping = nodes.new('ShaderNodeMapping')
mapping.inputs['Scale'].default_value = (1.0, 10.0, 1.0)
```

**Procedural dents** (Musgrave + spherical gradient masking):
```python
# Musgrave for organic dent shapes
musgrave = nodes.new('ShaderNodeTexMusgrave')
musgrave.musgrave_type = 'RIDGED_MULTIFRACTAL'
musgrave.inputs['Scale'].default_value = 3.0
musgrave.inputs['Detail'].default_value = 4.0
# Mix with random object-seeded position for unique dents per instance
```

### 4.3 Ornamental Detail Generation

**For dark fantasy ornamental detail (scrollwork, filigree, runes)**:

**Approach 1 - Decal system** (our `decal_system.py`):
- Pre-generate ornament meshes as flat planes
- Project onto surfaces using shrinkwrap
- Bake to normal map
- Zero runtime geometry cost

**Approach 2 - Curve-based ornaments**:
```python
# Generate ornamental curves procedurally
curve = bpy.data.curves.new("Scrollwork", 'CURVE')
curve.dimensions = '3D'
spline = curve.splines.new('BEZIER')

# Spiral/scroll pattern
for i in range(20):
    t = i / 19.0
    r = 0.1 * (1 - t)
    angle = t * 4 * math.pi
    point = spline.bezier_points[i] if i < len(spline.bezier_points) else None
    if point is None:
        spline.bezier_points.add(1)
        point = spline.bezier_points[-1]
    point.co = (r * math.cos(angle), r * math.sin(angle), 0)

# Convert to mesh with bevel
curve.bevel_depth = 0.005
curve.bevel_resolution = 2
bpy.ops.object.convert(target='MESH')
```

**Approach 3 - Geometry Nodes for repeating patterns**:
```python
# Distribute ornamental elements along edges
# Use Geometry Nodes: Mesh to Curve -> Resample -> Instance on Points
# With rotation aligned to edge tangent
```

### 4.4 How AAA Studios Handle Procedural Detail

1. **High-poly sculpt -> Bake to low-poly**: Primary workflow (ZBrush/Blender sculpt)
2. **Trim sheets**: Reusable detail strips baked to textures, mapped via custom UVs
3. **Decal systems**: Projected detail layers (what our decal_system.py does)
4. **Tiling materials**: Procedural materials with unique detail masked per-asset
5. **Geometry Nodes scatter**: For environmental detail (rubble, foliage, debris)

**ACTION**: Implement trim sheet support -- generate a library of dark fantasy trim textures (stone borders, iron bands, wood carvings) and provide UV mapping tools to apply them to assets.

---

## 5. Performance

### 5.1 Batch Operations vs Individual Operations

**Critical rule**: Minimize Python-to-Blender round trips.

```python
# BAD: Individual operations per vertex
for v in bm.verts:
    bmesh.ops.translate(bm, verts=[v], vec=(0, 0, 1))

# GOOD: Single batch operation
bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, 1))
```

```python
# BAD: Multiple modifier applications one at a time
for mod_name in modifier_list:
    bpy.ops.object.modifier_apply(modifier=mod_name)

# GOOD: Apply all modifiers in order
for mod in obj.modifiers:
    bpy.ops.object.modifier_apply(modifier=mod.name)
```

**Mesh data access optimization**:
```python
# BAD: Accessing mesh data repeatedly
for i in range(len(mesh.vertices)):
    x = mesh.vertices[i].co.x
    y = mesh.vertices[i].co.y

# GOOD: Use foreach_get for bulk data access
import numpy as np
coords = np.empty(len(mesh.vertices) * 3)
mesh.vertices.foreach_get("co", coords)
coords = coords.reshape(-1, 3)
```

### 5.2 Memory Management for Large Scenes

```python
# Always free BMesh when done
bm = bmesh.new()
try:
    bm.from_mesh(obj.data)
    # ... operations ...
    bm.to_mesh(obj.data)
finally:
    bm.free()  # CRITICAL: Prevents memory leak

# Clear unused data blocks periodically
bpy.ops.outliner.orphans_purge(do_recursive=True)

# For large batch operations, process and free incrementally
for spec in mesh_specs:
    obj = mesh_from_spec(spec)
    # Don't hold references to all objects simultaneously
```

### 5.3 Instancing for Repeated Elements

**Linked duplicates** (Alt+D equivalent in Python):
```python
# Share mesh data between duplicates -- near-zero memory per instance
original = bpy.data.objects['Tree_Template']
for pos in scatter_positions:
    instance = bpy.data.objects.new(f"Tree_{i}", original.data)  # Same mesh data!
    instance.location = pos
    instance.rotation_euler.z = random.uniform(0, 2 * math.pi)
    collection.objects.link(instance)
```

**Collection instances** (best for complex multi-object assets):
```python
# Create template collection
template_col = bpy.data.collections.new("Building_Template")
# ... add objects to template_col ...

# Instance the entire collection
for pos in building_positions:
    empty = bpy.data.objects.new(f"Building_{i}", None)
    empty.instance_type = 'COLLECTION'
    empty.instance_collection = template_col
    empty.location = pos
    scene_col.objects.link(empty)
```

**ACTION**: Our `environment_scatter.py` and `worldbuilding.py` should use linked duplicates instead of full mesh copies. This would reduce memory usage by 10-100x for populated scenes.

### 5.4 Scene Cleanup and Optimization

```python
def optimize_scene():
    """Full scene optimization pass."""
    # 1. Remove doubles on all mesh objects
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
            bm.to_mesh(obj.data)
            bm.free()

    # 2. Purge orphaned data
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # 3. Recalculate normals
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(obj.data)
            bm.free()

    # 4. Apply scale on all objects (prevents export issues)
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)
```

---

## 6. Priority Actions for Our Toolkit

### Immediate (High Impact, Low Effort)

1. **Add `from_pydata` fast path** to `mesh_from_spec()` for clean generators -- skip BMesh dedup when not needed
2. **Ensure all generators call `_auto_detect_sharp_edges()`** -- many currently skip it
3. **Use linked duplicates in scatter operations** -- 10-100x memory savings
4. **Add `dissolve_degenerate` to boolean cleanup** -- prevents artifacts
5. **Auto-mark sharp edges as UV seams** before unwrapping

### Medium Term (High Impact, Medium Effort)

6. **Replace triangle-fan caps with quad caps** in all lathe generators
7. **Use Geometry Nodes for scatter** instead of individual object creation
8. **Implement LOD chain generation** as a single action
9. **Add poly budget validation** per asset type to `game_check`
10. **Create `bevel_hard_edges()` utility** for automatic edge beveling in mesh_from_spec

### Long Term (AAA Quality)

11. **Trim sheet system** -- reusable detail textures for dark fantasy assets
12. **Normal map bake pipeline** -- high-to-low automated baking
13. **Procedural wear/damage materials** -- edge wear, scratches, dents as shader nodes
14. **Ornamental detail library** -- scrollwork, filigree, rune curves for dark fantasy
15. **numpy-based mesh data access** -- for operations on very large meshes (10K+ verts)

---

## Sources

- [Blender Python API - BMesh Operators](https://docs.blender.org/api/current/bmesh.ops.html)
- [Blender Python API - BMesh Module](https://docs.blender.org/api/current/bmesh.html)
- [Blender Python API - BevelModifier](https://docs.blender.org/api/current/bpy.types.BevelModifier.html)
- [Blender Python API - DecimateModifier](https://docs.blender.org/api/current/bpy.types.DecimateModifier.html)
- [Blender Python API - Mesh Operators](https://docs.blender.org/api/current/bpy.ops.mesh.html)
- [Blender 5.1 Manual - Boolean Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html)
- [Blender 5.1 Manual - Bevel](https://docs.blender.org/manual/en/latest/modeling/meshes/editing/edge/bevel.html)
- [Blender 5.1 Manual - Displacement](https://docs.blender.org/manual/en/latest/render/materials/components/displacement.html)
- [Blender Conference 2024: Mastering Topology and Retopology](https://digitalproduction.com/2024/11/11/blender-conference-2024-mastering-topology-and-retopology/)
- [Blender Procedural Cities: Python vs Geometry Nodes](https://lonedevr.com/2022/03/20/blender-procedural-cities-python-vs-geometry-nodes/)
- [Blender 3D Modeling for Games: Complete Guide 2025](https://generalistprogrammer.com/tutorials/blender-3d-modeling-games-complete-guide)
- [The Art of Good Topology Guide - CG Cookie](https://cgcookie.com/posts/the-art-of-good-topology-blender)
- [Clean Topology in Blender - CG Cookie](https://cgcookie.com/posts/guide-to-clean-topology)
- [Mesh Topology for High-Performance 3D Models - Meshy](https://www.meshy.ai/blog/mesh-topology)
- [Topology for Game-Ready Assets - Gameaning Studio](https://www.gameaningstudios.com/topology-for-game-ready-assets/)
- [Mastering Mesh Cleanup After Boolean Operations](https://toxigon.com/blender-clean-up-mesh-after-boolean)
- [Blender Boolean Workflow Guide](https://hyper-casual.games/blog/blender-boolean-workflow)
- [Boolean Cleanup - MESHmachine](https://machin3.io/MESHmachine/docs/boolean_cleanup/)
- [How to Script Geometry Nodes in Blender with Python (2026)](https://blog.cg-wire.com/blender-scripting-geometry-nodes-2/)
- [Procedural Edge Wear Techniques in Blender](https://www.scribd.com/document/490006740/Procedural-wear-from-A-to-Z-in-Blender-pdf)
- [Procedural Worn Edges in Blender - BlenderNation](https://www.blendernation.com/2020/07/28/procedural-worn-edges-in-blender/)
- [Blender Python Optimization - Wikibooks](https://en.wikibooks.org/wiki/Blender_3D:_Blending_Into_Python/Optimize)
- [Geometry Nodes Performance - Blender Developer](https://developer.blender.org/docs/release_notes/3.1/nodes_physics/)
- [geonodes - Create Geometry Nodes with Python](https://github.com/al1brn/geonodes)
- [Replacement-based Procedural Modelling Proposal](https://devtalk.blender.org/t/replacement-based-procedural-modelling-proposal/31851)
