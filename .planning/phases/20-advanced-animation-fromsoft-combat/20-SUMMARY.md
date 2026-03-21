---
phase: 20
plan: "20-01, 20-02, 20-03"
subsystem: "Animation Pipeline"
tags: [combat-timing, blend-trees, additive-layers, ai-motion, cinematics, fromsoft]
dependency_graph:
  requires: [animation_gaits, animation_export, camera_templates, procedural_meshes]
  provides: [combat_timing, blend_trees, additive_layers, ai_motion, cinematic_sequences]
  affects: [blender_animation, unity_scene, unity_camera]
tech_stack:
  added: [requests-based-api-client, http-scheme-validation]
  patterns: [pure-logic-combat-timing, brand-parameterized-events, timeline-shot-composition]
key_files:
  created:
    - Tools/mcp-toolkit/blender_addon/handlers/_combat_timing.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/animation_templates.py
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/cinematic_templates.py
    - Tools/mcp-toolkit/tests/test_combat_timing.py
    - Tools/mcp-toolkit/tests/test_animation_templates.py
    - Tools/mcp-toolkit/tests/test_cinematic_templates.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/animation_export.py
decisions:
  - "FromSoft-style 3-phase timing (anticipation/active/recovery) with per-frame precision"
  - "Brand-specific VFX/sound parameterization for all 10 VeilBreakers brands"
  - "Procedural fallback for AI motion when no API endpoint is configured"
  - "requests library for HTTP API calls (avoids urllib file:// vulnerability)"
  - "Shot-based cinematic composition with cumulative timing and transition blending"
metrics:
  duration: "17 minutes"
  completed: "2026-03-21"
  tasks: 3
  files_created: 6
  files_modified: 1
  tests_added: 198
---

# Phase 20: Advanced Animation + FromSoft Combat Feel Summary

Combat timing system with 7 attack/movement presets, brand-parameterized animation events, root motion refinement, blend tree generation, additive animation layers, AI motion generation with API+procedural fallback, and cinematic Timeline sequences.

## Plan 20-01: Combat Timing + Animation Events + Root Motion Refinement

**Commit:** a207d62

### What was built

Pure-logic combat timing module (`_combat_timing.py`) implementing FromSoft-style animation feel:

- **COMBAT_TIMING_PRESETS**: 7 attack/movement types (light_attack, heavy_attack, charged_attack, combo_finisher, dodge_roll, parry, block) with precise frame timing at 30fps reference
- **configure_combat_timing**: FPS scaling (30->60->24 etc.), custom overrides, normalized time values (0.0-1.0), phase ranges
- **generate_animation_events**: Brand-parameterized event lists for Unity AnimationEvent injection. 6 event types: hit, vfx_spawn, sound_trigger, footstep, camera_shake, hitstop. All 10 VeilBreakers brands produce unique VFX/sound parameters
- **refine_root_motion**: Y-axis Gaussian smoothing (configurable passes), XZ drift snapping below threshold, loop boundary cleanup for seamless animation loops
- **generate_combat_animation_data**: Combined spec generator producing timing + events + root motion in a single dict

**Tests:** 84 (all passing)

## Plan 20-02: Blend Trees + Additive Animation Layers

**Commit:** 7bd8211

### What was built

Unity C# template generators (`animation_templates.py`):

- **generate_blend_tree_script**: 3 blend types:
  - `directional_8way`: 9-position 2D Freeform Directional (Idle + 8 directions) with moveX/moveY params
  - `speed_blend`: 1D Simple with 4 speed thresholds (Idle/Walk/Run/Sprint)
  - `directional_speed`: 2D Freeform Cartesian combining direction + speed
- **generate_additive_layer_script**: Base locomotion + configurable additive layers:
  - HitReactions layer (upper_body avatar mask, weight-controlled, 4 directional hit states)
  - Breathing layer (full_body mask, default weight 1.0, idle variation)
  - Custom layer support with Override or Additive blend modes

**Tests:** 47 (all passing)

## Plan 20-03: AI Motion + Cinematic Sequences

**Commit:** a5c334d

### What was built

1. **AI Motion Generation** (replaced stub in `animation_export.py`):
   - `_validate_ai_motion_params`: Pure-logic validation for prompt, model (3 options), fps, style (4 options), duration
   - `_attempt_ai_motion_api`: HTTP POST to configurable endpoint (VB_AI_MOTION_ENDPOINT env var) with http/https scheme validation
   - `handle_generate_ai_motion`: Full implementation with API -> procedural fallback pipeline. Fallback uses text-to-keyframe parser + combat timing enrichment for attack keywords. Style scaling (realistic=1.0, stylized=1.3, exaggerated=1.8, subtle=0.6)

2. **Cinematic Sequences** (`cinematic_templates.py`):
   - `validate_shots`: Pure-logic validation for camera positions, targets, durations, transitions (5 types), character actions (9 types)
   - `generate_cinematic_script`: Timeline-based cinematic with Cinemachine virtual cameras per shot, CinemachineRotationComposer look-at targets, shot-sequential clip timing, transition blending (crossfade/fade), PlayableDirector setup, activation markers, audio track placeholder

**Tests:** 67 (all passing)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] C# JSON bracket imbalance in error handler strings**
- **Found during:** Plan 20-02
- **Issue:** Non-f-string error handler JSON had literal `}}` instead of `}`, causing unbalanced C# braces
- **Fix:** Changed `"\\"}}";` to `"\\"}";` in both blend tree and additive layer error handlers
- **Files modified:** animation_templates.py
- **Commit:** 7bd8211

**2. [Rule 2 - Security] urllib file:// scheme vulnerability**
- **Found during:** Plan 20-03
- **Issue:** urllib.request.urlopen supports file:// schemes, allowing potential file access via malicious endpoint
- **Fix:** Replaced urllib with requests library + explicit http/https scheme validation
- **Files modified:** animation_export.py
- **Commit:** a5c334d

## Decisions Made

1. **FromSoft 3-phase timing model**: Each attack has clear anticipation -> active -> recovery with hit/VFX/sound frames within the active window. This mirrors Dark Souls/Elden Ring animation philosophy.
2. **Brand parameterization**: All 10 brands (IRON, SAVAGE, SURGE, etc.) produce unique VFX color, impact type, and trail type for animation events.
3. **Procedural AI motion fallback**: When no API endpoint is configured, the system falls back to existing text-to-keyframe parsing + combat timing enrichment. This ensures the tool always produces output.
4. **requests over urllib**: Used requests library for HTTP API calls to avoid file:// scheme vulnerability flagged by static analysis.
5. **Shot-based cinematic composition**: Shots define camera position/target/duration/transition and are laid out sequentially on a Timeline with cumulative start times.

## Known Stubs

None. The AI motion handler's `_attempt_ai_motion_api` returns None when no endpoint is configured, which triggers the procedural fallback -- this is intentional design, not a stub.

## Test Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| test_combat_timing.py | 84 | All passing |
| test_animation_templates.py | 47 | All passing |
| test_cinematic_templates.py | 67 | All passing |
| **Total Phase 20** | **198** | **All passing** |

Full suite: 7712 passed, 2 pre-existing failures (Gemini/ElevenLabs client -- unrelated).

## Self-Check: PASSED

All 6 created files verified on disk. All 3 commit hashes (a207d62, 7bd8211, a5c334d) verified in git log. Modified file (animation_export.py) confirmed present.
