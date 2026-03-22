"""Advanced rigging handlers for facial rigs, IK chains, spring bones, ragdoll,
retargeting, and shape keys.

Provides six command handlers:
  - handle_setup_facial: Bone-based facial rig with monster expression presets (RIG-04)
  - handle_setup_ik: Standard 2-bone and spline IK chain setup (RIG-05)
  - handle_setup_spring_bones: Secondary motion constraints for tails/hair/capes (RIG-06)
  - handle_setup_ragdoll: Auto-generate colliders and joint constraints (RIG-11)
  - handle_retarget_rig: Constraint-based bone mapping between rigs (RIG-12)
  - handle_add_shape_keys: Expression and damage state mesh deformations (RIG-13)

Pure-logic validation functions:
  - _validate_psd_config: Validate pose-space deformation configuration
  - _validate_ik_params: Validate IK chain setup parameters
  - _validate_spring_params: Validate spring bone dynamics parameters
  - _validate_ragdoll_spec: Validate ragdoll collider/joint specification
  - _validate_retarget_mapping: Validate bone retarget mapping between rigs
  - _validate_shape_key_params: Validate shape key name and vertex offsets
  - _compute_spring_chain_forces: Spring-mass chain simulation (returns positions + velocities)
  - _validate_spring_dynamics_params: Validate spring dynamics mass/stiffness/damping
  - _validate_facial_rig_params: Validate facial rig setup parameters
  - _validate_corrective_shape_config: Validate corrective blend shape configuration
"""

from __future__ import annotations

import math
import re

import bpy
from mathutils import Euler, Vector

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Facial bone definitions (bone-based facial rig layout)
# ---------------------------------------------------------------------------
# Each entry has head, tail, roll, parent keys -- same format as template bone
# dicts. Parent "head" references the head bone of the existing rig.

FACIAL_BONES: dict[str, dict] = {
    "jaw": {
        "head": (0.0, -0.02, 1.6),
        "tail": (0.0, -0.08, 1.55),
        "roll": 0.0,
        "parent": "head",
    },
    "lip_upper": {
        "head": (0.0, -0.07, 1.58),
        "tail": (0.0, -0.09, 1.58),
        "roll": 0.0,
        "parent": "head",
    },
    "lip_lower": {
        "head": (0.0, -0.07, 1.56),
        "tail": (0.0, -0.09, 1.56),
        "roll": 0.0,
        "parent": "jaw",
    },
    "lip_corner.L": {
        "head": (0.025, -0.065, 1.57),
        "tail": (0.03, -0.075, 1.57),
        "roll": 0.0,
        "parent": "head",
    },
    "lip_corner.R": {
        "head": (-0.025, -0.065, 1.57),
        "tail": (-0.03, -0.075, 1.57),
        "roll": 0.0,
        "parent": "head",
    },
    "eyelid_upper.L": {
        "head": (0.03, -0.06, 1.65),
        "tail": (0.03, -0.07, 1.66),
        "roll": 0.0,
        "parent": "head",
    },
    "eyelid_upper.R": {
        "head": (-0.03, -0.06, 1.65),
        "tail": (-0.03, -0.07, 1.66),
        "roll": 0.0,
        "parent": "head",
    },
    "eyelid_lower.L": {
        "head": (0.03, -0.06, 1.63),
        "tail": (0.03, -0.07, 1.62),
        "roll": 0.0,
        "parent": "head",
    },
    "eyelid_lower.R": {
        "head": (-0.03, -0.06, 1.63),
        "tail": (-0.03, -0.07, 1.62),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_inner.L": {
        "head": (0.015, -0.06, 1.67),
        "tail": (0.015, -0.07, 1.68),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_inner.R": {
        "head": (-0.015, -0.06, 1.67),
        "tail": (-0.015, -0.07, 1.68),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_mid.L": {
        "head": (0.03, -0.058, 1.675),
        "tail": (0.03, -0.068, 1.685),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_mid.R": {
        "head": (-0.03, -0.058, 1.675),
        "tail": (-0.03, -0.068, 1.685),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_outer.L": {
        "head": (0.045, -0.055, 1.67),
        "tail": (0.045, -0.065, 1.68),
        "roll": 0.0,
        "parent": "head",
    },
    "brow_outer.R": {
        "head": (-0.045, -0.055, 1.67),
        "tail": (-0.045, -0.065, 1.68),
        "roll": 0.0,
        "parent": "head",
    },
    "cheek.L": {
        "head": (0.04, -0.05, 1.60),
        "tail": (0.05, -0.06, 1.60),
        "roll": 0.0,
        "parent": "head",
    },
    "cheek.R": {
        "head": (-0.04, -0.05, 1.60),
        "tail": (-0.05, -0.06, 1.60),
        "roll": 0.0,
        "parent": "head",
    },
    "nose": {
        "head": (0.0, -0.07, 1.62),
        "tail": (0.0, -0.085, 1.62),
        "roll": 0.0,
        "parent": "head",
    },
    # Eye tracking bones
    "eye.L": {
        "head": (0.03, -0.06, 1.64),
        "tail": (0.03, -0.08, 1.64),
        "roll": 0.0,
        "parent": "head",
    },
    "eye.R": {
        "head": (-0.03, -0.06, 1.64),
        "tail": (-0.03, -0.08, 1.64),
        "roll": 0.0,
        "parent": "head",
    },
    "eye_target": {
        "head": (0.0, -0.5, 1.64),
        "tail": (0.0, -0.6, 1.64),
        "roll": 0.0,
        "parent": "head",
    },
}


# ---------------------------------------------------------------------------
# FACS Action Units (P2-A7)
# ---------------------------------------------------------------------------

FACS_ACTION_UNITS: dict[str, dict] = {
    "AU01": {"name": "Inner Brow Raise", "bones": ["brow_inner.L", "brow_inner.R"]},
    "AU02": {"name": "Outer Brow Raise", "bones": ["brow_outer.L", "brow_outer.R"]},
    "AU04": {"name": "Brow Lowerer", "bones": ["brow_inner.L", "brow_inner.R", "brow_mid.L", "brow_mid.R"]},
    "AU05": {"name": "Upper Lid Raise", "bones": ["eyelid_upper.L", "eyelid_upper.R"]},
    "AU06": {"name": "Cheek Raise", "bones": ["cheek.L", "cheek.R"]},
    "AU07": {"name": "Lid Tightener", "bones": ["eyelid_lower.L", "eyelid_lower.R"]},
    "AU09": {"name": "Nose Wrinkler", "bones": ["nose"]},
    "AU10": {"name": "Upper Lip Raise", "bones": ["lip_upper"]},
    "AU12": {"name": "Lip Corner Pull", "bones": ["lip_corner.L", "lip_corner.R"]},
    "AU15": {"name": "Lip Corner Depress", "bones": ["lip_corner.L", "lip_corner.R"]},
    "AU17": {"name": "Chin Raise", "bones": ["jaw"]},
    "AU20": {"name": "Lip Stretch", "bones": ["lip_corner.L", "lip_corner.R"]},
    "AU23": {"name": "Lip Tightener", "bones": ["lip_upper", "lip_lower"]},
    "AU25": {"name": "Lips Part", "bones": ["lip_upper", "lip_lower", "jaw"]},
    "AU26": {"name": "Jaw Drop", "bones": ["jaw"]},
    "AU27": {"name": "Mouth Stretch", "bones": ["jaw"]},
    "AU45": {"name": "Blink", "bones": ["eyelid_upper.L", "eyelid_upper.R", "eyelid_lower.L", "eyelid_lower.R"]},
}


# ---------------------------------------------------------------------------
# Viseme Shapes (P2-A7)
# ---------------------------------------------------------------------------

VISEME_SHAPES: dict[str, dict] = {
    "sil": {"name": "Silence", "bones": []},
    "PP": {"name": "P/B/M", "bones": ["lip_upper", "lip_lower"]},
    "FF": {"name": "F/V", "bones": ["lip_lower"]},
    "TH": {"name": "Th", "bones": ["lip_upper", "lip_lower", "jaw"]},
    "DD": {"name": "D/T/N", "bones": ["jaw", "lip_upper"]},
    "kk": {"name": "K/G", "bones": ["jaw"]},
    "CH": {"name": "Ch/J/Sh", "bones": ["lip_corner.L", "lip_corner.R", "jaw"]},
    "SS": {"name": "S/Z", "bones": ["lip_corner.L", "lip_corner.R"]},
    "nn": {"name": "N/L", "bones": ["jaw", "lip_upper"]},
    "RR": {"name": "R", "bones": ["lip_corner.L", "lip_corner.R", "lip_upper"]},
    "aa": {"name": "A/Ah", "bones": ["jaw", "lip_upper", "lip_lower"]},
    "E": {"name": "E/Eh", "bones": ["lip_corner.L", "lip_corner.R", "jaw"]},
    "I": {"name": "I/Ee", "bones": ["lip_corner.L", "lip_corner.R"]},
    "O": {"name": "O/Oh", "bones": ["lip_upper", "lip_lower", "jaw"]},
    "U": {"name": "U/Oo", "bones": ["lip_upper", "lip_lower"]},
}


# ---------------------------------------------------------------------------
# Corrective Blend Shape Definitions (P5-Q1)
# ---------------------------------------------------------------------------

CORRECTIVE_SHAPE_DEFS: list[dict] = [
    {"joint": "shoulder", "axis": "x", "threshold": 45.0, "strength": 1.0, "name": "shoulder_corrective"},
    {"joint": "elbow", "axis": "x", "threshold": 90.0, "strength": 0.8, "name": "elbow_corrective"},
    {"joint": "wrist", "axis": "z", "threshold": 30.0, "strength": 0.6, "name": "wrist_corrective"},
    {"joint": "hip", "axis": "x", "threshold": 60.0, "strength": 1.0, "name": "hip_corrective"},
    {"joint": "knee", "axis": "x", "threshold": 90.0, "strength": 0.9, "name": "knee_corrective"},
]


# ---------------------------------------------------------------------------
# Pose-Space Deformation Definitions (AAA multi-bone-driven correctives)
# ---------------------------------------------------------------------------

POSE_SPACE_DEFORMATIONS: list[dict] = [
    {
        "name": "shoulder_raise_forward",
        "driver_bones": ["upper_arm.L", "upper_arm.L"],
        "driver_axes": ["Z", "X"],
        "thresholds": [60.0, 30.0],
        "description": "Deltoid volume preservation on forward + abduction",
    },
    {
        "name": "elbow_extreme_flex",
        "driver_bones": ["forearm.L"],
        "driver_axes": ["X"],
        "thresholds": [120.0],
        "description": "Bicep bulge and forearm compression at extreme flexion",
    },
    {
        "name": "knee_deep_squat",
        "driver_bones": ["thigh.L", "shin.L"],
        "driver_axes": ["X", "X"],
        "thresholds": [90.0, 90.0],
        "description": "Quad/calf volume at deep squat with proper hip fold",
    },
    {
        "name": "wrist_bend",
        "driver_bones": ["hand.L"],
        "driver_axes": ["X"],
        "thresholds": [45.0],
        "description": "Tendon visibility on wrist extension/flexion",
    },
    {
        "name": "neck_turn",
        "driver_bones": ["spine.004"],
        "driver_axes": ["Y"],
        "thresholds": [45.0],
        "description": "SCM muscle and trapezius activation on head turn",
    },
]


def _validate_psd_config(
    driver_bones: list[str],
    driver_axes: list[str],
    thresholds: list[float],
) -> dict:
    """Validate pose-space deformation configuration."""
    errors = []
    valid_axes = {"X", "Y", "Z"}

    if len(driver_bones) != len(driver_axes):
        errors.append("driver_bones and driver_axes must have same length")
    if len(driver_bones) != len(thresholds):
        errors.append("driver_bones and thresholds must have same length")

    for axis in driver_axes:
        if axis not in valid_axes:
            errors.append(f"Invalid axis: '{axis}'")

    for thresh in thresholds:
        if not isinstance(thresh, (int, float)) or thresh <= 0 or thresh > 180:
            errors.append(f"Threshold must be in (0, 180], got {thresh}")

    return {"valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Apple ARKit 52 Blendshape Mapping (industry standard facial capture)
# ---------------------------------------------------------------------------

ARKIT_BLENDSHAPE_MAP: dict[str, list[str]] = {
    "eyeBlinkLeft": ["eyelid_upper.L", "eyelid_lower.L"],
    "eyeBlinkRight": ["eyelid_upper.R", "eyelid_lower.R"],
    "eyeWideLeft": ["eyelid_upper.L"],
    "eyeWideRight": ["eyelid_upper.R"],
    "eyeSquintLeft": ["eyelid_lower.L", "cheek.L"],
    "eyeSquintRight": ["eyelid_lower.R", "cheek.R"],
    "eyeLookUpLeft": ["eye.L"],
    "eyeLookUpRight": ["eye.R"],
    "eyeLookDownLeft": ["eye.L"],
    "eyeLookDownRight": ["eye.R"],
    "eyeLookInLeft": ["eye.L"],
    "eyeLookInRight": ["eye.R"],
    "eyeLookOutLeft": ["eye.L"],
    "eyeLookOutRight": ["eye.R"],
    "jawOpen": ["jaw"],
    "jawForward": ["jaw"],
    "jawLeft": ["jaw"],
    "jawRight": ["jaw"],
    "mouthClose": ["lip_upper", "lip_lower"],
    "mouthFunnel": ["lip_upper", "lip_lower", "lip_corner.L", "lip_corner.R"],
    "mouthPucker": ["lip_upper", "lip_lower", "lip_corner.L", "lip_corner.R"],
    "mouthLeft": ["lip_corner.L"],
    "mouthRight": ["lip_corner.R"],
    "mouthSmileLeft": ["lip_corner.L"],
    "mouthSmileRight": ["lip_corner.R"],
    "mouthFrownLeft": ["lip_corner.L"],
    "mouthFrownRight": ["lip_corner.R"],
    "mouthDimpleLeft": ["lip_corner.L", "cheek.L"],
    "mouthDimpleRight": ["lip_corner.R", "cheek.R"],
    "mouthStretchLeft": ["lip_corner.L"],
    "mouthStretchRight": ["lip_corner.R"],
    "mouthRollLower": ["lip_lower"],
    "mouthRollUpper": ["lip_upper"],
    "mouthShrugLower": ["lip_lower"],
    "mouthShrugUpper": ["lip_upper"],
    "mouthPressLeft": ["lip_corner.L"],
    "mouthPressRight": ["lip_corner.R"],
    "mouthLowerDownLeft": ["lip_lower"],
    "mouthLowerDownRight": ["lip_lower"],
    "mouthUpperUpLeft": ["lip_upper"],
    "mouthUpperUpRight": ["lip_upper"],
    "browDownLeft": ["brow_inner.L", "brow_mid.L"],
    "browDownRight": ["brow_inner.R", "brow_mid.R"],
    "browInnerUp": ["brow_inner.L", "brow_inner.R"],
    "browOuterUpLeft": ["brow_outer.L"],
    "browOuterUpRight": ["brow_outer.R"],
    "cheekPuff": ["cheek.L", "cheek.R"],
    "cheekSquintLeft": ["cheek.L"],
    "cheekSquintRight": ["cheek.R"],
    "noseSneerLeft": ["nose"],
    "noseSneerRight": ["nose"],
    "tongueOut": ["jaw"],
}


# ---------------------------------------------------------------------------
# Monster expression presets (bone name -> transform dicts)
# ---------------------------------------------------------------------------

MONSTER_EXPRESSIONS: dict[str, dict[str, dict]] = {
    "snarl": {
        "lip_upper": {"location": (0, 0, 0.005)},
        "lip_corner.L": {"rotation": (0, 0, 0.3)},
        "lip_corner.R": {"rotation": (0, 0, -0.3)},
        "brow_inner.L": {"location": (0, 0, 0.003)},
        "brow_inner.R": {"location": (0, 0, 0.003)},
    },
    "hiss": {
        "jaw": {"rotation": (-0.3, 0, 0)},
        "lip_upper": {"location": (0, 0, 0.003)},
        "lip_lower": {"location": (0, 0, -0.003)},
    },
    "roar": {
        "jaw": {"rotation": (-0.8, 0, 0)},
        "lip_upper": {"location": (0, 0, 0.008)},
        "lip_corner.L": {"rotation": (0, 0, 0.5)},
        "lip_corner.R": {"rotation": (0, 0, -0.5)},
        "brow_inner.L": {"location": (0, 0, 0.005)},
        "brow_inner.R": {"location": (0, 0, 0.005)},
        "cheek.L": {"location": (0, 0, 0.003)},
        "cheek.R": {"location": (0, 0, 0.003)},
    },
}


# ---------------------------------------------------------------------------
# Ragdoll presets -- default bone-to-collider mappings for common rig types
# ---------------------------------------------------------------------------

RAGDOLL_PRESETS: dict[str, dict[str, dict]] = {
    "humanoid": {
        "DEF-spine": {
            "shape": "CAPSULE",
            "radius": 0.1,
            "length": 0.3,
            "mass": 5.0,
            "joint_type": "GENERIC",
            "ang_x_min": -0.3,
            "ang_x_max": 0.3,
            "ang_y_min": -0.2,
            "ang_y_max": 0.2,
            "ang_z_min": -0.2,
            "ang_z_max": 0.2,
        },
        "DEF-spine.001": {
            "shape": "CAPSULE",
            "radius": 0.09,
            "length": 0.25,
            "mass": 4.0,
            "joint_type": "GENERIC",
            "ang_x_min": -0.3,
            "ang_x_max": 0.3,
            "ang_y_min": -0.2,
            "ang_y_max": 0.2,
            "ang_z_min": -0.2,
            "ang_z_max": 0.2,
        },
        "DEF-upper_arm.L": {
            "shape": "CAPSULE",
            "radius": 0.04,
            "length": 0.28,
            "mass": 2.0,
            "joint_type": "GENERIC",
            "ang_x_min": -1.5,
            "ang_x_max": 1.5,
            "ang_y_min": -0.1,
            "ang_y_max": 3.0,
            "ang_z_min": -1.0,
            "ang_z_max": 0.5,
        },
        "DEF-upper_arm.R": {
            "shape": "CAPSULE",
            "radius": 0.04,
            "length": 0.28,
            "mass": 2.0,
            "joint_type": "GENERIC",
            "ang_x_min": -1.5,
            "ang_x_max": 1.5,
            "ang_y_min": -3.0,
            "ang_y_max": 0.1,
            "ang_z_min": -0.5,
            "ang_z_max": 1.0,
        },
        "DEF-forearm.L": {
            "shape": "CAPSULE",
            "radius": 0.035,
            "length": 0.26,
            "mass": 1.5,
            "joint_type": "GENERIC",
            "ang_x_min": 0.0,
            "ang_x_max": 2.5,
            "ang_y_min": -0.1,
            "ang_y_max": 0.1,
            "ang_z_min": -0.1,
            "ang_z_max": 0.1,
        },
        "DEF-forearm.R": {
            "shape": "CAPSULE",
            "radius": 0.035,
            "length": 0.26,
            "mass": 1.5,
            "joint_type": "GENERIC",
            "ang_x_min": 0.0,
            "ang_x_max": 2.5,
            "ang_y_min": -0.1,
            "ang_y_max": 0.1,
            "ang_z_min": -0.1,
            "ang_z_max": 0.1,
        },
        "DEF-thigh.L": {
            "shape": "CAPSULE",
            "radius": 0.06,
            "length": 0.4,
            "mass": 4.0,
            "joint_type": "GENERIC",
            "ang_x_min": -1.5,
            "ang_x_max": 0.5,
            "ang_y_min": -0.3,
            "ang_y_max": 0.3,
            "ang_z_min": -0.5,
            "ang_z_max": 1.0,
        },
        "DEF-thigh.R": {
            "shape": "CAPSULE",
            "radius": 0.06,
            "length": 0.4,
            "mass": 4.0,
            "joint_type": "GENERIC",
            "ang_x_min": -1.5,
            "ang_x_max": 0.5,
            "ang_y_min": -0.3,
            "ang_y_max": 0.3,
            "ang_z_min": -1.0,
            "ang_z_max": 0.5,
        },
        "DEF-shin.L": {
            "shape": "CAPSULE",
            "radius": 0.045,
            "length": 0.38,
            "mass": 2.5,
            "joint_type": "GENERIC",
            "ang_x_min": -2.5,
            "ang_x_max": 0.0,
            "ang_y_min": -0.1,
            "ang_y_max": 0.1,
            "ang_z_min": -0.1,
            "ang_z_max": 0.1,
        },
        "DEF-shin.R": {
            "shape": "CAPSULE",
            "radius": 0.045,
            "length": 0.38,
            "mass": 2.5,
            "joint_type": "GENERIC",
            "ang_x_min": -2.5,
            "ang_x_max": 0.0,
            "ang_y_min": -0.1,
            "ang_y_max": 0.1,
            "ang_z_min": -0.1,
            "ang_z_max": 0.1,
        },
        "DEF-head": {
            "shape": "BOX",
            "radius": 0.1,
            "length": 0.15,
            "mass": 3.0,
            "joint_type": "GENERIC",
            "ang_x_min": -0.5,
            "ang_x_max": 0.5,
            "ang_y_min": -0.7,
            "ang_y_max": 0.7,
            "ang_z_min": -0.3,
            "ang_z_max": 0.3,
        },
    },
}


# ---------------------------------------------------------------------------
# Pure-logic validation functions (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_ik_params(params: dict) -> dict:
    """Validate IK constraint parameters.

    Args:
        params: Dict with bone_name, chain_length, constraint_type,
                pole_angle, and optionally curve_points for SPLINE_IK.

    Returns:
        Dict with valid (bool) and errors (list[str]).
    """
    errors: list[str] = []

    # bone_name
    bone_name = params.get("bone_name")
    if not isinstance(bone_name, str) or not bone_name:
        errors.append("bone_name must be a non-empty string")

    # chain_length
    chain_length = params.get("chain_length", 2)
    if not isinstance(chain_length, (int, float)):
        errors.append("chain_length must be a number")
    elif chain_length < 1:
        errors.append("chain_length must be >= 1")
    elif chain_length > 20:
        errors.append("chain_length must be <= 20")

    # constraint_type
    constraint_type = params.get("constraint_type", "IK")
    valid_types = ("IK", "SPLINE_IK")
    if constraint_type not in valid_types:
        errors.append(
            f"constraint_type must be one of {valid_types}, got '{constraint_type}'"
        )

    # pole_angle
    pole_angle = params.get("pole_angle", 0.0)
    if not isinstance(pole_angle, (int, float)):
        errors.append("pole_angle must be a float")

    # SPLINE_IK requires curve_points
    if constraint_type == "SPLINE_IK":
        curve_points = params.get("curve_points", 0)
        if not isinstance(curve_points, (int, float)):
            errors.append("curve_points must be a number for SPLINE_IK")
        elif curve_points < 2:
            errors.append("curve_points must be >= 2 for SPLINE_IK")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_spring_params(
    bone_names: list[str],
    stiffness: float,
    damping: float,
    gravity: float,
) -> dict:
    """Validate spring bone constraint parameters.

    Args:
        bone_names: List of bone names to apply spring constraints.
        stiffness: Spring stiffness factor [0, 1].
        damping: Damping factor [0, 1].
        gravity: Gravity influence >= 0.

    Returns:
        Dict with valid (bool), errors (list[str]), bone_count (int).
    """
    errors: list[str] = []

    # bone_names
    if not isinstance(bone_names, (list, tuple)) or len(bone_names) == 0:
        errors.append("bone_names must be a non-empty list")
    else:
        for i, name in enumerate(bone_names):
            if not isinstance(name, str) or not name:
                errors.append(f"bone_names[{i}] must be a non-empty string")

    # stiffness
    if not isinstance(stiffness, (int, float)):
        errors.append("stiffness must be a number")
    elif stiffness < 0 or stiffness > 1:
        errors.append("stiffness must be in [0, 1]")

    # damping
    if not isinstance(damping, (int, float)):
        errors.append("damping must be a number")
    elif damping < 0 or damping > 1:
        errors.append("damping must be in [0, 1]")

    # gravity
    if not isinstance(gravity, (int, float)):
        errors.append("gravity must be a number")
    elif gravity < 0:
        errors.append("gravity must be >= 0")

    bone_count = len(bone_names) if isinstance(bone_names, (list, tuple)) else 0
    return {"valid": len(errors) == 0, "errors": errors, "bone_count": bone_count}


def _validate_ragdoll_spec(bone_collider_map: dict) -> dict:
    """Validate ragdoll bone-to-collider specification.

    Args:
        bone_collider_map: Dict mapping bone names to collider specs.
            Each spec needs shape (BOX or CAPSULE), radius > 0,
            length > 0, mass > 0.

    Returns:
        Dict with valid (bool), errors (list[str]), collider_count (int).
    """
    errors: list[str] = []

    if not isinstance(bone_collider_map, dict) or len(bone_collider_map) == 0:
        errors.append("bone_collider_map must be a non-empty dict")
        return {"valid": False, "errors": errors, "collider_count": 0}

    valid_shapes = ("BOX", "CAPSULE")
    required_fields = {"shape", "radius", "length", "mass"}

    for bone_name, spec in bone_collider_map.items():
        if not isinstance(spec, dict):
            errors.append(f"'{bone_name}': spec must be a dict")
            continue

        # Check required fields
        missing = required_fields - set(spec.keys())
        if missing:
            errors.append(f"'{bone_name}': missing fields {sorted(missing)}")
            continue

        # shape
        if spec["shape"] not in valid_shapes:
            errors.append(
                f"'{bone_name}': shape must be one of {valid_shapes}, "
                f"got '{spec['shape']}'"
            )

        # radius
        if not isinstance(spec["radius"], (int, float)) or spec["radius"] <= 0:
            errors.append(f"'{bone_name}': radius must be > 0")

        # length
        if not isinstance(spec["length"], (int, float)) or spec["length"] <= 0:
            errors.append(f"'{bone_name}': length must be > 0")

        # mass
        if not isinstance(spec["mass"], (int, float)) or spec["mass"] <= 0:
            errors.append(f"'{bone_name}': mass must be > 0")

        # Joint angle limits (optional but validate if present)
        for ang_key in ("ang_x_min", "ang_x_max", "ang_y_min", "ang_y_max",
                        "ang_z_min", "ang_z_max"):
            if ang_key in spec:
                val = spec[ang_key]
                if not isinstance(val, (int, float)):
                    errors.append(f"'{bone_name}': {ang_key} must be a number")
                elif val < -math.pi or val > math.pi:
                    errors.append(
                        f"'{bone_name}': {ang_key} must be in [-pi, pi]"
                    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "collider_count": len(bone_collider_map),
    }


def _validate_retarget_mapping(
    source_bones: list[str],
    target_bones: list[str],
    mapping: dict[str, str],
) -> dict:
    """Validate retarget bone mapping between source and target rigs.

    Args:
        source_bones: List of bone names in the source rig.
        target_bones: List of bone names in the target rig.
        mapping: Dict mapping source bone names to target bone names.

    Returns:
        Dict with valid (bool), errors (list[str]), mapped_count (int),
        unmapped_source (list), unmapped_target (list).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(mapping, dict) or len(mapping) == 0:
        errors.append("mapping must be a non-empty dict")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "mapped_count": 0,
            "unmapped_source": list(source_bones) if isinstance(source_bones, list) else [],
            "unmapped_target": list(target_bones) if isinstance(target_bones, list) else [],
            "duplicate_targets": [],
        }

    source_set = set(source_bones) if isinstance(source_bones, list) else set()
    target_set = set(target_bones) if isinstance(target_bones, list) else set()

    # Validate all mapped source bones exist
    for src_bone in mapping.keys():
        if src_bone not in source_set:
            errors.append(f"source bone '{src_bone}' not found in source rig")

    # Validate all mapped target bones exist
    for tgt_bone in mapping.values():
        if tgt_bone not in target_set:
            errors.append(f"target bone '{tgt_bone}' not found in target rig")

    # Check for duplicate targets
    target_counts: dict[str, int] = {}
    for tgt in mapping.values():
        target_counts[tgt] = target_counts.get(tgt, 0) + 1
    duplicate_targets = [t for t, c in target_counts.items() if c > 1]
    if duplicate_targets:
        for dt in duplicate_targets:
            warnings.append(
                f"Warning: target bone '{dt}' mapped from {target_counts[dt]} sources"
            )

    # Compute unmapped bones
    mapped_sources = set(mapping.keys())
    mapped_targets = set(mapping.values())
    unmapped_source = sorted(source_set - mapped_sources)
    unmapped_target = sorted(target_set - mapped_targets)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "mapped_count": len(mapping),
        "unmapped_source": unmapped_source,
        "unmapped_target": unmapped_target,
        "duplicate_targets": duplicate_targets,
    }


def _validate_shape_key_params(name: str, vertex_offsets: dict) -> dict:
    """Validate shape key creation parameters.

    Args:
        name: Shape key name (non-empty, only alphanumeric/underscore/hyphen).
        vertex_offsets: Dict mapping vertex indices (int) to 3-element
            tuples/lists of floats representing xyz offsets.

    Returns:
        Dict with valid (bool), errors (list[str]), vertex_count (int).
    """
    errors: list[str] = []

    # name validation
    if not isinstance(name, str) or not name:
        errors.append("name must be a non-empty string")
    elif not re.match(r"^[a-zA-Z0-9_\-]+$", name):
        errors.append(
            "name must contain only alphanumeric characters, underscores, or hyphens"
        )

    # vertex_offsets validation
    if not isinstance(vertex_offsets, dict):
        errors.append("vertex_offsets must be a dict")
        return {"valid": False, "errors": errors, "vertex_count": 0}

    if len(vertex_offsets) == 0:
        errors.append("vertex_offsets must not be empty")

    for idx, offset in vertex_offsets.items():
        # Key must be a non-negative int
        if not isinstance(idx, int) or idx < 0:
            errors.append(
                f"vertex index must be a non-negative int, got {idx!r}"
            )
            continue

        # Value must be 3-element tuple/list of floats
        if not isinstance(offset, (tuple, list)):
            errors.append(f"vertex {idx}: offset must be a tuple or list")
            continue
        if len(offset) != 3:
            errors.append(
                f"vertex {idx}: offset must have 3 elements, got {len(offset)}"
            )
            continue
        for j, val in enumerate(offset):
            if not isinstance(val, (int, float)):
                errors.append(
                    f"vertex {idx}: offset[{j}] must be a number, "
                    f"got {type(val).__name__}"
                )

    vertex_count = sum(
        1 for idx in vertex_offsets if isinstance(idx, int) and idx >= 0
    )
    return {"valid": len(errors) == 0, "errors": errors, "vertex_count": vertex_count}


def _compute_spring_chain_forces(
    positions: list[tuple[float, float, float]],
    velocities: list[tuple[float, float, float]],
    stiffness: float,
    damping: float,
    gravity: float,
    dt: float = 1.0 / 60.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Compute spring bone simulation forces for a chain of bones.

    Simple spring-mass simulation: the first bone is the root (fixed),
    subsequent bones are pulled back toward rest position by stiffness and
    dragged down by gravity.

    Args:
        positions: Current world-space positions per bone.
        velocities: Current velocities per bone.
        stiffness: Spring stiffness [0, 1].
        damping: Damping factor [0, 1].
        gravity: Gravity magnitude (applied in -Z).
        dt: Timestep (default 1/60).

    Returns:
        Tuple of (new_positions, new_velocities) — each a list of (x, y, z)
        tuples per bone after one simulation step. Returning velocities
        enables multi-frame simulation by feeding them back as input.
    """
    # Compute rest offsets from initial positions so the spring force
    # maintains the bone's rest distance from its parent instead of
    # collapsing all bones onto the parent position.
    rest_offsets: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]
    for i in range(1, len(positions)):
        rest_offsets.append((
            positions[i][0] - positions[i - 1][0],
            positions[i][1] - positions[i - 1][1],
            positions[i][2] - positions[i - 1][2],
        ))

    new_positions: list[tuple[float, float, float]] = []
    new_velocities: list[tuple[float, float, float]] = []
    for i, (pos, vel) in enumerate(zip(positions, velocities)):
        if i == 0:
            # Root bone is fixed
            new_positions.append(pos)
            new_velocities.append(vel)
            continue

        px, py, pz = pos
        vx, vy, vz = vel

        # Rest position = parent position + rest offset
        parent = positions[i - 1]
        rest_x = parent[0] + rest_offsets[i][0]
        rest_y = parent[1] + rest_offsets[i][1]
        rest_z = parent[2] + rest_offsets[i][2]

        # Spring force pulling back toward rest position (not parent)
        spring_fx = stiffness * (rest_x - px)
        spring_fy = stiffness * (rest_y - py)
        spring_fz = stiffness * (rest_z - pz)

        # Gravity in -Z
        grav_fz = -gravity

        # Total acceleration
        ax = spring_fx - damping * vx
        ay = spring_fy - damping * vy
        az = spring_fz + grav_fz - damping * vz

        # Euler integration
        nvx = vx + ax * dt
        nvy = vy + ay * dt
        nvz = vz + az * dt

        npx = px + nvx * dt
        npy = py + nvy * dt
        npz = pz + nvz * dt

        new_positions.append((npx, npy, npz))
        new_velocities.append((nvx, nvy, nvz))

    return (new_positions, new_velocities)


def _validate_spring_dynamics_params(
    mass: float,
    stiffness: float,
    damping: float,
) -> dict:
    """Validate spring dynamics simulation parameters.

    Args:
        mass: Mass of each bone node (must be > 0).
        stiffness: Spring stiffness (must be in (0, 100]).
        damping: Damping factor (must be in [0, 1]).

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    if not isinstance(mass, (int, float)) or mass <= 0:
        errors.append("mass must be > 0")
    if not isinstance(stiffness, (int, float)) or stiffness <= 0 or stiffness > 100:
        errors.append("stiffness must be in (0, 100]")
    if not isinstance(damping, (int, float)) or damping < 0 or damping > 1:
        errors.append("damping must be in [0, 1]")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_facial_rig_params(params: dict) -> dict:
    """Validate facial rig setup parameters.

    Args:
        params: Dict with optional keys:
            expressions: list of expression names (must be in MONSTER_EXPRESSIONS)
            facs_units: list of FACS AU codes (must be in FACS_ACTION_UNITS)
            visemes: list of viseme codes (must be in VISEME_SHAPES)

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []

    expressions = params.get("expressions", [])
    if expressions:
        for expr in expressions:
            if expr not in MONSTER_EXPRESSIONS:
                errors.append(f"Unknown expression: '{expr}'")

    facs_units = params.get("facs_units", [])
    if facs_units:
        for au in facs_units:
            if au not in FACS_ACTION_UNITS:
                errors.append(f"Unknown FACS unit: '{au}'")

    visemes = params.get("visemes", [])
    if visemes:
        for vis in visemes:
            if vis not in VISEME_SHAPES:
                errors.append(f"Unknown viseme: '{vis}'")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_corrective_shape_config(config: dict) -> dict:
    """Validate a corrective blend shape configuration.

    Args:
        config: Dict with keys: joint, axis, threshold, strength.
            joint must be one of: shoulder, elbow, wrist, hip, knee.
            axis must be one of: x, y, z.
            threshold must be in [0, 180].
            strength must be in [0, 2].

    Returns:
        Dict with valid (bool), errors (list[str]).
    """
    errors: list[str] = []
    valid_joints = {"shoulder", "elbow", "wrist", "hip", "knee"}
    valid_axes = {"x", "y", "z"}

    joint = config.get("joint")
    if joint not in valid_joints:
        errors.append(f"joint must be one of {sorted(valid_joints)}, got '{joint}'")

    axis = config.get("axis")
    if axis not in valid_axes:
        errors.append(f"axis must be one of {sorted(valid_axes)}, got '{axis}'")

    threshold = config.get("threshold")
    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 180:
        errors.append("threshold must be in [0, 180]")

    strength = config.get("strength")
    if not isinstance(strength, (int, float)) or strength < 0 or strength > 2:
        errors.append("strength must be in [0, 2]")

    return {"valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Blender-dependent handlers
# ---------------------------------------------------------------------------


def handle_setup_facial(params: dict) -> dict:
    """Set up a bone-based facial rig with monster expression presets (RIG-04).

    Params:
        rig_name: Name of the armature object to add facial bones to.
        expressions: Optional list of expression preset names from
                     MONSTER_EXPRESSIONS to store as pose library entries.

    Returns dict with facial_bones_added, expressions_stored, rig_name.
    """
    rig_name = params.get("rig_name")
    if not rig_name:
        raise ValueError("'rig_name' is required")

    rig_obj = bpy.data.objects.get(rig_name)
    if not rig_obj or rig_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {rig_name}")

    expressions = params.get("expressions", [])
    arm = rig_obj.data

    # Enter edit mode to add facial bones
    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.object.mode_set(mode="EDIT")

    bones_added = 0
    for bone_name, bone_def in FACIAL_BONES.items():
        if bone_name in arm.edit_bones:
            continue  # Skip if bone already exists

        eb = arm.edit_bones.new(bone_name)
        eb.head = Vector(bone_def["head"])
        eb.tail = Vector(bone_def["tail"])
        eb.roll = bone_def["roll"]

        parent_name = bone_def["parent"]
        if parent_name and parent_name in arm.edit_bones:
            eb.parent = arm.edit_bones[parent_name]

        bones_added += 1

    bpy.ops.object.mode_set(mode="OBJECT")

    # Store expression presets as pose bone keyframes
    expressions_stored: list[str] = []
    if expressions:
        bpy.ops.object.mode_set(mode="POSE")
        for expr_name in expressions:
            if expr_name not in MONSTER_EXPRESSIONS:
                continue

            bone_transforms = MONSTER_EXPRESSIONS[expr_name]
            for bone_name, transform in bone_transforms.items():
                pbone = rig_obj.pose.bones.get(bone_name)
                if not pbone:
                    continue

                if "location" in transform:
                    pbone.location = Vector(transform["location"])
                if "rotation" in transform:
                    pbone.rotation_mode = "XYZ"
                    pbone.rotation_euler = Euler(transform["rotation"])

            # Store as a pose marker (custom property for retrieval)
            rig_obj[f"expression_{expr_name}"] = True
            expressions_stored.append(expr_name)

            # Reset pose for next expression
            for pbone in rig_obj.pose.bones:
                pbone.location = Vector((0, 0, 0))
                pbone.rotation_euler = Euler((0, 0, 0))

        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "facial_bones_added": bones_added,
        "expressions_stored": expressions_stored,
        "rig_name": rig_obj.name,
    }


def handle_setup_ik(params: dict) -> dict:
    """Set up IK constraints (standard 2-bone or spline IK) on rig bones (RIG-05).

    Params:
        rig_name: Name of the armature object.
        bone_name: Name of the bone to add IK constraint to.
        chain_length: Number of bones in the IK chain.
        constraint_type: "IK" or "SPLINE_IK".
        pole_angle: Pole angle for standard IK.
        pole_target_bone: Optional pole target bone name.
        curve_points: Number of control points for SPLINE_IK curve.
        joint_limits: Optional dict of bone_name -> {min_x, max_x, ...} for
                      LIMIT_ROTATION constraints.

    Returns dict with constraint, chain_length, type.
    """
    rig_name = params.get("rig_name")
    if not rig_name:
        raise ValueError("'rig_name' is required")

    # Validate IK params
    validation = _validate_ik_params(params)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid IK params: {'; '.join(validation['errors'])}"
        )

    rig_obj = bpy.data.objects.get(rig_name)
    if not rig_obj or rig_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {rig_name}")

    bone_name = params["bone_name"]
    chain_length = int(params.get("chain_length", 2))
    constraint_type = params.get("constraint_type", "IK")
    pole_angle = float(params.get("pole_angle", 0.0))

    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.object.mode_set(mode="POSE")

    pbone = rig_obj.pose.bones.get(bone_name)
    if not pbone:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise ValueError(f"Pose bone not found: {bone_name}")

    if constraint_type == "SPLINE_IK":
        # Create control curve for spline IK
        curve_points_count = int(params.get("curve_points", 4))

        curve_data = bpy.data.curves.new(f"{bone_name}_spline", type="CURVE")
        curve_data.dimensions = "3D"
        spline = curve_data.splines.new("NURBS")
        spline.points.add(curve_points_count - 1)

        # Distribute control points along the bone chain
        current = pbone
        points = [current.head.copy()]
        for _i in range(chain_length):
            if current.parent:
                current = current.parent
                points.append(current.head.copy())
            else:
                break
        points.reverse()

        # Space control points evenly
        for i, pt in enumerate(spline.points):
            if i < len(points):
                pt.co = (*points[i], 1.0)
            else:
                pt.co = (*points[-1], 1.0)

        curve_obj = bpy.data.objects.new(f"{bone_name}_spline", curve_data)
        bpy.context.collection.objects.link(curve_obj)

        # Add SPLINE_IK constraint
        con = pbone.constraints.new("SPLINE_IK")
        con.target = curve_obj
        con.chain_count = chain_length

        result_type = "SPLINE_IK"
    else:
        # Standard IK
        con = pbone.constraints.new("IK")
        con.chain_count = chain_length
        con.pole_angle = pole_angle

        # Set pole target if specified
        pole_target_bone = params.get("pole_target_bone")
        if pole_target_bone and pole_target_bone in rig_obj.pose.bones:
            con.pole_target = rig_obj
            con.pole_subtarget = pole_target_bone

        result_type = "IK"

    # Add joint limits if specified
    joint_limits = params.get("joint_limits", {})
    for limit_bone, limits in joint_limits.items():
        lpbone = rig_obj.pose.bones.get(limit_bone)
        if not lpbone:
            continue
        limit_con = lpbone.constraints.new("LIMIT_ROTATION")
        limit_con.use_limit_x = True
        limit_con.use_limit_y = True
        limit_con.use_limit_z = True
        limit_con.min_x = limits.get("min_x", -math.pi)
        limit_con.max_x = limits.get("max_x", math.pi)
        limit_con.min_y = limits.get("min_y", -math.pi)
        limit_con.max_y = limits.get("max_y", math.pi)
        limit_con.min_z = limits.get("min_z", -math.pi)
        limit_con.max_z = limits.get("max_z", math.pi)
        limit_con.owner_space = "LOCAL"

    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "constraint": con.name,
        "chain_length": chain_length,
        "type": result_type,
    }


def handle_setup_spring_bones(params: dict) -> dict:
    """Set up secondary motion constraints for spring/jiggle bones (RIG-06).

    Params:
        rig_name: Name of the armature object.
        bone_names: List of bone names to apply spring constraints.
        stiffness: Spring stiffness [0, 1].
        damping: Damping factor [0, 1].
        gravity: Gravity influence >= 0.

    Returns dict with spring_bones, stiffness, damping, gravity.
    """
    rig_name = params.get("rig_name")
    if not rig_name:
        raise ValueError("'rig_name' is required")

    bone_names = params.get("bone_names", [])
    stiffness = float(params.get("stiffness", 0.5))
    damping = float(params.get("damping", 0.3))
    gravity = float(params.get("gravity", 1.0))

    validation = _validate_spring_params(bone_names, stiffness, damping, gravity)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid spring params: {'; '.join(validation['errors'])}"
        )

    rig_obj = bpy.data.objects.get(rig_name)
    if not rig_obj or rig_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {rig_name}")

    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.object.mode_set(mode="POSE")

    spring_bones: list[str] = []

    for i, bone_name in enumerate(bone_names):
        pbone = rig_obj.pose.bones.get(bone_name)
        if not pbone:
            continue

        # Add COPY_ROTATION from parent with decaying influence for damping
        if pbone.parent:
            cr_con = pbone.constraints.new("COPY_ROTATION")
            cr_con.target = rig_obj
            cr_con.subtarget = pbone.parent.name
            # Decay influence along the chain
            decay = damping * (0.8 ** i)
            cr_con.influence = max(0.0, min(1.0, decay))
            cr_con.name = f"spring_damping_{bone_name}"

        # Store spring params as custom properties
        pbone["spring_stiffness"] = stiffness
        pbone["spring_damping"] = damping
        pbone["spring_gravity"] = gravity

        spring_bones.append(bone_name)

    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "spring_bones": spring_bones,
        "stiffness": stiffness,
        "damping": damping,
        "gravity": gravity,
    }


def handle_setup_ragdoll(params: dict) -> dict:
    """Auto-generate ragdoll colliders and joint constraints from rig bones (RIG-11).

    Params:
        rig_name: Name of the armature object.
        bone_collider_map: Dict mapping bone names to collider specs, OR
        preset: Name of a preset from RAGDOLL_PRESETS.

    Returns dict with colliders, joint_count, preset_used.
    """
    rig_name = params.get("rig_name")
    if not rig_name:
        raise ValueError("'rig_name' is required")

    rig_obj = bpy.data.objects.get(rig_name)
    if not rig_obj or rig_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {rig_name}")

    # Get collider spec from preset or explicit map
    preset_name = params.get("preset")
    bone_collider_map = params.get("bone_collider_map")
    preset_used = None

    if preset_name:
        if preset_name not in RAGDOLL_PRESETS:
            raise ValueError(
                f"Unknown ragdoll preset: '{preset_name}'. "
                f"Valid: {sorted(RAGDOLL_PRESETS.keys())}"
            )
        bone_collider_map = RAGDOLL_PRESETS[preset_name]
        preset_used = preset_name
    elif not bone_collider_map:
        raise ValueError("'bone_collider_map' or 'preset' is required")

    # Validate the spec
    validation = _validate_ragdoll_spec(bone_collider_map)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid ragdoll spec: {'; '.join(validation['errors'])}"
        )

    ctx = get_3d_context_override()

    colliders: list[str] = []
    joint_count = 0
    # Map bone names to their collider objects for parent-based joint chaining
    bone_collider_lookup: dict[str, object] = {}

    # Sort bones by hierarchy depth (parent bones first) for correct joint chaining
    def _bone_depth(bone_name):
        depth = 0
        b = rig_obj.data.bones.get(bone_name)
        while b and b.parent:
            depth += 1
            b = b.parent
        return depth

    sorted_bones = sorted(bone_collider_map.keys(), key=_bone_depth)

    for bone_name in sorted_bones:
        spec = bone_collider_map[bone_name]
        # Check bone exists in rig
        bone = rig_obj.data.bones.get(bone_name)
        if not bone:
            continue

        # Create collider mesh
        shape = spec["shape"]
        radius = spec["radius"]
        length = spec["length"]

        if shape == "CAPSULE":
            bpy.ops.mesh.primitive_cylinder_add(
                radius=radius, depth=length, location=(0, 0, 0)
            )
        else:  # BOX
            bpy.ops.mesh.primitive_cube_add(
                size=1.0, location=(0, 0, 0)
            )
            bpy.context.object.scale = (radius, radius, length / 2)
            bpy.ops.object.transform_apply(scale=True)

        collider = bpy.context.object
        collider.name = f"ragdoll_{bone_name}"
        collider.display_type = "WIRE"

        # Position at bone
        pbone = rig_obj.pose.bones.get(bone_name)
        if pbone:
            bone_center = (pbone.head + pbone.tail) / 2
            collider.location = rig_obj.matrix_world @ bone_center

        # Add rigid body
        bpy.context.view_layer.objects.active = collider
        bpy.ops.rigidbody.object_add(type="ACTIVE")
        collider.rigid_body.mass = spec["mass"]
        collider.rigid_body.collision_shape = (
            "CAPSULE" if shape == "CAPSULE" else "BOX"
        )

        # Parent to bone
        collider.parent = rig_obj
        collider.parent_bone = bone_name
        collider.parent_type = "BONE"

        colliders.append(collider.name)
        bone_collider_lookup[bone_name] = collider

        # Create rigid body constraint to PARENT bone's collider (not linear chain)
        parent_bone = bone.parent
        parent_collider = None
        if parent_bone:
            parent_collider = bone_collider_lookup.get(parent_bone.name)
        if parent_collider:
            bpy.ops.object.empty_add(location=collider.location)
            joint_obj = bpy.context.object
            joint_obj.name = f"ragdoll_joint_{bone_name}"

            bpy.ops.rigidbody.constraint_add(type="GENERIC")
            rbc = joint_obj.rigid_body_constraint
            rbc.object1 = parent_collider
            rbc.object2 = collider

            # Apply joint angle limits
            rbc.use_limit_ang_x = True
            rbc.use_limit_ang_y = True
            rbc.use_limit_ang_z = True
            rbc.limit_ang_x_lower = spec.get("ang_x_min", -0.5)
            rbc.limit_ang_x_upper = spec.get("ang_x_max", 0.5)
            rbc.limit_ang_y_lower = spec.get("ang_y_min", -0.5)
            rbc.limit_ang_y_upper = spec.get("ang_y_max", 0.5)
            rbc.limit_ang_z_lower = spec.get("ang_z_min", -0.3)
            rbc.limit_ang_z_upper = spec.get("ang_z_max", 0.3)

            joint_count += 1

    return {
        "colliders": colliders,
        "joint_count": joint_count,
        "preset_used": preset_used,
    }


def handle_retarget_rig(params: dict) -> dict:
    """Map bones between source and target rigs with constraint-based transfer (RIG-12).

    Params:
        source_rig: Name of the source armature object.
        target_rig: Name of the target armature object.
        mapping: Dict mapping source bone names to target bone names.

    Returns dict with mapped_bones, source_rig, target_rig, unmapped.
    """
    source_name = params.get("source_rig")
    target_name = params.get("target_rig")
    mapping = params.get("mapping", {})

    if not source_name:
        raise ValueError("'source_rig' is required")
    if not target_name:
        raise ValueError("'target_rig' is required")

    source_obj = bpy.data.objects.get(source_name)
    if not source_obj or source_obj.type != "ARMATURE":
        raise ValueError(f"Source armature not found: {source_name}")

    target_obj = bpy.data.objects.get(target_name)
    if not target_obj or target_obj.type != "ARMATURE":
        raise ValueError(f"Target armature not found: {target_name}")

    # Get bone lists
    source_bones = [b.name for b in source_obj.data.bones]
    target_bones = [b.name for b in target_obj.data.bones]

    # Validate mapping
    validation = _validate_retarget_mapping(source_bones, target_bones, mapping)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid retarget mapping: {'; '.join(validation['errors'])}"
        )

    # Apply constraints on target rig
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.mode_set(mode="POSE")

    mapped_count = 0
    for src_bone, tgt_bone in mapping.items():
        tgt_pbone = target_obj.pose.bones.get(tgt_bone)
        if not tgt_pbone:
            continue

        src_pbone = source_obj.pose.bones.get(src_bone)
        if not src_pbone:
            continue

        # Compute bone length ratio for influence scaling
        src_len = (src_pbone.tail - src_pbone.head).length
        tgt_len = (tgt_pbone.tail - tgt_pbone.head).length
        scale_factor = tgt_len / max(src_len, 0.001)

        # Add COPY_ROTATION constraint
        cr_con = tgt_pbone.constraints.new("COPY_ROTATION")
        cr_con.target = source_obj
        cr_con.subtarget = src_bone
        cr_con.name = f"retarget_rot_{src_bone}"

        # Add COPY_LOCATION constraint (scaled by bone ratio)
        cl_con = tgt_pbone.constraints.new("COPY_LOCATION")
        cl_con.target = source_obj
        cl_con.subtarget = src_bone
        cl_con.influence = min(1.0, scale_factor)
        cl_con.name = f"retarget_loc_{src_bone}"

        mapped_count += 1

    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "mapped_bones": mapped_count,
        "source_rig": source_obj.name,
        "target_rig": target_obj.name,
        "unmapped": validation["unmapped_target"],
    }


def handle_add_shape_keys(params: dict) -> dict:
    """Create expression and damage state mesh deformations as shape keys (RIG-13).

    Params:
        object_name: Name of the mesh object.
        shape_key_name: Name for the new shape key.
        mode: "expression", "damage", or "custom".
        expression_name: For mode="expression", name from MONSTER_EXPRESSIONS.
        vertex_offsets: For mode="custom", dict of vertex_index -> (x, y, z) offsets.
        damage_intensity: For mode="damage", float 0-1 controlling displacement magnitude.

    Returns dict with shape_key, vertices_modified, total_shape_keys.
    """
    obj_name = params.get("object_name")
    shape_key_name = params.get("shape_key_name")
    mode = params.get("mode", "custom")

    if not obj_name:
        raise ValueError("'object_name' is required")
    if not shape_key_name:
        raise ValueError("'shape_key_name' is required")

    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {obj_name}")

    # Ensure Basis shape key exists
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis")

    vertices_modified = 0

    if mode == "expression":
        expr_name = params.get("expression_name")
        if not expr_name or expr_name not in MONSTER_EXPRESSIONS:
            raise ValueError(
                f"Invalid expression_name. Valid: {sorted(MONSTER_EXPRESSIONS.keys())}"
            )

        sk = obj.shape_key_add(name=shape_key_name)
        # Expression shape keys: apply small offsets based on expression bone transforms
        bone_transforms = MONSTER_EXPRESSIONS[expr_name]
        vertex_count = len(obj.data.vertices)

        # Map facial regions to vertex groups for expression influence
        for bone_name, transform in bone_transforms.items():
            vg = obj.vertex_groups.get(bone_name)
            if not vg:
                continue

            offset = Vector((0, 0, 0))
            if "location" in transform:
                offset = Vector(transform["location"])
            if "rotation" in transform:
                # Convert rotation to approximate displacement
                rot = transform["rotation"]
                offset += Vector((rot[0] * 0.01, rot[1] * 0.01, rot[2] * 0.01))

            # Apply offset to vertices in this group
            for vi in range(vertex_count):
                try:
                    weight = vg.weight(vi)
                except RuntimeError:
                    continue
                if weight > 0.0:
                    sk.data[vi].co += offset * weight
                    vertices_modified += 1

    elif mode == "damage":
        damage_intensity = float(params.get("damage_intensity", 0.5))

        sk = obj.shape_key_add(name=shape_key_name)
        vertex_count = len(obj.data.vertices)

        # Damage: random-ish displacement scaled by convexity
        import hashlib
        import random

        # Use deterministic seed instead of Python's salted hash
        seed = int(hashlib.md5(shape_key_name.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        for vi, vert in enumerate(obj.data.vertices):
            # Use normal direction and random magnitude
            normal = vert.normal
            magnitude = rng.gauss(0, damage_intensity * 0.01)

            # Scale by convexity (outer vertices displace more)
            dist_from_center = vert.co.length
            convexity_scale = min(dist_from_center * 2, 1.5)

            displacement = Vector(normal) * magnitude * convexity_scale
            if displacement.length > 0.0001:
                sk.data[vi].co += displacement
                vertices_modified += 1

    elif mode == "custom":
        vertex_offsets = params.get("vertex_offsets", {})
        validation = _validate_shape_key_params(shape_key_name, vertex_offsets)
        if not validation["valid"]:
            raise ValueError(
                f"Invalid shape key params: {'; '.join(validation['errors'])}"
            )

        sk = obj.shape_key_add(name=shape_key_name)
        for idx_str, offset in vertex_offsets.items():
            idx = int(idx_str) if isinstance(idx_str, str) else idx_str
            if 0 <= idx < len(sk.data):
                sk.data[idx].co += Vector(offset)
                vertices_modified += 1
    else:
        raise ValueError(f"Invalid mode: '{mode}'. Must be 'expression', 'damage', or 'custom'")

    total_shape_keys = len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0

    return {
        "shape_key": shape_key_name,
        "vertices_modified": vertices_modified,
        "total_shape_keys": total_shape_keys,
    }
