"""Brand-specific ability animation generators for VeilBreakers combat.

Generates procedural animations for all 10 brands' ability archetypes,
matching the 6-slot ability system: Basic Attack, Defend, Skill 1-3, Ultimate.

Each brand has a distinct combat feel:
  IRON:   Heavy, deliberate, protective (tank/shield)
  SAVAGE: Fast, aggressive, multi-hit (melee burst)
  SURGE:  Lightning-fast, phasing, electric (speed/ranged)
  VENOM:  Toxic, corrosive, DoT application (poison)
  DREAD:  Menacing, fear-inducing, crowd control
  LEECH:  Draining, parasitic, self-sustaining
  GRACE:  Flowing, elegant, supportive (heal/buff)
  MEND:   Protective barriers, cleansing, restoration
  RUIN:   Explosive, destructive, area damage
  VOID:   Chaotic, reality-warping, unpredictable

Also provides:
  - Status effect persistent animations (poison cloud, burn, freeze, etc.)
  - Multi-hit combo sequence generator
  - Creature-type-specific combat idles
  - Cast/channel animations with progress phases

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_BRANDS: frozenset[str] = frozenset({
    "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
    "LEECH", "GRACE", "MEND", "RUIN", "VOID",
})

VALID_ABILITY_SLOTS: frozenset[str] = frozenset({
    "basic_attack", "defend", "skill_1", "skill_2", "skill_3", "ultimate",
})

VALID_STATUS_EFFECTS: frozenset[str] = frozenset({
    "poison", "burn", "freeze", "bleed", "stun",
    "fear", "drain", "shield", "regen", "haste",
})

VALID_CREATURE_TYPES: frozenset[str] = frozenset({
    "humanoid", "quadruped", "spider", "serpent", "floating",
    "amorphous", "insectoid", "avian",
})


# ---------------------------------------------------------------------------
# Brand attack style profiles
# ---------------------------------------------------------------------------

_BRAND_ATTACK_PROFILES: dict[str, dict] = {
    "IRON": {
        "basic": {"wind_up": 0.35, "strike_speed": 0.7, "recovery": 0.9, "style": "heavy_swing"},
        "defend": {"raise_speed": 0.6, "hold_tension": 0.8, "style": "shield_wall"},
        "skill_archetype": "ground_slam",
        "ultimate_archetype": "fortification",
    },
    "SAVAGE": {
        "basic": {"wind_up": 0.15, "strike_speed": 1.3, "recovery": 0.5, "style": "claw_swipe"},
        "defend": {"raise_speed": 1.0, "hold_tension": 0.3, "style": "aggressive_dodge"},
        "skill_archetype": "multi_slash",
        "ultimate_archetype": "frenzy",
    },
    "SURGE": {
        "basic": {"wind_up": 0.1, "strike_speed": 1.5, "recovery": 0.4, "style": "lightning_jab"},
        "defend": {"raise_speed": 1.2, "hold_tension": 0.2, "style": "phase_dodge"},
        "skill_archetype": "chain_bolt",
        "ultimate_archetype": "tempest",
    },
    "VENOM": {
        "basic": {"wind_up": 0.25, "strike_speed": 0.8, "recovery": 1.0, "style": "toxic_strike"},
        "defend": {"raise_speed": 0.5, "hold_tension": 0.6, "style": "toxic_shroud"},
        "skill_archetype": "acid_spray",
        "ultimate_archetype": "plague_cloud",
    },
    "DREAD": {
        "basic": {"wind_up": 0.4, "strike_speed": 0.6, "recovery": 0.8, "style": "shadow_strike"},
        "defend": {"raise_speed": 0.3, "hold_tension": 1.0, "style": "fear_aura"},
        "skill_archetype": "psychic_blast",
        "ultimate_archetype": "nightmare",
    },
    "LEECH": {
        "basic": {"wind_up": 0.2, "strike_speed": 0.9, "recovery": 0.7, "style": "drain_touch"},
        "defend": {"raise_speed": 0.7, "hold_tension": 0.5, "style": "absorb_barrier"},
        "skill_archetype": "life_drain",
        "ultimate_archetype": "consume",
    },
    "GRACE": {
        "basic": {"wind_up": 0.2, "strike_speed": 1.0, "recovery": 0.6, "style": "elegant_strike"},
        "defend": {"raise_speed": 0.8, "hold_tension": 0.4, "style": "flowing_parry"},
        "skill_archetype": "healing_wave",
        "ultimate_archetype": "divine_blessing",
    },
    "MEND": {
        "basic": {"wind_up": 0.25, "strike_speed": 0.9, "recovery": 0.7, "style": "staff_swing"},
        "defend": {"raise_speed": 0.6, "hold_tension": 0.7, "style": "barrier_raise"},
        "skill_archetype": "shield_burst",
        "ultimate_archetype": "sanctuary",
    },
    "RUIN": {
        "basic": {"wind_up": 0.3, "strike_speed": 1.1, "recovery": 0.6, "style": "explosive_punch"},
        "defend": {"raise_speed": 0.4, "hold_tension": 0.5, "style": "counter_blast"},
        "skill_archetype": "detonation",
        "ultimate_archetype": "cataclysm",
    },
    "VOID": {
        "basic": {"wind_up": 0.2, "strike_speed": 1.0, "recovery": 0.8, "style": "void_rend"},
        "defend": {"raise_speed": 0.5, "hold_tension": 0.6, "style": "reality_fold"},
        "skill_archetype": "chaos_bolt",
        "ultimate_archetype": "reality_tear",
    },
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_ability_params(params: dict) -> dict:
    """Validate ability animation parameters.

    Args:
        params: Dict with object_name, brand, slot, frame_count, etc.

    Returns:
        Normalized dict.

    Raises:
        ValueError: On invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    brand = params.get("brand", "IRON").upper()
    if brand not in VALID_BRANDS:
        raise ValueError(f"Invalid brand: {brand!r}. Valid: {sorted(VALID_BRANDS)}")

    slot = params.get("slot", "basic_attack")
    if slot not in VALID_ABILITY_SLOTS:
        raise ValueError(f"Invalid slot: {slot!r}. Valid: {sorted(VALID_ABILITY_SLOTS)}")

    frame_count = int(params.get("frame_count", 30))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")

    creature_type = params.get("creature_type", "humanoid")
    if creature_type not in VALID_CREATURE_TYPES:
        raise ValueError(f"Invalid creature_type: {creature_type!r}.")

    return {
        "object_name": object_name,
        "brand": brand,
        "slot": slot,
        "frame_count": frame_count,
        "intensity": intensity,
        "creature_type": creature_type,
    }


def validate_status_effect_params(params: dict) -> dict:
    """Validate status effect animation parameters."""
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    effect = params.get("effect", "poison")
    if effect not in VALID_STATUS_EFFECTS:
        raise ValueError(f"Invalid effect: {effect!r}. Valid: {sorted(VALID_STATUS_EFFECTS)}")

    frame_count = int(params.get("frame_count", 48))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")

    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")

    return {
        "object_name": object_name,
        "effect": effect,
        "frame_count": frame_count,
        "intensity": intensity,
    }


# ---------------------------------------------------------------------------
# Brand basic attack generators
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease_in_out(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def generate_brand_basic_attack(
    brand: str = "IRON",
    frame_count: int = 24,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate brand-styled basic attack animation.

    Each brand has a distinct attack feel based on _BRAND_ATTACK_PROFILES.
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    profile = _BRAND_ATTACK_PROFILES.get(brand.upper(), _BRAND_ATTACK_PROFILES["IRON"])
    basic = profile["basic"]

    wind_up_pct = basic["wind_up"]
    strike_speed = basic["strike_speed"]

    antic_end = int(wind_up_pct * frame_count)
    strike_end = int((wind_up_pct + 0.3 / strike_speed) * frame_count)
    strike_end = min(strike_end, int(0.6 * frame_count))

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= antic_end:
            # Wind-up phase (brand-specific intensity)
            p = frame / antic_end if antic_end > 0 else 1.0
            p = _ease_in_out(p)
            arm_val = -0.7 * p * intensity
            spine_val = -0.1 * p * intensity
        elif frame <= strike_end:
            # Strike phase — p normalized 0-1 within phase
            # strike_speed already controls phase duration via strike_end calc
            p = (frame - antic_end) / (strike_end - antic_end) if strike_end > antic_end else 1.0
            arm_val = _lerp(-0.7, 1.2, p) * intensity
            spine_val = _lerp(-0.1, 0.2, p) * intensity
        else:
            # Recovery
            p = (frame - strike_end) / (frame_count - strike_end) if frame_count > strike_end else 1.0
            p = _ease_in_out(p)
            arm_val = _lerp(1.2, 0.0, p) * intensity
            spine_val = _lerp(0.2, 0.0, p) * intensity

        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_val))
        keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, arm_val * 0.5))
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spine_val))

        # Brand-specific flavor
        if brand.upper() == "SAVAGE":
            # Left arm follows for dual-claw
            left_delay = max(0, frame - 3)
            lt = left_delay / frame_count
            if lt <= wind_up_pct:
                left_val = -0.5 * (lt / wind_up_pct) * intensity
            elif lt <= 0.5:
                left_val = _lerp(-0.5, 0.9, (lt - wind_up_pct) / (0.5 - wind_up_pct)) * intensity
            else:
                left_val = _lerp(0.9, 0.0, (lt - 0.5) / 0.5) * intensity
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, left_val))

        elif brand.upper() == "SURGE":
            # Electric tremor during strike
            if antic_end < frame <= strike_end:
                tremor = 0.03 * math.sin(frame * 8) * intensity
                keyframes.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, tremor))

        elif brand.upper() in ("IRON", "RUIN"):
            # Both hands for heavy/explosive attacks
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_val * 0.8))

    return keyframes


# ---------------------------------------------------------------------------
# Brand defend generators
# ---------------------------------------------------------------------------

def generate_brand_defend(
    brand: str = "IRON",
    frame_count: int = 20,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate brand-styled defend/guard animation."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    profile = _BRAND_ATTACK_PROFILES.get(brand.upper(), _BRAND_ATTACK_PROFILES["IRON"])
    defend = profile["defend"]

    raise_end = int(0.3 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= raise_end:
            p = _ease_in_out(frame / raise_end if raise_end > 0 else 1.0)
            guard_val = p
        else:
            # Hold with subtle breathing
            hold_t = (frame - raise_end) / (frame_count - raise_end) if frame_count > raise_end else 0.0
            breath = 0.01 * math.sin(hold_t * 4 * math.pi) * defend["hold_tension"]
            guard_val = 1.0 + breath

        # Arms up in guard
        arm_raise = -0.8 * guard_val * intensity
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_raise))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_raise))
        keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.4 * guard_val * intensity))
        keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.4 * guard_val * intensity))

        # Crouch
        crouch = 0.12 * guard_val * intensity
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, crouch))
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.1 * guard_val * intensity))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.1 * guard_val * intensity))

    return keyframes


# ---------------------------------------------------------------------------
# Brand skill generators
# ---------------------------------------------------------------------------

def generate_brand_skill(
    brand: str = "IRON",
    skill_slot: int = 1,
    frame_count: int = 36,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate brand-specific skill animation.

    skill_slot 1-3 maps to increasingly powerful/dramatic animations.
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    profile = _BRAND_ATTACK_PROFILES.get(brand.upper(), _BRAND_ATTACK_PROFILES["IRON"])
    skill_slot = max(1, min(3, skill_slot))

    # Scale drama by skill slot (skill 3 is most dramatic)
    drama = 0.6 + 0.2 * skill_slot

    antic_pct = 0.25 + 0.05 * skill_slot  # longer wind-up for bigger skills
    antic_end = int(antic_pct * frame_count)
    active_end = int((antic_pct + 0.2) * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= antic_end:
            p = _ease_in_out(frame / antic_end if antic_end > 0 else 1.0)

            # Gathering energy pose
            arm_raise = -0.9 * drama * p * intensity
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_raise))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_raise))

            # Charge tremor (increases with skill slot)
            if p > 0.5:
                tremor_amp = 0.01 * skill_slot * (p - 0.5) * 2
                tremor = tremor_amp * math.sin(frame * 6) * intensity
                keyframes.append(Keyframe("DEF-hand.L", "rotation_euler", 0, frame, tremor))
                keyframes.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, -tremor))

            # Lean back
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.15 * drama * p * intensity))

        elif frame <= active_end:
            p = (frame - antic_end) / (active_end - antic_end) if active_end > antic_end else 1.0

            # Release energy
            thrust = _lerp(-0.9 * drama, 1.0 * drama, p) * intensity
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, thrust))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, thrust))

            # Forward lean on release
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                      _lerp(-0.15 * drama, 0.2 * drama, p) * intensity))
        else:
            p = (frame - active_end) / (frame_count - active_end) if frame_count > active_end else 1.0
            p = _ease_in_out(p)

            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      _lerp(1.0 * drama, 0.0, p) * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      _lerp(1.0 * drama, 0.0, p) * intensity))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                      _lerp(0.2 * drama, 0.0, p) * intensity))

    return keyframes


# ---------------------------------------------------------------------------
# Brand ultimate generators
# ---------------------------------------------------------------------------

def generate_brand_ultimate(
    brand: str = "IRON",
    frame_count: int = 60,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate brand-specific ultimate ability animation.

    Extended sequence (60+ frames): long charge → dramatic release → aftermath.
    Intensity clamped to 1.5 to prevent deformation beyond safe rotation limits.
    """
    frame_count = max(1, frame_count)
    intensity = min(intensity, 1.5)  # Clamp to prevent > 1.5 rad rotations
    keyframes: list[Keyframe] = []

    charge_end = int(0.5 * frame_count)
    release_end = int(0.65 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= charge_end:
            # Long dramatic charge
            p = frame / charge_end if charge_end > 0 else 1.0
            ease_p = p * p  # quadratic ease-in for building tension

            # Arms rise progressively
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      -1.3 * ease_p * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      -1.3 * ease_p * intensity))

            # Body arches back
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                      -0.25 * ease_p * intensity))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame,
                                      -0.15 * ease_p * intensity))

            # Increasing tremor
            tremor_freq = 4 + 12 * p
            tremor_amp = 0.03 * p * intensity
            tremor = tremor_amp * math.sin(frame * tremor_freq * 0.5)
            keyframes.append(Keyframe("DEF-hand.L", "rotation_euler", 0, frame, tremor))
            keyframes.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, -tremor))

            # Legs brace
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.15 * ease_p * intensity))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.15 * ease_p * intensity))

        elif frame <= release_end:
            # Explosive release
            p = (frame - charge_end) / (release_end - charge_end) if release_end > charge_end else 1.0

            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      _lerp(-1.3, 1.5, p) * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      _lerp(-1.3, 1.5, p) * intensity))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                      _lerp(-0.25, 0.35, p) * intensity))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame,
                                      _lerp(-0.15, 0.2, p) * intensity))

            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.15 * intensity))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.15 * intensity))

        else:
            # Aftermath / recovery
            p = (frame - release_end) / (frame_count - release_end) if frame_count > release_end else 1.0
            p = _ease_in_out(p)

            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      _lerp(1.5, 0.0, p) * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      _lerp(1.5, 0.0, p) * intensity))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame,
                                      _lerp(0.35, 0.0, p) * intensity))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame,
                                      _lerp(0.2, 0.0, p) * intensity))

            # Exhaustion dip
            exhaustion = 0.05 * math.sin(p * math.pi) * intensity
            keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.1 * (1 - p) + exhaustion))
            keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.1 * (1 - p) + exhaustion))

    return keyframes


# ---------------------------------------------------------------------------
# Status effect persistent animations (looping)
# ---------------------------------------------------------------------------

def generate_status_effect_keyframes(
    effect: str = "poison",
    frame_count: int = 48,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate looping status effect animation overlay.

    These are subtle persistent animations applied on top of the
    creature's base animation while a status effect is active.
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi

        if effect == "poison":
            # Sickly swaying, hunched posture
            sway = 0.04 * intensity * math.sin(angle * 1.5)
            hunch = 0.06 * intensity
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, hunch))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, sway))
            # Occasional shudder
            shudder = 0.02 * intensity * math.sin(angle * 4) * max(0, math.sin(angle * 0.5))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, shudder))

        elif effect == "burn":
            # Writhing, flinching from pain
            flinch = 0.05 * intensity * abs(math.sin(angle * 3))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, flinch))
            # Arms pull in defensively
            arm_guard = -0.15 * intensity * (0.5 + 0.5 * math.sin(angle * 2))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_guard))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_guard))

        elif effect == "freeze":
            # Shivering, stiffened posture
            shiver = 0.02 * intensity * math.sin(angle * 8)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, shiver))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame,
                                      -0.1 * intensity + shiver * 0.5))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame,
                                      0.1 * intensity - shiver * 0.5))
            # Hunched
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.05 * intensity))

        elif effect == "bleed":
            # Favoring wounded side, periodic stumble
            lean = 0.06 * intensity * (1.0 + 0.3 * math.sin(angle))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, lean))
            # Arm holding wound
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.3 * intensity))
            keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, 0.4 * intensity))

        elif effect == "stun":
            # Dazed wobbling
            wobble_x = 0.06 * intensity * math.sin(angle * 1.2)
            wobble_y = 0.04 * intensity * math.sin(angle * 0.8 + math.pi / 3)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, wobble_x))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, wobble_y))
            # Head lolling
            keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 0, frame,
                                      0.08 * intensity * math.sin(angle * 1.5)))

        elif effect == "fear":
            # Cowering, trembling
            cower = 0.1 * intensity * (0.7 + 0.3 * math.sin(angle * 2))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, cower))
            # Arms up defensively
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame,
                                      -0.5 * intensity * (0.8 + 0.2 * math.sin(angle * 3))))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame,
                                      -0.5 * intensity * (0.8 + 0.2 * math.sin(angle * 3))))
            # Trembling
            tremble = 0.015 * intensity * math.sin(angle * 7)
            keyframes.append(Keyframe("DEF-hand.L", "rotation_euler", 0, frame, tremble))
            keyframes.append(Keyframe("DEF-hand.R", "rotation_euler", 0, frame, -tremble))

        elif effect == "drain":
            # Life being drained out, weakening posture
            weakness = 0.08 * intensity * (0.5 + 0.5 * math.sin(angle * 0.5))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, weakness))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, weakness * 0.7))
            # Arms dropping
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.2 * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.2 * intensity))

        elif effect == "shield":
            # Empowered stance, subtle glow pulse
            pulse = 0.02 * intensity * math.sin(angle * 2)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.03 * intensity + pulse))
            # Confident chest out
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, -0.02 * intensity))

        elif effect == "regen":
            # Slow deep breathing, recovering
            breath = 0.03 * intensity * math.sin(angle)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, breath))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, breath * 0.7))

        elif effect == "haste":
            # Twitchy, ready to spring, micro-movements
            twitch = 0.015 * intensity * math.sin(angle * 5)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, twitch))
            shift = 0.01 * intensity * math.sin(angle * 3 + math.pi / 4)
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, shift))
            # Weight on balls of feet
            keyframes.append(Keyframe("DEF-foot.L", "rotation_euler", 0, frame, -0.05 * intensity))
            keyframes.append(Keyframe("DEF-foot.R", "rotation_euler", 0, frame, -0.05 * intensity))

    return keyframes


# ---------------------------------------------------------------------------
# Multi-hit combo generator
# ---------------------------------------------------------------------------

def generate_combo_keyframes(
    hit_count: int = 3,
    frame_count: int = 36,
    intensity: float = 1.0,
) -> list[Keyframe]:
    """Generate multi-hit combo animation sequence.

    Distributes hits evenly across the frame range with wind-up for
    first hit and brief pauses between subsequent hits.

    Args:
        hit_count: Number of hits in the combo (1-6).
        frame_count: Total frames.
        intensity: Attack power multiplier.

    Returns:
        List of Keyframe namedtuples.
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    hit_count = max(1, min(6, hit_count))
    frames_per_hit = frame_count // hit_count

    for hit_idx in range(hit_count):
        hit_start = hit_idx * frames_per_hit
        hit_end = hit_start + frames_per_hit
        # Alternate sides for visual variety
        is_right = hit_idx % 2 == 0
        arm_bone = "DEF-upper_arm.R" if is_right else "DEF-upper_arm.L"
        forearm_bone = "DEF-forearm.R" if is_right else "DEF-forearm.L"
        twist_dir = 1.0 if is_right else -1.0

        for frame in range(hit_start, min(hit_end + 1, frame_count + 1)):
            local_t = (frame - hit_start) / frames_per_hit if frames_per_hit > 0 else 1.0

            # Each hit: 30% wind-up, 20% strike, 50% recovery
            if local_t <= 0.3:
                p = local_t / 0.3
                arm_val = -0.6 * p * intensity
                spine_twist = -0.1 * twist_dir * p * intensity
            elif local_t <= 0.5:
                p = (local_t - 0.3) / 0.2
                arm_val = _lerp(-0.6, 1.0, p) * intensity
                spine_twist = _lerp(-0.1, 0.15, p) * twist_dir * intensity
            else:
                p = (local_t - 0.5) / 0.5
                p = _ease_in_out(p)
                arm_val = _lerp(1.0, 0.0, p) * intensity
                spine_twist = _lerp(0.15, 0.0, p) * twist_dir * intensity

            keyframes.append(Keyframe(arm_bone, "rotation_euler", 0, frame, arm_val))
            keyframes.append(Keyframe(forearm_bone, "rotation_euler", 0, frame, arm_val * 0.4))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, spine_twist))

    return keyframes


# ---------------------------------------------------------------------------
# Creature-type combat idle generators
# ---------------------------------------------------------------------------

def generate_creature_combat_idle(
    creature_type: str = "humanoid",
    brand: str = "IRON",
    frame_count: int = 48,
) -> list[Keyframe]:
    """Generate creature-type-specific combat idle stance.

    Adapts the idle animation to the creature's body type.
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi

        if creature_type == "spider":
            # Low body, legs spread, subtle body pulse
            for i in range(1, 5):
                for side in [".L", ".R"]:
                    bone = f"DEF-leg_{i}{side}"
                    pulse = 0.02 * math.sin(angle + i * 0.3)
                    keyframes.append(Keyframe(bone, "rotation_euler", 2, frame, 0.15 + pulse))
            # Body bob
            keyframes.append(Keyframe("DEF-spine", "location", 2, frame,
                                      0.01 * math.sin(angle * 0.8)))

        elif creature_type == "serpent":
            # Continuous S-curve undulation
            for i, suffix in enumerate(["", ".001", ".002", ".003", ".004"]):
                bone = f"DEF-spine{suffix}"
                phase = i * math.pi / 3
                keyframes.append(Keyframe(bone, "rotation_euler", 1, frame,
                                          0.08 * math.sin(angle + phase)))

        elif creature_type == "floating":
            # Hover bob with slight rotation
            bob = 0.04 * math.sin(angle * 0.7)
            keyframes.append(Keyframe("DEF-spine", "location", 2, frame, bob))
            drift = 0.015 * math.sin(angle * 0.3)
            keyframes.append(Keyframe("DEF-spine", "location", 0, frame, drift))
            yaw = 0.03 * math.sin(angle * 0.2)
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, yaw))

        elif creature_type == "quadruped":
            # Weight shifting, breathing
            breath = 0.015 * math.sin(angle)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, breath))
            # Subtle weight shift
            shift = 0.01 * math.sin(angle * 0.5)
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, shift))
            # Tail idle sway
            keyframes.append(Keyframe("DEF-tail", "rotation_euler", 1, frame,
                                      0.05 * math.sin(angle * 0.6)))

        elif creature_type == "amorphous":
            # Pulsating, shifting mass
            pulse = 0.03 * math.sin(angle)
            for bone in ["DEF-spine", "DEF-spine.001", "DEF-spine.002"]:
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + pulse))
                keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 - pulse * 0.5))
                keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 + pulse))

        else:
            # Default humanoid combat idle with brand flavor
            breath = 0.015 * math.sin(angle)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, breath))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, breath * 0.7))
            # Subtle weight shift
            shift = 0.008 * math.sin(angle * 0.5 + math.pi / 4)
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, shift))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def generate_ability_keyframes(params: dict) -> list[Keyframe]:
    """Dispatch to the appropriate ability animation generator.

    Args:
        params: Validated params dict with brand, slot, frame_count, etc.

    Returns:
        List of Keyframe namedtuples.
    """
    slot = params["slot"]
    brand = params["brand"]
    fc = params["frame_count"]
    intensity = params.get("intensity", 1.0)

    if slot == "basic_attack":
        return generate_brand_basic_attack(brand, fc, intensity)
    elif slot == "defend":
        return generate_brand_defend(brand, fc, intensity)
    elif slot in ("skill_1", "skill_2", "skill_3"):
        skill_num = int(slot.split("_")[1])
        return generate_brand_skill(brand, skill_num, fc, intensity)
    elif slot == "ultimate":
        return generate_brand_ultimate(brand, fc, intensity)
    else:
        raise ValueError(f"Unknown slot: {slot!r}")
