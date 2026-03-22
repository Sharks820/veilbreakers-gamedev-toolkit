"""Social/emote animation generators for character expression.

Covers non-combat character animations:
  - talk_gesture: Conversation hand movements
  - emote_wave: Friendly wave
  - emote_bow: Respectful bow
  - emote_point: Point at target
  - sit_down: Transition to sitting
  - sleep: Lying down rest pose
  - eat_drink: Consumption gesture

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


VALID_SOCIAL_TYPES: frozenset[str] = frozenset({
    "talk_gesture", "emote_wave", "emote_bow", "emote_point",
    "sit_down", "sleep", "eat_drink",
})


def validate_social_params(params: dict) -> dict:
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    social_type = params.get("social_type", "talk_gesture")
    if social_type not in VALID_SOCIAL_TYPES:
        raise ValueError(f"Invalid social_type: {social_type!r}")
    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4")
    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0")
    return {"object_name": object_name, "social_type": social_type,
            "frame_count": frame_count, "intensity": intensity}


def generate_talk_gesture_keyframes(fc: int = 48, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        a = t * 2 * math.pi
        # Conversational hand gestures
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.3 * i + 0.15 * math.sin(a * 2) * i))
        kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.2 * i + 0.1 * math.sin(a * 3) * i))
        kfs.append(Keyframe("DEF-hand.R", "rotation_euler", 1, frame, 0.15 * math.sin(a * 2.5) * i))
        # Subtle body sway
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.02 * math.sin(a) * i))
        # Head nods while talking
        kfs.append(Keyframe("DEF-spine.004", "rotation_euler", 0, frame, 0.04 * math.sin(a * 1.5) * i))
    return kfs


def generate_emote_wave_keyframes(fc: int = 36, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    raise_end = int(0.25 * fc)
    wave_end = int(0.75 * fc)
    for frame in range(fc + 1):
        if frame <= raise_end:
            t = frame / raise_end if raise_end > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.2 * t * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.3 * t * i))
        elif frame <= wave_end:
            wave_t = (frame - raise_end) / (wave_end - raise_end) if wave_end > raise_end else 0.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.2 * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.3 * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 1, frame, 0.4 * math.sin(wave_t * 4 * math.pi) * i))
        else:
            t = (frame - wave_end) / (fc - wave_end) if fc > wave_end else 1.0
            ease = t * t * (3 - 2 * t)
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.2 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.3 * (1 - ease) * i))
    return kfs


def generate_emote_bow_keyframes(fc: int = 36, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    bow_end = int(0.4 * fc)
    hold_end = int(0.7 * fc)
    for frame in range(fc + 1):
        if frame <= bow_end:
            t = frame / bow_end if bow_end > 0 else 1.0
            ease = t * t * (3 - 2 * t)
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * ease * i))
            kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.3 * ease * i))
            kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.2 * ease * i))
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.2 * ease * i))
        elif frame <= hold_end:
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * i))
            kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.3 * i))
        else:
            t = (frame - hold_end) / (fc - hold_end) if fc > hold_end else 1.0
            ease = t * t * (3 - 2 * t)
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.3 * (1 - ease) * i))
    return kfs


def generate_emote_point_keyframes(fc: int = 24, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    extend_end = int(0.35 * fc)
    for frame in range(fc + 1):
        if frame <= extend_end:
            t = frame / extend_end if extend_end > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.8 * t * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.2 * t * i))
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, 0.1 * t * i))
        else:
            hold_t = (frame - extend_end) / (fc - extend_end) if fc > extend_end else 1.0
            ease = hold_t * hold_t * (3 - 2 * hold_t)
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.8 * (1 - ease * 0.3) * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.2 * (1 - ease * 0.3) * i))
    return kfs


def generate_sit_down_keyframes(fc: int = 30, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        ease = t * t * (3 - 2 * t)
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 1.2 * ease * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 1.2 * ease * i))
        kfs.append(Keyframe("DEF-shin.L", "rotation_euler", 0, frame, -1.2 * ease * i))
        kfs.append(Keyframe("DEF-shin.R", "rotation_euler", 0, frame, -1.2 * ease * i))
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.5 * ease * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.05 * ease * i))
    return kfs


def generate_sleep_keyframes(fc: int = 36, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    for frame in range(fc + 1):
        t = frame / fc
        ease = t * t * (3 - 2 * t)
        kfs.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, 1.3 * ease * i))
        kfs.append(Keyframe("DEF-spine", "location", 2, frame, -0.8 * ease * i))
        kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * ease * i))
        kfs.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.4 * ease * i))
        kfs.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.5 * ease * i))
        kfs.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.3 * ease * i))
        kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.5 * ease * i))
    return kfs


def generate_eat_drink_keyframes(fc: int = 36, i: float = 1.0) -> list[Keyframe]:
    fc = max(1, fc)
    kfs: list[Keyframe] = []
    raise_end = int(0.3 * fc)
    drink_end = int(0.7 * fc)
    for frame in range(fc + 1):
        if frame <= raise_end:
            t = frame / raise_end if raise_end > 0 else 1.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.6 * t * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.8 * t * i))
        elif frame <= drink_end:
            dt = (frame - raise_end) / (drink_end - raise_end) if drink_end > raise_end else 0.0
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.6 * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.8 * i))
            kfs.append(Keyframe("DEF-spine.004", "rotation_euler", 0, frame, -0.15 * i))
            sip = 0.03 * math.sin(dt * 3 * math.pi) * i
            kfs.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, sip))
        else:
            t = (frame - drink_end) / (fc - drink_end) if fc > drink_end else 1.0
            ease = t * t * (3 - 2 * t)
            kfs.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -0.6 * (1 - ease) * i))
            kfs.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.8 * (1 - ease) * i))
    return kfs


_SOCIAL_GENERATORS = {
    "talk_gesture": lambda p: generate_talk_gesture_keyframes(p["frame_count"], p["intensity"]),
    "emote_wave": lambda p: generate_emote_wave_keyframes(p["frame_count"], p["intensity"]),
    "emote_bow": lambda p: generate_emote_bow_keyframes(p["frame_count"], p["intensity"]),
    "emote_point": lambda p: generate_emote_point_keyframes(p["frame_count"], p["intensity"]),
    "sit_down": lambda p: generate_sit_down_keyframes(p["frame_count"], p["intensity"]),
    "sleep": lambda p: generate_sleep_keyframes(p["frame_count"], p["intensity"]),
    "eat_drink": lambda p: generate_eat_drink_keyframes(p["frame_count"], p["intensity"]),
}


def generate_social_keyframes(params: dict) -> list[Keyframe]:
    social_type = params["social_type"]
    if social_type not in _SOCIAL_GENERATORS:
        raise ValueError(f"Unknown social_type: {social_type!r}")
    return _SOCIAL_GENERATORS[social_type](params)
