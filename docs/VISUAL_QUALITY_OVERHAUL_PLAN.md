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

## Reference Games for Quality Bar
- **Elden Ring**: Dark fantasy architecture, creature design, atmospheric lighting
- **Skyrim**: Modular building kits, diverse biome assets, settlement composition
- **Witcher 3**: Material quality, weathering, vegetation density
- **Monster Hunter World**: Creature detail, environmental props, camp layouts
- **Dark Souls 3**: Gothic architecture, connected world design, atmospheric fog
