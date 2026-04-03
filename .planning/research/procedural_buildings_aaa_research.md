# Procedural Buildings & Mapped Interiors -- AAA Deep Research

**Researched:** 2026-04-02
**Domain:** Procedural architecture generation, modular building kits, interior mapping, building grammars
**Confidence:** HIGH (cross-referenced GDC talks, academic papers, shipped AAA titles, open-source implementations, and existing VB toolkit codebase)

---

## Executive Summary

AAA procedural building generation is not one technique but a **layered pipeline** combining multiple approaches at different scales. The industry has converged on a clear hierarchy:

1. **City/settlement scale**: Road networks and lot subdivision (L-systems, tensor fields) define where buildings go
2. **Building mass scale**: Blockout volumes define building proportions and silhouette
3. **Facade scale**: Split grammars recursively subdivide facades into floors, bays, and architectural elements
4. **Detail scale**: Modular kit pieces fill in walls, windows, doors, trim, and ornamentation
5. **Interior scale**: Room graphs with constraint satisfaction place rooms, furniture, and storytelling props

The critical insight across all AAA studios is: **procedural systems generate structure and variation; artists author the modular pieces and style rules.** No shipped AAA game generates buildings from pure math alone. They all use artist-created kit pieces assembled by procedural logic.

**Primary recommendation for VeilBreakers:** The toolkit already has `_building_grammar.py`, `modular_building_kit.py`, `building_quality.py`, and `building_interior_binding.py`. The gap is not in the pieces themselves but in the **assembly intelligence** -- the grammar rules that compose pieces into buildings that look designed rather than random. Adopt the CGA split grammar approach for facade generation and Bethesda's kit-connector system for interiors.

---

## Table of Contents

1. [How AAA Studios Build Procedural Architecture](#1-how-aaa-studios-build-procedural-architecture)
2. [Building Grammar Systems](#2-building-grammar-systems)
3. [Interior Generation Best Practices](#3-interior-generation-best-practices)
4. [Modular Kit Approach (Industry Standard)](#4-modular-kit-approach-industry-standard)
5. [Gothic & Dark Fantasy Architecture Rules](#5-gothic--dark-fantasy-architecture-rules)
6. [Open Source Tools & Implementations](#6-open-source-tools--implementations)
7. [Application to VeilBreakers Toolkit](#7-application-to-veilbreakers-toolkit)
8. [Sources](#8-sources)

---

## 1. How AAA Studios Build Procedural Architecture

### 1.1 Ubisoft -- Assassin's Creed Series

**Confidence:** HIGH (GDC talks 2016-2025, public articles)

Ubisoft uses a **hybrid procedural + handcrafted** approach across the AC series:

**AC Unity (Paris, 2014):**
- Largest AC city at the time with 1:1 scale Paris
- Used the **AnvilNext 2.0 engine** with procedural facade composition
- Buildings composed from **modular facade panels** -- artist-authored wall sections, window frames, balconies, roof elements
- Interior spaces were a major innovation: ~25% of Paris buildings had enterable interiors
- Total game area was 3x any previous AC game when including interiors and underground areas
- GeometryWorks tessellation applied to roofs, cobblestones, archways, statues for geometric detail beyond texture

**AC Origins (Egypt, 2017):**
- Shifted to **Houdini Engine** for procedural asset placement (GDC 2018, Nicholas Routhier)
- Used an **archipelago structure**: procedurally generated open world with handcrafted "islands" of content
- Houdini scattered vegetation, rocks, and structural elements across terrain
- Buildings themselves were modular kit assemblies placed by level designers

**AC Syndicate (London, 2015):**
- Developed a **custom toolset** for Victorian London including:
  - Road mesh generation system
  - Building creation and placement pipeline
  - Sidewalk decoration system
- Buildings assembled from period-appropriate modular pieces

**AC Shadows (2025):**
- Nicolas Lopez's GDC 2025 talk: "shifting from maximum quality to scalable solutions"
- Procedural generation and AI used for data production at scale
- Smarter procedural approaches to reduce manual work

**Key Ubisoft pattern:** Facade panels are artist-authored modular pieces. Procedural systems handle **placement, combination, and variation** -- not geometry creation. Each building style has a "recipe" that defines valid panel combinations per floor.

### 1.2 CD Projekt Red -- Cyberpunk 2077 / The Witcher

**Confidence:** HIGH (multiple official statements, GDC 2022)

**Cyberpunk 2077 (Night City):**
- CD Projekt RED explicitly stated: **"Everything was done by hand. Nothing is procedural in our world."**
- Used a **prefab-based hierarchy** to build the city
- Night City used **kitbash modular assets** -- artist-authored building blocks snapped together manually
- Interior spaces were fully handcrafted
- GDC 2022 presentation: "Building Night City" covered the tech team's approach to streaming and memory management for the dense urban environment

**Cyberpunk 2 (upcoming):**
- Major shift: will use **procedural generation for cities, characters, interiors, and environments**
- This is a significant industry signal -- even the most handcraft-focused studio is moving to procedural methods

**Key CDPR pattern:** Prefab hierarchy. Buildings are composed of large prefab sections (entire floors or building wings) placed by level designers. The Witcher 3 used similar approaches for villages. For VeilBreakers, this validates our building_interior_binding.py approach of mapping building types to room configurations.

### 1.3 Bethesda -- Skyrim / Starfield Kit System

**Confidence:** HIGH (Joel Burgess GDC 2013, Creation Kit documentation, active modding community)

This is the **most directly applicable system** for VeilBreakers. Bethesda's approach:

**The Kit Concept:**
- A "kit" is a system of simple art pieces designed to snap together
- 7 kits were created by 2 full-time artists
- These 7 kits + level designers = **400+ unique interior cells (dungeons, buildings)**
- Each kit contained **50+ assets** built on a standardized unit scale

**Kit Categories (Skyrim Nordic dungeon example):**

| Sub-Kit | Prefix | Purpose |
|---------|--------|---------|
| Big Rooms | NorRmBg | Large open chambers |
| Small Rooms | NorRmSm | Compact rooms, offices |
| Big Halls | NorHallBg | Wide corridors, galleries |
| Small Halls | NorHallSm | Standard corridors |
| Shafts | NorShaft | Vertical connections |
| Platforms | NorPlat | Elevated areas, balconies |
| Transitions | NorTrans | Connect different sub-kits |

**Naming Convention:**
```
[Kit][SubKit][Variant][Exit][Suffix]
Example: NorHallSm1WayEndExSm01
- Nor      = Nordic kit
- HallSm   = Small Hall sub-kit
- 1Way     = One exit direction
- End      = Dead end piece
- ExSm     = Exit connects to Small pieces
- 01       = Variant number
```

**The Exit System:**
- Every kit piece has labeled **exit points** (snap connectors)
- An exit marked "ExSm" will snap with any other "ExSm" piece in the kit
- This allows corridors, rooms, and transitions to connect freely
- Different exit sizes: ExSm (small), ExBg (big), ExHuge
- Transitions convert between exit sizes

**Interior-Exterior Separation:**
- Bethesda uses **separate cells** for interiors -- they are NOT inside the exterior building shell
- A door trigger loads the interior cell (completely separate geometry)
- This is why Skyrim buildings are often "bigger on the inside"
- For VeilBreakers, our `building_interior_binding.py` already takes a similar approach

**Starfield Extensions:**
- Added **instanced content** -- procedural generation at runtime
- Unique content for static locations vs. instanced content that can be reused
- Modular kits remained the core approach but with runtime assembly

**Key Bethesda pattern:** Kits with standardized exit connectors. Level designers assemble pieces like LEGO. The grammar is implicit in the exit compatibility rules.

### 1.4 FromSoftware -- Dark Souls / Elden Ring

**Confidence:** MEDIUM (design analysis, no official tech talks)

FromSoftware's approach is almost entirely **handcrafted** but follows strict design principles:

**Interconnected Architecture Design Rules:**
1. **"A path that could be reached in a straight line is forcibly made into a circle"** -- the core Souls principle
2. Vertical design: architecture is stacked, making it difficult to orient yourself
3. Shortcut revelation: long paths loop back to earlier areas via unlockable shortcuts
4. Radial exploration pattern: players enter a main area, explore radially, then funnel to a linear boss path

**Castle Design Pattern (Elden Ring):**
1. Enter main plaza (hub)
2. Radial exploration of surrounding buildings (interconnected cluster)
3. Linear path to boss room (funnel)

**For VeilBreakers:** FromSoftware's interconnection patterns are about **graph topology**, not procedural generation. The lesson is that generated buildings should have connection graphs with loops, not just trees. A castle should have shortcut paths that create cycles in the navigation graph.

### 1.5 Embark Studios -- THE FINALS (Houdini Pipeline)

**Confidence:** HIGH (SideFX published case study, GDC presentation)

THE FINALS has the most relevant modern procedural building system:

**Building Creator Tool (Houdini HDA):**
1. **Object-level HDA** orchestrates the pipeline with global parameters (wall thickness, floor height)
2. **Feature Nodes** (SOP-level HDAs) generate specific elements: walls, floors, roofs, windows, doors, rooms
3. Feature nodes are **loosely coupled** and largely order-independent
4. Custom viewport tools for artist control

**Pipeline Steps:**
1. Blockout mesh creation (artist defines proportions/silhouette)
2. Feature node assembly (chain nodes matching desired design)
3. Custom adjustments (viewport state tools, non-destructive)
4. Automatic collision generation (runs at pipeline end)
5. Fracturing (pre-fractured for destruction gameplay)

**Key Technical Constraints:**
- Buildings must be **fully watertight** (no open edges) for fracturing
- **Complete interiors** required -- hallways, staircases, rooms, attics
- Pre-fractured geometry for real-time destruction
- Collision-accurate for FPS gameplay

**Notable Features:**
- **Exterior Walls**: horizontal edge loops per floor, vertical subdivisions
- **Rooms**: input volume meshes generate interior walls at intersections, spaces tagged with identifiers
- **Room Style Node**: applies decor matching room tags
- **Exterior Decals**: automated mesh decals with edge softening and weathering
- **Collision**: custom VEX 2D convex decomposition algorithm

**Production Results:**
- Blockout to fractured asset in **4-6 minutes**
- 100+ unique buildings across THE FINALS and ARC Raiders
- Zero manual collision authoring

**Key Embark pattern:** Blockout-first, then procedural detail layering. Artists control proportions; procedures fill detail. This maps directly to how VeilBreakers should work.

### 1.6 SideFX Project Skylark (2025)

**Confidence:** HIGH (official SideFX release, full tutorial series)

SideFX's official procedural medieval village demo:

- Built by 6-person team using **Houdini 20.5 + Unreal Engine 5**
- Rolling medieval hamlet: houses, props, bridges, rocks, clouds, foliage
- Full UE5 project released (commercial use approved)
- 8 tutorials, 3 hours of content

**Building Generator HDA:**
- Takes artist blockout as input
- Automatically places windows and beams based on blockout shape
- Uses VEX + trigonometry + half-edge operations
- Projects 3D vectors onto 2D planes for facade element placement
- Advanced extrusion techniques for architectural detail

**Additional Tools:**
- Wooden Bridge Tool (spline-based with dynamic stilts, railings, ropes)
- Stylized rocks, props, vegetation
- **Trim sheet** workflow for efficient texturing

**Key Skylark pattern:** HDA takes blockout, outputs detailed building. Same pattern as Building Creator but for stylized medieval aesthetic. Directly applicable to VeilBreakers.

---

## 2. Building Grammar Systems

### 2.1 CGA Shape Grammar (Muller & Wonka, SIGGRAPH 2006)

**Confidence:** HIGH (seminal paper, implemented in CityEngine, widely cited)

The **foundational system** for procedural building generation. CGA = Computer Generated Architecture.

**Core Operations:**

| Operation | Syntax | Effect |
|-----------|--------|--------|
| **Split** | `split(axis) { size : name \| ... }` | Subdivide shape along axis into named parts |
| **Repeat** | `split(axis) { ~size : name }*` | Repeat element to fill available space |
| **Component** | `comp(f) { front : F \| side : S \| top : T }` | Select faces of a shape by orientation |
| **Scale** | `s(x, y, z)` | Resize current shape |
| **Translate** | `t(x, y, z)` | Move current shape |
| **Rotate** | `r(scopeAxis, angle)` | Rotate current shape |
| **Insert** | `i("asset.obj")` | Replace current shape with loaded asset |

**Facade Generation Workflow:**

```
// Step 1: Start with building mass model (box)
Lot --> extrude(height) Building

// Step 2: Decompose into faces
Building --> comp(f) { front: Facade | side: SideFacade | top: Roof }

// Step 3: Split facade into floors
Facade --> split(y) { 4: GroundFloor | ~3.5: UpperFloor }*

// Step 4: Split floors into bays
UpperFloor --> split(x) { 0.5: Wall | ~2: WindowBay | 0.5: Wall }*

// Step 5: Split bays into elements
WindowBay --> split(y) { 0.3: Sill | ~2: Window | 0.5: Lintel }

// Step 6: Insert detailed geometry
Window --> i("gothic_window.obj")
Wall --> i("stone_wall_section.obj")
```

**Key CGA Features:**
- **Tilde operator (~)**: flexible sizing -- `~3.5` means "approximately 3.5, adjust to fill evenly"
- **Scope system**: each shape has its own coordinate system, transformations are local
- **Occlusion queries**: `inside()` and `overlaps()` test against other shapes to prevent conflicts
- **Stochastic rules**: `p(0.3) : Balcony | p(0.7) : Window` for probabilistic variation

**Why CGA matters for VeilBreakers:** Our `_building_grammar.py` already uses a similar approach (BuildingSpec with operation lists) but lacks the **recursive split** mechanism. Adding split/repeat/component operations would make facade generation dramatically more flexible.

### 2.2 Split Grammar for Facades

**Confidence:** HIGH (multiple papers, implemented in CityEngine and academic prototypes)

Split grammar is a specialization of shape grammars focused on facades:

**Hierarchical Decomposition:**
```
Building
  -> Facade (front, sides, back)
    -> Floor (ground, upper, attic)
      -> Bay (wall section between structural elements)
        -> Element (window, door, balcony, blank wall)
          -> Sub-element (frame, glass, sill, lintel, shutter)
```

**Key Rules:**
1. **Symmetry**: facades should be bilaterally symmetric (or nearly so)
2. **Rhythm**: window bays repeat at consistent intervals
3. **Hierarchy**: ground floor is taller and has different elements (doors, shop fronts)
4. **Crown**: top floor has different treatment (dormers, cornices, attic windows)
5. **Base**: ground level has different treatment (rustication, larger stones)

**Inverse Split Grammar (recent 2024-2025):**
Neuro-symbolic learning can automatically derive split grammars from facade images. A segmented facade image is converted to a procedural definition using a split grammar. This enables learning building styles from reference images.

### 2.3 L-System Building Generation

**Confidence:** MEDIUM (academically explored but less common in production)

L-systems can generate building massing models:

```
// Simple tower with branching buttresses
Axiom: F
Rule: F -> F[+F]F[-F]F

// With architectural interpretation:
F = extend wall upward by one story
+ = rotate 30 degrees right  
- = rotate 30 degrees left
[ = push state (start branch)
] = pop state (end branch, return to main)
```

**Practical value:** Limited. L-systems produce interesting organic shapes but lack the **control** needed for architectural facades. Better used for growing vines, tree-like structures, or organic architecture (which maps to VeilBreakers' "organic" style).

### 2.4 Component-Based Assembly (Modular Kit Approach)

**Confidence:** HIGH (industry standard, see Section 4)

The most widely used approach in production:

1. Artists create modular pieces with standardized connection points
2. Grammar rules specify valid combinations
3. Assembly algorithm selects and places pieces

This is what Bethesda, Ubisoft, and Embark all use. See Section 4 for full details.

---

## 3. Interior Generation Best Practices

### 3.1 Room Graph Generation

**Confidence:** HIGH (multiple papers, Bethesda system, Holodeck implementation)

**Room Adjacency Graph:**
```
// Define rooms and required connections
graph = {
    "entrance": connects_to(["hallway"]),
    "hallway": connects_to(["kitchen", "living_room", "staircase"]),
    "kitchen": connects_to(["hallway", "pantry"]),
    "living_room": connects_to(["hallway", "balcony"]),
    "staircase": connects_to(["hallway", "upper_hallway"]),
    "upper_hallway": connects_to(["bedroom_1", "bedroom_2", "bathroom"]),
}
```

**Floor Plan Generation Algorithm (Real-time, from Lopes et al. 2012):**
1. Determine outer building shape (rectangular, L-shape, etc.)
2. Place rooms using **Squarified Treemap** algorithm (fills area proportionally)
3. Create connectivity graph (which rooms MUST connect)
4. Place corridors using shortest-path to link disconnected rooms
5. Place doors at room-corridor junctions
6. Place windows on exterior walls

**Multi-Floor Approach:**
1. Generate staircase/elevator position FIRST on ground floor
2. Duplicate staircase room at same position on every floor above
3. Apply normal room generation around the fixed staircase position
4. This ensures vertical consistency

**Key constraint types:**
- **Adjacency**: "kitchen must be next to dining room"
- **Separation**: "bathroom must NOT open directly to kitchen"
- **Size proportionality**: "living room is 2x bedroom area"
- **Access**: "every room reachable from entrance without passing through private rooms"
- **Light**: "bedrooms should have exterior windows"

### 3.2 Furniture Placement via Constraint Satisfaction

**Confidence:** HIGH (pvigier CSP implementation, academic papers)

**CSP Furniture Placement Algorithm:**

```python
# Variables: each furniture item to place
# Domain: all valid positions (grid cells) for each item
# Constraints: overlap, margin, wall-adjacency, connectivity

def solve(i, assignment):
    if i >= len(furniture_list):
        return True  # All placed successfully
    
    shuffle(domains[i])  # Randomize for variety
    
    for position in domains[i]:
        assignment[i] = position
        if check_all_constraints(i, assignment):
            if solve(i + 1, assignment):
                return True
    
    assignment[i] = None  # Backtrack
    return False
```

**Object Properties:**
- **Collision box**: physical space occupied by furniture
- **Margin box**: surrounding free space needed (e.g., chair needs space to pull out)
- **Anchor requirements**: "against wall", "in corner", "centered in room"
- **Surface hosting**: tables can host cups, shelves can host books

**Constraint Types:**
1. **Overlap prevention**: collision boxes must not intersect
2. **Wall adjacency**: beds, bookcases, desks typically against walls
3. **Connectivity**: all free floor space must remain connected (DFS check)
4. **Functional grouping**: desk + chair together, dining table + chairs
5. **Clearance**: doorways need 1m+ clearance on both sides

**Required vs Optional Objects:**
- Required: must be placed or generation fails (bed in bedroom, forge in smithy)
- Optional: attempt placement without backtracking (decorations, clutter)

**Activity Zone Approach (already in VB toolkit):**
VeilBreakers' `_building_grammar.py` already defines `ROOM_ACTIVITY_ZONES` which partition rooms into functional zones. This maps well to the CSP approach -- zones constrain which furniture goes where.

### 3.3 Exterior-Interior Alignment

**Confidence:** HIGH (THE FINALS system, academic papers)

The **hardest problem** in building generation. Three approaches:

**Approach A: Separate Cells (Bethesda)**
- Interior is completely separate geometry
- Door trigger loads new cell
- No alignment needed -- interior can be any size
- Drawback: buildings can be "bigger on the inside"

**Approach B: Shell-First (THE FINALS)**
- Generate exterior shell with wall thickness
- Room volumes intersect shell interior
- Interior walls generated at room-shell intersections
- Doors/windows must align with both exterior and interior

**Approach C: Grid-Aligned (CGA/Split Grammar)**
- Both exterior and interior share the same grid
- Floors align to exterior floor splits
- Windows on exterior correspond to rooms on interior
- Most visually consistent but most constrained

**For VeilBreakers:** We currently use Approach A (separate interiors via `building_interior_binding.py`). To upgrade:
- Use the building footprint to constrain interior room dimensions
- Align door positions between exterior and interior
- Match window positions to room locations on each floor

### 3.4 Door/Window Alignment Rules

**Confidence:** MEDIUM (synthesized from multiple sources)

**Door Placement Rules:**
1. Doors on exterior walls must align with interior room boundaries
2. Minimum doorway width: 0.9m (already enforced in VB toolkit tests at 0.8m)
3. Minimum doorway height: 2.1m (already enforced in VB toolkit tests at 2.0m)
4. Doors cannot span two rooms -- they must be at room boundary walls
5. Interior doors connect adjacent rooms; exterior doors face streets

**Window Placement Rules:**
1. Windows on exterior walls must correspond to rooms (not to walls between rooms)
2. Window sill height: 0.8-1.0m (allows furniture against wall below)
3. Windows should be centered in their bay, not at edges
4. Bathrooms/storage traditionally have smaller or no windows
5. For multi-floor: window columns should align vertically for visual coherence

### 3.5 Storytelling Through Interior Design

**Confidence:** HIGH (environmental storytelling is well-documented in game design)

**Lived-In Feel:**
- Personal items on surfaces (cups, books, tools)
- Worn paths on floors (darkened wood, polished stone)
- Food/drink remains (plates, mugs, crumbs)
- Clothing/armor on racks or scattered
- Fire in hearth with ash and soot marks

**Abandoned Feel:**
- Overturned furniture
- Dust particles in light beams
- Cobwebs in corners and on surfaces
- Water stains on walls/ceiling
- Vegetation growing through cracks
- Broken windows, collapsed roof sections
- Scattered papers/documents

**Corrupted/Dark Fantasy Feel (VeilBreakers-specific):**
- Organic growths on walls (tentacles, pustules, fungal masses)
- Darkened/stained stone with unnatural patterns
- Ritual circles or occult markings on floors
- Chains, cages, torture implements
- Unnatural light sources (glowing runes, ethereal flames)
- Signs of violent struggle (blood, claw marks, broken weapons)
- Partially consumed remains

**Procedural Approach (VB toolkit already has this):**
The `_STORYTELLING_PROPS` and `add_storytelling_props()` in `_building_grammar.py` already implement layer-3 narrative clutter. The `generate_overrun_variant()` handles corruption/damage narratives.

**Illuminance Requirements by Room Function:**

| Room Type | Lux Range | Light Quality |
|-----------|-----------|---------------|
| Sleeping quarters | 10-30 lx | Warm, dim, single source |
| General rooms | 75-150 lx | Mixed warm sources |
| Gathering halls | 150-220 lx | Multiple sources, even |
| Dining areas | 220-500 lx | Warm, focused on tables |
| Study/workshop | 500-1000 lx | Bright, directional |
| Dungeon/crypt | 5-15 lx | Cold, sparse |
| Chapel/shrine | 30-75 lx | Dramatic, directional |

---

## 4. Modular Kit Approach (Industry Standard)

### 4.1 What a Medieval Building Kit Needs

**Confidence:** HIGH (Skyrim system, Polycount wiki, THE FINALS, Project Skylark)

**Core Piece Set (minimum viable kit):**

| Category | Pieces | Count |
|----------|--------|-------|
| **Walls** | Plain wall, windowed wall, door wall, half wall, arch wall | 5 |
| **Corners** | Outer corner, inner corner, pillar corner | 3 |
| **Floors** | Floor slab, floor with hole (stairs), floor with trapdoor | 3 |
| **Ceilings** | Flat ceiling, vaulted ceiling, exposed beam ceiling | 3 |
| **Roofs** | Ridge, hip, gable end, eave, dormer | 5 |
| **Stairs** | Straight staircase, spiral staircase, ladder | 3 |
| **Doors** | Single door frame, double door frame, archway | 3 |
| **Windows** | Small window, tall window, gothic window, arrow slit | 4 |
| **Structural** | Column, beam, buttress, foundation block | 4 |
| **Trim** | Baseboard, crown molding, floor plank, wainscoting | 4 |
| **Transitions** | Hall-to-room, size adapter, elevation change | 3 |
| **Total** | | **40 core pieces** |

**Per-Style Variants (5 styles in VB toolkit):**
- Medieval: timber frame, plaster, rough stone
- Gothic: pointed arches, tracery, flying buttresses
- Fortress: thick walls, battlements, machicolations
- Organic: irregular shapes, grown stone, root structures
- Ruined: broken variants of above, rubble, collapsed sections

**Total: 40 core x 5 styles = 200 piece variants** (VB toolkit currently claims 175)

### 4.2 Piece Naming Convention

**Recommended for VeilBreakers (adapting Bethesda + industry standards):**

```
{Style}_{Category}_{Type}_{Size}_{Variant}

Examples:
med_wall_plain_2x3_01       # Medieval plain wall, 2m wide x 3m tall, variant 1
goth_wall_window_2x3_01     # Gothic windowed wall
fort_corner_outer_2x3_01    # Fortress outer corner
med_floor_slab_2x2_01       # Medieval floor slab
med_roof_ridge_2x1_01       # Medieval roof ridge piece
med_stair_spiral_2x3_01     # Medieval spiral staircase
med_trans_hall2room_01       # Medieval hall-to-room transition
```

**Size Convention:**
- Width x Height in meters (matching GRID_H=2.0, GRID_V=3.0 from modular_building_kit.py)
- `2x3` = one standard module (2m wide, 3m tall / one floor)
- `4x3` = double-width module
- `2x6` = two-floor module

### 4.3 Snap Point System

**Confidence:** HIGH (Bethesda exit system, industry standard)

```python
# Each piece defines snap points at its edges
SnapPoint = {
    "position": (x, y, z),      # Local coordinates
    "direction": (nx, ny, nz),   # Outward normal
    "type": "wall_edge",         # Compatibility type
    "size": "standard",          # Must match connecting piece
}

# Compatibility rules:
# - wall_edge connects to wall_edge
# - floor_edge connects to floor_edge  
# - door_opening connects to door_opening
# - stair_top connects to floor_edge
# - stair_bottom connects to floor_edge (level below)
```

**Grid Alignment:**
- Horizontal grid: 2m (from VB toolkit GRID_H)
- Vertical grid: 3m per floor (from VB toolkit GRID_V)
- Snap tolerance: 0.01m
- Wall thickness: 0.3-0.5m (style-dependent, from VB toolkit _STYLE_THICKNESS)

### 4.4 Corner and Junction Handling

**Confidence:** HIGH (Polycount wiki, THE FINALS system)

**Corner Types:**
1. **Outer corner (convex)**: two walls meet at exterior angle (90 degrees for most buildings)
2. **Inner corner (concave)**: two walls meet at interior angle
3. **T-junction**: wall meets perpendicular wall mid-span
4. **End cap**: wall terminates without connecting to another wall

**SideFX Labs Building Generator approach:**
- Separate corner modules for convex and concave corners
- "Sideslop" modules fill gaps between wall and corner modules
- Corners are special pieces, not just rotated walls

**Critical rule:** Corners must have proper **thickness on both axes**. A common mistake is making corners that are thin on one side, creating visible seams or z-fighting.

### 4.5 Material Variation Within a Kit

**Confidence:** HIGH (trim sheet workflow, industry practice)

**Three-Level Variation System:**

1. **Base material variation**: Same geometry, different material assignment
   - Pristine stone, weathered stone, mossy stone, blood-stained stone
   
2. **Geometry variation**: Different vertex positions, same topology
   - Variant 01: standard, Variant 02: slightly different stone pattern
   - 2-3 variants per piece prevents obvious repetition
   
3. **Overlay variation**: Decals and secondary materials
   - Moss patches, water stains, damage marks, graffiti
   - Applied as separate mesh layer or texture blend

**VeilBreakers already has:** `weathering.py` for procedural wear, `_STYLE_JITTER` for per-vertex variation

### 4.6 LOD Strategy for Modular Buildings

**Confidence:** HIGH (Unity documentation, standard practice)

| LOD Level | Distance | Tri Budget per Wall | Technique |
|-----------|----------|---------------------|-----------|
| LOD0 | 0-20m | 250-500 tris | Full detail |
| LOD1 | 20-50m | 50-100 tris | Simplified geometry |
| LOD2 | 50-100m | 10-25 tris | Billboard/flat planes |
| LOD3 | 100m+ | HLOD cluster | Merged into city mesh |

**HLOD (Hierarchical LOD):**
- At distance, groups of buildings merge into single simplified meshes
- Reduces draw calls from hundreds (individual pieces) to single digits
- Critical for VeilBreakers settlements with many buildings

**Instancing Strategy:**
- GPU instancing for identical pieces at same LOD level
- Different LOD levels do NOT batch with each other
- Static batching for pieces sharing materials
- Group similar meshes into combined meshes at bake time

### 4.7 Preventing Repetitive-Looking Buildings

**Confidence:** HIGH (industry best practices)

**Strategies:**
1. **Color variation**: Randomize tint per building (warm/cool shift, brightness)
2. **Module permutation**: Different window/door combinations per floor
3. **Height variation**: Vary floor count (2-4 floors from same kit)
4. **Width variation**: Vary bay count (2-5 bays)
5. **Roof variation**: Swap between roof types (hip, gable, flat)
6. **Age/wear variation**: Random weathering intensity per building
7. **Prop variation**: Different signs, hanging items, window boxes
8. **Asymmetric facades**: Not every bay needs the same window type
9. **Corner buildings**: L-shaped buildings at street corners add variety

**The 80/20 Rule:** 80% of variation comes from **proportion changes** (height, width, roof type). Only 20% comes from detail changes (window style, material variation). Prioritize proportion variation.

### 4.8 Trim Sheets and Texture Atlases

**Confidence:** HIGH (Beyond Extent deep dive, Frozenbyte wiki, Polycount)

**Trim Sheet Definition:**
A texture that tiles in ONE direction (U or V) containing multiple material strips. One trim sheet can texture 12+ modular pieces instead of requiring individual textures per piece.

**Trim Sheet Workflow:**
1. Create high-poly detail strips (stone block patterns, wood planks, metal bands)
2. Bake to flat plane with 0-1 UV coverage
3. Use fixed pixel heights for strips: 512, 256, 128, 64, 32, 16 px
4. UV-map modular pieces to align with strips

**UV Mapping for Trim Sheets:**
- UVs extend BEYOND 0-1 space (the texture tiles in one direction)
- UVs overlap between different pieces (they share the same trim)
- Create long rectangular UV shells aligned to trim direction
- Straighten UV shells for clean alignment

**Atlas Hybrid Trim Sheet:**
Combines tiling strips with unique non-tiling elements (hinges, brackets, unique details). Best of both worlds.

**Recommended Trim Sheets for Medieval Kit:**

| Trim Sheet | Resolution | Contents |
|------------|------------|----------|
| stone_wall_trim | 2048x2048 | Stone block patterns, mortar, rough stone |
| wood_trim | 2048x2048 | Planks, beams, rough timber, polished |
| metal_trim | 1024x1024 | Iron bands, rivets, hinges, chains |
| roof_trim | 2048x2048 | Shingles, tiles, thatch, slate |
| detail_atlas | 2048x2048 | Windows, doors, signs, decorative elements |

---

## 5. Gothic & Dark Fantasy Architecture Rules

### 5.1 Gothic Architecture Structural Rules

**Confidence:** HIGH (architectural references, Wikipedia, Britannica)

**Pointed Arch:**
- Formed by intersection of two circular arcs
- The two centers can be adjusted to create wider or narrower arches
- **Equilateral arch**: centers at spring points, radius = span width (most common)
- **Lancet arch**: centers outside spring points, steeper angle (Early Gothic)
- **Four-centred arch**: two pairs of centers create flatter, wider opening (Late Gothic)

**Proportional Rules:**
```
// Window proportions (height:width ratios)
Lancet window:     3:1 to 4:1
Standard pointed:  2:1 to 3:1
Decorated style:   2:1 with tracery filling upper portion
Perpendicular:     1.5:1 to 2:1, very wide with panel tracery

// Structural bay proportions
Bay width:         3-5m (between buttresses)
Bay height:        varies by order (arcade, triforium, clerestory)
Buttress depth:    1/3 to 1/2 of wall height
```

**Tracery Types (window subdivisions):**
1. **Plate tracery** (Early Gothic): holes punched in solid stone slab
2. **Bar tracery** (High Gothic): stone mullions branch into curves
3. **Geometric tracery**: circles and arcs
4. **Flowing/curvilinear tracery**: S-curves and ogee arches (Decorated)
5. **Panel/perpendicular tracery**: straight vertical mullions to arch top

**Buttress Placement:**
- Buttresses align with structural bays (one per bay)
- Flying buttresses transfer thrust from vaults to outer supports
- Pinnacles weight buttress tops to redirect thrust downward
- Buttress depth approximately 1/3 of wall height

**For VeilBreakers:** `building_quality.py` already has `generate_gothic_window()` with tracery and voussoirs. The proportional rules above should inform the split grammar parameters.

### 5.2 Dark Fantasy Architectural Modifications

**Confidence:** MEDIUM (design analysis, VeilBreakers project context)

Gothic architecture provides the base. Dark fantasy modifies it:

**Scale Distortion:**
- Walls taller and thicker than structurally necessary (oppressive feel)
- Doorways sized for larger-than-human creatures
- Windows narrower and deeper (fortress + cathedral hybrid)
- Stairs steeper and narrower (defensible, claustrophobic)

**Material Corruption:**
- Stone surfaces show unnatural erosion patterns
- Metal corroded with unusual colors (green-black, rust-red)
- Wood warped and darkened beyond natural aging
- Organic growths where none should survive

**Structural Impossibility:**
- Architecture that shouldn't stand (partially collapsed yet still functional)
- Impossible geometry hints (slight non-Euclidean distortion)
- Bridges and arches that defy physics
- Roots and organic matter integrated into stone as structural elements

---

## 6. Open Source Tools & Implementations

### 6.1 GitHub Projects

**Confidence:** MEDIUM (existence verified, quality varies)

| Project | Language | Purpose | Stars | Notes |
|---------|----------|---------|-------|-------|
| mxgmn/WaveFunctionCollapse | C# | Reference WFC implementation | 23K+ | The original, bitmap + tilemap |
| lsimic/ProceduralBuildingGenerator | Python/Blender | Blender building addon | Small | Procedural building generation |
| wojtryb/Procedural-Building-Generator | Python | Floor plan generator (master thesis) | Small | Grid placement + squarified treemaps |
| eliemichel/TownBuilder | C++ | Townscaper reproduction | Medium | WFC + irregular grids |
| zfedoran/go-wfc | Go | WFC tile maps | Small | Stalberg-style WFC |
| sharpaccent/Procedural-Dungeon-Generator | C# | Dungeon with spanning tree | Medium | Connected paths |

### 6.2 Commercial Tools & Plugins

| Tool | Platform | Type | Cost | Notes |
|------|----------|------|------|-------|
| SkyscrapX | Blender | Building generator addon | Paid | Three-click workflow, game-dev focused |
| SceneCity | Blender | City generator | Paid | Road networks + mass building placement |
| Dungeon Architect | Unity/UE | Level generator | Paid | Node-based dungeon layout |
| CityEngine (Esri) | Standalone | CGA grammar city generation | Commercial | The CGA reference implementation |
| SideFX Labs Building Generator | Houdini | Free building HDA | Free (with Houdini) | Version 4.0, blockout to detail |
| Project Skylark | Houdini+UE5 | Medieval village demo | Free | Full project with tutorials |

### 6.3 WFC for Architecture

**Confidence:** HIGH (Townscaper shipped, academic papers)

**How WFC Works for Buildings:**
1. Define a **tile set** of architectural modules (wall sections, corners, windows, etc.)
2. Define **adjacency rules**: which tiles can be next to which tiles
3. Start with all possibilities at every grid cell
4. Pick cell with lowest entropy (fewest possibilities)
5. Collapse it to one tile (random weighted selection)
6. Propagate constraints to neighbors (remove incompatible options)
7. Repeat until all cells resolved or contradiction found
8. On contradiction: backtrack or restart

**Townscaper's WFC Innovation:**
- Uses **irregular grids** instead of standard voxel grids
- Combines WFC with **Marching Cubes** for smooth geometry
- Focus on **transitions** (corners, edges, material boundaries) not uniform surfaces
- Players provide the high-level structure; WFC resolves the detail

**WFC for VeilBreakers facades:**
- Define tile set: wall section, window section, door section, balcony, blank
- Per-floor adjacency rules: ground floor allows doors, upper floors don't
- Per-bay adjacency rules: windows don't appear at corners
- Weight by style: gothic style weights pointed windows higher
- Result: varied facades that respect architectural rules

**Performance Note:** WFC is NOT fast. Processing should happen at generation time (in Blender), not at runtime. For a single facade (10x4 grid = 40 cells), WFC resolves in milliseconds. For an entire city block, seconds to minutes.

---

## 7. Application to VeilBreakers Toolkit

### 7.1 Existing Toolkit Assets

The VB toolkit already has significant building generation infrastructure:

| File | What It Does | Gap |
|------|-------------|-----|
| `_building_grammar.py` | Style configs, BuildingSpec, specialized templates | Lacks recursive split grammar |
| `modular_building_kit.py` | 175 piece variants, 5 styles, 2m/3m grid | Pieces exist but assembly intelligence is basic |
| `building_quality.py` | AAA generators (stone wall, timber, gothic window, roof, stairs, battlements) | Individual pieces are good; composition is missing |
| `building_interior_binding.py` | Building-to-room mapping, spatial alignment, style propagation | Good foundation; needs CSP furniture placement |
| `worldbuilding_layout.py` | Settlement layout with building placement | Connects buildings to settlements |

### 7.2 Recommended Architecture

**Layer 1 -- Mass Model:**
```python
# Input: lot polygon, building type, floor count, style
# Output: blockout volume (simple extruded box or L-shape)
def generate_mass_model(lot, building_type, floors, style):
    footprint = fit_to_lot(lot, building_type)
    volume = extrude(footprint, floors * GRID_V)
    return volume
```

**Layer 2 -- Facade Split Grammar:**
```python
# Input: mass model faces, style rules
# Output: hierarchical face decomposition with piece assignments
def apply_split_grammar(faces, style):
    for face in faces:
        floors = split_vertical(face, ground_height=4, floor_height=3.5)
        for floor in floors:
            bays = split_horizontal(floor, bay_width=2.0)
            for bay in bays:
                piece = select_piece(bay, style, floor_type)
                # piece references modular_building_kit piece
```

**Layer 3 -- Interior Layout:**
```python
# Input: building footprint, building type, floor count
# Output: room graph with positions and sizes
def generate_interior(footprint, building_type, floors):
    rooms = BUILDING_ROOM_MAP[building_type]  # already exists
    staircase = place_staircase(footprint)  # fix position first
    for floor in range(floors):
        floor_rooms = [r for r in rooms if r["floor"] == floor]
        layout = csp_place_rooms(footprint, floor_rooms, staircase)
        furniture = csp_place_furniture(layout)
```

**Layer 4 -- Detail & Storytelling:**
```python
# Input: rooms with furniture, narrative state
# Output: decorated rooms with storytelling props
def apply_narrative_decoration(rooms, state):
    for room in rooms:
        if state == "lived_in":
            add_storytelling_props(room, "occupied")
        elif state == "abandoned":
            add_storytelling_props(room, "abandoned")
        elif state == "corrupted":
            generate_overrun_variant(room)
```

### 7.3 Critical Implementation Priorities

1. **Split grammar engine for facades** -- this is the single biggest missing piece. Convert the current list-of-operations approach in `_building_grammar.py` to a recursive split/repeat/component system.

2. **CSP room layout solver** -- upgrade `building_interior_binding.py` from fixed size_ratio placements to constraint-satisfaction room layout within the building footprint.

3. **Snap connector system** -- formalize the connection point system in `modular_building_kit.py` so pieces know how to connect to each other (Bethesda exit system).

4. **Exterior-interior alignment** -- ensure generated windows and doors on the facade correspond to actual room positions inside.

5. **HLOD and instancing pipeline** -- critical for settlements with 50+ buildings.

---

## 8. Sources

### Primary (HIGH confidence)

**GDC Talks & Official Studios:**
- [Joel Burgess: Skyrim's Modular Level Design (GDC 2013)](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html)
- [GDC Vault: Building Night City (Cyberpunk 2077)](https://www.gdcvault.com/play/1028734/Building-Night-City-The-Technology)
- [GDC Vault: AC Syndicate - London](https://www.gdcvault.com/play/1023305/-Assassin-s-Creed-Syndicate)
- [GDC Vault: AC Odyssey - Building a Living World](https://gdcvault.com/play/1025769/Building-a-Living-World-from)
- [GDC Vault: THE FINALS Destruction Deep-Dive](https://gdcvault.com/play/1034307/Engineering-Mayhem-Technical-Deep-Dive)

**SideFX / Houdini:**
- [SideFX Labs Building Generator 4.0 Documentation](https://www.sidefx.com/docs/houdini/nodes/sop/labs--building_generator-4.0.html)
- [Making Procedural Buildings of THE FINALS (SideFX)](https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/)
- [Project Skylark Building Generator Tutorial](https://www.sidefx.com/tutorials/project-skylark-building-generator/)
- [Project Skylark Full Project](https://www.sidefx.com/learn-main-menu/tech-demos/project-skylark/)
- [SideFX Procedural Bridge Tool](https://digitalproduction.com/2025/05/07/sidefx-extends-houdini-labs-free-procedural-bridge-tool-arrives/)

**Academic Papers:**
- [Muller & Wonka: Procedural Modeling of Buildings (SIGGRAPH 2006)](https://dl.acm.org/doi/10.1145/1141911.1141931) -- CGA Shape Grammar
- [Parish & Muller: Procedural Modeling of Cities (2001)](https://www.researchgate.net/publication/220183823_Procedural_Modeling_of_Buildings) -- L-system roads
- [Lopes et al: Real-time Procedural Generation of Building Floor Plans (2012)](https://ar5iv.labs.arxiv.org/html/1211.5842)
- [pvigier: Room Generation using Constraint Satisfaction](https://pvigier.github.io/2022/11/05/room-generation-using-constraint-satisfaction.html)
- [WFC for Buildings (HAW Hamburg thesis)](https://reposit.haw-hamburg.de/bitstream/20.500.12738/15709/1/BA_Procedural%20Generation%20of%20Buildings_geschw%C3%A4rzt.pdf)
- [Constrained Growth Method for Floor Plan Generation (TU Delft)](https://graphics.tudelft.nl/~rafa/myPapers/bidarra.GAMEON10.pdf)
- [Pro-DG: Procedural Diffusion for Facade Generation (2025)](https://arxiv.org/html/2504.01571v1)

### Secondary (MEDIUM confidence)

**Game Developer / 80.lv Articles:**
- [How Townscaper Works (Game Developer)](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making)
- [Building Huge Open Worlds: Modularity (80.lv)](https://80.lv/articles/building-huge-open-worlds-modularity-kits-art-fatigue)
- [THE FINALS Procedural Buildings (80.lv)](https://80.lv/articles/how-embark-studios-built-procedural-environments-for-the-finals-using-houdini)
- [Modular Kit Design (Level Design Book)](https://book.leveldesignbook.com/process/blockout/metrics/modular)
- [Polycount Modular Environments Wiki](http://wiki.polycount.com/wiki/Modular_environments)

**Trim Sheets & Texturing:**
- [Beyond Extent: Trimsheets Deep Dive](https://www.beyondextent.com/deep-dives/trimsheets)
- [Frozenbyte: Tile Textures and Trimsheets](https://wiki.frozenbyte.com/index.php/3D_Asset_Workflow:_Tile_Textures_and_Trimsheets)
- [War Robots: Trim Sheets, Tilemaps and Terrain](https://medium.com/my-games-company/trim-sheets-tilemaps-and-terrain-how-we-remaster-game-maps-6dc35dde06f8)

**Environmental Storytelling:**
- [Environmental Storytelling in Video Games (Game Design Skills)](https://gamedesignskills.com/game-design/environmental-storytelling/)
- [When Buildings Dream: Horror Game Design](https://drwedge.uk/2025/05/04/when-buildings-dream-horror-game-design/)

**Open Source:**
- [mxgmn/WaveFunctionCollapse (GitHub)](https://github.com/mxgmn/WaveFunctionCollapse)
- [lsimic/ProceduralBuildingGenerator (GitHub)](https://github.com/lsimic/ProceduralBuildingGenerator)
- [wojtryb/Procedural-Building-Generator (GitHub)](https://github.com/wojtryb/Procedural-Building-Generator)
- [eliemichel/TownBuilder (GitHub)](https://github.com/eliemichel/TownBuilder)
- [SkyscrapX Blender Addon](https://baogames.itch.io/skyscrapx)

### Tertiary (LOW confidence -- needs validation)

- FromSoftware level design analysis is from community analysis, not official docs
- Gothic architecture proportional rules synthesized from multiple references (no single authoritative procedural source)
- Cyberpunk 2 procedural generation claims based on early reports, no technical details yet

---

## Metadata

**Research date:** 2026-04-02
**Confidence breakdown:**
- AAA studio approaches: HIGH (GDC talks, official documentation, case studies)
- Building grammar systems: HIGH (academic papers, CityEngine implementation)
- Interior generation: HIGH (CSP paper, Bethesda system, existing VB toolkit)
- Modular kit approach: HIGH (industry standard, multiple sources)
- Gothic architecture rules: MEDIUM-HIGH (architectural references, some synthesis)
- Open source tools: MEDIUM (existence verified, quality/applicability varies)
- Dark fantasy modifications: MEDIUM (design analysis, no formal study)

**Valid until:** 2026-07-02 (stable domain, 90-day validity)
