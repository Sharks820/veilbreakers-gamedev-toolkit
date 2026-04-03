# Terrain Water Systems Research

**Researched:** 2026-04-02
**Domain:** Procedural water generation (rivers, lakes, ponds, waterfalls, shorelines) + Unity URP water rendering
**Confidence:** HIGH (algorithm sources verified against open-source implementations + official Unity docs)

---

## Summary

This research covers the complete water pipeline for VeilBreakers: procedural generation of water features in Blender (rivers, lakes, ponds, waterfalls, swamps) and rendering in Unity URP (shaders, flow maps, caustics, foam). The existing toolkit already has foundational water capabilities -- `carve_river_path()` in `_terrain_noise.py` (A* pathfinding + depth carving), `handle_create_water()` in `environment.py` (spline-based mesh with flow vertex colors), `generate_waterfall()` in `terrain_features.py`, `generate_swamp_terrain()`, coastline generators, and a basic Unity water shader (`VFX-07`). The gaps are: meander simulation, natural lake formation from terrain depressions, tributary merging, shoreline material transitions, depth-based Unity rendering, and dark fantasy water variants.

**Primary recommendation:** Extend the existing `carve_river_path()` with momentum-based meander simulation (Nick McDonald's approach), add flood-fill lake generation, enhance the Unity water shader with depth-based coloring + Gerstner waves + flow maps + caustics, and create dark fantasy water material presets (corrupted, swamp, underground).

---

## Project Constraints (from CLAUDE.md)

- All generation must be pure Python/numpy (no bpy dependency in logic functions) for testability
- Blender mutations must return viewport screenshots for visual verification
- Pipeline order: repair -> UV -> texture -> rig -> animate -> export
- Use seeds for reproducible generation
- Unity tools generate C# editor scripts, follow `next_steps` for compile+execute
- Water mesh tri budget: < 20K triangles (from existing `test_aaa_water_scatter.py`)
- Vertex color convention for flow data: R=speed, G=dir_x, B=dir_z, A=foam
- Security sandbox: blocked functions are exec/eval/compile/__import__/breakpoint/globals/locals/vars ONLY

---

## 1. River Generation Algorithms

### 1.1 Current State in Toolkit

**`_terrain_noise.py::carve_river_path()`** -- A* pathfinding from source to destination on heightmap, with slope-weighted cost function, then carves channel with distance-based falloff. Works but produces unnaturally straight paths.

**`environment.py::handle_carve_river()`** -- Blender handler that extracts heightmap from mesh vertices, calls `carve_river_path()`, writes back.

**`handle_create_water()`** -- Creates spline-following water surface mesh with flow vertex colors (speed, direction, foam).

### 1.2 Meander Generation (Nick McDonald's Momentum Method)

**Source:** https://nickmcd.me/2023/12/12/meandering-rivers-in-particle-based-hydraulic-erosion-simulations/
**Confidence:** HIGH -- open source implementation with clear algorithm description

The key insight: tracking cumulative **stream momentum** across the terrain creates centrifugal forces that cause rivers to curve naturally. This is a low-complexity addition that produces high emergent complexity.

**Algorithm:**

1. **Momentum map** -- 2D array same size as heightmap, stores (momentum_x, momentum_y) per cell
2. **Accumulation phase** (per particle per timestep):
   ```
   cell.momentum_x_track += drop.volume * drop.speed_x
   cell.momentum_y_track += drop.volume * drop.speed_y
   ```
3. **Averaging phase** (after all particles descend):
   ```
   cell.momentum_x = (1.0 - lrate) * cell.momentum_x + lrate * cell.momentum_x_track
   cell.momentum_y = (1.0 - lrate) * cell.momentum_y + lrate * cell.momentum_y_track
   ```
4. **Force application** -- momentum transfers to particles via dot-product alignment (prevents perpendicular momentum transfer)

**Key parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| momentumTransfer | 1.0 | Force magnitude from momentum map to particle |
| lrate | 0.1 | Exponential averaging rate (temporal smoothing) |
| entrainment | 0.01 | Base sediment suspension, scaled by discharge |
| discharge | accumulated | Local volumetric flow rate |

**Integration path:** Add momentum arrays to existing `hydraulic_erosion()` in `_terrain_noise.py`. The existing droplet loop already tracks position and velocity -- adding momentum accumulation is ~20 lines of code.

### 1.3 River Path from Gradient Descent

For generating river paths without full erosion simulation (faster, for layout purposes):

```python
def generate_river_path_gradient(heightmap, start, seed=0, meander_strength=0.3):
    """Follow terrain gradient with noise-based meander offset.
    
    1. At each step, compute gradient direction (steepest descent)
    2. Add perpendicular noise offset (fbm-based, varies along path)
    3. Accumulate inertia (previous direction blended with gradient)
    4. Stop when reaching edge or local minimum
    """
    path = [start]
    direction = (0.0, 0.0)  # accumulated direction
    inertia = 0.6  # 0=pure gradient, 1=pure momentum
    
    for step in range(max_steps):
        r, c = path[-1]
        grad = compute_gradient(heightmap, r, c)  # steepest descent
        
        # Perpendicular meander offset
        perp = (-grad[1], grad[0])  # 90 degree rotation
        noise_val = fbm(step * 0.1, seed) * meander_strength
        
        # Blend gradient + inertia + meander
        new_dir = (
            grad[0] * (1 - inertia) + direction[0] * inertia + perp[0] * noise_val,
            grad[1] * (1 - inertia) + direction[1] * inertia + perp[1] * noise_val,
        )
        direction = normalize(new_dir)
        
        next_r = r + round(direction[0])
        next_c = c + round(direction[1])
        path.append((next_r, next_c))
    return path
```

### 1.4 River Widening and Depth Carving

Rivers should widen downstream as tributaries merge. The existing `carve_river_path()` uses fixed width -- this needs progressive widening:

```python
# Width increases with accumulated flow (proxy: distance from source)
width_at_point = base_width + width_growth * sqrt(distance_from_source / total_length)

# Depth profile: deepest at center, shallow at edges (parabolic cross-section)
depth_at_offset = max_depth * (1.0 - (offset / half_width) ** 2)
```

**Bank profiles by river type:**
| Type | Cross-section | Depth (m) | Width (m) | Notes |
|------|--------------|-----------|-----------|-------|
| Mountain stream | V-shaped | 0.5-1.5 | 2-4 | Rocky bed, fast flow |
| Valley river | U-shaped parabolic | 1.5-4.0 | 8-20 | Sandy/gravel bed |
| Lowland river | Wide, shallow | 1.0-3.0 | 15-40 | Muddy banks, meanders |
| Swamp channel | Irregular, flat | 0.3-1.0 | 3-10 | Murky, no defined banks |

### 1.5 Tributary Merging

```python
def merge_tributaries(main_path, tributary_paths, heightmap):
    """Merge tributary rivers into main river.
    
    1. Find closest point on main river to each tributary endpoint
    2. Route tributary to that point using A* (downhill preference)
    3. At merge point: increase main river width by tributary_width * 0.6
    4. Create delta/fan geometry at merge (triangle of sediment)
    """
```

### 1.6 Riverbed Materials

Material zones should auto-assign based on flow speed and terrain:
| Flow Speed | Primary Material | Secondary | Notes |
|------------|-----------------|-----------|-------|
| Fast (>2 m/s) | rock, gravel | wet_rock | Mountain streams |
| Medium (0.5-2) | gravel, sand | pebbles | Valley rivers |
| Slow (<0.5) | sand, mud | silt, clay | Lowland rivers |
| Still (0) | mud, silt | organic_matter | Ponds, swamp |

---

## 2. Lake and Pond Creation

### 2.1 Flood-Fill from Terrain Depressions

**Source:** https://nickmcd.me/2020/04/15/procedural-hydrology/
**Confidence:** HIGH

Lakes form naturally in terrain depressions. The algorithm:

```python
def find_lakes(heightmap, min_lake_area=16):
    """Find natural lake positions by flood-filling terrain depressions.
    
    1. For each local minimum in heightmap:
       a. Flood-fill outward, raising water level incrementally
       b. Track volume of water accumulated
       c. Stop when water overflows at a drainage point
       d. If flooded area > min_lake_area, record as lake
    2. Return list of (center, water_level, shoreline_cells, area)
    """
    
    # Find local minima (cells lower than all 8 neighbors)
    minima = find_local_minima(heightmap)
    
    lakes = []
    for min_pos in minima:
        water_level = heightmap[min_pos]
        increment = 0.001  # raise water level gradually
        
        while True:
            water_level += increment
            flooded = flood_fill_below(heightmap, min_pos, water_level)
            
            # Check for drainage: any flooded cell on boundary or with
            # neighbor below water_level that isn't in the basin
            drain = find_drainage(heightmap, flooded, water_level)
            if drain is not None:
                break
        
        if len(flooded) >= min_lake_area:
            lakes.append({
                "center": compute_centroid(flooded),
                "water_level": water_level,
                "shoreline": find_shoreline_cells(flooded, heightmap),
                "area": len(flooded),
                "depth_map": compute_depth_map(flooded, heightmap, water_level),
            })
    return lakes
```

### 2.2 Natural Shoreline Shapes

Perfectly circular lakes look fake. Natural shorelines use noise perturbation:

```python
def generate_lake_shoreline(center, base_radius, seed, irregularity=0.3):
    """Generate irregular lake shoreline using radial noise.
    
    For each angle around the center:
      radius = base_radius * (1.0 + fbm(angle * freq, seed) * irregularity)
    
    This produces lobed, organic shapes. Higher irregularity = more
    finger-like inlets. Add smaller octaves for micro-roughness.
    """
    points = []
    for i in range(num_points):
        angle = 2 * pi * i / num_points
        noise = fbm(angle * 3.0, seed, octaves=4) * irregularity
        r = base_radius * (1.0 + noise)
        points.append((center[0] + r * cos(angle), center[1] + r * sin(angle)))
    return points
```

### 2.3 Shoreline Material Transition

Concentric material zones around water edge:
```
Water center → Deep water → Shallow water → Wet sand/mud → Damp grass → Dry terrain
     0m           -2m          -0.5m           0m             +1m          +3m
```

**Material transition distances (from water edge):**
| Zone | Distance | Material | Visual |
|------|----------|----------|--------|
| Deep water | < -2.0m | deep_water | Dark blue, opaque |
| Shallow water | -2.0 to -0.3m | shallow_water | Lighter blue, semi-transparent |
| Water edge | -0.3 to 0m | water_edge | Foam line, ripples |
| Wet ground | 0 to 1.0m | wet_mud / wet_sand | Dark, reflective |
| Transition | 1.0 to 3.0m | damp_grass | Slightly darker grass |
| Dry | > 3.0m | terrain_default | Normal terrain material |

### 2.4 Depth Variation

Lake depth should follow terrain, not be flat-bottomed:
```python
# Depth = water_level - terrain_height at each point
# Add gentle noise for natural variation
depth = water_level - terrain_z + fbm(x * 0.05, y * 0.05, seed) * 0.3
# Deepest point should be offset from center (not exactly centered)
```

---

## 3. Waterfall Integration with Terrain

### 3.1 Current State

**`terrain_features.py::generate_waterfall()`** -- Generates step-down terrain with cliff face, splash pool, and optional cave behind waterfall. Returns mesh spec with materials (cliff_rock, wet_rock, pool_bottom, ledge, moss).

**`_terrain_depth.py::generate_waterfall_mesh()`** -- Stepped cascade with horizontal ledge surfaces + vertical curtain faces + circular pool at base.

### 3.2 Cliff Detection for Automatic Waterfall Placement

```python
def detect_waterfall_sites(heightmap, river_path, min_drop=3.0, min_width=2.0):
    """Find locations along a river path where waterfalls should occur.
    
    A waterfall site requires:
    1. Sudden elevation drop > min_drop along the path
    2. Sufficient width for water flow
    3. Hard rock layer transition (optional geological realism)
    
    Algorithm:
    - Walk the river path, compute elevation difference per step
    - Where cumulative drop over short distance exceeds threshold,
      mark as waterfall site
    - Cluster nearby drops into single multi-step waterfalls
    """
    sites = []
    for i in range(1, len(river_path)):
        r0, c0 = river_path[i-1]
        r1, c1 = river_path[i]
        drop = heightmap[r0, c0] - heightmap[r1, c1]
        
        if drop > min_drop:
            sites.append({
                "position": (r1, c1),
                "drop_height": drop,
                "upstream": (r0, c0),
                "downstream": (r1, c1),
            })
    
    return merge_nearby_sites(sites, min_gap=3)
```

### 3.3 Waterfall Components

A complete waterfall feature includes:

| Component | Generation Method | Material |
|-----------|------------------|----------|
| Cliff face | Vertical wall with noise-roughened surface | cliff_rock, wet_rock |
| Water curtain | Thin mesh following cliff contour, alpha blend | water_translucent |
| Splash pool | Circular depression carved into terrain | pool_water |
| Splash zone | Radial area with mist particles + wet materials | wet_rock, spray |
| Erosion undercut | Concavity at waterfall base | eroded_rock |
| Plunge pool depth | Deepened area directly under curtain | deep_water |
| Mossy zones | Mist-affected areas flanking waterfall | moss, wet_moss |

### 3.4 Erosion at Waterfall Base

```python
def carve_plunge_pool(heightmap, waterfall_pos, drop_height, pool_radius=None):
    """Carve erosion pool at waterfall base.
    
    Pool radius ~ 1.5 * drop_height (empirical geology)
    Pool depth ~ 0.3 * drop_height
    Shape: bowl with steeper upstream wall, gentler downstream slope
    """
    if pool_radius is None:
        pool_radius = drop_height * 1.5
    pool_depth = drop_height * 0.3
    
    for r, c in cells_within_radius(waterfall_pos, pool_radius):
        dist = distance(waterfall_pos, (r, c))
        falloff = 1.0 - (dist / pool_radius) ** 2
        heightmap[r, c] -= pool_depth * max(0, falloff)
```

---

## 4. Water Rendering in Unity URP

### 4.1 Current State

**`shader_templates.py::generate_water_shader()`** -- Basic URP water shader with:
- Dual sine wave vertex displacement (not Gerstner)
- Dual scrolling normal maps
- Basic URP lighting
- Alpha blending transparency
- No depth-based coloring, no foam, no caustics, no flow maps

**`vfx_mastery_templates.py`** -- Water caustics projector (decal/cookie-based)

### 4.2 Required Shader Upgrades

**Depth-based coloring** (highest priority):
```hlsl
// In fragment shader:
float sceneDepth = LinearEyeDepth(
    SAMPLE_TEXTURE2D(_CameraDepthTexture, sampler_CameraDepthTexture, screenUV).r,
    _ZBufferParams
);
float waterDepth = sceneDepth - input.positionCS.w; // distance from surface to bottom

// Lerp between shallow and deep colors
float depthFactor = saturate(waterDepth / _DepthMaxDistance);
half3 waterColor = lerp(_ShallowColor.rgb, _DeepColor.rgb, depthFactor);
```

**Refraction:**
```hlsl
// Distort screen UV by normal map to simulate refraction
float2 distortion = combinedNormal.xy * _RefractionStrength;
float2 refractedUV = screenUV + distortion;

// Sample scene color at distorted position (requires _CameraOpaqueTexture)
half3 refractionColor = SAMPLE_TEXTURE2D(_CameraOpaqueTexture, sampler_CameraOpaqueTexture, refractedUV).rgb;
```

**Foam at shorelines:**
```hlsl
// Foam where water is shallow (near terrain intersection)
float foamMask = 1.0 - saturate(waterDepth / _FoamDepth);
// Add noise-based foam breakup
float foamNoise = SAMPLE_TEXTURE2D(_FoamTex, sampler_FoamTex, input.uv * _FoamScale + _Time.y * _FoamSpeed).r;
float foam = foamMask * step(0.3, foamNoise);
```

**Flow maps for rivers:**
```hlsl
// Flow map encodes direction as RG (remapped from -1..1 to 0..1)
float2 flowDir = SAMPLE_TEXTURE2D(_FlowMap, sampler_FlowMap, input.uv).rg * 2.0 - 1.0;

// Two-phase flow sampling to avoid stretching
float phase0 = frac(_Time.y * _FlowSpeed);
float phase1 = frac(_Time.y * _FlowSpeed + 0.5);
float2 uv0 = input.uv + flowDir * phase0;
float2 uv1 = input.uv + flowDir * phase1;

half3 normal0 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uv0));
half3 normal1 = UnpackNormal(SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, uv1));

// Blend based on phase to hide seam
float blend = abs(2.0 * phase0 - 1.0);
half3 flowNormal = lerp(normal0, normal1, blend);
```

**Caustics:**
```hlsl
// Project caustics onto underwater surfaces using world-space XZ
float3 causticUV = input.positionWS.xz * _CausticsScale;
float caustic1 = SAMPLE_TEXTURE2D(_CausticsTex, sampler_CausticsTex, causticUV + _Time.y * 0.03).r;
float caustic2 = SAMPLE_TEXTURE2D(_CausticsTex, sampler_CausticsTex, causticUV * 1.4 - _Time.y * 0.02).r;
float caustics = min(caustic1, caustic2); // min creates sharp patterns
// Fade caustics with depth
caustics *= saturate(1.0 - waterDepth / _CausticsDepth);
```

**Gerstner waves** (replace current sine waves):
```hlsl
float3 GerstnerWave(float4 wave, float3 pos, inout float3 tangent, inout float3 binormal)
{
    float steepness = wave.z;
    float wavelength = wave.w;
    float k = 2.0 * PI / wavelength;
    float c = sqrt(9.8 / k);
    float2 d = normalize(wave.xy);
    float f = k * (dot(d, pos.xz) - c * _Time.y);
    float a = steepness / k;
    
    tangent += float3(-d.x * d.x * steepness * sin(f), d.x * steepness * cos(f), -d.x * d.y * steepness * sin(f));
    binormal += float3(-d.x * d.y * steepness * sin(f), d.y * steepness * cos(f), -d.y * d.y * steepness * sin(f));
    
    return float3(d.x * a * cos(f), a * sin(f), d.y * a * cos(f));
}
```

### 4.3 Reflection Options

| Method | Quality | Performance | Best For |
|--------|---------|-------------|----------|
| Reflection Probes | Medium | Cheap (baked) | Static scenes, lakes |
| Planar Reflection | High | Expensive (extra render) | Hero water areas |
| Screen-Space Reflection | Good | Medium | General purpose |
| Environment cubemap | Low-Medium | Very cheap | Distant water, fallback |

**Recommendation for VeilBreakers:** Use Reflection Probes (baked) as default, with SSR enabled for medium/high quality settings. Planar reflection only for key story locations.

### 4.4 Performance Budget

| Feature | GPU Cost (ms @ 1080p) | Notes |
|---------|----------------------|-------|
| Depth-based color | ~0.1 | Uses existing depth buffer |
| Dual normal map scroll | ~0.15 | 2 texture samples |
| Gerstner waves (4 waves) | ~0.2 | Vertex shader math |
| Refraction (scene color) | ~0.3 | Requires opaque texture copy |
| Flow map (2-phase) | ~0.3 | 4 texture samples + blend |
| Caustics | ~0.15 | 2 texture samples + min |
| Foam edge | ~0.1 | Depth comparison + noise |
| SSR | ~0.8-1.5 | Most expensive single feature |
| **Total (no SSR)** | **~1.3** | Within budget for water |
| **Total (with SSR)** | **~2.5** | High quality preset only |

**Target:** < 2ms total for water rendering at 1080p on mid-range GPU.

### 4.5 Required URP Setup

- Enable **Depth Texture** in URP Asset (for depth-based effects)
- Enable **Opaque Texture** in URP Asset (for refraction)
- Water material: Render Queue = Transparent (3000+)
- Water mesh: ZWrite Off, Blend SrcAlpha OneMinusSrcAlpha

---

## 5. Water Interaction with Terrain

### 5.1 Wet Zone Materials

Terrain near water should appear wet. Implementation in Blender procedural materials:

```python
# In auto-splat terrain material assignment:
def assign_wet_zone_material(terrain_cells, water_edge_cells, wet_distance=3.0):
    """Mark terrain cells near water as wet variants.
    
    - 0-1m from water: wet_mud (dark, high roughness 0.3, slight specular)
    - 1-2m: damp_ground (slightly darker base color, roughness 0.5)
    - 2-3m: transition (blend between wet and dry)
    """
```

For Unity shader: multiply terrain albedo by darkness factor based on distance-to-water, reduce roughness in wet zone.

### 5.2 Vegetation Rules Near Water

Extend existing `vegetation_system.py` biome rules with water-proximity zones:

| Distance from Water | Vegetation | Density | Notes |
|---------------------|-----------|---------|-------|
| 0-0.5m (in water) | Lily pads, water plants | Sparse | Floating on surface |
| 0-1m (bank) | Reeds, cattails, rushes | Dense | Tall, vertical |
| 1-3m | Ferns, moss, mushrooms | Medium | Moisture-loving |
| 3-5m | Willows, birch, alders | Normal | Water-tolerant trees |
| 5m+ | Standard biome vegetation | Normal | No water influence |

### 5.3 Bridge Placement

The existing `generate_terrain_bridge_mesh()` in `_terrain_depth.py` connects two world positions. For river crossings:

```python
def find_bridge_locations(river_path, road_paths, heightmap):
    """Find where roads cross rivers and place bridges.
    
    1. Detect road-river intersections
    2. Measure river width at crossing point
    3. Select bridge style based on width and terrain
    4. Generate bridge with abutments resting on terrain
    """
```

---

## 6. Fantasy / Dark Fantasy Water Variants

### 6.1 Corrupted Water

For VeilBreakers' dark fantasy setting, corrupted water areas need distinct visual treatment:

**Shader parameters for corrupted water:**
| Property | Normal Water | Corrupted Water |
|----------|-------------|-----------------|
| Shallow color | (0.3, 0.7, 0.8) cyan | (0.2, 0.05, 0.3) dark purple |
| Deep color | (0.05, 0.15, 0.3) deep blue | (0.1, 0.0, 0.15) near-black purple |
| Emissive | None | (0.4, 0.1, 0.6) * pulse(time) |
| Wave amplitude | 0.1-0.3 | 0.05-0.1 (slow, viscous) |
| Wave speed | 1.0 | 0.3 (sluggish) |
| Transparency | 0.7 | 0.4 (more opaque) |
| Foam color | White | Green-yellow (0.5, 0.7, 0.1) |
| Caustics | Normal | None or distorted purple |
| Particles | None | Floating corruption wisps (VFX) |

**Blender material preset:**
```python
CORRUPTED_WATER_PRESET = {
    "base_color": (0.15, 0.03, 0.2, 1.0),
    "roughness": 0.15,
    "metallic": 0.0,
    "emission_color": (0.4, 0.1, 0.6, 1.0),
    "emission_strength": 0.8,  # Pulsing via driver
    "alpha": 0.5,
    "ior": 1.2,  # Lower than water (1.333) for unnatural feel
}
```

### 6.2 Swamp Water

The existing `generate_swamp_terrain()` creates terrain with water zones. Enhance with:

**Swamp water characteristics:**
- Very shallow (0.1-0.5m depth)
- High turbidity (opaque beyond 0.3m depth)
- Green-brown tint with surface algae layer
- No waves, minimal flow
- Bubbles (methane) as particle effect
- Dead vegetation floating on surface

**Shader adjustments:**
```
Shallow color: (0.15, 0.2, 0.05) -- murky olive
Deep color: (0.05, 0.08, 0.02) -- nearly opaque dark green
Transparency: 0.3 (very opaque)
Normal map strength: 0.1 (barely any surface detail)
Add: surface scum texture overlay (green-brown noise, barely moving)
```

### 6.3 Underground Water

Cave pools and underground rivers have distinct properties:

| Property | Value | Reason |
|----------|-------|--------|
| Color | Very dark blue-green | No sunlight |
| Transparency | 0.9 (very clear) | No organic matter, filtered |
| Reflection | High (mirror-like) | Still water in low light |
| Caustics | None | No direct light source |
| Waves | None or micro-ripples | Sheltered from wind |
| Bioluminescence | Optional (0.2, 0.8, 0.6) glow | Fantasy element |
| Sound | Drip echoes, underground stream | Audio cue |

---

## 7. Architecture Patterns

### 7.1 Recommended Module Structure

```
blender_addon/handlers/
  _water_systems.py          # NEW: Pure-logic water generation
    |- generate_river_path()      # Gradient descent + meander
    |- carve_river_channel()      # Apply river to heightmap
    |- find_lakes()               # Flood-fill lake detection
    |- generate_lake_mesh()       # Lake surface + shoreline
    |- detect_waterfall_sites()   # Auto-detect from river+terrain
    |- generate_water_presets()   # Dark fantasy material presets
  
  environment.py             # EXISTING: Blender handlers
    |- handle_carve_river()       # UPDATE: use new meander paths
    |- handle_create_water()      # UPDATE: lake/pond mode
    |- handle_create_waterfall()  # NEW: auto-placed waterfalls
    |- handle_assign_wet_zones()  # NEW: material transitions

src/veilbreakers_mcp/shared/unity_templates/
  shader_templates.py        # UPDATE: Enhanced water shader
    |- generate_water_shader()    # ADD: depth, foam, flow, caustics
    |- generate_water_presets()   # NEW: corrupted, swamp, cave
```

### 7.2 Water Generation Pipeline

```
1. Generate terrain heightmap (existing)
2. Run hydraulic erosion with momentum (creates natural drainage)
3. Detect river paths from erosion flow map
4. Find lake sites from terrain depressions
5. Carve river channels + lake basins into heightmap
6. Detect waterfall sites along rivers
7. Generate water surface meshes (rivers, lakes, ponds)
8. Apply shoreline material transitions
9. Place water-proximity vegetation
10. Export to Unity with flow vertex colors + material data
```

---

## 8. Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| A* pathfinding | Custom A* | Existing `_astar()` in `_terrain_noise.py` | Already optimized with slope weights |
| Noise functions | Custom hash noise | Existing `_make_noise_generator()` (opensimplex) | Better quality, already integrated |
| Mesh generation | Raw vertex/face lists | Existing `MeshSpec` pattern from `_terrain_depth.py` | Consistent with 293 existing generators |
| Gerstner waves | Custom math | GPU Gems Chapter 1 formula | Well-proven, GPU-optimized |
| Flow maps | Runtime flow sim | Bake flow direction into vertex colors | Already supported by `handle_create_water()` |
| Lake detection | Custom flood fill | scipy.ndimage.label + numpy masking | Orders of magnitude faster than Python loops |

---

## 9. Common Pitfalls

### Pitfall 1: Flat Water Planes
**What goes wrong:** Water rendered as a single flat plane at fixed height looks artificial.
**Why it happens:** Simplest implementation is a plane at Y=water_level.
**How to avoid:** Use spline-following mesh (already in `handle_create_water()`), vary water level along path, add Gerstner wave displacement.
**Warning signs:** Water "floats" above terrain at some points, clips through at others.

### Pitfall 2: River Paths Ignore Terrain
**What goes wrong:** Rivers flowing uphill or through ridges.
**Why it happens:** Using noise-only path without terrain awareness.
**How to avoid:** Always use gradient-descent or A* with elevation cost. Carve the terrain to match, not the other way around.
**Warning signs:** River crosses ridge lines, water appears to flow uphill.

### Pitfall 3: Z-Fighting at Water Surface
**What goes wrong:** Flickering where water mesh meets terrain.
**Why it happens:** Water plane at exact same height as terrain vertices.
**How to avoid:** Offset water mesh slightly above terrain (0.01-0.05m), use alpha fade at edges rather than hard intersection.
**Warning signs:** Shimmering/flickering at shoreline in Unity.

### Pitfall 4: Missing Depth Texture in URP
**What goes wrong:** Depth-based effects (foam, color, refraction) show solid black or wrong values.
**Why it happens:** URP doesn't enable depth/opaque textures by default.
**How to avoid:** Verify URP Asset settings: Depth Texture = ON, Opaque Texture = ON. Document in setup steps.
**Warning signs:** `_CameraDepthTexture` returns 0 or 1, no gradient.

### Pitfall 5: Flow Map Stretching
**What goes wrong:** Normal maps stretch into long streaks along flow direction.
**Why it happens:** Single-phase UV offset accumulates infinitely.
**How to avoid:** Use two-phase flow sampling with crossfade (technique described in Section 4.2).
**Warning signs:** Water surface looks "smeared" instead of flowing.

### Pitfall 6: Performance Death from Transparency
**What goes wrong:** Water tanks framerate despite simple geometry.
**Why it happens:** Transparent objects can't use early-Z rejection; overdraw multiplies cost.
**How to avoid:** Keep water mesh low-poly (<20K tris), minimize transparency overlap layers, use alpha-test for foam instead of alpha-blend where possible.
**Warning signs:** GPU time spikes when camera looks at large water body.

---

## 10. Code Examples

### Complete River Generation (Pure Python)

```python
def generate_river_system(
    heightmap: np.ndarray,
    source: tuple[int, int],
    seed: int = 0,
    meander_strength: float = 0.3,
    base_width: int = 2,
    max_width: int = 6,
    base_depth: float = 0.03,
    max_depth: float = 0.08,
) -> dict:
    """Generate a complete river from source to terrain edge.
    
    Returns:
        dict with: path, carved_heightmap, width_at_each_point,
                   waterfall_sites, tributary_merge_points
    """
    # 1. Generate meandering path following gradient
    path = generate_river_path_gradient(
        heightmap, source, seed, meander_strength
    )
    
    # 2. Compute progressive width (wider downstream)
    widths = []
    for i, (r, c) in enumerate(path):
        t = i / max(len(path) - 1, 1)
        w = base_width + (max_width - base_width) * math.sqrt(t)
        widths.append(int(round(w)))
    
    # 3. Detect waterfall sites before carving
    waterfall_sites = detect_waterfall_sites(heightmap, path)
    
    # 4. Carve channel with variable width and depth
    result = heightmap.copy()
    for i, (r, c) in enumerate(path):
        half_w = widths[i] // 2
        depth = base_depth + (max_depth - base_depth) * (i / len(path))
        
        for dr in range(-half_w, half_w + 1):
            for dc in range(-half_w, half_w + 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < result.shape[0] and 0 <= nc < result.shape[1]:
                    dist = math.sqrt(dr*dr + dc*dc)
                    if dist <= half_w + 0.5:
                        # Parabolic cross-section
                        falloff = 1.0 - (dist / (half_w + 1.0)) ** 2
                        result[nr, nc] -= depth * falloff
    
    return {
        "path": path,
        "carved_heightmap": np.clip(result, 0.0, 1.0),
        "widths": widths,
        "waterfall_sites": waterfall_sites,
        "total_length": len(path),
    }
```

### Unity Water Shader Properties Block (Enhanced)

```hlsl
Properties
{
    [Header(Colors)]
    _ShallowColor ("Shallow Color", Color) = (0.3, 0.7, 0.8, 0.6)
    _DeepColor ("Deep Color", Color) = (0.05, 0.15, 0.3, 0.95)
    _DepthMaxDistance ("Max Depth Distance", Float) = 5.0
    
    [Header(Waves)]
    _WaveA ("Wave A (dir_x, dir_y, steepness, wavelength)", Vector) = (1, 0, 0.5, 10)
    _WaveB ("Wave B", Vector) = (0, 1, 0.25, 20)
    _WaveC ("Wave C", Vector) = (1, 1, 0.15, 40)
    
    [Header(Surface)]
    _NormalTex ("Normal Map", 2D) = "bump" {}
    _NormalStrength ("Normal Strength", Range(0, 2)) = 1.0
    _FlowMap ("Flow Map", 2D) = "gray" {}
    _FlowSpeed ("Flow Speed", Float) = 0.5
    
    [Header(Foam)]
    _FoamTex ("Foam Texture", 2D) = "white" {}
    _FoamColor ("Foam Color", Color) = (1, 1, 1, 1)
    _FoamDepth ("Foam Depth Threshold", Float) = 0.5
    _FoamScale ("Foam UV Scale", Float) = 5.0
    
    [Header(Refraction)]
    _RefractionStrength ("Refraction Strength", Float) = 0.1
    
    [Header(Caustics)]
    _CausticsTex ("Caustics Texture", 2D) = "black" {}
    _CausticsScale ("Caustics Scale", Float) = 0.5
    _CausticsDepth ("Caustics Max Depth", Float) = 3.0
    _CausticsIntensity ("Caustics Intensity", Float) = 1.0
    
    [Header(Fantasy)]
    _EmissionColor ("Emission Color", Color) = (0, 0, 0, 0)
    _EmissionPulseSpeed ("Emission Pulse Speed", Float) = 0.0
}
```

---

## 11. Water Material Presets for VeilBreakers

| Preset | Shallow Color | Deep Color | Waves | Foam | Emission | Use Case |
|--------|--------------|------------|-------|------|----------|----------|
| `clean_river` | (0.3, 0.7, 0.8) | (0.05, 0.2, 0.4) | Medium | White at edges | None | Standard rivers |
| `mountain_stream` | (0.4, 0.8, 0.9) | (0.1, 0.3, 0.5) | Strong | White, heavy | None | Fast mountain water |
| `calm_lake` | (0.2, 0.5, 0.6) | (0.02, 0.1, 0.2) | Minimal | Subtle | None | Still lakes |
| `swamp` | (0.15, 0.2, 0.05) | (0.05, 0.08, 0.02) | None | Green-brown | None | Murky swamp |
| `corrupted` | (0.2, 0.05, 0.3) | (0.1, 0.0, 0.15) | Slow | Yellow-green | Purple pulse | Corrupted areas |
| `blood_pool` | (0.4, 0.02, 0.02) | (0.2, 0.0, 0.0) | Slow | Dark red | Faint red | Boss arena |
| `cave_pool` | (0.1, 0.2, 0.25) | (0.02, 0.05, 0.08) | None | None | Optional cyan biolum | Underground |
| `frozen_edge` | (0.6, 0.8, 0.9) | (0.1, 0.2, 0.3) | Minimal | White ice crust | None | Winter areas |

---

## 12. State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat water planes | Spline-following mesh with flow data | 2020+ | Natural river shapes |
| Simple sine waves | Gerstner wave sum (4-8 waves) | GPU Gems 2004, still standard | Realistic wave shapes with horizontal displacement |
| Screen-space reflection only | Hybrid (probe + SSR + planar) | Unity 6.x | Quality/performance tradeoff per platform |
| Baked flow direction | Runtime vertex color flow + 2-phase sampling | 2018+ | No UV stretching |
| Separate water/terrain passes | Depth-aware water with terrain intersection | Standard now | Foam, shoreline, wet zones |
| Droplet erosion only | Momentum-based meander simulation | McDonald 2023 | Realistic river shapes from erosion |

---

## 13. Sources

### Primary (HIGH confidence)
- Nick McDonald -- Procedural Hydrology (2020): https://nickmcd.me/2020/04/15/procedural-hydrology/ -- Lake simulation, river networks, flood-fill
- Nick McDonald -- Meandering Rivers (2023): https://nickmcd.me/2023/12/12/meandering-rivers-in-particle-based-hydraulic-erosion-simulations/ -- Momentum-based meander algorithm
- Unity Shader Graph Production Ready Water: https://docs.unity3d.com/Packages/com.unity.shadergraph@17.0/manual/Shader-Graph-Sample-Production-Ready-Detail.html -- Official water shader patterns
- NVIDIA GPU Gems Ch.1: https://developer.nvidia.com/gpugems/gpugems/part-i-natural-effects/chapter-1-effective-water-simulation-physical-models -- Gerstner wave formula
- Cyanilux Water Shader Breakdown: https://www.cyanilux.com/tutorials/water-shader-breakdown/ -- Depth, refraction, caustics techniques

### Secondary (MEDIUM confidence)
- Red Blob Games -- Procedural River Drainage: https://www.redblobgames.com/x/1723-procedural-river-growing/ -- River network generation patterns
- Daniel Ilett URP Stylised Water: https://danielilett.com/2020-04-05-tut5-3-urp-stylised-water/ -- URP-specific implementation
- Catlike Coding Waves: https://catlikecoding.com/unity/tutorials/flow/waves/ -- Unity Gerstner wave implementation

### Tertiary (LOW confidence -- needs validation)
- Toxigon URP Water Tutorial: https://toxigon.com/creating-water-shader-unity-urp -- General approach, unverified performance claims

### Existing Codebase (HIGH confidence)
- `_terrain_noise.py::carve_river_path()` -- Current A* river carving
- `environment.py::handle_create_water()` -- Spline-based water mesh with flow vertex colors
- `terrain_features.py::generate_waterfall()` -- Step-down waterfall with pool
- `terrain_features.py::generate_swamp_terrain()` -- Swamp terrain with water zones
- `coastline.py` -- Coastline terrain strips with material zones
- `shader_templates.py::generate_water_shader()` -- Current basic URP water shader
- `vfx_mastery_templates.py` -- Water caustics projector

---

## Metadata

**Confidence breakdown:**
- River generation algorithms: HIGH -- based on published algorithms + existing codebase
- Lake generation: HIGH -- flood-fill is well-established, multiple open-source implementations
- Waterfall integration: HIGH -- extending existing `generate_waterfall()` pattern
- Unity URP water rendering: HIGH -- verified against official Unity docs + shader graph samples
- Dark fantasy variants: MEDIUM -- parameter presets based on game art direction, need visual validation
- Performance budgets: MEDIUM -- estimates based on general URP profiling, need actual measurement

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain, algorithms don't change frequently)
