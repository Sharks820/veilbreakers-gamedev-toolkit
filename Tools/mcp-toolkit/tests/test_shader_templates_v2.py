"""Unit tests for SHDR-01 and SHDR-02 shader template generators.

Tests that generate_arbitrary_shader and generate_renderer_feature produce
valid ShaderLab / C# source with correct structure, URP 17 RenderGraph API
usage, and no regressions on existing shader functions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_arbitrary_shader,
    generate_renderer_feature,
    # Original 7 functions (regression checks)
    generate_corruption_shader,
    generate_dissolve_shader,
    generate_force_field_shader,
    generate_water_shader,
    generate_foliage_shader,
    generate_outline_shader,
    generate_damage_overlay_shader,
)


# ---------------------------------------------------------------------------
# SHDR-01: Arbitrary shader builder
# ---------------------------------------------------------------------------


class TestArbitraryShader:
    """Tests for generate_arbitrary_shader() -- SHDR-01."""

    def test_basic_opaque_shader(self):
        result = generate_arbitrary_shader("TestShader")
        assert 'Shader "VeilBreakers/Custom/TestShader"' in result
        assert "HLSLPROGRAM" in result
        assert "ENDHLSL" in result
        assert '"RenderType"="Opaque"' in result
        assert '"RenderPipeline"="UniversalPipeline"' in result

    def test_transparent_shader(self):
        result = generate_arbitrary_shader("GlassShader", render_type="Transparent")
        assert '"Queue"="Transparent"' in result
        assert "Blend SrcAlpha OneMinusSrcAlpha" in result
        assert "ZWrite Off" in result

    def test_custom_properties_range(self):
        props = [
            {
                "name": "_Intensity",
                "display_name": "Effect Intensity",
                "type": "Range(0,1)",
                "default": "0.5",
            }
        ]
        result = generate_arbitrary_shader("PropShader", properties=props)
        assert '_Intensity ("Effect Intensity", Range(0,1)) = 0.5' in result

    def test_color_property(self):
        props = [
            {
                "name": "_TintColor",
                "display_name": "Tint Color",
                "type": "Color",
                "default": "(1,0,0,1)",
            }
        ]
        result = generate_arbitrary_shader("ColorShader", properties=props)
        assert "Color" in result
        assert "_TintColor" in result
        assert "(1,0,0,1)" in result

    def test_texture_property(self):
        props = [
            {
                "name": "_MainTex",
                "display_name": "Main Texture",
                "type": "2D",
            }
        ]
        result = generate_arbitrary_shader("TexShader", properties=props)
        assert '2D' in result
        assert '"white" {}' in result
        assert "TEXTURE2D(_MainTex)" in result
        assert "SAMPLER(sampler_MainTex)" in result

    def test_custom_fragment(self):
        result = generate_arbitrary_shader(
            "RedShader",
            fragment_code="return half4(1, 0, 0, 1);",
        )
        assert "return half4(1, 0, 0, 1);" in result

    def test_custom_vertex(self):
        custom_vert = "Varyings o; o.positionCS = float4(0,0,0,1); return o;"
        result = generate_arbitrary_shader(
            "CustomVert",
            vertex_code=custom_vert,
        )
        assert custom_vert in result

    def test_two_pass(self):
        result = generate_arbitrary_shader(
            "TwoPass",
            two_passes=True,
            second_pass_fragment="return half4(0, 0, 0, 1);",
        )
        # Should have two Pass blocks
        assert result.count("HLSLPROGRAM") == 2
        assert result.count("ENDHLSL") == 2
        assert 'Name "ForwardLit"' in result
        assert 'Name "SecondPass"' in result

    def test_extra_pragmas(self):
        result = generate_arbitrary_shader(
            "FogShader",
            pragma_directives=["#pragma multi_compile_fog"],
        )
        assert "#pragma multi_compile_fog" in result

    def test_custom_path(self):
        result = generate_arbitrary_shader(
            "MyEffect",
            shader_path="Game/Effects",
        )
        assert 'Shader "Game/Effects/MyEffect"' in result

    def test_balanced_braces(self):
        """All generated shaders should have balanced braces in the ShaderLab structure."""
        configs = [
            {"shader_name": "Basic"},
            {"shader_name": "Trans", "render_type": "Transparent"},
            {
                "shader_name": "Props",
                "properties": [
                    {"name": "_Val", "type": "Float"},
                    {"name": "_Col", "type": "Color"},
                ],
            },
            {"shader_name": "TwoP", "two_passes": True},
        ]
        for cfg in configs:
            result = generate_arbitrary_shader(**cfg)
            # In ShaderLab, texture property defaults include {} which may not
            # balance with structural braces, so we count only structural braces
            # by checking the overall structure is well-formed
            open_count = result.count("{")
            close_count = result.count("}")
            assert open_count == close_count, (
                f"Unbalanced braces for config {cfg}: {open_count} open vs {close_count} close"
            )

    def test_urp_include_present(self):
        result = generate_arbitrary_shader("IncTest")
        assert '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"' in result

    def test_fallback_shader(self):
        result = generate_arbitrary_shader("FallbackTest")
        assert 'FallBack "Hidden/InternalErrorShader"' in result

    def test_transparent_cutout(self):
        result = generate_arbitrary_shader("CutoutTest", render_type="TransparentCutout")
        assert '"Queue"="AlphaTest"' in result
        assert "ZWrite On" in result

    def test_cull_off(self):
        result = generate_arbitrary_shader("DoubleSided", cull="Off")
        assert "Cull Off" in result

    def test_cbuffer_generated_for_properties(self):
        props = [
            {"name": "_Speed", "type": "Float", "default": "1.0"},
            {"name": "_Color", "type": "Color"},
        ]
        result = generate_arbitrary_shader("CbufTest", properties=props)
        assert "CBUFFER_START(UnityPerMaterial)" in result
        assert "float _Speed;" in result
        assert "float4 _Color;" in result
        assert "CBUFFER_END" in result

    def test_extra_includes(self):
        result = generate_arbitrary_shader(
            "IncShader",
            include_paths=["Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"],
        )
        assert '#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"' in result

    def test_vector_property(self):
        props = [{"name": "_Direction", "type": "Vector", "default": "(1,0,0,0)"}]
        result = generate_arbitrary_shader("VecShader", properties=props)
        assert "Vector" in result
        assert "_Direction" in result

    def test_shader_name_sanitization(self):
        result = generate_arbitrary_shader('Test"Shader<>')
        # Special chars should be stripped
        assert '"' not in result.split("\n")[0].replace('Shader "', '').replace('"', '')
        assert "TestShader" in result

    def test_custom_tags(self):
        result = generate_arbitrary_shader(
            "TagTest",
            tags={"DisableBatching": "True"},
        )
        assert '"DisableBatching"="True"' in result

    def test_default_vertex_generates_transform(self):
        result = generate_arbitrary_shader("DefaultVert")
        assert "TransformObjectToHClip" in result
        assert "TransformObjectToWorldNormal" in result


# ---------------------------------------------------------------------------
# SHDR-02: URP ScriptableRendererFeature + RenderGraph pass
# ---------------------------------------------------------------------------


class TestRendererFeature:
    """Tests for generate_renderer_feature() -- SHDR-02."""

    def test_basic_feature(self):
        result = generate_renderer_feature("CustomEffect")
        assert "ScriptableRendererFeature" in result
        assert "ScriptableRenderPass" in result
        assert "RecordRenderGraph" in result
        assert "RenderGraph" in result
        assert "ContextContainer" in result

    def test_feature_class_name(self):
        result = generate_renderer_feature("CustomBloom")
        assert "CustomBloomFeature" in result
        assert "CustomBloomPass" in result

    def test_settings_class(self):
        settings = [
            {
                "type": "float",
                "name": "intensity",
                "default": "0.5f",
                "attribute": "Range(0f, 1f)",
            }
        ]
        result = generate_renderer_feature("Bloom", settings_fields=settings)
        assert "BloomSettings" in result
        assert "[Range(0f, 1f)]" in result
        assert "public float intensity = 0.5f;" in result

    def test_render_graph_api(self):
        result = generate_renderer_feature("TestFeature")
        # Must NOT contain the legacy Execute method
        assert "override void Execute(" not in result
        # Must contain the modern RecordRenderGraph
        assert "override void RecordRenderGraph(" in result

    def test_required_usings(self):
        result = generate_renderer_feature("UsingTest")
        assert "using UnityEngine.Rendering.RenderGraphModule;" in result
        assert "using UnityEngine.Rendering.Universal;" in result
        assert "using UnityEngine.Rendering;" in result
        assert "using UnityEngine;" in result

    def test_material_setup(self):
        result = generate_renderer_feature("MatTest")
        assert "CoreUtils.CreateEngineMaterial" in result
        assert "CoreUtils.Destroy" in result

    def test_pass_event_configurable(self):
        result = generate_renderer_feature(
            "EventTest",
            render_pass_event="AfterRenderingTransparents",
        )
        assert "RenderPassEvent.AfterRenderingTransparents" in result

    def test_material_properties(self):
        mat_props = [
            {"name": "_Intensity", "type": "float", "value": "0.5f"},
        ]
        result = generate_renderer_feature("PropTest", material_properties=mat_props)
        assert 'SetFloat("_Intensity", 0.5f)' in result

    def test_namespace_wrapping(self):
        result = generate_renderer_feature(
            "NsTest",
            namespace="VeilBreakers.Rendering",
        )
        assert "namespace VeilBreakers.Rendering" in result
        assert "{" in result

    def test_balanced_braces(self):
        """All renderer feature configurations should produce balanced C# braces."""
        configs = [
            {"feature_name": "Basic"},
            {
                "feature_name": "WithSettings",
                "settings_fields": [
                    {"type": "float", "name": "val", "default": "1f"},
                ],
            },
            {"feature_name": "WithNs", "namespace": "Test.NS"},
            {
                "feature_name": "Full",
                "namespace": "A.B",
                "settings_fields": [
                    {"type": "float", "name": "x", "default": "0f"},
                    {"type": "int", "name": "y", "default": "1"},
                ],
                "material_properties": [
                    {"name": "_X", "type": "float", "value": "0f"},
                ],
            },
        ]
        for cfg in configs:
            result = generate_renderer_feature(**cfg)
            assert result.count("{") == result.count("}"), (
                f"Unbalanced braces for config {cfg}"
            )

    def test_shader_property_name(self):
        result = generate_renderer_feature("ShaderProp", shader_property_name="_myShader")
        assert "private Shader _myShader;" in result
        assert "_myShader != null" in result

    def test_default_blit_pass(self):
        result = generate_renderer_feature("BlitTest")
        assert "AddBlitPass" in result
        assert "activeColorTexture" in result
        assert "UniversalResourceData" in result

    def test_custom_pass_code(self):
        custom = "// Custom pass code here"
        result = generate_renderer_feature("CustomPass", pass_code=custom)
        assert "// Custom pass code here" in result

    def test_camera_type_guard(self):
        result = generate_renderer_feature("CamGuard")
        assert "CameraType.Game" in result

    def test_back_buffer_guard(self):
        result = generate_renderer_feature("BackBuf")
        assert "isActiveTargetBackBuffer" in result

    def test_int_material_property(self):
        mat_props = [{"name": "_Count", "type": "int", "value": "3"}]
        result = generate_renderer_feature("IntProp", material_properties=mat_props)
        assert 'SetInt("_Count", 3)' in result

    def test_color_material_property(self):
        mat_props = [{"name": "_Tint", "type": "Color", "value": "Color.red"}]
        result = generate_renderer_feature("ColProp", material_properties=mat_props)
        assert 'SetColor("_Tint", Color.red)' in result

    def test_dispose_method(self):
        result = generate_renderer_feature("DispTest")
        assert "protected override void Dispose(bool disposing)" in result

    def test_serializable_settings(self):
        result = generate_renderer_feature("SerTest")
        assert "[System.Serializable]" in result

    def test_feature_name_sanitization(self):
        result = generate_renderer_feature("My-Cool Feature!")
        # Special chars removed, valid C# identifiers created
        assert "MyCoolFeatureFeature" in result
        assert "MyCoolFeaturePass" in result


# ---------------------------------------------------------------------------
# Regression: Existing shader functions still work
# ---------------------------------------------------------------------------


class TestExistingShadersNotBroken:
    """Verify all 7 original shader functions still import and produce output."""

    def test_all_original_shaders_importable(self):
        """Each original shader function should return a non-empty string."""
        fns = [
            generate_corruption_shader,
            generate_dissolve_shader,
            generate_force_field_shader,
            generate_water_shader,
            generate_foliage_shader,
            generate_outline_shader,
            generate_damage_overlay_shader,
        ]
        for fn in fns:
            result = fn()
            assert isinstance(result, str), f"{fn.__name__} did not return a string"
            assert len(result) > 100, f"{fn.__name__} returned too short output"

    def test_corruption_shader_still_works(self):
        result = generate_corruption_shader()
        assert "_CorruptionAmount" in result
        assert 'Shader "VeilBreakers/Corruption"' in result
        assert "HLSLPROGRAM" in result
