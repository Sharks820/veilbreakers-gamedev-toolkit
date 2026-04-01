"""Tests for world streaming templates -- setup_map_streaming action.

Validates the C# editor script generation for Addressable groups, static flags,
and occlusion baking from a scene hierarchy JSON manifest.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hierarchy_file(tmp_path: str, objects: list[dict] | None = None) -> str:
    """Write a minimal scene hierarchy JSON and return its path."""
    hierarchy = {
        "map_name": "TestMap",
        "generated_at": "2026-04-01T12:00:00Z",
        "objects": objects or [
            {"name": "TestMap_Terrain", "type": "MESH", "district": "", "world_position": [0, 0, 0], "world_rotation_euler": [0, 0, 0], "world_scale": [1, 1, 1]},
            {"name": "Village_Mesh", "type": "MESH", "district": "town", "world_position": [50, 50, 0], "world_rotation_euler": [0, 0, 0], "world_scale": [1, 1, 1]},
            {"name": "Keep_Mesh", "type": "MESH", "district": "castle", "world_position": [100, 100, 0], "world_rotation_euler": [0, 0, 0], "world_scale": [1, 1, 1]},
        ],
    }
    path = os.path.join(tmp_path, "scene_hierarchy.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(hierarchy, fh, indent=2)
    return path


def _make_mock_write():
    """Return a function that captures C# source without writing to disk."""
    captured = {}

    def mock_write(cs_source: str, rel_path: str) -> str:
        captured["source"] = cs_source
        captured["path"] = rel_path
        return rel_path

    return mock_write, captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupMapStreaming:

    @pytest.mark.asyncio
    async def test_returns_error_when_json_missing(self):
        from veilbreakers_mcp.unity_tools.world import _handle_setup_map_streaming
        result = await _handle_setup_map_streaming("TestMap", "/nonexistent/path.json", "")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["message"]

    @pytest.mark.asyncio
    async def test_generates_valid_csharp(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, captured = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            result = await world_mod._handle_setup_map_streaming(
                "TestMap", hierarchy_path, "",
            )
            data = json.loads(result)
            assert data["status"] == "success"
            source = captured["source"]
            assert "using UnityEditor" in source
            assert "AddressableAssetGroup" in source
            assert "Execute()" in source
            assert "TestMap" in source
        finally:
            world_mod._write_to_unity = original

    @pytest.mark.asyncio
    async def test_includes_addressable_groups(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, captured = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            await world_mod._handle_setup_map_streaming("TestMap", hierarchy_path, "")
            source = captured["source"]
            assert "town" in source or "castle" in source
            assert "CreateOrGetGroup" in source
        finally:
            world_mod._write_to_unity = original

    @pytest.mark.asyncio
    async def test_sets_static_flags_for_buildings(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, captured = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            await world_mod._handle_setup_map_streaming("TestMap", hierarchy_path, "")
            source = captured["source"]
            assert "SetStaticEditorFlags" in source
            assert "OccluderStatic" in source
        finally:
            world_mod._write_to_unity = original

    @pytest.mark.asyncio
    async def test_calls_occlusion_compute(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, captured = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            await world_mod._handle_setup_map_streaming("TestMap", hierarchy_path, "")
            source = captured["source"]
            assert "StaticOcclusionCulling.Compute" in source
        finally:
            world_mod._write_to_unity = original

    @pytest.mark.asyncio
    async def test_groups_created_in_response(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, _ = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            result = await world_mod._handle_setup_map_streaming("TestMap", hierarchy_path, "")
            data = json.loads(result)
            assert "groups_created" in data
            assert isinstance(data["groups_created"], list)
            assert data["object_count"] == 3
        finally:
            world_mod._write_to_unity = original

    @pytest.mark.asyncio
    async def test_namespace_applied(self, tmp_path):
        from veilbreakers_mcp.unity_tools import world as world_mod
        hierarchy_path = _make_hierarchy_file(str(tmp_path))
        mock_write, captured = _make_mock_write()
        original = world_mod._write_to_unity
        world_mod._write_to_unity = mock_write
        try:
            await world_mod._handle_setup_map_streaming("TestMap", hierarchy_path, "Streaming")
            source = captured["source"]
            assert "VeilBreakers.World.Streaming" in source
        finally:
            world_mod._write_to_unity = original
