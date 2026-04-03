# Model Size, Texture, and Performance Budgets for VeilBreakers

**Researched:** 2026-04-02
**Domain:** Asset polygon budgets, texture VRAM allocation, scene performance budgets, LOD specifications, Tripo AI decimation targets
**Confidence:** HIGH (cross-referenced Polycount wiki data, GDC-sourced AAA references, Unity URP docs, Tripo API docs, shipped game analysis)

---

## Summary

This document provides **strict, implementable budgets** for every asset type in VeilBreakers. All numbers are designed for Unity 6 URP Forward+ at 60fps, targeting hardware from 2GB VRAM integrated laptops to 16GB gaming GPUs. Four quality tiers (Low/Medium/High/Ultra) scale textures, LOD distances, and scene density -- but LOD0 triangle counts are FIXED per asset type (geometry is authored once, quality tiers control which LOD is shown at what distance).

**Primary recommendation:** Implement a `ASSET_BUDGETS` config dict in the toolkit that maps asset_type to triangle/texture/LOD budgets. All pipeline steps (Tripo generation, decimation, LOD chain, texture allocation, game_check validation) read from this single source of truth.

Reference games for budget calibration: Elden Ring, Dark Souls 3, Diablo IV, Baldur's Gate 3 -- all third-person dark fantasy action RPGs targeting 60fps on PC.

---

## 1. Per-Asset Triangle Budgets (LOD0)

All counts are **triangles** (not polygons/quads). These are LOD0 (maximum detail) targets. Quality tiers control LOD transition distances, not geometry counts.

### 1.1 Characters

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Player character** (3rd person, with equipment) | 25,000 | 35,000 | 50,000 | 70,000 | Body ~60%, equipment ~40%. Ultra for cutscene close-ups. |
| **Enemy - standard mob** | 6,000 | 10,000 | 15,000 | 20,000 | Spawned in groups of 5-15. Budget-critical. |
| **Enemy - elite/mini-boss** | 12,000 | 18,000 | 25,000 | 35,000 | 1-3 on screen simultaneously. |
| **Enemy - boss** | 25,000 | 40,000 | 60,000 | 80,000 | Usually 1 on screen. Gets hero-level budget. |
| **NPC (townfolk)** | 8,000 | 15,000 | 22,000 | 30,000 | Conversation distance matters. 5-10 visible in towns. |

**Reference data points (shipped games):**
- Nier: Automata 2B: 72,000 tris
- Batman: Arkham Asylum Batman: 21,304 tris; Bane: 25,000 tris
- Assassin's Creed 3 Connor: 28,501 tris
- Gears of War 3 Marcus: 31,831 tris
- Resident Evil 6 Chris: 22,240 tris
- Deus Ex: HR Jensen: 25,953 tris
- Street Fighter IV characters: 16,000 tris (60fps fighting game)
- Dark Souls-style recommended: 40,000-60,000 player with equipment (AAA Best Practices research)

### 1.2 Buildings & Architecture

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Building exterior - small** (house, 6x6m) | 3,000 | 5,000 | 8,000 | 12,000 | Shell only. Interior separate mesh. |
| **Building exterior - large** (castle, monastery) | 8,000 | 15,000 | 25,000 | 40,000 | Modular: assembled from kit pieces. Budget is per assembled structure. |
| **Castle wall section** (10m) | 1,500 | 2,500 | 4,000 | 6,000 | Instanced. Trim-sheet textured. |
| **Gate/portcullis** | 2,000 | 4,000 | 6,000 | 8,000 | Includes frame + gate mesh. May animate. |
| **Tower** (full structure) | 3,000 | 6,000 | 10,000 | 15,000 | Cylindrical = fewer tris than rectangular. |

**Reference:** Assassin's Creed Origins: ~4,000 tris for a 6x6m stone block module (per AAA Best Practices research).

### 1.3 Environment / Nature

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Tree** (trunk + branches, no leaves) | 2,000 | 4,000 | 6,000 | 8,000 | Leaves are separate cards/billboards. |
| **Rock/boulder - small** (<1m) | 200 | 400 | 600 | 1,000 | Heavily instanced. Normal map does the work. |
| **Rock/boulder - large** (>2m) | 800 | 1,500 | 3,000 | 5,000 | Fewer instances, needs silhouette detail. |
| **Dead tree/stump** | 500 | 1,000 | 2,000 | 3,000 | Simpler than living tree. |
| **Log** | 200 | 400 | 800 | 1,200 | Essentially a cylinder with detail. |
| **Grass blade** (instanced) | 4 | 6 | 8 | 12 | Single blade. Thousands instanced. GPU instancing required. |

### 1.4 Props

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Barrel/crate** (small prop) | 300 | 600 | 1,000 | 1,500 | Normal map handles plank/stave detail. |
| **Cart/bench** (medium prop) | 800 | 1,500 | 3,000 | 4,500 | Multiple sub-parts (wheels, planks). |
| **Market stall** (large prop) | 1,500 | 3,000 | 5,000 | 7,000 | Canvas + frame + displayed items. |
| **Well** | 800 | 1,500 | 2,500 | 4,000 | Stone ring + roof + bucket mechanism. |
| **Torch sconce** | 100 | 200 | 400 | 600 | Wall-mounted. Tiny screen coverage. |
| **Lantern post** | 300 | 600 | 1,000 | 1,500 | Wrought iron detail via normal map. |
| **Door** | 300 | 600 | 1,200 | 2,000 | Flat panel + hardware. Animated. |

### 1.5 Equipment

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Weapon** (sword, axe, mace) | 1,500 | 3,000 | 5,000 | 8,000 | Visible close to camera. Inspection view = Ultra. |
| **Shield** | 1,000 | 2,000 | 3,500 | 5,000 | Both sides visible. |
| **Armor piece** (single slot) | 2,000 | 4,000 | 6,000 | 8,000 | Per slot (chest, legs, etc). Player has 4-6 slots. |

### 1.6 Interior Furniture

| Asset Type | Low | Medium | High | Ultra | Notes |
|---|---|---|---|---|---|
| **Table** | 400 | 800 | 1,500 | 2,500 | |
| **Chair** | 300 | 600 | 1,200 | 2,000 | Gothic carved = higher end. |
| **Bed** | 500 | 1,000 | 2,000 | 3,000 | Frame + mattress + pillows. |
| **Wardrobe/shelf** | 400 | 800 | 1,500 | 2,500 | Flat surfaces, detail from normal map. |

---

## 2. Texture Resolution Budgets

### 2.1 Per-Asset Texture Size by Quality Tier

| Asset Type | Low (2GB VRAM) | Medium (4GB) | High (8GB) | Ultra (16GB) | PBR Channels |
|---|---|---|---|---|---|
| **Player character** | 1024 body | 2048 body | 2048 body + 1024 face | 2048 body + 2048 face | Full: Albedo, Normal, ORM |
| **Enemy - standard mob** | 512 | 1024 | 1024 | 2048 | Full: Albedo, Normal, ORM |
| **Enemy - elite/boss** | 1024 | 1024 | 2048 | 2048 | Full: Albedo, Normal, ORM |
| **NPC** | 512 | 1024 | 2048 | 2048 | Full: Albedo, Normal, ORM |
| **Building exterior** | 1024 trim | 2048 trim | 2048 trim | 4096 trim | Full: Albedo, Normal, ORM |
| **Castle wall section** | 512 tiling | 1024 tiling | 1024 tiling | 2048 tiling | Full: Albedo, Normal, ORM |
| **Tree trunk** | 512 | 1024 | 1024 | 2048 | Albedo, Normal, ORM |
| **Rock small** | 256 | 512 | 512 | 1024 | Albedo, Normal (no metallic) |
| **Rock large** | 512 | 1024 | 1024 | 2048 | Albedo, Normal, ORM |
| **Barrel/crate** | 256 | 512 | 512 | 1024 | Albedo, Normal |
| **Cart/bench** | 512 | 512 | 1024 | 1024 | Albedo, Normal, ORM |
| **Market stall** | 512 | 1024 | 1024 | 2048 | Albedo, Normal, ORM |
| **Weapon** | 512 | 1024 | 1024 | 2048 | Full: Albedo, Normal, ORM |
| **Shield** | 512 | 1024 | 1024 | 2048 | Full: Albedo, Normal, ORM |
| **Armor piece** | 512 | 1024 | 1024 | 2048 | Full: Albedo, Normal, ORM |
| **Furniture** | 256 | 512 | 1024 | 1024 | Albedo, Normal |
| **Torch/sconce** | 128 | 256 | 256 | 512 | Albedo, Normal |
| **Door** | 256 | 512 | 1024 | 1024 | Albedo, Normal, ORM |
| **Terrain** (per tiling layer) | 512 | 1024 | 1024 | 2048 | Albedo, Normal, ORM |
| **Grass blade** | Shared 256 atlas | Shared 512 atlas | Shared 512 atlas | Shared 1024 atlas | Albedo only |

### 2.2 PBR Channel Requirements

**Full PBR (Albedo + Normal + ORM packed):**
- All characters (player, enemies, NPCs)
- Buildings, architecture pieces
- Weapons, shields, armor
- Large rocks, terrain layers
- Medium/large props with metal or mixed materials

**Simplified PBR (Albedo + Normal only):**
- Small props (barrels, crates, furniture)
- Vegetation (grass, small plants)
- Interior furniture (wood-dominant)
- Torch sconces, lanterns, doors

**Albedo only:**
- Grass blade instances
- Distant billboard LODs
- Particle/VFX textures

### 2.3 Texture Memory per Asset (Approximate, BC7 Compressed)

| Resolution | Albedo (BC7) | Normal (BC5) | ORM (BC7) | Total per asset |
|---|---|---|---|---|
| 256x256 | 43 KB | 32 KB | 43 KB | ~118 KB |
| 512x512 | 171 KB | 128 KB | 171 KB | ~470 KB |
| 1024x1024 | 683 KB | 512 KB | 683 KB | ~1.9 MB |
| 2048x2048 | 2.7 MB | 2.0 MB | 2.7 MB | ~7.4 MB |
| 4096x4096 | 10.7 MB | 8.0 MB | 10.7 MB | ~29.4 MB |

### 2.4 Total VRAM Texture Budget per Quality Tier

| Tier | Target VRAM | Texture Budget | Remaining for RTs/Buffers | Max Unique Textures |
|---|---|---|---|---|
| **Low** (2GB) | 2 GB | ~600 MB | ~1.4 GB | ~300 at 512, ~75 at 1024 |
| **Medium** (4GB) | 4 GB | ~1.5 GB | ~2.5 GB | ~800 at 1024, ~200 at 2048 |
| **High** (8GB) | 8 GB | ~3.0 GB | ~5.0 GB | ~1,600 at 1024, ~400 at 2048 |
| **Ultra** (16GB) | 16 GB | ~6.0 GB | ~10.0 GB | ~800 at 2048, ~200 at 4096 |

**Note:** "Remaining" covers render targets, depth buffers, shadow maps, compute buffers, GPU-instanced mesh data, and Unity overhead. At 1080p, render targets alone consume ~200-400 MB. At 4K, ~800 MB-1.5 GB.

---

## 3. Scene Triangle Budgets

### 3.1 Total Visible Triangles at 60fps

| Tier | Total Visible Tris | Draw Calls | GPU Class |
|---|---|---|---|
| **Low** | 500,000 - 1,000,000 | 200-400 | Intel UHD / GTX 1050 (2GB) |
| **Medium** | 1,000,000 - 2,000,000 | 400-800 | GTX 1660 / RX 580 (4-6GB) |
| **High** | 2,000,000 - 4,000,000 | 800-1,500 | RTX 3060 / RX 6700 (8GB) |
| **Ultra** | 4,000,000 - 8,000,000 | 1,500-3,000 | RTX 4070+ / RX 7800 (12-16GB) |

**Reference:** Dark Souls-style game target is 2-6M total scene triangles at 60fps (from AAA Best Practices research). Modern GPUs handle 5-10M tris easily; the bottleneck is usually draw calls, pixel shader cost, and memory bandwidth -- not raw triangle throughput.

### 3.2 Maximum Simultaneous Asset Counts (per tier)

Based on LOD0 budgets. Actual counts are HIGHER because distant assets use LOD1-3.

| Asset Type | Low | Medium | High | Ultra |
|---|---|---|---|---|
| Player character | 1 | 1 | 1 | 1 |
| Standard mobs (visible) | 8 | 12 | 15 | 20 |
| Elite enemies (visible) | 1 | 2 | 3 | 4 |
| Boss | 1 | 1 | 1 | 1 |
| NPCs in town | 5 | 10 | 15 | 20 |
| Buildings (visible) | 5 | 8 | 12 | 18 |
| Trees (visible) | 15 | 30 | 50 | 80 |
| Large rocks | 10 | 20 | 35 | 50 |
| Small rocks | 30 | 60 | 100 | 150 |
| Small props (barrels etc) | 20 | 40 | 60 | 100 |
| Medium props | 10 | 20 | 30 | 50 |
| Grass instances | 5,000 | 15,000 | 30,000 | 60,000 |
| Furniture (interior) | 8 | 15 | 20 | 30 |

### 3.3 Draw Call Budget Breakdown

| Category | Low | Medium | High | Ultra |
|---|---|---|---|---|
| Terrain | 20-40 | 40-80 | 60-120 | 80-150 |
| Characters (all) | 20-40 | 30-60 | 50-100 | 60-120 |
| Buildings | 15-30 | 25-50 | 40-80 | 50-120 |
| Props (all) | 30-60 | 50-100 | 80-200 | 120-300 |
| Vegetation | 20-40 | 40-80 | 80-200 | 150-400 |
| VFX/particles | 10-20 | 20-40 | 30-60 | 50-100 |
| UI/HUD | 10-20 | 10-20 | 10-20 | 10-20 |
| Shadows | 30-50 | 50-100 | 100-200 | 150-300 |
| **TOTAL** | **~200-400** | **~400-800** | **~800-1,500** | **~1,500-3,000** |

**SRP Batcher note:** Unity URP's SRP Batcher groups draw calls by shader variant, making same-material objects nearly free after the first call. This is why material atlasing and trim sheets are critical -- 20 buildings sharing one trim sheet material = 20 draw calls batched as ~1 effective cost.

### 3.4 GPU Instancing Requirements

These asset types MUST use GPU instancing to hit budget:
- **Grass:** Mandatory. 30,000 blades at 8 tris = 240K tris but must be 1-2 draw calls.
- **Small rocks:** Mandatory at >20 visible.
- **Small props (barrels, crates):** Recommended at >10 visible.
- **Trees:** Recommended. Use instance + LOD groups.
- **Castle wall sections:** Recommended for large fortifications.

---

## 4. Tripo-Specific Decimation Targets

### 4.1 Tripo API face_limit Values

The Tripo v2.5 API supports a `face_limit` parameter that limits output faces. If unset, it's adaptively determined. When `quad=True` and face_limit unset, defaults to 10,000 quad faces.

**Recommended face_limit per asset type for Tripo API call:**

| Asset Type | face_limit (tris) | face_limit (quad) | Rationale |
|---|---|---|---|
| Player character | 50,000 | 15,000 | Request high detail, decimate in Blender for LODs. |
| Standard mob | 15,000 | 5,000 | Match Medium LOD0 target directly. |
| Elite/boss enemy | 40,000 | 12,000 | Request high, decimate to tier targets. |
| NPC | 20,000 | 7,000 | Slightly over Medium target for flexibility. |
| Building exterior small | 10,000 | 4,000 | Request High target, decimate for lower tiers. |
| Building exterior large | 30,000 | 10,000 | Complex structures need geometry. |
| Castle wall section | 5,000 | 2,000 | Simple repeating module. |
| Tree trunk | 8,000 | 3,000 | Organic forms need silhouette detail. |
| Rock small | 1,000 | 500 | Minimal geometry; normal map does the rest. |
| Rock large | 5,000 | 2,000 | Needs good silhouette. |
| Barrel/crate | 1,500 | 600 | Simple geometric shape. |
| Cart/bench | 4,000 | 1,500 | Multiple parts need resolution. |
| Market stall | 6,000 | 2,500 | Canvas draping + frame. |
| Weapon | 5,000 | 2,000 | Blade/handle detail matters. |
| Shield | 4,000 | 1,500 | Both sides visible. |
| Armor piece | 6,000 | 2,500 | Worn on character, close to camera. |
| Furniture (table/chair/bed) | 2,000 | 800 | Simple shapes. |
| Door | 1,500 | 600 | Flat panel. |
| Torch sconce | 500 | 300 | Very small asset. |
| Well | 3,000 | 1,200 | Stone ring + structure. |

### 4.2 Post-Import Decimation Pipeline

After Tripo generates a model, the Blender pipeline runs:

```
1. Import GLB/FBX from Tripo
2. mesh_auto_repair (remove doubles, fill holes, fix normals)
3. mesh_analyze_topology (get current tri count, grade)
4. IF tri_count > target_for_asset_type:
     mesh_retopologize(target_faces=LOD0_target_for_quality_tier)
5. Generate LOD chain (LOD0 -> LOD1 -> LOD2 -> LOD3)
6. UV unwrap + texture pipeline
7. mesh_check_game_ready(poly_budget=LOD0_target)
```

### 4.3 When Tripo Output is "Good Enough" vs Needs Heavy Decimation

| Tripo Output | Condition | Action |
|---|---|---|
| **< 1.5x target** | Within 50% of LOD0 budget | Light decimation only. Quality preserved well. |
| **1.5x - 3x target** | Moderate overshoot | Standard Quadriflow retopo. ~10-15% silhouette quality loss. Acceptable. |
| **3x - 10x target** | Heavy overshoot | Aggressive retopo. Use silhouette-preserving decimation. ~20-30% quality loss. Check visually. |
| **> 10x target** | Extreme (200K+ tris for a barrel) | Two-pass: rough decimate to 3x, then careful retopo. High quality loss risk. Always visual check. |

### 4.4 Quality Loss Thresholds

| Decimation Ratio | Quality Impact | Acceptable For |
|---|---|---|
| 1.0 -> 0.7 (30% reduction) | Negligible. Removes hidden/internal faces. | All assets. |
| 0.7 -> 0.5 (50% of original) | Minor. Slight silhouette softening. | All assets except hero close-ups. |
| 0.5 -> 0.25 (75% reduction) | Moderate. Visible on close inspection. Sharp edges round off. | LOD1+, background assets. |
| 0.25 -> 0.10 (90% reduction) | Significant. Reads as same object but detail gone. | LOD2+, distant assets. |
| < 0.10 (>90% reduction) | Severe. Silhouette-only recognition. | LOD3, billboard candidates. |

**Hard rule:** Never decimate below the point where the asset's TYPE is unrecognizable. A barrel at 100 tris should still read as "barrel" from 10 meters.

---

## 5. LOD Chain Specifications

### 5.1 LOD Distances (Screen Percentage Thresholds)

Unity LOD Group uses screen percentage (% of screen height the object's bounding box covers).

| LOD Level | Screen % | Approximate Distance (3rd person) | Triangle Ratio |
|---|---|---|---|
| **LOD0** | > 25% | 0-15m | 1.0 (full) |
| **LOD1** | 25% - 10% | 15-40m | 0.50 |
| **LOD2** | 10% - 3% | 40-100m | 0.25 |
| **LOD3** | 3% - 1% | 100-300m | 0.10 |
| **Cull** | < 1% | > 300m | 0 (not rendered) |

### 5.2 Per-Asset-Type LOD Chains

#### Characters

| Asset | LOD0 (>25%) | LOD1 (>10%) | LOD2 (>3%) | LOD3 (>1%) | Billboard? |
|---|---|---|---|---|---|
| Player | 100% | 50% | 25% | 10% | No (always rendered) |
| Standard mob | 100% | 50% | 25% | 8% | No |
| Elite/boss | 100% | 50% | 25% | 10% | No |
| NPC | 100% | 50% | 25% | 10% | No |

**Character LOD notes:**
- LOD2+: merge all equipment into single mesh + texture atlas (reduces draw calls from 6-8 to 1)
- LOD2+: simplify skeleton to major bones only (spine, hips, head, upper arms, upper legs)
- LOD3: disable cloth simulation, reduce bone influences to 1 per vertex
- Characters should NEVER billboard (silhouette is too distinctive)

#### Buildings & Architecture

| Asset | LOD0 (>20%) | LOD1 (>8%) | LOD2 (>2%) | LOD3 (>0.5%) | Billboard? |
|---|---|---|---|---|---|
| House | 100% | 50% | 20% | 7% | Yes (>500m) |
| Castle/monastery | 100% | 50% | 20% | 7% | Optional impostor |
| Wall section | 100% | 50% | 20% | -- | Cull at LOD2 distance |
| Gate | 100% | 50% | 20% | -- | Cull |
| Tower | 100% | 50% | 20% | 7% | Yes (landmark) |

**Building LOD notes:**
- Buildings use wider LOD bands (render LOD0 longer) because architectural silhouette is important
- LOD2+: collapse window/door detail to flat textured planes
- LOD3: simplify to box + roof silhouette only
- Large landmarks (towers, cathedrals) should use impostor billboards at extreme distance

#### Environment / Nature

| Asset | LOD0 (>15%) | LOD1 (>5%) | LOD2 (>1.5%) | LOD3 (>0.5%) | Billboard? |
|---|---|---|---|---|---|
| Tree | 100% | 50% | 15% | Billboard | Yes (mandatory) |
| Rock small | 100% | 50% | -- | -- | No (cull at LOD1) |
| Rock large | 100% | 50% | 20% | -- | No (cull at LOD2) |
| Dead tree/stump | 100% | 50% | 15% | -- | No |
| Log | 100% | 50% | -- | -- | No (cull) |

**Vegetation LOD notes:**
- Trees MUST billboard at distance (standard SpeedTree-style cross-billboard at LOD3)
- Small rocks cull aggressively -- they contribute to ground clutter only at close range
- Grass uses distance-based density fade, not traditional LOD (50% density at 20m, 0% at 40m on Low; 60m on Ultra)

#### Props

| Asset | LOD0 (>10%) | LOD1 (>3%) | LOD2 (>1%) | Billboard? |
|---|---|---|---|---|
| Barrel/crate | 100% | 50% | 15% | No (cull) |
| Cart/bench | 100% | 50% | 20% | No (cull) |
| Market stall | 100% | 50% | 20% | No (cull) |
| Well | 100% | 50% | 20% | No (cull) |
| Torch sconce | 100% | 50% | -- | No (cull at LOD1) |
| Lantern post | 100% | 50% | 15% | No (cull) |
| Door | 100% | 50% | -- | No |

**Prop LOD notes:**
- Props generally need only 2-3 LODs (they're small, screen coverage drops fast)
- Smallest props (torches, sconces) can cull at LOD1 distance
- Interactable props (doors, chests) should NOT cull while in interaction range

#### Equipment

| Asset | LOD0 (>8%) | LOD1 (>3%) | LOD2 (>1%) | Billboard? |
|---|---|---|---|---|
| Weapon | 100% | 50% | 20% | No |
| Shield | 100% | 50% | 20% | No |
| Armor piece | 100% | 50% | 25% | No |

**Equipment LOD notes:**
- Equipment LODs are used when attached to characters at LOD1+
- At character LOD2, all equipment merges into character mesh (single draw call)
- Dropped-on-ground weapons use standard prop LOD chain

### 5.3 Crossfade Settings

| Setting | Value | Notes |
|---|---|---|
| **Crossfade mode** | Animated | Use `LODFadeMode.CrossFade` in Unity |
| **Crossfade band width** | 10-15% of LOD distance | Prevents pop-in |
| **Hysteresis** | 5% | LOD switches down at 95% of threshold, up at 105%. Prevents oscillation. |
| **Speed fade** | 0.5 seconds | Time-based crossfade duration |

**Implementation in Unity:**
```csharp
LODGroup lodGroup = gameObject.AddComponent<LODGroup>();
lodGroup.fadeMode = LODFadeMode.CrossFade;
lodGroup.animateCrossFading = true;
// Set LOD levels with screen relative transition heights
```

### 5.4 Assets That Need Billboards vs Cull

| Needs Billboard | Just Cull |
|---|---|
| Trees (mandatory -- visible at extreme range) | Small rocks |
| Large buildings/landmarks | Logs, stumps |
| Towers | Small props (barrels, crates) |
| | Medium props (carts, benches) |
| | Torch sconces, lanterns |
| | Equipment (handled by character LOD) |

---

## 6. Disk/Download Size Budgets

### 6.1 Target Install Size: 8-15 GB

| Component | Budget | Notes |
|---|---|---|
| **Meshes (all LODs)** | 500 MB - 1 GB | Compressed FBX/mesh assets. Draco in GLB reduces by 70-90%. |
| **Textures** | 3 - 6 GB | BC7/BC5 compressed. Largest component. |
| **Audio** | 1 - 2 GB | Music, SFX, voice (if any). Vorbis/ADPCM. |
| **Animations** | 200 - 500 MB | Skeletal animation clips. |
| **Terrain data** | 200 - 500 MB | Heightmaps, splatmaps, detail maps. |
| **Shaders + scripts** | 50 - 100 MB | Compiled shader variants + C# assemblies. |
| **UI + other** | 100 - 200 MB | Fonts, sprites, configs, prefabs. |
| **TOTAL** | **~8 - 15 GB** | Competitive with Elden Ring (~45 GB) but much leaner scope. |

### 6.2 Per-Asset Compressed Size Estimates

**Mesh size rule of thumb:** ~20-40 bytes per triangle (compressed, with normals + UV + tangents).

| Asset Type | LOD0 Tris (Med) | Mesh Size (all LODs) | Textures | Total per asset |
|---|---|---|---|---|
| Player character | 35,000 | ~2 MB | ~15 MB (2048 x3) | ~17 MB |
| Standard mob | 10,000 | ~600 KB | ~6 MB (1024 x3) | ~7 MB |
| Building small | 5,000 | ~300 KB | ~8 MB (2048 trim) | ~8 MB |
| Tree | 4,000 | ~250 KB | ~4 MB (1024 x2) | ~4 MB |
| Small prop | 600 | ~40 KB | ~1 MB (512 x2) | ~1 MB |
| Weapon | 3,000 | ~200 KB | ~6 MB (1024 x3) | ~6 MB |

### 6.3 Asset Bundle Streaming Strategy

For a world with multiple zones:

| Bundle Type | Contents | Size Target | Loading |
|---|---|---|---|
| **Core** | Player, UI, common VFX, shared materials | 200-500 MB | Always loaded |
| **Zone** (per area) | Zone terrain, buildings, unique props | 300-800 MB | Load on zone enter |
| **Enemy set** | Enemy meshes, anims, VFX per encounter type | 50-200 MB | Load on proximity |
| **Interior** | Room furniture, interior props, lighting | 50-150 MB | Load on door enter |

### 6.4 Compression Strategy

| Data Type | Format | Compression | Ratio |
|---|---|---|---|
| Meshes | Unity .mesh (internal) | LZ4 chunk compression | ~60-70% of raw |
| Textures | BC7 (color), BC5 (normal) | GPU-native, already compressed | ~6:1 vs RGBA32 |
| Animations | Unity .anim | LZ4 | ~50-70% of raw |
| Audio | Vorbis (music), ADPCM (SFX) | Built-in | ~10:1 (music), ~4:1 (SFX) |
| Heightmaps | 16-bit RAW → Unity terrain | LZ4 | ~40-60% of raw |

---

## 7. Implementation: ASSET_BUDGETS Config Dict

This is the recommended single source of truth for the toolkit pipeline:

```python
ASSET_BUDGETS = {
    # Characters
    "player_character": {
        "lod0_tris": {"low": 25000, "medium": 35000, "high": 50000, "ultra": 70000},
        "lod_ratios": [1.0, 0.5, 0.25, 0.1],
        "lod_screen_pct": [0.25, 0.10, 0.03, 0.01],
        "texture_res": {"low": 1024, "medium": 2048, "high": 2048, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 50000,
        "needs_billboard": False,
    },
    "enemy_standard": {
        "lod0_tris": {"low": 6000, "medium": 10000, "high": 15000, "ultra": 20000},
        "lod_ratios": [1.0, 0.5, 0.25, 0.08],
        "lod_screen_pct": [0.25, 0.10, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 15000,
        "needs_billboard": False,
    },
    "enemy_elite": {
        "lod0_tris": {"low": 12000, "medium": 18000, "high": 25000, "ultra": 35000},
        "lod_ratios": [1.0, 0.5, 0.25, 0.1],
        "lod_screen_pct": [0.25, 0.10, 0.03, 0.01],
        "texture_res": {"low": 1024, "medium": 1024, "high": 2048, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 40000,
        "needs_billboard": False,
    },
    "enemy_boss": {
        "lod0_tris": {"low": 25000, "medium": 40000, "high": 60000, "ultra": 80000},
        "lod_ratios": [1.0, 0.5, 0.25, 0.1],
        "lod_screen_pct": [0.25, 0.10, 0.03, 0.01],
        "texture_res": {"low": 1024, "medium": 1024, "high": 2048, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 40000,
        "needs_billboard": False,
    },
    "npc": {
        "lod0_tris": {"low": 8000, "medium": 15000, "high": 22000, "ultra": 30000},
        "lod_ratios": [1.0, 0.5, 0.25, 0.1],
        "lod_screen_pct": [0.25, 0.10, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 2048, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 20000,
        "needs_billboard": False,
    },

    # Buildings & Architecture
    "building_small": {
        "lod0_tris": {"low": 3000, "medium": 5000, "high": 8000, "ultra": 12000},
        "lod_ratios": [1.0, 0.5, 0.2, 0.07],
        "lod_screen_pct": [0.20, 0.08, 0.02, 0.005],
        "texture_res": {"low": 1024, "medium": 2048, "high": 2048, "ultra": 4096},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 10000,
        "needs_billboard": True,
    },
    "building_large": {
        "lod0_tris": {"low": 8000, "medium": 15000, "high": 25000, "ultra": 40000},
        "lod_ratios": [1.0, 0.5, 0.2, 0.07],
        "lod_screen_pct": [0.20, 0.08, 0.02, 0.005],
        "texture_res": {"low": 1024, "medium": 2048, "high": 2048, "ultra": 4096},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 30000,
        "needs_billboard": True,
    },
    "wall_section": {
        "lod0_tris": {"low": 1500, "medium": 2500, "high": 4000, "ultra": 6000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.20, 0.08, 0.02],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 5000,
        "needs_billboard": False,
    },
    "gate_portcullis": {
        "lod0_tris": {"low": 2000, "medium": 4000, "high": 6000, "ultra": 8000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.20, 0.08, 0.02],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 6000,
        "needs_billboard": False,
    },
    "tower": {
        "lod0_tris": {"low": 3000, "medium": 6000, "high": 10000, "ultra": 15000},
        "lod_ratios": [1.0, 0.5, 0.2, 0.07],
        "lod_screen_pct": [0.20, 0.08, 0.02, 0.005],
        "texture_res": {"low": 1024, "medium": 2048, "high": 2048, "ultra": 4096},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 10000,
        "needs_billboard": True,
    },

    # Environment / Nature
    "tree": {
        "lod0_tris": {"low": 2000, "medium": 4000, "high": 6000, "ultra": 8000},
        "lod_ratios": [1.0, 0.5, 0.15, 0.0],  # 0.0 = billboard
        "lod_screen_pct": [0.15, 0.05, 0.015, 0.005],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 8000,
        "needs_billboard": True,
    },
    "rock_small": {
        "lod0_tris": {"low": 200, "medium": 400, "high": 600, "ultra": 1000},
        "lod_ratios": [1.0, 0.5],
        "lod_screen_pct": [0.10, 0.03],
        "texture_res": {"low": 256, "medium": 512, "high": 512, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 1000,
        "needs_billboard": False,
    },
    "rock_large": {
        "lod0_tris": {"low": 800, "medium": 1500, "high": 3000, "ultra": 5000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.15, 0.05, 0.015],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 5000,
        "needs_billboard": False,
    },
    "dead_tree_stump": {
        "lod0_tris": {"low": 500, "medium": 1000, "high": 2000, "ultra": 3000},
        "lod_ratios": [1.0, 0.5, 0.15],
        "lod_screen_pct": [0.15, 0.05, 0.015],
        "texture_res": {"low": 256, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 3000,
        "needs_billboard": False,
    },
    "log": {
        "lod0_tris": {"low": 200, "medium": 400, "high": 800, "ultra": 1200},
        "lod_ratios": [1.0, 0.5],
        "lod_screen_pct": [0.10, 0.03],
        "texture_res": {"low": 256, "medium": 512, "high": 512, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 1200,
        "needs_billboard": False,
    },
    "grass_blade": {
        "lod0_tris": {"low": 4, "medium": 6, "high": 8, "ultra": 12},
        "lod_ratios": [],  # Uses density fade, not LOD
        "lod_screen_pct": [],
        "texture_res": {"low": 256, "medium": 512, "high": 512, "ultra": 1024},
        "texture_channels": ["albedo"],
        "tripo_face_limit": None,  # Not generated by Tripo
        "needs_billboard": False,
    },

    # Props
    "barrel_crate": {
        "lod0_tris": {"low": 300, "medium": 600, "high": 1000, "ultra": 1500},
        "lod_ratios": [1.0, 0.5, 0.15],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 256, "medium": 512, "high": 512, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 1500,
        "needs_billboard": False,
    },
    "cart_bench": {
        "lod0_tris": {"low": 800, "medium": 1500, "high": 3000, "ultra": 4500},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 4000,
        "needs_billboard": False,
    },
    "market_stall": {
        "lod0_tris": {"low": 1500, "medium": 3000, "high": 5000, "ultra": 7000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 6000,
        "needs_billboard": False,
    },
    "well": {
        "lod0_tris": {"low": 800, "medium": 1500, "high": 2500, "ultra": 4000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 3000,
        "needs_billboard": False,
    },
    "torch_sconce": {
        "lod0_tris": {"low": 100, "medium": 200, "high": 400, "ultra": 600},
        "lod_ratios": [1.0, 0.5],
        "lod_screen_pct": [0.10, 0.03],
        "texture_res": {"low": 128, "medium": 256, "high": 256, "ultra": 512},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 500,
        "needs_billboard": False,
    },
    "lantern_post": {
        "lod0_tris": {"low": 300, "medium": 600, "high": 1000, "ultra": 1500},
        "lod_ratios": [1.0, 0.5, 0.15],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 256, "medium": 512, "high": 512, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 1500,
        "needs_billboard": False,
    },
    "door": {
        "lod0_tris": {"low": 300, "medium": 600, "high": 1200, "ultra": 2000},
        "lod_ratios": [1.0, 0.5],
        "lod_screen_pct": [0.10, 0.03],
        "texture_res": {"low": 256, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 1500,
        "needs_billboard": False,
    },

    # Equipment
    "weapon": {
        "lod0_tris": {"low": 1500, "medium": 3000, "high": 5000, "ultra": 8000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.08, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 5000,
        "needs_billboard": False,
    },
    "shield": {
        "lod0_tris": {"low": 1000, "medium": 2000, "high": 3500, "ultra": 5000},
        "lod_ratios": [1.0, 0.5, 0.2],
        "lod_screen_pct": [0.08, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 4000,
        "needs_billboard": False,
    },
    "armor_piece": {
        "lod0_tris": {"low": 2000, "medium": 4000, "high": 6000, "ultra": 8000},
        "lod_ratios": [1.0, 0.5, 0.25],
        "lod_screen_pct": [0.08, 0.03, 0.01],
        "texture_res": {"low": 512, "medium": 1024, "high": 1024, "ultra": 2048},
        "texture_channels": ["albedo", "normal", "orm"],
        "tripo_face_limit": 6000,
        "needs_billboard": False,
    },

    # Interior Furniture
    "table": {
        "lod0_tris": {"low": 400, "medium": 800, "high": 1500, "ultra": 2500},
        "lod_ratios": [1.0, 0.5, 0.25],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 256, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 2000,
        "needs_billboard": False,
    },
    "chair": {
        "lod0_tris": {"low": 300, "medium": 600, "high": 1200, "ultra": 2000},
        "lod_ratios": [1.0, 0.5, 0.25],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 256, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 2000,
        "needs_billboard": False,
    },
    "bed": {
        "lod0_tris": {"low": 500, "medium": 1000, "high": 2000, "ultra": 3000},
        "lod_ratios": [1.0, 0.5, 0.25],
        "lod_screen_pct": [0.10, 0.03, 0.01],
        "texture_res": {"low": 256, "medium": 512, "high": 1024, "ultra": 1024},
        "texture_channels": ["albedo", "normal"],
        "tripo_face_limit": 2000,
        "needs_billboard": False,
    },
}
```

---

## 8. Alignment with Existing Toolkit Code

### 8.1 Current LOD_PRESETS (lod_pipeline.py) vs These Budgets

The existing `LOD_PRESETS` in `lod_pipeline.py` need updating to match these budgets:

| Preset Key | Current min_tris | Recommended min_tris (Medium tier) |
|---|---|---|
| `hero_character` | [30000, 15000, 7500, 3000] | [35000, 17500, 8750, 3500] |
| `standard_mob` | [8000, 4000, 2000, 800] | [10000, 5000, 2500, 800] |
| `building` | [5000, 2500, 1000, 500] | [5000, 2500, 1000, 350] |
| `prop_small` | [500, 250, 100] | [600, 300, 90] |
| `prop_medium` | [1000, 500, 200] | [1500, 750, 300] |
| `weapon` | [3000, 1500, 500] | [3000, 1500, 600] |
| `vegetation` | [5000, 2500, 800, 4] | [4000, 2000, 600, 4] |
| `furniture` | [200, 100, 50] | [800, 400, 200] |

**Key discrepancy:** `furniture` preset has `min_tris: [200, 100, 50]` which is far too low for a Gothic carved chair at 600-2000 tris. Must update.

### 8.2 Current poly_budget Defaults

| Location | Current Default | Should Be |
|---|---|---|
| `blender_server.py:723` (game_check) | 90,000 | Varies by asset type -- pass from ASSET_BUDGETS |
| `blender_server.py:1374` (retopo) | 50,000 | Varies by asset type |
| `blender_server.py:1413` (target_faces) | 4,000 | Varies by asset type |
| `blender_server.py:2107` (pipeline) | 50,000 | Varies by asset type |
| `blender_server.py:3070` (world) | 90,000 / 120,000 | Varies by asset type |

**Recommendation:** Replace all hardcoded defaults with lookup from `ASSET_BUDGETS[asset_type]["lod0_tris"][quality_tier]`. Require `asset_type` parameter on all pipeline operations.

---

## 9. Common Pitfalls

### Pitfall 1: Tripo Over-Generation
**What goes wrong:** Requesting face_limit=50000 for a barrel gives Tripo too much budget, producing 50K tris of noise topology that decimation struggles to clean.
**How to avoid:** ALWAYS pass tight face_limit matching the asset type. A barrel should request face_limit=1500, not rely on post-processing.

### Pitfall 2: Texture Resolution as VRAM Killer
**What goes wrong:** Giving every prop 2048x2048 textures. A scene with 50 unique props at 2048 full PBR = 50 x 7.4 MB = 370 MB just for props.
**How to avoid:** Small props get 256-512. Only hero assets and buildings get 2048. Use atlases for sets of similar props.

### Pitfall 3: LOD Distance Too Aggressive
**What goes wrong:** Popping artifacts when LOD transitions are at wrong distances for third-person camera.
**How to avoid:** Use screen percentage, not world distance. Third-person camera is 5-8m behind player, so "close" objects are already 10-15m away. LOD0 should persist until object is <25% screen height.

### Pitfall 4: Draw Call Budget Ignored
**What goes wrong:** Scene runs at 60fps in triangle budget but stutters because 2000+ unique materials create CPU-bound draw call overhead.
**How to avoid:** Batch materials. Use trim sheets (1 material per architectural style). SRP Batcher. GPU instancing for repeated props.

### Pitfall 5: No Quality Tier Scaling
**What goes wrong:** Game runs fine on RTX 3080 but unplayable on GTX 1050.
**How to avoid:** Implement all 4 tiers. Low tier uses LOD1 as the "close" model, halves texture resolution, reduces grass density 75%, reduces shadow distance 50%.

---

## 10. Sources

### Primary (HIGH confidence)
- Existing VeilBreakers AAA_QUALITY_ASSETS.md research (cross-verified with Polycount wiki data)
- Existing VeilBreakers AAA_BEST_PRACTICES_COMPREHENSIVE.md (GDC-sourced)
- Existing VeilBreakers PROCEDURAL_3D_AAA_SPECS.md
- Existing lod_pipeline.py LOD_PRESETS (current codebase)
- [Polycount wiki - Triangle counts from various videogames](https://polycount.com/discussion/126662/triangle-counts-for-assets-from-various-videogames) -- shipped game asset data
- [Tripo API docs - face_limit parameter](https://platform.tripo3d.ai/docs/generation) -- face_limit range, quad defaults
- [Tripo v2.5 on fal.ai](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d/api) -- full API parameter reference
- [Unity URP performance docs](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/configure-for-better-performance.html)

### Secondary (MEDIUM confidence)
- [Tripo LOD strategy blog](https://www.tripo3d.ai/blog/explore/smart-mesh-lod-generation-strategy-for-low-poly-assets) -- LOD ratios 50%/25%/10%
- [Tripo retopology pipeline blog](https://www.tripo3d.ai/blog/explore/retopology-pipeline-for-ai-generated-models) -- 5K prop, 15K character targets
- [VRAM usage analysis 2024/2025](https://www.overclock.net/threads/how-vram-is-used-in-2023-2024-2025-games-at-1080p.1817387/)
- [TechSpot VRAM requirements](https://www.techspot.com/review/2856-how-much-vram-pc-gaming/)
- [Diablo IV VRAM requirements](https://us.forums.blizzard.com/en/d4/t/6gb-vram-texture-options/2840)

### Tertiary (LOW confidence -- estimates)
- Per-asset compressed disk size estimates (rule of thumb, not measured)
- Grass blade tri count (varies wildly by implementation)
- Asset bundle streaming sizes (project-specific, will need tuning)

---

## Metadata

**Confidence breakdown:**
- Per-asset triangle budgets: HIGH -- cross-referenced shipped game data, existing research, Polycount wiki
- Texture resolution tiers: HIGH -- standard BC7 sizes are well-documented, VRAM scaling is industry standard
- Scene triangle budget: HIGH -- 2-6M for Souls-like at 60fps is widely cited
- Tripo face_limit values: HIGH -- directly from Tripo API documentation
- LOD specifications: HIGH -- industry standard ratios confirmed across multiple sources
- Disk size estimates: MEDIUM -- rule of thumb, not project-measured
- Draw call budgets: MEDIUM -- highly dependent on SRP Batcher effectiveness and material count

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable domain -- polygon budgets change slowly; Tripo API params may update)
