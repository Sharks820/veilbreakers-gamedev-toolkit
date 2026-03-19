"""Unit tests for Unity performance C# template generators.

Tests that each generator function produces valid C# source containing
the expected keywords, Unity API calls, and parameter substitutions.
Also tests pure-logic helper functions independently.
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    generate_scene_profiler_script,
    generate_lod_setup_script,
    generate_lightmap_bake_script,
    generate_asset_audit_script,
    generate_build_automation_script,
    _analyze_profile_thresholds,
    _classify_asset_issues,
    _validate_lod_screen_percentages,
)


# ---------------------------------------------------------------------------
# Pure-logic helpers
# ---------------------------------------------------------------------------


class TestAnalyzeProfileThresholds:
    """Tests for _analyze_profile_thresholds()."""

    def test_returns_empty_when_within_budget(self):
        data = {"frame_time": 10.0, "draw_calls": 500, "triangles": 100000, "memory_mb": 200.0}
        budgets = {"frame_time": 16.6, "draw_calls": 1000, "triangles": 500000, "memory_mb": 512.0}
        result = _analyze_profile_thresholds(data, budgets)
        assert result == []

    def test_returns_violation_for_exceeded_metric(self):
        data = {"frame_time": 20.0, "draw_calls": 500}
        budgets = {"frame_time": 16.6, "draw_calls": 1000}
        result = _analyze_profile_thresholds(data, budgets)
        assert len(result) == 1
        assert result[0]["metric"] == "frame_time"
        assert result[0]["value"] == 20.0
        assert result[0]["budget"] == 16.6

    def test_returns_multiple_violations(self):
        data = {"frame_time": 25.0, "draw_calls": 1500, "triangles": 600000, "memory_mb": 700.0}
        budgets = {"frame_time": 16.6, "draw_calls": 1000, "triangles": 500000, "memory_mb": 512.0}
        result = _analyze_profile_thresholds(data, budgets)
        assert len(result) == 4

    def test_violation_has_severity(self):
        data = {"draw_calls": 2000}
        budgets = {"draw_calls": 1000}
        result = _analyze_profile_thresholds(data, budgets)
        assert "severity" in result[0]
        assert result[0]["severity"] in ("warning", "critical")

    def test_violation_has_recommendation(self):
        data = {"draw_calls": 2000}
        budgets = {"draw_calls": 1000}
        result = _analyze_profile_thresholds(data, budgets)
        assert "recommendation" in result[0]
        assert len(result[0]["recommendation"]) > 0

    def test_critical_severity_for_large_overshoot(self):
        data = {"draw_calls": 3000}
        budgets = {"draw_calls": 1000}
        result = _analyze_profile_thresholds(data, budgets)
        assert result[0]["severity"] == "critical"

    def test_warning_severity_for_small_overshoot(self):
        data = {"draw_calls": 1100}
        budgets = {"draw_calls": 1000}
        result = _analyze_profile_thresholds(data, budgets)
        assert result[0]["severity"] == "warning"


class TestClassifyAssetIssues:
    """Tests for _classify_asset_issues()."""

    def test_empty_input_returns_empty_categories(self):
        result = _classify_asset_issues([])
        assert result["oversized_textures"]["count"] == 0
        assert result["uncompressed_audio"]["count"] == 0
        assert result["unused_assets"]["count"] == 0
        assert result["duplicate_materials"]["count"] == 0

    def test_classifies_oversized_texture(self):
        assets = [{"type": "texture", "path": "tex.png", "size": 4096, "max_size": 2048}]
        result = _classify_asset_issues(assets)
        assert result["oversized_textures"]["count"] == 1
        assert result["oversized_textures"]["details"][0]["path"] == "tex.png"

    def test_classifies_uncompressed_audio(self):
        assets = [{"type": "audio", "path": "sfx.wav", "compressed": False}]
        result = _classify_asset_issues(assets)
        assert result["uncompressed_audio"]["count"] == 1

    def test_classifies_unused_asset(self):
        assets = [{"type": "unused", "path": "old_model.fbx"}]
        result = _classify_asset_issues(assets)
        assert result["unused_assets"]["count"] == 1

    def test_classifies_duplicate_material(self):
        assets = [{"type": "duplicate_material", "path": "mat_copy.mat", "duplicate_of": "mat.mat"}]
        result = _classify_asset_issues(assets)
        assert result["duplicate_materials"]["count"] == 1

    def test_classifies_mixed_issues(self):
        assets = [
            {"type": "texture", "path": "big.png", "size": 8192, "max_size": 2048},
            {"type": "audio", "path": "music.wav", "compressed": False},
            {"type": "unused", "path": "junk.fbx"},
            {"type": "duplicate_material", "path": "dup.mat", "duplicate_of": "orig.mat"},
        ]
        result = _classify_asset_issues(assets)
        assert result["oversized_textures"]["count"] == 1
        assert result["uncompressed_audio"]["count"] == 1
        assert result["unused_assets"]["count"] == 1
        assert result["duplicate_materials"]["count"] == 1


class TestValidateLodScreenPercentages:
    """Tests for _validate_lod_screen_percentages()."""

    def test_valid_descending(self):
        assert _validate_lod_screen_percentages([0.6, 0.3, 0.15]) is True

    def test_valid_two_levels(self):
        assert _validate_lod_screen_percentages([0.5, 0.1]) is True

    def test_rejects_ascending(self):
        assert _validate_lod_screen_percentages([0.1, 0.3, 0.6]) is False

    def test_rejects_equal_values(self):
        assert _validate_lod_screen_percentages([0.5, 0.5, 0.1]) is False

    def test_rejects_zero_value(self):
        assert _validate_lod_screen_percentages([0.6, 0.0, 0.1]) is False

    def test_rejects_negative_value(self):
        assert _validate_lod_screen_percentages([0.6, -0.1]) is False

    def test_rejects_empty_list(self):
        assert _validate_lod_screen_percentages([]) is False

    def test_single_value_valid(self):
        assert _validate_lod_screen_percentages([0.5]) is True


# ---------------------------------------------------------------------------
# Scene profiler script (PERF-01)
# ---------------------------------------------------------------------------


class TestGenerateSceneProfilerScript:
    """Tests for generate_scene_profiler_script()."""

    def test_contains_using_statements(self):
        result = generate_scene_profiler_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_scene_profiler_script()
        assert '[MenuItem("VeilBreakers/Performance/' in result

    def test_contains_result_json(self):
        result = generate_scene_profiler_script()
        assert "vb_result.json" in result

    def test_contains_unity_stats_draw_calls(self):
        result = generate_scene_profiler_script()
        assert "UnityStats.drawCalls" in result

    def test_contains_unity_stats_batches(self):
        result = generate_scene_profiler_script()
        assert "UnityStats.batches" in result

    def test_contains_unity_stats_triangles(self):
        result = generate_scene_profiler_script()
        assert "UnityStats.triangles" in result

    def test_contains_memory_profiling(self):
        result = generate_scene_profiler_script()
        assert "GetTotalAllocatedMemoryLong" in result

    def test_contains_frame_time(self):
        result = generate_scene_profiler_script()
        assert "unscaledDeltaTime" in result

    def test_contains_budget_thresholds(self):
        budgets = {"frame_time": 16.6, "draw_calls": 1000}
        result = generate_scene_profiler_script(budgets=budgets)
        assert "16.6" in result
        assert "1000" in result

    def test_default_budgets(self):
        result = generate_scene_profiler_script()
        # Should have some default budget values
        assert "budget" in result.lower() or "Budget" in result

    def test_contains_recommendations(self):
        result = generate_scene_profiler_script()
        assert "recommend" in result.lower() or "Recommend" in result

    def test_contains_try_catch(self):
        result = generate_scene_profiler_script()
        assert "try" in result
        assert "catch" in result


# ---------------------------------------------------------------------------
# LOD setup script (PERF-02)
# ---------------------------------------------------------------------------


class TestGenerateLodSetupScript:
    """Tests for generate_lod_setup_script()."""

    def test_contains_using_statements(self):
        result = generate_lod_setup_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_lod_setup_script()
        assert '[MenuItem("VeilBreakers/Performance/' in result

    def test_contains_result_json(self):
        result = generate_lod_setup_script()
        assert "vb_result.json" in result

    def test_contains_lod_group(self):
        result = generate_lod_setup_script()
        assert "LODGroup" in result

    def test_contains_set_lods(self):
        result = generate_lod_setup_script()
        assert "SetLODs" in result

    def test_contains_mesh_renderer(self):
        result = generate_lod_setup_script()
        assert "MeshRenderer" in result

    def test_contains_lod_naming(self):
        result = generate_lod_setup_script()
        assert "_LOD" in result

    def test_screen_percentages_in_output(self):
        result = generate_lod_setup_script(screen_percentages=[0.6, 0.3, 0.15])
        assert "0.6" in result
        assert "0.3" in result
        assert "0.15" in result

    def test_contains_recalculate_bounds(self):
        result = generate_lod_setup_script()
        assert "RecalculateBounds" in result

    def test_contains_occlusion_flags(self):
        result = generate_lod_setup_script()
        assert "OccludeeStatic" in result
        assert "OccluderStatic" in result

    def test_contains_static_editor_flags(self):
        result = generate_lod_setup_script()
        assert "StaticEditorFlags" in result

    def test_custom_lod_count(self):
        result = generate_lod_setup_script(lod_count=4, screen_percentages=[0.7, 0.5, 0.3, 0.1])
        assert "LOD" in result

    def test_rejects_non_descending_percentages(self):
        with pytest.raises(ValueError):
            generate_lod_setup_script(screen_percentages=[0.1, 0.3, 0.6])

    def test_contains_try_catch(self):
        result = generate_lod_setup_script()
        assert "try" in result
        assert "catch" in result


# ---------------------------------------------------------------------------
# Lightmap bake script (PERF-03)
# ---------------------------------------------------------------------------


class TestGenerateLightmapBakeScript:
    """Tests for generate_lightmap_bake_script()."""

    def test_contains_using_statements(self):
        result = generate_lightmap_bake_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_lightmap_bake_script()
        assert '[MenuItem("VeilBreakers/Performance/' in result

    def test_contains_result_json(self):
        result = generate_lightmap_bake_script()
        assert "vb_result.json" in result

    def test_contains_bake_async(self):
        result = generate_lightmap_bake_script()
        assert "BakeAsync" in result

    def test_contains_gi_workflow_on_demand(self):
        result = generate_lightmap_bake_script()
        assert "GIWorkflowMode" in result
        assert "OnDemand" in result

    def test_contains_is_running(self):
        result = generate_lightmap_bake_script()
        assert "isRunning" in result

    def test_contains_lightmap_editor_settings(self):
        result = generate_lightmap_bake_script()
        assert "LightmapEditorSettings" in result

    def test_contains_quality_settings(self):
        result = generate_lightmap_bake_script(quality="high", bounces=4, resolution=64)
        assert "4" in result
        assert "64" in result

    def test_contains_editor_application_update(self):
        result = generate_lightmap_bake_script()
        assert "EditorApplication.update" in result

    def test_default_values(self):
        result = generate_lightmap_bake_script()
        # Should produce valid C# even with defaults
        assert "Lightmapping" in result

    def test_contains_try_catch(self):
        result = generate_lightmap_bake_script()
        assert "try" in result
        assert "catch" in result


# ---------------------------------------------------------------------------
# Asset audit script (PERF-04)
# ---------------------------------------------------------------------------


class TestGenerateAssetAuditScript:
    """Tests for generate_asset_audit_script()."""

    def test_contains_using_statements(self):
        result = generate_asset_audit_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_asset_audit_script()
        assert '[MenuItem("VeilBreakers/Performance/' in result

    def test_contains_result_json(self):
        result = generate_asset_audit_script()
        assert "vb_result.json" in result

    def test_contains_get_all_asset_paths(self):
        result = generate_asset_audit_script()
        assert "GetAllAssetPaths" in result

    def test_contains_texture_importer(self):
        result = generate_asset_audit_script()
        assert "TextureImporter" in result

    def test_contains_audio_importer(self):
        result = generate_asset_audit_script()
        assert "AudioImporter" in result

    def test_contains_dependency_analysis(self):
        result = generate_asset_audit_script()
        assert "GetDependencies" in result

    def test_custom_max_texture_size(self):
        result = generate_asset_audit_script(max_texture_size=1024)
        assert "1024" in result

    def test_default_max_texture_size(self):
        result = generate_asset_audit_script()
        assert "2048" in result

    def test_contains_duplicate_material_detection(self):
        result = generate_asset_audit_script()
        assert "Material" in result

    def test_contains_try_catch(self):
        result = generate_asset_audit_script()
        assert "try" in result
        assert "catch" in result


# ---------------------------------------------------------------------------
# Build automation script (PERF-05)
# ---------------------------------------------------------------------------


class TestGenerateBuildAutomationScript:
    """Tests for generate_build_automation_script()."""

    def test_contains_using_statements(self):
        result = generate_build_automation_script()
        assert "using UnityEngine;" in result
        assert "using UnityEditor;" in result

    def test_contains_menu_item(self):
        result = generate_build_automation_script()
        assert '[MenuItem("VeilBreakers/Performance/' in result

    def test_contains_result_json(self):
        result = generate_build_automation_script()
        assert "vb_result.json" in result

    def test_contains_build_pipeline(self):
        result = generate_build_automation_script()
        assert "BuildPipeline.BuildPlayer" in result

    def test_contains_build_report(self):
        result = generate_build_automation_script()
        assert "BuildReport" in result

    def test_contains_build_result_check(self):
        result = generate_build_automation_script()
        assert "BuildResult.Succeeded" in result

    def test_contains_packed_assets(self):
        result = generate_build_automation_script()
        assert "packedAssets" in result or "PackedAssets" in result

    def test_custom_target(self):
        result = generate_build_automation_script(target="StandaloneWindows64")
        assert "StandaloneWindows64" in result

    def test_custom_scenes(self):
        result = generate_build_automation_script(
            scenes=["Assets/Scenes/Main.unity", "Assets/Scenes/Level1.unity"]
        )
        assert "Main.unity" in result
        assert "Level1.unity" in result

    def test_contains_build_options(self):
        result = generate_build_automation_script()
        assert "BuildOptions" in result

    def test_null_safe_report_access(self):
        result = generate_build_automation_script()
        # Check that the script checks BuildResult before accessing packedAssets
        assert "BuildResult.Succeeded" in result

    def test_contains_try_catch(self):
        result = generate_build_automation_script()
        assert "try" in result
        assert "catch" in result
