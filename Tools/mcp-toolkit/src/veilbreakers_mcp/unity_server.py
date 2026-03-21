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
    _sanitize_cs_identifier,
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
from veilbreakers_mcp.shared.unity_templates.data_templates import (
    generate_so_definition,
    generate_asset_creation_script,
    generate_json_validator_script,
    generate_json_loader_script,
    generate_localization_setup_script,
    generate_localization_entries_script,
    generate_data_authoring_window,
)
from veilbreakers_mcp.shared.unity_templates.pipeline_templates import (
    generate_gitlfs_config,
    generate_gitignore,
    generate_normal_map_bake_script,
    generate_sprite_atlas_script,
    generate_sprite_animation_script,
    generate_sprite_editor_config_script,
    generate_asset_postprocessor_script,
)
from veilbreakers_mcp.shared.unity_templates.quality_templates import (
    generate_poly_budget_check_script,
    generate_master_material_script,
    generate_texture_quality_check_script,
    generate_aaa_validation_script,
)
from veilbreakers_mcp.shared.unity_templates.game_templates import (
    generate_save_system_script,
    generate_health_system_script,
    generate_character_controller_script,
    generate_input_config_script,
    generate_settings_menu_script,
    generate_http_client_script,
    generate_interactable_script,
)
from veilbreakers_mcp.shared.unity_templates.vb_combat_templates import (
    generate_player_combat_script,
    generate_ability_system_script,
    generate_synergy_engine_script,
    generate_corruption_gameplay_script,
    generate_xp_leveling_script,
    generate_currency_system_script,
    generate_damage_type_script,
)
from veilbreakers_mcp.shared.unity_templates.content_templates import (
    generate_inventory_system_script,
    generate_dialogue_system_script,
    generate_quest_system_script,
    generate_loot_table_script,
    generate_crafting_system_script,
    generate_skill_tree_script,
    generate_dps_calculator_script,
    generate_encounter_simulator_script,
    generate_stat_curve_editor_script,
    generate_shop_system_script,
    generate_journal_system_script,
)
from veilbreakers_mcp.shared.unity_templates.equipment_templates import (
    generate_equipment_attachment_script,
)
from veilbreakers_mcp.shared.unity_templates.camera_templates import (
    generate_cinemachine_setup_script,
    generate_state_driven_camera_script,
    generate_camera_shake_script,
    generate_camera_blend_script,
    generate_timeline_setup_script,
    generate_cutscene_setup_script,
    generate_animation_clip_editor_script,
    generate_animator_modifier_script,
    generate_avatar_mask_script,
    generate_video_player_script,
)
from veilbreakers_mcp.shared.unity_templates.world_templates import (
    generate_scene_creation_script,
    generate_scene_transition_script,
    generate_probe_setup_script,
    generate_occlusion_setup_script,
    generate_environment_setup_script,
    generate_terrain_detail_script,
    generate_tilemap_setup_script,
    generate_2d_physics_script,
    generate_time_of_day_preset_script,
    generate_fast_travel_script,
    generate_puzzle_mechanics_script,
    generate_trap_system_script,
    generate_spatial_loot_script,
    generate_weather_system_script,
    generate_day_night_cycle_script,
    generate_npc_placement_script,
    generate_dungeon_lighting_script,
    generate_terrain_building_blend_script,
)
from veilbreakers_mcp.shared.unity_templates.ux_templates import (
    generate_minimap_script,
    generate_damage_numbers_script,
    generate_interaction_prompts_script,
    generate_primetween_sequence_script,
    generate_tmp_font_asset_script,
    generate_tmp_component_script,
    generate_tutorial_system_script,
    generate_accessibility_script,
    generate_character_select_script,
    generate_world_map_script,
    generate_rarity_vfx_script,
    generate_corruption_vfx_script,
)
from veilbreakers_mcp.shared.unity_templates.encounter_templates import (
    generate_encounter_system_script,
    generate_ai_director_script,
    generate_encounter_simulator_script as generate_encounter_sim_script,
    generate_boss_ai_script,
)
from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_bridge_server_script,
    generate_bridge_commands_script,
    generate_test_runner_handler,
    generate_play_session_script,
    generate_profiler_handler,
    generate_memory_leak_script,
    analyze_csharp_static,
    generate_crash_reporting_script,
    generate_analytics_script,
    generate_live_inspector_script,
)
from veilbreakers_mcp.shared.unity_templates.build_templates import (
    generate_multi_platform_build_script,
    generate_addressables_config_script,
    generate_platform_config_script,
    generate_shader_stripping_script,
    generate_github_actions_workflow,
    generate_gitlab_ci_config,
    generate_version_management_script,
    generate_changelog,
    generate_store_metadata,
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
    safe_name = _sanitize_cs_identifier(name) or "Shader"
    shader_path = f"Assets/Shaders/Generated/{safe_name}_Corruption.shader"

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
    safe_name = _sanitize_cs_identifier(name) or "Shader"
    shader_path = f"Assets/Shaders/Generated/{safe_name}_{type_label}.shader"

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
    safe_name = _sanitize_cs_identifier(name) or "sfx"
    output_rel = f"Assets/Resources/Audio/SFX/{safe_name}.mp3"

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
    safe_name = _sanitize_cs_identifier(name) or "music"
    safe_theme = _sanitize_cs_identifier(theme) or "theme"
    output_rel = f"Assets/Resources/Audio/Music/{safe_name}_{safe_theme}.mp3"

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
    safe_name = _sanitize_cs_identifier(name) or "voice"
    output_rel = f"Assets/Resources/Audio/Voice/{safe_name}.mp3"

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
    safe_biome = _sanitize_cs_identifier(biome) or "ambient"
    output_rel = f"Assets/Resources/Audio/Ambient/{safe_biome}"

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
        "create_encounter_system",   # AID-01: wave SO + encounter manager
        "create_ai_director",        # AID-02: AnimationCurve difficulty
        "simulate_encounters",       # AID-03: Monte Carlo encounter sim
        "create_boss_ai",            # VB-10: multi-phase boss FSM
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
    # Boss AI params (VB-10)
    phase_count: int = 3,
    # Common namespace
    namespace: str = "",
) -> str:
    """Unity Gameplay AI -- mob controllers, aggro, patrol, spawning, behavior trees, combat abilities, projectiles, encounters, AI director, boss AI.

    This compound tool generates C# runtime scripts for Unity gameplay AI
    systems: FSM mob controllers, aggro/threat detection, waypoint patrol,
    wave-based spawning, behavior trees, combat abilities, projectiles,
    encounter systems, AI director, encounter simulator, and boss AI.

    Actions:
    - create_mob_controller: FSM state machine with Patrol/Chase/Attack/Flee states (MOB-01)
    - create_aggro_system: OverlapSphereNonAlloc threat detection with decay (MOB-02)
    - create_patrol_route: NavMeshAgent waypoint patrol with dwell times (MOB-03)
    - create_spawn_system: Wave-based spawning with max alive tracking (MOB-04)
    - create_behavior_tree: ScriptableObject BT with Sequence/Selector/Leaf nodes (MOB-05)
    - create_combat_ability: Ability ScriptableObject + executor with cooldown queue (MOB-06)
    - create_projectile_system: Straight/arc/homing projectile with trail + impact VFX (MOB-07)
    - create_encounter_system: SO wave definitions + encounter manager MonoBehaviour (AID-01)
    - create_ai_director: AnimationCurve-driven dynamic difficulty adjustment (AID-02)
    - simulate_encounters: Monte Carlo encounter simulator EditorWindow (AID-03)
    - create_boss_ai: Multi-phase hierarchical FSM boss controller (VB-10)

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
        phase_count: Number of boss phases 2-5 (VB-10).
        namespace: C# namespace override (empty = generator default).
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
        elif action == "create_encounter_system":
            ns_kwargs: dict = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_encounter_system(name, ns_kwargs)
        elif action == "create_ai_director":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_ai_director(name, ns_kwargs)
        elif action == "simulate_encounters":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_encounter_simulator(name, ns_kwargs)
        elif action == "create_boss_ai":
            ns_kwargs = {}
            if namespace:
                ns_kwargs["namespace"] = namespace
            return await _handle_gameplay_boss_ai(name, phase_count, ns_kwargs)
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
# Encounter action handlers (AID-01, AID-02, AID-03, VB-10)
# ---------------------------------------------------------------------------


async def _handle_gameplay_encounter_system(name: str, ns_kwargs: dict) -> str:
    """Create encounter wave system with SO definitions + manager (AID-01)."""
    wave_so_cs, manager_cs = generate_encounter_system_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        wave_so_cs, f"Assets/ScriptableObjects/Encounters/VB_WaveData_{safe_name}.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, f"Assets/Scripts/Runtime/AI/VB_EncounterManager_{safe_name}.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_encounter_system",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the encounter system",
            "Create WaveData ScriptableObject assets and assign to encounter manager",
        ],
    }, indent=2)


async def _handle_gameplay_ai_director(name: str, ns_kwargs: dict) -> str:
    """Create AI director with AnimationCurve-driven difficulty (AID-02)."""
    script = generate_ai_director_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_AIDirector_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_ai_director",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the AI director",
            "Attach VB_AIDirector to a persistent game manager object",
        ],
    }, indent=2)


async def _handle_gameplay_encounter_simulator(name: str, ns_kwargs: dict) -> str:
    """Create Monte Carlo encounter simulator EditorWindow (AID-03)."""
    script = generate_encounter_sim_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/Tools/VB_EncounterSim_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "simulate_encounters",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the simulator",
            "Open from VeilBreakers > Tools > Encounter Simulator",
        ],
    }, indent=2)


async def _handle_gameplay_boss_ai(name: str, phase_count: int, ns_kwargs: dict) -> str:
    """Create multi-phase boss AI with hierarchical FSM (VB-10)."""
    script = generate_boss_ai_script(name=name, phase_count=phase_count, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/AI/VB_BossAI_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_boss_ai",
        "name": name,
        "phase_count": phase_count,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the boss AI",
            "Attach VB_BossAI to the boss prefab root",
        ],
    }, indent=2)


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
            try:
                full_path.relative_to(project_root)
            except ValueError:
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
            safe_shader_name = _sanitize_cs_identifier(shader_name) or "Shader"
            rel_path = f"{output_dir}/{safe_shader_name}.shader"
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
            safe_feature = _sanitize_cs_identifier(feature_name) or "Feature"
            rel_path = f"Assets/Scripts/Rendering/{safe_feature}Feature.cs"
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


# ---------------------------------------------------------------------------
# Compound tool: unity_data (DATA-01, DATA-02, DATA-03, DATA-04)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_data(
    action: Literal[
        "create_so_definition",       # DATA-02: ScriptableObject class definition
        "create_so_assets",           # DATA-02: .asset file instantiation
        "validate_json",             # DATA-01: JSON config schema validator
        "create_json_loader",        # DATA-01: Typed C# data class + JSON loader
        "setup_localization",        # DATA-03: Unity Localization infrastructure
        "add_localization_entries",   # DATA-03: String table entry population
        "create_data_editor",        # DATA-04: IMGUI EditorWindow for SO authoring
    ],
    # SO definition params
    class_name: str = "",
    namespace: str = "VeilBreakers.Data",
    fields: list[dict] | None = None,
    summary: str = "",
    menu_name: str = "",
    file_name: str = "",
    # Asset creation params
    so_class_name: str = "",
    assets: list[dict] | None = None,
    output_folder: str = "Assets/Data",
    category: str = "",
    # JSON params
    config_name: str = "",
    json_path: str = "",
    schema: dict | None = None,
    wrapper_class: str = "",
    is_array: bool = True,
    # Localization params
    default_locale: str = "en",
    locales: list[str] | None = None,
    table_name: str = "VeilBreakers_UI",
    entries: dict[str, str] | None = None,
    locale: str = "en",
    # Data editor params
    window_name: str = "",
    menu_path: str = "",
    data_folder: str = "Assets/Data",
) -> str:
    """Data-driven game architecture -- ScriptableObject definitions, JSON config
    loading, localization setup, and data authoring editor windows.

    This compound tool generates C# editor scripts for data architecture,
    writes them to the Unity project, and returns instructions for executing
    them via mcp-unity.

    Actions:
    - create_so_definition: Generate ScriptableObject class with CreateAssetMenu (DATA-02)
    - create_so_assets: Create .asset instances from a ScriptableObject class (DATA-02)
    - validate_json: Generate JSON config schema validator (DATA-01)
    - create_json_loader: Generate typed C# data class + JSON loader (DATA-01)
    - setup_localization: Set up Unity Localization infrastructure (DATA-03)
    - add_localization_entries: Populate string table entries (DATA-03)
    - create_data_editor: Generate IMGUI EditorWindow for batch SO authoring (DATA-04)

    Args:
        action: The data action to perform.
        class_name: C# class name for SO definition or JSON loader.
        namespace: C# namespace (default VeilBreakers.Data).
        fields: Field definitions (list of dicts with name, type, optional default/label).
        summary: XML summary comment for the class.
        menu_name: CreateAssetMenu menu name for SO.
        file_name: Default file name for SO asset creation.
        so_class_name: ScriptableObject class name for asset creation or data editor.
        assets: List of asset data dicts for create_so_assets.
        output_folder: Output folder for assets (default Assets/Data).
        category: Category name for asset organization.
        config_name: Config name for JSON validator.
        json_path: JSON file path for validation or loading.
        schema: JSON schema dict for validator.
        wrapper_class: Wrapper class name for JSON validator.
        is_array: Whether JSON data is an array (for JSON loader).
        default_locale: Default locale for localization (default en).
        locales: List of additional locale codes.
        table_name: String table name for localization.
        entries: Dict of key->value entries for localization.
        locale: Locale code for localization entries.
        window_name: EditorWindow class name for data editor.
        menu_path: MenuItem path for data editor.
        data_folder: Folder for data editor to browse (default Assets/Data).
    """
    try:
        if action == "create_so_definition":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(class_name) or "SODefinition"
            script = generate_so_definition(
                class_name=safe_class,
                namespace=namespace,
                fields=fields or [],
                summary=summary,
                menu_name=menu_name,
                file_name=file_name,
            )
            rel_path = f"Assets/Scripts/Generated/Data/{safe_class}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": safe_class,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the SO definition",
                ],
            })

        elif action == "create_so_assets":
            if not so_class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "so_class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(so_class_name) or "SOClass"
            script = generate_asset_creation_script(
                so_class_name=safe_class,
                namespace=namespace,
                assets=assets or [],
                output_folder=output_folder,
                category=category,
                menu_path=menu_path or f"VeilBreakers/Data/Create {safe_class} Assets",
            )
            rel_path = f"Assets/Editor/Generated/Data/Create_{safe_class}_Assets.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "so_class_name": safe_class,
                "asset_count": len(assets or []),
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the script",
                    f"Execute menu item: VeilBreakers/Data/Create {safe_class} Assets",
                ],
            })

        elif action == "validate_json":
            if not config_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "config_name is required"}
                )
            safe_config = _sanitize_cs_identifier(config_name) or "Config"
            script = generate_json_validator_script(
                config_name=safe_config,
                json_path=json_path,
                schema=schema or {},
                wrapper_class=wrapper_class,
            )
            rel_path = f"Assets/Editor/Generated/Data/Validate_{safe_config}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "config_name": safe_config,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the validator",
                    f"Execute menu item: VeilBreakers/Data/Validate {safe_config}",
                ],
            })

        elif action == "create_json_loader":
            if not class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "class_name is required"}
                )
            safe_class = _sanitize_cs_identifier(class_name) or "DataLoader"
            script = generate_json_loader_script(
                class_name=safe_class,
                namespace=namespace,
                fields=fields or [],
                json_path=json_path,
                is_array=is_array,
            )
            rel_path = f"Assets/Scripts/Generated/Data/{safe_class}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "class_name": safe_class,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the loader class",
                ],
            })

        elif action == "setup_localization":
            script = generate_localization_setup_script(
                default_locale=default_locale,
                locales=locales or [],
                table_name=table_name,
                output_dir=output_folder,
            )
            safe_table = _sanitize_cs_identifier(table_name) or "Localization"
            rel_path = f"Assets/Editor/Generated/Data/Setup_{safe_table}_Localization.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "table_name": table_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the setup script",
                    f"Execute menu item: VeilBreakers/Data/Setup {table_name} Localization",
                ],
            })

        elif action == "add_localization_entries":
            if not entries:
                return json.dumps(
                    {"status": "error", "action": action, "message": "entries dict is required"}
                )
            script = generate_localization_entries_script(
                table_name=table_name,
                entries=entries,
                locale=locale,
            )
            safe_table = _sanitize_cs_identifier(table_name) or "Localization"
            rel_path = f"Assets/Editor/Generated/Data/Add_{safe_table}_{locale}_Entries.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "table_name": table_name,
                "locale": locale,
                "entry_count": len(entries),
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the entries script",
                    f"Execute menu item: VeilBreakers/Data/Add {table_name} {locale} Entries",
                ],
            })

        elif action == "create_data_editor":
            if not window_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "window_name is required"}
                )
            if not so_class_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "so_class_name is required"}
                )
            safe_window = _sanitize_cs_identifier(window_name) or "DataEditor"
            safe_so = _sanitize_cs_identifier(so_class_name) or "SOClass"
            script = generate_data_authoring_window(
                window_name=safe_window,
                so_class_name=safe_so,
                namespace=namespace,
                fields=fields or [],
                menu_path=menu_path or f"VeilBreakers/Data/{safe_window}",
                data_folder=data_folder,
                category=category,
            )
            rel_path = f"Assets/Editor/Generated/Data/{safe_window}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "window_name": safe_window,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the editor window",
                    f"Open via menu: {menu_path or f'VeilBreakers/Data/{safe_window}'}",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_data action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )


# ---------------------------------------------------------------------------
# Compound tool: unity_quality (AAA-01, AAA-02, AAA-03, AAA-04, AAA-06)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_quality(
    action: Literal[
        "check_poly_budget",         # AAA-02: Per-asset-type polygon budget check
        "create_master_materials",   # AAA-04: Master material library generation
        "check_texture_quality",     # AAA-06: Texture quality validation
        "aaa_audit",                 # Combined AAA quality audit
    ],
    asset_type: str = "prop",
    target_path: str = "",
    target_folder: str = "Assets",
    auto_flag: bool = True,
    output_folder: str = "Assets/Data/Materials/MasterLibrary",
    materials: list[dict] | None = None,
    target_texel_density: float = 10.24,
    check_normal_maps: bool = True,
    check_channel_packing: bool = True,
    check_poly: bool = True,
    check_textures: bool = True,
    check_materials: bool = True,
) -> str:
    """AAA quality enforcement -- polygon budgets, master materials, texture
    quality, and combined quality auditing.

    This compound tool generates C# editor scripts that validate and enforce
    AAA quality standards for VeilBreakers game assets.

    Actions:
    - check_poly_budget: Check polygon counts against per-asset-type budgets (AAA-02)
    - create_master_materials: Generate master material library with PBR presets (AAA-04)
    - check_texture_quality: Validate texel density, normal maps, channel packing (AAA-06)
    - aaa_audit: Combined AAA quality audit (poly + texture + material checks)

    Args:
        action: The quality action to perform.
        asset_type: Asset type for poly budget (hero/mob/weapon/prop/building).
        target_path: Target path for poly budget check.
        target_folder: Target folder for texture quality or AAA audit.
        auto_flag: Auto-flag assets exceeding budgets.
        output_folder: Output folder for master materials.
        materials: Custom material definitions for master library.
        target_texel_density: Target texel density in px/m (default 10.24).
        check_normal_maps: Whether to validate normal maps.
        check_channel_packing: Whether to check channel packing.
        check_poly: Include poly check in AAA audit.
        check_textures: Include texture check in AAA audit.
        check_materials: Include material check in AAA audit.
    """
    try:
        if action == "check_poly_budget":
            safe_type = _sanitize_cs_identifier(asset_type) or "prop"
            script = generate_poly_budget_check_script(
                asset_type=safe_type,
                target_path=target_path,
                auto_flag=auto_flag,
            )
            rel_path = f"Assets/Editor/Generated/Quality/PolyBudgetCheck_{safe_type}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "asset_type": safe_type,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the budget check",
                    f"Execute menu item: VeilBreakers/Quality/Check Poly Budget ({safe_type})",
                ],
            })

        elif action == "create_master_materials":
            script = generate_master_material_script(
                output_folder=output_folder,
                materials=materials,
            )
            rel_path = "Assets/Editor/Generated/Quality/CreateMasterMaterials.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "material_count": len(materials) if materials else "default",
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the script",
                    "Execute menu item: VeilBreakers/Quality/Create Master Materials",
                ],
            })

        elif action == "check_texture_quality":
            script = generate_texture_quality_check_script(
                target_folder=target_folder,
                target_texel_density=target_texel_density,
                check_normal_maps=check_normal_maps,
                check_channel_packing=check_channel_packing,
            )
            rel_path = "Assets/Editor/Generated/Quality/TextureQualityCheck.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the checker",
                    "Execute menu item: VeilBreakers/Quality/Check Texture Quality",
                ],
            })

        elif action == "aaa_audit":
            safe_type = _sanitize_cs_identifier(asset_type) or "prop"
            script = generate_aaa_validation_script(
                target_folder=target_folder,
                asset_type=safe_type,
                check_poly=check_poly,
                check_textures=check_textures,
                check_materials=check_materials,
            )
            rel_path = "Assets/Editor/Generated/Quality/AAAQualityAudit.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "asset_type": safe_type,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the audit script",
                    "Execute menu item: VeilBreakers/Quality/AAA Quality Audit",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_quality action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )


# ---------------------------------------------------------------------------
# Compound tool: unity_pipeline (BUILD-06, TWO-03, PIPE-08, IMP-03)
# ---------------------------------------------------------------------------


@mcp.tool()
async def unity_pipeline(
    action: Literal[
        "create_sprite_atlas",       # BUILD-06: SpriteAtlas creation
        "create_sprite_animation",   # BUILD-06: Sprite AnimationClip
        "configure_sprite_editor",   # TWO-03: Sprite Editor configuration
        "create_asset_postprocessor",  # PIPE-08: AssetPostprocessor with folder rules
        "configure_git_lfs",         # IMP-03: Git LFS + .gitignore setup
    ],
    # Sprite atlas params
    atlas_name: str = "",
    source_folder: str = "",
    padding: int = 4,
    enable_tight_packing: bool = True,
    enable_rotation: bool = False,
    max_texture_size: int = 4096,
    srgb: bool = True,
    filter_mode: str = "Bilinear",
    include_in_build: bool = True,
    # Sprite animation params
    clip_name: str = "",
    sprite_folder: str = "",
    frame_rate: int = 12,
    loop: bool = True,
    # Sprite editor params
    sprite_path: str = "",
    pivot: list[float] | None = None,
    border: list[int] | None = None,
    pixels_per_unit: int = 100,
    sprite_mode: int = 1,
    custom_physics_shape: bool = False,
    # Postprocessor params
    processor_name: str = "",
    version: int = 1,
    texture_rules: list[dict] | None = None,
    model_rules: list[dict] | None = None,
    audio_rules: list[dict] | None = None,
    namespace: str = "VeilBreakers.Editor",
    # Git LFS params
    extra_extensions: list[str] | None = None,
    include_unity_yaml_merge: bool = True,
    extra_patterns: list[str] | None = None,
    output_path: str = "",
) -> str:
    """Asset pipeline automation -- sprite atlasing, sprite animation, Sprite
    Editor configuration, AssetPostprocessor, and Git LFS setup.

    This compound tool generates C# editor scripts and configuration files
    for Unity asset pipeline automation.

    Actions:
    - create_sprite_atlas: Create SpriteAtlas with folder sources (BUILD-06)
    - create_sprite_animation: Create sprite-based AnimationClip (BUILD-06)
    - configure_sprite_editor: Configure Sprite Editor import settings (TWO-03)
    - create_asset_postprocessor: Create AssetPostprocessor with folder rules (PIPE-08)
    - configure_git_lfs: Generate .gitattributes and .gitignore for Unity project (IMP-03)

    Args:
        action: The pipeline action to perform.
        atlas_name: SpriteAtlas name.
        source_folder: Source folder for sprites.
        padding: Atlas padding in pixels (default 4).
        enable_tight_packing: Enable tight packing (default True).
        enable_rotation: Allow sprite rotation in atlas (default False).
        max_texture_size: Maximum atlas texture size (default 4096).
        srgb: sRGB color space (default True).
        filter_mode: Texture filter mode (default Bilinear).
        include_in_build: Include atlas in build (default True).
        clip_name: Animation clip name.
        sprite_folder: Folder containing sprite frames.
        frame_rate: Animation frame rate (default 12).
        loop: Loop animation (default True).
        sprite_path: Path to sprite asset for editor config.
        pivot: Sprite pivot point [x, y] (default center).
        border: Sprite border [left, bottom, right, top].
        pixels_per_unit: Pixels per unit (default 100).
        sprite_mode: Sprite mode (1=Single, 2=Multiple, 3=Polygon).
        custom_physics_shape: Enable custom physics shape.
        processor_name: AssetPostprocessor class name.
        version: Postprocessor version number.
        texture_rules: Texture import rules list.
        model_rules: Model import rules list.
        audio_rules: Audio import rules list.
        namespace: C# namespace for postprocessor.
        extra_extensions: Additional file extensions for Git LFS tracking.
        include_unity_yaml_merge: Include Unity YAML merge driver config.
        extra_patterns: Additional .gitignore patterns.
        output_path: Output path for generated files.
    """
    try:
        if action == "create_sprite_atlas":
            if not atlas_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "atlas_name is required"}
                )
            safe_name = _sanitize_cs_identifier(atlas_name) or "Atlas"
            script = generate_sprite_atlas_script(
                atlas_name=safe_name,
                source_folder=source_folder,
                output_path=output_path or f"Assets/SpriteAtlases/{safe_name}.spriteatlas",
                padding=padding,
                enable_tight_packing=enable_tight_packing,
                enable_rotation=enable_rotation,
                max_texture_size=max_texture_size,
                srgb=srgb,
                filter_mode=filter_mode,
                include_in_build=include_in_build,
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/Create_{safe_name}_Atlas.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "atlas_name": safe_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the atlas script",
                    f"Execute menu item: VeilBreakers/Pipeline/Create {safe_name} Atlas",
                ],
            })

        elif action == "create_sprite_animation":
            if not clip_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "clip_name is required"}
                )
            safe_clip = _sanitize_cs_identifier(clip_name) or "SpriteAnim"
            script = generate_sprite_animation_script(
                clip_name=safe_clip,
                sprite_folder=sprite_folder,
                frame_rate=frame_rate,
                loop=loop,
                output_path=output_path or f"Assets/Animations/{safe_clip}.anim",
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/Create_{safe_clip}_Animation.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "clip_name": safe_clip,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the animation script",
                    f"Execute menu item: VeilBreakers/Pipeline/Create {safe_clip} Animation",
                ],
            })

        elif action == "configure_sprite_editor":
            if not sprite_path:
                return json.dumps(
                    {"status": "error", "action": action, "message": "sprite_path is required"}
                )
            # Convert list params to tuples for the generator
            pivot_tuple = tuple(pivot) if pivot else None
            border_tuple = tuple(border) if border else None
            script = generate_sprite_editor_config_script(
                sprite_path=sprite_path,
                pivot=pivot_tuple,
                border=border_tuple,
                pixels_per_unit=pixels_per_unit,
                sprite_mode=sprite_mode,
                custom_physics_shape=custom_physics_shape,
            )
            rel_path = "Assets/Editor/Generated/Pipeline/ConfigureSpriteEditor.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "sprite_path": sprite_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the configuration script",
                    "Execute menu item: VeilBreakers/Pipeline/Configure Sprite Editor",
                ],
            })

        elif action == "create_asset_postprocessor":
            if not processor_name:
                return json.dumps(
                    {"status": "error", "action": action, "message": "processor_name is required"}
                )
            safe_name = _sanitize_cs_identifier(processor_name) or "Postprocessor"
            script = generate_asset_postprocessor_script(
                processor_name=safe_name,
                version=version,
                texture_rules=texture_rules,
                model_rules=model_rules,
                audio_rules=audio_rules,
                namespace=namespace,
            )
            rel_path = f"Assets/Editor/Generated/Pipeline/{safe_name}.cs"
            abs_path = _write_to_unity(script, rel_path)
            return json.dumps({
                "status": "success",
                "action": action,
                "script_path": abs_path,
                "processor_name": safe_name,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile the postprocessor",
                    "The postprocessor will run automatically on future asset imports",
                ],
            })

        elif action == "configure_git_lfs":
            # Generate .gitattributes
            gitattributes = generate_gitlfs_config(
                extra_extensions=extra_extensions,
                include_unity_yaml_merge=include_unity_yaml_merge,
            )
            # Generate .gitignore
            gitignore = generate_gitignore(
                extra_patterns=extra_patterns,
            )
            # Write to Unity project root
            gitattr_path = _write_to_unity(gitattributes, ".gitattributes")
            gitignore_path = _write_to_unity(gitignore, ".gitignore")
            return json.dumps({
                "status": "success",
                "action": action,
                "gitattributes_path": gitattr_path,
                "gitignore_path": gitignore_path,
                "next_steps": [
                    "Run 'git lfs install' in the Unity project directory if not already configured",
                    "Commit the .gitattributes and .gitignore files",
                ],
            })

        else:
            return json.dumps(
                {"status": "error", "message": f"Unknown action: {action}"}
            )

    except Exception as exc:
        logger.exception("unity_pipeline action '%s' failed", action)
        return json.dumps(
            {"status": "error", "action": action, "message": str(exc)}
        )


@mcp.tool()
async def unity_game(
    action: Literal[
        # Core Game Systems (game_templates.py)
        "create_save_system",          # GAME-01
        "create_health_system",        # GAME-05
        "create_character_controller",  # GAME-06
        "create_input_config",         # GAME-07
        "create_settings_menu",        # GAME-08
        "create_http_client",          # MEDIA-02
        "create_interactable",         # RPG-03
        # VeilBreakers Combat (vb_combat_templates.py)
        "create_player_combat",        # VB-01
        "create_ability_system",       # VB-02
        "create_synergy_engine",       # VB-03
        "create_corruption_gameplay",  # VB-04
        "create_xp_leveling",         # VB-05
        "create_currency_system",      # VB-06
        "create_damage_types",         # VB-07
    ],
    name: str = "default",
    # Save system params (GAME-01)
    slot_count: int = 3,
    use_encryption: bool = True,
    use_compression: bool = True,
    auto_save: bool = True,
    # Health system params (GAME-05)
    max_hp: int = 100,
    use_damage_numbers: bool = True,
    use_respawn: bool = True,
    respawn_delay: float = 3.0,
    # Character controller params (GAME-06)
    mode: str = "third_person",
    move_speed: float = 5.0,
    sprint_multiplier: float = 1.5,
    jump_height: float = 1.5,
    gravity: float = -20.0,
    rotation_speed: float = 10.0,
    # Input params (GAME-07)
    action_maps: list[dict] | None = None,
    include_gamepad: bool = True,
    include_rebinding: bool = True,
    # Settings params (GAME-08)
    categories: list[str] | None = None,
    theme: str = "dark_fantasy",
    # HTTP params (MEDIA-02)
    base_url: str = "",
    max_retries: int = 3,
    timeout_seconds: int = 30,
    # Interactable params (RPG-03)
    interactable_types: list[str] | None = None,
    interaction_radius: float = 2.0,
    use_animation: bool = True,
    use_sound: bool = True,
    # Combat params (VB-01)
    light_combo_count: int = 3,
    heavy_combo_count: int = 2,
    dodge_iframe_duration: float = 0.2,
    dodge_distance: float = 4.0,
    block_stamina_drain: float = 10.0,
    stamina_max: float = 100.0,
    stamina_regen_rate: float = 15.0,
    # Ability params (VB-02)
    max_ability_slots: int = 4,
    mana_max: float = 100.0,
    mana_regen_rate: float = 5.0,
    # Corruption params (VB-04)
    thresholds: list[int] | None = None,
    # XP params (VB-05)
    max_level: int = 50,
    base_xp_per_level: int = 100,
    xp_scaling_factor: float = 1.15,
    # Currency params (VB-06)
    currency_types: list[str] | None = None,
    # Namespace (shared)
    namespace: str = "",
) -> str:
    """Core game systems and VeilBreakers combat -- save/load, health, character
    controller, input, settings, HTTP client, interactables, player combat,
    abilities, synergy, corruption, XP/leveling, currency, and damage types.

    This compound tool generates C# runtime scripts for Unity game systems and
    VeilBreakers-specific combat mechanics. Scripts are written to
    Assets/Scripts/Runtime/ -- they are runtime MonoBehaviours and utility
    classes, NOT editor scripts.

    Core Game Systems actions (game_templates.py):
    - create_save_system: JSON save/load with AES-CBC encryption, migration, auto-save (GAME-01)
    - create_health_system: HP component with DamageCalculator, damage numbers, respawn (GAME-05)
    - create_character_controller: Third-person CharacterController + Cinemachine 3.x (GAME-06)
    - create_input_config: Input System .inputactions JSON + C# wrapper with rebinding (GAME-07)
    - create_settings_menu: Settings C# controller + UXML layout + USS stylesheet (GAME-08)
    - create_http_client: UnityWebRequest wrapper with retry, timeout, Awaitable (MEDIA-02)
    - create_interactable: Interactable state machine + InteractionManager (RPG-03)

    VeilBreakers Combat actions (vb_combat_templates.py):
    - create_player_combat: FSM combat controller with combos, dodge, block (VB-01)
    - create_ability_system: Brand-specific ability system with mana (VB-02)
    - create_synergy_engine: Synergy wiring delegating to SynergySystem (VB-03)
    - create_corruption_gameplay: Corruption effects delegating to CorruptionSystem (VB-04)
    - create_xp_leveling: XP/leveling with EventBus integration (VB-05)
    - create_currency_system: Multi-currency system (VB-06)
    - create_damage_types: Brand-specific damage types delegating to BrandSystem (VB-07)

    Args:
        action: The game system action to perform.
        name: Name for the generated script/system.
        slot_count: Number of save slots (GAME-01, default 3).
        use_encryption: Enable AES-CBC save encryption (GAME-01).
        use_compression: Enable GZip save compression (GAME-01).
        auto_save: Enable auto-save system (GAME-01).
        max_hp: Maximum health points (GAME-05).
        use_damage_numbers: Enable floating damage numbers (GAME-05).
        use_respawn: Enable respawn system (GAME-05).
        respawn_delay: Respawn delay in seconds (GAME-05).
        mode: Controller mode: third_person or first_person (GAME-06).
        move_speed: Base movement speed (GAME-06).
        sprint_multiplier: Sprint speed multiplier (GAME-06).
        jump_height: Jump height in units (GAME-06).
        gravity: Gravity force (GAME-06, negative value).
        rotation_speed: Character rotation speed (GAME-06).
        action_maps: Custom action map definitions (GAME-07).
        include_gamepad: Include gamepad bindings (GAME-07).
        include_rebinding: Include runtime rebinding support (GAME-07).
        categories: Settings categories list (GAME-08).
        theme: UI theme for settings menu (GAME-08).
        base_url: Base URL for HTTP client (MEDIA-02).
        max_retries: HTTP retry count (MEDIA-02).
        timeout_seconds: HTTP timeout in seconds (MEDIA-02).
        interactable_types: Custom interactable type names (RPG-03).
        interaction_radius: Interaction detection radius (RPG-03).
        use_animation: Enable interaction animations (RPG-03).
        use_sound: Enable interaction sounds (RPG-03).
        light_combo_count: Light attack combo chain length (VB-01).
        heavy_combo_count: Heavy attack combo chain length (VB-01).
        dodge_iframe_duration: Dodge invincibility frame duration (VB-01).
        dodge_distance: Dodge roll distance (VB-01).
        block_stamina_drain: Stamina drain per blocked hit (VB-01).
        stamina_max: Maximum stamina (VB-01).
        stamina_regen_rate: Stamina regeneration per second (VB-01).
        max_ability_slots: Ability hotbar slot count (VB-02).
        mana_max: Maximum mana (VB-02).
        mana_regen_rate: Mana regeneration per second (VB-02).
        thresholds: Corruption threshold percentages (VB-04).
        max_level: Maximum character level (VB-05).
        base_xp_per_level: Base XP required per level (VB-05).
        xp_scaling_factor: XP requirement scaling factor (VB-05).
        currency_types: Custom currency type names (VB-06).
        namespace: C# namespace override (empty = generator default).
    """
    try:
        # Build namespace kwargs -- only pass if non-empty to use generator defaults
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_save_system":
            return await _handle_game_save_system(
                slot_count, use_encryption, use_compression, auto_save, ns_kwargs,
            )
        elif action == "create_health_system":
            return await _handle_game_health_system(
                max_hp, use_damage_numbers, use_respawn, respawn_delay, ns_kwargs,
            )
        elif action == "create_character_controller":
            return await _handle_game_character_controller(
                mode, move_speed, sprint_multiplier, jump_height, gravity,
                rotation_speed, ns_kwargs,
            )
        elif action == "create_input_config":
            return await _handle_game_input_config(
                action_maps, include_gamepad, include_rebinding, ns_kwargs,
            )
        elif action == "create_settings_menu":
            return await _handle_game_settings_menu(categories, theme, ns_kwargs)
        elif action == "create_http_client":
            return await _handle_game_http_client(
                base_url, max_retries, timeout_seconds, ns_kwargs,
            )
        elif action == "create_interactable":
            return await _handle_game_interactable(
                interactable_types, interaction_radius, use_animation, use_sound,
                ns_kwargs,
            )
        elif action == "create_player_combat":
            return await _handle_game_player_combat(
                light_combo_count, heavy_combo_count, dodge_iframe_duration,
                dodge_distance, block_stamina_drain, stamina_max, stamina_regen_rate,
                ns_kwargs,
            )
        elif action == "create_ability_system":
            return await _handle_game_ability_system(
                max_ability_slots, mana_max, mana_regen_rate, ns_kwargs,
            )
        elif action == "create_synergy_engine":
            return await _handle_game_synergy_engine(ns_kwargs)
        elif action == "create_corruption_gameplay":
            return await _handle_game_corruption_gameplay(thresholds, ns_kwargs)
        elif action == "create_xp_leveling":
            return await _handle_game_xp_leveling(
                max_level, base_xp_per_level, xp_scaling_factor, ns_kwargs,
            )
        elif action == "create_currency_system":
            return await _handle_game_currency_system(currency_types, ns_kwargs)
        elif action == "create_damage_types":
            return await _handle_game_damage_types(ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_game action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Game action handlers -- Core Game Systems
# ---------------------------------------------------------------------------


async def _handle_game_save_system(
    slot_count: int, use_encryption: bool, use_compression: bool,
    auto_save: bool, ns_kwargs: dict,
) -> str:
    """Create save system (GAME-01)."""
    script = generate_save_system_script(
        slot_count=slot_count,
        use_encryption=use_encryption,
        use_compression=use_compression,
        auto_save=auto_save,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/SaveSystem/SaveSystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_save_system",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the save system",
            "Attach SaveManager to a persistent GameObject in the scene",
        ],
    }, indent=2)


async def _handle_game_health_system(
    max_hp: int, use_damage_numbers: bool, use_respawn: bool,
    respawn_delay: float, ns_kwargs: dict,
) -> str:
    """Create health system (GAME-05)."""
    script = generate_health_system_script(
        max_hp=max_hp,
        use_damage_numbers=use_damage_numbers,
        use_respawn=use_respawn,
        respawn_delay=respawn_delay,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Health/HealthSystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_health_system",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the health system",
            "Attach HealthComponent to entities that need HP tracking",
        ],
    }, indent=2)


async def _handle_game_character_controller(
    mode: str, move_speed: float, sprint_multiplier: float,
    jump_height: float, gravity: float, rotation_speed: float,
    ns_kwargs: dict,
) -> str:
    """Create character controller (GAME-06)."""
    safe_mode = _sanitize_cs_identifier(mode) or "third_person"
    script = generate_character_controller_script(
        mode=safe_mode,
        move_speed=move_speed,
        sprint_multiplier=sprint_multiplier,
        jump_height=jump_height,
        gravity=gravity,
        rotation_speed=rotation_speed,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Character/CharacterController.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_character_controller",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the character controller",
            "Attach VBCharacterController to the player GameObject",
            "Add a Cinemachine CinemachineCamera to the scene for camera follow",
        ],
    }, indent=2)


async def _handle_game_input_config(
    action_maps: list[dict] | None, include_gamepad: bool,
    include_rebinding: bool, ns_kwargs: dict,
) -> str:
    """Create input config (GAME-07) -- returns tuple (JSON, C#)."""
    json_content, cs_content = generate_input_config_script(
        action_maps=action_maps,
        include_gamepad=include_gamepad,
        include_rebinding=include_rebinding,
        **ns_kwargs,
    )
    # Write .inputactions JSON to Settings folder
    json_path = "Assets/Settings/VeilBreakers.inputactions"
    abs_json = _write_to_unity(json_content, json_path)
    # Write C# wrapper to Runtime
    cs_path = "Assets/Scripts/Runtime/GameSystems/Input/InputConfig.cs"
    abs_cs = _write_to_unity(cs_content, cs_path)
    return json.dumps({
        "status": "success",
        "action": "create_input_config",
        "files": {
            "inputactions": abs_json,
            "csharp": abs_cs,
        },
        "next_steps": [
            "Call unity_editor action='recompile' to compile the input wrapper",
            "The .inputactions file will be recognized by Unity's Input System",
        ],
    }, indent=2)


async def _handle_game_settings_menu(
    categories: list[str] | None, theme: str, ns_kwargs: dict,
) -> str:
    """Create settings menu (GAME-08) -- returns tuple (C#, UXML, USS)."""
    safe_theme = _sanitize_cs_identifier(theme) or "dark_fantasy"
    cs_content, uxml_content, uss_content = generate_settings_menu_script(
        categories=categories,
        theme=safe_theme,
        **ns_kwargs,
    )
    # Write C# controller to Runtime
    cs_path = "Assets/Scripts/Runtime/GameSystems/Settings/SettingsMenu.cs"
    abs_cs = _write_to_unity(cs_content, cs_path)
    # Write UXML layout to UI folder
    uxml_path = "Assets/UI/SettingsMenu.uxml"
    abs_uxml = _write_to_unity(uxml_content, uxml_path)
    # Write USS stylesheet to UI folder
    uss_path = "Assets/UI/SettingsMenu.uss"
    abs_uss = _write_to_unity(uss_content, uss_path)
    return json.dumps({
        "status": "success",
        "action": "create_settings_menu",
        "files": {
            "csharp": abs_cs,
            "uxml": abs_uxml,
            "uss": abs_uss,
        },
        "next_steps": [
            "Call unity_editor action='recompile' to compile the settings controller",
            "Reference the UXML and USS from the SettingsMenuController component",
        ],
    }, indent=2)


async def _handle_game_http_client(
    base_url: str, max_retries: int, timeout_seconds: int, ns_kwargs: dict,
) -> str:
    """Create HTTP client (MEDIA-02)."""
    script = generate_http_client_script(
        base_url=base_url,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Network/HttpClient.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_http_client",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the HTTP client",
            "Use VBHttpClient.Instance for all HTTP requests",
        ],
    }, indent=2)


async def _handle_game_interactable(
    interactable_types: list[str] | None, interaction_radius: float,
    use_animation: bool, use_sound: bool, ns_kwargs: dict,
) -> str:
    """Create interactable system (RPG-03)."""
    script = generate_interactable_script(
        interactable_types=interactable_types,
        interaction_radius=interaction_radius,
        use_animation=use_animation,
        use_sound=use_sound,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Interaction/Interactable.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_interactable",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the interactable system",
            "Attach InteractableBase to objects and InteractionManager to the player",
        ],
    }, indent=2)


# ---------------------------------------------------------------------------
# Game action handlers -- VeilBreakers Combat
# ---------------------------------------------------------------------------


async def _handle_game_player_combat(
    light_combo_count: int, heavy_combo_count: int,
    dodge_iframe_duration: float, dodge_distance: float,
    block_stamina_drain: float, stamina_max: float,
    stamina_regen_rate: float, ns_kwargs: dict,
) -> str:
    """Create player combat controller (VB-01)."""
    script = generate_player_combat_script(
        light_combo_count=light_combo_count,
        heavy_combo_count=heavy_combo_count,
        dodge_iframe_duration=dodge_iframe_duration,
        dodge_distance=dodge_distance,
        block_stamina_drain=block_stamina_drain,
        stamina_max=stamina_max,
        stamina_regen_rate=stamina_regen_rate,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/PlayerCombat.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_player_combat",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the combat controller",
            "Attach PlayerCombatController to the player GameObject",
        ],
    }, indent=2)


async def _handle_game_ability_system(
    max_ability_slots: int, mana_max: float, mana_regen_rate: float,
    ns_kwargs: dict,
) -> str:
    """Create ability system (VB-02)."""
    script = generate_ability_system_script(
        max_ability_slots=max_ability_slots,
        mana_max=mana_max,
        mana_regen_rate=mana_regen_rate,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/AbilitySystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_ability_system",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the ability system",
            "Attach AbilityManager to the player, create AbilityDefinition SO assets",
        ],
    }, indent=2)


async def _handle_game_synergy_engine(ns_kwargs: dict) -> str:
    """Create synergy engine (VB-03)."""
    script = generate_synergy_engine_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/Combat/SynergyEngine.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_synergy_engine",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the synergy engine",
            "SynergyWiringManager auto-registers with EventBus on Awake",
        ],
    }, indent=2)


async def _handle_game_corruption_gameplay(
    thresholds: list[int] | None, ns_kwargs: dict,
) -> str:
    """Create corruption gameplay system (VB-04)."""
    script = generate_corruption_gameplay_script(
        thresholds=thresholds,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/Combat/CorruptionGameplay.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_corruption_gameplay",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the corruption system",
            "Attach CorruptionEffectsManager to the player",
        ],
    }, indent=2)


async def _handle_game_xp_leveling(
    max_level: int, base_xp_per_level: int, xp_scaling_factor: float,
    ns_kwargs: dict,
) -> str:
    """Create XP/leveling system (VB-05)."""
    script = generate_xp_leveling_script(
        max_level=max_level,
        base_xp_per_level=base_xp_per_level,
        xp_scaling_factor=xp_scaling_factor,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Progression/XPLeveling.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_xp_leveling",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the XP system",
            "Attach LevelingManager to the player, XPRewardSource to enemies",
        ],
    }, indent=2)


async def _handle_game_currency_system(
    currency_types: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create currency system (VB-06)."""
    script = generate_currency_system_script(
        currency_types=currency_types,
        **ns_kwargs,
    )
    rel_path = "Assets/Scripts/Runtime/GameSystems/Progression/CurrencySystem.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_currency_system",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the currency system",
            "Use CurrencyManager.Instance for all currency transactions",
        ],
    }, indent=2)


async def _handle_game_damage_types(ns_kwargs: dict) -> str:
    """Create damage type system (VB-07)."""
    script = generate_damage_type_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/Combat/DamageTypes.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_damage_types",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the damage type system",
            "DamageTypeRegistry initializes with all brand-specific damage types",
        ],
    }, indent=2)


# ===========================================================================
# Compound tool: unity_content (Content & Progression Systems -- Phase 13)
# ===========================================================================


@mcp.tool()
async def unity_content(
    action: Literal[
        # Content Systems (content_templates.py)
        "create_inventory_system",      # GAME-02
        "create_dialogue_system",       # GAME-03
        "create_quest_system",          # GAME-04
        "create_loot_table",            # GAME-09
        "create_crafting_system",       # GAME-10
        "create_skill_tree",            # GAME-11
        "create_dps_calculator",        # GAME-12
        "create_encounter_simulator",   # GAME-12
        "create_stat_curve_editor",     # GAME-12
        "create_shop_system",           # RPG-01
        "create_journal_system",        # RPG-05
        # Equipment (equipment_templates.py)
        "create_equipment_attachment",  # EQUIP-06
    ],
    name: str = "default",
    # Inventory params (GAME-02)
    grid_width: int = 8,
    grid_height: int = 5,
    equipment_slots: list[str] | None = None,
    # Skill tree params (GAME-11)
    hero_paths: list[str] | None = None,
    # DPS calculator params (GAME-12)
    brands: list[str] | None = None,
    # Namespace (shared)
    namespace: str = "",
) -> str:
    """Content and progression systems -- inventory, dialogue, quests, loot, crafting,
    skill tree, balancing tools, shop, journal, and equipment attachment.

    This compound tool generates C# runtime scripts and Editor tools for
    content/progression systems. Runtime scripts go to
    Assets/Scripts/Runtime/ContentSystems/; editor tools go to
    Assets/Scripts/Editor/BalancingTools/.

    Content Systems actions (content_templates.py):
    - create_inventory_system: Grid inventory + equipment slots + UI (GAME-02)
    - create_dialogue_system: Branching dialogue with YarnSpinner-compatible nodes (GAME-03)
    - create_quest_system: Quest state machine + objective tracker + log UI (GAME-04)
    - create_loot_table: Weighted loot tables with brand affinity (GAME-09)
    - create_crafting_system: Recipe SO + crafting station system (GAME-10)
    - create_skill_tree: Skill nodes + hero path tree (GAME-11)
    - create_dps_calculator: EditorWindow DPS calculator (GAME-12, EDITOR)
    - create_encounter_simulator: EditorWindow Monte Carlo encounter sim (GAME-12, EDITOR)
    - create_stat_curve_editor: EditorWindow stat curve editor (GAME-12, EDITOR)
    - create_shop_system: Merchant + shop UI with stat comparison (RPG-01)
    - create_journal_system: Codex with Lore/Bestiary/Items (RPG-05)

    Equipment actions (equipment_templates.py):
    - create_equipment_attachment: Bone rebinding + weapon sheathing (EQUIP-06)

    Args:
        action: The content system action to perform.
        name: Name for the generated system (used in file paths).
        grid_width: Inventory grid width (GAME-02, default 8).
        grid_height: Inventory grid height (GAME-02, default 5).
        equipment_slots: Equipment slot names (GAME-02).
        hero_paths: Hero path names for skill tree layout (GAME-11).
        brands: Brand names for DPS calculator (GAME-12).
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_inventory_system":
            return await _handle_content_inventory(
                grid_width, grid_height, equipment_slots, ns_kwargs,
            )
        elif action == "create_dialogue_system":
            return await _handle_content_dialogue(ns_kwargs)
        elif action == "create_quest_system":
            return await _handle_content_quest(ns_kwargs)
        elif action == "create_loot_table":
            return await _handle_content_loot_table(ns_kwargs)
        elif action == "create_crafting_system":
            return await _handle_content_crafting(ns_kwargs)
        elif action == "create_skill_tree":
            return await _handle_content_skill_tree(hero_paths, ns_kwargs)
        elif action == "create_dps_calculator":
            return await _handle_content_dps_calculator(brands, ns_kwargs)
        elif action == "create_encounter_simulator":
            return await _handle_content_encounter_simulator(ns_kwargs)
        elif action == "create_stat_curve_editor":
            return await _handle_content_stat_curve_editor(ns_kwargs)
        elif action == "create_shop_system":
            return await _handle_content_shop(ns_kwargs)
        elif action == "create_journal_system":
            return await _handle_content_journal(ns_kwargs)
        elif action == "create_equipment_attachment":
            return await _handle_content_equipment_attachment(ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_content action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Content action handlers
# ---------------------------------------------------------------------------


async def _handle_content_inventory(
    grid_width: int, grid_height: int,
    equipment_slots: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create inventory system (GAME-02)."""
    item_so, inventory_cs, uxml, uss = generate_inventory_system_script(
        grid_width=grid_width,
        grid_height=grid_height,
        equipment_slots=equipment_slots,
        **ns_kwargs,
    )
    base = "Assets/Scripts/Runtime/ContentSystems/Inventory"
    paths = []
    paths.append(_write_to_unity(item_so, f"{base}/VB_ItemData.cs"))
    paths.append(_write_to_unity(inventory_cs, f"{base}/VB_InventorySystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Inventory.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Inventory.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_inventory_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the inventory system",
            "Attach VB_InventorySystem to the player",
        ],
    }, indent=2)


async def _handle_content_dialogue(ns_kwargs: dict) -> str:
    """Create dialogue system (GAME-03)."""
    data_cs, system_cs, uxml, uss = generate_dialogue_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Dialogue"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_DialogueData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_DialogueSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Dialogue.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Dialogue.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_dialogue_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the dialogue system",
            "Create DialogueData ScriptableObject assets for conversations",
        ],
    }, indent=2)


async def _handle_content_quest(ns_kwargs: dict) -> str:
    """Create quest system (GAME-04)."""
    data_cs, system_cs, uxml, uss = generate_quest_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Quests"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_QuestData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_QuestSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/QuestLog.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/QuestLog.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_quest_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the quest system",
            "Create QuestDefinition ScriptableObject assets for quests",
        ],
    }, indent=2)


async def _handle_content_loot_table(ns_kwargs: dict) -> str:
    """Create loot table system (GAME-09)."""
    script = generate_loot_table_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Runtime/ContentSystems/Loot/VB_LootTable.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_loot_table",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the loot table system",
            "Create LootTable ScriptableObject assets for drop tables",
        ],
    }, indent=2)


async def _handle_content_crafting(ns_kwargs: dict) -> str:
    """Create crafting system (GAME-10)."""
    recipe_cs, crafting_cs = generate_crafting_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Crafting"
    paths = []
    paths.append(_write_to_unity(recipe_cs, f"{base}/VB_CraftingRecipe.cs"))
    paths.append(_write_to_unity(crafting_cs, f"{base}/VB_CraftingSystem.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_crafting_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the crafting system",
            "Create CraftingRecipe ScriptableObject assets for recipes",
        ],
    }, indent=2)


async def _handle_content_skill_tree(
    hero_paths: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create skill tree system (GAME-11)."""
    node_cs, tree_cs = generate_skill_tree_script(
        hero_paths=hero_paths,
        **ns_kwargs,
    )
    base = "Assets/Scripts/Runtime/ContentSystems/SkillTree"
    paths = []
    paths.append(_write_to_unity(node_cs, f"{base}/VB_SkillNode.cs"))
    paths.append(_write_to_unity(tree_cs, f"{base}/VB_SkillTree.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_skill_tree",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the skill tree system",
            "Create SkillNode ScriptableObject assets for skill definitions",
        ],
    }, indent=2)


async def _handle_content_dps_calculator(
    brands: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create DPS calculator editor tool (GAME-12)."""
    script = generate_dps_calculator_script(brands=brands, **ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_DPSCalculator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_dps_calculator",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the DPS calculator",
            "Open via menu: VeilBreakers > Balancing > DPS Calculator",
        ],
    }, indent=2)


async def _handle_content_encounter_simulator(ns_kwargs: dict) -> str:
    """Create encounter simulator editor tool (GAME-12)."""
    script = generate_encounter_simulator_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_EncounterSimulator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_encounter_simulator",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the encounter simulator",
            "Open via menu: VeilBreakers > Balancing > Encounter Simulator",
        ],
    }, indent=2)


async def _handle_content_stat_curve_editor(ns_kwargs: dict) -> str:
    """Create stat curve editor tool (GAME-12)."""
    script = generate_stat_curve_editor_script(**ns_kwargs)
    rel_path = "Assets/Scripts/Editor/BalancingTools/VB_StatCurveEditor.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_stat_curve_editor",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the stat curve editor",
            "Open via menu: VeilBreakers > Balancing > Stat Curve Editor",
        ],
    }, indent=2)


async def _handle_content_shop(ns_kwargs: dict) -> str:
    """Create shop/merchant system (RPG-01)."""
    merchant_cs, shop_cs, uxml, uss = generate_shop_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Shop"
    paths = []
    paths.append(_write_to_unity(merchant_cs, f"{base}/VB_MerchantData.cs"))
    paths.append(_write_to_unity(shop_cs, f"{base}/VB_ShopSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Shop.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Shop.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_shop_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the shop system",
            "Create MerchantData ScriptableObject assets for merchants",
        ],
    }, indent=2)


async def _handle_content_journal(ns_kwargs: dict) -> str:
    """Create journal/codex system (RPG-05)."""
    data_cs, system_cs, uxml, uss = generate_journal_system_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Journal"
    paths = []
    paths.append(_write_to_unity(data_cs, f"{base}/VB_JournalData.cs"))
    paths.append(_write_to_unity(system_cs, f"{base}/VB_JournalSystem.cs"))
    paths.append(_write_to_unity(uxml, "Assets/UI/Journal.uxml"))
    paths.append(_write_to_unity(uss, "Assets/UI/Journal.uss"))
    return json.dumps({
        "status": "success",
        "action": "create_journal_system",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the journal system",
            "Create JournalEntry ScriptableObject assets for lore and bestiary entries",
        ],
    }, indent=2)


async def _handle_content_equipment_attachment(ns_kwargs: dict) -> str:
    """Create equipment attachment system (EQUIP-06)."""
    attachment_cs, weapon_sheath_cs = generate_equipment_attachment_script(**ns_kwargs)
    base = "Assets/Scripts/Runtime/ContentSystems/Equipment"
    paths = []
    paths.append(_write_to_unity(attachment_cs, f"{base}/VB_EquipmentAttachment.cs"))
    paths.append(_write_to_unity(weapon_sheath_cs, f"{base}/VB_WeaponSheath.cs"))
    return json.dumps({
        "status": "success",
        "action": "create_equipment_attachment",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the equipment system",
            "Attach VB_EquipmentAttachment to the character root",
            "Attach VB_WeaponSheath to weapon objects with Animation Rigging",
        ],
    }, indent=2)


# ===========================================================================
# Compound tool: unity_camera (Camera, Cinematics & Animation -- Phase 14)
# ===========================================================================


@mcp.tool()
async def unity_camera(
    action: Literal[
        "create_virtual_camera",      # CAM-01
        "create_state_driven_camera",  # CAM-01
        "create_camera_shake",        # CAM-04
        "configure_blend",            # CAM-04
        "create_timeline",            # CAM-02
        "create_cutscene",            # CAM-03
        "edit_animation_clip",        # ANIMA-01
        "modify_animator",            # ANIMA-02
        "create_avatar_mask",         # ANIMA-03
        "setup_video_player",         # MEDIA-01
    ],
    name: str = "default",
    # camera params
    camera_type: str = "orbital",
    follow_target: str = "",
    look_at_target: str = "",
    priority: int = 10,
    radius: float = 5.0,
    target_offset: list[float] | None = None,
    damping: list[float] | None = None,
    # state-driven params
    states: list[dict] | None = None,
    # shake params
    impulse_force: float = 0.5,
    impulse_duration: float = 0.2,
    add_listener: bool = True,
    # blend params
    default_blend_time: float = 2.0,
    blend_style: str = "EaseInOut",
    custom_blends: list[dict] | None = None,
    # timeline params
    tracks: list[dict] | None = None,
    output_path: str = "Assets/Timelines",
    # cutscene params
    timeline_path: str = "",
    wrap_mode: str = "None",
    play_on_awake: bool = False,
    # animation clip params
    clip_name: str = "CustomClip",
    curves: list[dict] | None = None,
    # animator params
    controller_path: str = "",
    states_to_add: list[str] | None = None,
    transitions: list[dict] | None = None,
    parameters: list[dict] | None = None,
    sub_state_machines: list[str] | None = None,
    # avatar mask params
    mask_name: str = "CustomMask",
    body_parts: dict | None = None,
    transform_paths: list[str] | None = None,
    # video params
    video_source: str = "clip",
    video_path: str = "",
    render_texture_width: int = 1920,
    render_texture_height: int = 1080,
    loop: bool = True,
    # common
    namespace: str = "",
) -> str:
    """Camera, cinematics, and animation tools -- Cinemachine 3.x virtual cameras,
    state-driven cameras, camera shake, blend profiles, Timeline, cutscenes,
    animation clip editing, animator modification, avatar masks, video player.

    Camera actions (camera_templates.py):
    - create_virtual_camera: Cinemachine 3.x camera with orbital/follow/dolly body (CAM-01)
    - create_state_driven_camera: State-driven camera switching by animator state (CAM-01)
    - create_camera_shake: Cinemachine impulse shake system (CAM-04)
    - configure_blend: Camera blend profile configuration (CAM-04)

    Timeline/Cutscene actions:
    - create_timeline: Timeline asset with configurable tracks (CAM-02)
    - create_cutscene: Cutscene setup with PlayableDirector (CAM-03)

    Animation actions:
    - edit_animation_clip: Create/modify animation clips via AnimationUtility (ANIMA-01)
    - modify_animator: Modify animator controller states/transitions/parameters (ANIMA-02)
    - create_avatar_mask: Create avatar mask for animation layers (ANIMA-03)

    Media actions:
    - setup_video_player: Video player with render texture or camera overlay (MEDIA-01)

    Args:
        action: The camera/animation action to perform.
        name: Name for the generated system (used in file paths).
        camera_type: Virtual camera body type (orbital/follow/dolly).
        follow_target: Transform path for follow target.
        look_at_target: Transform path for look-at target.
        priority: Camera priority (higher = more important).
        radius: Orbital camera radius.
        target_offset: Target offset [x, y, z].
        damping: Damping values [x, y, z].
        states: State-driven camera state definitions.
        impulse_force: Camera shake impulse force.
        impulse_duration: Camera shake impulse duration.
        add_listener: Whether to add impulse listener.
        default_blend_time: Default camera blend time in seconds.
        blend_style: Blend curve style (EaseInOut/Cut/Linear).
        custom_blends: Custom per-camera-pair blend overrides.
        tracks: Timeline track definitions.
        output_path: Output directory for timeline/animation assets.
        timeline_path: Path to existing timeline asset for cutscene.
        wrap_mode: Cutscene wrap mode (None/Loop/Hold).
        play_on_awake: Whether cutscene plays on awake.
        clip_name: Animation clip name.
        curves: Animation curve definitions.
        controller_path: Path to existing animator controller.
        states_to_add: States to add to animator controller.
        transitions: Animator transitions to add.
        parameters: Animator parameters to add.
        sub_state_machines: Sub-state machines to add.
        mask_name: Avatar mask name.
        body_parts: Body part enable/disable map.
        transform_paths: Transform paths for avatar mask.
        video_source: Video source type (clip/url).
        video_path: Path to video clip or URL.
        render_texture_width: Render texture width.
        render_texture_height: Render texture height.
        loop: Whether video loops.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_virtual_camera":
            return await _handle_camera_virtual(
                name, camera_type, follow_target, look_at_target,
                priority, radius, target_offset, damping, ns_kwargs,
            )
        elif action == "create_state_driven_camera":
            return await _handle_camera_state_driven(name, states, ns_kwargs)
        elif action == "create_camera_shake":
            return await _handle_camera_shake(
                impulse_force, impulse_duration, add_listener, ns_kwargs,
            )
        elif action == "configure_blend":
            return await _handle_camera_blend(
                default_blend_time, blend_style, custom_blends, ns_kwargs,
            )
        elif action == "create_timeline":
            return await _handle_camera_timeline(name, tracks, output_path, ns_kwargs)
        elif action == "create_cutscene":
            return await _handle_camera_cutscene(
                name, timeline_path, wrap_mode, play_on_awake, ns_kwargs,
            )
        elif action == "edit_animation_clip":
            return await _handle_camera_animation_clip(
                clip_name, curves, output_path, ns_kwargs,
            )
        elif action == "modify_animator":
            return await _handle_camera_animator_modifier(
                controller_path, states_to_add, transitions,
                parameters, sub_state_machines, ns_kwargs,
            )
        elif action == "create_avatar_mask":
            return await _handle_camera_avatar_mask(
                mask_name, body_parts, transform_paths, output_path, ns_kwargs,
            )
        elif action == "setup_video_player":
            return await _handle_camera_video_player(
                video_source, video_path, render_texture_width,
                render_texture_height, loop, play_on_awake, ns_kwargs,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_camera action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# Camera action handlers
# ---------------------------------------------------------------------------


async def _handle_camera_virtual(
    name: str, camera_type: str, follow_target: str, look_at_target: str,
    priority: int, radius: float, target_offset: list[float] | None,
    damping: list[float] | None, ns_kwargs: dict,
) -> str:
    """Create Cinemachine 3.x virtual camera (CAM-01)."""
    script = generate_cinemachine_setup_script(
        camera_type=camera_type,
        follow_target=follow_target,
        look_at_target=look_at_target,
        priority=priority,
        radius=radius,
        target_offset=target_offset,
        damping=damping,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_CinemachineSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_virtual_camera",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the camera setup",
            f"Execute menu item: VeilBreakers > Camera > Setup {name}",
        ],
    }, indent=2)


async def _handle_camera_state_driven(
    name: str, states: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create state-driven camera (CAM-01)."""
    script = generate_state_driven_camera_script(
        camera_name=f"VB_{name}_StateDrivenCamera",
        states=states,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_StateDrivenCamera.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_state_driven_camera",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the state-driven camera",
            f"Execute menu item: VeilBreakers > Camera > Setup {name} State Camera",
        ],
    }, indent=2)


async def _handle_camera_shake(
    impulse_force: float, impulse_duration: float,
    add_listener: bool, ns_kwargs: dict,
) -> str:
    """Create camera shake system (CAM-04)."""
    script = generate_camera_shake_script(
        impulse_force=impulse_force,
        impulse_duration=impulse_duration,
        add_listener=add_listener,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/CameraShakeSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_camera_shake",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the camera shake system",
            "Execute menu item: VeilBreakers > Camera > Setup Shake",
        ],
    }, indent=2)


async def _handle_camera_blend(
    default_blend_time: float, blend_style: str,
    custom_blends: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Configure camera blend profile (CAM-04)."""
    script = generate_camera_blend_script(
        default_blend_time=default_blend_time,
        blend_style=blend_style,
        custom_blends=custom_blends,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/CameraBlendSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "configure_blend",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the blend configuration",
            "Execute menu item: VeilBreakers > Camera > Configure Blends",
        ],
    }, indent=2)


async def _handle_camera_timeline(
    name: str, tracks: list[dict] | None, output_path: str, ns_kwargs: dict,
) -> str:
    """Create timeline asset (CAM-02)."""
    script = generate_timeline_setup_script(
        timeline_name=f"VB_{name}_Timeline",
        tracks=tracks,
        output_path=output_path,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_TimelineSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_timeline",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the timeline setup",
            f"Execute menu item: VeilBreakers > Camera > Create {name} Timeline",
        ],
    }, indent=2)


async def _handle_camera_cutscene(
    name: str, timeline_path: str, wrap_mode: str,
    play_on_awake: bool, ns_kwargs: dict,
) -> str:
    """Create cutscene setup (CAM-03)."""
    script = generate_cutscene_setup_script(
        cutscene_name=f"VB_{name}_Cutscene",
        timeline_path=timeline_path or f"Assets/Timelines/VB_{name}_Timeline.playable",
        wrap_mode=wrap_mode,
        play_on_awake=play_on_awake,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/Camera/{name}_CutsceneSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_cutscene",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the cutscene setup",
            f"Execute menu item: VeilBreakers > Camera > Setup {name} Cutscene",
        ],
    }, indent=2)


async def _handle_camera_animation_clip(
    clip_name: str, curves: list[dict] | None,
    output_path: str, ns_kwargs: dict,
) -> str:
    """Create/edit animation clip (ANIMA-01)."""
    script = generate_animation_clip_editor_script(
        clip_name=clip_name,
        curves=curves,
        output_path=output_path,
        **ns_kwargs,
    )
    safe_name = clip_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/Camera/{safe_name}_ClipEditor.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "edit_animation_clip",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the clip editor",
            f"Execute menu item: VeilBreakers > Animation > Create {clip_name}",
        ],
    }, indent=2)


async def _handle_camera_animator_modifier(
    controller_path: str, states_to_add: list[str] | None,
    transitions: list[dict] | None, parameters: list[dict] | None,
    sub_state_machines: list[str] | None, ns_kwargs: dict,
) -> str:
    """Modify animator controller (ANIMA-02)."""
    script = generate_animator_modifier_script(
        controller_path=controller_path or "Assets/Animations/VB_Controller.controller",
        states_to_add=states_to_add,
        transitions=transitions,
        parameters=parameters,
        sub_state_machines=sub_state_machines,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/AnimatorModifier.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "modify_animator",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the animator modifier",
            "Execute menu item: VeilBreakers > Animation > Modify Controller",
        ],
    }, indent=2)


async def _handle_camera_avatar_mask(
    mask_name: str, body_parts: dict | None,
    transform_paths: list[str] | None, output_path: str, ns_kwargs: dict,
) -> str:
    """Create avatar mask (ANIMA-03)."""
    script = generate_avatar_mask_script(
        mask_name=mask_name,
        body_parts=body_parts,
        transform_paths=transform_paths,
        output_path=output_path,
        **ns_kwargs,
    )
    safe_name = mask_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/Camera/{safe_name}_MaskSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_avatar_mask",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the mask setup",
            f"Execute menu item: VeilBreakers > Animation > Create {mask_name}",
        ],
    }, indent=2)


async def _handle_camera_video_player(
    video_source: str, video_path: str, render_texture_width: int,
    render_texture_height: int, loop: bool, play_on_awake: bool,
    ns_kwargs: dict,
) -> str:
    """Setup video player (MEDIA-01)."""
    script = generate_video_player_script(
        video_source=video_source,
        video_path=video_path,
        render_texture_width=render_texture_width,
        render_texture_height=render_texture_height,
        loop=loop,
        play_on_awake=play_on_awake,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/Camera/VideoPlayerSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_video_player",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the video player setup",
            "Execute menu item: VeilBreakers > Media > Setup Video Player",
        ],
    }, indent=2)


# ===========================================================================
# Compound tool: unity_world (Scene & World Systems -- Phase 14)
# ===========================================================================


@mcp.tool()
async def unity_world(
    action: Literal[
        "create_scene",               # SCNE-01
        "create_transition_system",    # SCNE-02
        "setup_probes",               # SCNE-03
        "setup_occlusion",            # SCNE-04
        "setup_environment",          # SCNE-05
        "paint_terrain_detail",       # SCNE-06
        "create_tilemap",             # TWO-01
        "setup_2d_physics",           # TWO-02
        "apply_time_of_day",          # WORLD-08
        "create_fast_travel",         # RPG-02
        "create_puzzle",              # RPG-04
        "create_trap",                # RPG-06
        "create_spatial_loot",        # RPG-07
        "create_weather",             # RPG-09
        "create_day_night",           # RPG-10
        "create_npc_placement",       # RPG-11
        "create_dungeon_lighting",    # RPG-12
        "create_terrain_blend",       # RPG-13
    ],
    name: str = "default",
    # scene params
    scene_name: str = "",
    scene_setup: str = "DefaultGameObjects",
    loading_mode: str = "single",
    build_index: int = -1,
    # transition params
    fade_duration: float = 0.5,
    show_loading_screen: bool = True,
    # probe params
    reflection_probe_count: int = 4,
    reflection_resolution: int = 256,
    probe_box_size: list[float] | None = None,
    light_probe_grid_spacing: float = 2.0,
    light_probe_grid_size: list[int] | None = None,
    # occlusion params
    smallest_occluder: float = 5.0,
    smallest_hole: float = 0.25,
    backface_threshold: float = 100.0,
    # environment params
    skybox_shader: str = "Skybox/Procedural",
    ambient_mode: str = "Skybox",
    default_reflection_mode: str = "Skybox",
    enable_gi: bool = True,
    # terrain detail params
    detail_prototypes: list[dict] | None = None,
    paint_density: int = 8,
    # tilemap params
    grid_cell_size: list[float] | None = None,
    tile_entries: list[dict] | None = None,
    rule_tile_name: str = "",
    rule_tile_rules: list[dict] | None = None,
    # 2d physics params
    gravity: list[float] | None = None,
    collider_type: str = "box",
    body_type: str = "Dynamic",
    joint_type: str = "",
    joint_params: dict | None = None,
    # time of day params
    preset_name: str = "noon",
    custom_overrides: dict | None = None,
    apply_fog: bool = True,
    # fast travel params
    waypoint_prefab_path: str = "",
    teleport_fade_duration: float = 0.5,
    save_key: str = "discoveredWaypoints",
    # puzzle params
    puzzle_types: list[str] | None = None,
    # trap params
    trap_types: list[str] | None = None,
    base_damage: float = 25.0,
    cooldown: float = 3.0,
    # spatial loot params
    chest_prefab_path: str = "",
    loot_table_so_path: str = "",
    room_loot_density: float = 0.3,
    # weather params
    weather_states: list[str] | None = None,
    transition_duration: float = 3.0,
    default_state: str = "Clear",
    # day/night params
    day_duration_minutes: float = 10.0,
    start_hour: float = 8.0,
    time_presets: list[str] | None = None,
    # npc placement params
    npc_roles: list[str] | None = None,
    # dungeon lighting params
    torch_spacing: float = 5.0,
    torch_light_range: float = 8.0,
    torch_color: list[float] | None = None,
    fog_density: float = 0.03,
    fog_color: list[float] | None = None,
    # terrain blend params
    blend_radius: float = 2.0,
    decal_material_path: str = "",
    depression_depth: float = 0.1,
    vertex_color_falloff: float = 1.5,
    # common
    namespace: str = "",
) -> str:
    """Scene and world systems -- scene creation, transitions, probes, occlusion,
    environment, terrain detail, tilemaps, 2D physics, time-of-day, fast travel,
    puzzles, traps, spatial loot, weather, day/night cycle, NPC placement,
    dungeon lighting, terrain-building blending.

    Scene Management actions (world_templates.py):
    - create_scene: Create new scene with default objects (SCNE-01)
    - create_transition_system: Scene transition manager with fade/loading (SCNE-02)
    - setup_probes: Reflection + light probe grid setup (SCNE-03)
    - setup_occlusion: Occlusion culling configuration (SCNE-04)
    - setup_environment: Skybox, ambient, GI configuration (SCNE-05)
    - paint_terrain_detail: Terrain detail prototype painting (SCNE-06)

    2D actions:
    - create_tilemap: Tilemap grid with rule tiles (TWO-01)
    - setup_2d_physics: 2D physics, colliders, joints (TWO-02)

    World actions:
    - apply_time_of_day: Apply time-of-day lighting preset (WORLD-08)

    RPG World System actions:
    - create_fast_travel: Waypoint-based fast travel system (RPG-02)
    - create_puzzle: Environmental puzzle mechanics (RPG-04)
    - create_trap: Dungeon trap system (RPG-06)
    - create_spatial_loot: Room-based loot placement (RPG-07)
    - create_weather: Weather state machine with particle transitions (RPG-09)
    - create_day_night: Day/night cycle with lighting presets (RPG-10)
    - create_npc_placement: NPC role placement via ScriptableObject (RPG-11)
    - create_dungeon_lighting: Torch sconce + fog dungeon lighting (RPG-12)
    - create_terrain_blend: Terrain-building blending system (RPG-13)

    Args:
        action: The world system action to perform.
        name: Name for the generated system (used in file paths).
        scene_name: Name of the scene to create.
        scene_setup: Scene setup type (DefaultGameObjects/EmptyScene).
        loading_mode: Scene loading mode (single/additive).
        build_index: Build index for scene (-1 = auto).
        fade_duration: Transition fade duration in seconds.
        show_loading_screen: Show loading screen during transition.
        reflection_probe_count: Number of reflection probes.
        reflection_resolution: Reflection probe resolution.
        probe_box_size: Reflection probe box size [x, y, z].
        light_probe_grid_spacing: Light probe grid spacing.
        light_probe_grid_size: Light probe grid dimensions [x, y, z].
        smallest_occluder: Occlusion smallest occluder size.
        smallest_hole: Occlusion smallest hole size.
        backface_threshold: Occlusion backface threshold.
        skybox_shader: Skybox shader path.
        ambient_mode: Ambient lighting mode.
        default_reflection_mode: Default reflection mode.
        enable_gi: Enable global illumination.
        detail_prototypes: Terrain detail prototype definitions.
        paint_density: Terrain detail paint density.
        grid_cell_size: Tilemap grid cell size [x, y].
        tile_entries: Tile definitions for tilemap.
        rule_tile_name: Name for rule tile asset.
        rule_tile_rules: Rule tile rule definitions.
        gravity: 2D gravity vector [x, y].
        collider_type: 2D collider type (box/circle/polygon/edge).
        body_type: 2D rigidbody type (Dynamic/Kinematic/Static).
        joint_type: 2D joint type (hinge/spring/distance/fixed).
        joint_params: 2D joint parameters.
        preset_name: Time-of-day preset name.
        custom_overrides: Custom time-of-day overrides.
        apply_fog: Whether to apply fog settings.
        waypoint_prefab_path: Path to waypoint prefab.
        teleport_fade_duration: Teleport fade duration.
        save_key: PlayerPrefs key for discovered waypoints.
        puzzle_types: Puzzle type names to generate.
        trap_types: Trap type names to generate.
        base_damage: Base trap damage.
        cooldown: Trap cooldown in seconds.
        chest_prefab_path: Path to chest prefab.
        loot_table_so_path: Path to loot table ScriptableObjects.
        room_loot_density: Room loot placement density.
        weather_states: Weather state names.
        transition_duration: Weather transition duration.
        default_state: Default weather state name.
        day_duration_minutes: Full day cycle duration in minutes.
        start_hour: Starting hour of day (0-24).
        time_presets: Time preset names for day/night cycle.
        npc_roles: NPC role names for placement.
        torch_spacing: Spacing between dungeon torches.
        torch_light_range: Torch light range.
        torch_color: Torch light color [r, g, b].
        fog_density: Dungeon fog density.
        fog_color: Dungeon fog color [r, g, b].
        blend_radius: Terrain-building blend radius.
        decal_material_path: Path to blend decal material.
        depression_depth: Terrain depression depth at building edge.
        vertex_color_falloff: Vertex color blend falloff.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_scene":
            return await _handle_world_create_scene(
                scene_name or name, scene_setup, loading_mode, build_index, ns_kwargs,
            )
        elif action == "create_transition_system":
            return await _handle_world_transition(
                name, fade_duration, show_loading_screen, ns_kwargs,
            )
        elif action == "setup_probes":
            return await _handle_world_probes(
                name, reflection_probe_count, reflection_resolution,
                probe_box_size, light_probe_grid_spacing, light_probe_grid_size,
                ns_kwargs,
            )
        elif action == "setup_occlusion":
            return await _handle_world_occlusion(
                name, smallest_occluder, smallest_hole, backface_threshold, ns_kwargs,
            )
        elif action == "setup_environment":
            return await _handle_world_environment(
                name, skybox_shader, ambient_mode, default_reflection_mode,
                enable_gi, ns_kwargs,
            )
        elif action == "paint_terrain_detail":
            return await _handle_world_terrain_detail(
                name, detail_prototypes, paint_density, ns_kwargs,
            )
        elif action == "create_tilemap":
            return await _handle_world_tilemap(
                name, grid_cell_size, tile_entries, rule_tile_name,
                rule_tile_rules, ns_kwargs,
            )
        elif action == "setup_2d_physics":
            return await _handle_world_2d_physics(
                name, gravity, collider_type, body_type, joint_type,
                joint_params, ns_kwargs,
            )
        elif action == "apply_time_of_day":
            return await _handle_world_time_of_day(
                name, preset_name, custom_overrides, apply_fog, ns_kwargs,
            )
        elif action == "create_fast_travel":
            return await _handle_world_fast_travel(
                name, waypoint_prefab_path, teleport_fade_duration, save_key,
                ns_kwargs,
            )
        elif action == "create_puzzle":
            return await _handle_world_puzzle(name, puzzle_types, ns_kwargs)
        elif action == "create_trap":
            return await _handle_world_trap(
                name, trap_types, base_damage, cooldown, ns_kwargs,
            )
        elif action == "create_spatial_loot":
            return await _handle_world_spatial_loot(
                name, chest_prefab_path, loot_table_so_path,
                room_loot_density, ns_kwargs,
            )
        elif action == "create_weather":
            return await _handle_world_weather(
                name, weather_states, transition_duration, default_state,
                ns_kwargs,
            )
        elif action == "create_day_night":
            return await _handle_world_day_night(
                name, day_duration_minutes, start_hour, time_presets, ns_kwargs,
            )
        elif action == "create_npc_placement":
            return await _handle_world_npc_placement(name, npc_roles, ns_kwargs)
        elif action == "create_dungeon_lighting":
            return await _handle_world_dungeon_lighting(
                name, torch_spacing, torch_light_range, torch_color,
                fog_density, fog_color, ns_kwargs,
            )
        elif action == "create_terrain_blend":
            return await _handle_world_terrain_blend(
                name, blend_radius, decal_material_path, depression_depth,
                vertex_color_falloff, ns_kwargs,
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_world action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# World action handlers
# ---------------------------------------------------------------------------


async def _handle_world_create_scene(
    scene_name: str, scene_setup: str, loading_mode: str,
    build_index: int, ns_kwargs: dict,
) -> str:
    """Create new scene (SCNE-01)."""
    script = generate_scene_creation_script(
        scene_name=scene_name,
        scene_setup=scene_setup,
        loading_mode=loading_mode,
        build_index=build_index,
        **ns_kwargs,
    )
    safe_name = scene_name.replace(" ", "_")
    rel_path = f"Assets/Editor/Generated/World/{safe_name}_SceneCreator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_scene",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the scene creator",
            f"Execute menu item: VeilBreakers > World > Create {scene_name}",
        ],
    }, indent=2)


async def _handle_world_transition(
    name: str, fade_duration: float, show_loading_screen: bool, ns_kwargs: dict,
) -> str:
    """Create scene transition system (SCNE-02)."""
    editor_cs, runtime_cs = generate_scene_transition_script(
        fade_duration=fade_duration,
        show_loading_screen=show_loading_screen,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TransitionSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_SceneTransition.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_transition_system",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the transition system",
            "Execute menu item: VeilBreakers > World > Setup Transitions",
        ],
    }, indent=2)


async def _handle_world_probes(
    name: str, reflection_probe_count: int, reflection_resolution: int,
    probe_box_size: list[float] | None, light_probe_grid_spacing: float,
    light_probe_grid_size: list[int] | None, ns_kwargs: dict,
) -> str:
    """Setup reflection + light probes (SCNE-03)."""
    script = generate_probe_setup_script(
        reflection_probe_count=reflection_probe_count,
        reflection_resolution=reflection_resolution,
        probe_box_size=probe_box_size,
        light_probe_grid_spacing=light_probe_grid_spacing,
        light_probe_grid_size=light_probe_grid_size,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_ProbeSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_probes",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the probe setup",
            "Execute menu item: VeilBreakers > World > Setup Probes",
        ],
    }, indent=2)


async def _handle_world_occlusion(
    name: str, smallest_occluder: float, smallest_hole: float,
    backface_threshold: float, ns_kwargs: dict,
) -> str:
    """Setup occlusion culling (SCNE-04)."""
    script = generate_occlusion_setup_script(
        smallest_occluder=smallest_occluder,
        smallest_hole=smallest_hole,
        backface_threshold=backface_threshold,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_OcclusionSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_occlusion",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile occlusion setup",
            "Execute menu item: VeilBreakers > World > Setup Occlusion",
        ],
    }, indent=2)


async def _handle_world_environment(
    name: str, skybox_shader: str, ambient_mode: str,
    default_reflection_mode: str, enable_gi: bool, ns_kwargs: dict,
) -> str:
    """Setup environment (skybox, ambient, GI) (SCNE-05)."""
    script = generate_environment_setup_script(
        skybox_shader=skybox_shader,
        ambient_mode=ambient_mode,
        default_reflection_mode=default_reflection_mode,
        enable_gi=enable_gi,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_EnvironmentSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_environment",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the environment setup",
            "Execute menu item: VeilBreakers > World > Setup Environment",
        ],
    }, indent=2)


async def _handle_world_terrain_detail(
    name: str, detail_prototypes: list[dict] | None, paint_density: int,
    ns_kwargs: dict,
) -> str:
    """Paint terrain detail prototypes (SCNE-06)."""
    script = generate_terrain_detail_script(
        detail_prototypes=detail_prototypes,
        paint_density=paint_density,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TerrainDetail.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "paint_terrain_detail",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the terrain detail painter",
            "Execute menu item: VeilBreakers > World > Paint Terrain Detail",
        ],
    }, indent=2)


async def _handle_world_tilemap(
    name: str, grid_cell_size: list[float] | None, tile_entries: list[dict] | None,
    rule_tile_name: str, rule_tile_rules: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create tilemap setup (TWO-01)."""
    script = generate_tilemap_setup_script(
        grid_cell_size=grid_cell_size,
        tile_entries=tile_entries,
        rule_tile_name=rule_tile_name,
        rule_tile_rules=rule_tile_rules,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TilemapSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_tilemap",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the tilemap setup",
            "Execute menu item: VeilBreakers > World > Create Tilemap",
        ],
    }, indent=2)


async def _handle_world_2d_physics(
    name: str, gravity: list[float] | None, collider_type: str,
    body_type: str, joint_type: str, joint_params: dict | None,
    ns_kwargs: dict,
) -> str:
    """Setup 2D physics (TWO-02)."""
    script = generate_2d_physics_script(
        gravity=gravity,
        collider_type=collider_type,
        body_type=body_type,
        joint_type=joint_type,
        joint_params=joint_params,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_2DPhysicsSetup.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_2d_physics",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile 2D physics setup",
            "Execute menu item: VeilBreakers > World > Setup 2D Physics",
        ],
    }, indent=2)


async def _handle_world_time_of_day(
    name: str, preset_name: str, custom_overrides: dict | None,
    apply_fog: bool, ns_kwargs: dict,
) -> str:
    """Apply time-of-day lighting preset (WORLD-08)."""
    script = generate_time_of_day_preset_script(
        preset_name=preset_name,
        custom_overrides=custom_overrides,
        apply_fog=apply_fog,
        **ns_kwargs,
    )
    rel_path = f"Assets/Editor/Generated/World/{name}_TimeOfDay.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "apply_time_of_day",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile time-of-day setup",
            f"Execute menu item: VeilBreakers > World > Apply {preset_name}",
        ],
    }, indent=2)


async def _handle_world_fast_travel(
    name: str, waypoint_prefab_path: str, teleport_fade_duration: float,
    save_key: str, ns_kwargs: dict,
) -> str:
    """Create fast travel system (RPG-02)."""
    editor_cs, runtime_cs = generate_fast_travel_script(
        waypoint_prefab_path=waypoint_prefab_path or "Prefabs/Waypoint",
        teleport_fade_duration=teleport_fade_duration,
        save_key=save_key,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_FastTravelSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_FastTravel.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_fast_travel",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the fast travel system",
            "Place waypoint triggers in the scene and assign discovery events",
        ],
    }, indent=2)


async def _handle_world_puzzle(
    name: str, puzzle_types: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create puzzle mechanics system (RPG-04)."""
    editor_cs, runtime_cs = generate_puzzle_mechanics_script(
        puzzle_types=puzzle_types,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_PuzzleSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_PuzzleMechanics.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_puzzle",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the puzzle system",
            "Place puzzle objects in dungeon rooms and configure trigger sequences",
        ],
    }, indent=2)


async def _handle_world_trap(
    name: str, trap_types: list[str] | None, base_damage: float,
    cooldown: float, ns_kwargs: dict,
) -> str:
    """Create trap system (RPG-06)."""
    editor_cs, runtime_cs = generate_trap_system_script(
        trap_types=trap_types,
        base_damage=base_damage,
        cooldown=cooldown,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TrapSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_TrapSystem.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_trap",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the trap system",
            "Place trap prefabs in dungeon corridors",
        ],
    }, indent=2)


async def _handle_world_spatial_loot(
    name: str, chest_prefab_path: str, loot_table_so_path: str,
    room_loot_density: float, ns_kwargs: dict,
) -> str:
    """Create spatial loot system (RPG-07)."""
    editor_cs, runtime_cs = generate_spatial_loot_script(
        chest_prefab_path=chest_prefab_path or "Prefabs/TreasureChest",
        loot_table_so_path=loot_table_so_path or "Data/LootTables",
        room_loot_density=room_loot_density,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_LootSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_SpatialLoot.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_spatial_loot",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the loot system",
            "Create LootTable ScriptableObjects for room-specific drops",
        ],
    }, indent=2)


async def _handle_world_weather(
    name: str, weather_states: list[str] | None, transition_duration: float,
    default_state: str, ns_kwargs: dict,
) -> str:
    """Create weather system (RPG-09)."""
    editor_cs, runtime_cs = generate_weather_system_script(
        weather_states=weather_states,
        transition_duration=transition_duration,
        default_state=default_state,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_WeatherSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_WeatherSystem.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_weather",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the weather system",
            "Assign ParticleSystem prefabs for rain/snow/fog states",
        ],
    }, indent=2)


async def _handle_world_day_night(
    name: str, day_duration_minutes: float, start_hour: float,
    time_presets: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create day/night cycle system (RPG-10)."""
    editor_cs, runtime_cs = generate_day_night_cycle_script(
        day_duration_minutes=day_duration_minutes,
        start_hour=start_hour,
        time_presets=time_presets,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_DayNightSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_DayNightCycle.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_day_night",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile the day/night cycle",
            "Assign directional light for sun rotation",
        ],
    }, indent=2)


async def _handle_world_npc_placement(
    name: str, npc_roles: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create NPC placement system (RPG-11)."""
    so_cs, runtime_cs, editor_cs = generate_npc_placement_script(
        npc_roles=npc_roles,
        **ns_kwargs,
    )
    paths = []
    paths.append(_write_to_unity(
        so_cs, f"Assets/ScriptableObjects/World/{name}_NPCPlacementData.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_NPCPlacement.cs",
    ))
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_NPCPlacementSetup.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_npc_placement",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the NPC placement system",
            "Create NPCPlacementData ScriptableObject assets for NPC positions and roles",
        ],
    }, indent=2)


async def _handle_world_dungeon_lighting(
    name: str, torch_spacing: float, torch_light_range: float,
    torch_color: list[float] | None, fog_density: float,
    fog_color: list[float] | None, ns_kwargs: dict,
) -> str:
    """Create dungeon lighting system (RPG-12)."""
    editor_cs, runtime_cs = generate_dungeon_lighting_script(
        torch_spacing=torch_spacing,
        torch_light_range=torch_light_range,
        torch_color=torch_color,
        fog_density=fog_density,
        fog_color=fog_color,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_DungeonLightingSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_DungeonLighting.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_dungeon_lighting",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile dungeon lighting",
            "Place torch sconce prefabs or run auto-placement from editor menu",
        ],
    }, indent=2)


async def _handle_world_terrain_blend(
    name: str, blend_radius: float, decal_material_path: str,
    depression_depth: float, vertex_color_falloff: float, ns_kwargs: dict,
) -> str:
    """Create terrain-building blending system (RPG-13)."""
    editor_cs, runtime_cs = generate_terrain_building_blend_script(
        blend_radius=blend_radius,
        decal_material_path=decal_material_path or "Materials/TerrainBlendDecal",
        depression_depth=depression_depth,
        vertex_color_falloff=vertex_color_falloff,
        **ns_kwargs,
    )
    editor_path = _write_to_unity(
        editor_cs, f"Assets/Editor/Generated/World/{name}_TerrainBlendSetup.cs",
    )
    runtime_path = _write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/WorldSystems/{name}_TerrainBlend.cs",
    )
    return json.dumps({
        "status": "success",
        "action": "create_terrain_blend",
        "paths": [editor_path, runtime_path],
        "next_steps": [
            "Call unity_editor action='recompile' to compile terrain blending",
            "Select buildings and run blend from VeilBreakers > World > Blend Terrain",
        ],
    }, indent=2)


# ===========================================================================
# Compound tool: unity_ux (Game UX & HUD Elements -- Phase 15)
# ===========================================================================


@mcp.tool()
async def unity_ux(
    action: Literal[
        "create_minimap",              # UIX-01
        "create_damage_numbers",       # UIX-03
        "create_interaction_prompts",  # UIX-04
        "create_primetween_sequence",  # SHDR-04
        "create_tmp_font_asset",       # PIPE-10
        "setup_tmp_components",        # PIPE-10
        "create_tutorial_system",      # UIX-02
        "create_accessibility",        # ACC-01
        "create_character_select",     # VB-09
        "create_world_map",            # RPG-08
        "create_rarity_vfx",           # EQUIP-07
        "create_corruption_vfx",       # EQUIP-08
    ],
    name: str = "default",
    # minimap params
    render_texture_size: int = 256,
    zoom: float = 50.0,
    follow_target: str = "Player",
    culling_layers: list[str] | None = None,
    compass_enabled: bool = True,
    marker_types: list[str] | None = None,
    update_interval: int = 3,
    # damage numbers params
    pool_size: int = 20,
    float_height: float = 80.0,
    duration: float = 0.8,
    crit_scale: float = 1.5,
    # interaction prompts params
    prompt_text: str = "Interact",
    trigger_radius: float = 2.5,
    fade_duration: float = 0.3,
    # primetween params
    sequence_type: str = "panel_entrance",
    # TMP font asset params
    font_path: str = "Assets/Fonts/Cinzel-Regular.ttf",
    font_output_path: str = "Assets/Fonts/Generated",
    sampling_size: int = 48,
    atlas_width: int = 1024,
    atlas_height: int = 1024,
    character_set: str | None = None,
    # TMP component params
    font_asset_path: str = "",
    font_size: int = 36,
    text_color: list[float] | None = None,
    rich_text: bool = True,
    auto_sizing: bool = False,
    min_font_size: int = 18,
    max_font_size: int = 72,
    # tutorial params
    steps: list[dict] | None = None,
    # character select params
    hero_paths: list[str] | None = None,
    # world map params
    map_resolution: int = 512,
    fog_resolution: int = 256,
    # common
    namespace: str = "",
) -> str:
    """Unity UX & HUD tools -- minimap, damage numbers, interaction prompts,
    PrimeTween sequences, TextMeshPro setup, tutorial system, accessibility,
    character select, world map, rarity VFX, corruption VFX.

    UX HUD actions (ux_templates.py batch 1):
    - create_minimap: Orthographic camera + RenderTexture minimap with markers (UIX-01)
    - create_damage_numbers: Floating damage numbers with PrimeTween + ObjectPool (UIX-03)
    - create_interaction_prompts: Context-sensitive prompts with Input System rebind (UIX-04)
    - create_primetween_sequence: PrimeTween UI animation utility class (SHDR-04)
    - create_tmp_font_asset: TMP font asset creation editor script (PIPE-10)
    - setup_tmp_components: TMP component configuration editor script (PIPE-10)

    UX System actions (ux_templates.py batch 2):
    - create_tutorial_system: Step-based tutorial with tooltips + highlight rects (UIX-02)
    - create_accessibility: Colorblind simulation, subtitles, screen reader, motor (ACC-01)
    - create_character_select: Hero path carousel with PrimeTween animations (VB-09)
    - create_world_map: Heightmap-to-texture world map with fog-of-war (RPG-08)
    - create_rarity_vfx: 5-tier rarity particle + glow VFX controller (EQUIP-07)
    - create_corruption_vfx: 0-100% progressive corruption visual controller (EQUIP-08)

    Args:
        action: The UX action to perform.
        name: Name for the generated system (used in file paths).
        render_texture_size: Minimap render texture size in pixels.
        zoom: Minimap camera orthographic size.
        follow_target: Minimap follow target GameObject name.
        culling_layers: Minimap camera culling layer names.
        compass_enabled: Whether minimap includes compass direction.
        marker_types: Minimap marker type names.
        update_interval: Minimap camera update frame interval.
        pool_size: Damage number object pool size.
        float_height: Damage number float height in screen pixels.
        duration: Damage number animation duration in seconds.
        crit_scale: Damage number critical hit scale multiplier.
        prompt_text: Interaction prompt default text.
        trigger_radius: Interaction prompt trigger radius.
        fade_duration: Interaction prompt fade animation duration.
        sequence_type: PrimeTween sequence type (panel_entrance/button_hover/notification_popup/screen_shake).
        font_path: Font file path for TMP font asset creation.
        font_output_path: Output directory for generated TMP font assets.
        sampling_size: TMP font sampling point size.
        atlas_width: TMP font atlas texture width.
        atlas_height: TMP font atlas texture height.
        character_set: Custom character set for TMP font (None = ASCII).
        font_asset_path: Path to existing TMP font asset for component setup.
        font_size: TMP component font size.
        text_color: TMP component text color [r,g,b,a].
        rich_text: TMP component rich text support.
        auto_sizing: TMP component auto-sizing enabled.
        min_font_size: TMP component minimum font size (auto-sizing).
        max_font_size: TMP component maximum font size (auto-sizing).
        steps: Tutorial step definitions (list of dicts with title/description).
        hero_paths: Character select hero path names.
        map_resolution: World map texture resolution.
        fog_resolution: World map fog-of-war texture resolution.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "create_minimap":
            return await _handle_ux_minimap(
                name, render_texture_size, zoom, follow_target,
                culling_layers, compass_enabled, marker_types,
                update_interval, ns_kwargs,
            )
        elif action == "create_damage_numbers":
            return await _handle_ux_damage_numbers(
                name, pool_size, float_height, duration, crit_scale, ns_kwargs,
            )
        elif action == "create_interaction_prompts":
            return await _handle_ux_interaction_prompts(
                name, prompt_text, trigger_radius, fade_duration, ns_kwargs,
            )
        elif action == "create_primetween_sequence":
            return await _handle_ux_primetween_sequence(
                sequence_type, name, ns_kwargs,
            )
        elif action == "create_tmp_font_asset":
            return await _handle_ux_tmp_font_asset(
                font_path, font_output_path, sampling_size,
                atlas_width, atlas_height, character_set, ns_kwargs,
            )
        elif action == "setup_tmp_components":
            return await _handle_ux_tmp_components(
                name, font_asset_path, font_size, text_color,
                rich_text, auto_sizing, min_font_size, max_font_size, ns_kwargs,
            )
        elif action == "create_tutorial_system":
            return await _handle_ux_tutorial(name, steps, ns_kwargs)
        elif action == "create_accessibility":
            return await _handle_ux_accessibility(name, ns_kwargs)
        elif action == "create_character_select":
            return await _handle_ux_character_select(hero_paths, ns_kwargs)
        elif action == "create_world_map":
            return await _handle_ux_world_map(name, map_resolution, fog_resolution, ns_kwargs)
        elif action == "create_rarity_vfx":
            return await _handle_ux_rarity_vfx(name, ns_kwargs)
        elif action == "create_corruption_vfx":
            return await _handle_ux_corruption_vfx(name, ns_kwargs)
        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    except Exception as exc:
        logger.exception("unity_ux action '%s' failed", action)
        return json.dumps({"status": "error", "action": action, "message": str(exc)})


# ---------------------------------------------------------------------------
# UX action handlers
# ---------------------------------------------------------------------------


async def _handle_ux_minimap(
    name: str, render_texture_size: int, zoom: float, follow_target: str,
    culling_layers: list[str] | None, compass_enabled: bool,
    marker_types: list[str] | None, update_interval: int, ns_kwargs: dict,
) -> str:
    """Create minimap system with orthographic camera + RenderTexture (UIX-01)."""
    editor_cs, runtime_cs = generate_minimap_script(
        name=name,
        render_texture_size=render_texture_size,
        zoom=zoom,
        follow_target=follow_target,
        culling_layers=culling_layers,
        compass_enabled=compass_enabled,
        marker_types=marker_types,
        update_interval=update_interval,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/UX/{safe_name}_MinimapSetup.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_Minimap.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_minimap",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the minimap system",
            "Run editor setup from VeilBreakers > UX > Create Minimap",
        ],
    }, indent=2)


async def _handle_ux_damage_numbers(
    name: str, pool_size: int, float_height: float,
    duration: float, crit_scale: float, ns_kwargs: dict,
) -> str:
    """Create floating damage numbers with PrimeTween + ObjectPool (UIX-03)."""
    script = generate_damage_numbers_script(
        name=name,
        pool_size=pool_size,
        float_height=float_height,
        duration=duration,
        crit_scale=crit_scale,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_DamageNumbers_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_damage_numbers",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile damage numbers",
            "Attach VB_DamageNumbers to a Canvas or HUD manager",
        ],
    }, indent=2)


async def _handle_ux_interaction_prompts(
    name: str, prompt_text: str, trigger_radius: float,
    fade_duration: float, ns_kwargs: dict,
) -> str:
    """Create interaction prompts with Input System rebind display (UIX-04)."""
    script = generate_interaction_prompts_script(
        name=name,
        prompt_text=prompt_text,
        trigger_radius=trigger_radius,
        fade_duration=fade_duration,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_InteractionPrompt_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_interaction_prompts",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile interaction prompts",
            "Attach to interactable objects with a trigger collider",
        ],
    }, indent=2)


async def _handle_ux_primetween_sequence(
    sequence_type: str, name: str, ns_kwargs: dict,
) -> str:
    """Create PrimeTween UI animation sequence utility (SHDR-04)."""
    script = generate_primetween_sequence_script(
        sequence_type=sequence_type,
        name=name,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UI/VB_PrimeTweenSequence_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_primetween_sequence",
        "sequence_type": sequence_type,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the animation utility",
            "Call static methods from UI scripts for PrimeTween animations",
        ],
    }, indent=2)


async def _handle_ux_tmp_font_asset(
    font_path: str, font_output_path: str, sampling_size: int,
    atlas_width: int, atlas_height: int, character_set: str | None,
    ns_kwargs: dict,
) -> str:
    """Create TMP font asset editor script (PIPE-10)."""
    script = generate_tmp_font_asset_script(
        font_path=font_path,
        output_path=font_output_path,
        sampling_size=sampling_size,
        atlas_width=atlas_width,
        atlas_height=atlas_height,
        character_set=character_set,
        **ns_kwargs,
    )
    rel_path = "Assets/Editor/Generated/UX/VB_TMPFontAssetCreator.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_tmp_font_asset",
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the font creator",
            "Execute menu item: VeilBreakers > UX > Create TMP Font Asset",
        ],
    }, indent=2)


async def _handle_ux_tmp_components(
    name: str, font_asset_path: str, font_size: int,
    text_color: list[float] | None, rich_text: bool,
    auto_sizing: bool, min_font_size: int, max_font_size: int,
    ns_kwargs: dict,
) -> str:
    """Create TMP component setup editor script (PIPE-10)."""
    script = generate_tmp_component_script(
        name=name,
        font_asset_path=font_asset_path,
        font_size=font_size,
        color=text_color,
        rich_text=rich_text,
        auto_sizing=auto_sizing,
        min_size=min_font_size,
        max_size=max_font_size,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Editor/Generated/UX/VB_TMPSetup_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "setup_tmp_components",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile TMP setup",
            "Execute menu item: VeilBreakers > UX > Setup TMP Components",
        ],
    }, indent=2)


async def _handle_ux_tutorial(
    name: str, steps: list[dict] | None, ns_kwargs: dict,
) -> str:
    """Create tutorial system with step-based state machine (UIX-02)."""
    data_so_cs, manager_cs, uxml, uss = generate_tutorial_system_script(
        name=name, steps=steps, **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        data_so_cs, f"Assets/ScriptableObjects/UX/{safe_name}_TutorialData.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_TutorialManager.cs",
    ))
    paths.append(_write_to_unity(
        uxml, f"Assets/UI/Tutorial/{safe_name}_Tutorial.uxml",
    ))
    paths.append(_write_to_unity(
        uss, f"Assets/UI/Tutorial/{safe_name}_Tutorial.uss",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_tutorial_system",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the tutorial system",
            "Create TutorialData ScriptableObject assets with step definitions",
        ],
    }, indent=2)


async def _handle_ux_accessibility(name: str, ns_kwargs: dict) -> str:
    """Create accessibility system with colorblind, subtitles, motor options (ACC-01)."""
    settings_cs, shader_hlsl, renderer_feature_cs = generate_accessibility_script(
        name=name, **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        settings_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_AccessibilitySettings.cs",
    ))
    paths.append(_write_to_unity(
        shader_hlsl, f"Assets/Shaders/{safe_name}_ColorblindSimulation.shader",
    ))
    paths.append(_write_to_unity(
        renderer_feature_cs, f"Assets/Scripts/Runtime/Rendering/{safe_name}_ColorblindFeature.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_accessibility",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile accessibility system",
            "Add the ColorblindFeature to the URP Renderer in Project Settings",
        ],
    }, indent=2)


async def _handle_ux_character_select(
    hero_paths: list[str] | None, ns_kwargs: dict,
) -> str:
    """Create character selection screen with hero path carousel (VB-09)."""
    data_so_cs, manager_cs, uxml, uss = generate_character_select_script(
        hero_paths=hero_paths, **ns_kwargs,
    )
    paths = []
    paths.append(_write_to_unity(
        data_so_cs, "Assets/ScriptableObjects/UX/VB_HeroPathData.cs",
    ))
    paths.append(_write_to_unity(
        manager_cs, "Assets/Scripts/Runtime/UX/VB_CharacterSelectManager.cs",
    ))
    paths.append(_write_to_unity(
        uxml, "Assets/UI/CharacterSelect/VB_CharacterSelect.uxml",
    ))
    paths.append(_write_to_unity(
        uss, "Assets/UI/CharacterSelect/VB_CharacterSelect.uss",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_character_select",
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile character select",
            "Create HeroPathData ScriptableObject assets for each hero path",
        ],
    }, indent=2)


async def _handle_ux_world_map(
    name: str, map_resolution: int, fog_resolution: int, ns_kwargs: dict,
) -> str:
    """Create world map with heightmap-to-texture and fog-of-war (RPG-08)."""
    editor_cs, runtime_cs = generate_world_map_script(
        name=name,
        map_resolution=map_resolution,
        fog_resolution=fog_resolution,
        **ns_kwargs,
    )
    safe_name = name.replace(" ", "_").replace("-", "_")
    paths = []
    paths.append(_write_to_unity(
        editor_cs, f"Assets/Editor/Generated/UX/{safe_name}_WorldMapGenerator.cs",
    ))
    paths.append(_write_to_unity(
        runtime_cs, f"Assets/Scripts/Runtime/UX/{safe_name}_WorldMap.cs",
    ))
    return json.dumps({
        "status": "success",
        "action": "create_world_map",
        "name": name,
        "paths": paths,
        "next_steps": [
            "Call unity_editor action='recompile' to compile the world map system",
            "Run editor tool: VeilBreakers > UX > Generate World Map Texture",
        ],
    }, indent=2)


async def _handle_ux_rarity_vfx(name: str, ns_kwargs: dict) -> str:
    """Create rarity VFX controller with 5 tiers (EQUIP-07)."""
    script = generate_rarity_vfx_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_RarityVFX_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_rarity_vfx",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile rarity VFX",
            "Attach to item pickup or equipment display objects",
        ],
    }, indent=2)


async def _handle_ux_corruption_vfx(name: str, ns_kwargs: dict) -> str:
    """Create corruption VFX controller with 0-100% progression (EQUIP-08)."""
    script = generate_corruption_vfx_script(name=name, **ns_kwargs)
    safe_name = name.replace(" ", "_").replace("-", "_")
    rel_path = f"Assets/Scripts/Runtime/UX/VB_CorruptionVFX_{safe_name}.cs"
    abs_path = _write_to_unity(script, rel_path)
    return json.dumps({
        "status": "success",
        "action": "create_corruption_vfx",
        "name": name,
        "script_path": abs_path,
        "next_steps": [
            "Call unity_editor action='recompile' to compile corruption VFX",
            "Attach to player character or affected objects",
        ],
    }, indent=2)


@mcp.tool()
async def unity_qa(
    action: Literal[
        "setup_bridge",             # QA-00
        "run_tests",                # QA-01
        "run_play_session",         # QA-02
        "profile_scene",            # QA-03
        "detect_memory_leaks",      # QA-04
        "analyze_code",             # QA-05
        "setup_crash_reporting",    # QA-06
        "setup_analytics",          # QA-07
        "inspect_live_state",       # QA-08
    ],
    name: str = "default",
    # bridge params
    bridge_port: int = 9877,
    # test runner params
    test_mode: str = "EditMode",
    test_filter: str = "",
    timeout_seconds: int = 60,
    # play session params
    steps: list[dict] | None = None,
    timeout_per_step: float = 10.0,
    # profiler params
    target_frame_time_ms: float = 16.67,
    max_draw_calls: int = 2000,
    max_memory_mb: int = 1024,
    sample_frames: int = 60,
    # memory leak params
    growth_threshold_mb: int = 10,
    sample_interval_seconds: int = 5,
    sample_count: int = 10,
    # static analysis params
    source_code: str = "",
    source_file_path: str = "<unknown>",
    # crash reporting params
    dsn: str = "",
    environment: str = "development",
    enable_breadcrumbs: bool = True,
    sample_rate: float = 1.0,
    # analytics params
    event_names: list[str] | None = None,
    flush_interval_seconds: int = 30,
    max_buffer_size: int = 100,
    log_file_path: str = "Analytics/events.json",
    # live inspector params
    update_interval_frames: int = 10,
    max_tracked_objects: int = 20,
    # common
    namespace: str = "",
) -> str:
    """Unity Quality Assurance & Testing tools -- bridge, test runner, profiler,
    memory leak detection, static analysis, crash reporting, analytics, live inspector.

    Bridge & Infrastructure (qa_templates.py):
    - setup_bridge: TCP bridge server + command dispatch for Unity Editor automation (QA-00)

    Testing & Profiling (qa_templates.py):
    - run_tests: TestRunnerApi-based EditMode/PlayMode test execution with JSON results (QA-01)
    - run_play_session: Automated play session with sequential steps and verification (QA-02)
    - profile_scene: GPU/CPU profiler with budget comparison via ProfilerRecorder (QA-03)
    - detect_memory_leaks: Managed/native memory leak detection over sampled intervals (QA-04)
    - analyze_code: Python-side regex static analysis for Unity performance anti-patterns (QA-05)

    Observability (qa_templates.py):
    - setup_crash_reporting: Sentry SDK initialization with breadcrumbs and environment tagging (QA-06)
    - setup_analytics: Singleton analytics manager with event buffering and JSON logging (QA-07)
    - inspect_live_state: IMGUI EditorWindow for live GameObject field inspection (QA-08)

    Args:
        action: The QA action to perform.
        name: Name for the generated system (used in file paths).
        bridge_port: TCP port for VBBridge server (default 9877).
        test_mode: Test runner mode -- EditMode, PlayMode, or Both.
        test_filter: Optional test name filter substring.
        timeout_seconds: Test runner timeout in seconds.
        steps: Play session step definitions (list of dicts with action/params).
        timeout_per_step: Play session per-step timeout in seconds.
        target_frame_time_ms: Profiler target frame time budget in milliseconds.
        max_draw_calls: Profiler maximum draw call budget.
        max_memory_mb: Profiler maximum memory budget in MB.
        sample_frames: Profiler number of frames to sample.
        growth_threshold_mb: Memory leak growth threshold in MB.
        sample_interval_seconds: Memory leak sampling interval in seconds.
        sample_count: Memory leak number of samples to collect.
        source_code: C# source code string for static analysis.
        source_file_path: File path metadata for static analysis reports.
        dsn: Sentry DSN URL for crash reporting (empty = console fallback).
        environment: Sentry environment tag (development/staging/production).
        enable_breadcrumbs: Enable Sentry breadcrumb tracking.
        sample_rate: Sentry event sample rate (0.0 to 1.0).
        event_names: Analytics event names for typed convenience methods.
        flush_interval_seconds: Analytics event buffer flush interval.
        max_buffer_size: Analytics event buffer max size before auto-flush.
        log_file_path: Analytics JSON log file path relative to persistentDataPath.
        update_interval_frames: Live inspector refresh interval in frames.
        max_tracked_objects: Live inspector max pinned objects.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "setup_bridge":
            server_script = generate_bridge_server_script(
                port=bridge_port, **ns_kwargs,
            )
            commands_script = generate_bridge_commands_script(**ns_kwargs)
            server_path = _write_to_unity(
                server_script, "Assets/Editor/VBBridge/VBBridgeServer.cs",
            )
            commands_path = _write_to_unity(
                commands_script, "Assets/Editor/VBBridge/VBBridgeCommands.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_bridge",
                "paths": [server_path, commands_path],
                "next_steps": [
                    "Recompile scripts in Unity (AssetDatabase.Refresh)",
                    f"Verify VBBridge is listening on port {bridge_port} in Unity Console",
                ],
            }, indent=2)

        elif action == "run_tests":
            script = generate_test_runner_handler(
                test_mode=test_mode,
                test_filter=test_filter,
                timeout_seconds=timeout_seconds,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBTestRunner.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "run_tests",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile test runner",
                    "Execute menu item: VeilBreakers > QA > Run Tests",
                    "Read results from Temp/vb_test_results.json",
                ],
            }, indent=2)

        elif action == "run_play_session":
            script = generate_play_session_script(
                steps=steps,
                timeout_per_step=timeout_per_step,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBPlaySession.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "run_play_session",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile play session",
                    "Execute menu item: VeilBreakers > QA > Run Play Session",
                ],
            }, indent=2)

        elif action == "profile_scene":
            script = generate_profiler_handler(
                target_frame_time_ms=target_frame_time_ms,
                max_draw_calls=max_draw_calls,
                max_memory_mb=max_memory_mb,
                sample_frames=sample_frames,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBProfiler.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "profile_scene",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile profiler",
                    "Execute menu item: VeilBreakers > QA > Profile Scene",
                    "Read results from Temp/vb_profiler_results.json",
                ],
            }, indent=2)

        elif action == "detect_memory_leaks":
            script = generate_memory_leak_script(
                growth_threshold_mb=growth_threshold_mb,
                sample_interval_seconds=sample_interval_seconds,
                sample_count=sample_count,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBMemoryLeakDetector.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "detect_memory_leaks",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile leak detector",
                    "Enter Play Mode",
                    "Execute menu item: VeilBreakers > QA > Detect Memory Leaks",
                ],
            }, indent=2)

        elif action == "analyze_code":
            if not source_code:
                return json.dumps({
                    "status": "error",
                    "action": "analyze_code",
                    "message": "source_code parameter is required for static analysis",
                })
            result = analyze_csharp_static(source_code, source_file_path)
            report_lines = [
                f"Static Analysis: {result['file_path']}",
                f"Findings: {result['findings_count']}",
                "",
            ]
            for finding in result.get("findings", []):
                severity = finding.get("severity", "info")
                line = finding.get("line_number", finding.get("line", "?"))
                message = finding.get("message", "")
                fix = finding.get("fix", "")
                report_lines.append(
                    f"  [{severity.upper()}] Line {line}: {message}"
                )
                if fix:
                    report_lines.append(f"    Fix: {fix}")
            return json.dumps({
                "status": "success",
                "action": "analyze_code",
                "file_path": result["file_path"],
                "findings_count": result["findings_count"],
                "findings": result.get("findings", []),
                "report": "\n".join(report_lines),
            }, indent=2)

        elif action == "setup_crash_reporting":
            script = generate_crash_reporting_script(
                dsn=dsn,
                environment=environment,
                enable_breadcrumbs=enable_breadcrumbs,
                sample_rate=sample_rate,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Scripts/Generated/QA/VBCrashReporting.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_crash_reporting",
                "script_path": abs_path,
                "next_steps": [
                    "Install Sentry Unity SDK: add 'io.sentry.unity' via UPM",
                    "Set DSN in script or via Sentry dashboard",
                    "Call unity_editor action='recompile' to compile crash reporting",
                ],
            }, indent=2)

        elif action == "setup_analytics":
            # Validate log_file_path to prevent directory traversal

            if (log_file_path.startswith("/") or log_file_path.startswith("\\")
                    or ".." in log_file_path
                    or ":" in log_file_path):
                return json.dumps({
                    "status": "error",
                    "action": "setup_analytics",
                    "message": (
                        "log_file_path must be a relative path without "
                        "'..', leading '/' or '\\\\', or drive letters"
                    ),
                })
            script = generate_analytics_script(
                event_names=event_names,
                flush_interval_seconds=flush_interval_seconds,
                max_buffer_size=max_buffer_size,
                log_file_path=log_file_path,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Scripts/Generated/QA/VBAnalytics.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_analytics",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile analytics",
                    "Add VBAnalytics prefab to scene",
                    f"Events logged to Application.persistentDataPath/{log_file_path}",
                ],
            }, indent=2)

        elif action == "inspect_live_state":
            script = generate_live_inspector_script(
                update_interval_frames=update_interval_frames,
                max_tracked_objects=max_tracked_objects,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/QA/VBLiveInspector.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "inspect_live_state",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile live inspector",
                    "Open via VeilBreakers > QA > Live Inspector",
                    "Enter Play Mode to see live values",
                ],
            }, indent=2)

        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown action: {action}",
            })

    except Exception as exc:
        logger.exception("unity_qa action '%s' failed", action)
        return json.dumps({
            "status": "error",
            "action": action,
            "message": str(exc),
        })


@mcp.tool()
async def unity_build(
    action: Literal[
        "build_multi_platform",      # BUILD-01
        "configure_addressables",    # BUILD-02
        "generate_ci_pipeline",      # BUILD-03
        "manage_version",            # BUILD-04
        "configure_platform",        # BUILD-05
        "setup_shader_stripping",    # SHDR-03
        "generate_store_metadata",   # ACC-02
    ],
    name: str = "default",
    # multi-platform build params
    platforms: list[dict] | None = None,
    development: bool = False,
    # addressables params
    groups: list[dict] | None = None,
    build_remote: bool = False,
    # CI/CD params
    ci_provider: str = "github",
    unity_version: str = "6000.0.0f1",
    ci_platforms: list[str] | None = None,
    run_tests: bool = True,
    # version params
    version: str = "1.0.0",
    auto_increment: str = "patch",
    update_android: bool = True,
    update_ios: bool = True,
    # changelog params
    project_name: str = "VeilBreakers",
    # platform config params
    platform: str = "android",
    permissions: list[str] | None = None,
    features: list[str] | None = None,
    plist_entries: list[dict] | None = None,
    webgl_memory_mb: int = 256,
    # shader stripping params
    keywords_to_strip: list[str] | None = None,
    log_stripping: bool = True,
    # store metadata params
    game_title: str = "VeilBreakers",
    genre: str = "Action RPG",
    has_iap: bool = False,
    has_ads: bool = False,
    collects_data: bool = False,
    # common
    namespace: str = "",
) -> str:
    """Unity Build & Deploy Pipeline tools -- multi-platform builds, addressables,
    CI/CD, versioning, platform config, shader stripping, store metadata.

    Build Orchestration:
    - build_multi_platform: 6-platform build orchestrator with IL2CPP/Mono backend selection (BUILD-01)
    - configure_addressables: Addressable Asset Group configurator with BundledAssetGroupSchema (BUILD-02)
    - configure_platform: Android manifest/iOS PostProcessBuild/WebGL PlayerSettings config (BUILD-05)
    - setup_shader_stripping: IPreprocessShaders keyword blacklist for variant reduction (SHDR-03)

    CI/CD & Versioning:
    - generate_ci_pipeline: GitHub Actions or GitLab CI YAML with GameCI integration (BUILD-03)
    - manage_version: SemVer version bump + changelog generation C# editor scripts (BUILD-04)

    Store Publishing:
    - generate_store_metadata: Store description, content ratings, privacy policy markdown (ACC-02)

    Args:
        action: The build action to perform.
        name: Name for generated system (used in file paths).
        platforms: Multi-platform build target definitions (list of dicts with name/target/group/backend/extension).
        development: Enable development build mode with debugging.
        groups: Addressable group definitions (list of dicts with name/packing/local).
        build_remote: Build Addressable content for remote hosting.
        ci_provider: CI/CD provider -- "github" or "gitlab".
        unity_version: Unity editor version for CI Docker images.
        ci_platforms: CI build platforms list (e.g. ["StandaloneWindows64", "Android"]).
        run_tests: Run tests in CI pipeline before building.
        version: SemVer version string (e.g. "1.0.0").
        auto_increment: Version component to auto-increment (major/minor/patch).
        update_android: Update Android bundleVersionCode on version bump.
        update_ios: Update iOS buildNumber on version bump.
        project_name: Project name for changelog generation.
        platform: Target platform for platform-specific config (android/ios/webgl).
        permissions: Android permissions list (e.g. ["android.permission.CAMERA"]).
        features: Android features list.
        plist_entries: iOS Info.plist entries (list of dicts with key/value/type).
        webgl_memory_mb: WebGL initial memory size in MB.
        keywords_to_strip: Shader keywords to strip during builds.
        log_stripping: Log shader stripping results to JSON.
        game_title: Game title for store metadata.
        genre: Game genre for store metadata.
        has_iap: Game includes in-app purchases.
        has_ads: Game includes advertisements.
        collects_data: Game collects user data.
        namespace: C# namespace override (empty = generator default).
    """
    try:
        ns_kwargs: dict = {}
        if namespace:
            ns_kwargs["namespace"] = namespace

        if action == "build_multi_platform":
            script = generate_multi_platform_build_script(
                platforms=platforms,
                development=development,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBMultiPlatformBuild.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "build_multi_platform",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile build script",
                    "Execute menu item: VeilBreakers > Build > Multi-Platform Build",
                    "Read results from Temp/vb_build_results.json",
                ],
            }, indent=2)

        elif action == "configure_addressables":
            script = generate_addressables_config_script(
                groups=groups,
                build_remote=build_remote,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBAddressablesConfig.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "configure_addressables",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile addressables config",
                    "Execute menu item: VeilBreakers > Build > Configure Addressables",
                    "Read results from Temp/vb_result.json",
                ],
            }, indent=2)

        elif action == "generate_ci_pipeline":
            # Validate ci_platforms against the allowlist before passing
            # to generators -- prevents YAML injection via crafted names.
            if ci_platforms is not None:
                from veilbreakers_mcp.shared.unity_templates.build_templates import (
                    _validate_ci_platforms,
                )
                try:
                    ci_platforms = _validate_ci_platforms(ci_platforms)
                except ValueError as exc:
                    return json.dumps({
                        "status": "error",
                        "action": "generate_ci_pipeline",
                        "message": str(exc),
                    })

            if ci_provider == "github":
                content = generate_github_actions_workflow(
                    unity_version=unity_version,
                    platforms=ci_platforms,
                    run_tests=run_tests,
                )
                output_path = ".github/workflows/unity-build.yml"
            elif ci_provider == "gitlab":
                content = generate_gitlab_ci_config(
                    unity_version=unity_version,
                    platforms=ci_platforms,
                )
                output_path = ".gitlab-ci.yml"
            else:
                return json.dumps({
                    "status": "error",
                    "action": "generate_ci_pipeline",
                    "message": f"Unknown ci_provider: {ci_provider}. Use 'github' or 'gitlab'.",
                })

            # CI/CD files go at project root, not under Assets/
            project_root = Path(settings.unity_project_path).resolve()
            target = (project_root / output_path).resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "action": "generate_ci_pipeline",
                    "message": f"Path traversal detected: '{output_path}'",
                })
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            return json.dumps({
                "status": "success",
                "action": "generate_ci_pipeline",
                "file_path": str(target),
                "ci_provider": ci_provider,
                "next_steps": [
                    f"Review generated {ci_provider.title()} CI YAML at {output_path}",
                    "Set CI secrets: UNITY_LICENSE, UNITY_EMAIL, UNITY_PASSWORD",
                    "Push to trigger pipeline",
                ],
            }, indent=2)

        elif action == "manage_version":
            script = generate_version_management_script(
                version=version,
                auto_increment=auto_increment,
                update_android=update_android,
                update_ios=update_ios,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBVersionManager.cs",
            )
            next_steps = [
                "Call unity_editor action='recompile' to compile version manager",
                "Execute menu item: VeilBreakers > Build > Bump Version",
            ]

            # Also generate changelog script
            changelog_script = generate_changelog(
                project_name=project_name,
                version=version,
                **ns_kwargs,
            )
            changelog_path = _write_to_unity(
                changelog_script,
                "Assets/Editor/Generated/Build/VBChangelogGenerator.cs",
            )
            next_steps.append(
                "Execute menu item: VeilBreakers > Build > Generate Changelog"
            )

            return json.dumps({
                "status": "success",
                "action": "manage_version",
                "script_path": abs_path,
                "changelog_path": changelog_path,
                "next_steps": next_steps,
            }, indent=2)

        elif action == "configure_platform":
            valid_platforms = ("android", "ios", "webgl")
            if platform not in valid_platforms:
                return json.dumps({
                    "status": "error",
                    "action": "configure_platform",
                    "message": f"Unknown platform: {platform}. Use one of {valid_platforms}.",
                })

            script = generate_platform_config_script(
                platform=platform,
                permissions=permissions,
                features=features,
                plist_entries=plist_entries,
                webgl_memory_mb=webgl_memory_mb,
                **ns_kwargs,
            )

            platform_paths = {
                "android": "Assets/Editor/Generated/Build/VBAndroidConfig.cs",
                "ios": "Assets/Editor/Generated/Build/VBiOSPostProcess.cs",
                "webgl": "Assets/Editor/Generated/Build/VBWebGLConfig.cs",
            }
            output_path = platform_paths[platform]
            abs_path = _write_to_unity(script, output_path)

            platform_next_steps = {
                "android": [
                    "Call unity_editor action='recompile' to compile Android config",
                    "Execute menu item: VeilBreakers > Build > Configure Android",
                    "Review generated AndroidManifest.xml in Assets/Plugins/Android/",
                ],
                "ios": [
                    "Call unity_editor action='recompile' to compile iOS post-process",
                    "Build for iOS to trigger PostProcessBuild callback",
                    "Review Xcode project for applied Info.plist entries",
                ],
                "webgl": [
                    "Call unity_editor action='recompile' to compile WebGL config",
                    "Execute menu item: VeilBreakers > Build > Configure WebGL",
                    "Build for WebGL to apply settings",
                ],
            }

            return json.dumps({
                "status": "success",
                "action": "configure_platform",
                "platform": platform,
                "script_path": abs_path,
                "next_steps": platform_next_steps[platform],
            }, indent=2)

        elif action == "setup_shader_stripping":
            script = generate_shader_stripping_script(
                keywords_to_strip=keywords_to_strip,
                log_stripping=log_stripping,
                **ns_kwargs,
            )
            abs_path = _write_to_unity(
                script, "Assets/Editor/Generated/Build/VBShaderStripper.cs",
            )
            return json.dumps({
                "status": "success",
                "action": "setup_shader_stripping",
                "script_path": abs_path,
                "next_steps": [
                    "Call unity_editor action='recompile' to compile shader stripper",
                    "Build project to see shader stripping in action",
                    "Check Temp/vb_shader_strip_results.json for stripping report",
                ],
            }, indent=2)

        elif action == "generate_store_metadata":
            content = generate_store_metadata(
                game_title=game_title,
                genre=genre,
                has_iap=has_iap,
                has_ads=has_ads,
                collects_data=collects_data,
            )

            # Store metadata goes at project root, not under Assets/
            project_root = Path(settings.unity_project_path).resolve()
            target = (project_root / "StoreMetadata" / "STORE_LISTING.md").resolve()
            try:
                target.relative_to(project_root)
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "action": "generate_store_metadata",
                    "message": "Path traversal detected",
                })
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            return json.dumps({
                "status": "success",
                "action": "generate_store_metadata",
                "file_path": str(target),
                "next_steps": [
                    "Review generated store metadata at StoreMetadata/STORE_LISTING.md",
                    "Customize placeholder content for your game",
                    "Update screenshot specifications per store requirements",
                ],
            }, indent=2)

        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown action: {action}",
            })

    except Exception as exc:
        logger.exception("unity_build action '%s' failed", action)
        return json.dumps({
            "status": "error",
            "action": action,
            "message": str(exc),
        })


def main():
    """Entry point for the vb-unity-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
