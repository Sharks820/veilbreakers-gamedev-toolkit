"""Extended locomotion animations for AAA movement blendspace.

Covers animations missing from the base gait system:
  - sprint: Faster than run with forward lean
  - strafe_left/right: Lateral movement with body tilt
  - walk_backward: Reversed step cycle with cautious posture
  - jump_takeoff: Crouch-spring launch
  - jump_apex: Airborne pose
  - jump_land: Impact absorption with knee flex
  - fall_loop: Extended airborne state
  - dodge_roll: Full-body evasion roll
  - backstep: Quick backward hop
  - stagger: Multi-frame stumble from heavy hit
  - knockback: Root displacement from force
  - knockdown: Fall to ground
  - getup: Recovery from prone
  - weapon_draw: Reach and unsheathe
  - weapon_sheathe: Return weapon to rest

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe
from ._shared_utils import smoothstep


VALID_LOCOMOTION_TYPES: frozenset[str] = frozenset({
    "sprint", "strafe_left", "strafe_right", "walk_backward",
    "jump_takeoff", "jump_apex", "jump_land", "fall_loop",
    "dodge_roll", "backstep",
    "stagger", "knockback", "knockdown", "getup",
    "weapon_draw", "weapon_sheathe",
    # AAA completeness additions
    "swim", "climb", "slide", "crouch_walk", "ladder_climb",
    "parry_body", "riposte", "plunge_attack",
    "projectile_throw", "beam_aim", "summon_ritual",
    "mount", "dismount",
    "pickup", "push", "pull", "ledge_climb",
})


def validate_locomotion_params(params: dict) -> dict:
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    loco_type = params.get("loco_type", "sprint")
    if loco_type not in VALID_LOCOMOTION_TYPES:
        raise ValueError(f"Invalid loco_type: {loco_type!r}")
    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")
    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0")
    return {"object_name": object_name, "loco_type": loco_type,
            "frame_count": frame_count, "intensity": intensity}


# ---------------------------------------------------------------------------
# Locomotion generators
# ---------------------------------------------------------------------------

def generate_sprint_keyframes(frame_count: int = 12, intensity: float = 1.0) -> list[Keyframe]:
    """Sprint — faster than run, strong forward lean, larger arm pump."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        a = t * 2 * math.pi
        # Aggressive leg cycle
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 1.0 * math.sin(a) * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 1.0 * math.sin(a + math.pi) * intensity))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, 0.7 * math.sin(a + 0.5) * intensity))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, 0.7 * math.sin(a + math.pi + 0.5) * intensity))
        # Strong arm pump
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.6 * math.sin(a + math.pi) * intensity))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.6 * math.sin(a) * intensity))
        kfs.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.4 * abs(math.sin(a)) * intensity))
        kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.4 * abs(math.sin(a + math.pi)) * intensity))
        # Forward lean
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.15 * intensity))
        # Vertical bounce
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.03 * math.sin(a * 2) * intensity))
    return kfs


def generate_strafe_keyframes(frame_count: int = 24, direction: str = "left", intensity: float = 1.0) -> list[Keyframe]:
    """Lateral strafe — side step with body tilt toward movement."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    sign = -1.0 if direction == "left" else 1.0
    for frame in range(frame_count + 1):
        t = frame / frame_count
        a = t * 2 * math.pi
        # Lateral step cycle
        step = 0.35 * math.sin(a) * intensity
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 1, frame, step * sign))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 1, frame, step * sign))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, 0.15 * math.sin(a + 0.3) * intensity))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, 0.15 * math.sin(a + math.pi + 0.3) * intensity))
        # Body tilt
        kfs.append(Keyframe("DEF-spine", "rotation_euler", 2, frame, 0.08 * sign * intensity))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 2, frame, 0.05 * sign * intensity))
        # Arms balance
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.15 * math.sin(a) * intensity))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.15 * math.sin(a + math.pi) * intensity))
    return kfs


def generate_walk_backward_keyframes(frame_count: int = 28, intensity: float = 1.0) -> list[Keyframe]:
    """Backward walk — reversed phase, cautious upright posture."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        a = t * 2 * math.pi
        # Reversed leg cycle (negative phase direction)
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.45 * math.sin(a) * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, -0.45 * math.sin(a + math.pi) * intensity))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.3 * math.sin(a + 0.5) * intensity))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.3 * math.sin(a + math.pi + 0.5) * intensity))
        # Slight backward lean (cautious)
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.06 * intensity))
        # Smaller arm swing
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.15 * math.sin(a + math.pi) * intensity))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.15 * math.sin(a) * intensity))
    return kfs


def generate_jump_takeoff_keyframes(frame_count: int = 10, intensity: float = 1.0) -> list[Keyframe]:
    """Jump takeoff — crouch then spring upward."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    crouch_end = int(0.5 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= crouch_end:
            t = frame / crouch_end if crouch_end > 0 else 1.0
            # Crouch down
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * t * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * t * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.6 * t * intensity))
            kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.6 * t * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.1 * t * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.1 * t * intensity))
        else:
            t = (frame - crouch_end) / (frame_count - crouch_end) if frame_count > crouch_end else 1.0
            ease = smoothstep(t)
            # Spring up
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.6 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.6 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.1 * ease * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.3 * ease * intensity))
            # Arms swing up
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.8 * ease * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.8 * ease * intensity))
    return kfs


def generate_jump_apex_keyframes(frame_count: int = 8, intensity: float = 1.0) -> list[Keyframe]:
    """Jump apex — airborne spread pose."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.4 * intensity))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.4 * intensity))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.15 * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.1 * intensity))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.05 * intensity))
        # Subtle float drift
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.02 * math.sin(t * math.pi) * intensity))
    return kfs


def generate_jump_land_keyframes(frame_count: int = 12, intensity: float = 1.0) -> list[Keyframe]:
    """Landing — impact absorption with deep knee flex."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    impact_end = int(0.3 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= impact_end:
            t = frame / impact_end if impact_end > 0 else 1.0
            # Impact crouch
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * t * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6 * t * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.8 * t * intensity))
            kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.8 * t * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.15 * t * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.15 * t * intensity))
        else:
            t = (frame - impact_end) / (frame_count - impact_end) if frame_count > impact_end else 1.0
            ease = smoothstep(t)
            # Recover to standing
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.8 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.8 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.15 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.15 * (1 - ease) * intensity))
    return kfs


def generate_fall_loop_keyframes(frame_count: int = 24, intensity: float = 1.0) -> list[Keyframe]:
    """Falling loop — limbs flailing, wind resistance posture."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        a = t * 2 * math.pi
        # Arms flail
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.5 * intensity + 0.3 * math.sin(a * 2) * intensity))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.5 * intensity + 0.3 * math.sin(a * 2 + 1) * intensity))
        # Legs dangle
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * math.sin(a) * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.2 * math.sin(a + 0.5) * intensity))
        # Body slight arch
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.1 * intensity))
    return kfs


def generate_dodge_roll_keyframes(frame_count: int = 18, intensity: float = 1.0) -> list[Keyframe]:
    """Full-body dodge roll — tuck, rotate, recover."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    tuck_end = int(0.2 * frame_count)
    roll_end = int(0.7 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= tuck_end:
            t = frame / tuck_end if tuck_end > 0 else 1.0
            # Tuck into ball
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.8 * t * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * t * intensity))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.7 * t * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.7 * t * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.5 * t * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.5 * t * intensity))
        elif frame <= roll_end:
            roll_t = (frame - tuck_end) / (roll_end - tuck_end) if roll_end > tuck_end else 1.0
            # Full rotation (X-axis roll)
            roll_angle = 2 * math.pi * roll_t * intensity
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.8 * intensity + roll_angle))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * intensity))
            # Stay tucked
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.7 * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.7 * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.5 * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.5 * intensity))
        else:
            recover_t = (frame - roll_end) / (frame_count - roll_end) if frame_count > roll_end else 1.0
            ease = smoothstep(recover_t)
            # Unfold to standing
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, (0.8 + 2 * math.pi) * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.7 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.7 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.5 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.5 * (1 - ease) * intensity))
    return kfs


def generate_backstep_keyframes(frame_count: int = 12, intensity: float = 1.0) -> list[Keyframe]:
    """Quick backward hop evasion."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        hop = math.sin(t * math.pi)
        # Vertical hop
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.15 * hop * intensity))
        # Lean back
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.15 * hop * intensity))
        # Legs push off
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.3 * hop * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, -0.3 * hop * intensity))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, 0.4 * hop * intensity))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, 0.4 * hop * intensity))
    return kfs


def generate_stagger_keyframes(frame_count: int = 20, intensity: float = 1.0) -> list[Keyframe]:
    """Multi-frame stumble from heavy hit — off-balance recovery."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Damped wobble (decreasing amplitude)
        wobble = 0.3 * intensity * math.sin(t * 5 * math.pi) * (1 - t)
        kfs.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, wobble))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.2 * (1 - t) * intensity + wobble * 0.5))
        # Staggering steps
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * math.sin(t * 4 * math.pi) * (1 - t) * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, -0.2 * math.sin(t * 4 * math.pi) * (1 - t) * intensity))
        # Arms flail for balance
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.3 * wobble))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.3 * wobble))
    return kfs


def generate_knockback_keyframes(frame_count: int = 16, intensity: float = 1.0) -> list[Keyframe]:
    """Forced backward displacement from impact."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Arch backward from impact
        arch = 0.4 * intensity * math.sin(t * math.pi) * (1 - t * 0.5)
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -arch))
        kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, -arch * 0.7))
        # Feet drag
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.2 * (1 - t) * intensity))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, -0.2 * (1 - t) * intensity))
        # Arms fling backward
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.5 * arch))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.5 * arch))
    return kfs


def generate_knockdown_keyframes(frame_count: int = 24, intensity: float = 1.0) -> list[Keyframe]:
    """Fall to ground from knockdown attack."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    fall_end = int(0.5 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= fall_end:
            t = frame / fall_end if fall_end > 0 else 1.0
            ease = smoothstep(t)  # accelerating fall
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 1.2 * ease * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * ease * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.8 * ease * intensity))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * ease * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.4 * ease * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.6 * ease * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.3 * ease * intensity))
        else:
            # Ground impact settle
            settle_t = (frame - fall_end) / (frame_count - fall_end) if frame_count > fall_end else 1.0
            bounce = 0.05 * math.sin(settle_t * 3 * math.pi) * (1 - settle_t) * intensity
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 1.2 * intensity + bounce))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.8 * intensity + bounce))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * intensity))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.4 * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.6 * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.3 * intensity))
    return kfs


def generate_getup_keyframes(frame_count: int = 24, intensity: float = 1.0) -> list[Keyframe]:
    """Recovery from prone — push up, roll to side, stand."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    pushup_end = int(0.4 * frame_count)
    stand_start = int(0.6 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= pushup_end:
            t = frame / pushup_end if pushup_end > 0 else 1.0
            # Push up from prone
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 1.2 * (1 - t * 0.5) * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.8 * (1 - t * 0.3) * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, (0.6 - 1.0 * t) * intensity))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (-0.3 - 0.5 * t) * intensity))
        elif frame <= stand_start:
            t = (frame - pushup_end) / (stand_start - pushup_end) if stand_start > pushup_end else 1.0
            # Transition to kneeling
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.6 * (1 - t) * intensity))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.56 * (1 - t) * intensity))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * t * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.7 * t * intensity))
        else:
            t = (frame - stand_start) / (frame_count - stand_start) if frame_count > stand_start else 1.0
            ease = smoothstep(t)
            # Stand up
            kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.0))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.0))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.7 * (1 - ease) * intensity))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.0))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.0))
    return kfs


def generate_weapon_draw_keyframes(frame_count: int = 16, intensity: float = 1.0) -> list[Keyframe]:
    """Reach for weapon and draw/unsheathe."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    reach_end = int(0.4 * frame_count)
    for frame in range(frame_count + 1):
        if frame <= reach_end:
            t = frame / reach_end if reach_end > 0 else 1.0
            # Right hand reaches to hip/back
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.4 * t * intensity))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, 0.6 * t * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.1 * t * intensity))
        else:
            t = (frame - reach_end) / (frame_count - reach_end) if frame_count > reach_end else 1.0
            ease = smoothstep(t)
            # Draw forward to ready position
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (0.4 - 0.7 * ease) * intensity))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, (0.6 - 0.8 * ease) * intensity))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.1 * (1 - ease) * intensity))
    return kfs


def generate_weapon_sheathe_keyframes(frame_count: int = 16, intensity: float = 1.0) -> list[Keyframe]:
    """Return weapon to holster/sheathe position."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        ease = smoothstep(t)
        # Move arm to rest, reverse of draw
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.3 * (1 - ease) * intensity))
        kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.2 * math.sin(t * math.pi) * intensity))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.05 * math.sin(t * math.pi) * intensity))
    return kfs


# ---------------------------------------------------------------------------
# AAA completeness — remaining locomotion/combat/interaction generators
# ---------------------------------------------------------------------------

def _simple_cycle(bones_cfg: dict, frame_count: int, intensity: float) -> list[Keyframe]:
    """Helper: generate a simple sine cycle from {bone: (channel, axis, amp, phase)}."""
    frame_count = max(1, frame_count)
    kfs: list[Keyframe] = []
    for frame in range(frame_count + 1):
        t = frame / frame_count
        a = t * 2 * math.pi
        for bone, (ch, ax, amp, phase) in bones_cfg.items():
            kfs.append(Keyframe(bone, ch, ax, frame, amp * intensity * math.sin(a + phase)))
    return kfs


def generate_swim_keyframes(fc: int = 32, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    return _simple_cycle({
        "DEF-upper_arm.L": ("rotation_euler", 0, 0.6, 0.0),
        "DEF-upper_arm.R": ("rotation_euler", 0, 0.6, math.pi),
        "DEF-thigh.L": ("rotation_euler", 0, 0.4, math.pi),
        "DEF-thigh.R": ("rotation_euler", 0, 0.4, 0.0),
        "DEF-spine.001": ("rotation_euler", 0, 0.08, 0.0),
        "DEF-spine": ("location", 2, 0.03, math.pi / 2),
    }, fc, i)


def generate_climb_keyframes(fc: int = 24, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    return _simple_cycle({
        "DEF-upper_arm.L": ("rotation_euler", 0, -0.8, 0.0),
        "DEF-upper_arm.R": ("rotation_euler", 0, -0.8, math.pi),
        "DEF-thigh.L": ("rotation_euler", 0, 0.6, math.pi),
        "DEF-thigh.R": ("rotation_euler", 0, 0.6, 0.0),
        "DEF-spine.001": ("rotation_euler", 0, -0.1, 0.0),
        "DEF-spine": ("location", 2, 0.05, 0.0),
    }, fc, i)


def generate_slide_keyframes(fc: int = 16, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.2 * i))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.3 * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * i))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.7 * i))
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.3 * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.2 * i))
    return kfs


def generate_crouch_walk_keyframes(fc: int = 28, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        a = t * 2 * math.pi
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * i + 0.25 * math.sin(a) * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * i + 0.25 * math.sin(a + math.pi) * i))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.5 * i))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.5 * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.2 * i))
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.1 * math.sin(a + math.pi) * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.1 * math.sin(a) * i))
    return kfs


def generate_ladder_climb_keyframes(fc: int = 24, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    return _simple_cycle({
        "DEF-upper_arm.L": ("rotation_euler", 0, -1.0, 0.0),
        "DEF-upper_arm.R": ("rotation_euler", 0, -1.0, math.pi),
        "DEF-forearm.L": ("rotation_euler", 0, -0.5, 0.3),
        "DEF-forearm.R": ("rotation_euler", 0, -0.5, math.pi + 0.3),
        "DEF-thigh.L": ("rotation_euler", 0, 0.5, math.pi),
        "DEF-thigh.R": ("rotation_euler", 0, 0.5, 0.0),
        "DEF-shin.L": ("rotation_euler", 0, -0.3, math.pi + 0.5),
        "DEF-shin.R": ("rotation_euler", 0, -0.3, 0.5),
    }, fc, i)


def generate_parry_body_keyframes(fc: int = 14, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    deflect = int(0.25 * fc)
    for frame in range(fc + 1):
        if frame <= deflect:
            t = frame / deflect if deflect > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.7 * t * i))
            kfs.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.4 * t * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.15 * t * i))
        else:
            r = (frame - deflect) / (fc - deflect) if fc > deflect else 1.0
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.7 * (1 - r) * i))
            kfs.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.4 * (1 - r) * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.15 * (1 - r) * i))
    return kfs


def generate_riposte_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    antic = int(0.3 * fc)
    strike = int(0.5 * fc)
    for frame in range(fc + 1):
        if frame <= antic:
            t = frame / antic if antic > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.6 * t * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.2 * t * i))
        elif frame <= strike:
            t = (frame - antic) / (strike - antic) if strike > antic else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (-0.6 + 1.8 * t) * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, (-0.2 + 0.4 * t) * i))
        else:
            t = (frame - strike) / (fc - strike) if fc > strike else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 1.2 * (1 - t) * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.2 * (1 - t) * i))
    return kfs


def generate_plunge_attack_keyframes(fc: int = 16, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        ease = smoothstep(t)
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -1.2 * ease * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.2 * ease * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.4 * ease * i))
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.5 * ease * i))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * ease * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * ease * i))
    return kfs


def generate_projectile_throw_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    wind = int(0.4 * fc)
    release = int(0.55 * fc)
    for frame in range(fc + 1):
        if frame <= wind:
            t = frame / wind if wind > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.8 * t * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.2 * t * i))
        elif frame <= release:
            t = (frame - wind) / (release - wind) if release > wind else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (-0.8 + 2.0 * t) * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, (-0.2 + 0.4 * t) * i))
        else:
            t = (frame - release) / (fc - release) if fc > release else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 1.2 * (1 - t) * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.2 * (1 - t) * i))
    return kfs


def generate_beam_aim_keyframes(fc: int = 36, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        hold = min(1.0, t * 3)
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.7 * hold * i))
        kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.3 * hold * i))
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.4 * hold * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.05 * hold * i))
        tremor = 0.01 * i * math.sin(t * 10 * math.pi) * hold
        kfs.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, tremor))
    return kfs


def generate_summon_ritual_keyframes(fc: int = 48, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        a = t * 2 * math.pi
        raise_t = min(1.0, t * 2)
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.6 * raise_t * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.6 * raise_t * i))
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.5 * raise_t * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.5 * raise_t * i))
        pulse = 0.04 * i * math.sin(a * 3) * raise_t
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.1 * raise_t * i + pulse))
        kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, pulse * 0.5))
    return kfs


def generate_mount_keyframes(fc: int = 24, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    swing = int(0.5 * fc)
    for frame in range(fc + 1):
        if frame <= swing:
            t = frame / swing if swing > 0 else 1.0
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 1, frame, 0.8 * t * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * t * i))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.3 * t * i))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.3 * t * i))
        else:
            t = (frame - swing) / (fc - swing) if fc > swing else 1.0
            ease = smoothstep(t)
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 1, frame, 0.8 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * ease * i))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * ease * i))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.3 * (1 - 0.5 * ease) * i))
    return kfs


def generate_dismount_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        ease = smoothstep(t)
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * (1 - ease) * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * (1 - ease) * i))
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.15 * math.sin(t * math.pi) * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 1, frame, 0.6 * (1 - ease) * i))
    return kfs


def generate_pickup_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    bend = int(0.5 * fc)
    for frame in range(fc + 1):
        if frame <= bend:
            t = frame / bend if bend > 0 else 1.0
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * t * i))
            kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.3 * t * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * t * i))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * t * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.6 * t * i))
        else:
            t = (frame - bend) / (fc - bend) if fc > bend else 1.0
            ease = smoothstep(t)
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.3 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (0.6 - 0.9 * ease) * i))
    return kfs


def generate_push_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        push = math.sin(t * math.pi)
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.5 * push * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.5 * push * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.15 * push * i))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * push * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.1 * push * i))
    return kfs


def generate_pull_keyframes(fc: int = 20, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        pull = math.sin(t * math.pi)
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.4 * pull * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.4 * pull * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.15 * pull * i))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, -0.15 * pull * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.1 * pull * i))
    return kfs


def generate_ledge_climb_keyframes(fc: int = 24, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    pull_end = int(0.5 * fc)
    for frame in range(fc + 1):
        if frame <= pull_end:
            t = frame / pull_end if pull_end > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -1.0 * t * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.0 * t * i))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.5 * t * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * t * i))
        else:
            t = (frame - pull_end) / (fc - pull_end) if fc > pull_end else 1.0
            ease = smoothstep(t)
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -1.0 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.0 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-spine", "location", 2, frame, 0.5 * i))
            kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, (0.6 - 0.6 * ease) * i))
    return kfs


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_LOCO_GENERATORS = {
    "sprint": lambda p: generate_sprint_keyframes(p["frame_count"], p["intensity"]),
    "strafe_left": lambda p: generate_strafe_keyframes(p["frame_count"], "left", p["intensity"]),
    "strafe_right": lambda p: generate_strafe_keyframes(p["frame_count"], "right", p["intensity"]),
    "walk_backward": lambda p: generate_walk_backward_keyframes(p["frame_count"], p["intensity"]),
    "jump_takeoff": lambda p: generate_jump_takeoff_keyframes(p["frame_count"], p["intensity"]),
    "jump_apex": lambda p: generate_jump_apex_keyframes(p["frame_count"], p["intensity"]),
    "jump_land": lambda p: generate_jump_land_keyframes(p["frame_count"], p["intensity"]),
    "fall_loop": lambda p: generate_fall_loop_keyframes(p["frame_count"], p["intensity"]),
    "dodge_roll": lambda p: generate_dodge_roll_keyframes(p["frame_count"], p["intensity"]),
    "backstep": lambda p: generate_backstep_keyframes(p["frame_count"], p["intensity"]),
    "stagger": lambda p: generate_stagger_keyframes(p["frame_count"], p["intensity"]),
    "knockback": lambda p: generate_knockback_keyframes(p["frame_count"], p["intensity"]),
    "knockdown": lambda p: generate_knockdown_keyframes(p["frame_count"], p["intensity"]),
    "getup": lambda p: generate_getup_keyframes(p["frame_count"], p["intensity"]),
    "weapon_draw": lambda p: generate_weapon_draw_keyframes(p["frame_count"], p["intensity"]),
    "weapon_sheathe": lambda p: generate_weapon_sheathe_keyframes(p["frame_count"], p["intensity"]),
    "swim": lambda p: generate_swim_keyframes(p["frame_count"], p["intensity"]),
    "climb": lambda p: generate_climb_keyframes(p["frame_count"], p["intensity"]),
    "slide": lambda p: generate_slide_keyframes(p["frame_count"], p["intensity"]),
    "crouch_walk": lambda p: generate_crouch_walk_keyframes(p["frame_count"], p["intensity"]),
    "ladder_climb": lambda p: generate_ladder_climb_keyframes(p["frame_count"], p["intensity"]),
    "parry_body": lambda p: generate_parry_body_keyframes(p["frame_count"], p["intensity"]),
    "riposte": lambda p: generate_riposte_keyframes(p["frame_count"], p["intensity"]),
    "plunge_attack": lambda p: generate_plunge_attack_keyframes(p["frame_count"], p["intensity"]),
    "projectile_throw": lambda p: generate_projectile_throw_keyframes(p["frame_count"], p["intensity"]),
    "beam_aim": lambda p: generate_beam_aim_keyframes(p["frame_count"], p["intensity"]),
    "summon_ritual": lambda p: generate_summon_ritual_keyframes(p["frame_count"], p["intensity"]),
    "mount": lambda p: generate_mount_keyframes(p["frame_count"], p["intensity"]),
    "dismount": lambda p: generate_dismount_keyframes(p["frame_count"], p["intensity"]),
    "pickup": lambda p: generate_pickup_keyframes(p["frame_count"], p["intensity"]),
    "push": lambda p: generate_push_keyframes(p["frame_count"], p["intensity"]),
    "pull": lambda p: generate_pull_keyframes(p["frame_count"], p["intensity"]),
    "ledge_climb": lambda p: generate_ledge_climb_keyframes(p["frame_count"], p["intensity"]),
}


def generate_locomotion_keyframes(params: dict) -> list[Keyframe]:
    loco_type = params["loco_type"]
    if loco_type not in _LOCO_GENERATORS:
        raise ValueError(f"Unknown loco_type: {loco_type!r}")
    return _LOCO_GENERATORS[loco_type](params)
