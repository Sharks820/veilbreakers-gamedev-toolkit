# AAA Environmental Texturing Pipeline Research

**Researched:** 2026-03-22
**Domain:** Terrain texturing, building/architecture materials, vegetation, props, dark fantasy color science, weathering systems, decal systems
**Confidence:** HIGH (cross-referenced AAA titles, official Unity/Blender docs, community tutorials, and industry GDC-level techniques)
**Target Stack:** Blender procedural (bpy shader nodes) + Unity URP

---

## Table of Contents

1. [Terrain Texturing](#1-terrain-texturing)
2. [Building/Architecture Texturing](#2-buildingarchitecture-texturing)
3. [Vegetation Texturing](#3-vegetation-texturing)
4. [Prop Texturing](#4-prop-texturing)
5. [Dark Fantasy Color Science](#5-dark-fantasy-color-science)
6. [Weathering and Aging Systems](#6-weathering-and-aging-systems)
7. [Decal Systems](#7-decal-systems)
8. [Blender Node Recipes](#8-blender-node-recipes)
9. [Anti-Tiling Techniques](#9-anti-tiling-techniques)
10. [Unity URP Integration](#10-unity-urp-integration)

---

## 1. Terrain Texturing

### 1.1 Splatmap Blending (Industry Standard)

**What it is:** A control texture (splatmap) where each RGBA channel represents the opacity/weight of a terrain layer. Unity terrain natively supports 4 layers per splatmap (R, G, B, A), with additional splatmaps for 8+ layers.

**4-Channel Standard Setup:**
| Channel | Material | Slope Range | Height Range |
|---------|----------|-------------|--------------|
| R | Grass/ground cover | 0-25 degrees | Valley floor to mid-height |
| G | Dirt/mud | 15-40 degrees transition | Low areas, paths |
| B | Rock/cliff | 30-90 degrees | Mid to peak |
| A | Snow/moss/sand (biome-specific) | 0-15 degrees (snow accumulation) | Peak height (snow) or valley (sand) |

**8-Channel Extended Setup (2 splatmaps):**
Second splatmap adds: gravel, wet mud, dead grass, road surface.

**Height-Based Blending Algorithm (critical for realism):**
Instead of simple linear interpolation between layers, multiply each layer's weight by a per-pixel height value from the material's heightmap. This makes transitions follow surface detail (e.g., grass fills cracks between rocks instead of a smooth gradient).

```
// Pseudocode: height-based blend
for each pixel:
    height_adjusted[i] = splatmap_weight[i] * heightmap_value[i]
    max_height = max(height_adjusted)
    threshold = max_height - blend_depth
    for each layer:
        if height_adjusted[i] > threshold:
            final_weight[i] = height_adjusted[i] - threshold
        else:
            final_weight[i] = 0
    normalize(final_weights)
```

**Confidence:** HIGH -- verified from Unity URP TerrainLit shader docs and InnoGames terrain shader breakdown.

### 1.2 Slope-Based Material Assignment

**Thresholds for automatic splatmap painting:**

| Slope (degrees) | Material | Blending |
|-----------------|----------|----------|
| 0-15 | Ground cover (grass/dirt) | Full weight |
| 15-35 | Transition zone | Linear blend grass-to-rock |
| 35-70 | Rock/cliff face | Full weight |
| 70-90 | Overhang/cave ceiling | Dark rock variant |

**Implementation in Blender (for baking splatmaps):**
```python
# Blender Python: compute slope from face normals
import bpy, bmesh, math
from mathutils import Vector

obj = bpy.context.active_object
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.faces.ensure_lookup_table()

UP = Vector((0, 0, 1))
for face in bm.faces:
    slope_rad = face.normal.angle(UP)
    slope_deg = math.degrees(slope_rad)
    # slope_deg: 0 = flat, 90 = vertical cliff
```

### 1.3 Macro Variation Maps

**Problem:** Even with good tiling textures, terrain looks uniform at large scale. Every 50m patch of grass is identical.

**Solution:** A low-resolution (256x256 to 512x512) macro variation map covering the entire terrain that modulates:
- **Color tint** (subtle hue shifts: some grass patches yellower, some greener)
- **Roughness offset** (some areas slightly shinier from moisture)
- **Brightness** (large-scale shadows and exposure variation)

**Implementation:**
1. Generate procedural macro map in Blender (low-frequency Noise Texture, scale 0.01-0.05)
2. Export as grayscale image
3. In Unity, sample this map at world-space UV coordinates and multiply with terrain albedo

**Macro map generation recipe (Blender nodes):**
```
Texture Coordinate (Object) -> Mapping (Scale: 0.02, 0.02, 0.02)
  -> Noise Texture (Scale: 2.0, Detail: 4, Roughness: 0.5)
  -> ColorRamp (3 stops: 0.85 at 0.0, 1.0 at 0.5, 0.9 at 1.0)
  -> multiply with base terrain color
```

### 1.4 Detail Textures (Close-Up Micro-Normal)

When the camera is close to the ground, the base tiling texture becomes visibly low-resolution. Detail textures solve this:

- Tile a high-frequency normal map at 4x-8x the base tiling rate
- Blend it with the base normal map using distance-based weight (full strength close, fade out at distance)
- Same approach for roughness detail

**Unity URP implementation:** The Terrain Lit shader supports a secondary detail layer per terrain layer with independent tiling.

### 1.5 Wet Terrain / Rain Effects

**The physics of wet surfaces (verified from Sebastien Lagarde's research):**

| Property | Dry Value | Wet Value | Formula |
|----------|-----------|-----------|---------|
| Albedo | Original | Darkened to 30% | `diffuse *= lerp(1.0, 0.3, wetLevel)` |
| Roughness | Original | Reduced (shinier) | `roughness *= lerp(1.0, 0.4, wetLevel)` |
| Specular F0 | Material default | 0.02 (water IOR 1.33) | For puddle surfaces |
| Normal | Surface normal | Flat (0,0,1) | For standing water/puddles |

**Puddle accumulation technique:**
1. Use vertex color alpha (or a mask texture) to define puddle-prone areas (concavities, flat surfaces)
2. Use heightmap inversion -- water fills cracks first
3. `saturate((floodLevel - heightMap) / 0.4)` creates smooth wet-to-puddle transition
4. Puddle areas get flat normals and high specular

### 1.6 Road/Path Integration

**Avoid hard-cut edges between roads and terrain.** Use:
1. **Gradient falloff splatmap** -- road material fades 1-2m into surrounding terrain
2. **Edge scattering** -- small pebbles/debris scattered along road edges
3. **Depression mesh** -- slight downward displacement along road center (water flows off)
4. **Vertex color blending** at road-terrain boundary for organic transitions

---

## 2. Building/Architecture Texturing

### 2.1 Trim Sheet Workflow

**What it is:** A single texture atlas containing multiple architectural detail strips (moldings, brick patterns, stone courses, window frames) that tile along one axis (typically U). Buildings are UV-mapped so that geometry stretches across the appropriate strip.

**Why it matters:** A single 2048x2048 trim sheet can texture an entire building style. Without trim sheets, each building face needs unique texturing = massive memory waste.

**Complete Workflow:**

**Step 1: Plan the trim sheet layout**
```
+--------------------------------------------+
| Crown molding (64px high, tiles on U)      |  Strip 0
+--------------------------------------------+
| Stone course - large blocks (128px)         |  Strip 1
+--------------------------------------------+
| Stone course - small blocks (128px)         |  Strip 2
+--------------------------------------------+
| Brick pattern (256px)                       |  Strip 3
+--------------------------------------------+
| Wooden planks (128px)                       |  Strip 4
+--------------------------------------------+
| Window frame / door frame (256px)           |  Strip 5
+--------------------------------------------+
| Foundation stone (128px)                    |  Strip 6
+--------------------------------------------+
| Roof tiles (256px)                          |  Strip 7
+--------------------------------------------+
```
Total: 1344px of 2048 used, remaining space for non-tiling elements (unique details).

**Step 2: Model high-poly trim elements**
- Each strip has a high-poly sculpted version above a flat plane
- Sculpt wear, chipping, mortar erosion, moss growth into high-poly
- Bake normal map, AO, height, curvature from high-poly to flat strip

**Step 3: UV map buildings to trim sheet**
- Mark seams creating long rectangular UV shells
- Straighten UV shells to align with trim strips
- UVs CAN overlap and extend beyond 0-1 space (the sheet tiles on U)
- Map wall faces to stone strip, roof faces to tile strip, etc.

**Step 4: Create full PBR set**
- Albedo: hand-paint or procedural (per strip)
- Normal: baked from high-poly
- Roughness: high variation within each strip (worn edges vs. fresh faces)
- Metallic: 0 for stone/wood, masked regions for metal fixtures
- AO: baked from high-poly

**Trim sheet resolution standard:**
| Building Importance | Trim Sheet Size | Per-Texel Quality |
|--------------------|-----------------|-------------------|
| Hero building (castle keep, cathedral) | 4096x4096 | Maximum detail |
| Standard building (houses, shops) | 2048x2048 | Good balance |
| Background/distance building | 1024x1024 | Memory efficient |

### 2.2 Tiling Texture Techniques for Walls, Roofs, Floors

**Stone wall tiling:**
- Base: 1024x1024 tiling stone texture at 1x scale
- Detail: 512x512 micro-surface normal at 4x scale (stone grain)
- Variation: vertex color or decal overlay for moss, damage, weathering

**Roof tiles:**
- Use overlapping row pattern (not flat grid)
- Each tile needs slight randomized color/roughness variation
- Edge tiles show broken/chipped geometry via normal map

**Floor planks:**
- Grain direction must follow plank length
- Board-to-board gaps via normal map (not geometry)
- Variation: some planks darker, some worn smooth, knot holes

### 2.3 Breaking Tiling Repetition

**5 techniques, ordered by impact:**

1. **Stochastic tiling** (shader-level): Randomly offset and mirror texture per tile. Requires 3 texture samples. See Section 9 for details.

2. **Object Info Random node** (Blender): Each object instance gets a random value for hue/brightness variation.
```python
# Blender node setup for per-object variation
# Object Info (Random output) -> ColorRamp -> Mix RGB (multiply with base color)
# This gives each building instance slightly different coloring
```

3. **Decal overlays**: Unique damage, stains, graffiti projected onto tiling base.

4. **Vertex color driven blending**: Paint dirt/moss/damage gradients onto building meshes via vertex colors. R = dirt amount, G = moss amount, B = damage/wear.

5. **Multi-scale blending**: Blend base texture with large-scale macro variation (same technique as terrain macro maps).

### 2.4 Material Transitions

**Where materials meet (stone-to-wood, wall-to-floor), avoid hard lines:**
- Blend zone of 5-15cm at boundary
- Use heightmap-based blend (same algorithm as terrain height blend)
- Mortar/grout fills the gap with its own roughness (rougher than both materials)

### 2.5 Gothic/Medieval/Fortress Material Palettes

**Stone Variants (VeilBreakers specific):**
| Name | Hex | RGB (Linear) | Roughness | Notes |
|------|-----|-------------|-----------|-------|
| Carved Granite | #3D3833 | (0.054, 0.046, 0.038) | 0.75-0.85 | Fortress walls, carved detail |
| Rough Limestone | #5C5347 | (0.098, 0.083, 0.063) | 0.80-0.95 | Dungeon walls, cave-cut |
| Mossy Flagstone | #4A4E3D | (0.067, 0.072, 0.048) | 0.70-0.90 | Exterior floor, green tint |
| Dark Basalt | #2A2520 | (0.028, 0.024, 0.018) | 0.85-0.95 | Boss areas, ancient ruins |
| Crumbling Sandstone | #7A6B55 | (0.155, 0.127, 0.093) | 0.70-0.85 | Desert/warm biome variant |

**Wood Variants:**
| Name | Hex | RGB (Linear) | Roughness | Notes |
|------|-----|-------------|-----------|-------|
| Aged Oak | #4A3825 | (0.067, 0.049, 0.025) | 0.65-0.80 | Furniture, beams |
| Charred Timber | #2A1F18 | (0.028, 0.018, 0.012) | 0.80-0.95 | Fire damage areas |
| Rotting Plank | #3B3025 | (0.046, 0.035, 0.025) | 0.75-0.90 | Abandoned buildings |
| Polished Mahogany | #5A3D28 | (0.093, 0.049, 0.029) | 0.30-0.50 | Noble furniture, thrones |
| Birch (pale) | #8A7D68 | (0.197, 0.168, 0.123) | 0.55-0.70 | Light accent wood |

**Metal Variants:**
| Name | Hex | RGB (Linear) | Roughness | Metallic | Notes |
|------|-----|-------------|-----------|----------|-------|
| Rusted Iron | #5A4030 | (0.093, 0.052, 0.035) | 0.55-0.75 | 0.70-0.90 | Dominant VB metal |
| Blackened Steel | #252320 | (0.025, 0.023, 0.018) | 0.30-0.50 | 0.85-0.95 | Weapons, armor |
| Tarnished Bronze | #6A5530 | (0.127, 0.093, 0.035) | 0.40-0.60 | 0.80-0.90 | Decorative fixtures |
| Raw Iron | #484440 | (0.063, 0.057, 0.052) | 0.45-0.65 | 0.85-0.95 | Fresh-forged items |

---

## 3. Vegetation Texturing

### 3.1 Tree Bark

**Texture approach:**
- Vertical stretch UV mapping (bark grain runs up-down)
- Base bark texture tiles vertically, unique horizontally per trunk section
- Normal map carries most of the detail (deep crevices, ridges)
- Roughness: crevices are rougher (0.8-0.95), ridges are smoother (0.5-0.7)
- Moss overlay driven by height + world-space Y normal (top-facing surfaces accumulate moss)

**Dark fantasy bark palette:**
| Tree Type | Base Hex | Crevice Hex | Roughness Range |
|-----------|----------|-------------|-----------------|
| Dead Oak | #3A3028 | #1A1510 | 0.65-0.90 |
| Corrupted Birch | #5A5048 | #2A2520 | 0.55-0.80 |
| Ancient Pine | #2A2520 | #151210 | 0.70-0.95 |
| Twisted Willow | #3D3530 | #201A15 | 0.60-0.85 |

### 3.2 Leaf Texturing (Alpha Cards)

**Standard technique:** Flat planes with alpha-tested leaf textures. Each card contains 3-8 leaves arranged for visual density.

**Key properties:**
- **Alpha cutoff:** 0.5 for standard, 0.3 for soft edges (alpha-to-coverage)
- **Translucency/SSS:** Leaves transmit light. Use a translucency map (brighter = more light passes through). In Unity URP, use a two-sided foliage shader with subsurface scattering.
- **Color variation:** 3-4 leaf color variants per tree species. Mix randomly per card.
- **Seasonal corruption:** For VeilBreakers, corrupt leaves shift from green to purple-brown with desaturation.

**Leaf color palette (dark fantasy):**
| Season/State | Base Hex | Variation Range | Notes |
|-------------|----------|-----------------|-------|
| Living (dark green) | #2A4020 | H:95-130 S:30-50 V:15-30 | Muted, never vibrant |
| Dying (autumn) | #5A4025 | H:25-40 S:35-55 V:15-35 | Brown-gold |
| Dead | #3A3028 | H:20-35 S:10-25 V:12-25 | Desaturated brown |
| Corrupted | #3A2540 | H:270-290 S:25-45 V:15-30 | Purple-void tint |

### 3.3 Grass Billboard Texturing

- Each grass blade: alpha card with 1-3 blades per card
- Color matches terrain ground cover (never bright green on brown dirt)
- Base of blade darker (shadow), tip lighter (sun exposure)
- Wind preparation: vertex color R channel stores wind sway weight (0 at base, 1 at tip)
- Alpha test mode for performance (not alpha blend)

### 3.4 Mushroom/Flower Texturing

| Element | Technique | Notes |
|---------|-----------|-------|
| Mushroom cap | Subsurface scattering (translucent glow when backlit) | SSS color matches cap color at 50% saturation |
| Mushroom stem | Standard PBR, higher roughness than cap | Roughness 0.7-0.9 |
| Flower petals | Alpha card with translucency map | Petal edges slightly transparent |
| Bioluminescent fungi | Emissive map + bloom | Key VeilBreakers atmosphere element |

---

## 4. Prop Texturing

### 4.1 Wood Props (Furniture, Barrels, Crates)

**Critical rule:** Grain direction must follow the physical construction of the object.
- Barrel staves: vertical grain
- Barrel lid: radial grain (end grain visible)
- Table top: grain runs lengthwise
- Chair legs: vertical grain
- Crate sides: horizontal planks with vertical grain per plank

**Blender implementation:** UV-map each plank face separately, rotate UVs so the wood grain texture aligns with the plank's physical orientation.

**Roughness mapping for wood:**
| Zone | Roughness | Reason |
|------|-----------|--------|
| End grain (cut faces) | 0.80-0.95 | Raw, absorbent |
| Long grain (sides) | 0.50-0.70 | Smoother, sometimes polished |
| Joints/seams | 0.85-0.95 | Accumulate dirt |
| Wear surfaces (table top, handle) | 0.35-0.55 | Polished by use |
| Painted surfaces | 0.45-0.65 | Smooth but not glossy |

### 4.2 Metal Props

**Rust distribution follows physics:**
1. Water collection points rust first (bottom edges, concavities)
2. Exposed edges rust next (paint chips expose metal)
3. Protected areas (under overhangs, recesses) rust last
4. Full rust only in abandoned/aged items

**Roughness mapping for metal:**
| Zone | Roughness | Metallic | Notes |
|------|-----------|----------|-------|
| Polished/used surface | 0.10-0.25 | 0.90-1.0 | Handles, blade edges |
| Brushed surface | 0.30-0.50 | 0.85-0.95 | Armor plates |
| Patina/tarnish | 0.50-0.70 | 0.60-0.80 | Aged copper/bronze |
| Light rust | 0.60-0.80 | 0.40-0.60 | Partial oxidation |
| Heavy rust | 0.80-0.95 | 0.10-0.30 | Fully oxidized = non-metallic |

### 4.3 Fabric Props (Banners, Curtains, Rugs)

- **Weave pattern:** Normal map carries thread structure (not geometry)
- **Embroidery:** Slightly raised areas in normal map with different roughness/color
- **Fraying edges:** Alpha cutoff with ragged edge mask
- **Roughness:** Fabric is uniformly rough (0.75-0.95), except for silk (0.30-0.50)
- **Subsurface scattering:** Thin fabrics (curtains) transmit light

**Fabric palette (VeilBreakers):**
| Type | Hex | Notes |
|------|-----|-------|
| Common burlap | #5A4D38 | Brown-gray, rough |
| Noble velvet | #2A1A35 | Deep purple, VB royal color |
| Leather | #4A3525 | Warm brown, medium rough |
| Silk (rare) | #C4B8A0 | Pale ivory, low roughness |
| Bloodstained cloth | #4A2020 | Dark red-brown |

### 4.4 Ceramic/Pottery

- **Glaze:** Low roughness (0.15-0.35) on outer surface, high roughness (0.70-0.90) on unglazed base
- **Cracks:** Normal map with slight color variation in crack lines (darker)
- **Kiln marks:** Subtle color variation patches from uneven firing (noise overlay)

### 4.5 Glass/Crystal

- **Refraction:** IOR 1.5 for glass, 1.8-2.0 for crystal
- **Internal scattering:** Volume absorption for colored glass
- **Surface imperfections:** Fingerprints (lower roughness spots), scratches (anisotropic roughness direction)
- **VeilBreakers crystals:** Emissive + refraction. Void crystals use purple emission (#5A3070)

---

## 5. Dark Fantasy Color Science

### 5.1 What Makes Elden Ring Look Like Elden Ring

**Analysis of FromSoftware's color approach:**

1. **Desaturation is the foundation.** Environment saturation rarely exceeds 30%. This creates the sense of a dying/corrupted world. Even "green" areas (Limgrave) use desaturated green (H:95-130, S:15-35, V:20-45).

2. **Value compression.** Most pixels fall in the 15-55% value range. No pure whites, very few pure blacks. This creates a perpetual overcast/twilight feel without being literally dark.

3. **Warm vs. cold regional identity:**
   - Safe areas (firelink, roundtable): Warm gold-orange (H:25-40, warm light sources)
   - Dangerous areas (dungeons, boss rooms): Cool blue-gray (H:200-240, cold ambient)
   - Corrupted areas (Caelid, Haligtree): Unnatural temperature (extreme warm or extreme cold)

4. **Single accent color per area.** Each region has ONE saturated element that draws the eye:
   - Limgrave: Gold Erdtree leaves against gray-green
   - Caelid: Red rot against gray-brown
   - Liurnia: Blue glintstone against gray

5. **Fog as color tool.** Distance fog is NOT neutral gray. It carries the region's color identity:
   - Limgrave fog: warm gray-gold
   - Caelid fog: red-brown
   - Underground: blue-purple

**Confidence:** MEDIUM -- analysis based on community discussion and FromSoftware art direction posts, not official GDC material.

### 5.2 Dark Souls Darkness and Contrast

- Dark Souls uses deeper contrast than Elden Ring (more extreme darks)
- Key insight: darkness is NOT the absence of light but the careful placement of light sources that create pools of visibility surrounded by threatening darkness
- Average scene brightness: 20-35% value (vs. Elden Ring's 25-45%)
- Color grading: green/yellow tint in many areas (reinforces decay/sickness theme)
- Temperature has the greatest effect on overall perception

### 5.3 VeilBreakers Color Rules (Extending Existing Palette)

**Master palette already defined in AAA_QUALITY_ASSETS.md (Section 2.2). Extended rules:**

**Color temperature as storytelling:**
| Zone Type | Color Temperature | Kelvin Equivalent | Fog Color | Mood |
|-----------|-------------------|-------------------|-----------|------|
| Safe haven (town) | Warm | 3500K-4500K | #8A7558 (warm gold) | Comfort, rest |
| Wilderness (neutral) | Neutral | 5000K-6000K | #707070 (neutral gray) | Exploration |
| Danger (dungeon) | Cool | 7000K-9000K | #4A5570 (cold blue) | Tension |
| Corruption (boss) | Extreme/unnatural | N/A | #4A2050 (void purple) | Dread |
| Fire/destruction | Hot | 2500K-3000K | #8A4520 (ember) | Urgency |

**Brand-specific color overlays (VeilBreakers 10 brands):**
| Brand | Primary Hex | Secondary Hex | Environment Tint | Glow Color |
|-------|-------------|---------------|-------------------|------------|
| IRON | #808080 | #5A5A5A | Gray metallic | Silver-white #C0C0C0 |
| SAVAGE | #8A3020 | #5A2015 | Blood red-brown | Dark red #AA2020 |
| SURGE | #2050AA | #153570 | Electric blue | Bright blue #4080FF |
| VENOM | #305A20 | #1A3510 | Sickly green | Acid green #60AA30 |
| DREAD | #2A1535 | #1A0A25 | Deep purple-black | Void purple #6030A0 |
| LEECH | #5A2040 | #3A1030 | Crimson-purple | Blood magenta #AA2060 |
| GRACE | #C4A830 | #8A7520 | Golden warmth | Holy gold #FFD700 |
| MEND | #20705A | #105038 | Teal-green | Healing teal #40C0A0 |
| RUIN | #5A3A15 | #3A2510 | Scorched amber | Fire orange #FF6020 |
| VOID | #1A1030 | #0A0520 | Absolute darkness | Anti-light #8020FF |

### 5.4 Desaturation Techniques

**In Blender (for baked textures):**
```python
# HSV Adjust node setup for dark fantasy desaturation
# Input Color -> Hue/Saturation/Value node
#   Saturation: 0.5-0.7 (reduce from full)
#   Value: 0.6-0.8 (darken slightly)
# -> Output to Principled BSDF Base Color
```

**In Unity (post-processing):**
- Color Grading: Reduce saturation globally by 20-30%
- Per-region color correction via Volume triggers
- Fog color matches region identity (see table above)

### 5.5 Corruption Visual Language

**Corruption manifests as:**
1. Purple-void tinting: shift hue toward 270-290 degrees
2. Desaturation of surrounding materials (corruption drains color)
3. Emissive veins/cracks in geometry (purple glow #6030A0)
4. Roughness increase (corruption makes surfaces matte/chalky)
5. Metallic decrease on metals (corruption tarnishes)

**Corruption gradient (0-100%):**
| Level | Hue Shift | Saturation | Value | Roughness Offset | Visual |
|-------|-----------|------------|-------|-------------------|--------|
| 0% (clean) | 0 | Normal | Normal | 0 | Original material |
| 25% (tainted) | +10 toward purple | -10% | -5% | +0.05 | Subtle discoloration |
| 50% (corrupted) | +25 toward purple | -25% | -15% | +0.10 | Clearly affected |
| 75% (consumed) | +40 toward purple | -40% | -25% | +0.15 | Dominant purple |
| 100% (void) | Full purple (270) | -60% | -35% | +0.20 | Nearly monochrome void |

---

## 6. Weathering and Aging Systems

### 6.1 Edge Wear Generation

**Technique:** Use mesh curvature data to drive roughness and color changes at convex edges.

**Why edges wear first:** Convex edges (corners, ridges) have the most physical contact with the environment. Paint chips, metal polishes, stone rounds.

**Implementation pipeline:**
1. Bake curvature map in Blender (our `render_wear_map` already does this via vertex curvature)
2. Convex curvature (positive) = wear zone
3. In wear zone: lower roughness (worn smooth), lighter color (exposed underlayer), higher metallic (if painted metal)

**Curvature-to-wear mapping:**
| Curvature Range | Effect on Roughness | Effect on Color | Effect on Metallic |
|----------------|--------------------|-----------------|--------------------|
| Strong convex (>0.7) | -0.3 (smoother) | +0.15 lighter | +0.3 (expose metal) |
| Mild convex (0.3-0.7) | -0.15 | +0.08 lighter | +0.15 |
| Flat (0-0.3) | No change | No change | No change |
| Mild concave (-0.3-0) | +0.10 (rougher) | -0.05 darker | No change |
| Strong concave (<-0.3) | +0.20 (rougher) | -0.15 darker | -0.10 (tarnish) |

### 6.2 Dirt/Grime Accumulation

**Follows concavity (AO map as mask):**
- Bake AO map from mesh geometry
- Dark AO areas = dirt accumulation zones
- Apply dirt: darken albedo by 15-30%, increase roughness by 0.1-0.2
- Dirt color: desaturated brown #3A3028

**Implementation in Blender nodes:**
```
AO Bake Texture -> ColorRamp (black=1.0, white=0.0, invert for dirt mask)
  -> Mix RGB (Multiply) with Dirt Color (#3A3028)
  -> Mix with base albedo using AO-derived mask
```

### 6.3 Moss/Lichen Growth

**Placement rules:**
1. Top-facing surfaces (world normal Y > 0.7)
2. Moisture zones (near water, north-facing in northern hemisphere)
3. Not on recently placed or maintained surfaces

**Blender node setup:**
```
Geometry (Normal) -> Separate XYZ -> Z component
  -> Math (Greater Than: 0.5) -> blend weight
  -> Noise Texture (Scale: 8, Detail: 6) -> additional breakup
  -> Multiply both masks
  -> Mix base material with moss material using combined mask
```

**Moss material values:**
| Property | Value |
|----------|-------|
| Albedo | #2A3520 (dark desaturated green) |
| Roughness | 0.80-0.95 |
| Normal | Soft bumps (low frequency noise) |
| Height | Slightly raised from base surface |

### 6.4 Rain Staining

**Vertical streaks on walls caused by water runoff:**
- Appear below window sills, ledges, any horizontal surface
- Pattern: vertical streaks, 2-5cm wide, darkening + roughness change
- Use Blender Wave Texture (Bands mode, stretched vertically) masked to areas below overhangs

**Node recipe:**
```
Texture Coordinate (Object) -> Mapping (Scale X: 0.3, Y: 5.0, Z: 0.3)
  -> Wave Texture (Bands, Scale: 15, Distortion: 3)
  -> ColorRamp (narrow dark band)
  -> multiply with position mask (only below ledges)
  -> darken base albedo and increase roughness
```

### 6.5 Rust Progression

**5 stages of rust (map to corruption or age parameter):**

| Stage | Visual | Roughness | Metallic | Color Hex | When |
|-------|--------|-----------|----------|-----------|------|
| 0: Clean | Shiny metal | 0.15-0.30 | 0.90-1.0 | #707070 | New items |
| 1: Spots | Small rust dots | 0.25-0.45 | 0.75-0.90 | Metal + #8A5530 spots | Months |
| 2: Patches | Expanding rust areas | 0.40-0.60 | 0.50-0.70 | 50% rust coverage | Years |
| 3: Heavy | Most surface rusted | 0.55-0.80 | 0.25-0.45 | #6A4520 dominant | Decades |
| 4: Full | Completely oxidized | 0.75-0.95 | 0.05-0.15 | #5A3515 uniform | Abandoned |

**Blender rust progression recipe:**
```
# Mix rust stages based on age parameter (0-1)
Noise Texture (Scale: 4-12, varying per stage) -> ColorRamp
  -> threshold at different levels per stage
  -> Mix metal base color with rust color using stage mask
  -> Adjust roughness and metallic per-pixel based on same mask
```

### 6.6 Snow Accumulation

**Top-facing surface detection:**
```
Geometry (Normal) -> Separate XYZ -> Z component
  -> Math (Greater Than: threshold 0.6-0.8)
  -> Noise Texture (low frequency, Scale: 2-4) for edge breakup
  -> Multiply masks
  -> Mix base with snow material
```

**Snow material values:**
| Property | Value |
|----------|-------|
| Albedo | #D8D4D0 (slightly warm white, NOT pure white) |
| Roughness | 0.85-0.95 (rough, granular) |
| Subsurface | Slight blue tint for subsurface scattering in deep snow |
| Normal | Very soft, low-frequency bumps |

### 6.7 Fire/Scorch Damage

**Char pattern rules:**
- Radiates outward from ignition point
- Center: black char (#0A0A0A), roughness 0.90
- Edge: gradient to brown (#3A2515), then to darkened original
- Ember glow: emissive spots in recently scorched areas (#FF6020, low intensity)
- Roughness increases dramatically (charred = very rough)

---

## 7. Decal Systems

### 7.1 Unity URP Decal Setup

**Requirements:**
1. Add Decal Renderer Feature to URP Renderer Asset
2. Create material with `Shader Graphs/Decal` shader
3. Set Base Map (albedo) and Normal Map on material
4. Add `DecalProjector` component to GameObject
5. Set projection size (width, height, depth)
6. Rotation: typically 90 degrees X to project downward

**Performance:**
- Enable GPU Instancing on decal materials for batched draw calls
- Limit decal projection depth to minimum needed
- Decals do NOT work on transparent surfaces

**VeilBreakers decal categories:**

### 7.2 Blood Splatter Decals

| Variant | Size Range | Alpha | Normal | Notes |
|---------|-----------|-------|--------|-------|
| Small drops | 0.1-0.3m | Hard-edge alpha | Flat | Cast-off, drips |
| Medium splatter | 0.3-0.8m | Soft-edge alpha | Slight bump | Impact spray |
| Large pool | 0.5-2.0m | Very soft edge | Flat (liquid) | Pooling blood |
| Arterial spray | 0.2m x 1-3m | Directional alpha | Slight relief | Streak pattern |

**Blood color:** #4A1515 (dark, oxidized -- NOT bright red #FF0000)

### 7.3 Ground Damage Decals

| Type | Application | Notes |
|------|-------------|-------|
| Impact crack | Weapon/spell hit point | Radial crack pattern from center |
| Scorch mark | Fire/lightning impact | Darkened circle with radial fade |
| Frost pattern | Ice spell impact | Crystal formation radiating outward |
| Acid burn | Poison/venom impact | Irregular, organic edge with green-brown tint |

### 7.4 Environmental Storytelling Decals

| Type | Purpose | Placement |
|------|---------|-----------|
| Footprints | Show NPC/creature path | Floor, mud, snow |
| Drag marks | Something was pulled | Floor, directional |
| Claw marks | Combat evidence | Walls, doors, floors |
| Written symbols | Lore/puzzles | Walls, stones |
| Water stains | Environmental age | Walls below windows/ledges |
| Soot marks | Fire evidence | Walls, ceilings near fire sources |

---

## 8. Blender Node Recipes

### 8.1 Procedural Stone/Brick Wall

**Complete node graph for medieval stone wall:**

```python
import bpy

def create_stone_wall_material(name="VB_StoneWall"):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (800, 0)

    # Principled BSDF
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (500, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Texture Coordinate + Mapping
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-600, 0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # Brick Texture (stone block pattern)
    brick = nodes.new('ShaderNodeTexBrick')
    brick.location = (-300, 200)
    brick.inputs['Scale'].default_value = 3.0
    brick.inputs['Mortar Size'].default_value = 0.015
    brick.inputs['Mortar Smooth'].default_value = 0.1
    brick.inputs['Bias'].default_value = 0.0
    brick.inputs['Brick Width'].default_value = 0.7
    brick.inputs['Row Height'].default_value = 0.35
    brick.offset = 0.5
    brick.offset_frequency = 2
    links.new(mapping.outputs['Vector'], brick.inputs['Vector'])

    # Stone color variation (Noise for color breakup)
    noise_color = nodes.new('ShaderNodeTexNoise')
    noise_color.location = (-300, -100)
    noise_color.inputs['Scale'].default_value = 8.0
    noise_color.inputs['Detail'].default_value = 6.0
    noise_color.inputs['Roughness'].default_value = 0.7
    links.new(mapping.outputs['Vector'], noise_color.inputs['Vector'])

    # Color ramp for stone tones
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-50, -100)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.054, 0.046, 0.038, 1)  # Dark stone
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.098, 0.083, 0.063, 1)  # Light stone
    links.new(noise_color.outputs['Fac'], ramp.inputs['Fac'])

    # Mix stone color with mortar color using brick mask
    mix_color = nodes.new('ShaderNodeMix')
    mix_color.data_type = 'RGBA'
    mix_color.location = (200, 100)
    mix_color.inputs[6].default_value = (0.12, 0.10, 0.08, 1)  # Mortar color (A input)
    links.new(brick.outputs['Fac'], mix_color.inputs['Factor'])
    links.new(ramp.outputs['Color'], mix_color.inputs[7])  # Stone color (B input)
    links.new(mix_color.outputs[2], bsdf.inputs['Base Color'])

    # Roughness from noise (variation 0.70-0.90)
    noise_rough = nodes.new('ShaderNodeTexNoise')
    noise_rough.location = (-300, -350)
    noise_rough.inputs['Scale'].default_value = 15.0
    noise_rough.inputs['Detail'].default_value = 4.0
    links.new(mapping.outputs['Vector'], noise_rough.inputs['Vector'])

    ramp_rough = nodes.new('ShaderNodeValToRGB')
    ramp_rough.location = (-50, -350)
    ramp_rough.color_ramp.elements[0].position = 0.0
    ramp_rough.color_ramp.elements[0].color = (0.70, 0.70, 0.70, 1)
    ramp_rough.color_ramp.elements[1].position = 1.0
    ramp_rough.color_ramp.elements[1].color = (0.90, 0.90, 0.90, 1)
    links.new(noise_rough.outputs['Fac'], ramp_rough.inputs['Fac'])
    links.new(ramp_rough.outputs['Color'], bsdf.inputs['Roughness'])

    # Bump from brick + noise combined
    bump_noise = nodes.new('ShaderNodeTexNoise')
    bump_noise.location = (-300, -550)
    bump_noise.inputs['Scale'].default_value = 25.0
    bump_noise.inputs['Detail'].default_value = 8.0
    bump_noise.inputs['Roughness'].default_value = 0.6
    links.new(mapping.outputs['Vector'], bump_noise.inputs['Vector'])

    math_add = nodes.new('ShaderNodeMath')
    math_add.operation = 'ADD'
    math_add.location = (0, -500)
    links.new(brick.outputs['Fac'], math_add.inputs[0])
    links.new(bump_noise.outputs['Fac'], math_add.inputs[1])

    bump = nodes.new('ShaderNodeBump')
    bump.location = (200, -500)
    bump.inputs['Strength'].default_value = 0.5
    links.new(math_add.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    # Metallic = 0 for stone
    bsdf.inputs['Metallic'].default_value = 0.0

    return mat
```

### 8.2 Procedural Wood Grain/Plank

```python
import bpy

def create_wood_plank_material(name="VB_WoodPlank"):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (800, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (500, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-1000, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-800, 0)
    mapping.inputs['Scale'].default_value = (1.0, 5.0, 1.0)  # Stretch Y for grain
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # Wave Texture for wood grain rings
    wave = nodes.new('ShaderNodeTexWave')
    wave.location = (-500, 200)
    wave.wave_type = 'RINGS'
    wave.inputs['Scale'].default_value = 2.0
    wave.inputs['Distortion'].default_value = 8.0
    wave.inputs['Detail'].default_value = 3.0
    wave.inputs['Detail Scale'].default_value = 1.0
    wave.inputs['Detail Roughness'].default_value = 0.6
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    # Noise Texture for grain variation
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-500, -100)
    noise.inputs['Scale'].default_value = 12.0
    noise.inputs['Detail'].default_value = 8.0
    noise.inputs['Roughness'].default_value = 0.7
    noise.inputs['Distortion'].default_value = 0.3
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

    # Mix wave and noise for combined grain
    mix_grain = nodes.new('ShaderNodeMath')
    mix_grain.operation = 'ADD'
    mix_grain.location = (-250, 100)
    mix_grain.inputs[1].default_value = 0.0
    links.new(wave.outputs['Fac'], mix_grain.inputs[0])
    links.new(noise.outputs['Fac'], mix_grain.inputs[1])

    # Color ramp for wood tones (aged oak)
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (0, 100)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.040, 0.028, 0.015, 1)  # Dark grain
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (0.067, 0.049, 0.025, 1)  # Light grain
    links.new(mix_grain.outputs['Value'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    # Roughness with grain-following variation
    ramp_rough = nodes.new('ShaderNodeValToRGB')
    ramp_rough.location = (0, -200)
    ramp_rough.color_ramp.elements[0].position = 0.0
    ramp_rough.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1)
    ramp_rough.color_ramp.elements[1].position = 1.0
    ramp_rough.color_ramp.elements[1].color = (0.80, 0.80, 0.80, 1)
    links.new(wave.outputs['Fac'], ramp_rough.inputs['Fac'])
    links.new(ramp_rough.outputs['Color'], bsdf.inputs['Roughness'])

    # Bump from grain pattern
    bump = nodes.new('ShaderNodeBump')
    bump.location = (250, -400)
    bump.inputs['Strength'].default_value = 0.3
    links.new(mix_grain.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bsdf.inputs['Metallic'].default_value = 0.0

    return mat
```

### 8.3 Procedural Rust/Aged Metal

```python
import bpy

def create_rusted_metal_material(name="VB_RustedIron"):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (1000, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (700, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-600, 0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # Noise for rust pattern (large blotches)
    noise_rust = nodes.new('ShaderNodeTexNoise')
    noise_rust.location = (-400, 200)
    noise_rust.inputs['Scale'].default_value = 4.0
    noise_rust.inputs['Detail'].default_value = 6.0
    noise_rust.inputs['Roughness'].default_value = 0.7
    noise_rust.inputs['Distortion'].default_value = 0.5
    links.new(mapping.outputs['Vector'], noise_rust.inputs['Vector'])

    # Voronoi for pit/pock marks
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.location = (-400, -100)
    voronoi.inputs['Scale'].default_value = 12.0
    voronoi.feature = 'F1'
    voronoi.distance = 'EUCLIDEAN'
    links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

    # Rust mask (threshold noise)
    rust_ramp = nodes.new('ShaderNodeValToRGB')
    rust_ramp.location = (-150, 200)
    rust_ramp.color_ramp.elements[0].position = 0.4
    rust_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)  # Metal zone
    rust_ramp.color_ramp.elements[1].position = 0.6
    rust_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)  # Rust zone
    links.new(noise_rust.outputs['Fac'], rust_ramp.inputs['Fac'])

    # Metal base color (dark iron)
    metal_color = nodes.new('ShaderNodeRGB')
    metal_color.location = (0, 400)
    metal_color.outputs[0].default_value = (0.063, 0.057, 0.052, 1)  # Raw iron

    # Rust color
    rust_color = nodes.new('ShaderNodeRGB')
    rust_color.location = (0, 250)
    rust_color.outputs[0].default_value = (0.093, 0.052, 0.035, 1)  # Rust brown

    # Mix metal and rust using mask
    mix_color = nodes.new('ShaderNodeMix')
    mix_color.data_type = 'RGBA'
    mix_color.location = (250, 300)
    links.new(rust_ramp.outputs['Color'], mix_color.inputs['Factor'])
    links.new(metal_color.outputs['Color'], mix_color.inputs[6])  # A: metal
    links.new(rust_color.outputs['Color'], mix_color.inputs[7])  # B: rust
    links.new(mix_color.outputs[2], bsdf.inputs['Base Color'])

    # Metallic: high for metal, low for rust
    mix_metallic = nodes.new('ShaderNodeMix')
    mix_metallic.data_type = 'FLOAT'
    mix_metallic.location = (250, 100)
    mix_metallic.inputs[2].default_value = 0.90  # A: metal metallic
    mix_metallic.inputs[3].default_value = 0.15  # B: rust metallic
    links.new(rust_ramp.outputs['Color'], mix_metallic.inputs['Factor'])
    links.new(mix_metallic.outputs[0], bsdf.inputs['Metallic'])

    # Roughness: low for metal, high for rust
    mix_rough = nodes.new('ShaderNodeMix')
    mix_rough.data_type = 'FLOAT'
    mix_rough.location = (250, -100)
    mix_rough.inputs[2].default_value = 0.25  # A: metal roughness
    mix_rough.inputs[3].default_value = 0.80  # B: rust roughness
    links.new(rust_ramp.outputs['Color'], mix_rough.inputs['Factor'])
    links.new(mix_rough.outputs[0], bsdf.inputs['Roughness'])

    # Bump: combine Voronoi pits with noise surface
    math_add = nodes.new('ShaderNodeMath')
    math_add.operation = 'ADD'
    math_add.location = (250, -300)
    links.new(voronoi.outputs['Distance'], math_add.inputs[0])
    links.new(noise_rust.outputs['Fac'], math_add.inputs[1])

    bump = nodes.new('ShaderNodeBump')
    bump.location = (450, -300)
    bump.inputs['Strength'].default_value = 0.4
    links.new(math_add.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat
```

### 8.4 Procedural Moss/Snow Overlay

```python
import bpy

def create_directional_overlay_material(
    name="VB_MossOverlay",
    overlay_color=(0.028, 0.042, 0.018, 1),  # Dark moss green
    overlay_roughness=0.88,
    direction_threshold=0.5,  # 0.5 = top-facing surfaces
    noise_scale=6.0,
):
    """Creates a material that blends an overlay (moss/snow/dust) onto
    surfaces based on world-space normal direction."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (1000, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (700, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Geometry node for world normal
    geometry = nodes.new('ShaderNodeNewGeometry')
    geometry.location = (-600, 300)

    # Separate XYZ to get Z (up-facing)
    separate = nodes.new('ShaderNodeSeparateXYZ')
    separate.location = (-400, 300)
    links.new(geometry.outputs['Normal'], separate.inputs['Vector'])

    # Threshold for direction (Z > threshold = overlay applies)
    greater = nodes.new('ShaderNodeMath')
    greater.operation = 'GREATER_THAN'
    greater.location = (-200, 300)
    greater.inputs[1].default_value = direction_threshold
    links.new(separate.outputs['Z'], greater.inputs[0])

    # Noise for edge breakup (prevents perfect geometric cutoff)
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-600, 0)
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-400, 0)
    noise.inputs['Scale'].default_value = noise_scale
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 0.6
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])

    # Combine direction mask with noise for organic edge
    multiply = nodes.new('ShaderNodeMath')
    multiply.operation = 'MULTIPLY'
    multiply.location = (0, 200)
    links.new(greater.outputs['Value'], multiply.inputs[0])
    links.new(noise.outputs['Fac'], multiply.inputs[1])

    # Smooth the mask
    smooth_ramp = nodes.new('ShaderNodeValToRGB')
    smooth_ramp.location = (200, 200)
    smooth_ramp.color_ramp.elements[0].position = 0.3
    smooth_ramp.color_ramp.elements[1].position = 0.7
    links.new(multiply.outputs['Value'], smooth_ramp.inputs['Fac'])

    # Base material color (placeholder -- would be mixed with existing)
    base_color = nodes.new('ShaderNodeRGB')
    base_color.location = (200, -100)
    base_color.outputs[0].default_value = (0.054, 0.046, 0.038, 1)  # Stone

    # Overlay color
    overlay_rgb = nodes.new('ShaderNodeRGB')
    overlay_rgb.location = (200, -250)
    overlay_rgb.outputs[0].default_value = overlay_color

    # Mix base with overlay
    mix_color = nodes.new('ShaderNodeMix')
    mix_color.data_type = 'RGBA'
    mix_color.location = (450, 0)
    links.new(smooth_ramp.outputs['Color'], mix_color.inputs['Factor'])
    links.new(base_color.outputs['Color'], mix_color.inputs[6])
    links.new(overlay_rgb.outputs['Color'], mix_color.inputs[7])
    links.new(mix_color.outputs[2], bsdf.inputs['Base Color'])

    # Roughness blend
    mix_rough = nodes.new('ShaderNodeMix')
    mix_rough.data_type = 'FLOAT'
    mix_rough.location = (450, -200)
    mix_rough.inputs[2].default_value = 0.82  # Base roughness
    mix_rough.inputs[3].default_value = overlay_roughness
    links.new(smooth_ramp.outputs['Color'], mix_rough.inputs['Factor'])
    links.new(mix_rough.outputs[0], bsdf.inputs['Roughness'])

    return mat
```

### 8.5 Procedural Cobblestone/Irregular Stone Floor

```python
import bpy

def create_cobblestone_material(name="VB_Cobblestone"):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (900, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (600, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-600, 0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # Voronoi for stone cell pattern
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.location = (-350, 200)
    voronoi.inputs['Scale'].default_value = 6.0
    voronoi.feature = 'F1'
    voronoi.distance = 'EUCLIDEAN'
    links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

    # Voronoi edge detection (F2 - F1 for mortar lines)
    voronoi_edge = nodes.new('ShaderNodeTexVoronoi')
    voronoi_edge.location = (-350, -100)
    voronoi_edge.inputs['Scale'].default_value = 6.0
    voronoi_edge.feature = 'DISTANCE_TO_EDGE'
    voronoi_edge.distance = 'EUCLIDEAN'
    links.new(mapping.outputs['Vector'], voronoi_edge.inputs['Vector'])

    # Mortar mask from edge distance
    mortar_ramp = nodes.new('ShaderNodeValToRGB')
    mortar_ramp.location = (-100, -100)
    mortar_ramp.color_ramp.elements[0].position = 0.0
    mortar_ramp.color_ramp.elements[0].color = (1, 1, 1, 1)  # Mortar
    mortar_ramp.color_ramp.elements[1].position = 0.05
    mortar_ramp.color_ramp.elements[1].color = (0, 0, 0, 1)  # Stone face
    links.new(voronoi_edge.outputs['Distance'], mortar_ramp.inputs['Fac'])

    # Per-stone color variation (use Voronoi cell color)
    noise_color = nodes.new('ShaderNodeTexNoise')
    noise_color.location = (-350, -350)
    noise_color.inputs['Scale'].default_value = 3.0
    noise_color.inputs['Detail'].default_value = 4.0
    links.new(mapping.outputs['Vector'], noise_color.inputs['Vector'])

    # Stone color ramp
    stone_ramp = nodes.new('ShaderNodeValToRGB')
    stone_ramp.location = (-100, 200)
    stone_ramp.color_ramp.elements[0].position = 0.2
    stone_ramp.color_ramp.elements[0].color = (0.04, 0.035, 0.03, 1)
    stone_ramp.color_ramp.elements[1].position = 0.8
    stone_ramp.color_ramp.elements[1].color = (0.08, 0.07, 0.055, 1)
    links.new(voronoi.outputs['Distance'], stone_ramp.inputs['Fac'])

    # Mortar color
    mortar_color = nodes.new('ShaderNodeRGB')
    mortar_color.location = (50, -200)
    mortar_color.outputs[0].default_value = (0.06, 0.05, 0.04, 1)

    # Mix stone + mortar
    mix_final = nodes.new('ShaderNodeMix')
    mix_final.data_type = 'RGBA'
    mix_final.location = (300, 100)
    links.new(mortar_ramp.outputs['Color'], mix_final.inputs['Factor'])
    links.new(stone_ramp.outputs['Color'], mix_final.inputs[6])
    links.new(mortar_color.outputs['Color'], mix_final.inputs[7])
    links.new(mix_final.outputs[2], bsdf.inputs['Base Color'])

    # Roughness
    bsdf.inputs['Roughness'].default_value = 0.82

    # Displacement/Bump from Voronoi distance
    bump = nodes.new('ShaderNodeBump')
    bump.location = (400, -300)
    bump.inputs['Strength'].default_value = 0.6
    links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bsdf.inputs['Metallic'].default_value = 0.0

    return mat
```

---

## 9. Anti-Tiling Techniques

### 9.1 Stochastic Tiling (Inigo Quilez Method)

**The definitive technique for eliminating tiling repetition.**

**Algorithm (Technique 1: Per-Tile Random Transformation):**
1. Determine which tile contains the current UV sample
2. Generate 4 pseudo-random values per tile using a hash function
3. Apply mirroring transformations (x, y, or both directions)
4. Blend between 4 adjacent tiles near borders using smoothstep
5. Propagate orientation transformations to texture derivatives for correct mipmapping

**GLSL implementation:**
```glsl
vec4 textureNoTile(sampler2D samp, in vec2 uv) {
    ivec2 iuv = ivec2(floor(uv));
    vec2 fuv = fract(uv);

    // Hash function for random per-tile values
    vec4 ofa = hash4(iuv + ivec2(0,0));
    vec4 ofb = hash4(iuv + ivec2(1,0));
    vec4 ofc = hash4(iuv + ivec2(0,1));
    vec4 ofd = hash4(iuv + ivec2(1,1));

    // Apply orientation mirroring
    ofa.zw = sign(ofa.zw - 0.5);
    ofb.zw = sign(ofb.zw - 0.5);
    ofc.zw = sign(ofc.zw - 0.5);
    ofd.zw = sign(ofd.zw - 0.5);

    // Smooth blend factor at tile borders
    vec2 b = smoothstep(0.25, 0.75, fuv);

    // Sample with random offset + mirror, blend 4 corners
    return mix(
        mix(texture(samp, uv * ofa.zw + ofa.xy), texture(samp, uv * ofb.zw + ofb.xy), b.x),
        mix(texture(samp, uv * ofc.zw + ofc.xy), texture(samp, uv * ofd.zw + ofd.xy), b.x),
        b.y);
}
```

**Cost:** 4 texture samples per pixel (can be reduced to ~1.5 with dynamic culling).

### 9.2 Alternative: Voronoi-Based Blending

- Sample texture 9 times (3x3 neighborhood) with weighted contributions
- Each Voronoi cell applies random offset to UV
- Gaussian falloff weighting: `w = exp(-5.0 * distance)`
- Higher cost (9 samples) but smoother results for organic textures

### 9.3 Blender-Side Anti-Tiling

**Object Info Random technique:**
```
Object Info node (Random output, 0-1 per object)
  -> Math (Multiply by 0.1)
  -> Add to Mapping node offset
  -> Feeds texture coordinate

Result: each instance of a wall tile has slightly different UV offset
```

**Multi-octave noise overlay:**
```
Low-frequency Noise (Scale: 0.5-1.0) -> ColorRamp (subtle range)
  -> Multiply with base texture
  -> Breaks up visible repetition at large scale
```

---

## 10. Unity URP Integration

### 10.1 Terrain Layer Setup

**URP TerrainLit shader configuration:**
1. Create Material with shader `Universal Render Pipeline/Terrain/Lit`
2. Create TerrainLayer assets (one per texture layer)
3. Each TerrainLayer has:
   - Diffuse Texture (albedo)
   - Normal Map Texture
   - Mask Map Texture (R=Metallic, G=AO, B=Height, A=Smoothness)
   - Tiling settings (typically 10-30 for terrain-scale)

**Height-Based Blend (URP built-in):**
- Enable "Height-based Blend" on the Terrain material
- Blue channel of Mask Map stores height data per terrain layer
- First 4 layers support height-based transitions
- Additional layers fall back to standard alpha blending

### 10.2 Channel Packing for Unity

**Mask Map packing standard (URP/HDRP):**
| Channel | Content | Notes |
|---------|---------|-------|
| R | Metallic | 0.0 for non-metals, 0.85-1.0 for metals |
| G | Ambient Occlusion | White = no occlusion, dark = occluded |
| B | Height (for parallax/blend) | Used by terrain height blend |
| A | Smoothness | Inverted roughness (1.0 - roughness) |

**Critical: Unity uses Smoothness, not Roughness.** Convert: `smoothness = 1.0 - roughness`

### 10.3 Decal Renderer Feature

**Setup steps for URP:**
1. Select URP Renderer Asset
2. Add Renderer Feature: "Decal"
3. Configure: Screen Space (performance) or DBuffer (normal affect)
4. DBuffer mode allows decals to modify normals (better for blood/damage)
5. Create Decal materials using Shader Graphs/Decal

**Decal material properties:**
- Base Map: albedo with alpha transparency
- Normal Map: for surface detail modification
- Affect Albedo/Normal/MAOS: toggle per-property
- Draw Order: higher values render on top of lower

### 10.4 Vertex Color Material Blending in Unity

**For buildings/props with weathering gradients:**
```csharp
// Shader Graph approach:
// 1. Vertex Color node -> Split (R, G, B, A)
// 2. R channel -> Lerp between clean material and dirt material
// 3. G channel -> Lerp between base material and moss material
// 4. B channel -> Lerp between base material and damaged material
// 5. A channel -> wetness level (darken albedo, reduce roughness)
```

**Painting vertex colors in Blender for Unity:**
- Use Blender's Vertex Paint mode
- R = dirt amount, G = moss amount, B = damage/wear, A = wetness
- Colors export with FBX and are available in Unity's Shader Graph via Vertex Color node

### 10.5 Texture Size Standards for Unity Import

| Asset Type | Max Texture Size | Compression | Mipmaps |
|------------|-----------------|-------------|---------|
| Terrain layer (tiling) | 2048x2048 | BC7 (albedo), BC5 (normal) | Yes |
| Building trim sheet | 2048x2048 | BC7 | Yes |
| Prop albedo | 512-1024 | BC7 | Yes |
| Decal | 256-512 | BC7 with alpha | Yes |
| Vegetation atlas | 1024-2048 | BC7 with alpha | Yes |
| Detail normal | 512x512 | BC5 | Yes |

---

## Common Pitfalls

### Pitfall 1: Flat Roughness Maps
**What goes wrong:** Every pixel has the same roughness value. Everything looks like plastic.
**Why:** Artists set a single roughness slider and forget variation.
**How to avoid:** ALWAYS use noise-driven roughness with 0.15-0.30 variation range. Our `validate_roughness_map()` already catches this (minimum variance 0.05).
**Warning signs:** Screenshot looks "CG" or "fake" despite correct albedo.

### Pitfall 2: Baked Lighting in Albedo
**What goes wrong:** Textures have shadows and highlights baked in. They light incorrectly in-engine.
**Why:** AI-generated textures and photographic textures contain baked lighting.
**How to avoid:** Use `blender_texture` action=`delight` to remove baked lighting. Always validate that albedo has uniform brightness under flat lighting.
**Warning signs:** Shadows appear doubled (baked + realtime), highlights don't move with light.

### Pitfall 3: Visible Tiling on Large Surfaces
**What goes wrong:** Walls, floors, terrain show obvious repeating pattern.
**Why:** Single tiling texture without anti-tiling measures.
**How to avoid:** Layer 3 techniques: stochastic tiling (shader), macro variation (low-freq noise), and decal overlays.
**Warning signs:** Visible grid pattern from any viewing angle.

### Pitfall 4: Wrong Grain Direction on Wood
**What goes wrong:** Wood grain runs perpendicular to the physical construction.
**Why:** UV orientation not matched to plank direction.
**How to avoid:** UV-map each plank face separately, rotate UVs to align grain with plank length.
**Warning signs:** Barrel staves with horizontal grain, table with cross-grain.

### Pitfall 5: Hard Material Boundaries
**What goes wrong:** Stone meets wood in a perfect straight line. Looks artificial.
**Why:** No blend zone at material transitions.
**How to avoid:** Height-based blend at transitions, 5-15cm blend zone with mortar/grout fill.
**Warning signs:** Visible seam lines at material changes.

### Pitfall 6: Over-Saturated Colors in Dark Fantasy
**What goes wrong:** Environment looks like a cartoon or theme park.
**Why:** Using full-saturation textures in a dark fantasy context.
**How to avoid:** Environment saturation cap 30-40%. Use `validate_palette` (already built). Only magic/VFX may exceed 60%.
**Warning signs:** Colors "pop" too much, scene feels cheerful instead of foreboding.

### Pitfall 7: Pure White Snow / Pure Black Shadows
**What goes wrong:** Snow is RGB(255,255,255), shadows are RGB(0,0,0). Looks wrong.
**Why:** Real snow absorbs some light, real shadows receive ambient light.
**How to avoid:** Snow albedo max ~0.85 (slightly warm), shadow minimum ~0.05 (slightly blue).
**Warning signs:** Blown-out snow areas, crushed shadow detail.

### Pitfall 8: Unity Smoothness vs Blender Roughness Confusion
**What goes wrong:** Materials look inverted (rough things are shiny, shiny things are rough).
**Why:** Blender uses Roughness (0=mirror, 1=rough), Unity URP uses Smoothness (0=rough, 1=mirror).
**How to avoid:** Convert on export: `smoothness = 1.0 - roughness`. Invert the channel when packing mask maps.
**Warning signs:** Metal surfaces look chalky, stone surfaces look wet.

---

## Sources

### Primary (HIGH confidence)
- [Unity TerrainLit Shader Documentation (URP 14.0)](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0/manual/shader-terrain-lit.html) -- height-based blend, mask map channels
- [Unity Terrain Layers Manual](https://docs.unity3d.com/Manual/class-TerrainLayer.html) -- terrain layer configuration
- [Unity URP Decal Projector Reference](https://docs.unity3d.com/6000.1/Documentation/Manual/urp/renderer-feature-decal-projector-reference.html) -- decal setup and properties
- [Unity Decal Renderer Feature](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@14.0/manual/renderer-feature-decal.html) -- DBuffer vs Screen Space
- [Blender Voronoi Texture Node](https://docs.blender.org/manual/en/latest/render/shader_nodes/textures/voronoi.html) -- Worley noise, features
- [Blender Brick Texture Node](https://docs.blender.org/manual/en/latest/render/shader_nodes/textures/brick.html) -- parameters, mortar
- [Inigo Quilez: Texture Repetition](https://iquilezles.org/articles/texturerepetition/) -- stochastic tiling algorithms
- [Sebastien Lagarde: Dynamic Rain Effects](https://seblagarde.wordpress.com/2013/01/03/water-drop-2b-dynamic-rain-and-its-effects/) -- wet surface rendering formulas
- [InnoGames: Terrain Shader in Unity](https://blog.innogames.com/terrain-shader-in-unity/) -- splatmap blending, vertex color macro variation

### Secondary (MEDIUM confidence)
- [Beyond Extent: Trim Sheets Deep Dive](https://www.beyondextent.com/deep-dives/trimsheets) -- trim sheet workflow and UV mapping
- [Unity Procedural Stochastic Texturing Blog](https://blog.unity.com/technology/procedural-stochastic-texturing-in-unity) -- Unity Labs stochastic implementation
- [Polycount Terrain Texturing Techniques](https://polycount.com/discussion/130929/terrain-texturing-techniques) -- community techniques
- [Advanced Terrain Texture Splatting (GameDeveloper.com)](https://www.gamedeveloper.com/programming/advanced-terrain-texture-splatting) -- height-based blending algorithm
- [Frostbite Terrain Rendering Chapter](https://media.contentapi.ea.com/content/dam/eacom/frostbite/files/chapter5-andersson-terrain-rendering-in-frostbite.pdf) -- AAA terrain rendering
- [MicroSplat Anti-Tiling Module](https://assetstore.unity.com/packages/tools/terrain/microsplat-anti-tiling-module-96480) -- commercial anti-tiling solution
- [Curvature Map (Polycount Wiki)](http://wiki.polycount.com/wiki/Curvature_map) -- edge wear from curvature
- [FromSoftware Color Palette Analysis (ArtStation)](https://www.artstation.com/artwork/ZeqLv0) -- Patryk Szymanski's palette analysis
- [Removing 4-Layer Limit for Height Blending (2026)](https://medium.com/@sinitsyndev/removing-the-4-layer-limit-for-height-based-blending-in-unity-terrain-urp-c0ba85444f58) -- extending URP terrain layers

### Tertiary (LOW confidence -- needs validation)
- Community color palette extractions from Elden Ring (varies by source)
- Dark Souls modding community color grading discussions

---

## Appendix: Complete VeilBreakers Material Library Constants

```python
"""VeilBreakers Master Material Library for procedural texturing.

Each entry defines PBR values for use in Blender procedural materials
and Unity material setup. Colors are in linear RGB (not sRGB).
"""

VB_MATERIAL_LIBRARY = {
    # ===== STONE =====
    "stone_carved_granite": {
        "base_color": (0.054, 0.046, 0.038),
        "roughness_range": (0.75, 0.85),
        "metallic": 0.0,
        "normal_strength": 1.0,
        "hex": "#3D3833",
    },
    "stone_rough_limestone": {
        "base_color": (0.098, 0.083, 0.063),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 1.2,
        "hex": "#5C5347",
    },
    "stone_mossy_flagstone": {
        "base_color": (0.067, 0.072, 0.048),
        "roughness_range": (0.70, 0.90),
        "metallic": 0.0,
        "normal_strength": 0.8,
        "hex": "#4A4E3D",
    },
    "stone_dark_basalt": {
        "base_color": (0.028, 0.024, 0.018),
        "roughness_range": (0.85, 0.95),
        "metallic": 0.0,
        "normal_strength": 1.0,
        "hex": "#2A2520",
    },
    "stone_crumbling_sandstone": {
        "base_color": (0.155, 0.127, 0.093),
        "roughness_range": (0.70, 0.85),
        "metallic": 0.0,
        "normal_strength": 1.0,
        "hex": "#7A6B55",
    },
    "stone_mortar": {
        "base_color": (0.12, 0.10, 0.08),
        "roughness_range": (0.85, 0.95),
        "metallic": 0.0,
        "normal_strength": 0.5,
        "hex": "#605850",
    },

    # ===== WOOD =====
    "wood_aged_oak": {
        "base_color": (0.067, 0.049, 0.025),
        "roughness_range": (0.55, 0.80),
        "metallic": 0.0,
        "normal_strength": 0.8,
        "hex": "#4A3825",
    },
    "wood_charred_timber": {
        "base_color": (0.028, 0.018, 0.012),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 0.6,
        "hex": "#2A1F18",
    },
    "wood_rotting_plank": {
        "base_color": (0.046, 0.035, 0.025),
        "roughness_range": (0.75, 0.90),
        "metallic": 0.0,
        "normal_strength": 1.0,
        "hex": "#3B3025",
    },
    "wood_polished_mahogany": {
        "base_color": (0.093, 0.049, 0.029),
        "roughness_range": (0.30, 0.50),
        "metallic": 0.0,
        "normal_strength": 0.6,
        "hex": "#5A3D28",
    },
    "wood_birch_pale": {
        "base_color": (0.197, 0.168, 0.123),
        "roughness_range": (0.55, 0.70),
        "metallic": 0.0,
        "normal_strength": 0.7,
        "hex": "#8A7D68",
    },

    # ===== METAL =====
    "metal_rusted_iron": {
        "base_color": (0.093, 0.052, 0.035),
        "roughness_range": (0.55, 0.75),
        "metallic": 0.85,
        "normal_strength": 1.0,
        "hex": "#5A4030",
    },
    "metal_blackened_steel": {
        "base_color": (0.025, 0.023, 0.018),
        "roughness_range": (0.30, 0.50),
        "metallic": 0.92,
        "normal_strength": 0.8,
        "hex": "#252320",
    },
    "metal_tarnished_bronze": {
        "base_color": (0.127, 0.093, 0.035),
        "roughness_range": (0.40, 0.60),
        "metallic": 0.88,
        "normal_strength": 0.7,
        "hex": "#6A5530",
    },
    "metal_raw_iron": {
        "base_color": (0.063, 0.057, 0.052),
        "roughness_range": (0.45, 0.65),
        "metallic": 0.90,
        "normal_strength": 0.8,
        "hex": "#484440",
    },

    # ===== FABRIC =====
    "fabric_burlap": {
        "base_color": (0.093, 0.077, 0.052),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 1.2,
        "hex": "#5A4D38",
    },
    "fabric_noble_velvet": {
        "base_color": (0.028, 0.012, 0.042),
        "roughness_range": (0.60, 0.75),
        "metallic": 0.0,
        "normal_strength": 0.6,
        "hex": "#2A1A35",
    },
    "fabric_leather": {
        "base_color": (0.067, 0.042, 0.025),
        "roughness_range": (0.50, 0.70),
        "metallic": 0.0,
        "normal_strength": 0.8,
        "hex": "#4A3525",
    },
    "fabric_silk_pale": {
        "base_color": (0.217, 0.197, 0.162),
        "roughness_range": (0.25, 0.40),
        "metallic": 0.0,
        "normal_strength": 0.3,
        "hex": "#C4B8A0",
    },

    # ===== ORGANIC =====
    "organic_bone_ivory": {
        "base_color": (0.197, 0.168, 0.123),
        "roughness_range": (0.40, 0.60),
        "metallic": 0.0,
        "normal_strength": 0.5,
        "hex": "#8A7B65",
    },
    "organic_bark_dark": {
        "base_color": (0.042, 0.035, 0.025),
        "roughness_range": (0.70, 0.90),
        "metallic": 0.0,
        "normal_strength": 1.2,
        "hex": "#3A3028",
    },
    "organic_moss_dark": {
        "base_color": (0.028, 0.042, 0.018),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 0.8,
        "hex": "#2A3520",
    },
    "organic_dead_leaf": {
        "base_color": (0.067, 0.049, 0.035),
        "roughness_range": (0.75, 0.90),
        "metallic": 0.0,
        "normal_strength": 0.6,
        "hex": "#4A3825",
    },

    # ===== TERRAIN =====
    "terrain_grass_dark": {
        "base_color": (0.028, 0.048, 0.020),
        "roughness_range": (0.75, 0.90),
        "metallic": 0.0,
        "normal_strength": 0.5,
        "hex": "#243D1C",
    },
    "terrain_dirt_brown": {
        "base_color": (0.067, 0.049, 0.035),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 0.8,
        "hex": "#4A3825",
    },
    "terrain_mud_wet": {
        "base_color": (0.042, 0.032, 0.022),
        "roughness_range": (0.30, 0.50),
        "metallic": 0.0,
        "normal_strength": 0.4,
        "hex": "#3A2820",
    },
    "terrain_rock_cliff": {
        "base_color": (0.063, 0.057, 0.048),
        "roughness_range": (0.75, 0.90),
        "metallic": 0.0,
        "normal_strength": 1.2,
        "hex": "#484438",
    },
    "terrain_gravel": {
        "base_color": (0.098, 0.090, 0.077),
        "roughness_range": (0.80, 0.95),
        "metallic": 0.0,
        "normal_strength": 1.0,
        "hex": "#605850",
    },
    "terrain_snow": {
        "base_color": (0.680, 0.660, 0.640),
        "roughness_range": (0.85, 0.95),
        "metallic": 0.0,
        "normal_strength": 0.2,
        "hex": "#D8D4D0",
    },

    # ===== SPECIAL =====
    "special_void_crystal": {
        "base_color": (0.042, 0.018, 0.063),
        "roughness_range": (0.05, 0.15),
        "metallic": 0.0,
        "emission_color": (0.35, 0.19, 0.63),
        "emission_strength": 2.0,
        "hex": "#5A3070",
    },
    "special_blood_dried": {
        "base_color": (0.067, 0.012, 0.012),
        "roughness_range": (0.60, 0.80),
        "metallic": 0.0,
        "normal_strength": 0.3,
        "hex": "#4A1515",
    },
    "special_corruption_surface": {
        "base_color": (0.028, 0.012, 0.042),
        "roughness_range": (0.70, 0.90),
        "metallic": 0.0,
        "emission_color": (0.22, 0.08, 0.42),
        "emission_strength": 0.5,
        "hex": "#2A1535",
    },
}

# ===== CORRUPTION MODIFIER =====
# Apply to any material to create corruption variants
def apply_corruption(material_values: dict, corruption_level: float) -> dict:
    """Apply corruption modifier to a material dictionary.

    Args:
        material_values: dict from VB_MATERIAL_LIBRARY
        corruption_level: 0.0 (clean) to 1.0 (fully corrupted)

    Returns:
        Modified material dict with corruption applied.
    """
    import colorsys
    r, g, b = material_values["base_color"]

    # Convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Shift hue toward purple (0.75 in 0-1 range = 270 degrees)
    target_hue = 0.75
    h = h + (target_hue - h) * corruption_level * 0.6

    # Reduce saturation
    s = max(0, s * (1 - corruption_level * 0.6))

    # Reduce value
    v = max(0.01, v * (1 - corruption_level * 0.35))

    # Convert back
    r2, g2, b2 = colorsys.hsv_to_rgb(h % 1.0, s, v)

    result = dict(material_values)
    result["base_color"] = (r2, g2, b2)

    # Increase roughness
    rmin, rmax = result["roughness_range"]
    result["roughness_range"] = (
        min(1.0, rmin + corruption_level * 0.20),
        min(1.0, rmax + corruption_level * 0.15),
    )

    # Reduce metallic
    if result.get("metallic", 0) > 0:
        result["metallic"] = max(0, result["metallic"] * (1 - corruption_level * 0.5))

    return result
```

---

## Appendix: Trim Sheet UV Template

**Standard VeilBreakers trim sheet layout (2048x2048):**

```
V coordinate (bottom to top):
+---------------------------------------------------+  1.0
| Strip 7: Roof tiles/shingles    (256px = 12.5%)   |
+---------------------------------------------------+  0.875
| Strip 6: Foundation stone       (128px = 6.25%)   |
+---------------------------------------------------+  0.8125
| Strip 5: Window/door frames     (256px = 12.5%)   |
+---------------------------------------------------+  0.6875
| Strip 4: Wooden planks          (128px = 6.25%)   |
+---------------------------------------------------+  0.625
| Strip 3: Brick pattern          (256px = 12.5%)   |
+---------------------------------------------------+  0.5
| Strip 2: Small stone blocks     (128px = 6.25%)   |
+---------------------------------------------------+  0.4375
| Strip 1: Large stone blocks     (256px = 12.5%)   |
+---------------------------------------------------+  0.3125
| Strip 0: Crown/base molding     (128px = 6.25%)   |
+---------------------------------------------------+  0.25
| Unique elements (non-tiling)    (512px = 25%)      |
| (handles, keypads, signs, etc.)                    |
+---------------------------------------------------+  0.0

U coordinate: 0.0 to 1.0 (tiles horizontally)
```

**UV mapping rule:** Straighten UV shells and align to strip V-coordinates. UVs may extend beyond 0-1 in U direction (the strips tile horizontally).
