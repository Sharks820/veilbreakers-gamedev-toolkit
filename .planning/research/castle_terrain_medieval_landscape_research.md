# Castle Terrain Integration & Medieval Landscape Generation Research

Research for VeilBreakers dark fantasy RPG terrain and castle placement systems.

---

## SECTION 1: CASTLE-TERRAIN INTEGRATION

### 1. How Real Castles Shape Terrain

#### Motte-and-Bailey Construction
- **Motte**: Artificial earth mound created by piling consecutive layers of earth and stones, then compacting them
- **Typical motte height**: 3m to 30m (10-100 ft); most commonly 4.5-9m (15-30 ft)
- **Motte diameter**: 25-100m (80-330 ft)
- **Height distribution (England/Wales survey of 600+ sites)**:
  - 69% were less than 5m (16 ft) tall
  - 24% were between 5-10m (16-33 ft)
  - Only 7% exceeded 10m (33 ft)
- **Minimum academic threshold**: Mounds under 3m (9.8 ft) are excluded from motte classification
- **Bailey**: Enclosed courtyard at motte base, shape adapted to local terrain
- Construction speed: Could be built in several weeks using timber (vs months/years for stone)

#### Rock-Cut Ditches and Moats
- **Ditch/Fosse**: Common defense dug around exterior walls; excavated earth used to create banks
- **Moat dimensions**: Typically 3-5m deep, up to 15m wide
- **Wet moat minimum**: Only 0.5m water depth needed to obstruct attackers and make them vulnerable to missile fire
- **Dry moats**: Steep-sided ditches, sometimes riveted with wooden stakes for slipperiness
- Stakes placed in ditch bottom to further impede crossing

#### Glacis
- Sloped earth bank at wall base, constructed from earth excavated from the ditch
- Purpose: deflect projectiles, make wall-scaling harder, prevent siege towers from reaching walls
- Angle: typically 30-45 degrees from horizontal
- Material: compacted earth, sometimes faced with stone or turf

#### Scarping
- Cutting natural rock/hillside to make it steeper and less climbable
- Could produce a motte without needing an artificial mound if natural hill was suitable
- Common on rocky sites where the existing geology could be exploited

#### Counterscarp
- Outer slope/edge of the ditch/moat
- Sometimes faced with stone masonry to prevent collapse and make climbing out harder
- Creates a secondary obstacle after crossing the ditch

#### Terracing
- Multiple defense levels created by cutting horizontal platforms into hillsides
- Each level served different military and domestic functions
- Retaining walls built from local stone to hold each terrace level

### 2. Terrain Types That Castles Exploit

#### Rocky Promontory / Headland (3 sides naturally defended)
- **Example**: Chateau de Walzin -- steep rocky promontory rising 50+ metres above the Lesse river
- Built where a tight river bend sets the castle in a dramatic vertical site
- Natural topography serves as a natural rampart on three sides
- Only one approach requires artificial fortification
- **Castle plan effect**: Long, narrow layout following the ridge; gatehouse on the landward side; minimal wall needed on cliff sides

#### River Meander (water on 3 sides)
- **Example**: Durham Castle -- built on a tight river bend
- River provides free natural defense plus guaranteed water supply
- **Castle plan effect**: Roughly peninsular layout; main gate and heaviest fortification on the neck of land; potential for water-filled moat connecting river on both sides

#### Hill Summit (360-degree visibility)
- Commanding views in all directions for early warning
- Attackers must fight uphill from every direction
- **Castle plan effect**: Concentric rings of walls (inner and outer curtain); keep at highest point; round or roughly circular layout following hilltop contours; wide baileys possible if summit is flat

#### Mountain Spur (approach from one direction only)
- **Example**: Burg Eltz -- built on a rocky spur above the Moselle River
- Steep drops on three sides; single ridge connecting to mountain
- **Castle plan effect**: Elongated layout along the spur; heaviest fortification at the ridge junction; gatehouse with drawbridge cutting the ridge; thin walls on cliff sides (natural defense); towers at narrow points

#### Island in Lake/River
- Complete water barrier; attackers must use boats
- **Castle plan effect**: Compact layout filling available island area; dock/water gate for supply; causeway or bridge as single entry point; walls following island perimeter

#### Cliff Edge
- **Example**: Many German castles built on cliff edges or rocky outcrops
- Sheer drop eliminates attack from one direction entirely
- **Castle plan effect**: Linear layout along cliff edge; main buildings enjoy the view/defense of the cliff side; all fortification effort focused on landward approaches

### 3. Terrain Modification for Castle Construction

#### Leveling a Hilltop for the Bailey
- Soil tamped down using pickaxes, mattocks, wooden shovels
- Earth moved to fill depressions and create level ground
- Excess earth used to build up ramparts or fill moats
- Large flat areas needed for: garrison buildings, stables, workshops, kitchens, wells

#### Creating Approach Ramps / Switchback Roads
- Castle approach roads deliberately designed to expose attackers:
  - Right-hand side exposed to wall (shield on left arm gives no protection)
  - Sharp turns prevent battering rams being carried at speed
  - Multiple gates at turns for layered defense
- Switchback roads on steep terrain: typically 2-3m wide, with retaining walls on downhill side
- Gradients kept manageable for horse-drawn carts (roughly 1:7 to 1:10)

#### Retaining Walls on Slopes
- Built on top of trenches filled with rubble and mortar mixture
- Space between retaining walls filled with more rubble and mortar
- Dry stone construction commonly used for agricultural terracing
- **Talus walls**: Inwardly sloping fortified walls, especially common in Crusader constructions
- Batter (inward slope) at wall base: typically 10-15 degrees, adds stability and deflects projectiles

#### Drainage Channels
- Critical to prevent foundation undermining by water
- Channels cut into rock or lined with stone to direct rainwater away from walls
- Garderobe chutes also served as drainage
- Some castles had sophisticated cistern systems

#### Foundation Types
- **Rock foundations**: Preferred; walls built directly on bedrock where available
- **Earth foundations**: Rubble-filled trenches when bedrock too deep; compacted layers
- Foundation depth: typically 1-2m below ground level
- Wall thickness at foundation: often 2-4m for curtain walls, up to 5m for keeps

---

## SECTION 2: ADVANCED TERRAIN GENERATION TECHNIQUES

### 4. Terrain Features for Dark Fantasy

#### Dramatic Cliff Faces with Exposed Rock Strata
- Height-based terrain (heightmaps) cannot produce true vertical/overhanging cliffs
- **Solution**: Use density fields / voxel terrain where each block has its own density value
- Blocks placed where density is positive; enables sheer cliffs, overhangs, floating islands
- Layer different noise frequencies to create visible rock strata bands
- Horizontal stripe patterns using altitude-based material assignment

#### Deep Ravines with Bridges
- Carve ravines by subtracting elongated noise volumes from terrain
- Follow fractal river paths for natural-looking courses
- Width: 10-50m across for dramatic effect; depth: 20-100m
- Bridge placement at narrowest points (natural crossing locations)

#### Rocky Outcrops Jutting from Hillsides
- Overlay high-frequency noise on slopes above certain steepness threshold
- Use erosion-resistant "hard rock" layers that protrude after softer material erodes
- Size: 2-10m individual outcrops; clusters of 3-7 for natural grouping

#### Cave Entrances in Cliff Faces
- Boolean subtraction of spherical/tubular volumes from cliff geometry
- Place at geological layer boundaries (where hard rock meets soft)
- Typical entrance: 2-5m wide, 2-4m tall for playable spaces

#### Waterfalls
- Place where rivers meet cliff edges or significant elevation drops
- Plunge pool at base (carved depression from water impact)
- Spray mist particle effects; wet/dark rock textures on surrounding cliff face
- Width: 2-20m; height: 10-50m for dramatic effect

#### Ancient Ruined Walls Partially Buried
- Place wall segments along terrain surface with partial submersion (30-60% buried)
- Broken tops with irregular profiles
- Moss/vegetation growth on exposed portions
- Rubble scatter at base following terrain slope

#### Paths Carved into Mountainsides
- Cut horizontal channels into steep terrain with slight grade
- Inner wall (cliff side) rises vertically; outer edge has low wall or drops off
- Width: 1.5-3m for foot/horse paths
- Switchbacks at 15-20m intervals on steep faces

#### Natural Arches and Rock Formations
- Form from differential erosion of layered rock
- Span: 5-30m for dramatic game-scale arches
- Place at coastal cliffs or canyon walls where wave/water erosion is plausible

### 5. Terrain-to-Building Transitions

#### Buildings on Sloped Terrain (Stepped Foundations)
- **Split-level construction**: Front of building at one ground level, rear at another
- Foundation steps follow terrain contour at 0.5-1m increments
- Exposed foundation stone visible on downhill side
- Cellars/undercrofts naturally formed by slope difference

#### Retaining Walls Where Buildings Meet Hillsides
- Stone or dry-stone walls holding back earth behind buildings
- Height: 1-4m depending on slope
- Drainage holes (weep holes) at base to prevent water buildup
- Vegetation growing from cracks adds age/atmosphere

#### Stairs Connecting Elevation Levels
- **Stone steps**: 15-20cm rise, 25-30cm tread depth
- **Wooden stairs**: Steeper (20-25cm rise), often with railings
- Width: 1-2m for public stairs; 0.7-1m for private
- Landings every 10-15 steps for rest and direction changes
- In dark fantasy: crumbling edges, missing steps, worn centers

#### Terraced Gardens on Slopes
- Level platforms 3-5m deep, retained by 1-2m stone walls
- Planted with herbs, vegetables, or ornamental gardens
- Stairs or ramps connecting levels
- Drainage channels behind retaining walls

#### Roads Handling Elevation Changes
- **Switchbacks**: 180-degree turns with 3-5m turning radius
- **Ramps**: Maximum practical gradient 1:7 for carts; 1:4 for foot traffic
- **Retaining walls**: Stone-faced on downhill side of mountain roads
- **Cobblestone**: Essential on steep grades to prevent erosion and provide traction

#### Bridge Placement
- Span ravines at narrowest point (structural efficiency + historical accuracy)
- Stone arch bridges: span up to 30m per arch; multiple arches for wider crossings
- Wooden bridges: span up to 15m; require more frequent replacement
- Rope/chain bridges: span up to 50m; sway for atmospheric effect
- Abutments anchored into rock on both sides

### 6. Erosion and Weathering on Terrain

#### Water Erosion Channels
- **Hydraulic erosion**: Most significant terrain shaping force
- Simulated by particle-based water flow: droplets pick up sediment, deposit downstream
- Creates V-shaped valleys, gullies, alluvial fans
- GPU-accelerated erosion can process thousands of calculations simultaneously
- Fractal branching patterns from ridgeline to valley floor

#### Exposed Rock on Steep Slopes
- Soil slides off slopes above ~35 degrees, exposing bedrock
- Material assignment: use slope angle to blend between soil/grass and rock textures
- Vertical faces get cliff/rock material; horizontal gets soil/vegetation

#### Talus/Scree at Cliff Bases
- **Thermal erosion**: Simulates rock fracturing from temperature cycling
- Talus angle: typically 30-37 degrees (angle of repose for broken rock)
- Cone-shaped accumulations at base of cliffs
- Particle size gradient: larger blocks at base, finer material at top
- Simulated via static cascade method where sediment reaches maximum stable angle

#### Soil Creep Patterns
- Slow downhill movement of soil on moderate slopes
- Creates characteristic curved tree trunks (pistol-butt trees)
- Terracette formations: small step-like ridges on grass slopes
- Fence posts/walls gradually tilting downhill

#### Tree Line Effects
- Elevation-based: trees thin and shrink approaching mountain summits
- Wind-exposed ridges: stunted, wind-flagged trees (krummholz)
- Aspect-dependent: different vegetation on sun-facing vs shade-facing slopes
- In dark fantasy: dead tree line around corrupted zones; twisted/blackened trees at boundary

#### Dark Fantasy Terrain Corruption Effects
- **Dead zones**: Barren earth, cracked soil, no vegetation; air "thick with the stench of rot and decay"
- **Crystal formations**: Geometric crystalline structures erupting from ground; individual crystals reaching several meters; faceted surfaces with light refraction; razor-sharp edges
- **Void rifts**: Cracks in terrain revealing darkness/energy beneath; floating fragments of torn earth
- **Corrupted vegetation**: Gnarled, threatening tree shapes; twisted branches reaching skyward; bioluminescent fungal growths
- **Color shifting**: Desaturated palette transitioning to sickly purples/greens at corruption center
- **Terrain deformation**: Ground buckled upward or sunken; impossible angles; gravity-defying floating chunks
- Red flowers/bioluminescence as "beacons of hope" contrast elements

---

## SECTION 3: MEDIEVAL ROAD AND PATH SYSTEMS

### 7. Road Types and Dimensions

#### King's Road / Royal Highway (Via Regia)
- **Width specification** (Laws of Henry I, 1114-1118):
  - Wide enough for two wagons to pass (~20 feet / 6m)
  - Two ox-drivers should touch tips of their goads held at full length across the way
  - Theoretical maximum: 16 armed knights riding side by side (~80 feet / 24m)
  - Practical width: 4-6m for the roadbed; cleared area much wider
- **Statute of Winchester 1285**: 200-foot (60m) strip cleared on either side through forest/heathland (to prevent ambush)
- Surface: Packed earth, sometimes with gravel or cobblestone in towns
- Best-maintained roads in the kingdom; primarily for military and trade use
- Emblematic of royal authority; pivotal for administrative control, trade, and defense

#### Town Street
- Width: 3-4m typical
- Surface: Cobblestone in wealthy areas; packed earth elsewhere
- Central drainage channel (kennel/gutter) running down middle
- Market squares: widened sections 20-40m across

#### Village Lane
- Width: 2-3m
- Surface: Packed earth, often muddy
- Bordered by hedgerows or low walls
- Connects houses to fields, church, and main road

#### Forest Path / Packhorse Trail
- Width: 1-2m
- Surface: Bare earth, leaf litter, exposed roots
- Winding paths following contours to avoid steep grades
- Crucial for transporting goods across difficult terrain via pack animals

#### Mountain Trail
- Width: 1m or less
- Switchbacks on steep faces
- Sometimes carved into rock face
- Steps cut into steepest sections

#### Causeways
- Raised roads built over bogs and marshlands
- Constructed from logs, fascines (bundled sticks), and earth fill
- Width: 2-3m; raised 0.5-1m above waterlogged ground

#### Typical Travel Distance
- Medieval "journey" = approximately 20 miles (32 km) per day on foot
- Mounted travel: 30-40 miles per day
- Cart travel: 10-15 miles per day

### 8. Road Features

#### Milestones
- Stone markers indicating distance to nearest town/city
- Roman milestones reused where available
- Height: 0.5-1.5m; typically rough-hewn stone with carved numerals

#### Wayside Shrines and Crosses
- Erected at dangerous locations (accident sites, cliff edges, river crossings)
- Placed at crossroads for spiritual protection
- **Eleanor Crosses** (1290s): Grand memorial crosses marking nightly resting places of a royal funeral procession -- the most elaborate examples
- Small stone or wooden structures with religious imagery
- Offered travelers a place to rest, pray, and make offerings for safe journey
- Common in mountainous regions (e.g., Carinthia) at crossroads

#### Bridges
- **Stone arch bridges**: Most durable; span up to 30m per arch; multiple arches for rivers
  - Initially wooden piles, later rebuilt in stone
  - Construction: keystone arch method; centring (wooden support during construction)
- **Wooden plank bridges**: Simpler construction; span to 15m; require regular maintenance
- **Rope/chain bridges**: For mountain crossings; span to 50m
- Strategic nodes receiving extra maintenance funding from local councils

#### Fords (Shallow River Crossings)
- Natural shallow points in rivers where crossing was possible
- Maintained by local communities
- Subject to flooding disruption
- Often marked with posts or stone markers
- Frequently the reason for nearby settlement location (e.g., "Oxford" = ox ford)

#### Crossroads
- Places of great significance in medieval culture
- Used for burial of suicides (abolished by Parliament in 1832)
- Signposts at major junctions (wooden posts with directional markers)
- Often featured a wayside cross or shrine
- Strategic investment nodes for road maintenance

#### Roadside Features
- **Abbeys/monasteries**: Major nodes in road network; provided hospitality to travelers
- **Hospices/hospitals**: Charitable rest stops for pilgrims
- **Inns/taverns**: Commercial rest stops at day-journey intervals (~20 miles apart)
- **Market crosses**: In towns, marking the legal market area
- Convergence points: routes converged on fords, bridges, places of worship, and market places

---

## SECTION 4: LANDSCAPE COMPOSITION

### 9. Complete Dark Fantasy Landscape Composition

#### Core Elements and Placement Rules

**Castle on Dominant Terrain Feature**
- Always on highest/most defensible point in the region
- Visible from surrounding area (acts as visual anchor and power symbol)
- Placement priority: cliff edge > hilltop > river promontory > mountain spur
- For dark fantasy: silhouetted against storm clouds; lightning illumination; gargoyles on parapets

**Town Below Castle Walls**
- Nestled in the protective shadow of the castle
- Grows organically along roads leading to castle gate
- Walled towns: walls follow contour of buildable land below castle
- Market square near main gate (trade under lord's protection)
- Church/cathedral as secondary visual landmark
- Density decreases away from castle (dense core, sparse edges)

**Farms on Flat Land**
- Open fields surrounding the town on available flat/gentle terrain
- Strip farming patterns visible from above
- Orchards, vegetting gardens near town walls
- Grain fields further out
- Pasture land at edges near forest
- In dark fantasy: progressively more blighted further from town; dead crops near corruption zones

**Forest Pressing In**
- Dense, dark forest as a wall around the civilized area
- Old-growth trees (massive trunks, dense canopy, limited undergrowth)
- Paths into forest narrow and overgrown
- For dark fantasy: trees become more twisted and threatening deeper in; strange lights; mist
- Forest edge: visible logging clearings, charcoal burner camps, woodcutter paths

**River as Natural Boundary**
- Provides water supply, transportation, fishing, mill power
- Bridges at key crossing points (one main bridge, possibly a ford upstream)
- Watermills along the banks
- River defines one edge of the settlement area
- Flood plain: fertile but dangerous; seasonal flooding marks visible

**Roads Connecting Settlements**
- Main road: connects castle town to the wider kingdom
- Secondary roads: to nearby villages, farms, mines
- Forest paths: to logging camps, hermit dwellings, ruins
- Road condition degrades with distance from settlement

**Ruins in Wilderness**
- Scattered in forests and on hilltops away from active settlements
- Older fortifications (previous era's defenses)
- Abandoned churches, monasteries, villages
- Overgrown with vegetation; partially collapsed
- In dark fantasy: source of quests, dungeons, cursed items

**Corruption Zones**
- Encroaching from one direction (gives geographic narrative)
- Gradient transition: healthy land > sickly vegetation > dead zone > active corruption
- Terrain deforms: ground cracks, alien crystal growths, floating earth fragments
- Atmospheric change: fog/mist, color desaturation, unnatural lighting
- Fauna changes: normal animals flee; corrupted creatures emerge
- Acts as environmental boundary/barrier guiding player exploration

### 10. Vertical Composition

#### Valley Floor (Elevation: Base level, 0-50m relative)
- **Terrain**: Flat to gentle rolling; alluvial soil; river floodplain
- **Features**: Farms, river, roads, bridges, fords, watermills
- **Vegetation**: Crops, pasture grass, riverside willows, reeds
- **Atmosphere**: Morning mist in river valley; warm golden light; pastoral
- **Dark fantasy twist**: Fog that never fully lifts; scarecrows that seem to move; blood-red sunsets

#### Hillside (Elevation: 50-150m relative)
- **Terrain**: Moderate slopes (15-35 degrees); terraced where buildings exist
- **Features**: Town, outer defensive walls, winding streets, stairs between levels
- **Vegetation**: Gardens, orchards on terraces; wild shrubs on unbuilt slopes
- **Atmosphere**: Wind exposure; views down to valley; sound of town life
- **Dark fantasy twist**: Cramped, leaning buildings; perpetual shadow from castle above; rats and ravens

#### Hilltop / Castle Level (Elevation: 150-250m relative)
- **Terrain**: Leveled summit for bailey; scarped cliffs on natural sides
- **Features**: Castle walls, keep, towers, gatehouse, inner courtyard
- **Vegetation**: Sparse; wind-stunted trees; castle garden within walls
- **Atmosphere**: Exposed to wind and weather; panoramic views; isolation/power
- **Dark fantasy twist**: Lightning strikes towers; crows circling keep; banners tattered; gargoyles watching

#### Mountain Backdrop (Elevation: 250m+ relative)
- **Terrain**: Steep rocky slopes; snow-capped peaks; alpine meadows
- **Features**: Distant peaks, mountain passes, isolated hermitages/shrines
- **Vegetation**: Tree line at ~200-300m (game-scale); krummholz zone; bare rock above
- **Atmosphere**: Storm clouds gathering; distant thunder; sense of vastness
- **Dark fantasy twist**: Unnatural peak shapes (horn-like, skull-like); perpetual storm on highest peak; aurora-like corruption glow

#### Vegetation by Elevation Layer
| Elevation | Vegetation Type | Coverage |
|-----------|----------------|----------|
| Valley (0-50m) | Crops, grass, riverside trees | 70-90% |
| Lower hillside (50-100m) | Mixed woodland, scrub | 50-70% |
| Upper hillside (100-200m) | Hardy trees, heather, rock plants | 30-50% |
| Mountain (200-300m) | Stunted trees, alpine grass | 10-30% |
| High mountain (300m+) | Lichen, bare rock, snow | 0-10% |

#### Atmospheric Layers
| Elevation | Light Quality | Weather | Sound |
|-----------|--------------|---------|-------|
| Valley | Soft, diffused (mist) | Fog, light rain | Water, animals, village |
| Hillside | Directional, shadows | Rain, moderate wind | Wind, town noise |
| Hilltop | Harsh, exposed | Heavy rain, strong wind | Wind, birds of prey |
| Mountain | Cold, dramatic | Snow, storms, lightning | Thunder, howling wind |

---

## IMPLEMENTATION NOTES FOR VEILBREAKERS

### Priority Terrain Features for Procedural Generation
1. **Heightmap-based base terrain** with erosion simulation (hydraulic + thermal)
2. **Voxel overlay** for cliff faces, caves, overhangs where heightmap fails
3. **Castle placement algorithm**: Find dominant terrain feature, then modify terrain to suit (scarping, leveling, ditch-cutting)
4. **Road network**: Connect settlements with A* pathfinding on terrain, then carve paths
5. **Corruption gradient**: Perlin noise field overlaid on terrain, driving vegetation/material/atmospheric changes
6. **Vertical composition**: Enforce elevation-based biome rules for consistent visual storytelling

### Key Measurements for Game Scale (assuming 1 unit = 1 meter)
- Motte height: 5-15m (game-exaggerated from historical 3-10m average)
- Moat width: 10-15m; depth: 3-5m
- Castle wall height: 8-12m; thickness: 2-4m
- Main road width: 4-6m
- Village path: 2-3m
- Forest trail: 1-1.5m
- Building foundation step: 0.5-1m increments
- Stair rise: 15-20cm; tread: 25-30cm
- Bridge span: up to 30m (stone arch); up to 15m (wood)
- Cliff height for drama: 20-100m
- Ravine width: 10-50m

### Sources
- [Motte-and-Bailey Castle - Wikipedia](https://en.wikipedia.org/wiki/Motte-and-bailey_castle)
- [Motte and Bailey Castle - World History Encyclopedia](https://www.worldhistory.org/Motte_and_Bailey_Castle/)
- [Anatomy of a Castle - Great Castles](https://great-castles.com/anatomy.html)
- [Medieval Castle - World History Encyclopedia](https://www.worldhistory.org/Medieval_Castle/)
- [Castle & Siege Terminology - Ole Miss](https://home.olemiss.edu/~tjray/medieval/castle.htm)
- [Castle Defenses: Moats - Knights Templar](https://knightstemplar.co/castle-defenses-the-significance-of-moats-in-medieval-times/)
- [Anatomy of a Medieval Castle Part 1](https://historymaniacmegan.com/2018/03/15/the-anatomy-of-a-medieval-castle-part-1-around-the-walls/)
- [How to Build a Medieval Castle - History Skills](https://www.historyskills.com/classroom/year-8/how-to-build-a-castle/)
- [Medieval Architecture: Natural Defences](https://medievalbritain.com/type/medieval-life/architecture/medieval-architecture-using-natural-defences-for-castles-and-fortresses/)
- [Chateau de Walzin](https://www.ancient-history-sites.com/sites/walzin-castle/)
- [Procedural Terrain Generation - Medium](https://medium.com/@ashleythedev/understanding-procedural-terrain-generation-in-games-07ac63fca626)
- [Procedural Elevation - Red Blob Games](https://www.redblobgames.com/x/1725-procedural-elevation/)
- [GPU Terrain Erosion - NVIDIA GPU Gems 3](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1-generating-complex-procedural-terrains-using-gpu)
- [GPU-Optimized Terrain Erosion Models](https://www.daydreamsoft.com/blog/gpu-optimized-terrain-erosion-models-for-procedural-worlds-building-hyper-realistic-landscapes-at-scale)
- [SoilMachine - 3D Multi-Layer Erosion](https://nickmcd.me/2022/04/15/soilmachine/)
- [World Machine](https://www.world-machine.com/)
- [Three Ways of Generating Terrain with Erosion](https://github.com/dandrino/terrain-erosion-3-ways)
- [History of Road Dimensions - Designing Buildings](https://www.designingbuildings.co.uk/wiki/The_history_of_the_dimensions_and_design_of_roads,_streets_and_carriageways)
- [Medieval Roads - Gough Map](https://goughmap.uk/about-roads)
- [Medieval Roads - ScotWays](https://scotways.com/ken/medieval-roads/)
- [Traveling on Medieval Roads - Sarah Woodbury](https://www.sarahwoodbury.com/traveling-on-medieval-roads/)
- [What Did Medieval Roads Look Like - Viabundus](https://www.landesgeschichte.uni-goettingen.de/roads/viabundus/what-did-medieval-roads-look-like/)
- [Wayside Shrine - Wikipedia](https://en.wikipedia.org/wiki/Wayside_shrine)
- [Medieval Fortification - Wikipedia](https://en.wikipedia.org/wiki/Medieval_fortification)
- [Talus Fortification - Wikipedia](https://en.wikipedia.org/wiki/Talus_(fortification))
- [Dry Stone - Wikipedia](https://en.wikipedia.org/wiki/Dry_stone)
- [The Cursed Plateau - Fab](https://www.fab.com/listings/6c27c8ee-de5f-4d59-9f81-241aec687182)
- [Cobblestone Lanes and Towers - Medieval Cities](https://chaoticanwriter.com/cobblestone-lanes-and-majestic-towers-medieval-cities-and-roads/)
- [Motte and Bailey - Castellogy](https://castellogy.com/architecture/architectural-terms/motte-and-bailey-introduction)
- [Durham Castle - Motte and Bailey](https://www.durhamworldheritagesite.com/learn/architecture/castle/motte-and-bailey)
