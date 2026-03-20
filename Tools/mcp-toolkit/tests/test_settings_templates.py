"""Unit tests for Unity project settings C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, API calls, and parameter substitutions.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.settings_templates import (
    generate_physics_settings_script,
    generate_physics_material_script,
    generate_player_settings_script,
    generate_build_settings_script,
    generate_quality_settings_script,
    generate_package_install_script,
    generate_package_remove_script,
    generate_tag_layer_script,
    generate_tag_layer_sync_script,
    generate_time_settings_script,
    generate_graphics_settings_script,
)


# ---------------------------------------------------------------------------
# Physics settings script
# ---------------------------------------------------------------------------


class TestGeneratePhysicsSettingsScript:
    """Tests for generate_physics_settings_script()."""

    def test_contains_ignore_layer_collision(self):
        result = generate_physics_settings_script(
            collision_matrix={"Player": ["Enemy", "Projectile"], "Enemy": ["Player"]}
        )
        assert "Physics.IgnoreLayerCollision" in result

    def test_contains_layer_mask_name_to_layer(self):
        result = generate_physics_settings_script(
            collision_matrix={"Player": ["Enemy"]}
        )
        assert "LayerMask.NameToLayer" in result

    def test_contains_vb_result_json(self):
        result = generate_physics_settings_script(
            collision_matrix={"Player": ["Enemy"]}
        )
        assert "vb_result.json" in result

    def test_contains_undo(self):
        result = generate_physics_settings_script(
            collision_matrix={"Player": ["Enemy"]}
        )
        assert "Undo" in result

    def test_contains_menu_item(self):
        result = generate_physics_settings_script()
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_using_unity_editor(self):
        result = generate_physics_settings_script()
        assert "using UnityEditor;" in result

    def test_gravity_parameter(self):
        result = generate_physics_settings_script(gravity=[0, -15.0, 0])
        assert "Physics.gravity" in result
        assert "-15" in result

    def test_empty_collision_matrix(self):
        result = generate_physics_settings_script()
        assert "using UnityEditor;" in result
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Physics material script
# ---------------------------------------------------------------------------


class TestGeneratePhysicsMaterialScript:
    """Tests for generate_physics_material_script()."""

    def test_contains_physic_material(self):
        result = generate_physics_material_script("Bouncy", friction=0.2, bounciness=0.8)
        assert "PhysicMaterial" in result

    def test_contains_asset_database_create(self):
        result = generate_physics_material_script("Bouncy")
        assert "AssetDatabase.CreateAsset" in result

    def test_contains_bounciness(self):
        result = generate_physics_material_script("Bouncy", bounciness=0.8)
        assert ".bounciness" in result or "bounciness" in result

    def test_contains_dynamic_friction(self):
        result = generate_physics_material_script("Bouncy", friction=0.2)
        assert ".dynamicFriction" in result or "dynamicFriction" in result

    def test_friction_combine_maximum(self):
        result = generate_physics_material_script(
            "Bouncy", friction=0.2, bounciness=0.8, friction_combine="Maximum"
        )
        assert "Maximum" in result

    def test_contains_menu_item(self):
        result = generate_physics_material_script("Test")
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_physics_material_script("Test")
        assert "vb_result.json" in result

    def test_material_name_in_output(self):
        result = generate_physics_material_script("StickyFloor")
        assert "StickyFloor" in result


# ---------------------------------------------------------------------------
# Player settings script
# ---------------------------------------------------------------------------


class TestGeneratePlayerSettingsScript:
    """Tests for generate_player_settings_script()."""

    def test_contains_company_name(self):
        result = generate_player_settings_script(company="VeilBreakers")
        assert "PlayerSettings.companyName" in result
        assert "VeilBreakers" in result

    def test_contains_color_space(self):
        result = generate_player_settings_script(color_space="Linear")
        assert "PlayerSettings.colorSpace" in result
        assert "ColorSpace" in result

    def test_contains_scripting_backend(self):
        result = generate_player_settings_script(scripting_backend="IL2CPP")
        assert "SetScriptingBackend" in result
        assert "IL2CPP" in result

    def test_contains_api_level(self):
        result = generate_player_settings_script(api_level="NET_Standard")
        assert "SetApiCompatibilityLevel" in result

    def test_icon_path(self):
        result = generate_player_settings_script(icon_path="Assets/Icons/icon.png")
        assert "AssetDatabase.LoadAssetAtPath" in result
        assert "Texture2D" in result

    def test_splash_path(self):
        result = generate_player_settings_script(splash_path="Assets/Splash/logo.png")
        assert "SplashScreen" in result

    def test_contains_menu_item(self):
        result = generate_player_settings_script(company="Test")
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_player_settings_script(company="Test")
        assert "vb_result.json" in result

    def test_contains_using_unity_editor(self):
        result = generate_player_settings_script(company="Test")
        assert "using UnityEditor;" in result

    def test_skips_empty_parameters(self):
        result = generate_player_settings_script()
        # With all defaults (empty), should still produce valid C#
        assert "using UnityEditor;" in result


# ---------------------------------------------------------------------------
# Build settings script
# ---------------------------------------------------------------------------


class TestGenerateBuildSettingsScript:
    """Tests for generate_build_settings_script()."""

    def test_contains_editor_build_settings(self):
        result = generate_build_settings_script(
            scenes=["Assets/Scenes/Main.unity", "Assets/Scenes/Level1.unity"]
        )
        assert "EditorBuildSettings.scenes" in result

    def test_contains_editor_build_settings_scene(self):
        result = generate_build_settings_script(
            scenes=["Assets/Scenes/Main.unity"]
        )
        assert "EditorBuildSettingsScene" in result

    def test_contains_platform_switch(self):
        result = generate_build_settings_script(platform="StandaloneWindows64")
        assert "EditorUserBuildSettings" in result

    def test_contains_scripting_defines(self):
        result = generate_build_settings_script(defines=["ENABLE_DEBUG"])
        assert "SetScriptingDefineSymbolsForGroup" in result
        assert "ENABLE_DEBUG" in result

    def test_contains_menu_item(self):
        result = generate_build_settings_script()
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_build_settings_script()
        assert "vb_result.json" in result

    def test_scene_paths_in_output(self):
        result = generate_build_settings_script(
            scenes=["Assets/Scenes/Main.unity", "Assets/Scenes/Level1.unity"]
        )
        assert "Assets/Scenes/Main.unity" in result
        assert "Assets/Scenes/Level1.unity" in result


# ---------------------------------------------------------------------------
# Quality settings script
# ---------------------------------------------------------------------------


class TestGenerateQualitySettingsScript:
    """Tests for generate_quality_settings_script()."""

    def test_contains_quality_settings(self):
        levels = [
            {"name": "Low", "shadow_distance": 20, "texture_quality": 2,
             "anti_aliasing": 0, "vsync": 0, "lod_bias": 0.5},
            {"name": "High", "shadow_distance": 150, "texture_quality": 0,
             "anti_aliasing": 4, "vsync": 1, "lod_bias": 1.0},
        ]
        result = generate_quality_settings_script(levels=levels)
        assert "QualitySettings" in result

    def test_contains_shadow_distance(self):
        levels = [
            {"name": "Low", "shadow_distance": 20, "texture_quality": 2,
             "anti_aliasing": 0, "vsync": 0, "lod_bias": 0.5}
        ]
        result = generate_quality_settings_script(levels=levels)
        assert "20" in result

    def test_contains_serialized_object(self):
        levels = [{"name": "Low", "shadow_distance": 20}]
        result = generate_quality_settings_script(levels=levels)
        assert "SerializedObject" in result or "QualitySettings" in result

    def test_contains_menu_item(self):
        levels = [{"name": "Low", "shadow_distance": 20}]
        result = generate_quality_settings_script(levels=levels)
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        levels = [{"name": "Low", "shadow_distance": 20}]
        result = generate_quality_settings_script(levels=levels)
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Package install script
# ---------------------------------------------------------------------------


class TestGeneratePackageInstallScript:
    """Tests for generate_package_install_script()."""

    def test_upm_source_contains_client_add(self):
        result = generate_package_install_script(
            "com.unity.cinemachine", version="3.1.0", source="upm"
        )
        assert "Client.Add" in result

    def test_upm_source_contains_package_id_and_version(self):
        result = generate_package_install_script(
            "com.unity.cinemachine", version="3.1.0", source="upm"
        )
        assert "com.unity.cinemachine" in result
        assert "3.1.0" in result

    def test_openupm_source_edits_manifest(self):
        result = generate_package_install_script(
            "com.some.package", source="openupm",
            registry_url="https://package.openupm.com"
        )
        assert "manifest.json" in result
        assert "scopedRegistries" in result

    def test_git_source_contains_client_add_with_url(self):
        result = generate_package_install_script(
            "https://github.com/user/repo.git#v1.0", source="git"
        )
        assert "Client.Add" in result
        assert "https://github.com/user/repo.git#v1.0" in result

    def test_contains_menu_item(self):
        result = generate_package_install_script("com.unity.cinemachine")
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_package_install_script("com.unity.cinemachine")
        assert "vb_result.json" in result

    def test_contains_using_unity_editor(self):
        result = generate_package_install_script("com.unity.cinemachine")
        assert "using UnityEditor;" in result


# ---------------------------------------------------------------------------
# Package remove script
# ---------------------------------------------------------------------------


class TestGeneratePackageRemoveScript:
    """Tests for generate_package_remove_script()."""

    def test_contains_client_remove(self):
        result = generate_package_remove_script("com.unity.cinemachine")
        assert "Client.Remove" in result

    def test_contains_package_id(self):
        result = generate_package_remove_script("com.unity.cinemachine")
        assert "com.unity.cinemachine" in result

    def test_contains_menu_item(self):
        result = generate_package_remove_script("com.unity.cinemachine")
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_package_remove_script("com.unity.cinemachine")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Tag/layer management script
# ---------------------------------------------------------------------------


class TestGenerateTagLayerScript:
    """Tests for generate_tag_layer_script()."""

    def test_contains_serialized_object_on_tag_manager(self):
        result = generate_tag_layer_script(
            tags=["Monster", "Pickup"],
            layers=["Projectile"],
            sorting_layers=["Background"],
        )
        assert "SerializedObject" in result
        assert "TagManager" in result

    def test_contains_find_property_tags(self):
        result = generate_tag_layer_script(tags=["Monster"])
        assert 'FindProperty("tags")' in result or "FindProperty" in result

    def test_contains_find_property_layers(self):
        result = generate_tag_layer_script(layers=["Projectile"])
        assert 'FindProperty("layers")' in result or "FindProperty" in result

    def test_contains_find_property_sorting_layers(self):
        result = generate_tag_layer_script(sorting_layers=["Background", "Foreground"])
        assert "m_SortingLayers" in result or "SortingLayer" in result

    def test_tag_names_in_output(self):
        result = generate_tag_layer_script(
            tags=["Monster", "Pickup", "Hazard"]
        )
        assert "Monster" in result
        assert "Pickup" in result
        assert "Hazard" in result

    def test_layer_names_in_output(self):
        result = generate_tag_layer_script(
            layers=["Projectile", "Interactable"]
        )
        assert "Projectile" in result
        assert "Interactable" in result

    def test_contains_menu_item(self):
        result = generate_tag_layer_script(tags=["Test"])
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_tag_layer_script(tags=["Test"])
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Tag/layer sync script
# ---------------------------------------------------------------------------


class TestGenerateTagLayerSyncScript:
    """Tests for generate_tag_layer_sync_script()."""

    def test_contains_file_read_all_text(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "File.ReadAllText" in result

    def test_contains_regex_for_tag_constants(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "TAG_" in result or "Regex" in result or "regex" in result.lower()

    def test_contains_regex_for_layer_constants(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "LAYER_" in result or "Regex" in result or "regex" in result.lower()

    def test_contains_serialized_object_on_tag_manager(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "SerializedObject" in result
        assert "TagManager" in result

    def test_contains_constants_path(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "Assets/Scripts/Core/Constants.cs" in result

    def test_contains_menu_item(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_tag_layer_sync_script("Assets/Scripts/Core/Constants.cs")
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Time settings script
# ---------------------------------------------------------------------------


class TestGenerateTimeSettingsScript:
    """Tests for generate_time_settings_script()."""

    def test_contains_fixed_delta_time(self):
        result = generate_time_settings_script(fixed_timestep=0.02)
        assert "fixedDeltaTime" in result or "TimeManager" in result

    def test_timestep_value_in_output(self):
        result = generate_time_settings_script(fixed_timestep=0.02, maximum_timestep=0.1)
        assert "0.02" in result
        assert "0.1" in result

    def test_time_scale_in_output(self):
        result = generate_time_settings_script(time_scale=1.0)
        assert "timeScale" in result or "Time.timeScale" in result

    def test_contains_menu_item(self):
        result = generate_time_settings_script()
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_time_settings_script()
        assert "vb_result.json" in result

    def test_contains_using_unity_editor(self):
        result = generate_time_settings_script()
        assert "using UnityEditor;" in result


# ---------------------------------------------------------------------------
# Graphics settings script
# ---------------------------------------------------------------------------


class TestGenerateGraphicsSettingsScript:
    """Tests for generate_graphics_settings_script()."""

    def test_contains_render_pipeline(self):
        result = generate_graphics_settings_script(
            render_pipeline_path="Assets/Settings/URP.asset"
        )
        assert "GraphicsSettings" in result or "QualitySettings" in result or "renderPipeline" in result

    def test_contains_asset_database_load(self):
        result = generate_graphics_settings_script(
            render_pipeline_path="Assets/Settings/URP.asset"
        )
        assert "AssetDatabase.LoadAssetAtPath" in result

    def test_fog_mode_in_output(self):
        result = generate_graphics_settings_script(fog_mode="Exponential")
        assert "RenderSettings.fogMode" in result or "FogMode" in result

    def test_contains_menu_item(self):
        result = generate_graphics_settings_script()
        assert '[MenuItem("VeilBreakers/Settings/' in result

    def test_contains_vb_result_json(self):
        result = generate_graphics_settings_script()
        assert "vb_result.json" in result


# ---------------------------------------------------------------------------
# Cross-cutting tests
# ---------------------------------------------------------------------------


class TestAllGeneratorsCommon:
    """Tests that ALL generators share common patterns."""

    def test_all_contain_using_unity_editor(self):
        generators = [
            generate_physics_settings_script(),
            generate_physics_material_script("Test"),
            generate_player_settings_script(company="Test"),
            generate_build_settings_script(),
            generate_quality_settings_script(levels=[{"name": "Low", "shadow_distance": 20}]),
            generate_package_install_script("com.test"),
            generate_package_remove_script("com.test"),
            generate_tag_layer_script(tags=["Test"]),
            generate_tag_layer_sync_script("Constants.cs"),
            generate_time_settings_script(),
            generate_graphics_settings_script(),
        ]
        for i, result in enumerate(generators):
            assert "using UnityEditor;" in result, f"Generator {i} missing using UnityEditor"

    def test_all_contain_vb_result_json(self):
        generators = [
            generate_physics_settings_script(),
            generate_physics_material_script("Test"),
            generate_player_settings_script(company="Test"),
            generate_build_settings_script(),
            generate_quality_settings_script(levels=[{"name": "Low", "shadow_distance": 20}]),
            generate_package_install_script("com.test"),
            generate_package_remove_script("com.test"),
            generate_tag_layer_script(tags=["Test"]),
            generate_tag_layer_sync_script("Constants.cs"),
            generate_time_settings_script(),
            generate_graphics_settings_script(),
        ]
        for i, result in enumerate(generators):
            assert "vb_result.json" in result, f"Generator {i} missing vb_result.json"

    def test_all_contain_menu_item(self):
        generators = [
            generate_physics_settings_script(),
            generate_physics_material_script("Test"),
            generate_player_settings_script(company="Test"),
            generate_build_settings_script(),
            generate_quality_settings_script(levels=[{"name": "Low", "shadow_distance": 20}]),
            generate_package_install_script("com.test"),
            generate_package_remove_script("com.test"),
            generate_tag_layer_script(tags=["Test"]),
            generate_tag_layer_sync_script("Constants.cs"),
            generate_time_settings_script(),
            generate_graphics_settings_script(),
        ]
        for i, result in enumerate(generators):
            assert '[MenuItem("VeilBreakers/Settings/' in result, f"Generator {i} missing MenuItem"
