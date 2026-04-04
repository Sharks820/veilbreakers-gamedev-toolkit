# AAA Architecture Visual Standards: Dark Fantasy Castles, Buildings, and Settlements

**Researched:** 2026-04-03
**Domain:** Visual quality standards for procedural dark fantasy architecture
**Reference Games:** Elden Ring (Stormveil Castle, Raya Lucaria), Dark Souls (Anor Londo, Undead Parish), Skyrim (Whiterun, Riften, Solitude), Bloodborne (Yharnam)
**Confidence:** HIGH (cross-referenced against shipped game analysis, historical architecture, ArtStation breakdowns, GDC presentations)
**Purpose:** Define the specific visual bar that VeilBreakers generators must hit -- not "nice to have" but minimum shipping quality

---

## Table of Contents

1. [Castle Architecture Standards](#1-castle-architecture-standards)
2. [Village and Settlement Standards](#2-village-and-settlement-standards)
3. [Individual Building Detail Standards](#3-individual-building-detail-standards)
4. [PBR Material Reference Values](#4-pbr-material-reference-values)
5. [Quality Tier Definitions](#5-quality-tier-definitions)
6. [Polygon Budget Reference](#6-polygon-budget-reference)
7. [What VeilBreakers Currently Generates vs AAA](#7-what-veilbreakers-currently-generates-vs-aaa)
8. [Actionable Gap Closure Specifications](#8-actionable-gap-closure-specifications)
9. [Sources](#9-sources)

---

## 1. Castle Architecture Standards

### 1.1 Walls: The Single Most Important Visual Element

**The Rule:** Castle walls are NOT flat planes. They are THICK volumetric structures with a walkway on top, visible from both inside and outside the castle.

**Historical Dimensions (scaled for game use):**

| Element | Real-World | Game Scale (VeilBreakers) | Notes |
|---------|-----------|--------------------------|-------|
| Curtain wall height | 9-12m (30-40 ft) | 8-12m | Scale to player height (1.8m) for correct proportions |
| Curtain wall thickness | 2.4-6m (8-20 ft) | 2-3m minimum | Must be thick enough for a walkway on top |
| Tower height | 12-20m (40-65 ft) | 15-20m | Towers MUST exceed wall height by 30-50% |
| Keep height | 18-30m (60-100 ft) | 20-30m | Tallest structure in the castle, visible from outside |
| Merlon width | 1.2-1.5m (4-5 ft) | 0.6-0.8m | Shoulder-width of a defender with shield |
| Merlon height | 0.9-2.1m (3-7 ft) | 1.0-1.5m | Chest-to-head height of a defender |
| Crenel width | 0.6-0.9m (2-3 ft) | 0.4-0.6m | One-third width of merlon (historical ratio) |
| Arrow slit width | 3-10cm external | 0.04-0.08m | Narrow on outside, wider on inside (splayed) |
| Parapet walk width | 1.5-2.5m | 1.5-2.0m | Wide enough for two soldiers to pass |
| Gatehouse depth | 3-6m | 3-5m | Extended passage increases defensive value |

**Stormveil Castle Visual Checklist (what FromSoftware gets right):**

1. **Wall thickness is ALWAYS visible.** When you look at a wall from any angle, you see it has depth. The top has a walkway. The inside face is as detailed as the outside face.
2. **Walls are NOT uniform.** Different sections show different stone colors, repair patches, moss accumulation, structural cracks. Each wall segment tells a micro-story of construction and age.
3. **Multiple vertical layers.** Walls have a base plinth (wider, darker stone), main body (lighter coursed stone), and parapet (crenellated, sometimes different stone).
4. **Buttresses and counterforts.** Thick walls have visible structural supports on the inner face, spaced every 5-8m. These are NOT decorative -- they prevent wall collapse and read as structural necessity.
5. **Wall-walks connect to towers.** The parapet walk does not just stop at a tower -- there is a doorway or passage through the tower at walkway level.

**What VeilBreakers currently does vs this standard:**

The current `generate_castle_spec()` creates walls with `wall_thickness: 1.5m` and `wall_height: 8.0m`. These are boxes -- geometrically correct proportions but missing:
- Parapet walk geometry (walkway on top of wall)
- Stone block variation per wall section
- Buttress/counterfort on inner face
- Wall base plinth (thicker/wider foundation course)
- Multiple material zones (base vs body vs parapet)

### 1.2 Towers: Vertical Punctuation

**The Rule:** Towers are the vertical rhythm of a castle silhouette. They break up long wall runs, provide overlapping fields of fire, and give the castle its recognizable skyline.

**FromSoftware/Bethesda Tower Standards:**

| Feature | Requirement | Why |
|---------|------------|-----|
| Shape | Cylindrical or D-shaped preferred | Round towers deflect projectiles, create interesting shadow gradients |
| Taper | 5-15% narrower at top vs base | Creates visual stability, "planted in ground" feeling |
| Height | 1.3-1.5x wall height minimum | Tower must command the wall-walk, provide observation |
| Crown | Crenellated, with slight overhang | Machicolations or at minimum a projecting parapet |
| Arrow slits | 3-4 per floor, staggered vertically | Cruciform shape (vertical slit + horizontal cross) |
| Interior visible | At least 1 window/opening per floor | Suggests habitable interior, adds depth |
| Base | Wider than shaft (battered base) | 10-20% wider, tapers in over first 1-2m height |
| Roof | Conical cap OR open crenellated platform | Both are valid historical options |

**Stormveil-Quality Tower Details:**
- Wooden balconies/platforms attached to tower sides at various heights
- Rope/chain details hanging from upper levels
- Different stonework at base vs upper (rougher/larger blocks at base)
- At least one window with visible depth (not a flat texture)
- Bird nests, vegetation, weather staining at upper courses

**Current VeilBreakers tower generation:**
The `_append_fortress_tower_kit()` creates octagonal towers with taper and crown height. This is geometrically sound but lacks:
- Battered base (wider foundation)
- Arrow slits on body
- Interior floor plates visible through openings
- Material variation between base and upper courses
- Surface detail (no stone blocks on tower body)

### 1.3 Gatehouse: The Castle's Face

**The Rule:** The gatehouse is the FIRST thing a player sees approaching a castle. It must communicate "this is a defended entrance" through specific architectural features.

**Required Gatehouse Elements (from shipped dark fantasy games):**

1. **Archway opening** -- NOT a flat rectangular hole. Pointed or rounded arch with individually modeled voussoir stones (wedge-shaped arch stones). The arch is the gatehouse's most visible detail.
2. **Portcullis** -- A visible iron/wood grid either raised above the opening or partially lowered. Even when raised, the bottom edge should be visible in the arch ceiling, and the slots it rides in should be visible on the side walls.
3. **Murder holes** -- Openings in the ceiling of the gate passage, visible when looking up. These are functional (defenders pour hot liquids/drop stones) and read as threatening.
4. **Flanking towers** -- The gatehouse should have two projecting towers or bastions flanking the entrance, taller than the curtain wall.
5. **Drawbridge or approach** -- A visible bridge, ramp, or raised pathway leading to the gate. Even a simple stone ramp adds depth.
6. **Gate passage depth** -- The passage through the gatehouse should be 3-5m deep minimum. This is NOT a paper-thin wall with a hole -- it is a tunnel through thick masonry.

**Current VeilBreakers gatehouse:**
The `generate_castle_spec()` creates a gatehouse from boxes with an opening and two small bastions. It has the right structural idea but lacks:
- Arch shape (currently rectangular opening)
- Portcullis geometry
- Murder hole detail
- Gate passage depth visualization
- Approach/bridge geometry

### 1.4 Keep: The Castle's Heart

**The Rule:** The keep is the tallest, most detailed structure in the castle. It should have a visually complex roofline and suggest interior habitation.

**AAA Keep Standards:**

| Feature | Specification |
|---------|--------------|
| Height | 1.5-2x tower height (20-30m in game) |
| Roofline | NOT flat. Must have at least 2 height changes: main roof ridge + secondary gable or turret |
| Chimneys | 1-3 visible chimneys, implies heating = habitation |
| Windows | Larger than wall arrow slits; upper floors have wider windows (safer from attack at height) |
| Entrance | Elevated (2nd floor entry historically), reached by external stair or forebuilding |
| Material zones | At minimum 3: foundation stone (dark, heavy), wall stone (lighter, coursed), window/door surrounds (dressed stone, different color) |
| Buttresses | Flying or simple, at corners and mid-wall; 0.3-0.5m projection |

**Stormveil / Anor Londo Keep Qualities:**
- Multiple roof levels creating complex silhouette against sky
- Large Gothic windows on upper floors (Anor Londo: pointed arch windows with tracery)
- Balconies or projecting structures at upper levels
- Visible interior through doorways/windows (light inside, furniture shapes)
- Weathering gradient: heavier at base, lighter at top (rain runs down)
- Environmental storytelling: damage marks, collapsed sections, repair work

### 1.5 Castle Materials and Weathering

**Stone Wall Material Zones (minimum 3 per castle):**

| Zone | Application | Visual Character |
|------|------------|-----------------|
| Foundation stone | Base course, 0-2m height | Largest blocks, darkest color, heavily weathered, possible moss |
| Curtain wall stone | Main wall body | Medium coursed blocks, running bond pattern, moderate weathering |
| Dressed stone | Window/door surrounds, corner quoins, arch voussoirs | Smoother, lighter color, visible chisel marks, minimal weathering |
| Parapet stone | Crenellations, tower crowns | Often different color (repair/later construction), moderate weathering |
| Timber elements | Walkway decking, hoardings, doors, shutters | Dark stained wood, visible grain, iron reinforcement |

**Weathering Direction Rules:**
- Water flows DOWN. Rain stains, moss, and algae follow gravity. Vertical streaks on walls below windows, horizontal accumulation on ledges.
- Moss grows on NORTH-facing surfaces (in northern hemisphere) and in shadowed crevices, NOT uniformly everywhere.
- High-traffic areas show WEAR (polished stone on stairs, worn door handles) not weathering.
- Upper surfaces accumulate bird droppings, lichen. Lower surfaces accumulate splash-back staining.
- Repair patches use different stone color/size -- they are evidence of history.

### 1.6 Scale Reference (Human-Relative)

All dimensions assume player character height of 1.8m:

| Element | Height in Players | Meters |
|---------|------------------|--------|
| Doorway | 1.2x | 2.1-2.4m |
| Ground floor ceiling | 1.7x | 3.0-3.5m |
| Upper floor ceiling | 1.5x | 2.7-3.0m |
| Great hall ceiling | 4-5x | 7-9m |
| Curtain wall | 4.5-6.5x | 8-12m |
| Tower | 8-11x | 15-20m |
| Keep | 11-17x | 20-30m |
| Castle gate opening | 2-2.5x wide, 1.7-2x tall | 3.5-4.5m wide, 3-3.5m tall |
| Arrow slit | 0.02-0.04x wide | 0.04-0.08m external |
| Merlon | 0.5-0.8x tall | 1.0-1.5m |
| Stair tread | 0.15x rise | 0.17-0.20m rise, 0.25-0.30m run |

---

## 2. Village and Settlement Standards

### 2.1 The Cardinal Rule: No Two Buildings Identical

**Reference: Riften (Skyrim), Roundtable Hold (Elden Ring), Hateno Village (BotW)**

In every shipped AAA dark fantasy settlement, EACH building is visually distinct. This does not mean each building is a unique model -- it means each building has enough parameter variation to read as unique:

| Variation Axis | Minimum Range | Example |
|---------------|--------------|---------|
| Roof pitch angle | 30-55 degrees | Steep Nordic vs shallow Mediterranean |
| Building height | 1-3 floors | Varied skyline, not uniform blocks |
| Footprint shape | Rectangular, L-shaped, T-shaped | Not all buildings are simple rectangles |
| Material mix | 3-5 material combos per settlement | Stone-timber, all-timber, stone-slate, wattle-and-daub |
| Roof material | Thatch, shingle, slate, tile | Mix within settlement (wealth gradient) |
| Age/condition | New, weathered, damaged, repaired | Each building at different point in life |
| Architectural details | Shutters, balconies, awnings, signs | Unique combination per building |

**Riften Specifics (dark fantasy town reference):**
- Horizontal log construction (Scandinavian influence) with chunky logs crossing at corners
- Wooden shake shingle roofs (maintenance-heavy, shows age variation)
- City split by canal -- Dryside (residential) vs Plankside (commercial, built on wooden docks over water)
- Buildings on Plankside built atop wooden pier structures, showing the structural timber underneath
- Confined dark spaces: narrow alleys, overhanging upper stories, limited sunlight = dark fantasy atmosphere
- Visible age: moss/ivy on walls, weeds at foundations, mulch-covered paths
- Central circular plaza with well/fountain as orientation landmark

### 2.2 Street and Path Standards

**The Rule:** Streets are NOT flat terrain. They are distinct surfaces with visible construction.

| Street Type | Surface | Width | When to Use |
|------------|---------|-------|-------------|
| Main road (cobblestone) | Individual stone blocks visible, with mortar gaps | 4-8m | Town main street, market approach |
| Secondary street (packed earth) | Compressed dirt, wagon ruts, darker color than terrain | 2-4m | Residential streets |
| Alley | Narrow dirt or worn stone, debris, puddles | 0.8-2m | Between buildings, shortcut paths |
| Dock/pier | Visible planking with gaps between boards | 2-3m | Waterfront areas (Riften reference) |
| Castle approach | Formal stone or gravel, wider at gate | 5-8m | Leading to castle/keep |

**Street Detail Requirements:**
- Edges are NOT perfectly straight -- slight irregularity in stone placement
- Drainage channels visible at street edges or center (medieval streets crown slightly for rain runoff)
- Intersections are wider than mid-block sections (natural widening from traffic)
- Steps where streets change elevation (not smooth ramps -- medieval streets had steps on slopes)

### 2.3 Market and Commercial Areas

**The Rule:** Markets are NOT empty plazas with a few crates. They are dense, active-looking commercial zones.

**Market Square Required Elements:**

| Element | Count | Details |
|---------|-------|---------|
| Market stalls | 4-8 per market | Canvas/cloth canopy on timber frame, counter surface, goods displayed |
| Barrels and crates | 3-5 per stall | Grouped logically near the stall they belong to, NOT randomly scattered |
| Central feature | 1 | Well, fountain, market cross, or stocks/pillory |
| Benches | 2-4 | Near central feature or along edges |
| Signage | 1 per shop building | Hanging signs with trade symbols (anvil for smith, boot for cobbler) |
| Ground clutter | continuous | Straw on ground near animal areas, spilled goods near stalls, mud patches |

**Shop-Type Contextual Props (must match building function):**

| Building Type | Required Exterior Props | Required Interior Props |
|--------------|------------------------|------------------------|
| Blacksmith | Anvil, forge chimney (smoke), water trough, metal scraps | Bellows, tongs rack, horseshoe collection, coal pile |
| Tavern/Inn | Outdoor benches, barrel stack, hanging lantern, welcome sign | Bar counter, mugs/tankards, fireplace, keg rack |
| General store | Crates/barrels outside, awning, hanging goods | Shelves with varied items, counter, scales |
| Church/shrine | Graveyard adjacent, candles/offerings at entrance | Altar, pews/benches, religious symbols, candelabra |
| Bakery | Chimney (smoke), flour sacks outside | Oven, bread racks, flour-dusted surfaces |
| Apothecary | Hanging herbs at entrance, mortar+pestle sign | Shelves of bottles, dried herbs, cauldron |

### 2.4 Prop Placement Rules

**Anti-Pattern: Random Scatter**
NEVER place props using uniform random distribution. Props must follow CONTEXTUAL placement rules:

1. **Proximity rule:** Props relate to the nearest building. Blacksmith tools near the blacksmith, NOT near the church.
2. **Gravity rule:** Small props sit ON surfaces (tables, shelves, ground), not floating. Hanging props hang FROM structures (eaves, hooks, poles).
3. **Traffic rule:** Props do not block walkways. Crates/barrels pushed against walls, not in the middle of roads.
4. **Cluster rule:** Props come in groups of 2-5 related items, not single isolated objects. Three barrels together, not one barrel alone.
5. **Story rule:** Each prop cluster should suggest an activity. A chair + table + mug = someone was sitting here. An overturned cart + scattered goods = something happened here.

### 2.5 Settlement Perimeter and Transition

**The Rule:** Settlements do not have hard edges. They transition gradually into wilderness.

**Transition Zones (from center outward):**

| Zone | Distance from center | Density | Elements |
|------|---------------------|---------|----------|
| Core | 0-30% radius | Dense | Main buildings, market, paved streets |
| Inner ring | 30-60% | Medium | Residential, some gardens, packed earth streets |
| Outer ring | 60-80% | Sparse | Sheds, animal pens, fields, dirt paths |
| Perimeter | 80-95% | Minimal | Walls/fences (if fortified), guard posts, cleared ground |
| Transition | 95-120% | Scattered | Refuse piles, dead trees, worn paths into wilderness |

---

## 3. Individual Building Detail Standards

### 3.1 Doors

**The Rule:** Doors are the most interacted-with element. They must have visible 3D depth, not flat planes.

**Door Specification:**

| Feature | Measurement | Detail |
|---------|------------|--------|
| Width | 0.9-1.2m (single), 1.5-2.0m (double) | Slightly wider than player |
| Height | 2.0-2.4m | Player can walk through without ducking |
| Thickness | 0.06-0.10m | Visible as edge geometry when open |
| Frame depth | 0.15-0.25m | Recessed into wall, creates shadow depth |
| Frame width | 0.10-0.15m | Visible surround, often different material |
| Hinges | 2-3 per door | Iron strap hinges, visible on face or edge |
| Handle | 1 per door side | Iron ring pull, lever, or bar handle at 1.0m height |
| Threshold | 0.05-0.10m step | Raised stone or wood sill, prevents water ingress |

**Door Types by Building:**
- **Castle/Keep:** Heavy oak planks with iron reinforcement bands, large iron ring handles, possibly studded
- **Tavern:** Heavy but welcoming, possibly with a small window/peephole, iron latch
- **Cottage/House:** Simple plank construction, leather or iron hinges, wood latch
- **Church:** Tall pointed arch, possibly double, carved stone surround, iron fittings
- **Dungeon/Cell:** Iron-banded, small barred window, heavy lock plate

### 3.2 Windows

**The Rule:** Windows show building status. Rich buildings have larger, more decorated windows. Poor buildings have small shuttered openings.

**Window Types (by wealth level):**

| Type | Width | Height | Details | Used For |
|------|-------|--------|---------|----------|
| Arrow slit | 0.04-0.08m | 0.4-0.8m | Splayed interior, cruciform optional | Castle walls, towers |
| Shuttered opening | 0.4-0.6m | 0.5-0.7m | Wood shutters (hinged), no glass | Poor houses, cottages |
| Mullioned window | 0.6-1.0m | 0.8-1.2m | Stone mullion dividing panes, possible glass | Merchant houses |
| Gothic window | 0.8-1.5m | 1.5-3.0m | Pointed arch, tracery, leaded glass | Churches, keeps, guild halls |
| Rose window | 1.5-3.0m diameter | circular | Radial tracery, colored glass | Cathedral/church facade |

**Window Detail Requirements:**
- **Depth:** Window opening recessed at least 0.15m into wall (creates shadow)
- **Sill:** Stone or wood sill projecting 0.03-0.05m from wall face
- **Shutters:** If present, modeled as separate elements (openable or permanently fixed open/closed)
- **Interior light:** Inhabited buildings should show warm light through windows (point light or emissive plane behind window)
- **Frame:** Visible stone or timber frame, different material from wall

### 3.3 Roofs

**The Rule:** Roofs are the most visible element from distance. They define the building's silhouette and communicate building type.

**Roof Standards:**

| Feature | Specification |
|---------|--------------|
| Pitch angle | 30-55 degrees (steeper in rainy/snowy climates -- dark fantasy = steeper) |
| Overhang | 0.3-0.6m beyond wall face (eaves) -- provides shadow line and weather protection |
| Ridge line | NOT perfectly straight -- slight sag in middle (0.05-0.1m dip) for aged buildings |
| Material thickness | Thatch: 0.2-0.4m visible edge, Tile/shingle: 0.03-0.05m visible edge |
| Dormer windows | 1-2 per roof for buildings 2+ floors (breaks up large roof surfaces) |
| Chimneys | 1-3 per inhabited building, positioned off-center (NOT dead center of ridge) |

**Roof Material Variants:**

| Material | Texture | Edge Profile | Color Range | Wealth Level |
|----------|---------|-------------|-------------|-------------|
| Thatch | Bundled straw, visible grass bundles | Thick rounded edge, overhanging | Golden yellow to dark brown | Poor |
| Wood shake | Overlapping rectangular shingles, visible gaps | Layered edge, slight curl | Grey-brown (weathered) to dark brown | Middle |
| Slate tile | Overlapping flat rectangles, uniform | Thin crisp edge | Dark grey to blue-grey | Wealthy |
| Clay tile | Curved interlocking S-profiles | Wavy edge | Terracotta to dark red-brown | Mediterranean/wealthy |

**Roof Geometry (not texture-only):**
AAA roofs have individual tile/shingle geometry, at least at the edges and ridge line. The interior of the roof surface can use a flat plane with normal-mapped tiles, but edges must show individual elements:
- Ridge cap tiles along the peak
- Starter course along the eaves (visible individual tiles)
- Hip/valley tiles where roof planes meet

### 3.4 Chimneys

**The Rule:** Chimneys signal habitation. Every inhabited building needs at least one chimney, and it must be 3D geometry, not a texture.

**Chimney Specifications:**

| Feature | Measurement |
|---------|------------|
| Width | 0.4-0.8m |
| Depth | 0.4-0.8m |
| Height above roof ridge | 0.6-1.5m |
| Cap overhang | 0.05-0.10m on each side |
| Pot/cap | Visible topping element (stone cap, clay pot, or metal cowl) |
| Smoke | Particle effect (wisps) for inhabited buildings, absent for abandoned |

**Chimney Details:**
- Built from different material than main wall (often brick even on stone buildings)
- Slightly wider at base where it meets the roof (flashing detail)
- Visible brick/stone courses (not a smooth box)
- Soot staining on chimney face and adjacent roof area
- Position: offset from roof center, located above the fireplace inside

### 3.5 Hanging Signs

**The Rule:** Every shop/commercial building needs a hanging sign that communicates its function without text.

**Sign Specifications:**

| Feature | Measurement |
|---------|------------|
| Sign board | 0.4-0.6m wide, 0.3-0.4m tall |
| Bracket | Iron scrollwork, projecting 0.4-0.6m from wall |
| Mounting height | 2.5-3.0m (above doorway, visible while walking) |
| Chain/rope | Visible hanging mechanism (2 chains or rope loops) |
| Symbol | Trade symbol carved/painted (anvil, mug, key, boot, etc.) |

---

## 4. PBR Material Reference Values

### 4.1 Stone Materials

| Material | Base Color (sRGB range) | Roughness | Metallic | Notes |
|----------|------------------------|-----------|----------|-------|
| Granite (dark) | 80-120 across channels | 0.7-0.9 | 0.0 | Foundation stone, heavy weathering |
| Limestone (light) | 160-200 across channels | 0.6-0.85 | 0.0 | Dressed stone, door/window surrounds |
| Sandstone | R:170-200, G:140-170, B:100-130 | 0.65-0.85 | 0.0 | Wall body, warm tone |
| Cobblestone | 100-150 across channels | 0.75-0.95 | 0.0 | Street surfaces, irregular shapes |
| Slate | 60-90, slight blue shift | 0.5-0.7 | 0.0 | Roof tiles, smoother than wall stone |
| Brick | R:160-200, G:80-110, B:60-80 | 0.7-0.9 | 0.0 | Chimneys, some walls |
| Mortar | 140-170 across channels | 0.8-0.95 | 0.0 | Between stone blocks, recessed |
| Moss-covered stone | R:60-90, G:80-120, B:50-70 | 0.85-0.95 | 0.0 | North-facing, shaded, wet areas |

### 4.2 Wood Materials

| Material | Base Color (sRGB range) | Roughness | Metallic | Notes |
|----------|------------------------|-----------|----------|-------|
| Oak (fresh) | R:140-170, G:100-130, B:60-80 | 0.5-0.7 | 0.0 | Structural timber, indoor floors |
| Oak (weathered) | R:100-130, G:90-110, B:70-90 | 0.65-0.85 | 0.0 | Exterior timber, grey-brown shift |
| Pine (fresh) | R:180-210, G:150-170, B:100-120 | 0.45-0.65 | 0.0 | Light construction, scaffolding |
| Pine (weathered) | R:130-160, G:120-140, B:100-120 | 0.6-0.8 | 0.0 | Aged structural timber |
| Dark stained wood | R:50-80, G:35-55, B:25-40 | 0.4-0.6 | 0.0 | Doors, furniture, decorative elements |
| Charred/burnt wood | R:30-50, G:25-40, B:20-35 | 0.8-0.95 | 0.0 | Fire damage, forge areas |
| Thatch/straw | R:170-200, G:150-170, B:80-110 | 0.85-0.95 | 0.0 | Roof material, very rough |

### 4.3 Metal Materials

| Material | Base Color (sRGB range) | Roughness | Metallic | Notes |
|----------|------------------------|-----------|----------|-------|
| Iron (clean) | 135-145 across channels | 0.4-0.6 | 1.0 | Fresh ironwork, rarely seen |
| Iron (rusted) | R:120-160, G:60-80, B:40-55 | 0.7-0.9 | 0.3-0.6 | Common dark fantasy iron, mix metallic with rust |
| Iron (heavily rusted) | R:100-140, G:45-65, B:30-45 | 0.8-0.95 | 0.0-0.2 | Ancient ironwork, mostly dielectric |
| Steel (polished) | 170-185 across channels | 0.15-0.35 | 1.0 | Weapons, armor, rare in architecture |
| Copper (fresh) | R:210, G:140, B:100 | 0.3-0.5 | 1.0 | New copper fittings |
| Copper (patina) | R:70-100, G:130-160, B:110-140 | 0.5-0.7 | 0.3-0.5 | Aged copper, green verdigris |
| Bronze | R:180-200, G:140-160, B:80-100 | 0.35-0.55 | 1.0 | Bell castings, decorative fittings |
| Lead | 110-130 across channels | 0.5-0.7 | 1.0 | Roof flashing, window cames |

### 4.4 Other Materials

| Material | Base Color (sRGB range) | Roughness | Metallic | Notes |
|----------|------------------------|-----------|----------|-------|
| Leather | R:80-120, G:50-80, B:30-50 | 0.5-0.7 | 0.0 | Door coverings, furnishings |
| Canvas/cloth | R:160-200, G:150-180, B:130-160 | 0.8-0.95 | 0.0 | Market stall canopies, banners |
| Packed earth | R:110-140, G:90-110, B:60-80 | 0.85-0.95 | 0.0 | Dirt paths, unpaved streets |
| Mud/wet earth | R:70-100, G:55-75, B:35-55 | 0.5-0.7 | 0.0 | Puddles, wet ground |
| Glass (leaded) | R:150-200, G:170-210, B:160-200 | 0.05-0.2 | 0.0 | Church windows, wealthy buildings |

### 4.5 Critical PBR Rules

1. **Non-metals are ALWAYS metallic = 0.0.** Stone, wood, leather, cloth, thatch -- all 0.0 metallic. No exceptions.
2. **Metals are ALWAYS metallic = 1.0.** Iron, steel, copper, bronze, gold -- all 1.0. The ONLY exception is heavily rusted metal where the rust layer is dielectric (0.0).
3. **Partially rusted metal:** Use a metallic mask texture -- pure metal areas = 1.0, rust areas = 0.0, transition zone = gradient. Do NOT set metallic to 0.5 uniformly.
4. **Darkest base color for non-metals:** Never go below sRGB 30-50 (linear 0.003-0.01). Pure black non-metals do not exist.
5. **Lightest base color for non-metals:** Never exceed sRGB 240 (linear 0.9). Snow is about 230-240.
6. **Roughness correlates with wear.** Unworn surfaces are rough. High-traffic surfaces are smooth (polished by contact). This is counterintuitive but physically correct.

---

## 5. Quality Tier Definitions

### Tier 0: PLACEHOLDER (unshippable)

**Visual:** Cubes and cylinders with default grey material. No openings, no detail, no material variation. Looks like a blockout/greybox.

**Characteristics:**
- Single primitive per building (cube = house, cylinder = tower)
- No doors, no windows, no roof geometry
- Default material or single flat color
- No foundation or terrain interaction
- Identical dimensions between buildings
- 10-100 triangles per building

**When acceptable:** Very early prototyping only. Never in player-facing builds.

### Tier 1: BASIC (pre-alpha)

**Visual:** Correct proportions and general shape. Buildings have walls, a roof, and a door opening. Single material per building. Everything is clean and new.

**Characteristics:**
- Correct height-to-width proportions
- Roof is a single angled plane (no tiles, no overhang)
- Door is a hole in the wall (no frame, no door mesh)
- Windows are flat textures or simple holes
- Single material/color per building
- No weathering, no detail, no props
- 100-500 triangles per building

**Missing:** Visual interest, material variation, micro-detail, environmental context.

### Tier 2: DECENT (alpha)

**Visual:** Multi-material buildings with some architectural detail. Roof has visible pitch and material. Doors and windows exist as 3D elements. Some repetition between buildings is obvious.

**Characteristics:**
- 2-3 materials per building (wall, roof, trim)
- Roof has edge overhang and visible material (thatch/tiles)
- Door mesh exists with visible thickness
- Window shutters or frames present
- Some timber framing visible
- Foundation or base course present
- 500-2,000 triangles per building
- Buildings share identical detail kits (same window repeated)

**Missing:** Unique per-building character, weathering, contextual props, micro-detail.

### Tier 3: GOOD (beta)

**Visual:** Each building reads as unique. Multiple material zones with variation. Architectural details present (chimneys, signs, balconies). Some weathering. Missing the final layer of micro-detail and environmental integration.

**Characteristics:**
- 3-5 materials per building with variation
- Unique combinations of doors, windows, roof style per building
- Chimney with visible construction
- Hanging sign for commercial buildings
- Some weathering (but uniform, not directional)
- Contextual props near buildings (but limited)
- Foundation integrates with terrain
- 2,000-10,000 triangles per building
- Interior visible through doors/windows (basic)

**Missing:** Directional weathering, repair patches, lived-in micro-detail, environmental storytelling.

### Tier 4: AAA (shipping quality -- the Stormveil standard)

**Visual:** Every surface tells a story. Materials are directionally weathered. Buildings show age, use, repair, and context. Silhouettes are varied and interesting. Environmental storytelling is baked into every prop placement. Looking at a building, you can infer who lived here, what they did, and what happened.

**Characteristics:**
- 5+ material zones per building, each with unique weathering
- Directional weathering (rain down walls, moss on north faces, wear on touched surfaces)
- Repair patches visible (different stone color, replaced timber)
- Unique silhouette per building (chimneys, dormers, varied roofline)
- Environmental storytelling props (3-5 narrative vignettes per building)
- Interior fully visible through openings (furniture, light, occupancy signals)
- Foundation variable height adapting to terrain slope
- 10,000-50,000 triangles per hero building
- Multiple LOD levels (3-4) for performance
- Decal overlays (grout, stains, edge wear) at material boundaries
- Particle effects (chimney smoke, firefly sparkles, dust motes)
- Sound zones (crackling fire, hammering, crowd murmur)

**The "Three Stories" Test:** Can a player look at this building and infer at least three things about it? (1) What it was used for, (2) How old it is, (3) What condition it is in. If yes, it passes AAA.

---

## 6. Polygon Budget Reference

### 6.1 Per-Asset Triangle Budgets

Based on shipped AAA games (PS5/XSX/PC era, 2022-2025):

| Asset Type | LOD0 (close) | LOD1 (mid) | LOD2 (far) | LOD3 (distant) |
|-----------|-------------|-----------|-----------|---------------|
| Hero building (keep/cathedral) | 30,000-50,000 | 10,000-15,000 | 3,000-5,000 | 500-1,000 |
| Standard building (house/shop) | 5,000-15,000 | 2,000-5,000 | 500-1,500 | 100-300 |
| Castle wall segment (10m) | 3,000-8,000 | 1,000-3,000 | 300-800 | 50-150 |
| Tower | 8,000-20,000 | 3,000-7,000 | 1,000-2,500 | 200-500 |
| Door (with frame) | 500-2,000 | 200-500 | 50-100 | merged |
| Window (with frame) | 300-1,000 | 100-300 | 30-80 | merged |
| Market stall | 1,000-3,000 | 300-1,000 | 100-300 | merged |
| Prop cluster (barrels/crates) | 500-2,000 | 200-500 | 50-150 | merged |
| Chimney | 200-800 | 100-300 | 30-80 | merged |
| Hanging sign | 100-400 | 50-150 | merged | merged |

### 6.2 Scene Budgets

| Scene Type | Total Triangle Budget | Building Count | Props |
|-----------|---------------------|---------------|-------|
| Village (small) | 200K-500K | 4-8 buildings | 50-150 props |
| Town (medium) | 500K-2M | 8-20 buildings | 150-500 props |
| Castle complex | 500K-1.5M | Keep + 4-8 structures | 100-300 props |
| City district | 1M-5M | 20-50 buildings | 500-2,000 props |

### 6.3 Texture Budget

| Asset Type | Texture Resolution | Maps Required |
|-----------|-------------------|---------------|
| Hero building | 2K-4K atlas or trim sheet | Base Color, Normal, ORM (packed) |
| Standard building | 1K-2K atlas or trim sheet | Base Color, Normal, ORM |
| Prop | 512-1K | Base Color, Normal, ORM |
| Terrain material | 1K-2K tiling | Base Color, Normal, ORM, Height |

**Texel Density Standard:** 512 pixels per meter for hero assets at closest viewing distance. 256 px/m for standard buildings. 128 px/m for distant/background structures.

---

## 7. What VeilBreakers Currently Generates vs AAA

### 7.1 Castle Generation Gap Analysis

| Feature | Current (v8.0) | AAA Standard | Gap |
|---------|---------------|-------------|-----|
| Wall thickness | 1.5m (adequate) | 2-3m | Needs increase to 2.0m minimum |
| Wall walkway | Parapet walk geometry exists | Full walkable surface with guard rails | Present but thin |
| Merlons | Correct dimensions (0.6m wide, 0.8m tall) | 0.6-0.8m wide, 1.0-1.5m tall | Height should increase to 1.0m+ |
| Arrow slits | Present in merlons | Present in merlons AND wall body | Need wall-body slits too |
| Machicolations | Present with corbels | Present with murder holes | Current is good |
| Stone block surface | Individual blocks on both faces | Per-section variation with repair patches | Need variation per wall segment |
| Tower shape | Octagonal with taper | Cylindrical with battered base | Need battered base, more segments |
| Tower arrow slits | Not present on body | 3-4 per floor | MISSING |
| Tower interior | Not generated | Floor plates visible through openings | MISSING |
| Gatehouse arch | Rectangular opening | Pointed/rounded arch with voussoirs | MISSING arch geometry |
| Portcullis | Not generated | Visible iron grid | MISSING |
| Keep roofline | Single crown turret | Multiple height changes, dormers, chimneys | Needs complexity |
| Material zones | Single "stone_fortified" | 3-5 zones (foundation, body, dressed, parapet, timber) | MISSING variation |
| Weathering | Uniform (via material) | Directional per surface | MISSING |
| Foundation | Stone plinth exists | Variable-height stepped foundation | Needs terrain adaptation |

### 7.2 Settlement Generation Gap Analysis

| Feature | Current (v8.0) | AAA Standard | Gap |
|---------|---------------|-------------|-----|
| Building uniqueness | Type variation (house/forge/shrine) | Per-building parameter variation | Need more axes of variation |
| Street surface | Road type assigned | Visible cobblestone/dirt geometry | Need surface geometry |
| Market area | "market_stall_cluster" type exists | Dense props, stalls, central feature | Needs expansion |
| Contextual props | Basic prop manifest | Function-matched props per building type | Need contextual rules |
| Settlement transition | Hard boundary | Gradual density falloff | MISSING |
| Building-terrain interface | Terrain flatten exists | Variable foundation height | Exists but needs refinement |
| Hanging signs | Not generated | Per-shop signs with trade symbols | MISSING |
| Settlement atmosphere | Not addressed | Dark/confined alleys, varied lighting | MISSING |

### 7.3 Building Detail Gap Analysis

| Feature | Current (v8.0) | AAA Standard | Gap |
|---------|---------------|-------------|-----|
| Door 3D geometry | Door openings exist | Full door mesh with hinges, handle, frame, thickness | Partial (openings only) |
| Window geometry | Gothic window generator exists | Multiple window types by building wealth | Need type variety |
| Roof detail | Individual tile/shingle generation exists | Edge tiles, ridge cap, dormers | Need edge detail |
| Chimney | Generator exists | Smoke particle, soot staining | Need particles |
| Interior visibility | Interior layout generator exists | Light through windows, visible furniture | Need visual integration |
| Timber framing | Generator exists | Jettied upper floors (overhang) | Need jetty/overhang |
| Building signs | Not generated | Hanging signs per shop type | MISSING |
| Balconies/porches | Not generated | Projecting structures on upper floors | MISSING |

---

## 8. Actionable Gap Closure Specifications

### 8.1 Priority 1: Castle Walls (highest visual impact)

**Changes to `generate_battlements()`:**
1. Increase default `wall_thickness` from 1.5m to 2.5m
2. Increase `merlon_h` from 0.8m to 1.2m
3. Add wall base plinth: wider foundation course (wall_thickness * 1.3 wide, 0.5m tall)
4. Add inner-face buttresses every 6-8m (0.3m projection, wall_height * 0.7 tall)
5. Add arrow slits in wall body (not just merlons): 1 per 3m of wall length, at 60% wall height
6. Add material zone markers: "foundation" (0-0.5m), "wall_body" (0.5m-top), "parapet" (crenellations)

**Changes to `generate_castle_spec()`:**
1. Add gatehouse arch geometry (pointed arch using existing `_arch_curve()`)
2. Add portcullis mesh (iron grid with vertical bars 0.05m wide, 0.15m spacing, horizontal bars at 0.3m intervals)
3. Add tower arrow slits (3 per floor, staggered)
4. Add tower battered base (10% wider than shaft, first 1.5m height)
5. Add keep chimneys (2-3 per keep, offset from center)
6. Add keep dormer windows on roof

### 8.2 Priority 2: Building Individuality (settlement quality)

**Changes to settlement generator:**
1. Per-building randomized roof pitch (30-55 degrees)
2. Per-building randomized material combination (from 5 presets)
3. Per-building randomized detail set (shutters Y/N, balcony Y/N, chimney count 1-3)
4. Contextual prop rules per building type (see Section 2.3 table)
5. Hanging sign generation for commercial buildings
6. Settlement density falloff from center to edge

### 8.3 Priority 3: Weathering System (visual polish)

**New weathering system needed:**
1. Vertical rain streak overlay: darker streaks below window sills, ledges, cornices
2. Moss/lichen placement: north-facing surfaces, crevices, base of walls
3. Wear patterns: lighter/smoother stone on stairs, door thresholds, walkway centers
4. Repair patches: different stone color blocks inserted into wall grid (1-3 per wall segment)
5. Age gradient: more weathering at base (splash-back), less at top

### 8.4 Priority 4: Door and Window Detail (close-up quality)

**Door mesh generator needed:**
1. Plank construction (4-6 vertical planks, 0.15-0.2m wide each)
2. Iron cross-bands (horizontal reinforcement bars)
3. Iron ring handle (torus geometry at 1.0m height)
4. Strap hinges (2-3 per door, extending 0.2m across door face)
5. Frame (recessed 0.15-0.25m into wall, stone or timber surround)
6. Threshold step (0.05-0.1m raised sill)

**Window type variety:**
1. Shuttered opening (poor): simple rectangular hole + 2 shutter meshes
2. Mullioned window (middle): stone divider + glass panes
3. Gothic window (rich): pointed arch + tracery (existing generator covers this)

---

## 9. Sources

### Primary References (shipped games)

- [Stormveil Castle analysis -- GameSpot](https://www.gamespot.com/articles/how-stormveil-castle-embodies-the-brilliance-of-elden-ring/1100-6510147/) -- Interlocking paths, verticality, rooftop exploration, architectural compression/expansion
- [Stormveil Castle fan recreation -- ArtStation (Upsurge Studios)](https://www.artstation.com/artwork/LexEOP) -- 3D recreation with accurate proportions
- [Anor Londo Gothic Architecture -- Archaesthetic](https://archaesthetic.com/the-gothic-architecture-of-anor-londo/) -- Il Duomo Milan inspiration, Gothic structural elements, symmetry as narrative tool
- [Anor Londo Wikipedia](https://en.wikipedia.org/wiki/Anor_Londo) -- Design philosophy, Miyazaki's vision for cohesive late-medieval architecture
- [Exploring Skyrim's Architecture: Riften -- Medium (Deerest)](https://mydeerestdivine.medium.com/exploring-skyrims-architecture-riften-4ea8616834) -- Scandinavian timber construction, canal system, shake roofing, Mistveil Keep, Temple of Mara
- [Exploring Skyrim's Architecture: Whiterun -- Medium (Deerest)](https://mydeerestdivine.medium.com/exploring-skyrims-architecture-whiterun-8b49bceb7352) -- Nordic architecture analysis
- [Skyrim's Modular Level Design -- GDC 2013 (Joel Burgess)](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html) -- Kit-based building system, snap grids, modular reuse principles

### Architecture and Construction References

- [Castle Walls Architecture -- CastlesAndManorHouses.com](https://www.castlesandmanorhouses.com/architecture_03_walls.htm) -- Wall thickness 2.4-6m, height 9-12m, embrasure splaying
- [Medieval Fortification -- Wikipedia](https://en.wikipedia.org/wiki/Medieval_fortification) -- Wall dimensions, tower spacing, gatehouse design
- [Medieval Castle Walls -- Revisiting History](https://www.revisitinghistory.com/medieval/castle-walls/) -- Thickness-to-height ratios, construction techniques
- [Battlement -- Wikipedia](https://en.wikipedia.org/wiki/Battlement) -- Merlon 4-5ft wide, 3-7ft tall; crenel 2-3ft wide; one-third ratio
- [Merlon -- Wikipedia](https://en.wikipedia.org/wiki/Merlon) -- Ghibelline vs Guelph styles, arrow loop integration
- [Crenellations: Crowning Castles -- Medievalists.net](https://www.medievalists.net/2017/01/crenellations-crowning-castles/) -- Dimensional specifications, defensive function

### 3D Art and Technical Standards

- [Crafting Elden Ring-Style Cathedral -- 80.lv](https://80.lv/articles/crafting-elden-ring-style-cathedral-environment-inspired-by-real-life-architecture) -- Trim sheet approach, baked normal + RGBA mask, UV0/UV1 workflow
- [Dark Fantasy Kitbash Environment Pack -- ArtStation](https://www.artstation.com/marketplace/p/jNqMn/dark-fantasy-kitbash-environment-pack) -- Modular + decorative element library approach
- [Texel Density Reference Sheet -- ArtStation (ingbue)](https://www.artstation.com/ingbue/blog/odK9/texel-density-texture-map-resolutions-reference-sheet) -- 512px/m standard for hero assets
- [KitBash3D Medieval Siege](https://kitbash3d.com/products/medieval-siege) -- 265 modular pieces, production kit approach
- [PBR Guide Part 2 -- Adobe Substance 3D](https://substance3d.adobe.com/tutorials/courses/the-pbr-guide-part-2) -- Albedo ranges, metallic binary rule, roughness correlations
- [Physically Based Values Database](https://physicallybased.info/) -- Reference IOR and color values for common materials
- [PBR Value Lists -- Polycount](https://polycount.com/discussion/136216/pbr-value-lists) -- Community-maintained material reference values
- [Modular Environments -- Polycount Wiki](http://wiki.polycount.com/wiki/Modular_environments) -- Snap grid standards, kit piece design
- [Environmental Storytelling in Game Design -- GameDesignSkills](https://gamedesignskills.com/game-design/environmental-storytelling/) -- Prop placement as narrative, lived-in design principles

### Existing VeilBreakers Research (internal)

- `.planning/research/AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md` -- Settlement generation patterns, terrain-building interface, THE FINALS feature node architecture
- `.planning/research/gothic_architecture_rules_research.md` -- Gothic structural element specifications
- `.planning/research/modular_building_kits_research.md` -- Kit-based building system design
- `.planning/research/MEDIEVAL_TOWN_CASTLE_ARCHITECTURE.md` -- Historical town layout patterns

---

## Appendix A: Quick Reference Card

### Castle Wall Minimum Checklist

- [ ] Thickness >= 2.0m (walkway on top)
- [ ] Merlons 0.6-0.8m wide, 1.0-1.5m tall
- [ ] Crenels 0.4-0.6m wide (1/3 of merlon width)
- [ ] Arrow slits in wall body (not just merlons)
- [ ] Base plinth visible (wider foundation course)
- [ ] Inner buttresses every 6-8m
- [ ] 3+ material zones (foundation, body, parapet)
- [ ] Stone blocks visible (not smooth surface)

### Tower Minimum Checklist

- [ ] Height = 1.3-1.5x wall height
- [ ] Taper 5-15% narrower at top
- [ ] Battered base (10-20% wider, first 1-2m)
- [ ] Arrow slits (3-4 per floor, staggered)
- [ ] Crenellated crown
- [ ] At least 1 opening showing interior per floor

### Building Minimum Checklist

- [ ] 3D door with frame depth, hinges, handle
- [ ] Windows with depth (recessed 0.15m+)
- [ ] Roof with overhang (0.3-0.6m eaves)
- [ ] Chimney (inhabited buildings)
- [ ] Foundation course visible
- [ ] 3+ materials per building
- [ ] Unique among neighbors (different detail combination)

### Settlement Minimum Checklist

- [ ] No two adjacent buildings identical
- [ ] Streets have visible surface material
- [ ] Props contextual to nearest building function
- [ ] Props in clusters (2-5 related items), not isolated
- [ ] Central landmark/feature (well, fountain, tree)
- [ ] Density decreases from center outward
- [ ] Hanging signs on commercial buildings
