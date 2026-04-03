"""Pure-logic keyframe engine and gait/attack/reaction configuration dicts.

This module contains ZERO Blender imports. All functions return keyframe data
(lists of Keyframe namedtuples) that Blender-dependent handlers consume.
This separation enables full test coverage without a running Blender instance.

Gait configs use DEF-prefixed bone names matching Rigify output from Phase 4
rigging templates (rigging_templates.py).
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Core data type
# ---------------------------------------------------------------------------

class Keyframe(NamedTuple):
    """A single keyframe datum for one bone channel at one frame."""
    bone_name: str      # e.g. "DEF-thigh.L"
    channel: str        # "rotation_euler" or "location"
    axis: int           # 0=X, 1=Y, 2=Z
    frame: int
    value: float


# ---------------------------------------------------------------------------
# Gait configuration dicts
# ---------------------------------------------------------------------------
# Each config dict has:
#   "name": str identifier
#   "frame_count": int (default frames per cycle)
#   "bones": dict mapping DEF-bone names to
#       {"channel", "axis", "amplitude", "phase", "offset"(optional)}

BIPED_WALK_CONFIG: dict = {
    "name": "biped_walk",
    "frame_count": 24,
    "bones": {
        # Legs -- multi-harmonic thighs for natural foot-plant timing
        "DEF-thigh.L": {
            "channel": "rotation_euler", "axis": 0,
            "harmonics": [
                {"amp": 0.5, "phase": 0.0},
                {"amp": 0.15, "phase": 0.3},
                {"amp": 0.05, "phase": 0.8},
            ],
        },
        "DEF-thigh.R": {
            "channel": "rotation_euler", "axis": 0,
            "harmonics": [
                {"amp": 0.5, "phase": math.pi},
                {"amp": 0.15, "phase": math.pi + 0.3},
                {"amp": 0.05, "phase": math.pi + 0.8},
            ],
        },
        "DEF-shin.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.5,
        },
        "DEF-shin.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi + 0.5,
        },
        "DEF-foot.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": 1.0,
        },
        "DEF-foot.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": math.pi + 1.0,
        },
        # Arm swing -- opposite to legs
        "DEF-upper_arm.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": math.pi,
        },
        "DEF-upper_arm.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": 0.0,
        },
        # Hip bob (2x frequency via 2*pi phase trick - approximated as Z translation)
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.02, "phase": 0.0,
        },
        # Pelvis lateral sway (composite key for second channel on spine)
        "DEF-spine__sway": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.015, "phase": math.pi / 2,
        },
        # Spine counter-rotation
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.05, "phase": 0.0,
        },
        # Head stabilization (dampened inverse of spine motion)
        "DEF-spine.004": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.01, "phase": math.pi,
        },
    },
}

BIPED_RUN_CONFIG: dict = {
    "name": "biped_run",
    "frame_count": 16,
    "bones": {
        # Legs -- larger multi-harmonic thighs for running
        "DEF-thigh.L": {
            "channel": "rotation_euler", "axis": 0,
            "harmonics": [
                {"amp": 0.8, "phase": 0.0},
                {"amp": 0.2, "phase": 0.3},
                {"amp": 0.08, "phase": 0.8},
            ],
        },
        "DEF-thigh.R": {
            "channel": "rotation_euler", "axis": 0,
            "harmonics": [
                {"amp": 0.8, "phase": math.pi},
                {"amp": 0.2, "phase": math.pi + 0.3},
                {"amp": 0.08, "phase": math.pi + 0.8},
            ],
        },
        "DEF-shin.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.6, "phase": 0.5,
        },
        "DEF-shin.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.6, "phase": math.pi + 0.5,
        },
        "DEF-foot.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": 1.0,
        },
        "DEF-foot.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": math.pi + 1.0,
        },
        # Arm swing -- opposite to legs
        "DEF-upper_arm.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": math.pi,
        },
        "DEF-upper_arm.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": 0.0,
        },
        # Hip bob
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.04, "phase": 0.0,
        },
        # Pelvis lateral sway (composite key for second channel on spine)
        "DEF-spine__sway": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.025, "phase": math.pi / 2,
        },
        # Spine counter-rotation
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.08, "phase": 0.0,
        },
        # Head stabilization (dampened inverse of spine motion)
        "DEF-spine.004": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.015, "phase": math.pi,
        },
    },
}


# Quadruped: diagonal pairs (FL+RR vs FR+RL) -- phases: 0, pi, pi/2, 3pi/2
# Quadruped: 4-beat lateral sequence walk (LH->LF->RH->RF, each leg independent)
QUADRUPED_WALK_CONFIG: dict = {
    "name": "quadruped_walk",
    "frame_count": 32,
    "bones": {
        # 4-beat: each leg at quarter-cycle offset
        "DEF-thigh.L":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": 0.0},
        "DEF-shin.L":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": 0.5},
        "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": math.pi / 2},
        "DEF-forearm.L":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": math.pi / 2 + 0.5},
        "DEF-thigh.R":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": math.pi},
        "DEF-shin.R":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": math.pi + 0.5},
        "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": 3 * math.pi / 2},
        "DEF-forearm.R":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": 3 * math.pi / 2 + 0.5},
        "DEF-spine.001":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.04, "phase": 0.0},
        "DEF-spine.002":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.04, "phase": math.pi / 2},
    },
}

# Quadruped trot: 2-beat diagonal pairs (FL+RR vs FR+RL)
QUADRUPED_TROT_CONFIG: dict = {
    "name": "quadruped_trot",
    "frame_count": 24,
    "bones": {
        "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": 0.0},
        "DEF-forearm.L":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": 0.5},
        "DEF-thigh.R":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": 0.0},
        "DEF-shin.R":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": 0.5},
        "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": math.pi},
        "DEF-forearm.R":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": math.pi + 0.5},
        "DEF-thigh.L":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.5, "phase": math.pi},
        "DEF-shin.L":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.3, "phase": math.pi + 0.5},
        "DEF-spine.001":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.04, "phase": 0.0},
        "DEF-spine.002":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.04, "phase": math.pi / 2},
    },
}

# Quadruped canter: 3-beat asymmetric (RH -> LH+RF -> LF)
QUADRUPED_CANTER_CONFIG: dict = {
    "name": "quadruped_canter",
    "frame_count": 20,
    "bones": {
        "DEF-thigh.R":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 0.0},
        "DEF-shin.R":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": 0.5},
        "DEF-thigh.L":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 2 * math.pi / 3},
        "DEF-shin.L":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": 2 * math.pi / 3 + 0.5},
        "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 2 * math.pi / 3},
        "DEF-forearm.R":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": 2 * math.pi / 3 + 0.5},
        "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 4 * math.pi / 3},
        "DEF-forearm.L":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.4, "phase": 4 * math.pi / 3 + 0.5},
        "DEF-spine.001":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.06, "phase": 0.0},
        "DEF-spine.002":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.06, "phase": math.pi / 2},
    },
}

# Quadruped gallop: 4-beat fastest gait with suspension phase
QUADRUPED_GALLOP_CONFIG: dict = {
    "name": "quadruped_gallop",
    "frame_count": 16,
    "bones": {
        "DEF-thigh.R":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.9, "phase": 0.0},
        "DEF-shin.R":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 0.5},
        "DEF-thigh.L":     {"channel": "rotation_euler", "axis": 0, "amplitude": 0.9, "phase": math.pi / 3},
        "DEF-shin.L":      {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": math.pi / 3 + 0.5},
        "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.9, "phase": 2 * math.pi / 3},
        "DEF-forearm.R":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": 2 * math.pi / 3 + 0.5},
        "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "amplitude": 0.9, "phase": math.pi},
        "DEF-forearm.L":   {"channel": "rotation_euler", "axis": 0, "amplitude": 0.6, "phase": math.pi + 0.5},
        "DEF-spine.001":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.1, "phase": 0.0},
        "DEF-spine.002":   {"channel": "rotation_euler", "axis": 1, "amplitude": 0.1, "phase": math.pi / 2},
    },
}

# Backward compatibility alias
QUADRUPED_RUN_CONFIG = QUADRUPED_GALLOP_CONFIG


# Hexapod (insect): alternating tripod gait
# Tripod A: leg_front.L, leg_mid.R, leg_rear.L (phase 0)
# Tripod B: leg_front.R, leg_mid.L, leg_rear.R (phase pi)
HEXAPOD_WALK_CONFIG: dict = {
    "name": "hexapod_walk",
    "frame_count": 24,
    "bones": {
        # Tripod A (phase 0)
        "DEF-leg_front.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": 0.0,
        },
        "DEF-leg_front_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": 0.5,
        },
        "DEF-leg_mid.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": 0.0,
        },
        "DEF-leg_mid_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": 0.5,
        },
        "DEF-leg_rear.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": 0.0,
        },
        "DEF-leg_rear_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": 0.5,
        },
        # Tripod B (phase pi)
        "DEF-leg_front.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": math.pi,
        },
        "DEF-leg_front_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": math.pi + 0.5,
        },
        "DEF-leg_mid.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": math.pi,
        },
        "DEF-leg_mid_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": math.pi + 0.5,
        },
        "DEF-leg_rear.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.45, "phase": math.pi,
        },
        "DEF-leg_rear_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.3, "phase": math.pi + 0.5,
        },
        # Body bob
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.01, "phase": 0.0,
        },
    },
}

HEXAPOD_RUN_CONFIG: dict = {
    "name": "hexapod_run",
    "frame_count": 16,
    "bones": {
        "DEF-leg_front.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": 0.0,
        },
        "DEF-leg_front_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": 0.5,
        },
        "DEF-leg_mid.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": 0.0,
        },
        "DEF-leg_mid_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": 0.5,
        },
        "DEF-leg_rear.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": 0.0,
        },
        "DEF-leg_rear_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": 0.5,
        },
        "DEF-leg_front.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": math.pi,
        },
        "DEF-leg_front_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": math.pi + 0.5,
        },
        "DEF-leg_mid.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": math.pi,
        },
        "DEF-leg_mid_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": math.pi + 0.5,
        },
        "DEF-leg_rear.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.7, "phase": math.pi,
        },
        "DEF-leg_rear_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.5, "phase": math.pi + 0.5,
        },
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.02, "phase": 0.0,
        },
    },
}


# Arachnid (8-legged): 4-4 alternating groups
# Group A: legs 1.L, 2.R, 3.L, 4.R (phase 0)
# Group B: legs 1.R, 2.L, 3.R, 4.L (phase pi)
ARACHNID_WALK_CONFIG: dict = {
    "name": "arachnid_walk",
    "frame_count": 24,
    "bones": {
        # Group A (phase 0)
        "DEF-leg_1.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": 0.0,
        },
        "DEF-leg_1_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": 0.5,
        },
        "DEF-leg_2.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": 0.0,
        },
        "DEF-leg_2_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": 0.5,
        },
        "DEF-leg_3.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": 0.0,
        },
        "DEF-leg_3_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": 0.5,
        },
        "DEF-leg_4.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": 0.0,
        },
        "DEF-leg_4_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": 0.5,
        },
        # Group B (phase pi)
        "DEF-leg_1.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": math.pi,
        },
        "DEF-leg_1_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi + 0.5,
        },
        "DEF-leg_2.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": math.pi,
        },
        "DEF-leg_2_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi + 0.5,
        },
        "DEF-leg_3.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": math.pi,
        },
        "DEF-leg_3_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi + 0.5,
        },
        "DEF-leg_4.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.4, "phase": math.pi,
        },
        "DEF-leg_4_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi + 0.5,
        },
        # Body bob
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.008, "phase": 0.0,
        },
    },
}

ARACHNID_RUN_CONFIG: dict = {
    "name": "arachnid_run",
    "frame_count": 16,
    "bones": {
        "DEF-leg_1.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": 0.0,
        },
        "DEF-leg_1_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.5,
        },
        "DEF-leg_2.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": 0.0,
        },
        "DEF-leg_2_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.5,
        },
        "DEF-leg_3.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": 0.0,
        },
        "DEF-leg_3_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.5,
        },
        "DEF-leg_4.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": 0.0,
        },
        "DEF-leg_4_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.5,
        },
        "DEF-leg_1.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": math.pi,
        },
        "DEF-leg_1_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi + 0.5,
        },
        "DEF-leg_2.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": math.pi,
        },
        "DEF-leg_2_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi + 0.5,
        },
        "DEF-leg_3.R": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": math.pi,
        },
        "DEF-leg_3_lower.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi + 0.5,
        },
        "DEF-leg_4.L": {
            "channel": "rotation_euler", "axis": 2,
            "amplitude": 0.65, "phase": math.pi,
        },
        "DEF-leg_4_lower.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi + 0.5,
        },
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.015, "phase": 0.0,
        },
    },
}


# Serpent: wave propagation along spine chain (no legs)
# Each successive spine bone gets increasing phase offset for traveling wave
SERPENT_WALK_CONFIG: dict = {
    "name": "serpent_walk",
    "frame_count": 24,
    "bones": {
        "DEF-spine": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.3, "phase": 0.0,
        },
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.3, "phase": math.pi / 4,
        },
        "DEF-spine.002": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.3, "phase": math.pi / 2,
        },
        "DEF-spine.003": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.3, "phase": 3 * math.pi / 4,
        },
        "DEF-spine.004": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.3, "phase": math.pi,
        },
        "DEF-spine.005": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.25, "phase": 5 * math.pi / 4,
        },
        "DEF-spine.006": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.2, "phase": 3 * math.pi / 2,
        },
        "DEF-spine.007": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.15, "phase": 7 * math.pi / 4,
        },
    },
}

SERPENT_RUN_CONFIG: dict = {
    "name": "serpent_run",
    "frame_count": 16,
    "bones": {
        "DEF-spine": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.5, "phase": 0.0,
        },
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.5, "phase": math.pi / 4,
        },
        "DEF-spine.002": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.5, "phase": math.pi / 2,
        },
        "DEF-spine.003": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.5, "phase": 3 * math.pi / 4,
        },
        "DEF-spine.004": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.5, "phase": math.pi,
        },
        "DEF-spine.005": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.4, "phase": 5 * math.pi / 4,
        },
        "DEF-spine.006": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.35, "phase": 3 * math.pi / 2,
        },
        "DEF-spine.007": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.25, "phase": 7 * math.pi / 4,
        },
    },
}


# Fly/hover: wing bone oscillation with frequency, amplitude, glide params
FLY_HOVER_CONFIG: dict = {
    "name": "fly_hover",
    "frame_count": 24,
    "frequency": 1.0,
    "glide_ratio": 0.0,
    "bones": {
        "DEF-wing_upper.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.8, "phase": 0.0,
        },
        "DEF-wing_fore.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.3,
        },
        "DEF-wing_tip.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": 0.6,
        },
        "DEF-wing_upper.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.8, "phase": 0.0,
        },
        "DEF-wing_fore.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.3,
        },
        "DEF-wing_tip.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": 0.6,
        },
        # Subtle body bob while hovering
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.03, "phase": 0.0,
        },
    },
}


# Idle: subtle breathing on spine/chest, very low amplitude
IDLE_CONFIG: dict = {
    "name": "idle",
    "frame_count": 48,
    "bones": {
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.02, "phase": 0.0,
        },
        "DEF-spine.002": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.015, "phase": math.pi / 4,
        },
        # Subtle hip weight shift (Y-axis sway)
        "DEF-spine": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.01, "phase": math.pi / 2,
        },
    },
}


# Bird: hopping walk on two legs with wing-balance micro-flaps.
# Uses DEF-thigh.L/R for leg hop, DEF-wing_upper.L/R for balance beats.
BIRD_WALK_CONFIG: dict = {
    "name": "bird_walk",
    "frame_count": 16,
    "bones": {
        # Hop: both legs push together (birds hop, not stride)
        "DEF-thigh.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": 0.0,
        },
        "DEF-thigh.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": 0.0,  # in-phase for synchronized hop
        },
        "DEF-shin.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi,  # extend on push
        },
        "DEF-shin.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi,
        },
        # Micro-flap for balance while hopping (BIRD uses upper_arm, not wing_upper)
        "DEF-upper_arm.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.15, "phase": 0.0,
        },
        "DEF-upper_arm.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.15, "phase": 0.0,
        },
        # Head bob (characteristic bird movement)
        "DEF-spine.004__head_bob": {
            "channel": "location", "axis": 1,
            "amplitude": 0.04, "phase": 0.0,
        },
    },
}

BIRD_RUN_CONFIG: dict = {
    "name": "bird_run",
    "frame_count": 12,
    "bones": {
        "DEF-thigh.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.6, "phase": 0.0,
        },
        "DEF-thigh.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.6, "phase": math.pi,  # alternating stride when running
        },
        "DEF-shin.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": math.pi,
        },
        "DEF-shin.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.4, "phase": 0.0,
        },
        # BIRD uses upper_arm, not wing_upper (which is for DRAGON rigs)
        "DEF-upper_arm.L": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": math.pi,
        },
        "DEF-upper_arm.R": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.25, "phase": 0.0,
        },
        "DEF-spine.004__head_bob": {
            "channel": "location", "axis": 1,
            "amplitude": 0.07, "phase": 0.0,
        },
    },
}


# Floating: amorphous/ghost creatures with undulating spine and tentacles.
# No leg bones — uses DEF-spine chain + DEF-tentacle bones for locomotion.
FLOATING_WALK_CONFIG: dict = {
    "name": "floating_walk",
    "frame_count": 32,
    "bones": {
        # Spine undulation — slow, dreamlike bobbing
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.05, "phase": 0.0,
        },
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.08, "phase": math.pi / 4,
        },
        "DEF-spine.002": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.06, "phase": math.pi / 2,
        },
        "DEF-spine.003": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.04, "phase": math.pi,
        },
        # Tentacle trailing motion — names match FLOATING_BONES template
        "DEF-tentacle_fl": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": 0.0,
        },
        "DEF-tentacle_fr": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": math.pi / 2,
        },
        "DEF-tentacle_bl": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": math.pi,
        },
        "DEF-tentacle_br": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.2, "phase": 3 * math.pi / 2,
        },
    },
}

FLOATING_RUN_CONFIG: dict = {
    "name": "floating_run",
    "frame_count": 20,
    "bones": {
        "DEF-spine": {
            "channel": "location", "axis": 2,
            "amplitude": 0.1, "phase": 0.0,
        },
        "DEF-spine.001": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.15, "phase": math.pi / 4,
        },
        "DEF-spine.002": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.12, "phase": math.pi / 2,
        },
        "DEF-spine.003": {
            "channel": "rotation_euler", "axis": 1,
            "amplitude": 0.08, "phase": math.pi,
        },
        "DEF-tentacle_fl": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": 0.0,
        },
        "DEF-tentacle_fr": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": math.pi / 2,
        },
        "DEF-tentacle_bl": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": math.pi,
        },
        "DEF-tentacle_br": {
            "channel": "rotation_euler", "axis": 0,
            "amplitude": 0.35, "phase": 3 * math.pi / 2,
        },
    },
}


# ---------------------------------------------------------------------------
# Gait config registry
# ---------------------------------------------------------------------------

_GAIT_REGISTRY: dict[str, dict[str, dict]] = {
    "biped": {"walk": BIPED_WALK_CONFIG, "run": BIPED_RUN_CONFIG},
    "quadruped": {
        "walk": QUADRUPED_WALK_CONFIG, "trot": QUADRUPED_TROT_CONFIG,
        "canter": QUADRUPED_CANTER_CONFIG, "gallop": QUADRUPED_GALLOP_CONFIG,
        "run": QUADRUPED_GALLOP_CONFIG,
    },
    "hexapod": {"walk": HEXAPOD_WALK_CONFIG, "run": HEXAPOD_RUN_CONFIG},
    "arachnid": {"walk": ARACHNID_WALK_CONFIG, "run": ARACHNID_RUN_CONFIG},
    "serpent": {"walk": SERPENT_WALK_CONFIG, "run": SERPENT_RUN_CONFIG},
    "bird": {"walk": BIRD_WALK_CONFIG, "run": BIRD_RUN_CONFIG},
    "floating": {"walk": FLOATING_WALK_CONFIG, "run": FLOATING_RUN_CONFIG},
}


# ---------------------------------------------------------------------------
# Keyframe engine
# ---------------------------------------------------------------------------

def generate_cycle_keyframes(config: dict) -> list[Keyframe]:
    """Generate keyframes for a locomotion/animation cycle from a config dict.

    Pure math -- no Blender dependency. For each bone in config["bones"],
    generates frame_count+1 keyframes using:
        value = amplitude * sin(frequency * 2*pi*frame/frame_count + phase) + offset

    Multi-harmonic support: if a bone config contains a ``"harmonics"`` list,
    each entry ``{"amp": float, "phase": float}`` is summed as an additional
    sine component.  The base ``amplitude``/``phase`` keys are ignored when
    harmonics are present.

    Composite bone keys: a bone key containing ``"__"`` (double underscore) is
    treated as ``<real_bone>__<tag>``.  The tag is stripped so that the emitted
    ``Keyframe.bone_name`` uses only the real bone name.  This allows multiple
    channels on the same bone in one config dict (e.g. ``DEF-spine__sway``).

    The optional config["frequency"] multiplier (default 1.0) scales how many
    oscillations occur per cycle -- e.g. 2.0 means two full sine waves within
    frame_count frames (useful for fly/hover wing beats).

    Frame 0 and frame frame_count produce identical values (seamless loop)
    as long as frequency is a positive integer (which it is for all built-in
    configs).

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []
    frame_count = max(1, config["frame_count"])
    frequency = config.get("frequency", 1.0)

    for bone_key, bone_cfg in config["bones"].items():
        # Composite key: strip __tag suffix for actual bone name
        bone_name = bone_key.split("__")[0] if "__" in bone_key else bone_key

        offset = bone_cfg.get("offset", 0.0)
        channel = bone_cfg["channel"]
        axis = bone_cfg["axis"]
        harmonics = bone_cfg.get("harmonics")

        for frame in range(frame_count + 1):
            t = (frame / frame_count) * 2.0 * math.pi * frequency
            if harmonics:
                value = sum(
                    h["amp"] * math.sin(t + h["phase"]) for h in harmonics
                ) + offset
            else:
                amp = bone_cfg["amplitude"]
                phase = bone_cfg["phase"]
                value = amp * math.sin(t + phase) + offset
            keyframes.append(Keyframe(
                bone_name=bone_name,
                channel=channel,
                axis=axis,
                frame=frame,
                value=value,
            ))

    return keyframes


def get_gait_config(
    gait: str,
    speed: str = "walk",
    frame_count: int | None = None,
    bone_names: list[str] | None = None,
) -> dict:
    """Look up a gait configuration dict by gait type and speed.

    Args:
        gait: One of "biped", "quadruped", "hexapod", "arachnid", "serpent".
        speed: "walk", "run", "fly", or "idle".
        frame_count: Override the default frame_count if provided.
        bone_names: If given, filter config to only include bones in this list.

    Returns:
        A copy of the matching config dict (possibly modified).

    Raises:
        ValueError: If gait type is unknown.
    """
    # Special speed modes
    if speed == "fly":
        config = _deep_copy_config(FLY_HOVER_CONFIG)
    elif speed == "idle":
        config = _deep_copy_config(IDLE_CONFIG)
    else:
        if gait not in _GAIT_REGISTRY:
            raise ValueError(
                f"Unknown gait type: {gait!r}. "
                f"Valid types: {sorted(_GAIT_REGISTRY.keys())}"
            )
        speed_map = _GAIT_REGISTRY[gait]
        if speed not in speed_map:
            raise ValueError(
                f"Unknown speed: {speed!r} for gait {gait!r}. "
                f"Valid speeds: {sorted(speed_map.keys())}"
            )
        config = _deep_copy_config(speed_map[speed])

    # Override frame_count if provided
    if frame_count is not None:
        config["frame_count"] = frame_count

    # Filter to requested bones
    if bone_names is not None:
        bone_set = set(bone_names)
        config["bones"] = {
            k: v for k, v in config["bones"].items() if k in bone_set
        }

    return config


def _deep_copy_config(config: dict) -> dict:
    """Return a shallow-enough copy of a config dict to allow mutation."""
    result = dict(config)
    result["bones"] = {k: dict(v) for k, v in config["bones"].items()}
    return result


# ---------------------------------------------------------------------------
# Attack configuration dicts
# ---------------------------------------------------------------------------
# Each attack config has phases: list of dicts with:
#   start_pct, end_pct, bones: {bone: {channel, axis, start_value, end_value}}

ATTACK_CONFIGS: dict[str, dict] = {
    "melee_swing": {
        "name": "melee_swing",
        "phases": [
            {  # Anticipation: arm back (20%)
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.4},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 2, "start_value": 0.0, "end_value": -0.3},
                },
            },
            {  # Strike: arm forward arc (30%)
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 1.2},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.4, "end_value": 0.6},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 2, "start_value": -0.3, "end_value": 0.5},
                },
            },
            {  # Recovery: return (50%)
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 1.2, "end_value": 0.0},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 2, "start_value": 0.5, "end_value": 0.0},
                },
            },
        ],
    },
    "thrust": {
        "name": "thrust",
        "phases": [
            {  # Anticipation: pull back
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.5},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                },
            },
            {  # Strike: lunge forward
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": 0.4},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.5, "end_value": 1.0},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 0.2},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.4, "end_value": 0.0},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.2, "end_value": 0.0},
                },
            },
        ],
    },
    "slam": {
        "name": "slam",
        "phases": [
            {  # Anticipation: raise arms
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -1.2},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -1.2},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                },
            },
            {  # Strike: smash down
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "start_value": -1.2, "end_value": 1.0},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -1.2, "end_value": 1.0},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": 0.5},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.5, "end_value": 0.0},
                },
            },
        ],
    },
    "bite": {
        "name": "bite",
        "phases": [
            {  # Anticipation: jaw opens wide, head tilts
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": 0.6},
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                },
            },
            {  # Strike: jaw snaps shut
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": -0.1},
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": 0.2},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": -0.1, "end_value": 0.0},
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": 0.2, "end_value": 0.0},
                },
            },
        ],
    },
    "claw": {
        "name": "claw",
        "phases": [
            {  # Anticipation: arm back, hand spread
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.6},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.5},
                },
            },
            {  # Strike: quick swipe arc
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.6, "end_value": 0.8},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": 0.5},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.5, "end_value": 0.6},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.0},
                    "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.5, "end_value": 0.0},
                    "DEF-hand.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                },
            },
        ],
    },
    "tail_whip": {
        "name": "tail_whip",
        "phases": [
            {  # Anticipation: tail coils
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-tail": {"channel": "rotation_euler", "axis": 1, "start_value": 0.0, "end_value": -0.5},
                    "DEF-tail.001": {"channel": "rotation_euler", "axis": 1, "start_value": 0.0, "end_value": -0.6},
                    "DEF-tail.002": {"channel": "rotation_euler", "axis": 1, "start_value": 0.0, "end_value": -0.7},
                    "DEF-tail.003": {"channel": "rotation_euler", "axis": 1, "start_value": 0.0, "end_value": -0.8},
                },
            },
            {  # Strike: tail sweeps
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-tail": {"channel": "rotation_euler", "axis": 1, "start_value": -0.5, "end_value": 0.8},
                    "DEF-tail.001": {"channel": "rotation_euler", "axis": 1, "start_value": -0.6, "end_value": 1.0},
                    "DEF-tail.002": {"channel": "rotation_euler", "axis": 1, "start_value": -0.7, "end_value": 1.2},
                    "DEF-tail.003": {"channel": "rotation_euler", "axis": 1, "start_value": -0.8, "end_value": 1.4},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-tail": {"channel": "rotation_euler", "axis": 1, "start_value": 0.8, "end_value": 0.0},
                    "DEF-tail.001": {"channel": "rotation_euler", "axis": 1, "start_value": 1.0, "end_value": 0.0},
                    "DEF-tail.002": {"channel": "rotation_euler", "axis": 1, "start_value": 1.2, "end_value": 0.0},
                    "DEF-tail.003": {"channel": "rotation_euler", "axis": 1, "start_value": 1.4, "end_value": 0.0},
                },
            },
        ],
    },
    "wing_buffet": {
        "name": "wing_buffet",
        "phases": [
            {  # Anticipation: wings pull back
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-wing_upper.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                    "DEF-wing_upper.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                    "DEF-wing_fore.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.4},
                    "DEF-wing_fore.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.4},
                },
            },
            {  # Strike: wings sweep forward
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-wing_upper.L": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 1.0},
                    "DEF-wing_upper.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 1.0},
                    "DEF-wing_fore.L": {"channel": "rotation_euler", "axis": 0, "start_value": -0.4, "end_value": 0.6},
                    "DEF-wing_fore.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.4, "end_value": 0.6},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-wing_upper.L": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-wing_upper.R": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-wing_fore.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                    "DEF-wing_fore.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                },
            },
        ],
    },
    "breath_attack": {
        "name": "breath_attack",
        "phases": [
            {  # Anticipation: head tilts up, jaw opens
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.5},
                    "DEF-spine.005": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": 0.8},
                },
            },
            {  # Strike: hold open, breath sustain
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": -0.5, "end_value": -0.4},
                    "DEF-spine.005": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": -0.2},
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.7},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "start_value": -0.4, "end_value": 0.0},
                    "DEF-spine.005": {"channel": "rotation_euler", "axis": 0, "start_value": -0.2, "end_value": 0.0},
                    "DEF-jaw": {"channel": "rotation_euler", "axis": 0, "start_value": 0.7, "end_value": 0.0},
                },
            },
        ],
    },
    # Insect/arachnid: mandible strike. Uses DEF-thigh.L/R (first leg pair) as
    # "arm" analogues for insect forelegs, plus spine lunge. Works on any
    # hexapod/arachnid rig regardless of whether it has biped arm bones.
    "mandible_strike": {
        "name": "mandible_strike",
        "phases": [
            {  # Anticipation: rear up, forelegs raise
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-spine": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.4},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.3},
                    "DEF-thigh.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                    "DEF-thigh.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                },
            },
            {  # Strike: lunge forward, forelegs snap down
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-spine": {"channel": "rotation_euler", "axis": 0, "start_value": -0.4, "end_value": 0.5},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": -0.3, "end_value": 0.4},
                    "DEF-thigh.L": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 0.6},
                    "DEF-thigh.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 0.6},
                },
            },
            {  # Recovery
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-spine": {"channel": "rotation_euler", "axis": 0, "start_value": 0.5, "end_value": 0.0},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.4, "end_value": 0.0},
                    "DEF-thigh.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                    "DEF-thigh.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
                },
            },
        ],
    },
    # Floating/amorphous: tentacle lash. Uses DEF-tentacle bones which are
    # present on floating and amorphous rig templates.
    "tentacle_lash": {
        "name": "tentacle_lash",
        "phases": [
            {  # Anticipation: tentacle coils back
                "start_pct": 0.0, "end_pct": 0.2,
                "bones": {
                    "DEF-tentacle_fl": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.8},
                    "DEF-tentacle_fr": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.6},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.0, "end_value": -0.2},
                },
            },
            {  # Strike: whip forward
                "start_pct": 0.2, "end_pct": 0.5,
                "bones": {
                    "DEF-tentacle_fl": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 1.0},
                    "DEF-tentacle_fr": {"channel": "rotation_euler", "axis": 0, "start_value": -0.6, "end_value": 0.8},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": -0.2, "end_value": 0.3},
                },
            },
            {  # Recovery: tentacle retracts
                "start_pct": 0.5, "end_pct": 1.0,
                "bones": {
                    "DEF-tentacle_fl": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
                    "DEF-tentacle_fr": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.0},
                    "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.3, "end_value": 0.0},
                },
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Attack keyframe generator
# ---------------------------------------------------------------------------

def generate_attack_keyframes(
    attack_type: str,
    frame_count: int = 24,
    intensity: float = 1.0,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Generate keyframes for an attack animation.

    Attack animations follow 3-phase timing:
      - Anticipation (20% of frames)
      - Strike (30% of frames)
      - Recovery (50% of frames)

    Within each phase, values are linearly interpolated between start and end.

    Args:
        attack_type: One of the keys in ATTACK_CONFIGS.
        frame_count: Total number of frames for the attack.
        intensity: Multiplier for all values (0.5 = half, 2.0 = double).
        bone_names: If provided, only generate keyframes for bones in this list.
            Bones not present in the list are silently skipped. Use this to
            avoid keyframing DEF-jaw on creatures that have no jaw bone.

    Returns:
        List of Keyframe namedtuples.

    Raises:
        ValueError: If attack_type is unknown.
    """
    if attack_type not in ATTACK_CONFIGS:
        raise ValueError(
            f"Unknown attack type: {attack_type!r}. "
            f"Valid types: {sorted(ATTACK_CONFIGS.keys())}"
        )

    bone_filter: set[str] | None = set(bone_names) if bone_names else None
    config = ATTACK_CONFIGS[attack_type]
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    phases = config["phases"]
    for phase_idx, phase in enumerate(phases):
        start_frame = int(round(phase["start_pct"] * frame_count))
        end_frame = int(round(phase["end_pct"] * frame_count))
        phase_length = end_frame - start_frame
        is_last_phase = (phase_idx == len(phases) - 1)

        if phase_length <= 0:
            continue

        for bone_name, bone_cfg in phase["bones"].items():
            # Skip bones not present on this creature's armature
            if bone_filter is not None and bone_name not in bone_filter:
                continue

            channel = bone_cfg["channel"]
            axis = bone_cfg["axis"]
            start_val = bone_cfg["start_value"] * intensity
            end_val = bone_cfg["end_value"] * intensity

            # Include end_frame only for the final phase to avoid
            # duplicate keyframes at phase boundaries (where phase N's
            # end_frame equals phase N+1's start_frame).
            frame_end_inclusive = end_frame + 1 if is_last_phase else end_frame
            for frame in range(start_frame, frame_end_inclusive):
                t = (frame - start_frame) / phase_length if phase_length > 0 else 1.0
                value = start_val + (end_val - start_val) * t
                keyframes.append(Keyframe(
                    bone_name=bone_name,
                    channel=channel,
                    axis=axis,
                    frame=frame,
                    value=value,
                ))

    return keyframes


# ---------------------------------------------------------------------------
# Reaction configuration dicts
# ---------------------------------------------------------------------------

# Direction -> torso rotation mapping for hit reactions
_HIT_DIRECTION_MAP: dict[str, tuple[str, int, float]] = {
    "front":  ("rotation_euler", 0, 0.5),     # tilt back on X
    "back":   ("rotation_euler", 0, -0.5),    # tilt forward on X
    "left":   ("rotation_euler", 1, -0.4),    # twist left on Y
    "right":  ("rotation_euler", 1, 0.4),     # twist right on Y
}

REACTION_CONFIGS: dict[str, dict] = {
    "death": {
        "name": "death",
        "description": "Progressive spine collapse, limbs go limp",
        "bones": {
            # Spine progressive forward collapse
            "DEF-spine": {"channel": "rotation_euler", "axis": 0, "end_value": 0.8},
            "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "end_value": 0.6},
            "DEF-spine.002": {"channel": "rotation_euler", "axis": 0, "end_value": 0.5},
            "DEF-spine.003": {"channel": "rotation_euler", "axis": 0, "end_value": 0.4},
            # Head drops
            "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "end_value": 0.7},
            # Arms go limp
            "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "end_value": 0.3},
            "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "end_value": 0.3},
            "DEF-forearm.L": {"channel": "rotation_euler", "axis": 0, "end_value": 0.5},
            "DEF-forearm.R": {"channel": "rotation_euler", "axis": 0, "end_value": 0.5},
            # Legs buckle
            "DEF-thigh.L": {"channel": "rotation_euler", "axis": 0, "end_value": 0.4},
            "DEF-thigh.R": {"channel": "rotation_euler", "axis": 0, "end_value": 0.4},
            "DEF-shin.L": {"channel": "rotation_euler", "axis": 0, "end_value": -0.6},
            "DEF-shin.R": {"channel": "rotation_euler", "axis": 0, "end_value": -0.6},
        },
    },
    "hit": {
        "name": "hit",
        "description": "Directional torso rotation, head snap, arm flinch",
        "bones": {
            # Base bones always animated, direction modifies torso
            "DEF-spine.004": {"channel": "rotation_euler", "axis": 0, "end_value": 0.3},
            "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "end_value": -0.2},
            "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "end_value": -0.2},
        },
    },
    "spawn": {
        "name": "spawn",
        "description": "Start curled/compressed, unfold to full pose",
        "bones": {
            # Start compressed (spine curl)
            "DEF-spine": {"channel": "rotation_euler", "axis": 0, "start_value": 1.0, "end_value": 0.0},
            "DEF-spine.001": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.0},
            "DEF-spine.002": {"channel": "rotation_euler", "axis": 0, "start_value": 0.6, "end_value": 0.0},
            "DEF-upper_arm.L": {"channel": "rotation_euler", "axis": 0, "start_value": 1.2, "end_value": 0.0},
            "DEF-upper_arm.R": {"channel": "rotation_euler", "axis": 0, "start_value": 1.2, "end_value": 0.0},
            "DEF-thigh.L": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.0},
            "DEF-thigh.R": {"channel": "rotation_euler", "axis": 0, "start_value": 0.8, "end_value": 0.0},
            # Vertical rise (legs extending from crouched position)
            "DEF-shin.L": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 0.0},
            "DEF-shin.R": {"channel": "rotation_euler", "axis": 0, "start_value": -0.8, "end_value": 0.0},
        },
    },
}


# ---------------------------------------------------------------------------
# Reaction keyframe generator
# ---------------------------------------------------------------------------

def generate_reaction_keyframes(
    reaction_type: str,
    direction: str | None = None,
    frame_count: int = 24,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Generate keyframes for a reaction animation (death, hit, spawn).

    Args:
        reaction_type: One of "death", "hit", "spawn".
        direction: For "hit" reactions: "front", "back", "left", "right".
            Ignored for other reaction types.
        frame_count: Total number of frames.
        bone_names: If provided, only generate keyframes for bones in this list.
            Bones not present in the list are silently skipped.

    Returns:
        List of Keyframe namedtuples.

    Raises:
        ValueError: If reaction_type is unknown.
    """
    if reaction_type not in REACTION_CONFIGS:
        raise ValueError(
            f"Unknown reaction type: {reaction_type!r}. "
            f"Valid types: {sorted(REACTION_CONFIGS.keys())}"
        )

    bone_filter: set[str] | None = set(bone_names) if bone_names else None
    config = REACTION_CONFIGS[reaction_type]
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for bone_name, bone_cfg in config["bones"].items():
        if bone_filter is not None and bone_name not in bone_filter:
            continue
        channel = bone_cfg["channel"]
        axis = bone_cfg.get("axis", 0)
        start_val = bone_cfg.get("start_value", 0.0)
        end_val = bone_cfg.get("end_value", 0.0)

        for frame in range(frame_count + 1):
            t = frame / frame_count
            value = start_val + (end_val - start_val) * t
            keyframes.append(Keyframe(
                bone_name=bone_name,
                channel=channel,
                axis=axis,
                frame=frame,
                value=value,
            ))

    # For hit reactions, add directional torso rotation
    if reaction_type == "hit" and direction:
        dir_key = direction.lower()
        hit_bone = "DEF-spine.001"
        if dir_key in _HIT_DIRECTION_MAP and (
            bone_filter is None or hit_bone in bone_filter
        ):
            channel, axis, magnitude = _HIT_DIRECTION_MAP[dir_key]
            # Quick snap to direction then recover
            for frame in range(frame_count + 1):
                t = frame / frame_count
                # Quick hit (peak at 20%) then recover
                if t <= 0.2:
                    value = magnitude * (t / 0.2)
                else:
                    value = magnitude * (1.0 - (t - 0.2) / 0.8)
                keyframes.append(Keyframe(
                    bone_name=hit_bone,
                    channel=channel,
                    axis=axis,
                    frame=frame,
                    value=value,
                ))

    return keyframes


# ---------------------------------------------------------------------------
# Custom animation text-to-keyframe mapper
# ---------------------------------------------------------------------------

# Verb -> motion type mapping
_VERB_MAP: dict[str, tuple[str, int, float]] = {
    "rise": ("rotation_euler", 0, -0.5),
    "raise": ("rotation_euler", 0, -0.5),
    "lower": ("rotation_euler", 0, 0.5),
    "drop": ("rotation_euler", 0, 0.5),
    "spread": ("rotation_euler", 1, 0.8),
    "open": ("rotation_euler", 1, 0.6),
    "close": ("rotation_euler", 1, -0.6),
    "swing": ("rotation_euler", 0, 1.0),
    "slash": ("rotation_euler", 0, 1.0),
    "breathe": ("rotation_euler", 0, 0.3),
    "exhale": ("rotation_euler", 0, 0.3),
    "inhale": ("rotation_euler", 0, -0.2),
    "twist": ("rotation_euler", 1, 0.6),
    "turn": ("rotation_euler", 1, 0.5),
    "nod": ("rotation_euler", 0, 0.3),
    "shake": ("rotation_euler", 1, 0.4),
    "curl": ("rotation_euler", 0, 0.7),
    "extend": ("rotation_euler", 0, -0.4),
    "stomp": ("location", 2, -0.1),
    "jump": ("location", 2, 0.3),
    "crouch": ("rotation_euler", 0, 0.5),
    "wave": ("rotation_euler", 1, 0.6),
}

# Body part -> bone name mapping
_BODY_PART_MAP: dict[str, list[str]] = {
    "wings": ["DEF-wing_upper.L", "DEF-wing_upper.R", "DEF-wing_fore.L", "DEF-wing_fore.R"],
    "wing": ["DEF-wing_upper.L", "DEF-wing_upper.R", "DEF-wing_fore.L", "DEF-wing_fore.R"],
    "arms": ["DEF-upper_arm.L", "DEF-upper_arm.R", "DEF-forearm.L", "DEF-forearm.R"],
    "arm": ["DEF-upper_arm.R", "DEF-forearm.R"],
    "left arm": ["DEF-upper_arm.L", "DEF-forearm.L"],
    "right arm": ["DEF-upper_arm.R", "DEF-forearm.R"],
    "hands": ["DEF-hand.L", "DEF-hand.R"],
    "hand": ["DEF-hand.R"],
    "head": ["DEF-spine.004", "DEF-spine.005"],
    "tail": ["DEF-tail", "DEF-tail.001", "DEF-tail.002", "DEF-tail.003"],
    "jaw": ["DEF-jaw"],
    "mouth": ["DEF-jaw"],
    "legs": ["DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R"],
    "leg": ["DEF-thigh.R", "DEF-shin.R"],
    "spine": ["DEF-spine.001", "DEF-spine.002"],
    "body": ["DEF-spine", "DEF-spine.001", "DEF-spine.002"],
    "chest": ["DEF-spine.002", "DEF-spine.003"],
    "hips": ["DEF-spine"],
    "feet": ["DEF-foot.L", "DEF-foot.R"],
    "foot": ["DEF-foot.R"],
}


def generate_custom_keyframes(
    description: str,
    frame_count: int = 48,
) -> list[Keyframe]:
    """Parse a text description and generate keyframes for the described motion.

    Maps action verbs (raise, spread, swing, breathe, etc.) and body part
    keywords (wings, arms, head, tail, jaw, etc.) to keyframe sequences.
    Actions are sequenced in the order they appear in the text, dividing
    frame_count proportionally among them.

    Args:
        description: Natural language description of the animation.
            Example: "raise wings then swing arms"
        frame_count: Total frames for the animation.

    Returns:
        List of Keyframe namedtuples (best effort).
    """
    # Normalize input
    text = description.lower().strip()

    # Split into action phrases by common connectors
    phrases = re.split(r'\b(?:then|and|while|next|followed by)\b|,', text)
    phrases = [p.strip() for p in phrases if p.strip()]

    if not phrases:
        return []

    # Parse each phrase for verb + body part
    actions: list[tuple[str, list[str], tuple[str, int, float]]] = []
    for phrase in phrases:
        verb_match = None
        body_bones: list[str] = []

        # Find verb
        for verb, motion in _VERB_MAP.items():
            if re.search(r'\b' + re.escape(verb) + r'\b', phrase):
                verb_match = motion
                break

        # Find body part (check multi-word keys first, use word boundaries)
        sorted_parts = sorted(_BODY_PART_MAP.keys(), key=len, reverse=True)
        for part in sorted_parts:
            if re.search(r'(?:^|\b|\s)' + re.escape(part) + r'(?:\b|\s|$)', phrase):
                body_bones = _BODY_PART_MAP[part]
                break

        if verb_match and body_bones:
            actions.append((phrase, body_bones, verb_match))

    if not actions:
        return []

    # Distribute frames proportionally
    frames_per_action = frame_count // len(actions)
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for i, (_phrase, bones, (channel, axis, magnitude)) in enumerate(actions):
        start_frame = i * frames_per_action
        end_frame = start_frame + frames_per_action
        action_length = end_frame - start_frame

        for bone_name in bones:
            for frame in range(start_frame, end_frame + 1):
                local_frame = frame - start_frame
                t = local_frame / action_length if action_length > 0 else 1.0
                # Bell curve: ramp up then back down
                if t <= 0.5:
                    value = magnitude * (t / 0.5)
                else:
                    value = magnitude * (1.0 - (t - 0.5) / 0.5)
                keyframes.append(Keyframe(
                    bone_name=bone_name,
                    channel=channel,
                    axis=axis,
                    frame=frame,
                    value=value,
                ))

    return keyframes
