# Phase 07 Plan 02 Summary: VFX System (Templates + Shaders + unity_vfx Tool)

**Status:** COMPLETE
**Date:** 2026-03-19

## What was built

### New files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/vfx_templates.py` (~520 lines) -- 8 VFX C# template generators: `generate_particle_vfx_script`, `generate_brand_vfx_script`, `generate_environmental_vfx_script`, `generate_trail_vfx_script`, `generate_aura_vfx_script`, `generate_post_processing_script`, `generate_screen_effect_script`, `generate_ability_vfx_script`. Includes `BRAND_VFX_CONFIGS` (IRON/VENOM/SURGE/DREAD/BLAZE) and `ENV_VFX_CONFIGS` (dust/fireflies/snow/rain/ash) dictionaries.
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py` (~530 lines) -- 7 HLSL shader generators: `generate_corruption_shader`, `generate_dissolve_shader`, `generate_force_field_shader`, `generate_water_shader`, `generate_foliage_shader`, `generate_outline_shader`, `generate_damage_overlay_shader`. All target URP with proper ShaderLab structure.
- `Tools/mcp-toolkit/tests/test_vfx_templates.py` (~460 lines) -- 125 tests covering all 15 generators (8 VFX + 7 shader).

### Modified files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` -- Added VFX imports (vfx_templates + shader_templates) and `unity_vfx` compound tool with 10 actions + 10 handler functions (~350 lines added).

## Test results
- 125 new VFX/shader template tests pass
- 1381 total tests pass (zero regressions)

## Requirements covered

| ID | Requirement | Implementation |
|----|-------------|----------------|
| VFX-01 | VFX Graph particle from text description | `generate_particle_vfx_script()` -- VisualEffect with SetFloat/SetVector4 for rate/lifetime/size/color/shape |
| VFX-02 | Per-brand damage VFX | `generate_brand_vfx_script()` -- BRAND_VFX_CONFIGS with 5 brands (IRON sparks, VENOM drip, SURGE crackle, DREAD shadows, BLAZE fire) |
| VFX-03 | Environmental VFX | `generate_environmental_vfx_script()` -- ENV_VFX_CONFIGS for dust/fireflies/snow/rain/ash with gravity/rate/lifetime |
| VFX-04 | Weapon/projectile trail | `generate_trail_vfx_script()` -- TrailRenderer with width curve, color gradient, lifetime |
| VFX-05 | Character aura/buff | `generate_aura_vfx_script()` -- Looping ParticleSystem with sphere emission around character bounds |
| VFX-06 | Corruption shader (0-1) | `generate_corruption_shader()` -- HLSL with _CorruptionAmount Range(0,1), noise vein pattern, lerp to corruption color |
| VFX-07 | Shader templates | 6 generators: dissolve (noise clip + edge glow), force field (fresnel + depth intersection), water (wave displacement + transparency), foliage (wind sway + _Time + sin/cos), outline (two-pass backface extrusion), damage overlay (fullscreen alpha blend) |
| VFX-08 | Post-processing | `generate_post_processing_script()` -- Volume + VolumeProfile with Bloom/ColorAdjustments/Vignette/SSAO/DepthOfField + Override pattern |
| VFX-09 | Screen effects | `generate_screen_effect_script()` -- Camera shake (CinemachineImpulseSource), damage vignette, low health pulse, poison overlay, heal glow (Canvas + CanvasGroup alpha) |
| VFX-10 | Ability VFX + animation | `generate_ability_vfx_script()` -- AnimationEvent binding + VFX Instantiate + runtime MonoBehaviour trigger script |

## Architecture

The `unity_vfx` compound tool follows the same code generation pattern as `unity_editor` and `unity_audio`:

1. Python generates C# editor scripts or HLSL shader files from parameterized string templates
2. Files are written to the Unity project via `_write_to_unity()`
   - C# scripts -> `Assets/Editor/Generated/VFX/`
   - HLSL shaders -> `Assets/Shaders/Generated/`
3. Returns JSON with next_steps for mcp-unity integration (recompile + execute_menu_item)

All HLSL shaders target URP with `#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"` and proper ShaderLab `Shader "VeilBreakers/..."` naming.
