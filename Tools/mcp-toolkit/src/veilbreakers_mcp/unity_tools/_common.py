"""Shared utilities for Unity tool modules.

Contains _write_to_unity, _read_unity_result, _handle_dict_template,
and shared state (logger, settings, mcp) used by all tool handlers.
"""

import json
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from veilbreakers_mcp.shared.config import Settings
from veilbreakers_mcp.shared.unity_client import UnityConnection, UnityCommandError
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier

STANDARD_NEXT_STEPS = [
    "Recompile: unity_editor action=recompile",
    "Then run the generated menu item in Unity Editor",
]


def _strip_schema_titles(obj: dict | list) -> None:
    """Recursively remove redundant JSON-schema title fields."""
    if isinstance(obj, dict):
        obj.pop("title", None)
        for value in obj.values():
            if isinstance(value, (dict, list)):
                _strip_schema_titles(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _strip_schema_titles(item)


def _strip_registered_tool_titles(mcp_instance: FastMCP) -> None:
    """Trim auto-generated schema titles from all registered tool params."""
    tool_manager = getattr(mcp_instance, "_tool_manager", None)
    tools = getattr(tool_manager, "_tools", {})
    for tool in tools.values():
        parameters = getattr(tool, "parameters", None)
        if isinstance(parameters, (dict, list)):
            _strip_schema_titles(parameters)


async def _execute_menu_item(menu_path: str) -> dict | None:
    """Execute a Unity menu item via the VBBridge TCP connection.

    Returns the result dict on success, or None if bridge unavailable.
    """
    try:
        conn = UnityConnection(timeout=30)
        return await conn.send_command("execute_menu_item", {"menu_path": menu_path})
    except (ConnectionError, TimeoutError, OSError):
        return None


async def _bridge_recompile_and_execute(menu_path: str) -> dict | None:
    """Recompile Unity, wait for completion, then execute a menu item.

    Returns the execution result, or None if bridge unavailable.
    Uses exponential backoff polling to avoid TCP connection flooding.
    """
    import asyncio

    try:
        conn = UnityConnection(timeout=30)
        # Trigger recompile
        await conn.send_command("recompile")

        # Wait for compilation to finish (up to 30s) with exponential backoff
        # to avoid creating 60+ TCP connections
        delay = 0.5
        elapsed = 0.0
        max_wait = 30.0
        while elapsed < max_wait:
            await asyncio.sleep(delay)
            elapsed += delay
            try:
                status = await conn.send_command("check_compile_status")
                if not status.get("is_compiling", True):
                    break
            except (ConnectionError, OSError):
                # Bridge may be temporarily unavailable during recompile
                pass
            delay = min(delay * 1.5, 3.0)  # Cap at 3s intervals

        # Check for errors
        status = await conn.send_command("check_compile_status")
        if status.get("has_errors", False):
            return {"status": "error", "compile_errors": status.get("errors", [])}

        # Execute menu item
        result = await conn.send_command("execute_menu_item", {"menu_path": menu_path})
        return result
    except (ConnectionError, TimeoutError, OSError):
        return None

logger = logging.getLogger("veilbreakers_mcp.unity")

settings = Settings()
mcp = FastMCP(
    "veilbreakers-unity",
    instructions="""\
VeilBreakers Unity MCP — 22 compound tools (258 actions) for dark fantasy action RPG development.

## Tool Architecture
Each tool uses a compound pattern: one tool name, `action` param selects the operation.
Tools generate C# editor scripts written to the Unity project. CRITICAL two-step pattern:
1. Call the tool (generates .cs file)
2. Read the `next_steps` in the response — typically: call `unity_editor` action=recompile, then execute the menu item in Unity Editor

## Core Tool Categories
**Editor Control**: unity_editor — recompile, enter/exit_play_mode, screenshot, console_logs, load_scene
**VFX**: unity_vfx — 19 actions: particle systems, brand VFX (IRON/SAVAGE/SURGE/VENOM/DREAD/LEECH/GRACE/MEND/RUIN/VOID), shaders (dissolve/force_field/water), post-processing, projectile chains, AOE, boss transitions, decals
**Audio**: unity_audio — 20 actions: AI SFX (ElevenLabs), music loops, ambient, adaptive music, spatial audio, dynamic music, portal audio, procedural foley, VO pipeline
**UI**: unity_ui — 14 actions: screen generation, WCAG contrast checking, procedural frames, icon pipeline, cursors, tooltips, radial menus, notifications, loading screens, combat HUD
**Scene**: unity_scene — terrain setup, lighting (dawn/noon/dusk/night), animators, blend trees, additive layers
**Gameplay**: unity_gameplay — mob controllers, spawn systems, behavior trees, projectile systems, encounter systems, AI director, boss AI
**Game Systems**: unity_game — save, health, character controller, input, abilities, synergy engine, corruption, XP, currency, damage types
**Content**: unity_content — inventory, dialogue, quests, loot tables, crafting, skill trees, shops, journals, equipment
**World**: unity_world — scenes, transitions, occlusion, weather, day/night, fast travel, puzzles, traps, WFC dungeons, interior streaming, door systems
**Camera**: unity_camera — Cinemachine virtual cameras, state-driven, camera shake, timelines, cutscenes, lock-on camera
**Performance**: unity_performance — scene profiling, LOD groups, lightmap baking, asset audits, build automation
**QA**: unity_qa — TCP bridge setup, test runner, play sessions, memory leak detection, compile recovery, pipeline orchestration, code review

## Workflow Rules
- ALWAYS read `next_steps` from tool responses and follow them
- After generating scripts: call `unity_editor` action=recompile to trigger compilation
- Use `unity_editor` action=screenshot to verify visual results
- Use `unity_performance` action=profile_scene after scene setup
- Use `unity_qa` action=check_compile_status to detect compilation errors
- Use `unity_quality` action=aaa_audit for comprehensive quality checks
""",
)




def _write_to_unity(content: str, relative_path: str) -> str:
    """Write generated file content to the Unity project directory.

    Args:
        content: File content (C# source, JSON, etc.) to write.
        relative_path: Path relative to the Unity project root
                       (e.g., "Assets/Editor/Generated/AutoRecompile/Recompile.cs").

    Returns:
        Absolute path of the written file.

    Raises:
        ValueError: If unity_project_path is not configured.
    """
    if not settings.unity_project_path:
        raise ValueError(
            "unity_project_path not configured. Set UNITY_PROJECT_PATH environment "
            "variable or unity_project_path in Settings."
        )

    project_root = Path(settings.unity_project_path).resolve()
    target = (project_root / relative_path).resolve()

    # Path traversal protection: ensure target stays within project root
    try:
        target.relative_to(project_root)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{relative_path}' resolves outside the "
            f"Unity project directory."
        )

    if not content or not content.strip():
        raise ValueError(
            f"Refusing to write empty generated content to '{relative_path}'."
        )

    # Create parent directories as needed
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return str(target)


def _read_unity_result() -> dict:
    """Read the result JSON written by a Unity editor script.

    Returns:
        Parsed JSON dict from Temp/vb_result.json, or an error dict
        if the file doesn't exist.
    """
    if not settings.unity_project_path:
        return {"status": "error", "message": "unity_project_path not configured"}

    result_path = Path(settings.unity_project_path) / "Temp" / "vb_result.json"
    if not result_path.exists():
        return {
            "status": "pending",
            "message": (
                "Result file not found. The Unity editor script may not have "
                "executed yet. Run unity_editor action=recompile to compile, "
                "then open Unity Editor and run the generated menu command."
            ),
        }

    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "message": f"Failed to read result: {exc}"}


async def _handle_dict_template(action_name: str, result: dict) -> str:
    """Generic handler for v3.0 template generators that return dicts.

    v3.0 generators (audio_middleware, ui_polish, vfx_mastery, production)
    return ``{script_path, script_content, next_steps, menu_path?}``.
    This helper writes the script to Unity and optionally auto-executes
    via the VBBridge TCP connection if a menu_path is provided.
    """
    script_content = result.get("script_content", "")
    rel_path = result.get("script_path", f"Assets/Scripts/Generated/{action_name}.cs")
    next_steps = result.get("next_steps", [])
    menu_path = result.get("menu_path", "")
    passthrough_keys = {
        key: value for key, value in result.items()
        if key not in {"script_content", "script_path", "next_steps", "menu_path"}
    }

    try:
        abs_path = _write_to_unity(script_content, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": action_name, "message": str(exc)})

    # Attempt auto-execute via bridge if menu_path is provided
    bridge_result = None
    if menu_path:
        bridge_result = await _bridge_recompile_and_execute(menu_path)

    response = {
        "status": "success",
        "action": action_name,
        "script_path": abs_path,
        "result_file": "Temp/vb_result.json",
    }
    response.update(passthrough_keys)

    if bridge_result is not None:
        response["bridge_executed"] = True
        response["bridge_result"] = bridge_result
        response["next_steps"] = ["Auto-executed via VBBridge. Check result above."]
    else:
        response["bridge_executed"] = False
        response["next_steps"] = next_steps

    return json.dumps(response, indent=2)
