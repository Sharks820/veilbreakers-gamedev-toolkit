"""AAA animation production tools: FK/IK switching, motion retargeting,
mocap import, pose library, animation layers, keyframe editing, and
contact solving.

Provides 7 handler functions:
  - handle_fk_ik_switch: Toggle FK/IK on a rig limb with pose matching (GAP-62)
  - handle_retarget_motion: Retarget animation between armatures (GAP-63a)
  - handle_import_mocap: Import BVH/FBX motion capture data (GAP-63b)
  - handle_pose_library: Save/load/blend/list/delete named poses (GAP-64a)
  - handle_animation_layer: NLA-based additive animation layers (GAP-64b)
  - handle_keyframe_edit: F-curve and keyframe editing operations (GAP-65)
  - handle_contact_solver: Foot/hand contact stabilization (GAP-66)

Pure-logic helpers are separated for testability without Blender:
  - compute_bone_mapping_auto: Fuzzy bone name matching
  - compute_noise_filter: Remove sub-threshold keyframes
  - compute_contact_phases: Detect contact frame ranges from height data
  - lerp_pose: Interpolate between two pose dicts
  - compute_euler_filter: Fix euler angle discontinuities (360-flip removal)
  - validate_fk_ik_params / validate_retarget_params / validate_mocap_params
  - validate_pose_library_params / validate_animation_layer_params
  - validate_keyframe_edit_params / validate_contact_solver_params
"""

from __future__ import annotations

import math
import re

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from ._action_compat import (
    get_fcurve_count,
    get_fcurves,
    get_frame_range,
    is_layered_action,
    new_fcurve,
    remove_fcurve,
    setup_action_for_armature,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_LIMBS: frozenset[str] = frozenset({"arm_L", "arm_R", "leg_L", "leg_R"})
VALID_FK_IK_MODES: frozenset[str] = frozenset({"FK", "IK"})

LIMB_CHAIN_MAP: dict[str, dict] = {
    "arm_L": {
        "bones": ["DEF-upper_arm.L", "DEF-forearm.L", "DEF-hand.L"],
        "ik_bone": "DEF-hand.L",
        "pole_bone": "DEF-forearm.L",
    },
    "arm_R": {
        "bones": ["DEF-upper_arm.R", "DEF-forearm.R", "DEF-hand.R"],
        "ik_bone": "DEF-hand.R",
        "pole_bone": "DEF-forearm.R",
    },
    "leg_L": {
        "bones": ["DEF-thigh.L", "DEF-shin.L", "DEF-foot.L"],
        "ik_bone": "DEF-foot.L",
        "pole_bone": "DEF-shin.L",
    },
    "leg_R": {
        "bones": ["DEF-thigh.R", "DEF-shin.R", "DEF-foot.R"],
        "ik_bone": "DEF-foot.R",
        "pole_bone": "DEF-shin.R",
    },
}

VALID_POSE_ACTIONS: frozenset[str] = frozenset({
    "save", "load", "list", "delete", "blend",
})

VALID_POSE_CATEGORIES: frozenset[str] = frozenset({
    "combat", "idle", "expression", "locomotion", "custom",
})

VALID_LAYER_ACTIONS: frozenset[str] = frozenset({
    "add_layer", "remove_layer", "set_weight", "list_layers",
})

VALID_BLEND_MODES: frozenset[str] = frozenset({"REPLACE", "ADD", "MULTIPLY"})

VALID_KEYFRAME_OPERATIONS: frozenset[str] = frozenset({
    "insert", "delete", "move", "set_interpolation", "set_handle",
    "scale_time", "smooth", "clean", "sample", "euler_filter",
})

VALID_INTERPOLATIONS: frozenset[str] = frozenset({
    "CONSTANT", "LINEAR", "BEZIER", "BOUNCE", "ELASTIC",
})

VALID_HANDLE_TYPES: frozenset[str] = frozenset({
    "AUTO", "AUTO_CLAMPED", "ALIGNED", "FREE", "VECTOR",
})

VALID_CHANNELS: frozenset[str] = frozenset({
    "location", "rotation_quaternion", "rotation_euler", "scale",
})


# ---------------------------------------------------------------------------
# Pure-logic validation helpers (testable without Blender)
# ---------------------------------------------------------------------------


def validate_fk_ik_params(params: dict) -> dict:
    """Validate FK/IK switch parameters.

    Args:
        params: Dict with armature_name, limb, mode, match_pose.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    armature_name = params.get("armature_name")
    if not armature_name or not isinstance(armature_name, str):
        raise ValueError("armature_name is required and must be a non-empty string")

    limb = params.get("limb")
    if limb not in VALID_LIMBS:
        raise ValueError(
            f"Invalid limb: {limb!r}. Valid: {sorted(VALID_LIMBS)}"
        )

    mode = params.get("mode")
    if mode not in VALID_FK_IK_MODES:
        raise ValueError(
            f"Invalid mode: {mode!r}. Valid: {sorted(VALID_FK_IK_MODES)}"
        )

    match_pose = params.get("match_pose", True)
    if not isinstance(match_pose, bool):
        match_pose = bool(match_pose)

    return {
        "armature_name": armature_name,
        "limb": limb,
        "mode": mode,
        "match_pose": match_pose,
    }


def validate_retarget_params(params: dict) -> dict:
    """Validate motion retargeting parameters.

    Args:
        params: Dict with source_armature, target_armature, bone_mapping, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    source = params.get("source_armature")
    if not source or not isinstance(source, str):
        raise ValueError("source_armature is required and must be a non-empty string")

    target = params.get("target_armature")
    if not target or not isinstance(target, str):
        raise ValueError("target_armature is required and must be a non-empty string")

    if source == target:
        raise ValueError("source_armature and target_armature must be different")

    bone_mapping = params.get("bone_mapping")
    if bone_mapping is not None:
        if not isinstance(bone_mapping, dict) or not bone_mapping:
            raise ValueError("bone_mapping must be a non-empty dict if provided")

    frame_range = params.get("frame_range")
    if frame_range is not None:
        if (not isinstance(frame_range, (list, tuple))
                or len(frame_range) != 2
                or frame_range[0] > frame_range[1]):
            raise ValueError(
                "frame_range must be [start, end] with start <= end"
            )

    scale_factor = float(params.get("scale_factor", 1.0))
    if scale_factor <= 0:
        raise ValueError(f"scale_factor must be > 0, got {scale_factor}")

    clean_noise = params.get("clean_noise", False)
    noise_threshold = float(params.get("noise_threshold", 0.001))
    if noise_threshold < 0:
        raise ValueError(f"noise_threshold must be >= 0, got {noise_threshold}")

    return {
        "source_armature": source,
        "target_armature": target,
        "bone_mapping": bone_mapping,
        "frame_range": list(frame_range) if frame_range else None,
        "scale_factor": scale_factor,
        "clean_noise": bool(clean_noise),
        "noise_threshold": noise_threshold,
    }


def validate_mocap_params(params: dict) -> dict:
    """Validate mocap import parameters.

    Args:
        params: Dict with file_path, target_armature, scale, frame_start.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    file_path = params.get("file_path")
    if not file_path or not isinstance(file_path, str):
        raise ValueError("file_path is required and must be a non-empty string")

    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    if ext not in ("bvh", "fbx"):
        raise ValueError(
            f"Unsupported file format: {ext!r}. Supported: bvh, fbx"
        )

    target_armature = params.get("target_armature")
    # target_armature is optional

    scale = float(params.get("scale", 1.0))
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")

    frame_start = int(params.get("frame_start", 1))

    return {
        "file_path": file_path,
        "file_format": ext,
        "target_armature": target_armature,
        "scale": scale,
        "frame_start": frame_start,
    }


def validate_pose_library_params(params: dict) -> dict:
    """Validate pose library parameters.

    Args:
        params: Dict with armature_name, action, pose_name, category, blend_factor.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    armature_name = params.get("armature_name")
    if not armature_name or not isinstance(armature_name, str):
        raise ValueError("armature_name is required and must be a non-empty string")

    action = params.get("action")
    if action not in VALID_POSE_ACTIONS:
        raise ValueError(
            f"Invalid action: {action!r}. Valid: {sorted(VALID_POSE_ACTIONS)}"
        )

    pose_name = params.get("pose_name")
    # pose_name required for save, load, delete, blend
    if action in ("save", "load", "delete", "blend"):
        if not pose_name or not isinstance(pose_name, str):
            raise ValueError(
                f"pose_name is required for action '{action}'"
            )

    category = params.get("category", "custom")
    if category not in VALID_POSE_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category!r}. Valid: {sorted(VALID_POSE_CATEGORIES)}"
        )

    blend_factor = float(params.get("blend_factor", 1.0))
    if not 0.0 <= blend_factor <= 1.0:
        raise ValueError(
            f"blend_factor must be in [0.0, 1.0], got {blend_factor}"
        )

    return {
        "armature_name": armature_name,
        "action": action,
        "pose_name": pose_name,
        "category": category,
        "blend_factor": blend_factor,
    }


def validate_animation_layer_params(params: dict) -> dict:
    """Validate animation layer parameters.

    Args:
        params: Dict with armature_name, action, layer_name, weight, blend_mode.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    armature_name = params.get("armature_name")
    if not armature_name or not isinstance(armature_name, str):
        raise ValueError("armature_name is required and must be a non-empty string")

    action = params.get("action")
    if action not in VALID_LAYER_ACTIONS:
        raise ValueError(
            f"Invalid action: {action!r}. Valid: {sorted(VALID_LAYER_ACTIONS)}"
        )

    layer_name = params.get("layer_name")
    if action in ("add_layer", "remove_layer", "set_weight"):
        if not layer_name or not isinstance(layer_name, str):
            raise ValueError(
                f"layer_name is required for action '{action}'"
            )

    weight = float(params.get("weight", 1.0))
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"weight must be in [0.0, 1.0], got {weight}")

    blend_mode = params.get("blend_mode", "REPLACE")
    if blend_mode not in VALID_BLEND_MODES:
        raise ValueError(
            f"Invalid blend_mode: {blend_mode!r}. Valid: {sorted(VALID_BLEND_MODES)}"
        )

    return {
        "armature_name": armature_name,
        "action": action,
        "layer_name": layer_name,
        "weight": weight,
        "blend_mode": blend_mode,
    }


def validate_keyframe_edit_params(params: dict) -> dict:
    """Validate keyframe editing parameters.

    Args:
        params: Dict with armature_name, action_name, operation, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    armature_name = params.get("armature_name")
    if not armature_name or not isinstance(armature_name, str):
        raise ValueError("armature_name is required and must be a non-empty string")

    action_name = params.get("action_name")
    if not action_name or not isinstance(action_name, str):
        raise ValueError("action_name is required and must be a non-empty string")

    operation = params.get("operation")
    if operation not in VALID_KEYFRAME_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. Valid: {sorted(VALID_KEYFRAME_OPERATIONS)}"
        )

    bone_name = params.get("bone_name")  # optional
    channel = params.get("channel")  # optional
    if channel is not None and channel not in VALID_CHANNELS:
        raise ValueError(
            f"Invalid channel: {channel!r}. Valid: {sorted(VALID_CHANNELS)}"
        )

    frame = params.get("frame")
    if operation in ("insert", "delete", "move"):
        if frame is None:
            raise ValueError(f"frame is required for operation '{operation}'")
        frame = int(frame)

    value = params.get("value")
    if operation == "insert" and value is None:
        raise ValueError("value is required for operation 'insert'")
    if value is not None:
        value = float(value)

    interpolation = params.get("interpolation")
    if operation == "set_interpolation":
        if interpolation not in VALID_INTERPOLATIONS:
            raise ValueError(
                f"Invalid interpolation: {interpolation!r}. "
                f"Valid: {sorted(VALID_INTERPOLATIONS)}"
            )

    handle_type = params.get("handle_type")
    if operation == "set_handle":
        if handle_type not in VALID_HANDLE_TYPES:
            raise ValueError(
                f"Invalid handle_type: {handle_type!r}. "
                f"Valid: {sorted(VALID_HANDLE_TYPES)}"
            )

    time_scale = params.get("time_scale")
    if operation == "scale_time":
        if time_scale is None:
            raise ValueError("time_scale is required for operation 'scale_time'")
        time_scale = float(time_scale)
        if time_scale <= 0:
            raise ValueError(f"time_scale must be > 0, got {time_scale}")

    clean_threshold = float(params.get("clean_threshold", 0.001))
    if clean_threshold < 0:
        raise ValueError(f"clean_threshold must be >= 0, got {clean_threshold}")

    return {
        "armature_name": armature_name,
        "action_name": action_name,
        "operation": operation,
        "bone_name": bone_name,
        "channel": channel,
        "frame": frame,
        "value": value,
        "interpolation": interpolation,
        "handle_type": handle_type,
        "time_scale": time_scale,
        "clean_threshold": clean_threshold,
    }


def validate_contact_solver_params(params: dict) -> dict:
    """Validate contact solver parameters.

    Args:
        params: Dict with armature_name, action_name, contact_bones, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    armature_name = params.get("armature_name")
    if not armature_name or not isinstance(armature_name, str):
        raise ValueError("armature_name is required and must be a non-empty string")

    action_name = params.get("action_name")
    if not action_name or not isinstance(action_name, str):
        raise ValueError("action_name is required and must be a non-empty string")

    contact_bones = params.get("contact_bones")
    if not isinstance(contact_bones, (list, tuple)) or not contact_bones:
        raise ValueError("contact_bones must be a non-empty list of bone names")
    for bone in contact_bones:
        if not isinstance(bone, str) or not bone:
            raise ValueError(
                f"Each contact bone must be a non-empty string, got {bone!r}"
            )

    ground_height = float(params.get("ground_height", 0.0))

    contact_threshold = float(params.get("contact_threshold", 0.05))
    if contact_threshold < 0:
        raise ValueError(
            f"contact_threshold must be >= 0, got {contact_threshold}"
        )

    frame_range = params.get("frame_range")
    if frame_range is not None:
        if (not isinstance(frame_range, (list, tuple))
                or len(frame_range) != 2
                or frame_range[0] > frame_range[1]):
            raise ValueError(
                "frame_range must be [start, end] with start <= end"
            )

    lock_rotation = params.get("lock_rotation", False)

    return {
        "armature_name": armature_name,
        "action_name": action_name,
        "contact_bones": list(contact_bones),
        "ground_height": ground_height,
        "contact_threshold": contact_threshold,
        "frame_range": list(frame_range) if frame_range else None,
        "lock_rotation": bool(lock_rotation),
    }


# ---------------------------------------------------------------------------
# Pure-logic computation helpers (testable without Blender)
# ---------------------------------------------------------------------------


def compute_bone_mapping_auto(
    source_bones: list[str],
    target_bones: list[str],
) -> dict[str, str]:
    """Auto-detect bone mapping by fuzzy name matching.

    Matching strategy (in priority order):
      1. Exact match (case-insensitive)
      2. Match after stripping common prefixes (DEF-, MCH-, ORG-, mixamorig:)
      3. Match after stripping common suffixes (.L, .R, _L, _R, Left, Right)
      4. Substring containment match

    Args:
        source_bones: List of bone names from source armature.
        target_bones: List of bone names from target armature.

    Returns:
        Dict mapping source bone name to target bone name.
    """
    PREFIX_RE = re.compile(
        r"^(DEF-|MCH-|ORG-|mixamorig:|Bip01_|Bip01 |CC_Base_)", re.IGNORECASE,
    )
    SUFFIX_RE = re.compile(
        r"(\.(L|R)|_(L|R)|(Left|Right))$", re.IGNORECASE,
    )

    def _normalize(name: str) -> str:
        """Strip prefixes, suffixes, and lowercase for matching."""
        n = PREFIX_RE.sub("", name)
        n = SUFFIX_RE.sub("", n)
        return n.lower().replace("_", "").replace("-", "").replace(" ", "")

    def _side_suffix(name: str) -> str:
        """Extract side indicator (l/r/empty)."""
        m = SUFFIX_RE.search(name)
        if m:
            raw = m.group(0).lower().rstrip(".")
            if "l" in raw:
                return "l"
            if "r" in raw:
                return "r"
        return ""

    mapping: dict[str, str] = {}
    target_used: set[str] = set()

    # Build normalized target lookup
    target_norm: dict[str, list[str]] = {}
    for tb in target_bones:
        key = _normalize(tb)
        target_norm.setdefault(key, []).append(tb)

    # Pass 1: Exact case-insensitive match
    for sb in source_bones:
        for tb in target_bones:
            if tb in target_used:
                continue
            if sb.lower() == tb.lower():
                mapping[sb] = tb
                target_used.add(tb)
                break

    # Pass 2: Normalized name match (with side agreement)
    for sb in source_bones:
        if sb in mapping:
            continue
        s_norm = _normalize(sb)
        s_side = _side_suffix(sb)
        candidates = target_norm.get(s_norm, [])
        for tb in candidates:
            if tb in target_used:
                continue
            t_side = _side_suffix(tb)
            if s_side == t_side:
                mapping[sb] = tb
                target_used.add(tb)
                break

    # Pass 3: Normalized match ignoring side (fallback)
    for sb in source_bones:
        if sb in mapping:
            continue
        s_norm = _normalize(sb)
        candidates = target_norm.get(s_norm, [])
        for tb in candidates:
            if tb in target_used:
                continue
            mapping[sb] = tb
            target_used.add(tb)
            break

    # Pass 4: Substring containment
    for sb in source_bones:
        if sb in mapping:
            continue
        s_norm = _normalize(sb)
        if len(s_norm) < 3:
            continue  # too short for substring matching
        s_side = _side_suffix(sb)
        best_tb: str | None = None
        best_len: int = 0
        for tb in target_bones:
            if tb in target_used:
                continue
            t_norm = _normalize(tb)
            t_side = _side_suffix(tb)
            if s_side and t_side and s_side != t_side:
                continue
            if s_norm in t_norm or t_norm in s_norm:
                match_len = min(len(s_norm), len(t_norm))
                if match_len > best_len:
                    best_len = match_len
                    best_tb = tb
        if best_tb is not None:
            mapping[sb] = best_tb
            target_used.add(best_tb)

    return mapping


def compute_noise_filter(
    keyframes: list[tuple[float, float]],
    threshold: float,
) -> list[tuple[float, float]]:
    """Remove keyframes where delta value < threshold.

    Always preserves the first and last keyframes.

    Args:
        keyframes: List of (frame, value) tuples, assumed sorted by frame.
        threshold: Minimum value delta to keep a keyframe.

    Returns:
        Filtered list of (frame, value) tuples.
    """
    if len(keyframes) <= 2:
        return list(keyframes)

    result: list[tuple[float, float]] = [keyframes[0]]

    for i in range(1, len(keyframes) - 1):
        prev_val = result[-1][1]
        curr_val = keyframes[i][1]
        next_val = keyframes[i + 1][1]

        # Keep keyframe if it represents a significant change from the
        # previous kept keyframe OR from the next keyframe
        delta_from_prev = abs(curr_val - prev_val)
        delta_to_next = abs(next_val - curr_val)

        if delta_from_prev >= threshold or delta_to_next >= threshold:
            result.append(keyframes[i])

    result.append(keyframes[-1])
    return result


def compute_contact_phases(
    bone_heights: list[tuple[int, float]],
    ground: float,
    threshold: float,
) -> list[tuple[int, int]]:
    """Detect contact phase frame ranges from bone height data.

    A contact phase is a contiguous range of frames where the bone
    is within threshold distance of the ground plane.

    Args:
        bone_heights: List of (frame, height) tuples, sorted by frame.
        ground: Ground plane height.
        threshold: Distance from ground that counts as contact.

    Returns:
        List of (start_frame, end_frame) tuples for each contact phase.
    """
    if not bone_heights:
        return []

    phases: list[tuple[int, int]] = []
    in_contact = False
    phase_start = 0

    for frame, height in bone_heights:
        dist = abs(height - ground)
        if dist <= threshold:
            if not in_contact:
                phase_start = frame
                in_contact = True
        else:
            if in_contact:
                phases.append((phase_start, frame - 1))
                in_contact = False

    # Close final phase if still in contact
    if in_contact:
        phases.append((phase_start, bone_heights[-1][0]))

    return phases


def lerp_pose(
    pose_a: dict[str, dict],
    pose_b: dict[str, dict],
    factor: float,
) -> dict[str, dict]:
    """Linearly interpolate between two pose dictionaries.

    Each pose is a dict of bone_name -> {"location": [x,y,z],
    "rotation": [w,x,y,z], "scale": [x,y,z]}.

    Args:
        pose_a: First pose dictionary.
        pose_b: Second pose dictionary.
        factor: Interpolation factor (0.0 = pose_a, 1.0 = pose_b).

    Returns:
        Interpolated pose dictionary. Only bones present in both poses
        are included.
    """
    factor = max(0.0, min(1.0, factor))
    result: dict[str, dict] = {}

    common_bones = set(pose_a.keys()) & set(pose_b.keys())

    for bone in common_bones:
        a = pose_a[bone]
        b = pose_b[bone]
        bone_data: dict = {}

        # Interpolate location
        if "location" in a and "location" in b:
            loc_a = a["location"]
            loc_b = b["location"]
            bone_data["location"] = [
                loc_a[i] + (loc_b[i] - loc_a[i]) * factor
                for i in range(3)
            ]

        # Interpolate rotation (quaternion slerp approximation via nlerp)
        if "rotation" in a and "rotation" in b:
            rot_a = a["rotation"]
            rot_b = b["rotation"]
            # Check dot product for shortest path
            dot = sum(rot_a[i] * rot_b[i] for i in range(4))
            sign = 1.0 if dot >= 0 else -1.0
            interp = [
                rot_a[i] + (sign * rot_b[i] - rot_a[i]) * factor
                for i in range(4)
            ]
            # Normalize
            length = math.sqrt(sum(v * v for v in interp))
            if length > 1e-8:
                interp = [v / length for v in interp]
            bone_data["rotation"] = interp

        # Interpolate scale
        if "scale" in a and "scale" in b:
            scl_a = a["scale"]
            scl_b = b["scale"]
            bone_data["scale"] = [
                scl_a[i] + (scl_b[i] - scl_a[i]) * factor
                for i in range(3)
            ]

        result[bone] = bone_data

    return result


def compute_euler_filter(
    eulers: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Fix euler angle discontinuities (360-degree flips).

    When euler angles jump by approximately +/-2*pi between consecutive
    frames, this filter adds/subtracts 2*pi to maintain continuity.

    Args:
        eulers: List of (x, y, z) euler angle tuples in radians.

    Returns:
        Corrected list of euler tuples.
    """
    if len(eulers) <= 1:
        return list(eulers)

    TWO_PI = 2.0 * math.pi
    FLIP_THRESHOLD = math.pi  # > 180 degree jump = flip

    result: list[tuple[float, float, float]] = [eulers[0]]
    # Track accumulated offsets per axis
    offsets = [0.0, 0.0, 0.0]

    for i in range(1, len(eulers)):
        corrected = list(eulers[i])
        for axis in range(3):
            raw = eulers[i][axis] + offsets[axis]
            prev = result[-1][axis]
            delta = raw - prev

            while delta > FLIP_THRESHOLD:
                offsets[axis] -= TWO_PI
                raw -= TWO_PI
                delta = raw - prev

            while delta < -FLIP_THRESHOLD:
                offsets[axis] += TWO_PI
                raw += TWO_PI
                delta = raw - prev

            corrected[axis] = raw

        result.append((corrected[0], corrected[1], corrected[2]))

    return result


# ---------------------------------------------------------------------------
# Blender-dependent handler functions
# ---------------------------------------------------------------------------


def _get_armature(name: str):
    """Get armature object by name, raise ValueError if not found or wrong type."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name!r}")
    if obj.type != "ARMATURE":
        raise ValueError(f"Object {name!r} is not an armature (type={obj.type})")
    return obj


def _ensure_action(armature_obj, action_name: str):
    """Get or create an action on the armature."""
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()

    action = bpy.data.actions.get(action_name)
    if action is None:
        action = bpy.data.actions.new(name=action_name)

    armature_obj.animation_data.action = action
    return action


def _get_pose_bone(armature_obj, bone_name: str):
    """Get a pose bone, raise ValueError if not found."""
    pb = armature_obj.pose.bones.get(bone_name)
    if pb is None:
        raise ValueError(
            f"Bone {bone_name!r} not found on armature {armature_obj.name!r}"
        )
    return pb


def _snapshot_bone_transforms(armature_obj) -> dict:
    """Capture current pose bone transforms as a serializable dict."""
    pose_data: dict[str, dict] = {}
    for pb in armature_obj.pose.bones:
        bone_data: dict = {}
        bone_data["location"] = list(pb.location)
        if pb.rotation_mode == "QUATERNION":
            bone_data["rotation"] = list(pb.rotation_quaternion)
        else:
            bone_data["rotation_euler"] = list(pb.rotation_euler)
            bone_data["rotation_mode"] = pb.rotation_mode
        bone_data["scale"] = list(pb.scale)
        pose_data[pb.name] = bone_data
    return pose_data


def _apply_bone_transforms(armature_obj, pose_data: dict) -> int:
    """Apply a saved pose dict to an armature's pose bones.

    Returns the number of bones applied.
    """
    count = 0
    for bone_name, data in pose_data.items():
        pb = armature_obj.pose.bones.get(bone_name)
        if pb is None:
            continue
        if "location" in data:
            pb.location = data["location"]
        if "rotation" in data:
            if pb.rotation_mode == "QUATERNION":
                pb.rotation_quaternion = data["rotation"]
            else:
                # Convert quaternion to euler
                q = Quaternion(data["rotation"])
                pb.rotation_euler = q.to_euler(pb.rotation_mode)
        if "rotation_euler" in data:
            pb.rotation_euler = data["rotation_euler"]
        if "scale" in data:
            pb.scale = data["scale"]
        count += 1
    return count


def handle_fk_ik_switch(params: dict) -> dict:
    """Toggle between FK and IK on a rig's limb chain.

    Finds the IK constraint on the chain's end bone, toggles influence,
    and optionally matches the pose so the limb doesn't jump.
    """
    p = validate_fk_ik_params(params)
    armature_obj = _get_armature(p["armature_name"])
    limb_info = LIMB_CHAIN_MAP[p["limb"]]
    chain_bones = limb_info["bones"]
    ik_bone_name = limb_info["ik_bone"]

    # Get the IK end bone
    ik_pb = _get_pose_bone(armature_obj, ik_bone_name)

    # Find IK constraint
    ik_constraint = None
    for c in ik_pb.constraints:
        if c.type == "IK":
            ik_constraint = c
            break

    if ik_constraint is None:
        raise ValueError(
            f"No IK constraint found on bone {ik_bone_name!r}. "
            f"Add an IK constraint before switching."
        )

    # Capture current world-space matrices before switching
    pre_matrices = {}
    if p["match_pose"]:
        bpy.context.view_layer.update()
        for bone_name in chain_bones:
            pb = _get_pose_bone(armature_obj, bone_name)
            pre_matrices[bone_name] = pb.matrix.copy()

    if p["mode"] == "IK":
        # FK -> IK: Enable IK constraint
        ik_constraint.influence = 1.0

        if p["match_pose"] and ik_constraint.target:
            # Move IK target to current end-effector position
            target_obj = ik_constraint.target
            end_pb = _get_pose_bone(armature_obj, ik_bone_name)
            target_obj.location = end_pb.matrix.translation.copy()
    else:
        # IK -> FK: Capture current bone rotations, then disable IK
        if p["match_pose"]:
            bpy.context.view_layer.update()
            # Store world-space rotations while IK is active
            fk_rotations = {}
            for bone_name in chain_bones:
                pb = _get_pose_bone(armature_obj, bone_name)
                fk_rotations[bone_name] = pb.matrix.copy()

        ik_constraint.influence = 0.0

        if p["match_pose"]:
            # Apply stored rotations as FK pose
            bpy.context.view_layer.update()
            for bone_name in chain_bones:
                pb = _get_pose_bone(armature_obj, bone_name)
                # Convert world matrix to local bone space
                if pb.parent:
                    local_mat = pb.parent.matrix.inverted() @ fk_rotations[bone_name]
                else:
                    local_mat = fk_rotations[bone_name]
                pb.matrix = local_mat

    bpy.context.view_layer.update()

    return {
        "status": "ok",
        "armature": p["armature_name"],
        "limb": p["limb"],
        "mode": p["mode"],
        "ik_influence": ik_constraint.influence,
        "match_pose": p["match_pose"],
        "chain_bones": chain_bones,
    }


def handle_retarget_motion(params: dict) -> dict:
    """Retarget animation from source armature to target armature.

    For each frame in range: reads source bone world-space rotations,
    applies bone_mapping to find target bones, sets target bone rotations
    (accounting for rest pose differences), and keyframes the target.
    """
    p = validate_retarget_params(params)
    src_obj = _get_armature(p["source_armature"])
    tgt_obj = _get_armature(p["target_armature"])

    # Build bone mapping
    if p["bone_mapping"]:
        bone_mapping = p["bone_mapping"]
    else:
        src_bones = [b.name for b in src_obj.pose.bones]
        tgt_bones = [b.name for b in tgt_obj.pose.bones]
        bone_mapping = compute_bone_mapping_auto(src_bones, tgt_bones)

    if not bone_mapping:
        raise ValueError("No bone mapping could be established between armatures")

    # Determine frame range from source action
    if src_obj.animation_data is None or src_obj.animation_data.action is None:
        raise ValueError(
            f"Source armature {p['source_armature']!r} has no active action"
        )
    src_action = src_obj.animation_data.action

    cb, layered = setup_action_for_armature(src_action, src_obj)
    if p["frame_range"]:
        frame_start, frame_end = p["frame_range"]
    else:
        fr = get_frame_range(src_action, cb, layered)
        frame_start, frame_end = fr[0], fr[1]

    # Ensure target has an action
    tgt_action_name = f"{tgt_obj.name}_{src_action.name}_retarget"
    tgt_action = bpy.data.actions.new(name=tgt_action_name)
    if tgt_obj.animation_data is None:
        tgt_obj.animation_data_create()
    tgt_obj.animation_data.action = tgt_action

    scale = p["scale_factor"]
    keyframed_bones = 0

    # Pre-compute rest pose inverse matrices for offset correction
    src_rest_inv: dict[str, Matrix] = {}
    tgt_rest: dict[str, Matrix] = {}
    for src_bone_name, tgt_bone_name in bone_mapping.items():
        src_data_bone = src_obj.data.bones.get(src_bone_name)
        tgt_data_bone = tgt_obj.data.bones.get(tgt_bone_name)
        if src_data_bone and tgt_data_bone:
            src_rest_inv[src_bone_name] = src_data_bone.matrix_local.inverted()
            tgt_rest[tgt_bone_name] = tgt_data_bone.matrix_local

    # Retarget each frame
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)

        for src_bone_name, tgt_bone_name in bone_mapping.items():
            src_pb = src_obj.pose.bones.get(src_bone_name)
            tgt_pb = tgt_obj.pose.bones.get(tgt_bone_name)
            if src_pb is None or tgt_pb is None:
                continue

            # Get source world-space rotation
            src_world_mat = src_obj.matrix_world @ src_pb.matrix

            # Compute rotation delta from rest pose
            if src_bone_name in src_rest_inv:
                delta_rot = src_rest_inv[src_bone_name] @ src_pb.matrix
            else:
                delta_rot = src_pb.matrix

            # Apply to target bone
            if tgt_bone_name in tgt_rest:
                tgt_local = tgt_rest[tgt_bone_name] @ delta_rot
            else:
                tgt_local = delta_rot

            # Apply rotation
            if tgt_pb.rotation_mode == "QUATERNION":
                tgt_pb.rotation_quaternion = tgt_local.to_quaternion()
                tgt_pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            else:
                tgt_pb.rotation_euler = tgt_local.to_euler(tgt_pb.rotation_mode)
                tgt_pb.keyframe_insert(data_path="rotation_euler", frame=frame)

            # Apply scaled location (for root motion)
            if src_pb.parent is None:
                tgt_pb.location = Vector(src_pb.location) * scale
                tgt_pb.keyframe_insert(data_path="location", frame=frame)

            keyframed_bones += 1

    # Optional noise cleaning
    cleaned_keys = 0
    if p["clean_noise"]:
        tgt_cb, tgt_layered = setup_action_for_armature(tgt_action, tgt_obj)
        fcurves = list(get_fcurves(tgt_action, tgt_cb, tgt_layered))
        for fc in fcurves:
            kf_data = [(kp.co[0], kp.co[1]) for kp in fc.keyframe_points]
            filtered = compute_noise_filter(kf_data, p["noise_threshold"])
            removed = len(kf_data) - len(filtered)
            cleaned_keys += removed
            if removed > 0:
                # Rebuild keyframe points
                filtered_frames = {f for f, _ in filtered}
                to_remove = [
                    kp for kp in fc.keyframe_points
                    if kp.co[0] not in filtered_frames
                ]
                for kp in reversed(to_remove):
                    fc.keyframe_points.remove(kp)

    return {
        "status": "ok",
        "source": p["source_armature"],
        "target": p["target_armature"],
        "action_name": tgt_action_name,
        "frame_range": [frame_start, frame_end],
        "mapped_bones": len(bone_mapping),
        "keyframed_bones_per_frame": keyframed_bones // max(frame_end - frame_start + 1, 1),
        "total_keyframes": keyframed_bones,
        "cleaned_keyframes": cleaned_keys,
        "bone_mapping": bone_mapping,
    }


def handle_import_mocap(params: dict) -> dict:
    """Import BVH/FBX motion capture data.

    Supports BVH and FBX formats. Optionally retargets to an existing armature.
    """
    p = validate_mocap_params(params)

    # Import based on format
    if p["file_format"] == "bvh":
        bpy.ops.import_anim.bvh(
            filepath=p["file_path"],
            global_scale=p["scale"],
            frame_start=p["frame_start"],
            use_fps_scale=True,
        )
    else:
        bpy.ops.import_scene.fbx(
            filepath=p["file_path"],
            global_scale=p["scale"],
            use_anim=True,
        )

    # Find the imported armature (most recently created)
    imported_armature = None
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE":
            imported_armature = obj
            break

    if imported_armature is None:
        raise ValueError("No armature found in imported file")

    result = {
        "status": "ok",
        "imported_armature": imported_armature.name,
        "file_path": p["file_path"],
        "format": p["file_format"],
        "bone_count": len(imported_armature.data.bones),
    }

    # Optionally retarget to target armature
    if p["target_armature"]:
        retarget_result = handle_retarget_motion({
            "source_armature": imported_armature.name,
            "target_armature": p["target_armature"],
            "scale_factor": p["scale"],
        })
        result["retarget"] = retarget_result

    return result


def handle_pose_library(params: dict) -> dict:
    """Manage pose library for an armature.

    Uses custom properties on the armature to store named poses,
    organized by category.
    """
    p = validate_pose_library_params(params)
    armature_obj = _get_armature(p["armature_name"])

    # Initialize pose library storage as custom property
    PROP_KEY = "vb_pose_library"
    import json as _json

    if PROP_KEY not in armature_obj:
        armature_obj[PROP_KEY] = _json.dumps({})

    try:
        library = _json.loads(armature_obj[PROP_KEY])
    except (ValueError, TypeError):
        library = {}

    action = p["action"]

    if action == "save":
        pose_data = _snapshot_bone_transforms(armature_obj)
        library[p["pose_name"]] = {
            "category": p["category"],
            "bones": pose_data,
        }
        armature_obj[PROP_KEY] = _json.dumps(library)
        return {
            "status": "ok",
            "action": "save",
            "pose_name": p["pose_name"],
            "category": p["category"],
            "bone_count": len(pose_data),
        }

    elif action == "load":
        if p["pose_name"] not in library:
            raise ValueError(f"Pose not found: {p['pose_name']!r}")
        pose_entry = library[p["pose_name"]]
        applied = _apply_bone_transforms(armature_obj, pose_entry["bones"])
        bpy.context.view_layer.update()
        return {
            "status": "ok",
            "action": "load",
            "pose_name": p["pose_name"],
            "bones_applied": applied,
        }

    elif action == "blend":
        if p["pose_name"] not in library:
            raise ValueError(f"Pose not found: {p['pose_name']!r}")
        pose_entry = library[p["pose_name"]]
        current_pose = _snapshot_bone_transforms(armature_obj)

        # Normalize current pose to match saved format
        normalized_current: dict[str, dict] = {}
        for bone_name, data in current_pose.items():
            nd: dict = {}
            nd["location"] = data.get("location", [0, 0, 0])
            if "rotation" in data:
                nd["rotation"] = data["rotation"]
            elif "rotation_euler" in data:
                # Convert euler to quat for lerp
                order = data.get("rotation_mode", "XYZ")
                e = Euler(data["rotation_euler"], order)
                q = e.to_quaternion()
                nd["rotation"] = [q.w, q.x, q.y, q.z]
            else:
                nd["rotation"] = [1, 0, 0, 0]
            nd["scale"] = data.get("scale", [1, 1, 1])
            normalized_current[bone_name] = nd

        normalized_saved: dict[str, dict] = {}
        for bone_name, data in pose_entry["bones"].items():
            nd2: dict = {}
            nd2["location"] = data.get("location", [0, 0, 0])
            if "rotation" in data:
                nd2["rotation"] = data["rotation"]
            elif "rotation_euler" in data:
                order = data.get("rotation_mode", "XYZ")
                e = Euler(data["rotation_euler"], order)
                q = e.to_quaternion()
                nd2["rotation"] = [q.w, q.x, q.y, q.z]
            else:
                nd2["rotation"] = [1, 0, 0, 0]
            nd2["scale"] = data.get("scale", [1, 1, 1])
            normalized_saved[bone_name] = nd2

        blended = lerp_pose(normalized_current, normalized_saved, p["blend_factor"])

        applied = _apply_bone_transforms(armature_obj, blended)
        bpy.context.view_layer.update()
        return {
            "status": "ok",
            "action": "blend",
            "pose_name": p["pose_name"],
            "blend_factor": p["blend_factor"],
            "bones_blended": applied,
        }

    elif action == "list":
        poses = []
        for name, entry in library.items():
            poses.append({
                "name": name,
                "category": entry.get("category", "custom"),
                "bone_count": len(entry.get("bones", {})),
            })
        return {
            "status": "ok",
            "action": "list",
            "poses": poses,
            "total": len(poses),
        }

    elif action == "delete":
        if p["pose_name"] not in library:
            raise ValueError(f"Pose not found: {p['pose_name']!r}")
        del library[p["pose_name"]]
        armature_obj[PROP_KEY] = _json.dumps(library)
        return {
            "status": "ok",
            "action": "delete",
            "pose_name": p["pose_name"],
        }

    return {"status": "error", "message": f"Unknown action: {action}"}


def handle_animation_layer(params: dict) -> dict:
    """Manage additive animation layers via NLA (Non-Linear Animation).

    Uses NLA tracks and strips to implement weighted, blendable animation layers.
    """
    p = validate_animation_layer_params(params)
    armature_obj = _get_armature(p["armature_name"])

    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()

    anim_data = armature_obj.animation_data
    action = p["action"]

    if action == "add_layer":
        # Create a new NLA track with an action strip
        track = anim_data.nla_tracks.new()
        track.name = p["layer_name"]

        # Create or find an action for this layer
        layer_action = bpy.data.actions.get(f"NLA_{p['layer_name']}")
        if layer_action is None:
            layer_action = bpy.data.actions.new(name=f"NLA_{p['layer_name']}")

        frame_start = 1
        strip = track.strips.new(p["layer_name"], int(frame_start), layer_action)
        strip.influence = p["weight"]

        # Set blend type
        blend_map = {
            "REPLACE": "REPLACE",
            "ADD": "ADD",
            "MULTIPLY": "MULTIPLY",
        }
        strip.blend_type = blend_map.get(p["blend_mode"], "REPLACE")

        return {
            "status": "ok",
            "action": "add_layer",
            "layer_name": p["layer_name"],
            "weight": p["weight"],
            "blend_mode": p["blend_mode"],
            "action_name": layer_action.name,
        }

    elif action == "remove_layer":
        track_to_remove = None
        for track in anim_data.nla_tracks:
            if track.name == p["layer_name"]:
                track_to_remove = track
                break
        if track_to_remove is None:
            raise ValueError(
                f"NLA track not found: {p['layer_name']!r}"
            )
        anim_data.nla_tracks.remove(track_to_remove)
        return {
            "status": "ok",
            "action": "remove_layer",
            "layer_name": p["layer_name"],
        }

    elif action == "set_weight":
        found = False
        for track in anim_data.nla_tracks:
            if track.name == p["layer_name"]:
                for strip in track.strips:
                    strip.influence = p["weight"]
                found = True
                break
        if not found:
            raise ValueError(
                f"NLA track not found: {p['layer_name']!r}"
            )
        return {
            "status": "ok",
            "action": "set_weight",
            "layer_name": p["layer_name"],
            "weight": p["weight"],
        }

    elif action == "list_layers":
        layers = []
        for track in anim_data.nla_tracks:
            strips_info = []
            for strip in track.strips:
                strips_info.append({
                    "name": strip.name,
                    "influence": strip.influence,
                    "blend_type": strip.blend_type,
                    "frame_start": strip.frame_start,
                    "frame_end": strip.frame_end,
                })
            layers.append({
                "name": track.name,
                "mute": track.mute,
                "strips": strips_info,
            })
        return {
            "status": "ok",
            "action": "list_layers",
            "layers": layers,
            "total": len(layers),
        }

    return {"status": "error", "message": f"Unknown action: {action}"}


def handle_keyframe_edit(params: dict) -> dict:
    """Edit animation keyframes and F-curve properties.

    Supports insert, delete, move, set_interpolation, set_handle,
    scale_time, smooth, clean, sample, and euler_filter operations.
    """
    p = validate_keyframe_edit_params(params)
    armature_obj = _get_armature(p["armature_name"])

    action = bpy.data.actions.get(p["action_name"])
    if action is None:
        raise ValueError(f"Action not found: {p['action_name']!r}")

    cb, layered = setup_action_for_armature(action, armature_obj)
    fcurves = list(get_fcurves(action, cb, layered))

    # Filter fcurves by bone_name and/or channel
    if p["bone_name"] or p["channel"]:
        filtered = []
        for fc in fcurves:
            dp = fc.data_path
            if p["bone_name"] and p["bone_name"] not in dp:
                continue
            if p["channel"] and not dp.endswith(p["channel"]):
                continue
            filtered.append(fc)
        fcurves = filtered

    operation = p["operation"]
    modified = 0

    if operation == "insert":
        for fc in fcurves:
            fc.keyframe_points.insert(float(p["frame"]), p["value"])
            modified += 1
        # If no fcurves matched but we have bone/channel, create one
        if not fcurves and p["bone_name"] and p["channel"]:
            dp = f'pose.bones["{p["bone_name"]}"].{p["channel"]}'
            fc = new_fcurve(action, dp, 0, cb, layered)
            fc.keyframe_points.insert(float(p["frame"]), p["value"])
            modified = 1

    elif operation == "delete":
        for fc in fcurves:
            to_remove = [
                kp for kp in fc.keyframe_points
                if int(kp.co[0]) == p["frame"]
            ]
            for kp in reversed(to_remove):
                fc.keyframe_points.remove(kp)
                modified += 1

    elif operation == "move":
        new_frame = params.get("new_frame")
        if new_frame is None:
            raise ValueError("new_frame is required for operation 'move'")
        new_frame = int(new_frame)
        for fc in fcurves:
            for kp in fc.keyframe_points:
                if int(kp.co[0]) == p["frame"]:
                    kp.co[0] = float(new_frame)
                    modified += 1

    elif operation == "set_interpolation":
        for fc in fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = p["interpolation"]
                modified += 1

    elif operation == "set_handle":
        for fc in fcurves:
            for kp in fc.keyframe_points:
                kp.handle_left_type = p["handle_type"]
                kp.handle_right_type = p["handle_type"]
                modified += 1

    elif operation == "scale_time":
        for fc in fcurves:
            # Find center frame for scaling
            frames = [kp.co[0] for kp in fc.keyframe_points]
            if not frames:
                continue
            center = frames[0]  # Scale relative to first keyframe
            for kp in fc.keyframe_points:
                old_frame = kp.co[0]
                kp.co[0] = center + (old_frame - center) * p["time_scale"]
                modified += 1

    elif operation == "smooth":
        for fc in fcurves:
            kps = list(fc.keyframe_points)
            if len(kps) < 3:
                continue
            # Simple 3-point moving average on values
            new_values = [kps[0].co[1]]
            for i in range(1, len(kps) - 1):
                avg = (kps[i - 1].co[1] + kps[i].co[1] + kps[i + 1].co[1]) / 3.0
                new_values.append(avg)
            new_values.append(kps[-1].co[1])
            for i, kp in enumerate(kps):
                kp.co[1] = new_values[i]
                modified += 1

    elif operation == "clean":
        for fc in fcurves:
            kf_data = [(kp.co[0], kp.co[1]) for kp in fc.keyframe_points]
            filtered = compute_noise_filter(kf_data, p["clean_threshold"])
            removed = len(kf_data) - len(filtered)
            modified += removed
            if removed > 0:
                filtered_frames = {f for f, _ in filtered}
                to_remove = [
                    kp for kp in fc.keyframe_points
                    if kp.co[0] not in filtered_frames
                ]
                for kp in reversed(to_remove):
                    fc.keyframe_points.remove(kp)

    elif operation == "sample":
        sample_rate = int(params.get("sample_rate", 1))
        for fc in fcurves:
            fr = get_frame_range(action, cb, layered)
            for frame in range(fr[0], fr[1] + 1, sample_rate):
                val = fc.evaluate(float(frame))
                fc.keyframe_points.insert(float(frame), val)
                modified += 1

    elif operation == "euler_filter":
        # Group fcurves by bone (rotation_euler x/y/z)
        bone_euler_fcs: dict[str, dict[int, object]] = {}
        for fc in fcurves:
            if "rotation_euler" in fc.data_path:
                bone_euler_fcs.setdefault(fc.data_path, {})[fc.array_index] = fc

        for dp, axis_fcs in bone_euler_fcs.items():
            if len(axis_fcs) < 3:
                continue
            # Read euler tuples per frame
            fc_x = axis_fcs.get(0)
            fc_y = axis_fcs.get(1)
            fc_z = axis_fcs.get(2)
            if not (fc_x and fc_y and fc_z):
                continue

            frames_set: set[float] = set()
            for fc in (fc_x, fc_y, fc_z):
                for kp in fc.keyframe_points:
                    frames_set.add(kp.co[0])
            frames_sorted = sorted(frames_set)

            eulers = []
            for f in frames_sorted:
                eulers.append((
                    fc_x.evaluate(f),
                    fc_y.evaluate(f),
                    fc_z.evaluate(f),
                ))

            filtered = compute_euler_filter(eulers)

            # Write back
            for i, f in enumerate(frames_sorted):
                for axis, fc in enumerate((fc_x, fc_y, fc_z)):
                    for kp in fc.keyframe_points:
                        if kp.co[0] == f:
                            kp.co[1] = filtered[i][axis]
                            modified += 1
                            break

    return {
        "status": "ok",
        "action_name": p["action_name"],
        "operation": operation,
        "modified_keyframes": modified,
        "fcurves_processed": len(fcurves),
    }


def handle_contact_solver(params: dict) -> dict:
    """Apply foot/hand contact stabilization to animation.

    For each frame, checks if contact bones are within threshold of the
    ground plane. During contact phases, locks bone position to the contact
    point. Smooths transitions at contact enter/exit with a 2-3 frame blend.
    """
    p = validate_contact_solver_params(params)
    armature_obj = _get_armature(p["armature_name"])

    action = bpy.data.actions.get(p["action_name"])
    if action is None:
        raise ValueError(f"Action not found: {p['action_name']!r}")

    cb, layered = setup_action_for_armature(action, armature_obj)

    # Determine frame range
    if p["frame_range"]:
        frame_start, frame_end = p["frame_range"]
    else:
        fr = get_frame_range(action, cb, layered)
        frame_start, frame_end = fr[0], fr[1]

    ground_height = p["ground_height"]
    threshold = p["contact_threshold"]
    BLEND_FRAMES = 3  # Frames to blend at contact transitions

    total_corrections = 0
    contact_phases_all: dict[str, list] = {}

    for bone_name in p["contact_bones"]:
        pb = armature_obj.pose.bones.get(bone_name)
        if pb is None:
            continue

        # Pass 1: Gather bone heights per frame
        bone_heights: list[tuple[int, float]] = []
        for frame in range(frame_start, frame_end + 1):
            bpy.context.scene.frame_set(frame)
            world_pos = armature_obj.matrix_world @ pb.matrix.translation
            bone_heights.append((frame, world_pos.z))

        # Detect contact phases
        phases = compute_contact_phases(bone_heights, ground_height, threshold)
        contact_phases_all[bone_name] = phases

        # Pass 2: Apply corrections
        # Build a height map for quick lookup
        height_map = {f: h for f, h in bone_heights}

        for phase_start, phase_end in phases:
            # Lock position: use the bone position at the moment of first contact
            bpy.context.scene.frame_set(phase_start)
            world_pos = armature_obj.matrix_world @ pb.matrix.translation
            lock_pos = world_pos.copy()
            lock_pos.z = ground_height

            if p["lock_rotation"]:
                lock_rot = pb.rotation_quaternion.copy()

            for frame in range(phase_start, phase_end + 1):
                bpy.context.scene.frame_set(frame)

                # Compute blend factor for smooth transitions
                blend = 1.0
                if frame - phase_start < BLEND_FRAMES:
                    blend = (frame - phase_start + 1) / BLEND_FRAMES
                if phase_end - frame < BLEND_FRAMES:
                    blend = min(blend, (phase_end - frame + 1) / BLEND_FRAMES)

                # Current world position
                current_world = armature_obj.matrix_world @ pb.matrix.translation

                # Target position (locked to ground)
                target = current_world.copy()
                target.z = ground_height + (current_world.z - ground_height) * (1.0 - blend)

                # Convert back to bone-local space
                inv_world = armature_obj.matrix_world.inverted()
                local_target = inv_world @ target

                # Apply correction to bone location
                if pb.parent:
                    parent_inv = pb.parent.matrix.inverted()
                    local_offset = parent_inv @ Matrix.Translation(
                        local_target - pb.matrix.translation
                    )
                    pb.location = pb.location + Vector(local_offset.translation)
                else:
                    delta = local_target - pb.matrix.translation
                    pb.location = pb.location + delta

                pb.keyframe_insert(data_path="location", frame=frame)
                total_corrections += 1

                if p["lock_rotation"]:
                    current_rot = pb.rotation_quaternion.copy()
                    pb.rotation_quaternion = current_rot.slerp(lock_rot, blend)
                    pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)

    return {
        "status": "ok",
        "action_name": p["action_name"],
        "frame_range": [frame_start, frame_end],
        "contact_bones": p["contact_bones"],
        "ground_height": ground_height,
        "total_corrections": total_corrections,
        "contact_phases": {
            bone: [(s, e) for s, e in phases]
            for bone, phases in contact_phases_all.items()
        },
    }
