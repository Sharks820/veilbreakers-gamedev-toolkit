"""Tests for Unity build & deploy C# template generators.

Covers:
- generate_multi_platform_build_script (BUILD-01): 6 platform targets,
  IL2CPP/Mono backends, BuildPipeline.BuildPlayer, BuildResult checks,
  development flag, namespace wrapping, brace balance
- generate_addressables_config_script (BUILD-02): AddressableAssetSettings,
  CreateGroup, BundledAssetGroupSchema, ContentUpdateGroupSchema,
  local/remote paths, BuildPlayerContent, namespace wrapping
- generate_platform_config_script (BUILD-05): Android manifest with permissions
  and tools:node="merge", iOS PostProcessBuild with PlistDocument/PBXProject,
  WebGL PlayerSettings with Brotli compression
- generate_shader_stripping_script (SHDR-03): IPreprocessShaders, OnProcessShader,
  ShaderKeyword, shaderKeywordSet.IsEnabled, RemoveAt, callbackOrder,
  log stripping toggle
- _validate_platforms, _validate_addressable_groups: pure-logic validators
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.build_templates import (
    _validate_addressable_groups,
    _validate_platforms,
    generate_addressables_config_script,
    generate_multi_platform_build_script,
    generate_platform_config_script,
    generate_shader_stripping_script,
)


# =====================================================================
# Multi-Platform Build Tests (BUILD-01)
# =====================================================================


class TestMultiPlatformBuild:
    """Tests for generate_multi_platform_build_script output."""

    @pytest.fixture
    def build_cs(self) -> str:
        return generate_multi_platform_build_script()

    def test_default_output_contains_build_pipeline(self, build_cs: str):
        assert "BuildPipeline.BuildPlayer" in build_cs

    def test_default_output_has_menu_item(self, build_cs: str):
        assert "[MenuItem" in build_cs

    def test_menu_item_path(self, build_cs: str):
        assert "VeilBreakers/Build/Multi-Platform Build" in build_cs

    def test_default_has_windows(self, build_cs: str):
        assert "StandaloneWindows64" in build_cs

    def test_default_has_mac(self, build_cs: str):
        assert "StandaloneOSX" in build_cs

    def test_default_has_linux(self, build_cs: str):
        assert "StandaloneLinux64" in build_cs

    def test_default_has_android(self, build_cs: str):
        assert "BuildTarget.Android" in build_cs

    def test_default_has_ios(self, build_cs: str):
        assert "BuildTarget.iOS" in build_cs

    def test_default_has_webgl(self, build_cs: str):
        assert "BuildTarget.WebGL" in build_cs

    def test_il2cpp_backend_set(self, build_cs: str):
        assert "ScriptingBackend.IL2CPP" in build_cs

    def test_webgl_mono_backend(self, build_cs: str):
        assert "ScriptingBackend.Mono2x" in build_cs

    def test_build_report_check(self, build_cs: str):
        assert "BuildResult.Succeeded" in build_cs

    def test_result_json_written(self, build_cs: str):
        assert "vb_build_results.json" in build_cs

    def test_switch_build_target(self, build_cs: str):
        assert "EditorUserBuildSettings.SwitchActiveBuildTarget" in build_cs

    def test_set_scripting_backend(self, build_cs: str):
        assert "PlayerSettings.SetScriptingBackend" in build_cs

    def test_named_build_target(self, build_cs: str):
        assert "NamedBuildTarget.FromBuildTargetGroup" in build_cs

    def test_development_flag_absent_by_default(self, build_cs: str):
        assert "BuildOptions.None" in build_cs

    def test_development_flag_present(self):
        out = generate_multi_platform_build_script(development=True)
        assert "BuildOptions.Development" in out

    def test_custom_platforms(self):
        custom = [{"name": "CustomTarget", "target": "StandaloneWindows64", "group": "Standalone", "backend": "Mono2x", "extension": ".exe"}]
        out = generate_multi_platform_build_script(platforms=custom)
        assert "CustomTarget" in out
        # Should only have one platform block
        assert "StandaloneOSX" not in out

    def test_namespace_wrapping(self):
        out = generate_multi_platform_build_script(namespace="VB.Build")
        assert "namespace VB.Build" in out

    def test_balanced_braces(self, build_cs: str):
        assert build_cs.count("{") == build_cs.count("}")

    def test_output_length(self, build_cs: str):
        assert len(build_cs) > 500

    def test_has_using_statements(self, build_cs: str):
        assert "using UnityEditor;" in build_cs
        assert "using UnityEditor.Build.Reporting;" in build_cs
        assert "using UnityEngine;" in build_cs
        assert "using System.IO;" in build_cs

    def test_has_class_declaration(self, build_cs: str):
        assert "public static class VeilBreakers_MultiPlatformBuild" in build_cs

    def test_build_player_options(self, build_cs: str):
        assert "BuildPlayerOptions" in build_cs

    def test_total_size_reported(self, build_cs: str):
        assert "totalSize" in build_cs

    def test_total_time_reported(self, build_cs: str):
        assert "totalTime" in build_cs


# =====================================================================
# Addressables Config Tests (BUILD-02)
# =====================================================================


class TestAddressablesConfig:
    """Tests for generate_addressables_config_script output."""

    @pytest.fixture
    def addr_cs(self) -> str:
        return generate_addressables_config_script()

    def test_default_output_has_addressables(self, addr_cs: str):
        assert "AddressableAssetSettings" in addr_cs

    def test_create_group(self, addr_cs: str):
        assert "CreateGroup" in addr_cs

    def test_bundled_schema(self, addr_cs: str):
        assert "BundledAssetGroupSchema" in addr_cs

    def test_content_update_schema(self, addr_cs: str):
        assert "ContentUpdateGroupSchema" in addr_cs

    def test_local_build_path(self, addr_cs: str):
        assert "kLocalBuildPath" in addr_cs

    def test_local_load_path(self, addr_cs: str):
        assert "kLocalLoadPath" in addr_cs

    def test_remote_paths_not_in_default(self, addr_cs: str):
        # Default group is local, so remote paths should not appear
        assert "kRemoteBuildPath" not in addr_cs

    def test_remote_paths_with_remote_group(self):
        groups = [{"name": "RemoteAssets", "packing": "PackTogether", "local": False}]
        out = generate_addressables_config_script(groups=groups)
        assert "kRemoteBuildPath" in out
        assert "kRemoteLoadPath" in out

    def test_build_player_content(self):
        out = generate_addressables_config_script(build_remote=True)
        assert "BuildPlayerContent" in out

    def test_no_build_by_default(self, addr_cs: str):
        assert "BuildPlayerContent" not in addr_cs

    def test_custom_groups(self):
        groups = [{"name": "MyGroup", "packing": "PackTogether", "local": False}]
        out = generate_addressables_config_script(groups=groups)
        assert "MyGroup" in out

    def test_pack_mode(self, addr_cs: str):
        assert "BundlePackingMode" in addr_cs

    def test_menu_item(self, addr_cs: str):
        assert "[MenuItem" in addr_cs
        assert "VeilBreakers/Build/Configure Addressables" in addr_cs

    def test_balanced_braces(self, addr_cs: str):
        assert addr_cs.count("{") == addr_cs.count("}")

    def test_result_json(self, addr_cs: str):
        assert "vb_result.json" in addr_cs

    def test_namespace(self):
        out = generate_addressables_config_script(namespace="VB.Addressables")
        assert "namespace VB.Addressables" in out

    def test_has_using_statements(self, addr_cs: str):
        assert "using UnityEditor.AddressableAssets;" in addr_cs
        assert "using UnityEditor.AddressableAssets.Settings;" in addr_cs
        assert "using UnityEditor.AddressableAssets.Settings.GroupSchemas;" in addr_cs

    def test_settings_default_object(self, addr_cs: str):
        assert "AddressableAssetSettingsDefaultObject.Settings" in addr_cs

    def test_find_existing_group(self, addr_cs: str):
        assert "FindGroup" in addr_cs

    def test_get_schema(self, addr_cs: str):
        assert "GetSchema<BundledAssetGroupSchema>" in addr_cs

    def test_output_length(self, addr_cs: str):
        assert len(addr_cs) > 500


# =====================================================================
# Platform Config Tests (BUILD-05)
# =====================================================================


class TestPlatformConfig:
    """Tests for generate_platform_config_script output."""

    # --- Android ---

    @pytest.fixture
    def android_cs(self) -> str:
        return generate_platform_config_script(platform="android")

    def test_android_manifest_xml(self, android_cs: str):
        assert '<?xml version' in android_cs

    def test_android_permissions(self, android_cs: str):
        assert "android.permission.INTERNET" in android_cs

    def test_android_custom_permissions(self):
        out = generate_platform_config_script(
            platform="android",
            permissions=["android.permission.CAMERA", "android.permission.VIBRATE"],
        )
        assert "android.permission.CAMERA" in out
        assert "android.permission.VIBRATE" in out

    def test_android_tools_merge(self, android_cs: str):
        assert 'tools:node' in android_cs
        assert 'merge' in android_cs

    def test_android_intent_filter(self, android_cs: str):
        assert "android.intent.action.MAIN" in android_cs

    def test_android_launcher_category(self, android_cs: str):
        assert "android.intent.category.LAUNCHER" in android_cs

    def test_android_features(self, android_cs: str):
        assert "android.hardware.touchscreen" in android_cs

    def test_android_custom_features(self):
        out = generate_platform_config_script(
            platform="android",
            features=["android.hardware.camera"],
        )
        assert "android.hardware.camera" in out

    def test_android_menu_item(self, android_cs: str):
        assert "[MenuItem" in android_cs
        assert "Configure Android" in android_cs

    def test_android_balanced_braces(self, android_cs: str):
        assert android_cs.count("{") == android_cs.count("}")

    def test_android_output_length(self, android_cs: str):
        assert len(android_cs) > 300

    def test_android_manifest_path(self, android_cs: str):
        assert "Assets/Plugins/Android" in android_cs

    def test_android_asset_database_refresh(self, android_cs: str):
        assert "AssetDatabase.Refresh" in android_cs

    # --- iOS ---

    @pytest.fixture
    def ios_cs(self) -> str:
        return generate_platform_config_script(platform="ios")

    def test_ios_post_process_build(self, ios_cs: str):
        assert "PostProcessBuild" in ios_cs

    def test_ios_plist_document(self, ios_cs: str):
        assert "PlistDocument" in ios_cs

    def test_ios_pbx_project(self, ios_cs: str):
        assert "PBXProject" in ios_cs

    def test_ios_info_plist(self, ios_cs: str):
        assert "Info.plist" in ios_cs

    def test_ios_default_entries(self, ios_cs: str):
        assert "ITSAppUsesNonExemptEncryption" in ios_cs
        assert "UIRequiresFullScreen" in ios_cs

    def test_ios_custom_entries(self):
        entries = [
            {"key": "NSCameraUsageDescription", "value": "We need camera", "type": "string"},
        ]
        out = generate_platform_config_script(platform="ios", plist_entries=entries)
        assert "NSCameraUsageDescription" in out
        assert "We need camera" in out

    def test_ios_set_boolean(self, ios_cs: str):
        assert "SetBoolean" in ios_cs

    def test_ios_add_capability(self, ios_cs: str):
        assert "AddCapability" in ios_cs

    def test_ios_using_xcode(self, ios_cs: str):
        assert "using UnityEditor.iOS.Xcode;" in ios_cs

    def test_ios_using_callbacks(self, ios_cs: str):
        assert "using UnityEditor.Callbacks;" in ios_cs

    def test_ios_balanced_braces(self, ios_cs: str):
        assert ios_cs.count("{") == ios_cs.count("}")

    def test_ios_output_length(self, ios_cs: str):
        assert len(ios_cs) > 300

    def test_ios_get_unity_main_target_guid(self, ios_cs: str):
        assert "GetUnityMainTargetGuid" in ios_cs

    # --- WebGL ---

    @pytest.fixture
    def webgl_cs(self) -> str:
        return generate_platform_config_script(platform="webgl")

    def test_webgl_memory_size(self, webgl_cs: str):
        assert "memorySize" in webgl_cs

    def test_webgl_default_memory(self, webgl_cs: str):
        assert "256" in webgl_cs

    def test_webgl_custom_memory(self):
        out = generate_platform_config_script(platform="webgl", webgl_memory_mb=512)
        assert "512" in out

    def test_webgl_compression(self, webgl_cs: str):
        assert "Brotli" in webgl_cs

    def test_webgl_linker_target(self, webgl_cs: str):
        assert "Wasm" in webgl_cs

    def test_webgl_player_settings(self, webgl_cs: str):
        assert "PlayerSettings.WebGL" in webgl_cs

    def test_webgl_menu_item(self, webgl_cs: str):
        assert "[MenuItem" in webgl_cs
        assert "Configure WebGL" in webgl_cs

    def test_webgl_balanced_braces(self, webgl_cs: str):
        assert webgl_cs.count("{") == webgl_cs.count("}")

    def test_webgl_output_length(self, webgl_cs: str):
        assert len(webgl_cs) > 200

    def test_webgl_result_json(self, webgl_cs: str):
        assert "vb_result.json" in webgl_cs

    # --- Invalid platform ---

    def test_invalid_platform_raises(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            generate_platform_config_script(platform="ps5")

    # --- Namespace wrapping ---

    def test_android_namespace(self):
        out = generate_platform_config_script(platform="android", namespace="VB.Platform")
        assert "namespace VB.Platform" in out

    def test_ios_namespace(self):
        out = generate_platform_config_script(platform="ios", namespace="VB.Platform")
        assert "namespace VB.Platform" in out

    def test_webgl_namespace(self):
        out = generate_platform_config_script(platform="webgl", namespace="VB.Platform")
        assert "namespace VB.Platform" in out


# =====================================================================
# Shader Stripping Tests (SHDR-03)
# =====================================================================


class TestShaderStripping:
    """Tests for generate_shader_stripping_script output."""

    @pytest.fixture
    def shader_cs(self) -> str:
        return generate_shader_stripping_script()

    def test_ipreprocess_shaders(self, shader_cs: str):
        assert "IPreprocessShaders" in shader_cs

    def test_on_process_shader(self, shader_cs: str):
        assert "OnProcessShader" in shader_cs

    def test_default_keywords_debug(self, shader_cs: str):
        assert '"DEBUG"' in shader_cs

    def test_default_keywords_editor(self, shader_cs: str):
        assert '"_EDITOR"' in shader_cs

    def test_custom_keywords(self):
        out = generate_shader_stripping_script(keywords_to_strip=["FOG_LINEAR", "_SHADOWS_SOFT"])
        assert '"FOG_LINEAR"' in out
        assert '"_SHADOWS_SOFT"' in out

    def test_shader_keyword_set(self, shader_cs: str):
        assert "shaderKeywordSet.IsEnabled" in shader_cs

    def test_remove_at(self, shader_cs: str):
        assert "RemoveAt" in shader_cs

    def test_callback_order(self, shader_cs: str):
        assert "callbackOrder" in shader_cs

    def test_log_stripping_enabled(self, shader_cs: str):
        assert "Debug.Log" in shader_cs

    def test_no_log_when_disabled(self):
        out = generate_shader_stripping_script(log_stripping=False)
        # The OnProcessShader body should not have Debug.Log for stripping stats
        # But the report class will still have Debug.Log
        # Check that there is no "_totalStripped" tracking
        assert "_totalStripped" not in out

    def test_shader_keyword_constructor(self, shader_cs: str):
        assert "new ShaderKeyword(" in shader_cs

    def test_balanced_braces(self, shader_cs: str):
        assert shader_cs.count("{") == shader_cs.count("}")

    def test_backwards_iteration(self, shader_cs: str):
        assert "data.Count - 1" in shader_cs
        assert "i >= 0" in shader_cs
        assert "i--" in shader_cs

    def test_before_count_tracking(self, shader_cs: str):
        assert "beforeCount" in shader_cs

    def test_namespace_wrapping(self):
        out = generate_shader_stripping_script(namespace="VB.Shaders")
        assert "namespace VB.Shaders" in out

    def test_has_using_statements(self, shader_cs: str):
        assert "using UnityEditor.Build;" in shader_cs
        assert "using UnityEditor.Rendering;" in shader_cs
        assert "using UnityEngine.Rendering;" in shader_cs

    def test_class_name(self, shader_cs: str):
        assert "VeilBreakers_ShaderStripper" in shader_cs

    def test_output_length(self, shader_cs: str):
        assert len(shader_cs) > 400

    def test_strip_results_json(self, shader_cs: str):
        assert "vb_shader_strip_results.json" in shader_cs

    def test_ipostprocess_build_report(self, shader_cs: str):
        assert "IPostprocessBuildWithReport" in shader_cs

    def test_stripped_per_shader_tracking(self, shader_cs: str):
        assert "_strippedPerShader" in shader_cs

    def test_total_processed_tracking(self, shader_cs: str):
        assert "_totalProcessed" in shader_cs


# =====================================================================
# Validation Helper Tests
# =====================================================================


class TestValidationHelpers:
    """Tests for _validate_platforms and _validate_addressable_groups."""

    # --- _validate_platforms ---

    def test_validate_platforms_valid(self):
        valid = [
            {"name": "Win", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP"},
        ]
        assert _validate_platforms(valid) is True

    def test_validate_platforms_empty(self):
        assert _validate_platforms([]) is False

    def test_validate_platforms_none_like(self):
        assert _validate_platforms([]) is False

    def test_validate_platforms_missing_name(self):
        invalid = [{"target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP"}]
        assert _validate_platforms(invalid) is False

    def test_validate_platforms_missing_target(self):
        invalid = [{"name": "Win", "group": "Standalone", "backend": "IL2CPP"}]
        assert _validate_platforms(invalid) is False

    def test_validate_platforms_missing_group(self):
        invalid = [{"name": "Win", "target": "StandaloneWindows64", "backend": "IL2CPP"}]
        assert _validate_platforms(invalid) is False

    def test_validate_platforms_missing_backend(self):
        invalid = [{"name": "Win", "target": "StandaloneWindows64", "group": "Standalone"}]
        assert _validate_platforms(invalid) is False

    def test_validate_platforms_not_dict(self):
        invalid = ["not a dict"]
        assert _validate_platforms(invalid) is False

    def test_validate_platforms_multiple_valid(self):
        valid = [
            {"name": "Win", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP"},
            {"name": "Mac", "target": "StandaloneOSX", "group": "Standalone", "backend": "IL2CPP"},
        ]
        assert _validate_platforms(valid) is True

    def test_validate_platforms_extra_keys_ok(self):
        valid = [
            {"name": "Win", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP", "extension": ".exe"},
        ]
        assert _validate_platforms(valid) is True

    # --- _validate_addressable_groups ---

    def test_validate_groups_valid(self):
        valid = [{"name": "Default"}]
        assert _validate_addressable_groups(valid) is True

    def test_validate_groups_empty(self):
        assert _validate_addressable_groups([]) is False

    def test_validate_groups_missing_name(self):
        invalid = [{"packing": "PackTogether"}]
        assert _validate_addressable_groups(invalid) is False

    def test_validate_groups_invalid_packing(self):
        invalid = [{"name": "Test", "packing": "InvalidMode"}]
        assert _validate_addressable_groups(invalid) is False

    def test_validate_groups_valid_packing_modes(self):
        for mode in ["PackTogether", "PackSeparately", "PackTogetherByLabel"]:
            valid = [{"name": "Test", "packing": mode}]
            assert _validate_addressable_groups(valid) is True

    def test_validate_groups_not_dict(self):
        invalid = ["not a dict"]
        assert _validate_addressable_groups(invalid) is False

    def test_validate_groups_default_packing(self):
        # When packing is not specified, should default to PackSeparately (valid)
        valid = [{"name": "Test"}]
        assert _validate_addressable_groups(valid) is True

    def test_validate_groups_multiple_valid(self):
        valid = [
            {"name": "Group1", "packing": "PackTogether"},
            {"name": "Group2", "packing": "PackSeparately"},
        ]
        assert _validate_addressable_groups(valid) is True
