from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_unity_prefab_create_auto_executes_via_bridge(monkeypatch, tmp_path):
    from veilbreakers_mcp.shared.config import Settings
    from veilbreakers_mcp.unity_tools import prefab

    monkeypatch.setattr(
        prefab,
        "settings",
        Settings(unity_project_path=str(tmp_path)),
        raising=False,
    )

    captured: dict = {}

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": kwargs["action_name"],
                "script_path": str(tmp_path / "Assets/Editor/Generated/Prefab/VeilBreakers_CreatePrefab.cs"),
                "bridge_executed": True,
                "bridge_result": {"status": "success", "executed": True},
                "execution_result": {
                    "status": "success",
                    "action": kwargs["action_name"],
                    "created_prefab": "Assets/Prefabs/Test.prefab",
                },
                "result_file": "Temp/vb_result.json",
            }
        )

    monkeypatch.setattr(
        prefab,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    payload = json.loads(
        await prefab.unity_prefab(
            action="create",
            name="TestPrefab",
            prefab_type="prop",
            save_dir="Assets/Prefabs",
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["bridge_result"]["status"] == "success"
    assert payload["execution_result"]["created_prefab"] == "Assets/Prefabs/Test.prefab"
    assert payload["result_file"] == "Temp/vb_result.json"
    assert captured["menu_path"] == "VeilBreakers/Prefab/Create Prefab"
    assert captured["response_fields"]["name"] == "TestPrefab"
    assert captured["rel_path"].endswith("VeilBreakers_CreatePrefab.cs")


@pytest.mark.asyncio
async def test_unity_prefab_cloth_setup_uses_dynamic_menu_path(monkeypatch, tmp_path):
    from veilbreakers_mcp.shared.config import Settings
    from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier
    from veilbreakers_mcp.unity_tools import prefab

    monkeypatch.setattr(
        prefab,
        "settings",
        Settings(unity_project_path=str(tmp_path)),
        raising=False,
    )

    captured: dict = {}

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": kwargs["action_name"],
                "bridge_executed": True,
                "bridge_result": {"status": "success", "executed": True},
                "execution_result": {"status": "success", "cloth": "configured"},
                "result_file": "Temp/vb_result.json",
            }
        )

    monkeypatch.setattr(
        prefab,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    mesh_name = "Cape Rig 01"
    payload = json.loads(
        await prefab.unity_prefab(
            action="cloth_setup",
            name=mesh_name,
            cloth_type="cape",
            cloth_stiffness=0.75,
            cloth_damping=0.2,
        )
    )

    safe_name = sanitize_cs_identifier(mesh_name)
    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["execution_result"]["cloth"] == "configured"
    assert captured["menu_path"] == f"VeilBreakers/Character/Setup Cloth - {safe_name}"
    assert captured["response_fields"]["mesh_name"] == mesh_name
