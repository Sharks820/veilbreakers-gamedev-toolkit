# AAA Game Development Best Practices - Comprehensive Reference
# Dark Fantasy Action RPG (Dark Souls / Elden Ring / Diablo 4 class) - Unity URP

> Research compiled from Polycount wiki, Google Filament PBR docs, Unity documentation,
> DOOM 2016 graphics study (Adrian Courreges), Marmoset PBR guides, GDC resources,
> and cross-referenced AAA production data.

---

## 1. CHARACTER & EQUIPMENT SYSTEMS

### 1.1 Triangle Budgets (PC/Console, Current Gen)

| Asset Category | LOD0 Triangles | LOD1 | LOD2 | LOD3/Cull |
|---|---|---|---|---|
| Hero/Player Character | 30,000-80,000 | 15,000-40,000 | 5,000-15,000 | 1,500-5,000 |
| Major NPCs | 20,000-50,000 | 10,000-25,000 | 4,000-10,000 | 1,000-3,000 |
| Common Enemies | 15,000-40,000 | 7,500-20,000 | 3,000-8,000 | 800-2,000 |
| Background NPCs | 5,000-15,000 | 2,500-7,500 | 1,000-3,000 | Culled |

Reference data points:
- Nier: Automata (2B): 72,000 polygons
- Street Fighter 5: 80,000 per character at 60fps
- Final Fantasy XV: 100,000 max; hair alone 20,000
- Infamous Second Son: 120,000 per character
- Rainbow Six Siege: 40,000 + 3 texture maps at 2048x2048
- Sunset Overdrive: 40,000 per character

For a Dark Souls-style game at 60fps with multiple enemies on screen, target:
- **Player character: 40,000-60,000 triangles** (with equipment)
- **Enemies: 15,000-35,000 triangles** depending on importance
- **Total scene triangle budget: 2-6 million** at 60fps

### 1.2 Equipment Attachment Systems

#### Bone Socket System (FromSoftware / Blizzard approach)
Weapons and shields attach to predefined bone sockets on the skeleton:

```text
Standard Socket Bones:
- weapon_r          (right hand weapon mount)
- weapon_l          (left hand / shield mount)
- sheath_back       (back-mounted weapons when holstered)
- sheath_hip_r      (hip-holstered weapons)
- sheath_hip_l
- head_top          (helmet mount point)
- spine_upper       (cape/cloak attachment)
- shoulder_r        (pauldron mount)
- shoulder_l
- belt_front        (belt accessories)
- belt_back
```

Implementation approach:
1. Create empty GameObjects parented to skeleton bones at socket positions
2. Equipment prefabs instantiate as children of socket transforms
3. Socket transforms include position/rotation offsets per equipment piece
4. Store socket offsets in ScriptableObject data per equipment item

#### Armor: Mesh Merging vs Separate Meshes

**Separate Meshes (most common in Souls-like games):**
- Each armor piece is a separate SkinnedMeshRenderer sharing the character skeleton
- Pros: Hot-swappable, simpler asset pipeline, individual LOD control
- Cons: Multiple draw calls per character (typically 4-8 for full armor set)
- Used by: Dark Souls, Elden Ring, Diablo 3/4, most MMOs

**Mesh Merging (runtime combining):**
- Combine all visible equipment into single SkinnedMeshRenderer at equip time
- Uses `Mesh.CombineMeshes()` with bone remapping
- Pros: Single draw call per character, better batching
- Cons: Rebuild on every equip change, texture atlas required, memory spike during combine
- Used by: Some MMOs with many characters on screen

**Recommended for Dark Fantasy Action RPG:** Separate meshes with SRP Batcher.
- 4-6 equipment slots: Head, Chest, Hands, Legs, Feet, Cape
- Each slot = 1 SkinnedMeshRenderer + 1 material = 1 draw call
- Total per character: 6-8 draw calls (body + equipment slots)
- SRP Batcher groups these efficiently if using same shader variant

#### Body Part Hiding
When armor covers body parts, hide the underlying body mesh sections:
- **Approach A (blend shapes):** Body mesh has blend shapes that shrink covered regions to zero
- **Approach B (material masking):** Discard pixels on body mesh under armor via stencil or clip
- **Approach C (separate body parts):** Body is split into parts matching armor slots; disable renderer on covered parts
- **Recommended:** Approach C for Souls-like games (same approach FromSoftware uses)

### 1.3 Armor Deformation Techniques

**Weight Painting (primary method):**
- Armor meshes share the same skeleton as the base character
- Armor pieces are weight-painted to the same bones as the body region they cover
- For tight-fitting armor: copy weights from the body mesh directly
- For loose armor (robes, capes): paint with slightly different weights to allow overlap movement

**Shrinkwrap (fitting in Blender):**
- Use Shrinkwrap modifier to conform armor mesh to body shape
- Offset value: 0.5-2.0cm depending on armor type (thicker for plate, thinner for leather)
- Apply modifier, then transfer weights from body mesh using Data Transfer modifier

**Blend Shapes (size variation):**
- Create blend shapes for body type variation (muscular, thin, etc.)
- Armor meshes include corresponding blend shapes
- Runtime: apply same blend shape weight to both body and armor

### 1.4 LOD Strategy for Equipped Characters

```text
LOD0 (>30% screen): Full detail, all equipment separate meshes, 4-bone skinning
LOD1 (15-30%):      Simplified equipment, 2-bone skinning, no cloth sim
LOD2 (5-15%):       Merged equipment, simplified skeleton, 1-bone skinning
LOD3 (<5%):         Billboard or ultra-low-poly silhouette, no skeleton
Cull (<2%):         Not rendered
```

Key optimization: At LOD2+, merge all equipment into a single mesh with a texture atlas to reduce draw calls from 6-8 to 1.

### 1.5 Skinned Mesh Renderer Performance Rules

From Unity documentation:
- **Max 4 bone influences per vertex** for optimal performance (configurable: 1, 2, or 4)
- **Single SkinnedMeshRenderer** is roughly 2x faster than two separate ones on the same character
- Using `updateWhenOffscreen = false` (default) significantly reduces CPU cost
- Skinned Motion Vectors increase GPU memory usage -- only enable for hero characters

---

## 2. ENVIRONMENT & WORLD BUILDING

### 2.1 Modular Kit Design

#### Grid and Snap Standards (AAA consensus)

```text
Primary Grid:    1m (100cm) -- walls, floors, basic modules
Secondary Grid:  0.5m (50cm) -- half-walls, trim pieces, detail alignment
Fine Grid:       0.25m (25cm) -- props, small detail placement
Micro Grid:      0.125m (12.5cm) -- texture detail, ornamental trim

Wall Height:     3m (standard room), 4m (grand hall), 6m+ (cathedral)
Wall Width:      Multiples of 1m: 1m, 2m, 3m, 4m, 6m
Door Width:      1.2m (standard), 2m (double), 3m (grand)
Door Height:     2.4m (standard), 3m (grand), 4m+ (boss door)
```

#### Module Piece Categories (per kit, 25-40 pieces minimum)

```text
Structural (10-15 pieces):
  - wall_straight_1m, wall_straight_2m, wall_straight_4m
  - wall_corner_inner, wall_corner_outer
  - wall_door_frame, wall_window_frame
  - wall_end_cap
  - floor_1x1, floor_2x2, floor_4x4
  - ceiling_1x1, ceiling_2x2, ceiling_4x4
  - pillar_base, pillar_mid, pillar_top

Connectors (5-8 pieces):
  - arch_1m, arch_2m
  - stairs_straight, stairs_spiral
  - ramp_1m
  - doorway_standard, doorway_grand
  - bridge_section

Trim and Detail (8-12 pieces):
  - trim_horizontal, trim_vertical
  - trim_corner
  - baseboard, crown_molding
  - window_sill
  - beam_horizontal, beam_vertical
  - bracket, corbel

Damage/Variation (4-6 pieces):
  - wall_damaged_1, wall_damaged_2
  - floor_broken
  - pillar_broken
  - rubble_pile
```

#### Pivot Point Convention
All modular pieces: pivot at **bottom-left-back corner** (or bottom-center for symmetric pieces). This ensures clean snapping when pieces are placed at grid coordinates.

#### UV and Texture Approach
- **Tiling textures:** Use world-space UV projection or box mapping for walls/floors
- **Trim sheets:** 1-2 horizontal trim sheets per kit (2048x2048 or 4096x4096)
- **Atlas per kit:** One shared material with trim sheet reduces draw calls
- Assassin's Creed Origins: ~4,000 triangles for a 6x6m stone block module

### 2.2 Terrain Blending

#### Mesh-to-Terrain Blending
- Use height-based blending in shader: sample terrain heightmap at mesh position
- Blend factor = saturate((mesh_height - terrain_height) / blend_range)
- blend_range typically 0.3-1.0 meters
- Apply terrain texture layers to bottom portion of placed meshes

#### Vertex Color Blending
- Paint vertex colors on environment meshes: R=moss, G=dirt, B=snow, A=damage
- Shader reads vertex color to blend between base material and overlay textures
- Cost-effective, artist-controllable, no extra textures needed

#### Procedural Placement Rules
```text
Rock placement:  Cluster in groups of 3-7, vary scale 0.8-1.3x, random rotation
                 Partially embed in terrain (sink 10-30% below surface)
Trees:           Poisson disk sampling, min distance 2-5m between trunks
                 Avoid slopes > 35 degrees, cluster density near water
Grass/Foliage:   Density falloff from paths, higher near walls/rocks
                 Zero density on slopes > 45 degrees, near buildings
```

### 2.3 Vegetation Rendering

#### LOD Chain for Trees
```text
LOD0 (>15% screen): Full 3D mesh, 2,000-8,000 tris
LOD1 (8-15%):       Simplified mesh, 800-3,000 tris
LOD2 (3-8%):        Card-based (6-12 intersecting planes), 100-500 tris
LOD3/Billboard (<3%): Single billboard quad, 2 tris
```

#### GPU Instancing for Vegetation
- Use `Graphics.DrawMeshInstanced()` or Unity terrain detail system with Draw Instanced enabled
- All instances of same mesh+material rendered in single draw call
- Per-instance data: position, rotation, scale, color tint (passed via MaterialPropertyBlock)
- SpeedTree integration provides built-in wind animation and LOD crossfade

#### Grass Rendering
- Terrain detail system: up to 4,048 detail resolution
- Billboard grass: 2 triangles per tuft, draw distance 60-100m
- Mesh grass: 4-12 triangles per tuft, draw distance 30-50m
- Detail density scale: 0.5-0.8 for performance, 1.0 for screenshots
- Wind: vertex displacement in shader using world-position-based sine waves

### 2.4 Dungeon Generation (Hand-Crafted Feel)

#### BSP (Binary Space Partitioning)
Best for rectangular room layouts:
```text
Parameters:
  - min_room_size: 5-8 cells (prevents tiny rooms)
  - max_depth: 4-6 splits (controls room count)
  - cell_size: 1-3m (affects granularity)
  - split_ratio: 0.4-0.6 (prevents extreme proportions)
  - corridor_width: 2-3 cells

Post-processing for quality:
  1. Remove rooms below minimum area threshold
  2. Connect rooms via L-shaped or straight corridors
  3. Add loops (connect 15-25% of non-adjacent rooms)
  4. Vary room shapes (erode corners, add alcoves)
  5. Place doors at corridor-room boundaries
  6. Apply height variation between connected rooms
```

#### Graph-Based (Enter the Gungeon approach)
1. Define abstract flow graph (room types + connections)
2. Break into composites (loops vs trees)
3. Place rooms depth-first for trees, alternating-end for loops
4. Prefer tight loops and short corridors for central areas
5. Use room templates (prefabs) for hand-crafted feel

#### Making Procedural Look Hand-Crafted
- Mix procedural layout with hand-authored room templates (50+ room prefabs)
- Apply style rules per room type (throne room = large + pillars, prison = small + gates)
- Add environmental storytelling props with placement rules
- Vary lighting intensity and color per room mood
- Break up repetition with 2-3 wall/floor texture variants per biome

### 2.5 Town/City Layout

#### Organic Layout Algorithms
- **L-Systems:** Generate branching road networks from grammar rules
  - Axiom: major road, Rules: branch at angles 30-90 degrees
  - Branch probability decreases with recursion depth
  - Width decreases with depth (main road 6m -> alley 2m)

- **Wave Function Collapse (WFC):**
  - Define tile set with adjacency constraints
  - Collapse tiles from lowest entropy first
  - Tile types: road, building footprint, park, plaza, wall
  - 20-40 unique tiles for convincing variety
  - Shannon entropy = log(sum(weight)) - (sum(weight * log(weight)) / sum(weight))

- **Agent-Based Growth:**
  - Place seed buildings (church, market, castle)
  - Growth agents place buildings along roads
  - Roads extend from existing intersections
  - Buildings face roads, align to road tangent
  - Density decreases from center outward

### 2.6 Biome Transitions

- Transition zone width: 20-50 meters
- Blend factor: smoothstep based on distance from biome boundary
- Layer transitions: ground texture first, then vegetation, then skybox/fog
- Height-based transitions on terrain shader (snow above X altitude)
- Scatter transition props (dead trees at forest-desert boundary, frost on desert-tundra)

### 2.7 Environmental Storytelling

Prop placement rules for narrative:
```text
Battle aftermath:  Scattered weapons, broken shields, arrow clusters in walls
                   Blood decals, overturned furniture, damaged walls
Abandoned room:    Cobwebs in corners, dust particles, toppled chairs
                   Open books, cold hearth with ash, dripping water
Active living:     Warm fire, placed plates, hung clothing, organized shelves
Ritual site:       Candle circles, drawn symbols, bones/skulls, altar with items
Boss approach:     Increasing corpses, warning messages, blood trails
                   Damaged walls showing claw marks, broken weapons
```

---

## 3. LIGHTING & ATMOSPHERE (URP)

### 3.1 URP Lighting Configuration

#### Rendering Path Selection
- **Forward+:** Best for dark fantasy. Supports many lights per cluster without per-object limits.
- **Forward (legacy):** Per-object additional light limit (typically 4-8). Fine for simpler scenes.
- **Deferred:** Better for many lights but limited material variety (no custom lighting models easily).

**Recommendation:** Forward+ for dark fantasy action RPG. Supports dozens of point/spot lights for torches, braziers, magic effects without hitting per-object limits.

#### URP Asset Settings for Dark Fantasy
```text
Main Light:              Per Pixel (directional sun/moon)
Additional Lights:       Per Pixel, limit 8-16 per object (Forward) or unlimited (Forward+)
Shadow Cascades:         4 cascades
Shadow Resolution:       2048 (main light), 512-1024 (additional lights)
Shadow Distance:         80-120m (tune based on level size)
Soft Shadows:            Medium (5x5 tent filter) or High (7x7 tent filter)
HDR:                     Enabled, 32-bit precision
MSAA:                    4x for quality, 2x for performance
Depth Priming:           Auto (reduces overdraw for opaque geometry)
SRP Batcher:             Enabled (essential for batching)
```

### 3.2 Light Probe Placement Strategy

```text
Placement Rules:
1. Place at every significant lighting transition (shadow edge, color change)
2. Grid spacing: 2-3m in gameplay areas, 4-6m in corridors, 8-10m outdoors
3. Add vertical layers: floor level + head height (0m and 1.8m above floor)
4. Dense placement near doors, windows, and light sources
5. Sparse placement in uniformly lit areas
6. Always place at room corners and doorway thresholds

Density by area type:
  - Indoor rooms: 1 probe per 2-4 m^2
  - Corridors: every 2m along length, 2 across width
  - Outdoor open: every 5-10m grid
  - Near light sources: ring of 4-6 probes at light radius boundary
```

### 3.3 Reflection Probe Configuration

#### Interior Probes
```text
Type:             Baked (performance) or Realtime at low frequency
Resolution:       256x256 (small rooms), 512x512 (large halls)
Box Projection:   Enabled (critical for interiors -- prevents infinite parallax)
Box Size:         Match room dimensions closely
Importance:       Higher for prominent reflective surfaces
Update:           On Awake for baked, Via Scripting for realtime
Time Slicing:     Individual Faces (14 frames) for realtime
```

#### Exterior Probes
```text
Type:             Baked with skybox fallback
Resolution:       128x128 (adequate for outdoor)
Box Projection:   Disabled (outdoor reflections are essentially at infinity)
Box Size:         Large encompassing areas (20-50m)
Importance:       Lower priority, skybox provides good fallback
Blend Distance:   5-10m for smooth transitions between probes
```

### 3.4 Volumetric Lighting in URP

URP does not natively support volumetric lighting. Approaches:
1. **Fake volumetric (light shafts):** Cone mesh with additive shader + depth fade
   - Low cost, good for spot lights and god rays
   - Use noise texture for dusty atmosphere effect
2. **Screen-space volumetric fog:** Custom renderer feature with ray marching
   - Sample 16-32 steps along view ray
   - Apply noise for density variation
   - Cost: ~1-2ms on mid-range GPU at quarter resolution
3. **Particle-based fog:** Low-alpha billboards with soft particles
   - 50-200 particles per fog volume
   - Scale 2-5m, lifetime infinite, slow drift animation

### 3.5 Time-of-Day System

```text
Key time points with lighting values:
  Dawn (6:00):    Sun angle 5-15 deg, warm orange (1.0, 0.6, 0.3), intensity 0.3-0.5
                  Fog: thick, warm tint, density 0.02-0.05
  Morning (9:00): Sun angle 30-45 deg, warm white (1.0, 0.9, 0.8), intensity 0.7
  Noon (12:00):   Sun angle 70-90 deg, neutral white (1.0, 1.0, 0.95), intensity 1.0
                  Shadows shortest, harshest contrast
  Dusk (18:00):   Sun angle 5-15 deg, deep orange-red (1.0, 0.4, 0.2), intensity 0.3
                  Fog: medium, purple tint
  Night (22:00):  Moon angle variable, cool blue (0.4, 0.5, 0.7), intensity 0.05-0.15
                  Ambient: very low, blue-purple (0.05, 0.05, 0.1)

Implementation: Lerp between Volume profiles per time state.
Sun rotation: Rotate directional light around X axis over 24h cycle.
Ambient: Gradient skybox with time-varying colors.
```

### 3.6 Indoor/Outdoor Transition

- Use trigger volumes at doorways/cave entrances
- Lerp between outdoor and indoor Volume profiles over 0.5-1.0 seconds
- Swap reflection probes (outdoor skybox -> indoor room probe)
- Adjust ambient intensity (outdoor 0.3-0.5 -> indoor 0.05-0.15)
- Enable/disable fog or switch fog parameters
- Dark Souls approach: dramatic lighting contrast (bright outdoor -> very dark interior)

---

## 4. MESH GENERATION QUALITY

### 4.1 Procedural Mesh Topology Rules

```text
Golden Rules:
1. Quads over triangles -- maintain quad-dominant topology for clean subdivision
2. Edge loops at deformation zones -- every joint needs 3+ edge loops
3. Even polygon density -- no sudden density changes (causes shading artifacts)
4. Consistent face normals -- all faces pointing outward
5. No n-gons (faces with 5+ sides) -- causes unpredictable triangulation
6. Manifold geometry -- every edge shared by exactly 2 faces
7. No zero-area faces or degenerate triangles

Deformation Zone Edge Loops:
  Shoulder:  3-4 loops
  Elbow:     2-3 loops
  Wrist:     2 loops
  Knee:      2-3 loops
  Ankle:     2 loops
  Neck:      3 loops
  Spine:     1 loop per vertebra in range of motion
```

### 4.2 Weapon Mesh Generation (AAA Quality)

#### Triangle Budgets for Weapons
```text
Melee weapons:    3,000-8,000 tris (LOD0), 1,000-3,000 (LOD1), 300-800 (LOD2)
Ranged weapons:   5,000-15,000 tris (LOD0), 2,000-6,000 (LOD1), 500-1,500 (LOD2)
Shields:          2,000-6,000 tris (LOD0), 800-2,000 (LOD1), 200-500 (LOD2)

Reference: Rainbow Six Siege weapons ~15,000 tris, Division FNX45 ~15,000 tris
For dark fantasy melee focus: 5,000-8,000 is the sweet spot
```

#### Proportional Guidelines (Sword)
```text
Total length:    0.9-1.2m (one-handed), 1.3-1.8m (two-handed)
Blade:           60-70% of total length
Guard:           10-15% of total length width
Grip:            15-20% of total length
Pommel:          5-8% of total length

Cross-section:   Diamond (double-edged), wedge (single-edged)
Edge geometry:   Min 2 edge loops for blade edge (catch light properly)
Fuller (blood groove): Inset channel, 50-70% of blade length
Guard detail:    Cross-guard, swept, basket -- 500-1500 tris for ornate guards
Wrapping:        Grip wrap geometry or normal map detail
```

#### Proportional Guidelines (Axe)
```text
Total length:    0.6-0.9m (one-handed), 1.0-1.5m (two-handed)
Head:            25-35% of total length, width 20-40cm
Shaft:           65-75% of total length
Edge:            Curved cutting edge, 2+ edge loops
Beard (hook):    Optional downward extension for Nordic style
```

### 4.3 Building Mesh Generation

#### UV Layout for Tiling Textures
- **World-space UV mapping:** Best for walls and floors (consistent texel density)
- **Texel density target:** 512 pixels per meter (standard), 1024 px/m (hero assets)
- **Tiling:** Set UV scale so texture repeats naturally (1 tile = 1-2 meters of wall)
- **Unique UVs:** Only for trim, ornamental details, and damage decals (UV2 channel)

#### Doorways and Windows
```text
Door opening:    1.2m x 2.4m (standard), 2.0m x 3.0m (grand)
Window opening:  0.8m x 1.2m (standard), 1.5m x 2.0m (gothic arch)
Wall thickness:  0.3-0.5m (stone), 0.15-0.25m (wood)
Frame inset:     0.05-0.1m from wall face
Arch geometry:   8-16 segments for curved arch top
```

### 4.4 LOD Ratios and Screen Percentages

```text
Standard LOD Configuration:
  LOD0:  100% tris, screen threshold >60% (with LOD Bias 2: >30%)
  LOD1:  50% tris,  screen threshold >30% (with LOD Bias 2: >15%)
  LOD2:  25% tris,  screen threshold >10% (with LOD Bias 2: >5%)
  LOD3:  12% tris,  screen threshold >5%  (with LOD Bias 2: >2.5%)
  Cull:  0 tris,    below LOD3 threshold

Unity LOD Bias default: 2.0 (doubles estimated visual size)
Cross-fade duration: 0.5 seconds (LODGroup.crossFadeAnimationDuration)
Fade transition width: 0.3-0.5 (proportion of LOD level range)

Aggressive LOD (recommended for action RPG with many characters):
  LOD0:  100%  at >25% screen
  LOD1:  40%   at >10% screen
  LOD2:  15%   at >3% screen
  Cull:  below 3% screen
```

---

## 5. MATERIAL & TEXTURE QUALITY

### 5.1 PBR Material Reference Values (Metallic/Roughness Workflow)

#### Base Color / Albedo (sRGB)
From Google Filament PBR reference:
- **Non-metals:** sRGB 50-240 (strict), 30-240 (tolerant). Never pure black or white.
- **Metals:** Luminosity 67-100% (sRGB 170-255)

Specific material base colors (sRGB, from physicallybased.info + Filament):

```text
METALS (metallic = 1.0):
  Iron:         (135, 131, 126)    roughness: 0.5-0.8 (raw), 0.2-0.4 (polished)
  Steel:        (155, 155, 155)    roughness: 0.3-0.6
  Gold:         (255, 217, 145)    roughness: 0.1-0.3
  Silver:       (252, 250, 245)    roughness: 0.1-0.3
  Copper:       (250, 190, 158)    roughness: 0.2-0.5
  Bronze:       (250, 230, 150)    roughness: 0.3-0.6
  Brass:        (249, 229, 150)    roughness: 0.2-0.5
  Titanium:     (194, 186, 175)    roughness: 0.3-0.5
  Platinum:     (214, 209, 198)    roughness: 0.1-0.3
  Aluminum:     (232, 234, 234)    roughness: 0.2-0.5
  Chromium:     (140, 142, 141)    roughness: 0.05-0.2

NON-METALS (metallic = 0.0):
  Wood (light):    (190, 160, 115)    roughness: 0.6-0.9
  Wood (dark):     (80, 55, 35)       roughness: 0.5-0.8
  Stone (light):   (180, 170, 155)    roughness: 0.7-0.95
  Stone (dark):    (90, 85, 75)       roughness: 0.6-0.9
  Marble:          (212, 202, 192)    roughness: 0.1-0.3 (polished), 0.5-0.7 (rough)
  Concrete:        (130, 130, 130)    roughness: 0.8-1.0
  Leather:         (75, 45, 25)       roughness: 0.5-0.8
  Fabric:          (100, 85, 70)      roughness: 0.8-1.0
  Skin:            (200, 150, 120)    roughness: 0.3-0.6
  Bone:            (202, 202, 169)    roughness: 0.4-0.7
  Dirt:            (115, 95, 60)      roughness: 0.9-1.0
  Sand:            (112, 98, 59)      roughness: 0.9-1.0
  Rust:            (120, 60, 30)      roughness: 0.7-1.0
  Dried Blood:     (80, 15, 10)       roughness: 0.6-0.9
  Obsidian:        (20, 20, 22)       roughness: 0.05-0.2
  Clay:            (160, 130, 100)    roughness: 0.8-1.0
```

#### Fresnel Reflectance (F0) for Non-Metals
- Most common materials: ~4% (0.04 linear) -- this is the default reflectance
- Water: 2%
- Fabric: 2-4%
- Plastic: 4-5%
- Glass: 4-8% (IOR 1.52)
- Gemstones: 5-16%

#### Minimum Roughness Clamping
From Filament: clamp roughness minimum to 0.089 to avoid half-precision floating point artifacts. In practice, never use roughness below 0.04 (perfectly smooth mirrors don't exist in reality).

### 5.2 Texture Resolution Standards

```text
Asset Type              Albedo    Normal    ORM (AO/Rough/Metal)
Hero Character          2048      2048      2048
Major NPC               2048      2048      1024
Common Enemy            1024      1024      1024
Weapon (hero)           1024      1024      1024
Weapon (common)         512       512       512
Large Prop              1024      1024      512
Medium Prop             512       512       512
Small Prop              256       256       256
Environment Module      2048      2048      1024 (shared trim sheet)
Terrain Layer           1024      1024      512 (tiling)
UI Element              Varies    N/A       N/A

Total texture memory budget (PC): 1-2 GB VRAM for textures
Texture format: BC7 (best quality), BC5 (normals), BC1 (if alpha not needed)
Mipmap: Always enabled for 3D assets. Streaming enabled.
```

### 5.3 Detail Normal Maps

- Apply micro-surface detail (pores, scratches, weave) via blended detail normal map
- Detail normal uses UV2 or tiled UV1 at higher frequency (4-16x base UV scale)
- Blend in shader: `float3 n = BlendNormals(baseNormal, detailNormal * detailStrength)`
- Detail strength typically 0.3-0.7 (subtle is better)
- Resolution: 256x256 or 512x512 tiling textures
- Examples: skin pore detail, chainmail weave, leather grain, stone chipping

### 5.4 Material Layering

For dark fantasy weathering:
```text
Layer Stack (bottom to top):
  1. Base material (stone, metal, wood)
  2. Wear/edge damage (height-based, curvature-based)
  3. Dirt/grime accumulation (top-facing surfaces, cavity)
  4. Moss/organic growth (moisture areas, north-facing)
  5. Snow/frost (top-facing, exposure-based)

Blending method: Height-based blending using material heightmaps
  blend_factor = saturate((height_A - height_B + bias) / contrast)

Curvature-based wear:
  Convex edges: expose bare metal/stone underneath paint/finish
  Concave areas: accumulate dirt, grime, moisture
```

### 5.5 Weathering and Aging

```text
Weathering Techniques:
1. Edge Wear:
   - Use curvature map or baked AO to identify edges
   - Increase roughness on edges (+0.2-0.4)
   - Lighten color on edges (simulate wear through paint/coating)
   - Metallic edges on painted metal surfaces

2. Cavity Dirt:
   - Use inverted AO map to identify cavities
   - Darken albedo in cavities (multiply by 0.5-0.8)
   - Increase roughness in cavities (+0.1-0.3)

3. Moisture/Wetness:
   - Decrease roughness (wet surfaces: roughness *= 0.3-0.5)
   - Darken albedo slightly (multiply by 0.7-0.9)
   - Increase base reflectance (water layer F0 = 0.02)

4. Rust/Corrosion (for metals):
   - Transition metallic to 0 in corroded areas
   - Roughness increases (0.7-1.0)
   - Color shifts to orange-brown (120, 60, 30)
   - Height variation (raised bumpy texture)

5. Age Patina:
   - Green/turquoise tint on copper/bronze surfaces
   - Color: (70, 130, 100) with roughness 0.5-0.7
   - Appears in rain-exposed and cavity areas
```

---

## 6. ANIMATION QUALITY

### 6.1 State Machine Architecture (Combat-Heavy)

#### Layer Structure
```text
Layer 0 - Base/Locomotion (weight 1.0, Override):
  States: Idle, Walk, Run, Sprint, Crouch, CrouchWalk
  Blend Trees: 8-directional locomotion (speed x direction)

Layer 1 - Combat Upper Body (weight 0-1, Override, Avatar Mask = upper body):
  States: LightAttack1-3, HeavyAttack1-2, Block, Parry, CastSpell
  Transitions: Triggered by input, combo windows

Layer 2 - Hit Reactions (weight 0-1, Additive):
  States: HitFront, HitBack, HitLeft, HitRight, Stagger, KnockDown
  Triggered by damage events, interrupts combat layer

Layer 3 - Equipment IK (weight 0-1, Override, Avatar Mask = arms):
  States: WeaponIdle, WeaponAim, ShieldRaise
  IK targets for weapon grip and shield positioning

Layer 4 - Facial/Emotes (weight 0-1, Additive, Avatar Mask = head):
  States: Neutral, Pain, Anger, Fear, Speak
  Blend shapes or bone-based facial animation
```

#### Animator Parameters (typical set)
```text
Float:   Speed, Direction, AimAngle, VerticalSpeed, AttackSpeed
Bool:    IsGrounded, IsCrouching, IsBlocking, IsDead, IsStaggered, InCombat
Trigger: Attack, HeavyAttack, Dodge, Jump, TakeHit, Die, Interact, CastSpell
Int:     ComboIndex, WeaponType, EquipmentState, HitDirection
```

### 6.2 Root Motion vs In-Place

#### Root Motion (recommended for Souls-like combat)
- **Use for:** Attack animations, dodge rolls, backsteps, staggers
- Character position driven by animation curves, not script
- Ensures attack reach matches animation visuals exactly
- `Animator.applyRootMotion = true` during combat states
- Extract root motion: `OnAnimatorMove()` callback for custom handling

#### In-Place (recommended for general locomotion)
- **Use for:** Walk, run, sprint, idle
- Script controls movement speed; animation just plays
- Allows smooth speed transitions and directional changes
- Prevent foot sliding by matching animation speed to move speed
- `Animator.applyRootMotion = false` during locomotion

#### Hybrid Approach (Dark Souls pattern)
```text
Locomotion:  In-place, script-driven movement
Combat:      Root motion for attacks, dodges, staggers
Transitions: Root motion for special transitions (climb, vault, sit)
Boss moves:  Root motion for lunges, charges, area attacks
```

### 6.3 Animation Layers for Equipment

#### Weapon IK Layer
```text
Two-Bone IK on weapon hand:
  - Target: weapon grip socket
  - Hint/Pole: elbow direction bone
  - Weight: 1.0 during combat, 0.0 during locomotion (blend over 0.2s)

Shield positioning:
  - Left arm IK target: shield center grip
  - Block state: raise shield IK target to defensive position
  - Walk state: lower to hip or back mount position
```

#### Avatar Masks
```text
Upper Body mask:   Spine1 and above (arms, hands, head, upper spine)
Lower Body mask:   Hips and below (legs, feet)
Right Arm mask:    Right shoulder, arm, hand
Left Arm mask:     Left shoulder, arm, hand
Head mask:         Neck and head bones
Full Body:         All bones (for reactions, deaths, transitions)
```

### 6.4 Blend Tree Configurations

#### 8-Directional Locomotion
```text
Type: 2D Freeform Directional
Parameters: Speed (0-6), Direction (-180 to 180)

Motion clips at positions:
  (0, 0):      Idle
  (0, 3):      WalkForward
  (0, 6):      RunForward
  (45, 3):     WalkForwardRight
  (90, 3):     WalkRight (strafe)
  (135, 3):    WalkBackwardRight
  (180, 3):    WalkBackward
  (-135, 3):   WalkBackwardLeft
  (-90, 3):    WalkLeft (strafe)
  (-45, 3):    WalkForwardLeft
  // Repeat run variants at speed 6
```

#### Attack Combo Blend
```text
Type: 1D
Parameter: ComboIndex (0-3)

Motions:
  0: LightAttack1
  1: LightAttack2
  2: LightAttack3
  3: HeavyFinisher

Combo window: 0.3-0.5 seconds at end of each attack
Cancel window: start of attack (first 0.1s) for dodge cancel
```

### 6.5 Procedural Animation

```text
Chains/Pendulums:
  - Spring-damper simulation: F = -kx - bv
  - Stiffness (k): 20-80 for chains, 5-20 for cloth
  - Damping (b): 0.5-2.0
  - Update in LateUpdate() after animation

Cloth/Capes:
  - Unity Cloth component on cape mesh
  - Stiffness: 0.2-0.5, Damping: 0.1-0.3
  - Max distance from skinned position: 0.3-0.8m
  - Collision spheres on character bones (spine, shoulders)

Vegetation Wind:
  - Vertex shader displacement using world position
  - Primary wave: sin(time * speed + worldPos.x * frequency) * amplitude
  - Secondary wave: sin(time * 1.7 * speed + worldPos.z * 1.3 * frequency) * amplitude * 0.3
  - Mask by vertex color (green channel = wind influence, 0 at base, 1 at tips)
```

---

## 7. PERFORMANCE OPTIMIZATION

### 7.1 Draw Call Budgets

```text
Platform              Target FPS    Draw Call Budget    SetPass Budget
High-End PC (RTX)     60            3,000-5,000         500-1,000
Mid-Range PC          60            1,500-3,000         300-600
Current Console       60            2,000-4,000         400-800
Current Console       30            4,000-8,000         800-1,500
Mobile (high)         30            200-500             100-200
Mobile (low)          30            100-200             50-100

Key insight from DOOM 2016: 1,331 draw calls total per frame at <16ms
Star Wars Battlefront: ~2,000 draw calls for large outdoor scenes
```

### 7.2 Triangle Budgets (Per Frame)

```text
Platform              Total Triangles/Frame    Characters    Environment
High-End PC           5-10 million             30-40%        50-60%
Mid-Range PC          2-5 million              25-35%        55-65%
Current Console       3-8 million              25-35%        55-65%

Per-category breakdown (PC, 60fps, 5M tri budget):
  Player character:      40,000-60,000 (1-1.2%)
  Active enemies (x10):  150,000-350,000 (3-7%)
  Background NPCs:      50,000-150,000 (1-3%)
  Environment:           2,500,000-3,500,000 (50-70%)
  Props/Decor:           500,000-1,000,000 (10-20%)
  VFX/Particles:         200,000-500,000 (4-10%)
  UI/HUD:                10,000-50,000 (<1%)

Reference data:
  Infamous Second Son: 11 million polygons rendered regularly
  The Division: 5-6 million triangles at 60fps
  Street Fighter 5 stages: 400,000-500,000 background at 60fps
```

### 7.3 Texture Memory Budgets

```text
Platform          Total VRAM Available    Texture Budget    Streaming Pool
High-End PC       8-12 GB                2-4 GB            1-2 GB
Mid-Range PC      4-6 GB                 1-2 GB            512 MB-1 GB
Current Console   8-16 GB (shared)       1.5-3 GB          1-2 GB
Mobile            1-3 GB (shared)        200-500 MB        100-200 MB

Compression ratios (vs uncompressed RGBA):
  BC7:   4:1 (best quality, all platforms)
  BC3:   4:1 (with alpha)
  BC1:   6:1 (no alpha, acceptable quality)
  BC5:   4:1 (2-channel, ideal for normal maps)
  ASTC:  4:1 to 12:1 (mobile, quality varies with block size)

Always use texture streaming for open-world games.
Mipmap streaming: load only mip levels needed for current view distance.
```

### 7.4 Occlusion Culling Strategy

```text
Static Occlusion (baked):
  - Mark large opaque objects as Occluder Static (walls, floors, terrain)
  - Mark all renderable objects as Occludee Static
  - Bake with cell size matching level modularity (1-2m for interiors, 4-8m outdoors)
  - Effective for Souls-like games with many walls and corridors

Dynamic Occlusion:
  - Camera.layerCullDistances[] for per-layer cull distances
  - Small props: cull at 50-80m
  - Medium props: cull at 80-120m
  - Large structures: cull at 200-500m
  - Characters: cull at 100-150m

Frustum Culling (automatic):
  - Unity culls objects outside camera frustum automatically
  - Ensure accurate bounds on all renderers
  - LODGroup.RecalculateBounds() after any mesh changes
```

### 7.5 LOD Group Configurations (AAA Standard)

```text
Characters:
  LOD0: 100% (>25% screen)
  LOD1: 50%  (>12% screen) - reduce face detail, fingers merge
  LOD2: 25%  (>5% screen)  - simplified silhouette, no face
  Cull: <2% screen

Environment Props:
  LOD0: 100% (>15% screen)
  LOD1: 40%  (>8% screen)
  LOD2: 15%  (>3% screen)
  LOD3: 5%   (>1% screen)  - optional for very common objects
  Cull: <1% screen

Vegetation:
  LOD0: Full mesh (>10% screen)
  LOD1: Simplified (>5% screen)
  LOD2: Billboard/Cards (>1% screen)
  Cull: <1% screen

Buildings:
  LOD0: Full detail interior+exterior (>20% screen)
  LOD1: Exterior only, simplified (>8% screen)
  LOD2: Block shape with baked texture (>2% screen)
  Cull: <1% screen
```

### 7.6 Batching & Instancing Strategy

```text
SRP Batcher (primary strategy for URP):
  - Enable in URP Asset settings
  - All objects using same shader variant batch together
  - Does NOT reduce draw calls but reduces CPU cost per draw call
  - Incompatible with MaterialPropertyBlock -- use per-material instead
  - Verify in Frame Debugger: look for "SRP Batch" entries

GPU Instancing (for repeated meshes):
  - Best for: vegetation, rocks, debris, modular pieces
  - Same mesh + same material = single draw call for all instances
  - Enable "GPU Instancing" on material
  - Not compatible with SkinnedMeshRenderer
  - Static batching max: 64K vertices/indices per batch

Batching Priority:
  1. SRP Batcher for all unique objects (characters, unique props)
  2. GPU Instancing for repeated meshes (vegetation, rocks, modular env)
  3. Static Batching for small static props sharing materials
  4. Dynamic Batching only for very small meshes (<300 verts) -- usually not worth it
```

---

## 8. VFX QUALITY

### 8.1 Particle System Budgets

```text
VFX Budget Guidelines (PC, 60fps):
  Max active particle systems per scene:     50-100
  Max particles per system (combat effect):  50-200
  Max particles per system (ambient):        20-100
  Max total particles on screen:             2,000-5,000
  Max overdraw ratio:                        3-4x (screen pixels redrawn)
  VFX draw call budget:                      50-150 (10-15% of total budget)

Per-Effect Budgets:
  Weapon swing trail:        1 system, 20-50 particles, 1 draw call
  Hit impact:                2-3 systems, 30-80 particles, 2-4 draw calls
  Spell cast:                3-5 systems, 50-150 particles, 3-6 draw calls
  Boss ability:              5-8 systems, 100-300 particles, 5-10 draw calls
  Environmental ambient:     1-2 systems, 20-50 particles, 1-2 draw calls
  Torch/fire:                2-3 systems, 30-80 particles, 2-4 draw calls
  Footstep dust:             1 system, 5-15 particles, 1 draw call
```

### 8.2 Shader VFX vs Particle VFX

```text
Use SHADER-BASED VFX for:
  - Screen-space effects (damage vignette, screen shake, chromatic aberration)
  - Material effects (dissolve, hologram, force field, damage overlay)
  - Full-screen post-processing (bloom, color grade shift)
  - Persistent auras (glowing outlines, selection highlights)
  - Water/lava surface animation
  - Distortion/heat haze (screen-space refraction)
  Cost: Fixed per-pixel, no particle overhead

Use PARTICLE-BASED VFX for:
  - Physical particles (sparks, embers, debris, blood splatter)
  - Volumetric effects (smoke, fog, clouds)
  - Projectile trails (streaks, ribbons)
  - Burst effects (explosions, impacts, spawns)
  - Environmental ambient (dust motes, fireflies, ash)
  Cost: Per-particle, overdraw-dependent

HYBRID approach (most effects):
  - Shader: core effect (dissolve, glow)
  - Particles: embellishment (sparks, smoke, debris)
  - Example: death dissolve = shader dissolve + particle ash/embers
```

### 8.3 Screen-Space Combat Feedback

```text
Hit Confirmation Stack (applied in 1-3 frames):
  1. Screen shake:     Amplitude 0.05-0.2m, duration 0.1-0.3s, frequency 15-25Hz
                       Reduce amplitude by 50% each frame (exponential decay)
  2. Hit freeze:       Pause game time 0.03-0.1s (heavy hits longer)
                       Character-only freeze (world continues) for responsiveness
  3. Chromatic aberration: Intensity 0.3-0.8, decay over 0.2s
  4. Vignette pulse:   Intensity 0.3-0.6, red tint, decay over 0.3s
  5. Directional indicator: Arrow/flash toward damage source, 0.5s duration
  6. Camera zoom:      Subtle 2-5% FOV reduction on heavy hit, 0.2s recovery

Damage Taken Stack:
  1. Screen flash:     Red tint overlay, 0.1s duration, 0.3 alpha
  2. Vignette:         Red vignette, intensity proportional to damage%
  3. Post-process:     Desaturation at low health (lerp saturation 1.0 -> 0.3)
  4. Screen crack:     Overlay texture at critical health
```

### 8.4 Environmental VFX Layering

```text
Atmosphere Stack (layer from bottom to top):
  1. Ground fog:       Low-lying particle fog, height 0-1m, soft particles
                       50-100 billboard particles, slow drift, alpha 0.1-0.3
  2. Dust motes:       Small bright particles in light beams
                       20-50 particles per light shaft, slow float, alpha 0.3-0.5
  3. Ambient particles: Fireflies, embers, spores (biome-dependent)
                       10-30 particles, medium area, slow movement
  4. Weather:          Rain (GPU particles, 500-1000), snow (200-500)
                       Screen-space rain drops on camera lens for immersion
  5. God rays:         Volumetric light cone meshes or screen-space ray march
                       1-3 per scene, alpha 0.1-0.3

Dark Fantasy Specific Effects:
  - Corruption tendrils: Animated UV scroll on tendril meshes + particle wisps
  - Soul/essence wisps: 5-10 glowing particles with trail, slow orbit
  - Candle flicker: Point light with noise-driven intensity (random range 0.7-1.0)
  - Dripping water: Small particle emitters at ceiling contact points, splash on ground
  - Torch smoke: 20-40 particles, upward drift, alpha fade, lit by torch light
```

---

## APPENDIX A: DARK FANTASY SPECIFIC GUIDELINES

### Color Palette
```text
Primary Palette (dark, desaturated):
  Dark stone:     (45, 42, 38)      -- walls, floors
  Aged wood:      (65, 50, 35)      -- furniture, doors
  Tarnished metal:(90, 85, 75)      -- armor, weapons
  Dark leather:   (55, 35, 20)      -- straps, covers
  Bone/ivory:     (180, 170, 150)   -- skulls, ornaments

Accent Palette (saturated, used sparingly):
  Blood red:      (140, 20, 15)     -- damage, corruption
  Soul blue:      (60, 120, 180)    -- magic, wisps
  Poison green:   (40, 140, 60)     -- venom, corruption variant
  Holy gold:      (200, 170, 80)    -- divine, legendary items
  Void purple:    (80, 30, 120)     -- dark magic, portals
  Fire orange:    (220, 130, 40)    -- flames, warmth

Lighting Palette:
  Torch light:    (255, 180, 100)   temperature ~3000K
  Moonlight:      (150, 170, 220)   temperature ~8000K
  Magic glow:     Brand-specific color at 2-3x intensity
  Ambient dark:   (15, 15, 20)      very dark blue-black
```

### Post-Processing Profile (Dark Fantasy URP)
```text
Tonemapping:     ACES
Bloom:           Threshold 0.9, Intensity 0.3-0.5, Scatter 0.7
                 Tint: warm (1.0, 0.95, 0.9)
Color Grading:   Lift shadows toward blue-purple, Gamma neutral, Gain toward warm
                 Contrast +10-20, Saturation -10 to -20 (desaturated look)
Vignette:        Intensity 0.25-0.35, Smoothness 0.4
SSAO:            Intensity 1.0-2.0, Radius 0.3-0.5 (strong ambient shadows)
                 Direct lighting strength 0.3-0.5
Film Grain:      Intensity 0.1-0.2, Type: Medium
Chromatic Ab:    Intensity 0.05 (very subtle, increase on damage)
```

---

## APPENDIX B: UNITY C# IMPLEMENTATION CONSTANTS

These constants can be directly used in Unity C# templates:

```csharp
public static class AAABudgets
{
    // Triangle budgets
    public const int HERO_CHARACTER_TRIS = 50000;
    public const int ENEMY_MAJOR_TRIS = 30000;
    public const int ENEMY_COMMON_TRIS = 20000;
    public const int NPC_BACKGROUND_TRIS = 10000;
    public const int WEAPON_MELEE_TRIS = 6000;
    public const int WEAPON_RANGED_TRIS = 10000;
    public const int SHIELD_TRIS = 4000;
    public const int PROP_LARGE_TRIS = 5000;
    public const int PROP_MEDIUM_TRIS = 2000;
    public const int PROP_SMALL_TRIS = 500;
    public const int ENV_MODULE_TRIS = 4000; // per 6x6m module
    public const int VEGETATION_TREE_TRIS = 5000;
    public const int VEGETATION_BUSH_TRIS = 1000;

    // LOD ratios
    public static readonly float[] LOD_RATIOS = { 1.0f, 0.5f, 0.25f, 0.12f };
    public static readonly float[] LOD_SCREEN_PCTS = { 0.25f, 0.12f, 0.05f, 0.02f };

    // Draw call budget (60fps PC)
    public const int DRAW_CALL_BUDGET = 3000;
    public const int SETPASS_BUDGET = 600;
    public const int VFX_DRAW_CALL_BUDGET = 150;

    // Texture sizes
    public const int TEX_HERO = 2048;
    public const int TEX_ENEMY = 1024;
    public const int TEX_PROP_LARGE = 1024;
    public const int TEX_PROP_MEDIUM = 512;
    public const int TEX_PROP_SMALL = 256;
    public const int TEX_ENV_TRIMSHEET = 2048;

    // Particle budgets
    public const int MAX_PARTICLE_SYSTEMS = 80;
    public const int MAX_PARTICLES_TOTAL = 4000;
    public const int MAX_PARTICLES_PER_EFFECT = 200;

    // Modular grid
    public const float GRID_PRIMARY = 1.0f;
    public const float GRID_SECONDARY = 0.5f;
    public const float GRID_FINE = 0.25f;
    public const float WALL_HEIGHT_STANDARD = 3.0f;
    public const float WALL_HEIGHT_GRAND = 4.0f;
    public const float WALL_HEIGHT_CATHEDRAL = 6.0f;
    public const float DOOR_WIDTH_STANDARD = 1.2f;
    public const float DOOR_HEIGHT_STANDARD = 2.4f;

    // Shadow settings
    public const int SHADOW_CASCADES = 4;
    public const int SHADOW_RES_MAIN = 2048;
    public const int SHADOW_RES_ADDITIONAL = 512;
    public const float SHADOW_DISTANCE = 100f;

    // Light probes
    public const float PROBE_SPACING_INDOOR = 2.5f;
    public const float PROBE_SPACING_CORRIDOR = 2.0f;
    public const float PROBE_SPACING_OUTDOOR = 8.0f;

    // Bone limits
    public const int MAX_BONES_PER_VERTEX = 4;
    public const int MAX_SKELETON_BONES = 75; // recommended for mobile compat
    public const int MAX_SKELETON_BONES_PC = 150;

    // Animation
    public const float COMBO_WINDOW_DURATION = 0.4f;
    public const float DODGE_CANCEL_WINDOW = 0.1f;
    public const float HIT_FREEZE_DURATION = 0.05f;
    public const float SCREEN_SHAKE_DECAY = 0.5f;
}

public static class PBRValues
{
    // Metallic/Roughness reference (linear space)
    public static readonly Color IRON_COLOR = new Color(0.531f, 0.512f, 0.494f);
    public static readonly Color GOLD_COLOR = new Color(1.000f, 0.851f, 0.569f);
    public static readonly Color SILVER_COLOR = new Color(0.988f, 0.980f, 0.961f);
    public static readonly Color COPPER_COLOR = new Color(0.980f, 0.745f, 0.620f);
    public static readonly Color BRONZE_COLOR = new Color(0.980f, 0.902f, 0.588f);
    public static readonly Color STEEL_COLOR = new Color(0.608f, 0.608f, 0.608f);

    // Non-metal defaults
    public const float DEFAULT_REFLECTANCE = 0.04f; // 4% F0 for most dielectrics
    public const float MIN_ROUGHNESS = 0.089f; // Filament recommendation

    // Dark fantasy palette (sRGB, divide by 255 for Unity Color)
    public static readonly Color DARK_STONE = new Color(45/255f, 42/255f, 38/255f);
    public static readonly Color AGED_WOOD = new Color(65/255f, 50/255f, 35/255f);
    public static readonly Color TARNISHED_METAL = new Color(90/255f, 85/255f, 75/255f);
    public static readonly Color DARK_LEATHER = new Color(55/255f, 35/255f, 20/255f);
    public static readonly Color BONE_IVORY = new Color(180/255f, 170/255f, 150/255f);
    public static readonly Color BLOOD_RED = new Color(140/255f, 20/255f, 15/255f);
    public static readonly Color SOUL_BLUE = new Color(60/255f, 120/255f, 180/255f);
    public static readonly Color HOLY_GOLD = new Color(200/255f, 170/255f, 80/255f);
    public static readonly Color TORCH_LIGHT = new Color(1.0f, 0.706f, 0.392f);
    public static readonly Color MOONLIGHT = new Color(0.588f, 0.667f, 0.863f);
}
```

---

## APPENDIX C: RENDERING PIPELINE REFERENCE (DOOM 2016)

From Adrian Courreges' DOOM 2016 graphics study -- a useful reference for dark atmosphere rendering:

```text
Frame Statistics:
  Total Draw Calls:           1,331
  Textures Used:              132
  Render Targets:             50
  Frame Time:                 <16ms (60fps)

Shadow System:
  Shadow Atlas:               8192x8192 depth buffer
  Static shadow caching:      Only dynamic meshes re-render each frame

Lighting:
  Clustered Forward:          3,072 clusters (16x8x24 frustum subdivision)
  Per-Cluster Capacity:       256 lights, 256 decals, 256 cubemaps
  Depth Slices:               Logarithmic distribution

Reflections:
  Screen-Space Reflections:   Ray-traced from depth/normal buffers
  Static Cubemaps:            128x128 resolution, dozens per level

Post-Processing:
  Bloom:                      Quarter-resolution HDR + Gaussian blur layers
  TAA:                        Velocity maps + frame reprojection
  Tonemapping:                Filmic (Uncharted 2 equation)

Particles:
  Simulation:                 Compute shader (position, velocity, lifetime)
  Collision:                  Reads depth/normal buffers
  Lighting Atlas:             4096 resolution, variable tile sizes
```

---

## APPENDIX D: SCENE COMPOSITION BUDGET EXAMPLE

Budget for a typical dark fantasy dungeon room (60fps, PC):

```text
Asset                        Count    Tris Each    Total Tris    Draw Calls
Player character (equipped)  1        55,000       55,000        7
Enemy (common)               3        20,000       60,000        12
Enemy (elite)                1        35,000       35,000        5
Floor modules                8        1,500        12,000        1*
Wall modules                 16       2,000        32,000        1*
Ceiling modules              8        1,000        8,000         1*
Pillars                      4        3,000        12,000        1*
Door frames                  2        2,000        4,000         1*
Torches                      6        500          3,000         1*
Props (barrels, crates)      8        800          6,400         1*
Props (table, chairs)        4        1,500        6,000         1*
Decor (cobwebs, chains)      12       200          2,400         1*
Weapons (dropped)            3        5,000        15,000        3
VFX (torch fire)             6        --           ~2,000        6
VFX (ambient dust)           1        --           ~500          1
Decals (blood, cracks)       8        2            16            4
                                                   -----------   --------
TOTAL                                              ~254,000      ~46

* Instanced/batched via SRP Batcher (same shader, different material properties)

Remaining budget for LODs, shadows, post-processing overhead: ~4.7M triangles
This allows comfortable headroom for the full scene at 60fps.
```
