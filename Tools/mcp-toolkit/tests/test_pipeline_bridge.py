"""Unit tests for PipelineRunner.blender_to_unity_pipeline().

Tests the Blender-side orchestration helper that chains game_check, repair,
UV analyze/unwrap, and export into a single async call. Uses AsyncMock to
simulate BlenderConnection responses without a live Blender instance.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_TMP_UNITY_PROJECT = str(Path(tempfile.gettempdir()) / "UnityProject")

from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_runner(command_responses=None):
    """Create a PipelineRunner with a mocked BlenderConnection.

    Args:
        command_responses: Dict mapping command names to return dicts.
            Defaults to a happy-path set of responses.
    """
    defaults = {
        "mesh_check_game_ready": {
            "game_ready": True,
            "grade": "A",
            "checks": {
                "poly_budget": {"passed": True, "value": 5000},
            },
        },
        "mesh_auto_repair": {"status": "success", "fixed": 2},
        "mesh_retopologize": {"status": "success", "final_faces": 8000},
        "uv_analyze": {"coverage": 0.95, "uv_layers": 1},
        "uv_unwrap_xatlas": {"status": "success", "coverage": 0.98},
        "export_fbx": {"status": "success", "filepath": "hero.fbx"},
        "export_gltf": {"status": "success", "filepath": "hero.glb"},
    }
    if command_responses:
        defaults.update(command_responses)

    blender = MagicMock()

    async def mock_send(cmd, params=None):
        if cmd in defaults:
            return defaults[cmd]
        return {"status": "success"}

    blender.send_command = AsyncMock(side_effect=mock_send)

    settings = MagicMock()
    return PipelineRunner(blender, settings)


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Tests: blender_to_unity_pipeline
# ---------------------------------------------------------------------------


class TestBlenderToUnityPipeline:
    """Tests for PipelineRunner.blender_to_unity_pipeline()."""

    def test_returns_dict(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert isinstance(result, dict)

    def test_success_status_on_happy_path(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["status"] == "success"

    def test_contains_fbx_path(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["fbx_path"] != ""
        assert "Hero" in result["fbx_path"]

    def test_contains_mesh_grade(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["mesh_grade"] == "A"

    def test_contains_poly_count(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["poly_count"] == 5000

    def test_contains_uv_coverage(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["uv_coverage"] == 0.95

    def test_game_check_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "game_check" in result["steps"]

    def test_export_step_recorded(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "export" in result["steps"]

    def test_no_repair_when_game_ready(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "repair" not in result["steps"]

    def test_repair_when_not_game_ready(self):
        runner = _make_runner({
            "mesh_check_game_ready": {
                "game_ready": False,
                "grade": "D",
                "checks": {
                    "poly_budget": {"passed": True, "value": 5000},
                },
            },
        })
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "repair" in result["steps"]
        assert any("repair" in w.lower() for w in result["warnings"])

    def test_retopologize_when_over_budget(self):
        runner = _make_runner({
            "mesh_check_game_ready": {
                "game_ready": False,
                "grade": "F",
                "checks": {
                    "poly_budget": {"passed": False, "value": 200000},
                },
            },
        })
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "retopologize" in result["steps"]

    def test_no_retopologize_when_within_budget(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "retopologize" not in result["steps"]

    def test_uv_unwrap_when_no_uvs(self):
        runner = _make_runner({
            "uv_analyze": {"coverage": 0.0, "uv_layers": 0},
        })
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "uv_unwrap" in result["steps"]
        assert any("unwrap" in w.lower() for w in result["warnings"])

    def test_no_uv_unwrap_when_good_coverage(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert "uv_unwrap" not in result["steps"]

    def test_uv_coverage_updated_after_unwrap(self):
        runner = _make_runner({
            "uv_analyze": {"coverage": 0.0, "uv_layers": 0},
            "uv_unwrap_xatlas": {"status": "success", "coverage": 0.97},
        })
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["uv_coverage"] == 0.97

    def test_asset_type_prop_default(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Chair"))
        assert result["asset_type"] == "prop"

    def test_asset_type_hero(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero", asset_type="hero"))
        assert result["asset_type"] == "hero"

    def test_export_format_fbx_default(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["fbx_path"].endswith(".fbx")

    def test_export_format_gltf(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline(
            "Hero", export_format="gltf"
        ))
        assert result["fbx_path"].endswith(".glb")

    def test_export_to_unity_project_path(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline(
            "Hero", unity_project_path=_TMP_UNITY_PROJECT
        ))
        assert "Assets" in result["fbx_path"]
        assert "Models" in result["fbx_path"]

    def test_object_name_in_result(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("DarkKnight"))
        assert result["object_name"] == "DarkKnight"

    def test_warnings_is_list(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert isinstance(result["warnings"], list)

    def test_failed_status_on_connection_error(self):
        runner = _make_runner()
        runner.blender.send_command = AsyncMock(
            side_effect=ConnectionError("Blender not running")
        )
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["status"] == "failed"
        assert "error" in result

    def test_failed_status_on_timeout(self):
        runner = _make_runner()
        runner.blender.send_command = AsyncMock(
            side_effect=TimeoutError("Connection timed out")
        )
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["status"] == "failed"

    def test_failed_status_on_blender_command_error(self):
        from veilbreakers_mcp.shared.blender_client import BlenderCommandError
        from veilbreakers_mcp.shared.models import BlenderResponse

        mock_response = BlenderResponse(
            status="error",
            message="Object not found",
            error_type="NOT_FOUND",
        )
        runner = _make_runner()
        runner.blender.send_command = AsyncMock(
            side_effect=BlenderCommandError(mock_response)
        )
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert result["status"] == "failed"
        assert "Object not found" in result["error"]

    def test_poly_budget_hero_is_65000(self):
        """Hero assets should use 65000 poly budget."""
        runner = _make_runner()
        _run(runner.blender_to_unity_pipeline("Hero", asset_type="hero"))
        # Verify game_check was called with correct budget
        calls = runner.blender.send_command.call_args_list
        game_check_call = [c for c in calls if c[0][0] == "mesh_check_game_ready"]
        assert len(game_check_call) == 1
        assert game_check_call[0][0][1]["poly_budget"] == 65000

    def test_poly_budget_weapon_is_15000(self):
        """Weapon assets should use 15000 poly budget."""
        runner = _make_runner()
        _run(runner.blender_to_unity_pipeline("Sword", asset_type="weapon"))
        calls = runner.blender.send_command.call_args_list
        game_check_call = [c for c in calls if c[0][0] == "mesh_check_game_ready"]
        assert game_check_call[0][0][1]["poly_budget"] == 15000

    def test_poly_budget_environment_is_100000(self):
        """Environment assets should use 100000 poly budget."""
        runner = _make_runner()
        _run(runner.blender_to_unity_pipeline("Terrain", asset_type="environment"))
        calls = runner.blender.send_command.call_args_list
        game_check_call = [c for c in calls if c[0][0] == "mesh_check_game_ready"]
        assert game_check_call[0][0][1]["poly_budget"] == 100000

    def test_steps_dict_populated(self):
        runner = _make_runner()
        result = _run(runner.blender_to_unity_pipeline("Hero"))
        assert isinstance(result["steps"], dict)
        assert len(result["steps"]) >= 3  # game_check, uv_analyze, export

    def test_export_calls_export_fbx_command(self):
        runner = _make_runner()
        _run(runner.blender_to_unity_pipeline("Hero", export_format="fbx"))
        calls = runner.blender.send_command.call_args_list
        export_calls = [c for c in calls if c[0][0] == "export_fbx"]
        assert len(export_calls) == 1

    def test_export_calls_export_gltf_command(self):
        runner = _make_runner()
        _run(runner.blender_to_unity_pipeline("Hero", export_format="gltf"))
        calls = runner.blender.send_command.call_args_list
        export_calls = [c for c in calls if c[0][0] == "export_gltf"]
        assert len(export_calls) == 1
