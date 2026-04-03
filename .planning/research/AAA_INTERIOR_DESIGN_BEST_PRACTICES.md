# AAA Interior Design Best Practices for Procedural Generation

**Researched:** 2026-04-03
**Domain:** Interior space design, environmental storytelling, procedural room generation
**Target:** VeilBreakers dark fantasy action RPG toolkit interior generation system
**Confidence:** HIGH (cross-referenced across GDC talks, academic papers, AAA analysis, historical sources)

---

## Table of Contents

1. [Room Composition Rules](#1-room-composition-rules)
2. [Medieval Building Interior Conventions](#2-medieval-building-interior-conventions)
3. [Procedural Interior Generation - State of the Art](#3-procedural-interior-generation)
4. [Environmental Storytelling Through Placement](#4-environmental-storytelling)
5. [Clutter and Detail Density](#5-clutter-and-detail-density)
6. [Functional Zones Within Rooms](#6-functional-zones)
7. [Lighting as Interior Design](#7-lighting-as-interior-design)
8. [Procedural Generation Translation Rules](#8-procedural-generation-rules)

---

<a name="1-room-composition-rules"></a>
## 1. Room Composition Rules in AAA Games

### 1.1 Focal Points

Every room needs a **focal point** -- the element that catches the player's eye upon first entering. Without one, the eye wanders aimlessly and the room feels meaningless.

**AAA Focal Point Hierarchy:**
| Room Type | Primary Focal Point | Secondary Focal Points |
|-----------|-------------------|----------------------|
| Tavern | Hearth/fireplace | Bar counter, staircase |
| Smithy | Forge (glowing fire) | Anvil, weapon display |
| Throne Room | Throne on dais | Banners, columns |
| Library | Grand bookshelf wall | Reading desk with candle, orrery/globe |
| Chapel | Altar with candles | Stained glass window, statue |
| Bedroom | Bed with canopy | Wardrobe, vanity desk |
| Kitchen | Cooking hearth | Hanging pots, butcher block |
| Dungeon Cell | Door/bars | Chains on wall, straw bed |

**Focal Point Design Rules:**
1. **Contrast of form**: The focal point should break from surrounding geometry. A round hearth in a rectangular room. A tall bookshelf against low furniture.
2. **Contrast of light**: The focal point should be the brightest or most dramatically lit element. A forge glow, candles on an altar, a fireplace.
3. **Contrast of color**: In dark fantasy, a warm amber glow against cool stone. A red banner against grey walls.
4. **Placement**: Focal points work best when visible from the entrance. The player should see it within the first 2 seconds of entering.

**Procedural Rule:** When generating a room, place the focal point FIRST, position it visible from the primary entrance, then arrange all other elements in relationship to it.

### 1.2 Spatial Hierarchy (Not "Rule of Thirds")

The Level Design Book explicitly warns against applying photography's "rule of thirds" to 3D game spaces. Instead, AAA games use **spatial hierarchy** -- making some parts of a room feel more important than others through:

- **Height variations**: A raised dais in a great hall, a sunken conversation pit, a lofted reading nook
- **Density contrast**: A cluttered work area next to an open floor for movement
- **Orientation breaks**: A diagonal piece of furniture in an otherwise grid-aligned room draws the eye
- **Shape variation**: A round table in a room of rectangular furniture

**Procedural Rule:** Assign importance weights to room zones. The focal zone gets 40% of detail budget, secondary zones get 35%, transition zones get 25%.

### 1.3 Guiding the Player's Eye Through a Room

AAA games do NOT rely on "leading lines" (the Level Design Book debunks this myth -- playtesting shows players ignore them). Instead, they use:

1. **Light beacons**: Bright spots in dark rooms pull the eye. A candle on a desk, a shaft of light from a window, a glowing forge.
2. **Color accents**: A single red object in a grey room. Gold trim on a chest. A blue potion on a shelf.
3. **Motion**: Flickering flames, swaying chains, floating dust particles, dripping water.
4. **Sound sources**: Crackling fire, bubbling cauldron, creaking wood (not visual but critical for immersion).
5. **Sightlines**: Empty space trajectories that offer views of important elements. A corridor framing a distant throne. A doorway revealing a fireplace.

**Procedural Rule:** For each room, define 2-3 "attention anchors" -- objects that are brighter, more colorful, or animated. Ensure at least one is visible from each entrance.

### 1.4 What Makes a Room Feel "Lived In"

The universal finding across all AAA analysis: **asymmetry and imperfection**.

**"Lived-In" Indicators:**
- Furniture is NOT perfectly aligned to walls (offset 2-5 degrees, pulled slightly away)
- Chairs are pushed back from tables (someone just stood up)
- Objects cluster in groups that suggest activity (plate + cup + utensils, not evenly distributed)
- Wear patterns: scuffed floors near doors, faded paint where hands touch, worn edges on table corners
- Personal items: a book left open, a half-finished meal, a garment draped over a chair
- Accumulation: dust in corners, cobwebs on unused shelves, ash around fireplace

**The "Someone Was Just Here" Effect:**
The most powerful lived-in technique is suggesting recent departure. A chair pushed back, a candle still burning, steam rising from a cup, an open door. This creates the uncanny feeling that the space is occupied even when empty.

**Procedural Rule:** After placing furniture, apply a "lived-in pass" that:
1. Rotates each piece 1-5 degrees randomly
2. Offsets each piece 0.02-0.08m from its "ideal" position
3. Adds 2-4 "activity trace" objects per furniture group (dishes on tables, tools near workbenches)
4. Pushes chairs away from tables 0.1-0.3m
5. Adds floor clutter near high-traffic areas (dirt, scuffs, dropped items)

---

<a name="2-medieval-building-interior-conventions"></a>
## 2. Medieval Building Interior Conventions

### 2.1 Tavern / Inn Layout

**Historical Basis:** Medieval taverns were NOT like modern bars. They evolved from private homes that served ale, with the "alewife" brewing in her own kitchen. The physical layout reflected this domestic origin.

**Standard Zones:**

```
[STREET]
    |
[ENTRY] ---- [COMMON ROOM] ---- [HEARTH WALL]
    |              |                    |
    |         [BAR COUNTER]        [FIREPLACE]
    |              |                    |
    |         [TABLES/BENCHES]    [BEST SEATS]
    |              |
[STAIRS UP]  [BACK AREA]
    |              |
[GUEST ROOMS] [KITCHEN]---[PANTRY]
                   |
              [CELLAR STAIRS]
                   |
              [BEER/WINE CELLAR]
```

**Key Layout Rules:**
1. **Common room** is the largest space, taking 40-60% of ground floor
2. **Hearth/fireplace** is on the far wall from entrance -- draws patrons inward
3. **Bar counter** (actually a serving hatch or trestle) is between kitchen and common room
4. **Best seats** are near the fireplace -- reserved for regulars, wealthy patrons
5. **Tables** are long communal trestle tables (not individual round tables -- those are post-medieval)
6. **Private rooms** (snugs/parlors) are small alcoves off the main room, separated by screens or half-walls
7. **Kitchen** is behind or below the common room, connected by a service passage
8. **Cellar** is below, accessed by a trapdoor or narrow stairs near the bar
9. **Guest rooms** are upstairs, accessed by a single narrow staircase
10. **Stabling** is in a separate yard building, not integrated

**Furniture Details:**
- Tables: wide planks on trestles or barrels, NOT permanent fixtures (can be collapsed for brawls/dancing)
- Seating: benches/forms, NOT individual chairs (one chair exists: the "master's chair")
- Bar: a plank counter on barrels, or a hatch window into the kitchen
- Light: central hearth provides primary light; tallow candles/rushlights on tables; lantern at door

**Procedural Rule:** Generate tavern interiors using this zone hierarchy:
```python
TAVERN_ZONES = {
    "entry": {"area_pct": 0.08, "furniture": ["door_mat", "coat_hooks", "lantern"]},
    "common": {"area_pct": 0.45, "furniture": ["trestle_table*3", "bench*6", "stool*4"]},
    "bar": {"area_pct": 0.12, "furniture": ["bar_counter", "barrel*3", "tap", "mugs_shelf"]},
    "hearth": {"area_pct": 0.15, "furniture": ["fireplace", "best_bench", "hearthstone", "fire_tools"]},
    "private_nook": {"area_pct": 0.10, "furniture": ["small_table", "bench*2", "screen_partition"]},
    "service": {"area_pct": 0.10, "furniture": ["kitchen_door", "cellar_trapdoor", "serving_shelf"]}
}
```

### 2.2 Smithy / Blacksmith Workshop Layout

**Historical Basis:** The smithy was organized entirely around workflow -- the smith moves between forge, anvil, and quench trough hundreds of times per day.

**Standard Zones:**

```
[STREET/DISPLAY FRONT]
        |
[DISPLAY ZONE] -- finished goods, customer area
        |
[WORK ZONE] -- anvil, workbench, tool racks
        |
[FORGE ZONE] -- forge, bellows, coal, chimney
        |
[QUENCH/WATER] -- slack tub, cooling area
        |
[STORAGE] -- raw materials, coal pile, scrap
```

**Key Layout Rules:**
1. **Forge** is the heart, positioned against a wall with chimney/flue (needs ventilation)
2. **Anvil** is within ONE STEP of the forge (0.5-1.0m) -- the smith must transfer hot metal instantly
3. **Slack tub** (water trough) is within arm's reach of the anvil (0.3-0.8m from anvil)
4. **Bellows** are beside or behind the forge, operated by apprentice
5. **Tool rack** is on the wall nearest the anvil -- hammers, tongs, swages, drifts hung by size
6. **Workbench** is near a window or light source for detail work (filing, polishing)
7. **Display area** faces the street -- finished goods hung or mounted where customers can see
8. **Storage** is in the back or a lean-to -- coal, iron stock, scrap metal
9. **Floor** is packed earth or stone (NOT wood -- fire hazard), covered with coal dust and scale
10. **Ceiling** is high (3-4m minimum) to allow heat to rise; blackened with soot

**The Anvil Triangle:**
The forge, anvil, and slack tub form a tight triangle. This is the most critical spatial relationship in any smithy. The smith pivots between these three points constantly.

```
        [FORGE]
       /       \
   0.8m        0.6m
     /             \
[ANVIL]---0.5m---[SLACK TUB]
```

**Procedural Rule:**
```python
SMITHY_ZONES = {
    "forge": {"area_pct": 0.25, "anchor": "forge", "requires_wall": True,
              "furniture": ["forge", "bellows", "coal_pile", "chimney"]},
    "work": {"area_pct": 0.30, "anchor": "anvil",
             "constraints": {"max_distance_from_forge": 1.0},
             "furniture": ["anvil", "slack_tub", "workbench", "tool_rack"]},
    "display": {"area_pct": 0.20, "requires_street_wall": True,
                "furniture": ["weapon_rack", "armor_stand", "display_shelf", "counter"]},
    "storage": {"area_pct": 0.15, "furniture": ["iron_stock_rack", "coal_bin", "scrap_pile"]},
    "customer": {"area_pct": 0.10, "furniture": ["counter", "stool", "price_board"]}
}
```

### 2.3 Castle Interior Organization

**Historical Basis:** Castles followed a strict public-to-private gradient with service functions carefully separated from living spaces.

**The Screens Passage Pattern:**
The single most important architectural element in medieval interiors is the **screens passage** -- a cross-corridor at the "low end" of the great hall that acts as a buffer zone between the public hall and service areas.

```
[LORD'S PRIVATE QUARTERS]     [CHAPEL]
        |                        |
    [DAIS END]              [SOLAR/STUDY]
        |
    [GREAT HALL - long rectangular space]
        |
    [SCREENS PASSAGE - cross corridor with timber screen]
     /     |        \
[BUTTERY] [KITCHEN] [PANTRY]
             |
        [LARDER]---[BAKEHOUSE]---[BREWHOUSE]
```

**Key Room Relationships:**
1. **Great Hall** is the central space, everything connects through or near it
2. **Screens Passage** separates service from public, has 2-3 doors to service rooms
3. **Dais** is at the "high end" (opposite from screens), raised 1-2 steps, where the lord sits
4. **Solar** is beyond the dais, accessed by a door behind the high table -- lord's private retreat
5. **Bedchambers** are above or adjacent to the solar, upper floors
6. **Kitchen** is SEPARATE from the hall (fire risk), connected by the screens passage
7. **Buttery** (drink storage) and **Pantry** (bread/food storage) flank the kitchen entrance
8. **Chapel** is near the great hall, sometimes two-story (lord above, servants below)
9. **Garderobe** (latrine) is in wall thickness, discharges externally
10. **Undercroft/Cellar** is below the great hall, vaulted stone, for bulk storage

**The Public-to-Private Gradient:**
```
MOST PUBLIC                                          MOST PRIVATE
Gatehouse → Courtyard → Great Hall → Solar → Bedchamber → Garderobe
                              ↓
                        Screens Passage
                              ↓
                    Kitchen/Buttery/Pantry (SERVICE)
```

**Procedural Rule:** When generating castle interiors, enforce the public-to-private gradient. Never place bedchambers adjacent to kitchens. Always place a screens passage or corridor between the great hall and service rooms. The solar must be accessible only through the great hall's high end.

### 2.4 Medieval Manor Room Relationships

**Standard Manor Adjacency Graph:**
```python
MANOR_ADJACENCY = {
    "great_hall": ["screens_passage", "solar", "chapel", "courtyard"],
    "screens_passage": ["great_hall", "buttery", "pantry", "kitchen_corridor"],
    "solar": ["great_hall", "bedchamber", "study"],
    "bedchamber": ["solar", "garderobe", "dressing_room"],
    "kitchen": ["kitchen_corridor", "larder", "pantry", "bakehouse"],
    "buttery": ["screens_passage", "cellar_stairs"],
    "pantry": ["screens_passage", "kitchen"],
    "chapel": ["great_hall", "vestry"],
    "cellar": ["cellar_stairs"],
    "courtyard": ["great_hall", "gatehouse", "stables", "well"]
}
```

### 2.5 Kitchen-to-Dining Connection

**Historical Pattern:** Kitchens were deliberately separated from dining to isolate smoke, heat, smell, and fire risk. The connection was always through an intermediary zone:

```
[GREAT HALL / DINING] ←→ [SCREENS PASSAGE] ←→ [KITCHEN CORRIDOR] ←→ [KITCHEN]
                                ↕                                        ↕
                           [BUTTERY]                               [LARDER]
                           [PANTRY]                                [BAKEHOUSE]
```

Food traveled from kitchen through the corridor, through the screens passage (where it might pause for plating), and into the hall. In larger establishments, a dedicated "servery" existed between kitchen and hall.

**Procedural Rule:** Never directly connect kitchen to dining hall. Always insert at least one intermediary room (screens passage, corridor, or servery).

---

<a name="3-procedural-interior-generation"></a>
## 3. Procedural Interior Generation - State of the Art

### 3.1 Skyrim's Creation Kit Approach

**Source:** Joel Burgess, GDC 2013 -- Skyrim's Modular Level Design

Skyrim uses a **modular kit system** where 7 art kits (Nordic, Imperial, Dwemer, Cave, Mine, Ice, Riften) are assembled by level designers into 400+ interior cells. The key insight:

**Kits are NOT rooms -- they are PIECES that make rooms:**
- Wall segments, floor tiles, ceiling pieces, pillars, doorframes
- Naming convention: `[Tileset][Type][Size][Piece][Exit][Variant]` (e.g., `NorRmSmWallSideExSm01`)
- Pieces snap to a grid (256-unit grid, with 128 and 64 subdivisions)
- Two full-time kit artists supported eight level designers

**Interior Cell Design Process:**
1. Designer creates an empty cell in the Creation Kit
2. Selects a kit (e.g., Nordic tomb) and begins placing pieces
3. Kit pieces have snap points for seamless assembly
4. Rooms are built from walls, floors, ceilings, then dressed with "clutter" sets
5. Each kit has matching clutter sets (Nordic urns, Imperial banners, Dwemer gears)
6. Lighting is placed manually with preference for baked-in light sources (wall sconces, braziers, ceiling fixtures)

**Kit-Bashing:** Designers mix pieces from different kits to create unique-feeling spaces. A Nordic tomb might have Imperial stone accents in areas where two civilizations overlapped -- this is both aesthetically interesting and environmental storytelling.

**Procedural Lesson:** Our system should maintain kit-coherent generation (a room uses primarily one tileset) but allow 10-20% cross-kit contamination for visual interest and storytelling.

### 3.2 Diablo IV Dungeon Generation

Diablo IV uses a **tile-set mixing** approach with handcrafted room templates:

1. **150+ dungeons** across 5 regions, each with distinct visual identity
2. Overworld is STATIC (handcrafted); dungeons are PROCEDURAL
3. Dungeons pull from a library of **pre-designed room templates** (tiles)
4. Templates are mixed and matched, then dressed with props, interactives, and lighting
5. Each dungeon type has rules about which tiles connect and in what order
6. Enemy population is generated separately from room layout
7. Dynamic weather and lighting create variation between runs of the same dungeon

**Key Insight:** Diablo IV's dungeons feel better than purely procedural alternatives because the individual tiles are handcrafted. The procedural system only controls WHICH tiles connect and HOW, not the internal layout of each tile.

**Procedural Lesson:** Pre-design a library of "room templates" for each room type (tavern common room, smithy work area, etc.) with internal furniture pre-placed. The procedural system selects and connects templates, then applies variation (clutter, lighting, storytelling vignettes).

### 3.3 Constraint-Based Furniture Placement (CSP)

**Source:** pvigier's blog, academic papers (Yu et al. SIGGRAPH 2011)

CSP treats furniture placement as a formal constraint satisfaction problem:

**Variables:** Objects to place (table, chair, bed, etc.)
**Domains:** All valid positions for each object (discretized grid, typically 0.1m resolution)
**Constraints:**
- **Hard:** No overlap, in-bounds, door clearance (1.0m), path connectivity
- **Soft:** Wall adjacency preference, facing direction, activity zone membership, group cohesion

**Solver Algorithm:**
1. Classify objects as Required (must place) or Optional (attempt, don't backtrack)
2. Order by MRV (Minimum Remaining Values) -- most constrained objects first
3. Backtracking search with constraint propagation (AC-3)
4. Shuffle domains each run for variety
5. After required objects placed, greedily attempt optionals

**Key Insight from Yu et al.:** Pure CSP (hard constraints only) produces VALID but UNNATURAL layouts. The best results combine hard constraints with a soft-constraint **cost function** that penalizes:
- Objects far from walls (most furniture is wall-adjacent)
- Objects not facing their intended direction (chairs face tables)
- Objects in wrong zones (cooking items not near hearth)
- Symmetric/grid-aligned placement (too artificial)

**Procedural Lesson:** Our CSP solver should have two phases: hard-constraint satisfaction (no overlap, clearances, connectivity) then soft-constraint optimization (naturalness, zone adherence, facing).

### 3.4 Activity-Based Room Design

**Core Idea:** Rooms should be designed around ACTIVITIES, not furniture lists.

Instead of "place: table, 4 chairs, bookshelf, desk" think:
- **Dining activity** requires: table surface, seating around it, serving access, lighting
- **Reading activity** requires: seating, book storage, light source, quiet location
- **Sleeping activity** requires: bed, nightstand, storage, privacy, low light
- **Crafting activity** requires: work surface, tool storage, material storage, good light, waste disposal

**Activity-Based Generation Process:**
1. Define which activities happen in this room type
2. For each activity, define the "activity kit" (required objects + spatial relationships)
3. Place activity kits as atomic groups, not individual objects
4. Allow activity zones to have soft boundaries that can overlap at edges

**Example: Tavern Activities:**
```
ACTIVITY_KITS = {
    "communal_dining": {
        "anchor": "trestle_table",
        "satellites": ["bench_left", "bench_right"],
        "surface_items": ["plates*2-4", "mugs*2-4", "candle_holder"],
        "floor_items": ["spilled_drink?0.3", "dropped_bone?0.2"],
        "min_instances": 2, "max_instances": 5
    },
    "drinking_at_bar": {
        "anchor": "bar_counter",
        "satellites": ["bar_stool*2-4"],
        "surface_items": ["mug*2-3", "bottle*1-2", "coin_pile?0.3"],
        "wall_items": ["shelf_with_bottles", "tap_system"],
        "min_instances": 1, "max_instances": 1
    },
    "warming_by_fire": {
        "anchor": "fireplace",
        "satellites": ["armchair?0.5", "bench", "hearthrug"],
        "nearby_items": ["fire_poker", "wood_pile", "sleeping_dog?0.3"],
        "min_instances": 1, "max_instances": 1
    },
    "private_meeting": {
        "anchor": "small_table",
        "satellites": ["chair*2", "partition_screen"],
        "surface_items": ["candle", "sealed_letter?0.3", "coin_purse?0.2"],
        "min_instances": 0, "max_instances": 2
    }
}
```

### 3.5 Modern Roguelike Approaches (Dead Cells, Hades)

**Dead Cells - Hybrid Handcrafted/Procedural:**
1. Fixed world graph (which biomes connect to which)
2. Handcrafted room "tiles" designed around specific purposes (combat, treasure, merchant, traversal)
3. "Concept graph" per biome defines: level length, special tile count, labyrinth density, entrance-to-exit distance
4. Procedural algorithm selects tiles matching the concept graph constraints
5. Enemy density derived from combat tile count
6. Result: each run feels designed because individual rooms ARE designed; only the sequence and combination changes

**Hades - Fixed Rooms, Variable Encounters:**
Hades takes the opposite approach: rooms are FIXED (same layout every time), but encounters and rewards are procedurally selected. The quality of each room is handcrafted; replayability comes from content variety, not spatial variety.

**Procedural Lesson:** The highest quality approach is Dead Cells' hybrid model:
1. Pre-design 5-10 layout variants per room type
2. Procedurally select which variant to use based on context (adjacent rooms, narrative tags, difficulty)
3. Apply procedural variation within the selected template (furniture swap, clutter, lighting, storytelling vignettes)

---

<a name="4-environmental-storytelling"></a>
## 4. Environmental Storytelling Through Placement

### 4.1 FromSoftware's Environmental Language

FromSoftware games tell stories primarily through spatial arrangement. Key techniques:

**Item Placement as History:**
- Items are placed based on RELEVANCE to the area, not game balance
- A knight's sword near a corpse in knight armor = a fallen warrior's last stand
- An empty estus flask by a bonfire that won't light = someone who gave up
- A child's toy near adult bones = tragedy without words

**Enemy Placement as Narrative:**
- Soldiers locked in combat with mutated creatures = ongoing struggle
- Enemies facing away from the player's approach = they're watching something else
- A single enemy in a large empty room = a boss that killed everything else
- Enemies clustered around a door = guarding something important

**Architectural Storytelling:**
- Collapsed architecture = past violence or natural disaster
- Sealed doors with scratch marks = something tried to get out
- Elaborate decorations in a now-ruined space = fallen grandeur
- Different architectural styles in one building = multiple eras of construction

**The "Elevation = Status" Rule:**
- Higher areas = more important inhabitants (lord's solar above, servants below)
- Descent = approaching danger/corruption (going underground = getting worse)
- This maps directly to dark fantasy: the Veil corruption could intensify with depth

### 4.2 Scene Vignettes (Procedural Micro-Stories)

A **vignette** is a small group of 3-7 objects arranged to suggest a micro-story. These are the most powerful environmental storytelling tool and are highly procedural-friendly.

**Vignette Categories:**

**Category: Interrupted Activity**
| Vignette | Objects | Story Implied |
|----------|---------|---------------|
| Interrupted feast | Table, plates, food, tipped goblet, pushed-back chairs | Sudden departure or attack during meal |
| Abandoned reading | Desk, open book, extinguished candle, chair pushed back | Scholar left in a hurry |
| Unfinished crafting | Workbench, half-shaped metal, cold forge, dropped tongs | Smith fled mid-work |
| Disrupted prayer | Altar, scattered candles, torn prayer book, blood smear | Violence in a holy place |
| Abandoned game | Table, scattered dice/cards, overturned mugs, coins | Players fled or fought |

**Category: Violence/Struggle**
| Vignette | Objects | Story Implied |
|----------|---------|---------------|
| Last stand | Overturned table (cover), arrows in wall, sword on ground | Someone fought from behind furniture |
| Barricade | Furniture piled against door, scratch marks, blood trail | Tried to keep something out |
| Ambush aftermath | Bodies/bones in doorway, weapons scattered, broken glass | Attack at a chokepoint |
| Execution | Chair, rope/chains, blade on floor, dark stain | Someone was restrained and killed |

**Category: Daily Life (Pre-Disaster)**
| Vignette | Objects | Story Implied |
|----------|---------|---------------|
| Cook's station | Cutting board, knife, vegetables, pot on fire, apron on hook | Kitchen was active |
| Scholar's nook | Desk, stack of books, inkwell, quill, notes, candle | Someone studied here |
| Child's corner | Small bed, carved toy, drawing on paper, tiny shoes | A child lived here |
| Merchant's count | Table, scales, coin stacks, ledger book, strongbox | Business was being conducted |

**Category: Decay/Abandonment**
| Vignette | Objects | Story Implied |
|----------|---------|---------------|
| Overgrown shrine | Altar with vines, cracked statue, scattered offerings | Sacred place forgotten |
| Collapsed ceiling | Rubble pile, crushed furniture, dusty debris, exposed sky | Structural failure, long-abandoned |
| Flooded cellar | Standing water, floating barrels, waterline on walls, mold | Slow deterioration |
| Vermin nest | Shredded cloth, gnawed bones, droppings, small tunnel | Animals moved in after humans left |

**Procedural Rule:** Create a vignette library of 40-60 templates. When generating a room, select 1-3 vignettes based on the room's narrative tags (e.g., "abandoned", "recently_occupied", "site_of_violence", "peaceful"). Place vignettes as atomic groups, then scatter additional context clutter around them.

```python
VIGNETTE_TEMPLATE = {
    "interrupted_feast": {
        "anchor": "dining_table",
        "required": ["plate*2-4", "goblet_tipped", "chair_pushed_back"],
        "optional": ["food_remains?0.7", "spilled_wine?0.5", "knife_on_floor?0.3",
                      "broken_plate?0.2", "napkin_crumpled?0.4"],
        "tags": ["interrupted", "recent", "social"],
        "narrative_weight": 0.8,  # Strong story signal
        "placement": "table_surface_and_nearby_floor"
    }
}
```

### 4.3 Procedural Narrative Generation Rules

**Narrative Coherence Constraints:**
1. **One dominant narrative per room:** A room should tell ONE primary story, not five conflicting ones
2. **Gradient of evidence:** The most dramatic vignette should be near the focal point; subtler clues elsewhere
3. **Temporal consistency:** All vignettes in a room should suggest the same time period of the event
4. **Causal chains:** If there's blood on the floor, there should be a source (weapon, body, trail leading somewhere)
5. **Accumulation principle:** One knocked-over chair is an accident. Three knocked-over chairs with a blood trail is a story.

**Tag-Based Vignette Selection:**
```python
ROOM_NARRATIVE_TAGS = {
    "tavern_abandoned": ["interrupted", "social", "decay"],
    "tavern_active": ["daily_life", "social", "warm"],
    "smithy_raided": ["interrupted", "violence", "crafting"],
    "smithy_active": ["daily_life", "crafting", "warm"],
    "chapel_desecrated": ["violence", "sacred", "corruption"],
    "chapel_maintained": ["sacred", "daily_life", "peaceful"],
    "dungeon_cell": ["captivity", "despair", "decay"],
    "nobles_bedroom": ["luxury", "daily_life", "private"]
}
```

---

<a name="5-clutter-and-detail-density"></a>
## 5. Clutter and Detail Density

### 5.1 The Five-Layer System

AAA environment art follows a consistent layering hierarchy. Each layer adds detail but must not overwhelm previous layers:

**Layer 1: STRUCTURE (Shell)**
- Walls, floor, ceiling, pillars, archways, windows, doors
- This is the room's skeleton -- defines shape and scale
- Polygon budget: 60-70% of total room budget
- Generated FIRST, never changes after placement

**Layer 2: FURNITURE (Major Props)**
- Tables, chairs, beds, shelves, workbenches, counters, chests
- These define the room's FUNCTION -- what happens here
- Polygon budget: 15-20% of total room budget
- Placed using CSP solver with zone constraints

**Layer 3: SMALL PROPS (Functional Details)**
- Plates, cups, books, tools, candles, bottles, baskets, pots
- These populate the furniture and define ACTIVITY
- Polygon budget: 5-10% of total room budget
- Placed ON or NEAR furniture (surface spawning + floor scatter)

**Layer 4: CLUTTER (Environmental Detail)**
- Dust, cobwebs, leaves, ash, spilled liquids, scattered papers, bones
- This creates ATMOSPHERE and suggests TIME PASSAGE
- Polygon budget: 2-5% of total room budget (mostly decals and particles)
- Applied as a post-process "weathering pass"

**Layer 5: LIGHTING + EFFECTS**
- Candle flames, fireplace glow, torch flicker, god rays, dust motes, fog
- This creates MOOD and guides ATTENTION
- Applied last, after all geometry is placed
- Must be responsive to layers 2-4 (candle on table = light source there)

### 5.2 Density Guidelines by Room Type

| Room Type | Layer 2 Count | Layer 3 Count | Layer 4 Intensity | Notes |
|-----------|:---:|:---:|:---:|-------|
| Tavern Common | 8-15 | 25-45 | Medium | Dense with tables, mugs, food |
| Smithy | 5-8 | 15-25 | High | Tools everywhere, coal dust, scale |
| Library | 4-8 | 30-60 | Low-Medium | Books dominate L3, minimal floor clutter |
| Chapel | 3-6 | 10-20 | Low (if maintained) / High (if ruined) | Sparse furniture, rich in sacred objects |
| Bedroom | 4-7 | 10-20 | Medium | Personal items, clothing, bedding |
| Kitchen | 5-10 | 20-40 | High | Pots, pans, food, cutting boards, fire |
| Great Hall | 10-20 | 30-50 | Medium | Banners, weapons on walls, table settings |
| Dungeon Cell | 1-3 | 3-8 | High (decay) | Minimal furniture, maximum decay |
| Storage Room | 3-8 | 15-30 | Medium | Barrels, crates, sacks, shelves |
| Guard Room | 3-6 | 10-20 | Medium | Weapons, armor, dice, cards |

### 5.3 Avoiding "Too Clean" / Sterile Rooms

The most common failure in procedural interiors is generating rooms that feel like furniture showrooms. Dark fantasy demands grime, wear, and imperfection.

**The Decay Stack (applied bottom to top):**
1. **Material wear**: Scratches, dents, faded paint, worn edges (texture-level)
2. **Dust accumulation**: Thin layer on horizontal surfaces, thicker in corners and under furniture
3. **Stains and spills**: Rings on tables from cups, dark patches on floor near hearth, grease near kitchen
4. **Biological growth**: Moss on stone near water, cobwebs in upper corners, mold in damp areas
5. **Structural damage**: Cracks in walls, loose stones, warped wood, missing plaster revealing brick
6. **Debris**: Fallen ceiling plaster, scattered leaves (near windows), broken pottery

**Decay Level Presets:**
```python
DECAY_LEVELS = {
    "pristine": {"dust": 0.1, "stains": 0.05, "damage": 0.0, "growth": 0.0, "debris": 0.0},
    "well_maintained": {"dust": 0.2, "stains": 0.15, "damage": 0.05, "growth": 0.02, "debris": 0.05},
    "lived_in": {"dust": 0.3, "stains": 0.3, "damage": 0.1, "growth": 0.05, "debris": 0.1},
    "neglected": {"dust": 0.5, "stains": 0.4, "damage": 0.25, "growth": 0.15, "debris": 0.2},
    "abandoned": {"dust": 0.8, "stains": 0.5, "damage": 0.4, "growth": 0.4, "debris": 0.5},
    "ruined": {"dust": 0.9, "stains": 0.6, "damage": 0.7, "growth": 0.6, "debris": 0.8}
}
```

**Procedural Rule:** Every generated room must have a decay level assigned. Even "pristine" rooms get a 10% dust factor. Dark fantasy default should be "lived_in" to "neglected" for most spaces, "abandoned" to "ruined" for dungeons and ruins.

### 5.4 Weathering as Visual Storytelling

Weathering patterns communicate history without dialogue:

| Weathering Pattern | Story It Tells |
|---|---|
| Worn floor path from door to fireplace | High traffic, well-used room |
| Clean rectangle on dusty shelf | Something was recently removed |
| Soot blackening above torch sconces | Long-term use of this light source |
| Water stain line on wall (uniform height) | Past flooding |
| Moss growth on one wall only | That wall faces north/gets less sun |
| Scratches at lock height on door | Frequent/desperate attempts to open |
| Grease layer near cooking area, none elsewhere | Functional zoning visible in decay |
| Boot prints in dust leading to one corner | Someone explored recently |

**Procedural Rule:** Weathering should be zone-aware. High-traffic zones (doorways, paths between furniture groups) get MORE floor wear and LESS dust. Corners and under-furniture get MORE dust and cobwebs. Areas near fire sources get soot. Areas near water get mold.

---

<a name="6-functional-zones"></a>
## 6. Functional Zones Within Rooms

### 6.1 Zone-Based Placement vs. Random Scatter

**Random scatter** places objects anywhere within the room bounds using collision avoidance. This produces "furniture warehouse" layouts -- technically valid but emotionally dead.

**Zone-based placement** divides the room into functional areas, then places objects within their appropriate zone. This produces rooms that feel purposeful and logical.

**Why zones matter:** Real rooms are organized by ACTIVITY. People cook in one area, eat in another, sleep in another. Furniture clusters around activities, not randomly throughout the space. Zone-based placement automatically produces this clustering.

### 6.2 Tavern Zones

```
+---------------------------------------------------+
|                                                     |
|  [PRIVATE NOOK]    [DINING ZONE]     [HEARTH ZONE] |
|  Small table        Trestle tables    Fireplace     |
|  2 chairs           Benches           Best seats    |
|  Screen/partition    Mugs/plates       Fire tools    |
|                                        Dog/cat      |
|                                                     |
|  [ENTRY ZONE]      [COMMON FLOOR]    [BAR ZONE]    |
|  Door mat           Open space for    Bar counter   |
|  Coat hooks         movement/brawls   Barrel seats  |
|  Bouncer stool      Spilled drinks    Tap/shelf     |
|  Notice board       Floor rushes       Mugs          |
|                                                     |
+---------------------------------------------------+
```

**Zone Rules:**
- ENTRY is always at a door, 1-2m deep
- BAR is on a wall perpendicular to the entrance (customers walk past it)
- HEARTH is on the wall opposite or farthest from the entrance (draws people in)
- DINING fills the center, multiple table groups with paths between
- PRIVATE NOOK is in a corner, partially screened from the main room
- COMMON FLOOR is open space (minimum 2m x 2m) for movement, brawling, dancing

### 6.3 Smithy Zones

```
+-------------------------------------------+
|                                             |
|  [FORGE ZONE]       [WORK ZONE]            |
|  Forge (against      Anvil (1m from forge) |
|  wall w/ chimney)    Slack tub (near anvil) |
|  Bellows             Workbench              |
|  Coal pile           Tool rack (on wall)    |
|                                             |
|  [STORAGE ZONE]     [DISPLAY ZONE]         |
|  Iron stock rack     Weapon rack            |
|  Coal bin            Armor stand            |
|  Scrap pile          Display shelf          |
|  Lumber stack        Counter                |
|                      (faces street/door)    |
|                                             |
+-------------------------------------------+
```

**Zone Rules:**
- FORGE must be against an exterior wall (chimney) or in center with hood
- WORK zone (anvil triangle) is within 1m of forge -- this is NON-NEGOTIABLE
- DISPLAY faces the customer entrance (street-facing wall)
- STORAGE is in the back, away from customers
- Minimum 1.5m clear path from entrance to display zone

### 6.4 Library Zones

```
+-------------------------------------------+
|                                             |
|  [ARCHIVE ZONE]     [READING ZONE]         |
|  Tall bookshelves    Reading desk + chair   |
|  (against walls)     Candelabra             |
|  Rolling ladder      Side table             |
|  Shelf labels        Reading stand          |
|                                             |
|  [DESK ZONE]        [STUDY NOOK]           |
|  Writing desk        Armchair               |
|  Inkwell, quills     Small bookshelf        |
|  Paper/parchment     Globe/orrery           |
|  Seal/wax            Window (natural light) |
|                                             |
+-------------------------------------------+
```

**Zone Rules:**
- ARCHIVE shelves line the walls (maximize book storage)
- READING zone needs the best light (near windows or large candelabra)
- DESK zone needs privacy and quiet (corner or alcove)
- STUDY NOOK is optional, intimate, with its own light source
- Center of room should have a lectern or display case as focal point

### 6.5 How Zone-Based Placement Differs from Random Scatter

| Aspect | Random Scatter | Zone-Based |
|--------|---------------|------------|
| Object placement | Anywhere that fits | Within assigned zone |
| Clustering | Accidental | Deliberate by activity |
| Pathfinding | May block routes | Zones include circulation |
| Narrative | None | Zone purpose implies story |
| Density | Uniform | Varies by zone |
| Focal point | Random | Zone hierarchy defines it |
| Result | Furniture warehouse | Believable room |

**Procedural Rule:** 
1. Define zones for the room type with percentage allocations
2. Partition the room rectangle into zone regions (using weighted Voronoi or simple rectangular subdivision)
3. Place zone anchors first (fireplace in hearth zone, forge in forge zone)
4. Fill each zone using CSP with zone-boundary constraints
5. Add cross-zone elements (paths, shared furniture at zone boundaries)

---

<a name="7-lighting-as-interior-design"></a>
## 7. Lighting as Interior Design

### 7.1 Light Pools Define Activity Areas

The fundamental principle from all AAA dark fantasy games: **light is not decoration, it is spatial design**. Each pool of light defines an activity area:

- A candle on a desk = "someone reads/writes here"
- A fireplace glow = "this is the gathering/warmth zone"
- A torch by a door = "this is the entrance/exit"
- A chandelier over a table = "this is where meals happen"
- A brazier in a corridor = "you are on the right path"

**The inverse is equally important:** darkness between light pools creates atmosphere, mystery, and the feeling that spaces extend beyond what you can see.

### 7.2 The Soulsborne Lighting Pattern

FromSoftware games use a consistent lighting philosophy across Dark Souls, Bloodborne, and Elden Ring:

**Warm Safe Islands in Cold Darkness:**
- Bonfires/Grace Sites emit warm orange-amber light, creating a 3-5m radius "island of safety"
- The surrounding world is cold, dark, threatening
- The contrast between bonfire warmth and world darkness is the emotional core
- Players instinctively move toward light because it signals rest, progress, and safety

**No Global Ambient in Dungeons:**
- Dungeon interiors have ZERO ambient light
- Every photon comes from a placed light source
- This means darkness is the default; light is the exception
- Result: every lit area feels intentional, important, precious

**Light Color as Information:**
| Color | Meaning |
|-------|---------|
| Warm amber/orange | Safety, fire, human habitation |
| Cool blue/white | Moonlight, magic, the unknown |
| Sickly green | Poison, plague, corruption |
| Deep purple/red | Demonic, blood magic, forbidden |
| Golden | Divine, sacred, important loot |

### 7.3 Practical Light Sources for Dark Fantasy Interiors

Every light in a medieval-fantasy interior should have a VISIBLE SOURCE. No invisible fill lights. Every photon should be traceable to an object.

**Light Source Catalog:**

| Source | Color Temp | Radius | Intensity | Flicker | Placement Rules |
|--------|-----------|--------|-----------|---------|-----------------|
| Tallow candle | 1800K (deep amber) | 1.5-2.5m | Low | Yes, slow | On tables, desks, shelves, altar |
| Beeswax candle | 2200K (warm amber) | 2-3m | Medium | Yes, slow | Wealthy rooms, chapel, solar |
| Candelabra (3-7) | 2200K | 3-5m | Medium-High | Yes, slow | Dining tables, chandeliers |
| Rushlight | 1600K (orange) | 1-1.5m | Very Low | Yes, fast | Poor rooms, servants' quarters |
| Oil lamp | 2400K (amber) | 2-4m | Medium | Slight | Desks, reading areas, workshops |
| Wall torch | 2000K (amber-orange) | 3-5m | Medium-High | Yes, medium | Corridors, doorways, stairwells |
| Fireplace (small) | 1900K (red-amber) | 4-6m | High | Yes, slow | Bedrooms, private rooms |
| Fireplace (large) | 1900K (red-amber) | 6-10m | Very High | Yes, slow | Great hall hearth, tavern |
| Forge fire | 2500K (yellow-white) | 3-5m | Very High | Yes, fast | Smithy (primary light source) |
| Window (day) | 5500K (blue-white) | Directional | Varies | No | Shafts of light on floor |
| Window (night) | 4000K (cool blue) | Faint | Very Low | No | Moonlight wash |

### 7.4 Lighting Placement Rules

**Rule 1: Every activity zone gets its own light source.**
If there's a reading desk, there's a candle on it. If there's a dining table, there's a candelabra above or candles on it. If there's a doorway, there's a torch beside it.

**Rule 2: Light pools should overlap at zone boundaries.**
The fireplace glow should barely reach the nearest dining table. The torch at the door should illuminate the entry zone. This creates a connected but varied light landscape.

**Rule 3: At least 30% of the room should be in shadow.**
Dark fantasy demands darkness. A room lit to 100% feels like an office, not a medieval interior. The unlit corners, the darkness behind pillars, the shadows under tables -- these are essential.

**Rule 4: The focal point gets the brightest light.**
The fireplace is the brightest thing in a tavern. The forge is the brightest thing in a smithy. The altar candles are the brightest thing in a chapel. This reinforces the spatial hierarchy.

**Rule 5: Warm core, cool edges.**
The center of activity (fire, candles) radiates warm light. The room's edges, especially walls and ceiling, fall into cooler shadow. This creates the "warm cave" feeling essential to dark fantasy.

### 7.5 Procedural Lighting Generation

```python
def generate_room_lighting(room, zones, furniture):
    lights = []
    
    # Step 1: Focal point light (brightest)
    focal = get_focal_point(room)
    lights.append(create_light(
        position=focal.position + Vec3(0, 0, focal.height),
        color=WARM_AMBER, intensity=focal.light_intensity,
        radius=focal.light_radius, flicker=True
    ))
    
    # Step 2: Activity zone lights
    for zone in zones:
        if zone.has_light_source:
            for source in zone.light_sources:
                lights.append(create_light(
                    position=source.position,
                    color=source.color_temp,
                    intensity=source.intensity,
                    radius=source.radius,
                    flicker=source.flicker
                ))
    
    # Step 3: Furniture-mounted lights
    for item in furniture:
        if item.type in LIGHT_BEARING_FURNITURE:
            lights.append(create_light(
                position=item.position + item.light_offset,
                color=get_candle_color(),
                intensity=CANDLE_INTENSITY,
                radius=2.0, flicker=True
            ))
    
    # Step 4: Doorway/entrance torches
    for door in room.doors:
        lights.append(create_light(
            position=door.position + Vec3(0.3, 0, 2.0),  # beside and above
            color=TORCH_COLOR, intensity=TORCH_INTENSITY,
            radius=4.0, flicker=True
        ))
    
    # Step 5: Validate shadow coverage >= 30%
    shadow_pct = calculate_shadow_percentage(room, lights)
    if shadow_pct < 0.30:
        reduce_light_radii(lights, target_shadow=0.35)
    
    return lights
```

---

<a name="8-procedural-generation-rules"></a>
## 8. Consolidated Procedural Generation Rules

### 8.1 The Complete Interior Generation Pipeline

```
PHASE 1: CONTEXT
  Input: room_type, building_type, narrative_tags, decay_level, seed
  Output: zone_definitions, activity_list, vignette_selections, decay_params

PHASE 2: ZONE LAYOUT
  Input: room_dimensions, zone_definitions
  Process: Subdivide room into zones using weighted rectangular partitioning
  Output: zone_regions (polygons with assigned types)
  Constraint: All zones must be accessible (pathfinding check)

PHASE 3: FOCAL POINT
  Input: room, zone_regions, entrance_positions
  Process: Place focal point object in its assigned zone, visible from primary entrance
  Output: focal_point_position, focal_point_object
  Constraint: Must be visible within 2s of entering (sightline check)

PHASE 4: FURNITURE (CSP SOLVER)
  Input: zone_regions, activity_kits, room_type_config
  Process: 
    a. Place zone anchors (fireplace, forge, bar counter, etc.)
    b. Place activity kit groups as atomic units
    c. CSP solver for remaining required furniture (MRV + backtracking)
    d. Greedy placement of optional furniture
  Output: furniture_positions[]
  Constraints: No overlap, door clearance (1.0m), path connectivity, zone adherence

PHASE 5: SMALL PROPS (Surface + Nearby Spawning)
  Input: furniture_positions, activity_kits
  Process:
    a. Spawn surface items on furniture (plates on tables, books on shelves)
    b. Spawn floor items near relevant furniture (logs near fireplace, tools near anvil)
    c. Apply probability masks from activity_kit definitions
  Output: prop_positions[]

PHASE 6: VIGNETTES (Environmental Storytelling)
  Input: narrative_tags, room_type, decay_level
  Process:
    a. Select 1-3 vignettes matching narrative tags
    b. Place vignette groups as atomic units in appropriate zones
    c. Ensure narrative coherence (one dominant story per room)
  Output: vignette_positions[]

PHASE 7: LIVED-IN PASS (Imperfection)
  Input: all furniture and prop positions
  Process:
    a. Rotate each piece 1-5 degrees randomly
    b. Offset each piece 0.02-0.08m from ideal position
    c. Push chairs away from tables 0.1-0.3m
    d. Add asymmetric offsets to symmetric arrangements
  Output: adjusted_positions[]

PHASE 8: DECAY/WEATHERING PASS
  Input: adjusted_positions, decay_level, zone_regions
  Process:
    a. Apply dust based on zone traffic (low traffic = more dust)
    b. Apply wear on high-traffic paths (doorway to focal point)
    c. Add cobwebs to upper corners and unused furniture
    d. Add stains near fire sources (soot), water sources (mold), food areas (grease)
    e. Apply structural damage based on decay_level
    f. Scatter debris based on decay_level
  Output: decay_objects[], decay_decals[]

PHASE 9: LIGHTING
  Input: room, zones, furniture (with light-bearing items identified)
  Process:
    a. Focal point gets brightest light
    b. Each activity zone gets appropriate light source
    c. Light-bearing furniture gets candle/lamp
    d. Doorways get torches
    e. Validate >= 30% shadow coverage
    f. Apply warm-core, cool-edges gradient
  Output: light_positions[], light_params[]

PHASE 10: VALIDATION
  - Path connectivity: Can the player reach every zone from every entrance?
  - Collision: No overlapping objects?
  - Density: Does prop count match guidelines for room type?
  - Narrative: Are vignettes coherent (single story, consistent timeline)?
  - Lighting: Does shadow coverage meet dark fantasy threshold?
  - Performance: Total triangle count within budget?
```

### 8.2 Key Constants and Thresholds

```python
# Door clearance -- minimum clear space in front of any door
DOOR_CLEARANCE_M = 1.0

# Minimum path width between furniture groups
MIN_PATH_WIDTH_M = 0.8

# Furniture rotation jitter (lived-in pass)
ROTATION_JITTER_DEG = (1.0, 5.0)

# Furniture position jitter (lived-in pass)
POSITION_JITTER_M = (0.02, 0.08)

# Chair pull-back distance from tables
CHAIR_PULLBACK_M = (0.1, 0.3)

# Minimum shadow coverage for dark fantasy
MIN_SHADOW_COVERAGE = 0.30

# Maximum shadow coverage (room shouldn't be unplayable)
MAX_SHADOW_COVERAGE = 0.70

# Smithy anvil-to-forge maximum distance
ANVIL_FORGE_MAX_DIST_M = 1.0

# Smithy slack-tub-to-anvil maximum distance
SLACKTUB_ANVIL_MAX_DIST_M = 0.8

# Tavern minimum open floor space for movement
TAVERN_MIN_OPEN_FLOOR_M2 = 4.0  # 2m x 2m

# Screens passage minimum width (castle)
SCREENS_PASSAGE_WIDTH_M = 2.0

# Focal point visibility check angle from entrance
FOCAL_VISIBILITY_ANGLE_DEG = 60.0

# Props per square meter targets by room type
PROP_DENSITY_PER_M2 = {
    "tavern": 2.5,
    "smithy": 2.0,
    "library": 3.0,
    "chapel": 1.5,
    "bedroom": 1.8,
    "kitchen": 2.8,
    "great_hall": 1.5,
    "dungeon_cell": 1.0,
    "storage": 2.2,
    "guard_room": 1.8
}
```

### 8.3 Quality Checklist (Run After Every Generation)

- [ ] Focal point is visible from primary entrance
- [ ] No furniture blocks doorways (1.0m clearance)
- [ ] All zones are reachable via paths (0.8m wide minimum)
- [ ] Activity kits are placed as groups (not scattered)
- [ ] Furniture has rotation/position jitter (not grid-aligned)
- [ ] At least 1 vignette is present (unless room is "empty" narrative)
- [ ] Decay level matches room narrative tags
- [ ] Every light has a visible source object
- [ ] Shadow coverage is 30-70%
- [ ] Warm light at core, cool light at edges
- [ ] No identical rooms in same building (seed variation)
- [ ] Prop density matches room type guidelines
- [ ] Chairs are pushed back from tables
- [ ] Medieval historical accuracy maintained (no post-medieval furniture)

---

## Sources

### Level Design and Composition
- [Composition - The Level Design Book](https://book.leveldesignbook.com/process/blockout/massing/composition)
- [Environment Art - The Level Design Book](https://book.leveldesignbook.com/process/env-art)
- [Composition in Level Design - Game Developer](https://www.gamedeveloper.com/design/composition-in-level-design)
- [Architectural Functionality in Game Levels - Geoff Ellenor](https://gellenor.medium.com/architectural-functionality-in-video-games-43301c8a8075)
- [Level Design Views and Vistas - Envato Tuts+](https://code.tutsplus.com/level-design-views-and-vistas--cms-25036a)

### Medieval Historical References
- [Rooms in a Medieval Castle - Historic European Castles](https://historiceuropeancastles.com/rooms-in-a-medieval-castle/)
- [Castle Life - Rooms in a Medieval Castle](https://www.castlesandmanorhouses.com/life_01_rooms.htm)
- [Medieval Castle Layout - Historic European Castles](https://historiceuropeancastles.com/medieval-castle-layout/)
- [Great Hall - Wikipedia](https://en.wikipedia.org/wiki/Great_hall)
- [Buttery (room) - Wikipedia](https://en.wikipedia.org/wiki/Buttery_(room))
- [Medieval Tavern - One Stop For Writers](https://onestopforwriters.com/scene_settings/medieval-tavern-speculative)
- [Medieval Blacksmith - Medieval Chronicles](https://www.medievalchronicles.com/medieval-people/medieval-tradesmen-and-merchants/medieval-blacksmith/)

### Procedural Generation
- [Room Generation using Constraint Satisfaction - pvigier](https://pvigier.github.io/2022/11/05/room-generation-using-constraint-satisfaction.html)
- [Dead Cells Level Design - Deepnight Games](https://deepnight.net/tutorial/the-level-design-of-dead-cells-a-hybrid-approach/)
- [Skyrim's Modular Level Design - Joel Burgess GDC 2013](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html)
- [Skyrim's Modular Approach - Game Developer](https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design)
- [Rule-Based Layout Solving - ResearchGate](https://www.researchgate.net/publication/228922424_Rule-based_layout_solving_and_its_application_to_procedural_interior_generation)
- [Hierarchical Procedural Decoration - DiVA Portal](https://www.diva-portal.org/smash/get/diva2:1479952/FULLTEXT01.pdf)

### Environmental Storytelling
- [Environmental Storytelling - Game Developer (Don Carson)](https://www.gamedeveloper.com/design/environmental-storytelling)
- [Environmental Storytelling in Video Games - Game Design Skills](https://gamedesignskills.com/game-design/environmental-storytelling/)
- [World Design Lessons from FromSoftware - James Roha](https://medium.com/@Jamesroha/world-design-lessons-from-fromsoftware-78cadc8982df)
- [How Elden Ring Masters Environmental Storytelling - CBR](https://www.cbr.com/elden-ring-environmental-storytelling-fromsoftware/)
- [Environmental Storytelling - Lokey Lore](https://lokeysouls.com/2020/11/16/environmental-storytelling/)

### AAA Environment Art
- [3D Prop Design Guide - AAA Game Art Studio](https://aaagameartstudio.com/blog/3d-prop-design)
- [Approach to Environment Design in AAA Games - 80 Level](https://80.lv/articles/approach-to-environment-design-in-aaa-games)
- [Lighting Environments Tips and Tricks - 80 Level](https://80.lv/articles/lighting-environments-tips-and-tricks)
- [God of War Ragnarok AAA Environment Workflows - The Rookies](https://discover.therookies.co/2025/09/05/study-god-of-war-ragnarok-to-learn-aaa-environment-workflows/)
