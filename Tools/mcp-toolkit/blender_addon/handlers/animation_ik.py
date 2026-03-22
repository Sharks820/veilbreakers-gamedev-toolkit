"""IK foot placement ground-contact solver.

Post-processing function that bakes corrected keyframes for terrain adaptation:
  - Raycast downward from each foot bone per frame
  - Adjust foot bone position to terrain surface
  - Rotate foot to match terrain normal (ankle correction)
  - Adjust hip height based on lowest foot position
  - Supports flat ground, slopes, and discrete steps

This is NOT real-time IK — it bakes corrected keyframes into the action
for export to game engines. The runtime IK is handled by Unity's
Animation Rigging package.

Pure-logic module for the validation and keyframe math.
Blender-dependent handler uses bpy for raycasting.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Pure-logic validation (testable without Blender)
# ---------------------------------------------------------------------------

VALID_TERRAIN_TYPES: frozenset[str] = frozenset({
    "flat", "slope", "steps", "auto",
})

DEFAULT_FOOT_BONES: list[str] = ["DEF-foot.L", "DEF-foot.R"]
DEFAULT_HIP_BONE: str = "DEF-spine"
DEFAULT_RAYCAST_DISTANCE: float = 2.0
DEFAULT_GROUND_OFFSET: float = 0.0


def validate_ik_foot_params(params: dict) -> dict:
    """Validate IK foot placement parameters.

    Args:
        params: Dict with object_name, action_name, foot_bones, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    action_name = params.get("action_name")
    if not action_name:
        raise ValueError("action_name is required")

    foot_bones = params.get("foot_bones", DEFAULT_FOOT_BONES)
    if not isinstance(foot_bones, (list, tuple)) or not foot_bones:
        raise ValueError("foot_bones must be a non-empty list")

    hip_bone = params.get("hip_bone", DEFAULT_HIP_BONE)
    if not isinstance(hip_bone, str) or not hip_bone:
        raise ValueError("hip_bone must be a non-empty string")

    terrain_type = params.get("terrain_type", "auto")
    if terrain_type not in VALID_TERRAIN_TYPES:
        raise ValueError(
            f"Invalid terrain_type: {terrain_type!r}. Valid: {sorted(VALID_TERRAIN_TYPES)}"
        )

    raycast_distance = float(params.get("raycast_distance", DEFAULT_RAYCAST_DISTANCE))
    if raycast_distance <= 0:
        raise ValueError(f"raycast_distance must be > 0, got {raycast_distance}")

    ground_offset = float(params.get("ground_offset", DEFAULT_GROUND_OFFSET))

    frame_start = params.get("frame_start")
    frame_end = params.get("frame_end")

    return {
        "object_name": object_name,
        "action_name": action_name,
        "foot_bones": list(foot_bones),
        "hip_bone": hip_bone,
        "terrain_type": terrain_type,
        "raycast_distance": raycast_distance,
        "ground_offset": ground_offset,
        "frame_start": frame_start,
        "frame_end": frame_end,
    }


# ---------------------------------------------------------------------------
# Pure-logic foot correction math
# ---------------------------------------------------------------------------

def compute_foot_correction(
    foot_z: float,
    ground_z: float,
    ground_normal: tuple[float, float, float],
    ground_offset: float = 0.0,
) -> dict:
    """Compute foot position and rotation correction for ground contact.

    Args:
        foot_z: Current foot bone world Z position.
        ground_z: Ground surface Z at foot XY position.
        ground_normal: Ground surface normal (nx, ny, nz) at hit point.
        ground_offset: Additional offset above ground.

    Returns:
        Dict with z_correction (float), ankle_pitch (float),
        ankle_roll (float), is_grounded (bool).
    """
    # Z correction to place foot on ground
    target_z = ground_z + ground_offset
    z_correction = target_z - foot_z

    # Ankle rotation from ground normal
    # Normal (0,0,1) = flat ground = no rotation
    nx, ny, nz = ground_normal

    # Pitch (X rotation): from forward tilt of surface
    if abs(nz) > 0.01:
        ankle_pitch = math.atan2(ny, nz)
    else:
        ankle_pitch = 0.0

    # Roll (Y rotation): from lateral tilt of surface
    if abs(nz) > 0.01:
        ankle_roll = -math.atan2(nx, nz)
    else:
        ankle_roll = 0.0

    # Clamp corrections to reasonable ranges
    ankle_pitch = max(-0.5, min(0.5, ankle_pitch))
    ankle_roll = max(-0.3, min(0.3, ankle_roll))

    is_grounded = abs(z_correction) < 0.5  # reasonable threshold

    return {
        "z_correction": z_correction,
        "ankle_pitch": ankle_pitch,
        "ankle_roll": ankle_roll,
        "is_grounded": is_grounded,
    }


def compute_hip_correction(
    foot_corrections: list[dict],
) -> float:
    """Compute hip height adjustment based on foot corrections.

    Lowers the hip when feet need to reach further down (e.g., on a slope
    the downhill foot pulls the hip down).

    Args:
        foot_corrections: List of compute_foot_correction results.

    Returns:
        Hip Z correction (typically negative = lower).
    """
    if not foot_corrections:
        return 0.0

    # Use the most negative correction (lowest foot needs)
    min_correction = min(fc["z_correction"] for fc in foot_corrections)

    # Only adjust hip downward, not upward (prevents floating)
    if min_correction < 0:
        return min_correction * 0.8  # 80% transfer to hip
    return 0.0


def generate_ik_corrected_keyframes(
    foot_data: list[dict],
    hip_bone: str = "DEF-spine",
) -> list[Keyframe]:
    """Generate corrected keyframes from per-frame foot placement data.

    This is the pure-logic component. The Blender handler provides the
    per-frame raycast data, and this function produces the correction
    keyframes.

    Args:
        foot_data: List of per-frame dicts, each containing:
            - frame (int)
            - feet: list of dicts with bone_name, z_correction,
              ankle_pitch, ankle_roll
        hip_bone: Name of hip bone for height adjustment.

    Returns:
        List of Keyframe namedtuples with corrections.
    """
    keyframes: list[Keyframe] = []

    for frame_data in foot_data:
        frame = frame_data["frame"]
        feet = frame_data.get("feet", [])

        # Generate foot correction keyframes
        foot_corrections = []
        for foot in feet:
            bone_name = foot["bone_name"]
            z_corr = foot.get("z_correction", 0.0)
            pitch = foot.get("ankle_pitch", 0.0)
            roll = foot.get("ankle_roll", 0.0)

            # Z position correction
            keyframes.append(Keyframe(bone_name, "location", 2, frame, z_corr))

            # Ankle pitch (X rotation)
            if abs(pitch) > 0.001:
                keyframes.append(Keyframe(bone_name, "rotation_euler", 0, frame, pitch))

            # Ankle roll (Y rotation)
            if abs(roll) > 0.001:
                keyframes.append(Keyframe(bone_name, "rotation_euler", 1, frame, roll))

            foot_corrections.append({"z_correction": z_corr})

        # Hip height adjustment
        hip_corr = compute_hip_correction(foot_corrections)
        if abs(hip_corr) > 0.001:
            keyframes.append(Keyframe(hip_bone, "location", 2, frame, hip_corr))

    return keyframes


# ---------------------------------------------------------------------------
# Smoothing utilities
# ---------------------------------------------------------------------------

def smooth_corrections(
    keyframes: list[Keyframe],
    passes: int = 2,
) -> list[Keyframe]:
    """Smooth IK correction keyframes to prevent jitter.

    Applies weighted averaging to reduce frame-to-frame noise in the
    correction values while preserving contact events.

    Args:
        keyframes: List of correction Keyframes.
        passes: Number of smoothing passes.

    Returns:
        Smoothed list of Keyframes.
    """
    if len(keyframes) < 3 or passes < 1:
        return list(keyframes)

    # Group by (bone, channel, axis)
    groups: dict[tuple, list[Keyframe]] = {}
    for kf in keyframes:
        key = (kf.bone_name, kf.channel, kf.axis)
        groups.setdefault(key, []).append(kf)

    result: list[Keyframe] = []
    for key, kfs in groups.items():
        kfs_sorted = sorted(kfs, key=lambda k: k.frame)
        values = [kf.value for kf in kfs_sorted]

        for _ in range(passes):
            smoothed = list(values)
            for i in range(1, len(values) - 1):
                smoothed[i] = 0.25 * values[i - 1] + 0.5 * values[i] + 0.25 * values[i + 1]
            values = smoothed

        for kf, new_val in zip(kfs_sorted, values):
            result.append(Keyframe(kf.bone_name, kf.channel, kf.axis, kf.frame, new_val))

    return result
