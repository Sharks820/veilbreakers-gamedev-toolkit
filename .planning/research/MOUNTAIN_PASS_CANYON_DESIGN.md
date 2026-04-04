# Mountain Pass, Canyon & Mountain Terrain Design Research

**Domain:** Procedural dark fantasy mountain environment generation in Blender
**Researched:** 2026-04-03
**Confidence:** HIGH (cross-referenced against codebase, GDC talks, academic papers, shipped AAA games)
**Target:** VeilBreakers MCP toolkit -- `terrain_features.py`, `_terrain_noise.py`, `terrain_advanced.py`

---

## Table of Contents

1. [Mountain Pass Geometry](#1-mountain-pass-geometry)
2. [Canyon Systems](#2-canyon-systems)
3. [Mountain-Cliff Integration](#3-mountain-cliff-integration)
4. [Path & Trail Generation](#4-path--trail-generation)
5. [Mountain Materials & Altitude Zones](#5-mountain-materials--altitude-zones)
6. [Dark Fantasy Mountain Aesthetic](#6-dark-fantasy-mountain-aesthetic)
7. [Existing Codebase Analysis](#7-existing-codebase-analysis)
8. [Implementation Recommendations](#8-implementation-recommendations)
9. [Sources](#9-sources)

---

## 1. Mountain Pass Geometry

### 1.1 What a Mountain Pass Actually Is

A mountain pass (col, saddle, gap) is the lowest point along a ridge connecting two peaks. It forms naturally where erosion weakens a ridge line, creating a navigable route between valleys on either side.

**Cross-section profiles:**

| Type | Shape | Cause | Game Use |
|------|-------|-------|----------|
| V-shaped pass | Narrow V cut into ridge | River/stream erosion | Tight choke points, ambush territory |
| U-shaped pass | Wide rounded trough | Glacial erosion | Trade routes, army movement corridors |
| Wind gap | Shallow notch, no water | Ancient river dried up | Elevated lookout positions |
| Saddle pass | Broad gentle dip between peaks | Natural ridge low point | Settlement locations, crossroads |

**Key dimensions for game-scale terrain (dark fantasy):**

| Feature | Dimension | Notes |
|---------|-----------|-------|
| Pass width at narrowest | 30-100m | Wider = trade route, narrower = defensible choke |
| Pass width at approaches | 200-500m | Gradual widening into valleys |
| Pass floor length | 200-800m | Distance through the narrow section |
| Approach slope grade | 8-15% (5-9 degrees) | Switchback trail territory |
| Pass floor grade | 2-5% | Gentle enough for wagons |
| Peak height above pass | 200-800m | Dramatic looming walls |
| Ridge sharpness | 10-30m wide at top | Knife-edge to broad saddle |

### 1.2 How to Generate a Convincing Pass

**Algorithm: Ridge-Cut Method**

1. Generate base mountain terrain using ridged multifractal noise (already in `_terrain_noise.py` as `generate_heightmap_ridged`)
2. Define ridge line as the highest continuous path between two peaks (extractable from heightmap via gradient ascent)
3. Find or place the saddle point (lowest point on ridge)
4. Apply a Gaussian-cross-section cut at the saddle:
   ```
   pass_depth(x, y) = pass_max_depth * exp(-(d_along^2 / (2 * sigma_along^2))) * exp(-(d_across^2 / (2 * sigma_across^2)))
   ```
   Where `d_along` = distance along ridge, `d_across` = distance perpendicular to ridge, `sigma_along` controls pass length, `sigma_across` controls pass width
5. The cut depth should NOT go below the valley floors on either side
6. Apply hydraulic erosion (`apply_hydraulic_erosion` -- already exists) concentrated at the pass to create natural drainage channels

**Pass floor detail:**
- Slight V-channel down the center for water runoff (1-2m depression)
- Scattered boulder meshes along edges where rockfall accumulates
- Sparse vegetation: hardy grasses, lichen on wind-sheltered sides only
- Possible stream running through (use `carve_river_path` already in codebase)

### 1.3 Defensive Features (Dark Fantasy)

Mountain passes are natural choke points. For VeilBreakers:
- **Lookout positions:** Flat ledges 20-50m above pass floor on both sides
- **Gatehouse site:** Flat area at narrowest point, 30-50m wide, suitable for wall placement
- **Hidden paths:** Secondary trails on the cliff faces (1.5m wide ledge paths)
- **Ambush alcoves:** Small indentations in pass walls where enemies can hide
- **Ruin placement zones:** Flat terraces on approach slopes for watchtower foundations

---

## 2. Canyon Systems

### 2.1 Canyon Types and Their Geometry

**Existing codebase:** `generate_canyon()` in `terrain_features.py` creates a basic walkable canyon with floor, two walls, and side caves. It uses a linear X-axis layout with noise-roughened walls. This is a solid foundation but needs expansion for the variety VeilBreakers requires.

#### River-Carved Canyon (Grand Canyon style)

**Profile:** Deep V-shape widening at top, river at bottom, layered horizontal strata in walls.

**Generation approach:**
1. Start with heightmap terrain
2. Carve primary channel using `carve_river_path` (exists) with increased depth (0.15-0.25 instead of default 0.05)
3. Apply step-function to canyon walls to create horizontal strata:
   ```python
   # Quantize wall heights into layers
   layer_height = wall_height / num_layers
   z_layered = round(z / layer_height) * layer_height
   # Blend: 70% layered + 30% original for natural look
   z_final = 0.7 * z_layered + 0.3 * z_original
   ```
4. Each layer slightly inset from layer below (creating ledges)
5. Add noise to layer edges for broken/weathered look
6. Apply `apply_thermal_erosion` (exists) to create talus slopes at wall bases

**Key parameters:**
- Canyon depth: 50-200m
- Top width: 200-500m
- Bottom width: 10-30m (river width)
- Number of strata layers: 5-12
- Layer inset per step: 0.5-2m
- Wall angle: 70-85 degrees (near vertical with slight taper)

#### Slot Canyon

**Profile:** Extremely narrow (1-5m), extremely tall (20-50m), sinuous path, dramatic light shafts from above.

**Generation approach:**
1. Generate a sinuous 2D path using domain-warped noise:
   ```python
   # Path center line with sinuosity
   center_y(x) = amplitude * noise(x / wavelength, seed) 
   # Apply domain warping for organic curves
   warped_x = x + warp_strength * noise(x / warp_scale, seed + 1)
   center_y = amplitude * noise(warped_x / wavelength, seed)
   ```
2. Walls are nearly vertical (85-90 degrees) with slight overhang at top
3. Floor width varies: 1-5m, controlled by secondary noise
4. Wall texture: smooth water-carved surfaces with occasional fluting (vertical grooves)
5. Top opening narrower than bottom in places (overhanging walls)
6. Light: minimal -- only direct light at midday, otherwise reflected/ambient

**Critical for dark fantasy:** Slot canyons are inherently claustrophobic and threatening. Perfect for horror encounters. The walls should lean inward slightly, and the ceiling should be visible but unreachably high.

**Mesh approach:** Cannot use heightmap for this -- requires explicit mesh generation (extend existing `generate_canyon()` pattern with much taller walls, sinuous path, and wall lean parameters).

#### Box Canyon

**Profile:** Dead end -- three walls, one entrance. Natural arena.

**Generation approach:**
1. Generate U-shaped plan view: entrance on one side, curved back wall
2. Walls rise steeply on three sides (70-85 degrees)
3. Floor is roughly flat with slight drainage toward entrance
4. Back wall may have waterfall, cave entrance, or shrine niche
5. Entrance narrows to 15-40m (defensible)
6. Interior floor: 60-150m diameter

**Perfect for:** Boss arenas, ambush encounters, dragon lairs, ritual sites. The player enters through the narrow mouth and cannot easily retreat.

**Mesh specification:**
```
Floor: circular/elliptical mesh, slight center depression
Walls: 270-degree arc of near-vertical cliff
Entrance: gap in wall arc, 15-40m wide
Back feature: flat area for altar/cave/waterfall placement
Ledges: 2-3 horizontal ledge rings at 1/3 and 2/3 height for ranged enemies
```

#### Multi-Level Canyon (Terraced)

**Profile:** Wide canyon with terraced walls -- ledges at each level creating explorable layers.

**Generation approach:**
1. Start with river-carved canyon profile
2. Apply aggressive step-function quantization to create wide terraces (3-8m per level)
3. Each terrace is walkable (2-5m wide minimum)
4. Connect terraces with ramp paths, carved stairs, or narrow trails
5. Vegetation on terraces: small trees, shrubs (altitude-appropriate)

**Key parameters:**
- Number of terrace levels: 3-6
- Terrace width: 2-8m
- Riser height per level: 5-15m
- Riser angle: 60-80 degrees

### 2.2 Canyon-to-Terrain Integration

The #1 problem with procedural canyons is the seam where canyon meets surrounding terrain. Solutions:

1. **Heightmap carving:** For large-scale canyons, carve directly into the terrain heightmap using `carve_river_path` with widening. The canyon IS the terrain, no seam.

2. **Blending zone:** For standalone canyon meshes placed on terrain, create a 20-50m transition zone where:
   - Canyon wall height decreases to zero
   - Terrain height increases to match canyon rim
   - Use cosine interpolation for smooth blend
   - Place rock scatter meshes to hide any remaining seam

3. **Spline deformation:** Use existing `handle_spline_deform` in `terrain_advanced.py` to carve the canyon path into terrain, then place canyon wall meshes along the carved path.

### 2.3 Canyon with Waterfall

The existing `generate_waterfall()` already creates a cliff face with water stream and pool. For canyon integration:

1. Place waterfall at a terrace step within the canyon
2. Pool at base of waterfall acts as level transition (player climbs down/around)
3. Mist zone around waterfall base: 10-20m radius of reduced visibility
4. Wet rock material zone: 5-10m around waterfall spray area
5. Behind-waterfall cave: 2-3m deep alcove hidden by water curtain (classic dark fantasy secret)

---

## 3. Mountain-Cliff Integration

### 3.1 Mountain Profile: Base to Peak

The transition from flat terrain to mountain peak follows a natural gradient that AAA games must replicate:

```
Elevation Profile (cross-section):

Peak ........... /\ ............. 2500m
                / .\
               /   .\
Alpine ...../     .  \ ........ 1800m  (snow, bare rock)
           /       .   \
Treeline /         .    \ ..... 1200m  (sparse stunted trees)
        /           .    |
Mid .../..............\..| ..... 500m   (mixed forest, rock outcrops)
      /                 .|
Base /___________________| ..... 0m    (grassland, forest floor)
     ^                    ^
   Gentle slope (15-25deg)  Cliff face (60-90deg)
```

**Critical insight from FromSoftware (Elden Ring):** Mountains should NOT be uniformly sloped. They alternate between:
- Gentle slopes (15-25 degrees) where paths can traverse
- Cliff bands (60-90 degrees) that form vertical barriers
- Ledge shelves (0-5 degrees) that break up cliff faces

This creates the **cliff-ledge-slope rhythm** that makes mountains both visually interesting and gameplay-functional.

### 3.2 Generating Mountain Silhouettes

**Dark fantasy demands jagged, threatening silhouettes.** The existing ridged multifractal generator (`generate_heightmap_ridged`) is the right foundation.

**Peak shape recipes:**

| Peak Type | Noise Config | Post-Processing |
|-----------|-------------|-----------------|
| Sharp ridgeline | ridged_multifractal, offset=1.2, gain=0.6 | power(h, 1.8) for sharpening |
| Dome/rounded | perlin fBm, persistence=0.35 | smooth filter, 3 passes |
| Plateau/flat-top | ridged_multifractal, offset=0.8 | clamp(h, 0, plateau_threshold) |
| Jagged/chaotic | ridged + domain warping | abs(noise) for extra ridges |
| Twin peaks | Two offset Gaussians added to ridged base | -- |
| Volcanic cone | radial gradient * noise | crater subtraction at center |

**Domain warping for organic mountain shapes:**
```python
# Domain warping creates the organic, non-repetitive look
warp_x = fbm(x * 0.01, y * 0.01, seed=seed+100) * warp_strength
warp_y = fbm(x * 0.01, y * 0.01, seed=seed+200) * warp_strength
height = ridged_multifractal(x + warp_x, y + warp_y, ...)
```
Warp strength of 50-150m creates convincing organic mountain shapes. Higher values create more surreal, fantastical peaks.

### 3.3 Foothills

Foothills are the transition zone between plains and mountains. They should:
- Use lower-amplitude noise than the mountain proper
- Have rolling, rounded profiles (lower persistence, fewer octaves)
- Gradually increase in height and steepness toward the mountain
- Support vegetation: full forest cover transitioning to sparse at higher elevations

**Implementation:** Blend between two heightmaps:
```python
# Blend factor based on distance from mountain center
blend = smoothstep(foothill_start, mountain_start, distance_from_center)
height = lerp(foothill_heightmap, mountain_heightmap, blend)
```

### 3.4 Mountain Ridges Between Peaks

Ridges connecting peaks are critical for both visual silhouette and gameplay (traversable ridgetop paths).

**Ridge types:**
- **Knife-edge (arete):** 1-3m wide at top, steep drops both sides. Generated by high-amplitude ridged noise with narrow peak.
- **Broad ridge:** 10-30m wide, gentle enough for a trail. Generated by lower-amplitude noise connecting two peak zones.
- **Saddle/col:** Local minimum along a ridge -- natural pass location.

**Generation:** Connect peak positions with Catmull-Rom splines (already in `terrain_advanced.py` as `_auto_control_points`), then raise the heightmap along the spline to create the ridge. The ridge height should be 60-80% of adjacent peak heights.

---

## 4. Path & Trail Generation

### 4.1 Existing Infrastructure

The codebase already has `generate_road_path()` in `_terrain_noise.py` which uses weighted A* with slope avoidance. This is the foundation for mountain trails, but needs adjustment for steep terrain.

### 4.2 Switchback Trail Algorithm

Switchback trails are the signature feature of mountain paths. They zigzag up steep slopes because direct ascent exceeds walkable grade.

**Key insight from Gamasutra research:** The cost function must penalize steepness **non-linearly** (squared or cubed), not linearly. This naturally produces switchbacks because the pathfinder prefers two gradual segments over one steep one.

**Modified A* cost function for switchbacks:**
```python
def switchback_cost(current_height, neighbor_height, distance):
    slope = abs(neighbor_height - current_height) / distance
    max_grade = 0.15  # 15% maximum comfortable grade
    
    if slope > max_grade:
        # Quadratic penalty for exceeding max grade
        excess = (slope - max_grade) / max_grade
        penalty = 1.0 + 10.0 * excess * excess
    else:
        penalty = 1.0
    
    return distance * penalty
```

**Path width by terrain type:**
- Switchback trail: 2-4m wide
- Mountain road: 4-6m wide  
- Carved stone stairs: 1.5-3m wide, steeper sections
- Ledge path: 1-2m wide, cliff face traverse

**Trail features to scatter along path:**
- Cairns (stone piles): every 50-100m as trail markers
- Rest areas: flat spots 6-10m wide at switchback turns
- Retaining walls: on the downhill side of traversing trails
- Torch brackets: on rock faces adjacent to trail (dark fantasy)
- Carved symbols: on rock faces at junctions

### 4.3 Carved Stone Stairs

For sections steeper than 25% grade (14 degrees), switchbacks become impractical. Stone stairs are the solution.

**Stair parameters:**
- Tread depth: 0.3-0.5m
- Riser height: 0.15-0.25m
- Width: 1.5-3m
- Material: same stone as mountain rock face
- Condition (dark fantasy): cracked, moss-covered, some treads missing

**Generation:** Quantize the path Z-coordinates into step heights:
```python
stair_height = 0.2  # riser height
z_stairs = round(z / stair_height) * stair_height
```

### 4.4 Rope Bridges

Span gaps between cliff faces or across canyons.

**Parameters:**
- Span: 10-40m (longer = more dramatic sag)
- Width: 1-2m (single file, rickety)
- Sag: catenary curve, 10-20% of span length
- Planks: 0.15m wide, 0.03m thick, gaps between some
- Rope diameter: 0.03-0.05m

**Catenary math:** `z(x) = a * cosh(x/a) - a` where `a = span / (2 * sinh(sag_ratio))`

### 4.5 Short Tunnels Through Ridge

When a trail encounters a thin rock ridge (5-15m thick), a short tunnel is more natural than going over.

**Generation:**
- Tunnel cross-section: arched (semi-circular or pointed arch for dark fantasy)
- Width: 2-4m
- Height: 2.5-3.5m
- Length: 5-15m (through the ridge)
- Boolean-subtract the tunnel volume from the ridge mesh (use bmesh bisect or knife operations)

---

## 5. Mountain Materials & Altitude Zones

### 5.1 Existing Material System

The codebase already has altitude/slope-based biome rules in `BIOME_RULES` (`_terrain_noise.py`), with materials including `cliff_rock`, `rock`, `highland_scrub`, and others. These need expansion for proper mountain altitude zones.

### 5.2 Complete Altitude Zone Material Table

| Zone | Altitude (game scale) | Slope Behavior | Base Color (sRGB) | Roughness | Notes |
|------|----------------------|----------------|-------------------|-----------|-------|
| **Valley Floor** | 0-200m | <20 deg: grass, >35 deg: soil | (65, 85, 40) dark grass | 0.90 | Dense vegetation, dark humus soil |
| **Lower Forest** | 200-600m | <25 deg: forest floor, >40 deg: rock | (45, 55, 30) pine needle carpet | 0.88 | Conifer forest, thick canopy |
| **Upper Forest** | 600-1000m | <25 deg: thin grass/moss, >35 deg: rock | (70, 75, 45) pale moss | 0.85 | Trees thinning, more rock exposure |
| **Treeline** | 1000-1400m | <20 deg: scrub, >30 deg: rock | (85, 80, 55) dry scrub | 0.82 | Stunted krummholz, wind-bent trees |
| **Alpine Meadow** | 1400-1800m | <25 deg: alpine grass, >30 deg: scree | (90, 95, 55) tough alpine grass | 0.80 | Sparse, low vegetation |
| **Rock/Scree** | 1800-2400m | All slopes: bare rock | (120, 115, 100) light granite | 0.85 | No vegetation, loose rock on <35 deg |
| **Summit/Snow** | 2400m+ | <30 deg: snow, >45 deg: exposed rock | (220, 225, 230) snow white | 0.60 | Snow on flat/gentle surfaces, rock on steep |
| **Perpetual Ice** | 2800m+ | All: ice/snow | (190, 210, 230) blue-white | 0.40 | Glacial ice, blue tint in shadows |

**Dark fantasy modifications to standard mountain materials:**
- All colors shifted darker and more desaturated than real-world equivalents
- Vegetation colors tend toward sickly yellows and grayed greens, not vibrant
- Rock has subtle purple/dark blue veining (corruption undertone)
- Snow has gray tint, never pure white (perpetual overcast)
- Above 2000m: occasional purple/void energy glow cracks in rock (0.5-1m wide fissures)

### 5.3 Slope-Based Material Blending

The existing `compute_biome_assignments` uses hard altitude/slope thresholds. For AAA quality, materials should BLEND at zone boundaries:

```python
# Fuzzy zone transition (50-100m blend width)
blend_width = 75.0  # meters
blend_factor = smoothstep(zone_boundary - blend_width/2, 
                          zone_boundary + blend_width/2, 
                          altitude)
final_color = lerp(lower_zone_color, upper_zone_color, blend_factor)
```

**Slope-based overrides (applied AFTER altitude zone):**
- Slope > 55 degrees: always cliff rock, regardless of altitude
- Slope > 35 degrees: rock/exposed surface, vegetation suppressed
- Slope < 10 degrees: flat surface -- snow accumulates here at high altitude
- North-facing (negative Y in Blender): snow line 200m lower than south-facing

### 5.4 Rock Face Material Varieties

| Rock Type | Color (sRGB) | Roughness | Where to Use |
|-----------|-------------|-----------|--------------|
| Grey granite | (130, 125, 115) | 0.85 | Default mountain rock, most common |
| Dark basalt | (55, 50, 45) | 0.80 | Volcanic areas, dramatic cliff faces |
| Brown sandstone | (150, 120, 80) | 0.82 | Canyon walls, layered formations |
| Slate/shale | (90, 85, 80) | 0.78 | Cliff bands, flat-breaking rock |
| Corrupted rock | (70, 50, 65) | 0.75 | Void-touched zones, purple-black |

### 5.5 Snow Accumulation Logic

Snow should NOT uniformly cover surfaces above the snow line. It accumulates based on:

1. **Surface angle:** Only on surfaces < 35 degrees from horizontal
2. **Aspect (facing direction):** More on north-facing (shadow) slopes
3. **Sheltering:** Lee side of ridges gets more snow (wind deposits)
4. **Rock overhangs:** No snow directly under overhangs, accumulation at overhang drip line

```python
def snow_coverage(altitude, slope_deg, aspect_north_factor):
    """Returns snow blend factor 0-1."""
    snow_line = 2200.0  # base snow line altitude
    # North-facing gets snow 200m lower
    effective_snow_line = snow_line - 200.0 * aspect_north_factor
    
    # Altitude factor
    alt_factor = smoothstep(effective_snow_line, effective_snow_line + 300, altitude)
    
    # Slope factor (steep = no snow)
    slope_factor = smoothstep(40, 25, slope_deg)  # inverted: more snow on gentle slopes
    
    return alt_factor * slope_factor
```

---

## 6. Dark Fantasy Mountain Aesthetic

### 6.1 Visual Principles (FromSoftware / VeilBreakers Style)

**Silhouette is everything.** Dark fantasy mountains must read as threatening shapes against the sky:

1. **Jagged, asymmetric peaks:** Never smooth or rounded. Use ridged multifractal with high offset (1.2-1.5) and domain warping.
2. **Exaggerated verticality:** Real mountains are 30-45 degree average slope. Fantasy mountains should have sections at 60-80 degrees with cliff bands.
3. **Scale contrast:** Tiny details (crags, spires, overhangs) against massive bulk. Achieved through high octave count (8+) in noise generation.
4. **Broken/ruined appearance:** Mountains should look damaged -- split peaks, collapsed cliff faces, enormous scars. Apply thermal erosion aggressively to create talus fields.

### 6.2 Atmospheric Effects

Atmosphere is what makes mountains feel dark fantasy rather than just "mountains":

| Effect | Implementation | Parameters |
|--------|---------------|------------|
| **Valley fog** | Volumetric/particle plane at valley floor | Height: 100-300m above valley floor, density: 0.4-0.7 |
| **Peak cloud wrap** | Torus/ring mesh around peak with cloud material | Altitude: 1600-2200m, radius: 200-500m |
| **Perpetual overcast** | Flat cloud plane above scene | Altitude: 3000m+, coverage: 70-90% |
| **Mist tendrils in canyons** | Thin fog volumes in narrow passages | Density increases with canyon depth |
| **Lightning on peaks** | Emissive flicker on peak vertices | Intermittent, purple-white color |
| **Filtered light** | Directional light through cloud gaps | Low angle (15-25 deg), warm-cold contrast |

### 6.3 Environmental Storytelling Features

These are NOT terrain features -- they are placement zones on the terrain where ruin/prop generators should place objects:

| Feature | Placement Rules | Size |
|---------|----------------|------|
| **Ancient watchtower ruins** | On lookout points (high, with sightlines) | 5-8m diameter footprint |
| **Wayside shrine** | Trail junctions, switchback rest points | 2-3m footprint |
| **Collapsed bridge abutment** | Canyon edges, gap crossings | 4-6m x 8-12m |
| **Dragon/creature nest** | High ledges (1800m+), sheltered from wind | 10-15m diameter |
| **Void corruption crack** | Random cliff faces, canyon walls | 1-3m wide, 5-20m long, purple glow |
| **Dead forest patches** | Treeline zone, corruption spread origin | 30-80m diameter |
| **Frozen corpses/equipment** | Snow zone, near trail | 1-2m scatter radius |
| **Carved mountain face** | Large flat cliff surface | 20-50m tall carving area |
| **Mine entrance** | Mid-altitude cliff face | 3-4m wide, 3m tall arch |

### 6.4 Corruption Gradient

VeilBreakers has corruption as a core theme. Mountains should show corruption increasing with altitude (the Veil is thinner at heights):

| Altitude Zone | Corruption Level | Visual Signs |
|---------------|-----------------|--------------|
| 0-500m | None | Normal dark fantasy palette |
| 500-1200m | Subtle | Occasional dead tree, slight purple tint on rock |
| 1200-1800m | Moderate | Dead tree patches, purple lichen, faint glow cracks |
| 1800-2400m | Heavy | All vegetation dead, purple veins in rock, void particles |
| 2400m+ | Extreme | Rock partially translucent, reality distortion, floating fragments |

---

## 7. Existing Codebase Analysis

### 7.1 What Already Exists

| Component | File | Status | Quality |
|-----------|------|--------|---------|
| Perlin/fBm heightmap generation | `_terrain_noise.py` | Complete | HIGH -- vectorized numpy, 8 terrain presets |
| Ridged multifractal noise | `_terrain_noise.py` | Complete | HIGH -- proper octave weighting, gain feedback |
| Hydraulic erosion | `_terrain_erosion.py` | Complete | HIGH -- droplet-based, brush radius, full params |
| Thermal erosion | `_terrain_erosion.py` | Complete | HIGH -- vectorized 8-neighbor, talus angle |
| Basic canyon | `terrain_features.py` | Complete | MEDIUM -- linear layout, lacks sinuosity and types |
| Waterfall | `terrain_features.py` | Complete | MEDIUM -- cliff + pool, good integration point |
| Cliff face | `terrain_features.py` | Complete | MEDIUM -- overhang + cave entrances + ledge path |
| Natural arch | `terrain_features.py` | Complete | MEDIUM -- bridge formation |
| Biome assignment | `_terrain_noise.py` | Complete | MEDIUM -- altitude/slope rules but hard boundaries |
| A* river carving | `_terrain_noise.py` | Complete | HIGH -- slope-weighted pathfinding |
| A* road generation | `_terrain_noise.py` | Complete | HIGH -- waypoint chaining, terrain grading |
| Spline terrain deform | `terrain_advanced.py` | Complete | HIGH -- Catmull-Rom, cubic Bezier |
| Terrain stamp/feature placement | `terrain_advanced.py` | Complete | HIGH -- heightmap stamp at position |
| Snap to terrain | `terrain_advanced.py` | Complete | HIGH -- object grounding |
| Flow map (D8) | `terrain_advanced.py` | Complete | HIGH -- drainage network computation |
| Terrain sculpt brushes | `terrain_sculpt.py` | Complete | HIGH -- raise/lower/smooth/flatten/stamp |
| Terrain flatten zone | `terrain_advanced.py` | Complete | HIGH -- flat area for building placement |
| Terrain chunking | `terrain_chunking.py` | Complete | -- |
| Terrain materials | `terrain_materials.py` | Complete | -- |

### 7.2 What is MISSING for Mountain Pass / Canyon Systems

| Missing Feature | Priority | Complexity | Notes |
|-----------------|----------|------------|-------|
| **Mountain pass generator** | HIGH | Medium | Ridge-cut algorithm on heightmap |
| **Slot canyon generator** | HIGH | Medium | Extend `generate_canyon()` with sinuosity + tall walls |
| **Box canyon generator** | HIGH | Medium | Dead-end variant of canyon |
| **Multi-level terraced canyon** | MEDIUM | Medium | Step-function quantization of canyon walls |
| **Switchback trail generator** | HIGH | Low | Modify A* cost function in `generate_road_path()` |
| **Stone stair sections** | MEDIUM | Low | Z-quantization on steep path sections |
| **Rope bridge mesh** | LOW | Low | Catenary curve + plank geometry |
| **Ridge connector** | MEDIUM | Low | Spline-based height raise between peaks |
| **Altitude material blending** | MEDIUM | Low | Fuzzy zone transitions in biome assignment |
| **Snow accumulation logic** | LOW | Low | Slope + aspect + altitude factor |
| **Mountain silhouette profiles** | LOW | Low | New presets for ridged noise params |
| **Fog/mist volume placement** | LOW | Low | Mesh generation for atmospheric volumes |
| **Corruption material overlay** | LOW | Low | Altitude-based corruption tint |

### 7.3 Integration Points

The existing architecture is well-suited for these additions:

1. **Heightmap-based features** (pass, ridges) integrate directly with `generate_heightmap_ridged` and erosion functions
2. **Mesh-based features** (slot canyon, box canyon) follow the `generate_canyon()` pattern -- pure logic returning vertex/face/material dicts
3. **Path features** (switchbacks, stairs) extend `generate_road_path()` with modified cost functions
4. **Material features** extend `BIOME_RULES` in `_terrain_noise.py`
5. **Placement features** use `handle_terrain_stamp()` and `handle_snap_to_terrain()` from `terrain_advanced.py`

---

## 8. Implementation Recommendations

### 8.1 Phase Priority

**Phase 1: Core Mountain Terrain (HIGH priority)**
1. `generate_mountain_pass()` -- Ridge-cut on heightmap, Gaussian cross-section
2. `generate_switchback_trail()` -- Modified A* with quadratic slope penalty
3. New mountain silhouette presets for ridged noise (3-4 peak shapes)

**Phase 2: Canyon Variants (HIGH priority)**
4. `generate_slot_canyon()` -- Sinuous path, domain-warped, tall narrow walls
5. `generate_box_canyon()` -- Dead-end arena, three walls + entrance
6. `generate_terraced_canyon()` -- Multi-level with walkable ledges

**Phase 3: Path Detail (MEDIUM priority)**
7. `generate_stone_stairs()` -- Z-quantized steep path sections
8. `generate_rope_bridge()` -- Catenary curve plank mesh
9. `generate_ridge_path()` -- Spline-based ridge connector between peaks

**Phase 4: Materials & Atmosphere (MEDIUM priority)**
10. Extended `BIOME_RULES` with full mountain altitude zones
11. Fuzzy zone blending in `compute_biome_assignments()`
12. Snow accumulation function
13. Corruption altitude gradient materials

### 8.2 Technical Approach

All new generators should follow the established pattern:
- **Pure logic functions** in `terrain_features.py` (no bpy imports)
- Return dicts with `mesh`, `materials`, `material_indices`, and metadata
- Seed parameter for reproducibility
- Testable without Blender (existing test pattern in `test_terrain_features_v2.py`)

For heightmap-level operations (passes, ridges):
- Operate on numpy arrays from `generate_heightmap_ridged()`
- Return modified heightmaps (same shape)
- Compatible with existing erosion pipeline

### 8.3 Parameter Recommendations

**Mountain Pass defaults:**
```python
pass_width = 60.0       # meters at narrowest
pass_length = 400.0     # meters through section  
approach_width = 250.0  # meters at approach
peak_height = 500.0     # meters above pass floor
erosion_iterations = 2000  # hydraulic erosion for natural drainage
```

**Slot Canyon defaults:**
```python
width = 3.0             # meters floor width
length = 80.0           # meters  
depth = 35.0            # meters wall height
sinuosity = 0.6         # domain warp amount [0-1]
wall_lean = 0.1         # inward lean factor
num_sections = 20       # mesh resolution along length
```

**Box Canyon defaults:**
```python
diameter = 100.0        # meters interior
entrance_width = 25.0   # meters
wall_height = 60.0      # meters  
num_ledge_levels = 3    # horizontal ledge rings
back_feature = "cave"   # or "waterfall", "shrine", "flat"
```

**Switchback Trail defaults:**
```python
max_grade = 0.12        # 12% maximum slope
trail_width = 3.0       # meters
steepness_power = 2.0   # quadratic penalty exponent
steepness_multiplier = 10.0  # cost multiplier for steep sections
```

---

## 9. Sources

### Academic / Technical
- [The Mountains of Madness - Interactive Terrain Generation Algorithms](https://amanpriyanshu.github.io/The-Mountains-of-Madness/) -- Comprehensive interactive demos of Perlin, ridged multifractal, domain warping, exponential slope weighting
- [Procedural Generation of 3D Canyons (IEEE)](https://ieeexplore.ieee.org/document/6915296/) -- Academic paper on canyon generation combining height map manipulation with clustering
- [Three Ways of Generating Terrain with Erosion Features](https://github.com/dandrino/terrain-erosion-3-ways) -- Open source hydraulic, thermal, and particle erosion implementations
- [F. Kenton Musgrave - Procedural Fractal Terrains (UChicago)](https://www.classes.cs.uchicago.edu/archive/2015/fall/23700-1/final-project/MusgraveTerrain00.pdf) -- Definitive reference on ridged multifractal and hybrid terrain
- [Realtime Procedural Terrain Generation (MIT)](https://web.mit.edu/cesium/Public/terrain.pdf) -- Diamond-square, Perlin, erosion overview
- [Creating Natural Paths on Terrains Using Pathfinding (Game Developer)](https://www.gamedeveloper.com/programming/creating-natural-paths-on-terrains-using-pathfinding) -- Non-linear steepness penalty for natural trail generation

### Game Development / Art Direction
- [World Design Lessons from FromSoftware](https://medium.com/@Jamesroha/world-design-lessons-from-fromsoftware-78cadc8982df) -- Cliff-ledge-slope rhythm, verticality, environmental storytelling
- [The Ultimate Methodology of Creating Souls-like Levels](https://medium.com/@bramasolejm030206/preface-ec08bc1459d0) -- Shape language for terrain, player routing through terrain features
- [Creating Game-Ready Fantasy Environment in UE5 (80lv)](https://80.lv/articles/creating-dark-souls-inspired-game-ready-environment-with-gaea) -- Gaea terrain + UE5, atmospheric fog, dark fantasy lighting
- [Slope and Altitude Based Materials in Cycles (Panta Rei)](https://pantarei.xyz/posts/snowline-tutorial/) -- Blender shader node setup for altitude-based snow/rock/grass
- [Altitudinal Zonation (Wikipedia)](https://en.wikipedia.org/wiki/Altitudinal_zonation) -- Real-world altitude vegetation zones, treeline science

### Tools / Implementations
- [Ridged Multi (Isara Docs)](https://docs.isaratech.com/ue4-plugins/noise-library/generators/ridged-multi) -- Parameter documentation for ridged multifractal
- [SharpNoise RidgedMulti.cs](https://github.com/rthome/SharpNoise/blob/master/SharpNoise/Modules/RidgedMulti.cs) -- Reference C# implementation of ridged multifractal
- [Red Blob Games - Procedural Elevation](https://www.redblobgames.com/x/1725-procedural-elevation/) -- Interactive elevation generation tutorials
- [Canyon Generator (Geometry Nodes) - BlenderKit](https://www.blenderkit.com/asset-gallery-detail/09b7563c-b783-4868-b2c2-1318d9a9f408/) -- Reference for Blender geometry nodes canyon approach
- [Procedural Terrain 2.0 - BlenderKit](https://www.blenderkit.com/addons/9ef8471a-d401-4404-98f9-093837891b43/) -- Geometry nodes terrain generator with LOD

### Existing VeilBreakers Codebase
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py` -- Heightmap generation, ridged multifractal, road/river A*, biome rules
- `Tools/mcp-toolkit/blender_addon/handlers/_terrain_erosion.py` -- Hydraulic and thermal erosion (numpy, no bpy)
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_features.py` -- Canyon, waterfall, cliff, swamp, arch, geyser, sinkhole, floating rocks, ice, lava generators
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_advanced.py` -- Spline deform, terrain layers, stamps, snap-to-terrain, flatten zone
- `Tools/mcp-toolkit/blender_addon/handlers/terrain_sculpt.py` -- Brush-based terrain editing
- `.planning/research/AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md` -- Prior research on terrain/city generation
