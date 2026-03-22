"""Combat command flow animation generators for VeilBreakers tactical RPG.

Implements full combat animation vocabulary beyond basic attacks:

P0 (must have):
  - generate_command_receive_keyframes: Subtle nod/ready stance
  - generate_combat_idle_keyframes: Brand-parameterized idle stance
  - generate_approach_keyframes: Walk toward target with wind-up
  - generate_return_to_formation_keyframes: Post-attack walk back
  - generate_guard_keyframes: Raise guard pose

P1 (should have):
  - generate_flee_keyframes: Turn and run, optional stumble
  - generate_target_switch_keyframes: Head turn, body pivot, settle
  - generate_synergy_activation_keyframes: Team flash pose

P2 (nice to have):
  - generate_ultimate_windup_keyframes: Extended anticipation
  - generate_victory_pose_keyframes: Brand-specific celebration
  - generate_defeat_collapse_keyframes: Brand-specific death

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Valid constants
# ---------------------------------------------------------------------------

VALID_BRANDS: frozenset[str] = frozenset({
    "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
    "LEECH", "GRACE", "MEND", "RUIN", "VOID",
})

VALID_COMBAT_COMMANDS: frozenset[str] = frozenset({
    "command_receive", "combat_idle", "approach", "return_to_formation",
    "guard", "flee", "target_switch", "synergy_activation",
    "ultimate_windup", "victory_pose", "defeat_collapse",
})

# Brand-specific combat idle stance presets
_BRAND_IDLE_STYLES: dict[str, dict[str, float]] = {
    "IRON":    {"spine_lean": 0.05, "arm_spread": 0.15, "sway_amp": 0.005, "sway_freq": 0.5},
    "SAVAGE":  {"spine_lean": 0.10, "arm_spread": 0.25, "sway_amp": 0.02, "sway_freq": 1.2},
    "SURGE":   {"spine_lean": 0.02, "arm_spread": 0.10, "sway_amp": 0.03, "sway_freq": 2.0},
    "VENOM":   {"spine_lean": 0.08, "arm_spread": 0.12, "sway_amp": 0.015, "sway_freq": 0.8},
    "DREAD":   {"spine_lean": 0.00, "arm_spread": 0.05, "sway_amp": 0.002, "sway_freq": 0.2},
    "LEECH":   {"spine_lean": 0.06, "arm_spread": 0.18, "sway_amp": 0.012, "sway_freq": 0.7},
    "GRACE":   {"spine_lean": -0.02, "arm_spread": 0.08, "sway_amp": 0.02, "sway_freq": 0.6},
    "MEND":    {"spine_lean": -0.03, "arm_spread": 0.06, "sway_amp": 0.01, "sway_freq": 0.5},
    "RUIN":    {"spine_lean": 0.12, "arm_spread": 0.30, "sway_amp": 0.025, "sway_freq": 1.5},
    "VOID":    {"spine_lean": 0.01, "arm_spread": 0.03, "sway_amp": 0.008, "sway_freq": 0.3},
}

# Brand-specific defeat collapse styles
_BRAND_DEFEAT_STYLES: dict[str, str] = {
    "IRON": "crumble",      # Heavy forward collapse
    "SAVAGE": "violent",     # Thrashing then fall
    "SURGE": "spasm",        # Electric spasm then drop
    "VENOM": "dissolve",     # Slow melt downward
    "DREAD": "frozen",       # Stiffen then topple
    "LEECH": "wither",       # Shrink inward
    "GRACE": "graceful",     # Elegant slow fall
    "MEND": "peaceful",      # Gentle kneel then rest
    "RUIN": "explosive",     # Jerk backward violently
    "VOID": "implode",       # Pull inward then collapse
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_combat_command_params(params: dict) -> dict:
    """Validate combat command animation parameters.

    Args:
        params: Dict with object_name, command, brand, frame_count, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    command = params.get("command")
    if not command:
        raise ValueError("command is required")
    if command not in VALID_COMBAT_COMMANDS:
        raise ValueError(
            f"Invalid command: {command!r}. Valid: {sorted(VALID_COMBAT_COMMANDS)}"
        )

    brand = params.get("brand", "IRON").upper()
    if brand not in VALID_BRANDS:
        raise ValueError(f"Invalid brand: {brand!r}. Valid: {sorted(VALID_BRANDS)}")

    frame_count = int(params.get("frame_count", 24))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    stumble = bool(params.get("stumble", False))

    return {
        "object_name": object_name,
        "command": command,
        "brand": brand,
        "frame_count": frame_count,
        "stumble": stumble,
    }


# ---------------------------------------------------------------------------
# P0 Generators
# ---------------------------------------------------------------------------

def generate_command_receive_keyframes(
    frame_count: int = 12,
) -> list[Keyframe]:
    """Subtle nod/ready stance acknowledging a command. 8-12 frames."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Quick nod (head dips at 30%, recovers by 70%)
        if t <= 0.3:
            nod = 0.15 * (t / 0.3)
        elif t <= 0.7:
            nod = 0.15 * (1.0 - (t - 0.3) / 0.4)
        else:
            nod = 0.0
        keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 0, frame, nod))

        # Slight spine straighten (readiness)
        straighten = -0.05 * math.sin(t * math.pi)
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, straighten))

    return keyframes


def generate_combat_idle_keyframes(
    brand: str = "IRON",
    frame_count: int = 48,
) -> list[Keyframe]:
    """Brand-parameterized combat idle stance with subtle motion.

    IRON=heavy wide stance, GRACE=flowing sway, SURGE=twitchy shifts,
    DREAD=unnaturally still.
    """
    keyframes: list[Keyframe] = []
    style = _BRAND_IDLE_STYLES.get(brand.upper(), _BRAND_IDLE_STYLES["IRON"])

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Spine lean (brand-specific posture)
        lean = style["spine_lean"]
        sway = style["sway_amp"] * math.sin(t * 2 * math.pi * style["sway_freq"])
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, lean + sway))

        # Lateral sway
        lateral = style["sway_amp"] * 0.7 * math.sin(t * 2 * math.pi * style["sway_freq"] * 0.5 + math.pi / 3)
        keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, lateral))

        # Arm spread (wider for aggressive brands)
        arm_base = style["arm_spread"]
        arm_sway = style["sway_amp"] * 0.5 * math.sin(t * 2 * math.pi * style["sway_freq"] * 0.3)
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -(arm_base + arm_sway)))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, arm_base + arm_sway))

        # Breathing
        breath = 0.015 * math.sin(t * 2 * math.pi)
        keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, breath))

    return keyframes


def generate_approach_keyframes(
    frame_count: int = 32,
) -> list[Keyframe]:
    """Walk toward target with attack wind-up in last 25%."""
    keyframes: list[Keyframe] = []
    windup_start = int(0.75 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Walking motion (simplified step cycle for first 75%)
        if frame <= windup_start:
            walk_t = frame / windup_start if windup_start > 0 else 0.0
            # Leg cycle
            leg_amp = 0.4
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame,
                                      leg_amp * math.sin(walk_t * 4 * math.pi)))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame,
                                      leg_amp * math.sin(walk_t * 4 * math.pi + math.pi)))
            # Arm counter-swing
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      0.2 * math.sin(walk_t * 4 * math.pi + math.pi)))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      0.2 * math.sin(walk_t * 4 * math.pi)))
            # No wind-up yet
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.0))
        else:
            # Wind-up: transition to attack ready
            windup_t = (frame - windup_start) / (frame_count - windup_start) if frame_count > windup_start else 1.0
            # Legs slow down and plant
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * (1 - windup_t)))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, -0.1 * windup_t))
            # Right arm pulls back for strike
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.6 * windup_t))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.0))
            # Torso twists for power
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, -0.15 * windup_t))

        # Spine forward lean (slight throughout, more at end)
        spine_lean = 0.05 + 0.05 * t
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spine_lean))

    return keyframes


def generate_return_to_formation_keyframes(
    frame_count: int = 32,
) -> list[Keyframe]:
    """Post-attack walk back, weapon lowered, relaxed posture."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Relaxed walk
        leg_amp = 0.3
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame,
                                  leg_amp * math.sin(t * 4 * math.pi)))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame,
                                  leg_amp * math.sin(t * 4 * math.pi + math.pi)))

        # Arms lowered, relaxed swing
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                  0.15 * math.sin(t * 4 * math.pi + math.pi) + 0.1))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                  0.15 * math.sin(t * 4 * math.pi) + 0.1))

        # Relaxed spine (slight backward lean = confidence)
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.03))

    return keyframes


def generate_guard_keyframes(
    frame_count: int = 16,
) -> list[Keyframe]:
    """Raise guard pose — arms/shield up, damage reduction hint."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Quick raise to guard (first 40%), then hold
        if t <= 0.4:
            guard_t = t / 0.4
        else:
            guard_t = 1.0

        # Arms raise to guard position
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.9 * guard_t))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.9 * guard_t))
        keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.5 * guard_t))
        keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.5 * guard_t))

        # Crouch slightly
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.1 * guard_t))
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.15 * guard_t))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.15 * guard_t))

        # Subtle breathing during hold
        if t > 0.4:
            hold_t = (t - 0.4) / 0.6
            breath = 0.01 * math.sin(hold_t * 4 * math.pi)
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, breath))

    return keyframes


# ---------------------------------------------------------------------------
# P1 Generators
# ---------------------------------------------------------------------------

def generate_flee_keyframes(
    frame_count: int = 24,
    stumble: bool = False,
) -> list[Keyframe]:
    """Turn and run animation. Optional stumble at low HP."""
    keyframes: list[Keyframe] = []

    # Turn phase (first 25%)
    turn_end = int(0.25 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= turn_end:
            turn_t = frame / turn_end if turn_end > 0 else 1.0
            # Spin 180 degrees (expressed as Y rotation on spine)
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, math.pi * turn_t))
        else:
            # Running away
            run_t = (frame - turn_end) / (frame_count - turn_end) if frame_count > turn_end else 0.0
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, math.pi))

            # Panicked run (faster, larger amplitude)
            leg_amp = 0.7
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame,
                                      leg_amp * math.sin(run_t * 6 * math.pi)))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame,
                                      leg_amp * math.sin(run_t * 6 * math.pi + math.pi)))

            # Frantic arm pump
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      0.5 * math.sin(run_t * 6 * math.pi + math.pi)))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      0.5 * math.sin(run_t * 6 * math.pi)))

            # Stumble variant
            if stumble and 0.4 <= run_t <= 0.6:
                stumble_t = (run_t - 0.4) / 0.2
                # Forward pitch
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                          0.4 * math.sin(stumble_t * math.pi)))
                # Knee buckle
                keyframes.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame,
                                          -0.3 * math.sin(stumble_t * math.pi)))

    return keyframes


def generate_target_switch_keyframes(
    frame_count: int = 16,
) -> list[Keyframe]:
    """Head turn -> body pivot -> settle into new facing."""
    keyframes: list[Keyframe] = []

    head_end = int(0.3 * frame_count)
    pivot_end = int(0.7 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= head_end:
            # Phase 1: Head turns first (anticipation)
            head_t = frame / head_end if head_end > 0 else 1.0
            keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 1, frame, 0.4 * head_t))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.0))
        elif frame <= pivot_end:
            # Phase 2: Body follows head
            pivot_t = (frame - head_end) / (pivot_end - head_end) if pivot_end > head_end else 1.0
            keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 1, frame, 0.4))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.3 * pivot_t))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, 0.2 * pivot_t))
        else:
            # Phase 3: Settle (head reduces to match body)
            settle_t = (frame - pivot_end) / (frame_count - pivot_end) if frame_count > pivot_end else 1.0
            keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 1, frame, 0.4 * (1 - 0.5 * settle_t)))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.3))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, 0.2))

    return keyframes


def generate_synergy_activation_keyframes(
    brand: str = "IRON",
    frame_count: int = 24,
) -> list[Keyframe]:
    """Team synergy flash pose with brand energy pulse."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Quick power pose (arms out) at 30%
        if t <= 0.3:
            pose_t = t / 0.3
            arm_val = -1.0 * pose_t
            spine_val = -0.15 * pose_t
        elif t <= 0.5:
            # Hold pose
            arm_val = -1.0
            spine_val = -0.15
        else:
            # Return
            return_t = (t - 0.5) / 0.5
            arm_val = -1.0 * (1 - return_t)
            spine_val = -0.15 * (1 - return_t)

        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_val))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_val))
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spine_val))

        # Energy pulse on chest
        if 0.25 <= t <= 0.55:
            pulse_t = (t - 0.25) / 0.3
            pulse = 0.03 * math.sin(pulse_t * 4 * math.pi)
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, pulse))

    return keyframes


# ---------------------------------------------------------------------------
# P2 Generators
# ---------------------------------------------------------------------------

def generate_ultimate_windup_keyframes(
    frame_count: int = 48,
) -> list[Keyframe]:
    """Extended anticipation (2-3x normal), energy gathering."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Long wind-up: arms gradually rise, body tenses
        # Exponential ease-in for dramatic build
        ease_t = t * t  # quadratic ease-in

        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -1.2 * ease_t))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.2 * ease_t))

        # Spine arches back
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.3 * ease_t))
        keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, -0.2 * ease_t))

        # Energy gathering tremor (increasing frequency)
        tremor_freq = 2 + 8 * t  # accelerating tremor
        tremor_amp = 0.02 * t
        tremor = tremor_amp * math.sin(t * tremor_freq * 2 * math.pi)
        keyframes.append(Keyframe("DEF-hand.L", "rotation_euler", 0, frame, tremor))
        keyframes.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, -tremor))

        # Legs brace
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.15 * ease_t))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.15 * ease_t))

    return keyframes


def generate_victory_pose_keyframes(
    brand: str = "IRON",
    frame_count: int = 36,
) -> list[Keyframe]:
    """Brand-specific celebration pose."""
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Quick transition to pose (first 30%), then hold with flourish
        if t <= 0.3:
            pose_t = t / 0.3
        else:
            pose_t = 1.0

        flourish_t = max(0, (t - 0.3) / 0.7) if t > 0.3 else 0.0

        brand_u = brand.upper()
        if brand_u in ("IRON", "SAVAGE", "RUIN"):
            # Triumphant fist pump
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.5 * pose_t))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.1 * pose_t))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.2 * pose_t))
        elif brand_u in ("GRACE", "MEND"):
            # Elegant bow
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * pose_t))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.2 * pose_t))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.3 * pose_t))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.3 * pose_t))
        else:
            # Power stance (SURGE, VENOM, DREAD, LEECH, VOID)
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.8 * pose_t))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.8 * pose_t))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.05 * pose_t))

        # Subtle breathing during hold
        if flourish_t > 0:
            breath = 0.01 * math.sin(flourish_t * 4 * math.pi)
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, breath))

    return keyframes


def generate_defeat_collapse_keyframes(
    brand: str = "IRON",
    frame_count: int = 36,
) -> list[Keyframe]:
    """Brand-specific death/defeat collapse animation."""
    keyframes: list[Keyframe] = []
    brand_u = brand.upper()
    style = _BRAND_DEFEAT_STYLES.get(brand_u, "crumble")

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if style == "crumble":
            # Heavy forward collapse (IRON)
            ease_t = t * t
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.8 * ease_t))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * ease_t))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.4 * ease_t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.4 * ease_t))
            keyframes.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.5 * ease_t))
            keyframes.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.5 * ease_t))

        elif style == "implode":
            # Pull inward then collapse (VOID)
            if t <= 0.5:
                curl_t = t / 0.5
                # Curl inward
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.5 * curl_t))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.4 * curl_t))
                keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.8 * curl_t))
                keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.8 * curl_t))
                keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * curl_t))
                keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6 * curl_t))
            else:
                collapse_t = (t - 0.5) / 0.5
                # Sudden drop
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.5 + 0.4 * collapse_t))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.4 + 0.3 * collapse_t))
                keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.8))
                keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.8))
                keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6))
                keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6))

        elif style == "violent":
            # Thrashing then fall (SAVAGE)
            if t <= 0.4:
                thrash = 0.4 * math.sin(t * 15 * math.pi) * (1 - t / 0.4)
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, thrash))
                keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.5 * math.sin(t * 10)))
                keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.5 * math.sin(t * 10)))
            else:
                fall_t = (t - 0.4) / 0.6
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.8 * fall_t * fall_t))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * fall_t))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * t))

        elif style == "spasm":
            # Electric spasm then drop (SURGE)
            spasm = 0.15 * math.sin(t * 20 * math.pi) * max(0, 1 - t * 1.5)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spasm + 0.5 * t * t))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, spasm * 0.7))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, spasm * 2))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -spasm * 2))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * t * t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * t * t))

        elif style == "dissolve":
            # Slow melt downward (VENOM)
            melt = t * t * t  # cubic ease-in = very slow start
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.6 * melt))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * melt))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.4 * melt))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.4 * melt))
            keyframes.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.4 * melt))
            keyframes.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.4 * melt))

        elif style == "frozen":
            # Stiffen then topple (DREAD)
            if t <= 0.6:
                # Stiffen phase — barely move
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.02 * t))
            else:
                topple_t = (t - 0.6) / 0.4
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.9 * topple_t))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * topple_t))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.2 * t))

        elif style == "wither":
            # Shrink inward (LEECH)
            shrink = t * t
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.5 * shrink))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.4 * shrink))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.6 * shrink))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.6 * shrink))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.5 * shrink))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * shrink))

        elif style == "graceful":
            # Elegant slow fall (GRACE)
            grace = math.sin(t * math.pi / 2)  # smooth ease-out
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.4 * grace))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * grace))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * grace))
            keyframes.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.4 * grace))
            # One arm across body
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.3 * grace))

        elif style == "peaceful":
            # Gentle kneel then rest (MEND)
            if t <= 0.5:
                kneel = t / 0.5
                keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * kneel))
                keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6 * kneel))
                keyframes.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -0.8 * kneel))
                keyframes.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -0.8 * kneel))
            else:
                rest_t = (t - 0.5) / 0.5
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.4 * rest_t))
                keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6))
                keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6))

        elif style == "explosive":
            # Jerk backward violently (RUIN)
            if t <= 0.2:
                jerk = t / 0.2
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, -0.5 * jerk))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.4 * jerk))
            else:
                fall_t = (t - 0.2) / 0.8
                ease = fall_t * fall_t
                keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, -0.5 + 1.3 * ease))
                keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.4 + 1.0 * ease))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -0.3 * (1 - t)))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.3 * (1 - t)))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.3 * t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.3 * t))

        else:
            # Fallback generic collapse
            ease_t = t * t
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 0.7 * ease_t))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * ease_t))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.3 * ease_t))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.3 * ease_t))
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.35 * ease_t))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.35 * ease_t))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch function
# ---------------------------------------------------------------------------

_GENERATORS = {
    "command_receive": lambda p: generate_command_receive_keyframes(p["frame_count"]),
    "combat_idle": lambda p: generate_combat_idle_keyframes(p["brand"], p["frame_count"]),
    "approach": lambda p: generate_approach_keyframes(p["frame_count"]),
    "return_to_formation": lambda p: generate_return_to_formation_keyframes(p["frame_count"]),
    "guard": lambda p: generate_guard_keyframes(p["frame_count"]),
    "flee": lambda p: generate_flee_keyframes(p["frame_count"], p.get("stumble", False)),
    "target_switch": lambda p: generate_target_switch_keyframes(p["frame_count"]),
    "synergy_activation": lambda p: generate_synergy_activation_keyframes(p["brand"], p["frame_count"]),
    "ultimate_windup": lambda p: generate_ultimate_windup_keyframes(p["frame_count"]),
    "victory_pose": lambda p: generate_victory_pose_keyframes(p["brand"], p["frame_count"]),
    "defeat_collapse": lambda p: generate_defeat_collapse_keyframes(p["brand"], p["frame_count"]),
}


def generate_combat_command_keyframes(params: dict) -> list[Keyframe]:
    """Dispatch to the appropriate combat command generator.

    Args:
        params: Validated params dict with command, brand, frame_count, etc.

    Returns:
        List of Keyframe namedtuples.

    Raises:
        ValueError: If command is unknown.
    """
    command = params["command"]
    if command not in _GENERATORS:
        raise ValueError(f"Unknown command: {command!r}")
    return _GENERATORS[command](params)
