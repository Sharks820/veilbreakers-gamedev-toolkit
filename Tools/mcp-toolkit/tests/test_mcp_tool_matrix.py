"""37-tool MCP verification matrix.

Verifies all 16 Blender tools and 23 Unity tools are importable,
have correct action Literal parameters, and handler registrations exist.
Also verifies bridge template generators produce valid C# output.
"""

from __future__ import annotations

import typing

import pytest


# =====================================================================
# Blender Tool Matrix
# =====================================================================


BLENDER_TOOL_NAMES = [
    "blender_scene",
    "blender_object",
    "blender_material",
    "blender_viewport",
    "blender_execute",
    "blender_export",
    "blender_mesh",
    "blender_uv",
    "blender_texture",
    "asset_pipeline",
    "concept_art",
    "blender_rig",
    "blender_animation",
    "blender_environment",
    "blender_worldbuilding",
    "blender_quality",
]


class TestBlenderToolMatrix:
    """Verify all 16 Blender compound tools."""

    def test_blender_server_importable(self):
        import veilbreakers_mcp.blender_server as bs
        assert hasattr(bs, "mcp")

    @pytest.mark.parametrize("tool_name", BLENDER_TOOL_NAMES)
    def test_blender_tool_exists(self, tool_name):
        import veilbreakers_mcp.blender_server as bs
        assert hasattr(bs, tool_name), f"Missing tool function: {tool_name}"

    # blender_execute uses 'code', blender_export uses 'export_format'
    BLENDER_ACTION_TOOLS = [
        t for t in BLENDER_TOOL_NAMES
        if t not in ("blender_execute", "blender_export")
    ]

    @pytest.mark.parametrize("tool_name", BLENDER_ACTION_TOOLS)
    def test_blender_tool_has_action_param(self, tool_name):
        import veilbreakers_mcp.blender_server as bs
        func = getattr(bs, tool_name)
        hints = typing.get_type_hints(func)
        assert "action" in hints, f"{tool_name} missing 'action' parameter"
        args = typing.get_args(hints["action"])
        assert len(args) >= 2, f"{tool_name} action Literal has too few values: {args}"

    def test_blender_execute_has_code_param(self):
        import veilbreakers_mcp.blender_server as bs
        hints = typing.get_type_hints(bs.blender_execute)
        assert "code" in hints, "blender_execute missing 'code' parameter"

    def test_blender_export_has_format_param(self):
        import veilbreakers_mcp.blender_server as bs
        hints = typing.get_type_hints(bs.blender_export)
        assert "export_format" in hints, "blender_export missing 'export_format' parameter"

    def test_blender_tool_count(self):
        assert len(BLENDER_TOOL_NAMES) == 16

    # Handler registration checks
    EXPECTED_HANDLER_KEYS = [
        "create_object", "modify_object", "delete_object", "duplicate_object",
        "mesh_analyze_topology", "mesh_auto_repair", "mesh_check_game_ready",
        "uv_analyze", "uv_unwrap_xatlas", "uv_unwrap_blender",
        "texture_create_pbr", "texture_bake", "texture_validate",
        "material_create", "material_assign", "material_modify",
        "rig_analyze", "rig_apply_template", "rig_auto_weight",
        "anim_generate_walk", "anim_generate_idle", "anim_generate_attack",
        "export_fbx", "export_gltf",
        "execute_code",
        "get_scene_info", "list_objects", "clear_scene",
        "get_viewport_screenshot", "render_contact_sheet",
        "env_generate_terrain", "env_create_water",
        "world_generate_building", "world_generate_dungeon",
        "world_generate_settlement", "world_generate_town",
        "auto_frame_camera", "interior_camera_shot",
        "env_scatter_vegetation", "env_scatter_props",
        "pipeline_generate_lods",
        "mesh_boolean", "mesh_sculpt",
        "curve_create", "curve_to_mesh",
        "rig_setup_ik", "rig_setup_facial",
        "anim_batch_export",
        "setup_beauty_scene",
    ]

    @pytest.mark.parametrize("handler_key", EXPECTED_HANDLER_KEYS)
    def test_blender_command_handler_registered(self, handler_key):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert handler_key in COMMAND_HANDLERS, (
            f"Missing handler: {handler_key}"
        )

    def test_blender_command_handlers_count(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        # Should have at least 50 handler entries
        assert len(COMMAND_HANDLERS) >= 50, (
            f"Expected >= 50 handlers, got {len(COMMAND_HANDLERS)}"
        )


# =====================================================================
# Unity Tool Matrix
# =====================================================================


UNITY_TOOL_MODULES = [
    "editor", "vfx", "audio", "ui", "scene", "gameplay",
    "performance", "settings", "prefab", "assets", "code",
    "shader", "data", "quality", "pipeline", "game",
    "content", "camera", "world", "ux", "qa", "build",
    "gameobject",
]

UNITY_TOOL_FUNCTIONS = [
    ("editor", "unity_editor"),
    ("vfx", "unity_vfx"),
    ("audio", "unity_audio"),
    ("ui", "unity_ui"),
    ("scene", "unity_scene"),
    ("gameplay", "unity_gameplay"),
    ("performance", "unity_performance"),
    ("settings", "unity_settings"),
    ("prefab", "unity_prefab"),
    ("assets", "unity_assets"),
    ("code", "unity_code"),
    ("shader", "unity_shader"),
    ("data", "unity_data"),
    ("quality", "unity_quality"),
    ("pipeline", "unity_pipeline"),
    ("game", "unity_game"),
    ("content", "unity_content"),
    ("camera", "unity_camera"),
    ("world", "unity_world"),
    ("ux", "unity_ux"),
    ("qa", "unity_qa"),
    ("build", "unity_build"),
    ("gameobject", "unity_gameobject"),
]


class TestUnityToolMatrix:
    """Verify all 23 Unity compound tools."""

    @pytest.mark.parametrize("module_name", UNITY_TOOL_MODULES)
    def test_unity_module_importable(self, module_name):
        import importlib
        mod = importlib.import_module(f"veilbreakers_mcp.unity_tools.{module_name}")
        assert mod is not None

    @pytest.mark.parametrize("module_name,func_name", UNITY_TOOL_FUNCTIONS)
    def test_unity_tool_function_exists(self, module_name, func_name):
        import importlib
        mod = importlib.import_module(f"veilbreakers_mcp.unity_tools.{module_name}")
        assert hasattr(mod, func_name), (
            f"Module {module_name} missing function {func_name}"
        )

    @pytest.mark.parametrize("module_name,func_name", UNITY_TOOL_FUNCTIONS)
    def test_unity_tool_has_action_param(self, module_name, func_name):
        import importlib
        mod = importlib.import_module(f"veilbreakers_mcp.unity_tools.{module_name}")
        func = getattr(mod, func_name)
        hints = typing.get_type_hints(func)
        assert "action" in hints, f"{func_name} missing 'action' parameter"
        args = typing.get_args(hints["action"])
        assert len(args) >= 2, f"{func_name} action Literal too few values: {args}"

    def test_unity_tool_count(self):
        from veilbreakers_mcp.unity_tools import mcp
        tools = getattr(mcp, "_tool_manager", None)
        tool_dict = getattr(tools, "_tools", {})
        assert len(tool_dict) >= 23, f"Expected >= 23 tools, got {len(tool_dict)}"

    def test_unity_gameobject_has_16_actions(self):
        from veilbreakers_mcp.unity_tools.gameobject import unity_gameobject
        hints = typing.get_type_hints(unity_gameobject)
        args = typing.get_args(hints["action"])
        assert len(args) == 16, f"Expected 16, got {len(args)}"


# =====================================================================
# Bridge Template Tests
# =====================================================================


class TestBridgeTemplates:
    """Verify bridge template generators produce valid C# output."""

    def test_bridge_server_script_generated(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_server_script,
        )
        cs = generate_bridge_server_script()
        assert isinstance(cs, str)
        assert len(cs) > 500
        assert "TcpListener" in cs
        assert "EditorApplication" in cs
        assert "VBBridgeServer" in cs

    def test_bridge_commands_original_10(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_commands_script,
        )
        cs = generate_bridge_commands_script()
        original_10 = [
            "ping", "recompile", "execute_menu_item", "enter_play_mode",
            "exit_play_mode", "screenshot", "console_logs", "read_result",
            "get_game_objects", "check_compile_status",
        ]
        for key in original_10:
            assert f'["{key}"]' in cs, f"Missing original handler: {key}"

    def test_bridge_commands_dispatch_method(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_commands_script,
        )
        cs = generate_bridge_commands_script()
        assert "public static string Dispatch" in cs
        assert "HANDLERS.TryGetValue" in cs

    def test_bridge_commands_has_26_handlers(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_commands_script,
        )
        cs = generate_bridge_commands_script()
        # Count handler registrations in HANDLERS dict
        all_26 = [
            "ping", "recompile", "execute_menu_item", "enter_play_mode",
            "exit_play_mode", "screenshot", "console_logs", "read_result",
            "get_game_objects", "check_compile_status",
            "create_gameobject", "delete_gameobject", "duplicate_gameobject",
            "reparent_gameobject", "set_transform", "update_gameobject",
            "find_gameobjects", "get_components", "add_component",
            "remove_component", "get_hierarchy", "get_scene_info",
            "save_scene", "undo", "redo", "instantiate_prefab",
        ]
        for key in all_26:
            assert f'["{key}"]' in cs, f"Missing handler: {key}"

    def test_qa_template_generators_callable(self):
        from veilbreakers_mcp.shared.unity_templates.qa_templates import (
            generate_bridge_server_script,
            generate_bridge_commands_script,
            generate_crash_reporting_script,
            generate_analytics_script,
            generate_live_inspector_script,
        )
        for gen in [
            generate_bridge_server_script,
            generate_bridge_commands_script,
            generate_crash_reporting_script,
            generate_analytics_script,
            generate_live_inspector_script,
        ]:
            result = gen()
            assert isinstance(result, str)
            assert len(result) > 100, f"{gen.__name__} returned too-short output"
