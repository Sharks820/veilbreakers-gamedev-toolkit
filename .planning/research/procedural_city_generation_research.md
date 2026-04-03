# Procedural City & Medieval Settlement Generation -- Comprehensive Research

**Researched:** 2026-04-02
**Domain:** Procedural generation of believable medieval settlements for dark fantasy action RPG
**Confidence:** HIGH (academic papers + shipping game implementations + existing codebase analysis)

---

## Summary

Procedural city generation for games is a mature field with well-understood algorithms spanning road networks, lot subdivision, district zoning, building facade generation, and settlement liveability. The foundational work by Parish & Muller (2001) introduced L-system road generation with global goals and local constraints. This was superseded for organic layouts by tensor field methods (Chen et al. 2008) which produce smoother, more natural road networks. For medieval fantasy towns specifically, the Watabou approach (block-centric Voronoi subdivision) has proven the most visually convincing and is the basis for the most widely-used fantasy city generator.

The VeilBreakers toolkit already has significant settlement generation infrastructure: `_settlement_grammar.py` implements concentric ring districts, OBB lot subdivision, organic road networks with L-system-style perturbation, corruption-scaled prop placement, and Tripo AI prompt templates. `settlement_generator.py` provides complete settlement composition for 5 types (village, town, bandit_camp, castle, outpost). The key gaps are: (1) tensor field road generation for more natural layouts, (2) Voronoi-based district subdivision for organic medieval feel, (3) CGA-style shape grammar for building facade variety, (4) WFC tile-based building generation, (5) multi-tier vertical city support, and (6) settlement liveability features (NPC routines, environmental storytelling, defensibility analysis).

**Primary recommendation:** Upgrade road generation from simple radial-spoke to tensor field streamlines, add Voronoi district subdivision as an alternative to concentric rings, and implement CGA shape grammar for building facade generation. These three additions would transform generated settlements from "recognizably procedural" to "believably medieval."

---

## Research Mission 1: City Generation Algorithms

### 1.1 Parish & Muller (2001) -- The Foundational Paper
**Confidence: HIGH** (original paper, widely cited, algorithm fully documented)

The seminal SIGGRAPH paper that established procedural city generation as a field. Uses an extended parametric L-system where two external functions override pure grammar rewriting:

**Global Goals Function** -- Selects direction for new road segments:
- For highways: cast N rays radially, sample population density along each ray, weight by inverse distance, choose highest-score direction
- For streets: apply local pattern rules (grid at 90deg, radial toward center, organic with Perlin noise)

**Local Constraints Function** -- Validates each proposed segment:
1. Water check: if crossing narrow water, mark as bridge; if wide, rotate to avoid
2. Intersection snapping: snap to nearby existing roads within radius (15m)
3. Elevation check: reject segments exceeding max grade (8% highways, 15% streets)
4. Collision check: create intersection at crossing points, trim segment

**Key parameters (implementable defaults):**

| Parameter | Highway | Main Street | Secondary | Alley |
|-----------|---------|-------------|-----------|-------|
| Segment length | 50-100m | 20-40m | 10-20m | 5-10m |
| Road width | 15-25m | 8-12m | 5-8m | 2-4m |
| Branch angle | 30-60deg | 70-90deg | 85-95deg | 60-120deg |
| Branch probability | 0.3 | 0.6 | 0.4 | 0.1 |
| Max grade | 8% | 12% | 15% | 20% |
| Snap radius | 20m | 15m | 10m | 5m |

**Source:** [Parish & Muller 2001 PDF (ETH Zurich)](https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf)

### 1.2 Chen et al. (2008) -- Tensor Field Roads
**Confidence: HIGH** (published paper with full pseudocode)

Superior to L-systems for organic road networks. Core insight: roads naturally follow two dominant perpendicular directions at any point; tensor fields encode this.

**Basis field types (composable):**
- **Grid field**: Manhattan-like grids from rotation tensor with decay
- **Radial field**: circular patterns for plazas/market squares
- **Height field**: roads follow terrain contours via gradient sampling
- **Boundary field**: roads parallel to water/walls/cliffs with decay

**Field combination**: weighted average of multiple basis tensors -- fields blend smoothly with no conflict resolution needed. This is the key advantage over L-systems.

**Streamline tracing** uses RK4 integration for smooth curves, with flip-checking for consistent direction and termination conditions (too close to existing streamlines = snap or terminate).

**Separation distance controls road density:**
- Major streamlines (main roads): sep = 30-80m for towns
- Minor streamlines (streets): sep = 10-20m for medieval scale
- Modulate by district: `sep = base_sep / (1 + density_factor)`

### 1.3 CityEngine CGA Shape Grammar (Esri)
**Confidence: HIGH** (commercial product, well-documented, industry standard)

CGA (Computer Generated Architecture) is a unique programming language for generating architectural 3D content. Rules control mass, geometry, proportions, and texturing at citywide scale.

**CityEngine 2025.0** (June 2025): Added dedicated Street Designer for procedural multi-lane roads, Visual CGA Editor updates. Subscription only ($2,200-$4,200/year).

**CityEngine 2025.1** (December 2025): New `modify` operation for selective geometry manipulation, Python 3 API connecting CityEngine to third-party libraries.

**Key CGA concepts applicable to VeilBreakers:**
- **Shape splitting**: recursively split a shape into sub-shapes (floors, bays, windows)
- **Component selection**: `comp(shape, {front: ..., top: ..., ...})` to address faces
- **Repeat operations**: `repeat_x/y(shape, spacing, rule)` for regular patterns
- **Stochastic rules**: `random_choice(options, weights)` for variety
- **Occlusion queries**: test if a sub-shape is visible from street (skip detail on hidden faces)

**Implementation approach for our toolkit:** The CGA split/component pattern can be implemented in pure Python without CityEngine. Use recursive shape subdivision:
```
Lot -> extrude -> Envelope -> comp(front, side, back, top) -> 
Front -> split_y(ground, upper_floors, cornice) ->
UpperFloor -> repeat_x(window_bay) -> WindowBay -> split_x(wall, window, wall)
```

### 1.4 L-System Road Networks
**Confidence: HIGH** (well-understood, already partially implemented in codebase)

The VeilBreakers toolkit already implements L-system-inspired road generation in `_settlement_grammar.py::generate_road_network_organic()`. Current implementation:
- Radial waypoints from center to perimeter with angular jitter
- Perturbed road segments using perpendicular noise
- Alley cross-connects between adjacent waypoints
- Short trails from mid-waypoints

**Gaps vs. full L-system approach:**
- No terrain awareness (all roads at z=0)
- No population density sampling for road direction
- No intersection snapping (roads cross without creating junctions)
- No road hierarchy beyond main/alley/trail width differences
- No bridge placement at water crossings

### 1.5 Agent-Based City Growth Simulation
**Confidence: MEDIUM** (academic research, less common in shipping games)

Treats city growth as emergent behavior from individual actors:
- **Land developer agents**: Buy empty lots, subdivide, sell
- **Builder agents**: Construct buildings on purchased lots
- **Infrastructure agents**: Extend roads to underserved areas
- **Population agents**: Move in/out based on amenities, employment, safety

For medieval settings, simpler rules work well:
- Merchant agents cluster near market crossroads
- Craftsmen agents locate near water (mill power) and roads (trade)
- Poor residents fill remaining space, expanding outward
- Lord/church agents claim the highest ground first

The existing VeilBreakers `simulate_city_growth` pseudocode in prior research captures this well with 25-year timesteps over 300 years of growth.

### 1.6 Voronoi-Based District Subdivision
**Confidence: HIGH** (widely used, proven in Watabou and many games)

The Watabou method (Medieval Fantasy City Generator, open-source on GitHub):
1. Scatter seed points in Fibonacci spiral pattern
2. Compute Voronoi diagram clipped to city bounds
3. Lloyd relaxation (3 iterations) for slight regularization
4. Classify patches as inner/outer based on distance to center (wall boundary)
5. Assign ward types by location rating function
6. Subdivide wards into blocks along roads

**Location rating function** scores each patch for each ward type using:
- Distance to center (Castle, Cathedral, Administration score high near center)
- Distance to gates (Market, Merchant, Military score high near gates)
- Distance to water (Craftsmen score high near rivers)
- Elevation (Castle, Patriciate score high on high ground)
- Population pressure (Slum scores high in overcrowded areas)

**Source:** [Watabou TownGeneratorOS GitHub](https://github.com/watabou/TownGeneratorOS)

### 1.7 How AAA Games Handle City Generation

**Assassin's Creed (Ubisoft):**
- Uses **modular architectural kits** per cultural style (Gothic for Paris in Unity, Abbasid for Baghdad in Mirage)
- Kits contain walls, columns, arches, windows, roofs as separate meshes that snap together
- Hand-placed major landmarks (Notre Dame = 14 months, 5,000 hours)
- Procedural fill between landmarks using modular kit assembly
- Distances between windows adjusted to match character jump abilities (gameplay drives architecture)
- Up to 10,000 crowd NPCs via AI level-of-detail pooling

**Cyberpunk 2077 / Night City:**
- NOT procedurally generated -- entirely hand-built
- However, uses **prefab-based hierarchy** (modular building kits assembled into blocks)
- Key insight: procedural layout + curated modular pieces is the sweet spot

**Townscaper (Oskar Stalberg):**
- Uses **irregular grid** (not square voxels) for organic feel
- WFC constraint solving + marching cubes mesh generation
- "Driven WFC": user clicks affect hidden solidity/color layers, not tiles directly
- Fully deterministic tile selection via priority list
- ~100 hand-made blocks produce entire cities
- Key insight: the grid shape itself creates organic appearance

**Dwarf Fortress:**
- World generation builds geology, climate, ecosystems, civilizations and history
- Settlement placement governed by geography (rivers, biomes)
- Internal layout follows entity/culture rules
- Time-simulated growth over centuries of history before play begins

**Medieval Dynasty:**
- Player-placed buildings, but underlying system uses zone-based district formation
- Spline-based road system with adjustable parameters
- Spawn markers for prop placement along roads

### 1.8 Existing Codebase State
**Confidence: HIGH** (direct code inspection)

**Already implemented in VeilBreakers toolkit:**
- 5 settlement types: village, town, bandit_camp, castle, outpost
- Concentric ring districts: market_square, civic_ring, residential, industrial, outskirts
- OBB lot subdivision (axis-aligned simplified OBB)
- Organic road network with perturbation
- Corruption-scaled prop placement with Tripo prompts
- Building assignment to lots by district
- Terrain-aware foundation placement (heightmap support)
- Interior furnishing by room function
- Interior lighting placement per room type

---

## Research Mission 2: Road Network Generation

### 2.1 L-System Branching for Organic Layouts
**Confidence: HIGH**

**Core algorithm:**
```
Axiom: Road(0, highway_attrs) at city_center
Rule 1: Road(delay, attrs) : delay > 0 -> Road(delay-1, attrs)
Rule 2: Road(delay, attrs) : delay == 0 -> 
    IntersectionQuery(road_attrs)
    Branch(attrs, road_attrs)
Rule 3: Branch(attrs, road_attrs) ->
    Road(delay_highway, highway_attrs)   // continue forward
    Road(delay_street, street_attrs_L)   // branch left
    Road(delay_street, street_attrs_R)   // branch right
```

For organic medieval roads, add Perlin noise to direction (15-30deg amplitude) and reduce branch probability to 0.3-0.4 for main roads, 0.1-0.2 for alleys.

### 2.2 Grid-Based Road Networks for Planned Cities
**Confidence: HIGH**

Grid patterns (bastide towns, Roman-founded cities):
- Main axis (cardo/decumanus): 2 perpendicular major roads through center
- Secondary grid: parallel roads at 50-100m spacing
- Block size: 50x80m typical for medieval bastides
- Market square: where main axes cross, widened to 40x40m+
- Irregularity factor: offset grid nodes by 0-15% of spacing for age/organic feel

### 2.3 Terrain-Following Roads
**Confidence: HIGH**

**Algorithm for road-terrain interaction:**
1. Sample terrain height at each road point
2. Calculate grade between consecutive points
3. If grade exceeds max: try hill cut (if hill is narrow), bridge (if valley), or switchback (if sustained steep slope)
4. Road height = lerp between terrain height and preferred-grade extrapolation (0.7 terrain weight)
5. Switchback insertion: add zigzag waypoints at turn_radius=15m when grade > 20%
6. Contour following: on hillsides, roads follow terrain contours with gentle diagonal descent

**Max grade standards:**
| Road type | Max grade | Switchback threshold |
|-----------|-----------|---------------------|
| Main road | 8-12% | 15% |
| Side street | 12-15% | 20% |
| Alley/path | 15-20% | 25% |
| Stairs | 100% (45deg) | N/A |

### 2.4 Road Hierarchy
**Confidence: HIGH**

| Level | Name | Width | Surface | Use |
|-------|------|-------|---------|-----|
| 1 | Main road | 8-12m | Cobblestone | Primary through-route, connects gates |
| 2 | Side street | 5-8m | Mixed cobble/dirt | District internal circulation |
| 3 | Alley | 2-4m | Dirt/gravel | Building rear access |
| 4 | Path | 1-2m | Packed earth | Pedestrian only, garden access |
| 5 | Passage | 1-1.5m | Stone | Covered passageways through buildings |

**Road surface materials by type:**
| Surface | Material | Use cases | Medieval period |
|---------|----------|-----------|-----------------|
| Cobblestone | Cut granite/basalt | Main roads, market squares | 12th century+ wealthy towns |
| Flagstone | Flat stone slabs | Important buildings, plazas | Religious/civic areas |
| Mixed cobble | Irregular stones | Side streets | Common in most towns |
| Packed earth/dirt | Compacted soil | Alleys, outskirts, villages | Universal, all periods |
| Gravel | Crushed stone | Paths, drainage edges | Road margins |
| Timber planks | Wood boards | Bridge surfaces, marshy areas | Wetland crossings |

### 2.5 Gate Connections
**Confidence: HIGH**

Roads connect to gates following these rules:
1. Every gate has a direct road to the market square (the "main road")
2. Gates face the direction of the most important external destination (trade routes, neighboring towns)
3. Number of gates = min(num_major_external_destinations, num_wall_segments / 4)
4. Typical: 2-6 gates for a medieval town
5. Gate roads are the widest in town (10-15m including gatehouse passage at 3-4m)
6. Roads fan out from gates into the town, creating triangular "gate district" zones
7. Inns, stables, and traders cluster within 100m of gates

### 2.6 Bridge Placement
**Confidence: HIGH**

**Bridge selection by span and road hierarchy:**

| Bridge style | Max span | Min road level | Features |
|--------------|----------|----------------|----------|
| Small stone | 8m | Alley | Single arch |
| Stone arch | 20m | Side street | Multiple arches at 6-8m spacing |
| Covered wooden | 15m | Side street | Medieval style, provides shelter |
| Grand stone | 40m | Main road | May have shops, double road width |
| Drawbridge | 10m | Main road | At gates only, defensive |
| Wooden plank | 12m | Path | Simple, no railings, temporary |

**Placement algorithm:**
1. For each road segment, check intersection with water bodies
2. If water width < 30m: place bridge
3. If water width >= 30m: reroute road to nearest bridge-worthy crossing (narrowest point)
4. Bridge height above water = 2m + water_width * 0.1 (taller for wider rivers)
5. Bridge orientation perpendicular to water flow (shortest crossing)

### 2.7 Road Width Standards
**Confidence: HIGH** (historical accuracy cross-referenced)

| Road type | Medieval width | Game-adjusted width | Notes |
|-----------|---------------|-------------------|-------|
| King's road/highway | 4-8m | 10-12m | Room for carts to pass |
| Town main street | 3-6m | 8-10m | Often widened at market |
| Market square "road" | 15-30m | 20-40m | Open space, not linear |
| Side street | 2-4m | 5-7m | Single cart width |
| Alley | 1-2m | 2-4m | Pedestrian + handcart |
| Passage | 0.5-1.5m | 1.5-2m | Between buildings |

Note: Game-adjusted widths are 1.5-2x historical to accommodate camera/player movement and combat.

---

## Research Mission 3: Lot Subdivision and Building Placement

### 3.1 Dividing City Blocks into Building Lots
**Confidence: HIGH**

**Two primary approaches:**

**Approach A -- OBB Recursive Splitting (already implemented in toolkit):**
1. Compute minimum-area oriented bounding box of block polygon
2. Split perpendicular to longest axis at 40-60% of extent
3. Recurse until lots reach target area range
4. Validate: min width, min depth, max aspect ratio, road frontage

**Approach B -- Voronoi-Based Irregular Subdivision (for medieval organic layouts):**
1. Scatter points inside block (70% biased toward road edges)
2. Compute constrained Voronoi clipped to block boundary
3. Lloyd relaxation (1-3 iterations) for slight regularization
4. Merge tiny lots, split oversized ones
5. Result: irregular lots typical of real medieval towns

**Recommendation:** Use OBB for planned/grid towns and bastides. Use Voronoi for organic medieval towns. The current toolkit implements OBB only.

### 3.2 OBB Subdivision Details
**Confidence: HIGH** (already in codebase, verified working)

Current implementation in `_settlement_grammar.py::subdivide_block_to_lots()`:
- Axis-aligned bounding box split (simplified from true OBB)
- District-specific minimum lot areas: market_square=60m2, civic_ring=50m2, residential=25m2, industrial=40m2, outskirts=20m2
- Max recursion depth: 6
- Split ratio randomized at 0.4-0.6
- Produces CCW rectangle halves for each split

### 3.3 Lot Size Variation by District
**Confidence: HIGH**

| District | Min area | Max area | Min width | Min depth | Max aspect | Min frontage | Setback |
|----------|----------|----------|-----------|-----------|------------|--------------|---------|
| Market/Commercial | 80m2 | 300m2 | 8m | 10m | 2.5:1 | 6m | 0m |
| Residential (wealthy) | 150m2 | 500m2 | 10m | 12m | 2:1 | 8m | 3m |
| Residential (common) | 48m2 | 150m2 | 6m | 8m | 3:1 | 4m | 1m |
| Slum | 20m2 | 60m2 | 4m | 5m | 4:1 | 2m | 0m |
| Industrial/Craft | 100m2 | 400m2 | 10m | 10m | 2:1 | 6m | 2m |
| Noble/Patriciate | 300m2 | 1000m2 | 15m | 15m | 2:1 | 10m | 5m |
| Religious | 200m2 | 2000m2 | 12m | 15m | 2:1 | 8m | 3m |

### 3.4 Building Setback Rules
**Confidence: HIGH**

- **Zero setback**: Market district, slums, medieval common residential (buildings directly on street, creating continuous streetwall -- the most medieval look)
- **Small setback (1-2m)**: Common residential (small front yard or step)
- **Medium setback (3-5m)**: Noble/patriciate (garden or courtyard visible from street)
- **Large setback (5m+)**: Religious buildings (cemetery, forecourt), castle (killing ground)
- **Overhang/jettying**: Upper floors overhang street by 0.3-1.0m (very common in medieval timber-frame buildings, creates characteristic "leaning" streetscape)

### 3.5 Irregular Lot Shapes
**Confidence: HIGH**

Corner lots, triangular lots, and L-shaped lots arise naturally from organic road networks:
- **Corner lots**: Have frontage on 2+ roads. Building wraps the corner in L-shape. Primary facade = longer road edge.
- **Triangular lots**: At Y-junctions. Building fills triangle with cut corner.
- **L-shaped lots**: Behind corner buildings. Used for gardens, workshops, or divided into sub-lots.
- **Deep narrow lots** (burgage plots): Typical medieval pattern -- narrow street frontage (4-6m), deep lot (20-40m). Building at front, garden/workshop at rear.

### 3.6 Density Variation
**Confidence: HIGH**

```
Center (market square):     95-100% lot coverage, 0m setback, 2-4 story
Inner ring (civic/wealthy): 80-90% coverage, 1-3m setback, 2-3 story
Middle ring (residential):  60-80% coverage, 1-2m setback, 1-2 story
Outer ring (industrial):    50-70% coverage, 2-5m setback, 1 story
Outskirts:                  30-50% coverage, 5m+ setback, 1 story
Outside walls (suburbs):    20-40% coverage, variable, 1 story
```

### 3.7 Open Space Reservation
**Confidence: HIGH**

Reserve space for non-building features BEFORE lot subdivision:
1. **Market square**: At center or main crossroads. Size: 30x30m to 50x50m.
2. **Church/cathedral yard**: Adjacent to or containing the main religious building. 20x30m+.
3. **Wells/fountains**: At every major intersection. 3x3m footprint, 6m clearance radius.
4. **Small squares/plazas**: At major Y-junctions or road widenings. 15x15m typical.
5. **Cemeteries**: Adjacent to churches, within walls. 15x20m.
6. **Training/parade ground**: In military district. 30x40m.
7. **Gardens**: In noble/patriciate district. Per-lot, not communal.

**Algorithm:** Before running lot subdivision, place open spaces as "occupied lots" with special type flags. Then subdivide remaining block area around them.

---

## Research Mission 4: District Design

### 4.1 Medieval Town District Types
**Confidence: HIGH** (cross-referenced historical and game design sources)

| District | Primary function | Building types | Density | Wealth | Smell/Noise |
|----------|-----------------|---------------|---------|--------|-------------|
| Market | Commerce/trade | Shops, stalls, taverns, warehouses, inns, guild halls | Very high | High | Moderate (food, animals) |
| Civic | Administration | Town hall, courthouse, treasury, tax office | Medium | High | Low |
| Residential (wealthy) | Noble/merchant housing | Townhouses, manors, gardens, chapels, stables | Medium | Very high | Low |
| Residential (common) | Worker housing | Houses, hovels, small workshops | High | Low-medium | Moderate |
| Industrial/Craft | Production | Smithies, tanneries, dye works, mills, bakeries | Medium-high | Medium | High (smoke, chemicals) |
| Religious | Worship/learning | Cathedral, churches, monastery, scriptorium, hospice | Low-medium | High (buildings), low (residents) | Low (bells) |
| Military | Defense | Barracks, armory, training yard, gatehouse, watchtowers | Medium | Medium | High (drilling) |
| Slum | Marginal housing | Hovels, shanties, lean-tos, alehouses, pawnshops | Very high | Very low | High (sewage) |

### 4.2 Organic District Formation
**Confidence: HIGH**

Districts form naturally based on proximity to key features:

1. **Market district**: Forms at the main crossroads or where the road widens. Gravitates toward gates (trade access).
2. **Along main road**: Wealthy merchants and craftsmen claim frontage on the main road first. Buildings behind these are lower-status.
3. **Near water**: Mills, tanneries, dyers, breweries need water power or process water. Industrial/craft districts form along rivers.
4. **On high ground**: Castle/lord on highest point. Noble/patriciate on elevated ground nearby. Status decreases with elevation.
5. **Near gates**: Military (defense), inns/stables (travelers), markets (trade goods arrive).
6. **Near church**: Religious buildings cluster. Wealthy residents prefer proximity to church.
7. **Downwind/downstream**: Noxious industries (tanning, dyeing, butchering) forced to edges, downwind of wealthy areas.

### 4.3 District-Specific Building Distribution
**Confidence: HIGH**

```python
DISTRICT_BUILDINGS = {
    'Market': {
        'merchant_shop': 0.35, 'tavern': 0.10, 'warehouse': 0.15,
        'market_stall': 0.20, 'inn': 0.05, 'guild_hall': 0.02,
        'fountain': 0.03, 'residential_upper': 0.10
    },
    'CraftsmenWard': {
        'workshop': 0.30, 'residential': 0.35, 'shop_front': 0.15,
        'stable': 0.05, 'well': 0.02, 'small_warehouse': 0.08,
        'smithy': 0.05
    },
    'PatriciateWard': {
        'manor_house': 0.25, 'townhouse': 0.30, 'garden': 0.15,
        'chapel': 0.05, 'fountain': 0.05, 'servant_quarters': 0.10,
        'stable': 0.10
    },
    'Slum': {
        'hovel': 0.40, 'shanty': 0.25, 'lean_to': 0.15,
        'alehouse': 0.08, 'pawnshop': 0.05, 'empty_lot': 0.07
    },
    'MilitaryWard': {
        'barracks': 0.25, 'armory': 0.10, 'training_yard': 0.15,
        'stable': 0.15, 'officer_quarters': 0.10, 'gatehouse': 0.05,
        'watchtower': 0.10, 'mess_hall': 0.10
    },
    'Cathedral': {
        'cathedral': 0.05, 'monastery': 0.10, 'scriptorium': 0.05,
        'garden': 0.20, 'clergy_housing': 0.25, 'hospice': 0.10,
        'cemetery': 0.10, 'bell_tower': 0.05, 'courtyard': 0.10
    }
}
```

### 4.4 Wealth Gradient
**Confidence: HIGH**

The concentric ring model already in the toolkit captures this well:

```
Castle/Keep (center, highest ground) -----> Walls -----> Outskirts
  Noble estate   Merchant houses   Common housing   Slums/shanties
  Cathedral      Guild halls       Workshops        Marginal farms
  
Wealth:  Very High    High         Medium           Low           Very Low
Density: Low          Medium       High             Very High     Low
Height:  3-4 story    2-3 story    1-2 story        1 story       1 story
```

Exceptions:
- Religious buildings (wealthy) scattered throughout
- Wealthy merchant houses sometimes near gates (trade access)
- Industrial districts moderate wealth but high productivity

### 4.5 Fortified Town Internal Organization
**Confidence: HIGH**

**Walled town layout rules:**
1. Castle/keep at center or highest point, with own inner wall (double defense)
2. Market square adjacent to castle gate (lord controls commerce)
3. Church/cathedral within 100m of market (spiritual authority visible)
4. Ring road inside walls (military circulation for rapid deployment)
5. Main roads connect each gate to market square (direct trade routes)
6. Side streets create grid-like blocks between main roads
7. Buildings densest along main roads, sparser toward walls
8. 3-5m clear zone inside walls (pomerium -- for defense access, no buildings)
9. Wall towers every 30-60m (crossbow range overlap)
10. Gatehouse with barbican on most-threatened approach

### 4.6 Veil Corruption Effects on District Design (VeilBreakers-specific)
**Confidence: HIGH** (based on existing corruption system in codebase)

The toolkit already implements corruption tiers (pristine/weathered/damaged/corrupted) with spacing modifiers. For district-level corruption effects:

| Corruption level | District changes |
|-----------------|-----------------|
| Pristine (0.0-0.2) | Normal medieval layout. Clean buildings, active market. |
| Weathered (0.2-0.5) | Abandoned buildings at edges. Fewer market stalls. Overgrown gardens. Warning signs posted. |
| Damaged (0.5-0.8) | Barricaded streets. District boundaries blur as residents flee. Corrupted props appear. Defensive positions improvised. Military district expands. |
| Corrupted (0.8-1.0) | Entire districts abandoned. Buildings collapsed or warped. Roads crack and shift. Unnatural geometry appears. Only military/religious districts remain active. |

**Implementation approach:** Modify district fill rates by corruption pressure. At high corruption, reduce building count, increase prop spacing, add ruin/debris props, shift district weights toward military/religious.

---

## Research Mission 5: Making Generated Towns Feel Alive

### 5.1 NPC Placement and Routines
**Confidence: MEDIUM** (game design patterns, not algorithmic -- subjective quality)

**NPC placement by building type:**

| Building | NPCs | Day routine | Night routine |
|----------|------|-------------|---------------|
| House | 2-5 residents | Work at assigned building | Return home, sleep |
| Shop | 1 owner + 0-2 assistants | Tend shop, hawk wares | Close shop, go home |
| Tavern | 1 keeper + 0-3 staff | Cook, serve, clean | Serve evening crowd, sleep upstairs |
| Smithy | 1 smith + 0-1 apprentice | Work forge, hammer | Return home or sleep in back |
| Market stall | 1 vendor | Sell goods, arrange display | Pack up, go home |
| Barracks | 4-10 soldiers | Train, patrol, stand guard | Sleep in barracks |
| Church | 1-3 clergy | Pray, tend grounds, counsel | Retire to quarters |
| Guard post | 2-4 guards | Patrol assigned route | Night watch shift or sleep |

**Key routine patterns:**
- Dawn: NPCs leave homes, walk to workplaces via main roads
- Morning: Work activities, market opens
- Midday: Some NPCs visit tavern/market for food
- Afternoon: Continue work, children play in squares
- Dusk: Shops close, NPCs return home, tavern fills
- Night: Guards patrol, tavern activity, most NPCs indoors

### 5.2 Market Stall Placement
**Confidence: HIGH**

- Place in market square in **rows** facing each other (creates browsing aisles)
- Stall spacing: 3-4m between stalls, 4-6m between rows
- Central feature: fountain, well, or market cross at center of square
- Stall types distributed: 40% food (bread, meat, produce), 20% dry goods (cloth, rope), 15% crafts (pottery, tools), 10% exotic (spices, jewelry), 15% services (barber, scribe)
- Permanent stalls (wooden frame + canvas) vs. ground blankets (for poorest merchants)
- Orientation: stalls face foot traffic direction (toward gates)

### 5.3 Street Furniture
**Confidence: HIGH**

| Prop type | Placement rule | Density per 100m road | Notes |
|-----------|---------------|----------------------|-------|
| Lantern post | Every 15-20m on main roads | 5-7 | None on alleys (dark!) |
| Signpost | At every major intersection | 1-2 | Wood with carved arrows |
| Well/fountain | At major intersections | 0-1 | Every 200m, social gathering point |
| Bench | Near wells, churches, squares | 1-2 | Stone or wood |
| Barrel cluster | Near shops, taverns, warehouses | 3-5 | Vary size (single to stack) |
| Crate stack | Near warehouses, gates, docks | 2-4 | Different sizes |
| Cart | Near market, parked by shops | 0-1 | Hay cart, merchant cart |
| Hitching post | Near taverns, gates, stables | 1-2 | For horses |
| Notice board | Near gates, market, town hall | 0-1 | Parchments pinned |
| Gallows/stocks | Near town hall, market square | 0-1 | Punitive display |
| Horse trough | Near stables, gates | 0-1 | Stone with water |
| Woodpile | Near houses, smith | 2-3 | Fuel supply |
| Hanging signs | On shops, taverns, inns | per-building | Iconic images (no text needed for illiterate population) |

The toolkit already has prop prompts for: lantern_post, market_stall, well, barrel_cluster, cart, bench, trough, notice_board.

### 5.4 Environmental Storytelling in Town Layout
**Confidence: MEDIUM** (design philosophy, not algorithm)

**Principles for VeilBreakers dark fantasy:**
1. **Burned district**: Section of town with charred buildings, telling of a past attack. Buildings have blackened walls, collapsed roofs, debris in streets.
2. **Boarded-up area**: Buildings with planks over windows/doors near corruption zone. Warning signs, arcane wards painted on doors.
3. **Refugee camp**: Tents and makeshift shelters outside walls, near gates. Overflowing settlement from corruption-displaced villages.
4. **Prosperity gradient**: Quality of building materials tells wealth story -- stone at center, timber-frame middle, wattle-and-daub outer, shanties at edge.
5. **Battle scars**: Damaged wall sections, patched with different stone. Embedded arrows/projectiles in walls. Defensive ditches partially filled.
6. **Growth rings**: Different architectural styles in different wall rings tell the town's age. Oldest buildings near center have different style than newest outer ring.
7. **Personal touches**: Laundry lines between buildings, potted plants on windowsills, children's toys in yards, food scraps near doorways.

### 5.5 Memorable Landmarks
**Confidence: HIGH**

Every generated town needs 3-5 landmarks for player orientation (Kevin Lynch's "Image of the City"):
1. **Tallest structure**: Bell tower, cathedral spire, or castle keep -- visible from everywhere
2. **Central gathering space**: Market square with unique fountain/statue/market cross
3. **Distinctive gate**: Largest/most ornate gate, often with the town's crest
4. **Natural feature**: River bend, prominent tree, cliff face, waterfall
5. **Unique building**: A building that breaks the pattern -- different color, larger size, unusual shape

**Implementation:** After generating standard layout, select 3-5 buildings/features and apply "landmark" modifiers: 1.5x scale, unique material, added decoration, unique silhouette.

### 5.6 Defensibility Analysis
**Confidence: HIGH**

**Chokepoint identification:**
- Every gate is a primary chokepoint (3-4m wide passage through wall)
- Narrow alleys between buildings create secondary chokepoints
- Bridge approaches are natural chokepoints
- Bent entrances (L-shaped passages) force attackers to slow and turn

**Sightline analysis:**
- Wall towers need overlapping fields of view (every 30-60m based on crossbow range ~150m effective)
- Gate towers should see the approach road for 100m+
- Interior sightlines from guard posts should cover main intersections
- "Dead zones" (areas not visible from any guard position) are gameplay-interesting for stealth

**Wall coverage:**
- Complete perimeter enclosure for fortified towns
- Wall height: 5-12m depending on era/wealth
- Wall thickness: 1.5-3m (walkable on top)
- Crenellations: merlons 0.6m wide, 0.4m gaps, 2m high
- Arrow loops: every 3m along wall, alternating heights

**Algorithm for defensibility scoring:**
```
For each settlement:
  wall_coverage = perimeter_walled / total_perimeter
  chokepoint_count = count(passages < 4m wide)
  sightline_coverage = area_visible_from_guard_positions / total_area
  elevation_advantage = average_defender_height - average_attacker_height
  
  defense_score = (wall_coverage * 0.3 + 
                   min(chokepoint_count / expected, 1.0) * 0.2 +
                   sightline_coverage * 0.3 +
                   clamp(elevation_advantage / 5.0, 0, 1) * 0.2)
```

### 5.7 Player Navigation in Procedural Towns
**Confidence: HIGH** (Kevin Lynch + game design research)

**The five elements (from Kevin Lynch's urban design, applied to games):**
1. **Paths**: Clear main roads that players naturally follow. Make main roads wider, better lit, more decorated.
2. **Edges**: Walls, rivers, cliff faces that bound areas. Players use these to orient.
3. **Districts**: Visually distinct areas (material palette, building height, decoration density). Player should recognize "I'm in the market district" without a map.
4. **Nodes**: Important intersections, squares, gathering points. Decision points for the player.
5. **Landmarks**: Unique, visible features. The cathedral spire, the giant tree, the colored building.

**Practical implementation:**
- **District color palettes**: Each district uses a dominant material/color (warm wood for market, grey stone for military, white plaster for noble, dark timber for slums)
- **Signage**: Hanging signs with iconic images (anvil = smithy, bed = inn, goblet = tavern)
- **Road width gradient**: Roads get narrower as you move away from center -- players intuitively follow wider roads to find the center
- **Weenies** (Disney Imagineering term): Tall, visible objects that draw the player forward. Place at the end of long straight roads.
- **Birth canals**: Narrow passages that open into dramatic spaces (enter through tight alley, emerge into grand market square)

---

## Architecture Patterns

### Recommended Generation Pipeline

```
1. Define settlement parameters (type, size, seed, corruption)
       |
2. Generate terrain heightmap (if not provided)
       |
3. Place seed points (castle/market/church)
       |
4. Generate road network (tensor field or L-system)
       |
5. Extract city blocks from road network
       |
6. Generate districts (Voronoi or concentric ring)
       |
7. Subdivide blocks into lots (OBB or Voronoi)
       |
8. Assign building types to lots (by district)
       |
9. Generate building geometry (CGA shape grammar)
       |
10. Place street furniture and props
       |
11. Place NPCs and assign routines
       |
12. Run defensibility analysis
       |
13. Apply corruption modifiers
       |
14. Generate underground (sewers, catacombs)
```

### Pattern: Seed-Deterministic Generation
Every function takes a `seed: int` parameter and uses `random.Random(seed)` for all stochastic decisions. This ensures:
- Same seed = same settlement
- Seeds can be stored in save games
- Seeds enable A/B comparison during development

### Pattern: Pure-Logic + Geometry Separation
Already used in the toolkit. Pure-logic layer (`_settlement_grammar.py`) produces data dicts. Geometry layer (`settlement_generator.py`, Blender handlers) converts to mesh. This enables:
- Testing without Blender
- Multiple output targets (Blender, Unity, preview)
- Separation of concerns

### Anti-Patterns to Avoid

1. **Monolithic generator**: Don't make one function that generates everything. Keep pipeline stages independent and composable.
2. **Hardcoded dimensions**: Always parameterize sizes. Medieval scale differs from modern; game scale differs from historical.
3. **Perfect symmetry**: Medieval towns are asymmetric. Always add noise/jitter to positions, angles, and sizes.
4. **Ignoring terrain**: Flat-ground generation looks artificial. Even gentle terrain slopes create character.
5. **Uniform density**: Real towns have density gradients. A town with uniform building spacing looks wrong.

---

## Don't Hand-Roll

| Problem | Don't build | Use/reference instead | Why |
|---------|------------|----------------------|-----|
| Voronoi diagrams | Custom Voronoi | `scipy.spatial.Voronoi` or pure-Python Fortune's algorithm | Edge cases in degenerate configurations |
| Convex hull | Custom hull | `scipy.spatial.ConvexHull` | Numerically stable, handles collinear points |
| Perlin/simplex noise | Custom noise | `opensimplex` or `noise` package | Correct gradient calculation, tiling support |
| Minimum bounding box | Custom OBB | Rotating calipers algorithm (well-documented) | O(n log n) vs naive O(n^3) |
| Shortest path in road network | Custom pathfinding | Dijkstra/A* from any graph library | Correctness guarantees, heap optimization |
| Polygon clipping | Custom clipping | Sutherland-Hodgman or Weiler-Atherton | Edge cases in concave polygons |

**Note:** The toolkit avoids numpy in the pure-logic layer for Blender compatibility. For algorithms requiring scipy, provide a pure-Python fallback with the scipy version as optional optimization.

---

## Common Pitfalls

### Pitfall 1: Floating Buildings
**What goes wrong:** Buildings placed on lots don't account for terrain slope, leaving gaps under one side or clipping into terrain on the other.
**Why it happens:** Lot subdivision operates in 2D; building placement ignores heightmap.
**How to avoid:** After placing a building footprint, sample terrain at all four corners. Set building base to lowest corner height. Add foundation/retaining wall geometry to fill the gap.
**Warning signs:** Buildings visually hovering or intersecting terrain in viewport.

### Pitfall 2: Inaccessible Buildings
**What goes wrong:** Lot subdivision creates lots with no road frontage, making buildings unreachable.
**Why it happens:** Recursive splitting can create interior lots disconnected from road edges.
**How to avoid:** Validate every lot has minimum road frontage (4m). If not, merge with adjacent lot or create access path.
**Warning signs:** Flood-fill from any road can't reach a building entrance.

### Pitfall 3: Overlapping Geometry
**What goes wrong:** Buildings, roads, and props intersect each other.
**Why it happens:** Independent placement systems don't check mutual clearance.
**How to avoid:** Maintain a spatial occupancy grid. Check clearance before placing each element. Prefer rejection sampling over post-hoc collision resolution.
**Warning signs:** Z-fighting in renderer, physics engine explosions.

### Pitfall 4: Monotonous Streetscapes
**What goes wrong:** Every street looks the same because buildings are too regular.
**Why it happens:** Insufficient variation in building parameters (height, width, material, style).
**How to avoid:** Vary building height (+/-1 floor from district default), material (2-3 per district), roof style (mix gable/hip/flat), and facade detail. Introduce occasional "special" buildings (taller, wider, different material).
**Warning signs:** Player can't distinguish one street from another.

### Pitfall 5: Unrealistic District Boundaries
**What goes wrong:** Districts have sharp, visible boundaries like a zoning map.
**Why it happens:** Hard cutoffs between district types.
**How to avoid:** Blend district characteristics at boundaries. A building at the market/residential boundary might be a shop with residential upper floors. Use noise-based soft boundaries with 10-20m transition zones.
**Warning signs:** Walking from one district to another feels like crossing an invisible line.

### Pitfall 6: Scale Mismatch
**What goes wrong:** Medieval town feels too big or too small for gameplay.
**Why it happens:** Using historical dimensions without game-scale adjustment, or vice versa.
**How to avoid:** Historical medieval towns were SMALL. A 500-person town might be 200m across. For gameplay, scale up 1.5-2x. But don't go too far -- traversal time matters. Target: 30-90 seconds to walk across the largest generated town.
**Warning signs:** Town takes 5+ minutes to cross, or can be sprinted through in 5 seconds.

---

## State of the Art (2025-2026)

| Old approach | Current approach | When changed | Impact |
|--------------|-----------------|--------------|--------|
| L-system roads only | Tensor field + L-system hybrid | 2008+ (Chen) | More organic, controllable roads |
| Regular grid lots | OBB + Voronoi hybrid | 2012+ (Aliaga) | Realistic lot shapes |
| Hand-placed buildings | CGA shape grammar | 2006+ (CityEngine) | Scalable facade generation |
| Random building placement | WFC constraint solving | 2016+ (Gumin/Stalberg) | Structurally coherent buildings |
| Flat-ground only | Terrain-integrated generation | Always evolving | Believable hillside towns |
| Single-pass generation | Time-simulated growth | 2009+ (Weber) | Historical authenticity |
| CityEngine 2024 | CityEngine 2025.1 | Dec 2025 | Python 3 API, modify operation |
| Fixed procedural rules | GAN/ML-assisted layout | 2023+ (experimental) | Layout learning from real cities |

---

## Open Questions

1. **Voronoi in pure Python without scipy**: The pure-logic layer avoids numpy. Implementing Fortune's algorithm from scratch is complex. Should we allow scipy as optional dependency or find a lightweight pure-Python Voronoi?
   - What we know: scipy.spatial.Voronoi works well, Fortune's algorithm is O(n log n)
   - What's unclear: Performance requirements for settlement-scale (50-200 points, likely fine either way)
   - Recommendation: Implement simplified Voronoi for <200 points using brute-force (O(n^2) acceptable at this scale), with scipy as optional fast path

2. **WFC tile set authoring**: The WFC approach to buildings requires hand-authored tile modules (~100 tiles). Who authors these?
   - What we know: Tripo AI could generate base meshes, Blender tools could refine
   - What's unclear: Whether AI-generated tiles maintain sufficient quality/consistency
   - Recommendation: Defer WFC buildings to a later phase. Current CGA approach + existing building generators is sufficient for now.

3. **Performance at scale**: How many buildings before generation time becomes a problem?
   - What we know: Current settlement generator handles 2-16 buildings easily
   - What's unclear: Scaling to 100+ buildings for large towns
   - Recommendation: Profile current pipeline at 100 buildings. Expect lot subdivision and road generation to be fast (< 1s). Building geometry generation will be the bottleneck.

---

## Sources

### Primary (HIGH confidence)
- [Parish & Muller 2001 - Procedural Modeling of Cities](https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf) -- Foundational L-system road generation
- [Chen et al. 2008 - Interactive Procedural Street Modeling](https://www.sci.utah.edu/~chengu/street_sig08/street_project.htm) -- Tensor field roads
- [Watabou TownGeneratorOS](https://github.com/watabou/TownGeneratorOS) -- Open-source medieval city generator
- [CityEngine CGA Documentation](https://doc.arcgis.com/en/cityengine/latest/tutorials/tutorial-6-basic-shape-grammar.htm) -- Shape grammar reference
- [How Townscaper Works](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making) -- WFC + irregular grid approach
- [Procedural Cities Survey](https://www.citygen.net/files/images/Procedural_City_Generation_Survey.pdf) -- Comprehensive algorithm survey
- VeilBreakers codebase: `_settlement_grammar.py`, `settlement_generator.py`, `worldbuilding_layout.py`

### Secondary (MEDIUM confidence)
- [Voronoi City Generation (Game Dev Indie)](https://gamedevindie.com/city-procedural-generation-voronoi-approach/) -- Implementation walkthrough
- [Red Blob Games - Polygonal Map Generation](http://www-cs-students.stanford.edu/~amitp/game-programming/polygon-map-generation/) -- Voronoi-based map generation
- [Wayfinding - Level Design Book](https://book.leveldesignbook.com/process/blockout/wayfinding) -- Player navigation patterns
- [Planning Video Game Cities](https://80.lv/articles/planning-of-video-game-cities) -- City design principles
- [Kevin Lynch - Image of the City concepts](https://en.wikipedia.org/wiki/The_Image_of_the_City) -- Paths, edges, districts, nodes, landmarks

### Tertiary (LOW confidence -- needs validation)
- [Medieval Town Defense Strategies (MedievalChronicles)](https://www.medievalchronicles.com/medieval-battles-wars/medieval-warfare/defending-a-medieval-town-or-city-strategies-structures-and-tactics/) -- Historical defense patterns
- [GIS and Agent-Based Modeling for Cities](https://www.gisagents.org/2018/11/procedural-city-generation-beyond-game.html) -- Agent-based growth simulation

---

## Metadata

**Confidence breakdown:**
- Road generation algorithms: HIGH -- foundational papers fully documented, implementations verified
- Lot subdivision: HIGH -- already implemented in codebase, well-understood algorithms
- District design: HIGH -- historical patterns well-documented, existing system works
- Building generation: MEDIUM -- CGA grammar clear but WFC tile authoring unresolved
- NPC/liveability: MEDIUM -- design patterns established but implementation details project-specific
- Defensibility: HIGH -- historical + game design patterns well-documented

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain, algorithms don't change)
