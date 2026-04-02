# AAA Terrain Sculpting Techniques -- Deep Research

Research date: 2026-04-01
Target: VeilBreakers dark fantasy procedural terrain toolkit (Blender + Python/numpy)
Games studied: Elden Ring, Skyrim, Witcher 3, Ghost of Tsushima, Horizon, RDR2, God of War Ragnarok

---

## 1. MOUNTAIN GENERATION

### 1.1 Noise Architecture (Multi-Layer fBm)

AAA mountains use 3-4 stacked noise layers, not a single fBm call:

| Layer | Purpose | Octaves | Persistence | Lacunarity | Scale | Notes |
|-------|---------|---------|-------------|------------|-------|-------|
| Base shape | Continental-scale ridges | 2-3 | 0.5 | 2.0 | 800-1600m | Low frequency, defines mountain range placement |
| Mountain body | Individual peaks | 6-8 | 0.5 | 2.0 | 100-400m | Main height contribution, use power curve (exp 1.5-2.0) |
| Detail | Rock faces, crevices | 4-6 | 0.45 | 2.2 | 10-50m | Added only above certain altitude threshold |
| Micro | Surface roughness | 2-3 | 0.35 | 2.5 | 1-5m | Vertex displacement only at close LOD |

**Current toolkit state:** `_terrain_noise.py` uses single-layer fBm with 8 octaves for mountains. This is the "smooth blob" problem.

**Fix:** Stack multiple noise calls with different seeds, combine with altitude-dependent blending:
```python
# Pseudocode for AAA mountain generation
base = fbm(x/800, y/800, octaves=3, persistence=0.5, seed=s)
mountain = fbm(x/200, y/200, octaves=7, persistence=0.5, seed=s+1)
mountain = pow(max(mountain, 0), 1.8)  # Power curve for sharp peaks
detail = fbm(x/30, y/30, octaves=5, persistence=0.45, seed=s+2)

# Altitude-dependent detail (only add detail on peaks)
altitude_mask = smoothstep(0.4, 0.7, base * 0.3 + mountain * 0.7)
height = base * 0.15 + mountain * 0.7 + detail * 0.15 * altitude_mask
```

### 1.2 Ridged Multifractal for Jagged Peaks (Elden Ring / Skyrim style)

The "Musgrave" algorithm from Texturing & Modeling: A Procedural Approach. This is what makes peaks look sharp and eroded rather than smooth.

**Algorithm (from Musgrave's original C code):**
```
RidgedMultifractal(point, H=1.0, lacunarity=2.0, octaves=8, offset=1.0, gain=2.0):
    // Precompute spectral weights
    for i in 0..octaves:
        exponents[i] = pow(lacunarity, -i * H)
    
    signal = noise(point)
    signal = offset - abs(signal)  // Create ridges from zero-crossings
    signal = signal * signal       // Square for sharpness
    result = signal
    weight = 1.0
    
    for i in 1..octaves:
        point *= lacunarity
        weight = clamp(signal * gain, 0.0, 1.0)
        signal = noise(point)
        signal = offset - abs(signal)
        signal = signal * signal
        signal *= weight  // Weight by previous octave
        result += signal * exponents[i]
    
    return result
```

**Recommended parameters for dark fantasy mountains:**
- H = 1.0 (fractal dimension, controls roughness falloff)
- Lacunarity = 2.0 (standard octave doubling)
- Octaves = 6-8 (more = more detail, diminishing returns past 8)
- Offset = 1.0 (shifts noise range to create ridges at zero-crossings)
- Gain = 2.0 (feedback intensity -- higher = rougher peaks, lower = smoother valleys)

**Peak shape control:**
- Jagged peaks (Caelid/Skellige): H=0.8, gain=2.5, offset=1.2
- Rounded peaks (Limgrave hills): H=1.2, gain=1.5, offset=0.8
- Knife-edge ridges: H=0.6, gain=3.0, offset=1.5

### 1.3 Hybrid Multifractal for Natural Variation

Musgrave's HybridMultifractal creates terrain where valleys are smooth and peaks are rough -- exactly how real geology works.

```
HybridMultifractal(point, H=0.25, lacunarity=2.0, octaves=8, offset=0.7):
    exponents[i] = pow(lacunarity, -i * H)
    
    result = (noise(point) + offset) * exponents[0]
    weight = result
    
    for i in 1..octaves:
        point *= lacunarity
        weight = clamp(weight, 0.0, 1.0)
        signal = (noise(point) + offset) * exponents[i]
        result += weight * signal
        weight *= signal  // Areas already rough get more detail
    
    return result
```

**Parameters:** H=0.25, offset=0.7. This is the single most important terrain algorithm for avoiding uniform noise texture.

### 1.4 Ridge Line Generation

Mountains need visible ridge lines connecting peaks. Two approaches:

**A) Voronoi Ridge Extraction:**
```python
# Use Worley/Voronoi F2-F1 noise for ridge lines
# F1 = distance to nearest point, F2 = distance to second nearest
ridge_value = voronoi_f2(x, y) - voronoi_f1(x, y)
# ridge_value is near 0 on ridges, high in basins
ridge_mask = 1.0 - smoothstep(0.0, 0.15, ridge_value)
height += ridge_mask * ridge_height * fbm_detail
```

**B) Gradient-Based Ridge Detection (post-process):**
After generating heightmap, compute Hessian matrix eigenvalues. Negative eigenvalues = ridge points. Use this to add additional height along detected ridges.

### 1.5 Saddle Points Between Peaks

Real mountain ranges have saddle points (passes) between peaks. Generate by:
1. Find local maxima in heightmap (peaks)
2. For each pair of adjacent peaks, find the minimum-height path between them (A* on height)
3. Slightly raise the path to create a natural col/saddle
4. Add path-aligned noise for natural variation

### 1.6 Domain Warping for Organic Shape (Critical)

**Inigo Quilez's technique** eliminates the grid-aligned artifacts that make procedural terrain look fake:

```python
# Single-level domain warp
def warped_terrain(x, y, seed):
    qx = fbm(x + 0.0, y + 0.0, seed=seed)
    qy = fbm(x + 5.2, y + 1.3, seed=seed+1)
    return fbm(x + 4.0*qx, y + 4.0*qy, seed=seed+2)

# Double-level domain warp (more organic)
def double_warped(x, y, seed):
    qx = fbm(x, y, seed=seed)
    qy = fbm(x + 5.2, y + 1.3, seed=seed+1)
    rx = fbm(x + 4.0*qx + 1.7, y + 4.0*qy + 9.2, seed=seed+2)
    ry = fbm(x + 4.0*qx + 8.3, y + 4.0*qy + 2.8, seed=seed+3)
    return fbm(x + 4.0*rx, y + 4.0*ry, seed=seed+4)
```

**Parameters:**
- Warp amplitude: 4.0 (Quilez default). Range 2.0-8.0 for terrain.
- Offset vectors: (0,0), (5.2,1.3), (1.7,9.2), (8.3,2.8) -- arbitrary but consistent
- For terrain: use warp_strength 0.3-0.6 for natural geology, 0.8-1.2 for alien/chaotic

**Current toolkit state:** `_terrain_noise.py` already has `domain_warp_array()` with configurable warp_strength and warp_scale. This is good. But it only does single-level warping.

### 1.7 Skyrim/Bethesda Heightmap System Reference

Bethesda's Creation Engine terrain specs:
- Cell size: 4096 x 4096 game units (~57m x 57m at 71.1 units/meter)
- Heightmap: 32 pixels per cell (128 game units between vertices)
- 16-bit grayscale heightmaps
- Height scaling: differences from sea level (gray=128) are doubled
- Skyrim total map: 3808 x 3008 pixels = ~119 x 94 cells
- Mountains generated externally (World Machine), not purely procedural in-engine
- Rock face detail: separate mesh objects placed on terrain, not part of heightmap

**Key insight:** Bethesda does NOT generate good-looking mountains from heightmaps alone. They place separate rock/cliff meshes over the terrain. Your toolkit should do the same.

---

## 2. CLIFF FACE SCULPTING

### 2.1 Layered Rock Strata (Horizontal Bands)

Real cliffs show horizontal bands of different rock types with differential erosion. This is the #1 thing that makes cliffs look geological vs. just "steep terrain."

**Algorithm for procedural strata:**
```python
def cliff_strata_displacement(z_normalized, seed=0):
    """Compute horizontal displacement for cliff face based on rock layers.
    
    z_normalized: 0.0 (bottom) to 1.0 (top) of cliff
    Returns: displacement amount (positive = protruding, negative = recessed)
    """
    num_layers = 8-15  # Number of rock strata bands
    layer_heights = []
    
    # Non-uniform layer thickness (real geology varies)
    rng = Random(seed)
    for i in range(num_layers):
        thickness = 0.5 + rng.random() * 1.5  # 0.5-2.0 relative units
        layer_heights.append(thickness)
    
    # Normalize to fill cliff height
    total = sum(layer_heights)
    layer_heights = [h/total for h in layer_heights]
    
    # Assign hardness per layer (harder = protrudes more)
    # Alternating hard/soft creates realistic differential erosion
    hardness = []
    for i in range(num_layers):
        if rng.random() > 0.5:
            hardness.append(0.7 + rng.random() * 0.3)  # Hard: 0.7-1.0
        else:
            hardness.append(0.1 + rng.random() * 0.3)  # Soft: 0.1-0.4
    
    # Find which layer z_normalized falls in
    cumulative = 0.0
    for i, h in enumerate(layer_heights):
        if cumulative + h > z_normalized:
            # Displacement based on hardness (hard protrudes, soft recedes)
            base_displacement = (hardness[i] - 0.5) * 2.0  # Range [-1, 1]
            
            # Add within-layer variation
            layer_pos = (z_normalized - cumulative) / h  # 0-1 within layer
            edge_fade = smoothstep(0.0, 0.1, layer_pos) * smoothstep(1.0, 0.9, layer_pos)
            
            return base_displacement * edge_fade
        cumulative += h
    
    return 0.0
```

**Visual parameters:**
- Layer count: 8-15 for a 20m cliff (typical Skellige/Elden Ring)
- Layer thickness variation: 0.3m to 3.0m per band
- Hard layer protrusion: 0.2-0.8m out from cliff face
- Soft layer recession: 0.1-0.5m into cliff face
- Add horizontal noise (Perlin, scale=5-10m) to make layers undulate slightly

### 2.2 Overhang Generation

Overhangs occur where hard rock sits above eroded soft rock. Two approaches:

**A) Displacement-based (current toolkit approach):**
The existing `generate_cliff_face()` in `terrain_features.py` uses a linear overhang starting at 70% height. This is too uniform.

**Improved approach:**
```python
# Overhang should follow strata -- only where soft layer is under hard layer
def compute_overhang(z_norm, x, layer_hardness, seed):
    for i in range(len(layer_hardness) - 1):
        if layer_hardness[i] < 0.4 and layer_hardness[i+1] > 0.6:
            # Soft under hard = overhang candidate
            layer_top_z = cumulative_height(i+1)
            overhang_depth = (layer_hardness[i+1] - layer_hardness[i]) * 1.5
            overhang_depth *= noise(x * 0.2, seed)  # Vary along cliff
            # Overhang is deeper at top of soft layer
            if layer_top_z - 0.1 < z_norm < layer_top_z + 0.05:
                return -overhang_depth  # Negative Y = overhang toward viewer
    return 0.0
```

**B) Boolean/carving approach (more geometrically accurate):**
Generate cliff as solid, then carve overhangs using noise-driven boolean subtraction. More expensive but better for close-up viewing.

### 2.3 Cliff Ledge Generation

Ledges for traversal (God of War Ragnarok style):
- Place ledges at boundaries between hard/soft strata layers
- Ledge width: 0.3-0.8m (traversable)
- Ledge depth (protrusion): 0.4-1.2m
- Spacing: every 3-5m vertically (climbable distance)
- Add slight downward slope for drainage (2-5 degrees)
- Noise-break ledges so they aren't continuous straight lines

### 2.4 Cave Mouth Placement

Cave openings on cliff faces follow geological rules:
- Place at soft strata layers (water erodes soft rock preferentially)
- Typical height: 2-4m tall, 1.5-3m wide
- Arch shape: use elliptical cross-section with noise perturbation
- Place at base of cliff or at strata boundaries
- Frequency: 1-3 per 50m of cliff face
- Add darkening/moisture gradient around entrance

### 2.5 Cliff Face Detail Meshes

Following Bethesda's approach, supplement heightmap-based cliffs with placed detail meshes:
- Rock slab meshes tilted outward at strata layers
- Loose rock clusters at cliff base (talus/scree)
- Vegetation in cracks (placement at high-curvature concave points)
- Water staining (vertex color darkening in vertical strips)
- Bird nesting ledges (small horizontal platform meshes)

---

## 3. VALLEY AND CANYON GENERATION

### 3.1 V-Shaped vs U-Shaped Valleys

**V-shaped (river-carved):**
```python
def v_valley_profile(distance_from_center, valley_width, depth):
    """Cross-section of a V-shaped river valley."""
    t = abs(distance_from_center) / (valley_width / 2.0)
    t = clamp(t, 0.0, 1.0)
    return -depth * (1.0 - t)  # Linear sides, deepest at center
```
- Narrow floor (river width), steep sides
- Typical V angle: 30-60 degrees
- Created by river downcutting in hard rock
- Use for: canyons, mountain stream valleys, Skellige fjords

**U-shaped (glacial):**
```python
def u_valley_profile(distance_from_center, valley_width, depth):
    """Cross-section of a U-shaped glacial valley."""
    t = abs(distance_from_center) / (valley_width / 2.0)
    t = clamp(t, 0.0, 1.0)
    # Parabolic: flat bottom, steep sides
    return -depth * (1.0 - t * t)
```
- Wide flat floor, steep curved walls
- Floor width: 30-50% of total valley width
- Created by glaciers
- Use for: Skyrim-style mountain valleys, Toussaint vineyards on valley floors

### 3.2 Hydraulic Erosion for Canyon Carving

**Current toolkit state:** `_terrain_erosion.py` has a solid droplet-based erosion implementation with correct parameters.

**Recommended parameter ranges for different canyon types:**

| Canyon Type | Iterations | Erosion Rate | Deposition | Capacity | Evap | Inertia | Max Life |
|-------------|-----------|-------------|------------|----------|------|---------|----------|
| Narrow slot canyon | 200K | 0.4 | 0.1 | 8.0 | 0.005 | 0.03 | 64 |
| Wide river canyon | 100K | 0.3 | 0.3 | 4.0 | 0.01 | 0.05 | 30 |
| Gentle valley | 50K | 0.2 | 0.4 | 2.0 | 0.02 | 0.1 | 20 |
| Desert wash | 150K | 0.35 | 0.2 | 6.0 | 0.03 | 0.04 | 40 |
| Dark fantasy abyss | 300K | 0.5 | 0.05 | 10.0 | 0.003 | 0.02 | 80 |

**Key insight:** High capacity + low deposition + low evaporation = deep narrow canyons. Low capacity + high deposition = wide shallow valleys.

### 3.3 Canyon Wall Detail (Layered Sedimentary Look)

Apply the strata system from Section 2.1 to canyon walls. Additional techniques:

**Horizontal banding via step function:**
```python
def canyon_step_height(raw_height, num_steps=8, step_sharpness=0.8):
    """Quantize height into steps for layered sedimentary look."""
    stepped = floor(raw_height * num_steps) / num_steps
    # Blend between smooth and stepped
    return lerp(raw_height, stepped, step_sharpness)
```
This is already partially in the toolkit as `post_process="step"` with `step_count=5`. Increase to 8-12 steps for geological realism.

**Color banding:** Alternate warm (sandstone: 0.18, 0.12, 0.08) and cool (shale: 0.08, 0.08, 0.10) tones per layer.

### 3.4 Valley Floor Detail

- Alluvial fan deposits: scatter flat rock meshes at canyon mouths
- River stones: small rounded mesh instances along water path
- Sediment layers: vertex color gradient from dark (wet center) to light (dry edges)
- Flood debris: log/branch meshes at high-water marks on canyon walls
- Width variation: narrow sections (2-5m) alternating with wide pools (10-20m)

---

## 4. RIVER SYSTEMS

### 4.1 River Path Generation

**A) A* Path on Heightmap (current toolkit approach):**
`_terrain_noise.py` has `carve_river_path()` using A* which is correct for single rivers. For river networks, use drainage basin approach.

**B) Drainage Basin (Red Blob Games approach):**
1. Start from ocean/lake boundary triangles
2. BFS/Dijkstra hybrid grows drainage basins inward and uphill
3. Each cell gets assigned to one basin with one downstream neighbor
4. River hierarchy via Strahler numbers:
   - Source streams: order 1
   - Two order-1 streams merge: order 2
   - Two order-N streams merge: order N+1
   - Order N meets order M (M>N): stays order M
5. River width proportional to Strahler number: `width = base_width * strahler_number^0.5`

### 4.2 Meander Generation

Real rivers meander on flat terrain. Sinuosity = path length / straight-line distance.

**Parameters by terrain type:**
- Mountain stream: sinuosity 1.0-1.1 (nearly straight, steep gradient)
- Hill river: sinuosity 1.1-1.3 (gentle curves)
- Plains river: sinuosity 1.3-2.0 (pronounced meanders)
- Swamp/delta: sinuosity 1.5-3.0+ (extreme meandering)

**Algorithm for meander curves:**
```python
def generate_meander_path(start, end, sinuosity=1.5, seed=0):
    """Generate a meandering river path between two points.
    
    Uses sine-based oscillation with noise perturbation.
    """
    straight_dist = distance(start, end)
    direction = normalize(end - start)
    perpendicular = rotate_90(direction)
    
    num_points = int(straight_dist / 2.0)  # Point every 2 units
    amplitude = straight_dist * (sinuosity - 1.0) * 0.3
    wavelength = straight_dist / (2 + sinuosity * 2)  # More sinuous = more bends
    
    points = []
    gen = noise_generator(seed)
    for i in range(num_points):
        t = i / (num_points - 1)
        pos_along = lerp(start, end, t)
        
        # Sine-based meander with noise perturbation
        phase = t * straight_dist / wavelength * 2 * pi
        noise_offset = gen.noise2(t * 3.0, seed * 0.1) * 0.4
        lateral = sin(phase + noise_offset) * amplitude
        lateral *= smoothstep(0.0, 0.15, t) * smoothstep(1.0, 0.85, t)  # Taper at ends
        
        points.append(pos_along + perpendicular * lateral)
    
    return points
```

### 4.3 River Width Variation

Width should vary based on:
- Gradient: narrow in steep sections, wide in flat sections
  `width_factor = 1.0 / (1.0 + slope * 5.0)`
- Confluence: width increases at tributary junctions
  `width_after = sqrt(width_main^2 + width_tributary^2)`
- Canyon constraint: capped by canyon floor width
- Typical ranges: 2-5m in mountains, 10-30m in valleys, 50-200m in plains

### 4.4 Rapids and Waterfalls

Place rapids where elevation gradient exceeds threshold:
```python
# For each river segment:
gradient = (height[i] - height[i+1]) / segment_length
if gradient > 0.15:      # Waterfall (>15% grade)
    place_waterfall_mesh(position, height_drop)
elif gradient > 0.05:    # Rapids (5-15% grade)
    place_rapids_particles(position, width)
    scatter_exposed_rocks(position, count=int(gradient * 50))
elif gradient > 0.02:    # Riffles (2-5% grade)
    add_surface_turbulence(position)
```

### 4.5 River Confluence (Tributary Merging)

Where two rivers meet:
- The tributary enters at 30-60 degree angle to main channel
- A sediment bar (point bar) forms at the inside of the junction
- Water deepens at the outside of the junction (scour pool)
- Combined width: approximately `sqrt(w1^2 + w2^2)` (not simply additive)
- Mesh: create a triangular transition zone between the three channels

### 4.6 Oxbow Lakes

Generated from extremely sinuous meanders:
```python
def check_oxbow_formation(meander_points, min_neck_width=3.0):
    """Detect where a meander loop nearly pinches off."""
    for i in range(len(meander_points)):
        for j in range(i + 5, len(meander_points)):  # Skip nearby points
            dist = distance(meander_points[i], meander_points[j])
            if dist < min_neck_width:
                # Oxbow candidate: shortcut the river, leave old loop as lake
                return {
                    'cutoff_start': i,
                    'cutoff_end': j,
                    'lake_points': meander_points[i:j+1],
                    'new_path': meander_points[:i] + meander_points[j:]
                }
    return None
```

### 4.7 Blender Mesh Generation for Rivers

```python
# Generate river as mesh strip following path
def create_river_mesh(path_points, widths):
    vertices = []
    faces = []
    for i, (point, width) in enumerate(zip(path_points, widths)):
        if i == 0:
            forward = normalize(path_points[1] - point)
        elif i == len(path_points) - 1:
            forward = normalize(point - path_points[-2])
        else:
            forward = normalize(path_points[i+1] - path_points[i-1])
        
        right = cross(forward, UP) * width * 0.5
        
        # Left and right bank vertices
        vertices.append(point - right)  # Left bank
        vertices.append(point)          # Center (slightly lower for depth)
        vertices.append(point + right)  # Right bank
        
        # Vertex Z: center is lower (river bed)
        vertices[-2] = (vertices[-2][0], vertices[-2][1], vertices[-2][2] - width * 0.15)
    
    # Create quad faces between segments
    for i in range(len(path_points) - 1):
        base = i * 3
        # Two quads per segment (left half, right half)
        faces.append((base, base+1, base+4, base+3))
        faces.append((base+1, base+2, base+5, base+4))
    
    return vertices, faces
```

---

## 5. TERRAIN MICRO-DETAIL

### 5.1 Embedded Rocks

Scatter rocks that are partially buried in terrain (not sitting on top):

**Placement rules:**
- Density: 2-8 per 10m^2 on slopes > 15 degrees
- Density: 0-2 per 10m^2 on flat terrain
- Size: 0.1-0.5m (small), 0.5-2.0m (medium), 2.0-5.0m (large)
- Distribution: 70% small, 25% medium, 5% large (power law)
- Burial depth: 30-70% of rock height below terrain surface
- Orientation: tilt downslope by 10-30 degrees
- Clustering: use Poisson disk sampling with variable radius

```python
def embed_rock_in_terrain(rock_position, rock_radius, terrain_heightmap):
    """Sink rock into terrain and blend edges."""
    burial_fraction = 0.3 + random() * 0.4  # 30-70% buried
    rock_z = terrain_height_at(rock_position) - rock_radius * burial_fraction
    
    # Raise terrain slightly around rock base (soil accumulation)
    for nearby_vertex in terrain_vertices_within(rock_position, rock_radius * 1.5):
        dist = distance_2d(nearby_vertex, rock_position)
        blend = smoothstep(rock_radius * 1.5, rock_radius * 0.8, dist)
        nearby_vertex.z += rock_radius * 0.1 * blend  # Slight mound
```

### 5.2 Root Systems Near Trees

- Spawn 3-8 root meshes per tree, radiating outward
- Root length: 1-4m from trunk
- Root height above ground: 0.05-0.15m (subtle ridges)
- Apply as terrain displacement in a radial pattern
- Root thickness tapers from 0.1m at trunk to 0.02m at tip
- Raise terrain slightly along root path

### 5.3 Worn Dirt Paths

Paths form where entities walk repeatedly:

```python
def generate_worn_path(path_points, width=1.0, depth=0.05):
    """Depress terrain along a path and remove grass."""
    for point in path_points:
        for vertex in terrain_vertices_within(point, width):
            dist = distance_2d(vertex, point) / width
            # Depression profile: deeper in center
            depression = depth * (1.0 - dist * dist)
            vertex.z -= depression
            
            # Set vertex color to dirt (for splatmap)
            dirt_weight = smoothstep(width, width * 0.3, distance_2d(vertex, point))
            vertex.color = lerp(vertex.color, DIRT_COLOR, dirt_weight)
```

**Path width by type:**
- Animal trail: 0.3-0.5m, depth 0.02-0.03m
- Foot path: 0.6-1.0m, depth 0.03-0.05m
- Cart track: 1.5-2.5m, depth 0.05-0.10m, with two rut lines

### 5.4 Puddles in Low Areas

Detect depressions in terrain and fill with water:

```python
def find_puddle_locations(heightmap, min_depth=0.02, min_area=0.5):
    """Find local minima that collect water."""
    puddles = []
    # Compute "filled" heightmap (fill all depressions to their spill point)
    filled = priority_flood_fill(heightmap)
    depth_map = filled - heightmap
    
    # Puddles are where depth > threshold
    puddle_mask = depth_map > min_depth
    # Connected components = individual puddles
    labels = connected_components(puddle_mask)
    
    for label_id in unique(labels):
        area = count(labels == label_id) * cell_area
        if area > min_area:
            center = centroid(where(labels == label_id))
            max_depth = max(depth_map[labels == label_id])
            puddles.append({'center': center, 'area': area, 'depth': max_depth})
    
    return puddles
```

### 5.5 Erosion Channels on Slopes

Small rivulets that form on slopes during rain:

- Generate on slopes > 20 degrees
- Width: 0.05-0.2m, depth: 0.02-0.08m
- Follow steepest descent from random start points above the slope
- Branch probability: 15-25% at each step
- Converge into larger channels downslope
- Implemented as vertex displacement along computed flow paths

### 5.6 Stamp/Detail Maps (Witcher 3 / Ghost of Tsushima approach)

Pre-authored detail heightmaps stamped onto terrain at random positions:

```python
# Library of detail stamps (16x16 to 64x64 pixel heightmaps)
STAMP_LIBRARY = {
    'rock_cluster': load_stamp('rock_cluster_64.png'),      # Embedded rocks
    'tree_root_mound': load_stamp('root_mound_32.png'),     # Tree base
    'erosion_gully': load_stamp('gully_64x16.png'),         # Narrow erosion
    'animal_burrow': load_stamp('burrow_16.png'),           # Small hole
    'fallen_log_impression': load_stamp('log_32x8.png'),    # Decomposed log
}

def apply_stamps(heightmap, stamp_type, count, seed):
    rng = Random(seed)
    stamp = STAMP_LIBRARY[stamp_type]
    for _ in range(count):
        x = rng.randint(0, heightmap.width - stamp.width)
        y = rng.randint(0, heightmap.height - stamp.height)
        angle = rng.random() * 360
        scale = 0.7 + rng.random() * 0.6  # 70-130% size variation
        rotated = rotate_stamp(stamp, angle)
        scaled = resize_stamp(rotated, scale)
        blend_stamp(heightmap, scaled, x, y, strength=0.3 + rng.random() * 0.4)
```

---

## 6. TERRAIN PAINTING / SPLATTING AUTOMATION

### 6.1 Rule-Based Auto-Painting System

**Complete rule set for dark fantasy terrain:**

```python
SPLATMAP_RULES = [
    # Each rule: (texture_name, conditions, weight_function)
    
    # Layer 0: Cliff rock (steep surfaces)
    {
        'texture': 'dark_rock',
        'color': (0.10, 0.09, 0.08, 1.0),
        'condition': 'slope > 45',
        'weight': 'smoothstep(35, 55, slope)',
        'roughness': 0.88,
    },
    
    # Layer 1: Gravel/scree (moderate slope, any height)
    {
        'texture': 'gravel',
        'color': (0.12, 0.10, 0.08, 1.0),
        'condition': '25 < slope < 55',
        'weight': 'bell_curve(slope, center=40, width=15) * 0.7',
        'roughness': 0.92,
    },
    
    # Layer 2: Dead grass (gentle slopes, mid altitude)
    {
        'texture': 'dead_grass',
        'color': (0.04, 0.06, 0.02, 1.0),
        'condition': 'slope < 35 and 0.2 < altitude < 0.7',
        'weight': '(1.0 - smoothstep(25, 40, slope)) * bell_curve(altitude, 0.45, 0.25)',
        'roughness': 0.95,
    },
    
    # Layer 3: Mud (low areas, low slope)
    {
        'texture': 'dark_mud',
        'color': (0.06, 0.04, 0.03, 1.0),
        'condition': 'altitude < 0.25 and slope < 20',
        'weight': 'smoothstep(0.3, 0.1, altitude) * smoothstep(25, 10, slope)',
        'roughness': 0.95,
    },
    
    # Layer 4: Snow/ash (high altitude, low slope)
    {
        'texture': 'ash_snow',
        'color': (0.06, 0.08, 0.03, 1.0),
        'condition': 'altitude > 0.75 and slope < 40',
        'weight': 'smoothstep(0.65, 0.85, altitude) * (1.0 - smoothstep(30, 50, slope))',
        'roughness': 0.92,
    },
    
    # Layer 5: Wet rock (near water, any slope)
    {
        'texture': 'wet_rock',
        'color': (0.05, 0.05, 0.06, 1.0),
        'condition': 'moisture > 0.7',
        'weight': 'smoothstep(0.5, 0.9, moisture)',
        'roughness': 0.4,  # Wet = smooth/reflective
    },
    
    # Layer 6: Path dirt (on paths, vertex-painted)
    {
        'texture': 'path_dirt',
        'color': (0.08, 0.06, 0.04, 1.0),
        'condition': 'path_mask > 0.3',
        'weight': 'path_mask',
        'roughness': 0.85,
    },
    
    # Layer 7: Corruption (dark fantasy overlay)
    {
        'texture': 'corruption',
        'color': (0.02, 0.01, 0.02, 1.0),
        'condition': 'corruption_mask > 0.0',
        'weight': 'corruption_mask * smoothstep(25, 5, slope)',
        'roughness': 0.7,
    },
]
```

### 6.2 Input Maps for Splatting

Compute these maps from the heightmap:

```python
def compute_splatmap_inputs(heightmap):
    """Compute all input maps needed for auto-painting."""
    
    # 1. Altitude (normalized 0-1)
    altitude = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min())
    
    # 2. Slope (degrees, from gradient)
    gy, gx = np.gradient(heightmap)
    slope_rad = np.arctan(np.sqrt(gx**2 + gy**2))
    slope_deg = np.degrees(slope_rad)
    
    # 3. Curvature (Laplacian of heightmap)
    # Positive = convex (ridge/peak), Negative = concave (valley/depression)
    curvature = laplacian(heightmap)
    
    # 4. Aspect (compass direction the slope faces, 0-360)
    aspect = np.degrees(np.arctan2(-gx, -gy)) % 360
    
    # 5. Moisture (flow accumulation -- where water collects)
    # Simple: invert altitude and blur, or use full flow accumulation
    moisture = gaussian_blur(1.0 - altitude, sigma=5)
    # Add concavity contribution
    moisture += np.clip(-curvature * 10, 0, 1) * 0.5
    moisture = np.clip(moisture, 0, 1)
    
    # 6. Occlusion (ambient occlusion from heightmap -- sheltered areas)
    # Higher = more exposed, lower = more sheltered
    occlusion = compute_horizon_occlusion(heightmap, num_directions=8)
    
    return {
        'altitude': altitude,
        'slope': slope_deg,
        'curvature': curvature,
        'aspect': aspect,
        'moisture': moisture,
        'occlusion': occlusion,
    }
```

### 6.3 Slope Thresholds (Industry Standard)

Based on Witcher 3 and Ghost Recon Wildlands pipelines:

| Slope Range | Texture | Notes |
|-------------|---------|-------|
| 0-15 deg | Grass/ground cover | Full coverage, blends to dirt at edges |
| 15-35 deg | Mixed grass + gravel | Transition zone, 50/50 at 25 deg |
| 35-55 deg | Gravel + rock | Rock increases with slope |
| 55-75 deg | Rock face | Full rock, add strata detail |
| 75-90 deg | Cliff rock | Vertical/near-vertical, darkest rock |

### 6.4 Height-Based Blending (Texture Priority)

Instead of simple alpha blending, use height-based blending for natural transitions:

```python
def height_blend(texture_a_height, texture_b_height, blend_factor, blend_depth=0.2):
    """Height-based texture blending for natural transitions.
    
    texture_a_height, texture_b_height: per-pixel height from texture heightmap
    blend_factor: 0.0 = all A, 1.0 = all B (from splatmap)
    blend_depth: transition sharpness (smaller = sharper)
    """
    ha = texture_a_height + (1.0 - blend_factor)
    hb = texture_b_height + blend_factor
    
    max_h = max(ha, hb)
    threshold = max_h - blend_depth
    
    wa = max(ha - threshold, 0.0)
    wb = max(hb - threshold, 0.0)
    total = wa + wb
    
    if total > 0:
        return wb / total  # Weight for texture B
    return blend_factor
```

This prevents the "vaseline smear" look of linear blending. Grass grows between rocks rather than fading through them. The toolkit already has `height_blend()` in `terrain_materials.py` -- make sure it's wired into the auto-painting pipeline.

### 6.5 Curvature-Based Rules

- Convex ridges (curvature > threshold): exposed rock, lighter color, more erosion
- Concave valleys (curvature < -threshold): moisture accumulation, darker, moss/lichen
- Flat areas (curvature ~0): ground cover (grass, dirt)

```python
# Curvature contribution to moisture
moisture_from_curvature = np.clip(-curvature * 10.0, 0.0, 1.0)
# Curvature contribution to rock exposure
rock_from_curvature = np.clip(curvature * 5.0, 0.0, 1.0)
```

### 6.6 Ghost Recon Wildlands Pipeline Reference

Ubisoft's approach for 11 ecosystems:
- Houdini procedural tools scatter rocks using: terrain materials, curvature, slope alignment, cliff detection, road detection
- All decals have puddle masks for weather integration
- Landscape pipeline: heightmap -> material layers -> scattering rules -> GPU-interpreted bytecode
- Key lesson: rules are per-biome, not global. A "swamp" biome has completely different slope/texture mappings than a "mountain" biome.

---

## 7. IMPLEMENTATION PRIORITIES FOR VEILBREAKERS TOOLKIT

### 7.1 What the Toolkit Already Has (Solid Foundation)
- `_terrain_noise.py`: fBm with 8 presets, domain warping, biome rules, A* river carving
- `_terrain_erosion.py`: Hydraulic + thermal erosion with correct parameters
- `terrain_features.py`: Canyon, cliff face, swamp, waterfall, etc. generators
- `terrain_materials.py`: Biome material system, slope-based assignment, height blending
- `terrain_sculpt.py`: Brush-based sculpting (raise, lower, smooth, flatten, stamp)

### 7.2 Critical Gaps to Address

1. **Multi-layer noise stacking** -- Current mountains use single fBm. Need layered approach (base + mountain + detail) with altitude-dependent blending.

2. **Ridged Multifractal** -- Not implemented. This is the #1 improvement for mountain quality. Add `ridged_multifractal()` and `hybrid_multifractal()` to `_terrain_noise.py`.

3. **Rock strata for cliffs** -- Current cliff face generator uses simple noise. Need horizontal banding with differential erosion (hardness per layer).

4. **Double domain warping** -- Current warping is single-level. Add Quilez-style double warp option.

5. **River network generation** -- Current system does single A* paths. Need drainage basin approach for realistic river networks with Strahler numbering.

6. **Meander generation** -- No sinuosity control currently. Add sine-based meander with noise perturbation.

7. **Splatmap input maps** -- Curvature and moisture maps not computed. Add `compute_splatmap_inputs()` function.

8. **Micro-detail placement** -- No embedded rock, root system, worn path, or puddle detection. Add these as scatter/displacement operations.

9. **Stamp/detail map system** -- No stamp library. Add pre-authored detail heightmaps for variety.

### 7.3 Suggested Implementation Order

1. Ridged Multifractal + Hybrid Multifractal in `_terrain_noise.py` (highest impact)
2. Multi-layer noise stacking with altitude-dependent blending
3. Double domain warping
4. Rock strata system for cliff faces
5. Splatmap input computation (curvature, moisture, occlusion)
6. River network with drainage basins and meander
7. Micro-detail (embedded rocks, paths, puddles, erosion channels)
8. Stamp/detail map system

---

## SOURCES

- [Noise for Terrains - Learn Procedural Generation](https://aparis69.github.io/LearnProceduralGeneration/terrain/procedural/noise_for_terrains/)
- [Perlin Noise Comprehensive Guide](https://www.jdhwilkins.com/mountains-cliffs-and-caves-a-comprehensive-guide-to-using-perlin-noise-for-procedural-generation)
- [Musgrave Terrain Algorithms (Purdue)](https://engineering.purdue.edu/~ebertd/texture/1stEdition/musgrave/musgrave.c)
- [Inigo Quilez - Domain Warping](https://iquilezles.org/articles/warp/)
- [Sebastian Lague - Hydraulic Erosion](https://sebastian.itch.io/hydraulic-erosion)
- [Simple Particle-Based Hydraulic Erosion (Nick McDonald)](https://nickmcd.me/2020/04/10/simple-particle-based-hydraulic-erosion/)
- [Procedural River Drainage Basins (Red Blob Games)](https://www.redblobgames.com/x/1723-procedural-river-growing/)
- [Procedural Hydrology (Nick McDonald)](https://nickmcd.me/2020/04/15/procedural-hydrology/)
- [Procedural Terrain Splatmapping (Alastair Aitchison)](https://alastaira.wordpress.com/2013/11/14/procedural-terrain-splatmapping/)
- [Witcher 3 Landscape Creation GDC 2014](https://gdcvault.com/play/1020197/Landscape-Creation-and-Rendering-in)
- [Ghost of Tsushima GDC - Samurai Landscapes](https://gdcvault.com/play/1027352/Samurai-Landscapes-Building-and-Rendering)
- [Skyrim Heightmap to Worldspace](https://hoddminir.blogspot.com/2012/02/from-heightmap-to-worldspace-in-skyrim.html)
- [Ghost Recon Wildlands Landscape Pipeline (80.lv)](https://80.lv/articles/landscape-and-material-pipeline-of-ghost-recon-wildlands)
- [Advanced Terrain Texture Splatting (Gamedeveloper)](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting)
- [FastNoiseLite - Ridged Multi](https://github.com/Auburn/FastNoiseLite/issues/26)
- [Blender Musgrave Texture](https://docs.blender.org/manual/en/latest/render/materials/legacy_textures/types/musgrave.html)
- [Authoring and Simulating Meandering Rivers (ACM)](https://dl.acm.org/doi/10.1145/3618350)
- [Geological Strata and Cliff Profiles](https://geographyrevisionalevel.weebly.com/2b2c-geological-structure-and-cliff-profiles.html)
- [God of War Ragnarok Sculpts (ArtStation)](https://www.artstation.com/artwork/qQqeyR)
- [NVIDIA GPU Gems 3 - Procedural Terrains](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1-generating-complex-procedural-terrains-using-gpu)
