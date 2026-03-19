# Phase 07 Plan 05 Summary: Unity Scene Setup (Terrain, Scatter, Lighting, NavMesh, Animator, Avatar, Rigging)

**Status:** COMPLETE
**Date:** 2026-03-19

## What was built

### New files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/scene_templates.py` (521 lines) -- 7 C# template generators: `generate_terrain_setup_script`, `generate_object_scatter_script`, `generate_lighting_setup_script`, `generate_navmesh_bake_script`, `generate_animator_controller_script`, `generate_avatar_config_script`, `generate_animation_rigging_script`
- `Tools/mcp-toolkit/tests/test_scene_templates.py` (445 lines) -- 86 tests covering all 7 scene template generators

### Modified files
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` -- Added `unity_scene` compound tool with 7 actions (`setup_terrain`, `scatter_objects`, `setup_lighting`, `bake_navmesh`, `create_animator`, `configure_avatar`, `setup_animation_rigging`) + imports from scene_templates + 7 handler functions

## Test results
- 86 new tests pass (scene_templates)
- 1467 total tests pass (zero regressions)

## Requirements covered
- **SCENE-01:** Terrain setup -- `generate_terrain_setup_script` creates TerrainData, reads RAW heightmap, calls SetHeights, configures splatmap layers with SetAlphamaps, creates Terrain.CreateTerrainGameObject
- **SCENE-02:** Object scatter -- `generate_object_scatter_script` uses grid-with-jitter sampling on terrain, filters by slope (GetInterpolatedNormal) and altitude (SampleHeight), instantiates via PrefabUtility.InstantiatePrefab, groups under parent GameObject
- **SCENE-03:** Lighting setup -- `generate_lighting_setup_script` creates directional light with time_of_day presets (dawn/noon/dusk/night/overcast), configures RenderSettings (ambient, fog, skybox), creates Volume with Bloom/Vignette/ColorAdjustments
- **SCENE-04:** NavMesh bake -- `generate_navmesh_bake_script` adds NavMeshSurface, configures agent radius/height/slope/step, calls BuildNavMesh(), creates NavMeshLinks
- **SCENE-05:** Animator Controller -- `generate_animator_controller_script` creates AnimatorController at path, AddParameter for float/int/bool/trigger, AddState, AddTransition with conditions, CreateBlendTreeInController with child motions
- **SCENE-06:** Avatar configuration -- `generate_avatar_config_script` sets ModelImporter.animationType to Humanoid/Generic, configures HumanDescription bone mapping, calls SaveAndReimport()
- **SCENE-07:** Animation Rigging -- `generate_animation_rigging_script` adds RigBuilder + Rig, creates TwoBoneIKConstraint (root/mid/tip/target) and MultiAimConstraint (constrainedObject + WeightedTransformArray sources)

## Architecture

### Scene Templates
All 7 generators follow the established pattern: return complete C# source with `using UnityEngine;`, `using UnityEditor;`, `[MenuItem("VeilBreakers/Scene/...")]`, try/catch with JSON result written to `Temp/vb_result.json`.

- **Terrain** reads 16-bit RAW heightmap bytes, converts to float[,], supports N splatmap layers with TerrainLayer objects
- **Scatter** calculates grid spacing from density (0=20m, 1=2m spacing), applies per-cell jitter, validates slope angle via normal dot product and altitude via SampleHeight
- **Lighting** has 5 presets with sun rotation, color temperatures, and ambient/fog colors tuned for dark fantasy aesthetic; post-processing Volume uses Bloom (1.2 intensity), Vignette (0.35), ColorAdjustments (contrast +15, saturation -10)
- **NavMesh** uses Unity.AI.Navigation NavMeshSurface component with NavMesh.GetSettingsByIndex for agent type
- **Animator** builds full state machine programmatically with condition modes (Greater, Less, Equals, etc.) and optional BlendTree children with threshold-based motion blending
- **Avatar** handles both Humanoid (with HumanBone[] mapping) and Generic types via ModelImporter API
- **Rigging** requires `using UnityEngine.Animations.Rigging;`, creates RigBuilder/Rig hierarchy, FindTransformRecursive helper for bone lookup

### unity_scene Compound Tool
The `unity_scene` tool in `unity_server.py` has 7 actions. Each action:
1. Validates required parameters (returns error JSON if missing)
2. Calls the appropriate scene_templates generator
3. Writes C# to `Assets/Editor/Generated/Scene/{name}_{action}.cs` via `_write_to_unity`
4. Returns structured JSON with file_path, menu_item path, and next_steps

## Phase 7 Complete Summary

With Plan 05 complete, `unity_server.py` now has **5 compound tools with 38 total actions**:

| Tool | Actions | Requirements |
|------|---------|-------------|
| `unity_editor` | 6 (recompile, enter_play_mode, exit_play_mode, screenshot, console_logs, gemini_review) | Editor automation |
| `unity_vfx` | 10 (create_particle_vfx, create_brand_vfx, create_environmental_vfx, create_trail_vfx, create_aura_vfx, create_corruption_shader, create_shader, setup_post_processing, create_screen_effect, create_ability_vfx) | VFX-01 to VFX-10 |
| `unity_audio` | 10 (generate_sfx, generate_music_loop, generate_voice_line, generate_ambient, setup_footstep_system, setup_adaptive_music, setup_audio_zones, setup_audio_mixer, setup_audio_pool_manager, assign_animation_sfx) | AUD-01 to AUD-10 |
| `unity_ui` | 5 (generate_ui_screen, validate_layout, test_responsive, check_contrast, compare_screenshots) | UI-02, UI-03, UI-05, UI-06, UI-07 |
| `unity_scene` | 7 (setup_terrain, scatter_objects, setup_lighting, bake_navmesh, create_animator, configure_avatar, setup_animation_rigging) | SCENE-01 to SCENE-07 |
