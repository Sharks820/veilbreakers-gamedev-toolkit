"""Blender animation handlers that bridge pure-logic keyframes to Blender Actions.

Provides 9 command handlers:
  - handle_generate_walk: Walk/run cycle for any of 5 gait types (ANIM-01)
  - handle_generate_fly: Fly/hover with wing oscillation (ANIM-02)
  - handle_generate_idle: Breathing, weight shift, secondary motion (ANIM-03)
  - handle_generate_attack: 8 attack types with anticipation-strike-recovery (ANIM-04)
  - handle_generate_reaction: Death, directional hit, spawn (ANIM-05)
  - handle_generate_custom: Text-to-keyframe via verb/body-part parser (ANIM-06)
  - handle_add_animation_events: Add named event markers to action frames (AN-05)
  - handle_list_animation_events: List all event markers on an action (AN-05)
  - handle_remove_animation_event: Remove event marker by frame + type (AN-05)

Each handler validates inputs, calls the keyframe engine in animation_gaits.py,
applies results to a Blender Action with fcurves and optional CYCLES modifier,
and adds pose_markers at contact frames.

Pure-logic validation helpers (_validate_walk_params, _validate_fly_params, etc.)
are separated for testability without Blender.
"""

from __future__ import annotations

import bpy

from .animation_gaits import (
    ATTACK_CONFIGS,
    FLY_HOVER_CONFIG,
    IDLE_CONFIG,
    Keyframe,
    generate_attack_keyframes,
    generate_custom_keyframes,
    generate_cycle_keyframes,
    generate_reaction_keyframes,
    get_gait_config,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_GAITS: frozenset[str] = frozenset({
    "biped", "quadruped", "hexapod", "arachnid", "serpent", "bird", "floating",
})

VALID_SPEEDS: frozenset[str] = frozenset({"walk", "run", "trot", "canter", "gallop"})

VALID_ATTACK_TYPES: frozenset[str] = frozenset(ATTACK_CONFIGS.keys())

VALID_REACTION_TYPES: frozenset[str] = frozenset({"death", "hit", "spawn"})

VALID_HIT_DIRECTIONS: frozenset[str] = frozenset({
    "front", "back", "left", "right",
})

VALID_TANGENT_TYPES: frozenset[str] = frozenset({"AUTO_CLAMPED", "BEZIER", "LINEAR", "CONSTANT"})
DEFAULT_TANGENT_TYPE: str = "AUTO_CLAMPED"

VALID_EVENT_TYPES: frozenset[str] = frozenset({
    "SFX_footstep",
    "SFX_impact",
    "VFX_impact",
    "VFX_trail_start",
    "VFX_trail_end",
    "Hitbox_start",
    "Hitbox_end",
    "Camera_shake",
    "Sound_whoosh",
})


# ---------------------------------------------------------------------------
# Pure-logic validation helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_walk_params(params: dict) -> dict:
    """Validate and normalize walk cycle parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, gait, speed, frame_count.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    gait = params.get("gait", "biped")
    if gait not in VALID_GAITS:
        raise ValueError(
            f"Invalid gait: {gait!r}. Valid gaits: {sorted(VALID_GAITS)}"
        )

    speed = params.get("speed", "walk")
    if speed not in VALID_SPEEDS:
        raise ValueError(
            f"Invalid speed: {speed!r}. Valid speeds: {sorted(VALID_SPEEDS)}"
        )

    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    return {
        "object_name": object_name,
        "gait": gait,
        "speed": speed,
        "frame_count": frame_count,
    }


def _validate_fly_params(params: dict) -> dict:
    """Validate and normalize fly cycle parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, frequency, amplitude,
        glide_ratio, frame_count.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    frequency = float(params.get("frequency", 2.0))
    if frequency <= 0:
        raise ValueError(f"frequency must be > 0, got {frequency}")

    amplitude = float(params.get("amplitude", 0.8))
    if amplitude <= 0:
        raise ValueError(f"amplitude must be > 0, got {amplitude}")

    glide_ratio = float(params.get("glide_ratio", 0.3))
    if not (0.0 <= glide_ratio <= 1.0):
        raise ValueError(
            f"glide_ratio must be between 0.0 and 1.0, got {glide_ratio}"
        )

    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    return {
        "object_name": object_name,
        "frequency": frequency,
        "amplitude": amplitude,
        "glide_ratio": glide_ratio,
        "frame_count": frame_count,
    }


def _validate_idle_params(params: dict) -> dict:
    """Validate and normalize idle animation parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, frame_count, breathing_intensity.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    breathing_intensity = float(params.get("breathing_intensity", 1.0))
    if breathing_intensity <= 0:
        raise ValueError(
            f"breathing_intensity must be > 0, got {breathing_intensity}"
        )

    return {
        "object_name": object_name,
        "frame_count": frame_count,
        "breathing_intensity": breathing_intensity,
    }


def _validate_attack_params(params: dict) -> dict:
    """Validate and normalize attack animation parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, attack_type, frame_count, intensity.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    attack_type = params.get("attack_type")
    if not attack_type:
        raise ValueError("attack_type is required")
    if attack_type not in VALID_ATTACK_TYPES:
        raise ValueError(
            f"Invalid attack_type: {attack_type!r}. "
            f"Valid types: {sorted(VALID_ATTACK_TYPES)}"
        )

    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    intensity = float(params.get("intensity", 1.0))
    if not (0.1 <= intensity <= 5.0):
        raise ValueError(
            f"intensity must be between 0.1 and 5.0, got {intensity}"
        )

    return {
        "object_name": object_name,
        "attack_type": attack_type,
        "frame_count": frame_count,
        "intensity": intensity,
    }


def _validate_reaction_params(params: dict) -> dict:
    """Validate and normalize reaction animation parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, reaction_type, direction, frame_count.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    reaction_type = params.get("reaction_type")
    if not reaction_type:
        raise ValueError("reaction_type is required")
    if reaction_type not in VALID_REACTION_TYPES:
        raise ValueError(
            f"Invalid reaction_type: {reaction_type!r}. "
            f"Valid types: {sorted(VALID_REACTION_TYPES)}"
        )

    direction = params.get("direction", "front")
    if reaction_type == "hit" and direction not in VALID_HIT_DIRECTIONS:
        raise ValueError(
            f"Invalid direction: {direction!r} for hit reaction. "
            f"Valid directions: {sorted(VALID_HIT_DIRECTIONS)}"
        )

    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    return {
        "object_name": object_name,
        "reaction_type": reaction_type,
        "direction": direction,
        "frame_count": frame_count,
    }


def _validate_custom_params(params: dict) -> dict:
    """Validate and normalize custom animation parameters.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, description, frame_count.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    description = params.get("description")
    if not description or not isinstance(description, str) or not description.strip():
        raise ValueError("description is required and must be a non-empty string")

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    return {
        "object_name": object_name,
        "description": description.strip(),
        "frame_count": frame_count,
    }


# ---------------------------------------------------------------------------
# Blender-dependent helpers
# ---------------------------------------------------------------------------


def _validate_animation_params(params: dict) -> tuple:
    """Validate that object_name points to a valid armature with pose bones.

    Args:
        params: Handler params dict (must have "object_name").

    Returns:
        Tuple of (armature_obj, object_name).

    Raises:
        ValueError: If object not found, not an armature, or has no pose bones.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    armature_obj = bpy.data.objects.get(object_name)
    if armature_obj is None:
        raise ValueError(f"Object not found: {object_name!r}")
    if armature_obj.type != "ARMATURE":
        raise ValueError(
            f"Object {object_name!r} is type {armature_obj.type!r}, "
            f"expected ARMATURE"
        )
    if not armature_obj.pose or not armature_obj.pose.bones:
        raise ValueError(
            f"Armature {object_name!r} has no pose bones"
        )

    return armature_obj, object_name


def _get_armature_def_bones(armature_obj) -> list[str]:
    """Return sorted list of DEF-prefixed bone names from the armature.

    Args:
        armature_obj: A Blender armature object.

    Returns:
        Sorted list of bone names starting with "DEF-".
    """
    return sorted(
        bone.name for bone in armature_obj.pose.bones
        if bone.name.startswith("DEF-")
    )


def _resolve_bone_name(armature_obj, bone_name: str) -> str:
    """Resolve a bone name, trying with and without DEF- prefix.

    Args:
        armature_obj: A Blender armature object.
        bone_name: The bone name to resolve.

    Returns:
        The resolved bone name that exists on the armature.

    Raises:
        ValueError: If bone cannot be found.
    """
    pose_bones = armature_obj.pose.bones

    # Try exact match first
    if bone_name in pose_bones:
        return bone_name

    # Try adding DEF- prefix
    if not bone_name.startswith("DEF-"):
        def_name = f"DEF-{bone_name}"
        if def_name in pose_bones:
            return def_name

    # Try removing DEF- prefix
    if bone_name.startswith("DEF-"):
        base_name = bone_name[4:]
        if base_name in pose_bones:
            return base_name

    raise ValueError(
        f"Bone {bone_name!r} not found on armature {armature_obj.name!r}"
    )


def _apply_keyframes_to_action(
    armature_obj,
    action_name: str,
    keyframes: list[Keyframe],
    use_cyclic: bool = True,
    tangent_type: str = "AUTO_CLAMPED",
) -> dict:
    """Create a Blender Action from keyframe data and assign to armature.

    Args:
        armature_obj: The Blender armature object.
        action_name: Name for the new Action.
        keyframes: List of Keyframe namedtuples from the engine.
        use_cyclic: If True, add CYCLES modifier to each fcurve for looping.
        tangent_type: Interpolation tangent type. One of AUTO_CLAMPED, BEZIER,
            LINEAR, CONSTANT. Defaults to AUTO_CLAMPED.

    Returns:
        Dict with action_name, fcurve_count, frame_range, tangent_type.
    """
    # Validate tangent_type
    if tangent_type not in VALID_TANGENT_TYPES:
        tangent_type = DEFAULT_TANGENT_TYPE

    from ._action_compat import (
        setup_action_for_armature, new_fcurve,
        get_frame_range, get_fcurve_count,
    )

    # Create action
    action = bpy.data.actions.new(name=action_name)
    action.use_fake_user = True

    # Ensure animation data exists
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Set up for Blender 5.0+ layered API or legacy
    _channelbag, _is_layered = setup_action_for_armature(action, armature_obj)

    # Group keyframes by (bone, channel, axis) for fcurve creation
    fcurve_map: dict[tuple[str, str, int], list[tuple[int, float]]] = {}
    for kf in keyframes:
        key = (kf.bone_name, kf.channel, kf.axis)
        fcurve_map.setdefault(key, []).append((kf.frame, kf.value))

    # Map tangent_type to Blender interpolation
    if tangent_type in ("AUTO_CLAMPED", "BEZIER"):
        interpolation = "BEZIER"
    elif tangent_type == "LINEAR":
        interpolation = "LINEAR"
    else:  # CONSTANT
        interpolation = "CONSTANT"

    # Create fcurves and bulk-insert keyframes
    for (bone_name, channel, axis), frames in fcurve_map.items():
        # Check rotation mode for this bone if channel is rotation-related
        resolved_channel = channel
        if channel == "rotation_euler" and bone_name in armature_obj.pose.bones:
            pbone = armature_obj.pose.bones[bone_name]
            if hasattr(pbone, "rotation_mode") and pbone.rotation_mode == "QUATERNION":
                resolved_channel = "rotation_quaternion"
                # Map euler axis (0-2) to quaternion axis (1-3, since 0=W)
                axis = axis + 1

        data_path = f'pose.bones["{bone_name}"].{resolved_channel}'
        fc = new_fcurve(action, data_path, axis, _channelbag, _is_layered)
        fc.keyframe_points.add(count=len(frames))
        for i, (frame, value) in enumerate(frames):
            fc.keyframe_points[i].co = (frame, value)
            fc.keyframe_points[i].interpolation = interpolation
            if tangent_type == "AUTO_CLAMPED":
                fc.keyframe_points[i].handle_left_type = "AUTO_CLAMPED"
                fc.keyframe_points[i].handle_right_type = "AUTO_CLAMPED"
            elif tangent_type == "BEZIER":
                fc.keyframe_points[i].handle_left_type = "AUTO"
                fc.keyframe_points[i].handle_right_type = "AUTO"

        # Add cycles modifier for seamless looping
        if use_cyclic:
            fc.modifiers.new(type="CYCLES")

    frame_range = get_frame_range(action, _channelbag, _is_layered)
    fcurve_count = get_fcurve_count(action, _channelbag, _is_layered)

    return {
        "action_name": action.name,
        "fcurve_count": fcurve_count,
        "frame_range": frame_range,
        "tangent_type": tangent_type,
    }


def _add_contact_markers(action, contact_frames: list[int]) -> None:
    """Add pose_markers to an action at each contact frame.

    Args:
        action: A Blender Action.
        contact_frames: List of frame numbers to mark.
    """
    for i, frame in enumerate(contact_frames):
        marker = action.pose_markers.new(f"contact_{i}")
        marker.frame = frame


# ---------------------------------------------------------------------------
# Handler: Walk/Run Cycle (ANIM-01)
# ---------------------------------------------------------------------------


def handle_generate_walk(params: dict) -> dict:
    """Generate procedural walk/run cycle for any gait type.

    Params:
        object_name: Name of the armature object.
        gait: Gait type (default "biped"). One of: biped, quadruped,
            hexapod, arachnid, serpent.
        speed: "walk" or "run" (default "walk").
        frame_count: Frames per cycle (default 24).

    Returns:
        Dict with action_name, gait, speed, frame_count, fcurve_count,
        contact_frames.
    """
    validated = _validate_walk_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    gait = validated["gait"]
    speed = validated["speed"]
    frame_count = validated["frame_count"]

    # Get DEF bone names from armature for bone filtering
    def_bones = _get_armature_def_bones(armature_obj)

    # Get gait config and generate keyframes
    config = get_gait_config(gait, speed, frame_count, bone_names=def_bones or None)
    keyframes = generate_cycle_keyframes(config)

    # Apply to Blender Action
    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_{gait}_{speed}"
    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=True,
        tangent_type=tangent_type,
    )

    # Compute contact frames (foot plants at phase extremes)
    # For most gaits, contacts occur at 0 and half the cycle
    contact_frames = [0, frame_count // 2]
    if gait == "hexapod":
        # Alternating tripod has 3 contacts per cycle
        contact_frames = [0, frame_count // 3, 2 * frame_count // 3]
    elif gait == "arachnid":
        # 4-4 alternating
        contact_frames = [0, frame_count // 4, frame_count // 2, 3 * frame_count // 4]

    # Add contact markers to Action
    action = bpy.data.actions.get(result["action_name"])
    if action:
        _add_contact_markers(action, contact_frames)

    return {
        "action_name": result["action_name"],
        "gait": gait,
        "speed": speed,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
        "contact_frames": contact_frames,
    }


# ---------------------------------------------------------------------------
# Handler: Fly/Hover Cycle (ANIM-02)
# ---------------------------------------------------------------------------


def handle_generate_fly(params: dict) -> dict:
    """Generate procedural fly/hover cycle with wing oscillation.

    Params:
        object_name: Name of the armature object.
        frequency: Wing beat frequency multiplier (default 2.0).
        amplitude: Wing oscillation amplitude multiplier (default 0.8).
        glide_ratio: Ratio of glide to flap (0.0-1.0, default 0.3).
        frame_count: Frames per cycle (default 24).

    Returns:
        Dict with action_name, frequency, amplitude, glide_ratio,
        frame_count, fcurve_count.
    """
    validated = _validate_fly_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    frequency = validated["frequency"]
    amplitude = validated["amplitude"]
    glide_ratio = validated["glide_ratio"]
    frame_count = validated["frame_count"]

    # Get fly config and apply param overrides
    config = get_gait_config("biped", "fly", frame_count)
    config["frequency"] = frequency
    config["glide_ratio"] = glide_ratio

    # Scale bone amplitudes by user amplitude relative to default
    default_amp = FLY_HOVER_CONFIG["bones"]["DEF-wing_upper.L"]["amplitude"]
    amp_scale = amplitude / default_amp if default_amp > 0 else 1.0
    for bone_cfg in config["bones"].values():
        bone_cfg["amplitude"] *= amp_scale

    # Apply glide ratio -- reduce amplitude during glide portion
    # This effectively dampens the oscillation by (1 - glide_ratio)
    glide_dampen = 1.0 - glide_ratio
    for bone_cfg in config["bones"].values():
        bone_cfg["amplitude"] *= glide_dampen

    # Filter config to bones present on this armature (RIG-004)
    def_bones = _get_armature_def_bones(armature_obj)
    if def_bones:
        config["bones"] = {
            k: v for k, v in config["bones"].items()
            if k.split("__")[0] in def_bones
        }

    keyframes = generate_cycle_keyframes(config)

    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_fly_hover"
    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=True,
        tangent_type=tangent_type,
    )

    # Wing beat contacts at top and bottom of stroke
    contact_frames = [0, frame_count // 2]
    action = bpy.data.actions.get(result["action_name"])
    if action:
        _add_contact_markers(action, contact_frames)

    return {
        "action_name": result["action_name"],
        "frequency": frequency,
        "amplitude": amplitude,
        "glide_ratio": glide_ratio,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
    }


# ---------------------------------------------------------------------------
# Handler: Idle Animation (ANIM-03)
# ---------------------------------------------------------------------------


def handle_generate_idle(params: dict) -> dict:
    """Generate procedural idle animation with breathing and weight shift.

    Params:
        object_name: Name of the armature object.
        frame_count: Frames per cycle (default 48).
        breathing_intensity: Multiplier for breathing amplitude (default 1.0).

    Returns:
        Dict with action_name, frame_count, fcurve_count.
    """
    validated = _validate_idle_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    frame_count = validated["frame_count"]
    breathing_intensity = validated["breathing_intensity"]

    # Get idle config and scale amplitudes by breathing intensity
    config = get_gait_config("biped", "idle", frame_count)
    for bone_cfg in config["bones"].values():
        bone_cfg["amplitude"] *= breathing_intensity

    # Filter config to bones present on this armature (RIG-004)
    def_bones = _get_armature_def_bones(armature_obj)
    if def_bones:
        config["bones"] = {
            k: v for k, v in config["bones"].items()
            if k.split("__")[0] in def_bones
        }

    keyframes = generate_cycle_keyframes(config)

    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_idle"
    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=True,
        tangent_type=tangent_type,
    )

    return {
        "action_name": result["action_name"],
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
    }


# ---------------------------------------------------------------------------
# Handler: Attack Animation (ANIM-04)
# ---------------------------------------------------------------------------


def handle_generate_attack(params: dict) -> dict:
    """Generate attack animation with anticipation-strike-recovery phases.

    Params:
        object_name: Name of the armature object.
        attack_type: One of: melee_swing, thrust, slam, bite, claw,
            tail_whip, wing_buffet, breath_attack.
        frame_count: Total frames (default 24).
        intensity: Value multiplier (default 1.0, range 0.1-5.0).

    Returns:
        Dict with action_name, attack_type, intensity, frame_count,
        fcurve_count, phases.
    """
    validated = _validate_attack_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    attack_type = validated["attack_type"]
    frame_count = validated["frame_count"]
    intensity = validated["intensity"]

    # Filter keyframes to bones present on this armature (RIG-002/RIG-004)
    def_bones = _get_armature_def_bones(armature_obj)
    keyframes = generate_attack_keyframes(
        attack_type, frame_count, intensity,
        bone_names=def_bones or None,
    )

    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_attack_{attack_type}"
    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=False,
        tangent_type=tangent_type,
    )

    # Compute phase frame ranges from standard percentages
    anticipation_end = int(round(0.2 * frame_count))
    strike_end = int(round(0.5 * frame_count))
    phases = {
        "anticipation": {"start": 0, "end": anticipation_end},
        "strike": {"start": anticipation_end, "end": strike_end},
        "recovery": {"start": strike_end, "end": frame_count},
    }

    # Add contact marker at strike frame (end of anticipation = impact moment)
    action = bpy.data.actions.get(result["action_name"])
    if action:
        _add_contact_markers(action, [anticipation_end])

    return {
        "action_name": result["action_name"],
        "attack_type": attack_type,
        "intensity": intensity,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
        "phases": phases,
    }


# ---------------------------------------------------------------------------
# Handler: Reaction Animation (ANIM-05)
# ---------------------------------------------------------------------------


def handle_generate_reaction(params: dict) -> dict:
    """Generate reaction animation (death, hit, spawn).

    Params:
        object_name: Name of the armature object.
        reaction_type: One of: death, hit, spawn.
        direction: For hit reactions: front, back, left, right (default "front").
        frame_count: Total frames (default 24).

    Returns:
        Dict with action_name, reaction_type, direction, frame_count,
        fcurve_count.
    """
    validated = _validate_reaction_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    reaction_type = validated["reaction_type"]
    direction = validated["direction"]
    frame_count = validated["frame_count"]

    # Filter keyframes to bones present on this armature (RIG-004)
    def_bones = _get_armature_def_bones(armature_obj)
    keyframes = generate_reaction_keyframes(
        reaction_type, direction=direction, frame_count=frame_count,
        bone_names=def_bones or None,
    )

    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_{reaction_type}"
    if reaction_type == "hit":
        action_name = f"{object_name}_hit_{direction}"

    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=False,
        tangent_type=tangent_type,
    )

    # Add contact marker at impact frame for hit reactions (20% mark)
    if reaction_type == "hit":
        impact_frame = int(round(0.2 * frame_count))
        action = bpy.data.actions.get(result["action_name"])
        if action:
            _add_contact_markers(action, [impact_frame])

    return {
        "action_name": result["action_name"],
        "reaction_type": reaction_type,
        "direction": direction,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
    }


# ---------------------------------------------------------------------------
# Handler: Custom Animation (ANIM-06)
# ---------------------------------------------------------------------------


def handle_generate_custom(params: dict) -> dict:
    """Generate animation from text description via verb/body-part parser.

    Params:
        object_name: Name of the armature object.
        description: Natural language description (e.g. "raise wings then
            swing arms").
        frame_count: Total frames (default 48).

    Returns:
        Dict with action_name, description, frame_count, fcurve_count,
        parsed_actions.
    """
    validated = _validate_custom_params(params)
    armature_obj, object_name = _validate_animation_params(validated)

    description = validated["description"]
    frame_count = validated["frame_count"]

    keyframes = generate_custom_keyframes(description, frame_count)

    # Filter keyframes to bones present on this armature (RIG-004)
    def_bones_set = set(_get_armature_def_bones(armature_obj))
    if def_bones_set:
        keyframes = [kf for kf in keyframes if kf.bone_name in def_bones_set]

    tangent_type = params.get("tangent_type", DEFAULT_TANGENT_TYPE)
    action_name = f"{object_name}_custom"
    result = _apply_keyframes_to_action(
        armature_obj, action_name, keyframes, use_cyclic=False,
        tangent_type=tangent_type,
    )

    # Extract parsed actions from the keyframes for reporting
    # Group by unique (bone, channel) combos to identify what was parsed
    parsed_bones: set[str] = set()
    for kf in keyframes:
        parsed_bones.add(kf.bone_name)

    return {
        "action_name": result["action_name"],
        "description": description,
        "frame_count": frame_count,
        "fcurve_count": result["fcurve_count"],
        "parsed_actions": sorted(parsed_bones),
    }


# ---------------------------------------------------------------------------
# Pure-logic validation: Animation Events (AN-05)
# ---------------------------------------------------------------------------


def _validate_event_entry(entry: dict, index: int) -> dict:
    """Validate a single animation event entry.

    Args:
        entry: Dict with frame, event_type, event_name, data.
        index: Position in events list (for error messages).

    Returns:
        Normalized dict.

    Raises:
        ValueError: On missing/invalid fields.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"events[{index}] must be a dict, got {type(entry).__name__}")

    frame = entry.get("frame")
    if frame is None:
        raise ValueError(f"events[{index}].frame is required")
    frame = int(frame)
    if frame < 0:
        raise ValueError(f"events[{index}].frame must be >= 0, got {frame}")

    event_type = entry.get("event_type")
    if not event_type:
        raise ValueError(f"events[{index}].event_type is required")
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"events[{index}].event_type {event_type!r} invalid. "
            f"Valid types: {sorted(VALID_EVENT_TYPES)}"
        )

    event_name = entry.get("event_name", "")
    data = entry.get("data", "")

    return {
        "frame": frame,
        "event_type": event_type,
        "event_name": str(event_name),
        "data": str(data),
    }


def _validate_add_events_params(params: dict) -> dict:
    """Validate parameters for handle_add_animation_events.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, action_name, events.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    action_name = params.get("action_name")
    if not action_name:
        raise ValueError("action_name is required")

    events = params.get("events")
    if not events or not isinstance(events, list):
        raise ValueError("events must be a non-empty list")

    validated_events = [
        _validate_event_entry(e, i) for i, e in enumerate(events)
    ]

    return {
        "object_name": object_name,
        "action_name": action_name,
        "events": validated_events,
    }


def _validate_list_events_params(params: dict) -> dict:
    """Validate parameters for handle_list_animation_events.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, action_name.

    Raises:
        ValueError: On missing parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    action_name = params.get("action_name")
    if not action_name:
        raise ValueError("action_name is required")

    return {
        "object_name": object_name,
        "action_name": action_name,
    }


def _validate_remove_event_params(params: dict) -> dict:
    """Validate parameters for handle_remove_animation_event.

    Args:
        params: Handler params dict.

    Returns:
        Normalized dict with object_name, action_name, frame, event_type.

    Raises:
        ValueError: On missing/invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    action_name = params.get("action_name")
    if not action_name:
        raise ValueError("action_name is required")

    frame = params.get("frame")
    if frame is None:
        raise ValueError("frame is required")
    frame = int(frame)
    if frame < 0:
        raise ValueError(f"frame must be >= 0, got {frame}")

    event_type = params.get("event_type")
    if not event_type:
        raise ValueError("event_type is required")
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"event_type {event_type!r} invalid. "
            f"Valid types: {sorted(VALID_EVENT_TYPES)}"
        )

    return {
        "object_name": object_name,
        "action_name": action_name,
        "frame": frame,
        "event_type": event_type,
    }


# ---------------------------------------------------------------------------
# Handler: Add Animation Events (AN-05)
# ---------------------------------------------------------------------------


def handle_add_animation_events(params: dict) -> dict:
    """Add named event markers to animation frames for SFX/VFX/hitbox timing.

    Stores events as pose_markers on the action. Each marker's name is set
    to the event_type, and event_name/data are stored as custom properties
    on the action keyed by ``event_{frame}_{event_type}``.

    Params:
        object_name: Target armature name.
        action_name: Animation action to mark.
        events: List of dicts with {frame, event_type, event_name, data}.

    Returns:
        Dict with action_name, added_events list.
    """
    validated = _validate_add_events_params(params)
    _validate_animation_params(validated)  # ensure armature exists

    action_name = validated["action_name"]
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action not found: {action_name!r}")

    added: list[dict] = []
    for evt in validated["events"]:
        marker = action.pose_markers.new(evt["event_type"])
        marker.frame = evt["frame"]

        # Store event_name and data as custom properties on the action
        prop_key = f"event_{evt['frame']}_{evt['event_type']}"
        action[prop_key] = f"{evt['event_name']}|{evt['data']}"

        added.append({
            "frame": evt["frame"],
            "event_type": evt["event_type"],
            "event_name": evt["event_name"],
            "data": evt["data"],
        })

    return {
        "action_name": action_name,
        "added_events": added,
        "total_markers": len(action.pose_markers),
    }


# ---------------------------------------------------------------------------
# Handler: List Animation Events (AN-05)
# ---------------------------------------------------------------------------


def handle_list_animation_events(params: dict) -> dict:
    """List all event markers on an animation action.

    Params:
        object_name: Target armature name.
        action_name: Animation action to query.

    Returns:
        Dict with action_name and events list.
    """
    validated = _validate_list_events_params(params)
    _validate_animation_params(validated)  # ensure armature exists

    action_name = validated["action_name"]
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action not found: {action_name!r}")

    events: list[dict] = []
    for marker in action.pose_markers:
        event_type = marker.name
        frame = marker.frame

        # Retrieve custom property data if stored
        prop_key = f"event_{frame}_{event_type}"
        event_name = ""
        data = ""
        if prop_key in action:
            stored = str(action[prop_key])
            parts = stored.split("|", 1)
            event_name = parts[0]
            data = parts[1] if len(parts) > 1 else ""

        events.append({
            "frame": frame,
            "event_type": event_type,
            "event_name": event_name,
            "data": data,
        })

    # Sort by frame
    events.sort(key=lambda e: e["frame"])

    return {
        "action_name": action_name,
        "events": events,
        "total_markers": len(action.pose_markers),
    }


# ---------------------------------------------------------------------------
# Handler: Remove Animation Event (AN-05)
# ---------------------------------------------------------------------------


def handle_remove_animation_event(params: dict) -> dict:
    """Remove an event marker by frame and event_type.

    Params:
        object_name: Target armature name.
        action_name: Animation action to modify.
        frame: Frame number of the event to remove.
        event_type: Event type string to match.

    Returns:
        Dict with action_name, removed flag, frame, event_type.
    """
    validated = _validate_remove_event_params(params)
    _validate_animation_params(validated)  # ensure armature exists

    action_name = validated["action_name"]
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise ValueError(f"Action not found: {action_name!r}")

    target_frame = validated["frame"]
    target_type = validated["event_type"]

    removed = False
    for i, marker in enumerate(action.pose_markers):
        if marker.frame == target_frame and marker.name == target_type:
            action.pose_markers.remove(marker)
            # Also clean up custom property
            prop_key = f"event_{target_frame}_{target_type}"
            if prop_key in action:
                del action[prop_key]
            removed = True
            break

    return {
        "action_name": action_name,
        "removed": removed,
        "frame": target_frame,
        "event_type": target_type,
        "remaining_markers": len(action.pose_markers),
    }
