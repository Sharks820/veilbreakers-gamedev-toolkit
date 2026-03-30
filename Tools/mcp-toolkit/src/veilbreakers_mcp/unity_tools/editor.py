"""unity_editor tool handler.

Uses the VBBridge TCP connection (port 9877) for direct Unity Editor
communication when available.  Falls back to generating C# scripts
when the bridge is not connected.
"""

import json
import os
from pathlib import Path
from typing import Literal

from veilbreakers_mcp.unity_tools._common import (
    mcp, settings, logger,
    _write_to_unity, STANDARD_NEXT_STEPS,
)
from veilbreakers_mcp.shared.unity_templates._cs_sanitize import sanitize_cs_identifier

from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_recompile_script,
    generate_play_mode_script,
    generate_screenshot_script,
    generate_console_log_script,
    generate_gemini_review_script,
    generate_test_runner_script,
)
from veilbreakers_mcp.shared.gemini_client import GeminiReviewClient
from veilbreakers_mcp.shared.unity_client import UnityConnection, UnityCommandError


# ---------------------------------------------------------------------------
# TCP Bridge helpers -- direct communication with Unity Editor
# ---------------------------------------------------------------------------

async def _try_bridge(command: str, params: dict | None = None, retries: int = 2) -> dict | None:
    """Try to execute a command via the VBBridge TCP connection.

    Returns the result dict on success, or None if the bridge is not
    available (falls back to script generation).  Retries on transient
    connection failures (e.g., bridge momentarily busy after play mode).
    """
    import asyncio

    last_exc = None
    for attempt in range(retries):
        try:
            conn = UnityConnection(timeout=30)
            result = await conn.send_command(command, params or {})
            return result
        except UnityCommandError:
            # Command-level error (not transient) -- don't retry
            raise
        except (ConnectionError, OSError, TimeoutError) as exc:
            last_exc = exc
            logger.debug(
                "VBBridge attempt %d/%d for '%s' failed: %s",
                attempt + 1, retries, command, exc,
            )
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.debug("VBBridge unexpected error for '%s': %s", command, exc)
            return None

    logger.debug("VBBridge unavailable for '%s' after %d attempts: %s", command, retries, last_exc)
    return None




@mcp.tool()
async def unity_editor(
    action: Literal[
        "recompile",
        "enter_play_mode",
        "exit_play_mode",
        "screenshot",
        "console_logs",
        "gemini_review",
        "run_tests",
        "clean_generated",
        "load_scene",
    ],
    screenshot_path: str = "Screenshots/vb_capture.png",
    supersize: int = 1,
    log_filter: str = "all",
    log_count: int = 50,
    gemini_prompt: str = "Review this game screenshot for visual quality",
    gemini_criteria: list[str] | None = None,
    test_mode: str = "EditMode",
    assembly_filter: str = "",
    category_filter: str = "",
    scene_path: str = "",
    older_than_hours: int = 0,
) -> str:
    """Unity Editor automation -- generate C# scripts and trigger actions.

    Actions:
        recompile: Trigger Unity recompile via bridge or generated script.
        enter_play_mode / exit_play_mode: Toggle play mode.
        screenshot: Capture game view screenshot.
        console_logs: Read Unity console output.
        gemini_review: AI visual quality review of screenshot.
        run_tests: Execute EditMode/PlayMode tests.
        clean_generated: Remove accumulated editor scripts from Assets/Editor/Generated/.
        load_scene: Open a scene by path in the editor.
    """
    if gemini_criteria is None:
        gemini_criteria = ["lighting", "composition", "visual_quality"]

    try:
        if action == "recompile":
            return await _handle_recompile()
        elif action == "enter_play_mode":
            return await _handle_play_mode(enter=True)
        elif action == "exit_play_mode":
            return await _handle_play_mode(enter=False)
        elif action == "screenshot":
            return await _handle_screenshot(screenshot_path, supersize)
        elif action == "console_logs":
            return await _handle_console_logs(log_filter, log_count)
        elif action == "gemini_review":
            return await _handle_gemini_review(
                screenshot_path, gemini_prompt, gemini_criteria
            )
        elif action == "run_tests":
            return await _handle_run_tests(
                test_mode, assembly_filter, category_filter
            )
        elif action == "clean_generated":
            return await _handle_clean_generated(older_than_hours)
        elif action == "load_scene":
            return await _handle_load_scene(scene_path)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_editor action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


async def _handle_run_tests(
    test_mode: str, assembly_filter: str, category_filter: str,
) -> str:
    """Generate and write the test runner script."""
    script = generate_test_runner_script(
        test_mode=test_mode,
        assembly_filter=assembly_filter,
        category_filter=category_filter,
    )
    script_path = "Assets/Editor/Generated/Code/VeilBreakers_RunTests.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "run_tests", "message": str(exc)}
        )

    return json.dumps({
        "status": "success",
        "action": "run_tests",
        "script_path": abs_path,
        "test_mode": test_mode,
        "next_steps": STANDARD_NEXT_STEPS,
    })


async def _handle_recompile() -> str:
    """Recompile via TCP bridge, fallback to script generation."""
    # Try direct bridge first
    result = await _try_bridge("recompile")
    if result is not None:
        return json.dumps({"status": "success", "action": "recompile", "bridge": True, **result})

    # Fallback: generate script
    script = generate_recompile_script()
    script_path = "Assets/Editor/Generated/AutoRecompile/VeilBreakers_Recompile.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "recompile", "message": str(exc)})
    return json.dumps({"status": "success", "action": "recompile", "script_path": abs_path, "next_steps": STANDARD_NEXT_STEPS}, indent=2)


async def _handle_play_mode(enter: bool) -> str:
    """Enter/exit play mode via TCP bridge, fallback to script."""
    action_name = "enter_play_mode" if enter else "exit_play_mode"
    cmd = "enter_play_mode" if enter else "exit_play_mode"

    result = await _try_bridge(cmd)
    if result is not None:
        return json.dumps({"status": "success", "action": action_name, "bridge": True, **result})

    # Fallback
    script = generate_play_mode_script(enter=enter)
    filename = f"VeilBreakers_PlayMode_{action_name}.cs"
    script_path = f"Assets/Editor/Generated/PlayMode/{filename}"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": action_name, "message": str(exc)})
    return json.dumps({"status": "success", "action": action_name, "script_path": abs_path, "next_steps": STANDARD_NEXT_STEPS}, indent=2)


async def _handle_screenshot(screenshot_path: str, supersize: int) -> str:
    """Take screenshot via TCP bridge, fallback to script."""
    result = await _try_bridge("screenshot", {"path": screenshot_path, "supersize": supersize})
    if result is not None:
        return json.dumps({"status": "success", "action": "screenshot", "bridge": True, "screenshot_path": screenshot_path, **result})

    # Fallback
    script = generate_screenshot_script(output_path=screenshot_path, supersize=supersize)
    script_path = "Assets/Editor/Generated/Screenshot/VeilBreakers_Screenshot.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "screenshot", "message": str(exc)})
    return json.dumps({"status": "success", "action": "screenshot", "script_path": abs_path, "screenshot_path": screenshot_path, "next_steps": STANDARD_NEXT_STEPS}, indent=2)


async def _handle_console_logs(log_filter: str, log_count: int) -> str:
    """Read console logs via TCP bridge, fallback to script."""
    result = await _try_bridge("console_logs", {"filter": log_filter, "count": log_count})
    if result is not None:
        return json.dumps({"status": "success", "action": "console_logs", "bridge": True, **result})

    # Fallback
    script = generate_console_log_script(filter_type=log_filter, count=log_count)
    script_path = "Assets/Editor/Generated/ConsoleLogs/VeilBreakers_ConsoleLogs.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "console_logs", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "console_logs",
            "script_path": abs_path,
            "filter": log_filter,
            "max_count": log_count,
            "next_steps": STANDARD_NEXT_STEPS,
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gemini_review(
    screenshot_path: str,
    prompt: str,
    criteria: list[str],
) -> str:
    """Handle Gemini visual review -- Python-side API call."""
    # First, write the C# script that exports the screenshot path
    script = generate_gemini_review_script(
        screenshot_path=screenshot_path, criteria=criteria
    )
    script_path = "Assets/Editor/Generated/GeminiReview/VeilBreakers_GeminiReview.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "gemini_review", "message": str(exc)}
        )

    # Attempt Python-side Gemini review if the screenshot exists
    full_screenshot = ""
    if settings.unity_project_path:
        full_screenshot = str(
            Path(settings.unity_project_path) / screenshot_path
        )

    review_result = {}
    if full_screenshot and os.path.exists(full_screenshot):
        client = GeminiReviewClient(api_key=settings.gemini_api_key or None)
        review_result = client.review_screenshot(
            image_path=full_screenshot, prompt=prompt
        )

    return json.dumps(
        {
            "status": "success",
            "action": "gemini_review",
            "script_path": abs_path,
            "screenshot_path": screenshot_path,
            "criteria": criteria,
            "review": review_result if review_result else None,
            "next_steps": STANDARD_NEXT_STEPS,
        },
        indent=2,
    )


async def _handle_clean_generated(older_than_hours: int) -> str:
    """Remove accumulated generated editor scripts from Assets/Editor/Generated/.

    Args:
        older_than_hours: If > 0, only remove files older than this many hours.
                          If 0, remove all generated scripts.
    """
    if not settings.unity_project_path:
        return json.dumps({
            "status": "error",
            "action": "clean_generated",
            "message": "unity_project_path not configured",
        })

    import time

    gen_dir = Path(settings.unity_project_path) / "Assets" / "Editor" / "Generated"
    if not gen_dir.exists():
        return json.dumps({
            "status": "success",
            "action": "clean_generated",
            "removed_count": 0,
            "message": "No generated scripts directory found.",
        })

    removed = []
    now = time.time()
    cutoff = now - (older_than_hours * 3600) if older_than_hours > 0 else float("inf")

    for cs_file in gen_dir.rglob("*.cs"):
        if older_than_hours > 0 and cs_file.stat().st_mtime > cutoff:
            continue
        removed.append(str(cs_file.relative_to(Path(settings.unity_project_path))))
        cs_file.unlink()
        # Also remove .meta file if present
        meta = cs_file.with_suffix(".cs.meta")
        if meta.exists():
            meta.unlink()

    # Clean up empty directories
    for dirpath in sorted(gen_dir.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()

    return json.dumps({
        "status": "success",
        "action": "clean_generated",
        "removed_count": len(removed),
        "removed_files": removed[:50],  # Cap output
        "message": f"Removed {len(removed)} generated script(s).",
    }, indent=2)


async def _handle_load_scene(scene_path: str) -> str:
    """Load a scene in the Unity Editor via bridge, fallback to script."""
    if not scene_path:
        return json.dumps({
            "status": "error",
            "action": "load_scene",
            "message": "scene_path is required (e.g., 'Assets/Scenes/MainMenu.unity')",
        })

    # Validate scene_path: must look like a Unity scene path (no injection chars)
    import re as _re
    if not _re.match(r'^[A-Za-z0-9_./\- ]+\.unity$', scene_path):
        return json.dumps({
            "status": "error",
            "action": "load_scene",
            "message": "Invalid scene_path: must match pattern 'Assets/.../*.unity'",
        })

    # Try bridge first
    result = await _try_bridge("load_scene", {"scene_path": scene_path})
    if result is not None:
        return json.dumps({
            "status": "success",
            "action": "load_scene",
            "bridge": True,
            "scene_path": scene_path,
            **result,
        })

    # Fallback: generate a C# script that opens the scene
    safe_name = sanitize_cs_identifier(scene_path.rsplit("/", 1)[-1].replace(".unity", ""))
    script = f'''using UnityEditor;
using UnityEditor.SceneManagement;

public static class VeilBreakers_LoadScene_{safe_name}
{{
    [MenuItem("VeilBreakers/Load Scene/{safe_name}")]
    public static void Execute()
    {{
        if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
        {{
            EditorSceneManager.OpenScene("{scene_path}");
            UnityEngine.Debug.Log("[VB] Loaded scene: {scene_path}");
        }}
    }}
}}
'''
    script_rel = f"Assets/Editor/Generated/Scene/VeilBreakers_LoadScene_{safe_name}.cs"
    try:
        abs_path = _write_to_unity(script, script_rel)
    except ValueError as exc:
        return json.dumps({
            "status": "error", "action": "load_scene", "message": str(exc),
        })

    return json.dumps({
        "status": "success",
        "action": "load_scene",
        "bridge": False,
        "scene_path": scene_path,
        "script_path": abs_path,
        "next_steps": STANDARD_NEXT_STEPS,
    }, indent=2)
