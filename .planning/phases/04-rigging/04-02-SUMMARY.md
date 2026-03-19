---
phase: 04-rigging
plan: 02
status: complete
completed: 2026-03-19
tests_passed: 55 new (404 total suite)
handler_count: 46 -> 50
---

## What was built

### rigging_weights.py (new)
- DEFORMATION_POSES constant: 8 standard deformation test poses (t_pose, a_pose, crouch, reach_up, twist_left, twist_right, extreme_bend, action_pose) mapping DEF bone names to (x, y, z) rotation tuples
- _compute_rig_grade(unweighted_pct, non_normalized, symmetry_issues, roll_issues): pure-logic A-F grading with cascading thresholds (F: >10%/100, D: >5%/50/5, C: >1%/10/2, B: >0/0/2rolls, A: all zero)
- _validate_rig_report(vertex_count, vertex_group_names, unweighted_vertex_indices, weight_sums, bone_names, bone_rolls, bone_parents): pure-logic report builder computing unweighted percentage, non-normalized count, L/R symmetry check, roll consistency check, issues list, and grade
- _validate_weight_fix_params(operation, params): pure-logic validator for fix operations (normalize, clean_zeros, smooth, mirror) with param range checks
- handle_auto_weight (RIG-07): parents mesh to armature via ARMATURE_AUTO heat diffusion with ARMATURE_ENVELOPE fallback
- handle_test_deformation (RIG-08): poses rig at DEFORMATION_POSES presets, keyframes each, generates contact sheet via handle_render_contact_sheet
- handle_validate_rig (RIG-09): extracts mesh weights and armature bone data, calls _validate_rig_report for A-F grading
- handle_fix_weights (RIG-10): executes normalize/clean_zeros/smooth/mirror via bpy.ops vertex group operators with temp_override

### handlers/__init__.py (modified)
- Registered 4 new handlers: rig_auto_weight, rig_test_deformation, rig_validate, rig_fix_weights (46 -> 50 total)

### test_rigging_handlers.py (appended, 55 new tests)
- TestRigValidation: 16 tests (clean rig grades A, heavily unweighted grades F, non-normalized grades F, moderate grades D, symmetry issues grade D/C, small issues grade C/B, roll mismatches, asymmetric bones, zero vertex edge case, required keys)
- TestComputeRigGrade: 16 tests (each grade threshold boundary, boundary-exact values, worst-grade-wins cascading)
- TestDeformationPoses: 8 tests (exactly 8 poses, expected names, values are dicts, 3-element rotation tuples, t_pose empty, a_pose has upper arms, DEF- prefix, numeric values)
- TestWeightFixParams: 15 tests (all 4 valid operations, invalid operation, mirror direction required/valid/invalid, smooth factor/repeat valid/invalid, clean_zeros threshold valid/invalid, required keys)

## Key decisions
- Pure-logic extraction: _validate_rig_report accepts pre-extracted data (no bpy dependency) so grading logic is fully testable -- 31 tests cover grade boundaries without Blender
- Auto weight fallback: handle_auto_weight tries heat diffusion first, catches RuntimeError ("Bone Heat Weighting Failed") and falls back to envelope weights
- Deformation test workflow: keyframes each pose at sequential frames, then delegates to handle_render_contact_sheet for visual proof
- Roll consistency check uses tolerance of 0.05 radians -- L bone roll should be negative of R bone roll
- Weight fix operations use bpy.ops vertex group operators (normalize_all, clean, smooth, mirror) via temp_override pattern
