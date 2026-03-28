"""Unit tests for blender_server.py MCP tool registration.

Tests cover:
- Module imports without error
- MCP tool count is 15
- Each compound tool is registered (including blender_environment, blender_worldbuilding)
"""

import pytest

from veilbreakers_mcp.blender_server import mcp


class TestBlenderServerModuleImports:
    """Test that the blender_server module loads without errors."""

    def test_module_imports_without_error(self):
        """Importing blender_server should not raise."""
        # The import at module level already validates this;
        # this test makes the assertion explicit.
        assert mcp is not None


class TestMCPToolCount:
    """Test that the correct number of tools are registered."""

    def test_tool_count(self):
        """MCP server should have exactly 16 tools registered (15 original + blender_quality)."""
        tool_count = len(mcp._tool_manager._tools)
        assert tool_count == 16, (
            f"Expected 16 tools, got {tool_count}. "
            f"Registered tools: {sorted(mcp._tool_manager._tools.keys())}"
        )


class TestNewToolsRegistered:
    """Test that each compound tool is registered."""

    def test_blender_texture_registered(self):
        """blender_texture tool is registered in the MCP server."""
        assert "blender_texture" in mcp._tool_manager._tools

    def test_asset_pipeline_registered(self):
        """asset_pipeline tool is registered in the MCP server."""
        assert "asset_pipeline" in mcp._tool_manager._tools

    def test_concept_art_registered(self):
        """concept_art tool is registered in the MCP server."""
        assert "concept_art" in mcp._tool_manager._tools

    def test_blender_rig_registered(self):
        """blender_rig tool is registered in the MCP server."""
        assert "blender_rig" in mcp._tool_manager._tools

    def test_blender_animation_registered(self):
        """blender_animation tool is registered in the MCP server."""
        assert "blender_animation" in mcp._tool_manager._tools

    def test_blender_environment_registered(self):
        """blender_environment tool is registered in the MCP server."""
        assert "blender_environment" in mcp._tool_manager._tools

    def test_blender_worldbuilding_registered(self):
        """blender_worldbuilding tool is registered in the MCP server."""
        assert "blender_worldbuilding" in mcp._tool_manager._tools

    def test_existing_tools_still_registered(self):
        """All 8 original tools are still registered."""
        expected = [
            "blender_scene",
            "blender_object",
            "blender_material",
            "blender_viewport",
            "blender_execute",
            "blender_export",
            "blender_mesh",
            "blender_uv",
        ]
        for tool_name in expected:
            assert tool_name in mcp._tool_manager._tools, (
                f"Original tool '{tool_name}' should still be registered"
            )


class TestTerrainHeightFallback:
    """Regression tests for best-effort terrain height sampling."""

    @pytest.mark.asyncio
    async def test_sample_terrain_height_returns_zero_on_connection_error(self):
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        class _FakeBlender:
            async def send_command(self, *_args, **_kwargs):
                raise ConnectionError("offline")

        result = await _sample_terrain_height(
            _FakeBlender(),
            "Terrain",
            12.5,
            30.0,
        )

        assert result == 0.0
