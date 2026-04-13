from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "expected_menu_path", "expected_field_name", "expected_field_value"),
    [
        (
            {
                "action": "create_sprite_atlas",
                "atlas_name": "Hero Atlas",
                "source_folder": "Assets/Sprites/Hero",
                "output_path": "Assets/SpriteAtlases/Hero.spriteatlas",
            },
            "VeilBreakers/Assets/Create HeroAtlas Atlas",
            "atlas_name",
            "HeroAtlas",
        ),
        (
            {
                "action": "create_sprite_animation",
                "clip_name": "Run Cycle",
                "sprite_folder": "Assets/Sprites/Run",
                "output_path": "Assets/Animations/Run.anim",
            },
            "VeilBreakers/Assets/Create RunCycle Animation",
            "clip_name",
            "RunCycle",
        ),
        (
            {
                "action": "configure_sprite_editor",
                "sprite_path": "Assets/Sprites/Hero.png",
                "pivot": [0.5, 0.5],
                "border": [4, 4, 4, 4],
                "custom_physics_shape": [],
            },
            "VeilBreakers/Assets/Configure Sprite Hero",
            "sprite_path",
            "Assets/Sprites/Hero.png",
        ),
    ],
)
async def test_unity_pipeline_menu_item_actions_use_bridge_first_helper(
    monkeypatch,
    kwargs,
    expected_menu_path,
    expected_field_name,
    expected_field_value,
):
    from veilbreakers_mcp.unity_tools import pipeline

    captured: dict = {}

    async def fake_write(**helper_kwargs):
        captured.update(helper_kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": helper_kwargs["action_name"],
                "script_path": "/tmp/generated.cs",
                "bridge_executed": True,
                "bridge_result": {"status": "success", "executed": True},
                "execution_result": {"status": "success", "tool": helper_kwargs["action_name"]},
                "result_file": "Temp/vb_result.json",
                **helper_kwargs["response_fields"],
            }
        )

    monkeypatch.setattr(
        pipeline,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    payload = json.loads(await pipeline.unity_pipeline(**kwargs))

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is True
    assert payload["result_file"] == "Temp/vb_result.json"
    assert payload[expected_field_name] == expected_field_value
    assert captured["menu_path"] == expected_menu_path
    assert captured["response_fields"][expected_field_name] == expected_field_value
    assert captured["rel_path"].startswith("Assets/Editor/Generated/Pipeline/")


@pytest.mark.asyncio
async def test_create_asset_postprocessor_uses_shared_helper_without_bridge(monkeypatch):
    from veilbreakers_mcp.unity_tools import pipeline

    captured: dict = {}

    async def fake_write(**helper_kwargs):
        captured.update(helper_kwargs)
        return json.dumps(
            {
                "status": "success",
                "action": helper_kwargs["action_name"],
                "script_path": "/tmp/generated.cs",
                "bridge_executed": False,
                "next_steps": helper_kwargs["next_steps"],
                "processor_name": helper_kwargs["response_fields"]["processor_name"],
            }
        )

    monkeypatch.setattr(
        pipeline,
        "_write_generated_editor_response",
        fake_write,
        raising=False,
    )

    payload = json.loads(
        await pipeline.unity_pipeline(
            action="create_asset_postprocessor",
            processor_name="Import Rules",
            texture_rules=[{"folder": "Assets/Textures"}],
        )
    )

    assert payload["status"] == "success"
    assert payload["bridge_executed"] is False
    assert payload["processor_name"] == "ImportRules"
    assert captured["menu_path"] == ""
    assert captured["result_file"] is None
    assert captured["next_steps"] == [
        "Recompile: unity_editor action=recompile",
        "Reimport matching assets to apply the generated AssetPostprocessor rules",
    ]


@pytest.mark.asyncio
async def test_configure_git_lfs_remains_file_write_path(monkeypatch, tmp_path):
    from veilbreakers_mcp.shared.config import Settings
    from veilbreakers_mcp.unity_tools import pipeline

    monkeypatch.setattr(
        pipeline,
        "settings",
        Settings(unity_project_path=str(tmp_path)),
        raising=False,
    )

    helper_called = False

    async def fail_if_called(**_kwargs):
        nonlocal helper_called
        helper_called = True
        raise AssertionError("_write_generated_editor_response should not be used for git LFS")

    written_paths: list[str] = []

    def fake_write(content: str, relative_path: str) -> str:
        written_paths.append(relative_path)
        return str(tmp_path / relative_path)

    monkeypatch.setattr(
        pipeline,
        "_write_generated_editor_response",
        fail_if_called,
        raising=False,
    )
    monkeypatch.setattr(pipeline, "_write_to_unity", fake_write, raising=False)
    monkeypatch.setattr(
        pipeline,
        "generate_gitlfs_config",
        lambda **_kwargs: "# git lfs config",
        raising=False,
    )
    monkeypatch.setattr(
        pipeline,
        "generate_gitignore",
        lambda **_kwargs: "# gitignore",
        raising=False,
    )

    payload = json.loads(
        await pipeline.unity_pipeline(
            action="configure_git_lfs",
            extra_extensions=["psd"],
            extra_patterns=["Library/"],
        )
    )

    assert helper_called is False
    assert payload["status"] == "success"
    assert payload["gitattributes_path"].endswith(".gitattributes")
    assert payload["gitignore_path"].endswith(".gitignore")
    assert written_paths == [".gitattributes", ".gitignore"]
