# Interior Mapping, Rendering, and Procedural Interior Generation -- Research

**Researched:** 2026-04-02
**Domain:** Shader techniques, interior rendering, procedural room generation, game architecture
**Confidence:** HIGH (well-established techniques with AAA production track record)

---

## Summary

This research covers the full spectrum of creating convincing building interiors in games, from pure shader illusions (zero geometry cost) through to fully walkable procedurally-generated rooms with furniture. The findings split into five pillars: (1) interior mapping shaders for window illusions, (2) walkable interior rendering with occlusion/streaming, (3) room layout algorithms, (4) multi-floor building generation, and (5) atmosphere/storytelling. Each pillar has well-documented techniques with AAA production use.

**Primary recommendation:** Use a hybrid two-tier system. Interior mapping shaders for all non-enterable buildings (95% of settlement buildings), and actual geometry with portal-based occlusion + additive scene loading for key walkable interiors (taverns, shops, quest buildings). The VeilBreakers toolkit already has `building_interior_binding.py` with room-type mappings and `_building_grammar.py` with spatial graph-based furniture placement -- these need to be connected to actual Blender geometry generation and a Unity interior mapping shader needs to be created.

**Existing toolkit state:** The codebase has `BUILDING_ROOM_MAP`, `ROOM_SPATIAL_GRAPHS`, `ROOM_ACTIVITY_ZONES`, and `generate_interior_layout()` -- all pure logic, no Blender geometry wiring. No interior mapping shader exists in the Unity templates. The `building_interior_binding.py` bridges building types to room specs but nothing generates the actual mesh shells or transitions.

---

## Mission 1: Interior Mapping Shader Technique

### The Joost van Dongen Technique (2007/2008)

**Confidence: HIGH** -- technique is 18 years old, used in dozens of AAA titles.

Interior mapping creates the illusion of 3D rooms behind windows using only a flat polygon + shader. Zero additional geometry. The shader performs ray-box intersection against virtual wall/ceiling/floor planes to determine what the camera should see through each window.

**How it works:**
1. UV coordinates are fractioned (`frac(uv)`) to create repeating room cells
2. UVs mapped to [-1, 1] range for box intersection math
3. View direction converted to tangent space
4. Ray cast against 3 axis-aligned planes (2 walls + ceiling/floor)
5. Closest intersection determines which cubemap face to sample
6. Result blended with exterior surface using window mask texture

**Core math (HLSL):**
```hlsl
float3 id = 1.0 / viewDirTangent;        // reciprocal of view direction
float3 k = abs(id) - pos * id;            // distance to box planes
float kMin = min(min(k.x, k.y), k.z);    // closest intersection
pos += kMin * viewDirTangent;             // final sample position
float4 interior = texCUBE(_InteriorCubemap, pos);
```

**Required inputs per material:**
- Cubemap texture (or texture atlas with 6 faces: 4 walls + ceiling + floor)
- Window mask texture (which parts of the surface are windows)
- Room depth parameter (controls apparent room size)
- Optional: room size variation, random seed per window

### Games Using Interior Mapping

| Game | Implementation Notes |
|------|---------------------|
| Marvel's Spider-Man PS4/PS5 | Thousands of NYC buildings, all shader-only interiors |
| Destiny / Destiny 2 | Tower and city environments |
| Overwatch | Map buildings |
| BioShock Infinite | Columbia buildings |
| Assassin's Creed series | City environments |
| Saints Row | Urban environments |

### Randomization and Variation

**Texture atlas approach (recommended):** Pack multiple room variations into a single atlas (e.g., 4x4 grid = 16 room types). Each window selects randomly from the atlas using a deterministic seed (object position hash). This prevents the "all rooms look identical" problem.

**Per-window variation techniques:**
- Random cubemap rotation (cheap, limited variety)
- Atlas index selection per window via hash of UV + object ID
- Random lighting state (lit/unlit/partially lit) per room
- Blinds/curtain state variation via secondary texture

### Unity URP Implementation

**Confidence: HIGH** -- multiple proven implementations exist.

Unity's Shader Graph Feature Samples (available since 2022 LTS / Unity 6) include an interior cubemap mapping example. Additionally:

| Implementation | Source | Notes |
|---------------|--------|-------|
| Gaxil/Unity-InteriorMapping | GitHub (MIT) | Full feature set: room variations, corridors, window refraction, light projection, shadows. HLSL, DX11 tested. |
| knowercoder/BasicInteriorMap | GitHub | URP + animated texture support |
| herohiralal HLSL gist | GitHub Gist | Pure HLSL for URP, minimal |
| merpheus-dev/FakeInteriorsShader | GitHub | Spider-Man-style, Shader Graph based |

**Recommended approach for VeilBreakers:**
- Write a custom HLSL shader for URP (not Shader Graph -- more control, better performance)
- Use texture atlas approach with 8-16 dark fantasy room variants
- Include parameters: room depth, room scale, atlas index, lighting state, grime/damage overlay
- Window mask driven by the building's exterior material

### Performance Cost

**Confidence: HIGH** -- consistently reported as negligible.

Interior mapping is a fragment shader effect -- no geometry, no draw calls, no LOD needed. The cost is:
- ~4-8 extra ALU instructions per pixel (ray-box intersection)
- 1 cubemap/atlas texture sample per pixel
- No vertex processing overhead
- No memory for room geometry

**Comparison to actual geometry:**
| Metric | Interior Mapping | Actual Room Geometry |
|--------|-----------------|---------------------|
| Vertices per room | 0 | 200-2000+ |
| Draw calls per building | 0 additional | 5-20 per room |
| Texture memory | 1 atlas shared | Per-room materials |
| LOD required | No | Yes |
| Occlusion culling | Not needed | Required |
| Suitable for 500+ buildings | Yes | No (memory/perf) |

### Limitations

1. **Viewing angle:** At extreme grazing angles the parallax breaks down -- rooms appear to flatten. Mitigate by adding reflective glass overlay at shallow angles.
2. **Room uniformity:** Rooms are always axis-aligned rectangular boxes. No L-shaped rooms, no varied ceiling heights.
3. **No interaction:** Purely visual -- cannot enter, no physics, no AI pathfinding.
4. **Repetition:** Without atlas randomization, every window shows the same room.
5. **No 3D objects:** Furniture/objects must be baked into the cubemap faces, cannot be dynamic.
6. **Requires `DisableBatching="True"`** for tangent space calculations (minor perf consideration).

### Combining Interior Mapping with Walkable Interiors

**The hybrid approach used by AAA studios:**
- 95% of buildings: interior mapping shader only (non-enterable)
- 5% of buildings: actual geometry interiors (key locations)
- When player approaches an enterable building: the interior mapping shader on that building's windows can be swapped to match the actual interior layout for visual consistency
- Door transition: either seamless (Dark Souls style) or brief loading screen (Bethesda style)

---

## Mission 2: Walkable Interior Rendering

### Bethesda Creation Kit: Interior Cells

**Confidence: HIGH** -- documented system, used in Skyrim/Fallout 4/Starfield.

Bethesda separates interiors into independent "cells" -- each interior is its own self-contained worldspace. Transition happens via "load doors" configured as teleport references.

**How it works:**
1. Exterior worldspace: door mesh placed on building
2. Door configured with `Teleport` flag linking to interior cell
3. Player activates door: loading screen, interior cell loaded, exterior unloaded
4. Interior cell: completely separate coordinate space, own lighting, own navmesh

**Pros:** Complete artistic freedom per interior, no memory overhead from unused interiors, can have interiors much larger than exterior footprint (TARDIS effect).

**Cons:** Loading screen breaks immersion, no seamless transition, player cannot see interior from outside.

### Dark Souls: Seamless Interiors

**Confidence: HIGH** -- well-analyzed design.

From Software uses a fundamentally different approach: interior and exterior exist in the same worldspace as continuous geometry. Director Miyazaki explicitly designed for "seamless exploration."

**How it works:**
1. Building interior geometry exists in the same scene as exterior
2. No loading screens between inside/outside
3. Occlusion culling handles performance (interior not rendered when outside)
4. Cathedral of the Deep (DS3): interior vertical segmentation (different floors) + exterior loop planning (different routes)
5. Verticality is key -- players "climb" between areas

**Pros:** Complete immersion, spatial coherence, no loading breaks.

**Cons:** All geometry always present in scene graph (memory), requires careful manual level design, not easily procedural.

**Relevance to VeilBreakers:** Dark Souls approach works for hand-crafted dungeons but not for procedural settlements with dozens of enterable buildings. Use selectively for key dungeon/castle areas.

### Portal-Based Occlusion Culling

**Confidence: HIGH** -- foundational rendering technique.

Portal rendering divides the world into cells (rooms) connected by portals (doorways/windows). The renderer traverses the portal graph starting from the camera's cell, clipping the view frustum to each portal.

**Algorithm:**
1. Determine camera's current cell
2. Render current cell
3. For each portal in current cell visible to camera:
   a. Clip frustum to portal bounds
   b. Recurse into connected cell with clipped frustum
   c. Render connected cell with clipped frustum
4. Everything beyond non-visible portals is culled

**Performance characteristics:**
- Computationally cheap (frustum-plane intersections only)
- Deterministic -- no false positives
- Perfect for structured environments (buildings, dungeons, corridors)
- Scales with portal count, not geometry count

**Modern layered approach:**
1. Portal culling: coarse visibility for structured interiors
2. Hi-Z buffer: fine-grained occlusion for dynamic/open areas
3. Clustered rendering: efficient processing of remaining visible geometry

### Unity Interior Streaming

**Confidence: HIGH** -- documented Unity feature.

Unity supports additive scene loading with occlusion culling for interior streaming:

**Setup:**
1. Each interior is a separate Unity Scene
2. Scenes loaded/unloaded additively via `SceneManager.LoadSceneAsync(name, LoadSceneMode.Additive)`
3. Occlusion culling data baked with all scenes open simultaneously
4. Portal/area colliders trigger scene loading as player approaches

**Key requirements:**
- Occlusion data must be baked with all scenes open at once
- Data saved as `Assets/[active Scene name]/OcclusionCullingData.asset`
- Reference added to all participating scenes
- Occlusion portals/areas placed in additive scenes

**Pattern for VeilBreakers:**
```
settlement_exterior.unity          -- always loaded
  tavern_interior.unity            -- loaded when near tavern
  blacksmith_interior.unity        -- loaded when near forge
  castle_great_hall.unity          -- loaded when entering castle
```

### Camera Transition Techniques

| Technique | When to Use | Implementation |
|-----------|-------------|----------------|
| Seamless walk-through | Dark Souls style, same scene | No special handling needed |
| Brief fade to black | Bethesda style, scene swap | 0.3-0.5s fade, load async during fade |
| Door animation mask | Player opens door, camera pushes through | Animate door + camera dolly, load behind door geometry |
| Portal effect | Dark fantasy magical transition | VFX on doorway, swap scene behind VFX |

**Recommended for VeilBreakers:** Door animation mask for important buildings (taverns, shops), seamless for dungeons/castles where interior is in same scene.

---

## Mission 3: Room Layout Algorithms

### Algorithm Comparison

| Algorithm | Best For | Pros | Cons |
|-----------|----------|------|------|
| BSP (Binary Space Partition) | Dungeons, regular layouts | No overlapping rooms guaranteed, simple to implement | Rooms always rectangular, tree structure limits connectivity |
| Squarified Treemap | Floor plans with target areas | Rooms approach square aspect ratio, no wasted space, area-accurate | All rooms rectangular, no corridors |
| Constrained Growth | Organic layouts | Adjacency-aware, corridor generation, accessible rooms | More complex, slower |
| Graph-Based (Space Syntax) | Architecturally correct layouts | Models adjacency/accessibility like real architecture, ignores metric info | Requires two-stage (topology then geometry) |
| Constraint Satisfaction | Furniture placement | Intuitive constraints (bed against wall), guaranteed satisfaction | Backtracking can be slow for complex layouts |

### BSP for Floor Plans

**Confidence: HIGH** -- standard game dev technique.

```
1. Start with building footprint rectangle
2. Choose split axis (alternate H/V, or random with aspect ratio bias)
3. Split at random point within valid range (e.g., 40-60% of dimension)
4. Recurse on both halves until minimum room size reached
5. Each leaf = one room
6. Connect sibling rooms with doorways through split line
```

**Customization for medieval buildings:**
- Bias split positions to create one large + one small room (great hall + side room)
- Enforce minimum room dimensions: 3m x 3m (smallest closet) to 15m x 10m (great hall)
- First split creates front/back of building (public/private separation)

### Squarified Treemap (Marson & Musse, 2010)

**Confidence: HIGH** -- published algorithm with real-time performance.

Takes a list of room types with target areas and packs them into a rectangle with no wasted space while minimizing aspect ratios.

```
Input: building_footprint, rooms = [
    ("great_hall", 0.4),    # 40% of total area
    ("kitchen", 0.2),
    ("bedroom", 0.15),
    ("storage", 0.15),
    ("corridor", 0.1)
]
Output: list of (room_type, x, y, width, height) non-overlapping rectangles
```

**Algorithm steps:**
1. Sort rooms by area (descending)
2. Place largest room first, filling one strip of the rectangle
3. Each subsequent room either extends current strip or starts new strip
4. Strip direction chosen to minimize worst aspect ratio

### Graph-Based Room Connectivity (Space Syntax)

**Confidence: MEDIUM** -- active research area, newer approaches.

Modern approach factorizes floor-plan synthesis into two stages:
1. **Topology stage:** Sequential room-centroid placement capturing adjacency and circulation intent
2. **Geometry stage:** Rectangle regression on a room-boundary graph for metrically consistent rooms

**Adjacency matrix approach:**
```
Tavern adjacency:
  main_hall -- kitchen (direct)
  main_hall -- stairs_up (direct)
  main_hall -- entrance (direct)
  kitchen -- storage (direct)
  stairs_up -- bedroom_1 (via stairs)
  stairs_up -- bedroom_2 (via corridor)
```

The topology-first approach matches how real architects think: define which rooms connect, then figure out dimensions.

### Constraint Satisfaction for Furniture Placement

**Confidence: HIGH** -- well-established technique, already partially implemented in VeilBreakers.

The VeilBreakers toolkit already has `ROOM_SPATIAL_GRAPHS` and `generate_interior_layout()` using this approach. The CSP approach:

**Variables:** Objects to place (bed, table, chairs, etc.)
**Domains:** All possible positions for each object (grid cells)
**Constraints:**
- No overlap between objects
- Minimum clearance around objects (0.3m walls, 1.0m doors)
- Wall-adjacent items must be against walls
- Chairs face tables
- Beds against back wall
- Path from door to all areas must remain clear

**Backtracking algorithm:**
```python
def solve(variable_index, assignment):
    if variable_index >= num_variables:
        return True  # all placed
    for position in shuffled_domain(variable_index):
        assignment[variable_index] = position
        if check_constraints(variable_index, assignment):
            if solve(variable_index + 1, assignment):
                return True
    return False  # backtrack
```

**Optimization: Grid-based collision** -- use a 2D grid (like Shadows of Doubt's 1.8m tiles) to quickly check occupancy without geometric intersection tests.

### Shadows of Doubt Interior System (Reference Implementation)

**Confidence: HIGH** -- shipped commercial game, detailed devblog.

Location hierarchy: City > District > Block > Building > Floor > Address > Room > Tile

**Key design decisions:**
- 1.8m x 1.8m tile grid for everything (pathfinding, culling, generation)
- Building floors: 15x15 tiles
- Hallway generation first (prevents rooms only accessible through other rooms)
- Room placement priority order (living room first, then bathroom, etc.)
- Ranking criteria per room: floor space proportions, uniform shape (corner count), window access
- Rooms can "steal floorspace" from existing rooms when needed
- Furniture driven by occupant preferences (personalization)

**Adaptable to VeilBreakers:**
- Use similar priority-based room placement
- Tile grid can be coarser (2m x 2m for medieval buildings)
- Room priority: focal room first (tavern hall, great hall), then utility rooms

### Medieval Room Layouts

#### Tavern
```
Ground Floor:
  +---------------------------+
  | Main Hall (60%)           |
  | [bar_counter at back wall]|
  | [tables + chairs center]  |
  | [fireplace side wall]     |
  +------------------+--------+
  | Kitchen (25%)    | Stairs |
  | [cooking_fire]   |   up   |
  | [shelves, barrels]|       |
  +------------------+--------+
  |     Entrance Door         |

Upper Floor:
  +---------------------------+
  | Corridor                  |
  +--------+--------+--------+
  | Room 1 | Room 2 | Room 3 |
  | [bed]  | [bed]  | [bed]  |
  +--------+--------+--------+

Cellar (-1):
  +---------------------------+
  | Storage (barrels, crates) |
  | [wine racks along walls]  |
  +---------------------------+
```

#### Castle
```
Ground Floor:
  +-------------------------------------------+
  | Courtyard                                 |
  +-------------------+-----------+-----------+
  | Great Hall (50%)  | Barracks  | Kitchen   |
  | [throne/dais]     | [beds]    | [hearth]  |
  | [long tables]     | [racks]   | [tables]  |
  | [tapestries]      |           |           |
  +-------------------+-----------+-----------+

Upper Floors:
  +-------------------------------------------+
  | War Room (25%)    | Bedchambers           |
  | [map table]       | [canopy beds]         |
  | [weapon displays] | [wardrobes]           |
  +-------------------+-----------------------+

Below Ground:
  +-------------------------------------------+
  | Treasury/Vault    | Dungeons              |
  | [chests, gold]    | [cells, chains]       |
  +-------------------+-----------------------+
```

#### Shop (Blacksmith, Apothecary, etc.)
```
Ground Floor:
  +---------------------------+
  | Shop Floor (60%)          |
  | [display counters]        |
  | [wares on shelves]        |
  +------------------+--------+
  | Stockroom (30%)  | Stairs |
  | [crates, raw     |   up   |
  |  materials]      |        |
  +------------------+--------+
  |    Shop Entrance          |

Upper Floor:
  +---------------------------+
  | Living Quarters           |
  | [bed, table, wardrobe]    |
  +---------------------------+
```

---

## Mission 4: Multi-Floor Buildings

### THE FINALS Procedural Building System (Embark Studios / Houdini)

**Confidence: HIGH** -- GDC-presented, shipping AAA game.

The FINALS generates fully destructible multi-floor buildings using a modular Feature Node system in Houdini:

**Key architectural insight:** Elements that span multiple floors (staircases, elevator shafts, chimney stacks) must be positioned FIRST, then the building is split into individual floors.

**Floor Slab Generation:**
- Floor Height: vertical spacing between slabs
- Floor Thickness: slab depth
- Clearance Threshold: minimum space between slab and ceiling above
- Slabs align to inner faces of exterior walls

**Modular Feature Node approach:**
1. Foundation nodes
2. Exterior wall nodes
3. Multi-floor structural elements (stairs, shafts, chimneys)
4. Floor slab nodes
5. Interior wall nodes (subdivide floor space)
6. Window/door nodes
7. Roof nodes
8. Detail/decoration nodes

### Staircase Generation

| Type | When to Use | Generation Notes |
|------|-------------|-----------------|
| Straight run | Simple houses, utility buildings | Width 1-1.2m, rise/run ratio 7/11 |
| L-shaped | Multi-room buildings | Two straight runs with landing, saves floor space |
| Spiral | Towers, castle turrets | Radius 1-1.5m, always clockwise ascending (defender's advantage) |
| Grand/split | Castle great halls, cathedrals | Wide first flight splits to two upper flights |

**Medieval spiral staircase detail:** Historical spiral staircases in castles ascend clockwise so that a right-handed defender fighting downward has full sword swing while an attacker climbing has their sword arm blocked by the central column.

**Staircase placement algorithm:**
1. Identify stairwell zone (2m x 3m minimum for straight, 3m x 3m for spiral)
2. Place stairwell in same XY position on all connected floors
3. Cut floor slab opening at stairwell position
4. Generate stair geometry connecting floors
5. Add railings/walls around stairwell

### Floor Plan Consistency Across Floors

**Structural wall alignment rule:** Load-bearing walls on upper floors MUST align with walls below. Non-structural partition walls can vary freely.

**Implementation:**
```
1. Generate ground floor plan (BSP/treemap)
2. Mark structural walls (exterior + any interior walls supporting upper floors)
3. Copy structural wall positions to upper floors
4. Subdivide remaining space on upper floors independently
5. Verify all structural walls align vertically
```

### Varying Floor Heights

| Floor Type | Height | Use |
|-----------|--------|-----|
| Cellar/dungeon | 2.5-3.0m | Low ceilings, oppressive |
| Ground floor (commercial) | 3.5-4.0m | Tall for shop displays, tavern halls |
| Great hall | 5.0-8.0m+ | Double-height, open to rafters |
| Upper residential | 2.8-3.0m | Standard rooms |
| Attic | 1.5-2.5m (sloped) | Under roof, variable height |
| Tower levels | 3.0m | Consistent, tight |

### Balconies, Mezzanines, Open-to-Below

**Mezzanine generation:**
1. Identify rooms marked as "double-height" (great halls, tavern main rooms)
2. On the floor above, instead of full floor slab, generate half-slab or balcony ring
3. Add railing along open edge
4. Optional: grand staircase connecting mezzanine to room below

**Chimney/Fireplace Multi-Floor:**
1. Place fireplace on ground floor against exterior wall
2. Generate chimney shaft upward through all floors
3. Cut openings in each floor slab for chimney
4. Fireplace openings can exist on multiple floors (shared chimney, different hearths)
5. Chimney exits through roof with cap/pot

---

## Mission 5: Interior Atmosphere and Storytelling

### Environmental Storytelling Through Clutter

**Confidence: HIGH** -- AAA standard practice, documented by Naughty Dog/others.

Naughty Dog's approach (The Last of Us Part II): every space has a purpose and adds to the narrative. Each space feels uniquely handcrafted with strategically placed environmental storytelling moments.

**Layers of interior detail:**
1. **Structural:** Walls, floors, ceiling, doors, windows (defines space)
2. **Functional furniture:** Tables, beds, shelves (defines room purpose)
3. **Personal items:** Books, letters, trinkets (defines occupant)
4. **Wear and use:** Scratches on floors, worn chair seats, soot near fireplace (defines history)
5. **Narrative clutter:** Specific items telling a micro-story (blood stains, overturned furniture, abandoned meals)

**VeilBreakers toolkit already has this:** `_STORYTELLING_PROPS` and `add_storytelling_props()` in `_building_grammar.py` implement layer-5 narrative clutter. `generate_overrun_variant()` handles corruption/damage narrative debris.

### Corruption/Damage Progression for Dark Fantasy

**Tiers of interior decay (VeilBreakers-specific):**

| Tier | Name | Visual Indicators |
|------|------|-------------------|
| 0 | Pristine | Clean surfaces, organized items, warm lighting |
| 1 | Neglected | Dust, cobwebs, dim lighting, slightly disorganized |
| 2 | Abandoned | Broken furniture, debris, rats, water damage, no artificial light |
| 3 | Corrupted | Veil-corruption tendrils on walls, glowing runes, warped geometry |
| 4 | Overrun | Veil creatures nesting, organic growths, pulsating walls, hostile environment |

**Implementation via material parameter collection:**
- Corruption level (0-1 float) drives material blending
- Base material lerps toward corruption material (dark veins, bioluminescent growths)
- Geometry displacement at high corruption (bulging walls, warped floors)
- Particle effects scale with corruption (spores, embers, void sparks)

### Lighting as Wayfinding

**Confidence: HIGH** -- well-documented level design technique.

Core principle: players are drawn toward light. In interiors, this is the primary navigation tool.

**Techniques:**
1. **Bright doorways:** Light spilling through doorways pulls players toward exits/objectives
2. **Contrast:** Bright focal areas (fireplace, chandelier) vs dark periphery guides eye
3. **Color temperature:** Warm light = safe, cool/green light = danger, purple = Veil corruption
4. **Light strings:** Sequential light sources create a path (torches along a corridor)
5. **Absence of light:** Darkness on the critical path creates tension/horror

**Recommended for VeilBreakers interiors:**
- Fireplace/hearth as warm anchor in taverns/homes
- Torch sconces along corridors (every 5-7m)
- Eerie bioluminescent glow in corrupted areas
- Window light shafts (god rays) marking important objects/areas
- Light intensity decreases deeper into buildings (increasing tension)

### Sound Design for Interiors

**Confidence: HIGH** -- standard middleware feature.

**Reverb zones:** Wwise 23.1+ and FMOD both support room-aware reverb:
- Each room type gets a reverb preset (stone cathedral = long reverb, small wooden room = short)
- Transition regions between zones fade smoothly
- Portals (doorways) define acoustic boundaries

**Material-based footsteps:**
| Surface | Sound Category |
|---------|---------------|
| Stone floor | Hard, echoing |
| Wood planks | Creaky, hollow |
| Carpet/rug | Muffled |
| Wet stone | Splashy |
| Dirt/earth (cellar) | Soft thud |
| Metal grating | Metallic ring |

**Interior ambient sounds:**
- Fireplace crackle (taverns, bedrooms)
- Dripping water (cellars, dungeons)
- Wind through broken windows (ruins)
- Distant voices/activity (populated buildings)
- Rats/insects (abandoned spaces)
- Veil whispers (corrupted spaces) -- VeilBreakers specific

---

## Architecture: Recommended Hybrid System

### Two-Tier Building Interior System

```
Tier 1: Interior Mapping (non-enterable, 95% of buildings)
  - URP HLSL shader on building exterior material
  - Texture atlas with 16+ dark fantasy room variants
  - Per-window randomization via position hash
  - Lighting state variation (lit, dim, dark, flickering)
  - Zero geometry cost, zero draw call cost
  - Applied to ALL settlement buildings by default

Tier 2: Walkable Interiors (enterable, 5% of buildings)
  - Actual geometry generated by Blender tools
  - Room layout via BSP/treemap + constraint satisfaction furniture
  - Loaded as additive Unity scenes
  - Portal-based occlusion at doorways
  - Interior mapping on these buildings' windows matches actual interior
  - Only generated for: taverns, shops, quest buildings, player housing
```

### Generation Pipeline

```
Building Shell (exterior)
    |
    +-- Is enterable? --NO--> Apply interior mapping shader
    |                         (Tier 1, done)
    YES
    |
    v
Room Layout Generation
    |-- BSP/Treemap subdivide footprint into rooms
    |-- Apply medieval room rules (room types, proportions)
    |-- Place multi-floor elements (stairs, chimneys) first
    |-- Generate floor plans per level
    |
    v
Interior Geometry Generation (Blender)
    |-- Generate room shell meshes (walls, floor, ceiling)
    |-- Cut doorway openings between rooms
    |-- Add architectural details (arches, beams, columns)
    |-- Apply materials from STYLE_MATERIAL_MAP
    |
    v
Furniture Placement
    |-- generate_interior_layout() with ROOM_SPATIAL_GRAPHS
    |-- Constraint satisfaction ensures no overlaps
    |-- Quality tier affects furniture density/condition
    |
    v
Atmosphere
    |-- generate_lighting_layout() for light sources
    |-- add_storytelling_props() for narrative clutter
    |-- generate_overrun_variant() for corruption
    |-- Reverb zone metadata for audio
    |
    v
Export to Unity
    |-- Room meshes as GLB/FBX
    |-- Packed as additive scene
    |-- Occlusion data baked
    |-- Door triggers configured
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interior mapping shader math | Custom ray-box intersection from scratch | Adapt Gaxil/Unity-InteriorMapping (MIT) or Unity Shader Graph Feature Samples | Ray-box math has subtle edge cases, proven implementations exist |
| Furniture collision detection | Custom AABB intersection | Grid-based occupancy map (Shadows of Doubt style) | Grid is O(1) lookup vs O(n) geometric tests |
| Room connectivity validation | Manual pathfinding | Flood fill from entrance door | Guarantees all rooms reachable, trivial to implement |
| Reverb zone setup | Custom audio system | Wwise Reverb Zones or FMOD snapshots | Middleware handles smooth transitions and spatialization |
| Occlusion culling | Custom portal renderer | Unity built-in occlusion culling + Occlusion Areas/Portals | Unity's system is battle-tested, integrates with scene loading |

---

## Common Pitfalls

### Pitfall 1: Interior Mapping Tangent Space
**What goes wrong:** Interior mapping looks correct in some orientations but distorted/inverted in others.
**Why it happens:** View direction must be in tangent space, which requires correct tangent/bitangent vectors. Batched objects share tangent space incorrectly.
**How to avoid:** Set `DisableBatching="True"` on the shader. Use per-vertex tangent-to-world matrix.
**Warning signs:** Rooms appear to invert when camera rotates, or all windows show the same perspective regardless of viewing angle.

### Pitfall 2: Room Layout Dead Ends
**What goes wrong:** Generated floor plans have rooms only accessible through other rooms (bedroom through kitchen through bathroom).
**Why it happens:** BSP/treemap algorithms don't inherently create corridors.
**How to avoid:** Generate hallways FIRST (like Shadows of Doubt), then subdivide remaining space into rooms. Or: validate connectivity graph after generation and add corridor doorways.
**Warning signs:** Adjacency graph has rooms with only one connection to non-corridor rooms.

### Pitfall 3: Structural Misalignment Across Floors
**What goes wrong:** Upper floor walls don't align with ground floor walls, creating physically impossible buildings.
**Why it happens:** Each floor generated independently without constraints from floors below.
**How to avoid:** Generate structural walls first for ALL floors, copy positions upward, then subdivide independently on each floor.
**Warning signs:** Building cross-section shows walls floating with no support.

### Pitfall 4: Furniture Blocking Doors
**What goes wrong:** Generated furniture layout blocks the room entrance.
**Why it happens:** Placement algorithm doesn't reserve door clearance corridor.
**How to avoid:** Reserve a 1.0m corridor from door to room center before placing any furniture. The existing `generate_interior_layout()` already handles this with `_door_corridor_clear()`.
**Warning signs:** Navmesh generation fails for room, or pathfinding to room interior fails.

### Pitfall 5: Scene Loading Hitches
**What goes wrong:** Player enters building and experiences a visible hitch/freeze.
**Why it happens:** Interior scene loaded synchronously, or loaded too late.
**How to avoid:** Use `LoadSceneAsync` triggered by proximity collider (10-15m before door), not door interaction. Preload interior as player approaches.
**Warning signs:** Frame time spike when opening doors.

### Pitfall 6: Occlusion Data Not Shared
**What goes wrong:** Interior geometry visible through walls, or exterior disappears when inside.
**Why it happens:** Occlusion culling data baked separately for each scene.
**How to avoid:** Open ALL additive scenes simultaneously before baking occlusion data. Unity saves combined data to a shared asset.
**Warning signs:** Objects popping in/out at scene boundaries.

---

## Code Examples

### Interior Mapping Shader (URP HLSL)
```hlsl
// Source: Adapted from Gaxil/Unity-InteriorMapping (MIT) + Joost van Dongen technique
Shader "VeilBreakers/InteriorMapping"
{
    Properties
    {
        _MainTex ("Exterior Albedo", 2D) = "white" {}
        _InteriorAtlas ("Interior Atlas (4x4)", 2D) = "black" {}
        _WindowMask ("Window Mask", 2D) = "black" {}
        _RoomDepth ("Room Depth", Range(0.1, 5.0)) = 1.0
        _AtlasSize ("Atlas Grid Size", Float) = 4.0
        _GrimeOverlay ("Grime/Damage", 2D) = "black" {}
        _CorruptionLevel ("Corruption", Range(0, 1)) = 0.0
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" }
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes { float4 posOS : POSITION; float2 uv : TEXCOORD0; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; };
            struct Varyings { float4 posCS : SV_POSITION; float2 uv : TEXCOORD0; float3 viewDirTS : TEXCOORD1; };

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            TEXTURE2D(_InteriorAtlas); SAMPLER(sampler_InteriorAtlas);
            TEXTURE2D(_WindowMask); SAMPLER(sampler_WindowMask);
            float _RoomDepth, _AtlasSize, _CorruptionLevel;

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                OUT.posCS = TransformObjectToHClip(IN.posOS.xyz);
                OUT.uv = IN.uv;
                // Tangent space view direction
                float3 worldPos = TransformObjectToWorld(IN.posOS.xyz);
                float3 viewDir = GetWorldSpaceViewDir(worldPos);
                float3 normalWS = TransformObjectToWorldNormal(IN.normalOS);
                float3 tangentWS = TransformObjectToWorldDir(IN.tangentOS.xyz);
                float3 bitangentWS = cross(normalWS, tangentWS) * IN.tangentOS.w;
                OUT.viewDirTS = float3(
                    dot(viewDir, tangentWS),
                    dot(viewDir, bitangentWS),
                    dot(viewDir, normalWS)
                );
                return OUT;
            }

            float4 frag(Varyings IN) : SV_Target
            {
                float mask = SAMPLE_TEXTURE2D(_WindowMask, sampler_WindowMask, IN.uv).r;
                float4 exterior = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, IN.uv);

                if (mask < 0.01) return exterior; // not a window

                // Interior mapping ray-box intersection
                float3 viewDir = normalize(IN.viewDirTS);
                float2 roomUV = frac(IN.uv * _AtlasSize); // which room cell
                float3 pos = float3(roomUV * 2.0 - 1.0, 1.0); // map to [-1,1] box

                float3 id = 1.0 / viewDir;
                float3 k = abs(id) - pos * id;
                float kMin = min(min(k.x, k.y), k.z);
                float3 hitPos = pos + kMin * viewDir;

                // Deterministic room index from UV cell
                float2 cellIndex = floor(IN.uv * _AtlasSize);
                float roomHash = frac(sin(dot(cellIndex, float2(12.9898, 78.233))) * 43758.5453);
                float2 atlasOffset = floor(float2(
                    fmod(roomHash * 16.0, _AtlasSize),
                    floor(roomHash * 16.0 / _AtlasSize)
                )) / _AtlasSize;

                // Sample interior atlas
                float2 interiorUV = (hitPos.xy * 0.5 + 0.5) / _AtlasSize + atlasOffset;
                float4 interior = SAMPLE_TEXTURE2D(_InteriorAtlas, sampler_InteriorAtlas, interiorUV);

                // Blend with glass reflection at grazing angles
                float fresnel = pow(1.0 - saturate(dot(normalize(IN.viewDirTS), float3(0,0,1))), 3.0);
                float4 result = lerp(interior, exterior * 0.5 + 0.3, fresnel * 0.7);

                return lerp(result, exterior, 1.0 - mask);
            }
            ENDHLSL
        }
    }
}
```

### BSP Room Layout Generator (Python)
```python
# Source: Standard BSP adapted for medieval buildings
import random
from dataclasses import dataclass

@dataclass
class Room:
    x: float; y: float; w: float; h: float
    room_type: str = "generic"
    floor: int = 0

def bsp_subdivide(x, y, w, h, min_size=3.0, depth=0, max_depth=4, rng=None):
    """BSP subdivide a rectangle into rooms."""
    rng = rng or random.Random()
    if depth >= max_depth or (w < min_size * 2 and h < min_size * 2):
        return [Room(x, y, w, h)]

    # Choose split axis (prefer splitting longer dimension)
    if w > h * 1.25:
        split_vertical = True
    elif h > w * 1.25:
        split_vertical = False
    else:
        split_vertical = rng.random() > 0.5

    if split_vertical and w >= min_size * 2:
        split = rng.uniform(min_size, w - min_size)
        left = bsp_subdivide(x, y, split, h, min_size, depth+1, max_depth, rng)
        right = bsp_subdivide(x+split, y, w-split, h, min_size, depth+1, max_depth, rng)
        return left + right
    elif not split_vertical and h >= min_size * 2:
        split = rng.uniform(min_size, h - min_size)
        bottom = bsp_subdivide(x, y, w, split, min_size, depth+1, max_depth, rng)
        top = bsp_subdivide(x, y+split, w, h-split, min_size, depth+1, max_depth, rng)
        return bottom + top
    else:
        return [Room(x, y, w, h)]
```

### Additive Scene Loading (Unity C#)
```csharp
// Source: Unity documentation pattern for interior streaming
using UnityEngine;
using UnityEngine.SceneManagement;

public class InteriorLoader : MonoBehaviour
{
    [SerializeField] private string interiorSceneName;
    [SerializeField] private float loadDistance = 15f;
    [SerializeField] private float unloadDistance = 25f;

    private bool isLoaded = false;
    private AsyncOperation loadOp;

    void Update()
    {
        float dist = Vector3.Distance(
            transform.position,
            Camera.main.transform.position
        );

        if (!isLoaded && dist < loadDistance)
        {
            loadOp = SceneManager.LoadSceneAsync(
                interiorSceneName, LoadSceneMode.Additive
            );
            loadOp.allowSceneActivation = true;
            isLoaded = true;
        }
        else if (isLoaded && dist > unloadDistance)
        {
            SceneManager.UnloadSceneAsync(interiorSceneName);
            isLoaded = false;
        }
    }
}
```

---

## State of the Art (2024-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-window cubemap | Texture atlas with per-window hash | ~2018 (Spider-Man) | Eliminated repetition problem |
| Manual interior level design | Procedural generation (Shadows of Doubt) | 2023 | Enables massive city generation |
| Loading screen transitions | Additive scene streaming | Unity 2019+ | Seamless transitions possible |
| Simple BSP dungeons | Graph-based topology + geometry (Space Syntax) | 2024-2025 | Architecturally correct layouts |
| Houdini-only procedural buildings | Runtime generation (THE FINALS) | 2023 | Real-time procedural with destruction |
| Static reverb zones | Wwise Reverb Zones with geometry-driven transitions | 2023.1 | Smooth, spatial audio transitions |

---

## Open Questions

1. **Cubemap baking for interior mapping atlas**
   - What we know: Need 16+ dark fantasy room cubemaps for the atlas
   - What's unclear: Best workflow for creating these -- render in Blender? Hand-paint? Generate from room layouts?
   - Recommendation: Render from Blender using `generate_interior_layout()` output placed in a simple room shell, capture 6-face cubemap per variant

2. **Interior mapping on curved/irregular building surfaces**
   - What we know: Standard interior mapping assumes flat walls with regular UV grids
   - What's unclear: How to handle towers (cylindrical walls), irregular medieval building shapes
   - Recommendation: Apply interior mapping only to flat wall sections; use opacity fade-out near wall edges/corners

3. **Performance budget for walkable interiors**
   - What we know: Interior mapping is nearly free; walkable interiors have real geometry cost
   - What's unclear: How many simultaneous walkable interiors can be loaded on target hardware
   - Recommendation: Limit to 1-2 loaded walkable interiors at a time, with 10-15m preload distance

---

## Sources

### Primary (HIGH confidence)
- [Interior Mapping: rendering real rooms without geometry -- Joost van Dongen](http://joostdevblog.blogspot.com/2018/09/interior-mapping-real-rooms-without.html)
- [Interior Mapping original paper (PDF)](https://www.proun-game.com/Oogst3D/CODING/InteriorMapping/InteriorMapping.pdf)
- [Gaxil/Unity-InteriorMapping GitHub (MIT)](https://github.com/Gaxil/Unity-InteriorMapping)
- [merpheus-dev/FakeInteriorsShader (Shader Graph)](https://github.com/merpheus-dev/FakeInteriorsShader)
- [herohiralal HLSL URP Interior Mapping Gist](https://gist.github.com/herohiralal/44cd4e5d4910c73cb91db47bd03a2082)
- [Unity Shader Graph Feature Samples 2022 LTS](https://blog.unity.com/engine-platform/shader-graph-feature-examples-2022-lts)
- [Unity Manual: Occlusion Culling and Scene Loading](https://docs.unity3d.com/Manual/occlusion-culling-scene-loading.html)
- [Shadows of Doubt DevBlog 13: Creating Procedural Interiors](https://colepowered.com/shadows-of-doubt-devblog-13-creating-procedural-interiors/)
- [Making the Procedural Buildings of THE FINALS (SideFX)](https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/)
- [Medieval Castle Layout -- Exploring Castles](https://www.exploring-castles.com/castle_designs/medieval_castle_layout/)

### Secondary (MEDIUM confidence)
- [Interior Mapping -- Harry Alisavakis](https://halisavakis.com/my-take-on-shaders-interior-mapping/)
- [Interior Mapping -- Alan Zucconi](https://www.alanzucconi.com/2018/09/10/shader-showcase-9/)
- [80.lv Interior Mapping article](https://80.lv/articles/interior-mapping-rendering-real-rooms-without-geometry)
- [Spider-Man PS4 Interior Mapping -- ResetEra](https://www.resetera.com/threads/spider-man-ps4s-interior-mapping-shader-makes-the-city-pop.74071/)
- [Squarified Treemap Floor Plans -- Marson & Musse 2010](https://onlinelibrary.wiley.com/doi/10.1155/2010/624817)
- [Novel Algorithm for Real-time Floor Plan Generation](https://arxiv.org/abs/1211.5842)
- [Room Generation Using Constraint Satisfaction -- pvigier](https://pvigier.github.io/2022/11/05/room-generation-using-constraint-satisfaction.html)
- [Constrained Growth Method for Floor Plans -- TU Delft](https://graphics.tudelft.nl/~rafa/myPapers/bidarra.GAMEON10.pdf)
- [Advanced Occlusion Culling with Portals -- DaydreamSoft](https://daydreamsoft.com/blog/advanced-occlusion-culling-with-portals-hi-z-buffers-and-clustered-rendering)
- [Portal-Based Occlusion Culling -- Umbra 3D](https://medium.com/@Umbra3D/introduction-to-occlusion-culling-3d6cfb195c79)
- [Wayfinding -- The Level Design Book](https://book.leveldesignbook.com/process/blockout/wayfinding)
- [Lighting -- The Level Design Book](https://book.leveldesignbook.com/process/lighting)
- [Wwise Reverb Zones 2023.1](https://www.audiokinetic.com/en/blog/reverb-zones/)
- [GTA V Graphics Study -- Adrian Courreges](https://www.adriancourreges.com/blog/2015/11/02/gta-v-graphics-study/)
- [Dark Souls Level Design -- The Gamer](https://www.thegamer.com/dark-souls-1-fromsoftwares-magnum-opus-of-interconnected-level-design/)
- [Bethesda Tutorial World Hookup -- Creation Kit Wiki](https://ck.uesp.net/wiki/Bethesda_Tutorial_World_Hookup)

### Tertiary (LOW confidence)
- [Space Syntax-guided Post-training for Floor Plans](https://arxiv.org/abs/2602.22507) -- very recent, not yet validated
- [Hexagonal Cellular Automata for Layout Generation](https://www.tandfonline.com/doi/full/10.1080/13467581.2025.2568756) -- 2025, novel approach

---

## Metadata

**Confidence breakdown:**
- Interior mapping shader: HIGH -- 18-year-old technique with AAA production track record, multiple open-source implementations
- Walkable interior rendering: HIGH -- Unity occlusion/streaming is well-documented, portal culling is foundational
- Room layout algorithms: HIGH -- BSP/treemap/CSP are established algorithms, Shadows of Doubt provides production validation
- Multi-floor generation: MEDIUM-HIGH -- THE FINALS demonstrates it works, but integration with VeilBreakers toolkit needs custom work
- Atmosphere/storytelling: HIGH -- well-documented design principles, VeilBreakers already has some implementation

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable techniques, 3-month validity)
