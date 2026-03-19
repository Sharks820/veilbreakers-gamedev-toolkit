---
phase: 05-animation
plan: 03
status: complete
tests_passed: 78
tests_total: 78
full_suite_passed: 759
full_suite_total: 759
---

# Phase 05-03 Summary: Animation Export & Integration Handlers

## What was built

**`Tools/mcp-toolkit/blender_addon/handlers/animation_export.py`** -- 6 animation export/integration handlers with pure-logic validation functions. Contains:

1. **MIXAMO_TO_RIGIFY mapping** -- 22 core humanoid bone mappings from Mixamo skeleton names to Rigify DEF bones (spine chain x6, left/right arms x4 each, left/right legs x4 each). All keys prefixed with "mixamorig:", all values prefixed with "DEF-".

2. **handle_preview_animation(params)** (ANIM-07): Renders every Nth frame of an animation from multiple configurable angles into contact sheet images. Reuses existing `handle_render_contact_sheet` from viewport.py with `frame_set()` per frame. Supports named angle presets (front, back, left, right, side, top, three_quarter) or custom [azimuth, elevation] pairs.

3. **handle_add_secondary_motion(params)** (ANIM-08): Bakes spring bone constraint simulations to explicit keyframes for export. Selects specified spring bones, calls `bpy.ops.nla.bake()` with `visual_keying=True` to capture constraint effects, preserving original constraints.

4. **handle_extract_root_motion(params)** (ANIM-09): Frame-by-frame extraction of hip XY translation to root bone. Preserves vertical bob (Z intact). Creates root bone fcurves with extracted XY values, zeros out hip XY local fcurves. Places `pose_markers` at foot contact frames by detecting foot bone Z position local minima. Optional Z rotation extraction respecting bone rotation_mode (Euler vs Quaternion).

5. **handle_retarget_mixamo(params)** (ANIM-10): Imports Mixamo FBX, identifies the mixamorig armature, builds filtered bone mapping using MIXAMO_TO_RIGIFY, applies COPY_ROTATION constraints from source to target, bakes with visual keying, then cleans up imported objects.

6. **handle_generate_ai_motion(params)** (ANIM-11): Stub handler returning `{"status": "stub", "message": "..."}`. Validates prompt, model (hy-motion or motion-gpt), and frame_count params. Ready for API integration when available.

7. **handle_batch_export(params)** (ANIM-12): Exports each NLA strip as separate FBX with Unity naming convention (`ObjectName@ClipName.fbx`). Uses `bake_anim_use_nla_strips=True` AND `bake_anim_use_all_actions=False` (both required for correct per-strip export). Solos strips individually, exports with FBX_SCALE_ALL, -Z forward, Y up, no leaf bones.

8. **Pure-logic validation functions**: `_validate_export_params`, `_validate_preview_params`, `_validate_secondary_motion_params`, `_validate_root_motion_params`, `_validate_batch_export_params`, `_map_mixamo_bones`, `_generate_unity_filename` -- all testable without Blender.

9. **NLA helpers**: `_push_action_to_nla`, `_solo_nla_strip`, `_restore_nla_mute_states` for batch export strip management.

**`Tools/mcp-toolkit/tests/test_animation_export.py`** -- 78 tests across 10 test classes:
- TestValidateExportParams (7), TestValidatePreviewParams (9), TestValidateSecondaryMotionParams (6), TestValidateRootMotionParams (8), TestValidateBatchExportParams (10), TestMixamoBoneMapping (14), TestMapMixamoBones (6), TestGenerateUnityFilename (7), TestPreviewAngles (6), TestAIMotionStub (2), TestBatchExportFBXSettings (3)

**`Tools/mcp-toolkit/blender_addon/handlers/__init__.py`** -- Updated with 6 new handler imports and COMMAND_HANDLERS registrations (anim_preview, anim_add_secondary_motion, anim_extract_root_motion, anim_retarget_mixamo, anim_generate_ai_motion, anim_batch_export). Total handlers now: 52.

## Key design decisions

- Root motion extraction processes frame-by-frame in world space (not raw fcurve values) to avoid quality loss pitfall from RESEARCH
- Both `bake_anim_use_nla_strips=True` and `bake_anim_use_all_actions=False` set explicitly to prevent Unity "Take 001" single-animation pitfall
- Mixamo bone mapping uses static dict (not regex transformation) for explicit control and testability
- PREVIEW_ANGLES dict provides named presets for common camera positions
- _map_mixamo_bones filters by bones actually present on both rigs to handle partial skeletons
- Unity filename sanitizes spaces to underscores for safe filesystem paths
- AI motion stub validates model and frame_count params to match future API contract

## Verification

- 78/78 tests pass for animation_export module
- 759/759 tests pass for full suite (no regressions)
- All 6 handlers follow handle_*(params) -> dict pattern
- MIXAMO_TO_RIGIFY has 22 entries covering full humanoid skeleton
- All Mixamo keys prefixed with "mixamorig:", all Rigify values prefixed with "DEF-"
- Left/right symmetry verified in test
