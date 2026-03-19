"""VeilBreakers Unity MCP Server.

FastMCP server providing Unity Editor automation tools. Generates C# editor
scripts that are written to the Unity project and executed via mcp-unity's
recompile_scripts + execute_menu_item workflow.

Entry point: vb-unity-mcp (see pyproject.toml [project.scripts])
"""

import json
import logging
import os
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from veilbreakers_mcp.shared.config import Settings
from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_recompile_script,
    generate_play_mode_script,
    generate_screenshot_script,
    generate_console_log_script,
    generate_gemini_review_script,
)
from veilbreakers_mcp.shared.gemini_client import GeminiReviewClient
from veilbreakers_mcp.shared.elevenlabs_client import ElevenLabsAudioClient
from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    generate_particle_vfx_script,
    generate_brand_vfx_script,
    generate_environmental_vfx_script,
    generate_trail_vfx_script,
    generate_aura_vfx_script,
    generate_post_processing_script,
    generate_screen_effect_script,
    generate_ability_vfx_script,
)
from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_corruption_shader,
    generate_dissolve_shader,
    generate_force_field_shader,
    generate_water_shader,
    generate_foliage_shader,
    generate_outline_shader,
    generate_damage_overlay_shader,
)
from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_footstep_manager_script,
    generate_adaptive_music_script,
    generate_audio_zone_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_animation_event_sfx_script,
)
from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    generate_uss_stylesheet,
    generate_responsive_test_script,
    validate_uxml_layout,
)
from veilbreakers_mcp.shared.wcag_checker import validate_uxml_contrast
from veilbreakers_mcp.shared.screenshot_diff import (
    compare_screenshots as _compare_screenshots,
    generate_diff_image,
)
from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_object_scatter_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_animation_rigging_script,
)

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
        )

    project_root = Path(settings.unity_project_path).resolve()
    target = (project_root / relative_path).resolve()

    # Path traversal protection: ensure target stays within project root
    if not str(target).startswith(str(project_root)):
        raise ValueError(
            f"Path traversal detected: '{relative_path}' resolves outside the "
            f"Unity project directory."
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
                "executed yet. Use mcp-unity's recompile_scripts tool to compile, "
                "then execute_menu_item to run the generated command."
            ),
        }

    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "message": f"Failed to read result: {exc}"}


@mcp.tool()
async def unity_editor(
    action: Literal[
        "recompile",
        "enter_play_mode",
        "exit_play_mode",
        "screenshot",
        "console_logs",
        "gemini_review",
    ],
    screenshot_path: str = "Screenshots/vb_capture.png",
    supersize: int = 1,
    log_filter: str = "all",
    log_count: int = 50,
    gemini_prompt: str = "Review this game screenshot for visual quality",
    gemini_criteria: list[str] | None = None,
) -> str:
    """Unity Editor automation -- generate C# scripts and trigger actions.

    This compound tool generates C# editor scripts, writes them to the Unity
    project, and returns instructions for executing them via mcp-unity.

    Actions:
    - recompile: Force Unity to recompile all scripts (AssetDatabase.Refresh)
    - enter_play_mode: Enter Unity play mode
    - exit_play_mode: Exit Unity play mode
    - screenshot: Capture game view screenshot
    - console_logs: Collect Unity console log entries
    - gemini_review: Send a screenshot to Gemini for visual quality review

    Args:
        action: The editor action to perform.
        screenshot_path: Path for screenshot capture (relative to Unity project).
        supersize: Screenshot resolution multiplier (1-4).
        log_filter: Console log filter -- "all", "error", "warning", "log".
        log_count: Maximum number of log entries to collect.
        gemini_prompt: Prompt for Gemini visual review.
        gemini_criteria: List of quality criteria for Gemini review.
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
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_editor action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


async def _handle_recompile() -> str:
    """Generate and write the recompile script."""
    script = generate_recompile_script()
    script_path = "Assets/Editor/Generated/AutoRecompile/VeilBreakers_Recompile.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "recompile", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "recompile",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Editor/Force Recompile"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_play_mode(enter: bool) -> str:
    """Generate and write the play mode script."""
    script = generate_play_mode_script(enter=enter)
    action_name = "enter_play_mode" if enter else "exit_play_mode"
    menu_label = "Enter Play Mode" if enter else "Exit Play Mode"
    filename = f"VeilBreakers_PlayMode_{'enterplaymode' if enter else 'exitplaymode'}.cs"
    script_path = f"Assets/Editor/Generated/PlayMode/{filename}"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": action_name, "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": action_name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/Editor/{menu_label}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_screenshot(screenshot_path: str, supersize: int) -> str:
    """Generate and write the screenshot capture script."""
    script = generate_screenshot_script(output_path=screenshot_path, supersize=supersize)
    script_path = "Assets/Editor/Generated/Screenshot/VeilBreakers_Screenshot.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "screenshot", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "screenshot",
            "script_path": abs_path,
            "screenshot_path": screenshot_path,
            "supersize": supersize,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Editor/Capture Screenshot"',
                f"Screenshot will be saved to: {screenshot_path}",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_console_logs(log_filter: str, log_count: int) -> str:
    """Generate and write the console log collection script."""
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
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Editor/Collect Console Logs"',
            ],
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
            "next_steps": [
                "If screenshot doesn't exist yet, capture it first with action='screenshot'",
                "Call mcp-unity recompile_scripts to compile the export script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Editor/Prepare Gemini Review"',
                "The Gemini review result will also be available in Temp/vb_result.json",
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# VFX tool -- compound tool covering VFX-01 through VFX-10
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_vfx(
    action: Literal[
        "create_particle_vfx",      # VFX-01: text -> VFX Graph config
        "create_brand_vfx",         # VFX-02: per-brand damage VFX
        "create_environmental_vfx", # VFX-03: dust/fireflies/snow/rain/ash
        "create_trail_vfx",         # VFX-04: weapon/projectile trails
        "create_aura_vfx",          # VFX-05: character aura/buff
        "create_corruption_shader", # VFX-06: corruption scaling shader
        "create_shader",            # VFX-07: dissolve/force field/water/foliage/outline
        "setup_post_processing",    # VFX-08: bloom/color grading/vignette/AO/DOF
        "create_screen_effect",     # VFX-09: camera shake/damage vignette/etc
        "create_ability_vfx",       # VFX-10: ability VFX + animation integration
    ],
    # Common params
    name: str = "default",
    # Particle params (VFX-01)
    rate: float = 100,
    lifetime: float = 1.0,
    size: float = 0.5,
    color: list[float] | None = None,
    shape: str = "cone",
    # Brand params (VFX-02)
    brand: str = "IRON",
    # Environment params (VFX-03)
    effect_type: str = "dust",
    # Trail params (VFX-04)
    width: float = 0.5,
    trail_lifetime: float = 0.5,
    # Aura params (VFX-05)
    aura_intensity: float = 1.0,
    aura_radius: float = 1.5,
    # Shader params (VFX-07)
    shader_type: str = "dissolve",
    # Post-processing params (VFX-08)
    bloom_intensity: float = 1.5,
    bloom_threshold: float = 0.9,
    vignette_intensity: float = 0.35,
    ao_intensity: float = 0.5,
    dof_focus_distance: float = 10.0,
    # Screen effect params (VFX-09)
    screen_effect_type: str = "camera_shake",
    shake_intensity: float = 1.0,
    # Ability params (VFX-10)
    vfx_prefab_path: str = "",
    anim_clip_path: str = "",
    keyframe_time: float = 0.0,
) -> str:
    """Unity VFX system -- VFX particles, shaders, post-processing, screen effects.

    This compound tool generates C# editor scripts and HLSL shader files
    for all VFX functionality: particle systems, brand damage effects,
    environmental VFX, trails, auras, shaders, post-processing, screen
    effects, and ability VFX with animation integration.

    Actions:
    - create_particle_vfx: Create VFX Graph particle prefab from params (VFX-01)
    - create_brand_vfx: Generate per-brand damage VFX (IRON/VENOM/SURGE/DREAD/BLAZE) (VFX-02)
    - create_environmental_vfx: Create dust/fireflies/snow/rain/ash VFX (VFX-03)
    - create_trail_vfx: Create weapon/projectile trail prefab (VFX-04)
    - create_aura_vfx: Create character aura/buff particle system (VFX-05)
    - create_corruption_shader: Generate corruption scaling HLSL shader (VFX-06)
    - create_shader: Generate HLSL shader (dissolve/force field/water/foliage/outline/damage overlay) (VFX-07)
    - setup_post_processing: Create post-processing Volume with bloom/vignette/AO/DOF (VFX-08)
    - create_screen_effect: Create screen effects (camera shake/damage vignette/etc) (VFX-09)
    - create_ability_vfx: Bind VFX to AnimationEvent for ability effects (VFX-10)

    Args:
        action: The VFX action to perform.
        name: Name for the generated VFX asset or script.
        rate: Particle emission rate per second (VFX-01).
        lifetime: Particle lifetime in seconds (VFX-01).
        size: Particle size (VFX-01).
        color: RGBA color as [r, g, b, a] (VFX-01/04/05).
        shape: Emission shape (VFX-01).
        brand: Brand name for damage VFX (VFX-02).
        effect_type: Environmental effect type (VFX-03).
        width: Trail width (VFX-04).
        trail_lifetime: Trail segment lifetime (VFX-04).
        aura_intensity: Aura emission intensity multiplier (VFX-05).
        aura_radius: Aura emission radius around character (VFX-05).
        shader_type: Shader type for create_shader (VFX-07).
        bloom_intensity: Post-processing bloom intensity (VFX-08).
        bloom_threshold: Post-processing bloom threshold (VFX-08).
        vignette_intensity: Post-processing vignette intensity (VFX-08).
        ao_intensity: Post-processing ambient occlusion intensity (VFX-08).
        dof_focus_distance: Post-processing depth of field focus distance (VFX-08).
        screen_effect_type: Screen effect type (VFX-09).
        shake_intensity: Camera shake intensity (VFX-09).
        vfx_prefab_path: Path to VFX prefab for ability binding (VFX-10).
        anim_clip_path: Path to animation clip for ability binding (VFX-10).
        keyframe_time: Animation keyframe time for VFX trigger (VFX-10).
    """
    try:
        if action == "create_particle_vfx":
            return await _handle_vfx_particle(name, rate, lifetime, size, color, shape)
        elif action == "create_brand_vfx":
            return await _handle_vfx_brand(brand)
        elif action == "create_environmental_vfx":
            return await _handle_vfx_environmental(effect_type)
        elif action == "create_trail_vfx":
            return await _handle_vfx_trail(name, width, color, trail_lifetime)
        elif action == "create_aura_vfx":
            return await _handle_vfx_aura(name, color, aura_intensity, aura_radius)
        elif action == "create_corruption_shader":
            return await _handle_vfx_corruption_shader(name)
        elif action == "create_shader":
            return await _handle_vfx_shader(name, shader_type)
        elif action == "setup_post_processing":
            return await _handle_vfx_post_processing(
                bloom_intensity, bloom_threshold, vignette_intensity,
                ao_intensity, dof_focus_distance,
            )
        elif action == "create_screen_effect":
            return await _handle_vfx_screen_effect(screen_effect_type, shake_intensity)
        elif action == "create_ability_vfx":
            return await _handle_vfx_ability(
                name, vfx_prefab_path, anim_clip_path, keyframe_time
            )
        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )
    except Exception as exc:
        logger.exception("unity_vfx action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# VFX action handlers
# ---------------------------------------------------------------------------


async def _handle_vfx_particle(
    name: str, rate: float, lifetime: float, size: float,
    color: list[float] | None, shape: str,
) -> str:
    """Create VFX Graph particle prefab (VFX-01)."""
    script = generate_particle_vfx_script(
        name=name, rate=rate, lifetime=lifetime, size=size, color=color, shape=shape,
    )
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_VFX_{name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_particle_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_particle_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Create Particle VFX/{name}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_brand(brand: str) -> str:
    """Create per-brand damage VFX (VFX-02)."""
    script = generate_brand_vfx_script(brand=brand)
    brand_upper = brand.upper()
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_BrandVFX_{brand_upper}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_brand_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_brand_vfx",
            "brand": brand_upper,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Brand Damage/{brand_upper}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_environmental(effect_type: str) -> str:
    """Create environmental VFX (VFX-03)."""
    script = generate_environmental_vfx_script(effect_type=effect_type)
    safe = effect_type.capitalize()
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_EnvVFX_{safe}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_environmental_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_environmental_vfx",
            "effect_type": effect_type,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Environment/{safe}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_trail(
    name: str, width: float, color: list[float] | None, lifetime: float,
) -> str:
    """Create weapon/projectile trail VFX (VFX-04)."""
    script = generate_trail_vfx_script(
        name=name, width=width, color=color, lifetime=lifetime,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_Trail_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_trail_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_trail_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Create Trail/{name}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_aura(
    name: str, color: list[float] | None, intensity: float, radius: float,
) -> str:
    """Create character aura/buff VFX (VFX-05)."""
    script = generate_aura_vfx_script(
        name=name, color=color, intensity=intensity, radius=radius,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_Aura_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_aura_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_aura_vfx",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Create Aura/{name}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_corruption_shader(name: str) -> str:
    """Generate corruption scaling HLSL shader (VFX-06)."""
    shader = generate_corruption_shader()
    shader_path = f"Assets/Shaders/Generated/{name}_Corruption.shader"

    try:
        abs_path = _write_to_unity(shader, shader_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_corruption_shader", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_corruption_shader",
            "shader_path": abs_path,
            "shader_name": "VeilBreakers/Corruption",
            "properties": [
                "_CorruptionAmount (Range 0-1)",
                "_CorruptionColor",
                "_VeinScale",
            ],
            "next_steps": [
                "Call mcp-unity recompile_scripts to import the new shader",
                "Create a material using shader 'VeilBreakers/Corruption'",
                "Adjust _CorruptionAmount from 0 (clean) to 1 (fully corrupted)",
            ],
        },
        indent=2,
    )


async def _handle_vfx_shader(name: str, shader_type: str) -> str:
    """Generate HLSL shader by type (VFX-07)."""
    shader_generators = {
        "dissolve": generate_dissolve_shader,
        "force_field": generate_force_field_shader,
        "water": generate_water_shader,
        "foliage": generate_foliage_shader,
        "outline": generate_outline_shader,
        "damage_overlay": generate_damage_overlay_shader,
    }

    if shader_type not in shader_generators:
        return json.dumps({
            "status": "error",
            "action": "create_shader",
            "message": (
                f"Unknown shader_type: '{shader_type}'. "
                f"Valid types: {sorted(shader_generators)}"
            ),
        })

    shader = shader_generators[shader_type]()
    type_label = shader_type.title().replace("_", "")
    shader_path = f"Assets/Shaders/Generated/{name}_{type_label}.shader"

    try:
        abs_path = _write_to_unity(shader, shader_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_shader", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_shader",
            "shader_type": shader_type,
            "shader_path": abs_path,
            "shader_name": f"VeilBreakers/{type_label}",
            "next_steps": [
                "Call mcp-unity recompile_scripts to import the new shader",
                f"Create a material using shader 'VeilBreakers/{type_label}'",
            ],
        },
        indent=2,
    )


async def _handle_vfx_post_processing(
    bloom_intensity: float,
    bloom_threshold: float,
    vignette_intensity: float,
    ao_intensity: float,
    dof_focus_distance: float,
) -> str:
    """Create post-processing Volume (VFX-08)."""
    script = generate_post_processing_script(
        bloom_intensity=bloom_intensity,
        bloom_threshold=bloom_threshold,
        vignette_intensity=vignette_intensity,
        ao_intensity=ao_intensity,
        dof_focus_distance=dof_focus_distance,
    )
    script_path = "Assets/Editor/Generated/VFX/VeilBreakers_PostProcessing.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_post_processing", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_post_processing",
            "script_path": abs_path,
            "settings": {
                "bloom": bloom_intensity,
                "vignette": vignette_intensity,
                "ao": ao_intensity,
                "dof_focus": dof_focus_distance,
            },
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Setup Post Processing"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_screen_effect(effect_type: str, intensity: float) -> str:
    """Create screen effect (VFX-09)."""
    script = generate_screen_effect_script(
        effect_type=effect_type, intensity=intensity,
    )
    safe_type = effect_type.replace("_", " ").title().replace(" ", "")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_ScreenEffect_{safe_type}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_screen_effect", "message": str(exc)}
        )

    label = effect_type.replace("_", " ").title()

    return json.dumps(
        {
            "status": "success",
            "action": "create_screen_effect",
            "effect_type": effect_type,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Screen Effects/{label}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_vfx_ability(
    name: str, vfx_prefab_path: str, anim_clip_path: str, keyframe_time: float,
) -> str:
    """Bind VFX to AnimationEvent for ability effects (VFX-10)."""
    vfx_prefab = vfx_prefab_path or f"Assets/Prefabs/VFX/{name}.prefab"
    anim_clip = anim_clip_path or f"Assets/Animations/{name}.anim"

    script = generate_ability_vfx_script(
        ability_name=name,
        vfx_prefab=vfx_prefab,
        anim_clip=anim_clip,
        keyframe_time=keyframe_time,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/VFX/VeilBreakers_AbilityVFX_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_ability_vfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_ability_vfx",
            "ability": name,
            "vfx_prefab": vfx_prefab,
            "anim_clip": anim_clip,
            "keyframe_time": keyframe_time,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/VFX/Ability VFX/{name}"',
                f"Ensure VFX prefab exists at: {vfx_prefab}",
                f"Ensure animation clip exists at: {anim_clip}",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Audio tool -- lazy ElevenLabs client
# ---------------------------------------------------------------------------

_audio_client: ElevenLabsAudioClient | None = None


def _get_audio_client() -> ElevenLabsAudioClient:
    """Lazily initialise the ElevenLabs audio client."""
    global _audio_client
    if _audio_client is None:
        _audio_client = ElevenLabsAudioClient(
            api_key=settings.elevenlabs_api_key or None,
            unity_project_path=settings.unity_project_path,
        )
    return _audio_client


@mcp.tool()
async def unity_audio(
    action: Literal[
        "generate_sfx",             # AUD-01: AI SFX from text
        "generate_music_loop",      # AUD-02: combat/exploration/boss/town loops
        "generate_voice_line",      # AUD-03: NPC/monster voice synthesis
        "generate_ambient",         # AUD-04: biome ambient soundscape
        "setup_footstep_system",    # AUD-05: surface-material footstep mapping
        "setup_adaptive_music",     # AUD-06: layered music responding to game state
        "setup_audio_zones",        # AUD-07: reverb zones for caves/outdoor/indoor
        "setup_audio_mixer",        # AUD-08: Unity Audio Mixer with groups
        "setup_audio_pool_manager", # AUD-09: audio pooling, priority, ducking
        "assign_animation_sfx",     # AUD-10: SFX at animation event keyframes
    ],
    # Common
    name: str = "default",
    # SFX/Music/Voice params
    description: str = "",
    duration_seconds: float = 2.0,
    theme: str = "combat",
    text: str = "",
    voice_id: str = "default",
    # Ambient params
    biome: str = "forest",
    layers: list[str] | None = None,
    # Footstep params
    surfaces: list[str] | None = None,
    # Adaptive music params
    music_layers: list[str] | None = None,
    # Audio zone params
    zone_type: str = "cave",
    # Pool manager params
    pool_size: int = 16,
    max_sources: int = 32,
    # Mixer params
    groups: list[str] | None = None,
    # Animation event params
    events: list[dict] | None = None,
    anim_clip_path: str = "",
) -> str:
    """Unity Audio system -- AI audio generation and C# audio infrastructure.

    This compound tool covers all audio functionality: AI-generated sound
    effects, music loops, voice lines, and ambient soundscapes via ElevenLabs,
    plus Unity audio infrastructure setup (mixer, pool manager, footstep
    system, adaptive music, audio zones, animation event SFX).

    Actions:
    - generate_sfx: Generate AI sound effect from text description (AUD-01)
    - generate_music_loop: Generate loopable music track (AUD-02)
    - generate_voice_line: Synthesise NPC/monster voice line (AUD-03)
    - generate_ambient: Generate layered ambient soundscape (AUD-04)
    - setup_footstep_system: Generate footstep manager C# scripts (AUD-05)
    - setup_adaptive_music: Generate adaptive music manager C# script (AUD-06)
    - setup_audio_zones: Generate audio reverb zone C# script (AUD-07)
    - setup_audio_mixer: Generate audio mixer setup C# script (AUD-08)
    - setup_audio_pool_manager: Generate audio pool manager C# script (AUD-09)
    - assign_animation_sfx: Generate animation event SFX binding C# script (AUD-10)

    Args:
        action: The audio action to perform.
        name: Name for the generated asset or script.
        description: Text description for SFX generation.
        duration_seconds: Duration for generated audio (seconds).
        theme: Music theme for loop generation.
        text: Dialogue text for voice line synthesis.
        voice_id: ElevenLabs voice ID for voice synthesis.
        biome: Biome type for ambient soundscape generation.
        layers: Layer descriptions for ambient generation.
        surfaces: Surface types for footstep system.
        music_layers: Layer/state names for adaptive music.
        zone_type: Environment type for audio zones.
        pool_size: Initial pool size for audio pool manager.
        max_sources: Maximum audio sources for pool manager.
        groups: Mixer group names for audio mixer setup.
        events: Animation event definitions for SFX binding.
        anim_clip_path: Path to animation clip for event binding.
    """
    try:
        if action == "generate_sfx":
            return await _handle_audio_generate_sfx(name, description, duration_seconds)
        elif action == "generate_music_loop":
            return await _handle_audio_generate_music_loop(name, theme, duration_seconds)
        elif action == "generate_voice_line":
            return await _handle_audio_generate_voice_line(name, text, voice_id)
        elif action == "generate_ambient":
            return await _handle_audio_generate_ambient(name, biome, layers)
        elif action == "setup_footstep_system":
            return await _handle_audio_setup_footstep(name, surfaces)
        elif action == "setup_adaptive_music":
            return await _handle_audio_setup_adaptive_music(name, music_layers)
        elif action == "setup_audio_zones":
            return await _handle_audio_setup_zones(name, zone_type)
        elif action == "setup_audio_mixer":
            return await _handle_audio_setup_mixer(groups)
        elif action == "setup_audio_pool_manager":
            return await _handle_audio_setup_pool_manager(name, pool_size, max_sources)
        elif action == "assign_animation_sfx":
            return await _handle_audio_assign_animation_sfx(name, events)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_audio action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Audio action handlers
# ---------------------------------------------------------------------------


async def _handle_audio_generate_sfx(
    name: str, description: str, duration_seconds: float
) -> str:
    """Generate AI SFX from text description (AUD-01)."""
    client = _get_audio_client()
    output_rel = f"Assets/Resources/Audio/SFX/{name}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_sfx(
        description=description,
        duration_seconds=duration_seconds,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_sfx",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "duration": result["duration"],
            "stub": result["stub"],
            "description": description,
            "next_steps": [
                "Audio file written. Import into Unity via AssetDatabase.Refresh.",
                "Call unity_editor action='recompile' to pick up new assets.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_music_loop(
    name: str, theme: str, duration_seconds: float
) -> str:
    """Generate loopable music track (AUD-02)."""
    client = _get_audio_client()
    output_rel = f"Assets/Resources/Audio/Music/{name}_{theme}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_music_loop(
        theme=theme,
        duration_seconds=duration_seconds,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_music_loop",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "duration": result["duration"],
            "stub": result["stub"],
            "theme": theme,
            "next_steps": [
                "Music loop written. Import into Unity via AssetDatabase.Refresh.",
                "Assign to AdaptiveMusicManager via inspector or script.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_voice_line(
    name: str, text: str, voice_id: str
) -> str:
    """Synthesise NPC/monster voice line (AUD-03)."""
    client = _get_audio_client()
    output_rel = f"Assets/Resources/Audio/Voice/{name}.mp3"

    if settings.unity_project_path:
        output_path = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_path = output_rel

    result = client.generate_voice_line(
        text=text,
        voice_id=voice_id,
        output_path=output_path,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_voice_line",
            "audio_path": result["path"],
            "relative_path": output_rel,
            "stub": result["stub"],
            "text": text,
            "voice_id": voice_id,
            "next_steps": [
                "Voice line written. Import into Unity via AssetDatabase.Refresh.",
                "Assign to dialogue system or NPC AudioSource.",
            ],
        },
        indent=2,
    )


async def _handle_audio_generate_ambient(
    name: str, biome: str, layers: list[str] | None
) -> str:
    """Generate layered ambient soundscape (AUD-04)."""
    client = _get_audio_client()
    output_rel = f"Assets/Resources/Audio/Ambient/{biome}"

    if settings.unity_project_path:
        output_dir = str(Path(settings.unity_project_path) / output_rel)
    else:
        output_dir = output_rel

    result = client.generate_ambient_layers(
        biome=biome,
        layers=layers,
        output_dir=output_dir,
    )

    return json.dumps(
        {
            "status": "success",
            "action": "generate_ambient",
            "layer_paths": result["layer_paths"],
            "biome": biome,
            "layer_count": len(result["layer_paths"]),
            "stub": result["stub"],
            "next_steps": [
                f"Generated {len(result['layer_paths'])} ambient layers for {biome} biome.",
                "Import into Unity via AssetDatabase.Refresh.",
                "Layer these AudioClips in an AudioSource group for rich ambient sound.",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_footstep(
    name: str, surfaces: list[str] | None
) -> str:
    """Generate footstep manager C# scripts (AUD-05)."""
    script = generate_footstep_manager_script(surfaces=surfaces)
    script_path = f"Assets/Scripts/Runtime/Audio/VeilBreakers_FootstepManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_footstep_system", "message": str(exc)}
        )

    effective_surfaces = surfaces or ["stone", "wood", "grass", "metal", "water"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_footstep_system",
            "script_path": abs_path,
            "surfaces": effective_surfaces,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new scripts",
                "Attach VeilBreakers_FootstepManager to the player character",
                "Create a FootstepSoundBank via Assets > Create > VeilBreakers > Audio > Footstep Sound Bank",
                f"Assign AudioClips for surfaces: {', '.join(effective_surfaces)}",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_adaptive_music(
    name: str, music_layers: list[str] | None
) -> str:
    """Generate adaptive music manager C# script (AUD-06)."""
    script = generate_adaptive_music_script(layers=music_layers)
    script_path = f"Assets/Scripts/Runtime/Audio/VeilBreakers_AdaptiveMusicManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_adaptive_music", "message": str(exc)}
        )

    effective_layers = music_layers or ["Exploration", "Combat", "Boss", "Town", "Stealth"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_adaptive_music",
            "script_path": abs_path,
            "layers": effective_layers,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Add VeilBreakers_AdaptiveMusicManager to a persistent GameObject",
                f"Assign AudioClips for states: {', '.join(effective_layers)}",
                "Call SetGameState(GameState.Combat) etc. from game logic",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_zones(name: str, zone_type: str) -> str:
    """Generate audio reverb zone C# script (AUD-07)."""
    script = generate_audio_zone_script(zone_type=zone_type)
    zone_label = zone_type.capitalize()
    script_path = f"Assets/Editor/Generated/Audio/VeilBreakers_AudioZone_{zone_label}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_zones", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_zones",
            "script_path": abs_path,
            "zone_type": zone_type,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/Audio/Create {zone_label} Reverb Zone"',
                "Position the reverb zone in the scene as needed",
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_mixer(groups: list[str] | None) -> str:
    """Generate audio mixer setup C# script (AUD-08)."""
    script = generate_audio_mixer_setup_script(groups=groups)
    script_path = "Assets/Editor/Generated/Audio/VeilBreakers_AudioMixerSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_mixer", "message": str(exc)}
        )

    effective_groups = groups or ["Master", "SFX", "Music", "Voice", "Ambient", "UI"]

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_mixer",
            "script_path": abs_path,
            "groups": effective_groups,
            "next_steps": [
                "First, create an AudioMixer at Assets/Audio/VeilBreakersMixer.mixer in Unity",
                f"Add these groups to the mixer: {', '.join(effective_groups)}",
                "Call mcp-unity recompile_scripts to compile the setup script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Audio/Setup Audio Mixer"',
            ],
        },
        indent=2,
    )


async def _handle_audio_setup_pool_manager(
    name: str, pool_size: int, max_sources: int
) -> str:
    """Generate audio pool manager C# script (AUD-09)."""
    script = generate_audio_pool_manager_script(
        pool_size=pool_size, max_sources=max_sources
    )
    script_path = "Assets/Scripts/Runtime/Audio/VeilBreakers_AudioPoolManager.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_audio_pool_manager", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_audio_pool_manager",
            "script_path": abs_path,
            "pool_size": pool_size,
            "max_sources": max_sources,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Add VeilBreakers_AudioPoolManager to a persistent GameObject",
                f"Pool starts with {pool_size} AudioSources, grows up to {max_sources}",
                "Call VeilBreakers_AudioPoolManager.Instance.Play(clip, position, priority)",
            ],
        },
        indent=2,
    )


async def _handle_audio_assign_animation_sfx(
    name: str, events: list[dict] | None
) -> str:
    """Generate animation event SFX binding C# script (AUD-10)."""
    script = generate_animation_event_sfx_script(events=events)
    script_path = "Assets/Editor/Generated/Audio/VeilBreakers_AnimationEventSFX.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "assign_animation_sfx", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "assign_animation_sfx",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Select an AnimationClip in the Unity Project window",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Audio/Assign Animation SFX Events"',
                "The script will bind SFX function calls to the specified animation keyframes",
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# UI tool
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_ui(
    action: Literal[
        "generate_ui_screen",   # UI-05: UXML + USS from description
        "validate_layout",      # UI-02: check overlaps, zero-size, overflow
        "test_responsive",      # UI-03: capture at 5 resolutions
        "check_contrast",       # UI-06: WCAG AA contrast validation
        "compare_screenshots",  # UI-07: visual regression detection
    ],
    # Screen generation params
    screen_spec: dict | None = None,
    theme: str = "dark_fantasy",
    screen_name: str = "default",
    # Validation params
    uxml_path: str = "",
    uss_path: str = "",
    uxml_content: str = "",
    uss_content: str = "",
    # Responsive test params
    resolutions: list[list[int]] | None = None,
    # Screenshot comparison params
    reference_path: str = "",
    current_path: str = "",
    diff_threshold: float = 0.01,
) -> str:
    """Unity UI system -- UXML/USS generation, layout validation, WCAG contrast, responsive testing, visual regression.

    This compound tool covers all UI functionality: generating UI screens from
    text descriptions as UXML + USS with dark fantasy theming, validating layout
    for overlaps and sizing issues, checking WCAG color contrast compliance,
    testing responsiveness at multiple resolutions, and detecting visual
    regressions through screenshot comparison.

    Actions:
    - generate_ui_screen: Generate UXML + USS from screen spec with dark fantasy styling (UI-05)
    - validate_layout: Check UXML for overlaps, zero-size elements, overflow (UI-02)
    - test_responsive: Generate C# script to capture screenshots at 5 resolutions (UI-03)
    - check_contrast: Validate WCAG AA contrast ratios for text elements (UI-06)
    - compare_screenshots: Detect visual regressions between screenshot pairs (UI-07)

    Args:
        action: The UI action to perform.
        screen_spec: Screen specification dict for generate_ui_screen.
        theme: USS theme name (default: "dark_fantasy").
        screen_name: Name for the generated screen files.
        uxml_path: Path to UXML file (relative to Unity project) for validation.
        uss_path: Path to USS file (relative to Unity project) for contrast check.
        uxml_content: Inline UXML content (alternative to uxml_path).
        uss_content: Inline USS content (alternative to uss_path).
        resolutions: List of [width, height] pairs for responsive testing.
        reference_path: Path to reference screenshot for comparison.
        current_path: Path to current screenshot for comparison.
        diff_threshold: Maximum acceptable diff percentage (0.01 = 1%).
    """
    try:
        if action == "generate_ui_screen":
            return await _handle_ui_generate_screen(screen_spec, theme, screen_name)
        elif action == "validate_layout":
            return await _handle_ui_validate_layout(uxml_path, uxml_content)
        elif action == "test_responsive":
            return await _handle_ui_test_responsive(
                uxml_path or f"Assets/Resources/UI/{screen_name}.uxml",
                screen_name,
                resolutions,
            )
        elif action == "check_contrast":
            return await _handle_ui_check_contrast(
                uxml_path, uss_path, uxml_content, uss_content
            )
        elif action == "compare_screenshots":
            return await _handle_ui_compare_screenshots(
                reference_path, current_path, diff_threshold
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_ui action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# UI action handlers
# ---------------------------------------------------------------------------


async def _handle_ui_generate_screen(
    screen_spec: dict | None,
    theme: str,
    screen_name: str,
) -> str:
    """Generate UXML + USS from screen spec (UI-05)."""
    if not screen_spec:
        return json.dumps({
            "status": "error",
            "action": "generate_ui_screen",
            "message": "screen_spec is required for generate_ui_screen action",
        })

    uxml = generate_uxml_screen(screen_spec)
    uss = generate_uss_stylesheet(theme)

    uxml_rel = f"Assets/Resources/UI/{screen_name}.uxml"
    uss_rel = f"Assets/Resources/UI/{screen_name}.uss"

    try:
        uxml_abs = _write_to_unity(uxml, uxml_rel)
        uss_abs = _write_to_unity(uss, uss_rel)
    except ValueError as exc:
        return json.dumps({
            "status": "error",
            "action": "generate_ui_screen",
            "message": str(exc),
        })

    # Run validation on generated UXML
    body = uxml.split("\n", 1)[1] if "\n" in uxml else uxml
    layout_result = validate_uxml_layout(body)

    # Run contrast check on generated UXML + USS
    contrast_results = validate_uxml_contrast(body, uss)
    contrast_violations = [r for r in contrast_results if not r["passes"]]

    return json.dumps(
        {
            "status": "success",
            "action": "generate_ui_screen",
            "uxml_path": uxml_abs,
            "uss_path": uss_abs,
            "screen_name": screen_name,
            "theme": theme,
            "layout_valid": layout_result["valid"],
            "layout_issues": layout_result["issues"],
            "contrast_violations": contrast_violations,
            "next_steps": [
                "Call mcp-unity recompile_scripts to pick up new UI files",
                f"UXML: {uxml_rel}",
                f"USS: {uss_rel}",
                "Open the UXML in Unity's UI Builder for visual editing",
            ],
        },
        indent=2,
    )


async def _handle_ui_validate_layout(uxml_path: str, uxml_content: str) -> str:
    """Validate UXML layout for issues (UI-02)."""
    content = uxml_content
    if not content and uxml_path:
        if settings.unity_project_path:
            full_path = Path(settings.unity_project_path) / uxml_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
            else:
                return json.dumps({
                    "status": "error",
                    "action": "validate_layout",
                    "message": f"UXML file not found: {full_path}",
                })
        else:
            return json.dumps({
                "status": "error",
                "action": "validate_layout",
                "message": "unity_project_path not configured and no uxml_content provided",
            })

    if not content:
        return json.dumps({
            "status": "error",
            "action": "validate_layout",
            "message": "No UXML content provided. Use uxml_path or uxml_content.",
        })

    result = validate_uxml_layout(content)

    return json.dumps(
        {
            "status": "success",
            "action": "validate_layout",
            "valid": result["valid"],
            "issues": result["issues"],
            "issue_count": len(result["issues"]),
        },
        indent=2,
    )


async def _handle_ui_test_responsive(
    uxml_path: str,
    screen_name: str,
    resolutions: list[list[int]] | None,
) -> str:
    """Generate responsive test C# script (UI-03)."""
    # Convert list-of-lists to list-of-tuples if provided
    res_tuples = None
    if resolutions:
        res_tuples = [(r[0], r[1]) for r in resolutions]

    script = generate_responsive_test_script(uxml_path, resolutions=res_tuples)
    script_rel = f"Assets/Editor/Generated/UI/ResponsiveTest_{screen_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_rel)
    except ValueError as exc:
        return json.dumps({
            "status": "error",
            "action": "test_responsive",
            "message": str(exc),
        })

    return json.dumps(
        {
            "status": "success",
            "action": "test_responsive",
            "script_path": abs_path,
            "screen_name": screen_name,
            "resolutions": resolutions or [[w, h] for w, h in [
                (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160), (800, 600)
            ]],
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the test script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/UI/Responsive Test {uxml_path.split("/")[-1].replace(".uxml", "")}"',
                "Screenshots will be saved to Assets/Screenshots/Responsive/",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_ui_check_contrast(
    uxml_path: str,
    uss_path: str,
    uxml_content: str,
    uss_content: str,
) -> str:
    """Validate WCAG AA contrast ratios (UI-06)."""
    uxml = uxml_content
    uss = uss_content

    # Read UXML from file if path provided and no inline content
    if not uxml and uxml_path and settings.unity_project_path:
        full = Path(settings.unity_project_path) / uxml_path
        if full.exists():
            uxml = full.read_text(encoding="utf-8")

    # Read USS from file if path provided and no inline content
    if not uss and uss_path and settings.unity_project_path:
        full = Path(settings.unity_project_path) / uss_path
        if full.exists():
            uss = full.read_text(encoding="utf-8")

    if not uxml or not uss:
        return json.dumps({
            "status": "error",
            "action": "check_contrast",
            "message": "Both UXML and USS content are required (via paths or inline content).",
        })

    results = validate_uxml_contrast(uxml, uss)
    passing = [r for r in results if r["passes"]]
    failing = [r for r in results if not r["passes"]]

    # Convert tuples to lists for JSON serialization
    for r in results:
        r["foreground"] = list(r["foreground"])
        r["background"] = list(r["background"])

    return json.dumps(
        {
            "status": "success",
            "action": "check_contrast",
            "total_checked": len(results),
            "passing": len(passing),
            "failing": len(failing),
            "wcag_aa_compliant": len(failing) == 0,
            "results": results,
        },
        indent=2,
    )


async def _handle_ui_compare_screenshots(
    reference_path: str,
    current_path: str,
    diff_threshold: float,
) -> str:
    """Compare screenshots for visual regression (UI-07)."""
    if not reference_path or not current_path:
        return json.dumps({
            "status": "error",
            "action": "compare_screenshots",
            "message": "Both reference_path and current_path are required.",
        })

    # Resolve paths relative to Unity project if needed
    ref = reference_path
    cur = current_path
    if settings.unity_project_path:
        ref_full = Path(settings.unity_project_path) / reference_path
        cur_full = Path(settings.unity_project_path) / current_path
        if ref_full.exists():
            ref = str(ref_full)
        if cur_full.exists():
            cur = str(cur_full)

    result = _compare_screenshots(ref, cur, threshold=diff_threshold)

    return json.dumps(
        {
            "status": "success",
            "action": "compare_screenshots",
            "match": result["match"],
            "diff_percentage": result["diff_percentage"],
            "diff_threshold": diff_threshold,
            "diff_image_path": result.get("diff_image_path"),
            "reference_size": list(result["reference_size"]),
            "current_size": list(result["current_size"]),
            "visual_regression_detected": not result["match"],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Scene tool -- compound tool covering SCENE-01 through SCENE-07
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_scene(
    action: Literal[
        "setup_terrain",            # SCENE-01: terrain from heightmap + splatmaps
        "scatter_objects",          # SCENE-02: density-based object placement
        "setup_lighting",           # SCENE-03: directional light, fog, post-processing
        "bake_navmesh",             # SCENE-04: NavMesh with agent settings
        "create_animator",          # SCENE-05: Animator Controller with states/transitions
        "configure_avatar",         # SCENE-06: Humanoid/Generic bone mapping
        "setup_animation_rigging",  # SCENE-07: TwoBoneIK, MultiAim constraints
    ],
    # Common
    name: str = "default",
    # Terrain params
    heightmap_path: str = "",
    terrain_size: list[float] | None = None,
    terrain_resolution: int = 513,
    splatmap_layers: list[dict] | None = None,
    # Scatter params
    prefab_paths: list[str] | None = None,
    density: float = 0.5,
    min_slope: float = 0.0,
    max_slope: float = 45.0,
    min_altitude: float = 0.0,
    max_altitude: float = 1000.0,
    scatter_seed: int = 42,
    # Lighting params
    sun_color: list[float] | None = None,
    sun_intensity: float = 1.0,
    ambient_color: list[float] | None = None,
    fog_enabled: bool = True,
    fog_color: list[float] | None = None,
    fog_density: float = 0.01,
    skybox_material: str = "",
    time_of_day: str = "noon",
    # NavMesh params
    agent_radius: float = 0.5,
    agent_height: float = 2.0,
    nav_max_slope: float = 45.0,
    step_height: float = 0.4,
    nav_links: list[dict] | None = None,
    # Animator params
    states: list[dict] | None = None,
    transitions: list[dict] | None = None,
    parameters: list[dict] | None = None,
    blend_trees: list[dict] | None = None,
    # Avatar params
    fbx_path: str = "",
    animation_type: str = "Humanoid",
    bone_mapping: dict | None = None,
    # Animation Rigging params
    constraints: list[dict] | None = None,
) -> str:
    """Unity Scene setup -- terrain, object scattering, lighting, NavMesh, animation.

    This compound tool generates C# editor scripts for complete Unity scene
    setup: terrain from heightmaps, density-based object scattering, atmospheric
    lighting with post-processing, NavMesh baking for AI navigation, Animator
    Controllers with blend trees, avatar configuration, and Animation Rigging
    constraints.

    Actions:
    - setup_terrain: Create terrain from RAW heightmap with splatmaps (SCENE-01)
    - scatter_objects: Density-based object placement filtered by slope/altitude (SCENE-02)
    - setup_lighting: Directional light, fog, post-processing Volume (SCENE-03)
    - bake_navmesh: NavMesh with agent radius/height/slope settings (SCENE-04)
    - create_animator: Animator Controller with states, transitions, blend trees (SCENE-05)
    - configure_avatar: Set Humanoid/Generic animation type with bone mapping (SCENE-06)
    - setup_animation_rigging: TwoBoneIK and MultiAim constraints (SCENE-07)

    Args:
        action: The scene action to perform.
        name: Name for the generated asset or script.
        heightmap_path: Path to RAW heightmap file (SCENE-01).
        terrain_size: Terrain [width, height, length] (SCENE-01).
        terrain_resolution: Heightmap resolution e.g. 513, 1025 (SCENE-01).
        splatmap_layers: List of {texture_path, tiling} dicts (SCENE-01).
        prefab_paths: Prefab paths for scattering (SCENE-02).
        density: Scatter density 0-1 (SCENE-02).
        min_slope: Min terrain slope filter in degrees (SCENE-02).
        max_slope: Max terrain slope filter in degrees (SCENE-02).
        min_altitude: Min terrain height filter (SCENE-02).
        max_altitude: Max terrain height filter (SCENE-02).
        scatter_seed: Random seed for scatter (SCENE-02).
        sun_color: RGB sun color [r, g, b] (SCENE-03).
        sun_intensity: Sun light intensity (SCENE-03).
        ambient_color: RGB ambient color [r, g, b] (SCENE-03).
        fog_enabled: Enable fog (SCENE-03).
        fog_color: RGB fog color [r, g, b] (SCENE-03).
        fog_density: Fog density (SCENE-03).
        skybox_material: Path to skybox material (SCENE-03).
        time_of_day: Preset: dawn/noon/dusk/night/overcast (SCENE-03).
        agent_radius: NavMesh agent radius (SCENE-04).
        agent_height: NavMesh agent height (SCENE-04).
        nav_max_slope: NavMesh max walkable slope (SCENE-04).
        step_height: NavMesh max step height (SCENE-04).
        nav_links: NavMesh links [{start, end, width}] (SCENE-04).
        states: Animator states [{name, motion_path}] (SCENE-05).
        transitions: Animator transitions [{from_state, to_state, conditions, has_exit_time}] (SCENE-05).
        parameters: Animator parameters [{name, type}] (SCENE-05).
        blend_trees: Blend trees [{name, blend_param, children}] (SCENE-05).
        fbx_path: Path to FBX model (SCENE-06).
        animation_type: "Humanoid" or "Generic" (SCENE-06).
        bone_mapping: Unity-to-model bone name mapping (SCENE-06).
        constraints: Rigging constraints [{type, target_path, ...}] (SCENE-07).
    """
    try:
        if action == "setup_terrain":
            return await _handle_scene_setup_terrain(
                heightmap_path, terrain_size, terrain_resolution, splatmap_layers
            )
        elif action == "scatter_objects":
            return await _handle_scene_scatter_objects(
                prefab_paths, density, min_slope, max_slope,
                min_altitude, max_altitude, scatter_seed,
            )
        elif action == "setup_lighting":
            return await _handle_scene_setup_lighting(
                sun_color, sun_intensity, ambient_color, fog_enabled,
                fog_color, fog_density, skybox_material, time_of_day,
            )
        elif action == "bake_navmesh":
            return await _handle_scene_bake_navmesh(
                agent_radius, agent_height, nav_max_slope, step_height, nav_links,
            )
        elif action == "create_animator":
            return await _handle_scene_create_animator(
                name, states, transitions, parameters, blend_trees,
            )
        elif action == "configure_avatar":
            return await _handle_scene_configure_avatar(
                fbx_path, animation_type, bone_mapping,
            )
        elif action == "setup_animation_rigging":
            return await _handle_scene_setup_animation_rigging(name, constraints)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_scene action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Scene action handlers
# ---------------------------------------------------------------------------


async def _handle_scene_setup_terrain(
    heightmap_path: str,
    terrain_size: list[float] | None,
    terrain_resolution: int,
    splatmap_layers: list[dict] | None,
) -> str:
    """Create terrain from heightmap (SCENE-01)."""
    if not heightmap_path:
        return json.dumps({
            "status": "error",
            "action": "setup_terrain",
            "message": "heightmap_path is required for setup_terrain action",
        })

    size_tuple = tuple(terrain_size) if terrain_size and len(terrain_size) == 3 else (1000, 600, 1000)

    script = generate_terrain_setup_script(
        heightmap_path=heightmap_path,
        size=size_tuple,
        resolution=terrain_resolution,
        splatmap_layers=splatmap_layers,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_TerrainSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_terrain", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_terrain",
            "script_path": abs_path,
            "heightmap_path": heightmap_path,
            "terrain_size": list(size_tuple),
            "resolution": terrain_resolution,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Setup Terrain"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_scatter_objects(
    prefab_paths: list[str] | None,
    density: float,
    min_slope: float,
    max_slope: float,
    min_altitude: float,
    max_altitude: float,
    seed: int,
) -> str:
    """Scatter objects on terrain (SCENE-02)."""
    if not prefab_paths:
        return json.dumps({
            "status": "error",
            "action": "scatter_objects",
            "message": "prefab_paths is required for scatter_objects action",
        })

    script = generate_object_scatter_script(
        prefab_paths=prefab_paths,
        density=density,
        min_slope=min_slope,
        max_slope=max_slope,
        min_altitude=min_altitude,
        max_altitude=max_altitude,
        seed=seed,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_ObjectScatter.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "scatter_objects", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "scatter_objects",
            "script_path": abs_path,
            "prefab_paths": prefab_paths,
            "density": density,
            "seed": seed,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Scatter Objects"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_setup_lighting(
    sun_color: list[float] | None,
    sun_intensity: float,
    ambient_color: list[float] | None,
    fog_enabled: bool,
    fog_color: list[float] | None,
    fog_density: float,
    skybox_material: str,
    time_of_day: str,
) -> str:
    """Setup scene lighting, fog, and post-processing (SCENE-03)."""
    script = generate_lighting_setup_script(
        sun_color=sun_color,
        sun_intensity=sun_intensity,
        ambient_color=ambient_color,
        fog_enabled=fog_enabled,
        fog_color=fog_color,
        fog_density=fog_density,
        skybox_material=skybox_material,
        time_of_day=time_of_day,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_LightingSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_lighting", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_lighting",
            "script_path": abs_path,
            "time_of_day": time_of_day,
            "fog_enabled": fog_enabled,
            "sun_intensity": sun_intensity,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Setup Lighting"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_bake_navmesh(
    agent_radius: float,
    agent_height: float,
    max_slope: float,
    step_height: float,
    nav_links: list[dict] | None,
) -> str:
    """Bake NavMesh with agent settings (SCENE-04)."""
    script = generate_navmesh_bake_script(
        agent_radius=agent_radius,
        agent_height=agent_height,
        max_slope=max_slope,
        step_height=step_height,
        nav_links=nav_links,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_NavMeshBake.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "bake_navmesh", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "bake_navmesh",
            "script_path": abs_path,
            "agent_radius": agent_radius,
            "agent_height": agent_height,
            "max_slope": max_slope,
            "step_height": step_height,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Bake NavMesh"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_create_animator(
    name: str,
    states: list[dict] | None,
    transitions: list[dict] | None,
    parameters: list[dict] | None,
    blend_trees: list[dict] | None,
) -> str:
    """Create Animator Controller (SCENE-05)."""
    if not states:
        return json.dumps({
            "status": "error",
            "action": "create_animator",
            "message": "states is required for create_animator action (at least one state)",
        })

    script = generate_animator_controller_script(
        name=name,
        states=states,
        transitions=transitions or [],
        parameters=parameters or [],
        blend_trees=blend_trees,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/Scene/VeilBreakers_Animator_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_animator", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_animator",
            "name": name,
            "script_path": abs_path,
            "state_count": len(states),
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Create Animator/{name}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_configure_avatar(
    fbx_path: str,
    animation_type: str,
    bone_mapping: dict | None,
) -> str:
    """Configure avatar animation type (SCENE-06)."""
    if not fbx_path:
        return json.dumps({
            "status": "error",
            "action": "configure_avatar",
            "message": "fbx_path is required for configure_avatar action",
        })

    script = generate_avatar_config_script(
        fbx_path=fbx_path,
        animation_type=animation_type,
        bone_mapping=bone_mapping,
    )
    script_path = "Assets/Editor/Generated/Scene/VeilBreakers_AvatarConfig.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "configure_avatar", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "configure_avatar",
            "script_path": abs_path,
            "fbx_path": fbx_path,
            "animation_type": animation_type,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Configure Avatar"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_scene_setup_animation_rigging(
    name: str,
    constraints: list[dict] | None,
) -> str:
    """Setup Animation Rigging constraints (SCENE-07)."""
    if not constraints:
        return json.dumps({
            "status": "error",
            "action": "setup_animation_rigging",
            "message": "constraints is required for setup_animation_rigging action",
        })

    script = generate_animation_rigging_script(
        rig_name=name,
        constraints=constraints,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Editor/Generated/Scene/VeilBreakers_Rigging_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_animation_rigging", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_animation_rigging",
            "name": name,
            "script_path": abs_path,
            "constraint_count": len(constraints),
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                f'Call mcp-unity execute_menu_item with path "VeilBreakers/Scene/Setup Animation Rigging/{name}"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


def main():
    """Entry point for the vb-unity-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
