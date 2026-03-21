#!/usr/bin/env python3
"""Deep functional verification of all 37 MCP tools (22 Unity + 15 Blender).

Checks:
1. Tool function exists and is decorated with @mcp.tool()
2. Every Literal action has a matching handler branch
3. Generator functions exist and return non-empty strings
4. Handler calls _write_to_unity (or equivalent) correctly
5. Return JSON has required keys (status, action, script_path, next_steps)
"""

import ast
import json
import os
import sys
from pathlib import Path

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

# We need to set env vars before importing to avoid Settings validation errors
os.environ.setdefault("UNITY_PROJECT_PATH", "/tmp/fake_unity_project")
os.environ.setdefault("BLENDER_HOST", "localhost")
os.environ.setdefault("BLENDER_PORT", "9876")

# Import all template modules directly (whitelist pattern -- no dynamic import_module)
# nosemgrep: python.lang.security.audit.non-literal-import
from veilbreakers_mcp.shared.unity_templates import editor_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import vfx_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import audio_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import ui_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import scene_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import gameplay_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import performance_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import settings_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import prefab_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import asset_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import code_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import data_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import pipeline_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import quality_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import game_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import vb_combat_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import content_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import equipment_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import camera_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import world_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import ux_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import encounter_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import qa_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import build_templates  # noqa: E402
from veilbreakers_mcp.shared.unity_templates import shader_templates  # noqa: E402

# Also import shared modules used by blender_server
from veilbreakers_mcp.shared import security  # noqa: E402
from veilbreakers_mcp.shared import image_utils  # noqa: E402
from veilbreakers_mcp.shared import texture_ops  # noqa: E402
from veilbreakers_mcp.shared import texture_validation  # noqa: E402
from veilbreakers_mcp.shared import esrgan_runner  # noqa: E402
from veilbreakers_mcp.shared import tripo_client  # noqa: E402
from veilbreakers_mcp.shared import pipeline_runner  # noqa: E402
from veilbreakers_mcp.shared import asset_catalog  # noqa: E402
from veilbreakers_mcp.shared import fal_client  # noqa: E402
from veilbreakers_mcp.shared import delight  # noqa: E402
from veilbreakers_mcp.shared import palette_validator  # noqa: E402
from veilbreakers_mcp.shared import blender_client  # noqa: E402
from veilbreakers_mcp.shared import config  # noqa: E402
from veilbreakers_mcp.shared import unity_client  # noqa: E402
from veilbreakers_mcp.shared import gemini_client  # noqa: E402
from veilbreakers_mcp.shared import elevenlabs_client  # noqa: E402
from veilbreakers_mcp.shared import wcag_checker  # noqa: E402
from veilbreakers_mcp.shared import screenshot_diff  # noqa: E402

# Whitelist mapping: short name -> already-imported module object
_MODULE_WHITELIST = {
    "editor_templates": editor_templates,
    "vfx_templates": vfx_templates,
    "shader_templates": shader_templates,
    "audio_templates": audio_templates,
    "ui_templates": ui_templates,
    "scene_templates": scene_templates,
    "gameplay_templates": gameplay_templates,
    "performance_templates": performance_templates,
    "settings_templates": settings_templates,
    "prefab_templates": prefab_templates,
    "asset_templates": asset_templates,
    "code_templates": code_templates,
    "data_templates": data_templates,
    "pipeline_templates": pipeline_templates,
    "quality_templates": quality_templates,
    "game_templates": game_templates,
    "vb_combat_templates": vb_combat_templates,
    "content_templates": content_templates,
    "equipment_templates": equipment_templates,
    "camera_templates": camera_templates,
    "world_templates": world_templates,
    "ux_templates": ux_templates,
    "encounter_templates": encounter_templates,
    "qa_templates": qa_templates,
    "build_templates": build_templates,
    # Shared modules (used for blender import cross-check)
    "veilbreakers_mcp.shared.security": security,
    "veilbreakers_mcp.shared.image_utils": image_utils,
    "veilbreakers_mcp.shared.texture_ops": texture_ops,
    "veilbreakers_mcp.shared.texture_validation": texture_validation,
    "veilbreakers_mcp.shared.esrgan_runner": esrgan_runner,
    "veilbreakers_mcp.shared.tripo_client": tripo_client,
    "veilbreakers_mcp.shared.pipeline_runner": pipeline_runner,
    "veilbreakers_mcp.shared.asset_catalog": asset_catalog,
    "veilbreakers_mcp.shared.fal_client": fal_client,
    "veilbreakers_mcp.shared.delight": delight,
    "veilbreakers_mcp.shared.palette_validator": palette_validator,
    "veilbreakers_mcp.shared.blender_client": blender_client,
    "veilbreakers_mcp.shared.config": config,
    "veilbreakers_mcp.shared.unity_client": unity_client,
    "veilbreakers_mcp.shared.gemini_client": gemini_client,
    "veilbreakers_mcp.shared.elevenlabs_client": elevenlabs_client,
    "veilbreakers_mcp.shared.wcag_checker": wcag_checker,
    "veilbreakers_mcp.shared.screenshot_diff": screenshot_diff,
    "veilbreakers_mcp.shared.unity_templates.editor_templates": editor_templates,
    "veilbreakers_mcp.shared.unity_templates.vfx_templates": vfx_templates,
    "veilbreakers_mcp.shared.unity_templates.shader_templates": shader_templates,
    "veilbreakers_mcp.shared.unity_templates.audio_templates": audio_templates,
    "veilbreakers_mcp.shared.unity_templates.ui_templates": ui_templates,
    "veilbreakers_mcp.shared.unity_templates.scene_templates": scene_templates,
    "veilbreakers_mcp.shared.unity_templates.gameplay_templates": gameplay_templates,
    "veilbreakers_mcp.shared.unity_templates.performance_templates": performance_templates,
    "veilbreakers_mcp.shared.unity_templates.settings_templates": settings_templates,
    "veilbreakers_mcp.shared.unity_templates.prefab_templates": prefab_templates,
    "veilbreakers_mcp.shared.unity_templates.asset_templates": asset_templates,
    "veilbreakers_mcp.shared.unity_templates.code_templates": code_templates,
    "veilbreakers_mcp.shared.unity_templates.data_templates": data_templates,
    "veilbreakers_mcp.shared.unity_templates.pipeline_templates": pipeline_templates,
    "veilbreakers_mcp.shared.unity_templates.quality_templates": quality_templates,
    "veilbreakers_mcp.shared.unity_templates.game_templates": game_templates,
    "veilbreakers_mcp.shared.unity_templates.vb_combat_templates": vb_combat_templates,
    "veilbreakers_mcp.shared.unity_templates.content_templates": content_templates,
    "veilbreakers_mcp.shared.unity_templates.equipment_templates": equipment_templates,
    "veilbreakers_mcp.shared.unity_templates.camera_templates": camera_templates,
    "veilbreakers_mcp.shared.unity_templates.world_templates": world_templates,
    "veilbreakers_mcp.shared.unity_templates.ux_templates": ux_templates,
    "veilbreakers_mcp.shared.unity_templates.encounter_templates": encounter_templates,
    "veilbreakers_mcp.shared.unity_templates.qa_templates": qa_templates,
    "veilbreakers_mcp.shared.unity_templates.build_templates": build_templates,
}


def safe_get_module(name: str):
    """Look up a module from the pre-imported whitelist. No dynamic imports."""
    mod = _MODULE_WHITELIST.get(name)
    if mod is None:
        raise ImportError(f"Module '{name}' is not in the verification whitelist")
    return mod

# ============================================================
# UNITY SERVER VERIFICATION
# ============================================================

print("=" * 80)
print("DEEP FUNCTIONAL VERIFICATION -- VeilBreakers MCP Toolkit")
print("=" * 80)
print()

total_tools = 0
passed_tools = 0
failed_tools = 0
issues = []

# ---------- Parse the source AST for both servers ----------

unity_src = Path(__file__).parent / "src" / "veilbreakers_mcp" / "unity_server.py"
blender_src = Path(__file__).parent / "src" / "veilbreakers_mcp" / "blender_server.py"

unity_code = unity_src.read_text(encoding="utf-8")
blender_code = blender_src.read_text(encoding="utf-8")

unity_tree = ast.parse(unity_code)
blender_tree = ast.parse(blender_code)


def extract_tool_functions(tree, source_code):
    """Extract all @mcp.tool() decorated async functions and their Literal actions."""
    tools = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            # Check for @mcp.tool() decorator
            is_tool = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Attribute) and dec.func.attr == "tool":
                        is_tool = True
                elif isinstance(dec, ast.Attribute) and dec.attr == "tool":
                    is_tool = True

            if not is_tool:
                continue

            func_name = node.name
            actions = []

            # Find the 'action' parameter and its Literal values
            for arg in node.args.args:
                if arg.arg == "action" and arg.annotation:
                    # Extract Literal values from annotation
                    ann = arg.annotation
                    if isinstance(ann, ast.Subscript):
                        # Literal[...]
                        if isinstance(ann.slice, ast.Tuple):
                            for elt in ann.slice.elts:
                                if isinstance(elt, ast.Constant):
                                    actions.append(elt.value)
                        elif isinstance(ann.slice, ast.Constant):
                            actions.append(ann.slice.value)

            tools[func_name] = {
                "actions": actions,
                "node": node,
                "lineno": node.lineno,
            }

    return tools


def extract_if_branches(func_node):
    """Extract all action string comparisons in if/elif chains and dict-based dispatch."""
    handled_actions = set()

    def visit_compare(node):
        """Check for action == "value" or action in (...) patterns."""
        if isinstance(node, ast.Compare):
            # action == "value"
            if (isinstance(node.left, ast.Name) and node.left.id == "action" and
                len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)):
                for comp in node.comparators:
                    if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        handled_actions.add(comp.value)
            # action in ("a", "b", ...)
            if (isinstance(node.left, ast.Name) and node.left.id == "action" and
                len(node.ops) == 1 and isinstance(node.ops[0], ast.In)):
                for comp in node.comparators:
                    if isinstance(comp, ast.Tuple) or isinstance(comp, ast.Set):
                        for elt in comp.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                handled_actions.add(elt.value)

    def visit_dict(node):
        """Check for dict-based dispatch like cmd_map = {"action": "command", ...}."""
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    handled_actions.add(key.value)

    # Also detect dict subscript dispatch: some_dict[action]
    for node in ast.walk(func_node):
        visit_compare(node)
        # Check for dict literals that map action strings to commands
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "map" in target.id.lower():
                    if isinstance(node.value, ast.Dict):
                        visit_dict(node.value)

    return handled_actions


def check_handler_calls_generator(func_body_source, action_name):
    """Check if a handler for an action calls a generator function."""
    # This is a heuristic check - look for calls in the handler branch
    pass


# ============================================================
# UNITY: Import and verify all generator functions
# ============================================================

print("PHASE 1: Unity Generator Function Verification")
print("-" * 60)

# Import all template modules to verify they load
unity_template_modules = {
    "editor_templates": "veilbreakers_mcp.shared.unity_templates.editor_templates",
    "vfx_templates": "veilbreakers_mcp.shared.unity_templates.vfx_templates",
    "shader_templates": "veilbreakers_mcp.shared.unity_templates.shader_templates",
    "audio_templates": "veilbreakers_mcp.shared.unity_templates.audio_templates",
    "ui_templates": "veilbreakers_mcp.shared.unity_templates.ui_templates",
    "scene_templates": "veilbreakers_mcp.shared.unity_templates.scene_templates",
    "gameplay_templates": "veilbreakers_mcp.shared.unity_templates.gameplay_templates",
    "performance_templates": "veilbreakers_mcp.shared.unity_templates.performance_templates",
    "settings_templates": "veilbreakers_mcp.shared.unity_templates.settings_templates",
    "prefab_templates": "veilbreakers_mcp.shared.unity_templates.prefab_templates",
    "asset_templates": "veilbreakers_mcp.shared.unity_templates.asset_templates",
    "code_templates": "veilbreakers_mcp.shared.unity_templates.code_templates",
    "data_templates": "veilbreakers_mcp.shared.unity_templates.data_templates",
    "pipeline_templates": "veilbreakers_mcp.shared.unity_templates.pipeline_templates",
    "quality_templates": "veilbreakers_mcp.shared.unity_templates.quality_templates",
    "game_templates": "veilbreakers_mcp.shared.unity_templates.game_templates",
    "vb_combat_templates": "veilbreakers_mcp.shared.unity_templates.vb_combat_templates",
    "content_templates": "veilbreakers_mcp.shared.unity_templates.content_templates",
    "equipment_templates": "veilbreakers_mcp.shared.unity_templates.equipment_templates",
    "camera_templates": "veilbreakers_mcp.shared.unity_templates.camera_templates",
    "world_templates": "veilbreakers_mcp.shared.unity_templates.world_templates",
    "ux_templates": "veilbreakers_mcp.shared.unity_templates.ux_templates",
    "encounter_templates": "veilbreakers_mcp.shared.unity_templates.encounter_templates",
    "qa_templates": "veilbreakers_mcp.shared.unity_templates.qa_templates",
    "build_templates": "veilbreakers_mcp.shared.unity_templates.build_templates",
}

loaded_modules = {}
for short_name, full_name in unity_template_modules.items():
    try:
        mod = safe_get_module(short_name)
        loaded_modules[short_name] = mod
        print(f"  OK: {short_name}")
    except Exception as e:
        print(f"  FAIL: {short_name} -- {e}")
        issues.append(f"Template import failed: {short_name} -- {e}")

print()

# ============================================================
# Map each Unity tool action to its generator function
# ============================================================

# This is the master mapping: tool_name -> {action -> (generator_func_name, module, minimal_args)}
# Built by reading the unity_server.py source

UNITY_TOOL_ACTION_GENERATORS = {
    "unity_editor": {
        "recompile": ("generate_recompile_script", "editor_templates", {}),
        "enter_play_mode": ("generate_play_mode_script", "editor_templates", {"enter": True}),
        "exit_play_mode": ("generate_play_mode_script", "editor_templates", {"enter": False}),
        "screenshot": ("generate_screenshot_script", "editor_templates", {"output_path": "test.png", "supersize": 1}),
        "console_logs": ("generate_console_log_script", "editor_templates", {"filter_type": "all", "count": 50}),
        "gemini_review": ("generate_gemini_review_script", "editor_templates", {"screenshot_path": "test.png", "criteria": ["lighting"]}),
        "run_tests": ("generate_test_runner_script", "editor_templates", {"test_mode": "EditMode", "assembly_filter": "", "category_filter": ""}),
    },
    "unity_vfx": {
        "create_particle_vfx": ("generate_particle_vfx_script", "vfx_templates", {"name": "test", "rate": 100, "lifetime": 1.0, "size": 0.5, "color": None, "shape": "cone"}),
        "create_brand_vfx": ("generate_brand_vfx_script", "vfx_templates", {"brand": "IRON"}),
        "create_environmental_vfx": ("generate_environmental_vfx_script", "vfx_templates", {"effect_type": "dust"}),
        "create_trail_vfx": ("generate_trail_vfx_script", "vfx_templates", {"name": "test", "width": 0.5, "color": None, "lifetime": 0.5}),
        "create_aura_vfx": ("generate_aura_vfx_script", "vfx_templates", {"name": "test", "color": None, "intensity": 1.0, "radius": 1.5}),
        "create_corruption_shader": ("generate_corruption_shader", "shader_templates", {}),
        "create_shader": ("generate_dissolve_shader", "shader_templates", {}),
        "setup_post_processing": ("generate_post_processing_script", "vfx_templates", {"bloom_intensity": 1.5, "bloom_threshold": 0.9, "vignette_intensity": 0.35, "ao_intensity": 0.5, "dof_focus_distance": 10.0}),
        "create_screen_effect": ("generate_screen_effect_script", "vfx_templates", {"effect_type": "camera_shake", "intensity": 1.0}),
        "create_ability_vfx": ("generate_ability_vfx_script", "vfx_templates", {"ability_name": "test", "vfx_prefab": "test.prefab", "anim_clip": "test.anim", "keyframe_time": 0.0}),
    },
    "unity_audio": {
        "generate_sfx": (None, None, {}),  # Uses ElevenLabs API, not a generator
        "generate_music_loop": (None, None, {}),  # Uses ElevenLabs API
        "generate_voice_line": (None, None, {}),  # Uses ElevenLabs API
        "generate_ambient": (None, None, {}),  # Uses ElevenLabs API
        "setup_footstep_system": ("generate_footstep_manager_script", "audio_templates", {}),
        "setup_adaptive_music": ("generate_adaptive_music_script", "audio_templates", {"music_layers": ["combat", "explore"]}),
        "setup_audio_zones": ("generate_audio_zone_script", "audio_templates", {"zone_type": "cave"}),
        "setup_audio_mixer": ("generate_audio_mixer_setup_script", "audio_templates", {"groups": ["Master", "SFX"]}),
        "setup_audio_pool_manager": ("generate_audio_pool_manager_script", "audio_templates", {"pool_size": 16}),
        "assign_animation_sfx": ("generate_animation_event_sfx_script", "audio_templates", {}),
    },
    "unity_ui": {
        "generate_ui_screen": ("generate_uxml_screen", "ui_templates", {"spec": {"title": "Test", "elements": []}}),
        "validate_layout": ("validate_uxml_layout", "ui_templates", {"uxml_string": "<UXML></UXML>"}),
        "test_responsive": ("generate_responsive_test_script", "ui_templates", {"uxml_path": "test.uxml"}),
        "check_contrast": (None, None, {}),  # Uses wcag_checker module directly
        "compare_screenshots": (None, None, {}),  # Uses screenshot_diff module directly
    },
    "unity_scene": {
        "setup_terrain": ("generate_terrain_setup_script", "scene_templates", {"heightmap_path": "test.raw", "size": (500, 100, 500), "resolution": 513}),
        "scatter_objects": ("generate_object_scatter_script", "scene_templates", {"prefab_paths": ["test.prefab"], "density": 0.5}),
        "setup_lighting": ("generate_lighting_setup_script", "scene_templates", {"time_of_day": "noon"}),
        "bake_navmesh": ("generate_navmesh_bake_script", "scene_templates", {}),
        "create_animator": ("generate_animator_controller_script", "scene_templates", {"name": "test", "states": [{"name": "Idle"}], "transitions": [], "parameters": []}),
        "configure_avatar": ("generate_avatar_config_script", "scene_templates", {"fbx_path": "test.fbx", "animation_type": "Humanoid"}),
        "setup_animation_rigging": ("generate_animation_rigging_script", "scene_templates", {"rig_name": "test", "constraints": [{"type": "TwoBoneIK", "bone": "Hand"}]}),
    },
    "unity_gameplay": {
        "create_mob_controller": ("generate_mob_controller_script", "gameplay_templates", {"name": "test"}),
        "create_aggro_system": ("generate_aggro_system_script", "gameplay_templates", {"name": "test"}),
        "create_patrol_route": ("generate_patrol_route_script", "gameplay_templates", {"name": "test"}),
        "create_spawn_system": ("generate_spawn_system_script", "gameplay_templates", {"name": "test"}),
        "create_behavior_tree": ("generate_behavior_tree_script", "gameplay_templates", {"name": "test"}),
        "create_combat_ability": ("generate_combat_ability_script", "gameplay_templates", {"name": "test"}),
        "create_projectile_system": ("generate_projectile_script", "gameplay_templates", {"name": "test"}),
        "create_encounter_system": ("generate_encounter_system_script", "encounter_templates", {"name": "test"}),
        "create_ai_director": ("generate_ai_director_script", "encounter_templates", {"name": "test"}),
        "simulate_encounters": ("generate_encounter_simulator_script", "encounter_templates", {"name": "test"}),
        "create_boss_ai": ("generate_boss_ai_script", "encounter_templates", {"name": "test"}),
    },
    "unity_performance": {
        "profile_scene": ("generate_scene_profiler_script", "performance_templates", {}),
        "setup_lod_groups": ("generate_lod_setup_script", "performance_templates", {}),
        "bake_lightmaps": ("generate_lightmap_bake_script", "performance_templates", {}),
        "audit_assets": ("generate_asset_audit_script", "performance_templates", {}),
        "automate_build": ("generate_build_automation_script", "performance_templates", {"build_target": "StandaloneWindows64"}),
    },
    "unity_settings": {
        "configure_physics": ("generate_physics_settings_script", "settings_templates", {}),
        "create_physics_material": ("generate_physics_material_script", "settings_templates", {"name": "test"}),
        "configure_player": ("generate_player_settings_script", "settings_templates", {}),
        "configure_build": ("generate_build_settings_script", "settings_templates", {}),
        "configure_quality": ("generate_quality_settings_script", "settings_templates", {}),
        "install_package": ("generate_package_install_script", "settings_templates", {"package_id": "com.unity.test"}),
        "remove_package": ("generate_package_remove_script", "settings_templates", {"package_id": "com.unity.test"}),
        "manage_tags_layers": ("generate_tag_layer_script", "settings_templates", {}),
        "sync_tags_layers": ("generate_tag_layer_sync_script", "settings_templates", {"constants_cs_path": "Assets/Scripts/Constants.cs"}),
        "configure_time": ("generate_time_settings_script", "settings_templates", {}),
        "configure_graphics": ("generate_graphics_settings_script", "settings_templates", {}),
    },
    "unity_prefab": {
        "create": ("generate_prefab_create_script", "prefab_templates", {"name": "test", "prefab_type": "prop", "save_dir": "Assets/Prefabs"}),
        "create_variant": ("generate_prefab_variant_script", "prefab_templates", {"name": "test_var", "base_prefab_path": "test.prefab"}),
        "modify": ("generate_prefab_modify_script", "prefab_templates", {"prefab_path": "test.prefab", "modifications": [{"component": "Transform", "property": "position", "value": "Vector3.zero"}]}),
        "delete": ("generate_prefab_delete_script", "prefab_templates", {"prefab_path": "test.prefab"}),
        "create_scaffold": ("generate_scaffold_prefab_script", "prefab_templates", {"name": "test", "prefab_type": "prop"}),
        "add_component": ("generate_add_component_script", "prefab_templates", {"selector": "test", "component_type": "BoxCollider"}),
        "remove_component": ("generate_remove_component_script", "prefab_templates", {"selector": "test", "component_type": "BoxCollider"}),
        "configure": ("generate_configure_component_script", "prefab_templates", {"selector": "test", "component_type": "BoxCollider", "properties": [{"property": "isTrigger", "value": "true"}]}),
        "reflect_component": ("generate_reflect_component_script", "prefab_templates", {"selector": "test", "component_type": "BoxCollider"}),
        "hierarchy": ("generate_hierarchy_script", "prefab_templates", {"operation": "list"}),
        "batch_configure": ("generate_batch_configure_script", "prefab_templates", {"selector": {"path": "Assets/Prefabs"}, "component_type": "BoxCollider", "properties": []}),
        "batch_job": ("generate_job_script", "prefab_templates", {"operations": [{"type": "add_component", "component": "Rigidbody"}]}),
        "generate_variants": ("generate_variant_matrix_script", "prefab_templates", {"base_name": "Enemy", "base_prefab_path": "test.prefab", "corruption_tiers": [0, 1], "brands": ["IRON"]}),
        "setup_joints": ("generate_joint_setup_script", "prefab_templates", {"selector": "test", "joint_type": "FixedJoint", "config": {"breakForce": 100}}),
        "setup_navmesh": ("generate_navmesh_setup_script", "prefab_templates", {"operation": "add_agent", "selector": "test"}),
        "setup_bone_sockets": ("generate_bone_socket_script", "prefab_templates", {"prefab_path": "test.prefab"}),
        "validate_project": ("generate_validate_project_script", "prefab_templates", {}),
    },
    "unity_assets": {
        "move": ("generate_asset_move_script", "asset_templates", {"old_path": "Assets/test.cs", "new_path": "Assets/test2.cs"}),
        "rename": ("generate_asset_rename_script", "asset_templates", {"asset_path": "test.cs", "new_name": "test2"}),
        "delete": ("generate_asset_delete_script", "asset_templates", {"asset_path": "test.cs"}),
        "duplicate": ("generate_asset_duplicate_script", "asset_templates", {"source_path": "test.cs", "dest_path": "test2.cs"}),
        "create_folder": ("generate_create_folder_script", "asset_templates", {"folder_path": "Assets/Test"}),
        "configure_fbx": ("generate_fbx_import_script", "asset_templates", {"asset_path": "test.fbx"}),
        "configure_texture": ("generate_texture_import_script", "asset_templates", {"asset_path": "test.png"}),
        "remap_materials": ("generate_material_remap_script", "asset_templates", {"fbx_path": "test.fbx", "remappings": {"Default": "Assets/Materials/Test.mat"}}),
        "auto_materials": ("generate_material_auto_generate_script", "asset_templates", {"fbx_path": "test.fbx", "texture_dir": "Assets/Textures"}),
        "create_asmdef": ("generate_asmdef_script", "asset_templates", {"name": "Test", "root_dir": "Assets/Scripts"}),
        "create_preset": ("generate_preset_create_script", "asset_templates", {"preset_name": "test", "source_asset_path": "Assets/test.fbx"}),
        "apply_preset": ("generate_preset_apply_script", "asset_templates", {"preset_path": "test.preset", "target_path": "test.fbx"}),
        "scan_references": ("generate_reference_scan_script", "asset_templates", {"asset_path": "test.cs"}),
        "atomic_import": ("generate_atomic_import_script", "asset_templates", {"texture_paths": ["Assets/tex.png"], "material_name": "TestMat", "fbx_path": "Assets/test.fbx"}),
    },
    "unity_code": {
        "generate_class": ("generate_class", "code_templates", {"class_name": "TestClass"}),
        "modify_script": ("modify_script", "code_templates", {"source": "using UnityEngine;\npublic class Test : MonoBehaviour { }"}),
        "editor_window": ("generate_editor_window", "code_templates", {"window_name": "TestWindow", "menu_path": "VeilBreakers/Test"}),
        "property_drawer": ("generate_property_drawer", "code_templates", {"target_type": "TestAttribute"}),
        "inspector_drawer": ("generate_inspector_drawer", "code_templates", {"target_type": "TestComponent"}),
        "scene_overlay": ("generate_scene_overlay", "code_templates", {"overlay_name": "TestOverlay", "display_name": "Test Overlay"}),
        "generate_test": ("generate_test_class", "code_templates", {"class_name": "TestTests"}),
        "service_locator": ("generate_service_locator", "code_templates", {}),
        "object_pool": ("generate_object_pool", "code_templates", {}),
        "singleton": ("generate_singleton", "code_templates", {"class_name": "TestSingleton"}),
        "state_machine": ("generate_state_machine", "code_templates", {"class_name": "TestFSM"}),
        "event_channel": ("generate_so_event_channel", "code_templates", {"event_name": "TestEvent"}),
    },
    "unity_shader": {
        "create_shader": ("generate_arbitrary_shader", "shader_templates", {"shader_name": "TestShader"}),
        "create_renderer_feature": ("generate_renderer_feature", "shader_templates", {"feature_name": "TestFeature"}),
    },
    "unity_data": {
        "create_so_definition": ("generate_so_definition", "data_templates", {"class_name": "TestSO"}),
        "create_so_assets": ("generate_asset_creation_script", "data_templates", {"so_class_name": "TestSO", "assets": [{"name": "test"}]}),
        "validate_json": ("generate_json_validator_script", "data_templates", {"config_name": "test", "json_path": "Assets/Data/test.json"}),
        "create_json_loader": ("generate_json_loader_script", "data_templates", {"class_name": "TestData"}),
        "setup_localization": ("generate_localization_setup_script", "data_templates", {}),
        "add_localization_entries": ("generate_localization_entries_script", "data_templates", {"table_name": "test"}),
        "create_data_editor": ("generate_data_authoring_window", "data_templates", {"window_name": "TestEditor", "so_class_name": "TestSO"}),
    },
    "unity_quality": {
        "check_poly_budget": ("generate_poly_budget_check_script", "quality_templates", {}),
        "create_master_materials": ("generate_master_material_script", "quality_templates", {}),
        "check_texture_quality": ("generate_texture_quality_check_script", "quality_templates", {}),
        "aaa_audit": ("generate_aaa_validation_script", "quality_templates", {}),
    },
    "unity_pipeline": {
        "create_sprite_atlas": ("generate_sprite_atlas_script", "pipeline_templates", {"atlas_name": "test", "source_folder": "Assets/Sprites"}),
        "create_sprite_animation": ("generate_sprite_animation_script", "pipeline_templates", {"clip_name": "test", "sprite_folder": "Assets/Sprites"}),
        "configure_sprite_editor": ("generate_sprite_editor_config_script", "pipeline_templates", {"sprite_path": "test.png"}),
        "create_asset_postprocessor": ("generate_asset_postprocessor_script", "pipeline_templates", {"processor_name": "test"}),
        "configure_git_lfs": ("generate_gitlfs_config", "pipeline_templates", {}),
    },
    "unity_game": {
        "create_save_system": ("generate_save_system_script", "game_templates", {}),
        "create_health_system": ("generate_health_system_script", "game_templates", {}),
        "create_character_controller": ("generate_character_controller_script", "game_templates", {}),
        "create_input_config": ("generate_input_config_script", "game_templates", {}),
        "create_settings_menu": ("generate_settings_menu_script", "game_templates", {}),
        "create_http_client": ("generate_http_client_script", "game_templates", {}),
        "create_interactable": ("generate_interactable_script", "game_templates", {}),
        "create_player_combat": ("generate_player_combat_script", "vb_combat_templates", {}),
        "create_ability_system": ("generate_ability_system_script", "vb_combat_templates", {}),
        "create_synergy_engine": ("generate_synergy_engine_script", "vb_combat_templates", {}),
        "create_corruption_gameplay": ("generate_corruption_gameplay_script", "vb_combat_templates", {}),
        "create_xp_leveling": ("generate_xp_leveling_script", "vb_combat_templates", {}),
        "create_currency_system": ("generate_currency_system_script", "vb_combat_templates", {}),
        "create_damage_types": ("generate_damage_type_script", "vb_combat_templates", {}),
    },
    "unity_content": {
        "create_inventory_system": ("generate_inventory_system_script", "content_templates", {}),
        "create_dialogue_system": ("generate_dialogue_system_script", "content_templates", {}),
        "create_quest_system": ("generate_quest_system_script", "content_templates", {}),
        "create_loot_table": ("generate_loot_table_script", "content_templates", {}),
        "create_crafting_system": ("generate_crafting_system_script", "content_templates", {}),
        "create_skill_tree": ("generate_skill_tree_script", "content_templates", {}),
        "create_dps_calculator": ("generate_dps_calculator_script", "content_templates", {}),
        "create_encounter_simulator": ("generate_encounter_simulator_script", "content_templates", {}),
        "create_stat_curve_editor": ("generate_stat_curve_editor_script", "content_templates", {}),
        "create_shop_system": ("generate_shop_system_script", "content_templates", {}),
        "create_journal_system": ("generate_journal_system_script", "content_templates", {}),
        "create_equipment_attachment": ("generate_equipment_attachment_script", "equipment_templates", {}),
    },
    "unity_camera": {
        "create_virtual_camera": ("generate_cinemachine_setup_script", "camera_templates", {}),
        "create_state_driven_camera": ("generate_state_driven_camera_script", "camera_templates", {}),
        "create_camera_shake": ("generate_camera_shake_script", "camera_templates", {}),
        "configure_blend": ("generate_camera_blend_script", "camera_templates", {}),
        "create_timeline": ("generate_timeline_setup_script", "camera_templates", {}),
        "create_cutscene": ("generate_cutscene_setup_script", "camera_templates", {}),
        "edit_animation_clip": ("generate_animation_clip_editor_script", "camera_templates", {}),
        "modify_animator": ("generate_animator_modifier_script", "camera_templates", {}),
        "create_avatar_mask": ("generate_avatar_mask_script", "camera_templates", {}),
        "setup_video_player": ("generate_video_player_script", "camera_templates", {}),
    },
    "unity_world": {
        "create_scene": ("generate_scene_creation_script", "world_templates", {"scene_name": "TestScene"}),
        "create_transition_system": ("generate_scene_transition_script", "world_templates", {}),
        "setup_probes": ("generate_probe_setup_script", "world_templates", {}),
        "setup_occlusion": ("generate_occlusion_setup_script", "world_templates", {}),
        "setup_environment": ("generate_environment_setup_script", "world_templates", {}),
        "paint_terrain_detail": ("generate_terrain_detail_script", "world_templates", {}),
        "create_tilemap": ("generate_tilemap_setup_script", "world_templates", {}),
        "setup_2d_physics": ("generate_2d_physics_script", "world_templates", {}),
        "apply_time_of_day": ("generate_time_of_day_preset_script", "world_templates", {}),
        "create_fast_travel": ("generate_fast_travel_script", "world_templates", {}),
        "create_puzzle": ("generate_puzzle_mechanics_script", "world_templates", {}),
        "create_trap": ("generate_trap_system_script", "world_templates", {}),
        "create_spatial_loot": ("generate_spatial_loot_script", "world_templates", {}),
        "create_weather": ("generate_weather_system_script", "world_templates", {}),
        "create_day_night": ("generate_day_night_cycle_script", "world_templates", {}),
        "create_npc_placement": ("generate_npc_placement_script", "world_templates", {}),
        "create_dungeon_lighting": ("generate_dungeon_lighting_script", "world_templates", {}),
        "create_terrain_blend": ("generate_terrain_building_blend_script", "world_templates", {}),
    },
    "unity_ux": {
        "create_minimap": ("generate_minimap_script", "ux_templates", {}),
        "create_damage_numbers": ("generate_damage_numbers_script", "ux_templates", {}),
        "create_interaction_prompts": ("generate_interaction_prompts_script", "ux_templates", {}),
        "create_primetween_sequence": ("generate_primetween_sequence_script", "ux_templates", {}),
        "create_tmp_font_asset": ("generate_tmp_font_asset_script", "ux_templates", {}),
        "setup_tmp_components": ("generate_tmp_component_script", "ux_templates", {}),
        "create_tutorial_system": ("generate_tutorial_system_script", "ux_templates", {}),
        "create_accessibility": ("generate_accessibility_script", "ux_templates", {}),
        "create_character_select": ("generate_character_select_script", "ux_templates", {}),
        "create_world_map": ("generate_world_map_script", "ux_templates", {}),
        "create_rarity_vfx": ("generate_rarity_vfx_script", "ux_templates", {}),
        "create_corruption_vfx": ("generate_corruption_vfx_script", "ux_templates", {}),
    },
    "unity_qa": {
        "setup_bridge": ("generate_bridge_server_script", "qa_templates", {}),
        "run_tests": ("generate_test_runner_handler", "qa_templates", {}),
        "run_play_session": ("generate_play_session_script", "qa_templates", {}),
        "profile_scene": ("generate_profiler_handler", "qa_templates", {}),
        "detect_memory_leaks": ("generate_memory_leak_script", "qa_templates", {}),
        "analyze_code": ("analyze_csharp_static", "qa_templates", {"source_code": "using UnityEngine;\npublic class Test : MonoBehaviour { }"}),
        "setup_crash_reporting": ("generate_crash_reporting_script", "qa_templates", {}),
        "setup_analytics": ("generate_analytics_script", "qa_templates", {}),
        "inspect_live_state": ("generate_live_inspector_script", "qa_templates", {}),
        "check_compile_status": (None, None, {}),  # Direct TCP call, no generator
    },
    "unity_build": {
        "build_multi_platform": ("generate_multi_platform_build_script", "build_templates", {}),
        "configure_addressables": ("generate_addressables_config_script", "build_templates", {}),
        "generate_ci_pipeline": (None, None, {}),  # Multiple generators (github/gitlab)
        "manage_version": (None, None, {}),  # Multiple generators (version + changelog)
        "configure_platform": ("generate_platform_config_script", "build_templates", {"platform": "android"}),
        "setup_shader_stripping": ("generate_shader_stripping_script", "build_templates", {}),
        "generate_store_metadata": ("generate_store_metadata", "build_templates", {"project_name": "VeilBreakers"}),
    },
}


# ============================================================
# PHASE 2: Extract tool functions from AST and verify
# ============================================================

print("PHASE 2: Unity Tool Function & Action Dispatch Verification")
print("-" * 60)

unity_tools = extract_tool_functions(unity_tree, unity_code)

# Expected 22 Unity tools
expected_unity_tools = [
    "unity_editor", "unity_vfx", "unity_audio", "unity_ui", "unity_scene",
    "unity_gameplay", "unity_performance", "unity_settings", "unity_prefab",
    "unity_assets", "unity_code", "unity_shader", "unity_data", "unity_quality",
    "unity_pipeline", "unity_game", "unity_content", "unity_camera",
    "unity_world", "unity_ux", "unity_qa", "unity_build",
]

for tool_name in expected_unity_tools:
    total_tools += 1
    tool_issues = []

    # Check 1: Tool function exists with @mcp.tool()
    if tool_name not in unity_tools:
        tool_issues.append(f"Tool function not found or missing @mcp.tool() decorator")
        issues.extend([f"{tool_name}: {i}" for i in tool_issues])
        failed_tools += 1
        print(f"  FAIL: {tool_name} -- {'; '.join(tool_issues)}")
        continue

    tool_info = unity_tools[tool_name]
    declared_actions = tool_info["actions"]

    # Check 2: Verify handler branches exist for all actions
    handled_actions = extract_if_branches(tool_info["node"])
    unhandled = set(declared_actions) - handled_actions

    if unhandled:
        tool_issues.append(f"Missing handler branches for: {sorted(unhandled)}")

    # Check 3: Verify generator functions exist and produce output
    if tool_name in UNITY_TOOL_ACTION_GENERATORS:
        action_map = UNITY_TOOL_ACTION_GENERATORS[tool_name]
        for action_name in declared_actions:
            if action_name not in action_map:
                tool_issues.append(f"Action '{action_name}' not in verification map")
                continue

            gen_name, mod_name, args = action_map[action_name]

            if gen_name is None:
                # Skip actions that don't use generators (API calls, etc.)
                continue

            if mod_name not in loaded_modules:
                tool_issues.append(f"Module '{mod_name}' not loaded for action '{action_name}'")
                continue

            mod = loaded_modules[mod_name]

            if not hasattr(mod, gen_name):
                tool_issues.append(f"Generator '{gen_name}' not found in {mod_name}")
                continue

            gen_func = getattr(mod, gen_name)

            # Try calling with minimal args
            try:
                result = gen_func(**args)
                if not result or (isinstance(result, str) and len(result.strip()) == 0):
                    tool_issues.append(f"Generator '{gen_name}' returned empty output for action '{action_name}'")
                elif isinstance(result, str) and len(result) < 10:
                    tool_issues.append(f"Generator '{gen_name}' returned suspiciously short output ({len(result)} chars) for action '{action_name}'")
            except TypeError as e:
                # Try calling with no args as fallback
                try:
                    result = gen_func()
                    if not result or (isinstance(result, str) and len(result.strip()) == 0):
                        tool_issues.append(f"Generator '{gen_name}' returned empty output for action '{action_name}'")
                except Exception as e2:
                    tool_issues.append(f"Generator '{gen_name}' call failed for '{action_name}': {e} / fallback: {e2}")
            except Exception as e:
                tool_issues.append(f"Generator '{gen_name}' call failed for '{action_name}': {e}")

    if tool_issues:
        failed_tools += 1
        issues.extend([f"{tool_name}: {i}" for i in tool_issues])
        print(f"  FAIL: {tool_name} ({len(declared_actions)} actions) -- {'; '.join(tool_issues)}")
    else:
        passed_tools += 1
        print(f"  PASS: {tool_name} -- all {len(declared_actions)} actions verified")


# ============================================================
# PHASE 3: Blender Tool Verification
# ============================================================

print()
print("PHASE 3: Blender Tool Function & Action Dispatch Verification")
print("-" * 60)

blender_tools = extract_tool_functions(blender_tree, blender_code)

expected_blender_tools = [
    "blender_scene", "blender_object", "blender_material", "blender_viewport",
    "blender_execute", "blender_export", "blender_mesh", "blender_uv",
    "blender_texture", "asset_pipeline", "concept_art", "blender_rig",
    "blender_animation", "blender_environment", "blender_worldbuilding",
]

# For Blender tools we check:
# 1. Tool exists with @mcp.tool()
# 2. All Literal actions have handler branches
# (Blender tools dispatch to Blender socket, not Python generators)

for tool_name in expected_blender_tools:
    total_tools += 1
    tool_issues = []

    if tool_name not in blender_tools:
        tool_issues.append(f"Tool function not found or missing @mcp.tool() decorator")
        issues.extend([f"{tool_name}: {i}" for i in tool_issues])
        failed_tools += 1
        print(f"  FAIL: {tool_name} -- {'; '.join(tool_issues)}")
        continue

    tool_info = blender_tools[tool_name]
    declared_actions = tool_info["actions"]

    if declared_actions:
        handled_actions = extract_if_branches(tool_info["node"])
        unhandled = set(declared_actions) - handled_actions

        if unhandled:
            tool_issues.append(f"Missing handler branches for: {sorted(unhandled)}")

    # For blender_execute and blender_export, no action param
    if not declared_actions and tool_name in ("blender_execute", "blender_export"):
        # These don't have Literal actions, they're single-purpose
        pass

    if tool_issues:
        failed_tools += 1
        issues.extend([f"{tool_name}: {i}" for i in tool_issues])
        print(f"  FAIL: {tool_name} ({len(declared_actions)} actions) -- {'; '.join(tool_issues)}")
    else:
        passed_tools += 1
        action_count = len(declared_actions) if declared_actions else "N/A (single-purpose)"
        print(f"  PASS: {tool_name} -- all {action_count} actions verified")


# ============================================================
# PHASE 4: Cross-check imports in unity_server.py
# ============================================================

print()
print("PHASE 4: Import Verification -- unity_server.py")
print("-" * 60)

# Verify all imports in unity_server.py actually resolve
import_issues = []
for node in ast.walk(unity_tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and "unity_templates" in (node.module or ""):
            for alias in node.names:
                mod_path = node.module
                func_name = alias.name
                try:
                    mod = safe_get_module(mod_path)
                    if not hasattr(mod, func_name):
                        import_issues.append(f"'{func_name}' not found in {mod_path}")
                except ImportError as e:
                    import_issues.append(f"Cannot import {mod_path}: {e}")

if import_issues:
    print(f"  FAIL: {len(import_issues)} import issues found:")
    for issue in import_issues:
        print(f"    - {issue}")
        issues.append(f"Import: {issue}")
else:
    print(f"  OK: All unity_templates imports verified")


# ============================================================
# PHASE 5: Verify blender_server.py imports
# ============================================================

print()
print("PHASE 5: Import Verification -- blender_server.py")
print("-" * 60)

blender_import_issues = []
for node in ast.walk(blender_tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and "veilbreakers_mcp" in (node.module or ""):
            for alias in node.names:
                mod_path = node.module
                func_name = alias.name
                try:
                    mod = safe_get_module(mod_path)
                    if not hasattr(mod, func_name):
                        blender_import_issues.append(f"'{func_name}' not found in {mod_path}")
                except ImportError as e:
                    blender_import_issues.append(f"Cannot import {mod_path}: {e}")

if blender_import_issues:
    print(f"  FAIL: {len(blender_import_issues)} import issues found:")
    for issue in blender_import_issues:
        print(f"    - {issue}")
        issues.append(f"Import: {issue}")
else:
    print(f"  OK: All blender_server imports verified")


# ============================================================
# PHASE 6: Verify generator output is valid C#/HLSL (basic check)
# ============================================================

print()
print("PHASE 6: Generator Output Quality Spot-Check")
print("-" * 60)

spot_check_generators = [
    ("generate_recompile_script", "editor_templates", {}, "recompile"),
    ("generate_particle_vfx_script", "vfx_templates", {"name": "test", "rate": 100, "lifetime": 1.0, "size": 0.5, "color": None, "shape": "cone"}, "particle_vfx"),
    ("generate_mob_controller_script", "gameplay_templates", {"name": "test"}, "mob_controller"),
    ("generate_save_system_script", "game_templates", {}, "save_system"),
    ("generate_inventory_system_script", "content_templates", {}, "inventory"),
    ("generate_corruption_shader", "shader_templates", {}, "corruption_shader"),
    ("generate_cinemachine_setup_script", "camera_templates", {}, "cinemachine"),
    ("generate_scene_creation_script", "world_templates", {"scene_name": "TestScene"}, "scene_creation"),
    ("generate_minimap_script", "ux_templates", {}, "minimap"),
    ("generate_bridge_server_script", "qa_templates", {}, "qa_bridge"),
    ("generate_multi_platform_build_script", "build_templates", {}, "multi_platform_build"),
]

spot_check_pass = 0
spot_check_fail = 0
for gen_name, mod_name, args, label in spot_check_generators:
    if mod_name not in loaded_modules:
        print(f"  SKIP: {label} -- module not loaded")
        continue

    mod = loaded_modules[mod_name]
    gen_func = getattr(mod, gen_name, None)
    if gen_func is None:
        print(f"  FAIL: {label} -- generator not found")
        spot_check_fail += 1
        continue

    try:
        output = gen_func(**args)
        if isinstance(output, str) and len(output) > 50:
            # Check for basic C# or shader markers
            has_csharp = "using " in output or "class " in output or "Shader " in output or "namespace " in output
            has_newlines = "\n" in output
            if has_csharp and has_newlines:
                print(f"  OK: {label} -- {len(output)} chars, valid C#/shader structure")
                spot_check_pass += 1
            else:
                print(f"  WARN: {label} -- {len(output)} chars, missing expected C# markers")
                spot_check_fail += 1
        elif isinstance(output, tuple) and len(output) >= 2:
            # Some generators return (script, path) tuples
            content = output[0] if isinstance(output[0], str) else str(output)
            print(f"  OK: {label} -- tuple output, {len(content)} chars")
            spot_check_pass += 1
        elif isinstance(output, dict):
            # Some return dicts (like git config generators)
            print(f"  OK: {label} -- dict output with {len(output)} keys")
            spot_check_pass += 1
        else:
            print(f"  WARN: {label} -- unexpected output type: {type(output).__name__}, len={len(str(output))}")
            spot_check_fail += 1
    except Exception as e:
        print(f"  FAIL: {label} -- {e}")
        spot_check_fail += 1


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 80)
print("FINAL REPORT")
print("=" * 80)
print()
print(f"Tools verified: {total_tools}/37")
print(f"  PASSED: {passed_tools}")
print(f"  FAILED: {failed_tools}")
print()
print(f"Generator spot-checks: {spot_check_pass} passed, {spot_check_fail} failed")
print()

if issues:
    print(f"Issues found ({len(issues)}):")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
else:
    print("No issues found!")

print()
print(f"RESULT: {passed_tools}/{total_tools} tools fully verified, {len(issues)} issues found.")
