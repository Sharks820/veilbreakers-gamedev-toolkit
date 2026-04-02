# Procedural 3D Modeling -- AAA Implementable Specs for Blender Toolkit

**Researched:** 2026-04-01
**Purpose:** Specific, number-driven specs for procedural generation in Blender (export to Unity URP)
**Sources:** GDC talks, Frostbite/CryEngine papers, Polycount wiki, physicallybased.info, GPU Gems, World Machine/Gaea docs, SpeedTree docs, studio breakdowns (FromSoftware, CDPR, Bethesda, Ubisoft, Guerrilla)

---

## 1. TERRAIN

### 1.1 Heightmap Resolution

| World Size | Heightmap Resolution | Meters/Pixel | Use Case |
|---|---|---|---|
| 1 km x 1 km | 1025 x 1025 | ~0.98 m | Single zone / dungeon exterior |
| 2 km x 2 km | 2049 x 2049 | ~0.98 m | Settlement + surrounding area |
| 4 km x 4 km | 4097 x 4097 | ~0.98 m | Region (Limgrave-sized) |
| 8 km x 8 km | 8193 x 8193 | ~0.98 m | Full open world tile |
| 16 km x 16 km | 4097 x 4097 (tiled 4x4) | ~0.98 m per tile | Mega-world (Elden Ring scale) |

**Format:** 16-bit PNG or RAW (65,536 height levels). 32-bit float for World Machine/Gaea intermediate work.
**Height range:** 0-1000m typical for a region. 0-500m for a single zone.
**Unity import:** Unity terrain uses power-of-2-plus-1 resolutions (513, 1025, 2049, 4097).

### 1.2 Erosion Simulation

Implement 3 erosion types in the Blender heightmap pipeline:

**Hydraulic Erosion (most important):**
- Simulate water droplets flowing downhill, carrying sediment
- Parameters: `droplet_count` = 50,000-200,000 per km^2, `erosion_rate` = 0.01-0.05, `deposition_rate` = 0.01-0.03, `evaporation_rate` = 0.01-0.02, `max_lifetime` = 30-64 steps
- Creates: river channels, alluvial fans, valleys, natural drainage patterns
- GPU implementation: use compute shader or numpy vectorized for speed (~2-5 sec for 2049^2)

**Thermal Erosion (talus slopes):**
- Material above talus angle slides downhill
- Parameters: `talus_angle` = 35-45 degrees (rock), 25-35 degrees (soil), `erosion_amount` = 0.5-2.0 per iteration, `iterations` = 20-50
- Creates: scree slopes, cliff base debris, smooth hillsides

**Wind Erosion (optional, desert/exposed):**
- Moves material in wind direction, preferring fine particles
- Parameters: `wind_direction`, `wind_strength` = 0.01-0.05, `iterations` = 10-30
- Creates: dune forms, exposed rock faces, wind-carved features

**Erosion pass order:** Thermal first (establishes slopes) -> Hydraulic (carves channels) -> Wind (final polish).

### 1.3 Biome Blending

**Transition width:** 20-50 meters between biomes (narrower = more dramatic, wider = more natural).

**Blending method:** Height-based + noise-masked smoothstep:
```
blend = smoothstep(0, 1, (distance_from_boundary + noise * jitter) / transition_width)
```
- `jitter` = 5-15m of Perlin noise offset to break up straight boundaries
- Noise frequency: 0.02-0.05 (large-scale variation)

**Biome parameters for a dark fantasy world:**

| Biome | Ground Layers | Vegetation Density | Height Range | Slope Range |
|---|---|---|---|---|
| Dark Forest | moss, loam, roots, rock | 0.7-0.9 | 0-200m | 0-30 deg |
| Corrupted Wasteland | ash, cracked earth, embers | 0.0-0.1 | 50-300m | 0-25 deg |
| Swamp/Rot | mud, murky water, reeds | 0.4-0.6 | 0-50m | 0-10 deg |
| Mountain/Cliff | rock, gravel, snow, ice | 0.1-0.3 | 200-1000m | 20-70 deg |
| Grassy Plains | grass, wildflowers, dirt path | 0.5-0.8 | 0-150m | 0-20 deg |
| Ruins/Settlement | cobblestone, dirt, rubble | 0.1-0.3 | any | 0-15 deg |

### 1.4 Cliff Face Generation

**Detection:** Identify terrain faces with slope > 55-65 degrees.

**Geometry approach:**
- Extract cliff faces as separate mesh regions from terrain
- Apply triplanar UV mapping (eliminates stretching on vertical surfaces)
- Triplanar blend sharpness: 4.0-8.0 (higher = sharper transitions between projection planes)

**Detail geometry:**
- Extrude cliff ledges every 3-8m vertical distance (0.5-1.5m depth, 0.3-0.8m height)
- Add rock outcrop meshes at 2-5 per 10m^2 of cliff face
- Crack/crevice detail via normal map or displacement: depth 0.1-0.3m

**Cliff rock material:**
- Base: triplanar projected rock texture at 1m tiling
- Overlay: moss/lichen on top-facing normals (world Y > 0.7), blend width 0.1-0.3
- Cavity: darker albedo (multiply 0.5-0.7) in AO-detected recesses

### 1.5 Terrain Texture Splatting

**Layer count:** 4 layers per splat map RGBA. Use 2-4 splat maps for 8-16 total layers.
- Recommended: **8 layers** (2 splat maps) for most terrain
- Maximum practical: **16 layers** (4 splat maps) with virtual texturing

**Per-layer textures (tiling):**

| Map | Resolution | Format | Purpose |
|---|---|---|---|
| Albedo | 1024 x 1024 | BC7 | Base color (tiling) |
| Normal | 1024 x 1024 | BC5 | Surface normal (tiling) |
| ORM | 512 x 512 | BC7 | AO (R), Roughness (G), Metallic (B) |
| Height | 512 x 512 | BC4 | Height-based blending between layers |

**Splat map resolution:** 512 x 512 per terrain tile (1 km^2) for broad blending; 1024 x 1024 for detailed paintwork.

**Height-based blending (Frostbite technique):**
```
// Per pixel, for each pair of layers:
float h1 = tex2D(heightmap_layer1, uv) + splat_weight1;
float h2 = tex2D(heightmap_layer2, uv) + splat_weight2;
float blend_depth = 0.2;  // Controls transition sharpness
float ma = max(h1, h2) - blend_depth;
float b1 = max(h1 - ma, 0);
float b2 = max(h2 - ma, 0);
float3 result = (color1 * b1 + color2 * b2) / (b1 + b2);
```
This produces natural-looking transitions where rocks poke through dirt based on their height texture.

### 1.6 Micro-Detail (Close Range)

**Pebbles/debris:**
- Spawn as instanced meshes within 15-30m of camera
- 4-20 triangles each, density 2-8 per m^2 on appropriate surfaces
- Use vertex color for random tint variation (5-15% hue shift)
- Cull beyond 30m, fade 25-30m

**Grass at close range:**
- Mesh grass (not billboard) within 20-40m
- 4-12 tris per tuft, 8-20 tufts per m^2
- Beyond 40m: switch to billboard cards (2 tris per tuft)
- Beyond 80-100m: terrain shader grass color tint only (zero geometry)

**Tessellation/displacement (if GPU budget allows):**
- Apply only within 10-20m of camera
- Tessellation factor: 4-8x in near range
- Displacement height: 0.02-0.1m (subtle rocks, roots, cracks)
- Use distance-based tessellation falloff

### 1.7 Terrain LOD Strategy

**Recommended: CDLOD (Continuous Distance-Dependent LOD)**

Quadtree-based, adapts to terrain complexity:

| LOD Level | Grid Spacing | Distance Range | Triangles/Chunk |
|---|---|---|---|
| LOD 0 | 0.5-1 m | 0-100 m | 4,096-16,384 |
| LOD 1 | 2 m | 100-250 m | 1,024-4,096 |
| LOD 2 | 4 m | 250-500 m | 256-1,024 |
| LOD 3 | 8 m | 500-1000 m | 64-256 |
| LOD 4 | 16 m | 1000-2000 m | 16-64 |
| LOD 5+ | 32-64 m | 2000+ m | 4-16 |

**Transition:** Morph vertices between LOD levels using morphing factor based on distance. No visible popping.

**Chunk size:** 64x64 or 128x128 vertices per chunk (before LOD reduction).

**For Blender export:** Pre-generate LOD meshes as separate objects. Unity applies at runtime via terrain system or custom chunked mesh.

---

## 2. ARCHITECTURE / BUILDINGS

### 2.1 Modular Building System

**Grid standard:** 1m primary, 0.5m secondary, 0.25m fine detail.

**Module library per building style (minimum viable kit: 25-40 pieces):**

```
WALLS (8-12 pieces):
  wall_straight_2m, wall_straight_4m, wall_straight_6m
  wall_corner_inner_90, wall_corner_outer_90
  wall_door_frame_1.2m, wall_door_frame_2m
  wall_window_frame_1m, wall_window_frame_1.5m
  wall_half_timber (exposed beam variant)
  wall_damaged_1, wall_damaged_2

ROOFS (6-8 pieces):
  roof_slope_2m, roof_slope_4m
  roof_ridge, roof_eave
  roof_gable_end, roof_hip_corner
  roof_dormer, roof_chimney

FLOORS/CEILINGS (4-6 pieces):
  floor_2x2, floor_4x4
  ceiling_2x2, ceiling_beamed
  stair_straight_3m, stair_spiral_segment

FOUNDATIONS (3-4 pieces):
  foundation_block_2m, foundation_block_4m
  foundation_corner, foundation_step

DETAILS (6-10 pieces):
  beam_horizontal_2m, beam_vertical_3m
  bracket_corbel, pillar_1m
  window_shutters, door_plank, door_iron
  trim_horizontal, trim_corner
  balcony_railing_2m
```

**Pivot convention:** Bottom-left-back corner for asymmetric pieces. Bottom-center for symmetric pieces (pillars, doors). This ensures snapping at grid coordinates.

**Triangle budgets per module:**

| Module Type | LOD0 Tris | LOD1 Tris | LOD2 Tris |
|---|---|---|---|
| Wall section (4m) | 200-600 | 100-300 | 50-100 |
| Roof section | 300-800 | 150-400 | 50-150 |
| Door/window frame | 400-1200 | 200-600 | 50-200 |
| Pillar/column | 200-800 | 100-400 | 50-100 |
| Stair section | 500-1500 | 200-600 | 100-200 |
| Full building (assembled) | 3,000-15,000 | 1,500-7,000 | 500-2,000 |

### 2.2 Trim Sheet Texturing

**Atlas sizes:**
- Primary trim sheet: **2048 x 2048** (covers walls, floors, trim, roofing)
- Secondary trim sheet: **2048 x 2048** (doors, windows, details, damage)
- Optional tiling set: **1024 x 1024** per tiling texture (brick, plaster, wood planks)

**UV mapping strategy:**
- All modular pieces UV-mapped to shared trim sheet
- Trim sheet organized in horizontal bands (tiling along U axis):
  - Row 0-25%: Stone/brick variations (3-4 varieties)
  - Row 25-50%: Wood plank/beam variations
  - Row 50-70%: Plaster/stucco/daub
  - Row 70-85%: Metal/iron details, hinges, nails
  - Row 85-100%: Trim, molding, edge pieces
- Texel density: **5.12-10.24 px/cm** (512-1024 pixels per meter) for 2K trim sheet

**Benefits:** Single material per building style -> 1 draw call for entire building.

### 2.3 Procedural Weathering/Aging

**Layer stack (applied in Blender material/bake):**

1. **Base material:** Clean trim sheet
2. **Edge wear (curvature-driven):**
   - Detect convex edges via curvature map (bake from high-poly or compute from normals)
   - Lighten albedo +15-25% on convex edges
   - Increase roughness +0.15-0.3
   - For stone: expose lighter sub-surface color
   - For wood: expose grain, splinter texture
3. **Cavity dirt (AO-driven):**
   - Darken albedo in concave areas (multiply 0.5-0.7)
   - Increase roughness +0.1-0.2
   - Color shift toward brown/dark grey
4. **Moss/growth (world-normal + AO):**
   - Apply where world normal Y > 0.6 (top-facing) AND AO < 0.7 (sheltered)
   - Green-brown tint: sRGB (60, 85, 40)
   - Roughness: 0.7-0.9
   - Coverage: 10-40% of surface for moderate aging
5. **Stain streaks (height gradient):**
   - Dark vertical streaks below window sills, roof edges
   - Width: 0.1-0.3m, length: 0.5-2m
   - Albedo darken 20-40%

**Age parameter (0.0 = new, 1.0 = ancient ruins):**
- 0.0-0.2: Minor edge wear only
- 0.2-0.5: Edge wear + cavity dirt + minor moss
- 0.5-0.7: Heavy wear + dirt + moss + streaks + minor structural damage
- 0.7-1.0: Crumbling edges, heavy moss, missing pieces, collapsed sections

### 2.4 Foundation-to-Terrain Blending

- Sink building foundations 0.1-0.3m below terrain surface
- Apply vertex color gradient on foundation mesh bottom vertices (blend to terrain material)
- Blend distance: 0.3-1.0m vertically
- Scatter props at base: rubble, dirt mounds, grass tufts, moss patches
- Dirt/mud decals at doorway thresholds (1m x 2m, 30-50% opacity)

### 2.5 Interior-Exterior Transition

- Interior floor level: 0.1-0.15m above exterior ground (threshold step)
- Door frame depth: 0.3-0.5m (creates natural shadow portal)
- Light probe placement: one exterior, one in doorway, one interior (minimum 3 for smooth transition)
- Interior ambient: 30-50% of exterior ambient intensity
- Dust particle emitter in doorway light shafts

---

## 3. VEGETATION

### 3.1 Tree LOD Chain (Billboard/Card Based)

| LOD | Screen Size | Geometry | Tri Count | Notes |
|---|---|---|---|---|
| LOD0 | >15% screen | Full 3D mesh | 3,000-10,000 | Bark, individual branches, leaf clusters |
| LOD1 | 8-15% | Simplified mesh | 1,000-4,000 | Merged branch groups, simplified bark |
| LOD2 | 3-8% | Card-based | 100-600 | 6-12 intersecting planes with leaf/branch textures |
| LOD3 | 1-3% | Billboard | 2-8 | Single camera-facing quad or cross (2 quads) |
| Cull | <1% | None | 0 | Completely culled |

**SpeedTree-style card generation (for LOD2):**
- Generate 6-12 intersecting planes through the canopy volume
- Each plane textured with pre-rendered branch/leaf clusters (alpha cutout)
- Planes oriented to maximize coverage from all viewing angles
- Common arrangement: 3 vertical planes at 60-degree intervals + 2-3 angled planes

**Billboard generation (LOD3):**
- Render 8 views of tree (every 45 degrees) into atlas
- Atlas size: 512 x 512 (8 frames at 128 x 256 each) or 1024 x 512 for larger trees
- Octahedral or cross-billboard for better parallax than single quad

### 3.2 Grass Card Systems

**Card geometry:**
- Single grass tuft: 3-6 triangles (1-3 quads, slight V-bend for depth)
- Clump of 3-5 tufts: 12-24 triangles
- Alpha-tested, double-sided rendering

**Density targets:**

| Quality | Tufts/m^2 | Draw Distance | Total Active |
|---|---|---|---|
| Low | 4-8 | 40 m | ~20,000-50,000 |
| Medium | 8-16 | 60 m | ~100,000-200,000 |
| High | 16-32 | 80 m | ~300,000-600,000 |
| Ultra | 32-64 | 100 m | ~1,000,000+ |

**Performance note:** Overdraw is the primary cost. Cut alpha-transparent areas from quads by shaping geometry to match grass silhouette (spend 2-4 extra tris to eliminate 40-60% transparent pixels).

**LOD for grass:**
- 0-20m: Mesh grass with full geometry (6-12 tris/tuft)
- 20-50m: Simplified card grass (2-4 tris/tuft)
- 50-80m: Billboard strips (clusters batched into rows)
- 80m+: Terrain color tint only (no geometry)

### 3.3 Wind Animation Vertex Color Convention

**Industry standard (CryEngine/SpeedTree-derived):**

| Channel | Name | Usage | Paint Rules |
|---|---|---|---|
| **R (Red)** | Leaf flutter / edge wiggle | Controls high-frequency leaf tip oscillation | Full red at leaf edges/tips, black at leaf center and all branches/trunk |
| **G (Green)** | Per-leaf phase variation | Offsets oscillation phase so each leaf moves independently | Unique random value per leaf/leaf cluster (0.0-1.0) |
| **B (Blue)** | Branch sway amplitude | Controls how much each branch bends side-to-side | Gradient: 0 at trunk, increases toward branch tips. Trunk = 0, major branch = 0.3, minor branch = 0.6, leaf = 0.8-1.0 |
| **A (Alpha)** | Trunk sway / AO | Overall trunk sway weight, or baked ambient occlusion | Gradient bottom-to-top for trunk sway: 0 at base, 1 at crown. Or: baked AO for SpeedTree models |

**Shader implementation:**
```
// Simplified wind vertex displacement
float time = _Time.y * wind_speed;
float trunk_sway = sin(time * 0.5 + object_phase) * vertex_color.a * trunk_amplitude;
float branch_sway = sin(time * 1.5 + vertex_color.g * 6.28) * vertex_color.b * branch_amplitude;
float leaf_flutter = sin(time * 4.0 + vertex_color.g * 6.28) * vertex_color.r * flutter_amplitude;
float3 displacement = wind_direction * (trunk_sway + branch_sway) + leaf_flutter_direction * leaf_flutter;
vertex_position += displacement;
```

**Amplitude values:**
- Trunk sway: 0.1-0.5m (calm wind), 0.5-2.0m (storm)
- Branch sway: 0.05-0.3m (calm), 0.3-1.0m (storm)
- Leaf flutter: 0.01-0.05m (calm), 0.05-0.2m (storm)
- Wind speed multiplier: 0.5 (gentle breeze) to 3.0 (storm)

### 3.4 Procedural Branch Generation (L-System Parameters)

**L-System rules for dark fantasy trees:**
```
Axiom: F
Rules:
  F -> F[+F]F[-F]F       (symmetric branching)
  F -> FF-[-F+F+F]+[+F-F-F]  (asymmetric, more natural)

Parameters:
  branch_angle: 20-45 degrees (25-35 most natural)
  branch_length_ratio: 0.6-0.8 (child/parent length)
  branch_radius_ratio: 0.5-0.7 (child/parent radius)
  iterations: 4-7 (4=shrub, 5=small tree, 6=medium tree, 7=large tree)
  twist_per_segment: 0-30 degrees (adds organic feel)
  gravity_influence: 0.02-0.1 (drooping branches)
  randomization: 10-20% variation on angles and lengths
```

**Dark fantasy modifiers:**
- Twisted/gnarled: increase `twist_per_segment` to 30-60, reduce `branch_length_ratio` to 0.5-0.6
- Dead/corrupted: randomly terminate 30-50% of branches early, remove leaves from terminated
- Ancient/massive: trunk radius 0.5-2.0m at base, 6-8 iterations, exposed roots extending 1-3m

### 3.5 Seasonal Variation

**Color parameter sets:**

| Season | Leaf Hue Range (sRGB) | Leaf Saturation | Leaf Coverage | Ground Litter |
|---|---|---|---|---|
| Spring | (100, 180, 60) - (140, 200, 80) | High | 60-80% | Low |
| Summer | (50, 130, 30) - (80, 160, 50) | High | 90-100% | None |
| Autumn | (180, 120, 30) - (220, 80, 20) | Medium | 50-70% | Heavy |
| Winter | (120, 110, 90) - (150, 140, 120) | Low | 0-20% | Decayed |
| Corrupted | (100, 60, 80) - (140, 40, 100) | Low | 30-60% | Ash |

**Implementation:** Vertex color tint multiplied with season parameter. Leaf density controlled by alpha threshold shift.

---

## 4. MATERIALS / PBR

### 4.1 Physically Accurate Material Values

**Reference: physicallybased.info + Google Filament + Marmoset**

#### Metals (metallic = 1.0)

| Material | Albedo (sRGB) | Roughness | F0 (linear) | Notes |
|---|---|---|---|---|
| Iron (raw) | (135, 131, 126) | 0.5-0.8 | 0.560 | Dark fantasy primary metal |
| Iron (polished) | (135, 131, 126) | 0.2-0.4 | 0.560 | Rare, well-maintained |
| Steel | (155, 155, 155) | 0.3-0.6 | 0.560 | Brighter than iron |
| Gold | (255, 217, 145) | 0.1-0.3 | 0.920 | Treasure, boss accents |
| Silver | (252, 250, 245) | 0.1-0.3 | 0.950 | Holy weapons |
| Copper | (250, 190, 158) | 0.2-0.5 | 0.630 | Pipes, decorative |
| Bronze | (250, 230, 150) | 0.3-0.6 | 0.630 | Statues, ancient items |
| Brass | (249, 229, 150) | 0.2-0.5 | 0.590 | Door fittings, trim |
| Rusted Iron | (120, 60, 30) | 0.7-1.0 | metallic->0 | Rust = dielectric |

#### Non-Metals (metallic = 0.0, F0 = 0.04 unless noted)

| Material | Albedo (sRGB) | Roughness | Notes |
|---|---|---|---|
| Granite (light) | (180, 170, 155) | 0.7-0.9 | Castle walls, foundations |
| Granite (dark) | (90, 85, 75) | 0.6-0.85 | Dungeon walls |
| Limestone | (200, 195, 175) | 0.6-0.85 | Church/cathedral |
| Sandstone | (210, 185, 140) | 0.7-0.9 | Desert ruins |
| Marble (polished) | (212, 202, 192) | 0.1-0.3 | Boss rooms, temples |
| Marble (rough) | (212, 202, 192) | 0.5-0.7 | Weathered columns |
| Oak (light) | (190, 160, 115) | 0.6-0.85 | Furniture, beams |
| Oak (dark) | (80, 55, 35) | 0.5-0.8 | Aged/stained wood |
| Pine | (200, 175, 130) | 0.65-0.9 | Structural timber |
| Charred Wood | (30, 25, 20) | 0.8-1.0 | Fire damage |
| Thatch/Straw | (175, 155, 95) | 0.85-1.0 | Roofing |
| Leather (new) | (100, 65, 35) | 0.4-0.65 | Equipment |
| Leather (worn) | (75, 45, 25) | 0.5-0.8 | Aged gear |
| Bone/Ivory | (202, 202, 169) | 0.4-0.7 | Decorative/grim |
| Cloth (linen) | (180, 170, 150) | 0.85-1.0 | Banners, bedding |
| Cloth (wool) | (100, 85, 70) | 0.9-1.0 | Clothing |
| Mud/Earth | (115, 95, 60) | 0.9-1.0 | Ground, walls |
| Wet Mud | (80, 65, 40) | 0.3-0.6 | Roughness drops when wet |
| Concrete/Mortar | (130, 130, 130) | 0.8-1.0 | Between stones |
| Obsidian | (20, 20, 22) | 0.05-0.2 | F0 ~0.08, dark magic |
| Glass | (230, 235, 240) | 0.0-0.1 | F0 = 0.04, IOR 1.52 |

**Critical rules:**
- Non-metal albedo: NEVER below sRGB 30, NEVER above sRGB 240
- Metal albedo: NEVER below sRGB 170
- Roughness: NEVER below 0.04 (clamp minimum 0.089 per Filament spec)
- Rust transitions metallic from 1.0 to 0.0 (rust is dielectric)

### 4.2 Roughness from Geometry (Curvature-Based)

**Bake pipeline in Blender:**
1. High-poly to low-poly bake: position, normal, curvature, AO, thickness
2. Curvature map: bake using Cycles shader `Geometry > Pointiness` or addon
3. Split curvature: convex (>0.5) = edge wear, concave (<0.5) = cavity dirt

**Curvature -> roughness mapping:**
```python
# Convex edges: decrease roughness slightly (exposed, polished by wear)
roughness_edge = base_roughness - curvature_convex * 0.15

# Concave cavities: increase roughness (dirt/grime accumulation)
roughness_cavity = base_roughness + curvature_concave * 0.2

# Final roughness
roughness = lerp(roughness_cavity, roughness_edge, curvature_normalized)
```

### 4.3 Normal Map Baking Workflow

**Source resolution ratio:** High-poly should be 10-100x the poly count of low-poly.

**Bake settings (Blender Cycles):**
- Ray distance: 0.01-0.05m (auto-detect or manual cage)
- Cage extrusion: 0.005-0.02m beyond low-poly surface
- Tangent space: MikkTSpace (matches Unity/Unreal)
- Output: 16-bit PNG or OpenEXR for intermediate, 8-bit BC5 for final
- Resolution: match texture resolution table (512-2048 depending on asset tier)

**Validation checklist:**
- No hard edges crossing UV seams (causes normal map artifacts)
- UV padding: minimum 4px at target resolution (8px at 2048, 4px at 1024)
- Smooth groups match UV island boundaries
- Test with flat color material to spot bake errors

### 4.4 Texture Atlas / Trim Sheet Creation

**Trim sheet layout (2048 x 2048 example for medieval stone building):**
```
Y 0-256:    Stone wall varieties (3 bands: rough, smooth, damaged)
Y 256-384:  Stone trim / molding profiles (2 bands)
Y 384-640:  Wood plank varieties (3 bands: clean, worn, rotten)
Y 640-768:  Wood beam / timber frame profiles
Y 768-896:  Plaster / daub / stucco (2 bands: clean, cracked)
Y 896-1024: Metal (iron bands, nails, hinges, locks)
Y 1024-1280: Roof tiles (clay, slate, thatch)
Y 1280-1408: Ground (cobblestone, dirt, gravel)
Y 1408-1536: Damage (cracks, holes, crumbling edges)
Y 1536-1792: Organic (moss, ivy, lichen, roots)
Y 1792-2048: Detail / unique (signs, symbols, frames)
```

**Texel density:** All bands should have consistent texel density of ~512-1024 px/m.
**Tiling axis:** Bands tile horizontally (U axis). V axis is non-tiling (variety).

### 4.5 Material Layering System

**4-layer stack for procedural weathering:**

| Layer | Source | Blend Mask | Parameters |
|---|---|---|---|
| Base | Trim sheet or tiling | Full coverage | Clean material |
| Wear | Curvature (convex) | Curvature map > threshold 0.6 | Lighter albedo, lower roughness, expose substrate |
| Dirt | Curvature (concave) + AO | AO < 0.7 + noise | Darker albedo (*0.5-0.7), higher roughness (+0.2) |
| Moss/Growth | World normal Y + AO + noise | Y > 0.6 AND AO < 0.8 AND noise > 0.5 | Green tint (60,85,40), roughness 0.8+ |

**Blend method:** Height-based blend using per-layer heightmap (same as terrain splatting).
**Age multiplier (0-1):** Scales wear/dirt/moss coverage globally. At 0 = pristine. At 1 = heavily aged.

---

## 5. TOWN / SETTLEMENT LAYOUT

### 5.1 Road Network Generation

**Two-tier approach:**

**Primary roads (agent-based L-system):**
- Start from town center (market/church/castle)
- Branch at 30-90 degree angles with probability decreasing per depth
- Width: main road 4-6m, secondary 2.5-4m, alley 1.5-2.5m
- Curve roads slightly (add Perlin noise offset of 0.5-2m per 10m segment)
- Roads avoid steep slopes (max 15 degrees for main roads, 25 for alleys)
- Roads naturally follow contour lines on hills

**Secondary roads (connection passes):**
- After primary network: connect dead ends that are within 20-40m of each other
- Create ring roads around market squares
- Add 2-3 cross-connections per block to prevent dead-end neighborhoods

### 5.2 Building Lot Subdivision

**Algorithm: Recursive OBB (Oriented Bounding Box) split:**
1. Define city block as polygon bounded by roads
2. Find longest axis of block OBB
3. Split perpendicular to longest axis at 40-60% point (add 5-15% randomization)
4. Recurse until lot area reaches target: 40-120 m^2 (small house), 80-200 m^2 (medium), 150-400 m^2 (large)
5. Reject lots without road frontage (minimum 3m of road-facing edge)
6. Setback from road: 0-2m (dense medieval), 1-3m (wealthy quarter)

**Building footprint within lot:**
- Coverage: 60-90% of lot area (medieval = dense, 80-90%)
- Remaining space: backyard, garden, or courtyard
- Building faces road; entrance on road-facing facade

### 5.3 Organic vs Grid Layouts

**Organic (medieval village/town):**
- Road angles: random between 15-75 degrees at intersections
- Block shapes: irregular polygons, 4-7 sides
- Road curvature: Perlin noise offset 1-3m per 10m
- Building alignment: follow road tangent, +/-5-10 degree variation
- Growth pattern: radial from center outward, with density decreasing

**Grid (planned settlement/Roman-influenced):**
- Road angles: 90 degrees (with 0-3 degree noise for realism)
- Block shapes: rectangular, 30-60m x 20-40m
- Roads: straight with slight width variation
- Building alignment: perpendicular to road, consistent setback
- Grid broken by: market square, church, fortification, river

**Hybrid (most realistic):**
- Core: organic (oldest part of town)
- Extensions: semi-grid (later planned growth)
- Outside walls: organic farmstead scatter

### 5.4 Special Spaces

**Market square:**
- Area: 400-2500 m^2 (20x20m to 50x50m)
- Shape: roughly rectangular or triangular
- Located at intersection of 2-3 major roads
- Central feature: well, fountain, or market cross
- Surrounded by: taverns, shops, guildhalls (commercial buildings)
- Stall placement: 3m x 2m per stall, 1m spacing, along square edges

**Gathering spaces:**
- Church/temple yard: 200-800 m^2, adjacent to main religious building
- Execution/punishment square: 100-400 m^2, central gallows/stocks
- Training yard: 300-1000 m^2, near barracks

### 5.5 Defensive Wall Placement

**Wall dimensions:**
- Height: 6-10m (small town), 10-15m (major city)
- Thickness: 2-3m (allows wall walk on top)
- Wall walk width: 1.5-2.5m with crenellations (0.5m merlons, 0.4m gaps)

**Tower spacing:** 25-50m apart (effective arrow range, allow flanking fire along curtain wall)
**Tower diameter:** 4-8m, protruding 1-3m beyond wall face
**Gate placement:** At major road intersections with wall circuit. 1-3 gates for small towns, 4-8 for cities.

**Wall path algorithm:**
1. Compute convex hull of settlement with 20-50m buffer
2. Snap wall path to terrain contours (prefer ridgelines)
3. Place towers at corners and every 30-40m along straight sections
4. Place gatehouse where major roads intersect wall path
5. Add postern (small secondary gate) on opposite side from main gate

### 5.6 District Zoning

**Typical medieval town districts:**

| District | Location | Building Types | Density | Lot Size |
|---|---|---|---|---|
| Market/Commercial | Town center | Shops, tavern, guildhall | Very high | 40-80 m^2 |
| Residential (wealthy) | Near center/castle | Manor houses, gardens | Medium | 150-400 m^2 |
| Residential (common) | Between center and walls | Row houses, workshops | High | 40-120 m^2 |
| Religious | Near center | Church, monastery, graveyard | Low | 200-1000 m^2 |
| Military | Near walls/gates | Barracks, armory, stables | Medium | 100-300 m^2 |
| Industrial | Downwind/downstream | Tannery, smithy, dye works | Medium | 80-200 m^2 |
| Slums | Near walls, worst land | Hovels, lean-tos | Very high | 20-60 m^2 |
| Farmstead | Outside walls | Farmhouses, barns, fields | Very low | 500-2000 m^2 |

---

## 6. CASTLE / FORTIFICATION

### 6.1 Concentric Wall Design

**Layout principle:** 2-3 rings of walls, each inner ring higher than the outer.

```
Ring 1 (outer):  Height 6-8m,  Thickness 2m,   Tower spacing 30-40m
Ring 2 (middle): Height 10-12m, Thickness 2.5m,  Tower spacing 25-35m
Ring 3 (inner):  Height 12-16m, Thickness 3m,    Tower spacing 20-30m

Inter-wall gap (bailey): 8-15m wide (killing ground)
```

**Height differential:** Each inner wall 2-4m taller than outer, allowing archers on inner wall to fire over outer wall.

### 6.2 Gatehouse Architecture

**Standard gatehouse components:**

| Element | Dimensions | Geometry Notes |
|---|---|---|
| Passage | 3-4m wide, 3.5-4.5m tall, 8-15m deep | Barrel vault or pointed arch |
| Portcullis (front) | 3m x 3.5m iron grid | Vertical bars 0.05m dia, 0.15m spacing |
| Portcullis (rear) | Same as front | Twin portcullis creates kill zone |
| Murder holes | 0.3-0.5m openings in ceiling | 3-5 holes in passage ceiling |
| Arrow slits | 0.1m wide x 1.2m tall, splayed interior | Flanking the passage, 2-3 per side |
| Machicolation | 0.5m overhang above gate | Floor openings for dropping stones/oil |
| Twin towers | 5-8m diameter, flanking gate | Circular or D-shaped, 15-20m tall |
| Drawbridge | 3-4m wide, 4-6m long | Pivots at wall face, chain-raised |

**Barbican (advanced gatehouse):**
- Extended fortified corridor 10-30m beyond main gate
- Narrowing passage (4m entry to 3m at gate)
- Own gate and portcullis at outer end
- Open-topped section between barbican and main gate (killing ground)
- Walls 6-10m high with arrow loops

### 6.3 Tower Types and Placement

| Tower Type | Diameter | Height | Placement | Tri Budget (LOD0) |
|---|---|---|---|---|
| Corner/Flanking | 4-6m | Wall height + 4-8m | Wall corners, every 30-40m | 1,000-3,000 |
| Gatehouse Tower | 6-8m | Wall height + 6-10m | Flanking gates (paired) | 2,000-5,000 |
| Keep/Donjon | 10-20m | 20-35m | Center of inner bailey | 5,000-15,000 |
| Watch Tower | 3-4m | 12-20m | Outer wall, high ground | 800-2,000 |
| Turret | 2-3m | Wall height + 2-4m | Secondary walls, decorative | 400-1,000 |

**Tower shapes:**
- Round: strongest, deflects projectiles, 12-24 sided polygon in Blender (16 common)
- D-shaped: flat interior face against wall, round exterior
- Square: easiest to build, but vulnerable corners (add buttresses)
- Polygonal (6-8 sides): compromise between round and square

### 6.4 Curtain Wall Construction

**Wall segment dimensions:**
- Length between towers: 25-50m
- Height: 6-16m depending on ring
- Thickness: 2-3m at base, 1.5-2.5m at top (slight taper)
- Batter (base splay): 10-15 degree outward angle on bottom 1-2m

**Wall-top features:**
- Crenellations: merlons 0.5m wide x 1.0m tall, 0.4m gaps (embrasures)
- Wall walk: 1.5-2.5m wide, stone or wood deck
- Hoarding (temporary timber gallery): extends 1-1.5m beyond wall face, 2m tall

**Modular wall kit (minimum pieces):**
```
wall_curtain_straight_4m    (base segment)
wall_curtain_straight_8m    (double segment)
wall_curtain_corner_90      (inner/outer variants)
wall_curtain_corner_45      (angle variants)
wall_curtain_gate_section   (with portcullis slot)
wall_curtain_damaged_1      (breach variant)
wall_curtain_damaged_2      (crumbled section)
wall_battlement_straight_4m (crenellation top)
wall_battlement_corner      (merlon at corner)
wall_walk_section_4m        (walkway floor)
wall_stair_section          (access from ground to wall walk)
wall_tower_base             (cylindrical base where tower meets wall)
```

### 6.5 Keep/Donjon Design

**Dimensions:**
- Footprint: 15-25m x 15-25m (rectangular or 12-16m diameter circular)
- Height: 20-35m (3-5 stories)
- Wall thickness: 3-5m at base (very thick)
- Stories: Great Hall (1st/2nd), Private Chambers (3rd), Storage/Kitchen (ground), Roof/Battlements (top)

**Per-floor layout:**
```
Ground Floor:    Storage, kitchen, well access. No windows. Single door.
                 Area: 100-400 m^2, ceiling height 3-4m
First Floor:     Great Hall. Fireplace, high windows, main staircase.
                 Area: 100-400 m^2, ceiling height 4-6m
Second Floor:    Lord's chambers, solar (private room). Garderobe (toilet).
                 Area: same footprint, ceiling height 3-4m
Third Floor:     Additional chambers, chapel (sometimes).
                 Ceiling height 3m
Roof:            Battlements, flag poles. Open or partially covered.
```

### 6.6 Spiral Staircase Geometry

**Parameters for Blender generation:**
- Outer radius: 1.2-2.0m (fits within tower wall)
- Inner radius (central pillar): 0.15-0.3m
- Step height: 0.18-0.22m
- Step depth (at inner): 0.08-0.12m
- Step depth (at outer): 0.25-0.35m
- Steps per 360-degree turn: 12-20 (18 common = 20 degrees per step)
- Rotation direction: clockwise ascending (historically, to disadvantage right-handed attackers coming up)
- Total height per story: 3-4m = 14-22 steps per flight
- Headroom: minimum 1.9m clearance
- Triangle count: 200-600 per full revolution (depends on step count)

---

## 7. WATER

### 7.1 River Mesh Generation

**Spline-based approach:**
1. Define river path as Bezier/NURBS curve following terrain valleys
2. Width: 2-8m (stream), 8-30m (river), 30-100m+ (major river)
3. Generate flat mesh along spline with cross-section subdivisions (8-16 across width)
4. Vertex Y position: slightly below terrain surface (0.05-0.2m)
5. UV mapping: U = across width (0-1), V = along flow (tiling at 1m intervals)

**Flow data encoding (vertex color or UV2):**
- R: Flow speed (0=still, 1=rapid). Computed from slope: `speed = clamp(slope * 10, 0.1, 1.0)`
- G: Flow direction X component (encoded 0-1 from -1 to +1)
- B: Flow direction Z component (encoded 0-1 from -1 to +1)
- A: Foam amount (higher at banks, rapids, obstacles)

**Mesh density:**
- River center: 1 quad per 1-2m along flow
- Near banks: subdivide to 0.25-0.5m (for shore deformation)
- Total: ~100-500 tris per 10m river section

### 7.2 Shore Blending

**Depth-based transparency:**
- Sample terrain heightmap at water surface UV
- Depth = water_surface_height - terrain_height
- Alpha: 0 at depth 0 (shore), 1.0 at depth > 1-2m
- Color shift: shallow = lighter, saturated; deep = darker, desaturated
- Shore foam: white band where depth < 0.1-0.3m, animated scrolling texture

**Shore geometry:**
- Smooth terrain mesh vertices near water edge to flatten slope
- Add shore debris meshes (rocks, driftwood, reeds) within 1-3m of waterline
- Scatter density: 1-3 objects per meter of shoreline

**Vertex displacement at shore:**
- Gentle wave-like vertex displacement on water mesh near shore
- Amplitude: 0.02-0.05m
- Frequency: match water surface wave frequency

### 7.3 Waterfall Geometry

**Construction method:**
1. Detect steep drops in river path (height change > 1m over < 2m horizontal)
2. Generate vertical/near-vertical mesh sheet at drop point
3. Width: match river width or slightly narrower (80-100% of upstream width)
4. Mesh subdivisions: 8-16 across, 4-8 per meter of drop height

**Texture and animation:**
- UV scrolling: V axis scrolling at 1-3 m/s (match water speed)
- Distortion noise: animated Perlin offset on UVs for turbulent look
- Alpha: full at center, fading at edges

**Splash zone at base:**
- Circular foam area: radius = drop_height * 0.3-0.5
- Mist particle emitter: cone shape, upward, radius matching splash zone
- Particle count: 50-200 (LOD dependent)
- Splash particles: 20-100, radial burst pattern
- Rocks/boulders scattered at waterfall base (4-8 pieces)

### 7.4 Ocean/Lake Surface

**Mesh approach (for Blender pre-generation):**
- Use Blender's Ocean Modifier: resolution 64-256, spatial size matching scene
- Gerstner waves for runtime: 3-6 wave components with varying frequency/amplitude/direction
- Typical wave parameters:
  - Calm: amplitude 0.1-0.3m, wavelength 5-15m
  - Moderate: amplitude 0.3-1.0m, wavelength 10-30m
  - Stormy: amplitude 1.0-3.0m, wavelength 20-60m

**LOD for water surface:**
- Near camera (0-100m): full subdivision, 1-2m grid
- Mid range (100-500m): 4-8m grid
- Far range (500m+): 16-32m grid or flat plane with normal map only

### 7.5 Foam/Spray Placement

**Foam generation rules:**
- Shore contact: foam where water depth < 0.2m (scrolling foam texture, opacity = 1 - depth/0.2)
- Object contact: foam ring around objects intersecting water (rocks, pilings)
  - Ring width: 0.2-0.5m, opacity based on object size
- Rapids: foam where flow speed > 0.7 (encoded in vertex color R)
- Waterfall base: circular foam patch, radius = drop_height * 0.4

**Spray particles:**
- Waterfall spray: 50-200 particles, upward cone, lifetime 1-3s
- Wave crash: 20-50 particles per impact, radial burst
- Particle size: 0.05-0.3m
- Particle texture: 64x64 or 128x128 soft circle with noise

---

## 8. PERFORMANCE / EXPORT

### 8.1 LOD Chain Generation

**Standard LOD reduction ratios:**

| LOD Level | Tri % of LOD0 | Screen Size Threshold | Transition |
|---|---|---|---|
| LOD0 | 100% | >25% screen | Full detail |
| LOD1 | 40-50% | >12% screen | Simplified detail |
| LOD2 | 15-25% | >5% screen | Silhouette only |
| LOD3 | 5-10% | >1% screen | Block shape |
| Cull | 0% | <1% screen | Not rendered |

**Blender LOD generation pipeline:**
1. LOD0: Source mesh (hand-modeled or generated)
2. LOD1: Decimate modifier, ratio 0.4-0.5, preserve UV boundaries
3. LOD2: Decimate modifier, ratio 0.15-0.25, collapse small features
4. LOD3: Manual or aggressive decimate, ratio 0.05-0.1, bake normal map from LOD0 onto LOD3
5. Export each LOD as separate mesh, same UV layout, same material

**LOD transition distances (for 1920x1080 viewport):**
- LOD0->1: 15-30m (small prop), 30-60m (medium), 50-100m (large building)
- LOD1->2: 30-60m, 60-120m, 100-200m
- LOD2->3: 60-120m, 120-240m, 200-400m
- Cull: 100-200m, 200-400m, 400-800m

### 8.2 Texture Budget Per Asset Type

| Asset Type | Albedo | Normal | ORM | Total (BC7) | Notes |
|---|---|---|---|---|---|
| Hero character | 2048 | 2048 | 2048 | ~16 MB | Top priority |
| Major NPC/Boss | 2048 | 2048 | 1024 | ~12 MB | |
| Common enemy | 1024 | 1024 | 1024 | ~4 MB | |
| Weapon (hero) | 1024 | 1024 | 1024 | ~4 MB | |
| Weapon (common) | 512 | 512 | 512 | ~1 MB | |
| Building (shared trim) | 2048 | 2048 | 1024 | ~12 MB | Shared across all modules |
| Large prop | 1024 | 1024 | 512 | ~3 MB | |
| Medium prop | 512 | 512 | 512 | ~1 MB | |
| Small prop | 256 | 256 | 256 | ~0.25 MB | |
| Terrain layer (tiling) | 1024 | 1024 | 512 | ~3 MB | x8-16 layers |
| Tree atlas | 1024 | 1024 | 512 | ~3 MB | Shared per tree species |
| Grass atlas | 512 | 512 | - | ~0.5 MB | Alpha cutout |

**Total VRAM texture budget target:** 1.5-2.5 GB for mid-range PC at any given time.
**Compression:** BC7 for albedo+ORM, BC5 for normal maps, BC4 for single-channel (height, AO).
**Always enable mipmaps and texture streaming.**

### 8.3 Draw Call Optimization

**Target budgets:**

| Platform | Draw Calls/Frame | SetPass Calls | Total Tris/Frame |
|---|---|---|---|
| High-end PC (60fps) | 3,000-5,000 | 500-1,000 | 5-10M |
| Mid-range PC (60fps) | 1,500-3,000 | 300-600 | 2-5M |
| Console (60fps) | 2,000-4,000 | 400-800 | 3-8M |

**Reduction strategies (priority order):**
1. **SRP Batcher:** All unique objects, same shader variant batch together (70-90% CPU overhead reduction)
2. **GPU Instancing:** All repeated meshes (vegetation, rocks, modular env pieces) - same mesh + material = 1 draw call
3. **Static Batching:** Small static props sharing materials (max 64K verts per batch)
4. **Texture Atlasing:** Combine textures to reduce material count (trim sheets = 1 material per building style)
5. **LOD System:** Fewer tris at distance reduces vertex shader cost
6. **Occlusion Culling:** Static + dynamic culling for complex scenes

### 8.4 Instancing Strategies

**GPU Instancing rules:**
- Same mesh + same material = instanced (single draw call for all instances)
- Per-instance data via shader buffer: position, rotation, scale, color tint (16-32 bytes/instance)
- Maximum instances per draw: 500-1,023 (engine/platform dependent)
- Best candidates: grass, rocks, debris, fences, crates, barrels, candles

**Indirect instancing (advanced):**
- GPU-driven rendering: compute shader fills draw buffer
- Frustum + occlusion culling on GPU
- Supports millions of instances (vegetation, debris)
- Unity: use `Graphics.DrawMeshInstancedIndirect()`

**Modular building instancing:**
- Identical wall sections, floor tiles, roof segments -> instance
- Typical medieval town: 200-500 unique module meshes, 5,000-20,000 instances
- Without instancing: 5,000-20,000 draw calls. With instancing: 200-500 draw calls.

### 8.5 Lightmap UV Generation

**UV2 requirements for lightmaps:**
- Non-overlapping UV islands (every face has unique UV space)
- No UV islands crossing 0-1 boundary
- Padding between islands: 2-4 texels at target lightmap resolution
- Chart area proportional to world-space area (uniform texel density)

**Lightmap resolution targets:**

| Asset Type | Texels/Meter | Lightmap Size | Notes |
|---|---|---|---|
| Building exterior | 10-20 | 256-512 per building | Shared UV2 across modules |
| Building interior | 20-40 | 256-1024 per room | Higher quality for player-visible |
| Large prop | 10-15 | 64-128 | |
| Small prop | 5-10 | 32-64 | |
| Terrain | 2-5 | 512-1024 per chunk | Lower priority with real-time lighting |
| Ground plane | 5-10 | 256-512 | |

**Blender UV2 generation:**
- Smart UV Project with angle limit 66-80 degrees
- Or: Lightmap Pack (built-in, optimized for non-overlapping)
- Margin: 0.005-0.02 (depending on target lightmap resolution)
- Export as second UV channel in FBX

### 8.6 Export Checklist (Blender -> Unity)

**Pre-export validation (run `blender_mesh` action=game_check):**
- [ ] No n-gons (all faces are tris or quads, export as tris)
- [ ] No zero-area faces
- [ ] No loose vertices
- [ ] Normals consistent (no flipped faces)
- [ ] UV0 present and valid (no overlapping for unique assets)
- [ ] UV1 present for lightmapped assets (non-overlapping)
- [ ] Scale applied (Ctrl+A in Blender)
- [ ] Rotation applied
- [ ] Origin at correct pivot point
- [ ] LODs named correctly: `MeshName_LOD0`, `MeshName_LOD1`, etc.
- [ ] Materials assigned and named
- [ ] Vertex colors present if needed (wind, AO, blend)

**FBX export settings:**
- Scale: 1.0 (units = meters)
- Forward: -Z Forward (Unity convention)
- Up: Y Up
- Apply transforms: enabled
- Mesh: triangulate, include normals, include UVs, include vertex colors
- Armature: if rigged
- Animation: if animated (separate FBX per animation clip is common)

---

## APPENDIX: QUICK REFERENCE NUMBERS

### Scene Budget Example (Dark Fantasy Town)

```
Total triangle budget: 4,000,000 (60fps, mid-range PC)

Terrain:           200,000-400,000 tris (5-10%)
Buildings (x20):   60,000-300,000 tris (modular instanced, 1.5-7.5%)
Walls/Fortification: 100,000-200,000 tris (2.5-5%)
Vegetation (trees x50): 150,000-500,000 tris (LOD-dependent, 3.75-12.5%)
Vegetation (grass): 200,000-600,000 tris (5-15%)
Props (x200):      200,000-400,000 tris (5-10%)
Water:             10,000-50,000 tris (0.25-1.25%)
Characters (x15):  150,000-450,000 tris (3.75-11.25%)
VFX/Particles:     100,000-300,000 tris (2.5-7.5%)
UI:                10,000-50,000 tris (<1%)

Draw calls target: 1,500-2,500
Texture memory: 1.5-2.0 GB
```

### Distance Reference

```
Player interaction range:    0-3m
Melee combat range:          0-5m
Close detail visible:        0-15m (full LOD0, mesh grass)
Medium detail:               15-50m (LOD1, card grass)
Far detail:                  50-200m (LOD2, billboard trees)
Horizon/skybox transition:   200-1000m (LOD3, minimal geo)
Cull distance (small):       100-200m
Cull distance (large):       400-800m
Terrain render distance:     1000-4000m
```
