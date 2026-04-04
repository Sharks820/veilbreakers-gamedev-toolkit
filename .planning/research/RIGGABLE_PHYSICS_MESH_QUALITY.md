# Riggable & Physics-Driven Mesh Quality Guide

**Domain:** Dark fantasy environmental interactive objects
**Researched:** 2026-04-03
**Overall confidence:** HIGH (codebase verified + web research + Blender API docs)

## Executive Summary

This document covers the creation of highest-quality riggable and physics-driven meshes for VeilBreakers: doors, ropes, chains, flags, cloth, banners, curtains, shutters, hanging objects, and other interactive environmental elements. It addresses topology, rigging, physics simulation in Blender Python (bpy), baking workflows, and Unity export compatibility.

The existing `riggable_objects.py` handler already provides generators for 10 object categories (doors, chains, flags, chests, chandeliers, drawbridges, rope bridges, hanging signs, windmills, cages) with proper vertex groups, empties, and pivot points. The existing `physics.py` handler provides rigid body, cloth, soft body, and physics baking. The `animation_environment.py` handler provides keyframe-based animation for doors, flags, chains, and more. This research identifies quality gaps and provides specific implementation guidance for AAA-level output.

---

## 1. Door Meshes

### 1.1 Topology Rules

**Optimal poly budget:** 200-500 tris per door (current generator produces ~250-400 depending on style).

| Door Type | Tri Budget | Key Topology Feature |
|-----------|-----------|---------------------|
| Wooden plank | 200-300 | Individual planks with gaps, 8 verts per plank |
| Iron-bound | 300-400 | Planks + iron strap boxes across width |
| Portcullis | 250-350 | Vertical bars (cylinders) + crossbars, no frame |
| Double door | 400-500 | Two independent panels, each with own hinge set |
| Trapdoor | 150-250 | Single panel + frame, hinge at one edge |
| Barn door | 300-400 | Wide planks + diagonal cross-brace |
| Castle gate | 350-500 | Thick planks + iron studs + reinforcement |

**Edge loop requirements for hinge deformation:**
- Doors do NOT deform -- they rotate as rigid bodies around a hinge axis
- Therefore quad flow matters less than proper pivot point placement
- The hinge edge of the door must align exactly with the pivot empty
- Current implementation correctly places `hinge_top` and `hinge_bottom` empties at the left edge

**Critical topology detail:** The door frame MUST be a separate mesh from the door panel. In the current `generate_door()`, frame and panel vertices are merged into one mesh but tracked via vertex groups (`frame`, `panel`). This is correct for Blender but for Unity export, consider separate GameObjects for frame (static) and panel (rigged/animated).

### 1.2 Hinge Rigging for Smooth Rotation

**Approach A: Simple pivot (recommended for doors)**
```python
# Door rotation uses object-level transform, NOT bone deformation
# The pivot point (origin) must be at the hinge edge
# In Blender:
obj.location = hinge_position
# Set origin to hinge:
bpy.context.scene.cursor.location = hinge_position
bpy.ops.object.origin_set(type='ORIGIN_3D_CURSOR')
```

**Approach B: Armature with single bone (for FBX export to Unity)**
```python
# Create a single-bone armature for the door
armature = bpy.data.armatures.new("DoorRig")
rig_obj = bpy.data.objects.new("DoorRig", armature)
bpy.context.collection.objects.link(rig_obj)

# Position bone at hinge axis
bpy.context.view_layer.objects.active = rig_obj
bpy.ops.object.mode_set(mode='EDIT')
bone = armature.edit_bones.new("Door_Hinge")
bone.head = (hinge_x, 0.0, 0.0)       # bottom hinge
bone.tail = (hinge_x, 0.0, height)     # top hinge (Z-up = rotation axis)
bpy.ops.object.mode_set(mode='OBJECT')

# Parent door mesh to armature with automatic weights
door_obj.parent = rig_obj
modifier = door_obj.modifiers.new("Armature", 'ARMATURE')
modifier.object = rig_obj
```

**Unity side:** Use `HingeJoint` component on the door GameObject. Set anchor at hinge edge, axis along Y (vertical). Spring/damper for realistic swing.

### 1.3 Door Frame Integration

**Use modeled frames, NOT booleans.** Boolean operations:
- Create non-manifold geometry
- Produce triangles and n-gons in deformation zones
- Break UV layouts
- Create inconsistent normals

The current `generate_door()` correctly models frames as separate box primitives (left jamb, right jamb, lintel, threshold) merged via `_merge_parts_tracked()`. This is the correct approach.

**Wall integration strategy:**
1. Model wall with a pre-cut doorway opening (inset rectangle)
2. Door frame mesh snaps into the opening
3. Frame is PASSIVE rigid body, door panel is ACTIVE or kinematic
4. Use vertex snapping to ensure frame outer dimensions match wall opening

### 1.4 Texture Detail Requirements

| Detail | Implementation | Priority |
|--------|---------------|----------|
| Wood grain direction | UV-mapped along plank length, vertical grain | MUST |
| Iron straps | Separate geometry with metallic=1.0 material | MUST |
| Handle/ring | Separate mesh object, torus + cylinder, ~50 tris | SHOULD |
| Keyhole | Normal map detail, NOT geometry (saves tris) | SHOULD |
| Damage/weathering | Roughness variation map, edge wear via AO bake | SHOULD |
| Rust on iron | Roughness 0.7-0.9, slight orange tint in albedo | NICE |
| Nail heads | Normal map bumps at plank intersections | NICE |

### 1.5 Current Gaps in `riggable_objects.py`

1. **No trapdoor style** -- needs horizontal hinge axis instead of vertical
2. **No handle/ring mesh** -- doors lack grab points
3. **No damage variants** -- missing battle-damaged / broken states
4. **UV quality** -- current UVs are randomized per-plank, need proper planar projection along grain direction
5. **No LOD consideration** -- no simplified version for distance rendering

---

## 2. Rope/Chain Meshes

### 2.1 Rope Geometry

**Two approaches, use based on distance:**

| Approach | When | Tris | Visual Quality |
|----------|------|------|---------------|
| Twisted strand (geometry) | Close-up, hero props | 200-400 per meter | HIGH |
| Cylinder + normal map | Mid/far distance | 50-100 per meter | MEDIUM (looks great with good normals) |
| Spline + curve bevel | Procedural/dynamic | Variable | HIGH (Blender only, bake for export) |

**Cylinder-with-normal-map approach (recommended for most game use):**
```python
# 6-8 sided cylinder is sufficient with a good rope normal map
segments = 8  # cross-section segments
length_divisions = 10  # per meter of rope
# Total: ~160 tris per meter (8 segments * 10 divisions * 2 tris)
```

**Twisted strand approach (for hero ropes):**
```python
# 3 intertwined helixes, each 4-sided
strands = 3
strand_segments = 4
twist_rate = 2.0  # full twists per meter
# Each strand follows: x = r*cos(theta + offset), z = r*sin(theta + offset)
# where theta increases with Y position
```

**Catenary curve for natural hang:**
```python
import math

def catenary_points(start, end, sag, num_points=20):
    """Generate points along a catenary curve between two attachment points.
    
    The catenary equation: y = a * cosh((x - x0) / a) + y0
    For game purposes, a parabolic approximation is close enough and cheaper.
    """
    points = []
    for i in range(num_points + 1):
        t = i / num_points
        x = start[0] + (end[0] - start[0]) * t
        z = start[2] + (end[2] - start[2]) * t
        # Parabolic sag: maximum at midpoint (t=0.5)
        y_base = start[1] + (end[1] - start[1]) * t
        y_sag = -4.0 * sag * t * (1.0 - t)  # parabola peaking at t=0.5
        y = y_base + y_sag
        points.append((x, y, z))
    return points
```

### 2.2 Chain Link Geometry

**Poly budget per link:** 80-120 tris (current `_torus_link` uses 12 major segments x 6 tube segments = 144 quads = 288 tris -- TOO HIGH).

**Recommended reduction:**
```python
# Optimal chain link settings for game use
major_segments = 8   # around the ring (was 12)
tube_segments = 4    # cross-section (was 6)
# Result: 8 * 4 = 32 quads = 64 tris per link
# With elongation for oblong shape: ~80 tris per link
```

**Instancing strategy for long chains:**
- In Blender: Use linked duplicates (`Alt+D`) or collection instances
- For export: Bake to mesh (instances become unique geometry)
- In Unity: Use GPU instancing via `Graphics.DrawMeshInstanced()` or SRP Batcher
- Unity 6+ URP: GPU Resident Drawer handles instancing automatically
- **Critical:** All chain links sharing the same material batch together in SRP Batcher

**Chain link alternation:**
Links must alternate orientation (0/90 degrees) to interlock properly. The current `generate_chain()` correctly handles this with `orientation = i % 2`.

### 2.3 Rope/Chain Rigging for Physics

**Bone chain approach (best for FBX export):**
```python
def create_chain_rig(chain_obj, link_count, link_height):
    """Create a bone chain for rope/chain physics."""
    armature = bpy.data.armatures.new(f"{chain_obj.name}_Rig")
    rig = bpy.data.objects.new(f"{chain_obj.name}_Rig", armature)
    bpy.context.collection.objects.link(rig)
    
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    
    parent_bone = None
    for i in range(link_count):
        bone = armature.edit_bones.new(f"Link_{i:03d}")
        bone.head = (0, 0, -i * link_height)
        bone.tail = (0, 0, -(i + 1) * link_height)
        if parent_bone:
            bone.parent = parent_bone
        parent_bone = bone
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Parent mesh to armature
    chain_obj.parent = rig
    mod = chain_obj.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    
    # Weight paint: each link's vertices to corresponding bone
    # Use existing vertex_groups from generate_chain()
    for group_name, indices in chain_obj.get("vertex_groups", {}).items():
        vg = chain_obj.vertex_groups.new(name=group_name)
        vg.add(indices, 1.0, 'REPLACE')
```

**Attachment points:** The top bone should be constrained (Copy Location) to the attachment point (hook, ring, post). In Unity, use a `ConfigurableJoint` with locked position on the first link.

### 2.4 Current Gaps

1. **Chain link poly count too high** -- 288 tris/link, should be ~80
2. **No catenary curve** -- chains hang in straight lines currently
3. **No rope generator** -- only chains exist, no twisted rope mesh
4. **No bone chain rig** -- only vertex groups, no armature generation
5. **No attachment point meshes** -- hooks, rings, wall brackets missing

---

## 3. Cloth/Flag/Banner Physics

### 3.1 Optimal Cloth Mesh Topology

**The single most important rule: uniform quad grid with consistent edge length.**

```
Recommended grid density by object type:

| Object | Grid Size | Quads | Tris | Notes |
|--------|----------|-------|------|-------|
| Flag (medium) | 12x12 | 144 | 288 | Current default, good |
| Banner (tall) | 8x16 | 128 | 256 | More vertical for tall banners |
| Curtain | 10x15 | 150 | 300 | More vertical for draping |
| Tapestry | 12x16 | 192 | 384 | Wider for wall hangings |
| Window shade | 8x10 | 80 | 160 | Small, simple |
| Cape/cloak | 16x20 | 320 | 640 | Higher res for character attachment |
```

**Why uniform quads matter:**
- Cloth simulation applies spring forces between vertices
- Non-uniform edge lengths create uneven spring forces
- Triangles create directional bias in deformation
- The existing `generate_flag()` correctly creates a regular grid with `rows x cols` quads

### 3.2 Pin Constraints

**Pin placement by object type:**

| Object | Pinned Edge | Vertex Group Name | Weight |
|--------|------------|-------------------|--------|
| Banner | Top edge | `pinned` | 1.0 |
| Flag | Left edge (pole side) | `pinned` | 1.0 |
| Curtain | Top edge (rod) | `pinned` | 1.0 |
| Tapestry | Top 2 rows | `pinned` | 1.0 top, 0.5 second row |
| Window shade | Top edge + bottom bar | `pinned` | 1.0 both |
| Cape | Shoulder attachment | `pinned` | 1.0 |

**Gradient pinning for natural drape:**
```python
def create_gradient_pin_group(obj, pin_axis='Z', pin_threshold=0.9, gradient_range=0.1):
    """Create a vertex group with gradient weights for smooth cloth pinning.
    
    Vertices above pin_threshold get weight 1.0.
    Vertices in the gradient_range below get interpolated weights.
    This prevents the harsh fold line at the pin boundary.
    """
    vg = obj.vertex_groups.new(name="pinned")
    mesh = obj.data
    
    # Find bounds
    coords = [v.co[2] for v in mesh.vertices]  # Z axis
    max_z = max(coords)
    min_z = min(coords)
    height = max_z - min_z
    
    threshold_z = max_z - height * (1.0 - pin_threshold)
    gradient_z = threshold_z - height * gradient_range
    
    for v in mesh.vertices:
        z = v.co[2]
        if z >= threshold_z:
            vg.add([v.index], 1.0, 'REPLACE')
        elif z >= gradient_z:
            # Linear interpolation in gradient zone
            t = (z - gradient_z) / (threshold_z - gradient_z)
            vg.add([v.index], t, 'REPLACE')
        # Vertices below gradient get weight 0.0 (free to simulate)
```

### 3.3 Wind Force Setup in Blender Python

```python
def setup_wind_force(strength=5.0, turbulence=2.0, noise=1.5, seed=42):
    """Create a wind force field for cloth simulation.
    
    Returns the wind empty object.
    """
    bpy.ops.object.effector_add(type='WIND')
    wind = bpy.context.active_object
    wind.name = "Wind_Force"
    
    # Wind blows along local -Z of the empty
    # Rotate to desired direction (e.g., blowing in +X)
    wind.rotation_euler = (math.radians(90), 0, 0)
    
    field = wind.field
    field.strength = strength        # Force magnitude
    field.flow = 0.0                 # Flow: 0 = wind, 1 = force field
    field.noise = noise              # Turbulence noise amount
    field.seed = seed                # Random seed for turbulence
    field.use_absorption = False
    
    # For turbulence/gusting effect:
    # Animate strength with noise modifier on the fcurve
    wind.keyframe_insert(data_path="field.strength", frame=1)
    
    if wind.animation_data and wind.animation_data.action:
        for fc in wind.animation_data.action.fcurves:
            mod = fc.modifiers.new(type='NOISE')
            mod.scale = 30.0          # Noise frequency
            mod.strength = turbulence  # Noise amplitude
            mod.phase = seed * 17.0
    
    return wind
```

### 3.4 Cloth Simulation Settings for Different Objects

```python
CLOTH_PRESETS = {
    "flag_heavy": {
        # Heavy canvas/wool flag
        "quality": 7,
        "mass": 0.4,
        "air_damping": 1.0,
        "tension_stiffness": 15.0,
        "compression_stiffness": 15.0,
        "bending_stiffness": 0.5,    # Low = more flexible
        "tension_damping": 5.0,
        "compression_damping": 5.0,
        "bending_damping": 0.5,
    },
    "flag_light": {
        # Light silk/linen flag
        "quality": 5,
        "mass": 0.15,
        "air_damping": 1.5,          # Higher = more wind resistance
        "tension_stiffness": 5.0,
        "compression_stiffness": 5.0,
        "bending_stiffness": 0.05,   # Very flexible
        "tension_damping": 0.0,
        "compression_damping": 0.0,
        "bending_damping": 0.5,
    },
    "curtain": {
        # Heavy draping fabric
        "quality": 5,
        "mass": 0.8,
        "air_damping": 0.5,
        "tension_stiffness": 20.0,
        "compression_stiffness": 20.0,
        "bending_stiffness": 5.0,    # Stiffer = fewer small folds
        "tension_damping": 15.0,
        "compression_damping": 15.0,
        "bending_damping": 0.5,
    },
    "banner_tattered": {
        # Torn, thin fabric
        "quality": 5,
        "mass": 0.1,
        "air_damping": 2.0,
        "tension_stiffness": 3.0,
        "compression_stiffness": 3.0,
        "bending_stiffness": 0.01,   # Extremely flexible
        "tension_damping": 0.0,
        "compression_damping": 0.0,
        "bending_damping": 0.1,
    },
    "rope_cloth": {
        # Rope simulated as cloth (for dangling ropes)
        "quality": 7,
        "mass": 0.5,
        "air_damping": 0.2,
        "tension_stiffness": 80.0,   # Very stiff along length
        "compression_stiffness": 80.0,
        "bending_stiffness": 0.5,
        "tension_damping": 25.0,
        "compression_damping": 25.0,
        "bending_damping": 0.5,
    },
}

def apply_cloth_preset(obj, preset_name, pin_group="pinned"):
    """Apply a cloth simulation preset to a mesh object."""
    preset = CLOTH_PRESETS[preset_name]
    
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # Add cloth modifier
    cloth_mod = obj.modifiers.new(name="Cloth", type="CLOTH")
    cs = cloth_mod.settings
    
    cs.quality = preset["quality"]
    cs.mass = preset["mass"]
    cs.air_damping = preset["air_damping"]
    cs.tension_stiffness = preset["tension_stiffness"]
    cs.compression_stiffness = preset["compression_stiffness"]
    cs.bending_stiffness = preset["bending_stiffness"]
    cs.tension_damping = preset["tension_damping"]
    cs.compression_damping = preset["compression_damping"]
    cs.bending_damping = preset["bending_damping"]
    
    # Set pin group
    if pin_group and pin_group in obj.vertex_groups:
        cs.vertex_group_mass = pin_group
    
    # Enable self-collision for overlapping cloth
    cloth_mod.collision_settings.use_self_collision = True
    cloth_mod.collision_settings.self_distance_min = 0.005
    
    return cloth_mod
```

### 3.5 Collision Settings

```python
def setup_cloth_collision(obj, cloth_obj):
    """Make obj a collision surface for cloth_obj's simulation."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # Add collision modifier
    col_mod = obj.modifiers.new(name="Collision", type="COLLISION")
    col_settings = col_mod.settings
    
    col_settings.thickness_outer = 0.01    # Collision shell thickness
    col_settings.thickness_inner = 0.01
    col_settings.cloth_friction = 5.0       # Friction with cloth
    col_settings.damping = 0.5
```

### 3.6 Pre-baked vs Runtime Physics Decision Matrix

| Scenario | Recommendation | Why |
|----------|---------------|-----|
| Background flags, distant banners | Pre-baked animation loop | Zero runtime cost, consistent look |
| Player-interactive curtains | Unity Cloth component | Responds to player movement |
| Quest-triggered banners | Pre-baked + trigger | Reliable, art-directed |
| Performance-critical mobile | Bone animation (spring bones) | Cheaper than cloth sim |
| Close-up hero objects | Unity Cloth with low vertex count | Best visual quality |
| Chains/ropes swinging | Pre-baked bone animation | Predictable, exportable |

### 3.7 Current Gaps in Flag/Banner Generation

1. **No curtain generator** -- missing entirely
2. **No tapestry/wall hanging generator** -- missing
3. **No window shade generator** -- missing  
4. **Flag styles limited** -- no heraldic elements, cross patterns, or torn holes in center
5. **No cloth simulation auto-setup** -- generators create mesh but don't apply cloth modifier
6. **No wind force auto-creation** -- no automated wind setup paired with flags
7. **Pole attachment needs work** -- pole and flag are merged into one mesh, should be separate for independent physics

---

## 4. Window Coverings

### 4.1 Shutters

**Topology:** Identical to doors but smaller (0.4m-0.8m width). Each shutter is a rigid panel that rotates on hinges.

```python
def generate_shutter(width=0.4, height=0.6, slat_count=5):
    """Generate a window shutter with horizontal slats.
    
    Slats are angled planks (louvers) that give medieval character.
    Each slat: 8 verts (box), angled 15-30 degrees.
    Frame: 4 box members around the edge.
    Hinge empties at left edge top/bottom.
    
    Poly budget: 100-200 tris per shutter panel.
    """
    # Frame: left/right/top/bottom rails
    # Slats: horizontal planks within frame, rotated slightly
    # Vertex groups: "frame", "slats", "hinge_side"
    # Empties: "hinge_top", "hinge_bottom"
    pass  # Implementation pattern same as door
```

**Unity integration:** Same as doors -- `HingeJoint` on each shutter panel, limited to 0-90 degree swing.

### 4.2 Curtains

**Mesh:** Regular quad grid, 10x15 subdivisions, draped with cloth sim.

```python
def generate_curtain(width=0.8, height=1.2, subdivisions=12):
    """Generate a curtain mesh ready for cloth simulation.
    
    - Regular quad grid for uniform cloth sim
    - Top edge pinned (curtain rod attachment)
    - Optional gathered folds via initial displacement
    - Vertex groups: "pinned" (top row), "hem" (bottom row), "body"
    - Empty: "rod_left", "rod_right" for curtain rod placement
    """
    # Grid generation similar to flag, but:
    # 1. Oriented in XZ plane (hanging down Z)
    # 2. Top row pinned
    # 3. Optional sine-wave displacement on X for gathered look
    # 4. Bottom row slightly heavier weight for hem draping
    pass
```

### 4.3 Window Bars (Iron Grate)

**Mesh:** Vertical and horizontal cylinders forming a grid. ~6-8 segments per bar cross-section.

```python
def generate_window_bars(width=0.6, height=0.8, bar_count=4, cross_bars=2):
    """Generate iron window bars (grate).
    
    Poly budget: 150-250 tris total.
    Each bar: 6-segment cylinder, ~24 tris.
    Cross bars: same geometry, horizontal.
    
    Material: iron, metallic=1.0, roughness=0.6-0.8.
    """
    # Vertical bars evenly spaced across width
    # Horizontal cross-bars at regular intervals
    # All quads for clean subdivision
    # Vertex group: "bars" (all geometry, for rigid body)
    pass
```

### 4.4 Broken/Damaged Window States

**Strategy:** Generate variant meshes, not runtime destruction.

| State | Modification | Tri Impact |
|-------|-------------|-----------|
| Intact | Base mesh | 0 |
| Cracked glass | Additional edge loops on glass plane forming crack pattern | +50-100 |
| Broken glass | Glass plane with holes (deleted faces), shard triangles at edges | +20-80 |
| Torn curtain | Cloth mesh with faces removed in irregular pattern | -20% (fewer faces) |
| Bent bars | Bar vertices displaced, dents via normal map | 0 |

---

## 5. Hanging Objects

### 5.1 Chandelier

**Current `generate_chandelier()` supports:** iron_ring, candelabra, bone_chandelier, cage_lantern.

**Physics approach for chandelier sway:**
```python
# Option A: Single-bone pendulum (simplest, best for game)
# One bone from ceiling to chandelier center
# Animate with sine wave for gentle sway
# Responds to wind/explosions via animation blend

# Option B: Multi-bone chain + rigid chandelier
# Chain bones (3-5 links) from ceiling
# Chandelier mesh as child of bottom bone
# Apply chain physics to bones, chandelier follows

def generate_chandelier_sway_keyframes(frame_count=120, amplitude=3.0, speed=1.0):
    """Pendulum sway animation for hanging chandelier.
    
    Uses damped sine wave for natural pendulum motion.
    Rotation around X and Z axes (slight circular sway).
    """
    keyframes = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Primary sway (X axis)
        angle_x = amplitude * math.sin(2 * math.pi * speed * t) * math.exp(-0.3 * t)
        # Secondary sway (Z axis, phase-shifted)
        angle_z = amplitude * 0.5 * math.sin(2 * math.pi * speed * t + 0.7) * math.exp(-0.3 * t)
        
        keyframes.append({
            "frame": frame,
            "rotation": (math.radians(angle_x), 0, math.radians(angle_z)),
            "channel": "rotation_euler",
        })
    return keyframes
```

### 5.2 Hanging Signs

**Current `generate_hanging_sign()` exists** with bracket and chain attachment.

**Key improvement needed:** The sign should have TWO attachment chains (left and right) for realistic two-point suspension. Currently it uses a single attachment point.

**Wind-driven rotation animation:**
- Primary axis: rotation around vertical (Y) for wind push
- Secondary axis: slight tilt forward/back
- Damped spring behavior: overshoot then settle

### 5.3 Cage Suspension

**Current `generate_cage()` supports:** hanging_cage, prison_cell, gibbet, animal_trap.

**Physics chain for cage:**
```
Ceiling attachment (static)
   |
   Chain (3-5 bone segments, physics-driven)
   |
   Cage (rigid body, child of bottom chain bone)
```

**Weight distribution:** The cage should be much heavier than the chain, creating a natural pendulum effect. Set cage mass to 50-100kg, chain link mass to 0.5-1kg each.

---

## 6. Blender Python Implementation

### 6.1 Complete Cloth Simulation Pipeline

```python
def setup_cloth_object_full(
    obj_name: str,
    pin_group: str = "pinned",
    preset: str = "flag_heavy",
    wind_strength: float = 5.0,
    bake_frames: tuple[int, int] = (1, 120),
):
    """Full cloth simulation setup: modifier + wind + bake.
    
    Steps:
    1. Apply cloth modifier with preset
    2. Create wind force field
    3. Set collision on nearby objects
    4. Bake simulation
    5. Optionally convert to shape keys or bone animation
    """
    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != 'MESH':
        raise ValueError(f"Mesh object not found: {obj_name}")
    
    # 1. Apply cloth
    cloth_mod = apply_cloth_preset(obj, preset, pin_group)
    
    # 2. Wind
    wind = setup_wind_force(strength=wind_strength)
    
    # 3. Bake
    scene = bpy.context.scene
    scene.frame_start = bake_frames[0]
    scene.frame_end = bake_frames[1]
    
    point_cache = cloth_mod.point_cache
    point_cache.frame_start = bake_frames[0]
    point_cache.frame_end = bake_frames[1]
    
    # Override context for bake (required for non-interactive)
    override = {'scene': scene, 'point_cache': point_cache}
    bpy.ops.ptcache.bake(override, bake=True)
    
    return {
        "object": obj_name,
        "preset": preset,
        "frames_baked": bake_frames[1] - bake_frames[0] + 1,
        "wind_strength": wind_strength,
    }
```

### 6.2 Baking Cloth Simulation to Exportable Formats

**Method 1: Shape Keys (best for looping animations)**
```python
def cloth_to_shape_keys(obj_name: str, frame_start=1, frame_end=120, step=1):
    """Convert baked cloth simulation to shape keys.
    
    Each frame becomes a shape key. Use for looping cloth animations
    that can be exported via glTF (supports shape keys natively).
    
    WARNING: FBX does NOT export shape key animations well.
    Use glTF format or bone method for FBX.
    """
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        raise ValueError(f"Object not found: {obj_name}")
    
    # Store reference shape
    bpy.context.scene.frame_set(frame_start)
    obj.shape_key_add(name="Basis", from_mix=False)
    
    for frame in range(frame_start, frame_end + 1, step):
        bpy.context.scene.frame_set(frame)
        
        # Apply cloth modifier as shape key
        # Note: Blender 4.x uses modifier.apply() differently
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # The cloth modifier must be applied as shape key
        # This requires the modifier to be the active one
        sk = obj.shape_key_add(name=f"Frame_{frame:04d}", from_mix=False)
        
        # Copy deformed mesh coordinates to shape key
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        
        for i, vert in enumerate(eval_mesh.vertices):
            sk.data[i].co = vert.co
        
        eval_obj.to_mesh_clear()
    
    return {"shape_keys_created": (frame_end - frame_start) // step + 1}
```

**Method 2: Bone-based bake (best for FBX/Unity export) -- RECOMMENDED**
```python
def cloth_to_bones(obj_name: str, bone_count=None, frame_start=1, frame_end=120):
    """Convert cloth simulation to bone-driven animation using Mesh2Rig approach.
    
    Strategy:
    1. Create a grid of bones matching the cloth mesh topology
    2. For each frame, sample deformed vertex positions
    3. Calculate bone transforms to match deformation
    4. Keyframe bone transforms
    
    This exports cleanly via FBX with armature animation.
    """
    obj = bpy.data.objects.get(obj_name)
    mesh = obj.data
    
    # Determine bone grid: one bone per N vertices
    vert_count = len(mesh.vertices)
    if bone_count is None:
        # ~1 bone per 4-9 vertices for cloth
        bone_count = max(4, vert_count // 6)
    
    # Create armature with bone grid
    armature = bpy.data.armatures.new(f"{obj_name}_ClothRig")
    rig = bpy.data.objects.new(f"{obj_name}_ClothRig", armature)
    bpy.context.collection.objects.link(rig)
    
    # ... (bone creation, weight painting, keyframe sampling)
    # This is complex -- recommend using Mesh2Rig addon for production
    
    return {"bones_created": bone_count, "frames": frame_end - frame_start + 1}
```

### 6.3 Spring Bones vs Cloth Sim Performance Comparison

| Factor | Cloth Sim (Blender bake) | Cloth Sim (Unity runtime) | Spring Bones (Unity) |
|--------|-------------------------|--------------------------|---------------------|
| Setup complexity | Medium | Low | Low |
| Visual quality | HIGH (pre-baked) | MEDIUM | LOW-MEDIUM |
| Runtime CPU cost | Zero (pre-baked) | HIGH (per vertex) | LOW (per bone) |
| Interactivity | None (pre-baked) | Full | Partial |
| Memory cost | Animation data | Cloth state | Bone transforms |
| Export method | FBX with armature/shape keys | Unity Cloth component | FBX bones + Unity script |
| Recommended for | Background props, hero cutscenes | Player-worn cloaks | Chains, hair, tails |

**Recommendation:** Use pre-baked cloth-to-bone animation for most environmental objects (flags, banners, curtains). Use Unity Cloth component only for objects the player interacts with directly. Use spring bones (EZSoftBone or Unity-chan Spring Bone) for chains, hanging signs, and other rigid-body-on-spring objects.

### 6.4 FBX Export Settings for Rigged/Animated Objects

The existing `handle_export_fbx()` in `export.py` already handles most requirements. Key settings for riggable environmental objects:

```python
# Critical FBX settings for rigged props (already in export.py):
"axis_forward": "-Z",              # Unity coordinate system
"axis_up": "Y",                    # Unity coordinate system
"bake_space_transform": True,      # Apply transforms
"use_armature_deform_only": True,  # Only export deform bones
"add_leaf_bones": False,           # NOT needed for props (only humanoid)
"use_mesh_modifiers": True,        # Bake cloth/other modifiers

# Additional settings needed for environmental props:
"use_active_collection": False,    # Export all or selected
"bake_anim": True,                 # Include animation data
"bake_anim_use_all_bones": True,   # All bone keyframes
"bake_anim_use_nla_strips": False, # Single action per file
"bake_anim_simplify_factor": 0.0,  # No keyframe reduction (preserve quality)
```

**Root bone requirement:** Unity expects a root bone at object origin. For prop rigs (doors, chains), the first bone should be at the pivot point. Name it `Root` or `Prop_Root`.

**Animation clip splitting:** Export each animation (e.g., door_open, door_close, door_slam) as a separate FBX file, OR use Unity's animation clip splitting in the import inspector (define frame ranges per clip).

### 6.5 Unity Import Configuration

```csharp
// Unity C# editor script for configuring imported rigged props
[MenuItem("VeilBreakers/Setup Rigged Prop")]
static void SetupRiggedProp()
{
    var obj = Selection.activeGameObject;
    if (obj == null) return;
    
    // For doors: add HingeJoint
    var hinge = obj.AddComponent<HingeJoint>();
    hinge.anchor = new Vector3(0, 0, 0);  // At hinge bone position
    hinge.axis = Vector3.up;               // Vertical rotation axis
    hinge.useLimits = true;
    var limits = hinge.limits;
    limits.min = 0;
    limits.max = 90;
    hinge.limits = limits;
    
    // For cloth objects: add Cloth component
    // Only if the mesh has enough vertices for simulation
    var smr = obj.GetComponent<SkinnedMeshRenderer>();
    if (smr != null && smr.sharedMesh.vertexCount > 50)
    {
        var cloth = obj.AddComponent<Cloth>();
        cloth.bendingStiffness = 0.5f;
        cloth.stretchingStiffness = 0.8f;
        cloth.damping = 0.1f;
        cloth.externalAcceleration = new Vector3(2f, 0, 0); // Wind
        
        // Pin top vertices (from vertex colors or by position)
        var coefficients = cloth.coefficients;
        var verts = smr.sharedMesh.vertices;
        float maxY = verts.Max(v => v.y);
        for (int i = 0; i < coefficients.Length; i++)
        {
            float normalizedY = verts[i].y / maxY;
            coefficients[i].maxDistance = normalizedY < 0.1f ? 0f : 
                                          Mathf.Lerp(0f, 1f, normalizedY);
        }
        cloth.coefficients = coefficients;
    }
}
```

---

## 7. Quality Topology Rules for Deformable Objects

### 7.1 Universal Rules

1. **Edge loops MUST follow deformation paths**
   - For hinged objects: edge loop parallel to hinge axis at the hinge line
   - For cloth: uniform grid (inherently follows all directions)
   - For chains: rings of edges around each link's bend points

2. **Minimum 3 edge loops across any bending area**
   - A hinge needs at least 3 loops: before, at, and after the pivot
   - A chain link bend needs 3+ loops around the curve
   - A cloth fold naturally creates this via the simulation grid

3. **Quads only in deformation zones**
   - Triangles create directional stiffness in cloth sim
   - N-gons collapse unpredictably under deformation
   - Poles (5+ edge vertices) cause pinching -- move them to flat/static areas
   - The existing generators correctly use all-quad topology

4. **Weight painting distribution**
   ```
   Rigid objects (doors, shutters): Binary weights (0.0 or 1.0)
   Soft objects (cloth, rope): Gradient weights at transitions
   Chain links: Each link 100% to its bone, no blending between links
   ```

5. **Preventing self-intersection**
   - Cloth: Enable self-collision (`collision_settings.use_self_collision = True`)
   - Set `self_distance_min` to at least 2x the mesh thickness
   - For chains: use rigid body, NOT cloth sim (links should not deform)
   - For doors: rigid body prevents intersection with frame

### 7.2 Specific Topology Patterns

**Door panel (rigid, no deformation):**
```
+--+--+--+--+--+
|  |  |  |  |  |   <- Individual planks, each a box
+--+--+--+--+--+   <- Gaps between planks (separate geometry)
|  |  |  |  |  |
+--+--+--+--+--+
```

**Flag/cloth mesh (uniform deformation):**
```
+--+--+--+--+--+--+   <- Pinned row (top)
|  |  |  |  |  |  |
+--+--+--+--+--+--+
|  |  |  |  |  |  |   <- Free-flowing quads
+--+--+--+--+--+--+   <- All edges same length
|  |  |  |  |  |  |
+--+--+--+--+--+--+
```

**Chain link cross-section (8 sides minimum):**
```
    --
  /    \
 |      |   <- 8-segment ring, each segment = 1 quad
  \    /
    --
```

**Rope cross-section (6-8 sides):**
```
   /\
  /  \
 |    |   <- 6-segment cylinder sufficient with normal map
  \  /
   \/
```

---

## 8. Implementation Priority

### Phase 1: Fix Existing Generators (Estimated: 2-3 days)

| Task | File | Impact |
|------|------|--------|
| Reduce chain link segments (12x6 -> 8x4) | `riggable_objects.py` | -65% chain tris |
| Add catenary curve to chain generation | `riggable_objects.py` | Natural hanging |
| Improve flag UV mapping (consistent grid UVs) | `riggable_objects.py` | Better texturing |
| Add trapdoor style to `generate_door()` | `riggable_objects.py` | New door type |
| Add door handle/ring mesh | `riggable_objects.py` | Visual completeness |

### Phase 2: New Generators (Estimated: 3-4 days)

| Task | File | Impact |
|------|------|--------|
| Curtain generator (quad grid + rod) | `riggable_objects.py` | New object type |
| Window shutter generator | `riggable_objects.py` | New object type |
| Window bars/grate generator | `riggable_objects.py` | New object type |
| Rope mesh generator (twisted strand) | `riggable_objects.py` | New object type |
| Tapestry/wall hanging generator | `riggable_objects.py` | New object type |

### Phase 3: Physics & Rigging Pipeline (Estimated: 3-4 days)

| Task | File | Impact |
|------|------|--------|
| Cloth preset system (`CLOTH_PRESETS`) | `physics.py` | Automated cloth setup |
| Wind force auto-setup with turbulence | `physics.py` | Paired with cloth |
| Cloth-to-bone bake pipeline | `physics.py` | FBX export path |
| Bone chain generator for ropes/chains | `rigging.py` | Physics-ready rigs |
| Gradient pin groups for cloth | `physics.py` | Better cloth behavior |

### Phase 4: Export & Unity Integration (Estimated: 2-3 days)

| Task | File | Impact |
|------|------|--------|
| Prop-specific FBX settings (no leaf bones) | `export.py` | Clean Unity import |
| Animation clip per-action export | `animation_export.py` | Separate clips |
| Unity door system C# template | `unity_templates/world.py` | HingeJoint setup |
| Unity cloth setup C# template | `unity_templates/world.py` | Cloth component |
| Unity spring bone C# template | `unity_templates/world.py` | Chain/rope physics |

---

## 9. Pitfalls & Warnings

### Critical

1. **FBX does NOT support vertex animation (shape keys with animation).** Cloth simulations MUST be converted to bone-based animation or exported as Alembic (Unity supports Alembic but with caveats). The recommended path is cloth-to-bone bake.

2. **Unity Cloth component requires SkinnedMeshRenderer.** You cannot add Cloth to a MeshRenderer -- the mesh must have blend shapes or an armature. For static cloth (pre-baked), use Animator with baked clips instead.

3. **Blender's `ptcache.bake` operator requires specific context override.** The current `handle_bake_physics()` uses `{"point_cache": point_cache}` which may fail in Blender 4.x. Use `bpy.context.temp_override()` pattern instead.

### Moderate

4. **Chain GPU instancing breaks with different materials.** All instances must share the exact same material for batching. Use material property blocks for per-instance variation (rust amount, etc.).

5. **Cloth simulation frame dependency.** Cloth sim results depend on starting frame. Always start from frame 1, never scrub to a random frame and expect correct results. The bake must run sequentially.

6. **Armature export and bone naming.** Unity strips bone name prefixes (`DEF-`, `MCH-`, etc.) inconsistently. Use simple names (`Bone_001`, `Link_003`) for prop rigs to avoid import issues.

### Minor

7. **Over-subdivided cloth meshes kill performance.** A 20x20 grid (400 quads) is the maximum for Unity Cloth at runtime. Pre-baked cloth can be higher resolution since the cost is only in animation data.

8. **Door rotation direction.** Ensure the hinge bone's local axis matches Unity's HingeJoint axis. Blender uses Z-up, Unity uses Y-up -- the export's `axis_forward`/`axis_up` settings handle this, but verify with visual test.

---

## Sources

### Web Research
- [Blender cloth to Unity FBX discussion](https://discussions.unity.com/t/bake-cloth-simulation-from-blender-to-unity/774224)
- [Blender cloth to keyframes conversion](https://blenderartists.org/t/how-to-convert-a-cloth-simulation-animation-to-keyframes/600133)
- [FBX cloth animation export](https://blenderartists.org/t/export-cloth-simulation-animation-to-fbx-file/1233863)
- [Unity HingeJoint for doors](https://playgama.com/blog/unity/how-can-i-use-hinge-joints-in-unity-to-create-realistic-door-mechanics-for-my-game/)
- [GPU instancing Unity URP](https://docs.unity3d.com/Manual/GPUInstancing.html)
- [Unity GPU Resident Drawer](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/gpu-resident-drawer.html)
- [Mesh topology best practices](https://www.meshy.ai/blog/mesh-topology)
- [Topology for game-ready assets](https://www.gameaningstudios.com/topology-for-game-ready-assets/)
- [Edge flow in 3D modeling](https://www.whizzystudios.com/post/why-edge-flow-matters-in-3d-modeling-and-how-to-improve-it)
- [Blender ClothSettings API](https://docs.blender.org/api/current/bpy.types.ClothSettings.html)
- [Blender FieldSettings API](https://docs.blender.org/api/current/bpy.types.FieldSettings.html)
- [EZSoftBone - Spring bone for Unity](https://github.com/EZhex1991/EZSoftBone)
- [Mesh2Rig Blender addon](https://extensions.blender.org/add-ons/mesh2rig/)
- [Cloth to Shape Keys workflow](https://odederell3d.blog/2018/08/17/blender-cloth-animation-to-shape-keys/)
- [Unity Cloth component performance](https://discussions.unity.com/t/how-is-cloth-performance-related-to-the-whole-vertex-count-of-a-skinned-mesh-with-cloth-component/681908)

### Codebase (verified)
- `Tools/mcp-toolkit/blender_addon/handlers/riggable_objects.py` -- 10 generator functions verified
- `Tools/mcp-toolkit/blender_addon/handlers/physics.py` -- 4 physics handlers verified
- `Tools/mcp-toolkit/blender_addon/handlers/animation_environment.py` -- 27 animation types verified
- `Tools/mcp-toolkit/blender_addon/handlers/export.py` -- FBX export settings verified
- `Tools/mcp-toolkit/blender_addon/handlers/clothing_system.py` -- 12 garment types verified
- `Tools/mcp-toolkit/blender_addon/handlers/rigging_templates.py` -- Rigify templates verified
