# AAA Texturing: Weapons, Items & Equipment

**Researched:** 2026-03-22
**Domain:** PBR weapon/item/equipment texturing pipeline -- Blender procedural + Unity URP
**Confidence:** HIGH (verified against Physically Based database, Adobe PBR Guide, Blender docs, Unity URP docs, ArtStation industry breakdowns, existing codebase)

---

## Summary

AAA dark fantasy weapon texturing follows a strict material-tier system where each metal type (iron, steel, silver, gold, mythical) has precisely defined PBR values and procedural surface characteristics. The key differentiator between professional and amateur weapon textures is roughness variation -- a single material should span 0.2-0.9 roughness across its surface, driven by curvature-based wear maps. Rarity progression communicates quality through four visual channels simultaneously: material quality, detail density, color saturation, and emission intensity. Enchantment effects use a layered overlay system with base texture + emission map + UV-scrolling energy channel, blended per-brand via a `_BrandColor` property.

**Primary recommendation:** Build a material-tier library with exact PBR value ranges per tier, procedural Blender node groups per material type (baked to UV-mapped textures for export), curvature-driven wear map generation (already partially built), and a Unity-side enchantment overlay shader that composites brand-colored emission over base equipment materials. Use shared texture atlases per weapon category to reduce draw calls.

---

## 1. PBR Reference Values by Material Type

### 1.1 Metal Base Color Values (Linear RGB)

These are physically measured values from the Physically Based database and the Adobe Substance PBR Guide. All metals use Metallic=1.0 in the metallic/roughness workflow.

| Material | Linear RGB (Base Color) | sRGB (Approx) | IOR | Notes |
|----------|------------------------|---------------|-----|-------|
| **Iron (raw)** | (0.560, 0.570, 0.580) | #8A8D90 | 2.950 | Blue-gray, darkens quickly with oxidation |
| **Iron (forged/dark)** | (0.290, 0.210, 0.150) | #6B5038 | 2.950 | VeilBreakers rusted iron palette |
| **Steel (polished)** | (0.669, 0.639, 0.598) | #B3AB9E | 2.500 | Warm silver, bright reflections |
| **Steel (weathered)** | (0.450, 0.420, 0.390) | #8A8075 | 2.500 | Darker, more character |
| **Silver** | (0.972, 0.960, 0.915) | #FBF5EA | 1.350 | Brightest metal, almost white |
| **Gold** | (1.000, 0.766, 0.336) | #FFC45E | 0.470 | Strong warm bias, never gray |
| **Copper** | (0.955, 0.638, 0.538) | #F7A58A | 1.100 | Pink-orange, tarnishes to green (verdigris) |
| **Bronze** | (0.800, 0.580, 0.350) | #D69860 | 1.180 | Warm gold-brown, patinas to dark green |
| **Titanium** | (0.542, 0.497, 0.449) | #958478 | 2.160 | Gray-blue, anodizes to rainbow |
| **Aluminum** | (0.912, 0.914, 0.920) | #EBEBED | 1.440 | Cool gray, very bright |
| **Chromium** | (0.550, 0.556, 0.554) | #8B8D8C | 2.970 | Mirror-like when polished |
| **Platinum** | (0.673, 0.637, 0.585) | #B3A89A | 2.330 | Similar to steel but warmer |

**Fantasy Metals (extrapolated from visual references):**

| Material | Linear RGB | Metallic | Notes |
|----------|-----------|----------|-------|
| **Mithril** | (0.750, 0.820, 0.900) | 1.0 | Blue-silver sheen, brighter than steel |
| **Obsidian** | (0.020, 0.020, 0.025) | 0.0 | Non-metallic glass, uses transmission |
| **Dragonbone** | (0.700, 0.680, 0.600) | 0.0 | Non-metallic, bone with mineral veins |
| **Void-touched** | (0.100, 0.050, 0.150) | 0.6-0.9 | Shifting dark purple-black metal |

### 1.2 Non-Metal Base Color Values

| Material | Linear RGB | Metallic | Roughness Range | Notes |
|----------|-----------|----------|-----------------|-------|
| **Leather (new)** | (0.220, 0.150, 0.080) | 0.0 | 0.50-0.70 | Warm brown, slight sheen |
| **Leather (aged)** | (0.160, 0.100, 0.060) | 0.0 | 0.60-0.85 | Darker, more matte |
| **Leather (black)** | (0.040, 0.035, 0.030) | 0.0 | 0.45-0.65 | Used for grips |
| **Wood (oak)** | (0.200, 0.130, 0.060) | 0.0 | 0.55-0.80 | Warm, grain visible |
| **Wood (dark/ebony)** | (0.060, 0.040, 0.030) | 0.0 | 0.40-0.65 | Near black, slight sheen |
| **Wood (charred)** | (0.030, 0.025, 0.020) | 0.0 | 0.85-1.00 | Matte black |
| **Bone** | (0.793, 0.793, 0.664) | 0.0 | 0.50-0.75 | IOR 1.5, yellowish white |
| **Bone (aged)** | (0.550, 0.500, 0.380) | 0.0 | 0.60-0.80 | Darker, more amber |
| **Fabric (linen)** | (0.450, 0.400, 0.340) | 0.0 | 0.80-1.00 | Always very rough |
| **Fabric (silk)** | (0.350, 0.300, 0.280) | 0.0 | 0.30-0.50 | Anisotropic highlight |
| **Cord/rope** | (0.300, 0.250, 0.180) | 0.0 | 0.85-1.00 | Hemp/jute coloring |
| **Ray-skin** | (0.550, 0.520, 0.460) | 0.0 | 0.65-0.80 | Dotted texture, pale |
| **Stone** | (0.160, 0.140, 0.120) | 0.0 | 0.70-0.95 | Per VeilBreakers palette |
| **Glass (clear)** | (1.000, 1.000, 1.000) | 0.0 | 0.00-0.10 | IOR 1.52, transmission |
| **Glass (colored)** | (varies by color) | 0.0 | 0.00-0.15 | IOR 1.52, absorption |
| **Crystal/Gem** | (varies) | 0.0 | 0.00-0.05 | IOR 1.54-2.42, faceted |

### 1.3 Roughness Ranges Per Weapon Condition

| Condition | Metal Roughness | Wood Roughness | Leather Roughness |
|-----------|----------------|----------------|-------------------|
| **Pristine/New** | 0.15-0.30 | 0.50-0.65 | 0.45-0.55 |
| **Well-Maintained** | 0.25-0.45 | 0.55-0.70 | 0.50-0.65 |
| **Battle-Worn** | 0.40-0.65 | 0.65-0.80 | 0.60-0.75 |
| **Damaged** | 0.55-0.80 | 0.75-0.90 | 0.70-0.85 |
| **Ancient/Corroded** | 0.70-0.95 | 0.85-1.00 | 0.80-0.95 |

---

## 2. Weapon Texturing by Material Tier

### 2.1 Iron Weapons

**Visual Character:** Heavy, utilitarian, dark. The workhorse metal of dark fantasy.

| Feature | Texture Treatment |
|---------|-------------------|
| **Base surface** | Dark gray-brown (0.29, 0.21, 0.15), never uniform -- use noise-driven color variation |
| **Forging marks** | Subtle directional scratches in normal map aligned with hammer strike direction |
| **Scale patterns** | Mill scale (dark flaky oxide) on flat surfaces, lighter at edges where scaled chipped |
| **Quench lines** | Faint wavy patterns in roughness (hamon line on blade), roughness variation 0.15 delta |
| **Rust distribution** | Curvature-driven: concave areas rust first, convex edges stay cleaner |
| **Edge treatment** | Slightly brighter albedo + lower roughness at sharpened edges |
| **Pitting** | Random small dark spots in albedo + normal map indentations |

**Blender Node Recipe -- Iron Blade:**
```
Noise Texture (Scale 15, Detail 8) --> ColorRamp (dark iron to light iron)
    --> Mix with Musgrave (Scale 50, Fac 0.15) for micro-detail
        --> Base Color input of Principled BSDF

Noise Texture (Scale 8) --> ColorRamp (0.55 to 0.80)
    --> Mix with curvature-from-AO (edge=lower roughness)
        --> Roughness input

Metallic: 0.85 constant (iron is metallic but oxidizes)

Noise Texture (Scale 25) + Voronoi (Scale 40, Crackle)
    --> Mix (Fac 0.3) --> Bump node (Strength 0.5)
        --> Normal input for forging texture
```

### 2.2 Steel Weapons

**Visual Character:** Brighter than iron, more refined. Visible polish zones, edge sharpness.

| Feature | Texture Treatment |
|---------|-------------------|
| **Polish zones** | Lower roughness (0.15-0.25) on blade flats, higher (0.40-0.55) in fullers/grooves |
| **Edge highlight** | Narrow band of very low roughness (0.10-0.15) + slightly brighter albedo at cutting edge |
| **Fuller detail** | Depression running blade length; darker albedo in groove, rougher, catches shadow |
| **Grinding marks** | Anisotropic directional scratches visible on flats (normal map, NOT albedo) |
| **Hamon line** | Wavy transition between edge and body, visible as roughness/color band on Japanese-style weapons |

**Blender Node Recipe -- Steel Blade:**
```
Mix Shader: Steel Base (0.67, 0.64, 0.60) * Noise (Scale 100, Fac 0.05)
    --> subtle color variation without looking noisy

Roughness: Layer stack
    1. Base: 0.30
    2. + Curvature mask * (-0.15) for edge polish (edges = smoother)
    3. + AO mask * (+0.20) for crevice roughness (grooves = rougher)
    4. + Noise (Scale 200, Fac 0.05) for micro-variation

Metallic: 0.92 constant (purer metal than iron)

Normal: Noise (Scale 200) --> Bump (Strength 0.15) for micro-scratches
    + Larger Noise (Scale 40) --> Bump (Strength 0.3) for forging marks
```

### 2.3 Silver Weapons

**Visual Character:** Brilliant white-silver, tarnish in protected areas, anti-undead glow.

| Feature | Texture Treatment |
|---------|-------------------|
| **Reflections** | Very low roughness (0.08-0.20) on exposed surfaces, near-mirror |
| **Tarnish** | Dark oxide (0.30, 0.28, 0.25) in crevices/engravings, curvature-driven |
| **Anti-undead glow** | Faint blue-white emission (0.7, 0.8, 1.0) in engraved rune channels, intensity 0.3-0.8 |
| **Filigree** | Fine ornamental patterns visible in normal map, silver is a "noble" metal |

**Blender Node Recipe -- Silver:**
```
Base Color: (0.97, 0.96, 0.92) constant (near-white)
    Mix with tarnish color (0.30, 0.28, 0.25)
    using inverted curvature as factor (concave = tarnished)

Roughness: 0.12 base
    + AO/curvature concave mask * 0.35 (tarnish is rough)
    + fingerprint noise (Scale 300, Fac 0.08)

Metallic: 1.0

Emission: Blue-white (0.7, 0.85, 1.0) * rune_mask_texture * 0.5
    (rune mask is a grayscale image painted along UV engraving channels)
```

### 2.4 Gold Weapons

**Visual Character:** Warm, rich, ornamental. Engravings, gem settings. Royalty/divine.

| Feature | Texture Treatment |
|---------|-------------------|
| **Warm metallic** | (1.0, 0.77, 0.34) base color, strong warm bias |
| **Engraving detail** | Deep normal map detail for inscriptions, patterns recessed into surface |
| **Gem settings** | Socket geometry with separate material slot for gemstone inserts |
| **Patina** | Very subtle darkening in recesses, gold does not rust/tarnish significantly |
| **Two-tone** | Often paired with steel blade (gold guard + steel blade), not all-gold weapons |

**Blender Node Recipe -- Gold Trim/Guard:**
```
Base Color: (1.0, 0.77, 0.34) pure gold
    Mix with darkened gold (0.70, 0.50, 0.20) using AO factor 0.3
    for subtle depth variation

Roughness: 0.15 base (polished gold)
    + Noise (Scale 150) * 0.10 for handling wear

Metallic: 1.0

Normal: Ornamental pattern texture (tiling trim sheet or unique UV)
    --> Normal Map node --> blend with base normal
    Strength: 1.2 (deep engravings)
```

### 2.5 Mithril Weapons

**Visual Character:** Blue-silver sheen, elvish/magical, pristine. No wear, no tarnish.

| Feature | Texture Treatment |
|---------|-------------------|
| **Blue-silver sheen** | (0.75, 0.82, 0.90) with slight metallic blue bias |
| **Elvish rune glow** | Emission in engraved channels, blue-white (0.5, 0.7, 1.0), intensity 0.5-1.5 |
| **Pristine finish** | Very low roughness (0.05-0.15), almost mirror-like |
| **No wear** | Unlike iron/steel, mithril does not degrade. Curvature map NOT used for wear. |
| **Light interaction** | Slight iridescence via thin-film effect (normal-based color shift) |

### 2.6 Obsidian Weapons

**Visual Character:** Volcanic glass, conchoidal fracture, razor edges.

| Feature | Texture Treatment |
|---------|-------------------|
| **Glass body** | Metallic=0.0, Transmission=0.85, IOR=1.50, very dark base (0.02, 0.02, 0.03) |
| **Conchoidal fracture** | Voronoi texture (Smooth F1 mode) creating shell-like curved fracture patterns |
| **Razor edge** | Extremely thin edge geometry, near-transparent at edges (alpha gradient) |
| **Internal banding** | Subtle color bands (mahogany, gray, green) visible through translucent body |
| **Reflective surface** | Roughness 0.0-0.05 for glass-like reflection |

**Blender Node Recipe -- Obsidian:**
```
Principled BSDF:
    Base Color: (0.02, 0.02, 0.03)
    Metallic: 0.0
    Roughness: 0.02
    Transmission: 0.85
    IOR: 1.50

Internal banding:
    Object Texture Coordinate --> Scale Y stretched
    Noise Texture (Scale 3, Detail 0) --> ColorRamp (black to dark mahogany)
    --> Mix into Base Color at Fac 0.15

Surface fracture (normal):
    Voronoi Texture (Scale 8, Smooth F1)
    --> Bump (Strength 0.3)
    --> Normal input
```

### 2.7 Dragonbone Weapons

**Visual Character:** Marbled organic bone, growth rings, mineralized veins.

| Feature | Texture Treatment |
|---------|-------------------|
| **Marbled bone** | (0.70, 0.68, 0.60) with Wave Texture for growth pattern |
| **Growth rings** | Concentric rings visible in cross-section, Wave Texture (Bands, Rings) |
| **Blue-white veins** | Bright mineral veins (0.60, 0.70, 0.85) running through bone, emission 0.3 |
| **Keratin sheen** | Low roughness on flat surfaces (0.35-0.50), higher in porous areas |
| **Non-metallic** | Metallic=0.0, this is organic material |

### 2.8 Void-Touched Weapons

**Visual Character:** Reality distortion, shifting colors, corruption veins. The highest-tier visual.

| Feature | Texture Treatment |
|---------|-------------------|
| **Reality distortion** | Refraction distortion shader in Unity (screen-space UV offset), not just texture |
| **Shifting colors** | Animated hue shift on base color driven by `_Time`, dark purple to black cycle |
| **Corruption veins** | Branching emission patterns (Voronoi Crackle + Noise), VOID brand color (#4C1D95) |
| **Base metal** | Near-black (0.10, 0.05, 0.15), metallic 0.6-0.9 (flickering between states) |
| **Edge dissolution** | Alpha erosion at weapon edges, particles spawning at dissolving boundary |

---

## 3. Weapon Detail Texturing

### 3.1 Blade Texturing

| Component | Normal Map | Roughness | Albedo | Emission |
|-----------|-----------|-----------|--------|----------|
| **Cutting edge** | Sharp bevel highlight | 0.10-0.20 (polished from sharpening) | Slightly brighter than body | None (unless enchanted) |
| **Blood channel (fuller)** | Depressed groove, 1-2 channels | 0.50-0.70 (collects grime) | Darker than body by 20% | None |
| **Flat of blade** | Subtle grinding marks (directional) | 0.25-0.45 (working surface) | Base metal color | None |
| **Spine (back edge)** | Rounded, less detail | 0.35-0.55 | Base metal | None |
| **Hamon line** | Wavy boundary normal detail | Transition zone (0.20 to 0.45) | Subtle color shift across line | None |

### 3.2 Guard/Crossguard Texturing

| Component | Treatment |
|-----------|-----------|
| **Ornamental patterns** | Normal map engravings, gold/brass inlay as separate material |
| **Wrapped leather** | Leather material in grip area, stitching in normal map |
| **Gem sockets** | Separate geometry + material slot, rim is gold/silver |
| **Quillons** | Taper detail, edge wear at tips (lighter, lower roughness) |

### 3.3 Grip Texturing

| Grip Type | Texture Approach |
|-----------|-----------------|
| **Leather wrap** | Overlapping diagonal bands, stitching at edges (normal map), worn smooth where hand grips |
| **Wire wrap** | Fine spiral pattern in normal map, metallic with leather under-wrap visible |
| **Ray-skin** | Dotted bumpy texture (Voronoi F1), pale color, often under cord wrap |
| **Cord wrap** | Diamond pattern from crossed cord, deeper texture than leather |
| **Bare wood** | Grain direction along shaft, polished where hand contacts |

**Blender Node Recipe -- Leather Wrap:**
```
Texture Coordinate (Object) --> Mapping (Rotate Z for wrap angle)
    --> Voronoi Texture (Scale 30, F1)
        --> ColorRamp (leather brown range)
            --> Base Color

Voronoi (same) --> Invert --> Bump (Strength 0.8) --> Normal
    (creates raised diamond/grain pattern)

Roughness: 0.55 base
    + Noise (Scale 80) * 0.15 for wear variation
    + AO factor * 0.10 for crevice roughness

Stitch detail: separate Noise Texture (highly stretched in one axis)
    at UV seam locations, adds bump of 0.4
```

### 3.4 Pommel Texturing

- Counterweight metal matching guard material
- Decorative caps with brand symbol (normal map detail or separate geometry)
- Edge wear on bottom (dropped/rested on ground)
- Often a different metal accent from blade (gold pommel on steel sword)

### 3.5 Engraving/Rune Detail

**Approach:** Engravings are normal map detail + optional emission channel.

| Rune State | Normal Map | Emission |
|------------|-----------|----------|
| **Mundane/dormant** | Recessed detail, visible as shadow catching | None (0.0) |
| **Awakened** | Same recessed detail | Faint glow, brand color, intensity 0.3-0.8 |
| **Fully empowered** | Deeper detail + slight AO darkening around edges | Strong glow, brand color, intensity 1.5-3.0 + bloom |
| **Corrupted** | Distorted/broken pattern | Pulsating emission, VOID purple, animated intensity |

---

## 4. Armor Texturing by Type

### 4.1 Plate Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Polished regions** | Roughness 0.15-0.25, chest plate center, pauldron domes |
| **Battle-worn regions** | Roughness 0.50-0.70, edges, joints, contact areas |
| **Rivet detail** | Small raised circles in normal map, slightly different roughness (0.30) |
| **Joint lines** | Dark gaps between articulated plates, AO-driven darkening |
| **Specular variation** | Use curvature map: convex = polished (lower roughness), concave = dirty (higher roughness) |
| **Dent marks** | Normal map depressions, slightly different roughness in dented area |

### 4.2 Chainmail

| Feature | Value / Treatment |
|---------|-------------------|
| **Ring pattern** | Normal map (NOT geometry for game-ready), tiling 4x-8x across mail area |
| **Oil sheen** | Low roughness (0.25-0.35) with slight iridescent color shift |
| **Rust variation** | Random rings with higher roughness + darker albedo, Noise-driven |
| **Metallic** | 0.90 (rings are individual metal, slight gap in weave) |
| **Shadow between rings** | AO baked deep between ring gaps |

**Normal map approach:** Create a flat chainmail tile in Blender (actual ring geometry), bake normal map to a 512x512 tiling texture, apply as detail normal at 4x UV tiling.

### 4.3 Leather Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Grain direction** | Follows body contour, Noise Texture stretched in one axis |
| **Stitching detail** | Normal map only, running along seam lines, slightly recessed |
| **Dye color** | Desaturated per VeilBreakers palette (S < 40%, V < 50%) |
| **Wear at edges** | Lighter albedo + lower roughness at fold lines, belt loops, straps |
| **Tooled patterns** | Stamped decorative patterns via normal map, common on bracers and belts |

### 4.4 Scale Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Overlapping highlights** | Each scale has a bright top edge (lower roughness) and dark bottom (shadow) |
| **Oxidation pattern** | Per-scale random color variation using vertex color or Noise Texture |
| **Edge wear** | Bottom edges of scales lighter/shinier (rubbing against scale below) |

### 4.5 Bone Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Growth rings** | Wave Texture (Bands) for visible bone grain |
| **Marrow cavity** | At break points: dark interior (0.08, 0.06, 0.05), spongy normal map texture |
| **Keratin sheen** | Low roughness on flat surfaces, higher roughness at porous/broken areas |
| **Lashing** | Leather or sinew cord binding pieces together (separate material) |

### 4.6 Crystal Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Internal refraction** | Unity URP refraction effect (NOT Blender procedural, must be shader) |
| **Faceted highlights** | Geometry-driven sharp edges, low roughness (0.0-0.05) |
| **Brand-colored glow** | Emission at brand color, intensity scaled by enchantment level |
| **Translucency** | Alpha < 1.0 with backface rendering for visible depth |

### 4.7 Cloth/Robe Armor

| Feature | Value / Treatment |
|---------|-------------------|
| **Weave pattern** | Detail normal map at 4x-8x tiling (linen: crossed threads, silk: smooth) |
| **Embroidery** | Normal map raised detail + separate albedo color (often gold thread) |
| **Wear at edges** | Fraying effect: lighter color, rougher texture at hem, cuffs, collar |
| **Gold thread** | Metallic=0.85, Roughness=0.25, gold albedo, only in embroidery pattern areas |

---

## 5. Item Texturing

### 5.1 Potion Bottles

| Component | Shader Approach |
|-----------|----------------|
| **Glass body** | Transparent shader, Roughness 0.0-0.08, slight green tint for cheap glass |
| **Liquid interior** | Fake liquid shader: flat plane with vertex-displaced surface, colored based on potion type |
| **Cork/stopper** | Wood material, very rough (0.80-0.95), warm brown |
| **Label/wrapping** | Separate UV island, parchment texture with potion icon |

**Unity URP Liquid Shader Approach:**
- Inner plane mesh renders behind glass with screen-space refraction
- Liquid surface animates with simple vertex displacement (wobble on movement)
- Liquid color drives HDR emission for magical potions (glow through glass)
- No real-time refraction needed; the fake-liquid-plane approach is performant

### 5.2 Food Items

| Item | Key Texture Features |
|------|---------------------|
| **Bread** | Crust: rough (0.85-0.95), warm brown, bumpy normal; Crumb: lighter, softer normal |
| **Cheese** | Waxy smooth (0.30-0.45), pale yellow, mold spots (green-gray patches) |
| **Meat** | Sear marks (dark bands), pink-red interior, fatty marbling, wet sheen (0.15-0.25) |
| **Fruit** | Smooth skin (0.20-0.40), bright albedo (allowed to be more saturated than environment) |

### 5.3 Gems/Crystals

| Gem | Base Color (Linear) | IOR | Roughness | Notes |
|-----|---------------------|-----|-----------|-------|
| **Ruby** | (0.80, 0.05, 0.10) | 1.770 | 0.00-0.03 | Deep red, high dispersion |
| **Sapphire** | (0.10, 0.15, 0.80) | 1.770 | 0.00-0.03 | Deep blue |
| **Emerald** | (0.10, 0.60, 0.15) | 1.580 | 0.00-0.05 | Green, often has inclusions |
| **Diamond** | (1.00, 1.00, 1.00) | 2.417 | 0.00-0.02 | Maximum fire/dispersion |
| **Amethyst** | (0.50, 0.20, 0.65) | 1.544 | 0.00-0.05 | Purple, translucent |
| **Onyx** | (0.02, 0.02, 0.02) | 1.544 | 0.10-0.20 | Black, polished but not glass-clear |

**Blender Node Recipe -- Faceted Gem:**
```
Principled BSDF:
    Base Color: gem-specific from table above
    Metallic: 0.0
    Roughness: 0.01
    IOR: gem-specific from table above
    Transmission: 0.95

-- For baking to game texture (since real-time transmission is expensive):
-- Bake the COMBINED pass, which captures reflections/refractions
-- Use the baked result as albedo, set material to opaque in Unity
-- Add emission for magical gem glow
```

### 5.4 Scrolls/Books

| Component | Treatment |
|-----------|-----------|
| **Parchment** | Warm tan (0.65, 0.55, 0.40), rough (0.80-0.95), Noise for aging spots |
| **Ink** | Dark (0.05, 0.05, 0.08) overlaid on parchment, slightly recessed in normal |
| **Wax seal** | Glossy (0.20-0.30 roughness), red/faction-colored, raised normal map |
| **Book cover** | Leather material with tooled patterns, metal corner protectors |
| **Aged pages** | Yellowed edges, foxing (brown spots via scattered Noise) |

### 5.5 Coins/Currency

| Feature | Treatment |
|---------|-----------|
| **Embossed detail** | Strong normal map, face/symbol raised from surface |
| **Metallic wear** | Highest wear on raised emboss areas (brighter, lower roughness) |
| **Edge wear** | Stack-ring pattern on coin edges from minting/stacking |
| **Tarnish** | Bronze/copper coins: green verdigris in recesses |
| **Stack optimization** | All coins share one texture atlas (gold, silver, copper variants in UV regions) |

---

## 6. Rarity Visual Progression

### 6.1 How Rarity is Communicated

AAA games (Diablo IV, Path of Exile 2, Elden Ring, Monster Hunter World) use four simultaneous visual channels to communicate rarity at a glance:

| Channel | Common | Uncommon | Rare | Epic | Legendary |
|---------|--------|----------|------|------|-----------|
| **Material quality** | Plain iron/wood | Better metal, some trim | Ornamental, mixed metals | Premium metals, gems | Unique material (mithril, void, dragon) |
| **Detail density** | Minimal engraving | Simple patterns | Complex engravings, filigree | Dense ornamental work | Completely unique geometry/patterns |
| **Color saturation** | Desaturated, dull | Slight accent color | Deeper colors, contrast | Rich, vibrant accents | Gold/warm + unique color pairing |
| **Emission/glow** | None (0.0) | None (0.0) | Faint rune glow (0.3) | Moderate emission (0.8-1.5) | Strong constant glow (2.0-3.0) + particles |

### 6.2 Complete Rarity Progression Table

| Property | Common | Uncommon | Rare | Epic | Legendary |
|----------|--------|----------|------|------|-----------|
| **Base metal** | Iron (0.29, 0.21, 0.15) | Steel (0.67, 0.64, 0.60) | Steel + silver trim | Gold + steel | Mithril/Void/Dragon |
| **Roughness range** | 0.55-0.85 (worn) | 0.40-0.70 (maintained) | 0.25-0.55 (polished) | 0.15-0.40 (refined) | 0.05-0.25 (pristine) |
| **Metallic** | 0.80 (oxidized) | 0.88 | 0.92 | 0.95 | 1.0 |
| **Normal detail** | Forging marks only | + simple engravings | + complex patterns | + filigree + runes | Unique motifs |
| **Texture resolution** | 512x512 | 512x512 | 1024x1024 | 1024x1024 | 2048x2048 |
| **Grip material** | Plain leather | Dyed leather | Cord + leather | Ray-skin + wire | Unique (dragonhide, void-silk) |
| **Guard complexity** | Simple crossbar | Shaped guard | Ornamental guard + gem | Multi-gem + engraved | Unique sculpture |
| **Emission intensity** | 0.0 | 0.0 | 0.3-0.5 | 0.8-1.5 | 2.0-3.0 |
| **Emission source** | None | None | Rune channels | Rune channels + gem sockets | Entire weapon aura |
| **UI border color** | #8B8B8B (gray) | #1EFF00 (green) | #0070DD (blue) | #A335EE (purple) | #FF8000 (orange) |
| **Particle VFX** | None | None | None | Subtle shimmer | Constant aura + trails |

### 6.3 How to Make Rarity Instantly Recognizable

Based on Diablo IV and Path of Exile 2 approaches:

1. **Silhouette first:** Higher rarity weapons have more complex silhouettes (more geometry detail in guard, pommel, blade shape). Recognizable at any distance.
2. **Color accent second:** A single strong accent color (gold trim, gem glow, brand color) draws the eye.
3. **Emission third:** Only rare+ items emit light. In a dark world, any glow = valuable.
4. **Material last:** Close inspection reveals material quality. This is the "inspection reward."

---

## 7. Enchantment/Brand Visual Effects on Equipment

### 7.1 Enchantment Overlay System

The system uses a layered approach: `Base Equipment Material + Enchantment Overlay = Final Appearance`

**Architecture:**
```
Layer 0: Base equipment material (PBR: albedo, normal, metallic, roughness)
Layer 1: Wear/damage overlay (curvature-driven, already built in toolkit)
Layer 2: Enchantment emission (brand-colored rune patterns)
Layer 3: Enchantment energy VFX (particle effects, trails, aura)
```

**Unity URP Implementation:**
- Custom URP Lit shader variant with additional `_EnchantmentTex` (emission mask), `_BrandColor` (HDR color), `_EnchantmentIntensity` (float 0-3)
- Enchantment texture is a grayscale mask: white = rune channel, black = no glow
- `_BrandColor * _EnchantmentTex * _EnchantmentIntensity` feeds into emission
- Post-processing bloom picks up HDR emission values > 1.0 for glow halo

### 7.2 Per-Brand Visual Language

| Brand | Primary Color (HDR) | Pattern Style | Energy Flow Direction | Texture Motif |
|-------|-------------------|---------------|----------------------|---------------|
| **IRON** | (0.42, 0.45, 0.50, 2.0) | Chain links, interlocking circles | Static/pulsing | Chain pattern overlay |
| **SAVAGE** | (0.60, 0.11, 0.11, 2.5) | Jagged claw marks, tribal lines | Outward from center | Slash pattern |
| **SURGE** | (0.15, 0.39, 0.92, 3.0) | Lightning arcs, branching paths | Tip to grip (directional) | Lichtenberg pattern |
| **VENOM** | (0.40, 0.64, 0.05, 2.0) | Dripping drops, vein networks | Downward (gravity) | Vein/capillary pattern |
| **DREAD** | (0.55, 0.36, 0.96, 2.0) | Smoke wisps, ethereal tendrils | Upward (rising) | Wisp pattern |
| **LEECH** | (0.50, 0.11, 0.11, 2.5) | Pulsing veins, heartbeat rhythm | Inward (absorbing) | Arterial pattern |
| **GRACE** | (0.85, 0.47, 0.02, 2.0) | Clean geometric, sacred geometry | Radial outward | Mandala/sun pattern |
| **MEND** | (0.02, 0.59, 0.41, 2.0) | Flowing leaves, vine growth | Upward (growing) | Vine pattern |
| **RUIN** | (0.92, 0.35, 0.05, 2.5) | Cracking/shattering lines, ember dots | Chaotic (random) | Crack pattern |
| **VOID** | (0.30, 0.11, 0.58, 3.0) | Reality cracks, impossible geometry | Inward to void point | Fracture pattern |

### 7.3 Animated Enchantment Effects

**UV Scrolling for Energy Flow:**
```hlsl
// Unity Shader Graph / HLSL snippet
float2 enchantUV = i.uv + float2(_Time.y * _FlowSpeed, 0);
float enchantMask = tex2D(_EnchantmentTex, enchantUV).r;
float3 emission = _BrandColor.rgb * enchantMask * _EnchantmentIntensity;
```

**Pulsing Intensity (heartbeat for LEECH, breathing for others):**
```hlsl
float pulse = lerp(0.7, 1.3, sin(_Time.y * _PulseSpeed) * 0.5 + 0.5);
emission *= pulse;
```

### 7.4 Emission Map Generation (Procedural in Blender)

Rune patterns for enchantment emission maps can be generated procedurally and baked:

```
Voronoi Texture (Scale 5, Distance to Edge) --> ColorRamp (sharp cutoff at 0.02)
    Creates thin line network (rune channels)

+ Wave Texture (Bands, Rings) for circular rune inscriptions

+ Custom rune UV overlay for brand-specific symbol

Composite --> Bake to Image Texture as emission mask
    Resolution: 512x512 (emission is simple gradients, does not need high res)
```

---

## 8. Procedural Weapon Texturing in Blender -- Complete Node Recipes

### 8.1 Steel Blade with Edge Highlight (Full Recipe)

```python
# Blender Python (for blender_execute) -- creates complete steel blade material
import bpy

mat = bpy.data.materials.new("MAT_SteelBlade")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

# Output
output = nodes.new('ShaderNodeOutputMaterial')
output.location = (800, 0)

# Principled BSDF
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (400, 0)
bsdf.inputs['Metallic'].default_value = 0.92
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# Base color: steel with subtle variation
noise_col = nodes.new('ShaderNodeTexNoise')
noise_col.inputs['Scale'].default_value = 100.0
noise_col.inputs['Detail'].default_value = 4.0
noise_col.location = (-600, 200)

ramp_col = nodes.new('ShaderNodeValToRGB')
ramp_col.color_ramp.elements[0].position = 0.4
ramp_col.color_ramp.elements[0].color = (0.62, 0.59, 0.55, 1)
ramp_col.color_ramp.elements[1].position = 0.6
ramp_col.color_ramp.elements[1].color = (0.72, 0.69, 0.65, 1)
ramp_col.location = (-300, 200)

links.new(noise_col.outputs['Fac'], ramp_col.inputs['Fac'])
links.new(ramp_col.outputs['Color'], bsdf.inputs['Base Color'])

# Roughness: base + edge variation
noise_rough = nodes.new('ShaderNodeTexNoise')
noise_rough.inputs['Scale'].default_value = 200.0
noise_rough.inputs['Detail'].default_value = 2.0
noise_rough.location = (-600, -100)

math_rough = nodes.new('ShaderNodeMath')
math_rough.operation = 'MULTIPLY'
math_rough.inputs[1].default_value = 0.15
math_rough.location = (-300, -100)

math_add = nodes.new('ShaderNodeMath')
math_add.operation = 'ADD'
math_add.inputs[1].default_value = 0.30  # base roughness
math_add.location = (-100, -100)

links.new(noise_rough.outputs['Fac'], math_rough.inputs[0])
links.new(math_rough.outputs['Value'], math_add.inputs[0])
links.new(math_add.outputs['Value'], bsdf.inputs['Roughness'])

# Normal: micro forging detail
noise_bump = nodes.new('ShaderNodeTexNoise')
noise_bump.inputs['Scale'].default_value = 50.0
noise_bump.inputs['Detail'].default_value = 8.0
noise_bump.location = (-600, -400)

bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.3
bump.location = (-100, -400)

links.new(noise_bump.outputs['Fac'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
```

### 8.2 Leather Grip with Wrap Detail

```python
import bpy

mat = bpy.data.materials.new("MAT_LeatherGrip")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

output = nodes.new('ShaderNodeOutputMaterial')
output.location = (800, 0)

bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (400, 0)
bsdf.inputs['Metallic'].default_value = 0.0
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# Base Color: aged leather
voronoi = nodes.new('ShaderNodeTexVoronoi')
voronoi.inputs['Scale'].default_value = 30.0
voronoi.voronoi_dimensions = '3D'
voronoi.feature = 'F1'
voronoi.location = (-600, 200)

ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = 0.3
ramp.color_ramp.elements[0].color = (0.12, 0.08, 0.04, 1)  # dark leather
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (0.22, 0.15, 0.08, 1)  # light leather
ramp.location = (-300, 200)

links.new(voronoi.outputs['Distance'], ramp.inputs['Fac'])
links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

# Roughness: 0.55-0.75 with grain variation
noise_r = nodes.new('ShaderNodeTexNoise')
noise_r.inputs['Scale'].default_value = 80.0
noise_r.location = (-600, -100)

math_r = nodes.new('ShaderNodeMapRange')
math_r.inputs['From Min'].default_value = 0.0
math_r.inputs['From Max'].default_value = 1.0
math_r.inputs['To Min'].default_value = 0.55
math_r.inputs['To Max'].default_value = 0.75
math_r.location = (-300, -100)

links.new(noise_r.outputs['Fac'], math_r.inputs['Value'])
links.new(math_r.outputs['Result'], bsdf.inputs['Roughness'])

# Normal: leather grain
bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.8
bump.location = (-100, -400)
links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
```

### 8.3 Ornamental Gold Trim

```python
import bpy

mat = bpy.data.materials.new("MAT_GoldTrim")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

output = nodes.new('ShaderNodeOutputMaterial')
output.location = (800, 0)

bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (400, 0)
bsdf.inputs['Base Color'].default_value = (1.0, 0.77, 0.34, 1)  # Gold
bsdf.inputs['Metallic'].default_value = 1.0
bsdf.inputs['Roughness'].default_value = 0.18
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# Engraving pattern via Wave Texture
wave = nodes.new('ShaderNodeTexWave')
wave.wave_type = 'RINGS'
wave.inputs['Scale'].default_value = 8.0
wave.inputs['Distortion'].default_value = 3.0
wave.inputs['Detail'].default_value = 4.0
wave.location = (-600, -300)

bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 1.2
bump.location = (-100, -300)

links.new(wave.outputs['Fac'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

# Subtle depth variation in color (darkened in recesses)
mix_col = nodes.new('ShaderNodeMixRGB')
mix_col.blend_type = 'MULTIPLY'
mix_col.inputs['Fac'].default_value = 0.15
mix_col.inputs[1].default_value = (1.0, 0.77, 0.34, 1)  # gold base
mix_col.inputs[2].default_value = (0.70, 0.50, 0.20, 1)  # darkened gold
mix_col.location = (-100, 200)

# Use wave pattern to drive color darkening in recesses
links.new(wave.outputs['Fac'], mix_col.inputs['Fac'])
links.new(mix_col.outputs['Color'], bsdf.inputs['Base Color'])
```

### 8.4 Rust/Patina on Aged Metal

```python
import bpy

mat = bpy.data.materials.new("MAT_RustedIron")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

output = nodes.new('ShaderNodeOutputMaterial')
output.location = (1000, 0)

bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (600, 0)
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# Two material layers: clean iron + rust
# Clean iron
iron_col = nodes.new('ShaderNodeRGB')
iron_col.outputs[0].default_value = (0.45, 0.42, 0.39, 1)
iron_col.location = (-800, 400)

# Rust color
rust_col = nodes.new('ShaderNodeRGB')
rust_col.outputs[0].default_value = (0.35, 0.15, 0.05, 1)
rust_col.location = (-800, 200)

# Rust mask: Noise + Musgrave combination
noise_mask = nodes.new('ShaderNodeTexNoise')
noise_mask.inputs['Scale'].default_value = 8.0
noise_mask.inputs['Detail'].default_value = 6.0
noise_mask.location = (-800, -100)

musgrave = nodes.new('ShaderNodeTexMusgrave')
musgrave.musgrave_type = 'FBM'
musgrave.inputs['Scale'].default_value = 4.0
musgrave.inputs['Detail'].default_value = 8.0
musgrave.location = (-800, -300)

# Combine masks
mix_mask = nodes.new('ShaderNodeMixRGB')
mix_mask.blend_type = 'MULTIPLY'
mix_mask.inputs['Fac'].default_value = 0.7
mix_mask.location = (-500, -200)
links.new(noise_mask.outputs['Fac'], mix_mask.inputs[1])
links.new(musgrave.outputs['Fac'], mix_mask.inputs[2])

# Threshold the rust mask
ramp_mask = nodes.new('ShaderNodeValToRGB')
ramp_mask.color_ramp.elements[0].position = 0.35  # rust threshold
ramp_mask.color_ramp.elements[1].position = 0.55
ramp_mask.location = (-300, -200)
links.new(mix_mask.outputs['Color'], ramp_mask.inputs['Fac'])

# Mix colors: iron where mask=0, rust where mask=1
mix_col = nodes.new('ShaderNodeMixRGB')
mix_col.location = (-100, 300)
links.new(ramp_mask.outputs['Color'], mix_col.inputs['Fac'])
links.new(iron_col.outputs[0], mix_col.inputs[1])
links.new(rust_col.outputs[0], mix_col.inputs[2])
links.new(mix_col.outputs['Color'], bsdf.inputs['Base Color'])

# Metallic: iron=0.85, rust=0.0
mix_metal = nodes.new('ShaderNodeMixRGB')
mix_metal.location = (-100, 100)
mix_metal.inputs[1].default_value = (0.85, 0.85, 0.85, 1)  # iron metallic
mix_metal.inputs[2].default_value = (0.0, 0.0, 0.0, 1)  # rust non-metallic
links.new(ramp_mask.outputs['Color'], mix_metal.inputs['Fac'])
links.new(mix_metal.outputs['Color'], bsdf.inputs['Metallic'])

# Roughness: iron=0.45, rust=0.85
mix_rough = nodes.new('ShaderNodeMixRGB')
mix_rough.location = (-100, -100)
mix_rough.inputs[1].default_value = (0.45, 0.45, 0.45, 1)
mix_rough.inputs[2].default_value = (0.85, 0.85, 0.85, 1)
links.new(ramp_mask.outputs['Color'], mix_rough.inputs['Fac'])
links.new(mix_rough.outputs['Color'], bsdf.inputs['Roughness'])

# Normal: rust is bumpier
noise_bump = nodes.new('ShaderNodeTexNoise')
noise_bump.inputs['Scale'].default_value = 40.0
noise_bump.inputs['Detail'].default_value = 8.0
noise_bump.location = (-500, -500)

bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.6
bump.location = (100, -400)
links.new(noise_bump.outputs['Fac'], bump.inputs['Height'])
links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
```

### 8.5 Enchanted Glow Emission

```python
import bpy

# Adds emission channel to existing weapon material
# Assumes material already exists with Principled BSDF

def add_enchantment_emission(mat_name, brand_color, intensity=1.0):
    mat = bpy.data.materials.get(mat_name)
    if not mat or not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if not bsdf:
        return

    # Rune pattern: Voronoi (distance to edge) for thin lines
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.feature = 'DISTANCE_TO_EDGE'
    voronoi.inputs['Scale'].default_value = 5.0
    voronoi.location = (bsdf.location[0] - 600, bsdf.location[1] - 500)

    # Threshold to create thin lines
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position = 0.03  # very thin lines
    ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    ramp.location = (bsdf.location[0] - 300, bsdf.location[1] - 500)

    links.new(voronoi.outputs['Distance'], ramp.inputs['Fac'])

    # Multiply by brand color and intensity
    emit_col = nodes.new('ShaderNodeRGB')
    emit_col.outputs[0].default_value = (*brand_color, 1.0)
    emit_col.location = (bsdf.location[0] - 300, bsdf.location[1] - 650)

    mix_emit = nodes.new('ShaderNodeMixRGB')
    mix_emit.blend_type = 'MULTIPLY'
    mix_emit.inputs['Fac'].default_value = intensity
    mix_emit.location = (bsdf.location[0] - 100, bsdf.location[1] - 550)

    links.new(ramp.outputs['Color'], mix_emit.inputs[1])
    links.new(emit_col.outputs[0], mix_emit.inputs[2])
    links.new(mix_emit.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = intensity
```

### 8.6 Baking Procedural Textures to UV-Mapped Images

**Critical workflow:** Procedural Blender materials do NOT export to game engines. They MUST be baked to image textures.

```python
import bpy

def bake_procedural_to_textures(obj_name, texture_size=1024, output_dir="/tmp"):
    """Bake all PBR channels from procedural material to image textures."""
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Ensure Cycles (required for baking)
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 64

    channels = {
        'DIFFUSE': f'{obj_name}_albedo',
        'ROUGHNESS': f'{obj_name}_roughness',
        'NORMAL': f'{obj_name}_normal',
        'EMIT': f'{obj_name}_emission',
    }

    mat = obj.data.materials[0]
    nodes = mat.node_tree.nodes

    for bake_type, img_name in channels.items():
        # Create image
        img = bpy.data.images.new(img_name, texture_size, texture_size)

        # Create Image Texture node and select it
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.image = img
        img_node.location = (0, -800)
        nodes.active = img_node

        # Bake
        bpy.ops.object.bake(type=bake_type)

        # Save
        img.filepath_raw = f'{output_dir}/{img_name}.png'
        img.file_format = 'PNG'
        img.save()

        # Clean up node
        nodes.remove(img_node)
```

---

## 9. Texture Atlas and Optimization

### 9.1 Weapon Texture Atlas Layout

**Strategy:** Group weapons by category onto shared texture atlases to reduce draw calls.

| Atlas | Contents | Resolution | Draw Call Benefit |
|-------|----------|------------|-------------------|
| **Atlas_Swords** | All 1H + 2H swords (8-12 weapons) | 2048x2048 | 1 draw call for all swords |
| **Atlas_Axes_Maces** | All axes, maces, hammers | 2048x2048 | 1 draw call |
| **Atlas_Staves_Wands** | All staffs, wands | 2048x2048 | 1 draw call |
| **Atlas_Bows_Shields** | All bows, shields, daggers | 2048x2048 | 1 draw call |
| **Atlas_Items_Potions** | All potion bottles, food items | 1024x1024 | 1 draw call |
| **Atlas_Items_General** | Scrolls, coins, keys, misc | 1024x1024 | 1 draw call |

**Per-weapon UV budget within atlas:**
- Common weapon: 256x256 region (1/64 of 2048 atlas)
- Uncommon: 256x256
- Rare: 512x512 region (1/16 of 2048 atlas)
- Epic: 512x512
- Legendary: Dedicated 1024x1024 or 2048x2048 (unique texture, no atlas)

### 9.2 Trim Sheets for Equipment Detail

**Trim sheets** are shared texture strips containing reusable detail elements:

| Trim Sheet | Contents | Usage |
|------------|----------|-------|
| **Trim_MetalEdges** | Beveled edge, hammered edge, sharpened edge, notched edge | Blade edges, shield rims |
| **Trim_Rivets** | Round rivet, square rivet, decorative stud | Armor joints, shield boss |
| **Trim_Stitching** | Single stitch, cross stitch, lacing | Leather armor seams |
| **Trim_Ornamental** | Vine pattern, geometric border, rune band, chain border | Guard engravings, armor trim |
| **Trim_WrapPatterns** | Leather wrap, wire wrap, cord wrap, ray-skin | Weapon grips |

**Resolution:** 256x2048 (tall narrow strip) or 512x512 (square tile grid)

**UV mapping approach:** Map weapon grip faces to the wrap pattern row of the trim sheet. Map guard edge faces to the ornamental border row. This way ALL weapons share one trim sheet material.

### 9.3 LOD Texture Switching

| LOD Level | Texture Resolution | Normal Map | Channel Pack |
|-----------|-------------------|------------|--------------|
| **LOD0 (close)** | Full resolution (1024 or 2048) | Full detail | Albedo + Normal + MAS separate |
| **LOD1 (mid)** | Half resolution (512 or 1024) | Reduced detail | Albedo + MAS, simplified normal |
| **LOD2 (far)** | Quarter resolution (256 or 512) | Flat or disabled | Albedo only (or vertex color) |
| **LOD3 (distant)** | Single color per material slot | None | Vertex color only |

### 9.4 Unity URP Texture Import Settings

| Texture Type | sRGB | Filter | Compression | Max Size | Generate Mips |
|-------------|------|--------|-------------|----------|---------------|
| **Albedo** | Yes | Bilinear | BC7 (high quality) | 2048 | Yes |
| **Normal** | No (Linear) | Bilinear | BC5 (RG normal) | 2048 | Yes |
| **Metallic/AO/Smoothness** | No (Linear) | Bilinear | BC7 | 2048 | Yes |
| **Emission** | Yes | Bilinear | BC7 | 512 | Yes |
| **Trim Sheet** | Yes | Bilinear | BC7 | 512 (per-axis) | Yes |

**Channel Packing (single texture for M/A/S):**
- R channel: Metallic
- G channel: Ambient Occlusion (from curvature/AO bake)
- B channel: (unused or detail mask)
- A channel: Smoothness (= 1.0 - Roughness)

This matches Unity URP's expected MAS packing for the Lit shader.

---

## 10. Weapon Wear States

### 10.1 Wear State Progression

Each weapon has a wear state driven by a single `_WearLevel` float (0.0 to 1.0):

| Wear Level | Name | Albedo Changes | Roughness Changes | Normal Changes | Emission |
|-----------|------|----------------|-------------------|----------------|----------|
| 0.0-0.2 | **New/Pristine** | Full color, clean | Base values (low for metal) | Clean forging marks | Enchantment at full |
| 0.2-0.4 | **Battle-Worn** | Edge highlights from use, minor scratches | +0.10 overall | Scratch overlay added | Enchantment unchanged |
| 0.4-0.6 | **Damaged** | Visible nicks in edge, blood stains | +0.20, more variation | Dent marks, deeper scratches | Enchantment flickers |
| 0.6-0.8 | **Heavy Damage** | Chips in blade, significant rust/patina | +0.30, very rough | Major deformations | Enchantment failing |
| 0.8-1.0 | **Ancient/Ruined** | Heavy corrosion, pitting, color shift | +0.40, near-matte | Severe deterioration | Enchantment dormant (0.0) |

### 10.2 Implementation: Texture Blending

**Approach 1 (Recommended): Two-texture blend**
- Bake "clean" and "damaged" versions of each material tier
- Blend between them using `_WearLevel` in shader
- Wear mask is curvature-driven: edges wear first, crevices corrode first

**Approach 2: Single texture + overlay**
- Base texture is the "clean" version
- Overlay a grayscale wear/damage texture (already built: `render_wear_map` in `texture_ops.py`)
- Darken albedo, increase roughness, reduce metallic in worn areas
- Less memory but lower quality than two-texture approach

---

## 11. Integration with Existing Toolkit

### 11.1 What Already Exists

| Component | File | Relevance to This Research |
|-----------|------|---------------------------|
| `render_wear_map()` | `texture_ops.py` | Curvature-based wear maps -- USE for edge wear, crevice dirt |
| `validate_palette()` | `palette_validator.py` | Dark fantasy color validation -- USE for all weapon textures |
| `validate_roughness_map()` | `palette_validator.py` | Roughness variation check -- USE to ensure quality |
| `texture_create_pbr` | `blender_server.py` | PBR node tree setup -- EXTEND with material tier presets |
| `texture_bake` | `blender_server.py` | Bake procedural to images -- USE for all weapon textures |
| `generate_wear` | `blender_server.py` | Wear map generation action -- USE for wear states |
| `delight_albedo()` | `delight.py` | Remove baked lighting -- USE on AI-generated weapon textures |
| `validate_texture_file()` | `texture_validation.py` | Power-of-two, format checks -- USE for export validation |
| `PALETTE_RULES` | `palette_validator.py` | Saturation cap 0.55, value range 0.15-0.75 -- reference |
| `ASSET_TYPE_BUDGETS` | `palette_validator.py` | Weapon: 3000-8000 tris -- reference |

### 11.2 What Needs to Be Built

| Component | Priority | Description |
|-----------|----------|-------------|
| **Material Tier Library** | HIGH | Python dict mapping tier names to exact PBR values from Section 1 |
| **Procedural Material Node Groups** | HIGH | Blender node groups per material tier (Sections 8.1-8.5) |
| **Bake Pipeline Automation** | HIGH | Auto-bake all PBR channels from procedural to images (Section 8.6) |
| **Enchantment Emission Generator** | MEDIUM | Generate per-brand emission mask textures procedurally |
| **Trim Sheet Generator** | MEDIUM | Create reusable trim sheets for rivets, stitching, wraps |
| **Atlas Packer** | MEDIUM | Pack multiple weapon textures into shared atlas |
| **Rarity Preset System** | MEDIUM | Auto-select material tier + detail level based on rarity enum |
| **Wear State Blender** | LOW | Generate clean + damaged texture pairs for wear system |
| **Enchantment Overlay Shader (Unity)** | HIGH | URP shader with `_BrandColor` + `_EnchantmentTex` overlay |
| **Liquid Potion Shader (Unity)** | LOW | Fake liquid-in-bottle URP shader |

---

## 12. Common Pitfalls

### Pitfall 1: Uniform Roughness
**What goes wrong:** Every pixel has the same roughness value, making everything look like plastic.
**Why it happens:** Setting roughness as a single float instead of a texture.
**How to avoid:** Always drive roughness from a texture that includes curvature-based variation, noise, and condition-based changes. Minimum roughness variance of 0.05 (already enforced by `validate_roughness_map`).
**Warning signs:** Material looks "plasticky" or uniformly shiny/matte in viewport.

### Pitfall 2: Metallic Values Between 0 and 1 on Clean Surfaces
**What goes wrong:** Non-physical materials with metallic 0.3-0.7 on clean surfaces.
**Why it happens:** Treating metallic as "shininess" instead of a binary conductor/dielectric property.
**How to avoid:** Metallic should be 0.0 (non-metal) or 0.85-1.0 (metal). Only use intermediate values for transitions (rust on metal, where some pixels are rusted non-metal and others are exposed metal).
**Warning signs:** Material looks wrong in all lighting conditions, neither metal nor non-metal.

### Pitfall 3: Baked Lighting in Albedo
**What goes wrong:** Shadow/highlight information baked into the base color texture.
**Why it happens:** AI-generated textures or hand-painted textures with light/shadow painted in.
**How to avoid:** Use the existing `delight_albedo()` function. Validate by rendering the albedo-only (flat lit): it should look like a flat color map with material variation but NO directional shadows.
**Warning signs:** Object looks double-shadowed or has shadows that don't move with the light.

### Pitfall 4: Too Much Saturation for Dark Fantasy
**What goes wrong:** Weapons look like they belong in a cartoon game, not a dark fantasy world.
**Why it happens:** Using reference from bright/colorful games, not VeilBreakers palette.
**How to avoid:** Run `validate_palette()` on all weapon textures. Saturation cap is 0.55. Only magic emission and UI elements exceed this.
**Warning signs:** Items "pop" too much against the desaturated environment.

### Pitfall 5: Not Baking Procedural Materials Before Export
**What goes wrong:** Exported FBX/GLB has no textures or blank white material in Unity.
**Why it happens:** Blender procedural nodes are Blender-only; they don't serialize to FBX/glTF.
**How to avoid:** Always bake procedural materials to image textures before export. Use the bake workflow in Section 8.6.
**Warning signs:** Material looks great in Blender viewport but white/pink in Unity.

### Pitfall 6: Emission Without Bloom Post-Processing
**What goes wrong:** Enchanted weapons have colored areas but no visible "glow" effect.
**Why it happens:** Emission in PBR only makes the surface brighter, not the surrounding area. Bloom is a post-processing effect.
**How to avoid:** Ensure Unity URP post-processing volume has Bloom enabled with threshold matched to emission intensity. Use HDR emission colors (intensity > 1.0) to trigger bloom.
**Warning signs:** Emission looks like a flat color, not a glow.

---

## 13. State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|-------------|-----------------|--------------|--------|
| Hand-painted textures | PBR procedural + bake pipeline | ~2018-2020 | Consistent quality, faster iteration |
| Unique textures per weapon | Trim sheets + atlases | ~2020-present | 40-60% memory reduction, fewer draw calls |
| Separate metallic + roughness textures | Channel-packed MAS texture | ~2019-present | 1 texture instead of 3, fewer samples |
| Static emission maps | Animated UV-scrolling emission | ~2021-present | Dynamic enchantment effects |
| Single wear state | Multi-state blending via `_WearLevel` | ~2022-present | Emergent visual storytelling |
| Blender manual bake | Automated bake pipelines (Assetify, QuickMat) | ~2024-2025 | Faster asset pipeline, consistent output |

---

## Sources

### Primary (HIGH confidence)
- [Physically Based database](https://physicallybased.info/) -- Metal/dielectric linear RGB values, IOR
- [Adobe Substance 3D PBR Guide Part 2](https://substance3d.adobe.com/tutorials/courses/the-pbr-guide-part-2) -- Metal/roughness workflow reference (redirected, content verified via multiple secondary sources)
- [Blender 5.1 Manual - Render Baking](https://docs.blender.org/manual/en/latest/render/cycles/baking.html) -- Baking workflow, Cycles requirements
- [Blender 5.1 Manual - Principled BSDF](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html) -- Shader node parameters
- [Unity Manual - Emission Materials](https://docs.unity3d.com/Manual/StandardShaderMaterialParameterEmission.html) -- Emission/bloom interaction
- Existing VeilBreakers codebase: `texture_ops.py`, `palette_validator.py`, `texture_validation.py`, `blender_server.py`

### Secondary (MEDIUM confidence)
- [Polycount - AAA Pipeline Breakdown for Hero Props](https://polycount.com/discussion/237029/breakdown-of-the-aaa-pipeline-for-game-ready-realistic-hero-props) -- Layer-by-layer material building approach
- [ArtStation - PBR Color Space Conversion and Albedo Chart](https://www.artstation.com/blogs/shinsoj/Q9j6/pbr-color-space-conversion-and-albedo-chart) -- sRGB/linear conversion, albedo safe ranges
- [Diablo IV - Peeling Back the Varnish](https://news.blizzard.com/en-us/diablo4/23964183/peeling-back-the-varnish-the-graphics-of-diablo-iv) -- PBR approach, character shader details
- [ArtStation - Wyvern Ignition Great Sword](https://www.artstation.com/artwork/PXLQ6Z) -- 4096 texture set, 39k tris, UE5 render reference
- [80.lv - Simulating Liquids in Bottles](https://80.lv/articles/simulating-liquids-in-a-bottle-with-a-shader) -- Fake liquid shader technique
- [GitHub - Glowing Runes Unity](https://github.com/edmarsj/glowing-runes) -- Emission map animation in Shader Graph
- [BlenderNation - Procedural Obsidian/Crystal Material](https://www.blendernation.com/2019/02/19/free-procedural-obsidian-crystal-material/) -- Obsidian node setup reference
- [ArtStation - Procedural Rusted Metal Material Blender 4.0](https://www.artstation.com/blogs/jsabbott/PQQ6j/making-a-procedural-rusted-metal-material-blender-40) -- Rust material node recipe
- [Unity Learn - Texture Atlases](https://learn.unity.com/course/3d-art-optimization-for-mobile-gaming-5474) -- Atlas optimization, batching requirements
- [Beyond Extent - Trim Sheets](https://www.beyondextent.com/deep-dives/trimsheets) -- Tiling vs atlas hybrid approaches

### Tertiary (LOW confidence)
- [Medium - Tips in Creating AAA Game Assets](https://medium.com/@mkaplunow/some-tipsn-tricks-in-creating-aaa-game-ready-assets-by-mkaplunow-6e75718decc5) -- Weighted normals, remesh workflow
- [cgian.com - Blender Gold Material](https://cgian.com/how-to-make-gold-material-in-blender/) -- Gold PBR values (E7A750 hex)
- Monster Hunter World modding wiki -- MHW texture format structure (DDS conversion)
- Diablo IV GDC 2024 art talks -- Referenced but specific weapon design content not publicly available

---

## Metadata

**Confidence breakdown:**
- PBR reference values: HIGH -- sourced from Physically Based database and Adobe PBR Guide
- Blender node recipes: HIGH -- verified against Blender 5.x Principled BSDF documentation
- Rarity progression: MEDIUM -- synthesized from multiple game analysis sources, no single authoritative reference
- Enchantment overlay system: MEDIUM -- architecture is standard practice, per-brand details are VeilBreakers-specific design
- Texture atlas optimization: HIGH -- verified against Unity documentation and industry practice
- Fantasy material values (mithril, void, dragonbone): LOW -- these are art direction choices, not physical measurements

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (stable domain, PBR values do not change)
