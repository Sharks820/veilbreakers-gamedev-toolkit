# Terrain Materials & Shader Research

**Researched:** 2026-04-02
**Domain:** Terrain material assignment, splatmap blending, PBR terrain shaders
**Confidence:** HIGH (core techniques well-documented across industry)

## Summary

AAA terrain material systems use a data-driven pipeline where terrain analysis maps (slope, curvature, erosion, flow) feed into splatmap weights that control physically-based material blending. The current VeilBreakers system uses hard 30/60-degree slope thresholds with abrupt zone boundaries. Professional systems instead use smooth sigmoid/smoothstep transitions, height-blended texturing for sharp natural edges, curvature-driven detail overlays, and triplanar projection for cliff faces.

The key architectural shift is from "classify face into zone, assign material" to "compute continuous weight channels per-vertex from multiple terrain analysis inputs, blend materials in shader using height maps." This produces results comparable to Horizon Forbidden West, Elden Ring, and Ghost of Tsushima terrain.

**Primary recommendation:** Replace hard slope thresholds with smoothstep-based continuous weight computation. Add height-blend shader with per-texture height maps. Add curvature and erosion data as additional blending inputs. Use triplanar projection for surfaces steeper than ~45 degrees.

---

## 1. Splatmap-Based Terrain Texturing

**Confidence: HIGH** -- Industry standard since 2005, extensively documented.

### How Splatmaps Work

A splatmap is a texture where each RGBA channel stores a weight (0.0-1.0) for one terrain material layer. For any pixel on the terrain, the four channel values determine how much of each material is visible.

| Channel | Typical Assignment | Range |
|---------|-------------------|-------|
| R | Ground/Grass | 0.0 - 1.0 |
| G | Slope/Rock | 0.0 - 1.0 |
| B | Cliff/Stone | 0.0 - 1.0 |
| A | Special (snow, sand, water edge) | 0.0 - 1.0 |

**Sum-to-one normalization:** Weights at every pixel MUST sum to 1.0. This is enforced by dividing each weight by the sum of all weights:

```python
# Python (splatmap generation)
total = r + g + b + a
if total > 0.001:
    r, g, b, a = r/total, g/total, b/total, a/total
else:
    r, g, b, a = 1.0, 0.0, 0.0, 0.0  # Default to ground
```

```hlsl
// HLSL (shader-side normalization)
float4 splat = SAMPLE_TEXTURE2D(_SplatMap, sampler_SplatMap, uv);
splat /= dot(splat, float4(1,1,1,1));  // Normalize to sum=1
```

### Multi-Splatmap Setups (8-16+ Layers)

For more than 4 layers, multiple splatmaps are used:

| Layers | Splatmaps | Approach |
|--------|-----------|----------|
| 4 | 1 RGBA | Standard, single pass |
| 8 | 2 RGBA | Two-pass or single pass with texture arrays |
| 12 | 3 RGBA | Requires texture arrays for performance |
| 16 | 4 RGBA | MegaSplat/MULTISPLAT16 approach |
| 256 | Index-based | MegaSplat: fixed cost regardless of texture count |

**Unity URP specifics:** URP supports 4 Terrain Layers per texture pass with unlimited passes. Each additional pass increases draw calls. For performance, limit to 4-8 layers per terrain tile.

**Texture Array approach (recommended for 8+ layers):** Instead of individual texture samplers, use Texture2DArray. The splatmap selects which array indices to blend. MegaSplat selects the 4 most-representative textures per fragment, blends them, and runs at fixed cost regardless of total texture count.

### Priority-Based Splatmap Painting (Gaea's Approach)

Gaea uses terrain analysis to generate splatmaps procedurally:

1. **Data maps** are generated from terrain geometry: slope, curvature, flow, deposits
2. **Color ramps/gradients** are mapped into black-and-white masks from these data maps
3. Priority ordering: later layers overwrite earlier ones where their mask is active
4. **Biome node** combines water/flow maps to create zone masks
5. Output can be a direct color map or a "Super Splat" for engine-side blending

### Exclusion Masks

Material A can prevent material B from appearing. Implementation:

```python
# If snow is present (A > threshold), suppress grass (R)
if weights['snow'] > 0.3:
    weights['grass'] *= max(0.0, 1.0 - weights['snow'] * 2.0)
# Re-normalize after exclusion
total = sum(weights.values())
weights = {k: v/total for k, v in weights.items()}
```

---

## 2. Height-Blended Texturing

**Confidence: HIGH** -- Core technique used in all modern terrain shaders.

### The Problem with Linear Blending

Standard linear interpolation (`lerp`) between two textures creates a "soft blur" at transitions. In reality, materials have micro-scale height variation -- grass blades poke through dirt, rocks emerge above sand. Height blending solves this.

### How Height Blending Works

Each terrain material has an associated height map (grayscale texture, usually stored in alpha channel of albedo). During blending:

1. Sample height value from each layer's height map
2. Multiply height by splatmap weight
3. Find the maximum weighted height
4. Suppress layers whose weighted height is far from the maximum
5. Re-normalize remaining weights

### The Standard Height Blend Algorithm

```hlsl
// Existing in our TerrainBlend shader (verified correct)
float4 HeightBlend(float4 splatWeights, float h0, float h1, float h2, float h3, float sharpness)
{
    float4 heights = float4(h0, h1, h2, h3) * splatWeights;
    float maxHeight = max(max(heights.x, heights.y), max(heights.z, heights.w));
    float4 diff = heights - (maxHeight - 1.0 / sharpness);
    float4 blended = max(diff, 0.0) * splatWeights;
    float total = dot(blended, float4(1, 1, 1, 1));
    return total > 0.001 ? blended / total : splatWeights;
}
```

**Sharpness parameter:**
- Low (1-4): Soft, gradual transitions
- Medium (8-12): Natural-looking transitions (recommended default)
- High (16-32): Very sharp, almost binary transitions

### Visual Effect

With rock (height map = rough surface) and grass (height map = blade tips):
- At 50/50 blend, individual rock peaks poke through grass
- Grass fills crevices between rocks
- Transition looks natural, not blurred

### Implementation for Blender (Python side)

The height blend is relevant for baking splatmaps in Python too:

```python
def height_blend_weights(weights, heights, sharpness=8.0):
    """Apply height-based bias to splatmap weights.
    
    Args:
        weights: list of 4 floats (RGBA splatmap channels)
        heights: list of 4 floats (height values per layer, 0-1)
        sharpness: controls transition sharpness
    
    Returns:
        list of 4 normalized floats
    """
    weighted_h = [w * h for w, h in zip(weights, heights)]
    max_h = max(weighted_h)
    threshold = max_h - 1.0 / sharpness
    biased = [max(0.0, wh - threshold) * w 
              for wh, w in zip(weighted_h, weights)]
    total = sum(biased)
    if total > 0.001:
        return [b / total for b in biased]
    return list(weights)
```

---

## 3. Slope-Based Material Assignment (Smooth Transitions)

**Confidence: HIGH** -- Well-documented, current system needs this upgrade.

### Current Problem

The current system uses hard thresholds:
```python
# CURRENT (terrain_materials.py lines 1013-1065)
_FLAT_MAX_ANGLE = 30.0    # Hard cutoff: ground vs slopes
_SLOPE_MAX_ANGLE = 60.0   # Hard cutoff: slopes vs cliffs
```

This creates visible "banding" at 30 and 60 degrees.

### Smooth Slope Mapping with Smoothstep

Replace hard thresholds with smoothstep interpolation:

```python
def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite interpolation between 0 and 1."""
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)

def compute_slope_weights(
    angle_deg: float,
    ground_end: float = 25.0,
    slope_start: float = 20.0,
    slope_end: float = 55.0,
    cliff_start: float = 50.0,
) -> tuple[float, float, float]:
    """Compute smooth ground/slope/cliff weights from angle.
    
    Overlapping ranges create smooth transitions:
      - Ground: full at 0, fades 20-25 degrees
      - Slope: fades in 20-25, full at 30-45, fades out 50-55
      - Cliff: fades in 50-55, full at 60+
    """
    ground = 1.0 - smoothstep(slope_start, ground_end, angle_deg)
    cliff = smoothstep(cliff_start, slope_end, angle_deg)
    slope = 1.0 - ground - cliff
    slope = max(0.0, slope)
    
    # Normalize
    total = ground + slope + cliff
    if total > 0.001:
        return ground/total, slope/total, cliff/total
    return 1.0, 0.0, 0.0
```

### Angle of Repose

Different materials naturally rest at different maximum slope angles:

| Material | Angle of Repose | Notes |
|----------|----------------|-------|
| Dry sand | 30-35 deg | Cannot exist above this angle |
| Wet soil | 35-45 deg | Moisture increases cohesion |
| Gravel | 35-40 deg | Interlocking particles |
| Grass/turf | 40-50 deg | Root systems allow steeper |
| Rock/cliff | 60-90 deg | Solid material, any angle |
| Snow (dry) | 35-45 deg | Avalanche threshold |
| Mud | 15-25 deg | Very low cohesion when wet |

Use these as the "fade-out" angles for each material:

```python
MATERIAL_SLOPE_LIMITS = {
    "sand": {"max_angle": 33.0, "fade_width": 5.0},
    "grass": {"max_angle": 45.0, "fade_width": 8.0},
    "dirt": {"max_angle": 40.0, "fade_width": 6.0},
    "gravel": {"max_angle": 38.0, "fade_width": 5.0},
    "rock": {"max_angle": 90.0, "fade_width": 0.0},  # Exists at any angle
    "snow": {"max_angle": 42.0, "fade_width": 7.0},
    "mud": {"max_angle": 22.0, "fade_width": 4.0},
}
```

### HLSL Slope Blending

```hlsl
// Smooth slope factor from world normal
float slopeFactor = 1.0 - saturate(normalWS.y);  // 0 = flat, 1 = vertical

// Smoothstep transitions instead of hard if/else
float groundWeight = 1.0 - smoothstep(0.3, 0.45, slopeFactor);
float cliffWeight = smoothstep(0.6, 0.75, slopeFactor);
float slopeWeight = 1.0 - groundWeight - cliffWeight;
slopeWeight = max(0.0, slopeWeight);
```

---

## 4. Curvature-Based Detail

**Confidence: HIGH** -- Well-established technique in terrain tools and shaders.

### Concavity and Convexity

Curvature is the second derivative of elevation. It determines surface shape:

| Curvature | Shape | Material Effect |
|-----------|-------|-----------------|
| Negative (concave) | Valley, crevice, crack | Moss, dirt accumulation, water staining, mud |
| Zero (flat) | Planar surface | Base material unchanged |
| Positive (convex) | Ridge, peak, edge | Wear, exposed rock, snow accumulation, lichen |

### Computing Curvature from Heightmap (Laplacian)

The Laplacian filter approximates the second derivative:

```python
def compute_curvature(heightmap, cell_size=1.0):
    """Compute curvature using Laplacian filter.
    
    Args:
        heightmap: 2D numpy array of elevation values
        cell_size: distance between cells
    
    Returns:
        2D array: positive = convex, negative = concave
    """
    import numpy as np
    # Laplacian kernel
    kernel = np.array([
        [0,  1, 0],
        [1, -4, 1],
        [0,  1, 0]
    ]) / (cell_size * cell_size)
    
    from scipy.ndimage import convolve
    curvature = convolve(heightmap, kernel, mode='reflect')
    return curvature
```

**GPU-friendly approach (Wronski/NVIDIA):** Use the mipmap chain as a Laplacian pyramid approximation. Sample at current mip and coarser mip, compute difference. This runs in real-time with no precomputation.

### Curvature-Driven Material Modulation

```python
def modulate_weights_by_curvature(
    weights: dict[str, float],
    curvature: float,
    concavity_boost: str = "moss",      # Material boosted in concave areas
    convexity_boost: str = "rock",       # Material boosted on ridges
    strength: float = 0.3,
) -> dict[str, float]:
    """Adjust material weights based on local curvature."""
    if curvature < -0.01:  # Concave
        intensity = min(1.0, abs(curvature) * 10.0) * strength
        if concavity_boost in weights:
            weights[concavity_boost] += intensity
    elif curvature > 0.01:  # Convex
        intensity = min(1.0, curvature * 10.0) * strength
        if convexity_boost in weights:
            weights[convexity_boost] += intensity
    
    # Re-normalize
    total = sum(weights.values())
    return {k: v/total for k, v in weights.items()}
```

### Terrain Ambient Occlusion

Heightmap-based AO: if the average neighborhood elevation exceeds the center pixel, that pixel is more occluded (darker). This is equivalent to the concavity map.

```python
def heightmap_ao(heightmap, radius=3):
    """Approximate AO from heightmap using neighborhood average."""
    import numpy as np
    from scipy.ndimage import uniform_filter
    avg = uniform_filter(heightmap, size=radius*2+1, mode='reflect')
    ao = 1.0 - np.clip((avg - heightmap) * 2.0, 0.0, 1.0)
    return ao
```

---

## 5. Flow/Erosion-Driven Materials

**Confidence: HIGH** -- Gaea documentation and terrain generation literature.

### Erosion Data Maps

Terrain erosion simulation produces several data maps that drive material assignment:

| Map | What It Contains | Material Effect |
|-----|-----------------|-----------------|
| **Wear map** | Areas where material was removed by water | Exposed bedrock, harder substrate |
| **Deposit map** | Areas where sediment accumulated | Sand, silt, sediment, alluvial material |
| **Flow map** | Water flow paths and accumulation | Water staining, algae, wet surfaces, darker material |
| **Wetness map** | Moisture saturation levels | Reduced roughness, darker albedo, mud |
| **Velocity map** | Water speed at each point | Determines erosion intensity |

### How Gaea Uses These for Texturing

Gaea's pipeline:
1. **Erosion node** simulates hydraulic erosion, outputs terrain + data maps
2. **Flow node** generates independent flow data via rainfall simulation
3. **Data maps are decoupled** -- can be generated anywhere in the graph without modifying terrain geometry
4. **Biome node** combines water maps with terrain analysis to create zone masks
5. Color ramps/gradients are "flowed into" masks to produce final texture

### Implementation Pattern

```python
def compute_erosion_weights(
    wear: float,          # 0-1, how eroded this point is
    deposit: float,       # 0-1, how much sediment deposited
    flow: float,          # 0-1, water flow intensity
    wetness: float,       # 0-1, moisture level
) -> dict[str, float]:
    """Convert erosion data into material weight adjustments."""
    adjustments = {}
    
    # Wear exposes bedrock
    if wear > 0.3:
        adjustments['exposed_rock'] = (wear - 0.3) * 1.4
    
    # Deposits add sediment/sand
    if deposit > 0.2:
        adjustments['sediment'] = (deposit - 0.2) * 1.25
    
    # Flow paths get water staining
    if flow > 0.4:
        adjustments['water_stain'] = (flow - 0.4) * 1.5
    
    # Wetness darkens and smooths materials
    if wetness > 0.5:
        adjustments['mud'] = (wetness - 0.5) * 2.0
    
    return adjustments
```

### Integration with Splatmap

Erosion weights are additive modifiers to the base slope/height splatmap:

```python
def combine_slope_and_erosion_weights(
    slope_weights: tuple[float, ...],   # From slope analysis
    erosion_adj: dict[str, float],      # From erosion analysis
    erosion_strength: float = 0.4,      # How much erosion influences final result
) -> tuple[float, ...]:
    """Blend slope-based weights with erosion-driven adjustments."""
    # Apply erosion as weighted overlay
    combined = list(slope_weights)
    for channel, adjustment in erosion_adj.items():
        idx = CHANNEL_MAP.get(channel, -1)
        if idx >= 0:
            combined[idx] += adjustment * erosion_strength
    
    # Re-normalize
    total = sum(combined)
    return tuple(c / total for c in combined) if total > 0.001 else slope_weights
```

---

## 6. Triplanar Projection

**Confidence: HIGH** -- Extensively documented, already partially implemented in our shader.

### How It Works

1. Project texture from 3 orthogonal planes (XY, XZ, YZ) using world-space coordinates
2. Compute blend weights from surface normal: `abs(normal)` normalized
3. Sample texture 3 times, blend results by weights

```hlsl
// Blend weights from normal
float3 blend = pow(abs(normalWS), _TriplanarSharpness);
blend /= dot(blend, float3(1, 1, 1));

// Sample from 3 projections
half4 xProj = SAMPLE_TEXTURE2D(tex, samp, posWS.yz * tiling);
half4 yProj = SAMPLE_TEXTURE2D(tex, samp, posWS.xz * tiling);
half4 zProj = SAMPLE_TEXTURE2D(tex, samp, posWS.xy * tiling);

half4 result = xProj * blend.x + yProj * blend.y + zProj * blend.z;
```

### Why Essential for Cliff Faces

On slopes > ~45 degrees, UV-based texturing stretches severely because the UV projection (usually top-down for terrain) becomes nearly parallel to the surface. Triplanar eliminates this entirely.

### Performance Cost

| Approach | Texture Samples | Relative Cost |
|----------|----------------|---------------|
| Standard UV | 1 per map | 1x |
| Triplanar (full) | 3 per map | 3x |
| Adaptive triplanar | 1-3 per map | 1.5-2x average |

**Optimization -- Adaptive triplanar:** Only apply triplanar on steep surfaces. Our existing shader does this:

```hlsl
float steepness = 1.0 - absNormal.y;
bool useTriplanar = _TriplanarEnabled > 0.5 && steepness > 0.5;
```

This is correct. Recommend lowering the threshold to `steepness > 0.4` for smoother transition, or using a smoothstep blend instead of a binary switch.

### Blender Implementation

Blender has built-in "Box" projection mode on Image Texture nodes:
- Set projection to "Box" instead of "Flat"
- Use "Blend" parameter to control transition softness (0 = sharp, 1 = gradual)
- Connect Texture Coordinate > Object output to the vector input

For procedural textures (Noise, Voronoi, etc.), use Object coordinates directly -- they are already 3D and do not suffer from UV stretching.

### Normal Map Handling in Triplanar

Normal maps require special treatment. Use UDN (Unreal Derivative Normal) blending:

```hlsl
float3 BlendTriplanarNormal(float3 mappedNormal, float3 surfaceNormal) {
    float3 n;
    n.xy = mappedNormal.xy + surfaceNormal.xy;
    n.z = mappedNormal.z * surfaceNormal.z;
    return n;
}
```

---

## 7. PBR Terrain Material Values

**Confidence: HIGH** -- Based on physicallybased.info and Adobe PBR Guide.

### Ground Truth Reference Values

All albedo values in **linear RGB** (0-1 range). Roughness on 0-1 scale.

| Material | Albedo (Linear) | Roughness | Metallic | Notes |
|----------|-----------------|-----------|----------|-------|
| **Short green grass** | 0.20 - 0.25 | 0.75 - 0.90 | 0.0 | R: 0.105, G: 0.133, B: 0.041 (from physicallybased.info) |
| **Tall wild grass** | 0.16 - 0.18 | 0.80 - 0.95 | 0.0 | Drier, more yellow |
| **Dry grass** | 0.25 - 0.35 | 0.85 - 0.95 | 0.0 | Yellow-brown |
| **Bare soil** | 0.15 - 0.20 | 0.85 - 1.00 | 0.0 | Dark when wet (~0.08) |
| **Dry clay** | 0.15 - 0.35 | 0.80 - 0.95 | 0.0 | Varies by color |
| **Sandy soil** | 0.25 - 0.45 | 0.85 - 1.00 | 0.0 | Lighter tones |
| **Sand** | 0.35 - 0.50 | 0.80 - 0.95 | 0.0 | R: 0.44, G: 0.39, B: 0.23 |
| **Rock (granite)** | 0.30 - 0.45 | 0.60 - 0.85 | 0.0 | Gray spectrum |
| **Rock (dark/basalt)** | 0.10 - 0.20 | 0.65 - 0.80 | 0.0 | Dark volcanic |
| **Rock (sandstone)** | 0.30 - 0.50 | 0.70 - 0.90 | 0.0 | Warm tones |
| **Wet rock** | 0.05 - 0.15 | 0.10 - 0.30 | 0.0 | Dramatically lower roughness |
| **Fresh snow** | 0.80 - 0.90 | 0.30 - 0.50 | 0.0 | R/G/B: ~0.85 (physicallybased.info) |
| **Packed snow** | 0.60 - 0.75 | 0.40 - 0.60 | 0.0 | Slightly rougher/darker |
| **Ice** | 0.90 - 1.00 | 0.05 - 0.15 | 0.0 | Very smooth, IOR 1.31 |
| **Mud (wet)** | 0.08 - 0.15 | 0.10 - 0.30 | 0.0 | Very dark, specular |
| **Mud (dry/cracked)** | 0.15 - 0.25 | 0.85 - 1.00 | 0.0 | Matte surface |
| **Gravel** | 0.20 - 0.35 | 0.85 - 1.00 | 0.0 | High roughness |
| **Moss** | 0.08 - 0.15 | 0.80 - 0.95 | 0.0 | Dark green, matte |
| **Concrete** | 0.45 - 0.55 | 0.70 - 0.90 | 0.0 | R/G/B: ~0.51 |

### VeilBreakers Dark Fantasy Adjustment

VeilBreakers palette rule: environment saturation never exceeds 40%, value range 10-50%. Apply these modifiers to ground truth values:

```python
def veilbreakers_adjust(albedo_rgb, saturation_cap=0.40, value_range=(0.10, 0.50)):
    """Adjust PBR values to VeilBreakers dark fantasy palette."""
    import colorsys
    r, g, b = albedo_rgb
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(s, saturation_cap)
    v = max(value_range[0], min(value_range[1], v))
    return colorsys.hsv_to_rgb(h, s, v)
```

### Wetness Modulation

When surfaces get wet, their PBR properties change predictably:

```python
def apply_wetness(albedo, roughness, wetness_factor):
    """Modify PBR values based on wetness (0-1)."""
    # Wet surfaces are darker (albedo reduced by up to 50%)
    wet_albedo = albedo * (1.0 - wetness_factor * 0.5)
    # Wet surfaces are smoother (roughness approaches 0.1)
    wet_roughness = roughness * (1.0 - wetness_factor * 0.7) + 0.1 * wetness_factor
    return wet_albedo, wet_roughness
```

---

## 8. Macro-Variation (Tiling Break-Up)

**Confidence: HIGH** -- Standard AAA technique, well-documented.

### The Tiling Problem

All tiled terrain textures repeat visibly at medium-to-far distances. This destroys realism instantly.

### Solution Layers

| Technique | Scale | Purpose | Performance |
|-----------|-------|---------|-------------|
| **Macro color tint** | 50-200m per tile | Large-scale color variation | Very cheap |
| **Rotation tiling** | 2x base texture | Break repetition patterns | 2x sampling |
| **Stochastic texturing** | Per-pixel | Eliminate tiling entirely | Moderate |
| **Distance detail reduction** | LOD-based | Switch to simpler textures at range | Cheap |
| **Hex grid tiling** | Per-hex cell | Randomized offset per cell | Moderate |

### Macro Color Tint (Recommended First Step)

Apply a large-scale, low-frequency color texture over the entire terrain. This is the single most impactful anti-tiling technique.

**How to create a macro texture:**
1. Take satellite/aerial photo of similar terrain type
2. Blur heavily (remove all high-frequency detail)
3. Desaturate partially (keep subtle color variation)
4. Apply as multiplicative overlay at very large scale (entire terrain or large chunks)

```hlsl
// HLSL macro variation
half3 macroColor = SAMPLE_TEXTURE2D(_MacroTex, sampler_MacroTex, input.uv * _MacroScale).rgb;
// Blend with base material color (multiply mode)
albedo.rgb *= lerp(float3(1,1,1), macroColor, _MacroStrength);
```

**Parameters:**
- `_MacroScale`: 0.001 - 0.01 (one tile covers 100-1000 world units)
- `_MacroStrength`: 0.1 - 0.4 (subtle is better)

### Procedural Macro Variation (No Texture Needed)

Use low-frequency noise as macro variation:

```hlsl
// Procedural macro tint using world position
float macro = frac(sin(dot(posWS.xz * 0.003, float2(12.9898, 78.233))) * 43758.5453);
float3 macroTint = lerp(float3(0.85, 0.9, 0.85), float3(1.1, 1.05, 0.95), macro);
albedo.rgb *= macroTint;
```

### Distance-Based Detail

At far distances, replace tiled detail textures with a single low-res "satellite view" texture:

```hlsl
float dist = length(posWS - _WorldSpaceCameraPos);
float detailFade = saturate((dist - _DetailFadeStart) / (_DetailFadeEnd - _DetailFadeStart));
albedo = lerp(detailAlbedo, macroAlbedo, detailFade);
```

---

## Architecture Patterns

### Recommended Weight Computation Pipeline

```
Input Terrain Mesh
       |
       v
+------------------+
| Terrain Analysis  |  (Pure Python, no bpy)
|  - Slope angles   |
|  - Height percentile |
|  - Curvature      |
|  - Erosion maps   |
|  - Moisture       |
+------------------+
       |
       v
+------------------+
| Weight Computation |  (smoothstep blending)
|  - Slope weights  |
|  - Height weights |
|  - Curvature mod  |
|  - Erosion mod    |
|  - Exclusion masks|
+------------------+
       |
       v
+------------------+
| Sum-to-One        |  (normalize all channels)
| Normalization     |
+------------------+
       |
       v
+------------------+       +------------------+
| Vertex Colors /   |       | Shader (HLSL)    |
| Splatmap Texture  | ----> |  - Height blend   |
+------------------+       |  - Triplanar      |
                           |  - Macro variation |
                           +------------------+
```

### Blender Side (Python)

The terrain analysis and splatmap weight computation should be pure Python (no bpy), operating on mesh data dictionaries. The `auto_assign_terrain_layers` function needs these changes:

1. Replace linear interpolation with smoothstep
2. Add curvature input
3. Add erosion/flow map inputs
4. Add per-material angle-of-repose limits
5. Add height-blend support (requires per-material height values)

### Unity/Shader Side (HLSL)

The `generate_terrain_blend_shader` already has the right structure. Enhancements needed:

1. Add macro variation texture/noise
2. Add smooth triplanar blending (not binary switch)
3. Add distance-based LOD for texture detail
4. Support for 8-layer (2 splatmap) setup

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Splatmap normalization | Custom normalizer per call site | Centralized `normalize_splatmap()` | Sum-to-one bugs are subtle |
| Height blend algorithm | New blend formula | Standard max-height-threshold algorithm | Proven across industry |
| Curvature computation | Manual neighbor sampling | scipy.ndimage Laplacian or np convolution | Edge cases, performance |
| Triplanar blending | Custom normal transform | UDN normal blending (standard) | Normal map math is error-prone |
| PBR value clamping | Per-material hardcoded clamps | Validated PBR range table + auto-clamp | Prevents impossible values |

---

## Common Pitfalls

### Pitfall 1: Non-Normalized Splatmap Weights
**What goes wrong:** Weights exceed 1.0 or are less than 1.0, causing overbright or too-dark terrain.
**Why it happens:** Adding curvature/erosion modifiers without re-normalizing.
**How to avoid:** Always normalize after ANY modification to weights. Use a single `normalize_splatmap()` function as final step.
**Warning signs:** Bright spots, dark seams, or flickering at terrain transitions.

### Pitfall 2: Hard Threshold Banding
**What goes wrong:** Visible lines at exactly 30 or 60 degrees where material abruptly changes.
**Why it happens:** Using `if angle < 30` instead of smooth interpolation.
**How to avoid:** Always use smoothstep with overlapping transition ranges (at least 5-10 degree overlap).
**Warning signs:** Horizontal lines visible on hillsides following contour lines.

### Pitfall 3: Triplanar Seams at Exactly 45 Degrees
**What goes wrong:** Binary triplanar switching creates a visible seam.
**Why it happens:** Using `steepness > 0.5` as a hard boolean.
**How to avoid:** Use smoothstep blend between UV and triplanar, not a boolean switch.
**Warning signs:** A ring-like artifact around hills at constant slope angle.

### Pitfall 4: Height Map Mismatch
**What goes wrong:** Height blend produces unexpected results (wrong material wins).
**Why it happens:** Height maps have inconsistent value ranges (one 0-0.5, another 0-1.0).
**How to avoid:** Normalize all height maps to consistent 0-1 range. Document expected range.
**Warning signs:** One material always dominates regardless of splatmap weights.

### Pitfall 5: Macro Variation Too Strong
**What goes wrong:** Terrain looks splotchy and unnatural from a distance.
**Why it happens:** Macro tint strength too high or frequency too high.
**How to avoid:** Keep macro strength < 0.3, scale very large (100+ world units per tile).
**Warning signs:** Visible color patches that don't match terrain geometry.

### Pitfall 6: Ignoring Wetness on Roughness
**What goes wrong:** Wet areas look identical to dry areas.
**Why it happens:** Only modifying albedo for wetness, forgetting roughness.
**How to avoid:** Always modify BOTH albedo (darker) and roughness (smoother) together.
**Warning signs:** Rain/water areas that look uniformly matte.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard slope thresholds | Smoothstep continuous blending | ~2015+ | Eliminates banding artifacts |
| Linear texture lerp | Height-based blend | ~2012+ (CryEngine 3) | Natural transitions |
| UV-only terrain | Triplanar + UV hybrid | ~2010+ | Cliff texturing solved |
| Single tiling | Macro variation + stochastic | ~2016+ | Eliminates tiling at distance |
| Flat splatmap | Curvature/erosion-driven splats | ~2018+ (Gaea/WM) | Physically motivated material placement |
| 4-layer limit | Texture arrays + virtual texturing | ~2020+ | 16-256 layers |

---

## Sources

### Primary (HIGH confidence)
- [physicallybased.info](https://physicallybased.info/) - PBR albedo values for grass, sand, snow, ice, concrete
- [Catlike Coding - Triplanar Mapping](https://catlikecoding.com/unity/tutorials/advanced-rendering/triplanar-mapping/) - Complete triplanar implementation with normal handling
- [Gaea Documentation - Flow](https://docs.quadspinner.com/Reference/Data/Flow.html) - Flow map generation and erosion data
- [Gaea Documentation - Procedural Textures](https://docs.quadspinner.com/Guide/Using-Gaea/Color-Production.html) - Data-driven terrain coloring
- [Rastertek Tutorial 14](https://rastertek.com/tertut14.html) - Slope-based texturing implementation

### Secondary (MEDIUM confidence)
- [Advanced Terrain Texture Splatting - GameDev.net](https://www.gamedev.net/tutorials/programming/graphics/advanced-terrain-texture-splatting-r3287/) - Multi-splatmap, height blending
- [Polycount PBR Value Lists](https://polycount.com/discussion/136216/pbr-value-lists) - Community-verified PBR ranges
- [Terrain3D Shader Design](https://terrain3d.readthedocs.io/en/latest/docs/shader_design.html) - Height blend implementation
- [Ben Golus - Triplanar Normal Mapping](https://bgolus.medium.com/normal-mapping-for-a-triplanar-shader-10bf39dca05a) - Correct normal transforms
- [Jason Booth - Stochastic Texturing](https://medium.com/@jasonbooth_86226/stochastic-texturing-3c2e58d76a14) - Tiling break techniques
- [Jason Booth - Improved Triplanar](https://medium.com/@jasonbooth_86226/improved-triplanar-projections-b990a49637f9) - Optimized triplanar

### Tertiary (LOW confidence)
- [Scrawk/Terrain-Topology-Algorithms](https://github.com/Scrawk/Terrain-Topology-Algorithms) - Unity terrain curvature computation (not verified against current Unity version)

---

## Metadata

**Confidence breakdown:**
- Splatmap fundamentals: HIGH - Industry standard, 20+ years established
- Height blending: HIGH - Algorithm already in our shader, well-documented
- Smooth slope transitions: HIGH - Smoothstep is mathematically well-defined
- Curvature computation: HIGH - Standard Laplacian filter
- Erosion-driven materials: MEDIUM-HIGH - Gaea docs partially incomplete for v1.3
- Triplanar projection: HIGH - Multiple authoritative sources
- PBR values: HIGH - physicallybased.info is authoritative
- Macro variation: HIGH - Well-documented AAA technique

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable techniques, slow-moving domain)
