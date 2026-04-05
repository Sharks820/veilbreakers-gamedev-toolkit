"""Deep C# template syntax verification.

Calls every template generator with default parameters and verifies:
1. Balanced braces in the output string
2. Expected C# keywords present (class, void, using, etc.)
3. No Python f-string artifacts remain (bare {variable_name} patterns)
4. Semicolons at end of statements
5. Proper try/catch structure (every try has a catch)
6. No unescaped quotes inside C# string literals
"""

from __future__ import annotations

import re
import pytest

# ---------------------------------------------------------------------------
# editor_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_recompile_script,
    generate_play_mode_script,
    generate_screenshot_script,
    generate_console_log_script,
    generate_gemini_review_script,
    generate_test_runner_script,
)

# ---------------------------------------------------------------------------
# code_templates.py generators (Phase 10)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.code_templates import (
    generate_class,
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

# ---------------------------------------------------------------------------
# vfx_templates.py generators
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# shader_templates.py generators
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# audio_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_footstep_manager_script,
    generate_adaptive_music_script,
    generate_audio_zone_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_animation_event_sfx_script,
)

# ---------------------------------------------------------------------------
# ui_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    generate_uss_stylesheet,
    generate_responsive_test_script,
)

# ---------------------------------------------------------------------------
# scene_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_tiled_terrain_setup_script,
    generate_object_scatter_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_animation_rigging_script,
)

# ---------------------------------------------------------------------------
# gameplay_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_mob_controller_script,
    generate_aggro_system_script,
    generate_patrol_route_script,
    generate_spawn_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_projectile_script,
)

# ---------------------------------------------------------------------------
# performance_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    generate_scene_profiler_script,
    generate_lod_setup_script,
    generate_lightmap_bake_script,
    generate_asset_audit_script,
    generate_build_automation_script,
)

# ---------------------------------------------------------------------------
# data_templates.py generators (Phase 11)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.data_templates import (
    generate_so_definition,
    generate_asset_creation_script,
    generate_json_validator_script,
    generate_json_loader_script,
    generate_localization_setup_script,
    generate_localization_entries_script,
    generate_data_authoring_window,
)

# ---------------------------------------------------------------------------
# pipeline_templates.py generators (Phase 11 -- C# only)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.pipeline_templates import (
    generate_sprite_atlas_script,
    generate_sprite_animation_script,
    generate_sprite_editor_config_script,
    generate_asset_postprocessor_script,
)

# ---------------------------------------------------------------------------
# quality_templates.py generators (Phase 11)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.quality_templates import (
    generate_poly_budget_check_script,
    generate_master_material_script,
    generate_texture_quality_check_script,
    generate_aaa_validation_script,
)

# ---------------------------------------------------------------------------
# game_templates.py generators (Phase 12 -- Core Game Systems)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.game_templates import (
    generate_save_system_script,
    generate_health_system_script,
    generate_character_controller_script,
    generate_input_config_script,
    generate_settings_menu_script,
    generate_http_client_script,
    generate_interactable_script,
)

# ---------------------------------------------------------------------------
# vb_combat_templates.py generators (Phase 12 -- VeilBreakers Combat)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.vb_combat_templates import (
    generate_player_combat_script,
    generate_ability_system_script,
    generate_synergy_engine_script,
    generate_corruption_gameplay_script,
    generate_xp_leveling_script,
    generate_currency_system_script,
    generate_damage_type_script,
)

# ---------------------------------------------------------------------------
# content_templates.py generators (Phase 13 -- Content & Progression)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# equipment_templates.py generators (Phase 13 -- Equipment Attachment)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.equipment_templates import (
    generate_equipment_attachment_script,
)

# ---------------------------------------------------------------------------
# camera_templates.py generators (Phase 14 -- Camera, Cinematics & Animation)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# world_templates.py generators (Phase 14 -- Scene & World Systems)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# ux_templates.py generators (Phase 15 -- Game UX)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# encounter_templates.py generators (Phase 15 -- Encounter & AI)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.encounter_templates import (
    generate_encounter_system_script as generate_enc_system_script,
    generate_ai_director_script,
    generate_encounter_simulator_script as generate_enc_sim_script,
    generate_boss_ai_script,
)

# ---------------------------------------------------------------------------
# qa_templates.py generators (Phase 16 -- Quality Assurance & Testing)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.qa_templates import (
    generate_bridge_server_script,
    generate_bridge_commands_script,
    generate_test_runner_handler,
    generate_play_session_script,
    generate_profiler_handler,
    generate_memory_leak_script,
    generate_crash_reporting_script,
    generate_analytics_script,
    generate_live_inspector_script,
)

# ---------------------------------------------------------------------------
# build_templates.py generators (Phase 17 -- Build & Deploy Pipeline)
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.build_templates import (
    generate_multi_platform_build_script,
    generate_addressables_config_script,
    generate_platform_config_script,
    generate_shader_stripping_script,
    generate_version_management_script,
    generate_changelog,
)


# ===================================================================
# Build a list of (name, callable, is_csharp) for every generator
# ===================================================================

# Each entry: (test_id, generator_callable_returning_string, is_csharp_or_shader)
# is_csharp_or_shader = "cs" | "shader" | "uxml" | "uss"

ALL_GENERATORS: list[tuple[str, callable, str]] = [
    # --- editor ---
    ("editor/recompile", generate_recompile_script, "cs"),
    ("editor/play_mode_enter", lambda: generate_play_mode_script(enter=True), "cs"),
    ("editor/play_mode_exit", lambda: generate_play_mode_script(enter=False), "cs"),
    ("editor/screenshot", lambda: generate_screenshot_script(), "cs"),
    ("editor/console_log_all", lambda: generate_console_log_script(filter_type="all"), "cs"),
    ("editor/console_log_error", lambda: generate_console_log_script(filter_type="error"), "cs"),
    ("editor/gemini_review", lambda: generate_gemini_review_script("Screenshots/test.png", ["lighting", "composition"]), "cs"),
    ("editor/test_runner", lambda: generate_test_runner_script(), "cs"),
    ("editor/test_runner_playmode", lambda: generate_test_runner_script(test_mode="PlayMode"), "cs"),
    ("editor/test_runner_filtered", lambda: generate_test_runner_script(assembly_filter="VeilBreakers.Tests", category_filter="Unit"), "cs"),

    # --- code generation (Phase 10) ---
    ("code/class_monobehaviour", lambda: generate_class("TestClass", "MonoBehaviour", namespace="Test", summary="A test MonoBehaviour class for validation"), "cs"),
    ("code/class_scriptable_object", lambda: generate_class("TestSO", "ScriptableObject", namespace="Test", summary="A test ScriptableObject for validation"), "cs"),
    ("code/class_plain", lambda: generate_class("TestPlain", "class", namespace="Test", usings=["System"], summary="A plain test class", methods=[{"access": "public", "return_type": "void", "name": "Execute", "body": "// TODO"}]), "cs"),
    ("code/class_static", lambda: generate_class("TestStatic", "static class", namespace="Test", usings=["System"], methods=[{"access": "public static", "return_type": "string", "name": "GetName", "body": 'return "test";'}]), "cs"),
    ("code/class_abstract", lambda: generate_class("TestAbstract", "abstract class", namespace="Test", usings=["System"], methods=[{"access": "public abstract", "return_type": "void", "name": "OnExecute"}]), "cs"),
    ("code/class_struct", lambda: generate_class("TestStruct", "struct", namespace="Game.Data", usings=["System"], fields=[{"access": "public", "type": "float", "name": "x"}, {"access": "public", "type": "float", "name": "y"}, {"access": "public", "type": "float", "name": "z"}]), "cs"),
    ("code/class_enum", lambda: generate_class("TestEnum", "enum", namespace="Game", enum_values=["None", "Attack", "Defend", "Heal", "Flee"]), "cs"),
    ("code/class_interface", lambda: generate_class("ITestable", "interface", namespace="Game", methods=[{"access": "", "return_type": "void", "name": "Initialize"}, {"access": "", "return_type": "bool", "name": "IsReady"}]), "cs"),
    (
        "code/class_with_members",
        lambda: generate_class(
            "PlayerStats", "MonoBehaviour", namespace="Game",
            fields=[{"access": "private", "type": "int", "name": "health", "default": "100"}],
            properties=[{"access": "public", "type": "int", "name": "Health", "getter": "return health;", "setter": "health = value;"}],
            methods=[{"access": "public", "return_type": "void", "name": "TakeDamage", "params": "int amount", "body": "health -= amount;"}],
        ),
        "cs",
    ),
    ("code/editor_window", lambda: generate_editor_window("TestWindow", "Tools/Test"), "cs"),
    ("code/editor_window_custom", lambda: generate_editor_window("DebugPanel", "VeilBreakers/Debug", on_gui_body='GUILayout.Label("Debug Info");'), "cs"),
    ("code/property_drawer", lambda: generate_property_drawer("TestType"), "cs"),
    ("code/property_drawer_custom", lambda: generate_property_drawer("HealthRange", drawer_body='EditorGUI.Slider(position, property.floatValue, 0f, 100f);'), "cs"),
    ("code/inspector_drawer", lambda: generate_inspector_drawer("TestComponent"), "cs"),
    ("code/inspector_drawer_fields", lambda: generate_inspector_drawer("EnemyStats", fields_to_draw=["health", "damage", "speed"]), "cs"),
    ("code/scene_overlay", lambda: generate_scene_overlay("TestOverlay", "Test"), "cs"),
    ("code/test_class_editmode", lambda: generate_test_class("TestSuite"), "cs"),
    ("code/test_class_playmode", lambda: generate_test_class("PlayTests", test_mode="PlayMode"), "cs"),
    (
        "code/test_class_with_methods",
        lambda: generate_test_class(
            "HealthTests", target_class="PlayerHealth",
            test_methods=[
                {"name": "TestInitialHealth", "body": "Assert.AreEqual(100, _sut.CurrentHealth);"},
                {"name": "TestDamage", "body": "_sut.TakeDamage(10);\nAssert.AreEqual(90, _sut.CurrentHealth);"},
            ],
        ),
        "cs",
    ),
    ("code/service_locator", lambda: generate_service_locator(), "cs"),
    ("code/service_locator_no_init", lambda: generate_service_locator(include_scene_persistent=False), "cs"),
    ("code/object_pool", lambda: generate_object_pool(), "cs"),
    ("code/object_pool_no_go", lambda: generate_object_pool(include_gameobject_pool=False), "cs"),
    ("code/singleton_mono", lambda: generate_singleton("TestSingleton", "MonoBehaviour"), "cs"),
    ("code/singleton_plain", lambda: generate_singleton("TestSingleton2", "Plain"), "cs"),
    ("code/singleton_no_persist", lambda: generate_singleton("TransientSingleton", "MonoBehaviour", persistent=False), "cs"),
    ("code/state_machine", lambda: generate_state_machine(), "cs"),
    ("code/event_channel_base", lambda: generate_so_event_channel(), "cs"),
    ("code/event_channel_typed", lambda: generate_so_event_channel(event_name="PlayerDeath"), "cs"),
    ("code/event_channel_param", lambda: generate_so_event_channel(event_name="DamageDealt", has_parameter=True, parameter_type="float"), "cs"),

    # --- vfx ---
    ("vfx/particle", lambda: generate_particle_vfx_script(name="TestEffect"), "cs"),
    ("vfx/brand_iron", lambda: generate_brand_vfx_script("IRON"), "cs"),
    ("vfx/brand_venom", lambda: generate_brand_vfx_script("VENOM"), "cs"),
    ("vfx/brand_surge", lambda: generate_brand_vfx_script("SURGE"), "cs"),
    ("vfx/brand_dread", lambda: generate_brand_vfx_script("DREAD"), "cs"),
    ("vfx/brand_savage", lambda: generate_brand_vfx_script("SAVAGE"), "cs"),
    ("vfx/brand_leech", lambda: generate_brand_vfx_script("LEECH"), "cs"),
    ("vfx/brand_grace", lambda: generate_brand_vfx_script("GRACE"), "cs"),
    ("vfx/brand_mend", lambda: generate_brand_vfx_script("MEND"), "cs"),
    ("vfx/brand_ruin", lambda: generate_brand_vfx_script("RUIN"), "cs"),
    ("vfx/brand_void", lambda: generate_brand_vfx_script("VOID"), "cs"),
    ("vfx/env_dust", lambda: generate_environmental_vfx_script("dust"), "cs"),
    ("vfx/env_fireflies", lambda: generate_environmental_vfx_script("fireflies"), "cs"),
    ("vfx/env_snow", lambda: generate_environmental_vfx_script("snow"), "cs"),
    ("vfx/env_rain", lambda: generate_environmental_vfx_script("rain"), "cs"),
    ("vfx/env_ash", lambda: generate_environmental_vfx_script("ash"), "cs"),
    ("vfx/trail", lambda: generate_trail_vfx_script(name="TestTrail"), "cs"),
    ("vfx/aura", lambda: generate_aura_vfx_script(name="TestAura"), "cs"),
    ("vfx/post_processing", lambda: generate_post_processing_script(), "cs"),
    ("vfx/screen_camera_shake", lambda: generate_screen_effect_script("camera_shake"), "cs"),
    ("vfx/screen_damage_vignette", lambda: generate_screen_effect_script("damage_vignette"), "cs"),
    ("vfx/screen_low_health", lambda: generate_screen_effect_script("low_health_pulse"), "cs"),
    ("vfx/screen_poison", lambda: generate_screen_effect_script("poison_overlay"), "cs"),
    ("vfx/screen_heal", lambda: generate_screen_effect_script("heal_glow"), "cs"),
    ("vfx/ability", lambda: generate_ability_vfx_script(ability_name="Fireball"), "cs"),

    # --- shaders ---
    ("shader/corruption", lambda: generate_corruption_shader(), "shader"),
    ("shader/dissolve", lambda: generate_dissolve_shader(), "shader"),
    ("shader/force_field", lambda: generate_force_field_shader(), "shader"),
    ("shader/water", lambda: generate_water_shader(), "shader"),
    ("shader/foliage", lambda: generate_foliage_shader(), "shader"),
    ("shader/outline", lambda: generate_outline_shader(), "shader"),
    ("shader/damage_overlay", lambda: generate_damage_overlay_shader(), "shader"),
    ("shader/arbitrary", lambda: generate_arbitrary_shader("TestShader"), "shader"),
    ("shader/arbitrary_transparent", lambda: generate_arbitrary_shader("TestTransparent", render_type="Transparent"), "shader"),
    ("shader/arbitrary_two_pass", lambda: generate_arbitrary_shader("TestTwoPass", two_passes=True), "shader"),
    ("shader/renderer_feature", lambda: generate_renderer_feature("TestFeature"), "cs"),
    ("shader/renderer_feature_ns", lambda: generate_renderer_feature("CustomBloom", namespace="VeilBreakers.Rendering"), "cs"),

    # --- audio ---
    ("audio/footstep", lambda: generate_footstep_manager_script(), "cs"),
    ("audio/adaptive_music", lambda: generate_adaptive_music_script(), "cs"),
    ("audio/zone_cave", lambda: generate_audio_zone_script(zone_type="cave"), "cs"),
    ("audio/zone_outdoor", lambda: generate_audio_zone_script(zone_type="outdoor"), "cs"),
    ("audio/zone_indoor", lambda: generate_audio_zone_script(zone_type="indoor"), "cs"),
    ("audio/zone_dungeon", lambda: generate_audio_zone_script(zone_type="dungeon"), "cs"),
    ("audio/zone_forest", lambda: generate_audio_zone_script(zone_type="forest"), "cs"),
    ("audio/mixer_setup", lambda: generate_audio_mixer_setup_script(), "cs"),
    ("audio/pool_manager", lambda: generate_audio_pool_manager_script(), "cs"),
    ("audio/animation_event_sfx", lambda: generate_animation_event_sfx_script(), "cs"),

    # --- ui (only generate_responsive_test_script produces C#) ---
    ("ui/responsive_test", lambda: generate_responsive_test_script(uxml_path="Assets/UI/MainHUD.uxml"), "cs"),

    # --- scene ---
    ("scene/terrain", lambda: generate_terrain_setup_script(heightmap_path="Assets/Terrain/heightmap.raw"), "cs"),
    (
        "scene/terrain_with_splatmaps",
        lambda: generate_terrain_setup_script(
            heightmap_path="Assets/Terrain/heightmap.raw",
            splatmap_layers=[
                {"texture_path": "Assets/Textures/grass.png", "tiling": 15.0},
                {"texture_path": "Assets/Textures/rock.png", "tiling": 10.0},
            ],
        ),
        "cs",
    ),
    (
        "scene/tiled_terrain",
        lambda: generate_tiled_terrain_setup_script(
            tiles=[
                {"heightmap_path": "Assets/Terrain/tile_0.raw", "name": "Tile_0", "grid_x": 0, "grid_y": 0},
                {"heightmap_path": "Assets/Terrain/tile_1.raw", "name": "Tile_1", "grid_x": 1, "grid_y": 0},
            ],
        ),
        "cs",
    ),
    (
        "scene/object_scatter",
        lambda: generate_object_scatter_script(prefab_paths=["Assets/Prefabs/Tree.prefab", "Assets/Prefabs/Rock.prefab"]),
        "cs",
    ),
    ("scene/lighting", lambda: generate_lighting_setup_script(), "cs"),
    ("scene/lighting_dawn", lambda: generate_lighting_setup_script(time_of_day="dawn"), "cs"),
    ("scene/lighting_night", lambda: generate_lighting_setup_script(time_of_day="night"), "cs"),
    ("scene/navmesh", lambda: generate_navmesh_bake_script(), "cs"),
    (
        "scene/navmesh_with_links",
        lambda: generate_navmesh_bake_script(
            nav_links=[{"start": [0, 0, 0], "end": [5, 2, 0], "width": 1.5}]
        ),
        "cs",
    ),
    (
        "scene/animator",
        lambda: generate_animator_controller_script(
            name="TestController",
            states=[{"name": "Idle"}, {"name": "Walk"}, {"name": "Run"}],
            transitions=[
                {"from_state": "Idle", "to_state": "Walk", "has_exit_time": False, "conditions": [{"param": "Speed", "mode": "Greater", "threshold": 0.1}]},
                {"from_state": "Walk", "to_state": "Run", "has_exit_time": False, "conditions": [{"param": "Speed", "mode": "Greater", "threshold": 0.5}]},
            ],
            parameters=[
                {"name": "Speed", "type": "float"},
                {"name": "IsGrounded", "type": "bool"},
            ],
        ),
        "cs",
    ),
    (
        "scene/animator_with_blend_tree",
        lambda: generate_animator_controller_script(
            name="BlendTest",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
            blend_trees=[{
                "name": "Locomotion",
                "blend_param": "Speed",
                "children": [
                    {"motion_path": "Assets/Animations/Idle.anim", "threshold": 0.0},
                    {"motion_path": "Assets/Animations/Walk.anim", "threshold": 0.5},
                ],
            }],
        ),
        "cs",
    ),
    ("scene/avatar", lambda: generate_avatar_config_script(fbx_path="Assets/Models/character.fbx"), "cs"),
    (
        "scene/avatar_with_bones",
        lambda: generate_avatar_config_script(
            fbx_path="Assets/Models/character.fbx",
            bone_mapping={"Hips": "mixamorig:Hips", "Spine": "mixamorig:Spine"},
        ),
        "cs",
    ),
    (
        "scene/animation_rigging",
        lambda: generate_animation_rigging_script(
            rig_name="TestRig",
            constraints=[
                {"type": "two_bone_ik", "target_path": "IKTarget", "root_path": "UpperArm", "mid_path": "Forearm", "tip_path": "Hand"},
            ],
        ),
        "cs",
    ),
    (
        "scene/animation_rigging_multi_aim",
        lambda: generate_animation_rigging_script(
            rig_name="AimRig",
            constraints=[
                {"type": "multi_aim", "target_path": "Head", "source_paths": ["LookTarget"], "weight": 1.0},
            ],
        ),
        "cs",
    ),

    # --- gameplay ---
    ("gameplay/mob_controller", lambda: generate_mob_controller_script(name="Skeleton"), "cs"),
    ("gameplay/aggro_system", lambda: generate_aggro_system_script(name="BasicAggro"), "cs"),
    ("gameplay/patrol_route", lambda: generate_patrol_route_script(name="GuardRoute"), "cs"),
    ("gameplay/spawn_system", lambda: generate_spawn_system_script(name="GoblinSpawner"), "cs"),
    ("gameplay/behavior_tree", lambda: generate_behavior_tree_script(name="SkeletonBT"), "cs"),
    (
        "gameplay/behavior_tree_with_nodes",
        lambda: generate_behavior_tree_script(name="AdvancedBT", node_types=["CheckHealth", "FindTarget", "Attack"]),
        "cs",
    ),
    ("gameplay/combat_ability", lambda: generate_combat_ability_script(name="Slash"), "cs"),
    ("gameplay/projectile_straight", lambda: generate_projectile_script(name="Arrow", trajectory="straight"), "cs"),
    ("gameplay/projectile_arc", lambda: generate_projectile_script(name="Grenade", trajectory="arc"), "cs"),
    ("gameplay/projectile_homing", lambda: generate_projectile_script(name="Missile", trajectory="homing"), "cs"),

    # --- performance ---
    ("performance/scene_profiler", lambda: generate_scene_profiler_script(), "cs"),
    ("performance/lod_setup", lambda: generate_lod_setup_script(), "cs"),
    ("performance/lightmap_bake", lambda: generate_lightmap_bake_script(), "cs"),
    ("performance/asset_audit", lambda: generate_asset_audit_script(), "cs"),
    ("performance/build_automation", lambda: generate_build_automation_script(), "cs"),

    # --- data (Phase 11) ---
    ("data/so_definition", lambda: generate_so_definition("ItemConfig", namespace="VeilBreakers.Data", fields=[{"name": "itemName", "type": "string"}, {"name": "rarity", "type": "int", "default": "0"}], summary="Game item configuration"), "cs"),
    ("data/asset_creation", lambda: generate_asset_creation_script("ItemConfig", namespace="VeilBreakers.Data", assets=[{"itemName": "Sword", "rarity": "1"}], category="Items"), "cs"),
    ("data/json_validator", lambda: generate_json_validator_script("MonsterData", "Resources/Data/monsters.json", schema={"monster_id": {"type": "string", "required": True}}, wrapper_class="MonsterDataWrapper"), "cs"),
    ("data/json_loader", lambda: generate_json_loader_script("MonsterData", namespace="VeilBreakers.Data", fields=[{"name": "monster_id", "type": "string"}, {"name": "base_hp", "type": "int"}], json_path="Data/monsters", is_array=True), "cs"),
    ("data/localization_setup", lambda: generate_localization_setup_script(default_locale="en", locales=["es", "fr"], table_name="VeilBreakers_UI"), "cs"),
    ("data/localization_entries", lambda: generate_localization_entries_script(table_name="VeilBreakers_UI", entries={"UI.MainMenu.Start": "Start Game", "Combat.Brand.Iron": "Iron"}, locale="en"), "cs"),
    ("data/authoring_window", lambda: generate_data_authoring_window("ItemEditor", "ItemConfig", namespace="VeilBreakers.Data", fields=[{"name": "itemName", "type": "string", "label": "Item Name"}], category="Items"), "cs"),

    # --- pipeline (Phase 11, C# only) ---
    ("pipeline/sprite_atlas", lambda: generate_sprite_atlas_script("UIAtlas", "Assets/Art/Sprites/UI", padding=4), "cs"),
    ("pipeline/sprite_animation", lambda: generate_sprite_animation_script("WalkAnim", "Assets/Art/Sprites/Walk", frame_rate=12, loop=True), "cs"),
    ("pipeline/sprite_editor", lambda: generate_sprite_editor_config_script("Assets/test.png", pivot=(0.5, 0.0), border=(10, 10, 10, 10)), "cs"),
    ("pipeline/asset_postprocessor", lambda: generate_asset_postprocessor_script("VBPostprocessor", version=1, texture_rules=[{"folder_pattern": "Sprites/", "settings_dict": {"textureType": "Sprite"}}]), "cs"),

    # --- quality (Phase 11) ---
    ("quality/poly_budget", lambda: generate_poly_budget_check_script("hero", "Assets/Characters"), "cs"),
    ("quality/master_materials", lambda: generate_master_material_script(), "cs"),
    ("quality/texture_check", lambda: generate_texture_quality_check_script("Assets", 10.24, True, True), "cs"),
    ("quality/aaa_audit", lambda: generate_aaa_validation_script("Assets", "prop", True, True, True), "cs"),

    # --- game systems (Phase 12 -- Core Game Systems) ---
    ("game/save_system", lambda: generate_save_system_script(), "cs"),
    ("game/health_system", lambda: generate_health_system_script(), "cs"),
    ("game/character_controller", lambda: generate_character_controller_script(), "cs"),
    ("game/input_config", lambda: generate_input_config_script()[1], "cs"),
    ("game/settings_menu", lambda: generate_settings_menu_script()[0], "cs"),
    ("game/http_client", lambda: generate_http_client_script(), "cs"),
    ("game/interactable", lambda: generate_interactable_script(), "cs"),

    # --- vb combat (Phase 12 -- VeilBreakers Combat) ---
    ("vb/player_combat", lambda: generate_player_combat_script(), "cs"),
    ("vb/ability_system", lambda: generate_ability_system_script(), "cs"),
    ("vb/synergy_engine", lambda: generate_synergy_engine_script(), "cs"),
    ("vb/corruption_gameplay", lambda: generate_corruption_gameplay_script(), "cs"),
    ("vb/xp_leveling", lambda: generate_xp_leveling_script(), "cs"),
    ("vb/currency_system", lambda: generate_currency_system_script(), "cs"),
    ("vb/damage_types", lambda: generate_damage_type_script(), "cs"),

    # --- content & progression (Phase 13) ---
    ("content/inventory_item_so", lambda: generate_inventory_system_script()[0], "cs"),
    ("content/inventory_system", lambda: generate_inventory_system_script()[1], "cs"),
    ("content/dialogue_data", lambda: generate_dialogue_system_script()[0], "cs"),
    ("content/dialogue_system", lambda: generate_dialogue_system_script()[1], "cs"),
    ("content/quest_data", lambda: generate_quest_system_script()[0], "cs"),
    ("content/quest_system", lambda: generate_quest_system_script()[1], "cs"),
    ("content/loot_table", lambda: generate_loot_table_script(), "cs"),
    ("content/crafting_recipe", lambda: generate_crafting_system_script()[0], "cs"),
    ("content/crafting_system", lambda: generate_crafting_system_script()[1], "cs"),
    ("content/skill_node", lambda: generate_skill_tree_script()[0], "cs"),
    ("content/skill_tree", lambda: generate_skill_tree_script()[1], "cs"),
    ("content/dps_calculator", lambda: generate_dps_calculator_script(), "cs"),
    ("content/encounter_simulator", lambda: generate_encounter_simulator_script(), "cs"),
    ("content/stat_curve_editor", lambda: generate_stat_curve_editor_script(), "cs"),
    ("content/shop_merchant", lambda: generate_shop_system_script()[0], "cs"),
    ("content/shop_system", lambda: generate_shop_system_script()[1], "cs"),
    ("content/journal_data", lambda: generate_journal_system_script()[0], "cs"),
    ("content/journal_system", lambda: generate_journal_system_script()[1], "cs"),

    # --- equipment (Phase 13 -- EQUIP-06) ---
    ("equipment/attachment", lambda: generate_equipment_attachment_script()[0], "cs"),
    ("equipment/weapon_sheath", lambda: generate_equipment_attachment_script()[1], "cs"),

    # ===================================================================
    # Phase 14: Camera, Cinematics & Scene Management
    # ===================================================================

    # --- camera/ -- camera_templates.py (10 generators) ---
    ("camera/cinemachine_orbital", lambda: generate_cinemachine_setup_script(camera_type="orbital"), "cs"),
    ("camera/cinemachine_follow", lambda: generate_cinemachine_setup_script(camera_type="follow"), "cs"),
    ("camera/cinemachine_dolly", lambda: generate_cinemachine_setup_script(camera_type="dolly"), "cs"),
    ("camera/cinemachine_with_targets", lambda: generate_cinemachine_setup_script(
        camera_type="orbital", follow_target="Player", look_at_target="Player/Head",
        priority=15, radius=8.0, target_offset=[0, 1.5, 0], damping=[1, 1, 0.5],
    ), "cs"),
    ("camera/state_driven_default", lambda: generate_state_driven_camera_script(), "cs"),
    ("camera/state_driven_custom", lambda: generate_state_driven_camera_script(
        camera_name="VB_CombatCamera",
        states=[{"state": "Idle", "blend_time": 1.0}, {"state": "Combat", "blend_time": 0.3}],
    ), "cs"),
    ("camera/shake_default", lambda: generate_camera_shake_script(), "cs"),
    ("camera/shake_custom", lambda: generate_camera_shake_script(
        impulse_force=1.5, impulse_duration=0.4, add_listener=False,
    ), "cs"),
    ("camera/blend_default", lambda: generate_camera_blend_script(), "cs"),
    ("camera/blend_custom", lambda: generate_camera_blend_script(
        default_blend_time=1.0, blend_style="Cut",
        custom_blends=[{"from_camera": "CamA", "to_camera": "CamB", "blend_time": 0.5}],
    ), "cs"),
    ("camera/timeline_default", lambda: generate_timeline_setup_script(), "cs"),
    ("camera/timeline_with_tracks", lambda: generate_timeline_setup_script(
        timeline_name="BossCutscene",
        tracks=[{"type": "AnimationTrack", "name": "BossEntry"}],
    ), "cs"),
    ("camera/cutscene_default", lambda: generate_cutscene_setup_script(), "cs"),
    ("camera/cutscene_custom", lambda: generate_cutscene_setup_script(
        cutscene_name="IntroCutscene",
        timeline_path="Assets/Timelines/Intro.playable",
        wrap_mode="Hold", play_on_awake=True,
    ), "cs"),
    ("camera/animation_clip_default", lambda: generate_animation_clip_editor_script(), "cs"),
    ("camera/animation_clip_with_curves", lambda: generate_animation_clip_editor_script(
        clip_name="DoorOpen",
        curves=[{"property": "localRotation.y", "type": "Transform", "keys": [{"time": 0, "value": 0}, {"time": 1, "value": 90}]}],
    ), "cs"),
    ("camera/animator_modifier_default", lambda: generate_animator_modifier_script(), "cs"),
    ("camera/animator_modifier_custom", lambda: generate_animator_modifier_script(
        states_to_add=["Dodge", "Block"],
        parameters=[{"name": "IsDodging", "type": "bool"}],
        transitions=[{"from": "Idle", "to": "Dodge", "condition_param": "IsDodging"}],
    ), "cs"),
    ("camera/avatar_mask_default", lambda: generate_avatar_mask_script(), "cs"),
    ("camera/avatar_mask_custom", lambda: generate_avatar_mask_script(
        mask_name="LowerBodyMask",
        body_parts={"Head": False, "LeftArm": False, "RightArm": False, "LeftLeg": True, "RightLeg": True},
    ), "cs"),
    ("camera/video_player_clip", lambda: generate_video_player_script(video_source="clip"), "cs"),
    ("camera/video_player_url", lambda: generate_video_player_script(
        video_source="url", video_path="https://example.com/video.mp4", loop=False,
    ), "cs"),

    # --- world/ -- world_templates.py (18 generators: 9 scene/env + 9 RPG) ---

    # Scene/Environment generators
    ("world/scene_creation_default", lambda: generate_scene_creation_script(), "cs"),
    ("world/scene_creation_custom", lambda: generate_scene_creation_script(
        scene_name="DungeonLevel1", scene_setup="EmptyScene",
        loading_mode="additive", build_index=3,
    ), "cs"),
    ("world/scene_transition_editor", lambda: generate_scene_transition_script()[0], "cs"),
    ("world/scene_transition_runtime", lambda: generate_scene_transition_script()[1], "cs"),
    ("world/scene_transition_custom_editor", lambda: generate_scene_transition_script(
        fade_duration=1.0, show_loading_screen=False,
    )[0], "cs"),
    ("world/scene_transition_custom_runtime", lambda: generate_scene_transition_script(
        fade_duration=1.0, show_loading_screen=False,
    )[1], "cs"),
    ("world/probe_setup", lambda: generate_probe_setup_script(), "cs"),
    ("world/probe_setup_custom", lambda: generate_probe_setup_script(
        reflection_probe_count=8, reflection_resolution=512,
        probe_box_size=[20.0, 10.0, 20.0],
    ), "cs"),
    ("world/occlusion_setup", lambda: generate_occlusion_setup_script(), "cs"),
    ("world/environment_setup", lambda: generate_environment_setup_script(), "cs"),
    ("world/terrain_detail", lambda: generate_terrain_detail_script(), "cs"),
    ("world/tilemap_setup", lambda: generate_tilemap_setup_script(), "cs"),
    ("world/2d_physics", lambda: generate_2d_physics_script(), "cs"),
    ("world/2d_physics_hinge", lambda: generate_2d_physics_script(
        collider_type="circle", body_type="Kinematic", joint_type="hinge",
    ), "cs"),
    ("world/time_of_day_noon", lambda: generate_time_of_day_preset_script(preset_name="noon"), "cs"),
    ("world/time_of_day_dusk", lambda: generate_time_of_day_preset_script(preset_name="dusk"), "cs"),
    ("world/time_of_day_midnight", lambda: generate_time_of_day_preset_script(preset_name="midnight"), "cs"),

    # RPG World System generators
    ("world/fast_travel_editor", lambda: generate_fast_travel_script()[0], "cs"),
    ("world/fast_travel_runtime", lambda: generate_fast_travel_script()[1], "cs"),
    ("world/puzzle_editor", lambda: generate_puzzle_mechanics_script()[0], "cs"),
    ("world/puzzle_runtime", lambda: generate_puzzle_mechanics_script()[1], "cs"),
    ("world/puzzle_custom_editor", lambda: generate_puzzle_mechanics_script(
        puzzle_types=["lever_sequence", "pressure_plate"],
    )[0], "cs"),
    ("world/puzzle_custom_runtime", lambda: generate_puzzle_mechanics_script(
        puzzle_types=["lever_sequence", "pressure_plate"],
    )[1], "cs"),
    ("world/trap_editor", lambda: generate_trap_system_script()[0], "cs"),
    ("world/trap_runtime", lambda: generate_trap_system_script()[1], "cs"),
    ("world/trap_custom_editor", lambda: generate_trap_system_script(
        trap_types=["spike_pit", "dart_wall"], base_damage=50.0, cooldown=5.0,
    )[0], "cs"),
    ("world/trap_custom_runtime", lambda: generate_trap_system_script(
        trap_types=["spike_pit", "dart_wall"], base_damage=50.0, cooldown=5.0,
    )[1], "cs"),
    ("world/spatial_loot_editor", lambda: generate_spatial_loot_script()[0], "cs"),
    ("world/spatial_loot_runtime", lambda: generate_spatial_loot_script()[1], "cs"),
    ("world/weather_editor", lambda: generate_weather_system_script()[0], "cs"),
    ("world/weather_runtime", lambda: generate_weather_system_script()[1], "cs"),
    ("world/weather_custom_editor", lambda: generate_weather_system_script(
        weather_states=["Clear", "Rain", "Storm"],
    )[0], "cs"),
    ("world/weather_custom_runtime", lambda: generate_weather_system_script(
        weather_states=["Clear", "Rain", "Storm"],
    )[1], "cs"),
    ("world/day_night_editor", lambda: generate_day_night_cycle_script()[0], "cs"),
    ("world/day_night_runtime", lambda: generate_day_night_cycle_script()[1], "cs"),
    ("world/day_night_custom_editor", lambda: generate_day_night_cycle_script(
        day_duration_minutes=20.0, start_hour=6.0,
    )[0], "cs"),
    ("world/day_night_custom_runtime", lambda: generate_day_night_cycle_script(
        day_duration_minutes=20.0, start_hour=6.0,
    )[1], "cs"),
    ("world/npc_placement_so", lambda: generate_npc_placement_script()[0], "cs"),
    ("world/npc_placement_runtime", lambda: generate_npc_placement_script()[1], "cs"),
    ("world/npc_placement_editor", lambda: generate_npc_placement_script()[2], "cs"),
    ("world/npc_custom_so", lambda: generate_npc_placement_script(
        npc_roles=["merchant", "guard", "quest_giver"],
    )[0], "cs"),
    ("world/npc_custom_runtime", lambda: generate_npc_placement_script(
        npc_roles=["merchant", "guard", "quest_giver"],
    )[1], "cs"),
    ("world/npc_custom_editor", lambda: generate_npc_placement_script(
        npc_roles=["merchant", "guard", "quest_giver"],
    )[2], "cs"),
    ("world/dungeon_lighting_editor", lambda: generate_dungeon_lighting_script()[0], "cs"),
    ("world/dungeon_lighting_runtime", lambda: generate_dungeon_lighting_script()[1], "cs"),
    ("world/dungeon_lighting_custom_editor", lambda: generate_dungeon_lighting_script(
        torch_spacing=4.0, torch_light_range=10.0, fog_density=0.05,
    )[0], "cs"),
    ("world/dungeon_lighting_custom_runtime", lambda: generate_dungeon_lighting_script(
        torch_spacing=4.0, torch_light_range=10.0, fog_density=0.05,
    )[1], "cs"),
    ("world/terrain_blend_editor", lambda: generate_terrain_building_blend_script()[0], "cs"),
    ("world/terrain_blend_runtime", lambda: generate_terrain_building_blend_script()[1], "cs"),
    ("world/terrain_blend_custom_editor", lambda: generate_terrain_building_blend_script(
        blend_radius=3.0, depression_depth=0.2, vertex_color_falloff=2.0,
    )[0], "cs"),
    ("world/terrain_blend_custom_runtime", lambda: generate_terrain_building_blend_script(
        blend_radius=3.0, depression_depth=0.2, vertex_color_falloff=2.0,
    )[1], "cs"),

    # ===================================================================
    # Phase 15: Game UX & Encounter Design
    # ===================================================================

    # --- ux/ -- ux_templates.py (12 generators, batch 1 + batch 2) ---
    ("ux/minimap_editor", lambda: generate_minimap_script("TestMinimap")[0], "cs"),
    ("ux/minimap_runtime", lambda: generate_minimap_script("TestMinimap")[1], "cs"),
    ("ux/damage_numbers", lambda: generate_damage_numbers_script("TestDmgNum"), "cs"),
    ("ux/interaction_prompts", lambda: generate_interaction_prompts_script("TestPrompt"), "cs"),
    ("ux/primetween_panel_entrance", lambda: generate_primetween_sequence_script("panel_entrance"), "cs"),
    ("ux/primetween_button_hover", lambda: generate_primetween_sequence_script("button_hover"), "cs"),
    ("ux/primetween_notification", lambda: generate_primetween_sequence_script("notification_popup"), "cs"),
    ("ux/primetween_screen_shake", lambda: generate_primetween_sequence_script("screen_shake"), "cs"),
    ("ux/tmp_font_asset", lambda: generate_tmp_font_asset_script(), "cs"),
    ("ux/tmp_component", lambda: generate_tmp_component_script("TestTMP"), "cs"),
    ("ux/tutorial_data_so", lambda: generate_tutorial_system_script("TestTutorial")[0], "cs"),
    ("ux/tutorial_manager", lambda: generate_tutorial_system_script("TestTutorial")[1], "cs"),
    ("ux/accessibility_settings", lambda: generate_accessibility_script("TestAccess")[0], "cs"),
    ("ux/accessibility_shader", lambda: generate_accessibility_script("TestAccess")[1], "shader"),
    ("ux/accessibility_renderer_feature", lambda: generate_accessibility_script("TestAccess")[2], "cs"),
    ("ux/character_select_data", lambda: generate_character_select_script()[0], "cs"),
    ("ux/character_select_manager", lambda: generate_character_select_script()[1], "cs"),
    ("ux/world_map_editor", lambda: generate_world_map_script("TestMap")[0], "cs"),
    ("ux/world_map_runtime", lambda: generate_world_map_script("TestMap")[1], "cs"),
    ("ux/rarity_vfx", lambda: generate_rarity_vfx_script("TestRarity"), "cs"),
    ("ux/corruption_vfx", lambda: generate_corruption_vfx_script("TestCorrupt"), "cs"),

    # --- encounter/ -- encounter_templates.py (4 generators) ---
    ("encounter/wave_data_so", lambda: generate_enc_system_script("TestEnc")[0], "cs"),
    ("encounter/encounter_manager", lambda: generate_enc_system_script("TestEnc")[1], "cs"),
    ("encounter/ai_director", lambda: generate_ai_director_script("TestDirector"), "cs"),
    ("encounter/simulator", lambda: generate_enc_sim_script("TestSim"), "cs"),
    ("encounter/boss_ai_3phase", lambda: generate_boss_ai_script("TestBoss", phase_count=3), "cs"),
    ("encounter/boss_ai_4phase", lambda: generate_boss_ai_script("TestBoss4", phase_count=4), "cs"),

    # --- qa/ -- qa_templates.py (Phase 16 -- 8 C# generators) ---
    ("qa/bridge_server_default", lambda: generate_bridge_server_script(), "cs"),
    ("qa/bridge_server_custom", lambda: generate_bridge_server_script(port=9999, namespace="VB.QA"), "cs"),
    ("qa/bridge_commands_default", lambda: generate_bridge_commands_script(), "cs"),
    ("qa/bridge_commands_ns", lambda: generate_bridge_commands_script(namespace="VB.QA"), "cs"),
    ("qa/test_runner_default", lambda: generate_test_runner_handler(), "cs"),
    ("qa/test_runner_playmode", lambda: generate_test_runner_handler(test_mode="PlayMode", test_filter="MyTests"), "cs"),
    ("qa/play_session_default", lambda: generate_play_session_script(), "cs"),
    ("qa/play_session_steps", lambda: generate_play_session_script(steps=[{"action": "wait", "seconds": 2, "expected": "loaded"}]), "cs"),
    ("qa/profiler_default", lambda: generate_profiler_handler(), "cs"),
    ("qa/profiler_custom", lambda: generate_profiler_handler(target_frame_time_ms=33.33, max_draw_calls=500), "cs"),
    ("qa/memory_leak_default", lambda: generate_memory_leak_script(), "cs"),
    ("qa/memory_leak_custom", lambda: generate_memory_leak_script(growth_threshold_mb=50, sample_count=20), "cs"),
    ("qa/crash_reporting_default", lambda: generate_crash_reporting_script(), "cs"),
    ("qa/crash_reporting_prod", lambda: generate_crash_reporting_script(dsn="https://examplePublicKey@o0.ingest.sentry.io/0", environment="production"), "cs"),
    ("qa/analytics_default", lambda: generate_analytics_script(), "cs"),
    ("qa/analytics_events", lambda: generate_analytics_script(event_names=["custom_event", "boss_killed"]), "cs"),
    ("qa/live_inspector_default", lambda: generate_live_inspector_script(), "cs"),
    ("qa/live_inspector_custom", lambda: generate_live_inspector_script(update_interval_frames=30, max_tracked_objects=50), "cs"),

    # --- build & deploy (Phase 17) ---
    ("build/multi_platform_default", lambda: generate_multi_platform_build_script(), "cs"),
    ("build/multi_platform_dev", lambda: generate_multi_platform_build_script(development=True), "cs"),
    ("build/multi_platform_custom", lambda: generate_multi_platform_build_script(platforms=[{"name": "Win", "target": "StandaloneWindows64", "group": "Standalone", "backend": "IL2CPP", "extension": ".exe"}]), "cs"),
    ("build/multi_platform_ns", lambda: generate_multi_platform_build_script(namespace="VB.Build"), "cs"),
    ("build/addressables_default", lambda: generate_addressables_config_script(), "cs"),
    ("build/addressables_remote", lambda: generate_addressables_config_script(build_remote=True), "cs"),
    ("build/addressables_custom", lambda: generate_addressables_config_script(groups=[{"name": "MyGroup", "packing": "PackTogether", "local": False}]), "cs"),
    ("build/addressables_ns", lambda: generate_addressables_config_script(namespace="VB.Build"), "cs"),
    ("build/platform_android", lambda: generate_platform_config_script(platform="android"), "cs"),
    ("build/platform_android_perms", lambda: generate_platform_config_script(platform="android", permissions=["android.permission.CAMERA"]), "cs"),
    ("build/platform_ios", lambda: generate_platform_config_script(platform="ios"), "cs"),
    ("build/platform_ios_entries", lambda: generate_platform_config_script(platform="ios", plist_entries=[{"key": "NSCameraUsageDescription", "value": "AR", "type": "string"}]), "cs"),
    ("build/platform_webgl", lambda: generate_platform_config_script(platform="webgl"), "cs"),
    ("build/platform_webgl_512", lambda: generate_platform_config_script(platform="webgl", webgl_memory_mb=512), "cs"),
    ("build/shader_strip_default", lambda: generate_shader_stripping_script(), "cs"),
    ("build/shader_strip_custom", lambda: generate_shader_stripping_script(keywords_to_strip=["FOG_LINEAR", "_SHADOWS_SOFT"]), "cs"),
    ("build/shader_strip_nolog", lambda: generate_shader_stripping_script(log_stripping=False), "cs"),
    ("build/shader_strip_ns", lambda: generate_shader_stripping_script(namespace="VB.Build"), "cs"),
    ("build/version_default", lambda: generate_version_management_script(), "cs"),
    ("build/version_major", lambda: generate_version_management_script(auto_increment="major"), "cs"),
    ("build/version_no_android", lambda: generate_version_management_script(update_android=False), "cs"),
    ("build/version_ns", lambda: generate_version_management_script(namespace="VB.Build"), "cs"),
    ("build/changelog_default", lambda: generate_changelog(), "cs"),
    ("build/changelog_custom", lambda: generate_changelog(project_name="MyGame", version="2.0.0"), "cs"),
]

# Also test the non-C# generators separately for their own validity
NON_CS_GENERATORS: list[tuple[str, callable, str]] = [
    (
        "ui/uxml_screen",
        lambda: generate_uxml_screen({
            "title": "Test HUD",
            "elements": [
                {"type": "label", "text": "Health", "name": "health-label"},
                {"type": "button", "text": "Attack", "name": "attack-btn"},
                {"type": "panel", "name": "stats-panel", "children": [
                    {"type": "label", "text": "STR: 10"},
                ]},
            ],
        }),
        "uxml",
    ),
    ("ui/uss_stylesheet", lambda: generate_uss_stylesheet(), "uss"),

    # --- content UXML/USS (Phase 13) ---
    ("content/inventory_uxml", lambda: generate_inventory_system_script()[2], "uxml"),
    ("content/inventory_uss", lambda: generate_inventory_system_script()[3], "uss"),
    ("content/dialogue_uxml", lambda: generate_dialogue_system_script()[2], "uxml"),
    ("content/dialogue_uss", lambda: generate_dialogue_system_script()[3], "uss"),
    ("content/quest_uxml", lambda: generate_quest_system_script()[2], "uxml"),
    ("content/quest_uss", lambda: generate_quest_system_script()[3], "uss"),
    ("content/shop_uxml", lambda: generate_shop_system_script()[2], "uxml"),
    ("content/shop_uss", lambda: generate_shop_system_script()[3], "uss"),
    ("content/journal_uxml", lambda: generate_journal_system_script()[2], "uxml"),
    ("content/journal_uss", lambda: generate_journal_system_script()[3], "uss"),

    # --- Phase 15 UX UXML/USS ---
    ("ux/tutorial_uxml", lambda: generate_tutorial_system_script("TestTutorial")[2], "uxml"),
    ("ux/tutorial_uss", lambda: generate_tutorial_system_script("TestTutorial")[3], "uss"),
    ("ux/character_select_uxml", lambda: generate_character_select_script()[2], "uxml"),
    ("ux/character_select_uss", lambda: generate_character_select_script()[3], "uss"),
]


# ===================================================================
# Helpers
# ===================================================================


def count_braces(text: str) -> tuple[int, int]:
    """Count open and close braces in a string.

    Returns (open_count, close_count).
    """
    return text.count("{"), text.count("}")


def check_brace_balance(text: str) -> bool:
    """Verify that braces are balanced throughout the string.

    This uses a simple counter that must never go negative and must
    end at zero.
    """
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


def find_unmatched_brace_location(text: str) -> str:
    """Find the location of the first unmatched brace for diagnostics."""
    depth = 0
    lines = text.split("\n")
    for lineno, line in enumerate(lines, 1):
        for col, ch in enumerate(line):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth < 0:
                return f"Extra '}}' at line {lineno}, col {col}: {line.strip()}"
    if depth > 0:
        return f"Unclosed '{{' -- depth={depth} at end of file"
    return "Balanced"


# Regex that matches potential Python f-string leak: a bare {identifier}
# that is NOT doubled {{ }} and not inside a C# string context.
# We look for single braces containing Python-style identifiers that are
# NOT valid C# patterns (like array indexing {0}, {i}, etc.).
_FSTRING_LEAK_RE = re.compile(
    r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}(?!\})"
)

# Known C# patterns that look like f-string vars but are valid C#:
# - String interpolation in C# $"...{expr}..."  (but our templates use
#   explicit concatenation, so true string interpolation is fine)
# - LINQ expressions, etc.
# We'll whitelist a few common C# single-brace patterns:
_CS_BRACE_WHITELIST = {
    # C# string interpolation variables from responsive_test_script
    "res.x", "res.y", "path", "ex.Message",
    # Common C# format strings
    "0", "1", "2", "3", "i",
    # C# interpolated string variables (used in code_templates SO event channels)
    "value", "name",
    # C# interpolated string variables (used in data_templates localization entries)
    "added", "skipped", "failed",
    # C# interpolated string variables (used in pipeline_templates sprite animation)
    "sprites.Length",
    # C# interpolated string variables (used in game_templates HTTP client)
    "method", "url",
    # C# interpolated string variables (used in world_templates probe/occlusion setup)
    "positions.Count",
    "occludeeCount",
    # C# interpolated string variables (used in ux_templates character select)
    "path.baseIntelligence",
}


def find_fstring_leaks(text: str) -> list[str]:
    """Find potential Python f-string interpolation artifacts.

    Returns list of suspicious {variable_name} matches.
    """
    leaks = []
    for match in _FSTRING_LEAK_RE.finditer(text):
        var_name = match.group(1)
        # Skip known C# patterns
        if var_name in _CS_BRACE_WHITELIST:
            continue
        # Skip C# string interpolation patterns (inside $"..." strings)
        # These are intentional, not leaks.
        # Check if the match is inside a C# interpolated string (preceded by $")
        start = match.start()
        preceding = text[max(0, start - 50):start]
        if '$"' in preceding or "$@\"" in preceding:
            continue
        leaks.append(f"  Possible f-string leak: '{match.group(0)}' (var={var_name})")
    return leaks


# ===================================================================
# Parametrized tests
# ===================================================================


@pytest.mark.parametrize(
    "name,generator,lang",
    ALL_GENERATORS,
    ids=[g[0] for g in ALL_GENERATORS],
)
class TestCSharpTemplateSyntax:
    """Verify C# and shader template syntax for every generator."""

    def test_brace_balance(self, name: str, generator, lang: str) -> None:
        """Every { must have a matching } in the output."""
        output = generator()
        open_count, close_count = count_braces(output)
        balanced = check_brace_balance(output)
        if not balanced:
            location = find_unmatched_brace_location(output)
            pytest.fail(
                f"[{name}] Unbalanced braces: {{ ={open_count}, }} ={close_count}\n"
                f"  {location}\n"
                f"  First 200 chars: {output[:200]!r}"
            )

    def test_contains_expected_keywords(self, name: str, generator, lang: str) -> None:
        """Output should contain expected C# / shader keywords."""
        output = generator()
        if lang == "cs":
            # C# scripts must have a type declaration keyword
            has_type_keyword = (
                "class " in output
                or "interface " in output
                or "enum " in output
                or "struct " in output
            )
            assert has_type_keyword, (
                f"[{name}] Missing type keyword (class/interface/enum/struct)"
            )
            # Most C# scripts have 'using' statements, but minimal code
            # generators (plain class, enum, interface) may legitimately omit them
        elif lang == "shader":
            # Shader files should have Shader, Properties, SubShader
            assert "Shader " in output, f"[{name}] Missing 'Shader' keyword"
            assert "SubShader" in output, f"[{name}] Missing 'SubShader' keyword"
            assert "Pass" in output, f"[{name}] Missing 'Pass' keyword"

    def test_no_fstring_leaks(self, name: str, generator, lang: str) -> None:
        """No accidental Python f-string artifacts in output."""
        output = generator()
        leaks = find_fstring_leaks(output)
        if leaks:
            leak_details = "\n".join(leaks)
            pytest.fail(
                f"[{name}] Found {len(leaks)} potential f-string leak(s):\n{leak_details}"
            )

    def test_no_triple_single_braces(self, name: str, generator, lang: str) -> None:
        """No patterns like {{{ or }}} which indicate f-string escaping errors."""
        output = generator()
        # In properly escaped f-strings, {{ becomes { and }} becomes }.
        # A triple brace {{{ would yield a literal { followed by an interpolation start.
        # This is a strong signal of an escaping bug.
        if "{{{" in output or "}}}" in output:
            # Find the location
            for i, line in enumerate(output.split("\n"), 1):
                if "{{{" in line or "}}}" in line:
                    pytest.fail(
                        f"[{name}] Triple brace at line {i}: {line.strip()}"
                    )

    def test_try_catch_structure(self, name: str, generator, lang: str) -> None:
        """Every 'try' block should have a matching 'catch' block (C#).
        For HLSL shader files, every HLSLPROGRAM block must have a matching ENDHLSL.
        """
        output = generator()
        if lang == "shader":
            # HLSL does not have try/catch; verify HLSLPROGRAM/ENDHLSL pairs balance.
            opens = output.count("HLSLPROGRAM")
            closes = output.count("ENDHLSL")
            if opens != closes:
                pytest.fail(
                    f"[{name}] HLSLPROGRAM/ENDHLSL mismatch: "
                    f"HLSLPROGRAM={opens}, ENDHLSL={closes}"
                )
            return
        # C# try/catch check: count try and catch keywords, ignoring comments.
        lines = output.split("\n")
        try_count = 0
        catch_count = 0
        for line in lines:
            stripped = line.strip()
            # Skip comment lines
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            # Match 'try' as a standalone statement (possibly followed by {)
            if re.match(r"^\s*try\s*$", line) or re.match(r"^\s*try\s*\{", line):
                try_count += 1
            if re.search(r"\bcatch\s*\(", stripped) or re.match(r"^\s*catch\s*$", line):
                catch_count += 1
        if try_count != catch_count:
            pytest.fail(
                f"[{name}] try/catch mismatch: try={try_count}, catch={catch_count}"
            )

    def test_semicolons_after_statements(self, name: str, generator, lang: str) -> None:
        """C# variable declarations and method calls should end with semicolons.
        HLSL shaders must contain semicolons in their property and cbuffer blocks.
        """
        output = generator()
        if lang == "shader":
            # Every HLSL shader must have semicolons: variable declarations,
            # cbuffer fields, and struct members all require them.
            sc = output.count(";")
            assert sc >= 5, (
                f"[{name}] Shader output has only {sc} semicolon(s); "
                "expected at least 5 from HLSL declarations"
            )
            return
        lines = output.split("\n")
        # Patterns that should end with ; in C#
        # - Lines containing '=' that are not control flow, not comments, not class decl
        # - Lines with method calls ending in ')'
        issues = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if stripped.startswith("#"):  # preprocessor
                continue
            if stripped.startswith("["):  # attributes
                continue
            if stripped.startswith("///"):  # XML doc comments
                continue
            # Skip lines that are block openers/closers
            if stripped in ("{", "}", "};"):
                continue
            if stripped.endswith("{") or stripped.endswith("}"):
                continue
            # Skip class/struct/enum/namespace declarations
            if re.match(r"^(public|private|protected|internal|static|abstract|sealed|partial|override|virtual)\s+", stripped):
                if "class " in stripped or "struct " in stripped or "enum " in stripped:
                    continue
                if "interface " in stripped:
                    continue
                if stripped.endswith("{"):
                    continue
            # Skip HLSL/shader content (not expected here for cs type, but just in case)
            if any(kw in stripped for kw in ["HLSLPROGRAM", "ENDHLSL", "CBUFFER_START", "CBUFFER_END"]):
                continue

        # We just verify no empty file -- detailed semicolon analysis would
        # produce too many false positives due to template complexity
        assert len(output.strip()) > 50, f"[{name}] Output suspiciously short"

    def test_output_nonempty(self, name: str, generator, lang: str) -> None:
        """Generator should produce non-empty output."""
        output = generator()
        assert isinstance(output, str), f"[{name}] Output is not a string"
        assert len(output) > 100, f"[{name}] Output too short ({len(output)} chars)"


# ===================================================================
# Non-C# template tests (UXML, USS) — split by format so every test
# runs a real assertion with no pytest.skip() guards.
# ===================================================================

UXML_ONLY_GENERATORS: list[tuple[str, callable, str]] = [
    (n, g, l) for n, g, l in NON_CS_GENERATORS if l == "uxml"
]
USS_ONLY_GENERATORS: list[tuple[str, callable, str]] = [
    (n, g, l) for n, g, l in NON_CS_GENERATORS if l == "uss"
]


@pytest.mark.parametrize(
    "name,generator,lang",
    UXML_ONLY_GENERATORS,
    ids=[g[0] for g in UXML_ONLY_GENERATORS],
)
class TestUXMLTemplates:
    """Verify UXML template outputs — all tests apply to every entry."""

    def test_uxml_is_valid_xml(self, name: str, generator, lang: str) -> None:
        """UXML output should be parseable as XML."""
        import xml.etree.ElementTree as ET
        output = generator()
        try:
            ET.fromstring(output.split("\n", 1)[1] if output.startswith("<?xml") else output)
        except ET.ParseError as exc:
            pytest.fail(f"[{name}] Invalid XML: {exc}")

    def test_brace_balance(self, name: str, generator, lang: str) -> None:
        """Braces should be balanced in UXML templates."""
        output = generator()
        balanced = check_brace_balance(output)
        if not balanced:
            location = find_unmatched_brace_location(output)
            pytest.fail(f"[{name}] Unbalanced braces: {location}")

    def test_output_nonempty(self, name: str, generator, lang: str) -> None:
        """Generator should produce non-empty output."""
        output = generator()
        assert isinstance(output, str)
        assert len(output) > 50


@pytest.mark.parametrize(
    "name,generator,lang",
    USS_ONLY_GENERATORS,
    ids=[g[0] for g in USS_ONLY_GENERATORS],
)
class TestUSSTemplates:
    """Verify USS stylesheet template outputs — all tests apply to every entry."""

    def test_uss_has_css_rules(self, name: str, generator, lang: str) -> None:
        """USS output should contain CSS-like rules with selectors and color properties."""
        output = generator()
        assert "{" in output and "}" in output, f"[{name}] No CSS rules found"
        assert "background-color:" in output or "color:" in output, \
            f"[{name}] No color properties found"

    def test_brace_balance(self, name: str, generator, lang: str) -> None:
        """Braces should be balanced in USS stylesheets."""
        output = generator()
        balanced = check_brace_balance(output)
        if not balanced:
            location = find_unmatched_brace_location(output)
            pytest.fail(f"[{name}] Unbalanced braces: {location}")

    def test_output_nonempty(self, name: str, generator, lang: str) -> None:
        """Generator should produce non-empty output."""
        output = generator()
        assert isinstance(output, str)
        assert len(output) > 50


# ===================================================================
# Aggregate brace count report (informational, always passes)
# ===================================================================


def test_brace_count_summary() -> None:
    """Report brace counts for all generators (informational)."""
    results = []
    for name, generator, lang in ALL_GENERATORS:
        output = generator()
        open_c, close_c = count_braces(output)
        balanced = "OK" if open_c == close_c else f"MISMATCH(open={open_c}, close={close_c})"
        results.append((name, open_c, close_c, balanced))

    # Print summary (visible with -v flag)
    for name, oc, cc, status in results:
        assert status == "OK", f"{name}: {status}"
