---
phase: 04-rigging
plan: 03
status: complete
completed: 2026-03-19
tests_passed: 77 new (481 total suite)
handler_count: 50 -> 56
---

## What was built

### rigging_advanced.py (new)
- FACIAL_BONES dict: 18 bone-based facial rig controls (jaw, lip_upper, lip_lower, lip_corner.L/R, eyelid_upper.L/R, eyelid_lower.L/R, brow_inner.L/R, brow_mid.L/R, brow_outer.L/R, cheek.L/R, nose) -- all with L/R symmetry, mirrored X positions, head/tail/roll/parent keys
- MONSTER_EXPRESSIONS dict: 3 creature expression presets (snarl, hiss, roar) with bone name -> location/rotation transform mappings
- RAGDOLL_PRESETS dict: humanoid preset with 11 bone-to-collider mappings (spine x2, upper_arm.L/R, forearm.L/R, thigh.L/R, shin.L/R, head) including shape, radius, length, mass, and joint angle limits
- 5 pure-logic validation functions:
  - _validate_ik_params: chain_length [1,20], constraint_type IK/SPLINE_IK, bone_name, pole_angle, curve_points for spline
  - _validate_spring_params: stiffness [0,1], damping [0,1], gravity >= 0, non-empty bone_names
  - _validate_ragdoll_spec: shape BOX/CAPSULE, mass/radius/length > 0, joint angles in [-pi, pi]
  - _validate_retarget_mapping: source/target bone existence, unmapped bone tracking
  - _validate_shape_key_params: name regex, vertex indices non-negative int, offsets 3-element numeric
- 6 Blender-dependent handlers:
  - handle_setup_facial (RIG-04): adds FACIAL_BONES to armature, stores MONSTER_EXPRESSIONS as pose presets
  - handle_setup_ik (RIG-05): standard IK and SPLINE_IK with curve generation and LIMIT_ROTATION joint limits
  - handle_setup_spring_bones (RIG-06): DAMPED_TRACK + COPY_ROTATION with decay chain, custom property storage
  - handle_setup_ragdoll (RIG-11): mesh collider generation (cylinder/cube), rigid body setup, joint constraints from presets
  - handle_retarget_rig (RIG-12): COPY_ROTATION + COPY_LOCATION constraints with bone length ratio scaling
  - handle_add_shape_keys (RIG-13): expression/damage/custom modes with vertex group weighting and convexity-based damage

### handlers/__init__.py (modified)
- Registered 6 new handlers: rig_setup_facial, rig_setup_ik, rig_setup_spring_bones, rig_setup_ragdoll, rig_retarget, rig_add_shape_keys (50 -> 56 total)

### test_rigging_advanced.py (new, 77 tests)
- TestFacialRig: 16 tests (bone count >= 15, jaw/lip/eyelid/brow/cheek presence, required keys, 3-tuple positions, roll numeric, L/R symmetry, mirrored X, parent hierarchy)
- TestMonsterExpressions: 10 tests (snarl/hiss/roar presence, bone transforms non-empty, all bones reference FACIAL_BONES, valid transform format, jaw rotation in roar/hiss)
- TestIKParams: 11 tests (valid standard/spline IK, chain_length bounds 0/1/20/21, missing/empty bone_name, SPLINE_IK without curve_points, invalid constraint_type, result keys)
- TestSpringParams: 10 tests (valid params, empty bone_names, stiffness/damping bounds, negative gravity, zero gravity, boundary values, bone_count, result keys)
- TestRagdollSpec: 12 tests (valid capsule/box, invalid shape, mass 0/negative, missing fields, empty map, multiple colliders, zero radius, joint angles, humanoid preset validation, result keys)
- TestRetargetMapping: 7 tests (valid mapping, source/target bone missing, empty mapping, partial mapping unmapped reporting, result keys, mapped_count)
- TestShapeKeyParams: 11 tests (valid params, empty name, special chars, underscore/hyphen, negative index, wrong tuple length, non-numeric offset, empty offsets, vertex_count, list offset, result keys)

## Key decisions
- Created test_rigging_advanced.py as a SEPARATE file to avoid conflicts with Plan 02's modifications to test_rigging_handlers.py
- Facial rig uses bone-based controls (not shape keys) for jaw, lips, eyelids, brows, cheeks -- allows direct pose manipulation
- Lip_lower parents to jaw (moves with jaw opening), all other facial bones parent to head
- Spring bones use DAMPED_TRACK + COPY_ROTATION with exponential decay (0.8^i) along the chain for natural falloff
- Ragdoll colliders use cylinder for CAPSULE and cube for BOX shapes, parented to bones with BONE parent type
- Shape key damage mode uses seeded random + vertex normal direction + convexity scaling for deterministic, physically plausible deformation
