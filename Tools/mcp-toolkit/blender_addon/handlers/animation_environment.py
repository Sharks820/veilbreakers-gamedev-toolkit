"""Environmental and world animation generators for VeilBreakers.

Covers all non-character animations needed for a dark fantasy world:
  - Door animations (open/close/slam/creak)
  - Gate animations (portcullis raise/lower, drawbridge)
  - Destructible props (break/shatter/collapse)
  - Fire/torch flicker (flame sway, ember drift)
  - Water animations (wave, ripple, waterfall)
  - Flags/banners (wind cloth sim approximation)
  - Chains/ropes (pendulum swing, taut sway)
  - Traps (trigger, reset, idle)
  - Ambient props (candle flicker, chandelier sway, windmill rotation)
  - Interactable objects (chest open, lever pull, switch toggle)

Pure-logic module (NO bpy imports). Returns Keyframe data for
object-level transforms (location, rotation, scale) rather than
bone-level poses.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe
from ._shared_utils import smoothstep


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ENV_TYPES: frozenset[str] = frozenset({
    "door_open", "door_close", "door_slam", "door_creak",
    "gate_raise", "gate_lower", "drawbridge",
    "destructible_break", "destructible_shatter",
    "fire_flicker", "torch_sway",
    "water_wave", "water_ripple", "waterfall",
    "flag_wind", "banner_wind",
    "chain_swing", "rope_sway",
    "trap_trigger", "trap_reset", "trap_idle",
    "chest_open", "lever_pull", "switch_toggle",
    "candle_flicker", "chandelier_sway", "windmill_rotate",
})

# For environment animations, bone_name is the object name placeholder
ENV_ROOT = "ENV_ROOT"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_env_params(params: dict) -> dict:
    """Validate environment animation parameters."""
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    env_type = params.get("env_type", "door_open")
    if env_type not in VALID_ENV_TYPES:
        raise ValueError(f"Invalid env_type: {env_type!r}. Valid: {sorted(VALID_ENV_TYPES)}")

    frame_count = int(params.get("frame_count", 30))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")

    angle = float(params.get("angle", 90.0))
    speed = float(params.get("speed", 1.0))

    return {
        "object_name": object_name,
        "env_type": env_type,
        "frame_count": frame_count,
        "intensity": intensity,
        "angle": angle,
        "speed": speed,
    }


# ---------------------------------------------------------------------------
# Door animations
# ---------------------------------------------------------------------------

def generate_door_open_keyframes(
    frame_count: int = 30,
    angle: float = 90.0,
    speed: float = 1.0,
) -> list[Keyframe]:
    """Door swings open with realistic easing — fast start, slow settle."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Ease-out cubic for natural door swing
        ease_t = 1.0 - (1.0 - t) ** 3
        rot = angle_rad * ease_t * speed
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, rot))

    return keyframes


def generate_door_close_keyframes(
    frame_count: int = 24,
    angle: float = 90.0,
) -> list[Keyframe]:
    """Door swings closed — starts slow, accelerates to impact."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Ease-in quadratic for closing momentum
        ease_t = t * t
        rot = angle_rad * (1.0 - ease_t)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, rot))

    return keyframes


def generate_door_slam_keyframes(
    frame_count: int = 20,
    angle: float = 90.0,
) -> list[Keyframe]:
    """Door slams with impact bounce."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)
    impact_frame = int(0.5 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= impact_frame:
            t = frame / impact_frame if impact_frame > 0 else 1.0
            rot = angle_rad * (1.0 - smoothstep(t))  # fast close
        else:
            bounce_t = (frame - impact_frame) / (frame_count - impact_frame) if frame_count > impact_frame else 1.0
            # Damped bounce
            bounce = 0.05 * angle_rad * math.sin(bounce_t * 3 * math.pi) * (1 - bounce_t)
            rot = bounce
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, rot))

    return keyframes


def generate_door_creak_keyframes(
    frame_count: int = 48,
    angle: float = 45.0,
) -> list[Keyframe]:
    """Door opens slowly with creaking hesitation."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Step-wise opening with hesitation pauses
        base = angle_rad * smoothstep(t)
        hesitation = 0.02 * angle_rad * math.sin(t * 8 * math.pi) * (1 - t)
        rot = base + hesitation
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, rot))

    return keyframes


# ---------------------------------------------------------------------------
# Gate animations
# ---------------------------------------------------------------------------

def generate_gate_raise_keyframes(
    frame_count: int = 60,
    height: float = 3.0,
) -> list[Keyframe]:
    """Portcullis raises with chain-driven jerky motion."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Chain-driven: slight jerkiness superimposed on smooth raise
        smooth = height * smoothstep(t)
        jerk = 0.02 * height * math.sin(t * 12 * math.pi) * (1 - t)
        z = smooth + jerk
        keyframes.append(Keyframe(ENV_ROOT, "location", 2, frame, z))

    return keyframes


def generate_gate_lower_keyframes(
    frame_count: int = 30,
    height: float = 3.0,
) -> list[Keyframe]:
    """Portcullis drops with gravity acceleration and ground impact."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    drop_end = int(0.7 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= drop_end:
            t = frame / drop_end if drop_end > 0 else 1.0
            z = height * (1.0 - smoothstep(t))  # gravity acceleration
        else:
            bounce_t = (frame - drop_end) / (frame_count - drop_end) if frame_count > drop_end else 1.0
            z = 0.03 * height * math.sin(bounce_t * 4 * math.pi) * (1 - bounce_t)
        keyframes.append(Keyframe(ENV_ROOT, "location", 2, frame, z))

    return keyframes


def generate_drawbridge_keyframes(
    frame_count: int = 90,
    angle: float = 80.0,
) -> list[Keyframe]:
    """Drawbridge lowers on chains — slow controlled descent."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # S-curve for controlled lowering
        s_curve = smoothstep(t)
        rot = -angle_rad * s_curve
        # Slight chain wobble
        wobble = 0.01 * math.sin(t * 6 * math.pi) * (1 - t)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, rot + wobble))

    return keyframes


# ---------------------------------------------------------------------------
# Destructible animations
# ---------------------------------------------------------------------------

def generate_destructible_break_keyframes(
    frame_count: int = 20,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Object breaks apart — wobble then collapse."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    break_frame = int(0.3 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= break_frame:
            t = frame / break_frame if break_frame > 0 else 1.0
            wobble = 0.05 * intensity * math.sin(t * 8 * math.pi) * t
            keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, wobble))
            keyframes.append(Keyframe(ENV_ROOT, "scale", 0, frame, 1.0))
        else:
            collapse_t = (frame - break_frame) / (frame_count - break_frame) if frame_count > break_frame else 1.0
            scale = 1.0 - 0.8 * collapse_t * collapse_t
            drop = -0.5 * intensity * collapse_t * collapse_t
            keyframes.append(Keyframe(ENV_ROOT, "location", 2, frame, drop))
            keyframes.append(Keyframe(ENV_ROOT, "scale", 0, frame, max(0.1, scale)))
            keyframes.append(Keyframe(ENV_ROOT, "scale", 1, frame, max(0.1, scale)))
            keyframes.append(Keyframe(ENV_ROOT, "scale", 2, frame, max(0.1, scale)))

    return keyframes


# ---------------------------------------------------------------------------
# Fire / torch animations (looping)
# ---------------------------------------------------------------------------

def generate_fire_flicker_keyframes(
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Procedural fire flicker — scale/position jitter for flame objects."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Multi-frequency flicker for natural randomness
        flicker1 = math.sin(t * 7.3 * 2 * math.pi)
        flicker2 = math.sin(t * 11.7 * 2 * math.pi) * 0.5
        flicker3 = math.sin(t * 3.1 * 2 * math.pi) * 0.3

        # Scale Y (height) fluctuation
        y_scale = 1.0 + 0.15 * intensity * (flicker1 + flicker2)
        keyframes.append(Keyframe(ENV_ROOT, "scale", 1, frame, max(0.5, y_scale)))

        # Scale XZ (width) inverse fluctuation
        xz_scale = 1.0 - 0.05 * intensity * flicker1
        keyframes.append(Keyframe(ENV_ROOT, "scale", 0, frame, max(0.5, xz_scale)))
        keyframes.append(Keyframe(ENV_ROOT, "scale", 2, frame, max(0.5, xz_scale)))

        # Lateral sway
        sway = 0.02 * intensity * (flicker2 + flicker3)
        keyframes.append(Keyframe(ENV_ROOT, "location", 0, frame, sway))

    return keyframes


def generate_torch_sway_keyframes(
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Torch/sconce with wind-driven sway."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        sway = 0.03 * intensity * math.sin(t * 2 * math.pi * 1.3)
        sway2 = 0.01 * intensity * math.sin(t * 2 * math.pi * 2.7)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, sway + sway2))
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, sway * 0.5))

    return keyframes


# ---------------------------------------------------------------------------
# Water animations (looping)
# ---------------------------------------------------------------------------

def generate_water_wave_keyframes(
    frame_count: int = 60,
    amplitude: float = 0.1,
    wavelength: float = 1.0,
) -> list[Keyframe]:
    """Water surface wave — vertical oscillation with drift."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        wave = amplitude * math.sin(t * 2 * math.pi * wavelength)
        secondary = amplitude * 0.3 * math.sin(t * 2 * math.pi * wavelength * 2.3 + 0.7)
        keyframes.append(Keyframe(ENV_ROOT, "location", 2, frame, wave + secondary))
        # Subtle rotation for wave direction
        tilt = 0.02 * math.sin(t * 2 * math.pi * wavelength + math.pi / 4)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, tilt))

    return keyframes


# ---------------------------------------------------------------------------
# Flag / banner animations (looping)
# ---------------------------------------------------------------------------

def generate_flag_wind_keyframes(
    frame_count: int = 48,
    wind_strength: float = 1.0,
) -> list[Keyframe]:
    """Flag cloth simulation approximation — multi-bone wave."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    segments = 4  # FLAG_ROOT, flag.001, flag.002, flag.003

    for seg in range(segments):
        bone = ENV_ROOT if seg == 0 else f"flag.{seg:03d}"
        phase = seg * math.pi / 3
        amp = 0.1 * wind_strength * (1 + seg * 0.5)  # increases toward tip

        for frame in range(frame_count + 1):
            t = frame / frame_count
            wave = amp * math.sin(t * 2 * math.pi + phase)
            secondary = amp * 0.3 * math.sin(t * 2 * math.pi * 2.1 + phase)
            keyframes.append(Keyframe(bone, "rotation_euler", 0, frame, wave + secondary))

    return keyframes


# ---------------------------------------------------------------------------
# Chain / rope animations (looping)
# ---------------------------------------------------------------------------

def generate_chain_swing_keyframes(
    frame_count: int = 48,
    amplitude: float = 0.3,
) -> list[Keyframe]:
    """Pendulum chain swing with damping."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        swing = amplitude * math.sin(t * 2 * math.pi)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, swing))

    return keyframes


# ---------------------------------------------------------------------------
# Trap animations
# ---------------------------------------------------------------------------

def generate_trap_trigger_keyframes(
    frame_count: int = 12,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Trap triggers — fast snap with recoil."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    snap_frame = int(0.2 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= snap_frame:
            t = frame / snap_frame if snap_frame > 0 else 1.0
            rot = -0.8 * intensity * smoothstep(t)  # smooth snap
        else:
            settle_t = (frame - snap_frame) / (frame_count - snap_frame) if frame_count > snap_frame else 1.0
            rot = -0.8 * intensity * (1 - 0.1 * math.sin(settle_t * 3 * math.pi) * (1 - settle_t))
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, rot))

    return keyframes


# ---------------------------------------------------------------------------
# Interactable objects
# ---------------------------------------------------------------------------

def generate_chest_open_keyframes(
    frame_count: int = 30,
    angle: float = 110.0,
) -> list[Keyframe]:
    """Treasure chest lid opens — hinge rotation with slight bounce."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)
    open_end = int(0.7 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= open_end:
            t = frame / open_end if open_end > 0 else 1.0
            ease_t = smoothstep(t)
            rot = -angle_rad * ease_t
        else:
            settle_t = (frame - open_end) / (frame_count - open_end) if frame_count > open_end else 1.0
            bounce = 0.03 * angle_rad * math.sin(settle_t * 2 * math.pi) * (1 - settle_t)
            rot = -angle_rad + bounce
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, rot))

    return keyframes


def generate_lever_pull_keyframes(
    frame_count: int = 20,
    angle: float = 60.0,
) -> list[Keyframe]:
    """Lever pull — forward rotation with weight feel."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    angle_rad = math.radians(angle)

    for frame in range(frame_count + 1):
        t = frame / frame_count
        ease_t = smoothstep(t)
        rot = angle_rad * ease_t
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, rot))

    return keyframes


# ---------------------------------------------------------------------------
# Ambient props (looping)
# ---------------------------------------------------------------------------

def generate_candle_flicker_keyframes(
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Candle flame flicker — smaller scale than fire."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        flicker = math.sin(t * 9.7 * 2 * math.pi) * 0.5 + math.sin(t * 5.3 * 2 * math.pi) * 0.3
        y_scale = 1.0 + 0.1 * intensity * flicker
        keyframes.append(Keyframe(ENV_ROOT, "scale", 1, frame, max(0.6, y_scale)))
        sway = 0.01 * intensity * math.sin(t * 3.7 * 2 * math.pi)
        keyframes.append(Keyframe(ENV_ROOT, "location", 0, frame, sway))

    return keyframes


def generate_chandelier_sway_keyframes(
    frame_count: int = 72,
    amplitude: float = 0.05,
) -> list[Keyframe]:
    """Chandelier pendulum sway — slow, heavy."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        sway = amplitude * math.sin(t * 2 * math.pi * 0.5)
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 0, frame, sway))
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 2, frame, sway * 0.3))

    return keyframes


def generate_windmill_rotate_keyframes(
    frame_count: int = 120,
    speed: float = 1.0,
) -> list[Keyframe]:
    """Windmill blade continuous rotation."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        rot = t * 2 * math.pi * speed
        keyframes.append(Keyframe(ENV_ROOT, "rotation_euler", 1, frame, rot))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ENV_GENERATORS = {
    "door_open": lambda p: generate_door_open_keyframes(p["frame_count"], p.get("angle", 90), p.get("speed", 1.0)),
    "door_close": lambda p: generate_door_close_keyframes(p["frame_count"], p.get("angle", 90)),
    "door_slam": lambda p: generate_door_slam_keyframes(p["frame_count"], p.get("angle", 90)),
    "door_creak": lambda p: generate_door_creak_keyframes(p["frame_count"], p.get("angle", 45)),
    "gate_raise": lambda p: generate_gate_raise_keyframes(p["frame_count"], p.get("height", 3.0)),
    "gate_lower": lambda p: generate_gate_lower_keyframes(p["frame_count"], p.get("height", 3.0)),
    "drawbridge": lambda p: generate_drawbridge_keyframes(p["frame_count"], p.get("angle", 80)),
    "destructible_break": lambda p: generate_destructible_break_keyframes(p["frame_count"], p.get("intensity", 1.0)),
    "destructible_shatter": lambda p: generate_destructible_break_keyframes(p["frame_count"], p.get("intensity", 1.5)),
    "fire_flicker": lambda p: generate_fire_flicker_keyframes(p["frame_count"], p.get("intensity", 1.0)),
    "torch_sway": lambda p: generate_torch_sway_keyframes(p["frame_count"], p.get("intensity", 1.0)),
    "water_wave": lambda p: generate_water_wave_keyframes(p["frame_count"], p.get("amplitude", 0.1)),
    "water_ripple": lambda p: generate_water_wave_keyframes(p["frame_count"], p.get("amplitude", 0.03)),
    "waterfall": lambda p: generate_water_wave_keyframes(p["frame_count"], p.get("amplitude", 0.2)),
    "flag_wind": lambda p: generate_flag_wind_keyframes(p["frame_count"], p.get("wind_strength", 1.0)),
    "banner_wind": lambda p: generate_flag_wind_keyframes(p["frame_count"], p.get("wind_strength", 0.6)),
    "chain_swing": lambda p: generate_chain_swing_keyframes(p["frame_count"], p.get("amplitude", 0.3)),
    "rope_sway": lambda p: generate_chain_swing_keyframes(p["frame_count"], p.get("amplitude", 0.15)),
    "trap_trigger": lambda p: generate_trap_trigger_keyframes(p["frame_count"], p.get("intensity", 1.0)),
    "trap_reset": lambda p: generate_lever_pull_keyframes(p["frame_count"], p.get("angle", -60)),
    "trap_idle": lambda p: generate_chain_swing_keyframes(p["frame_count"], p.get("amplitude", 0.02)),
    "chest_open": lambda p: generate_chest_open_keyframes(p["frame_count"], p.get("angle", 110)),
    "lever_pull": lambda p: generate_lever_pull_keyframes(p["frame_count"], p.get("angle", 60)),
    "switch_toggle": lambda p: generate_lever_pull_keyframes(p["frame_count"], p.get("angle", 45)),
    "candle_flicker": lambda p: generate_candle_flicker_keyframes(p["frame_count"], p.get("intensity", 1.0)),
    "chandelier_sway": lambda p: generate_chandelier_sway_keyframes(p["frame_count"], p.get("amplitude", 0.05)),
    "windmill_rotate": lambda p: generate_windmill_rotate_keyframes(p["frame_count"], p.get("speed", 1.0)),
}


def generate_env_keyframes(params: dict) -> list[Keyframe]:
    """Dispatch to the appropriate environment animation generator."""
    env_type = params["env_type"]
    if env_type not in _ENV_GENERATORS:
        raise ValueError(f"Unknown env_type: {env_type!r}")
    return _ENV_GENERATORS[env_type](params)
