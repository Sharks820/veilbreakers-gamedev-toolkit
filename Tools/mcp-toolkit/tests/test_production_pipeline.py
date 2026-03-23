"""Unit tests for Phase 24 Production Pipeline C# template generators.

Tests that each generator function:
1. Returns a dict with script_path, script_content, next_steps
2. Produces valid C# source with balanced braces and proper syntax
3. Contains expected Unity API calls, classes, and parameter substitutions
4. Handles custom parameters correctly

Also tests pure-Python helpers:
- check_name_conflicts: offline type name conflict detection
- generate_pipeline_step_definitions: pipeline metadata
- validate_cs_syntax: offline C# syntax validation

Requirements covered:
    PROD-01: Compile recovery (generate_compile_recovery_script)
    PROD-02: Conflict detection (generate_conflict_detector_script, check_name_conflicts)
    PROD-03: Pipeline orchestration (generate_pipeline_orchestrator_script, generate_pipeline_step_definitions)
    PROD-04: Art style validation (generate_art_style_validator_script)
    PROD-05: Build smoke tests (generate_build_smoke_test_script, validate_cs_syntax)
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.production_templates import (
    generate_compile_recovery_script,
    generate_conflict_detector_script,
    check_name_conflicts,
    generate_pipeline_orchestrator_script,
    generate_pipeline_step_definitions,
    generate_art_style_validator_script,
    generate_build_smoke_test_script,
    validate_cs_syntax,
    ERROR_CLASSIFICATIONS,
    ALL_ERROR_TYPES,
    COMMON_USINGS,
    PIPELINE_DEFINITIONS,
    ALL_PIPELINES,
    DEFAULT_PALETTE_COLORS,
    DEFAULT_ROUGHNESS_RANGE,
    DEFAULT_MAX_TEXEL_DENSITY,
    DEFAULT_NAMING_PATTERN,
)


# ---------------------------------------------------------------------------
# Helpers for C# validation
# ---------------------------------------------------------------------------


def _check_balanced_braces(code: str) -> bool:
    """Verify that curly braces are balanced in the generated C# code."""
    count = 0
    for ch in code:
        if ch == "{":
            count += 1
        elif ch == "}":
            count -= 1
        if count < 0:
            return False
    return count == 0


def _check_output_structure(result: dict) -> None:
    """Assert that a generator result has the correct dict structure."""
    assert isinstance(result, dict), "Result must be a dict"
    assert "script_path" in result, "Missing script_path"
    assert "script_content" in result, "Missing script_content"
    assert "next_steps" in result, "Missing next_steps"
    assert isinstance(result["script_path"], str), "script_path must be str"
    assert isinstance(result["script_content"], str), "script_content must be str"
    assert isinstance(result["next_steps"], list), "next_steps must be list"
    assert len(result["next_steps"]) > 0, "next_steps must not be empty"
    assert len(result["script_content"]) > 100, "script_content too short"


def _check_cs_path(result: dict) -> None:
    """Assert that script_path ends with .cs."""
    assert result["script_path"].endswith(".cs"), "script_path must end with .cs"


# ===========================================================================
# Module-level constants tests
# ===========================================================================


class TestModuleConstants:
    """Tests for module-level constants and configuration data."""

    def test_error_classifications_present(self):
        expected = {"missing_reference", "duplicate_type", "syntax_error",
                    "missing_using", "type_mismatch", "member_hiding"}
        assert set(ERROR_CLASSIFICATIONS.keys()) == expected

    def test_error_classification_structure(self):
        for etype, data in ERROR_CLASSIFICATIONS.items():
            assert "patterns" in data, f"{etype} missing patterns"
            assert "description" in data, f"{etype} missing description"
            assert "auto_fixable" in data, f"{etype} missing auto_fixable"
            assert "fix_strategy" in data, f"{etype} missing fix_strategy"
            assert isinstance(data["patterns"], list), f"{etype} patterns must be list"
            assert len(data["patterns"]) > 0, f"{etype} must have at least one pattern"

    def test_all_error_types_list(self):
        assert len(ALL_ERROR_TYPES) == 6
        assert set(ALL_ERROR_TYPES) == set(ERROR_CLASSIFICATIONS.keys())

    def test_auto_fixable_errors(self):
        fixable = {k for k, v in ERROR_CLASSIFICATIONS.items() if v["auto_fixable"]}
        assert "missing_reference" in fixable
        assert "syntax_error" in fixable
        assert "missing_using" in fixable

    def test_non_auto_fixable_errors(self):
        not_fixable = {k for k, v in ERROR_CLASSIFICATIONS.items() if not v["auto_fixable"]}
        assert "duplicate_type" in not_fixable
        assert "type_mismatch" in not_fixable

    def test_common_usings_present(self):
        assert len(COMMON_USINGS) > 20
        assert "MonoBehaviour" in COMMON_USINGS
        assert "EditorWindow" in COMMON_USINGS
        assert "Vector3" in COMMON_USINGS
        assert "List" in COMMON_USINGS
        assert "CompilationPipeline" in COMMON_USINGS

    def test_common_usings_values_are_namespaces(self):
        for type_name, ns in COMMON_USINGS.items():
            assert isinstance(ns, str), f"{type_name} using must be str"
            assert len(ns) > 0, f"{type_name} using must be non-empty"
            # Namespace must be dot-separated identifiers
            parts = ns.split(".")
            for part in parts:
                assert len(part) > 0, f"Empty segment in namespace for {type_name}"

    def test_pipeline_definitions_present(self):
        expected = {"create_character", "create_level", "create_item", "full_build"}
        assert set(PIPELINE_DEFINITIONS.keys()) == expected

    def test_pipeline_definition_structure(self):
        for pname, pdef in PIPELINE_DEFINITIONS.items():
            assert "description" in pdef, f"{pname} missing description"
            assert "steps" in pdef, f"{pname} missing steps"
            assert isinstance(pdef["steps"], list), f"{pname} steps must be list"
            assert len(pdef["steps"]) > 0, f"{pname} must have steps"

    def test_pipeline_step_structure(self):
        for pname, pdef in PIPELINE_DEFINITIONS.items():
            for step in pdef["steps"]:
                assert "name" in step, f"{pname} step missing name"
                assert "tool" in step, f"{pname} step missing tool"
                assert "action" in step, f"{pname} step missing action"
                assert "timeout" in step, f"{pname} step missing timeout"
                assert isinstance(step["timeout"], int), f"{pname} step timeout must be int"
                assert step["timeout"] > 0, f"{pname} step timeout must be positive"

    def test_all_pipelines_list(self):
        assert len(ALL_PIPELINES) == 4
        assert set(ALL_PIPELINES) == set(PIPELINE_DEFINITIONS.keys())

    def test_create_character_pipeline_steps(self):
        steps = PIPELINE_DEFINITIONS["create_character"]["steps"]
        step_names = [s["name"] for s in steps]
        assert "mesh_import" in step_names
        assert "rig_setup" in step_names
        assert "prefab_create" in step_names

    def test_full_build_pipeline_steps(self):
        steps = PIPELINE_DEFINITIONS["full_build"]["steps"]
        step_names = [s["name"] for s in steps]
        assert "compile_check" in step_names
        assert "run_tests" in step_names
        assert "build" in step_names

    def test_default_palette_colors(self):
        assert len(DEFAULT_PALETTE_COLORS) == 10
        for pc in DEFAULT_PALETTE_COLORS:
            assert "name" in pc
            assert "hsv" in pc
            assert "tolerance" in pc
            assert len(pc["hsv"]) == 3

    def test_default_roughness_range(self):
        assert DEFAULT_ROUGHNESS_RANGE[0] < DEFAULT_ROUGHNESS_RANGE[1]
        assert 0.0 <= DEFAULT_ROUGHNESS_RANGE[0] <= 1.0
        assert 0.0 <= DEFAULT_ROUGHNESS_RANGE[1] <= 1.0

    def test_default_max_texel_density(self):
        assert DEFAULT_MAX_TEXEL_DENSITY > 0

    def test_default_naming_pattern(self):
        import re
        pattern = re.compile(DEFAULT_NAMING_PATTERN)
        assert pattern.match("VB_TestAsset")
        assert pattern.match("SomeClass")
        assert not pattern.match("123invalid")


# ===========================================================================
# PROD-01: Compile Recovery
# ===========================================================================


class TestGenerateCompileRecoveryScript:
    """Tests for generate_compile_recovery_script() -- PROD-01."""

    def test_output_structure(self):
        result = generate_compile_recovery_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_compile_recovery_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_compile_recovery_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_compile_recovery_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_compile_recovery_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_compile_recovery_script()
        assert "MenuItem" in result["script_content"]

    def test_menu_path_pipeline(self):
        result = generate_compile_recovery_script()
        assert "VeilBreakers/Pipeline/Compile Recovery" in result["script_content"]

    def test_contains_compilation_pipeline(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "CompilationPipeline" in content
        assert "assemblyCompilationFinished" in content

    def test_contains_error_classifications(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "missing_reference" in content
        assert "duplicate_type" in content
        assert "syntax_error" in content
        assert "missing_using" in content
        assert "type_mismatch" in content

    def test_contains_initialize_on_load(self):
        result = generate_compile_recovery_script()
        assert "InitializeOnLoad" in result["script_content"]

    def test_contains_auto_fix_logic(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "AttemptAutoFix" in content
        assert "TryAddMissingUsing" in content
        assert "TryFixSyntax" in content

    def test_default_auto_fix_enabled(self):
        result = generate_compile_recovery_script()
        assert "autoFixEnabled = true" in result["script_content"]

    def test_auto_fix_disabled(self):
        result = generate_compile_recovery_script(auto_fix_enabled=False)
        assert "autoFixEnabled = false" in result["script_content"]

    def test_default_max_retries(self):
        result = generate_compile_recovery_script()
        assert "MaxRetries = 3" in result["script_content"]

    def test_custom_max_retries(self):
        result = generate_compile_recovery_script(max_retries=5)
        assert "MaxRetries = 5" in result["script_content"]

    def test_default_log_path(self):
        result = generate_compile_recovery_script()
        assert "vb_compile_recovery.json" in result["script_content"]

    def test_custom_log_path(self):
        result = generate_compile_recovery_script(log_path="Logs/recovery.json")
        assert "Logs/recovery.json" in result["script_content"]

    def test_watch_assemblies_none(self):
        result = generate_compile_recovery_script(watch_assemblies=None)
        assert "WatchAssemblies = null" in result["script_content"]

    def test_watch_assemblies_custom(self):
        result = generate_compile_recovery_script(
            watch_assemblies=["Assembly-CSharp", "Assembly-CSharp-Editor"]
        )
        content = result["script_content"]
        assert "Assembly-CSharp" in content
        assert "Assembly-CSharp-Editor" in content

    def test_contains_recovery_log_class(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "RecoveryLog" in content
        assert "CompileError" in content
        assert "FixAttempt" in content

    def test_contains_classify_error(self):
        result = generate_compile_recovery_script()
        assert "ClassifyError" in result["script_content"]

    def test_contains_write_log(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "WriteLog" in content
        assert "JsonUtility.ToJson" in content

    def test_contains_delay_call(self):
        result = generate_compile_recovery_script()
        assert "EditorApplication.delayCall" in result["script_content"]

    def test_contains_asset_database_refresh(self):
        result = generate_compile_recovery_script()
        assert "AssetDatabase.Refresh" in result["script_content"]

    def test_contains_common_usings_dict(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "CommonUsings" in content
        assert "MonoBehaviour" in content
        assert "UnityEngine" in content

    def test_contains_gui_elements(self):
        result = generate_compile_recovery_script()
        content = result["script_content"]
        assert "OnGUI" in content
        assert "GUILayout.Button" in content
        assert "EditorGUILayout" in content

    def test_next_steps_contains_recompile(self):
        result = generate_compile_recovery_script()
        steps_text = " ".join(result["next_steps"])
        assert "recompile" in steps_text.lower()


# ===========================================================================
# PROD-02: Conflict Detection
# ===========================================================================


class TestGenerateConflictDetectorScript:
    """Tests for generate_conflict_detector_script() -- PROD-02."""

    def test_output_structure(self):
        result = generate_conflict_detector_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_conflict_detector_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_conflict_detector_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_conflict_detector_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_conflict_detector_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_conflict_detector_script()
        assert "MenuItem" in result["script_content"]

    def test_menu_path_pipeline(self):
        result = generate_conflict_detector_script()
        assert "VeilBreakers/Pipeline/Conflict Detector" in result["script_content"]

    def test_contains_scan_project(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "ScanProject" in content
        assert "ScanFileForTypes" in content

    def test_contains_type_registry(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "typeRegistry" in content
        assert "guidRegistry" in content

    def test_contains_check_type_name(self):
        result = generate_conflict_detector_script()
        assert "CheckTypeName" in result["script_content"]

    def test_contains_check_file_path(self):
        result = generate_conflict_detector_script()
        assert "CheckFilePath" in result["script_content"]

    def test_contains_conflict_result_class(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "ConflictResult" in content
        assert "ConflictReport" in content

    def test_default_scan_paths(self):
        result = generate_conflict_detector_script()
        assert '"Assets"' in result["script_content"]

    def test_custom_scan_paths(self):
        result = generate_conflict_detector_script(
            scan_paths=["Assets/Scripts", "Assets/Editor"]
        )
        content = result["script_content"]
        assert "Assets/Scripts" in content
        assert "Assets/Editor" in content

    def test_default_namespace_prefix(self):
        result = generate_conflict_detector_script()
        assert "VeilBreakers" in result["script_content"]

    def test_custom_namespace_prefix(self):
        result = generate_conflict_detector_script(namespace_prefix="MyGame")
        assert "MyGame" in result["script_content"]

    def test_contains_duplicate_type_detection(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "duplicate_type" in content

    def test_contains_case_collision_detection(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "case_collision" in content
        assert "OrdinalIgnoreCase" in content

    def test_contains_file_exists_check(self):
        result = generate_conflict_detector_script()
        assert "file_exists" in result["script_content"]

    def test_contains_guid_scanning(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "guid" in content.lower()
        assert ".meta" in content

    def test_contains_regex_type_pattern(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "class" in content
        assert "struct" in content
        assert "enum" in content
        assert "interface" in content

    def test_contains_run_full_check(self):
        result = generate_conflict_detector_script()
        assert "RunFullCheck" in result["script_content"]

    def test_contains_severity_levels(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert '"error"' in content
        assert '"warning"' in content
        assert '"ok"' in content

    def test_contains_gui_elements(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "OnGUI" in content
        assert "GUILayout.Button" in content

    def test_ignore_patterns_default(self):
        result = generate_conflict_detector_script()
        content = result["script_content"]
        assert "IgnorePatterns" in content

    def test_custom_ignore_patterns(self):
        result = generate_conflict_detector_script(
            ignore_patterns=[r".*Test.*\.cs$"]
        )
        assert "Test" in result["script_content"]


# ===========================================================================
# PROD-02: Python-side conflict detection (check_name_conflicts)
# ===========================================================================


class TestCheckNameConflicts:
    """Tests for check_name_conflicts() -- PROD-02 Python helper."""

    def test_no_conflicts(self):
        files = {
            "Foo.cs": "public class Foo { }",
            "Bar.cs": "public class Bar { }",
        }
        result = check_name_conflicts(files, ["Baz", "Qux"])
        assert result["conflict_count"] == 0
        assert len(result["conflicts"]) == 0

    def test_duplicate_type_conflict(self):
        files = {
            "Foo.cs": "public class Foo { }",
        }
        result = check_name_conflicts(files, ["Foo"])
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["conflict_type"] == "duplicate_type"
        assert result["conflicts"][0]["severity"] == "error"

    def test_case_collision(self):
        files = {
            "Foo.cs": "public class Foo { }",
        }
        result = check_name_conflicts(files, ["foo"])
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["conflict_type"] == "case_collision"
        assert result["conflicts"][0]["severity"] == "warning"

    def test_multiple_conflicts(self):
        files = {
            "Player.cs": "public class Player { }",
            "Enemy.cs": "public class Enemy { }",
        }
        result = check_name_conflicts(files, ["Player", "Enemy", "NewClass"])
        assert result["conflict_count"] == 2

    def test_struct_detection(self):
        files = {
            "Data.cs": "public struct PlayerData { }",
        }
        result = check_name_conflicts(files, ["PlayerData"])
        assert result["conflict_count"] == 1

    def test_enum_detection(self):
        files = {
            "Types.cs": "public enum WeaponType { Sword, Axe }",
        }
        result = check_name_conflicts(files, ["WeaponType"])
        assert result["conflict_count"] == 1

    def test_interface_detection(self):
        files = {
            "Interfaces.cs": "public interface IDamageable { }",
        }
        result = check_name_conflicts(files, ["IDamageable"])
        assert result["conflict_count"] == 1

    def test_scans_correct_count(self):
        files = {
            "Multi.cs": "public class A { }\npublic class B { }\npublic struct C { }",
        }
        result = check_name_conflicts(files, ["D"])
        assert result["total_types_scanned"] == 3

    def test_empty_project(self):
        result = check_name_conflicts({}, ["Foo"])
        assert result["total_types_scanned"] == 0
        assert result["conflict_count"] == 0

    def test_empty_proposed(self):
        files = {"Foo.cs": "public class Foo { }"}
        result = check_name_conflicts(files, [])
        assert result["proposed_count"] == 0
        assert result["conflict_count"] == 0

    def test_suggestions_present(self):
        files = {"Foo.cs": "public class Foo { }"}
        result = check_name_conflicts(files, ["Foo"])
        assert len(result["conflicts"][0]["suggestions"]) > 0

    def test_existing_files_in_conflict(self):
        files = {"path/to/Foo.cs": "public class Foo { }"}
        result = check_name_conflicts(files, ["Foo"])
        assert "path/to/Foo.cs" in result["conflicts"][0]["existing_files"]

    def test_private_class_detected(self):
        files = {"Foo.cs": "private class Secret { }"}
        result = check_name_conflicts(files, ["Secret"])
        assert result["conflict_count"] == 1

    def test_internal_class_detected(self):
        files = {"Foo.cs": "internal class Internal { }"}
        result = check_name_conflicts(files, ["Internal"])
        assert result["conflict_count"] == 1

    def test_abstract_class_detected(self):
        files = {"Base.cs": "public abstract class BaseSystem { }"}
        result = check_name_conflicts(files, ["BaseSystem"])
        assert result["conflict_count"] == 1

    def test_sealed_class_detected(self):
        files = {"Final.cs": "public sealed class FinalBoss { }"}
        result = check_name_conflicts(files, ["FinalBoss"])
        assert result["conflict_count"] == 1

    def test_partial_class_detected(self):
        files = {"Part.cs": "public partial class SplitClass { }"}
        result = check_name_conflicts(files, ["SplitClass"])
        assert result["conflict_count"] == 1


# ===========================================================================
# PROD-03: Pipeline Orchestrator
# ===========================================================================


class TestGeneratePipelineOrchestratorScript:
    """Tests for generate_pipeline_orchestrator_script() -- PROD-03."""

    def test_output_structure(self):
        result = generate_pipeline_orchestrator_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_pipeline_orchestrator_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_pipeline_orchestrator_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_pipeline_orchestrator_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_pipeline_orchestrator_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_pipeline_orchestrator_script()
        assert "MenuItem" in result["script_content"]

    def test_menu_path_pipeline(self):
        result = generate_pipeline_orchestrator_script()
        assert "VeilBreakers/Pipeline/Pipeline Orchestrator" in result["script_content"]

    def test_contains_step_status_enum(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "StepStatus" in content
        assert "Pending" in content
        assert "Running" in content
        assert "Success" in content
        assert "Failed" in content
        assert "Skipped" in content

    def test_contains_failure_mode_enum(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "FailureMode" in content
        assert "Stop" in content
        assert "Continue" in content
        assert "Retry" in content

    def test_contains_pipeline_step_class(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "PipelineStep" in content
        assert "PipelineDefinition" in content
        assert "PipelineReport" in content

    def test_contains_builtin_pipelines(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "create_character" in content
        assert "create_level" in content
        assert "create_item" in content
        assert "full_build" in content

    def test_contains_start_pipeline(self):
        result = generate_pipeline_orchestrator_script()
        assert "StartPipeline" in result["script_content"]

    def test_contains_execute_step(self):
        result = generate_pipeline_orchestrator_script()
        assert "ExecuteCurrentStep" in result["script_content"]

    def test_contains_complete_step(self):
        result = generate_pipeline_orchestrator_script()
        assert "CompleteStep" in result["script_content"]

    def test_contains_finish_pipeline(self):
        result = generate_pipeline_orchestrator_script()
        assert "FinishPipeline" in result["script_content"]

    def test_contains_estimate_remaining(self):
        result = generate_pipeline_orchestrator_script()
        assert "EstimateRemainingMs" in result["script_content"]

    def test_contains_load_pipeline(self):
        result = generate_pipeline_orchestrator_script()
        assert "LoadPipeline" in result["script_content"]

    def test_default_pipeline_name(self):
        result = generate_pipeline_orchestrator_script()
        assert "custom" in result["script_content"]

    def test_named_pipeline_create_character(self):
        result = generate_pipeline_orchestrator_script(pipeline_name="create_character")
        content = result["script_content"]
        assert "mesh_import" in content
        assert "rig_setup" in content

    def test_named_pipeline_full_build(self):
        result = generate_pipeline_orchestrator_script(pipeline_name="full_build")
        content = result["script_content"]
        assert "compile_check" in content
        assert "run_tests" in content

    def test_custom_steps(self):
        steps = [
            {"name": "my_step", "tool": "unity_editor", "action": "recompile", "timeout": 60},
            {"name": "my_step_2", "tool": "unity_qa", "action": "test_runner", "timeout": 120},
        ]
        result = generate_pipeline_orchestrator_script(steps=steps)
        content = result["script_content"]
        assert "my_step" in content
        assert "my_step_2" in content
        assert "unity_editor" in content
        assert "unity_qa" in content

    def test_on_failure_stop(self):
        result = generate_pipeline_orchestrator_script(on_failure="stop")
        assert "FailureMode.Stop" in result["script_content"]

    def test_on_failure_continue(self):
        result = generate_pipeline_orchestrator_script(on_failure="continue")
        assert "FailureMode.Continue" in result["script_content"]

    def test_on_failure_retry(self):
        result = generate_pipeline_orchestrator_script(on_failure="retry")
        assert "FailureMode.Retry" in result["script_content"]

    def test_on_failure_invalid_defaults_to_stop(self):
        result = generate_pipeline_orchestrator_script(on_failure="invalid")
        assert "FailureMode.Stop" in result["script_content"]

    def test_contains_progress_bar(self):
        result = generate_pipeline_orchestrator_script()
        assert "ProgressBar" in result["script_content"]

    def test_contains_json_report(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "JsonUtility.ToJson" in content
        assert "vb_pipeline_report.json" in content

    def test_contains_stopwatch(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "Stopwatch" in content
        assert "System.Diagnostics" in content

    def test_contains_gui_elements(self):
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "OnGUI" in content
        assert "GUILayout.Button" in content

    def test_contains_delay_call(self):
        result = generate_pipeline_orchestrator_script()
        assert "EditorApplication.delayCall" in result["script_content"]


# ===========================================================================
# PROD-03: Pipeline Step Definitions (Python helper)
# ===========================================================================


class TestGeneratePipelineStepDefinitions:
    """Tests for generate_pipeline_step_definitions() -- PROD-03 Python helper."""

    def test_returns_dict(self):
        result = generate_pipeline_step_definitions()
        assert isinstance(result, dict)

    def test_contains_pipelines(self):
        result = generate_pipeline_step_definitions()
        assert "pipelines" in result
        assert isinstance(result["pipelines"], dict)

    def test_contains_dependency_graph(self):
        result = generate_pipeline_step_definitions()
        assert "dependency_graph" in result
        assert isinstance(result["dependency_graph"], dict)

    def test_contains_available_pipelines(self):
        result = generate_pipeline_step_definitions()
        assert "available_pipelines" in result
        assert set(result["available_pipelines"]) == set(PIPELINE_DEFINITIONS.keys())

    def test_contains_counts(self):
        result = generate_pipeline_step_definitions()
        assert "total_pipeline_count" in result
        assert "total_step_count" in result
        assert result["total_pipeline_count"] == 4
        assert result["total_step_count"] > 0

    def test_dependency_graph_structure(self):
        result = generate_pipeline_step_definitions()
        for pname, deps in result["dependency_graph"].items():
            assert isinstance(deps, dict), f"{pname} deps must be dict"
            # First step should have no dependencies
            first_step = PIPELINE_DEFINITIONS[pname]["steps"][0]["name"]
            assert deps[first_step] == [], f"{pname} first step should have no deps"

    def test_dependency_graph_sequential(self):
        result = generate_pipeline_step_definitions()
        for pname in PIPELINE_DEFINITIONS:
            steps = PIPELINE_DEFINITIONS[pname]["steps"]
            deps = result["dependency_graph"][pname]
            for i in range(1, len(steps)):
                curr = steps[i]["name"]
                prev = steps[i - 1]["name"]
                assert prev in deps[curr], \
                    f"{pname}: {curr} should depend on {prev}"

    def test_all_pipelines_in_graph(self):
        result = generate_pipeline_step_definitions()
        assert set(result["dependency_graph"].keys()) == set(PIPELINE_DEFINITIONS.keys())

    def test_total_step_count_matches(self):
        result = generate_pipeline_step_definitions()
        expected = sum(len(p["steps"]) for p in PIPELINE_DEFINITIONS.values())
        assert result["total_step_count"] == expected


# ===========================================================================
# PROD-04: Art Style Validator
# ===========================================================================


class TestGenerateArtStyleValidatorScript:
    """Tests for generate_art_style_validator_script() -- PROD-04."""

    def test_output_structure(self):
        result = generate_art_style_validator_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_art_style_validator_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_art_style_validator_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_art_style_validator_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_art_style_validator_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_art_style_validator_script()
        assert "MenuItem" in result["script_content"]

    def test_menu_path_pipeline(self):
        result = generate_art_style_validator_script()
        assert "VeilBreakers/Pipeline/Art Style Validator" in result["script_content"]

    def test_contains_palette_check(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "PaletteColor" in content
        assert "CheckPalette" in content
        assert "RGBToHSV" in content

    def test_contains_roughness_check(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "RoughnessMin" in content
        assert "RoughnessMax" in content
        assert "roughness_range" in content

    def test_contains_texel_density_check(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "MaxTexelDensity" in content
        assert "texel_density" in content

    def test_contains_naming_check(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "NamingRegex" in content
        assert "naming_convention" in content

    def test_contains_validation_issue_class(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "ValidationIssue" in content
        assert "ValidationReport" in content
        assert "CheckSeverity" in content

    def test_contains_severity_levels(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "Pass" in content
        assert "Warning" in content
        assert "Fail" in content

    def test_contains_run_validation(self):
        result = generate_art_style_validator_script()
        assert "RunValidation" in result["script_content"]

    def test_default_palette_colors_in_output(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "shadow_black" in content
        assert "blood_red" in content
        assert "bone_white" in content

    def test_custom_palette_colors(self):
        custom = [
            {"name": "my_red", "hsv": [0, 1.0, 0.5], "tolerance": 10},
            {"name": "my_blue", "hsv": [240, 1.0, 0.5], "tolerance": 15},
        ]
        result = generate_art_style_validator_script(palette_colors=custom)
        content = result["script_content"]
        assert "my_red" in content
        assert "my_blue" in content

    def test_default_roughness_range_in_output(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "0.3f" in content  # min
        assert "0.95f" in content  # max

    def test_custom_roughness_range(self):
        result = generate_art_style_validator_script(roughness_range=(0.2, 0.8))
        content = result["script_content"]
        assert "0.2f" in content
        assert "0.8f" in content

    def test_custom_max_texel_density(self):
        result = generate_art_style_validator_script(max_texel_density=20.0)
        assert "20.0f" in result["script_content"]

    def test_custom_naming_pattern(self):
        result = generate_art_style_validator_script(naming_pattern=r"^VB_.*$")
        assert "VB_" in result["script_content"]

    def test_contains_material_scanning(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "FindAssets" in content
        assert "t:Material" in content

    def test_contains_mesh_scanning(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "t:Mesh" in content

    def test_contains_json_report(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "JsonUtility.ToJson" in content
        assert "vb_art_style_report.json" in content

    def test_contains_gui_toggles(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "scanMaterials" in content
        assert "scanTextures" in content
        assert "scanNaming" in content

    def test_contains_gui_elements(self):
        result = generate_art_style_validator_script()
        content = result["script_content"]
        assert "OnGUI" in content
        assert "GUILayout.Button" in content


# ===========================================================================
# PROD-05: Build Smoke Test
# ===========================================================================


class TestGenerateBuildSmokeTestScript:
    """Tests for generate_build_smoke_test_script() -- PROD-05."""

    def test_output_structure(self):
        result = generate_build_smoke_test_script()
        _check_output_structure(result)

    def test_cs_path(self):
        result = generate_build_smoke_test_script()
        _check_cs_path(result)

    def test_path_contains_editor(self):
        result = generate_build_smoke_test_script()
        assert "Editor" in result["script_path"]

    def test_balanced_braces(self):
        result = generate_build_smoke_test_script()
        assert _check_balanced_braces(result["script_content"]), "Unbalanced braces"

    def test_contains_editor_window(self):
        result = generate_build_smoke_test_script()
        assert "EditorWindow" in result["script_content"]

    def test_contains_menu_item(self):
        result = generate_build_smoke_test_script()
        assert "MenuItem" in result["script_content"]

    def test_menu_path_pipeline(self):
        result = generate_build_smoke_test_script()
        assert "VeilBreakers/Pipeline/Build Smoke Test" in result["script_content"]

    def test_contains_smoke_test_check(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "SmokeTestCheck" in content
        assert "SmokeTestReport" in content

    def test_contains_run_smoke_test(self):
        result = generate_build_smoke_test_script()
        assert "RunSmokeTest" in result["script_content"]

    def test_contains_build_exists_check(self):
        result = generate_build_smoke_test_script()
        assert "build_exists" in result["script_content"]

    def test_contains_build_size_check(self):
        result = generate_build_smoke_test_script()
        assert "build_size" in result["script_content"]

    def test_contains_process_launch(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "process_launch" in content
        assert "Process.Start" in content

    def test_contains_process_stable_check(self):
        result = generate_build_smoke_test_script()
        assert "process_stable" in result["script_content"]

    def test_contains_log_analysis(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "log_analysis" in content
        assert "Player.log" in content

    def test_default_build_path(self):
        result = generate_build_smoke_test_script()
        assert "VeilBreakers.exe" in result["script_content"]

    def test_custom_build_path(self):
        result = generate_build_smoke_test_script(build_path="Builds/MyGame.exe")
        assert "MyGame.exe" in result["script_content"]

    def test_default_timeout(self):
        result = generate_build_smoke_test_script()
        assert "timeoutSeconds = 30" in result["script_content"]

    def test_custom_timeout(self):
        result = generate_build_smoke_test_script(timeout_seconds=60)
        assert "timeoutSeconds = 60" in result["script_content"]

    def test_custom_scene_to_load(self):
        result = generate_build_smoke_test_script(scene_to_load="MainMenu")
        assert "MainMenu" in result["script_content"]

    def test_custom_expected_fps(self):
        result = generate_build_smoke_test_script(expected_fps_min=30)
        assert "expectedFpsMin = 30" in result["script_content"]

    def test_contains_process_kill_cleanup(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "Kill" in content

    def test_contains_json_report(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "JsonUtility.ToJson" in content
        assert "vb_smoke_test_report.json" in content

    def test_contains_gui_elements(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "OnGUI" in content
        assert "GUILayout.Button" in content

    def test_contains_player_log_path(self):
        result = generate_build_smoke_test_script()
        assert "GetPlayerLogPath" in result["script_content"]

    def test_contains_error_regex(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "Error" in content
        assert "Exception" in content

    def test_contains_async(self):
        result = generate_build_smoke_test_script()
        content = result["script_content"]
        assert "async" in content
        assert "await" in content
        assert "Task.Delay" in content


# ===========================================================================
# PROD-05: Offline C# Syntax Validator (Python)
# ===========================================================================


class TestValidateCsSyntax:
    """Tests for validate_cs_syntax() -- PROD-05 Python helper."""

    def test_valid_code_no_issues(self):
        code = """using UnityEngine;

public class Foo : MonoBehaviour
{
    void Start()
    {
        Debug.Log("Hello");
    }
}
"""
        issues = validate_cs_syntax(code)
        # Should have no errors (warnings are acceptable)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_unbalanced_braces_missing_close(self):
        code = """public class Foo {
    void Start() {
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] == "CS_UNCLOSED_DELIM"]
        assert len(errors) >= 1

    def test_unbalanced_braces_extra_close(self):
        code = """public class Foo {
}
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] == "CS_UNMATCHED_CLOSE"]
        assert len(errors) >= 1

    def test_unbalanced_parentheses(self):
        code = """public class Foo {
    void Start() {
        Debug.Log("hello"
    }
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] in ("CS_UNCLOSED_DELIM", "CS_UNMATCHED_CLOSE")]
        assert len(errors) >= 1

    def test_using_after_code(self):
        code = """public class Foo { }
using System;
"""
        issues = validate_cs_syntax(code)
        warnings = [i for i in issues if i["code"] == "CS_USING_POSITION"]
        assert len(warnings) >= 1

    def test_using_at_top_ok(self):
        code = """using UnityEngine;
using System;

public class Foo { }
"""
        issues = validate_cs_syntax(code)
        warnings = [i for i in issues if i["code"] == "CS_USING_POSITION"]
        assert len(warnings) == 0

    def test_duplicate_type_names(self):
        code = """public class Foo { }
public class Foo { }
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] == "CS_DUPLICATE_TYPE"]
        assert len(errors) >= 1

    def test_duplicate_type_different_kinds(self):
        code = """public class Foo { }
public struct Foo { }
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] == "CS_DUPLICATE_TYPE"]
        assert len(errors) >= 1

    def test_no_duplicate_types_different_names(self):
        code = """public class Foo { }
public class Bar { }
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["code"] == "CS_DUPLICATE_TYPE"]
        assert len(errors) == 0

    def test_missing_semicolon_on_return(self):
        code = """public class Foo {
    int Get() {
        return 42
    }
}
"""
        issues = validate_cs_syntax(code)
        warnings = [i for i in issues if i["code"] == "CS_MISSING_SEMICOLON"]
        assert len(warnings) >= 1

    def test_missing_semicolon_on_var(self):
        code = """public class Foo {
    void Start() {
        var x = 5
    }
}
"""
        issues = validate_cs_syntax(code)
        warnings = [i for i in issues if i["code"] == "CS_MISSING_SEMICOLON"]
        assert len(warnings) >= 1

    def test_comment_does_not_affect_braces(self):
        code = """// { this is a comment
public class Foo {
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_string_does_not_affect_braces(self):
        code = '''public class Foo {
    string s = "{ not a brace }";
}
'''
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_returns_list_of_dicts(self):
        code = "public class Foo { }"
        issues = validate_cs_syntax(code)
        assert isinstance(issues, list)
        for issue in issues:
            assert isinstance(issue, dict)
            assert "line" in issue
            assert "severity" in issue
            assert "message" in issue
            assert "code" in issue

    def test_empty_code(self):
        issues = validate_cs_syntax("")
        assert isinstance(issues, list)

    def test_multiline_comment_handled(self):
        code = """public class Foo {
    /* { this is
       a multiline comment } */
    void Start() { }
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_complex_valid_code(self):
        code = """using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

/// <summary>
/// Test class with various constructs.
/// </summary>
[InitializeOnLoad]
public class TestClass : EditorWindow
{
    private static readonly Dictionary<string, int> map = new Dictionary<string, int>();

    [MenuItem("Test/Menu")]
    public static void ShowWindow()
    {
        GetWindow<TestClass>("Test");
    }

    private void OnGUI()
    {
        if (GUILayout.Button("Click"))
        {
            for (int i = 0; i < 10; i++)
            {
                Debug.Log($"Item {i}");
            }
        }
    }
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_issue_has_line_number(self):
        code = """public class Foo {
public class Foo {
}
}
"""
        issues = validate_cs_syntax(code)
        dup_issues = [i for i in issues if i["code"] == "CS_DUPLICATE_TYPE"]
        assert len(dup_issues) >= 1
        assert dup_issues[0]["line"] == 2  # Second definition is on line 2

    def test_nested_classes_different_names_ok(self):
        code = """public class Outer {
    public class Inner { }
}
"""
        issues = validate_cs_syntax(code)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0


# ===========================================================================
# Cross-generator integration tests
# ===========================================================================


class TestCrossGeneratorIntegration:
    """Integration tests across all production pipeline generators."""

    def test_all_generators_return_dict(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            assert isinstance(result, dict), f"{gen.__name__} must return dict"
            assert "script_path" in result
            assert "script_content" in result
            assert "next_steps" in result

    def test_all_scripts_have_balanced_braces(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            assert _check_balanced_braces(result["script_content"]), \
                f"{gen.__name__} has unbalanced braces"

    def test_all_scripts_have_menu_items(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            assert "MenuItem" in result["script_content"], \
                f"{gen.__name__} missing MenuItem"
            assert "VeilBreakers/Pipeline/" in result["script_content"], \
                f"{gen.__name__} missing VeilBreakers/Pipeline/ menu path"

    def test_all_scripts_are_editor_scripts(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            assert "Editor" in result["script_path"], \
                f"{gen.__name__} not in Editor folder"
            assert result["script_path"].endswith(".cs"), \
                f"{gen.__name__} not a .cs file"

    def test_no_script_path_duplicates(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        paths = set()
        for gen in generators:
            result = gen()
            assert result["script_path"] not in paths, \
                f"Duplicate script_path: {result['script_path']}"
            paths.add(result["script_path"])

    def test_all_scripts_have_using_statements(self):
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            content = result["script_content"]
            assert "using UnityEngine;" in content, \
                f"{gen.__name__} missing UnityEngine using"
            assert "using UnityEditor;" in content, \
                f"{gen.__name__} missing UnityEditor using"

    def test_validate_own_output(self):
        """Each generated C# script should pass our offline syntax validator."""
        generators = [
            generate_compile_recovery_script,
            generate_conflict_detector_script,
            generate_pipeline_orchestrator_script,
            generate_art_style_validator_script,
            generate_build_smoke_test_script,
        ]
        for gen in generators:
            result = gen()
            issues = validate_cs_syntax(result["script_content"])
            errors = [i for i in issues if i["severity"] == "error"]
            assert len(errors) == 0, \
                f"{gen.__name__} fails own syntax validation: {errors}"

    def test_python_helpers_return_dicts(self):
        assert isinstance(
            check_name_conflicts({}, []),
            dict
        )
        assert isinstance(
            generate_pipeline_step_definitions(),
            dict
        )

    def test_validate_cs_syntax_returns_list(self):
        assert isinstance(validate_cs_syntax(""), list)
