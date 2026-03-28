# VeilBreakers MCP Toolkit -- Claude Code Instructions

You are the AI game development assistant for **VeilBreakers**, a dark fantasy action RPG. You have 37 compound MCP tools (15 Blender, 22 Unity) that give you direct control over both applications.

## Project Structure

```
Tools/mcp-toolkit/           # MCP server source
  src/veilbreakers_mcp/
    blender_server.py        # 15 Blender compound tools
    unity_server.py          # 22 Unity compound tools
  blender_addon/             # Blender socket addon (handlers/)
  tests/                     # pytest suite
.mcp.json                    # MCP server config (vb-blender, vb-unity)
.planning/                   # Phase plans, research, state tracking
```

## Tool Architecture

All tools use a **compound pattern**: one tool name per domain, `action` param selects the operation. This gives 350 operations across 37 tools.

- **Blender tools** connect via TCP to Blender (localhost:9876). Most mutations return viewport screenshots.
- **Unity tools** generate C# editor scripts, write to Unity project, return `next_steps` for compile+execute.

## Blender Server Tools (vb-blender)

### blender_scene
Actions: `inspect` | `clear` | `configure` | `list_objects`
- configure: `render_engine`, `fps`, `unit_scale`

### blender_object
Actions: `create` | `modify` | `delete` | `duplicate` | `list`
- create: `mesh_type` (cube/sphere/cylinder/plane/cone/torus/monkey), `position`, `rotation`, `scale`
- modify/delete/duplicate: `name` required

### blender_material
Actions: `create` | `assign` | `modify` | `list`
- `name`, `object_name`, `base_color` [r,g,b,a], `metallic`, `roughness`

### blender_viewport
Actions: `screenshot` | `contact_sheet` | `set_shading` | `navigate`
- contact_sheet: `object_name` required, returns multi-angle composite
- set_shading: `shading_type` (WIREFRAME/SOLID/MATERIAL/RENDERED)
- navigate: `camera_position`, `camera_target`

### blender_execute
Direct Blender Python execution. `code` param is AST-validated.
- Allowed: bpy, mathutils, bmesh, math, random, json
- Blocked: os, sys, subprocess, socket, exec, eval, getattr, open

### blender_export
`export_format` (fbx/gltf), `filepath`, `selected_only`, `apply_modifiers`

### blender_mesh
Actions: `analyze` | `repair` | `game_check` | `select` | `edit` | `boolean` | `retopo` | `sculpt` | `sculpt_brush` | `dyntopo` | `voxel_remesh` | `face_sets` | `multires`
- analyze: A-F topology grading
- repair: remove doubles, fix normals, fill holes (`merge_distance`, `max_hole_sides`)
- game_check: `poly_budget`, `platform`
- select: by `material_index`/`material_name`/`vertex_group`/`face_normal_direction`/`loose_parts`
- edit: `operation` (extrude/inset/mirror/separate/join), `offset`, `thickness`, `axis`
- boolean: `cutter_name`, `operation` (DIFFERENCE/UNION/INTERSECT)
- retopo: `target_faces`, `preserve_sharp`, `use_symmetry`
- sculpt: `operation` (smooth/inflate/flatten/crease), `strength`, `iterations`
- sculpt_brush: Advanced sculpt brush operations (clay/pinch/snake_hook/grab), `brush_type`, `radius`, `falloff`
- dyntopo: Dynamic topology sculpting, `detail_size`, `detail_method`
- voxel_remesh: Voxel-based remesh, `voxel_size`
- face_sets: Create/modify face sets for sculpt masking
- multires: Multires modifier operations, `levels`

### blender_uv
Actions: `analyze` | `unwrap` | `unwrap_blender` | `pack` | `lightmap` | `equalize` | `export_layout` | `set_layer` | `ensure_xatlas`
- unwrap: xatlas-based, `padding`, `resolution`, `rotate_charts`
- unwrap_blender: `method` (smart_project/angle_based), `angle_limit`
- lightmap: separate UV2 for Unity
- equalize: texel density equalization with `target_density`

### blender_texture
Actions: `create_pbr` | `mask_region` | `inpaint` | `hsv_adjust` | `blend_seams` | `generate_wear` | `bake` | `upscale` | `make_tileable` | `validate` | `delight` | `validate_palette`
- create_pbr: full node tree with `name`, `texture_dir`, `texture_size`
- bake: `bake_type` (COMBINED/NORMAL/AO/etc.), `image_name`, `samples`, `source_object`
- upscale: Real-ESRGAN, `image_path`, `scale`, `model`
- inpaint: fal.ai, `image_path`, `mask_path`, `prompt`
- delight: Remove baked-in lighting from albedo texture (AAA-01)
- validate_palette: Validate dark fantasy palette rules on albedo texture (AAA-03)

### asset_pipeline
Actions: `generate_3d` | `generate_building` | `generate_terrain_mesh` | `compose_map` | `compose_interior` | `cleanup` | `generate_lods` | `validate_export` | `tag_metadata` | `batch_process` | `catalog_query` | `catalog_add` | `generate_weapon` | `split_character` | `fit_armor` | `render_equipment_icon` | `import_model` | `import_and_process` | `full_pipeline` | `generate_and_process` | `inspect_external_toolchain` | `configure_external_toolchain`
- generate_3d: Tripo3D from `prompt` or `image_path` (requires API credits)
- generate_building: Tripo-powered architecture with dark fantasy presets, `building_type` (tavern/castle/cathedral/tower/house/shop/ruin/gate/bridge/wall_section/dungeon_entrance/shrine), `building_style` (dark_fantasy/gothic/medieval/elven/dwarven/corrupted), `building_size`
- generate_terrain_mesh: Procedural terrain in Blender, `terrain_preset` (mountains/hills/plains/canyon/volcanic/coastal/swamp), `terrain_size`, `terrain_resolution`, `terrain_height_scale`, `terrain_erosion`
- compose_map: **Full map orchestration** — single `map_spec` dict chains: terrain→water→rivers→roads→locations(town/castle/dungeon/cave/ruins/boss_arena)→biome paint→vegetation→props→interiors. Returns Unity next_steps for lighting/weather/atmosphere/navmesh.
- compose_interior: **Walkable interior orchestration** — single `interior_spec` dict chains: linked room shells→door triggers→occlusion zones→per-room geometry→storytelling props→Tripo prop generation queue. Supports room types: tavern_hall, kitchen, bedroom, storage, throne_room, library, forge, chapel, prison.
- import_model: Import local GLB/FBX/OBJ file into Blender (use for Tripo Studio downloads)
- import_and_process: Import local file + run full cleanup/material/rig/LOD/export pipeline
- cleanup: auto repair + UV + PBR on AI model
- generate_lods: LOD chain with `ratios`
- batch_process: `object_names`, `steps`
- generate_weapon: Generate parametric weapon mesh (EQUIP-01), `weapon_type`, `style`
- split_character: Split rigged character into modular equipment parts (EQUIP-03)
- fit_armor: Fit armor mesh to character body via shrinkwrap (EQUIP-04)
- render_equipment_icon: Render transparent equipment preview icon (EQUIP-05)

### concept_art
Actions: `generate` | `extract_palette` | `style_board` | `silhouette_test`
- generate: fal.ai FLUX, `prompt`, `style`, `width`, `height`
- silhouette_test: readability at game distances, `threshold`, `distances`

### blender_rig
Actions: `analyze_mesh` | `apply_template` | `build_custom` | `setup_facial` | `setup_ik` | `setup_spring_bones` | `auto_weight` | `test_deformation` | `validate` | `fix_weights` | `setup_ragdoll` | `retarget` | `add_shape_keys`
- apply_template: `template` (humanoid/quadruped/bird/etc.)
- setup_ik: `bone_name`, `chain_length`, `constraint_type`, `pole_target`, `curve_points`
- test_deformation: tests 8 standard poses, returns contact sheet
- validate: A-F grade (unweighted verts, symmetry, bone rolls)
- fix_weights: `operation` (normalize/clean/smooth/mirror), `direction`, `factor`

### blender_animation
Actions: `generate_walk` | `generate_fly` | `generate_idle` | `generate_attack` | `generate_reaction` | `generate_custom` | `preview` | `add_secondary` | `extract_root_motion` | `retarget_mixamo` | `generate_ai_motion` | `batch_export`
- generate_walk: `gait` (biped/quadruped/hexapod/arachnid/serpent), `speed` (walk/run)
- generate_attack: `attack_type`, `intensity`
- generate_reaction: `reaction_type` (death/hit/spawn), `direction`
- generate_ai_motion: AI motion from text prompt (API + procedural fallback), `prompt`, `model`, `style`, `duration`
- batch_export: `output_dir`, `naming`, `actions` list

### blender_environment
Actions: `generate_terrain` | `paint_terrain` | `carve_river` | `generate_road` | `create_water` | `export_heightmap` | `scatter_vegetation` | `scatter_props` | `create_breakable` | `add_storytelling_props` | `sculpt_terrain`
- generate_terrain: `terrain_type`, `resolution`, `height_scale`, `erosion`, `erosion_iterations`, `seed`
- scatter_vegetation: Poisson disk, `rules`, `min_distance`, `max_instances`
- create_breakable: intact + damaged variants, `prop_type`
- add_storytelling_props: Add narrative clutter to interior rooms (AAA-05), `target_interior`

### blender_quality
Actions: `quality_sword` | `quality_axe` | `quality_mace` | `quality_bow` | `quality_shield` | `quality_staff` | `quality_pauldron` | `quality_chestplate` | `quality_gauntlet` | `creature_mouth` | `creature_eyelid` | `creature_paw` | `creature_wing` | `creature_serpent` | `creature_quadruped` | `creature_fantasy` | `riggable_door` | `riggable_chain` | `riggable_flag` | `riggable_chest` | `riggable_chandelier` | `riggable_drawbridge` | `riggable_rope_bridge` | `riggable_hanging_sign` | `riggable_windmill` | `riggable_cage` | `clothing_generate` | `vegetation_tree` | `vegetation_leaf_cards` | `smart_material` | `trim_sheet` | `macro_variation`
- quality_*: AAA procedural mesh generators for weapons, armor (sword/axe/mace/bow/shield/staff/pauldron/chestplate/gauntlet)
- creature_*: Creature anatomy generators (mouth/eyelid/paw/wing/serpent/quadruped/fantasy)
- riggable_*: Interactive prop generators with rig-ready vertex groups (door/chain/flag/chest/chandelier/drawbridge/rope_bridge/hanging_sign/windmill/cage)
- clothing_generate: Parametric clothing mesh generation, `clothing_type`, `style`
- vegetation_tree: L-system tree generator, `tree_type`, `height`, `branching`
- vegetation_leaf_cards: Billboard leaf card generation
- smart_material: AAA smart material setup, `material_preset`
- trim_sheet: Trim sheet layout generator
- macro_variation: Macro detail variation for terrain textures

### blender_worldbuilding
Actions: `generate_dungeon` | `generate_cave` | `generate_town` | `generate_building` | `generate_castle` | `generate_ruins` | `generate_interior` | `generate_modular_kit` | `generate_location` | `generate_boss_arena` | `generate_world_graph` | `generate_linked_interior` | `generate_multi_floor_dungeon` | `generate_overrun_variant` | `generate_easter_egg`
- generate_dungeon: BSP, `width`, `height`, `min_room_size`, `max_depth`, `cell_size`, `wall_height`
- generate_castle: `outer_size`, `keep_size`, `tower_count`
- generate_modular_kit: `name_prefix`, `cell_size`, `pieces` list
- generate_location: Composed location with buildings, paths, POIs (WORLD-01), `location_type`, `poi_count`
- generate_boss_arena: Arena with cover, hazards, phase triggers (WORLD-03), `arena_type`
- generate_world_graph: MST-connected world graph with locations (WORLD-04), `locations`, `target_distance`
- generate_linked_interior: Interior with door/occlusion/lighting markers (WORLD-05)
- generate_multi_floor_dungeon: Multi-floor dungeon with vertical connections (WORLD-06), `num_floors`
- generate_overrun_variant: Corrupted variant with narrative debris (WORLD-09), `corruption_level`
- generate_easter_egg: Secret rooms, hidden paths, lore items (WORLD-10)

## Unity Server Tools (vb-unity)

**IMPORTANT**: Every Unity tool writes C# to the project and returns `next_steps`. You must:
1. Read the `next_steps` array in the response
2. Typically: call `unity_editor` action=`recompile`, then open Unity Editor and run the menu item from the menu bar

### unity_editor
Actions: `recompile` | `enter_play_mode` | `exit_play_mode` | `screenshot` | `console_logs` | `gemini_review` | `run_tests` | `clean_generated` | `load_scene`
- screenshot: `screenshot_path`, `supersize` (1-4)
- console_logs: `log_filter` (all/error/warning/log), `log_count`
- gemini_review: `gemini_prompt`, `gemini_criteria`
- run_tests: `test_mode` (EditMode/PlayMode), `assembly_filter`, `category_filter`
- clean_generated: Remove accumulated editor scripts, `older_than_hours` (0=all)
- load_scene: Open scene in editor, `scene_path` required

### unity_vfx
Actions: `create_particle_vfx` | `create_brand_vfx` | `create_environmental_vfx` | `create_trail_vfx` | `create_aura_vfx` | `create_corruption_shader` | `create_shader` | `setup_post_processing` | `create_screen_effect` | `create_ability_vfx` | `create_flipbook` | `compose_vfx_graph` | `create_projectile_chain` | `create_aoe_vfx` | `create_status_effect_vfx` | `create_deep_environmental_vfx` | `create_directional_hit_vfx` | `create_boss_transition_vfx` | `create_decal_system`
- create_particle_vfx: `name`, `rate`, `lifetime`, `size`, `color` [r,g,b,a], `shape`
- create_brand_vfx: `brand` (IRON/SAVAGE/SURGE/VENOM/DREAD/LEECH/GRACE/MEND/RUIN/VOID)
- create_shader: `shader_type` (dissolve/force_field/water/foliage/outline/damage_overlay)
- setup_post_processing: `bloom_intensity`, `bloom_threshold`, `vignette_intensity`, `ao_intensity`, `dof_focus_distance`
- create_flipbook: Flipbook texture sheet from particle captures (VFX3-01), `rows`, `columns`, `frame_count`
- compose_vfx_graph: Programmatic VFX Graph node composition (VFX3-02), `spawn_config`, `update_config`, `output_config`
- create_projectile_chain: 4-stage projectile VFX (spawn/travel/impact/aftermath) (VFX3-03), `stages`
- create_aoe_vfx: Area-of-effect ground VFX (VFX3-04), `aoe_type` (ground_circle/cone/line/sphere)
- create_status_effect_vfx: Per-brand persistent status effect VFX (VFX3-05), `brand`, `vfx_intensity`
- create_deep_environmental_vfx: Volumetric fog, god rays, heat distortion, caustics (VFX3-06), `deep_vfx_type`
- create_directional_hit_vfx: Directional combat hit VFX with screen effects (VFX3-07), `hit_magnitude`
- create_boss_transition_vfx: Boss phase transition VFX (VFX3-08), `transition_type`
- create_decal_system: URP decal projector pool manager (VFX-11)

### unity_audio
Actions: `generate_sfx` | `generate_music_loop` | `generate_voice_line` | `generate_ambient` | `setup_footstep_system` | `setup_adaptive_music` | `setup_audio_zones` | `setup_audio_mixer` | `setup_audio_pool_manager` | `assign_animation_sfx` | `setup_spatial_audio` | `setup_layered_sound` | `setup_audio_event_chain` | `setup_dynamic_music` | `setup_portal_audio` | `setup_audio_lod` | `setup_vo_pipeline` | `setup_procedural_foley` | `setup_ui_sound_system` | `setup_material_impact_audio`
- generate_sfx: ElevenLabs AI, `description`, `duration_seconds`
- generate_music_loop: `theme` (combat/exploration/boss/town)
- generate_ambient: `biome` (forest/cave/etc.), `layers`
- setup_adaptive_music: `music_layers` (state names)
- setup_audio_mixer: `groups` (default: Master/SFX/Music/Voice/Ambient/UI)
- setup_spatial_audio: 3D spatial audio with occlusion/rolloff (AUDM-01), `min_distance`, `max_distance`, `occlusion_enabled`
- setup_layered_sound: Composite layered sound design (AUDM-02), `sound_layers`
- setup_audio_event_chain: Sequenced audio event chains (AUDM-03), `chain_events`
- setup_dynamic_music: Horizontal re-sequencing + vertical layering + stingers (AUDM-04), `sections`, `crossfade_duration`
- setup_portal_audio: Room-based sound propagation via portals (AUDM-05), `room_a`, `room_b`
- setup_audio_lod: Distance-based audio quality tiers (AUDM-06), `lod_distances`
- setup_vo_pipeline: Dialogue/VO playback with subtitles and lip sync (AUDM-07), `vo_entries`
- setup_procedural_foley: Movement-based procedural foley (AUDM-08), `armor_type`, `terrain_type`
- setup_ui_sound_system: Runtime UI sound infrastructure (AU-01)
- setup_material_impact_audio: Physics material-aware impact sounds (AU-02)

### unity_ui
Actions: `generate_ui_screen` | `validate_layout` | `test_responsive` | `check_contrast` | `compare_screenshots` | `create_procedural_frame` | `create_icon_pipeline` | `create_cursor_system` | `create_tooltip_system` | `create_radial_menu` | `create_notification_system` | `create_loading_screen` | `create_ui_shaders` | `create_combat_hud`
- generate_ui_screen: `screen_spec` dict, `theme` (default dark_fantasy), `screen_name`
- check_contrast: WCAG AA validation, needs UXML + USS content
- compare_screenshots: `reference_path`, `current_path`, `diff_threshold`
- create_procedural_frame: Ornate dark fantasy UI frames with rune decorations (UIPOL-01), `frame_name`, `rune_brand`
- create_icon_pipeline: 3D icon render pipeline with rarity borders (UIPOL-02), `icon_size`, `render_resolution`
- create_cursor_system: Context-sensitive cursors with dark fantasy themes (UIPOL-03), `cursor_types`, `cursor_size`
- create_tooltip_system: Rich tooltips with equipment comparison and lore (UIPOL-04), `tooltip_style`, `show_comparison`
- create_radial_menu: Radial ability/item wheel with PrimeTween animation (UIPOL-05), `segment_count`, `trigger_key`
- create_notification_system: Toast notification system with priority queue (UIPOL-06), `max_visible`, `toast_types`
- create_loading_screen: Loading screen with tips, lore, and concept art (UIPOL-07), `show_tips`, `tip_interval`
- create_ui_shaders: Material-based UI effect shaders (gold-leaf, blood stain, etc.) (UIPOL-08), `ui_shader_name`
- create_combat_hud: Complete dark fantasy combat HUD (UI-08)

### unity_scene
Actions: `setup_terrain` | `scatter_objects` | `setup_lighting` | `bake_navmesh` | `create_animator` | `configure_avatar` | `setup_animation_rigging` | `create_blend_tree` | `create_additive_layer`
- setup_terrain: `heightmap_path`, `terrain_size` [w,h,l], `splatmap_layers`
- setup_lighting: `time_of_day` (dawn/noon/dusk/night/overcast), `fog_enabled`, `sun_intensity`
- create_animator: `states`, `transitions`, `parameters`, `blend_trees`
- configure_avatar: `fbx_path`, `animation_type` (Humanoid/Generic), `bone_mapping`
- create_blend_tree: Directional 8-way, speed, or combined blend trees (ANIM3-03), `blend_type`, `motion_clips`
- create_additive_layer: Additive animation layers for hit reactions/breathing (ANIM3-04), `layer_name`, `base_clips`

### unity_gameplay
Actions: `create_mob_controller` | `create_aggro_system` | `create_patrol_route` | `create_spawn_system` | `create_behavior_tree` | `create_combat_ability` | `create_projectile_system` | `create_encounter_system` | `create_ai_director` | `simulate_encounters` | `create_boss_ai`
- create_mob_controller: FSM with `detection_range`, `attack_range`, `leash_distance`, `patrol_speed`, `chase_speed`, `flee_health_pct`
- create_spawn_system: `max_count`, `respawn_timer`, `spawn_radius`, `wave_cooldown`, `wave_count`
- create_projectile_system: `velocity`, `trajectory` (straight/arc/homing), `trail_width`, `impact_vfx`
- create_encounter_system: Wave ScriptableObject + encounter manager (AID-01)
- create_ai_director: AnimationCurve-based difficulty scaling (AID-02)
- simulate_encounters: Monte Carlo encounter simulator (AID-03)
- create_boss_ai: Multi-phase boss FSM (VB-10)

### unity_performance
Actions: `profile_scene` | `setup_lod_groups` | `bake_lightmaps` | `audit_assets` | `automate_build`
- profile_scene: `target_frame_time_ms`, `max_draw_calls`, `max_batches`, `max_triangles`, `max_memory_mb`
- setup_lod_groups: `lod_count`, `screen_percentages` (descending)
- audit_assets: `max_texture_size`, `allowed_audio_formats`
- automate_build: `build_target` (e.g. StandaloneWindows64), `scenes`, `build_options`

### unity_prefab (v2.0)
Actions: `create` | `create_variant` | `modify` | `delete` | `create_scaffold` | `add_component` | `remove_component` | `configure` | `reflect_component` | `batch_configure` | `hierarchy` | `generate_variants` | `batch_job` | `setup_joints` | `setup_navmesh` | `setup_bone_sockets` | `validate_project` | `cloth_setup`
- create: auto-wire components based on prefab type (monster/hero/prop/ui profiles)
- generate_variants: corruption tier x brand x archetype from one base prefab
- batch_job: multiple operations in one compilation cycle
- cloth_setup: Configure Unity Cloth component with presets (CHAR-07), `cloth_type` (cape/skirt/banner/hair/chain)

### unity_settings (v2.0)
Actions: `configure_physics` | `create_physics_material` | `configure_player` | `configure_build` | `configure_quality` | `install_package` | `remove_package` | `manage_tags_layers` | `sync_tags_layers` | `configure_time` | `configure_graphics`
- sync_tags_layers: auto-sync tags/layers from Constants.cs
- install_package: UPM, OpenUPM, git URL sources

### unity_assets (v2.0)
Actions: `move` | `rename` | `delete` | `duplicate` | `create_folder` | `configure_fbx` | `configure_texture` | `remap_materials` | `auto_materials` | `create_asmdef` | `create_preset` | `apply_preset` | `scan_references` | `atomic_import`

### unity_code (v2.0)
Actions: `generate_class` | `modify_script` | `editor_window` | `property_drawer` | `inspector_drawer` | `scene_overlay` | `generate_test` | `service_locator` | `object_pool` | `singleton` | `state_machine` | `event_channel`

### unity_shader (v2.0)
Actions: `create_shader` | `create_renderer_feature` | `sss_skin_shader` | `parallax_eye_shader` | `micro_detail_normal`
- create_shader: arbitrary HLSL/ShaderLab with configurable properties
- create_renderer_feature: URP ScriptableRendererFeature with RenderGraph API
- sss_skin_shader: Subsurface scattering skin shader for characters (CHAR-08), `sss_color`, `sss_scale`
- parallax_eye_shader: Parallax/refraction eye shader with iris depth (CHAR-08), `iris_depth`, `ior`
- micro_detail_normal: Micro-detail normal compositing script (CHAR-08), `base_normal_property`

### unity_data (v2.0)
Actions: `create_so_definition` | `create_so_assets` | `validate_json` | `create_json_loader` | `setup_localization` | `add_localization_entries` | `create_data_editor`

### unity_quality (v2.0)
Actions: `check_poly_budget` | `create_master_materials` | `check_texture_quality` | `aaa_audit`

### unity_pipeline (v2.0)
Actions: `configure_git_lfs` | `create_sprite_atlas` | `create_sprite_animation` | `configure_sprite_editor` | `create_asset_postprocessor`

### unity_game (v2.0)
Actions: `create_save_system` | `create_health_system` | `create_character_controller` | `create_input_config` | `create_settings_menu` | `create_http_client` | `create_interactable` | `create_player_combat` | `create_ability_system` | `create_synergy_engine` | `create_corruption_gameplay` | `create_xp_leveling` | `create_currency_system` | `create_damage_types`

### unity_content (v2.0)
Actions: `create_inventory_system` | `create_dialogue_system` | `create_quest_system` | `create_loot_table` | `create_crafting_system` | `create_skill_tree` | `create_dps_calculator` | `create_encounter_simulator` | `create_stat_curve_editor` | `create_shop_system` | `create_journal_system` | `create_equipment_attachment`

### unity_camera (v2.0)
Actions: `create_virtual_camera` | `create_state_driven_camera` | `create_camera_shake` | `configure_blend` | `create_timeline` | `create_cutscene` | `edit_animation_clip` | `modify_animator` | `create_avatar_mask` | `setup_video_player` | `cinematic_sequence` | `create_lock_on_camera`
- cinematic_sequence: Timeline-based cinematic with shots and character staging (ANIM3-07), `shots`
- create_lock_on_camera: Souls-like lock-on targeting camera (CAM-05)

### unity_world (v2.0)
Actions: `create_scene` | `create_transition_system` | `setup_probes` | `setup_occlusion` | `setup_environment` | `paint_terrain_detail` | `create_tilemap` | `setup_2d_physics` | `apply_time_of_day` | `create_fast_travel` | `create_puzzle` | `create_trap` | `create_spatial_loot` | `create_weather` | `create_day_night` | `create_npc_placement` | `create_dungeon_lighting` | `create_terrain_blend` | `create_wfc_dungeon` | `create_interior_streaming` | `create_door_system`
- create_wfc_dungeon: WFC tile-based dungeon generation (WORLD-11)
- create_interior_streaming: Seamless interior/exterior streaming (WORLD-12)
- create_door_system: Door/gate/lock and lever system (WORLD-13)

### unity_ux (v2.0)
Actions: `create_minimap` | `create_damage_numbers` | `create_interaction_prompts` | `create_primetween_sequence` | `create_tmp_font_asset` | `setup_tmp_components` | `create_tutorial_system` | `create_accessibility` | `create_character_select` | `create_world_map` | `create_rarity_vfx` | `create_corruption_vfx`

### unity_qa (v2.0)
Actions: `setup_bridge` | `run_tests` | `run_play_session` | `profile_scene` | `detect_memory_leaks` | `analyze_code` | `setup_crash_reporting` | `setup_analytics` | `inspect_live_state` | `check_compile_status` | `compile_recovery` | `detect_conflicts` | `orchestrate_pipeline` | `list_pipeline_steps` | `validate_art_style` | `build_smoke_test` | `code_review`
- setup_bridge: Deploy VBBridge TCP server for direct Unity Editor communication (QA-00)
- check_compile_status: detect Unity compilation errors via TCP bridge
- compile_recovery: Compile error auto-detection and recovery (PROD-01), `auto_fix_enabled`, `max_retries`
- detect_conflicts: Pre-write asset/class name conflict scanning (PROD-02), `scan_paths`, `namespace_prefix`
- orchestrate_pipeline: Multi-step pipeline orchestration with status tracking (PROD-03), `pipeline_name`, `pipeline_steps`, `on_failure`
- list_pipeline_steps: List available built-in pipeline step definitions (PROD-03b)
- validate_art_style: Art style consistency validation (PROD-04), `palette_colors`, `naming_pattern`
- build_smoke_test: Post-build smoke test verification (PROD-05), `build_path`, `scene_to_load`
- code_review: Deploy unified C#/Python code reviewer (PROD-06)

### unity_build (v2.0)
Actions: `build_multi_platform` | `configure_addressables` | `generate_ci_pipeline` | `manage_version` | `configure_platform` | `setup_shader_stripping` | `generate_store_metadata`

## Workflow Rules

1. **Always verify visually** after Blender mutations. Use `blender_viewport` action=`contact_sheet` for thorough review.
2. **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
3. **Unity two-step**: Tool writes script, you must recompile + execute. Follow `next_steps`.
4. **Game readiness**: Run `blender_mesh` action=`game_check` before export. Run `unity_performance` action=`profile_scene` after setup.
5. **Use seeds** for reproducible environment/worldbuilding generation.
6. **Batch when possible**: `asset_pipeline` action=`batch_process`, `blender_animation` action=`batch_export`.

## Planning Files

Phase plans are in `.planning/phases/`. Current project state is in `.planning/STATE.md`. Requirements in `.planning/REQUIREMENTS.md`. Roadmap in `.planning/ROADMAP.md`.
