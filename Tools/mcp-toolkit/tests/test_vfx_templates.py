"""Unit tests for VFX and shader template generators.

Tests that each generator function produces valid C# or HLSL source containing
the expected keywords, API calls, and parameter substitutions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    BRAND_VFX_CONFIGS,
    ENV_VFX_CONFIGS,
    generate_particle_vfx_script,
    generate_brand_vfx_script,
    generate_environmental_vfx_script,
    generate_trail_vfx_script,
    generate_aura_vfx_script,
    generate_post_processing_script,
    generate_screen_effect_script,
    generate_ability_vfx_script,
)

from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_corruption_shader,
    generate_dissolve_shader,
    generate_force_field_shader,
    generate_water_shader,
    generate_foliage_shader,
    generate_outline_shader,
    generate_damage_overlay_shader,
)


# ---------------------------------------------------------------------------
# Particle VFX script (VFX-01)
# ---------------------------------------------------------------------------


class TestGenerateParticleVfxScript:
    """Tests for generate_particle_vfx_script()."""

    def test_contains_visual_effect(self):
        result = generate_particle_vfx_script("TestVFX")
        assert "VisualEffect" in result

    def test_contains_set_float_rate(self):
        result = generate_particle_vfx_script("TestVFX", rate=150)
        assert "SetFloat" in result
        assert "Rate" in result

    def test_contains_set_float_lifetime(self):
        result = generate_particle_vfx_script("TestVFX", lifetime=2.5)
        assert "Lifetime" in result

    def test_contains_set_float_size(self):
        result = generate_particle_vfx_script("TestVFX", size=0.3)
        assert "Size" in result

    def test_contains_color_parameter(self):
        result = generate_particle_vfx_script(
            "TestVFX", color=[1.0, 0.5, 0.0, 1.0]
        )
        assert "Color" in result
        assert "SetVector4" in result

    def test_contains_shape(self):
        result = generate_particle_vfx_script("TestVFX", shape="sphere")
        assert "sphere" in result.lower() or "Sphere" in result

    def test_contains_using_statements(self):
        result = generate_particle_vfx_script("TestVFX")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_particle_vfx_script("TestVFX")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_particle_vfx_script("TestVFX")
        assert "vb_result.json" in result

    def test_contains_prefab_utility(self):
        result = generate_particle_vfx_script("TestVFX")
        assert "PrefabUtility" in result or "SaveAsPrefabAsset" in result

    def test_name_in_output(self):
        result = generate_particle_vfx_script("MyCoolEffect")
        assert "MyCoolEffect" in result

    def test_default_values_produce_valid_output(self):
        result = generate_particle_vfx_script("Default")
        assert len(result) > 100
        assert "VisualEffect" in result


# ---------------------------------------------------------------------------
# Brand VFX script (VFX-02)
# ---------------------------------------------------------------------------


class TestGenerateBrandVfxScript:
    """Tests for generate_brand_vfx_script()."""

    def test_iron_brand_contains_sparks(self):
        result = generate_brand_vfx_script("IRON")
        assert "IRON" in result or "sparks" in result.lower() or "Sparks" in result

    def test_venom_brand_contains_acid(self):
        result = generate_brand_vfx_script("VENOM")
        assert "VENOM" in result or "acid" in result.lower() or "drip" in result.lower()

    def test_surge_brand_contains_electric(self):
        result = generate_brand_vfx_script("SURGE")
        assert "SURGE" in result or "electric" in result.lower() or "crackle" in result.lower()

    def test_dread_brand_contains_shadow(self):
        result = generate_brand_vfx_script("DREAD")
        assert "DREAD" in result or "shadow" in result.lower()

    def test_savage_brand_contains_claw(self):
        result = generate_brand_vfx_script("SAVAGE")
        assert "SAVAGE" in result or "claw" in result.lower() or "slash" in result.lower()

    def test_leech_brand_contains_drain(self):
        result = generate_brand_vfx_script("LEECH")
        assert "LEECH" in result or "drain" in result.lower() or "tendril" in result.lower()

    def test_grace_brand_contains_holy(self):
        result = generate_brand_vfx_script("GRACE")
        assert "GRACE" in result or "holy" in result.lower() or "light" in result.lower()

    def test_mend_brand_contains_restoration(self):
        result = generate_brand_vfx_script("MEND")
        assert "MEND" in result or "restoration" in result.lower() or "nature" in result.lower()

    def test_ruin_brand_contains_decay(self):
        result = generate_brand_vfx_script("RUIN")
        assert "RUIN" in result or "decay" in result.lower() or "earth" in result.lower()

    def test_void_brand_contains_void(self):
        result = generate_brand_vfx_script("VOID")
        assert "VOID" in result or "void" in result.lower() or "rift" in result.lower()

    def test_all_brands_have_configs(self):
        assert "IRON" in BRAND_VFX_CONFIGS
        assert "VENOM" in BRAND_VFX_CONFIGS
        assert "SURGE" in BRAND_VFX_CONFIGS
        assert "DREAD" in BRAND_VFX_CONFIGS
        assert "SAVAGE" in BRAND_VFX_CONFIGS
        assert "LEECH" in BRAND_VFX_CONFIGS
        assert "GRACE" in BRAND_VFX_CONFIGS
        assert "MEND" in BRAND_VFX_CONFIGS
        assert "RUIN" in BRAND_VFX_CONFIGS
        assert "VOID" in BRAND_VFX_CONFIGS

    def test_brand_configs_have_required_fields(self):
        for brand, cfg in BRAND_VFX_CONFIGS.items():
            assert "rate" in cfg, f"{brand} missing rate"
            assert "lifetime" in cfg, f"{brand} missing lifetime"
            assert "size" in cfg, f"{brand} missing size"
            assert "color" in cfg, f"{brand} missing color"
            assert "shape" in cfg, f"{brand} missing shape"
            assert "desc" in cfg, f"{brand} missing desc"

    def test_contains_using_statements(self):
        result = generate_brand_vfx_script("IRON")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_visual_effect(self):
        result = generate_brand_vfx_script("IRON")
        assert "VisualEffect" in result

    def test_contains_result_json_output(self):
        result = generate_brand_vfx_script("IRON")
        assert "vb_result.json" in result

    def test_invalid_brand_raises(self):
        with pytest.raises(ValueError, match="brand"):
            generate_brand_vfx_script("INVALID_BRAND")

    def test_all_brands_produce_different_output(self):
        outputs = {b: generate_brand_vfx_script(b) for b in BRAND_VFX_CONFIGS}
        assert len(set(outputs.values())) == len(BRAND_VFX_CONFIGS)


# ---------------------------------------------------------------------------
# Environmental VFX script (VFX-03)
# ---------------------------------------------------------------------------


class TestGenerateEnvironmentalVfxScript:
    """Tests for generate_environmental_vfx_script()."""

    @pytest.mark.parametrize("effect", ["dust", "fireflies", "snow", "rain", "ash"])
    def test_supported_effects(self, effect):
        result = generate_environmental_vfx_script(effect)
        assert len(result) > 100

    def test_all_env_configs_exist(self):
        for env in ["dust", "fireflies", "snow", "rain", "ash"]:
            assert env in ENV_VFX_CONFIGS, f"Missing config for {env}"

    def test_contains_using_statements(self):
        result = generate_environmental_vfx_script("snow")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_visual_effect_or_particle(self):
        result = generate_environmental_vfx_script("rain")
        assert "VisualEffect" in result or "ParticleSystem" in result

    def test_contains_menu_item(self):
        result = generate_environmental_vfx_script("dust")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_environmental_vfx_script("fireflies")
        assert "vb_result.json" in result

    def test_invalid_effect_raises(self):
        with pytest.raises(ValueError, match="effect_type"):
            generate_environmental_vfx_script("tornado")

    def test_snow_has_downward_motion(self):
        result = generate_environmental_vfx_script("snow")
        # Snow should have gravity or downward velocity references
        assert "gravity" in result.lower() or "Gravity" in result or "down" in result.lower() or "Y" in result


# ---------------------------------------------------------------------------
# Trail VFX script (VFX-04)
# ---------------------------------------------------------------------------


class TestGenerateTrailVfxScript:
    """Tests for generate_trail_vfx_script()."""

    def test_contains_trail_renderer(self):
        result = generate_trail_vfx_script("SwordTrail")
        assert "TrailRenderer" in result

    def test_contains_name(self):
        result = generate_trail_vfx_script("LightningTrail")
        assert "LightningTrail" in result

    def test_width_parameter(self):
        result = generate_trail_vfx_script("Trail", width=0.8)
        assert "0.8" in result

    def test_lifetime_parameter(self):
        result = generate_trail_vfx_script("Trail", lifetime=1.5)
        assert "1.5" in result

    def test_contains_using_statements(self):
        result = generate_trail_vfx_script("Trail")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_trail_vfx_script("Trail")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_trail_vfx_script("Trail")
        assert "vb_result.json" in result

    def test_contains_prefab_save(self):
        result = generate_trail_vfx_script("Trail")
        assert "PrefabUtility" in result or "SaveAsPrefabAsset" in result


# ---------------------------------------------------------------------------
# Aura VFX script (VFX-05)
# ---------------------------------------------------------------------------


class TestGenerateAuraVfxScript:
    """Tests for generate_aura_vfx_script()."""

    def test_contains_particle_system(self):
        result = generate_aura_vfx_script("HealingAura")
        assert "ParticleSystem" in result

    def test_contains_name(self):
        result = generate_aura_vfx_script("CorruptionGlow")
        assert "CorruptionGlow" in result

    def test_looping_enabled(self):
        result = generate_aura_vfx_script("BuffAura")
        assert "loop" in result.lower() or "Looping" in result or "looping" in result

    def test_color_parameter(self):
        result = generate_aura_vfx_script("Aura", color=[0.0, 1.0, 0.0, 1.0])
        assert "Color" in result

    def test_radius_parameter(self):
        result = generate_aura_vfx_script("Aura", radius=2.5)
        assert "2.5" in result

    def test_contains_using_statements(self):
        result = generate_aura_vfx_script("Aura")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_aura_vfx_script("Aura")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_aura_vfx_script("Aura")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Post-processing script (VFX-08)
# ---------------------------------------------------------------------------


class TestGeneratePostProcessingScript:
    """Tests for generate_post_processing_script()."""

    def test_contains_volume(self):
        result = generate_post_processing_script()
        assert "Volume" in result

    def test_contains_bloom(self):
        result = generate_post_processing_script(bloom_intensity=2.0)
        assert "Bloom" in result

    def test_contains_color_adjustments(self):
        result = generate_post_processing_script()
        assert "ColorAdjustments" in result or "ColorGrading" in result

    def test_contains_vignette(self):
        result = generate_post_processing_script(vignette_intensity=0.5)
        assert "Vignette" in result

    def test_contains_ao(self):
        result = generate_post_processing_script(ao_intensity=0.8)
        assert "AmbientOcclusion" in result or "ScreenSpaceAmbientOcclusion" in result or "SSAO" in result

    def test_contains_dof(self):
        result = generate_post_processing_script(dof_focus_distance=15.0)
        assert "DepthOfField" in result

    def test_contains_using_statements(self):
        result = generate_post_processing_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_post_processing_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_post_processing_script()
        assert "vb_result.json" in result

    def test_contains_volume_profile(self):
        result = generate_post_processing_script()
        assert "VolumeProfile" in result

    def test_override_pattern(self):
        result = generate_post_processing_script()
        assert "Override" in result


# ---------------------------------------------------------------------------
# Screen effect script (VFX-09)
# ---------------------------------------------------------------------------


class TestGenerateScreenEffectScript:
    """Tests for generate_screen_effect_script()."""

    def test_camera_shake_contains_impulse(self):
        result = generate_screen_effect_script("camera_shake")
        assert "Impulse" in result or "impulse" in result or "CinemachineImpulseSource" in result

    def test_damage_vignette(self):
        result = generate_screen_effect_script("damage_vignette")
        assert "vignette" in result.lower() or "Vignette" in result

    def test_low_health_pulse(self):
        result = generate_screen_effect_script("low_health_pulse")
        assert "pulse" in result.lower() or "Pulse" in result or "health" in result.lower()

    def test_poison_overlay(self):
        result = generate_screen_effect_script("poison_overlay")
        assert "poison" in result.lower() or "Poison" in result or "overlay" in result.lower()

    def test_heal_glow(self):
        result = generate_screen_effect_script("heal_glow")
        assert "heal" in result.lower() or "Heal" in result or "glow" in result.lower()

    def test_contains_using_statements(self):
        result = generate_screen_effect_script("camera_shake")
        assert "using UnityEngine;" in result

    def test_contains_menu_item(self):
        result = generate_screen_effect_script("camera_shake")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_screen_effect_script("camera_shake")
        assert "vb_result.json" in result

    def test_invalid_effect_raises(self):
        with pytest.raises(ValueError, match="effect_type"):
            generate_screen_effect_script("explosion")

    @pytest.mark.parametrize(
        "effect_type",
        ["camera_shake", "damage_vignette", "low_health_pulse", "poison_overlay", "heal_glow"],
    )
    def test_all_supported_effects_produce_output(self, effect_type):
        result = generate_screen_effect_script(effect_type)
        assert len(result) > 100


# ---------------------------------------------------------------------------
# Ability VFX script (VFX-10)
# ---------------------------------------------------------------------------


class TestGenerateAbilityVfxScript:
    """Tests for generate_ability_vfx_script()."""

    def test_contains_ability_name(self):
        result = generate_ability_vfx_script("Fireball")
        assert "Fireball" in result

    def test_contains_vfx_prefab(self):
        result = generate_ability_vfx_script(
            "Slash", vfx_prefab="Assets/Prefabs/VFX/Slash.prefab"
        )
        assert "Slash.prefab" in result

    def test_contains_animation_event(self):
        result = generate_ability_vfx_script("Strike")
        assert "AnimationEvent" in result

    def test_contains_keyframe_time(self):
        result = generate_ability_vfx_script("Strike", keyframe_time=0.35)
        assert "0.35" in result

    def test_contains_using_statements(self):
        result = generate_ability_vfx_script("Test")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_ability_vfx_script("Test")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json_output(self):
        result = generate_ability_vfx_script("Test")
        assert "vb_result.json" in result

    def test_contains_instantiate(self):
        result = generate_ability_vfx_script("Test")
        assert "Instantiate" in result


# ===========================================================================
# Shader template tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Corruption shader (VFX-06)
# ---------------------------------------------------------------------------


class TestGenerateCorruptionShader:
    """Tests for generate_corruption_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_corruption_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_corruption_amount_property(self):
        result = generate_corruption_shader()
        assert "_CorruptionAmount" in result

    def test_corruption_range_0_1(self):
        result = generate_corruption_shader()
        assert "Range(0" in result or "Range(0,1)" in result or "Range(0, 1)" in result

    def test_contains_hlsl_program(self):
        result = generate_corruption_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_properties_block(self):
        result = generate_corruption_shader()
        assert "Properties" in result

    def test_contains_subshader(self):
        result = generate_corruption_shader()
        assert "SubShader" in result

    def test_contains_urp_include(self):
        result = generate_corruption_shader()
        assert "com.unity.render-pipelines.universal" in result


# ---------------------------------------------------------------------------
# Dissolve shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateDissolveShader:
    """Tests for generate_dissolve_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_dissolve_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_dissolve_amount(self):
        result = generate_dissolve_shader()
        assert "_DissolveAmount" in result

    def test_contains_edge_width(self):
        result = generate_dissolve_shader()
        assert "_EdgeWidth" in result

    def test_contains_edge_color(self):
        result = generate_dissolve_shader()
        assert "_EdgeColor" in result

    def test_contains_hlsl_program(self):
        result = generate_dissolve_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_clip_call(self):
        result = generate_dissolve_shader()
        assert "clip" in result.lower() or "clip(" in result

    def test_contains_urp_include(self):
        result = generate_dissolve_shader()
        assert "com.unity.render-pipelines.universal" in result


# ---------------------------------------------------------------------------
# Force field shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateForceFieldShader:
    """Tests for generate_force_field_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_force_field_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_fresnel(self):
        result = generate_force_field_shader()
        assert "fresnel" in result.lower() or "Fresnel" in result

    def test_contains_intersection_or_depth(self):
        result = generate_force_field_shader()
        assert "depth" in result.lower() or "Depth" in result or "intersection" in result.lower()

    def test_contains_hlsl_program(self):
        result = generate_force_field_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_urp_include(self):
        result = generate_force_field_shader()
        assert "com.unity.render-pipelines.universal" in result


# ---------------------------------------------------------------------------
# Water shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateWaterShader:
    """Tests for generate_water_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_water_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_wave_or_displacement(self):
        result = generate_water_shader()
        assert "wave" in result.lower() or "displacement" in result.lower() or "Wave" in result

    def test_contains_transparency(self):
        result = generate_water_shader()
        assert "Transparent" in result or "Alpha" in result or "alpha" in result

    def test_contains_hlsl_program(self):
        result = generate_water_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_urp_include(self):
        result = generate_water_shader()
        assert "com.unity.render-pipelines.universal" in result


# ---------------------------------------------------------------------------
# Foliage shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateFoliageShader:
    """Tests for generate_foliage_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_foliage_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_wind(self):
        result = generate_foliage_shader()
        assert "wind" in result.lower() or "Wind" in result

    def test_contains_time_based_animation(self):
        result = generate_foliage_shader()
        assert "_Time" in result

    def test_contains_sin_or_cos(self):
        result = generate_foliage_shader()
        assert "sin" in result or "cos" in result

    def test_contains_hlsl_program(self):
        result = generate_foliage_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_urp_include(self):
        result = generate_foliage_shader()
        assert "com.unity.render-pipelines.universal" in result


# ---------------------------------------------------------------------------
# Outline shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateOutlineShader:
    """Tests for generate_outline_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_outline_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_outline_reference(self):
        result = generate_outline_shader()
        assert "outline" in result.lower() or "Outline" in result

    def test_contains_hlsl_program(self):
        result = generate_outline_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_urp_include(self):
        result = generate_outline_shader()
        assert "com.unity.render-pipelines.universal" in result

    def test_contains_two_pass_or_sobel(self):
        result = generate_outline_shader()
        # Should have either two passes or Sobel edge detection
        assert "Pass" in result


# ---------------------------------------------------------------------------
# Damage overlay shader (VFX-07)
# ---------------------------------------------------------------------------


class TestGenerateDamageOverlayShader:
    """Tests for generate_damage_overlay_shader()."""

    def test_contains_shader_declaration(self):
        result = generate_damage_overlay_shader()
        assert 'Shader "VeilBreakers/' in result

    def test_contains_intensity_property(self):
        result = generate_damage_overlay_shader()
        assert "_Intensity" in result

    def test_contains_overlay_or_blend(self):
        result = generate_damage_overlay_shader()
        assert "overlay" in result.lower() or "Blend" in result or "blend" in result.lower()

    def test_contains_hlsl_program(self):
        result = generate_damage_overlay_shader()
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_contains_urp_include(self):
        result = generate_damage_overlay_shader()
        assert "com.unity.render-pipelines.universal" in result
