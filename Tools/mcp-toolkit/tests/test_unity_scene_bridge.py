"""Scene bridge-first regression tests."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_setup_terrain_uses_bridge_first_helper_and_surfaces_execution_result(
    monkeypatch,
):
    """unity_scene should auto-execute the generated terrain script via VBBridge."""
    from veilbreakers_mcp.unity_tools import scene

    captured: dict = {}

    async def _fake_write(**kwargs):
        captured.update(kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": kwargs["action_name"],
                "bridge_executed": True,
                "bridge_result": {"status": "success", "executed": True},
                "execution_result": {"status": "success", "terrain_name": "VB_Terrain"},
                "next_steps": ["Auto-executed via VBBridge. Check execution_result and bridge_result above."],
            }
        )

    monkeypatch.setattr(
        scene,
        "_write_generated_editor_response",
        _fake_write,
        raising=False,
    )

    payload = json.loads(
        await scene.unity_scene(
            action="setup_terrain",
            heightmap_path="Assets/Terrain/heightmap.raw",
            alphamap_path="Assets/Terrain/alphamap.raw",
            terrain_size=[1000.0, 600.0, 1000.0],
            terrain_resolution=513,
            splatmap_layers=[
                {"texture_path": "Assets/Textures/grass.png", "tiling": 8.0},
                {"texture_path": "Assets/Textures/rock.png", "tiling": 8.0},
                {"texture_path": "Assets/Textures/mud.png", "tiling": 8.0},
                {"texture_path": "Assets/Textures/snow.png", "tiling": 8.0},
            ],
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["execution_result"]["terrain_name"] == "VB_Terrain"
    assert captured["menu_path"] == "VeilBreakers/Scene/Setup Terrain"
    assert captured["response_fields"]["heightmap_path"] == "Assets/Terrain/heightmap.raw"
    assert captured["response_fields"]["terrain_size"] == [1000.0, 600.0, 1000.0]


@pytest.mark.asyncio
async def test_create_blend_tree_uses_dynamic_menu_path_and_surfaces_bridge_payload(
    monkeypatch,
):
    """Animation-scene generation should route through the bridge with the dynamic menu path."""
    from veilbreakers_mcp.unity_tools import scene

    captured: dict = {}

    async def _fake_write(**kwargs):
        captured.update(kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": kwargs["action_name"],
                "bridge_executed": True,
                "bridge_result": {"status": "success", "executed": True},
                "execution_result": {"status": "success", "controller": "VB Run"},
            }
        )

    monkeypatch.setattr(
        scene,
        "_write_generated_editor_response",
        _fake_write,
        raising=False,
    )

    payload = json.loads(
        await scene.unity_scene(
            action="create_blend_tree",
            controller_name="VB Run",
            blend_type="speed_blend",
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["execution_result"]["controller"] == "VB Run"
    assert captured["menu_path"] == "VeilBreakers/Animation/Create Blend Tree/VB Run"
    assert captured["response_fields"]["controller_name"] == "VB Run"
    assert captured["response_fields"]["blend_type"] == "speed_blend"
