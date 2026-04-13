from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_unity_performance_profile_scene_auto_executes_via_bridge(monkeypatch, tmp_path):
    from veilbreakers_mcp.shared.config import Settings
    from veilbreakers_mcp.unity_tools import performance

    monkeypatch.setattr(
        performance,
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
                "execution_result": {
                    "status": "success",
                    "frame_time_ms": 12.5,
                },
                "result_file": "Temp/vb_result.json",
            }
        )

    monkeypatch.setattr(
        performance,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    payload = json.loads(
        await performance.unity_performance(
            action="profile_scene",
            target_frame_time_ms=16.67,
            max_draw_calls=1200,
            max_batches=900,
            max_triangles=1500000,
            max_memory_mb=1536.0,
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["execution_result"]["frame_time_ms"] == 12.5
    assert captured["menu_path"] == "VeilBreakers/Performance/Profile Scene"
    assert captured["response_fields"]["budgets"]["draw_calls"] == 1200
    assert captured["rel_path"].endswith("VeilBreakers_SceneProfiler.cs")


@pytest.mark.asyncio
async def test_unity_performance_automate_build_includes_bridge_payload(monkeypatch, tmp_path):
    from veilbreakers_mcp.shared.config import Settings
    from veilbreakers_mcp.unity_tools import performance

    monkeypatch.setattr(
        performance,
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
                "execution_result": {
                    "status": "success",
                    "build_target": kwargs["response_fields"]["build_target"],
                },
                "result_file": "Temp/vb_result.json",
            }
        )

    monkeypatch.setattr(
        performance,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    payload = json.loads(
        await performance.unity_performance(
            action="automate_build",
            build_target="StandaloneWindows64",
            scenes=["Assets/Scenes/Main.unity"],
            build_options="Development",
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["execution_result"]["build_target"] == "StandaloneWindows64"
    assert captured["menu_path"] == "VeilBreakers/Performance/Build With Report"
    assert captured["response_fields"]["scenes"] == ["Assets/Scenes/Main.unity"]
