"""Amorphous creature animation system for blob/ooze monsters.

Provides shape-key-based animations for creatures without rigid skeletons:
  - generate_blob_locomotion_keyframes: Body compression/expansion cycle
  - generate_pseudopod_reach_keyframes: Shape key limb protrusion
  - generate_blob_idle_keyframes: Subtle pulsing, surface ripple
  - generate_blob_attack_keyframes: Rapid pseudopod extension + retraction
  - generate_blob_split_keyframes: Scale down + duplicate visual

Uses shape keys extensively. Works with the amorphous rig template from T1.
For armature-based animations, uses DEF-spine chain for body deformation.

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_BLOB_TYPES: frozenset[str] = frozenset({
    "blob_locomotion", "pseudopod_reach", "blob_idle",
    "blob_attack", "blob_split",
})

# Shape key bone naming convention for amorphous rigs
# These use scale channels (not rotation) for deformation
BLOB_SPINE_BONES: list[str] = [
    "DEF-spine", "DEF-spine.001", "DEF-spine.002", "DEF-spine.003",
]

BLOB_PSEUDOPOD_BONES: list[str] = [
    "DEF-pseudopod_1", "DEF-pseudopod_2",
    "DEF-pseudopod_3", "DEF-pseudopod_4",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_blob_params(params: dict) -> dict:
    """Validate amorphous creature animation parameters.

    Args:
        params: Dict with object_name, blob_type, frame_count, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    blob_type = params.get("blob_type", "blob_idle")
    if blob_type not in VALID_BLOB_TYPES:
        raise ValueError(
            f"Invalid blob_type: {blob_type!r}. Valid: {sorted(VALID_BLOB_TYPES)}"
        )

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    direction = params.get("direction", "forward")
    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")

    return {
        "object_name": object_name,
        "blob_type": blob_type,
        "frame_count": frame_count,
        "direction": direction,
        "intensity": intensity,
    }


# ---------------------------------------------------------------------------
# Blob locomotion
# ---------------------------------------------------------------------------

def generate_blob_locomotion_keyframes(
    frame_count: int = 32,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate blob movement via compression/expansion cycle.

    The blob alternates between squishing down (compress X/Z, expand Y)
    and stretching forward (expand X/Z, compress Y). Uses scale channels
    on spine bones.

    Args:
        frame_count: Total frames.
        intensity: Scale of deformation.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi

        # Phase 1: Compress (squish down, spread out)
        # Phase 2: Extend (stretch forward, narrow)
        compress = math.sin(angle) * 0.15 * intensity

        for i, bone in enumerate(BLOB_SPINE_BONES):
            # Wave propagation along body
            phase_offset = i * math.pi / (len(BLOB_SPINE_BONES) - 1) if len(BLOB_SPINE_BONES) > 1 else 0.0

            # Vertical scale (Y): compress when moving, expand when planting
            y_scale = -compress * math.sin(angle + phase_offset)
            keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 + y_scale))

            # Lateral scale (X/Z): inverse of Y for volume preservation
            xz_scale = compress * 0.5 * math.sin(angle + phase_offset)
            keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + xz_scale))
            keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 + xz_scale))

            # Forward translation (actual movement)
            forward = 0.03 * intensity * math.sin(angle + phase_offset)
            keyframes.append(Keyframe(bone, "location", 1, frame, forward))

    return keyframes


# ---------------------------------------------------------------------------
# Pseudopod reach
# ---------------------------------------------------------------------------

def generate_pseudopod_reach_keyframes(
    direction: str = "forward",
    frame_count: int = 24,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate pseudopod extension toward a target direction.

    Extends a limb-like protrusion from the main body mass. Uses scale
    and location on pseudopod bones.

    Args:
        direction: "forward", "left", "right", "up".
        frame_count: Total frames.
        intensity: Reach distance multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    # Direction to axis mapping
    dir_map = {
        "forward": (1, 1.0),   # +Y
        "left": (0, -1.0),     # -X
        "right": (0, 1.0),     # +X
        "up": (2, 1.0),        # +Z
    }
    axis, sign = dir_map.get(direction, (1, 1.0))

    # Use first pseudopod bone for reach
    bone = BLOB_PSEUDOPOD_BONES[0] if BLOB_PSEUDOPOD_BONES else "DEF-spine.003"

    antic_end = int(0.2 * frame_count)
    active_end = int(0.5 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= antic_end:
            # Gather/coil
            reach_t = frame / antic_end if antic_end > 0 else 1.0
            reach = -0.02 * reach_t * intensity * sign
            scale = 1.0 + 0.1 * reach_t * intensity
        elif frame <= active_end:
            # Extend
            extend_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 1.0
            reach = (-0.02 + 0.15 * extend_t) * intensity * sign
            scale = 1.0 + 0.1 * intensity + 0.3 * extend_t * intensity
        else:
            # Retract
            retract_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
            reach = 0.13 * (1.0 - retract_t) * intensity * sign
            scale = (1.0 + 0.4 * intensity) * (1.0 - retract_t) + retract_t

        keyframes.append(Keyframe(bone, "location", axis, frame, reach))
        keyframes.append(Keyframe(bone, "scale", axis, frame, scale))

    # Body recoil (opposite direction)
    for frame in range(frame_count + 1):
        t = frame / frame_count
        recoil = -0.01 * intensity * sign * math.sin(t * math.pi)
        keyframes.append(Keyframe("DEF-spine", "location", axis, frame, recoil))

    return keyframes


# ---------------------------------------------------------------------------
# Blob idle
# ---------------------------------------------------------------------------

def generate_blob_idle_keyframes(
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate blob idle animation: subtle pulsing and surface ripple.

    Args:
        frame_count: Total frames.
        intensity: Pulse amplitude.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Breathing pulse (all spine bones scale uniformly)
        pulse = 0.03 * intensity * math.sin(t * 2 * math.pi)

        for i, bone in enumerate(BLOB_SPINE_BONES):
            phase = i * 0.3
            bone_pulse = pulse * math.sin(t * 2 * math.pi + phase)

            # Uniform breathing scale
            keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + bone_pulse))
            keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 - bone_pulse * 0.5))
            keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 + bone_pulse))

        # Surface ripple via subtle rotation
        for i, bone in enumerate(BLOB_SPINE_BONES):
            ripple_phase = i * math.pi / 2
            ripple = 0.02 * intensity * math.sin(t * 4 * math.pi + ripple_phase)
            keyframes.append(Keyframe(bone, "rotation_euler", 0, frame, ripple))

    return keyframes


# ---------------------------------------------------------------------------
# Blob attack
# ---------------------------------------------------------------------------

def generate_blob_attack_keyframes(
    frame_count: int = 16,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate rapid pseudopod extension + retraction attack.

    Args:
        frame_count: Total frames.
        intensity: Attack reach multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    antic_end = int(0.2 * frame_count)
    strike_end = int(0.4 * frame_count)

    bone = BLOB_PSEUDOPOD_BONES[0] if BLOB_PSEUDOPOD_BONES else "DEF-spine.003"

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= antic_end:
            # Coil back
            coil_t = frame / antic_end if antic_end > 0 else 1.0
            extend = -0.03 * coil_t * intensity
            scale_y = 1.0 + 0.2 * coil_t * intensity
        elif frame <= strike_end:
            # Rapid strike
            strike_t = (frame - antic_end) / (strike_end - antic_end) if strike_end > antic_end else 1.0
            extend = (-0.03 + 0.2 * strike_t) * intensity
            scale_y = 1.0 + 0.2 * intensity + 0.5 * strike_t * intensity
        else:
            # Retract
            retract_t = (frame - strike_end) / (frame_count - strike_end) if frame_count > strike_end else 1.0
            extend = 0.17 * (1.0 - retract_t) * intensity
            scale_y = (1.0 + 0.7 * intensity) * (1.0 - retract_t) + retract_t

        keyframes.append(Keyframe(bone, "location", 1, frame, extend))
        keyframes.append(Keyframe(bone, "scale", 1, frame, scale_y))

    # Body compression during strike
    for frame in range(frame_count + 1):
        t = frame / frame_count
        if t <= 0.4:
            compress = 0.05 * intensity * math.sin(t / 0.4 * math.pi)
        else:
            compress = 0.0
        keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, 1.0 - compress))
        keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, 1.0 + compress * 0.5))

    return keyframes


# ---------------------------------------------------------------------------
# Blob split
# ---------------------------------------------------------------------------

def generate_blob_split_keyframes(
    frame_count: int = 32,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate split animation: scale down and prepare for duplication.

    The actual duplication happens in-engine; this animation shows the
    visual buildup: wobble → stretch → pinch → separate.

    Args:
        frame_count: Total frames.
        intensity: Split deformation amount.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    wobble_end = int(0.3 * frame_count)
    stretch_end = int(0.6 * frame_count)
    pinch_end = int(0.8 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= wobble_end:
            # Wobble phase
            wobble_t = frame / wobble_end if wobble_end > 0 else 0.0
            wobble = 0.05 * intensity * math.sin(wobble_t * 6 * math.pi) * wobble_t
            for bone in BLOB_SPINE_BONES:
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + wobble))
                keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 - wobble))

        elif frame <= stretch_end:
            # Stretch laterally
            stretch_t = (frame - wobble_end) / (stretch_end - wobble_end) if stretch_end > wobble_end else 1.0
            for i, bone in enumerate(BLOB_SPINE_BONES):
                side = 1.0 if i < len(BLOB_SPINE_BONES) // 2 else -1.0
                stretch = 0.15 * intensity * stretch_t * side
                keyframes.append(Keyframe(bone, "location", 0, frame, stretch))
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + 0.1 * stretch_t))
                keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 - 0.05 * stretch_t))

        elif frame <= pinch_end:
            # Pinch at center
            pinch_t = (frame - stretch_end) / (pinch_end - stretch_end) if pinch_end > stretch_end else 1.0
            for i, bone in enumerate(BLOB_SPINE_BONES):
                mid = len(BLOB_SPINE_BONES) / 2
                dist_from_mid = abs(i - mid) / mid if mid > 0 else 0.0
                pinch = 0.2 * intensity * (1.0 - dist_from_mid) * pinch_t
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + 0.1 - pinch))
                keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 - pinch))

        else:
            # Separate: scale down to 0.7
            sep_t = (frame - pinch_end) / (frame_count - pinch_end) if frame_count > pinch_end else 1.0
            final_scale = 1.0 - 0.3 * sep_t
            for bone in BLOB_SPINE_BONES:
                keyframes.append(Keyframe(bone, "scale", 0, frame, final_scale))
                keyframes.append(Keyframe(bone, "scale", 1, frame, final_scale))
                keyframes.append(Keyframe(bone, "scale", 2, frame, final_scale))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def generate_blob_keyframes(params: dict) -> list[Keyframe]:
    """Dispatch to the appropriate blob animation generator.

    Args:
        params: Validated params dict.

    Returns:
        List of Keyframe namedtuples.
    """
    blob_type = params["blob_type"]
    fc = params["frame_count"]
    intensity = params.get("intensity", 1.0)

    if blob_type == "blob_locomotion":
        return generate_blob_locomotion_keyframes(fc, intensity)
    elif blob_type == "pseudopod_reach":
        return generate_pseudopod_reach_keyframes(params.get("direction", "forward"), fc, intensity)
    elif blob_type == "blob_idle":
        return generate_blob_idle_keyframes(fc, intensity)
    elif blob_type == "blob_attack":
        return generate_blob_attack_keyframes(fc, intensity)
    elif blob_type == "blob_split":
        return generate_blob_split_keyframes(fc, intensity)
    else:
        raise ValueError(f"Unknown blob_type: {blob_type!r}")
