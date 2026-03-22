# AAA Character/Creature Texturing Pipeline Research

**Researched:** 2026-03-22
**Domain:** PBR Texturing, Procedural Materials, Skin/Creature/Equipment Texturing, Blender-to-Unity URP Pipeline
**Confidence:** HIGH (cross-verified with Blender 4.0+ official docs, Polycount standards, PBR reference databases, AAA production breakdowns)

---

## Summary

This document covers the complete texturing pipeline for characters, NPCs, monsters, and equipment in a dark fantasy action RPG targeting AAA visual quality. The pipeline starts with procedural material creation in Blender using the Principled BSDF node (Blender 4.0+ naming conventions), bakes procedural textures to image maps for game engine export, and defines PBR value ranges for every material type encountered in VeilBreakers.

The existing toolkit has a solid foundation: `blender_texture` action=`create_pbr` builds a 5-channel PBR node tree (albedo, metallic, roughness, normal, AO), `delight.py` removes baked-in lighting from AI textures, `palette_validator.py` enforces dark fantasy color rules, and `texture_ops.py` handles UV masking, seam blending, wear maps, and tileability. What is missing is the **procedural material generation layer** -- the ability to create convincing skin, scales, metal, leather, fabric, bone, and corruption materials entirely from Blender shader nodes, then bake them to exportable image textures.

**Primary recommendation:** Implement a material template library of ~25 procedural Blender shader node recipes (keyed by material archetype), each producing all PBR channels via procedural nodes, with a one-command bake-to-images pipeline that outputs game-ready textures at the correct resolution for the asset type.

---

## 1. Skin Texturing

### 1.1 Principled BSDF Configuration for Skin (Blender 4.0+)

The Principled BSDF in Blender 4.0+ uses the following naming (already handled by `BSDF_INPUT_MAP` in `texture.py`):

| Parameter | Skin Value | Notes |
|-----------|-----------|-------|
| Base Color | Albedo texture or procedural | sRGB colorspace |
| Subsurface Weight | 1.0 | Fully SSS (not 0.1-0.2 -- the old approach. In 4.0+ set to 1.0 and control with Scale) |
| Subsurface Scale | 0.005-0.02 | Controls actual scatter distance. 0.01 is good default for game-scale characters |
| Subsurface Radius | (1.0, 0.2, 0.1) | Default RGB scatter ratio. Red scatters farthest, blue least -- mimics blood under skin |
| Subsurface IOR | 1.4 | Skin IOR (lower than default 1.45) |
| Roughness | 0.35-0.65 | Zone-dependent (see Section 1.2) |
| Specular IOR Level | 0.5 | Default is correct for skin |
| Metallic | 0.0 | Skin is never metallic |
| Normal | Normal map texture | Macro surface (wrinkles, folds) |
| Coat Weight | 0.0-0.15 | Slight coat simulates skin's oily sheen layer |

**SSS Color/Radius by Skin Tone (Dark Fantasy Context):**

| Skin Type | Base Color (linear RGB) | SSS Scale | Radius Multiplier | Notes |
|-----------|------------------------|-----------|-------------------|-------|
| Pale/Undead | (0.55, 0.45, 0.40) | 0.008 | (1.0, 0.15, 0.08) | Reduced scatter -- dead skin looks waxy |
| Fair human | (0.72, 0.56, 0.45) | 0.012 | (1.0, 0.20, 0.10) | Standard caucasian skin scatter |
| Medium human | (0.55, 0.38, 0.28) | 0.015 | (1.0, 0.25, 0.12) | Slightly deeper scatter |
| Dark human | (0.35, 0.22, 0.15) | 0.018 | (1.0, 0.30, 0.15) | Deeper scatter, richer red component |
| Corrupted | (0.40, 0.30, 0.35) | 0.006 | (1.0, 0.10, 0.20) | Blue channel higher -- unnatural purplish scatter |
| Demonic/Void | (0.25, 0.15, 0.20) | 0.004 | (0.8, 0.10, 0.30) | Inverted scatter profile -- blue > red |

### 1.2 Zone-Based Roughness Variation

Skin roughness is NOT uniform. Zone-based roughness is the single biggest factor separating amateur from professional skin textures.

| Facial Zone | Roughness | Reason |
|------------|-----------|--------|
| Forehead (T-zone) | 0.30-0.40 | Oily, more specular |
| Nose bridge | 0.30-0.38 | Oily, high sebum production |
| Cheeks | 0.50-0.60 | Drier, more matte |
| Chin | 0.40-0.50 | Moderate oil |
| Ears | 0.55-0.65 | Dry cartilage skin |
| Lips | 0.25-0.35 | Wet, glossy (lower roughness) |
| Neck | 0.50-0.60 | Similar to cheeks |
| Eyelids | 0.35-0.45 | Thin, slightly oily |

**Body zone roughness:**

| Body Zone | Roughness | Notes |
|-----------|-----------|-------|
| Palms/Soles | 0.70-0.85 | Thick callused skin |
| Arms/Legs | 0.50-0.65 | General body skin |
| Torso | 0.45-0.55 | Moderate |
| Joints (elbows/knees) | 0.65-0.80 | Rough, dry, darker |

### 1.3 Procedural Skin Pore Detail

**Node Recipe -- Procedural Skin Pores (micro-detail bump):**

```
Texture Coordinate (Object)
  -> Mapping (Scale: 80, 80, 80)
    -> Noise Texture (Scale: 12.0, Detail: 8.0, Roughness: 0.65, Distortion: 0.3)
      -> ColorRamp (B-Spline: Black at 0.42, White at 0.58)
        -> Bump (Strength: 0.15, Distance: 0.001)
          -> Principled BSDF Normal input (via Normal Map node if needed)
```

**Node Recipe -- Macro skin wrinkles overlay:**

```
Texture Coordinate (Object)
  -> Mapping (Scale: 5, 5, 5)
    -> Voronoi Texture (Feature: F1, Distance: Euclidean, Scale: 8.0)
      -> ColorRamp (B-Spline: Black at 0.0, White at 0.15)
        -> Bump (Strength: 0.08, Distance: 0.002)
          -> Mix with pore bump via Bump node chain
```

Combine both bumps by chaining: Pore Bump -> Normal output feeds into Wrinkle Bump -> Normal input feeds into BSDF Normal input.

### 1.4 Scarred, Diseased, Corrupted, and Undead Skin

**Scar Tissue:**
- Roughness: 0.70-0.85 (scarred skin is much rougher)
- Color: Slightly lighter and pinker than surrounding skin (+0.1 R, +0.05 G)
- Normal: Flattened/smooth compared to surrounding pore detail
- SSS: Reduced scale (0.004) -- scar tissue is less translucent

**Corruption/Void-Touched:**
- Use vertex color painting to create corruption mask (R channel = corruption intensity)
- Mix between clean skin and corrupted skin materials using vertex color as factor
- Corrupted albedo: desaturated base + dark vein pattern overlay
- Vein pattern: Voronoi F2 - F1 distance, thin lines radiating from corruption center
- Emission: Low-intensity glow in vein patterns (Emission Strength: 0.3-0.8, Color: brand-specific)
- Roughness: Higher in corrupted areas (0.6-0.8) with wet/glossy patches at veins (0.15-0.25)

**Vein Pattern Recipe:**
```
Texture Coordinate (Object)
  -> Mapping (Scale: 15, 15, 15)
    -> Voronoi Texture (Feature: Distance to Edge, Scale: 5.0)
      -> ColorRamp (Sharp: Black at 0.0, White at 0.04)
        -> Multiply with corruption mask from Vertex Color
          -> Mix into Base Color (dark purple/black veins)
          -> Also drive Emission Color (brand-specific glow)
```

**Undead/Decomposing:**
- Base color: desaturated, shifted toward gray-green (H:80-120, S:10-25, V:25-45)
- Patches of exposed muscle: redder (H:0-15, S:40-60, V:20-35)
- Bone exposure: Use a second Noise texture to create holes in flesh revealing bone beneath
- SSS: Very low (Scale: 0.002-0.004) -- dead tissue barely scatters
- Roughness: High and varied (0.6-0.9) with wet decomposition patches (0.15-0.25)

---

## 2. Monster/Creature Surface Texturing

### 2.1 Scales (Reptilian, Dragon, Fish)

**Procedural Scale Pattern Recipe:**

```
Texture Coordinate (Object)
  -> Mapping (Scale: varies by creature size)
    -> Voronoi Texture (Feature: F1, Distance: Euclidean, Scale: 15-30)
      -> ColorRamp (Constant: Black at 0.0, Mid-gray at 0.35, White at 0.5)

PARALLEL:
  Same Texture Coordinate -> Same Mapping
    -> Voronoi Texture (Feature: Distance to Edge, Scale: same)
      -> ColorRamp (Sharp: White at 0.0, Black at 0.08)
        -> This creates the scale border lines

COMBINE:
  Scale body (F1 output) -> Mix Color (Multiply) with border lines
    -> Feed into Base Color via ColorRamp for final color mapping

  Scale body -> Bump (Strength: 0.3-0.5, Distance: 0.005)
    -> Normal input

  Border lines inverted -> Roughness variation
    (scale centers: 0.4-0.5, borders: 0.6-0.7)
```

**Scale PBR Values:**

| Scale Type | Base Color (linear) | Roughness Center/Edge | Metallic | SSS | Notes |
|-----------|---------------------|----------------------|----------|-----|-------|
| Dragon (dark) | (0.08, 0.12, 0.06) | 0.35 / 0.65 | 0.0-0.1 | Scale 0.003 | Large scales, slight iridescence via Coat |
| Dragon (belly) | (0.18, 0.15, 0.10) | 0.45 / 0.55 | 0.0 | Scale 0.008 | Softer, more translucent underbelly |
| Serpent | (0.10, 0.15, 0.08) | 0.25 / 0.50 | 0.0-0.05 | Scale 0.004 | Smooth, glossy scales |
| Fish | (0.15, 0.20, 0.25) | 0.15 / 0.40 | 0.2-0.4 | Scale 0.005 | Wet, metallic sheen |
| Lizard | (0.12, 0.10, 0.07) | 0.50 / 0.70 | 0.0 | Scale 0.003 | Matte, rough, smaller scales |

**Scale Iridescence (dragons, fish):** Use Coat Weight 0.3-0.6 with Coat Tint set to a color shifted from base. Layer Thin Film interference is not directly in Principled BSDF, but approximate with a Facing-based (Layer Weight -> Facing) color ramp driving Coat Tint from cool-blue to warm-gold.

### 2.2 Chitin/Carapace (Insects, Arachnids)

**Procedural Chitin Recipe:**

```
BASE LAYER (smooth hard shell):
  Principled BSDF:
    Base Color: dark brown-black (0.05, 0.03, 0.02)
    Roughness: 0.15-0.30 (chitin is glossy)
    Metallic: 0.0
    Coat Weight: 0.4-0.7 (hard clear coat)
    Coat Roughness: 0.05-0.15
    Coat Tint: Slight amber (1.0, 0.9, 0.7)
    Specular IOR Level: 0.6 (higher than default -- chitin is very reflective)

SEGMENTATION PATTERN:
  Voronoi (Feature: F1, Scale: 3-8, Randomness: 0.3)
    -> Creates large plate segments

  Voronoi (Feature: Distance to Edge, same scale)
    -> ColorRamp (Sharp: White at 0.0, Black at 0.05)
      -> Creates segment border grooves
      -> Feed into Roughness mixer (borders rougher: 0.5-0.7)
      -> Feed into Bump (Strength: 0.4) for groove depth

TEXTURE OVERLAY (fine chitin texture):
  Noise Texture (Scale: 40, Detail: 6)
    -> ColorRamp -> Bump (Strength: 0.05) for surface micro-texture
```

**Beetle Iridescence:** For iridescent chitin (beetle-like), use Layer Weight (Facing) -> ColorRamp with rainbow gradient -> Mix into Coat Tint. This creates view-angle-dependent color shifting.

### 2.3 Fur/Hair Base Skin

For creatures with fur cards, the skin beneath needs texturing:

| Property | Value | Notes |
|----------|-------|-------|
| Base Color | Slightly darker than fur color | Skin visible between cards |
| Roughness | 0.6-0.8 | Matte skin under fur |
| SSS Scale | 0.005-0.010 | Subtle scatter at thin areas |
| Normal | Gentle bumps only | Hair follicle bumps via Noise (Scale: 50, Strength: 0.05) |

**Hair card alpha texture:** Needs gradient from opaque root to transparent tip. Generate procedurally with Wave Texture (Bands, Direction: Y) -> ColorRamp (Black at 0.0, White at 0.3) -> Alpha output.

### 2.4 Membrane/Wing Texturing

**Wing Membrane Recipe:**

```
Principled BSDF:
  Base Color: (0.25, 0.15, 0.12) -- dark leathery membrane
  Roughness: 0.55-0.70
  SSS Scale: 0.02-0.05 (high! membranes are very translucent)
  SSS Radius: (1.0, 0.3, 0.1) -- blood-rich tissue scatters red deeply
  Transmission Weight: 0.2-0.4 -- some light passes through

VEIN PATTERN:
  Voronoi (Feature: Distance to Edge, Scale: 3-5)
    -> ColorRamp (Sharp: White 0.0, Black 0.03)
      -> Multiply with gradient (thicker veins at base, thinner at edge)
      -> Darken Base Color where veins are (veins are darker, more opaque)
      -> Reduce SSS Scale at veins (veins block scatter)
      -> Increase roughness at veins (0.65 vs 0.55 for membrane)

EDGE WEAR:
  Use Geometry node -> Pointiness
    -> ColorRamp (isolate high curvature = edges)
      -> Mix in tattered/torn edge color (darker, higher roughness)
      -> Reduce Alpha at extreme edges for torn wing effect
```

### 2.5 Bone/Horn/Claw Texturing

**Procedural Bone Recipe:**

```
BASE:
  Principled BSDF:
    Base Color: (0.55, 0.50, 0.40) -- warm ivory
    Roughness: 0.65-0.80
    Metallic: 0.0
    SSS Scale: 0.005 -- subtle translucency
    SSS Radius: (1.0, 0.6, 0.3) -- warmer scatter than skin

GROWTH RING PATTERN (horns, claws):
  Wave Texture (Type: Bands, Bands Direction: Y, Scale: 3.0, Distortion: 2.0)
    -> ColorRamp (4 stops alternating light/dark bone colors)
      -> Mix with base color (Factor: 0.3-0.5)
      -> Also drives roughness variation (darker rings rougher: +0.1)

SURFACE TEXTURE:
  Noise Texture (Scale: 25, Detail: 8, Roughness: 0.7)
    -> Bump (Strength: 0.15)
      -> Fine surface grain

TIP WEAR (claws, horns):
  Geometry node -> Pointiness
    -> ColorRamp (convex edges only)
      -> Mix to darker, smoother material (worn bone tip)
      -> Roughness: 0.40-0.50 (polished from use)
```

**Keratin (horn/claw) PBR Values:**

| Property | Horn | Claw | Tusk | Antler |
|----------|------|------|------|--------|
| Base Color | (0.45, 0.38, 0.28) | (0.30, 0.25, 0.18) | (0.60, 0.55, 0.42) | (0.50, 0.45, 0.35) |
| Roughness | 0.55-0.75 | 0.40-0.60 | 0.50-0.70 | 0.65-0.85 |
| SSS Scale | 0.003 | 0.002 | 0.006 | 0.004 |
| Coat Weight | 0.2 | 0.3 | 0.1 | 0.0 |

### 2.6 Organic-to-Inorganic Transitions

Where flesh meets armor growth, crystals, or metal (common in dark fantasy creatures):

**Transition Recipe:**
```
MASK GENERATION:
  Noise Texture (Scale: 4.0, Detail: 6, Distortion: 2.0)
    -> ColorRamp (B-Spline: positioned to create irregular boundary)
      -> This is the transition mask

  Geometry -> Pointiness (optional addition for edge-aware transition)
    -> Add to noise mask for organic-feeling boundary

MATERIAL MIX:
  Mix Shader (Factor: transition mask)
    Shader 1: Flesh/Skin material (full SSS setup)
    Shader 2: Armor/Crystal/Metal material (appropriate settings)

  At the boundary zone:
    - Add emission glow (Factor: inverted edge of transition mask, narrow band)
    - Increase bump/displacement (transition ridge)
    - Roughness spike at boundary (0.7-0.9 -- irritated/scarred tissue meets hard surface)
```

---

## 3. Armor and Equipment Texturing

### 3.1 Metal Texturing by Tier

**PBR Values by Metal Type:**

| Metal Tier | Base Color (linear) | Metallic | Roughness (pristine) | Roughness (worn) | IOR | Notes |
|-----------|---------------------|----------|---------------------|-------------------|-----|-------|
| Iron | (0.53, 0.51, 0.49) | 0.95 | 0.45-0.55 | 0.60-0.80 | 2.95 | Dark, warm gray. Most common |
| Steel | (0.63, 0.62, 0.60) | 0.95 | 0.30-0.40 | 0.50-0.70 | 2.50 | Lighter, cooler gray |
| Bronze | (0.70, 0.45, 0.20) | 0.90 | 0.35-0.45 | 0.55-0.75 | 1.18 | Warm orange-brown |
| Silver | (0.95, 0.93, 0.88) | 0.98 | 0.20-0.30 | 0.40-0.60 | 0.18 | Near-white, very reflective |
| Gold | (1.00, 0.77, 0.31) | 0.98 | 0.15-0.25 | 0.35-0.55 | 0.47 | Rich warm yellow |
| Dark/Black Steel | (0.20, 0.20, 0.22) | 0.92 | 0.35-0.45 | 0.50-0.65 | 2.50 | "Blackened" metal |
| Obsidian (volcanic glass) | (0.03, 0.03, 0.04) | 0.0 | 0.05-0.15 | 0.30-0.50 | 1.50 | Dielectric, not metal! |
| Mithril/Fantasy | (0.75, 0.80, 0.85) | 0.95 | 0.10-0.20 | 0.25-0.40 | 1.80 | Cool blue-silver, very smooth |

**Note:** Metallic is binary for physically accurate PBR (0.0 or 1.0). Values between 0 and 1 are only used for transition zones (e.g., rusted metal where rust is dielectric at 0.0 and clean metal is 1.0).

**Procedural Rusted Metal Recipe:**

```
CLEAN METAL BASE:
  Principled BSDF:
    Base Color: iron color (0.53, 0.51, 0.49)
    Metallic: 1.0
    Roughness: 0.45

RUST LAYER:
  Noise Texture (Scale: 5.0, Detail: 8, Roughness: 0.6)
    -> ColorRamp (2 stops: 0.0=black, 0.6=white) -- controls rust coverage
      -> This is the RUST MASK

  Rust BSDF values (driven by mask):
    Base Color: (0.40, 0.20, 0.08) -- dark orange-brown rust
    Metallic: 0.0 (rust is NOT metallic)
    Roughness: 0.80-0.95 (rust is very rough)

EDGE WEAR (exposed clean metal at edges):
  Geometry -> Pointiness
    -> ColorRamp (Black at 0.47, White at 0.52) -- isolate convex edges
      -> Invert: edges REMOVE rust (reveal clean metal)
      -> Multiply with inverted rust mask

FINAL MIX:
  Mix Shader:
    Factor: rust_mask * (1 - edge_wear_mask)
    Shader 1: Clean metal Principled BSDF
    Shader 2: Rust Principled BSDF

SURFACE DETAIL:
  Noise Texture (Scale: 30, Detail: 4) -> Bump (Strength: 0.1)
    for metal grain / hammer marks
  Voronoi (Feature: Crackle, Scale: 15) -> Bump (Strength: 0.05)
    for pitting/corrosion texture
```

**Patina (aged bronze/copper):** Same structure as rust but with green-blue color (0.15, 0.35, 0.25), lower roughness (0.5-0.7), and accumulation in concavities instead of random noise. Use AO-baked cavity mask or inverted Pointiness to concentrate patina in crevices.

### 3.2 Leather Texturing

**Procedural Leather Recipe:**

```
GRAIN PATTERN:
  Voronoi Texture (Feature: F1, Distance: Euclidean, Scale: 25-40)
    -> ColorRamp (B-Spline: creates rounded grain bumps)
      -> Bump (Strength: 0.2-0.3, Distance: 0.002)

  Noise Texture (Scale: 8, Detail: 4, Distortion: 1.5)
    -> Mix with Voronoi via Add (Factor: 0.3) for irregularity

PRINCIPLED BSDF:
  Base Color: varies by leather type (see table)
  Roughness: 0.55-0.75 (worn leather smoother: 0.45-0.55)
  Metallic: 0.0
  Sheen Weight: 0.3-0.5 (leather has a velvet-like sheen at grazing angles)
  Sheen Roughness: 0.5
  Sheen Tint: slightly warm version of base color
  Coat Weight: 0.0-0.2 (oiled leather higher)
  SSS Scale: 0.002 (very subtle for thin leather)
```

**Leather Color by Type:**

| Leather Type | Base Color (linear) | Roughness | Notes |
|-------------|---------------------|-----------|-------|
| Raw/undyed | (0.25, 0.18, 0.10) | 0.65-0.80 | Warm tan-brown |
| Aged/darkened | (0.12, 0.08, 0.05) | 0.55-0.70 | Dark brown, near black |
| Red-dyed | (0.30, 0.08, 0.05) | 0.50-0.65 | Deep oxblood |
| Black leather | (0.03, 0.03, 0.03) | 0.45-0.60 | Very dark, slight sheen |

### 3.3 Cloth/Fabric Texturing

**Procedural Fabric Weave Recipe:**

```
WARP THREADS:
  Wave Texture (Type: Bands, Direction: X, Scale: 50, Distortion: 0.5)
    -> ColorRamp -> creates vertical thread pattern

WEFT THREADS:
  Wave Texture (Type: Bands, Direction: Y, Scale: 50, Distortion: 0.5)
    -> ColorRamp -> creates horizontal thread pattern

WEAVE INTERSECTION:
  Mix (Overlay mode): Warp * Weft
    -> Creates crosshatch weave pattern
    -> Feed into Bump (Strength: 0.1-0.2) for thread relief

ALTERNATIVE (Brick Texture method):
  Brick Texture (Scale: 30, Row Height: 0.5, Brick Width: 1.0, Offset: 0.5)
    -> Creates interlocking brick pattern resembling plain weave
    -> Better for coarse fabric (burlap, canvas)
    -> ColorRamp to control thread color variation

PRINCIPLED BSDF:
  Base Color: fabric color with slight thread variation
  Roughness: 0.75-0.95 (fabric is rough)
  Metallic: 0.0
  Sheen Weight: 0.4-0.8 (fabric has strong velvet sheen)
  Sheen Roughness: 0.3-0.5
  Sheen Tint: base color with increased saturation
```

**Fabric PBR Values by Type:**

| Fabric Type | Roughness | Sheen Weight | Sheen Roughness | Notes |
|------------|-----------|-------------|-----------------|-------|
| Burlap/Canvas | 0.85-0.95 | 0.2 | 0.5 | Coarse weave, matte |
| Linen | 0.70-0.80 | 0.4 | 0.4 | Medium weave |
| Wool | 0.80-0.90 | 0.5 | 0.3 | Fuzzy, strong sheen |
| Silk | 0.30-0.45 | 0.8 | 0.2 | Smooth, high sheen, anisotropic |
| Velvet | 0.60-0.70 | 1.0 | 0.15 | Maximum sheen effect |
| Tattered (any) | base + 0.10 | base - 0.2 | base + 0.1 | Worn fabric is rougher, less sheen |

### 3.4 Equipment Rarity Visual Progression

How rarity tiers affect texture appearance:

| Rarity | Texture Treatment | Emission | Roughness Delta | Additional VFX |
|--------|------------------|----------|----------------|----------------|
| Common (white) | Plain materials, visible wear | None | +0.0 (base values) | None |
| Uncommon (green) | Slightly cleaner, minor detail | None | -0.05 | None |
| Rare (blue) | Polished, engraved detail | None | -0.10 | Subtle sheen |
| Epic (purple) | Ornate patterns, gem inlays | Low glow (0.2-0.5) | -0.15 | Faint particle trail |
| Legendary (gold) | Master-crafted, unique materials | Strong glow (0.5-1.5) | -0.20 | Persistent aura VFX |

**Enchantment Glow Overlay:**
- Use Emission Color set to brand color (see VeilBreakers brand palette)
- Emission Strength: 0.3 (rare) to 1.5 (legendary)
- Pattern: Use UV-scrolling Noise or Wave textures for animated glow
- In Unity: emission map with UV scrolling shader (already supported by `unity_vfx` create_shader)

### 3.5 Wear and Damage on Equipment

**Edge Scratch Pattern:**
```
Geometry -> Pointiness
  -> ColorRamp (isolate convex edges: Black at 0.48, White at 0.52)
    -> Noise Texture (Scale: 50, Detail: 2) -> Multiply (breaks up solid edge)
      -> Edge wear mask

Apply edge wear mask:
  - Base Color: shift toward bare metal color at edges
  - Metallic: increase at edges (reveals metal under paint/coating)
  - Roughness: decrease at edges (worn smooth from contact)
```

**Dent/Impact Damage:**
```
Voronoi (Feature: F1, Scale: 3, Randomness: 1.0)
  -> ColorRamp (isolate individual cells as dent locations)
    -> Multiply with Noise (random placement)
      -> Bump (Strength: -0.3 negative for indentation)
```

**Rust Progression (time-based parameter):**
Control rust coverage with a single 0-1 value (exposed as node group input):
- 0.0 = pristine
- 0.3 = light surface rust at crevices
- 0.6 = moderate rust spreading from edges and crevices
- 1.0 = heavily corroded, structural damage visible

---

## 4. Procedural Texturing in Blender -- Implementation Guide

### 4.1 Baking Procedural Textures to Image Textures

This is the critical pipeline step: procedural materials MUST be baked to image textures for game engine export. Unity and other engines cannot use Blender's procedural node trees.

**Bake Pipeline (already partially implemented in `handle_bake_textures`):**

```python
# 1. Ensure Cycles render engine (REQUIRED for baking)
bpy.context.scene.render.engine = 'CYCLES'

# 2. Create target image for baking
img = bpy.data.images.new("BakedAlbedo", width=2048, height=2048)

# 3. Create Image Texture node in material, set as active for baking
# CRITICAL: This node must exist but NOT be connected to anything
tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex_node.image = img
mat.node_tree.nodes.active = tex_node  # MUST be active node

# 4. Set bake type and bake
bpy.context.scene.render.bake.use_pass_direct = False
bpy.context.scene.render.bake.use_pass_indirect = False
bpy.context.scene.render.bake.use_pass_color = True  # For DIFFUSE
bpy.context.scene.cycles.samples = 1  # Procedural textures need only 1 sample
bpy.ops.object.bake(type='DIFFUSE')  # Bakes Base Color channel

# 5. Save baked image
img.filepath_raw = "/path/to/output_albedo.png"
img.file_format = 'PNG'
img.save()
```

**Per-Channel Bake Types:**

| PBR Channel | Bake Type | Settings | Notes |
|------------|-----------|----------|-------|
| Albedo | DIFFUSE | use_pass_color=True, direct=False, indirect=False | Color only, no lighting |
| Normal | NORMAL | space='TANGENT' | Tangent space for game engines |
| Roughness | ROUGHNESS | (direct bake type in Blender 4.0+) | Or use EMIT with roughness connected to Emission |
| Metallic | EMIT | Connect Metallic to Emission, bake EMIT | No direct metallic bake type |
| AO | AO | samples=32+ | Higher samples = cleaner AO |
| Emission | EMIT | Standard emit bake | If material has emission |

**Workaround for channels without direct bake type (Metallic, Roughness):**
Temporarily rewire the channel value to Emission Color input, bake as EMIT, then restore original wiring. This is the standard technique used by game artists.

### 4.2 Multi-Layer Material Blending via Vertex Colors

**Setup in Blender:**

```python
# 1. Create vertex color layer
mesh = obj.data
if not mesh.vertex_colors:
    mesh.vertex_colors.new(name="MaterialBlend")

# 2. In shader node tree:
# Attribute node (name="MaterialBlend") -> Separate Color
#   R channel -> Mix factor between Material A and Material B
#   G channel -> Mix factor for Material C overlay
#   B channel -> Mix factor for Material D overlay (or corruption mask)
```

**Node Structure:**
```
Attribute (MaterialBlend) -> Separate Color
  R -> Mix Shader (Material A / Material B)
    -> Mix Shader (result / Material C, Factor: G)
      -> Mix Shader (result / Material D, Factor: B)
        -> Material Output
```

This supports up to 4 materials blended by vertex painting. The vertex colors export with FBX and can drive Unity shader blending too.

### 4.3 Texel Density Targets by Asset Type

| Asset Type | Texture Resolution | Texel Density Target | Notes |
|-----------|-------------------|---------------------|-------|
| Hero Character (head) | 2048x2048 | 20.48 px/cm | Double density for face close-ups |
| Hero Character (body) | 2048x2048 | 10.24 px/cm | Standard TPP density |
| Standard Mob | 1024x1024 | 5.12 px/cm | Groups visible at distance |
| NPC | 2048x2048 | 10.24 px/cm | Conversation distance |
| Weapon (hero) | 1024x1024 | 10.24 px/cm | Small surface, high importance |
| Shield | 1024x1024 | 5.12-10.24 px/cm | Medium priority |
| Armor piece | 1024x1024 | 10.24 px/cm | Per-piece, visible on player |
| Small prop | 256x256 - 512x512 | 2.56-5.12 px/cm | Low priority |
| Medium prop | 512x512 - 1024x1024 | 5.12 px/cm | Standard |
| Large prop | 1024x1024 | 5.12 px/cm | Standard |
| Building trim sheet | 2048x2048 | N/A (tiling) | Shared across building style |
| Terrain tile | 2048x2048 | N/A (tiling) | Per-biome tiling |

**Formula:** `texel_density = texture_resolution / (object_surface_width_cm)`

For a 1.8m tall character body with 2048 texture: `2048 / 180cm = 11.38 px/cm` (close to 10.24 target).

---

## 5. Texture Resolution and Format Standards

### 5.1 Resolution Standards

| Asset Category | Albedo | Normal | M/R/AO Pack | Emission | Notes |
|---------------|--------|--------|-------------|----------|-------|
| Hero Character | 2048 + 1024 face | 2048 + 1024 face | 2048 | 512-1024 | Face gets dedicated texture |
| Standard Mob | 1024 | 1024 | 1024 | 512 | Single atlas |
| Boss Creature | 2048-4096 | 2048-4096 | 2048 | 1024 | Hero-quality villain |
| NPC | 2048 | 2048 | 1024 | 512 | Conversation distance |
| Weapon | 1024 | 1024 | 1024 | 512 | Inspectable = 2048 |
| Armor Piece | 1024 | 1024 | 1024 | 512 | Per-piece |
| Small Prop | 256-512 | 256-512 | 256-512 | -- | Often no emission |
| Medium Prop | 512-1024 | 512-1024 | 512-1024 | -- | |
| Large Prop | 1024 | 1024 | 1024 | 512 | |
| Environment Tile | 2048 | 2048 | 2048 | -- | Tiling, shared |

**All textures MUST be power-of-two.** Non-POT textures cannot be properly mipmapped and waste GPU memory. Already enforced by `_validate_texture_metadata` in `texture.py`.

### 5.2 Channel Packing Convention

**Standard channel pack (reduces 3 textures to 1):**

| Channel | R | G | B | A |
|---------|---|---|---|---|
| _MRA pack | Metallic | Roughness | AO | (unused or height) |
| _Normal | Normal X | Normal Y | (unused) | -- |
| _Albedo | Color R | Color G | Color B | Alpha/Opacity |

**Why R=Metallic, G=Roughness, B=AO:**
- This is the most common Unity/Unreal convention
- Green channel has highest precision in most compression formats
- Roughness has the most perceptual impact, so it gets the best channel
- Unity URP Standard Lit shader expects this exact packing in the "Metallic" texture slot

**Implementation in existing pipeline:**
The current `_build_channel_config()` in `texture.py` creates separate texture nodes for each channel. For channel packing, add a bake step that:
1. Bakes each channel separately
2. Loads as numpy arrays
3. Packs into a single RGBA image: `packed[:,:,0] = metallic; packed[:,:,1] = roughness; packed[:,:,2] = ao`
4. Saves as single PNG

### 5.3 UDIM Tile Layout for Hero Characters

UDIM tiles assign body regions to numbered texture tiles for higher resolution:

| Tile | Region | Resolution | Priority |
|------|--------|-----------|----------|
| 1001 | Head/Face | 2048x2048 | Highest -- conversation close-ups |
| 1002 | Torso (front/back) | 2048x2048 | High -- always visible |
| 1003 | Arms + Hands | 1024x1024 | Medium -- often covered by armor |
| 1004 | Legs + Feet | 1024x1024 | Medium -- often covered |
| 1005 | Equipment/Accessories | 1024x1024 | Medium |

**Note on UDIM for games:** Most game engines (including Unity URP) do NOT natively support UDIM at runtime. UDIMs are a production workflow convenience -- at export time, each UDIM tile becomes a separate material with its own texture set. For VeilBreakers, use UDIMs only for hero characters during production, and flatten to per-material textures at export.

### 5.4 Texture Compression Formats for Unity URP

| Format | Use Case | Quality | Size | Platform |
|--------|---------|---------|------|----------|
| BC7 | Albedo, M/R/AO pack, Emission | Highest | 8 bpp | PC (DX11+) |
| BC5 | Normal maps (RG only) | High for normals | 8 bpp | PC (DX11+) |
| BC6H | HDR textures | High | 8 bpp | PC (DX11+) |
| DXT5 | Albedo with alpha | Good | 8 bpp | PC (legacy fallback) |
| DXT1 | Albedo no alpha | Good | 4 bpp | PC (legacy fallback) |
| ASTC 4x4 | All maps | Highest mobile | 8 bpp | Mobile/Console |
| ASTC 6x6 | All maps | Good mobile | 3.56 bpp | Mobile (balanced) |
| ASTC 8x8 | Low-priority maps | Acceptable | 2 bpp | Mobile (perf) |

**Recommendation for VeilBreakers (PC target):**
- Albedo: BC7 (best quality for color data)
- Normal maps: BC5 (optimized for 2-channel normal data, higher quality than BC7 for normals)
- M/R/AO pack: BC7 (good quality for packed data)
- Emission: BC7 or DXT1 (if no alpha needed)

Unity import settings (for `unity_assets` texture_import action):
```json
{
  "texture_type": "Default",
  "max_size": 2048,
  "compression": "HighQuality",
  "format_override_pc": "BC7",
  "generate_mipmaps": true,
  "streaming_mipmaps": true,
  "aniso_level": 4
}
```

For normal maps:
```json
{
  "texture_type": "NormalMap",
  "max_size": 2048,
  "compression": "NormalQuality",
  "format_override_pc": "BC5",
  "generate_mipmaps": true,
  "aniso_level": 4
}
```

### 5.5 Mipmap Requirements

- **Generate mipmaps:** YES for all game textures (essential for rendering quality at distance)
- **Streaming mipmaps:** Enable for textures > 512x512 (reduces initial VRAM load)
- **Anisotropic filtering:** Level 4-8 for floor/ground textures, level 2-4 for vertical surfaces
- **Mip bias:** 0 default, -0.5 for textures that appear blurry at distance

---

## 6. Texture Baking Pipeline

### 6.1 High-Poly to Low-Poly Normal Map Baking

**Critical settings for quality baking:**

| Parameter | Recommended Value | Notes |
|-----------|------------------|-------|
| Render Engine | Cycles | EEVEE cannot bake |
| Bake Type | Normal | Tangent space |
| Space | Tangent | Game engine standard |
| Samples | 1-4 | Normal baking is deterministic, low samples fine |
| Margin | 16px (1024), 32px (2048), 64px (4096) | Prevents mipmap bleeding |
| Extrusion | Auto-calculate | Set to smallest value that eliminates green artifacts |
| Max Ray Distance | 1.5-2x Extrusion | Limits search range |
| Selected to Active | ON | High-poly selected, low-poly active |

**Extrusion auto-calculation (implement in handler):**
```python
# Calculate based on bounding box difference
high_dims = high_poly.dimensions
low_dims = low_poly.dimensions
max_diff = max(abs(h - l) for h, l in zip(high_dims, low_dims))
extrusion = max_diff * 1.5 + 0.01  # Safety margin
```

### 6.2 AO Baking Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Bake Type | AO | Ambient occlusion |
| Samples | 32-64 | More = cleaner, less noise |
| Distance | 0.5-2.0 | How far AO rays travel. Smaller = tighter, more contact-shadow-like |
| Margin | Same as normal map | |

### 6.3 Curvature Map Generation

Blender does NOT have a direct curvature bake type. Two approaches:

**Approach A -- Bake from shader (recommended for our pipeline):**
```python
# Create temporary material with Pointiness driving Emission
temp_mat = bpy.data.materials.new("CurvatureBake")
temp_mat.use_nodes = True
tree = temp_mat.node_tree
tree.nodes.clear()

# Geometry -> Pointiness -> ColorRamp -> Emission -> Output
geo = tree.nodes.new("ShaderNodeNewGeometry")
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.45
ramp.color_ramp.elements[1].position = 0.55
emit = tree.nodes.new("ShaderNodeEmission")
out = tree.nodes.new("ShaderNodeOutputMaterial")

tree.links.new(geo.outputs["Pointiness"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], emit.inputs["Color"])
tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])

# Bake as EMIT
bpy.ops.object.bake(type='EMIT')
```

**Approach B -- Compute from normal map (post-process in Python/numpy):**
```python
import numpy as np
from PIL import Image

normal_img = np.array(Image.open("normal_map.png")).astype(float) / 255.0
# Compute Laplacian of normals for curvature approximation
dx = np.gradient(normal_img[:,:,0], axis=1)
dy = np.gradient(normal_img[:,:,1], axis=0)
curvature = np.sqrt(dx**2 + dy**2)
curvature_normalized = (curvature / curvature.max() * 255).astype(np.uint8)
Image.fromarray(curvature_normalized).save("curvature_map.png")
```

### 6.4 Thickness Map for SSS

**Bake method:** Use the Cycles "Thickness" baker by inverting AO:

```python
# Method: AO bake with inverted normals (simulates thickness)
# 1. Duplicate mesh
# 2. Flip normals on duplicate
# 3. Bake AO from flipped-normal mesh onto original UV
# 4. Result: thin areas = bright (more occlusion from inside)

# Alternatively, use custom emission shader:
# AO node -> Invert -> Emission -> bake EMIT
```

**Simplified approach for our pipeline:**
Use AO bake with very short distance (0.1-0.5). Thin areas naturally get more occlusion. Then invert in post-processing via numpy: `thickness = 255 - ao_map`.

### 6.5 ID Map / Material Mask

**Purpose:** Color-coded regions for masking in texture painting or shader effects.

```python
# Assign flat, unique colors to each material slot
# Then bake DIFFUSE with no lighting contribution
mat_colors = [
    (1, 0, 0),    # Red = material slot 0
    (0, 1, 0),    # Green = material slot 1
    (0, 0, 1),    # Blue = material slot 2
    (1, 1, 0),    # Yellow = material slot 3
    (1, 0, 1),    # Magenta = material slot 4
]
# Temporarily set each material to flat emission of its ID color
# Bake EMIT
# Restore original materials
```

### 6.6 Bent Normal Baking

Bent normals encode the average unoccluded direction, improving ambient lighting quality.

**Not directly supported in Blender's bake system.** Options:
1. Bake in external tool (xNormal, Substance Baker, Marmoset)
2. Approximate by combining normal map with AO direction
3. For VeilBreakers, skip bent normals -- Unity URP does not use them by default, and the visual improvement is marginal for a third-person game

---

## 7. Material Template Library Architecture

### 7.1 Proposed Structure

```python
MATERIAL_TEMPLATES = {
    # ---- ORGANIC ----
    "skin_fair": {
        "category": "organic",
        "base_color": (0.72, 0.56, 0.45),
        "metallic": 0.0,
        "roughness": 0.50,
        "roughness_variation": 0.15,
        "sss_weight": 1.0,
        "sss_scale": 0.012,
        "sss_radius": (1.0, 0.2, 0.1),
        "sss_ior": 1.4,
        "coat_weight": 0.05,
        "normal_strength": 1.0,
        "pore_detail": {"noise_scale": 12.0, "bump_strength": 0.15},
        "zones": {  # roughness zones for faces
            "forehead": 0.35, "nose": 0.33, "cheeks": 0.55,
            "chin": 0.45, "ears": 0.60, "lips": 0.30
        }
    },
    "skin_pale_undead": { ... },
    "skin_corrupted": { ... },
    "skin_dark": { ... },
    "skin_demonic": { ... },

    # ---- CREATURE ----
    "scales_dragon": { ... },
    "scales_serpent": { ... },
    "chitin_dark": { ... },
    "chitin_iridescent": { ... },
    "membrane_wing": { ... },
    "bone_aged": { ... },
    "horn_dark": { ... },
    "fur_base_skin": { ... },

    # ---- METAL ----
    "metal_iron": { ... },
    "metal_iron_rusted": { ... },
    "metal_steel": { ... },
    "metal_steel_blackened": { ... },
    "metal_bronze": { ... },
    "metal_bronze_patina": { ... },
    "metal_gold": { ... },
    "metal_silver": { ... },
    "metal_mithril": { ... },

    # ---- SOFT GOODS ----
    "leather_raw": { ... },
    "leather_aged": { ... },
    "leather_dyed_red": { ... },
    "fabric_burlap": { ... },
    "fabric_linen": { ... },
    "fabric_silk": { ... },
    "fabric_wool": { ... },

    # ---- HARD ORGANIC ----
    "wood_aged_oak": { ... },
    "wood_charred": { ... },
    "stone_dark": { ... },
    "stone_carved": { ... },
}
```

### 7.2 Implementation Priority

| Priority | Material Templates | Reason |
|----------|-------------------|--------|
| P0 (Critical) | skin_fair, skin_pale_undead, skin_corrupted, metal_iron, metal_iron_rusted, leather_raw, bone_aged | Core character/creature/equipment materials |
| P1 (High) | scales_dragon, chitin_dark, metal_steel, metal_gold, fabric_burlap, horn_dark | Monster variety, equipment tiers |
| P2 (Medium) | All remaining metals, fabrics, creature surfaces | Complete material coverage |
| P3 (Low) | Exotic materials (mithril, obsidian, iridescent chitin) | Fantasy/rare materials |

---

## 8. PBR Value Reference Chart

### 8.1 Complete Material Properties Reference

| Material | Metallic | Roughness (range) | IOR | SSS Scale | Coat Weight | Sheen Weight |
|----------|----------|-------------------|-----|-----------|-------------|-------------|
| Human skin | 0.0 | 0.30-0.65 | 1.40 | 0.008-0.018 | 0.0-0.15 | 0.0 |
| Undead skin | 0.0 | 0.50-0.85 | 1.35 | 0.002-0.006 | 0.0 | 0.0 |
| Iron | 1.0 | 0.45-0.80 | 2.95 | 0.0 | 0.0 | 0.0 |
| Steel | 1.0 | 0.30-0.70 | 2.50 | 0.0 | 0.0 | 0.0 |
| Gold | 1.0 | 0.15-0.55 | 0.47 | 0.0 | 0.0 | 0.0 |
| Copper | 1.0 | 0.25-0.60 | 1.10 | 0.0 | 0.0 | 0.0 |
| Bronze | 0.90 | 0.35-0.75 | 1.18 | 0.0 | 0.0 | 0.0 |
| Silver | 1.0 | 0.20-0.60 | 0.18 | 0.0 | 0.0 | 0.0 |
| Rust | 0.0 | 0.80-0.95 | 1.50 | 0.0 | 0.0 | 0.0 |
| Leather | 0.0 | 0.45-0.80 | 1.50 | 0.002 | 0.0-0.2 | 0.3-0.5 |
| Fabric (rough) | 0.0 | 0.75-0.95 | 1.50 | 0.0 | 0.0 | 0.4-0.8 |
| Silk | 0.0 | 0.30-0.45 | 1.50 | 0.0 | 0.0 | 0.8 |
| Bone | 0.0 | 0.55-0.80 | 1.50 | 0.005 | 0.0 | 0.0 |
| Chitin | 0.0 | 0.15-0.35 | 1.55 | 0.0 | 0.4-0.7 | 0.0 |
| Horn/Claw | 0.0 | 0.40-0.75 | 1.55 | 0.003 | 0.2-0.3 | 0.0 |
| Dragon scale | 0.0-0.1 | 0.30-0.65 | 1.50 | 0.003 | 0.3-0.5 | 0.0 |
| Membrane | 0.0 | 0.50-0.70 | 1.40 | 0.02-0.05 | 0.0 | 0.0 |
| Wood | 0.0 | 0.60-0.90 | 1.50 | 0.0 | 0.0-0.1 | 0.1-0.3 |
| Stone | 0.0 | 0.65-0.95 | 1.50 | 0.0 | 0.0 | 0.0 |
| Crystal/Gem | 0.0 | 0.02-0.10 | 1.50-2.42 | 0.0 | 0.0 | 0.0 |
| Glass | 0.0 | 0.02-0.08 | 1.45 | 0.0 | 0.0 | 0.0 |

### 8.2 Dark Fantasy Palette Rules (cross-reference with palette_validator.py)

Already implemented in `palette_validator.py`:
- Saturation cap: 0.55 (environments never exceed 40%, only magic/UI exceed 60%)
- Value range: 0.15-0.75 (dark world)
- Warm temperature threshold: 0.55
- Cool bias target: 0.6

**Additional rules for character textures specifically:**
- Skin albedo should NEVER be pure white or pure black -- keep in 0.15-0.75 value range
- Scar tissue color shift: +0.1 red, +0.05 green relative to surrounding skin
- Blood: (0.25, 0.02, 0.02) -- dark, desaturated (not bright red)
- Bruise progression: fresh(purple) -> healing(yellow-green) -> healed(slightly darker than skin)

---

## 9. Integration with Existing Toolkit

### 9.1 What Exists (no changes needed)

| Component | File | Capability |
|-----------|------|-----------|
| PBR node tree creation | `blender_addon/handlers/texture.py` | Creates 5-channel PBR material with image textures |
| BSDF input mapping | `texture.py` BSDF_INPUT_MAP | Handles Blender 3.x and 4.0+ socket names |
| Texture baking | `handle_bake_textures` | High-to-low-poly baking with cage support |
| De-lighting | `shared/delight.py` | Removes baked lighting from AI albedo textures |
| Palette validation | `shared/palette_validator.py` | Enforces dark fantasy color/saturation rules |
| UV masking | `shared/texture_ops.py` | Feathered UV masks for surgical texture editing |
| Seam blending | `shared/texture_ops.py` | Smooths UV seam discontinuities |
| Wear map generation | `shared/texture_ops.py` | Curvature-based wear/damage maps |
| Tileable textures | `shared/texture_ops.py` | Cross-fade edges for seamless tiling |
| AI inpainting | `shared/texture_ops.py` | fal.ai FLUX texture inpainting |
| Texture validation | `shared/texture_validation.py` | Resolution, format, colorspace checks |
| ESRGAN upscaling | `shared/esrgan_runner.py` | 4x AI texture upscaling |
| Roughness validation | `shared/palette_validator.py` | Checks roughness map variance |

### 9.2 What Needs Building

| Component | Priority | Description |
|-----------|----------|-------------|
| Material template library | P0 | Python dict of ~25 procedural material recipes |
| Procedural node tree builder | P0 | Function that creates full procedural shader from template |
| Channel bake pipeline | P0 | Bake all PBR channels from procedural material to images |
| Channel packer | P1 | Pack M/R/AO into single texture (numpy) |
| Curvature map baker | P1 | Pointiness-to-emission bake for edge wear masks |
| Thickness map baker | P1 | Inverted-normal AO bake for SSS thickness |
| Vertex color material blend | P2 | Multi-material blending via vertex color painting |
| Corruption overlay system | P2 | Brand-specific corruption texture overlays |
| Rarity VFX texture system | P2 | Emission maps for equipment enchantment glows |
| ID map baker | P3 | Color-coded material region maps |

### 9.3 Recommended New blender_texture Actions

| Action | Parameters | Description |
|--------|-----------|-------------|
| `create_procedural` | `template`, `object_name`, `texture_size`, `variation_seed` | Build procedural material from template library |
| `bake_all_channels` | `object_name`, `texture_size`, `output_dir`, `source_object` | Bake all PBR channels + pack M/R/AO |
| `apply_corruption` | `object_name`, `brand`, `intensity`, `pattern_seed` | Apply brand-colored corruption overlay via vertex color |
| `apply_wear` | `object_name`, `wear_amount`, `rust_amount` | Apply edge wear + rust using curvature + noise masks |
| `bake_curvature` | `object_name`, `image_name`, `texture_size` | Bake curvature map from Pointiness |
| `bake_thickness` | `object_name`, `image_name`, `texture_size` | Bake thickness map for SSS |
| `pack_channels` | `metallic_path`, `roughness_path`, `ao_path`, `output_path` | Pack 3 grayscale maps into single RGB |

---

## 10. Common Pitfalls

### Pitfall 1: Linear vs sRGB Colorspace Confusion
**What goes wrong:** Textures look washed out or too dark in-engine
**Root cause:** Albedo saved as linear but imported as sRGB, or vice versa
**Prevention:** Albedo = sRGB. ALL other maps (normal, roughness, metallic, AO) = Linear/Non-Color
**Already handled:** `_build_channel_config()` sets colorspace correctly per channel

### Pitfall 2: Baking Procedural Textures with Wrong Samples
**What goes wrong:** Baked textures look noisy or have firefly artifacts
**Root cause:** Using too many or too few Cycles samples for baking
**Prevention:** Procedural textures need only 1-4 samples (deterministic). Image-based textures/lighting need 32+

### Pitfall 3: Normal Map Tangent Space Mismatch
**What goes wrong:** Normal maps appear inverted (bumps look like dents) in Unity
**Root cause:** Blender uses OpenGL tangent space (+Y up). Unity URP expects OpenGL (+Y up) but DirectX normal maps have flipped Y
**Prevention:** Always bake in Tangent space. Unity expects OpenGL format by default. If importing DirectX normal maps, flip G channel

### Pitfall 4: Metallic Values Between 0 and 1
**What goes wrong:** Materials look plasticky or unrealistic
**Root cause:** Setting metallic to intermediate values (0.3, 0.5, etc.)
**Prevention:** Metallic should be 0 (dielectric) or 1 (metal). Only use intermediate values for transition zones (rust edge, paint chipping)

### Pitfall 5: Missing Bake Margins
**What goes wrong:** Visible seams at UV island boundaries, especially at distance
**Root cause:** No margin (or too small) causes mipmapped textures to bleed background color at seam edges
**Prevention:** Margin = texture_size / 64 (minimum 16px). Our existing bake handler defaults to 16, but should scale with resolution

### Pitfall 6: Overbaked AO Creating Dark Halos
**What goes wrong:** Dark, unrealistic shadows baked into textures
**Root cause:** AO distance too high or multiplied too strongly with albedo
**Prevention:** AO distance should match object scale. Multiply AO with albedo at 0.5-0.8 factor, not 1.0. Our existing handler uses factor 1.0 in `mix_node.inputs["Fac"].default_value = 1.0` -- consider reducing

### Pitfall 7: Vertex Color Export Failure
**What goes wrong:** Vertex color data missing after FBX export to Unity
**Root cause:** FBX exporter settings or vertex color layer naming issues
**Prevention:** Ensure `include_vertex_colors` is True in FBX export settings. Name vertex color layers clearly. Unity imports vertex colors from FBX automatically

---

## Sources

### Primary (HIGH confidence)
- [Blender 4.0 Principled BSDF Manual](https://docs.blender.org/manual/en/4.0/render/shader_nodes/shader/principled.html) -- All BSDF input parameters, defaults, SSS changes
- [Blender 5.1 Render Baking Manual](https://docs.blender.org/manual/en/latest/render/cycles/baking.html) -- Bake types, margin, cage settings
- [Blender 5.1 Voronoi Texture Node](https://docs.blender.org/manual/en/latest/render/shader_nodes/textures/voronoi.html) -- F1, F2, Distance to Edge features
- [Physically Based Database](https://physicallybased.info/) -- Reference IOR and color values for metals and materials
- [Adobe Substance PBR Guide Part 2](https://substance3d.adobe.com/tutorials/courses/the-pbr-guide-part-2) -- Metallic/roughness workflow reference values
- [Unity Texture Compression Formats Manual](https://docs.unity3d.com/2022.2/Documentation/Manual/class-TextureImporterOverride.html) -- BC7, BC5, ASTC platform support

### Secondary (MEDIUM confidence)
- [Polycount -- Physically Accurate Material Values](https://polycount.com/discussion/164435/physically-accurate-material-values) -- Community-verified PBR charts
- [Beyond Extent -- Texel Density Deep Dive](https://www.beyondextent.com/deep-dives/deepdive-texeldensity) -- 5.12/10.24 px/cm standards
- [Marmoset -- Creating Realistic Skin with Saurabh Jethani](https://marmoset.co/posts/creating-realistic-skin-toolbag-saurabh-jethani/) -- Zone-based roughness technique
- [Blender Base Camp -- SSS Techniques](https://www.blenderbasecamp.com/skin-texturing-blender-s-sss-techniques/) -- Skin SSS workflow
- [Polycount -- AAA Pipeline Breakdown](https://polycount.com/discussion/237029/breakdown-of-the-aaa-pipeline-for-game-ready-realistic-hero-props) -- Hero prop texturing pipeline
- [Curvature Based Edge Wear](http://neilblevins.com/art_lessons/curvature_edge_wear/curvature_edge_wear.htm) -- Edge wear theory and technique
- [Generalist Programmer -- Substance Painter PBR Workflow 2025](https://generalistprogrammer.com/tutorials/substance-painter-game-texturing-complete-pbr-workflow) -- Modern PBR workflow
- [Tripo3D -- Curvature and Thickness Map Baking](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-baking-curvature-and-thickness-maps) -- Baking additional maps
- [BlenderKit -- Dragon Scales Material](https://www.blenderkit.com/asset-gallery-detail/25de9a7e-8316-42f2-85c4-f421dc23befe/) -- Scale pattern reference
- [O'Reilly -- Blender Cycles Chitin Material](https://www.oreilly.com/library/view/blender-cycles-materials/9781784399931/ch08s03.html) -- Procedural chitin recipe
- [TheGamedev.Guru -- Texture Compression in Unity](https://thegamedev.guru/unity-gpu-performance/texture-compression-and-formats/) -- Compression format comparison

### Tertiary (LOW confidence -- needs validation)
- [ArtStation -- Procedural Rusted Metal Blender 4.0](https://www.artstation.com/blogs/jsabbott/PQQ6j/making-a-procedural-rusted-metal-material-blender-40) -- Rust recipe reference (403 at fetch time)
- [GarageFarm -- UDIM Setup in Blender](https://garagefarm.net/blog/setting-up-udims-in-blender-step-by-step) -- UDIM workflow
- [Lesterbanks -- Procedural Fabric Weave](https://lesterbanks.com/2021/09/how-to-create-a-fabric-weave-shader-procedurally-in-blender/) -- Fabric node recipe
- [Artisticrender -- Procedural Leather](https://artisticrender.com/how-to-create-a-leather-material-in-blender/) -- Leather shader setup

---

## Metadata

**Confidence breakdown:**
- PBR value reference: HIGH -- cross-verified with physicallybased.info, Adobe PBR Guide, Polycount
- Blender node recipes: HIGH -- based on official Blender docs and established community techniques
- Skin SSS values: MEDIUM-HIGH -- SSS is inherently subjective, values are starting points to tune visually
- Texture format/compression: HIGH -- verified against Unity documentation
- Equipment rarity progression: MEDIUM -- based on industry conventions, not VeilBreakers-specific design doc
- Curvature/thickness baking: MEDIUM -- Blender's limitations verified, workarounds are standard practice

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (3 months -- PBR standards are stable, Blender node API may change with 5.x releases)
