from __future__ import annotations

import json

import pytest


def _bridge_ok(
    action_name: str,
    *,
    bridge_executed: bool = True,
    result_file: str = "Temp/vb_result.json",
) -> str:
    return json.dumps(
        {
            "status": "success",
            "action": action_name,
            "script_path": f"/tmp/{action_name}.cs",
            "bridge_executed": bridge_executed,
            "bridge_result": {"status": "success", "executed": bridge_executed},
            "execution_result": {"status": "success", "action": action_name},
            "result_file": result_file,
        }
    )


@pytest.mark.asyncio
async def test_build_multi_platform_routes_through_bridge_helper(monkeypatch):
    from veilbreakers_mcp.unity_tools import build

    captured: dict = {}

    monkeypatch.setattr(
        build,
        "generate_multi_platform_build_script",
        lambda **kwargs: "MULTI_PLATFORM_SCRIPT",
        raising=False,
    )

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return _bridge_ok(kwargs["action_name"], bridge_executed=True)

    monkeypatch.setattr(build, "_write_build_editor_response", fake_write, raising=False)

    payload = json.loads(
        await build.unity_build(
            action="build_multi_platform",
            platforms=[{"name": "Windows", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP"}],
        )
    )

    assert payload["status"] == "success"
    assert captured["menu_path"] == "VeilBreakers/Build/Multi-Platform Build"
    assert captured["result_file"] == "Temp/vb_build_results.json"
    assert captured["response_fields"]["development"] is False
    assert captured["response_fields"]["platforms"][0]["name"] == "Windows"


@pytest.mark.asyncio
async def test_configure_addressables_routes_through_bridge_helper(monkeypatch):
    from veilbreakers_mcp.unity_tools import build

    captured: dict = {}

    monkeypatch.setattr(
        build,
        "generate_addressables_config_script",
        lambda **kwargs: "ADDRESSABLES_SCRIPT",
        raising=False,
    )

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return _bridge_ok(kwargs["action_name"], bridge_executed=True)

    monkeypatch.setattr(build, "_write_build_editor_response", fake_write, raising=False)

    payload = json.loads(
        await build.unity_build(
            action="configure_addressables",
            groups=[{"name": "Default", "packing": "PackSeparately", "local": True}],
            build_remote=True,
        )
    )

    assert payload["status"] == "success"
    assert captured["menu_path"] == "VeilBreakers/Build/Configure Addressables"
    assert captured["response_fields"]["build_remote"] is True
    assert captured["response_fields"]["groups"][0]["name"] == "Default"


@pytest.mark.asyncio
async def test_manage_version_writes_changelog_and_fails_when_bridge_fails(
    monkeypatch,
    tmp_path,
):
    from veilbreakers_mcp.unity_tools import build

    captured: dict = {"writes": []}

    monkeypatch.setattr(
        build,
        "generate_changelog",
        lambda **kwargs: "CHANGELOG_SCRIPT",
        raising=False,
    )
    monkeypatch.setattr(
        build,
        "generate_version_management_script",
        lambda **kwargs: "VERSION_SCRIPT",
        raising=False,
    )

    def fake_write_to_unity(content, rel_path):
        captured["writes"].append((rel_path, content))
        return str(tmp_path / rel_path)

    async def fake_write(**kwargs):
        captured["bridge"] = kwargs
        return json.dumps(
            {
                "status": "error",
                "action": kwargs["action_name"],
                "script_path": str(tmp_path / "Assets/Editor/Generated/Build/VBVersionManager.cs"),
                "bridge_executed": True,
                "bridge_result": {"status": "error", "message": "compile failed"},
                "execution_result": {"status": "error", "message": "compile failed"},
                "result_file": "Temp/vb_result.json",
            }
        )

    monkeypatch.setattr(build, "_write_to_unity", fake_write_to_unity, raising=False)
    monkeypatch.setattr(build, "_write_build_editor_response", fake_write, raising=False)

    payload = json.loads(
        await build.unity_build(
            action="manage_version",
            version="2.3.4",
            auto_increment="patch",
        )
    )

    assert payload["status"] == "error"
    assert payload["changelog_path"] == str(tmp_path / "Assets/Editor/Generated/Build/VBChangelogGenerator.cs")
    assert payload["changelog_menu_path"] == "VeilBreakers/Build/Generate Changelog"
    assert captured["bridge"]["menu_path"] == "VeilBreakers/Build/Bump Version"
    assert captured["writes"] == [
        (
            "Assets/Editor/Generated/Build/VBChangelogGenerator.cs",
            "CHANGELOG_SCRIPT",
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform, expected_menu_path, bridge_executed",
    [
        ("android", "VeilBreakers/Build/Configure Android", True),
        ("webgl", "VeilBreakers/Build/Configure WebGL", True),
        ("ios", "", False),
    ],
)
async def test_configure_platform_routes_menu_items_through_shared_helper(
    monkeypatch,
    platform,
    expected_menu_path,
    bridge_executed,
):
    from veilbreakers_mcp.unity_tools import build

    captured: dict = {}

    monkeypatch.setattr(
        build,
        "generate_platform_config_script",
        lambda **kwargs: "PLATFORM_SCRIPT",
        raising=False,
    )

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return _bridge_ok(kwargs["action_name"], bridge_executed=bridge_executed)

    monkeypatch.setattr(build, "_write_build_editor_response", fake_write, raising=False)

    payload = json.loads(
        await build.unity_build(
            action="configure_platform",
            platform=platform,
        )
    )

    assert payload["status"] == "success"
    assert captured["response_fields"]["platform"] == platform
    assert captured["menu_path"] == expected_menu_path
    assert payload["bridge_executed"] is bridge_executed


@pytest.mark.asyncio
async def test_setup_shader_stripping_uses_shared_helper_without_menu_item(monkeypatch):
    from veilbreakers_mcp.unity_tools import build

    captured: dict = {}

    monkeypatch.setattr(
        build,
        "generate_shader_stripping_script",
        lambda **kwargs: "SHADER_STRIP_SCRIPT",
        raising=False,
    )

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return _bridge_ok(
            kwargs["action_name"],
            bridge_executed=False,
            result_file="Temp/vb_shader_strip_results.json",
        )

    monkeypatch.setattr(build, "_write_build_editor_response", fake_write, raising=False)

    payload = json.loads(
        await build.unity_build(
            action="setup_shader_stripping",
            keywords_to_strip=["DEBUG", "_EDITOR"],
            log_stripping=True,
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is False
    assert payload["result_file"] == "Temp/vb_shader_strip_results.json"
    assert captured.get("menu_path", "") == ""
    assert captured["result_file"] == "Temp/vb_shader_strip_results.json"
    assert captured["response_fields"]["keywords_to_strip"] == ["DEBUG", "_EDITOR"]
