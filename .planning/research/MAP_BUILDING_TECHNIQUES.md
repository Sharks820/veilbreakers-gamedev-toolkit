# Deep Dive: Map Building & Level Design Tool Techniques

**Researched:** 2026-03-22
**Domain:** Terrain generation, level design tools, procedural placement, streaming, modular kits
**Confidence:** HIGH (cross-referenced official engine docs, GDC talks, open-source implementations, academic papers)
**Target Stack:** Blender Python (procedural generation) + Unity URP C# (runtime rendering)

---

## Table of Contents

1. [Unreal Engine Level Editor Internals](#1-unreal-engine-level-editor-internals)
2. [Unity ProBuilder Internals](#2-unity-probuilder-internals)
3. [Houdini Terrain Tools](#3-houdini-terrain-tools)
4. [Gaea / World Machine](#4-gaea--world-machine)
5. [Modular Level Design (Bethesda / FromSoftware)](#5-modular-level-design-bethesda--fromsoftware)
6. [Procedural Placement (Guerrilla / Ubisoft)](#6-procedural-placement-guerrilla--ubisoft)
7. [Terrain Streaming and LOD](#7-terrain-streaming-and-lod)
8. [Techniques We Can Implement in Blender Python](#8-techniques-we-can-implement-in-blender-python)
9. [Techniques We Can Implement in Unity C#](#9-techniques-we-can-implement-in-unity-c)
10. [Implementation Priority](#10-implementation-priority)
11. [Existing VB Toolkit Coverage & Gaps](#11-existing-vb-toolkit-coverage--gaps)
12. [Sources](#12-sources)

---

## 1. Unreal Engine Level Editor Internals

### 1.1 BSP Brush System (CSG)

**Confidence:** HIGH

The BSP system uses two distinct concepts that are often confused:

- **CSG (Constructive Solid Geometry):** The creation method. Brushes are volumes that either ADD solid space or SUBTRACT solid space from the level. The order of operations matters -- a subtractive brush placed before an additive brush produces different results than the reverse.

- **BSP (Binary Space Partitioning):** The storage and rendering format. After brush placement, the engine "Builds Geometry" -- a complex process that partitions the brush volumes into renderable convex polygons via a binary tree.

**How the Build Process Works:**
1. All additive and subtractive brushes are collected in placement order
2. The engine computes the CSG union/difference of all brushes
3. The resulting solid is split into convex polygons via BSP tree construction
4. Each polygon is assigned collision, material, and lighting data
5. Semi-solid brushes skip the BSP cutting step (performance optimization)

**Solidity Types:**
| Type | Collision | BSP Cuts | Use Case |
|------|-----------|----------|----------|
| Solid (default) | Yes | Yes | Walls, floors, structural geometry |
| Semi-solid | Yes | No | Pillars, beams, decorative elements |
| Non-solid | No | No | Trigger volumes, visual-only |

**Key Insight for VB Toolkit:** BSP is essentially boolean operations on convex volumes stored in a spatial tree. Our `blender_mesh` boolean action already does CSG via Blender's boolean modifier. What we lack is the ordered operation queue concept -- applying multiple booleans in sequence to sculpt a space.

**What to Steal:**
- Ordered boolean operation chains (add/subtract queue)
- The concept of "building" geometry from a sequence of volume operations
- Semi-solid optimization (skip complex boolean for non-structural elements)

### 1.2 Terrain Layer Blending Algorithm

**Confidence:** HIGH

Unreal's terrain material system uses `LandscapeLayerBlend` nodes with two blending modes:

**Alpha Blend (LB_AlphaBlend):**
Simple linear interpolation between layers based on paint weight:
```
finalColor = lerp(layerA, layerB, weight)
```

**Height Blend (LB_HeightBlend):**
Uses per-pixel height information from each layer's heightmap to create natural transitions. The algorithm:

```hlsl
// For each layer, compute effective height
float effectiveHeight_A = heightmapA * weightA;
float effectiveHeight_B = heightmapB * weightB;

// The layer with greater effective height "wins" at each pixel
// Smoothstep creates soft transitions
float blendDepth = 0.2; // Artist-controllable
float diff = effectiveHeight_A - effectiveHeight_B;
float blend = smoothstep(-blendDepth, blendDepth, diff);

float4 finalColor = lerp(colorB, colorA, blend);
```

**Why Height Blend Looks Better:**
- Dirt naturally fills cracks between rock surfaces
- Snow sits on top of peaks, not uniformly across the surface
- Grass stops at cliff edges rather than blending linearly into rock
- The heightmap from each texture's detail (bumps, cracks) drives the transition

**Multi-Layer Height Blend (4+ layers):**
```hlsl
// Sequential application with alpha maps stored in splatmap RGBA
float4 splatmap = tex2D(splatmapSampler, uv);
float4 color = baseColor;  // Default layer (LB_AlphaBlend)

// Each subsequent layer uses LB_HeightBlend
color = heightBlend(color, layer1Color, layer1Height, splatmap.r, blendDepth);
color = heightBlend(color, layer2Color, layer2Height, splatmap.g, blendDepth);
color = heightBlend(color, layer3Color, layer3Height, splatmap.b, blendDepth);
color = heightBlend(color, layer4Color, layer4Height, splatmap.a, blendDepth);
```

**Per-Component Optimization:** Each terrain component checks which layers are actually painted on it. Unused layers are compiled out of that component's material instance, saving GPU cycles.

### 1.3 Foliage Painting System

**Confidence:** HIGH

**Paint Distribution Algorithm:**
When painting foliage, the engine uses a spherical brush volume and fires raycasts (line traces) from the camera through the sphere into the terrain. Any surface within the sphere that intersects a ray is a candidate for instance placement.

**Instance Management:**
- Uses Hierarchical Instanced Static Meshes (HISM) behind the scenes
- HISM groups instances into a spatial hierarchy (clusters of ~128 instances)
- Entire clusters can be culled at once -- critical for forests with millions of instances
- Each foliage type gets its own HISM component

**Key Parameters Per Foliage Type:**
| Parameter | Effect |
|-----------|--------|
| Density | Instances per 1000x1000 unit area |
| Radius | Minimum distance between instances (Poisson-like) |
| Ground Slope Angle | Min/max slope where instances can spawn |
| Height Range | Altitude range for placement |
| Align to Normal | Instance rotation follows surface normal |
| Random Yaw | Random rotation around up axis |
| Scale Range | Min/max random scale per instance |
| Cull Distance Start/End | Per-instance LOD distance |

### 1.4 Procedural Foliage Spawner

**Confidence:** HIGH

Unlike the paint tool, the Procedural Foliage Spawner simulates an ecosystem:

1. **Seeding Phase:** Initial seed points are placed randomly across the spawner volume
2. **Growth Simulation:** Seeds "grow" over simulated time steps. Each step:
   - Seeds expand their radius based on growth rate
   - Overlapping instances compete based on priority
   - Shade-intolerant species die under the canopy of taller species
   - Overlap-intolerant species kill neighbors within their radius
3. **Final Placement:** Surviving instances are placed as HISM instances

**Key Parameters:**
- `Num Steps`: Number of simulation iterations (more = denser, more varied)
- `Initial Seed Density`: Starting seed count per area
- `Shade Radius`: How far a plant's shade extends
- `Max Initial Age`: Randomized starting maturity
- `Overlap Priority`: Which species wins in competition

### 1.5 Landscape Spline Terrain Deformation

**Confidence:** HIGH

**How Spline Terrain Carving Works:**

1. A spline curve is defined with control points on the landscape
2. Each control point has `Width` and `Falloff` properties
3. When "Apply Splines to Landscape" is triggered:
   - The heightmap under the spline is sampled
   - Heights are adjusted to match the spline's Z position
   - A **cosine-blended falloff** smoothly transitions from the road surface to original terrain:
     ```
     // Distance from spline center, normalized to [0, 1] across falloff width
     float t = saturate((distFromCenter - halfWidth) / falloffWidth);
     float blend = 0.5 * (1.0 + cos(t * PI));  // Cosine falloff
     float newHeight = lerp(splineHeight, originalHeight, blend);
     ```
4. Layer weightmaps are also modified -- road material is painted under the spline, with the same cosine falloff

**What to Steal:**
- Cosine-blended falloff for road carving (our current road gen uses simpler linear falloff)
- Combined heightmap + material painting in a single operation
- Width/falloff per control point for varying road widths

### 1.6 Level Streaming Volumes

**Confidence:** HIGH

**UE4 Classic Approach:**
- World is divided into sub-levels, each in its own .umap file
- Level Streaming Volumes are placed in the persistent level
- When the player's viewpoint enters a volume, the associated sub-level loads
- When the viewpoint exits, the sub-level unloads
- `Load Distance` and `Unload Distance` prevent pop-in at volume boundaries

**UE5 World Partition:**
- Automatic grid-based division of the world
- Cells stream in/out based on camera distance
- No manual volume placement required
- Each cell is independently loaded/unloaded
- Grid size is configurable (e.g., 128m, 256m cells)

**Key Implementation Detail:**
Only one AsyncOperation progresses at a time in the scene loading queue. This means loading multiple chunks requires careful priority ordering -- nearest chunks load first.

---

## 2. Unity ProBuilder Internals

### 2.1 Mesh Editing Operations

**Confidence:** HIGH

ProBuilder operates in three selection modes, each with specific operations:

**Vertex Mode:**
- Move, merge, split, weld vertices
- Collapse selection

**Edge Mode:**
- Extrude edges (creates new face along open edge)
- Bridge edges (connects two selected edge loops with new faces)
- Subdivide, insert edge loop

**Face Mode:**
- Extrude face (Shift+Drag shortcut): Pushes face out, creates side walls
- Inset face: Pulls edges inward within the face boundary
- Detach face: Separates face into new object
- Subdivide face: Splits into grid of sub-faces

**How Extrude Works Internally:**
1. Clone the selected face
2. Create quad side-faces connecting original edges to cloned edges
3. Move the cloned face along its normal by the extrusion amount
4. Recalculate normals and UVs for new geometry

### 2.2 Boolean (CSG) Operations

**Confidence:** MEDIUM (marked experimental in ProBuilder)

ProBuilder's CSG library implements three standard boolean operations:

| Operation | Result |
|-----------|--------|
| Union | Combined volume of both meshes |
| Intersection | Only the overlapping volume |
| Subtraction | First mesh minus the overlapping volume |

**Architecture:** The CSG library has been moved from MeshOperations into an External directory, suggesting it uses a third-party implementation. The base class provides GameObject-level methods that handle mesh conversion, boolean computation, and result mesh creation.

**Key Limitation:** Booleans are still "Experimental" even in ProBuilder 6.0. Material information can be lost during boolean operations (a known issue with an open pull request to fix it).

### 2.3 UV Auto-Projection

**Confidence:** HIGH

ProBuilder uses two primary UV mapping methods:

- **Auto UV:** Projects UVs based on the face normal direction (planar projection). Each face maps independently. Fast but can create seams.
- **Manual UV:** Full UV editor with pinning, stitching, and island manipulation.

For auto-projection, the algorithm determines the dominant axis of each face's normal and projects UVs along that axis:
```
if (abs(normal.y) > abs(normal.x) && abs(normal.y) > abs(normal.z))
    project onto XZ plane  // Horizontal face
else if (abs(normal.x) > abs(normal.z))
    project onto YZ plane  // Side face
else
    project onto XY plane  // Front/back face
```

---

## 3. Houdini Terrain Tools

### 3.1 HeightField Node System

**Confidence:** HIGH

Houdini's terrain system uses 2D volumetric layers called "height fields." The key insight is that terrain is not a mesh but a stack of 2D grids:

**Layer Architecture:**
| Layer | Purpose |
|-------|---------|
| height | Primary elevation data |
| mask | Operation masking (0-1 per cell) |
| sediment | Deposited material from erosion |
| debris | Loose material from thermal erosion |
| flow | Water flow intensity |
| flowdir | Water flow direction |
| bedrock | Hard underlying material |

**Operation Chaining:**
Each node reads one or more layers, processes them, and outputs modified layers. The node graph is a pipeline:

```
Noise -> HeightField -> Erode (hydro, large scale)
                            -> Erode (thermal)
                                -> Erode (hydro, small scale)
                                    -> Mask by Feature (slope > 40)
                                        -> Scatter (on masked area)
```

**Multi-Scale Erosion:**
The critical technique is chaining multiple erosion nodes at different `Erosion Feature Size` values. Larger scales reshape major landforms; smaller scales carve fine gullies. The smallest possible feature size is 3x the input terrain's voxel size.

### 3.2 Erosion Simulation Algorithms

**Confidence:** HIGH

#### Hydraulic Erosion (Droplet-Based)

The algorithm implemented in our toolkit and in Sebastian Lague's widely-referenced implementation:

```python
# PSEUDOCODE: Droplet-based hydraulic erosion
for each iteration:
    # 1. Spawn droplet at random position
    pos = random_position()
    direction = (0, 0)
    speed = 1.0
    water = 1.0
    sediment = 0.0

    for step in range(max_lifetime):
        # 2. Compute gradient via bilinear interpolation
        gradient = compute_gradient_bilinear(heightmap, pos)

        # 3. Update direction with inertia
        direction = direction * inertia - gradient * (1 - inertia)
        direction = normalize(direction)

        # 4. Move droplet
        new_pos = pos + direction

        # 5. Compute height difference
        h_old = sample_height_bilinear(heightmap, pos)
        h_new = sample_height_bilinear(heightmap, new_pos)
        h_diff = h_new - h_old

        # 6. Compute sediment capacity
        capacity = max(-h_diff, min_slope) * speed * water * capacity_factor

        # 7. Erode or deposit
        if sediment > capacity or h_diff > 0:  # Deposit
            if h_diff > 0:
                amount = min(sediment, h_diff)
            else:
                amount = (sediment - capacity) * deposition_rate
            deposit_bilinear(heightmap, pos, amount)
            sediment -= amount
        else:  # Erode
            amount = min((capacity - sediment) * erosion_rate, -h_diff)
            erode_brush(heightmap, pos, amount, radius)
            sediment += amount

        # 8. Update physics
        speed = sqrt(max(speed^2 + h_diff, 0.01))
        water *= (1 - evaporation)
        pos = new_pos
```

**Key Parameters:**
| Parameter | Typical Value | Effect |
|-----------|--------------|--------|
| iterations | 1000-70000 | More = deeper erosion |
| inertia | 0.05 | 0=follow gradient, 1=keep direction |
| capacity | 4.0 | Sediment carrying capacity |
| deposition | 0.3 | Deposit rate when over capacity |
| erosion_rate | 0.3 | Erode rate when under capacity |
| evaporation | 0.01 | Water loss per step |
| min_slope | 0.01 | Prevents divide-by-zero in flat areas |
| radius | 3 | Erosion brush radius |
| max_lifetime | 30 | Max steps before forced evaporation |

#### Thermal Erosion (Talus-Based)

Simpler algorithm based on material stability angles:

```python
# PSEUDOCODE: Thermal erosion
talus_threshold = tan(talus_angle_degrees * PI / 180)

for each iteration:
    delta = zeros_like(heightmap)

    for each cell (r, c):
        h = heightmap[r, c]
        diffs = []

        for each neighbor (nr, nc, distance):
            slope = (h - heightmap[nr, nc]) / distance
            if slope > talus_threshold:
                excess = slope - talus_threshold
                diffs.append((nr, nc, excess))

        if diffs:
            total_excess = sum(d for _, _, d in diffs)
            transfer = max_excess * 0.5  # Transfer half

            for nr, nc, d in diffs:
                fraction = d / total_excess
                amount = transfer * fraction
                delta[r, c] -= amount
                delta[nr, nc] += amount

    heightmap += delta
    clamp(heightmap, 0, 1)
```

**Key Parameter:** `talus_angle` (typically 30-45 degrees). Lower values = more aggressive flattening of steep slopes.

#### Houdini's Enhancements Over Basic Algorithms

Houdini's HeightField Erode 3.0 (rewritten in Houdini 21) adds:

- **Erosion Feature Size:** Scales the simulation to control feature granularity
- **Bank Angle:** Controls how steep river channels become
- **Rainfall Coverage:** Amount of simulated rainfall per frame
- **Slope Influence:** How much slope affects stream paths
- **Separate output layers:** height, sediment, debris, flow, flowdir -- each usable downstream
- **Multi-scale chaining:** Multiple erosion nodes at different scales for realistic results

### 3.3 Scatter / Copy-to-Points

**Confidence:** HIGH

Houdini's scatter workflow is the gold standard for procedural placement:

1. **Scatter Node:** Generates random points on a surface
   - Uses Poisson disk sampling by default for blue-noise distribution
   - Density can be driven by an attribute (e.g., a mask layer)
   - Points inherit surface attributes (normal, UV, custom layers)

2. **Copy to Points:** Instances geometry onto scattered points
   - Point attributes control transform: `pscale` (scale), `orient` (quaternion rotation), `N` (normal for alignment)
   - Supports random variation per-instance via attribute randomization
   - Extremely efficient -- geometry is instanced, not duplicated

3. **Labs Biome Tools:** Rule-based ecosystem simulation
   - Define biome rules (what grows where based on slope, altitude, moisture)
   - Species compete for placement based on priority
   - Ecosystem behavior handles natural clustering and spacing

**What to Steal:**
- Attribute-driven density (already partially in our biome_filter_points)
- Point attribute inheritance for per-instance variation
- The Scatter -> Filter -> Copy-to-Points pipeline as a composable chain

### 3.4 L-System Vegetation

**Confidence:** HIGH

L-systems (Lindenmayer systems) generate plant structures via string rewriting:

**Core Algorithm:**
```python
# PSEUDOCODE: L-System tree generation

# Define grammar
axiom = "F"
rules = {
    "F": "FF+[+F-F-F]-[-F+F+F]"
}
angle = 25.0  # degrees
iterations = 4

# 1. String rewriting (expand axiom through rules)
current = axiom
for i in range(iterations):
    next_string = ""
    for char in current:
        if char in rules:
            next_string += rules[char]
        else:
            next_string += char
    current = next_string

# 2. Turtle graphics interpretation
position = (0, 0, 0)
direction = (0, 0, 1)  # Up
stack = []

for char in current:
    if char == 'F':
        # Draw forward: create a branch segment
        new_pos = position + direction * segment_length
        create_cylinder(position, new_pos, thickness)
        position = new_pos
        thickness *= 0.95  # Taper
    elif char == '+':
        direction = rotate(direction, angle, roll_axis)
    elif char == '-':
        direction = rotate(direction, -angle, roll_axis)
    elif char == '[':
        stack.push((position, direction, thickness))  # Save state
    elif char == ']':
        position, direction, thickness = stack.pop()  # Restore state
```

**Common L-System Grammars for Game Trees:**
| Type | Axiom | Rule | Angle | Iterations |
|------|-------|------|-------|------------|
| Binary tree | F | F[+F]F[-F]F | 25.7 | 5 |
| Bush | F | FF+[+F-F-F]-[-F+F+F] | 22.5 | 4 |
| Stochastic tree | F | 0.33: F[+F]F[-F]+F, 0.33: F[+F]F, 0.34: F[-F]F | 20 | 5 |
| Conifer | F | FF-[-F+F+F]+[+F-F-F] | 22.5 | 4 |

**Stochastic Extension:** Each rule has a probability, creating natural variation:
```python
rules = {
    "F": [
        (0.33, "F[+F]F[-F]+F"),
        (0.33, "F[+F]F"),
        (0.34, "F[-F]F"),
    ]
}
```

### 3.5 Procedural Road System

**Confidence:** HIGH

Houdini's approach to terrain road carving:

1. **Define road path** as a spline curve on the heightfield
2. **HeightField Mask by Geometry:** Project the road spline onto the heightfield to create a road mask
3. **HeightField Project:** Carve the road into terrain using `combine method = Minimum`
   - First pass: road surface itself (flat)
   - Second pass: road shoulders with falloff
4. **Material assignment:** Paint road texture using the road mask on a material weight layer

**Key Technique -- Road Grading:**
Roads need consistent grade (slope along their length). The algorithm:
1. Sample terrain height at each road control point
2. Smooth the height profile to limit maximum grade (typically 8-12%)
3. Interpolate smoothed heights along the road path
4. Flatten terrain to match interpolated heights with cosine falloff

---

## 4. Gaea / World Machine

### 4.1 Terrain Generation from Noise

**Confidence:** HIGH

Both tools use layered noise functions as the starting point, then refine with erosion:

**Noise Stack Architecture:**
```
Layer 1: Perlin/Simplex noise (large features -- mountains, valleys)
    + Layer 2: Ridged noise (ridge lines, mountain spines)
        + Layer 3: Billow noise (rounded hills in lowlands)
            + Layer 4: Worley/Voronoi noise (mesa/plateau edges)
                -> Erosion pipeline
```

**Gaea's NoiseGenerator:**
Uses FastNoiseLite internally, providing access to:
- Perlin, OpenSimplex, Cellular (Voronoi), Value noise
- Domain warping (distort the input coordinates of noise for organic shapes)
- Fractal types: FBM, Ridged Multi, Ping-Pong

**World Machine's 2025 "Hurricane Ridge" Erosion:**
- Entirely new erosion model with better performance
- Flow-based erosion simulating water dynamics that carve gullies
- Thermal erosion decomposing cliff faces and accumulating talus slopes

### 4.2 Erosion Algorithms (Production-Quality)

**Confidence:** HIGH

**Gaea's Erosion Node Separation:**
Gaea separates erosion into three independently controllable components:
| Component | What It Does |
|-----------|-------------|
| Sediments | Deposited material in valleys and flat areas |
| Channels | Water-carved gully paths |
| Debris | Loose talus material at cliff bases |

This separation means you can have deep channels without excessive debris, or heavy sediment without visible channels. Our toolkit currently combines all three effects in a single pass.

**Resolution-Independent Erosion:**
Gaea's key innovation: erosion features are preserved across different heightmap resolutions. Most basic implementations (including ours) produce different-looking results at different resolutions because the cell spacing changes relative to the erosion parameters.

**Fix:** Scale all erosion parameters (capacity, deposition rate, erosion rate) relative to the cell size, not absolute values.

### 4.3 Flow Map Computation

**Confidence:** HIGH

Flow maps encode the direction and intensity of water flow across terrain:

**D8 Algorithm (Standard):**
```python
# For each cell, find the steepest downhill neighbor
# Direction is one of 8 compass directions
for each cell (r, c):
    max_slope = 0
    flow_dir = -1

    for each of 8 neighbors (nr, nc):
        distance = sqrt((nr-r)^2 + (nc-c)^2)
        slope = (height[r,c] - height[nr,nc]) / distance

        if slope > max_slope:
            max_slope = slope
            flow_dir = neighbor_index

    flow_direction[r,c] = flow_dir
    flow_intensity[r,c] = max_slope
```

**Limitation:** D8 only allows 8 directions -- rivers always look grid-aligned.

**Multiple Flow Direction (MFD) Algorithm:**
```python
# Distribute flow to ALL downslope neighbors proportionally
for each cell (r, c):
    total_slope = 0
    slopes = {}

    for each neighbor (nr, nc):
        slope = (height[r,c] - height[nr,nc]) / distance
        if slope > 0:
            slopes[(nr,nc)] = slope
            total_slope += slope

    for (nr,nc), slope in slopes.items():
        flow_fraction[r,c -> nr,nc] = slope / total_slope
```

**Sobel-Based Gradient Flow:**
For shader-compatible flow maps, apply a Sobel operator to the heightmap:
```python
# Horizontal gradient
gx = heightmap[y, x+1] - heightmap[y, x-1]
# Vertical gradient
gy = heightmap[y+1, x] - heightmap[y-1, x]
# Flow direction (perpendicular to gradient = contour following)
flow_u = -gy  # or gx for downhill flow
flow_v = gx   # or gy for downhill flow
# Normalize
length = sqrt(flow_u^2 + flow_v^2)
flow_u /= max(length, 0.001)
flow_v /= max(length, 0.001)
```

**Flow Accumulation:**
Computed by summing upstream contributions:
```python
# Topological sort cells from highest to lowest
sorted_cells = sort_by_height_descending(heightmap)

accumulation = ones_like(heightmap)  # Each cell starts with 1 unit

for (r, c) in sorted_cells:
    for each downslope neighbor (nr, nc):
        fraction = flow_fraction[r,c -> nr,nc]
        accumulation[nr, nc] += accumulation[r, c] * fraction
```

Cells with high accumulation values are river channels.

### 4.4 Macro Terrain Features

**Confidence:** HIGH

Specific noise/processing combinations for geological features:

**Mesa / Plateau:**
```python
# Generate base noise
height = fbm_noise(x, y, octaves=6)

# Clamp top to create flat mesa top
mesa_threshold = 0.6
height = where(height > mesa_threshold, mesa_threshold, height)

# Optional: add step function for layered mesas
height = floor(height * step_count) / step_count
```

**Canyon:**
```python
# Start with ridged noise to create valley paths
ridge = 1.0 - abs(noise(x, y))  # Ridged noise
ridge = ridge ** power  # Sharpen ridges

# Carve deep channels
height = base_height - canyon_depth * (1.0 - ridge)

# Add wall detail
height += wall_noise * mask_by_slope(height)
```

**Valley:**
```python
# Use domain warping to create organic valley shapes
warped_x = x + noise(x * warp_freq, y * warp_freq) * warp_amount
warped_y = y + noise(x * warp_freq + 100, y * warp_freq + 100) * warp_amount

# Generate main ridge with warped coordinates
valley = abs(noise(warped_x, warped_y))  # Valley floor at 0, ridges at 1
```

---

## 5. Modular Level Design (Bethesda / FromSoftware)

### 5.1 Grid System and Snap Points

**Confidence:** HIGH

**Bethesda's Kit System (from GDC 2013, Joel Burgess):**

The footprint is the foundation of every kit. All pieces in a kit must share footprint dimensions that are multiples of each other:

| Dimension Type | Standard Values (Bethesda units) | Metric Equivalent |
|---------------|--------------------------------|-------------------|
| Room width | 512 | ~5.12m |
| Room height | 512 | ~5.12m |
| Room depth | 512 | ~5.12m |
| Hallway width | 256 | ~2.56m |
| Hallway height | 512 | ~5.12m |
| Small room | 256 x 256 | ~2.56m x 2.56m |

**Critical Rule:** Footprints must be multiples of each other. A 512x512 room tiles with a 256x256 hallway. A 384x384 room will create gaps when the kit loops back on itself.

**Snap Grid:** Level designers build on a grid snap setting of **half the footprint size.** For 512-unit rooms, snap to 256 units. This allows precise alignment while permitting some offset for variety.

**For VeilBreakers (metric, 1 unit = 1 meter):**
| Piece Type | Recommended Size | Grid Snap |
|------------|-----------------|-----------|
| Large room | 8m x 8m x 4m | 4m |
| Standard room | 4m x 4m x 4m | 2m |
| Hallway | 2m x 4m x 4m | 2m |
| Doorway | 2m x 3m | 1m |
| Corridor connector | 2m x 2m x 4m | 1m |

### 5.2 Connection Points

**Confidence:** HIGH

Modular pieces connect via defined connection points (also called "portals" or "doors"):

**Connection Point Properties:**
```python
class ConnectionPoint:
    position: Vector3      # Location on the piece boundary
    normal: Vector3        # Direction the connection faces (outward)
    size: (width, height)  # Opening dimensions
    type: str              # "door", "hallway", "open", "wall"
    tags: set              # Compatibility tags
```

**Matching Rule:** Two pieces connect when:
1. Connection point positions align (within snap tolerance)
2. Normals point in opposite directions (facing each other)
3. Sizes match (or are compatible)
4. Types are compatible (door connects to door, not to wall)

**Corner and T-Junction Handling:**
| Junction Type | Piece Set Required |
|--------------|-------------------|
| Straight | 2 connection points on opposite walls |
| Corner (90 deg) | 2 connection points on adjacent walls |
| T-junction | 3 connection points (one wall has none) |
| 4-way | 4 connection points (all walls) |
| Dead end | 1 connection point |

### 5.3 Piece Naming Convention

**Confidence:** HIGH

Bethesda uses a systematic naming scheme:
```
[Kit]_[SubKit]_[PieceType]_[Variant]_[Size]

Examples:
NordCrypt_Hall_Str_01_Lrg    -- Nord crypt, hallway, straight, variant 1, large
NordCrypt_Room_Corn_02_Med   -- Nord crypt, room, corner, variant 2, medium
NordCrypt_Stair_Dn_01        -- Nord crypt, stairs down, variant 1
```

**Standard Piece Types:**
| Code | Piece Type | Description |
|------|-----------|-------------|
| Str | Straight | Straight hallway or room |
| Corn | Corner | 90-degree turn |
| Tee | T-junction | Three-way intersection |
| Cross | Crossroads | Four-way intersection |
| Dead | Dead end | Terminal piece |
| Stair_Up/Dn | Stairs | Vertical connection |
| Balc | Balcony | Overlook area |
| Trans | Transition | Size or style change |

### 5.4 Texture Approaches: Trim Sheets and Atlases

**Confidence:** HIGH

**Trim Sheet:**
A single texture containing horizontal strips of different materials (stone trim, wood beam, metal band, etc.). Modular pieces UV-map their geometry to these strips.

**Advantages:**
- All pieces in a kit share ONE material/draw call
- UV mapping is trivial -- just align to the correct strip
- Easy to create variants (dirty, damaged, mossy) by making alternate trim sheets

**Trim Sheet Layout (typical):**
```
+----------------------------------+
| Stone wall (rough)      512px    |
+----------------------------------+
| Stone wall (smooth)     256px    |
+----------------------------------+
| Wood beam              128px     |
+----------------------------------+
| Metal trim              64px     |
+----------------------------------+
| Floor tile             256px     |
+----------------------------------+
| Ceiling                128px     |
+----------------------------------+
| Door frame             128px     |
+----------------------------------+
```

**Atlas vs Trim Sheet:**
| Feature | Trim Sheet | Atlas |
|---------|-----------|-------|
| Layout | Horizontal strips | Grid of unique elements |
| UV tiling | Can tile horizontally | No tiling |
| Best for | Repeating architectural elements | Unique props/details |
| Draw calls | 1 per kit | 1 per atlas |

---

## 6. Procedural Placement (Guerrilla / Ubisoft)

### 6.1 Poisson Disk Sampling

**Confidence:** HIGH (we already implement Bridson's algorithm)

Our `_scatter_engine.py` implements Bridson's algorithm correctly. Key properties:
- **Blue noise distribution:** No two points closer than `min_distance`
- **O(n) complexity:** Each point is processed once
- **Deterministic with seed:** Same seed = same distribution

**Enhancement opportunities:**

**Variable-Radius Poisson Disk:**
Instead of a fixed `min_distance`, vary it based on a density map:
```python
def variable_poisson_disk(width, depth, density_map, base_distance, seed):
    """Poisson disk where min_distance varies by location.

    density_map: 2D array [0,1] where 1 = dense, 0 = sparse
    Effective distance = base_distance / max(density_map[y,x], 0.1)
    """
    # Same Bridson's algorithm, but _is_valid() checks:
    # local_min_dist = base_distance / max(density_at(x, y), 0.1)
    # dist_sq < local_min_dist^2
```

**Multi-Species Poisson Disk:**
Each species has its own minimum distance, but also a cross-species minimum distance:
```python
species_distances = {
    "tree": {"tree": 5.0, "bush": 2.0, "rock": 3.0},
    "bush": {"tree": 2.0, "bush": 1.5, "rock": 1.0},
    "rock": {"tree": 3.0, "rock": 4.0, "bush": 1.0},
}
```

### 6.2 Rule-Based Placement

**Confidence:** HIGH (partially implemented in our biome_filter_points)

**Full Rule System Structure:**
```python
class PlacementRule:
    # Terrain constraints
    min_altitude: float       # Normalized [0, 1]
    max_altitude: float
    min_slope: float          # Degrees
    max_slope: float
    preferred_slope: float    # Ideal slope (weight increases near this)

    # Spatial constraints
    min_distance_to_water: float
    max_distance_to_water: float
    min_distance_to_road: float  # Exclusion from roads
    min_distance_to_building: float
    max_distance_to_building: float  # For "near building" placement

    # Cluster behavior
    cluster_probability: float   # Chance to spawn cluster vs single
    cluster_count: (int, int)    # Min/max items in cluster
    cluster_radius: float        # Cluster spread

    # Variation
    scale_range: (float, float)
    rotation_range: (float, float)
    align_to_normal: bool
    random_yaw: bool
    sink_depth: float            # How deep to embed in terrain
```

### 6.3 Density Maps

**Confidence:** HIGH

Density maps are grayscale images that modulate placement probability:

**Types of Density Maps:**
| Map Type | Source | Effect |
|----------|--------|--------|
| Biome mask | Generated from altitude/slope | Where each biome exists |
| Moisture map | Flow accumulation + distance from water | Lush vs arid areas |
| Canopy density | Accumulated tree cover | Controls undergrowth |
| Hand-painted | Artist override | Specific placement control |
| Exclusion mask | Roads, buildings, water bodies | Where NOT to place |

**Combining Density Maps:**
```python
final_density = (
    biome_mask *
    moisture_map *
    (1.0 - exclusion_mask) *
    artist_override
)
# Final density modulates Poisson disk min_distance
effective_distance = base_distance / max(final_density, 0.1)
```

### 6.4 Exclusion Zones

**Confidence:** HIGH

**Implementation:**
```python
def compute_exclusion_mask(terrain_size, objects):
    """Generate exclusion mask from roads, buildings, and water."""
    mask = np.zeros((resolution, resolution))

    for road in roads:
        for point in road.sampled_points():
            # Paint road exclusion with falloff
            r = road.width + road.exclusion_margin
            paint_circle(mask, point, r, value=1.0, falloff="cosine")

    for building in buildings:
        # Rectangular exclusion from building footprint
        paint_rect(mask, building.bounds, value=1.0, margin=building.exclusion_margin)

    for water_body in water:
        # Water exclusion (but trees can be near water)
        paint_polygon(mask, water.shoreline, value=1.0)

    return mask
```

### 6.5 Physics-Based Settling

**Confidence:** MEDIUM

Some studios apply a settling pass after scatter placement:

```python
def settle_instances(instances, terrain_heightmap):
    """Drop instances onto terrain surface and apply slight randomization."""
    for inst in instances:
        # 1. Raycast down to find terrain surface
        terrain_height = sample_height(terrain_heightmap, inst.x, inst.y)

        # 2. Sink into terrain slightly
        inst.z = terrain_height - inst.sink_depth

        # 3. Align to surface normal
        if inst.align_to_normal:
            normal = compute_normal(terrain_heightmap, inst.x, inst.y)
            inst.rotation = align_to_vector(inst.up, normal)

        # 4. Add random tilt for organic feel
        inst.rotation *= random_tilt(max_degrees=5)
```

---

## 7. Terrain Streaming and LOD

### 7.1 Terrain Chunk Division

**Confidence:** HIGH

**Standard Chunk Sizes:**
| Game Type | Chunk Size | Heightmap Res per Chunk |
|-----------|-----------|------------------------|
| Small world (Dark Souls) | 256m x 256m | 257x257 |
| Medium world (Skyrim) | 512m x 512m | 513x513 |
| Large world (Elden Ring) | 1024m x 1024m | 1025x1025 |

**Chunk Data Structure:**
```python
class TerrainChunk:
    grid_pos: (int, int)          # Grid coordinates
    world_pos: (float, float)      # World-space center
    heightmap: np.ndarray          # Height data
    splatmap: np.ndarray           # Material weights (RGBA = 4 layers)
    detail_maps: list[np.ndarray]  # Grass/detail placement
    tree_instances: list[dict]     # Tree positions, scales, rotations
    lod_level: int                 # Current detail level
```

### 7.2 Terrain LOD Strategy

**Confidence:** HIGH

**Mesh LOD (CDLOD -- Chunked Distance-based LOD):**
```
LOD 0: Full resolution mesh (every vertex)    -- 0-100m
LOD 1: Half resolution (skip every other)     -- 100-400m
LOD 2: Quarter resolution                     -- 400-1600m
LOD 3: 1/8 resolution                         -- 1600m+
```

**Geomorphing:** To prevent visible "popping" between LOD levels, vertices smoothly interpolate between their LOD positions:
```hlsl
// In vertex shader
float morphFactor = smoothstep(lodStartDist, lodEndDist, distanceToCamera);
float3 morphedPos = lerp(highLodPos, lowLodPos, morphFactor);
```

### 7.3 Billboard Impostor Trees

**Confidence:** HIGH

**Octahedral Impostors:**
Pre-render a 3D object from multiple angles arranged in an octahedral pattern, stored in a texture atlas.

**How It Works:**
1. **Bake Phase:**
   - Place camera at positions on a hemisphere around the object
   - Render the object from each position (typically 8x8 or 12x12 grid)
   - Store renders in a texture atlas with corresponding depth/normal data

2. **Runtime Rendering:**
   - For each distant tree instance, determine the viewing angle
   - Map the viewing angle to octahedral UV coordinates
   - Sample the atlas to get the correct view
   - Render as a camera-facing billboard with the sampled texture

**Atlas Layout (8x8 = 64 views):**
```
+----+----+----+----+----+----+----+----+
| 0  | 1  | 2  | 3  | 4  | 5  | 6  | 7  |  <- Top-down views
+----+----+----+----+----+----+----+----+
| 8  | 9  | 10 | ...                     |  <- High angle views
+----+----+----+----+----+----+----+----+
| ...                                    |
+----+----+----+----+----+----+----+----+
| 56 | 57 | 58 | 59 | 60 | 61 | 62 | 63 |  <- Eye-level views
+----+----+----+----+----+----+----+----+
```

**Performance Impact:**
Unity reports frame time dropping from 111ms to 5.78ms when switching 1,600 tree instances from real meshes to impostors -- a 19x improvement.

### 7.4 Unity Terrain Streaming (Additive Scene Loading)

**Confidence:** HIGH

**Implementation Pattern:**
```csharp
// Terrain Streaming Manager
public class TerrainStreamingManager : MonoBehaviour
{
    public float loadDistance = 500f;
    public float unloadDistance = 700f;

    private Dictionary<Vector2Int, AsyncOperation> loadedChunks = new();

    void Update()
    {
        Vector2Int playerChunk = WorldToChunk(player.position);

        // Load nearby chunks
        foreach (var chunk in GetChunksInRange(playerChunk, loadDistance))
        {
            if (!loadedChunks.ContainsKey(chunk))
            {
                string sceneName = $"Terrain_{chunk.x}_{chunk.y}";
                var op = SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive);
                op.allowSceneActivation = true;
                loadedChunks[chunk] = op;
            }
        }

        // Unload distant chunks
        foreach (var (chunk, op) in loadedChunks.ToList())
        {
            float dist = ChunkDistance(playerChunk, chunk);
            if (dist > unloadDistance && op.isDone)
            {
                SceneManager.UnloadSceneAsync($"Terrain_{chunk.x}_{chunk.y}");
                loadedChunks.Remove(chunk);
            }
        }
    }
}
```

**Load Priority:** Nearest chunks first. Unity processes only one AsyncOperation at a time, so order matters.

**Progressive Loading Order:**
1. Terrain geometry (<100ms)
2. Textures/materials (<300ms)
3. Vegetation instances (<1s)
4. Volumetric/effects (<3s)

---

## 8. Techniques We Can Implement in Blender Python

### 8.1 HeightField-Style Operation Chaining

**Priority: HIGH**

Create a composable terrain pipeline where each operation reads and modifies a heightmap array:

```python
# Target API
pipeline = TerrainPipeline(resolution=257, scale=100.0)
pipeline.add(NoiseLayer("mountains", octaves=8, persistence=0.5))
pipeline.add(NoiseLayer("detail", octaves=4, persistence=0.3, blend="add", strength=0.2))
pipeline.add(HydraulicErosion(iterations=5000, scale="large"))
pipeline.add(ThermalErosion(iterations=10, talus_angle=35))
pipeline.add(HydraulicErosion(iterations=2000, scale="small"))  # Fine detail pass
pipeline.add(MaskBySlope(min_slope=40, max_slope=90))
pipeline.add(ScatterOnMask("rocks", min_distance=3.0))
heightmap, layers = pipeline.execute(seed=42)
```

**Implementation in our codebase:**
Our `_terrain_noise.py` already does single-pass noise generation. We need to add:
1. A pipeline class that chains operations
2. Multi-scale erosion (pass `scale` parameter to erosion functions)
3. Mask output from each operation (slope mask, erosion mask, flow mask)
4. Layer stack for combining masks

### 8.2 Flow Map Computation from Heightfield

**Priority: HIGH**

```python
def compute_flow_map(heightmap: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute flow direction and accumulation from heightmap.

    Returns:
        flow_direction: 2D array of direction indices (0-7 for D8)
        flow_accumulation: 2D array of accumulated upstream area
    """
    rows, cols = heightmap.shape
    flow_dir = np.full((rows, cols), -1, dtype=np.int8)
    flow_acc = np.ones((rows, cols), dtype=np.float64)

    # D8 flow direction
    offsets = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
    distances = [1.414, 1.0, 1.414, 1.0, 1.0, 1.414, 1.0, 1.414]

    for r in range(1, rows-1):
        for c in range(1, cols-1):
            max_slope = 0
            for i, ((dr, dc), dist) in enumerate(zip(offsets, distances)):
                slope = (heightmap[r,c] - heightmap[r+dr,c+dc]) / dist
                if slope > max_slope:
                    max_slope = slope
                    flow_dir[r,c] = i

    # Flow accumulation (topological sort, high to low)
    sorted_cells = np.argsort(-heightmap.ravel())
    for idx in sorted_cells:
        r, c = divmod(idx, cols)
        d = flow_dir[r, c]
        if d >= 0:
            dr, dc = offsets[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                flow_acc[nr, nc] += flow_acc[r, c]

    return flow_dir, flow_acc
```

### 8.3 Enhanced Vegetation Placement

**Priority: MEDIUM**

Extend existing Poisson disk + biome filter with:
1. Variable-radius Poisson disk driven by density maps
2. Exclusion zones from roads, buildings, water
3. Cluster spawning for natural groupings
4. Multi-species cross-distance constraints

### 8.4 L-System Vegetation Generation

**Priority: MEDIUM**

```python
def generate_lsystem_tree(
    axiom: str = "F",
    rules: dict[str, str] = None,
    angle: float = 25.0,
    iterations: int = 4,
    segment_length: float = 1.0,
    thickness: float = 0.1,
    taper: float = 0.7,
    seed: int = 0,
) -> list[dict]:
    """Generate tree mesh specs from L-system grammar.

    Returns list of cylinder/sphere specs for mesh_from_spec.
    """
    if rules is None:
        rules = {"F": "FF+[+F-F-F]-[-F+F+F]"}

    # String expansion
    current = axiom
    for _ in range(iterations):
        next_str = ""
        for ch in current:
            next_str += rules.get(ch, ch)
        current = next_str

    # Turtle interpretation
    specs = []
    pos = Vector3(0, 0, 0)
    direction = Vector3(0, 0, 1)
    thickness_current = thickness
    stack = []

    for ch in current:
        if ch == 'F':
            end = pos + direction * segment_length
            specs.append({
                "type": "cylinder",
                "start": pos, "end": end,
                "radius": thickness_current,
            })
            pos = end
            thickness_current *= taper
        elif ch == '+':
            direction = rotate(direction, angle)
        elif ch == '-':
            direction = rotate(direction, -angle)
        elif ch == '[':
            stack.append((pos.copy(), direction.copy(), thickness_current))
        elif ch == ']':
            pos, direction, thickness_current = stack.pop()

    return specs
```

### 8.5 Modular Piece Connection Validation

**Priority: HIGH**

```python
class ConnectionPoint:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    size: tuple[float, float]  # width, height
    conn_type: str  # "door", "hallway", "open", "wall"
    tags: set[str]  # compatibility tags

def validate_connection(point_a: ConnectionPoint, point_b: ConnectionPoint,
                       tolerance: float = 0.01) -> bool:
    """Check if two connection points can snap together."""
    # Positions must align
    pos_diff = distance(point_a.position, point_b.position)
    if pos_diff > tolerance:
        return False

    # Normals must face opposite directions
    dot = dot_product(point_a.normal, point_b.normal)
    if dot > -0.99:  # Should be approximately -1
        return False

    # Sizes must match
    if abs(point_a.size[0] - point_b.size[0]) > tolerance:
        return False
    if abs(point_a.size[1] - point_b.size[1]) > tolerance:
        return False

    # Types must be compatible
    if point_a.conn_type != point_b.conn_type:
        return False

    return True
```

### 8.6 Terrain Chunk Splitting for Streaming

**Priority: MEDIUM**

```python
def split_terrain_to_chunks(
    heightmap: np.ndarray,
    splatmap: np.ndarray,
    chunk_size: int = 257,  # Vertices per chunk side
    overlap: int = 1,       # 1 vertex overlap for seamless normals
) -> dict[tuple[int,int], dict]:
    """Split a large terrain into streaming-ready chunks.

    Each chunk gets its own heightmap RAW file and splatmap.
    Returns dict of grid_pos -> chunk_data.
    """
    rows, cols = heightmap.shape
    chunks = {}

    # Calculate chunk grid
    effective_size = chunk_size - overlap
    grid_rows = math.ceil(rows / effective_size)
    grid_cols = math.ceil(cols / effective_size)

    for gr in range(grid_rows):
        for gc in range(grid_cols):
            r_start = gr * effective_size
            c_start = gc * effective_size
            r_end = min(r_start + chunk_size, rows)
            c_end = min(c_start + chunk_size, cols)

            chunk_height = heightmap[r_start:r_end, c_start:c_end]
            chunk_splat = splatmap[r_start:r_end, c_start:c_end]

            chunks[(gr, gc)] = {
                "heightmap": chunk_height,
                "splatmap": chunk_splat,
                "world_offset": (gc * effective_size, gr * effective_size),
                "raw_bytes": export_heightmap_raw(chunk_height),
            }

    return chunks
```

---

## 9. Techniques We Can Implement in Unity C#

### 9.1 Height-Based Texture Blending Shader

**Priority: HIGH**

```hlsl
// VeilBreakers Height-Blend Terrain Shader (URP)

// Height blend function
float3 HeightBlend(float3 colorA, float heightA, float3 colorB, float heightB,
                   float blendWeight, float blendDepth)
{
    // Compute effective heights
    float ha = heightA + (1.0 - blendWeight) * 2.0 - 1.0;
    float hb = heightB + blendWeight * 2.0 - 1.0;

    // Soft max -- the higher surface "wins"
    float ma = max(ha, hb) - blendDepth;
    float ba = max(ha - ma, 0);
    float bb = max(hb - ma, 0);

    // Normalized weights
    float totalWeight = ba + bb + 0.001;
    return (colorA * ba + colorB * bb) / totalWeight;
}

// In fragment shader:
half4 frag(Varyings input) : SV_Target
{
    float4 splatmap = SAMPLE_TEXTURE2D(_SplatMap, sampler_SplatMap, input.uv);

    // Sample each layer
    float3 c0 = SampleLayer(0, input.uv); float h0 = SampleHeight(0, input.uv);
    float3 c1 = SampleLayer(1, input.uv); float h1 = SampleHeight(1, input.uv);
    float3 c2 = SampleLayer(2, input.uv); float h2 = SampleHeight(2, input.uv);
    float3 c3 = SampleLayer(3, input.uv); float h3 = SampleHeight(3, input.uv);

    // Sequential height blending
    float3 result = c0;
    result = HeightBlend(result, h0, c1, h1, splatmap.r, _BlendDepth);
    result = HeightBlend(result, h0, c2, h2, splatmap.g, _BlendDepth);
    result = HeightBlend(result, h0, c3, h3, splatmap.b, _BlendDepth);

    return half4(result, 1.0);
}
```

### 9.2 GPU Instanced Vegetation Rendering

**Priority: HIGH**

```csharp
// Compute shader-driven vegetation instancing
// Handles frustum culling, distance culling, and LOD selection on GPU

[System.Serializable]
public struct VegetationInstance
{
    public Vector3 position;
    public float rotation;
    public float scale;
    public int typeIndex;
}

public class GPUVegetationRenderer : MonoBehaviour
{
    public ComputeShader cullingShader;
    public Mesh[] vegetationMeshes;
    public Material[] vegetationMaterials;

    private ComputeBuffer instanceBuffer;
    private ComputeBuffer argsBuffer;
    private ComputeBuffer visibleBuffer;

    void Update()
    {
        // 1. Run culling compute shader
        cullingShader.SetVector("_CameraPos", Camera.main.transform.position);
        cullingShader.SetMatrix("_VP", Camera.main.projectionMatrix *
                                       Camera.main.worldToCameraMatrix);
        cullingShader.SetFloat("_MaxDistance", cullDistance);
        cullingShader.Dispatch(cullingKernel, instanceCount / 64, 1, 1);

        // 2. Draw with indirect instancing
        Graphics.DrawMeshInstancedIndirect(
            vegetationMeshes[0], 0, vegetationMaterials[0],
            bounds, argsBuffer
        );
    }
}
```

### 9.3 Terrain Streaming with Additive Scene Loading

**Priority: HIGH**

```csharp
public class TerrainStreamer : MonoBehaviour
{
    [SerializeField] private float loadRadius = 500f;
    [SerializeField] private float unloadRadius = 700f;
    [SerializeField] private float chunkSize = 256f;

    private Dictionary<Vector2Int, SceneLoadState> chunks = new();
    private Transform player;

    private enum SceneLoadState { Loading, Loaded, Unloading }

    void Update()
    {
        Vector2Int playerChunk = new Vector2Int(
            Mathf.FloorToInt(player.position.x / chunkSize),
            Mathf.FloorToInt(player.position.z / chunkSize)
        );

        int loadChunkRadius = Mathf.CeilToInt(loadRadius / chunkSize);

        // Priority-sorted loading (nearest first)
        var toLoad = new List<(Vector2Int pos, float dist)>();

        for (int x = -loadChunkRadius; x <= loadChunkRadius; x++)
        for (int z = -loadChunkRadius; z <= loadChunkRadius; z++)
        {
            Vector2Int pos = playerChunk + new Vector2Int(x, z);
            float dist = new Vector2(x, z).magnitude * chunkSize;

            if (dist <= loadRadius && !chunks.ContainsKey(pos))
                toLoad.Add((pos, dist));
        }

        toLoad.Sort((a, b) => a.dist.CompareTo(b.dist));

        foreach (var (pos, _) in toLoad)
        {
            StartCoroutine(LoadChunk(pos));
        }

        // Unload distant chunks
        foreach (var (pos, state) in chunks.ToList())
        {
            float dist = Vector2.Distance(
                new Vector2(pos.x, pos.y),
                new Vector2(playerChunk.x, playerChunk.y)
            ) * chunkSize;

            if (dist > unloadRadius && state == SceneLoadState.Loaded)
                StartCoroutine(UnloadChunk(pos));
        }
    }

    private IEnumerator LoadChunk(Vector2Int pos)
    {
        chunks[pos] = SceneLoadState.Loading;
        string sceneName = $"Terrain_{pos.x}_{pos.y}";
        var op = SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive);
        yield return op;
        chunks[pos] = SceneLoadState.Loaded;
    }
}
```

### 9.4 Billboard Impostor Rendering

**Priority: MEDIUM**

```csharp
// Editor script to bake impostor atlas from a tree prefab
public static class ImpostorBaker
{
    public static Texture2D BakeImpostorAtlas(
        GameObject treePrefab, int gridSize = 8, int cellResolution = 256)
    {
        int atlasSize = gridSize * cellResolution;
        var atlas = new Texture2D(atlasSize, atlasSize, TextureFormat.RGBA32, false);

        // Setup orthographic camera
        var camGO = new GameObject("ImpostorCam");
        var cam = camGO.AddComponent<Camera>();
        cam.orthographic = true;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0, 0, 0, 0);

        var tree = Instantiate(treePrefab);
        var bounds = CalculateBounds(tree);
        cam.orthographicSize = bounds.extents.magnitude;

        var rt = new RenderTexture(cellResolution, cellResolution, 24);

        for (int y = 0; y < gridSize; y++)
        for (int x = 0; x < gridSize; x++)
        {
            // Octahedral mapping: grid position -> view direction
            float u = (x + 0.5f) / gridSize * 2f - 1f;
            float v = (y + 0.5f) / gridSize * 2f - 1f;
            Vector3 viewDir = OctahedralDecode(u, v);

            cam.transform.position = bounds.center - viewDir * bounds.extents.magnitude * 2f;
            cam.transform.LookAt(bounds.center);

            cam.targetTexture = rt;
            cam.Render();

            // Copy to atlas
            RenderTexture.active = rt;
            atlas.ReadPixels(
                new Rect(0, 0, cellResolution, cellResolution),
                x * cellResolution, y * cellResolution
            );
        }

        atlas.Apply();
        DestroyImmediate(camGO);
        DestroyImmediate(tree);
        DestroyImmediate(rt);
        return atlas;
    }

    private static Vector3 OctahedralDecode(float u, float v)
    {
        Vector3 n = new Vector3(u, 1f - Mathf.Abs(u) - Mathf.Abs(v), v);
        if (n.y < 0)
        {
            float ox = (1f - Mathf.Abs(n.z)) * Mathf.Sign(n.x);
            float oz = (1f - Mathf.Abs(n.x)) * Mathf.Sign(n.z);
            n.x = ox;
            n.z = oz;
        }
        return n.normalized;
    }
}
```

### 9.5 Wind Animation from Vertex Colors

**Priority: MEDIUM**

```hlsl
// URP Foliage Wind Shader (Shader Graph compatible structure)

void WindAnimation_float(
    float3 worldPos,
    float3 objectPos,
    float vertexColorR,  // Branch sway weight
    float vertexColorB,  // Leaf flutter weight
    float windSpeed,
    float windStrength,
    float time,
    out float3 offset)
{
    // Phase offset based on world position (prevents uniform motion)
    float phase = dot(objectPos.xz, float2(0.7, 0.3));

    // Primary sway (whole tree/branch)
    float sway = sin(time * windSpeed + phase) * windStrength;
    float3 primaryOffset = float3(sway, 0, sway * 0.5) * vertexColorR;

    // Secondary flutter (leaves)
    float flutter = sin(time * windSpeed * 3.7 + worldPos.x * 1.3 + worldPos.z * 0.7);
    flutter *= sin(time * windSpeed * 2.3 + worldPos.y * 2.1);
    float3 leafOffset = float3(flutter, flutter * 0.3, flutter * 0.5)
                        * windStrength * 0.3 * vertexColorB;

    // Combine
    offset = primaryOffset + leafOffset;
}
```

---

## 10. Implementation Priority

### Priority Tiers for VB Toolkit Enhancement

**Tier 1 -- High Impact, Feasible Now:**

| Technique | Where | Why | Effort |
|-----------|-------|-----|--------|
| Height-based texture blending shader | Unity | Dramatically better terrain transitions vs linear blend | 2-3 days |
| Multi-scale erosion chaining | Blender | Better terrain quality with minimal API change | 1-2 days |
| Flow map computation | Blender | Enables river placement, moisture maps, better scatter | 1-2 days |
| Cosine-falloff road carving | Blender | Better road integration vs current linear falloff | 1 day |
| Terrain chunk splitting | Blender | Export ready-to-stream terrain chunks | 1-2 days |
| Terrain streaming manager | Unity | Required for any open-world content | 2-3 days |
| Connection point validation | Blender | Our modular kit gen needs validation | 1 day |
| Exclusion zone masks | Blender | No-build/no-scatter zones around roads/buildings | 1 day |

**Tier 2 -- High Impact, Moderate Effort:**

| Technique | Where | Why | Effort |
|-----------|-------|-----|--------|
| GPU instanced vegetation | Unity | Performance requirement for dense forests | 3-5 days |
| Variable-radius Poisson disk | Blender | Density-map-driven natural scatter | 2 days |
| L-system tree generation | Blender | Procedural tree variety without AI/external assets | 3-4 days |
| Billboard impostor baking | Unity | Required for distant vegetation performance | 3-4 days |
| Wind vertex shader | Unity | All foliage needs wind animation | 2-3 days |
| Macro terrain features (mesa, canyon) | Blender | New terrain_type presets | 2-3 days |

**Tier 3 -- Nice to Have:**

| Technique | Where | Why | Effort |
|-----------|-------|-----|--------|
| Resolution-independent erosion | Blender | Consistent results at different resolutions | 2 days |
| Ecosystem simulation scatter | Blender | UE5-style competitive growth model | 3-5 days |
| Separated erosion outputs | Blender | Independent sediment/channel/debris layers | 2-3 days |
| Trim sheet UV mapping tools | Blender | Auto-UV to trim sheet strips | 3-4 days |
| BSP-style boolean chains | Blender | Ordered CSG operation queue | 2-3 days |

---

## 11. Existing VB Toolkit Coverage & Gaps

### What We Already Have

| Feature | Implementation | Quality |
|---------|---------------|---------|
| Terrain noise generation | `_terrain_noise.py` -- 6 presets, fBm, OpenSimplex | Good |
| Hydraulic erosion | `_terrain_erosion.py` -- droplet-based, bilinear interp | Good (matches Lague) |
| Thermal erosion | `_terrain_erosion.py` -- talus angle, 8-neighbor | Good |
| Poisson disk sampling | `_scatter_engine.py` -- Bridson's algorithm | Good |
| Biome-filtered scatter | `_scatter_engine.py` -- altitude/slope rules | Good |
| Heightmap export (RAW) | `environment.py` -- 16-bit for Unity | Good |
| Unity terrain setup | `scene_templates.py` -- heightmap import + splatmaps | Good |
| Modular kit generation | `worldbuilding.py` -- building grammar + mesh specs | Good |
| Road generation | `_terrain_noise.py` -- A* weighted path | Basic |
| River carving | `_terrain_noise.py` -- A* path carving | Basic |

### Key Gaps

| Gap | Impact | Technique to Implement |
|-----|--------|----------------------|
| No flow map computation | Can't auto-place rivers/moisture-dependent vegetation | D8/MFD flow direction + accumulation |
| No multi-scale erosion | Single-pass erosion lacks fine detail | Pipeline chaining with scale parameter |
| No density maps / exclusion zones | Scatter ignores roads/buildings/water | Mask composition system |
| No height-based texture blending | Unity terrain uses basic linear blend | Custom URP terrain shader |
| No terrain streaming | Can't handle open-world map sizes | Additive scene loading manager |
| No GPU vegetation instancing | Dense forests tank performance | Compute shader + indirect draw |
| No impostor baking | Distant trees are expensive | Octahedral impostor baker |
| No wind animation | Static vegetation looks dead | Vertex color wind shader |
| No L-system trees | No procedural tree variation | String rewrite + turtle interpreter |
| No connection validation | Modular pieces can mis-align | Connection point matching system |
| Linear road falloff | Roads have harsh terrain edges | Cosine-blended falloff |
| No variable-radius scatter | Uniform density regardless of biome | Density-map-driven Poisson disk |

---

## 12. Sources

### Primary (HIGH confidence)

- [Unreal Engine BSP Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/geometry-brush-actors-in-unreal-engine) -- BSP brush system architecture
- [Unreal Engine Landscape Materials](https://docs.unrealengine.com/4.27/en-US/BuildingWorlds/Landscape/Materials) -- Layer blending algorithm
- [Unreal Engine Procedural Foliage Tool](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-foliage-tool-in-unreal-engine) -- Ecosystem simulation spawner
- [Unreal Engine Landscape Splines](https://docs.unrealengine.com/5.3/en-US/landscape-splines-in-unreal-engine/) -- Spline terrain deformation
- [Unreal Engine Level Streaming](https://dev.epicgames.com/documentation/en-us/unreal-engine/level-streaming-in-unreal-engine) -- Streaming volumes and World Partition
- [SideFX HeightField Erode 3.0](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode.html) -- Multi-scale erosion parameters
- [SideFX HeightField Erode Thermal](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode_thermal.html) -- Thermal erosion algorithm
- [SideFX Scatter Node](https://www.sidefx.com/docs/houdini/nodes/sop/scatter.html) -- Point distribution
- [Unity ProBuilder Boolean Operations](https://docs.unity3d.com/Packages/com.unity.probuilder@6.0/manual/boolean.html) -- CSG implementation
- [Unity GPU Instancing Manual](https://docs.unity3d.com/Manual/GPUInstancing.html) -- Instanced rendering
- [Unity SceneManager.LoadSceneAsync](https://docs.unity3d.com/ScriptReference/SceneManagement.SceneManager.LoadSceneAsync.html) -- Additive scene loading
- [Unity Terrain Tree LOD](https://docs.unity3d.com/6000.0/Documentation/Manual/terrain-Tree-LOD.html) -- Billboard tree system
- [Sebastian Lague Hydraulic Erosion (GitHub)](https://github.com/SebLague/Hydraulic-Erosion) -- Droplet erosion implementation (MIT license)
- [Axel Paris -- Terrain Erosion on the GPU](https://aparis69.github.io/public_html/posts/terrain_erosion.html) -- Thermal/hydraulic GPU algorithms

### Secondary (MEDIUM confidence)

- [Joel Burgess -- Skyrim's Modular Level Design (GDC 2013)](https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design) -- Kit system and grid sizes
- [The Level Design Book -- Modular Kit Design](https://book.leveldesignbook.com/process/blockout/metrics/modular) -- Kit piece types and naming
- [Gaea Documentation -- Erosion](https://docs.quadspinner.com/Reference/Erosion/Erosion.html) -- Separated erosion outputs
- [Gaea Documentation -- Noise Generators](https://gaea-docs.readthedocs.io/en/1.x/generators/noise/) -- FastNoiseLite terrain generation
- [Cyanilux -- GPU Instanced Grass Breakdown](https://www.cyanilux.com/tutorials/gpu-instanced-grass-breakdown/) -- Compute shader grass
- [Heightmap Blending Tutorial (Shaderic)](https://www.shaderic.com/tutorials/HeightmapBlending.html) -- Height blend shader algorithm
- [Amplify Impostors](https://wiki.amplify.pt/index.php?title=Unity_Products:Amplify_Impostors/Manual) -- Octahedral impostor baking
- [ArcGIS Flow Direction Documentation](https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/how-flow-direction-works.htm) -- D8 flow direction algorithm
- [NedMakesGames -- Foliage Shader in URP](https://nedmakesgames.medium.com/creating-a-foliage-shader-in-unity-urp-shader-graph-5854bf8dc4c2) -- Wind vertex displacement

### Tertiary (LOW confidence)

- [World Machine 2025 Hurricane Ridge](https://www.world-machine.com/) -- New erosion model (no detailed algorithm docs available)
- [Gaea 3.0 Announcement](https://www.cgchannel.com/2025/12/quadspinner-unveils-gaea-3-0/) -- 2.7D displacement, sand/snow simulation
- [Reshadable Impostors (2025 paper)](https://onlinelibrary.wiley.com/doi/10.1111/cgf.70183) -- Forward-mapping impostor rendering
- [NVIDIA GPU Laplacian Pyramid Blending (2025)](https://app.cinevva.com/guides/landscape-generation-browser) -- Real-time shader blending without precomputation
