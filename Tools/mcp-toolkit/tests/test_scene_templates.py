"""Unit tests for Unity scene C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_tiled_terrain_setup_script,
    generate_object_scatter_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_animation_rigging_script,
)


# ---------------------------------------------------------------------------
# Terrain setup script (SCENE-01)
# ---------------------------------------------------------------------------


class TestGenerateTerrainSetupScript:
    """Tests for generate_terrain_setup_script()."""

    def test_contains_using_statements(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_terrain_data(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "TerrainData" in result

    def test_contains_set_heights(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "SetHeights" in result

    def test_contains_create_terrain_game_object(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "Terrain.CreateTerrainGameObject" in result

    def test_contains_heightmap_resolution(self):
        result = generate_terrain_setup_script(
            "Assets/Terrain/heightmap.raw", resolution=1025
        )
        assert "1025" in result

    def test_contains_terrain_size(self):
        result = generate_terrain_setup_script(
            "Assets/Terrain/heightmap.raw", size=(2000, 800, 2000)
        )
        assert "2000" in result
        assert "800" in result

    def test_contains_heightmap_path(self):
        result = generate_terrain_setup_script("Assets/Terrain/my_heightmap.raw")
        assert "my_heightmap.raw" in result

    def test_splatmap_layers(self):
        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
        ]
        result = generate_terrain_setup_script(
            "Assets/Terrain/heightmap.raw", splatmap_layers=layers
        )
        assert "SetAlphamaps" in result
        assert "grass.png" in result
        assert "rock.png" in result

    def test_alphamap_path_is_supported(self):
        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
            {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
            {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
        ]
        result = generate_terrain_setup_script(
            "Assets/Terrain/heightmap.raw",
            splatmap_layers=layers,
            alphamap_path="Assets/Terrain/tile_0_alphamap.raw",
        )
        assert "tile_0_alphamap.raw" in result
        assert "File.Exists(alphamapPath)" in result

    def test_contains_menu_item(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "vb_result.json" in result

    def test_default_resolution(self):
        result = generate_terrain_setup_script("Assets/Terrain/heightmap.raw")
        assert "513" in result


class TestGenerateTiledTerrainSetupScript:
    """Tests for generate_tiled_terrain_setup_script()."""

    def test_rejects_empty_tiles(self):
        with pytest.raises(ValueError, match="tiles"):
            generate_tiled_terrain_setup_script([])

    def test_contains_tiled_menu_item(self):
        result = generate_tiled_terrain_setup_script(
            [{"heightmap_path": "Assets/Terrain/tile_0.raw", "grid_x": 0, "grid_y": 0}]
        )
        assert "Setup Tiled Terrain" in result
        assert "VeilBreakers_TiledTerrainSetup" in result

    def test_contains_tile_heightmap_paths(self):
        result = generate_tiled_terrain_setup_script(
            [
                {"heightmap_path": "Assets/Terrain/tile_0.raw", "name": "Tile_0", "grid_x": 0, "grid_y": 0},
                {"heightmap_path": "Assets/Terrain/tile_1.raw", "name": "Tile_1", "grid_x": 1, "grid_y": 0},
            ]
        )
        assert "tile_0.raw" in result
        assert "tile_1.raw" in result
        assert "Tile_0" in result
        assert "Tile_1" in result
        assert "SetNeighbors" in result

    def test_uses_terrain_component_for_neighbor_map(self):
        result = generate_tiled_terrain_setup_script(
            [{"heightmap_path": "Assets/Terrain/tile_0.raw", "grid_x": 0, "grid_y": 0}]
        )
        assert "new Dictionary<string, Terrain>()" in result
        assert ".GetComponent<Terrain>()" in result

    def test_contains_tiled_parent_and_positions(self):
        result = generate_tiled_terrain_setup_script(
            [
                {
                    "heightmap_path": "Assets/Terrain/tile_0.raw",
                    "grid_x": 0,
                    "grid_y": 0,
                    "position": [128.0, 0.0, 256.0],
                }
            ],
            parent_name="VB_TerrainRoot",
        )
        assert "VB_TerrainRoot" in result
        assert "128.0f" in result or "128f" in result
        assert "256.0f" in result or "256f" in result

    def test_contains_tiled_alphamap_paths(self):
        layers = [
            {"texture_path": "Assets/Textures/grass.png", "tiling": 10.0},
            {"texture_path": "Assets/Textures/rock.png", "tiling": 5.0},
            {"texture_path": "Assets/Textures/dirt.png", "tiling": 8.0},
            {"texture_path": "Assets/Textures/snow.png", "tiling": 12.0},
        ]
        result = generate_tiled_terrain_setup_script(
            [
                {
                    "heightmap_path": "Assets/Terrain/tile_0.raw",
                    "alphamap_path": "Assets/Terrain/tile_0_alphamap.raw",
                    "grid_x": 0,
                    "grid_y": 0,
                }
            ],
            splatmap_layers=layers,
        )
        assert "tile_0_alphamap.raw" in result
        assert "SetAlphamaps" in result


# ---------------------------------------------------------------------------
# Object scatter script (SCENE-02)
# ---------------------------------------------------------------------------


class TestGenerateObjectScatterScript:
    """Tests for generate_object_scatter_script()."""

    def test_contains_using_statements(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_prefab_utility(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "PrefabUtility" in result

    def test_contains_sample_height(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "SampleHeight" in result

    def test_contains_interpolated_normal(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "GetInterpolatedNormal" in result

    def test_contains_density(self):
        result = generate_object_scatter_script(
            ["Assets/Prefabs/tree.prefab"], density=0.8
        )
        assert "0.8" in result

    def test_contains_slope_filter(self):
        result = generate_object_scatter_script(
            ["Assets/Prefabs/tree.prefab"], min_slope=5.0, max_slope=30.0
        )
        assert "30" in result

    def test_contains_altitude_filter(self):
        result = generate_object_scatter_script(
            ["Assets/Prefabs/tree.prefab"], min_altitude=50.0, max_altitude=500.0
        )
        assert "500" in result

    def test_contains_seed(self):
        result = generate_object_scatter_script(
            ["Assets/Prefabs/tree.prefab"], seed=123
        )
        assert "123" in result

    def test_contains_prefab_paths(self):
        result = generate_object_scatter_script(
            ["Assets/Prefabs/tree.prefab", "Assets/Prefabs/rock.prefab"]
        )
        assert "tree.prefab" in result
        assert "rock.prefab" in result

    def test_contains_parent_game_object(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "GameObject" in result

    def test_contains_menu_item(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_object_scatter_script(["Assets/Prefabs/tree.prefab"])
        assert "vb_result.json" in result

    def test_raises_on_empty_prefab_paths(self):
        with pytest.raises(ValueError, match="prefab_paths"):
            generate_object_scatter_script([])


# ---------------------------------------------------------------------------
# Lighting setup script (SCENE-03)
# ---------------------------------------------------------------------------


class TestGenerateLightingSetupScript:
    """Tests for generate_lighting_setup_script()."""

    def test_contains_using_statements(self):
        result = generate_lighting_setup_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_render_settings(self):
        result = generate_lighting_setup_script()
        assert "RenderSettings" in result

    def test_contains_directional_light(self):
        result = generate_lighting_setup_script()
        assert "LightType.Directional" in result

    def test_contains_fog_settings(self):
        result = generate_lighting_setup_script(fog_enabled=True, fog_density=0.05)
        assert "fog" in result.lower()
        assert "0.05" in result

    def test_contains_volume_post_processing(self):
        result = generate_lighting_setup_script()
        assert "Volume" in result

    def test_contains_bloom(self):
        result = generate_lighting_setup_script()
        assert "Bloom" in result

    def test_contains_vignette(self):
        result = generate_lighting_setup_script()
        assert "Vignette" in result

    def test_contains_color_grading(self):
        result = generate_lighting_setup_script()
        assert "ColorAdjustments" in result or "ColorGrading" in result

    def test_sun_intensity(self):
        result = generate_lighting_setup_script(sun_intensity=2.5)
        assert "2.5" in result

    def test_time_of_day_noon(self):
        result = generate_lighting_setup_script(time_of_day="noon")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_time_of_day_dawn(self):
        result = generate_lighting_setup_script(time_of_day="dawn")
        assert isinstance(result, str)

    def test_time_of_day_dusk(self):
        result = generate_lighting_setup_script(time_of_day="dusk")
        assert isinstance(result, str)

    def test_time_of_day_night(self):
        result = generate_lighting_setup_script(time_of_day="night")
        assert isinstance(result, str)

    def test_time_of_day_overcast(self):
        result = generate_lighting_setup_script(time_of_day="overcast")
        assert isinstance(result, str)

    def test_skybox_material(self):
        result = generate_lighting_setup_script(skybox_material="Assets/Materials/Sky.mat")
        assert "Sky.mat" in result

    def test_contains_menu_item(self):
        result = generate_lighting_setup_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_lighting_setup_script()
        assert "vb_result.json" in result

    def test_custom_ambient_color(self):
        result = generate_lighting_setup_script(ambient_color=[0.1, 0.2, 0.3])
        assert "0.1" in result
        assert "0.2" in result
        assert "0.3" in result


# ---------------------------------------------------------------------------
# NavMesh bake script (SCENE-04)
# ---------------------------------------------------------------------------


class TestGenerateNavmeshBakeScript:
    """Tests for generate_navmesh_bake_script()."""

    def test_contains_using_statements(self):
        result = generate_navmesh_bake_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_navmesh_surface(self):
        result = generate_navmesh_bake_script()
        assert "NavMeshSurface" in result

    def test_contains_build_navmesh(self):
        result = generate_navmesh_bake_script()
        assert "BuildNavMesh" in result

    def test_contains_agent_radius(self):
        result = generate_navmesh_bake_script(agent_radius=0.75)
        assert "0.75" in result

    def test_contains_agent_height(self):
        result = generate_navmesh_bake_script(agent_height=1.8)
        assert "1.8" in result

    def test_contains_max_slope(self):
        result = generate_navmesh_bake_script(max_slope=35.0)
        assert "35" in result

    def test_contains_step_height(self):
        result = generate_navmesh_bake_script(step_height=0.6)
        assert "0.6" in result

    def test_nav_links(self):
        links = [
            {"start": [0, 0, 0], "end": [5, 2, 0], "width": 1.0},
        ]
        result = generate_navmesh_bake_script(nav_links=links)
        assert "NavMeshLink" in result

    def test_contains_menu_item(self):
        result = generate_navmesh_bake_script()
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_navmesh_bake_script()
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Animator controller script (SCENE-05)
# ---------------------------------------------------------------------------


class TestGenerateAnimatorControllerScript:
    """Tests for generate_animator_controller_script()."""

    def test_contains_using_statements(self):
        result = generate_animator_controller_script(
            name="PlayerLocomotion",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
        )
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_animator_controller(self):
        result = generate_animator_controller_script(
            name="PlayerLocomotion",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
        )
        assert "AnimatorController" in result

    def test_contains_create_at_path(self):
        result = generate_animator_controller_script(
            name="PlayerLocomotion",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
        )
        assert "CreateAnimatorControllerAtPath" in result

    def test_contains_state_names(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}, {"name": "Run"}],
            transitions=[],
            parameters=[],
        )
        assert "Idle" in result
        assert "Run" in result

    def test_contains_add_state(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[],
        )
        assert "AddState" in result

    def test_contains_transition(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}, {"name": "Run"}],
            transitions=[{
                "from_state": "Idle",
                "to_state": "Run",
                "conditions": [{"param": "Speed", "mode": "Greater", "threshold": 0.1}],
                "has_exit_time": False,
            }],
            parameters=[{"name": "Speed", "type": "float"}],
        )
        assert "AddTransition" in result
        assert "AddCondition" in result

    def test_contains_parameters(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[
                {"name": "Speed", "type": "float"},
                {"name": "IsGrounded", "type": "bool"},
            ],
        )
        assert "AddParameter" in result
        assert "Speed" in result
        assert "IsGrounded" in result

    def test_blend_trees(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
            blend_trees=[{
                "name": "Locomotion",
                "blend_param": "Speed",
                "children": [
                    {"motion_path": "Assets/Animations/Idle.anim", "threshold": 0.0},
                    {"motion_path": "Assets/Animations/Walk.anim", "threshold": 0.5},
                    {"motion_path": "Assets/Animations/Run.anim", "threshold": 1.0},
                ],
            }],
        )
        assert "BlendTree" in result
        assert "Locomotion" in result

    def test_contains_controller_path(self):
        result = generate_animator_controller_script(
            name="PlayerLocomotion",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[],
        )
        assert "PlayerLocomotion" in result

    def test_contains_menu_item(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[],
        )
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_animator_controller_script(
            name="Test",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[],
        )
        assert "vb_result.json" in result

    def test_raises_on_empty_states(self):
        with pytest.raises(ValueError, match="states"):
            generate_animator_controller_script(
                name="Test",
                states=[],
                transitions=[],
                parameters=[],
            )


# ---------------------------------------------------------------------------
# Avatar configuration script (SCENE-06)
# ---------------------------------------------------------------------------


class TestGenerateAvatarConfigScript:
    """Tests for generate_avatar_config_script()."""

    def test_contains_using_statements(self):
        result = generate_avatar_config_script("Assets/Models/character.fbx")
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_model_importer(self):
        result = generate_avatar_config_script("Assets/Models/character.fbx")
        assert "ModelImporter" in result

    def test_contains_animation_type_humanoid(self):
        result = generate_avatar_config_script(
            "Assets/Models/character.fbx", animation_type="Humanoid"
        )
        assert "Humanoid" in result or "Human" in result

    def test_contains_animation_type_generic(self):
        result = generate_avatar_config_script(
            "Assets/Models/character.fbx", animation_type="Generic"
        )
        assert "Generic" in result

    def test_contains_save_and_reimport(self):
        result = generate_avatar_config_script("Assets/Models/character.fbx")
        assert "SaveAndReimport" in result

    def test_contains_fbx_path(self):
        result = generate_avatar_config_script("Assets/Models/my_character.fbx")
        assert "my_character.fbx" in result

    def test_bone_mapping(self):
        mapping = {
            "Hips": "mixamorig:Hips",
            "Spine": "mixamorig:Spine",
            "Head": "mixamorig:Head",
        }
        result = generate_avatar_config_script(
            "Assets/Models/character.fbx",
            animation_type="Humanoid",
            bone_mapping=mapping,
        )
        assert "HumanDescription" in result or "humanDescription" in result
        assert "mixamorig:Hips" in result

    def test_contains_menu_item(self):
        result = generate_avatar_config_script("Assets/Models/character.fbx")
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_avatar_config_script("Assets/Models/character.fbx")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Animation rigging script (SCENE-07)
# ---------------------------------------------------------------------------


class TestGenerateAnimationRiggingScript:
    """Tests for generate_animation_rigging_script()."""

    def test_contains_using_statements(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_animation_rigging_namespace(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "UnityEngine.Animations.Rigging" in result

    def test_contains_two_bone_ik_constraint(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "TwoBoneIKConstraint" in result

    def test_contains_multi_aim_constraint(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "multi_aim",
                "target_path": "Head",
                "source_paths": ["LookTarget"],
                "weight": 1.0,
            }],
        )
        assert "MultiAimConstraint" in result

    def test_contains_rig_builder(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "RigBuilder" in result

    def test_contains_rig_component(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "Rig" in result

    def test_contains_constraint_paths(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "RightUpperArm" in result
        assert "RightForearm" in result
        assert "RightHand" in result

    def test_contains_weighted_transform(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "multi_aim",
                "target_path": "Head",
                "source_paths": ["LookTarget"],
                "weight": 1.0,
            }],
        )
        assert "WeightedTransform" in result

    def test_multiple_constraints(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[
                {
                    "type": "two_bone_ik",
                    "target_path": "IKTarget_RightHand",
                    "root_path": "RightUpperArm",
                    "mid_path": "RightForearm",
                    "tip_path": "RightHand",
                },
                {
                    "type": "multi_aim",
                    "target_path": "Head",
                    "source_paths": ["LookTarget"],
                    "weight": 1.0,
                },
            ],
        )
        assert "TwoBoneIKConstraint" in result
        assert "MultiAimConstraint" in result

    def test_contains_menu_item(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert '[MenuItem("VeilBreakers/' in result

    def test_contains_result_json(self):
        result = generate_animation_rigging_script(
            rig_name="PlayerRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget_RightHand",
                "root_path": "RightUpperArm",
                "mid_path": "RightForearm",
                "tip_path": "RightHand",
            }],
        )
        assert "vb_result.json" in result

    def test_raises_on_empty_constraints(self):
        with pytest.raises(ValueError, match="constraints"):
            generate_animation_rigging_script(
                rig_name="PlayerRig",
                constraints=[],
            )

    def test_rig_name_in_output(self):
        result = generate_animation_rigging_script(
            rig_name="EnemyRig",
            constraints=[{
                "type": "two_bone_ik",
                "target_path": "IKTarget",
                "root_path": "UpperArm",
                "mid_path": "Forearm",
                "tip_path": "Hand",
            }],
        )
        assert "EnemyRig" in result
