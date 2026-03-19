# Phase 5: Animation - Research

**Researched:** 2026-03-19
**Domain:** Blender Python animation pipeline -- procedural keyframe generation, NLA management, retargeting, FBX export
**Confidence:** HIGH

## Summary

This phase builds a complete creature animation pipeline as Blender addon handlers, following the same compound MCP tool pattern used across 8 existing tools (40+ handlers). The core work is procedural keyframe math (sine waves, phase offsets, parametric curves) applied to DEF bones from the Phase 4 rig templates. Blender's Python API provides all the primitives needed: `bpy.data.actions.new()` creates Actions, `action.fcurves.new()` creates F-curves per bone channel, `fcurve.keyframe_points.insert(frame, value)` sets keys, and `NlaTrack.strips.new()` pushes actions to the NLA stack for batch FBX export.

The biggest implementation risk is the combinatorial complexity of gait types (5) times creature templates (10) times action types (walk/run/idle/attack/death/etc). The mitigation strategy is a shared keyframe engine with per-gait configuration dicts -- the math is the same, only the bone names, phase offsets, and amplitude tables change. Pure-logic separation (established in Phase 2+) enables testing all keyframe math without Blender.

**Primary recommendation:** Build a shared `_keyframe_engine` module that all procedural handlers call into, parameterized by gait config dicts. One new compound tool `blender_animation` with ~12 actions. Target 2 new handler files: `animation.py` (procedural cycles, combat, custom) and `animation_export.py` (preview, root motion, retarget, batch export).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Walk/run cycles generated procedurally using keyframe math (sine waves for leg cycles, phase offsets per gait type)
- 5 gait types: biped, quadruped, hexapod, arachnid, serpent -- each with unique foot placement patterns
- Fly/hover cycles use wing bone oscillation with adjustable frequency, amplitude, and glide ratio
- Idle animations use subtle breathing (chest/spine), weight shift, and secondary motion
- Attack types: melee swing, thrust, slam, bite, claw, tail whip, wing buffet, breath attack
- Death, hit reaction (directional), and spawn animations from parametric descriptions
- Custom animation from text description maps to keyframe sequences on rig bones
- Contact sheet preview renders every Nth frame from multiple angles using existing render infrastructure
- AI motion generation stub for HY-Motion/MotionGPT (API integration placeholder)
- Mixamo animation retargeting maps standard Mixamo bone names to custom rig bone names
- Retargeting uses constraint-based approach matching Phase 4 rig retargeting pattern
- Root motion extraction separates hip/root translation from animation curves
- Animation events mark contact frames (footsteps, hit impacts) as NLA markers
- Batch export produces separate FBX files per animation clip with Unity-compatible naming

### Claude's Discretion
All implementation choices at Claude's discretion -- autonomous execution mode.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ANIM-01 | Procedural walk/run cycle (biped, quadruped, hexapod, arachnid, serpent gaits) | Sine-wave keyframe engine with per-gait config dicts; bone names from TEMPLATE_CATALOG |
| ANIM-02 | Procedural fly/hover cycle (wing frequency, amplitude, glide ratio) | Wing bone oscillation using same keyframe engine; freq/amp/glide as parameters |
| ANIM-03 | Procedural idle animation (breathing, weight shift, secondary motion) | Low-amplitude sine waves on spine/chest bones; random weight shift offsets |
| ANIM-04 | Attack animations (melee swing, thrust, slam, bite, claw, tail whip, wing buffet, breath attack) | Parametric keyframe sequences with anticipation-strike-recovery phases; config per attack type |
| ANIM-05 | Death, hit reaction (directional), and spawn animations | Parametric templates with direction parameter for hit reactions; collapse sequences for death |
| ANIM-06 | Custom animation from text description | Keyword-to-keyframe mapping engine; parse verbs/body parts from description text |
| ANIM-07 | Animation contact sheet preview | Reuse existing render_contact_sheet with frame stepping; set scene frame before each render |
| ANIM-08 | Secondary motion physics (jiggle on tails, ears, capes, hair) | Build on Phase 4 spring bone constraints; bake physics sim to keyframes via NLA bake |
| ANIM-09 | Root motion extraction and animation events for Unity | Extract hip XY translation to root bone; pose_markers for contact frame events |
| ANIM-10 | Mixamo retargeting to custom rigs | MIXAMO_BONE_MAP dict mapping Mixamo names to Rigify DEF bones; constraint-based transfer |
| ANIM-11 | AI motion generation via HY-Motion / MotionGPT | Stub client with placeholder API; HY-Motion outputs skeleton data, needs BVH-to-action converter |
| ANIM-12 | Batch animation export as separate Unity clips | NLA strips per action + FBX export with bake_anim_use_nla_strips=True; Unity naming conventions |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bpy (Blender Python API) | 4.x | All animation creation, keyframing, NLA, export | Only option for Blender scripting |
| mathutils | 4.x (bundled) | Euler, Vector, Quaternion math for bone transforms | Blender's native math library |
| math (stdlib) | 3.12 | sin, cos, pi for procedural wave generation | Standard library trigonometry |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | 3.12 | Serialize gait configs, attack params | Config data loading |
| re (stdlib) | 3.12 | Parse text descriptions for custom animation | ANIM-06 text-to-keyframe |
| random (stdlib) | 3.12 | Noise/variation in idle animations | ANIM-03 weight shift randomness |

### No New Dependencies Required
All animation work uses Blender's built-in API and Python stdlib. No pip packages needed. This matches the pattern of Phases 2 and 4 where handler code runs inside Blender's Python environment.

## Architecture Patterns

### Recommended Project Structure
```
blender_addon/handlers/
    animation.py             # Procedural cycle + combat + custom animation handlers (ANIM-01 through ANIM-06)
    animation_export.py      # Preview, root motion, retarget, AI stub, batch export (ANIM-07 through ANIM-12)
    animation_gaits.py       # Gait config dicts and keyframe engine (pure-logic, testable)
tests/
    test_animation_gaits.py  # Pure-logic tests for keyframe engine + gait configs
    test_animation_handlers.py # Pure-logic validation tests for animation handlers
src/veilbreakers_mcp/
    blender_server.py        # Add blender_animation compound tool
```

### Pattern 1: Shared Keyframe Engine (Pure-Logic)
**What:** A `_generate_keyframes()` function that takes a gait config dict and returns a list of `(bone_name, channel, frame, value)` tuples. All procedural handlers call this.
**When to use:** Every procedural animation handler (ANIM-01 through ANIM-03).
**Example:**
```python
# Source: Project pattern (pure-logic extraction from Phase 2+)

# In animation_gaits.py (pure-logic, no bpy imports)

import math
from typing import NamedTuple

class Keyframe(NamedTuple):
    bone_name: str
    channel: str       # "rotation_euler" or "location"
    axis: int          # 0=X, 1=Y, 2=Z
    frame: int
    value: float

# Gait configuration dict format
BIPED_WALK_CONFIG = {
    "name": "biped_walk",
    "frame_count": 24,       # frames per cycle
    "fps": 24,
    "bones": {
        "DEF-thigh.L":  {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 0.0},
        "DEF-thigh.R":  {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": math.pi},
        "DEF-shin.L":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": 0.5},
        "DEF-shin.R":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": math.pi + 0.5},
        "DEF-spine.001": {"channel": "rotation_euler", "axis": 1, "amplitude": 0.05, "phase": 0.0},
        # ... hip bob, arm swing, etc.
    },
}

def generate_cycle_keyframes(config: dict) -> list[Keyframe]:
    """Generate keyframes for a locomotion cycle from a gait config.

    Pure math -- no Blender dependency. Returns list of Keyframe tuples.
    """
    keyframes = []
    frame_count = config["frame_count"]
    for bone_name, bone_cfg in config["bones"].items():
        amp = bone_cfg["amplitude"]
        phase = bone_cfg["phase"]
        for frame in range(frame_count + 1):  # +1 for seamless loop
            t = (frame / frame_count) * 2 * math.pi
            value = amp * math.sin(t + phase)
            keyframes.append(Keyframe(
                bone_name=bone_name,
                channel=bone_cfg["channel"],
                axis=bone_cfg["axis"],
                frame=frame,
                value=value,
            ))
    return keyframes
```

### Pattern 2: Keyframe Application to Blender Action (Blender-Dependent)
**What:** Takes keyframe tuples from the engine and writes them into a bpy.data.actions Action with proper fcurves.
**When to use:** Every handler that creates animation.
**Example:**
```python
# Source: Blender Python API docs (bpy.types.Action, FCurveKeyframePoints)

import bpy

def _apply_keyframes_to_action(
    armature_obj,
    action_name: str,
    keyframes: list,  # list of Keyframe namedtuples
    use_cyclic: bool = True,
) -> dict:
    """Create a Blender Action from keyframe data and assign to armature."""
    # Create or get action
    action = bpy.data.actions.new(name=action_name)
    action.use_fake_user = True

    # Ensure animation data exists
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Group keyframes by (bone, channel, axis) for fcurve creation
    fcurve_map = {}
    for kf in keyframes:
        key = (kf.bone_name, kf.channel, kf.axis)
        fcurve_map.setdefault(key, []).append((kf.frame, kf.value))

    # Create fcurves and insert keyframes
    for (bone_name, channel, axis), frames in fcurve_map.items():
        data_path = f'pose.bones["{bone_name}"].{channel}'
        fc = action.fcurves.new(data_path=data_path, index=axis)
        fc.keyframe_points.add(count=len(frames))
        for i, (frame, value) in enumerate(frames):
            fc.keyframe_points[i].co = (frame, value)
            fc.keyframe_points[i].interpolation = 'BEZIER'

        # Add cycles modifier for seamless looping
        if use_cyclic:
            mod = fc.modifiers.new(type='CYCLES')

    action.frame_range  # auto-computed from keyframes
    return {
        "action_name": action.name,
        "fcurve_count": len(action.fcurves),
        "frame_range": [int(action.frame_range[0]), int(action.frame_range[1])],
    }
```

### Pattern 3: NLA Strip Management for Batch Export
**What:** Push each animation action onto the NLA stack as a separate strip. FBX export with `bake_anim_use_nla_strips=True` produces one AnimStack per strip, which Unity imports as separate clips.
**When to use:** ANIM-09 (root motion) and ANIM-12 (batch export).
**Example:**
```python
# Source: Blender Python API (bpy.types.NlaTrack, NlaStrips)

def _push_action_to_nla(armature_obj, action, strip_name=None):
    """Push an action onto the NLA stack as a new strip."""
    anim_data = armature_obj.animation_data
    if anim_data is None:
        armature_obj.animation_data_create()
        anim_data = armature_obj.animation_data

    track = anim_data.nla_tracks.new()
    track.name = strip_name or action.name

    start_frame = int(action.frame_range[0])
    strip = track.strips.new(
        name=action.name,
        start=start_frame,
        action=action,
    )
    strip.frame_end = int(action.frame_range[1])
    return strip
```

### Pattern 4: Compound MCP Tool (Established)
**What:** One `blender_animation` tool with Literal action parameter routing to handlers.
**When to use:** Server-side tool definition in blender_server.py.
**Example:**
```python
# Source: Existing blender_rig pattern in blender_server.py

@mcp.tool()
async def blender_animation(
    action: Literal[
        "generate_walk",       # ANIM-01
        "generate_fly",        # ANIM-02
        "generate_idle",       # ANIM-03
        "generate_attack",     # ANIM-04
        "generate_reaction",   # ANIM-05
        "generate_custom",     # ANIM-06
        "preview",             # ANIM-07
        "add_secondary",       # ANIM-08
        "extract_root_motion", # ANIM-09
        "retarget_mixamo",     # ANIM-10
        "generate_ai_motion",  # ANIM-11
        "batch_export",        # ANIM-12
    ],
    object_name: str,
    # ... action-specific params
):
    """Generate, preview, and export game-ready animations."""
```

### Anti-Patterns to Avoid
- **Hardcoded bone names per gait:** Use config dicts that reference TEMPLATE_CATALOG bone names, not inline strings. A humanoid walk and quadruped walk use the same sine-wave math with different bone lists.
- **Keyframe insertion in loops via operator calls:** Use `fcurve.keyframe_points.add(count=N)` for bulk insert, then set `.co` on each point. Calling `keyframe_insert()` in a loop via `bpy.ops` is 10-100x slower.
- **Mode switching inside keyframe generation:** Keyframes are inserted on pose bones via fcurves on the Action -- no mode switch to POSE mode needed for fcurve manipulation. Only need POSE mode for constraint-based operations.
- **Single monolithic handler file:** Split into gaits (pure-logic), animation handlers (Blender-dependent), and export handlers to keep files under 500 lines and testable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Seamless loop math | Custom loop-closing logic | F-curve CYCLES modifier (`fc.modifiers.new(type='CYCLES')`) | Blender handles interpolation across loop boundary automatically |
| Animation baking | Manual keyframe copying | `bpy.ops.nla.bake()` with frame_start/frame_end/step | Handles constraint resolution, NLA blending, visual keying |
| FBX animation clips | Custom FBX writer | `bpy.ops.export_scene.fbx()` with `bake_anim_use_nla_strips=True` | Blender's FBX exporter handles AnimStack creation per NLA strip |
| Mixamo bone name transform | Manual regex per bone | Algorithmic mapping: strip "mixamorig:" prefix, convert Left/Right to .L/.R suffix | Standard pattern used by community tools; covers all Mixamo skeleton variants |
| Contact sheet for animation frames | Custom multi-render compositor | Existing `handle_render_contact_sheet` + `bpy.context.scene.frame_set()` | Already built in Phase 1 |
| Quaternion/Euler conversion | Manual rotation math | `mathutils.Euler.to_quaternion()` / `Quaternion.to_euler()` | Blender's math library handles gimbal lock edge cases |

**Key insight:** Blender's animation system is comprehensive. The procedural part is just generating the right numbers (pure math). Applying those numbers to Blender is a thin layer of API calls that must not be overthought.

## Common Pitfalls

### Pitfall 1: Bone Name Mismatch Between Templates and Animation
**What goes wrong:** Animation targets bone names like "thigh.L" but the deformation bones are "DEF-thigh.L" after Rigify generation.
**Why it happens:** Rigify adds "DEF-" prefix to deformation bones. Template dicts use non-prefixed names. Animation keyframes must target DEF bones.
**How to avoid:** All gait configs use "DEF-" prefixed names. Add a `_resolve_bone_name()` helper that checks if the armature has the DEF variant and maps accordingly.
**Warning signs:** Keyframes exist but mesh doesn't move. FCurves show data_path errors in Blender's Graph Editor.

### Pitfall 2: FCurve Data Path Format
**What goes wrong:** FCurve created with wrong data_path string, keyframes have no effect.
**Why it happens:** Bone names with dots or special chars need exact quoting in `pose.bones["name"].rotation_euler`.
**How to avoid:** Always use `f'pose.bones["{bone_name}"].{channel}'` with double quotes inside the f-string. Validate bone_name exists on armature before creating fcurve.
**Warning signs:** `action.fcurves` shows entries but bone doesn't animate.

### Pitfall 3: FBX Export Ignoring NLA Strips
**What goes wrong:** Exported FBX has one merged animation instead of separate clips.
**Why it happens:** `bake_anim_use_nla_strips` defaults to True but `bake_anim_use_all_actions` also True -- these conflict. Need `bake_anim_use_nla_strips=True, bake_anim_use_all_actions=False` for NLA-strip-based export.
**How to avoid:** Set both flags explicitly. Mute strips you don't want exported. Verify strip names match expected Unity clip names.
**Warning signs:** Unity shows one "Take 001" animation instead of individual clips.

### Pitfall 4: Walk Cycle Not Looping Cleanly
**What goes wrong:** Visible pop/jerk at loop boundary.
**Why it happens:** Frame 0 and final frame have different values. Or keyframe at frame_count is missing.
**How to avoid:** Generate frame_count + 1 keyframes where frame[0] == frame[frame_count]. Use CYCLES fcurve modifier. Set action.use_cyclic = True.
**Warning signs:** Small jerk visible in viewport playback at loop point.

### Pitfall 5: Root Motion Extraction Losing Animation Quality
**What goes wrong:** After extracting root motion, character slides or floats.
**Why it happens:** Removing hip XY translation without compensating the remaining animation creates ground-plane disconnect.
**How to avoid:** Extract hip bone's world-space XY translation per frame, transfer it to root bone, then subtract from hip's local-space keys. Keep hip's Z (vertical bob) intact. Process frame-by-frame, not by modifying raw fcurve values.
**Warning signs:** Feet slide on ground during walk cycle. Character bobs vertically at wrong times.

### Pitfall 6: Quaternion vs Euler Rotation Mode
**What goes wrong:** Keyframes set on rotation_euler but bone uses rotation_quaternion (or vice versa).
**Why it happens:** Rigify bones default to rotation mode varies by bone type. Some use quaternion, some Euler.
**How to avoid:** Check `pose_bone.rotation_mode` before inserting keyframes. If 'QUATERNION', use `rotation_quaternion` data_path with axis indices 0-3 (WXYZ). If 'XYZ' or other Euler, use `rotation_euler` with 0-2.
**Warning signs:** Bones snap to weird orientations instead of smooth animation.

## Code Examples

### Creating a Walk Cycle Action
```python
# Source: Blender Python API + project pattern

def handle_generate_walk(params: dict) -> dict:
    """Generate procedural walk/run cycle for any gait type (ANIM-01)."""
    obj_name = params.get("object_name")
    gait = params.get("gait", "biped")          # biped/quadruped/hexapod/arachnid/serpent
    speed = params.get("speed", "walk")          # walk/run
    frame_count = int(params.get("frame_count", 24))

    # Validate
    armature_obj = bpy.data.objects.get(obj_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {obj_name}")

    # Get gait config (pure-logic module)
    from .animation_gaits import get_gait_config, generate_cycle_keyframes
    config = get_gait_config(gait, speed, frame_count, armature_obj)
    keyframes = generate_cycle_keyframes(config)

    # Apply to Blender action
    action_name = f"{obj_name}_{gait}_{speed}"
    result = _apply_keyframes_to_action(armature_obj, action_name, keyframes)

    # Add contact frame markers
    action = bpy.data.actions.get(action_name)
    if action:
        contact_frames = config.get("contact_frames", [])
        for i, frame in enumerate(contact_frames):
            marker = action.pose_markers.new(f"foot_contact_{i}")
            marker.frame = frame

    return {
        "action_name": result["action_name"],
        "gait": gait,
        "speed": speed,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
        "contact_frames": contact_frames,
    }
```

### Root Motion Extraction
```python
# Source: Root Motionist addon pattern + Blender API

def handle_extract_root_motion(params: dict) -> dict:
    """Extract root motion from hip bone and transfer to root bone (ANIM-09)."""
    obj_name = params.get("object_name")
    action_name = params.get("action_name")
    hip_bone = params.get("hip_bone", "DEF-spine")
    root_bone = params.get("root_bone", "root")
    extract_rotation = params.get("extract_rotation", False)

    armature_obj = bpy.data.objects.get(obj_name)
    action = bpy.data.actions.get(action_name)
    # ... validation ...

    # Read hip XY translation per frame
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])

    hip_translations = []
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        hip_pbone = armature_obj.pose.bones[hip_bone]
        world_loc = armature_obj.matrix_world @ hip_pbone.matrix.translation
        hip_translations.append((frame, world_loc.x, world_loc.y))

    # Create root bone fcurves with extracted XY motion
    # Subtract extracted motion from hip bone fcurves
    # ... (frame-by-frame subtraction)

    return {
        "action_name": action_name,
        "root_bone": root_bone,
        "frames_processed": len(hip_translations),
        "total_distance": ...,
    }
```

### Batch FBX Export with NLA Strips
```python
# Source: Blender FBX export API docs

def handle_batch_export(params: dict) -> dict:
    """Export all NLA strips as separate Unity animation clips (ANIM-12)."""
    obj_name = params.get("object_name")
    output_dir = params.get("output_dir")
    naming_convention = params.get("naming", "unity")  # "unity" or "raw"

    armature_obj = bpy.data.objects.get(obj_name)
    anim_data = armature_obj.animation_data
    if not anim_data or not anim_data.nla_tracks:
        raise ValueError("No NLA tracks found")

    exported = []
    for track in anim_data.nla_tracks:
        for strip in track.strips:
            if strip.mute:
                continue

            # Unity naming: CharacterName@AnimationName.fbx
            if naming_convention == "unity":
                filename = f"{obj_name}@{strip.name}.fbx"
            else:
                filename = f"{strip.name}.fbx"

            filepath = os.path.join(output_dir, filename)

            # Mute all other strips, unmute only this one
            _solo_nla_strip(anim_data, strip)

            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                bake_anim=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=False,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                apply_scale_options="FBX_SCALE_ALL",
                axis_forward="-Z",
                axis_up="Y",
                add_leaf_bones=False,
            )
            exported.append({"name": strip.name, "filepath": filepath})

    # Restore all strip mute states
    _restore_nla_mute_states(anim_data)

    return {
        "exported_clips": len(exported),
        "clips": exported,
        "output_dir": output_dir,
    }
```

### Mixamo Bone Name Mapping
```python
# Source: Community standard (Gist eelstork/6b2944d74ec9dd229938 pattern)

MIXAMO_TO_RIGIFY: dict[str, str] = {
    # Spine chain
    "mixamorig:Hips": "DEF-spine",
    "mixamorig:Spine": "DEF-spine.001",
    "mixamorig:Spine1": "DEF-spine.002",
    "mixamorig:Spine2": "DEF-spine.003",
    "mixamorig:Neck": "DEF-spine.004",
    "mixamorig:Head": "DEF-spine.005",
    # Left arm
    "mixamorig:LeftShoulder": "DEF-shoulder.L",
    "mixamorig:LeftArm": "DEF-upper_arm.L",
    "mixamorig:LeftForeArm": "DEF-forearm.L",
    "mixamorig:LeftHand": "DEF-hand.L",
    # Right arm
    "mixamorig:RightShoulder": "DEF-shoulder.R",
    "mixamorig:RightArm": "DEF-upper_arm.R",
    "mixamorig:RightForeArm": "DEF-forearm.R",
    "mixamorig:RightHand": "DEF-hand.R",
    # Left leg
    "mixamorig:LeftUpLeg": "DEF-thigh.L",
    "mixamorig:LeftLeg": "DEF-shin.L",
    "mixamorig:LeftFoot": "DEF-foot.L",
    "mixamorig:LeftToeBase": "DEF-toe.L",
    # Right leg
    "mixamorig:RightUpLeg": "DEF-thigh.R",
    "mixamorig:RightLeg": "DEF-shin.R",
    "mixamorig:RightFoot": "DEF-foot.R",
    "mixamorig:RightToeBase": "DEF-toe.R",
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual keyframing in Blender UI | Procedural keyframe generation via Python | Long-standing | Enables batch generation for many creature types |
| Separate FBX per animation (manual) | NLA strips + batch FBX export | Blender 2.8+ | Single workflow produces all Unity clips |
| Mocap-only motion generation | AI text-to-motion (HY-Motion 1.0) | Dec 2025 | Can generate motion from text descriptions; local model, no API yet |
| Manual Mixamo retarget via UI | Constraint-based Python retarget | Long-standing | Programmatic retarget matches Phase 4 pattern |
| FBX_SCALE_NONE for Unity export | FBX_SCALE_ALL (project standard) | Phase 1 decision | Consistent with existing export handler |

**Deprecated/outdated:**
- `bpy.ops.nla.bake()` for simple keyframe generation -- only needed for constraint/physics baking, not procedural keyframes
- Manual NLA strip naming -- use programmatic `track.strips.new()` for consistency

## Open Questions

1. **HY-Motion Output Format**
   - What we know: HY-Motion 1.0 is local-only (no HTTP API), outputs "skeleton-based 3D animations"
   - What's unclear: Exact output format (BVH? raw joint rotations? SMPL parameters?) not documented in README
   - Recommendation: Build a stub that accepts text prompt and returns placeholder action data. When format is confirmed, add a converter function. Mark as LOW confidence until output format verified.

2. **Quadruped/Hexapod/Serpent Gait Accuracy**
   - What we know: Biped walk is well-documented (sine wave + phase offset). Quadruped gait patterns (walk, trot, canter, gallop) have different phase relationships.
   - What's unclear: Hexapod (insect) and arachnid (8-leg) gait patterns are less standardized in game animation
   - Recommendation: Use published gait phase tables: quadruped walk = diagonal pairs (0, pi, pi/2, 3pi/2), hexapod = alternating tripod (0, pi for tripod groups). Test visually with contact sheet preview.

3. **DEF Bone Availability Across All 10 Templates**
   - What we know: Humanoid and quadruped DEF bone names are clear from DEFORMATION_POSES and TEMPLATE_CATALOG
   - What's unclear: Whether all 10 templates (serpent, floating, amorphous, etc.) have consistent DEF bone naming after Rigify generation
   - Recommendation: Build a `_get_def_bones()` helper that introspects the armature at runtime rather than hardcoding names per template. Fall back to template bone names with "DEF-" prefix.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | Tools/mcp-toolkit/pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_animation_gaits.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANIM-01 | Biped/quadruped/hexapod/arachnid/serpent walk keyframes | unit | `pytest tests/test_animation_gaits.py::TestWalkCycle -x` | No -- Wave 0 |
| ANIM-02 | Fly/hover wing oscillation keyframes | unit | `pytest tests/test_animation_gaits.py::TestFlyCycle -x` | No -- Wave 0 |
| ANIM-03 | Idle breathing/weight shift keyframes | unit | `pytest tests/test_animation_gaits.py::TestIdleCycle -x` | No -- Wave 0 |
| ANIM-04 | Attack keyframe sequences (8 types) | unit | `pytest tests/test_animation_gaits.py::TestAttackSequences -x` | No -- Wave 0 |
| ANIM-05 | Death/hit/spawn parametric keyframes | unit | `pytest tests/test_animation_gaits.py::TestReactionAnimations -x` | No -- Wave 0 |
| ANIM-06 | Text description to keyframe validation | unit | `pytest tests/test_animation_handlers.py::TestCustomAnimation -x` | No -- Wave 0 |
| ANIM-07 | Animation preview param validation | unit | `pytest tests/test_animation_handlers.py::TestPreviewParams -x` | No -- Wave 0 |
| ANIM-08 | Secondary motion param validation | unit | `pytest tests/test_animation_handlers.py::TestSecondaryMotion -x` | No -- Wave 0 |
| ANIM-09 | Root motion extraction validation | unit | `pytest tests/test_animation_handlers.py::TestRootMotion -x` | No -- Wave 0 |
| ANIM-10 | Mixamo bone mapping completeness | unit | `pytest tests/test_animation_handlers.py::TestMixamoMapping -x` | No -- Wave 0 |
| ANIM-11 | AI motion stub validation | unit | `pytest tests/test_animation_handlers.py::TestAIMotionStub -x` | No -- Wave 0 |
| ANIM-12 | Batch export param validation | unit | `pytest tests/test_animation_handlers.py::TestBatchExport -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_animation_gaits.py tests/test_animation_handlers.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_animation_gaits.py` -- pure-logic tests for keyframe engine, gait configs, cycle math
- [ ] `tests/test_animation_handlers.py` -- pure-logic validation tests for all handler param validation functions
- [ ] No framework install needed (pytest already in dev dependencies)
- [ ] No new conftest.py fixtures needed (existing bpy/bmesh stubs sufficient)

## Sources

### Primary (HIGH confidence)
- [Blender Python API - Action(ID)](https://docs.blender.org/api/current/bpy.types.Action.html) - Action creation, fcurves, frame_range, pose_markers, use_cyclic
- [Blender Python API - NlaStrip](https://docs.blender.org/api/current/bpy.types.NlaStrip.html) - NLA strip properties, action reference, frame ranges
- [Blender Python API - Export Scene FBX](https://docs.blender.org/api/3.1/bpy.ops.export_scene.html) - FBX animation export parameters with defaults
- [Blender Python API - ActionPoseMarkers](https://docs.blender.org/api/current/bpy.types.ActionPoseMarkers.html) - Pose marker creation for animation events
- [Blender Python API - FCurveKeyframePoints](https://docs.blender.org/api/current/bpy.types.FCurveKeyframePoints.html) - Bulk keyframe insertion
- Existing project code: `rigging_templates.py` TEMPLATE_CATALOG, `rigging_weights.py` DEFORMATION_POSES, `viewport.py` render_contact_sheet, `export.py` FBX settings, `rigging_advanced.py` retarget/spring bones

### Secondary (MEDIUM confidence)
- [Blender Artists - Convert Mixamo bone names](https://gist.github.com/eelstork/6b2944d74ec9dd229938) - Mixamo-to-Blender bone mapping algorithm
- [Root Motionist addon](https://github.com/RoboPoets/root_motionist) - Root motion extraction approach (hip-to-root transfer)
- [RustyCruise Labs - Blender to Unity FBX](https://rustycruiselabs.com/devlogs/generic/2024-10-19-blender-to-unity-settings/) - Unity FBX import configuration for animations
- [Procedural Animation Locomotion](https://blog.littlepolygon.com/posts/loco1/) - Sine wave walk cycle math

### Tertiary (LOW confidence)
- [HY-Motion 1.0 GitHub](https://github.com/Tencent-Hunyuan/HY-Motion-1.0) - AI motion generation; output format unclear, local-only model
- [MotionGPT GitHub](https://github.com/OpenMotionLab/MotionGPT) - Alternative AI motion model; academic project, no production API

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses only Blender built-in API (bpy, mathutils, math) with well-documented animation primitives
- Architecture: HIGH - Follows established project patterns (compound tool, handler split, pure-logic extraction) with proven rigging phase precedent
- Procedural keyframe math: HIGH - Sine wave locomotion is well-documented; per-gait config dict pattern is straightforward
- Export pipeline: HIGH - FBX animation export parameters verified against official Blender docs
- Mixamo retarget: MEDIUM - Bone mapping algorithm verified against community tools; exact Rigify DEF bone coverage needs runtime validation
- AI motion integration: LOW - HY-Motion output format undocumented; stub-only implementation is safe
- Exotic gait patterns (hexapod/arachnid/serpent): MEDIUM - Less standardized than biped/quadruped; visual testing via contact sheets mitigates risk

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain -- Blender animation API rarely changes between minor versions)
