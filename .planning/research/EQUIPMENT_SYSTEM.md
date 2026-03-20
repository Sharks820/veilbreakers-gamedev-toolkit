# Equipment System, Weapon Attachment & Inventory Visuals

**Domain:** Visual equipment swapping on character models for dark fantasy RPG
**Researched:** 2026-03-19
**Confidence:** HIGH (verified against Unity docs, industry patterns, existing toolkit codebase)

---

## 1. Equipment Attachment Systems

### 1.1 Bone Socket System (Weapons & Held Items)

The bone socket pattern is the universal AAA approach for attaching rigid objects (weapons, shields, torches) to animated characters. The item becomes a child of a bone's Transform, moving with it automatically.

**How it works:**
1. Every skeleton defines named "socket" bones or empty GameObjects parented to hand/body bones
2. Equipment prefab is instantiated and `transform.SetParent(socketBone, worldPositionStays: false)`
3. The item's local position/rotation are set to predefined offsets (the "grip transform")
4. On unequip, the prefab is destroyed or reparented to an object pool

**Standard socket bones for VeilBreakers humanoid characters:**

| Socket Name | Parent Bone | Purpose |
|-------------|-------------|---------|
| `socket_weapon_R` | `hand.R` | Right-hand weapon grip (swords, axes, maces) |
| `socket_weapon_L` | `hand.L` | Left-hand weapon/shield grip |
| `socket_back_upper` | `spine.003` | Two-hand weapon sheathed on upper back |
| `socket_back_lower` | `spine.001` | Quiver, short weapon sheathed on lower back |
| `socket_hip_L` | `thigh.L` | Sword scabbard on left hip |
| `socket_hip_R` | `thigh.R` | Dagger/potion on right hip |
| `socket_head` | `spine.005` (head) | Helmets, circlets, hoods |
| `socket_shoulder_L` | `upper_arm.L` | Left pauldron |
| `socket_shoulder_R` | `upper_arm.R` | Right pauldron |
| `socket_spine_cape` | `spine.003` | Cape/cloak attachment |

**Mapping to existing rig templates (rigging_templates.py):**
Our HUMANOID_BONES already defines: `spine` through `spine.005`, `upper_arm.L/R`, `forearm.L/R`, `hand.L/R`, `thigh.L/R`, `shin.L/R`, `foot.L/R`. Socket bones should be added as non-deforming children of these at rig setup time.

**Unity-side implementation:**
```
// Pseudocode for bone socket attachment
Transform socket = animator.GetBoneTransform(HumanBodyBones.RightHand)
                   .Find("socket_weapon_R");
GameObject weapon = Instantiate(weaponPrefab, socket);
weapon.transform.localPosition = weaponData.gripOffset;
weapon.transform.localRotation = Quaternion.Euler(weaponData.gripRotation);
```

### 1.2 SkinnedMeshRenderer Swapping (Armor & Clothing)

Armor pieces that deform with the body (chest plates that flex when breathing, gloves that bend with fingers) use SkinnedMeshRenderer bone rebinding, not socket parenting.

**How it works:**
1. All armor pieces are authored on the SAME skeleton as the base character body
2. Each piece (helmet, chest, gauntlets, greaves, boots) is a separate mesh with bone weights painted against the shared skeleton
3. At runtime, the armor SkinnedMeshRenderer's `.bones` array is remapped to point at the character instance's actual bone Transforms
4. The armor mesh deforms identically to the body because it references the same bone hierarchy

**Bone rebinding algorithm (critical for modular characters):**
```
// Pseudocode for SkinnedMeshRenderer bone rebinding
void RebindSkinnedMesh(SkinnedMeshRenderer equipmentSMR, Transform characterRoot) {
    Transform[] newBones = new Transform[equipmentSMR.bones.Length];
    for (int i = 0; i < equipmentSMR.bones.Length; i++) {
        string boneName = equipmentSMR.bones[i].name;
        newBones[i] = FindBoneRecursive(characterRoot, boneName);
    }
    equipmentSMR.bones = newBones;
    equipmentSMR.rootBone = FindBoneRecursive(characterRoot, "Hips");
}
```

**Key requirement:** All armor meshes MUST be authored against the same skeleton with identical bone names. This means our Blender rig templates in `rigging_templates.py` define the canonical bone names that ALL equipment must match.

**Unity components needed:**
- `SkinnedMeshRenderer` on each armor piece
- `Mesh.bindposes` must match the skeleton's rest pose (the inverse transformation matrix of each bone in its bind pose)
- `BoneWeight` per vertex (1-4 bones per vertex, quality setting configurable)

### 1.3 Modular Character System (Body Part Swapping)

For maximum customization (different heads, torso builds, arm types), characters are split into independently swappable modules.

**Module breakdown for VeilBreakers:**

| Slot | Mesh Region | Weighted Bones | Notes |
|------|-------------|----------------|-------|
| Head | skull, face, ears, jaw | `spine.004`, `spine.005`, facial bones | Includes shape keys for expressions |
| Torso | chest, stomach, upper back | `spine` through `spine.003` | Base body shape; armor replaces this |
| Arms_Upper | shoulders to elbows | `upper_arm.L/R` | Pauldrons integrated |
| Arms_Lower | elbows to wrists | `forearm.L/R`, `hand.L/R` | Gauntlets/bracers |
| Legs_Upper | hips to knees | `thigh.L/R` | Tassets/leg armor |
| Legs_Lower | knees to ankles | `shin.L/R` | Greaves |
| Feet | ankles down | `foot.L/R` | Boots/sabatons |

**Implementation pattern:**
1. **Blender side:** Character is modeled as one mesh, then split into modules along seam lines (edge loops at joints). Each module retains vertex groups for ALL bones but only has non-zero weights for its region.
2. **Export:** Each module exports as a separate FBX/GLB with the full skeleton but only its mesh portion.
3. **Unity side:** A `ModularCharacterManager` component holds references to slot renderers. Swapping equipment instantiates the new module's mesh and calls the bone rebinding algorithm above.

**Seam hiding techniques:**
- Overlapping geometry at module boundaries (2-3mm overlap)
- Consistent UV unwrapping at seam edges so textures tile seamlessly
- Normal transfer at boundaries to prevent shading breaks
- "Inner body" mesh (low-poly bodysuit) visible only through gaps

### 1.4 Blend Shapes for Body Fit

Shape keys (blend shapes) adjust equipment meshes to different body proportions.

**Our existing infrastructure (rigging_advanced.py, `handle_add_shape_keys`)** supports:
- Custom vertex offset shape keys via `mode="custom"`
- Expression and damage shape keys
- Validation of vertex offset data

**Equipment fit shape keys needed:**
| Shape Key | Purpose | Driven By |
|-----------|---------|-----------|
| `fit_muscular` | Expand armor for muscular build | Character body type slider |
| `fit_slim` | Shrink armor for slim build | Character body type slider |
| `fit_tall` | Stretch armor for tall build | Character height slider |
| `fit_wide` | Widen armor for heavy build | Character weight slider |
| `corruption_XX` | Deform armor as corruption increases | Corruption percentage (0-100%) |

**Implementation:** Equipment meshes include these shape keys at authoring time. Unity drives the blend shape weight values from character stats. Our `handle_add_shape_keys` handler already supports creating these programmatically.

---

## 2. Weapon Types & Mesh Requirements

### 2.1 Universal Weapon Mesh Standards

Every weapon mesh must include:

| Component | Purpose | Technical Spec |
|-----------|---------|----------------|
| **Grip point** | Origin/pivot for hand attachment | Empty at exact grip center, Y-up along shaft, Z-forward |
| **Collision mesh** | Physics interactions | Simplified convex hull, separate `_col` mesh, 50-200 tris |
| **Trail VFX points** | Weapon swing trail emission | 2+ empties along blade edge: `vfx_trail_base`, `vfx_trail_tip` |
| **Hand IK targets** | Precise hand placement | `ik_hand_R`, `ik_hand_L` transforms at grip positions |
| **Material slots** | Consistent PBR materials | Max 2-3 slots: blade/head, grip/shaft, accent/gem |

### 2.2 Per-Weapon-Type Specifications

#### Swords (One-Hand)
- **Poly budget:** 800-2,000 tris
- **Anatomy:** pommel, grip (handle), guard (cross-guard), blade
- **Pivot:** Center of grip, where palm wraps
- **Trail points:** Guard to blade tip
- **UV layout:** Blade gets 60% UV space (most visible), grip gets 25%, guard/pommel 15%
- **Sheathed position:** `socket_hip_L`, rotated 15deg forward

#### Swords (Two-Hand)
- **Poly budget:** 1,500-3,000 tris
- **Anatomy:** Same as one-hand but longer, with two grip zones
- **Extra:** `ik_hand_L` offset on lower grip for two-hand animation
- **Sheathed position:** `socket_back_upper`, diagonal across back

#### Axes, Maces, Hammers
- **Poly budget:** 800-2,500 tris (heads can be detailed)
- **Anatomy:** head (axe blade / mace flanges / hammer face), shaft, grip wrap
- **Pivot:** Where dominant hand grips, typically 1/3 from bottom of shaft
- **Trail points:** Furthest extent of head to opposite side
- **Weight distribution note:** CoM should be marked for physics (offset from grip)

#### Staffs / Wands
- **Poly budget:** Staff 1,000-2,000; Wand 400-800 tris
- **Anatomy:** shaft, grip section, head/crystal/orb, optional base spike
- **Extra empties:** `vfx_cast_point` at head (particle emission for spells), `vfx_ambient` for idle magical glow
- **Pivot:** Center of grip section (lower third for staffs, center for wands)
- **Sheathed position:** `socket_back_upper`, vertical on back

#### Bows
- **Poly budget:** 1,200-2,500 tris
- **Anatomy:** upper limb, lower limb, grip, string
- **Extra:** `string_top`, `string_bottom` (for bowstring deformation shape key), `arrow_nock` (where arrow sits on string)
- **String:** Separate mesh or spline, driven by shape key for draw animation
- **Pivot:** Center of grip
- **Sheathed position:** `socket_back_upper`, diagonal with string outward

#### Shields
- **Poly budget:** 800-2,000 tris
- **Anatomy:** face (front), rim, arm strap (interior), grip handle (interior)
- **Two attachment points:** `ik_hand_L` at grip, `strap_forearm` at forearm contact
- **Pivot:** Center of grip on interior face
- **Block surface:** Define a `block_normal` direction for gameplay (face-forward vector)
- **Sheathed position:** `socket_back_lower`, flat against back

#### Daggers / Knives
- **Poly budget:** 400-1,000 tris
- **Anatomy:** blade, guard (small or none), grip, pommel
- **Pivot:** Center of small grip
- **Trail points:** Guard to tip (short trail)
- **Sheathed position:** `socket_hip_R` or `socket_back_lower` (cross-draw)

### 2.3 Universal Naming Convention

All weapon empties/sockets follow this pattern:
```
weapon_name/
  mesh_visual          -- Render mesh
  mesh_collision       -- Collision mesh (MeshCollider, convex)
  grip_primary         -- Primary hand grip transform
  grip_secondary       -- Secondary hand (two-hand weapons only)
  ik_hand_R            -- IK target for right hand
  ik_hand_L            -- IK target for left hand (two-hand/shield)
  vfx_trail_base       -- Trail renderer start point
  vfx_trail_tip        -- Trail renderer end point
  vfx_cast_point       -- Spell emission point (staffs/wands)
  vfx_ambient          -- Ambient effect point (glow, drip, etc.)
  block_normal         -- Shield block direction (shields only)
  string_top           -- Bowstring top attachment (bows only)
  string_bottom        -- Bowstring bottom attachment (bows only)
  arrow_nock           -- Arrow rest position (bows only)
```

---

## 3. Inventory Visual System

### 3.1 Real-Time Equipment Display on Character Model

**Architecture:** `EquipmentManager` MonoBehaviour manages all equipment slots and coordinates visual updates.

**Slot system:**
```
enum EquipmentSlot {
    Head,           // Helmet, circlet, hood
    Shoulders,      // Pauldrons (L+R as pair)
    Chest,          // Chest armor (replaces torso module)
    Arms,           // Gauntlets, bracers
    Legs,           // Greaves, leg armor
    Feet,           // Boots, sabatons
    Back,           // Cape, cloak, quiver
    MainHand,       // Primary weapon
    OffHand,        // Shield, secondary weapon, torch
    Ring_L,         // Left ring (no visual, stats only)
    Ring_R,         // Right ring (no visual, stats only)
    Amulet,         // Necklace (no visual or minimal)
}
```

**Equipment change flow:**
1. Player equips item via inventory UI
2. `EquipmentManager.Equip(slot, itemData)` called
3. Previous equipment in slot is unequipped (destroy visual, return to inventory)
4. For **skinned armor** (Head, Chest, Arms, Legs, Feet, Shoulders): Instantiate armor prefab, call `RebindBones()` to share character skeleton, enable SkinnedMeshRenderer
5. For **socket items** (MainHand, OffHand): Instantiate weapon prefab, parent to appropriate socket bone, set grip offset
6. For **cape/cloak** (Back): Instantiate, rebind bones, enable cloth simulation component
7. Fire `OnEquipmentChanged` event for UI update, stat recalculation, animation layer changes

### 3.2 Sheathed Weapon Positions

When a weapon is equipped but not "drawn" (active in combat), it displays in a sheathed/holstered position on the body.

**Sheathing uses Unity's Multi-Parent Constraint** (from Animation Rigging package):
- Weapon has two parent sources: combat socket (hand) and sheathed socket (back/hip)
- Draw/sheathe animation blends the constraint weights between sources
- "Maintain Offset" preserves proper alignment at each parent
- No reparenting needed -- weight blending handles the transition smoothly

**Sheathe position map:**

| Weapon Type | Sheathed Socket | Offset Notes |
|-------------|----------------|--------------|
| One-hand sword | `socket_hip_L` | Angled 15deg forward, handle up |
| Two-hand sword | `socket_back_upper` | Diagonal, handle over right shoulder |
| Axe/mace (1H) | `socket_hip_R` | Head down, handle up |
| Axe/hammer (2H) | `socket_back_upper` | Head up, handle down |
| Staff | `socket_back_upper` | Vertical, head up |
| Wand | `socket_hip_R` | Vertical, in loop holder |
| Bow | `socket_back_upper` | Diagonal, string outward |
| Shield | `socket_back_lower` | Flat against lower back |
| Dagger | `socket_hip_R` | Horizontal, blade back |

### 3.3 Armor Layering System

Equipment renders in layers from innermost to outermost:

```
Layer 0: Base body mesh (always present, hidden under armor)
Layer 1: Underclothes / gambeson (visible at gaps)
Layer 2: Primary armor (chest plate, greaves, gauntlets)
Layer 3: Over-armor (tabard, pauldrons, belt accessories)
Layer 4: Outer layer (cape, cloak, hood)
```

**Implementation:**
- Each layer is a separate SkinnedMeshRenderer or set of them
- Body mesh regions hidden by armor use a "body mask" texture (alpha cutout on base mesh where armor covers)
- Alternatively, body mesh vertices under armor are scaled to zero via shape key (prevents z-fighting)
- Capes/cloaks use Unity Cloth component with collision against body/armor colliders

### 3.4 Equipment Preview in Inventory UI

**Two approaches (both needed):**

1. **3D Preview Camera:** A separate camera renders the equipped character to a RenderTexture displayed in the UI panel. Character slowly rotates. Equipment changes are reflected in real-time. Uses a dedicated "preview" layer to avoid lighting interference.

2. **Flat Icons:** Each equipment item has a 2D icon (256x256 or 512x512) for inventory grid display. Generated in Blender using a standardized camera setup and lighting rig, exported as sprite atlas.

**Icon generation pipeline (Blender-side, new handler opportunity):**
1. Place weapon/armor mesh in standard scene with fixed camera + 3-point lighting
2. Render front-facing view at target resolution
3. Apply rarity-tier border (color-coded frame)
4. Export as PNG with transparent background
5. Batch process into sprite atlas for Unity import

### 3.5 Open-Source Inventory Patterns

**Grid-based inventory** (Diablo-style): Items occupy NxM cells in a grid. The FarrokhGames/Inventory system demonstrates this with:
- `InventoryManager(width, height)` -- grid dimensions
- `IInventoryItem` interface with `InventoryShape` defining item footprint
- `ItemDefinition` as ScriptableObject for reusable templates
- `InventoryRenderer` MonoBehaviour for UI display
- Equipment slots as separate named containers

**Slot-based inventory** (WoW/Dark Souls-style): Fixed equipment slots + general bag storage. Simpler to implement, better for action RPGs.

**Recommended for VeilBreakers:** Slot-based equipment (12 slots above) + grid-based general inventory. Equipment slots are the visual display system; bag inventory is storage.

---

## 4. Art Style Consistency for Equipment

### 4.1 Maintaining Consistent Style Across 100+ Items

**Material Template System:**
All equipment uses a shared URP Lit shader configuration with constrained property ranges:

| Property | Range | Rationale |
|----------|-------|-----------|
| Metallic | 0.0-0.15 (cloth/leather), 0.7-0.95 (metal) | Prevents "plastic metal" look |
| Smoothness | 0.2-0.5 (worn/aged), 0.6-0.85 (polished) | Dark fantasy = weathered, not pristine |
| Normal intensity | 0.8-1.2 | Consistent surface detail depth |
| AO strength | 0.7-1.0 | Deep crevice shadows |
| Emission intensity | 0.0 (mundane), 0.5-2.0 (magical) | Only enchanted items glow |

**Master material approach:** Create 4-5 master materials (metal, leather, cloth, wood, bone/chitin) as Material instances of URP/Lit. All equipment pieces use instances of these masters, only varying textures and tint colors. This guarantees PBR consistency.

### 4.2 Color Palette: Rarity Tiers

| Rarity | Base Tint | Emission | Border Color (UI) | VFX |
|--------|-----------|----------|-------------------|-----|
| Common | Desaturated, natural tones | None | `#8B8B8B` (gray) | None |
| Uncommon | Slightly saturated | None | `#1EFF00` (green) | None |
| Rare | Deeper color saturation | Faint glow | `#0070DD` (blue) | Subtle particle shimmer |
| Epic | Rich, vibrant colors | Moderate glow | `#A335EE` (purple) | Ambient particle trail |
| Legendary | Gold/warm accent colors | Strong glow | `#FF8000` (orange) | Constant particle aura |

**Faction color accents** (VeilBreakers brands):
| Brand | Primary Accent | Secondary |
|-------|---------------|-----------|
| IRON | Gunmetal gray `#6B7280` | Rust orange `#B45309` |
| SAVAGE | Blood red `#991B1B` | Bone white `#F5F0E6` |
| SURGE | Electric blue `#2563EB` | White spark `#DBEAFE` |
| VENOM | Acid green `#65A30D` | Dark purple `#581C87` |
| DREAD | Shadow black `#1F2937` | Pale violet `#8B5CF6` |
| LEECH | Dark crimson `#7F1D1D` | Sickly yellow `#CA8A04` |
| GRACE | Gold `#D97706` | White `#FFFBEB` |
| MEND | Verdant green `#059669` | Soft blue `#BAE6FD` |
| RUIN | Ash gray `#6B7280` | Ember orange `#EA580C` |
| VOID | Deep purple `#4C1D95` | Void black `#0F0326` |

### 4.3 Wear, Damage & Corruption on Equipment

**Wear maps** (our existing `handle_generate_wear_map` in `texture.py`):**
- Edge wear (scratches along convex edges) -- already supported
- Surface dirt accumulation in crevices -- AO-driven
- Battle damage (dents, cuts) -- normal map overlay

**Corruption integration:**
Equipment visuals change as VeilBreakers corruption percentage increases (0-100%):

| Corruption % | Visual Effect |
|--------------|---------------|
| 0-20% | Clean equipment, normal appearance |
| 20-40% | Subtle vein-like discoloration on metal surfaces |
| 40-60% | Visible corruption tendrils, darkened edges, slight glow in cracks |
| 60-80% | Major surface transformation, organic growths, pulsing emission |
| 80-100% | Equipment appears partially consumed, heavy distortion, strong emission |

**Implementation:** Corruption drives a blend between clean and corrupted texture sets, plus shape key deformation. The corruption shader (already planned in PROJECT.md) scales these effects via a single `_CorruptionPercent` float property.

### 4.4 Texture Specifications

| Texture Type | Resolution | Format | Notes |
|--------------|-----------|--------|-------|
| Albedo (Base Map) | 1024x1024 (weapons), 2048x2048 (armor sets) | BC7 (RGBA) | sRGB color space |
| Normal Map | Same as albedo | BC5 (RG) | Linear, OpenGL format |
| Metallic/AO/Smoothness | Same as albedo | BC7 (RGBA) | R=metallic, G=AO, A=smoothness |
| Emission | 512x512 | BC7 (RGBA) | Only for magical items, smaller since it's simple gradients |
| Detail Normal | 256x256 | BC5 (RG) | Tiling micro-detail (chainmail pattern, leather grain) |

**Channel packing** (single texture for M/AO/S) is critical -- reduces texture samples per pixel from 3 to 1 for these properties.

---

## 5. Technical Implementation in Our Stack

### 5.1 Existing Infrastructure Audit

**What we already have that supports equipment:**

| Component | File | Relevance |
|-----------|------|-----------|
| Humanoid skeleton with named bones | `rigging_templates.py` (HUMANOID_BONES) | Defines all socket parent bones |
| Shape key creation | `rigging_advanced.py` (`handle_add_shape_keys`) | Equipment fit adjustment, corruption deformation |
| Spring bones for capes/hair | `rigging_advanced.py` (`handle_setup_spring_bones`) | Cape/cloak secondary motion |
| IK constraint setup | `rigging_advanced.py` (`handle_setup_ik`) | Hand IK for weapon gripping |
| PBR material creation | `texture.py` (`handle_create_pbr_material`) | Equipment material setup |
| Texture baking | `texture.py` (`handle_bake_textures`) | Equipment texture generation |
| Wear map generation | `texture.py` (`handle_generate_wear_map`) | Equipment wear/damage textures |
| Mesh analysis & repair | `mesh.py` (multiple handlers) | Equipment mesh validation |
| UV unwrapping | `uv.py` (multiple handlers) | Equipment UV setup |
| LOD generation | `pipeline_lod.py` (`handle_generate_lods`) | Equipment LOD chains |
| FBX/glTF export | `export.py` | Equipment asset export |
| Combat abilities | `gameplay_templates.py` | Weapon damage, hitbox, VFX |
| Ragdoll setup | `rigging_advanced.py` (`handle_setup_ragdoll`) | Dropped weapon physics |
| Retarget rig | `rigging_advanced.py` (`handle_retarget_rig`) | Ensure equipment works across character variants |

**What we are missing (gap analysis):**

| Gap | Priority | Complexity | Description |
|-----|----------|------------|-------------|
| Socket bone creation handler | HIGH | LOW | Add non-deforming socket bones to rig at setup time |
| Modular mesh splitting handler | HIGH | MEDIUM | Split character mesh into head/torso/arms/legs/feet modules |
| Weapon mesh generation handler | HIGH | HIGH | Parametric weapon creation from type + description |
| Equipment attachment point setup | HIGH | LOW | Configure empties (grip, trail, cast, IK targets) on weapon meshes |
| Armor fit shape key batch | MEDIUM | LOW | Create standard fit shape keys on armor meshes |
| Equipment icon renderer | MEDIUM | LOW | Render equipment item icons with standard lighting |
| Mesh bone rebinding validator | MEDIUM | LOW | Verify equipment mesh bones match character skeleton |
| Equipment material template | MEDIUM | LOW | Create master materials with constrained PBR ranges |
| Corruption texture overlay | MEDIUM | MEDIUM | Generate corruption-state texture variants |
| Mesh combining utility | LOW | MEDIUM | Combine multiple skinned meshes for draw call reduction |

### 5.2 New Handlers Needed

#### Handler: `equip_setup_sockets` (EQUIP-01)
**Purpose:** Add equipment socket bones to an existing rig
**Input:** `rig_name`, `socket_preset` ("humanoid_melee", "humanoid_ranged", "humanoid_full")
**Blender operations:**
1. Enter edit mode on armature
2. Create socket bones as children of appropriate deform bones
3. Mark socket bones as non-deforming (no vertex weights)
4. Set socket bone display type to "WIRE" for visibility
**Output:** `{ sockets_added: [...], rig_name }`

#### Handler: `equip_split_modular` (EQUIP-02)
**Purpose:** Split a character mesh into modular equipment-swappable parts
**Input:** `object_name`, `split_scheme` ("humanoid_5slot", "humanoid_7slot", "custom"), `custom_vertex_groups` (optional)
**Blender operations:**
1. Validate mesh has proper vertex groups matching rig bones
2. Separate mesh by vertex group regions (select by weight threshold)
3. Ensure each module retains all bone vertex groups (zero-weight groups kept for bind pose)
4. Add 2-3mm overlap at seam boundaries
5. Transfer normals at boundaries for seamless shading
**Output:** `{ modules: [{name, vertex_count, bone_count}...], seam_quality }`

#### Handler: `equip_create_weapon` (EQUIP-03)
**Purpose:** Generate a parametric weapon mesh from type and parameters
**Input:** `weapon_type` ("sword_1h", "sword_2h", "axe_1h", "mace", "staff", "wand", "bow", "shield", "dagger"), `style` ("straight", "curved", "ornate", "brutal", "elegant"), `length`, `description`
**Blender operations:**
1. Generate base mesh from parametric template (bezier curves for blades, cylinders for shafts)
2. Apply style modifiers (bevel, subdivision, displacement for detail)
3. Create material slots (blade, grip, accent)
4. Add socket empties (grip, trail, IK, VFX points) per weapon type spec
5. UV unwrap with weapon-appropriate island layout
6. Generate collision mesh (convex hull simplification)
**Output:** `{ weapon_name, poly_count, material_slots, sockets: [...], bounds }`

#### Handler: `equip_setup_attachment` (EQUIP-04)
**Purpose:** Configure attachment empties on an equipment mesh
**Input:** `object_name`, `equipment_type` ("weapon" or "armor"), `weapon_type` (if weapon), `custom_points` (optional)
**Blender operations:**
1. Analyze mesh bounds and geometry
2. Place standard empties per equipment type specification
3. Orient empties based on mesh principal axes
4. Validate all required points present
**Output:** `{ attachment_points: [{name, position, rotation}...] }`

#### Handler: `equip_fit_shape_keys` (EQUIP-05)
**Purpose:** Add standard body-fit shape keys to armor/clothing mesh
**Input:** `object_name`, `fit_presets` ("muscular", "slim", "tall", "wide"), `corruption_levels` (optional int list)
**Blender operations:**
1. For each fit preset, compute vertex displacement based on vertex normal direction and bone region
2. Create named shape keys: `fit_muscular`, `fit_slim`, etc.
3. If corruption_levels specified, create `corruption_XX` shape keys with procedural organic deformation
**Output:** `{ shape_keys_added: [...], vertex_ranges }`

#### Handler: `equip_render_icon` (EQUIP-06)
**Purpose:** Render equipment item icon for inventory UI
**Input:** `object_name`, `resolution` (256 or 512), `background` ("transparent" or hex color), `rarity_border` (optional: "common", "uncommon", "rare", "epic", "legendary")
**Blender operations:**
1. Set up standard 3-point lighting rig
2. Position camera for front-facing item view (auto-frame to bounds)
3. Render with transparent background
4. Composite rarity border if specified
5. Export as PNG
**Output:** `{ icon_path, resolution, file_size }`

#### Handler: `equip_validate_bones` (EQUIP-07)
**Purpose:** Validate that equipment mesh bones match a target character skeleton
**Input:** `equipment_object`, `rig_name`
**Blender operations:**
1. Extract bone names from equipment mesh vertex groups
2. Compare against rig bone names
3. Check bind pose compatibility
4. Report mismatches, missing bones, extra bones
**Output:** `{ compatible: bool, missing_bones: [...], extra_bones: [...], weight_quality }`

### 5.3 Unity-Side Code Generation Needed

Following the existing `gameplay_templates.py` pattern (generate C# scripts written to disk):

| Template | File Pattern | Purpose |
|----------|-------------|---------|
| `generate_equipment_manager_script` | `VeilBreakers_EquipmentManager.cs` | Slot management, equip/unequip, visual update |
| `generate_modular_character_script` | `VeilBreakers_ModularCharacter.cs` | Body module swapping, bone rebinding |
| `generate_weapon_controller_script` | `VeilBreakers_WeaponController.cs` | Weapon state (sheathed/drawn), IK, trail VFX |
| `generate_equipment_data_script` | `VeilBreakers_EquipmentData.cs` | ScriptableObject for equipment stats + visual refs |
| `generate_inventory_ui_script` | `VeilBreakers_InventoryUI.cs` | UXML/USS-driven inventory display with 3D preview |

### 5.4 Integration with Existing VeilBreakers Systems

**Combat abilities (gameplay_templates.py):** `CombatAbility` ScriptableObjects already define `hitboxSize`, `damage`, `animTrigger`, `vfxPrefab`. Weapons should reference these -- each weapon type has a set of compatible abilities.

**Animation system (animation.py, animation_export.py):** Weapon type determines animation layer:
- One-hand + shield: "CombatOneHandShield" animation layer
- Two-hand: "CombatTwoHand" animation layer
- Dual wield: "CombatDualWield" animation layer
- Staff/ranged: "CombatRanged" animation layer

**VFX pipeline (planned):** Weapon trail VFX uses the `vfx_trail_base` and `vfx_trail_tip` attachment points. Corruption VFX uses `vfx_ambient` point. Cast VFX uses `vfx_cast_point`.

**Spring bones (rigging_advanced.py):** Cape/cloak attached at `socket_spine_cape` gets spring bone physics for secondary motion. Already supported by `handle_setup_spring_bones`.

---

## 6. Implementation Roadmap

### Phase A: Foundation (fits in Phase 13: Content & Progression Systems)
1. `equip_setup_sockets` -- Add socket bones to humanoid rig template
2. `equip_validate_bones` -- Validate equipment/rig bone compatibility
3. `equip_setup_attachment` -- Configure weapon attachment empties
4. `generate_equipment_data_script` -- ScriptableObject for equipment definition
5. `generate_equipment_manager_script` -- Runtime equipment slot management

### Phase B: Visual Equipment (fits in Phase 13 or dedicated sub-phase)
6. `equip_split_modular` -- Split character mesh into swappable modules
7. `equip_fit_shape_keys` -- Body fit shape keys for armor
8. `generate_modular_character_script` -- Bone rebinding and module swapping
9. `generate_weapon_controller_script` -- Weapon state management and IK

### Phase C: Content Pipeline (accelerates bulk equipment creation)
10. `equip_create_weapon` -- Parametric weapon mesh generation
11. `equip_render_icon` -- Automated equipment icon rendering
12. `generate_inventory_ui_script` -- Inventory display with equipment preview

### Phase D: Polish (corruption integration, art consistency)
13. Equipment material template handler (master materials with PBR constraints)
14. Corruption texture overlay generation
15. Mesh combining utility for draw call optimization

---

## 7. Key Technical Decisions

| Decision | Options | Recommendation | Rationale |
|----------|---------|----------------|-----------|
| Armor attachment method | Socket parenting vs Skinned mesh rebinding | **Skinned mesh rebinding** for body armor, **socket parenting** for weapons/rigid items | Body armor must deform with character; weapons are rigid |
| Modular split granularity | 5-slot vs 7-slot vs freeform | **7-slot** (head, torso, upper arms, lower arms, upper legs, lower legs, feet) | Maximum mix-and-match without excessive seam management |
| Weapon sheathing | Reparenting vs Multi-Parent Constraint | **Multi-Parent Constraint** (Animation Rigging package) | Smooth animation-driven transitions without code reparenting |
| Equipment icons | Runtime render vs Pre-baked sprites | **Pre-baked sprites** via Blender handler | Deterministic quality, no runtime render cost, works offline |
| Body hiding under armor | Alpha cutout vs Shape key to zero | **Shape key** (`body_hidden_{region}`) | No shader complexity, works with any material, no z-fighting |
| Corruption visual | Shader parameter vs Texture swap | **Both** -- shader parameter for realtime blending + texture set swap at major thresholds | Smooth low-cost transitions with high-quality threshold jumps |

---

## Sources

### Primary (HIGH confidence)
- Unity SkinnedMeshRenderer docs: bone arrays, blend shapes, quality settings, bind pose system
- Unity HumanBodyBones enum: 55 standard humanoid bone attachment points (Hips through finger distal)
- Unity Animation Rigging package: Two Bone IK Constraint (weapon grip), Multi-Parent Constraint (sheathing)
- Unity Mesh.bindposes: inverse transformation matrices enabling bone rebinding across meshes
- Unity URP Lit shader: metallic/smoothness/normal/emission/occlusion property ranges and channel packing
- Unity Mesh.CombineMeshes: skinned mesh combining for draw call optimization
- Existing VeilBreakers codebase: rigging_templates.py, rigging_advanced.py, gameplay_templates.py, texture.py

### Secondary (MEDIUM confidence)
- AAA modular character patterns (Synty Studios, Unity Open Project approaches)
- FarrokhGames/Inventory: grid-based inventory with ScriptableObject items
- Industry-standard weapon polygon budgets from game art forums and ArtStation references
- PBR material consistency guidelines from Substance/Quixel documentation standards

---
*Research for: VeilBreakers GameDev Toolkit -- Equipment System*
*Researched: 2026-03-19*
