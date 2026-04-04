# Cliff Face, Cave Entrance & Canyon Wall Design Research

**Domain:** Procedural geological feature generation for dark fantasy action RPG
**Researched:** 2026-04-03
**Overall Confidence:** HIGH (cross-referenced Blender API docs, academic papers, AAA postmortems, existing codebase)
**Target:** VeilBreakers `terrain_features.py`, `_terrain_depth.py`, `environment.py` cliff/cave/canyon generators

---

## Table of Contents

1. [Current Codebase State](#1-current-codebase-state)
2. [Cliff Face Geometry](#2-cliff-face-geometry)
3. [Cave Entrances](#3-cave-entrances)
4. [Mountain Integration](#4-mountain-integration)
5. [Canyon / Gorge Walls](#5-canyon--gorge-walls)
6. [Dark Fantasy Aesthetic](#6-dark-fantasy-aesthetic)
7. [Material & Shader Strategy](#7-material--shader-strategy)
8. [BMesh Code Patterns](#8-bmesh-code-patterns)
9. [Implementation Recommendations](#9-implementation-recommendations)
10. [Sources](#10-sources)

---

## 1. Current Codebase State

### What Exists

The toolkit already has cliff/cave/canyon generators in three files:

**`terrain_features.py`** (pure logic, no bpy):
- `generate_cliff_face()` -- vertical cliff with overhang, cave entrances, ledge path
- `generate_canyon()` -- walkable canyon with floor path, walls, side caves
- `generate_waterfall()` -- step-down cliff with splash pool, cave behind

**`_terrain_depth.py`** (pure logic, no bpy):
- `generate_cliff_face_mesh()` -- curved vertical cliff face with noise displacement
- `generate_cave_entrance_mesh()` -- semicircular arch with tunnel

**`environment.py`** (Blender handler):
- Auto-places cliff overlays at steep terrain edges via `detect_cliff_edges()`
- Creates cliff mesh objects parented to terrain

### What Is Missing (Why This Research Exists)

The existing generators produce **flat, featureless walls** with simple noise displacement. They lack:

1. **Rock strata layers** -- No horizontal banding of hard/soft rock. Current cliff faces are uniform noise on a plane.
2. **Erosion channels** -- No vertical water-carved grooves. Just random Gaussian noise.
3. **Undercuts** -- No differential erosion where soft layers recede behind hard layers.
4. **True overhangs** -- Only a linear lean at top 30%. No protruding ledges at arbitrary heights.
5. **Surface roughness variation** -- No micro/meso/macro detail hierarchy. Single noise octave.
6. **Talus/scree** -- No debris at cliff base.
7. **Cave entrance integration** -- Caves are metadata dicts, not actual geometry cut into the cliff mesh.
8. **Canyon strata matching** -- Left and right canyon walls don't share geological layers.
9. **Dark fantasy details** -- No corruption veins, carved runes, hanging roots, or nesting sites.

---

## 2. Cliff Face Geometry

### 2.1 Layered Rock Strata (The Core Technique)

Real cliffs show **horizontal bands** of alternating hard and soft rock. This is the single most important visual feature that separates realistic cliffs from noise-displaced planes.

**The Strata Profile Model:**

Define a 1D profile function `strata_profile(z)` that returns `(hardness, protrusion)` for any height:

```python
def build_strata_profile(height: float, num_layers: int, seed: int = 0):
    """Generate alternating hard/soft rock layers.
    
    Returns list of layer dicts with z_start, z_end, hardness, color_id.
    Hard layers protrude; soft layers are recessed.
    """
    rng = random.Random(seed)
    layers = []
    z = 0.0
    for i in range(num_layers):
        # Vary layer thickness: hard layers are thinner, soft are thicker
        is_hard = (i % 2 == 0)
        thickness = rng.uniform(0.3, 1.2) if is_hard else rng.uniform(0.8, 2.5)
        if z + thickness > height:
            thickness = height - z
        layers.append({
            "z_start": z,
            "z_end": z + thickness,
            "hardness": rng.uniform(0.7, 1.0) if is_hard else rng.uniform(0.1, 0.4),
            "protrusion": rng.uniform(0.3, 0.8) if is_hard else rng.uniform(-0.8, -0.2),
            "color_id": "hard_rock" if is_hard else "soft_rock",
        })
        z += thickness
        if z >= height:
            break
    return layers
```

**Applying strata to cliff mesh vertices:**

For each vertex at height `z`, look up which layer it falls in. Displace the vertex along the cliff normal by the layer's `protrusion` value, plus noise scaled by `(1 - hardness)` (soft rock is rougher/more eroded):

```python
def apply_strata_displacement(z: float, layers: list, x: float, seed: int) -> float:
    """Return Y displacement for a cliff vertex at height z."""
    for layer in layers:
        if layer["z_start"] <= z < layer["z_end"]:
            # Base protrusion from layer hardness
            base = layer["protrusion"]
            # Soft rock gets more erosion noise
            erosion_noise = fbm(x * 0.3, z * 0.5, seed, octaves=3)
            erosion_amount = erosion_noise * (1.0 - layer["hardness"]) * 0.5
            return base + erosion_amount
    return 0.0
```

**Layer edge detail:** At boundaries between hard and soft layers, add a slight lip/overhang on the hard layer side (hard rock protruding over eroded soft rock below). This is the most visually impactful detail:

```python
# At layer boundary, check if transitioning from soft (below) to hard (above)
if prev_layer["hardness"] < 0.5 and curr_layer["hardness"] > 0.5:
    # Add overhang lip: vertices just above the boundary protrude extra
    boundary_factor = 1.0 - min(1.0, (z - curr_layer["z_start"]) / 0.3)
    extra_protrusion = boundary_factor * 0.4  # lip extends 0.4 units
```

### 2.2 Vertical Erosion Channels

Water-carved grooves running down the cliff face. These are critical for realism.

**Technique:** Define vertical channel paths as 1D splines along the X axis. For each channel, carve a concave groove into the cliff surface:

```python
def generate_erosion_channels(width: float, num_channels: int, seed: int):
    """Generate X positions and widths of vertical erosion channels."""
    rng = random.Random(seed)
    channels = []
    for _ in range(num_channels):
        cx = rng.uniform(-width * 0.4, width * 0.4)
        cw = rng.uniform(0.3, 1.5)  # channel width
        cd = rng.uniform(0.2, 0.8)  # channel depth (how far it recedes)
        channels.append({"x_center": cx, "width": cw, "depth": cd})
    return channels

def channel_displacement(x: float, channels: list) -> float:
    """Return additional Y recession for erosion channels at position x."""
    displacement = 0.0
    for ch in channels:
        dist = abs(x - ch["x_center"])
        if dist < ch["width"]:
            # Smooth concave profile (parabolic)
            t = dist / ch["width"]
            displacement -= ch["depth"] * (1.0 - t * t)
    return displacement
```

### 2.3 Horizontal Undercuts

Where soft layers erode far beneath hard layers, creating sheltered overhangs:

```python
def undercut_profile(z: float, layers: list) -> float:
    """Deep recession at soft layers adjacent to hard layers above."""
    for i, layer in enumerate(layers):
        if layer["z_start"] <= z < layer["z_end"] and layer["hardness"] < 0.3:
            # Check if hard layer above
            if i + 1 < len(layers) and layers[i + 1]["hardness"] > 0.7:
                # Deep undercut: recede up to 2x normal soft layer recession
                depth_in_layer = (z - layer["z_start"]) / (layer["z_end"] - layer["z_start"])
                # Undercut deepest at top of soft layer (just under the hard cap)
                return -1.5 * (depth_in_layer ** 0.5)
    return 0.0
```

### 2.4 Multi-Scale Noise Hierarchy

AAA rock surfaces use 3 noise scales, not 1:

| Scale | Frequency | Amplitude | Purpose |
|-------|-----------|-----------|---------|
| Macro | 0.02-0.05 | 1.0-3.0 | Large bulges, overall cliff shape |
| Meso | 0.1-0.3 | 0.3-0.8 | Rock face irregularity, shelf edges |
| Micro | 0.5-1.5 | 0.05-0.15 | Surface grain, pitting |

```python
def multi_scale_rock_noise(x: float, z: float, seed: int) -> float:
    """Three-octave rock surface displacement."""
    macro = fbm(x * 0.03, z * 0.03, seed, octaves=2) * 2.0
    meso = fbm(x * 0.15, z * 0.2, seed + 100, octaves=3) * 0.5
    micro = fbm(x * 0.8, z * 1.0, seed + 200, octaves=2) * 0.1
    return macro + meso + micro
```

### 2.5 Cliff as Overlay Mesh (Not Heightmap Modification)

**Critical architectural decision:** Cliff faces must be separate mesh objects overlaid at steep terrain edges, NOT modifications to the terrain heightmap. Reasons:

1. Heightmaps cannot represent overhangs (each X,Y has one Z)
2. Cliff meshes need different material slots than terrain
3. Cliff meshes need higher poly density than surrounding terrain
4. Cliff meshes can be LOD'd independently

The existing `environment.py` already does this correctly via `detect_cliff_edges()` and `generate_cliff_face_mesh()`. The improvement needed is in the mesh quality, not the placement architecture.

### 2.6 Recommended Cliff Face Grid Resolution

| Cliff Height | Vertical Segments | Horizontal Segments | Rationale |
|--------------|-------------------|---------------------|-----------|
| 5-10m | 16-20 | 12-16 | Enough for 2-3 strata layers |
| 10-25m | 24-32 | 16-24 | 4-6 strata layers visible |
| 25-50m | 40-64 | 24-40 | 8-12 layers, LOD critical |

Rule of thumb: approximately 2 vertical segments per meter of cliff height for strata detail, and 1 horizontal segment per 1.5m of width.

---

## 3. Cave Entrances

### 3.1 Cave Mouth Shape Vocabulary

| Shape | Description | When to Use | Generation Approach |
|-------|-------------|-------------|---------------------|
| **Arched** | Semicircular top, vertical sides | Default cave entrance | Existing `_terrain_depth.py` approach works |
| **Slot** | Tall and narrow, vertical crack | Cliff crevice, hidden passage | Stretch arch profile: height >> width |
| **Collapsed** | Irregular top, fallen boulders | Abandoned/old caves | Arch + random vertex displacement + rubble meshes |
| **Keyhole** | Narrow bottom, wider top | Water-carved caves | Inverse tapered arch, wider upper profile |
| **Overhung** | Low ceiling, wide floor | Undercut shelters | Horizontal slot with curved ceiling |

### 3.2 Integration with Cliff Strata

The cave entrance must be **cut into the cliff face strata**, not floating in front of it. Implementation:

1. Generate the cliff face mesh with strata layers as normal
2. Identify vertices within the cave mouth boundary (elliptical test)
3. Displace those vertices backward (deeper into the cliff) along -Y
4. The cave arch profile follows the strata bands -- hard rock forms the arch lintel, soft rock forms the recessed interior

```python
def carve_cave_into_cliff(cliff_verts, cave_position, cave_width, cave_height):
    """Displace cliff vertices within cave boundary to create entrance.
    
    Vertices inside the cave ellipse are pushed back into the cliff.
    Vertices on the boundary get a smooth falloff transition.
    """
    cx, cz = cave_position[0], cave_position[2]
    hw, hh = cave_width / 2, cave_height / 2
    
    for i, (vx, vy, vz) in enumerate(cliff_verts):
        # Elliptical distance from cave center
        dx = (vx - cx) / hw
        dz = (vz - cz) / hh
        dist = math.sqrt(dx * dx + dz * dz)
        
        if dist < 1.0:
            # Inside cave mouth: push back
            depth_factor = (1.0 - dist) ** 2  # smooth falloff
            recession = -2.0 * depth_factor  # 2m deep at center
            cliff_verts[i] = (vx, vy + recession, vz)
        elif dist < 1.3:
            # Boundary zone: slight recess for smooth transition
            blend = (1.3 - dist) / 0.3
            cliff_verts[i] = (vx, vy - 0.3 * blend, vz)
```

### 3.3 Cave Interior Visible from Outside

The visible interior (first 2-5m) should include:

- **Dark interior gradient:** Vertex color or material darkening toward the back
- **Stalactites at entrance edge:** Small cone meshes hanging from the arch top
- **Damp/wet rock material:** Lower roughness (shinier) on cave interior walls
- **Floor rubble:** Scattered small rock meshes at the entrance

**Stalactite generation (cone taper approach):**

```python
def generate_stalactite(length: float = 0.5, base_radius: float = 0.08, 
                        segments: int = 6, seed: int = 0) -> MeshSpec:
    """Generate a single stalactite as a tapered cone with noise.
    
    Hangs downward from origin (tip at -Z).
    """
    rng = random.Random(seed)
    verts = [(0.0, 0.0, 0.0)]  # tip
    faces = []
    
    num_rings = max(3, int(length * 4))
    for ri in range(num_rings):
        t = (ri + 1) / num_rings  # 0 at tip, 1 at base
        z = t * length  # grows upward from tip
        radius = base_radius * (t ** 0.7)  # tapers toward tip
        
        for si in range(segments):
            angle = 2 * math.pi * si / segments
            noise = rng.gauss(0, radius * 0.15)
            r = radius + noise
            x = math.cos(angle) * r
            y = math.sin(angle) * r
            verts.append((x, y, z))
    
    # Tip fan
    for si in range(segments):
        v1 = 1 + si
        v2 = 1 + (si + 1) % segments
        faces.append((0, v1, v2))
    
    # Ring-to-ring quads
    for ri in range(num_rings - 1):
        base = 1 + ri * segments
        next_base = base + segments
        for si in range(segments):
            v0 = base + si
            v1 = base + (si + 1) % segments
            v2 = next_base + (si + 1) % segments
            v3 = next_base + si
            faces.append((v0, v1, v2, v3))
    
    return verts, faces
```

### 3.4 Rubble/Debris at Entrance

Scatter 5-15 small rock meshes at the cave entrance floor. Use the existing `procedural_meshes.py` rock generators (they exist in the "NATURAL FORMATIONS" category). Place them with:

- Concentration highest at the drip line (directly below cave arch edge)
- Sizes 0.1m to 0.6m
- Slight embedding into ground (lower Y by 30% of height)
- Random rotation around all axes

---

## 4. Mountain Integration

### 4.1 Cliff-to-Terrain Transitions

The most common visual artifact is a hard edge where cliff mesh meets terrain. Three transition zones are needed:

**Cliff Top (grass to exposed rock to cliff edge):**
```
Terrain surface (grass)
  |
  v  [3-5m transition zone: grass thins, rock patches appear]
  |
  v  [1-2m exposed rock zone: bare stone, no vegetation]
  |
  v  Cliff edge (slight rounding, NOT a knife-edge)
  |
  v  Cliff face begins
```

Implementation: At the cliff top, add a "cap" strip of vertices that curves from horizontal (terrain slope) to vertical (cliff face). This prevents the hard 90-degree edge:

```python
def generate_cliff_cap(cliff_width, cap_depth=2.0, cap_segments=4):
    """Generate rounded cap at cliff top to transition from terrain.
    
    Creates a curved strip from horizontal to vertical.
    """
    verts = []
    faces = []
    for ix in range(cliff_width_segments):
        x = (ix / (cliff_width_segments - 1) - 0.5) * cliff_width
        for ci in range(cap_segments):
            t = ci / (cap_segments - 1)
            # Quarter-circle curve from horizontal to vertical
            angle = t * math.pi / 2  # 0 = horizontal, pi/2 = vertical
            y = -math.sin(angle) * cap_depth  # forward protrusion
            z = math.cos(angle) * cap_depth    # height above cliff top
            verts.append((x, y, z_cliff_top + z))
    # Build quad faces between adjacent columns...
    return verts, faces
```

**Cliff Base (scree/talus fan):**

The base of a cliff accumulates debris in a characteristic fan shape:

| Feature | Size | Slope Angle | Material |
|---------|------|-------------|----------|
| Talus fan | 5-15m from cliff base | 30-38 degrees | Large angular boulders |
| Scree slope | 3-8m from cliff base | 28-35 degrees | Small rock fragments |
| Soil transition | Beyond scree | < 20 degrees | Soil with sparse vegetation |

Generate the talus as a wedge-shaped mesh at the cliff base, with scattered boulder meshes on top:

```python
def generate_talus_fan(cliff_width, cliff_height, seed=0):
    """Talus/scree fan at cliff base.
    
    The fan extends outward from the cliff base, sloping down at ~33 degrees.
    Height of fan is approximately cliff_height * 0.15 to 0.25.
    """
    fan_height = cliff_height * 0.2
    fan_extent = fan_height / math.tan(math.radians(33))  # ~33 degree slope
    # Generate a wedge mesh tapering from cliff base to ground level
    # Scatter boulder meshes on surface
```

### 4.2 Mountain Ridgeline Profiles

| Profile Type | Cross-Section | When to Use |
|--------------|---------------|-------------|
| Knife-edge | Triangle with steep sides | Young mountains, volcanic ridges |
| Rounded dome | Parabolic curve | Old weathered mountains |
| Stepped | Multiple flat terraces | Horizontally bedded sedimentary |
| Jagged | Irregular spikes | Freeze-thaw weathered granite |

For VeilBreakers dark fantasy, use **stepped + jagged** -- ancient layered mountains with weathered peaks. This is consistent with the established late medieval Gothic aesthetic.

---

## 5. Canyon / Gorge Walls

### 5.1 Canyon Cross-Section Profiles

Real canyons have characteristic cross-section shapes based on geology:

| Type | Width:Depth Ratio | Wall Angle | Example |
|------|-------------------|------------|---------|
| **V-canyon** | 1:1 to 2:1 | 45-70 degrees | Young river canyon |
| **Box canyon** | 1:2 to 1:1 | 80-90 degrees | Hard caprock over soft layers |
| **Slot canyon** | 1:5 to 1:20 | Near vertical | Water-carved sandstone |
| **Stepped canyon** | Variable | Alternating vertical/horizontal | Grand Canyon style |

For dark fantasy, **box canyon** and **stepped canyon** provide the most dramatic and usable spaces.

### 5.2 Strata Matching Across Canyon Walls

**Critical:** Both canyon walls must share the same geological layer profile. They were originally one piece of rock that eroded apart. If the left wall shows a hard red sandstone band at height 8m, the right wall must show the same band at approximately 8m (with slight vertical offset for geological tilting).

```python
def generate_canyon_with_matched_strata(
    width, length, depth, num_layers, seed=0
):
    """Generate canyon with geologically consistent walls.
    
    Both walls share the same strata profile, ensuring visual coherence.
    """
    # Generate ONE strata profile, used for BOTH walls
    strata = build_strata_profile(depth, num_layers, seed)
    
    # Optional: slight geological tilt (layers not perfectly horizontal)
    tilt_angle = random.uniform(-3, 3)  # degrees
    
    left_wall = generate_canyon_wall(strata, side="left", tilt=tilt_angle, ...)
    right_wall = generate_canyon_wall(strata, side="right", tilt=tilt_angle, ...)
    
    floor = generate_canyon_floor(width, length, ...)
    
    return merge_meshes([left_wall, right_wall, floor])
```

### 5.3 Canyon Width Variation

Canyons are NOT uniform width. They narrow at hard rock layers and widen at soft rock layers. Additionally, the plan-view path should meander:

```python
def canyon_width_at_position(x_along_canyon, base_width, strata_at_depth):
    """Canyon width varies with rock hardness at river level."""
    # Hard rock at river level = narrow canyon
    # Soft rock at river level = wider canyon
    bottom_layer = strata_at_depth[0]  # lowest layer
    width_factor = 1.0 + (1.0 - bottom_layer["hardness"]) * 0.6
    
    # Add sinusoidal meander
    meander = math.sin(x_along_canyon * 0.05) * base_width * 0.3
    
    return base_width * width_factor + meander
```

### 5.4 Canyon Floor Features

| Feature | Generation Method | Placement |
|---------|-------------------|-----------|
| River/stream | Bezier spline mesh, low-poly plane with flow UVs | Center of canyon floor |
| Gravel banks | Noise-displaced strips beside river | River edges |
| Large boulders | Rock mesh instances from procedural_meshes.py | Scattered on gravel, some in river |
| Dried mud flats | Flat quads with Voronoi crack pattern | Wider sections |
| Pool/waterfall | Flat water plane + step geometry | Where canyon narrows |

### 5.5 Slot Canyon Geometry

Slot canyons are very narrow (0.5-3m) and very tall (10-30m). They need special treatment:

- Walls nearly parallel but with smooth undulations
- Walls sometimes touch at the top (natural bridge)
- Filtered light from above -- vertex color darkening toward bottom
- Smooth, water-polished surfaces (low roughness material)
- Rounded corners, not angular (water erosion rounds everything)

```python
def generate_slot_canyon(length, depth, min_width=0.5, max_width=3.0, seed=0):
    """Slot canyon with undulating walls and natural bridges."""
    # Width varies smoothly along length
    # Use sin/cos superposition for organic width variation
    def width_at(x):
        w = (min_width + max_width) / 2
        w += math.sin(x * 0.2) * (max_width - min_width) * 0.3
        w += math.sin(x * 0.7 + 1.5) * (max_width - min_width) * 0.15
        return max(min_width, w)
```

---

## 6. Dark Fantasy Aesthetic

### 6.1 Corruption Veins

Glowing purple/black fissures running through rock. Implementation:

1. **Geometry:** Select random edges on cliff mesh, extrude inward slightly to create crevice geometry
2. **Material:** Assign emissive material to crevice faces (purple/dark magenta, emission strength 2-5)
3. **Pattern:** Veins follow strata layer boundaries and vertical cracks (they exploit existing weaknesses in rock)

```python
def add_corruption_veins(cliff_verts, cliff_faces, strata_layers, seed=0, 
                         density=0.1):
    """Add glowing corruption vein geometry to cliff face.
    
    Veins are narrow crevice meshes at strata boundaries and random 
    vertical cracks. Returns additional verts/faces with emissive material.
    """
    rng = random.Random(seed)
    vein_verts = []
    vein_faces = []
    
    # Horizontal veins at layer boundaries
    for layer in strata_layers:
        if rng.random() > density:
            continue
        z = layer["z_end"]
        # Create thin strip at this height
        # Width: 0.02-0.08m, recessed 0.1m into cliff
        ...
    
    # Vertical veins (random cracks)
    num_vertical = int(len(strata_layers) * density * 3)
    for _ in range(num_vertical):
        x = rng.uniform(...)
        z_start = rng.uniform(0, cliff_height * 0.3)
        z_end = z_start + rng.uniform(1.0, cliff_height * 0.5)
        # Branching: main vein + 1-2 offshoots
        ...
```

### 6.2 Carved Faces / Runes

Ancient civilization markers carved into cliff walls:

- **Placement:** On hard rock strata layers (soft rock would have eroded them away)
- **Technique:** Inset faces on cliff mesh, extrude inward 0.02-0.05m
- **Pattern:** Use predefined rune glyph vertex templates, projected onto cliff surface
- **Weathering:** Partial erosion -- some carved lines are deeper than others, some are filled with moss

### 6.3 Hanging Roots and Dead Vines

- Spline-based cylinder meshes originating from cliff top or horizontal cracks
- 3-8 control points per vine, 4-6 radial segments
- Taper from 0.03m at root to 0.01m at tip
- Randomize length (0.5-4m), slight curl via noise-displaced control points
- Place at cliff top and at horizontal strata boundaries where roots penetrate cracks

### 6.4 Environmental Storytelling Props

| Feature | Placement Zone | Density |
|---------|---------------|---------|
| Bird nests | Ledges, overhangs | 1-2 per cliff face |
| Broken stairs/platforms | Carved into cliff | 0-1 per cliff, rare |
| Rope/chain anchors | Hard rock at accessible heights | 2-4 per cliff |
| Bone deposits | Cave entrances, base of cliff | Cluster of 3-8 |
| Torch sconce holes | Near cave entrances | 1-2 per entrance |

---

## 7. Material & Shader Strategy

### 7.1 Blender 4.x Node Changes

**IMPORTANT:** Musgrave Texture node has been merged into the Noise Texture node in Blender 4.x. The existing codebase uses `ShaderNodeTexMusgrave` which will need compatibility handling. In Blender 4.0+, use `ShaderNodeTexNoise` with the `type` parameter set to fBM/Multifractal/etc. to get Musgrave functionality.

### 7.2 Rock Material Node Strategy

For cliff faces, use a **layered material** driven by the Z-coordinate of the surface:

```
Object Info (position) → Separate XYZ → Z
  |
  Z → Color Ramp (strata bands: dark grey, tan, rust, grey)
  |
  Z → Noise Texture (fbm type, scale 2-4) → strata_roughness variation
  |
  Combined → Principled BSDF
    Base Color: strata band color + noise variation
    Roughness: 0.7-0.95 (rock is rough)
    Normal: Noise Texture (scale 15-30) → Bump Node (strength 0.3)
```

### 7.3 Material Zones for Cliff Faces

| Zone | Material | Roughness | Color |
|------|----------|-----------|-------|
| Hard rock (protruding) | `cliff_hard_rock` | 0.75-0.85 | Dark grey, blue-grey |
| Soft rock (recessed) | `cliff_soft_rock` | 0.85-0.95 | Tan, ochre, reddish |
| Wet rock (seepage) | `cliff_wet_rock` | 0.3-0.5 | Dark, slightly green |
| Moss patches | `cliff_moss` | 0.6-0.7 | Dark green, olive |
| Corruption veins | `corruption_emissive` | 0.2 | Purple/magenta, emissive 3.0 |
| Cave interior | `cave_dark_rock` | 0.5-0.7 | Very dark grey/brown |

### 7.4 PBR Value Ranges (Per AAA Standards)

All materials must follow the existing toolkit PBR rules:
- **Metallic:** 0.0 for all rock (dielectric, never metallic)
- **Roughness:** 0.7-0.95 for dry rock, 0.3-0.5 for wet rock
- **Base Color brightness:** 0.02-0.08 sRGB for dark fantasy stone (dark, not bright)
- **Normal map strength:** 0.2-0.4 for macro, 0.1-0.2 for micro detail

---

## 8. BMesh Code Patterns

### 8.1 Grid Mesh with Strata Displacement (Complete Pattern)

This is the core pattern for building a cliff face with layered rock:

```python
import bmesh
import math
import random
from mathutils import noise, Vector

def create_cliff_face_bmesh(
    width=20.0, height=15.0, 
    seg_x=24, seg_z=32,
    num_layers=8, seed=42
):
    """Create cliff face mesh with layered rock strata using bmesh.
    
    Pure bmesh approach -- no modifiers needed.
    """
    bm = bmesh.new()
    rng = random.Random(seed)
    
    # 1. Build strata profile
    layers = build_strata_profile(height, num_layers, seed)
    
    # 2. Generate erosion channels
    channels = generate_erosion_channels(width, num_channels=4, seed=seed+1)
    
    # 3. Create grid vertices with displacement
    for iz in range(seg_z + 1):
        z_frac = iz / seg_z
        z = z_frac * height
        
        for ix in range(seg_x + 1):
            x_frac = ix / seg_x
            x = (x_frac - 0.5) * width
            
            # Layer-based protrusion
            y = apply_strata_displacement(z, layers, x, seed)
            
            # Erosion channel carving
            y += channel_displacement(x, channels)
            
            # Multi-scale rock noise
            y += multi_scale_rock_noise(x, z, seed)
            
            # Undercut at soft layers below hard layers
            y += undercut_profile(z, layers)
            
            bm.verts.new((x, y, z))
    
    bm.verts.ensure_lookup_table()
    
    # 4. Create quad faces
    row_width = seg_x + 1
    for iz in range(seg_z):
        for ix in range(seg_x):
            v0 = bm.verts[iz * row_width + ix]
            v1 = bm.verts[iz * row_width + ix + 1]
            v2 = bm.verts[(iz + 1) * row_width + ix + 1]
            v3 = bm.verts[(iz + 1) * row_width + ix]
            bm.faces.new((v0, v1, v2, v3))
    
    bm.faces.ensure_lookup_table()
    
    # 5. Assign materials per face based on strata layer
    # (Requires material index layer on faces)
    mat_layer = bm.faces.layers.int.new("material_index")
    for face in bm.faces:
        center_z = sum(v.co.z for v in face.verts) / len(face.verts)
        for li, layer in enumerate(layers):
            if layer["z_start"] <= center_z < layer["z_end"]:
                face[mat_layer] = li % 4  # cycle through material slots
                break
    
    return bm
```

### 8.2 Cave Mouth Carving into Existing Cliff Mesh

```python
def carve_cave_entrance(bm, cave_center, cave_width, cave_height, cave_depth):
    """Carve a cave entrance into an existing cliff bmesh.
    
    Displaces vertices within the cave ellipse backward into the cliff.
    """
    cx, cz = cave_center
    hw = cave_width / 2.0
    hh = cave_height / 2.0
    
    for vert in bm.verts:
        dx = (vert.co.x - cx) / hw
        dz = (vert.co.z - cz) / hh
        dist_sq = dx * dx + dz * dz
        
        if dist_sq < 1.0:
            # Inside cave ellipse
            dist = math.sqrt(dist_sq)
            # Smooth falloff: deepest at center
            factor = (1.0 - dist) ** 1.5
            recession = cave_depth * factor
            vert.co.y -= recession
        elif dist_sq < 1.5 * 1.5:
            # Transition zone
            dist = math.sqrt(dist_sq)
            blend = (1.5 - dist) / 0.5
            vert.co.y -= cave_depth * 0.15 * blend
```

### 8.3 Noise Displacement via mathutils.noise

For Blender-side handlers (not pure logic), use `mathutils.noise` instead of custom hash noise:

```python
from mathutils import noise, Vector

def blender_rock_noise(co: Vector, seed: int, scale: float = 1.0) -> float:
    """Multi-fractal noise using Blender's built-in noise module."""
    # Offset by seed to get different patterns
    offset = Vector((seed * 13.7, seed * 7.3, seed * 19.1))
    p = (co + offset) * scale
    
    # Use multi_fractal for rock-like noise
    return noise.multi_fractal(p, 2.0, 2.0, 4, noise_basis='PERLIN_ORIGINAL')
```

### 8.4 Performance: Subdivide vs Pre-computed Grid

Two approaches for cliff mesh density:

**Pre-computed grid (recommended for pure-logic generators):**
- Calculate all vertices in one pass
- Control exact vertex count
- Deterministic, testable without Blender
- Used by existing `terrain_features.py` and `_terrain_depth.py`

**Subdivide + displace (for Blender handlers):**
```python
# Create base plane, subdivide, then displace
bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=16, use_grid_fill=True)
for vert in bm.verts:
    vert.co += vert.normal * noise_value
```

Use pre-computed grid for the pure-logic generators (consistency with codebase architecture). Use subdivide + displace only when modifying an existing mesh in a Blender handler.

---

## 9. Implementation Recommendations

### 9.1 Recommended Approach: Enhance Existing Generators

Do NOT create new files. Enhance the existing generators in `terrain_features.py` and `_terrain_depth.py`:

**`terrain_features.py` -- enhance `generate_cliff_face()`:**
1. Add `strata_layers` parameter (list or auto-generated from `num_layers`)
2. Add `erosion_channels` parameter (count, auto-generated)
3. Add `undercut_enabled` parameter
4. Add `multi_scale_noise` parameter (bool, default True)
5. Add `corruption_veins` parameter (density 0.0-1.0)
6. Keep pure-logic architecture (no bpy imports)

**`terrain_features.py` -- enhance `generate_canyon()`:**
1. Add shared `strata_profile` for both walls
2. Add width variation based on rock hardness
3. Add canyon floor features (river, gravel zones)
4. Add slot canyon variant

**`_terrain_depth.py` -- enhance `generate_cliff_face_mesh()`:**
1. Add strata displacement
2. Add erosion channels
3. Add cliff cap (rounded top edge)
4. Add talus fan at base

**`_terrain_depth.py` -- enhance `generate_cave_entrance_mesh()`:**
1. Add cave carving into adjacent cliff mesh (elliptical vertex displacement)
2. Add stalactite placement data
3. Add rubble scatter positions
4. Add interior darkening vertex colors

### 9.2 New Helper Functions to Add

Add to `terrain_features.py`:

```python
# Strata system
def build_strata_profile(height, num_layers, seed) -> list[dict]
def apply_strata_displacement(z, layers, x, seed) -> float

# Erosion
def generate_erosion_channels(width, num_channels, seed) -> list[dict]
def channel_displacement(x, channels) -> float
def undercut_profile(z, layers) -> float

# Multi-scale noise
def multi_scale_rock_noise(x, z, seed) -> float

# Canyon
def generate_slot_canyon(...) -> dict
def canyon_width_at_position(x, base_width, strata) -> float

# Dark fantasy
def generate_corruption_vein_positions(cliff_dims, strata, density, seed) -> list[dict]
def generate_stalactite_positions(cave_arch, count, seed) -> list[dict]
def generate_talus_fan(cliff_width, cliff_height, seed) -> dict
```

### 9.3 Material Slot Assignments

Each cliff face mesh should have these material slots:

| Slot Index | Material Name | Applied To |
|------------|---------------|------------|
| 0 | `cliff_hard_rock` | Hard strata layers |
| 1 | `cliff_soft_rock` | Soft strata layers |
| 2 | `cliff_wet_rock` | Seepage zones, lower sections |
| 3 | `cliff_moss` | North-facing surfaces, crevices |
| 4 | `cliff_overhang` | Underside of overhangs |
| 5 | `corruption_vein` | Emissive corruption fissures |

### 9.4 Performance Budget

| Feature | Target Poly Count | Notes |
|---------|-------------------|-------|
| Cliff face (20m) | 800-1200 quads | Main mesh |
| Cave entrance | 200-400 quads | Including tunnel first 3m |
| Talus fan | 100-200 quads | Wedge mesh |
| Stalactites (per) | 30-60 tris | 4-6 per cave entrance |
| Corruption veins | 50-100 quads | Thin strips |
| Scattered boulders | 20-40 tris each | 10-20 per cliff base |
| **Total per cliff** | **~2000-3000 quads** | Game-ready |

### 9.5 Testing Strategy

All new functions must be pure-logic (no bpy) in `terrain_features.py` and testable:

```python
def test_strata_profile_covers_full_height():
    layers = build_strata_profile(height=15.0, num_layers=8, seed=42)
    assert layers[0]["z_start"] == 0.0
    assert layers[-1]["z_end"] >= 15.0  # or close to it

def test_canyon_strata_match():
    """Both canyon walls must share the same strata profile."""
    result = generate_canyon_with_matched_strata(...)
    left_strata = result["left_wall_strata"]
    right_strata = result["right_wall_strata"]
    assert left_strata == right_strata

def test_cliff_has_multiple_material_zones():
    result = generate_cliff_face(width=20, height=15, num_layers=6)
    assert len(set(result["material_indices"])) >= 3
```

---

## 10. Sources

### Techniques & Tutorials
- [Procedural Stylized Rock Modeling (Greg Zaal)](https://blog.gregzaal.com/2013/09/20/procedural-stylized-rock-modeling/) -- Icosphere + dual displacement + decimation workflow. Knife tool for strata cuts. HIGH confidence.
- [BMesh Python Patterns (Jeremy Behreandt)](https://behreajj.medium.com/shaping-models-with-bmesh-in-blender-2-9-2f4fcc889bf0) -- Comprehensive bmesh code patterns: extrusion, noise displacement, UV mapping. HIGH confidence.
- [BMesh Operators API](https://docs.blender.org/api/current/bmesh.ops.html) -- Official Blender Python API for bmesh operations. HIGH confidence.
- [Procedural Rock/Mountain Shader Tutorial (80.lv)](https://80.lv/articles/tutorial-procedural-rock-mountain-shader-in-blender) -- Node-based rock material with strata bands. MEDIUM confidence.
- [Procedural Rock Material (ArtStation)](https://www.artstation.com/blogs/jsabbott/RLzVb/making-a-procedural-rock-material-blender-402) -- Blender 4.0.2 rock material nodes. HIGH confidence.

### Academic Papers
- [Procedural Generation of 3D Canyons (ResearchGate)](https://www.researchgate.net/publication/287184479_Procedural_Generation_of_3D_Canyons) -- Canyon generation algorithms, cross-section profiles. MEDIUM confidence (could not access full text).
- [Procedural Generation of 3D Cave Models with Stalactites and Stalagmites](https://www.semanticscholar.org/paper/Procedural-generation-of-3D-cave-models-with-and-Cui-Chow/8365da9afd1f2b767f9947a1dd4940d75c656bf4) -- Voxel-based stalactite generation, mesh polygonalization. MEDIUM confidence.
- [Rock Layers for Real-Time Erosion Simulation (GameDev.net)](https://www.gamedev.net/blogs/entry/2284060-rock-layers-for-real-time-erosion-simulation/) -- Hardness-based differential erosion, layer data structures. MEDIUM confidence (403 on fetch).

### Tools & Addons
- [Blender Cliff Generator (GitHub)](https://github.com/marcueberall/blender.cliffgenerator) -- Particle-system based procedural cliffs. Reference for visual quality targets. MEDIUM confidence.
- [Stalagmite Generator (GitHub)](https://github.com/Malinovent/Stalagmite-Generator) -- Real-parameter-based stalactite/stalagmite mesh generation. HIGH confidence.
- [Blender GeoModeller](https://github.com/bsomps/BlenderGeoModeller) -- Geological strata modeling in Blender. Niche but relevant for strata visualization. LOW confidence (not game-focused).

### Blender API Changes
- [Musgrave/Noise Node Merger (Blender Dev Forum)](https://devtalk.blender.org/t/merging-the-musgrave-texture-and-noise-texture-nodes/30646) -- Musgrave merged into Noise Texture node in Blender 4.x. Must use `ShaderNodeTexNoise` with type parameter. HIGH confidence.

### Existing Codebase (VeilBreakers Toolkit)
- `terrain_features.py` -- Existing canyon, cliff face, waterfall generators (pure logic)
- `_terrain_depth.py` -- Cliff face mesh, cave entrance mesh generators (pure logic)
- `environment.py` -- Cliff overlay detection and placement (Blender handler)
- `coastline.py` -- Cliff coastline with cave entrances (pure logic)
- `procedural_meshes.py` -- Rock, stalactite, boulder mesh generators (pure logic)
