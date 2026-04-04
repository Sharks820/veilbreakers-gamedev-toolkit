# Water-Rock Interaction Design for Procedural Generation

**Researched:** 2026-04-03
**Domain:** River rocks, waterfall formations, lake shorelines, underwater rocks, wet/dry materials, dark fantasy water aesthetics
**Target:** VeilBreakers procedural environment generators (terrain_features, environment, coastline, procedural_meshes, procedural_materials)
**Confidence:** HIGH (cross-referenced hydrology sources, Lagarde PBR research, AAA game techniques)

---

## Table of Contents

1. [River Rocks and Rapids](#1-river-rocks-and-rapids)
2. [Waterfall Rock Formations](#2-waterfall-rock-formations)
3. [Lake/Pond Shoreline Rocks](#3-lakepond-shoreline-rocks)
4. [Underwater Rocks](#4-underwater-rocks-visible-through-clear-water)
5. [Wet vs Dry Rock Materials](#5-wet-vs-dry-rock-materials)
6. [Rock-Water Edge Treatment](#6-rock-water-edge-treatment)
7. [Dark Fantasy Water-Rock Aesthetic](#7-dark-fantasy-water-rock-aesthetic)
8. [Implementation for VeilBreakers](#8-implementation-for-veilbreakers)
9. [Sources](#9-sources)

---

## 1. River Rocks and Rapids

### 1.1 How Rocks Sit in Flowing Water

Rocks in rivers are partially submerged with water flowing around and over them. The key principle is **hydrodynamic interaction**: water accelerates as it squeezes between and over obstacles, creating distinct flow patterns.

**Submersion Rules by Rock Size:**

| Rock Size | Diameter | Typical Submersion | Water Behavior |
|-----------|----------|-------------------|----------------|
| Pebble | 2-6 cm | Fully submerged | No visible disruption |
| Cobble | 6-25 cm | Mostly submerged | Small ripple wake |
| Small boulder | 25-60 cm | 60-80% submerged | V-shaped wake, small eddy |
| Medium boulder | 0.6-2 m | 40-60% submerged | Strong wake, white water upstream face, eddy pool behind |
| Large boulder | 2-5 m | 20-40% submerged | Full rapids, standing waves, large eddy pool, foam trails |

**Placement Rules for Procedural Generation:**

1. **Rocks cluster, they do not distribute uniformly.** Natural rivers have groups of 3-7 rocks with gaps between clusters. Use Poisson disk sampling with cluster bias (spawn a cluster center, then spawn 2-6 rocks within 1-3x the largest rock diameter).
2. **Rocks orient with longest axis perpendicular to flow.** Water rotates elongated rocks so their widest face catches the current. Set rock Y-rotation so the longest horizontal axis is roughly perpendicular to the river flow direction.
3. **Larger rocks sit deeper.** Scale submersion depth with rock volume -- a 2m boulder sinks 0.8-1.2m into the riverbed, not just resting on the surface.
4. **Flat rocks stack; round rocks scatter.** Flat-topped rocks tend to cluster in layered formations. Round boulders distribute more randomly.

### 1.2 Rapids Formation

Rapids form where the channel narrows, the gradient steepens, or large rocks constrict flow. The key elements:

**Standing Waves:** Form downstream of submerged rocks where fast water hits slow water. Height proportional to flow speed difference. For a 1m submerged boulder in moderate current: standing wave height ~0.2-0.5m, extending 1-3m downstream.

**White Water / Foam:** Generated where turbulence entrains air. Occurs at:
- Upstream face of exposed rocks (water splashes against the rock)
- Downstream of the rock crest (where water drops over the top)
- Between closely-spaced rocks (flow acceleration + collision)

**Foam Placement Formula:**
```
foam_intensity = clamp(flow_speed * rock_exposure_ratio * 2.0, 0.0, 1.0)
where:
  flow_speed = normalized river speed (0=still, 1=rapids)
  rock_exposure_ratio = fraction of rock above water (0=submerged, 1=fully exposed)
```

### 1.3 Eddy Pools Behind Large Rocks

When water flows past a large rock (diameter > 0.5m), it creates a **recirculation zone** directly behind the rock. This is the eddy pool:

- **Shape:** Roughly triangular, point downstream, base width = rock width
- **Length:** 2-5x the rock diameter downstream
- **Depth:** Slightly deeper than surrounding riverbed (scour from recirculating current)
- **Water surface:** Calmer than surrounding rapids, often nearly flat
- **Debris:** Leaves, foam, small sticks collect in the eddy (game litter spawning)

**Procedural rule:** For each rock with diameter > 0.5m and > 30% exposed above water, spawn a calm-water zone behind it. The zone extends downstream by `rock_diameter * 3`, with width tapering from `rock_diameter` to 0.

### 1.4 How Rock Size Affects Flow Patterns

The **thalweg** (line of maximum depth and velocity) weaves through a river, pushing against the outside of bends and away from obstructions. Rocks redirect this flow:

| Rock Configuration | Flow Pattern | Visual Effect |
|-------------------|--------------|---------------|
| Single large boulder | Flow splits around both sides, reunites downstream | V-shaped wake, eddy behind |
| Two boulders close together | Flow accelerates in gap (Venturi effect) | White water jet between rocks |
| Line of rocks across channel | Water drops over/through gaps, mini waterfall | Cascading white water line |
| Boulder field (many rocks) | Chaotic multi-path flow, braided rapids | Extensive foam, standing waves |

### 1.5 Gravel Bars at River Bends

Gravel bars form on the **inside of meanders** (point bars) where water velocity drops. The key geological principle: the thalweg (fastest current) runs along the outside of a bend, causing erosion at the cut bank, while the inside gets deposition.

**Gravel Bar Characteristics:**
- **Position:** Inside curve of river bends, never the outside
- **Shape:** Crescent-shaped, widest at the bend apex, tapering upstream and downstream
- **Size grading:** Coarsest material (10-30 cm cobbles) at the upstream head, grading to fine gravel (2-5 cm) and sand at the downstream tail
- **Height:** Top of gravel bar is at or slightly above normal water level -- partially exposed in low water, submerged in high water
- **Vegetation:** Sparse grasses/moss on top of bar if exposed long enough; bare gravel at water edge

**Procedural Generation:**
```python
# At each river bend (detected by curvature threshold):
bend_radius = calculate_bend_radius(river_spline, sample_point)
if bend_radius < river_width * 5:  # Significant bend
    bar_center = inside_of_bend(sample_point)
    bar_width = river_width * 0.3  # Gravel bar is ~30% of river width
    bar_length = river_width * 1.5  # Extends 1.5x width along bend
    # Spawn cobbles: large upstream, small downstream
    for i in range(num_rocks):
        t = i / num_rocks  # 0=upstream, 1=downstream
        rock_size = lerp(0.15, 0.03, t)  # 15cm to 3cm
        spawn_rock(bar_center, offset_along_bend(t), rock_size)
```

### 1.6 Boulder Dams

Natural boulder dams form where a cluster of large rocks creates a barrier across the channel, producing a small waterfall or drop.

**Structure:**
- 3-7 large boulders (1-3m) spanning most of the channel width
- Not a perfect line -- irregular, with gaps that water pours through
- Water drops 0.3-2m on the downstream side
- Plunge scour immediately downstream (deeper pool)
- Debris and smaller rocks jam between the large boulders

**For procedural generation:** Spawn boulder dams at locations where the river gradient increases (steeper slope). Space them 20-100m apart in steep sections. Each dam creates a 0.5-1.5m elevation drop.

---

## 2. Waterfall Rock Formations

### 2.1 Waterfall Lip (Ledge)

The lip is the hard rock ledge where water exits horizontally before falling. Key properties:

- **Material:** Harder rock than the layer below (this differential erosion is WHY the waterfall exists)
- **Shape:** Roughly horizontal with slight downstream tilt (5-15 degrees)
- **Edge profile:** Not a clean knife edge. Irregular, with sections that protrude 0.1-0.5m further than others, creating uneven water curtain
- **Width:** The waterfall lip is typically 1.5-3x the width of the water stream approaching it (water spreads as it exits)
- **Undercut:** The soft rock below erodes faster, creating an overhang of 0.5-3m

**Geometry Notes:** The lip should be a slightly beveled horizontal shelf. Add noise to the edge profile (displacement along flow direction) to create natural-looking water distribution. The mesh should have a visible overhang underneath.

### 2.2 Plunge Pool

The plunge pool is a deep, roughly circular depression at the waterfall base, carved by the impact of falling water.

**Dimensions (based on geological research):**

| Waterfall Height | Pool Depth | Pool Radius | Notes |
|-----------------|------------|-------------|-------|
| 2-5 m | 0.5-2 m | 2-4 m | Small cascade |
| 5-15 m | 2-5 m | 4-8 m | Medium waterfall |
| 15-50 m | 5-15 m | 8-20 m | Large waterfall |

**Key rule:** Pool depth is approximately 1/3 of waterfall height. Pool radius is approximately equal to waterfall height.

**Shape:** Not a perfect circle. Elongated in the downstream direction (water exits the pool downstream). The upstream wall (nearest the waterfall) is steepest and deepest. The downstream lip is shallow and grades into the river channel.

**Floor:** Polished, smooth rock with rounded pebbles. Darker than surrounding rock due to permanent submersion.

### 2.3 Wet Rock Face Behind Waterfall

The cliff face behind/beside the waterfall curtain is perpetually wet and distinct from surrounding rock:

- **Color:** 30-40% darker than dry rock (base_color multiplied by 0.6-0.7)
- **Roughness:** 0.2-0.4 (vs 0.8-0.95 for dry rock) -- much shinier
- **Surface:** Covered in dark green/black moss and algae in spray zone
- **Streaks:** Vertical dark mineral staining where water trickles
- **Cave behind:** If the waterfall has sufficient overhang (>1m), there is often a recessed cavity behind the water curtain. The cave walls are permanently wet, covered in moisture-loving ferns and moss

### 2.4 Spray Zone

The spray zone extends outward from the waterfall base in a roughly hemispherical pattern.

**Spray Zone Radius by Waterfall Height:**

| Waterfall Height | Spray Zone Radius | Notes |
|-----------------|-------------------|-------|
| 2-5 m | 3-5 m | Light mist |
| 5-15 m | 5-10 m | Moderate spray, perpetually wet rocks |
| 15-50 m | 10-30 m | Heavy mist, visibility reduced |

**Vegetation in Spray Zone:**
- **0-2 m from impact:** Bare rock, too much water force for growth. Heavy moss on any protected surface.
- **2-5 m:** Dense moss coverage (80-100% of rock surfaces), ferns in crevices, liverworts.
- **5-10 m:** Patchy moss (40-60%), transition to normal vegetation. Rocks are damp but not streaming.
- **>10 m:** Normal vegetation. Only wet during high flow conditions.

**Material Gradient:** The spray zone creates a gradient from fully wet to dry. For procedural placement, use distance from waterfall impact point to blend between wet_rock and dry_rock materials.

### 2.5 Step/Cascade Waterfalls

Most natural waterfalls are NOT single sheer drops. They are cascades -- a series of steps.

**Step Characteristics:**
- **Step height:** Irregular, ranging from 0.3m to 3m per step
- **Step depth (horizontal):** 0.5-2m, providing a ledge where water pools briefly
- **Each step has a mini plunge pool:** 0.1-0.5m deep, 1-2m wide
- **Water speed increases between steps** (acceleration) and resets at each pool
- **Total cascade height = sum of steps:** A 10m cascade might have 4-8 steps

**Generation approach (existing code extends well):** The current `generate_waterfall` in terrain_features.py already supports `num_steps`. Enhance by:
1. Varying step heights (not uniform)
2. Adding lateral offset per step (steps don't perfectly align vertically)
3. Adding mini plunge pools between steps
4. Applying moss material to horizontal ledge surfaces (wet_rock to vertical faces)

### 2.6 Generating Waterfall Geometry in Blender

The existing codebase has two waterfall generators:
- `terrain_features.generate_waterfall()` -- full cliff + steps + pool + cave
- `_terrain_depth.generate_waterfall_mesh()` -- simpler stepped cascade mesh

**Recommended enhancement approach:**
1. Use the terrain_features version as the primary generator (it already returns material indices)
2. Add rock scatter around the plunge pool (large boulders that have "fallen" from the cliff)
3. Add spray zone vertex painting (distance-based wetness gradient)
4. Connect to the water body system (`handle_create_water`) to place water surface at plunge pool level

---

## 3. Lake/Pond Shoreline Rocks

### 3.1 How Rocks Sit at Lake Edges

Lake shoreline rocks are distinctly different from river rocks. They are NOT polished smooth by current. Instead:

- **Placement:** Half in water, half on shore. The water level bisects rocks at the shoreline.
- **Orientation:** Random. No preferred alignment (no current to orient them).
- **Size distribution:** Larger rocks closer to the water, smaller further up shore (wave sorting).
- **Spacing:** Denser at the waterline, sparser inland.
- **Embedding:** Rocks at the waterline are partially buried in sediment. Only the top 40-60% is visible.

### 3.2 Algae/Waterline Staining

The most important visual indicator of a lake shore is the **waterline mark** on partially submerged rocks:

- **Below waterline:** Dark green-brown algae coating. Slimy texture.
- **At waterline (0-10 cm band):** Distinct color boundary. Often a white/light mineral deposit ring (calcium carbonate in hard water) or dark organic stain.
- **Above waterline (splash zone, 10-30 cm):** Damp, slightly darker than dry rock. Patchy lichen.
- **Above splash zone:** Normal dry rock color.

**Material Implementation:**
```python
# Per-rock material zone assignment based on water level
rock_bottom = rock.location.z - rock_half_height
rock_top = rock.location.z + rock_half_height

if rock_bottom < water_level:
    # Rock intersects water
    submerged_fraction = (water_level - rock_bottom) / (rock_top - rock_bottom)
    # Assign vertex colors: below water_level = algae, above = dry
    # Transition band of 0.1m at waterline = mineral stain zone
```

### 3.3 Rock Shelves

Flat rocky areas extending just below the water surface. Common at lake edges where bedrock is exposed.

- **Depth:** 0.05-0.5m below water surface
- **Extent:** 1-5m from shore into the lake
- **Surface:** Relatively flat with gentle undulation, covered in thin algae film
- **Visibility:** Clearly visible through clear water. Darkens with depth.
- **Edges:** Abrupt drop-off where shelf ends and deeper water begins

**For generation:** Extend the terrain mesh slightly below water level at rocky shorelines. The shelf is a nearly-flat region of terrain at `water_level - 0.1m` to `water_level - 0.3m`.

### 3.4 Rocky Beach Grading

Natural rocky beaches exhibit clear size grading:

1. **Water edge:** Large cobbles and small boulders (15-40 cm). Wave-polished, rounded.
2. **Mid beach (1-3m inland):** Medium cobbles (5-15 cm). Mixed rounded/angular.
3. **Upper beach (3-5m inland):** Small gravel and pebbles (1-5 cm). Often angular.
4. **Above high water:** Soil, vegetation begins. Occasional large boulders.

**Rule:** Rock size decreases with distance from water. Use: `rock_size = max_size * (1.0 - distance_from_water / beach_width) ** 0.7`

### 3.5 Island Rocks

Clusters of boulders that protrude above the lake surface, forming small islands:

- **Minimum:** 2-3 large boulders (1-3m) with gaps filled by smaller rocks
- **Top surface:** Flat enough for occasional vegetation (moss, small shrubs)
- **Shape:** Irregular, not circular. Usually elongated in one direction.
- **Distance from shore:** 5-50m. Close enough to be visually prominent.
- **Water depth around islands:** 0.5-3m. Visible underwater rocks extending outward.

---

## 4. Underwater Rocks (Visible Through Clear Water)

### 4.1 Riverbed Pebble Textures

The riverbed is covered in a layer of rounded, water-polished pebbles:

- **Size:** 2-10 cm typical. Uniform within a section, varies between sections.
- **Shape:** Rounded to well-rounded. No sharp edges (water erosion).
- **Color:** Multi-colored: greys, browns, tans, occasional white quartz, dark basalt. More color variety than surface rocks because wet surfaces show true mineral color.
- **Arrangement:** Dense packing, no gaps. Pebbles nestle against each other.
- **Depth:** Typically a 10-30 cm layer over bedrock or sand.

**For rendering:** The riverbed pebble layer is best handled as a texture/material on the terrain surface below water level, not individual meshes. Use a pebble displacement map or normal map on the riverbed material.

### 4.2 Larger Underwater Boulders

Boulders fully submerged in rivers and lakes appear as dark shapes:

- **Color:** Darker than they would be above water (water absorbs light)
- **Edges:** Soft/blurry due to refraction, especially in moving water
- **Algae:** Heavy algae growth on top surfaces (receives most light). Sides cleaner.
- **Shadow:** Cast noticeable shadows on the pebble bed below

### 4.3 Depth-Dependent Visibility

Clear water visibility follows exponential falloff:

| Depth | Visibility | Rock Appearance |
|-------|------------|-----------------|
| 0-0.3 m | Full detail | Colors clear, sharp edges, individual pebbles visible |
| 0.3-1 m | Good detail | Slightly blue-shifted, softened edges |
| 1-2 m | Moderate | Noticeably darker, color desaturated, shape recognizable |
| 2-5 m | Low | Dark shapes only, no color detail, blurred |
| >5 m | Minimal | Nearly invisible in all but the clearest water |

**Shader Formula:**
```
visibility = exp(-depth * extinction_coefficient)
where:
  extinction_coefficient = 0.5 for clear mountain stream
  extinction_coefficient = 1.5 for typical river
  extinction_coefficient = 3.0 for murky/dark fantasy water

underwater_color = lerp(rock_color, water_color, 1.0 - visibility)
```

### 4.4 Sediment Around Underwater Rocks

Fine sediment (sand, silt) accumulates in specific patterns around submerged rocks:

- **Upstream:** Scour zone. Sediment cleared away, exposing bare rock or coarse gravel.
- **Sides:** Slight ridges of sediment pushed aside by diverted flow.
- **Downstream:** Deposition tail. Fine sediment settles in the calm wake. Length = 2-4x rock diameter.
- **Shape:** The deposition pattern looks like a teardrop or comet tail behind the rock.

---

## 5. Wet vs Dry Rock Materials

### 5.1 The Physics of Wet Rock Appearance

Based on Sebastien Lagarde's definitive PBR research on physically-based wet surfaces:

**Why wet rock looks different:**
1. Water fills pores and surface roughness, replacing air (IOR 1.0) with water (IOR 1.33)
2. This reduces the refraction difference at the surface, allowing more light to penetrate
3. More light enters the material, more gets absorbed, less returns = darker appearance
4. Surface becomes smoother because water fills micro-roughness = shinier/more specular

### 5.2 Exact PBR Values for Rock Zones

**Zone 1: Permanently Wet Rock (below waterline, splash zone)**
```
base_color = dry_base_color * 0.6   (40% darker)
roughness  = 0.15 - 0.30            (very smooth/shiny)
metallic   = 0.0                    (dielectric)
specular   = 0.5 - 0.6              (slight boost from water layer)
normal     = dry_normal * 0.7       (water smooths micro detail)
```

**Zone 2: Intermittently Wet Rock (splash zone edge, tidal zone)**
```
base_color = dry_base_color * 0.75  (25% darker)
roughness  = 0.35 - 0.55            (partly smooth)
metallic   = 0.0
specular   = 0.5
normal     = dry_normal * 0.85
```

**Zone 3: Damp Rock (mist zone, recently rained)**
```
base_color = dry_base_color * 0.85  (15% darker)
roughness  = 0.50 - 0.70
metallic   = 0.0
specular   = 0.5
normal     = dry_normal * 0.95
```

**Zone 4: Dry Rock (above all water influence)**
```
base_color = (0.18, 0.16, 0.14) to (0.35, 0.30, 0.28)  (dark fantasy palette)
roughness  = 0.80 - 0.95
metallic   = 0.0
specular   = 0.5
normal     = full detail
```

### 5.3 Transition Zone

The wet-to-dry transition is not a hard line. It is a gradient over 0.3-1.0 meters vertically:

```python
def wet_blend_factor(vertex_z, water_level, transition_height=0.5):
    """Returns 0.0 (fully dry) to 1.0 (fully wet)."""
    if vertex_z <= water_level:
        return 1.0  # Submerged = fully wet
    elif vertex_z >= water_level + transition_height:
        return 0.0  # Above transition = fully dry
    else:
        t = (vertex_z - water_level) / transition_height
        return 1.0 - smoothstep(t)  # Smooth gradient

def apply_wetness(base_color, roughness, wet_factor, porosity=0.8):
    """Apply Lagarde-derived wetness model."""
    darken = lerp(1.0, 0.2, porosity)  # 0.2 = max darkening for fully porous
    wet_color = base_color * lerp(1.0, darken, wet_factor)
    wet_rough = lerp(roughness, roughness * 0.3, wet_factor)
    return wet_color, wet_rough
```

### 5.4 Lagarde Shader Implementation (HLSL Reference)

From the definitive source:

```hlsl
void DoWetProcess(inout float3 Diffuse, inout float Gloss,
                  float WetLevel, float2 uv)
{
    float Porosity = tex2D(GreyTextures, uv).g;
    float factor = lerp(1, 0.2, Porosity);

    Diffuse *= lerp(1.0, factor, WetLevel);
    Gloss = lerp(1.0, Gloss, lerp(1, factor, 0.5 * WetLevel));
}
```

**Without porosity texture** (simplified for VeilBreakers procedural materials):
```hlsl
// Infer porosity from roughness:
float Porosity = saturate(-2.5 * (1.0 - Roughness) + 1.25);
// High roughness = high porosity = more darkening
// Low roughness = low porosity = minimal darkening
```

**Metal handling:** Only darken dielectrics. Metals do not absorb more light when wet.
```hlsl
float factor = lerp(1, 0.2, (1 - Metalness) * Porosity);
```

### 5.5 Implementation in Blender Nodes

For the VeilBreakers procedural material system, implement wet rock as a node group:

```python
# Blender Python material setup
def create_wet_rock_material(name, dry_color, water_level):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Inputs
    tex_coord = nodes.new('ShaderNodeTexCoord')
    separate_z = nodes.new('ShaderNodeSeparateXYZ')  # Get Z from Object coords
    links.new(tex_coord.outputs['Object'], separate_z.inputs[0])

    # Wetness gradient (Z-based)
    subtract = nodes.new('ShaderNodeMath')  # vertex_z - water_level
    subtract.operation = 'SUBTRACT'
    subtract.inputs[1].default_value = water_level

    divide = nodes.new('ShaderNodeMath')  # normalize by transition height
    divide.operation = 'DIVIDE'
    divide.inputs[1].default_value = 0.5  # transition_height

    clamp = nodes.new('ShaderNodeClamp')  # 0-1 range
    # ... wet_factor = 1.0 - clamped_value

    # Apply darkening
    # dry_color * lerp(1.0, 0.6, wet_factor) -> mix node
    # roughness: lerp(0.9, 0.25, wet_factor) -> mix node

    # Feed into Principled BSDF
```

---

## 6. Rock-Water Edge Treatment

### 6.1 Where Rock Meets Water Surface

The contact line between rock and water is the most visually critical detail. Rules:

- **NO gap.** The rock mesh must intersect the water plane. A visible gap between rock bottom and water surface looks terrible.
- **NO floating.** Rock must appear to sit IN the water, not on top of it.
- **Penetration depth:** Rock mesh should extend 0.1-0.3m below the water surface at minimum. Larger rocks should extend further (half their height or more).

**Procedural placement rule:**
```python
def place_rock_in_water(rock, water_level, submersion_fraction=0.5):
    """Place rock so it's partially submerged."""
    rock_height = rock.dimensions.z
    # Rock origin is at center. Move down so desired fraction is below water.
    rock.location.z = water_level - (rock_height * submersion_fraction) + (rock_height * 0.5)
    # Result: bottom submersion_fraction of rock is below water_level
```

### 6.2 Foam and Debris Accumulation

**Upstream face:** Where flowing water meets a rock, foam and floating debris accumulate:
- Small foam patches on the upstream face, concentrated at waterline
- Leaves, twigs, small branches caught against the rock
- In dark fantasy: bones, cloth scraps, corrupted organic matter

**Implementation:** Spawn small decal planes at the upstream waterline of each large rock. Face the decal toward the flow direction. Use a foam/debris texture with alpha transparency.

### 6.3 Plants in Crevices

Crevices in rocks above the waterline are prime spots for small vegetation:

- **At waterline:** Moss, algae. Dark green to black.
- **0-0.5m above water:** Ferns, small grasses growing from cracks. Dense where spray reaches.
- **0.5-2m above water:** Lichen, small shrubs if crevice is large enough.

**Spawn rule:** For each rock face with a steep angle (>60 degrees from horizontal) and within 1m of water level, there is a 60-80% chance of moss/fern growth in any detected crevice.

### 6.4 Overhanging Rock Shadows

Rocks that extend over the water surface cast shadows that:
- Darken the water surface below (shadow decal or vertex color)
- Make the underwater area beneath the rock appear deeper/darker
- Create contrast that emphasizes the rock edge

**For the water shader:** Multiply water surface color by shadow factor. Alternatively, use a shadow map projected onto the water plane from above.

### 6.5 Snapping Rocks to Water Surface Level

The procedural placement algorithm for rocks near water:

```python
def scatter_rocks_near_water(water_level, terrain_mesh, params):
    """Place rocks with correct water interaction."""
    rocks = []
    for i in range(params.rock_count):
        # 1. Pick random position within scatter zone
        pos = random_point_in_scatter_zone(params)

        # 2. Sample terrain height at this position
        terrain_z = sample_terrain_height(terrain_mesh, pos.x, pos.y)

        # 3. Determine if this is underwater, shoreline, or land
        if terrain_z < water_level - 0.5:
            # Deep underwater: skip or place small underwater rock
            continue
        elif terrain_z < water_level + 0.3:
            # Shoreline zone: rock straddles waterline
            rock_size = random_rock_size(params)
            submersion = remap(terrain_z, water_level - 0.5, water_level + 0.3, 0.8, 0.1)
            z = water_level - rock_size * submersion
            apply_wet_material(rock, wet_factor=1.0 - submersion)
        else:
            # Above water: normal placement
            z = terrain_z
            distance_to_water = terrain_z - water_level
            if distance_to_water < 1.0:
                apply_damp_material(rock, damp_factor=1.0 - distance_to_water)

        rocks.append(create_rock(pos.x, pos.y, z, rock_size))
    return rocks
```

---

## 7. Dark Fantasy Water-Rock Aesthetic

### 7.1 Corrupted Water

VeilBreakers dark fantasy demands water that looks wrong, dangerous, or magical. Corrupted water surrounding rocks:

**Color Palette:**
- **Void corruption:** Deep purple-black (#1A0A2E) with cyan (#00FFD4) edge glow
- **Poison/plague:** Dark green-brown (#0A1F0A) with sickly yellow (#C4FF00) foam
- **Blood corruption:** Dark crimson (#2A0000) with black sediment
- **Arcane:** Deep blue-black (#0A0A2E) with electric blue (#0066FF) glow around specific rocks

**Glow Effect Around Rocks:**
Certain "corruption-touched" rocks emit a faint glow that reflects in surrounding water:
```python
# Emission on corrupted rocks: subtle glow in wet areas
emission_color = corruption_palette[corruption_type]
emission_strength = 0.3  # Subtle, not a light source
# Apply to rock material where wet_factor > 0.5
# Add matching glow to water material near the rock (within 1-2m)
```

### 7.2 Ancient Carved Stones in Riverbed

Submerged ruins and markers add narrative weight:

- **Broken columns:** Partially buried in river gravel, moss-covered above water
- **Rune stones:** Flat slabs with carved symbols, visible through shallow water
- **Bridge foundations:** Remnants of ancient bridges -- pairs of stone pillars in the riverbed
- **Offering stones:** Flat-topped rocks at waterfall bases with carved channels (for ritual use)

**Generation rule:** At points of interest (near ruins, settlements, crossroads near water), replace 1-2 natural rocks with carved stone variants. Use the existing `standing_stone` rock_type from generate_rock_mesh with added surface detail.

### 7.3 Bioluminescent Moss on Wet Cave Rocks

In cave environments near water, moss emits a faint glow:

**Color:** Blue-green (#00FF88) or purple (#8800FF), very low intensity
**Distribution:** Patches of 0.1-0.5m diameter, concentrated where water drips
**Intensity:** Emission strength 0.1-0.3, enough to be visible in darkness but not illuminating
**Animation:** Subtle pulsing (sine wave, 0.5-2 second period) via driver or keyframe

**Material setup:**
```python
# Bioluminescent moss material
moss_color = (0.02, 0.15, 0.05)  # Dark green base
emission_color = (0.0, 1.0, 0.53)  # Blue-green glow
emission_strength = 0.15  # Very subtle

# Apply as vertex color blend: moss zones on wet rock faces
# Only in cave environments or heavily shaded areas
```

### 7.4 Petrified Wood in Water

Fossilized tree trunks in rivers and lakes:

- **Color:** Dark grey-brown, with wood grain texture visible
- **Shape:** Cylindrical logs, 0.3-1m diameter, 2-5m long
- **Orientation:** Lying across the flow or wedged against rocks
- **Surface:** Rough, stone-like, but with visible wood grain patterns
- **Material:** Use rock roughness/metallic values but with wood-grain normal map

### 7.5 Blood-Stained Rocks at Battle Sites

Near combat areas adjacent to water:

- **Stain pattern:** Dark reddish-brown (#3A0A0A), concentrated on upstream faces
- **Age:** Fresh blood is redder; old stains are dark brown-black
- **Distribution:** Splatter pattern on 2-5 rocks near a battle site marker
- **In water:** Blood stains wash away below waterline but leave dark organic residue at waterline

---

## 8. Implementation for VeilBreakers

### 8.1 Current Codebase Gaps

Based on analysis of the existing handlers:

| Feature | Status | Location | Gap |
|---------|--------|----------|-----|
| Water body creation | EXISTS | environment.py `handle_create_water` | Has flow vertex colors, no rock interaction |
| Waterfall generator | EXISTS | terrain_features.py `generate_waterfall` | Has cliff + pool + materials, no rock scatter |
| Waterfall mesh | EXISTS | _terrain_depth.py `generate_waterfall_mesh` | Simpler version, no materials |
| Rock mesh generator | EXISTS | procedural_meshes.py `generate_rock_mesh` | boulder, standing_stone, crystal, rubble_pile, cliff_outcrop |
| Coastline | EXISTS | coastline.py | Has material zones including wet_rock, no rock placement |
| Wet rock material | MISSING | procedural_materials.py | No wet_rock material defined anywhere |
| Rock-water scatter | MISSING | -- | No system to place rocks relative to water level |
| Waterline staining | MISSING | -- | No waterline material zone on rocks |
| Gravel bar generation | MISSING | -- | No gravel bar at river bends |
| Underwater rock visibility | MISSING | -- | No depth-based material blending |
| Dark fantasy water glow | MISSING | -- | No corruption/bioluminescence materials |

### 8.2 Recommended Implementation Order

1. **Wet Rock Material** -- Add to `procedural_materials.py`. Use Lagarde-derived values. Z-height-based blending between wet and dry. This is the foundation everything else depends on.

2. **Rock-Water Scatter System** -- New function in `environment_scatter.py` or `terrain_features.py`. Given a water body and terrain, scatter rocks with correct submersion, size grading, and material assignment.

3. **Waterfall Rock Scatter** -- Enhance `generate_waterfall` to scatter fallen boulders around the plunge pool and at the base of the cliff. Apply spray zone material gradient.

4. **Gravel Bar Generation** -- Detect bends in river splines (from `handle_create_water` path_points), spawn gravel bars on inside of bends with size-graded cobbles.

5. **Shoreline Rock Placement** -- Enhance coastline.py to include rock placement with waterline staining and size grading.

6. **Dark Fantasy Water Effects** -- Add corruption material variants: glowing water near rocks, bioluminescent moss, blood staining. Integrate with existing dungeon theme system.

### 8.3 Key Data Structures

```python
# Water-rock interaction config
WATER_ROCK_CONFIG = {
    "river_rocks": {
        "density": 0.3,          # rocks per square meter in rocky sections
        "size_range": (0.1, 2.5), # meters
        "size_power_law": 2.5,    # larger rocks exponentially rarer
        "cluster_probability": 0.6,
        "cluster_size": (2, 7),
        "submersion_range": (0.3, 0.7),  # fraction below water
        "flow_orientation": True,  # orient to flow direction
    },
    "waterfall_rocks": {
        "plunge_pool_count": (3, 8),  # fallen boulders around pool
        "size_range": (0.5, 3.0),
        "spray_zone_moss": True,
        "cliff_base_rubble": True,
    },
    "lake_shore_rocks": {
        "density_at_waterline": 0.5,
        "density_falloff": 0.7,   # multiplier per meter from water
        "size_grading": True,     # larger near water, smaller inland
        "waterline_staining": True,
        "algae_below_water": True,
    },
    "gravel_bar": {
        "min_bend_curvature": 0.1,  # radians per meter
        "bar_width_fraction": 0.3,   # fraction of river width
        "size_upstream": 0.15,       # meters, largest cobbles
        "size_downstream": 0.03,     # meters, smallest pebbles
    },
}

# Wet rock material zones
WET_ROCK_ZONES = {
    "submerged": {
        "color_multiply": 0.55,
        "roughness": (0.10, 0.25),
        "moss_coverage": 0.0,  # too deep for moss usually
        "algae_coverage": 0.8,
    },
    "waterline": {
        "color_multiply": 0.65,
        "roughness": (0.15, 0.30),
        "moss_coverage": 0.3,
        "mineral_stain": True,
        "transition_height": 0.1,  # meters
    },
    "splash_zone": {
        "color_multiply": 0.75,
        "roughness": (0.30, 0.50),
        "moss_coverage": 0.6,
        "transition_height": 0.5,
    },
    "damp": {
        "color_multiply": 0.85,
        "roughness": (0.50, 0.70),
        "moss_coverage": 0.2,
        "transition_height": 1.0,
    },
    "dry": {
        "color_multiply": 1.0,
        "roughness": (0.80, 0.95),
        "moss_coverage": 0.05,
    },
}
```

### 8.4 Integration Points

**With map_composer.py:** The `compose_map` pipeline already calls `handle_create_water` for rivers and lakes. Add a post-water step that calls the rock-water scatter system for each water body created.

**With vegetation_system.py:** The biome configs already include boulder scatter. Enhance to use wet_rock material for boulders near water bodies. Check `corrupted_swamp`, `dark_forest`, and `mountain_pass` biomes.

**With terrain_features.py:** The waterfall generator already returns splash_zone data. Use this to drive the spray zone material gradient on surrounding rocks.

**With terrain_materials.py:** Add wet_rock, waterline, splash_zone, and algae material presets to the terrain material library.

---

## 9. Sources

### Physically-Based Wet Surface Rendering
- [Water drop 3a - Physically based wet surfaces (Lagarde)](https://seblagarde.wordpress.com/2013/03/19/water-drop-3a-physically-based-wet-surfaces/) -- Definitive reference for wet surface PBR. HIGH confidence.
- [Water drop 3b - Physically based wet surfaces (Lagarde)](https://seblagarde.wordpress.com/2013/04/14/water-drop-3b-physically-based-wet-surfaces/) -- HLSL implementation, porosity formula, game-ready code. HIGH confidence.
- [Why do things look darker when wet? (Polycount)](https://polycount.com/discussion/154210/why-do-things-look-darker-when-wet-translate-to-pbr) -- Community discussion validating Lagarde values. MEDIUM confidence.

### Hydrology and Sediment Transport
- [Sediment Transport and Deposition (Fondriest)](https://www.fondriest.com/environmental-measurements/parameters/hydrology/sediment-transport-deposition/) -- Grain size sorting, velocity relationships. HIGH confidence.
- [How Sediment Deposition Shapes River Landscapes (World Rivers)](https://worldrivers.net/2020/04/02/sediment-deposition/) -- Point bar formation, gravel bar mechanics. HIGH confidence.
- [Water Erosion and Deposition (Geosciences LibreTexts)](https://geo.libretexts.org/Bookshelves/Geology/Fundamentals_of_Geology_(Schulte)/11:_Hydrology/11.05:_Water_Erosion_and_Deposition) -- Thalweg dynamics, cut banks, meander deposition. HIGH confidence.
- [Plunge Pool (Wikipedia)](https://en.wikipedia.org/wiki/Plunge_pool) -- Plunge pool dimensions, erosion mechanics. MEDIUM confidence.

### Procedural Generation Tools
- [Dynamic Flow Blender Add-on (CG Channel)](https://www.cgchannel.com/2026/01/check-out-real-time-blender-water-simulation-add-on-dynamic-flow/) -- Terrain-aware water flow, foam at intersections. MEDIUM confidence.
- [Baga River Generator (CG Channel)](https://www.cgchannel.com/2025/05/baga-river-generator-lets-you-draw-rivers-into-blender-scenes/) -- Spline-based rivers with rock scatter. MEDIUM confidence.
- [Houdini Waterfall with Procedural Terrain (SideFX)](https://www.sidefx.com/gallery/houdini-waterfall-with-procedural-terrain-asset-generation/) -- AAA waterfall generation pipeline. MEDIUM confidence.

### Game Water Rendering
- [Water foam/shoreline shader (Unity Forums)](https://forum.unity.com/threads/water-foam-shoreline-shader.347107/) -- Depth-based intersection foam techniques. MEDIUM confidence.
- [How to create a semi procedural cartoon foam shader (Game Developer)](https://www.gamedeveloper.com/programming/how-to-create-a-semi-procedural-cartoon-foam-shader) -- Distance field foam generation. MEDIUM confidence.
