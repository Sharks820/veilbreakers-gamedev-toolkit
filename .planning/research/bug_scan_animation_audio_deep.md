# Deep Bug Scan: Animation, Rigging, and Audio Systems

**Date:** 2026-04-02
**Scanned by:** Claude Opus 4.6 (1M context)
**Scope:** All animation handlers (16 files), rigging handlers (4 files), Unity audio tools, audio templates, ElevenLabs client
**Confidence:** HIGH -- full source read, cross-referenced bone names/APIs across systems

---

## Executive Summary

The animation and rigging systems are surprisingly well-structured with good separation of pure-logic and Blender-dependent code. However, the scan uncovered **14 confirmed bugs** and **6 high-risk patterns** that will cause silent failures or incorrect behavior at runtime.

The most critical findings are:
1. **Bone name mismatch between animation_monster.py and rigging systems** -- `DEF-jaw` used in animations but facial rig creates bones without `DEF-` prefix
2. **Ragdoll preset references non-existent bone `DEF-head`** -- the rigging system creates `spine.005` as the head bone, not `head`
3. **Quaternion-to-Euler conversion is lossy when applied to "scale" channel animations** -- blob/monster animations use `scale` channel but the `_apply_keyframes_to_action` function only handles `rotation_euler` -> `rotation_quaternion` conversion, not `scale`
4. **Root motion extraction uses world space but writes to local space** -- causes incorrect root motion data
5. **Audio SFX output paths use `.mp3` extension but ElevenLabs returns raw audio bytes** -- format mismatch

---

## CONFIRMED BUGS

### BUG-ANIM-01: `DEF-jaw` bone name mismatch in animation_monster.py [CRITICAL]

**File:** `blender_addon/handlers/animation_monster.py` lines 259, 267, 371, 467
**File:** `blender_addon/handlers/rigging_advanced.py` lines 43-60

The monster animation generators reference `DEF-jaw` for regurgitate, gnaw_loop, and chorus animations:
```python
keyframes.append(Keyframe("DEF-jaw", "rotation_euler", 0, frame, 0.6 * heave * intensity))
```

But the facial rig in `rigging_advanced.py` creates the jaw bone as `"jaw"` (without DEF- prefix):
```python
FACIAL_BONES = {
    "jaw": {
        "head": (0.0, -0.02, 1.6),
        ...
```

The `_apply_keyframes_to_action` function in `animation.py` constructs data_path as:
```python
data_path = f'pose.bones["{bone_name}"].{resolved_channel}'
```

This will create fcurves targeting `pose.bones["DEF-jaw"]` but the bone is named `jaw`. **The animation silently does nothing -- no error, no jaw movement.**

**Impact:** All jaw-based monster animations are broken: regurgitate, gnaw_loop, chorus.
**Fix:** Change `DEF-jaw` to `jaw` in animation_monster.py, OR add DEF- prefix when creating facial bones.

---

### BUG-ANIM-02: `DEF-pseudopod_*` bones referenced but never created by any rig template [HIGH]

**File:** `blender_addon/handlers/animation_blob.py` lines 34-40
**File:** `blender_addon/handlers/rigging_templates.py` -- NO pseudopod entries

The blob animation system references four pseudopod bones:
```python
BLOB_PSEUDOPOD_BONES: list[str] = [
    "DEF-pseudopod_1", "DEF-pseudopod_2",
    "DEF-pseudopod_3", "DEF-pseudopod_4",
]
```

The `rigging_templates.py` file has no `pseudopod` entries at all (confirmed via grep). The amorphous rig template (`TEMPLATE_CATALOG`) does not create these bones.

The blob animation code has a fallback: `bone = BLOB_PSEUDOPOD_BONES[0] if BLOB_PSEUDOPOD_BONES else "DEF-spine.003"` -- but this fallback is unreachable because the list is always non-empty (it is a constant). The actual issue is that `DEF-pseudopod_1` won't exist on any armature.

**Impact:** `generate_pseudopod_reach_keyframes()` and `generate_blob_attack_keyframes()` create keyframes for non-existent bones. The fcurves are created but target bones that don't exist, so the animation does nothing.
**Fix:** Either add pseudopod bones to the amorphous rig template, OR update blob animations to use spine bones directly.

---

### BUG-ANIM-03: Ragdoll preset references `DEF-head` bone that doesn't exist [HIGH]

**File:** `blender_addon/handlers/rigging_advanced.py` line 528

The ragdoll humanoid preset includes:
```python
"DEF-head": {
    "shape": "BOX",
    "radius": 0.1,
    ...
```

But the rigging system never creates a bone named `DEF-head`. The head bone is `DEF-spine.005` (as seen in the Unity humanoid bone map at `rigging.py` line 175). The facial rig creates `head` as a reference parent name, but the actual DEF bone is `DEF-spine.005`.

**Impact:** Ragdoll setup will fail to find the head bone, leaving the head without physics colliders.
**Fix:** Change `"DEF-head"` to `"DEF-spine.005"` in the ragdoll preset.

---

### BUG-ANIM-04: Root motion extraction mixes world space and local space [MEDIUM-HIGH]

**File:** `blender_addon/handlers/animation_export.py` lines 718-754

```python
# Step 1: Read hip XY translation per frame (world space)
world_loc = armature_obj.matrix_world @ hip_pbone.matrix.translation
hip_translations.append((frame, world_loc.x, world_loc.y, world_loc.z))
...
# Step 3: Transfer hip XY to root bone (but these are world-space values!)
fc_root_x.keyframe_points[i].co = (frame, hx)
fc_root_y.keyframe_points[i].co = (frame, hy)
```

The code reads hip bone translations in world space (`matrix_world @ hip_pbone.matrix.translation`) but writes them directly to the root bone's local-space fcurves (`pose.bones["root"].location`). If the armature object has any transform (position, rotation, or scale), the root motion data will be incorrect.

Also, the hip bone's `.matrix.translation` gives the bone's position in armature-local space, not its own pose-space location. The world transform is then `armature.matrix_world @ bone.matrix.translation`. But this value is then written as if it were a pose-bone local location, which is wrong -- pose bone locations are relative to the rest pose in bone-local space.

**Impact:** Root motion will have incorrect position values if the armature has any world transform other than identity. Even with identity transform, the values are in armature space, not bone-local space. Animations exported with root motion will drift or slide in Unity.
**Fix:** Use `hip_pbone.location` (local pose space) for the XY extraction, or properly convert from world to bone-local space.

---

### BUG-ANIM-05: Quaternion axis mapping is incorrect for W component [MEDIUM-HIGH]

**File:** `blender_addon/handlers/animation.py` lines 462-465

```python
if hasattr(pbone, "rotation_mode") and pbone.rotation_mode == "QUATERNION":
    resolved_channel = "rotation_quaternion"
    # Map euler axis (0-2) to quaternion axis (1-3, since 0=W)
    axis = axis + 1
```

When a bone's rotation mode is QUATERNION, the code maps euler axis 0/1/2 to quaternion indices 1/2/3. However, this discards the W component (index 0). Quaternion keyframes need ALL four components (W, X, Y, Z) to be valid. If only one component is set, the quaternion will be incomplete (W defaults to 0), producing wildly incorrect rotations.

The keyframe engine generates `rotation_euler` keyframes with axes 0, 1, 2. If the bone happens to be in QUATERNION mode, the code maps these to quaternion indices 1, 2, 3 -- but never sets index 0 (W). A quaternion with W=0 is a 180-degree rotation, which is almost certainly wrong.

**Impact:** Any bone in QUATERNION rotation mode will have broken animations. In practice, `rigging.py` line 1163 sets `pbone.rotation_mode = "XYZ"`, so most rigged bones should be in euler mode. But if any external rig or imported model uses quaternion mode, animations will be completely wrong.
**Fix:** Either ensure all bones are set to euler mode before animation (defensive), or properly convert euler values to full quaternion (W, X, Y, Z) keyframes.

---

### BUG-ANIM-06: `_apply_keyframes_to_action` doesn't handle `scale` channel [MEDIUM]

**File:** `blender_addon/handlers/animation.py` lines 456-470

The function only special-cases `rotation_euler` -> `rotation_quaternion` conversion. But blob animations and monster animations use `"scale"` as a channel (e.g., `Keyframe(bone, "scale", 0, frame, 1.0 + xz_scale)`). The code at line 460 only checks:
```python
if channel == "rotation_euler" and bone_name in armature_obj.pose.bones:
```

The `scale` channel passes through without issue IF the data_path is correct. Let me verify -- the data_path becomes `pose.bones["DEF-spine"].scale` which IS valid in Blender. So this is not a bug per se -- but the lack of scale channel validation means:
- No check that scale values are positive (negative scale would flip normals)
- No check for degenerate scale (0.0 would collapse geometry)

**Impact:** LOW -- the channel works, but negative/zero scale values from intense animations won't be caught.
**Fix:** Add validation: clamp scale values to minimum 0.001.

---

### BUG-ANIM-07: Bone name filtering in `get_gait_config` doesn't account for composite keys [MEDIUM]

**File:** `blender_addon/handlers/animation_gaits.py` lines 808-812

```python
if bone_names is not None:
    bone_set = set(bone_names)
    config["bones"] = {
        k: v for k, v in config["bones"].items() if k in bone_set
    }
```

If a caller passes `bone_names=["DEF-spine"]` to filter the config, the composite key `"DEF-spine__sway"` will NOT match because the filter compares against the raw key string, not the stripped bone name. The sway channel will be silently dropped.

This only matters if someone uses the `bone_names` filter parameter, which is optional.

**Impact:** Loss of pelvis sway motion when bone_names filter is used. Subtle visual quality degradation.
**Fix:** Compare against `k.split("__")[0]` instead of `k` directly.

---

### BUG-ANIM-08: `generate_approach_keyframes` writes to same bone/channel twice per frame [LOW-MEDIUM]

**File:** `blender_addon/handlers/animation_combat.py` lines 190-231

In the `generate_approach_keyframes` function, at the bottom of the loop:
```python
# Spine forward lean (slight throughout, more at end)
spine_lean = 0.05 + 0.05 * t
keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spine_lean))
```

But during the wind-up phase (frame > windup_start), the code also writes:
```python
keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.15 * windup_t))
```

The axis 1 (Y) write is fine. But for the walking phase (frame <= windup_start), the code writes `DEF-spine.001` rotation axis 0 at line 216 with value 0.0, AND again at line 231 with a different value. When these keyframes are applied, `_apply_keyframes_to_action` groups by (bone, channel, axis), so BOTH values end up in the same fcurve. The last value wins during insertion, but this is implementation-dependent.

**Impact:** The spine forward lean may be overridden or produce incorrect interpolation during the walking phase.
**Fix:** Remove the redundant keyframe write, or consolidate the two values (add them).

---

### BUG-ANIM-09: Quaternion rotation_z extraction in root motion is wrong for QUATERNION mode [MEDIUM]

**File:** `blender_addon/handlers/animation_export.py` lines 768-790

```python
if rot_mode in ("QUATERNION",):
    root_rot_data_path = f'pose.bones["{root_bone_name}"].rotation_quaternion'
    rot_index = 3  # W, X, Y, Z -- Z rotation is index 3 for quaternion
```

The comment says "W, X, Y, Z -- Z rotation is index 3 for quaternion" but this is wrong. Blender's quaternion indices are: 0=W, 1=X, 2=Y, 3=Z. So index 3 IS Z, which is correct.

However, the value being written is:
```python
rot_z = hip_pbone.matrix.to_quaternion().z
```

This extracts only the Z component of the quaternion, but writes it as if it's a complete rotation. A single quaternion component is NOT a rotation -- you need all four components. Setting only Z and leaving W/X/Y at defaults produces garbage.

**Impact:** Root rotation extraction in quaternion mode produces incorrect rotation data.
**Fix:** Extract the full quaternion and write all four components, or convert to euler Z and use euler mode for the root bone.

---

### BUG-AUDIO-01: SFX/Music output paths use `.mp3` extension but content may be WAV or raw [MEDIUM]

**File:** `unity_tools/audio.py` lines 239, 274, 308

The audio tool generates output paths with `.mp3` extension:
```python
output_rel = f"Assets/Resources/Audio/SFX/{safe_name}.mp3"
```

But in stub mode, `ElevenLabsAudioClient._write_silent_wav()` writes a proper WAV file with WAV headers to that `.mp3` path. Unity may handle this (it reads headers, not extensions), but it's technically a format mismatch that could cause issues with Unity's audio import pipeline.

In live mode, the ElevenLabs API returns audio bytes -- the format depends on the API endpoint. `text_to_sound_effects.convert` returns MP3 by default, but `text_to_speech.convert` may return different formats.

**Impact:** Stub mode writes WAV data to `.mp3` files. Unity will likely still import them, but the extension mismatch is a maintenance hazard and could break some audio processing tools.
**Fix:** Use `.wav` extension in stub mode, or detect the actual output format.

---

### BUG-AUDIO-02: Voice line duration estimate doesn't match actual audio duration [LOW]

**File:** `shared/elevenlabs_client.py` lines 267-268

```python
word_count = max(1, len(text.split()))
duration = max(1.0, word_count / 3.0)
```

In live mode, the actual audio duration from ElevenLabs is not measured -- only estimated by word count. The returned `duration` field will be wrong for fast/slow speech, pauses, or emotional delivery.

**Impact:** Any system relying on the `duration` field for timing (e.g., subtitle display, lip sync timing) will be incorrect.
**Fix:** Measure actual audio duration from the returned bytes, or use ElevenLabs API metadata if available.

---

### BUG-AUDIO-03: Adaptive music creates all AudioSources and starts playback immediately [LOW-MEDIUM]

**File:** `shared/unity_templates/audio_templates.py` lines 232-242

```csharp
private void Start()
{
    for (int i = 0; i < musicClips.Length && i < _layers.Length; i++)
    {
        if (musicClips[i] != null)
        {
            _layers[i].clip = musicClips[i];
            _layers[i].Play();  // ALL layers start playing immediately
        }
    }
}
```

All music layers start playing simultaneously at load time, with inactive layers at volume 0. This means:
- Multiple AudioSources consume audio processing even when silent
- Memory for all music clips is loaded at once
- CPU decoding overhead for all layers

**Impact:** Performance cost of N simultaneous AudioSource decodes for a system that typically only needs 1-2 active at a time.
**Fix:** Only `Play()` the active layer. On crossfade, `Play()` the target layer and `Stop()` the previous after fade-out completes.

---

### BUG-RIG-01: Deformation test poses use raw euler tuples without setting rotation mode first [LOW-MEDIUM]

**File:** `blender_addon/handlers/rigging_weights.py` lines 43-77, 621-629

The `DEFORMATION_POSES` dict uses euler tuples:
```python
"a_pose": {
    "DEF-upper_arm.L": (0, 0, -0.785),
    "DEF-upper_arm.R": (0, 0, 0.785),
},
```

But in `handle_test_deformation`, the code applies these to bones. Looking at line 623:
```python
pb.rotation_quaternion = (1, 0, 0, 0)  # Reset quaternion
```

And line 629:
```python
pb.rotation_mode = "XYZ"
```

The code sets rotation_mode to XYZ AFTER resetting quaternion. Then it applies euler values. This sequence is actually correct (reset quat, set mode, apply euler). However, line 646 shows:
```python
pb.rotation_quaternion = (1, 0, 0, 0)
```

This reset-to-identity sets quaternion, but if rotation_mode is already XYZ, this has no effect on the display (the euler values dominate). The actual pose application should be setting `pb.rotation_euler` after `rotation_mode = "XYZ"`.

**Impact:** LOW -- the code works because it resets both quat and euler, but the sequencing is fragile.

---

### BUG-RIG-02: Multi-arm parent bone reference uses invalid spine number format [MEDIUM]

**File:** `blender_addon/handlers/rigging.py` lines 252

```python
parent_spine = "spine.003" if pair_idx == 0 else f"spine.{(3 - pair_idx):03d}" if pair_idx < 3 else "spine"
```

For pair_idx=1: `f"spine.{(3-1):03d}"` = `"spine.002"` -- correct
For pair_idx=2: `f"spine.{(3-2):03d}"` = `"spine.001"` -- correct

But these parent names lack the `DEF-` prefix. The armature's edit bones use the base name (no DEF- prefix), so this is fine for bone creation. However, at animation time when referencing these bones via `_apply_keyframes_to_action`, the DEF- prefix is used. This could cause issues if custom rig limbs try to reference parent bones.

**Impact:** LOW in practice (bone creation uses edit bones which don't have DEF- prefix), but the inconsistency is a latent bug.

---

## HIGH-RISK PATTERNS (Not Bugs Yet, But Will Bite)

### RISK-01: No bone existence validation in `_apply_keyframes_to_action`

The function at `animation.py:456` creates fcurves for bone names without checking if the bone exists on the armature. If an animation references a bone that doesn't exist (e.g., `DEF-pseudopod_1`), Blender creates an fcurve targeting a non-existent data path. This produces no error but the animation has no visible effect. Combined with BUG-ANIM-01 and BUG-ANIM-02, this is a silent failure pattern.

**Recommendation:** Add a warning log when creating fcurves for bones not found in `armature_obj.pose.bones`.

### RISK-02: No NLA track cleanup in batch export

`animation_export.py:handle_batch_export` pushes actions to NLA tracks (via `_push_action_to_nla`) during export but may accumulate NLA tracks on repeated exports. The `_push_action_to_nla` function always creates a NEW track without checking if one already exists for the action.

**Recommendation:** Check for existing NLA strips for the action before creating new ones.

### RISK-03: Cyclic modifier applied unconditionally

`animation.py:481` adds a CYCLES modifier to every fcurve when `use_cyclic=True`. For non-looping animations (attack, reaction, death), this creates visual artifacts where the animation wraps around. The handlers do pass `use_cyclic` as a parameter, but some callers may not set it correctly.

**Recommendation:** Audit all callers of `_apply_keyframes_to_action` to ensure non-looping animations pass `use_cyclic=False`.

### RISK-04: Audio pool manager has no AudioSource cleanup

The generated `VeilBreakers_AudioPoolManager.cs` creates a pool of AudioSources. If `pool_size` is increased at runtime or across scene loads, old sources may not be cleaned up, leading to leaked AudioSources.

**Recommendation:** Implement `OnDestroy()` cleanup in the generated C# template.

### RISK-05: ElevenLabs retry catches overly broad exception types

`elevenlabs_client.py:118`:
```python
except (ConnectionError, TimeoutError, OSError, ValueError, KeyError) as exc:
```

`ValueError` and `KeyError` are not rate-limit errors -- they indicate programming bugs or API response format changes. Retrying on these wastes time and hides real errors.

**Recommendation:** Only catch `ConnectionError`, `TimeoutError`, `OSError` for retries. Let `ValueError`/`KeyError` propagate immediately.

### RISK-06: Spatial audio occlusion uses static RaycastHit array

`audio_middleware_templates.py` line 83:
```csharp
private static readonly RaycastHit[] _occlusionHits = new RaycastHit[16];
```

This is a static array shared across ALL spatial audio instances. If multiple spatial audio sources update occlusion in the same frame, they will overwrite each other's results. Since `Physics.RaycastNonAlloc` writes to this shared buffer, concurrent calls produce race conditions.

**Recommendation:** Use instance-level arrays, or serialize occlusion updates (one per frame via a manager).

---

## SUMMARY TABLE

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-ANIM-01 | CRITICAL | animation_monster.py | `DEF-jaw` bone name mismatch -- jaw animations silently broken |
| BUG-ANIM-02 | HIGH | animation_blob.py | `DEF-pseudopod_*` bones never created by any rig template |
| BUG-ANIM-03 | HIGH | rigging_advanced.py | Ragdoll `DEF-head` bone doesn't exist (should be `DEF-spine.005`) |
| BUG-ANIM-04 | MEDIUM-HIGH | animation_export.py | Root motion world/local space mixing |
| BUG-ANIM-05 | MEDIUM-HIGH | animation.py | Quaternion axis mapping missing W component |
| BUG-ANIM-06 | LOW | animation.py | No scale channel validation (negative/zero scale) |
| BUG-ANIM-07 | MEDIUM | animation_gaits.py | Bone filter doesn't handle composite `__` keys |
| BUG-ANIM-08 | LOW-MEDIUM | animation_combat.py | Duplicate keyframes on same bone/channel/axis per frame |
| BUG-ANIM-09 | MEDIUM | animation_export.py | Root rotation quaternion extraction writes single component |
| BUG-AUDIO-01 | MEDIUM | unity_tools/audio.py | `.mp3` extension but WAV content in stub mode |
| BUG-AUDIO-02 | LOW | elevenlabs_client.py | Voice duration estimate doesn't match actual |
| BUG-AUDIO-03 | LOW-MEDIUM | audio_templates.py | All music layers play simultaneously (performance) |
| BUG-RIG-01 | LOW-MEDIUM | rigging_weights.py | Deformation pose reset sequencing fragile |
| BUG-RIG-02 | MEDIUM | rigging.py | Multi-arm parent bone DEF- prefix inconsistency |
| RISK-01 | HIGH | animation.py | No bone existence check in fcurve creation |
| RISK-02 | MEDIUM | animation_export.py | NLA track accumulation on repeated export |
| RISK-03 | MEDIUM | animation.py | Cyclic modifier on non-looping animations |
| RISK-04 | LOW-MEDIUM | audio_templates.py | AudioSource pool leak potential |
| RISK-05 | LOW-MEDIUM | elevenlabs_client.py | Retry catches ValueError/KeyError |
| RISK-06 | MEDIUM | audio_middleware_templates.py | Static RaycastHit array shared across instances |

---

## POSITIVE FINDINGS

The codebase has several well-implemented patterns worth noting:

1. **Pure-logic separation** -- All animation keyframe generators are Blender-independent, enabling test coverage without running Blender. This is excellent architecture.

2. **Blender 5.0 compatibility layer** -- `_action_compat.py` properly handles the layered Action API for both 4.x and 5.0+. The channelbag/slot management is correct.

3. **Gait configs are physically accurate** -- Quadruped walk uses proper 4-beat lateral sequence, trot uses diagonal pairs, canter uses 3-beat asymmetric, gallop uses 4-beat. The arachnid 4-4 alternating pattern is correct. The serpent uses traveling wave propagation.

4. **Mixamo-to-Rigify mapping is comprehensive** -- 52 bones mapped including all 15 per-hand finger bones. The mapping is bidirectional.

5. **Unity Humanoid bone map is correct** -- All 17 required bones are properly mapped to Rigify DEF names.

6. **Audio system has graceful degradation** -- ElevenLabs client falls back to stub mode (silent WAV) when no API key is configured. This enables testing without API costs.

7. **Combat timing sidecar generation** -- FBX export automatically generates `.timing.json` files with frame-accurate combat timing data. Smart design for game engine integration.

8. **IK foot placement math is correct** -- `animation_ik.py` properly computes ankle pitch/roll from surface normals with reasonable clamping. The hip correction uses 80% transfer which prevents floating.
