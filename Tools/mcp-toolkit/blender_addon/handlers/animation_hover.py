"""Floating creature hover animation system.

Provides hover animations for flying/floating monsters:
  - generate_hover_idle_keyframes: Vertical bob, lateral drift, body tilt
  - generate_hover_move_keyframes: Banking on turns, altitude transitions
  - generate_wing_flap_keyframes: Wing bone sync to vertical bob
  - generate_tentacle_float_keyframes: Sinusoidal tentacle wave

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALID_HOVER_TYPES: frozenset[str] = frozenset({
    "hover_idle", "hover_move", "wing_flap", "tentacle_float",
})


def validate_hover_params(params: dict) -> dict:
    """Validate hover animation parameters.

    Args:
        params: Dict with object_name, hover_type, bob_amplitude, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    hover_type = params.get("hover_type", "hover_idle")
    if hover_type not in VALID_HOVER_TYPES:
        raise ValueError(
            f"Invalid hover_type: {hover_type!r}. Valid: {sorted(VALID_HOVER_TYPES)}"
        )

    bob_amplitude = float(params.get("bob_amplitude", 0.05))
    if bob_amplitude < 0:
        raise ValueError(f"bob_amplitude must be >= 0, got {bob_amplitude}")

    bob_frequency = float(params.get("bob_frequency", 0.8))
    if bob_frequency <= 0:
        raise ValueError(f"bob_frequency must be > 0, got {bob_frequency}")

    bank_angle = float(params.get("bank_angle", 0.3))
    drift_amount = float(params.get("drift_amount", 0.02))

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    return {
        "object_name": object_name,
        "hover_type": hover_type,
        "bob_amplitude": bob_amplitude,
        "bob_frequency": bob_frequency,
        "bank_angle": bank_angle,
        "drift_amount": drift_amount,
        "frame_count": frame_count,
    }


# ---------------------------------------------------------------------------
# Hover idle
# ---------------------------------------------------------------------------

def generate_hover_idle_keyframes(
    bob_amplitude: float = 0.05,
    bob_frequency: float = 0.8,
    drift_amount: float = 0.02,
    frame_count: int = 48,
) -> list[Keyframe]:
    """Generate hovering idle animation.

    Vertical bob (sine wave), slight lateral drift, body tilt responding
    to vertical acceleration.

    Args:
        bob_amplitude: Height of vertical oscillation.
        bob_frequency: Oscillation speed multiplier.
        drift_amount: Lateral drift magnitude.
        frame_count: Total frames.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi * bob_frequency

        # Vertical bob on root/spine
        bob = bob_amplitude * math.sin(angle)
        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, bob))

        # Body tilt responding to vertical motion (derivative of bob)
        # When rising, tilt slightly back; when falling, tilt forward
        bob_derivative = bob_amplitude * bob_frequency * 2 * math.pi * math.cos(angle) / frame_count
        tilt = -bob_derivative * 2.0  # scale for visible effect
        tilt = max(-0.1, min(0.1, tilt))  # clamp
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, tilt))

        # Lateral drift (slower than bob, different phase)
        drift = drift_amount * math.sin(angle * 0.5 + math.pi / 3)
        keyframes.append(Keyframe("DEF-spine", "location", 0, frame, drift))

        # Subtle yaw oscillation
        yaw = 0.02 * math.sin(angle * 0.3 + math.pi / 2)
        keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, yaw))

    return keyframes


# ---------------------------------------------------------------------------
# Hover move (banking turns)
# ---------------------------------------------------------------------------

def generate_hover_move_keyframes(
    bank_angle: float = 0.3,
    bob_amplitude: float = 0.03,
    bob_frequency: float = 1.0,
    frame_count: int = 32,
) -> list[Keyframe]:
    """Generate hover movement with banking turns.

    Forward movement with roll toward turn direction and altitude
    transitions.

    Args:
        bank_angle: Maximum bank/roll angle during turns (radians).
        bob_amplitude: Reduced bob during movement.
        bob_frequency: Bob speed.
        frame_count: Total frames.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi * bob_frequency

        # Reduced vertical bob during movement
        bob = bob_amplitude * math.sin(angle)
        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, bob))

        # Forward lean during movement
        lean = 0.15
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, lean))

        # Banking: roll follows a turn arc (sine curve for smooth turn)
        bank = bank_angle * math.sin(t * 2 * math.pi)
        keyframes.append(Keyframe("DEF-spine", "rotation_euler", 0, frame, bank))

        # Yaw follows bank (coordinated turn)
        yaw = 0.2 * math.sin(t * 2 * math.pi)
        keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, yaw))

    return keyframes


# ---------------------------------------------------------------------------
# Wing flap (synced to bob)
# ---------------------------------------------------------------------------

def generate_wing_flap_keyframes(
    bob_frequency: float = 0.8,
    flap_amplitude: float = 0.7,
    frame_count: int = 48,
) -> list[Keyframe]:
    """Generate wing flap cycle synchronized to vertical bob.

    If armature has wing bones, sync flap cycle to bob. Wings extend
    on downstroke and fold on upstroke.

    Args:
        bob_frequency: Must match hover_idle bob_frequency.
        flap_amplitude: Wing rotation amplitude.
        frame_count: Total frames.

    Returns:
        List of Keyframe namedtuples for wing bones.
    """
    keyframes: list[Keyframe] = []

    wing_bones = [
        ("DEF-wing_upper.L", 1.0),
        ("DEF-wing_upper.R", 1.0),
        ("DEF-wing_fore.L", 0.5),
        ("DEF-wing_fore.R", 0.5),
        ("DEF-wing_tip.L", 0.25),
        ("DEF-wing_tip.R", 0.25),
    ]

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi * bob_frequency

        for bone_name, amp_scale in wing_bones:
            # Main flap: synced to bob (wings down = body up)
            flap = flap_amplitude * amp_scale * math.sin(angle)

            # Add secondary motion for fore/tip (delayed phase)
            if "fore" in bone_name:
                flap += 0.15 * amp_scale * math.sin(angle - 0.3)
            elif "tip" in bone_name:
                flap += 0.1 * amp_scale * math.sin(angle - 0.6)

            keyframes.append(Keyframe(bone_name, "rotation_euler", 0, frame, flap))

    return keyframes


# ---------------------------------------------------------------------------
# Tentacle float
# ---------------------------------------------------------------------------

def generate_tentacle_float_keyframes(
    tentacle_count: int = 4,
    wave_amplitude: float = 0.3,
    wave_frequency: float = 1.0,
    frame_count: int = 48,
) -> list[Keyframe]:
    """Generate sinusoidal tentacle wave for amorphous/tentacle creatures.

    Each tentacle segment gets increasing phase delay for traveling wave.
    Tentacles use bone naming: DEF-tentacle_N (N=1..tentacle_count)
    with segments .001, .002, .003.

    Args:
        tentacle_count: Number of tentacles.
        wave_amplitude: Wave magnitude.
        wave_frequency: Wave speed.
        frame_count: Total frames.

    Returns:
        List of Keyframe namedtuples.
    """
    keyframes: list[Keyframe] = []
    segments_per_tentacle = 3

    for tent_idx in range(1, tentacle_count + 1):
        # Each tentacle has a different base phase
        base_phase = (tent_idx - 1) * (2 * math.pi / tentacle_count)

        for seg_idx in range(segments_per_tentacle):
            if seg_idx == 0:
                bone_name = f"DEF-tentacle_{tent_idx}"
            else:
                bone_name = f"DEF-tentacle_{tent_idx}.{seg_idx:03d}"

            # Phase delay increases along the tentacle (traveling wave)
            seg_phase = base_phase + seg_idx * math.pi / 4

            # Amplitude increases toward tip
            seg_amp = wave_amplitude * (1.0 + seg_idx * 0.3)

            for frame in range(frame_count + 1):
                t = frame / frame_count
                angle = t * 2 * math.pi * wave_frequency + seg_phase

                # Primary wave on Y axis (lateral undulation)
                wave_y = seg_amp * math.sin(angle)
                keyframes.append(Keyframe(bone_name, "rotation_euler", 1, frame, wave_y))

                # Secondary wave on X axis (smaller, offset phase)
                wave_x = seg_amp * 0.4 * math.sin(angle + math.pi / 3)
                keyframes.append(Keyframe(bone_name, "rotation_euler", 0, frame, wave_x))

    # Body bob (similar to hover_idle)
    for frame in range(frame_count + 1):
        t = frame / frame_count
        bob = 0.03 * math.sin(t * 2 * math.pi * wave_frequency * 0.5)
        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, bob))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def generate_hover_keyframes(params: dict) -> list[Keyframe]:
    """Dispatch to the appropriate hover generator.

    Args:
        params: Validated params dict with hover_type, bob_amplitude, etc.

    Returns:
        List of Keyframe namedtuples.
    """
    hover_type = params["hover_type"]
    if hover_type == "hover_idle":
        return generate_hover_idle_keyframes(
            params["bob_amplitude"], params["bob_frequency"],
            params["drift_amount"], params["frame_count"],
        )
    elif hover_type == "hover_move":
        return generate_hover_move_keyframes(
            params["bank_angle"], params["bob_amplitude"],
            params["bob_frequency"], params["frame_count"],
        )
    elif hover_type == "wing_flap":
        return generate_wing_flap_keyframes(
            params["bob_frequency"], params.get("flap_amplitude", 0.7),
            params["frame_count"],
        )
    elif hover_type == "tentacle_float":
        return generate_tentacle_float_keyframes(
            params.get("tentacle_count", 4), params.get("wave_amplitude", 0.3),
            params["bob_frequency"], params["frame_count"],
        )
    else:
        raise ValueError(f"Unknown hover_type: {hover_type!r}")
