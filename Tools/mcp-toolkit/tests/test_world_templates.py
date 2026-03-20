"""Unit tests for world and scene management C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
These are editor scripts and MUST contain 'using UnityEditor;' (except
the runtime part of scene transitions which must NOT).
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.world_templates import (
    generate_scene_creation_script,
    generate_scene_transition_script,
    generate_probe_setup_script,
    generate_occlusion_setup_script,
    generate_environment_setup_script,
    generate_terrain_detail_script,
    generate_tilemap_setup_script,
    generate_2d_physics_script,
    generate_time_of_day_preset_script,
)


# ---------------------------------------------------------------------------
# SCNE-01: Scene creation + async loading
# ---------------------------------------------------------------------------


class TestSceneLoading:
    """Tests for generate_scene_creation_script()."""

    def test_returns_string(self):
        result = generate_scene_creation_script()
        assert isinstance(result, str)

    def test_contains_editor_scene_manager(self):
        result = generate_scene_creation_script()
        assert "EditorSceneManager" in result

    def test_contains_load_scene_async(self):
        result = generate_scene_creation_script()
        assert "LoadSceneAsync" in result

    def test_contains_load_scene_mode(self):
        result = generate_scene_creation_script()
        assert "LoadSceneMode" in result

    def test_default_single_mode(self):
        result = generate_scene_creation_script()
        assert "LoadSceneMode.Single" in result

    def test_additive_mode(self):
        result = generate_scene_creation_script(loading_mode="additive")
        assert "LoadSceneMode.Additive" in result

    def test_custom_scene_name(self):
        result = generate_scene_creation_script(scene_name="BattleArena")
        assert "BattleArena" in result

    def test_empty_scene_setup(self):
        result = generate_scene_creation_script(scene_setup="EmptyScene")
        assert "NewSceneSetup.EmptyScene" in result

    def test_default_scene_setup(self):
        result = generate_scene_creation_script()
        assert "NewSceneSetup.DefaultGameObjects" in result

    def test_build_index_adds_to_settings(self):
        result = generate_scene_creation_script(build_index=0)
        assert "EditorBuildSettings" in result

    def test_no_build_index_skips_settings(self):
        result = generate_scene_creation_script(build_index=-1)
        assert "EditorBuildSettings" not in result

    def test_contains_menu_item(self):
        result = generate_scene_creation_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World" in result

    def test_contains_namespace(self):
        result = generate_scene_creation_script(namespace="VeilBreakers.WorldSystems")
        assert "namespace VeilBreakers.WorldSystems" in result

    def test_contains_result_json(self):
        result = generate_scene_creation_script()
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# SCNE-02: Scene transition system
# ---------------------------------------------------------------------------


class TestSceneTransition:
    """Tests for generate_scene_transition_script()."""

    def test_returns_tuple(self):
        result = generate_scene_transition_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_are_strings(self):
        editor_cs, runtime_cs = generate_scene_transition_script()
        assert isinstance(editor_cs, str)
        assert isinstance(runtime_cs, str)

    def test_runtime_contains_dont_destroy_on_load(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "DontDestroyOnLoad" in runtime_cs

    def test_runtime_contains_load_scene_async(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "LoadSceneAsync" in runtime_cs

    def test_runtime_contains_allow_scene_activation(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "allowSceneActivation" in runtime_cs

    def test_runtime_contains_fade_out(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "FadeOut" in runtime_cs

    def test_runtime_contains_fade_in(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "FadeIn" in runtime_cs

    def test_runtime_contains_ienumerator(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "IEnumerator" in runtime_cs

    def test_runtime_contains_monobehaviour(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "MonoBehaviour" in runtime_cs

    def test_runtime_contains_singleton(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "Instance" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "using UnityEditor" not in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_scene_transition_script()
        assert "MenuItem" in editor_cs

    def test_runtime_contains_progress_tracking(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "LoadProgress" in runtime_cs

    def test_custom_fade_duration(self):
        _, runtime_cs = generate_scene_transition_script(fade_duration=1.0)
        assert "1" in runtime_cs

    def test_runtime_contains_coroutine(self):
        _, runtime_cs = generate_scene_transition_script()
        assert "StartCoroutine" in runtime_cs


# ---------------------------------------------------------------------------
# SCNE-03: Reflection probes + light probes
# ---------------------------------------------------------------------------


class TestProbeSetup:
    """Tests for generate_probe_setup_script()."""

    def test_returns_string(self):
        result = generate_probe_setup_script()
        assert isinstance(result, str)

    def test_contains_reflection_probe(self):
        result = generate_probe_setup_script()
        assert "ReflectionProbe" in result

    def test_contains_reflection_probe_mode(self):
        result = generate_probe_setup_script()
        assert "ReflectionProbeMode" in result

    def test_contains_light_probe_group(self):
        result = generate_probe_setup_script()
        assert "LightProbeGroup" in result

    def test_contains_probe_positions(self):
        result = generate_probe_setup_script()
        assert "probePositions" in result

    def test_custom_resolution(self):
        result = generate_probe_setup_script(reflection_resolution=512)
        assert "512" in result

    def test_custom_probe_count(self):
        result = generate_probe_setup_script(reflection_probe_count=8)
        assert "8" in result

    def test_custom_box_size(self):
        result = generate_probe_setup_script(probe_box_size=[20.0, 10.0, 20.0])
        assert "20" in result

    def test_contains_menu_item(self):
        result = generate_probe_setup_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Setup Probes" in result

    def test_contains_box_projection(self):
        result = generate_probe_setup_script()
        assert "boxProjection" in result


# ---------------------------------------------------------------------------
# SCNE-04: Occlusion culling setup
# ---------------------------------------------------------------------------


class TestOcclusionSetup:
    """Tests for generate_occlusion_setup_script()."""

    def test_returns_string(self):
        result = generate_occlusion_setup_script()
        assert isinstance(result, str)

    def test_contains_static_editor_flags(self):
        result = generate_occlusion_setup_script()
        assert "StaticEditorFlags" in result

    def test_contains_occluder_static(self):
        result = generate_occlusion_setup_script()
        assert "OccluderStatic" in result

    def test_contains_occludee_static(self):
        result = generate_occlusion_setup_script()
        assert "OccludeeStatic" in result

    def test_contains_compute(self):
        result = generate_occlusion_setup_script()
        assert "StaticOcclusionCulling.Compute" in result

    def test_custom_occluder_size(self):
        result = generate_occlusion_setup_script(smallest_occluder=10.0)
        assert "10" in result

    def test_custom_hole_size(self):
        result = generate_occlusion_setup_script(smallest_hole=0.5)
        assert "0.5" in result

    def test_contains_menu_item(self):
        result = generate_occlusion_setup_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Setup Occlusion" in result

    def test_contains_set_static_editor_flags(self):
        result = generate_occlusion_setup_script()
        assert "SetStaticEditorFlags" in result or "GameObjectUtility" in result


# ---------------------------------------------------------------------------
# SCNE-05: HDR skybox + GI
# ---------------------------------------------------------------------------


class TestEnvironmentSetup:
    """Tests for generate_environment_setup_script()."""

    def test_returns_string(self):
        result = generate_environment_setup_script()
        assert isinstance(result, str)

    def test_contains_render_settings_skybox(self):
        result = generate_environment_setup_script()
        assert "RenderSettings.skybox" in result

    def test_contains_ambient_mode(self):
        result = generate_environment_setup_script()
        assert "AmbientMode" in result

    def test_contains_default_reflection_mode(self):
        result = generate_environment_setup_script()
        assert "defaultReflectionMode" in result

    def test_contains_lightmapping_when_gi_enabled(self):
        result = generate_environment_setup_script(enable_gi=True)
        assert "Lightmapping" in result

    def test_no_lightmapping_when_gi_disabled(self):
        result = generate_environment_setup_script(enable_gi=False)
        assert "BakeAsync" not in result

    def test_custom_skybox_shader(self):
        result = generate_environment_setup_script(skybox_shader="Skybox/Panoramic")
        assert "Skybox/Panoramic" in result

    def test_trilight_ambient_mode(self):
        result = generate_environment_setup_script(ambient_mode="Trilight")
        assert "AmbientMode.Trilight" in result

    def test_contains_menu_item(self):
        result = generate_environment_setup_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Setup Environment" in result

    def test_custom_reflection_mode(self):
        result = generate_environment_setup_script(default_reflection_mode="Custom")
        assert "DefaultReflectionMode.Custom" in result


# ---------------------------------------------------------------------------
# SCNE-06: Terrain detail painting
# ---------------------------------------------------------------------------


class TestTerrainDetail:
    """Tests for generate_terrain_detail_script()."""

    def test_returns_string(self):
        result = generate_terrain_detail_script()
        assert isinstance(result, str)

    def test_contains_detail_prototype(self):
        result = generate_terrain_detail_script()
        assert "DetailPrototype" in result

    def test_contains_detail_prototypes_assignment(self):
        result = generate_terrain_detail_script()
        assert "detailPrototypes" in result

    def test_contains_set_detail_layer(self):
        result = generate_terrain_detail_script()
        assert "SetDetailLayer" in result

    def test_contains_terrain_data(self):
        result = generate_terrain_detail_script()
        assert "TerrainData" in result

    def test_default_grass_texture(self):
        result = generate_terrain_detail_script()
        assert "GrassBillboard" in result

    def test_custom_detail_mesh(self):
        protos = [
            {
                "type": "detail_mesh",
                "prefab_path": "Assets/Prefabs/Rock_01.prefab",
                "min_height": 0.3,
                "max_height": 0.8,
                "min_width": 0.3,
                "max_width": 0.6,
                "color": [0.5, 0.5, 0.4],
            },
        ]
        result = generate_terrain_detail_script(detail_prototypes=protos)
        assert "VertexLit" in result
        assert "usePrototypeMesh" in result

    def test_custom_density(self):
        result = generate_terrain_detail_script(paint_density=12)
        assert "12" in result

    def test_contains_menu_item(self):
        result = generate_terrain_detail_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Paint Terrain Detail" in result


# ---------------------------------------------------------------------------
# TWO-01: Tilemap + Rule Tiles
# ---------------------------------------------------------------------------


class TestTilemapSetup:
    """Tests for generate_tilemap_setup_script()."""

    def test_returns_string(self):
        result = generate_tilemap_setup_script()
        assert isinstance(result, str)

    def test_contains_tilemap(self):
        result = generate_tilemap_setup_script()
        assert "Tilemap" in result

    def test_contains_set_tile(self):
        entries = [{"x": 0, "y": 0, "tile_asset_path": "Assets/Tiles/test.asset"}]
        result = generate_tilemap_setup_script(tile_entries=entries)
        assert "SetTile" in result

    def test_contains_vector3int(self):
        entries = [{"x": 1, "y": 2, "tile_asset_path": "Assets/Tiles/test.asset"}]
        result = generate_tilemap_setup_script(tile_entries=entries)
        assert "Vector3Int" in result

    def test_contains_grid(self):
        result = generate_tilemap_setup_script()
        assert "Grid" in result

    def test_rule_tile_creation(self):
        result = generate_tilemap_setup_script(rule_tile_name="ForestRuleTile")
        assert "RuleTile" in result

    def test_rule_tile_with_rules(self):
        rules = [{"output": "single"}, {"output": "random"}]
        result = generate_tilemap_setup_script(
            rule_tile_name="TestRuleTile",
            rule_tile_rules=rules,
        )
        assert "TilingRule" in result

    def test_custom_cell_size(self):
        result = generate_tilemap_setup_script(grid_cell_size=[2.0, 2.0, 0.0])
        assert "2" in result

    def test_contains_menu_item(self):
        result = generate_tilemap_setup_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Setup Tilemap" in result

    def test_contains_tilemap_renderer(self):
        result = generate_tilemap_setup_script()
        assert "TilemapRenderer" in result

    def test_no_rule_tile_when_name_empty(self):
        result = generate_tilemap_setup_script(rule_tile_name="")
        assert "RuleTile" not in result


# ---------------------------------------------------------------------------
# TWO-02: 2D Physics configuration
# ---------------------------------------------------------------------------


class TestPhysics2DSetup:
    """Tests for generate_2d_physics_script()."""

    def test_returns_string(self):
        result = generate_2d_physics_script()
        assert isinstance(result, str)

    def test_contains_rigidbody2d(self):
        result = generate_2d_physics_script()
        assert "Rigidbody2D" in result

    def test_contains_box_collider_by_default(self):
        result = generate_2d_physics_script()
        assert "BoxCollider2D" in result

    def test_circle_collider(self):
        result = generate_2d_physics_script(collider_type="circle")
        assert "CircleCollider2D" in result

    def test_composite_collider(self):
        result = generate_2d_physics_script(collider_type="composite")
        assert "CompositeCollider2D" in result

    def test_contains_physics2d_gravity(self):
        result = generate_2d_physics_script()
        assert "Physics2D.gravity" in result

    def test_custom_gravity(self):
        result = generate_2d_physics_script(gravity=[0.0, -15.0])
        assert "-15" in result

    def test_hinge_joint(self):
        result = generate_2d_physics_script(joint_type="hinge")
        assert "HingeJoint2D" in result

    def test_spring_joint(self):
        result = generate_2d_physics_script(joint_type="spring")
        assert "SpringJoint2D" in result

    def test_distance_joint(self):
        result = generate_2d_physics_script(joint_type="distance")
        assert "DistanceJoint2D" in result

    def test_kinematic_body_type(self):
        result = generate_2d_physics_script(body_type="Kinematic")
        assert "RigidbodyType2D.Kinematic" in result

    def test_static_body_type(self):
        result = generate_2d_physics_script(body_type="Static")
        assert "RigidbodyType2D.Static" in result

    def test_contains_menu_item(self):
        result = generate_2d_physics_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Setup 2D Physics" in result

    def test_hinge_with_motor(self):
        result = generate_2d_physics_script(
            joint_type="hinge",
            joint_params={"use_motor": True, "motor_speed": 200.0},
        )
        assert "useMotor" in result
        assert "200" in result


# ---------------------------------------------------------------------------
# WORLD-08: Time-of-day lighting presets
# ---------------------------------------------------------------------------


class TestTimeOfDayPresets:
    """Tests for generate_time_of_day_preset_script()."""

    def test_returns_string(self):
        result = generate_time_of_day_preset_script()
        assert isinstance(result, str)

    def test_dawn_preset(self):
        result = generate_time_of_day_preset_script(preset_name="dawn")
        assert "dawn" in result
        assert "RenderSettings" in result

    def test_morning_preset(self):
        result = generate_time_of_day_preset_script(preset_name="morning")
        assert "morning" in result

    def test_noon_preset(self):
        result = generate_time_of_day_preset_script(preset_name="noon")
        assert "noon" in result

    def test_afternoon_preset(self):
        result = generate_time_of_day_preset_script(preset_name="afternoon")
        assert "afternoon" in result

    def test_dusk_preset(self):
        result = generate_time_of_day_preset_script(preset_name="dusk")
        assert "dusk" in result

    def test_evening_preset(self):
        result = generate_time_of_day_preset_script(preset_name="evening")
        assert "evening" in result

    def test_night_preset(self):
        result = generate_time_of_day_preset_script(preset_name="night")
        assert "night" in result

    def test_midnight_preset(self):
        result = generate_time_of_day_preset_script(preset_name="midnight")
        assert "midnight" in result

    def test_all_presets_produce_valid_output(self):
        presets = ["dawn", "morning", "noon", "afternoon", "dusk", "evening", "night", "midnight"]
        for name in presets:
            result = generate_time_of_day_preset_script(preset_name=name)
            assert isinstance(result, str)
            assert len(result) > 100
            assert "RenderSettings" in result

    def test_contains_render_settings(self):
        result = generate_time_of_day_preset_script()
        assert "RenderSettings" in result

    def test_contains_directional_light(self):
        result = generate_time_of_day_preset_script()
        assert "Directional" in result

    def test_contains_sun_reference(self):
        result = generate_time_of_day_preset_script()
        assert "sun" in result.lower()

    def test_fog_enabled_by_default(self):
        result = generate_time_of_day_preset_script()
        assert "fogDensity" in result

    def test_fog_disabled(self):
        result = generate_time_of_day_preset_script(apply_fog=False)
        assert "RenderSettings.fog = false" in result

    def test_custom_overrides(self):
        result = generate_time_of_day_preset_script(
            preset_name="noon",
            custom_overrides={"sun_intensity": 2.0},
        )
        assert "2" in result

    def test_contains_menu_item(self):
        result = generate_time_of_day_preset_script()
        assert "MenuItem" in result
        assert "VeilBreakers/World/Apply Time of Day" in result

    def test_contains_skybox_tint(self):
        result = generate_time_of_day_preset_script()
        assert "_Tint" in result
