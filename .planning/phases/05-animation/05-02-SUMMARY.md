---
phase: 05-animation
plan: 02
status: complete
tests_passed: 90
tests_total: 90
full_suite_passed: 759
full_suite_total: 759
---

# Phase 05-02 Summary: Blender Animation Handlers

## What was built

**`Tools/mcp-toolkit/blender_addon/handlers/animation.py`** (482 lines) -- 6 Blender animation handlers that bridge the pure-logic keyframe engine (animation_gaits.py) to Blender Actions with fcurves, CYCLES modifiers, and pose_markers. Contains:

1. **6 pure-logic validation helpers** (testable without Blender):
   - `_validate_walk_params` -- gait (5 types), speed (walk/run), frame_count
   - `_validate_fly_params` -- frequency, amplitude, glide_ratio bounds
   - `_validate_idle_params` -- breathing_intensity, frame_count
   - `_validate_attack_params` -- 8 attack types, intensity (0.1-5.0)
   - `_validate_reaction_params` -- 3 reaction types, hit directions
   - `_validate_custom_params` -- non-empty description string

2. **5 Blender-dependent helpers**:
   - `_validate_animation_params` -- checks armature exists, type, has pose bones
   - `_get_armature_def_bones` -- returns sorted DEF-prefixed bone names
   - `_resolve_bone_name` -- tries with/without DEF- prefix
   - `_apply_keyframes_to_action` -- creates Action, fcurves, bulk-inserts keyframes, adds CYCLES modifier, handles QUATERNION rotation mode
   - `_add_contact_markers` -- adds pose_markers at contact frames

3. **6 handler functions** (handle_*(params) -> dict pattern):
   - `handle_generate_walk` (ANIM-01) -- 5 gaits x 2 speeds, cyclic, contact markers for foot plants
   - `handle_generate_fly` (ANIM-02) -- frequency/amplitude/glide_ratio scaling, cyclic wing oscillation
   - `handle_generate_idle` (ANIM-03) -- breathing_intensity scaling, cyclic subtle motion
   - `handle_generate_attack` (ANIM-04) -- 8 attack types, non-cyclic, strike frame markers, phase info
   - `handle_generate_reaction` (ANIM-05) -- death/hit/spawn, non-cyclic, directional hit with impact markers
   - `handle_generate_custom` (ANIM-06) -- text-to-keyframe, non-cyclic, parsed_actions report

**`Tools/mcp-toolkit/tests/test_animation_handlers.py`** (610 lines) -- 90 tests across 8 test classes:
- TestConstants (8), TestWalkParams (12), TestFlyParams (11), TestIdleParams (7), TestAttackParams (12), TestReactionParams (12), TestCustomParams (10), TestNoBlenderImportsInValidation (4)

**`Tools/mcp-toolkit/blender_addon/handlers/__init__.py`** -- registered 6 animation handlers in COMMAND_HANDLERS (46 -> 52 total handlers).

## Key design decisions

- Cyclic handlers (walk/fly/idle) set `use_cyclic=True` for CYCLES fcurve modifier; combat handlers (attack/reaction/custom) set `use_cyclic=False` for one-shot animations
- All handlers separate validation into two steps: pure-logic param validation (testable) then Blender armature validation (requires bpy)
- `_apply_keyframes_to_action` handles quaternion rotation mode by checking `pose_bone.rotation_mode` and remapping axis indices (euler 0-2 -> quaternion 1-3)
- Contact frames computed per gait: biped/quadruped/serpent get 2 markers, hexapod gets 3 (tripod), arachnid gets 4 (4-4 alternating)
- Fly handler scales bone amplitudes relative to FLY_HOVER_CONFIG defaults and applies glide dampening
- Attack handler computes phase frame ranges from standard 20/30/50% timing and includes them in return dict

## Verification

- 90/90 tests pass for animation handler validation
- 759/759 tests pass for full suite (no regressions)
- All acceptance criteria met: 6 handlers, 1 _apply_keyframes_to_action, 1 _validate_animation_params, pose_markers references, melee_swing/breath_attack present, 3x use_cyclic=False
