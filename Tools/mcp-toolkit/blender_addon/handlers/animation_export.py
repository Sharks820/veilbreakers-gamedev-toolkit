"""Animation export and integration handlers for preview, secondary motion,
root motion extraction, Mixamo retargeting, AI motion stub, and batch FBX export.

Provides six command handlers:
  - handle_preview_animation: Contact sheet of animation frames (ANIM-07)
  - handle_add_secondary_motion: Bake spring bone constraints to keyframes (ANIM-08)
  - handle_extract_root_motion: Separate root/hip translation from anim curves (ANIM-09)
  - handle_retarget_mixamo: Map Mixamo bone names to custom rig DEF bones (ANIM-10)
  - handle_generate_ai_motion: HY-Motion/MotionGPT stub (ANIM-11)
  - handle_batch_export: Export each NLA action as separate FBX with Unity naming (ANIM-12)

Pure-logic validation functions (_validate_export_params, _validate_root_motion_params,
_validate_secondary_motion_params, _validate_batch_export_params, _map_mixamo_bones,
_generate_unity_filename) are separated for testability without Blender.
"""

from __future__ import annotations

import json as _json
import math
import os

import bpy
from mathutils import Vector

from ._action_compat import (
    get_fcurves, get_frame_range, get_fcurve_count,
    is_layered_action, new_fcurve, remove_fcurve,
    setup_action_for_armature,
)
from ._context import get_3d_context_override


def _action_frame_range(action, armature_obj=None) -> list[int]:
    """Get action frame range, compatible with Blender 4.x and 5.0+."""
    if hasattr(action, "frame_range"):
        return [int(action.frame_range[0]), int(action.frame_range[1])]
    # Blender 5.0+: need channelbag context to read frame range
    cb, layered = setup_action_for_armature(action, armature_obj) if armature_obj else (None, True)
    return get_frame_range(action, cb, layered)


def _action_fcurves_list(action, armature_obj=None):
    """Get action fcurves as a list, compatible with Blender 4.x and 5.0+."""
    if hasattr(action, "fcurves"):
        return action.fcurves
    cb, layered = setup_action_for_armature(action, armature_obj) if armature_obj else (None, True)
    return get_fcurves(action, cb, layered)


def _action_new_fcurve(action, data_path, index, armature_obj=None):
    """Create new fcurve on action, compatible with Blender 4.x and 5.0+."""
    if hasattr(action, "fcurves"):
        return action.fcurves.new(data_path=data_path, index=index)
    cb, layered = setup_action_for_armature(action, armature_obj) if armature_obj else (None, True)
    return new_fcurve(action, data_path, index, cb, layered)


def _action_remove_fcurve(action, fc, armature_obj=None):
    """Remove fcurve from action, compatible with Blender 4.x and 5.0+."""
    if hasattr(action, "fcurves"):
        action.fcurves.remove(fc)
    else:
        cb, layered = setup_action_for_armature(action, armature_obj) if armature_obj else (None, True)
        remove_fcurve(action, fc, cb, layered)


# ---------------------------------------------------------------------------
# Mixamo-to-Rigify bone mapping (22 core humanoid bones)
# ---------------------------------------------------------------------------
# Keys are Mixamo bone names (with "mixamorig:" prefix).
# Values are Rigify DEF bone names matching Phase 4 rig templates.

MIXAMO_TO_RIGIFY: dict[str, str] = {
    # Spine chain (6 bones)
    "mixamorig:Hips": "DEF-spine",
    "mixamorig:Spine": "DEF-spine.001",
    "mixamorig:Spine1": "DEF-spine.002",
    "mixamorig:Spine2": "DEF-spine.003",
    "mixamorig:Neck": "DEF-spine.004",
    "mixamorig:Head": "DEF-spine.005",
    # Left arm (4 bones)
    "mixamorig:LeftShoulder": "DEF-shoulder.L",
    "mixamorig:LeftArm": "DEF-upper_arm.L",
    "mixamorig:LeftForeArm": "DEF-forearm.L",
    "mixamorig:LeftHand": "DEF-hand.L",
    # Right arm (4 bones)
    "mixamorig:RightShoulder": "DEF-shoulder.R",
    "mixamorig:RightArm": "DEF-upper_arm.R",
    "mixamorig:RightForeArm": "DEF-forearm.R",
    "mixamorig:RightHand": "DEF-hand.R",
    # Left leg (4 bones)
    "mixamorig:LeftUpLeg": "DEF-thigh.L",
    "mixamorig:LeftLeg": "DEF-shin.L",
    "mixamorig:LeftFoot": "DEF-foot.L",
    "mixamorig:LeftToeBase": "DEF-toe.L",
    # Right leg (4 bones)
    "mixamorig:RightUpLeg": "DEF-thigh.R",
    "mixamorig:RightLeg": "DEF-shin.R",
    "mixamorig:RightFoot": "DEF-foot.R",
    "mixamorig:RightToeBase": "DEF-toe.R",
    # Left hand fingers (15 bones) - G13
    "mixamorig:LeftHandThumb1": "DEF-thumb.01.L",
    "mixamorig:LeftHandThumb2": "DEF-thumb.02.L",
    "mixamorig:LeftHandThumb3": "DEF-thumb.03.L",
    "mixamorig:LeftHandIndex1": "DEF-f_index.01.L",
    "mixamorig:LeftHandIndex2": "DEF-f_index.02.L",
    "mixamorig:LeftHandIndex3": "DEF-f_index.03.L",
    "mixamorig:LeftHandMiddle1": "DEF-f_middle.01.L",
    "mixamorig:LeftHandMiddle2": "DEF-f_middle.02.L",
    "mixamorig:LeftHandMiddle3": "DEF-f_middle.03.L",
    "mixamorig:LeftHandRing1": "DEF-f_ring.01.L",
    "mixamorig:LeftHandRing2": "DEF-f_ring.02.L",
    "mixamorig:LeftHandRing3": "DEF-f_ring.03.L",
    "mixamorig:LeftHandPinky1": "DEF-f_pinky.01.L",
    "mixamorig:LeftHandPinky2": "DEF-f_pinky.02.L",
    "mixamorig:LeftHandPinky3": "DEF-f_pinky.03.L",
    # Right hand fingers (15 bones) - G13
    "mixamorig:RightHandThumb1": "DEF-thumb.01.R",
    "mixamorig:RightHandThumb2": "DEF-thumb.02.R",
    "mixamorig:RightHandThumb3": "DEF-thumb.03.R",
    "mixamorig:RightHandIndex1": "DEF-f_index.01.R",
    "mixamorig:RightHandIndex2": "DEF-f_index.02.R",
    "mixamorig:RightHandIndex3": "DEF-f_index.03.R",
    "mixamorig:RightHandMiddle1": "DEF-f_middle.01.R",
    "mixamorig:RightHandMiddle2": "DEF-f_middle.02.R",
    "mixamorig:RightHandMiddle3": "DEF-f_middle.03.R",
    "mixamorig:RightHandRing1": "DEF-f_ring.01.R",
    "mixamorig:RightHandRing2": "DEF-f_ring.02.R",
    "mixamorig:RightHandRing3": "DEF-f_ring.03.R",
    "mixamorig:RightHandPinky1": "DEF-f_pinky.01.R",
    "mixamorig:RightHandPinky2": "DEF-f_pinky.02.R",
    "mixamorig:RightHandPinky3": "DEF-f_pinky.03.R",
}


# ---------------------------------------------------------------------------
# G15: Timing JSON sidecar for FBX export
# ---------------------------------------------------------------------------


def _generate_timing_sidecar(
    action_name: str,
    output_dir: str,
    naming: str,
    object_name: str,
) -> str | None:
    """Generate .timing.json sidecar for a combat animation FBX export.

    Checks if the action name matches a combat timing preset and writes
    the timing data as JSON alongside the exported FBX file.

    Returns the sidecar file path, or None if no timing data applies.
    """
    from ._combat_timing import COMBAT_TIMING_PRESETS

    matched = None
    action_lower = action_name.lower()
    for preset in COMBAT_TIMING_PRESETS:
        if preset in action_lower:
            matched = preset
            break
    if not matched:
        for kw, preset in [("attack", "light_attack"), ("dodge", "dodge_roll"),
                           ("parry", "parry"), ("block", "block"),
                           ("combo", "combo_finisher"), ("charged", "charged_attack")]:
            if kw in action_lower:
                matched = preset
                break
    if not matched:
        return None

    fbx_name = _generate_unity_filename(object_name, action_name, naming)
    sidecar_name = fbx_name.replace(".fbx", ".timing.json")
    sidecar_path = os.path.join(output_dir, sidecar_name)

    data = dict(COMBAT_TIMING_PRESETS[matched])
    data["source_action"] = action_name
    data["preset"] = matched

    with open(sidecar_path, "w") as f:
        _json.dump(data, f, indent=2)
    return sidecar_path


# ---------------------------------------------------------------------------
# Pure-logic validation functions (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_export_params(params: dict) -> dict:
    """Validate common animation export parameters.

    Args:
        params: Dict with object_name (required), optionally object_type.

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    object_name = params.get("object_name")
    if not isinstance(object_name, str) or not object_name:
        errors.append("object_name is required and must be a non-empty string")

    # object_type check (caller passes armature type string for validation)
    object_type = params.get("object_type")
    if object_type is not None and object_type != "ARMATURE":
        errors.append(
            f"object must be an armature, got type '{object_type}'"
        )

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_preview_params(params: dict) -> dict:
    """Validate animation preview parameters.

    Args:
        params: Dict with frame_step, angles, resolution.

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    frame_step = params.get("frame_step", 4)
    if not isinstance(frame_step, (int, float)):
        errors.append("frame_step must be a number")
    elif frame_step < 1:
        errors.append("frame_step must be >= 1")

    angles = params.get("angles", ["front", "side"])
    if not isinstance(angles, (list, tuple)):
        errors.append("angles must be a list")
    elif len(angles) == 0:
        errors.append("angles must be non-empty")

    resolution = params.get("resolution", 256)
    if not isinstance(resolution, (int, float)):
        errors.append("resolution must be a number")
    elif resolution < 32:
        errors.append("resolution must be >= 32")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_secondary_motion_params(params: dict) -> dict:
    """Validate secondary motion baking parameters.

    Args:
        params: Dict with action_name, bone_names.

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    action_name = params.get("action_name")
    if not isinstance(action_name, str) or not action_name:
        errors.append("action_name is required")

    bone_names = params.get("bone_names", [])
    if not isinstance(bone_names, (list, tuple)) or len(bone_names) == 0:
        errors.append("bone_names must be a non-empty list")
    else:
        for i, name in enumerate(bone_names):
            if not isinstance(name, str) or not name:
                errors.append(f"bone_names[{i}] must be a non-empty string")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_root_motion_params(params: dict) -> dict:
    """Validate root motion extraction parameters.

    Args:
        params: Dict with action_name (required), hip_bone, root_bone,
                extract_rotation.

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    action_name = params.get("action_name")
    if not isinstance(action_name, str) or not action_name:
        errors.append("action_name is required")

    hip_bone = params.get("hip_bone", "DEF-spine")
    if not isinstance(hip_bone, str) or not hip_bone:
        errors.append("hip_bone must be a non-empty string")

    root_bone = params.get("root_bone", "root")
    if not isinstance(root_bone, str) or not root_bone:
        errors.append("root_bone must be a non-empty string")

    extract_rotation = params.get("extract_rotation", False)
    if extract_rotation and (not isinstance(hip_bone, str) or not hip_bone):
        errors.append("hip_bone is required when extract_rotation is True")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_batch_export_params(params: dict) -> dict:
    """Validate batch export parameters.

    Args:
        params: Dict with output_dir (required), naming, actions.

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    output_dir = params.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        errors.append("output_dir is required")

    naming = params.get("naming", "unity")
    valid_naming = ("unity", "raw")
    if naming not in valid_naming:
        errors.append(f"naming must be one of {valid_naming}, got '{naming}'")

    actions = params.get("actions")
    if actions is not None:
        if not isinstance(actions, (list, tuple)):
            errors.append("actions must be a list if provided")
        elif len(actions) == 0:
            errors.append("actions list must not be empty if provided")

    return {"valid": len(errors) == 0, "errors": errors}


def _map_mixamo_bones(
    source_bones: list[str],
    target_bones: list[str],
) -> dict:
    """Map Mixamo bone names to Rigify DEF bones filtered by what exists.

    Args:
        source_bones: List of bone names on the source (Mixamo) armature.
        target_bones: List of bone names on the target (Rigify) armature.

    Returns:
        Dict with mapped (dict[str,str]), unmapped_source (list[str]),
        unmapped_target (list[str]).
    """
    source_set = set(source_bones)
    target_set = set(target_bones)

    mapped: dict[str, str] = {}
    for mixamo_name, rigify_name in MIXAMO_TO_RIGIFY.items():
        if mixamo_name in source_set and rigify_name in target_set:
            mapped[mixamo_name] = rigify_name

    # Unmapped: Mixamo bones with no mapping or target missing
    mapped_source = set(mapped.keys())
    mixamo_source = {b for b in source_bones if b.startswith("mixamorig:")}
    unmapped_source = sorted(mixamo_source - mapped_source)

    mapped_target = set(mapped.values())
    def_target = {b for b in target_bones if b.startswith("DEF-")}
    unmapped_target = sorted(def_target - mapped_target)

    return {
        "mapped": mapped,
        "unmapped_source": unmapped_source,
        "unmapped_target": unmapped_target,
    }


def _generate_unity_filename(
    object_name: str,
    clip_name: str,
    naming: str = "unity",
) -> str:
    """Generate export filename following Unity naming conventions.

    Args:
        object_name: Name of the armature/character.
        clip_name: Name of the animation clip/NLA strip.
        naming: "unity" for ObjectName@ClipName.fbx, "raw" for ClipName.fbx.

    Returns:
        Filename string (not full path).
    """
    # Sanitize names -- replace spaces with underscores, strip special chars
    safe_obj = object_name.replace(" ", "_")
    safe_clip = clip_name.replace(" ", "_")

    if naming == "unity":
        return f"{safe_obj}@{safe_clip}.fbx"
    return f"{safe_clip}.fbx"


# ---------------------------------------------------------------------------
# Angle presets for animation preview
# ---------------------------------------------------------------------------

PREVIEW_ANGLES: dict[str, tuple[float, float]] = {
    "front": (0, 0),
    "back": (180, 0),
    "left": (90, 0),
    "right": (270, 0),
    "side": (90, 0),
    "top": (0, 90),
    "three_quarter": (45, 30),
}


# ---------------------------------------------------------------------------
# NLA helper functions
# ---------------------------------------------------------------------------


def _push_action_to_nla(armature_obj, action, strip_name=None):
    """Push an action onto the NLA stack as a new strip.

    Args:
        armature_obj: Blender armature object.
        action: Blender Action to push.
        strip_name: Optional name for the NLA strip (defaults to action name).

    Returns:
        The created NLA strip.
    """
    anim_data = armature_obj.animation_data
    if anim_data is None:
        armature_obj.animation_data_create()
        anim_data = armature_obj.animation_data

    track = anim_data.nla_tracks.new()
    track.name = strip_name or action.name

    start_frame = int(_action_frame_range(action)[0])
    strip = track.strips.new(
        name=strip_name or action.name,
        start=start_frame,
        action=action,
    )
    strip.frame_end = int(_action_frame_range(action)[1])
    return strip


def _solo_nla_strip(anim_data, target_strip):
    """Mute all NLA strips except the target strip.

    Args:
        anim_data: Blender animation data.
        target_strip: The strip to leave unmuted.

    Returns:
        Dict mapping (track_index, strip_index) -> original mute state.
    """
    saved_states = {}
    for ti, track in enumerate(anim_data.nla_tracks):
        for si, strip in enumerate(track.strips):
            saved_states[(ti, si)] = strip.mute
            strip.mute = (strip != target_strip)
    return saved_states


def _restore_nla_mute_states(anim_data, saved_states):
    """Restore original mute states for all NLA strips.

    Args:
        anim_data: Blender animation data.
        saved_states: Dict from _solo_nla_strip.
    """
    for (ti, si), mute_state in saved_states.items():
        if ti < len(anim_data.nla_tracks):
            track = anim_data.nla_tracks[ti]
            if si < len(track.strips):
                track.strips[si].mute = mute_state


# ---------------------------------------------------------------------------
# Blender-dependent handlers
# ---------------------------------------------------------------------------


def handle_preview_animation(params: dict) -> dict:
    """Render a contact sheet of animation frames from multiple angles (ANIM-07).

    Renders every Nth frame of an animation from configurable angles into
    a contact sheet image using existing render infrastructure.

    Params:
        object_name: Name of the armature object.
        action_name: Optional action name (uses active action if not specified).
        frame_step: Render every Nth frame (default 4, must be >= 1).
        angles: List of angle names from PREVIEW_ANGLES or [azimuth, elevation]
                pairs (default ["front", "side"]).
        output_path: Optional output file path.
        resolution: Resolution per cell in pixels (default 256).

    Returns dict with image_path, frame_count, frame_step, angles, cells.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    armature_obj = bpy.data.objects.get(object_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {object_name}")

    # Validate preview params
    preview_valid = _validate_preview_params(params)
    if not preview_valid["valid"]:
        raise ValueError(
            f"Invalid preview params: {'; '.join(preview_valid['errors'])}"
        )

    frame_step = int(params.get("frame_step", 4))
    angle_names = params.get("angles", ["front", "side"])
    resolution = int(params.get("resolution", 256))
    output_path = params.get("output_path")

    # Resolve action
    action_name = params.get("action_name")
    if action_name:
        action = bpy.data.actions.get(action_name)
        if not action:
            raise ValueError(f"Action not found: {action_name}")
        if armature_obj.animation_data is None:
            armature_obj.animation_data_create()
        armature_obj.animation_data.action = action
    else:
        if not armature_obj.animation_data or not armature_obj.animation_data.action:
            raise ValueError("No active action on armature and no action_name specified")
        action = armature_obj.animation_data.action

    # Calculate frames to render
    frame_start = int(_action_frame_range(action)[0])
    frame_end = int(_action_frame_range(action)[1])
    frames = list(range(frame_start, frame_end + 1, frame_step))

    # Resolve angle pairs
    angle_pairs = []
    for angle in angle_names:
        if isinstance(angle, str) and angle in PREVIEW_ANGLES:
            angle_pairs.append(PREVIEW_ANGLES[angle])
        elif isinstance(angle, (list, tuple)) and len(angle) == 2:
            angle_pairs.append(tuple(angle))
        else:
            angle_pairs.append(PREVIEW_ANGLES.get("front", (0, 0)))

    # Render each frame at each angle using existing contact sheet camera setup
    from .viewport import handle_render_contact_sheet

    all_paths = []
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        result = handle_render_contact_sheet({
            "object_name": object_name,
            "angles": [list(ap) for ap in angle_pairs],
            "resolution": [resolution, resolution],
        })
        all_paths.extend(result.get("paths") or [])

    return {
        "image_path": output_path or (all_paths[0] if all_paths else ""),
        "frame_count": len(frames),
        "frame_step": frame_step,
        "angles": angle_names,
        "cells": len(all_paths),
    }


def handle_add_secondary_motion(params: dict) -> dict:
    """Bake spring bone constraint simulations to keyframes for export (ANIM-08).

    Takes existing spring bone constraints (from Phase 4 RIG-06) and bakes
    their visual result into explicit keyframes so the animation exports
    correctly to game engines.

    Params:
        object_name: Name of the armature object.
        action_name: Name of the action to bake into (required).
        bone_names: List of spring bone names to bake (required, non-empty).
        frame_start: Optional start frame (default from action range).
        frame_end: Optional end frame (default from action range).

    Returns dict with action_name, baked_bones, frame_range.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    armature_obj = bpy.data.objects.get(object_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {object_name}")

    # Validate secondary motion params
    sm_valid = _validate_secondary_motion_params(params)
    if not sm_valid["valid"]:
        raise ValueError(
            f"Invalid secondary motion params: {'; '.join(sm_valid['errors'])}"
        )

    action_name = params["action_name"]
    bone_names = params["bone_names"]

    # Set action as active
    action = bpy.data.actions.get(action_name)
    if not action:
        raise ValueError(f"Action not found: {action_name}")

    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Determine frame range
    _fr = _action_frame_range(action)
    frame_start = int(params.get("frame_start", _fr[0]))
    frame_end = int(params.get("frame_end", _fr[1]))

    # Enter pose mode and select spring bones
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="POSE")

    # Deselect all bones, then select only the spring bones
    bpy.ops.pose.select_all(action="DESELECT")
    baked_bones = []
    for bone_name in bone_names:
        pbone = armature_obj.pose.bones.get(bone_name)
        if pbone:
            pbone.bone.select = True
            baked_bones.append(bone_name)

    if not baked_bones:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise ValueError("No valid spring bones found on armature")

    # Bake with visual keying to capture constraint effects
    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        only_selected=True,
        bake_types={"POSE"},
        visual_keying=True,
        clear_constraints=False,
    )

    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "action_name": action_name,
        "baked_bones": baked_bones,
        "frame_range": [frame_start, frame_end],
    }


def handle_extract_root_motion(params: dict) -> dict:
    """Extract root motion from hip bone and transfer to root bone (ANIM-09).

    Separates hip XY translation into the root bone for in-place animation,
    preserving vertical bob (Z). Places animation events at contact frames
    as pose markers.

    Params:
        object_name: Name of the armature object.
        action_name: Name of the action to process (required).
        hip_bone: Name of the hip bone (default "DEF-spine").
        root_bone: Name of the root bone (default "root").
        extract_rotation: Whether to also extract Z rotation (default False).

    Returns dict with action_name, root_bone, frames_processed, total_distance,
    events_placed.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    armature_obj = bpy.data.objects.get(object_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {object_name}")

    # Validate root motion params
    rm_valid = _validate_root_motion_params(params)
    if not rm_valid["valid"]:
        raise ValueError(
            f"Invalid root motion params: {'; '.join(rm_valid['errors'])}"
        )

    action_name = params["action_name"]
    hip_bone_name = params.get("hip_bone", "DEF-spine")
    root_bone_name = params.get("root_bone", "root")
    extract_rotation = params.get("extract_rotation", False)

    # Validate action exists
    action = bpy.data.actions.get(action_name)
    if not action:
        raise ValueError(f"Action not found: {action_name}")

    # Set action as active
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Validate bones exist
    hip_pbone = armature_obj.pose.bones.get(hip_bone_name)
    if not hip_pbone:
        raise ValueError(f"Hip bone not found: {hip_bone_name}")

    root_pbone = armature_obj.pose.bones.get(root_bone_name)
    if not root_pbone:
        raise ValueError(f"Root bone not found: {root_bone_name}")

    frame_start = int(_action_frame_range(action)[0])
    frame_end = int(_action_frame_range(action)[1])

    # Step 1: Read hip XY translation per frame (world space)
    hip_translations = []
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        world_loc = armature_obj.matrix_world @ hip_pbone.matrix.translation
        hip_translations.append((frame, world_loc.x, world_loc.y, world_loc.z))

    # Step 2: Create root bone fcurves for location X, Y
    root_loc_data_path = f'pose.bones["{root_bone_name}"].location'

    # Remove existing root bone location fcurves if present
    for fc in list(_action_fcurves_list(action)):
        if fc.data_path == root_loc_data_path:
            _action_remove_fcurve(action, fc, armature_obj)

    fc_root_x = _action_new_fcurve(action, root_loc_data_path, 0, armature_obj)
    fc_root_y = _action_new_fcurve(action, root_loc_data_path, 1, armature_obj)

    fc_root_x.keyframe_points.add(count=len(hip_translations))
    fc_root_y.keyframe_points.add(count=len(hip_translations))

    # Step 3: Transfer hip XY to root bone
    total_distance = 0.0
    prev_x, prev_y = hip_translations[0][1], hip_translations[0][2]

    for i, (frame, hx, hy, hz) in enumerate(hip_translations):
        # Set root bone keyframes with hip XY values
        fc_root_x.keyframe_points[i].co = (frame, hx)
        fc_root_x.keyframe_points[i].interpolation = "BEZIER"
        fc_root_y.keyframe_points[i].co = (frame, hy)
        fc_root_y.keyframe_points[i].interpolation = "BEZIER"

        # Accumulate total distance
        dx = hx - prev_x
        dy = hy - prev_y
        total_distance += math.sqrt(dx * dx + dy * dy)
        prev_x, prev_y = hx, hy

    # Step 4: Subtract extracted XY from hip bone's local fcurves
    # Keep Z (vertical bob) intact
    hip_loc_data_path = f'pose.bones["{hip_bone_name}"].location'
    for fc in _action_fcurves_list(action):
        if fc.data_path == hip_loc_data_path and fc.array_index in (0, 1):
            # Zero out X and Y on hip bone (motion moved to root)
            for kp in fc.keyframe_points:
                kp.co = (kp.co[0], 0.0)

    # Step 5: Extract rotation if requested
    if extract_rotation:
        rot_mode = hip_pbone.rotation_mode
        if rot_mode in ("QUATERNION",):
            root_rot_data_path = f'pose.bones["{root_bone_name}"].rotation_quaternion'
            rot_index = 3  # W, X, Y, Z -- Z rotation is index 3 for quaternion
        else:
            root_rot_data_path = f'pose.bones["{root_bone_name}"].rotation_euler'
            rot_index = 2  # Z axis

        # Remove existing root rotation Z fcurve if present
        for fc in list(_action_fcurves_list(action)):
            if fc.data_path == root_rot_data_path and fc.array_index == rot_index:
                _action_remove_fcurve(action, fc, armature_obj)

        fc_root_rz = _action_new_fcurve(action, root_rot_data_path, rot_index, armature_obj)
        fc_root_rz.keyframe_points.add(count=len(hip_translations))

        for i, (frame, hx, hy, hz) in enumerate(hip_translations):
            bpy.context.scene.frame_set(frame)
            if rot_mode in ("QUATERNION",):
                rot_z = hip_pbone.matrix.to_quaternion().z
            else:
                rot_z = hip_pbone.matrix.to_euler().z
            fc_root_rz.keyframe_points[i].co = (frame, rot_z)
            fc_root_rz.keyframe_points[i].interpolation = "BEZIER"

    # Step 6: Place animation events at contact frames via pose_markers
    # Detect foot contact by finding frames where foot bone Z is at local minima
    events_placed = 0
    foot_bones = ["DEF-foot.L", "DEF-foot.R"]
    for foot_name in foot_bones:
        foot_pbone = armature_obj.pose.bones.get(foot_name)
        if not foot_pbone:
            continue

        # Read foot Z positions
        foot_z_positions = []
        for frame in range(frame_start, frame_end + 1):
            bpy.context.scene.frame_set(frame)
            world_z = (armature_obj.matrix_world @ foot_pbone.matrix.translation).z
            foot_z_positions.append((frame, world_z))

        # Find local minima (contact frames)
        for j in range(1, len(foot_z_positions) - 1):
            prev_z = foot_z_positions[j - 1][1]
            curr_z = foot_z_positions[j][1]
            next_z = foot_z_positions[j + 1][1]
            if curr_z <= prev_z and curr_z <= next_z:
                contact_frame = foot_z_positions[j][0]
                side = "L" if ".L" in foot_name else "R"
                marker = action.pose_markers.new(
                    f"foot_contact_{side}_{events_placed}"
                )
                marker.frame = contact_frame
                events_placed += 1

    return {
        "action_name": action_name,
        "root_bone": root_bone_name,
        "frames_processed": len(hip_translations),
        "total_distance": round(total_distance, 4),
        "events_placed": events_placed,
    }


def handle_retarget_mixamo(params: dict) -> dict:
    """Retarget Mixamo animation to custom Rigify rig using bone mapping (ANIM-10).

    Imports a Mixamo FBX, maps bone names to Rigify DEF bones using
    MIXAMO_TO_RIGIFY mapping, transfers animation via constraint-based
    approach, then bakes and cleans up.

    Params:
        object_name: Name of the target Rigify armature.
        source_file: Path to Mixamo FBX file.
        action_name: Optional name for the new action.

    Returns dict with action_name, mapped_bones, unmapped_bones, frame_range.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    target_obj = bpy.data.objects.get(object_name)
    if not target_obj or target_obj.type != "ARMATURE":
        raise ValueError(f"Target armature not found: {object_name}")

    source_file = params.get("source_file")
    if not source_file:
        raise ValueError("source_file is required")
    if not os.path.isfile(source_file):
        raise ValueError(f"Source file not found: {source_file}")

    action_name = params.get("action_name")

    # Import the Mixamo FBX
    bpy.ops.import_scene.fbx(filepath=source_file)

    # Find the imported armature (has mixamorig: bones)
    source_obj = None
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE":
            bone_names = [b.name for b in obj.data.bones]
            if any(b.startswith("mixamorig:") for b in bone_names):
                source_obj = obj
                break

    if not source_obj:
        raise ValueError("No Mixamo armature found in imported FBX")

    # Build bone mapping filtered to bones existing on both rigs
    source_bones = [b.name for b in source_obj.data.bones]
    target_bones = [b.name for b in target_obj.data.bones]
    mapping_result = _map_mixamo_bones(source_bones, target_bones)
    mapped = mapping_result["mapped"]

    if not mapped:
        # Clean up imported object
        bpy.data.objects.remove(source_obj, do_unlink=True)
        raise ValueError("No bones could be mapped between source and target")

    # Apply constraint-based transfer (matching Phase 4 retarget pattern)
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.mode_set(mode="POSE")

    for src_bone, tgt_bone in mapped.items():
        tgt_pbone = target_obj.pose.bones.get(tgt_bone)
        if not tgt_pbone:
            continue

        # Add COPY_ROTATION constraint from source
        cr_con = tgt_pbone.constraints.new("COPY_ROTATION")
        cr_con.target = source_obj
        cr_con.subtarget = src_bone
        cr_con.name = f"mixamo_rot_{src_bone}"

    # G13: Add COPY_LOCATION for hip bone (root motion transfer)
    hip_mixamo = "mixamorig:Hips"
    hip_rigify = mapped.get(hip_mixamo)
    if hip_rigify:
        hip_tgt_pbone = target_obj.pose.bones.get(hip_rigify)
        if hip_tgt_pbone:
            cl_con = hip_tgt_pbone.constraints.new("COPY_LOCATION")
            cl_con.target = source_obj
            cl_con.subtarget = hip_mixamo
            cl_con.name = f"mixamo_loc_{hip_mixamo}"

    # Get frame range from source action
    src_action = None
    if source_obj.animation_data and source_obj.animation_data.action:
        src_action = source_obj.animation_data.action

    if src_action:
        frame_start = int(_action_frame_range(src_action)[0])
        frame_end = int(_action_frame_range(src_action)[1])
    else:
        frame_start = int(bpy.context.scene.frame_start)
        frame_end = int(bpy.context.scene.frame_end)

    # Bake the constrained animation with visual keying
    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        only_selected=False,
        bake_types={"POSE"},
        visual_keying=True,
        clear_constraints=True,
    )

    # Rename the baked action
    if target_obj.animation_data and target_obj.animation_data.action:
        if action_name:
            target_obj.animation_data.action.name = action_name
        result_action_name = target_obj.animation_data.action.name
    else:
        result_action_name = action_name or "mixamo_retarget"

    bpy.ops.object.mode_set(mode="OBJECT")

    # Clean up: remove imported source armature and its meshes
    for child in list(source_obj.children):
        bpy.data.objects.remove(child, do_unlink=True)
    bpy.data.objects.remove(source_obj, do_unlink=True)

    return {
        "action_name": result_action_name,
        "mapped_bones": len(mapped),
        "unmapped_bones": mapping_result["unmapped_source"],
        "frame_range": [frame_start, frame_end],
    }


VALID_AI_MOTION_MODELS: tuple[str, ...] = (
    "hy-motion", "motion-gpt", "motiondiffuse",
)

# Environment variable for custom AI motion API endpoint
AI_MOTION_ENDPOINT_ENV = "VB_AI_MOTION_ENDPOINT"


def _validate_ai_motion_params(params: dict) -> dict:
    """Validate AI motion generation parameters (pure-logic, testable).

    Args:
        params: Handler params dict.

    Returns:
        Dict with valid=True and normalized params, or valid=False with errors.
    """
    errors: list[str] = []

    object_name = params.get("object_name")
    if not object_name or not isinstance(object_name, str):
        errors.append("object_name is required and must be a non-empty string")

    prompt = params.get("prompt")
    if not prompt or not isinstance(prompt, str):
        errors.append("prompt is required and must be a non-empty string")

    model = params.get("model", "hy-motion")
    if model not in VALID_AI_MOTION_MODELS:
        errors.append(
            f"model must be one of {VALID_AI_MOTION_MODELS}, got '{model}'"
        )

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 1:
        errors.append("frame_count must be >= 1")

    fps = int(params.get("fps", 30))
    if fps < 1:
        errors.append("fps must be >= 1")

    style = params.get("style", "realistic")
    valid_styles = ("realistic", "stylized", "exaggerated", "subtle")
    if style not in valid_styles:
        errors.append(f"style must be one of {valid_styles}, got '{style}'")

    duration = params.get("duration")
    if duration is not None:
        duration = float(duration)
        if duration <= 0:
            errors.append("duration must be > 0")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "object_name": object_name,
        "prompt": prompt or "",
        "model": model,
        "frame_count": frame_count,
        "fps": fps,
        "style": style,
        "duration": duration,
    }


def _attempt_ai_motion_api(
    prompt: str,
    model: str,
    frame_count: int,
    fps: int,
    style: str,
    duration: float | None,
) -> dict | None:
    """Attempt to call an external AI motion API.

    Checks for VB_AI_MOTION_ENDPOINT env var. If set, sends HTTP POST
    with the motion request. Returns keyframe data dict on success,
    None if endpoint not configured or request fails.
    """
    endpoint = os.environ.get(AI_MOTION_ENDPOINT_ENV, "")
    if not endpoint:
        return None

    # Validate endpoint -- only http/https schemes allowed (no file://)
    if not endpoint.startswith(("http://", "https://")):
        return None

    try:
        import json
        import requests  # type: ignore[import-untyped]

        payload = {
            "prompt": prompt,
            "model": model,
            "frame_count": frame_count,
            "fps": fps,
            "style": style,
            "duration": duration or (frame_count / fps),
        }

        resp = requests.post(endpoint, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            if "keyframes" in data:
                return data
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError):
        pass

    return None


def handle_generate_ai_motion(params: dict) -> dict:
    """AI motion generation with API + procedural fallback (ANIM-11/ANIM3-06).

    Generates animation from a text prompt using either:
    1. External AI motion API (if VB_AI_MOTION_ENDPOINT is configured)
    2. Procedural fallback using keyword extraction + existing generators

    The procedural fallback extracts motion verbs and body parts from the
    prompt text and combines them using generate_custom_keyframes from
    the animation_gaits module, plus combat timing data if attack keywords
    are detected.

    Params:
        object_name: Name of the target armature.
        prompt: Text description of desired motion.
        model: AI model (hy-motion/motion-gpt/motiondiffuse, default hy-motion).
        frame_count: Number of frames to generate (default 48).
        fps: Frames per second (default 30).
        style: Motion style (realistic/stylized/exaggerated/subtle).
        duration: Optional duration in seconds (overrides frame_count).

    Returns dict with status, generation_method, action_name, prompt,
    model, frame_count, keyframe_count.
    """
    validated = _validate_ai_motion_params(params)
    if not validated["valid"]:
        raise ValueError(
            f"Invalid AI motion params: {'; '.join(validated['errors'])}"
        )

    object_name = validated["object_name"]
    prompt = validated["prompt"]
    model = validated["model"]
    fps = validated["fps"]
    style = validated["style"]
    duration = validated["duration"]

    # If duration specified, compute frame_count from it
    if duration is not None:
        frame_count = max(1, int(duration * fps))
    else:
        frame_count = validated["frame_count"]

    armature_obj = bpy.data.objects.get(object_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {object_name}")

    # Attempt external AI API first
    api_result = _attempt_ai_motion_api(
        prompt, model, frame_count, fps, style, duration,
    )

    generation_method = "api"
    keyframes = []

    if api_result and "keyframes" in api_result:
        # Parse API response into Keyframe namedtuples
        from .animation_gaits import Keyframe
        for kf_data in api_result["keyframes"]:
            keyframes.append(Keyframe(
                bone_name=kf_data.get("bone_name", "DEF-spine"),
                channel=kf_data.get("channel", "rotation_euler"),
                axis=kf_data.get("axis", 0),
                frame=kf_data.get("frame", 0),
                value=kf_data.get("value", 0.0),
            ))
    else:
        # Procedural fallback: use text-to-keyframe parser
        generation_method = "procedural_fallback"
        from .animation_gaits import generate_custom_keyframes
        keyframes = generate_custom_keyframes(prompt, frame_count=frame_count)

        # If attack keywords detected, enrich with combat timing
        attack_keywords = {"attack", "strike", "slash", "swing", "thrust", "slam", "hit", "punch", "kick"}
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in attack_keywords):
            from ._combat_timing import generate_combat_animation_data
            # Determine attack type from prompt
            attack_type = "light_attack"
            if "heavy" in prompt_lower or "slam" in prompt_lower:
                attack_type = "heavy_attack"
            elif "charge" in prompt_lower:
                attack_type = "charged_attack"
            elif "combo" in prompt_lower or "finisher" in prompt_lower:
                attack_type = "combo_finisher"

            combat_data = generate_combat_animation_data(
                attack_type, fps=fps,
            )
            # Append combat timing events as metadata (not keyframes)
            # The keyframes from generate_custom_keyframes already provide motion

    # Apply style scaling to keyframe values
    style_scale = {
        "realistic": 1.0,
        "stylized": 1.3,
        "exaggerated": 1.8,
        "subtle": 0.6,
    }.get(style, 1.0)

    if abs(style_scale - 1.0) > 1e-9:
        from .animation_gaits import Keyframe as KF
        keyframes = [
            KF(kf.bone_name, kf.channel, kf.axis, kf.frame, kf.value * style_scale)
            for kf in keyframes
        ]

    # Create Blender Action from keyframes
    action_name = f"AIMotion_{object_name}_{model}"
    action = bpy.data.actions.new(name=action_name)
    action.use_fake_user = True

    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Group keyframes by (bone, channel, axis) for fcurve creation
    fcurve_map: dict[tuple[str, str, int], list[tuple[int, float]]] = {}
    for kf in keyframes:
        key = (kf.bone_name, kf.channel, kf.axis)
        fcurve_map.setdefault(key, []).append((kf.frame, kf.value))

    for (bone_name, channel, axis), frames in fcurve_map.items():
        data_path = f'pose.bones["{bone_name}"].{channel}'
        fc = _action_new_fcurve(action, data_path, axis, armature_obj)
        fc.keyframe_points.add(count=len(frames))
        for i, (frame, value) in enumerate(frames):
            fc.keyframe_points[i].co = (frame, value)
            fc.keyframe_points[i].interpolation = "BEZIER"

    frame_range = [int(_action_frame_range(action)[0]), int(_action_frame_range(action)[1])]

    return {
        "status": "success",
        "generation_method": generation_method,
        "action_name": action.name,
        "prompt": prompt,
        "model": model,
        "style": style,
        "frame_count": frame_count,
        "keyframe_count": len(keyframes),
        "fcurve_count": get_fcurve_count(action),
        "frame_range": frame_range,
    }


def handle_batch_export(params: dict) -> dict:
    """Export each NLA action as a separate FBX file with Unity naming (ANIM-12).

    Iterates NLA strips, solos each one, and exports individual FBX files
    using Unity-compatible settings. Each file uses the naming convention
    ObjectName@ClipName.fbx for Unity auto-import.

    Params:
        object_name: Name of the armature object.
        output_dir: Directory to write FBX files (required).
        naming: Naming convention -- "unity" or "raw" (default "unity").
        actions: Optional list of action names to export (default all).

    Returns dict with exported_clips, clips, output_dir.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    armature_obj = bpy.data.objects.get(object_name)
    if not armature_obj or armature_obj.type != "ARMATURE":
        raise ValueError(f"Armature not found: {object_name}")

    # Validate batch export params
    be_valid = _validate_batch_export_params(params)
    if not be_valid["valid"]:
        raise ValueError(
            f"Invalid batch export params: {'; '.join(be_valid['errors'])}"
        )

    output_dir = params["output_dir"]
    naming = params.get("naming", "unity")
    action_filter = params.get("actions")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    anim_data = armature_obj.animation_data
    if not anim_data:
        raise ValueError("No animation data on armature")

    # If no NLA tracks, push current actions to NLA
    if not anim_data.nla_tracks or len(anim_data.nla_tracks) == 0:
        # Push all matching actions to NLA
        for action in bpy.data.actions:
            if action_filter and action.name not in action_filter:
                continue
            _push_action_to_nla(armature_obj, action)

    # Select the armature and its mesh children
    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    for child in armature_obj.children:
        if child.type == "MESH":
            child.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    # Export each NLA strip as separate FBX
    exported = []
    override = get_3d_context_override()

    for track in anim_data.nla_tracks:
        for strip in track.strips:
            if strip.mute:
                continue

            # Apply action filter
            if action_filter and strip.name not in action_filter:
                continue

            # Solo this strip
            saved_states = _solo_nla_strip(anim_data, strip)

            # Generate filename
            filename = _generate_unity_filename(object_name, strip.name, naming)
            filepath = os.path.join(output_dir, filename)

            # FBX export with Unity animation settings
            kwargs = {
                "filepath": filepath,
                "use_selection": True,
                "bake_anim": True,
                "bake_anim_use_nla_strips": True,
                "bake_anim_use_all_actions": False,
                "bake_anim_force_startend_keying": True,
                "bake_anim_step": 1.0,
                "apply_scale_options": "FBX_SCALE_ALL",
                "axis_forward": "-Z",
                "axis_up": "Y",
                "add_leaf_bones": False,
                "mesh_smooth_type": "FACE",
                "use_tspace": True,
                "use_armature_deform_only": True,
            }

            if override:
                with bpy.context.temp_override(**override):
                    bpy.ops.export_scene.fbx(**kwargs)
            else:
                bpy.ops.export_scene.fbx(**kwargs)

            frame_range = [int(strip.frame_start), int(strip.frame_end)]
            exported.append({
                "name": strip.name,
                "filepath": filepath,
                "frame_range": frame_range,
            })

            # Restore mute states
            _restore_nla_mute_states(anim_data, saved_states)

    return {
        "exported_clips": len(exported),
        "clips": exported,
        "output_dir": output_dir,
    }
