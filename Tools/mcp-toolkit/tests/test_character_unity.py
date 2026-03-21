"""Tests for Unity character templates: cloth setup + AAA shaders.

Validates CHAR-07 and CHAR-08 requirements:
- Cloth component configuration with presets
- SSS skin shader for character heads
- Parallax eye shader with iris depth
- Micro-detail normal map compositor
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.character_templates import (
    generate_cloth_setup_script,
    generate_sss_skin_shader,
    generate_parallax_eye_shader,
    generate_micro_detail_normal_script,
    _CLOTH_PRESETS,
)


# ---------------------------------------------------------------------------
# CHAR-07: Cloth setup tests
# ---------------------------------------------------------------------------


class TestClothSetup:
    """Tests for generate_cloth_setup_script -- CHAR-07."""

    def test_basic_generation(self):
        result = generate_cloth_setup_script("MyCape", "cape")
        assert "class VeilBreakers_ClothSetup_MyCape" in result
        assert "Cloth" in result
        assert "MenuItem" in result

    def test_default_parameters(self):
        result = generate_cloth_setup_script()
        assert "CharacterCloth" in result
        assert "stretchingStiffness" in result
        assert "bendingStiffness" in result
        assert "damping" in result

    @pytest.mark.parametrize("cloth_type", [
        "cape", "robe", "hair", "banner", "cloth_armor",
    ])
    def test_all_cloth_types(self, cloth_type: str):
        """Each cloth preset should produce valid C#."""
        result = generate_cloth_setup_script("Test", cloth_type)
        assert "stretchingStiffness" in result
        assert cloth_type in result

    def test_cape_preset_values(self):
        result = generate_cloth_setup_script("TestCape", "cape")
        # Cape should have moderate stiffness
        assert "0.8f" in result  # stretching_stiffness
        assert "0.5f" in result  # bending_stiffness

    def test_cloth_armor_high_stiffness(self):
        result = generate_cloth_setup_script("TestArmor", "cloth_armor")
        assert "0.95f" in result  # high stiffness

    def test_custom_stiffness_override(self):
        result = generate_cloth_setup_script("Test", "cape", stiffness=0.5)
        # Should use overridden value
        assert "stretchingStiffness = 0.5f" in result

    def test_custom_damping_override(self):
        result = generate_cloth_setup_script("Test", "cape", damping=0.9)
        assert "damping = 0.9f" in result

    def test_wind_parameters(self):
        result = generate_cloth_setup_script("Test", wind_main=2.5, wind_turbulence=0.8)
        assert "windMain = 2.5f" in result
        assert "windTurbulence = 0.8f" in result

    def test_collision_spheres(self):
        spheres = [
            {"transform_name": "Hips", "radius": 0.15},
            {"transform_name": "Spine", "radius": 0.12},
        ]
        result = generate_cloth_setup_script("Test", collision_spheres=spheres)
        assert "Hips" in result
        assert "Spine" in result
        assert "SphereCollider" in result
        assert "ClothSphereColliderPair" in result
        assert "0.15f" in result
        assert "0.12f" in result

    def test_no_collision_spheres(self):
        result = generate_cloth_setup_script("Test")
        assert "ClothSphereColliderPair" not in result

    def test_auto_vertex_weights(self):
        """Script should include automatic vertex weight painting."""
        result = generate_cloth_setup_script("Test")
        assert "ClothSkinningCoefficient" in result
        assert "maxDistance" in result
        assert "coefficients" in result

    def test_wind_zone_creation(self):
        result = generate_cloth_setup_script("Test")
        assert "WindZone" in result
        assert "VB_WindZone" in result

    def test_error_handling(self):
        result = generate_cloth_setup_script("Test")
        assert "catch" in result
        assert "vb_result.json" in result

    def test_undo_support(self):
        result = generate_cloth_setup_script("Test")
        assert "Undo.RecordObject" in result

    def test_skinned_mesh_renderer_check(self):
        result = generate_cloth_setup_script("Test")
        assert "SkinnedMeshRenderer" in result

    def test_all_presets_defined(self):
        """All expected preset types should exist."""
        expected = {"cape", "robe", "hair", "banner", "cloth_armor"}
        assert set(_CLOTH_PRESETS.keys()) == expected

    def test_preset_fields_complete(self):
        """Each preset should have all required fields."""
        required_fields = {
            "stretching_stiffness", "bending_stiffness", "damping",
            "world_velocity_scale", "world_acceleration_scale", "friction",
            "use_gravity",
        }
        for name, preset in _CLOTH_PRESETS.items():
            for field in required_fields:
                assert field in preset, f"Preset '{name}' missing '{field}'"

    def test_special_characters_in_name(self):
        """Names with special chars should be sanitized."""
        result = generate_cloth_setup_script("My Cape-01!")
        assert "MyCape01" in result  # sanitized identifier


# ---------------------------------------------------------------------------
# CHAR-08: SSS Skin Shader tests
# ---------------------------------------------------------------------------


class TestSSSSkinShader:
    """Tests for generate_sss_skin_shader -- CHAR-08."""

    def test_basic_generation(self):
        result = generate_sss_skin_shader()
        assert 'Shader "VeilBreakers/Character/SSS_Skin"' in result
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result

    def test_urp_pipeline_tags(self):
        result = generate_sss_skin_shader()
        assert '"RenderPipeline"="UniversalPipeline"' in result
        assert '"RenderType"="Opaque"' in result

    def test_sss_properties(self):
        result = generate_sss_skin_shader()
        assert "_SSSColor" in result
        assert "_SSSPower" in result
        assert "_SSSDistortion" in result
        assert "_SSSScale" in result

    def test_texture_properties(self):
        result = generate_sss_skin_shader()
        assert "_MainTex" in result
        assert "_BumpMap" in result
        assert "_ThicknessMap" in result
        assert "_OcclusionMap" in result
        assert "_DetailNormalMap" in result

    def test_custom_sss_color(self):
        result = generate_sss_skin_shader(sss_color=(1.0, 0.5, 0.3, 1.0))
        assert "(1.0, 0.5, 0.3, 1.0)" in result

    def test_custom_sss_power(self):
        result = generate_sss_skin_shader(sss_power=5.0)
        assert "5.0" in result

    def test_subsurface_scatter_function(self):
        """Should include the SSS approximation function."""
        result = generate_sss_skin_shader()
        assert "SubsurfaceScatter" in result

    def test_wrapped_diffuse(self):
        """Should use wrapped diffuse for softer skin lighting."""
        result = generate_sss_skin_shader()
        assert "wrappedNdotL" in result

    def test_shadow_caster_pass(self):
        """Should include a shadow caster pass."""
        result = generate_sss_skin_shader()
        assert "ShadowCaster" in result

    def test_detail_normal_blending(self):
        """Should blend base + detail normals."""
        result = generate_sss_skin_shader()
        assert "detailNormal" in result
        assert "_DetailTiling" in result

    def test_additional_lights_support(self):
        """Should handle additional lights."""
        result = generate_sss_skin_shader()
        assert "GetAdditionalLightsCount" in result
        assert "GetAdditionalLight" in result

    def test_multi_compile_shadows(self):
        result = generate_sss_skin_shader()
        assert "_MAIN_LIGHT_SHADOWS" in result

    def test_fallback_shader(self):
        result = generate_sss_skin_shader()
        assert "FallBack" in result
        assert "Universal Render Pipeline/Lit" in result


# ---------------------------------------------------------------------------
# CHAR-08: Parallax Eye Shader tests
# ---------------------------------------------------------------------------


class TestParallaxEyeShader:
    """Tests for generate_parallax_eye_shader -- CHAR-08."""

    def test_basic_generation(self):
        result = generate_parallax_eye_shader()
        assert 'Shader "VeilBreakers/Character/ParallaxEye"' in result
        assert "HLSLPROGRAM" in result

    def test_urp_tags(self):
        result = generate_parallax_eye_shader()
        assert '"RenderPipeline"="UniversalPipeline"' in result

    def test_iris_properties(self):
        result = generate_parallax_eye_shader()
        assert "_IrisTex" in result
        assert "_IrisColor" in result
        assert "_IrisRadius" in result
        assert "_IrisDepth" in result

    def test_sclera_properties(self):
        result = generate_parallax_eye_shader()
        assert "_ScleraTex" in result
        assert "_ScleraColor" in result

    def test_pupil_properties(self):
        result = generate_parallax_eye_shader()
        assert "_PupilColor" in result
        assert "_PupilScale" in result

    def test_limbal_ring(self):
        result = generate_parallax_eye_shader()
        assert "_LimbalRingColor" in result
        assert "_LimbalRingWidth" in result

    def test_parallax_offset(self):
        """Should include parallax offset calculation for iris depth."""
        result = generate_parallax_eye_shader()
        assert "parallaxOffset" in result
        assert "viewTS" in result

    def test_refraction(self):
        """Should include refraction approximation."""
        result = generate_parallax_eye_shader()
        assert "_IOR" in result
        assert "refractionFactor" in result

    def test_cornea_specular(self):
        """Should include sharp specular for wet cornea look."""
        result = generate_parallax_eye_shader()
        assert "_CorneaSmoothness" in result
        assert "_CorneaSpecular" in result
        assert "specPower" in result

    def test_fresnel_rim(self):
        """Should include fresnel for cornea rim."""
        result = generate_parallax_eye_shader()
        assert "fresnel" in result

    def test_custom_iris_depth(self):
        result = generate_parallax_eye_shader(iris_depth=0.8)
        assert "0.8" in result

    def test_custom_pupil_scale(self):
        result = generate_parallax_eye_shader(pupil_scale=0.5)
        assert "0.5" in result

    def test_custom_ior(self):
        result = generate_parallax_eye_shader(ior=1.5)
        assert "1.5" in result


# ---------------------------------------------------------------------------
# CHAR-08: Micro-detail normal compositor tests
# ---------------------------------------------------------------------------


class TestMicroDetailNormal:
    """Tests for generate_micro_detail_normal_script -- CHAR-08."""

    def test_basic_generation(self):
        result = generate_micro_detail_normal_script()
        assert "MicroDetailNormalCompositor" in result
        assert "MonoBehaviour" in result

    def test_runtime_component(self):
        """Should be a runtime component (not editor-only)."""
        result = generate_micro_detail_normal_script()
        assert "[ExecuteAlways]" in result
        assert "RequireComponent" in result

    def test_texture_references(self):
        result = generate_micro_detail_normal_script()
        assert "baseNormalMap" in result
        assert "detailNormalMap" in result

    def test_detail_settings(self):
        result = generate_micro_detail_normal_script()
        assert "detailTiling" in result
        assert "detailStrength" in result

    def test_material_property_block(self):
        """Should use MaterialPropertyBlock for per-instance overrides."""
        result = generate_micro_detail_normal_script()
        assert "MaterialPropertyBlock" in result
        assert "SetPropertyBlock" in result

    def test_property_id_caching(self):
        """Should cache Shader.PropertyToID for performance."""
        result = generate_micro_detail_normal_script()
        assert "Shader.PropertyToID" in result
        assert "CachePropertyIds" in result

    def test_runtime_api(self):
        """Should provide runtime API for strength/tiling changes."""
        result = generate_micro_detail_normal_script()
        assert "SetDetailStrength" in result
        assert "SetDetailTiling" in result

    def test_custom_detail_tiling(self):
        result = generate_micro_detail_normal_script(detail_tiling=20.0)
        assert "20.0f" in result

    def test_custom_detail_strength(self):
        result = generate_micro_detail_normal_script(detail_strength=0.8)
        assert "0.8f" in result

    def test_custom_property_names(self):
        result = generate_micro_detail_normal_script(
            base_normal_property="_CustomNormal",
            detail_normal_property="_CustomDetail",
        )
        assert "_CustomNormal" in result
        assert "_CustomDetail" in result

    def test_editor_inspector(self):
        """Should include custom editor inspector."""
        result = generate_micro_detail_normal_script()
        assert "CustomEditor" in result
        assert "MicroDetailNormalCompositorEditor" in result
        assert "OnInspectorGUI" in result

    def test_cleanup_on_disable(self):
        """Should clean up property block on disable."""
        result = generate_micro_detail_normal_script()
        assert "OnDisable" in result
        assert "SetPropertyBlock(null)" in result

    def test_on_validate(self):
        """Should respond to inspector changes via OnValidate."""
        result = generate_micro_detail_normal_script()
        assert "OnValidate" in result
