# AAA-Quality 3D Asset Generation for VeilBreakers

**Researched:** 2026-03-19
**Domain:** AI 3D Generation Post-Processing, PBR Quality Standards, Dark Fantasy Art Direction, Interior Design, Equipment Systems, Blender-to-Unity Pipeline
**Confidence:** HIGH

---

## 1. Model Quality Pipeline: From AI Slop to AAA

### 1.1 What Makes AI-Generated Models Look Bad

AI model generators (Tripo3D, Meshy, etc.) produce raw meshes with consistent, predictable defects. Understanding these is the first step to fixing them.

**Topology Problems:**
- **Dense triangle soup**: AI models bake surface detail into extremely high polygon counts (often 200k-2M tris) rather than using intelligent topology. This creates lighting artifacts, poor UV unwrapping, and meshes that deform incorrectly for animation.
- **Non-manifold edges**: Holes, gaping surfaces in unseen areas, floating vertices creating shadow artifacts.
- **Double-layer surfaces**: Internal duplicate faces that waste render budget and cause z-fighting.
- **No edge flow**: Edges follow no logical path around deformation zones (eyes, joints, bends). Animation becomes impossible without retopology.
- **Poles everywhere**: N-poles (5+ edge vertices) and E-poles (3 edge vertices) placed randomly instead of strategically cause pinching during subdivision and deformation.

**Texture Problems:**
- **Blurry, low-resolution textures**: AI generators typically output 512x512 or 1024x1024 textures that look acceptable at thumbnail size but fall apart at game-view distances.
- **UV overlapping and bleeding**: Overlapping UV islands cause texture bleeding artifacts. Poor UV layout wastes texture memory.
- **Baked lighting in albedo**: AI often bakes ambient occlusion and directional lighting directly into the albedo/diffuse texture, making the asset impossible to light properly in a game engine.
- **No PBR channel separation**: Raw AI output often comes as a single color texture with no metallic, roughness, normal, or AO maps.
- **Texture seam visibility**: UV seam locations are often placed on visible areas with no blending, creating hard color discontinuities.

**Structural Problems:**
- **Wrong scale**: Models arrive at arbitrary scales, not matching Unity's 1 unit = 1 meter convention.
- **Origin point misplaced**: Pivot points are at world origin or arbitrary locations instead of logical object centers (bottom center for props, hip for characters).
- **No LOD consideration**: Single-detail mesh with no optimization strategy for distance rendering.

### 1.2 The Post-Processing Pipeline: Tripo3D Output to AAA Quality

Our existing MCP toolkit already implements most of these steps. Below is the complete pipeline with what we HAVE vs. what we NEED.

```
STEP 1: AI Generation (Tripo3D)
  [HAVE] tripo_client.py - text-to-model, image-to-model
  [HAVE] Tripo v2.5 with PBR output, v3.0 with improved topology

STEP 2: Import & Initial Cleanup
  [HAVE] mesh_auto_repair - remove doubles, fill holes, recalc normals
  [HAVE] mesh_analyze_topology - A-F grading, non-manifold detection
  [NEED] Auto-scale normalization (detect bounding box, scale to target)
  [NEED] Origin point correction (auto-detect base, set pivot)
  [NEED] Delete internal/double-layer faces automatically

STEP 3: Retopology
  [HAVE] mesh_retopologize - Quadriflow with target face count
  [NEED] Per-asset-type poly budget presets (see Section 1.3)
  [NEED] Adaptive density - more polys at deformation zones, fewer at flat areas
  [NEED] Edge loop insertion at animation-critical zones (eyes, mouth, joints)

STEP 4: UV Unwrap
  [HAVE] uv_unwrap_xatlas - automatic UV unwrapping
  [HAVE] uv_pack_islands - island packing
  [HAVE] uv_equalize_density - texel density normalization
  [NEED] Smart seam placement (hide seams at natural edges, material boundaries)
  [NEED] Per-asset-type texel density targets

STEP 5: Texture Enhancement
  [HAVE] esrgan_runner.py - 4x texture upscaling via Real-ESRGAN
  [HAVE] texture_ops.py - HSV adjustment, seam blending, wear map, tileable
  [HAVE] texture_create_pbr - full PBR node tree setup
  [HAVE] texture_bake - high-to-low-poly baking (normal, AO, combined)
  [NEED] Albedo de-lighting (remove baked lighting from AI textures)
  [NEED] PBR channel extraction from single AI texture
  [NEED] Style transfer / color grading to match VeilBreakers palette

STEP 6: LOD Generation
  [HAVE] pipeline_lod.py - LOD0-LOD3 via Decimate modifier
  [HAVE] _LOD{N} naming convention (Unity auto-imports)
  [NEED] Per-asset-type LOD ratio presets

STEP 7: Validation & Export
  [HAVE] mesh_check_game_ready - topology, budget, UV, material, naming, transforms
  [HAVE] texture_validate - resolution, format, colorspace, UV coverage
  [HAVE] pipeline_runner.py - validate_export for FBX/GLB
  [HAVE] export_fbx, export_gltf handlers
  [NEED] Automated full-pipeline validation checklist per asset type
```

### 1.3 Polygon Budgets by Asset Type

Based on industry standards for third-person dark fantasy RPG (PC target, comparable to Elden Ring / Diablo IV viewing distances):

| Asset Type | LOD0 (Close) | LOD1 (Mid) | LOD2 (Far) | LOD3 (Distant) | Notes |
|---|---|---|---|---|---|
| **Hero Character** (player, boss) | 30,000-50,000 | 15,000-25,000 | 7,500-12,000 | 3,000-5,000 | Includes body + armor + weapon. LOD0 for close-up cutscenes. |
| **Standard Mob** | 8,000-15,000 | 4,000-7,500 | 2,000-3,500 | 800-1,500 | Spawned in groups of 5-20. Budget critical. |
| **NPC** | 15,000-25,000 | 7,500-12,000 | 3,500-6,000 | 1,500-3,000 | Conversation distance matters. |
| **Weapon (held)** | 3,000-8,000 | 1,500-4,000 | 500-1,500 | 200-500 | Higher budget for 1st-person or inspection view. |
| **Shield** | 2,000-5,000 | 1,000-2,500 | 500-1,000 | 200-500 | Visible from both sides. |
| **Small Prop** (cup, potion, key) | 500-2,000 | 250-1,000 | 100-500 | -- | Often culled at distance. |
| **Medium Prop** (chair, barrel, crate) | 1,000-4,000 | 500-2,000 | 250-1,000 | 100-500 | Most common interior object. |
| **Large Prop** (table, bed, wardrobe) | 2,000-6,000 | 1,000-3,000 | 500-1,500 | 250-750 | |
| **Building Exterior** | 5,000-15,000 | 2,500-7,500 | 1,000-3,500 | 500-1,500 | Shell only. Interior separate. |
| **Building Interior** (per room) | 3,000-8,000 | 1,500-4,000 | -- | -- | Only LOD0-1 needed (culled when outside). |
| **Furniture Set** (per room) | 5,000-15,000 | 2,500-7,500 | -- | -- | Sum of all furniture in one room. |
| **Environment Piece** (rock, tree, ruin) | 2,000-8,000 | 1,000-4,000 | 500-2,000 | 200-800 | Instanced heavily. Budget per instance. |
| **Terrain Chunk** (64x64m) | 16,384 | 4,096 | 1,024 | 256 | Quadtree LOD in Unity. |

**LOD Ratios for our pipeline_lod.py**: Default `[1.0, 0.5, 0.25, 0.1]` is good. Consider per-type presets:
- Characters: `[1.0, 0.5, 0.25, 0.1]` (standard 4-level)
- Props: `[1.0, 0.5, 0.15]` (3-level, aggressive final)
- Buildings: `[1.0, 0.5, 0.2, 0.07]` (4-level, very aggressive distant)
- Mobs: `[1.0, 0.5, 0.25, 0.08]` (aggressive LOD3 for large groups)

### 1.4 Texture Resolution Standards

Based on texel density targets for third-person dark fantasy RPG at standard PC viewing distance:

**Base texel density target: 10.24 px/cm (industry standard)**

| Asset Type | Texture Size | Channels | Notes |
|---|---|---|---|
| **Hero Character** | 2048x2048 (body) + 1024x1024 (face detail) | Albedo, Normal, Metallic/Roughness/AO packed | Face gets dedicated texture for close-up quality. |
| **Standard Mob** | 1024x1024 | Albedo, Normal, M/R/AO packed | Single texture atlas for the full creature. |
| **NPC** | 2048x2048 | Albedo, Normal, M/R/AO packed | Conversation distance requires decent quality. |
| **Weapon (held)** | 1024x1024 | Albedo, Normal, M/R/AO packed | Higher density exception: 2048 for inspectable weapons. |
| **Small Prop** | 256x256 to 512x512 | Albedo, Normal | AO/roughness often baked into albedo for small props. |
| **Medium Prop** | 512x512 to 1024x1024 | Albedo, Normal, M/R/AO packed | |
| **Large Prop** | 1024x1024 | Albedo, Normal, M/R/AO packed | |
| **Building Exterior** | 2048x2048 (trim sheet) | Albedo, Normal, M/R/AO packed | Trim sheet shared across building style. |
| **Building Interior Walls** | 1024x1024 (tiling) | Albedo, Normal, M/R/AO packed | Tileable textures, not unique. |
| **Furniture** | 512x512 to 1024x1024 | Albedo, Normal, M/R/AO packed | Per-piece or atlas for room set. |
| **Terrain** | 2048x2048 (tiling, per-biome) | Albedo, Normal, M/R/AO packed | 4-8 tiling layers blended via splatmap. |

**Channel Packing Strategy** (reduces draw calls and memory):
- **Albedo**: RGB = color, A = opacity (if needed)
- **Normal**: RG = normal XY (BC5/BC7 compression), B = unused or height
- **M/R/AO Pack**: R = Metallic, G = Roughness, B = AO (single texture, 3 channels)

**Upscaling Pipeline** (our existing ESRGAN):
1. Tripo outputs 1024x1024 albedo
2. ESRGAN 4x upscale to 4096x4096
3. Downscale to target resolution (2048 or 1024) with sharpening
4. This produces significantly better quality than the raw 1024 due to ESRGAN's learned detail hallucination

### 1.5 PBR Material Quality: Professional vs. Cheap

What separates AAA PBR from amateur work is NOT the shader -- it is the texture authoring. Both use the same Principled BSDF. The difference is in the data.

**What makes textures look CHEAP:**
- Flat, uniform roughness (every pixel the same value)
- No roughness variation = everything looks like plastic
- Metallic is 0 or 1 everywhere with no transition zones
- Normal map has no macro surface variation (only micro bumps)
- No wear patterns (edges are pristine, crevices are clean)
- Color is uniformly saturated (no value variation, no color temperature shifts)
- AO is missing or too strong (dark halos instead of subtle occlusion)

**What makes textures look PROFESSIONAL (AAA standards):**

1. **Roughness Variation is King**: A single material should have roughness ranging from 0.2 to 0.9 within it. Edges are smoother (worn), crevices are rougher (dust accumulation), flat surfaces have subtle variation (fingerprints, use patterns). This is the #1 differentiator.

2. **Micro-Detail in Normal Maps**: Beyond the primary form, add subtle surface noise -- grain on wood, pores on skin, casting marks on metal, weave pattern on fabric. Use a detail normal map blended at 2x UV tiling for extra resolution without extra texture memory.

3. **Wear Patterns Follow Physics**:
   - **Edges wear first** (lighter color, lower roughness, exposed metal on painted surfaces)
   - **Crevices accumulate dirt** (darker, higher roughness)
   - **Top surfaces collect dust** (slightly lighter, higher roughness)
   - **High-contact areas show use** (handles are polished, steps are scuffed)
   - Our `handle_generate_wear_map` already computes per-vertex curvature for this

4. **Color Temperature Variation**: Even a "gray stone wall" should shift from warm gray (sun-facing) to cool gray (shadow-facing). Break up large surfaces with subtle hue shifts.

5. **Material Transitions**: Where two materials meet (wood meeting metal, stone meeting mortar), add a blending zone in the roughness/color, not a hard line.

6. **AO is Subtle**: Ambient occlusion should darken crevices by 10-30%, not create black halos. Our bake_textures handler with `bake_type="AO"` does this correctly when samples are sufficient (32+).

---

## 2. Consistent Art Style System

### 2.1 How AAA Studios Enforce Consistent Art Style

The core principle: **Constrain the parameter space, not the creativity.**

1. **Master Material Library**: Create a set of 20-40 base materials that ALL assets reference. No artist creates materials from scratch. Example set for dark fantasy:
   - Stone (3 variants: carved, rough, mossy)
   - Wood (3 variants: aged oak, charred, rotting)
   - Metal (4 variants: iron, bronze, rusted iron, blackened steel)
   - Fabric (3 variants: burlap, silk, leather)
   - Organic (3 variants: skin, bark, bone)
   - Special (2 variants: crystal/gem, enchanted/glowing)

2. **Color Palette Lock**: Define exact HSV ranges per material type. All stone must fall within H:20-40, S:5-15, V:25-55. All wood within H:15-35, S:20-45, V:20-50. Enforce via automated validation.

3. **Roughness Range Lock**: Each material type has a permitted roughness range. Stone: 0.6-0.9. Polished metal: 0.1-0.3. Leather: 0.5-0.8. Fabric: 0.7-1.0.

4. **Texel Density Uniformity**: All assets in the same scene must have matching texel density (10.24 px/cm baseline). Our `uv_equalize_density` handler already does this.

### 2.2 VeilBreakers Dark Fantasy Color Palette

Reference points: Dark Souls III, Elden Ring, Diablo IV, Darkest Dungeon (for 2D reference).

**Primary Palette (environments, buildings, terrain):**
| Material | Hex Range | HSV Range | Notes |
|---|---|---|---|
| Dark Stone | #2A2520 to #5C5347 | H:25-35, S:10-20, V:14-35 | Foundation of the world. Cool undertone. |
| Aged Wood | #3B2E1F to #6B5438 | H:25-35, S:30-50, V:12-42 | Warm but desaturated. Never orange. |
| Rusted Iron | #4A3525 to #7A5840 | H:20-30, S:35-55, V:15-48 | Dominant metal. Brown-red undertone. |
| Moss/Growth | #2A3520 to #4A5538 | H:90-130, S:20-40, V:14-35 | Subtle green, never vibrant. |
| Bone/Ivory | #8A7B65 to #C4B8A0 | H:35-45, S:15-30, V:40-77 | Lightest neutral in palette. |

**Accent Palette (weapons, magic, UI highlights):**
| Material | Hex Range | Notes |
|---|---|---|
| Blood Red | #6B1520 to #9A2030 | Desaturated. Not fire-engine red. |
| Arcane Blue | #1A2540 to #3050A0 | Deep, cold. For magic effects. |
| Cursed Gold | #8A7520 to #C4A830 | Tarnished, not shiny. Treasure/royalty. |
| Ember Orange | #8A4510 to #C46820 | Warm. Torchlight, fire, enchantments. |
| Void Purple | #2A1535 to #5A3070 | Corruption, dark magic. |

**Rules:**
- Environment saturation NEVER exceeds 40% (keeps the dark, muted feel)
- Only magic effects and UI elements may exceed 60% saturation
- Value range for environments: 10-50% (dark world, not bright)
- One accent color per scene focal point (a single red banner in a gray hall)

### 2.3 Material Library System for the MCP Toolkit

Our existing `_building_grammar.py` already defines material names per architectural style. We need to extend this into a shared material library that ALL handlers reference.

**Proposed structure:**
```python
MATERIAL_LIBRARY = {
    "stone_dark": {
        "base_color": (0.16, 0.14, 0.12),
        "roughness": 0.82,
        "roughness_variation": 0.15,  # +/- from base
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 2.0,  # UV tiling for detail normal
        "wear_intensity": 0.3,  # edge wear amount
    },
    "iron_rusted": {
        "base_color": (0.29, 0.21, 0.15),
        "roughness": 0.65,
        "roughness_variation": 0.25,
        "metallic": 0.85,
        "metallic_edge_reveal": 0.95,  # wear shows more metallic at edges
        "normal_strength": 1.2,
        "detail_scale": 3.0,
        "wear_intensity": 0.6,
    },
    # ... 20-40 entries covering all VeilBreakers materials
}
```

This library would be consumed by:
- `texture_create_pbr` - to set default values per material type
- `world_generate_building` - already references material names
- Proposed `style_validate` handler - checks assets against palette/roughness constraints

### 2.4 Texture Tiling: Avoiding Repetition on Large Surfaces

Large surfaces (building walls, terrain, dungeon corridors) must use tiling textures but avoid the "wallpaper effect" of visible repetition.

**Techniques (all implementable in our pipeline):**

1. **Multi-Scale Tiling**: Blend 2-3 texture layers at different scales. Base tile at 1x, detail at 4x, macro variation at 0.25x. Already standard in Unity terrain shader.

2. **Stochastic Tiling**: Randomly rotate and mirror UV coordinates per-tile to break up repetition. Unity shader support available.

3. **Trim Sheets**: Instead of unique textures per building face, use shared trim sheets where different parts of the texture map to different architectural elements (molding, brick, windowsill). Our building grammar already has material roles that could map to trim sheet regions.

4. **Decal Overlays**: Layer unique detail decals (cracks, stains, moss patches) over tiling base textures. Our `env_scatter_props` handler could be extended for decal placement.

5. **Vertex Color Blending**: Paint variation into vertex colors. Our terrain handler already uses vertex color for splatmap blending.

Our `make_tileable()` in texture_ops.py already handles creating seamlessly tiling textures via symmetric mirror-blend. This is used for base tiling textures before they enter the engine.

---

## 3. Interior Design Quality

### 3.1 What Makes Interiors Feel Lived-In vs. Empty

The difference between an empty box with furniture and a believable room is **density, layering, and storytelling detail**.

**Three-Layer System:**

**Layer 1 - Structure** (our building grammar already does this):
- Walls, floor, ceiling, doors, windows
- Architectural details: molding, beams, pillars, arches
- These define the room's shape and period

**Layer 2 - Functional Furniture** (our `generate_interior_layout` already does this):
- Tables, chairs, beds, storage, workstations
- Placed according to room purpose
- Collision-checked for player navigation

**Layer 3 - Storytelling Props** (THIS IS WHAT WE'RE MISSING):
- Clutter on tables: plates, cups, candles, papers, quills
- Wall decorations: banners, mounted weapons, paintings, shelves with items
- Floor clutter: scattered straw, dust piles, bloodstains, dropped items
- Signs of activity: open books, half-eaten food, tools left mid-use
- Damage/age: cracks in walls, cobwebs in corners, water stains on ceiling

**Each prop tells a micro-story.** A tavern with clean tables feels like a game asset. A tavern with a knocked-over chair, a bloodstain, and a dropped dagger tells the player "something happened here."

### 3.2 Furniture Placement Rules

Our existing `generate_interior_layout` uses collision avoidance with wall/center/corner placement rules. Additional rules for AAA quality:

**Clustering**: Furniture forms functional groups, not random scatter.
- Dining: table + 2-6 chairs + candle/centerpiece
- Sleeping: bed + nightstand + chest/wardrobe + rug
- Working: desk + chair + shelf/bookcase + light source
- Social: chairs arranged facing each other, hearth as focal point

**Path Clearance** (for player navigation):
- Primary paths: 1.2m minimum (player character width + margin)
- Secondary paths (between furniture): 0.8m minimum
- Doorways: always unblocked, 1.2m clear zone on both sides
- Stairs: 1.5m clear zone at top and bottom

**Density by Room Type:**
| Room Type | Floor Coverage | Props per 10m^2 | Feel |
|---|---|---|---|
| Tavern | 50-65% | 15-25 | Crowded, busy |
| Throne Room | 20-30% | 5-10 | Grand, imposing |
| Bedroom | 40-55% | 10-18 | Comfortable, private |
| Dungeon Cell | 15-25% | 3-6 | Sparse, oppressive |
| Kitchen | 55-70% | 18-30 | Cluttered, functional |
| Library | 45-60% | 12-20 | Dense shelving, clear reading areas |
| Armory | 40-55% | 10-15 | Organized, military |
| Chapel | 30-45% | 8-15 | Orderly rows, open altar area |

### 3.3 Scale Consistency Standards

All measurements in meters (Unity's 1 unit = 1 meter):

| Element | Measurement | Notes |
|---|---|---|
| **Player Character Height** | 1.8m | Reference for all other measurements |
| **Door Width** | 1.0-1.2m | Must allow player + small margin |
| **Door Height** | 2.2-2.5m | Gothic style allows up to 3.0m |
| **Ceiling Height** | 2.8-3.5m (standard) | Gothic/cathedral: 6.0-12.0m |
| **Chair Seat Height** | 0.45m | |
| **Table Height** | 0.75m | |
| **Counter/Bar Height** | 1.1m | |
| **Bed Height** | 0.5-0.6m | Frame + mattress |
| **Shelf Height** | 1.8-2.2m (top) | Must be reachable |
| **Window Sill Height** | 0.8-1.0m | From floor |
| **Stair Step Height** | 0.18-0.22m | 0.20m is ideal |
| **Stair Step Depth** | 0.25-0.30m | |
| **Hallway Width** | 2.0-3.0m | Depends on building type |
| **Wall Thickness** | 0.25-0.80m | Thin for interiors, thick for fortifications |

### 3.4 Interior Lighting Guidelines

Lighting is what transforms a gray box into an atmospheric space.

**Light Sources for Dark Fantasy:**
1. **Torches**: Warm (2700K-3200K), flicker animation, wall-mounted every 4-6m in corridors. Cast sharp shadows. Always paired with a wall sconce prop.
2. **Candles**: Warm (2500K-3000K), subtle flicker, on tables/shelves. Cluster 2-5 candles.
3. **Fireplace/Hearth**: Warm (2000K-2800K), dominant room light, animated. Provides 70% of room illumination in inhabited spaces.
4. **Windows**: Cool daylight (5500K-7000K) or moonlight (7000K-9000K). Volumetric shafts via Unity's VFX. Dust motes in shafts.
5. **Magic/Arcane**: Purple-blue (8000K+) or custom RGB. Pulsing, not flickering. Used sparingly.

**Lighting Rules:**
- Never uniformly lit. Every room has bright zones and dark corners.
- Primary light source illuminates 60% of room, secondary 25%, remaining 15% in shadow.
- Ambient light in interiors: very low (0.05-0.15 intensity). Darkness is a design element.
- Place lights AT the prop that emits them (torch, candle, window), never floating.
- Baked lightmaps for static interiors (our `uv_generate_lightmap` handler creates the lightmap UV).

---

## 4. Weapon & Equipment Generation

### 4.1 Weapon Mesh Requirements

Every weapon needs specific geometry features beyond just looking correct:

**Grip Point** (mandatory):
- Empty/bone placed at the character's hand position
- Named `grip_point` or `socket_grip` for our pipeline
- Located where the character's palm center contacts the weapon
- Oriented: Y-forward along weapon length, Z-up relative to hand

**Attachment Points** (for effects, sheaths):
- `socket_sheath` - where weapon attaches to body when not held
- `socket_effect_tip` - where spell/impact VFX spawn (blade tip, staff head)
- `socket_effect_trail` - for weapon trail VFX (along blade edge)

**Collision Mesh**:
- Simplified 20-50 triangle convex hull
- Named `{weapon_name}_collision`
- Used for physics interactions, not rendering

**Weapon Types for VeilBreakers Dark Fantasy:**
| Type | LOD0 Tris | Grip Style | Special Requirements |
|---|---|---|---|
| Sword (1H) | 3,000-5,000 | Single hand | Blade edge for trail VFX |
| Greatsword (2H) | 5,000-8,000 | Two hand | Longer blade, heavier crossguard |
| Axe (1H) | 2,500-4,000 | Single hand | Asymmetric head |
| Battleaxe (2H) | 4,000-6,000 | Two hand | Large head, counterweight |
| Mace/Hammer (1H) | 2,000-4,000 | Single hand | Dense head geometry |
| Warhammer (2H) | 4,000-6,000 | Two hand | Massive head |
| Dagger | 1,500-2,500 | Single hand | Small, detailed |
| Staff | 3,000-5,000 | Two hand | Top ornament, gem socket |
| Bow | 3,000-5,000 | Two hand + arrow | String as separate mesh (for draw animation) |
| Shield | 2,000-5,000 | Off-hand | Back face visible when sheathed |
| Torch | 1,000-2,000 | Single hand | Flame VFX attachment point |

### 4.2 Equipment Attachment System

How games handle equipping armor/weapons on character models:

**Method 1: Bone Socket Attachment (Weapons, Held Items)**

The standard approach in Unity for held items. The weapon mesh is parented to a specific bone in the character's skeleton at runtime.

```
Character Rig Hierarchy:
  Hips
    Spine -> Spine1 -> Spine2
      Neck -> Head
      LeftShoulder -> LeftArm -> LeftForeArm -> LeftHand
        [socket_weapon_left]   <- Shield/off-hand parented here
      RightShoulder -> RightArm -> RightForeArm -> RightHand
        [socket_weapon_right]  <- Main weapon parented here
    LeftUpLeg -> ...
    RightUpLeg -> ...
  [socket_back]                <- Sheathed 2H weapon
  [socket_hip_left]            <- Sheathed dagger
  [socket_hip_right]           <- Sheathed 1H sword
```

**Implementation**: Create empty GameObjects at socket positions in the rig. At runtime, instantiate weapon prefab and parent it to the socket transform. Our rigging_templates.py already defines complete bone hierarchies -- we need to add socket empties to each template.

**Method 2: Skinned Mesh Renderer Swapping (Armor, Clothing)**

For armor and clothing that deforms with the body:

1. **All armor meshes are skinned to the SAME skeleton** as the base character body
2. Each armor piece is a separate SkinnedMeshRenderer component
3. To "equip" armor: enable the armor piece's renderer, disable the body section it replaces
4. The key requirement: **armor meshes and body mesh must share identical bone names and hierarchy**

**Implementation for our pipeline:**
- Character body is exported with the full armature
- Each armor piece is modeled on the same armature in Blender, with identical vertex group names
- Export each piece as a separate FBX but referencing the same skeleton
- In Unity, combine SkinnedMeshRenderers that share bones

**Method 3: Blend Shapes for Body Fitting (Advanced)**

For tight-fitting armor that needs to prevent clipping with the body:
- Body mesh has blend shapes that slightly shrink areas under armor
- When chest armor is equipped, activate "chest_shrink" blend shape on body
- Our `rig_add_shape_keys` handler already supports creating shape keys

### 4.3 Armor/Equipment Set Structure

For VeilBreakers, a modular equipment system with these slots:

| Slot | Mesh Type | Attachment Method | Notes |
|---|---|---|---|
| Head | Skinned mesh | Bone: Head | Replace head/hair mesh |
| Chest | Skinned mesh | Bones: Spine, Spine1, Spine2, Shoulders | Largest piece, most complex |
| Gloves | Skinned mesh | Bones: Hands, Fingers | |
| Legs | Skinned mesh | Bones: UpperLegs, LowerLegs | |
| Boots | Skinned mesh | Bones: Feet, Toes | |
| Cape/Back | Skinned mesh + cloth sim | Bones: Spine2, Neck + spring bones | Uses our `rig_setup_spring_bones` |
| Main Weapon | Static mesh | Socket: RightHand | Bone attachment |
| Off-Hand | Static mesh | Socket: LeftHand | Shield or secondary weapon |
| Belt Items | Static mesh | Socket: Hips | Pouches, potions |

---

## 5. Best Practices: Blender-to-Unity Pipeline & Tools

### 5.1 Blender-to-Unity Export Settings

**FBX Export (primary format for characters and rigged assets):**
```python
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=True,
    global_scale=1.0,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',      # Unity uses left-hand Y-up
    axis_up='Y',
    use_mesh_modifiers=True,
    mesh_smooth_type='FACE',
    use_tspace=True,         # Tangent space for normal maps
    add_leaf_bones=False,    # Unity doesn't need leaf bones
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    use_armature_deform_only=True,
    bake_anim=True,
    bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=True,
)
```

**GLB/glTF Export (preferred for static props and environment):**
```python
bpy.ops.export_scene.gltf(
    filepath=filepath,
    export_format='GLB',     # Single binary file
    use_selection=True,
    export_apply=True,       # Apply modifiers
    export_texcoords=True,
    export_normals=True,
    export_tangents=True,
    export_materials='EXPORT',
    export_colors=True,      # Vertex colors for terrain blending
)
```

**Critical Unity import settings:**
- Scale Factor: 1 (if exported correctly from Blender)
- Convert Units: ON
- Import BlendShapes: ON (for facial/body shape keys)
- Import Visibility: OFF
- Import Cameras/Lights: OFF
- LOD naming: `_LOD0`, `_LOD1`, etc. (Unity auto-detects, auto-creates LODGroup)

### 5.2 LOD for Interior-Heavy Scenes

Interiors are the most expensive rendering scenario because:
- Player is close to many objects simultaneously
- All objects are at LOD0
- No distance culling available (everything is "near")

**Professional solutions:**

1. **Room-Based Occlusion Culling**: Only render rooms the player can see. Unity's built-in occlusion culling handles this IF rooms are properly separated with portals (doorways).
   - Each room should be a separate "occlusion area"
   - Doorways act as portals
   - Rooms not visible through any portal chain are fully culled

2. **Interior LOD via Distance from Room Center**:
   - Room the player is IN: all props at LOD0
   - Adjacent rooms (visible through doorway): props at LOD1
   - Two rooms away: props at LOD2 or culled entirely

3. **Prop Instance Batching**: Identical props (chairs, candles, barrels) use GPU instancing in Unity. One draw call for all instances of the same mesh+material.

4. **Texture Atlasing for Interior Props**: Group all small props in a room onto a shared texture atlas (1024x1024 or 2048x2048). One material = one draw call for the entire room's small props.

5. **Light Probe Groups**: Instead of real-time lights for each torch, use baked lightmaps + light probes for dynamic objects. Our `uv_generate_lightmap` handler creates the lightmap UV channel.

### 5.3 Unity Packages for Equipment/Inventory Systems

Relevant packages for VeilBreakers' visual equipment system:

1. **Unity's Animation Rigging Package** (`com.unity.animation.rigging`):
   - Runtime IK for weapon holding, shield blocking, two-hand grip
   - Constraint-based bone manipulation without new animations
   - Critical for: weapon socket adjustment, look-at, aim

2. **Unity's Mesh LOD** (built-in since Unity 6):
   - Automatic LOD generation on import
   - Stores LODs in index buffer (no extra GameObjects)
   - Better memory footprint than traditional LODGroup

3. **Addressable Assets** (`com.unity.addressables`):
   - Load equipment meshes/textures on demand
   - Don't load all 200 armor variants at startup
   - Critical for: equipment variety without memory explosion

### 5.4 Automated Quality Gate

The final pipeline step should be an automated validation that prevents "AI slop" from entering the game.

**Proposed `validate_asset_quality` handler checks:**

```
PASS/FAIL Criteria:
  [x] Topology grade >= C (our mesh_analyze_topology)
  [x] Triangle count within budget for asset type
  [x] UV coverage >= 85% (no wasted texture space)
  [x] Texel density within 20% of target (our uv_equalize_density)
  [x] All textures power-of-two
  [x] PBR channels present (albedo + normal + M/R/AO minimum)
  [x] No baked lighting in albedo (luminance variance check)
  [x] Color values within palette constraints
  [x] Roughness has sufficient variation (stddev > 0.05)
  [x] Scale correct for asset type (bounding box check)
  [x] Origin point at expected location
  [x] LOD chain generated with correct naming
  [x] Materials count <= 3 per object
  [x] Naming convention followed ({asset_name}_LOD{N})
  [x] Object has no default Blender names
  [x] Transforms applied (location=0, rotation=0, scale=1)
```

---

## 6. Implementation Priorities for the MCP Toolkit

### 6.1 What We Already Have (Strong Foundation)

Our toolkit already implements the core pipeline:
- **40 command handlers** across mesh, UV, texture, rigging, animation, environment, worldbuilding
- **Tripo3D integration** for AI model generation
- **ESRGAN integration** for texture upscaling
- **Full PBR material creation** with node tree setup
- **Texture baking** (normal, AO, combined, roughness, emit, diffuse)
- **LOD generation** with Unity-compatible naming
- **Interior layout generation** with collision avoidance
- **Building grammar** with 5 architectural styles
- **Wear map generation** from mesh curvature
- **Seam blending** and **tileable texture** creation
- **Pipeline runner** for batch processing
- **Asset catalog** for tracking generated assets

### 6.2 Critical Gaps to Fill (Ranked by Impact)

**HIGH IMPACT (directly prevents "AI slop"):**

1. **Albedo De-lighting**: Remove baked lighting from AI-generated textures. Without this, models look flat or wrongly lit in every scene. Can be implemented as a texture_ops function using frequency separation (high-pass filter preserves detail, low-pass removes lighting gradient).

2. **Style Validation Handler**: Automated check that assets match the VeilBreakers palette and material constraints. Returns pass/fail with specific violations. Gate the pipeline -- nothing enters the game without passing.

3. **Material Library with Presets**: Shared dict of all VeilBreakers materials with locked HSV ranges, roughness ranges, and metallic values. Every handler that creates materials references this library.

4. **Per-Asset-Type Pipeline Presets**: When you say "generate a sword," the pipeline knows: 4000 tris, 1024x1024 textures, weapon grip socket, sheath socket, blade trail socket. When you say "generate a tavern chair," it knows: 1500 tris, 512x512 texture, no sockets. Currently every asset gets the same generic treatment.

**MEDIUM IMPACT (improves quality significantly):**

5. **Storytelling Prop Scatter (Layer 3)**: Extend interior generation to add clutter, wall decorations, floor detail, and narrative props. The `_ROOM_CONFIGS` in `_building_grammar.py` currently only covers Layer 2 (functional furniture).

6. **Equipment Socket System**: Add socket empties to rigging templates for weapon/shield attachment. Extend the rig handlers to support equipment bone sockets.

7. **Roughness Variation Generator**: Take a flat roughness map and add physics-based variation: edge wear (from curvature/wear map), crevice dirt accumulation, surface use patterns. Combines our wear map with procedural noise.

8. **Smart Seam Placement**: UV seams automatically placed at material boundaries, sharp edges, and natural fold lines rather than arbitrary positions.

**LOWER IMPACT (polish):**

9. **Texture Atlas Generator**: Combine multiple small prop textures into a single atlas for reduced draw calls.
10. **Detail Normal Map Blending**: Second UV channel with tiled detail normal for surface micro-detail.
11. **Color Grading LUT**: Apply a unified color look-up table to all textures for consistent mood.

---

## 7. Quick Reference: The VeilBreakers Asset Quality Checklist

For every asset generated through the pipeline, verify:

```
GEOMETRY:
  [ ] Quad-dominant topology (grade C or better)
  [ ] Within poly budget for asset type (see Section 1.3)
  [ ] No non-manifold edges, loose verts, or floating geometry
  [ ] Clean edge flow at deformation zones (characters only)
  [ ] Origin at logical position (bottom-center for props, hip for chars)
  [ ] Scale matches Unity 1 unit = 1 meter

TEXTURES:
  [ ] Power-of-two resolution matching asset type (see Section 1.4)
  [ ] PBR channels: Albedo + Normal + M/R/AO (minimum)
  [ ] No baked lighting in albedo
  [ ] Roughness has visible variation (not flat)
  [ ] Colors within VeilBreakers palette (see Section 2.2)
  [ ] UV coverage >= 85%, consistent texel density
  [ ] Seams hidden at natural edges, blended where visible

GAME INTEGRATION:
  [ ] LOD chain generated (_LOD0 through _LOD3)
  [ ] Materials count <= 3
  [ ] Equipment sockets present (weapons/armor only)
  [ ] Collision mesh present (interactive objects only)
  [ ] FBX/GLB export validates clean

STYLE:
  [ ] Matches dark fantasy aesthetic (desaturated, muted, aged)
  [ ] Wear patterns present on metal/wood surfaces
  [ ] Scale consistent with character reference (1.8m)
  [ ] Materials from VeilBreakers material library
```

---

## Sources

- [Breakdown of the AAA Pipeline for Game-Ready Props (Polycount)](https://polycount.com/discussion/237029/breakdown-of-the-aaa-pipeline-for-game-ready-realistic-hero-props)
- [A Practical Retopology Pipeline for AI-Generated 3D Models (Tripo)](https://www.tripo3d.ai/blog/explore/retopology-pipeline-for-ai-generated-models)
- [How to Check if Your AI 3D Model is Game-Ready (Tripo)](https://www.tripo3d.ai/blog/how-to-check-if-ai-3d-models-are-game-ready)
- [How to Upscale Textures on AI 3D Models (Tripo)](https://www.tripo3d.ai/blog/upscale-textures-on-ai-3d-models)
- [Texel Density Deep Dive (Beyond Extent)](https://www.beyondextent.com/deep-dives/deepdive-texeldensity)
- [Environment Art (The Level Design Book)](https://book.leveldesignbook.com/process/env-art)
- [Creating a Real Time Dark Fantasy Character (The Rookies)](https://discover.therookies.co/2025/01/20/creating-a-real-time-dark-fantasy-character-for-unreal-engine-5)
- [PBR Textures Guide (ArtStation / Luis Mesquita)](https://www.artstation.com/blogs/luismesquita/PwEm/everything-about-pbr-textures-and-a-little-more-part-1)
- [3D Character Customization in Unity (Larissa Redeker / Medium)](https://medium.com/@larissaredeker/3d-character-customization-fd95a1d57ae)
- [The State of AI in AAA Game Production (David A. Smith / Medium)](https://davidasmith.medium.com/the-state-of-ai-in-aaa-game-production-b7d949df4daa)
- [LOD Group Configuration (Unity Manual)](https://docs.unity3d.com/Manual/lod-group-configure.html)
- [Mesh LOD Introduction (Unity Manual)](https://docs.unity3d.com/Manual/lod/mesh-lod-introduction.html)
- [Blender 4.5 Manual / Python API](https://docs.blender.org/manual/en/4.5/)
