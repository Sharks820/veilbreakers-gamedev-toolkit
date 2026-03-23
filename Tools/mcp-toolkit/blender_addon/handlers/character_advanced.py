"""Advanced character systems: DNA blending, cloth collision proxies, strand hair, body morphs.

Pure-logic module (NO bpy imports). Provides:
- handle_dna_blend: Morph between character archetypes for unique faces/bodies
- handle_cloth_collision_proxy: Generate simplified collision proxy meshes
- handle_hair_strands: Generate strand-based hair curves and card meshes
- handle_facial_setup: Full facial articulation bone/driver definitions
- handle_body_morph: Parametric body morph controls

Gaps covered: #57 (DNA blending), #58 (cloth collision), #59 (strand hair),
#60 (facial articulation), #61 (body morphs).

All functions return pure data (vertices, faces, bone specs, etc.).
Quality target: AAA character customization (FromSoftware / CD Projekt quality).
"""

from __future__ import annotations

import math
import random
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]
MeshSpec = dict[str, Any]

# ---------------------------------------------------------------------------
# Valid enumeration sets
# ---------------------------------------------------------------------------

VALID_HAIR_STYLES: frozenset = frozenset({
    "straight", "wavy", "curly", "braided", "dreadlocks", "ponytail",
})

VALID_MORPH_NAMES: frozenset = frozenset({
    "muscular", "heavy", "gaunt", "tall", "short", "broad_shoulders",
    "narrow_waist", "long_arms", "barrel_chest", "pear_shaped", "athletic",
    "elderly_posture", "pregnancy", "scarred_torso", "battle_damaged",
})

VALID_COLLISION_TYPES: frozenset = frozenset({
    "convex_hull", "capsule", "box", "sphere",
})

VALID_FACIAL_LEVELS: frozenset = frozenset({
    "basic", "standard", "full",
})

VALID_BODY_PARTS: frozenset = frozenset({
    "torso", "upper_arm_L", "upper_arm_R", "thigh_L", "thigh_R",
    "lower_arm_L", "lower_arm_R", "shin_L", "shin_R", "head", "full_body",
})

# ---------------------------------------------------------------------------
# Gap #57: Face morph target definitions
# ---------------------------------------------------------------------------
# Each morph target defines a set of vertex manipulation rules.
# For face morphs, we use a parametric region system: vertices are selected
# by proximity to anatomical landmarks, then displaced along specified axes.
# The delta magnitudes are calibrated for a standard head mesh (radius ~0.1m).

FACE_MORPH_TARGETS: dict[str, dict[str, Any]] = {
    "jaw_width": {
        "description": "Wider/narrower jaw",
        "region_center": (0.0, -0.04, -0.06),
        "region_radius": 0.06,
        "axis": "X",  # displace outward on X
        "mode": "symmetric_expand",  # both sides move away from center
        "magnitude": 0.015,  # max displacement at weight=1
        "falloff": "smooth",  # smooth falloff from region center
    },
    "brow_height": {
        "description": "Higher/lower brow ridge",
        "region_center": (0.0, 0.06, 0.06),
        "region_radius": 0.04,
        "axis": "Z",
        "mode": "directional",
        "magnitude": 0.012,
        "falloff": "smooth",
    },
    "nose_length": {
        "description": "Longer/shorter nose",
        "region_center": (0.0, 0.07, 0.02),
        "region_radius": 0.025,
        "axis": "Y",  # nose extends forward
        "mode": "directional",
        "magnitude": 0.015,
        "falloff": "linear",
    },
    "cheekbone_prominence": {
        "description": "More/less prominent cheekbones",
        "region_center": (0.0, 0.03, 0.02),
        "region_radius": 0.035,
        "axis": "XY",  # outward + slightly forward
        "mode": "symmetric_expand",
        "magnitude": 0.010,
        "falloff": "smooth",
    },
    "chin_strength": {
        "description": "Stronger/weaker chin projection",
        "region_center": (0.0, -0.08, -0.02),
        "region_radius": 0.03,
        "axis": "Y",
        "mode": "directional",
        "magnitude": 0.012,
        "falloff": "smooth",
    },
    "eye_spacing": {
        "description": "Wider/closer eye spacing",
        "region_center": (0.0, 0.05, 0.05),
        "region_radius": 0.035,
        "axis": "X",
        "mode": "symmetric_expand",
        "magnitude": 0.008,
        "falloff": "smooth",
    },
    "forehead_slope": {
        "description": "More/less sloping forehead",
        "region_center": (0.0, 0.08, 0.04),
        "region_radius": 0.04,
        "axis": "YZ",  # backward + upward
        "mode": "directional",
        "magnitude": 0.010,
        "falloff": "smooth",
    },
    "lip_fullness": {
        "description": "Fuller/thinner lips",
        "region_center": (0.0, 0.05, -0.04),
        "region_radius": 0.025,
        "axis": "Y",
        "mode": "directional",
        "magnitude": 0.006,
        "falloff": "smooth",
    },
}

# ---------------------------------------------------------------------------
# Gap #61: Body morph target definitions
# ---------------------------------------------------------------------------
# Body morphs affect vertices in specific anatomical regions.
# Each morph defines which body regions are affected and how.

BODY_MORPH_TARGETS: dict[str, dict[str, Any]] = {
    "muscular": {
        "description": "Increased muscle mass across body",
        "regions": {
            "torso": {"mode": "radial_expand", "magnitude": 0.025, "focus": "lateral"},
            "upper_arm": {"mode": "radial_expand", "magnitude": 0.018},
            "lower_arm": {"mode": "radial_expand", "magnitude": 0.012},
            "thigh": {"mode": "radial_expand", "magnitude": 0.020},
            "shin": {"mode": "radial_expand", "magnitude": 0.010},
            "chest": {"mode": "radial_expand", "magnitude": 0.022, "focus": "anterior"},
            "shoulder": {"mode": "radial_expand", "magnitude": 0.020, "focus": "lateral"},
        },
    },
    "heavy": {
        "description": "Increased body fat distribution",
        "regions": {
            "torso": {"mode": "radial_expand", "magnitude": 0.040, "focus": "anterior"},
            "belly": {"mode": "directional", "axis": "Y", "magnitude": 0.045},
            "thigh": {"mode": "radial_expand", "magnitude": 0.025},
            "upper_arm": {"mode": "radial_expand", "magnitude": 0.015},
            "chin": {"mode": "directional", "axis": "Y", "magnitude": 0.010},
            "hip": {"mode": "radial_expand", "magnitude": 0.030, "focus": "lateral"},
        },
    },
    "gaunt": {
        "description": "Emaciated, prominent bone structure",
        "regions": {
            "torso": {"mode": "radial_shrink", "magnitude": 0.020},
            "upper_arm": {"mode": "radial_shrink", "magnitude": 0.012},
            "lower_arm": {"mode": "radial_shrink", "magnitude": 0.008},
            "thigh": {"mode": "radial_shrink", "magnitude": 0.015},
            "shin": {"mode": "radial_shrink", "magnitude": 0.008},
            "cheek": {"mode": "radial_shrink", "magnitude": 0.006},
            "belly": {"mode": "directional", "axis": "Y", "magnitude": -0.015},
        },
    },
    "tall": {
        "description": "Proportional height increase",
        "regions": {
            "full_body": {"mode": "scale_z", "magnitude": 0.08},
            "torso": {"mode": "scale_z", "magnitude": 0.03},
            "thigh": {"mode": "scale_z", "magnitude": 0.025},
            "shin": {"mode": "scale_z", "magnitude": 0.025},
        },
    },
    "short": {
        "description": "Proportional height decrease",
        "regions": {
            "full_body": {"mode": "scale_z", "magnitude": -0.06},
            "torso": {"mode": "scale_z", "magnitude": -0.02},
            "thigh": {"mode": "scale_z", "magnitude": -0.02},
            "shin": {"mode": "scale_z", "magnitude": -0.02},
        },
    },
    "broad_shoulders": {
        "description": "Wider shoulder span",
        "regions": {
            "shoulder": {"mode": "symmetric_expand", "axis": "X", "magnitude": 0.030},
            "upper_arm": {"mode": "translate", "axis": "X", "magnitude": 0.015},
            "chest": {"mode": "radial_expand", "magnitude": 0.010, "focus": "lateral"},
        },
    },
    "narrow_waist": {
        "description": "Slimmer waist/core area",
        "regions": {
            "waist": {"mode": "radial_shrink", "magnitude": 0.020},
            "belly": {"mode": "radial_shrink", "magnitude": 0.015},
            "hip": {"mode": "radial_shrink", "magnitude": 0.010},
        },
    },
    "long_arms": {
        "description": "Proportionally longer arms",
        "regions": {
            "upper_arm": {"mode": "scale_z", "magnitude": 0.020},
            "lower_arm": {"mode": "scale_z", "magnitude": 0.025},
            "hand": {"mode": "translate", "axis": "Z", "magnitude": -0.020},
        },
    },
    "barrel_chest": {
        "description": "Expanded rib cage / chest volume",
        "regions": {
            "chest": {"mode": "radial_expand", "magnitude": 0.030},
            "torso": {"mode": "radial_expand", "magnitude": 0.015, "focus": "upper"},
            "shoulder": {"mode": "symmetric_expand", "axis": "X", "magnitude": 0.010},
        },
    },
    "pear_shaped": {
        "description": "Wider hips relative to shoulders",
        "regions": {
            "hip": {"mode": "symmetric_expand", "axis": "X", "magnitude": 0.025},
            "thigh": {"mode": "radial_expand", "magnitude": 0.015},
            "waist": {"mode": "radial_expand", "magnitude": 0.010, "focus": "lateral"},
            "shoulder": {"mode": "radial_shrink", "magnitude": 0.005},
        },
    },
    "athletic": {
        "description": "Lean, toned build",
        "regions": {
            "torso": {"mode": "radial_expand", "magnitude": 0.008},
            "chest": {"mode": "radial_expand", "magnitude": 0.012},
            "upper_arm": {"mode": "radial_expand", "magnitude": 0.008},
            "thigh": {"mode": "radial_expand", "magnitude": 0.010},
            "waist": {"mode": "radial_shrink", "magnitude": 0.010},
        },
    },
    "elderly_posture": {
        "description": "Stooped posture, reduced muscle mass",
        "regions": {
            "upper_torso": {"mode": "directional", "axis": "Y", "magnitude": 0.015},
            "shoulder": {"mode": "directional", "axis": "Z", "magnitude": -0.010},
            "torso": {"mode": "radial_shrink", "magnitude": 0.008},
            "upper_arm": {"mode": "radial_shrink", "magnitude": 0.006},
            "thigh": {"mode": "radial_shrink", "magnitude": 0.008},
        },
    },
    "pregnancy": {
        "description": "Abdominal expansion",
        "regions": {
            "belly": {"mode": "directional", "axis": "Y", "magnitude": 0.060},
            "waist": {"mode": "radial_expand", "magnitude": 0.020},
            "hip": {"mode": "radial_expand", "magnitude": 0.010},
        },
    },
    "scarred_torso": {
        "description": "Battle-scarred torso surface disruption",
        "regions": {
            "torso": {"mode": "noise", "magnitude": 0.004, "frequency": 8.0},
            "chest": {"mode": "noise", "magnitude": 0.003, "frequency": 10.0},
        },
    },
    "battle_damaged": {
        "description": "Heavy scarring across body",
        "regions": {
            "torso": {"mode": "noise", "magnitude": 0.005, "frequency": 6.0},
            "upper_arm": {"mode": "noise", "magnitude": 0.003, "frequency": 8.0},
            "thigh": {"mode": "noise", "magnitude": 0.003, "frequency": 7.0},
            "face": {"mode": "noise", "magnitude": 0.002, "frequency": 12.0},
        },
    },
}

# ---------------------------------------------------------------------------
# Gap #60: Facial landmark definitions
# ---------------------------------------------------------------------------
# Positions are relative to head center (0, 0, 0), Z-up, Y-forward.
# Head radius is approximately 0.10m.

FACIAL_LANDMARKS: dict[str, dict[str, Any]] = {
    # --- Basic level (10 bones) ---
    "jaw": {
        "pos": (0.0, 0.02, -0.05),
        "axis": "X",
        "range": (-0.1, 0.5),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.04,
    },
    "upper_lip": {
        "pos": (0.0, 0.065, -0.025),
        "axis": "Y",
        "range": (-0.02, 0.02),
        "level": "basic",
        "parent": "jaw",
        "vertex_group_radius": 0.015,
    },
    "lower_lip": {
        "pos": (0.0, 0.055, -0.04),
        "axis": "Y",
        "range": (-0.02, 0.02),
        "level": "basic",
        "parent": "jaw",
        "vertex_group_radius": 0.015,
    },
    "brow_L": {
        "pos": (-0.032, 0.045, 0.055),
        "axis": "Z",
        "range": (-0.02, 0.03),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.02,
    },
    "brow_R": {
        "pos": (0.032, 0.045, 0.055),
        "axis": "Z",
        "range": (-0.02, 0.03),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.02,
    },
    "eyelid_upper_L": {
        "pos": (-0.032, 0.055, 0.045),
        "axis": "Z",
        "range": (-0.005, 0.015),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "eyelid_upper_R": {
        "pos": (0.032, 0.055, 0.045),
        "axis": "Z",
        "range": (-0.005, 0.015),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "eyelid_lower_L": {
        "pos": (-0.032, 0.052, 0.038),
        "axis": "Z",
        "range": (-0.01, 0.005),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "eyelid_lower_R": {
        "pos": (0.032, 0.052, 0.038),
        "axis": "Z",
        "range": (-0.01, 0.005),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "nose": {
        "pos": (0.0, 0.075, 0.01),
        "axis": "Y",
        "range": (-0.005, 0.01),
        "level": "basic",
        "parent": "head",
        "vertex_group_radius": 0.018,
    },
    # --- Standard level (adds 15 bones = 25 total) ---
    "cheek_L": {
        "pos": (-0.045, 0.035, 0.01),
        "axis": "XY",
        "range": (-0.01, 0.015),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.025,
    },
    "cheek_R": {
        "pos": (0.045, 0.035, 0.01),
        "axis": "XY",
        "range": (-0.01, 0.015),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.025,
    },
    "lip_corner_L": {
        "pos": (-0.022, 0.055, -0.03),
        "axis": "XY",
        "range": (-0.01, 0.015),
        "level": "standard",
        "parent": "jaw",
        "vertex_group_radius": 0.010,
    },
    "lip_corner_R": {
        "pos": (0.022, 0.055, -0.03),
        "axis": "XY",
        "range": (-0.01, 0.015),
        "level": "standard",
        "parent": "jaw",
        "vertex_group_radius": 0.010,
    },
    "nostril_L": {
        "pos": (-0.012, 0.070, 0.0),
        "axis": "X",
        "range": (-0.005, 0.008),
        "level": "standard",
        "parent": "nose",
        "vertex_group_radius": 0.008,
    },
    "nostril_R": {
        "pos": (0.012, 0.070, 0.0),
        "axis": "X",
        "range": (-0.005, 0.008),
        "level": "standard",
        "parent": "nose",
        "vertex_group_radius": 0.008,
    },
    "chin": {
        "pos": (0.0, 0.035, -0.065),
        "axis": "Y",
        "range": (-0.01, 0.01),
        "level": "standard",
        "parent": "jaw",
        "vertex_group_radius": 0.020,
    },
    "tongue": {
        "pos": (0.0, 0.03, -0.03),
        "axis": "YZ",
        "range": (-0.02, 0.03),
        "level": "standard",
        "parent": "jaw",
        "vertex_group_radius": 0.015,
    },
    "ear_L": {
        "pos": (-0.065, 0.0, 0.02),
        "axis": "X",
        "range": (-0.005, 0.01),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.020,
    },
    "ear_R": {
        "pos": (0.065, 0.0, 0.02),
        "axis": "X",
        "range": (-0.005, 0.01),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.020,
    },
    "nasolabial_L": {
        "pos": (-0.025, 0.055, -0.01),
        "axis": "Y",
        "range": (-0.005, 0.008),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "nasolabial_R": {
        "pos": (0.025, 0.055, -0.01),
        "axis": "Y",
        "range": (-0.005, 0.008),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "jaw_hinge_L": {
        "pos": (-0.055, 0.005, -0.01),
        "axis": "X",
        "range": (-0.05, 0.1),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.018,
    },
    "jaw_hinge_R": {
        "pos": (0.055, 0.005, -0.01),
        "axis": "X",
        "range": (-0.05, 0.1),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.018,
    },
    "neck_base": {
        "pos": (0.0, -0.02, -0.06),
        "axis": "XZ",
        "range": (-0.02, 0.02),
        "level": "standard",
        "parent": "head",
        "vertex_group_radius": 0.025,
    },
    # --- Full level (adds 25+ bones = 50+ total) ---
    "lip_upper_L": {
        "pos": (-0.010, 0.065, -0.025),
        "axis": "Y",
        "range": (-0.005, 0.005),
        "level": "full",
        "parent": "upper_lip",
        "vertex_group_radius": 0.008,
    },
    "lip_upper_R": {
        "pos": (0.010, 0.065, -0.025),
        "axis": "Y",
        "range": (-0.005, 0.005),
        "level": "full",
        "parent": "upper_lip",
        "vertex_group_radius": 0.008,
    },
    "lip_upper_mid": {
        "pos": (0.0, 0.068, -0.022),
        "axis": "Y",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "upper_lip",
        "vertex_group_radius": 0.006,
    },
    "lip_lower_L": {
        "pos": (-0.010, 0.055, -0.038),
        "axis": "Y",
        "range": (-0.005, 0.005),
        "level": "full",
        "parent": "lower_lip",
        "vertex_group_radius": 0.008,
    },
    "lip_lower_R": {
        "pos": (0.010, 0.055, -0.038),
        "axis": "Y",
        "range": (-0.005, 0.005),
        "level": "full",
        "parent": "lower_lip",
        "vertex_group_radius": 0.008,
    },
    "lip_lower_mid": {
        "pos": (0.0, 0.053, -0.04),
        "axis": "Y",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "lower_lip",
        "vertex_group_radius": 0.006,
    },
    "wrinkle_forehead_L": {
        "pos": (-0.020, 0.04, 0.075),
        "axis": "Z",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "brow_L",
        "vertex_group_radius": 0.015,
    },
    "wrinkle_forehead_R": {
        "pos": (0.020, 0.04, 0.075),
        "axis": "Z",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "brow_R",
        "vertex_group_radius": 0.015,
    },
    "wrinkle_forehead_mid": {
        "pos": (0.0, 0.04, 0.078),
        "axis": "Z",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "eye_aim_L": {
        "pos": (-0.032, 0.10, 0.042),
        "axis": "YZ",
        "range": (-0.5, 0.5),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.0,
    },
    "eye_aim_R": {
        "pos": (0.032, 0.10, 0.042),
        "axis": "YZ",
        "range": (-0.5, 0.5),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.0,
    },
    "squint_L": {
        "pos": (-0.040, 0.050, 0.035),
        "axis": "Z",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "squint_R": {
        "pos": (0.040, 0.050, 0.035),
        "axis": "Z",
        "range": (-0.003, 0.005),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.012,
    },
    "teeth_upper": {
        "pos": (0.0, 0.055, -0.02),
        "axis": "Z",
        "range": (0.0, 0.0),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.0,
    },
    "teeth_lower": {
        "pos": (0.0, 0.045, -0.035),
        "axis": "Z",
        "range": (0.0, 0.0),
        "level": "full",
        "parent": "jaw",
        "vertex_group_radius": 0.0,
    },
    "tongue_tip": {
        "pos": (0.0, 0.05, -0.025),
        "axis": "YZ",
        "range": (-0.01, 0.02),
        "level": "full",
        "parent": "tongue",
        "vertex_group_radius": 0.008,
    },
    "tongue_mid": {
        "pos": (0.0, 0.04, -0.028),
        "axis": "YZ",
        "range": (-0.01, 0.015),
        "level": "full",
        "parent": "tongue",
        "vertex_group_radius": 0.010,
    },
    "brow_inner_L": {
        "pos": (-0.015, 0.050, 0.058),
        "axis": "Z",
        "range": (-0.01, 0.02),
        "level": "full",
        "parent": "brow_L",
        "vertex_group_radius": 0.010,
    },
    "brow_inner_R": {
        "pos": (0.015, 0.050, 0.058),
        "axis": "Z",
        "range": (-0.01, 0.02),
        "level": "full",
        "parent": "brow_R",
        "vertex_group_radius": 0.010,
    },
    "brow_outer_L": {
        "pos": (-0.048, 0.040, 0.048),
        "axis": "Z",
        "range": (-0.01, 0.02),
        "level": "full",
        "parent": "brow_L",
        "vertex_group_radius": 0.010,
    },
    "brow_outer_R": {
        "pos": (0.048, 0.040, 0.048),
        "axis": "Z",
        "range": (-0.01, 0.02),
        "level": "full",
        "parent": "brow_R",
        "vertex_group_radius": 0.010,
    },
    "crow_feet_L": {
        "pos": (-0.050, 0.048, 0.038),
        "axis": "XZ",
        "range": (-0.002, 0.004),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "crow_feet_R": {
        "pos": (0.050, 0.048, 0.038),
        "axis": "XZ",
        "range": (-0.002, 0.004),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "sneer_L": {
        "pos": (-0.018, 0.060, -0.005),
        "axis": "Y",
        "range": (-0.003, 0.008),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "sneer_R": {
        "pos": (0.018, 0.060, -0.005),
        "axis": "Y",
        "range": (-0.003, 0.008),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.010,
    },
    "dimple_L": {
        "pos": (-0.030, 0.045, -0.02),
        "axis": "Y",
        "range": (-0.005, 0.0),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.008,
    },
    "dimple_R": {
        "pos": (0.030, 0.045, -0.02),
        "axis": "Y",
        "range": (-0.005, 0.0),
        "level": "full",
        "parent": "head",
        "vertex_group_radius": 0.008,
    },
}


# ===========================================================================
# Utility functions
# ===========================================================================

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value to [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _vec_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _vec_len(v: Vec3) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _vec_dist(a: Vec3, b: Vec3) -> float:
    return _vec_len(_vec_sub(a, b))


def _vec_normalize(v: Vec3) -> Vec3:
    length = _vec_len(v)
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _vec_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _smooth_falloff(distance: float, radius: float) -> float:
    """Smooth hermite falloff: 1 at center, 0 at radius."""
    if radius <= 0:
        return 0.0
    t = min(distance / radius, 1.0)
    # Smoothstep inverse: strongest at center
    return 1.0 - (3.0 * t * t - 2.0 * t * t * t)


def _linear_falloff(distance: float, radius: float) -> float:
    """Linear falloff: 1 at center, 0 at radius."""
    if radius <= 0:
        return 0.0
    return max(0.0, 1.0 - distance / radius)


def _poisson_disk_2d(
    positions: list[Vec3],
    count: int,
    min_distance: float,
    rng: random.Random,
) -> list[int]:
    """Select a subset of positions using Poisson disk sampling.

    Returns indices into the positions list.
    """
    if not positions:
        return []
    if count >= len(positions):
        return list(range(len(positions)))

    # Shuffle candidates
    indices = list(range(len(positions)))
    rng.shuffle(indices)

    selected: list[int] = []
    for idx in indices:
        if len(selected) >= count:
            break
        pos = positions[idx]
        too_close = False
        for sel_idx in selected:
            sel_pos = positions[sel_idx]
            dist = math.sqrt(
                (pos[0] - sel_pos[0]) ** 2
                + (pos[1] - sel_pos[1]) ** 2
                + (pos[2] - sel_pos[2]) ** 2
            )
            if dist < min_distance:
                too_close = True
                break
        if not too_close:
            selected.append(idx)

    # If Poisson disk rejected too many, fill remaining randomly
    if len(selected) < count:
        remaining = [i for i in indices if i not in set(selected)]
        rng.shuffle(remaining)
        selected.extend(remaining[: count - len(selected)])

    return selected[:count]


# ===========================================================================
# Gap #57: DNA / Mesh Blending
# ===========================================================================

def blend_vertices(
    base: list[list[float]],
    morph_targets: dict[str, list[list[float]]],
    weights: dict[str, float],
) -> list[list[float]]:
    """Apply weighted morph targets to base vertex positions.

    For each vertex i:
        final_pos[i] = base[i] + sum(morph_targets[name][i] * clamp(weights[name]))

    Args:
        base: List of [x, y, z] base vertex positions.
        morph_targets: Dict mapping target names to lists of [dx, dy, dz] deltas.
        weights: Dict mapping target names to blend weights (clamped 0-1).

    Returns:
        List of [x, y, z] blended vertex positions.
    """
    if not base:
        return []

    vert_count = len(base)
    # Start with a deep copy of base
    result = [[v[0], v[1], v[2]] for v in base]

    for target_name, weight in weights.items():
        w = _clamp(weight, 0.0, 1.0)
        if w < 1e-8:
            continue
        deltas = morph_targets.get(target_name)
        if deltas is None:
            continue
        # Deltas list may be shorter than base (partial morph targets)
        for i in range(min(vert_count, len(deltas))):
            d = deltas[i]
            result[i][0] += d[0] * w
            result[i][1] += d[1] * w
            result[i][2] += d[2] * w

    return result


def _generate_face_morph_deltas(
    vertices: list[list[float]],
    morph_name: str,
    head_center: Vec3 = (0.0, 0.0, 0.0),
) -> list[list[float]]:
    """Generate per-vertex deltas for a face morph target.

    Uses the FACE_MORPH_TARGETS definitions to compute anatomically
    correct vertex displacements based on proximity to facial landmarks.
    """
    target = FACE_MORPH_TARGETS.get(morph_name)
    if target is None:
        return [[0.0, 0.0, 0.0] for _ in vertices]

    center = target["region_center"]
    radius = target["region_radius"]
    axis = target["axis"]
    mode = target["mode"]
    magnitude = target["magnitude"]
    falloff_type = target.get("falloff", "smooth")

    abs_center = (
        center[0] + head_center[0],
        center[1] + head_center[1],
        center[2] + head_center[2],
    )

    falloff_fn = _smooth_falloff if falloff_type == "smooth" else _linear_falloff
    deltas: list[list[float]] = []

    for v in vertices:
        vt = (v[0], v[1], v[2])
        dist = _vec_dist(vt, abs_center)
        influence = falloff_fn(dist, radius)

        if influence < 1e-6:
            deltas.append([0.0, 0.0, 0.0])
            continue

        dx, dy, dz = 0.0, 0.0, 0.0

        if mode == "symmetric_expand":
            # Move vertices away from the center axis (X=0 plane)
            sign_x = 1.0 if vt[0] >= 0 else -1.0
            if "X" in axis:
                dx = sign_x * magnitude * influence
            if "Y" in axis:
                # Forward component scaled by distance from centerline
                dy = magnitude * 0.5 * influence
        elif mode == "directional":
            if "X" in axis:
                dx = magnitude * influence
            if "Y" in axis:
                dy = magnitude * influence
            if "Z" in axis:
                dz = magnitude * influence

        deltas.append([dx, dy, dz])

    return deltas


def handle_dna_blend(params: dict) -> dict:
    """Morph between character archetypes for unique faces/bodies.

    Supports multiple simultaneous morphs combined additively.
    Weights are clamped to 0-1.

    Params:
        base_mesh_verts: list of [x,y,z] base character vertices
        morph_targets: dict of {target_name: list of [dx,dy,dz] deltas}
        blend_weights: dict of {target_name: float 0-1}

    Returns:
        Dict with blended vertex positions and metadata.
    """
    base_verts = params.get("base_mesh_verts", [])
    morph_targets = params.get("morph_targets", {})
    blend_weights = params.get("blend_weights", {})

    if not base_verts:
        return {"error": "base_mesh_verts is required and must not be empty"}

    # Validate and clamp weights
    clamped_weights: dict[str, float] = {}
    for name, w in blend_weights.items():
        clamped_weights[name] = _clamp(float(w), 0.0, 1.0)

    blended = blend_vertices(base_verts, morph_targets, clamped_weights)

    # Compute displacement statistics
    total_displacement = 0.0
    max_displacement = 0.0
    for i, (bv, rv) in enumerate(zip(base_verts, blended)):
        d = math.sqrt(
            (rv[0] - bv[0]) ** 2 + (rv[1] - bv[1]) ** 2 + (rv[2] - bv[2]) ** 2
        )
        total_displacement += d
        max_displacement = max(max_displacement, d)

    avg_displacement = total_displacement / len(base_verts) if base_verts else 0.0

    return {
        "vertices": blended,
        "vertex_count": len(blended),
        "weights_applied": clamped_weights,
        "active_targets": [n for n, w in clamped_weights.items() if w > 1e-6],
        "stats": {
            "avg_displacement": round(avg_displacement, 6),
            "max_displacement": round(max_displacement, 6),
        },
    }


# ===========================================================================
# Gap #58: Cloth Collision Proxy Volumes
# ===========================================================================

def compute_collision_capsule(vertices: list[list[float]], axis: str = "Z") -> dict:
    """Compute a capsule collision proxy from a vertex cloud.

    The capsule is the minimum-enclosing capsule along the specified axis.
    A capsule = cylinder with hemisphere caps.

    Args:
        vertices: List of [x, y, z] positions.
        axis: Primary axis ('X', 'Y', or 'Z').

    Returns:
        Dict with center, half_height, radius, axis, cap_top, cap_bottom.
    """
    if not vertices:
        return {"error": "Empty vertex list"}

    axis_idx = {"X": 0, "Y": 1, "Z": 2}.get(axis.upper(), 2)
    other_axes = [i for i in range(3) if i != axis_idx]

    # Find axis extent
    axis_vals = [v[axis_idx] for v in vertices]
    axis_min = min(axis_vals)
    axis_max = max(axis_vals)
    half_height = (axis_max - axis_min) / 2.0
    center_axis = (axis_min + axis_max) / 2.0

    # Find max radial distance from the central axis
    center_other = [0.0, 0.0]
    for oi, ax in enumerate(other_axes):
        vals = [v[ax] for v in vertices]
        center_other[oi] = (min(vals) + max(vals)) / 2.0

    max_radius = 0.0
    for v in vertices:
        r_sq = sum((v[ax] - center_other[oi]) ** 2 for oi, ax in enumerate(other_axes))
        max_radius = max(max_radius, math.sqrt(r_sq))

    # Build center position
    center = [0.0, 0.0, 0.0]
    center[axis_idx] = center_axis
    for oi, ax in enumerate(other_axes):
        center[ax] = center_other[oi]

    # Capsule height is the cylinder portion (total - 2*radius for caps)
    cylinder_half_height = max(0.0, half_height - max_radius)

    cap_top = list(center)
    cap_top[axis_idx] = center_axis + cylinder_half_height
    cap_bottom = list(center)
    cap_bottom[axis_idx] = center_axis - cylinder_half_height

    return {
        "type": "capsule",
        "center": tuple(center),
        "half_height": half_height,
        "radius": max_radius,
        "cylinder_half_height": cylinder_half_height,
        "axis": axis.upper(),
        "cap_top": tuple(cap_top),
        "cap_bottom": tuple(cap_bottom),
    }


def compute_collision_box(vertices: list[list[float]], margin: float = 0.01) -> dict:
    """Compute an axis-aligned bounding box proxy.

    Args:
        vertices: List of [x, y, z] positions.
        margin: Amount to inflate the box on each side.

    Returns:
        Dict with min_corner, max_corner, center, half_extents, vertices, faces.
    """
    if not vertices:
        return {"error": "Empty vertex list"}

    margin = max(0.0, margin)

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    min_c = [min(xs) - margin, min(ys) - margin, min(zs) - margin]
    max_c = [max(xs) + margin, max(ys) + margin, max(zs) + margin]

    center = [(min_c[i] + max_c[i]) / 2.0 for i in range(3)]
    half_ext = [(max_c[i] - min_c[i]) / 2.0 for i in range(3)]

    # Generate box mesh vertices (8 corners)
    x0, y0, z0 = min_c
    x1, y1, z1 = max_c
    box_verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    box_faces = [
        (0, 1, 2, 3),  # bottom
        (4, 7, 6, 5),  # top
        (0, 4, 5, 1),  # front
        (2, 6, 7, 3),  # back
        (0, 3, 7, 4),  # left
        (1, 5, 6, 2),  # right
    ]

    return {
        "type": "box",
        "min_corner": tuple(min_c),
        "max_corner": tuple(max_c),
        "center": tuple(center),
        "half_extents": tuple(half_ext),
        "vertices": box_verts,
        "faces": box_faces,
        "margin": margin,
    }


def _compute_collision_sphere(vertices: list[list[float]], margin: float = 0.01) -> dict:
    """Compute a bounding sphere proxy."""
    if not vertices:
        return {"error": "Empty vertex list"}

    # Centroid
    n = len(vertices)
    cx = sum(v[0] for v in vertices) / n
    cy = sum(v[1] for v in vertices) / n
    cz = sum(v[2] for v in vertices) / n

    # Max distance from centroid
    max_r = 0.0
    for v in vertices:
        r = math.sqrt((v[0] - cx) ** 2 + (v[1] - cy) ** 2 + (v[2] - cz) ** 2)
        max_r = max(max_r, r)

    return {
        "type": "sphere",
        "center": (cx, cy, cz),
        "radius": max_r + margin,
        "margin": margin,
    }


def _simplify_convex_hull(vertices: list[list[float]], max_faces: int) -> dict:
    """Compute a simplified convex hull proxy.

    Uses an iterative vertex selection approach: pick the 6 extremal vertices
    (min/max on each axis), then iteratively add the vertex farthest from the
    current hull approximation.
    """
    if not vertices or max_faces < 4:
        return {"error": "Need vertices and max_faces >= 4"}

    n = len(vertices)
    if n <= 4:
        # Trivial case: all vertices form the hull
        hull_verts = [tuple(v) for v in vertices]
        hull_faces = [(0, 1, 2)] if n == 3 else [(0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2)]
        return {
            "type": "convex_hull",
            "vertices": hull_verts,
            "faces": hull_faces,
            "vertex_count": len(hull_verts),
            "face_count": len(hull_faces),
        }

    # Start with extremal vertices
    selected_indices: list[int] = []
    for axis in range(3):
        min_idx = min(range(n), key=lambda i: vertices[i][axis])
        max_idx = max(range(n), key=lambda i: vertices[i][axis])
        if min_idx not in selected_indices:
            selected_indices.append(min_idx)
        if max_idx not in selected_indices:
            selected_indices.append(max_idx)

    # Target vertex count based on max_faces (Euler: V - E + F = 2, E = 3V - 6, F = 2V - 4)
    target_verts = min(n, max(4, (max_faces + 4) // 2))

    # Iteratively add farthest vertex from centroid of selected
    while len(selected_indices) < target_verts:
        sel_set = set(selected_indices)
        cx = sum(vertices[i][0] for i in selected_indices) / len(selected_indices)
        cy = sum(vertices[i][1] for i in selected_indices) / len(selected_indices)
        cz = sum(vertices[i][2] for i in selected_indices) / len(selected_indices)

        best_idx = -1
        best_dist = -1.0
        for i in range(n):
            if i in sel_set:
                continue
            d = (
                (vertices[i][0] - cx) ** 2
                + (vertices[i][1] - cy) ** 2
                + (vertices[i][2] - cz) ** 2
            )
            if d > best_dist:
                best_dist = d
                best_idx = i
        if best_idx < 0:
            break
        selected_indices.append(best_idx)

    hull_verts = [tuple(vertices[i]) for i in selected_indices]

    # Generate triangulated faces via fan from centroid projection
    # This is a simplified approach; real convex hull would use quickhull
    nv = len(hull_verts)
    hull_faces: list[tuple[int, ...]] = []
    if nv >= 3:
        # Sort vertices by angle around centroid for reasonable triangulation
        cx = sum(v[0] for v in hull_verts) / nv
        cy = sum(v[1] for v in hull_verts) / nv
        cz = sum(v[2] for v in hull_verts) / nv

        # Triangulate using fan from first vertex as simple approximation
        for i in range(1, nv - 1):
            hull_faces.append((0, i, i + 1))
        # Close with back faces
        if nv > 3:
            for i in range(1, nv - 1):
                hull_faces.append((0, i + 1, i))

    # Limit face count
    hull_faces = hull_faces[:max_faces]

    return {
        "type": "convex_hull",
        "vertices": hull_verts,
        "faces": hull_faces,
        "vertex_count": len(hull_verts),
        "face_count": len(hull_faces),
    }


# Body part bounding regions (relative to a standard 1.8m humanoid, Z-up)
_BODY_PART_BOUNDS: dict[str, dict[str, Any]] = {
    "torso": {"z_range": (0.85, 1.45), "axis": "Z"},
    "upper_arm_L": {"z_range": (1.20, 1.50), "x_range": (-0.40, -0.18), "axis": "Z"},
    "upper_arm_R": {"z_range": (1.20, 1.50), "x_range": (0.18, 0.40), "axis": "Z"},
    "thigh_L": {"z_range": (0.45, 0.85), "x_range": (-0.20, -0.02), "axis": "Z"},
    "thigh_R": {"z_range": (0.45, 0.85), "x_range": (0.02, 0.20), "axis": "Z"},
    "lower_arm_L": {"z_range": (0.95, 1.22), "x_range": (-0.50, -0.20), "axis": "Z"},
    "lower_arm_R": {"z_range": (0.95, 1.22), "x_range": (0.20, 0.50), "axis": "Z"},
    "shin_L": {"z_range": (0.05, 0.48), "x_range": (-0.18, -0.02), "axis": "Z"},
    "shin_R": {"z_range": (0.05, 0.48), "x_range": (0.02, 0.18), "axis": "Z"},
    "head": {"z_range": (1.55, 1.80), "axis": "Z"},
    "full_body": {"z_range": (0.0, 1.85), "axis": "Z"},
}


def _filter_body_part_verts(
    vertices: list[list[float]],
    faces: list,
    body_part: str,
) -> tuple[list[list[float]], list]:
    """Filter vertices belonging to a body part by bounding region."""
    bounds = _BODY_PART_BOUNDS.get(body_part)
    if bounds is None:
        return vertices, faces

    z_lo, z_hi = bounds["z_range"]
    x_range = bounds.get("x_range")

    filtered: list[list[float]] = []
    for v in vertices:
        if v[2] < z_lo or v[2] > z_hi:
            continue
        if x_range is not None and (v[0] < x_range[0] or v[0] > x_range[1]):
            continue
        filtered.append(v)

    return filtered if filtered else vertices, faces


def handle_cloth_collision_proxy(params: dict) -> dict:
    """Generate simplified collision proxy meshes for cloth simulation.

    Params:
        character_body_verts: list of [x,y,z]
        character_body_faces: list of face tuples
        body_part: 'torso' | 'upper_arm_L' | ... | 'full_body'
        proxy_type: 'convex_hull' | 'capsule' | 'box' | 'sphere'
        resolution: int (for convex hull -- max faces)
        margin: float (inflate proxy to prevent cloth clipping)

    Returns:
        Proxy mesh data + collision settings dict.
    """
    verts = params.get("character_body_verts", [])
    faces = params.get("character_body_faces", [])
    body_part = params.get("body_part", "full_body")
    proxy_type = params.get("proxy_type", "capsule")
    resolution = params.get("resolution", 32)
    margin = params.get("margin", 0.01)

    if not verts:
        return {"error": "character_body_verts is required"}
    if body_part not in VALID_BODY_PARTS:
        return {"error": f"Invalid body_part '{body_part}'. Valid: {sorted(VALID_BODY_PARTS)}"}
    if proxy_type not in VALID_COLLISION_TYPES:
        return {"error": f"Invalid proxy_type '{proxy_type}'. Valid: {sorted(VALID_COLLISION_TYPES)}"}

    # Filter vertices to body part region
    part_verts, _ = _filter_body_part_verts(verts, faces, body_part)

    # Generate proxy based on type
    if proxy_type == "capsule":
        axis = _BODY_PART_BOUNDS.get(body_part, {}).get("axis", "Z")
        proxy = compute_collision_capsule(part_verts, axis=axis)
        # Inflate by margin
        if "radius" in proxy:
            proxy["radius"] += margin
    elif proxy_type == "box":
        proxy = compute_collision_box(part_verts, margin=margin)
    elif proxy_type == "sphere":
        proxy = _compute_collision_sphere(part_verts, margin=margin)
    elif proxy_type == "convex_hull":
        proxy = _simplify_convex_hull(part_verts, max_faces=resolution)
    else:
        return {"error": f"Unknown proxy_type: {proxy_type}"}

    # Collision settings for Unity/Blender cloth sim
    collision_settings = {
        "body_part": body_part,
        "proxy_type": proxy_type,
        "friction": 0.5,
        "stickiness": 0.0,
        "damping": 0.1,
        "thickness_outer": margin,
        "thickness_inner": margin * 0.5,
    }

    return {
        "proxy": proxy,
        "collision_settings": collision_settings,
        "source_vertex_count": len(part_verts),
    }


# ===========================================================================
# Gap #59: Strand-Based Hair (Curves -> Cards)
# ===========================================================================

def generate_strand_curve(
    root_pos: Vec3,
    root_normal: Vec3,
    length: float,
    segments: int,
    style: str,
    gravity: float,
    seed: int,
) -> list[Vec3]:
    """Generate a single hair strand as a list of control points.

    The strand grows from root_pos in the direction of root_normal,
    then bends according to style, gravity, and randomness.

    Args:
        root_pos: Starting position on the scalp.
        root_normal: Surface normal at root (initial growth direction).
        length: Total strand length in meters.
        segments: Number of control points (including root).
        style: One of VALID_HAIR_STYLES.
        gravity: Gravity influence (0 = none, 1 = full droop).
        seed: Random seed for variation.

    Returns:
        List of (x, y, z) control points from root to tip.
    """
    rng = random.Random(seed)
    segments = max(2, segments)
    seg_len = length / (segments - 1)

    # Normalize root normal
    normal = _vec_normalize(root_normal)

    # Build a local tangent frame
    up = (0.0, 0.0, 1.0)
    if abs(normal[2]) > 0.95:
        up = (0.0, 1.0, 0.0)

    tangent = _vec_normalize(_vec_cross(normal, up))
    binormal = _vec_normalize(_vec_cross(normal, tangent))

    gravity_vec = (0.0, 0.0, -1.0)

    # Style-specific parameters
    wave_freq = 0.0
    wave_amp = 0.0
    curl_freq = 0.0
    curl_amp = 0.0
    braid_twist = 0.0

    if style == "wavy":
        wave_freq = 3.0 + rng.uniform(-0.5, 0.5)
        wave_amp = 0.012 + rng.uniform(-0.003, 0.003)
    elif style == "curly":
        curl_freq = 6.0 + rng.uniform(-1.0, 1.0)
        curl_amp = 0.018 + rng.uniform(-0.004, 0.004)
    elif style == "braided":
        braid_twist = 4.0 + rng.uniform(-0.5, 0.5)
        wave_amp = 0.008
    elif style == "dreadlocks":
        wave_freq = 1.5 + rng.uniform(-0.3, 0.3)
        wave_amp = 0.006 + rng.uniform(-0.002, 0.002)
        # Dreadlocks are thicker but less wavy, with random kinks
    elif style == "ponytail":
        # Strands converge toward a gathering point then fall
        wave_freq = 1.0
        wave_amp = 0.005

    # Per-strand random variation
    rand_offset_x = rng.uniform(-0.003, 0.003)
    rand_offset_y = rng.uniform(-0.003, 0.003)

    points: list[Vec3] = [root_pos]
    current_dir = normal

    for seg in range(1, segments):
        t = seg / (segments - 1)  # 0 to 1 from root to tip

        # Gravity influence accumulates toward tip
        gravity_strength = gravity * t * t * seg_len * 2.0

        # Style curvature
        phase = t * math.pi * 2.0
        lateral_offset_t = 0.0
        lateral_offset_b = 0.0

        if style == "wavy":
            lateral_offset_t = wave_amp * math.sin(phase * wave_freq)
        elif style == "curly":
            lateral_offset_t = curl_amp * math.sin(phase * curl_freq)
            lateral_offset_b = curl_amp * math.cos(phase * curl_freq)
        elif style == "braided":
            braid_phase = phase * braid_twist
            lateral_offset_t = wave_amp * math.sin(braid_phase)
            lateral_offset_b = wave_amp * math.cos(braid_phase)
        elif style == "dreadlocks":
            lateral_offset_t = wave_amp * math.sin(phase * wave_freq)
            # Add random kinks
            if rng.random() < 0.15:
                lateral_offset_t += rng.uniform(-0.008, 0.008)
                lateral_offset_b += rng.uniform(-0.008, 0.008)
        elif style == "ponytail":
            # Converge strands then droop
            if t < 0.3:
                # Converge phase
                lateral_offset_t *= (1.0 - t / 0.3) * 0.5
            lateral_offset_t += wave_amp * math.sin(phase * wave_freq)

        # Compose displacement
        dx = (
            current_dir[0] * seg_len
            + tangent[0] * lateral_offset_t
            + binormal[0] * lateral_offset_b
            + gravity_vec[0] * gravity_strength
            + rand_offset_x * t
        )
        dy = (
            current_dir[1] * seg_len
            + tangent[1] * lateral_offset_t
            + binormal[1] * lateral_offset_b
            + gravity_vec[1] * gravity_strength
            + rand_offset_y * t
        )
        dz = (
            current_dir[2] * seg_len
            + tangent[2] * lateral_offset_t
            + binormal[2] * lateral_offset_b
            + gravity_vec[2] * gravity_strength
        )

        prev = points[-1]
        new_point = (prev[0] + dx, prev[1] + dy, prev[2] + dz)
        points.append(new_point)

        # Gradually bend direction toward gravity
        blend = gravity * t * 0.3
        current_dir = _vec_normalize((
            current_dir[0] * (1.0 - blend) + gravity_vec[0] * blend,
            current_dir[1] * (1.0 - blend) + gravity_vec[1] * blend,
            current_dir[2] * (1.0 - blend) + gravity_vec[2] * blend,
        ))

    return points


def generate_hair_guide_strands(
    scalp_positions: list[Vec3],
    scalp_normals: list[Vec3],
    count: int,
    length: float,
    segments: int,
    style: str,
    gravity: float,
    clumping: float,
    seed: int,
) -> list[list[Vec3]]:
    """Generate guide strand control point curves.

    Distributes hair roots on the scalp using Poisson disk sampling,
    then grows each strand with style, gravity, and clumping.

    Returns:
        List of strands, each strand is a list of (x, y, z) control points.
    """
    rng = random.Random(seed)

    if not scalp_positions:
        return []

    count = max(1, count)
    segments = max(2, segments)

    # Determine minimum spacing for Poisson disk based on scalp area estimate
    # Approximate: sqrt(scalp_area / count)
    min_spacing = length * 0.05  # Rough estimate
    if count > 1 and len(scalp_positions) > 1:
        # More sophisticated: use average spacing of positions
        avg_dist = 0.0
        sample_count = min(20, len(scalp_positions))
        for i in range(sample_count):
            idx_a = rng.randint(0, len(scalp_positions) - 1)
            idx_b = rng.randint(0, len(scalp_positions) - 1)
            if idx_a != idx_b:
                avg_dist += _vec_dist(scalp_positions[idx_a], scalp_positions[idx_b])
        if sample_count > 1:
            avg_dist /= sample_count
        min_spacing = avg_dist * 0.1

    # Select root positions via Poisson disk
    root_indices = _poisson_disk_2d(scalp_positions, count, min_spacing, rng)

    # Generate guide strands
    guide_strands: list[list[Vec3]] = []
    for idx in root_indices:
        root_pos = scalp_positions[idx]
        root_normal = scalp_normals[idx] if idx < len(scalp_normals) else (0.0, 0.0, 1.0)
        strand_seed = seed + idx * 7 + 13
        strand = generate_strand_curve(
            root_pos, root_normal, length, segments, style, gravity, strand_seed
        )
        guide_strands.append(strand)

    # Apply clumping: pull strands toward their nearest guide
    if clumping > 0.01 and len(guide_strands) > 1:
        clump_weight = _clamp(clumping, 0.0, 1.0)

        # Use first N strands as guide strands (every 4th)
        guide_count = max(1, len(guide_strands) // 4)
        guide_indices = list(range(0, len(guide_strands), max(1, len(guide_strands) // guide_count)))

        for si, strand in enumerate(guide_strands):
            if si in guide_indices:
                continue  # Don't clump guide strands themselves

            # Find nearest guide strand (by root distance)
            nearest_guide_idx = min(
                guide_indices,
                key=lambda gi: _vec_dist(strand[0], guide_strands[gi][0]),
            )
            nearest_guide = guide_strands[nearest_guide_idx]

            # Blend toward guide, increasing from root to tip
            for pi in range(1, len(strand)):
                if pi >= len(nearest_guide):
                    break
                t = pi / (len(strand) - 1)
                blend = clump_weight * t * 0.6  # Max 60% pull at tips
                gp = nearest_guide[pi]
                sp = strand[pi]
                strand[pi] = (
                    sp[0] + (gp[0] - sp[0]) * blend,
                    sp[1] + (gp[1] - sp[1]) * blend,
                    sp[2] + (gp[2] - sp[2]) * blend,
                )

    return guide_strands


def strands_to_cards(strands: list[list[Vec3]], card_width: float) -> MeshSpec:
    """Convert strand curves to flat card mesh geometry.

    Each strand becomes a strip of quads. Each quad has 4 vertices:
    left-bottom, right-bottom, right-top, left-top along the strand path.

    UV mapping: V goes 0 (root) to 1 (tip), U is 0 (left) to 1 (right).

    Args:
        strands: List of strands, each a list of (x, y, z) control points.
        card_width: Width of each hair card quad.

    Returns:
        MeshSpec dict with vertices, faces, UVs.
    """
    all_verts: list[Vec3] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[Vec2] = []

    half_width = card_width / 2.0

    for strand in strands:
        if len(strand) < 2:
            continue

        base_idx = len(all_verts)
        seg_count = len(strand)

        for si, point in enumerate(strand):
            v_coord = si / (seg_count - 1)  # 0 at root, 1 at tip

            # Compute card normal (perpendicular to strand direction)
            if si < seg_count - 1:
                fwd = _vec_sub(strand[si + 1], strand[si])
            else:
                fwd = _vec_sub(strand[si], strand[si - 1])

            fwd = _vec_normalize(fwd)

            # Use world up to derive card right vector
            up = (0.0, 0.0, 1.0)
            if abs(fwd[2]) > 0.95:
                up = (0.0, 1.0, 0.0)

            right = _vec_normalize(_vec_cross(fwd, up))

            # Taper width from root to tip
            taper = 1.0 - v_coord * 0.5  # 50% taper at tip
            w = half_width * taper

            # Left and right vertices
            left = (point[0] - right[0] * w, point[1] - right[1] * w, point[2] - right[2] * w)
            right_pt = (point[0] + right[0] * w, point[1] + right[1] * w, point[2] + right[2] * w)

            all_verts.append(left)
            all_verts.append(right_pt)

            # UVs: left edge U=0, right edge U=1
            all_uvs.append((0.0, v_coord))
            all_uvs.append((1.0, v_coord))

        # Generate quad faces for this strand
        for si in range(seg_count - 1):
            v0 = base_idx + si * 2        # left bottom
            v1 = base_idx + si * 2 + 1    # right bottom
            v2 = base_idx + (si + 1) * 2 + 1  # right top
            v3 = base_idx + (si + 1) * 2  # left top
            all_faces.append((v0, v1, v2, v3))

    return {
        "vertices": all_verts,
        "faces": all_faces,
        "uvs": all_uvs,
        "metadata": {
            "name": "hair_cards",
            "poly_count": len(all_faces),
            "vertex_count": len(all_verts),
            "strand_count": len(strands),
            "type": "hair_card_mesh",
        },
    }


def handle_hair_strands(params: dict) -> dict:
    """Generate hair strand curves and convert to renderable card mesh.

    Params:
        scalp_verts: list of [x,y,z] vertices on scalp
        scalp_normals: list of [nx,ny,nz] scalp surface normals
        hair_style: 'straight' | 'wavy' | 'curly' | 'braided' | 'dreadlocks' | 'ponytail'
        strand_count: int (total strands to generate)
        strand_length: float (in meters)
        strand_segments: int (control points per strand)
        gravity: float (0=no droop, 1=full gravity)
        clumping: float (0=separate, 1=clumped together)
        card_width: float (width of each hair card quad)
        seed: int

    Returns:
        MeshSpec with card geometry + strand_data for optional curve output.
    """
    scalp_verts = params.get("scalp_verts", [])
    scalp_normals = params.get("scalp_normals", [])
    hair_style = params.get("hair_style", "straight")
    strand_count = params.get("strand_count", 50)
    strand_length = params.get("strand_length", 0.15)
    strand_segments = params.get("strand_segments", 8)
    gravity_val = params.get("gravity", 0.5)
    clumping_val = params.get("clumping", 0.3)
    card_width = params.get("card_width", 0.005)
    seed = params.get("seed", 42)

    if not scalp_verts:
        return {"error": "scalp_verts is required"}
    if hair_style not in VALID_HAIR_STYLES:
        return {"error": f"Invalid hair_style '{hair_style}'. Valid: {sorted(VALID_HAIR_STYLES)}"}

    # Convert to tuples if needed
    scalp_positions: list[Vec3] = [
        (v[0], v[1], v[2]) if isinstance(v, (list, tuple)) else v
        for v in scalp_verts
    ]
    scalp_norms: list[Vec3] = [
        (n[0], n[1], n[2]) if isinstance(n, (list, tuple)) else n
        for n in scalp_normals
    ]

    # Pad normals if shorter than positions
    while len(scalp_norms) < len(scalp_positions):
        scalp_norms.append((0.0, 0.0, 1.0))

    # Generate strands
    guide_strands = generate_hair_guide_strands(
        scalp_positions=scalp_positions,
        scalp_normals=scalp_norms,
        count=strand_count,
        length=strand_length,
        segments=strand_segments,
        style=hair_style,
        gravity=gravity_val,
        clumping=clumping_val,
        seed=seed,
    )

    # Convert to card mesh
    card_mesh = strands_to_cards(guide_strands, card_width)

    # Attach strand curve data for optional Blender curves output
    card_mesh["strand_data"] = {
        "strands": guide_strands,
        "strand_count": len(guide_strands),
        "segments_per_strand": strand_segments,
        "style": hair_style,
    }

    return card_mesh


# ===========================================================================
# Gap #60: Full Facial Articulation
# ===========================================================================

def _get_bones_for_level(setup_level: str) -> list[str]:
    """Get bone names for a given setup level (cumulative)."""
    level_order = ["basic", "standard", "full"]
    if setup_level not in level_order:
        setup_level = "basic"

    max_level_idx = level_order.index(setup_level)
    bones: list[str] = []
    for name, data in FACIAL_LANDMARKS.items():
        bone_level = data.get("level", "full")
        if bone_level in level_order and level_order.index(bone_level) <= max_level_idx:
            bones.append(name)
    return bones


def handle_facial_setup(params: dict) -> dict:
    """Set up full facial articulation bones and drivers.

    Params:
        armature_name: str
        face_mesh_name: str
        setup_level: 'basic' | 'standard' | 'full'

    Returns:
        Bone list with positions, vertex group names, driver setup code.
    """
    armature_name = params.get("armature_name", "Armature")
    face_mesh_name = params.get("face_mesh_name", "Head")
    setup_level = params.get("setup_level", "basic")

    if setup_level not in VALID_FACIAL_LEVELS:
        return {"error": f"Invalid setup_level '{setup_level}'. Valid: {sorted(VALID_FACIAL_LEVELS)}"}

    bone_names = _get_bones_for_level(setup_level)

    bones: list[dict[str, Any]] = []
    vertex_groups: list[dict[str, Any]] = []
    drivers: list[dict[str, Any]] = []

    for bone_name in bone_names:
        landmark = FACIAL_LANDMARKS[bone_name]
        pos = landmark["pos"]
        axis = landmark["axis"]
        motion_range = landmark["range"]
        parent = landmark["parent"]
        vg_radius = landmark["vertex_group_radius"]

        bone_data = {
            "name": f"face_{bone_name}",
            "head_position": pos,
            "tail_position": (
                pos[0],
                pos[1] + 0.01,  # Short bones pointing forward
                pos[2],
            ),
            "parent": f"face_{parent}" if parent != "head" else "head",
            "use_deform": vg_radius > 0,
            "bone_group": "facial",
        }
        bones.append(bone_data)

        # Vertex group for weight painting
        if vg_radius > 0:
            vg_data = {
                "name": f"face_{bone_name}",
                "center": pos,
                "radius": vg_radius,
                "falloff": "smooth",
            }
            vertex_groups.append(vg_data)

        # Shape key driver (for blend shape control)
        if motion_range[0] != 0.0 or motion_range[1] != 0.0:
            driver_data = {
                "bone_name": f"face_{bone_name}",
                "transform_channel": axis,
                "shape_key_name": f"SK_{bone_name}",
                "min_value": motion_range[0],
                "max_value": motion_range[1],
                "driver_expression": f"var * {1.0 / max(abs(motion_range[1] - motion_range[0]), 0.001):.3f}",
            }
            drivers.append(driver_data)

    # Generate Blender Python code for setup
    setup_code_lines = [
        "import bpy",
        f"arm = bpy.data.objects['{armature_name}']",
        f"mesh = bpy.data.objects['{face_mesh_name}']",
        "bpy.context.view_layer.objects.active = arm",
        "bpy.ops.object.mode_set(mode='EDIT')",
        "",
    ]

    for bone in bones:
        name = bone["name"]
        hp = bone["head_position"]
        tp = bone["tail_position"]
        parent = bone["parent"]
        setup_code_lines.extend([
            f"b = arm.data.edit_bones.new('{name}')",
            f"b.head = ({hp[0]}, {hp[1]}, {hp[2]})",
            f"b.tail = ({tp[0]}, {tp[1]}, {tp[2]})",
            f"b.use_deform = {bone['use_deform']}",
        ])
        if parent:
            setup_code_lines.append(f"b.parent = arm.data.edit_bones.get('{parent}')")
        setup_code_lines.append("")

    setup_code_lines.append("bpy.ops.object.mode_set(mode='OBJECT')")

    return {
        "armature_name": armature_name,
        "face_mesh_name": face_mesh_name,
        "setup_level": setup_level,
        "bone_count": len(bones),
        "bones": bones,
        "vertex_groups": vertex_groups,
        "drivers": drivers,
        "setup_code": "\n".join(setup_code_lines),
    }


# ===========================================================================
# Gap #61: Body Morph / Proportion Controls
# ===========================================================================

def compute_morph_deltas(
    vertices: list[list[float]],
    vertex_regions: dict[str, list[int]],
    morph_name: str,
    weight: float,
) -> list[tuple[float, float, float]]:
    """Compute per-vertex position deltas for a named body morph.

    Uses anatomical rules per morph definition. Each morph affects specific
    body regions with region-appropriate deformations.

    Args:
        vertices: List of [x, y, z] vertex positions.
        vertex_regions: Dict mapping region names to lists of vertex indices.
        morph_name: Name of morph from VALID_MORPH_NAMES.
        weight: Blend weight (clamped 0-1).

    Returns:
        List of (dx, dy, dz) per vertex, same length as vertices.
    """
    w = _clamp(weight, 0.0, 1.0)
    n = len(vertices)
    deltas: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * n

    if w < 1e-8:
        return deltas

    morph_def = BODY_MORPH_TARGETS.get(morph_name)
    if morph_def is None:
        return deltas

    regions = morph_def.get("regions", {})
    rng = random.Random(hash(morph_name))

    for region_name, region_params in regions.items():
        mode = region_params.get("mode", "radial_expand")
        magnitude = region_params.get("magnitude", 0.0) * w

        # Get vertex indices for this region
        indices = vertex_regions.get(region_name, [])
        if not indices:
            # Try partial match (e.g., "upper_arm" matches "upper_arm_L" and "upper_arm_R")
            for rn, ri in vertex_regions.items():
                if region_name in rn or rn in region_name:
                    indices.extend(ri)

        if not indices:
            continue

        # Compute region centroid for radial operations
        cx = sum(vertices[i][0] for i in indices if i < n) / max(1, len(indices))
        cy = sum(vertices[i][1] for i in indices if i < n) / max(1, len(indices))
        cz = sum(vertices[i][2] for i in indices if i < n) / max(1, len(indices))

        for idx in indices:
            if idx >= n:
                continue
            v = vertices[idx]

            if mode == "radial_expand":
                # Move vertices away from region centroid in XY
                dx = v[0] - cx
                dy = v[1] - cy
                dz = 0.0
                focus = region_params.get("focus")
                if focus == "lateral":
                    dy *= 0.3  # Emphasize side expansion
                elif focus == "anterior":
                    dx *= 0.3  # Emphasize forward expansion
                elif focus == "upper":
                    # Only affect upper portion of region
                    if v[2] < cz:
                        continue
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1e-6:
                    scale = magnitude / dist
                    deltas[idx] = (dx * scale, dy * scale, dz)

            elif mode == "radial_shrink":
                # Move vertices toward region centroid
                dx = cx - v[0]
                dy = cy - v[1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1e-6:
                    scale = magnitude / dist
                    deltas[idx] = (dx * scale, dy * scale, 0.0)

            elif mode == "directional":
                axis = region_params.get("axis", "Y")
                if axis == "X":
                    deltas[idx] = (magnitude, 0.0, 0.0)
                elif axis == "Y":
                    deltas[idx] = (0.0, magnitude, 0.0)
                elif axis == "Z":
                    deltas[idx] = (0.0, 0.0, magnitude)

            elif mode == "scale_z":
                # Scale along Z relative to region centroid
                dz = (v[2] - cz) * magnitude
                deltas[idx] = (0.0, 0.0, dz)

            elif mode == "symmetric_expand":
                axis = region_params.get("axis", "X")
                if axis == "X":
                    sign = 1.0 if v[0] >= 0 else -1.0
                    deltas[idx] = (sign * magnitude, 0.0, 0.0)
                elif axis == "Y":
                    sign = 1.0 if v[1] >= 0 else -1.0
                    deltas[idx] = (0.0, sign * magnitude, 0.0)

            elif mode == "translate":
                axis = region_params.get("axis", "X")
                sign = 1.0 if v[0] >= 0 else -1.0  # Symmetric translate
                if axis == "X":
                    deltas[idx] = (sign * magnitude, 0.0, 0.0)
                elif axis == "Y":
                    deltas[idx] = (0.0, magnitude, 0.0)
                elif axis == "Z":
                    deltas[idx] = (0.0, 0.0, magnitude)

            elif mode == "noise":
                freq = region_params.get("frequency", 5.0)
                # Procedural noise based on vertex position
                nx = math.sin(v[0] * freq * 17.3 + v[1] * freq * 7.1) * magnitude
                ny = math.sin(v[1] * freq * 13.7 + v[2] * freq * 11.3) * magnitude
                nz = math.sin(v[2] * freq * 19.1 + v[0] * freq * 5.7) * magnitude
                deltas[idx] = (nx, ny, nz)

    return deltas


def handle_body_morph(params: dict) -> dict:
    """Apply parametric body morph controls.

    Params:
        vertices: list of [x,y,z]
        morphs: dict of {morph_name: float weight}
        body_regions: dict of {region_name: list of vertex_indices}

    Returns:
        Dict with morphed vertices and metadata.
    """
    vertices = params.get("vertices", [])
    morphs = params.get("morphs", {})
    body_regions = params.get("body_regions", {})

    if not vertices:
        return {"error": "vertices is required"}

    n = len(vertices)
    result_verts = [[v[0], v[1], v[2]] for v in vertices]
    applied_morphs: list[str] = []

    for morph_name, weight in morphs.items():
        if morph_name not in VALID_MORPH_NAMES:
            continue

        w = _clamp(float(weight), 0.0, 1.0)
        if w < 1e-8:
            continue

        deltas = compute_morph_deltas(vertices, body_regions, morph_name, w)
        for i in range(n):
            d = deltas[i]
            result_verts[i][0] += d[0]
            result_verts[i][1] += d[1]
            result_verts[i][2] += d[2]

        applied_morphs.append(morph_name)

    # Compute total displacement
    total_disp = 0.0
    max_disp = 0.0
    for i in range(n):
        d = math.sqrt(
            (result_verts[i][0] - vertices[i][0]) ** 2
            + (result_verts[i][1] - vertices[i][1]) ** 2
            + (result_verts[i][2] - vertices[i][2]) ** 2
        )
        total_disp += d
        max_disp = max(max_disp, d)

    return {
        "vertices": result_verts,
        "vertex_count": n,
        "applied_morphs": applied_morphs,
        "stats": {
            "avg_displacement": round(total_disp / max(1, n), 6),
            "max_displacement": round(max_disp, 6),
        },
    }
