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
from veilbreakers_mcp.shared.unity_templates.code_templates import _sanitize_cs_identifier

logger = logging.getLogger("veilbreakers_mcp.unity")

settings = Settings()
mcp = FastMCP(
    "veilbreakers-unity",
    instructions="VeilBreakers Unity game development tools",
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

    project_root = Path(settings.unity_project_path).resolve()
    target = (project_root / relative_path).resolve()

    # Path traversal protection: ensure target stays within project root
    try:
        target.relative_to(project_root)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{relative_path}' resolves outside the "
            f"Unity project directory."

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
    return ``{script_path, script_content, next_steps}``.
    This helper writes the script to Unity and returns a standard JSON response.
    """
    script_content = result.get("script_content", "")
    rel_path = result.get("script_path", f"Assets/Scripts/Generated/{action_name}.cs")
    next_steps = result.get("next_steps", [])

    try:
        abs_path = _write_to_unity(script_content, rel_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": action_name, "message": str(exc)})

    return json.dumps({
        "status": "success",
        "action": action_name,
        "script_path": abs_path,
        "next_steps": next_steps,
        "result_file": "Temp/vb_result.json",
    }, indent=2)
