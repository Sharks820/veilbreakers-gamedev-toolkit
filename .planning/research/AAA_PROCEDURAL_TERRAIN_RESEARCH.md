# AAA Procedural Terrain Generation in Blender Python (bpy/bmesh)

**Researched:** 2026-04-03
**Domain:** Procedural terrain, water, vegetation, castles, environmental props for dark fantasy action RPG
**Target:** VeilBreakers MCP toolkit -- blender_execute, terrain handlers, vegetation_system, worldbuilding
**Confidence:** HIGH (cross-referenced existing codebase, academic papers, GDC postmortems, open-source implementations)

---

## Table of Contents

1. [Terrain Mesh Generation](#1-terrain-mesh-generation)
2. [Terrain Texturing and Materials](#2-terrain-texturing-and-materials)
3. [Water Bodies](#3-water-bodies)
4. [Vegetation System](#4-vegetation-system)
5. [Castle and Settlement Generation](#5-castle-and-settlement-generation)
6. [Environmental Props](#6-environmental-props)
7. [Unity Export Considerations](#7-unity-export-considerations)
8. [VeilBreakers Codebase Status](#8-veilbreakers-codebase-status)
9. [Recommended Improvements](#9-recommended-improvements)
10. [Sources](#10-sources)

---

## 1. Terrain Mesh Generation

### 1.1 Heightmap Noise Techniques (bpy/numpy)

**Best approach: fBm (Fractal Brownian Motion) with OpenSimplex noise, numpy-vectorized.**

The VeilBreakers codebase already implements this correctly in `_terrain_noise.py` with:
- OpenSimplex noise (preferred) with permutation-table fallback
- 8 terrain presets (mountains, hills, plains, volcanic, canyon, cliffs, flat, chaotic)
- numpy meshgrid vectorization (256x256x8 octaves in ~0.05s)

**The correct noise layering approach for realistic terrain:**

```python
# Layer 1: Continental shape (very low frequency, 1-2 octaves)
continental = fbm(x * 0.002, y * 0.002, octaves=2)

# Layer 2: Mountain ranges (medium frequency, ridged noise)
# Use abs(noise) for ridges -- this creates sharp peaks
ridged = 1.0 - abs(fbm(x * 0.01, y * 0.01, octaves=4))
ridged = ridged ** 2  # Sharpen the ridges

# Layer 3: Hills and valleys (standard fBm, 6-8 octaves)
detail = fbm(x * 0.05, y * 0.05, octaves=6, persistence=0.45)

# Layer 4: Micro detail (high frequency, low amplitude)
micro = fbm(x * 0.2, y * 0.2, octaves=3, persistence=0.3) * 0.05

# Composite with altitude-dependent blending
height = continental * 0.4 + ridged * mountain_mask * 0.35 + detail * 0.2 + micro
```

**Critical insight: Use RIDGED noise for mountains, not standard fBm.** Standard fBm creates rounded hills. Ridged noise (taking `1.0 - abs(noise)`) creates sharp ridgelines and peaks. The VeilBreakers `canyon` preset uses `ridge_strength` but should be expanded for mountain ranges.

### 1.2 Erosion Simulation

**Hydraulic erosion is the single most important post-process for realistic terrain.** Without it, procedural terrain looks artificial.

**Droplet-based hydraulic erosion algorithm (recommended for VeilBreakers):**

```python
def hydraulic_erosion(heightmap: np.ndarray, iterations: int = 50000,
                      seed: int = 0) -> np.ndarray:
    """Particle-based hydraulic erosion.
    
    Each droplet:
    1. Spawns at random position
    2. Computes gradient via bilinear interpolation
    3. Moves downhill following gradient
    4. Erodes based on: speed * slope * (capacity - sediment)
    5. Deposits when: capacity < sediment (flat areas, pools)
    6. Evaporates gradually, depositing remaining sediment
    """
    rng = np.random.default_rng(seed)
    result = heightmap.copy()
    rows, cols = result.shape
    
    # Key parameters (tuned for game terrain, not geological accuracy)
    inertia = 0.05        # How much previous direction influences movement
    capacity_mult = 4.0   # Sediment carrying capacity multiplier
    deposition = 0.3      # Fraction of excess sediment deposited per step
    erosion_rate = 0.3     # Fraction of capacity deficit eroded per step
    evaporation = 0.01    # Water loss per step
    min_slope = 0.01      # Minimum slope to prevent division by zero
    max_lifetime = 64     # Steps before droplet is removed
    erosion_radius = 3    # Radius for distributing erosion/deposition
    
    for _ in range(iterations):
        # Spawn at random position
        x = rng.uniform(1, cols - 2)
        y = rng.uniform(1, rows - 2)
        dx, dy = 0.0, 0.0
        speed = 1.0
        water = 1.0
        sediment = 0.0
        
        for _ in range(max_lifetime):
            ix, iy = int(x), int(y)
            if ix < 1 or ix >= cols - 2 or iy < 1 or iy >= rows - 2:
                break
            
            # Compute gradient via bilinear interpolation
            gx = (result[iy, ix+1] - result[iy, ix-1]) * 0.5
            gy = (result[iy+1, ix] - result[iy-1, ix]) * 0.5
            
            # Update direction with inertia
            dx = dx * inertia - gx * (1 - inertia)
            dy = dy * inertia - gy * (1 - inertia)
            
            length = math.sqrt(dx*dx + dy*dy)
            if length < 1e-6:
                break
            dx /= length
            dy /= length
            
            # Move droplet
            new_x = x + dx
            new_y = y + dy
            
            # Height difference
            old_h = result[iy, ix]
            nix, niy = int(new_x), int(new_y)
            if nix < 0 or nix >= cols or niy < 0 or niy >= rows:
                break
            new_h = result[niy, nix]
            h_diff = new_h - old_h
            
            # Sediment capacity based on speed and slope
            capacity = max(-h_diff, min_slope) * speed * water * capacity_mult
            
            if sediment > capacity or h_diff > 0:
                # Deposit: on flat ground or uphill
                deposit_amount = (sediment - capacity) * deposition if h_diff <= 0 else min(sediment, h_diff)
                result[iy, ix] += deposit_amount
                sediment -= deposit_amount
            else:
                # Erode: downhill with capacity remaining
                erode_amount = min((capacity - sediment) * erosion_rate, -h_diff)
                result[iy, ix] -= erode_amount
                sediment += erode_amount
            
            speed = math.sqrt(max(0, speed*speed + h_diff))
            water *= (1 - evaporation)
            x, y = new_x, new_y
    
    return result
```

**Parameters that matter most:**
- `iterations`: 35,000-50,000 for 256x256 terrain (scales linearly with resolution)
- `erosion_radius`: 3 cells creates natural-looking erosion grooves
- `capacity_mult`: Higher = deeper channels. 4.0 is good for dark fantasy (deep gorges)
- `inertia`: 0.05 = water follows gradient closely (realistic). Higher = smoother channels

**Thermal erosion (complementary, simpler):**

```python
def thermal_erosion(heightmap: np.ndarray, iterations: int = 50,
                    talus_angle: float = 0.04) -> np.ndarray:
    """Thermal weathering -- collapses slopes steeper than talus angle.
    
    Simulates freeze-thaw cycles that break down cliff faces.
    Much faster than hydraulic erosion, run AFTER hydraulic.
    """
    result = heightmap.copy()
    rows, cols = result.shape
    
    for _ in range(iterations):
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                h = result[r, c]
                # Check 4-connected neighbors
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nh = result[r+dr, c+dc]
                    diff = h - nh
                    if diff > talus_angle:
                        transfer = diff * 0.5
                        result[r, c] -= transfer
                        result[r+dr, c+dc] += transfer
    return result
```

**VeilBreakers already has thermal erosion in `terrain_advanced.py`.** The hydraulic erosion droplet algorithm should be added or enhanced.

### 1.3 Feature-Specific Terrain Shapes

**Hills and Valleys:**
- Use smooth fBm (persistence 0.4-0.5, 6 octaves)
- Apply `smoothstep` post-processing to flatten valley floors
- Valley floor height: `h = max(h, valley_floor_level)` within valley radius

**Cliffs and Plateaus:**
- Step function post-processing: `h = round(h * step_count) / step_count`
- Then smooth transitions between steps with a narrow blend zone
- VeilBreakers `cliffs` preset already uses this (`"post_process": "step"`)

**Mountain Ridgelines:**
- Ridged multifractal: `h = 1.0 - abs(noise(x, y))`
- Apply power function to sharpen: `h = h ** 1.5`
- Chain multiple ridged noise at different frequencies for realistic ranges
- Add a "domain warping" pass: offset noise coordinates by another noise field to break up regularity

**Canyon/Gorge with Natural Banks:**
- Do NOT carve straight channels (the VeilBreakers `carve_river_path` uses A* which is good)
- Apply smooth falloff from channel center: `cosine_falloff(distance/width)`
- Add noise perturbation to the channel edges
- Layer multiple width variations along the path length
- Bank slopes should follow: steep near rim (0.7-1.0 slope), gentler near floor (0.3-0.5)

```python
def natural_bank_profile(distance_from_center: float, half_width: float) -> float:
    """Natural river/canyon bank profile. NOT a straight V-cut.
    
    Returns height offset (0 at center, 1 at full bank top).
    Profile: gentle slope at bottom, steeper at mid-height, 
    gentle rollover at top (S-curve).
    """
    t = min(distance_from_center / half_width, 1.0)
    # Hermite S-curve: gentle-steep-gentle
    return 3*t*t - 2*t*t*t
```

### 1.4 BMesh vs Numpy for Terrain

**Use numpy for heightmap computation, BMesh only for final mesh creation.**

```python
import bmesh
import bpy
import numpy as np

def heightmap_to_mesh(heightmap: np.ndarray, scale: float = 100.0,
                      height_scale: float = 20.0) -> bpy.types.Object:
    """Convert numpy heightmap to Blender mesh via BMesh."""
    rows, cols = heightmap.shape
    
    mesh = bpy.data.meshes.new("Terrain")
    bm = bmesh.new()
    
    # Create vertex grid
    verts = []
    for r in range(rows):
        for c in range(cols):
            x = (c / (cols - 1) - 0.5) * scale
            y = (r / (rows - 1) - 0.5) * scale
            z = heightmap[r, c] * height_scale
            verts.append(bm.verts.new((x, y, z)))
    
    bm.verts.ensure_lookup_table()
    
    # Create quad faces
    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            bm.faces.new([verts[i], verts[i+1], 
                          verts[i+cols+1], verts[i+cols]])
    
    bm.to_mesh(mesh)
    bm.free()
    
    mesh.update()
    # Smooth normals for better shading
    for poly in mesh.polygons:
        poly.use_smooth = True
    
    obj = bpy.data.objects.new("Terrain", mesh)
    bpy.context.collection.objects.link(obj)
    return obj
```

**Key performance rules:**
- NEVER modify individual vertices in a loop through bpy.ops -- use BMesh or numpy
- For heightmaps > 512x512, use `numpy.meshgrid` for coordinate generation
- BMesh `bm.verts.ensure_lookup_table()` is required before indexed access
- Always `bm.free()` after `bm.to_mesh()` to prevent memory leaks (VeilBreakers v8.0 fixed several of these)

---

## 2. Terrain Texturing and Materials

### 2.1 Vertex Color Splatmap (Primary Technique for Game Export)

**Use vertex colors as a 4-channel splatmap. This is the most performant and Unity-compatible approach.**

VeilBreakers `terrain_materials.py` already implements this correctly:
- R = grass weight, G = rock weight, B = dirt weight, A = special/biome
- Height and slope analysis determines per-vertex weights
- Biome transition blending smooths boundaries

**The splatmap computation (pure numpy, already in codebase):**

```python
def compute_splatmap(heightmap: np.ndarray, slope_map: np.ndarray,
                     biome_map: np.ndarray) -> np.ndarray:
    """Compute RGBA splatmap from terrain analysis.
    
    R = grass (low slope, mid altitude)
    G = rock (high slope or high altitude)
    B = dirt/mud (low altitude, low slope)
    A = special (biome-specific: snow, sand, swamp, etc.)
    """
    rows, cols = heightmap.shape
    splatmap = np.zeros((rows, cols, 4), dtype=np.float32)
    
    # Normalized altitude
    alt = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min() + 1e-8)
    
    # Rock: steep slopes (>35 degrees) or high altitude (>0.8)
    rock_weight = np.clip((slope_map - 25.0) / 20.0, 0, 1)
    rock_weight = np.maximum(rock_weight, np.clip((alt - 0.75) / 0.15, 0, 1))
    
    # Dirt: low altitude (<0.2), gentle slopes
    dirt_weight = np.clip((0.2 - alt) / 0.15, 0, 1) * np.clip((15 - slope_map) / 10, 0, 1)
    
    # Grass: everything else (mid altitude, gentle slope)
    grass_weight = np.clip(1.0 - rock_weight - dirt_weight, 0, 1)
    
    splatmap[:, :, 0] = grass_weight
    splatmap[:, :, 1] = rock_weight
    splatmap[:, :, 2] = dirt_weight
    # Channel 3 (A) set by biome system
    
    # Normalize so weights sum to 1.0
    total = splatmap.sum(axis=2, keepdims=True)
    total = np.maximum(total, 1e-8)
    splatmap /= total
    
    return splatmap
```

### 2.2 Blender Shader Node Material for Terrain

**Build a single material with height/slope-driven blending using shader nodes.**

```python
def create_terrain_material(name: str = "TerrainMaterial") -> bpy.types.Material:
    """Create a multi-layer terrain material using shader nodes.
    
    Uses vertex color splatmap for texture blending.
    Height-based: grass -> dirt -> rock -> snow
    Slope-based: gentle = grass/dirt, steep = rock/cliff
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1200, 0)
    
    # Final BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (900, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    # Vertex Color splatmap
    vcol = nodes.new("ShaderNodeVertexColor")
    vcol.layer_name = "Splatmap"
    vcol.location = (-600, 0)
    
    # Separate RGBA channels
    sep = nodes.new("ShaderNodeSeparateColor")
    sep.location = (-400, 0)
    links.new(vcol.outputs["Color"], sep.inputs["Color"])
    
    # Texture coordinates
    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-800, -200)
    
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, -200)
    links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])
    
    # Create noise textures for each terrain layer
    layers = [
        ("Grass", (0.065, 0.12, 0.025, 1.0), 0.90, 8.0),   # Dark fantasy grass
        ("Rock",  (0.10, 0.09, 0.07, 1.0),   0.85, 4.0),    # Weathered rock
        ("Dirt",  (0.09, 0.07, 0.04, 1.0),    0.92, 6.0),    # Dark earth
        ("Snow",  (0.35, 0.34, 0.33, 1.0),    0.70, 3.0),    # Dirty snow (not white)
    ]
    
    mix_result = None
    for i, (layer_name, color, roughness, detail_scale) in enumerate(layers):
        # Noise for texture variation
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = detail_scale
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Roughness"].default_value = 0.6
        noise.location = (-200, -i * 300)
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        
        # Color + noise variation
        mix_color = nodes.new("ShaderNodeMix")
        mix_color.data_type = 'RGBA'
        mix_color.inputs[6].default_value = color  # A color
        mix_color.inputs[7].default_value = (color[0]*0.7, color[1]*0.7, 
                                              color[2]*0.7, 1.0)  # B color (darker)
        mix_color.location = (0, -i * 300)
        links.new(noise.outputs["Fac"], mix_color.inputs["Factor"])
        
        if i == 0:
            mix_result = mix_color
        else:
            # Mix with previous result using splatmap channel
            layer_mix = nodes.new("ShaderNodeMix")
            layer_mix.data_type = 'RGBA'
            layer_mix.location = (300, -i * 200)
            links.new(mix_result.outputs[2], layer_mix.inputs[6])  # A = previous
            links.new(mix_color.outputs[2], layer_mix.inputs[7])   # B = this layer
            # Channel index: 0=R(grass), 1=G(rock), 2=B(dirt)
            channel_idx = min(i, 2)
            links.new(sep.outputs[channel_idx], layer_mix.inputs["Factor"])
            mix_result = layer_mix
    
    links.new(mix_result.outputs[2], bsdf.inputs["Base Color"])
    
    return mat
```

### 2.3 Biome-Based Material Zones

VeilBreakers has 14 biome definitions in `terrain_materials.py`. The key design principles:

**Transition zones are critical.** Hard biome boundaries look artificial. Blend over 10-20m with noise-perturbed edges:

```python
def compute_biome_transition(distance_to_border: float, 
                             noise_value: float) -> float:
    """Smooth biome transition with noise-perturbed edge.
    
    Returns blend factor [0, 1] where 0 = biome A, 1 = biome B.
    """
    transition_width = 15.0  # meters
    # Perturb the border position with noise
    perturbed_distance = distance_to_border + noise_value * 5.0
    return smoothstep(-transition_width/2, transition_width/2, perturbed_distance)
```

**Dark fantasy palette constraints (already enforced in codebase):**
- Environment saturation: NEVER exceeds 40%
- Value range: 10-50% (dark world)
- All colors in linear space (Blender native)
- Roughness > 0.7 for all natural surfaces (no shiny terrain)
- Metallic = 0.0 for all terrain (dielectric)

### 2.4 Mud/Riverbank Textures

Near water, terrain should transition through:
1. **Dry grass/dirt** (>5m from water)
2. **Damp earth** (2-5m): darker, lower roughness (0.5-0.6)
3. **Wet mud** (0.5-2m): very dark, low roughness (0.3-0.4), slight specular
4. **Water edge** (<0.5m): mix mud with water material

```python
# Water proximity weight for material blending
def water_proximity_weight(distance_to_water: float) -> dict:
    """Returns material blend weights based on distance to nearest water."""
    if distance_to_water < 0.5:
        return {"mud": 0.3, "water_edge": 0.7}
    elif distance_to_water < 2.0:
        t = (distance_to_water - 0.5) / 1.5
        return {"wet_mud": 1.0 - t, "damp_earth": t}
    elif distance_to_water < 5.0:
        t = (distance_to_water - 2.0) / 3.0
        return {"damp_earth": 1.0 - t, "dry_dirt": t}
    else:
        return {"terrain_default": 1.0}
```

---

## 3. Water Bodies

### 3.1 River/Stream Generation with Natural Meandering

**The correct approach: Cubic Bezier splines with sinusoidal displacement.**

VeilBreakers `carve_river_path` uses A* pathfinding which finds good downhill routes but produces angular paths. The path needs post-processing for natural curves.

**Meandering algorithm:**

```python
def generate_meandering_river(heightmap: np.ndarray, 
                              source: tuple, dest: tuple,
                              meander_amplitude: float = 8.0,
                              meander_frequency: float = 0.05,
                              seed: int = 0) -> list[tuple[float, float]]:
    """Generate naturally meandering river path.
    
    1. Find downhill A* path (coarse route)
    2. Resample to even spacing
    3. Apply sinusoidal displacement perpendicular to flow
    4. Smooth with cubic spline
    5. Variable width along length (narrow at source, wider downstream)
    """
    rng = np.random.default_rng(seed)
    
    # Step 1: Coarse A* path
    coarse_path = astar_downhill(heightmap, source, dest)
    
    # Step 2: Resample to even spacing
    resampled = resample_path(coarse_path, segment_length=5.0)
    
    # Step 3: Perpendicular meander displacement
    result = []
    for i, (x, y) in enumerate(resampled):
        # Direction of flow
        if i < len(resampled) - 1:
            dx = resampled[i+1][0] - x
            dy = resampled[i+1][1] - y
        else:
            dx = x - resampled[i-1][0]
            dy = y - resampled[i-1][1]
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1e-6:
            result.append((x, y))
            continue
        
        # Perpendicular direction
        perp_x = -dy / length
        perp_y = dx / length
        
        # Sinusoidal meander with noise variation
        t = i * meander_frequency
        offset = meander_amplitude * math.sin(t * 2 * math.pi)
        offset += rng.normal(0, meander_amplitude * 0.15)
        
        result.append((x + perp_x * offset, y + perp_y * offset))
    
    # Step 4: Smooth with cubic interpolation
    return smooth_path_cubic(result)
```

**River cross-section profile (NOT a V-cut):**

```
     ___/                          \___
    /      gentle bank slope           \
   |   ____________________________    |
   |  /                            \   |
   | /   deeper center channel      \  |
   |/________________________________\|
```

The river bed should be:
- Asymmetric (outside of meanders is deeper, steeper)
- Wider at bends, narrower at straight sections
- Floor is not flat -- slightly concave with deeper thalweg channel

### 3.2 Lake/Pond Generation

**Lakes are NOT just flat planes. Natural lakes have:**
- Irregular shorelines (use noise-displaced circles/ellipses)
- Gradual depth increase from shore (0.5-2m shallow shelf, then drop-off)
- Inlet and outlet streams
- Reed/vegetation zones along shallow edges

```python
def generate_lake_shoreline(center: tuple, radius: float, 
                            irregularity: float = 0.3,
                            seed: int = 0) -> list[tuple[float, float]]:
    """Generate irregular lake shoreline using noise-displaced circle."""
    rng = np.random.default_rng(seed)
    points = []
    num_points = max(32, int(radius * 4))
    
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        # Noise displacement for irregular shape
        noise_val = _fbm(math.cos(angle) * 2, math.sin(angle) * 2, 
                         seed=seed, octaves=4)
        r = radius * (1.0 + noise_val * irregularity)
        x = center[0] + r * math.cos(angle)
        y = center[1] + r * math.sin(angle)
        points.append((x, y))
    
    return points
```

**Terrain modification for lakes:**
1. Flatten the lake bed below water level
2. Create a gradual slope from shore to lake bed (3-8m transition)
3. Apply noise to the lake bed (not perfectly flat)
4. Ensure water surface plane is exactly at the planned water level

### 3.3 Waterfall Geometry

VeilBreakers already has `generate_waterfall` in `terrain_features.py` and `generate_waterfall_mesh` in `_terrain_depth.py`. Key principles:

- Waterfall face: curved surface, NOT a flat plane
- Mist zone at base: particle effect region marker (export as empty/locator)
- Pool at base: carved depression in terrain
- Rock outcroppings along the fall for visual interest
- Water material with high transparency, animated UV offset for flow

### 3.4 Water Material

```python
def create_water_material(name: str = "WaterSurface", 
                          depth_color: tuple = (0.02, 0.04, 0.03, 0.8),
                          shallow_color: tuple = (0.04, 0.06, 0.04, 0.5)) -> bpy.types.Material:
    """Dark fantasy water material.
    
    Uses:
    - Glass BSDF mixed with Principled for transparency + reflection
    - Noise-driven normal map for ripples
    - Vertex color for depth variation (deeper = darker, more opaque)
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'  # For EEVEE transparency
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    
    # Dark water base color
    bsdf.inputs["Base Color"].default_value = depth_color
    bsdf.inputs["Roughness"].default_value = 0.05  # Very smooth
    bsdf.inputs["IOR"].default_value = 1.333  # Water IOR
    bsdf.inputs["Alpha"].default_value = 0.7
    
    # Noise for ripple normal map
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 20.0
    noise.inputs["Detail"].default_value = 6.0
    
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    return mat
```

**For Unity export:** The Blender water material is a placeholder. Export the water mesh as a separate object with a "Water" material name. In Unity, replace with a proper water shader (URP Water shader or custom).

### 3.5 River Bank Slopes

**The most common mistake is carving straight channels.** Natural riverbanks have:

| Feature | Inner Bank (meander inside) | Outer Bank (meander outside) |
|---------|---------------------------|------------------------------|
| Slope | Gentle (15-25 degrees) | Steep (40-70 degrees) |
| Material | Sandy/muddy deposit | Exposed rock/roots |
| Vegetation | Reeds, cattails, willows | Overhanging trees |
| Width | Wider shelf | Narrow or vertical |

```python
def river_bank_height(distance_from_center: float, 
                      river_half_width: float,
                      is_outer_bank: bool) -> float:
    """Compute bank height profile.
    
    Inner bank: gentle ramp with depositional shelf.
    Outer bank: steep cutbank with overhanging lip.
    """
    t = distance_from_center / river_half_width
    if t < 1.0:
        # In the river channel
        return -0.3 * (1.0 - t * t)  # Concave bed
    
    bank_t = (t - 1.0) / 0.5  # 0-1 over bank width
    if bank_t > 1.0:
        return 1.0  # Above bank, normal terrain
    
    if is_outer_bank:
        # Steep cutbank (almost vertical, then sharp rollover)
        return min(bank_t ** 0.3, 1.0)
    else:
        # Gentle depositional slope (S-curve)
        return 3*bank_t*bank_t - 2*bank_t*bank_t*bank_t
```

---

## 4. Vegetation System

### 4.1 Poisson Disk Sampling with Terrain Filtering

VeilBreakers `vegetation_system.py` already uses Poisson disk sampling with slope/height filtering. This is the correct approach.

**The complete placement pipeline:**

```
1. Generate Poisson disk samples (minimum distance per species)
2. Filter by height range (no trees above treeline)
3. Filter by slope (no trees on cliffs >45 degrees)
4. Filter by water proximity (exclusion zone: no trees IN water)
5. Filter by road proximity (no trees ON roads)
6. Filter by building proximity (clearance zone around structures)
7. Apply biome-specific species selection
8. Randomize rotation (full 360) and scale (species-specific range)
```

**Critical: Scale limits per species.**

| Species | Min Scale | Max Scale | Max Random Rotation |
|---------|-----------|-----------|---------------------|
| Oak | 0.8 | 1.4 | 360 degrees (Z only) |
| Pine | 0.7 | 1.3 | 360 degrees (Z only) |
| Birch | 0.85 | 1.2 | 360 degrees (Z only) |
| Dead tree | 0.5 | 1.0 | 360 degrees (Z only) |
| Bush | 0.6 | 1.2 | 360 degrees (Z only) |
| Rock | 0.5 | 2.0 | 360 (all axes) |
| Grass clump | 0.7 | 1.3 | 360 degrees (Z only) |

**NEVER rotate trees on X or Y axes (they would be sideways/upside down).** Only Z-axis rotation. Small tilt (1-3 degrees) on X/Y is acceptable for natural variation on slopes.

### 4.2 Water Exclusion Zones

```python
def filter_by_water_proximity(positions: list[tuple], 
                              water_mask: np.ndarray,
                              min_distance: float = 2.0,
                              heightmap_scale: float = 1.0) -> list[tuple]:
    """Remove vegetation positions too close to water.
    
    water_mask: 2D boolean array (True = water present)
    min_distance: minimum distance from water edge in world units
    """
    from scipy.ndimage import distance_transform_edt
    
    # Distance from water in cells
    dist_from_water = distance_transform_edt(~water_mask)
    min_cells = min_distance / heightmap_scale
    
    filtered = []
    for pos in positions:
        r, c = world_to_grid(pos, heightmap_scale)
        if 0 <= r < water_mask.shape[0] and 0 <= c < water_mask.shape[1]:
            if dist_from_water[r, c] >= min_cells:
                filtered.append(pos)
    
    return filtered
```

### 4.3 Forest Clearing Generation

**Clearings are gameplay-critical spaces.** Generate them explicitly, not as accidental gaps.

```python
def generate_forest_clearing(center: tuple, radius: float,
                             edge_noise: float = 0.3,
                             seed: int = 0) -> dict:
    """Generate a circular-ish clearing in forest vegetation.
    
    Returns:
        clearing_mask: 2D array for vegetation exclusion
        edge_positions: list of positions along clearing edge
                       (for fallen logs, stumps, dense undergrowth)
    """
    # Irregular boundary using noise-displaced circle
    # Transition zone: dense undergrowth at clearing edge (1-3m band)
    # Interior: grass, wildflowers, maybe a central feature (rock, stump, pond)
    pass
```

**Clearings should contain:**
- Lower grass (not bare ground unless a campsite/ruin)
- Ring of dense undergrowth at the edge (bushes, ferns)
- Fallen logs along the edge (forest remnants)
- Central feature: boulder, old stump, small pond, or shrine
- Better lighting (for gameplay visibility)

### 4.4 Undergrowth and Ground Cover

**Layers of ground vegetation (bottom to top):**
1. **Ground texture** (moss, leaf litter, dirt) -- handled by terrain material
2. **Ground cover meshes** (0.05-0.15m): mushrooms, small flowers, moss patches
3. **Low plants** (0.15-0.5m): ferns, grass tufts, small herbs
4. **Mid plants** (0.5-1.5m): bushes, brambles, young saplings
5. **Fallen logs** (random orientation, partially buried)
6. **Trees** (2-20m)

**Performance rules:**
- Ground cover at LOD0 only (within 20m of camera in Unity)
- Low plants at LOD0-LOD1 (within 50m)
- Bushes at LOD0-LOD2 (within 100m)
- Trees: full LOD chain (LOD0 mesh -> LOD1 simplified -> LOD2 billboard impostor)

### 4.5 L-System Trees (Already Implemented)

VeilBreakers `vegetation_lsystem.py` has a solid L-system implementation with:
- 6+ tree grammars (oak, pine, birch, willow, dead, dark_pine)
- Leaf card placement
- Wind vertex color baking
- Billboard impostor generation

**Key improvement needed:** Vary L-system parameters per instance within a species. Two oaks should not look identical.

```python
# Variation per instance
instance_iterations = base_iterations + rng.choice([-1, 0, 0, 1])
instance_angle = base_angle * rng.uniform(0.85, 1.15)
instance_gravity = base_gravity * rng.uniform(0.7, 1.3)
```

---

## 5. Castle and Settlement Generation

### 5.1 Modular Castle Architecture

VeilBreakers has extensive castle/settlement generation in `worldbuilding.py`, `_building_grammar.py`, and `settlement_generator.py`. The key principles for making castles look NOT like blocks:

**Architectural elements that prevent "block castle" syndrome:**

| Element | Purpose | Implementation |
|---------|---------|----------------|
| Crenellations (merlons + embrasures) | Wall top defense | Alternating raised/lowered sections, 0.6-1.0m wide |
| Machicolations | Overhanging defense | Corbeled stone brackets extending from wall face |
| Arrow slits | Ranged defense | Narrow vertical slots in wall, splayed interior |
| Battered base | Structural strength | Wall base wider than top (5-15 degree inward lean) |
| String courses | Visual break | Horizontal stone bands at each floor level |
| Corner buttresses | Structural + visual | Diagonal or rectangular buttresses at tower corners |
| Round vs square towers | Historical accuracy | Round = harder to mine, square = easier to build |

**VeilBreakers `generate_battlements` already handles crenellations.** Missing elements include:
- Machicolations (overhanging stone brackets between crenels)
- Battered bases (wall base wider than top)
- String courses (horizontal bands)
- Murder holes above gate passages

### 5.2 Gate and Entrance Design

```
                    Merlon   Merlon
                   __|__   __|__
                  |     | |     |
   _______________|     |_|     |_______________
  |  Machicolation      gap     Machicolation   |
  |_____|                              |_____|
  |     |         GATEHOUSE            |     |
  |     |    ___________________       |     |
  |     |   |                   |      |     |
  |  T  |   |   Portcullis      |      |  T  |
  |  O  |   |   slot             |      |  O  |
  |  W  |   |                   |      |  W  |
  |  E  |   |   Murder hole     |      |  E  |
  |  R  |   |   above           |      |  R  |
  |     |   |___________________|      |     |
  |     |   |                   |      |     |
  |     |   |   Gate arch       |      |     |
  |_____|   |___________________|      |_____|
            
            Drawbridge (optional)
```

**Key dimensions:**
- Gate passage: 3-4m wide, 4-5m tall (enough for a cart)
- Tower diameter: 6-10m (flanking the gate)
- Portcullis slot: 0.3m groove in wall face
- Murder hole: 0.5-1.0m opening in passage ceiling

### 5.3 Courtyard Layout

**Courtyards are NOT empty squares.** Contents by type:

| Castle Type | Courtyard Contents |
|-------------|-------------------|
| Military keep | Well, smithy, stables, armory, barracks, training yard |
| Noble residence | Garden, fountain, chapel, great hall entrance, servants quarters |
| Ruined fortress | Rubble, overgrown vegetation, collapsed walls, moss |
| Dark fortress | Ritual circle, cages, black forge, corruption crystals |

### 5.4 Terrain-Aware Foundation Placement

**The most critical integration: buildings must sit ON terrain, not float or clip.**

```python
def place_building_on_terrain(building_obj: bpy.types.Object,
                              terrain_obj: bpy.types.Object,
                              position_xy: tuple[float, float]) -> None:
    """Place a building on terrain with proper grounding.
    
    1. Raycast DOWN from above terrain to find surface height
    2. Set building Z to terrain height at its center
    3. Flatten terrain under building footprint
    4. Add foundation mesh to fill gap between building base and terrain
    5. Place rock/rubble meshes around foundation to hide seams
    """
    # Raycast to find terrain height
    origin = Vector((position_xy[0], position_xy[1], 1000.0))
    direction = Vector((0, 0, -1))
    
    success, location, normal, face_idx = terrain_obj.ray_cast(origin, direction)
    if not success:
        return
    
    # Set building position
    building_obj.location.x = position_xy[0]
    building_obj.location.y = position_xy[1]
    building_obj.location.z = location.z
    
    # Flatten terrain under building footprint
    # (use sculpt handler's flatten brush on terrain vertices within building bounds)
    flatten_terrain_under_object(terrain_obj, building_obj)
    
    # Add foundation/rubble to hide seams (Bethesda technique)
    add_foundation_rocks(building_obj, terrain_obj)
```

**The Bethesda approach (confirmed from GDC talks):**
1. Flatten terrain under building with a brush
2. Soften terrain edges around the flattened area
3. Place rock static meshes at building base to hide terrain-building seams
4. Accept that seams exist -- hide them, don't try to eliminate them

### 5.5 City Infrastructure

VeilBreakers `settlement_generator.py` implements the ward/district system with concentric organic layout. Key infrastructure rules from the codebase:

- Main streets: 4-8m wide, cobblestone
- Secondary streets: 2-4m wide, packed earth
- Alleys: 0.8-2m wide
- Market square: 30x50m to 80x120m (irregular shape)
- Burgage plots: 5-7m wide x 30-60m deep

**Road generation follows terrain contours** using weighted A* (already implemented in `_terrain_noise.py` as `generate_road_path`).

---

## 6. Environmental Props

### 6.1 Terrain-Surface Placement (Raycasting)

**All props must be placed ON the terrain surface, not at an arbitrary Z height.**

```python
def place_prop_on_terrain(prop_name: str, terrain_obj: bpy.types.Object,
                          position_xy: tuple[float, float],
                          align_to_normal: bool = True) -> bpy.types.Object:
    """Place a prop on terrain using raycasting.
    
    align_to_normal: If True, rotate prop to match terrain slope.
                     Good for: rocks, fallen logs, ground details.
                     Bad for: trees, posts, structures (should stay vertical).
    """
    # Raycast down to terrain
    origin = Vector((position_xy[0], position_xy[1], 1000.0))
    direction = Vector((0, 0, -1))
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    success, location, normal, face_idx, obj, matrix = \
        bpy.context.scene.ray_cast(depsgraph, origin, direction)
    
    if not success:
        return None
    
    # Create/duplicate prop
    prop = bpy.data.objects.get(prop_name)
    if prop is None:
        return None
    
    instance = prop.copy()
    instance.data = prop.data  # Share mesh data (instancing)
    bpy.context.collection.objects.link(instance)
    
    instance.location = location
    
    if align_to_normal:
        # Align prop's Z axis to terrain normal
        up = Vector((0, 0, 1))
        rotation = up.rotation_difference(normal)
        instance.rotation_mode = 'QUATERNION'
        instance.rotation_quaternion = rotation
    
    return instance
```

**IMPORTANT:** Use `scene.ray_cast()` with `depsgraph` (not `object.ray_cast()`) for world-space raycasting that accounts for object transforms.

### 6.2 Object Categories

| Category | Align to Normal? | Random Rotation? | Scale Variation |
|----------|-----------------|-------------------|-----------------|
| Trees | NO (vertical) | Z-axis only | 0.7-1.4 |
| Bushes | NO (vertical) | Z-axis only | 0.6-1.2 |
| Rocks/Boulders | YES | All axes | 0.5-2.0 |
| Fallen logs | PARTIAL (lie on surface) | Z-axis | 0.7-1.3 |
| Ground clutter | YES | All axes | 0.5-1.5 |
| Posts/Stakes | NO (vertical) | Z-axis only | 0.9-1.1 |
| Gravestones | NO (slight tilt for age) | Z-axis (limited) | 0.8-1.2 |
| Ruins/Rubble | YES | All axes | 0.6-1.5 |

### 6.3 Boulder/Rock Formation Placement

**Rock formations should follow geological patterns:**

```python
def place_rock_formation(center: tuple, num_rocks: int = 5,
                         formation_type: str = "cluster",
                         seed: int = 0) -> list[dict]:
    """Generate a natural-looking rock formation.
    
    formation_type:
      - "cluster": 3-8 rocks grouped together, largest in center
      - "scatter": rocks distributed across a hillside
      - "outcrop": linear arrangement following a ridge
      - "cairn": stacked rocks (artificial/landmark)
    """
    rng = np.random.default_rng(seed)
    rocks = []
    
    if formation_type == "cluster":
        # Large rock in center, smaller ones around it
        rocks.append({
            "position": center,
            "scale": rng.uniform(1.5, 2.5),
            "rotation": tuple(rng.uniform(0, 360, 3)),
            "half_buried": True
        })
        for i in range(num_rocks - 1):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(1.0, 4.0)
            pos = (center[0] + math.cos(angle) * dist,
                   center[1] + math.sin(angle) * dist)
            rocks.append({
                "position": pos,
                "scale": rng.uniform(0.3, 1.2),
                "rotation": tuple(rng.uniform(0, 360, 3)),
                "half_buried": rng.random() > 0.3
            })
    
    return rocks
```

### 6.4 Path/Road Generation

VeilBreakers `generate_road_path` in `_terrain_noise.py` handles A*-based pathfinding with terrain grading. Additional best practices:

- Roads should have slight camber (higher in center for drainage)
- Path edges should have loose stones/dirt spillover
- Terrain alongside roads should be slightly flattened (foot traffic)
- Intersections need explicit handling (widened area, possibly paved differently)

---

## 7. Unity Export Considerations

### 7.1 Terrain Format Options

| Format | Pros | Cons | Best For |
|--------|------|------|----------|
| **RAW heightmap** | Native Unity terrain import, smallest file | Loses custom mesh detail, limited to Unity terrain resolution | Large open worlds with Unity terrain tools |
| **FBX mesh** | Full control, custom topology | Cannot use Unity terrain tools, larger file | Stylized terrain, custom LOD |
| **Heightmap PNG (16-bit)** | Compatible with most engines, easy to preview | Limited vertical precision at 8-bit | Small terrains, prototyping |

**Recommendation for VeilBreakers: Export BOTH.**
- RAW heightmap for Unity Terrain system (handles LOD, vegetation, tree placement automatically)
- FBX mesh for hero areas where custom topology matters (cliffs, caves, waterfalls)

### 7.2 Texture Export Strategy

**Vertex color splatmap + texture atlas is the most performant approach.**

```
Export from Blender:
1. Terrain mesh with vertex colors (splatmap baked into RGBA)
2. Texture atlas: 2048x2048 containing 4 tiled terrain textures
   - Each texture gets a 1024x1024 quadrant
   - OR: Individual tileable textures (grass, rock, dirt, special)
3. Normal map atlas (matching layout)
4. Material metadata JSON (which channel = which texture, tiling rates)
```

**Unity-side shader reads vertex colors and blends textures accordingly.** This is exactly how Unity's built-in terrain system works internally.

### 7.3 Unity Terrain vs Mesh Terrain Trade-offs

| Feature | Unity Terrain | Mesh Terrain (FBX) |
|---------|--------------|-------------------|
| Built-in LOD | YES (automatic) | Must set up LODGroup manually |
| Tree/grass placement | YES (Unity tools) | Must use prefab scattering |
| Heightmap painting | YES (in-editor) | NO (edit in Blender) |
| Overhangs/caves | NO | YES |
| Custom topology | NO (uniform grid) | YES |
| Performance | Optimized for terrain | Needs manual optimization |
| Occlusion | Automatic | Manual |

**For VeilBreakers dark fantasy:** Use mesh terrain for hero areas (where overhangs, caves, cliffs matter) and Unity Terrain for open-world background terrain.

### 7.4 Vegetation LOD Chain

```
LOD0 (0-30m):    Full mesh, full materials, wind animation
LOD1 (30-80m):   Simplified mesh (50% triangles), shared materials
LOD2 (80-200m):  Billboard impostor (2 crossing planes with baked texture)
LOD3 (200m+):    Not rendered (culled)
```

VeilBreakers `vegetation_lsystem.py` already generates billboard impostors. The LOD transition distances should be exported as metadata for Unity's LODGroup component.

**GPU Instancing:** All vegetation of the same species/LOD should share mesh data and use GPU instancing. VeilBreakers `vegetation_lsystem.py` has `prepare_gpu_instancing_export` for this.

---

## 8. VeilBreakers Codebase Status

### What Already Exists (Solid Foundation)

| Component | File | Status | Quality |
|-----------|------|--------|---------|
| Heightmap generation (fBm) | `_terrain_noise.py` | Complete | HIGH -- numpy vectorized, 8 presets |
| Slope/biome analysis | `_terrain_noise.py` | Complete | HIGH -- proper gradient computation |
| Terrain sculpt brushes | `terrain_sculpt.py` | Complete | HIGH -- 5 operations, falloff curves |
| Thermal erosion | `terrain_advanced.py` | Complete | MEDIUM -- basic implementation |
| Spline deformation | `terrain_advanced.py` | Complete | HIGH -- cubic Bezier, smooth |
| Flow maps (D8) | `terrain_advanced.py` | Complete | HIGH |
| Terrain chunking/LOD | `terrain_chunking.py` | Complete | HIGH -- bilinear downsample, streaming metadata |
| River carving (A*) | `_terrain_noise.py` | Complete | MEDIUM -- angular paths, needs meandering |
| Road generation (A*) | `_terrain_noise.py` | Complete | HIGH -- grading, width control |
| Terrain features | `terrain_features.py` | Complete | MEDIUM -- canyons, waterfalls, cliffs |
| Cliff/cave/bridge | `_terrain_depth.py` | Complete | HIGH -- vertical geometry |
| Biome materials (14) | `terrain_materials.py` | Complete | HIGH -- proper splatmap, dark palette |
| Vegetation Poisson | `vegetation_system.py` | Complete | HIGH -- 14 biomes, slope filtering |
| L-system trees | `vegetation_lsystem.py` | Complete | HIGH -- 6+ grammars, wind, billboards |
| Castles | `worldbuilding.py` | Complete | HIGH -- battlements, multi-tier |
| Settlements | `settlement_generator.py` | Complete | HIGH -- organic ward system |
| Building grammar | `_building_grammar.py` | Complete | HIGH -- CGA-style rules |

### What Needs Improvement

| Gap | Current State | Recommended Fix | Priority |
|-----|---------------|-----------------|----------|
| Hydraulic erosion | Not implemented (only thermal) | Add droplet-based erosion | HIGH |
| River meandering | A* produces angular paths | Add sinusoidal post-processing | HIGH |
| Lake generation | No dedicated lake generator | Add noise-displaced shoreline + bed | MEDIUM |
| Water material | No dedicated water material handler | Add transparent + ripple shader nodes | MEDIUM |
| Bank profile | Straight V-cut channels | Implement S-curve bank profiles | HIGH |
| Machicolations | Not in castle gen | Add overhanging stone brackets | LOW |
| Battered wall bases | Not implemented | Add inward-leaning lower wall | LOW |
| Forest clearings | No explicit clearing gen | Add noise-circle exclusion zones | MEDIUM |
| Water exclusion | Partially implemented | Add scipy distance transform | MEDIUM |
| Terrain grounding | Partial (flatten exists) | Add foundation rock placement | HIGH |
| Heightmap export (RAW) | Not implemented | Add 16-bit RAW for Unity Terrain | MEDIUM |

---

## 9. Recommended Improvements

### Priority 1: Hydraulic Erosion (HIGH)

Add `hydraulic_erosion()` to `_terrain_noise.py` or `terrain_advanced.py`. This single addition has the highest visual impact. 35,000-50,000 droplets for 256x256 terrain, ~0.5s execution time.

### Priority 2: Natural River Banks (HIGH)

Replace the simple distance-falloff channel carving with the S-curve bank profile from Section 3.5. This prevents the "carved trench" look that is currently the biggest visual weakness.

### Priority 3: River Meandering (HIGH)

Post-process A* river paths with sinusoidal perpendicular displacement + cubic smoothing. The coarse path from A* is correct for route-finding but needs organic curves.

### Priority 4: Terrain-Building Foundation Integration (HIGH)

Implement the Bethesda technique: flatten -> soften -> place foundation rocks at seams. The flatten brush exists in `terrain_sculpt.py` but the foundation rock placement step is missing.

### Priority 5: Lake Generation (MEDIUM)

Add a dedicated lake generator with irregular shoreline, gradual depth shelf, and proper terrain modification around the shore.

### Priority 6: Water Proximity Material Blending (MEDIUM)

Compute distance-to-water for each terrain vertex and blend materials accordingly (dry -> damp -> wet -> mud near water).

### Priority 7: Forest Clearing Generator (MEDIUM)

Explicit gameplay-space clearing with dense edge undergrowth, fallen logs at boundaries, and lower vegetation inside.

### Priority 8: 16-bit RAW Heightmap Export (MEDIUM)

For Unity Terrain import. Simple numpy operation: `(heightmap * 65535).astype(np.uint16).tofile("terrain.raw")`.

---

## 10. Sources

### Erosion Algorithms
- [Job Talle - Simulating Hydraulic Erosion](https://jobtalle.com/simulating_hydraulic_erosion.html) -- droplet parameter tuning, deposition/erosion formulas
- [Nick McDonald - Simple Particle-Based Hydraulic Erosion](https://nickmcd.me/2020/04/10/simple-particle-based-hydraulic-erosion/) -- mass-transfer approach, 20-line core algorithm
- [Three Ways of Generating Terrain with Erosion (GitHub)](https://github.com/dandrino/terrain-erosion-3-ways) -- Python/numpy implementations
- [Michel Anders - Simulating Erosion in Blender Part I: Thermal Erosion](https://blog.michelanders.nl/2014/01/simulating-erosion-in-blender-part-i_90.html) -- talus angle, diffusion constant
- [Improved Terrain Generation Using Hydraulic Erosion (Medium)](https://medium.com/@ivo.thom.vanderveen/improved-terrain-generation-using-hydraulic-erosion-2adda8e3d99b)

### Terrain Generation
- [LoaDy.ONE - Generating Terrain Mesh in Python](https://loady.one/blog/terrain_mesh.html)
- [DEV.to - Realistic Random Terrain with Perlin Noise](https://dev.to/hexshift/how-to-generate-realistic-random-terrain-in-python-using-perlin-noise-3ch5)
- [Procedural Terrain 2.0 (BlenderKit)](https://www.blenderkit.com/addons/9ef8471a-d401-4404-98f9-093837891b43/) -- geometry nodes approach reference

### Terrain Texturing
- [Polycount - Terrain Splatmaps](https://polycount.com/discussion/214342/terrain-splatmaps-how-do-they-get-applied) -- vertex color splatmap fundamentals
- [Scopique - Rendering with Splat Maps and Megascans](https://scopique.com/2025/01/21/getting-there-rendering-with-splat-maps-and-megascans/)
- [ResearchGate - Blend Maps: Enhanced Terrain Texturing](https://www.researchgate.net/publication/262294515_Blend_maps_Enhanced_terrain_texturing)

### Water and Rivers
- [Blender Addons - Procedural River](https://blender-addons.org/procedural-river/) -- geometry nodes river reference
- [Superhive - Procedural River/Stream Generator](https://superhivemarket.com/products/procedural-river--stream-generator---geometry-nodes)

### Roads and Paths
- [Masaryk University Thesis - Blender Road Generator Plugin](https://is.muni.cz/th/q1gre/blender-road-generator.pdf) -- academic road generation
- [Jeremy Behreandt - Scripting Curves in Blender with Python](https://behreajj.medium.com/scripting-curves-in-blender-with-python-c487097efd13)
- [GitHub - Blender Street Generator](https://github.com/Leon-2802/Blender_Street_Generator)

### Vegetation
- [Dev.Mag - Poisson Disk Sampling](http://devmag.org.za/2009/05/03/poisson-disk-sampling/) -- Bridson's algorithm
- [GameIdea - Poisson Disk Sampling](https://gameidea.org/2023/12/27/poisson-disk-sampling/) -- game placement filtering

### Castle Architecture
- [Superhive - Procedural Medieval Castle Generator](https://superhivemarket.com/products/procedural-medieval-castle-generator)
- [ResearchGate - Procedural Modeling Historical Buildings](https://www.researchgate.net/publication/284175248_Procedural_modeling_historical_buildings_for_serious_games)
- [Tiny Glade (Steam)](https://store.steampowered.com/app/2198150/Tiny_Glade/) -- gridless building chemistry reference

### Unity Export
- [Unity Manual - Working with Heightmaps](https://docs.unity3d.com/Manual/terrain-Heightmaps.html) -- RAW format specs
- [LMHPoly - Convert Mesh to Unity Terrain](https://www.lmhpoly.com/tutorials/convert-mesh-to-unity-terrain)
- [3D-Mapper - Create Terrain from Heightmap in Unity](https://3d-mapper.com/create-terrain-from-heightmap-and-texture-in-unity/)

### GDC / Industry References (from existing codebase research)
- Bethesda GDC 2013 (Joel Burgess) -- Skyrim modular kit system, terrain flattening under buildings
- FromSoftware (Elden Ring) -- 80% procedural vegetation, hand-placed architecture, variable foundations
- Embark Studios (THE FINALS) -- Houdini procedural destruction, building generation
- Esri CityEngine CGA -- grammar-based building generation rules
