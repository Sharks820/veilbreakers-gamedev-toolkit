# Bethesda Modular Kit System - Ultra Deep Dive Research

**Researched:** 2026-04-02
**Domain:** Modular Level Design, Procedural Architecture, Snap Systems
**Confidence:** HIGH (primary sources: GDC talks, Creation Kit docs, official tutorials)

---

## Table of Contents

1. [Mission 1: Joel Burgess GDC 2013 - Skyrim's Modular Level Design](#mission-1)
2. [Mission 2: Bethesda Creation Kit Technical Details](#mission-2)
3. [Mission 3: Fallout 4 Settlement Building System](#mission-3)
4. [Mission 4: Starfield Procedural POIs](#mission-4)
5. [Mission 5: CGA Split Grammar Deep Dive](#mission-5)
6. [Mission 6: Snap Connector Implementation in Python/Blender](#mission-6)

---

<a name="mission-1"></a>
## Mission 1: Joel Burgess GDC 2013 - Skyrim's Modular Level Design

### Source
Joel Burgess, Bethesda Game Studios. GDC 2013 "Level Design in a Day" bootcamp.
- Blog transcript: http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html
- Slides: https://www.slideshare.net/JoelBurgess/gdc2013-kit-buildingfinal
- Gamasutra summary: https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design
- Confidence: HIGH (primary source from the actual developer)

### Production Scale

| Metric | Value |
|--------|-------|
| Total dungeons | 300+ |
| Points of interest | 140+ |
| Cities and villages | Dozens |
| Dungeon team size | 10 people (out of 90 total developers) |
| Development time | "A few years" |
| Median player playtime | 100+ hours |

### Kit Architecture

A **kit** is a collection of modular art pieces that snap together using a grid system. The core principle: kits "add up to far more than the sum of their parts" -- infinite configurations from relatively few base pieces.

#### Skyrim Kit Categories (from Creation Kit Object Window: WorldObjects > Static > Dungeons)

| Kit Prefix | Full Name | Description |
|------------|-----------|-------------|
| **Nor** | Nordic | Nordic tombs/crypts (Draugr dungeons) -- the flagship kit |
| **Imp** | Imperial | Imperial forts and underground structures |
| **Dwe** / **Dwem** | Dwemer | Dwarven ruins (mechanical/steampunk aesthetic) |
| **Cave** | Cave | Natural cave systems |
| **Mine** | Mine | Mining tunnels and shafts |
| **Ice** | Ice Cave | Frozen cave variants |
| **Riften** | Riften | Riften-style sewers/ratways |
| **Sol** | Solitude | Solitude architecture (noted as "most complex kit") |

Each major kit contains **sub-kits** organized by room type and size:

| Sub-Kit Code | Meaning | Example Filter |
|-------------|---------|----------------|
| **RmSm** | Room Small | NorRmSm* |
| **RmBg** / **RmLg** | Room Big/Large | NorRmBg* |
| **HallSm** | Hall Small | NorHallSm* |
| **HallBg** | Hall Big | NorHallBg* |
| **Plat** | Platform | NorPlat* |

### Naming Convention Breakdown (COMPLETE)

Format: `[Tileset][Type][Size][PieceKind][ExitType][Variant]`

Example: **NorRmSmWallSideExSm01**

| Segment | Code | Meaning |
|---------|------|---------|
| Tileset | **Nor** | Nordic |
| Type | **Rm** | Room |
| Size | **Sm** | Small |
| Piece Kind | **WallSide** | Side wall piece |
| Exit Type | **ExSm** | Small exit (doorway) |
| Variant | **01** | First variant |

#### All Known Tileset Prefixes

| Prefix | Tileset |
|--------|---------|
| Nor | Nordic |
| Imp | Imperial |
| Dwe / Dwem | Dwemer |
| Cave | Cave |
| Mine | Mine |
| Ice | Ice Cave |
| Rft | Riften |
| Sol | Solitude |

#### All Known Type Codes

| Code | Type | Description |
|------|------|-------------|
| Rm | Room | Enclosed rooms |
| Hall | Hall | Corridors/hallways |
| Plat | Platform | Open platform areas |
| Stair | Stair | Staircase pieces |
| Ent | Entrance | Entrance vestibules |

#### All Known Size Codes

| Code | Size |
|------|------|
| Sm | Small |
| Bg | Big |
| Lg | Large (sometimes used instead of Bg) |
| Med | Medium (rare) |

#### All Known Piece Kind Codes

| Code | Piece Type | Description |
|------|-----------|-------------|
| **WallSide** | Side Wall | Wall along the side of a room |
| **WallFront** | Front Wall | Wall facing the entrance direction |
| **CorIn** | Corner Inward | Interior corner piece (concave) |
| **CorOut** / **Cor** | Corner Outward | Exterior corner piece (convex) |
| **Mid** | Middle/Floor | Floor tile / center piece |
| **Ceil** | Ceiling | Ceiling piece |
| **Plat** | Platform | Raised platform section |
| **Col** | Column | Pillar/column piece |
| **Stair** | Stairs | Staircase piece |
| **Arch** | Arch | Archway piece |
| **Door** | Doorway | Door frame piece |

#### Exit System Codes

| Code | Exit Type | Description |
|------|-----------|-------------|
| **ExSm** | Exit Small | Small doorway/exit opening. Snaps with ANY other ExSm piece in the same kit |
| **ExBg** | Exit Big | Large doorway/exit opening. Snaps with ANY other ExBg piece in the same kit |
| **ExLg** | Exit Large | Extra-large transition (rare, typically for special connections) |

**Critical rule:** Exit pieces are the primary connector between rooms. An ExSm piece will snap precisely with any other ExSm piece from the same tileset. This is what enables rooms and halls of different sizes to connect freely -- the exits are standardized connection points.

#### Variant Numbers

| Pattern | Meaning |
|---------|---------|
| 01 | First variant |
| 02 | Second variant (minor shape/texture differences) |
| 03+ | Additional variants |

Most frequently applied to: walls, hallway pieces, mid/floor pieces. Variants provide visual variety while maintaining identical snap behavior.

### Complete Example Pieces (Nordic Small Room)

```
NorRmSmMid01           -- Floor tile, variant 1
NorRmSmMid02           -- Floor tile, variant 2
NorRmSmWallSide01      -- Side wall, variant 1
NorRmSmWallSide02      -- Side wall, variant 2
NorRmSmWallFront01     -- Front wall, variant 1
NorRmSmWallFrontExSm01 -- Front wall with small exit
NorRmSmCorIn01         -- Inward corner
NorRmSmCorOut01        -- Outward corner (if exists)
NorRmSmCeil01          -- Ceiling piece
```

### Snap Point System

**Grid-based alignment** is the ONLY reliable method:
- Kit pieces align to a shared grid. "Eyeballing" kit pieces always leaves gaps and seams.
- The grid is the foundation of the entire kit system.
- Level designers work at **half the footprint size** for snap (e.g., 128-unit snap for 256-unit rooms).

**Footprint rules:**
- Sub-kits within a kit MUST have footprints that are **multiples of each other**.
- A 512x512x512 room tiles perfectly with a 256x256x256 hallway.
- A 384x384x384 room WILL eventually create gaps when combined with 256-unit halls.
- Non-uniform XY sizes are strongly discouraged.

**Pivot point placement:**
- Every kit piece's origin/pivot is positioned at a consistent location (typically a corner or center of the footprint).
- This ensures that grid-snapped placement lines up pieces perfectly.

### Helper Markers (Editor-Only)

Helper markers are **non-rendered geometry visible only in the editor** that communicate information to level designers:

| Marker Type | Purpose |
|-------------|---------|
| **Snap markers** | Show how pieces should connect to each other |
| **Doorway outlines** | Walls and doorways outlined with marker geometry for clear layout visibility |
| **Ceiling handles** | Square markers on ceilings so designers can grab one-sided ceiling art without flipping the camera upside-down |
| **Direction indicators** | Show which direction a door opens, differentiate asymmetrical hall sides, indicate tiling direction |
| **Flow markers** | Indicate direction of flow on pieces that must tile in a specific direction |

In practice: walls and doorways are outlined with marker geometry, giving the level designer a clear representation of the level layout, even in top-down or cluttered views.

### Kit Bashing Workflow

1. **Choose a kit** from the Object Window (e.g., NorRmSm for Nordic Small Room)
2. **Set grid snap** to the kit's standard grid (e.g., 128 units, 45-degree angle snap for Nordic)
3. **Place room pieces** starting from an entrance/exit piece
4. **Connect rooms via exits** -- align ExSm to ExSm, ExBg to ExBg
5. **Fill interior details** -- mid pieces, columns, clutter
6. **Add ceiling pieces** using ceiling handle markers
7. **Place helper markers** for QA reference
8. **NavMesh generation** on the bare kit layout
9. **Clutter pass** -- add props, loot, enemies
10. **Lighting pass** -- per-cell lighting setup

**Speed:** An experienced level designer can rough out a complete dungeon layout in a single day using kits. The full dungeon (with clutter, lighting, quests, encounters) takes much longer.

### QA Validation Rules

| Test | What It Checks | How It Works |
|------|---------------|--------------|
| **Loopback Test** | Can the player loop back to the start? | Verify modules loop properly -- connect beginning to end |
| **Stack Test** | Multi-level construction integrity | Floors must have thickness, not be paper-thin. Confirm vertical stacking works |
| **Gap Test** | Gaps in off-angle constructions | Ensure sufficient "glue pieces" exist for non-orthogonal interior connections |
| **Collision Test** | Player entrapment | Verify collision meshes don't trap the player in geometry |
| **Visual Repetition Check** | Art fatigue | Assess how much visual variety exists per kit |

### Production Metrics

| Metric | Details |
|--------|---------|
| Artists per kit | Approximately 2-3 (one lead artist + support) |
| Kit creation time | "Time-consuming" with significant lead time and on-boarding overhead. Estimated weeks to months per complete kit |
| Kit pieces per kit | Varies: simple kits (pipe system) = 4 pieces; complex kits (Nordic) = 50-100+ pieces including all sub-kits |
| Initial kit creator at BGS | Istvan Pely (implemented initial modular approach at BGS in 2005) |
| Key team members | Nathan Purkeypile, Cory Edwards (kit creators from TRI), Robert Wisnewski, Clara Struthers, Rafael Vargas (artists) |

### Art Fatigue Problem

The primary drawback of modular kits is **art fatigue** -- players see the same pieces repeated across hundreds of hours. Bethesda combats this with:
- Multiple variants per piece (01, 02, 03...)
- Clutter and prop variation
- Lighting variation per cell
- Unique set-pieces mixed into modular layouts
- "Kit bashing" -- combining pieces from different sub-kits creatively

---

<a name="mission-2"></a>
## Mission 2: Bethesda Creation Kit Technical Details

### Sources
- Creation Kit Wiki: https://ck.uesp.net/wiki/Bethesda_Tutorial_Layout_Part_1
- Creation Kit Wiki: https://ck.uesp.net/wiki/Bethesda_Tutorial_Layout_Part_2
- Creation Kit Wiki: https://ck.uesp.net/wiki/Room_Bounds_and_Portal_Basics
- Creation Kit Wiki: https://ck.uesp.net/wiki/Bethesda_Tutorial_Optimization
- Confidence: HIGH (official Bethesda documentation)

### Grid System

| Setting | Value | Notes |
|---------|-------|-------|
| Default Snap to Grid | **128 units** | Standard for Nordic Ruin kit |
| Default Snap to Angle | **45 degrees** | Standard rotation snap |
| Available grid sizes | 256, 128, 64, 32, etc. | Any power-of-2 value works |
| Exterior cell size | **4096 x 4096 units** | Each exterior cell |
| Exterior vertex spacing | **128 units** apart | Heightmap grid |
| Working principle | Snap = half the footprint | If room is 256 wide, snap at 128 |

**Critical rules:**
- Grid Size IS the Foundation of your Kit (capitalized emphasis from Burgess)
- Level designers build on a grid snap of **one-half the footprint size**
- If the default snap size is large, the kit is very easy to work with
- Sub-kits don't HAVE to share the same footprint, but footprints MUST be multiples

### Interior Cells vs Exterior Worldspace

| Property | Interior Cell | Exterior Cell |
|----------|--------------|---------------|
| Size | Arbitrary (defined by kit layout) | 4096x4096 units fixed |
| Sky/weather | None (must add manually) | Inherited from worldspace |
| Lighting | Per-cell, manual setup | Dynamic sun + weather |
| LOD | Not needed (enclosed) | Required for distance rendering |
| Cell border | None (single enclosed space) | Loads adjacent cells |
| Creation | Right-click > New in Cell View | Part of worldspace grid |
| Naming | EditorID (e.g., "MyDungeon01") | Coordinates (X,Y) |

### Load Doors and Teleport Markers

**Load doors** are the transition mechanism between cells (interior-to-exterior or interior-to-interior).

#### How They Work:

1. Place a door object (static mesh with door behavior) in both the interior and exterior cells
2. Double-click the door reference in the exterior cell
3. Check the **Teleport** checkbox in the Reference dialog
4. Click "Select Reference in Render Window" and double-click the corresponding interior entrance door
5. The engine creates **yellow teleport markers** at each door
6. Position the teleport marker just outside each door, facing away from it
7. The player transitions between cells when activating the door

#### Teleport Marker Details:

| Property | Description |
|----------|-------------|
| Visual | Yellow arrow-shaped marker (editor only) |
| Position | Just outside the door, player-side |
| Direction | Facing away from the door (direction player faces after loading) |
| NavMesh link | Triangle under the teleport marker turns green after finalization |
| COC marker | Blue Center-Of-Cell marker = default spawn point |

#### NavMesh Finalization:
After placing teleport markers, both cells' navmeshes must be finalized:
- Press **Ctrl+E** then **Ctrl+1** in each cell
- A navmesh triangle under the yellow Teleport Marker turns green
- This enables NPC pathfinding across cell boundaries

### Lighting Per Cell

Interior cells have their own lighting independent of the exterior worldspace:
- Each cell has an **ambient light** setting (base illumination)
- **Point lights** are placed manually around the cell
- **Shadow-casting lights** are expensive; used sparingly
- **Image Space** modifiers control post-processing per cell (contrast, saturation, fog)
- Bethesda typically uses a dark ambient with strategically placed warm torches/fires

### NavMesh Generation in Modular Kits

| Method | Description | Best For |
|--------|-------------|----------|
| **Recast Based** | Automatic generation from geometry | Majority of interiors (recommended) |
| **Object Based** | Uses object collision shapes | Simple layouts |
| **Havok Based** | Uses Havok physics collision | Physics-heavy areas |
| **Advanced** | Manual fine-tuning | Complex areas |

**Kit workflow:**
1. Generate NavMesh on **bare kit layout** first (before clutter) -- generates cleanly on bare kits
2. Clean up manually as needed
3. As clutter objects are added, **cut them out** of the navmesh: Ctrl+Alt+Click on object > "Cut Selected Objects"
4. Exception: Metro kit must be navmeshed entirely by hand

### Collision on Kit Pieces

- Kit pieces use **automatic collision generation** from their mesh geometry
- The engine generates collision hulls from the visible mesh
- Manual collision is used for:
  - Complex pieces where auto-collision creates player traps
  - Invisible barriers at ledges
  - Simplified collision for performance
- **Havok collision** shapes (bhkCollisionObject) are embedded in the NIF model files

### LOD (Level of Detail) for Kit Pieces

- Interior kit pieces generally **do not need LOD** (they're always close to the camera in enclosed spaces)
- Exterior kit pieces (city buildings, ruins visible from distance) use:
  - **Object LOD**: Simplified meshes at distance
  - **Tree LOD**: For vegetation
  - **Terrain LOD**: For landscape
- LOD is generated via the CK's LOD generation tool

### Room Bounds and Portal System (Occlusion Culling)

#### Room Markers (Room Bounds)

- **Room markers** are box-shaped volumes that define a "room" for rendering purposes
- Everything inside a room marker is treated as a group for culling
- When the camera is NOT in a room, all objects in that room are culled (not rendered)
- Room markers should tightly encompass all geometry in a room without overlapping other rooms

#### Portals

- **Portals** are flat rectangular planes that connect two room markers
- Placed at doorways/openings between rooms
- The renderer tests portal visibility against the camera frustum
- If a portal is not visible, the connected room is culled entirely

#### How They Work Together:

```
[Room A] --portal--> [Room B] --portal--> [Room C]

Camera in Room A:
- Room A: RENDERED (camera is here)
- Room B: Test portal A->B against frustum. Visible? RENDER Room B
- Room C: Test portal B->C against frustum via Room B. Not visible? CULL Room C
```

#### Implementation Rules:

| Rule | Description |
|------|-------------|
| No overlap | Room markers must NOT overlap each other |
| No gaps | Room markers must fully contain all geometry |
| Portal placement | Portals go at doorway openings only |
| Portal size | Match the doorway opening size exactly |
| Room size | Smaller rooms = better culling performance |
| Debugging | If objects disappear when walking through areas, room bounds overlap or have gaps |

#### Additional Occlusion Tools:

| Tool | Purpose |
|------|---------|
| **Multibounds** | Group objects for batch culling (used in exteriors) |
| **Occlusion Planes** | Flat surfaces that block rendering of objects behind them |
| **PreVis** (Fallout 4+) | Pre-computed visibility data |
| **PreCombines** (Fallout 4+) | Pre-combined static geometry for performance |

---

<a name="mission-3"></a>
## Mission 3: Fallout 4 Settlement Building System

### Sources
- Nexus Mods tutorials: https://www.nexusmods.com/fallout4/articles/128
- Fallout Wiki: https://fallout.fandom.com/wiki/Structure
- Community modding documentation
- Confidence: MEDIUM-HIGH (community documentation based on reverse engineering + official mod tools)

### Snap System Architecture

Fallout 4's settlement building uses **BSConnectPoint::Parents** -- a NIF file data structure that defines snap points on each buildable piece.

#### BSConnectPoint Data Structure (per NIF file)

Each piece's NIF mesh file contains:

```
BSConnectPoint::Parents
  Num Connect Points: [integer]
  Connect Points: [array]
    [0]:
      Parent: "root"              // Parent bone/node name
      Name: "P-WallTop"          // Variable name (snap category)
      Rotation: [quaternion]      // Orientation of the snap point
      Translation: [x, y, z]     // Position relative to piece origin
      Scale: [float]             // Scale factor (usually 1.0)
    [1]:
      ...
```

#### How Snap Compatibility Works

1. **Variable Name matching**: Two pieces snap together ONLY if they have matching variable names
2. When the player holds a piece near a placed piece, the engine searches for matching connect points within a radius
3. Matching connect points cause the held piece to "snap" into position, aligning the two connect points

#### The Variable Name System

| Variable Name | Category | Connects To |
|---------------|----------|-------------|
| **P-Wall01** | Wall connection | Other P-Wall01 points |
| **P-Balcony01** | Balcony attachment | Balcony rail/platform points |
| **P-Floor** | Floor/foundation | Floor snap points |
| **P-Ceiling** | Ceiling attachment | Ceiling mount points |
| **P-Door** | Door frame | Door snap points |
| **P-Stairs** | Staircase | Stair connection points |
| **P-Fence** | Fence connection | Other fence posts |
| **P-Power** | Power connection | Wire/conduit attachment |
| **P-Pipe** | Pipe connection | Pipe/plumbing attachment |

#### The -Dif Modifier

Adding **"-Dif"** to a variable name prevents a piece from snapping to **itself**:
- `P-Door-Dif` on piece A will snap to `P-Door` on piece B
- But `P-Door-Dif` on piece A will NOT snap to `P-Door-Dif` on piece A (prevents self-snap)
- This ensures doorframes connect to walls, not to other doorframes

#### P-WS-Rotation Variable

The `P-WS-Rotation` variable controls the held piece's orientation relative to the player's crosshair when selected from the build menu. This is a display/UX parameter, not a structural snap parameter.

### Snap Point Configuration via NifSkope

**To add snap points to a custom piece:**

1. Open the NIF file in NifSkope
2. Right-click root node > Node > Insert extra data > **BSConnectPoint::Parents**
3. Set **Num Connect Points** to desired count
4. Right-click "Connect Points" > Array > Update
5. For each connect point:
   - Set **Name** (variable name like "P-Wall01")
   - Set **Translation** (X, Y, Z position relative to origin)
   - Set **Rotation** (quaternion orientation)
   - Set **Scale** (typically 1.0)
6. Save the NIF

### INI Configuration

```ini
[Workshop]
fWorkshopItemConnectPointQueryRadius=128.0000  ; Search radius for snap matches
; Set to 0.0000 to disable snapping entirely
```

### Building Categories (Fallout 4)

| Category | Description | Snap Behavior |
|----------|-------------|---------------|
| **Wood Structures** | Flat-panel objects, stairs, ladders, railings | Full snap between wood pieces |
| **Metal Structures** | Curved/cylindrical pieces, less flexible | Snap within metal set |
| **Concrete** | Heavy foundations and walls | Snap with concrete pieces |
| **Fences** | Interlock within groups (junk fence = standalone) | Fence-to-fence only |
| **Vault-Tec** | Halls, rooms, windows, railings, bridges | Full vault-to-vault snap |
| **Barn** (Far Harbor) | Barn-style structures | Snap within barn set |
| **Warehouse** (Wasteland Workshop) | Industrial structures | Snap within warehouse set |

**Cross-compatibility limitation:** Structures from different DLCs generally cannot snap together.

### Validation System (Green/Red Placement)

| Color | Meaning |
|-------|---------|
| **Green** | Valid placement -- piece will be placed |
| **Yellow** | Snapped position -- locked to a snap point |
| **Red** | Invalid placement -- blocked by collision, terrain, or budget |

**Validation checks:**
- Collision overlap with existing pieces
- Terrain penetration (partial allowed, full block)
- Build budget remaining
- Line of sight from player
- Settlement boundary

### Power/Wire Connection System

Power connections use a **separate snap point category**:

| Component | Snap Type |
|-----------|-----------|
| Generators | P-Power output |
| Conduits | P-Power in + P-Power out |
| Switches | P-Power through |
| Lights | P-Power input |
| Wire attachment | Player manually connects with wire tool |

Wires are physics-based (sag with length) and have a maximum length. Conduits pass power through walls.

---

<a name="mission-4"></a>
## Mission 4: Starfield Procedural POIs

### Sources
- Steam Community Guide: https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
- Nexus Forums: https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/
- StarfieldDB: https://www.starfielddb.com/creation-engine-2/
- Confidence: MEDIUM (community documentation + limited official info)

### Outpost Hab Kit System

Starfield uses named kit prefixes, similar to Skyrim but for sci-fi architecture:

| Kit Prefix | Full Name | Visual Style | Shape Variants |
|------------|-----------|-------------|----------------|
| **Opi** | Outpost Industrial | Green habs | Rectangular, Hexagonal (large/small) |
| **Ops** | Outpost Science | White habs | Rectangular WallA (sloping), WallB (right-angle), Round |
| **Oph** | Outpost Hydroponic | Glass habs | Rectangular, Round |
| **Opm** | Outpost Military | Tactical | Rectangular only (directional constraints) |
| **Opc** | Outpost Colony | Residential | Rectangular in two variants |

Additional kits:
- **Science Hull Kit** -- research station interiors
- **Akila Kit** -- Wild West/frontier architecture
- **New Atlantis Kit** -- Sleek modern architecture
- **Neon Kit** -- Cyberpunk/neon-lit architecture
- **Starborn Temple Kit** -- Alien/ancient architecture

### Grid and Snap System (Starfield)

| Property | Value |
|----------|-------|
| Base unit | Standard CK unit (inherited from Skyrim's system) |
| Hab layout grid | **4x4 grid** for standard small square habs |
| Piece sizes | 1x1 (corners), 2x1 (walls/exits/windows), 2x2 (smallest mid-sections) |
| Pivot point location | **Center of a 4x4 grid**, NOT center of the object |
| Interior partitions | Fit at **whole and 0.5 fractions** of X/Y grid positions |
| Snap to Grid toggle | Constrains placement to whole-number grid positions |
| Height | Most objects are 1 unit high |

### Procedural vs Hand-Placed Content

| Content Type | Generation Method |
|-------------|-------------------|
| Named cities (New Atlantis, Akila, Neon) | **100% hand-crafted** |
| Story quest locations | **Hand-crafted** |
| Named locations with NPCs | **Partially or fully hand-crafted** |
| Planet surface POIs | **Procedurally placed from templates** |
| Abandoned facilities | **Kit-assembled templates, procedurally placed** |
| Geological features | **Procedurally generated** |
| Flora/fauna distribution | **Procedurally distributed** |

### Planet Content Manager (PCM)

A new system in Starfield (not present in Skyrim/Fallout 4):
- Controls procedural content placement on planets and in space cells
- Similar to but distinct from Story Manager
- Determines which POI templates can appear on which biomes
- Controls density and spacing of procedural content

### Unique vs Instanced Content

| Type | Description | Example |
|------|-------------|---------|
| **Unique** | Static, single-use locations | A specific building interior on one planet |
| **Instanced** | Generated at runtime, reusable | Starborn Temples appearing on multiple planets |

### Improvements Over Skyrim/Fallout 4

The documentation states: "Many of the features, concepts, fundamental methods and tools carry over to the Starfield CK or exist in an updated or enhanced form." Specific confirmed improvements:

1. **Galaxy View** -- New data management tool for stellar bodies
2. **Planet Content Manager** -- Procedural content distribution system
3. **Terrain Cutting** -- New landscape block selection system
4. **Instanced content** -- Runtime-generated reusable locations
5. **VSCode integration** -- For Papyrus scripting
6. **3DSMax integration** -- For 3D asset pipeline

### Handling Repetition

The biggest challenge: same kit pieces appear across many planets. Mitigation strategies:
- Environmental context variation (different terrain, lighting, weather)
- Biome-specific material swaps
- Loot/enemy variation per POI instance
- Layout variation within the same kit
- Mix of procedural and unique POIs

---

<a name="mission-5"></a>
## Mission 5: CGA Split Grammar Deep Dive

### Sources
- Muller, Wonka, Haegler, Ulmer, Van Gool. "Procedural Modeling of Buildings." SIGGRAPH 2006
  - https://history.siggraph.org/learning/procedural-modeling-of-buildings-by-muller-wonka-haegler-ulmer-and-gool/
- ArcGIS CityEngine CGA Reference: https://doc.arcgis.com/en/cityengine/2019.0/cga/cityengine-cga-introduction.htm
- CityEngine Tutorials 6 & 9: https://doc.arcgis.com/en/cityengine/latest/tutorials/tutorial-6-basic-shape-grammar.htm
- Penn State GEOG 497: https://www.e-education.psu.edu/geogvr/node/891
- Confidence: HIGH (primary academic source + official CityEngine docs)

### CGA Rule Syntax

```
Predecessor --> Successor
```

- **Predecessor**: Symbolic name of the shape to be replaced
- **Successor**: Shape operations + symbolic names for output shapes
- Rules fire when a shape with a matching predecessor name exists in the shape tree

#### Example:
```
Lot --> extrude(10) Building
Building --> comp(f) { front: FrontFacade | side: SideFacade | top: Roof }
FrontFacade --> split(y) { 4: Groundfloor | { ~3.5: Floor }* }
Floor --> split(x) { 0.5: Wall | { ~3: Tile }* | 0.5: Wall }
Tile --> split(y) { 0.4: Wall | ~1.5: Window | 0.4: Wall }
```

### Complete CGA Operations Reference

#### Geometry Creation

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **extrude** | `extrude(height)` | Extends 2D shape vertically into 3D |
| **envelope** | `envelope(...)` | Creates building envelope |
| **i** (insert) | `i("asset.obj")` | Inserts an external 3D asset |
| **insertAlongUV** | `insertAlongUV(...)` | Insert along UV coordinates |
| **roofGable** | `roofGable(angle)` | Creates gable roof |
| **roofHip** | `roofHip(angle)` | Creates hip roof |
| **roofPyramid** | `roofPyramid(angle)` | Creates pyramid roof |
| **roofShed** | `roofShed(angle)` | Creates shed roof |
| **taper** | `taper(height, fraction)` | Tapers shape upward |
| **primitiveCube** | `primitiveCube()` | Inserts cube primitive |
| **primitiveCylinder** | `primitiveCylinder(...)` | Inserts cylinder |
| **primitiveSphere** | `primitiveSphere()` | Inserts sphere |
| **primitiveDisk** | `primitiveDisk()` | Inserts disk |
| **primitiveCone** | `primitiveCone()` | Inserts cone |
| **primitiveQuad** | `primitiveQuad()` | Inserts quad |

#### Geometry Subdivision (THE CORE OPERATIONS)

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **split** | `split(axis) { sizes : shapes }` | Divides shape along axis (x, y, or z) |
| **comp** | `comp(f) { selectors : shapes }` | Component split -- separates faces |
| **offset** | `offset(distance, inside)` | Insets shape boundary |
| **scatter** | `scatter(surface, n, ...)` | Distributes points on surface |
| **setback** | `setback(dist) { ... }` | Steps back edges |
| **setbackPerEdge** | `setbackPerEdge(dist) { ... }` | Per-edge step back |
| **setbackToArea** | `setbackToArea(area) { ... }` | Steps back to target area |
| **shapeL** | `shapeL(w1,d1,w2,d2)` | Creates L-shape |
| **shapeO** | `shapeO(w,d)` | Creates O-shape (courtyard) |
| **shapeU** | `shapeU(w1,d1,w2)` | Creates U-shape |
| **splitArea** | `splitArea(axis) { ... }` | Area-based split |

#### Transformations

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **s** | `s(x, y, z)` | Set scope size. `'1` = relative |
| **t** | `t(x, y, z)` | Translate scope |
| **r** | `r(x, y, z)` | Rotate scope |
| **translate** | `translate(rel, coord, x, y, z)` | Absolute translate |
| **rotate** | `rotate(rel, coord, angle)` | Absolute rotate |
| **center** | `center(axis)` | Center on axis |

#### Texturing

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **texture** | `texture("file.jpg")` | Apply texture |
| **setupProjection** | `setupProjection(channel, plane, w, h, ...)` | Setup UV projection |
| **projectUV** | `projectUV(channel)` | Apply UV projection |
| **tileUV** | `tileUV(channel, u, v)` | Tile UVs |
| **rotateUV** | `rotateUV(channel, angle)` | Rotate UVs |
| **scaleUV** | `scaleUV(channel, su, sv)` | Scale UVs |
| **translateUV** | `translateUV(channel, tu, tv)` | Translate UVs |
| **normalizeUV** | `normalizeUV(channel)` | Normalize UVs |
| **deleteUV** | `deleteUV(channel)` | Delete UVs |

#### Flow Control and Attributes

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **color** | `color(r, g, b)` | Set shape color |
| **set** | `set(attr, value)` | Set material attribute |
| **NIL** | `NIL` | Discard shape (no output) |
| **print** | `print("msg")` | Debug output |
| **report** | `report("key", value)` | Report statistics |
| **push** / **pop** | `push. / pop.` | Save/restore scope state |

#### Geometry Manipulation

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **cleanupGeometry** | `cleanupGeometry(...)` | Remove degenerate faces |
| **convexify** | `convexify()` | Make convex |
| **mirror** | `mirror(axis)` | Mirror shape |
| **reduceGeometry** | `reduceGeometry(percent)` | Simplify mesh |
| **reverseNormals** | `reverseNormals()` | Flip normals |
| **trim** | `trim()` | Trim to scope |

#### Scope Management

| Operation | Syntax | Description |
|-----------|--------|-------------|
| **alignScopeToAxes** | `alignScopeToAxes()` | Align scope to world |
| **alignScopeToGeometry** | `alignScopeToGeometry(...)` | Align to geo |
| **setPivot** | `setPivot(x,y,z)` | Set pivot point |
| **rotateScope** | `rotateScope(x,y,z)` | Rotate the scope |
| **mirrorScope** | `mirrorScope(axis)` | Mirror the scope |

### The Split Operation in Detail

```
split(axis) { size1 : Shape1 | size2 : Shape2 | ... }
```

**Axis**: `x` (width), `y` (height), `z` (depth)

**Size specifiers:**

| Prefix | Meaning | Example |
|--------|---------|---------|
| (none) | Absolute size in meters | `4` = exactly 4 meters |
| `~` | Floating/proportional size | `~3.5` = approximately 3.5m, adjusts to fill |
| `'` | Relative to scope | `'0.5` = half of parent scope |

**Repeat operator `*`**: Repeats the preceding pattern to fill available space.

```
split(y) { 4: Groundfloor | { ~3.5: Floor }* }
```
This creates a 4m ground floor, then repeats ~3.5m floors until the building height is filled. The `~` ensures a whole number of floors always fits.

### The Component Split (comp) in Detail

```
comp(f) { selector : Shape | ... }
```

Separates a 3D shape into its constituent faces:

| Selector | Meaning |
|----------|---------|
| `front` | Front-facing facade |
| `back` | Back facade |
| `left` | Left side |
| `right` | Right side |
| `top` | Top face (roof base) |
| `bottom` | Bottom face |
| `side` | All side faces |
| `all` | All faces |

### Recursive Building Decomposition (Complete Hierarchy)

```
Lot (2D footprint polygon)
  |
  +-- extrude(height) --> Building (3D mass model)
       |
       +-- comp(f) --> FrontFacade, SideFacade, BackFacade, Roof
            |
            +-- [FrontFacade] split(y) --> Groundfloor, Floor, Floor, Floor...
                 |
                 +-- [Floor] split(x) --> Wall, Tile, Tile, Tile..., Wall
                      |
                      +-- [Tile] split(y) --> Wall, WindowArea, Wall
                           |
                           +-- [WindowArea] split(x) --> Frame, Glass, Frame
                                |
                                +-- [Glass] --> color, reflectivity, texture
                                +-- [Frame] --> extrude depth, texture
```

**In words:**
1. **Lot** (2D polygon) --> **extrude** to building mass
2. **Building mass** --> **component split** into facades + roof
3. **Facade** --> **vertical split** into ground floor + repeating upper floors
4. **Floor** --> **horizontal split** into wall borders + repeating tiles
5. **Tile** --> **vertical split** into wall strips + window opening
6. **Window** --> **horizontal split** into frame elements + glass pane
7. **Elements** --> depth extrusion, texturing, coloring

### How Windows, Doors, and Decorative Elements Are Placed

```cga
// Ground floor gets doors, upper floors get windows
Floor(floorIndex) -->
    case floorIndex == 0:
        split(x) { ~4: GroundTile }*
    else:
        split(x) { ~3: UpperTile }*

GroundTile -->
    split(x) { 0.5: Wall | ~2: split(y) {
        0.3: Wall | ~2.5: Door | 0.3: Wall
    } | 0.5: Wall }

UpperTile -->
    split(x) { 0.5: Wall | ~1.5: split(y) {
        0.4: Wall | ~1.5: Window | 0.4: Wall
    } | 0.5: Wall }

Window -->
    t(0, 0, -0.2)           // Recess into wall
    split(y) {
        0.1: Frame |
        ~1: split(x) {
            0.1: Frame | { ~1: Glass | 0.1: Frame }*
        } |
        0.1: Frame
    }

Door -->
    t(0, 0, -0.15)
    i("door_asset.obj")      // Insert door model
```

### How Facades Handle Corner Conditions

Corners are handled through the **component split** and **border framing**:

```cga
// The wall splits create border frames that handle corners
Floor --> split(x) {
    borderwallW: Wall |     // Left border (covers corner)
    ~1: FloorContent |      // Middle content (tiles)
    borderwallW: Wall       // Right border (covers corner)
}
```

For L-shaped buildings, CGA provides:
- `shapeL(w1, d1, w2, d2)` -- Creates L-shaped footprint
- `shapeU(w1, d1, w2)` -- Creates U-shaped footprint
- `shapeO(w, d)` -- Creates O-shaped (courtyard) footprint
- The component split then correctly identifies front/side/back for each wing

**Context-sensitive rules** prevent problems:
- Windows/doors don't intersect with other walls
- Doors only appear at ground level or terraces
- Terraces get railings automatically
- Occlusion queries prevent overlapping elements

### Advanced CGA Features

| Feature | Description |
|---------|-------------|
| **Parameter passing** | `Floor(floorIndex)` -- index-based variation |
| **Conditional rules** | `case floorIndex == 0:` for ground floor vs upper |
| **Stochastic rules** | Random selection between alternatives |
| **Style keyword** | Apply color/material themes across rules |
| **Nested repeat splits** | `{ ~tileW*n : DoubleTile }*` for complex patterns |
| **Modulo operations** | `tileIndex%2 + floorIndex%2 == 1` for checkerboard |
| **Occlusion queries** | `inside()` / `overlaps()` for collision detection |
| **Snap lines** | Alignment guides for consistent element placement |

### Open Source CGA Implementations

| Project | Language | Platform | URL |
|---------|----------|----------|-----|
| **Prokitektura** | Python | Blender addon | https://github.com/nortikin/prokitektura-blender |
| **BCGA** | Python | Blender addon | https://github.com/vvoovv/bcga |
| **ShapeML** | C++ | Standalone (GPL3) | https://github.com/stefalie/shapeml |
| **CGA_interpreter** | C++ | Standalone | https://github.com/pvallet/CGA_interpreter |
| **cga-shape** | (simplified) | Implementation | https://github.com/LudwikJaniuk/cga-shape |

#### Prokitektura (Python/Blender) Workflow:

1. Start with 2D building outlines
2. Extrude to desired height
3. Decompose into vertical rectangles (facades) and roof base
4. Cut floors into each facade
5. Subdivide floors into window sections
6. Further refine sections iteratively
7. Parameters exposed in Blender panel for real-time updates

### Implementing CGA-Style Grammar in Python

```python
# Simplified CGA-style grammar engine for Blender

class Shape:
    """Represents a 3D scope (bounding box + geometry)"""
    def __init__(self, name, position, size, geometry=None):
        self.name = name
        self.position = position  # (x, y, z)
        self.size = size          # (width, height, depth)
        self.geometry = geometry
        self.children = []

class Rule:
    """A CGA-style production rule"""
    def __init__(self, predecessor, successor_fn, condition=None):
        self.predecessor = predecessor
        self.successor_fn = successor_fn
        self.condition = condition  # Optional guard

class Grammar:
    """CGA grammar engine"""
    def __init__(self):
        self.rules = {}

    def add_rule(self, name, successor_fn, condition=None):
        if name not in self.rules:
            self.rules[name] = []
        self.rules[name].append(Rule(name, successor_fn, condition))

    def derive(self, shape, max_depth=10):
        """Recursively apply rules to shape tree"""
        if max_depth <= 0 or shape.name not in self.rules:
            return shape

        for rule in self.rules[shape.name]:
            if rule.condition is None or rule.condition(shape):
                children = rule.successor_fn(shape)
                shape.children = children
                for child in children:
                    self.derive(child, max_depth - 1)
                break
        return shape

# Split operation
def split(shape, axis, sizes_and_names):
    """
    Split a shape along an axis.
    axis: 0=x, 1=y, 2=z
    sizes_and_names: [(size, name), ...] where size can be:
      - float: absolute size
      - ('~', float): floating size
      - ('*', float, name): repeat
    """
    children = []
    pos = list(shape.position)
    remaining = shape.size[axis]

    # Calculate absolute sizes
    absolute_total = sum(s for s, _ in sizes_and_names if isinstance(s, (int, float)))
    floating_total = remaining - absolute_total
    floating_count = sum(1 for s, _ in sizes_and_names if isinstance(s, tuple) and s[0] == '~')

    for size_spec, name in sizes_and_names:
        if isinstance(size_spec, (int, float)):
            actual_size = size_spec
        elif isinstance(size_spec, tuple) and size_spec[0] == '~':
            actual_size = floating_total / max(floating_count, 1)

        child_size = list(shape.size)
        child_size[axis] = actual_size
        child_pos = list(pos)

        children.append(Shape(name, tuple(child_pos), tuple(child_size)))
        pos[axis] += actual_size

    return children

# Component split
def comp(shape, face_rules):
    """
    Component split: separate shape into faces.
    face_rules: {'front': name, 'side': name, 'top': name, ...}
    """
    children = []
    x, y, z = shape.position
    w, h, d = shape.size

    face_map = {
        'front': (x, y, z+d, w, h, 0),
        'back':  (x, y, z,   w, h, 0),
        'left':  (x, y, z,   0, h, d),
        'right': (x+w, y, z, 0, h, d),
        'top':   (x, y+h, z, w, 0, d),
        'bottom':(x, y, z,   w, 0, d),
    }

    for face_name, rule_name in face_rules.items():
        if face_name in face_map:
            fx, fy, fz, fw, fh, fd = face_map[face_name]
            children.append(Shape(rule_name, (fx, fy, fz), (fw, fh, fd)))

    return children
```

---

<a name="mission-6"></a>
## Mission 6: Snap Connector Implementation in Python/Blender

### Sources
- Inu Games Modular Snap System: https://inu-games.com/2018/08/30/modular-snap-system-plugin-for-ue4/
- Snappable Meshes PCG: https://github.com/VideojogosLusofona/snappable-meshes-pcg
- Blender Python API: https://docs.blender.org/api/current/
- Confidence: HIGH (well-documented systems + Blender API is stable)

### Snap Point Data Structure

```python
from dataclasses import dataclass, field
from typing import Optional
from mathutils import Vector, Quaternion
import math

@dataclass
class SnapPoint:
    """A connection point on a modular kit piece."""

    # Core identity
    name: str              # Category name (e.g., "Wall", "Floor", "ExSm")
    piece_id: str          # ID of the piece this snap point belongs to

    # Spatial properties
    position: Vector       # Local position relative to piece origin
    normal: Vector         # Outward-facing direction (the "forward" vector)
    up: Vector             # Up direction for orientation alignment

    # Connection rules
    type: str              # Snap type category (e.g., "wall", "floor", "exit_sm")
    polarity: str = "neutral"  # "positive", "negative", or "neutral"
    tags: set = field(default_factory=set)  # Additional compatibility tags

    # Metadata
    occupied: bool = False  # Whether this snap point is already connected
    connected_to: Optional['SnapPoint'] = None  # Reference to connected point

    @property
    def world_position(self) -> Vector:
        """Get world position given the piece's transform."""
        # Must be computed from piece's world matrix
        raise NotImplementedError("Call with piece transform")

    def is_compatible(self, other: 'SnapPoint', max_angle: float = 75.0) -> bool:
        """Check if this snap point can connect to another."""
        # 1. Type must match
        if self.type != other.type:
            return False

        # 2. Neither can be occupied
        if self.occupied or other.occupied:
            return False

        # 3. Polarity check
        if not self._polarity_compatible(other):
            return False

        # 4. Normals must be roughly opposing (face each other)
        dot = self.normal.dot(other.normal)
        angle = math.degrees(math.acos(max(-1, min(1, -dot))))
        if angle > max_angle:
            return False

        return True

    def _polarity_compatible(self, other: 'SnapPoint') -> bool:
        """Check polarity compatibility."""
        if self.polarity == "neutral" or other.polarity == "neutral":
            return True  # Neutral matches anything
        if self.polarity == other.polarity:
            return False  # Same polarity = no match (prevents self-snap)
        return True  # Opposite polarity = match


@dataclass
class KitPiece:
    """A modular kit piece with snap points."""

    id: str
    name: str
    mesh_name: str         # Blender mesh object name
    category: str          # e.g., "NorRmSm", "NorHallBg"
    snap_points: list = field(default_factory=list)

    # Transform
    position: Vector = field(default_factory=lambda: Vector((0, 0, 0)))
    rotation: Quaternion = field(default_factory=lambda: Quaternion())

    def add_snap_point(self, snap: SnapPoint):
        self.snap_points.append(snap)

    def get_compatible_points(self, other_piece: 'KitPiece',
                               max_distance: float = 1.0,
                               max_angle: float = 75.0) -> list:
        """Find all compatible snap point pairs between two pieces."""
        pairs = []
        for sp_self in self.snap_points:
            for sp_other in other_piece.snap_points:
                if sp_self.is_compatible(sp_other, max_angle):
                    # Check distance in world space
                    world_a = self._to_world(sp_self.position)
                    world_b = other_piece._to_world(sp_other.position)
                    dist = (world_a - world_b).length
                    if dist < max_distance:
                        pairs.append((sp_self, sp_other, dist))
        # Sort by distance (closest first)
        pairs.sort(key=lambda p: p[2])
        return pairs

    def _to_world(self, local_pos: Vector) -> Vector:
        """Transform local position to world space."""
        return self.position + self.rotation @ local_pos
```

### Detecting Compatible Connections

```python
class SnapSystem:
    """Manages snap connections between kit pieces."""

    def __init__(self, search_radius: float = 256.0, max_angle: float = 75.0):
        self.search_radius = search_radius
        self.max_angle = max_angle
        self.pieces: list[KitPiece] = []
        self.connections: list[tuple[SnapPoint, SnapPoint]] = []

    def find_best_snap(self, moving_piece: KitPiece) -> Optional[tuple]:
        """
        Find the best snap connection for a piece being placed.
        Returns (snap_a, snap_b, transform) or None.
        """
        best = None
        best_dist = float('inf')

        for placed_piece in self.pieces:
            for sp_moving in moving_piece.snap_points:
                if sp_moving.occupied:
                    continue
                for sp_placed in placed_piece.snap_points:
                    if sp_placed.occupied:
                        continue
                    if not sp_moving.is_compatible(sp_placed, self.max_angle):
                        continue

                    # Calculate where moving piece needs to go
                    transform = self._calculate_snap_transform(
                        moving_piece, sp_moving,
                        placed_piece, sp_placed
                    )

                    # Check distance after alignment
                    world_moving = transform['position'] + transform['rotation'] @ sp_moving.position
                    world_placed = placed_piece._to_world(sp_placed.position)
                    dist = (world_moving - world_placed).length

                    if dist < self.search_radius and dist < best_dist:
                        best_dist = dist
                        best = (sp_moving, sp_placed, transform)

        return best

    def _calculate_snap_transform(self, piece_a, snap_a, piece_b, snap_b):
        """
        Calculate the transform to align piece_a's snap_a
        with piece_b's snap_b (opposing normals, coincident positions).
        """
        # Target: snap_a.world_normal = -snap_b.world_normal
        # Target: snap_a.world_position = snap_b.world_position

        # 1. Calculate rotation to oppose normals
        world_normal_b = piece_b.rotation @ snap_b.normal
        target_normal_a = -world_normal_b  # Must face opposite

        local_normal_a = snap_a.normal
        rotation_fix = local_normal_a.rotation_difference(
            piece_a.rotation.inverted() @ target_normal_a
        )
        new_rotation = piece_a.rotation @ rotation_fix

        # 2. Calculate position to align snap points
        world_snap_b = piece_b._to_world(snap_b.position)
        offset = new_rotation @ snap_a.position
        new_position = world_snap_b - offset

        return {
            'position': new_position,
            'rotation': new_rotation
        }

    def connect(self, snap_a: SnapPoint, snap_b: SnapPoint):
        """Register a connection between two snap points."""
        snap_a.occupied = True
        snap_b.occupied = True
        snap_a.connected_to = snap_b
        snap_b.connected_to = snap_a
        self.connections.append((snap_a, snap_b))

    def validate_assembly(self) -> dict:
        """
        Validate a completed assembly for structural integrity.
        Returns validation report.
        """
        report = {
            'valid': True,
            'gaps': [],
            'overlaps': [],
            'unconnected': [],
            'structural_issues': []
        }

        # 1. Find unconnected snap points (potential gaps)
        for piece in self.pieces:
            for sp in piece.snap_points:
                if not sp.occupied:
                    report['unconnected'].append({
                        'piece': piece.id,
                        'snap_point': sp.name,
                        'position': piece._to_world(sp.position)
                    })

        # 2. Check for overlapping pieces (AABB test)
        for i, piece_a in enumerate(self.pieces):
            for piece_b in self.pieces[i+1:]:
                if self._pieces_overlap(piece_a, piece_b):
                    report['overlaps'].append((piece_a.id, piece_b.id))
                    report['valid'] = False

        # 3. Gap detection: check if open snap points form enclosed space
        open_exits = [sp for piece in self.pieces
                      for sp in piece.snap_points
                      if not sp.occupied and 'exit' in sp.type.lower()]
        if open_exits:
            report['gaps'] = [{
                'snap_point': sp.name,
                'position': str(sp.position)
            } for sp in open_exits]

        # 4. Connectivity: all pieces must be reachable
        if self.pieces:
            visited = set()
            self._flood_fill(self.pieces[0], visited)
            if len(visited) < len(self.pieces):
                report['structural_issues'].append(
                    f"Disconnected pieces: {len(self.pieces) - len(visited)} unreachable"
                )
                report['valid'] = False

        return report

    def _pieces_overlap(self, a: KitPiece, b: KitPiece) -> bool:
        """Simple AABB overlap test."""
        # Implementation depends on bounding box data
        return False  # Placeholder

    def _flood_fill(self, piece: KitPiece, visited: set):
        """Traverse connected pieces via snap connections."""
        if piece.id in visited:
            return
        visited.add(piece.id)
        for sp in piece.snap_points:
            if sp.connected_to:
                # Find the piece that owns the connected snap point
                for other in self.pieces:
                    if sp.connected_to in other.snap_points:
                        self._flood_fill(other, visited)
```

### Storing Snap Points in Blender Custom Properties

```python
import bpy
import json

def add_snap_points_to_object(obj, snap_points: list[dict]):
    """
    Store snap point data as custom properties on a Blender object.

    Each snap point dict:
    {
        "name": "ExSm",
        "type": "exit_small",
        "polarity": "positive",
        "position": [x, y, z],
        "normal": [nx, ny, nz],
        "up": [ux, uy, uz],
        "tags": ["nordic", "room"]
    }
    """
    # Store as JSON string in custom property
    obj["snap_points"] = json.dumps(snap_points)
    obj["snap_point_count"] = len(snap_points)

    # Also create empty objects as visual markers (editor-only, like Bethesda helpers)
    for i, sp in enumerate(snap_points):
        marker = bpy.data.objects.new(f"SNAP_{obj.name}_{sp['name']}_{i}", None)
        marker.empty_display_type = 'SINGLE_ARROW'
        marker.empty_display_size = 0.5
        marker.location = sp['position']

        # Orient arrow along normal direction
        from mathutils import Vector
        normal = Vector(sp['normal'])
        up = Vector(sp.get('up', [0, 0, 1]))
        # Create rotation from default (Z-up) to normal direction
        marker.rotation_mode = 'QUATERNION'
        marker.rotation_quaternion = normal.to_track_quat('Z', 'Y')

        # Parent to the kit piece
        marker.parent = obj

        # Mark as non-renderable (helper only)
        marker.hide_render = True

        # Store snap metadata on the marker
        marker["snap_name"] = sp['name']
        marker["snap_type"] = sp['type']
        marker["snap_polarity"] = sp.get('polarity', 'neutral')
        marker["snap_tags"] = json.dumps(sp.get('tags', []))

        # Add to scene
        bpy.context.scene.collection.objects.link(marker)


def read_snap_points_from_object(obj) -> list[dict]:
    """Read snap points from object custom properties."""
    if "snap_points" not in obj:
        return []
    return json.loads(obj["snap_points"])


def snap_piece_to_piece(moving_obj, target_obj,
                         moving_snap_idx: int, target_snap_idx: int):
    """
    Snap moving_obj to target_obj by aligning specified snap points.
    The snap points face each other (opposing normals) at the same position.
    """
    from mathutils import Vector, Matrix

    moving_snaps = read_snap_points_from_object(moving_obj)
    target_snaps = read_snap_points_from_object(target_obj)

    if not moving_snaps or not target_snaps:
        return False

    ms = moving_snaps[moving_snap_idx]
    ts = target_snaps[target_snap_idx]

    # Target world position of the connection
    target_world = target_obj.matrix_world @ Vector(ts['position'])

    # Target normal in world space (the snap point we're connecting TO)
    target_normal = (target_obj.matrix_world.to_3x3() @ Vector(ts['normal'])).normalized()

    # Moving piece's snap normal in local space
    moving_normal_local = Vector(ms['normal']).normalized()
    moving_pos_local = Vector(ms['position'])

    # We need moving_normal_world = -target_normal (opposing)
    # Calculate rotation needed
    desired_normal = -target_normal

    # Current world normal of the moving snap
    current_normal = (moving_obj.matrix_world.to_3x3() @ moving_normal_local).normalized()

    # Rotation from current to desired
    rot = current_normal.rotation_difference(desired_normal)

    # Apply rotation to moving object
    moving_obj.rotation_mode = 'QUATERNION'
    moving_obj.rotation_quaternion = rot @ moving_obj.rotation_quaternion

    # Now calculate position so snap points coincide
    # After rotation, where is the moving snap point in world space?
    new_world_matrix = moving_obj.matrix_world
    new_snap_world = new_world_matrix @ moving_pos_local

    # Offset to align
    offset = target_world - new_snap_world
    moving_obj.location += offset

    return True
```

### Using Vertex Groups as Snap Point Markers (Alternative Approach)

```python
def create_snap_vertex_groups(obj, snap_points: list[dict]):
    """
    Create vertex groups at snap point locations.
    Each vertex group = one snap point.
    Useful for visual editing in Blender.
    """
    import bmesh

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    for sp in snap_points:
        # Create vertex group
        group_name = f"SNAP_{sp['name']}_{sp['type']}"
        vg = obj.vertex_groups.new(name=group_name)

        # Find nearest vertex to snap position
        from mathutils import Vector
        snap_pos = Vector(sp['position'])
        nearest_vert = min(bm.verts, key=lambda v: (v.co - snap_pos).length)

        # Add vertex to group
        vg.add([nearest_vert.index], 1.0, 'REPLACE')

    bm.free()
```

### Assembly Validation Algorithm

```python
def validate_dungeon_assembly(pieces: list, connections: list) -> dict:
    """
    Validate a modular dungeon assembly.
    Implements Bethesda's QA tests programmatically.
    """
    report = {
        'loopback_test': None,   # Can player return to start?
        'stack_test': None,      # Multi-level integrity
        'gap_test': None,        # No unwanted gaps
        'collision_test': None,  # No player traps
        'connectivity': None,    # All pieces reachable
    }

    # 1. LOOPBACK TEST
    # Build graph of connected pieces
    graph = {}
    for piece in pieces:
        graph[piece.id] = set()
    for conn_a, conn_b in connections:
        piece_a = conn_a.piece_id
        piece_b = conn_b.piece_id
        graph[piece_a].add(piece_b)
        graph[piece_b].add(piece_a)

    # Check for cycles (loops) using DFS
    def has_cycle(graph, start):
        visited = set()
        stack = [(start, None)]
        while stack:
            node, parent = stack.pop()
            if node in visited:
                return True  # Cycle found
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor != parent:
                    stack.append((neighbor, node))
        return False

    report['loopback_test'] = has_cycle(graph, pieces[0].id) if pieces else False

    # 2. STACK TEST
    # Check all pieces have non-zero height floors
    for piece in pieces:
        if hasattr(piece, 'floor_thickness'):
            if piece.floor_thickness < 0.01:
                report['stack_test'] = False
                break
    else:
        report['stack_test'] = True

    # 3. GAP TEST
    # Count unconnected snap points (excluding intentional openings)
    unconnected = []
    for piece in pieces:
        for sp in piece.snap_points:
            if not sp.occupied and 'exit' in sp.type:
                unconnected.append(sp)
    report['gap_test'] = len(unconnected) == 0

    # 4. CONNECTIVITY TEST
    # All pieces reachable from the first piece
    visited = set()
    stack = [pieces[0].id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(graph.get(current, []))
    report['connectivity'] = len(visited) == len(pieces)

    return report
```

---

## Cross-Reference: Bethesda Kit System vs CGA Grammar

| Aspect | Bethesda Kit System | CGA Grammar | Best For VeilBreakers |
|--------|-------------------|-------------|----------------------|
| **Approach** | Pre-built mesh pieces snapped together | Procedural rules generating geometry | Hybrid: CGA for building shells, kits for interiors |
| **Granularity** | Room-scale pieces | Element-scale (windows, doors) | Kit system for dungeon rooms, CGA for building facades |
| **Connection** | Grid snap + exit matching | Rule-based subdivision | Snap points for modular connections |
| **Variation** | Variant numbers (01, 02) | Stochastic rules + parameters | Both: variants for hand-placed, stochastic for procedural |
| **Performance** | Pre-baked geometry | Generated at build time | Pre-generate with CGA, place with snap system |
| **Authoring** | Artist-created pieces | Rule-authored | Artists create kit pieces, rules compose them |

### Recommended Hybrid Architecture for VeilBreakers

```
1. CGA Grammar Layer (building shells)
   - Generates building mass models from footprints
   - Splits into floors, facades, roofs
   - Outputs facade panels as placement zones

2. Kit System Layer (modular interiors)
   - Pre-made room/hall/corridor pieces
   - Snap-point based connections
   - Exit system for room-to-room transitions

3. Detail Layer (props and clutter)
   - Scatter-based prop placement
   - Rule-based clutter distribution
   - Lighting templates per room type
```

---

## Summary of Key Numbers

| Metric | Value | Source |
|--------|-------|-------|
| Skyrim dungeon count | 300+ | GDC 2013 |
| Skyrim POI count | 140+ | GDC 2013 |
| Dungeon team | 10 of 90 | GDC 2013 |
| Nordic default grid | 128 units | CK Wiki |
| Nordic angle snap | 45 degrees | CK Wiki |
| Exterior cell size | 4096x4096 units | CK Wiki |
| Exterior vertex spacing | 128 units | CK Wiki |
| Footprint rule | Must be multiples | GDC 2013 |
| Snap radius (FO4) | fWorkshopItemConnectPointQueryRadius | FO4 INI |
| Snap angle tolerance | ~75 degrees (typical) | Modular Snap System |
| Starfield hab grid | 4x4 base grid | CK Guide |
| CGA operations | 50+ distinct operations | CityEngine docs |
| Open source CGA impls | 5 known projects | GitHub |

---

## Sources

### Primary (HIGH confidence)
- Joel Burgess GDC 2013 transcript: http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html
- Joel Burgess GDC 2016 (Fallout 4): https://archive.org/details/GDC2016Burgess
- Creation Kit Wiki tutorials: https://ck.uesp.net/wiki/Bethesda_Tutorial_Layout_Part_1
- CityEngine CGA Reference: https://doc.arcgis.com/en/cityengine/2019.0/cga/cityengine-cga-introduction.htm
- CityEngine Tutorial 6 (Basic CGA): https://doc.arcgis.com/en/cityengine/latest/tutorials/tutorial-6-basic-shape-grammar.htm
- Muller & Wonka SIGGRAPH 2006: https://history.siggraph.org/learning/procedural-modeling-of-buildings-by-muller-wonka-haegler-ulmer-and-gool/

### Secondary (MEDIUM confidence)
- Gamasutra/GameDeveloper summary: https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design
- 80.lv interview with Burgess: https://80.lv/articles/building-huge-open-worlds-modularity-kits-art-fatigue
- Level Design Book modular section: https://book.leveldesignbook.com/process/blockout/metrics/modular
- Starfield CK Guide: https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
- Creation Kit asset nomenclature forum: https://www.gamesas.com/creation-kit-asset-nomenclature-t351192.html
- Inu Games Modular Snap System: https://inu-games.com/2018/08/30/modular-snap-system-plugin-for-ue4/

### Tertiary (LOW confidence - needs validation)
- Fallout 4 snap point variable names (reverse-engineered, not official docs)
- Starfield procedural POI specifics (limited official documentation)
- Piece counts per kit (requires direct CK inspection to verify)

### Open Source References
- Prokitektura (Python/Blender CGA): https://github.com/nortikin/prokitektura-blender
- BCGA (Blender CGA): https://github.com/vvoovv/bcga
- ShapeML (C++ grammar framework): https://github.com/stefalie/shapeml
- Snappable Meshes PCG (Unity): https://github.com/VideojogosLusofona/snappable-meshes-pcg
- Snappable Meshes paper: https://arxiv.org/pdf/2108.00056
