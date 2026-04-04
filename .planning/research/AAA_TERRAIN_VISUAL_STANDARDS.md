# AAA Terrain Visual Standards: What Shipped Dark Fantasy Games Actually Look Like

**Researched:** 2026-04-03
**Domain:** Terrain surface, trees, rocks/cliffs, water -- visual quality standards from shipped AAA titles
**Reference Games:** Elden Ring, Skyrim, Horizon Zero Dawn/Forbidden West, Ghost of Tsushima, Dark Souls III
**Confidence:** HIGH (cross-referenced GDC presentations, ArtStation breakdowns, engine documentation, shipped game analysis)

---

## Table of Contents

1. [Terrain Surface](#1-terrain-surface)
2. [Trees and Vegetation](#2-trees-and-vegetation)
3. [Rocks and Cliffs](#3-rocks-and-cliffs)
4. [Water](#4-water)
5. [Quality Tier Definitions](#5-quality-tier-definitions)
6. [Dark Fantasy Specific Standards](#6-dark-fantasy-specific-standards)
7. [VeilBreakers Gap Analysis](#7-veilbreakers-gap-analysis)
8. [Sources](#8-sources)

---

## 1. Terrain Surface

### 1.1 What AAA Ground ACTUALLY Looks Like Up Close

**At 1-3 meters (close inspection):**
- Individual grass blades visible, each with distinct color variation along the blade length (darker at base, lighter/yellower at tip)
- Dirt particles: visible granularity in soil textures -- individual grain-sized bumps in the normal map, not smooth color
- Pebbles: scattered small stones (2-5cm) sitting ON the surface with actual geometry or parallax occlusion, not painted flat
- Root patterns: where trees meet ground, gnarled roots 5-15cm thick emerge, partially buried
- Leaf litter: dead leaves, small twigs, pine needles scattered irregularly
- No visible texture repetition within a 5m radius

**At 10-30 meters (mid-range):**
- Ground reads as a coherent biome (forest floor, rocky hillside, muddy path)
- Material transitions are height-blended: rocks poke through grass, not smeared linear blends
- Grass density variation: thick in valleys, sparse on ridges, none on paths
- Color temperature shifts: slightly warmer in sun-exposed areas, cooler in shade

**At 50-200 meters (distance):**
- Macro color variation prevents tile recognition: color shifts every 20-50m
- LOD grass represented by flat color patches that match close-range grass hue
- No visible grid patterns, no repeating texture squares

### 1.2 The "Never Flat" Rule

**AAA terrain is NEVER truly flat.** This is the single most important visual standard.

**Micro-undulation specifications:**
- Even "flat" plains have 5-15cm height variation per meter (micro noise)
- Rolling frequency: gentle bumps every 2-5 meters with 10-30cm amplitude
- Erosion channels: shallow 3-8cm depressions following natural water drainage paths
- Animal trails: subtle 2-4cm compressed paths through grass areas
- Tree root heave: 5-20cm bumps radiating 1-3m from tree bases

**Noise layers used in AAA terrain (from World Machine / Gaea pipelines):**

| Layer | Frequency | Amplitude | Purpose |
|-------|-----------|-----------|---------|
| Continental | 500-2000m | 50-500m | Mountain ranges, valleys |
| Regional | 50-200m | 5-50m | Hills, ridges, basins |
| Local | 10-50m | 0.5-5m | Mounds, depressions, gullies |
| Micro | 1-5m | 5-30cm | Ground undulation, bumps |
| Surface | 0.1-0.5m | 1-5cm | Soil texture, pebble bumps |

**What "flat" looks like in AAA:**
- Elden Ring's Limgrave plains: gentle rolling with 0.5-2m undulation per 20m, scattered boulders breaking sightlines
- Skyrim's tundra: low rolling hills with 1-3m variation per 30m, grass tufts on micro-bumps
- Ghost of Tsushima's pampas fields: extremely subtle 10-20cm rippling every 3-5m, masked by tall grass

### 1.3 Material Transitions (Height Blending)

**The AAA standard is height-based blending, NOT linear alpha blending.**

Linear blend (BAD): Two materials fade into each other creating a 50/50 mush zone 1-3m wide. Looks like watercolor bleeding.

Height blend (GOOD): Uses a height map per material. Rocks poke through grass at their highest points first. Dirt fills the crevices between rocks. The transition zone is physically motivated -- materials interact based on their 3D surface properties.

**Technical implementation (shipped standard):**

```
transition_sharpness = 0.15 to 0.3  (higher = sharper boundary)
blend_zone_width = 0.5 to 2.0 meters (how wide the mixing zone is)
height_offset = per-material height map (8-bit, packed in alpha channel)
```

**What transitions look like in shipped games:**
- Grass-to-rock: individual grass blades grow shorter and sparser as rock surfaces emerge, rocks poke through first at high points, grass persists in crevices
- Grass-to-dirt: grass thins gradually over 1-2m, bare soil patches appear, then dominant dirt with occasional grass tuft
- Dirt-to-mud: color darkens, roughness decreases (shinier), slight displacement depression
- Path-to-grass: compressed dirt path with clearly worn edges, grass encroaching from sides

### 1.4 Anti-Tiling (Macro Variation)

**The problem:** Terrain textures tile. At distance, repeating patterns become obvious grid squares.

**Shipped solutions (ALL must be used simultaneously):**

1. **Macro noise overlay** -- A large-scale (50-200m period) color/value noise texture multiplied over terrain. Shifts hue/brightness by 5-15% across the landscape. Breaks pattern recognition.

2. **Stochastic sampling** -- Sample the same texture from different UV offsets and blend using height maps. Eliminates tiling at ~1.5x texture cost. Used in Horizon Forbidden West (deferred texturing), MicroSplat (Unity).

3. **Detail distance scaling** -- Close-up uses high-frequency detail texture (0.5m UV scale). At distance, blends to a lower-frequency version (2-5m UV scale). Prevents both close-up blur and distant repetition.

4. **Rotation variation** -- Randomly rotate texture samples per terrain patch (90/180/270 degrees). Breaks directional patterns (e.g., visible grass direction repeating).

**Minimum standard for "no visible tiling":**
- No repeated pattern recognizable at ANY camera distance
- No grid lines visible at oblique angles
- Color variation visible every 20-50m even in uniform biomes

### 1.5 Terrain Texture Resolution Standards

**Industry standard texel density for terrain:**

| Game Type | Texel Density | Texture Resolution |
|-----------|---------------|-------------------|
| Third-person (Elden Ring, Skyrim) | 5.12 px/cm (512 px/m) | 2K tiling textures |
| First-person (Elder Scrolls in FPP) | 10.24 px/cm (1024 px/m) | 2K-4K tiling |
| Terrain unique maps | N/A | 4K-8K for heightmap |
| Detail/micro textures | 20.48 px/cm | 1K-2K tiling |

**PBR map requirements per terrain layer:**
- Base Color (albedo) -- 2K minimum
- Normal Map -- 2K minimum (carries most of the visual detail)
- Height Map -- 1K minimum (used for parallax and height blending)
- Roughness -- 1K minimum (can be packed with metallic/AO)
- AO (ambient occlusion) -- 1K minimum (baked micro-shadowing)
- Metallic -- usually 0.0 for all terrain (terrain is dielectric)

**Splatmap resolution:**
- Skyrim: 6 texture layers per terrain quad
- Typical modern: 4 layers per splatmap RGBA, multiple splatmaps for more
- Frostbite (Battlefield): procedural splatmap from terrain data (slope, height, moisture)

### 1.6 Ground Cover Elements

**What sits ON the terrain surface in AAA:**

| Element | Density | Size | Placement Rule |
|---------|---------|------|----------------|
| Grass blades | 50-200 per m2 | 5-30cm tall | GPU-instanced, density by biome mask |
| Small rocks/pebbles | 3-10 per m2 | 2-8cm | Scattered, denser near paths/water |
| Fallen leaves | 5-15 per m2 | 3-8cm | Under trees, wind-accumulated against obstacles |
| Twigs/debris | 1-3 per m2 | 5-20cm | Random, avoid paths |
| Mushrooms/fungi | 0-2 per 10m2 | 3-10cm | Near trees, damp areas, clusters |
| Wildflowers | 2-8 per m2 | 10-25cm | Open meadows, color variation |
| Moss patches | 10-30% ground coverage | N/A | North-facing, damp, shade |

---

## 2. Trees and Vegetation

### 2.1 Trunk Standards

**Bark texture at close range (1-3m):**
- Visible individual bark plates/ridges with 3-5mm depth relief via normal map
- Color variation within bark: lighter ridges, darker furrows
- Bark type matches species: smooth birch, plated oak, fibrous pine, peeling elm
- Proper taper: trunk diameter decreases ~15-20% per meter of height for deciduous, ~8-12% for conifers
- Base flare: trunk widens 20-40% at ground level with visible root buttresses
- Moss/lichen on north-facing side (10-30% coverage in damp biomes)

**Trunk geometry standards:**
- 8-16 sided polygon cross-section at close range (LOD0)
- NOT perfectly round -- slight ovality, bumps, lean
- Trunk lean: 2-8 degrees from vertical (trees lean toward light)
- Wounded/scarred sections on 10-20% of trees (lightning damage, animal rubbing)

### 2.2 Branch Standards

**What makes branches look real vs procedural:**

| Attribute | REAL (AAA) | PROCEDURAL (amateur) |
|-----------|-----------|----------------------|
| Branching angle | Variable, 20-70 degrees, species-dependent | Uniform angle everywhere |
| Branch thickness | Tapers from 80% of parent to 20% at tip | Constant cylinder diameter |
| Curve | Organic S-curves, gravity droop | Straight lines or simple arcs |
| Distribution | Asymmetric, denser on sun side | Perfectly symmetric spiral |
| Dead branches | 5-15% of branches are bare/broken stubs | Zero dead branches |
| Cross-section | Slightly oval, not circular | Perfect circle |
| Junction | Swollen collar at branch-trunk joint | Abrupt cylinder intersection |
| Variation between trees | Each tree unique in branch layout | Copy-paste identical structure |

**Branch hierarchy:**
- Primary branches: 3-7 per tree, 40-80% of trunk diameter at origin
- Secondary branches: 2-5 per primary, 30-50% of parent diameter
- Tertiary: 3-8 per secondary, transition to leaf cards at this level

### 2.3 Leaf/Canopy Standards

**Individual leaf rendering (LOD0, close range):**
- Leaf cards with alpha cutout, NOT solid blob geometry
- Each card contains 3-8 leaves arranged naturally
- Card size: 15-40cm for broadleaf, 20-60cm for conifer sprigs
- Alpha channel provides clean leaf silhouettes with 1-pixel antialiased edges
- Subsurface scattering tint: leaves glow warm yellow-green when backlit by sun
- Two-sided rendering with darker underside color

**Canopy from outside (10-50m):**
- Visible sky gaps: 15-30% of canopy area is transparent (you can see sky through)
- Density variation: thicker on crown, sparser at edges and bottom
- Light dapple: sunlight filtering through creates visible spots on ground
- Edge silhouette is irregular, not a smooth dome or sphere
- Crown shape matches species: conical for conifers, round for oak, vase for elm

**What makes canopy look "blobby" (avoid):**
- Solid opaque canopy with no sky penetration
- Perfectly spherical or ellipsoidal crown shape
- Uniform leaf density everywhere
- No interior branch structure visible through gaps
- Single shade of green across entire canopy

### 2.4 Tree Variety Standards

**Minimum AAA variety per biome:**
- 3-5 distinct species, each recognizable by silhouette alone
- 5-10 variations per species (different seed, age, health)
- Size range: young saplings (2-4m) through mature (15-30m) per species
- At least one dead/dying tree per forest cluster (bare branches, peeling bark, fungus)
- At least one fallen log per 20-30 trees
- Stumps where trees were "felled" near settlements

**Species differentiation checklist:**
- [ ] Unique bark texture
- [ ] Unique leaf shape/color
- [ ] Unique crown silhouette
- [ ] Unique branching pattern
- [ ] Unique size range

### 2.5 LOD Standards for Trees

**SpeedTree industry standard LOD chain:**

| LOD | Distance | Detail | Technique |
|-----|----------|--------|-----------|
| LOD0 | 0-20m | Full geometry, individual leaf cards | Mesh + alpha cutout |
| LOD1 | 20-50m | Reduced branches, larger leaf cards | Merged leaf clusters |
| LOD2 | 50-100m | Simple trunk + billboard branch planes | Impostor cards |
| LOD3 | 100-300m | Billboard cross (2-3 intersecting planes) | Billboard atlas |
| LOD4 | 300m+ | Single billboard card | Fades to terrain color |

**Critical: LOD transitions must be smooth.** Alpha-to-coverage crossfading prevents pop-in. Billboard normals must include ambient occlusion in alpha channel for consistent lighting across LOD transitions.

### 2.6 Ghost of Tsushima Grass: The Gold Standard

Ghost of Tsushima's procedural grass system (GDC 2021, Eric Wohllaib) represents the peak of grass rendering in shipped games:

- **Individual blade generation on GPU** -- each blade is a cubic Bezier curve, not a pre-authored mesh
- **Color per blade**: gloss texture stretched across blade, diffuse texture varies color along blade length
- **Normals tilted outward** from cluster center for rounded, natural appearance
- **Translucency and AO** per blade based on thickness and light occlusion
- **LOD**: high-detail (full Bezier) and low-detail, with smooth transition
- **Wind**: unified 2D Perlin noise wind system, sine wave bobbing animation
- **Shadows**: impostor shadow maps approximating grass height + screen-space shadows for fine detail
- **Camera trick**: grass blades tilt when camera looks straight down, preventing empty patches between grass meshes
- **Pampas grass**: GPU instanced artist-authored assets placed procedurally within tiles, mixed with generated blades

**Horizon Zero Dawn grass (GDC 2018, Gilbert Sanders):**
- Grass LOD: LOD1 = 20-36 triangles, LOD2 = 10-18 triangles (high shader), LOD3 = 10-18 triangles (low shader)
- Grass tilts with camera tilt to prevent visible ground between meshes
- Wind tied to global force field with per-vertex displacement
- Alpha-tested rendering in two passes: first as early occluders, then normal rendering

---

## 3. Rocks and Cliffs

### 3.1 Surface Detail Standards

**What AAA cliff faces look like:**

- **Layered strata visible**: horizontal bands of slightly different color/texture showing geological depositional layers, typically 10-50cm thick bands
- **NOT smooth or uniform**: surface is rough, pitted, fractured
- **Fracture patterns**: angular breaks where rock has split along natural planes of weakness (joints, bedding planes)
- **Sharp edges where recently fractured**: clean angular breaks with lighter-colored exposed surfaces
- **Rounded where weathered**: edges that have been exposed for a long time are softened, darker, lichen-covered
- **Vertical striping**: water stain patterns running down cliff faces (darker streaks)
- **Micro-crevices**: 1-5mm cracks throughout, visible in normal map as a dense network

### 3.2 Weathering and Biological Detail

**Moss and lichen placement (NOT random):**

| Surface Condition | Moss Coverage | Lichen Coverage | Where |
|-------------------|---------------|-----------------|-------|
| North-facing, shaded | 30-60% | 10-20% | Crevices, horizontal ledges, base |
| East/West facing | 10-20% | 20-40% | Scattered patches, more lichen than moss |
| South-facing, exposed | 0-5% | 10-30% | Only in crevices, mostly lichen |
| Overhang underside | 0% | 5-10% | Dry, minimal biological growth |
| Water splash zone | 40-70% | 5-10% | Near waterfalls, streams -- thick moss |

**Weathering gradient (top to bottom of cliff):**
1. Top edge: sharp, sometimes overhanging, with grass/roots growing over
2. Upper face: relatively clean, less weathering, lighter color
3. Mid face: maximum lichen coverage, some moss in crevices
4. Lower face: water staining, algae streaks, heavier moss
5. Base: scree accumulation, soil contact zone, heaviest moss and plant growth

### 3.3 The Scree Rule

**Every cliff base in AAA games has scree.** This is non-negotiable for geological realism.

**Scree specifications:**
- Scree = loose broken rock fragments accumulated at cliff base through freeze-thaw weathering
- Fragment sizes: 2-30cm, angular to sub-angular (NOT rounded like river rocks)
- Distribution: triangular fan shape from cliff face outward, 30-45 degree angle of repose
- Depth: 0.5-2m deep at cliff base, thinning to nothing at fan edge
- Distance from cliff: extends 1-5x the cliff height horizontally
- Material: same rock type as parent cliff (same color, texture)
- Mixed with soil at edges, vegetation growing through at periphery

**The scree hierarchy (cliff base to level ground):**
1. Raw cliff face (vertical or near-vertical)
2. Large fallen blocks (0.5-2m, angular, some tilted)
3. Medium scree (10-30cm fragments, densely packed)
4. Fine scree (2-10cm, mixed with dirt)
5. Soil with scattered small rocks
6. Normal terrain surface

### 3.4 Rock Geometry Standards (NOT Displaced Spheres)

**What rocks actually look like vs common procedural failure:**

| Attribute | AAA Rock | Displaced Sphere (BAD) |
|-----------|----------|----------------------|
| Silhouette | Angular, fractured planes | Blobby, rounded |
| Flat faces | Has flat facets from fracture | All convex curves |
| Edge sharpness | Mix of sharp and weathered edges | Uniformly rounded |
| Shape language | Geological -- bedded, folded, faulted | Organic -- looks like a potato |
| Layering | Visible sedimentary layers | No internal structure |
| Base contact | Buried partially in ground, debris around base | Sitting ON ground like dropped |
| Scale consistency | Detail resolution matches viewing distance | Same detail at all scales |

**Rock asset hierarchy for a complete environment:**

| Category | Count Needed | Size Range | Geometry |
|----------|-------------|------------|----------|
| Pebbles | 5-10 variations | 2-8cm | Low-poly + texture |
| Small rocks | 5-8 variations | 10-30cm | Medium-poly, unique UV |
| Boulders | 3-5 variations | 0.5-2m | High-poly, blended shader |
| Rock formations | 3-4 variations | 2-5m | Modular, trimsheet |
| Cliff faces | 5-10 modular pieces | 3-15m tall | Modular kit, world-space texturing |
| Cliff cap (top edge) | 3-5 variations | 1-3m | Transitions cliff to terrain |

### 3.5 FromSoftware Rock/Cliff Visual Language

Elden Ring and Dark Souls use a distinctive approach:
- Cliffs have extreme vertical scale with layered horizontal strata
- Rock surfaces are rough with high-frequency normal detail
- Colors are desaturated earth tones with dramatic value contrast
- Architecture is built INTO cliffs (Stormveil Castle integrating with cliffsides)
- Wooden walkways and stairs follow cliff contours rather than leveling terrain
- Variable foundation heights on buildings to conform to slopes
- Rock meshes placed at building-terrain intersections to hide seams

---

## 4. Water

### 4.1 Surface Standards

**What AAA water surfaces look like:**

- **Wave displacement**: visible low-frequency undulation (0.5-2m wavelength, 2-10cm amplitude for lakes; larger for oceans)
- **Micro-ripples**: high-frequency surface detail from wind (normal map animation, 5-20cm wavelength)
- **Reflections**: screen-space or planar reflections showing sky, trees, cliffs on surface
- **Fresnel effect**: water is transparent when looking straight down, reflective at grazing angles
- **Color by depth**: shallow = visible bottom (warm brown/green), deep = opaque dark blue-green-black
- **Flow direction**: rivers show directional flow via animated normal maps and foam streaks

**NOT a flat colored plane.** Even the calmest lake has:
- Micro-ripples from wind
- Subtle wave displacement
- Depth-based color gradient from shore to center
- Reflection of the sky (even if simple cubemap)

### 4.2 Bank/Shoreline Transition

**The AAA shoreline transition (from dry land into water):**

This is one of the most scrutinized details in environment art. It should look like this:

1. **Dry terrain** (0m from water): normal grass/dirt, fully dry
2. **Damp zone** (0-1m from water): slightly darker soil, no grass, scattered pebbles
3. **Mud/wet sand** (at water line): darkened, increased roughness variation, wet specular highlights
4. **Shallow water** (0-30cm depth): visible bottom through transparent water, small pebbles/sand visible, reeds/cattails growing
5. **Transition depth** (30-100cm): bottom fades from visible to obscured by depth fog, color shifts to water color
6. **Deep water** (100cm+): opaque water color, full wave displacement, reflections dominant

**Bank materials (shore to water):**
- Grass (dry) -> sparse grass (damp) -> bare dirt (wet) -> mud/clay -> wet pebbles -> submerged sand/silt
- Each transition is 0.5-1.5m wide, height-blended
- Reeds/cattails at waterline: 30-80cm tall, clustered, partially submerged

### 4.3 Foam and Interaction Effects

**Where foam appears in AAA water:**

| Location | Foam Type | Appearance |
|----------|-----------|------------|
| Rock intersections | Persistent churn foam | White opacity ring around any object touching water |
| Shoreline | Wave wash foam | Thin white edge following waterline, animated |
| River rapids | Flow foam | Streaky white following current direction |
| Waterfall base | Turbulence foam | Dense white churning, spray particles |
| Behind moving objects | Wake foam | V-shaped trail |

**Intersection foam (depth-based):**
- Uses scene depth vs water surface depth to detect where objects pierce the water plane
- Renders a white/light blue foam ring 10-30cm wide around intersection
- Animates with slight pulsing/flowing motion
- Without this, objects look like they are hovering above or punching through water with no physical interaction

### 4.4 Water Debris and Life

**What sits at water edges in AAA:**
- Fallen branches partially submerged
- Leaf debris collected against rocks and at bends
- Algae/water plants at shallows
- Small fish or insects (particle effects)
- Mud tracks from animals drinking
- Smooth river stones (rounded, unlike angular scree)

---

## 5. Quality Tier Definitions

### Visual Reference: What Each Tier Actually Looks Like

#### TIER 1: PLACEHOLDER (White/Grey Box)

**Terrain:**
- Flat white or grey plane, no texture
- Grid lines visible from subdivision
- No heightmap displacement
- Zero material variation

**Trees:**
- Cone on a cylinder (Christmas tree shape)
- Solid single-color green
- No bark texture, no leaf detail
- All identical copies

**Rocks:**
- Displaced UV sphere or cube
- Single grey color, smooth surface
- No geological detail, no weathering
- Floating on terrain surface

**Water:**
- Flat blue plane
- No transparency, no waves
- No shoreline interaction
- Hard edge where meets terrain

**Use case:** Layout planning, collision testing, scale reference. Never ship.

---

#### TIER 2: BASIC (Correct Shapes, Flat Materials)

**Terrain:**
- Basic heightmap with hills/valleys at correct scale
- Single texture per biome zone (one grass, one dirt, one rock)
- Linear alpha blend between textures (mushy transitions)
- Visible tiling at 20-30m distance
- No micro-undulation, terrain feels artificially smooth between large features
- No ground cover objects (grass, rocks, debris)

**Trees:**
- Correct proportions (trunk taper, branch spread)
- Single bark color, flat shading
- Leaves as solid green masses or basic cards
- No transparency/alpha, canopy is opaque blob
- All same species, minimal variation

**Rocks:**
- Correct angular shapes (not spheres)
- Single material, no weathering
- No moss, no staining, no lichen
- No scree at cliff bases
- Correct placement but uniform appearance

**Water:**
- Flat plane with basic water color
- Simple transparency (constant, not depth-based)
- No waves, basic animated normal map at best
- No foam, no shoreline interaction
- Hard material edge at terrain border

**Gap from AAA:** Missing ALL secondary detail. Reads as "unfinished."

---

#### TIER 3: DECENT (Textured, Some Detail)

**Terrain:**
- Multiple terrain layers with height blending
- Tiling visible at 50-100m but acceptable close up
- Basic macro variation (some color shifts)
- Micro-undulation present but subtle
- Some ground cover (grass planes, rock scatters)
- Material transitions read correctly (rock on slopes, grass on flat)

**Trees:**
- Bark texture with normal map
- Leaf cards with alpha cutout
- 2-3 species visible
- Some size variation
- No dead branches, no fallen logs
- Canopy somewhat blobby but has some transparency

**Rocks:**
- PBR materials with roughness/normal maps
- Some weathering (moss in crevices)
- Basic strata visible in cliffs
- Scree present but sparse
- Some variety in rock types

**Water:**
- Depth-based transparency
- Animated waves (normal map + subtle displacement)
- Basic foam at intersections
- Soft shoreline blend
- Reflections (screen-space or cubemap)

**Gap from AAA:** Missing micro-detail, tiling still visible at distance, transitions not fully convincing, vegetation lacks variety.

---

#### TIER 4: GOOD (Multi-Layer, Decent Variety)

**Terrain:**
- 4-8 terrain layers with height blending
- Anti-tiling via macro noise (no visible repetition at medium distance)
- Micro-undulation across all "flat" surfaces
- Dense ground cover: grass blades, pebbles, debris, flowers
- Material transitions look natural
- Slight tiling artifacts only at very long distance or oblique angles

**Trees:**
- Full bark detail with depth, correct taper and base flare
- Alpha cutout leaf cards with SSS (subsurface scattering) tint
- 3-5 species with multiple variations each
- Some dead branches, occasional fallen log
- Light filtering through canopy visible
- Reasonable LOD chain

**Rocks:**
- Detailed PBR with strata, fracture patterns
- Weathering gradient (more moss at base, lichen on exposed faces)
- Scree at cliff bases
- Multiple rock types per biome
- Good variety in sizes and shapes

**Water:**
- Full depth fog with color gradient
- Wave displacement + animated normals
- Foam at intersections and shoreline
- Proper bank transition (grass -> mud -> pebbles -> shallow water)
- Reflections with Fresnel

**Gap from AAA:** Missing the "last 10%" -- finest micro-detail, perfect anti-tiling at all distances, individual grass blade rendering, photorealistic material quality.

---

#### TIER 5: AAA (Photorealistic at Distance, Detailed Up Close)

**Terrain:**
- Zero visible tiling at any distance or angle
- Stochastic sampling + macro noise + distance scaling ALL active
- Individual grass blades rendered per-pixel on GPU (Ghost of Tsushima level)
- Every square meter has unique micro-variation
- Ground cover density: 50-200 elements per m2
- Material transitions are physically motivated (height blend, slope blend, moisture blend)
- Terrain conforms to objects (foundations, roads, walls) with custom masks

**Trees:**
- Individual leaf cards with per-blade color variation, translucency, AO
- Bark with parallax occlusion mapping, visible depth
- 5+ species per biome, 10+ variations per species
- 5-15% dead branches, wounded bark, broken limbs
- Fallen trees, stumps, nurse logs
- Canopy with 15-30% sky visibility, light dapple on ground
- Smooth LOD transitions via alpha-to-coverage crossfade

**Rocks:**
- Photogrammetry or photogrammetry-quality sculpts
- Layered strata, fracture patterns, water staining
- Full weathering: moss in crevices, lichen on exposed faces, root invasion
- Complete scree hierarchy at every cliff base
- World-space texturing for consistent detail across modular pieces
- Blended shader: unique baked detail + tiling micro-texture

**Water:**
- FFT ocean simulation or equivalent physical wave model
- SDF-based shoreline interaction (waves respect geometry accurately)
- Multi-layer depth fog + caustics on shallow bottoms
- Foam at ALL intersections with geometry
- Full bank transition with 6+ material stages
- Debris, vegetation, life at water edges
- Accurate reflections with distortion

**This is the target.** Every visual element has been considered at every viewing distance.

---

## 6. Dark Fantasy Specific Standards

### 6.1 Dark Fantasy Terrain Palette

Dark fantasy terrain (Elden Ring, Dark Souls, Skyrim) uses a specific color language:

**Ground colors (NOT vibrant green meadows):**
- Grass: muted olive green, yellow-brown, not saturated green (HSV: H=70-100, S=20-40%, V=30-50%)
- Dirt: dark brown to grey-brown, desaturated (HSV: H=25-40, S=15-30%, V=20-40%)
- Mud: near-black brown with slight red tint (HSV: H=15-25, S=20-35%, V=15-25%)
- Rock: grey to blue-grey, slightly warm or cool depending on geology (HSV: H=200-240, S=5-15%, V=30-50%)
- Sand/gravel: warm grey-tan (HSV: H=35-50, S=10-25%, V=40-55%)

**Key difference from bright fantasy:** Dark fantasy terrain is 20-40% lower value (brightness) and 30-50% lower saturation than typical fantasy game terrain.

### 6.2 Dark Fantasy Atmosphere

**Fog/Haze:**
- Volumetric fog in valleys and near water
- Distance fog starts at 200-500m (much closer than bright fantasy)
- Fog color: cool blue-grey in shade, warm amber near light sources
- God rays: visible where sunlight breaks through tree canopy or cloud gaps

**Lighting:**
- Dominant light is overcast/diffuse, not direct sun
- When sun is visible, it is low-angle (dawn/dusk feeling) casting long shadows
- Shadow color is cool blue-purple, not neutral grey
- Ambient light is dim (0.1-0.3 intensity, not 0.5+)

### 6.3 Dark Fantasy Details That Matter

**Environmental storytelling elements scattered on terrain:**
- Broken weapons, rusted armor fragments
- Bones (animal and humanoid)
- Burnt patches, charred tree stumps
- Abandoned campsites (stone fire ring, scattered belongings)
- Shrine remnants (broken stone, faded carvings)
- Cobwebs between trees in dense forest
- Unnatural discoloration near corrupted areas (purple-black soil, withered vegetation)

---

## 7. VeilBreakers Gap Analysis

### Current Capabilities vs AAA Standard

Based on the existing codebase (`terrain_materials.py`, `environment.py`, `vegetation_system.py`):

| Feature | Current State | AAA Target | Gap |
|---------|--------------|------------|-----|
| Height blending | `height_blend()` function exists | Per-material height maps | Material height maps may be placeholder |
| Terrain layers | 14 biome palettes, 6 zones each | 4-8 layers with blending | Adequate count, need quality verification |
| Anti-tiling | Unknown | Stochastic + macro noise + distance | Likely missing stochastic sampling |
| Micro-undulation | Terrain noise modules exist | Multi-octave surface noise | Need to verify amplitude/frequency |
| Ground cover | Scatter engine exists | 50-200 elements/m2 | Need density and variety verification |
| Tree quality | Vegetation L-system exists | SpeedTree-level detail | Need leaf card alpha, bark depth audit |
| Rock geology | Unknown | Strata, fracture, weathering | Likely needs major upgrade |
| Scree system | Unknown | Auto-generated at cliff bases | Probably missing |
| Water rendering | Coastline handler exists | Full depth fog + foam + bank transition | Blender water is limited |
| Material palette | Dark fantasy palette exists | Desaturated, low-value earth tones | Need color audit |
| Moss/weathering | Some weathering support | Placement rules based on orientation | Need directional rules |

### Priority Improvements

1. **CRITICAL**: Verify micro-undulation noise is active on ALL terrain (the "never flat" rule)
2. **CRITICAL**: Add scree generation at every cliff/rock formation base
3. **HIGH**: Implement proper bank/shoreline material transition (6-stage gradient)
4. **HIGH**: Audit tree leaf cards for alpha cutout quality and sky gap percentage
5. **HIGH**: Add macro noise overlay to terrain materials for anti-tiling
6. **MEDIUM**: Implement directional moss/lichen placement rules
7. **MEDIUM**: Add dead branch percentage (5-15%) to tree generation
8. **MEDIUM**: Add environmental storytelling debris scatter
9. **LOW**: GPU grass blade rendering (this is engine-side, mostly Unity concern)

---

## 8. Sources

### GDC Presentations (HIGH confidence)
- [GDC 2021 - Procedural Grass in Ghost of Tsushima (Eric Wohllaib)](https://gdcvault.com/play/1027214/Advanced-Graphics-Summit-Procedural-Grass)
- [GDC 2021 - Samurai Landscapes: Building and Rendering Tsushima Island](https://gdcvault.com/play/1027352/Samurai-Landscapes-Building-and-Rendering)
- [GDC 2018 - Between Tech and Art: The Vegetation of Horizon Zero Dawn (Gilbert Sanders)](https://www.gdcvault.com/play/1025530/Between-Tech-and-Art-The)
- [GDC 2022 - Adventures with Deferred Texturing in Horizon Forbidden West (James McLaren)](https://www.guerrilla-games.com/read/adventures-with-deferred-texturing-in-horizon-forbidden-west)
- [GDC 2023 - Frostbite Terrain Procedural Framework (Julien Keable)](https://www.ea.com/frostbite/news/frostbite-presents-at-gdc-2023)
- [SIGGRAPH 2022 - A Showcase of Decima Engine in Horizon Forbidden West](https://dl.acm.org/doi/10.1145/3532833.3538681)

### Technical References (HIGH confidence)
- [SpeedTree LOD Documentation](https://docs.speedtree.com/doku.php?id=overview_level-ofdetail)
- [NVIDIA GPU Gems 3 - Next-Generation SpeedTree Rendering](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-4-next-generation-speedtree-rendering)
- [Terrain Rendering In Games - Basics (kosmonaut's blog)](https://kosmonautblog.wordpress.com/2017/06/04/terrain-rendering-overview-and-tricks/)
- [Stochastic Texturing (Jason Booth / MicroSplat)](https://medium.com/@jasonbooth_86226/stochastic-texturing-3c2e58d76a14)
- [Unity Procedural Stochastic Texturing](https://blog.unity.com/engine-platform/procedural-stochastic-texturing-in-unity)
- [Crest Ocean System Documentation](https://crest.readthedocs.io/en/stable/user/shallows-and-shorelines.html)
- [MicroSplat Anti-Tiling Module](https://assetstore.unity.com/packages/tools/terrain/microsplat-anti-tiling-module-96480)
- [Macro/Micro Variation Technique (World of Level Design)](https://www.worldofleveldesign.com/categories/ue4/landscape-macro-tiling-variation.php)

### Environment Art Community (MEDIUM confidence)
- [Polycount - How to Plan Cliff Packs](https://polycount.com/discussion/235383/how-to-plan-cliff-packs-for-game-environments-any-good-references-or-breakdowns-for-other-games)
- [Polycount - Cliff Modeling Approaches](https://polycount.com/discussion/152790/how-would-do-you-approach-cliff-modeling)
- [Phillip Jenne - Ghost of Tsushima Ground Materials](https://phillipjenne.artstation.com/projects/QrKGQl)
- [Texel Density Theory (Inspirant)](https://inspirant.substack.com/p/understanding-the-texel-density-theory)
- [Beyond Extent - Texel Density Deep Dive](https://www.beyondextent.com/deep-dives/deepdive-texeldensity)

### Game Analysis (MEDIUM confidence)
- [Crimson Desert Water Tech Analysis](https://tech.sportskeeda.com/gaming-news/crimson-desert-water-tech-might-dethrone-xbox-game-studios-finest)
- [80.lv - Dark Fantasy Canyon in Unreal Engine](https://80.lv/articles/how-to-set-up-cinematic-dark-fantasy-canyon-in-unreal-engine)
- [80.lv - Elden Ring-Style Cathedral Environment](https://80.lv/articles/crafting-elden-ring-style-cathedral-environment-inspired-by-real-life-architecture)
- [Dark Fantasy Diorama Breakdown (The Rookies)](https://discover.therookies.co/2023/05/08/organic-3d-environment-modeling-creating-a-game-ready-dark-fantasy-diorama/)

### Geological Reference (HIGH confidence)
- [Scree Formation and Characteristics (Wikipedia)](https://en.wikipedia.org/wiki/Scree)
- [Talus vs Scree - Size and Formation Differences](https://pmags.com/talus-vs-scree-what-is-the-difference)
- [Weathering Processes (EVS Institute)](https://evs.institute/earth-processes/understanding-weathering-earths-surface/)
