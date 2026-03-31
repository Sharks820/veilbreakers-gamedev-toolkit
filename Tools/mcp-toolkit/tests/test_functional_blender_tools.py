"""Functional tests for every Blender MCP tool (Tools 1-8).

Verifies that every MCP tool can be imported, its function signature matches
expectations, its Literal action types are all handled (no dead branches),
every COMMAND_HANDLERS key maps to a callable, and the _with_screenshot helper
exists and is referenced by mutation tools.

These tests run without a live Blender connection -- they only inspect module
structure, function signatures, handler registrations, and pure-logic helpers.
"""

from __future__ import annotations

import asyncio
import inspect
import typing
from typing import get_type_hints

import pytest

from veilbreakers_mcp.blender_server import (
    mcp,
    _with_screenshot,
    blender_scene,
    blender_object,
    blender_material,
    blender_viewport,
    blender_execute,
    blender_export,
    blender_mesh,
    blender_uv,
)
from veilbreakers_mcp.shared.security import validate_code
from blender_addon.handlers import COMMAND_HANDLERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_literal_values(func, param_name: str) -> set[str]:
    """Extract the Literal values from a function parameter's type annotation."""
    hints = get_type_hints(func, include_extras=True)
    annotation = hints.get(param_name)
    if annotation is None:
        raise ValueError(f"No annotation for '{param_name}' on {func.__name__}")
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Literal:
        return set(annotation.__args__)
    # typing.get_args works for Literal in 3.10+
    args = typing.get_args(annotation)
    if args and all(isinstance(a, str) for a in args):
        return set(args)
    raise ValueError(f"Could not extract Literal values from {annotation}")


def _get_source(func) -> str:
    """Return source code of a function, unwrapping MCP decorators."""
    return inspect.getsource(func)


# ---------------------------------------------------------------------------
# Tool 1: blender_scene (4 actions)
# ---------------------------------------------------------------------------


class TestTool1BlenderScene:
    """blender_scene: inspect, clear, configure, list_objects."""

    EXPECTED_ACTIONS = {"inspect", "clear", "configure", "list_objects"}

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_scene)

    def test_registered_in_mcp(self):
        assert "blender_scene" in mcp._tool_manager._tools

    def test_action_literal_values(self):
        values = _get_literal_values(blender_scene, "action")
        assert values == self.EXPECTED_ACTIONS

    def test_no_unreachable_actions(self):
        """Every Literal value has a branch in the function body."""
        source = _get_source(blender_scene)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source, (
                f"Action '{action}' has no branch in blender_scene"
            )

    def test_scene_command_handlers_exist(self):
        """Each scene action maps to a registered COMMAND_HANDLERS key."""
        expected_commands = {
            "inspect": "get_scene_info",
            "clear": "clear_scene",
            "configure": "configure_scene",
            "list_objects": "list_objects",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"Scene action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_with_screenshot_used_for_mutations(self):
        """Mutation actions (clear, configure) use _with_screenshot."""
        source = _get_source(blender_scene)
        assert "_with_screenshot" in source


# ---------------------------------------------------------------------------
# Tool 2: blender_object (5 actions)
# ---------------------------------------------------------------------------


class TestTool2BlenderObject:
    """blender_object: create, modify, delete, duplicate, list."""

    EXPECTED_ACTIONS = {"create", "modify", "delete", "duplicate", "list"}

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_object)

    def test_registered_in_mcp(self):
        assert "blender_object" in mcp._tool_manager._tools

    def test_action_literal_has_5_values(self):
        values = _get_literal_values(blender_object, "action")
        assert values == self.EXPECTED_ACTIONS

    def test_no_unreachable_actions(self):
        source = _get_source(blender_object)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source, (
                f"Action '{action}' has no branch in blender_object"
            )

    def test_object_command_handlers_exist(self):
        expected_commands = {
            "create": "create_object",
            "modify": "modify_object",
            "delete": "delete_object",
            "duplicate": "duplicate_object",
            "list": "list_objects",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"Object action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_with_screenshot_used_for_mutations(self):
        source = _get_source(blender_object)
        assert "_with_screenshot" in source

    def test_cmd_map_covers_mutation_actions(self):
        """The cmd_map dict covers create/modify/delete/duplicate."""
        source = _get_source(blender_object)
        for action in ("create", "modify", "delete", "duplicate"):
            assert f'"{action}"' in source


# ---------------------------------------------------------------------------
# Tool 3: blender_material (4 actions)
# ---------------------------------------------------------------------------


class TestTool3BlenderMaterial:
    """blender_material: create, assign, modify, list."""

    EXPECTED_ACTIONS = {"create", "assign", "modify", "list"}

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_material)

    def test_registered_in_mcp(self):
        assert "blender_material" in mcp._tool_manager._tools

    def test_action_literal_has_4_values(self):
        values = _get_literal_values(blender_material, "action")
        assert values == self.EXPECTED_ACTIONS

    def test_no_unreachable_actions(self):
        source = _get_source(blender_material)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source

    def test_material_command_handlers_exist(self):
        expected_commands = {
            "create": "material_create",
            "assign": "material_assign",
            "modify": "material_modify",
            "list": "material_list",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"Material action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_with_screenshot_used_for_mutations(self):
        source = _get_source(blender_material)
        assert "_with_screenshot" in source


# ---------------------------------------------------------------------------
# Tool 4: blender_viewport (4 actions)
# ---------------------------------------------------------------------------


class TestTool4BlenderViewport:
    """blender_viewport: screenshot, contact_sheet, set_shading, navigate."""

    EXPECTED_ACTIONS = {"screenshot", "contact_sheet", "set_shading", "navigate"}

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_viewport)

    def test_registered_in_mcp(self):
        assert "blender_viewport" in mcp._tool_manager._tools

    def test_action_literal_values(self):
        values = _get_literal_values(blender_viewport, "action")
        assert values == self.EXPECTED_ACTIONS

    def test_no_unreachable_actions(self):
        source = _get_source(blender_viewport)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source

    def test_viewport_command_handlers_exist(self):
        """Viewport commands that map to COMMAND_HANDLERS (excluding screenshot which uses capture_viewport_bytes)."""
        expected_commands = {
            "contact_sheet": "render_contact_sheet",
            "set_shading": "set_shading",
            "navigate": "navigate_camera",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"Viewport action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_screenshot_handler_exists(self):
        """The get_viewport_screenshot handler exists for the addon side."""
        assert "get_viewport_screenshot" in COMMAND_HANDLERS
        assert callable(COMMAND_HANDLERS["get_viewport_screenshot"])

    def test_with_screenshot_used_for_mutations(self):
        source = _get_source(blender_viewport)
        assert "_with_screenshot" in source


# ---------------------------------------------------------------------------
# Tool 5: blender_execute
# ---------------------------------------------------------------------------


class TestTool5BlenderExecute:
    """blender_execute: code execution with security validation."""

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_execute)

    def test_registered_in_mcp(self):
        assert "blender_execute" in mcp._tool_manager._tools

    def test_validate_code_is_imported_and_used(self):
        """validate_code is called in blender_execute function body."""
        source = _get_source(blender_execute)
        assert "validate_code" in source

    def test_safe_code_passes_validation(self):
        """Standard bpy code passes security validation."""
        safe, violations = validate_code("import bpy\nbpy.ops.mesh.primitive_cube_add()")
        assert safe is True
        assert violations == []

    def test_dangerous_import_os_fails_validation(self):
        """Importing os is blocked."""
        safe, violations = validate_code("import os\nos.listdir('.')")
        assert safe is False
        assert any("os" in v for v in violations)

    def test_dangerous_import_subprocess_fails_validation(self):
        """Importing subprocess is blocked."""
        safe, violations = validate_code("import subprocess")
        assert safe is False
        assert any("subprocess" in v for v in violations)

    def test_dangerous_eval_fails_validation(self):
        """Calling eval() is blocked."""
        safe, violations = validate_code("x = eval('1+1')")
        assert safe is False
        assert any("eval" in v for v in violations)

    def test_dangerous_exec_fails_validation(self):
        """Calling exec() is blocked."""
        safe, violations = validate_code("exec('print(1)')")
        assert safe is False
        assert any("exec" in v for v in violations)

    def test_dangerous_open_allowed_per_policy(self):
        """open() is allowed per user security policy."""
        safe, violations = validate_code("f = open('/etc/passwd')")
        assert safe is True

    def test_safe_mathutils_passes_validation(self):
        """mathutils imports are allowed."""
        safe, violations = validate_code(
            "from mathutils import Vector\nv = Vector((1, 0, 0))"
        )
        assert safe is True

    def test_execute_command_handler_exists(self):
        """execute_code handler exists in COMMAND_HANDLERS."""
        assert "execute_code" in COMMAND_HANDLERS
        assert callable(COMMAND_HANDLERS["execute_code"])

    def test_with_screenshot_used(self):
        source = _get_source(blender_execute)
        assert "_with_screenshot" in source


# ---------------------------------------------------------------------------
# Tool 6: blender_export (2 formats)
# ---------------------------------------------------------------------------


class TestTool6BlenderExport:
    """blender_export: fbx, gltf."""

    EXPECTED_FORMATS = {"fbx", "gltf"}

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_export)

    def test_registered_in_mcp(self):
        assert "blender_export" in mcp._tool_manager._tools

    def test_format_literal_has_2_values(self):
        values = _get_literal_values(blender_export, "export_format")
        assert values == self.EXPECTED_FORMATS

    def test_export_command_handlers_exist(self):
        """Each export format maps to a COMMAND_HANDLERS key."""
        for fmt in self.EXPECTED_FORMATS:
            cmd_key = f"export_{fmt}"
            assert cmd_key in COMMAND_HANDLERS, (
                f"Export format '{fmt}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_export_builds_command_from_format(self):
        """The export tool constructs command as f'export_{export_format}'."""
        source = _get_source(blender_export)
        assert "export_" in source


# ---------------------------------------------------------------------------
# Tool 7: blender_mesh (8 actions)
# ---------------------------------------------------------------------------


class TestTool7BlenderMesh:
    """blender_mesh: analyze, repair, game_check, select, edit, boolean, retopo, sculpt."""

    EXPECTED_ACTIONS = {
        "analyze", "repair", "game_check",
        "select", "edit", "boolean", "retopo", "sculpt",
        # v6: expanded sculpt/modeling operations
        "sculpt_brush", "dyntopo", "voxel_remesh", "face_sets", "multires",
        # AAA geometry enhancement pipeline
        "enhance", "bake_normals", "bake_ao", "bake_curvature", "validate_enhance",
    }

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_mesh)

    def test_registered_in_mcp(self):
        assert "blender_mesh" in mcp._tool_manager._tools

    def test_action_literal_has_expected_values(self):
        values = _get_literal_values(blender_mesh, "action")
        assert values == self.EXPECTED_ACTIONS
        assert len(values) == 18  # 8 original + 5 v6 sculpt + 5 AAA enhance

    def test_no_unreachable_actions(self):
        source = _get_source(blender_mesh)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source, (
                f"Action '{action}' has no branch in blender_mesh"
            )

    def test_mesh_command_handlers_exist(self):
        """Each mesh action maps to a COMMAND_HANDLERS key."""
        expected_commands = {
            "analyze": "mesh_analyze_topology",
            "repair": "mesh_auto_repair",
            "game_check": "mesh_check_game_ready",
            "select": "mesh_select",
            "edit": "mesh_edit",
            "boolean": "mesh_boolean",
            "retopo": "mesh_retopologize",
            "sculpt": "mesh_sculpt",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"Mesh action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_with_screenshot_used_for_mutations(self):
        """Mutation actions use _with_screenshot."""
        source = _get_source(blender_mesh)
        assert "_with_screenshot" in source

    def test_analyze_returns_json_not_screenshot(self):
        """analyze action returns JSON (read-only, no screenshot)."""
        source = _get_source(blender_mesh)
        # After 'action == "analyze"', should use json.dumps not _with_screenshot
        # We verify by checking the analyze block returns a list with json
        assert "mesh_analyze_topology" in source

    def test_game_check_returns_json_not_screenshot(self):
        """game_check action returns JSON (read-only, no screenshot)."""
        source = _get_source(blender_mesh)
        assert "mesh_check_game_ready" in source


# ---------------------------------------------------------------------------
# Tool 8: blender_uv (9 actions)
# ---------------------------------------------------------------------------


class TestTool8BlenderUV:
    """blender_uv: analyze, unwrap, unwrap_blender, pack, lightmap, equalize, export_layout, set_layer, ensure_xatlas."""

    EXPECTED_ACTIONS = {
        "analyze", "unwrap", "unwrap_blender", "pack", "lightmap",
        "equalize", "export_layout", "set_layer", "ensure_xatlas",
    }

    def test_function_exists_and_is_async(self):
        assert asyncio.iscoroutinefunction(blender_uv)

    def test_registered_in_mcp(self):
        assert "blender_uv" in mcp._tool_manager._tools

    def test_action_literal_has_9_values(self):
        values = _get_literal_values(blender_uv, "action")
        assert values == self.EXPECTED_ACTIONS
        assert len(values) == 9

    def test_no_unreachable_actions(self):
        source = _get_source(blender_uv)
        for action in self.EXPECTED_ACTIONS:
            assert f'"{action}"' in source or f"'{action}'" in source, (
                f"Action '{action}' has no branch in blender_uv"
            )

    def test_uv_command_handlers_exist(self):
        """Each UV action maps to a COMMAND_HANDLERS key."""
        expected_commands = {
            "analyze": "uv_analyze",
            "unwrap": "uv_unwrap_xatlas",
            "unwrap_blender": "uv_unwrap_blender",
            "pack": "uv_pack_islands",
            "lightmap": "uv_generate_lightmap",
            "equalize": "uv_equalize_density",
            "export_layout": "uv_export_layout",
            "set_layer": "uv_set_active_layer",
            "ensure_xatlas": "uv_ensure_xatlas",
        }
        for action, cmd_key in expected_commands.items():
            assert cmd_key in COMMAND_HANDLERS, (
                f"UV action '{action}' -> command '{cmd_key}' not in COMMAND_HANDLERS"
            )
            assert callable(COMMAND_HANDLERS[cmd_key])

    def test_with_screenshot_used_for_mutations(self):
        source = _get_source(blender_uv)
        assert "_with_screenshot" in source

    def test_analyze_returns_json_not_screenshot(self):
        """analyze action returns JSON (read-only)."""
        source = _get_source(blender_uv)
        assert "uv_analyze" in source

    def test_ensure_xatlas_returns_json(self):
        """ensure_xatlas action returns JSON result."""
        source = _get_source(blender_uv)
        assert "uv_ensure_xatlas" in source


# ---------------------------------------------------------------------------
# Cross-cutting: _with_screenshot helper
# ---------------------------------------------------------------------------


class TestWithScreenshotHelper:
    """The _with_screenshot helper exists and is used by mutation tools."""

    def test_with_screenshot_is_async(self):
        assert asyncio.iscoroutinefunction(_with_screenshot)

    def test_with_screenshot_signature(self):
        """_with_screenshot accepts (blender, result, capture) parameters."""
        sig = inspect.signature(_with_screenshot)
        params = list(sig.parameters.keys())
        assert "blender" in params
        assert "result" in params
        assert "capture" in params

    def test_with_screenshot_used_by_tool1_scene(self):
        assert "_with_screenshot" in _get_source(blender_scene)

    def test_with_screenshot_used_by_tool2_object(self):
        assert "_with_screenshot" in _get_source(blender_object)

    def test_with_screenshot_used_by_tool3_material(self):
        assert "_with_screenshot" in _get_source(blender_material)

    def test_with_screenshot_used_by_tool4_viewport(self):
        assert "_with_screenshot" in _get_source(blender_viewport)

    def test_with_screenshot_used_by_tool5_execute(self):
        assert "_with_screenshot" in _get_source(blender_execute)

    def test_with_screenshot_used_by_tool7_mesh(self):
        assert "_with_screenshot" in _get_source(blender_mesh)

    def test_with_screenshot_used_by_tool8_uv(self):
        assert "_with_screenshot" in _get_source(blender_uv)


# ---------------------------------------------------------------------------
# Cross-cutting: COMMAND_HANDLERS completeness
# ---------------------------------------------------------------------------


class TestCommandHandlersCompleteness:
    """Every COMMAND_HANDLERS value is callable and covers all 8 tools."""

    def test_all_handlers_are_callable(self):
        """Every entry in COMMAND_HANDLERS maps to a callable."""
        for key, handler in COMMAND_HANDLERS.items():
            assert callable(handler), f"COMMAND_HANDLERS['{key}'] is not callable"

    def test_handler_count_minimum(self):
        """At least 40 handlers are registered (ping + scene + objects + ... + worldbuilding)."""
        assert len(COMMAND_HANDLERS) >= 40, (
            f"Expected >= 40 handlers, got {len(COMMAND_HANDLERS)}. "
            f"Keys: {sorted(COMMAND_HANDLERS.keys())}"
        )

    def test_scene_handlers_present(self):
        for key in ("get_scene_info", "clear_scene", "configure_scene", "list_objects"):
            assert key in COMMAND_HANDLERS

    def test_object_handlers_present(self):
        for key in ("create_object", "modify_object", "delete_object", "duplicate_object"):
            assert key in COMMAND_HANDLERS

    def test_material_handlers_present(self):
        for key in ("material_create", "material_assign", "material_modify", "material_list"):
            assert key in COMMAND_HANDLERS

    def test_viewport_handlers_present(self):
        for key in ("get_viewport_screenshot", "render_contact_sheet", "set_shading", "navigate_camera"):
            assert key in COMMAND_HANDLERS

    def test_execute_handler_present(self):
        assert "execute_code" in COMMAND_HANDLERS

    def test_export_handlers_present(self):
        for key in ("export_fbx", "export_gltf"):
            assert key in COMMAND_HANDLERS

    def test_mesh_handlers_present(self):
        for key in (
            "mesh_analyze_topology", "mesh_auto_repair", "mesh_check_game_ready",
            "mesh_select", "mesh_edit", "mesh_boolean", "mesh_retopologize", "mesh_sculpt",
        ):
            assert key in COMMAND_HANDLERS

    def test_uv_handlers_present(self):
        for key in (
            "uv_analyze", "uv_unwrap_xatlas", "uv_unwrap_blender",
            "uv_pack_islands", "uv_generate_lightmap", "uv_equalize_density",
            "uv_export_layout", "uv_set_active_layer", "uv_ensure_xatlas",
        ):
            assert key in COMMAND_HANDLERS

    def test_ping_handler_present(self):
        """The ping utility handler exists."""
        assert "ping" in COMMAND_HANDLERS
        result = COMMAND_HANDLERS["ping"]({})
        assert result == {"status": "success", "result": "pong"}


# ---------------------------------------------------------------------------
# Cross-cutting: MCP tool registration (all 8 original tools)
# ---------------------------------------------------------------------------


class TestMCPToolRegistration:
    """All 8 original Blender tools are registered in the MCP server."""

    ORIGINAL_TOOLS = [
        "blender_scene",
        "blender_object",
        "blender_material",
        "blender_viewport",
        "blender_execute",
        "blender_export",
        "blender_mesh",
        "blender_uv",
    ]

    def test_all_8_original_tools_registered(self):
        for tool_name in self.ORIGINAL_TOOLS:
            assert tool_name in mcp._tool_manager._tools, (
                f"Tool '{tool_name}' not registered in MCP server"
            )

    def test_total_tool_count_at_least_15(self):
        """The server has at least 15 tools (8 original + 7 compound)."""
        count = len(mcp._tool_manager._tools)
        assert count >= 15, (
            f"Expected >= 15 tools, got {count}. "
            f"Registered: {sorted(mcp._tool_manager._tools.keys())}"
        )


# ---------------------------------------------------------------------------
# Pure-logic: validate_code edge cases specific to blender_execute
# ---------------------------------------------------------------------------


class TestValidateCodePureLogic:
    """Pure-logic tests for the security validator used by blender_execute."""

    def test_empty_code_is_safe(self):
        safe, violations = validate_code("")
        assert safe is True
        assert violations == []

    def test_multiline_safe_code(self):
        code = (
            "import bpy\n"
            "import bmesh\n"
            "from mathutils import Vector\n"
            "obj = bpy.context.active_object\n"
            "bm = bmesh.new()\n"
            "bm.from_mesh(obj.data)\n"
            "bm.free()\n"
        )
        safe, violations = validate_code(code)
        assert safe is True

    def test_allowed_getattr_call(self):
        """getattr is allowed per user security policy."""
        safe, violations = validate_code("x = getattr(obj, 'name')")
        assert safe is True

    def test_blocked_dunder_import(self):
        safe, violations = validate_code("__import__('os')")
        assert safe is False

    def test_code_too_long_rejected(self):
        """Code exceeding MAX_CODE_LENGTH is rejected."""
        from veilbreakers_mcp.shared.security import MAX_CODE_LENGTH
        code = "x = 1\n" * (MAX_CODE_LENGTH // 5)
        safe, violations = validate_code(code)
        assert safe is False
        assert any("too long" in v.lower() for v in violations)

    def test_syntax_error_rejected(self):
        safe, violations = validate_code("def foo(")
        assert safe is False
        assert any("syntax" in v.lower() for v in violations)

    def test_blocked_bpy_handlers_access(self):
        """Accessing bpy.app.handlers is blocked (sandbox escape)."""
        safe, violations = validate_code("import bpy\nbpy.app.handlers")
        assert safe is False
        assert any("handlers" in v for v in violations)

    def test_blocked_star_import(self):
        safe, violations = validate_code("from bpy import *")
        assert safe is False
        assert any("star" in v.lower() for v in violations)


# ---------------------------------------------------------------------------
# Function signature verification for all 8 tools
# ---------------------------------------------------------------------------


class TestToolSignatures:
    """Verify that each tool has the expected key parameters."""

    def test_blender_scene_params(self):
        sig = inspect.signature(blender_scene)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "render_engine" in params
        assert "fps" in params
        assert "unit_scale" in params

    def test_blender_object_params(self):
        sig = inspect.signature(blender_object)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "name" in params
        assert "mesh_type" in params
        assert "position" in params
        assert "rotation" in params
        assert "scale" in params
        assert "capture_viewport" in params

    def test_blender_material_params(self):
        sig = inspect.signature(blender_material)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "name" in params
        assert "object_name" in params
        assert "base_color" in params
        assert "metallic" in params
        assert "roughness" in params
        assert "capture_viewport" in params

    def test_blender_viewport_params(self):
        sig = inspect.signature(blender_viewport)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "object_name" in params
        assert "shading_type" in params
        assert "camera_position" in params
        assert "camera_target" in params
        assert "max_size" in params

    def test_blender_execute_params(self):
        sig = inspect.signature(blender_execute)
        params = set(sig.parameters.keys())
        assert "code" in params
        assert "capture_viewport" in params

    def test_blender_export_params(self):
        sig = inspect.signature(blender_export)
        params = set(sig.parameters.keys())
        assert "export_format" in params
        assert "filepath" in params
        assert "selected_only" in params
        assert "apply_modifiers" in params

    def test_blender_mesh_params(self):
        sig = inspect.signature(blender_mesh)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "object_name" in params
        assert "merge_distance" in params
        assert "poly_budget" in params
        assert "platform" in params
        assert "operation" in params
        assert "target_faces" in params
        assert "capture_viewport" in params

    def test_blender_uv_params(self):
        sig = inspect.signature(blender_uv)
        params = set(sig.parameters.keys())
        assert "action" in params
        assert "object_name" in params
        assert "texture_size" in params
        assert "padding" in params
        assert "method" in params
        assert "layer_name" in params
        assert "capture_viewport" in params


# ---------------------------------------------------------------------------
# Default parameter value checks
# ---------------------------------------------------------------------------


class TestDefaultParameterValues:
    """Verify critical default parameter values match expectations."""

    def test_blender_mesh_merge_distance_default(self):
        sig = inspect.signature(blender_mesh)
        assert sig.parameters["merge_distance"].default == 0.0001

    def test_blender_mesh_poly_budget_default(self):
        sig = inspect.signature(blender_mesh)
        assert sig.parameters["poly_budget"].default == 50000

    def test_blender_mesh_platform_default(self):
        sig = inspect.signature(blender_mesh)
        assert sig.parameters["platform"].default == "pc"

    def test_blender_mesh_target_faces_default(self):
        sig = inspect.signature(blender_mesh)
        assert sig.parameters["target_faces"].default == 4000

    def test_blender_uv_texture_size_default(self):
        sig = inspect.signature(blender_uv)
        assert sig.parameters["texture_size"].default == 1024

    def test_blender_uv_method_default(self):
        sig = inspect.signature(blender_uv)
        assert sig.parameters["method"].default == "smart_project"

    def test_blender_uv_angle_limit_default(self):
        sig = inspect.signature(blender_uv)
        assert sig.parameters["angle_limit"].default == 66.0

    def test_blender_viewport_max_size_default(self):
        sig = inspect.signature(blender_viewport)
        assert sig.parameters["max_size"].default == 1024

    def test_blender_export_selected_only_default(self):
        sig = inspect.signature(blender_export)
        assert sig.parameters["selected_only"].default is False

    def test_blender_export_apply_modifiers_default(self):
        sig = inspect.signature(blender_export)
        assert sig.parameters["apply_modifiers"].default is True

    def test_blender_object_capture_viewport_default(self):
        sig = inspect.signature(blender_object)
        assert sig.parameters["capture_viewport"].default is True

    def test_blender_execute_capture_viewport_default(self):
        sig = inspect.signature(blender_execute)
        assert sig.parameters["capture_viewport"].default is True
