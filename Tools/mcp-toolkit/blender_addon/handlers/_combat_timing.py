"""Combat timing system for FromSoft-style animation feel.

Pure-logic module (NO bpy imports). Provides:
- COMBAT_TIMING_PRESETS: Frame timing for 7 attack/movement types
- configure_combat_timing: Configure timing with fps scaling + custom overrides
- generate_animation_events: Produce event lists (hit, VFX, sound, footstep, etc.)
- refine_root_motion: Smooth Y-axis drift and eliminate foot sliding
- generate_combat_animation_data: Combine timing + events + root motion into spec

Each attack type encodes the FromSoft combat philosophy:
  anticipation -> active -> recovery
with clear hit, VFX, and sound frames for game feel precision.

Fulfils ANIM3-01, ANIM3-02, ANIM3-05 requirements.
"""

from __future__ import annotations

import copy
import math
from typing import Any


# ---------------------------------------------------------------------------
# ANIM3-01: Combat timing presets (at 30fps reference)
# ---------------------------------------------------------------------------

COMBAT_TIMING_PRESETS: dict[str, dict[str, Any]] = {
    "light_attack": {
        "anticipation": 6,
        "active": 3,
        "recovery": 8,
        "total": 17,
        "hit_frame": 7,       # frame 6 + 1 into active
        "vfx_frame": 6,       # VFX spawns at start of active
        "sound_frame": 5,     # whoosh starts end of anticipation
        "camera_shake_frame": 7,
        "hitstop_frames": 2,
    },
    "heavy_attack": {
        "anticipation": 12,
        "active": 4,
        "recovery": 15,
        "total": 31,
        "hit_frame": 14,      # frame 12 + 2 into active
        "vfx_frame": 12,      # VFX at start of active
        "sound_frame": 10,    # wind-up sound
        "camera_shake_frame": 14,
        "hitstop_frames": 4,
    },
    "charged_attack": {
        "anticipation": 20,
        "active": 5,
        "recovery": 12,
        "total": 37,
        "hit_frame": 22,      # frame 20 + 2 into active
        "vfx_frame": 15,      # charge VFX starts during anticipation
        "sound_frame": 0,     # charge sound from start
        "camera_shake_frame": 22,
        "hitstop_frames": 6,
    },
    "combo_finisher": {
        "anticipation": 8,
        "active": 6,
        "recovery": 18,
        "total": 32,
        "hit_frame": 10,      # frame 8 + 2 into active
        "vfx_frame": 8,       # big VFX at active start
        "sound_frame": 6,     # anticipation sound
        "camera_shake_frame": 10,
        "hitstop_frames": 5,
    },
    "dodge_roll": {
        "anticipation": 3,
        "active": 8,
        "recovery": 5,
        "total": 16,
        "hit_frame": -1,      # no hit frame for dodge
        "vfx_frame": 3,       # dust VFX at roll start
        "sound_frame": 3,     # roll sound
        "camera_shake_frame": -1,
        "hitstop_frames": 0,
    },
    "parry": {
        "anticipation": 2,
        "active": 4,
        "recovery": 10,
        "total": 16,
        "hit_frame": 3,       # parry deflect frame
        "vfx_frame": 3,       # spark VFX on deflect
        "sound_frame": 3,     # clang sound
        "camera_shake_frame": 3,
        "hitstop_frames": 3,
    },
    "block": {
        "anticipation": 1,
        "active": 0,
        "recovery": 3,
        "total": 4,
        "hit_frame": -1,      # no hit frame
        "vfx_frame": 1,       # shield raise VFX
        "sound_frame": 0,     # guard sound
        "camera_shake_frame": -1,
        "hitstop_frames": 0,
    },
}

# VeilBreakers brand names for VFX parameterization
VALID_BRANDS: frozenset[str] = frozenset({
    "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
    "LEECH", "GRACE", "MEND", "RUIN", "VOID",
})

# Brand-specific VFX and sound param overrides
_BRAND_VFX_PARAMS: dict[str, dict[str, str]] = {
    "IRON":    {"vfx_color": "gray",    "impact_type": "metallic",   "trail": "sparks"},
    "SAVAGE":  {"vfx_color": "red",     "impact_type": "blood",      "trail": "claw_marks"},
    "SURGE":   {"vfx_color": "blue",    "impact_type": "electric",   "trail": "lightning"},
    "VENOM":   {"vfx_color": "green",   "impact_type": "poison",     "trail": "acid_drip"},
    "DREAD":   {"vfx_color": "purple",  "impact_type": "shadow",     "trail": "dark_mist"},
    "LEECH":   {"vfx_color": "crimson", "impact_type": "drain",      "trail": "blood_tendrils"},
    "GRACE":   {"vfx_color": "gold",    "impact_type": "holy",       "trail": "light_ribbons"},
    "MEND":    {"vfx_color": "white",   "impact_type": "heal",       "trail": "soft_glow"},
    "RUIN":    {"vfx_color": "orange",  "impact_type": "explosion",  "trail": "fire"},
    "VOID":    {"vfx_color": "black",   "impact_type": "distortion", "trail": "void_tears"},
}

# ---------------------------------------------------------------------------
# ANIM3-06: Per-brand animation timing profiles
# ---------------------------------------------------------------------------

BRAND_TIMING_MODIFIERS: dict[str, dict[str, float | str]] = {
    "IRON":   {"anticipation_scale": 1.5, "active_scale": 1.0, "recovery_scale": 1.3, "easing": "ease_in_out_cubic"},
    "SAVAGE": {"anticipation_scale": 0.8, "active_scale": 0.9, "recovery_scale": 0.5, "easing": "ease_in_quad"},
    "SURGE":  {"anticipation_scale": 0.5, "active_scale": 0.7, "recovery_scale": 0.6, "easing": "ease_out_expo"},
    "VENOM":  {"anticipation_scale": 1.2, "active_scale": 0.4, "recovery_scale": 1.5, "easing": "ease_in_expo"},
    "DREAD":  {"anticipation_scale": 1.3, "active_scale": 0.8, "recovery_scale": 1.0, "easing": "linear_with_pauses"},
    "LEECH":  {"anticipation_scale": 1.1, "active_scale": 1.0, "recovery_scale": 1.4, "easing": "ease_in_sticky"},
    "GRACE":  {"anticipation_scale": 0.9, "active_scale": 1.1, "recovery_scale": 0.9, "easing": "ease_in_out_sine"},
    "MEND":   {"anticipation_scale": 1.0, "active_scale": 1.2, "recovery_scale": 0.8, "easing": "ease_in_out_sine"},
    "RUIN":   {"anticipation_scale": 0.7, "active_scale": 0.6, "recovery_scale": 0.7, "easing": "chaotic_random"},
    "VOID":   {"anticipation_scale": 1.0, "active_scale": 1.0, "recovery_scale": 1.0, "easing": "time_warp"},
}


def apply_brand_timing(timing_config: dict[str, Any], brand: str) -> dict[str, Any]:
    """Apply brand-specific timing modifiers to a combat timing config."""
    brand_upper = brand.upper()
    if brand_upper not in BRAND_TIMING_MODIFIERS:
        raise ValueError(f"Unknown brand: {brand!r}. Valid: {sorted(BRAND_TIMING_MODIFIERS.keys())}")

    mods = BRAND_TIMING_MODIFIERS[brand_upper]
    result = copy.deepcopy(timing_config)
    frames = result["frames"]

    frames["anticipation"] = max(1, round(frames["anticipation"] * mods["anticipation_scale"]))
    frames["active"] = max(0, round(frames["active"] * mods["active_scale"])) if frames["active"] > 0 else 0
    frames["recovery"] = max(1, round(frames["recovery"] * mods["recovery_scale"]))
    total = frames["anticipation"] + frames["active"] + frames["recovery"]
    frames["total"] = total

    if frames["hit_frame"] >= 0 and frames["active"] > 0:
        frames["hit_frame"] = max(frames["anticipation"], min(frames["hit_frame"], frames["anticipation"] + frames["active"] - 1))
    elif frames["hit_frame"] >= 0 and frames["active"] == 0:
        frames["hit_frame"] = -1

    total_f = float(total) if total > 0 else 1.0
    antic = frames["anticipation"]
    active = frames["active"]
    result["times"] = {
        "anticipation_start": 0.0, "anticipation_end": antic / total_f,
        "active_start": antic / total_f, "active_end": (antic + active) / total_f,
        "recovery_start": (antic + active) / total_f, "recovery_end": 1.0,
        "hit_time": frames["hit_frame"] / total_f if frames["hit_frame"] >= 0 else -1.0,
    }
    result["total_frames"] = total
    result["total_duration_seconds"] = total / float(result["fps"])
    result["brand"] = brand_upper
    result["easing"] = mods["easing"]
    return result


# ---------------------------------------------------------------------------
# ANIM3-01: Configure combat timing
# ---------------------------------------------------------------------------


def configure_combat_timing(
    attack_type: str,
    fps: int = 30,
    custom_timing: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Configure combat animation timing for a given attack type.

    Returns a timing config dict with frame numbers scaled to the target fps
    and normalized time values (0.0-1.0) for each phase.

    Args:
        attack_type: One of the COMBAT_TIMING_PRESETS keys.
        fps: Target frames per second (presets are authored at 30fps).
        custom_timing: Optional dict to override specific preset values.
            Valid keys: anticipation, active, recovery, hit_frame,
            vfx_frame, sound_frame, camera_shake_frame, hitstop_frames.

    Returns:
        Dict with: attack_type, fps, frames (scaled), times (normalized),
        phase_ranges, total_frames, total_duration_seconds.

    Raises:
        ValueError: If attack_type is unknown or fps < 1.
    """
    if attack_type not in COMBAT_TIMING_PRESETS:
        raise ValueError(
            f"Unknown attack type: {attack_type!r}. "
            f"Valid types: {sorted(COMBAT_TIMING_PRESETS.keys())}"
        )
    if fps < 1:
        raise ValueError(f"fps must be >= 1, got {fps}")

    preset = dict(COMBAT_TIMING_PRESETS[attack_type])

    # Apply custom overrides
    if custom_timing:
        for key, value in custom_timing.items():
            if key in preset:
                preset[key] = value

    # Recalculate total if phases were overridden
    preset["total"] = preset["anticipation"] + preset["active"] + preset["recovery"]

    # Scale frames from reference 30fps to target fps
    scale = fps / 30.0
    anticipation = max(1, round(preset["anticipation"] * scale))
    active = max(0, round(preset["active"] * scale))
    recovery = max(1, round(preset["recovery"] * scale))
    total = anticipation + active + recovery

    # Scale event frames, clamp hit_frame to active window
    hit_frame = round(preset["hit_frame"] * scale) if preset["hit_frame"] >= 0 else -1
    if hit_frame >= 0 and active > 0:
        hit_frame = max(anticipation, min(hit_frame, anticipation + active - 1))
    elif hit_frame >= 0 and active == 0:
        hit_frame = -1  # no active window means no hit
    vfx_frame = max(0, round(preset["vfx_frame"] * scale))
    sound_frame = max(0, round(preset["sound_frame"] * scale))
    camera_shake_frame = round(preset["camera_shake_frame"] * scale) if preset["camera_shake_frame"] >= 0 else -1
    hitstop_frames = max(0, round(preset["hitstop_frames"] * scale))

    # Compute normalized times (0.0-1.0)
    total_f = float(total) if total > 0 else 1.0

    return {
        "attack_type": attack_type,
        "fps": fps,
        "frames": {
            "anticipation": anticipation,
            "active": active,
            "recovery": recovery,
            "total": total,
            "hit_frame": hit_frame,
            "vfx_frame": vfx_frame,
            "sound_frame": sound_frame,
            "camera_shake_frame": camera_shake_frame,
            "hitstop_frames": hitstop_frames,
        },
        "times": {
            "anticipation_start": 0.0,
            "anticipation_end": anticipation / total_f,
            "active_start": anticipation / total_f,
            "active_end": (anticipation + active) / total_f,
            "recovery_start": (anticipation + active) / total_f,
            "recovery_end": 1.0,
            "hit_time": hit_frame / total_f if hit_frame >= 0 else -1.0,
        },
        "phase_ranges": {
            "anticipation": (0, anticipation - 1),
            "active": (anticipation, anticipation + active - 1) if active > 0 else None,
            "recovery": (anticipation + active, total - 1),
        },
        "total_frames": total,
        "total_duration_seconds": total / float(fps),
    }


# ---------------------------------------------------------------------------
# ANIM3-02: Generate animation events
# ---------------------------------------------------------------------------


def generate_animation_events(
    timing_config: dict[str, Any],
    brand: str = "IRON",
) -> list[dict[str, Any]]:
    """Generate animation event dicts from a timing config.

    Produces a list of events suitable for Unity AnimationEvent injection
    or Blender pose marker placement. Each event has a frame, event_type,
    function_name (Unity callback), and brand-specific parameters.

    Args:
        timing_config: Output of configure_combat_timing().
        brand: VeilBreakers brand name for VFX/sound parameterization.

    Returns:
        List of event dicts: [{frame, event_type, function_name,
        string_param, float_param, int_param}].

    Raises:
        ValueError: If brand is not a valid VeilBreakers brand.
    """
    brand_upper = brand.upper()
    if brand_upper not in VALID_BRANDS:
        raise ValueError(
            f"Unknown brand: {brand!r}. Valid brands: {sorted(VALID_BRANDS)}"
        )

    frames = timing_config["frames"]
    attack_type = timing_config["attack_type"]
    brand_params = _BRAND_VFX_PARAMS[brand_upper]
    events: list[dict[str, Any]] = []

    # Sound trigger at anticipation
    if frames["sound_frame"] >= 0:
        events.append({
            "frame": frames["sound_frame"],
            "event_type": "sound_trigger",
            "function_name": "OnAnimSoundTrigger",
            "string_param": f"{attack_type}_whoosh_{brand_upper.lower()}",
            "float_param": 1.0,
            "int_param": 0,
        })

    # VFX spawn at active start
    if frames["vfx_frame"] >= 0:
        events.append({
            "frame": frames["vfx_frame"],
            "event_type": "vfx_spawn",
            "function_name": "OnAnimVFXSpawn",
            "string_param": f"{brand_params['trail']}_{attack_type}",
            "float_param": 0.0,
            "int_param": 0,
        })

    # Hit event
    if frames["hit_frame"] >= 0:
        events.append({
            "frame": frames["hit_frame"],
            "event_type": "hit",
            "function_name": "OnAnimHit",
            "string_param": f"{brand_params['impact_type']}_{attack_type}",
            "float_param": 1.0,
            "int_param": frames["hitstop_frames"],
        })

    # Camera shake on hit
    if frames["camera_shake_frame"] >= 0:
        # Intensity scales with hitstop
        intensity = min(1.0, frames["hitstop_frames"] / 6.0) if frames["hitstop_frames"] > 0 else 0.3
        events.append({
            "frame": frames["camera_shake_frame"],
            "event_type": "camera_shake",
            "function_name": "OnAnimCameraShake",
            "string_param": brand_params["impact_type"],
            "float_param": intensity,
            "int_param": 0,
        })

    # Hitstop event (same frame as hit but separate event)
    if frames["hitstop_frames"] > 0 and frames["hit_frame"] >= 0:
        events.append({
            "frame": frames["hit_frame"],
            "event_type": "hitstop",
            "function_name": "OnAnimHitstop",
            "string_param": attack_type,
            "float_param": frames["hitstop_frames"] / float(timing_config["fps"]),
            "int_param": frames["hitstop_frames"],
        })

    # Footstep events for movement-based attacks
    if attack_type in ("dodge_roll", "charged_attack", "combo_finisher"):
        # Add footstep at anticipation start and recovery midpoint
        events.append({
            "frame": 0,
            "event_type": "footstep",
            "function_name": "OnAnimFootstep",
            "string_param": "left",
            "float_param": 0.8,
            "int_param": 0,
        })
        recovery_mid = frames["anticipation"] + frames["active"] + frames["recovery"] // 2
        events.append({
            "frame": recovery_mid,
            "event_type": "footstep",
            "function_name": "OnAnimFootstep",
            "string_param": "right",
            "float_param": 0.6,
            "int_param": 0,
        })

    # Sort events by frame for deterministic ordering
    events.sort(key=lambda e: (e["frame"], e["event_type"]))

    return events


# ---------------------------------------------------------------------------
# ANIM3-05: Root motion refinement
# ---------------------------------------------------------------------------


def refine_root_motion(
    keyframes: list[dict[str, float]],
    smoothing_passes: int = 3,
    drift_threshold: float = 0.01,
) -> list[dict[str, float]]:
    """Refine root motion keyframe data to prevent foot sliding.

    Smooths Y-axis drift (vertical bobbing artifacts) and snaps small
    horizontal displacements below the drift threshold to zero, preventing
    the character from sliding when standing still.

    Each keyframe dict has: {frame, x, y, z} where:
    - x = lateral movement
    - y = vertical (up) movement
    - z = forward movement

    Args:
        keyframes: List of root motion keyframe dicts with frame, x, y, z.
        smoothing_passes: Number of Gaussian-like averaging passes on Y.
        drift_threshold: Displacements below this are snapped to zero.

    Returns:
        New list of refined keyframe dicts (original is not mutated).

    Raises:
        ValueError: If keyframes list is empty or smoothing_passes < 0.
    """
    if not keyframes:
        raise ValueError("keyframes list must not be empty")
    if smoothing_passes < 0:
        raise ValueError(f"smoothing_passes must be >= 0, got {smoothing_passes}")

    # Deep copy to avoid mutation
    refined = [dict(kf) for kf in keyframes]

    n = len(refined)
    if n < 3:
        # Not enough frames to smooth, just apply drift threshold
        for kf in refined:
            if abs(kf.get("x", 0.0)) < drift_threshold:
                kf["x"] = 0.0
            if abs(kf.get("z", 0.0)) < drift_threshold:
                kf["z"] = 0.0
        return refined

    # Pass 1: Smooth Y-axis drift (vertical bobbing)
    for _pass in range(smoothing_passes):
        y_values = [kf.get("y", 0.0) for kf in refined]
        smoothed_y = list(y_values)
        for i in range(1, n - 1):
            # Weighted average: 0.25 * prev + 0.5 * current + 0.25 * next
            smoothed_y[i] = (
                0.25 * y_values[i - 1]
                + 0.50 * y_values[i]
                + 0.25 * y_values[i + 1]
            )
        for i, kf in enumerate(refined):
            kf["y"] = smoothed_y[i]

    # Pass 2: Snap small XZ displacements to zero (foot sliding prevention)
    for i in range(1, n):
        dx = refined[i].get("x", 0.0) - refined[i - 1].get("x", 0.0)
        dz = refined[i].get("z", 0.0) - refined[i - 1].get("z", 0.0)

        if abs(dx) < drift_threshold:
            refined[i]["x"] = refined[i - 1].get("x", 0.0)
        if abs(dz) < drift_threshold:
            refined[i]["z"] = refined[i - 1].get("z", 0.0)

    # Pass 3: Ensure first and last frames have clean values
    # (prevents accumulation errors at loop boundaries)
    if abs(refined[0].get("y", 0.0)) < drift_threshold:
        refined[0]["y"] = 0.0
    if abs(refined[-1].get("y", 0.0) - refined[0].get("y", 0.0)) < drift_threshold:
        refined[-1]["y"] = refined[0].get("y", 0.0)

    return refined


# ---------------------------------------------------------------------------
# Combined combat animation data generator
# ---------------------------------------------------------------------------


def generate_combat_animation_data(
    attack_type: str,
    brand: str = "IRON",
    fps: int = 30,
    custom_timing: dict[str, int] | None = None,
    root_motion_keyframes: list[dict[str, float]] | None = None,
    smoothing_passes: int = 3,
) -> dict[str, Any]:
    """Generate complete combat animation specification.

    Combines timing configuration, animation events, and root motion
    refinement into a single spec dict suitable for Blender keyframe
    generation or Unity Animator import.

    Args:
        attack_type: Combat timing preset name.
        brand: VeilBreakers brand for VFX/sound parameterization.
        fps: Target frames per second.
        custom_timing: Optional timing overrides.
        root_motion_keyframes: Optional root motion data to refine.
        smoothing_passes: Passes for root motion smoothing.

    Returns:
        Dict with: timing, events, root_motion (if provided),
        metadata (attack_type, brand, fps).
    """
    timing = configure_combat_timing(attack_type, fps=fps, custom_timing=custom_timing)

    # Apply brand-specific timing modifiers
    brand_upper = brand.upper() if brand else "IRON"
    if brand_upper in BRAND_TIMING_MODIFIERS:
        timing = apply_brand_timing(timing, brand_upper)

    events = generate_animation_events(timing, brand=brand)

    result: dict[str, Any] = {
        "timing": timing,
        "events": events,
        "metadata": {
            "attack_type": attack_type,
            "brand": brand,
            "fps": fps,
            "total_frames": timing["total_frames"],
            "total_duration": timing["total_duration_seconds"],
            "event_count": len(events),
        },
    }

    # Refine root motion if provided
    if root_motion_keyframes:
        result["root_motion"] = refine_root_motion(
            root_motion_keyframes,
            smoothing_passes=smoothing_passes,
        )
    else:
        # Generate default root motion for the attack type
        total = timing["total_frames"]
        default_rm: list[dict[str, float]] = []
        for i in range(total):
            t = i / float(total - 1) if total > 1 else 0.0
            # Forward lunge during active phase
            active_start = timing["times"]["active_start"]
            active_end = timing["times"]["active_end"]
            if active_start <= t <= active_end and active_end > active_start:
                progress = (t - active_start) / (active_end - active_start)
                z = 0.3 * math.sin(progress * math.pi)  # forward lunge
            else:
                z = 0.0
            default_rm.append({"frame": float(i), "x": 0.0, "y": 0.0, "z": z})

        result["root_motion"] = refine_root_motion(
            default_rm, smoothing_passes=smoothing_passes,
        )

    return result
