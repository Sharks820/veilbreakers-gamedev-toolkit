"""Unit tests for blender_server.py MCP tool registration.

Tests cover:
- Module imports without error
- MCP tool count is 11
- Each new compound tool is registered
"""

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

    def test_tool_count_is_11(self):
        """MCP server should have exactly 11 tools registered."""
        tool_count = len(mcp._tool_manager._tools)
        assert tool_count == 11, (
            f"Expected 11 tools, got {tool_count}. "
            f"Registered tools: {sorted(mcp._tool_manager._tools.keys())}"
        )


class TestNewToolsRegistered:
    """Test that each new compound tool is registered."""

    def test_blender_texture_registered(self):
        """blender_texture tool is registered in the MCP server."""
        assert "blender_texture" in mcp._tool_manager._tools

    def test_asset_pipeline_registered(self):
        """asset_pipeline tool is registered in the MCP server."""
        assert "asset_pipeline" in mcp._tool_manager._tools

    def test_concept_art_registered(self):
        """concept_art tool is registered in the MCP server."""
        assert "concept_art" in mcp._tool_manager._tools

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
