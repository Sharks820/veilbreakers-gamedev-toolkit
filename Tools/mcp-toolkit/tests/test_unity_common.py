"""Tests for shared Unity tool helpers."""

from __future__ import annotations

import asyncio
import json

import pytest


class TestUnityWriteHelpers:
    """Regression tests for the shared Unity write boundary."""

    def test_strip_schema_titles_removes_nested_titles(self):
        """Schema title cleanup should recurse through dicts and arrays."""
        from veilbreakers_mcp.unity_tools import _common

        schema = {
            "title": "Root",
            "properties": {
                "child": {
                    "title": "Child",
                    "items": [{"title": "Nested"}],
                }
            },
        }

        _common._strip_schema_titles(schema)

        assert "title" not in schema
        assert "title" not in schema["properties"]["child"]
        assert "title" not in schema["properties"]["child"]["items"][0]

    def test_write_to_unity_rejects_empty_content(self, tmp_path, monkeypatch):
        """_write_to_unity should refuse to write blank generated files."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )

        with pytest.raises(ValueError, match="Refusing to write empty generated content"):
            _common._write_to_unity("   \n\t  ", "Assets/Editor/Generated/Test.cs")

    def test_handle_dict_template_surfaces_empty_script_error(self, tmp_path, monkeypatch):
        """_handle_dict_template should return an error JSON response for blank scripts."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )

        result = asyncio.run(
            _common._handle_dict_template(
                "demo_action",
                {
                    "script_content": "   ",
                    "script_path": "Assets/Editor/Generated/Demo.cs",
                    "next_steps": ["Should never be used"],
                },
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "error"
        assert "Refusing to write empty generated content" in payload["message"]

    def test_handle_dict_template_preserves_extra_metadata(self, tmp_path, monkeypatch):
        """Extra metadata from generators should survive helper normalization."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )

        result = asyncio.run(
            _common._handle_dict_template(
                "reviewer",
                {
                    "script_content": "public static class Demo {}",
                    "script_path": "Assets/Editor/Generated/Demo.cs",
                    "next_steps": ["Recompile"],
                    "semantic_tier_rule_ids": ["BUG-31"],
                    "review_scope_default": "production",
                },
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        assert payload["semantic_tier_rule_ids"] == ["BUG-31"]
        assert payload["review_scope_default"] == "production"

    def test_write_generated_editor_response_reads_bridge_execution_result(
        self, tmp_path, monkeypatch,
    ):
        """Bridge-backed helper should surface the Unity result payload."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )
        temp_dir = tmp_path / "Temp"
        temp_dir.mkdir()
        (temp_dir / "vb_result.json").write_text(
            json.dumps({"status": "success", "materials_created": 12}),
            encoding="utf-8",
        )

        async def _fake_bridge(_menu_path: str) -> dict:
            return {"status": "success", "executed": True}

        monkeypatch.setattr(
            _common,
            "_bridge_recompile_and_execute",
            _fake_bridge,
            raising=False,
        )

        result = asyncio.run(
            _common._write_generated_editor_response(
                action_name="create_master_materials",
                script_content="public static class Demo {}",
                rel_path="Assets/Editor/Generated/Demo.cs",
                menu_path="VeilBreakers/Quality/Generate Master Material Library",
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        assert payload["bridge_executed"] is True
        assert payload["execution_result"]["materials_created"] == 12
        assert "Auto-executed via VBBridge" in payload["next_steps"][0]

    def test_write_generated_editor_response_propagates_bridge_execution_errors(
        self, tmp_path, monkeypatch,
    ):
        """Bridge-backed helper should fail closed on Unity execution errors."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )
        temp_dir = tmp_path / "Temp"
        temp_dir.mkdir()
        (temp_dir / "vb_result.json").write_text(
            json.dumps({"status": "error", "message": "Shader missing"}),
            encoding="utf-8",
        )

        async def _fake_bridge(_menu_path: str) -> dict:
            return {"status": "success", "executed": True}

        monkeypatch.setattr(
            _common,
            "_bridge_recompile_and_execute",
            _fake_bridge,
            raising=False,
        )

        result = asyncio.run(
            _common._write_generated_editor_response(
                action_name="create_master_materials",
                script_content="public static class Demo {}",
                rel_path="Assets/Editor/Generated/Demo.cs",
                menu_path="VeilBreakers/Quality/Generate Master Material Library",
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "error"
        assert payload["message"] == "Shader missing"
        assert payload["execution_result"]["status"] == "error"

    def test_write_generated_editor_response_reads_custom_result_file(
        self, tmp_path, monkeypatch,
    ):
        """Bridge-backed helper should support non-default Unity temp result files."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )
        temp_dir = tmp_path / "Temp"
        temp_dir.mkdir()
        (temp_dir / "vb_build_results.json").write_text(
            json.dumps({"status": "success", "succeeded": 3, "failed": 0}),
            encoding="utf-8",
        )

        async def _fake_bridge(_menu_path: str) -> dict:
            return {"status": "success", "executed": True}

        monkeypatch.setattr(
            _common,
            "_bridge_recompile_and_execute",
            _fake_bridge,
            raising=False,
        )

        result = asyncio.run(
            _common._write_generated_editor_response(
                action_name="build_multi_platform",
                script_content="public static class Demo {}",
                rel_path="Assets/Editor/Generated/Demo.cs",
                menu_path="VeilBreakers/Build/Multi-Platform Build",
                result_file="Temp/vb_build_results.json",
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        assert payload["result_file"] == "Temp/vb_build_results.json"
        assert payload["execution_result"]["succeeded"] == 3

    @pytest.mark.asyncio
    async def test_unity_assets_move_uses_bridge_generation_helper(self, monkeypatch):
        """unity_assets should auto-execute generated asset scripts via bridge helper."""
        from veilbreakers_mcp.unity_tools import assets

        captured: dict = {}

        async def _fake_write(**kwargs):
            captured.update(kwargs)
            return json.dumps({"status": "success", "action": kwargs["action_name"]})

        monkeypatch.setattr(
            assets,
            "_write_generated_editor_response",
            _fake_write,
            raising=False,
        )

        payload = json.loads(
            await assets.unity_assets(
                action="move",
                asset_path="Assets/Props/Old.prefab",
                new_path="Assets/Props/New.prefab",
            )
        )

        assert payload["status"] == "success"
        assert captured["action_name"] == "move"
        assert captured["menu_path"] == "VeilBreakers/Assets/Move Asset"
        assert captured["rel_path"].endswith("VeilBreakers_MoveAsset.cs")

    @pytest.mark.asyncio
    async def test_unity_assets_auto_materials_forwards_master_material_path(self, monkeypatch):
        """unity_assets should forward master material inheritance hints to the generator."""
        from veilbreakers_mcp.unity_tools import assets

        captured: dict = {}

        async def _fake_write(**kwargs):
            captured.update(kwargs)
            return json.dumps({"status": "success", "action": kwargs["action_name"]})

        monkeypatch.setattr(
            assets,
            "_write_generated_editor_response",
            _fake_write,
            raising=False,
        )

        payload = json.loads(
            await assets.unity_assets(
                action="auto_materials",
                fbx_path="Assets/Models/hero.fbx",
                texture_dir="Assets/Textures/Hero",
                master_material_path="Assets/Data/Materials/MasterLibrary/wet_cliff.mat",
            )
        )

        assert payload["status"] == "success"
        assert captured["action_name"] == "auto_materials"
        assert captured["response_fields"]["master_material_path"] == "Assets/Data/Materials/MasterLibrary/wet_cliff.mat"
        assert "masterMaterialPath" in captured["script_content"]

    @pytest.mark.asyncio
    async def test_unity_assets_atomic_import_forwards_master_material_path(self, monkeypatch):
        """unity_assets should forward master material inheritance hints for atomic import."""
        from veilbreakers_mcp.unity_tools import assets

        captured: dict = {}

        async def _fake_write(**kwargs):
            captured.update(kwargs)
            return json.dumps({"status": "success", "action": kwargs["action_name"]})

        monkeypatch.setattr(
            assets,
            "_write_generated_editor_response",
            _fake_write,
            raising=False,
        )

        payload = json.loads(
            await assets.unity_assets(
                action="atomic_import",
                texture_paths=["Assets/Textures/albedo.png"],
                material_name="HeroSkin",
                fbx_path="Assets/Models/hero.fbx",
                master_material_path="Assets/Data/Materials/MasterLibrary/stone_rough.mat",
            )
        )

        assert payload["status"] == "success"
        assert captured["action_name"] == "atomic_import"
        assert captured["response_fields"]["master_material_path"] == "Assets/Data/Materials/MasterLibrary/stone_rough.mat"
        assert "masterMaterialPath" in captured["script_content"]

    @pytest.mark.asyncio
    async def test_unity_quality_uses_bridge_generation_helper(self, monkeypatch):
        """unity_quality should auto-execute generated audit/material scripts via bridge helper."""
        from veilbreakers_mcp.unity_tools import quality

        captured: dict = {}

        async def _fake_write(**kwargs):
            captured.update(kwargs)
            return json.dumps({"status": "success", "action": kwargs["action_name"]})

        monkeypatch.setattr(
            quality,
            "_write_generated_editor_response",
            _fake_write,
            raising=False,
        )

        payload = json.loads(
            await quality.unity_quality(
                action="create_master_materials",
                output_folder="Assets/Data/Materials/AAA",
                materials=[{
                    "name": "wet_cliff",
                    "color_hex": "445566",
                    "metallic": 0.0,
                    "roughness": 0.82,
                    "normal_strength": 1.4,
                }],
            )
        )

        assert payload["status"] == "success"
        assert captured["action_name"] == "create_master_materials"
        assert captured["menu_path"] == "VeilBreakers/Quality/Generate Master Material Library"
        assert captured["response_fields"]["output_folder"] == "Assets/Data/Materials/AAA"
