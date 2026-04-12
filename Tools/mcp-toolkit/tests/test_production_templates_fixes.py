"""Tests for F360-F381 compound tool bug fixes in production_templates.py.

Validates:
- Orchestrator theater fix: ExecuteCurrentStep no longer auto-succeeds
- Step command file written for MCP bridge consumption
- Result polling with timeout mechanism
- StepCommand serialization
"""

import pytest

from veilbreakers_mcp.shared.unity_templates.production_templates import (
    generate_pipeline_orchestrator_script,
    generate_pipeline_step_definitions,
    PIPELINE_DEFINITIONS,
    ALL_PIPELINES,
)


# ---------------------------------------------------------------------------
# F360-F365: Orchestrator theater fix
# ---------------------------------------------------------------------------


class TestOrchestratorNoTheater:
    """The orchestrator must NOT auto-succeed every step."""

    def test_no_auto_succeed_pattern(self):
        """CompleteStep(true, null) should not appear as the default execution path."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        # The old theater pattern was: delayCall += () => { CompleteStep(true, null); }
        # This should no longer exist as the primary execution path
        assert "// For now, mark as success and advance" not in content

    def test_no_simulate_comment(self):
        """The 'simulate' comment from the theater implementation should be gone."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "// Simulate step execution" not in content

    def test_writes_step_command_file(self):
        """ExecuteCurrentStep should write a command file for MCP bridge."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "vb_pipeline_step_cmd.json" in content

    def test_checks_result_file(self):
        """ExecuteCurrentStep should poll for vb_result.json."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "vb_result.json" in content

    def test_timeout_mechanism(self):
        """Steps should have a timeout that triggers failure."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "timed out" in content

    def test_step_command_has_tool_field(self):
        """StepCommand should include the tool name."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "step.Tool" in content

    def test_step_command_has_action_field(self):
        """StepCommand should include the action name."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "step.Action" in content

    def test_deletes_old_result_before_step(self):
        """Should delete existing result file before running a new step."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "File.Delete(resultPath)" in content

    def test_parses_result_status(self):
        """Should check result JSON for success/failure status."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert '"status": "success"' in content or '\\"status\\": \\"success\\"' in content


# ---------------------------------------------------------------------------
# F366-F370: Pipeline definitions remain correct
# ---------------------------------------------------------------------------


class TestPipelineDefinitionsIntact:
    """Pipeline definitions should still be correct after the fix."""

    def test_all_pipelines_present(self):
        expected = {"create_character", "create_level", "create_item", "full_build"}
        assert set(ALL_PIPELINES) == expected

    def test_each_pipeline_has_steps(self):
        for name, pdef in PIPELINE_DEFINITIONS.items():
            assert "steps" in pdef, f"{name} missing steps"
            assert len(pdef["steps"]) > 0, f"{name} has no steps"

    def test_each_step_has_required_fields(self):
        for pname, pdef in PIPELINE_DEFINITIONS.items():
            for step in pdef["steps"]:
                assert "name" in step, f"{pname} step missing name"
                assert "tool" in step, f"{pname} step missing tool"
                assert "action" in step, f"{pname} step missing action"
                assert "timeout" in step, f"{pname} step missing timeout"

    def test_step_definitions_helper(self):
        result = generate_pipeline_step_definitions()
        assert "pipelines" in result
        assert "dependency_graph" in result
        assert result["total_pipeline_count"] == len(PIPELINE_DEFINITIONS)


# ---------------------------------------------------------------------------
# F371-F375: Orchestrator script structure
# ---------------------------------------------------------------------------


class TestOrchestratorStructure:
    """The orchestrator script should have proper C# structure."""

    def test_output_structure(self):
        result = generate_pipeline_orchestrator_script()
        assert "script_path" in result
        assert "script_content" in result
        assert "next_steps" in result
        assert result["script_path"].endswith(".cs")

    def test_contains_step_status_enum(self):
        result = generate_pipeline_orchestrator_script()
        assert "StepStatus" in result["script_content"]

    def test_contains_failure_mode_enum(self):
        result = generate_pipeline_orchestrator_script()
        assert "FailureMode" in result["script_content"]

    def test_contains_complete_step_method(self):
        result = generate_pipeline_orchestrator_script()
        assert "CompleteStep" in result["script_content"]

    def test_contains_finish_pipeline_method(self):
        result = generate_pipeline_orchestrator_script()
        assert "FinishPipeline" in result["script_content"]

    def test_retry_logic_present(self):
        result = generate_pipeline_orchestrator_script(on_failure="retry")
        content = result["script_content"]
        assert "RetryCount" in content
        assert "MaxStepRetries" in content

    def test_custom_steps(self):
        steps = [
            {"name": "my_step", "tool": "unity_editor", "action": "recompile", "timeout": 60},
        ]
        result = generate_pipeline_orchestrator_script(steps=steps)
        assert "my_step" in result["script_content"]

    def test_custom_failure_mode(self):
        result = generate_pipeline_orchestrator_script(on_failure="continue")
        assert "FailureMode.Continue" in result["script_content"]

    def test_step_command_class_present(self):
        """StepCommand data class should be defined for serialization."""
        result = generate_pipeline_orchestrator_script()
        content = result["script_content"]
        assert "class StepCommand" in content


# ---------------------------------------------------------------------------
# F376-F381: Built-in pipelines embedded in orchestrator
# ---------------------------------------------------------------------------


class TestBuiltinPipelinesInOrchestrator:
    """Built-in pipelines should be embedded in the generated C# script."""

    def test_create_character_embedded(self):
        result = generate_pipeline_orchestrator_script()
        assert "create_character" in result["script_content"]

    def test_create_level_embedded(self):
        result = generate_pipeline_orchestrator_script()
        assert "create_level" in result["script_content"]

    def test_full_build_embedded(self):
        result = generate_pipeline_orchestrator_script()
        assert "full_build" in result["script_content"]

    def test_load_pipeline_method(self):
        result = generate_pipeline_orchestrator_script()
        assert "LoadPipeline" in result["script_content"]

    def test_pipeline_report_class(self):
        result = generate_pipeline_orchestrator_script()
        assert "PipelineReport" in result["script_content"]

    def test_eta_estimation(self):
        result = generate_pipeline_orchestrator_script()
        assert "EstimateRemainingMs" in result["script_content"]
