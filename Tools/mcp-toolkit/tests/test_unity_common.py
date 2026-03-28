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
