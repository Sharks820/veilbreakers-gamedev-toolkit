# Visual Quality Overhaul — The Path From Placeholder to AAA

## Current State: UNUSABLE
- Characters: 320 vertices (AAA needs 50,000+) — **150x too simple**
- Buildings: sealed boxes, no openings, no detail, no textures
- Materials: flat single-color PBR, no noise, no bump, no variation
- Textures: blank white images created but never filled
- Animation topology: zero edge loops, will tear at joints
- LODs: nonexistent

## The AAA Standard (from research)
- **Elden Ring/Skyrim/Witcher 3**: modular kit approach (20-270 snap-together pieces per style)
- **Houdini**: shape grammar → subdivide facade → scatter detail components
- **Substance Designer**: layered noise nodes (Perlin + Voronoi + Slope Blur + Curvature masks)
- **Poly budgets**: small prop 2.5-5K tris, building 10-15K tris, character 40-60K tris
- **Every asset has**: normal map, roughness variation, AO, 3-4 LOD levels

---

## Phase 1: BUILDINGS (Week 1) — The Most Visible Fix

### 1A. Modular Kit System (replaces _building_grammar.py)
Create 25-30 snap-together pieces per architectural style:
- **Walls**: solid, window, door, damaged, half-height, corner (inside/outside)
- **Floors**: stone slab, wooden plank, dirt
- **Roofs**: peak, slope, flat, gutter, dormer
- **Trim**: cornice, sill, lintel, column, buttress
- **Doors**: single, double, arched (with frame geometry)
- **Windows**: small, large, pointed arch, round, broken
- **Stairs**: straight, spiral, ramp

Each piece:
- Has wall THICKNESS (0.3-0.5m)
- Snaps on a grid (2m x 3m wall sections)
- Has proper UVs for tiling textures
- Gets per-vertex jitter for imperfection
- 250-500 tris per wall section (matches AAA budget)

### 1B. Procedural Material Nodes (replaces flat PBR)
For EACH material type, create Blender shader node graphs:

**Stone Wall:**
```
Noise Texture (scale 15) → Color Ramp (mortar lines)
Voronoi Texture (scale 8) → Bump Node (block edges)
Musgrave Texture → Mix with base color (surface variation)
Ambient Occlusion → Multiply into roughness
```

**Wood:**
```
Wave Texture (bands) → Color Ramp (grain pattern)
Noise Texture (detail) → Mix overlay for knots
Bump Node from wave → Normal input
```

**Roof Slate:**
```
Brick Texture (offset 0.5) → shape mask
Noise per-brick → color variation
Edge detection → roughness variation
```

**Metal/Iron:**
```
Noise Texture (large scale) → rust pattern mask
Mix Shader: clean metal (low rough, high metal) + rust (high rough, low metal)
Scratches via fine noise → roughness detail
```

### 1C. Auto Scene Setup
Every generation auto-creates:
- HDRI world environment or 3-point lighting
- Ground plane with material
- Camera at good viewing angle
- EEVEE with bloom + AO enabled

### 1D. Weathering System
Per-vertex color painting after generation:
- Edge wear mask from curvature analysis (dirty/worn edges)
- AO from mesh concavities
- Moss/dirt at base (Y-position gradient)
- Rain staining (top-down gradient on walls)

---

## Phase 2: CHARACTERS/MONSTERS (Week 2)

### 2A. Topology-Correct Base Meshes
Instead of stacking cylinders, use subdivision surface modeling:
- Start with low-poly cage (500-800 verts) with proper edge loops
- Subdivision surface modifier (level 2-3) for smooth result
- Edge loops at: shoulders, elbows, wrists, hips, knees, ankles, neck
- Quad-dominant topology for deformation
- Mirror modifier for symmetry

### 2B. Monster Body Type Templates
For each of the 20 VB monsters, create body templates:
- **Humanoid** (Chainbound, Corrodex, Crackling, Hollow, The Bulwark, Voltgeist, Bloodshade, The Vessel):
  - Base mesh: 2,000-5,000 verts with edge loops
  - Variants via shape keys (bulk, height, limb length)

- **Quadruped** (Grimthorn, Ironjaw, Mawling, Ravener, Sporecaller):
  - 4-leg topology with spine flexibility
  - Tail as separate chain

- **Amorphous** (Gluttony Polyp, The Congregation, The Weeping):
  - Metaball-based generation → convert to mesh
  - Smooth subdivision for organic look

- **Arachnid** (Skitter-Teeth, The Broodmother):
  - Segmented body with 8-leg topology
  - Proper joint deformation points

- **Serpent** (Needlefang):
  - Spine chain with scale pattern
  - Hood geometry for cobra-like display

- **Insect** (Flicker):
  - Wing membrane as separate thin mesh
  - Compound eye detail via spherical projection

### 2C. Brand-Specific Visual Features
Each monster's key_features from vb_game_data.py become actual geometry:
- Chains (IRON): torus-chain generator along bones
- Vines/thorns (SAVAGE): curve-based vine growth along surface
- Lightning veins (SURGE): edge-detected emission pattern
- Shadow tendrils (VOID): extruded dark geometry

### 2D. Per-Monster Textures
Use the blender_texture bake pipeline:
- Sculpt detail on high-poly → bake normal map to game mesh
- Curvature → edge wear mask
- AO bake for depth
- Brand color as base, variations via noise

---

## Phase 3: WEAPONS/ITEMS (Week 2-3)

### 3A. Weapon Detail
Current weapons are ~90 verts. Need 2,000-5,000 for close-up:
- Blade: proper edge bevel (not flat face), fuller groove, blood channel
- Guard: cross-guard geometry, decorative elements
- Grip: wrapped leather/cord pattern (cylindrical UV + texture)
- Pommel: geometric ornament

### 3B. Equipment/Armor
- Plate segments with overlap
- Rivet/stud detail (small cylinders)
- Trim/edging as separate geometry
- Cloth/leather parts with thickness
- Straps and buckles

### 3C. Small Items
- Potions: glass bottle with liquid (inner surface)
- Keys: teeth pattern
- Books: page edges, cover detail
- Scrolls: rolled cylinder with ribbon

---

## Phase 4: TERRAIN/MAP VISUAL QUALITY (Week 3)

### 4A. Terrain Materials
- Multi-material blending via vertex painting
- Grass/dirt/rock/snow transitions based on slope + height
- Cliff faces with proper normal maps
- River beds with pebble detail

### 4B. Vegetation Quality
- Trees: proper branch structure (not cylinders with sphere canopy)
- Grass: billboard quads with alpha-tested texture
- Bushes: branch structure with leaf cards
- Flowers: petal geometry

### 4C. Water
- Transparent material with Fresnel
- Flow direction via UV animation
- Shore foam via distance gradient
- Depth-based color tinting

### 4D. Roads
- Actual carved geometry into terrain (not painted overlay)
- Cobblestone normal map
- Dirt path with rut detail
- Road edges with grass encroachment

---

## Phase 5: VIEWING/ITERATION PIPELINE (Ongoing)

### 5A. Auto Beauty Setup
Every screenshot/contact_sheet should auto-setup:
- Material preview shading (not Solid)
- HDRI environment lighting
- Proper camera distance (fit object to frame)
- AO enabled in viewport

### 5B. Quality Verification Checklist
After every generation, automatically check:
- [ ] Mesh has >500 verts (not a primitive box)
- [ ] Materials assigned with textures (not blank)
- [ ] No overlapping/intersecting geometry
- [ ] UVs present and unwrapped
- [ ] Door/window openings are actual holes (not overlaid boxes)
- [ ] Topology grade B or above
- [ ] Screenshot in Material Preview mode looks acceptable

### 5C. Iterative Refinement Workflow
```
Generate → Screenshot → Identify issues → Edit (move/sculpt/modify) → Screenshot → Repeat
```
The toolkit must support rapid iteration, not just one-shot generation.

---

## Success Criteria
A generated building should:
1. Have a real door you can walk through
2. Have windows that are actual holes in the walls
3. Have thick walls (not paper-thin faces)
4. Have dark fantasy materials that look like stone/wood/metal
5. Have bump/normal detail visible in material preview
6. Have roof with overhang and visible structure
7. Have interior space with floor
8. Look like it belongs in Elden Ring or Skyrim, not Minecraft

A generated character should:
1. Have proper proportions matching its monster type
2. Have brand-specific visual features (chains, vines, lightning, etc.)
3. Have topology that supports animation (edge loops at joints)
4. Have textured skin/surface (not flat gray)
5. Have enough detail to hold up at game-camera distance
6. Be riggable with the existing rig templates

---

---

## Phase 6: MISSING ASSET CATEGORIES (Week 3-4)

### 6A. NPCs / Human Characters
- Player heroes (Vex, Seraphina, Orion, Nyx) need full character meshes
- Body proportions per hero (Vex=heavy tank, Seraphina=lithe assassin, Orion=robed mage, Nyx=shadowy hybrid)
- Face geometry: nose, mouth, eyes, ears — not a smooth sphere
- Hair: card-based hair strips with alpha transparency
- Clothing as separate meshes layered over body (for equipment swapping)
- Each hero needs 3-4 outfit variants matching their Path

### 6B. Animals / Wildlife (non-monster)
- Deer, wolves, birds, rats, snakes for ambient world life
- Simple topology (2-5K tris) — background creatures, not hero assets
- Walk/idle animations needed
- Biome-appropriate (forest animals vs mountain vs swamp)

### 6C. Furniture & Interior Props (DETAILED)
Current generators make 80-vert placeholders. Need:
- Tables: 500+ tris with plank detail, worn edges, nail heads
- Chairs: proper joint detail, cushion if applicable
- Beds: frame + mattress + pillow + blanket as separate geometry
- Bookshelves: individual book spines visible
- Fireplaces: stone surround, mantel, fire cradle, ash
- Chandeliers: arms, candle holders, chains
- Rugs: flat mesh with fringe edge detail and pattern UV
- Curtains: cloth-sim-ready geometry with rings

### 6D. Shields
- Separate from armor system
- Round, kite, tower variants
- Boss/emblem geometry on face
- Strap/handle geometry on back
- Edge damage/dent deformation
- Brand-specific decorations (IRON=riveted steel, SAVAGE=bone/hide, etc.)

### 6E. Crafting Stations
- Forge: anvil + bellows + furnace + chimney + tool rack
- Alchemy table: mortar/pestle + bottles + bubbling cauldron
- Workbench: wood surface + vice + tools + blueprints
- Enchanting altar: runic circle + crystal focus + candles
- Each station is a composed scene, not a single mesh

### 6F. Interactive Objects
- Doors that swing (hinge point defined, animation-ready)
- Chests that open (lid as separate piece with pivot)
- Levers/switches (handle geometry with rotation axis)
- Breakable crates/barrels (pre-fractured pieces)
- Lootable containers (glow highlight material)

### 6G. Flags / Banners / Cloth
- Cloth-sim-ready flat meshes with proper vertex density
- Brand-specific heraldry UV mapped
- Attachment points (rope/chain/pole mount)
- Torn/damaged variants with edge alpha

### 6H. Signs / Waymarkers
- Wooden signpost with carved text (text-to-mesh)
- Stone waymarker with runic inscriptions
- Warning signs (skull icon, danger markers)
- Direction arrows

### 6I. Lighting Fixtures (3D objects)
- Wall torches with bracket geometry + flame particle emitter point
- Standing braziers with coal bed
- Hanging lanterns with chain + glass housing
- Campfire with log arrangement + stone ring
- Crystal light sources (for shrines/magic areas)
- Each fixture defines: light position, light color, light range, flicker speed

### 6J. Bridges / Gates / Fortifications
- Drawbridge with chain mechanism
- Stone bridge with arch support + railing
- Rope bridge with plank + rope geometry
- Portcullis (iron grid that raises/lowers)
- Palisade wall sections (pointed logs)
- Watchtower (multi-level with ladder access)

### 6K. Mounts (Future)
- Horse base mesh with saddle/bridle equipment slots
- Monster mounts (rideable creatures from capture system)
- Mount armor as separate mesh layer

---

## Phase 7: TECHNICAL PIPELINE QUALITY (Ongoing)

### 7A. Texture Baking Pipeline
- Sculpt high-poly detail → bake normal map to game mesh
- AO bake from mesh concavities
- Curvature map for edge wear masking
- Thickness map for subsurface scattering
- All bakes to 2K or 4K resolution

### 7B. UV Quality
- Smart UV project as baseline
- Manual seam correction for visible assets
- Texel density equalization (no stretching)
- UV2 for lightmaps (Unity requirement)
- Padding ≥4px for mipmap safety

### 7C. LOD Pipeline
- LOD0: full detail (hero distance)
- LOD1: 50% tris (medium distance)
- LOD2: 25% tris (far distance)
- LOD3: 12% tris or billboard (background)
- Silhouette-preserving decimation (not uniform)
- Auto-LOD generation after mesh finalization

### 7D. Collision Meshes
- Simplified convex hull for physics
- Walkable floor detection
- Door/window pass-through zones
- Stairs as ramp collider

### 7E. Vertex Color Data
- Channel R: AO (ambient occlusion)
- Channel G: Curvature (edge wear mask)
- Channel B: Height gradient (moss/dirt at base)
- Channel A: Wetness/damage mask
- Painted automatically after mesh generation

### 7F. Edge Wear / Weathering Pipeline
- Analyze mesh curvature (pointiness)
- Worn edges = higher roughness + slightly lighter color
- Crevices = darker + lower roughness (moisture/dirt)
- Base-to-top gradient for moss/dirt accumulation
- Rain staining on vertical surfaces (top-down streaks)
- Random vertex displacement for structural settling

### 7G. Art Style Consistency Rules
- Same biome = same material palette (max 7 textures per district, Witcher 3 approach)
- Color temperature: warm for safe areas, cold for dangerous
- Saturation: lower in corrupted areas, higher in pure/ascended
- Corruption level affects: darkness, purple tint, vein overlay intensity
- VB brand colors from BrandSystem.cs must be used consistently

---

## COMPLETE ASSET CHECKLIST FOR VEILBREAKERS RPG

### Architecture (25+ modular pieces per style × 5 styles)
- [ ] Gothic (shrines, cathedrals)
- [ ] Medieval (houses, taverns, shops)
- [ ] Fortress (walls, towers, barracks)
- [ ] Organic (tree-homes, root structures, mushroom houses)
- [ ] Ruined (damaged variants of all above)

### Characters (mesh + rig + texture each)
- [ ] Vex (IRONBOUND tank)
- [ ] Seraphina (FANGBORN assassin)
- [ ] Orion (VOIDTOUCHED mage)
- [ ] Nyx (UNCHAINED hybrid)
- [ ] Generic NPCs (merchant, guard, villager, priest)

### Monsters (20 unique meshes)
- [ ] All 20 from vb_game_data.py with brand-specific features
- [ ] 3 size variants each (young/adult/elder)
- [ ] Corruption visual variants (5 tiers)

### Weapons (per type × brand variants)
- [ ] Swords (straight, curved, greatsword)
- [ ] Axes (hand axe, battle axe, greataxe)
- [ ] Maces/hammers (club, mace, warhammer)
- [ ] Spears/polearms
- [ ] Daggers/knives
- [ ] Staves/wands (magic weapons)
- [ ] Bows/crossbows
- [ ] Shields (round, kite, tower)

### Armor (per slot × style variants)
- [ ] Helmets (open face, full helm, hood, crown)
- [ ] Chest (plate, leather, robes, chain)
- [ ] Gauntlets (plate, leather, wraps)
- [ ] Boots/greaves (plate, leather, sandals)
- [ ] Shoulders/pauldrons
- [ ] Capes/cloaks (cloth-sim ready)

### Items
- [ ] Potions (health, mana, antidote, buff)
- [ ] Capture devices (per-brand visual)
- [ ] Keys/lockpicks
- [ ] Books/scrolls/maps
- [ ] Food/cooking ingredients
- [ ] Crafting materials (ore, leather, herbs, gems)
- [ ] Currency (gold coins, brand tokens)

### Environment
- [ ] Trees (3+ species per biome)
- [ ] Rocks (boulder, standing stone, rubble)
- [ ] Grass/flowers (billboard cards)
- [ ] Bushes/shrubs
- [ ] Mushrooms (normal + giant for Thornwood)
- [ ] Fallen logs/stumps
- [ ] Vines/ivy (surface-following curves)

### Dungeon Props
- [ ] Torch sconces (with light point)
- [ ] Prison doors/gates
- [ ] Chains/shackles
- [ ] Coffins/sarcophagi
- [ ] Altars (per-brand variant)
- [ ] Traps (spike, pressure plate, dart, swinging blade)
- [ ] Skull piles/bone decorations
- [ ] Corruption crystals (per-brand color)

### Vehicles/Transport
- [ ] Wagons/carts
- [ ] Boats (rowboat, ferry)
- [ ] Horse saddle/equipment

## Reference Games for Quality Bar
- **Elden Ring**: Dark fantasy architecture, creature design, atmospheric lighting
- **Skyrim**: Modular building kits, diverse biome assets, settlement composition
- **Witcher 3**: Material quality, weathering, vegetation density
- **Monster Hunter World**: Creature detail, environmental props, camp layouts
- **Dark Souls 3**: Gothic architecture, connected world design, atmospheric fog
