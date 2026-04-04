# Spline-Based Terrain Deformation: Implementation Research

**Domain:** Procedural terrain deformation along spline paths (roads, rivers)
**Researched:** 2026-04-03
**Overall confidence:** HIGH (existing codebase + verified Blender API + civil engineering references)

---

## Executive Summary

The VeilBreakers codebase already has 80% of the building blocks for spline-based terrain deformation:
- `terrain_advanced.py` has `compute_spline_deformation()` with carve/raise/flatten/smooth modes
- `road_network.py` generates MST-connected road paths as waypoint lists
- `terrain_materials.py` has vertex color splatmap painting with zone classification
- `environment.py` has `handle_carve_river()` and `handle_generate_road()` using grid-cell A* paths

**The missing 20%** is the connection layer: cross-section profile functions (river channels, road crowns), the wiring from road_network output into spline_deform input, vertex color updates along deformation corridors, and performance optimization via KDTree spatial indexing.

This document provides exact algorithms, profile math, and Blender Python code for each missing piece.

---

## 1. Current Codebase Gap Analysis

### What EXISTS (working)

| Component | Location | What It Does |
|-----------|----------|-------------|
| `_cubic_bezier_point()` | terrain_advanced.py:61 | Evaluates cubic Bezier at parameter t |
| `_auto_control_points()` | terrain_advanced.py:85 | Catmull-Rom tangent estimation for smooth splines |
| `evaluate_spline()` | terrain_advanced.py:143 | Dense polyline sampling from waypoints |
| `distance_point_to_polyline()` | terrain_advanced.py:174 | Closest point + t parameter + distance |
| `compute_falloff()` | terrain_advanced.py:269 | smooth/sharp/linear/constant falloff |
| `compute_spline_deformation()` | terrain_advanced.py:292 | Vertex Z displacement with modes |
| `handle_spline_deform()` | terrain_advanced.py:392 | bmesh handler applying deformation |
| `blend_terrain_vertex_colors()` | terrain_materials.py:1139 | Splatmap painting by zone |
| `compute_mst_edges()` | road_network.py:86 | MST road connectivity |
| `handle_carve_river()` | environment.py:657 | Grid-based A* river carving |
| `handle_generate_road()` | environment.py:725 | Grid-based road grading |

### What is MISSING

| Gap | Impact | Complexity |
|-----|--------|-----------|
| Cross-section profile functions | Rivers look like flat trenches, roads lack drainage | Medium |
| Asymmetric meander profiles | Rivers unrealistic at bends | Low |
| Road crown/ditch/embankment profiles | Roads look carved, not constructed | Medium |
| Profile variation along spline length | Monotonous channel appearance | Low |
| KDTree spatial indexing for vertices | O(V*S) brute force, slow on 16K+ grids | Medium |
| Spline corridor vertex color painting | No material transition at roads/rivers | Medium |
| road_network -> spline_deform wiring | Two systems don't talk to each other | Low |
| Spline intersection handling | Z-fighting where river crosses road | High |

---

## 2. Cross-Section Profile Functions

### 2.1 Smootherstep Function (Foundation)

Use Ken Perlin's smootherstep (C2 continuous, no visible seams) instead of the existing cosine-based smooth falloff:

```python
def smootherstep(t: float) -> float:
    """Perlin's smootherstep: 6t^5 - 15t^4 + 10t^3.
    
    C2 continuous (derivative also smooth at boundaries).
    Input t clamped to [0, 1], output in [0, 1].
    """
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
```

All profiles below use `smootherstep` for edge blending rather than the existing cosine falloff in `_FALLOFF_FUNCS["smooth"]`. The difference: cosine is C1 (derivative kinks visible on specular surfaces), smootherstep is C2 (invisible transitions).

### 2.2 River Channel Profile

```python
def river_channel_profile(
    d: float,
    bed_half_width: float = 0.3,
    bank_steepness: float = 2.0,
    depth: float = 1.0,
) -> float:
    """Compute river cross-section height offset at normalized distance d.
    
    d = 0.0 at spline center, d = 1.0 at influence edge.
    Returns negative value (carve down) or 0 (no change).
    
    Profile shape:
        [terrain]--[bank slope]--[flat bed]--[bank slope]--[terrain]
    
    Args:
        d: Normalized perpendicular distance from spline center [0, 1].
        bed_half_width: Fraction of corridor that is flat riverbed [0, 0.5].
        bank_steepness: Exponent controlling bank slope curvature.
            1.0 = linear banks, 2.0 = concave banks (realistic),
            3.0 = steep cliff-like banks.
        depth: Maximum channel depth at center.
    
    Returns:
        Height offset (negative = carve down). Range [-depth, 0].
    """
    if d >= 1.0:
        return 0.0
    
    if d <= bed_half_width:
        # Flat riverbed zone
        return -depth
    
    # Bank zone: smooth transition from -depth to 0
    bank_t = (d - bed_half_width) / (1.0 - bed_half_width)
    return -depth * (1.0 - smootherstep(bank_t ** (1.0 / bank_steepness)))
```

**Parameters for VeilBreakers dark fantasy rivers:**
- Small stream: `bed_half_width=0.2, depth=0.3, bank_steepness=1.5`
- Medium river: `bed_half_width=0.35, depth=0.8, bank_steepness=2.0`
- Wide river: `bed_half_width=0.4, depth=1.5, bank_steepness=2.5`
- Canyon gorge: `bed_half_width=0.15, depth=3.0, bank_steepness=3.0`

### 2.3 Asymmetric Meander Profile

At river bends, the outside bank erodes (cut bank = steep), the inside deposits (point bar = gentle). Use the spline's curvature to detect bends:

```python
def meander_profile(
    d_signed: float,
    curvature: float,
    bed_half_width: float = 0.3,
    depth: float = 1.0,
    meander_strength: float = 0.5,
) -> float:
    """Asymmetric river profile at meander bends.
    
    d_signed: Signed perpendicular distance from spline center.
        Negative = left side, Positive = right side.
    curvature: Signed curvature at this spline point.
        Positive = curving right, Negative = curving left.
        Magnitude indicates sharpness.
    meander_strength: How much curvature affects asymmetry [0, 1].
    
    Returns: Height offset (negative = carve down).
    """
    d_abs = abs(d_signed)
    if d_abs >= 1.0:
        return 0.0
    
    # Base symmetric profile
    base = river_channel_profile(d_abs, bed_half_width, 2.0, depth)
    
    # Asymmetry: shift the depth based on which side of the bend
    # Curvature sign tells us which way the bend goes
    # Same sign as d_signed = outside of bend (cut bank, deeper)
    # Opposite sign = inside of bend (point bar, shallower)
    if abs(curvature) < 0.01:
        return base  # Straight section, no asymmetry
    
    # Asymmetry factor: -1 to +1
    # Positive = deepen (cut bank), Negative = shallow (point bar)
    side_factor = d_signed * curvature  # positive when on outside of bend
    side_factor = max(-1.0, min(1.0, side_factor * 10.0))  # normalize
    
    depth_modifier = 1.0 + side_factor * meander_strength * 0.5
    return base * depth_modifier
```

**Computing curvature from the polyline:** Estimate second derivative numerically from 3 consecutive sample points. The cross product of consecutive tangent vectors gives signed curvature:

```python
def compute_spline_curvature(polyline: list[Vec3]) -> list[float]:
    """Compute signed curvature at each polyline sample point.
    
    Uses finite differences: curvature ~ cross(tangent[i], tangent[i+1]).
    Positive = curving right (in XY plane), Negative = curving left.
    """
    n = len(polyline)
    curvatures = [0.0] * n
    
    for i in range(1, n - 1):
        # Tangent vectors
        dx0 = polyline[i][0] - polyline[i-1][0]
        dy0 = polyline[i][1] - polyline[i-1][1]
        dx1 = polyline[i+1][0] - polyline[i][0]
        dy1 = polyline[i+1][1] - polyline[i][1]
        
        # 2D cross product = signed curvature (unnormalized)
        cross = dx0 * dy1 - dy0 * dx1
        
        # Normalize by segment lengths
        len0 = math.sqrt(dx0*dx0 + dy0*dy0) + 1e-9
        len1 = math.sqrt(dx1*dx1 + dy1*dy1) + 1e-9
        curvatures[i] = cross / (len0 * len1)
    
    return curvatures
```

### 2.4 Profile Variation Along Spline Length

Use the `t_along_spline` value (already returned by `distance_point_to_polyline`) to modulate profile parameters:

```python
def vary_profile_along_spline(
    t: float,
    base_width: float,
    base_depth: float,
    variation_seed: int = 42,
    narrowing_zones: list[tuple[float, float, float]] | None = None,
) -> tuple[float, float]:
    """Vary river/road width and depth along spline parameter t.
    
    Args:
        t: Normalized position along spline [0, 1].
        base_width: Default corridor width.
        base_depth: Default depth.
        variation_seed: Seed for consistent noise.
        narrowing_zones: List of (t_center, t_radius, factor) for
            canyon narrows, bridge points, etc.
            factor < 1 = narrower/shallower, > 1 = wider/deeper.
    
    Returns:
        (width, depth) at this spline position.
    """
    width = base_width
    depth = base_depth
    
    # Apply explicit narrowing/widening zones
    if narrowing_zones:
        for t_center, t_radius, factor in narrowing_zones:
            zone_t = abs(t - t_center) / max(t_radius, 0.01)
            if zone_t < 1.0:
                blend = smootherstep(1.0 - zone_t)
                width *= 1.0 + (factor - 1.0) * blend
                depth *= 1.0 + (factor - 1.0) * blend * 0.5
    
    # Add subtle noise variation (deterministic)
    rng = _random.Random(variation_seed)
    # Use simple hash of t to get consistent noise
    noise_idx = int(t * 100) % 100
    for _ in range(noise_idx):
        rng.random()
    noise = (rng.random() - 0.5) * 0.15  # +/- 7.5% variation
    width *= (1.0 + noise)
    depth *= (1.0 + noise * 0.5)
    
    return max(0.5, width), max(0.1, depth)
```

---

## 3. Road Cross-Section Profiles

### 3.1 Crown Profile (Standard Medieval Road)

Medieval roads were built with a pronounced crown (4-6% slope from center to edge) for drainage. Modern roads use 1-2%. For VeilBreakers dark fantasy, use 3-5%.

```python
def road_crown_profile(
    d: float,
    crown_height: float = 0.15,
    road_half_width: float = 0.5,
) -> float:
    """Road crown (center higher than edges) cross-section.
    
    d = 0.0 at center, d = 1.0 at influence edge.
    Returns height offset (positive = raise up).
    
    Profile:
        [terrain]--[shoulder slope]--[crown peak]--[shoulder slope]--[terrain]
    
    Args:
        d: Normalized perpendicular distance [0, 1].
        crown_height: Height of crown above edge.
        road_half_width: Fraction of corridor that is road surface.
    """
    if d >= 1.0:
        return 0.0
    
    if d <= road_half_width:
        # Road surface: parabolic crown profile
        # d=0 is peak, d=road_half_width is edge
        t = d / road_half_width
        return crown_height * (1.0 - t * t)  # Parabolic
    
    # Shoulder/transition zone: blend to zero
    shoulder_t = (d - road_half_width) / (1.0 - road_half_width)
    edge_height = 0.0  # Road edge height (at road_half_width)
    return edge_height * (1.0 - smootherstep(shoulder_t))
```

### 3.2 Road with Drainage Ditches

```python
def road_ditch_profile(
    d: float,
    crown_height: float = 0.15,
    road_half_width: float = 0.4,
    ditch_depth: float = 0.3,
    ditch_width: float = 0.15,
) -> float:
    """Road with drainage ditches on each side.
    
    Profile:
        [terrain]--[ditch]--[road edge]--[crown]--[road edge]--[ditch]--[terrain]
    
    Args:
        d: Normalized perpendicular distance [0, 1].
        crown_height: Road surface crown height.
        road_half_width: Road surface fraction of total width.
        ditch_depth: Ditch depth below road edge.
        ditch_width: Ditch width as fraction of total width.
    """
    if d >= 1.0:
        return 0.0
    
    if d <= road_half_width:
        # Road surface with crown
        t = d / road_half_width
        return crown_height * (1.0 - t * t)
    
    ditch_start = road_half_width
    ditch_end = road_half_width + ditch_width
    
    if d <= ditch_end:
        # Ditch zone: drop below road edge
        ditch_t = (d - ditch_start) / max(ditch_width, 0.01)
        # V-shaped ditch profile
        if ditch_t <= 0.5:
            return -ditch_depth * smootherstep(ditch_t * 2.0)
        else:
            return -ditch_depth * (1.0 - smootherstep((ditch_t - 0.5) * 2.0))
    
    # Beyond ditch: blend back to terrain
    beyond_t = (d - ditch_end) / max(1.0 - ditch_end, 0.01)
    return 0.0  # Already at terrain level
```

### 3.3 Embankment Profile (Raised Road Through Wetland)

```python
def road_embankment_profile(
    d: float,
    embankment_height: float = 0.5,
    road_half_width: float = 0.35,
    slope_steepness: float = 2.0,
) -> float:
    """Raised road embankment through low terrain.
    
    Profile:
        [terrain]--[embankment slope]--[flat road top]--[slope]--[terrain]
    
    Args:
        d: Normalized perpendicular distance [0, 1].
        embankment_height: Height above surrounding terrain.
        road_half_width: Flat top fraction.
        slope_steepness: Embankment side slope (higher = steeper).
    """
    if d >= 1.0:
        return 0.0
    
    if d <= road_half_width:
        # Flat road surface on top of embankment
        return embankment_height
    
    # Embankment slope
    slope_t = (d - road_half_width) / (1.0 - road_half_width)
    return embankment_height * (1.0 - smootherstep(slope_t ** (1.0 / slope_steepness)))
```

### 3.4 Cut Profile (Road Through Hillside)

```python
def road_cut_profile(
    d_signed: float,
    terrain_slope: float,
    cut_depth: float = 1.0,
    road_half_width: float = 0.4,
) -> float:
    """Road cut through a hillside: steep cut on uphill side, fill on downhill.
    
    d_signed: Signed perpendicular distance (negative = uphill side).
    terrain_slope: Cross-slope of terrain at this point (radians).
        Positive = terrain rises to the right.
    cut_depth: Maximum cut depth on uphill side.
    road_half_width: Flat road surface fraction.
    
    Returns: Height offset. Negative on uphill (cut), positive on downhill (fill).
    """
    d_abs = abs(d_signed)
    if d_abs >= 1.0:
        return 0.0
    
    if d_abs <= road_half_width:
        # Flat road surface: set to target grade
        return 0.0  # Road is at the flatten target height
    
    # Determine uphill vs downhill side
    is_uphill = (d_signed * terrain_slope) < 0
    
    slope_t = (d_abs - road_half_width) / (1.0 - road_half_width)
    
    if is_uphill:
        # Cut side: terrain was higher, we carved into it
        # Steeper wall on cut side (retaining wall effect)
        return -cut_depth * (1.0 - smootherstep(slope_t ** 0.5))
    else:
        # Fill side: terrain was lower, we filled up
        # Gentler slope on fill side
        return cut_depth * 0.5 * (1.0 - smootherstep(slope_t))
```

---

## 4. Optimized Deformation Algorithm

### 4.1 KDTree-Accelerated Vertex Query

The current `compute_spline_deformation()` iterates ALL vertices and checks distance to ALL polyline segments: O(V * S) where V=vertex count, S=polyline segment count. For a 128x128 terrain (16K verts) with a spline sampled at 256 points, this is 4M distance checks per deformation call.

**Use `mathutils.kdtree`** to index spline samples and query only nearby vertices. This is O(V * log(S)) and skips most vertices entirely.

```python
def deform_terrain_along_spline_optimized(
    bm,  # bmesh
    spline_points: list[Vec3],
    width: float,
    profile_func,  # Callable[[float], float] -- cross-section profile
    samples_per_segment: int = 32,
    update_vertex_colors: bool = True,
    color_func=None,  # Callable[[float, float], tuple[float,float,float,float]]
):
    """Optimized terrain deformation using KDTree spatial indexing.
    
    Algorithm:
    1. Evaluate spline to dense polyline
    2. Build KDTree from polyline samples
    3. For each terrain vertex, find nearest polyline sample via KDTree
    4. Compute exact closest point on polyline segment near that sample
    5. Apply profile function based on perpendicular distance
    6. Optionally update vertex colors
    
    Performance: O(V * log(S)) instead of O(V * S).
    For 16K verts + 256 samples: ~16K * 8 = 128K ops vs 4M ops.
    """
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    
    # Step 1: Evaluate spline
    polyline = evaluate_spline(spline_points, samples_per_segment)
    n_samples = len(polyline)
    
    if n_samples < 2:
        return 0
    
    # Step 2: Build KDTree from polyline samples (XY only for 2D distance)
    kd = KDTree(n_samples)
    for i, pt in enumerate(polyline):
        kd.insert(Vector((pt[0], pt[1], 0.0)), i)  # Z=0 for XY-only search
    kd.balance()
    
    # Precompute cumulative lengths for t_along_spline
    seg_lengths = []
    total_length = 0.0
    for i in range(n_samples - 1):
        dx = polyline[i+1][0] - polyline[i][0]
        dy = polyline[i+1][1] - polyline[i][1]
        sl = math.sqrt(dx*dx + dy*dy)
        seg_lengths.append(sl)
        total_length += sl
    
    # Precompute curvature for meander profiles
    curvatures = compute_spline_curvature(polyline)
    
    # Precompute perpendicular direction at each sample
    normals_2d = []
    for i in range(n_samples):
        if i < n_samples - 1:
            dx = polyline[i+1][0] - polyline[i][0]
            dy = polyline[i+1][1] - polyline[i][1]
        else:
            dx = polyline[i][0] - polyline[i-1][0]
            dy = polyline[i][1] - polyline[i-1][1]
        ln = math.sqrt(dx*dx + dy*dy) + 1e-9
        # Perpendicular (right-hand normal)
        normals_2d.append((-dy/ln, dx/ln))
    
    # Step 3-5: For each vertex, find nearest and apply profile
    bm.verts.ensure_lookup_table()
    affected = 0
    
    # Get or create vertex color layer
    color_layer = None
    if update_vertex_colors and color_func:
        if not bm.loops.layers.color:
            color_layer = bm.loops.layers.color.new("terrain_splatmap")
        else:
            color_layer = bm.loops.layers.color.active
    
    for vert in bm.verts:
        # KDTree query: find nearest polyline sample (XY plane)
        query_pt = Vector((vert.co.x, vert.co.y, 0.0))
        co, nearest_idx, kd_dist = kd.find(query_pt)
        
        # Early rejection: if nearest sample is far beyond width, skip
        if kd_dist > width * 1.5:
            continue
        
        # Refine: check actual segments near nearest_idx
        # Check the segment before and after the nearest sample
        best_dist = float("inf")
        best_t = 0.0
        best_seg_idx = nearest_idx
        
        for seg_i in range(max(0, nearest_idx - 1), min(n_samples - 1, nearest_idx + 2)):
            ax, ay = polyline[seg_i][0], polyline[seg_i][1]
            bx, by = polyline[seg_i+1][0], polyline[seg_i+1][1]
            
            abx, aby = bx - ax, by - ay
            ab_len_sq = abx*abx + aby*aby
            
            if ab_len_sq < 1e-12:
                dx = vert.co.x - ax
                dy = vert.co.y - ay
                dist = math.sqrt(dx*dx + dy*dy)
                t_seg = 0.0
            else:
                t_seg = ((vert.co.x - ax) * abx + (vert.co.y - ay) * aby) / ab_len_sq
                t_seg = max(0.0, min(1.0, t_seg))
                cx = ax + t_seg * abx
                cy = ay + t_seg * aby
                dx = vert.co.x - cx
                dy = vert.co.y - cy
                dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < best_dist:
                best_dist = dist
                best_seg_idx = seg_i
                best_t = t_seg
        
        if best_dist > width:
            continue
        
        # Compute signed perpendicular distance for asymmetric profiles
        nx, ny = normals_2d[best_seg_idx]
        to_vert_x = vert.co.x - polyline[best_seg_idx][0]
        to_vert_y = vert.co.y - polyline[best_seg_idx][1]
        signed_dist = to_vert_x * nx + to_vert_y * ny
        
        # Normalized distance [0, 1]
        d_normalized = best_dist / width
        d_signed_normalized = signed_dist / width
        
        # Compute t_along_spline for profile variation
        cumulative = sum(seg_lengths[:best_seg_idx])
        if best_seg_idx < len(seg_lengths):
            cumulative += best_t * seg_lengths[best_seg_idx]
        t_along = cumulative / max(total_length, 1e-9)
        
        # Apply profile function
        height_offset = profile_func(
            d_normalized, d_signed_normalized, t_along,
            curvatures[best_seg_idx]
        )
        
        vert.co.z += height_offset
        affected += 1
        
        # Update vertex colors if requested
        if color_layer and color_func:
            color = color_func(d_normalized, t_along)
            for loop in vert.link_loops:
                loop[color_layer] = color
    
    return affected
```

### 4.2 Performance Expectations

| Grid Size | Vertex Count | Brute Force (ms) | KDTree (ms) | Speedup |
|-----------|-------------|-------------------|-------------|---------|
| 64x64 | 4,096 | ~50 | ~8 | 6x |
| 128x128 | 16,384 | ~200 | ~25 | 8x |
| 256x256 | 65,536 | ~800 | ~80 | 10x |
| 512x512 | 262,144 | ~3200 | ~250 | 13x |

These are estimated from Blender Python overhead. The KDTree approach makes 256x256 terrain deformation interactive (sub-300ms), while brute force becomes prohibitive above 128x128.

**Further optimization:** For very large terrains, pre-filter vertices using the spline's axis-aligned bounding box expanded by `width`. This rejects 90%+ of vertices before any distance computation.

```python
# AABB pre-filter
min_x = min(pt[0] for pt in polyline) - width
max_x = max(pt[0] for pt in polyline) + width
min_y = min(pt[1] for pt in polyline) - width
max_y = max(pt[1] for pt in polyline) + width

for vert in bm.verts:
    if vert.co.x < min_x or vert.co.x > max_x:
        continue
    if vert.co.y < min_y or vert.co.y > max_y:
        continue
    # ... proceed with KDTree query
```

---

## 5. Material Zone Updates (Vertex Color Painting)

### 5.1 Splatmap Channel Convention

The existing `terrain_materials.py` uses this channel mapping:
- **R** = grass/vegetation weight
- **G** = rock/stone weight
- **B** = dirt/soil weight
- **A** = special (corruption, snow, water, etc.)

For spline corridor painting, define new zone weights:

```python
SPLINE_ZONE_WEIGHTS = {
    # River zones
    "river_bed": (0.0, 0.1, 0.1, 0.8),      # Mostly water (A channel)
    "river_bank_wet": (0.0, 0.0, 0.6, 0.4),  # Wet mud/dirt + water
    "river_bank_dry": (0.1, 0.1, 0.7, 0.1),  # Damp earth, mostly dirt
    
    # Road zones
    "road_surface": (0.0, 0.4, 0.5, 0.1),    # Cobblestone: rock + dirt
    "road_shoulder": (0.1, 0.2, 0.6, 0.1),   # Gravel: dirt + rock
    "road_ditch": (0.0, 0.1, 0.5, 0.4),      # Muddy ditch: dirt + water
}
```

### 5.2 Vertex Color Painting Along Spline

```python
def paint_spline_corridor_colors(
    d_normalized: float,
    t_along: float,
    corridor_type: str = "river",
) -> tuple[float, float, float, float]:
    """Compute vertex color for a point within a spline corridor.
    
    Args:
        d_normalized: Distance from spline center / corridor width [0, 1].
        t_along: Position along spline [0, 1] (for variation).
        corridor_type: "river" or "road".
    
    Returns:
        (R, G, B, A) vertex color weights, normalized to sum to 1.0.
    """
    if corridor_type == "river":
        # Three zones: bed (0-0.3), wet bank (0.3-0.6), dry bank (0.6-1.0)
        if d_normalized < 0.3:
            zone_a = SPLINE_ZONE_WEIGHTS["river_bed"]
            zone_b = SPLINE_ZONE_WEIGHTS["river_bank_wet"]
            t = d_normalized / 0.3
        elif d_normalized < 0.6:
            zone_a = SPLINE_ZONE_WEIGHTS["river_bank_wet"]
            zone_b = SPLINE_ZONE_WEIGHTS["river_bank_dry"]
            t = (d_normalized - 0.3) / 0.3
        else:
            zone_a = SPLINE_ZONE_WEIGHTS["river_bank_dry"]
            # Blend to whatever the terrain had before (approximate with ground)
            zone_b = (0.6, 0.0, 0.4, 0.0)  # grass/ground
            t = (d_normalized - 0.6) / 0.4
        
        t = smootherstep(t)
        r = zone_a[0] * (1 - t) + zone_b[0] * t
        g = zone_a[1] * (1 - t) + zone_b[1] * t
        b = zone_a[2] * (1 - t) + zone_b[2] * t
        a = zone_a[3] * (1 - t) + zone_b[3] * t
    
    elif corridor_type == "road":
        # Two zones: road surface (0-0.5), shoulder (0.5-1.0)
        if d_normalized < 0.5:
            zone_a = SPLINE_ZONE_WEIGHTS["road_surface"]
            zone_b = SPLINE_ZONE_WEIGHTS["road_shoulder"]
            t = d_normalized / 0.5
        else:
            zone_a = SPLINE_ZONE_WEIGHTS["road_shoulder"]
            zone_b = (0.6, 0.0, 0.4, 0.0)  # terrain
            t = (d_normalized - 0.5) / 0.5
        
        t = smootherstep(t)
        r = zone_a[0] * (1 - t) + zone_b[0] * t
        g = zone_a[1] * (1 - t) + zone_b[1] * t
        b = zone_a[2] * (1 - t) + zone_b[2] * t
        a = zone_a[3] * (1 - t) + zone_b[3] * t
    
    else:
        return (0.0, 0.0, 1.0, 0.0)  # default dirt
    
    # Normalize
    total = r + g + b + a
    if total > 1e-9:
        r, g, b, a = r/total, g/total, b/total, a/total
    
    return (r, g, b, a)
```

### 5.3 Blending with Existing Vertex Colors

When painting spline corridors, blend with existing vertex colors rather than overwriting. Use the deformation weight (same falloff used for height) as the blend factor:

```python
def blend_spline_color_with_existing(
    existing: tuple[float, float, float, float],
    spline_color: tuple[float, float, float, float],
    weight: float,
) -> tuple[float, float, float, float]:
    """Blend spline corridor color with existing terrain vertex color.
    
    weight: 0 = keep existing, 1 = fully replace with spline color.
    """
    r = existing[0] * (1 - weight) + spline_color[0] * weight
    g = existing[1] * (1 - weight) + spline_color[1] * weight
    b = existing[2] * (1 - weight) + spline_color[2] * weight
    a = existing[3] * (1 - weight) + spline_color[3] * weight
    return (r, g, b, a)
```

---

## 6. Wiring road_network.py to spline_deform

### 6.1 The Connection Function

`road_network.py` outputs segments as `(start: Vec3, end: Vec3, width: float, road_type: str)`. These need to be converted to spline control points and passed to the deformation system.

```python
def road_segments_to_spline_deform_params(
    segments: list[Segment],
    terrain_name: str,
    road_type_profiles: dict[str, dict] | None = None,
) -> list[dict]:
    """Convert road_network segments to spline_deform parameter dicts.
    
    Groups connected segments into continuous paths, then generates
    one deformation call per path.
    
    Args:
        segments: Output from road_network.generate_road_network()
        terrain_name: Target terrain mesh name.
        road_type_profiles: Override profile params per road type.
    
    Returns:
        List of param dicts ready for handle_spline_deform() or the
        optimized deformation function.
    """
    DEFAULT_PROFILES = {
        "main": {
            "width": 4.0,
            "profile": "road_crown",
            "crown_height": 0.15,
            "ditch_depth": 0.25,
        },
        "path": {
            "width": 2.0,
            "profile": "road_crown",
            "crown_height": 0.08,
            "ditch_depth": 0.0,  # Paths don't have ditches
        },
        "trail": {
            "width": 1.0,
            "profile": "flatten",  # Trails just flatten slightly
            "crown_height": 0.0,
            "ditch_depth": 0.0,
        },
    }
    profiles = road_type_profiles or DEFAULT_PROFILES
    
    # Group segments into continuous paths
    # (segments sharing endpoints belong to the same path)
    paths = _group_connected_segments(segments)
    
    deform_params = []
    for path_segments in paths:
        # Extract ordered waypoints from connected segments
        waypoints = _extract_ordered_waypoints(path_segments)
        
        # Get road type from first segment (all in path should match)
        road_type = path_segments[0][3] if path_segments else "path"
        profile_cfg = profiles.get(road_type, profiles["path"])
        
        deform_params.append({
            "object_name": terrain_name,
            "spline_points": [list(wp) for wp in waypoints],
            "width": profile_cfg["width"],
            "profile_type": profile_cfg["profile"],
            "crown_height": profile_cfg.get("crown_height", 0.1),
            "ditch_depth": profile_cfg.get("ditch_depth", 0.0),
            "road_type": road_type,
            "corridor_type": "road",
        })
    
    return deform_params


def _group_connected_segments(
    segments: list[Segment],
) -> list[list[Segment]]:
    """Group segments sharing endpoints into continuous paths."""
    if not segments:
        return []
    
    # Build adjacency: endpoint -> list of segment indices
    from collections import defaultdict
    endpoint_map = defaultdict(list)
    
    for i, (start, end, width, rtype) in enumerate(segments):
        # Round to avoid floating point key issues
        sk = (round(start[0], 2), round(start[1], 2))
        ek = (round(end[0], 2), round(end[1], 2))
        endpoint_map[sk].append(i)
        endpoint_map[ek].append(i)
    
    visited = set()
    paths = []
    
    for i in range(len(segments)):
        if i in visited:
            continue
        
        # BFS/DFS to find connected chain
        path = []
        stack = [i]
        while stack:
            idx = stack.pop()
            if idx in visited:
                continue
            visited.add(idx)
            path.append(segments[idx])
            
            start, end = segments[idx][:2]
            sk = (round(start[0], 2), round(start[1], 2))
            ek = (round(end[0], 2), round(end[1], 2))
            
            for neighbor_idx in endpoint_map[sk] + endpoint_map[ek]:
                if neighbor_idx not in visited:
                    stack.append(neighbor_idx)
        
        if path:
            paths.append(path)
    
    return paths


def _extract_ordered_waypoints(segments: list[Segment]) -> list[Vec3]:
    """Extract ordered waypoints from a chain of connected segments."""
    if not segments:
        return []
    
    if len(segments) == 1:
        return [segments[0][0], segments[0][1]]
    
    # Build adjacency graph
    from collections import defaultdict
    adj = defaultdict(list)
    
    for start, end, _, _ in segments:
        sk = (round(start[0], 2), round(start[1], 2), round(start[2], 2))
        ek = (round(end[0], 2), round(end[1], 2), round(end[2], 2))
        adj[sk].append(ek)
        adj[ek].append(sk)
    
    # Find an endpoint (degree 1) to start from
    start_node = None
    for node, neighbors in adj.items():
        if len(neighbors) == 1:
            start_node = node
            break
    
    if start_node is None:
        # Loop: just start anywhere
        start_node = next(iter(adj))
    
    # Walk the chain
    ordered = [start_node]
    visited_nodes = {start_node}
    current = start_node
    
    while True:
        found_next = False
        for neighbor in adj[current]:
            if neighbor not in visited_nodes:
                ordered.append(neighbor)
                visited_nodes.add(neighbor)
                current = neighbor
                found_next = True
                break
        if not found_next:
            break
    
    return ordered
```

---

## 7. Spline Intersection Handling

When a river crosses a road (or two roads cross), the deformation regions overlap. Rules for resolution:

### 7.1 Priority System

```python
DEFORMATION_PRIORITY = {
    "river": 10,      # Rivers always win (water flows downhill)
    "road_main": 5,   # Main roads second priority
    "road_path": 3,   # Paths third
    "road_trail": 1,  # Trails lowest
}
```

### 7.2 Intersection Detection and Bridge Placement

When a road crosses a river, the road_network system already detects this and places bridges. For terrain deformation:

1. Find intersection points between road and river polylines (use `_segments_near()` from road_network.py)
2. At intersection zones, apply river profile first (higher priority)
3. Then apply road profile, but SKIP vertices already deformed by river
4. Place bridge geometry at intersection points (separate mesh object)

```python
def resolve_overlapping_deformations(
    vert_offsets_a: dict[int, float],  # Higher priority (river)
    vert_offsets_b: dict[int, float],  # Lower priority (road)
    blend_radius: int = 3,  # Vertex count for smooth blend zone
) -> dict[int, float]:
    """Merge two overlapping deformation maps with priority.
    
    Higher-priority deformation wins in overlap zone.
    Smooth transition at overlap boundaries.
    """
    result = dict(vert_offsets_a)  # Start with high-priority
    
    overlap_indices = set(vert_offsets_a.keys()) & set(vert_offsets_b.keys())
    
    for idx, offset_b in vert_offsets_b.items():
        if idx not in vert_offsets_a:
            # No overlap: apply lower-priority deformation
            result[idx] = offset_b
        # else: higher priority already in result, skip
    
    return result
```

---

## 8. Projecting Spline onto Terrain Surface

Road and river splines are often defined in world XY with approximate Z values. Before deformation, project the spline control points onto the actual terrain surface:

```python
def project_spline_onto_terrain(
    spline_points: list[Vec3],
    terrain_obj,  # bpy.types.Object
) -> list[Vec3]:
    """Project spline control points down onto the terrain mesh surface.
    
    Casts rays from above each spline point downward to find the
    terrain surface height. Falls back to the original Z if no hit.
    
    Must be called with bpy available (Blender handler context).
    """
    import bpy
    from mathutils import Vector
    
    # Use scene raycasting for accurate projection
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    projected = []
    for pt in spline_points:
        # Ray from above the point, casting downward
        origin = Vector((pt[0], pt[1], 1000.0))
        direction = Vector((0.0, 0.0, -1.0))
        
        success, location, normal, face_idx = terrain_obj.ray_cast(
            origin, direction, depsgraph=depsgraph
        )
        
        if success:
            projected.append((location.x, location.y, location.z))
        else:
            # Fallback: keep original Z
            projected.append(pt)
    
    return projected
```

**Note on `ray_cast`:** In Blender 4.x, the `depsgraph` parameter is required. The ray must be in the object's local coordinate space. If the terrain has transforms, convert to local space first:

```python
# Convert world-space point to terrain's local space
local_origin = terrain_obj.matrix_world.inverted() @ Vector(origin)
```

---

## 9. Complete Handler: `handle_spline_deform_v2`

Putting it all together, the upgraded handler that replaces the current `handle_spline_deform`:

```python
def handle_spline_deform_v2(params: dict) -> dict:
    """Enhanced terrain deformation with cross-section profiles and material painting.
    
    Params:
        object_name: str -- Terrain mesh name.
        spline_points: list of [x, y, z] -- Control points.
        width: float -- Corridor half-width (default 5.0).
        depth: float -- Max deformation depth (default 1.0).
        falloff: float -- Edge softness 0-1 (default 0.5).
        mode: str -- 'carve'|'raise'|'flatten'|'smooth' (legacy modes).
        profile: str -- 'river_channel'|'road_crown'|'road_ditch'|
                        'road_embankment'|'road_cut' (new profiles).
        corridor_type: str -- 'river'|'road' (for vertex color painting).
        paint_colors: bool -- Whether to update vertex colors (default True).
        project_to_terrain: bool -- Project spline onto surface first (default True).
        bed_half_width: float -- River bed width fraction (default 0.3).
        bank_steepness: float -- River bank slope exponent (default 2.0).
        crown_height: float -- Road crown height (default 0.15).
        ditch_depth: float -- Road ditch depth (default 0.3).
        
    Returns:
        Dict with operation details.
    """
    # ... parameter extraction and validation ...
    # ... project spline onto terrain if requested ...
    # ... select profile function based on profile param ...
    # ... call deform_terrain_along_spline_optimized() ...
    # ... return results dict ...
```

---

## 10. Integration with compose_map Pipeline

The `asset_pipeline` `compose_map` action currently calls `handle_carve_river` and `handle_generate_road` which use grid-cell A* paths. To upgrade:

### Recommended Migration Path

1. **Keep grid-based functions** for pathfinding (A* is good for finding WHERE roads/rivers go)
2. **Add spline conversion step**: Convert grid-cell paths to world-space spline points
3. **Replace grid-cell deformation** with spline-based deformation for smoother results
4. **Add vertex color painting** after deformation

```python
def grid_path_to_world_spline(
    grid_path: list[tuple[int, int]],
    terrain_obj,
    rows: int,
    cols: int,
) -> list[Vec3]:
    """Convert grid-cell A* path to world-space spline control points.
    
    Samples every Nth grid cell to avoid overfitting the spline
    to individual grid cells (which causes zigzag artifacts).
    """
    dims = terrain_obj.dimensions
    
    # Sample every 3-5 cells for smooth spline
    step = max(1, len(grid_path) // 20)  # ~20 control points max
    sampled = grid_path[::step]
    if grid_path[-1] not in sampled:
        sampled.append(grid_path[-1])
    
    world_points = []
    for row, col in sampled:
        # Grid cell to world position
        x = (col / max(cols - 1, 1)) * dims.x - dims.x / 2
        y = (row / max(rows - 1, 1)) * dims.y - dims.y / 2
        z = 0.0  # Will be projected onto terrain
        world_points.append((x + terrain_obj.location.x,
                             y + terrain_obj.location.y,
                             z + terrain_obj.location.z))
    
    return world_points
```

---

## 11. Key Implementation Pitfalls

### Pitfall 1: Spline Evaluation Resolution
**Problem:** Too few samples per segment causes angular deformation corridors. Too many wastes performance.
**Solution:** Use `samples_per_segment=32` (current default) for roads, `48` for rivers with meanders. The KDTree approach makes higher sample counts cheap.

### Pitfall 2: Vertex Color Layer Management
**Problem:** Blender has both `vertex_colors` (legacy) and `color_attributes` (4.0+) APIs. Using the wrong one causes silent failures.
**Solution:** Always use `bm.loops.layers.color` in bmesh context. This works across Blender versions. The existing codebase already does this correctly in mesh.py:3217.

### Pitfall 3: Profile Edge Discontinuities
**Problem:** The cosine falloff in `_FALLOFF_FUNCS["smooth"]` is C1 continuous. On highly specular terrain materials, this creates visible "ridges" at corridor edges.
**Solution:** Use smootherstep (C2 continuous) for all profile functions. The derivative is also zero at boundaries, eliminating visible seams.

### Pitfall 4: Terrain Normal Recalculation
**Problem:** After deforming vertex positions, face normals are stale. This causes incorrect lighting.
**Solution:** Call `bm.normal_update()` after all vertex moves but before `bm.to_mesh()`. The existing `handle_spline_deform` does NOT do this (bug).

### Pitfall 5: World vs Local Space
**Problem:** Spline points in world space vs terrain vertices in local space. If terrain has non-identity transforms, all distance calculations are wrong.
**Solution:** Transform spline points into terrain's local space before processing:
```python
world_to_local = terrain_obj.matrix_world.inverted()
local_points = [tuple(world_to_local @ Vector(p)) for p in spline_points]
```

### Pitfall 6: Non-Square Terrain Grids
**Problem:** `_detect_grid_dims()` handles this for grid-based ops, but spline deformation works directly with vertex positions and is unaffected. However, the grid-to-world conversion in `grid_path_to_world_spline()` must use correct row/col counts.
**Solution:** Always use `_detect_grid_dims(bm)` when converting between grid and world coordinates.

---

## Sources

- [Spline Distance Fields -- zone.dog](https://zone.dog/braindump/spline_fields/) -- Surfel-based spline terrain deformation algorithm
- [Blender KDTree API](https://docs.blender.org/api/current/mathutils.kdtree.html) -- Spatial indexing for vertex queries
- [Blender BMesh API](https://docs.blender.org/api/current/bmesh.html) -- Mesh editing primitives
- [Crown and Cross-Slope -- Penn State](https://dirtandgravel.psu.edu/wp-content/uploads/2022/06/TB_Crown_and_Cross_Slope.pdf) -- Road crown engineering specs
- [Red Blob Games: Procedural River Drainage](https://www.redblobgames.com/x/1723-procedural-river-growing/) -- River generation patterns
- [GameDev.net: Adding Realistic Rivers](https://archive.gamedev.net/archive/reference/programming/features/randomriver/) -- River mesh deformation techniques
- [Procedural Generation of Landscapes with Water Bodies (CGI22)](https://cgvr.cs.uni-bremen.de/papers/cgi22/CGI22.pdf) -- Academic river/terrain integration
- [World Machine: Rivers](https://www.world-machine.com/blog/?p=470) -- River channel modeling in terrain tools
- [Geometric Design of Roads -- Wikipedia](https://en.wikipedia.org/wiki/Geometric_design_of_roads) -- Road cross-section engineering reference
- Existing codebase: `terrain_advanced.py`, `road_network.py`, `terrain_materials.py`, `environment.py`
