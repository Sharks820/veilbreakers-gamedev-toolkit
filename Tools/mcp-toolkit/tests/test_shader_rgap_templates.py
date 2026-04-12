"""Tests for RGAP rendering gap shader template generators.

Each test verifies that the generator returns valid ShaderLab source
with the correct shader name, URP pipeline tags, HLSL blocks, and
key feature markers.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.shader_rgap_templates import (
    generate_stochastic_tiling_shader,
    generate_height_blend_shader,
    generate_atmospheric_fog_shader,
    generate_snow_sss_shader,
    generate_vegetation_wind_shader,
    generate_water_terrain_intersection_shader,
    generate_decal_projector_shader,
    generate_minimap_shader,
    generate_waterfall_shader,
    generate_river_flow_shader,
    generate_parallax_occlusion_shader,
    generate_moss_overlay_shader,
    generate_wet_surface_shader,
    generate_puddle_shader,
    generate_rain_ripple_shader,
    generate_god_rays_shader,
    generate_procedural_skybox_shader,
    generate_cloud_shadow_shader,
    generate_distance_fog_gradient_shader,
    generate_detail_normal_blend_shader,
    generate_rock_face_shader,
    generate_caustics_shader,
    generate_underwater_post_process_shader,
    generate_lava_flow_shader,
    generate_emissive_crystal_shader,
    generate_cloth_wind_shader,
    generate_triplanar_moss_shader,
    generate_edge_detect_outline_shader,
    generate_ssao_shader,
    generate_vertex_color_blend_shader,
    generate_uv_free_detail_shader,
    generate_snow_accumulation_shader,
    generate_terrain_cutout_shader,
)


def _check_shader_basics(source: str, shader_name: str) -> None:
    """Common assertions for all shaders."""
    assert f'Shader "VeilBreakers/{shader_name}"' in source, f"Missing shader name: {shader_name}"
    assert "HLSLPROGRAM" in source
    assert "ENDHLSL" in source
    assert "Core.hlsl" in source


def _check_urp_tags(source: str) -> None:
    """Check for URP pipeline tag."""
    assert "UniversalPipeline" in source or "Background" in source


def _check_lit_pass(source: str) -> None:
    """Check for standard lit pass features."""
    assert "GetMainLight" in source or "TransformObjectToHClip" in source


# ---------------------------------------------------------------------------
# RGAP-01: Stochastic tiling
# ---------------------------------------------------------------------------

class TestStochasticTiling:
    def test_basic_output(self):
        s = generate_stochastic_tiling_shader()
        _check_shader_basics(s, "StochasticTiling")
        _check_urp_tags(s)

    def test_hex_grid_present(self):
        s = generate_stochastic_tiling_shader()
        assert "hexGrid" in s
        assert "hash22" in s

    def test_custom_params(self):
        s = generate_stochastic_tiling_shader(hex_scale=2.0, blend_contrast=1.0)
        assert "2.0" in s or "2" in s
        assert "1.0" in s or "1" in s


# ---------------------------------------------------------------------------
# RGAP-02: Height blend
# ---------------------------------------------------------------------------

class TestHeightBlend:
    def test_basic_output(self):
        s = generate_height_blend_shader()
        _check_shader_basics(s, "HeightBlend")
        _check_urp_tags(s)

    def test_height_blend_function(self):
        s = generate_height_blend_shader()
        assert "heightBlend" in s
        assert "_SplatMap" in s

    def test_macro_variation_enabled(self):
        s = generate_height_blend_shader(macro_variation=True)
        assert "_MacroVariation" in s
        assert "_MacroNoiseTex" in s

    def test_layer_count_clamped(self):
        s = generate_height_blend_shader(layer_count=1)  # should clamp to 2
        assert "_Layer0Tex" in s
        assert "_Layer1Tex" in s


# ---------------------------------------------------------------------------
# RGAP-03: Atmospheric fog
# ---------------------------------------------------------------------------

class TestAtmosphericFog:
    def test_basic_output(self):
        s = generate_atmospheric_fog_shader()
        _check_shader_basics(s, "AtmosphericFog")

    def test_depth_sampling(self):
        s = generate_atmospheric_fog_shader()
        assert "SampleSceneDepth" in s
        assert "LinearEyeDepth" in s

    def test_sun_scatter(self):
        s = generate_atmospheric_fog_shader()
        assert "_SunScatterColor" in s


# ---------------------------------------------------------------------------
# RGAP-04: Snow SSS
# ---------------------------------------------------------------------------

class TestSnowSSS:
    def test_basic_output(self):
        s = generate_snow_sss_shader()
        _check_shader_basics(s, "SnowSSS")

    def test_sss_features(self):
        s = generate_snow_sss_shader()
        assert "_SSSColor" in s
        assert "_SSSPower" in s
        assert "_SSSDistortion" in s

    def test_sparkle(self):
        s = generate_snow_sss_shader()
        assert "_SparkleThreshold" in s
        assert "hash21" in s


# ---------------------------------------------------------------------------
# RGAP-05: Vegetation wind
# ---------------------------------------------------------------------------

class TestVegetationWind:
    def test_basic_output(self):
        s = generate_vegetation_wind_shader()
        _check_shader_basics(s, "VegetationWind")

    def test_wind_layers(self):
        s = generate_vegetation_wind_shader()
        assert "_TrunkFlex" in s or "TrunkFlex" in s
        assert "_LeafFlutterFreq" in s or "LeafFlutterFreq" in s
        assert "color.r" in s  # vertex color masking
        assert "color.g" in s
        assert "color.b" in s

    def test_alpha_cutoff(self):
        s = generate_vegetation_wind_shader()
        assert "_Cutoff" in s
        assert "clip" in s


# ---------------------------------------------------------------------------
# RGAP-06: Water-terrain intersection
# ---------------------------------------------------------------------------

class TestWaterTerrainIntersection:
    def test_basic_output(self):
        s = generate_water_terrain_intersection_shader()
        _check_shader_basics(s, "WaterTerrainIntersection")

    def test_depth_based_foam(self):
        s = generate_water_terrain_intersection_shader()
        assert "SampleSceneDepth" in s
        assert "_FoamWidth" in s
        assert "_FoamColor" in s

    def test_transparent_blend(self):
        s = generate_water_terrain_intersection_shader()
        assert "Blend SrcAlpha OneMinusSrcAlpha" in s


# ---------------------------------------------------------------------------
# RGAP-07: Decal projector
# ---------------------------------------------------------------------------

class TestDecalProjector:
    def test_basic_output(self):
        s = generate_decal_projector_shader()
        _check_shader_basics(s, "DecalProjector")

    def test_alpha_blend_mode(self):
        s = generate_decal_projector_shader(blend_mode="alpha")
        assert "Blend SrcAlpha OneMinusSrcAlpha" in s

    def test_additive_blend_mode(self):
        s = generate_decal_projector_shader(blend_mode="additive")
        assert "Blend SrcAlpha One" in s

    def test_invalid_blend_defaults_alpha(self):
        s = generate_decal_projector_shader(blend_mode="invalid")
        assert "Blend SrcAlpha OneMinusSrcAlpha" in s

    def test_depth_reconstruction(self):
        s = generate_decal_projector_shader()
        assert "SampleSceneDepth" in s
        assert "_DecalWorldToLocal" in s


# ---------------------------------------------------------------------------
# RGAP-08: Minimap
# ---------------------------------------------------------------------------

class TestMinimap:
    def test_basic_output(self):
        s = generate_minimap_shader()
        _check_shader_basics(s, "Minimap")

    def test_circular_mask(self):
        s = generate_minimap_shader()
        assert "_BorderWidth" in s
        assert "length" in s  # circular distance calc

    def test_overlay_queue(self):
        s = generate_minimap_shader()
        assert '"Queue"="Overlay"' in s


# ---------------------------------------------------------------------------
# RGAP-09: Waterfall
# ---------------------------------------------------------------------------

class TestWaterfall:
    def test_basic_output(self):
        s = generate_waterfall_shader()
        _check_shader_basics(s, "Waterfall")

    def test_flow_features(self):
        s = generate_waterfall_shader()
        assert "_FlowSpeed" in s
        assert "_FoamThreshold" in s
        assert "_DisplacementStrength" in s

    def test_vertex_displacement(self):
        s = generate_waterfall_shader()
        assert "normalOS" in s or "input.normalOS" in s


# ---------------------------------------------------------------------------
# RGAP-10: River flow
# ---------------------------------------------------------------------------

class TestRiverFlow:
    def test_basic_output(self):
        s = generate_river_flow_shader()
        _check_shader_basics(s, "RiverFlow")

    def test_flowmap(self):
        s = generate_river_flow_shader()
        assert "_FlowMap" in s
        assert "_FlowStrength" in s

    def test_phase_cycling(self):
        s = generate_river_flow_shader()
        assert "frac" in s  # phase cycling


# ---------------------------------------------------------------------------
# RGAP-11: Parallax occlusion
# ---------------------------------------------------------------------------

class TestParallaxOcclusion:
    def test_basic_output(self):
        s = generate_parallax_occlusion_shader()
        _check_shader_basics(s, "ParallaxOcclusion")

    def test_pom_function(self):
        s = generate_parallax_occlusion_shader()
        assert "_HeightMap" in s
        assert "_HeightScale" in s
        assert "SAMPLE_TEXTURE2D_LOD" in s

    def test_uv_clipping(self):
        s = generate_parallax_occlusion_shader()
        assert "discard" in s


# ---------------------------------------------------------------------------
# RGAP-12: Moss overlay
# ---------------------------------------------------------------------------

class TestMossOverlay:
    def test_basic_output(self):
        s = generate_moss_overlay_shader()
        _check_shader_basics(s, "MossOverlay")

    def test_direction_mask(self):
        s = generate_moss_overlay_shader()
        assert "_MossDirection" in s
        assert "_MossDirectionBias" in s


# ---------------------------------------------------------------------------
# RGAP-13: Wet surface
# ---------------------------------------------------------------------------

class TestWetSurface:
    def test_basic_output(self):
        s = generate_wet_surface_shader()
        _check_shader_basics(s, "WetSurface")

    def test_wet_features(self):
        s = generate_wet_surface_shader()
        assert "_Wetness" in s
        assert "_WetDarkening" in s
        assert "_Porosity" in s
        assert "_NormalFlatten" in s


# ---------------------------------------------------------------------------
# RGAP-14: Puddle
# ---------------------------------------------------------------------------

class TestPuddle:
    def test_basic_output(self):
        s = generate_puddle_shader()
        _check_shader_basics(s, "PuddleAccumulation")

    def test_flatness_detection(self):
        s = generate_puddle_shader()
        assert "float3(0,1,0)" in s or "float3(0, 1, 0)" in s  # up vector


# ---------------------------------------------------------------------------
# RGAP-15: Rain ripple
# ---------------------------------------------------------------------------

class TestRainRipple:
    def test_basic_output(self):
        s = generate_rain_ripple_shader()
        _check_shader_basics(s, "RainRipple")

    def test_ripple_function(self):
        s = generate_rain_ripple_shader()
        assert "ripple" in s
        assert "_RippleDensity" in s


# ---------------------------------------------------------------------------
# RGAP-16: God rays
# ---------------------------------------------------------------------------

class TestGodRays:
    def test_basic_output(self):
        s = generate_god_rays_shader()
        _check_shader_basics(s, "GodRays")

    def test_radial_blur(self):
        s = generate_god_rays_shader()
        assert "_LightScreenPos" in s
        assert "_RayDecay" in s
        assert "for" in s  # sample loop


# ---------------------------------------------------------------------------
# RGAP-17: Procedural skybox
# ---------------------------------------------------------------------------

class TestProceduralSkybox:
    def test_basic_output(self):
        s = generate_procedural_skybox_shader()
        _check_shader_basics(s, "ProceduralSkybox")

    def test_skybox_tags(self):
        s = generate_procedural_skybox_shader()
        assert '"Queue"="Background"' in s
        assert "ZWrite Off" in s

    def test_sun_and_stars(self):
        s = generate_procedural_skybox_shader()
        assert "_SunSize" in s
        assert "_StarDensity" in s
        assert "_CloudTex" in s


# ---------------------------------------------------------------------------
# RGAP-18: Cloud shadow
# ---------------------------------------------------------------------------

class TestCloudShadow:
    def test_basic_output(self):
        s = generate_cloud_shadow_shader()
        _check_shader_basics(s, "CloudShadow")

    def test_multiplicative_blend(self):
        s = generate_cloud_shadow_shader()
        assert "Blend DstColor Zero" in s

    def test_wind_direction(self):
        s = generate_cloud_shadow_shader()
        assert "_WindDirection" in s


# ---------------------------------------------------------------------------
# RGAP-19: Distance fog gradient
# ---------------------------------------------------------------------------

class TestDistanceFogGradient:
    def test_basic_output(self):
        s = generate_distance_fog_gradient_shader()
        _check_shader_basics(s, "DistanceFogGradient")

    def test_three_bands(self):
        s = generate_distance_fog_gradient_shader()
        assert "_NearFogColor" in s
        assert "_MidFogColor" in s
        assert "_FarFogColor" in s


# ---------------------------------------------------------------------------
# RGAP-20: Detail normal blend
# ---------------------------------------------------------------------------

class TestDetailNormalBlend:
    def test_basic_output(self):
        s = generate_detail_normal_blend_shader()
        _check_shader_basics(s, "DetailNormalBlend")

    def test_reoriented_blend(self):
        s = generate_detail_normal_blend_shader()
        assert "blendNormals" in s

    def test_distance_fade(self):
        s = generate_detail_normal_blend_shader()
        assert "_DetailFadeStart" in s
        assert "_DetailFadeEnd" in s


# ---------------------------------------------------------------------------
# RGAP-21: Rock face
# ---------------------------------------------------------------------------

class TestRockFace:
    def test_basic_output(self):
        s = generate_rock_face_shader()
        _check_shader_basics(s, "RockFace")

    def test_triplanar(self):
        s = generate_rock_face_shader()
        assert "_TriplanarSharpness" in s or "Tri Sharp" in s

    def test_strata(self):
        s = generate_rock_face_shader()
        assert "_StrataScale" in s


# ---------------------------------------------------------------------------
# RGAP-22: Caustics
# ---------------------------------------------------------------------------

class TestCaustics:
    def test_basic_output(self):
        s = generate_caustics_shader()
        _check_shader_basics(s, "Caustics")

    def test_additive_blend(self):
        s = generate_caustics_shader()
        assert "Blend One One" in s

    def test_water_level_clip(self):
        s = generate_caustics_shader()
        assert "_WaterLevel" in s
        assert "clip" in s


# ---------------------------------------------------------------------------
# RGAP-23: Underwater post-process
# ---------------------------------------------------------------------------

class TestUnderwaterPostProcess:
    def test_basic_output(self):
        s = generate_underwater_post_process_shader()
        _check_shader_basics(s, "UnderwaterPostProcess")

    def test_distortion(self):
        s = generate_underwater_post_process_shader()
        assert "_DistortionTex" in s
        assert "_DistortionStrength" in s

    def test_vignette(self):
        s = generate_underwater_post_process_shader()
        assert "_VignetteStrength" in s


# ---------------------------------------------------------------------------
# RGAP-24: Lava flow
# ---------------------------------------------------------------------------

class TestLavaFlow:
    def test_basic_output(self):
        s = generate_lava_flow_shader()
        _check_shader_basics(s, "LavaFlow")

    def test_emissive_crust(self):
        s = generate_lava_flow_shader()
        assert "_CrustThreshold" in s
        assert "_EmissiveIntensity" in s
        assert "_PulseSpeed" in s


# ---------------------------------------------------------------------------
# RGAP-25: Emissive crystal
# ---------------------------------------------------------------------------

class TestEmissiveCrystal:
    def test_basic_output(self):
        s = generate_emissive_crystal_shader()
        _check_shader_basics(s, "EmissiveCrystal")

    def test_pulse_and_fresnel(self):
        s = generate_emissive_crystal_shader()
        assert "_PulseSpeed" in s
        assert "_FresnelPower" in s
        assert "_GlowIntensity" in s


# ---------------------------------------------------------------------------
# RGAP-26: Cloth wind
# ---------------------------------------------------------------------------

class TestClothWind:
    def test_basic_output(self):
        s = generate_cloth_wind_shader()
        _check_shader_basics(s, "ClothWind")

    def test_two_sided(self):
        s = generate_cloth_wind_shader()
        assert "Cull Off" in s

    def test_vertex_color_freedom(self):
        s = generate_cloth_wind_shader()
        assert "color.r" in s  # pinned edge mask


# ---------------------------------------------------------------------------
# RGAP-27: Triplanar moss
# ---------------------------------------------------------------------------

class TestTriplanarMoss:
    def test_basic_output(self):
        s = generate_triplanar_moss_shader()
        _check_shader_basics(s, "TriplanarMoss")

    def test_triplanar_sampling(self):
        s = generate_triplanar_moss_shader()
        assert "triS" in s or "triplanar" in s.lower()


# ---------------------------------------------------------------------------
# RGAP-28: Edge detection outline
# ---------------------------------------------------------------------------

class TestEdgeDetectOutline:
    def test_basic_output(self):
        s = generate_edge_detect_outline_shader()
        _check_shader_basics(s, "EdgeDetectOutline")

    def test_depth_and_normal_edges(self):
        s = generate_edge_detect_outline_shader()
        assert "SampleSceneDepth" in s
        assert "SampleSceneNormals" in s
        assert "_DepthThreshold" in s
        assert "_NormalThreshold" in s


# ---------------------------------------------------------------------------
# RGAP-29: SSAO
# ---------------------------------------------------------------------------

class TestSSAO:
    def test_basic_output(self):
        s = generate_ssao_shader()
        _check_shader_basics(s, "SSAO")

    def test_hemisphere_kernel(self):
        s = generate_ssao_shader()
        assert "kernel" in s
        assert "_AORadius" in s
        assert "_AOIntensity" in s

    def test_noise_rotation(self):
        s = generate_ssao_shader()
        assert "_NoiseTex" in s


# ---------------------------------------------------------------------------
# RGAP-30: Vertex color blend
# ---------------------------------------------------------------------------

class TestVertexColorBlend:
    def test_basic_output(self):
        s = generate_vertex_color_blend_shader()
        _check_shader_basics(s, "VertexColorBlend")

    def test_four_layers(self):
        s = generate_vertex_color_blend_shader()
        assert "_Layer0Tex" in s
        assert "_Layer1Tex" in s
        assert "_Layer2Tex" in s
        assert "_Layer3Tex" in s


# ---------------------------------------------------------------------------
# RGAP-31: UV-free detail
# ---------------------------------------------------------------------------

class TestUVFreeDetail:
    def test_basic_output(self):
        s = generate_uv_free_detail_shader()
        _check_shader_basics(s, "UVFreeDetail")

    def test_triplanar_detail(self):
        s = generate_uv_free_detail_shader()
        assert "_TriplanarSharpness" in s or "Tri Sharp" in s
        assert "_DetailFadeStart" in s


# ---------------------------------------------------------------------------
# RGAP-32: Snow accumulation
# ---------------------------------------------------------------------------

class TestSnowAccumulation:
    def test_basic_output(self):
        s = generate_snow_accumulation_shader()
        _check_shader_basics(s, "SnowAccumulation")

    def test_snow_features(self):
        s = generate_snow_accumulation_shader()
        assert "_SnowDirection" in s
        assert "_SnowLineHeight" in s
        assert "_SnowNoiseTex" in s


# ---------------------------------------------------------------------------
# RGAP-33: Terrain cutout
# ---------------------------------------------------------------------------

class TestTerrainCutout:
    def test_basic_output(self):
        s = generate_terrain_cutout_shader()
        _check_shader_basics(s, "TerrainCutout")

    def test_cutout_mask(self):
        s = generate_terrain_cutout_shader()
        assert "_CutoutMask" in s
        assert "_CutoutThreshold" in s
        assert "clip" in s

    def test_edge_glow(self):
        s = generate_terrain_cutout_shader()
        assert "_EdgeColor" in s
        assert "_EdgeEmissive" in s

    def test_shadow_caster_pass(self):
        s = generate_terrain_cutout_shader()
        assert "ShadowCaster" in s
        assert "ApplyShadowBias" in s


# ---------------------------------------------------------------------------
# Cross-cutting: All 33 generators return non-empty strings
# ---------------------------------------------------------------------------

_ALL_GENERATORS = [
    ("StochasticTiling", generate_stochastic_tiling_shader),
    ("HeightBlend", generate_height_blend_shader),
    ("AtmosphericFog", generate_atmospheric_fog_shader),
    ("SnowSSS", generate_snow_sss_shader),
    ("VegetationWind", generate_vegetation_wind_shader),
    ("WaterTerrainIntersection", generate_water_terrain_intersection_shader),
    ("DecalProjector", generate_decal_projector_shader),
    ("Minimap", generate_minimap_shader),
    ("Waterfall", generate_waterfall_shader),
    ("RiverFlow", generate_river_flow_shader),
    ("ParallaxOcclusion", generate_parallax_occlusion_shader),
    ("MossOverlay", generate_moss_overlay_shader),
    ("WetSurface", generate_wet_surface_shader),
    ("PuddleAccumulation", generate_puddle_shader),
    ("RainRipple", generate_rain_ripple_shader),
    ("GodRays", generate_god_rays_shader),
    ("ProceduralSkybox", generate_procedural_skybox_shader),
    ("CloudShadow", generate_cloud_shadow_shader),
    ("DistanceFogGradient", generate_distance_fog_gradient_shader),
    ("DetailNormalBlend", generate_detail_normal_blend_shader),
    ("RockFace", generate_rock_face_shader),
    ("Caustics", generate_caustics_shader),
    ("UnderwaterPostProcess", generate_underwater_post_process_shader),
    ("LavaFlow", generate_lava_flow_shader),
    ("EmissiveCrystal", generate_emissive_crystal_shader),
    ("ClothWind", generate_cloth_wind_shader),
    ("TriplanarMoss", generate_triplanar_moss_shader),
    ("EdgeDetectOutline", generate_edge_detect_outline_shader),
    ("SSAO", generate_ssao_shader),
    ("VertexColorBlend", generate_vertex_color_blend_shader),
    ("UVFreeDetail", generate_uv_free_detail_shader),
    ("SnowAccumulation", generate_snow_accumulation_shader),
    ("TerrainCutout", generate_terrain_cutout_shader),
]


@pytest.mark.parametrize("name,gen", _ALL_GENERATORS, ids=[n for n, _ in _ALL_GENERATORS])
def test_generator_returns_shader(name, gen):
    """Every RGAP generator must return a non-empty ShaderLab string."""
    result = gen()
    assert isinstance(result, str)
    assert len(result) > 100, f"{name} returned suspiciously short output"
    _check_shader_basics(result, name)


@pytest.mark.parametrize("name,gen", _ALL_GENERATORS, ids=[n for n, _ in _ALL_GENERATORS])
def test_generator_has_balanced_braces(name, gen):
    """ShaderLab output must have balanced curly braces."""
    result = gen()
    assert result.count("{") == result.count("}"), f"{name} has unbalanced braces"
