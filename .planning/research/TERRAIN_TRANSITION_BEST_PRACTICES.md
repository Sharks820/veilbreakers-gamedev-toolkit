# Terrain Feature Transition Best Practices

**Researched:** 2026-04-03
**Domain:** Procedural terrain transitions, environmental detail, audio zones, weather effects
**Target:** VeilBreakers dark fantasy action RPG -- terrain pipeline, map_composer, terrain_features, terrain_materials
**Confidence:** MEDIUM-HIGH (cross-referenced GDC talks, AAA postmortems, engine docs, community best practices)

---

## Table of Contents

1. [Transition Types Not Yet Covered](#1-transition-types-not-yet-covered)
2. [Terrain Detail at Player Eye Level](#2-terrain-detail-at-player-eye-level)
3. [Environmental Storytelling via Terrain](#3-environmental-storytelling-via-terrain)
4. [Terrain Audio Zones](#4-terrain-audio-zones)
5. [Weather Effects on Terrain Appearance](#5-weather-effects-on-terrain-appearance)
6. [Current Codebase Gap Analysis](#6-current-codebase-gap-analysis)
7. [Implementation Priorities](#7-implementation-priorities)

---

## 1. Transition Types Not Yet Covered

### 1.1 Bridge Approach Terrain

**Current state:** `map_composer.py` places `bridge_crossing` features at road midpoints over valleys, but generates no terrain geometry for the approach. The bridge itself is placed; the ground leading up to it is untouched.

**What AAA games actually do (Skyrim, Elden Ring, The Witcher 3):**

The bridge approach is a 5-zone transition system:

| Zone | Distance from Bridge | Terrain Treatment |
|------|---------------------|-------------------|
| Approach ramp | 10-20m out | Gradual slope steepening toward bridge level, road widens slightly |
| Abutment platform | 2-5m out | Flat pad at bridge deck elevation, retained by stone wall on downslope side |
| Retaining wall | At edge | Vertical or near-vertical stone/masonry face, 1-4m high depending on terrain drop |
| Erosion undercut | Below retaining wall | Exposed soil/rock where water has eroded behind the wall, darker wet materials |
| Rubble skirt | Base of retaining wall | Loose rocks, scattered masonry fragments, vegetation growing in gaps |

**Key geometry requirements:**
- **Abutment mesh:** A flat-topped trapezoidal mass at each end of the bridge. Width = bridge width + 1m each side. Extends 3-5m from bridge end along road direction. Material: dressed stone or rough masonry matching bridge.
- **Retaining wall:** Vertical face on the downslope side of the abutment. Top matches bridge deck height. Bottom conforms to terrain. Height varies per side based on terrain slope. Material: stone with mortar lines, darker at base from water contact.
- **Approach ramp:** Road surface grades smoothly from terrain level to bridge deck elevation over 10-20m. Crown profile maintained. Side ditches terminate at abutment.
- **Wing walls:** Short angled walls extending diagonally from abutment corners to terrain, preventing soil slumping. 45-degree splay, 2-4m long.

**What to generate procedurally:**
```
1. Sample terrain height at bridge endpoints
2. Compute required abutment height (bridge_deck_z - terrain_z)
3. If height > 0.5m: generate retaining wall + wing walls
4. If height > 2m: add buttress supports on retaining wall
5. Grade approach road from terrain to deck over 15m
6. Place rubble scatter at retaining wall base
7. Apply wet_stone material to lower 30% of retaining wall
```

### 1.2 Dungeon/Cave Entrance Integration with Terrain

**Current state:** `terrain_features.py` generates cliff faces with `cave_entrances` as side-cave openings in canyon walls. `map_composer.py` places `dungeon_entrance` POIs. But there is NO terrain deformation around cave mouths -- no surrounding rubble, no hillside cut, no concealment vegetation.

**The five cave entrance types and their terrain signatures:**

**Type A: Hillside Cut (most common for dungeons)**
- Terrain is cut into a hillside creating a U-shaped depression
- Side walls are exposed rock/earth faces, 2-5m high
- Floor grades downward from terrain level into the cave mouth
- Rubble apron: 3-8m fan of broken rock extending outward from mouth
- Drainage channel: slight V-groove in floor center where water runs out
- Vegetation: ferns and moss concentrate at entrance edges where light and moisture meet
- Material zones: terrain_grass -> exposed_earth -> rubble -> wet_rock -> cave_darkness

**Type B: Cliff Face (natural cave)**
- No terrain deformation needed -- cave is in an existing cliff
- Scree slope at base of cliff leading up to mouth
- Stalactite drip stains on cliff face above entrance
- Guano/organic staining at mouth edges

**Type C: Sinkhole/Pit (vertical entrance)**
- Circular depression in terrain, 3-10m diameter
- Rim slightly raised (0.3m) from displaced material
- Walls become vertical 1-2m in from rim
- Cracked terrain texture radiating 2-5m from rim edge
- Vegetation dies back 1-3m from rim (underground cold air, lack of root support)

**Type D: Concealed (hidden entrance)**
- No visible terrain deformation from distance
- Close inspection reveals: worn path through vegetation, rubble arranged to look natural, slightly different vegetation color (trampled/dead near entrance)
- Overgrown archway partially visible through ivy/vines
- Dark fantasy: corruption tendrils seep from cracks near entrance

**Type E: Ruined Structure (dungeon under ruins)**
- Foundation remnants frame the entrance
- Collapsed ceiling/floor reveals descending stairway
- Terrain around foundation shows buried wall lines (subtle ridges 0.1m high)
- Paving stone fragments scattered in surrounding terrain
- Weeds grow through cracks in remaining paving

**What to generate procedurally:**
```
For each dungeon_entrance POI:
1. Determine type from context (hillside if slope > 15deg, sinkhole if flat, ruin if near settlement)
2. Create terrain deformation: cut (hillside), depression (sinkhole), flatten (ruin)
3. Generate rubble apron mesh (cone of scattered rock pieces)
4. Apply material transition: terrain -> exposed_earth -> rubble -> wet_rock
5. Place concealment vegetation at edges (ferns, ivy, dead branches)
6. Add drainage groove in floor
7. Tag entrance zone with "dark" material tint (light falloff from outside to inside)
```

### 1.3 Waterfall Terrain Environment

**Current state:** `generate_waterfall()` in `terrain_features.py` creates cliff face, step ledges, and splash pool. Materials include cliff_rock, wet_rock, pool_bottom, ledge_stone, moss. Missing: mist zone, spray-fed vegetation, erosion plunge pool shape, wet terrain extending downstream.

**The waterfall terrain system has 7 distinct zones:**

| Zone | Radius from Base | Terrain Character |
|------|-----------------|-------------------|
| Plunge pool | 0-1x pool radius | Deep, steep-sided erosion basin. Floor is scoured rock/gravel, not flat |
| Splash zone | 1-2x pool radius | Permanently wet rock. Water-polished surfaces. No vegetation. Roughness < 0.3 |
| Mist zone | 2-5x pool radius | Perpetually damp. Intense moss/fern growth. Dark wet soil. Slippery surfaces |
| Spray vegetation | 5-10x pool radius | Lush, dense vegetation fed by moisture. Greener than surroundings. Ferns, moss, liverworts |
| Downstream channel | Along outflow | Eroded V-groove. Water-polished stones. Banks 0.5-1m high |
| Upstream approach | Above falls | River/stream bed narrowing toward lip. Current-polished rock at lip edge |
| Cliff face moisture | Flanking cliff | Vertical moisture streaks. Dark mineral staining. Moss in sheltered overhangs |

**Missing from current generator:**
- Mist zone material (perpetually damp terrain extending 2-5x pool radius)
- Spray vegetation density boost (vegetation scatter should be 3-5x denser in mist zone)
- Erosion plunge pool geometry (current pool is flat-bottomed; should be bowl-shaped with deepest point directly under falls)
- Downstream channel (water outflow groove cutting into terrain beyond the pool)
- Wet terrain material extending along downstream channel with gradual drying transition
- Cliff face moisture streaks (vertical dark bands on rock flanking the falls)
- Sound of water metadata (for audio zone tagging, see Section 4)

**PBR material specifications for waterfall zones:**

| Zone | Base Color | Roughness | Notes |
|------|-----------|-----------|-------|
| Splash zone wet rock | 0.06-0.10 (dark) | 0.10-0.20 | Water film creates near-mirror reflection |
| Mist zone soil | 0.05-0.08 | 0.30-0.45 | Darker than dry soil, slightly reflective |
| Spray moss | 0.04-0.07 green-tint | 0.60-0.75 | Saturated moss, deep green |
| Plunge pool bottom | 0.03-0.06 | 0.15-0.25 | Submerged rock, dark, smooth |
| Downstream wet stones | 0.08-0.14 | 0.25-0.40 | Water-polished, lighter than splash zone |

### 1.4 Ford/River Crossing Terrain

**Current state:** No ford/river crossing terrain generator exists. Bridge crossings are placed but fords (shallow wade-across points) are not generated.

**What a ford crossing looks like in terrain:**

A ford is a natural or improved shallow crossing point where the river widens and shallows over a firm bed. Key terrain features:

**Approach ramps (both banks):**
- Terrain grades smoothly down to water level over 5-15m
- Surface transitions: road_surface -> packed_earth -> gravel -> wet_gravel -> shallow_water
- Banks are lower and gentler than elsewhere on the river (that is why the ford is here)
- Cart tracks/ruts visible in soft ground near water edge
- Mud zone 2-4m from water line

**River bed at ford:**
- Wider than normal river (1.5-2x)
- Depth: 0.3-0.8m (ankle to knee for a walking human)
- Substrate: firm gravel or exposed bedrock (sand/mud = stuck wagons, not a viable ford)
- Current-sorted stones: larger upstream, finer downstream
- Mid-stream stepping stones (natural or placed)

**Downstream scatter:**
- Fine sediment deposited downstream of ford (lighter color, smoother)
- Vegetation debris caught on downstream rocks
- Bank erosion slightly worse downstream of ford due to turbulence

**Procedural generation approach:**
```
1. Identify ford location (road crosses river/stream at low-slope point)
2. Widen river channel 1.5x at crossing point, taper back over 20m each direction
3. Lower river bed to 0.3-0.5m depth (shallower than normal)
4. Grade both banks to gentle slope (max 15 degrees)
5. Apply material transition: road -> packed_earth -> gravel -> wet_gravel -> river_bed
6. Place stepping stones (3-6 large flat rocks across, spaced 0.8-1.2m)
7. Add cart track ruts on soft ground approaches
8. Scatter debris downstream (branches, leaf clumps on rocks)
```

### 1.5 Farmland-to-Forest Edge (Ecotone Transition)

**Current state:** `compute_biome_transition()` in `terrain_materials.py` blends splatmap weights between two biomes along an axis with noise-displaced boundary. This handles material blending but NOT the geometric/structural transition between open farmland and dense forest.

**The real-world ecotone has 5 distinct structural layers (field to forest):**

| Layer | Width | Height | Content |
|-------|-------|--------|---------|
| Open field | -- | 0m | Crops, bare earth, low grass |
| Field boundary | 1-3m | 0-1m | Hedgerow, stone wall, or fence. Defines property edge |
| Scrub zone | 3-8m | 1-3m | Bushes, brambles, young saplings, tall weeds. Impenetrable undergrowth |
| Forest edge | 5-15m | 3-10m | Young/medium trees, lower canopy, dense understory. Trees lean outward toward light |
| Dense forest | -- | 10-25m | Mature canopy, less undergrowth (shaded out), taller trunks |

**What the current biome transition system misses:**
- **Height gradient:** The transition is not just a material blend -- it is a height progression from flat field through bushes to tree canopy. Vegetation scatter density and height should increase across the transition.
- **Edge trees lean outward:** Trees at the forest edge grow toward light, creating asymmetric crowns leaning into the field. This is a strong visual cue.
- **Hedgerow/wall geometry:** The field boundary is a discrete linear feature (stone wall, wooden fence, or dense hedge) -- not a gradient. It should be a placed mesh along the boundary.
- **Undergrowth density inversion:** Undergrowth is densest at the forest EDGE (more light penetration) and thinnest deep in the forest (canopy shade). Current scatter does not account for this.
- **Ground material progression:** field_soil -> trampled_grass -> leaf_litter -> forest_floor (across 20-30m)
- **Light zone:** The forest edge casts shadow onto the field. In a dark fantasy setting, this shadow zone is exaggerated -- the forest looms.

**For VeilBreakers dark fantasy:**
- The Thornwood Forest should feel menacing at its edges. Trees should be gnarled, leaning, with visible roots at the boundary.
- Hedgerows near settlements would be maintained (trimmed, with gates). Abandoned ones are overgrown, broken.
- Corruption effects intensify at forest boundaries near Veil cracks: dead vegetation in field near forest, unnaturally dark shadow, ground cracks.

---

## 2. Terrain Detail at Player Eye Level

### 2.1 What Players See Standing on Terrain

At player eye height (1.7m for human characters), terrain within 0-5m dominates the visual field below the horizon line. This is where "flat ground" syndrome kills immersion.

**The micro-detail hierarchy (ground up):**

| Layer | Scale | What It Is | How AAA Games Implement It |
|-------|-------|-----------|---------------------------|
| Displacement | 1-10cm | Micro-undulation of ground surface | Heightmap displacement in vertex shader (Far Cry 5: half-meter resolution heightmap) or tessellation |
| Ground mesh clutter | 2-15cm | Pebbles, twigs, fallen leaves, bone fragments, pottery shards | Instanced static meshes scattered per terrain material type. ARK/DayZ: "ground clutter" system |
| Ground cover | 5-30cm | Grass tufts, small ferns, moss patches, mushrooms | GPU-instanced billboard cards or mesh patches. Density controlled by splat map channel |
| Root/edge detail | 10-50cm | Tree roots breaking surface, rock edges poking through soil | Decal meshes or displacement. Placed at tree bases and rock-terrain junctions |
| Debris layer | 5-30cm | Fallen branches, leaf piles, dead animals, broken items | Authored or procedurally scattered props based on biome |

**What breaks the "flat ground" illusion:**

1. **Micro-undulation:** The single most important detail. Real ground is never flat. A sine-based vertex displacement of 2-5cm amplitude at 0.3-0.8m wavelength creates believable ground. Apply as a detail pass on top of the base heightmap.

2. **Grass tufts at borders:** Where terrain material changes (grass-to-dirt, stone-to-grass), place grass tufts along the boundary. This breaks the hard edge between materials and adds life.

3. **Small rocks:** Scatter 3-8cm rocks on any non-paved surface. Density: 2-5 per square meter on rocky terrain, 0.5-1 per square meter on grassland, 0 on paved surfaces.

4. **Root exposure at tree bases:** Within 1-2m radius of any tree, terrain should be slightly raised (2-5cm) and have exposed root geometry or root-shaped displacement.

5. **Puddle depressions:** Small 10-30cm depressions that collect water after rain. Randomized placement, 1-3 per 10x10m area. Even when dry, the depression is visible as slightly darker/smoother terrain.

### 2.2 Camera Distance LOD for Terrain Detail

**The LOD cascade for terrain detail (based on Far Cry 5 / Horizon approach):**

| Distance | Geometry | Texturing | Clutter |
|----------|----------|-----------|---------|
| 0-5m | Full tessellation + displacement. POM for ground detail | Full PBR, 4-layer splatmap, detail normal maps | All ground clutter visible. Full density grass, pebbles, debris |
| 5-20m | Reduced tessellation. No POM | Full PBR, 4-layer splatmap, reduced detail normals | Grass cards visible. Small clutter (pebbles) hidden |
| 20-50m | Base mesh only | 4-layer splatmap, no detail textures | Only large grass patches visible as low-poly patches |
| 50-200m | Simplified mesh (LOD 1-2) | Baked composite texture, no splatmap | No clutter. Color from baked terrain texture only |
| 200m+ | Minimal mesh (LOD 3+) | Flat color + normal. Virtual texture or impostor | Nothing |

**For Blender procedural generation (VeilBreakers):**
The LOD cascade is primarily a Unity runtime concern. In Blender, generate the highest detail level only. However, the export pipeline should:
- Tag vertices with terrain material type (for Unity splatmap reconstruction)
- Export micro-undulation as a separate detail heightmap
- Include clutter spawn point metadata (position + material type + density) rather than actual clutter geometry
- Bake a composite color texture at reduced resolution for distant LOD

### 2.3 Breaking Flat Ground in Procedural Generation

**Current gap in VeilBreakers:** The terrain generators produce smooth heightfield meshes. While erosion adds macro-level variation, there is no micro-displacement pass.

**Recommended implementation:**

```python
def apply_micro_undulation(vertices, terrain_type, seed=42):
    """Add subtle height variation to break flat ground.
    
    Applied AFTER all other terrain operations as a final detail pass.
    """
    for i, (x, y, z) in enumerate(vertices):
        # Base undulation: low-frequency humps
        z += noise(x * 0.5, y * 0.5, seed) * 0.03  # 3cm humps at 2m wavelength
        
        # Detail variation: high-frequency bumps
        z += noise(x * 3.0, y * 3.0, seed + 1) * 0.008  # 8mm at 0.33m wavelength
        
        # Terrain-type scaling:
        # Rocky terrain: more variation. Grassland: gentle. Paved: none
        scale = {"rock": 1.5, "grass": 1.0, "dirt": 1.2, "paved": 0.0, "mud": 0.8}
        z *= scale.get(terrain_type, 1.0)
        
        vertices[i] = (x, y, z)
```

---

## 3. Environmental Storytelling via Terrain

### 3.1 Battle Aftermath Terrain

**What a battle does to terrain (lasting effects):**

| Feature | Geometry | Material | Scatter |
|---------|----------|----------|---------|
| Impact craters | Circular depressions, 0.5-3m diameter, 0.1-0.5m deep | Scorched earth: charred black center, brown rim | Broken weapon/shield fragments in and around crater |
| Scorched earth | Flat or slightly depressed patch, 2-10m | Black/dark brown, roughness 0.95, no vegetation | Charred wood fragments, ash piles |
| Trampled ground | Slightly compressed, churned surface | Mud/bare earth, mixed grass-dirt | Boot prints (displacement texture), horse hoof marks |
| Blood staining | No geometry change | Dark red-brown patches on existing material, fades over time | Broken arrow shafts, torn cloth |
| Defensive earthworks | Linear raised berms 0.5-1m high, ditches 0.3-0.5m deep | Exposed soil on berm, water in ditch | Sharpened stakes, broken barricade fragments |
| Cart/siege track ruts | Parallel grooves 0.1-0.2m deep, 1.5m apart | Compressed mud/dirt | Broken wheel spokes, scattered supplies |

**Procedural parameters for battle terrain:**
```python
def generate_battle_aftermath(
    center: Vec2,
    radius: float = 30.0,
    intensity: float = 0.7,  # 0=skirmish, 1=major battle
    age: float = 0.5,  # 0=fresh, 1=ancient (overgrown)
    has_fire: bool = True,
    has_siege: bool = False,
    seed: int = 42,
):
    # intensity controls: crater count, scorch area, trampling extent
    # age controls: vegetation regrowth, rust on weapons, earth settling
    # has_fire: adds scorched patches, charcoal, burnt timber
    # has_siege: adds earthworks, wider area, siege equipment remnants
```

### 3.2 Abandoned Camp Terrain

**A camp leaves these terrain marks (in order of visibility):**

1. **Flattened grass circle:** 5-15m diameter where tents stood. Grass is pressed flat or dead. Slowly recovers (weeks: pressed, months: thin regrowth, years: nearly invisible).
2. **Fire-blackened circle:** 0.5-1m diameter charred ground at campfire site. Ring of fire-cracked stones around it. Ash deposit. Very slow to recover (years).
3. **Cart tracks:** Paired ruts leading in from nearest road. Depth depends on traffic volume and soil softness.
4. **Latrine pit:** Small disturbed earth area 10-20m downwind from camp center. Slightly mounded from fill.
5. **Wear path:** Trampled path between tent sites, fire, latrine, water source. Width 0.3-0.5m.
6. **Refuse scatter:** Broken pottery, bone fragments, torn cloth in a midden area near camp edge.
7. **Post holes:** Small circular depressions where tent poles stood. 0.1m diameter, 2-4 per tent site.

**Material layers for abandoned camp:**
- Fresh (age=0): bare_earth center, trampled_grass ring, scattered_ash at fire, mud at paths
- Weathered (age=0.5): thin_grass center, regular_grass ring, charcoal_stain at fire, dirt_path
- Ancient (age=1.0): normal_grass everywhere, subtle_depression at fire, barely visible path as slightly darker grass

### 3.3 Ancient Ruins Terrain

**Buried structures affect terrain surface in specific ways:**

1. **Foundation lines:** Linear ridges 0.05-0.15m high where buried walls resist soil settling. Form rectangular patterns revealing floor plan. Vegetation grows differently over walls (shorter grass, more weeds due to less soil depth).
2. **Paving fragments:** Broken flagstone/cobble patches poking through grass. Clustered near doorways and along paths. Scattered further from center.
3. **Column bases:** Circular stone platforms 0.5-1m diameter at ground level. Grass grows around but not on them.
4. **Overgrown paths:** Slightly lower terrain following old road alignment. Different vegetation color (compacted soil underneath).
5. **Rubble mounds:** Low mounds (0.5-2m high) where walls collapsed. Mixed material: stone chunks, mortar, timber fragments.
6. **Subsidence:** Terrain dips where underground spaces (cellars, sewers, crypts) have partially collapsed. 0.3-1m depression, 2-5m diameter. Ground may be cracked around edges.

**Material progression from ruin center outward:**
- Center: exposed_stone, broken_paving, rubble
- Inner ring: paving_fragments_in_grass, exposed_foundation_ridges
- Outer ring: slightly_different_grass_over_buried_structure
- Beyond: normal_terrain

### 3.4 Corrupted Terrain Near the Veil

**VeilBreakers-specific. The Veil corruption manifests in terrain as:**

1. **Cracked earth:** Polygonal crack patterns (like dried mud but on any terrain type). Cracks are 0.05-0.10m wide, 0.1-0.3m deep. Emit faint purple/blue glow.
2. **Glowing fissures:** Larger cracks, 0.2-1m wide, that emit visible light. Ground around fissures is warped slightly upward (0.1-0.3m bulge). Temperature: warm.
3. **Dead vegetation patterns:** Circular kill zones radiating from corruption source. Sharp boundary: living grass -> brown dead grass -> bare soil -> cracked/corrupted earth. Boundary is NOT smooth -- it is jagged, fractal.
4. **Material corruption:** Existing materials shift toward purple-black. Roughness decreases (surfaces become unnaturally smooth/glassy). Faint emission in cracks and at corruption boundary.
5. **Floating debris:** Small rocks and dirt particles levitate 0.1-0.5m above ground near fissures. (Particle effect, not terrain geometry.)
6. **Terrain warping:** Ground surface is subtly warped near Veil cracks -- gentle hills where ground should be flat, depressions on ridges. Reality distortion.

**Corruption gradient (distance from Veil crack):**

| Distance | Visual | Material Change |
|----------|--------|----------------|
| 0-2m | Glowing fissures, floating debris, severe warping | Full corruption: purple-black, emission, roughness 0.1 |
| 2-10m | Cracked earth, dead vegetation, mild warping | Partial corruption: desaturated, darkened, roughness -0.2 |
| 10-30m | Dying vegetation, subtle cracks | Tint shift: slight purple cast, edges of corruption |
| 30-50m | Stressed vegetation (discolored) | Minimal: very slight color shift |
| 50m+ | Normal | No change |

---

## 4. Terrain Audio Zones

### 4.1 Surface Type Audio Tags

**Current state:** No audio metadata is exported with terrain. The terrain material system in `terrain_materials.py` defines 14 biomes with material palettes, but none carry audio surface type information.

**Standard audio surface types for dark fantasy RPG:**

| Surface Type | Audio Tag | Footstep Character | Example Biome Materials |
|-------------|-----------|-------------------|------------------------|
| Grass | `surface_grass` | Soft rustle, slight squish | sparse_grass, forest_grass, meadow_grass |
| Dirt/Earth | `surface_dirt` | Dull thud, slight crunch | forest_soil, dark_soil, packed_earth |
| Stone | `surface_stone` | Hard click/clack, echo in enclosed spaces | gray_stone, weathered_stone, flagstone |
| Wood | `surface_wood` | Hollow thump, creak | wooden_floor, bridge_planks, dock_boards |
| Mud | `surface_mud` | Squelch, suction | black_mud, swamp_mud, wet_earth |
| Gravel | `surface_gravel` | Crunch, shifting | gravel, river_gravel, scree |
| Sand | `surface_sand` | Soft scrape, whisper | wet_sand, beach_sand, desert_sand |
| Snow | `surface_snow` | Crunch (cold), squish (wet) | snow_patches, deep_snow |
| Water (shallow) | `surface_water_shallow` | Splash, ripple | ford_crossing, puddle, stream |
| Water (deep) | `surface_water_deep` | Heavy splash, wade sounds | river, pool, lake_shore |
| Metal | `surface_metal` | Clang, ring | iron_grate, metal_plate, chain |
| Corruption | `surface_corruption` | Unsettling crackle, crystalline hum | corrupted_stone, veil_crack |
| Bone/Organic | `surface_bone` | Snap, wet crunch | bone_field, organic_growth |
| Rubble | `surface_rubble` | Shifting debris, clattering | rubble, collapsed_masonry |

### 4.2 How to Tag Terrain for Audio

**The industry standard approach (Unreal/Unity/Wwise):**

1. **Physical Material assignment:** Each terrain material is assigned a Physical Material in the engine. The Physical Material contains the audio surface type tag.
2. **Runtime detection:** On footstep events, a downward raycast from the character's foot hits terrain. The engine reads the Physical Material at that point.
3. **Splatmap lookup:** For blended terrain, the engine samples the splatmap at the hit point, determines the dominant material layer, and uses that layer's surface type.
4. **Wwise integration:** The surface type tag sets a Wwise Switch (e.g., `Footstep_Surface`) which selects the appropriate sound container.

**What VeilBreakers needs to export from Blender:**

Each terrain chunk should carry metadata mapping vertex color channels to audio surface types:

```python
MATERIAL_AUDIO_MAP = {
    # terrain_materials.py material name -> audio surface tag
    "dark_leaf_litter": "surface_dirt",
    "exposed_roots": "surface_wood",
    "forest_soil": "surface_dirt",
    "mossy_rock": "surface_stone",
    "black_mud": "surface_mud",
    "toxic_pool": "surface_water_shallow",
    "gravel": "surface_gravel",
    "snow_patches": "surface_snow",
    "wet_sand": "surface_sand",
    "corroded_stone_purple": "surface_corruption",
    # ... map all terrain materials
}
```

Export this mapping as JSON metadata alongside the terrain FBX/glTF. Unity's terrain setup tool (`unity_scene` action=`terrain_setup`) should read this metadata and assign Unity Physical Materials accordingly.

### 4.3 Audio Zone Boundaries

Beyond footstep surfaces, terrain should define ambient audio zones:

| Zone Type | Trigger | Audio Effect |
|-----------|---------|-------------|
| Water proximity | Within 10m of river/lake | Ambient water loop, volume scales with proximity |
| Waterfall | Within 30m of waterfall | Roaring water, mist hiss, scales with distance |
| Wind exposure | Ridge tops, open fields | Wind loop, intensity based on elevation/exposure |
| Forest interior | Under canopy | Bird calls, insect buzz, wind-in-leaves, reduced wind volume |
| Cave entrance | Within 5m of cave mouth | Echo reverb increase, wind whistle, dripping water |
| Corruption zone | Within corrupted terrain | Low-frequency hum, crystalline crackling, ambient unease |
| Settlement | Within town/village bounds | Crowd murmur, smithing, animal sounds |

These should be exported as bounding volumes (convex hulls or radius-based) with the terrain, not per-vertex data.

---

## 5. Weather Effects on Terrain Appearance

### 5.1 Wet Terrain (Rain)

**Current state:** Terrain materials have fixed roughness/color values. No dynamic wetness system exists.

**How wet surfaces work in PBR (Sebastien Lagarde, DONTNOD/Frostbite):**

Water on a surface causes two physical changes:
1. **Darkening:** Water fills micro-cavities in the surface, reducing diffuse scattering. Base color multiplied by 0.4-0.7 (porous materials darken more, smooth stone darkens less).
2. **Roughness reduction:** Water film smooths the surface. Roughness multiplied by 0.1-0.5 depending on water thickness.

**Wetness parameter cascade:**

| Material Property | Dry Value | Damp (light rain) | Wet (heavy rain) | Puddle |
|-------------------|-----------|-------------------|-------------------|--------|
| Base Color | original | original * 0.7 | original * 0.5 | original * 0.3 |
| Roughness | original | original * 0.6 | original * 0.3 | 0.05-0.10 |
| Normal strength | original | original * 0.8 | original * 0.5 | 0.0 (flat water surface) |
| Specular/Fresnel | original | boosted 2x | boosted 5x | full water Fresnel (0.02 F0) |

**Puddle formation logic:**
Puddles form in terrain depressions. Use the heightmap to detect local minima:
```
For each vertex:
  If vertex.z < average_neighbor_z - threshold:
    puddle_depth = average_neighbor_z - vertex.z
    If puddle_depth > min_puddle_depth (0.01m):
      Apply puddle material (near-zero roughness, darkened color, flat normal)
```

**What to implement in Blender (static bake):**
Rather than real-time wetness, generate a "wet variant" material set:
- `terrain_material_wet` variants with adjusted roughness/color
- Puddle mask: vertex color channel (e.g., Alpha) indicating puddle probability
- Export puddle mask to Unity for runtime weather-driven material switching

### 5.2 Snow Accumulation Patterns

**Snow does not accumulate uniformly. The rules:**

1. **Surface orientation:** Snow accumulates on surfaces facing UP (dot product of normal with up-vector > 0.7). Steep slopes (> 60 degrees) do not hold snow.
2. **Wind direction:** Windward faces accumulate less (wind blows snow off). Leeward faces accumulate more (drift). Wind shadow behind ridges creates deep drifts.
3. **Exposure:** Ridges, summits, exposed hilltops lose snow to wind. Sheltered valleys, forest floors, building lee sides retain snow.
4. **Aspect (hemisphere-dependent):** North-facing slopes (northern hemisphere) retain snow longer (less direct sunlight). South-facing slopes melt first.
5. **Flat surfaces first:** Horizontal surfaces accumulate before angled ones. Roofs, flat rocks, wall tops show snow before slopes.
6. **Depth variation:** Snow drifts against vertical surfaces (walls, tree trunks, rock faces). Depth can be 2-5x average near obstacles.

**Snow material blending for terrain splatmap:**
```python
def compute_snow_weight(normal, world_position, wind_direction, snow_amount):
    """Compute snow accumulation weight for a terrain vertex.
    
    Returns weight 0.0 (no snow) to 1.0 (full snow coverage).
    """
    up_dot = max(0, normal.dot(UP_VECTOR))  # Flat = more snow
    
    # Steep slopes don't hold snow
    if up_dot < 0.5:
        return 0.0
    
    # Wind exposure reduces snow
    wind_dot = max(0, normal.dot(wind_direction))  # Facing wind = less snow
    wind_factor = 1.0 - wind_dot * 0.6
    
    # Altitude: more snow at higher elevations
    altitude_factor = clamp((world_position.z - snow_line) / transition_height, 0, 1)
    
    # Sheltering: concave terrain retains more
    shelter_factor = 1.0 + curvature * 0.3  # curvature > 0 = concave = sheltered
    
    return clamp(up_dot * wind_factor * altitude_factor * shelter_factor * snow_amount, 0, 1)
```

### 5.3 Fog Interaction with Terrain

**Fog behavior in terrain is primarily a Unity runtime effect, but terrain geometry informs fog placement:**

1. **Valley pooling:** Fog collects in terrain depressions and valleys. Fog density should be highest at terrain local minima and decrease with height above valley floor.
2. **Ridge thinning:** Fog is thin or absent on ridge tops and exposed hilltops. Wind disperses fog from elevated points.
3. **River corridors:** Fog follows river channels and gathers at confluences. Water evaporation feeds fog formation.
4. **Forest trapping:** Dense forest canopy traps fog within the forest interior. Fog is denser under trees than in adjacent clearings.

**What to export from Blender for Unity fog:**
- Terrain depression map: per-vertex height relative to local average (negative = depression = fog accumulation)
- Water proximity map: distance to nearest water body/river (closer = more fog)
- Canopy coverage map: vertex color indicating overhead vegetation density

These maps let Unity's volumetric fog system place fog density spatially using terrain-derived data rather than uniform fog volumes.

---

## 6. Current Codebase Gap Analysis

### What EXISTS and works:
- Biome transition blending via splatmap (`compute_biome_transition`) -- axis-aligned with noise displacement
- Waterfall generator with cliff, steps, pool, cave behind (`generate_waterfall`)
- Canyon, cliff face, swamp, sinkhole generators in `terrain_features.py`
- 14 biome material palettes with slope/height/moisture-based splatmap assignment
- Bridge crossing placement in `map_composer.py`
- Dungeon entrance POI placement
- Terrain sculpting (raise/lower/smooth/flatten/stamp)
- Spline-based terrain deformation
- Erosion (hydraulic + thermal)
- Corruption tint overlay system

### What is MISSING (ordered by impact):

| Gap | Impact | Complexity | Where to Add |
|-----|--------|------------|-------------|
| Micro-undulation detail pass | HIGH -- flat ground kills immersion | LOW | `terrain_advanced.py` as post-process function |
| Audio surface type metadata | HIGH -- silent terrain breaks immersion | LOW | `terrain_materials.py` + export pipeline |
| Bridge approach terrain (abutments, retaining walls) | HIGH -- bridges float over terrain | MEDIUM | `map_composer.py` bridge_crossing handler |
| Cave/dungeon entrance terrain deformation | HIGH -- entrances appear pasted on | MEDIUM | New function in `terrain_features.py` |
| Waterfall mist zone + downstream channel | MEDIUM -- waterfall feels incomplete | LOW | Extend `generate_waterfall()` |
| Ford/river crossing terrain | MEDIUM -- all river crossings are bridges | MEDIUM | New generator in `terrain_features.py` |
| Battle aftermath terrain overlay | MEDIUM -- environmental storytelling | MEDIUM | New generator, integrates with biome system |
| Farmland-to-forest ecotone structure | MEDIUM -- biome borders lack structural depth | MEDIUM | Extend `compute_biome_transition` + scatter rules |
| Wetness parameter variants | LOW (Unity runtime) | LOW | `terrain_materials.py` wet material variants |
| Snow accumulation logic | LOW (Unity runtime) | LOW | Pure-logic function for export metadata |
| Fog terrain data export | LOW (Unity runtime) | LOW | Depression/water proximity maps in export |
| Corruption terrain warping | LOW (exists as tint, needs geometry) | MEDIUM | Extend corruption overlay in `terrain_materials.py` |
| Abandoned camp terrain overlay | LOW -- nice to have | LOW | New small generator |
| Ancient ruins terrain marks | LOW -- nice to have | MEDIUM | Integrate with worldbuilding ruin generators |

---

## 7. Implementation Priorities

### Phase 1: Foundation (HIGH impact, LOW complexity)

1. **Micro-undulation pass** -- Add `apply_micro_undulation()` to `terrain_advanced.py`. Call it as the last step in terrain generation before material assignment. Parameterize by terrain type. Estimated: 50 lines of pure logic.

2. **Audio surface type mapping** -- Add `MATERIAL_AUDIO_MAP` dict to `terrain_materials.py`. Map every existing material to one of 14 audio surface tags. Include in terrain export metadata. Estimated: 40 lines.

3. **Waterfall mist zone extension** -- Extend `generate_waterfall()` to produce mist_zone material zone extending 3x pool radius, downstream channel groove, and spray vegetation density metadata. Estimated: 80 lines.

### Phase 2: Structural Transitions (HIGH impact, MEDIUM complexity)

4. **Bridge approach terrain** -- New function `generate_bridge_approach()` that creates abutment geometry, retaining walls, and approach ramps when bridge_crossing features are placed. Integrate into `map_composer.py` bridge placement. Estimated: 200 lines.

5. **Cave entrance terrain deformation** -- New function `generate_cave_entrance_terrain()` with 5 entrance types. Apply terrain sculpting (cut/depress/flatten) around dungeon_entrance POIs. Add rubble apron scatter. Estimated: 250 lines.

6. **Ford crossing generator** -- New function `generate_ford_crossing()` for river-road intersections where bridge is inappropriate (low banks, shallow water). Estimated: 150 lines.

### Phase 3: Environmental Storytelling (MEDIUM impact)

7. **Battle aftermath overlay** -- Terrain deformation + material overlay system for battle sites. Parameterized by intensity and age. Estimated: 200 lines.

8. **Farmland-forest ecotone** -- Extend biome transition to include structural layer progression (hedgerow placement, undergrowth density gradient, edge-tree lean). Estimated: 150 lines.

9. **Abandoned camp terrain** -- Small terrain overlay with fire circle, trampled zones, cart tracks. Estimated: 100 lines.

### Phase 4: Runtime Data (LOW impact on Blender side, enables Unity features)

10. **Wet material variants** -- Generate `_wet` versions of terrain materials with adjusted roughness/color. Export puddle probability mask. Estimated: 60 lines.

11. **Snow accumulation metadata** -- Pure-logic function computing snow weight per vertex based on normal, altitude, wind exposure. Export as vertex color channel. Estimated: 80 lines.

12. **Fog terrain data** -- Depression map and water proximity map computed from terrain heightfield. Export for Unity volumetric fog. Estimated: 60 lines.

---

## Sources

- [Terrain Rendering in Far Cry 5 (GDC 2018)](https://www.gdcvault.com/play/1025480/Terrain-Rendering-in-Far-Cry) -- Heightmap resolution, LOD cascade, cliff displacement
- [Far Cry 5 Terrain Rendering Slides](https://media.gdcvault.com/gdc2018/presentations/TerrainRenderingFarCry5.pdf) -- Half-meter terrain authoring resolution, vertex shader displacement
- [Water Drop 2b - Dynamic Rain and Its Effects (Sebastien Lagarde)](https://seblagarde.wordpress.com/2013/01/03/water-drop-2b-dynamic-rain-and-its-effects/) -- PBR wetness model, roughness/color modification, puddle formation
- [Game Environments: Making Wet Environments (fxguide)](https://www.fxguide.com/fxfeatured/game-environments-partc/) -- Specular reflection for wet surfaces, water film PBR
- [Footsteps Material Management (Audiokinetic/Wwise)](https://www.audiokinetic.com/en/blog/footsteps-material-management-using-wwise-unreal-engine-4-unity-3d/) -- Physical Material tagging, Switch-based footstep audio
- [Footsteps Audio System in UE5/Wwise (Above Noise Studios)](https://abovenoisestudios.com/blogeng/wwiseue5footstepseng) -- Line trace surface detection, PM_ naming convention
- [Environmental Storytelling in Video Games (GameDesignSkills)](https://gamedesignskills.com/game-design/environmental-storytelling/) -- Battle aftermath, abandoned locations, layered history in terrain
- [Environmental Storytelling (IntechOpen)](https://www.intechopen.com/online-first/1225186) -- Scorch marks, fortified bunkers, desolate fields as narrative devices
- [Creating Snowy Scenes with UE4 & Houdini (80.lv)](https://80.lv/articles/creating-snowy-scenes-with-ue4-houdini) -- Snow accumulation rules, wind direction, aspect-based retention
- [Dynamic Snow Shader (Alan Zucconi)](https://www.alanzucconi.com/2018/08/18/shader-showcase-saturday-6/) -- Normal-based accumulation, wind shadow, drift modeling
- [Snow Accumulation Effects in Screen Space (IEEE)](https://ieeexplore.ieee.org/document/8939960/) -- Wind direction, surface orientation, exposure-based accumulation
- [Generating Procedural Plant Ecosystems (80.lv)](https://80.lv/articles/002sgr-generating-procedural-plant-ecosystems) -- Ecotone transitions, vegetation density gradients
- [Creating Dense Forests in Prologue (PlayerUnknown Productions)](https://playerunknownproductions.net/news/creating-dense-forests-in-prologue-balancing-immersion-and-performance) -- Forest density, performance-immersion balance
- [Ford (crossing) - Wikipedia](https://en.wikipedia.org/wiki/Ford_(crossing)) -- Physical characteristics of natural fords, substrate requirements
- [DayZ Grass-clutter Configuration](https://community.bistudio.com/wiki/DayZ:Grass-clutter_configuration) -- Ground clutter density, distance settings, performance
- [GPU-Optimized Terrain Erosion Models (DaydreamSoft)](https://www.daydreamsoft.com/blog/gpu-optimized-terrain-erosion-models-for-procedural-worlds-building-hyper-realistic-landscapes-at-scale) -- GPU erosion, dynamic terrain deformation
- [Road Modeling in AAA Games (Polycount)](https://polycount.com/discussion/149269/road-modeling-in-aaa-bigger-games) -- Road-terrain integration, dedicated tooling
- [Procedural World Generation of Far Cry 5 (GDC 2018)](https://tools.engineer/gdc2018-procedural-world-generation-of-far-cry-5) -- PCG scatter, terrain-aware placement
- [Enviro 3 - Terrain Shader (Unity)](https://unityassetcollection.com/enviro-3-terrain-shader-free-download/) -- Dynamic rain, puddles, snow terrain shader, anti-tiling
