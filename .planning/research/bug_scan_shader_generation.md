# Bug Scan: Shader Code Generation & HLSL/ShaderLab Output

**Date:** 2026-04-02
**Scope:** All shader-generating templates in `unity_templates/`
**Files Analyzed:**
- `shader_templates.py` (12 shader generators + renderer feature)
- `character_templates.py` (SSS skin, parallax eye)
- `evolution_templates.py` (evolution dissolve)
- `ux_templates.py` (colorblind filter)
- `ui_polish_templates.py` (UI effects shader)

---

## NEW Bugs Found

### BUG-S01: Duplicate ShadowCaster passes in corruption shader [SEVERITY: HIGH]

**File:** `shader_templates.py`, `generate_corruption_shader()`, lines ~252-353

The corruption shader has THREE passes: ForwardLit, a custom ShadowCaster (lines 252-299) with proper `ApplyShadowBias` and `_LightDirection`, AND a second ShadowCaster (lines 340-353) using `ShadowCasterPass.hlsl` with `ShadowPassVertex`/`ShadowPassFragment`. Having two passes with the same `"LightMode"="ShadowCaster"` tag is undefined behavior in Unity. The second pass will either be ignored or cause a shader compilation error because the built-in `ShadowCasterPass.hlsl` expects its own `Attributes`/`Varyings` struct definitions (with specific names) and a CBUFFER with `_BaseMap_ST` -- none of which are provided. The second ShadowCaster pass will fail to compile.

**Impact:** Shader compilation failure or shadow rendering errors.
**Fix:** Remove the second ShadowCaster pass (lines 340-353). The first custom one is correct.

### BUG-S02: Duplicate ShadowCaster passes in dissolve shader [SEVERITY: HIGH]

**File:** `shader_templates.py`, `generate_dissolve_shader()`, lines ~498-577

Identical issue to BUG-S01. The dissolve shader has a custom ShadowCaster pass (lines 498-562) that correctly clips dissolved pixels using noise, PLUS a second generic ShadowCaster (lines 564-577) using `ShadowCasterPass.hlsl` without any dissolve clipping. Same compilation failure risk. Even if it did compile, the second pass would render shadows for dissolved pixels -- defeating the purpose.

**Impact:** Shader compilation failure or dissolved objects casting solid shadows.
**Fix:** Remove the second ShadowCaster pass (lines 564-577).

### BUG-S03: ShadowCasterPass.hlsl used without required struct definitions [SEVERITY: HIGH]

**File:** `shader_templates.py`, force field shader (line 711), water shader (line 873)

The force field and water shaders include `ShadowCasterPass.hlsl` and declare `ShadowPassVertex`/`ShadowPassFragment` but do NOT define the `Attributes` and `Varyings` structs that `ShadowCasterPass.hlsl` expects. URP's `ShadowCasterPass.hlsl` internally references specific struct member names (`positionOS`, `normalOS` in `Attributes`; `positionCS` in `Varyings`) and expects `CBUFFER_START(UnityPerMaterial)` with certain variables. Without these definitions, the shader will fail to compile.

**Impact:** Shader compilation errors for force field and water shadow passes.
**Fix:** Either (a) add the required `Attributes`/`Varyings` struct definitions and CBUFFER that `ShadowCasterPass.hlsl` expects, or (b) replace with a custom ShadowCaster pass like the corruption shader's first one.

### BUG-S04: Transparent force field shader casts shadows [SEVERITY: MEDIUM]

**File:** `shader_templates.py`, `generate_force_field_shader()`, lines ~700-714

A transparent force field with `Blend SrcAlpha OneMinusSrcAlpha` and `ZWrite Off` has a ShadowCaster pass. Transparent objects should not cast opaque shadows -- it creates a solid black shadow silhouette for what should be a see-through effect. The `FallBack Off` is correct (no fallback shadow), but the explicit ShadowCaster pass overrides that.

**Impact:** Force fields cast solid shadows that look wrong visually.
**Fix:** Remove the ShadowCaster pass from the force field shader entirely.

### BUG-S05: Transparent water shader casts opaque shadows [SEVERITY: MEDIUM]

**File:** `shader_templates.py`, `generate_water_shader()`, lines ~862-875

Same issue as BUG-S04. The water shader is transparent (`Blend SrcAlpha OneMinusSrcAlpha`, `ZWrite Off`) but includes a ShadowCaster pass. Water surfaces should not cast solid shadows -- or at minimum should have alpha-clip shadow casting with a caustic pattern. The current pass casts a solid shadow silhouette.

**Impact:** Water surfaces cast solid opaque shadows.
**Fix:** Remove the ShadowCaster pass, or implement a dithered/alpha-clipped shadow pass if shadow casting is desired.

### BUG-S06: No DepthNormals pass in ANY generated shader [SEVERITY: MEDIUM]

**File:** All shader templates

None of the 14+ generated shaders include a `DepthNormals` pass (`"LightMode"="DepthNormalsOnly"`). This pass is required by URP for:
- SSAO (Screen-Space Ambient Occlusion)
- Screen-space reflections
- Decal rendering with proper normals
- Any renderer feature relying on `_CameraNormalsTexture`

Without it, objects using these custom shaders will show visual artifacts in scenes using SSAO -- they will either be missing ambient occlusion or display incorrect normals.

**Impact:** All custom-shaded objects break SSAO and similar effects.
**Fix:** Add a DepthNormals pass to every opaque/cutout shader. Template:
```hlsl
Pass
{
    Name "DepthNormals"
    Tags { "LightMode"="DepthNormalsOnly" }
    ZWrite On

    HLSLPROGRAM
    #pragma vertex DepthNormalsVertex
    #pragma fragment DepthNormalsFragment

    #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
    #include "Packages/com.unity.render-pipelines.universal/Shaders/DepthNormalsPass.hlsl"
    ENDHLSL
}
```

### BUG-S07: SSS skin shader ShadowCaster missing UNITY_REVERSED_Z clamp [SEVERITY: MEDIUM]

**File:** `character_templates.py`, `generate_sss_skin_shader()`, lines ~522-528

The SSS skin ShadowCaster vertex function calls `TransformWorldToHClip(ApplyShadowBias(...))` but does NOT clamp `output.positionCS.z` using the `UNITY_REVERSED_Z` pattern. Every other custom ShadowCaster in the codebase has this clamp. Without it, shadow acne or shadow loss can occur on platforms with reversed Z-buffer (all modern platforms: D3D11, D3D12, Vulkan, Metal).

```hlsl
// Missing in SSS skin shader:
#if UNITY_REVERSED_Z
output.positionCS.z = min(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
#else
output.positionCS.z = max(output.positionCS.z, UNITY_NEAR_CLIP_VALUE);
#endif
```

**Impact:** Potential shadow acne or missing shadows on character skin.
**Fix:** Add the `UNITY_REVERSED_Z` depth clamp.

### BUG-S08: Parallax eye shader has no ShadowCaster or DepthOnly pass [SEVERITY: MEDIUM]

**File:** `character_templates.py`, `generate_parallax_eye_shader()`, lines ~571-740

The eye shader only has a ForwardLit pass -- no ShadowCaster, DepthOnly, or DepthNormals passes. While the FallBack to "Universal Render Pipeline/Lit" should provide these, the fallback uses a completely different material property set and may not produce correct results. Eyes need proper depth writing for depth-of-field and depth prepass to work correctly.

**Impact:** Eyes may not write to depth buffer properly, causing DOF artifacts and incorrect sorting.
**Fix:** Add at minimum a DepthOnly pass.

### BUG-S09: generate_arbitrary_shader() has no ShadowCaster pass [SEVERITY: HIGH]

**File:** `shader_templates.py`, `generate_arbitrary_shader()`, lines ~1712-1783

This is the user-facing general-purpose shader builder (SHDR-01). It generates only ForwardLit passes (one or two). No ShadowCaster, DepthOnly, or DepthNormals pass is included. Objects using this shader will not cast shadows unless the `FallBack "Hidden/InternalErrorShader"` provides them -- and `InternalErrorShader` does NOT provide ShadowCaster.

**Impact:** Any object using a custom shader from `create_shader` casts no shadows at all.
**Fix:** Add a ShadowCaster pass to the generated output, using the custom properties' alpha clip if the render type is TransparentCutout.

### BUG-S10: UI shader uses legacy `sampler2D` instead of URP TEXTURE2D/SAMPLER macros [SEVERITY: LOW]

**File:** `ui_polish_templates.py`, lines ~2700-2748

The UI effects shader uses `sampler2D _MainTex` and `sampler2D _RuneMask` instead of URP's `TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);` pattern, and uses `tex2D()` instead of `SAMPLE_TEXTURE2D()`. While this compiles and works, it:
1. Breaks SRP Batcher compatibility for texture variables (the CBUFFER correctly excludes `sampler2D`, but the old-style declarations bypass URP's texture management)
2. Prevents platform-specific texture sampling optimizations
3. Is inconsistent with every other shader in the codebase

**Impact:** Minor performance impact, SRP Batcher may not batch these UI draws.
**Fix:** Use `TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);` and `SAMPLE_TEXTURE2D()`.

### BUG-S11: Colorblind filter shader uses Blit.hlsl Varyings but declares `_ColorblindMode` outside CBUFFER [SEVERITY: MEDIUM]

**File:** `ux_templates.py`, lines ~1658-1726

The colorblind filter shader declares `int _ColorblindMode;` as a global variable outside any CBUFFER. This breaks SRP Batcher compatibility. All material properties must be inside `CBUFFER_START(UnityPerMaterial)` for the SRP Batcher to work. Additionally, the shader declares `TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);` but the `Blit.hlsl` include may already define its own `_BlitTexture` -- potential name collision depending on URP version.

**Impact:** SRP Batcher broken for colorblind filter. Potential compilation error with Blit.hlsl texture name conflicts.
**Fix:** Wrap `_ColorblindMode` in a CBUFFER. Verify compatibility with `Blit.hlsl` texture declarations.

### BUG-S12: Water shader applies wave displacement THEN re-calls TransformObjectToWorld [SEVERITY: LOW]

**File:** `shader_templates.py`, `generate_water_shader()`, lines ~808-819

The water vertex shader does:
1. `worldPos = TransformObjectToWorld(input.positionOS.xyz)` (line 812)
2. Modifies `input.positionOS.y` with wave displacement (line 816)
3. `output.positionCS = TransformObjectToHClip(input.positionOS.xyz)` (line 817)
4. `output.positionWS = TransformObjectToWorld(input.positionOS.xyz)` (line 819)

Step 1 calculates world pos for wave input (correct), but step 4 re-transforms the modified object-space position. The wave displacement is applied in world space (wave frequencies use worldPos.x/z) but the offset is added to object-space Y. For non-uniformly scaled or rotated water planes, this produces incorrect wave direction -- waves will sway in local Y instead of world Y.

**Impact:** Waves look wrong on rotated or non-uniformly scaled water planes.
**Fix:** Apply wave displacement in world space after the transform, or at minimum document that the water plane must not be rotated.

### BUG-S13: Evolution dissolve shader ZWrite On with transparent blend [SEVERITY: LOW]

**File:** `evolution_templates.py`, lines ~908-910

The evolution dissolve shader uses:
```
Blend SrcAlpha OneMinusSrcAlpha
ZWrite On
```

Having `ZWrite On` with alpha blending causes visual artifacts: partially transparent pixels (during dissolve fade) will write to the depth buffer, preventing objects behind them from rendering. This creates a "ghost outline" effect where the dissolving object blocks rendering of things behind it even where it is visually transparent.

**Impact:** Visual artifacts during dissolve transitions -- objects behind dissolving mesh pop in/out.
**Fix:** Either use `ZWrite Off` (standard for transparent), or use alpha-test (`clip()`) with `ZWrite On` and no alpha blending.

### BUG-S14: Damage overlay shader has unnecessary multi_compile pragmas [SEVERITY: LOW]

**File:** `shader_templates.py`, `generate_damage_overlay_shader()`, lines ~1393-1396

The damage overlay is a fullscreen post-processing shader (`ZTest Always`, `Queue=Overlay`), yet it includes:
```
#pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
#pragma multi_compile _ _ADDITIONAL_LIGHTS
#pragma multi_compile_fog
```

This shader never uses lighting, shadows, or fog. Each `multi_compile` directive creates shader variants that are compiled but never used, wasting build time and memory. For a fullscreen UI overlay, these are 100% unnecessary.

**Impact:** Wasted shader variants (up to 8x more compiled variants than needed).
**Fix:** Remove all three `multi_compile` pragmas.

### BUG-S15: Outline shader pass 1 has unnecessary shadow/light pragmas [SEVERITY: LOW]

**File:** `shader_templates.py`, `generate_outline_shader()`, lines ~1161-1164

The outline extrusion pass (pass 1, `Cull Front`) has:
```
#pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
#pragma multi_compile _ _ADDITIONAL_LIGHTS
#pragma multi_compile_fog
```

This pass renders a solid flat color (`return _OutlineColor;`). It never samples lights, shadows, or fog. These pragmas create unnecessary shader variants.

**Impact:** Wasted shader variants for the outline pass.
**Fix:** Remove multi_compile pragmas from pass 1.

### BUG-S16: Terrain blend shader has 12 separate samplers -- exceeds mobile limit [SEVERITY: MEDIUM]

**File:** `shader_templates.py`, `generate_terrain_blend_shader()`, lines ~2426-2444

The terrain blend shader declares 13 TEXTURE2D/SAMPLER pairs:
- 1 splat map
- 4 layers x 3 textures each (albedo, normal, height)

That is 13 texture samplers in a single pass. The hardware sampler limit is:
- OpenGL ES 3.x / WebGL: 16 (cuts it close with engine-reserved samplers)
- Some mobile GPUs: 8-12 active samplers

With URP's reserved samplers (shadow map, depth, etc.), this shader will exceed the sampler limit on lower-end hardware.

**Impact:** Shader compilation failure on mobile/WebGL. Performance issues even on desktop.
**Fix:** Use sampler sharing (define SAMPLERs once, reuse for layers with similar settings), or reduce to 2 layers on lower quality settings.

### BUG-S17: Foliage shader wind offset uses unity_WorldToObject incorrectly [SEVERITY: LOW]

**File:** `shader_templates.py`, `generate_foliage_shader()`, lines ~981-983

```hlsl
float3 windOffset = normalize(_WindDirection.xyz) * swayX;
windOffset.z += swayZ;
input.positionOS.xyz += mul(unity_WorldToObject, float4(windOffset, 0)).xyz;
```

The `mul(unity_WorldToObject, float4(windOffset, 0))` call treats the 4x4 world-to-object matrix as if the wind offset is a point (homogeneous w=0 makes it direction-only, which is correct for direction but uses the wrong mul order). For proper direction transformation, this should be `mul((float3x3)unity_WorldToObject, windOffset)` to avoid the translation component being involved in the calculation. With `w=0` the result is mathematically equivalent, but using `float3x3` is cleaner and avoids confusion.

**Impact:** Functionally works for most cases, but adds unnecessary computation.
**Fix:** Use `mul((float3x3)unity_WorldToObject, windOffset)`.

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| HIGH | 3 | Duplicate ShadowCaster passes (BUG-S01, S02), missing ShadowCaster in arbitrary shader (BUG-S09) |
| MEDIUM | 6 | Missing DepthNormals everywhere (S06), broken ShadowCasterPass.hlsl (S03), transparent shadow casting (S04, S05), missing REVERSED_Z (S07), CBUFFER issues (S11), sampler overflow (S16) |
| LOW | 5 | UI sampler style (S10), water wave math (S12), ZWrite+blend (S13), unnecessary variants (S14, S15), wind math (S17) |
| **TOTAL** | **17** | |

### Critical Patterns:
1. **Duplicate ShadowCaster passes** -- corruption and dissolve shaders have two conflicting ShadowCaster passes each
2. **ShadowCasterPass.hlsl without required definitions** -- force field and water shaders include the URP pass file but don't define the structs it expects
3. **Missing DepthNormals pass** -- universal across ALL generated shaders, breaks SSAO
4. **No ShadowCaster in arbitrary shader** -- the most user-facing shader builder produces shadowless objects
5. **Transparent shaders casting opaque shadows** -- force field and water
