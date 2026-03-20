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
    generate_fast_travel_script,
    generate_puzzle_mechanics_script,
    generate_trap_system_script,
    generate_spatial_loot_script,
    generate_weather_system_script,
    generate_day_night_cycle_script,
    generate_npc_placement_script,
    generate_dungeon_lighting_script,
    generate_terrain_building_blend_script,
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


# ===========================================================================
# RPG World System Tests (RPG-02, 04, 06, 07, 09, 10, 11, 12, 13)
# ===========================================================================


# ---------------------------------------------------------------------------
# RPG-02: Fast travel
# ---------------------------------------------------------------------------


class TestFastTravel:
    """Tests for generate_fast_travel_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_fast_travel_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_fast_travel_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_waypoint_manager(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "WaypointManager" in runtime_cs

    def test_runtime_contains_on_trigger_enter(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "OnTriggerEnter" in runtime_cs

    def test_runtime_contains_discovered_waypoints(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "discoveredWaypoints" in runtime_cs

    def test_runtime_contains_teleport_to(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "TeleportTo" in runtime_cs

    def test_runtime_contains_json_utility(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "JsonUtility" in runtime_cs

    def test_runtime_contains_load_scene_async(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "LoadSceneAsync" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_fast_travel_script()
        assert "MenuItem" in editor_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_fast_travel_script()
        assert "using UnityEditor" not in runtime_cs

    def test_custom_save_key(self):
        _, runtime_cs = generate_fast_travel_script(save_key="myWaypoints")
        assert "myWaypoints" in runtime_cs

    def test_custom_fade_duration(self):
        _, runtime_cs = generate_fast_travel_script(teleport_fade_duration=1.0)
        assert "1.0" in runtime_cs

    def test_custom_namespace(self):
        _, runtime_cs = generate_fast_travel_script(namespace="MyGame.Travel")
        assert "namespace MyGame.Travel" in runtime_cs


# ---------------------------------------------------------------------------
# RPG-04: Puzzle mechanics
# ---------------------------------------------------------------------------


class TestPuzzleMechanics:
    """Tests for generate_puzzle_mechanics_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_puzzle_mechanics_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_puzzle_mechanics_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_puzzle_mechanic_base(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "PuzzleMechanic" in runtime_cs

    def test_runtime_contains_is_solved(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "IsSolved" in runtime_cs

    def test_runtime_contains_on_solved(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "OnSolved" in runtime_cs

    def test_runtime_contains_reset_puzzle(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "ResetPuzzle" in runtime_cs

    def test_runtime_contains_lever_sequence(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "LeverSequencePuzzle" in runtime_cs

    def test_runtime_contains_pressure_plate(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "PressurePlatePuzzle" in runtime_cs

    def test_runtime_contains_key_lock(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "KeyLockPuzzle" in runtime_cs

    def test_runtime_contains_light_beam(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "LightBeamPuzzle" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_puzzle_mechanics_script()
        assert "MenuItem" in editor_cs

    def test_custom_puzzle_types(self):
        _, runtime_cs = generate_puzzle_mechanics_script(puzzle_types=["lever_sequence", "key_lock"])
        assert "LeverSequencePuzzle" in runtime_cs
        assert "KeyLockPuzzle" in runtime_cs
        assert "PressurePlatePuzzle" not in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_puzzle_mechanics_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-06: Trap mechanics
# ---------------------------------------------------------------------------


class TestTrapMechanics:
    """Tests for generate_trap_system_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_trap_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_trap_system_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_trap_base(self):
        _, runtime_cs = generate_trap_system_script()
        assert "TrapBase" in runtime_cs

    def test_runtime_contains_activate(self):
        _, runtime_cs = generate_trap_system_script()
        assert "Activate" in runtime_cs

    def test_runtime_contains_pressure_plate_trap(self):
        _, runtime_cs = generate_trap_system_script()
        assert "PressurePlateTrap" in runtime_cs

    def test_runtime_contains_dart_wall_trap(self):
        _, runtime_cs = generate_trap_system_script()
        assert "DartWallTrap" in runtime_cs

    def test_runtime_contains_spike_pit_trap(self):
        _, runtime_cs = generate_trap_system_script()
        assert "SpikePitTrap" in runtime_cs

    def test_runtime_contains_poison_gas_trap(self):
        _, runtime_cs = generate_trap_system_script()
        assert "PoisonGasTrap" in runtime_cs

    def test_runtime_contains_swinging_blade_trap(self):
        _, runtime_cs = generate_trap_system_script()
        assert "SwingingBladeTrap" in runtime_cs

    def test_runtime_contains_damage_field(self):
        _, runtime_cs = generate_trap_system_script()
        assert "_damage" in runtime_cs

    def test_runtime_contains_cooldown_field(self):
        _, runtime_cs = generate_trap_system_script()
        assert "_cooldown" in runtime_cs

    def test_custom_damage(self):
        _, runtime_cs = generate_trap_system_script(base_damage=50.0)
        assert "50.0" in runtime_cs

    def test_custom_cooldown(self):
        _, runtime_cs = generate_trap_system_script(cooldown=5.0)
        assert "5.0" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_trap_system_script()
        assert "MenuItem" in editor_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_trap_system_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-07: Spatial loot
# ---------------------------------------------------------------------------


class TestSpatialLoot:
    """Tests for generate_spatial_loot_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_spatial_loot_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_spatial_loot_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_spatial_loot_manager(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "SpatialLootManager" in runtime_cs

    def test_runtime_contains_chest(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "chest" in runtime_cs.lower()

    def test_runtime_contains_loot(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "loot" in runtime_cs.lower()

    def test_runtime_contains_loot_table(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "RoomLootTable" in runtime_cs

    def test_runtime_contains_treasure_room(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "TreasureRoom" in runtime_cs or "Treasure" in runtime_cs

    def test_runtime_contains_scriptable_object(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "ScriptableObject" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_spatial_loot_script()
        assert "MenuItem" in editor_cs

    def test_custom_density(self):
        _, runtime_cs = generate_spatial_loot_script(room_loot_density=0.5)
        assert "0.5" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_spatial_loot_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-09: Weather system
# ---------------------------------------------------------------------------


class TestWeatherSystem:
    """Tests for generate_weather_system_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_weather_system_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_weather_system_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_weather_manager(self):
        _, runtime_cs = generate_weather_system_script()
        assert "WeatherManager" in runtime_cs

    def test_runtime_contains_weather_state_enum(self):
        _, runtime_cs = generate_weather_system_script()
        assert "WeatherState" in runtime_cs

    def test_runtime_contains_clear_state(self):
        _, runtime_cs = generate_weather_system_script()
        assert "Clear" in runtime_cs

    def test_runtime_contains_rain_state(self):
        _, runtime_cs = generate_weather_system_script()
        assert "Rain" in runtime_cs

    def test_runtime_contains_snow_state(self):
        _, runtime_cs = generate_weather_system_script()
        assert "Snow" in runtime_cs

    def test_runtime_contains_fog_state(self):
        _, runtime_cs = generate_weather_system_script()
        assert "Fog" in runtime_cs

    def test_runtime_contains_storm_state(self):
        _, runtime_cs = generate_weather_system_script()
        assert "Storm" in runtime_cs

    def test_runtime_contains_transition_to(self):
        _, runtime_cs = generate_weather_system_script()
        assert "TransitionTo" in runtime_cs

    def test_runtime_contains_ienumerator(self):
        _, runtime_cs = generate_weather_system_script()
        assert "IEnumerator" in runtime_cs

    def test_runtime_contains_particle_system(self):
        _, runtime_cs = generate_weather_system_script()
        assert "ParticleSystem" in runtime_cs

    def test_runtime_contains_emission(self):
        _, runtime_cs = generate_weather_system_script()
        assert "emission" in runtime_cs

    def test_runtime_contains_render_settings(self):
        _, runtime_cs = generate_weather_system_script()
        assert "RenderSettings" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_weather_system_script()
        assert "MenuItem" in editor_cs

    def test_custom_transition_duration(self):
        _, runtime_cs = generate_weather_system_script(transition_duration=5.0)
        assert "5.0" in runtime_cs

    def test_custom_states(self):
        _, runtime_cs = generate_weather_system_script(weather_states=["Clear", "Sandstorm"])
        assert "Sandstorm" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_weather_system_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-10: Day/night cycle
# ---------------------------------------------------------------------------


class TestDayNightCycle:
    """Tests for generate_day_night_cycle_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_day_night_cycle_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_day_night_cycle_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_day_night_cycle_manager(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "DayNightCycleManager" in runtime_cs

    def test_runtime_contains_time_of_day(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "_timeOfDay" in runtime_cs

    def test_runtime_contains_on_time_changed(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "OnTimeChanged" in runtime_cs

    def test_runtime_contains_on_nightfall(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "OnNightfall" in runtime_cs

    def test_runtime_contains_on_daybreak(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "OnDaybreak" in runtime_cs

    def test_runtime_contains_render_settings(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "RenderSettings" in runtime_cs

    def test_runtime_contains_ambient_light(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "ambientLight" in runtime_cs

    def test_runtime_contains_8_presets(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "Dawn" in runtime_cs
        assert "Morning" in runtime_cs
        assert "Noon" in runtime_cs
        assert "Afternoon" in runtime_cs
        assert "Dusk" in runtime_cs
        assert "Evening" in runtime_cs
        assert "Night" in runtime_cs
        assert "Midnight" in runtime_cs

    def test_runtime_contains_set_time(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "SetTime" in runtime_cs

    def test_runtime_contains_pause_time(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "PauseTime" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_day_night_cycle_script()
        assert "MenuItem" in editor_cs

    def test_custom_day_duration(self):
        _, runtime_cs = generate_day_night_cycle_script(day_duration_minutes=20.0)
        assert "20.0" in runtime_cs

    def test_custom_start_hour(self):
        _, runtime_cs = generate_day_night_cycle_script(start_hour=12.0)
        assert "12.0" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_day_night_cycle_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-11: NPC placement
# ---------------------------------------------------------------------------


class TestNPCPlacement:
    """Tests for generate_npc_placement_script()."""

    def test_returns_tuple_of_three(self):
        result = generate_npc_placement_script()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_all_parts_non_empty(self):
        so_cs, runtime_cs, editor_cs = generate_npc_placement_script()
        assert len(so_cs) > 100
        assert len(runtime_cs) > 100
        assert len(editor_cs) > 100

    def test_so_contains_npc_placement_data(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "NPCPlacementData" in so_cs

    def test_so_contains_scriptable_object(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "ScriptableObject" in so_cs

    def test_so_contains_create_asset_menu(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "CreateAssetMenu" in so_cs

    def test_so_contains_npc_slot(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "NPCSlot" in so_cs

    def test_so_contains_npc_role_enum(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "NPCRole" in so_cs

    def test_runtime_contains_npc_placement_manager(self):
        _, runtime_cs, _ = generate_npc_placement_script()
        assert "NPCPlacementManager" in runtime_cs

    def test_runtime_contains_instantiate(self):
        _, runtime_cs, _ = generate_npc_placement_script()
        assert "Instantiate" in runtime_cs

    def test_runtime_contains_spawn_npcs(self):
        _, runtime_cs, _ = generate_npc_placement_script()
        assert "SpawnNPCs" in runtime_cs

    def test_editor_contains_menu_item(self):
        _, _, editor_cs = generate_npc_placement_script()
        assert "MenuItem" in editor_cs

    def test_custom_roles(self):
        so_cs, _, _ = generate_npc_placement_script(npc_roles=["merchant", "healer"])
        assert "Merchant" in so_cs
        assert "Healer" in so_cs

    def test_default_roles(self):
        so_cs, _, _ = generate_npc_placement_script()
        assert "Shopkeeper" in so_cs
        assert "Guard" in so_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs, _ = generate_npc_placement_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-12: Dungeon lighting
# ---------------------------------------------------------------------------


class TestDungeonLighting:
    """Tests for generate_dungeon_lighting_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_dungeon_lighting_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_dungeon_lighting_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_dungeon_lighting_setup(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "DungeonLightingSetup" in runtime_cs

    def test_runtime_contains_torch_reference(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "torch" in runtime_cs.lower() or "sconce" in runtime_cs.lower()

    def test_runtime_contains_point_light(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "LightType.Point" in runtime_cs

    def test_runtime_contains_fog(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "fog" in runtime_cs.lower()

    def test_runtime_contains_torch_spacing(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "_torchSpacing" in runtime_cs

    def test_runtime_contains_torch_color(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "_torchColor" in runtime_cs

    def test_runtime_contains_render_settings_fog(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "RenderSettings.fog" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_dungeon_lighting_script()
        assert "MenuItem" in editor_cs

    def test_custom_torch_spacing(self):
        _, runtime_cs = generate_dungeon_lighting_script(torch_spacing=6.0)
        assert "6.0" in runtime_cs

    def test_custom_torch_range(self):
        _, runtime_cs = generate_dungeon_lighting_script(torch_light_range=12.0)
        assert "12.0" in runtime_cs

    def test_custom_fog_density(self):
        _, runtime_cs = generate_dungeon_lighting_script(fog_density=0.05)
        assert "0.05" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_dungeon_lighting_script()
        assert "using UnityEditor" not in runtime_cs


# ---------------------------------------------------------------------------
# RPG-13: Terrain-building blend
# ---------------------------------------------------------------------------


class TestTerrainBlend:
    """Tests for generate_terrain_building_blend_script()."""

    def test_returns_tuple_of_two(self):
        result = generate_terrain_building_blend_script()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_both_parts_non_empty(self):
        editor_cs, runtime_cs = generate_terrain_building_blend_script()
        assert len(editor_cs) > 100
        assert len(runtime_cs) > 100

    def test_runtime_contains_terrain_building_blend(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "TerrainBuildingBlend" in runtime_cs

    def test_runtime_contains_decal_projector(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "DecalProjector" in runtime_cs

    def test_runtime_contains_set_heights(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "SetHeights" in runtime_cs

    def test_runtime_contains_terrain_data(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "terrainData" in runtime_cs or "TerrainData" in runtime_cs

    def test_runtime_contains_vertex_color(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "colors" in runtime_cs or "Color" in runtime_cs

    def test_runtime_contains_mesh_filter(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "MeshFilter" in runtime_cs

    def test_runtime_contains_blend_radius(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "_blendRadius" in runtime_cs

    def test_editor_contains_menu_item(self):
        editor_cs, _ = generate_terrain_building_blend_script()
        assert "MenuItem" in editor_cs

    def test_custom_blend_radius(self):
        _, runtime_cs = generate_terrain_building_blend_script(blend_radius=5.0)
        assert "5.0" in runtime_cs

    def test_custom_depression_depth(self):
        _, runtime_cs = generate_terrain_building_blend_script(depression_depth=0.2)
        assert "0.2" in runtime_cs

    def test_custom_falloff(self):
        _, runtime_cs = generate_terrain_building_blend_script(vertex_color_falloff=2.0)
        assert "2.0" in runtime_cs

    def test_runtime_no_editor_namespace(self):
        _, runtime_cs = generate_terrain_building_blend_script()
        assert "using UnityEditor" not in runtime_cs
