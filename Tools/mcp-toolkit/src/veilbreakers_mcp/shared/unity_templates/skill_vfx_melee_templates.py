"""Melee skill, blood/gore, and screen effect VFX C# template generators.

Comprehensive VFX library for VeilBreakers melee combat, blood effects,
and screen post-processing combat reactions.

Each function returns a dict with ``script_path``, ``script_content``, and
``next_steps``.  Generated C# uses ParticleSystem + TrailRenderer +
LineRenderer (NOT VisualEffect), PrimeTween (NOT DOTween), C# events,
and targets Unity 2022.3+ URP with
``Universal Render Pipeline/Particles/Unlit`` shader.

Exports:
    generate_melee_skill_vfx_script    -- 25 named melee skills
    generate_blood_gore_vfx_script     -- 15 named blood/gore effects
    generate_screen_effect_vfx_script  -- 20 named screen effects
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# ---------------------------------------------------------------------------
# Brand colors -- defined locally to avoid race-condition imports
# ---------------------------------------------------------------------------

BRAND_COLORS: dict[str, list[float]] = {
    "IRON":   [0.55, 0.59, 0.65, 1.0],
    "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE":  [0.24, 0.55, 0.86, 1.0],
    "VENOM":  [0.31, 0.71, 0.24, 1.0],
    "DREAD":  [0.47, 0.24, 0.63, 1.0],
    "LEECH":  [0.55, 0.16, 0.31, 1.0],
    "GRACE":  [0.86, 0.86, 0.94, 1.0],
    "MEND":   [0.78, 0.67, 0.31, 1.0],
    "RUIN":   [0.86, 0.47, 0.16, 1.0],
    "VOID":   [0.16, 0.08, 0.24, 1.0],
}

ALL_BRANDS = list(BRAND_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# ``new Color(r, g, b, a)``."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _brand_colors_cs_dict(var_name: str) -> str:
    """Build a C# Dictionary<string, Color> initializer for all brands."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in BRAND_COLORS.items():
        lines.append(f'            {{ "{brand}", {_fmt_color(rgba)} }},')
    lines.append("        };")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Melee skill config data -- 25 named melee skills
# ---------------------------------------------------------------------------

MELEE_SKILL_CONFIGS: dict[str, dict[str, Any]] = {
    "phantom_cleave": {
        "desc": "Spectral afterimage arc, pale blue-white, 0.5s fade",
        "color": [0.75, 0.85, 1.0, 0.8], "glow": [0.9, 0.95, 1.0, 1.0],
        "rate": 200, "lifetime": 0.5, "size": 0.6, "speed": 8.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.7, 0.8, 1.0, 0.5],
        "impact_type": "afterimage_fade",
        "secondary_particles": 40, "burst": 60,
    },
    "abyssal_rend": {
        "desc": "Dark purple rift, void particles leak from wound",
        "color": [0.3, 0.08, 0.45, 1.0], "glow": [0.5, 0.15, 0.7, 1.0],
        "rate": 150, "lifetime": 1.2, "size": 0.4, "speed": 3.0,
        "shape": "Sphere", "trail_enabled": True,
        "trail_color": [0.2, 0.05, 0.35, 0.6],
        "impact_type": "void_rift",
        "secondary_particles": 80, "burst": 100,
    },
    "savage_frenzy": {
        "desc": "5-hit red claw combo, blood droplets per hit",
        "color": [0.85, 0.12, 0.12, 1.0], "glow": [1.0, 0.3, 0.2, 1.0],
        "rate": 350, "lifetime": 0.3, "size": 0.35, "speed": 12.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.8, 0.1, 0.1, 0.7],
        "impact_type": "claw_blood_spray",
        "secondary_particles": 30, "burst": 50,
    },
    "thunderstrike_blade": {
        "desc": "Lightning through blade, ground fork pattern",
        "color": [0.6, 0.85, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 500, "lifetime": 0.15, "size": 0.1, "speed": 30.0,
        "shape": "Edge", "trail_enabled": True,
        "trail_color": [0.5, 0.8, 1.0, 0.9],
        "impact_type": "ground_lightning_fork",
        "secondary_particles": 60, "burst": 120,
    },
    "crimson_crescent": {
        "desc": "Red crescent moon trail, blood mist impact",
        "color": [0.9, 0.15, 0.2, 1.0], "glow": [1.0, 0.3, 0.3, 1.0],
        "rate": 250, "lifetime": 0.6, "size": 0.5, "speed": 10.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.85, 0.1, 0.15, 0.6],
        "impact_type": "blood_mist_burst",
        "secondary_particles": 50, "burst": 80,
    },
    "bonecrusher_slam": {
        "desc": "Radial bone fragment explosion, spider-web ground crack",
        "color": [0.85, 0.8, 0.7, 1.0], "glow": [1.0, 0.95, 0.85, 1.0],
        "rate": 400, "lifetime": 0.7, "size": 0.25, "speed": 15.0,
        "shape": "Sphere", "trail_enabled": False,
        "trail_color": [0.8, 0.75, 0.65, 0.4],
        "impact_type": "radial_bone_explosion",
        "secondary_particles": 100, "burst": 200,
    },
    "venom_fang_strike": {
        "desc": "Green poison trail, toxin drip wound",
        "color": [0.2, 0.8, 0.15, 1.0], "glow": [0.4, 1.0, 0.3, 1.0],
        "rate": 180, "lifetime": 1.0, "size": 0.2, "speed": 6.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.15, 0.7, 0.1, 0.5],
        "impact_type": "toxin_drip_pool",
        "secondary_particles": 35, "burst": 45,
    },
    "soul_reaver_slash": {
        "desc": "Blue soul wisps pulled from target toward caster",
        "color": [0.3, 0.5, 0.9, 0.9], "glow": [0.5, 0.7, 1.0, 1.0],
        "rate": 120, "lifetime": 1.5, "size": 0.3, "speed": -4.0,
        "shape": "Sphere", "trail_enabled": True,
        "trail_color": [0.25, 0.45, 0.85, 0.4],
        "impact_type": "soul_wisp_drain",
        "secondary_particles": 60, "burst": 70,
    },
    "inferno_uppercut": {
        "desc": "Spiraling fire vortex, embers at apex",
        "color": [1.0, 0.5, 0.1, 1.0], "glow": [1.0, 0.7, 0.2, 1.0],
        "rate": 400, "lifetime": 0.8, "size": 0.35, "speed": 12.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [1.0, 0.4, 0.05, 0.7],
        "impact_type": "ember_apex_burst",
        "secondary_particles": 80, "burst": 150,
    },
    "glacial_bisect": {
        "desc": "Flash-freeze line, ice crystal shatter",
        "color": [0.6, 0.9, 1.0, 1.0], "glow": [0.8, 0.95, 1.0, 1.0],
        "rate": 300, "lifetime": 0.4, "size": 0.2, "speed": 20.0,
        "shape": "Edge", "trail_enabled": True,
        "trail_color": [0.5, 0.85, 0.95, 0.6],
        "impact_type": "ice_crystal_shatter",
        "secondary_particles": 70, "burst": 100,
    },
    "shadow_step_strike": {
        "desc": "Dark smoke teleport, delayed purple slash line",
        "color": [0.15, 0.05, 0.2, 0.9], "glow": [0.4, 0.15, 0.6, 1.0],
        "rate": 100, "lifetime": 0.8, "size": 0.5, "speed": 5.0,
        "shape": "Sphere", "trail_enabled": True,
        "trail_color": [0.1, 0.03, 0.15, 0.4],
        "impact_type": "delayed_slash_line",
        "secondary_particles": 45, "burst": 60,
    },
    "chain_lash": {
        "desc": "Whip-chain fire trail, target yank",
        "color": [1.0, 0.55, 0.15, 1.0], "glow": [1.0, 0.7, 0.3, 1.0],
        "rate": 280, "lifetime": 0.5, "size": 0.15, "speed": 18.0,
        "shape": "Edge", "trail_enabled": True,
        "trail_color": [0.9, 0.45, 0.1, 0.6],
        "impact_type": "chain_yank_pull",
        "secondary_particles": 40, "burst": 65,
    },
    "seismic_smash": {
        "desc": "Earth ripple wave, rocks jut ring",
        "color": [0.6, 0.45, 0.25, 1.0], "glow": [0.8, 0.6, 0.35, 1.0],
        "rate": 350, "lifetime": 0.7, "size": 0.4, "speed": 10.0,
        "shape": "Circle", "trail_enabled": False,
        "trail_color": [0.55, 0.4, 0.2, 0.5],
        "impact_type": "earth_ripple_ring",
        "secondary_particles": 90, "burst": 180,
    },
    "dimensional_slash": {
        "desc": "Simultaneous glowing white cut lines, delayed damage",
        "color": [1.0, 1.0, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "rate": 600, "lifetime": 0.2, "size": 0.08, "speed": 40.0,
        "shape": "Edge", "trail_enabled": True,
        "trail_color": [0.95, 0.95, 1.0, 0.8],
        "impact_type": "delayed_multi_cut",
        "secondary_particles": 30, "burst": 90,
    },
    "bloodletting_strike": {
        "desc": "Red energy drain tendrils from target to caster",
        "color": [0.8, 0.1, 0.15, 1.0], "glow": [1.0, 0.2, 0.25, 1.0],
        "rate": 160, "lifetime": 1.2, "size": 0.18, "speed": -3.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.7, 0.08, 0.12, 0.5],
        "impact_type": "drain_tendril_pull",
        "secondary_particles": 55, "burst": 50,
    },
    "runic_cleave": {
        "desc": "Glowing rune drawn in air, detonates after 1s",
        "color": [0.9, 0.7, 0.2, 1.0], "glow": [1.0, 0.85, 0.4, 1.0],
        "rate": 220, "lifetime": 1.0, "size": 0.5, "speed": 2.0,
        "shape": "Circle", "trail_enabled": True,
        "trail_color": [0.85, 0.65, 0.15, 0.6],
        "impact_type": "rune_detonation",
        "secondary_particles": 100, "burst": 140,
    },
    "spiral_pierce": {
        "desc": "Drilling spear rotation, wind spiral",
        "color": [0.7, 0.75, 0.8, 1.0], "glow": [0.9, 0.92, 0.95, 1.0],
        "rate": 300, "lifetime": 0.4, "size": 0.15, "speed": 22.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.65, 0.7, 0.75, 0.5],
        "impact_type": "wind_spiral_burst",
        "secondary_particles": 50, "burst": 80,
    },
    "fury_combo": {
        "desc": "Progressive 7-hit increasing intensity, screen flash finale",
        "color": [1.0, 0.3, 0.1, 1.0], "glow": [1.0, 0.5, 0.2, 1.0],
        "rate": 450, "lifetime": 0.25, "size": 0.3, "speed": 14.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.95, 0.25, 0.08, 0.7],
        "impact_type": "escalating_combo_finale",
        "secondary_particles": 40, "burst": 70,
    },
    "petrifying_blow": {
        "desc": "Stone spread from impact, gray crystallization",
        "color": [0.6, 0.58, 0.55, 1.0], "glow": [0.75, 0.73, 0.7, 1.0],
        "rate": 180, "lifetime": 1.5, "size": 0.35, "speed": 4.0,
        "shape": "Sphere", "trail_enabled": False,
        "trail_color": [0.55, 0.53, 0.5, 0.4],
        "impact_type": "stone_crystallize_spread",
        "secondary_particles": 70, "burst": 110,
    },
    "moonlight_slash": {
        "desc": "Crescent energy projectile, pale white-blue glow",
        "color": [0.8, 0.85, 1.0, 0.9], "glow": [0.9, 0.93, 1.0, 1.0],
        "rate": 250, "lifetime": 0.6, "size": 0.45, "speed": 16.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.75, 0.8, 0.95, 0.5],
        "impact_type": "crescent_wave_burst",
        "secondary_particles": 45, "burst": 75,
    },
    "draconic_claw": {
        "desc": "3 parallel claw marks glow with element",
        "color": [1.0, 0.6, 0.1, 1.0], "glow": [1.0, 0.8, 0.3, 1.0],
        "rate": 320, "lifetime": 0.5, "size": 0.3, "speed": 11.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.95, 0.55, 0.08, 0.6],
        "impact_type": "triple_claw_glow",
        "secondary_particles": 55, "burst": 90,
    },
    "execution_strike": {
        "desc": "Slow overhead, dark red buildup, screen darken",
        "color": [0.4, 0.02, 0.02, 1.0], "glow": [0.7, 0.1, 0.1, 1.0],
        "rate": 100, "lifetime": 2.0, "size": 0.7, "speed": 2.0,
        "shape": "Sphere", "trail_enabled": True,
        "trail_color": [0.35, 0.01, 0.01, 0.6],
        "impact_type": "execution_darken_burst",
        "secondary_particles": 120, "burst": 250,
    },
    "twin_fang_rip": {
        "desc": "X-shaped energy mark from dual weapons",
        "color": [0.9, 0.4, 0.9, 1.0], "glow": [1.0, 0.6, 1.0, 1.0],
        "rate": 280, "lifetime": 0.4, "size": 0.25, "speed": 13.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.85, 0.35, 0.85, 0.5],
        "impact_type": "x_mark_energy",
        "secondary_particles": 50, "burst": 85,
    },
    "corruption_rend": {
        "desc": "Corrupted pulsing wound, dark particles spread",
        "color": [0.35, 0.05, 0.4, 1.0], "glow": [0.55, 0.15, 0.65, 1.0],
        "rate": 170, "lifetime": 1.8, "size": 0.3, "speed": 3.0,
        "shape": "Sphere", "trail_enabled": True,
        "trail_color": [0.3, 0.03, 0.35, 0.5],
        "impact_type": "corruption_pulse_wound",
        "secondary_particles": 65, "burst": 80,
    },
    "spectral_riposte": {
        "desc": "Ghostly counter-slash from perfect parry",
        "color": [0.6, 0.8, 1.0, 0.7], "glow": [0.8, 0.9, 1.0, 1.0],
        "rate": 200, "lifetime": 0.4, "size": 0.5, "speed": 15.0,
        "shape": "Cone", "trail_enabled": True,
        "trail_color": [0.55, 0.75, 0.95, 0.4],
        "impact_type": "ghostly_counter_flash",
        "secondary_particles": 35, "burst": 55,
    },
}

VALID_MELEE_SKILLS = set(MELEE_SKILL_CONFIGS.keys())

# ---------------------------------------------------------------------------
# Blood/gore config data -- 15 named effects
# ---------------------------------------------------------------------------

BLOOD_GORE_CONFIGS: dict[str, dict[str, Any]] = {
    "blood_splatter": {
        "desc": "Directional spray on hit, wall/ground staining",
        "color": [0.55, 0.02, 0.02, 1.0], "glow": [0.7, 0.05, 0.05, 1.0],
        "rate": 300, "lifetime": 0.8, "size": 0.15, "speed": 12.0,
        "shape": "Cone", "gravity": -3.0, "burst": 80,
        "stain_enabled": True, "stain_lifetime": 8.0,
    },
    "visceral_burst": {
        "desc": "Critical hit body burst, high-pressure red spray",
        "color": [0.7, 0.03, 0.03, 1.0], "glow": [0.9, 0.1, 0.08, 1.0],
        "rate": 500, "lifetime": 0.6, "size": 0.2, "speed": 18.0,
        "shape": "Sphere", "gravity": -4.0, "burst": 200,
        "stain_enabled": True, "stain_lifetime": 10.0,
    },
    "hemorrhage": {
        "desc": "Continuous stream from target, pooling beneath",
        "color": [0.5, 0.01, 0.01, 1.0], "glow": [0.6, 0.04, 0.03, 1.0],
        "rate": 80, "lifetime": 2.0, "size": 0.08, "speed": 3.0,
        "shape": "Cone", "gravity": -5.0, "burst": 0,
        "stain_enabled": True, "stain_lifetime": 15.0,
    },
    "gore_explosion": {
        "desc": "Lethal blow body explosion, chunks + blood spray",
        "color": [0.6, 0.02, 0.02, 1.0], "glow": [0.8, 0.08, 0.06, 1.0],
        "rate": 600, "lifetime": 1.0, "size": 0.3, "speed": 15.0,
        "shape": "Sphere", "gravity": -6.0, "burst": 350,
        "stain_enabled": True, "stain_lifetime": 12.0,
    },
    "wound_rend": {
        "desc": "Visible slash wounds opening, element-glowing blood",
        "color": [0.65, 0.05, 0.05, 1.0], "glow": [0.85, 0.15, 0.1, 1.0],
        "rate": 200, "lifetime": 1.2, "size": 0.12, "speed": 5.0,
        "shape": "Cone", "gravity": -2.0, "burst": 60,
        "stain_enabled": True, "stain_lifetime": 6.0,
    },
    "blood_geyser": {
        "desc": "Vertical arterial fountain, gravity arc",
        "color": [0.7, 0.02, 0.02, 1.0], "glow": [0.9, 0.08, 0.05, 1.0],
        "rate": 350, "lifetime": 1.5, "size": 0.1, "speed": 20.0,
        "shape": "Cone", "gravity": -8.0, "burst": 120,
        "stain_enabled": True, "stain_lifetime": 10.0,
    },
    "impale_effect": {
        "desc": "Weapon sticking in target, blood around entry point",
        "color": [0.5, 0.02, 0.02, 1.0], "glow": [0.65, 0.06, 0.04, 1.0],
        "rate": 60, "lifetime": 3.0, "size": 0.06, "speed": 1.0,
        "shape": "Sphere", "gravity": -1.5, "burst": 30,
        "stain_enabled": True, "stain_lifetime": 20.0,
    },
    "severing_slash": {
        "desc": "Part separation, dark blood spray",
        "color": [0.45, 0.01, 0.01, 1.0], "glow": [0.6, 0.04, 0.03, 1.0],
        "rate": 450, "lifetime": 0.7, "size": 0.18, "speed": 14.0,
        "shape": "Cone", "gravity": -5.0, "burst": 180,
        "stain_enabled": True, "stain_lifetime": 10.0,
    },
    "blood_mist": {
        "desc": "Airborne red haze from mass violence",
        "color": [0.4, 0.02, 0.02, 0.5], "glow": [0.5, 0.05, 0.04, 0.6],
        "rate": 40, "lifetime": 5.0, "size": 1.5, "speed": 0.5,
        "shape": "Sphere", "gravity": 0.1, "burst": 0,
        "stain_enabled": False, "stain_lifetime": 0.0,
    },
    "corruption_bleed": {
        "desc": "Purple-black blood, corruption particles",
        "color": [0.25, 0.02, 0.2, 1.0], "glow": [0.45, 0.08, 0.4, 1.0],
        "rate": 150, "lifetime": 1.5, "size": 0.12, "speed": 5.0,
        "shape": "Sphere", "gravity": -2.5, "burst": 60,
        "stain_enabled": True, "stain_lifetime": 8.0,
    },
    "scarlet_rot": {
        "desc": "Red-orange infection spreading, flesh deterioration",
        "color": [0.8, 0.25, 0.05, 1.0], "glow": [1.0, 0.4, 0.1, 1.0],
        "rate": 100, "lifetime": 3.0, "size": 0.2, "speed": 2.0,
        "shape": "Circle", "gravity": -0.5, "burst": 40,
        "stain_enabled": True, "stain_lifetime": 15.0,
    },
    "blood_armor": {
        "desc": "Absorbed blood protective coating, dripping",
        "color": [0.5, 0.01, 0.01, 0.8], "glow": [0.65, 0.05, 0.03, 0.9],
        "rate": 50, "lifetime": 4.0, "size": 0.08, "speed": 0.3,
        "shape": "Sphere", "gravity": -1.0, "burst": 0,
        "stain_enabled": False, "stain_lifetime": 0.0,
    },
    "heart_rip": {
        "desc": "Organ extraction finisher, massive spray (monsters only)",
        "color": [0.7, 0.02, 0.02, 1.0], "glow": [1.0, 0.1, 0.08, 1.0],
        "rate": 700, "lifetime": 1.2, "size": 0.25, "speed": 16.0,
        "shape": "Sphere", "gravity": -7.0, "burst": 400,
        "stain_enabled": True, "stain_lifetime": 15.0,
    },
    "bleed_accumulation": {
        "desc": "Progressive bloodiness over time, increasing drip rate",
        "color": [0.55, 0.02, 0.02, 0.6], "glow": [0.7, 0.06, 0.04, 0.8],
        "rate": 20, "lifetime": 2.5, "size": 0.05, "speed": 0.8,
        "shape": "Sphere", "gravity": -3.0, "burst": 0,
        "stain_enabled": True, "stain_lifetime": 20.0,
    },
    "blood_nova": {
        "desc": "360-degree crimson shockwave explosion",
        "color": [0.8, 0.04, 0.04, 1.0], "glow": [1.0, 0.15, 0.1, 1.0],
        "rate": 800, "lifetime": 0.6, "size": 0.2, "speed": 22.0,
        "shape": "Sphere", "gravity": -1.0, "burst": 500,
        "stain_enabled": True, "stain_lifetime": 10.0,
    },
}

VALID_BLOOD_EFFECTS = set(BLOOD_GORE_CONFIGS.keys())

# ---------------------------------------------------------------------------
# Screen effect config data -- 20 named screen effects
# ---------------------------------------------------------------------------

SCREEN_EFFECT_CONFIGS: dict[str, dict[str, Any]] = {
    "impact_freeze_frame": {
        "desc": "2-3 frame pause on heavy hit",
        "type": "time_scale", "intensity": 0.0, "duration": 0.05,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 1.0,
    },
    "camera_shake_light": {
        "desc": "Subtle 0.1s vibration",
        "type": "camera_shake", "intensity": 0.15, "duration": 0.1,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 1.0,
    },
    "camera_shake_heavy": {
        "desc": "Violent 0.3s shake",
        "type": "camera_shake", "intensity": 0.6, "duration": 0.3,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 1.0,
    },
    "chromatic_aberration_burst": {
        "desc": "RGB separation flash on crits",
        "type": "post_process", "intensity": 1.0, "duration": 0.15,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 6.0,
    },
    "screen_flash_white": {
        "desc": "Brief white flash on powerful attacks",
        "type": "screen_overlay", "intensity": 0.8, "duration": 0.08,
        "color": [1.0, 1.0, 1.0, 0.8], "recovery_speed": 8.0,
    },
    "screen_flash_red": {
        "desc": "Red vignette on player damage",
        "type": "screen_overlay", "intensity": 0.6, "duration": 0.3,
        "color": [0.8, 0.05, 0.05, 0.6], "recovery_speed": 3.0,
    },
    "radial_blur": {
        "desc": "Edge blur during dash/charge",
        "type": "post_process", "intensity": 0.5, "duration": 0.4,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 4.0,
    },
    "slow_motion_hit": {
        "desc": "50% time for 0.5s on killing blow",
        "type": "time_scale", "intensity": 0.5, "duration": 0.5,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 2.0,
    },
    "style_rank_border": {
        "desc": "Escalating border energy with combo rank",
        "type": "screen_overlay", "intensity": 0.4, "duration": 2.0,
        "color": [1.0, 0.6, 0.1, 0.4], "recovery_speed": 0.5,
    },
    "dark_vignette": {
        "desc": "Edges darken in boss encounters",
        "type": "screen_overlay", "intensity": 0.7, "duration": 5.0,
        "color": [0.0, 0.0, 0.0, 0.7], "recovery_speed": 0.3,
    },
    "elemental_screen_tint": {
        "desc": "Brief color shift matching element/brand",
        "type": "screen_overlay", "intensity": 0.3, "duration": 0.2,
        "color": [0.5, 0.5, 1.0, 0.3], "recovery_speed": 5.0,
    },
    "transformation_zoom": {
        "desc": "Camera zoom+rotate during transform",
        "type": "camera_zoom", "intensity": 1.2, "duration": 0.8,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 2.0,
    },
    "kill_cam": {
        "desc": "Cinematic angle on final kill",
        "type": "camera_override", "intensity": 1.0, "duration": 1.5,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 1.5,
    },
    "environmental_distortion": {
        "desc": "Heat/frost/static shimmer",
        "type": "post_process", "intensity": 0.4, "duration": 1.0,
        "color": [1.0, 1.0, 1.0, 0.0], "recovery_speed": 2.0,
    },
    "boss_intro_darkening": {
        "desc": "Screen darkens for boss reveal",
        "type": "screen_overlay", "intensity": 0.85, "duration": 2.0,
        "color": [0.0, 0.0, 0.0, 0.85], "recovery_speed": 0.8,
    },
    "ultimate_cutscene": {
        "desc": "Brief cinematic insert for ultimates",
        "type": "camera_override", "intensity": 1.0, "duration": 1.2,
        "color": [1.0, 1.0, 1.0, 0.1], "recovery_speed": 2.0,
    },
    "near_death_desaturation": {
        "desc": "Colors drain at low HP",
        "type": "post_process", "intensity": 0.8, "duration": 10.0,
        "color": [0.3, 0.3, 0.3, 0.8], "recovery_speed": 0.2,
    },
    "corruption_screen_effect": {
        "desc": "Purple tendrils at screen edges",
        "type": "screen_overlay", "intensity": 0.5, "duration": 3.0,
        "color": [0.35, 0.05, 0.4, 0.5], "recovery_speed": 0.5,
    },
    "time_stop_monochrome": {
        "desc": "Grayscale except caster",
        "type": "post_process", "intensity": 1.0, "duration": 2.0,
        "color": [0.5, 0.5, 0.5, 1.0], "recovery_speed": 1.0,
    },
    "power_up_shockwave": {
        "desc": "Radial distortion from character",
        "type": "post_process", "intensity": 0.7, "duration": 0.4,
        "color": [1.0, 0.9, 0.6, 0.3], "recovery_speed": 5.0,
    },
}

VALID_SCREEN_EFFECTS = set(SCREEN_EFFECT_CONFIGS.keys())


# ---------------------------------------------------------------------------
# C# code block helpers -- shared across all three generators
# ---------------------------------------------------------------------------

_CS_PARTICLE_HELPER = '''
    // ---- Shared particle helpers ----
    private ParticleSystem CreatePS(string psName, Transform parent, int maxParticles = 1000)
    {
        var go = new GameObject(psName);
        go.transform.SetParent(parent, false);
        var ps = go.AddComponent<ParticleSystem>();
        var main = ps.main;
        main.playOnAwake = false;
        main.maxParticles = maxParticles;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        var emission = ps.emission;
        emission.enabled = false;
        var renderer = go.GetComponent<ParticleSystemRenderer>();
        renderer.material = GetParticleMaterial();
        return ps;
    }

    private void ConfigureParticleSystem(ParticleSystem ps, Color color, float rate, float lifetime,
                          float size, float speed, ParticleSystemShapeType shape = ParticleSystemShapeType.Cone,
                          float gravity = 0f)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = size;
        main.startSpeed = speed;
        main.gravityModifier = gravity;
        var emission = ps.emission;
        emission.enabled = true;
        emission.rateOverTime = rate;
        var sh = ps.shape;
        sh.enabled = true;
        sh.shapeType = shape;
    }

    private void BurstPS(ParticleSystem ps, int count, Color color, float lifetime,
                         float sizeMin, float sizeMax, float speedMin, float speedMax,
                         float gravity = 0f)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speedMin, speedMax);
        main.gravityModifier = gravity;
        var emission = ps.emission;
        emission.enabled = true;
        emission.SetBursts(new ParticleSystem.Burst[] {
            new ParticleSystem.Burst(0f, (short)count)
        });
    }

    private Material GetParticleMaterial()
    {
        if (_particleMat == null)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            _particleMat = new Material(shader);
            _particleMat.SetFloat("_Surface", 1f);
            _particleMat.SetFloat("_Blend", 0f);
            _particleMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        return _particleMat;
    }
    private Material _particleMat;

    private Material GetAdditiveMaterial()
    {
        if (_additiveMat == null)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            _additiveMat = new Material(shader);
            _additiveMat.SetFloat("_Surface", 1f);
            _additiveMat.SetFloat("_Blend", 1f);
            _additiveMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        return _additiveMat;
    }
    private Material _additiveMat;
'''

_CS_TRAIL_HELPER = '''
    private TrailRenderer CreateTrail(string trailName, Transform parent, Color color,
                                      float width = 0.15f, float lifetime = 0.3f)
    {
        var go = new GameObject(trailName);
        go.transform.SetParent(parent, false);
        var tr = go.AddComponent<TrailRenderer>();
        tr.material = GetAdditiveMaterial();
        tr.startWidth = width;
        tr.endWidth = 0f;
        tr.time = lifetime;
        tr.startColor = color;
        tr.endColor = new Color(color.r, color.g, color.b, 0f);
        tr.minVertexDistance = 0.05f;
        tr.enabled = false;
        return tr;
    }
'''

_CS_LINE_HELPER = '''
    private LineRenderer CreateLine(string lineName, Transform parent, Color color,
                                    float width = 0.08f)
    {
        var go = new GameObject(lineName);
        go.transform.SetParent(parent, false);
        var lr = go.AddComponent<LineRenderer>();
        lr.material = GetAdditiveMaterial();
        lr.startWidth = width;
        lr.endWidth = width * 0.3f;
        lr.startColor = color;
        lr.endColor = new Color(color.r, color.g, color.b, 0f);
        lr.positionCount = 0;
        lr.enabled = false;
        return lr;
    }
'''

_CS_SCREEN_SHAKE = '''
    private void DoScreenShake(float intensity, float duration)
    {
        if (Camera.main == null) return;
        PrimeTween.Tween.ShakeCamera(Camera.main, intensity, duration: duration);
    }
'''

_CS_COROUTINE_DELAY = '''
    private System.Collections.IEnumerator DelayedAction(float delay, System.Action action)
    {
        yield return new WaitForSeconds(delay);
        action?.Invoke();
    }
'''


# ---------------------------------------------------------------------------
# Python helpers for building C# config dictionaries
# ---------------------------------------------------------------------------


def _melee_skill_configs_cs() -> str:
    """Build C# dictionary initializer for all 25 melee skill configs."""
    lines = []
    lines.append("        private static readonly Dictionary<string, MeleeSkillConfig> SkillConfigs = new Dictionary<string, MeleeSkillConfig>")
    lines.append("        {")
    for name, cfg in MELEE_SKILL_CONFIGS.items():
        c = cfg["color"]
        g = cfg["glow"]
        tc = cfg["trail_color"]
        lines.append(f'            {{ "{name}", new MeleeSkillConfig {{')
        lines.append(f"                color = new Color({c[0]}f, {c[1]}f, {c[2]}f, {c[3]}f),")
        lines.append(f"                glow = new Color({g[0]}f, {g[1]}f, {g[2]}f, {g[3]}f),")
        lines.append(f"                emissionRate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f"                size = {cfg['size']}f, speed = {cfg['speed']}f,")
        lines.append(f'                shape = ParticleSystemShapeType.{cfg["shape"]},')
        lines.append(f"                trailEnabled = {'true' if cfg['trail_enabled'] else 'false'},")
        lines.append(f"                trailColor = new Color({tc[0]}f, {tc[1]}f, {tc[2]}f, {tc[3]}f),")
        lines.append(f'                impactType = "{sanitize_cs_string(cfg["impact_type"])}",')
        lines.append(f"                secondaryParticles = {cfg['secondary_particles']},")
        lines.append(f"                burstCount = {cfg['burst']},")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


def _blood_gore_configs_cs() -> str:
    """Build C# dictionary initializer for all 15 blood/gore configs."""
    lines = []
    lines.append("        private static readonly Dictionary<string, BloodConfig> BloodConfigs = new Dictionary<string, BloodConfig>")
    lines.append("        {")
    for name, cfg in BLOOD_GORE_CONFIGS.items():
        c = cfg["color"]
        g = cfg["glow"]
        lines.append(f'            {{ "{name}", new BloodConfig {{')
        lines.append(f"                color = new Color({c[0]}f, {c[1]}f, {c[2]}f, {c[3]}f),")
        lines.append(f"                glow = new Color({g[0]}f, {g[1]}f, {g[2]}f, {g[3]}f),")
        lines.append(f"                emissionRate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f"                size = {cfg['size']}f, speed = {cfg['speed']}f,")
        lines.append(f'                shape = ParticleSystemShapeType.{cfg["shape"]},')
        lines.append(f"                gravity = {cfg['gravity']}f, burstCount = {cfg['burst']},")
        lines.append(f"                stainEnabled = {'true' if cfg['stain_enabled'] else 'false'},")
        lines.append(f"                stainLifetime = {cfg['stain_lifetime']}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


def _screen_effect_configs_cs() -> str:
    """Build C# dictionary initializer for all 20 screen effect configs."""
    lines = []
    lines.append("        private static readonly Dictionary<string, ScreenEffectConfig> EffectConfigs = new Dictionary<string, ScreenEffectConfig>")
    lines.append("        {")
    for name, cfg in SCREEN_EFFECT_CONFIGS.items():
        c = cfg["color"]
        lines.append(f'            {{ "{name}", new ScreenEffectConfig {{')
        lines.append(f'                effectType = "{sanitize_cs_string(cfg["type"])}",')
        lines.append(f"                intensity = {cfg['intensity']}f, duration = {cfg['duration']}f,")
        lines.append(f"                color = new Color({c[0]}f, {c[1]}f, {c[2]}f, {c[3]}f),")
        lines.append(f"                recoverySpeed = {cfg['recovery_speed']}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


# ===================================================================
# 1. generate_melee_skill_vfx_script
# ===================================================================


def generate_melee_skill_vfx_script(skill_name: str = "phantom_cleave") -> dict[str, Any]:
    """Generate MeleeSkillVFXController MonoBehaviour with 25 named melee skills.

    Each skill has distinct particle/trail behavior, color, shape, impact type,
    and secondary particles.  A shared ``ConfigureParticleSystem`` helper
    applies per-skill config.

    API: TriggerMeleeSkill(skillName, brand, position, direction)
    Event: OnMeleeSkillTriggered(skillName, brand)

    Args:
        skill_name: Default skill to configure. Defaults to phantom_cleave.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in MELEE_SKILL_CONFIGS:
        skill_name = "phantom_cleave"

    safe_skill = sanitize_cs_identifier(skill_name)
    skill_configs_block = _melee_skill_configs_cs()
    brand_dict = _brand_colors_cs_dict("BrandColors")

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Melee Skill VFX Controller for VeilBreakers.
/// 25 named melee skills, each with distinct particle/trail behavior.
/// Default skill: {skill_name}
/// API: TriggerMeleeSkill(skillName, brand, position, direction)
/// Event: OnMeleeSkillTriggered(skillName, brand)
/// </summary>
public class MeleeSkillVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct MeleeSkillConfig
    {{
        public Color color;
        public Color glow;
        public int emissionRate;
        public float lifetime;
        public float size;
        public float speed;
        public ParticleSystemShapeType shape;
        public bool trailEnabled;
        public Color trailColor;
        public string impactType;
        public int secondaryParticles;
        public int burstCount;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";
    [SerializeField] private string defaultBrand = "IRON";

    // Events
    public event Action<string, string> OnMeleeSkillTriggered;

    // Configs
{skill_configs_block}

{brand_dict}

    // Runtime particle systems
    private ParticleSystem primaryPS;
    private ParticleSystem secondaryPS;
    private ParticleSystem impactPS;
    private TrailRenderer skillTrail;
    private LineRenderer slashLine;
    private Light skillLight;
    private Coroutine activeSkillRoutine;

    private void Awake()
    {{
        primaryPS = CreatePS("MeleeSkill_Primary", transform);
        secondaryPS = CreatePS("MeleeSkill_Secondary", transform);
        impactPS = CreatePS("MeleeSkill_Impact", transform, 500);
        skillTrail = CreateTrailInternal("MeleeSkill_Trail", transform);
        slashLine = CreateLineInternal("MeleeSkill_Line", transform);

        var lightGO = new GameObject("MeleeSkill_Light");
        lightGO.transform.SetParent(transform, false);
        skillLight = lightGO.AddComponent<Light>();
        skillLight.type = LightType.Point;
        skillLight.range = 4f;
        skillLight.intensity = 0f;
        skillLight.enabled = false;
    }}

    /// <summary>
    /// Trigger a named melee skill VFX at the given position and direction.
    /// Brand tints the base skill color toward the brand palette.
    /// </summary>
    public void TriggerMeleeSkill(string skillName, string brand, Vector3 position, Vector3 direction)
    {{
        skillName = skillName ?? defaultSkill;
        brand = brand ?? defaultBrand;
        if (!SkillConfigs.ContainsKey(skillName)) skillName = defaultSkill;

        var cfg = SkillConfigs[skillName];
        Color brandTint = BrandColors.ContainsKey(brand) ? BrandColors[brand] : BrandColors["IRON"];
        Color finalColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        Color finalGlow = Color.Lerp(cfg.glow, brandTint, 0.2f);

        if (activeSkillRoutine != null) StopCoroutine(activeSkillRoutine);
        activeSkillRoutine = StartCoroutine(PlayMeleeSkill(skillName, cfg, finalColor, finalGlow, position, direction));

        OnMeleeSkillTriggered?.Invoke(skillName, brand);
    }}

    private IEnumerator PlayMeleeSkill(string skillName, MeleeSkillConfig cfg, Color color,
                                        Color glow, Vector3 pos, Vector3 dir)
    {{
        // Position everything
        transform.position = pos;
        if (dir != Vector3.zero) transform.rotation = Quaternion.LookRotation(dir);

        // Configure primary particle system
        ConfigureParticleSystem(primaryPS, color, cfg.emissionRate, cfg.lifetime,
                                cfg.size, cfg.speed, cfg.shape);
        primaryPS.transform.position = pos;

        // Configure secondary burst particles
        BurstPS(secondaryPS, cfg.secondaryParticles, glow, cfg.lifetime * 0.8f,
                cfg.size * 0.3f, cfg.size * 0.8f, cfg.speed * 0.5f, cfg.speed * 1.2f);
        secondaryPS.transform.position = pos;

        // Trail
        if (cfg.trailEnabled)
        {{
            skillTrail.startColor = cfg.trailColor;
            skillTrail.endColor = new Color(cfg.trailColor.r, cfg.trailColor.g, cfg.trailColor.b, 0f);
            skillTrail.enabled = true;
        }}

        // Slash line for edge/multi-cut types
        if (cfg.shape == ParticleSystemShapeType.SingleSidedEdge)
        {{
            slashLine.enabled = true;
            slashLine.startColor = glow;
            slashLine.endColor = new Color(glow.r, glow.g, glow.b, 0f);
            slashLine.positionCount = 2;
            slashLine.SetPosition(0, pos);
            slashLine.SetPosition(1, pos + dir.normalized * 3f);
        }}

        // Light flash
        skillLight.enabled = true;
        skillLight.color = glow;
        skillLight.intensity = 3f;
        skillLight.transform.position = pos;

        // Play particles
        primaryPS.Play();
        secondaryPS.Play();

        // Burst impact after short delay
        yield return new WaitForSeconds(cfg.lifetime * 0.4f);
        BurstPS(impactPS, cfg.burstCount, color, cfg.lifetime * 0.6f,
                cfg.size * 0.5f, cfg.size * 1.5f, cfg.speed * 0.8f, cfg.speed * 1.5f);
        impactPS.transform.position = pos + dir.normalized * 1.5f;
        impactPS.Play();

        // Fade light
        float elapsed = 0f;
        float fadeDuration = cfg.lifetime;
        while (elapsed < fadeDuration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / fadeDuration;
            skillLight.intensity = Mathf.Lerp(3f, 0f, t);
            yield return null;
        }}

        // Cleanup
        primaryPS.Stop();
        secondaryPS.Stop();
        impactPS.Stop();
        skillTrail.enabled = false;
        slashLine.enabled = false;
        skillLight.enabled = false;
        activeSkillRoutine = null;
    }}
{_CS_PARTICLE_HELPER}
    private TrailRenderer CreateTrailInternal(string trailName, Transform parent)
    {{
        var go = new GameObject(trailName);
        go.transform.SetParent(parent, false);
        var tr = go.AddComponent<TrailRenderer>();
        tr.material = GetAdditiveMaterial();
        tr.startWidth = 0.2f;
        tr.endWidth = 0f;
        tr.time = 0.3f;
        tr.minVertexDistance = 0.05f;
        tr.enabled = false;
        return tr;
    }}

    private LineRenderer CreateLineInternal(string lineName, Transform parent)
    {{
        var go = new GameObject(lineName);
        go.transform.SetParent(parent, false);
        var lr = go.AddComponent<LineRenderer>();
        lr.material = GetAdditiveMaterial();
        lr.startWidth = 0.1f;
        lr.endWidth = 0.03f;
        lr.positionCount = 0;
        lr.enabled = false;
        return lr;
    }}

    /// <summary>Returns all available melee skill names.</summary>
    public static string[] GetAllSkillNames()
    {{
        var keys = new string[SkillConfigs.Count];
        SkillConfigs.Keys.CopyTo(keys, 0);
        return keys;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Create Melee Skill VFX Controller")]
    private static void CreateMeleeSkillVFXController()
    {{
        var go = new GameObject("MeleeSkillVFXController");
        go.AddComponent<MeleeSkillVFXController>();
        Selection.activeGameObject = go;
        Debug.Log("[VeilBreakers] MeleeSkillVFXController created with 25 named melee skills.");
    }}

    [MenuItem("VeilBreakers/VFX/Test Melee Skill - {safe_skill}")]
    private static void TestDefaultMeleeSkill()
    {{
        var ctrl = FindObjectOfType<MeleeSkillVFXController>();
        if (ctrl == null)
        {{
            Debug.LogWarning("[VeilBreakers] No MeleeSkillVFXController in scene. Create one first.");
            return;
        }}
        ctrl.TriggerMeleeSkill("{skill_name}", "IRON", ctrl.transform.position, ctrl.transform.forward);
        Debug.Log("[VeilBreakers] Triggered melee skill: {skill_name}");
    }}
#endif
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/MeleeSkillVFXController.cs",
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. generate_blood_gore_vfx_script
# ===================================================================


def generate_blood_gore_vfx_script(effect_name: str = "blood_splatter") -> dict[str, Any]:
    """Generate BloodGoreVFXController MonoBehaviour with 15 named blood/gore effects.

    Each effect has distinct spray patterns, staining behavior, and gravity.
    Config-driven via a shared particle helper.

    API: TriggerBloodEffect(effectName, position, direction, intensity)

    Args:
        effect_name: Default blood effect. Defaults to blood_splatter.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    effect_name = effect_name.lower().replace(" ", "_")
    if effect_name not in BLOOD_GORE_CONFIGS:
        effect_name = "blood_splatter"

    safe_effect = sanitize_cs_identifier(effect_name)
    blood_configs_block = _blood_gore_configs_cs()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Blood and Gore VFX Controller for VeilBreakers.
/// 15 named blood/gore effects with directional spray, staining, and gravity.
/// Default effect: {effect_name}
/// API: TriggerBloodEffect(effectName, position, direction, intensity)
/// </summary>
public class BloodGoreVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct BloodConfig
    {{
        public Color color;
        public Color glow;
        public int emissionRate;
        public float lifetime;
        public float size;
        public float speed;
        public ParticleSystemShapeType shape;
        public float gravity;
        public int burstCount;
        public bool stainEnabled;
        public float stainLifetime;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultEffect = "{effect_name}";
    [SerializeField] private float globalGoreMultiplier = 1f;
    [SerializeField] private bool enableStaining = true;

    // Events
    public event Action<string, Vector3, float> OnBloodEffectTriggered;

    // Configs
{blood_configs_block}

    // Runtime systems
    private ParticleSystem sprayPS;
    private ParticleSystem burstPS;
    private ParticleSystem dripPS;
    private ParticleSystem stainPS;
    private TrailRenderer bloodTrail;
    private Light bloodLight;
    private Coroutine activeBloodRoutine;

    // Stain decal tracking
    private readonly List<GameObject> activeStains = new List<GameObject>();
    private const int MAX_STAINS = 32;

    private void Awake()
    {{
        sprayPS = CreatePS("Blood_Spray", transform, 2000);
        burstPS = CreatePS("Blood_Burst", transform, 1500);
        dripPS = CreatePS("Blood_Drip", transform, 500);
        stainPS = CreatePS("Blood_Stain", transform, 200);

        var trailGO = new GameObject("Blood_Trail");
        trailGO.transform.SetParent(transform, false);
        bloodTrail = trailGO.AddComponent<TrailRenderer>();
        bloodTrail.material = GetAdditiveMaterial();
        bloodTrail.startWidth = 0.1f;
        bloodTrail.endWidth = 0f;
        bloodTrail.time = 0.5f;
        bloodTrail.minVertexDistance = 0.03f;
        bloodTrail.enabled = false;

        var lightGO = new GameObject("Blood_Light");
        lightGO.transform.SetParent(transform, false);
        bloodLight = lightGO.AddComponent<Light>();
        bloodLight.type = LightType.Point;
        bloodLight.range = 3f;
        bloodLight.intensity = 0f;
        bloodLight.enabled = false;
    }}

    /// <summary>
    /// Trigger a named blood/gore effect at the given position and direction.
    /// Intensity scales emission rate, burst count, and speed.
    /// </summary>
    public void TriggerBloodEffect(string effectName, Vector3 position, Vector3 direction, float intensity = 1f)
    {{
        effectName = effectName ?? defaultEffect;
        if (!BloodConfigs.ContainsKey(effectName)) effectName = defaultEffect;

        intensity = Mathf.Clamp(intensity, 0.1f, 3f) * globalGoreMultiplier;
        var cfg = BloodConfigs[effectName];

        if (activeBloodRoutine != null) StopCoroutine(activeBloodRoutine);
        activeBloodRoutine = StartCoroutine(PlayBloodEffect(effectName, cfg, position, direction, intensity));

        OnBloodEffectTriggered?.Invoke(effectName, position, intensity);
    }}

    private IEnumerator PlayBloodEffect(string effectName, BloodConfig cfg, Vector3 pos,
                                         Vector3 dir, float intensity)
    {{
        transform.position = pos;
        if (dir != Vector3.zero) transform.rotation = Quaternion.LookRotation(dir);

        int scaledRate = Mathf.RoundToInt(cfg.emissionRate * intensity);
        int scaledBurst = Mathf.RoundToInt(cfg.burstCount * intensity);
        float scaledSpeed = cfg.speed * intensity;

        // Configure spray
        ConfigureParticleSystem(sprayPS, cfg.color, scaledRate, cfg.lifetime,
                                cfg.size, scaledSpeed, cfg.shape, cfg.gravity);
        sprayPS.transform.position = pos;

        // Burst particles
        if (scaledBurst > 0)
        {{
            BurstPS(burstPS, scaledBurst, cfg.glow, cfg.lifetime * 0.7f,
                    cfg.size * 0.4f, cfg.size * 1.2f,
                    scaledSpeed * 0.6f, scaledSpeed * 1.4f, cfg.gravity);
            burstPS.transform.position = pos;
        }}

        // Drip particles for continuous effects
        if (cfg.lifetime > 1.5f)
        {{
            ConfigureParticleSystem(dripPS, cfg.color, scaledRate * 0.2f, cfg.lifetime * 1.5f,
                                    cfg.size * 0.5f, 1f, ParticleSystemShapeType.Sphere, cfg.gravity * 1.5f);
            dripPS.transform.position = pos + Vector3.down * 0.2f;
            dripPS.Play();
        }}

        // Blood trail
        bloodTrail.startColor = cfg.color;
        bloodTrail.endColor = new Color(cfg.color.r, cfg.color.g, cfg.color.b, 0f);
        bloodTrail.enabled = true;

        // Flash light
        bloodLight.enabled = true;
        bloodLight.color = cfg.glow;
        bloodLight.intensity = 2f * intensity;
        bloodLight.transform.position = pos;

        // Play main systems
        sprayPS.Play();
        if (scaledBurst > 0) burstPS.Play();

        // Staining via raycast
        if (cfg.stainEnabled && enableStaining)
        {{
            StartCoroutine(SpawnStainDecal(pos, dir, cfg.color, cfg.stainLifetime, cfg.size * 2f));
        }}

        // Fade out
        float elapsed = 0f;
        float totalDuration = cfg.lifetime * 1.2f;
        while (elapsed < totalDuration)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / totalDuration;
            bloodLight.intensity = Mathf.Lerp(2f * intensity, 0f, t);
            yield return null;
        }}

        // Cleanup
        sprayPS.Stop();
        burstPS.Stop();
        dripPS.Stop();
        bloodTrail.enabled = false;
        bloodLight.enabled = false;
        activeBloodRoutine = null;
    }}

    private IEnumerator SpawnStainDecal(Vector3 origin, Vector3 dir, Color color,
                                         float stainLife, float stainSize)
    {{
        yield return new WaitForSeconds(0.15f);

        // Raycast down and in direction to find surfaces
        Vector3[] rayDirs = {{ Vector3.down, dir.normalized, (dir + Vector3.down).normalized }};
        foreach (var rd in rayDirs)
        {{
            if (Physics.Raycast(origin, rd, out RaycastHit hit, 5f))
            {{
                if (activeStains.Count >= MAX_STAINS)
                {{
                    var oldest = activeStains[0];
                    activeStains.RemoveAt(0);
                    if (oldest != null) Destroy(oldest);
                }}

                var stainGO = GameObject.CreatePrimitive(PrimitiveType.Quad);
                stainGO.name = "BloodStain";
                Destroy(stainGO.GetComponent<Collider>());
                stainGO.transform.position = hit.point + hit.normal * 0.01f;
                stainGO.transform.rotation = Quaternion.LookRotation(-hit.normal);
                stainGO.transform.localScale = Vector3.one * stainSize;

                var mat = new Material(GetParticleMaterial());
                mat.color = color;
                stainGO.GetComponent<Renderer>().material = mat;
                activeStains.Add(stainGO);

                // Fade and destroy after stainLife
                StartCoroutine(FadeStain(stainGO, mat, stainLife));
                break;
            }}
        }}
    }}

    private IEnumerator FadeStain(GameObject stainGO, Material mat, float life)
    {{
        yield return new WaitForSeconds(life * 0.7f);
        float fadeDuration = life * 0.3f;
        float elapsed = 0f;
        Color startColor = mat.color;
        while (elapsed < fadeDuration && stainGO != null)
        {{
            elapsed += Time.deltaTime;
            float a = Mathf.Lerp(startColor.a, 0f, elapsed / fadeDuration);
            mat.color = new Color(startColor.r, startColor.g, startColor.b, a);
            yield return null;
        }}
        if (stainGO != null)
        {{
            activeStains.Remove(stainGO);
            Destroy(stainGO);
        }}
    }}
{_CS_PARTICLE_HELPER}
    /// <summary>Returns all available blood effect names.</summary>
    public static string[] GetAllEffectNames()
    {{
        var keys = new string[BloodConfigs.Count];
        BloodConfigs.Keys.CopyTo(keys, 0);
        return keys;
    }}

    /// <summary>Clear all active blood stains.</summary>
    public void ClearAllStains()
    {{
        foreach (var s in activeStains)
        {{
            if (s != null) Destroy(s);
        }}
        activeStains.Clear();
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Create Blood Gore VFX Controller")]
    private static void CreateBloodGoreVFXController()
    {{
        var go = new GameObject("BloodGoreVFXController");
        go.AddComponent<BloodGoreVFXController>();
        Selection.activeGameObject = go;
        Debug.Log("[VeilBreakers] BloodGoreVFXController created with 15 named blood/gore effects.");
    }}

    [MenuItem("VeilBreakers/VFX/Test Blood Effect - {safe_effect}")]
    private static void TestDefaultBloodEffect()
    {{
        var ctrl = FindObjectOfType<BloodGoreVFXController>();
        if (ctrl == null)
        {{
            Debug.LogWarning("[VeilBreakers] No BloodGoreVFXController in scene. Create one first.");
            return;
        }}
        ctrl.TriggerBloodEffect("{effect_name}", ctrl.transform.position, ctrl.transform.forward, 1f);
        Debug.Log("[VeilBreakers] Triggered blood effect: {effect_name}");
    }}
#endif
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/BloodGoreVFXController.cs",
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 3. generate_screen_effect_vfx_script
# ===================================================================


def generate_screen_effect_vfx_script(effect_name: str = "impact_freeze_frame") -> dict[str, Any]:
    """Generate ScreenEffectVFXController MonoBehaviour with 20 named screen effects.

    Covers time scale, camera shake, post-processing, screen overlays,
    camera zoom, and camera overrides.  Uses PrimeTween for all animation.

    API: TriggerScreenEffect(effectName, intensity, duration)

    Args:
        effect_name: Default screen effect. Defaults to impact_freeze_frame.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    effect_name = effect_name.lower().replace(" ", "_")
    if effect_name not in SCREEN_EFFECT_CONFIGS:
        effect_name = "impact_freeze_frame"

    safe_effect = sanitize_cs_identifier(effect_name)
    screen_configs_block = _screen_effect_configs_cs()

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Screen Effect VFX Controller for VeilBreakers.
/// 20 named screen effects: time scale, camera shake, post-processing,
/// screen overlays, camera zoom, and camera overrides.
/// Default effect: {effect_name}
/// API: TriggerScreenEffect(effectName, intensity, duration)
/// </summary>
public class ScreenEffectVFXController : MonoBehaviour
{{
    [System.Serializable]
    public struct ScreenEffectConfig
    {{
        public string effectType;
        public float intensity;
        public float duration;
        public Color color;
        public float recoverySpeed;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultEffect = "{effect_name}";

    [Header("References")]
    [SerializeField] private Volume postProcessVolume;
    [SerializeField] private Camera mainCamera;

    // Events
    public event Action<string, float, float> OnScreenEffectTriggered;

    // Configs
{screen_configs_block}

    // Runtime state
    private Coroutine activeEffectRoutine;
    private float originalTimeScale = 1f;
    private float originalFOV;
    private Quaternion originalCamRotation;

    // Screen overlay quad
    private GameObject overlayQuad;
    private Material overlayMat;
    private MeshRenderer overlayRenderer;

    // Post-process overrides cache
    private ChromaticAberration chromaticAberration;
    private Vignette vignette;
    private ColorAdjustments colorAdjustments;

    private void Awake()
    {{
        if (mainCamera == null) mainCamera = Camera.main;
        if (mainCamera != null)
        {{
            originalFOV = mainCamera.fieldOfView;
            originalCamRotation = mainCamera.transform.rotation;
        }}

        SetupOverlayQuad();
        CachePostProcessOverrides();
    }}

    private void SetupOverlayQuad()
    {{
        overlayQuad = GameObject.CreatePrimitive(PrimitiveType.Quad);
        overlayQuad.name = "ScreenEffect_Overlay";
        overlayQuad.transform.SetParent(transform, false);
        Destroy(overlayQuad.GetComponent<Collider>());

        var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
        if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
        overlayMat = new Material(shader);
        overlayMat.SetFloat("_Surface", 1f);
        overlayMat.SetFloat("_Blend", 0f);
        overlayMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        overlayMat.color = new Color(0, 0, 0, 0);
        overlayMat.renderQueue = 4000;

        overlayRenderer = overlayQuad.GetComponent<MeshRenderer>();
        overlayRenderer.material = overlayMat;
        overlayRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        overlayRenderer.receiveShadows = false;

        overlayQuad.SetActive(false);
    }}

    private void CachePostProcessOverrides()
    {{
        if (postProcessVolume == null)
        {{
            postProcessVolume = FindObjectOfType<Volume>();
        }}
        if (postProcessVolume != null && postProcessVolume.profile != null)
        {{
            postProcessVolume.profile.TryGet(out chromaticAberration);
            postProcessVolume.profile.TryGet(out vignette);
            postProcessVolume.profile.TryGet(out colorAdjustments);
        }}
    }}

    /// <summary>
    /// Trigger a named screen effect with optional intensity and duration overrides.
    /// Pass 0 for intensity/duration to use config defaults.
    /// </summary>
    public void TriggerScreenEffect(string effectName, float intensity = 0f, float duration = 0f)
    {{
        effectName = effectName ?? defaultEffect;
        if (!EffectConfigs.ContainsKey(effectName)) effectName = defaultEffect;

        var cfg = EffectConfigs[effectName];
        float finalIntensity = intensity > 0f ? intensity : cfg.intensity;
        float finalDuration = duration > 0f ? duration : cfg.duration;

        if (activeEffectRoutine != null) StopCoroutine(activeEffectRoutine);
        activeEffectRoutine = StartCoroutine(PlayScreenEffect(effectName, cfg, finalIntensity, finalDuration));

        OnScreenEffectTriggered?.Invoke(effectName, finalIntensity, finalDuration);
    }}

    private IEnumerator PlayScreenEffect(string effectName, ScreenEffectConfig cfg,
                                          float intensity, float duration)
    {{
        switch (cfg.effectType)
        {{
            case "time_scale":
                yield return PlayTimeScale(intensity, duration, cfg.recoverySpeed);
                break;
            case "camera_shake":
                yield return PlayCameraShake(intensity, duration);
                break;
            case "post_process":
                yield return PlayPostProcess(effectName, cfg, intensity, duration);
                break;
            case "screen_overlay":
                yield return PlayScreenOverlay(cfg.color, intensity, duration, cfg.recoverySpeed);
                break;
            case "camera_zoom":
                yield return PlayCameraZoom(intensity, duration, cfg.recoverySpeed);
                break;
            case "camera_override":
                yield return PlayCameraOverride(intensity, duration, cfg.recoverySpeed);
                break;
        }}

        activeEffectRoutine = null;
    }}

    // ---- Time Scale Effects ----
    private IEnumerator PlayTimeScale(float targetScale, float duration, float recoverySpeed)
    {{
        originalTimeScale = Time.timeScale;
        Time.timeScale = targetScale;
        Time.fixedDeltaTime = 0.02f * targetScale;

        yield return new WaitForSecondsRealtime(duration);

        float elapsed = 0f;
        float recoveryDuration = 1f / Mathf.Max(recoverySpeed, 0.1f);
        while (elapsed < recoveryDuration)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = elapsed / recoveryDuration;
            Time.timeScale = Mathf.Lerp(targetScale, originalTimeScale, t);
            Time.fixedDeltaTime = 0.02f * Time.timeScale;
            yield return null;
        }}
        Time.timeScale = originalTimeScale;
        Time.fixedDeltaTime = 0.02f;
    }}

    // ---- Camera Shake ----
    private IEnumerator PlayCameraShake(float intensity, float duration)
    {{
        if (mainCamera == null) yield break;
        PrimeTween.Tween.ShakeCamera(mainCamera, intensity, duration: duration);
        yield return new WaitForSeconds(duration);
    }}

    // ---- Post-Process Effects ----
    private IEnumerator PlayPostProcess(string effectName, ScreenEffectConfig cfg,
                                         float intensity, float duration)
    {{
        // Chromatic aberration burst
        if (effectName.Contains("chromatic") && chromaticAberration != null)
        {{
            chromaticAberration.active = true;
            chromaticAberration.intensity.Override(intensity);
            yield return new WaitForSeconds(duration);
            float elapsed = 0f;
            float recovery = 1f / Mathf.Max(cfg.recoverySpeed, 0.1f);
            while (elapsed < recovery)
            {{
                elapsed += Time.deltaTime;
                chromaticAberration.intensity.Override(Mathf.Lerp(intensity, 0f, elapsed / recovery));
                yield return null;
            }}
            chromaticAberration.intensity.Override(0f);
            yield break;
        }}

        // Vignette effects (radial blur approximation, desaturation)
        if (vignette != null && (effectName.Contains("radial") || effectName.Contains("desaturation")
            || effectName.Contains("distortion") || effectName.Contains("death")))
        {{
            vignette.active = true;
            vignette.intensity.Override(Mathf.Clamp01(intensity));
            if (effectName.Contains("death") || effectName.Contains("desaturation"))
            {{
                if (colorAdjustments != null)
                {{
                    colorAdjustments.active = true;
                    colorAdjustments.saturation.Override(-80f * intensity);
                }}
            }}
            yield return new WaitForSeconds(duration);
            float elapsed = 0f;
            float recovery = 1f / Mathf.Max(cfg.recoverySpeed, 0.1f);
            while (elapsed < recovery)
            {{
                elapsed += Time.deltaTime;
                float t = elapsed / recovery;
                vignette.intensity.Override(Mathf.Lerp(intensity, 0f, t));
                if (colorAdjustments != null && (effectName.Contains("death") || effectName.Contains("desaturation")))
                    colorAdjustments.saturation.Override(Mathf.Lerp(-80f * intensity, 0f, t));
                yield return null;
            }}
            vignette.intensity.Override(0f);
            if (colorAdjustments != null) colorAdjustments.saturation.Override(0f);
            yield break;
        }}

        // Monochrome time stop
        if (effectName.Contains("monochrome") && colorAdjustments != null)
        {{
            colorAdjustments.active = true;
            colorAdjustments.saturation.Override(-100f);
            yield return new WaitForSeconds(duration);
            float elapsed = 0f;
            float recovery = 1f / Mathf.Max(cfg.recoverySpeed, 0.1f);
            while (elapsed < recovery)
            {{
                elapsed += Time.deltaTime;
                colorAdjustments.saturation.Override(Mathf.Lerp(-100f, 0f, elapsed / recovery));
                yield return null;
            }}
            colorAdjustments.saturation.Override(0f);
            yield break;
        }}

        // Generic post-process fallback: use vignette
        if (vignette != null)
        {{
            vignette.active = true;
            vignette.intensity.Override(Mathf.Clamp01(intensity * 0.5f));
            yield return new WaitForSeconds(duration);
            float elapsed = 0f;
            float recovery = 1f / Mathf.Max(cfg.recoverySpeed, 0.1f);
            while (elapsed < recovery)
            {{
                elapsed += Time.deltaTime;
                vignette.intensity.Override(Mathf.Lerp(intensity * 0.5f, 0f, elapsed / recovery));
                yield return null;
            }}
            vignette.intensity.Override(0f);
        }}
        else
        {{
            yield return new WaitForSeconds(duration);
        }}
    }}

    // ---- Screen Overlay ----
    private IEnumerator PlayScreenOverlay(Color color, float intensity, float duration, float recoverySpeed)
    {{
        if (mainCamera == null) yield break;

        // Position overlay quad in front of camera
        overlayQuad.SetActive(true);
        overlayQuad.transform.position = mainCamera.transform.position + mainCamera.transform.forward * (mainCamera.nearClipPlane + 0.1f);
        overlayQuad.transform.rotation = mainCamera.transform.rotation;
        overlayQuad.transform.localScale = new Vector3(
            mainCamera.orthographicSize * mainCamera.aspect * 3f,
            mainCamera.orthographicSize * 3f, 1f);
        if (!mainCamera.orthographic)
        {{
            float dist = mainCamera.nearClipPlane + 0.1f;
            float height = 2f * dist * Mathf.Tan(mainCamera.fieldOfView * 0.5f * Mathf.Deg2Rad);
            float width = height * mainCamera.aspect;
            overlayQuad.transform.localScale = new Vector3(width * 1.2f, height * 1.2f, 1f);
        }}

        Color targetColor = new Color(color.r, color.g, color.b, color.a * intensity);
        overlayMat.color = targetColor;

        yield return new WaitForSeconds(duration);

        // Fade out
        float elapsed = 0f;
        float recovery = 1f / Mathf.Max(recoverySpeed, 0.1f);
        while (elapsed < recovery)
        {{
            elapsed += Time.deltaTime;
            float t = elapsed / recovery;
            float a = Mathf.Lerp(targetColor.a, 0f, t);
            overlayMat.color = new Color(color.r, color.g, color.b, a);
            // Keep overlay positioned in front of camera
            overlayQuad.transform.position = mainCamera.transform.position + mainCamera.transform.forward * (mainCamera.nearClipPlane + 0.1f);
            overlayQuad.transform.rotation = mainCamera.transform.rotation;
            yield return null;
        }}

        overlayMat.color = new Color(0, 0, 0, 0);
        overlayQuad.SetActive(false);
    }}

    // ---- Camera Zoom ----
    private IEnumerator PlayCameraZoom(float zoomMultiplier, float duration, float recoverySpeed)
    {{
        if (mainCamera == null) yield break;

        float targetFOV = originalFOV / Mathf.Max(zoomMultiplier, 0.1f);

        // Zoom in
        float elapsed = 0f;
        float halfDuration = duration * 0.5f;
        while (elapsed < halfDuration)
        {{
            elapsed += Time.deltaTime;
            mainCamera.fieldOfView = Mathf.Lerp(originalFOV, targetFOV, elapsed / halfDuration);
            yield return null;
        }}

        // Hold
        yield return new WaitForSeconds(duration * 0.2f);

        // Zoom out
        elapsed = 0f;
        float recovery = 1f / Mathf.Max(recoverySpeed, 0.1f);
        while (elapsed < recovery)
        {{
            elapsed += Time.deltaTime;
            mainCamera.fieldOfView = Mathf.Lerp(targetFOV, originalFOV, elapsed / recovery);
            yield return null;
        }}
        mainCamera.fieldOfView = originalFOV;
    }}

    // ---- Camera Override (Kill Cam / Cutscene) ----
    private IEnumerator PlayCameraOverride(float intensity, float duration, float recoverySpeed)
    {{
        if (mainCamera == null) yield break;

        Quaternion savedRot = mainCamera.transform.rotation;
        Vector3 savedPos = mainCamera.transform.position;

        // Dramatic angle: offset camera for cinematic framing
        Vector3 offset = mainCamera.transform.right * 1.5f * intensity + Vector3.up * 0.5f * intensity;
        Vector3 targetPos = savedPos + offset;
        Quaternion targetRot = Quaternion.LookRotation(
            (savedPos + mainCamera.transform.forward * 5f) - targetPos);

        // Lerp to cinematic position
        float elapsed = 0f;
        float moveIn = duration * 0.2f;
        while (elapsed < moveIn)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = elapsed / moveIn;
            mainCamera.transform.position = Vector3.Lerp(savedPos, targetPos, t);
            mainCamera.transform.rotation = Quaternion.Slerp(savedRot, targetRot, t);
            yield return null;
        }}

        // Hold cinematic angle
        yield return new WaitForSecondsRealtime(duration * 0.6f);

        // Return to original
        elapsed = 0f;
        float recovery = 1f / Mathf.Max(recoverySpeed, 0.1f);
        while (elapsed < recovery)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = elapsed / recovery;
            mainCamera.transform.position = Vector3.Lerp(targetPos, savedPos, t);
            mainCamera.transform.rotation = Quaternion.Slerp(targetRot, savedRot, t);
            yield return null;
        }}
        mainCamera.transform.position = savedPos;
        mainCamera.transform.rotation = savedRot;
    }}

    /// <summary>Returns all available screen effect names.</summary>
    public static string[] GetAllEffectNames()
    {{
        var keys = new string[EffectConfigs.Count];
        EffectConfigs.Keys.CopyTo(keys, 0);
        return keys;
    }}

    /// <summary>Force-reset all screen effects to default state.</summary>
    public void ResetAllEffects()
    {{
        if (activeEffectRoutine != null)
        {{
            StopCoroutine(activeEffectRoutine);
            activeEffectRoutine = null;
        }}

        Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;

        if (mainCamera != null)
        {{
            mainCamera.fieldOfView = originalFOV;
        }}

        if (overlayMat != null)
        {{
            overlayMat.color = new Color(0, 0, 0, 0);
        }}
        if (overlayQuad != null) overlayQuad.SetActive(false);

        if (chromaticAberration != null) chromaticAberration.intensity.Override(0f);
        if (vignette != null) vignette.intensity.Override(0f);
        if (colorAdjustments != null) colorAdjustments.saturation.Override(0f);
    }}

    private void OnDestroy()
    {{
        // Ensure time scale is restored
        Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Create Screen Effect VFX Controller")]
    private static void CreateScreenEffectVFXController()
    {{
        var go = new GameObject("ScreenEffectVFXController");
        go.AddComponent<ScreenEffectVFXController>();
        Selection.activeGameObject = go;
        Debug.Log("[VeilBreakers] ScreenEffectVFXController created with 20 named screen effects.");
    }}

    [MenuItem("VeilBreakers/VFX/Test Screen Effect - {safe_effect}")]
    private static void TestDefaultScreenEffect()
    {{
        var ctrl = FindObjectOfType<ScreenEffectVFXController>();
        if (ctrl == null)
        {{
            Debug.LogWarning("[VeilBreakers] No ScreenEffectVFXController in scene. Create one first.");
            return;
        }}
        ctrl.TriggerScreenEffect("{effect_name}");
        Debug.Log("[VeilBreakers] Triggered screen effect: {effect_name}");
    }}
#endif
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/ScreenEffectVFXController.cs",
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }
