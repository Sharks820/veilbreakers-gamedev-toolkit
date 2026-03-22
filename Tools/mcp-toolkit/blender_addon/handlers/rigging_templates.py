"""Creature rig template bone definitions for Rigify metarig generation.

Provides 10 creature template bone dicts, a TEMPLATE_CATALOG mapping,
a LIMB_LIBRARY for mix-and-match custom rig building, and helper functions
for creating metarig bones and generating control rigs.

Templates: humanoid, quadruped, bird, insect, serpent, floating, dragon,
multi-armed, arachnid, amorphous.
"""

from __future__ import annotations

import bpy

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Valid Rigify type strings (for validation in tests)
# ---------------------------------------------------------------------------

VALID_RIGIFY_TYPES: frozenset[str] = frozenset({
    "",  # empty means "no rigify type" (child bones in chain)
    "spines.super_spine",
    "spines.basic_tail",
    "limbs.super_limb",
    "limbs.arm",
    "limbs.leg",
    "limbs.paw",
    "limbs.front_paw",
    "limbs.rear_paw",
    "limbs.super_finger",
    "limbs.super_palm",
    "limbs.simple_tentacle",
    "basic.copy_chain",
    "basic.pivot",
    "basic.raw_copy",
    "basic.super_copy",
    "faces.super_face",
    "skin.basic_chain",
    "skin.stretchy_chain",
    "skin.anchor",
    "skin.glue",
})


# ---------------------------------------------------------------------------
# Creature template bone definitions
# ---------------------------------------------------------------------------
# Each template is a dict[str, dict] where keys are bone names and values
# have "head" (3-tuple), "tail" (3-tuple), "roll" (float),
# "parent" (str or None), "rigify_type" (str, can be empty).


HUMANOID_BONES: dict[str, dict] = {
    # Root motion bone
    "root": {
        "head": (0.0, 0.0, 0.0),
        "tail": (0.0, 0.0, 0.1),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "",
    },
    # Spine chain (4 bones)
    "spine": {
        "head": (0.0, 0.0, 0.95),
        "tail": (0.0, 0.0, 1.1),
        "roll": 0.0,
        "parent": "root",
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, 0.0, 1.1),
        "tail": (0.0, 0.0, 1.25),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, 0.0, 1.25),
        "tail": (0.0, 0.0, 1.4),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    "spine.003": {
        "head": (0.0, 0.0, 1.4),
        "tail": (0.0, 0.0, 1.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    # Neck and head (spaced for Rigify minimum neck length)
    "spine.004": {
        "head": (0.0, 0.0, 1.55),
        "tail": (0.0, 0.0, 1.73),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    "spine.005": {
        "head": (0.0, 0.0, 1.73),
        "tail": (0.0, 0.0, 1.95),
        "roll": 0.0,
        "parent": "spine.004",
        "rigify_type": "",
    },
    # Shoulders (Rigify convention: shoulder.L/R)
    "shoulder.L": {
        "head": (0.02, 0.0, 1.5),
        "tail": (0.18, 0.0, 1.5),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "basic.super_copy",
    },
    "shoulder.R": {
        "head": (-0.02, 0.0, 1.5),
        "tail": (-0.18, 0.0, 1.5),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "basic.super_copy",
    },
    # Left arm
    "upper_arm.L": {
        "head": (0.18, 0.0, 1.5),
        "tail": (0.4, 0.0, 1.5),
        "roll": 0.0,
        "parent": "shoulder.L",
        "rigify_type": "limbs.arm",
    },
    "forearm.L": {
        "head": (0.4, 0.0, 1.5),
        "tail": (0.62, 0.0, 1.5),
        "roll": 1.5708,
        "parent": "upper_arm.L",
        "rigify_type": "",
    },
    "hand.L": {
        "head": (0.62, 0.0, 1.5),
        "tail": (0.72, 0.0, 1.5),
        "roll": 0.0,
        "parent": "forearm.L",
        "rigify_type": "",
    },
    # Right arm
    "upper_arm.R": {
        "head": (-0.18, 0.0, 1.5),
        "tail": (-0.4, 0.0, 1.5),
        "roll": 0.0,
        "parent": "shoulder.R",
        "rigify_type": "limbs.arm",
    },
    "forearm.R": {
        "head": (-0.4, 0.0, 1.5),
        "tail": (-0.62, 0.0, 1.5),
        "roll": -1.5708,
        "parent": "upper_arm.R",
        "rigify_type": "",
    },
    "hand.R": {
        "head": (-0.62, 0.0, 1.5),
        "tail": (-0.72, 0.0, 1.5),
        "roll": 0.0,
        "parent": "forearm.R",
        "rigify_type": "",
    },
    # Left leg
    "thigh.L": {
        "head": (0.1, 0.0, 0.95),
        "tail": (0.1, 0.0, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.L": {
        "head": (0.1, 0.0, 0.5),
        "tail": (0.1, 0.0, 0.08),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "",
    },
    "foot.L": {
        "head": (0.1, 0.0, 0.08),
        "tail": (0.1, -0.1, 0.0),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "",
    },
    # Right leg
    "thigh.R": {
        "head": (-0.1, 0.0, 0.95),
        "tail": (-0.1, 0.0, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.R": {
        "head": (-0.1, 0.0, 0.5),
        "tail": (-0.1, 0.0, 0.08),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "",
    },
    "foot.R": {
        "head": (-0.1, 0.0, 0.08),
        "tail": (-0.1, -0.1, 0.0),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "",
    },
    # Toes
    "toe.L": {
        "head": (0.1, -0.1, 0.0),
        "tail": (0.1, -0.15, 0.0),
        "roll": 0.0,
        "parent": "foot.L",
        "rigify_type": "basic.super_copy",
    },
    "toe.001.L": {
        "head": (0.1, -0.15, 0.0),
        "tail": (0.1, -0.19, 0.0),
        "roll": 0.0,
        "parent": "toe.L",
        "rigify_type": "",
    },
    "toe.R": {
        "head": (-0.1, -0.1, 0.0),
        "tail": (-0.1, -0.15, 0.0),
        "roll": 0.0,
        "parent": "foot.R",
        "rigify_type": "basic.super_copy",
    },
    "toe.001.R": {
        "head": (-0.1, -0.15, 0.0),
        "tail": (-0.1, -0.19, 0.0),
        "roll": 0.0,
        "parent": "toe.R",
        "rigify_type": "",
    },
    # Finger bones -- Left hand (Rigify convention: thumb.XX, f_finger.XX)
    "thumb.01.L": {
        "head": (0.64, -0.02, 1.49),
        "tail": (0.66, -0.03, 1.48),
        "roll": 0.0,
        "parent": "hand.L",
        "rigify_type": "limbs.super_finger",
    },
    "thumb.02.L": {
        "head": (0.66, -0.03, 1.48),
        "tail": (0.68, -0.04, 1.47),
        "roll": 0.0,
        "parent": "thumb.01.L",
        "rigify_type": "",
    },
    "thumb.03.L": {
        "head": (0.68, -0.04, 1.47),
        "tail": (0.70, -0.05, 1.46),
        "roll": 0.0,
        "parent": "thumb.02.L",
        "rigify_type": "",
    },
    "f_index.01.L": {
        "head": (0.72, -0.01, 1.50),
        "tail": (0.75, -0.01, 1.50),
        "roll": 0.0,
        "parent": "hand.L",
        "rigify_type": "limbs.super_finger",
    },
    "f_index.02.L": {
        "head": (0.75, -0.01, 1.50),
        "tail": (0.78, -0.01, 1.50),
        "roll": 0.0,
        "parent": "f_index.01.L",
        "rigify_type": "",
    },
    "f_index.03.L": {
        "head": (0.78, -0.01, 1.50),
        "tail": (0.81, -0.01, 1.50),
        "roll": 0.0,
        "parent": "f_index.02.L",
        "rigify_type": "",
    },
    "f_middle.01.L": {
        "head": (0.72, 0.0, 1.50),
        "tail": (0.75, 0.0, 1.50),
        "roll": 0.0,
        "parent": "hand.L",
        "rigify_type": "limbs.super_finger",
    },
    "f_middle.02.L": {
        "head": (0.75, 0.0, 1.50),
        "tail": (0.78, 0.0, 1.50),
        "roll": 0.0,
        "parent": "f_middle.01.L",
        "rigify_type": "",
    },
    "f_middle.03.L": {
        "head": (0.78, 0.0, 1.50),
        "tail": (0.81, 0.0, 1.50),
        "roll": 0.0,
        "parent": "f_middle.02.L",
        "rigify_type": "",
    },
    "f_ring.01.L": {
        "head": (0.72, 0.01, 1.50),
        "tail": (0.75, 0.01, 1.50),
        "roll": 0.0,
        "parent": "hand.L",
        "rigify_type": "limbs.super_finger",
    },
    "f_ring.02.L": {
        "head": (0.75, 0.01, 1.50),
        "tail": (0.78, 0.01, 1.50),
        "roll": 0.0,
        "parent": "f_ring.01.L",
        "rigify_type": "",
    },
    "f_ring.03.L": {
        "head": (0.78, 0.01, 1.50),
        "tail": (0.81, 0.01, 1.50),
        "roll": 0.0,
        "parent": "f_ring.02.L",
        "rigify_type": "",
    },
    "f_pinky.01.L": {
        "head": (0.72, 0.02, 1.50),
        "tail": (0.74, 0.02, 1.50),
        "roll": 0.0,
        "parent": "hand.L",
        "rigify_type": "limbs.super_finger",
    },
    "f_pinky.02.L": {
        "head": (0.74, 0.02, 1.50),
        "tail": (0.76, 0.02, 1.50),
        "roll": 0.0,
        "parent": "f_pinky.01.L",
        "rigify_type": "",
    },
    "f_pinky.03.L": {
        "head": (0.76, 0.02, 1.50),
        "tail": (0.78, 0.02, 1.50),
        "roll": 0.0,
        "parent": "f_pinky.02.L",
        "rigify_type": "",
    },
    # Finger bones -- Right hand (Rigify convention: thumb.XX, f_finger.XX)
    "thumb.01.R": {
        "head": (-0.64, -0.02, 1.49),
        "tail": (-0.66, -0.03, 1.48),
        "roll": 0.0,
        "parent": "hand.R",
        "rigify_type": "limbs.super_finger",
    },
    "thumb.02.R": {
        "head": (-0.66, -0.03, 1.48),
        "tail": (-0.68, -0.04, 1.47),
        "roll": 0.0,
        "parent": "thumb.01.R",
        "rigify_type": "",
    },
    "thumb.03.R": {
        "head": (-0.68, -0.04, 1.47),
        "tail": (-0.70, -0.05, 1.46),
        "roll": 0.0,
        "parent": "thumb.02.R",
        "rigify_type": "",
    },
    "f_index.01.R": {
        "head": (-0.72, -0.01, 1.50),
        "tail": (-0.75, -0.01, 1.50),
        "roll": 0.0,
        "parent": "hand.R",
        "rigify_type": "limbs.super_finger",
    },
    "f_index.02.R": {
        "head": (-0.75, -0.01, 1.50),
        "tail": (-0.78, -0.01, 1.50),
        "roll": 0.0,
        "parent": "f_index.01.R",
        "rigify_type": "",
    },
    "f_index.03.R": {
        "head": (-0.78, -0.01, 1.50),
        "tail": (-0.81, -0.01, 1.50),
        "roll": 0.0,
        "parent": "f_index.02.R",
        "rigify_type": "",
    },
    "f_middle.01.R": {
        "head": (-0.72, 0.0, 1.50),
        "tail": (-0.75, 0.0, 1.50),
        "roll": 0.0,
        "parent": "hand.R",
        "rigify_type": "limbs.super_finger",
    },
    "f_middle.02.R": {
        "head": (-0.75, 0.0, 1.50),
        "tail": (-0.78, 0.0, 1.50),
        "roll": 0.0,
        "parent": "f_middle.01.R",
        "rigify_type": "",
    },
    "f_middle.03.R": {
        "head": (-0.78, 0.0, 1.50),
        "tail": (-0.81, 0.0, 1.50),
        "roll": 0.0,
        "parent": "f_middle.02.R",
        "rigify_type": "",
    },
    "f_ring.01.R": {
        "head": (-0.72, 0.01, 1.50),
        "tail": (-0.75, 0.01, 1.50),
        "roll": 0.0,
        "parent": "hand.R",
        "rigify_type": "limbs.super_finger",
    },
    "f_ring.02.R": {
        "head": (-0.75, 0.01, 1.50),
        "tail": (-0.78, 0.01, 1.50),
        "roll": 0.0,
        "parent": "f_ring.01.R",
        "rigify_type": "",
    },
    "f_ring.03.R": {
        "head": (-0.78, 0.01, 1.50),
        "tail": (-0.81, 0.01, 1.50),
        "roll": 0.0,
        "parent": "f_ring.02.R",
        "rigify_type": "",
    },
    "f_pinky.01.R": {
        "head": (-0.72, 0.02, 1.50),
        "tail": (-0.74, 0.02, 1.50),
        "roll": 0.0,
        "parent": "hand.R",
        "rigify_type": "limbs.super_finger",
    },
    "f_pinky.02.R": {
        "head": (-0.74, 0.02, 1.50),
        "tail": (-0.76, 0.02, 1.50),
        "roll": 0.0,
        "parent": "f_pinky.01.R",
        "rigify_type": "",
    },
    "f_pinky.03.R": {
        "head": (-0.76, 0.02, 1.50),
        "tail": (-0.78, 0.02, 1.50),
        "roll": 0.0,
        "parent": "f_pinky.02.R",
        "rigify_type": "",
    },
    # Twist bones (50% of segment)
    "upper_arm_twist.L": {
        "head": (0.29, 0.0, 1.5),
        "tail": (0.35, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist.R": {
        "head": (-0.29, 0.0, 1.5),
        "tail": (-0.35, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.L": {
        "head": (0.51, 0.0, 1.5),
        "tail": (0.57, 0.0, 1.5),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.R": {
        "head": (-0.51, 0.0, 1.5),
        "tail": (-0.57, 0.0, 1.5),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.L": {
        "head": (0.1, 0.0, 0.73),
        "tail": (0.1, 0.0, 0.67),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.R": {
        "head": (-0.1, 0.0, 0.73),
        "tail": (-0.1, 0.0, 0.67),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.L": {
        "head": (0.1, 0.0, 0.29),
        "tail": (0.1, 0.0, 0.23),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.R": {
        "head": (-0.1, 0.0, 0.29),
        "tail": (-0.1, 0.0, 0.23),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
    # AAA multi-twist bones (25% of segment) for improved volume preservation
    "upper_arm_twist_025.L": {
        "head": (0.235, 0.0, 1.5),
        "tail": (0.265, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist_025.R": {
        "head": (-0.235, 0.0, 1.5),
        "tail": (-0.265, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist_025.L": {
        "head": (0.455, 0.0, 1.5),
        "tail": (0.485, 0.0, 1.5),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist_025.R": {
        "head": (-0.455, 0.0, 1.5),
        "tail": (-0.485, 0.0, 1.5),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist_025.L": {
        "head": (0.1, 0.0, 0.8375),
        "tail": (0.1, 0.0, 0.7975),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist_025.R": {
        "head": (-0.1, 0.0, 0.8375),
        "tail": (-0.1, 0.0, 0.7975),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist_025.L": {
        "head": (0.1, 0.0, 0.395),
        "tail": (0.1, 0.0, 0.355),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist_025.R": {
        "head": (-0.1, 0.0, 0.395),
        "tail": (-0.1, 0.0, 0.355),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
}


QUADRUPED_BONES: dict[str, dict] = {
    # Root motion bone
    "root": {
        "head": (0.0, 0.0, 0.0),
        "tail": (0.0, 0.0, 0.1),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "",
    },
    # Spine chain (3 bones)
    "spine": {
        "head": (0.0, 0.0, 0.8),
        "tail": (0.0, -0.2, 0.85),
        "roll": 0.0,
        "parent": "root",
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.2, 0.85),
        "tail": (0.0, -0.4, 0.9),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, -0.4, 0.9),
        "tail": (0.0, -0.55, 0.92),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Neck and head
    "spine.003": {
        "head": (0.0, -0.55, 0.92),
        "tail": (0.0, -0.65, 0.98),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    "spine.004": {
        "head": (0.0, -0.65, 0.98),
        "tail": (0.0, -0.75, 1.05),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    # Front left leg
    "upper_arm.L": {
        "head": (0.15, -0.45, 0.7),
        "tail": (0.15, -0.43, 0.4),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.front_paw",
    },
    "forearm.L": {
        "head": (0.15, -0.43, 0.4),
        "tail": (0.15, -0.42, 0.1),
        "roll": 1.5708,
        "parent": "upper_arm.L",
        "rigify_type": "",
    },
    "hand.L": {
        "head": (0.15, -0.42, 0.1),
        "tail": (0.15, -0.42, 0.0),
        "roll": 0.0,
        "parent": "forearm.L",
        "rigify_type": "",
    },
    # Front right leg
    "upper_arm.R": {
        "head": (-0.15, -0.45, 0.7),
        "tail": (-0.15, -0.43, 0.4),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.front_paw",
    },
    "forearm.R": {
        "head": (-0.15, -0.43, 0.4),
        "tail": (-0.15, -0.42, 0.1),
        "roll": -1.5708,
        "parent": "upper_arm.R",
        "rigify_type": "",
    },
    "hand.R": {
        "head": (-0.15, -0.42, 0.1),
        "tail": (-0.15, -0.42, 0.0),
        "roll": 0.0,
        "parent": "forearm.R",
        "rigify_type": "",
    },
    # Rear left leg
    "thigh.L": {
        "head": (0.12, 0.05, 0.75),
        "tail": (0.12, 0.07, 0.4),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "shin.L": {
        "head": (0.12, 0.07, 0.4),
        "tail": (0.12, 0.05, 0.1),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "",
    },
    "foot.L": {
        "head": (0.12, 0.05, 0.1),
        "tail": (0.12, -0.05, 0.0),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "",
    },
    # Rear right leg
    "thigh.R": {
        "head": (-0.12, 0.05, 0.75),
        "tail": (-0.12, 0.07, 0.4),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "shin.R": {
        "head": (-0.12, 0.07, 0.4),
        "tail": (-0.12, 0.05, 0.1),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "",
    },
    "foot.R": {
        "head": (-0.12, 0.05, 0.1),
        "tail": (-0.12, -0.05, 0.0),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "",
    },
    # Tail chain (3 bones)
    "tail": {
        "head": (0.0, 0.15, 0.78),
        "tail": (0.0, 0.35, 0.72),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "spines.basic_tail",
    },
    "tail.001": {
        "head": (0.0, 0.35, 0.72),
        "tail": (0.0, 0.55, 0.65),
        "roll": 0.0,
        "parent": "tail",
        "rigify_type": "",
    },
    "tail.002": {
        "head": (0.0, 0.55, 0.65),
        "tail": (0.0, 0.7, 0.58),
        "roll": 0.0,
        "parent": "tail.001",
        "rigify_type": "",
    },
    # Twist bones
    "upper_arm_twist.L": {
        "head": (0.15, -0.44, 0.55),
        "tail": (0.15, -0.435, 0.48),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist.R": {
        "head": (-0.15, -0.44, 0.55),
        "tail": (-0.15, -0.435, 0.48),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.L": {
        "head": (0.15, -0.425, 0.25),
        "tail": (0.15, -0.42, 0.18),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.R": {
        "head": (-0.15, -0.425, 0.25),
        "tail": (-0.15, -0.42, 0.18),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.L": {
        "head": (0.12, 0.06, 0.575),
        "tail": (0.12, 0.065, 0.49),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.R": {
        "head": (-0.12, 0.06, 0.575),
        "tail": (-0.12, 0.065, 0.49),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.L": {
        "head": (0.12, 0.06, 0.25),
        "tail": (0.12, 0.055, 0.18),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.R": {
        "head": (-0.12, 0.06, 0.25),
        "tail": (-0.12, 0.055, 0.18),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
}


BIRD_BONES: dict[str, dict] = {
    # Spine chain (3 bones)
    "spine": {
        "head": (0.0, 0.0, 0.5),
        "tail": (0.0, -0.1, 0.55),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.1, 0.55),
        "tail": (0.0, -0.2, 0.6),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, -0.2, 0.6),
        "tail": (0.0, -0.28, 0.63),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Neck chain (2 bones)
    "spine.003": {
        "head": (0.0, -0.28, 0.63),
        "tail": (0.0, -0.35, 0.7),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    "spine.004": {
        "head": (0.0, -0.35, 0.7),
        "tail": (0.0, -0.4, 0.78),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    # Head
    "spine.005": {
        "head": (0.0, -0.4, 0.78),
        "tail": (0.0, -0.48, 0.82),
        "roll": 0.0,
        "parent": "spine.004",
        "rigify_type": "",
    },
    # Left wing (arm bones)
    "upper_arm.L": {
        "head": (0.08, -0.15, 0.58),
        "tail": (0.35, -0.12, 0.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "forearm.L": {
        "head": (0.35, -0.12, 0.55),
        "tail": (0.6, -0.1, 0.52),
        "roll": 1.5708,
        "parent": "upper_arm.L",
        "rigify_type": "",
    },
    "hand.L": {
        "head": (0.6, -0.1, 0.52),
        "tail": (0.8, -0.08, 0.5),
        "roll": 0.0,
        "parent": "forearm.L",
        "rigify_type": "",
    },
    # Right wing (arm bones)
    "upper_arm.R": {
        "head": (-0.08, -0.15, 0.58),
        "tail": (-0.35, -0.12, 0.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "forearm.R": {
        "head": (-0.35, -0.12, 0.55),
        "tail": (-0.6, -0.1, 0.52),
        "roll": -1.5708,
        "parent": "upper_arm.R",
        "rigify_type": "",
    },
    "hand.R": {
        "head": (-0.6, -0.1, 0.52),
        "tail": (-0.8, -0.08, 0.5),
        "roll": 0.0,
        "parent": "forearm.R",
        "rigify_type": "",
    },
    # Left leg
    "thigh.L": {
        "head": (0.06, 0.02, 0.45),
        "tail": (0.06, 0.04, 0.25),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.L": {
        "head": (0.06, 0.04, 0.25),
        "tail": (0.06, 0.02, 0.06),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "",
    },
    "foot.L": {
        "head": (0.06, 0.02, 0.06),
        "tail": (0.06, -0.06, 0.0),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "",
    },
    # Right leg
    "thigh.R": {
        "head": (-0.06, 0.02, 0.45),
        "tail": (-0.06, 0.04, 0.25),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.R": {
        "head": (-0.06, 0.04, 0.25),
        "tail": (-0.06, 0.02, 0.06),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "",
    },
    "foot.R": {
        "head": (-0.06, 0.02, 0.06),
        "tail": (-0.06, -0.06, 0.0),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "",
    },
    # Tail fan
    "tail": {
        "head": (0.0, 0.1, 0.48),
        "tail": (0.0, 0.22, 0.42),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "spines.basic_tail",
    },
    "tail.001": {
        "head": (0.0, 0.22, 0.42),
        "tail": (0.0, 0.32, 0.38),
        "roll": 0.0,
        "parent": "tail",
        "rigify_type": "",
    },
    # Twist bones
    "upper_arm_twist.L": {
        "head": (0.215, -0.135, 0.565),
        "tail": (0.28, -0.128, 0.558),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist.R": {
        "head": (-0.215, -0.135, 0.565),
        "tail": (-0.28, -0.128, 0.558),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.L": {
        "head": (0.475, -0.11, 0.535),
        "tail": (0.538, -0.105, 0.528),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.R": {
        "head": (-0.475, -0.11, 0.535),
        "tail": (-0.538, -0.105, 0.528),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.L": {
        "head": (0.06, 0.03, 0.35),
        "tail": (0.06, 0.035, 0.3),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.R": {
        "head": (-0.06, 0.03, 0.35),
        "tail": (-0.06, 0.035, 0.3),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.L": {
        "head": (0.06, 0.03, 0.155),
        "tail": (0.06, 0.025, 0.11),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.R": {
        "head": (-0.06, 0.03, 0.155),
        "tail": (-0.06, 0.025, 0.11),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
}


INSECT_BONES: dict[str, dict] = {
    # Thorax spine (2 bones)
    "spine": {
        "head": (0.0, 0.0, 0.3),
        "tail": (0.0, -0.15, 0.32),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.15, 0.32),
        "tail": (0.0, -0.3, 0.33),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    # Head
    "spine.002": {
        "head": (0.0, -0.3, 0.33),
        "tail": (0.0, -0.4, 0.34),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Mandible left
    "mandible.L": {
        "head": (0.03, -0.4, 0.32),
        "tail": (0.05, -0.48, 0.3),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "basic.super_copy",
    },
    # Mandible right
    "mandible.R": {
        "head": (-0.03, -0.4, 0.32),
        "tail": (-0.05, -0.48, 0.3),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "basic.super_copy",
    },
    # Antenna left
    "antenna.L": {
        "head": (0.02, -0.38, 0.35),
        "tail": (0.04, -0.5, 0.42),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.simple_tentacle",
    },
    "antenna.L.001": {
        "head": (0.04, -0.5, 0.42),
        "tail": (0.05, -0.58, 0.48),
        "roll": 0.0,
        "parent": "antenna.L",
        "rigify_type": "",
    },
    # Antenna right
    "antenna.R": {
        "head": (-0.02, -0.38, 0.35),
        "tail": (-0.04, -0.5, 0.42),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.simple_tentacle",
    },
    "antenna.R.001": {
        "head": (-0.04, -0.5, 0.42),
        "tail": (-0.05, -0.58, 0.48),
        "roll": 0.0,
        "parent": "antenna.R",
        "rigify_type": "",
    },
    # Leg pair 1 (front) L/R
    "leg_front.L": {
        "head": (0.08, -0.25, 0.28),
        "tail": (0.18, -0.24, 0.15),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_front_lower.L": {
        "head": (0.18, -0.24, 0.15),
        "tail": (0.24, -0.23, 0.0),
        "roll": 0.0,
        "parent": "leg_front.L",
        "rigify_type": "",
    },
    "leg_front_foot.L": {
        "head": (0.24, -0.23, 0.0),
        "tail": (0.26, -0.25, -0.02),
        "roll": 0.0,
        "parent": "leg_front_lower.L",
        "rigify_type": "",
    },
    "leg_front.R": {
        "head": (-0.08, -0.25, 0.28),
        "tail": (-0.18, -0.24, 0.15),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_front_lower.R": {
        "head": (-0.18, -0.24, 0.15),
        "tail": (-0.24, -0.23, 0.0),
        "roll": 0.0,
        "parent": "leg_front.R",
        "rigify_type": "",
    },
    "leg_front_foot.R": {
        "head": (-0.24, -0.23, 0.0),
        "tail": (-0.26, -0.25, -0.02),
        "roll": 0.0,
        "parent": "leg_front_lower.R",
        "rigify_type": "",
    },
    # Leg pair 2 (mid) L/R
    "leg_mid.L": {
        "head": (0.08, -0.12, 0.28),
        "tail": (0.2, -0.12, 0.15),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.front_paw",
    },
    "leg_mid_lower.L": {
        "head": (0.2, -0.12, 0.15),
        "tail": (0.28, -0.12, 0.0),
        "roll": 0.0,
        "parent": "leg_mid.L",
        "rigify_type": "",
    },
    "leg_mid_foot.L": {
        "head": (0.28, -0.12, 0.0),
        "tail": (0.3, -0.14, -0.02),
        "roll": 0.0,
        "parent": "leg_mid_lower.L",
        "rigify_type": "",
    },
    "leg_mid.R": {
        "head": (-0.08, -0.12, 0.28),
        "tail": (-0.2, -0.12, 0.15),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.front_paw",
    },
    "leg_mid_lower.R": {
        "head": (-0.2, -0.12, 0.15),
        "tail": (-0.28, -0.12, 0.0),
        "roll": 0.0,
        "parent": "leg_mid.R",
        "rigify_type": "",
    },
    "leg_mid_foot.R": {
        "head": (-0.28, -0.12, 0.0),
        "tail": (-0.3, -0.14, -0.02),
        "roll": 0.0,
        "parent": "leg_mid_lower.R",
        "rigify_type": "",
    },
    # Leg pair 3 (rear) L/R
    "leg_rear.L": {
        "head": (0.08, 0.02, 0.28),
        "tail": (0.18, 0.04, 0.15),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_rear_lower.L": {
        "head": (0.18, 0.04, 0.15),
        "tail": (0.24, 0.05, 0.0),
        "roll": 0.0,
        "parent": "leg_rear.L",
        "rigify_type": "",
    },
    "leg_rear_foot.L": {
        "head": (0.24, 0.05, 0.0),
        "tail": (0.26, 0.03, -0.02),
        "roll": 0.0,
        "parent": "leg_rear_lower.L",
        "rigify_type": "",
    },
    "leg_rear.R": {
        "head": (-0.08, 0.02, 0.28),
        "tail": (-0.18, 0.04, 0.15),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_rear_lower.R": {
        "head": (-0.18, 0.04, 0.15),
        "tail": (-0.24, 0.05, 0.0),
        "roll": 0.0,
        "parent": "leg_rear.R",
        "rigify_type": "",
    },
    "leg_rear_foot.R": {
        "head": (-0.24, 0.05, 0.0),
        "tail": (-0.26, 0.03, -0.02),
        "roll": 0.0,
        "parent": "leg_rear_lower.R",
        "rigify_type": "",
    },
}


SERPENT_BONES: dict[str, dict] = {
    # Long spine chain (8 bones)
    "spine": {
        "head": (0.0, 0.0, 0.1),
        "tail": (0.0, -0.2, 0.12),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.2, 0.12),
        "tail": (0.0, -0.4, 0.14),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, -0.4, 0.14),
        "tail": (0.0, -0.6, 0.16),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    "spine.003": {
        "head": (0.0, -0.6, 0.16),
        "tail": (0.0, -0.8, 0.18),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    "spine.004": {
        "head": (0.0, -0.8, 0.18),
        "tail": (0.0, -1.0, 0.2),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    "spine.005": {
        "head": (0.0, -1.0, 0.2),
        "tail": (0.0, -1.15, 0.24),
        "roll": 0.0,
        "parent": "spine.004",
        "rigify_type": "",
    },
    "spine.006": {
        "head": (0.0, -1.15, 0.24),
        "tail": (0.0, -1.28, 0.3),
        "roll": 0.0,
        "parent": "spine.005",
        "rigify_type": "",
    },
    "spine.007": {
        "head": (0.0, -1.28, 0.3),
        "tail": (0.0, -1.38, 0.38),
        "roll": 0.0,
        "parent": "spine.006",
        "rigify_type": "",
    },
    # Head
    "spine.008": {
        "head": (0.0, -1.38, 0.38),
        "tail": (0.0, -1.5, 0.44),
        "roll": 0.0,
        "parent": "spine.007",
        "rigify_type": "",
    },
    # Jaw
    "jaw": {
        "head": (0.0, -1.5, 0.42),
        "tail": (0.0, -1.6, 0.38),
        "roll": 0.0,
        "parent": "spine.008",
        "rigify_type": "basic.super_copy",
    },
}


FLOATING_BONES: dict[str, dict] = {
    # Minimal spine (2 bones)
    "spine": {
        "head": (0.0, 0.0, 0.5),
        "tail": (0.0, 0.0, 0.65),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, 0.0, 0.65),
        "tail": (0.0, 0.0, 0.8),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    # Head
    "spine.002": {
        "head": (0.0, 0.0, 0.8),
        "tail": (0.0, 0.0, 0.95),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Tentacle 1 (front-left)
    "tentacle_fl": {
        "head": (0.1, -0.08, 0.48),
        "tail": (0.15, -0.12, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_fl.001": {
        "head": (0.15, -0.12, 0.3),
        "tail": (0.18, -0.15, 0.12),
        "roll": 0.0,
        "parent": "tentacle_fl",
        "rigify_type": "",
    },
    # Tentacle 2 (front-right)
    "tentacle_fr": {
        "head": (-0.1, -0.08, 0.48),
        "tail": (-0.15, -0.12, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_fr.001": {
        "head": (-0.15, -0.12, 0.3),
        "tail": (-0.18, -0.15, 0.12),
        "roll": 0.0,
        "parent": "tentacle_fr",
        "rigify_type": "",
    },
    # Tentacle 3 (back-left)
    "tentacle_bl": {
        "head": (0.1, 0.08, 0.48),
        "tail": (0.15, 0.12, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_bl.001": {
        "head": (0.15, 0.12, 0.3),
        "tail": (0.18, 0.15, 0.12),
        "roll": 0.0,
        "parent": "tentacle_bl",
        "rigify_type": "",
    },
    # Tentacle 4 (back-right)
    "tentacle_br": {
        "head": (-0.1, 0.08, 0.48),
        "tail": (-0.15, 0.12, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_br.001": {
        "head": (-0.15, 0.12, 0.3),
        "tail": (-0.18, 0.15, 0.12),
        "roll": 0.0,
        "parent": "tentacle_br",
        "rigify_type": "",
    },
    # Tentacle 5 (left)
    "tentacle_l": {
        "head": (0.12, 0.0, 0.48),
        "tail": (0.2, 0.0, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_l.001": {
        "head": (0.2, 0.0, 0.3),
        "tail": (0.25, 0.0, 0.12),
        "roll": 0.0,
        "parent": "tentacle_l",
        "rigify_type": "",
    },
    # Tentacle 6 (right)
    "tentacle_r": {
        "head": (-0.12, 0.0, 0.48),
        "tail": (-0.2, 0.0, 0.3),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_r.001": {
        "head": (-0.2, 0.0, 0.3),
        "tail": (-0.25, 0.0, 0.12),
        "roll": 0.0,
        "parent": "tentacle_r",
        "rigify_type": "",
    },
}


DRAGON_BONES: dict[str, dict] = {
    # Spine chain (4 bones)
    "spine": {
        "head": (0.0, 0.0, 1.0),
        "tail": (0.0, -0.2, 1.05),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.2, 1.05),
        "tail": (0.0, -0.4, 1.1),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, -0.4, 1.1),
        "tail": (0.0, -0.6, 1.12),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    "spine.003": {
        "head": (0.0, -0.6, 1.12),
        "tail": (0.0, -0.75, 1.15),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    # Neck chain (2 bones)
    "spine.004": {
        "head": (0.0, -0.75, 1.15),
        "tail": (0.0, -0.9, 1.25),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    "spine.005": {
        "head": (0.0, -0.9, 1.25),
        "tail": (0.0, -1.0, 1.35),
        "roll": 0.0,
        "parent": "spine.004",
        "rigify_type": "",
    },
    # Head
    "spine.006": {
        "head": (0.0, -1.0, 1.35),
        "tail": (0.0, -1.12, 1.4),
        "roll": 0.0,
        "parent": "spine.005",
        "rigify_type": "",
    },
    # Jaw
    "jaw": {
        "head": (0.0, -1.12, 1.38),
        "tail": (0.0, -1.25, 1.3),
        "roll": 0.0,
        "parent": "spine.006",
        "rigify_type": "basic.super_copy",
    },
    # Front left leg
    "upper_arm.L": {
        "head": (0.2, -0.55, 0.9),
        "tail": (0.2, -0.52, 0.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.front_paw",
    },
    "forearm.L": {
        "head": (0.2, -0.52, 0.55),
        "tail": (0.2, -0.5, 0.15),
        "roll": 1.5708,
        "parent": "upper_arm.L",
        "rigify_type": "",
    },
    "hand.L": {
        "head": (0.2, -0.5, 0.15),
        "tail": (0.2, -0.55, 0.0),
        "roll": 0.0,
        "parent": "forearm.L",
        "rigify_type": "",
    },
    # Front right leg
    "upper_arm.R": {
        "head": (-0.2, -0.55, 0.9),
        "tail": (-0.2, -0.52, 0.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.front_paw",
    },
    "forearm.R": {
        "head": (-0.2, -0.52, 0.55),
        "tail": (-0.2, -0.5, 0.15),
        "roll": -1.5708,
        "parent": "upper_arm.R",
        "rigify_type": "",
    },
    "hand.R": {
        "head": (-0.2, -0.5, 0.15),
        "tail": (-0.2, -0.55, 0.0),
        "roll": 0.0,
        "parent": "forearm.R",
        "rigify_type": "",
    },
    # Rear left leg
    "thigh.L": {
        "head": (0.18, 0.05, 0.9),
        "tail": (0.18, 0.08, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "shin.L": {
        "head": (0.18, 0.08, 0.5),
        "tail": (0.18, 0.06, 0.12),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "",
    },
    "foot.L": {
        "head": (0.18, 0.06, 0.12),
        "tail": (0.18, -0.02, 0.0),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "",
    },
    # Rear right leg
    "thigh.R": {
        "head": (-0.18, 0.05, 0.9),
        "tail": (-0.18, 0.08, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "shin.R": {
        "head": (-0.18, 0.08, 0.5),
        "tail": (-0.18, 0.06, 0.12),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "",
    },
    "foot.R": {
        "head": (-0.18, 0.06, 0.12),
        "tail": (-0.18, -0.02, 0.0),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "",
    },
    # Left wing
    "wing_upper.L": {
        "head": (0.15, -0.35, 1.15),
        "tail": (0.5, -0.3, 1.4),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "wing_fore.L": {
        "head": (0.5, -0.3, 1.4),
        "tail": (0.9, -0.25, 1.3),
        "roll": 0.0,
        "parent": "wing_upper.L",
        "rigify_type": "",
    },
    "wing_tip.L": {
        "head": (0.9, -0.25, 1.3),
        "tail": (1.3, -0.2, 1.15),
        "roll": 0.0,
        "parent": "wing_fore.L",
        "rigify_type": "",
    },
    # Right wing
    "wing_upper.R": {
        "head": (-0.15, -0.35, 1.15),
        "tail": (-0.5, -0.3, 1.4),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "wing_fore.R": {
        "head": (-0.5, -0.3, 1.4),
        "tail": (-0.9, -0.25, 1.3),
        "roll": 0.0,
        "parent": "wing_upper.R",
        "rigify_type": "",
    },
    "wing_tip.R": {
        "head": (-0.9, -0.25, 1.3),
        "tail": (-1.3, -0.2, 1.15),
        "roll": 0.0,
        "parent": "wing_fore.R",
        "rigify_type": "",
    },
    # Wing membrane finger bones
    "wing_finger_1.L": {
        "head": (1.3, -0.2, 1.15),
        "tail": (1.5, -0.18, 1.0),
        "roll": 0.0,
        "parent": "wing_tip.L",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_2.L": {
        "head": (1.3, -0.2, 1.15),
        "tail": (1.55, -0.19, 1.05),
        "roll": 0.0,
        "parent": "wing_tip.L",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_3.L": {
        "head": (1.3, -0.2, 1.15),
        "tail": (1.6, -0.2, 1.1),
        "roll": 0.0,
        "parent": "wing_tip.L",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_4.L": {
        "head": (1.3, -0.2, 1.15),
        "tail": (1.55, -0.21, 1.15),
        "roll": 0.0,
        "parent": "wing_tip.L",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_5.L": {
        "head": (1.3, -0.2, 1.15),
        "tail": (1.5, -0.22, 1.2),
        "roll": 0.0,
        "parent": "wing_tip.L",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_1.R": {
        "head": (-1.3, -0.2, 1.15),
        "tail": (-1.5, -0.18, 1.0),
        "roll": 0.0,
        "parent": "wing_tip.R",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_2.R": {
        "head": (-1.3, -0.2, 1.15),
        "tail": (-1.55, -0.19, 1.05),
        "roll": 0.0,
        "parent": "wing_tip.R",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_3.R": {
        "head": (-1.3, -0.2, 1.15),
        "tail": (-1.6, -0.2, 1.1),
        "roll": 0.0,
        "parent": "wing_tip.R",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_4.R": {
        "head": (-1.3, -0.2, 1.15),
        "tail": (-1.55, -0.21, 1.15),
        "roll": 0.0,
        "parent": "wing_tip.R",
        "rigify_type": "basic.copy_chain",
    },
    "wing_finger_5.R": {
        "head": (-1.3, -0.2, 1.15),
        "tail": (-1.5, -0.22, 1.2),
        "roll": 0.0,
        "parent": "wing_tip.R",
        "rigify_type": "basic.copy_chain",
    },
    # Twist bones
    "upper_arm_twist.L": {
        "head": (0.2, -0.535, 0.725),
        "tail": (0.2, -0.525, 0.6),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist.R": {
        "head": (-0.2, -0.535, 0.725),
        "tail": (-0.2, -0.525, 0.6),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.L": {
        "head": (0.2, -0.51, 0.35),
        "tail": (0.2, -0.505, 0.25),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.R": {
        "head": (-0.2, -0.51, 0.35),
        "tail": (-0.2, -0.505, 0.25),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.L": {
        "head": (0.18, 0.065, 0.7),
        "tail": (0.18, 0.07, 0.6),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.R": {
        "head": (-0.18, 0.065, 0.7),
        "tail": (-0.18, 0.07, 0.6),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.L": {
        "head": (0.18, 0.07, 0.31),
        "tail": (0.18, 0.065, 0.21),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.R": {
        "head": (-0.18, 0.07, 0.31),
        "tail": (-0.18, 0.065, 0.21),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
    # Tail chain (4 bones)
    "tail": {
        "head": (0.0, 0.15, 0.98),
        "tail": (0.0, 0.4, 0.9),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "spines.basic_tail",
    },
    "tail.001": {
        "head": (0.0, 0.4, 0.9),
        "tail": (0.0, 0.65, 0.8),
        "roll": 0.0,
        "parent": "tail",
        "rigify_type": "",
    },
    "tail.002": {
        "head": (0.0, 0.65, 0.8),
        "tail": (0.0, 0.85, 0.68),
        "roll": 0.0,
        "parent": "tail.001",
        "rigify_type": "",
    },
    "tail.003": {
        "head": (0.0, 0.85, 0.68),
        "tail": (0.0, 1.0, 0.55),
        "roll": 0.0,
        "parent": "tail.002",
        "rigify_type": "",
    },
}


MULTI_ARMED_BONES: dict[str, dict] = {
    # Root motion bone
    "root": {
        "head": (0.0, 0.0, 0.0),
        "tail": (0.0, 0.0, 0.1),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "",
    },
    # Humanoid spine (4 bones)
    "spine": {
        "head": (0.0, 0.0, 0.95),
        "tail": (0.0, 0.0, 1.1),
        "roll": 0.0,
        "parent": "root",
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, 0.0, 1.1),
        "tail": (0.0, 0.0, 1.25),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, 0.0, 1.25),
        "tail": (0.0, 0.0, 1.4),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    "spine.003": {
        "head": (0.0, 0.0, 1.4),
        "tail": (0.0, 0.0, 1.55),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    # Head
    "spine.004": {
        "head": (0.0, 0.0, 1.55),
        "tail": (0.0, 0.0, 1.65),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "",
    },
    "spine.005": {
        "head": (0.0, 0.0, 1.65),
        "tail": (0.0, 0.0, 1.8),
        "roll": 0.0,
        "parent": "spine.004",
        "rigify_type": "",
    },
    # Arm pair 1 (upper) -- L/R
    "upper_arm.L": {
        "head": (0.18, 0.0, 1.5),
        "tail": (0.4, 0.0, 1.5),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "limbs.arm",
    },
    "forearm.L": {
        "head": (0.4, 0.0, 1.5),
        "tail": (0.62, 0.0, 1.5),
        "roll": 1.5708,
        "parent": "upper_arm.L",
        "rigify_type": "",
    },
    "hand.L": {
        "head": (0.62, 0.0, 1.5),
        "tail": (0.72, 0.0, 1.5),
        "roll": 0.0,
        "parent": "forearm.L",
        "rigify_type": "",
    },
    "upper_arm.R": {
        "head": (-0.18, 0.0, 1.5),
        "tail": (-0.4, 0.0, 1.5),
        "roll": 0.0,
        "parent": "spine.003",
        "rigify_type": "limbs.arm",
    },
    "forearm.R": {
        "head": (-0.4, 0.0, 1.5),
        "tail": (-0.62, 0.0, 1.5),
        "roll": -1.5708,
        "parent": "upper_arm.R",
        "rigify_type": "",
    },
    "hand.R": {
        "head": (-0.62, 0.0, 1.5),
        "tail": (-0.72, 0.0, 1.5),
        "roll": 0.0,
        "parent": "forearm.R",
        "rigify_type": "",
    },
    # Arm pair 2 (lower) -- L/R
    "upper_arm_lower.L": {
        "head": (0.18, 0.0, 1.3),
        "tail": (0.38, 0.02, 1.3),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "forearm_lower.L": {
        "head": (0.38, 0.02, 1.3),
        "tail": (0.58, 0.04, 1.3),
        "roll": 1.5708,
        "parent": "upper_arm_lower.L",
        "rigify_type": "",
    },
    "hand_lower.L": {
        "head": (0.58, 0.04, 1.3),
        "tail": (0.68, 0.04, 1.3),
        "roll": 0.0,
        "parent": "forearm_lower.L",
        "rigify_type": "",
    },
    "upper_arm_lower.R": {
        "head": (-0.18, 0.0, 1.3),
        "tail": (-0.38, 0.02, 1.3),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "limbs.arm",
    },
    "forearm_lower.R": {
        "head": (-0.38, 0.02, 1.3),
        "tail": (-0.58, 0.04, 1.3),
        "roll": -1.5708,
        "parent": "upper_arm_lower.R",
        "rigify_type": "",
    },
    "hand_lower.R": {
        "head": (-0.58, 0.04, 1.3),
        "tail": (-0.68, 0.04, 1.3),
        "roll": 0.0,
        "parent": "forearm_lower.R",
        "rigify_type": "",
    },
    # Legs
    "thigh.L": {
        "head": (0.1, 0.0, 0.95),
        "tail": (0.1, 0.0, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.L": {
        "head": (0.1, 0.0, 0.5),
        "tail": (0.1, 0.0, 0.08),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "",
    },
    "foot.L": {
        "head": (0.1, 0.0, 0.08),
        "tail": (0.1, -0.1, 0.0),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "",
    },
    "thigh.R": {
        "head": (-0.1, 0.0, 0.95),
        "tail": (-0.1, 0.0, 0.5),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.leg",
    },
    "shin.R": {
        "head": (-0.1, 0.0, 0.5),
        "tail": (-0.1, 0.0, 0.08),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "",
    },
    "foot.R": {
        "head": (-0.1, 0.0, 0.08),
        "tail": (-0.1, -0.1, 0.0),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "",
    },
    # Twist bones
    "upper_arm_twist.L": {
        "head": (0.29, 0.0, 1.5),
        "tail": (0.35, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.L",
        "rigify_type": "basic.super_copy",
    },
    "upper_arm_twist.R": {
        "head": (-0.29, 0.0, 1.5),
        "tail": (-0.35, 0.0, 1.5),
        "roll": 0.0,
        "parent": "upper_arm.R",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.L": {
        "head": (0.51, 0.0, 1.5),
        "tail": (0.57, 0.0, 1.5),
        "roll": 1.5708,
        "parent": "forearm.L",
        "rigify_type": "basic.super_copy",
    },
    "forearm_twist.R": {
        "head": (-0.51, 0.0, 1.5),
        "tail": (-0.57, 0.0, 1.5),
        "roll": -1.5708,
        "parent": "forearm.R",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.L": {
        "head": (0.1, 0.0, 0.73),
        "tail": (0.1, 0.0, 0.67),
        "roll": 0.0,
        "parent": "thigh.L",
        "rigify_type": "basic.super_copy",
    },
    "thigh_twist.R": {
        "head": (-0.1, 0.0, 0.73),
        "tail": (-0.1, 0.0, 0.67),
        "roll": 0.0,
        "parent": "thigh.R",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.L": {
        "head": (0.1, 0.0, 0.29),
        "tail": (0.1, 0.0, 0.23),
        "roll": 0.0,
        "parent": "shin.L",
        "rigify_type": "basic.super_copy",
    },
    "shin_twist.R": {
        "head": (-0.1, 0.0, 0.29),
        "tail": (-0.1, 0.0, 0.23),
        "roll": 0.0,
        "parent": "shin.R",
        "rigify_type": "basic.super_copy",
    },
}


ARACHNID_BONES: dict[str, dict] = {
    # Cephalothorax spine (2 bones)
    "spine": {
        "head": (0.0, 0.0, 0.35),
        "tail": (0.0, -0.15, 0.37),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, -0.15, 0.37),
        "tail": (0.0, -0.3, 0.38),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    # Head
    "spine.002": {
        "head": (0.0, -0.3, 0.38),
        "tail": (0.0, -0.4, 0.4),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Mandibles L/R
    "mandible.L": {
        "head": (0.03, -0.4, 0.37),
        "tail": (0.05, -0.48, 0.34),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "basic.super_copy",
    },
    "mandible.R": {
        "head": (-0.03, -0.4, 0.37),
        "tail": (-0.05, -0.48, 0.34),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "basic.super_copy",
    },
    # Leg pair 1 (front) L/R
    "leg_1.L": {
        "head": (0.08, -0.28, 0.33),
        "tail": (0.2, -0.32, 0.2),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_1_lower.L": {
        "head": (0.2, -0.32, 0.2),
        "tail": (0.3, -0.35, 0.0),
        "roll": 0.0,
        "parent": "leg_1.L",
        "rigify_type": "",
    },
    "leg_1_foot.L": {
        "head": (0.3, -0.35, 0.0),
        "tail": (0.32, -0.37, -0.02),
        "roll": 0.0,
        "parent": "leg_1_lower.L",
        "rigify_type": "",
    },
    "leg_1.R": {
        "head": (-0.08, -0.28, 0.33),
        "tail": (-0.2, -0.32, 0.2),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_1_lower.R": {
        "head": (-0.2, -0.32, 0.2),
        "tail": (-0.3, -0.35, 0.0),
        "roll": 0.0,
        "parent": "leg_1.R",
        "rigify_type": "",
    },
    "leg_1_foot.R": {
        "head": (-0.3, -0.35, 0.0),
        "tail": (-0.32, -0.37, -0.02),
        "roll": 0.0,
        "parent": "leg_1_lower.R",
        "rigify_type": "",
    },
    # Leg pair 2 L/R
    "leg_2.L": {
        "head": (0.08, -0.18, 0.33),
        "tail": (0.22, -0.2, 0.2),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_2_lower.L": {
        "head": (0.22, -0.2, 0.2),
        "tail": (0.32, -0.22, 0.0),
        "roll": 0.0,
        "parent": "leg_2.L",
        "rigify_type": "",
    },
    "leg_2_foot.L": {
        "head": (0.32, -0.22, 0.0),
        "tail": (0.34, -0.24, -0.02),
        "roll": 0.0,
        "parent": "leg_2_lower.L",
        "rigify_type": "",
    },
    "leg_2.R": {
        "head": (-0.08, -0.18, 0.33),
        "tail": (-0.22, -0.2, 0.2),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "limbs.front_paw",
    },
    "leg_2_lower.R": {
        "head": (-0.22, -0.2, 0.2),
        "tail": (-0.32, -0.22, 0.0),
        "roll": 0.0,
        "parent": "leg_2.R",
        "rigify_type": "",
    },
    "leg_2_foot.R": {
        "head": (-0.32, -0.22, 0.0),
        "tail": (-0.34, -0.24, -0.02),
        "roll": 0.0,
        "parent": "leg_2_lower.R",
        "rigify_type": "",
    },
    # Leg pair 3 L/R
    "leg_3.L": {
        "head": (0.08, -0.05, 0.33),
        "tail": (0.22, -0.04, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_3_lower.L": {
        "head": (0.22, -0.04, 0.2),
        "tail": (0.32, -0.03, 0.0),
        "roll": 0.0,
        "parent": "leg_3.L",
        "rigify_type": "",
    },
    "leg_3_foot.L": {
        "head": (0.32, -0.03, 0.0),
        "tail": (0.34, -0.05, -0.02),
        "roll": 0.0,
        "parent": "leg_3_lower.L",
        "rigify_type": "",
    },
    "leg_3.R": {
        "head": (-0.08, -0.05, 0.33),
        "tail": (-0.22, -0.04, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_3_lower.R": {
        "head": (-0.22, -0.04, 0.2),
        "tail": (-0.32, -0.03, 0.0),
        "roll": 0.0,
        "parent": "leg_3.R",
        "rigify_type": "",
    },
    "leg_3_foot.R": {
        "head": (-0.32, -0.03, 0.0),
        "tail": (-0.34, -0.05, -0.02),
        "roll": 0.0,
        "parent": "leg_3_lower.R",
        "rigify_type": "",
    },
    # Leg pair 4 (rear) L/R
    "leg_4.L": {
        "head": (0.08, 0.08, 0.33),
        "tail": (0.2, 0.12, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_4_lower.L": {
        "head": (0.2, 0.12, 0.2),
        "tail": (0.3, 0.15, 0.0),
        "roll": 0.0,
        "parent": "leg_4.L",
        "rigify_type": "",
    },
    "leg_4_foot.L": {
        "head": (0.3, 0.15, 0.0),
        "tail": (0.32, 0.13, -0.02),
        "roll": 0.0,
        "parent": "leg_4_lower.L",
        "rigify_type": "",
    },
    "leg_4.R": {
        "head": (-0.08, 0.08, 0.33),
        "tail": (-0.2, 0.12, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.rear_paw",
    },
    "leg_4_lower.R": {
        "head": (-0.2, 0.12, 0.2),
        "tail": (-0.3, 0.15, 0.0),
        "roll": 0.0,
        "parent": "leg_4.R",
        "rigify_type": "",
    },
    "leg_4_foot.R": {
        "head": (-0.3, 0.15, 0.0),
        "tail": (-0.32, 0.13, -0.02),
        "roll": 0.0,
        "parent": "leg_4_lower.R",
        "rigify_type": "",
    },
    # Optional tail
    "tail": {
        "head": (0.0, 0.15, 0.33),
        "tail": (0.0, 0.3, 0.28),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "spines.basic_tail",
    },
    "tail.001": {
        "head": (0.0, 0.3, 0.28),
        "tail": (0.0, 0.42, 0.22),
        "roll": 0.0,
        "parent": "tail",
        "rigify_type": "",
    },
}


AMORPHOUS_BONES: dict[str, dict] = {
    # Flexible spine (3 bones)
    "spine": {
        "head": (0.0, 0.0, 0.3),
        "tail": (0.0, 0.0, 0.45),
        "roll": 0.0,
        "parent": None,
        "rigify_type": "spines.super_spine",
    },
    "spine.001": {
        "head": (0.0, 0.0, 0.45),
        "tail": (0.0, 0.0, 0.6),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "",
    },
    "spine.002": {
        "head": (0.0, 0.0, 0.6),
        "tail": (0.0, 0.0, 0.72),
        "roll": 0.0,
        "parent": "spine.001",
        "rigify_type": "",
    },
    # Head
    "spine.003": {
        "head": (0.0, 0.0, 0.72),
        "tail": (0.0, 0.0, 0.85),
        "roll": 0.0,
        "parent": "spine.002",
        "rigify_type": "",
    },
    # Tentacle 1 L/R
    "tentacle_1.L": {
        "head": (0.1, -0.05, 0.4),
        "tail": (0.2, -0.1, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_1.L.001": {
        "head": (0.2, -0.1, 0.2),
        "tail": (0.28, -0.14, 0.05),
        "roll": 0.0,
        "parent": "tentacle_1.L",
        "rigify_type": "",
    },
    "tentacle_1.R": {
        "head": (-0.1, -0.05, 0.4),
        "tail": (-0.2, -0.1, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_1.R.001": {
        "head": (-0.2, -0.1, 0.2),
        "tail": (-0.28, -0.14, 0.05),
        "roll": 0.0,
        "parent": "tentacle_1.R",
        "rigify_type": "",
    },
    # Tentacle 2 L/R
    "tentacle_2.L": {
        "head": (0.1, 0.05, 0.4),
        "tail": (0.2, 0.1, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_2.L.001": {
        "head": (0.2, 0.1, 0.2),
        "tail": (0.28, 0.14, 0.05),
        "roll": 0.0,
        "parent": "tentacle_2.L",
        "rigify_type": "",
    },
    "tentacle_2.R": {
        "head": (-0.1, 0.05, 0.4),
        "tail": (-0.2, 0.1, 0.2),
        "roll": 0.0,
        "parent": "spine",
        "rigify_type": "limbs.simple_tentacle",
    },
    "tentacle_2.R.001": {
        "head": (-0.2, 0.1, 0.2),
        "tail": (-0.28, 0.14, 0.05),
        "roll": 0.0,
        "parent": "tentacle_2.R",
        "rigify_type": "",
    },
}


# ---------------------------------------------------------------------------
# Template catalog
# ---------------------------------------------------------------------------

TEMPLATE_CATALOG: dict[str, dict[str, dict]] = {
    "humanoid": HUMANOID_BONES,
    "quadruped": QUADRUPED_BONES,
    "bird": BIRD_BONES,
    "insect": INSECT_BONES,
    "serpent": SERPENT_BONES,
    "floating": FLOATING_BONES,
    "dragon": DRAGON_BONES,
    "multi_armed": MULTI_ARMED_BONES,
    "arachnid": ARACHNID_BONES,
    "amorphous": AMORPHOUS_BONES,
}


# ---------------------------------------------------------------------------
# Limb library -- mix-and-match bone segment functions
# ---------------------------------------------------------------------------

def _arm_pair_bones() -> dict[str, dict]:
    """Return bone defs for a standard arm pair (L/R)."""
    return {
        "upper_arm.L": {
            "head": (0.18, 0.0, 1.5), "tail": (0.4, 0.0, 1.5),
            "roll": 0.0, "parent": "spine.003", "rigify_type": "limbs.arm",
        },
        "forearm.L": {
            "head": (0.4, 0.0, 1.5), "tail": (0.62, 0.0, 1.5),
            "roll": 1.5708, "parent": "upper_arm.L", "rigify_type": "",
        },
        "hand.L": {
            "head": (0.62, 0.0, 1.5), "tail": (0.72, 0.0, 1.5),
            "roll": 0.0, "parent": "forearm.L", "rigify_type": "",
        },
        "upper_arm.R": {
            "head": (-0.18, 0.0, 1.5), "tail": (-0.4, 0.0, 1.5),
            "roll": 0.0, "parent": "spine.003", "rigify_type": "limbs.arm",
        },
        "forearm.R": {
            "head": (-0.4, 0.0, 1.5), "tail": (-0.62, 0.0, 1.5),
            "roll": -1.5708, "parent": "upper_arm.R", "rigify_type": "",
        },
        "hand.R": {
            "head": (-0.62, 0.0, 1.5), "tail": (-0.72, 0.0, 1.5),
            "roll": 0.0, "parent": "forearm.R", "rigify_type": "",
        },
    }


def _leg_pair_bones() -> dict[str, dict]:
    """Return bone defs for a standard leg pair (L/R)."""
    return {
        "thigh.L": {
            "head": (0.1, 0.0, 0.95), "tail": (0.1, 0.0, 0.5),
            "roll": 0.0, "parent": "spine", "rigify_type": "limbs.leg",
        },
        "shin.L": {
            "head": (0.1, 0.0, 0.5), "tail": (0.1, 0.0, 0.08),
            "roll": 0.0, "parent": "thigh.L", "rigify_type": "",
        },
        "foot.L": {
            "head": (0.1, 0.0, 0.08), "tail": (0.1, -0.1, 0.0),
            "roll": 0.0, "parent": "shin.L", "rigify_type": "",
        },
        "thigh.R": {
            "head": (-0.1, 0.0, 0.95), "tail": (-0.1, 0.0, 0.5),
            "roll": 0.0, "parent": "spine", "rigify_type": "limbs.leg",
        },
        "shin.R": {
            "head": (-0.1, 0.0, 0.5), "tail": (-0.1, 0.0, 0.08),
            "roll": 0.0, "parent": "thigh.R", "rigify_type": "",
        },
        "foot.R": {
            "head": (-0.1, 0.0, 0.08), "tail": (-0.1, -0.1, 0.0),
            "roll": 0.0, "parent": "shin.R", "rigify_type": "",
        },
    }


def _paw_leg_pair_bones(side: str = "front") -> dict[str, dict]:
    """Return bone defs for a paw leg pair (front or rear)."""
    rigify_type = "limbs.front_paw" if side == "front" else "limbs.rear_paw"
    if side == "front":
        return {
            "upper_arm.L": {
                "head": (0.15, -0.45, 0.7), "tail": (0.15, -0.43, 0.4),
                "roll": 0.0, "parent": "spine.002", "rigify_type": rigify_type,
            },
            "forearm.L": {
                "head": (0.15, -0.43, 0.4), "tail": (0.15, -0.42, 0.1),
                "roll": 1.5708, "parent": "upper_arm.L", "rigify_type": "",
            },
            "hand.L": {
                "head": (0.15, -0.42, 0.1), "tail": (0.15, -0.42, 0.0),
                "roll": 0.0, "parent": "forearm.L", "rigify_type": "",
            },
            "upper_arm.R": {
                "head": (-0.15, -0.45, 0.7), "tail": (-0.15, -0.43, 0.4),
                "roll": 0.0, "parent": "spine.002", "rigify_type": rigify_type,
            },
            "forearm.R": {
                "head": (-0.15, -0.43, 0.4), "tail": (-0.15, -0.42, 0.1),
                "roll": -1.5708, "parent": "upper_arm.R", "rigify_type": "",
            },
            "hand.R": {
                "head": (-0.15, -0.42, 0.1), "tail": (-0.15, -0.42, 0.0),
                "roll": 0.0, "parent": "forearm.R", "rigify_type": "",
            },
        }
    else:
        return {
            "thigh.L": {
                "head": (0.12, 0.05, 0.75), "tail": (0.12, 0.07, 0.4),
                "roll": 0.0, "parent": "spine", "rigify_type": rigify_type,
            },
            "shin.L": {
                "head": (0.12, 0.07, 0.4), "tail": (0.12, 0.05, 0.1),
                "roll": 0.0, "parent": "thigh.L", "rigify_type": "",
            },
            "foot.L": {
                "head": (0.12, 0.05, 0.1), "tail": (0.12, -0.05, 0.0),
                "roll": 0.0, "parent": "shin.L", "rigify_type": "",
            },
            "thigh.R": {
                "head": (-0.12, 0.05, 0.75), "tail": (-0.12, 0.07, 0.4),
                "roll": 0.0, "parent": "spine", "rigify_type": rigify_type,
            },
            "shin.R": {
                "head": (-0.12, 0.07, 0.4), "tail": (-0.12, 0.05, 0.1),
                "roll": 0.0, "parent": "thigh.R", "rigify_type": "",
            },
            "foot.R": {
                "head": (-0.12, 0.05, 0.1), "tail": (-0.12, -0.05, 0.0),
                "roll": 0.0, "parent": "shin.R", "rigify_type": "",
            },
        }


def _wing_pair_bones() -> dict[str, dict]:
    """Return bone defs for a wing pair (L/R)."""
    return {
        "wing_upper.L": {
            "head": (0.15, -0.35, 1.15), "tail": (0.5, -0.3, 1.4),
            "roll": 0.0, "parent": "spine.002", "rigify_type": "limbs.arm",
        },
        "wing_fore.L": {
            "head": (0.5, -0.3, 1.4), "tail": (0.9, -0.25, 1.3),
            "roll": 0.0, "parent": "wing_upper.L", "rigify_type": "",
        },
        "wing_tip.L": {
            "head": (0.9, -0.25, 1.3), "tail": (1.3, -0.2, 1.15),
            "roll": 0.0, "parent": "wing_fore.L", "rigify_type": "",
        },
        "wing_upper.R": {
            "head": (-0.15, -0.35, 1.15), "tail": (-0.5, -0.3, 1.4),
            "roll": 0.0, "parent": "spine.002", "rigify_type": "limbs.arm",
        },
        "wing_fore.R": {
            "head": (-0.5, -0.3, 1.4), "tail": (-0.9, -0.25, 1.3),
            "roll": 0.0, "parent": "wing_upper.R", "rigify_type": "",
        },
        "wing_tip.R": {
            "head": (-0.9, -0.25, 1.3), "tail": (-1.3, -0.2, 1.15),
            "roll": 0.0, "parent": "wing_fore.R", "rigify_type": "",
        },
    }


def _tail_chain_bones(length: int = 3) -> dict[str, dict]:
    """Return bone defs for a tail chain of given length."""
    bones: dict[str, dict] = {}
    y_start = 0.15
    z_start = 0.78
    for i in range(length):
        name = "tail" if i == 0 else f"tail.{i:03d}"
        parent = None if i == 0 else ("tail" if i == 1 else f"tail.{i - 1:03d}")
        y = y_start + i * 0.2
        z = z_start - i * 0.07
        bones[name] = {
            "head": (0.0, y, z),
            "tail": (0.0, y + 0.2, z - 0.07),
            "roll": 0.0,
            "parent": parent if i > 0 else "spine",
            "rigify_type": "spines.basic_tail" if i == 0 else "",
        }
    return bones


def _head_chain_bones() -> dict[str, dict]:
    """Return bone defs for a neck + head chain."""
    return {
        "spine.004": {
            "head": (0.0, 0.0, 1.55), "tail": (0.0, 0.0, 1.65),
            "roll": 0.0, "parent": "spine.003", "rigify_type": "",
        },
        "spine.005": {
            "head": (0.0, 0.0, 1.65), "tail": (0.0, 0.0, 1.8),
            "roll": 0.0, "parent": "spine.004", "rigify_type": "",
        },
    }


def _jaw_bones() -> dict[str, dict]:
    """Return bone defs for a jaw bone."""
    return {
        "jaw": {
            "head": (0.0, -1.12, 1.38), "tail": (0.0, -1.25, 1.3),
            "roll": 0.0, "parent": "spine.005", "rigify_type": "basic.super_copy",
        },
    }


def _tentacle_chain_bones(count: int = 4) -> dict[str, dict]:
    """Return bone defs for tentacle chains radiating from spine."""
    import math
    bones: dict[str, dict] = {}
    for i in range(count):
        angle = (2.0 * math.pi * i) / count
        x = 0.1 * math.cos(angle)
        y = 0.1 * math.sin(angle)
        name = f"tentacle_{i}"
        child = f"tentacle_{i}.001"
        bones[name] = {
            "head": (x, y, 0.48),
            "tail": (x * 2, y * 2, 0.3),
            "roll": 0.0,
            "parent": "spine",
            "rigify_type": "limbs.simple_tentacle",
        }
        bones[child] = {
            "head": (x * 2, y * 2, 0.3),
            "tail": (x * 2.8, y * 2.8, 0.12),
            "roll": 0.0,
            "parent": name,
            "rigify_type": "",
        }
    return bones


def _insect_leg_pair_bones(index: int = 0) -> dict[str, dict]:
    """Return bone defs for one insect leg pair at the given index (0-2)."""
    y_offsets = [-0.25, -0.12, 0.02]
    y = y_offsets[min(index, 2)]
    prefix = ["leg_front", "leg_mid", "leg_rear"][min(index, 2)]
    rigify_type = "limbs.front_paw" if index < 2 else "limbs.rear_paw"
    parent = "spine.001" if index == 0 else "spine"
    return {
        f"{prefix}.L": {
            "head": (0.08, y, 0.28), "tail": (0.18, y + 0.01, 0.15),
            "roll": 0.0, "parent": parent, "rigify_type": rigify_type,
        },
        f"{prefix}_lower.L": {
            "head": (0.18, y + 0.01, 0.15), "tail": (0.24, y + 0.02, 0.0),
            "roll": 0.0, "parent": f"{prefix}.L", "rigify_type": "",
        },
        f"{prefix}_foot.L": {
            "head": (0.24, y + 0.02, 0.0), "tail": (0.26, y, -0.02),
            "roll": 0.0, "parent": f"{prefix}_lower.L", "rigify_type": "",
        },
        f"{prefix}.R": {
            "head": (-0.08, y, 0.28), "tail": (-0.18, y + 0.01, 0.15),
            "roll": 0.0, "parent": parent, "rigify_type": rigify_type,
        },
        f"{prefix}_lower.R": {
            "head": (-0.18, y + 0.01, 0.15), "tail": (-0.24, y + 0.02, 0.0),
            "roll": 0.0, "parent": f"{prefix}.R", "rigify_type": "",
        },
        f"{prefix}_foot.R": {
            "head": (-0.24, y + 0.02, 0.0), "tail": (-0.26, y, -0.02),
            "roll": 0.0, "parent": f"{prefix}_lower.R", "rigify_type": "",
        },
    }


LIMB_LIBRARY: dict[str, callable] = {
    "arm_pair": _arm_pair_bones,
    "leg_pair": _leg_pair_bones,
    "paw_leg_pair": _paw_leg_pair_bones,
    "wing_pair": _wing_pair_bones,
    "tail_chain": _tail_chain_bones,
    "head_chain": _head_chain_bones,
    "jaw": _jaw_bones,
    "tentacle_chain": _tentacle_chain_bones,
    "insect_leg_pair": _insect_leg_pair_bones,
}


# ---------------------------------------------------------------------------
# Blender-dependent helper functions
# ---------------------------------------------------------------------------

def _compute_bone_scale_offset(
    bone_defs: dict[str, dict],
    mesh_obj,
) -> tuple:
    """Compute scale and offset to fit template bones inside a target mesh.

    Calculates the bounding box of both the template bones and the mesh,
    then returns (scale_factor, offset_vector) to map bones into mesh space.

    Returns:
        (scale: float, offset: tuple[float,float,float])
    """
    # Template bone bounding box
    all_positions = []
    for props in bone_defs.values():
        all_positions.append(props["head"])
        all_positions.append(props["tail"])

    if not all_positions:
        return (1.0, (0.0, 0.0, 0.0))

    t_min_x = min(p[0] for p in all_positions)
    t_max_x = max(p[0] for p in all_positions)
    t_min_z = min(p[2] for p in all_positions)
    t_max_z = max(p[2] for p in all_positions)
    t_height = t_max_z - t_min_z
    t_center_x = (t_min_x + t_max_x) / 2.0

    # Mesh bounding box (in world space)
    bbox_corners = [mesh_obj.matrix_world @ bpy.types.Object.bl_rna.properties["bound_box"].fixed_type(v)
                    for v in mesh_obj.bound_box]
    # Simpler: use mesh bound_box directly
    bb = mesh_obj.bound_box
    loc = mesh_obj.location
    m_min_z = min(v[2] for v in bb) + loc.z
    m_max_z = max(v[2] for v in bb) + loc.z
    m_min_x = min(v[0] for v in bb) + loc.x
    m_max_x = max(v[0] for v in bb) + loc.x
    m_height = m_max_z - m_min_z
    m_center_x = (m_min_x + m_max_x) / 2.0

    if t_height < 0.001:
        scale = 1.0
    else:
        scale = m_height / t_height

    offset_x = m_center_x - t_center_x * scale
    offset_z = m_min_z - t_min_z * scale

    return (scale, (offset_x, 0.0, offset_z))


def _create_template_bones(
    arm_obj,
    bone_defs: dict[str, dict],
    mesh_obj=None,
) -> None:
    """Create metarig bones from a template definition dict.

    Two-pass bone creation (create all bones, then set parents).
    Assigns rigify_types in object mode after bone creation.
    Never stores EditBone references across mode switches.

    If mesh_obj is provided, bones are auto-scaled and positioned to
    fit inside the mesh bounding box.
    """
    # Compute scale/offset if a target mesh is provided
    scale = 1.0
    offset = (0.0, 0.0, 0.0)
    if mesh_obj is not None:
        scale, offset = _compute_bone_scale_offset(bone_defs, mesh_obj)

    ctx = get_3d_context_override()
    bpy.context.view_layer.objects.active = arm_obj

    if ctx:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="EDIT")
    else:
        bpy.ops.object.mode_set(mode="EDIT")

    arm = arm_obj.data

    # First pass: create all bones with positions (scaled + offset)
    for name, props in bone_defs.items():
        bone = arm.edit_bones.new(name)
        h = props["head"]
        t = props["tail"]
        bone.head = (h[0] * scale + offset[0],
                     h[1] * scale + offset[1],
                     h[2] * scale + offset[2])
        bone.tail = (t[0] * scale + offset[0],
                     t[1] * scale + offset[1],
                     t[2] * scale + offset[2])
        bone.roll = props["roll"]

    # Second pass: set parents (all bones exist now)
    for name, props in bone_defs.items():
        if props["parent"]:
            parent_bone = arm.edit_bones.get(props["parent"])
            if parent_bone:
                arm.edit_bones[name].parent = parent_bone
                arm.edit_bones[name].use_connect = (
                    arm.edit_bones[name].head == parent_bone.tail
                )

    if ctx:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="OBJECT")
    else:
        bpy.ops.object.mode_set(mode="OBJECT")

    # Third pass: assign rigify types (must be in object/pose mode)
    for name, props in bone_defs.items():
        rt = props.get("rigify_type", "")
        if rt:
            arm_obj.pose.bones[name].rigify_type = rt


def _generate_rig(metarig_obj) -> object:
    """Generate a control rig from a Rigify metarig.

    Enables the Rigify addon if needed, then calls generate_rig().
    Returns the generated rig object.
    """
    # Ensure Rigify is enabled
    import addon_utils
    addon_utils.enable("rigify")

    import rigify.generate

    bpy.context.view_layer.objects.active = metarig_obj
    rigify.generate.generate_rig(bpy.context, metarig_obj)
    return bpy.context.view_layer.objects.active


def _fix_deform_hierarchy(rig_obj) -> int:
    """Re-parent DEF bones into a single connected hierarchy for game export.

    Rigify splits DEF bones into disconnected chains per module, which breaks
    FBX export for Unity. This re-parents them using ORG bone parentage as
    reference.

    Returns the number of DEF bones that were re-parented.
    """
    ctx = get_3d_context_override()
    bpy.context.view_layer.objects.active = rig_obj

    if ctx:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="EDIT")
    else:
        bpy.ops.object.mode_set(mode="EDIT")

    arm = rig_obj.data
    reparented = 0

    for bone in arm.edit_bones:
        if not bone.name.startswith("DEF-"):
            continue
        if bone.parent and bone.parent.name.startswith("DEF-"):
            continue  # Already has a DEF parent

        # Find corresponding ORG bone to determine logical parent
        org_name = "ORG-" + bone.name[4:]
        org_bone = arm.edit_bones.get(org_name)
        if org_bone and org_bone.parent:
            # Look for the DEF equivalent of the ORG parent
            org_parent = org_bone.parent
            # Handle ORG parent that might have a prefix
            if org_parent.name.startswith("ORG-"):
                def_parent_name = "DEF-" + org_parent.name[4:]
            else:
                def_parent_name = "DEF-" + org_parent.name
            def_parent = arm.edit_bones.get(def_parent_name)
            if def_parent:
                bone.parent = def_parent
                reparented += 1

    if ctx:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="OBJECT")
    else:
        bpy.ops.object.mode_set(mode="OBJECT")

    return reparented
