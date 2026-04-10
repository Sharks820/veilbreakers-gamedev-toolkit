"""Tests for Unity bridge GameObject handlers and unity_gameobject MCP tool.

Covers:
- 16 new bridge handler registrations in generate_bridge_commands_script()
- Undo support for all mutating handlers
- Depth limits, result caps, assembly-scanning type resolution
- _try_bridge importability from _common
- unity_gameobject tool structure, action routing, bridge-only error handling
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_bridge_commands_script,
)


# =====================================================================
# Task 1: Bridge handler C# generation tests
# =====================================================================


class TestBridgeCommandsTemplate:
    """Verify all 26 handlers (10 existing + 16 new) in generated C#."""

    @pytest.fixture(autouse=True)
    def _generate_cs(self):
        self.cs = generate_bridge_commands_script()

    # --- 10 original handlers still present ---

    ORIGINAL_HANDLERS = [
        "ping", "recompile", "execute_menu_item", "enter_play_mode",
        "exit_play_mode", "screenshot", "console_logs", "read_result",
        "get_game_objects", "check_compile_status",
    ]

    @pytest.mark.parametrize("handler_key", ORIGINAL_HANDLERS)
    def test_original_handler_registered(self, handler_key):
        assert f'["{handler_key}"]' in self.cs

    # --- 16 new handlers ---

    NEW_HANDLER_KEYS = [
        "create_gameobject", "delete_gameobject", "duplicate_gameobject",
        "reparent_gameobject", "set_transform", "update_gameobject",
        "find_gameobjects", "get_components", "add_component",
        "remove_component", "get_hierarchy", "get_scene_info",
        "save_scene", "undo", "redo", "instantiate_prefab",
    ]

    @pytest.mark.parametrize("handler_key", NEW_HANDLER_KEYS)
    def test_new_handler_registered(self, handler_key):
        assert f'["{handler_key}"]' in self.cs

    NEW_HANDLER_METHODS = [
        "HandleCreateGameObject", "HandleDeleteGameObject",
        "HandleDuplicateGameObject", "HandleReparentGameObject",
        "HandleSetTransform", "HandleUpdateGameObject",
        "HandleFindGameObjects", "HandleGetComponents",
        "HandleAddComponent", "HandleRemoveComponent",
        "HandleGetHierarchy", "HandleGetSceneInfo",
        "HandleSaveScene", "HandleUndo", "HandleRedo",
        "HandleInstantiatePrefab",
    ]

    @pytest.mark.parametrize("method_name", NEW_HANDLER_METHODS)
    def test_new_handler_method_exists(self, method_name):
        assert method_name in self.cs

    def test_total_handler_count(self):
        """26 total handler registrations in HANDLERS dict."""
        all_keys = self.ORIGINAL_HANDLERS + self.NEW_HANDLER_KEYS
        for key in all_keys:
            assert f'["{key}"]' in self.cs, f"Missing handler: {key}"

    # --- Undo support ---

    def test_undo_register_created_object(self):
        """create, duplicate, instantiate_prefab use RegisterCreatedObjectUndo."""
        count = self.cs.count("Undo.RegisterCreatedObjectUndo")
        assert count >= 3, f"Expected 3+ RegisterCreatedObjectUndo, got {count}"

    def test_undo_record_object(self):
        """set_transform, update, reparent use Undo.RecordObject."""
        count = self.cs.count("Undo.RecordObject")
        assert count >= 3, f"Expected 3+ Undo.RecordObject, got {count}"

    def test_undo_destroy_object(self):
        """delete_gameobject uses Undo.DestroyObjectImmediate."""
        assert "Undo.DestroyObjectImmediate" in self.cs

    # --- Safety features ---

    def test_get_hierarchy_max_depth(self):
        """get_hierarchy handler checks max_depth parameter."""
        assert "max_depth" in self.cs

    def test_find_gameobjects_result_cap(self):
        """find_gameobjects caps results at 1000."""
        assert "1000" in self.cs

    def test_add_component_assembly_scanning(self):
        """add_component uses AppDomain.CurrentDomain.GetAssemblies() for type resolution."""
        assert "AppDomain.CurrentDomain.GetAssemblies" in self.cs

    # --- Helpers ---

    def test_get_hierarchy_path_helper(self):
        """GetHierarchyPath helper exists."""
        assert "GetHierarchyPath" in self.cs

    def test_find_gameobject_by_path_helper(self):
        """FindGameObjectByPath helper exists."""
        assert "FindGameObjectByPath" in self.cs

    def test_resolve_type_helper(self):
        """ResolveType helper exists."""
        assert "ResolveType" in self.cs

    # --- Using directives ---

    def test_uses_scene_management(self):
        assert "using UnityEditor.SceneManagement" in self.cs

    def test_uses_linq(self):
        assert "using System.Linq" in self.cs


class TestTryBridgeImportable:
    """_try_bridge must be importable from _common."""

    def test_try_bridge_from_common(self):
        from veilbreakers_mcp.unity_tools._common import _try_bridge
        assert callable(_try_bridge)

    def test_try_bridge_from_editor(self):
        """editor.py still exports _try_bridge for backward compat."""
        from veilbreakers_mcp.unity_tools.editor import _try_bridge
        assert callable(_try_bridge)


# =====================================================================
# Task 2: unity_gameobject MCP tool tests
# =====================================================================


class TestUnityGameObjectTool:
    """Verify unity_gameobject tool structure and routing."""

    def test_importable(self):
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject
        assert callable(unity_gameobject)

    def test_action_literal_has_16_values(self):
        import typing
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject

        hints = typing.get_type_hints(unity_gameobject)
        action_type = hints["action"]
        args = typing.get_args(action_type)
        assert len(args) == 16, f"Expected 16 action values, got {len(args)}: {args}"

    EXPECTED_ACTIONS = [
        "create", "delete", "duplicate", "reparent",
        "set_transform", "update", "find",
        "get_components", "add_component", "remove_component",
        "get_hierarchy", "get_scene_info", "save_scene",
        "undo", "redo", "instantiate_prefab",
    ]

    @pytest.mark.parametrize("action", EXPECTED_ACTIONS)
    def test_action_in_literal(self, action):
        import typing
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject

        hints = typing.get_type_hints(unity_gameobject)
        args = typing.get_args(hints["action"])
        assert action in args

    @pytest.mark.asyncio
    async def test_bridge_not_connected_returns_error(self):
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject

        with patch(
            "veilbreakers_mcp.unity_tools.gameobject._try_bridge",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result_str = await unity_gameobject(action="create", name="TestObj")
            result = json.loads(result_str)
            assert result["status"] == "error"
            assert "VBBridge" in result["message"]

    ACTION_TO_BRIDGE = {
        "create": "create_gameobject",
        "delete": "delete_gameobject",
        "duplicate": "duplicate_gameobject",
        "reparent": "reparent_gameobject",
        "set_transform": "set_transform",
        "update": "update_gameobject",
        "find": "find_gameobjects",
        "get_components": "get_components",
        "add_component": "add_component",
        "remove_component": "remove_component",
        "get_hierarchy": "get_hierarchy",
        "get_scene_info": "get_scene_info",
        "save_scene": "save_scene",
        "undo": "undo",
        "redo": "redo",
        "instantiate_prefab": "instantiate_prefab",
    }

    @pytest.mark.parametrize("action,bridge_cmd", list(ACTION_TO_BRIDGE.items()))
    @pytest.mark.asyncio
    async def test_action_routes_to_bridge_command(self, action, bridge_cmd):
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject

        mock_bridge = AsyncMock(return_value={"ok": True})
        with patch(
            "veilbreakers_mcp.unity_tools.gameobject._try_bridge",
            mock_bridge,
        ):
            await unity_gameobject(action=action)
            mock_bridge.assert_called_once()
            actual_cmd = mock_bridge.call_args[0][0]
            assert actual_cmd == bridge_cmd, (
                f"action={action} should route to '{bridge_cmd}', got '{actual_cmd}'"
            )

    def test_module_registered_in_init(self):
        """gameobject module is registered in unity_tools __init__."""
        import veilbreakers_mcp.unity_tools as ut
        assert hasattr(ut, "gameobject") or "gameobject" in dir(ut)

    def test_tool_count_at_least_23(self):
        """After registration, mcp should have >= 23 tools."""
        from veilbreakers_mcp.unity_tools import mcp
        tools = getattr(mcp, "_tool_manager", None)
        tool_dict = getattr(tools, "_tools", {})
        assert len(tool_dict) >= 23, f"Expected >= 23 tools, got {len(tool_dict)}"
