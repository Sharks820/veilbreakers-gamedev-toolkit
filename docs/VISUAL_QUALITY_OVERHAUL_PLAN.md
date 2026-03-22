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

**Roof Slate/Tile:**
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

---

## COMPREHENSIVE TEXTURE & MATERIAL REFERENCE

### Texture Map Types (Every Asset Needs These)
| Map | Purpose | Format | Notes |
|-----|---------|--------|-------|
| **Albedo/Diffuse** | Base color without lighting | sRGB, RGB | NO baked shadows or AO |
| **Normal Map** | Surface detail without geometry | Linear, RGB (tangent space) | Blue-dominant, from high-poly bake or procedural |
| **Roughness** | Micro-surface smoothness | Linear, Grayscale | 0=mirror, 1=matte. Worn edges=smoother, crevices=rougher |
| **Metallic** | Metal vs non-metal | Linear, Grayscale | Binary in practice: 0=dielectric, 1=metal. Rust transitions |
| **AO (Ambient Occlusion)** | Crevice darkening | Linear, Grayscale | Baked from mesh concavities. Multiply into albedo or separate |
| **Emission** | Self-illumination | sRGB, RGB | Brand-colored glows, magic runes, lava, crystals |
| **Displacement/Height** | Actual surface deformation | Linear, Grayscale | For terrain, stone walls. Costly — use sparingly |
| **Opacity/Alpha** | Transparency mask | Linear, Grayscale | Foliage, hair cards, cloth edges, glass |

### Texture Resolution Per Asset Type
| Asset | Albedo | Normal | Rough/Metal | AO |
|-------|--------|--------|-------------|-----|
| **Hero character** | 4096 | 4096 | 2048 | 2048 |
| **Common monster** | 2048 | 2048 | 1024 | 1024 |
| **Weapon (held)** | 2048 | 2048 | 1024 | 1024 |
| **Building exterior** | 2048 tiling | 2048 tiling | 1024 tiling | 1024 tiling |
| **Furniture/prop** | 1024 | 1024 | 512 | 512 |
| **Small item** | 512 | 512 | 256 | 256 |
| **Terrain (per tile)** | 2048 tiling | 2048 tiling | 1024 tiling | — |
| **Vegetation** | 1024 atlas | 1024 | 512 | — |
| **Skybox** | 4096 | — | — | — |

### COMPLETE Material Library (30+ Materials)

**ARCHITECTURE — Stone/Masonry**
```
1. rough_stone_wall    — Voronoi blocks + mortar lines + noise variation + bump
2. smooth_stone        — Subtle noise + low roughness + polished feel
3. cobblestone_floor   — Round Voronoi cells + mortar + worn-smooth tops
4. brick_wall          — Brick Texture node + mortar + per-brick color shift
5. crumbling_stone     — rough_stone + edge damage mask + debris particles
6. mossy_stone         — rough_stone + green noise mask at bottom (height gradient)
7. marble              — Wave Texture (veins) + low roughness + subtle color variation
```

**ARCHITECTURE — Wood**
```
8. rough_timber        — Wave Texture (grain) + high roughness + knot noise
9. polished_wood       — Wave Texture (fine grain) + low roughness + warm color
10. rotten_wood        — rough_timber + green/brown noise spots + high roughness
11. charred_wood       — Dark base + noise cracks revealing orange embers
12. plank_floor        — Repeating planks via Brick Texture (stretched) + gap lines
```

**ARCHITECTURE — Roofing**
```
13. slate_tiles        — Brick Texture (offset rows) + per-tile noise + edge chip bump
14. thatch_roof        — Noise-driven grass/straw pattern + very high roughness
15. wooden_shingles    — Small Brick Texture + wood grain per shingle
```

**METALS**
```
16. rusted_iron        — Mix: clean metal (high metallic, low rough) + rust (low metallic, high rough)
17. polished_steel     — High metallic + very low roughness + subtle scratch noise
18. tarnished_bronze   — Warm metallic base + green patina noise in crevices
19. chain_metal        — High metallic + medium roughness + small-scale noise
20. gold_ornament      — Warm yellow metallic + polished + minor scratch detail
```

**ORGANIC — Creature Surfaces**
```
21. monster_skin       — Subsurface scattering + pore noise + roughness variation
22. scales             — Voronoi pattern + per-scale color shift + smooth bump
23. chitin/carapace    — High metallic sheen + hard surface + segment lines
24. fur_base           — Dark base with noise strands (for under hair cards)
25. bone               — Off-white + fine noise + smooth-to-rough gradient
26. membrane           — Subsurface + translucency + vein noise (wings, webbing)
```

**ORGANIC — Vegetation**
```
27. bark               — High-frequency noise + vertical stretch + deep crevice bump
28. leaf               — Green gradient + translucency + vein pattern
29. moss               — Soft green noise + very high roughness + no specular
30. mushroom_cap       — Smooth dome + subtle spotting + subsurface glow
```

**TERRAIN**
```
31. grass              — Green base + blade noise + high roughness
32. dirt               — Brown noise + pebble bump + medium roughness
33. mud                — Dark wet brown + very low roughness (wet) + displacement
34. snow               — White + subsurface blue tint + sparkle noise in roughness
35. sand               — Warm beige noise + fine grain bump + medium roughness
36. cliff_rock         — Layered noise at multiple scales + strong normal detail
```

**SPECIAL / VFX**
```
37. corruption_overlay — Purple/dark noise + vein pattern + emission pulse
38. brand_glow_[10]    — Per-brand emission color (from BrandSystem.cs) + fresnel edge
39. magic_rune         — Emission pattern from UV-mapped rune texture + pulse animation
40. blood_splatter     — Dark red + high roughness + alpha-masked decal
41. water_surface      — Transparent + fresnel + animated normal scroll + foam edge
42. lava/ember         — Black base + orange emission in cracks (noise mask)
43. ice/crystal        — Transparent + high IOR refraction + internal scatter
44. glass              — Transparent + low roughness + slight tint
45. cloth/fabric       — Woven pattern (Brick Texture) + high roughness + color dye
```

### Texture Techniques

**Tiling Textures (Architecture/Terrain)**
- All architectural surfaces use TILING textures (seamless repeat)
- UV scale controlled by Mapping node — consistent texel density across assets
- Per-instance variation via Object Info > Random node offset
- Witcher 3 rule: max 7 base textures + 2 trim textures per district

**Trim Sheets (Detail Strips)**
- A single texture containing multiple detail strips side-by-side
- UV mapped so different mesh faces sample different strips
- Used for: molding, cornices, window frames, door frames, edge trim
- One 2048 trim sheet can detail 50+ buildings

**Texture Atlasing**
- Multiple small assets share one texture (e.g., all potions on one 2048 atlas)
- Reduces draw calls in game engine
- UV islands packed into shared atlas space
- Categories: weapon atlas, armor atlas, prop atlas, vegetation atlas

**Decals (Overlaid Detail)**
- Blood: alpha-masked splatter projected onto surfaces
- Dirt/grime: vertex-color-driven darkening at base of walls
- Moss/lichen: green noise masked by height + moisture
- Cracks: normal-map-only decals for damage detail
- Footprints: alpha-stamped trail decals
- Rain streaks: vertical smear pattern on building sides

**Vertex Color Channels for Material Blending**
```
Channel R: AO / cavity darkness
Channel G: Curvature / edge wear (convex = bright, concave = dark)
Channel B: Height gradient (bottom=1, top=0) for moss/dirt
Channel A: Damage/wetness mask
```
Materials read vertex colors via Attribute node and use them to blend between clean and weathered variants.

**Brand-Specific Texture Effects**
Each of the 10 VB brands has visual identity in textures:
| Brand | Emission Color | Surface Effect | Texture Detail |
|-------|---------------|----------------|----------------|
| IRON | Steel gray glow (0.71,0.75,0.80) | Metallic sheen | Chain/rivet pattern |
| SAVAGE | Blood red (0.86,0.27,0.27) | Organic veins | Claw scratch marks |
| SURGE | Electric blue (0.39,0.71,1.0) | Lightning arcs | Crackling energy lines |
| VENOM | Toxic green (0.47,0.86,0.39) | Bubbling surface | Acid erosion pitting |
| DREAD | Deep purple (0.63,0.39,0.78) | Shadow tendrils | Fear-rune inscriptions |
| LEECH | Dark crimson (0.71,0.24,0.43) | Pulsing veins | Parasitic growth |
| GRACE | Holy silver (1.0,1.0,1.0) | Radiant glow | Feather/light patterns |
| MEND | Healing gold (0.94,0.82,0.47) | Warm pulse | Cell/growth patterns |
| RUIN | Flame orange (1.0,0.63,0.31) | Heat distortion | Crack/fragment lines |
| VOID | Void dark (0.39,0.24,0.55) | Reality warp | Dimensional tear noise |

**Corruption Tier Visual Effects on Textures**
| Tier | Albedo Effect | Normal Effect | Emission |
|------|--------------|---------------|----------|
| ASCENDED (0-10%) | Slight golden tint | Smooth, clean | Soft warm glow |
| PURIFIED (11-25%) | Normal colors | Normal detail | None |
| UNSTABLE (26-50%) | Slight purple veins | Vein bump pattern | Occasional flicker |
| CORRUPTED (51-75%) | Dark purple overlay | Heavy vein bumps | Pulsing dark glow |
| ABYSSAL (76-100%) | Near-black with purple | Distorted, chaotic | Strong dark emission |

### Procedural vs Image-Based Decision Matrix
| Scenario | Use Procedural | Use Image-Based |
|----------|---------------|-----------------|
| Tiling surfaces (stone, wood, terrain) | YES — infinite resolution, no seams | NO |
| Unique character detail (face, tattoo) | NO | YES — painted texture |
| Equipment trim/ornament | Trim sheet (image) | — |
| Brand VFX glow | YES — shader-driven | NO |
| Skybox | NO | YES — HDRI or painted |
| Terrain splat | Vertex color blend (procedural) | Base textures (image) |
| Decals (blood, dirt) | NO | YES — alpha-masked projections |
| Weapon engravings | Trim sheet or normal-only decal | — |

---

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

## Phase 2: CHARACTERS/MONSTERS — STUDIO-GRADE

### 2A. Character Base Mesh System
NOT stacking cylinders. Proper subdivision surface modeling:

**Construction Method:**
1. Build low-poly cage (500-800 verts) with bmesh — ALL QUADS
2. Edge loops placed at EVERY joint: shoulder (3 loops), elbow (3 loops), wrist (2), hip (3), knee (3), ankle (2), neck (3), spine (5+ along torso)
3. Mirror modifier for perfect symmetry during modeling
4. Subdivision surface modifier level 2 for viewport, level 3 for render
5. Final LOD0: 20,000-50,000 tris for common monsters, 80,000-150,000 for heroes

**Face Topology Rules:**
- Concentric loops around eyes (3 rings minimum)
- Elliptical loops around mouth connecting to nasolabial fold
- Pole vertices (5+ edges) ONLY in non-deforming areas (top of head, back of torso)
- Edge flow follows muscle lines (deltoid wrap around shoulder, pectoral flow, quad/hamstring split at knee)
- NO triangles except at termination points (fingertips, ear tips, horn tips)

**Rigging Compatibility:**
- Vertex groups pre-defined matching rig template bone names
- Max 4 influences per vertex (GPU skinning compatible)
- Shape keys for: jaw open, blink L/R, brow raise L/R, smile L/R (minimum 12 blend shapes)
- Armature modifier last in stack

### 2B. Monster Body Type Templates — FULL SPECIFICATION

**HUMANOID BASE (8 monsters use this)**
Chainbound, Corrodex, Crackling, Hollow, The Bulwark, Voltgeist, Bloodshade, The Vessel

Construction:
- Torso: 8-segment cross-section extruded 6 times (spine segments)
- Arms: 8-segment ring extruded 5 times (upper arm, elbow×3, forearm, wrist, hand)
- Legs: 8-segment ring extruded 5 times (thigh, knee×3, shin, ankle, foot)
- Head: sphere (12×8 segments) with face topology cuts (eye sockets, mouth, nose ridge)
- Fingers: 4 per hand (5-segment cylinders), thumb opposing
- Scale variants via shape keys driven by vb_game_data.py scale values

Per-monster differentiation:
- **Chainbound**: heavy/wide torso (scale 1.2,1.5,1.2), thick limbs, hunched posture via shape key
- **Corrodex**: knight proportions (1.0,1.7,1.0), upright posture, armor attachment points on torso/shoulders
- **Crackling**: child-scale (0.5,0.7,0.5), large head ratio, thin limbs
- **Hollow**: elongated (0.8,1.6,0.6), sunken chest cavity (inverted shape key), wispy edges
- **The Bulwark**: massive (2.0,2.5,1.5), extra shoulder width, golem proportions, shield-merged arm
- **Voltgeist**: ghostly (1.0,1.5,0.8), tattered lower body fading to wisps, ribcage visible
- **Bloodshade**: wraith (1.0,1.8,0.8), flowing cape geometry, elongated fingers, hollow face
- **The Vessel**: delicate (0.8,1.5,0.8), floating posture, robes as cloth-sim-ready mesh, porcelain face mask as separate object

**QUADRUPED BASE (5 monsters)**
Grimthorn, Ironjaw, Mawling, Ravener, Sporecaller

Construction:
- Spine: 10-segment chain from skull to tail root, 8 verts per cross-section
- Rib cage: wider cross-sections at thorax, narrowing at waist
- 4 legs: each with shoulder/hip ball joint topology, upper leg, knee (3 loops), lower leg, paw/hoof
- Tail: 6-segment tapered chain with 6-vert cross-section
- Head: box-modeled skull → subdivision, jaw as separate hinged piece
- Tongue: flat tapered mesh inside mouth

Per-monster differentiation:
- **Grimthorn**: deer-like legs (elongated shin), vine growths extruded from spine (curve-based), mushroom antlers (metaball→mesh), barbed tail
- **Ironjaw**: bear proportions (heavy front, wide jaw), metal plate geometry on torso, chain tail (torus-linked), jaw trap mechanism (hinged separate mesh with teeth)
- **Mawling**: wolf proportions (lean, long muzzle), oversized jaw with exposed teeth row, matted fur texture, glowing eye emission
- **Ravener**: raptor build (forward lean, powerful hind legs), armored crest on skull (extruded ridge), razor claw geometry on feet, muscular forearms
- **Sporecaller**: deer frame with fungal overgrowth, mushroom cluster antlers (sphere compositions), spore sac bulges on back (inflated shape key), mossy hide texture

**AMORPHOUS BASE (3 monsters)**
Gluttony Polyp, The Congregation, The Weeping

Construction:
- Start with metaball composition (5-20 elements)
- Convert to mesh → voxel remesh (size 0.08) for clean topology
- Smooth subdivision level 1
- Shape keys for: pulsing (scale oscillation), pseudopod extension, splitting

Per-monster:
- **Gluttony Polyp**: central digestive sac (large translucent sphere), feeding tentacles (4-6 curve-based appendages), consumed matter visible through membrane material
- **The Congregation**: BOSS — massive writhing mass, face shapes pressing against surface (sculpt-pushed shape keys), central eye (separate sphere with iris texture), soul tendrils (particle hair system), scale 3.0×4.0×3.0
- **The Weeping**: floating eye cluster connected by tendons (curve-based sinew between sphere eyes), dark ichor drip (particle emitter), distortion aura (shader effect)

**ARACHNID BASE (2 monsters)**
Skitter-Teeth, The Broodmother

Construction:
- Cephalothorax: elongated sphere, 12-segment cross-section
- Abdomen: large sphere (egg sac for Broodmother)
- 8 legs: each with 4 segments (coxa, femur, patella+tibia, tarsus), 6-vert cross-section per segment
- Pedipalps: 2 shorter appendages near mouth
- Mandibles/fangs: sculpted geometry
- Spinnerets (optional): 3 nozzle-shapes at abdomen rear

Per-monster:
- **Skitter-Teeth**: ribcage as body instead of carapace (bone texture), teeth lining the open cavity (individual tooth geometry), bone-textured legs, undead/skeletal aesthetic
- **The Broodmother**: massive scale (2.5,1.5,3.0), egg sac abdomen (translucent membrane with egg shapes inside), wasp wings (membrane mesh with vein normal map), armored carapace (layered plate geometry), venomous mandibles with drip particle

**SERPENT (Needlefang)**
- 20+ segment spine chain, 8-vert cross-section tapering from body to tail
- Scale pattern via Voronoi texture on UV
- Hood geometry: flared neck section with eye-spot pattern UV
- Needle fangs: elongated cone geometry, hinged jaw
- Iridescent scale material (thin-film shader effect)

**INSECT (Flicker)**
- Thorax: 3-segment body, narrow waist
- Wings: 4 membrane meshes (dragonfly double-wing), alpha-transparent with vein normal map
- Compound eyes: sphere with faceted normal map
- 6 legs: thin segmented cylinders
- Antennae: 2 curve-based filaments
- Afterimage effect: slightly scaled transparent duplicate offset behind

### 2C. Brand-Specific Visual Features — FULL DETAIL
Every monster has key_features in vb_game_data.py. Each becomes REAL geometry or material:

| Brand | Geometry Features | Material Effects |
|-------|------------------|------------------|
| **IRON** | Chains (torus-link generator along bone paths), padlocks (box+cylinder composite), broken shackles (open torus), metal plates (extruded surface patches) | Steel gray metallic + rust noise, chain link normal map |
| **SAVAGE** | Thorns (cone extrusions along surface normals), vines (curve-based growth following edge flow), bone spurs (tapered cylinders from joints), claw marks (groove geometry) | Blood red veins in skin, thorn bark texture, organic roughness |
| **SURGE** | Lightning veins (edge-detected emission pattern via shader), spark particles (emitter points), translucent skin (subsurface + emission), crystal growths (faceted geometry) | Electric blue emission, translucent skin shader, crackling energy animated |
| **VENOM** | Poison barbs (spine geometry), acid drip (particle system), toxic pools (flat alpha mesh), pustules (inflated sphere shape keys) | Toxic green subsurface, bubbling surface animation, acid erosion pitting |
| **DREAD** | Shadow tendrils (extruded dark geometry from limb ends), fear runes (UV-projected emission), floating fragments (separate meshes with slight offset) | Deep purple darkness, shadow shader (light absorption), fear glow |
| **LEECH** | Parasitic tendrils (curve-based suction tubes), pulsing veins (animated normal map), proboscis (tapered tube with rings) | Dark crimson pulsing, wet/glossy skin, parasitic growth patterns |
| **GRACE** | Light robes (cloth-sim-ready mesh), healing glow particles, porcelain mask (smooth separate mesh), feather details (card-based like hair) | Holy silver emission, radiant fresnel glow, clean smooth surface |
| **MEND** | Regeneration particles, crystal formations (faceted geometry), growth patterns (vine-like emission on surface), shield geometry (translucent sphere) | Healing gold emission, cellular pattern in subsurface, warm pulse |
| **RUIN** | Fracture lines (mesh edge splits with emission), floating debris (separate rigid body chunks), explosion marks (cavity geometry) | Flame orange cracks with emission, charred surface, heat distortion |
| **VOID** | Reality cracks (plane meshes with warp shader), dimensional rift particles, unstable scale (animated scale oscillation) | Void dark with reality-warp shader, dimensional tear emission |

### 2D. Per-Monster Texture Pipeline — COMPLETE
For EACH of the 20 monsters:
1. **Sculpt pass**: Add surface detail on high-poly duplicate (skin pores, scales, scars, muscle definition, wrinkles)
2. **Bake normal map**: High-poly → low-poly tangent-space normal map (2048 for common, 4096 for bosses)
3. **Bake AO**: Mesh concavities → AO map
4. **Curvature map**: Edge detection → wear/highlight mask
5. **Albedo creation**: Brand base color + noise variation + curvature-driven highlights/shadows
6. **Roughness map**: Smooth on convex surfaces, rough in crevices, wet=low roughness, dry=high
7. **Metallic map**: Only for metallic parts (IRON brand armor plates, chain links)
8. **Emission map**: Brand glow patterns, eye glow, magical effects
9. **Opacity map**: For membrane wings, translucent tentacles, ghostly bodies

### 2E. Monster Scaling & Variation System
Every monster must support on-the-fly variation without regenerating:
- **Size**: 3 variants per monster (young 0.7x, adult 1.0x, elder 1.3x) via scale
- **Corruption visual**: 5 tiers from Ascended to Abyssal (shader-driven, not mesh change)
- **Color variation**: Object Info > Random seeds material hue shift ±10%
- **Scar/damage**: Shape keys for battle damage (torn ear, missing horn, cracked shell)
- **Evolution**: Shape key morph between evolution stages + brand VFX overlay

### 2F. New Monster Generation Pipeline
For adding NEW monsters over time (not just the initial 20):
1. Define in vb_game_data.py: body_type, scale, brand, key_features, description
2. Select closest base template (humanoid/quadruped/amorphous/arachnid/serpent/insect)
3. Apply scale and proportion shape keys
4. Generate brand-specific features from the feature library
5. Auto-assign materials from the 45-material library based on surface type
6. Sculpt pass for unique detail
7. Bake texture maps
8. Rig with matching template
9. Screenshot → evaluate → refine loop
10. Export with LOD chain

---

## Phase 3: WEAPONS/ITEMS/ARMOR — STUDIO-GRADE

### 3A. Weapon System — FULL SPECIFICATION

**Every weapon has these components (separate meshes for modularity):**
- Blade/Head: the business end
- Guard/Cross-guard: hand protection
- Grip/Handle: wrapped holding area
- Pommel: counterweight at bottom
- Decorative elements: runes, gems, brand insignia

**Sword Types (5 variants):**
| Type | Blade Tris | Total Tris | Blade Detail |
|------|-----------|------------|--------------|
| Shortsword | 800 | 2,500 | Single edge, slight curve, fuller groove |
| Longsword | 1,200 | 4,000 | Double edge, blood channel, crossguard detail |
| Greatsword | 2,000 | 6,000 | Wide blade, ricasso, elaborate guard, two-hand grip |
| Curved sword | 1,000 | 3,500 | Scimitar curve, single edge, wave pattern |
| Dagger | 500 | 1,500 | Short tapered blade, simple guard, ring pommel |

**Axe Types (3 variants):**
- Hand axe: 2,000 tris — single head, short haft, leather wrap
- Battle axe: 3,500 tris — double-headed or crescent, medium haft
- Greataxe: 5,000 tris — massive head, long haft, counterweight

**Blunt Weapons (3 variants):**
- Mace: 2,500 tris — flanged head (6-8 flanges as geometry), short handle
- Warhammer: 3,000 tris — flat striking face + pick back, long handle
- Club: 1,500 tris — rough wood with nail/spike extrusions

**Polearms (3 variants):**
- Spear: 2,000 tris — diamond-section blade, long shaft, buttcap
- Halberd: 4,000 tris — axe head + spike + hook on pole
- Glaive: 3,000 tris — curved blade on pole, tassel wrap

**Ranged (3 variants):**
- Shortbow: 2,000 tris — curved limbs (bezier profile), string (thin cylinder), grip
- Longbow: 2,500 tris — recurve limbs, arrow rest notch, leather grip
- Crossbow: 4,000 tris — mechanism detail, prod, stock, trigger, stirrup

**Staves/Wands (3 variants):**
- Staff: 2,000 tris — gnarled wood (curve-based), crystal head, rune wrappings
- Wand: 1,000 tris — straight shaft with ornate tip (sphere/crystal/flame)
- Tome: 3,000 tris — open book with page geometry, floating, brand-glow

**Brand Weapon Variants:**
Every weapon type gets visual treatment per brand:
- IRON: riveted metal, chain-wrapped grip, heavy construction
- SAVAGE: bone/antler parts, leather wrapping, primal aesthetic
- SURGE: crystalline blade, lightning engravings, energy core pommel
- VENOM: green-tinged blade, dripping acid VFX point, corroded edges
- DREAD: shadow-dark metal, fear rune engravings, eye motif
- LEECH: organic handle (tendon wrapping), blood groove channels, barbed edges
- GRACE: silver/white blade, feather guard detail, radiant gem
- MEND: golden staff, crystal focus, healing glow points
- RUIN: cracked blade with ember glow, destruction patterns, unstable energy
- VOID: reality-distorted blade (warp shader on edge), void crystal pommel

### 3B. Armor System — PER-SLOT DETAIL

**Helmet (5 variants, 2,000-8,000 tris each):**
- Open-face helm: cheek guards, nose guard, forehead plate, chin strap
- Full helm: visor (hinged separate mesh), breathing holes, crest mount point
- Hood: cloth mesh with face shadow, drawstring detail
- Crown/circlet: thin metallic band, gem sockets, branch/antler ornaments
- Skull mask: bone-textured face plate, jaw piece, eye socket geometry

**Chest Armor (5 variants, 5,000-15,000 tris each):**
- Plate mail: overlapping plates on torso, articulated waist section, back plate
- Chain mail: ring pattern normal map over base mesh, leather trim
- Leather armor: panels with stitching seams, buckle closures, tooling pattern
- Robes: flowing cloth-sim-ready mesh, layered fabric, belt/sash
- Bare/light: minimal chest wrap, tattoo UV region, muscle definition visible

**Gauntlets (3 variants, 1,500-4,000 tris each):**
- Plate gauntlets: articulated fingers (3 segments each), wrist guard, knuckle plates
- Leather gloves: stitched seams, reinforced palms, finger wraps
- Wraps/bracers: wrapped cloth/leather, forearm guard, ring attachments

**Boots/Greaves (3 variants, 2,000-5,000 tris each):**
- Plate greaves: shin guard, knee cop, sabatons with articulated toe
- Leather boots: tall shaft, buckle straps, sole detail, worn edges
- Sandals/wraps: minimal coverage, sole + strap geometry

**Shoulders/Pauldrons (3 variants, 1,500-4,000 tris each):**
- Plate pauldrons: layered plates, arm attachment, spike/horn mounts
- Fur mantle: draped fur mesh with hair card detail
- Bone shoulder: monster bone/trophy mounted on leather base

**Capes/Cloaks (cloth-sim ready, 2,000-5,000 tris):**
- Full cloak: shoulder-to-heel drape, hood attachment, clasp geometry
- Half cape: one-shoulder, wind-ready cloth sim mesh
- Tattered cape: pre-damaged edge with alpha, torn strips

### 3C. Item System — COMPREHENSIVE

**Consumables (500-1,500 tris each):**
- Health potion: glass bottle with cork, red liquid inner surface, label UV region
- Mana potion: blue liquid, ornate bottle shape, crystal stopper
- Antidote: green vial, narrow neck, wax seal
- Buff tonic: wide flask, colored liquid, brand-specific bottle shape
- Food items: bread (sculpted crust), cheese (wedge), meat (drumstick)
- Phoenix Down: feather bundle with golden glow emission

**Capture Devices (1,000-3,000 tris, per-brand visual):**
- IRON: chain-cage sphere with padlock mechanism
- SAVAGE: bone-cage with leather bindings
- SURGE: crystal containment sphere with arc conductors
- VENOM: sealed containment vial with toxic glow
- VOID: dimensional pocket orb with void energy

**Key Items (500-2,000 tris each):**
- Keys: skeleton key with ornate bow, dungeon key with simple teeth, master key with rune engraving
- Maps: rolled parchment with wax seal, visible edge wear
- Lockpicks: thin metal tools in leather roll case
- Brand tokens: per-brand shaped coin/medallion
- Quest items: unique shapes matching quest (e.g., "corroded padlock" from Chainbound drops)

**Crafting Materials (200-800 tris each):**
- Ores: rough angular chunks with metallic faces + rock matrix
- Leather: folded hide with stitching marks
- Herbs: leaf/stem/flower geometry with alpha cards
- Gems: faceted crystal geometry (12-20 faces) with refraction material
- Monster parts: from vb_game_data drop tables (e.g., "lightning shard" = crystal, "living seed" = organic pod)

**Currency:**
- Gold coins: disc with embossed face detail (normal map), stack variation
- Brand tokens: per-brand 3D shape (pentagon for 5 brands, hexagon for 6, etc.)

---

## Phase 4: TERRAIN/MAP VISUAL QUALITY (Week 3)

### 4A. Terrain Materials — PER-BIOME
Each biome has its own terrain material palette:

**Thornwood Forest:**
- Ground: dark leaf litter + exposed roots + soil
- Slopes: moss-covered rock + fern patches
- Cliffs: gray stone with vine growth
- Water edges: mud + reeds

**Corrupted Swamp:**
- Ground: black mud + toxic pools (emission)
- Slopes: slick dark rock + slime trails
- Cliffs: corroded stone with purple corruption veins
- Water: murky green with surface particles

**Mountain Pass:**
- Ground: gravel + sparse grass + snow patches
- Slopes: exposed rock + ice
- Cliffs: layered sedimentary rock with cracks
- Peaks: pure snow + ice crystals

**Ruined Fortress:**
- Ground: broken cobblestone + dirt + rubble
- Slopes: crumbling wall foundation + moss
- Structures: damaged stone (corruption overlay)

**Abandoned Village:**
- Ground: dirt paths + overgrown grass
- Structures: rotten wood + broken stone
- Garden areas: dead/wilted vegetation

**Veil Crack Zone:**
- Ground: fractured earth with glowing cracks (emission)
- Floating: crystal surfaces, void-touched stone
- Air: particle-dense atmosphere

**Cemetery:**
- Ground: dark soil + dead grass + fog
- Paths: worn stone walkways
- Decoration: fallen leaves, scattered petals

**Battlefield:**
- Ground: churned mud + blood-stained earth
- Debris: broken weapons, shield fragments
- Atmosphere: smoke/haze particles

### 4A-extended. Terrain Material Blending
- Vertex color splatmap with 4 channels (R=grass, G=rock, B=dirt, A=snow/special)
- Slope-based auto-assignment: flat=grass, 30°+=rock, vertical=cliff
- Height-based: low=dirt/water, mid=grass, high=rock/snow
- Noise variation prevents uniform bands
- Biome overlay: corruption tint on all surfaces in corrupted zones

### 4B. Vegetation Quality — PER-BIOME

**Thornwood Forest:**
- Dead/twisted oaks: full branch structure, 8-15K tris LOD0
- Giant mushrooms: dome cap + stem, 3-5K tris
- Ferns: alpha card billboards, 500 tris
- Thorny bushes: branch mesh + thorn extrusions, 2K tris
- Hanging moss/vines: curve-based draped geometry

**Corrupted Swamp:**
- Dead trees: bare branches, tilted, 5K tris
- Spore pods: metaball-generated clusters
- Toxic flowers: petal geometry with emission
- Reeds/cattails: billboard grass cards

**Mountain Pass:**
- Pine trees: proper conifer branch cards, 10K tris
- Alpine grass: short billboard strips
- Boulders: sculpted rocky noise, 3K tris
- Snow-laden branches: white caps on geometry

**Cemetery:**
- Willow trees: drooping branch curves
- Dead flowers: wilted petal geometry
- Iron fencing: modular posts + bars

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

## COMPLETE MESH LIBRARY — TARGET 1,200+ UNIQUE MESHES

AAA open worlds ship 3,000-5,000 unique meshes. Our Phase 1 target is 1,200+ to fill a compelling world. Everything must be HIGHEST QUALITY with proper materials, normals, and LODs.

### ARCHITECTURE — 175+ modular pieces (5 styles × 35 pieces)

**Per Style Kit (35 pieces each):**
- Walls: straight, corner-in, corner-out, window, door, half-height, damaged, T-junction, end-cap (9)
- Floors: stone slab, wooden plank, dirt, damaged (4)
- Ceilings: flat, vaulted, open-beam (3)
- Roofs: slope, peak, flat, gutter, dormer, chimney (6)
- Stairs: straight, spiral, ramp, ladder (4)
- Doors: single, double, arched, gate, trapdoor (5)
- Windows: small, large, pointed, round, broken (5)
- Trim: cornice, sill, lintel, baseboard (4)

**5 Styles: (175 total modular pieces)**
- [ ] Gothic: pointed arches, buttresses, rose windows, spires — for shrines, cathedrals
- [ ] Medieval: half-timber, plaster infill, thatched roofs — for houses, taverns, shops
- [ ] Fortress: thick stone, arrow slits, battlements, portcullis — for castles, walls, barracks
- [ ] Organic: living wood, root arches, mushroom domes, vine walls — for Thornwood structures
- [ ] Ruined: crumbling variants of ALL above — broken walls, collapsed roofs, rubble piles

**Building Compositions (assembled from kit pieces):**
- [ ] Cottage (1 floor, 4 walls, door, 2 windows)
- [ ] Two-story house (8 walls, stairs, 4 windows)
- [ ] Tavern/inn (large footprint, bar area, upper rooms)
- [ ] Shop (counter, display shelving, storage back)
- [ ] Blacksmith (forge area, open front)
- [ ] Shrine (small, altar room, offering area)
- [ ] Temple/cathedral (large, nave, transept, apse)
- [ ] Guard tower (3 floors, spiral stairs, lookout top)
- [ ] Barracks (bunk room, armory, mess hall)
- [ ] Prison (cells, guard post, interrogation)
- [ ] Warehouse (large open interior, crates)
- [ ] Stable (stalls, hay loft, trough)
- [ ] Bridge house (built over water/gap)
- [ ] Watchtower ruin
- [ ] Collapsed building shell

### CHARACTERS & NPCs — 60+ unique character meshes

**4 Playable Heroes (full detail, 80-150K tris each):**
- [ ] Vex — heavy build, prison-worn armor, chain motifs, stern face, scarred
- [ ] Seraphina — lithe build, thorn-decorated leather, wild hair, predatory eyes
- [ ] Orion — robed scholar build, conductor's gloves, crackling energy staff, intense gaze
- [ ] Nyx — androgynous build, shadow-touched skin, mismatched eyes, shifting form edges

**NPC Body Types (base meshes, 20-40K tris each, 8 types):**
- [ ] Male heavy (guards, blacksmiths, warriors)
- [ ] Male average (merchants, scholars, travelers)
- [ ] Male slim (thieves, mages, youths)
- [ ] Male elder (sages, priests, beggars)
- [ ] Female heavy (innkeepers, warriors, matrons)
- [ ] Female average (merchants, healers, travelers)
- [ ] Female slim (scouts, mages, nobles)
- [ ] Female elder (herbalists, oracles, shrine keepers)

**NPC Outfit Sets (layered over body types, 15 sets):**
- [ ] Town guard — plate helm, chainmail, sword belt, cape
- [ ] Merchant — fine tunic, apron, belt pouch, hat
- [ ] Farmer/villager — rough tunic, boots, straw hat, tool belt
- [ ] Priest/shrine keeper — robes, holy symbol, hood, sandals
- [ ] Noble — ornate clothing, jewelry, embroidered cloak
- [ ] Beggar — tattered rags, bare feet, bowl
- [ ] Blacksmith — leather apron, thick gloves, soot-stained
- [ ] Hunter — leather armor, quiver, fur-trimmed hood
- [ ] Mage/scholar — robes, book satchel, staff holster
- [ ] Tavern keeper — vest, rolled sleeves, serving towel
- [ ] Traveling merchant — pack-laden, exotic clothing
- [ ] Healer — white robes, herb pouch, gentle face
- [ ] Bandit — mismatched armor, face mask, stolen weapons
- [ ] Soldier — uniform plate, rank insignia, formation gear
- [ ] Cultist — dark robes, brand mask (per-brand variant ×10)

**NPC Full-Body Variation System (EVERY axis of variation):**

**Body Shape (shape keys on base mesh, blend 0-1):**
- Muscular ↔ Thin (muscle mass slider)
- Tall ↔ Short (height scale + proportional limb adjustment)
- Wide ↔ Narrow (shoulder/hip width)
- Heavy ↔ Lean (belly/chest/thigh volume)
- Young ↔ Old (posture hunch, skin sag, joint stiffness)
- 5 preset body builds: Athletic, Heavy, Slim, Average, Elder

**Height Variation:**
- 5 height tiers: Very Short (0.85x), Short (0.92x), Average (1.0x), Tall (1.08x), Very Tall (1.15x)
- NOT just uniform scale — legs/torso/head proportions shift with height

**Gender:**
- Male and Female base meshes (separate topology for chest/hip/shoulder differences)
- All 15 outfit sets work on BOTH genders (re-fitted per body type)
- Non-binary/androgynous body shape achievable via shape key blending

**Skin Tone (material parameter, 8+ options):**
- Pale, Fair, Light, Medium, Olive, Tan, Brown, Dark, Ash-gray (corrupted), Ghostly-pale (Veil-touched)

**Face (shape keys + separate pieces):**
- 5 face shapes (round, square, oval, angular, gaunt)
- 4 nose types (straight, broad, aquiline, button)
- 3 eye shapes (wide, narrow, deep-set)
- 3 jaw shapes (strong, narrow, round)
- 3 cheekbone heights (high, medium, flat)
- Scar/marking shape keys (3 per face region: forehead, cheek, chin)
- Age wrinkle shape keys (smooth → young → middle → elder)
- Tattoo/warpaint UV regions (brand-specific patterns)

**Hair (separate mesh, swappable):**
- Male: short crop, medium swept, long flowing, braided, mohawk, shaved, bald, ponytail, wild/unkempt, dreads (10)
- Female: short bob, medium wavy, long straight, long braided, twin braids, updo, wild/loose, shaved sides, ponytail, dreads (10)
- Hair COLORS: black, brown, dark brown, auburn, red, blonde, white/silver, gray, blue-tinted, green-tinted (10)
- All via hair card meshes with alpha transparency

**Facial Hair (male, separate mesh):**
- Clean-shaven, stubble, short beard, full beard, long beard, braided beard, mustache, goatee (8)

**Body Markings (texture layer):**
- Scars (slash, burn, puncture — 6 types, placeable on any limb/torso/face)
- Tattoos (brand-specific patterns ×10, tribal, runic)
- Corruption veins (shader-driven based on corruption level)
- Dirt/grime (vertex color overlay, adjustable intensity)

**Total Unique NPC Combinations:**
- Body: 5 shapes × 5 heights × 2 genders × 10 skin tones = 500 body variants
- Face: 5 × 4 × 3 × 3 × 3 = 540 face variants
- Hair: 10 styles × 10 colors = 100 hair variants
- Outfit: 15 outfit sets × 4 quality tiers = 60 outfit variants
- Accessories: 30 mix-and-match pieces
- **Theoretical maximum: 500 × 540 × 100 × 60 = 1.6 BILLION unique NPCs**
- **Practical distinct looks: 50,000+ easily achievable without repeats**

**NPC Accessories (separate meshes, mix-and-match):**
- [ ] Backpacks (3 sizes)
- [ ] Belt pouches (4 types)
- [ ] Jewelry (rings, necklaces, earrings — 6 pieces)
- [ ] Hats/headwear (8 types)
- [ ] Bags/satchels (3 types)
- [ ] Tool belts (blacksmith, herbalist, hunter)
- [ ] Cloaks/scarves (4 types)

### MONSTERS — 20 base + 60 variants = 80+ monster meshes

**20 Base Monsters (from vb_game_data.py):**
- [ ] Bloodshade, Chainbound, Corrodex, Crackling, Flicker
- [ ] Gluttony Polyp, Grimthorn, Hollow, Ironjaw, Mawling
- [ ] Needlefang, Ravener, Skitter-Teeth, Sporecaller
- [ ] The Broodmother, The Bulwark, The Congregation (BOSS)
- [ ] The Vessel, The Weeping, Voltgeist

**Per-Monster Variants (3 each = 60 additional):**
- Young (0.7x scale, simpler features, fewer scars)
- Adult (1.0x scale, full features, standard)
- Elder/Alpha (1.3x scale, extra growths/scars/armor, boss-like presence)

**Corruption Visual Variants (shader-driven, not separate meshes):**
- ASCENDED → PURIFIED → UNSTABLE → CORRUPTED → ABYSSAL
- Applied via material parameters, not new meshes

**Future Monster Slots (designed for expansion):**
- Framework supports adding unlimited new monsters via vb_game_data.py
- 6 body type templates (humanoid, quadruped, amorphous, arachnid, serpent, insect) cover most forms
- New body types can be added: avian, aquatic, multi-armed, centaur, floating

### WEAPONS — 22 base types × 10 brands = 220+ weapon meshes

**22 Base Weapon Types:**
- Shortsword, Longsword, Greatsword, Curved sword, Dagger (5 blades)
- Hand axe, Battle axe, Greataxe (3 axes)
- Club, Mace, Warhammer (3 blunt)
- Spear, Halberd, Glaive (3 polearms)
- Shortbow, Longbow, Crossbow (3 ranged)
- Staff, Wand, Tome (3 magic)
- Throwing knife (1 throwable)

**Per-Brand Visual Treatment (×10 brands = 220 variants):**
Each weapon type gets 10 brand variants via material/geometry swaps:
- IRON: riveted, heavy, chain-wrapped
- SAVAGE: bone/claw parts, primal leather
- SURGE: crystal blade, lightning engravings
- etc. (all 10 brands)

**Weapon Accessories (8 separate meshes):**
- [ ] Scabbard/sheath (sword, dagger)
- [ ] Quiver (arrows)
- [ ] Weapon belt hook
- [ ] Bow limb cover
- [ ] Staff crystal caps (per-brand)
- [ ] Weapon wrappings/charms
- [ ] Poison vials (attached)
- [ ] Glow runes (emission overlay)

### ARMOR — 22 base pieces × 4 material tiers = 88+ armor meshes

**22 Base Armor Pieces:**
- Helmets: open-face, full helm, hood, crown, skull mask (5)
- Chest: plate, chain, leather, robes, bare (5)
- Gauntlets: plate, leather, wraps (3)
- Boots: plate, leather, sandals (3)
- Shoulders: plate, fur, bone (3)
- Capes: full, half, tattered (3)

**4 Material/Quality Tiers:**
- Common (simple, minimal detail)
- Uncommon (some ornamentation, better materials)
- Rare (elaborate detail, magical elements)
- Legendary (maximum detail, brand-specific effects, glowing elements)

**Armor brand treatments (per-brand material swap ×10):**
880 potential combinations (22 × 4 tiers × 10 brands) — achieved via material/texture swap, not separate meshes

### SHIELDS — 15 shield meshes

- [ ] Round shield: wood, iron-bossed, large
- [ ] Kite shield: standard, decorated, tower
- [ ] Tower shield: full-body, arrow-slit, siege
- [ ] Buckler: small, metal, quick-use
- [ ] Magical barrier: translucent, brand-colored energy
- Per-brand boss/emblem variants (×10 via material swap)

### ITEMS & CONSUMABLES — 80+ item meshes

**Potions (12 variants):**
- [ ] Health: small, medium, large (3 sizes × red liquid)
- [ ] Mana: small, medium, large (3 sizes × blue liquid)
- [ ] Elixir, Ether, Hi-Ether (3 special)
- [ ] Antidote, Remedy, Smelling Salts (3 status cure)

**Capture Devices (10 — one per brand):**
- [ ] IRON cage-sphere, SAVAGE bone-cage, SURGE crystal-sphere
- [ ] VENOM containment vial, DREAD shadow-orb, LEECH tendril-pod
- [ ] GRACE light-sphere, MEND growth-pod, RUIN fragment-cage, VOID void-pocket

**Food & Cooking (12 items):**
- [ ] Bread loaf, cheese wheel, meat drumstick, fish, apple, mushroom
- [ ] Cooking pot (with ladle), cutting board, spice jars, flour sack, honey jar, dried herbs bundle

**Crafting Materials (20 items):**
- [ ] Iron ore, copper ore, silver ore, gold ore, dark crystal
- [ ] Leather strip, tanned hide, thick hide, monster hide
- [ ] Green herb, red herb, blue herb, rare flower, mushroom cluster
- [ ] Gem (ruby, sapphire, emerald, amethyst, diamond)
- [ ] Bone shard

**Key Items & Quest Objects (15 items):**
- [ ] Skeleton key, dungeon key, master key, lockpick set
- [ ] Map scroll, letter/note, ancient tome, journal
- [ ] Brand tokens (×10 — one per brand, coin/medallion shape)
- [ ] Purification crystal

**Currency (5 items):**
- [ ] Copper coin, silver coin, gold coin, coin pouch, treasure chest (small)

### FURNITURE & INTERIOR PROPS — 80+ meshes

**Seating (8):**
- [ ] Wooden chair, bench, stool, throne, cushioned chair, bar stool, log seat, stone seat

**Tables (6):**
- [ ] Tavern table (round), dining table (long), desk, workbench, counter, side table

**Storage (10):**
- [ ] Chest (wood, iron, ornate), barrel, crate, sack, basket, shelf, wardrobe, weapon rack

**Sleeping (5):**
- [ ] Bed frame (single, double), bedroll, hammock, hay pile

**Lighting (8):**
- [ ] Candelabra (floor, table), wall torch, hanging lantern, standing brazier, campfire, chandelier, crystal lamp, candle (single)

**Kitchen/Dining (10):**
- [ ] Plates, cups, bowls, pitcher, cauldron, cooking pot, cutting board, mortar/pestle, spice rack, barrel tap

**Decoration (12):**
- [ ] Banner (×10 brand + neutral), wall shield, mounted head/trophy, painting frame, rug (×3 sizes), tapestry, flower vase, mirror, clock, globe

**Religious/Shrine (6):**
- [ ] Altar (stone, wood), offering bowl, prayer mat, holy symbol, incense burner, relic display

**Crafting Stations (5):**
- [ ] Forge (anvil+bellows+furnace), alchemy table, workbench, enchanting altar, tanning rack

### ENVIRONMENT — 100+ meshes per biome × 8 biomes

**Trees (25 variants across biomes):**
- [ ] Dead oak, twisted oak, giant oak, birch, pine, spruce, willow, dead willow
- [ ] Mushroom tree (giant), root tree (Thornwood), corrupted tree, crystal tree (Veil zone)
- [ ] Young sapling (×5 species), stump (×3), fallen log (×4)

**Rocks (15 variants):**
- [ ] Boulder (small, medium, large), standing stone, rubble pile
- [ ] Cliff face section, cave entrance rock, crystal cluster
- [ ] Mossy rock, ice-covered rock, corrupted rock, floating rock (Veil)
- [ ] Pebbles (scatter mesh), slate stack, volcanic rock

**Grass & Ground Cover (12 variants):**
- [ ] Short grass (billboard), tall grass (billboard), dead grass
- [ ] Wildflowers (×3 colors), fern, clover patch
- [ ] Mushroom cluster (small), moss patch, leaf litter pile, snow patch

**Bushes & Shrubs (8 variants):**
- [ ] Berry bush, thorny bush, flowering bush, dead bush
- [ ] Hedge section, juniper, corrupted bush, crystal bush

**Water Features (6):**
- [ ] Stream bed rocks, waterfall splash zone, lily pad cluster
- [ ] Ice chunk, toxic pool edge, shore debris

**Atmospheric (8):**
- [ ] Fog emitter volume, dust mote emitter, firefly emitter
- [ ] Rain splash zone, snow drift, ash pile, spore cloud, void energy wisp

### DUNGEON PROPS — 60+ meshes

**Structural (12):**
- [ ] Pillar (stone, wood, broken), archway, collapsed ceiling debris
- [ ] Portcullis, iron gate, wooden door (intact, broken), secret passage lever
- [ ] Staircase section, bridge plank, trapdoor (closed, open)

**Imprisonment (8):**
- [ ] Shackles (wall, floor), chain (hanging, draped), iron maiden
- [ ] Cage (hanging, floor), stocks, prisoner skeleton

**Ritual/Dark (10):**
- [ ] Altar (blood-stained), sacrificial circle (floor marking), dark obelisk
- [ ] Soul cage, blood fountain, bone throne, corruption crystal (×10 brand colors)
- [ ] Summoning circle, ritual candles, occult symbols (floor decal meshes)

**Traps (8):**
- [ ] Spike trap (floor), pressure plate, dart launcher
- [ ] Swinging blade, falling cage, tripwire (thin cylinder)
- [ ] Poison gas vent, collapsing floor section

**Loot & Discovery (8):**
- [ ] Treasure chest (locked, open, trapped), gem pile, gold pile
- [ ] Hidden alcove, secret door, lore tablet, ancient mechanism

**Ambiance (14):**
- [ ] Cobwebs (×3 sizes), spider egg sac, bone pile (scattered, stacked)
- [ ] Skull pile, hanging skeleton, dripping water stalactite
- [ ] Toxic mushroom, glowing moss patch, bat roost (hanging mesh)
- [ ] Rat nest, insect swarm volume, rotting barrel, ancient rubble

### OUTDOOR STRUCTURES — 30+ meshes

**Fortification (10):**
- [ ] Wall section (stone, palisade), gate (wood, iron, drawbridge)
- [ ] Watchtower, corner tower, battlement section
- [ ] Moat edge, rampart walkway, murder hole ceiling

**Infrastructure (10):**
- [ ] Well (stone), water wheel, windmill, bridge (stone, rope, drawbridge)
- [ ] Dock/pier, market stall (×3 types), signpost, milestone marker

**Camp/Settlement (10):**
- [ ] Tent (small, large, command), campfire with log seats
- [ ] Hitching post, feeding trough, cart (intact, broken)
- [ ] Lookout post, barricade (wood, sandbag), spike fence

### ANIMALS & WILDLIFE — 20+ meshes

**Forest Animals (6):**
- [ ] Deer, wolf, fox, rabbit, owl, crow

**Mountain Animals (4):**
- [ ] Mountain goat, eagle, bear, snow hare

**Swamp/Water (4):**
- [ ] Frog, snake (non-monster), fish, turtle

**Domestic (4):**
- [ ] Horse, chicken, dog, cat

**Vermin (4):**
- [ ] Rat, bat, spider (small), beetle

### VEHICLES & MOUNTS — 10+ meshes

- [ ] Wagon (merchant, military), handcart
- [ ] Rowboat, raft, ferry
- [ ] Horse saddle (light, heavy, war), bridle
- [ ] Monster mount saddle (generic, adjustable)

---

## TOTAL MESH COUNT: 1,200+ unique meshes

| Category | Count |
|----------|-------|
| Architecture (5 styles × 35 pieces) | 175 |
| Building compositions | 15 |
| Character heroes | 4 |
| NPC body types | 8 |
| NPC outfit sets | 15 |
| NPC accessories | 30 |
| Monster bases | 20 |
| Monster variants (young/elder) | 40 |
| Weapons | 22 |
| Weapon brand variants (material) | 220 |
| Weapon accessories | 8 |
| Armor pieces | 22 |
| Armor tier variants | 88 |
| Shields | 15 |
| Items & consumables | 80 |
| Furniture & interior | 80 |
| Environment (trees/rocks/grass/etc) | 100+ |
| Dungeon props | 60 |
| Outdoor structures | 30 |
| Animals & wildlife | 22 |
| Vehicles & mounts | 10 |
| **TOTAL** | **~1,200+** |

The system is EXTENSIBLE — adding new monsters, weapons, building styles, or biome vegetation follows the same pipeline. Quality maintained through the autonomous generate → screenshot → evaluate → refine loop.

## Reference Games for Quality Bar
- **Elden Ring**: Dark fantasy architecture, creature design, atmospheric lighting
- **Skyrim**: Modular building kits, diverse biome assets, settlement composition
- **Witcher 3**: Material quality, weathering, vegetation density
- **Monster Hunter World**: Creature detail, environmental props, camp layouts
- **Dark Souls 3**: Gothic architecture, connected world design, atmospheric fog
- **God of War Ragnarok**: AAA material kits, modular weathering, environment detail density

---

## EXPERT REVIEW GAPS — 3-Agent Ultrathink Findings

See docs/EXPERT_REVIEW_GAPS.md for the complete 150+ item list from environment artist, character artist, and technical artist reviews.
