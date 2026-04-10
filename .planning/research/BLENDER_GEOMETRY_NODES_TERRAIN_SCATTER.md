# Blender Geometry Nodes for Terrain Scatter — Deep Technical Reference

**Scope:** Python (bpy) construction of Geometry Nodes graphs for terrain scatter, layering,
and rock-kit placement in an automated pipeline.

**Blender target:** 4.2+ LTS (code is forward-compatible through 4.5 LTS and 5.x as of writing).
All examples use the `node_group.interface.new_socket(...)` API introduced in Blender 4.0 — the
pre-4.0 `inputs.new()/outputs.new()` API is **deprecated** and will crash on 4.x.

**Coordinate system reminder:** Blender is **Z-up**. Every "up" reference in this document means
`+Z`. Do not use `+Y`. (See `feedback_blender_z_up.md`.)

**Related project files:**
- `Tools/mcp-toolkit/blender_addon/handlers/geometry_nodes.py` — existing scatter/boolean/array
  preset generators, uses the 4.x interface API correctly. Reuse patterns from there.
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py`,
  `Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py` — terrain pipeline integration
  points.

---

## 0. Conceptual model

A Geometry Nodes scatter modifier is a **node group** attached to a mesh via a `NODES`-type
modifier. The graph has a `Group Input` (the object's own geometry enters here), any number of
processing nodes, and a `Group Output`. Blender evaluates the graph once per frame and replaces
the object's evaluated geometry with the output.

```
[Terrain mesh] -> Group Input -> Distribute -> Instance on Points -> Join -> Group Output
                               \___________________________________/
                                      scatter subgraph
                      (terrain mesh is joined back to preserve the visible ground)
```

Key architectural rules:
1. **The terrain mesh must be joined back into the output** or the modifier will visually replace
   the terrain with only the instances. Use `GeometryNodeJoinGeometry`.
2. **Instances are cheap — realized geometry is not.** Never `Realize Instances` for scatter
   unless you are baking for export. Instances keep memory O(unique assets), realized mesh is
   O(total scatter count).
3. **Masks are floats**, typically in `[0, 1]`. Multiply them into the `Density Factor` input of
   `Distribute Points on Faces` — do NOT gate with Switch/IF, use continuous multiply.
4. **Alignment happens on instances**, not points. Compute a rotation from the captured normal
   then feed it to `Instance on Points`' `Rotation` socket (or, equivalently, to a downstream
   `Rotate Instances` node if you need additive tilt).

---

## 1. Creating Geometry Nodes setups from Python

### 1.1 Minimum viable node group

```python
import bpy

# 1. Create the tree itself (empty — just Input/Output)
tree = bpy.data.node_groups.new(name="GN_MyScatter", type='GeometryNodeTree')

# 2. Add interface sockets (Blender 4.x API)
tree.interface.new_socket(
    name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry',
)
tree.interface.new_socket(
    name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry',
)

# 3. Create Group Input / Group Output nodes
group_in = tree.nodes.new('NodeGroupInput')
group_in.location = (-800, 0)
group_out = tree.nodes.new('NodeGroupOutput')
group_out.location = (800, 0)

# 4. Pass-through link (so the modifier returns the unmodified mesh)
tree.links.new(group_in.outputs['Geometry'], group_out.inputs['Geometry'])

# 5. Attach to an object as a modifier
obj = bpy.data.objects['Terrain']
mod = obj.modifiers.new(name="GN_MyScatter", type='NODES')
mod.node_group = tree
```

### 1.2 Interface API (Blender 4.x)

`NodeTreeInterface.new_socket()` signature:

```python
tree.interface.new_socket(
    name="Density",                    # label shown in modifier panel
    in_out='INPUT',                    # 'INPUT' or 'OUTPUT'
    socket_type='NodeSocketFloat',     # class name of the socket type
    description="Points per m^2",      # optional tooltip
    parent=None,                       # optional NodePanel for grouping
)
```

Returns a `NodeTreeInterfaceSocket`. You can then set:

```python
sock = tree.interface.new_socket("Density", in_out='INPUT', socket_type='NodeSocketFloat')
sock.default_value = 0.1
sock.min_value = 0.0      # note: may not hard-clamp the modifier UI (Blender bug)
sock.max_value = 100.0
sock.hide_in_modifier = False
```

Common socket types for terrain scatter:

| Socket class              | Purpose                                    |
|---------------------------|--------------------------------------------|
| `NodeSocketGeometry`      | Geometry in/out (always required)          |
| `NodeSocketFloat`         | Density, slope thresholds, scale, etc.     |
| `NodeSocketFloatFactor`   | 0..1 fraction (slider with clamp)          |
| `NodeSocketFloatAngle`    | Angles in radians (shown as degrees in UI) |
| `NodeSocketFloatDistance` | Lengths in meters                          |
| `NodeSocketInt`           | Seed, count                                |
| `NodeSocketVector`        | Direction, scale vector                    |
| `NodeSocketBool`          | Toggles                                    |
| `NodeSocketColor`         | RGBA                                       |
| `NodeSocketObject`        | Target object picker                       |
| `NodeSocketCollection`    | Asset collection picker (kit pieces)       |
| `NodeSocketImage`         | Mask image                                 |

The `socket_type` string is the `bpy.types` class name, not the identifier inside the node.

### 1.3 Ordering inputs after creation

`new_socket()` appends to the end. To reorder, use:

```python
tree.interface.move(socket_item, to_index)
```

Or prefer to create sockets in the order you want them to appear in the modifier panel.

### 1.4 Setting modifier-panel inputs from Python

Once the node group is assigned, the modifier stores values keyed by the **socket identifier**
(which looks like `Socket_2`, `Input_3`, etc.), not by the name. Best practice:

```python
mod = obj.modifiers.new(name="GN_Scatter", type='NODES')
mod.node_group = tree

# Iterate interface items and set by name
for item in tree.interface.items_tree:
    if item.item_type != 'SOCKET':
        continue
    if item.in_out != 'INPUT':
        continue
    if item.name == "Density":
        mod[item.identifier] = 0.25
    elif item.name == "Seed":
        mod[item.identifier] = 42
    elif item.name == "Rocks":
        mod[item.identifier] = bpy.data.collections["RockKit"]
```

Setting `mod["Input_2"] = 0.25` is brittle across Blender versions — always look up the
identifier by name.

### 1.5 Full working example: "scatter rocks on terrain surface"

See section 8 for the full production-grade function. The short version:

```python
import bpy

def build_basic_scatter(terrain, instance_obj, density=0.1, seed=42):
    tree = bpy.data.node_groups.new("GN_BasicScatter", 'GeometryNodeTree')

    tree.interface.new_socket('Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    n_in   = tree.nodes.new('NodeGroupInput');  n_in.location  = (-800, 0)
    n_out  = tree.nodes.new('NodeGroupOutput'); n_out.location = ( 800, 0)

    distrib = tree.nodes.new('GeometryNodeDistributePointsOnFaces')
    distrib.location = (-400, 0)
    distrib.distribute_method = 'POISSON'
    distrib.inputs['Density Max'].default_value = density
    distrib.inputs['Distance Min'].default_value = 0.5
    distrib.inputs['Seed'].default_value = seed

    obj_info = tree.nodes.new('GeometryNodeObjectInfo')
    obj_info.location = (-400, -300)
    obj_info.inputs['Object'].default_value = instance_obj
    obj_info.transform_space = 'RELATIVE'

    iop = tree.nodes.new('GeometryNodeInstanceOnPoints')
    iop.location = (0, 0)

    join = tree.nodes.new('GeometryNodeJoinGeometry')
    join.location = (400, 0)

    L = tree.links.new
    L(n_in.outputs['Geometry'],      distrib.inputs['Mesh'])
    L(distrib.outputs['Points'],     iop.inputs['Points'])
    L(obj_info.outputs['Geometry'],  iop.inputs['Instance'])
    L(n_in.outputs['Geometry'],      join.inputs['Geometry'])   # terrain first
    L(iop.outputs['Instances'],      join.inputs['Geometry'])   # instances second
    L(join.outputs['Geometry'],      n_out.inputs['Geometry'])

    mod = terrain.modifiers.new("GN_BasicScatter", type='NODES')
    mod.node_group = tree
    return mod
```

---

## 2. Essential scatter nodes

All node type strings below are exact identifiers you pass to `tree.nodes.new(...)`.

### 2.1 `GeometryNodeDistributePointsOnFaces`

**Purpose:** Generate scatter points on the faces of an input mesh.

**Modes** (`node.distribute_method`):
- `'RANDOM'` — uniform random, fast, cheap.
- `'POISSON'` — Poisson-disk, enforces a minimum distance between points, blue-noise
  distribution. Slightly more expensive but vastly better-looking.

**Inputs (sockets):**
| Socket         | Type   | Notes                                                        |
|----------------|--------|--------------------------------------------------------------|
| `Mesh`         | Geom   | Surface to scatter on.                                       |
| `Selection`    | Bool   | Per-face mask. Exclude faces where this is False.            |
| `Distance Min` | Float  | **POISSON only.** Minimum distance between points.           |
| `Density Max`  | Float  | **POISSON only.** Maximum density points/m^2 before culling. |
| `Density`      | Float  | **RANDOM only.** Absolute density points/m^2.                |
| `Density Factor` | Float| Per-point multiplier (0..1) — this is your **mask input**.   |
| `Seed`         | Int    | RNG seed.                                                    |

**Outputs:**
- `Points` — a point cloud (with implicit `normal` and `rotation` attributes per point).
- `Normal` — per-point surface normal (field).
- `Rotation` — per-point rotation, already aligned to the surface. **This is the single best
  shortcut for alignment — feed it directly into Instance on Points' Rotation socket and you
  get free normal alignment.**

**Code:**
```python
distrib = tree.nodes.new('GeometryNodeDistributePointsOnFaces')
distrib.distribute_method = 'POISSON'
distrib.inputs['Density Max'].default_value = 0.2     # points/m^2 cap
distrib.inputs['Distance Min'].default_value = 0.4    # meters
distrib.inputs['Seed'].default_value = 42
```

### 2.2 `GeometryNodeInstanceOnPoints`

**Purpose:** Create one instance per point.

**Inputs:**
| Socket           | Type    | Notes                                                 |
|------------------|---------|-------------------------------------------------------|
| `Points`         | Geom    | From Distribute.                                      |
| `Selection`      | Bool    | Per-point mask.                                       |
| `Instance`       | Geom    | A single instance, OR a collection (with Pick).       |
| `Pick Instance`  | Bool    | If True and Instance is a collection, pick randomly.  |
| `Instance Index` | Int     | Index within the collection (field — per-point).      |
| `Rotation`       | Vector  | Euler rotation per instance.                          |
| `Scale`          | Vector  | Scale vector (x, y, z) per instance.                  |

**Output:** `Instances` — a point cloud of instance references (cheap).

```python
iop = tree.nodes.new('GeometryNodeInstanceOnPoints')
iop.inputs['Pick Instance'].default_value = True   # for collection picking
```

### 2.3 `GeometryNodeRotateInstances`

**Purpose:** Apply **additional** rotation to instances (on top of any rotation from IoP).
Critical for adding random tilt around Z after aligning to normal.

**Inputs:**
| Socket        | Type    | Notes                                       |
|---------------|---------|---------------------------------------------|
| `Instances`   | Geom    |                                             |
| `Rotation`    | Vector  | Euler rotation to apply.                    |
| `Pivot Point` | Vector  | Defaults to instance origin.                |
| `Local Space` | Bool    | True = rotate in instance-local space.      |

```python
rot = tree.nodes.new('GeometryNodeRotateInstances')
rot.inputs['Local Space'].default_value = True
```

### 2.4 `GeometryNodeScaleInstances`

**Purpose:** Apply scale to instances. Combine with `FunctionNodeRandomValue` for per-instance
scale variation.

```python
scale_node = tree.nodes.new('GeometryNodeScaleInstances')
# connect a FunctionNodeRandomValue(type='FLOAT_VECTOR') to the Scale socket
```

### 2.5 `GeometryNodeRealizeInstances`

**Purpose:** Convert instances to real mesh geometry.

**WHEN TO USE:** almost never in a scatter graph. Only right before an export-bake step, or if
you need a downstream node that does not accept instances (e.g., a mesh boolean).

**Cost:** O(instance_count * vertices_per_instance). On a map with 50k rocks at 500 verts each,
realizing produces 25M verts and collapses viewport/eevee performance.

```python
realize = tree.nodes.new('GeometryNodeRealizeInstances')   # add only if baking
```

### 2.6 `ShaderNodeTexImage` / `GeometryNodeImageTexture`

**Purpose:** Sample an image texture as a density mask. Use `GeometryNodeImageTexture` (the GN
variant, not the shader one) for mask-in-graph workflows.

```python
img_tex = tree.nodes.new('GeometryNodeImageTexture')
img_tex.inputs['Image'].default_value = bpy.data.images['rock_density_mask']
img_tex.interpolation = 'Linear'
img_tex.extension = 'REPEAT'
# Feed a UV-like Vector (e.g. XY from Position via SeparateXYZ -> CombineXYZ) into 'Vector'
# Use the 'Color' output as a mask -> multiply into Distribute's 'Density Factor'.
```

For texture painting on the terrain itself, use `GeometryNodeInputNamedAttribute` to sample a
vertex color layer (see section 6.2).

### 2.7 `GeometryNodeCaptureAttribute`

**Purpose:** Read a field (normal, position, etc.) on one domain and carry it forward through
subsequent nodes that change topology. Without Capture, a downstream normal read from a point
cloud gives undefined results.

**Common pattern for terrain scatter:**
```python
capture = tree.nodes.new('GeometryNodeCaptureAttribute')
capture.domain = 'FACE'                   # or 'POINT'
# 4.2+: capture uses items_tree (like interface)
capture.capture_items.new('FLOAT_VECTOR', 'Normal')
# Link: Group Input geometry -> capture.inputs['Geometry']
#       InputNormal -> capture.inputs['Value'] (the new item)
# Then: capture.outputs['Geometry'] -> Distribute.inputs['Mesh']
#       capture.outputs['Normal']   -> use downstream as a field
```

Note: The `capture_items` API landed in 4.2 and replaces the old single-value `data_type` +
`Value` pattern. For 4.2+ use `capture_items.new(socket_type, name)`.

### 2.8 `GeometryNodeRaycast`

**Purpose:** Cast a ray from each point against a target geometry. Useful for:
- Clearance checks (is there a rock or tree within N meters of this point?).
- Projecting scatter onto terrain from a source plane.
- Sampling attributes from a different geometry.

```python
ray = tree.nodes.new('GeometryNodeRaycast')
ray.data_type = 'FLOAT'          # type of the attribute being sampled
ray.mapping   = 'NEAREST'         # or 'INTERPOLATED'
# Inputs: Target Geometry, Source Position, Ray Direction, Ray Length
# Outputs: Is Hit (Bool), Hit Position, Hit Normal, Hit Distance, Attribute
```

### 2.9 `GeometryNodeMeshBoolean`

**Purpose:** Destructive mesh cuts. Used for carving caves, holes, windows into a terrain mesh.
**NOT** for scatter — this is destructive and expensive.

```python
bool_node = tree.nodes.new('GeometryNodeMeshBoolean')
bool_node.operation = 'DIFFERENCE'   # UNION | DIFFERENCE | INTERSECT
# Mesh 1 = base, Mesh 2 = cutter (multi-input socket in UNION/INTERSECT)
```

### 2.10 `GeometryNodeSetPosition`

**Purpose:** Displace vertices. The key node for procedural terrain deformation from Geometry
Nodes (rather than from a displace modifier).

```python
set_pos = tree.nodes.new('GeometryNodeSetPosition')
# Inputs: Geometry, Selection, Position (absolute), Offset (relative)
# For terrain noise displacement: feed (InputNormal * noise_value * scale) into 'Offset'.
```

### 2.11 `GeometryNodeSetShadeSmooth`

**Purpose:** Flag faces as smooth. Always run this after generating rock/terrain meshes.

```python
smooth = tree.nodes.new('GeometryNodeSetShadeSmooth')
smooth.domain = 'FACE'
smooth.inputs['Shade Smooth'].default_value = True
```

### 2.12 `GeometryNodeStoreNamedAttribute`

**Purpose:** Write a named attribute on the output geometry. The shader on the terrain can then
read this via `Attribute` node with the same name. Use for splat masks, per-instance seed,
slope value, anything the material shader needs.

```python
store = tree.nodes.new('GeometryNodeStoreNamedAttribute')
store.data_type = 'FLOAT'      # BYTE_COLOR, FLOAT_VECTOR, FLOAT2, ...
store.domain    = 'POINT'      # POINT | FACE | CORNER | EDGE | INSTANCE | CURVE
store.inputs['Name'].default_value = "slope_mask"
# Feed the float/vector you want to store into Value
```

---

## 3. Slope / height / noise masking

All masks produce a **float field** (typically 0..1). You multiply them into the
`Density Factor` of Distribute Points on Faces. Multiple masks combine with multiply
(intersection) or max (union).

### 3.1 Slope mask from surface normal . Z

Slope angle = acos(normal . Z). A flat face has `normal.Z = 1` (angle 0). A wall has
`normal.Z = 0` (angle 90 deg).

```python
# Inputs
normal_in = tree.nodes.new('GeometryNodeInputNormal')

# Separate XYZ to get the Z component
sep = tree.nodes.new('ShaderNodeSeparateXYZ')

# Optional: acos to get an angle in radians (slope)
acos = tree.nodes.new('ShaderNodeMath')
acos.operation = 'ARCCOSINE'

# Map radians to a 0..1 factor where [min_angle, max_angle] becomes [0, 1]
map_range = tree.nodes.new('ShaderNodeMapRange')
map_range.inputs['From Min'].default_value = math.radians(30)   # slope_min
map_range.inputs['From Max'].default_value = math.radians(75)   # slope_max
map_range.inputs['To Min'].default_value   = 0.0
map_range.inputs['To Max'].default_value   = 1.0
map_range.clamp = True

# Wire it up
L = tree.links.new
L(normal_in.outputs['Normal'], sep.inputs['Vector'])
L(sep.outputs['Z'],            acos.inputs['Value'])
L(acos.outputs['Value'],       map_range.inputs['Value'])
# Use map_range.outputs['Result'] as the slope mask (1.0 where slope is in [min,max])
```

For a cliff rock scatter (steep faces only) set `from_min = radians(30)`, `from_max = radians(75)`.

### 3.2 Height mask from position Z

Used for altitude-based biomes (snow at top, grass at bottom).

```python
pos = tree.nodes.new('GeometryNodeInputPosition')
sep = tree.nodes.new('ShaderNodeSeparateXYZ')
hmap = tree.nodes.new('ShaderNodeMapRange')
hmap.inputs['From Min'].default_value = 50.0    # meters
hmap.inputs['From Max'].default_value = 150.0
hmap.clamp = True

L(pos.outputs['Position'], sep.inputs['Vector'])
L(sep.outputs['Z'],        hmap.inputs['Value'])
```

### 3.3 Noise mask

Adds organic blobby variation so scatter is not a uniform carpet. Scatter-in-clumps is the
signature look of AAA ground scatter.

```python
noise = tree.nodes.new('ShaderNodeTexNoise')
noise.noise_dimensions = '3D'
noise.inputs['Scale'].default_value = 0.05       # large blobs
noise.inputs['Detail'].default_value = 2.0
noise.inputs['Roughness'].default_value = 0.5

# Feed world-space position in for world-space noise (recommended)
pos = tree.nodes.new('GeometryNodeInputPosition')
L(pos.outputs['Position'], noise.inputs['Vector'])

# Contrast-boost the noise into a binary-ish mask with a Map Range
nmap = tree.nodes.new('ShaderNodeMapRange')
nmap.inputs['From Min'].default_value = 0.4      # clump threshold
nmap.inputs['From Max'].default_value = 0.6
nmap.clamp = True
L(noise.outputs['Fac'], nmap.inputs['Value'])
```

### 3.4 Curvature mask (ridges/valleys)

True curvature is not directly exposed. Approximations:
- **Ambient occlusion** (fake) — use the built-in Geometry Node shader `ShaderNodeAmbientOcclusion`
  inside geometry nodes is NOT supported. Use workflow (a) or (b):
  - (a) Raycast the normal direction at a small step distance and compare hits.
  - (b) Bake a curvature map externally and sample it as a texture in-graph.
  - (c) Compare the vertex normal to the face-area-weighted average of neighbor normals.
- For most terrains, a **height + slope + noise** combination gives the "ridges vs valleys"
  split without needing true curvature.

### 3.5 World-space vs local-space noise

- **Local-space** (from `Position` read after any transform): noise moves with the terrain.
  Good for tileable content.
- **World-space** (default — GN position is world-space in the modifier): noise is fixed in
  world. Good for global biomes that shouldn't shift when the terrain is moved.

GN's `Position` is world-space by default. To get object-local, use:
```python
self_obj = tree.nodes.new('GeometryNodeSelfObject')
info     = tree.nodes.new('GeometryNodeObjectInfo')
# Invert the self transform and multiply against world position to get local-space.
```
In practice: just keep world-space and accept that scatter is stable in world.

### 3.6 Combining masks

Multiply = AND. Max = OR. Mix (factor) = weighted blend.

```python
mul = tree.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
# wire slope_mask -> Value 0, noise_mask -> Value 1
# wire mul.outputs['Value'] -> Distribute Points on Faces.inputs['Density Factor']
```

For splatmap authoring (grass + rocks + snow layers), store each mask as a named attribute on
the terrain via `GeometryNodeStoreNamedAttribute` and have the material shader read them via
`Attribute` nodes.

---

## 4. Multi-collection kit-piece scatter

This is the pattern for rock kits with N variants.

### 4.1 Graph structure

```
Terrain --> Distribute Points on Faces --> Instance on Points -> Rotate Instances -> Scale Instances -> Join
Collection Info (separate_children=True) ----^ (Instance socket)
Random Value (int) ----------------------------^ (Instance Index)
Random Value (float vector) -------------------^ (via Scale Instances)
```

### 4.2 Code

```python
import bpy, math

def build_collection_scatter(terrain, rock_collection, density=0.15, seed=42):
    tree = bpy.data.node_groups.new("GN_RockKitScatter", 'GeometryNodeTree')

    # Interface
    tree.interface.new_socket('Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

    n_in  = tree.nodes.new('NodeGroupInput');  n_in.location  = (-1000, 0)
    n_out = tree.nodes.new('NodeGroupOutput'); n_out.location = (1200, 0)

    # Distribute
    distrib = tree.nodes.new('GeometryNodeDistributePointsOnFaces')
    distrib.distribute_method = 'POISSON'
    distrib.inputs['Density Max'].default_value = density
    distrib.inputs['Distance Min'].default_value = 0.5
    distrib.inputs['Seed'].default_value = seed
    distrib.location = (-600, 0)

    # Collection info with separate children so each rock is a pickable instance
    coll = tree.nodes.new('GeometryNodeCollectionInfo')
    coll.inputs['Collection'].default_value = rock_collection
    coll.transform_space = 'ORIGINAL'
    coll.inputs['Separate Children'].default_value = True
    coll.inputs['Reset Children'].default_value   = True
    coll.location = (-600, -300)

    # Random index for picking variants
    rand_idx = tree.nodes.new('FunctionNodeRandomValue')
    rand_idx.data_type = 'INT'
    rand_idx.inputs[4].default_value = 0          # Min (int)
    rand_idx.inputs[5].default_value = 1000       # Max (int); clamped by collection size
    rand_idx.inputs['Seed'].default_value = seed + 1
    rand_idx.location = (-300, -300)

    # Instance on Points with pick-instance
    iop = tree.nodes.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    iop.location = (-100, 0)

    # Random scale (uniform): one Random Value (float), fed via CombineXYZ into Scale Instances
    rand_scale = tree.nodes.new('FunctionNodeRandomValue')
    rand_scale.data_type = 'FLOAT'
    rand_scale.inputs[2].default_value = 0.6      # Min
    rand_scale.inputs[3].default_value = 1.6      # Max
    rand_scale.inputs['Seed'].default_value = seed + 2
    rand_scale.location = (100, -300)

    combine = tree.nodes.new('ShaderNodeCombineXYZ')
    combine.location = (250, -300)

    scale_inst = tree.nodes.new('GeometryNodeScaleInstances')
    scale_inst.location = (450, 0)

    # Random additional tilt around Z (on top of normal alignment from distribute)
    rand_rot = tree.nodes.new('FunctionNodeRandomValue')
    rand_rot.data_type = 'FLOAT_VECTOR'
    rand_rot.inputs[0].default_value = (0, 0, 0)            # Min vector
    rand_rot.inputs[1].default_value = (0, 0, math.pi * 2)  # Max vector (full spin on Z)
    rand_rot.inputs['Seed'].default_value = seed + 3
    rand_rot.location = (250, 200)

    rotate_inst = tree.nodes.new('GeometryNodeRotateInstances')
    rotate_inst.inputs['Local Space'].default_value = True
    rotate_inst.location = (650, 0)

    # Join with terrain so we still see the ground
    join = tree.nodes.new('GeometryNodeJoinGeometry')
    join.location = (900, 0)

    # Links
    L = tree.links.new
    L(n_in.outputs['Geometry'],     distrib.inputs['Mesh'])
    L(distrib.outputs['Points'],    iop.inputs['Points'])
    L(distrib.outputs['Rotation'],  iop.inputs['Rotation'])       # normal alignment
    L(coll.outputs['Instances'],    iop.inputs['Instance'])
    L(rand_idx.outputs['Value'],    iop.inputs['Instance Index'])
    L(iop.outputs['Instances'],     scale_inst.inputs['Instances'])
    L(rand_scale.outputs['Value'],  combine.inputs['X'])
    L(rand_scale.outputs['Value'],  combine.inputs['Y'])
    L(rand_scale.outputs['Value'],  combine.inputs['Z'])
    L(combine.outputs['Vector'],    scale_inst.inputs['Scale'])
    L(scale_inst.outputs['Instances'], rotate_inst.inputs['Instances'])
    L(rand_rot.outputs['Value'],    rotate_inst.inputs['Rotation'])
    L(rotate_inst.outputs['Instances'], join.inputs['Geometry'])
    L(n_in.outputs['Geometry'],     join.inputs['Geometry'])
    L(join.outputs['Geometry'],     n_out.inputs['Geometry'])

    mod = terrain.modifiers.new("GN_RockKitScatter", type='NODES')
    mod.node_group = tree
    return mod
```

Key points:
- **`separate_children=True`** + `pick_instance=True` + `Instance Index` = random variant selection.
- **`Reset Children=True`** removes the collection's own object transform so all variants are
  positioned at the scatter point, not at their authored position.
- **Per-variant density weighting** is not directly supported — do one of:
  - Put low-weight variants into a **secondary collection** with its own scatter modifier at
    lower density.
  - Use a `Switch` on `Instance Index` to mask out certain indices with some probability.
- **Per-variant scale range** can be done by building a lookup table: route the index into a
  `ShaderNodeMapRange` or multiple `Compare` + `Switch` nodes to produce a per-index scale
  multiplier. For the usual "different sizes per variant" this is overkill — just author the
  variants in the collection at the sizes you want, and apply a uniform random scale on top.
- **Blue-noise non-overlap** comes from `distribute_method = 'POISSON'` + `Distance Min`. This is
  2D-on-the-surface, not true 3D, so very tall thin rocks can still intersect. Increase
  `Distance Min` to ~= the widest variant's footprint.

### 4.3 The `distribute.outputs['Rotation']` shortcut

The `Distribute Points on Faces` node's `Rotation` output is **already aligned to the surface
normal**. Wiring it straight into `Instance on Points > Rotation` is the fastest path to
normal-aligned scatter — no `Capture Attribute`, no `Align Euler to Vector` needed.

If you want tighter control (e.g., align Z-axis to normal but lock Y to world-north for tree
trunks), build the rotation explicitly:

```python
# Capture the normal so it survives topology change
cap = tree.nodes.new('GeometryNodeCaptureAttribute')
cap.domain = 'FACE'
cap.capture_items.new('FLOAT_VECTOR', 'n')

nrm = tree.nodes.new('GeometryNodeInputNormal')
L(n_in.outputs['Geometry'], cap.inputs['Geometry'])
L(nrm.outputs['Normal'],    cap.inputs['n'])    # in 4.2+ the dynamic socket
L(cap.outputs['Geometry'],  distrib.inputs['Mesh'])

# Build an align-Z-to-normal rotation
align = tree.nodes.new('FunctionNodeAlignEulerToVector')
align.axis = 'Z'           # align this local axis of the instance...
align.pivot_axis = 'AUTO'
L(cap.outputs['n'],         align.inputs['Vector'])     # ...to the captured normal

L(align.outputs['Rotation'], iop.inputs['Rotation'])
```

Note: Starting in 4.2+, Blender renamed `FunctionNodeAlignEulerToVector` to
`FunctionNodeAlignRotationToVector` in some builds — check `VALID_GN_NODE_TYPES` in
`geometry_nodes.py` before assuming. The older identifier still works as an alias on 4.5.

---

## 5. Performance

### 5.1 Instance count guidelines

| Use case                          | Instances / modifier | Notes                               |
|-----------------------------------|----------------------|--------------------------------------|
| Real-time viewport edit           | < 10k               | Stays interactive in solid shading.  |
| Eevee render                      | 50k - 200k          | Fine with shared instance source.    |
| Cycles render                     | 500k - several M    | Memory-bound, not compute-bound.     |
| Realized mesh (baked)             | avoid > 500k verts  | Realized is O(count * verts/mesh).   |

Hard rule: **keep scatter as instances**. Never Realize Instances inside a scatter graph at
runtime.

### 5.2 Viewport simplification

Blender's Simplify panel has a `Max Child Particles` slider, but that's for the particle system.
For Geometry Nodes you have to do it yourself. Best practice: expose a `Viewport Density`
multiplier as a modifier input, and use Blender's `bpy.context.scene.render.use_simplify` +
a manual density scaler driven by a property.

Alternative: use `GeometryNodeIsViewport` (bool input node) to gate density by viewport vs
render.

```python
is_vp = tree.nodes.new('GeometryNodeIsViewport')
# Use its Bool output in a Switch to select low-density vs full-density path.
```

### 5.3 Baking Geometry Nodes output to a real mesh

For export to FBX/glTF you need a real mesh. Two options:

**Option A — Temporary Realize in the graph, then `to_mesh()`:**
```python
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj  = terrain.evaluated_get(depsgraph)
new_mesh  = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True)
baked = bpy.data.objects.new(terrain.name + "_baked", new_mesh)
bpy.context.collection.objects.link(baked)
```
But this preserves instances as instances (linked-duplicate meshes) — which is the correct thing
for most exporters.

**Option B — Apply the modifier (destroys the non-destructive graph):**
```python
bpy.context.view_layer.objects.active = terrain
bpy.ops.object.modifier_apply(modifier="GN_Scatter")
```
This realizes instances to real mesh data. Do this only on a **copy** of the source object.

**Option C — Use `Convert` to make an instancer:**
```python
bpy.ops.object.convert(target='MESH', keep_original=True)
```

For export pipelines, you almost always want **Option A** — real mesh, instances preserved as
linked duplicates, which the glTF/FBX exporters then handle as mesh instancing.

### 5.4 LOD handling

Geometry Nodes has no built-in LOD. Patterns:
- Author multiple rock variants in the collection at different polycounts, and pick by distance
  using `GeometryNodeProximity` to the active camera (fed via an input object).
- Bake a low-poly version of the scatter and switch meshes at runtime in-engine.
- Use `GeometryNodeIsViewport` to swap collections between render and viewport.

---

## 6. Integrating with existing terrain

### 6.1 Adding a GN modifier to an existing terrain

```python
terrain = bpy.data.objects['Terrain_Hearthvale']
mod = terrain.modifiers.new(name="GN_RockScatter", type='NODES')
mod.node_group = existing_tree_or_new_tree
```

Modifier order matters. Scatter should come **after** displace/subdivision modifiers (so points
sample the final terrain surface) and **before** any final triangulate/decimate (so instances
aren't destroyed).

To reorder:
```python
while terrain.modifiers.find("GN_RockScatter") > desired_index:
    bpy.ops.object.modifier_move_up(modifier="GN_RockScatter")
```

### 6.2 Sampling the terrain's vertex color layer as a mask

```python
vcol = tree.nodes.new('GeometryNodeInputNamedAttribute')
vcol.data_type = 'FLOAT_COLOR'
vcol.inputs['Name'].default_value = 'biome_mask'   # name of the vertex color layer

sep = tree.nodes.new('ShaderNodeSeparateColor')    # RGBA -> R, G, B, A
# Use one channel as density mask for grass, another for rocks, another for trees.
L(vcol.outputs['Attribute'], sep.inputs['Color'])
L(sep.outputs['Red'],        distrib.inputs['Density Factor'])
```

The vertex color layer must exist on the terrain before the modifier evaluates. Create it via
`terrain.data.color_attributes.new(name='biome_mask', type='FLOAT_COLOR', domain='POINT')`.

### 6.3 Sampling the terrain's normal

Already covered — use `GeometryNodeInputNormal` inside the modifier. This reads the
**current** mesh normal at evaluation time (i.e., after any preceding modifiers but before the
scatter has been applied).

### 6.4 Connecting to terrain's world transform

Geometry Nodes operates in the modifier object's **local space** by default. World-space is
recovered by:

```python
self_obj = tree.nodes.new('GeometryNodeSelfObject')
info     = tree.nodes.new('GeometryNodeObjectInfo')
L(self_obj.outputs['Self Object'], info.inputs['Object'])

# info.outputs['Location'], info.outputs['Rotation'], info.outputs['Scale']
# info.outputs['Geometry'] is the object's evaluated geometry in world space.
```

For terrain, this matters if you're using world-space noise on top of a moving/rotating terrain
chunk.

---

## 7. Save/load of node groups

### 7.1 Appending a node group from a .blend library

```python
lib_path = r"C:\VB\assets\node_libs\scatter_kits.blend"
group_name = "GN_RockKitScatter_v03"

with bpy.data.libraries.load(lib_path, link=False) as (src, dst):
    if group_name in src.node_groups:
        dst.node_groups = [group_name]

tree = bpy.data.node_groups.get(group_name)
assert tree is not None, f"Failed to append {group_name}"
```

Set `link=True` instead of `False` to link (live-reference) rather than copy. Linking is better
for pipelines because an upstream fix propagates, but it makes the .blend dependent on the
library being present on disk.

### 7.2 Node group library structure

Recommended layout:

```
assets/node_libs/
  scatter_kits.blend        # GN_RockScatter, GN_GrassScatter, GN_TreeScatter, ...
  terrain_ops.blend          # GN_HeightNoise, GN_SlopeColor, GN_ErosionFake
  boolean_ops.blend          # GN_WindowCut, GN_DoorCut
```

Per-.blend conventions:
- One node group per scatter "look" (e.g., `GN_RockScatter_Cliff_v03`).
- Interface sockets are the only public API — treat the internals as private.
- Version suffix (`_v03`) to allow newer versions to coexist with old references.

### 7.3 Versioning

Store the version in a **custom property** on the node group, not just in the name:

```python
tree['schema_version'] = 3
tree['author']         = 'VB Pipeline'
tree['description']    = 'Rock kit scatter with slope/height/noise masks'
```

And in your pipeline code, when appending, check the version:

```python
if tree.get('schema_version', 0) < MIN_VERSION:
    raise RuntimeError(f"{tree.name} is v{tree.get('schema_version')}, need v{MIN_VERSION}")
```

---

## 8. Working code — full pipeline

Production-grade, Blender 4.2+ compatible, handles missing collections, uses 4.x interface API.

```python
"""
add_rock_scatter.py — production scatter builder for VB terrain pipeline.

Paste into a Blender handler module or bpy script. Blender 4.2+ only.
"""
from __future__ import annotations

import math
import bpy


def add_rock_scatter(
    terrain_obj: bpy.types.Object,
    rock_collection_name: str,
    density_per_m2: float = 0.1,
    slope_min_deg: float = 30.0,
    slope_max_deg: float = 75.0,
    scale_range: tuple[float, float] = (0.5, 2.0),
    seed: int = 42,
    distance_min: float | None = None,
    modifier_name: str = "GN_RockScatter",
) -> bpy.types.NodesModifier:
    """
    Build a Geometry Nodes scatter modifier on terrain_obj that scatters
    instances from rock_collection_name on faces with slope in
    [slope_min_deg, slope_max_deg] at density_per_m2, with per-instance scale
    variation and surface-normal alignment.

    Parameters
    ----------
    terrain_obj : bpy.types.Object
        The terrain mesh object to attach the modifier to. Must be a MESH.
    rock_collection_name : str
        Name of a bpy.data collection containing the rock variants. Must
        exist; each child is treated as a pickable instance.
    density_per_m2 : float
        Target density (points per square meter). Applied as Poisson-disk
        density cap.
    slope_min_deg, slope_max_deg : float
        Slope angle window (degrees from horizontal). Faces outside this
        range get zero density.
    scale_range : (float, float)
        Uniform random scale multiplier min/max.
    seed : int
        RNG seed. The function derives sub-seeds from this.
    distance_min : float | None
        Minimum Poisson-disk separation. If None, computed as a function of
        density_per_m2 so that the scatter reliably hits the target density.
    modifier_name : str
        Name for the modifier. If a modifier with this name already exists
        on the object, it is removed first.

    Returns
    -------
    bpy.types.NodesModifier
        The new modifier.

    Raises
    ------
    TypeError
        If terrain_obj is not a MESH.
    KeyError
        If rock_collection_name is not found in bpy.data.collections.
    """
    # --- validation -------------------------------------------------------
    if terrain_obj is None or terrain_obj.type != 'MESH':
        raise TypeError(
            f"terrain_obj must be a MESH object, got "
            f"{terrain_obj.type if terrain_obj else None}"
        )

    rock_collection = bpy.data.collections.get(rock_collection_name)
    if rock_collection is None:
        raise KeyError(
            f"Rock collection {rock_collection_name!r} not found in bpy.data.collections"
        )
    if not rock_collection.all_objects:
        raise ValueError(
            f"Rock collection {rock_collection_name!r} is empty"
        )

    # --- compute derived params ------------------------------------------
    if distance_min is None:
        # heuristic: average spacing for a Poisson distribution
        # d ~ 1 / sqrt(density); clamp to avoid extreme values
        distance_min = max(0.2, 1.0 / math.sqrt(max(density_per_m2, 1e-4)) * 0.6)

    slope_min_rad = math.radians(slope_min_deg)
    slope_max_rad = math.radians(slope_max_deg)
    scale_min, scale_max = float(scale_range[0]), float(scale_range[1])

    # --- tree -------------------------------------------------------------
    tree_name = f"GN_RockScatter_{terrain_obj.name}"
    tree = bpy.data.node_groups.new(tree_name, 'GeometryNodeTree')
    tree['schema_version'] = 1
    tree['author'] = 'VB Pipeline'

    # Interface: Geometry in/out + user-exposed controls
    tree.interface.new_socket('Geometry',  in_out='INPUT',  socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Geometry',  in_out='OUTPUT', socket_type='NodeSocketGeometry')
    s_coll  = tree.interface.new_socket('Rocks',    in_out='INPUT', socket_type='NodeSocketCollection')
    s_dens  = tree.interface.new_socket('Density',  in_out='INPUT', socket_type='NodeSocketFloat')
    s_dmin  = tree.interface.new_socket('Min Distance', in_out='INPUT', socket_type='NodeSocketFloat')
    s_smin  = tree.interface.new_socket('Slope Min (deg)', in_out='INPUT', socket_type='NodeSocketFloat')
    s_smax  = tree.interface.new_socket('Slope Max (deg)', in_out='INPUT', socket_type='NodeSocketFloat')
    s_scmin = tree.interface.new_socket('Scale Min', in_out='INPUT', socket_type='NodeSocketFloat')
    s_scmax = tree.interface.new_socket('Scale Max', in_out='INPUT', socket_type='NodeSocketFloat')
    s_seed  = tree.interface.new_socket('Seed',     in_out='INPUT', socket_type='NodeSocketInt')

    s_dens.default_value  = density_per_m2
    s_dens.min_value      = 0.0
    s_dmin.default_value  = distance_min
    s_dmin.min_value      = 0.0
    s_smin.default_value  = slope_min_deg
    s_smax.default_value  = slope_max_deg
    s_scmin.default_value = scale_min
    s_scmax.default_value = scale_max
    s_seed.default_value  = seed

    N = tree.nodes
    L = tree.links.new

    n_in  = N.new('NodeGroupInput');  n_in.location  = (-1400,  0)
    n_out = N.new('NodeGroupOutput'); n_out.location = ( 1400,  0)

    # --- slope mask: acos(normal.Z) in [slope_min, slope_max] -> [1, 1] ---
    nrm = N.new('GeometryNodeInputNormal');    nrm.location = (-1200, -250)
    sep = N.new('ShaderNodeSeparateXYZ');      sep.location = (-1000, -250)
    acos = N.new('ShaderNodeMath')
    acos.operation = 'ARCCOSINE'
    acos.location = (-800, -250)

    deg_to_rad_min = N.new('ShaderNodeMath')
    deg_to_rad_min.operation = 'RADIANS'
    deg_to_rad_min.location = (-800, -450)

    deg_to_rad_max = N.new('ShaderNodeMath')
    deg_to_rad_max.operation = 'RADIANS'
    deg_to_rad_max.location = (-800, -600)

    slope_window = N.new('ShaderNodeMapRange')
    slope_window.location = (-600, -400)
    slope_window.clamp = True

    # Build a symmetric tent: in-window -> 1, out-of-window -> 0
    # Use two Compares and Multiply (GREATER_THAN slope_min AND LESS_THAN slope_max)
    cmp_lo = N.new('FunctionNodeCompare')
    cmp_lo.data_type = 'FLOAT'
    cmp_lo.operation = 'GREATER_EQUAL'
    cmp_lo.location  = (-600, -200)

    cmp_hi = N.new('FunctionNodeCompare')
    cmp_hi.data_type = 'FLOAT'
    cmp_hi.operation = 'LESS_EQUAL'
    cmp_hi.location  = (-600, -350)

    mask_and = N.new('FunctionNodeBooleanMath')
    mask_and.operation = 'AND'
    mask_and.location  = (-400, -275)

    # Bool -> Float (via math multiply with 1.0)
    b_to_f = N.new('ShaderNodeMath')
    b_to_f.operation = 'MULTIPLY'
    b_to_f.inputs[1].default_value = 1.0
    b_to_f.location = (-200, -275)

    # --- noise mask (organic clumping) -----------------------------------
    pos = N.new('GeometryNodeInputPosition'); pos.location = (-1200, -800)
    noise = N.new('ShaderNodeTexNoise')
    noise.noise_dimensions = '3D'
    noise.inputs['Scale'].default_value = 0.04
    noise.inputs['Detail'].default_value = 2.0
    noise.inputs['Roughness'].default_value = 0.55
    noise.location = (-1000, -800)

    noise_window = N.new('ShaderNodeMapRange')
    noise_window.clamp = True
    noise_window.inputs['From Min'].default_value = 0.35
    noise_window.inputs['From Max'].default_value = 0.65
    noise_window.location = (-800, -800)

    # --- mask combine ----------------------------------------------------
    mask_mul = N.new('ShaderNodeMath')
    mask_mul.operation = 'MULTIPLY'
    mask_mul.location = (0, -500)

    # --- distribute ------------------------------------------------------
    distrib = N.new('GeometryNodeDistributePointsOnFaces')
    distrib.distribute_method = 'POISSON'
    distrib.location = (200, 0)

    # --- collection info + random pick -----------------------------------
    coll_info = N.new('GeometryNodeCollectionInfo')
    coll_info.inputs['Separate Children'].default_value = True
    coll_info.inputs['Reset Children'].default_value    = True
    coll_info.transform_space = 'ORIGINAL'
    coll_info.location = (200, -300)

    rand_idx = N.new('FunctionNodeRandomValue')
    rand_idx.data_type = 'INT'
    # FunctionNodeRandomValue socket layout per data_type:
    #   FLOAT_VECTOR: [0]=Min, [1]=Max, ..., Seed, ID
    #   FLOAT:        [2]=Min, [3]=Max, Seed, ID
    #   INT:          [4]=Min, [5]=Max, Seed, ID
    #   BOOL:         [6]=Probability, Seed, ID
    rand_idx.inputs[4].default_value = 0
    rand_idx.inputs[5].default_value = max(0, len(rock_collection.all_objects) - 1)
    rand_idx.inputs['Seed'].default_value = seed + 1
    rand_idx.location = (400, -300)

    # --- instance on points ----------------------------------------------
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    iop.location = (600, 0)

    # --- random scale ----------------------------------------------------
    rand_scale = N.new('FunctionNodeRandomValue')
    rand_scale.data_type = 'FLOAT'
    rand_scale.inputs['Seed'].default_value = seed + 2
    rand_scale.location = (600, -300)

    combine_scale = N.new('ShaderNodeCombineXYZ')
    combine_scale.location = (800, -300)

    scale_inst = N.new('GeometryNodeScaleInstances')
    scale_inst.location = (800, 0)

    # --- random Z spin on top of normal alignment ------------------------
    rand_rot = N.new('FunctionNodeRandomValue')
    rand_rot.data_type = 'FLOAT_VECTOR'
    rand_rot.inputs[0].default_value = (0.0, 0.0, 0.0)
    rand_rot.inputs[1].default_value = (0.0, 0.0, math.pi * 2)
    rand_rot.inputs['Seed'].default_value = seed + 3
    rand_rot.location = (800, 300)

    rotate_inst = N.new('GeometryNodeRotateInstances')
    rotate_inst.inputs['Local Space'].default_value = True
    rotate_inst.location = (1000, 0)

    # --- set shade smooth on instances -----------------------------------
    smooth = N.new('GeometryNodeSetShadeSmooth')
    smooth.domain = 'FACE'
    smooth.inputs['Shade Smooth'].default_value = True
    smooth.location = (1100, 0)

    # --- join with terrain ------------------------------------------------
    join = N.new('GeometryNodeJoinGeometry')
    join.location = (1250, 0)

    # -----------------------------------------------------------------
    # LINKS
    # -----------------------------------------------------------------
    # slope mask pipeline
    L(nrm.outputs['Normal'], sep.inputs['Vector'])
    L(sep.outputs['Z'],      acos.inputs['Value'])
    # take degree inputs and convert to radians
    # We connect the interface sockets; if user overrides in modifier panel,
    # this dynamically responds.
    L(n_in.outputs['Slope Min (deg)'], deg_to_rad_min.inputs['Value'])
    L(n_in.outputs['Slope Max (deg)'], deg_to_rad_max.inputs['Value'])
    L(acos.outputs['Value'],           cmp_lo.inputs['A'])
    L(deg_to_rad_min.outputs['Value'], cmp_lo.inputs['B'])
    L(acos.outputs['Value'],           cmp_hi.inputs['A'])
    L(deg_to_rad_max.outputs['Value'], cmp_hi.inputs['B'])
    L(cmp_lo.outputs['Result'],        mask_and.inputs[0])
    L(cmp_hi.outputs['Result'],        mask_and.inputs[1])
    L(mask_and.outputs['Boolean'],     b_to_f.inputs[0])

    # noise mask
    L(pos.outputs['Position'],         noise.inputs['Vector'])
    L(noise.outputs['Fac'],            noise_window.inputs['Value'])

    # combine masks
    L(b_to_f.outputs['Value'],         mask_mul.inputs[0])
    L(noise_window.outputs['Result'],  mask_mul.inputs[1])

    # distribute
    L(n_in.outputs['Geometry'],                 distrib.inputs['Mesh'])
    L(n_in.outputs['Density'],                  distrib.inputs['Density Max'])
    L(n_in.outputs['Min Distance'],             distrib.inputs['Distance Min'])
    L(mask_mul.outputs['Value'],                distrib.inputs['Density Factor'])
    L(n_in.outputs['Seed'],                     distrib.inputs['Seed'])

    # collection -> iop (pick by random index)
    L(n_in.outputs['Rocks'],                    coll_info.inputs['Collection'])
    L(coll_info.outputs['Instances'],           iop.inputs['Instance'])
    L(rand_idx.outputs['Value'],                iop.inputs['Instance Index'])

    # points + normal-aligned rotation from distribute
    L(distrib.outputs['Points'],                iop.inputs['Points'])
    L(distrib.outputs['Rotation'],              iop.inputs['Rotation'])

    # scale chain
    L(n_in.outputs['Scale Min'],                rand_scale.inputs[2])  # Min (float)
    L(n_in.outputs['Scale Max'],                rand_scale.inputs[3])  # Max (float)
    L(rand_scale.outputs['Value'],              combine_scale.inputs['X'])
    L(rand_scale.outputs['Value'],              combine_scale.inputs['Y'])
    L(rand_scale.outputs['Value'],              combine_scale.inputs['Z'])
    L(iop.outputs['Instances'],                 scale_inst.inputs['Instances'])
    L(combine_scale.outputs['Vector'],          scale_inst.inputs['Scale'])

    # rotation chain (extra Z spin)
    L(scale_inst.outputs['Instances'],          rotate_inst.inputs['Instances'])
    L(rand_rot.outputs['Value'],                rotate_inst.inputs['Rotation'])

    # smooth + join
    L(rotate_inst.outputs['Instances'],         smooth.inputs['Geometry'])
    L(smooth.outputs['Geometry'],               join.inputs['Geometry'])
    L(n_in.outputs['Geometry'],                 join.inputs['Geometry'])
    L(join.outputs['Geometry'],                 n_out.inputs['Geometry'])

    # --- modifier ---------------------------------------------------------
    # Remove any existing modifier with same name first
    existing = terrain_obj.modifiers.get(modifier_name)
    if existing is not None:
        terrain_obj.modifiers.remove(existing)

    mod = terrain_obj.modifiers.new(name=modifier_name, type='NODES')
    mod.node_group = tree

    # Drive the collection input by looking up the socket identifier.
    # Modifier panel values are keyed by identifier, not name.
    for item in tree.interface.items_tree:
        if item.item_type != 'SOCKET' or item.in_out != 'INPUT':
            continue
        if item.name == 'Rocks':
            mod[item.identifier] = rock_collection
        # Density/Seed/etc. already defaulted on the socket; modifier mirrors them.

    return mod
```

### Usage

```python
import bpy

terrain = bpy.data.objects['Terrain_Hearthvale']
mod = add_rock_scatter(
    terrain_obj=terrain,
    rock_collection_name='RockKit_Cliff',
    density_per_m2=0.15,
    slope_min_deg=25.0,
    slope_max_deg=80.0,
    scale_range=(0.4, 2.2),
    seed=1337,
)
```

### Notes on the full example

- **Slope window uses degrees on the interface**, converted to radians internally via
  `ShaderNodeMath operation='RADIANS'`. This makes the modifier panel friendly.
- **Distribute's Density Max + Density Factor:** Poisson mode needs `Density Max` as the cap.
  We route the combined mask (slope . noise) into `Density Factor`, so the final per-face
  density is `Density Max * mask`.
- **Normal alignment** comes from `distrib.outputs['Rotation']` going straight into
  `iop.inputs['Rotation']`. We add random Z spin on top via `Rotate Instances` with
  `Local Space=True` (critical — rotates around the instance's own up axis, not world Z).
- **Set Shade Smooth** on the instances before Join. Joining after smoothing is fine because
  Join doesn't change per-face smooth state.
- **Interface socket count is 9** (Geometry in/out + 7 params). The modifier panel shows all
  of these to the user for on-the-fly tuning.
- **Reset Children=True** on Collection Info is non-negotiable — otherwise each rock is placed
  at `scatter_point + rock_origin_in_collection`, and rocks fly off into space.
- **`FunctionNodeRandomValue` socket indices** are stable but confusing (Min/Max slots differ
  by data type). The inline comment in the code documents the mapping.

---

## 9. Alternative: particle systems

Blender's legacy particle system still works for hair-style scatter, but is **deprecated for
new content** in favor of Geometry Nodes. Both coexist.

### 9.1 When to use which

| Factor                         | Geometry Nodes         | Particles (Hair)           |
|--------------------------------|------------------------|-----------------------------|
| New content                    | Yes (preferred)        | No                          |
| Non-destructive graph          | Yes                    | Partially                   |
| Per-instance control (Python)  | Field-based, clean     | Particle system properties  |
| Render in Cycles/Eevee         | Both                   | Both                        |
| Export to glTF/FBX             | Native (baked)         | Requires particle -> mesh   |
| Child particles (LOD-like)     | Manual                 | Built-in                    |
| Weight painting for density    | Via named attribute    | Native (vertex group)       |
| Per-element forces / physics   | No                     | Yes                         |
| Performance (static scatter)   | Faster                 | Slower                      |
| Updating from addon/pipeline   | Clean API              | Legacy API, fragile         |
| Learning curve                 | Steeper                | Gentler                     |

**Rule of thumb:**
- Static scatter (rocks, grass, foliage, pebbles) -> **Geometry Nodes**.
- Dynamic/simulated (physics hair, fur with collisions, smoke-driven) -> **Particles**.
- New pipeline code -> **always GN**.
- Legacy assets already using particles -> convert via
  `handle_particle_to_mesh` (see
  `Tools/mcp-toolkit/blender_addon/handlers/geometry_nodes.py`).

### 9.2 Performance comparison

For 100k rock instances on a 1 km^2 terrain:
- Geometry Nodes (instances, non-realized): ~30 MB RAM, viewport 40-60 FPS in solid.
- Particle hair with mesh render: ~300 MB RAM, viewport 10-20 FPS.
- Particle hair with path render: similar RAM, renders only at render time.

GN wins decisively on both memory and viewport responsiveness.

### 9.3 Python API differences

**Particles (legacy):**
```python
psys = obj.modifiers.new("RockHair", type='PARTICLE_SYSTEM')
settings = obj.particle_systems[-1].settings
settings.type             = 'HAIR'
settings.render_type      = 'OBJECT'
settings.instance_object  = rock_obj   # single object only (or collection via use_collection)
settings.count            = 5000
settings.use_rotations    = True
settings.rotation_mode    = 'NOR'
settings.hair_length      = 1.0
```

Brittle: the settings are scattered across a flat `ParticleSettings` datablock with hundreds
of attributes, many interdependent. Collection usage requires `use_collection=True`,
`instance_collection = ...`, `use_collection_pick_random=True`.

**Geometry Nodes (modern):**
- All inputs are exposed as modifier properties with clear names (see section 1.4).
- The graph is inspectable, editable, and diff-able.
- One node group can serve multiple terrains without duplication.

For the VB pipeline, GN is the answer for all new code. Keep one `convert_particles_to_gn()`
utility around for migrating any legacy assets that come in.

---

## Appendix A — Node identifier quick reference

Used with `tree.nodes.new(type_string)`:

| Concept                            | Type string                                 |
|------------------------------------|---------------------------------------------|
| Group input/output                 | `NodeGroupInput` / `NodeGroupOutput`        |
| Distribute points on faces         | `GeometryNodeDistributePointsOnFaces`       |
| Distribute points in volume        | `GeometryNodeDistributePointsInVolume`      |
| Instance on points                 | `GeometryNodeInstanceOnPoints`              |
| Rotate instances                   | `GeometryNodeRotateInstances`               |
| Scale instances                    | `GeometryNodeScaleInstances`                |
| Translate instances                | `GeometryNodeTranslateInstances`            |
| Realize instances                  | `GeometryNodeRealizeInstances`              |
| Collection info                    | `GeometryNodeCollectionInfo`                |
| Object info                        | `GeometryNodeObjectInfo`                    |
| Self object                        | `GeometryNodeSelfObject`                    |
| Join geometry                      | `GeometryNodeJoinGeometry`                  |
| Set position                       | `GeometryNodeSetPosition`                   |
| Set shade smooth                   | `GeometryNodeSetShadeSmooth`                |
| Set material                       | `GeometryNodeSetMaterial`                   |
| Capture attribute                  | `GeometryNodeCaptureAttribute`              |
| Store named attribute              | `GeometryNodeStoreNamedAttribute`           |
| Input named attribute              | `GeometryNodeInputNamedAttribute`           |
| Input position                     | `GeometryNodeInputPosition`                 |
| Input normal                       | `GeometryNodeInputNormal`                   |
| Input radius                       | `GeometryNodeInputRadius`                   |
| Raycast                            | `GeometryNodeRaycast`                       |
| Proximity                          | `GeometryNodeProximity`                     |
| Mesh boolean                       | `GeometryNodeMeshBoolean`                   |
| Image texture (GN)                 | `GeometryNodeImageTexture`                  |
| Noise texture                      | `ShaderNodeTexNoise`                        |
| Voronoi texture                    | `ShaderNodeTexVoronoi`                      |
| White noise                        | `ShaderNodeTexWhiteNoise`                   |
| Map range                          | `ShaderNodeMapRange`                        |
| Math (scalar)                      | `ShaderNodeMath`                            |
| Vector math                        | `ShaderNodeVectorMath`                      |
| Clamp                              | `ShaderNodeClamp`                           |
| Mix                                | `ShaderNodeMix`                             |
| Combine XYZ / Separate XYZ         | `ShaderNodeCombineXYZ` / `ShaderNodeSeparateXYZ` |
| Color ramp                         | `ShaderNodeValToRGB`                        |
| Random value                       | `FunctionNodeRandomValue`                   |
| Compare                            | `FunctionNodeCompare`                       |
| Boolean math                       | `FunctionNodeBooleanMath`                   |
| Align Euler to vector              | `FunctionNodeAlignEulerToVector`            |
| Is viewport                        | `GeometryNodeIsViewport`                    |

---

## Appendix B — Socket class quick reference

Used with `tree.interface.new_socket(socket_type=...)`:

| Kind             | Socket class                |
|------------------|-----------------------------|
| Geometry         | `NodeSocketGeometry`        |
| Float            | `NodeSocketFloat`           |
| Float (0..1)     | `NodeSocketFloatFactor`     |
| Float (angle)    | `NodeSocketFloatAngle`      |
| Float (distance) | `NodeSocketFloatDistance`   |
| Integer          | `NodeSocketInt`             |
| Boolean          | `NodeSocketBool`            |
| Vector           | `NodeSocketVector`          |
| Color (RGBA)     | `NodeSocketColor`           |
| String           | `NodeSocketString`          |
| Object           | `NodeSocketObject`          |
| Collection       | `NodeSocketCollection`      |
| Material         | `NodeSocketMaterial`        |
| Image            | `NodeSocketImage`           |
| Texture          | `NodeSocketTexture`         |

---

## Appendix C — Known 4.x gotchas

1. **`FunctionNodeRandomValue` socket indices shift by data type.** The Min/Max sockets are at
   different positional indices depending on whether `data_type` is `FLOAT`, `INT`, `BOOL`, or
   `FLOAT_VECTOR`. Always set `data_type` **first**, then wire the sockets.

2. **Socket `min_value`/`max_value` on the interface are advisory.** The modifier panel uses
   them as soft clamps but Python code can still push values outside the range. Do not rely on
   them for validation — validate in your own pipeline code.

3. **`hide_in_modifier` hides the socket in the modifier panel but leaves it usable via the
   graph.** Useful for internal parameters you don't want artists to see.

4. **`tree.interface.items_tree` iterates all items including panels.** Always check
   `item.item_type == 'SOCKET'` before treating as a socket.

5. **Modifier input values survive node group swap if identifiers match.** If you rebuild the
   tree, assign a new set of sockets, and reassign `mod.node_group`, the old value lookup by
   identifier may fail. Always reassign values after swapping the node group.

6. **Eevee Next vs Cycles rotation semantics for instances are identical** — no renderer-specific
   workaround needed.

7. **`distribute_method='POISSON'` silently does nothing if `Density Max == 0`.** Always set a
   non-zero density, and use `Density Factor` for masking (which can go to 0).

8. **Blender 4.2 changed `GeometryNodeCaptureAttribute` to use `capture_items` dynamic sockets.**
   Pre-4.2 code using a single `data_type` + `Value` socket will break. Check your target
   Blender version.

9. **Shader nodes inside GN** (e.g., `ShaderNodeTexNoise`, `ShaderNodeMath`) work fine, but
   their UI properties (like `noise_dimensions`) must be set via Python not via inputs.

10. **`ShaderNodeMix` replaced `ShaderNodeMixRGB` in 4.x.** If you need color/float mixing, use
    `ShaderNodeMix` and set `data_type` to `RGBA`, `FLOAT`, or `VECTOR`.

---

## Sources

- [Blender Python API 4.5 (Context7)](https://docs.blender.org/api/4.5/) — authoritative reference, fetched via
  `/websites/blender_api_4_5` library.
- [Distribute Points on Faces (Blender manual)](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/point/distribute_points_on_faces.html)
- [GeometryNodeDistributePointsOnFaces API](https://docs.blender.org/api/current/bpy.types.GeometryNodeDistributePointsOnFaces.html)
- [Collection Info Node (manual)](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/input/scene/collection_info.html)
- [GeometryNodeCollectionInfo API](https://docs.blender.org/api/current/bpy.types.GeometryNodeCollectionInfo.html)
- [FunctionNodeAlignEulerToVector API](https://docs.blender.org/api/current/bpy.types.FunctionNodeAlignEulerToVector.html)
- [Align to normal with Geometry Nodes (Artisticrender)](https://artisticrender.com/align-to-normal-with-geometry-nodes-in-blender/)
- [NodeSocketCollection API](https://docs.blender.org/api/current/bpy.types.NodeSocketCollection.html)
- [NodeSocketFloat API](https://docs.blender.org/api/current/bpy.types.NodeSocketFloat.html)
- [Creating inputs and outputs for node groups in Blender 4.0 (Interplanety)](https://b3d.interplanety.org/en/creating-inputs-and-outputs-for-node-groups-in-blender-4-0-using-the-python-api/)
- [Geometry Nodes Modifier (manual)](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/geometry_nodes.html)
- [Geometry Nodes 4.2 release notes](https://developer.blender.org/docs/release_notes/4.2/geometry_nodes/)
- [Environment Scattering with Geometry Nodes (Poliigon blog)](https://www.blog.poliigon.com/blog/environment-scattering-with-geometry-nodes-in-blender)
- Internal reference: `Tools/mcp-toolkit/blender_addon/handlers/geometry_nodes.py` — existing
  scatter preset generators that already use the 4.x interface API correctly.
