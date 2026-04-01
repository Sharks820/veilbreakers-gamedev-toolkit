"""Integration tests for the Tripo pipeline blank-texture bug fix.

Verifies that cleanup_ai_model routes to the correct texture step depending
on whether has_extracted_textures is set.  All Blender TCP calls are mocked.
"""

from __future__ import annotations

from unittest import mock

import pytest

from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_runner():
    """Return a PipelineRunner with a fully mocked BlenderConnection."""
    blender = mock.AsyncMock()
    blender.send_command = mock.AsyncMock(return_value={"status": "ok"})
    settings = mock.MagicMock()

    runner = PipelineRunner(blender, settings)
    return runner, blender


# ---------------------------------------------------------------------------
# Test 1: without extracted textures, texture_create_pbr is called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_calls_create_pbr_when_no_extracted_textures():
    """cleanup_ai_model calls texture_create_pbr when has_extracted_textures=False."""
    runner, blender = _make_runner()

    await runner.cleanup_ai_model("MyProp", has_extracted_textures=False)

    called_commands = [call.args[0] for call in blender.send_command.call_args_list]
    assert "texture_create_pbr" in called_commands, (
        f"Expected texture_create_pbr in calls, got: {called_commands}"
    )
    assert "texture_load_extracted_textures" not in called_commands


# ---------------------------------------------------------------------------
# Test 2: with extracted textures, texture_load_extracted_textures is called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_calls_load_extracted_textures_when_flag_set():
    """cleanup_ai_model calls texture_load_extracted_textures when has_extracted_textures=True."""
    runner, blender = _make_runner()

    channels = {
        "albedo": "/tmp/textures/albedo.png",
        "orm": "/tmp/textures/orm.png",
        "normal": "/tmp/textures/normal.png",
    }

    await runner.cleanup_ai_model(
        "MyProp",
        has_extracted_textures=True,
        texture_channels=channels,
    )

    called_commands = [call.args[0] for call in blender.send_command.call_args_list]
    assert "texture_load_extracted_textures" in called_commands, (
        f"Expected texture_load_extracted_textures, got: {called_commands}"
    )
    assert "texture_create_pbr" not in called_commands, (
        "texture_create_pbr must NOT be called when extracted textures are present"
    )


# ---------------------------------------------------------------------------
# Test 3: albedo_delit preferred over albedo when present in channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_prefers_albedo_delit_path():
    """cleanup_ai_model sends albedo_delit_path (not albedo_path) when both present."""
    runner, blender = _make_runner()

    channels = {
        "albedo": "/tmp/textures/albedo.png",
        "albedo_delit": "/tmp/textures/albedo_delit.png",
        "orm": "/tmp/textures/orm.png",
    }

    await runner.cleanup_ai_model(
        "MyProp",
        has_extracted_textures=True,
        texture_channels=channels,
    )

    # Find the call to texture_load_extracted_textures
    tex_calls = [
        call for call in blender.send_command.call_args_list
        if call.args[0] == "texture_load_extracted_textures"
    ]
    assert len(tex_calls) == 1, "Expected exactly one texture_load_extracted_textures call"

    params = tex_calls[0].args[1]
    assert "albedo_delit_path" in params, "albedo_delit_path should be in params"
    assert "albedo_path" not in params, "raw albedo_path should NOT be sent when delit is present"
    assert params["albedo_delit_path"] == "/tmp/textures/albedo_delit.png"


# ---------------------------------------------------------------------------
# Test 4: has_extracted_textures=True but texture_channels=None falls back to create_pbr
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_falls_back_to_create_pbr_when_channels_none():
    """cleanup_ai_model falls back to texture_create_pbr if texture_channels is None."""
    runner, blender = _make_runner()

    await runner.cleanup_ai_model(
        "MyProp",
        has_extracted_textures=True,
        texture_channels=None,  # No channels provided despite flag
    )

    called_commands = [call.args[0] for call in blender.send_command.call_args_list]
    assert "texture_create_pbr" in called_commands, (
        "Should fall back to texture_create_pbr when texture_channels is None"
    )


# ---------------------------------------------------------------------------
# Test 5: all standard pipeline steps still run with extracted textures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_runs_all_standard_steps_with_extracted_textures():
    """cleanup_ai_model still runs repair, game_check, UV unwrap when using extracted textures."""
    runner, blender = _make_runner()

    channels = {"albedo": "/tmp/albedo.png", "orm": "/tmp/orm.png"}

    result = await runner.cleanup_ai_model(
        "MyProp",
        has_extracted_textures=True,
        texture_channels=channels,
    )

    called_commands = [call.args[0] for call in blender.send_command.call_args_list]

    # Core pipeline steps must still execute
    assert "mesh_auto_repair" in called_commands, "Repair step must run"
    assert "mesh_check_game_ready" in called_commands, "Game-check step must run"
    assert "uv_unwrap_xatlas" in called_commands, "UV unwrap must run"
    assert "texture_load_extracted_textures" in called_commands, "Texture wiring must run"

    assert result["status"] == "success"
