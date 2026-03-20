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
    generate_test_runner_script,
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
    generate_arbitrary_shader,
    generate_renderer_feature,
)
from veilbreakers_mcp.shared.unity_templates.code_templates import (
    generate_class,
    modify_script,
    generate_editor_window,
    generate_property_drawer,
    generate_inspector_drawer,
    generate_scene_overlay,
    generate_test_class,
    generate_service_locator,
    generate_object_pool,
    generate_singleton,
    generate_state_machine,
    generate_so_event_channel,
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
from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_mob_controller_script,
    generate_aggro_system_script,
    generate_patrol_route_script,
    generate_spawn_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_projectile_script,
    _validate_mob_params,
    _validate_spawn_params,
    _validate_ability_params,
    _validate_projectile_params,
)
from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    generate_scene_profiler_script,
    generate_lod_setup_script,
    generate_lightmap_bake_script,
    generate_asset_audit_script,
    generate_build_automation_script,
    _validate_lod_screen_percentages,
)
from veilbreakers_mcp.shared.unity_templates.settings_templates import (
    generate_physics_settings_script,
    generate_physics_material_script,
    generate_player_settings_script,
    generate_build_settings_script,
    generate_quality_settings_script,
    generate_package_install_script,
    generate_package_remove_script,
    generate_tag_layer_script,
    generate_tag_layer_sync_script,
    generate_time_settings_script,
    generate_graphics_settings_script,
)
from veilbreakers_mcp.shared.unity_templates.prefab_templates import (
    generate_prefab_create_script,
    generate_prefab_variant_script,
    generate_prefab_modify_script,
    generate_prefab_delete_script,
    generate_scaffold_prefab_script,
    generate_add_component_script,
    generate_remove_component_script,
    generate_configure_component_script,
    generate_reflect_component_script,
    generate_hierarchy_script,
    generate_batch_configure_script,
    generate_variant_matrix_script,
    generate_joint_setup_script,
    generate_navmesh_setup_script,
    generate_bone_socket_script,
    generate_validate_project_script,
    generate_job_script,
)
from veilbreakers_mcp.shared.unity_templates.asset_templates import (
    generate_asset_move_script,
    generate_asset_rename_script,
    generate_asset_delete_script,
    generate_asset_duplicate_script,
    generate_create_folder_script,
    generate_fbx_import_script,
    generate_texture_import_script,
    generate_material_remap_script,
    generate_material_auto_generate_script,
    generate_asmdef_script,
    generate_preset_create_script,
    generate_preset_apply_script,
    generate_reference_scan_script,
    generate_atomic_import_script,
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
    try:
        target.relative_to(project_root)
    except ValueError:
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
        "run_tests",
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
    - run_tests: Run Unity tests via TestRunnerApi (CODE-05)

    Args:
        action: The editor action to perform.
        screenshot_path: Path for screenshot capture (relative to Unity project).
        supersize: Screenshot resolution multiplier (1-4).
        log_filter: Console log filter -- "all", "error", "warning", "log".
        log_count: Maximum number of log entries to collect.
        gemini_prompt: Prompt for Gemini visual review.
        gemini_criteria: List of quality criteria for Gemini review.
        test_mode: Test mode for run_tests -- "EditMode" or "PlayMode".
        assembly_filter: Optional assembly name filter for run_tests.
        category_filter: Optional NUnit category filter for run_tests.
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
        "next_steps": [
            "Call unity_editor action='recompile' to compile the test runner script",
            "Execute menu item 'VeilBreakers/Code/Run Tests' via mcp-unity",
            "Call unity_editor action='console_logs' or read Temp/vb_result.json for test results",
        ],
    })


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


# ---------------------------------------------------------------------------
# Gameplay tool -- compound tool covering MOB-01 through MOB-07
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_gameplay(
    action: Literal[
        "create_mob_controller",     # MOB-01: FSM-based mob AI
        "create_aggro_system",       # MOB-02: detection + threat + leash
        "create_patrol_route",       # MOB-03: waypoints + dwell + deviation
        "create_spawn_system",       # MOB-04: spawn points + waves
        "create_behavior_tree",      # MOB-05: ScriptableObject BT scaffolding
        "create_combat_ability",     # MOB-06: ability prefab data + executor
        "create_projectile_system",  # MOB-07: trajectory + trail + impact
    ],
    name: str = "default",
    # Mob controller params (MOB-01, MOB-02)
    detection_range: float = 15.0,
    attack_range: float = 3.0,
    leash_distance: float = 30.0,
    patrol_speed: float = 2.0,
    chase_speed: float = 5.0,
    flee_health_pct: float = 0.2,
    # Aggro params (MOB-02)
    decay_rate: float = 1.0,
    max_threats: int = 5,
    # Patrol params (MOB-03)
    waypoint_count: int = 4,
    dwell_time: float = 2.0,
    random_deviation: float = 1.5,
    # Spawn params (MOB-04)
    max_count: int = 10,
    respawn_timer: float = 30.0,
    spawn_radius: float = 5.0,
    wave_cooldown: float = 10.0,
    wave_count: int = 3,
    # Behavior tree params (MOB-05)
    node_types: list[str] | None = None,
    # Combat ability params (MOB-06)
    damage: float = 25.0,
    cooldown: float = 2.0,
    ability_range: float = 3.0,
    vfx_prefab: str = "",
    sound_name: str = "",
    hitbox_size: float = 1.0,
    # Projectile params (MOB-07)
    velocity: float = 20.0,
    trajectory: str = "straight",
    trail_width: float = 0.3,
    impact_vfx: str = "",
    lifetime: float = 5.0,
) -> str:
    """Unity Gameplay AI -- mob controllers, aggro, patrol, spawning, behavior trees, combat abilities, projectiles.

    This compound tool generates C# runtime scripts for Unity gameplay AI
    systems: FSM mob controllers, aggro/threat detection, waypoint patrol,
    wave-based spawning, behavior trees, combat abilities, and projectiles.

    Actions:
    - create_mob_controller: FSM state machine with Patrol/Chase/Attack/Flee states (MOB-01)
    - create_aggro_system: OverlapSphereNonAlloc threat detection with decay (MOB-02)
    - create_patrol_route: NavMeshAgent waypoint patrol with dwell times (MOB-03)
    - create_spawn_system: Wave-based spawning with max alive tracking (MOB-04)
    - create_behavior_tree: ScriptableObject BT with Sequence/Selector/Leaf nodes (MOB-05)
    - create_combat_ability: Ability ScriptableObject + executor with cooldown queue (MOB-06)
    - create_projectile_system: Straight/arc/homing projectile with trail + impact VFX (MOB-07)

    Args:
        action: The gameplay action to perform.
        name: Name for the generated script/system.
        detection_range: Detection sphere radius (MOB-01, MOB-02).
        attack_range: Attack engagement range (MOB-01).
        leash_distance: Max distance from spawn before returning (MOB-01, MOB-02).
        patrol_speed: NavMeshAgent patrol speed (MOB-01).
        chase_speed: NavMeshAgent chase speed (MOB-01).
        flee_health_pct: Health % threshold to trigger flee (MOB-01).
        decay_rate: Threat decay per tick (MOB-02).
        max_threats: Pre-allocated collider buffer size (MOB-02).
        waypoint_count: Default waypoint slot count (MOB-03).
        dwell_time: Dwell time at each waypoint in seconds (MOB-03).
        random_deviation: Random offset radius per waypoint (MOB-03).
        max_count: Maximum alive spawned instances (MOB-04).
        respawn_timer: Delay before respawn after death (MOB-04).
        spawn_radius: Random spawn position radius (MOB-04).
        wave_cooldown: Delay between spawn waves (MOB-04).
        wave_count: Number of wave slots (MOB-04).
        node_types: Custom leaf node class names to scaffold (MOB-05).
        damage: Base damage value (MOB-06).
        cooldown: Cooldown duration in seconds (MOB-06).
        ability_range: Ability effective range (MOB-06).
        vfx_prefab: VFX prefab name/path (MOB-06).
        sound_name: Audio clip name (MOB-06).
        hitbox_size: Hitbox collider size (MOB-06).
        velocity: Projectile speed (MOB-07).
        trajectory: Trajectory type: straight/arc/homing (MOB-07).
        trail_width: Trail renderer width (MOB-07).
        impact_vfx: Impact VFX prefab name/path (MOB-07).
        lifetime: Projectile auto-destroy time in seconds (MOB-07).
    """
    try:
        if action == "create_mob_controller":
            return await _handle_gameplay_mob_controller(
                name, detection_range, attack_range, leash_distance,
                patrol_speed, chase_speed, flee_health_pct,
            )
        elif action == "create_aggro_system":
            return await _handle_gameplay_aggro_system(
                name, detection_range, decay_rate, leash_distance, max_threats,
            )
        elif action == "create_patrol_route":
            return await _handle_gameplay_patrol_route(
                name, waypoint_count, dwell_time, random_deviation,
            )
        elif action == "create_spawn_system":
            return await _handle_gameplay_spawn_system(
                name, max_count, respawn_timer, spawn_radius, wave_cooldown, wave_count,
            )
        elif action == "create_behavior_tree":
            return await _handle_gameplay_behavior_tree(name, node_types)
        elif action == "create_combat_ability":
            return await _handle_gameplay_combat_ability(
                name, damage, cooldown, ability_range, vfx_prefab, sound_name, hitbox_size,
            )
        elif action == "create_projectile_system":
            return await _handle_gameplay_projectile_system(
                name, velocity, trajectory, trail_width, impact_vfx, lifetime,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_gameplay action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Gameplay action handlers
# ---------------------------------------------------------------------------


async def _handle_gameplay_mob_controller(
    name: str,
    detection_range: float,
    attack_range: float,
    leash_distance: float,
    patrol_speed: float,
    chase_speed: float,
    flee_health_pct: float,
) -> str:
    """Create FSM-based mob controller (MOB-01)."""
    error = _validate_mob_params(
        detection_range, attack_range, leash_distance,
        patrol_speed, chase_speed, flee_health_pct,
    )
    if error:
        return json.dumps({"status": "error", "action": "create_mob_controller", "message": error})

    script = generate_mob_controller_script(
        name=name,
        detection_range=detection_range,
        attack_range=attack_range,
        leash_distance=leash_distance,
        patrol_speed=patrol_speed,
        chase_speed=chase_speed,
        flee_health_pct=flee_health_pct,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_MobController_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_mob_controller", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_mob_controller",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_aggro_system(
    name: str,
    detection_range: float,
    decay_rate: float,
    leash_distance: float,
    max_threats: int,
) -> str:
    """Create aggro/threat detection system (MOB-02)."""
    script = generate_aggro_system_script(
        name=name,
        detection_range=detection_range,
        decay_rate=decay_rate,
        leash_distance=leash_distance,
        max_threats=max_threats,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_AggroSystem_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_aggro_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_aggro_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_patrol_route(
    name: str,
    waypoint_count: int,
    dwell_time: float,
    random_deviation: float,
) -> str:
    """Create waypoint patrol route (MOB-03)."""
    script = generate_patrol_route_script(
        name=name,
        waypoint_count=waypoint_count,
        dwell_time=dwell_time,
        random_deviation=random_deviation,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/AI/VeilBreakers_PatrolRoute_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_patrol_route", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_patrol_route",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_spawn_system(
    name: str,
    max_count: int,
    respawn_timer: float,
    spawn_radius: float,
    wave_cooldown: float,
    wave_count: int,
) -> str:
    """Create wave-based spawn system (MOB-04)."""
    error = _validate_spawn_params(max_count, respawn_timer, spawn_radius)
    if error:
        return json.dumps({"status": "error", "action": "create_spawn_system", "message": error})

    script = generate_spawn_system_script(
        name=name,
        max_count=max_count,
        respawn_timer=respawn_timer,
        spawn_radius=spawn_radius,
        wave_cooldown=wave_cooldown,
        wave_count=wave_count,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Spawning/VeilBreakers_SpawnManager_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_spawn_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_spawn_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_behavior_tree(
    name: str,
    node_types: list[str] | None,
) -> str:
    """Create behavior tree scaffolding (MOB-05)."""
    script = generate_behavior_tree_script(
        name=name,
        node_types=node_types,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/BehaviorTree/VeilBreakers_BehaviorTree_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_behavior_tree", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_behavior_tree",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated BehaviorTreeRunner MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_combat_ability(
    name: str,
    damage: float,
    cooldown: float,
    ability_range: float,
    vfx_prefab: str,
    sound_name: str,
    hitbox_size: float,
) -> str:
    """Create combat ability data + executor (MOB-06)."""
    error = _validate_ability_params(cooldown, damage)
    if error:
        return json.dumps({"status": "error", "action": "create_combat_ability", "message": error})

    script = generate_combat_ability_script(
        name=name,
        damage=damage,
        cooldown=cooldown,
        ability_range=ability_range,
        vfx_prefab=vfx_prefab,
        sound_name=sound_name,
        hitbox_size=hitbox_size,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Combat/VeilBreakers_CombatAbility_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_combat_ability", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_combat_ability",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated AbilityExecutor MonoBehaviour to a GameObject in the scene",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_gameplay_projectile_system(
    name: str,
    velocity: float,
    trajectory: str,
    trail_width: float,
    impact_vfx: str,
    lifetime: float,
) -> str:
    """Create projectile system (MOB-07)."""
    error = _validate_projectile_params(velocity, trajectory)
    if error:
        return json.dumps({"status": "error", "action": "create_projectile_system", "message": error})

    script = generate_projectile_script(
        name=name,
        velocity=velocity,
        trajectory=trajectory,
        trail_width=trail_width,
        impact_vfx=impact_vfx,
        lifetime=lifetime,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    script_path = f"Assets/Scripts/Runtime/Combat/VeilBreakers_Projectile_{safe_name}.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "create_projectile_system", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "create_projectile_system",
            "name": name,
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                "Attach the generated Projectile MonoBehaviour to a prefab",
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Performance tool -- compound tool covering PERF-01 through PERF-05
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_performance(
    action: Literal[
        "profile_scene",        # PERF-01: frame time, draw calls, memory
        "setup_lod_groups",     # PERF-02: auto-generate LODGroups
        "bake_lightmaps",      # PERF-03: async lightmap baking
        "audit_assets",        # PERF-04: find oversized/unused/uncompressed
        "automate_build",      # PERF-05: build + size report
    ],
    # Profiler budgets (PERF-01)
    target_frame_time_ms: float = 16.67,
    max_draw_calls: int = 2000,
    max_batches: int = 1000,
    max_triangles: int = 2000000,
    max_memory_mb: float = 2048.0,
    # LOD params (PERF-02)
    lod_count: int = 3,
    screen_percentages: list[float] | None = None,
    # Lightmap params (PERF-03)
    lightmap_quality: str = "medium",
    bounces: int = 2,
    lightmap_resolution: int = 32,
    # Asset audit params (PERF-04)
    max_texture_size: int = 2048,
    allowed_audio_formats: list[str] | None = None,
    # Build params (PERF-05)
    build_target: str = "StandaloneWindows64",
    scenes: list[str] | None = None,
    build_options: str = "None",
) -> str:
    """Unity Performance -- scene profiling, LOD setup, lightmap baking, asset audit, build automation.

    This compound tool generates C# editor scripts for Unity performance
    optimization: scene profiling with budget thresholds, automatic LODGroup
    setup, async lightmap baking, asset auditing for oversized/unused/uncompressed
    assets, and build pipeline automation with size reports.

    Actions:
    - profile_scene: Collect frame time/draw calls/memory and compare against budgets (PERF-01)
    - setup_lod_groups: Auto-generate LODGroups for scene MeshRenderers (PERF-02)
    - bake_lightmaps: Async lightmap baking with quality/bounces/resolution (PERF-03)
    - audit_assets: Find oversized textures, uncompressed audio, unused assets (PERF-04)
    - automate_build: Build pipeline with packed asset size report (PERF-05)

    Args:
        action: The performance action to perform.
        target_frame_time_ms: Frame time budget in milliseconds (PERF-01).
        max_draw_calls: Draw call budget (PERF-01).
        max_batches: Batch count budget (PERF-01).
        max_triangles: Triangle count budget (PERF-01).
        max_memory_mb: Memory budget in MB (PERF-01).
        lod_count: Number of LOD levels (PERF-02).
        screen_percentages: Screen percentage thresholds per LOD level, must be strictly descending (PERF-02).
        lightmap_quality: Quality preset name (PERF-03).
        bounces: Number of light bounces (PERF-03).
        lightmap_resolution: Lightmap texels per unit (PERF-03).
        max_texture_size: Max texture dimension before flagging as oversized (PERF-04).
        allowed_audio_formats: Allowed audio compression formats (PERF-04).
        build_target: BuildTarget enum name e.g. StandaloneWindows64 (PERF-05).
        scenes: Scene paths to include in build, defaults to build settings (PERF-05).
        build_options: BuildOptions flags e.g. Development, None (PERF-05).
    """
    try:
        if action == "profile_scene":
            return await _handle_performance_profile_scene(
                target_frame_time_ms, max_draw_calls, max_batches, max_triangles, max_memory_mb,
            )
        elif action == "setup_lod_groups":
            return await _handle_performance_setup_lod_groups(
                lod_count, screen_percentages,
            )
        elif action == "bake_lightmaps":
            return await _handle_performance_bake_lightmaps(
                lightmap_quality, bounces, lightmap_resolution,
            )
        elif action == "audit_assets":
            return await _handle_performance_audit_assets(
                max_texture_size, allowed_audio_formats,
            )
        elif action == "automate_build":
            return await _handle_performance_automate_build(
                build_target, scenes, build_options,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_performance action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Performance action handlers
# ---------------------------------------------------------------------------


async def _handle_performance_profile_scene(
    target_frame_time_ms: float,
    max_draw_calls: int,
    max_batches: int,
    max_triangles: int,
    max_memory_mb: float,
) -> str:
    """Generate scene profiler editor script (PERF-01)."""
    budgets = {
        "frame_time": target_frame_time_ms,
        "draw_calls": max_draw_calls,
        "batches": max_batches,
        "triangles": max_triangles,
        "memory_mb": max_memory_mb,
    }
    script = generate_scene_profiler_script(budgets=budgets)
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_SceneProfiler.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "profile_scene", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "profile_scene",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Performance/Profile Scene"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_setup_lod_groups(
    lod_count: int,
    screen_percentages: list[float] | None,
) -> str:
    """Generate LODGroup setup editor script (PERF-02)."""
    pcts = screen_percentages or [0.6, 0.3, 0.15][:lod_count]

    if not _validate_lod_screen_percentages(pcts):
        return json.dumps({
            "status": "error",
            "action": "setup_lod_groups",
            "message": f"screen_percentages must be strictly descending and all > 0, got: {pcts}",
        })

    script = generate_lod_setup_script(lod_count=lod_count, screen_percentages=pcts)
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_LODSetup.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "setup_lod_groups", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "setup_lod_groups",
            "script_path": abs_path,
            "lod_count": len(pcts),
            "screen_percentages": pcts,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Performance/Setup LODGroups"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_bake_lightmaps(
    lightmap_quality: str,
    bounces: int,
    lightmap_resolution: int,
) -> str:
    """Generate lightmap bake editor script (PERF-03)."""
    script = generate_lightmap_bake_script(
        quality=lightmap_quality,
        bounces=bounces,
        resolution=lightmap_resolution,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_LightmapBaker.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "bake_lightmaps", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "bake_lightmaps",
            "script_path": abs_path,
            "quality": lightmap_quality,
            "bounces": bounces,
            "resolution": lightmap_resolution,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Performance/Bake Lightmaps"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_audit_assets(
    max_texture_size: int,
    allowed_audio_formats: list[str] | None,
) -> str:
    """Generate asset audit editor script (PERF-04)."""
    formats = allowed_audio_formats or ["Vorbis", "AAC"]
    script = generate_asset_audit_script(
        max_texture_size=max_texture_size,
        allowed_audio_formats=formats,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_AssetAudit.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "audit_assets", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "audit_assets",
            "script_path": abs_path,
            "max_texture_size": max_texture_size,
            "allowed_audio_formats": formats,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Performance/Audit Assets"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_performance_automate_build(
    build_target: str,
    scenes: list[str] | None,
    build_options: str,
) -> str:
    """Generate build automation editor script (PERF-05)."""
    scene_list = scenes or []
    script = generate_build_automation_script(
        target=build_target,
        scenes=scene_list if scene_list else None,
        options=build_options,
    )
    script_path = "Assets/Editor/Generated/Performance/VeilBreakers_BuildAutomation.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "action": "automate_build", "message": str(exc)}
        )

    return json.dumps(
        {
            "status": "success",
            "action": "automate_build",
            "script_path": abs_path,
            "build_target": build_target,
            "build_options": build_options,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Performance/Build With Report"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# unity_settings compound tool -- EDIT-04/05/06/07/08/09/11
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_settings(
    action: Literal[
        "configure_physics",
        "create_physics_material",
        "configure_player",
        "configure_build",
        "configure_quality",
        "install_package",
        "remove_package",
        "manage_tags_layers",
        "sync_tags_layers",
        "configure_time",
        "configure_graphics",
    ],
    # Physics params
    collision_matrix: dict | None = None,
    gravity: list[float] | None = None,
    material_name: str = "",
    friction: float = 0.5,
    bounciness: float = 0.0,
    friction_combine: str = "Average",
    bounce_combine: str = "Average",
    # Player settings params
    company: str = "",
    product: str = "",
    color_space: str = "",
    scripting_backend: str = "",
    api_level: str = "",
    icon_path: str = "",
    splash_path: str = "",
    default_screen_width: int = 0,
    default_screen_height: int = 0,
    # Build settings params
    scenes: list[str] | None = None,
    platform: str = "",
    defines: list[str] | None = None,
    # Quality settings params
    quality_levels: list[dict] | None = None,
    # Package params
    package_id: str = "",
    version: str = "",
    source: str = "upm",
    registry_url: str = "",
    scopes: list[str] | None = None,
    # Tag/layer params
    tags: list[str] | None = None,
    layers: list[str] | None = None,
    sorting_layers: list[str] | None = None,
    constants_cs_path: str = "",
    # Time params
    fixed_timestep: float = 0.02,
    maximum_timestep: float = 0.1,
    time_scale: float = 1.0,
    # Graphics params
    render_pipeline_path: str = "",
    fog_mode: str = "",
    fog_color: list[float] | None = None,
    fog_density: float = 0.0,
) -> str:
    """Unity project settings automation -- configure Player, Build, Quality,
    Physics, Time, Graphics settings, manage packages, and tags/layers.

    This compound tool generates C# editor scripts for project-level settings,
    writes them to the Unity project, and returns instructions for executing
    them via mcp-unity.

    Actions:
    - configure_physics: Set collision matrix and gravity (EDIT-04)
    - create_physics_material: Create PhysicMaterial asset (EDIT-04)
    - configure_player: Configure Player Settings (EDIT-05)
    - configure_build: Configure Build Settings (EDIT-06)
    - configure_quality: Configure Quality Settings tiers (EDIT-07)
    - install_package: Install package from UPM/OpenUPM/git (EDIT-08)
    - remove_package: Remove a package (EDIT-08)
    - manage_tags_layers: Create tags, layers, sorting layers (EDIT-09)
    - sync_tags_layers: Sync tags/layers from Constants.cs (EDIT-09)
    - configure_time: Configure time settings (EDIT-11)
    - configure_graphics: Configure graphics/render pipeline (EDIT-11)
    """
    try:
        if action == "configure_physics":
            return await _handle_settings_physics(collision_matrix, gravity)
        elif action == "create_physics_material":
            if not material_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "material_name is required"}
                )
            return await _handle_settings_physics_material(
                material_name, friction, bounciness, friction_combine, bounce_combine
            )
        elif action == "configure_player":
            return await _handle_settings_player(
                company, product, color_space, scripting_backend, api_level,
                icon_path, splash_path, default_screen_width, default_screen_height,
            )
        elif action == "configure_build":
            return await _handle_settings_build(scenes, platform, defines)
        elif action == "configure_quality":
            if not quality_levels:
                return json.dumps(
                    {"status": "error", "action": action, "message": "quality_levels must be a non-empty list"}
                )
            return await _handle_settings_quality(quality_levels)
        elif action == "install_package":
            if not package_id:
                return json.dumps(
                    {"status": "error", "action": action, "message": "package_id is required"}
                )
            return await _handle_settings_install_package(
                package_id, version, source, registry_url, scopes
            )
        elif action == "remove_package":
            if not package_id:
                return json.dumps(
                    {"status": "error", "action": action, "message": "package_id is required"}
                )
            return await _handle_settings_remove_package(package_id)
        elif action == "manage_tags_layers":
            return await _handle_settings_tags_layers(tags, layers, sorting_layers)
        elif action == "sync_tags_layers":
            if not constants_cs_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "constants_cs_path is required"}
                )
            return await _handle_settings_sync_tags_layers(constants_cs_path)
        elif action == "configure_time":
            return await _handle_settings_time(fixed_timestep, maximum_timestep, time_scale)
        elif action == "configure_graphics":
            return await _handle_settings_graphics(
                render_pipeline_path, fog_mode, fog_color, fog_density
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_settings action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


async def _handle_settings_physics(
    collision_matrix: dict | None, gravity: list[float] | None
) -> str:
    """Generate and write the physics settings script."""
    script = generate_physics_settings_script(
        collision_matrix=collision_matrix, gravity=gravity
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_ConfigurePhysics.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_physics", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_physics",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Physics"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_physics_material(
    material_name: str,
    friction: float,
    bounciness: float,
    friction_combine: str,
    bounce_combine: str,
) -> str:
    """Generate and write the physics material creation script."""
    script = generate_physics_material_script(
        name=material_name,
        friction=friction,
        bounciness=bounciness,
        friction_combine=friction_combine,
        bounce_combine=bounce_combine,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_CreatePhysicsMaterial.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_physics_material", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "create_physics_material",
            "script_path": abs_path,
            "material_name": material_name,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Create Physics Material"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_player(
    company: str,
    product: str,
    color_space: str,
    scripting_backend: str,
    api_level: str,
    icon_path: str,
    splash_path: str,
    default_screen_width: int,
    default_screen_height: int,
) -> str:
    """Generate and write the player settings script."""
    script = generate_player_settings_script(
        company=company,
        product=product,
        color_space=color_space,
        scripting_backend=scripting_backend,
        api_level=api_level,
        icon_path=icon_path,
        splash_path=splash_path,
        default_screen_width=default_screen_width,
        default_screen_height=default_screen_height,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_PlayerSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_player", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_player",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Player Settings"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_build(
    scenes: list[str] | None, platform: str, defines: list[str] | None
) -> str:
    """Generate and write the build settings script."""
    try:
        script = generate_build_settings_script(
            scenes=scenes, platform=platform, defines=defines
        )
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_build", "message": str(exc)})

    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_BuildSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_build", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_build",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Build Settings"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_quality(quality_levels: list[dict]) -> str:
    """Generate and write the quality settings script."""
    script = generate_quality_settings_script(levels=quality_levels)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_QualitySettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_quality", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_quality",
            "script_path": abs_path,
            "levels_count": len(quality_levels),
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Quality Settings"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_install_package(
    package_id: str,
    version: str,
    source: str,
    registry_url: str,
    scopes: list[str] | None,
) -> str:
    """Generate and write the package install script."""
    script = generate_package_install_script(
        package_id=package_id,
        version=version,
        source=source,
        registry_url=registry_url,
        scopes=scopes,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_InstallPackage.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "install_package", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "install_package",
            "script_path": abs_path,
            "package_id": package_id,
            "source": source,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Install Package"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_remove_package(package_id: str) -> str:
    """Generate and write the package remove script."""
    script = generate_package_remove_script(package_id=package_id)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_RemovePackage.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remove_package", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "remove_package",
            "script_path": abs_path,
            "package_id": package_id,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Remove Package"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_tags_layers(
    tags: list[str] | None,
    layers: list[str] | None,
    sorting_layers: list[str] | None,
) -> str:
    """Generate and write the tag/layer management script."""
    script = generate_tag_layer_script(
        tags=tags, layers=layers, sorting_layers=sorting_layers
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_TagsLayers.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "manage_tags_layers", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "manage_tags_layers",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Manage Tags & Layers"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_sync_tags_layers(constants_cs_path: str) -> str:
    """Generate and write the tag/layer sync script."""
    script = generate_tag_layer_sync_script(constants_cs_path=constants_cs_path)
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_SyncTagsLayers.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "sync_tags_layers", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "sync_tags_layers",
            "script_path": abs_path,
            "constants_path": constants_cs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Sync Tags & Layers from Code"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_time(
    fixed_timestep: float, maximum_timestep: float, time_scale: float
) -> str:
    """Generate and write the time settings script."""
    script = generate_time_settings_script(
        fixed_timestep=fixed_timestep,
        maximum_timestep=maximum_timestep,
        time_scale=time_scale,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_TimeSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_time", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_time",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Time Settings"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


async def _handle_settings_graphics(
    render_pipeline_path: str,
    fog_mode: str,
    fog_color: list[float] | None,
    fog_density: float,
) -> str:
    """Generate and write the graphics settings script."""
    script = generate_graphics_settings_script(
        render_pipeline_path=render_pipeline_path,
        fog_mode=fog_mode,
        fog_color=fog_color,
        fog_density=fog_density,
    )
    script_path = "Assets/Editor/Generated/Settings/VeilBreakers_GraphicsSettings.cs"

    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_graphics", "message": str(exc)})

    return json.dumps(
        {
            "status": "success",
            "action": "configure_graphics",
            "script_path": abs_path,
            "next_steps": [
                "Call mcp-unity recompile_scripts to compile the new script",
                'Call mcp-unity execute_menu_item with path "VeilBreakers/Settings/Configure Graphics Settings"',
            ],
            "result_file": "Temp/vb_result.json",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# unity_prefab compound tool -- Prefab, Component, Hierarchy, Physics, NavMesh
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_prefab(
    action: Literal[
        "create",
        "create_variant",
        "modify",
        "delete",
        "create_scaffold",
        "add_component",
        "remove_component",
        "configure",
        "reflect_component",
        "hierarchy",
        "batch_configure",
        "batch_job",
        "generate_variants",
        "setup_joints",
        "setup_navmesh",
        "setup_bone_sockets",
        "validate_project",
    ],
    # Params for create/scaffold
    name: str = "",
    prefab_type: str = "prop",
    save_dir: str = "Assets/Prefabs",
    # Params for variant
    base_prefab_path: str = "",
    overrides: dict | None = None,
    # Params for modify
    prefab_path: str = "",
    modifications: list[dict] | None = None,
    # Params for component/hierarchy/joint/navmesh -- SELECTOR-BASED
    selector: dict | str | None = None,
    # Legacy backward-compat
    object_name: str = "",
    component_type: str = "",
    properties: list[dict] | None = None,
    # Params for hierarchy
    operation: str = "",
    parent_name: str = "",
    new_name: str = "",
    layer: str = "",
    tag: str = "",
    enabled: bool = True,
    # Params for batch_configure
    batch_selector: dict | None = None,
    # Params for batch_job
    operations: list[dict] | None = None,
    # Params for variant matrix
    corruption_tiers: list[int] | None = None,
    brands: list[str] | None = None,
    output_dir: str = "Assets/Prefabs/Variants",
    # Params for joints
    joint_type: str = "HingeJoint",
    joint_config: dict | None = None,
    # Params for navmesh
    navmesh_operation: str = "add_obstacle",
    # Params for bone sockets
    sockets: list[str] | None = None,
    # Params for components list (auto-wire override)
    components: list[dict] | None = None,
) -> str:
    """Unity Prefab, Component, and Hierarchy automation.

    This compound tool generates C# editor scripts for prefab creation,
    component configuration, hierarchy manipulation, physics joints,
    NavMesh setup, bone sockets, and batch operations.

    Actions:
    - create: Create prefab from auto-wire profile (EDIT-01)
    - create_variant: Create prefab variant from base (EDIT-01)
    - modify: Modify existing prefab properties (EDIT-01)
    - delete: Delete prefab asset (EDIT-01)
    - create_scaffold: Create ghost scaffold placeholder
    - add_component: Add component to GameObject (EDIT-02)
    - remove_component: Remove component from GameObject (EDIT-02)
    - configure: Configure component properties via SerializedObject (EDIT-02)
    - reflect_component: Introspect component fields (EDIT-02)
    - hierarchy: Hierarchy operations (create_empty/rename/reparent/etc.) (EDIT-03)
    - batch_configure: Configure same component on multiple objects
    - batch_job: Multiple different operations in one compile cycle
    - generate_variants: Generate corruption x brand variant matrix
    - setup_joints: Configure physics joints (PHYS-01)
    - setup_navmesh: NavMesh configuration (PHYS-02)
    - setup_bone_sockets: Bone socket attachment points (EQUIP-02)
    - validate_project: Check project integrity
    """
    # Resolve selector: prefer explicit selector dict/str, fall back to object_name
    resolved_selector = selector if selector is not None else (object_name if object_name else None)

    try:
        if action == "create":
            return await _handle_prefab_create(name, prefab_type, save_dir, components)
        elif action == "create_variant":
            return await _handle_prefab_create_variant(name, base_prefab_path, overrides)
        elif action == "modify":
            return await _handle_prefab_modify(prefab_path, modifications)
        elif action == "delete":
            return await _handle_prefab_delete(prefab_path)
        elif action == "create_scaffold":
            return await _handle_prefab_scaffold(name, prefab_type)
        elif action == "add_component":
            return await _handle_prefab_add_component(resolved_selector, component_type, properties)
        elif action == "remove_component":
            return await _handle_prefab_remove_component(resolved_selector, component_type)
        elif action == "configure":
            return await _handle_prefab_configure(resolved_selector, component_type, properties)
        elif action == "reflect_component":
            return await _handle_prefab_reflect(resolved_selector, component_type)
        elif action == "hierarchy":
            return await _handle_prefab_hierarchy(
                operation, resolved_selector, parent_name, new_name, layer, tag, enabled, name
            )
        elif action == "batch_configure":
            return await _handle_prefab_batch_configure(batch_selector, component_type, properties)
        elif action == "batch_job":
            return await _handle_prefab_batch_job(operations)
        elif action == "generate_variants":
            return await _handle_prefab_generate_variants(
                name, base_prefab_path, corruption_tiers, brands, output_dir
            )
        elif action == "setup_joints":
            return await _handle_prefab_setup_joints(resolved_selector, joint_type, joint_config)
        elif action == "setup_navmesh":
            return await _handle_prefab_setup_navmesh(navmesh_operation, resolved_selector, joint_config)
        elif action == "setup_bone_sockets":
            return await _handle_prefab_setup_bone_sockets(prefab_path, sockets)
        elif action == "validate_project":
            return await _handle_prefab_validate_project()
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_prefab action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Prefab handler functions
# ---------------------------------------------------------------------------


async def _handle_prefab_create(
    name: str, prefab_type: str, save_dir: str, components: list[dict] | None
) -> str:
    if not name:
        return json.dumps({"status": "error", "action": "create", "message": "name is required"})
    script = generate_prefab_create_script(name, prefab_type, save_dir, components)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreatePrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Create Prefab"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_create_variant(
    name: str, base_prefab_path: str, overrides: dict | None
) -> str:
    if not base_prefab_path:
        return json.dumps({"status": "error", "action": "create_variant", "message": "base_prefab_path is required"})
    script = generate_prefab_variant_script(name, base_prefab_path, overrides)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreateVariant.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_variant", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_variant", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Create Variant"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_modify(
    prefab_path: str, modifications: list[dict] | None
) -> str:
    if not prefab_path or not modifications:
        return json.dumps({"status": "error", "action": "modify", "message": "prefab_path and modifications are required"})
    script = generate_prefab_modify_script(prefab_path, modifications)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ModifyPrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "modify", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "modify", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Modify Prefab"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_delete(prefab_path: str) -> str:
    if not prefab_path:
        return json.dumps({"status": "error", "action": "delete", "message": "prefab_path is required"})
    script = generate_prefab_delete_script(prefab_path)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_DeletePrefab.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "delete", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "delete", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Delete Prefab"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_scaffold(name: str, prefab_type: str) -> str:
    if not name:
        return json.dumps({"status": "error", "action": "create_scaffold", "message": "name is required"})
    script = generate_scaffold_prefab_script(name, prefab_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_CreateScaffold.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_scaffold", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_scaffold", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Create Scaffold"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_add_component(
    resolved_selector: dict | str | None, component_type: str, properties: list[dict] | None
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "add_component", "message": "selector and component_type are required"})
    script = generate_add_component_script(resolved_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_AddComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "add_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "add_component", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Add Component"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_remove_component(
    resolved_selector: dict | str | None, component_type: str
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "remove_component", "message": "selector and component_type are required"})
    script = generate_remove_component_script(resolved_selector, component_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_RemoveComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remove_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "remove_component", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Remove Component"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_configure(
    resolved_selector: dict | str | None, component_type: str, properties: list[dict] | None
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "configure", "message": "selector and component_type are required"})
    if not properties:
        return json.dumps({"status": "error", "action": "configure", "message": "properties list is required"})
    script = generate_configure_component_script(resolved_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ConfigureComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Configure Component"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_reflect(
    resolved_selector: dict | str | None, component_type: str
) -> str:
    if not resolved_selector or not component_type:
        return json.dumps({"status": "error", "action": "reflect_component", "message": "selector and component_type are required"})
    script = generate_reflect_component_script(resolved_selector, component_type)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ReflectComponent.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "reflect_component", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "reflect_component", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Reflect Component"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_hierarchy(
    operation: str,
    resolved_selector: dict | str | None,
    parent_name: str,
    new_name: str,
    layer: str,
    tag: str,
    enabled: bool,
    name: str,
) -> str:
    if not operation:
        return json.dumps({"status": "error", "action": "hierarchy", "message": "operation is required"})
    kwargs = {}
    if resolved_selector:
        kwargs["selector"] = resolved_selector
    if parent_name:
        kwargs["parent_name"] = parent_name
    if new_name:
        kwargs["new_name"] = new_name
    if layer:
        kwargs["layer"] = layer
    if tag:
        kwargs["tag"] = tag
    if name:
        kwargs["name"] = name
    kwargs["enabled"] = enabled
    script = generate_hierarchy_script(operation, **kwargs)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_Hierarchy.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "hierarchy", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "hierarchy", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Hierarchy"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_batch_configure(
    batch_selector: dict | None, component_type: str, properties: list[dict] | None
) -> str:
    if not batch_selector or not component_type:
        return json.dumps({"status": "error", "action": "batch_configure", "message": "batch_selector and component_type are required"})
    if not properties:
        return json.dumps({"status": "error", "action": "batch_configure", "message": "properties list is required"})
    script = generate_batch_configure_script(batch_selector, component_type, properties)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_BatchConfigure.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "batch_configure", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "batch_configure", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Batch Configure"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_batch_job(operations: list[dict] | None) -> str:
    if not operations:
        return json.dumps({"status": "error", "action": "batch_job", "message": "operations list is required"})
    script = generate_job_script(operations)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_JobScript.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "batch_job", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "batch_job", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Execute Job Script"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_generate_variants(
    name: str,
    base_prefab_path: str,
    corruption_tiers: list[int] | None,
    brands: list[str] | None,
    output_dir: str,
) -> str:
    if not name or not base_prefab_path:
        return json.dumps({"status": "error", "action": "generate_variants", "message": "name and base_prefab_path are required"})
    if not corruption_tiers or not brands:
        return json.dumps({"status": "error", "action": "generate_variants", "message": "corruption_tiers and brands must have items"})
    script = generate_variant_matrix_script(name, base_prefab_path, corruption_tiers, brands, output_dir)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_VariantMatrix.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "generate_variants", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "generate_variants", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Generate Variant Matrix"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_joints(
    resolved_selector: dict | str | None, joint_type: str, joint_config: dict | None
) -> str:
    if not resolved_selector or not joint_type:
        return json.dumps({"status": "error", "action": "setup_joints", "message": "selector and joint_type are required"})
    script = generate_joint_setup_script(resolved_selector, joint_type, joint_config or {})
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_SetupJoint.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_joints", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_joints", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Setup Joint"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_navmesh(
    navmesh_operation: str, resolved_selector: dict | str | None, config: dict | None
) -> str:
    if not resolved_selector:
        return json.dumps({"status": "error", "action": "setup_navmesh", "message": "selector is required"})
    script = generate_navmesh_setup_script(navmesh_operation, resolved_selector, **(config or {}))
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_NavMeshSetup.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_navmesh", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_navmesh", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/NavMesh Setup"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_setup_bone_sockets(
    prefab_path: str, sockets: list[str] | None
) -> str:
    if not prefab_path:
        return json.dumps({"status": "error", "action": "setup_bone_sockets", "message": "prefab_path is required"})
    script = generate_bone_socket_script(prefab_path, sockets)
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_BoneSockets.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "setup_bone_sockets", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "setup_bone_sockets", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Setup Bone Sockets"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_prefab_validate_project() -> str:
    script = generate_validate_project_script()
    script_path = "Assets/Editor/Generated/Prefab/VeilBreakers_ValidateProject.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "validate_project", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "validate_project", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Prefab/Validate Project Integrity"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


# ---------------------------------------------------------------------------
# unity_assets compound tool -- asset pipeline operations
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_assets(
    action: Literal[
        "move",              # EDIT-10 + IMP-01: Move asset (GUID-safe)
        "rename",            # EDIT-10 + IMP-01: Rename asset (GUID-safe)
        "delete",            # EDIT-10: Delete asset (with optional reference scan)
        "duplicate",         # EDIT-10: Duplicate asset
        "create_folder",     # EDIT-10: Create folder
        "configure_fbx",     # EDIT-12: FBX ModelImporter settings
        "configure_texture", # EDIT-13: TextureImporter settings
        "remap_materials",   # EDIT-14 + IMP-02: Material remapping on FBX
        "auto_materials",    # EDIT-14 + IMP-02: Auto-generate materials from textures
        "create_asmdef",     # EDIT-15: Assembly Definition creation
        "create_preset",     # PIPE-09: Create Unity Preset
        "apply_preset",      # PIPE-09: Apply Unity Preset
        "scan_references",   # IMP-01: Scan asset references
        "atomic_import",     # Combined import sequence
    ],
    # Asset operation params
    asset_path: str = "",
    new_path: str = "",
    new_name: str = "",
    safe_delete: bool = True,
    source_path: str = "",
    dest_path: str = "",
    folder_path: str = "",
    # FBX import params
    scale: float = 1.0,
    mesh_compression: str = "Off",
    animation_type: str = "None",
    import_animation: bool = False,
    normals_mode: str = "Import",
    import_blend_shapes: bool = True,
    optimize: bool = True,
    is_readable: bool = False,
    preset_type: str = "",
    # Texture import params
    max_size: int = 2048,
    srgb: bool = True,
    mipmap: bool = True,
    filter_mode: str = "Bilinear",
    wrap_mode: str = "Repeat",
    sprite_mode: str = "",
    platform_overrides: dict | None = None,
    auto_detect_srgb: bool = False,
    # Material remap params
    fbx_path: str = "",
    remappings: dict | None = None,
    texture_dir: str = "",
    shader_name: str = "Universal Render Pipeline/Lit",
    material_name: str = "",
    # Asmdef params
    asmdef_name: str = "",
    root_dir: str = "",
    root_namespace: str = "",
    references: list[str] | None = None,
    platforms: list[str] | None = None,
    asmdef_defines: list[str] | None = None,
    allow_unsafe: bool = False,
    auto_referenced: bool = True,
    # Preset params
    preset_name: str = "",
    source_asset_path: str = "",
    save_dir: str = "Assets/Editor/Presets",
    preset_path: str = "",
    target_path: str = "",
    # Atomic import params
    texture_paths: list[str] | None = None,
) -> str:
    """Unity asset pipeline automation -- asset operations, import config,
    material management, Assembly Definitions, presets, and atomic imports.

    This compound tool generates C# editor scripts (or JSON for asmdef) for
    asset pipeline operations, writes them to the Unity project, and returns
    instructions for executing them via mcp-unity.

    Actions:
    - move: Move asset preserving GUID (EDIT-10 + IMP-01)
    - rename: Rename asset preserving GUID (EDIT-10 + IMP-01)
    - delete: Delete asset with optional reference scan (EDIT-10)
    - duplicate: Duplicate asset (EDIT-10)
    - create_folder: Create folder structure (EDIT-10)
    - configure_fbx: Configure FBX ModelImporter settings (EDIT-12)
    - configure_texture: Configure TextureImporter settings (EDIT-13)
    - remap_materials: Remap materials on FBX import (EDIT-14 + IMP-02)
    - auto_materials: Auto-generate PBR materials from textures (EDIT-14 + IMP-02)
    - create_asmdef: Create Assembly Definition file (EDIT-15)
    - create_preset: Create Unity Preset from asset (PIPE-09)
    - apply_preset: Apply Unity Preset to asset (PIPE-09)
    - scan_references: Scan for assets referencing target (IMP-01)
    - atomic_import: Combined atomic import sequence
    """
    try:
        if action == "move":
            if not asset_path or not new_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path and new_path are required"}
                )
            return await _handle_assets_move(asset_path, new_path)
        elif action == "rename":
            if not asset_path or not new_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path and new_name are required"}
                )
            return await _handle_assets_rename(asset_path, new_name)
        elif action == "delete":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_delete(asset_path, safe_delete)
        elif action == "duplicate":
            if not source_path or not dest_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "source_path and dest_path are required"}
                )
            return await _handle_assets_duplicate(source_path, dest_path)
        elif action == "create_folder":
            if not folder_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "folder_path is required"}
                )
            return await _handle_assets_create_folder(folder_path)
        elif action == "configure_fbx":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_configure_fbx(
                asset_path, scale, mesh_compression, animation_type,
                import_animation, normals_mode, import_blend_shapes,
                optimize, is_readable, preset_type,
            )
        elif action == "configure_texture":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_configure_texture(
                asset_path, max_size, srgb, mipmap, filter_mode, wrap_mode,
                sprite_mode, platform_overrides, preset_type, auto_detect_srgb,
            )
        elif action == "remap_materials":
            if not fbx_path or not remappings:
                return json.dumps(
                    {"status": "error", "action": action, "message": "fbx_path and remappings are required"}
                )
            return await _handle_assets_remap_materials(fbx_path, remappings)
        elif action == "auto_materials":
            if not fbx_path or not texture_dir:
                return json.dumps(
                    {"status": "error", "action": action, "message": "fbx_path and texture_dir are required"}
                )
            return await _handle_assets_auto_materials(fbx_path, texture_dir, shader_name)
        elif action == "create_asmdef":
            if not asmdef_name or not root_dir:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asmdef_name and root_dir are required"}
                )
            return await _handle_assets_create_asmdef(
                asmdef_name, root_dir, root_namespace, references,
                platforms, asmdef_defines, allow_unsafe, auto_referenced,
            )
        elif action == "create_preset":
            if not preset_name or not source_asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "preset_name and source_asset_path are required"}
                )
            return await _handle_assets_create_preset(preset_name, source_asset_path, save_dir)
        elif action == "apply_preset":
            if not preset_path or not target_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "preset_path and target_path are required"}
                )
            return await _handle_assets_apply_preset(preset_path, target_path)
        elif action == "scan_references":
            if not asset_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "asset_path is required"}
                )
            return await _handle_assets_scan_references(asset_path)
        elif action == "atomic_import":
            if not texture_paths or not material_name or not fbx_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "texture_paths, material_name, and fbx_path are required"}
                )
            return await _handle_assets_atomic_import(
                texture_paths, material_name, fbx_path, shader_name, remappings,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})
    except Exception as exc:
        logger.exception("unity_assets action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# unity_assets handler functions
# ---------------------------------------------------------------------------


async def _handle_assets_move(asset_path: str, new_path: str) -> str:
    """Generate and write the asset move script."""
    script = generate_asset_move_script(asset_path, new_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_MoveAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "move", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "move", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Move Asset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_rename(asset_path: str, new_name: str) -> str:
    """Generate and write the asset rename script."""
    script = generate_asset_rename_script(asset_path, new_name)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_RenameAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "rename", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "rename", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Rename Asset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_delete(asset_path: str, safe_delete: bool) -> str:
    """Generate and write the asset delete script."""
    script = generate_asset_delete_script(asset_path, safe_delete=safe_delete)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_DeleteAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "delete", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "delete", "script_path": abs_path,
        "safe_delete": safe_delete,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Delete Asset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_duplicate(source_path: str, dest_path: str) -> str:
    """Generate and write the asset duplicate script."""
    script = generate_asset_duplicate_script(source_path, dest_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_DuplicateAsset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "duplicate", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "duplicate", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Duplicate Asset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_create_folder(folder_path: str) -> str:
    """Generate and write the create folder script."""
    script = generate_create_folder_script(folder_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_CreateFolder.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_folder", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_folder", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Create Folder"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_configure_fbx(
    asset_path: str, scale: float, mesh_compression: str,
    animation_type: str, import_animation: bool, normals_mode: str,
    import_blend_shapes: bool, optimize: bool, is_readable: bool,
    preset_type: str,
) -> str:
    """Generate and write the FBX import configuration script."""
    script = generate_fbx_import_script(
        asset_path, scale=scale, mesh_compression=mesh_compression,
        animation_type=animation_type, import_animation=import_animation,
        normals_mode=normals_mode, import_blend_shapes=import_blend_shapes,
        optimize=optimize, is_readable=is_readable, preset_type=preset_type,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ConfigureFBX.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_fbx", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure_fbx", "script_path": abs_path,
        "preset_type": preset_type if preset_type else "custom",
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Configure FBX Import"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_configure_texture(
    asset_path: str, max_size: int, srgb: bool, mipmap: bool,
    filter_mode: str, wrap_mode: str, sprite_mode: str,
    platform_overrides: dict | None, preset_type: str,
    auto_detect_srgb: bool,
) -> str:
    """Generate and write the texture import configuration script."""
    script = generate_texture_import_script(
        asset_path, max_size=max_size, srgb=srgb, mipmap=mipmap,
        filter_mode=filter_mode, wrap_mode=wrap_mode, sprite_mode=sprite_mode,
        platform_overrides=platform_overrides, preset_type=preset_type,
        auto_detect_srgb=auto_detect_srgb,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ConfigureTexture.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "configure_texture", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "configure_texture", "script_path": abs_path,
        "preset_type": preset_type if preset_type else "custom",
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Configure Texture Import"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_remap_materials(fbx_path: str, remappings: dict) -> str:
    """Generate and write the material remap script."""
    script = generate_material_remap_script(fbx_path, remappings)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_RemapMaterials.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "remap_materials", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "remap_materials", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Remap Materials"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_auto_materials(
    fbx_path: str, texture_dir: str, shader_name: str,
) -> str:
    """Generate and write the auto material generation script."""
    script = generate_material_auto_generate_script(
        fbx_path, texture_dir, shader_name=shader_name,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_AutoMaterials.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "auto_materials", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "auto_materials", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Auto Generate Materials"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_create_asmdef(
    asmdef_name: str, root_dir: str, root_namespace: str,
    references: list[str] | None, platforms: list[str] | None,
    asmdef_defines: list[str] | None, allow_unsafe: bool,
    auto_referenced: bool,
) -> str:
    """Generate and write the assembly definition JSON file directly."""
    content = generate_asmdef_script(
        asmdef_name, root_dir, root_namespace=root_namespace,
        references=references, platforms=platforms, defines=asmdef_defines,
        allow_unsafe=allow_unsafe, auto_referenced=auto_referenced,
    )
    # asmdef is JSON, not C# -- write directly as {name}.asmdef
    asmdef_path = f"{root_dir.rstrip('/')}/{asmdef_name}.asmdef"
    try:
        abs_path = _write_to_unity(content, asmdef_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_asmdef", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_asmdef",
        "asmdef_path": abs_path, "asmdef_name": asmdef_name,
        "next_steps": [
            "Call mcp-unity recompile_scripts to trigger Unity to recognize the new assembly definition",
        ],
        "result_file": None,
    }, indent=2)


async def _handle_assets_create_preset(
    preset_name: str, source_asset_path: str, save_dir: str,
) -> str:
    """Generate and write the preset creation script."""
    script = generate_preset_create_script(
        preset_name, source_asset_path, save_dir=save_dir,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_CreatePreset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "create_preset", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "create_preset", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Create Preset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_apply_preset(preset_path: str, target_path: str) -> str:
    """Generate and write the preset apply script."""
    script = generate_preset_apply_script(preset_path, target_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ApplyPreset.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "apply_preset", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "apply_preset", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Apply Preset"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_scan_references(asset_path: str) -> str:
    """Generate and write the reference scan script."""
    script = generate_reference_scan_script(asset_path)
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_ScanReferences.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "scan_references", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "scan_references", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Scan References"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


async def _handle_assets_atomic_import(
    texture_paths: list[str], material_name: str, fbx_path: str,
    shader_name: str, remappings: dict | None,
) -> str:
    """Generate and write the atomic import script."""
    script = generate_atomic_import_script(
        texture_paths, material_name, fbx_path,
        shader_name=shader_name, remappings=remappings,
    )
    script_path = "Assets/Editor/Generated/Assets/VeilBreakers_AtomicImport.cs"
    try:
        abs_path = _write_to_unity(script, script_path)
    except ValueError as exc:
        return json.dumps({"status": "error", "action": "atomic_import", "message": str(exc)})
    return json.dumps({
        "status": "success", "action": "atomic_import", "script_path": abs_path,
        "next_steps": [
            "Call mcp-unity recompile_scripts to compile the new script",
            'Call mcp-unity execute_menu_item with path "VeilBreakers/Assets/Atomic Import"',
        ],
        "result_file": "Temp/vb_result.json",
    }, indent=2)


# ---------------------------------------------------------------------------
# unity_code compound tool (CODE-01 through CODE-10)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_code(
    action: Literal[
        "generate_class",       # CODE-01: Generate any C# class type
        "modify_script",        # CODE-02: Modify existing C# script
        "editor_window",        # CODE-03: Generate EditorWindow
        "property_drawer",      # CODE-03: Generate PropertyDrawer
        "inspector_drawer",     # CODE-03: Generate custom Inspector
        "scene_overlay",        # CODE-03: Generate SceneView overlay
        "generate_test",        # CODE-04: Generate test class
        "service_locator",      # CODE-06: Scaffold service locator pattern
        "object_pool",          # CODE-07: Scaffold object pool pattern
        "singleton",            # CODE-08: Scaffold singleton pattern
        "state_machine",        # CODE-09: Scaffold state machine pattern
        "event_channel",        # CODE-10: Scaffold SO event channel
    ],
    # Class generation params (CODE-01)
    class_name: str = "",
    class_type: str = "MonoBehaviour",
    namespace: str = "",
    base_class: str = "",
    interfaces: list[str] | None = None,
    usings: list[str] | None = None,
    attributes: list[str] | None = None,
    fields: list[dict] | None = None,
    properties: list[dict] | None = None,
    methods: list[dict] | None = None,
    enum_values: list[str] | None = None,
    summary: str = "",
    output_dir: str = "Assets/Scripts/Generated",
    # Script modification params (CODE-02)
    script_path: str = "",
    add_usings: list[str] | None = None,
    add_fields: list[dict] | None = None,
    add_properties: list[dict] | None = None,
    add_methods: list[dict] | None = None,
    add_attributes: list[dict] | None = None,
    # Editor tool params (CODE-03)
    window_name: str = "",
    menu_path: str = "",
    target_type: str = "",
    overlay_name: str = "",
    display_name: str = "",
    drawer_body: str = "",
    panel_body: str = "",
    on_gui_body: str = "",
    fields_to_draw: list[str] | None = None,
    # Test params (CODE-04)
    test_mode: str = "EditMode",
    target_class: str = "",
    test_methods: list[dict] | None = None,
    setup_body: str = "",
    teardown_body: str = "",
    # Architecture pattern params (CODE-06-10)
    singleton_type: str = "MonoBehaviour",
    persistent: bool = True,
    include_scene_persistent: bool = True,
    include_gameobject_pool: bool = True,
    event_name: str = "",
    has_parameter: bool = False,
    parameter_type: str = "int",
) -> str:
    """C# code generation -- generate classes, modify scripts, create editor tools
    and architecture patterns.

    This compound tool generates C# source files covering arbitrary class types,
    script modification, editor windows/drawers/overlays, test classes, and
    common architecture patterns (service locator, object pool, singleton, state
    machine, event channels).

    Actions:
    - generate_class: Generate any C# class type (MonoBehaviour, SO, class, interface, enum, struct) (CODE-01)
    - modify_script: Modify existing C# script by adding usings, fields, properties, methods (CODE-02)
    - editor_window: Generate EditorWindow with MenuItem and OnGUI (CODE-03)
    - property_drawer: Generate CustomPropertyDrawer (CODE-03)
    - inspector_drawer: Generate CustomEditor (CODE-03)
    - scene_overlay: Generate SceneView Overlay (CODE-03)
    - generate_test: Generate NUnit test class for EditMode or PlayMode (CODE-04)
    - service_locator: Scaffold static service locator pattern (CODE-06)
    - object_pool: Scaffold generic ObjectPool<T> with optional GameObjectPool (CODE-07)
    - singleton: Scaffold MonoBehaviour or plain thread-safe singleton (CODE-08)
    - state_machine: Scaffold IState/StateMachine/BaseState framework (CODE-09)
    - event_channel: Scaffold ScriptableObject event channel system (CODE-10)

    Args:
        action: The code generation action to perform.
        class_name: Name of the class (required for generate_class, singleton, generate_test).
        class_type: Class type -- MonoBehaviour, ScriptableObject, class, static class, abstract class, interface, enum, struct.
        namespace: Optional C# namespace.
        base_class: Explicit base class override.
        interfaces: Interfaces to implement.
        usings: Additional using statements.
        attributes: Class-level attributes.
        fields: Field definitions (list of dicts).
        properties: Property definitions (list of dicts).
        methods: Method definitions (list of dicts).
        enum_values: Enum member names (only for enum class_type).
        summary: XML summary comment.
        output_dir: Output directory relative to Unity project (default Assets/Scripts/Generated).
        script_path: Path to existing script for modify_script action.
        add_usings: Usings to add (modify_script).
        add_fields: Fields to add (modify_script).
        add_properties: Properties to add (modify_script).
        add_methods: Methods to add (modify_script).
        add_attributes: Attributes to add (modify_script).
        window_name: EditorWindow class name (editor_window).
        menu_path: MenuItem path (editor_window).
        target_type: Target type for property_drawer/inspector_drawer.
        overlay_name: SceneView overlay class name.
        display_name: Display name for overlay header.
        drawer_body: Custom drawer OnGUI body.
        panel_body: Custom overlay panel body.
        on_gui_body: Custom OnGUI body for editor_window.
        fields_to_draw: Specific fields for inspector_drawer.
        test_mode: EditMode or PlayMode (generate_test).
        target_class: Target class for test setup (generate_test).
        test_methods: Test method definitions (generate_test).
        setup_body: SetUp method body (generate_test).
        teardown_body: TearDown method body (generate_test).
        singleton_type: MonoBehaviour or Plain (singleton).
        persistent: DontDestroyOnLoad for MonoBehaviour singletons.
        include_scene_persistent: Include auto-clear on scene load (service_locator).
        include_gameobject_pool: Include GameObjectPool subclass (object_pool).
        event_name: Event name for specific event channel subclass.
        has_parameter: Whether event carries a parameter (event_channel).
        parameter_type: C# type of event parameter (event_channel).
    """
    try:
        if action == "generate_class":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_class(
                class_name=class_name,
                class_type=class_type,
                namespace=namespace,
                usings=usings,
                base_class=base_class,
                interfaces=interfaces,
                attributes=attributes,
                fields=fields,
                properties=properties,
                methods=methods,
                enum_values=enum_values,
                summary=summary,
            )
            rel_path = f"{output_dir}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": class_name,
                "class_type": class_type,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "modify_script":
            if not script_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "script_path is required"}
                )
            project_root = Path(settings.unity_project_path).resolve()
            full_path = (project_root / script_path).resolve()
            if not str(full_path).startswith(str(project_root)):
                return json.dumps(
                    {"status": "error", "action": action, "message": "Path traversal detected"}
                )
            if not full_path.exists():
                return json.dumps(
                    {"status": "error", "action": action, "message": f"Script not found: {script_path}"}
                )
            source = full_path.read_text(encoding="utf-8")
            # Create backup
            backup_path = str(full_path) + ".bak"
            Path(backup_path).write_text(source, encoding="utf-8")
            modified, changes = modify_script(
                source=source,
                add_usings=add_usings,
                add_fields=add_fields,
                add_properties=add_properties,
                add_methods=add_methods,
                add_attributes=add_attributes,
            )
            full_path.write_text(modified, encoding="utf-8")
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": str(full_path),
                "backup_path": backup_path,
                "changes": changes,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the modified script",
                ],
            })

        elif action == "editor_window":
            if not window_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "window_name is required"}
                )
            script = generate_editor_window(
                window_name=window_name,
                menu_path=menu_path or f"VeilBreakers/Tools/{window_name}",
                namespace=namespace or "VeilBreakers.Editor",
                fields=fields,
                on_gui_body=on_gui_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{window_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                    f"Execute menu item '{menu_path or f'VeilBreakers/Tools/{window_name}'}' via mcp-unity",
                ],
            })

        elif action == "property_drawer":
            if not target_type:
                return json.dumps(
                    {"status": "error", "action": action, "message": "target_type is required"}
                )
            script = generate_property_drawer(
                target_type=target_type,
                namespace=namespace or "VeilBreakers.Editor",
                drawer_body=drawer_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{target_type}Drawer.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "inspector_drawer":
            if not target_type:
                return json.dumps(
                    {"status": "error", "action": action, "message": "target_type is required"}
                )
            script = generate_inspector_drawer(
                target_type=target_type,
                namespace=namespace or "VeilBreakers.Editor",
                fields_to_draw=fields_to_draw,
            )
            rel_path = f"Assets/Editor/Generated/Code/{target_type}Editor.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "scene_overlay":
            if not overlay_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "overlay_name is required"}
                )
            script = generate_scene_overlay(
                overlay_name=overlay_name,
                display_name=display_name or overlay_name,
                namespace=namespace or "VeilBreakers.Editor",
                panel_body=panel_body,
            )
            rel_path = f"Assets/Editor/Generated/Code/{overlay_name}Overlay.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "generate_test":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_test_class(
                class_name=class_name,
                test_mode=test_mode,
                namespace=namespace,
                target_class=target_class,
                test_methods=test_methods,
                setup_body=setup_body,
                teardown_body=teardown_body,
            )
            rel_path = f"Assets/Tests/{test_mode}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "test_mode": test_mode,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the test class",
                    "Call unity_editor action='run_tests' to execute tests",
                ],
            })

        elif action == "service_locator":
            script = generate_service_locator(
                namespace=namespace or "VeilBreakers.Patterns",
                include_scene_persistent=include_scene_persistent,
            )
            rel_path = f"{output_dir}/ServiceLocator.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "object_pool":
            script = generate_object_pool(
                namespace=namespace or "VeilBreakers.Patterns",
                include_gameobject_pool=include_gameobject_pool,
            )
            rel_path = f"{output_dir}/ObjectPool.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "singleton":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            script = generate_singleton(
                class_name=class_name,
                singleton_type=singleton_type,
                namespace=namespace or "VeilBreakers.Patterns",
                persistent=persistent,
            )
            rel_path = f"{output_dir}/{class_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "singleton_type": singleton_type,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "state_machine":
            script = generate_state_machine(
                namespace=namespace or "VeilBreakers.Patterns",
            )
            rel_path = f"{output_dir}/StateMachine.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        elif action == "event_channel":
            script = generate_so_event_channel(
                event_name=event_name,
                has_parameter=has_parameter,
                parameter_type=parameter_type,
                namespace=namespace or "VeilBreakers.Events.Channels",
            )
            file_name = f"{event_name}Event.cs" if event_name else "GameEvent.cs"
            rel_path = f"{output_dir}/{file_name}"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "event_name": event_name or "GameEvent (base classes)",
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the new script",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_code action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )


# ---------------------------------------------------------------------------
# unity_shader compound tool (SHDR-01, SHDR-02)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_shader(
    action: Literal[
        "create_shader",            # SHDR-01: Generate arbitrary HLSL/ShaderLab shader
        "create_renderer_feature",  # SHDR-02: Generate URP ScriptableRendererFeature
    ],
    # Shader params (SHDR-01)
    shader_name: str = "",
    shader_path: str = "VeilBreakers/Custom",
    render_type: str = "Opaque",
    shader_properties: list[dict] | None = None,
    vertex_code: str = "",
    fragment_code: str = "",
    shader_tags: dict | None = None,
    pragma_directives: list[str] | None = None,
    include_paths: list[str] | None = None,
    cull: str = "Back",
    zwrite: str = "",
    blend: str = "",
    two_passes: bool = False,
    second_pass_vertex: str = "",
    second_pass_fragment: str = "",
    output_dir: str = "Assets/Shaders/Generated",
    # Renderer feature params (SHDR-02)
    feature_name: str = "",
    namespace: str = "",
    settings_fields: list[dict] | None = None,
    render_pass_event: str = "BeforeRenderingPostProcessing",
    shader_property_name: str = "_shader",
    material_properties: list[dict] | None = None,
    pass_code: str = "",
) -> str:
    """Shader and renderer feature generation -- create HLSL/ShaderLab shaders
    and URP ScriptableRendererFeatures.

    Actions:
    - create_shader: Generate configurable HLSL/ShaderLab shader for URP (SHDR-01)
    - create_renderer_feature: Generate URP ScriptableRendererFeature with RenderGraph pass (SHDR-02)

    Args:
        action: The shader action to perform.
        shader_name: Display name for the shader (create_shader, required).
        shader_path: Shader menu path prefix (default VeilBreakers/Custom).
        render_type: Opaque, Transparent, or TransparentCutout.
        shader_properties: Shader property definitions (list of dicts).
        vertex_code: Custom vertex shader code.
        fragment_code: Custom fragment shader code.
        shader_tags: Additional SubShader tags.
        pragma_directives: Additional pragma directives.
        include_paths: Additional include paths.
        cull: Cull mode (Back, Front, Off).
        zwrite: ZWrite mode override.
        blend: Blend mode override.
        two_passes: Enable two-pass rendering.
        second_pass_vertex: Vertex code for second pass.
        second_pass_fragment: Fragment code for second pass.
        output_dir: Output directory for shader files.
        feature_name: Feature name (create_renderer_feature, required).
        namespace: Namespace for renderer feature.
        settings_fields: Settings field definitions.
        render_pass_event: RenderPassEvent for scheduling.
        shader_property_name: Shader serialized field name.
        material_properties: Material properties set per frame.
        pass_code: Custom RecordRenderGraph body.
    """
    try:
        if action == "create_shader":
            if not shader_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "shader_name is required"}
                )
            shader_source = generate_arbitrary_shader(
                shader_name=shader_name,
                shader_path=shader_path,
                render_type=render_type,
                properties=shader_properties,
                vertex_code=vertex_code,
                fragment_code=fragment_code,
                tags=shader_tags,
                pragma_directives=pragma_directives,
                include_paths=include_paths,
                cull=cull,
                zwrite=zwrite,
                blend=blend,
                two_passes=two_passes,
                second_pass_vertex=second_pass_vertex,
                second_pass_fragment=second_pass_fragment,
            )
            rel_path = f"{output_dir}/{shader_name}.shader"
            abs_path = _write_to_unity(shader_source, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "shader_path": abs_path,
                "shader_name": shader_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to refresh assets and compile the shader",
                ],
            })

        elif action == "create_renderer_feature":
            if not feature_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "feature_name is required"}
                )
            script = generate_renderer_feature(
                feature_name=feature_name,
                namespace=namespace,
                settings_fields=settings_fields,
                render_pass_event=render_pass_event,
                shader_property_name=shader_property_name,
                material_properties=material_properties,
                pass_code=pass_code,
            )
            rel_path = f"Assets/Scripts/Rendering/{feature_name}Feature.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "feature_name": feature_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the renderer feature",
                    f"Add {feature_name}Feature to the URP Renderer asset in Unity",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_shader action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )


def main():
    """Entry point for the vb-unity-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
