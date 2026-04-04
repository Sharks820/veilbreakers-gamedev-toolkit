"""Monster-specific animation generators for VeilBreakers creatures.

Covers specialized animations that generic attack/ability generators can't produce:
  - reassemble: Bones/parts flying back together (Skitter-Teeth)
  - burrow: Underground entry/exit (serpents, arachnids)
  - spawn_broodling: Egg-lay/spawn sequence (Broodmother)
  - phase_shift: Teleport/blink flicker (Crackling, Flicker)
  - bloat_inflate: Body inflation/expansion (Gluttony Polyp)
  - regurgitate: Expulsion/vomit attack (Gluttony Polyp)
  - entangle: Vine/tentacle wrap around target (Grimthorn)
  - boss_phase_transition: Multi-phase boss form change (The Congregation)
  - gnaw_loop: Continuous chewing/gnawing (Mawling)
  - shadow_embrace: Shadow expansion/drain (Bloodshade)
  - chorus: Multi-body vocalization (The Congregation)
  - plant_growth: Vine/thorn barrier formation (Grimthorn)

Also provides animation_id_to_generator mapping for the game's 138 skill animation IDs.

Pure-logic module (NO bpy imports). Returns Keyframe data.
"""

from __future__ import annotations

import math

from .animation_gaits import Keyframe
from ._shared_utils import smoothstep


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MONSTER_ANIMS: frozenset[str] = frozenset({
    "reassemble", "burrow_enter", "burrow_exit",
    "spawn_broodling", "phase_shift", "bloat_inflate",
    "regurgitate", "entangle", "boss_phase_transition",
    "gnaw_loop", "shadow_embrace", "chorus",
    "plant_growth", "bone_wall", "parasitic_injection",
    "devour", "mimic_copy",
})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_monster_anim_params(params: dict) -> dict:
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    anim_type = params.get("anim_type", "reassemble")
    if anim_type not in VALID_MONSTER_ANIMS:
        raise ValueError(f"Invalid anim_type: {anim_type!r}. Valid: {sorted(VALID_MONSTER_ANIMS)}")
    frame_count = int(params.get("frame_count", 30))
    if frame_count < 4:
        raise ValueError(f"frame_count must be >= 4, got {frame_count}")
    intensity = float(params.get("intensity", 1.0))
    if intensity <= 0:
        raise ValueError(f"intensity must be > 0, got {intensity}")
    return {"object_name": object_name, "anim_type": anim_type,
            "frame_count": frame_count, "intensity": intensity}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_reassemble_keyframes(frame_count: int = 36, intensity: float = 1.0) -> list[Keyframe]:
    """Bones/parts fly back together — scatter then converge to rest pose.

    Used by Skitter-Teeth (ribcage on finger-legs reassembling from bone pieces).
    """
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    converge_start = int(0.3 * frame_count)

    bones = ["DEF-spine", "DEF-spine.001", "DEF-spine.002",
             "DEF-upper_arm.L", "DEF-upper_arm.R",
             "DEF-thigh.L", "DEF-thigh.R"]

    for i, bone in enumerate(bones):
        scatter_dir = 1.0 if i % 2 == 0 else -1.0
        scatter_height = 0.3 * intensity * (1 + i * 0.15)

        for frame in range(frame_count + 1):
            if frame <= converge_start:
                # Scattered state — parts floating apart
                t = frame / converge_start if converge_start > 0 else 1.0
                st = smoothstep(t)
                loc_x = scatter_dir * 0.2 * intensity * math.sin(i * 1.3) * (1 - st * 0.3)
                loc_z = scatter_height * (1 - st * 0.2)
                rot = 0.5 * intensity * scatter_dir * math.sin(t * 4 * math.pi) * (1 - st * 0.5)
            else:
                # Converge to rest pose
                conv_t = (frame - converge_start) / (frame_count - converge_start) if frame_count > converge_start else 1.0
                ease = smoothstep(conv_t)
                loc_x = scatter_dir * 0.2 * intensity * math.sin(i * 1.3) * (1 - ease)
                loc_z = scatter_height * (1 - ease)
                rot = 0.3 * intensity * scatter_dir * (1 - ease)

            keyframes.append(Keyframe(bone, "location", 0, frame, loc_x))
            keyframes.append(Keyframe(bone, "location", 2, frame, loc_z))
            keyframes.append(Keyframe(bone, "rotation_euler", 0, frame, rot))

    return keyframes


def generate_burrow_enter_keyframes(frame_count: int = 24, intensity: float = 1.0) -> list[Keyframe]:
    """Creature dives underground — body drops, limbs fold, scale shrinks to zero."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        ease = t * t  # accelerating dive

        # Sink into ground
        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, -1.5 * ease * intensity))
        # Curl inward
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.6 * ease * intensity))
        # Limbs tuck
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, 0.8 * ease * intensity))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, 0.8 * ease * intensity))
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.6 * ease * intensity))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.6 * ease * intensity))
        # Scale down
        scale = max(0.01, 1.0 - 0.95 * ease)
        keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, scale))

    return keyframes


def generate_burrow_exit_keyframes(frame_count: int = 20, intensity: float = 1.0) -> list[Keyframe]:
    """Creature bursts from underground — reverse of burrow enter with explosive pop."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    pop_frame = int(0.3 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= pop_frame:
            t = frame / pop_frame if pop_frame > 0 else 1.0
            # Explosive emergence
            z = -1.0 * intensity * (1 - t * t * t)
            scale = 0.01 + 0.99 * t * t
        else:
            settle_t = (frame - pop_frame) / (frame_count - pop_frame) if frame_count > pop_frame else 1.0
            z = 0.2 * intensity * math.sin(settle_t * 2 * math.pi) * (1 - settle_t)
            scale = 1.0

        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, z))
        keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, scale))
        # Arms spread on emergence
        arm_spread = max(0, -0.8 * intensity * (1 - (frame / frame_count)))
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_spread))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, arm_spread))

    return keyframes


def generate_spawn_broodling_keyframes(frame_count: int = 36, intensity: float = 1.0) -> list[Keyframe]:
    """Egg-laying/spawn sequence — body contracts, pushes, releases."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    push_start = int(0.4 * frame_count)
    release = int(0.65 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= push_start:
            # Gathering/contracting
            contract = frame / push_start if push_start > 0 else 1.0
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * contract * intensity))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, 1.0 + 0.15 * contract * intensity))
        elif frame <= release:
            # Pushing
            push_t = (frame - push_start) / (release - push_start) if release > push_start else 1.0
            strain = 0.1 * intensity * math.sin(push_t * 6 * math.pi) * (1 - push_t * 0.5)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * intensity + strain))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, 1.0 + 0.15 * intensity))
        else:
            # Release and recover
            recover_t = (frame - release) / (frame_count - release) if frame_count > release else 1.0
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.3 * (1 - recover_t) * intensity))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, 1.0 + 0.15 * (1 - recover_t) * intensity))

        # Legs brace throughout
        keyframes.append(Keyframe("DEF-thigh.L", "rotation_euler", 0, frame, 0.2 * intensity))
        keyframes.append(Keyframe("DEF-thigh.R", "rotation_euler", 0, frame, 0.2 * intensity))

    return keyframes


def generate_phase_shift_keyframes(frame_count: int = 16, intensity: float = 1.0) -> list[Keyframe]:
    """Teleport/blink — rapid scale-to-zero, reappear at offset with flash."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    vanish_end = int(0.3 * frame_count)
    appear_start = int(0.6 * frame_count)

    for frame in range(frame_count + 1):
        if frame <= vanish_end:
            t = frame / vanish_end if vanish_end > 0 else 1.0
            scale = max(0.01, 1.0 - smoothstep(t))
            flicker = 0.1 * math.sin(frame * 15) * (1 - t)
        elif frame <= appear_start:
            # Invisible/between phase
            scale = 0.01
            flicker = 0.0
        else:
            t = (frame - appear_start) / (frame_count - appear_start) if frame_count > appear_start else 1.0
            scale = 0.01 + 0.99 * smoothstep(t)
            flicker = 0.05 * math.sin(frame * 10) * (1 - t)

        keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, scale))
        keyframes.append(Keyframe("DEF-spine", "location", 0, frame, flicker))

    return keyframes


def generate_bloat_inflate_keyframes(frame_count: int = 30, intensity: float = 1.0) -> list[Keyframe]:
    """Body inflation — progressive scale increase with wobble."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        inflate = 1.0 + 0.5 * t * intensity
        wobble = 0.03 * intensity * math.sin(t * 8 * math.pi) * t

        for bone in ["DEF-spine", "DEF-spine.001", "DEF-spine.002"]:
            keyframes.append(Keyframe(bone, "scale", 0, frame, inflate + wobble))
            keyframes.append(Keyframe(bone, "scale", 1, frame, inflate - wobble * 0.5))
            keyframes.append(Keyframe(bone, "scale", 2, frame, inflate + wobble))

    return keyframes


def generate_regurgitate_keyframes(
    frame_count: int = 24,
    intensity: float = 1.0,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Expulsion/vomit attack — heave forward, open jaw, project contents."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    heave_end = int(0.4 * frame_count)
    _has_jaw = bone_names is None or "DEF-jaw" in bone_names

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= heave_end:
            heave = frame / heave_end if heave_end > 0 else 1.0
            # Body curls forward
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.5 * heave * intensity))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, 0.4 * heave * intensity))
            # Jaw opens (only on creatures with a jaw bone)
            if _has_jaw:
                keyframes.append(Keyframe("DEF-jaw", "rotation_euler", 0, frame, 0.6 * heave * intensity))
        else:
            recover_t = (frame - heave_end) / (frame_count - heave_end) if frame_count > heave_end else 1.0
            # Snap back with diminishing heaves
            recoil = 0.5 * (1 - recover_t) * intensity
            shudder = 0.1 * math.sin(recover_t * 4 * math.pi) * (1 - recover_t) * intensity
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, recoil + shudder))
            keyframes.append(Keyframe("DEF-spine.002", "rotation_euler", 0, frame, recoil * 0.8))
            if _has_jaw:
                keyframes.append(Keyframe("DEF-jaw", "rotation_euler", 0, frame, 0.3 * (1 - recover_t) * intensity))

    return keyframes


def generate_entangle_keyframes(frame_count: int = 30, intensity: float = 1.0) -> list[Keyframe]:
    """Vine/tentacle wrap — arms extend and curl around target position."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Arms reach out then curl
        if t <= 0.4:
            reach = t / 0.4
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, -1.0 * reach * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -1.0 * reach * intensity))
            keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, -0.3 * reach * intensity))
            keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, -0.3 * reach * intensity))
        elif t <= 0.7:
            curl_t = (t - 0.4) / 0.3
            # Arms curl inward (entangling)
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, (-1.0 + 0.5 * curl_t) * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (-1.0 + 0.5 * curl_t) * intensity))
            keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, (-0.3 - 0.5 * curl_t) * intensity))
            keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, (-0.3 - 0.5 * curl_t) * intensity))
        else:
            hold_t = (t - 0.7) / 0.3
            # Hold with constricting pulse
            pulse = 0.05 * math.sin(hold_t * 6 * math.pi) * intensity
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, (-0.5 + pulse) * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, (-0.5 + pulse) * intensity))
            keyframes.append(Keyframe("DEF-forearm.L", "rotation_euler", 0, frame, (-0.8 + pulse) * intensity))
            keyframes.append(Keyframe("DEF-forearm.R", "rotation_euler", 0, frame, (-0.8 + pulse) * intensity))

        # Body leans forward
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, 0.15 * min(1.0, t * 2) * intensity))

    return keyframes


def generate_boss_phase_transition_keyframes(frame_count: int = 60, intensity: float = 1.0) -> list[Keyframe]:
    """Multi-phase boss transformation — convulse, reshape, emerge stronger."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    convulse_end = int(0.4 * frame_count)
    reshape_end = int(0.7 * frame_count)

    for frame in range(frame_count + 1):
        t = frame / frame_count

        if frame <= convulse_end:
            # Violent convulsions
            conv_t = frame / convulse_end if convulse_end > 0 else 1.0
            spasm = 0.3 * intensity * math.sin(conv_t * 12 * math.pi) * conv_t
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, spasm))
            keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, spasm * 0.7))
            # Scale pulses
            pulse_scale = 1.0 + 0.1 * intensity * abs(math.sin(conv_t * 8 * math.pi))
            keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, pulse_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, pulse_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, pulse_scale))

        elif frame <= reshape_end:
            # Reshape — body expands, limbs reconfigure
            reshape_t = (frame - convulse_end) / (reshape_end - convulse_end) if reshape_end > convulse_end else 1.0
            new_scale = 1.0 + 0.3 * reshape_t * intensity
            keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, new_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, new_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, new_scale))
            # Arms spread wide
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.8 * reshape_t * intensity))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.8 * reshape_t * intensity))
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.2 * reshape_t * intensity))

        else:
            # Emerge in new form — settle into power pose
            emerge_t = (frame - reshape_end) / (frame_count - reshape_end) if frame_count > reshape_end else 1.0
            ease = emerge_t * emerge_t * (3 - 2 * emerge_t)
            final_scale = 1.3 * intensity
            keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, final_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, final_scale))
            keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, final_scale))
            keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.5 * intensity * (1 - 0.3 * ease)))
            keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.5 * intensity * (1 - 0.3 * ease)))
            # Subtle power tremor
            tremor = 0.015 * intensity * math.sin(emerge_t * 10 * math.pi) * (1 - ease)
            keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, -0.1 * intensity + tremor))

    return keyframes


def generate_gnaw_loop_keyframes(
    frame_count: int = 24,
    intensity: float = 1.0,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Continuous chewing/gnawing loop — jaw oscillation with head bob."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    _has_jaw = bone_names is None or "DEF-jaw" in bone_names

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi

        # Jaw rapid open/close (only on creatures with a jaw bone)
        if _has_jaw:
            jaw = 0.4 * intensity * abs(math.sin(angle * 3))
            keyframes.append(Keyframe("DEF-jaw", "rotation_euler", 0, frame, jaw))
        # Head bobs with chewing
        head_bob = 0.05 * intensity * math.sin(angle * 3 + math.pi / 4)
        keyframes.append(Keyframe("DEF-spine.004", "rotation_euler", 0, frame, head_bob))
        # Slight body lean
        lean = 0.02 * intensity * math.sin(angle)
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 0, frame, lean))

    return keyframes


def generate_shadow_embrace_keyframes(frame_count: int = 36, intensity: float = 1.0) -> list[Keyframe]:
    """Shadow expansion and drain — body spreads, tendrils reach out."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count

        # Body expands like a shadow spreading
        if t <= 0.3:
            spread = t / 0.3
            for bone in ["DEF-spine", "DEF-spine.001"]:
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + 0.4 * spread * intensity))
                keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 + 0.4 * spread * intensity))
                keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 - 0.1 * spread * intensity))
        elif t <= 0.7:
            # Hold expanded with pulsing drain
            drain_t = (t - 0.3) / 0.4
            pulse = 0.05 * intensity * math.sin(drain_t * 6 * math.pi)
            for bone in ["DEF-spine", "DEF-spine.001"]:
                keyframes.append(Keyframe(bone, "scale", 0, frame, 1.0 + 0.4 * intensity + pulse))
                keyframes.append(Keyframe(bone, "scale", 2, frame, 1.0 + 0.4 * intensity + pulse))
                keyframes.append(Keyframe(bone, "scale", 1, frame, 1.0 - 0.1 * intensity))
        else:
            # Retract
            retract_t = (t - 0.7) / 0.3
            ease = retract_t * retract_t
            for bone in ["DEF-spine", "DEF-spine.001"]:
                val = (1.0 + 0.4 * intensity) * (1 - ease) + ease
                keyframes.append(Keyframe(bone, "scale", 0, frame, val))
                keyframes.append(Keyframe(bone, "scale", 2, frame, val))
                keyframes.append(Keyframe(bone, "scale", 1, frame, (1.0 - 0.1 * intensity) + 0.1 * intensity * ease))

        # Arms reach outward
        arm_reach = min(1.0, t * 2) * intensity if t <= 0.7 else (1 - (t - 0.7) / 0.3) * intensity
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 1, frame, -0.6 * arm_reach))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 1, frame, 0.6 * arm_reach))

    return keyframes


def generate_plant_growth_keyframes(frame_count: int = 36, intensity: float = 1.0) -> list[Keyframe]:
    """Vine/thorn barrier growing from ground — scale up with twisting motion."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []

    for frame in range(frame_count + 1):
        t = frame / frame_count
        # Grow from ground (Y scale leads, then X/Z fill out)
        y_growth = min(1.0, t * 1.5)  # reaches full height at 67%
        xz_growth = min(1.0, max(0, t * 2 - 0.5))  # starts filling at 25%

        keyframes.append(Keyframe("DEF-spine", "scale", 1, frame, max(0.01, y_growth * intensity)))
        keyframes.append(Keyframe("DEF-spine", "scale", 0, frame, max(0.1, xz_growth * intensity)))
        keyframes.append(Keyframe("DEF-spine", "scale", 2, frame, max(0.1, xz_growth * intensity)))

        # Twisting as it grows
        twist = 0.3 * t * intensity * math.sin(t * 4 * math.pi)
        keyframes.append(Keyframe("DEF-spine", "rotation_euler", 1, frame, twist))
        keyframes.append(Keyframe("DEF-spine.001", "rotation_euler", 1, frame, twist * 1.2))

        # Rise from ground
        keyframes.append(Keyframe("DEF-spine", "location", 2, frame, -1.0 * (1 - y_growth) * intensity))

    return keyframes


def generate_chorus_keyframes(
    frame_count: int = 48,
    intensity: float = 1.0,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Multi-body vocalization — spine segments ripple, jaw pulses, arms sway."""
    frame_count = max(1, frame_count)
    keyframes: list[Keyframe] = []
    _has_jaw = bone_names is None or "DEF-jaw" in bone_names

    for frame in range(frame_count + 1):
        t = frame / frame_count
        angle = t * 2 * math.pi

        # Multiple spine segments ripple (simulating multiple mouths)
        for i, suffix in enumerate(["", ".001", ".002", ".003"]):
            bone = f"DEF-spine{suffix}"
            phase = i * math.pi / 3
            ripple = 0.06 * intensity * math.sin(angle * 3 + phase)
            keyframes.append(Keyframe(bone, "rotation_euler", 0, frame, ripple))

        # Jaw pulse (rapid open/close like chanting; only on creatures with a jaw bone)
        if _has_jaw:
            jaw = 0.3 * intensity * abs(math.sin(angle * 4))
            keyframes.append(Keyframe("DEF-jaw", "rotation_euler", 0, frame, jaw))

        # Arms sway in ritual pattern
        arm_sway = 0.2 * intensity * math.sin(angle * 2)
        keyframes.append(Keyframe("DEF-upper_arm.L", "rotation_euler", 0, frame, arm_sway))
        keyframes.append(Keyframe("DEF-upper_arm.R", "rotation_euler", 0, frame, -arm_sway))

    return keyframes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_MONSTER_GENERATORS = {
    "reassemble": lambda p: generate_reassemble_keyframes(p["frame_count"], p["intensity"]),
    "burrow_enter": lambda p: generate_burrow_enter_keyframes(p["frame_count"], p["intensity"]),
    "burrow_exit": lambda p: generate_burrow_exit_keyframes(p["frame_count"], p["intensity"]),
    "spawn_broodling": lambda p: generate_spawn_broodling_keyframes(p["frame_count"], p["intensity"]),
    "phase_shift": lambda p: generate_phase_shift_keyframes(p["frame_count"], p["intensity"]),
    "bloat_inflate": lambda p: generate_bloat_inflate_keyframes(p["frame_count"], p["intensity"]),
    "regurgitate": lambda p: generate_regurgitate_keyframes(p["frame_count"], p["intensity"], p.get("bone_names")),
    "entangle": lambda p: generate_entangle_keyframes(p["frame_count"], p["intensity"]),
    "boss_phase_transition": lambda p: generate_boss_phase_transition_keyframes(p["frame_count"], p["intensity"]),
    "gnaw_loop": lambda p: generate_gnaw_loop_keyframes(p["frame_count"], p["intensity"], p.get("bone_names")),
    "shadow_embrace": lambda p: generate_shadow_embrace_keyframes(p["frame_count"], p["intensity"]),
    "chorus": lambda p: generate_chorus_keyframes(p["frame_count"], p["intensity"], p.get("bone_names")),
    "plant_growth": lambda p: generate_plant_growth_keyframes(p["frame_count"], p["intensity"]),
    "bone_wall": lambda p: generate_plant_growth_keyframes(p["frame_count"], p["intensity"]),
    "parasitic_injection": lambda p: generate_entangle_keyframes(p["frame_count"], p["intensity"]),
    "devour": lambda p: generate_gnaw_loop_keyframes(p["frame_count"], p["intensity"]),
    "mimic_copy": lambda p: generate_phase_shift_keyframes(p["frame_count"], p["intensity"]),
}


def generate_monster_anim_keyframes(
    params: dict,
    bone_names: list[str] | None = None,
) -> list[Keyframe]:
    """Dispatch to the appropriate monster animation generator.

    Args:
        params: Validated params dict with anim_type, frame_count, intensity.
        bone_names: If provided, filter output keyframes to only include bones
            present in this list. Use to skip biped bones on non-biped creatures
            (e.g. DEF-thigh on a serpent). (RIG-003)

    Returns:
        List of Keyframe namedtuples.
    """
    anim_type = params["anim_type"]
    if anim_type not in _MONSTER_GENERATORS:
        raise ValueError(f"Unknown anim_type: {anim_type!r}")
    keyframes = _MONSTER_GENERATORS[anim_type](params)
    if bone_names is not None:
        bone_filter = set(bone_names)
        keyframes = [kf for kf in keyframes if kf.bone_name in bone_filter]
    return keyframes
