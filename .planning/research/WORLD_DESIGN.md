# VeilBreakers World Design Research

**Researched:** 2026-03-19
**Purpose:** Define requirements for generating complete, walkable, detailed dark fantasy RPG worlds via MCP toolkit
**Confidence:** HIGH (cross-referenced AAA titles, level design literature, Unity docs, and real-world architecture)

---

## Table of Contents

1. [RPG Map Structure & Scale](#1-rpg-map-structure--scale)
2. [Location Types for VeilBreakers](#2-location-types-for-veilbreakers)
3. [Interior Furnishing Standards](#3-interior-furnishing-standards)
4. [Environment Cohesion](#4-environment-cohesion)
5. [Performance for Dense Interiors](#5-performance-for-dense-interiors)
6. [MCP Toolkit Gap Analysis](#6-mcp-toolkit-gap-analysis)
7. [Recommended Constants & Configs](#7-recommended-constants--configs)

---

## 1. RPG Map Structure & Scale

### 1.1 Overworld Size Reference (AAA Titles)

| Game | Map Size (km^2) | Playtime (hours) | Density Rating |
|------|-----------------|-------------------|----------------|
| Skyrim | ~37 | 100-300+ | High |
| Elden Ring | ~79 | 80-150+ | Very High |
| The Witcher 3 | ~127 | 50-200+ | High |
| Dark Souls 3 | ~5-8 (non-contiguous) | 30-60 | Extremely High |
| Red Dead Redemption 2 | ~75 | 50-100+ | High |
| GTA V | ~75 | 30-60+ (story) | Medium-High |

### 1.2 Recommended VeilBreakers World Size

For a dark fantasy RPG targeting 40-60 hours of gameplay with dense, curated content:

- **Target overworld:** 4-8 km^2 (2x2 km to ~2.8x2.8 km)
- **Rationale:** Dark Souls 3 achieves 30-60 hours in ~5-8 km^2 with extremely high density. VeilBreakers should favor density over sprawl. This is a curated world, not an open-world sandbox.
- **Unity Terrain tiles:** 4x (1024x1024m tiles) or 1x (2048x2048m tile) depending on detail needs
- **Heightmap resolution:** 2049x2049 (power-of-two+1) for the full overworld at ~1m per texel, or 1025x1025 per tile at ~1m per texel

### 1.3 Player Movement Speed

| Movement Type | Speed (Unity units/sec) | Speed (m/s) | Speed (km/h) |
|---------------|------------------------|-------------|---------------|
| Walk | 1.4 | 1.4 | 5.0 |
| Jog (default) | 3.5 | 3.5 | 12.6 |
| Sprint | 6.0 | 6.0 | 21.6 |
| Combat movement | 2.5 | 2.5 | 9.0 |

**Key metric:** 1 Unity unit = 1 meter. Standard RPG character jog speed is 3.5-4.0 m/s. Sprint is typically 1.5-2x jog speed.

### 1.4 Walking Distances Between Locations

| Route Type | Distance (m) | Jog Time | Design Purpose |
|------------|-------------|----------|----------------|
| Town to nearest POI | 100-300 | 30-90 sec | Quick exploration loop |
| Town to town | 500-1500 | 2-7 min | Journey with encounters |
| Town to major dungeon | 300-800 | 1.5-4 min | Adventure pacing |
| Hub to boss area | 800-2000 | 4-10 min | Tension building |
| Hidden area off path | 50-200 | 15-60 sec | Reward exploration |
| Between encounter clusters | 150-400 | 45 sec-2 min | Breathing room |

**Design principle:** The "30-second rule" -- a player should encounter something interesting (combat, loot, landmark, NPC, environmental storytelling) every 30 seconds of travel. For a 3.5 m/s jog, that means one point of interest every ~105 meters.

**Anti-monotony:** Fill travel routes with:
- Terrain variation (hills, rivers, bridges, cliffs)
- Ambient encounters (wildlife, patrols, weather events)
- Environmental storytelling (corpses, abandoned camps, blood trails)
- Resource nodes (herbs, ore, chests)
- Vista points and hidden paths

### 1.5 Location Count for 40-60 Hour RPG

Reference data from Skyrim (343 discoverable map markers, ~670 total named locations, 197 clearable dungeons):

| Category | Skyrim Count | VeilBreakers Target | Notes |
|----------|-------------|---------------------|-------|
| Major cities | 5 | 2-3 | Walled, fully explorable with interiors |
| Towns/settlements | 20+ | 8-12 | Mix of intact and overrun |
| Dungeons (clearable) | 197 | 30-50 | Caves, tombs, ruins, forts |
| Camps (hostile) | 10+ | 15-20 | Bandit, cultist, undead |
| Caves | 150+ | 20-30 | Natural formations |
| Forts/keeps | 16 | 8-12 | Occupied or ruined |
| Dragon lairs / boss lairs | 9 | 8-12 | Major boss encounters |
| Mines | 3+ | 4-6 | Resource + dungeon hybrid |
| Landmarks/shrines | 50+ | 20-30 | Lore, fast travel, rewards |
| Hidden areas | Unmarked | 15-25 | Easter eggs, secret rooms |
| **Total distinct locations** | **~670** | **~150-200** | **Dense, high-quality over quantity** |

### 1.6 Level Structure

```
OVERWORLD (open, interconnected)
  |
  +-- Hub City (safe zone, shops, quests, fast travel)
  |     +-- Interior: Tavern, Blacksmith, Temple, Castle, Market, Homes
  |     +-- Underground: Sewers, Catacombs (connect to other areas)
  |
  +-- Region 1: Darkwood Forest
  |     +-- Forest paths (branching, looping)
  |     +-- Bandit Camp A, B
  |     +-- Hidden Cave (optional treasure)
  |     +-- Forest Clearing (mini-boss)
  |     +-- Ancient Ruins entrance -> Dungeon 1
  |           +-- Entry Hall
  |           +-- Branching corridors (L1)
  |           +-- Puzzle room
  |           +-- Descending stairs
  |           +-- Deeper level (L2) with harder enemies
  |           +-- Treasure vault (optional)
  |           +-- Boss chamber
  |           +-- Shortcut back to entrance
  |
  +-- Region 2: Blighted Marshlands
  |     +-- Overrun Town (story-critical)
  |     +-- Witch's hut (NPC/quest)
  |     +-- Sunken Temple entrance -> Dungeon 2
  |     ...
  |
  +-- Region 3: Ashen Mountains
  |     +-- Fortress (multi-level, siege-themed)
  |     +-- Mining town (hostile takeover)
  |     +-- Volcanic caves
  |     +-- Final boss castle approach
  |     ...
  |
  +-- Endgame: The Veil Breach
        +-- Final dungeon complex
        +-- Multiple boss encounters
        +-- Point of no return
```

**Key structural rules:**
- Every region has 1 hub (safe or contested), 3-5 dungeons, 2-3 camps, 5-10 minor POIs
- Dungeons use 5-Room Dungeon structure: Entrance, Puzzle/RP, Trick/Setback, Boss, Reward
- Vertical progression: surface -> underground -> deeper underground
- Shortcuts and loops: every dungeon must loop back, no dead-end backtracking
- Interconnection: sewer/cave networks connect seemingly separate areas

---

## 2. Location Types for VeilBreakers

### 2.1 Cities/Towns

#### Intact City
| Component | Dimensions (m) | Required Elements |
|-----------|----------------|-------------------|
| City walls | 200-400m perimeter, 6-8m high, 1.5-2m thick | Walkable ramparts, 2+ gates, towers every 40-60m |
| Main street | 6-8m wide, 100-200m long | Cobblestone, market stalls, NPCs |
| Market square | 20x20 to 30x30 | Fountain/well, vendor stalls, crates, barrels |
| Residential district | 4-8 houses per block | 2-3 story buildings, alleys, clotheslines |
| Castle/keep | 30-60m footprint | Courtyard, great hall, tower, walls |
| Temple | 15x25m footprint | Nave, altar, bell tower, graveyard adjacent |
| Tavern | 12x8m footprint, 2 floors | Common room, kitchen, upstairs rooms |
| Blacksmith | 8x10m footprint | Workshop area, exterior forge area |
| Total city footprint | 150x150 to 300x300m | -- |

#### Overrun/Ruined Town
Same layout as intact but with:
- **Damage level 0.4-0.7** applied via ruins system
- Collapsed roofs, broken walls, rubble piles
- Vegetation overgrowth (ivy, moss, ferns at damage > 0.6)
- Hostile NPC camps in former buildings
- Barricades, overturned carts, burned areas
- Bodies, bloodstains, broken furniture
- Fire damage: blackened stone, charred timber, ash piles

#### Lighting & Atmosphere
| Setting | Light Color (Kelvin) | Fog Density | Mood |
|---------|---------------------|-------------|------|
| Intact town (day) | 5500K warm white | Low | Safe, inviting |
| Intact town (night) | 2700K amber (torchlight) | Medium | Cozy, mysterious |
| Overrun town | 4000K grey-blue | Heavy | Dread, danger |
| Burning town | 2000K deep orange | Heavy (smoke) | Chaos, urgency |

### 2.2 Dungeons

#### Standard Dungeon Structure
```
ENTRY (1 room)
  |-- Connects to overworld, visible entrance markers
  |-- Tutorial fight or environmental storytelling
  |
EXPLORATION ZONE (3-8 rooms, branching)
  |-- Main corridor: 3m wide, 3-4m tall
  |-- Side rooms: 5x5m to 10x10m
  |-- Vertical transitions: stairs, ladders, drops (3-5m descent per level)
  |-- Traps: pressure plates, dart walls, falling rocks, poison gas
  |-- Puzzle elements: levers, key doors, movable blocks, light beams
  |
DEEP ZONE (2-4 rooms, more linear)
  |-- Harder enemies, better loot
  |-- Environmental storytelling intensifies
  |-- Rooms get larger: 10x10m to 15x15m
  |
BOSS CHAMBER (1 room)
  |-- 20x20m to 30x30m (see Boss Arena section)
  |-- Entry is a one-way transition (fog gate, collapsing passage)
  |-- Multiple environmental features
  |
REWARD / EXIT
  |-- Treasure room: 5x5m with chest, lore item
  |-- Shortcut: elevator, opened gate back to entrance
```

#### Dungeon Size Guide
| Dungeon Type | Grid Size (cells) | Physical Size (m) | Room Count | Floors |
|-------------|-------------------|-------------------|------------|--------|
| Small cave | 32x32 | 64x64 | 4-6 | 1 |
| Medium dungeon | 48x48 | 96x96 | 8-12 | 1-2 |
| Large dungeon | 64x64 | 128x128 | 12-20 | 2-3 |
| Major story dungeon | 96x96 | 192x192 | 20-30 | 3-4 |
| Final dungeon | 128x128 | 256x256 | 30+ | 4-5 |

### 2.3 Castles

Based on real medieval castle dimensions:

| Component | Dimensions (m) | Details |
|-----------|----------------|---------|
| Outer walls | 60-100m per side, 8-10m high, 1.5-2m thick | Crenellations, arrow slits, walkable ramparts |
| Corner towers | 3-4m radius, 12-14m tall | Cylindrical, 2-3 floors, spiral staircase |
| Gatehouse | 5m wide opening, 10-12m tall | Portcullis, murder holes, flanking towers |
| Courtyard | 25x25 to 40x40m | Packed dirt/cobblestone, well, training dummies |
| Keep | 15-20m per side, 3-4 floors | Great hall (L1), private chambers (L2-3), roof access |
| Great hall | 20x10m to 30x15m, 6-8m ceiling | Proportion rule: 3:1 length:width, ceiling 2x width |
| Throne room | 15x10m, 5-6m ceiling | Part of or connected to great hall |
| Chapel | 8x15m | Nave + altar |
| Kitchen | 8x8m | Adjacent to great hall |
| Dungeon/prison | 10x10m below courtyard | 4-8 cells (2x3m each), guard room, torture chamber |
| Bedchambers | 5x5m to 8x8m each, 3-4 rooms | Lord's chamber is largest |
| Armory | 6x8m | Ground floor of tower or keep |
| Stables | 8x12m | Against outer wall |
| Total footprint | 60x60 to 100x100m | -- |

### 2.4 Bandit Camps

| Component | Dimensions (m) | Details |
|-----------|----------------|---------|
| Camp footprint | 20x20 to 40x40m | Hidden in terrain (forest clearing, ravine, cave mouth) |
| Tents/lean-tos | 2x3m each, 3-6 total | Canvas over poles, bedrolls inside |
| Central campfire | 2m diameter fire pit | Cooking spit, logs for seating, scattered bones |
| Lookout post | 3x3m platform, 4m high | Ladder access, on elevated terrain or tree |
| Stolen goods pile | 3x3m | Crates, sacks, stolen weapon rack |
| Cage/prisoner area | 2x2m | Optional: captured NPC |
| Perimeter | Sharpened stakes, tripwires | Early warning system |

**Atmosphere:** Dim torchlight, sounds of conversation/argument, animal hides drying, empty bottles.

### 2.5 Forest Areas

| Component | Dimensions (m) | Details |
|-----------|----------------|---------|
| Main paths | 2-3m wide | Dirt, occasional cobblestone near towns |
| Forest density | Trees every 3-8m | Poisson disk scatter, min_distance=3.0 |
| Clearings | 15x15 to 30x30m | Events, encounters, rest spots |
| Hidden caves | 5m wide entrance | Behind waterfalls, under roots, cliff faces |
| Ancient ruins | 10x10m footprint | Broken columns, overgrown altar, lore stones |
| Creature dens | 8x8m | Bone piles, scratched trees, animal tracks |
| Stream/river | 3-5m wide | Crossable at fords, bridges |

**Vegetation layers:**
1. Ground cover: grass, ferns, mushrooms, fallen leaves (scatter density HIGH)
2. Understory: bushes, saplings, dead logs (scatter density MEDIUM)
3. Canopy: large trees, 8-15m tall (scatter density LOW, Poisson disk min_distance=5-8m)
4. Details: hanging moss, spider webs, fireflies (particle effects)

### 2.6 Boss Arenas

| Arena Type | Dimensions (m) | Environmental Features |
|------------|----------------|----------------------|
| Standard arena | 20x20 to 25x25 | Pillars for cover (4-6), clear center space |
| Large arena | 30x30 to 40x40 | Multiple elevation levels, hazard zones |
| Spectacle arena | 40x40+ | Destructible elements, phase transitions |
| Tight arena | 15x15 | Nowhere to hide, claustrophobic pressure |
| Multi-level arena | 25x25, 2 floors | Balconies, drops, vertical combat |

**Required elements per boss arena:**
- **Entry point:** Fog gate, collapsing passage, or one-way drop
- **Cover objects:** 4-8 pillars, walls, or debris clusters (destructible preferred)
- **Hazard zones:** 2-3 areas of lava/poison/spikes/void (phase-triggered)
- **Phase triggers:** At 75%, 50%, 25% boss HP, arena changes:
  - Floor sections collapse
  - New hazard zones activate
  - Destructible cover gets destroyed
  - Additional enemies spawn at edges
- **Clear center:** 60-70% of arena floor must be traversable combat space
- **Spectacle elements:** Dramatic backdrop (cliff edge, vaulted ceiling, windows showing storm)
- **Audio cue zones:** Music intensifies with phase changes

### 2.7 Underground Areas

| Type | Grid Size | Wall Height | Features |
|------|----------|-------------|----------|
| Natural cave | 48x48 cells | 4-6m (irregular) | Stalactites, pools, narrow passages, large caverns |
| Mine | 32x32 cells | 3m | Timber supports, ore veins, mine carts, vertical shafts |
| Sewers | 48x48 cells | 3m | Channels (1m deep water), walkways, grates, junctions |
| Catacombs | 48x48 cells | 2.5m | Bone niches, sarcophagi, narrow corridors, crypts |
| Underground river | Linear, 200-400m | 5-8m | Boat traversal, cave with water, waterfalls |

---

## 3. Interior Furnishing Standards

### Design Philosophy
Every room must feel lived-in (or abandoned-in). The "minimum viable furnishing" list below represents what is needed for an AAA-quality feel. Items marked with * are required; unmarked items are strongly recommended.

### 3.1 Tavern / Inn Common Room
**Room size:** 10x8m to 14x10m, 3.5m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Bar counter | 1 | Against back wall | 3.0 x 0.8 x 1.1 |
| *Bar stools | 3-4 | Along bar | 0.4 x 0.4 x 0.7 |
| *Tables (round/square) | 3-5 | Center area, scattered | 1.0-1.2 diameter x 0.75h |
| *Chairs | 8-16 | Around tables, 2-4 per table | 0.5 x 0.5 x 0.9 |
| *Fireplace | 1 | Side wall | 1.5 x 0.8 x 1.8 |
| *Hanging lanterns | 3-5 | Ceiling, over tables and bar | 0.3 x 0.3 x 0.4 |
| *Barrels (ale/wine) | 3-6 | Behind bar, corners | 0.6 dia x 0.8h |
| Tankards/mugs | 8-12 | On tables, bar | 0.1 x 0.1 x 0.15 |
| Plates/bowls | 6-10 | On tables | 0.25 dia |
| Shelves (bottles) | 1-2 | Behind bar, wall | 1.5 x 0.4 x 1.8 |
| Trophy/mounted head | 0-2 | Above fireplace | 0.8 x 0.5 x 0.8 |
| Stairs to upper floor | 1 | Corner or side wall | 1.0w, standard rise |
| Broom/mop | 1 | Corner | 0.1 x 0.1 x 1.5 |
| Notice board | 1 | Near door | 0.8 x 0.05 x 1.0 |

### 3.2 Throne Room
**Room size:** 15x10m to 30x15m, 5-8m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Throne | 1 | Center of back wall, on dais (0.3m raised) | 1.5 x 1.2 x 2.0 |
| *Red carpet/runner | 1 | Center aisle, door to throne | 3.0w x length of room |
| *Pillars | 4-8 | Flanking center aisle, evenly spaced | 0.6 dia x ceiling height |
| *Banners/tapestries | 4-8 | Between pillars, on walls | 1.0 x 0.1 x 2.5 |
| *Chandelier | 1-3 | Ceiling, over center aisle | 1.5 dia x 1.0h |
| Guard positions (markers) | 4-8 | Flanking throne, at pillars, at doors | -- |
| Braziers/fire bowls | 2-4 | Flanking throne, at pillar bases | 0.5 x 0.5 x 1.0 |
| Weapon display | 0-2 | Wall niches | 1.0 x 0.3 x 2.0 |
| Audience benches | 0-4 | Along walls | 2.0 x 0.5 x 0.5 |
| Advisor's desk | 0-1 | Side of throne | 1.2 x 0.6 x 0.75 |

### 3.3 Prison / Dungeon Cells
**Room size:** 10x10m to 15x15m (total prison block), cells 2x3m each, 2.5m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Cell doors (iron bars) | 4-8 | Cell openings | 1.0 x 0.1 x 2.0 |
| *Chains (wall-mounted) | 2-4 per cell | Back wall of cells | 0.3 x 0.3 x 1.5 drop |
| *Straw/bedroll | 1 per cell | Floor of each cell | 0.7 x 1.8 x 0.1 |
| *Skeleton/bones | 1-3 | In cells, on floor, chained to wall | -- |
| *Guard station/desk | 1 | Outside cells, near entrance | 1.2 x 0.6 x 0.75 |
| Guard's chair | 1 | At guard station | 0.5 x 0.5 x 0.9 |
| Key rack | 1 | Guard station wall | 0.4 x 0.1 x 0.3 |
| Torch sconces | 2-4 | Corridor walls | 0.2 x 0.3 x 0.4 |
| Bucket | 1 per cell | Corner of cell | 0.35 dia x 0.3h |
| Torture device (rack/iron maiden) | 0-2 | Separate torture chamber | 2.0 x 1.0 x 2.0 |
| Drain grate | 1-2 | Floor | 0.5 x 0.5 |
| Rat (decorative/animated) | 2-4 | Scattered | 0.15 x 0.05 x 0.05 |

### 3.4 Bedroom
**Room size:** 5x5m to 8x8m, 3.0m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Bed | 1 | Against wall (head against wall) | 2.0 x 1.5 x 0.6 (single/double) |
| *Wardrobe/armoire | 1 | Against wall | 1.2 x 0.6 x 1.8 |
| *Desk | 1 | Near window | 1.2 x 0.6 x 0.75 |
| *Chair | 1 | At desk | 0.5 x 0.5 x 0.9 |
| *Candles/candlestick | 2-3 | On desk, nightstand, shelf | 0.1 dia x 0.3h |
| *Rug | 1 | Center or beside bed | 2.0 x 1.5 x 0.02 |
| *Window (if exterior wall) | 1 | Wall | 0.8 x 1.2 opening |
| Nightstand | 1 | Beside bed | 0.5 x 0.5 x 0.5 |
| Mirror | 0-1 | Above desk or on wardrobe | 0.5 x 0.05 x 0.8 |
| Chest | 0-1 | Foot of bed | 0.8 x 0.5 x 0.4 |
| Chamber pot | 0-1 | Under bed or corner | 0.3 dia x 0.2h |
| Book/journal | 1-2 | On desk | 0.2 x 0.15 x 0.03 |

### 3.5 Kitchen
**Room size:** 6x6m to 10x8m, 3.0m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Cooking fire/oven | 1 | Wall (chimney required) | 1.5 x 0.8 x 1.0 |
| *Work table | 1-2 | Center | 1.5 x 1.0 x 0.75 |
| *Hanging pots/pans | 3-6 | Above fire, ceiling rack | 0.3-0.5 dia |
| *Shelves | 1-2 | Walls | 2.0 x 0.4 x 1.8 |
| *Food items | 5-10 | On tables, shelves, hanging | Various (bread, cheese, meat) |
| Barrels (flour, salt) | 2-3 | Corners | 0.6 dia x 0.8h |
| Crates | 1-2 | Corners | 0.6 x 0.6 x 0.6 |
| Water bucket/basin | 1 | Near fire | 0.5 dia x 0.3h |
| Cutting board + knife | 1 | On work table | 0.4 x 0.25 |
| Herb bundles (hanging) | 2-4 | Ceiling beams | 0.2 x 0.2 x 0.3 |
| Spit roast | 0-1 | Over fire | 1.0 length |

### 3.6 Library / Study
**Room size:** 6x8m to 10x10m, 3.5m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Bookshelves | 3-6 | Against walls (floor to near ceiling) | 2.0 x 0.5 x 2.5 |
| *Reading desk | 1-2 | Center or near window | 1.5 x 0.8 x 0.75 |
| *Chair | 1-2 | At desks | 0.5 x 0.5 x 0.9 |
| *Candelabra | 2-4 | On desks, freestanding | 0.3 dia x 1.2h (standing), 0.3h (table) |
| *Scrolls/open books | 3-5 | On desks, shelves | Various |
| Ladder (rolling) | 0-1 | Along bookshelves | 0.4 x 0.1 x 2.5 |
| Globe/orrery | 0-1 | On desk or stand | 0.4 dia |
| Alchemy equipment | 0-1 set | On desk | 0.3 x 0.3 x 0.5 |
| Map (wall-mounted) | 0-1 | Wall | 1.0 x 0.05 x 0.7 |
| Rug | 1 | Center | 2.5 x 2.0 x 0.02 |
| Skull/curiosity | 0-2 | On shelves | 0.2 x 0.2 x 0.2 |

### 3.7 Armory
**Room size:** 6x8m to 10x8m, 3.0m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Weapon racks | 2-4 | Walls | 2.0 x 0.5 x 2.0 |
| *Armor stands | 2-4 | Along walls, in niches | 0.6 x 0.6 x 1.8 |
| *Workbench | 1 | Center or wall | 2.0 x 0.8 x 0.9 |
| *Tools (hammer, tongs, file) | 3-5 | On/near workbench | Various small |
| Shield rack | 1-2 | Wall | 1.5 x 0.3 x 1.5 |
| Weapon crate | 1-2 | Floor | 0.8 x 0.8 x 0.6 |
| Grindstone | 0-1 | Near workbench | 0.5 x 0.5 x 0.8 |
| Practice dummy | 0-1 | Open corner | 0.5 x 0.5 x 1.7 |
| Oil/whetstone | 1-2 | On workbench | 0.1 x 0.1 x 0.15 |

### 3.8 Temple / Altar Room
**Room size:** 8x15m to 12x20m, 4-6m ceiling

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Altar | 1 | Center-back of room, raised platform | 1.5 x 0.8 x 1.2 |
| *Candles (altar) | 4-8 | On and around altar | 0.08 dia x 0.2-0.4h |
| *Pews/kneeling areas | 4-8 rows | Center, facing altar | 2.0 x 0.6 x 0.8 |
| *Religious symbol/statue | 1 | Behind/above altar, on wall | 1.0 x 0.5 x 2.0 |
| *Incense burners | 2-4 | Flanking altar, on stands | 0.3 dia x 0.3h (+smoke VFX) |
| Stained glass windows | 1-3 | Side walls (if exterior) | 1.0 x 2.0 opening |
| Offering bowl | 1-2 | At altar base | 0.4 dia x 0.15h |
| Banners | 2-4 | Walls, pillars | 0.8 x 0.1 x 2.5 |
| Pillars | 2-4 | Flanking nave | 0.5 dia x ceiling height |
| Holy water font | 0-1 | Near entrance | 0.5 dia x 1.0h |
| Carpet/runner | 1 | Center aisle | 2.0w x room length |

**Dark fantasy variant (corrupted temple):**
- Blood stains on altar and floor
- Inverted/broken religious symbols
- Black candles, green/purple flame VFX
- Skeletal remains at pews
- Dark fog/mist at floor level
- Disturbing wall carvings

### 3.9 Blacksmith / Forge
**Room size:** 8x10m (partially open-air), 4m ceiling where roofed

| Item | Count | Placement | Dimensions (m) |
|------|-------|-----------|----------------|
| *Forge (with fire) | 1 | Center-back, against chimney wall | 1.5 x 1.0 x 1.0 |
| *Anvil | 1 | Near forge | 0.5 x 0.3 x 0.8 |
| *Bellows | 1 | Adjacent to forge | 0.8 x 0.4 x 1.0 |
| *Tool rack (hammers, tongs) | 1-2 | Wall near forge | 1.5 x 0.3 x 1.5 |
| *Weapon/item display | 1 | Customer-facing area | 2.0 x 0.5 x 2.0 |
| *Cooling trough (water) | 1 | Near anvil | 1.5 x 0.5 x 0.5 |
| Grindstone | 1 | Near anvil | 0.5 x 0.5 x 0.8 |
| Coal pile/bin | 1 | Near forge | 0.8 x 0.8 x 0.5 |
| Metal ingot stack | 1-2 | Near forge | 0.4 x 0.4 x 0.3 per stack |
| Barrel (quench oil) | 1 | Near forge | 0.5 dia x 0.8h |
| Customer counter | 0-1 | Front of shop | 1.5 x 0.6 x 1.0 |

---

## 4. Environment Cohesion

### 4.1 Texture Consistency Pipeline

**Problem:** Terrain textures, building textures, and prop textures must read as one unified world, not a kit-bash of mismatched assets.

**Solution -- Unified Material Palette:**

```
MATERIAL PALETTE (per biome)
  |
  +-- Base colors: 5-8 colors per biome (stone grey, wood brown, iron dark, etc.)
  +-- Roughness range: consistent min/max across all assets in biome
  +-- Normal map style: consistent bevel intensity, detail frequency
  +-- Wear patterns: same dirt/damage overlay approach everywhere
```

| Cohesion Rule | Implementation |
|--------------|----------------|
| Shared color palette per biome | Define 5-8 base colors per biome in config; all generated textures sample from this palette |
| Consistent PBR value ranges | Stone roughness: 0.6-0.8 everywhere; wood roughness: 0.4-0.7; metal roughness: 0.2-0.5 |
| Matching texture resolution | All props/buildings at 1024x1024 or 2048x2048 (same texel density ~512 px/m) |
| Tiling consistency | All tileable textures at same physical scale (1m = 1 tile repeat for stone, 0.5m for brick) |
| Shared detail textures | One set of dirt, moss, scratches, stains overlaid on all materials per biome |

### 4.2 Ground-to-Building Blending

**Technique: Vertex color terrain blending**

Buildings placed on terrain need their base to blend with the ground, not float on sharp edges.

| Method | How It Works | MCP Toolkit Action |
|--------|-------------|-------------------|
| Vertex color painting | Paint vertex colors on building base vertices; shader blends between building material and terrain texture based on vertex alpha | Generate buildings with vertex color data on bottom 0.3m of geometry |
| Decal projection | Project dirt/ground decal at building base | Export decal placement data alongside building position |
| Terrain depression | Slightly lower terrain vertices under building footprint | Modify heightmap at building placement coordinates |
| Foundation overlap | Building foundation extends 0.1-0.2m below terrain surface | Already in _building_grammar.py foundation spec |

### 4.3 Fog & Atmospheric Effects

| Time of Day | Fog Type | Fog Color (RGB) | Fog Density | Start/End Distance |
|------------|---------|-----------------|-------------|---------------------|
| Dawn (6:00) | Linear + volumetric | (0.85, 0.75, 0.65) warm gold | 0.015 | 20m / 200m |
| Morning (9:00) | Linear | (0.80, 0.85, 0.90) cool white | 0.005 | 50m / 500m |
| Midday (12:00) | None or very light | (0.85, 0.90, 0.95) | 0.002 | 100m / 1000m |
| Afternoon (15:00) | Linear | (0.85, 0.82, 0.75) warm | 0.004 | 60m / 400m |
| Golden Hour (17:00) | Linear + volumetric | (0.95, 0.75, 0.50) deep gold | 0.010 | 30m / 250m |
| Dusk (19:00) | Heavy volumetric | (0.60, 0.45, 0.55) purple-grey | 0.020 | 15m / 150m |
| Night (22:00) | Heavy linear | (0.15, 0.18, 0.25) dark blue | 0.025 | 10m / 100m |
| Midnight (0:00) | Very heavy | (0.08, 0.10, 0.15) near-black | 0.035 | 5m / 60m |

**Dark fantasy enhancement:** In corrupted/blighted areas, increase fog density by 2-3x and shift color toward sickly green (0.3, 0.4, 0.2) or blood red (0.4, 0.15, 0.1).

### 4.4 Time-of-Day Lighting Presets

| Preset | Sun Direction (deg) | Sun Color (Kelvin) | Sun Intensity | Ambient Color (RGB) | Shadow Strength |
|--------|--------------------|--------------------|---------------|---------------------|-----------------|
| Dawn | 5 elevation, 90 azimuth (East) | 2500K deep orange | 0.4 | (0.25, 0.18, 0.15) | 0.3 |
| Morning | 30 elevation, 120 azimuth | 4000K warm white | 0.8 | (0.30, 0.28, 0.25) | 0.6 |
| Midday | 75 elevation, 180 azimuth (South) | 5500K neutral | 1.0 | (0.35, 0.35, 0.38) | 0.8 |
| Afternoon | 40 elevation, 240 azimuth | 4500K warm | 0.85 | (0.32, 0.30, 0.25) | 0.7 |
| Golden Hour | 10 elevation, 270 azimuth (West) | 2200K deep gold | 0.5 | (0.30, 0.20, 0.12) | 0.4 |
| Dusk | 2 elevation, 280 azimuth | 2000K red-orange | 0.2 | (0.18, 0.12, 0.15) | 0.2 |
| Night | -30 (below horizon) | Moon: 8000K blue-white | 0.05 | (0.05, 0.06, 0.10) | 0.1 |
| Overcast | 60 elevation | 6500K cool grey | 0.5 | (0.25, 0.25, 0.28) | 0.15 |

### 4.5 Ambient Sound Zones

| Zone Type | Sound Layer 1 (Background) | Sound Layer 2 (Detail) | Sound Layer 3 (Spot) |
|-----------|---------------------------|----------------------|---------------------|
| Forest (day) | Wind through leaves (loop) | Birdsong, insects (randomized) | Branch snap, distant animal call |
| Forest (night) | Deep wind, silence (loop) | Owls, wolves howling (rare) | Twig snap, footsteps (tension) |
| Town (day) | Crowd murmur (loop) | Blacksmith hammering, chickens, cart wheels | Shopkeeper calls, children playing |
| Town (night) | Quiet wind (loop) | Distant tavern music, dog barking | Guard footsteps, door creak |
| Dungeon | Dripping water, deep hum (loop) | Chains rattling, distant moans | Stone grinding, scream echo |
| Cave | Wind whistle, water drip (loop) | Bat wing flutters, loose gravel | Stalagmite drip impact, echo |
| Swamp | Bubbling, thick air (loop) | Frogs, flies, squelching | Splash, gas bubble, distant cry |
| Castle interior | Stone echo, fire crackle (loop) | Footsteps echo, armor clink | Door slam, banner flap |
| Boss arena | Ominous drone (loop) | Boss breathing/growling | Impact sounds, arena collapse |

**Implementation:** Each zone defines a trigger volume. Sound layers crossfade over 2-3 seconds when the player crosses zone boundaries. Spot sounds play at randomized intervals within the zone.

---

## 5. Performance for Dense Interiors

### 5.1 LOD Strategy for Interior-Heavy Scenes

| LOD Level | Distance (m) | Geometry | Textures | Use Case |
|-----------|-------------|----------|----------|----------|
| LOD0 | 0-10 | Full detail | Full resolution (1024-2048) | Current room + adjacent |
| LOD1 | 10-30 | 50% triangles | Half resolution (512-1024) | Nearby rooms visible through doors |
| LOD2 | 30-80 | 25% triangles | Quarter resolution (256-512) | Distant exterior buildings |
| LOD3 | 80+ | Billboard or box | 64x64 or solid color | Far buildings, skyline |
| Culled | Not visible | Nothing | Nothing | Behind occluders |

**Interior LOD rules:**
- Furniture inside current room: always LOD0
- Furniture visible through doorways: LOD1
- Furniture in closed rooms: CULLED (do not render)
- Small props (mugs, plates, candles) beyond 10m: CULLED

### 5.2 Occlusion Culling Strategy

**Core principle:** When player is INSIDE a building, do NOT render the exterior world. When player is OUTSIDE, do NOT render building interiors.

| Scenario | What to Render | What to Cull |
|----------|---------------|-------------|
| Player outside, buildings closed | Building exteriors, terrain, vegetation | All interiors |
| Player outside, looking through window | Building exterior + visible interior of THAT building only | All other interiors |
| Player in building lobby/entry | Entry room interior, visible connected rooms, building exterior shell | Distant terrain details, other building interiors, far vegetation |
| Player deep inside building | Current room + rooms visible through open doors/windows | Everything else |
| Player in dungeon | Current dungeon area + connected corridors | Entire overworld |

**Unity implementation:**
- Mark all building shells as **Static Occluders** (they block visibility)
- Mark all interior furniture as **Static Occludees** (they get hidden when blocked)
- Use **Umbra** (Unity's built-in occlusion system) with bake settings:
  - Smallest Occluder: 2.0m (buildings are larger than this)
  - Smallest Hole: 0.5m (windows and doors)
  - Backface Threshold: 100 (default)
- For dungeons: each room is a separate occlusion area connected by portal-like doorways
- Indoor/outdoor can gain 90%+ GPU savings (documented: 30fps to 72fps improvement in dense interiors)

### 5.3 Draw Call Batching for Repeated Furniture

| Technique | When to Use | Expected Savings |
|-----------|-------------|-----------------|
| **Static batching** | Furniture that never moves (shelves, tables, beds) | Combines meshes sharing same material into one draw call |
| **GPU instancing** | Many identical props (chairs, barrels, crates, candles) | One draw call per unique mesh+material combo, unlimited instances |
| **SRP Batcher** | All materials using same shader variant | Reduces CPU overhead of material setup |
| **Dynamic batching** | Small moving objects (< 300 verts, rats, butterflies) | Auto-combines small meshes |

**Practical approach for VeilBreakers:**
1. Group all furniture into **material categories**: wood_dark, wood_light, stone, metal, cloth
2. Create **texture atlases** per category: one 2048x2048 atlas holds all wood furniture textures
3. All items sharing an atlas use the **same material** -> eligible for static batching
4. Repeated identical items (20 identical chairs in a tavern) -> GPU instancing

### 5.4 Texture Atlasing for Props

| Atlas Category | Atlas Size | Items Included | Texel Density |
|---------------|-----------|----------------|---------------|
| Wood furniture | 2048x2048 | Tables, chairs, beds, shelves, barrels, crates, doors | 512 px/m |
| Stone elements | 2048x2048 | Altars, pillars, sarcophagi, statues, walls, floors | 512 px/m |
| Metal items | 1024x1024 | Weapons, armor stands, chains, bars, tools, candlesticks | 512 px/m |
| Cloth/organic | 1024x1024 | Rugs, banners, bedding, curtains, rope, food | 512 px/m |
| Small props | 1024x1024 | Books, bottles, mugs, plates, candles, skulls, keys | 256 px/m |

**Rule:** No individual prop should have its own unique texture. Every prop UV maps to a shared atlas. This is the single most impactful optimization for interior-heavy scenes.

### 5.5 Instance Rendering for Repeated Decorative Items

| Item Type | Expected Instance Count | Rendering Method |
|-----------|----------------------|-----------------|
| Candles/torches | 50-200 per interior area | GPU instancing + LOD (billboard at distance) |
| Books on shelves | 100-500 per library | GPU instancing (3-4 book mesh variants) |
| Barrel/crate | 20-100 per town | Static batching (same atlas material) |
| Chairs/stools | 10-50 per building | Static batching |
| Wall sconces | 20-50 per dungeon level | GPU instancing |
| Bones/skulls | 30-100 per dungeon | GPU instancing (5-6 variants) |
| Cobwebs | 20-50 per dungeon | GPU instancing (billboard quad) |
| Food items | 10-30 per kitchen/tavern | Static batching (atlas material) |

---

## 6. MCP Toolkit Gap Analysis

### 6.1 What We Already Have

| Capability | File | Status |
|-----------|------|--------|
| Terrain heightmap generation (6 presets) | `_terrain_noise.py` | DONE |
| Hydraulic + thermal erosion | `_terrain_erosion.py` | DONE |
| Terrain mesh creation in Blender | `environment.py` | DONE |
| Biome auto-painting (slope/altitude) | `environment.py` | DONE |
| River carving (A* path) | `environment.py` | DONE |
| Road generation with grading | `environment.py` | DONE |
| Water body creation | `environment.py` | DONE |
| Heightmap export (16-bit RAW, Unity) | `environment.py` | DONE |
| BSP dungeon generation | `_dungeon_gen.py` | DONE |
| Cellular automata caves | `_dungeon_gen.py` | DONE |
| Voronoi town layout | `_dungeon_gen.py` | DONE |
| Building grammar (5 styles) | `_building_grammar.py` | DONE |
| Castle / tower / bridge / fortress | `_building_grammar.py` | DONE |
| Ruins damage system | `_building_grammar.py` | DONE |
| Interior furniture layout (8 room types) | `_building_grammar.py` | DONE |
| Modular architecture kit | `_building_grammar.py` | DONE |
| Poisson disk scatter | `_scatter_engine.py` | DONE |
| Biome-filtered vegetation | `_scatter_engine.py` | DONE |
| Context-aware prop scatter | `_scatter_engine.py` | DONE |
| Breakable prop variants | `_scatter_engine.py` | DONE |

### 6.2 What We Need for Complete Worlds

| Gap | Priority | Description |
|-----|----------|-------------|
| **World graph / region system** | HIGH | Overworld divided into regions with connectivity graph. Define regions, their biomes, location slots, and travel routes. Currently we generate individual terrain/dungeons/towns but have no system to compose them into a unified world. |
| **Location placement on terrain** | HIGH | Place town/dungeon/camp/castle markers on heightmap with proper grounding (flatten terrain under building, cut roads between locations). Currently buildings and terrain are separate. |
| **Interior-exterior linking** | HIGH | Buildings generated with both exterior shell and interior rooms. Currently interiors and buildings are separate handlers. Need: building exterior -> door -> interior room chain. |
| **Dungeon vertical stacking** | MEDIUM | Multi-floor dungeons with descending levels. Current BSP generates 2D grid. Need: stacked grids with staircase connections between floors. |
| **Boss arena generator** | MEDIUM | Dedicated handler for boss arenas with configurable hazards, cover objects, phase triggers. Not currently a distinct system. |
| **Easter egg / secret room system** | MEDIUM | Mark hidden rooms with special access (breakable walls, hidden switches, underwater passages). Currently rooms are all equally accessible. |
| **Ambient zone export** | MEDIUM | Export sound zone definitions (trigger volumes + audio config) alongside geometry for Unity import. |
| **LOD generation for buildings** | MEDIUM | Auto-generate LOD1/LOD2 versions of buildings. Pipeline LOD handler exists for meshes but not integrated with building generation. |
| **Fog/atmosphere presets** | LOW | Export time-of-day and fog configs as Unity-importable data. Could be JSON config files. |
| **Texture atlas generation** | LOW | Auto-pack prop textures into atlases with UV remapping. Could integrate with existing texture handlers. |
| **NPC placement markers** | LOW | Export guard positions, vendor locations, patrol routes as metadata alongside geometry. |

### 6.3 Existing Code Strengths

The current codebase already handles the hard algorithmic problems well:
- `_building_grammar.py` generates 8 interior room types with collision-avoidance furniture placement
- `_dungeon_gen.py` guarantees connectivity via flood-fill verification
- `_scatter_engine.py` handles blue-noise distribution and context-aware prop placement
- `_terrain_noise.py` + `_terrain_erosion.py` produce realistic terrain with 6 presets
- All pure-logic modules are fully testable without Blender

The main gap is **composition** -- connecting individual generated pieces into a coherent world graph with proper spatial relationships, transitions, and metadata export for Unity.

---

## 7. Recommended Constants & Configs

### 7.1 World Scale Constants

```python
WORLD_CONSTANTS = {
    # Player
    "player_walk_speed": 1.4,         # m/s
    "player_jog_speed": 3.5,          # m/s
    "player_sprint_speed": 6.0,       # m/s
    "player_height": 1.8,             # m
    "player_width": 0.6,              # m (collision capsule)

    # World scale
    "overworld_size": 2048,            # m per side (2km x 2km)
    "terrain_resolution": 2049,        # heightmap pixels (power-of-two + 1)
    "terrain_cell_size": 1.0,          # m per heightmap pixel
    "poi_interval": 100,               # m between points of interest (30-sec rule)

    # Buildings
    "story_height": 3.0,              # m per floor (medieval standard)
    "wall_thickness": 0.3,            # m (standard building)
    "fortress_wall_thickness": 1.5,   # m (castle/fortress)
    "door_width": 1.2,               # m
    "door_height": 2.2,              # m
    "window_width": 0.8,             # m
    "window_height": 1.2,            # m

    # Dungeons
    "dungeon_cell_size": 2.0,         # m per grid cell
    "corridor_width": 3.0,            # m
    "corridor_height": 3.0,           # m
    "boss_arena_min": 20.0,           # m per side
    "boss_arena_max": 40.0,           # m per side

    # Performance
    "lod0_distance": 10.0,            # m
    "lod1_distance": 30.0,            # m
    "lod2_distance": 80.0,            # m
    "cull_distance": 150.0,           # m (beyond this, not rendered)
    "small_prop_cull_distance": 10.0, # m (mugs, plates, candles)
}
```

### 7.2 Biome Definitions

```python
BIOME_CONFIGS = {
    "darkwood_forest": {
        "terrain_type": "hills",
        "height_range": (0.1, 0.5),
        "fog_color": (0.15, 0.20, 0.12),
        "fog_density": 0.02,
        "vegetation_density": 0.8,
        "tree_types": ["dead_oak", "twisted_pine", "willow"],
        "ground_cover": ["dark_grass", "fern", "mushroom", "fallen_leaves"],
        "ambient": "forest_dark",
        "palette": {
            "stone": (0.35, 0.33, 0.30),
            "wood": (0.25, 0.18, 0.12),
            "earth": (0.20, 0.15, 0.10),
        },
    },
    "blighted_marsh": {
        "terrain_type": "lowlands",
        "height_range": (0.0, 0.2),
        "fog_color": (0.25, 0.30, 0.18),
        "fog_density": 0.04,
        "vegetation_density": 0.5,
        "tree_types": ["dead_tree", "mangrove", "swamp_willow"],
        "ground_cover": ["swamp_grass", "lily_pad", "moss", "reeds"],
        "ambient": "swamp",
        "palette": {
            "stone": (0.30, 0.32, 0.25),
            "wood": (0.20, 0.22, 0.15),
            "earth": (0.15, 0.18, 0.10),
        },
    },
    "ashen_mountains": {
        "terrain_type": "mountains",
        "height_range": (0.4, 1.0),
        "fog_color": (0.40, 0.38, 0.35),
        "fog_density": 0.01,
        "vegetation_density": 0.2,
        "tree_types": ["dead_pine", "charred_trunk"],
        "ground_cover": ["ash", "volcanic_rock", "ember_moss"],
        "ambient": "mountain_wind",
        "palette": {
            "stone": (0.40, 0.38, 0.35),
            "wood": (0.15, 0.10, 0.08),
            "earth": (0.30, 0.25, 0.20),
        },
    },
    "cursed_ruins": {
        "terrain_type": "plateau",
        "height_range": (0.3, 0.6),
        "fog_color": (0.30, 0.15, 0.20),
        "fog_density": 0.03,
        "vegetation_density": 0.3,
        "tree_types": ["dead_tree", "corrupted_oak"],
        "ground_cover": ["dead_grass", "bone_fragments", "dark_moss"],
        "ambient": "ruins_ominous",
        "palette": {
            "stone": (0.28, 0.25, 0.28),
            "wood": (0.18, 0.12, 0.10),
            "earth": (0.22, 0.18, 0.20),
        },
    },
}
```

### 7.3 Room Type Expansion (Beyond Current _building_grammar.py)

The current `_ROOM_CONFIGS` in `_building_grammar.py` covers 8 room types. For complete world generation, we need these additional types:

```python
ADDITIONAL_ROOM_TYPES = {
    "guard_barracks": [
        ("bunk_bed", "wall", (1.8, 0.9), 1.8),    # stacked beds
        ("bunk_bed", "wall", (1.8, 0.9), 1.8),
        ("bunk_bed", "wall", (1.8, 0.9), 1.8),
        ("weapon_rack", "wall", (2.0, 0.5), 2.0),
        ("footlocker", "wall", (0.8, 0.5), 0.4),
        ("footlocker", "wall", (0.8, 0.5), 0.4),
        ("table", "center", (1.2, 0.8), 0.75),
        ("lantern", "wall", (0.3, 0.3), 0.4),
    ],
    "treasury": [
        ("chest_large", "wall", (1.0, 0.7), 0.6),
        ("chest_large", "wall", (1.0, 0.7), 0.6),
        ("chest_small", "wall", (0.6, 0.4), 0.4),
        ("coin_pile", "center", (0.5, 0.5), 0.3),
        ("display_case", "wall", (1.5, 0.5), 1.5),
        ("pedestal", "center", (0.4, 0.4), 1.0),
        ("lantern", "wall", (0.3, 0.3), 0.4),
    ],
    "war_room": [
        ("map_table", "center", (2.5, 1.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("chair", "center", (0.5, 0.5), 0.9),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("banner", "wall", (0.8, 0.1), 2.5),
        ("candelabra", "center", (0.3, 0.3), 1.2),
        ("weapon_display", "wall", (1.5, 0.3), 2.0),
    ],
    "alchemy_lab": [
        ("alchemy_table", "center", (1.5, 0.8), 0.9),
        ("shelf_potions", "wall", (2.0, 0.5), 2.0),
        ("shelf_potions", "wall", (2.0, 0.5), 2.0),
        ("cauldron", "center", (0.8, 0.8), 0.7),
        ("ingredient_rack", "wall", (1.5, 0.4), 1.8),
        ("candle", "center", (0.1, 0.1), 0.3),
        ("skull", "wall", (0.2, 0.2), 0.2),
        ("book_open", "center", (0.3, 0.2), 0.05),
    ],
    "torture_chamber": [
        ("rack_device", "center", (2.5, 1.0), 1.8),
        ("iron_maiden", "wall", (0.8, 0.8), 2.0),
        ("chains_ceiling", "center", (0.3, 0.3), 2.5),
        ("chains_ceiling", "center", (0.3, 0.3), 2.5),
        ("brazier_hot", "center", (0.5, 0.5), 0.8),
        ("tool_table", "wall", (1.2, 0.6), 0.75),
        ("blood_drain", "center", (0.5, 0.5), 0.1),
        ("cage_hanging", "center", (1.0, 1.0), 2.0),
    ],
    "crypt": [
        ("sarcophagus", "center", (2.0, 0.8), 1.0),
        ("sarcophagus", "wall", (2.0, 0.8), 1.0),
        ("candelabra", "center", (0.3, 0.3), 1.5),
        ("candelabra", "center", (0.3, 0.3), 1.5),
        ("offering_table", "wall", (1.0, 0.6), 0.75),
        ("urn", "wall", (0.3, 0.3), 0.5),
        ("urn", "wall", (0.3, 0.3), 0.5),
        ("skeleton_wall", "wall", (0.5, 0.2), 1.7),
    ],
    "dining_hall": [
        ("long_table", "center", (4.0, 1.2), 0.75),
        ("bench", "center", (3.5, 0.5), 0.45),
        ("bench", "center", (3.5, 0.5), 0.45),
        ("chair_head", "center", (0.6, 0.6), 1.2),
        ("chandelier", "center", (1.5, 1.5), 0.8),
        ("fireplace", "wall", (2.0, 0.8), 2.0),
        ("tapestry", "wall", (1.5, 0.1), 2.5),
        ("serving_table", "wall", (2.0, 0.6), 0.75),
    ],
}
```

---

## Sources

### Map Size & World Design
- [Elden Ring Map Size Comparison](https://www.ggrecon.com/guides/elden-ring-map-size-comparison/)
- [Video Game Worlds Bigger Than Skyrim](https://gamerant.com/video-game-worlds-bigger-elder-scrolls-skyrim/)
- [How Many Unique Locations Skyrim Has](https://screenrant.com/skyrim-how-many-locations-big-map-size/)
- [Skyrim Places - UESP Wiki](https://en.uesp.net/wiki/Skyrim:Places)
- [Skyrim Dungeons - UESP Wiki](https://en.uesp.net/wiki/Skyrim:Dungeons)

### Level Design & Pacing
- [Pacing - The Level Design Book](https://book.leveldesignbook.com/process/preproduction/pacing)
- [Open World Level Design - Gamedeveloper.com](https://www.gamedeveloper.com/design/open-world-level-design-the-full-vision-part-3-5-)
- [The Ultimate Guide to 5 Room Dungeons](https://www.roleplayingtips.com/5-room-dungeons/)
- [The Nine Forms of the Five Room Dungeon](https://gnomestew.com/the-nine-forms-of-the-five-room-dungeon/)

### Castle & Architecture
- [Castle Keep - World History Encyclopedia](https://www.worldhistory.org/Castle_Keep/)
- [Medieval Castle Layout - Exploring Castles](https://www.exploring-castles.com/castle_designs/medieval_castle_layout/)
- [Great Hall - Wikipedia](https://en.wikipedia.org/wiki/Great_hall)

### Boss Design
- [70 Tips for Better Boss Battles](https://www.mtblackgames.com/blog/65-tips-for-better-boss-battles)
- [Dark Souls 3 Coolest Boss Arenas](https://www.thegamer.com/dark-souls-3-coolest-boss-arenas/)
- [How to Create Epic Boss Fights](https://dumpstatadventures.com/the-gm-is-always-right/how-to-create-epic-boss-fights)

### Unity Performance
- [Unity Occlusion Culling Manual](https://docs.unity3d.com/6000.3/Documentation/Manual/OcclusionCulling.html)
- [Unity Draw Call Batching 2026](https://thegamedev.guru/unity-performance/draw-call-optimization/)
- [Unity Texture Atlases](https://learn.unity.com/course/3d-art-optimization-for-mobile-gaming-5474/unit/textures-5559/tutorial/texture-atlases-7428)
- [Unity Terrain Settings](https://docs.unity3d.com/Manual/terrain-OtherSettings.html)

### Texture Cohesion & Atmosphere
- [Advanced Terrain Texture Splatting](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting)
- [Approach to Environment Design in AAA Games](https://80.lv/articles/approach-to-environment-design-in-aaa-games)
- [Creating Volumetric Fog - Unity](https://learn.unity.com/tutorial/creating-volumetric-fog-18)

### Player Movement
- [Character Movement Speeds - Unity Discussions](https://discussions.unity.com/t/character-movement-speeds/1635603)
- [Unity Terrain Size Discussion](https://discussions.unity.com/t/terrain-size-units-heightmaps-resolution/745956)
