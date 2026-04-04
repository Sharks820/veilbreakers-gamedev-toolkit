# Boulder, Rock Formation & Rocks-in-Water: Procedural Generation Reference

**Researched:** 2026-04-03
**Domain:** Procedural rock/boulder generation in Blender Python for dark fantasy game assets
**Target:** VeilBreakers `procedural_meshes.py` rock generators, environment scatter, terrain features
**Confidence:** HIGH (cross-referenced Blender API docs, AAA environment art practices, shipped addon algorithms)

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Boulder Geometry Generation](#2-boulder-geometry-generation)
3. [Rock Type Catalog](#3-rock-type-catalog)
4. [Surface Detail Techniques](#4-surface-detail-techniques)
5. [Rock Formation Arrangements](#5-rock-formation-arrangements)
6. [Rocks in Water](#6-rocks-in-water)
7. [Rock Materials for Dark Fantasy](#7-rock-materials-for-dark-fantasy)
8. [Procedural Generation in Blender Python](#8-procedural-generation-in-blender-python)
9. [Rock Placement Rules](#9-rock-placement-rules)
10. [Poly Budget & LOD Strategy](#10-poly-budget--lod-strategy)
11. [Implementation Recommendations](#11-implementation-recommendations)
12. [Sources](#12-sources)

---

## 1. Current State Assessment

### What Exists Now

The current `generate_rock_mesh()` in `procedural_meshes.py` supports four rock types:

| Type | Technique | Problem |
|------|-----------|---------|
| `boulder` | `_make_faceted_rock_shell()` — ring/segment grid with ridge multipliers | Too uniform, single noise layer, all boulders look similar |
| `cliff_outcrop` | Stacked beveled boxes with random offsets | Good layering concept but boxy, lacks erosion |
| `standing_stone` | Lathe profile with noise on radius | Decent but rotationally symmetric |
| `crystal` | Hexagonal tapered cylinders | Acceptable for crystals |
| `rubble_pile` | Small random beveled boxes | Too clean, needs fracture aesthetics |

### Critical Gaps

1. **No seed parameter** on `generate_rock_mesh()` -- uses hardcoded seeds (1701, 9127, 77, 99, 55), making every boulder identical
2. **No size variation within type** -- a "boulder" always has the same proportions
3. **No river stones, shale, or rounded types** -- only angular/faceted
4. **No partial burial support** -- rocks float on terrain surface
5. **No wet/dry material zones** -- single material per rock
6. **No moss/lichen placement** -- no vertex color or UV-based moss masking
7. **No rock-in-water positioning** -- no waterline awareness
8. **Scatter engine** has power-law size distribution (70/25/5%) but only spawns the same boulder mesh

---

## 2. Boulder Geometry Generation

### The Problem with Icosphere + Displacement

The naive approach (icosphere -> subdivide -> displace along normals with noise) produces recognizable "displaced sphere" shapes. Every game artist knows this look. It fails because:

- Icosphere poles create visible convergence artifacts
- Single displacement pass creates uniform roughness without geological character
- No flat faces or planar breaks that real rocks have
- No asymmetry -- real boulders are NOT roughly spherical

### Recommended: Multi-Pass Deformation Pipeline

Use this pipeline order, which mirrors the proven Stylized Rock Generator approach adapted for bmesh/Python:

```
Step 1: Base Shape (NOT a sphere)
  -> Irregular convex hull from scattered points
  -> OR scaled/sheared cube with random face insets

Step 2: Primary Massing (large-scale shape)
  -> Multi-fractal displacement, 2-3 octaves, high amplitude
  -> Asymmetric scaling (stretch one axis 1.2-1.8x)

Step 3: Secondary Features (medium detail)
  -> Voronoi-based faceting (creates flat planes and ridges)
  -> Ridge/valley carving via directional noise

Step 4: Surface Detail (fine detail)
  -> High-frequency noise displacement, low amplitude
  -> Crack pattern via Voronoi distance subtraction

Step 5: Geometry Cleanup
  -> Decimate to target poly count
  -> Smooth pass (limited, 0.3-0.5 factor, 2-3 iterations)
  -> Recalculate normals
```

### Base Shape: Convex Hull from Random Points

Instead of starting with an icosphere, scatter 12-20 random points in an ellipsoidal volume and build a convex hull. This creates natural-looking planar faces and irregular massing from the start.

```python
import bmesh
import mathutils
from mathutils import Vector, noise

def _generate_rock_base(seed: int, size: float, 
                        aspect_x: float = 1.0,
                        aspect_y: float = 0.7,
                        aspect_z: float = 0.9,
                        num_points: int = 16) -> bmesh.types.BMesh:
    """Create irregular rock base via convex hull of random points."""
    import random
    rng = random.Random(seed)
    
    bm = bmesh.new()
    
    # Scatter points in ellipsoidal volume
    for _ in range(num_points):
        # Use rejection sampling for roughly ellipsoidal distribution
        while True:
            x = rng.uniform(-1, 1)
            y = rng.uniform(-1, 1)
            z = rng.uniform(-1, 1)
            if x*x + y*y + z*z <= 1.0:
                break
        
        # Apply aspect ratios and size
        bm.verts.new((
            x * size * aspect_x,
            y * size * aspect_y,
            z * size * aspect_z,
        ))
    
    bm.verts.ensure_lookup_table()
    bmesh.ops.convex_hull(bm, input=bm.verts)
    
    return bm
```

### Multi-Octave Displacement Along Normals

After creating the base shape, subdivide and displace using `mathutils.noise`:

```python
def _displace_rock_surface(bm: bmesh.types.BMesh, seed: int,
                           octaves: int = 4,
                           amplitude: float = 0.15,
                           lacunarity: float = 2.0,
                           persistence: float = 0.5) -> None:
    """Apply multi-octave fractal displacement along vertex normals."""
    from mathutils.noise import noise_vector, multi_fractal
    
    offset = Vector((seed * 13.37, seed * 7.13, seed * 3.71))
    
    for v in bm.verts:
        # Sample multi-fractal noise at vertex position
        sample_pos = v.co + offset
        
        # Layer multiple noise octaves
        displacement = 0.0
        amp = amplitude
        freq = 1.0
        for _ in range(octaves):
            n = multi_fractal(
                sample_pos * freq,
                H=1.0,
                lacunarity=lacunarity,
                octaves=1,
                noise_basis='PERLIN_NEW'
            )
            displacement += (n - 1.0) * amp  # multi_fractal centers around 1.0
            amp *= persistence
            freq *= lacunarity
        
        # Displace along normal
        v.co += v.normal * displacement
```

### Voronoi Faceting for Angular Rocks

Real rocks have flat faces where they fractured along crystal planes. Use Voronoi noise to create these:

```python
def _apply_voronoi_faceting(bm: bmesh.types.BMesh, seed: int,
                            strength: float = 0.08,
                            scale: float = 3.0) -> None:
    """Create flat faceted planes using Voronoi distance."""
    from mathutils.noise import noise as blender_noise
    
    offset = Vector((seed * 2.71, seed * 1.41, seed * 4.23))
    
    for v in bm.verts:
        # Use Voronoi F1 for cell distance
        sample = (v.co + offset) * scale
        # VORONOI_F1 gives distance to nearest cell center
        d = blender_noise(sample, noise_basis='VORONOI_F1')
        # Push vertices toward cell centers (flattening)
        v.co += v.normal * d * strength
```

---

## 3. Rock Type Catalog

### Type Definitions with Shape Parameters

| Rock Type | Aspect Ratio (X:Y:Z) | Base Points | Subdiv | Displacement | Target Tris | Visual Character |
|-----------|----------------------|-------------|--------|--------------|-------------|------------------|
| **River Stone** | 1.0 : 0.5 : 0.8 | 12-14 | 2-3 | Low (0.05), smooth | 150-300 | Rounded, water-worn, flat base |
| **Cobblestone** | 1.0 : 0.7 : 0.9 | 10-12 | 1-2 | Low (0.06) | 80-200 | Rounded, slightly irregular |
| **Angular Boulder** | 1.0 : 0.8 : 1.1 | 14-18 | 2-3 | Med (0.12), faceted | 300-600 | Sharp edges, flat faces, fractured |
| **Granite Boulder** | 1.2 : 0.7 : 1.0 | 16-20 | 2-3 | Med (0.15) | 400-800 | Massive, irregular, some rounded edges |
| **Flat Shale** | 1.5 : 0.15 : 1.2 | 8-10 | 1-2 | Very low (0.02) | 60-150 | Thin, flat, layered, can stack |
| **Cliff Debris** | 1.0 : 1.3 : 0.8 | 12-16 | 2 | High (0.20), angular | 200-500 | Tall, sharp, recently broken |
| **Massive Rock** | 1.3 : 0.9 : 1.1 | 20-24 | 3 | Med-high (0.18) | 500-800 | Weathered, partially buried, moss zones |
| **Standing Stone** | 0.4 : 2.0 : 0.35 | 10-14 | 2 | Low (0.08) | 200-400 | Tall, tapered, rough-hewn |
| **Rubble Chunk** | 1.0 : 0.6 : 0.9 | 8-10 | 1 | High (0.15), sharp | 40-120 | Small, jagged, debris |
| **Stepping Stone** | 1.2 : 0.3 : 1.0 | 8-10 | 1-2 | Low (0.03), flat top | 60-150 | Flat-topped, water-worn sides |

### Size Classes

| Class | Scale Range | Use Case | Typical Count per 100m2 |
|-------|-------------|----------|------------------------|
| Pebble | 0.03-0.08m | Ground scatter, riverbed | 50-200 (instanced) |
| Cobble | 0.08-0.25m | Path edges, stream beds | 20-50 |
| Stone | 0.25-0.5m | Forest floor, wall bases | 5-15 |
| Boulder | 0.5-2.0m | Terrain features, cover | 2-5 |
| Massive | 2.0-5.0m | Landmarks, outcrops | 0-2 |
| Monolith | 5.0-10.0m | Set pieces, boss arenas | 0-1 |

---

## 4. Surface Detail Techniques

### Crack Patterns

Cracks form along geological weakness planes. In Blender shader nodes:

1. **Voronoi Texture** (Crackle or F2-F1 mode) at scale 4-8 creates the crack network
2. **Math Node** (Less Than, threshold 0.03-0.06) converts distance field to thin crack lines
3. **Noise Texture** fed into the threshold creates variable crack width
4. Distort the Voronoi input vector with a low-factor Noise Texture to break straight lines

For bmesh geometry-level cracks:
- Sample Voronoi F2-F1 at each vertex position
- Vertices near cell boundaries (distance < threshold) get pushed inward along normal
- This creates visible groove lines in the mesh itself

### Lichen Spots

Lichen grows as circular patches on exposed stone surfaces:
- Position: upper surfaces and south-facing (in northern hemisphere) or exposed to light
- Shape: circular, 2-8cm diameter patches
- Color: pale grey-green (0.35, 0.40, 0.30) or yellow-orange (0.45, 0.35, 0.15)
- Material: very rough (0.95), completely non-metallic
- Implementation: use vertex color layer with noise-based circular masks on upward-facing vertices

### Moss Coverage

Moss accumulates in moisture-retaining areas:
- Position: crevices, north-facing surfaces, bases of rocks, between grouped rocks
- Coverage: 5-40% of surface area depending on environment moisture
- Color: deep green (0.08, 0.12, 0.06), desaturated for dark fantasy (0.09, 0.11, 0.07)
- Material: very rough (0.90-0.95), slight subsurface scattering
- Implementation: vertex color mask based on `dot(normal, up_vector)` + cavity detection

```python
def _compute_moss_mask(bm: bmesh.types.BMesh, seed: int,
                       coverage: float = 0.25,
                       cavity_bias: float = 0.6) -> None:
    """Paint vertex colors for moss placement.
    
    Moss grows on:
    - Upward-facing surfaces (dot with up > 0.3)
    - Concave areas (cavity)
    - Lower portions of rock
    - With noise variation for natural look
    """
    from mathutils.noise import noise as blender_noise
    
    # Create vertex color layer
    if "MossMask" not in bm.loops.layers.color:
        color_layer = bm.loops.layers.color.new("MossMask")
    else:
        color_layer = bm.loops.layers.color["MossMask"]
    
    up = Vector((0, 0, 1))  # Blender Z-up
    offset = Vector((seed * 5.5, seed * 3.3, seed * 1.1))
    
    # Find vertical extent for height bias
    min_z = min(v.co.z for v in bm.verts)
    max_z = max(v.co.z for v in bm.verts)
    z_range = max_z - min_z if max_z > min_z else 1.0
    
    for v in bm.verts:
        # Factor 1: Upward-facing (moss on top/horizontal surfaces)
        up_factor = max(0, v.normal.dot(up))
        
        # Factor 2: Height bias (more moss at base)
        height_t = (v.co.z - min_z) / z_range
        height_factor = 1.0 - height_t * 0.6  # More at bottom
        
        # Factor 3: Noise variation
        noise_val = blender_noise(v.co * 3.0 + offset, noise_basis='PERLIN_NEW')
        noise_factor = noise_val * 0.5 + 0.5  # Remap to 0-1
        
        # Factor 4: Cavity (approximated by comparing normal to average neighbor normal)
        # Concave areas trap moisture
        cavity = 0.5  # Default if no neighbors
        if v.link_edges:
            avg_neighbor_pos = Vector((0, 0, 0))
            for e in v.link_edges:
                other = e.other_vert(v)
                avg_neighbor_pos += other.co
            avg_neighbor_pos /= len(v.link_edges)
            # If vertex is below average neighbor position, it's concave
            to_avg = (avg_neighbor_pos - v.co).normalized()
            cavity = max(0, to_avg.dot(v.normal)) * cavity_bias + (1 - cavity_bias) * 0.5
        
        # Combine factors
        moss_value = up_factor * height_factor * noise_factor * cavity
        
        # Threshold based on coverage
        threshold = 1.0 - coverage
        moss_value = 1.0 if moss_value > threshold else 0.0
        
        # Apply to vertex color
        for loop in v.link_loops:
            loop[color_layer] = (moss_value, moss_value, moss_value, 1.0)
```

### Mineral Veins

Lighter or darker streaks following rock grain direction:
- Use a directional noise pattern (stretch noise along one axis by 3-5x)
- Color: lighter than base (quartz: 0.30, 0.28, 0.26) or darker (iron: 0.06, 0.04, 0.03)
- Width: 1-3cm, meandering, occasionally branching
- Roughness: slightly different from base stone (quartz: 0.4, iron oxide: 0.7)

---

## 5. Rock Formation Arrangements

### 5.1 Glacial Erratic (Isolated Boulder)

A single large boulder deposited by glacial action, sitting on different bedrock type.

**Placement rules:**
- Flat or gently sloping terrain (< 15 degrees)
- 15-45% buried below terrain surface
- Random rotation, slight tilt (5-15 degrees from vertical)
- Soil accumulation on uphill side
- Small debris scatter at base (3-6 cobbles within 1m radius)
- Grass/moss more lush immediately around boulder (moisture retention)

**Generation parameters:**
```python
erratic_config = {
    "rock_type": "granite_boulder",
    "size": (1.5, 4.0),  # meters, random range
    "burial_pct": (0.15, 0.45),
    "tilt_degrees": (2, 15),
    "debris_count": (3, 6),
    "debris_radius": 1.0,
    "moss_coverage": 0.20,
}
```

### 5.2 Talus / Scree Slope

Loose rock debris accumulated at cliff base through freeze-thaw weathering.

**Critical rule: Size sorting.** Larger fragments travel further downslope and accumulate at the bottom. Smaller fragments remain near the top. This is the single most important rule for realistic scree.

**Placement rules:**
- Slope angle: 30-40 degrees (angle of repose for angular rock)
- Size gradient: small at top (0.05-0.15m) grading to large at bottom (0.3-1.5m)
- Angular, freshly broken shapes (not rounded)
- Very little vegetation (too unstable for plant growth)
- Faint paths of flattened/settled rock where traffic has occurred
- Material matches the cliff face above

**Generation algorithm:**
```python
def generate_talus_slope(
    cliff_base: Vector,     # Bottom of cliff face
    slope_length: float,    # How far debris extends (5-20m)
    slope_width: float,     # Lateral extent (10-40m)  
    slope_angle: float,     # 30-40 degrees
    seed: int,
    density: float = 0.7,  # Coverage fraction
) -> list[dict]:
    """Generate talus/scree placement data.
    
    Returns list of {position, rotation, scale, rock_type} dicts.
    Size-sorted: largest at bottom, smallest at top.
    """
    placements = []
    rng = random.Random(seed)
    
    # Grid-based placement with jitter
    cell_size = 0.3  # meters
    rows = int(slope_length / cell_size)
    cols = int(slope_width / cell_size)
    
    for row in range(rows):
        t = row / max(rows - 1, 1)  # 0=top, 1=bottom
        
        # Size increases toward bottom (KEY RULE)
        min_size = 0.05 + t * 0.25
        max_size = 0.15 + t * 1.35
        
        for col in range(cols):
            if rng.random() > density:
                continue
            
            # Position with jitter
            x = col * cell_size + rng.uniform(-0.1, 0.1)
            z = -row * cell_size * math.cos(math.radians(slope_angle))
            y = row * cell_size * math.sin(math.radians(slope_angle))
            
            size = rng.uniform(min_size, max_size)
            
            placements.append({
                "position": cliff_base + Vector((x, y, z)),
                "rotation": (
                    rng.uniform(-20, 20),
                    rng.uniform(0, 360),
                    rng.uniform(-20, 20),
                ),
                "scale": size,
                "rock_type": "cliff_debris" if size > 0.3 else "rubble_chunk",
            })
    
    return placements
```

### 5.3 Rocky Outcrop (Bedrock Exposed)

Bedrock poking through soil, showing horizontal strata layers.

**Placement rules:**
- Occurs on hilltops, ridgelines, and where erosion exposes bedrock
- Layers are roughly horizontal (dipping 0-15 degrees in one direction)
- Each layer is 0.1-0.4m thick
- Layers step back (upper layers smaller than lower)
- Moss and grass in cracks between layers
- Weathering rounds the exposed edges
- Soil/grass grows right up to the rock edge

**Generation approach:**
Stack 4-8 flat shale-type rocks, each slightly smaller and offset from the one below. Use cliff_outcrop style but with more pronounced layering and less vertical extent.

### 5.4 Boulder Cluster (3-7 Rocks Grouped)

Natural grouping of rocks that looks like they were deposited together or split from one larger rock.

**Placement rules:**
- 3-7 rocks of decreasing size
- Largest rock at center or slightly off-center
- Rocks touch or nearly touch (gaps < 0.1m)
- Some rocks lean against larger ones
- Moss concentrated in gaps between rocks
- Debris/pebbles fill spaces between boulders
- One rock may be partially atop another
- Total footprint roughly circular, diameter 2-4x largest rock size

**Generation algorithm:**
```python
def generate_boulder_cluster(
    center: Vector,
    num_rocks: int = 5,  # 3-7
    primary_size: float = 1.5,
    seed: int = 42,
) -> list[dict]:
    """Generate a natural boulder cluster.
    
    Places rocks using a "golden angle" spiral for natural-looking distribution,
    with size decreasing from center outward.
    """
    rng = random.Random(seed)
    placements = []
    
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))  # ~137.5 degrees
    
    for i in range(num_rocks):
        t = i / max(num_rocks - 1, 1)
        
        # Size decreases outward
        size = primary_size * (1.0 - t * 0.6) * rng.uniform(0.7, 1.0)
        
        # Position: spiral outward from center
        if i == 0:
            pos = center.copy()
        else:
            angle = i * golden_angle + rng.uniform(-0.3, 0.3)
            radius = size * 0.8 + primary_size * t * 0.5
            pos = center + Vector((
                math.cos(angle) * radius,
                math.sin(angle) * radius,
                0,
            ))
        
        # Slight random tilt
        placements.append({
            "position": pos,
            "rotation": (rng.uniform(-8, 8), rng.uniform(0, 360), rng.uniform(-8, 8)),
            "scale": size,
            "rock_type": "granite_boulder" if size > 0.5 else "angular_boulder",
            "burial_pct": rng.uniform(0.10, 0.35),
        })
    
    return placements
```

### 5.5 Stone Circle / Cairn (Dark Fantasy Waypoints)

Artificial stone arrangements with supernatural significance.

**Stone Circle:**
- 5-9 standing stones arranged in rough circle, 3-8m diameter
- Stones are tall (1.5-3m), slightly tapered, leaning inward 3-8 degrees
- One stone slightly larger than others (marker/entrance stone)
- Center may have flat altar stone or fire pit
- Ground between stones: bare earth, moss, or corrupted soil
- Dark fantasy: rune carvings, glowing cracks, corruption tendrils

**Cairn (Stacked Stones):**
- Conical pile of 10-30 stones, 0.5-1.5m tall
- Largest stones at base, smallest at peak
- Roughly balanced (not perfectly stacked)
- Often marks trail or grave site
- Dark fantasy: may have a single glowing rune stone at peak

### 5.6 Dolmen / Standing Stone Arrangement

Large flat capstone resting on 2-3 vertical support stones.

**Structure:**
- 2-3 support stones: 1.0-1.5m tall, slightly tapered, leaning inward 5-10 degrees
- Capstone: flat slab, 1.5-3.0m long, 0.15-0.3m thick
- Gap beneath: 0.5-1.0m clearance (dark interior, spider webs, moss)
- Surrounding: small rubble debris from weathering

### 5.7 Rubble Pile (Collapsed Structure)

Debris from collapsed wall or building.

**Placement rules:**
- Roughly conical pile shape (angle of repose ~35 degrees)
- Mix of stone blocks (0.2-0.5m) and rubble (0.05-0.15m)
- Some blocks retain squared edges (worked stone)
- Mortar fragments mixed in
- Vegetation growing through gaps (especially at edges)
- May contain partial wall section still standing

---

## 6. Rocks in Water

### 6.1 Waterline Positioning

The critical challenge is positioning rocks so they look naturally partially submerged.

**Rules:**
- Water plane is at a known Z height (passed as parameter)
- Rock bottom extends below water plane by 30-70% of rock height
- Visible portion: 30-70% of total rock (varies per rock)
- Rock base should rest on riverbed (below water surface)
- Wet zone extends 5-15cm above waterline (capillary action / splash zone)

```python
def position_rock_in_water(
    rock_height: float,
    water_z: float,
    submersion_pct: float = 0.5,
    riverbed_z: float = None,
) -> dict:
    """Calculate rock placement for partial water submersion.
    
    Returns dict with rock_z (base position) and wet_zone_height.
    """
    if riverbed_z is None:
        riverbed_z = water_z - rock_height * 0.8
    
    # Rock base sits on riverbed
    rock_base_z = riverbed_z
    rock_top_z = rock_base_z + rock_height
    
    # Verify reasonable submersion
    actual_submersion = (water_z - rock_base_z) / rock_height
    
    # Wet zone: splash + capillary above waterline
    wet_zone_top = water_z + rock_height * 0.08  # 8% above waterline
    
    return {
        "rock_z": rock_base_z,
        "water_z": water_z,
        "visible_height": rock_top_z - water_z,
        "submerged_height": water_z - rock_base_z,
        "wet_zone_top": wet_zone_top,
        "submersion_pct": actual_submersion,
    }
```

### 6.2 River Stone Characteristics

River stones are shaped by water erosion over centuries:
- **Shape:** Rounded, smooth, no sharp edges
- **Aspect ratio:** Oblate (flattened sphere), Y:X ratio 0.4-0.7
- **Surface:** Very smooth, fine grain visible but no cracks
- **Size sorting:** In rivers, stones sort by size -- larger in fast water, smaller in eddies
- **Orientation:** Long axis parallel to current flow (hydrodynamic alignment)
- **Clustering:** Small stones pack into gaps between larger ones

**Material differences wet vs dry:**

| Property | Dry | Wet (below waterline) | Splash Zone |
|----------|-----|----------------------|-------------|
| Base Color | 1.0x | 0.65-0.70x (darker) | 0.80x |
| Roughness | 0.80-0.95 | 0.15-0.30 | 0.40-0.55 |
| Specular | 0.5 (default) | 0.6-0.7 | 0.55 |
| Normal Strength | 1.0x | 0.6x (water fills cracks) | 0.8x |

### 6.3 Stepping Stones

Flat-topped rocks spaced for crossing:
- **Top surface:** Roughly flat (within 5 degrees of horizontal)
- **Spacing:** 0.5-0.8m center-to-center (comfortable stride)
- **Size:** 0.3-0.6m diameter, flat-topped
- **Height:** Top surface 5-15cm above water level
- **Alignment:** Roughly linear path with slight natural deviation (not perfectly straight)
- **Wet surfaces:** Darker, lower roughness on sides below water

### 6.4 Rapids Rocks

Large boulders creating white water effects:
- **Size:** 0.5-2.0m, larger than river stones
- **Position:** Partially breaking the surface, creating flow disruption
- **Upstream face:** Slightly smoother from direct water impact
- **Downstream:** Moss/algae accumulation in calmer water behind rock
- **Foam zone:** White water/foam texture around upstream half of base
- **Sound cue position:** Use rock positions to place audio emitters

### 6.5 Waterfall Rocks

Rocks at waterfall base and face:
- **Base pool rocks:** Dark, wet, heavily mossed on spray-side
- **Face rocks:** Vertical, wet sheen, algae streaks running down
- **Roughness:** Very low (0.1-0.2) due to constant water contact
- **Moss:** Heavy (40-60% coverage) on sides receiving spray mist
- **Material:** Dark grey-green tint from algae

### 6.6 Lake Shore Rocks

Half-buried in mud/sand at lake edge:
- **Burial:** 40-70% buried in sediment
- **Algae line:** Distinct color change at typical water level
- **Below algae line:** Green-brown tint, slimy texture (roughness 0.15-0.25)
- **Above algae line:** Normal dry rock
- **Mud splashing:** Lower portions may have dried mud deposits (brown specks)

### 6.7 Riverbed Pebbles (Visible Through Water)

When water is clear enough to see the bottom:
- **Density:** High (80-95% coverage of riverbed surface)
- **Size:** 0.02-0.08m (pebbles and small cobbles)
- **Shape:** Very rounded, smooth
- **Color:** Multi-colored from different source rocks
- **Material:** Wet appearance (low roughness), colors appear more vivid underwater
- **Implementation:** Can use particle instancing or a single rock-bed mesh with displacement

---

## 7. Rock Materials for Dark Fantasy

### 7.1 Base Stone Palette

VeilBreakers' dark fantasy aesthetic demands muted, desaturated colors.

| Stone Type | Base Color (linear sRGB) | Roughness | Notes |
|------------|-------------------------|-----------|-------|
| Dark Granite | (0.10, 0.10, 0.11) | 0.85 | Primary boulder material |
| Warm Sandstone | (0.14, 0.11, 0.08) | 0.90 | Warm accent, building foundations |
| Blue-Grey Slate | (0.12, 0.12, 0.14) | 0.80 | Shale, flat rocks |
| Dark Basalt | (0.06, 0.06, 0.07) | 0.75 | Volcanic regions, very dark |
| Weathered Limestone | (0.16, 0.15, 0.13) | 0.88 | Cliff faces, outcrops |
| Mossy Stone | (0.09, 0.11, 0.07) | 0.82 | Forest floor rocks |

**All rocks: metallic = 0.0** (rocks are dielectric materials, never metallic)

### 7.2 Wet Rock Material

Wet rock appearance is achieved by:
1. Darkening base color to 65-70% of dry value
2. Reducing roughness dramatically (0.85 dry -> 0.25 wet)
3. Reducing normal map strength (water fills micro-crevices)

**Node approach for material with wet/dry zones:**

```
Vertex Color (MossMask.R) -> drives moss mix
Object Z position vs Water Z -> drives wet/dry mix

Dry Path:
  Base Color -> Noise variation -> Principled BSDF (roughness 0.85)

Wet Path:
  Base Color * 0.68 -> Principled BSDF (roughness 0.25)

Mix based on wet zone mask
```

### 7.3 Moss Material Layer

```
Moss Base Color: (0.08, 0.12, 0.06, 1.0)  -- dark forest green
Roughness: 0.92
Metallic: 0.0
Subsurface: 0.02 (slight green subsurface for translucency)
Normal: Low strength (0.3) -- moss is fuzzy/soft
```

Moss placement mask from vertex colors, driven by:
- Normal direction (dot with up vector > 0.3)
- Cavity detection (concave areas retain moisture)
- Height (lower = more moss)
- Noise (natural patchiness)

### 7.4 Lichen Material Layer

```
Lichen Base Color: (0.35, 0.40, 0.30, 1.0)  -- pale grey-green
  OR orange variant: (0.45, 0.30, 0.12, 1.0)
Roughness: 0.95
Metallic: 0.0
```

Lichen appears as discrete circular patches (2-8cm diameter). Implementation:
- Generate random circular mask positions on UV space
- Use Voronoi cell distance to create circular patches
- Only on upward-facing or wind-exposed surfaces

### 7.5 Corruption Effects (Dark Fantasy Specific)

For corrupted/tainted rocks in VeilBreakers:

**Dark Purple Veins:**
```
Vein Color: (0.12, 0.02, 0.15, 1.0)  -- deep purple-black
Pattern: Voronoi Crackle stretched along one axis (scale 4-6)
Width: Thin (0.01-0.03 UV space)
Edge glow: (0.6, 0.1, 0.8, 1.0) emission at 0.5-2.0 strength
```

**Glowing Cracks:**
```
Crack network: Voronoi F2-F1 at scale 3-5
Emission Color: (0.8, 0.2, 1.0, 1.0) or (1.0, 0.3, 0.1, 1.0) for fire
Emission Strength: 2.0-5.0 (visible glow in dark scenes)
Crack mask: Math Less Than with threshold 0.02-0.04
Animation: Noise-driven emission strength pulsing
```

**Crystalline Growths:**
- Small crystal clusters emerging from rock cracks
- Use the existing crystal rock_type but scaled to 0.05-0.15m
- Position at crack intersections
- Emission: slight internal glow (0.3-0.8 strength)
- Color: purple, sickly green, or blood red depending on corruption type

---

## 8. Procedural Generation in Blender Python

### 8.1 Complete Rock Generation Pipeline

```python
def generate_rock_mesh_v2(
    rock_type: str = "granite_boulder",
    size: float = 1.0,
    seed: int = 42,
    detail: int = 3,
    target_tris: int = 500,
) -> MeshSpec:
    """Generate a realistic rock mesh using multi-pass deformation.
    
    Pipeline:
    1. Convex hull from random points in ellipsoidal volume
    2. Subdivide to working resolution
    3. Multi-octave noise displacement (primary shape)
    4. Voronoi faceting (flat planes and ridges)
    5. Fine detail displacement
    6. Optional flat base (for ground contact)
    7. Decimate to target poly count
    8. Compute moss/wet vertex colors
    9. UV unwrap via cube projection
    """
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.noise import multi_fractal
    
    # Look up type parameters
    params = ROCK_TYPE_PARAMS[rock_type]
    
    # Step 1: Base shape
    bm = _generate_rock_base(
        seed=seed,
        size=size,
        aspect_x=params["aspect"][0],
        aspect_y=params["aspect"][1],
        aspect_z=params["aspect"][2],
        num_points=params["base_points"],
    )
    
    # Step 2: Subdivide
    subdiv_levels = params["subdiv"]
    for _ in range(subdiv_levels):
        bmesh.ops.subdivide_edges(
            bm, edges=bm.edges,
            cuts=1, use_grid_fill=True
        )
    
    # Step 3: Primary displacement
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    _displace_rock_surface(
        bm, seed=seed,
        octaves=3,
        amplitude=size * params["displacement"],
        lacunarity=2.0,
        persistence=0.5,
    )
    
    # Step 4: Voronoi faceting (skip for river stones)
    if params.get("faceted", True):
        _apply_voronoi_faceting(
            bm, seed=seed + 1000,
            strength=size * params["displacement"] * 0.4,
            scale=3.0,
        )
    
    # Step 5: Fine detail
    _displace_rock_surface(
        bm, seed=seed + 2000,
        octaves=2,
        amplitude=size * params["displacement"] * 0.15,
        lacunarity=4.0,
        persistence=0.3,
    )
    
    # Step 6: Flat base
    if params.get("flat_base", True):
        _flatten_base(bm, cut_height=-size * params["aspect"][1] * 0.4)
    
    # Step 7: Smooth pass (light, preserves detail)
    for v in bm.verts:
        if not v.is_boundary:
            avg = Vector((0, 0, 0))
            count = 0
            for e in v.link_edges:
                avg += e.other_vert(v).co
                count += 1
            if count > 0:
                avg /= count
                v.co = v.co.lerp(avg, 0.15)  # Very light smooth
    
    # Step 8: Decimate
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.001)
    current_tris = sum(len(f.verts) - 2 for f in bm.faces)
    if current_tris > target_tris:
        ratio = target_tris / current_tris
        bmesh.ops.dissolve_limit(
            bm, angle_limit=math.radians(5.0),
            verts=bm.verts, edges=bm.edges,
        )
    
    # Step 9: Moss vertex colors
    _compute_moss_mask(bm, seed=seed + 3000, coverage=params.get("moss", 0.15))
    
    # Extract verts/faces for MeshSpec
    bm.verts.ensure_lookup_table()
    verts = [tuple(v.co) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    
    bm.free()
    
    return _make_result(
        f"Rock_{rock_type}",
        verts, faces,
        rock_type=rock_type,
        category="vegetation",
    )
```

### 8.2 Generating Unique Rocks from Seeds

The seed parameter must flow through all noise functions. From a single seed, derive sub-seeds for each pass:

```python
# Seed derivation pattern
base_seed = user_seed
shape_seed = base_seed * 13 + 7      # Convex hull point placement
primary_disp_seed = base_seed * 29 + 11  # Primary displacement
facet_seed = base_seed * 43 + 19     # Voronoi faceting
detail_seed = base_seed * 61 + 23    # Fine detail
moss_seed = base_seed * 79 + 31      # Moss placement
```

To generate a library of 10+ unique rocks:
```python
rock_library = []
for i in range(12):
    rock = generate_rock_mesh_v2(
        rock_type="granite_boulder",
        size=1.0,
        seed=42 + i * 1000,  # Well-separated seeds
        detail=3,
        target_tris=400,
    )
    rock_library.append(rock)
```

### 8.3 UV Unwrapping Strategy

For irregular rock shapes, **cubic projection** is the most reliable automated approach:

```python
def _uv_unwrap_rock(bm: bmesh.types.BMesh) -> None:
    """Apply cube projection UVs suitable for triplanar/procedural materials."""
    uv_layer = bm.loops.layers.uv.verify()
    
    for face in bm.faces:
        normal = face.normal
        # Determine dominant axis
        abs_n = (abs(normal.x), abs(normal.y), abs(normal.z))
        dominant = abs_n.index(max(abs_n))
        
        for loop in face.loops:
            co = loop.vert.co
            if dominant == 0:    # X-facing -> use Y,Z
                loop[uv_layer].uv = (co.y, co.z)
            elif dominant == 1:  # Y-facing -> use X,Z
                loop[uv_layer].uv = (co.x, co.z)
            else:                # Z-facing -> use X,Y
                loop[uv_layer].uv = (co.x, co.y)
```

For game export, triplanar projection in the shader is preferred over UV-based texturing because:
- No visible seams on irregular geometry
- Works for any rock shape without UV unwrap artifacts
- Shader-level triplanar is standard in Unity URP/HDRP

### 8.4 mathutils.noise Available Functions

| Function | Use For | Key Parameters |
|----------|---------|----------------|
| `noise(position)` | Single noise sample | `noise_basis` (PERLIN_NEW, VORONOI_F1, etc.) |
| `multi_fractal(pos, H, lac, oct)` | Multi-octave fractal | `H`=1.0, `lacunarity`=2.0, `octaves`=4 |
| `turbulence(pos, oct, hard)` | Turbulent noise (fBm) | `hard`=True for ridged, `amplitude_scale`, `frequency_scale` |
| `fractal(pos, H, lac, oct)` | Fractal Brownian motion | Same as multi_fractal but different algorithm |
| `hetero_terrain(pos, H, lac, oct, offset)` | Terrain-like noise | Good for rock surface variation |
| `hybrid_multi_fractal(pos, H, lac, oct, offset, gain)` | Complex multi-fractal | Most control over fractal character |
| `variable_lacunarity(pos, distortion)` | Warped noise | Good for mineral veins |
| `cell(position)` | Voronoi cell noise | Returns cell value, good for blocky patterns |
| `cell_vector(position)` | Voronoi cell + vector | Returns vector, good for crack directions |

**Noise basis types:** `BLENDER`, `PERLIN_ORIGINAL`, `PERLIN_NEW`, `VORONOI_F1`, `VORONOI_F2`, `VORONOI_F3`, `VORONOI_F4`, `VORONOI_F2F1`, `VORONOI_CRACKLE`, `CELLNOISE`

---

## 9. Rock Placement Rules

### 9.1 Terrain Integration

**Partial Burial (Critical for Realism):**
- Rocks do NOT sit on top of terrain -- they are embedded in it
- Burial depth: 15-45% of rock height for most boulders
- Larger rocks = deeper burial (they're heavier, sink more)
- Formula: `burial_pct = 0.15 + 0.10 * log2(rock_diameter_m + 1)`

**Implementation:**
```python
def bury_rock_in_terrain(
    rock_position: Vector,
    rock_height: float,
    terrain_height_at_position: float,
    burial_pct: float = 0.25,
) -> Vector:
    """Adjust rock Y position so it's partially buried in terrain."""
    buried_depth = rock_height * burial_pct
    # Rock origin is at center, so offset by half height minus burial
    rock_y = terrain_height_at_position - buried_depth + rock_height * 0.5
    return Vector((rock_position.x, rock_y, rock_position.z))
```

### 9.2 Soil Accumulation

On the uphill side of large boulders, soil and debris accumulate:
- Depth: 5-15cm of soil buildup
- Extent: 0.3-1.0m from rock face
- Shape: Crescent-shaped, wrapping around uphill side
- Vegetation: Grass/moss denser in accumulated soil

### 9.3 Shadow and Microclimate

- **Under overhangs:** Darker soil, moss, dampness
- **South-facing (northern hemisphere):** Drier, more lichen, less moss
- **North-facing:** More moss, darker coloring
- **Lee side (downwind):** Snow/leaf accumulation
- **Crevices between grouped rocks:** Darkest, most moss, moisture trapped

### 9.4 Scatter Density Rules

| Biome | Rocks per 100m2 | Dominant Types | Notes |
|-------|-----------------|----------------|-------|
| Forest Floor | 3-8 | Mossy boulders, cobbles | Partially hidden by leaf litter |
| Mountain Slope | 15-30 | Angular debris, outcrops | Size-sorted on slopes |
| Riverbank | 10-20 | River stones, cobbles | Rounded, partially buried |
| Cliff Base | 20-40 | Talus, rubble | Dense, angular, fresh |
| Open Field | 1-3 | Glacial erratics | Sparse, large, isolated |
| Swamp/Marsh | 2-5 | Mossy, partially submerged | Dark, very mossy |
| Ruins | 10-25 | Rubble, worked stone blocks | Mixed angular and squared |
| Dark Fantasy Corrupted | 3-8 | Corrupted boulders, crystals | Glowing cracks, purple veins |

### 9.5 Grouping Probability

Not every rock is isolated. Natural rock placement follows:
- 40% solitary (single rock, possibly with pebble scatter)
- 35% paired or tripled (2-3 rocks near each other)
- 20% cluster (4-7 rocks grouped tightly)
- 5% formation (outcrop, wall, specific arrangement)

---

## 10. Poly Budget & LOD Strategy

### 10.1 Per-Rock Triangle Budgets

| Distance | Budget | Technique |
|----------|--------|-----------|
| < 5m (hero) | 400-800 tris | Full detail mesh |
| 5-20m (mid) | 100-200 tris | Decimated LOD |
| 20-50m (far) | 30-60 tris | Aggressive decimate |
| > 50m (distant) | Billboard or removed | 2-tri card with rock texture |

### 10.2 LOD Generation

Blender's `bmesh.ops.dissolve_limit` with increasing angle thresholds:

| LOD Level | Dissolve Angle | Smooth Iterations | Approximate Reduction |
|-----------|---------------|--------------------|-----------------------|
| LOD0 (full) | -- | 0 | 1.0x (100%) |
| LOD1 | 5 degrees | 1 | 0.4x (40%) |
| LOD2 | 12 degrees | 2 | 0.15x (15%) |
| LOD3 | 25 degrees | 3 | 0.05x (5%) |

### 10.3 Instancing Strategy

For dense rock scatter (riverbed, talus):
- Generate 8-12 unique rock meshes as a "rock library"
- Instance from library with random rotation, scale variation (0.8-1.2x), and mirror
- This gives apparent variety from limited unique meshes
- In Unity: GPU instancing with per-instance color variation

---

## 11. Implementation Recommendations

### Priority 1: Fix generate_rock_mesh()

1. **Add `seed` parameter** to `generate_rock_mesh()` -- currently hardcoded
2. **Replace `_make_faceted_rock_shell`** with convex-hull-based approach for boulders
3. **Add rock types:** `river_stone`, `flat_shale`, `stepping_stone`, `massive_rock`
4. **Add `burial_pct` to MeshSpec metadata** so scatter engine can position correctly

### Priority 2: Rock Formation Generators

New functions to add to `environment_scatter.py` or a new `rock_formations.py`:

| Function | Purpose |
|----------|---------|
| `generate_boulder_cluster()` | 3-7 grouped rocks |
| `generate_talus_slope()` | Size-sorted scree at cliff base |
| `generate_rocky_outcrop()` | Layered bedrock exposure |
| `generate_stone_circle()` | Dark fantasy waypoint marker |
| `generate_cairn()` | Stacked stone pile |
| `generate_dolmen()` | Capstone on supports |
| `generate_rubble_pile()` | Collapsed structure debris |
| `generate_stepping_stones()` | River crossing |

### Priority 3: Water Integration

1. Add `water_z` parameter to scatter engine
2. Create wet/dry material zones based on vertex Z relative to water surface
3. Add `generate_river_rocks()` function that places rounded stones in/near water
4. Implement splash zone material transition (dry -> splash -> wet -> submerged)

### Priority 4: Material Upgrades

1. Add `build_rock_material()` variant with moss/lichen/wet zones driven by vertex color
2. Add corruption variant with emission cracks
3. Implement triplanar projection node setup for seamless rock texturing
4. Add wet rock material preset

### File Organization

```
blender_addon/handlers/
  procedural_meshes.py     -- generate_rock_mesh_v2() (per-rock geometry)
  rock_formations.py       -- NEW: formation generators (clusters, talus, etc.)
  environment_scatter.py   -- Rock scatter passes (existing, needs water_z support)
  procedural_materials.py  -- build_rock_material() + wet/moss/corruption variants
  terrain_materials.py     -- Terrain-level rock zone materials
```

---

## 12. Sources

### Blender API & Addons
- [Blender BMesh Operators API](https://docs.blender.org/api/current/bmesh.ops.html) -- convex_hull, subdivide_edges, dissolve_limit
- [mathutils.noise API](https://docs.blender.org/api/current/mathutils.noise.html) -- multi_fractal, turbulence, noise basis types
- [Stylized Rock Generator addon](https://github.com/mertnizamoglu/Stylized-Rock-Blender) -- modifier stack pattern (subdiv -> displace -> decimate -> smooth -> bevel)
- [Rock Generator addon (Blender contrib)](https://github.com/versluis/Rock-Generator) -- classic icosphere + displacement approach
- [Blender Voronoi Texture Node](https://docs.blender.org/manual/en/latest/compositing/types/texture/voronoi.html)

### Procedural Rock Techniques
- [Geometry Nodes Procedural Rock Generation (ArtStation)](https://www.artstation.com/godstepson/blog/N8KB/007-geometry-nodes-in-blender-procedural-rock-generation)
- [Wicked Rocks Generator](https://thetahat.itch.io/wicked-rocks) -- 1-1000 unique rocks with variation modes
- [Procedural Rock Generator (Superhive)](https://superhivemarket.com/products/procedural-rock-generator)
- [RockForm Designer](https://superhivemarket.com/products/rockform) -- geonodes-based, 20 base mesh groups
- [Perlin Noise Algorithm Reference](https://rtouti.github.io/graphics/perlin-noise-algorithm)

### Materials & Shading
- [Procedural Crack Patterns (The Blend)](https://blend.beehiiv.com/p/cracks) -- Voronoi Less Than technique
- [Easy Stones & Cracks in Eevee (Creative Shrimp)](https://www.creativeshrimp.com/easy-stones-cracks-eevee.html)
- [Procedural Moss Material (Blender Artists)](https://blenderartists.org/t/procedural-moss-material-blender-tutorial/1454785)
- [Poly Haven Rock Textures](https://polyhaven.com/textures/rock) -- PBR reference values
- [Fractal Voronoi Noise in Blender](https://blenderartists.org/t/thanks-to-your-help-fractal-voronoi-noise-was-added-into-blender/1448508)

### Geology & Placement
- [Scree (Wikipedia)](https://en.wikipedia.org/wiki/Scree) -- angle of repose 30-40 degrees, size sorting
- [Talus vs Scree (pmags)](https://pmags.com/talus-vs-scree-what-is-the-difference) -- size classification
- [Landscape (Level Design Book)](https://book.leveldesignbook.com/process/blockout/massing/landscape)

### AAA Environment Art
- [Environment Design for AAA Games (80.lv)](https://80.lv/articles/environment-design-for-aaa-games-with-laurie-durand)
- [Creation of Realistic Rocks for AAA Games (ArtStation)](https://www.artstation.com/franvergara/blog/9e2L/creation-and-setup-of-realistic-rocks-for-aaa-games-in-unreal-engine-tutorial)
- [3D Water and Rocks in Blender (Evenant)](https://evenant.com/3d-rocks-and-water-in-blender/)
- [BMesh Shaping Models (Medium)](https://behreajj.medium.com/shaping-models-with-bmesh-in-blender-2-9-2f4fcc889bf0)

### Dark Fantasy Effects
- [Glowing Cracks Shader](https://gamecontentdeals.com/assets/vfx/glowing-cracks-shader/) -- crack emission technique
