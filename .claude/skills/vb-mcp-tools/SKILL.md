# VeilBreakers MCP Tools Context

You have access to 37 compound MCP tools (350+ actions) for game development:

## Blender (vb-blender) — 16 tools via TCP localhost:9876
- **blender_object**: create/modify/delete/duplicate meshes
- **blender_mesh**: analyze/repair/game_check/sculpt/boolean/retopo (run repair before UV)
- **blender_uv**: unwrap (xatlas)/pack/lightmap/equalize
- **blender_texture**: create_pbr/bake/upscale/inpaint/delight/validate_palette
- **blender_material**: create/assign/modify PBR materials
- **blender_rig**: apply_template (humanoid/quadruped)/auto_weight/validate/fix_weights
- **blender_animation**: generate_walk/attack/idle/reaction/ai_motion/batch_export
- **blender_quality**: 32 AAA generators — weapons, armor, creatures, riggable props, clothing, vegetation, materials
- **blender_worldbuilding**: dungeons/caves/towns/castles/ruins/boss_arenas/multi-floor
- **blender_environment**: terrain/rivers/roads/water/vegetation scatter/breakables
- **blender_viewport**: screenshot/contact_sheet (ALWAYS use for visual QA)
- **blender_export**: fbx/gltf (run game_check FIRST)
- **asset_pipeline**: compose_map/compose_interior/generate_3d (Tripo AI)/batch_process
- **concept_art**: generate (fal.ai FLUX)/extract_palette/silhouette_test

## Unity (vb-unity) — 22 tools generating C# editor scripts
**CRITICAL**: Every Unity tool returns `next_steps`. Call `unity_editor action=recompile` then execute the menu item.

- **unity_editor**: recompile/screenshot/console_logs/run_tests/clean_generated
- **unity_vfx**: particles/brand VFX (10 brands)/shaders/projectile chains/AoE/boss transitions
- **unity_audio**: AI SFX (ElevenLabs)/music/ambient/spatial/dynamic music/foley/VO
- **unity_ui**: screens/WCAG contrast/procedural frames/icons/cursors/tooltips/radial menus/combat HUD
- **unity_gameplay**: mob AI/spawn/behavior trees/projectiles/encounters/AI director/boss AI
- **unity_game**: save/health/character controller/input/abilities/synergy/corruption/XP/damage types
- **unity_content**: inventory/dialogue/quests/loot/crafting/skill trees/shops/equipment
- **unity_world**: scenes/weather/day-night/fast travel/puzzles/traps/WFC dungeons/door systems
- **unity_camera**: Cinemachine/camera shake/timelines/cutscenes/lock-on
- **unity_code**: generate_class/state_machine/event_channel/object_pool/service_locator
- **unity_shader**: custom HLSL/renderer features/SSS skin/parallax eyes
- **unity_qa**: bridge/tests/profiling/memory leaks/code review/compile recovery
- **unity_prefab**: create/variants/batch_configure/cloth_setup/bone_sockets
- **unity_performance**: profile_scene/LOD groups/lightmaps/asset audit
- **unity_build**: multi-platform/addressables/CI pipeline/shader stripping

## Pipeline Order
repair → UV → texture → rig → animate → export. Do not skip steps.

## Game Context
VeilBreakers3D: dark fantasy action RPG. 10 brands (IRON/SAVAGE/SURGE/VENOM/DREAD/LEECH/GRACE/MEND/RUIN/VOID). Unity 6, URP 17.3, UI Toolkit, PrimeTween.

## UI Implementation
When building UI, apply frontend-design skill's design thinking but implement in Unity UI Toolkit (UXML + USS + C#/PrimeTween), not web technologies. Reference `Assets/UI/Styles/VeilBreakers.uss` and `CharacterSelect.uss`.
