"""Spell-cast animation generators for magic/ability animations.

Provides three cast types:
  - generate_channel_keyframes: Arms raise gradually, energy gathering, looping hold
  - generate_release_keyframes: Sharp thrust/push, recoil recovery
  - generate_sustain_keyframes: Stable stance, rhythmic pulse, looping

Each type has anticipation -> active -> recovery phases matching _combat_timing format.
Supports cast_hand param: "left" | "right" | "both".

Pure-logic module (NO bpy imports). Returns keyframe data consumed by handlers.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Cast hand bone mappings
# ---------------------------------------------------------------------------

_CAST_HAND_BONES: dict[str, dict[str, list[str]]] = {
    "left": {
        "upper_arms": ["DEF-upper_arm.L"],
        "forearms": ["DEF-forearm.L"],
        "hands": ["DEF-hand.L"],
    },
    "right": {
        "upper_arms": ["DEF-upper_arm.R"],
        "forearms": ["DEF-forearm.R"],
        "hands": ["DEF-hand.R"],
    },
    "both": {
        "upper_arms": ["DEF-upper_arm.L", "DEF-upper_arm.R"],
        "forearms": ["DEF-forearm.L", "DEF-forearm.R"],
        "hands": ["DEF-hand.L", "DEF-hand.R"],
    },
}

VALID_CAST_HANDS: frozenset[str] = frozenset({"left", "right", "both"})

VALID_CAST_TYPES: frozenset[str] = frozenset({"channel", "release", "sustain"})

# ---------------------------------------------------------------------------
# Combat timing entries for spell casts
# ---------------------------------------------------------------------------

SPELL_CAST_TIMING: dict[str, dict[str, int]] = {
    "channel": {
        "anticipation_frames": 12,
        "active_frames": -1,  # -1 = looping
        "recovery_frames": 8,
        "cancel_window_start": 12,
        "cancel_window_end": -1,
        "vfx_frame": 10,
    },
    "release": {
        "anticipation_frames": 8,
        "active_frames": 4,
        "recovery_frames": 12,
        "cancel_window_start": 12,
        "cancel_window_end": 20,
        "vfx_frame": 8,
    },
    "sustain": {
        "anticipation_frames": 6,
        "active_frames": -1,  # -1 = looping
        "recovery_frames": 10,
        "cancel_window_start": 6,
        "cancel_window_end": -1,
        "vfx_frame": 5,
    },
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_spellcast_params(params: dict) -> dict:
    """Validate spell-cast animation parameters (pure-logic).

    Args:
        params: Dict with object_name, cast_type, cast_hand, frame_count.

    Returns:
        Normalized dict with validated parameters.

    Raises:
        ValueError: On invalid parameters.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    cast_type = params.get("cast_type", "channel")
    if cast_type not in VALID_CAST_TYPES:
        raise ValueError(
            f"Invalid cast_type: {cast_type!r}. Valid: {sorted(VALID_CAST_TYPES)}"
        )

    cast_hand = params.get("cast_hand", "both")
    if cast_hand not in VALID_CAST_HANDS:
        raise ValueError(
            f"Invalid cast_hand: {cast_hand!r}. Valid: {sorted(VALID_CAST_HANDS)}"
        )

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")

    return {
        "object_name": object_name,
        "cast_type": cast_type,
        "cast_hand": cast_hand,
        "frame_count": frame_count,
        "intensity": intensity,
    }


# ---------------------------------------------------------------------------
# Keyframe generators
# ---------------------------------------------------------------------------

def generate_channel_keyframes(
    cast_hand: str = "both",
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate channeling spell-cast keyframes.

    Arms raise gradually, energy gathering gesture, body tension increases.
    The active phase loops (hold position) for indefinite channeling.

    Phases:
        Anticipation (0-25%): Arms begin rising, slight lean forward
        Active (25-75%): Arms at gathering height, rhythmic pulse (looping)
        Recovery (75-100%): Arms lower, body relaxes

    Args:
        cast_hand: "left", "right", or "both".
        frame_count: Total frames.
        intensity: Value multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []
    bones = _CAST_HAND_BONES.get(cast_hand, _CAST_HAND_BONES["both"])

    antic_end = int(0.25 * frame_count)
    active_end = int(0.75 * frame_count)

    # Upper arms: raise to casting position
    for upper_arm in bones["upper_arms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                # Anticipation: gradually raise arm
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.8 * t * intensity  # negative = raise
            elif frame <= active_end:
                # Active: hold with slight pulse
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
                pulse = 0.05 * math.sin(active_t * 4 * math.pi) * intensity
                value = (-0.8 + pulse) * intensity
            else:
                # Recovery: lower arm
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = -0.8 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(upper_arm, "rotation_euler", 0, frame, value))

    # Forearms: slight bend inward during channel
    for forearm in bones["forearms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.4 * t * intensity
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
                pulse = 0.03 * math.sin(active_t * 4 * math.pi) * intensity
                value = (-0.4 + pulse) * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = -0.4 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(forearm, "rotation_euler", 0, frame, value))

    # Hands: open/spread during channel
    for hand in bones["hands"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = 0.3 * t * intensity
            elif frame <= active_end:
                value = 0.3 * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = 0.3 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(hand, "rotation_euler", 2, frame, value))

    # Spine: lean forward during channel
    for frame in range(frame_count + 1):
        if frame <= antic_end:
            t = frame / antic_end if antic_end > 0 else 1.0
            value = 0.1 * t * intensity
        elif frame <= active_end:
            value = 0.1 * intensity
        else:
            recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
            value = 0.1 * (1.0 - recover_t) * intensity
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, value))

    return keyframes


def generate_release_keyframes(
    cast_hand: str = "both",
    frame_count: int = 24,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate spell release keyframes.

    Sharp thrust/push motion, recoil recovery, energy dispersal.

    Phases:
        Anticipation (0-33%): Wind up / gather
        Active (33-50%): Sharp thrust forward
        Recovery (50-100%): Recoil and settle

    Args:
        cast_hand: "left", "right", or "both".
        frame_count: Total frames.
        intensity: Value multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []
    bones = _CAST_HAND_BONES.get(cast_hand, _CAST_HAND_BONES["both"])

    antic_end = int(0.33 * frame_count)
    active_end = int(0.50 * frame_count)

    # Upper arms: pull back then thrust forward
    for upper_arm in bones["upper_arms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.5 * t * intensity  # pull back
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 1.0
                value = (-0.5 + 1.5 * active_t) * intensity  # thrust forward
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = 1.0 * (1.0 - recover_t) * intensity  # return
            keyframes.append(Keyframe(upper_arm, "rotation_euler", 0, frame, value))

    # Forearms: extend during thrust
    for forearm in bones["forearms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.6 * t * intensity
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 1.0
                value = (-0.6 + 0.8 * active_t) * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = 0.2 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(forearm, "rotation_euler", 0, frame, value))

    # Spine: lean back then thrust forward
    for frame in range(frame_count + 1):
        if frame <= antic_end:
            t = frame / antic_end if antic_end > 0 else 1.0
            value = -0.15 * t * intensity
        elif frame <= active_end:
            active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 1.0
            value = (-0.15 + 0.4 * active_t) * intensity
        else:
            recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
            value = 0.25 * (1.0 - recover_t) * intensity
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, value))

    return keyframes


def generate_sustain_keyframes(
    cast_hand: str = "both",
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate sustained spell-cast keyframes.

    Stable stance, rhythmic pulse on arms/hands, looping for held spells.

    Phases:
        Anticipation (0-12.5%): Quick transition to sustain pose
        Active (12.5-80%): Rhythmic pulsing (looping)
        Recovery (80-100%): Release and settle

    Args:
        cast_hand: "left", "right", or "both".
        frame_count: Total frames.
        intensity: Value multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []
    bones = _CAST_HAND_BONES.get(cast_hand, _CAST_HAND_BONES["both"])

    antic_end = int(0.125 * frame_count)
    active_end = int(0.80 * frame_count)

    # Upper arms: hold at sustain height with rhythmic pulse
    for upper_arm in bones["upper_arms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.6 * t * intensity
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
                pulse = 0.08 * math.sin(active_t * 6 * math.pi) * intensity
                value = (-0.6 + pulse) * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = -0.6 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(upper_arm, "rotation_euler", 0, frame, value))

    # Forearms: steady with micro-pulse
    for forearm in bones["forearms"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = -0.3 * t * intensity
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
                pulse = 0.04 * math.sin(active_t * 6 * math.pi + math.pi / 4) * intensity
                value = (-0.3 + pulse) * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = -0.3 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(forearm, "rotation_euler", 0, frame, value))

    # Hands: rhythmic open/close
    for hand in bones["hands"]:
        for frame in range(frame_count + 1):
            if frame <= antic_end:
                t = frame / antic_end if antic_end > 0 else 1.0
                value = 0.2 * t * intensity
            elif frame <= active_end:
                active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
                value = (0.2 + 0.1 * math.sin(active_t * 6 * math.pi)) * intensity
            else:
                recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
                value = 0.2 * (1.0 - recover_t) * intensity
            keyframes.append(Keyframe(hand, "rotation_euler", 2, frame, value))

    # Spine: slight forward lean with breathing pulse
    for frame in range(frame_count + 1):
        if frame <= antic_end:
            t = frame / antic_end if antic_end > 0 else 1.0
            value = 0.08 * t * intensity
        elif frame <= active_end:
            active_t = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 0.0
            pulse = 0.02 * math.sin(active_t * 4 * math.pi) * intensity
            value = (0.08 + pulse) * intensity
        else:
            recover_t = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
            value = 0.08 * (1.0 - recover_t) * intensity
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, value))

    return keyframes


def get_spellcast_timing(cast_type: str) -> dict[str, int]:
    """Get combat timing data for a spell cast type.

    Args:
        cast_type: One of "channel", "release", "sustain".

    Returns:
        Dict with anticipation_frames, active_frames, recovery_frames,
        cancel_window_start, cancel_window_end, vfx_frame.

    Raises:
        ValueError: If cast_type is unknown.
    """
    if cast_type not in SPELL_CAST_TIMING:
        raise ValueError(
            f"Unknown cast_type: {cast_type!r}. Valid: {sorted(SPELL_CAST_TIMING)}"
        )
    return dict(SPELL_CAST_TIMING[cast_type])
