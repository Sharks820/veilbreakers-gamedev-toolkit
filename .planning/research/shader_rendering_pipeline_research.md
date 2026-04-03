# Shader, Rendering & Visual Pipeline Research for VeilBreakers (Unity 6 URP)

**Researched:** 2026-04-02
**Domain:** Unity 6 URP shaders, rendering pipeline, post-processing, texture management, GPU profiling
**Confidence:** HIGH (official Unity 6 docs verified, cross-referenced with existing codebase)

---

## Summary

VeilBreakers requires a comprehensive shader and rendering pipeline for a dark fantasy action RPG in Unity 6 URP. The existing toolkit already has foundational shaders (corruption, dissolve, force field, water, foliage, outline, damage overlay, hair anisotropic, terrain blend, ice crystal, SSS skin, parallax eye) but they need significant upgrades: the water shader lacks Gerstner waves/depth/caustics, vegetation lacks GPU instancing, and several critical shaders are missing entirely (building weathering, weapon/armor, full character set, decals, volumetric fog). The rendering pipeline needs quality-tiered URP Assets, shader warmup via PSO tracing (Unity 6's new `GraphicsStateCollection` API), aggressive variant stripping, and a tuned post-processing stack with dark fantasy color grading.

**Primary recommendation:** Build all custom shaders as hand-written HLSL (not Shader Graph) for maximum control and SRP Batcher compatibility. Use the existing `generate_arbitrary_shader` template as the base. Create 3 quality-tiered URP Assets (Low/Medium/High). Implement PSO tracing for shader warmup. Configure post-processing for dark, desaturated, high-contrast fantasy aesthetic.

---

## 1. Shader Compilation and Warmup

### 1.1 Shader Variant Stripping

**Confidence: HIGH** -- Official Unity 6 docs verified.

Shader variant stripping reduces build size, load times, and runtime memory. Unity 6 URP provides both automatic and manual stripping.

**Settings Location:** Graphics Settings > Shader Stripping

| Setting | Location | Effect |
|---------|----------|--------|
| Strip Unused Variants | URP Graphics Settings | Removes disabled-feature variants across all URP Assets |
| Strip Unused Post Processing Variants | URP Graphics Settings | Strips Volume Overrides not used in project |
| Strip Screen Coord Override Variants | URP Graphics Settings | Removes cluster display variants |
| Export Shader Variants | Additional Shader Stripping | Generates JSON report for analysis |

**Feature-specific stripping via URP Asset Inspector:**

| URP Asset Toggle | Keyword Stripped |
|------------------|-----------------|
| Disable Additional Lights | `_ADDITIONAL_LIGHTS` |
| Disable Main Light Cast Shadows | `_MAIN_LIGHT_SHADOWS` |
| Disable Additional Light Shadows | `_ADDITIONAL_LIGHT_SHADOWS` |
| Disable Soft Shadows | `_SHADOWS_SOFT` |
| Disable Terrain Holes | `_ALPHATEST_ON` |
| Disable Accurate G-buffer Normals | `_GBUFFER_NORMALS_OCT` |
| Disable Fast sRGB/Linear | `_USE_FAST_SRGB_LINEAR_CONVERSION` |

**Renderer Feature removal strips:**
- Remove Ambient Occlusion feature: strips `_SCREEN_SPACE_OCCLUSION`
- Remove Decals feature: strips `_DBUFFER_MRT` keywords
- Remove Native Render Pass: strips `_RENDER_PASS_ENABLED`

**Custom stripping via `IPreprocessShaders`:**
```csharp
// Editor script for advanced stripping
using UnityEditor.Build;
using UnityEditor.Rendering;

class VBShaderStripper : IPreprocessShaders
{
    public int callbackOrder => 0;

    public void OnProcessShader(Shader shader, ShaderSnippetData snippet, IList<ShaderCompilerData> data)
    {
        // Strip variants for features VeilBreakers never uses
        for (int i = data.Count - 1; i >= 0; i--)
        {
            // Example: strip point light cookie variants if not used
            if (data[i].shaderKeywordSet.IsEnabled(new ShaderKeyword("_LIGHT_COOKIES")))
                data.RemoveAt(i);
        }
    }
}
```

**VeilBreakers-specific stripping candidates:**
- Screen coord override (no cluster display)
- Light cookies (if not used)
- Deferred rendering keywords (VeilBreakers uses Forward/Forward+)
- Point light shadows if only using spot/directional

### 1.2 Shader Warmup / Prewarming

**Confidence: HIGH** -- Unity 6 official docs verified.

Shader stutters happen when Unity compiles a shader variant for the first time at runtime. Unity 6 introduces PSO (Pipeline State Object) tracing as the primary solution.

**Method 1: PSO Tracing (Unity 6 -- RECOMMENDED for DX12/Vulkan/Metal)**

```csharp
// Record phase: run during QA play-through
GraphicsStateCollection gsc = new GraphicsStateCollection();
gsc.BeginTrace();
// ... play through all gameplay scenarios ...
gsc.EndTrace();
gsc.SendToEditor(); // exports .graphicsstate file

// Warmup phase: load screen
GraphicsStateCollection loaded = LoadGraphicsStateCollection("path/to/collection.graphicsstate");
JobHandle handle = loaded.WarmUpProgressively(maxMillisecondsPerFrame: 2); // async, won't block
// Wait for handle.IsComplete or spread across frames
```

**Method 2: ShaderVariantCollection (DX11/OpenGL -- LEGACY)**

```csharp
// Add to Graphics Settings > Preloaded Shaders, OR:
ShaderVariantCollection svc = Resources.Load<ShaderVariantCollection>("VBShaderVariants");
svc.WarmUp(); // blocks until complete -- do during loading screen
```

**Method 3: Shader.WarmupAllShaders() (NUCLEAR -- use as last resort)**

```csharp
Shader.WarmupAllShaders(); // warms ALL shaders in memory, expensive
```

**Profiler markers to watch for stutter sources:**
- `Shader.CreateGPUProgram` -- GPU shader variant creation
- `CreateGraphicsGraphicsPipelineImpl` -- PSO creation

**VeilBreakers recommendation:** Use PSO tracing (Method 1) as primary. During development, add `Shader.CreateGPUProgram` as a Profiler alert. Build a QA automation script that exercises all shader/material combinations to populate the `.graphicsstate` file.

### 1.3 Shader Graph vs Hand-Written HLSL

**Confidence: HIGH**

| Criterion | Shader Graph | Hand-Written HLSL |
|-----------|-------------|-------------------|
| Iteration speed | Fast visual iteration | Slower, text-based |
| Performance control | Limited, generates boilerplate | Full control over instructions |
| SRP Batcher compat | Automatic | Manual (must follow CBUFFER rules) |
| Multi-pass | Difficult, breaks SRP Batcher | Full control |
| Custom lighting | Limited to Custom Function nodes | Full access to URP lighting API |
| Version control | Binary .shadergraph files | Text .shader files, clean diffs |
| Template generation | Cannot generate programmatically | **Can generate from Python templates** |

**VeilBreakers decision: Hand-written HLSL.** The existing toolkit generates shaders from Python templates (shader_templates.py), which is incompatible with Shader Graph. All 12 existing shaders use hand-written HLSL and this should continue.

**SRP Batcher compatibility rules (CRITICAL):**
1. ALL material properties in a single `CBUFFER_START(UnityPerMaterial)` block
2. ALL built-in engine properties in `CBUFFER_START(UnityPerDraw)` block
3. Single-pass preferred (multi-pass breaks batching)
4. Use `#pragma multi_compile` sparingly -- each keyword doubles variants

### 1.4 Common Shader Compilation Hitches

| Hitch Source | Cause | Prevention |
|--------------|-------|------------|
| First-use stutter | Shader variant compiled on-demand | PSO tracing + warmup at load |
| Excessive variants | `multi_compile` keyword explosion | Use `shader_feature` for editor-only toggles; strip unused |
| Long build times | Thousands of unused variants | Enable Strip Unused Variants; use `IPreprocessShaders` |
| Mobile thermal throttle | Complex fragment shaders | LOD shaders per quality tier |
| SRP Batcher break | Per-material CBUFFER mismatch | Validate all shaders with Frame Debugger |

---

## 2. Custom Shaders Needed for VeilBreakers

### Existing Shaders (in shader_templates.py)

| Shader | Status | Gaps |
|--------|--------|------|
| Corruption | EXISTS | Needs world-space dissolve, negative light |
| Dissolve | EXISTS | Functional |
| Force Field | EXISTS | Functional |
| Water | EXISTS | Missing: Gerstner waves, depth fog, caustics, foam |
| Foliage | EXISTS | Missing: GPU instancing, better wind model |
| Outline | EXISTS | Functional |
| Damage Overlay | EXISTS | Functional (fullscreen) |
| Arbitrary (configurable) | EXISTS | Template for custom shaders |
| Renderer Feature | EXISTS | Template for custom render passes |
| Anisotropic Hair | EXISTS | Functional (Kajiya-Kay model) |
| Terrain Blend | EXISTS | Height-based blending, needs triplanar for cliffs |
| Ice Crystal | EXISTS | Functional |
| SSS Skin | EXISTS (character_templates) | Pre-integrated SSS |
| Parallax Eye | EXISTS (character_templates) | IOR-based refraction |

### Shaders That Need CREATION or MAJOR UPGRADE

#### 2.1 Terrain Shader (UPGRADE)

Current `generate_terrain_blend_shader` does height-based 4-layer blending but lacks triplanar projection for cliffs.

**Required features:**
- 4 texture layers (albedo + normal + height per layer)
- Height-based blending with smoothstep transitions (EXISTS)
- Triplanar projection for surfaces > 45 degrees (MISSING)
- Splatmap weight input (RGBA channels) (EXISTS)
- Detail normal tiling at close range (MISSING)
- Distance-based LOD that switches to simpler blending far away (MISSING)

**Triplanar implementation pattern:**
```hlsl
// Triplanar sampling for cliff faces
float3 blendWeights = abs(normalWS);
blendWeights = pow(blendWeights, 4.0); // sharpen blend
blendWeights /= dot(blendWeights, 1.0); // normalize

half4 xSample = SAMPLE_TEXTURE2D(_CliffTex, sampler_CliffTex, worldPos.yz * _CliffTiling);
half4 ySample = SAMPLE_TEXTURE2D(_CliffTex, sampler_CliffTex, worldPos.xz * _CliffTiling);
half4 zSample = SAMPLE_TEXTURE2D(_CliffTex, sampler_CliffTex, worldPos.xy * _CliffTiling);
half4 triplanarColor = xSample * blendWeights.x + ySample * blendWeights.y + zSample * blendWeights.z;

// Blend between splatmap result and triplanar based on slope
float slopeAngle = acos(saturate(dot(normalWS, float3(0,1,0))));
float triplanarMask = smoothstep(0.6, 0.8, slopeAngle / 1.5708); // 0.6-0.8 radians = ~34-46 degrees
finalColor = lerp(splatmapResult, triplanarColor, triplanarMask);
```

#### 2.2 Water Shader (MAJOR UPGRADE)

Current water shader has basic sin/cos wave displacement. Needs complete rewrite.

**Required features:**

| Feature | Current | Required |
|---------|---------|----------|
| Waves | sin/cos displacement | Multi-octave Gerstner waves |
| Depth | None | Depth-based color/opacity gradient |
| Foam | None | Shore foam (depth-based) + wave crest foam |
| Caustics | None | Projected caustics on underwater surfaces |
| Flow | None | Flow map support for rivers |
| Refraction | Fresnel approximation only | Scene color distortion via grab pass |
| Reflection | None | Planar or SSR reflection |

**Gerstner wave implementation:**
```hlsl
// Gerstner wave function (sum multiple for realism)
float3 GerstnerWave(float4 wave, float3 p, inout float3 tangent, inout float3 binormal)
{
    float steepness = wave.z;
    float wavelength = wave.w;
    float k = 2.0 * PI / wavelength;
    float c = sqrt(9.8 / k);
    float2 d = normalize(wave.xy);
    float f = k * (dot(d, p.xz) - c * _Time.y);
    float a = steepness / k;

    tangent += float3(-d.x * d.x * steepness * sin(f), d.x * steepness * cos(f), -d.x * d.y * steepness * sin(f));
    binormal += float3(-d.x * d.y * steepness * sin(f), d.y * steepness * cos(f), -d.y * d.y * steepness * sin(f));

    return float3(d.x * a * cos(f), a * sin(f), d.y * a * cos(f));
}
```

**Depth fog pattern:**
```hlsl
float sceneDepth = LinearEyeDepth(SampleSceneDepth(screenUV), _ZBufferParams);
float waterDepth = sceneDepth - input.screenPos.w;
float depthFade = 1.0 - exp(-waterDepth * _DepthFogDensity);
half3 depthColor = lerp(_ShallowColor.rgb, _DeepColor.rgb, saturate(depthFade));
```

**Caustics pattern:**
```hlsl
// Sample caustics texture twice with offset for chromatic aberration
float2 causticUV = worldPosBelow.xz * _CausticScale;
float2 offset1 = _Time.y * _CausticSpeed * float2(1, 0.5);
float2 offset2 = _Time.y * _CausticSpeed * float2(-0.5, 0.7);
float r = SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, causticUV + offset1).r;
float g = SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, causticUV + offset2).g;
float b = SAMPLE_TEXTURE2D(_CausticTex, sampler_CausticTex, causticUV * 1.1 + offset1 * 0.8).b;
half3 caustics = half3(r, g, b) * _CausticIntensity * (1.0 - depthFade);
```

#### 2.3 Corruption/Veil Shader (UPGRADE)

Current corruption shader is a simple lerp toward a corruption color with noise veins. Needs world-space dissolve and "negative light" (light absorption).

**Required features:**
- World-space dissolve boundary (the Veil expanding across terrain) using worldPos.y or distance from a corruption origin point
- Negative light emission: areas touched by corruption darken surrounding lighting instead of emitting
- Edge glow at the boundary between normal and corrupted world
- Animated tendrils using layered noise in world space
- Corruption overlay that works on ANY material (via renderer feature / screen-space pass)

**World-space dissolve pattern:**
```hlsl
float worldDist = distance(input.positionWS, _VeilOrigin.xyz);
float veilBoundary = smoothstep(_VeilRadius - _VeilEdgeWidth, _VeilRadius, worldDist);
// veilBoundary = 0 inside corruption, 1 outside
// Invert for corruption amount: 1 = fully corrupted
float corruptAmount = 1.0 - veilBoundary;
```

**Negative light (light absorption) pattern:**
```hlsl
// In fragment shader, reduce received lighting based on corruption
float lightAbsorption = corruptAmount * _AbsorptionStrength;
half3 finalDiffuse = diffuse * (1.0 - lightAbsorption);
// Optionally emit a dim, sickly glow
half3 corruptGlow = _CorruptionColor.rgb * corruptAmount * _GlowIntensity * pulse;
```

#### 2.4 Vegetation Shader (UPGRADE)

Current foliage shader has basic wind sway but lacks GPU instancing support and proper alpha handling.

**Required features:**
- GPU instancing compatible (DOTS/Hybrid Renderer path OR SRP Batcher path)
- Alpha-to-coverage instead of alpha cutout (reduces aliasing on vegetation edges)
- Multi-octave wind: trunk sway + branch secondary + leaf flutter
- Vertex color channels: R=wind weight, G=phase offset, B=stiffness
- Subsurface scattering approximation for back-lit leaves (already partially exists)
- Billboard LOD for distant trees

**GPU Instancing vs SRP Batcher decision:**

For vegetation specifically, GPU instancing is preferred over SRP Batcher because vegetation typically uses many identical meshes (same tree/grass prefab) with the same material. SRP Batcher is better for varied materials.

```hlsl
// Enable GPU instancing
#pragma multi_compile_instancing
#pragma instancing_options renderinglayer

// Instance properties that vary per-instance
UNITY_INSTANCING_BUFFER_START(Props)
    UNITY_DEFINE_INSTANCED_PROP(float, _WindPhaseOffset)
    UNITY_DEFINE_INSTANCED_PROP(float, _WindScale)
UNITY_INSTANCING_BUFFER_END(Props)
```

**Alpha-to-coverage (better than alpha cutout for foliage):**
```hlsl
// In SubShader tags:
Tags { "RenderType"="TransparentCutout" "Queue"="AlphaTest" }
AlphaToMask On  // Requires MSAA enabled

// In fragment:
half alpha = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, input.uv).a;
// With MSAA + AlphaToMask, edge pixels get partial coverage samples
// producing smoother edges than hard clip()
```

#### 2.5 Building Shader (NEW -- MISSING)

**Required features:**
- Base PBR (albedo, normal, metallic/smoothness)
- Weathering: procedural dirt/rain streaks based on world-space Y gradient and cavity map
- Moss/vine growth: world-space Y gradient with noise mask, increasing in damp/shadow areas
- Wet surfaces: increase smoothness, darken albedo when _RainAmount > 0
- Damage states: blend toward cracked/broken texture using a mask
- SRP Batcher compatible

**Weathering pattern:**
```hlsl
// Height-based dirt accumulation
float heightFactor = saturate((input.positionWS.y - _DirtStartHeight) / _DirtGradient);
float dirtMask = (1.0 - heightFactor) * noise(input.positionWS.xz * _DirtScale);

// Rain streaks -- vertical world-space UV
float2 streakUV = float2(input.positionWS.x * _StreakDensity, input.positionWS.y * 2.0);
float streaks = SAMPLE_TEXTURE2D(_StreakTex, sampler_StreakTex, streakUV).r;
float streakMask = streaks * saturate(dot(normalWS, float3(0, 0, 1))); // Only on vertical faces

// Moss growth -- upward-facing surfaces at low height
float mossFacing = saturate(dot(normalWS, float3(0, 1, 0)) - 0.3);
float mossNoise = noise(input.positionWS.xz * _MossScale);
float mossMask = mossFacing * mossNoise * _MossAmount;
```

#### 2.6 Weapon/Armor Shader (NEW -- MISSING)

**Required features:**
- High-quality PBR metallic workflow
- Emissive rune channels: texture mask for glowing runes/enchantments, color + intensity per rune set
- Damage states: lerp between pristine and damaged textures (chips, scratches, rust)
- Material tinting for item rarity (common/rare/epic/legendary glow)
- Fresnel rim for selection highlight
- SRP Batcher compatible

```hlsl
Properties
{
    _MainTex ("Albedo", 2D) = "white" {}
    _MetallicGlossMap ("Metallic (R) Smoothness (A)", 2D) = "white" {}
    _BumpMap ("Normal Map", 2D) = "bump" {}
    _EmissionMask ("Rune Emission Mask", 2D) = "black" {}
    _RuneColor ("Rune Color", Color) = (0.2, 0.5, 1.0, 1.0)
    _RuneIntensity ("Rune Intensity", Float) = 2.0
    _RunePulseSpeed ("Rune Pulse Speed", Float) = 1.5
    _DamageAmount ("Damage Amount", Range(0, 1)) = 0
    _DamageTex ("Damage Texture", 2D) = "white" {}
    _RarityGlow ("Rarity Glow Color", Color) = (1, 1, 1, 0)
    _RarityIntensity ("Rarity Glow Intensity", Float) = 0
}
```

#### 2.7 Character Shader Suite

**Existing:** SSS skin (character_templates.py), parallax eye (character_templates.py), anisotropic hair (shader_templates.py)

**Missing shaders:**

| Shader | Purpose | Technique |
|--------|---------|-----------|
| Cloth | Robes, cloaks, fabric | Sheen/velvet BRDF (not metallic), dual-lobe specular |
| Skin detail | Pore-level normal overlay | Micro-detail normal compositing (EXISTS as script, needs shader) |

**Cloth shader pattern:**
```hlsl
// Velvet/sheen BRDF for fabric
float sheenFactor = pow(1.0 - saturate(dot(normalWS, viewDirWS)), _SheenPower);
half3 sheenColor = _SheenTint.rgb * sheenFactor * _SheenIntensity;

// Fabric microstructure via detail normal
half3 detailNormal = UnpackNormal(SAMPLE_TEXTURE2D(_DetailNormal, sampler_DetailNormal, input.uv * _DetailTiling));
half3 finalNormal = BlendNormals(baseNormal, detailNormal);

// Dual-lobe specular (broad + narrow)
float specBroad = pow(saturate(dot(finalNormal, halfDir)), 16.0) * 0.3;
float specNarrow = pow(saturate(dot(finalNormal, halfDir)), 256.0) * 0.7;
```

#### 2.8 VFX Shaders

**Existing:** Corruption, dissolve, force field, ice crystal, damage overlay

**Missing:**

| Shader | Purpose | Key Technique |
|--------|---------|---------------|
| Fire/Flame | Torches, bonfires, spell fire | Scrolling noise layers, emissive, vertex distortion, additive blend |
| Smoke | Environmental smoke, explosion aftermath | Soft particle (depth fade), animated flipbook, alpha erosion |
| Magic particles | Spell casting, buff indicators | Custom vertex stream from Particle System, color over lifetime |
| Corruption particles | Veil corruption spread VFX | World-space noise mask, particle trails |

**Soft particle pattern (critical for smoke/VFX):**
```hlsl
// Depth-based soft particles -- prevents hard edges where particles intersect geometry
float sceneDepth = LinearEyeDepth(SampleSceneDepth(screenUV), _ZBufferParams);
float particleDepth = input.screenPos.w;
float depthDiff = sceneDepth - particleDepth;
float softFade = saturate(depthDiff / _SoftParticleDistance);
finalColor.a *= softFade;
```

#### 2.9 Decal Shader (NEW -- MISSING)

URP has a built-in Decal Renderer Feature. Use it rather than hand-rolling.

**Configuration:**
1. Add Decal Renderer Feature to URP Renderer
2. Use `Shader Graphs/Decal` for decal materials
3. Technique: DBuffer (modifies G-buffer) or Screen Space (overlay)

**Performance considerations:**
- DBuffer decals are cheaper but require DepthNormal prepass
- Limit concurrent decals to ~50-100 via object pooling
- Use texture atlases: put blood/scorch/corruption into one atlas, select via UV offset
- GPU instancing for same-material decals

**VeilBreakers decal types:**
| Type | Trigger | Fade Time | Atlas Region |
|------|---------|-----------|--------------|
| Blood splatter | Melee hit | 30-60s | Atlas row 0 |
| Scorch mark | Fire spell | 60-120s | Atlas row 1 |
| Corruption stain | Veil corruption | Persistent | Atlas row 2 |
| Ice patch | Frost spell | 15-30s | Atlas row 3 |
| Footprints | Player/NPC movement | 10-20s | Atlas row 4 |

#### 2.10 Fog Shader (NEW -- MISSING)

URP does not have built-in volumetric fog (that is HDRP only). Must implement via custom Renderer Feature.

**Implementation approach: Height + Distance Fog via ScriptableRendererFeature**

```hlsl
// Height fog component
float heightFog = exp(-max(0, positionWS.y - _FogBaseHeight) * _FogHeightFalloff);

// Distance fog component  
float dist = length(positionWS - _WorldSpaceCameraPos);
float distFog = 1.0 - exp(-dist * _FogDensity);

// Combined fog factor
float fog = saturate(heightFog * distFog);

// Corruption fog variant: tint and increase density near Veil
float corruptDist = distance(positionWS, _VeilOrigin.xyz);
float corruptFog = smoothstep(_VeilRadius + 10, _VeilRadius, corruptDist);
half3 fogColor = lerp(_FogColor.rgb, _CorruptFogColor.rgb, corruptFog);
float finalFog = saturate(fog + corruptFog * _CorruptFogDensity);
```

**For volumetric light shafts**, use the open-source `Unity-URP-Volumetric-Light` package (supports Unity 6, render graph compatible) rather than building from scratch.

---

## 3. Rendering Pipeline Configuration

### 3.1 URP Asset Settings Per Quality Tier

Create 3 URP Assets: `VB_URP_Low.asset`, `VB_URP_Medium.asset`, `VB_URP_High.asset`.

| Setting | Low | Medium | High |
|---------|-----|--------|------|
| **Render Scale** | 0.75 | 1.0 | 1.0 |
| **MSAA** | Disabled | 2x | 4x |
| **HDR** | Off | On | On |
| **Main Light** | Per-Pixel | Per-Pixel | Per-Pixel |
| **Main Light Shadows** | On (1 cascade) | On (2 cascades) | On (4 cascades) |
| **Shadow Resolution** | 1024 | 2048 | 4096 |
| **Shadow Distance** | 30m | 60m | 100m |
| **Additional Lights** | Per-Vertex (4 max) | Per-Pixel (4 max) | Per-Pixel (8 max) |
| **Additional Light Shadows** | Off | On (2 max) | On (4 max) |
| **Soft Shadows** | Off | On | On |
| **SSAO** | Off | Medium (5 samples) | High (9 samples) |
| **Decals** | Off | DBuffer | DBuffer |
| **Depth Texture** | On | On | On |
| **Opaque Texture** | Off | Off | On (for refraction) |
| **LOD Cross Fade** | On | On | On |
| **SRP Batcher** | On | On | On |
| **GPU Resident Drawer** | Off | Off | On |

### 3.2 Render Pass Optimization

**Forward+ rendering (Unity 6 URP default):**
- Handles many lights efficiently without extra passes
- No per-object light limit in Forward+ (uses clustered lighting)
- Enable in Renderer: Rendering Path = Forward+

**Pass order for VeilBreakers custom features:**
1. DepthPrepass (built-in, required for SSAO and depth effects)
2. GBuffer / Forward Lit pass (main rendering)
3. Decal pass (DBuffer)
4. SSAO pass
5. Transparent pass (water, particles, force fields)
6. Custom fog pass (height + distance fog renderer feature)
7. Post-processing pass

### 3.3 Depth Prepass Configuration

Depth prepass is automatically enabled in URP when:
- Depth Texture is ON in URP Asset (required for soft particles, water depth, fog)
- SSAO Renderer Feature is added
- Decals use DBuffer technique

For VeilBreakers, **always enable Depth Texture** since water, fog, soft particles, and SSAO all depend on it.

### 3.4 Anti-Aliasing Per Quality Tier

| Tier | Method | Notes |
|------|--------|-------|
| Low | FXAA (camera) | Cheapest, some blur |
| Medium | MSAA 2x + FXAA | Good balance; MSAA handles geometry edges, FXAA catches specular |
| High | MSAA 4x + TAA | Best quality; NOTE: MSAA + TAA cannot coexist -- use TAA only on High |

**IMPORTANT:** MSAA and TAA are mutually exclusive in URP. If using TAA on High tier, set MSAA to Disabled in that URP Asset.

**Corrected High tier approach:**
- High: TAA only (no MSAA) -- TAA handles both geometry and temporal aliasing
- TAA settings: Base Blend Factor 0.875, Jitter Scale 1.0

### 3.5 HDR Rendering and Tone Mapping

**Setup:**
1. Project Settings > Player > Color Space: **Linear** (MANDATORY for PBR)
2. URP Asset > Quality > HDR: **On** (Medium and High tiers)
3. Post-processing Volume > Tonemapping: **ACES** (cinematic, contrasty, ideal for dark fantasy)

**Why ACES for dark fantasy:**
- Desaturates and darkens shadows naturally
- Compresses highlights gracefully (fire, magic, sunlight)
- Enhances contrast between dark and bright areas
- When ACES is active, Unity does color grading in ACES color space for better results

**Color space requirement:** Linear color space is mandatory. Gamma will produce incorrect PBR lighting and double-gamma on tonemapped output.

---

## 4. Post-Processing Stack

### 4.1 Dark Fantasy Post-Processing Preset

Configure via Global Volume with overrides:

#### Bloom
```
Mode: Default
Threshold: 0.9 (only bright sources bloom -- fire, magic, runes)
Intensity: 0.5 (subtle; increase to 1.5 for corruption zones)
Scatter: 0.7
Tint: (warm orange for fire zones, cold blue for corruption)
Dirt Texture: lens dirt for atmospheric feel
Dirt Intensity: 0.3
High Quality Filtering: On (Medium/High only)
```

#### SSAO (Ambient Occlusion)
```
Method: Screen Space Ambient Occlusion (Renderer Feature)
Intensity: 1.5 (strong ground contact shadows)
Radius: 0.5
Samples: Low=1, Medium=5, High=9
Direct Lighting Strength: 0.3
After Opaque: On
```

#### Color Grading
```
Tonemapping: ACES
Post Exposure: -0.3 (slightly dark overall)
Color Filter: slight warm desaturation (0.95, 0.90, 0.85)
Contrast: 25 (strong contrast for dark fantasy mood)
Saturation: -15 (desaturated world, makes magic colors pop)
Shadows: push toward dark blue-purple (+10, -5, +15)
Midtones: slight warm shift
Highlights: cool desaturation
```

**Color grading LUT approach:** For final polish, bake a custom LUT in Photoshop/DaVinci Resolve and use External mode for exact color control.

#### Vignette
```
Color: Black
Center: (0.5, 0.5)
Intensity: 0.25 (subtle ambient vignette)
Smoothness: 0.4
-- Increase to 0.6 intensity during damage, tint red
-- Script-driven: VignetteController.cs adjusts per health %
```

#### Motion Blur (Optional)
```
Mode: Camera Only (not per-object -- too expensive)
Quality: Low
Intensity: 0.3
Clamp: 0.05 (limit blur length)
-- Only enable on High quality tier
-- Disable during combat for responsiveness
```

#### Depth of Field (Cutscenes/Photo Mode only)
```
Mode: Bokeh (High) / Gaussian (Medium)
Focus Distance: script-driven
Focal Length: 50mm equivalent
Aperture: f/2.8 (strong blur)
-- NEVER enable during gameplay -- hurts responsiveness
```

#### Film Grain
```
Type: Medium
Intensity: 0.1 (barely perceptible, adds grit)
Response: 0.5
-- Only on Medium/High tiers
```

### 4.2 Local Volume Zones

Create Local Volumes for environmental storytelling:

| Zone | Bloom | Color Grading | Fog | Notes |
|------|-------|--------------|-----|-------|
| Corruption/Veil | Intensity 1.5, purple tint | Desaturation -30, shadows purple | Dense, purple | Override corruption color grading |
| Dungeon interior | Intensity 0.3 | Contrast +35, shadows deep blue | Light distance fog | Minimal bloom, heavy shadow |
| Forest canopy | Intensity 0.8, green tint | Saturation -5, warm midtones | Height fog, green tint | Dappled light feel |
| Fire/forge area | Intensity 1.2, orange tint | Warm highlights, orange shadows | Thin smoke fog | Warm, intense |
| Snow/mountain | Intensity 0.4 | Highlights cool, desaturated | Distance fog, white | Clean, cold |

---

## 5. Texture Streaming and Memory

### 5.1 Mipmap Streaming Configuration

**Setup:**
1. Edit > Project Settings > Quality > Textures > Enable Mipmap Streaming: **On**
2. Set Memory Budget based on target platform

| Platform | Recommended Budget | Notes |
|----------|-------------------|-------|
| PC Low (4GB VRAM) | 512 MB | Conservative, aggressive streaming |
| PC Medium (6GB VRAM) | 1024 MB | Comfortable |
| PC High (8GB+ VRAM) | 2048 MB | Generous, less streaming pop |

**Estimating budget:** Use `Texture.desiredTextureMemory` during gameplay to measure actual demand, then set budget to 10-20% above that.

**Runtime control:**
```csharp
QualitySettings.streamingMipmapsActive = true;
QualitySettings.streamingMipmapsMemoryBudget = 1024; // MB
QualitySettings.streamingMipmapsMaxLevelReduction = 2; // max 2 mip levels dropped
```

**Unity 6 feature:** The Rendering Debugger now includes a Mipmap Streaming section for inspecting streaming activity at runtime.

### 5.2 Texture Quality Per Tier

| Tier | Max Texture Size | Mipmap Streaming | Anisotropic Level |
|------|------------------|------------------|-------------------|
| Low | 1024 | On, aggressive (512MB) | 4x |
| Medium | 2048 | On (1024MB) | 8x |
| High | 4096 (terrain/characters), 2048 (props) | On (2048MB) | 16x |

### 5.3 Compression Formats

| Platform | Format | Quality | Size Ratio |
|----------|--------|---------|------------|
| PC/Desktop | BC7 (RGBA), BC5 (normals), BC6H (HDR) | Best quality | 8 bpp |
| iOS | ASTC 4x4 (high), ASTC 6x6 (medium), ASTC 8x8 (low) | Scalable | 8-2 bpp |
| Android | ASTC 4x4 (modern), ETC2 (older devices) | Good | 8-4 bpp |

**VeilBreakers texture format rules:**
- Albedo/Diffuse: BC7 (PC), ASTC 4x4 (mobile)
- Normal maps: BC5 (PC, 2-channel), ASTC 5x5 (mobile)
- Metallic/Smoothness: BC7 (packed RGBA)
- HDR environment maps: BC6H
- UI textures: BC7 with Crunch compression for build size (VRAM unchanged)
- Lightmaps: BC6H (HDR) or BC7 (LDR)

**IMPORTANT:** Crunch compression only reduces build/download size, NOT runtime VRAM. The GPU always uses the decompressed format.

### 5.4 VRAM Budget Allocation

**Target: 60fps at 1080p on 4GB VRAM (Low), 1440p on 6GB (Medium), 4K on 8GB+ (High)**

| Category | Low (4GB) | Medium (6GB) | High (8GB+) |
|----------|-----------|--------------|-------------|
| Terrain textures | 128 MB | 256 MB | 512 MB |
| Character textures | 64 MB | 128 MB | 256 MB |
| Props/buildings | 128 MB | 256 MB | 384 MB |
| VFX/particles | 32 MB | 64 MB | 128 MB |
| UI | 32 MB | 64 MB | 64 MB |
| Lightmaps | 64 MB | 128 MB | 256 MB |
| Render targets (shadows, depth, etc.) | ~200 MB | ~350 MB | ~600 MB |
| **Total** | **~648 MB** | **~1246 MB** | **~2200 MB** |

---

## 6. Render Performance Profiling

### 6.1 GPU Profiling Tools

| Tool | Platform | What It Shows |
|------|----------|---------------|
| Unity Profiler (GPU module) | All | Per-frame GPU timing, render pass breakdown |
| Frame Debugger | All | Draw call list, shader state, render targets |
| RenderDoc | PC (DX11/Vulkan) | GPU timings, shader debugging, texture inspection |
| Xcode Frame Capture | macOS/iOS | Metal GPU profiling |
| PIX | Windows (DX12) | GPU timeline, shader profiling |
| Rendering Debugger | All (Unity 6) | Mipmap streaming, overdraw, lighting complexity |

**Unity 6 Rendering Debugger** (Window > Analysis > Rendering Debugger):
- Material overrides: visualize complexity, overdraw, mipmaps
- Lighting debug: visualize light count per pixel, shadow cascades
- Mipmap Streaming section: inspect streaming activity

### 6.2 Frame Budget at 60fps (16.67ms Total)

| Phase | Budget | Notes |
|-------|--------|-------|
| CPU game logic | 4 ms | Physics, AI, scripts |
| CPU render prep | 2 ms | Culling, sorting, batching |
| GPU shadow pass | 2 ms | Cascaded shadow maps |
| GPU depth prepass | 1 ms | Required for SSAO/depth effects |
| GPU forward pass | 4 ms | Main geometry rendering |
| GPU transparent pass | 1.5 ms | Water, particles, VFX |
| GPU post-processing | 1.5 ms | Bloom, SSAO, color grading, fog |
| GPU present/vsync | 0.67 ms | Buffer swap |
| **Total** | **16.67 ms** | |

### 6.3 Identifying Bottlenecks

**CPU-bound indicators:**
- Profiler shows CPU frame time > GPU frame time
- "Gfx.WaitForPresent" is small or zero
- Bottleneck areas: C# scripts, physics, animation, culling

**GPU-bound indicators:**
- Profiler shows GPU frame time > CPU frame time
- "Gfx.WaitForPresent" is large (CPU waiting for GPU)
- Bottleneck sub-types:

| GPU Bottleneck | Indicator | Solution |
|----------------|-----------|----------|
| Fill rate (pixel shader) | High overdraw, complex fragment shaders | Reduce overdraw, simplify shaders, lower resolution |
| Vertex processing | Many vertices, complex vertex shaders | LOD system, mesh simplification |
| Bandwidth (memory) | Large textures, many render targets | Compress textures, reduce render target count/size |
| Shadow rendering | Shadow pass dominates GPU time | Reduce cascade count, shadow distance, resolution |

### 6.4 Profiling Workflow for VeilBreakers

```
1. Build Development Build with Profiler enabled
2. Connect Unity Profiler to build
3. Play through worst-case scenario (combat with many enemies, VFX, corruption)
4. Identify: Is frame > 16.67ms? CPU or GPU bound?
5. If GPU bound:
   a. Frame Debugger: which pass is slowest?
   b. RenderDoc: which draw calls are expensive?
   c. Rendering Debugger: overdraw visualization
6. If CPU bound:
   a. Profiler timeline: which scripts take time?
   b. Deep Profile for allocation tracking
7. Fix -> Re-profile -> Repeat
```

**Key Profiler markers for shader issues:**
- `Shader.CreateGPUProgram` -- shader compilation stutter
- `CreateGraphicsGraphicsPipelineImpl` -- PSO creation stutter
- `Shader.Parse` -- shader parsing overhead
- `BatchRenderer.Flush` -- SRP Batcher submission

### 6.5 GPU Resident Drawer (Unity 6 Feature)

The GPU Resident Drawer keeps mesh data on the GPU, reducing CPU overhead for large scenes. Enable on High quality tier:

```
URP Asset > Rendering > GPU Resident Drawer: On
```

Benefits:
- Reduced CPU draw call overhead
- Better performance with thousands of static objects (buildings, props, terrain details)
- Works with SRP Batcher and GPU instancing

Limitations:
- Not all materials/shaders are compatible
- Requires testing per-shader

---

## 7. Existing Codebase Integration Points

### Shader Template Generator

The toolkit already has `generate_arbitrary_shader()` in `shader_templates.py` which accepts:
- Shader name, path, render type
- Custom properties, vertex/fragment code
- Pragma directives, include paths
- Two-pass support, cull/zwrite/blend modes

This is the correct base for generating ALL new shaders programmatically.

### Shader Stripping Script

`build_templates.py` already contains `generate_shader_stripping_script()` -- verify it covers VeilBreakers-specific stripping needs.

### Settings Templates

`settings_templates.py` has URP Asset configuration via `render_pipeline_path` assignment. Extend this to support per-quality-tier URP Asset creation.

### Missing Template Functions Needed

| Function | File | Purpose |
|----------|------|---------|
| `generate_building_shader` | shader_templates.py | Weathering + moss + wet surfaces |
| `generate_weapon_armor_shader` | shader_templates.py | Metallic PBR + rune emission + damage |
| `generate_cloth_shader` | shader_templates.py | Sheen/velvet BRDF for fabric |
| `generate_vfx_fire_shader` | shader_templates.py | Scrolling noise fire |
| `generate_vfx_smoke_shader` | shader_templates.py | Soft particle smoke |
| `generate_height_fog_feature` | shader_templates.py | Height + distance fog renderer feature |
| `generate_water_shader_v2` | shader_templates.py | Full Gerstner + depth + caustics rewrite |
| `generate_corruption_shader_v2` | shader_templates.py | World-space Veil dissolve + negative light |
| `generate_vegetation_shader_v2` | shader_templates.py | GPU instanced, alpha-to-coverage |
| `generate_terrain_shader_v2` | shader_templates.py | Add triplanar for cliffs |
| `generate_post_processing_preset` | settings_templates.py | Dark fantasy Volume profile |
| `generate_quality_tier_urp_assets` | settings_templates.py | Low/Medium/High URP Assets |

---

## 8. Common Pitfalls

### Pitfall 1: SRP Batcher Incompatibility
**What goes wrong:** Custom shaders silently fall out of SRP Batcher, causing 10x more draw calls.
**How to detect:** Frame Debugger shows "SRP Batcher: not compatible" on objects.
**Prevention:** ALL material properties in one `CBUFFER_START(UnityPerMaterial)` block. Never access material properties outside CBUFFER. Validate with Frame Debugger after every new shader.

### Pitfall 2: Shader Variant Explosion
**What goes wrong:** Each `#pragma multi_compile` keyword doubles variant count. 10 keywords = 1024 variants PER PASS.
**How to detect:** Build log shows thousands of compiled variants; build takes 30+ minutes.
**Prevention:** Use `#pragma shader_feature` for editor-only toggles (stripped if unused). Use `#pragma multi_compile_fragment` for fragment-only keywords. Minimize keywords per shader.

### Pitfall 3: Missing DepthOnly/ShadowCaster Passes
**What goes wrong:** Objects with custom shaders don't cast shadows or appear in depth buffer (breaks SSAO, water depth, fog).
**Prevention:** EVERY opaque custom shader MUST include ShadowCaster and DepthOnly passes. The existing templates correctly include these -- maintain this pattern.

### Pitfall 4: Gamma Color Space
**What goes wrong:** PBR lighting calculations are incorrect. Textures appear too bright or washed out. Tonemapping produces double-gamma.
**Prevention:** Set Project Settings > Player > Color Space = Linear. This is a one-time project setting, cannot be changed after build.

### Pitfall 5: TAA + MSAA Conflict
**What goes wrong:** Enabling both causes undefined behavior or one silently disabling.
**Prevention:** MSAA and TAA are mutually exclusive. Choose one per quality tier. High tier should use TAA only (better temporal stability for fine detail like hair, foliage).

### Pitfall 6: Transparent Object Sorting
**What goes wrong:** Water, particles, glass render in wrong order, causing visual artifacts.
**Prevention:** Use proper Queue tags (Geometry < AlphaTest < Transparent). VFX particles should use Transparent+1 or higher. Water uses Transparent. Never render transparent objects with ZWrite On.

### Pitfall 7: Mipmap Streaming Pop-in
**What goes wrong:** Textures appear blurry for a frame when streaming in higher mips.
**Prevention:** Set Memory Budget generously (10-20% above measured demand). Use `StreamingController` component on cameras for predictive loading. Pre-load critical textures (player character, UI) at full resolution.

### Pitfall 8: Overdraw from Fullscreen Passes
**What goes wrong:** Each fullscreen pass (fog, damage overlay, post-processing) costs fill rate.
**Prevention:** Combine passes where possible. Fog + damage overlay can be a single pass. Disable passes not in use (no fog indoors, no damage overlay at full health).

---

## 9. Sources

### Primary (HIGH confidence)
- [Unity 6 URP Shader Variant Stripping](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/shader-stripping.html)
- [Unity 6 Shader Prewarm / PSO Tracing](https://docs.unity3d.com/6000.2/Documentation/Manual/shader-prewarm.html)
- [Unity 6 URP Performance Guide](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/understand-performance.html)
- [Unity 6 URP Anti-Aliasing](https://docs.unity3d.com/6000.1/Documentation/Manual/urp/anti-aliasing.html)
- [Unity 6 URP Bloom](https://docs.unity3d.com/6000.0/Documentation/Manual/urp/post-processing-bloom.html)
- [Unity 6 URP SSAO](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/post-processing-ssao.html)
- [Unity 6 URP HDR Output](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/post-processing/hdr-output.html)
- [Unity 6 URP Decals](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/renderer-feature-decal.html)
- [Unity 6 Texture Format Guide](https://docs.unity3d.com/6000.0/Documentation/Manual/texture-choose-format-by-platform.html)
- [Unity 6 Mipmap Streaming Config](https://docs.unity3d.com/6000.2/Documentation/Manual/TextureStreaming-configure.html)
- [Unity 6 URP SRP Batcher](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/shaders-in-universalrp-srp-batcher.html)
- [Unity 6 Terrain Shader Graph](https://docs.unity3d.com/6000.3/Documentation/Manual/terrain-shader-graph.html)

### Secondary (MEDIUM confidence)
- [PSO Tracing Discussion](https://discussions.unity.com/t/prevent-shader-compilation-stutters-with-pso-tracing-in-unity-6/951031)
- [URP-Volumetric-Light Package (Unity 6 compatible)](https://github.com/CristianQiu/Unity-URP-Volumetric-Light)
- [URP Hair Shader (Kajiya-Kay)](https://github.com/itsFulcrum/Unity-URP-Hair-Shader)
- [AirSticker Decal System](https://github.com/CyberAgentGameEntertainment/AirSticker)
- [Uber Stylized Water for Unity 6](https://github.com/MatrixRex/Uber-Stylized-Water)
- [URP SSS Implementation](https://echoesofsomewhere.com/2023/10/16/sub-surface-scattering/)
- [Stylized Water Shader Tutorial](https://ameye.dev/notes/stylized-water-shader/)
- [Cyanilux URP Shader Code Guide](https://www.cyanilux.com/tutorials/urp-shader-code/)

### Tertiary (LOW confidence)
- [ShaderVariantCollection WarmUp Issue in Unity 6](https://discussions.unity.com/t/shadervariantcollection-warmup-issue-in-unity-6/1711702) -- reported issues with legacy warmup in Unity 6, confirming PSO tracing is preferred path

### Codebase References
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py` -- 12 existing shader generators
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/character_templates.py` -- SSS skin, parallax eye
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/build_templates.py` -- shader stripping script
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/settings_templates.py` -- URP Asset config
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_tools/shader.py` -- shader tool entry point

---

## 10. Metadata

**Confidence breakdown:**
- Shader variant stripping: HIGH -- official Unity 6 docs
- Shader warmup / PSO tracing: HIGH -- official Unity 6 docs
- URP pipeline configuration: HIGH -- official Unity 6 docs
- Post-processing settings: HIGH -- official Unity 6 docs, standard values
- Custom shader implementations: MEDIUM -- patterns verified against URP shader library includes, but specific VeilBreakers shaders are novel
- VRAM budgets: MEDIUM -- based on industry standards, project-specific measurement needed
- GPU profiling workflow: HIGH -- official Unity profiler docs

**Research date:** 2026-04-02
**Valid until:** 2026-06-02 (Unity 6 is stable LTS, shader APIs are settled)
