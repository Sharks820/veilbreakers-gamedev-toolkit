---
phase: 05-animation
plan: 01
status: complete
tests_passed: 109
tests_total: 109
full_suite_passed: 591
full_suite_total: 591
---

# Phase 05-01 Summary: Keyframe Engine & Gait/Attack/Reaction Configs

## What was built

**`Tools/mcp-toolkit/blender_addon/handlers/animation_gaits.py`** -- Pure-logic keyframe engine with ZERO Blender imports (no bpy, bmesh, or mathutils). Contains:

1. **Keyframe NamedTuple** -- `(bone_name, channel, axis, frame, value)` data type for all animation data
2. **Cycle keyframe engine** -- `generate_cycle_keyframes(config)` produces sine-wave-based keyframes that loop seamlessly (frame 0 == frame N)
3. **5 gait configs at 2 speeds each** (10 total):
   - `BIPED_WALK_CONFIG` / `BIPED_RUN_CONFIG` -- anti-phase legs, arm swing, hip bob, spine counter-rotation
   - `QUADRUPED_WALK_CONFIG` / `QUADRUPED_RUN_CONFIG` -- diagonal-pair phasing (walk) / gallop (run), spine undulation
   - `HEXAPOD_WALK_CONFIG` / `HEXAPOD_RUN_CONFIG` -- alternating tripod gait, 6 upper leg bones
   - `ARACHNID_WALK_CONFIG` / `ARACHNID_RUN_CONFIG` -- 4-4 alternating groups, 8 upper leg bones
   - `SERPENT_WALK_CONFIG` / `SERPENT_RUN_CONFIG` -- wave propagation along 8-bone spine chain, no legs
4. **FLY_HOVER_CONFIG** -- wing bone oscillation with frequency/amplitude/glide_ratio params, body bob
5. **IDLE_CONFIG** -- subtle breathing on spine/chest bones, 48-frame cycle, all amplitudes < 0.1
6. **`get_gait_config(gait, speed, frame_count, bone_names)`** -- routing function with frame_count override and bone filtering
7. **8 attack type configs** (`ATTACK_CONFIGS`): melee_swing, thrust, slam, bite, claw, tail_whip, wing_buffet, breath_attack -- all with 3-phase timing (20% anticipation, 30% strike, 50% recovery)
8. **`generate_attack_keyframes(attack_type, frame_count, intensity)`** -- linear interpolation within phases, intensity scaling
9. **3 reaction configs** (`REACTION_CONFIGS`): death (progressive spine collapse), hit (4 directional torso rotations), spawn (compressed-to-neutral unfold)
10. **`generate_reaction_keyframes(reaction_type, direction, frame_count)`** -- directional hit support, death collapse sequence
11. **`generate_custom_keyframes(description, frame_count)`** -- text-to-keyframe mapper parsing verbs (raise, swing, curl, stomp, etc.) and body parts (wings, arms, head, tail, jaw, etc.) with bell-curve motion and multi-action sequencing via "then", "and", comma connectors

**`Tools/mcp-toolkit/tests/test_animation_gaits.py`** -- 109 tests across 13 test classes:
- TestKeyframeType (3), TestCycleGeneration (6), TestBipedConfigs (6), TestQuadrupedConfigs (6), TestHexapodConfigs (4), TestArachnidConfigs (4), TestSerpentConfigs (5), TestFlyConfig (5), TestIdleConfig (4), TestGetGaitConfig (18), TestAttackKeyframes (21), TestReactionKeyframes (12), TestCustomKeyframes (12), TestNoBlenderImports (3)

## Key design decisions

- All bone names use DEF- prefix matching Rigify output from Phase 4 templates
- Run configs have higher amplitude + shorter frame_count than walk configs for same gait
- Serpent uses Y-axis rotation (lateral wave) while most gaits use X-axis (forward/back)
- Custom keyframe parser uses word-boundary matching to avoid substring false positives (e.g. "swing" != "wing")
- `get_gait_config` returns a deep-enough copy to allow mutation without affecting global configs

## Verification

- 109/109 tests pass for animation_gaits module
- 591/591 tests pass for full suite (no regressions)
- No bpy/bmesh/mathutils imports in animation_gaits.py (verified by test)
