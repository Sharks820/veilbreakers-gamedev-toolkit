# Terrain Feature Visual Details -- Quantitative Reference for Procedural Generation

**Researched:** 2026-04-03
**Domain:** Geomorphology, fluvial geomorphology, geology, landscape ecology
**Purpose:** Exact measurements, angles, and visual rules for terrain feature generators
**Confidence:** HIGH (cross-referenced geological textbooks, USGS data, geomorphology papers)

---

## Current State of VeilBreakers Generators

The existing `terrain_features.py` has 10 generators: canyon, waterfall, cliff_face, swamp, natural_arch, geyser, sinkhole, floating_rocks, ice_formation, lava_flow. These create hard-carved channels and basic shapes without the nuanced geometry of real terrain. Key problems:

- Cliff faces use a single overhang factor, no strata layers or differential erosion
- Waterfall creates step-down terrain but pool geometry is basic (flat disc)
- No river bank generator exists at all
- No stream/tributary, pond/lake, boulder formation, forest clearing, or mountain pass generators
- Canyon walls are smooth noise surfaces without geological layering

This document provides the EXACT quantitative data needed to fix existing generators and build new ones.

---

## 1. River Banks

### Bank Angles (Cross-Section Profile)

| Bank Type | Angle from Horizontal | Material | Visual Character |
|-----------|----------------------|----------|-----------------|
| **Cut bank** (outer meander) | 60-90 degrees | Cohesive clay/silt: near-vertical (80-90 deg). Non-cohesive sand/gravel: 50-70 deg | Steep, exposed soil layers visible, active erosion, undercut at waterline, slumped blocks at base |
| **Slip-off slope** (inner meander / point bar) | 5-15 degrees | Sand, pebbles, gravel | Gentle ramp, wet near water, gradually transitions to dry. Deposited sediment forms a convex arc |
| **Straight reach** | 20-40 degrees | Mixed | Moderate slope, root-stabilized in forested areas |

**Source:** Haw River geomorphology study measured mean bank angle 53 deg, max 90 deg. Cut banks typically 60-90 deg in cohesive sediments.

### Transition Zones (Water to Dry Land)

The transition from water edge to normal terrain follows this layered profile. Total width: 2-8m depending on bank slope.

```
CROSS-SECTION (looking downstream):

Normal terrain (grass/forest)
    |  Dry bank (0.5-2m)  -- normal soil color, vegetation rooted
    |  Damp earth (0.5-1m) -- darker soil, sparse low vegetation
    |  Wet mud (0.3-0.5m) -- gleaming when wet, no vegetation
    |  Submerged pebbles (0-0.5m) -- visible through shallow water
    |  Stream bed
    ~~~~water surface~~~~
```

**Layer materials from water outward:**

| Zone | Width | Color/Appearance | Vegetation |
|------|-------|-----------------|------------|
| Submerged bed | 0-1m from bank | Dark pebbles/sand visible through water, algae green-brown | None |
| Wet mud | 0.3-0.5m | Dark brown/black, glossy wet surface, boot prints | None |
| Damp earth | 0.5-1.5m | Medium brown, slightly darker than surroundings | Sparse moss, small ferns, sedge grass |
| Riparian edge | 1-3m | Earth tone transitioning to normal | Dense grass, reeds, low shrubs, willow roots |
| Normal terrain | Beyond 3-5m | Normal terrain color | Full ground cover for biome |

### Biome Variations

| Biome | Bank Character | Unique Features |
|-------|---------------|-----------------|
| **Forest** | Root-reinforced, 30-50 deg slopes, exposed root systems on cut banks | Tree roots visible in bank face, leaf litter on banks, moss on wet rocks, fallen logs across stream |
| **Grassland** | Lower banks (1-3m high), 20-40 deg, more gradual | Grass grows to water edge, less erosion, wider floodplain, muddy access points |
| **Mountain** | Rocky, 40-70 deg, boulder-strewn | Exposed bedrock in bank, large cobbles, steeper gradient, whitewater, less vegetation |
| **Swamp/Wetland** | Nearly flat (0-10 deg), indistinct boundary | No clear bank edge, gradual transition water-to-land, dense reeds, murky water |

### Cut Bank vs Point Bar Formation

**Cut bank** forms on the OUTSIDE of meander bends where water velocity is highest (1.5-3x average velocity). The bank is undercut at the waterline, creating an overhang 0.3-1m deep. Soil blocks slump from above, creating rubble at the base.

**Point bar (slip-off slope)** forms on the INSIDE of meander bends where water velocity is lowest. Sediment deposits here, building a gentle ramp. Coarser gravel deposits closer to the channel, finer sand/silt further from water.

### Implementation Parameters

```python
# River bank cross-section generator parameters
BANK_PARAMS = {
    "cut_bank": {
        "angle_deg": (60, 90),      # Range for cohesive soils
        "height_m": (1.0, 5.0),     # Bank height
        "undercut_depth_m": (0.0, 1.0),  # Overhang at waterline
        "slump_blocks": True,        # Fallen soil chunks at base
        "exposed_layers": 3,         # Visible soil strata
    },
    "point_bar": {
        "angle_deg": (5, 15),
        "width_m": (2.0, 10.0),     # Lateral extent of bar
        "gravel_zone_width_m": (0.5, 2.0),  # Near channel
        "sand_zone_width_m": (1.0, 5.0),    # Further from channel
    },
    "straight_bank": {
        "angle_deg": (20, 40),
        "transition_width_m": (2.0, 5.0),
    },
}
```

---

## 2. Cliff Faces

### Cliff Angles by Rock Type

| Rock Type | Typical Angle | Visual Character |
|-----------|--------------|-----------------|
| **Granite** (hard igneous) | 80-90 deg (near vertical) | Massive, few horizontal layers, vertical joint cracks, grey-pink, clean faces |
| **Basalt** (hard igneous) | 75-90 deg | Columnar jointing (hexagonal columns), dark grey-black, very regular geometry |
| **Limestone** (hard sedimentary) | 70-85 deg | Horizontal strata bands (0.3-2m thick), solution pockets, grey-white, cave entrances |
| **Sandstone** (medium sedimentary) | 60-80 deg | Prominent horizontal banding, warm red-orange-buff colors, rounded erosion, alcoves |
| **Shale/mudstone** (soft sedimentary) | 45-65 deg | Thin laminated layers (mm to cm), crumbly, dark grey, prone to rockfall, debris slopes |
| **Chalk** (soft sedimentary) | 70-85 deg | Pure white, near vertical but recedes rapidly, flint bands visible |

### Strata Layer Appearance

**Layer thickness ranges:**
- Fine laminae: 1mm - 2cm
- Standard beds: 10cm - 2m (most common for visible cliff banding)
- Massive beds: 2m - 10m (appear as single large blocks)

**Visual rules for procedural strata:**
1. Layers are predominantly horizontal (0-5 deg tilt for undisturbed strata)
2. Alternate between resistant (protruding 5-20cm) and recessive (indented 5-20cm) layers
3. Color varies between layers: slight shifts in grey, tan, brown, reddish tones
4. Resistant layers create small ledges (5-30cm wide) that accumulate debris and small plants
5. Layer boundaries are the primary location for moisture seepage (darker wet streaks)
6. Joint cracks cross-cut layers vertically at roughly regular spacing (1-5m apart)

```
CLIFF FACE PROFILE (side view):

    |_____|  <- Resistant layer, protruding
    |     |  <- Recessive layer, indented
    |_____|  <- Resistant layer (widest = main ledge)
    |     |  <- Recessive with moisture seepage (dark streak)
    |_____|  <- Resistant layer
    |     |
    |  /     <- Overhang/undercut from differential erosion
    | /
    |/________  <- Talus pile at base
     \  .  . /   angle of repose: 30-38 deg
      \. . ./
       \. ./
```

### Erosion Patterns

| Pattern | Location | Appearance |
|---------|----------|------------|
| **Vertical water channels** | Follow joint cracks | Dark stained grooves 10-50cm wide, deeper at top, fan out at base, moss/lichen filled |
| **Horizontal undercuts** | At layer boundaries | Recessive layers erode inward 0.3-2m, creating shelves and shallow caves |
| **Solution pockets** (limestone only) | Random across face | Rounded holes 5-50cm diameter, often clustered, dark interior |
| **Exfoliation sheets** (granite) | On rounded surfaces | Curved plates 2-20cm thick peeling away from face |
| **Honeycomb weathering** (sandstone) | Sheltered areas | Grid of small cavities 1-10cm, creates intricate texture |

### Vegetation on Cliffs

| Location | Plant Type | Visual |
|----------|-----------|--------|
| Vertical cracks | Ferns, small grasses | Green tufts sprouting from crack lines |
| Ledges (>15cm wide) | Small shrubs, saplings | Stunted growth, wind-shaped, rooted in debris |
| Moist seepage zones | Moss, liverworts | Bright green patches, wet-looking, around water streaks |
| Overhang undersides | Moss, hanging roots | Dampness-dependent, sparse near dry overhangs |
| Cliff top edge | Trees leaning outward | Roots visible at edge, canopy extends over void |

### Talus/Scree at Cliff Base

**Angle of repose by material:**

| Material | Angle of Repose | Character |
|----------|----------------|-----------|
| Angular rock fragments | 35-40 deg | Interlocking pieces, stable cone |
| Rounded cobbles | 30-35 deg | Less stable, gaps between pieces |
| Mixed sand/gravel | 25-35 deg | Smoother surface, smaller particles fill gaps |
| Wet material | 15-25 deg | Reduced angle due to lubrication |

**Talus cone geometry:**
- Forms a half-cone shape against cliff base
- Width at base: 0.5x to 2x cliff height
- Largest fragments at bottom (inverse grading -- large rocks roll further)
- Small fragments accumulate near top of pile
- Vegetation colonizes older, stable sections (grass, then shrubs)
- Active rockfall areas are bare with fresh-colored rock fragments

### Implementation Parameters

```python
CLIFF_PARAMS = {
    "strata": {
        "layer_thickness_range": (0.3, 2.0),  # meters
        "layer_count": lambda height: max(3, int(height / 0.8)),
        "protrusion_range": (0.05, 0.20),     # meters, how far layers stick out
        "color_variation": 0.15,               # HSV value shift between layers
        "joint_spacing": (1.0, 5.0),           # meters between vertical cracks
        "joint_depth": (0.05, 0.15),           # meters into face
    },
    "talus": {
        "angle_of_repose_deg": (32, 38),
        "base_width_ratio": (0.5, 1.5),       # relative to cliff height
        "fragment_size_gradient": True,         # large at bottom, small at top
    },
    "erosion_channels": {
        "width_range": (0.1, 0.5),            # meters
        "spacing": (2.0, 8.0),                # meters apart
        "depth_range": (0.02, 0.10),          # meters into face
    },
}
```

---

## 3. Mountain Passes

### Dimensional Ranges

| Parameter | Small Pass | Medium Pass | Major Pass |
|-----------|-----------|-------------|------------|
| Width between peaks | 50-100m | 100-300m | 300-1000m+ |
| Trail width (foot) | 1.5-3m | 2-4m | -- |
| Trail width (cart/road) | -- | 4-6m | 6-12m |
| Saddle depth below peaks | 50-200m | 100-500m | 200-1000m |
| Approach grade | 10-25% (6-14 deg) | 8-15% (5-9 deg) | 5-10% (3-6 deg) |

### Vegetation Change with Altitude

For a temperate/European dark fantasy setting (VeilBreakers):

| Altitude Zone | Elevation (temperate) | Vegetation | Ground Cover |
|--------------|----------------------|------------|--------------|
| **Valley floor** | 0-500m | Dense deciduous forest, thick undergrowth | Leaf litter, moss, ferns |
| **Montane forest** | 500-1500m | Mixed deciduous-coniferous, trees thinner | Pine needles, sparse undergrowth |
| **Subalpine** | 1500-2000m | Stunted conifers (krummholz), wind-shaped | Heather, low shrubs, rocky soil |
| **Alpine treeline** | 2000-2500m | Last isolated, twisted trees | Alpine meadow grasses, wildflowers |
| **Alpine** | 2500-3000m | No trees, only ground-hugging plants | Cushion plants, lichen on rocks, bare rock |
| **Nival** | 3000m+ | No vascular plants | Snow, ice, bare rock only |

**Treeline note:** In VeilBreakers dark fantasy setting, assume temperate treeline at ~1800-2200m for gothic atmosphere (lower than real-world to emphasize barren peaks).

### Rock Types at High Altitude

| Feature | Description | Size |
|---------|-------------|------|
| Exposed bedrock | Flat slabs, glacially polished, striations visible | Continuous outcrops 5-50m across |
| Frost-shattered boulders | Angular, broken along joint planes, sharp edges | 0.3-3m diameter |
| Scree fields | Loose angular fragments covering slopes | Continuous slopes 50-500m wide |
| Glacial erratics | Isolated large boulders, often different rock type | 1-10m diameter, perched on bedrock |
| Moraine ridges | Linear boulder/gravel ridges | 2-10m high, 5-20m wide, km-long |

### Snow Line Appearance

- Patches in north-facing shadows and gullies first (down to 500m below full snowline)
- Full continuous cover above snowline
- Transition zone: 200-500m vertical where snow is patchy
- Snow accumulates in concavities, melts on convexities and south faces
- Cornices form at ridge crests (overhanging snow on lee side)

### Implementation Parameters

```python
PASS_PARAMS = {
    "saddle_width": (50.0, 300.0),     # meters between flanking peaks
    "trail_width_foot": (2.0, 3.5),    # meters
    "trail_width_cart": (4.0, 8.0),    # meters
    "approach_grade_pct": (8.0, 20.0), # percent slope
    "treeline_altitude": (1800, 2200), # meters (dark fantasy, lower than reality)
    "snow_patch_start": -500,          # meters below full snowline
    "vegetation_zones": [
        {"name": "valley", "max_alt": 500, "tree_density": 0.8},
        {"name": "montane", "max_alt": 1500, "tree_density": 0.5},
        {"name": "subalpine", "max_alt": 2000, "tree_density": 0.15},
        {"name": "alpine", "max_alt": 2500, "tree_density": 0.0},
        {"name": "nival", "max_alt": 99999, "tree_density": 0.0},
    ],
}
```

---

## 4. Forest Clearings

### Natural Clearing Dimensions

| Cause | Shape | Typical Diameter | Regularity |
|-------|-------|-----------------|------------|
| **Fallen giant tree** | Elongated oval aligned with trunk direction | 15-30m long x 8-15m wide | Moderate, follow crown spread |
| **Wet soil / poor drainage** | Irregular, tends circular | 10-50m | Low, follows water table contour |
| **Rock outcrop** | Follows rock shape, irregular | 5-30m | Low, sharp edges where rock meets soil |
| **Lightning fire** | Roughly circular with tendrils | 20-100m | Low, follows fire spread |
| **Wind throw** | Linear or fan-shaped | 20-80m long | Moderate, aligned with storm direction |

### Edge Vegetation Profile

The forest edge around a clearing creates a distinct "wall" effect. Edge effects penetrate 10-100m into forest, but the visible dense edge is 3-10m wide.

```
PLAN VIEW:

         Forest (dark, sparse undergrowth)
    -----.....-----.....-----
    Dense edge zone (3-10m)
    - Shrubs, brambles, saplings
    - Light-seeking lateral branches
    - 2-3x undergrowth density
    ============================
    Clearing interior
    - Grass/wildflowers (center)
    - Dappled light at edges
    - Gradually brighter toward center
    ============================
    Dense edge zone (3-10m)
    -----.....-----.....-----
         Forest
```

**Edge details:**
- Trees at the edge have lower branches (light-seeking), creating a "curtain" effect
- Undergrowth density at edge is 2-3x the forest interior
- Species shift: shade-tolerant interior species give way to sun-loving edge species
- Brambles, wild roses, blackberry create thorny barriers at edges
- First 1-2m inside edge: seedlings and saplings compete for light

### Ground Cover by Cause

| Clearing Type | Center Ground | Edge Ground | Debris |
|---------------|--------------|-------------|--------|
| Fallen tree | Young grass, ferns | Dense regrowth | Decaying trunk, root ball visible |
| Wet depression | Sedge grass, rushes, standing water | Wet-tolerant shrubs | Waterlogged soil visible |
| Rock outcrop | Bare rock, lichen, moss pockets | Thin soil over rock, stunted plants | Loose rock fragments |
| Fire clearing | New grass, fireweed | Charred stumps at edges | Charcoal soil, blackened trunks |

### Light Quality

- Center: 80-100% of open sky light
- 2m from edge: 50-70% (dappled)
- Under canopy drip line: 10-30% (deep shadow)
- Morning/evening: long shadows from edge trees cross the clearing
- Sun patches move across floor as sun traverses (important for atmosphere)

### Implementation Parameters

```python
CLEARING_PARAMS = {
    "diameter_range": (10.0, 50.0),    # meters
    "shape_irregularity": 0.3,          # 0=circle, 1=very irregular
    "edge_zone_width": (3.0, 8.0),     # meters of dense undergrowth
    "edge_tree_branch_height_factor": 0.3,  # branches start at 30% of tree height (vs 60% in interior)
    "undergrowth_density_multiplier": 2.5,  # at edge vs interior
    "center_ground_types": ["grass", "wildflowers", "ferns", "bare_earth"],
    "light_falloff_from_edge": 3.0,     # meters to reach full brightness from tree line
}
```

---

## 5. Boulder Formations

### Arrangement Patterns by Origin

| Origin | Pattern | Size Distribution | Spacing |
|--------|---------|-------------------|---------|
| **Glacial erratics** | Random scatter, isolated boulders | Varies widely: 0.5m to 10m+, no pattern | 10-100m+ apart, very sparse |
| **Glacial moraine** | Linear ridges, clustered | Mixed: boulders in gravel/clay matrix | Dense along ridge line |
| **River deposited** | Aligned with flow direction, size-sorted | Decreasing downstream, 0.2-2m | Clustered in bars and riffles |
| **Cliff base (talus)** | Fan/cone shape radiating from cliff | Largest at bottom, smallest at top (inverse grading). Power law: N proportional to d^(-2.5) | Dense, touching/overlapping |
| **Exposed bedrock** (tor) | Stacked, rounded, often balanced | 1-5m diameter, roughly similar sizes | Touching, stacked 2-5 high |
| **Frost-shattered** | Scattered around parent outcrop | Angular, 0.1-1m | Dense near source, sparse outward |

### Size Distribution (Power Law)

Natural boulder fields follow a power-law size distribution:
- For every boulder of diameter D, there are approximately (D_ref/D)^2.5 boulders
- Example: for every 2m boulder, expect ~6 boulders at 1m, ~34 at 0.5m, ~200 at 0.25m
- Procedural generation should use this ratio to populate scatter

```python
def boulder_count_at_size(ref_size, ref_count, target_size):
    """Power law: count = ref_count * (ref_size / target_size) ** 2.5"""
    return int(ref_count * (ref_size / target_size) ** 2.5)
```

### Moss and Lichen Patterns

| Surface | Coverage | Color |
|---------|----------|-------|
| **North-facing** (northern hemisphere) | 40-80% moss coverage | Green (moss), grey-green (lichen) |
| **South-facing** | 10-30% lichen, minimal moss | Yellow-grey, orange (crustose lichen) |
| **Top surface** | Sparse lichen, bird droppings | White splashes, grey-green patches |
| **Sheltered undersides** | Dense moss if moist, bare if dry | Dark green, or bare grey rock |
| **Ground contact zone** | Heavy moss, soil staining | Dark, organic-stained, moss creeping up 10-30cm |

**Moss placement rules:**
1. Always heaviest on the north side (in the northern hemisphere)
2. Heaviest in damp, shaded areas
3. Forms a gradient: dense at ground level, thinning toward top
4. Crevices and concavities catch moisture and have more moss
5. Lichen is everywhere moss is not -- dry, exposed, sun-facing surfaces

### How Boulders Sit in Ground

Boulders are NOT placed on the surface. They are partially embedded:

| Boulder Size | Burial Depth | Soil Buildup |
|-------------|-------------|--------------|
| < 0.5m | 30-50% buried | Minimal soil mound |
| 0.5-2m | 20-40% buried | Soil built up on uphill side (10-30cm higher) |
| 2-5m | 10-30% buried | Clear soil mound on uphill side, depression on downhill |
| > 5m | 5-20% buried | Significant terracing effect, smaller rocks accumulate around base |

**Visual rules:**
- Grass/moss grows up against boulder on all sides
- Small debris (leaves, twigs) collects on uphill side
- Downhill side may have a small erosion scour (5-15cm depression)
- Large boulders cast rain shadows: dry strip on lee side has less vegetation

### Implementation Parameters

```python
BOULDER_PARAMS = {
    "burial_depth_pct": (0.15, 0.45),    # fraction of diameter below surface
    "uphill_soil_buildup": (0.05, 0.30),  # meters of soil on uphill side
    "moss_coverage_north_pct": (0.4, 0.8),
    "moss_coverage_south_pct": (0.05, 0.25),
    "moss_ground_gradient_height": 0.3,    # meters -- moss thickest in bottom 30cm
    "power_law_exponent": 2.5,             # size distribution
    "size_classes": [0.2, 0.5, 1.0, 2.0, 4.0],  # meters diameter
}
```

---

## 6. Waterfalls

### Types and Geometry

| Type | Fall Angle | Water-Rock Contact | Pool Shape |
|------|-----------|-------------------|------------|
| **Plunge** | Vertical (90 deg) | None -- water free-falls | Deep circular plunge pool |
| **Horsetail** | 70-85 deg | Continuous contact | Shallower pool, wider spray |
| **Cascade** | 45-70 deg (stepped) | Full contact over steps | Series of small pools between steps |
| **Block/Sheet** | 80-90 deg | Minimal, wide curtain | Wide shallow pool |
| **Tiered** | Multiple vertical drops | None per tier | Pool between each tier |

### Plunge Pool Dimensions

The plunge pool depth is directly related to the fall height and water volume:

| Fall Height | Pool Depth | Pool Diameter | Spray Radius |
|------------|-----------|---------------|-------------|
| 3-5m | 0.5-2m | 3-6m | 3-5m |
| 5-10m | 1-4m | 5-10m | 5-8m |
| 10-20m | 2-8m | 8-15m | 8-12m |
| 20-50m | 5-15m | 10-25m | 15-25m |

**Rule of thumb:** Pool depth is approximately 30-60% of fall height. Pool diameter is approximately 1-2x fall height.

### Spray Zone Details

| Distance from Base | Conditions | Vegetation |
|-------------------|------------|------------|
| 0-2m | Constant spray, rocks always wet, roaring sound | Moss-covered boulders, liverworts |
| 2-5m | Intermittent spray, mist, rocks wet | Dense ferns, moss, small plants |
| 5-10m | Light mist, rocks damp | Lush vegetation ring, larger ferns |
| 10-20m | Occasional mist in wind | Normal vegetation, slightly damp soil |

**Visual rules for spray zone:**
1. ALL rocks within spray radius have darker, wet-look material (higher roughness metallic=0, lower roughness value ~0.2-0.4)
2. Moss coverage increases dramatically near waterfalls (80-100% in splash zone)
3. Rainbow effect possible in afternoon sun (atmospheric effect, not geometry)
4. Water staining below the fall creates dark streaks on cliff face

### Rock Behind Waterfall

- Erosion creates an overhang/cave behind the fall (depth 1-5m for a 10m fall)
- The cave follows the full width of the waterfall plus 1-3m on each side
- Rock surface inside is smooth from water erosion, dark colored
- Stalactite-like mineral deposits possible on cave ceiling
- Floor is wet, with gravel and rounded pebbles

### Implementation Parameters

```python
WATERFALL_PARAMS = {
    "plunge": {
        "fall_angle_deg": 90,
        "pool_depth_ratio": (0.3, 0.6),       # fraction of fall height
        "pool_diameter_ratio": (1.0, 2.0),     # fraction of fall height
        "spray_radius_ratio": (0.8, 1.5),      # fraction of fall height
        "cave_depth_ratio": (0.1, 0.5),        # fraction of fall height
        "cave_width_extra": (1.0, 3.0),        # meters beyond water width on each side
    },
    "cascade": {
        "fall_angle_deg": (45, 70),
        "step_count": (3, 8),
        "step_height_variation": 0.3,          # random variation in step height
        "pool_between_steps_depth": (0.2, 0.8), # meters
    },
    "horsetail": {
        "fall_angle_deg": (70, 85),
        "contact_roughness": 0.5,              # how bumpy the contact surface is
    },
    "spray_zone": {
        "wet_rock_radius_ratio": 1.0,          # radius = fall_height * ratio
        "moss_radius_ratio": 0.8,
        "fern_radius_ratio": 1.5,
    },
}
```

---

## 7. Ponds and Lakes

### Shoreline Geometry

**Fractal dimension of natural lake shorelines: approximately 1.28** (measured across thousands of lakes globally). This means:
- Shorelines are irregular but not extremely convoluted
- At every scale, there are bays within bays
- Use fractal subdivision with dimension ~1.3 for realistic outlines

**Practical generation approach:**
1. Start with a base ellipse or irregular polygon (8-16 vertices)
2. Apply midpoint displacement with scaling factor 0.3-0.5
3. Iterate 3-4 times for natural look
4. Smooth sharp concavities (water fills them)

### Depth Profile

| Distance from Shore | Depth | Substrate |
|--------------------|-------|-----------|
| 0-1m (wadeable) | 0-0.5m | Sand, mud, organic debris |
| 1-5m (littoral shelf) | 0.5-2m | Sand/silt, rooted aquatic plants |
| 5-15m (littoral slope) | 2-5m | Silt, submerged plants (if clear water) |
| 15m+ (profundal) | 5m+ (lakes) | Fine silt/clay, no light, no plants |

**Pond vs Lake:**
- Pond: < 2 hectares surface area, often circular/oval, typically < 5m deep, light reaches bottom everywhere
- Lake: > 2 hectares, irregular shape, typically > 5m deep, profundal zone exists

### Vegetation Zones (Water Outward)

```
CROSS-SECTION (shore to open water):

  Dry land  | Wet meadow | Marsh    | Emergent   | Floating    | Submerged  | Open water
            | (0-3m)     | (0-2m)   | reeds      | lily pads   | weeds      |
  Grass,    | Sedge,     | Cattails,| Bulrushes, | Water       | Pondweed,  | No plants
  shrubs    | rushes     | reeds    | horsetails | lilies,     | milfoil    |
            |            |          |            | duckweed    |            |
  _____|____|____________|__________|____________|_____________|____________|____
       |    |     0m     |   0.3m   |   0.5m     |    1m       |    2m      | 3m+
       |                            Water depth
```

| Zone | Width from Shore | Water Depth | Dominant Plants |
|------|-----------------|-------------|-----------------|
| Wet meadow | 0-5m landward | Above waterline, saturated soil | Sedge grasses, rushes, wildflowers |
| Marsh/emergent | 0-3m waterward | 0-0.5m | Cattails, bulrushes (stems above water) |
| Floating leaf | 3-8m waterward | 0.5-2m | Water lilies, duckweed |
| Submerged | 5-15m waterward | 1-4m | Pondweed, milfoil (below surface) |
| Open water | Beyond plants | 2m+ | None (or floating algae) |

### Small Pond Specific Details

For VeilBreakers dark fantasy forest ponds:
- Diameter: 5-30m (small atmospheric ponds)
- Shape: roughly circular to oval, irregular edges
- Depth: 0.5-3m at center
- Surface: dark reflective water, occasional leaf floating
- Edge: thick reeds and rushes in 50-80% of perimeter
- One or two access points (mud banks, game trails to water)
- Deadfall (fallen branches/logs) partially submerged at edges

### Implementation Parameters

```python
POND_LAKE_PARAMS = {
    "pond": {
        "diameter_range": (5.0, 30.0),
        "max_depth": (0.5, 3.0),
        "shape_vertices": (8, 16),           # base polygon vertices
        "fractal_iterations": 3,
        "fractal_displacement": 0.4,
        "reed_coverage_pct": (0.4, 0.8),     # perimeter with reeds
        "access_points": (1, 3),              # mud bank gaps in reeds
    },
    "lake": {
        "diameter_range": (100.0, 1000.0),
        "max_depth": (5.0, 30.0),
        "shoreline_fractal_dim": 1.28,
        "littoral_shelf_width": (5.0, 15.0),  # meters
        "littoral_depth": (0.5, 2.0),          # meters
    },
    "depth_profile": {
        "shelf_slope_deg": (5, 15),           # littoral shelf angle
        "drop_off_slope_deg": (20, 45),       # slope to deep water
    },
}
```

---

## 8. Streams and Tributaries

### Dimensional Ranges

| Stream Type | Width | Depth | Velocity |
|------------|-------|-------|----------|
| Rill / seep | 0.1-0.3m | 0.02-0.05m | Very slow |
| Small brook | 0.5-1.5m | 0.05-0.2m | Moderate |
| Stream | 1.5-5m | 0.1-0.5m | Moderate-fast |
| Large stream | 5-15m | 0.3-1.5m | Variable |
| Small river | 15-50m | 0.5-3m | Variable |

### Meandering Pattern

**Sinuosity ratio** = channel length / straight-line distance:
- Straight channel: 1.0-1.05
- Sinuous: 1.05-1.5
- Meandering: 1.5-3.0+ (most natural streams)
- Highly meandering: > 3.0

**Meander wavelength** = approximately 11x channel width (classic rule):
- 1m wide stream: meander wavelength ~11m
- 3m wide stream: meander wavelength ~33m
- 10m wide stream: meander wavelength ~110m

**Meander amplitude** (belt width) = approximately 3-5x channel width

**Meander radius of curvature** = approximately 2-3x channel width

### Confluence Geometry (Tributary Junctions)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Junction angle | 30-60 deg | Smaller tributaries join at sharper angles |
| Width increase | Main stream widens ~1.2-1.5x below confluence | Not doubled -- combined width is less than sum |
| Confluence scour pool | 1.5-2x normal depth | Turbulence at junction scours deeper |
| Sediment bar | Wedge-shaped deposit at junction | On inside of junction angle |

```
PLAN VIEW (tributary joining main stream):

        Tributary
           \   30-60 deg angle
            \
             \
    Main ======\=======> Main (slightly wider)
    stream      junction   
                pool (deeper)
```

### Ford/Crossing Points

Natural fords occur at **riffles** -- shallow, wide sections between deeper pools:

| Parameter | Value |
|-----------|-------|
| Riffle depth | 0.1-0.3m (wadeable) |
| Riffle length | 3-7x stream width |
| Riffle spacing | 5-7x stream width (riffle-pool-riffle pattern) |
| Substrate | Exposed gravel and cobbles, some stones above waterline |
| Width at ford | 1.3-2x normal width (stream spreads out where shallow) |

**Stepping stones:** 0.3-0.8m diameter rocks spaced 0.5-1m apart, tops 5-15cm above water surface.

### Stream Bed Features

| Feature | Spacing | Size | Visual |
|---------|---------|------|--------|
| Riffles (shallow, fast) | 5-7x width | 3-7x width long | Broken water surface, visible stones |
| Pools (deep, slow) | 5-7x width | 2-5x width long | Smooth dark water, deeper |
| Glides (moderate) | Between riffle and pool | Variable | Smooth surface, moderate depth |
| Undercut banks | Every meander bend | 0.3-1m overhang | Dark shadow, overhanging roots/grass |

### Implementation Parameters

```python
STREAM_PARAMS = {
    "width_range": (0.5, 5.0),           # meters
    "depth_ratio": (0.1, 0.3),            # depth/width ratio
    "sinuosity": (1.3, 2.5),              # channel/valley length ratio
    "meander_wavelength_ratio": 11.0,      # wavelength = ratio * width
    "meander_amplitude_ratio": 4.0,        # amplitude = ratio * width
    "riffle_pool_spacing_ratio": 6.0,      # spacing = ratio * width
    "riffle_depth_ratio": 0.3,             # riffle depth / normal depth
    "confluence_angle_deg": (30, 60),
    "confluence_width_increase": 1.3,      # multiply width after junction
    "ford": {
        "depth": (0.05, 0.20),            # meters
        "width_multiplier": 1.5,           # wider than normal
        "stepping_stone_spacing": (0.5, 1.0),
        "stepping_stone_size": (0.3, 0.8),
    },
}
```

---

## Summary: Priority Implementation Order

Based on what the VeilBreakers toolkit is MISSING and what would have the highest visual impact:

### Must-Build (no existing generator)

1. **River banks** -- needed for every river/stream. The current system carves channels without bank geometry, material transitions, or vegetation zones.
2. **Streams and tributaries** -- small water features that fill the world. Need meandering spline paths with riffle-pool sequences.
3. **Ponds** -- small atmospheric water bodies for forest/swamp scenes. Simple geometry, high visual impact.
4. **Boulder formations** -- currently no boulder scatter with proper burial, moss gradients, and size distribution.
5. **Forest clearings** -- needed for encounter areas, camps, quest locations. Edge vegetation is the key visual element.
6. **Mountain passes** -- needed for travel between regions. Vegetation altitude banding is the key feature.

### Must-Fix (existing generator, wrong geometry)

1. **Cliff faces** (`generate_cliff_face`) -- needs strata layers, differential erosion channels, and proper talus cone with angle of repose. Currently uses a single overhang parameter.
2. **Waterfalls** (`generate_waterfall`) -- needs proper plunge pool depth proportional to fall height, spray zone material transitions, and cave-behind geometry. Currently creates flat-bottom pools.

### Key Principle for All Features

**No hard edges.** Every terrain feature in nature has a TRANSITION ZONE. The current generators create features that end abruptly. Every feature needs:
- Material blending across boundaries (not sharp texture switches)
- Gradual slope transitions (not vertical-to-flat discontinuities)
- Vegetation density gradients (not present/absent binary)
- Weathering/erosion softening of all edges

---

## Sources

- [Meander geometry and fluvial processes -- Wikipedia](https://en.wikipedia.org/wiki/Meander)
- [Cut bank geomorphology -- Wikipedia](https://en.wikipedia.org/wiki/Cut_bank)
- [Slip-off slope -- Wikipedia](https://en.wikipedia.org/wiki/Slip-off_slope)
- [Haw River bank erosion study -- PLOS One](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0110170)
- [Angle of repose -- Wikipedia](https://en.wikipedia.org/wiki/Angle_of_repose)
- [Scree formation -- Wikipedia](https://en.wikipedia.org/wiki/Scree)
- [Talus landform -- Britannica](https://www.britannica.com/science/talus-landform)
- [Cliff geology and formation -- Biology Insights](https://biologyinsights.com/what-is-a-cliff-the-geology-and-formation-explained/)
- [Rock strata and cliff profiles -- A-Level Geography](https://geographyrevisionalevel.weebly.com/2b3b-rock-strata-and-complex-cliff-profiles.html)
- [Tree line -- Wikipedia](https://en.wikipedia.org/wiki/Tree_line)
- [Mountain pass -- Wikipedia](https://en.wikipedia.org/wiki/Mountain_pass)
- [Sinuosity -- Wikipedia](https://en.wikipedia.org/wiki/Sinuosity)
- [Rosgen stream classification -- US EPA](https://cfpub.epa.gov/watertrain/moduleFrame.cfm?parent_object_id=1265)
- [Global river width/meander relationships -- Frasson 2019, Geophysical Research Letters](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019GL082027)
- [Waterfall types -- Geography Worlds](https://geographyworlds.com/blog/types-of-waterfalls/)
- [Plunge pool -- Wikipedia](https://en.wikipedia.org/wiki/Plunge_pool)
- [Littoral zone -- Wikipedia](https://en.wikipedia.org/wiki/Littoral_zone)
- [Pond and lake zone identification -- Kasco Marine](https://kascomarine.com/blog/pond-lake-zone-identification/)
- [Riparian zone -- Wikipedia](https://en.wikipedia.org/wiki/Riparian_zone)
- [Glacial erratic -- Wikipedia](https://en.wikipedia.org/wiki/Glacial_erratic)
- [Edge effects in forest -- Wikipedia](https://en.wikipedia.org/wiki/Edge_effects)
- [Procedural river drainage basins -- Red Blob Games](https://www.redblobgames.com/x/1723-procedural-river-growing/)
- [Coastline paradox and fractal dimension -- Wikipedia](https://en.wikipedia.org/wiki/Coastline_paradox)
- [Stratum geology -- Wikipedia](https://en.wikipedia.org/wiki/Stratum)
