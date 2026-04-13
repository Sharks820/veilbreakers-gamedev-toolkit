from __future__ import annotations

import importlib
import json
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs, expected_menu_path, expected_script_path, expected_fields",
    [
        (
            {
                "action": "configure_physics",
                "collision_matrix": {"Player": ["Default"]},
                "gravity": [0.0, -9.81, 0.0],
            },
            "VeilBreakers/Settings/Configure Physics",
            "Assets/Editor/Generated/Settings/VeilBreakers_ConfigurePhysics.cs",
            {},
        ),
        (
            {
                "action": "create_physics_material",
                "material_name": "CliffMud",
                "friction": 0.65,
                "bounciness": 0.05,
            },
            "VeilBreakers/Settings/Create Physics Material",
            "Assets/Editor/Generated/Settings/VeilBreakers_CreatePhysicsMaterial.cs",
            {"material_name": "CliffMud"},
        ),
        (
            {
                "action": "configure_player",
                "company": "VeilBreakers",
                "product": "DarkWorld",
                "color_space": "Linear",
                "scripting_backend": "IL2CPP",
                "api_level": "NET_Standard",
            },
            "VeilBreakers/Settings/Configure Player Settings",
            "Assets/Editor/Generated/Settings/VeilBreakers_PlayerSettings.cs",
            {},
        ),
        (
            {
                "action": "configure_build",
                "scenes": ["Assets/Scenes/Main.unity"],
                "platform": "StandaloneWindows64",
                "defines": ["ENABLE_DEBUG"],
            },
            "VeilBreakers/Settings/Configure Build Settings",
            "Assets/Editor/Generated/Settings/VeilBreakers_BuildSettings.cs",
            {},
        ),
        (
            {
                "action": "configure_quality",
                "quality_levels": [
                    {"name": "Low", "shadow_distance": 20},
                    {"name": "High", "shadow_distance": 120},
                ],
            },
            "VeilBreakers/Settings/Configure Quality Settings",
            "Assets/Editor/Generated/Settings/VeilBreakers_QualitySettings.cs",
            {"levels_count": 2},
        ),
        (
            {
                "action": "install_package",
                "package_id": "com.unity.inputsystem",
                "version": "1.7.0",
                "source": "upm",
            },
            "VeilBreakers/Settings/Install Package",
            "Assets/Editor/Generated/Settings/VeilBreakers_InstallPackage.cs",
            {"package_id": "com.unity.inputsystem", "source": "upm"},
        ),
        (
            {
                "action": "remove_package",
                "package_id": "com.unity.cinemachine",
            },
            "VeilBreakers/Settings/Remove Package",
            "Assets/Editor/Generated/Settings/VeilBreakers_RemovePackage.cs",
            {"package_id": "com.unity.cinemachine"},
        ),
        (
            {
                "action": "manage_tags_layers",
                "tags": ["Player", "Enemy"],
                "layers": ["Gameplay", "FX"],
                "sorting_layers": ["Foreground", "Background"],
            },
            "VeilBreakers/Settings/Manage Tags & Layers",
            "Assets/Editor/Generated/Settings/VeilBreakers_TagsLayers.cs",
            {},
        ),
        (
            {
                "action": "sync_tags_layers",
                "constants_cs_path": "Assets/Scripts/Generated/Constants.cs",
            },
            "VeilBreakers/Settings/Sync Tags & Layers from Code",
            "Assets/Editor/Generated/Settings/VeilBreakers_SyncTagsLayers.cs",
            {"constants_path": "Assets/Scripts/Generated/Constants.cs"},
        ),
        (
            {
                "action": "configure_time",
                "fixed_timestep": 0.0166667,
                "maximum_timestep": 0.1,
                "time_scale": 1.0,
            },
            "VeilBreakers/Settings/Configure Time Settings",
            "Assets/Editor/Generated/Settings/VeilBreakers_TimeSettings.cs",
            {},
        ),
        (
            {
                "action": "configure_graphics",
                "render_pipeline_path": "Assets/RenderPipelines/URP.asset",
                "fog_mode": "Exponential",
                "fog_color": [0.08, 0.09, 0.11, 1.0],
                "fog_density": 0.015,
            },
            "VeilBreakers/Settings/Configure Graphics Settings",
            "Assets/Editor/Generated/Settings/VeilBreakers_GraphicsSettings.cs",
            {},
        ),
    ],
)
async def test_unity_settings_actions_use_bridge_first(
    monkeypatch,
    kwargs,
    expected_menu_path,
    expected_script_path,
    expected_fields,
):
    settings_mod = importlib.import_module("veilbreakers_mcp.unity_tools.settings")

    captured: dict = {}

    async def _fake_write(**call_kwargs):
        captured.update(call_kwargs)
        return json.dumps({"status": "success", "action": call_kwargs["action_name"]})

    monkeypatch.setattr(
        settings_mod,
        "_write_generated_editor_response",
        AsyncMock(side_effect=_fake_write),
        raising=False,
    )

    payload = json.loads(await settings_mod.unity_settings(**kwargs))

    assert payload["status"] == "success"
    assert payload["action"] == kwargs["action"]
    assert captured["menu_path"] == expected_menu_path
    assert captured["rel_path"] == expected_script_path
    for key, value in expected_fields.items():
        assert captured["response_fields"][key] == value


@pytest.mark.asyncio
async def test_unity_settings_configure_quality_missing_levels_short_circuits(monkeypatch):
    settings_mod = importlib.import_module("veilbreakers_mcp.unity_tools.settings")

    bridge = AsyncMock(side_effect=AssertionError("bridge should not be called"))
    monkeypatch.setattr(
        settings_mod,
        "_write_generated_editor_response",
        bridge,
        raising=False,
    )

    payload = json.loads(
        await settings_mod.unity_settings(
            action="configure_quality",
            quality_levels=None,
        )
    )

    assert payload["status"] == "error"
    assert payload["action"] == "configure_quality"
    assert "quality_levels" in payload["message"]
    bridge.assert_not_awaited()


@pytest.mark.asyncio
async def test_unity_settings_configure_build_generator_error_short_circuits(monkeypatch):
    settings_mod = importlib.import_module("veilbreakers_mcp.unity_tools.settings")

    bridge = AsyncMock(side_effect=AssertionError("bridge should not be called"))
    monkeypatch.setattr(
        settings_mod,
        "_write_generated_editor_response",
        bridge,
        raising=False,
    )

    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("invalid build scene list")

    monkeypatch.setattr(
        settings_mod,
        "generate_build_settings_script",
        _raise_value_error,
        raising=False,
    )

    payload = json.loads(
        await settings_mod.unity_settings(
            action="configure_build",
            scenes=["Assets/Scenes/Broken.unity"],
        )
    )

    assert payload["status"] == "error"
    assert payload["action"] == "configure_build"
    assert "invalid build scene list" in payload["message"]
    bridge.assert_not_awaited()
