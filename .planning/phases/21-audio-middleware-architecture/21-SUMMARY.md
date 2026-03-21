---
phase: "21"
plan: "21-01 through 21-03"
subsystem: audio-middleware
tags: [spatial-audio, audio-lod, layered-sound, event-chains, foley, dynamic-music, portal-audio, vo-pipeline]
dependency_graph:
  requires: [phase-7-audio-foundation]
  provides: [spatial-audio-system, audio-lod, layered-sound, audio-event-chains, procedural-foley, dynamic-music, portal-audio, vo-pipeline]
  affects: [unity_audio, runtime-audio]
tech_stack:
  added: [audio-middleware-templates]
  patterns: [dict-return-pattern, runtime-monobehaviour, scriptable-object-data, coroutine-sequencing, singleton-music-manager]
key_files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/audio_middleware_templates.py
    - Tools/mcp-toolkit/tests/test_audio_middleware.py
  modified: []
decisions:
  - Runtime MonoBehaviours only (no UnityEditor imports) for all middleware components
  - Dict return pattern (script_path, script_content, next_steps) matching newer Phase 20+ convention
  - ScriptableObject for data-driven configs (layered sounds, event chains, VO database)
  - Coroutine-based sequencing for event chains and crossfades
  - Singleton pattern for DynamicMusic manager (persists across scenes)
  - Physics.RaycastAll multi-ray for accurate occlusion sampling
  - Enum-based tier system for Audio LOD with configurable thresholds
  - Priority-based queue for VO playback with interruption support
metrics:
  duration: "9 minutes"
  completed: "2026-03-21"
  tasks_completed: 8
  tests_added: 157
  files_created: 2
requirements_fulfilled: [AUDM-01, AUDM-02, AUDM-03, AUDM-04, AUDM-05, AUDM-06, AUDM-07, AUDM-08]
---

# Phase 21: Audio Middleware Architecture Summary

Wwise/FMOD-level audio architecture in Unity without middleware cost -- 8 template generators covering spatial audio with geometry occlusion, layered sound design, sequenced event chains, dynamic music with horizontal re-sequencing and vertical stem layering, portal-based room propagation, distance-based audio LOD, dialogue/VO pipeline with lip sync and localization, and procedural movement foley.

## What Was Built

### AUDM-01: Spatial Audio System (`generate_spatial_audio_script`)
- 3D AudioSource with spatialBlend=1.0, configurable doppler, spread angle
- Distance attenuation: logarithmic, linear, or custom AnimationCurve rolloff
- Geometry occlusion via Physics.RaycastAll (multi-ray sampling for accuracy)
- AudioLowPassFilter for muffled through-wall sound
- Smooth occlusion transitions with configurable damping

### AUDM-06: Audio LOD System (`generate_audio_lod_script`)
- 4-tier distance-based quality: Full / Reduced / Minimal / Culled
- Full: all channels, full sample rate, highest priority
- Reduced: mono downmix, lower priority (configurable distance threshold)
- Minimal: simplified sound, lowest priority, volume reduction
- Culled: AudioSource.enabled = false (zero CPU cost)
- Periodic update interval to avoid per-frame overhead

### AUDM-02: Layered Sound Design (`generate_layered_sound_script`)
- VB_SoundLayer: per-layer AudioClip, volume, pitch, delay, random variation
- ScriptableObject data asset for designer-friendly configuration
- Coroutine-delayed playback for precise timing between layers
- Random pitch/volume per layer for natural variation
- Example: sword_impact = metal_clang + bone_crack + cloth_rustle

### AUDM-03: Audio Event Chains (`generate_audio_event_chain_script`)
- VB_AudioEvent: clip, delay_ms, volume, pitch, spatial_blend, condition
- ScriptableObject chain definitions with cooldown and interruption control
- Condition-based event filtering (game state checks)
- Source pool for concurrent event playback
- Example: impact(0ms) -> reverb_tail(50ms) -> debris_scatter(200ms)

### AUDM-08: Procedural Foley (`generate_procedural_foley_script`)
- Surface detection via Physics.Raycast + PhysicMaterial name matching
- 7 default surface materials: stone, wood, metal, dirt, grass, water, snow
- 4 armor types with distinct foley: plate (clinks), leather (creaks), cloth (rustles), chain
- Speed-based volume scaling: idle/walk/run/sprint
- Animation event integration: OnFootstep(), OnClothRustle(), OnArmorClink()
- Separate AudioSources for footsteps and armor sounds

### AUDM-04: Dynamic Music System (`generate_dynamic_music_script`)
- Horizontal re-sequencing: 8 sections with A/B source crossfading
- Vertical layering: 5 stems (drums, bass, melody, pads, percussion) with independent volume
- VB_StemMix: per-section stem volume presets
- VB_MusicTransition: custom crossfade duration and bar-aligned transitions
- Combat stingers: one-shot clips for EnemySpotted, BossPhaseChange, PlayerDeath, etc.
- Singleton pattern with DontDestroyOnLoad

### AUDM-05: Portal Audio Propagation (`generate_portal_audio_script`)
- VeilBreakers_AudioRoom: room volumes with AudioReverbZone + ambient clips
- VeilBreakers_AudioPortal: doorway components connecting two rooms
- PortalDoorState: Open / PartiallyOpen / Closed with configurable attenuation
- Low-pass filtering for muffled through-door sound
- SetDoorOpenness(float) for smooth interpolated transitions
- Room source registration for per-room audio management

### AUDM-07: Dialogue/VO Pipeline (`generate_vo_pipeline_script`)
- VB_VOEntry: clip, subtitle, emotion tag, viseme markers, priority
- VODatabase ScriptableObject with ID-based lookup
- VOPlayer MonoBehaviour with playback, subtitles, lip sync events
- 8 emotion types: Neutral, Aggressive, Despair, Joy, Fear, Sarcasm, Commanding, Whisper
- VB_VisemeMarker with timed viseme indices for lip sync
- Localization: locale-indexed clip/subtitle arrays
- Priority-based interruption queue with ClearQueue/StopCurrentVO

## Deviations from Plan

None -- plan executed exactly as written. All 8 requirements implemented in a single template module with comprehensive tests.

## Decisions Made

1. **Runtime-only scripts**: All 8 generators produce runtime MonoBehaviours/ScriptableObjects (no UnityEditor imports), ensuring they work in builds.
2. **Dict return pattern**: Each generator returns `{script_path, script_content, next_steps}` matching the newer convention (unlike Phase 7 which returned raw strings).
3. **Single module**: All 8 generators in one `audio_middleware_templates.py` file for cohesion -- they share helper patterns and are conceptually one "audio middleware layer."
4. **Coroutine sequencing**: Event chains and music crossfades use Unity coroutines for frame-accurate timing without Update() polling.
5. **Multi-ray occlusion**: Spatial audio uses 3 rays (center + offset) for more accurate geometry occlusion than single-ray.

## Test Results

- **157 new tests** across 10 test classes (8 per-generator + 2 cross-cutting)
- All tests pass (157/157)
- Full regression suite: 7869 passed, 2 pre-existing failures (environment stubs), 38 skipped
- Total project tests: 7869 (up from 7712)

## Known Stubs

None -- all generators produce complete, functional C# templates with no placeholder data.

## Commits

| Hash | Message |
|------|---------|
| 458320d | feat(21): audio middleware architecture -- 8 template generators, 157 tests |

## Self-Check: PASSED

- [x] audio_middleware_templates.py exists
- [x] test_audio_middleware.py exists
- [x] 21-SUMMARY.md exists
- [x] Commit 458320d exists
- [x] 157/157 tests pass
- [x] Full regression suite passes (7869 passed)
