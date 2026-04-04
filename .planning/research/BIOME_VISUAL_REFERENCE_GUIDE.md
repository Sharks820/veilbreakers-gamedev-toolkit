# Biome Visual Reference Guide

**Project:** VeilBreakers GameDev Toolkit
**Researched:** 2026-04-03
**Purpose:** Real-world visual knowledge base for procedural terrain generation
**Confidence:** HIGH (cross-referenced geology sources, NPS geomorphology, landscape ecology, game dev art direction)

---

## Table of Contents

1. [Dense Forest (thornwood_forest)](#1-dense-forest-thornwood_forest)
2. [Mountain Pass](#2-mountain-pass)
3. [Swamp/Marshland (corrupted_swamp)](#3-swampmarshland-corrupted_swamp)
4. [River Valley](#4-river-valley)
5. [Cliff/Canyon](#5-cliffcanyon)
6. [Rolling Plains/Grassland](#6-rolling-plainsgrassland)
7. [Lake/Pond](#7-lakepond)
8. [Rocky Highland](#8-rocky-highland)
9. [Cemetery/Graveyard](#9-cemeterygraveyard)
10. [Ruined Settlement](#10-ruined-settlement)
11. [Volcanic/Ashen](#11-volcanicashen)
12. [Frozen/Tundra](#12-frozentundra)
13. [Castle Approach](#13-castle-approach)
14. [Cross-Biome Terrain Rules](#14-cross-biome-terrain-rules)
15. [Dark Fantasy Color Rules](#15-dark-fantasy-color-rules)

---

## 1. Dense Forest (thornwood_forest)

### Visual Characteristics

**Canopy:** Dense, interlocking tree crowns block 70-90% of direct sunlight. Only dappled light shafts (god rays) penetrate. The canopy creates a permanent twilight at ground level. Upper canopy is 15-25m above ground in temperate forests.

**Color palette (real-world):** Deep greens (canopy), grey-greens and yellow-greens (moss), rich browns and near-blacks (soil, bark), muted ochre (dead leaves). For VeilBreakers dark fantasy: desaturate to 30-40% saturation max, shift value range to 10-50% (the existing TERRAIN_MATERIALS values are correct).

**Light quality:** Warm amber-green filtered light where sun penetrates. Deep blue-green shadows. High contrast between light shafts and shadow. Light direction is nearly horizontal in the understory since only angled light makes it through gaps.

### Terrain Mesh Features

**Ground contour:** Gently undulating with subtle mounds (tree root systems create 0.3-0.8m humps). No flat ground -- everything has micro-variation. Concavities between root mounds collect leaf litter and moisture.

**Slopes:** 0-15 degrees typical for forest floor. Steeper sections (15-35 degrees) around ravines and stream cuts. Ancient forests on hillsides have terraced root systems that create natural steps.

**Key mesh features to generate:**
- Root buttresses: Radial ridges 0.3-1.5m high extending 1-3m from tree bases
- Hollow depressions: 0.5-2m diameter, 0.1-0.3m deep between tree roots
- Fallen trunk channels: Linear depressions where logs have rotted into the ground
- Stream cuts: V-shaped 0.5-2m deep channels with exposed rock at bottom

### Texture/Material Rules

| Surface | Slope | Height | Moisture | Material |
|---------|-------|--------|----------|----------|
| Forest floor | 0-10 deg | Any | Normal | Leaf litter + soil blend |
| Gentle slopes | 10-25 deg | Any | Normal | Exposed roots + moss |
| Steep slopes | 25-45 deg | Any | Any | Mossy rock |
| Rock outcrops | >45 deg | Any | Any | Grey stone with vine/moss patches |
| Near water | Any | Low | High | Mud + fern patches |
| Root zones | 0-5 deg | Near tree | Any | Root bark texture (radial pattern) |

**Blend rules:**
- Leaf litter depth increases in concavities (accumulation)
- Moss coverage increases on north-facing surfaces (in northern hemisphere) and near water
- Bare soil shows through on high-traffic areas (paths, animal trails)
- Rock only shows on slopes >25 degrees or where erosion has stripped soil

### Vegetation Patterns

**Canopy layer (15-25m):** Oak, beech, hornbeam equivalent large trees. Spacing 4-8m. Irregular, NOT grid-planted. Older/larger trees at center of groves, younger at edges.

**Understory (3-8m):** Holly, hazel, young trees. Density 30-50% of canopy. Found in gaps and edges.

**Shrub layer (0.5-3m):** Ferns, brambles, holly. Dense where light reaches ground (gaps, edges, near paths). Sparse under dense canopy.

**Ground layer (0-0.5m):** Moss (continuous carpet on undisturbed ground), leaf litter (3-15cm deep), fungi on fallen logs, wood sorrel, wild garlic in spring patches.

**Dead wood:** Critical visual element. 10-20% of visible wood should be dead -- standing dead trees (snags), fallen trunks, broken branches. This reads as "natural" vs "planted."

### Water Features

Forest streams are narrow (0.5-3m), shallow (5-30cm), with rocky beds. Banks are stabilized by roots. Small pools form behind log jams. Water is clear to tea-colored (tannins from leaf litter).

### Environmental Props

| Prop | Density | Placement Rule |
|------|---------|---------------|
| Mossy boulders | Medium | On slopes, near streams, partially buried |
| Fallen logs | Low-medium | Random orientation, varying decay states |
| Mushroom clusters | Low | On fallen logs, tree bases, north side of stumps |
| Fern patches | Medium-high | Near water, in light gaps, on banks |
| Standing dead trees | Low | Random, 10-15% of tree population |
| Bracket fungi | Low | On dead/dying tree trunks, 0.5-3m height |
| Spider webs | Very low | Between branches, across gaps, visible in light shafts |

### Atmosphere

- **Fog:** Ground-hugging mist, 0-2m high, density 20-40%. Thicker near water and in hollows.
- **Light:** Warm amber god rays. Blue-green ambient. High dynamic range.
- **Particles:** Dust motes in light shafts. Occasional falling leaves. Fireflies at dusk (tiny warm specks).
- **Sound cues (visual implications):** Wind sway in canopy -- trees should have subtle lean/movement.

### Dark Fantasy Twist

**Thornwood Forest specifics:**
- Trees are twisted/gnarled, not straight. Trunks spiral. Branches reach downward like grasping claws.
- Bark textures include thorn-like protrusions (0.5-3cm scale bumps on bark normal maps)
- Some moss has a sickly yellow-green tint instead of healthy green (desaturate and yellow-shift)
- Scattered patches of dead/black vegetation indicate corruption creeping in
- Spider webs are thicker, more visible, and more abundant
- Occasional bioluminescent fungi provide eerie blue-green point lights
- Root systems break through the surface more aggressively, creating trip hazards and cage-like structures
- Fog has a slight greenish tint (not pure white)

**Material adjustments from real-world:**
- Reduce base_color value by 20-30% across all materials (darker overall)
- Add subtle purple/magenta tint to shadows (corruption color)
- Increase normal_strength by 20% (more aggressive surface detail reads as "hostile terrain")
- Roughness stays high (0.8-0.95) -- wet but not glossy, decaying

---

## 2. Mountain Pass

### Visual Characteristics

**Scale:** Mountain passes are typically 50-200m wide at the narrowest point. The trail through a pass is 1-3m wide (single track) to 4-6m wide (cart track). Walls rise 50-500m on either side.

**Color palette:** Grey, blue-grey, and brown rock. Sparse olive-green vegetation in cracks. White/grey snow patches at higher elevation. Warm ochre on sun-facing exposed rock (iron oxidation).

**Light quality:** Harsh, direct sunlight on exposed faces. Deep blue shadows in ravines. Very high contrast. Wind-driven clouds create moving shadow patterns.

### Terrain Mesh Features

**Pass profile:** Cross-section is a U-shape (glacial) or V-shape (water-carved). Floor slopes 5-15 degrees along the direction of travel. Walls are 30-70 degrees.

**Switchback trail geometry:**
- Trail width: 1.5-3m
- Switchback turn radius: 3-5m
- Grade: 8-15% (5-9 degrees) per segment
- Each switchback segment: 20-50m long before reversing direction
- Retaining walls on outer edge: 0.5-1.5m high, dry-stacked stone
- Cut into hillside on inner edge: 0.5-2m vertical cut

**Rockfall/scree formation:**
- Scree collects at base of cliffs in fan-shaped deposits (alluvial fans)
- Scree angle of repose: 30-38 degrees (use 34 degrees as default)
- Scree particle size grades from large at base to small at top (inverse grading)
- Scree fans originate from weakness points in cliff face (fractures, water channels)
- Fan apex is at the cliff base, fan spreads downslope

**Key mesh features:**
- Exposed bedrock ledges (horizontal bands, 0.3-2m step height)
- Wind-carved hollows (tafoni): 0.1-0.5m deep concavities in rock faces
- Frost-shattered rock pinnacles at ridgeline
- Boulder fields on gentler slopes (individual rocks 0.5-3m)

### Texture/Material Rules

| Surface | Slope | Height | Material |
|---------|-------|--------|----------|
| Trail surface | <15 deg | Any | Packed gravel/dirt |
| Gentle slopes | 0-20 deg | Low | Sparse grass + gravel |
| Moderate slopes | 20-35 deg | Any | Exposed rock + lichen |
| Scree slopes | 30-38 deg | Below cliffs | Loose gravel/talus |
| Cliff faces | >45 deg | Any | Layered sedimentary rock |
| Ridgeline | Any | Highest | Wind-polished rock, no soil |
| Snow line | Any | >70% height | Snow patches in shadows, bare rock in sun |
| Water channels | <15 deg | Low | Wet rock, darker than surrounding |

**Layered strata on cliffs:**
- Horizontal bands of alternating color: light grey limestone, dark grey shale, tan sandstone
- Band thickness: 0.3-3m each
- Slight angle variation (geological tilt): 0-15 degrees off horizontal
- Harder bands protrude 5-15cm beyond softer eroded bands
- Creates the characteristic "stepped" cliff profile

### Vegetation Patterns

- **On trail:** Nothing (compacted ground)
- **Trail edges:** Hardy alpine grasses, low cushion plants (0-15cm)
- **Sheltered cracks:** Small ferns, mosses, wildflowers in protected spots
- **Above treeline:** No trees. Only lichen on rock, moss in wet spots
- **Below treeline (lower pass):** Scattered, wind-bent conifers (flagged trees lean away from prevailing wind)
- **Vegetation decreases sharply with altitude** -- use height as primary vegetation density driver

### Water Features

Mountain streams are fast, narrow (0.5-2m), shallow (5-20cm), with exposed rock beds. Waterfalls occur where hard rock bands cross the stream course. Pools form at waterfall bases. Ice edges in shadow zones.

### Environmental Props

| Prop | Placement Rule |
|------|---------------|
| Large boulders | At base of cliffs, on scree fans, along trail edges |
| Cairns (stacked rocks) | Trail markers at switchback turns, pass summit |
| Snow patches | North-facing sheltered areas, increasing with altitude |
| Lichen-covered rocks | All exposed rock at moderate altitude, more on north faces |
| Wind-bent dead trees | Near treeline, leaning away from prevailing wind |
| Ice formations | Shadow zones, near water, north-facing cliff bases |

### Atmosphere

- **Fog:** Cloud banks that roll through the pass. Visibility can drop to 10-20m.
- **Light:** Harsh blue-white direct light. Deep blue shadows. Strong ambient occlusion.
- **Particles:** Wind-driven snow/ice particles at high elevation. Dust on exposed rock.
- **Wind:** Visual indicators -- dust trails, snow plumes off ridges, leaning vegetation.

### Dark Fantasy Twist

- Exposed rock has unnatural black veins running through it (corruption in the stone itself)
- Occasional skull/bone fragments embedded in scree (ancient battlefield or creature graveyard)
- Wind sounds carry distant screams (visual: add subtle heat-haze-like distortion in air)
- Abandoned/destroyed cairns suggest something actively un-marks the path
- Strange carved runes on cliff faces, partially weathered
- Snow patches have a faint grey-blue tint rather than pure white (tainted precipitation)
- Some scree has an unnatural angular quality, as if something shattered the rock deliberately

---

## 3. Swamp/Marshland (corrupted_swamp)

### Visual Characteristics

**Ground:** Permanently waterlogged. The "ground" is really mud with a thin water film. True ground surface is 10-50cm below water level. Islands of slightly higher ground (hummocks) break the surface.

**Color palette:** Near-black water, dark brown mud, grey-green dead vegetation, sickly yellow-green living moss, olive-brown reeds. Very low value range (darkest biome). The existing TERRAIN_MATERIALS black_mud (0.04, 0.03, 0.03) and toxic_pool (0.06, 0.07, 0.04) colors are accurate.

**Light quality:** Flat, diffused. No shadows because fog diffuses everything. Occasional sickly green or amber light through fog. Very low overall illumination.

### Terrain Mesh Features

**Ground contour:** Nearly flat overall (0-5 degree slopes). Micro-variation of +/-0.3m creates the hummock/pool pattern. Height variation at 2-5m wavelength.

**Water coverage:** 30-60% of surface is open water. Water is static (no flow). Depth 5-50cm in pools, occasionally 1-2m in channels.

**Key mesh features:**
- Hummocks: Raised mounds 0.3-1m above water, 1-3m diameter, irregular shape
- Channels: Linear depressions connecting pools, 0.5-2m wide
- Root platforms: Dead tree roots creating elevated platforms 0.5-1m above water
- Mud banks: Gentle slopes (5-15 degrees) between water and hummock surfaces
- Submerged logs: Just below water surface, creating dark shapes under murky water

### Texture/Material Rules

| Surface | Condition | Material |
|---------|-----------|----------|
| Hummock tops | Dry-ish | Dark peat/moss blend |
| Hummock sides | Wet | Black mud transitioning to water |
| Open water | Standing | Murky green-black, opaque, low roughness (0.10-0.15) |
| Deep pools | Stagnant | Even darker, near-black, slight green film |
| Channel edges | Saturated | Slick dark mud, very low roughness (0.35-0.45) |
| Tree bases | Waterlogged | Black rot texture, very dark |
| Dead wood | Exposed | Silver-grey weathered wood |

**Critical: Water surface material**
- Roughness 0.10-0.15 (near-mirror but disturbed by floating debris)
- Opacity: Fully opaque (no bottom visible in murky swamp)
- Slight green-brown tint
- Floating debris (leaves, sticks, algae film) breaks up reflections

### Vegetation Patterns

**Trees:** Predominantly dead or dying. 60-80% of trees are dead (no leaves, grey bark, broken crowns). Living trees are stunted, twisted. Spanish-moss-equivalent hangs from branches (grey-green drapes, 0.5-3m long). Cypress-knee-like root protrusions rise from water.

**Ground cover:**
- Sphagnum moss on hummocks (yellow-green, spongy)
- Reeds in shallow water edges (1-2m tall, dense stands)
- Cattails along channel edges
- Duckweed/algae film on still water surfaces (bright green dots on dark water)
- NO grass -- too waterlogged

**Density gradient:** Vegetation is densest at water edges and on hummocks. Open water has floating plants only.

### Water Features

All water is stagnant or barely flowing. Surface has a film (organic matter). Bubbles occasionally rise (decomposition gases). Water color is green-black to brown-black. No clarity -- cannot see bottom.

### Environmental Props

| Prop | Density | Placement |
|------|---------|-----------|
| Dead trees (standing) | High | Everywhere, 60-80% of tree population |
| Dead trees (fallen, in water) | Medium | Spanning between hummocks, half-submerged |
| Hanging moss/drapes | High | On every tree, living or dead |
| Reed clusters | High | Around every water edge |
| Mushroom clusters | Medium | On dead wood, hummock edges |
| Bubbling pools | Low | Random in stagnant water areas |
| Fog wisps | Continuous | Ground level, varying density |
| Spore pods/fungal growths | Medium | On dead wood, bases of trees |

### Atmosphere

- **Fog:** Dense ground fog, 0-3m. Visibility 10-30m. Thickest over water.
- **Light:** Sickly amber-green diffused. No clear shadows. Perpetual overcast feel.
- **Particles:** Floating spores (small glowing particles). Insects (dark specks). Rising bubbles from water.
- **Overall feel:** Claustrophobic despite being outdoors. Can't see far.

### Dark Fantasy Twist (corrupted_swamp)

- Water occasionally has an unnatural purple or green glow (bioluminescent corruption)
- Dead trees have bark that looks like it's melting or dripping
- Some hummocks are suspiciously regular in shape (something buried underneath)
- Toxic pools emit visible fumes (translucent green particle effect above surface)
- Vine clusters move subtly even without wind (animate them very slowly)
- Skeletal remains visible in shallow water edges
- Some moss/growth patterns form almost-but-not-quite recognizable shapes (faces, hands)
- The deeper you go, the more the corruption shows -- gradient from "natural swamp" at edges to "corrupted nightmare" at center

---

## 4. River Valley

### Visual Characteristics

**Valley profile:** Wide floodplain (50-500m wide) with gentle slopes leading to bluffs or hills. The river itself is 5-30m wide for a medium river. Valley walls slope 10-30 degrees.

**Color palette:** Rich greens (riverside vegetation), warm browns (exposed banks), blue-grey (water), sandy tan (gravel bars), yellow-green (willows). Dark earth tones on bluffs.

### Terrain Mesh Features

**River channel geometry (the MOST important part):**

The cross-section of a meander is ASYMMETRIC:
- **Outer bank (cut bank):** Steep (50-90 degree), 1-5m high vertical or near-vertical face of exposed soil/clay. Actively eroding. Tree roots hang exposed over edge. This is the deeper side.
- **Inner bank (point bar):** Gentle slope (5-15 degrees), gravel/sand/mud. Shallow water. Material grades from coarse gravel at water's edge to fine sand/silt higher up. Vegetation colonizes higher parts.

**River plan shape:**
- Rivers meander in S-curves. Wavelength of meander = 10-14x channel width.
- Meander amplitude = 2-4x channel width.
- River is deeper at outside of curves, shallower at inside.
- Point bars form on inside of each curve.

**Floodplain features:**
- Natural levees: Low ridges (0.5-2m high) parallel to river, formed by flood deposits
- Oxbow lakes: Abandoned meander loops (crescent-shaped ponds)
- Backswamp: Low-lying area behind natural levees (wetter, muddier)
- Terraces: Old floodplain levels, step-like features 2-10m above current floodplain

### Texture/Material Rules -- Bank Transition (Critical)

The transition from dry land to water follows a precise sequence. This is the VISUAL SIGNATURE of a natural river bank:

**Inner bank (point bar) transition -- Gradual:**
```
DRY ← → WET

Grass/meadow (>2m from water)
  → Sedges/rushes (1-2m from water)
    → Mud with plant roots (0.5-1m from water)
      → Wet mud/silt (0-0.5m from water)
        → Pebbles/gravel (at water line)
          → Submerged gravel/sand (in water)
```

**Outer bank (cut bank) transition -- Abrupt:**
```
Grass/meadow (top of bank)
  → Sharp edge (erosion scarp)
    → Vertical exposed soil/clay face (1-5m)
      → Undercut at base (erosion notch)
        → Deep water directly at base
```

| Zone | Width | Slope | Material |
|------|-------|-------|----------|
| Meadow | 5-20m | 0-5 deg | Grass + wildflowers |
| Riparian strip | 2-5m | 0-10 deg | Dense reeds, sedges |
| Mud margin | 0.5-2m | 5-15 deg | Wet mud, some gravel |
| Water edge | 0.2-0.5m | 5-10 deg | Wet pebbles/gravel |
| Shallow water | 1-3m | 5-10 deg | Submerged gravel/sand (visible through water) |
| Deep channel | 3-10m | Varies | Not visible (water too deep) |

### River Confluence (where tributary meets main river)

**Visual rules:**
- Tributary enters at 30-90 degree angle (NOT parallel)
- A visible color/turbidity difference between the two flows persists for 50-200m downstream
- The junction creates a deep scour pool at the meeting point
- A gravel/sand bar forms on the downstream side of the junction (deposition)
- The shear line (visible boundary between the two water colors) curves downstream
- The combined river is wider immediately downstream of the confluence

**Mesh implications:**
- Tributary channel carved into valley wall
- Fan-shaped gravel deposit at mouth
- Deepened pool at junction (lower terrain under water)
- Widened channel downstream

### Vegetation Patterns

- **Floodplain meadow:** Grass + wildflowers + scattered bushes. Dense, lush.
- **Riparian zone (stream banks):** Willows, alders (overhanging water), dense reeds/rushes
- **Natural levees:** Larger trees (oaks, elms) on slightly elevated ground
- **Point bars:** Pioneer plants colonizing new gravel -- willows, grasses
- **Bluff/valley walls:** Forest (connects to adjacent biome)

**Key rule:** Vegetation is LUSHEST near water and thins with distance. The river corridor is a green ribbon through any landscape.

### Water Features

- River is flowing (animated). Speed 0.5-2 m/s visually.
- Riffles (shallow, fast, over gravel) alternate with pools (deep, slow).
- Riffle spacing approximately 5-7x channel width.
- Eddies form behind large rocks and at bank irregularities.
- Small rapids where bedrock crosses channel.

### Atmosphere

- **Fog:** Morning mist in valley (cold air drainage). Burns off by midday.
- **Light:** Valley sides shade the river in morning/evening. Bright reflections off water at angles.
- **Particles:** Insects over water (warm months). Spray near rapids.

### Dark Fantasy Twist

- River water has an unnatural dark tint (tea-colored to near-black in corrupted areas)
- Banks have exposed bones/remains embedded in eroded cut banks (ancient burial ground exposed)
- Some willow trees have branches that trail INTO the water like reaching arms
- Fog on the river is thicker than natural and doesn't burn off (supernatural cold)
- Occasional dark shapes moving under water surface (shadow fish or something worse)
- Bridge ruins at strategic crossing points (collapsed arches, broken piers)
- Gravel bars have scattered rusted weapons/armor (old battlefield)

---

## 5. Cliff/Canyon

### Visual Characteristics

**Scale:** Cliff faces from 5m (small bluff) to 200m+ (major canyon). Canyon width: 10-500m. The visual impact depends on the viewer's position relative to the cliff.

**Color palette:** Bands of different rock colors. Common sequences:
- Grey limestone (light, 0.4-0.5 value)
- Red/brown sandstone (warm, 0.2-0.3 value)
- Dark grey shale (very dark, 0.1-0.15 value)
- Tan/buff sandstone (warm, 0.3-0.4 value)
- Near-white chalk or quartz bands (0.5-0.6 value, rare)

### Terrain Mesh Features -- How Cliffs MESH with Terrain

**The cliff-to-terrain transition has THREE zones:**

```
ABOVE THE CLIFF (top)
  Flat or gently sloping terrain (0-10 deg)
    → Edge zone: slight rounding (0.5-2m)
      → CLIFF FACE begins

CLIFF FACE (vertical zone)
  Near-vertical (60-90 deg)
    → May have ledges (horizontal bands, 0.5-3m deep)
    → May have overhangs (negative slope at hard/soft rock boundary)
    → Erosion channels (vertical grooves, 0.1-1m deep)
    → Vegetation in cracks (horizontal joints)

BELOW THE CLIFF (base)
  SCREE/TALUS SLOPE (30-38 deg, angle of repose)
    → Scree fan: 2-20m wide depending on cliff height
    → Large blocks at bottom, smaller fragments at top
    → Fan shape: apex at cliff base, widening downslope
      → TRANSITION to normal terrain (15-30m from cliff base)
        → Flat or gently sloping terrain (0-15 deg)
```

**Critical dimensions for mesh generation:**
- Cliff edge rounding: 0.5-2m radius (NOT a sharp edge -- erosion rounds it)
- Scree fan width: approximately 0.5x cliff height
- Scree angle: 34 degrees (universal for loose rock)
- Transition from scree to flat: 5-15m gradual slope reduction

### Layered Stone Strata (How to Model)

Real cliff faces show **horizontal bands of different rock types**. Each band has:

```
Hard band (sandstone/limestone):
  - Protrudes 5-20cm beyond softer layers
  - Relatively smooth face
  - Horizontal or near-horizontal cracks (bedding planes)
  - Color: lighter (tan, grey, buff)

Soft band (shale/mudstone):
  - Recessed 5-20cm behind harder layers
  - Rough, crumbly face
  - More erosion channels
  - Color: darker (grey, dark brown, near-black)
  - Often has vegetation growing from the recess
```

**For procedural generation:**
- Each stratum band: 0.3-5m thick
- Alternate hard/soft layers
- Add 0-15 degree tilt to all bands (geological dip)
- Hard bands: protrude slightly, smoother normal maps
- Soft bands: recessed, rougher normals, more vertex displacement

### Erosion Patterns on Cliff Faces

**Water channels:** Vertical grooves carved by water runoff. 0.1-1m wide, 0.05-0.5m deep. Follow gravity -- straight down with slight wandering. More channels per unit width = more erosion. Channels widen toward base.

**Wind-carved hollows (tafoni):** Honeycomb-like patterns on sandstone. Cells 0.05-0.3m diameter. Found 1-5m above ground level on sheltered faces. Circular to oval openings.

**Overhangs:** Form where a soft layer erodes faster than the hard layer above it. Creates a shelf 0.5-3m deep. Hard layer eventually collapses in blocks (these blocks are the large scree at cliff base).

**Fracture patterns:** Vertical joints (cracks) perpendicular to bedding planes. Spacing 1-5m. These are where the cliff eventually breaks into columns/pillars.

### Texture/Material Rules

| Surface | Material | Key Properties |
|---------|----------|----------------|
| Hard rock bands | Sandstone/limestone | Roughness 0.7-0.85, warm tones |
| Soft rock bands | Shale/mudstone | Roughness 0.85-0.95, dark, crumbly normals |
| Erosion channels | Wet/stained rock | Darker streak down face, roughness 0.6-0.7 |
| Ledge tops | Lichen + dust | Green-grey patches on horizontal surfaces |
| Scree (large) | Same as cliff rock | Angular blocks, strong normals |
| Scree (small) | Gravel mix | Mixed colors from all layers above |
| Cliff base | Wet/stained | Water seepage darkens base zone |

### Dark Fantasy Twist

- Some strata bands glow faintly (trapped energy/corruption in specific geological layers)
- Carvings/relief sculptures partially visible on cliff face (ancient civilization carved into the rock)
- Unnatural fracture patterns suggesting something PUSHED through from inside the rock
- Chains or iron anchors driven into cliff face (something was imprisoned here)
- Nesting sites for dark creatures (guano stains, bone litter on ledges)
- The deepest erosion channels weep a dark fluid instead of water

---

## 6. Rolling Plains/Grassland

### Visual Characteristics

**Terrain:** Gently undulating. Hill wavelength 100-500m. Hill amplitude 5-30m. NO flat ground -- always subtle rolls and waves. The horizon is distant (1-5km visible).

**Color palette:** Yellow-green to gold grass (season dependent). Warm earth tones where soil shows. Blue-grey distant hills (atmospheric perspective). Wildflower accent colors: purple, yellow, white in patches.

**Light quality:** Open sky means direct, bright lighting. Long shadows at dawn/dusk stretch across hills. Moving cloud shadows are a defining visual feature -- patches of light and shadow slide across the rolling terrain.

### Terrain Mesh Features

**Surface:** Smooth, broad curves. Very low-frequency terrain noise. The dominant visual is the silhouette of hills against sky.

**Subtle features:**
- Animal trails: Faint linear depressions, 0.3-0.5m wide, following contour lines
- Dry creek beds: Shallow depressions 1-3m wide, 0.3-1m deep, with gravel bottom
- Lone tree mounds: Slight elevation (0.2-0.5m) around tree base from root action
- Erosion rills: On steeper slopes (>15 deg), parallel shallow grooves 0.1-0.3m deep

### Texture/Material Rules

| Surface | Condition | Material |
|---------|-----------|----------|
| Hilltops | Exposed | Short grass + rock showing through (wind exposure) |
| Slopes | Sheltered | Tall grass, densest vegetation |
| Valleys/swales | Moist | Lush green grass, occasional standing water |
| Paths/trails | Compacted | Bare earth, compressed grass |
| Rocky outcrops | Exposed | Lichen-covered stone (rare, attention-grabbing features) |

**Grass is NOT uniform:** Patches of different grass species create a quilt-like pattern. Taller grass (0.5-1m) in sheltered areas, shorter (0.1-0.3m) on exposed hilltops.

### Vegetation Patterns

- **Dominant:** Grass. 90%+ ground cover.
- **Wildflower patches:** 2-10m diameter clusters. Follow moisture and shelter.
- **Lone trees:** Large, spreading crown. One tree per 100-300m. Often on hilltops (landmark). Shape: round, wind-sculpted on prevailing wind side.
- **Hedgerows/tree lines:** Following old boundaries or watercourses. Linear groupings.
- **Thickets:** Dense bush clusters 5-20m diameter in sheltered spots.

### Water Features

- Shallow, slow streams in valley bottoms (1-3m wide)
- Seasonal ponds in depressions after rain
- Spring seeps on hillsides (small wet patches)

### Atmosphere

- **Fog:** Ground mist in valleys at dawn. Clears quickly.
- **Light:** Big sky. Dramatic cloud shadows. Golden hour is spectacular.
- **Particles:** Seeds/pollen floating in air. Insects.
- **Wind:** Visible in grass movement (waves rolling across grassland).

### Dark Fantasy Twist

- Grass is paler/more yellow than healthy (drought/corruption)
- Lone trees are dead or dying (blackened, leafless)
- Some wildflower patches are unnaturally colored (blood red, void purple)
- Distant figures visible on hilltops that disappear when approached (add static silhouettes at LOD distance)
- Animal bones scattered in grass (not just skulls -- ribcages, limbs)
- Circular patches of dead/burned grass (ritual sites)
- The open sky feels oppressive rather than freeing (dark clouds, greenish-grey overcast)

---

## 7. Lake/Pond

### Visual Characteristics

**Shape:** Irregular, organic outline. NO perfectly circular/elliptical shapes. Bays, peninsulas, and inlets create complex shoreline. Ratio of shoreline length to area is high.

**Water surface:** Still water = near-perfect reflection of sky and surroundings. Wind creates small ripples that break reflections into impressionist patterns. Color depends on depth: shallow edges = greenish (vegetation visible), deep center = dark blue-grey to black (sky reflection).

### Terrain Mesh Features

**Shoreline profile:**
```
DRY LAND (above water)
  Meadow/forest (>5m from shore)
    → Marshy zone (2-5m from shore): slightly lower, wetter
      → Reed zone (0-2m from shore): water-saturated ground
        → Mud/sand margin (0-0.5m): at water line
          → Shallow shelf (0-1m depth): gentle slope for 3-10m
            → Drop-off to deeper water

```

**Key: The shoreline is NOT a sharp edge.** There is always a transition zone 2-10m wide.

**Shore types around a single lake (they vary!):**
- **Sandy beach section:** Gentle slope, 0-5 degrees, clear water, gravel bottom
- **Rocky shore:** Boulders at water edge, deeper water immediately adjacent
- **Marshy inlet:** Very gradual, reeds extend into water, mud bottom
- **Bluff/cliff section:** Steep bank (30-70 deg), deep water at base, erosion undercut

### Texture/Material Rules

| Zone | Distance from Water | Material |
|------|-------------------|----------|
| Dry land | >5m | Biome-specific ground |
| Marshy transition | 2-5m | Wet earth/grass blend |
| Reed zone | 0-2m | Mud + reed roots |
| Water edge | 0-0.5m | Wet mud/sand/pebbles |
| Shallow water | In water, 0-1m deep | Visible bottom: sand/gravel/mud through water |
| Deep water | In water, >1m | Opaque dark reflection surface |

### Vegetation Patterns

- **Aquatic (in water):** Lily pads (0.1-0.3m diameter, floating), submerged weeds (visible in shallow areas), algae on rocks
- **Emergent (water edge):** Reeds/cattails (1-3m tall, dense stands), rushes
- **Riparian (shore):** Willows (overhanging water), alders, moisture-loving shrubs
- **Transition:** Vegetation is lushest within 10m of water, then matches surrounding biome

### Dark Fantasy Twist

- Water is unnaturally dark and opaque (nothing visible below surface)
- Lily pads are dark purple/black instead of green
- Occasional ripples from below surface with no visible cause
- Shore has scattered personal effects (shoes, jewelry) suggesting people walked into the water and didn't come back
- Reflections in the water don't quite match reality (subtle distortion, wrong colors)
- Dead fish occasionally float to surface
- Reeds are grey/black instead of green

---

## 8. Rocky Highland

### Visual Characteristics

**Terrain:** Exposed bedrock with thin or absent soil. The rock IS the terrain. Vegetation exists in cracks and pockets. Reminiscent of Scottish Highlands or Nordic fells.

**Color palette:** Grey to blue-grey rock, orange-brown lichen, dark green moss in wet spots, muted purple heather in lower areas, ochre-brown dead grass. The palette shifts with seasons but stays muted.

**Light quality:** Open, wind-scoured. Harsh light with constant cloud movement. Dramatic weather changes.

### Terrain Mesh Features

**Surface character:** Smooth, glacier-polished rock slabs alternating with fractured, blocky areas. Two textures at different scales:
- **Large scale (10-100m):** Rounded, whale-back shapes (roche moutonnee) from glacial action
- **Small scale (0.1-2m):** Angular, fractured blocks from frost weathering

**Key features:**
- **Erratic boulders:** Large (1-5m) isolated rocks deposited by glaciers, sitting on smooth bedrock. Visually distinctive because they don't match surrounding rock.
- **Peat bogs:** Water-filled depressions between rock outcrops, 2-10m diameter
- **Frost-shattered pinnacles:** 1-5m tall spires of fractured rock on exposed ridges
- **Blockfield (felsenmeer):** Areas of angular shattered boulders covering flat ground, 0.3-2m diameter blocks

### Texture/Material Rules

| Surface | Material | Key Properties |
|---------|----------|----------------|
| Smooth bedrock | Glacier-polished stone | Low roughness (0.5-0.7), light grey |
| Fractured rock | Frost-shattered stone | High roughness (0.85-0.95), angular normals |
| Lichen patches | Orange/grey lichen on rock | Distributed on exposed north faces |
| Moss in cracks | Deep green, spongy | Only in sheltered, moist cracks |
| Peat | Near-black organic soil | Very dark, in depressions |
| Sparse grass | Yellow-brown tufts | In soil pockets between rocks |

### Vegetation Patterns

- **Coverage:** 10-40% of surface (rest is bare rock)
- **Grass:** Grows only where soil has accumulated in cracks/depressions. Tufts, not lawns.
- **Heather:** Low (0.1-0.5m), woody shrubs. Forms patches on deeper soil. Purple flowers in late summer.
- **Lichen:** Covers 30-60% of exposed rock surfaces. Grey, yellow, or orange crusty growth.
- **Moss:** Only in sheltered wet spots. Bright green accent against grey rock.
- **Trees:** None on exposed highland. Occasional wind-bent stunted tree in sheltered hollow.

### Dark Fantasy Twist

- Standing stones (menhirs) in circular arrangements on exposed ridges
- Rock surfaces have natural-looking but unnatural patterns (spirals, lines that are almost runes)
- Peat bogs are bottomless (dark, opaque water, things don't float in them)
- Wind carries voices/whispers (visual: wind particle effects more aggressive/visible)
- Lichen growth forms patterns that suggest maps or writing when viewed from above
- Some boulders sit at physically impossible angles (slightly floating or balanced wrong)

---

## 9. Cemetery/Graveyard

### Visual Characteristics

**Layout:** Gravestones arranged in roughly parallel rows, but not perfectly aligned. Older sections are more irregular. Paths between rows are 1-2m wide. The overall ground plan is organic, following terrain contours.

**Color palette:** Grey stone (headstones), dark green (yews, ivy), silver-grey (weathered wood), black iron (fences), yellow-brown (dead leaves), white (lichen on old stone). Very desaturated palette.

**Light quality:** Perpetually overcast. Flat, diffused light. No strong shadows. Occasional shafts of light through clouds create dramatic spotlighting. Trees filter light creating dappled patterns.

### Terrain Mesh Features

**Ground:** Gently undulating. Slight mounding over each grave (0.1-0.3m humps, 0.8x2m footprint). Older graves have subsided (shallow depressions). Paths are worn 0.05-0.1m below surrounding ground.

**Key structures:**
- **Headstones:** 0.5-1.2m tall, 0.3-0.6m wide, 0.1-0.2m thick. Spacing 0.8-1.5m apart in rows
- **Chest tombs:** 0.5m high, 0.8x2m stone boxes
- **Mausoleums:** 2-4m tall, 2x3m footprint. Heavy stone construction with doors.
- **Iron fences:** 0.8-1.2m tall, wrought iron with finials. Surrounds plots or entire cemetery.
- **Lychgate:** Covered gate at entrance, timber construction, 2-3m wide.
- **Paths:** Gravel or flagstone, 1-2m wide, connecting key points.

### Texture/Material Rules

| Surface | Material |
|---------|----------|
| Paths | Worn gravel or moss-covered flagstone |
| Between graves | Overgrown grass, leaf litter |
| On grave mounds | Short grass or bare earth |
| Stone surfaces | Lichen-covered, weathered (high roughness, high normal) |
| Iron elements | Rust + peeling black paint (roughness 0.7-0.85) |
| Wood elements | Silver-grey weathered wood (roughness 0.9+) |

### Vegetation Patterns

- **Yew trees:** Dark, dense evergreens. 5-15m tall. THE signature cemetery tree.
- **Weeping willows:** Near water features or paths. Drooping branches.
- **Ivy:** Climbing over walls, headstones, and mausoleums. Dense coverage on north sides.
- **Moss:** On all old stone surfaces, especially north-facing.
- **Overgrown grass:** Long (0.3-0.5m) between neglected graves. Shorter on maintained paths.
- **Wild flowers:** Small white/purple flowers in grass (daisies, violets).

### Atmosphere

- **Fog:** Ground-hugging, 0-1m. Dense. Moves slowly. Thickest at dawn/dusk.
- **Light:** Cool, blue-grey ambient. No warm tones. Occasional dramatic shaft of light.
- **Particles:** Floating leaves (autumn). Light rain/drizzle. Crow feathers.

### Dark Fantasy Twist

- Some graves are open (disturbed earth, broken coffin fragments visible)
- Headstone inscriptions are partially legible -- names and dates suggest an entire family died on the same day
- Iron fences are bent outward (something broke OUT, not in)
- A few graves glow faintly at night (phosphorescent fungi or supernatural)
- Statuary angels have faces that are worn away to blankness or are deliberately defaced
- Dead ravens scattered near specific graves (something killed them)
- The newest-looking grave has today's date (or the player character's name)
- Tree roots have grown through and displaced coffins/bones

---

## 10. Ruined Settlement

### Visual Characteristics

**Layout:** Recognizable street grid/organic path network still visible. Walls standing to 0.5-3m height (rarely full height). Roof collapse is the FIRST thing that happens to abandoned buildings -- so most structures are roofless.

**Color palette:** Grey stone walls, brown timber (rotten), green vegetation overtaking everything, dark earth showing through collapsed floors. Rich contrast between grey stone and green plants.

**Visual age indicators:**
- 10-50 years abandoned: Roofs gone, walls standing, vegetation filling interior, paths overgrown but visible
- 50-200 years: Wall tops crumbling, trees growing inside buildings, paths only visible as shallow depressions
- 200+ years: Only foundations visible as lines of stone in grass, mounds where buildings were

### Terrain Mesh Features

**Building footprints:** Rectangular depressions or raised foundations, 4-8m wide, 6-12m long. Walls as terrain features: linear ridges 0.3-3m high, 0.5-0.8m wide.

**Streets:** Linear depressions 2-4m wide, slightly lower than surrounding ground. Cobblestone fragments showing through vegetation.

**Key features:**
- Collapsed wall piles: Irregular mounds of rubble 0.5-2m high
- Cellar holes: Rectangular depressions 2-4m deep (the most persistent feature)
- Well circles: 1-1.5m diameter stone rings, sometimes collapsed
- Hearth mounds: Slightly raised platforms of fire-blackened stone

### Texture/Material Rules

| Surface | Material |
|---------|----------|
| Former streets | Broken cobblestone + dirt + grass |
| Building interiors | Rubble + scattered floor tiles + vegetation |
| Standing walls | Weathered stone, mortar eroded, moss/ivy coverage |
| Collapsed areas | Rubble pile: mixed stone, timber, tile fragments |
| Open ground | Overgrown grass/weeds, taller than natural |
| Foundation walls | Stone + soil buildup against base |

### Vegetation Patterns

**Nature reclaims buildings in a specific order:**
1. Grass and weeds colonize open ground and rubble first
2. Shrubs establish in sheltered corners (against walls, in doorways)
3. Small trees grow inside buildings (protected microclimate)
4. Ivy/climbing plants cover walls
5. Large trees eventually push through and topple remaining walls
6. Finally, only the tree pattern (regularly spaced in a grid of old building plots) betrays the former settlement

**Key plants:** Nettles (love nitrogen-rich soil of human habitation), elder trees (first tree colonizers), buddleia/butterfly bush (grows on walls), ivy (covers everything).

### Dark Fantasy Twist

- Some buildings have clearly been destroyed by force, not just decay (scorch marks, impact damage)
- Personal items are scattered as if residents fled suddenly (overturned furniture, dropped tools)
- One building is suspiciously intact/maintained amid the ruins (someone or something lives there)
- Scratches/claw marks on interior walls suggest something was trapped
- Plant growth is accelerated/mutated near certain buildings (supernatural contamination)
- The well/cistern is filled with something dark and viscous instead of water
- At night, faint light from some windows (ghostly remnants)

---

## 11. Volcanic/Ashen

### Visual Characteristics

**Terrain:** Dramatically alien. Black basalt rock, grey ash fields, occasional orange-red glow from lava cracks. The landscape is monochromatic (black/grey) with extreme color accents (orange lava, bright green moss on old flows).

**Color palette:** Near-black basalt (0.04-0.08 value), dark grey ash (0.10-0.15), bright orange-red lava glow (1.0, 0.3, 0.0 emission), yellow sulfur deposits (rare accent), bright green moss on old cooled lava (stark contrast).

**Light quality:** Harsh and dramatic. Red-orange glow from below (lava). Grey overcast from volcanic haze. Very high contrast between lit and shadowed areas.

### Terrain Mesh Features

**Lava field types:**

**A'a lava (rough):** Sharp, jagged, angular rock surface. 0.1-0.5m scale jaggedness. Extremely high roughness in both material and mesh. Painful to walk on. Generates from steep noise with high frequency.

**Pahoehoe lava (smooth):** Ropy, smooth, flowing textures in the rock. Looks like frozen liquid (because it was). Broad, low curves with rope-like ridges. Generates from low-frequency smooth noise with rope-like normal maps.

**Key features:**
- Lava tubes: Collapsed tunnel sections creating linear trenches, 2-5m wide
- Lava cracks: Narrow fissures 0.1-0.5m wide showing red-orange glow from below
- Cinder cones: Small volcanic mounds, 10-30m tall, 30-100m diameter, crater at top
- Ash plains: Nearly flat areas covered in fine grey-black ash, 0.1-1m deep
- Basalt columns: Hexagonal columns 0.3-1m diameter, forming cliff faces and outcrops

### Texture/Material Rules

| Surface | Material | Special |
|---------|----------|---------|
| Fresh lava rock (a'a) | Black basalt, roughness 0.9+, extreme normals | Slightly warm tint from retained heat |
| Old lava (pahoehoe) | Dark grey-black, roughness 0.6-0.8, smooth normals | May have moss patches |
| Ash ground | Dark grey, roughness 0.85, fine-grain normals | Very uniform, flat |
| Lava cracks | Black edges, orange-red emission center | Subsurface scattering / emission |
| Sulfur deposits | Yellow-white crust, roughness 0.7 | Around vents and cracks |
| Cooled lava with moss | Black + bright green patches | Strong contrast |

**Critical: Lava crack emission** -- Use emission shader (orange-red, 2-5 intensity) in narrow crack geometry. Modulate emission with noise for flickering effect.

### Vegetation Patterns

- **On fresh flows (<100 years):** NOTHING. Absolutely bare.
- **On old flows (100-500 years):** Lichen first, then moss (bright green on black -- very striking)
- **On ancient flows (500+ years):** Sparse grass in soil pockets, pioneer shrubs
- **In ash fields:** Scattered dead tree stumps (killed by ashfall, preserved by ash)
- **Near water:** Occasional hardy plants in geothermal warm zones

### Atmosphere

- **Haze:** Volcanic haze (vog) reduces visibility. Blue-grey tint. 200-500m visibility.
- **Heat distortion:** Shimmer/heat-haze effect above lava cracks and warm ground.
- **Particles:** Ash particles floating in air (grey specks). Ember particles near lava (orange specks).
- **Light:** Red-orange underglow from lava + grey overcast from haze = unique lighting.

### Dark Fantasy Twist

- Lava cracks form patterns that look like runes or writing
- Obsidian formations look like frozen screaming faces
- Some areas are unnaturally hot (ground literally too hot to stand on -- heat damage zones)
- Ash contains bone fragments and metal artifacts (civilization destroyed by eruption)
- The cinder cones have something moving inside them (glowing eyes in crater darkness)
- Basalt columns are arranged too regularly (built, not natural)
- Occasional geysers of black liquid instead of water/steam

---

## 12. Frozen/Tundra

### Visual Characteristics

**Terrain:** Flat to gently rolling, with permafrost-created features. Dominated by white/grey snow and ice. The landscape is strikingly empty and monochromatic.

**Color palette:** White snow (0.5-0.7 value -- NOT pure white, snow is actually grey in overcast), blue-white ice, dark grey exposed rock, brown-grey dead vegetation, pale blue sky.

**Light quality:** Very bright (snow reflects most light). Blue-white ambient. Long shadows (low sun angle). At night: deep blue-violet.

### Terrain Mesh Features

**Permafrost patterns:**
- **Polygon ground:** Hexagonal or polygonal cracks in the ground, 2-30m diameter. Cracks are 0.1-0.5m deep. Creates a distinctive tiled pattern visible from above.
- **Pingos:** Dome-shaped hills with ice core, 5-70m tall, 30-200m diameter. Hollow when ice melts.
- **Thermokarst:** Irregular pits and depressions from melting permafrost, 2-50m diameter.

**Snow features:**
- Snow drifts: Crescent-shaped accumulations on lee side of obstacles, 0.5-3m deep
- Wind-packed snow (sastrugi): Parallel ridges aligned with prevailing wind, 0.1-0.5m high
- Bare patches: Wind-scoured areas where snow is removed, exposing rock/ice beneath

**Ice features:**
- Frozen lakes: Flat white/blue surfaces, often with pressure ridges (0.5-2m high linear ice mounds)
- Ice walls: Exposed glacier or ice cliff faces, blue-white, layered
- Icicle formations: Where water seeps and freezes, creating curtains of ice on cliff faces

### Texture/Material Rules

| Surface | Material | Key Properties |
|---------|----------|----------------|
| Fresh snow | White-grey, roughness 0.6-0.7 (granular) | Subsurface scattering for translucency |
| Packed snow | Grey-white, roughness 0.3-0.5 | Slightly reflective |
| Clear ice | Blue-white, roughness 0.05-0.1 | Near-transparent, refractive |
| Frost (on surfaces) | White crystals, roughness 0.8 | On top of other materials |
| Frozen ground (exposed) | Dark brown-grey, roughness 0.85 | Cracked polygonal pattern |
| Dead vegetation | Brown-grey, roughness 0.9 | Frozen stiff, no movement |

### Vegetation Patterns

- **Trees:** Dead or absent. Occasional standing dead tree skeleton (branches gone, trunk bleached white).
- **Ground cover:** Lichen (grey-green-orange on exposed rock). Frozen moss (dark, brittle).
- **Grass:** Dead, frozen, brown. Only visible where wind has cleared snow.
- **Coverage:** 0-20%. Mostly bare snow/ice/frozen ground.

### Atmosphere

- **Fog:** Ice fog (tiny ice crystals in air). Creates halos around lights. 50-200m visibility.
- **Wind:** Visible as blowing snow particles. Constant.
- **Particles:** Snow crystals (white), ice crystals (sparkling in sunlight).
- **Light:** Blue-white domination. Very bright in sun. Deep blue shadows.

### Dark Fantasy Twist

- Some ice formations contain frozen figures/creatures (visible through translucent ice)
- The frozen dead trees have black marks that look like burn scars (frozen mid-combustion?)
- Wind carries voices/sounds that shouldn't be there (visual: wind streaks with dark particles)
- Areas of unnaturally dark ice (black ice -- not the regular kind, literally dark)
- Snow has blood-red tint in certain patches (iron deposits or something worse)
- Frost patterns on surfaces form recognizable symbols/letters
- The temperature drops sharply in certain areas (visual: breath mist particles, frost creeping on screen edges)

---

## 13. Castle Approach

### Visual Characteristics

**Terrain:** Deliberately modified landscape. The approach to a medieval castle is ENGINEERED for defense. The natural terrain has been altered:

**Cleared zone:** 100-300m around the castle walls, all trees and brush removed. This gives defenders clear sight lines and denies cover to attackers. The ground here is trampled, low grass, and shows signs of heavy use (mud, cart ruts, hoof prints).

**Color palette:** Green-brown (cleared land), grey (castle stone, road), brown (mud, dirt), darker values as you approach the gatehouse (walls cast shadows).

### Terrain Mesh Features

**Approach road:**
- Width: 3-5m (cart width + passing room)
- Surface: Packed earth transitioning to cobblestone near gates
- Grade: Gentle (2-5 degrees), deliberately NOT steep (supply carts must use it)
- Shape: NOT straight. Curves to force approaching enemies to expose their right (shield-less) side
- Final approach: Often flanked by walls, creating a kill zone

**Defensive earthworks:**
- **Moat/ditch:** 3-5m deep, 8-15m wide. Wet moats have water 1-3m deep. Dry moats have steep V or U profiles.
- **Glacis:** Gentle outward slope (10-15 degrees) below walls, cleared of all cover, deliberately exposed.
- **Barbican:** Fortified outwork protecting the gate. Creates a narrow channel 3-5m wide, 10-20m long.
- **Bailey:** Open ground inside walls. Packed earth. Some structures (stables, barracks, smith).

**Wall-terrain interface:**
- Castle walls rise from a rock foundation or motte (artificial mound)
- Motte: Conical earth mound, 5-15m tall, 30-60m diameter at base
- Walls sit on slight elevation above surrounding terrain
- At wall base: accumulated rubble, detritus, drainage channels

### Texture/Material Rules

| Zone | Distance from Castle | Material |
|------|---------------------|----------|
| Wild terrain | >300m | Biome-specific |
| Cleared zone | 100-300m | Short grass, bare earth, stumps |
| Road (far) | 100-300m | Packed earth with cart ruts |
| Road (near) | 0-100m | Cobblestone/flagstone |
| Moat/ditch | At walls | Wet mud or standing water |
| Glacis | 20-50m from walls | Bare sloped earth, no vegetation |
| Wall base | 0-5m | Stone rubble, drainage channels |
| Courtyard | Inside walls | Packed earth, some cobblestone |

### Vegetation Patterns

**The key rule is ABSENCE of vegetation.** The approach zone is deliberately cleared. This is the visual opposite of the forest biome.

- **>300m:** Normal biome vegetation
- **100-300m:** Only grass. All trees removed. Stumps may remain.
- **50-100m:** Short grass only. Obviously maintained/trampled.
- **<50m:** Bare earth. Nothing grows where hundreds of feet, hooves, and cart wheels pass daily.
- **Moat edges:** Reeds in wet moats (functional -- they can't be easily cleared)
- **Against walls:** Weeds in cracks, otherwise bare.

### Dark Fantasy Twist

- The cleared zone has an UNNATURALLY sharp boundary (as if something prevents growth beyond a circle)
- Defensive ditches are deeper/wider than practical (something besides humans dug them)
- The road has dark stains that could be old blood or something else
- Impaled heads/corpses on stakes along the road (grim warning -- very dark fantasy)
- The castle itself looks partly organic (stone growing/flowing, walls with vein-like patterns)
- Crows/ravens in unusual numbers on walls and road
- The moat water is black and still (nothing lives in it)
- Scorch marks on the glacis from previous magical attacks

---

## 14. Cross-Biome Terrain Rules

### How Biomes Transition Into Each Other

Biomes NEVER have sharp boundaries in nature. Transitions occur over 10-50m with ECOTONE zones (transition communities).

**Transition rules for procedural generation:**

| From | To | Transition Width | Key Visual Change |
|------|-----|-----------------|-------------------|
| Forest | Grassland | 20-40m | Trees thin out, grass increases, shrubs bridge |
| Forest | Swamp | 10-20m | Ground gets wetter, trees die, reeds appear |
| Grassland | Mountain | 30-50m | Grass shortens, rocks appear, slope steepens |
| River Valley | Any | 10-30m | Vegetation lushness gradient away from water |
| Forest | Cemetery | 5-15m | Trees thin into cleared zone, wall/fence boundary |
| Plains | Ruins | 15-30m | Grass gradually incorporates rubble/stone fragments |

### Universal Height-Based Material Rules

These apply EVERYWHERE regardless of biome:

| Slope Angle | Material Priority |
|-------------|------------------|
| 0-10 deg | Ground/soil/grass (biome-specific) |
| 10-25 deg | Mixed ground + rock showing through |
| 25-45 deg | Rock dominant, some moss/lichen |
| 45-70 deg | Bare rock, minimal vegetation |
| >70 deg | Cliff face, clean rock |

### Universal Moisture Rules

| Proximity to Water | Effect |
|-------------------|--------|
| 0-2m | Mud/wet material, reeds |
| 2-5m | Darker ground, lush vegetation |
| 5-15m | Slightly greener/denser vegetation |
| >15m | Normal biome materials |

### Universal Erosion Rules

- Water flows downhill and concentrates in valleys (obvious but must be in generation)
- Erosion is strongest on steep slopes with no vegetation
- Deposition occurs where slope decreases (transition from steep to flat)
- Rivers erode outer banks and deposit on inner banks
- Wind erosion is strongest on exposed ridges

---

## 15. Dark Fantasy Color Rules

### VeilBreakers Palette Constraints (from terrain_materials.py)

- Environment saturation: NEVER exceeds 40%
- Value range for environments: 10-50% (dark world)
- Metallic is 0.0 for all terrain (dielectric surfaces only)
- Roughness is generally high (0.7-0.95) -- a wet, grimy, aged world

### How to Darken a Real-World Biome

1. **Reduce value by 20-30%** from real-world reference
2. **Desaturate to max 40%** (most biomes should be 20-35%)
3. **Add corruption tint:** Subtle purple/magenta in shadows (corruption color)
4. **Increase normal strength by 20%** (more surface aggression = more hostile terrain)
5. **Add wear/damage:** Every surface shows age, decay, damage. Nothing is pristine.
6. **Reduce sky contribution:** Overcast, heavy clouds = less ambient light = darker world

### Color Temperature Rules

| Biome | Temperature | Why |
|-------|-------------|-----|
| Forest | Cool green-blue | Shade, moisture |
| Mountain | Cool blue-grey | Altitude, exposure |
| Swamp | Warm sickly amber-green | Decay, stagnation |
| River Valley | Cool blue-green | Water influence |
| Grassland | Warm gold-amber | Open sky, sun exposure |
| Volcanic | Extreme warm red-orange | Lava, heat |
| Frozen | Cool blue-white | Ice, snow |
| Cemetery | Cool grey-blue | Overcast, gloom |
| Ruins | Neutral grey-brown | Decay, age |
| Highland | Cool grey-blue | Exposure, altitude |

### Corruption Gradient

VeilBreakers has a corruption system that tints materials. The corruption_map (0.0 to 1.0) modifies visuals:

| Corruption Level | Visual Effect |
|-----------------|---------------|
| 0.0-0.2 | Normal biome, no visible corruption |
| 0.2-0.4 | Slight purple tint in shadows, vegetation slightly darker |
| 0.4-0.6 | Visible dark veins in terrain, some vegetation dead, fog thicker |
| 0.6-0.8 | Purple-black ground patches, most vegetation dead, glowing cracks |
| 0.8-1.0 | Full corruption: near-black terrain, void energy pools, floating debris |

---

## Sources

### Geology and Geomorphology
- [NPS Fluvial Landforms](https://www.nps.gov/subjects/geology/fluvial-landforms.htm)
- [NPS Meandering Streams](https://www.nps.gov/articles/meandering-stream.htm)
- [Wikipedia: Scree](https://en.wikipedia.org/wiki/Scree)
- [Wikipedia: Cut Bank](https://en.wikipedia.org/wiki/Cut_bank)
- [Wikipedia: Point Bar](https://en.wikipedia.org/wiki/Point_bar)
- [Grand Canyon Rock Layers](https://www.grandcanyontrust.org/blog/geology-rocks-grand-canyon-rock-layers/)
- [USGS Grand Canyon Geology](https://www.usgs.gov/geology-and-ecology-of-national-parks/geology-grand-canyon-national-park)
- [Wikipedia: Canyon](https://en.wikipedia.org/wiki/Canyon)
- [Wikipedia: Confluence](https://en.wikipedia.org/wiki/Confluence)
- [Biology Insights: River Confluence](https://biologyinsights.com/what-is-a-river-confluence-and-how-does-it-work/)

### Biome and Ecology
- [Wikipedia: Tundra](https://en.wikipedia.org/wiki/Tundra)
- [National Geographic: Tundra Biome](https://education.nationalgeographic.org/resource/tundra-biome/)
- [Britannica: Arctic Terrain](https://www.britannica.com/place/Arctic/Terrain)
- [NASA: Tundra Biome](https://earthobservatory.nasa.gov/biome/biotundra.php)
- [Wikipedia: Swamp](https://en.wikipedia.org/wiki/Swamp)
- [Wikipedia: Marsh](https://en.wikipedia.org/wiki/Marsh)
- [NPS Wetlands](https://www.nps.gov/piro/learn/nature/wetlands.htm)
- [Wikipedia: Moorland](https://en.wikipedia.org/wiki/Moorland)
- [NatureScot: Cairngorms](https://nature.scot/doc/landscape-character-assessment-cairngorms-landscape-evolution-and-influences)

### Volcanic Terrain
- [Guide to Iceland: Landscapes](https://guidetoiceland.is/nature-info/the-ultimate-guide-to-icelandic-landscapes)
- [Guide to Iceland: Geology](https://guidetoiceland.is/nature-info/geology-of-iceland)
- [Guide to Iceland: Basalt Columns](https://guidetoiceland.is/best-of-iceland/basalt-columns-in-iceland)

### Medieval Architecture and Defense
- [Medieval Chronicles: Moats, Drawbridges, Gatehouses](https://www.medievalchronicles.com/medieval-castles/medieval-castle-parts/the-role-of-moats-drawbridges-and-gatehouses-in-medieval-castle-defense/)
- [Exploring Castles: Medieval Castle Defence](https://www.exploring-castles.com/castle_designs/medieval_castle_defence/)
- [Great Castles: Anatomy of a Castle](https://great-castles.com/anatomy.html)
- [Wikipedia: Deserted Medieval Village](https://en.wikipedia.org/wiki/Deserted_medieval_village)

### Cemetery Architecture
- [Night Spirit Studio: Gothic Graveyard Scene](https://www.nightspiritstudio.com/post/gothic-graveyard-scene)
- [Legacy Headstones: Gothic Cemetery Architecture](https://legacyheadstones.com/blogs/articles/gothic-style-architecture-of-cemeteries)

### Dark Fantasy Art Direction
- [AesDes: Dark Fantasy Aesthetic](https://www.aesdes.org/2025/01/22/the-dark-fantasy-aesthetic-struggle-amidst-shadows/)
- [80 Level: Dark Souls-Inspired Environment in UE5](https://80.lv/articles/creating-dark-souls-inspired-game-ready-environment-with-gaea)

### Procedural Terrain Generation
- [Alastair Aitchison: Procedural Terrain Splatmapping](https://alastaira.wordpress.com/2013/11/14/procedural-terrain-splatmapping/)
- [Gamedeveloper: Advanced Terrain Texture Splatting](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting)
- [World Machine](https://www.world-machine.com/)

### Trail and Switchback Design
- [Outforia: What Is a Switchback](https://outforia.com/what-is-a-switchback/)
- [HikingDude: Hiking on Scree and Talus](https://www.hikingdude.com/hiking-scree.php)
- [Pmags: Talus vs Scree](https://pmags.com/talus-vs-scree-what-is-the-difference)
