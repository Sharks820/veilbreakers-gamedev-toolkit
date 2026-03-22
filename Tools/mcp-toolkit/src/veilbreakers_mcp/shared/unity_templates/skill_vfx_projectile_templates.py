"""Projectile + Ground/AoE skill VFX C# template generators for VeilBreakers.

Generates ParticleSystem-based VFX controllers for:
  - 25 named projectile skills (void_bolt, hellfire_orb, frost_shard_volley, ...)
  - 30 named ground/AoE skills (eruption, frozen_domain, corpse_garden, ...)

Uses PrimeTween for animation, C# events for callbacks, Unity 2022.3+ URP.
Shader: Universal Render Pipeline/Particles/Unlit.

Exports:
    generate_projectile_skill_vfx_script  -- ProjectileSkillVFXController MonoBehaviour
    generate_ground_aoe_skill_vfx_script  -- GroundAoESkillVFXController MonoBehaviour
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier

# ---------------------------------------------------------------------------
# Brand palette -- canonical RGBA colors for all 10 VeilBreakers brands.
# ---------------------------------------------------------------------------

BRAND_PRIMARY_COLORS: dict[str, list[float]] = {
    "IRON": [0.55, 0.59, 0.65, 1.0], "SAVAGE": [0.71, 0.18, 0.18, 1.0],
    "SURGE": [0.24, 0.55, 0.86, 1.0], "VENOM": [0.31, 0.71, 0.24, 1.0],
    "DREAD": [0.47, 0.24, 0.63, 1.0], "LEECH": [0.55, 0.16, 0.31, 1.0],
    "GRACE": [0.86, 0.86, 0.94, 1.0], "MEND": [0.78, 0.67, 0.31, 1.0],
    "RUIN": [0.86, 0.47, 0.16, 1.0], "VOID": [0.16, 0.08, 0.24, 1.0],
}
BRAND_GLOW_COLORS: dict[str, list[float]] = {
    "IRON": [0.71, 0.75, 0.80, 1.0], "SAVAGE": [0.86, 0.27, 0.27, 1.0],
    "SURGE": [0.39, 0.71, 1.00, 1.0], "VENOM": [0.47, 0.86, 0.39, 1.0],
    "DREAD": [0.63, 0.39, 0.78, 1.0], "LEECH": [0.71, 0.24, 0.43, 1.0],
    "GRACE": [1.00, 1.00, 1.00, 1.0], "MEND": [0.94, 0.82, 0.47, 1.0],
    "RUIN": [1.00, 0.63, 0.31, 1.0], "VOID": [0.39, 0.24, 0.55, 1.0],
}

ALL_BRANDS = list(BRAND_PRIMARY_COLORS.keys())

STANDARD_NEXT_STEPS = [
    "Open Unity Editor",
    "Wait for compilation",
    "Run the menu item from VeilBreakers menu",
]


# ---------------------------------------------------------------------------
# Projectile skill configs (25 skills)
# ---------------------------------------------------------------------------

PROJECTILE_CONFIGS: dict[str, dict[str, Any]] = {
    "void_bolt": {
        "color": [0.16, 0.08, 0.24, 1.0], "glow": [0.39, 0.24, 0.55, 1.0],
        "speed": 16.0, "size": 0.4, "rate": 250, "lifetime": 0.9,
        "trail_type": "spiral", "impact_type": "implode",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 300,
        "desc": "Dark sphere with swirling void particles, distorts space",
    },
    "hellfire_orb": {
        "color": [1.0, 0.3, 0.05, 1.0], "glow": [1.0, 0.65, 0.15, 1.0],
        "speed": 12.0, "size": 0.7, "rate": 400, "lifetime": 1.2,
        "trail_type": "flame", "impact_type": "scorch",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 500,
        "desc": "Large burning sphere, heat distortion, ground scorch",
    },
    "frost_shard_volley": {
        "color": [0.5, 0.85, 1.0, 1.0], "glow": [0.75, 0.95, 1.0, 1.0],
        "speed": 22.0, "size": 0.2, "rate": 180, "lifetime": 0.5,
        "trail_type": "frost", "impact_type": "shatter",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 200,
        "desc": "5-7 ice crystal spread, fragment shatter on impact",
    },
    "soul_arrow": {
        "color": [0.2, 0.7, 0.55, 1.0], "glow": [0.35, 0.9, 0.7, 1.0],
        "speed": 25.0, "size": 0.15, "rate": 150, "lifetime": 0.6,
        "trail_type": "wispy", "impact_type": "phase",
        "homing": False, "pierce": True, "bounce": False, "particle_count": 180,
        "desc": "Ghostly blue-green arrow, wispy trail, pierces first target",
    },
    "chain_lightning": {
        "color": [0.6, 0.85, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "speed": 50.0, "size": 0.1, "rate": 600, "lifetime": 0.12,
        "trail_type": "electric", "impact_type": "arc",
        "homing": False, "pierce": True, "bounce": True, "particle_count": 400,
        "desc": "Electric bolt jumping 3-5 targets, branching arcs",
    },
    "bone_javelin": {
        "color": [0.85, 0.82, 0.7, 1.0], "glow": [0.95, 0.9, 0.75, 1.0],
        "speed": 20.0, "size": 0.25, "rate": 200, "lifetime": 0.7,
        "trail_type": "bone_dust", "impact_type": "shatter",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 250,
        "desc": "Skeletal spear spinning in flight, bone burst on impact",
    },
    "plasma_lance": {
        "color": [1.0, 0.97, 0.9, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "speed": 60.0, "size": 0.08, "rate": 700, "lifetime": 0.1,
        "trail_type": "beam", "impact_type": "scorch",
        "homing": False, "pierce": True, "bounce": False, "particle_count": 500,
        "desc": "White-hot persistent beam with heat shimmer",
    },
    "seeking_orbs": {
        "color": [0.5, 0.3, 0.9, 1.0], "glow": [0.7, 0.5, 1.0, 1.0],
        "speed": 14.0, "size": 0.25, "rate": 220, "lifetime": 1.0,
        "trail_type": "comet", "impact_type": "burst",
        "homing": True, "pierce": False, "bounce": False, "particle_count": 300,
        "desc": "3 homing purple-blue comets, spiral approach to target",
    },
    "dragon_breath_bolt": {
        "color": [1.0, 0.55, 0.1, 1.0], "glow": [1.0, 0.8, 0.3, 1.0],
        "speed": 18.0, "size": 0.55, "rate": 350, "lifetime": 0.8,
        "trail_type": "flame", "impact_type": "explosion",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 400,
        "desc": "Condensed dragon fire, draconic silhouette in trail",
    },
    "corruption_spore": {
        "color": [0.2, 0.5, 0.1, 1.0], "glow": [0.35, 0.65, 0.2, 1.0],
        "speed": 8.0, "size": 0.5, "rate": 120, "lifetime": 2.0,
        "trail_type": "spore", "impact_type": "cloud",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 200,
        "desc": "Slow green-black bio projectile, spore cloud burst",
    },
    "moonbeam": {
        "color": [0.85, 0.88, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "speed": 40.0, "size": 0.6, "rate": 300, "lifetime": 0.5,
        "trail_type": "beam", "impact_type": "radiance",
        "homing": False, "pierce": True, "bounce": False, "particle_count": 350,
        "desc": "Silver-white beam from above, cold lunar light",
    },
    "blood_missile": {
        "color": [0.7, 0.05, 0.05, 1.0], "glow": [0.9, 0.15, 0.1, 1.0],
        "speed": 19.0, "size": 0.3, "rate": 280, "lifetime": 0.8,
        "trail_type": "drip", "impact_type": "splash",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 300,
        "desc": "Crimson solidified blood, red droplet trail, blood splash",
    },
    "spectral_blade": {
        "color": [0.6, 0.7, 1.0, 0.8], "glow": [0.85, 0.9, 1.0, 1.0],
        "speed": 17.0, "size": 0.35, "rate": 200, "lifetime": 0.9,
        "trail_type": "spirit", "impact_type": "phase",
        "homing": False, "pierce": False, "bounce": True, "particle_count": 250,
        "desc": "Thrown ghostly boomerang sword, blue-white spirit trail",
    },
    "abyssal_tendril": {
        "color": [0.12, 0.05, 0.18, 1.0], "glow": [0.3, 0.15, 0.45, 1.0],
        "speed": 15.0, "size": 0.3, "rate": 180, "lifetime": 1.2,
        "trail_type": "tendril", "impact_type": "grab",
        "homing": True, "pierce": False, "bounce": False, "particle_count": 250,
        "desc": "Dark tentacle grab, pulls target to caster",
    },
    "petal_storm": {
        "color": [0.95, 0.5, 0.6, 1.0], "glow": [1.0, 0.7, 0.75, 1.0],
        "speed": 20.0, "size": 0.2, "rate": 350, "lifetime": 0.7,
        "trail_type": "spiral", "impact_type": "scatter",
        "homing": False, "pierce": True, "bounce": False, "particle_count": 400,
        "desc": "Spiral razor petals, pink-red cutting wind",
    },
    "thunder_javelin": {
        "color": [0.7, 0.85, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "speed": 35.0, "size": 0.2, "rate": 500, "lifetime": 0.3,
        "trail_type": "electric", "impact_type": "field",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 450,
        "desc": "Lightning spear, expanding electric field on impact",
    },
    "magma_glob": {
        "color": [1.0, 0.4, 0.05, 1.0], "glow": [1.0, 0.7, 0.2, 1.0],
        "speed": 14.0, "size": 0.45, "rate": 300, "lifetime": 1.0,
        "trail_type": "flame", "impact_type": "pool",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 350,
        "desc": "Arcing molten rock, fire trail, lava pool landing",
    },
    "wind_cutter": {
        "color": [0.8, 0.9, 0.95, 0.4], "glow": [0.9, 0.95, 1.0, 0.6],
        "speed": 45.0, "size": 0.1, "rate": 100, "lifetime": 0.15,
        "trail_type": "distortion", "impact_type": "delayed_cut",
        "homing": False, "pierce": True, "bounce": False, "particle_count": 120,
        "desc": "Invisible air blade, distortion line, delayed cut mark",
    },
    "star_barrage": {
        "color": [0.5, 0.6, 1.0, 1.0], "glow": [0.8, 0.85, 1.0, 1.0],
        "speed": 28.0, "size": 0.1, "rate": 150, "lifetime": 0.4,
        "trail_type": "glint", "impact_type": "burst",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 150,
        "desc": "8-12 rapid small glintstone shots, constellation pattern",
    },
    "necrotic_orb": {
        "color": [0.3, 0.55, 0.15, 1.0], "glow": [0.45, 0.7, 0.25, 1.0],
        "speed": 13.0, "size": 0.4, "rate": 200, "lifetime": 1.1,
        "trail_type": "decay", "impact_type": "wither",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 280,
        "desc": "Sickly green death energy, visible decay on hit",
    },
    "bifrost_arrow": {
        "color": [0.9, 0.5, 0.9, 1.0], "glow": [1.0, 0.8, 1.0, 1.0],
        "speed": 30.0, "size": 0.2, "rate": 350, "lifetime": 0.5,
        "trail_type": "rainbow", "impact_type": "prismatic",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 400,
        "desc": "Rainbow-prismatic energy, iridescent trail, prismatic explosion",
    },
    "ember_volley": {
        "color": [1.0, 0.5, 0.15, 1.0], "glow": [1.0, 0.75, 0.3, 1.0],
        "speed": 22.0, "size": 0.15, "rate": 180, "lifetime": 0.5,
        "trail_type": "ember", "impact_type": "burst",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 200,
        "desc": "Fan of 5 small fire projectiles, ember trails",
    },
    "shadow_kunai": {
        "color": [0.15, 0.1, 0.2, 1.0], "glow": [0.35, 0.25, 0.5, 1.0],
        "speed": 35.0, "size": 0.12, "rate": 160, "lifetime": 0.3,
        "trail_type": "shadow", "impact_type": "sigil",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 180,
        "desc": "3 fast dark thrown weapons, shadow trail, dark sigil mark",
    },
    "gravity_well_shot": {
        "color": [0.2, 0.1, 0.35, 1.0], "glow": [0.45, 0.3, 0.65, 1.0],
        "speed": 10.0, "size": 0.5, "rate": 250, "lifetime": 1.5,
        "trail_type": "distortion", "impact_type": "implode",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 350,
        "desc": "Sphere pulling enemies to impact, spatial distortion",
    },
    "crystal_shard_rain": {
        "color": [0.7, 0.8, 1.0, 1.0], "glow": [0.9, 0.95, 1.0, 1.0],
        "speed": 18.0, "size": 0.18, "rate": 250, "lifetime": 0.6,
        "trail_type": "glint", "impact_type": "refract",
        "homing": False, "pierce": False, "bounce": False, "particle_count": 300,
        "desc": "Crystals from above in cluster, each refracts light",
    },
}

# Trail type -> C# shape/velocity hints
TRAIL_BEHAVIORS: dict[str, dict[str, Any]] = {
    "spiral": {"shape": "Sphere", "angle": 15, "speed_mult": 0.4, "noise_freq": 3.0},
    "flame": {"shape": "Cone", "angle": 8, "speed_mult": 0.5, "noise_freq": 1.5},
    "frost": {"shape": "Cone", "angle": 5, "speed_mult": 0.3, "noise_freq": 0.8},
    "wispy": {"shape": "Cone", "angle": 3, "speed_mult": 0.6, "noise_freq": 2.5},
    "electric": {"shape": "Cone", "angle": 2, "speed_mult": 0.2, "noise_freq": 8.0},
    "bone_dust": {"shape": "Cone", "angle": 10, "speed_mult": 0.3, "noise_freq": 1.0},
    "beam": {"shape": "Cone", "angle": 1, "speed_mult": 0.1, "noise_freq": 0.5},
    "comet": {"shape": "Cone", "angle": 6, "speed_mult": 0.5, "noise_freq": 2.0},
    "spore": {"shape": "Sphere", "angle": 20, "speed_mult": 0.7, "noise_freq": 1.2},
    "drip": {"shape": "Cone", "angle": 12, "speed_mult": 0.6, "noise_freq": 0.5},
    "spirit": {"shape": "Sphere", "angle": 10, "speed_mult": 0.4, "noise_freq": 3.5},
    "tendril": {"shape": "Cone", "angle": 4, "speed_mult": 0.3, "noise_freq": 4.0},
    "distortion": {"shape": "Cone", "angle": 2, "speed_mult": 0.15, "noise_freq": 6.0},
    "glint": {"shape": "Cone", "angle": 3, "speed_mult": 0.3, "noise_freq": 5.0},
    "decay": {"shape": "Sphere", "angle": 15, "speed_mult": 0.5, "noise_freq": 1.5},
    "rainbow": {"shape": "Cone", "angle": 5, "speed_mult": 0.4, "noise_freq": 2.5},
    "ember": {"shape": "Cone", "angle": 8, "speed_mult": 0.5, "noise_freq": 1.8},
    "shadow": {"shape": "Cone", "angle": 3, "speed_mult": 0.2, "noise_freq": 4.5},
}

# Impact type -> C# burst behavior hints
IMPACT_BEHAVIORS: dict[str, dict[str, Any]] = {
    "implode": {"burst_count": 200, "speed_min": -5.0, "speed_max": -1.0, "linger": 1.5},
    "scorch": {"burst_count": 300, "speed_min": 0.5, "speed_max": 3.0, "linger": 3.0},
    "shatter": {"burst_count": 250, "speed_min": 3.0, "speed_max": 8.0, "linger": 1.0},
    "phase": {"burst_count": 150, "speed_min": 1.0, "speed_max": 4.0, "linger": 0.8},
    "arc": {"burst_count": 400, "speed_min": 2.0, "speed_max": 10.0, "linger": 0.5},
    "burst": {"burst_count": 300, "speed_min": 2.0, "speed_max": 6.0, "linger": 1.0},
    "explosion": {"burst_count": 500, "speed_min": 3.0, "speed_max": 10.0, "linger": 2.0},
    "cloud": {"burst_count": 150, "speed_min": 0.5, "speed_max": 2.0, "linger": 5.0},
    "radiance": {"burst_count": 350, "speed_min": 1.0, "speed_max": 5.0, "linger": 2.0},
    "splash": {"burst_count": 250, "speed_min": 1.0, "speed_max": 5.0, "linger": 2.0},
    "scatter": {"burst_count": 300, "speed_min": 4.0, "speed_max": 8.0, "linger": 1.2},
    "field": {"burst_count": 350, "speed_min": 0.5, "speed_max": 3.0, "linger": 3.5},
    "pool": {"burst_count": 200, "speed_min": 0.2, "speed_max": 1.5, "linger": 5.0},
    "delayed_cut": {"burst_count": 100, "speed_min": 0.5, "speed_max": 2.0, "linger": 0.5},
    "wither": {"burst_count": 200, "speed_min": 0.5, "speed_max": 2.5, "linger": 3.0},
    "prismatic": {"burst_count": 400, "speed_min": 2.0, "speed_max": 7.0, "linger": 1.5},
    "sigil": {"burst_count": 150, "speed_min": 0.2, "speed_max": 1.0, "linger": 2.5},
    "grab": {"burst_count": 180, "speed_min": -3.0, "speed_max": -0.5, "linger": 1.8},
    "refract": {"burst_count": 250, "speed_min": 1.0, "speed_max": 4.0, "linger": 1.5},
}


# ---------------------------------------------------------------------------
# Ground/AoE skill configs (30 skills)
# ---------------------------------------------------------------------------

AOE_CONFIGS: dict[str, dict[str, Any]] = {
    "eruption": {
        "color": [1.0, 0.4, 0.05, 1.0], "glow": [1.0, 0.7, 0.2, 1.0],
        "radius": 5.0, "duration": 3.0, "height": 8.0, "linger_time": 4.0,
        "ground_effect": "lava_pool", "height_particles": "column",
        "damage_type": "fire", "rate": 400,
        "desc": "Magma column, lava splatter, lingering fire pool",
    },
    "frozen_domain": {
        "color": [0.5, 0.85, 1.0, 1.0], "glow": [0.75, 0.95, 1.0, 1.0],
        "radius": 10.0, "duration": 5.0, "height": 0.5, "linger_time": 6.0,
        "ground_effect": "ice_floor", "height_particles": "frost_mist",
        "damage_type": "ice", "rate": 300,
        "desc": "Expanding ice floor, 10m frost coverage",
    },
    "corpse_garden": {
        "color": [0.6, 0.08, 0.08, 1.0], "glow": [0.8, 0.15, 0.1, 1.0],
        "radius": 7.0, "duration": 2.5, "height": 4.0, "linger_time": 3.0,
        "ground_effect": "gore_splatter", "height_particles": "visceral_burst",
        "damage_type": "physical", "rate": 500,
        "desc": "Chain corpse detonations, red-black visceral",
    },
    "meteor_strike": {
        "color": [1.0, 0.5, 0.1, 1.0], "glow": [1.0, 0.8, 0.3, 1.0],
        "radius": 8.0, "duration": 1.5, "height": 25.0, "linger_time": 4.0,
        "ground_effect": "crater", "height_particles": "falling_rock",
        "damage_type": "fire", "rate": 600,
        "desc": "Flaming rock from sky, crater, radial shockwave",
    },
    "poison_miasma": {
        "color": [0.3, 0.55, 0.2, 1.0], "glow": [0.45, 0.7, 0.35, 1.0],
        "radius": 7.0, "duration": 6.0, "height": 3.0, "linger_time": 8.0,
        "ground_effect": "toxic_puddle", "height_particles": "rising_gas",
        "damage_type": "poison", "rate": 150,
        "desc": "Expanding green-purple toxic cloud",
    },
    "lightning_field": {
        "color": [0.6, 0.85, 1.0, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "radius": 6.0, "duration": 5.0, "height": 5.0, "linger_time": 5.0,
        "ground_effect": "scorched_earth", "height_particles": "random_bolts",
        "damage_type": "lightning", "rate": 500,
        "desc": "Persistent crackling electricity, random bolts",
    },
    "scarlet_bloom": {
        "color": [0.7, 0.1, 0.15, 1.0], "glow": [0.85, 0.2, 0.25, 1.0],
        "radius": 6.0, "duration": 4.0, "height": 3.5, "linger_time": 6.0,
        "ground_effect": "rot_field", "height_particles": "petal_rise",
        "damage_type": "rot", "rate": 250,
        "desc": "Giant rot flower blooms, lingering DOT field",
    },
    "seismic_shatter": {
        "color": [0.55, 0.4, 0.25, 1.0], "glow": [0.7, 0.55, 0.35, 1.0],
        "radius": 9.0, "duration": 1.0, "height": 3.0, "linger_time": 2.0,
        "ground_effect": "crack_pattern", "height_particles": "rock_launch",
        "damage_type": "physical", "rate": 600,
        "desc": "Star-pattern ground cracks, rocks launch upward",
    },
    "blizzard_zone": {
        "color": [0.7, 0.88, 1.0, 1.0], "glow": [0.9, 0.95, 1.0, 1.0],
        "radius": 10.0, "duration": 8.0, "height": 6.0, "linger_time": 8.0,
        "ground_effect": "snow_cover", "height_particles": "swirling_snow",
        "damage_type": "ice", "rate": 400,
        "desc": "Persistent snowstorm, swirling ice shards",
    },
    "necrotic_ground": {
        "color": [0.2, 0.2, 0.2, 1.0], "glow": [0.35, 0.3, 0.4, 1.0],
        "radius": 7.0, "duration": 5.0, "height": 2.0, "linger_time": 5.0,
        "ground_effect": "dead_zone", "height_particles": "skeletal_hands",
        "damage_type": "necrotic", "rate": 200,
        "desc": "Dead zone, gray-black ground, skeletal hands reaching",
    },
    "blood_pool": {
        "color": [0.6, 0.02, 0.02, 1.0], "glow": [0.8, 0.1, 0.08, 1.0],
        "radius": 5.0, "duration": 6.0, "height": 0.3, "linger_time": 7.0,
        "ground_effect": "blood_spread", "height_particles": "blood_mist",
        "damage_type": "blood", "rate": 180,
        "desc": "Crimson liquid spreading, drains health of those inside",
    },
    "tornado_alley": {
        "color": [0.3, 0.55, 0.3, 1.0], "glow": [0.5, 0.75, 0.5, 1.0],
        "radius": 12.0, "duration": 6.0, "height": 10.0, "linger_time": 6.0,
        "ground_effect": "dust_ring", "height_particles": "cyclone",
        "damage_type": "wind", "rate": 350,
        "desc": "Multiple wandering cyclones, green-tinged wind",
    },
    "holy_ground": {
        "color": [1.0, 0.95, 0.7, 1.0], "glow": [1.0, 1.0, 1.0, 1.0],
        "radius": 6.0, "duration": 5.0, "height": 4.0, "linger_time": 5.0,
        "ground_effect": "golden_circle", "height_particles": "light_pillars",
        "damage_type": "holy", "rate": 250,
        "desc": "Golden light circle, heals allies, damages enemies",
    },
    "shadow_rift": {
        "color": [0.1, 0.05, 0.15, 1.0], "glow": [0.3, 0.15, 0.45, 1.0],
        "radius": 5.0, "duration": 4.0, "height": 6.0, "linger_time": 4.0,
        "ground_effect": "dark_portal", "height_particles": "tentacle_rise",
        "damage_type": "void", "rate": 300,
        "desc": "Dark portal, tentacles pull enemies to center",
    },
    "spore_field": {
        "color": [0.4, 0.6, 0.2, 1.0], "glow": [0.55, 0.75, 0.35, 1.0],
        "radius": 8.0, "duration": 5.0, "height": 2.5, "linger_time": 6.0,
        "ground_effect": "mushroom_grow", "height_particles": "spore_rise",
        "damage_type": "poison", "rate": 200,
        "desc": "Rapid mushroom growths, toxic particles upward",
    },
    "star_rain": {
        "color": [0.5, 0.6, 1.0, 1.0], "glow": [0.8, 0.85, 1.0, 1.0],
        "radius": 12.0, "duration": 3.0, "height": 20.0, "linger_time": 2.0,
        "ground_effect": "impact_marks", "height_particles": "falling_stars",
        "damage_type": "arcane", "rate": 500,
        "desc": "Dozens of energy stars falling across wide area",
    },
    "fire_wall": {
        "color": [1.0, 0.45, 0.1, 1.0], "glow": [1.0, 0.7, 0.2, 1.0],
        "radius": 8.0, "duration": 5.0, "height": 4.0, "linger_time": 5.0,
        "ground_effect": "flame_line", "height_particles": "wall_flames",
        "damage_type": "fire", "rate": 450,
        "desc": "Line of roaring flames, impassable barrier",
    },
    "crystal_prison": {
        "color": [0.7, 0.8, 1.0, 1.0], "glow": [0.9, 0.95, 1.0, 1.0],
        "radius": 4.0, "duration": 4.0, "height": 3.5, "linger_time": 4.0,
        "ground_effect": "crystal_ring", "height_particles": "refraction",
        "damage_type": "arcane", "rate": 250,
        "desc": "Ring of crystals trapping enemies, refracting light",
    },
    "void_implosion": {
        "color": [0.15, 0.08, 0.25, 1.0], "glow": [0.4, 0.25, 0.6, 1.0],
        "radius": 7.0, "duration": 2.0, "height": 7.0, "linger_time": 2.0,
        "ground_effect": "void_crack", "height_particles": "implode_explode",
        "damage_type": "void", "rate": 500,
        "desc": "Area collapses inward then explodes outward",
    },
    "bone_graveyard": {
        "color": [0.85, 0.82, 0.7, 1.0], "glow": [0.95, 0.9, 0.75, 1.0],
        "radius": 6.0, "duration": 2.0, "height": 3.0, "linger_time": 3.0,
        "ground_effect": "bone_eruption", "height_particles": "bone_spikes",
        "damage_type": "necrotic", "rate": 400,
        "desc": "Bone spikes erupt from ground, skeletal energy, stun",
    },
    "corruption_wellspring": {
        "color": [0.3, 0.1, 0.35, 1.0], "glow": [0.5, 0.2, 0.55, 1.0],
        "radius": 5.0, "duration": 4.0, "height": 8.0, "linger_time": 5.0,
        "ground_effect": "corruption_pool", "height_particles": "geyser",
        "damage_type": "corruption", "rate": 350,
        "desc": "Dark geyser, purple-black corruption mist",
    },
    "molten_fissure": {
        "color": [1.0, 0.5, 0.1, 1.0], "glow": [1.0, 0.75, 0.25, 1.0],
        "radius": 8.0, "duration": 3.0, "height": 5.0, "linger_time": 5.0,
        "ground_effect": "magma_crack", "height_particles": "fire_geyser",
        "damage_type": "fire", "rate": 450,
        "desc": "Ground cracks revealing magma, fire geysers erupt",
    },
    "petal_cyclone": {
        "color": [0.95, 0.5, 0.6, 1.0], "glow": [1.0, 0.7, 0.75, 1.0],
        "radius": 7.0, "duration": 4.0, "height": 8.0, "linger_time": 4.0,
        "ground_effect": "petal_carpet", "height_particles": "cyclone",
        "damage_type": "physical", "rate": 400,
        "desc": "Massive flower petal tornado",
    },
    "thunder_storm": {
        "color": [0.4, 0.45, 0.55, 1.0], "glow": [0.8, 0.9, 1.0, 1.0],
        "radius": 12.0, "duration": 6.0, "height": 20.0, "linger_time": 6.0,
        "ground_effect": "scorched_earth", "height_particles": "storm_clouds",
        "damage_type": "lightning", "rate": 500,
        "desc": "Dark clouds, repeated lightning strikes below",
    },
    "spear_rain": {
        "color": [0.8, 0.7, 0.3, 1.0], "glow": [1.0, 0.9, 0.5, 1.0],
        "radius": 10.0, "duration": 3.0, "height": 20.0, "linger_time": 2.5,
        "ground_effect": "impact_marks", "height_particles": "falling_spears",
        "damage_type": "physical", "rate": 500,
        "desc": "Dozens of energy spears from sky like artillery",
    },
    "death_circle": {
        "color": [0.2, 0.05, 0.25, 1.0], "glow": [0.45, 0.15, 0.5, 1.0],
        "radius": 10.0, "duration": 3.0, "height": 2.0, "linger_time": 2.0,
        "ground_effect": "dark_ring_expand", "height_particles": "death_energy",
        "damage_type": "necrotic", "rate": 350,
        "desc": "Expanding dark energy ring, massive edge damage",
    },
    "acid_pool": {
        "color": [0.4, 0.7, 0.1, 1.0], "glow": [0.55, 0.85, 0.2, 1.0],
        "radius": 5.0, "duration": 6.0, "height": 0.5, "linger_time": 8.0,
        "ground_effect": "acid_spread", "height_particles": "bubbles",
        "damage_type": "acid", "rate": 200,
        "desc": "Green corrosive liquid, bubbling, dissolving",
    },
    "ice_geyser": {
        "color": [0.6, 0.9, 1.0, 1.0], "glow": [0.8, 0.95, 1.0, 1.0],
        "radius": 4.0, "duration": 1.5, "height": 10.0, "linger_time": 3.0,
        "ground_effect": "ice_shatter", "height_particles": "crystal_spray",
        "damage_type": "ice", "rate": 500,
        "desc": "Vertical ice eruption, crystalline spray",
    },
    "gravity_sphere": {
        "color": [0.25, 0.15, 0.4, 1.0], "glow": [0.5, 0.35, 0.7, 1.0],
        "radius": 6.0, "duration": 4.0, "height": 6.0, "linger_time": 3.0,
        "ground_effect": "distortion_ring", "height_particles": "floating_debris",
        "damage_type": "void", "rate": 300,
        "desc": "Localized gravity anomaly, debris floats upward",
    },
    "consecrated_ground": {
        "color": [1.0, 0.9, 0.6, 1.0], "glow": [1.0, 1.0, 0.8, 1.0],
        "radius": 6.0, "duration": 6.0, "height": 2.0, "linger_time": 6.0,
        "ground_effect": "rune_circle", "height_particles": "golden_symbols",
        "damage_type": "holy", "rate": 250,
        "desc": "Sacred rune circle, golden rotating symbols",
    },
}


# ---------------------------------------------------------------------------
# Shared C# code fragments
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

    private void ConfigPS(ParticleSystem ps, Color color, float rate, float lifetime,
                          float size, ParticleSystemShapeType shape = ParticleSystemShapeType.Cone,
                          float shapeAngle = 15f, float shapeRadius = 0.5f)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = size;
        var emission = ps.emission;
        emission.enabled = true;
        emission.rateOverTime = rate;
        var sh = ps.shape;
        sh.enabled = true;
        sh.shapeType = shape;
        sh.angle = shapeAngle;
        sh.radius = shapeRadius;
    }

    private void BurstPS(ParticleSystem ps, int count, Color color, float lifetime,
                         float sizeMin, float sizeMax, float speedMin, float speedMax)
    {
        var main = ps.main;
        main.startColor = color;
        main.startLifetime = lifetime;
        main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
        main.startSpeed = new ParticleSystem.MinMaxCurve(speedMin, speedMax);
        var emission = ps.emission;
        emission.enabled = true;
        emission.SetBursts(new ParticleSystem.Burst[] {
            new ParticleSystem.Burst(0f, (short)count)
        });
    }

    private void SetNoise(ParticleSystem ps, float frequency, float strength, int octaves = 2)
    {
        var noise = ps.noise;
        noise.enabled = true;
        noise.frequency = frequency;
        noise.strength = strength;
        noise.octaveCount = octaves;
    }

    private Material GetParticleMaterial()
    {
        if (_particleMat == null)
        {
            var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
            _particleMat = new Material(shader);
            _particleMat.SetFloat("_Surface", 1f); // Transparent
            _particleMat.SetFloat("_Blend", 0f);   // Alpha
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
            _additiveMat.SetFloat("_Surface", 1f); // Transparent
            _additiveMat.SetFloat("_Blend", 1f);   // Additive
            _additiveMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        return _additiveMat;
    }
    private Material _additiveMat;
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

_CS_LIGHT_FLASH = '''
    private void FlashLight(Light light, Vector3 pos, Color color, float intensity,
                            float range, float duration)
    {
        light.transform.position = pos;
        light.color = color;
        light.range = range;
        light.enabled = true;
        PrimeTween.Tween.Custom(light, intensity, 0f, duration: duration,
            onValueChange: (target, val) => target.intensity = val)
            .OnComplete(light, t => t.enabled = false);
    }
'''


# ---------------------------------------------------------------------------
# Python helpers for C# dict generation
# ---------------------------------------------------------------------------

def _fmt_color(rgba: list[float]) -> str:
    """Format RGBA list as C# Color constructor."""
    return f"new Color({rgba[0]}f, {rgba[1]}f, {rgba[2]}f, {rgba[3]}f)"


def _brand_color_dict_cs(var_name: str, color_map: dict[str, list[float]]) -> str:
    """Build C# Dictionary<string, Color> initializer from brand palette."""
    lines = [f"        private static readonly Dictionary<string, Color> {var_name} = new Dictionary<string, Color>"]
    lines.append("        {")
    for brand, rgba in color_map.items():
        lines.append(f'            {{ "{brand}", {_fmt_color(rgba)} }},')
    lines.append("        };")
    return "\n".join(lines)


def _projectile_configs_cs() -> str:
    """Build C# ProjectileConfig dictionary initializer."""
    lines = []
    lines.append("        private static readonly Dictionary<string, ProjectileConfig> ProjectileConfigs = new Dictionary<string, ProjectileConfig>")
    lines.append("        {")
    for name, cfg in PROJECTILE_CONFIGS.items():
        c = cfg["color"]
        g = cfg["glow"]
        tb = TRAIL_BEHAVIORS.get(cfg["trail_type"], TRAIL_BEHAVIORS["spiral"])
        ib = IMPACT_BEHAVIORS.get(cfg["impact_type"], IMPACT_BEHAVIORS["burst"])
        lines.append(f'            {{ "{name}", new ProjectileConfig {{')
        lines.append(f"                color = {_fmt_color(c)},")
        lines.append(f"                glow = {_fmt_color(g)},")
        lines.append(f"                speed = {cfg['speed']}f, size = {cfg['size']}f,")
        lines.append(f"                rate = {cfg['rate']}, lifetime = {cfg['lifetime']}f,")
        lines.append(f'                trailType = "{sanitize_cs_string(cfg["trail_type"])}",')
        lines.append(f'                impactType = "{sanitize_cs_string(cfg["impact_type"])}",')
        lines.append(f"                homing = {str(cfg['homing']).lower()},")
        lines.append(f"                pierce = {str(cfg['pierce']).lower()},")
        lines.append(f"                bounce = {str(cfg['bounce']).lower()},")
        lines.append(f"                particleCount = {cfg['particle_count']},")
        lines.append(f"                trailShapeAngle = {tb['angle']}f,")
        lines.append(f"                trailNoiseFreq = {tb['noise_freq']}f,")
        lines.append(f"                impactBurstCount = {ib['burst_count']},")
        lines.append(f"                impactSpeedMin = {ib['speed_min']}f,")
        lines.append(f"                impactSpeedMax = {ib['speed_max']}f,")
        lines.append(f"                impactLingerTime = {ib['linger']}f,")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


def _aoe_configs_cs() -> str:
    """Build C# AoEConfig dictionary initializer."""
    lines = []
    lines.append("        private static readonly Dictionary<string, AoEConfig> AoEConfigs = new Dictionary<string, AoEConfig>")
    lines.append("        {")
    for name, cfg in AOE_CONFIGS.items():
        c = cfg["color"]
        g = cfg["glow"]
        lines.append(f'            {{ "{name}", new AoEConfig {{')
        lines.append(f"                color = {_fmt_color(c)},")
        lines.append(f"                glow = {_fmt_color(g)},")
        lines.append(f"                radius = {cfg['radius']}f, duration = {cfg['duration']}f,")
        lines.append(f"                height = {cfg['height']}f, lingerTime = {cfg['linger_time']}f,")
        lines.append(f'                groundEffect = "{sanitize_cs_string(cfg["ground_effect"])}",')
        lines.append(f'                heightParticles = "{sanitize_cs_string(cfg["height_particles"])}",')
        lines.append(f'                damageType = "{sanitize_cs_string(cfg["damage_type"])}",')
        lines.append(f"                rate = {cfg['rate']},")
        lines.append(f'                desc = "{sanitize_cs_string(cfg["desc"])}"')
        lines.append("            } },")
    lines.append("        };")
    return "\n".join(lines)


# ===================================================================
# 1. generate_projectile_skill_vfx_script
# ===================================================================


def generate_projectile_skill_vfx_script(skill_name: str = "void_bolt") -> dict[str, Any]:
    """Generate ProjectileSkillVFXController MonoBehaviour with 25 projectile skills.

    Config-driven controller supporting all 25 named projectile types. Each has
    unique color, speed, trail behavior, impact behavior, and optional homing/
    pierce/bounce flags. Brand tinting overlays brand glow on base skill color.

    API: LaunchProjectile(string skillName, string brand, Vector3 origin, Vector3 target)
    Event: OnProjectileHit(string skillName, Vector3 position)

    Args:
        skill_name: Default skill to configure. Defaults to void_bolt.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in PROJECTILE_CONFIGS:
        skill_name = "void_bolt"

    safe_name = sanitize_cs_identifier(skill_name)
    proj_configs_block = _projectile_configs_cs()
    brand_primary_block = _brand_color_dict_cs("BrandPrimaryColors", BRAND_PRIMARY_COLORS)
    brand_glow_block = _brand_color_dict_cs("BrandGlowColors", BRAND_GLOW_COLORS)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Projectile skill VFX controller for VeilBreakers.
/// 25 named projectile skills with config-driven trail/impact behavior.
/// Default: {skill_name}
/// API: LaunchProjectile(skillName, brand, origin, target) -- event OnProjectileHit
/// </summary>
public class ProjectileSkillVFXController : MonoBehaviour
{{
    // ---- Config struct ----
    [System.Serializable]
    public struct ProjectileConfig
    {{
        public Color color;
        public Color glow;
        public float speed;
        public float size;
        public int rate;
        public float lifetime;
        public string trailType;
        public string impactType;
        public bool homing;
        public bool pierce;
        public bool bounce;
        public int particleCount;
        public float trailShapeAngle;
        public float trailNoiseFreq;
        public int impactBurstCount;
        public float impactSpeedMin;
        public float impactSpeedMax;
        public float impactLingerTime;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";
    [SerializeField] private float homingTurnSpeed = 5f;
    [SerializeField] private int multiShotCount = 5;
    [SerializeField] private float spreadAngle = 15f;

    // Events
    public event Action<string, Vector3> OnProjectileHit;

    // Configs
{proj_configs_block}

    // Brand palettes
{brand_primary_block}

{brand_glow_block}

    // Runtime particle systems
    private ParticleSystem corePS;
    private ParticleSystem trailPS;
    private ParticleSystem impactBurstPS;
    private ParticleSystem impactLingerPS;
    private ParticleSystem chargePS;
    private Light projectileLight;
    private Light impactLight;

    private readonly List<Coroutine> activeRoutines = new List<Coroutine>();
{_CS_PARTICLE_HELPER}
{_CS_SCREEN_SHAKE}
{_CS_COROUTINE_DELAY}
{_CS_LIGHT_FLASH}

    private void Awake()
    {{
        InitializeParticleSystems();
    }}

    private void InitializeParticleSystems()
    {{
        var root = transform;
        corePS = CreatePS("ProjCore", root, 500);
        trailPS = CreatePS("ProjTrail", root, 800);
        impactBurstPS = CreatePS("ProjImpactBurst", root, 1000);
        impactLingerPS = CreatePS("ProjImpactLinger", root, 500);
        chargePS = CreatePS("ProjCharge", root, 300);

        // Additive material for trail
        var trailRenderer = trailPS.GetComponent<ParticleSystemRenderer>();
        trailRenderer.material = GetAdditiveMaterial();
        var chargeRenderer = chargePS.GetComponent<ParticleSystemRenderer>();
        chargeRenderer.material = GetAdditiveMaterial();

        // Lights
        var pLightGo = new GameObject("ProjectileLight");
        pLightGo.transform.SetParent(root, false);
        projectileLight = pLightGo.AddComponent<Light>();
        projectileLight.type = LightType.Point;
        projectileLight.intensity = 0f;
        projectileLight.range = 6f;
        projectileLight.enabled = false;

        var iLightGo = new GameObject("ImpactLight");
        iLightGo.transform.SetParent(root, false);
        impactLight = iLightGo.AddComponent<Light>();
        impactLight.type = LightType.Point;
        impactLight.intensity = 0f;
        impactLight.range = 10f;
        impactLight.enabled = false;
    }}

    /// <summary>Launch a named projectile skill with optional brand tinting.</summary>
    public void LaunchProjectile(string skillName, string brand, Vector3 origin, Vector3 target)
    {{
        skillName = skillName.ToLowerInvariant().Replace(" ", "_");
        if (!ProjectileConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[ProjectileVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        var cfg = ProjectileConfigs[skillName];
        Color brandTint = Color.white;
        if (!string.IsNullOrEmpty(brand) && BrandGlowColors.ContainsKey(brand.ToUpperInvariant()))
            brandTint = BrandGlowColors[brand.ToUpperInvariant()];

        // Handle multi-shot skills
        if (skillName == "frost_shard_volley" || skillName == "ember_volley")
        {{
            var co = StartCoroutine(MultiShotSequence(cfg, brandTint, skillName, origin, target));
            activeRoutines.Add(co);
        }}
        else if (skillName == "shadow_kunai")
        {{
            var co = StartCoroutine(RapidShotSequence(cfg, brandTint, skillName, origin, target, 3));
            activeRoutines.Add(co);
        }}
        else if (skillName == "star_barrage")
        {{
            var co = StartCoroutine(RapidShotSequence(cfg, brandTint, skillName, origin, target, 10));
            activeRoutines.Add(co);
        }}
        else if (skillName == "seeking_orbs")
        {{
            var co = StartCoroutine(HomingOrbSequence(cfg, brandTint, skillName, origin, target, 3));
            activeRoutines.Add(co);
        }}
        else if (skillName == "crystal_shard_rain")
        {{
            var co = StartCoroutine(RainSequence(cfg, brandTint, skillName, target));
            activeRoutines.Add(co);
        }}
        else if (skillName == "moonbeam" || skillName == "plasma_lance")
        {{
            var co = StartCoroutine(BeamSequence(cfg, brandTint, skillName, origin, target));
            activeRoutines.Add(co);
        }}
        else
        {{
            var co = StartCoroutine(StandardProjectileSequence(cfg, brandTint, skillName, origin, target));
            activeRoutines.Add(co);
        }}
    }}

    // ---- Standard single projectile ----
    private IEnumerator StandardProjectileSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 origin, Vector3 target)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);
        var dir = (target - origin).normalized;
        var dist = Vector3.Distance(origin, target);

        // Charge-up
        chargePS.transform.position = origin;
        ConfigPS(chargePS, tintedGlow, cfg.rate * 0.4f, 0.4f, cfg.size * 0.5f,
                 ParticleSystemShapeType.Sphere, 360f, cfg.size * 2f);
        var chargeMain = chargePS.main;
        chargeMain.startSpeed = new ParticleSystem.MinMaxCurve(-3f, -1f);
        chargePS.Play();
        yield return new WaitForSeconds(0.25f);
        chargePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        // Core projectile
        var pos = origin;
        corePS.transform.position = pos;
        ConfigPS(corePS, tintedColor, cfg.rate, cfg.lifetime * 0.5f, cfg.size,
                 ParticleSystemShapeType.Sphere, 5f, cfg.size * 0.4f);
        SetNoise(corePS, cfg.trailNoiseFreq * 0.5f, cfg.size * 0.2f);
        corePS.Play();

        // Trail
        trailPS.transform.position = pos;
        ConfigPS(trailPS, tintedGlow * 0.7f, cfg.rate * 0.6f, cfg.lifetime, cfg.size * 0.3f,
                 ParticleSystemShapeType.Cone, cfg.trailShapeAngle, cfg.size * 0.2f);
        SetNoise(trailPS, cfg.trailNoiseFreq, cfg.size * 0.3f);
        trailPS.Play();

        // Light
        projectileLight.color = tintedGlow;
        projectileLight.enabled = true;
        projectileLight.intensity = 3f;

        // Travel
        float travelTime = dist / cfg.speed;
        float elapsed = 0f;
        while (elapsed < travelTime)
        {{
            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / travelTime);

            if (cfg.homing)
            {{
                dir = Vector3.Slerp(dir, (target - pos).normalized, homingTurnSpeed * Time.deltaTime);
            }}

            pos = Vector3.Lerp(origin, target, t);
            // Arc for magma_glob style
            if (cfg.impactType == "pool" || cfg.impactType == "scorch")
                pos.y += Mathf.Sin(t * Mathf.PI) * dist * 0.2f;

            corePS.transform.position = pos;
            trailPS.transform.position = pos;
            projectileLight.transform.position = pos;
            yield return null;
        }}

        corePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        trailPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        projectileLight.enabled = false;

        // Impact
        yield return StartCoroutine(ImpactSequence(cfg, tintedColor, tintedGlow, skillName, target));
    }}

    // ---- Multi-shot fan (frost_shard_volley, ember_volley) ----
    private IEnumerator MultiShotSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 origin, Vector3 target)
    {{
        var baseDir = (target - origin).normalized;
        int count = multiShotCount;
        for (int i = 0; i < count; i++)
        {{
            float angleOffset = Mathf.Lerp(-spreadAngle, spreadAngle,
                count > 1 ? (float)i / (count - 1) : 0.5f);
            var rot = Quaternion.AngleAxis(angleOffset, Vector3.up);
            var shotTarget = origin + rot * baseDir * Vector3.Distance(origin, target);
            StartCoroutine(StandardProjectileSequence(cfg, brandTint, skillName, origin, shotTarget));
            yield return new WaitForSeconds(0.05f);
        }}
    }}

    // ---- Rapid shot sequence (shadow_kunai, star_barrage) ----
    private IEnumerator RapidShotSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 origin, Vector3 target, int count)
    {{
        for (int i = 0; i < count; i++)
        {{
            var jitter = UnityEngine.Random.insideUnitSphere * 1.5f;
            jitter.y *= 0.3f;
            StartCoroutine(StandardProjectileSequence(cfg, brandTint, skillName, origin, target + jitter));
            yield return new WaitForSeconds(0.08f);
        }}
    }}

    // ---- Homing orb sequence (seeking_orbs) ----
    private IEnumerator HomingOrbSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 origin, Vector3 target, int count)
    {{
        for (int i = 0; i < count; i++)
        {{
            var offset = Quaternion.Euler(0f, i * 120f, 0f) * Vector3.right * 1.5f;
            StartCoroutine(StandardProjectileSequence(cfg, brandTint, skillName, origin + offset, target));
            yield return new WaitForSeconds(0.2f);
        }}
    }}

    // ---- Rain from above (crystal_shard_rain) ----
    private IEnumerator RainSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 target)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);
        int shardCount = UnityEngine.Random.Range(8, 15);
        for (int i = 0; i < shardCount; i++)
        {{
            var offset = UnityEngine.Random.insideUnitSphere * 3f;
            offset.y = 0f;
            var dropTarget = target + offset;
            var dropOrigin = dropTarget + Vector3.up * 15f + UnityEngine.Random.insideUnitSphere * 2f;
            StartCoroutine(StandardProjectileSequence(cfg, brandTint, skillName, dropOrigin, dropTarget));
            yield return new WaitForSeconds(UnityEngine.Random.Range(0.03f, 0.1f));
        }}
    }}

    // ---- Beam sequence (moonbeam, plasma_lance) ----
    private IEnumerator BeamSequence(ProjectileConfig cfg, Color brandTint,
        string skillName, Vector3 origin, Vector3 target)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        // Beam particles along line
        int segmentCount = 20;
        for (int i = 0; i < segmentCount; i++)
        {{
            float t = (float)i / segmentCount;
            var pos = Vector3.Lerp(origin, target, t);
            corePS.transform.position = pos;
            BurstPS(corePS, cfg.particleCount / segmentCount, tintedGlow,
                    0.3f, cfg.size * 0.3f, cfg.size, 0.5f, 2f);
            corePS.Play();
        }}

        FlashLight(impactLight, target + Vector3.up, tintedGlow, 5f, 8f, 0.5f);
        DoScreenShake(0.15f, 0.2f);
        yield return new WaitForSeconds(0.3f);

        // Impact at target
        yield return StartCoroutine(ImpactSequence(cfg, tintedColor, tintedGlow, skillName, target));
    }}

    // ---- Shared impact ----
    private IEnumerator ImpactSequence(ProjectileConfig cfg, Color tintedColor, Color tintedGlow,
        string skillName, Vector3 target)
    {{
        // Burst
        impactBurstPS.transform.position = target;
        BurstPS(impactBurstPS, cfg.impactBurstCount, tintedGlow,
                cfg.lifetime, cfg.size * 0.5f, cfg.size * 1.5f,
                cfg.impactSpeedMin, cfg.impactSpeedMax);
        var burstShape = impactBurstPS.shape;
        burstShape.shapeType = ParticleSystemShapeType.Sphere;
        burstShape.radius = cfg.size;
        impactBurstPS.Play();

        // Linger
        impactLingerPS.transform.position = target;
        ConfigPS(impactLingerPS, tintedColor * 0.6f, cfg.rate * 0.3f, cfg.impactLingerTime,
                 cfg.size * 0.4f, ParticleSystemShapeType.Sphere, 180f, cfg.size * 1.5f);
        SetNoise(impactLingerPS, 1.5f, cfg.size * 0.3f);
        impactLingerPS.Play();

        // Light flash
        FlashLight(impactLight, target + Vector3.up * 0.5f, tintedGlow, 4f, 10f, 0.4f);
        DoScreenShake(0.2f, 0.15f);

        // Fire event
        OnProjectileHit?.Invoke(skillName, target);

        yield return new WaitForSeconds(cfg.impactLingerTime);
        impactBurstPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        impactLingerPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    /// <summary>Stop all active projectile routines.</summary>
    public void StopAll()
    {{
        foreach (var co in activeRoutines)
            if (co != null) StopCoroutine(co);
        activeRoutines.Clear();
        corePS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        trailPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        impactBurstPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        impactLingerPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        chargePS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        projectileLight.enabled = false;
        impactLight.enabled = false;
    }}

    /// <summary>Get list of all available projectile skill names.</summary>
    public static List<string> GetAllSkillNames()
    {{
        return new List<string>(ProjectileConfigs.Keys);
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Projectile Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("ProjectileSkillVFXController");
        go.AddComponent<ProjectileSkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("ProjectileSkillVFXController created in scene");
    }}

    private static void WriteResult(string msg)
    {{
        var json = JsonUtility.ToJson(new VBResult {{ success = true, message = msg }});
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }}

    [System.Serializable]
    private class VBResult {{ public bool success; public string message; }}
#endif
}}
'''

    script_path = "Assets/Editor/Generated/VFX/ProjectileSkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }


# ===================================================================
# 2. generate_ground_aoe_skill_vfx_script
# ===================================================================


def generate_ground_aoe_skill_vfx_script(skill_name: str = "eruption") -> dict[str, Any]:
    """Generate GroundAoESkillVFXController MonoBehaviour with 30 ground/AoE skills.

    Config-driven controller supporting all 30 named ground/AoE types. Each has
    unique radius, duration, ground effect, height particles, linger time, and
    damage type. Brand tinting overlays brand glow on base skill color.

    API: TriggerGroundAoE(string skillName, string brand, Vector3 center, float radius)
    Event: OnAoETriggered(string skillName, Vector3 center, float radius)

    Args:
        skill_name: Default skill to configure. Defaults to eruption.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    skill_name = skill_name.lower().replace(" ", "_")
    if skill_name not in AOE_CONFIGS:
        skill_name = "eruption"

    safe_name = sanitize_cs_identifier(skill_name)
    aoe_configs_block = _aoe_configs_cs()
    brand_primary_block = _brand_color_dict_cs("BrandPrimaryColors", BRAND_PRIMARY_COLORS)
    brand_glow_block = _brand_color_dict_cs("BrandGlowColors", BRAND_GLOW_COLORS)

    script = f'''using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Ground/AoE skill VFX controller for VeilBreakers.
/// 30 named ground/AoE skills with config-driven ground effect and height particles.
/// Default: {skill_name}
/// API: TriggerGroundAoE(skillName, brand, center, radius) -- event OnAoETriggered
/// </summary>
public class GroundAoESkillVFXController : MonoBehaviour
{{
    // ---- Config struct ----
    [System.Serializable]
    public struct AoEConfig
    {{
        public Color color;
        public Color glow;
        public float radius;
        public float duration;
        public float height;
        public float lingerTime;
        public string groundEffect;
        public string heightParticles;
        public string damageType;
        public int rate;
        public string desc;
    }}

    [Header("Defaults")]
    [SerializeField] private string defaultSkill = "{skill_name}";
    [SerializeField] private float radiusOverrideMult = 1f;

    // Events
    public event Action<string, Vector3, float> OnAoETriggered;

    // Configs
{aoe_configs_block}

    // Brand palettes
{brand_primary_block}

{brand_glow_block}

    // Runtime particle systems
    private ParticleSystem groundPS;
    private ParticleSystem groundEdgePS;
    private ParticleSystem heightPS;
    private ParticleSystem burstPS;
    private ParticleSystem lingerPS;
    private ParticleSystem debrisPS;
    private Light aoeLight;

    private readonly List<Coroutine> activeRoutines = new List<Coroutine>();
{_CS_PARTICLE_HELPER}
{_CS_SCREEN_SHAKE}
{_CS_COROUTINE_DELAY}
{_CS_LIGHT_FLASH}

    private void Awake()
    {{
        InitializeParticleSystems();
    }}

    private void InitializeParticleSystems()
    {{
        var root = transform;
        groundPS = CreatePS("AoEGround", root, 800);
        groundEdgePS = CreatePS("AoEGroundEdge", root, 500);
        heightPS = CreatePS("AoEHeight", root, 600);
        burstPS = CreatePS("AoEBurst", root, 1000);
        lingerPS = CreatePS("AoELinger", root, 500);
        debrisPS = CreatePS("AoEDebris", root, 400);

        // Additive materials for glow effects
        var heightRenderer = heightPS.GetComponent<ParticleSystemRenderer>();
        heightRenderer.material = GetAdditiveMaterial();
        var edgeRenderer = groundEdgePS.GetComponent<ParticleSystemRenderer>();
        edgeRenderer.material = GetAdditiveMaterial();

        // Light
        var lightGo = new GameObject("AoELight");
        lightGo.transform.SetParent(root, false);
        aoeLight = lightGo.AddComponent<Light>();
        aoeLight.type = LightType.Point;
        aoeLight.intensity = 0f;
        aoeLight.range = 12f;
        aoeLight.enabled = false;
    }}

    /// <summary>Trigger a named ground/AoE skill with optional brand tinting.</summary>
    public void TriggerGroundAoE(string skillName, string brand, Vector3 center, float radius)
    {{
        skillName = skillName.ToLowerInvariant().Replace(" ", "_");
        if (!AoEConfigs.ContainsKey(skillName))
        {{
            Debug.LogWarning($"[AoEVFX] Unknown skill: {{skillName}}, using {skill_name}");
            skillName = "{skill_name}";
        }}
        var cfg = AoEConfigs[skillName];
        float finalRadius = (radius > 0f ? radius : cfg.radius) * radiusOverrideMult;

        Color brandTint = Color.white;
        if (!string.IsNullOrEmpty(brand) && BrandGlowColors.ContainsKey(brand.ToUpperInvariant()))
            brandTint = BrandGlowColors[brand.ToUpperInvariant()];

        // Dispatch based on ground effect type for specialized sequences
        if (skillName == "meteor_strike")
        {{
            var co = StartCoroutine(MeteorSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else if (skillName == "fire_wall")
        {{
            var co = StartCoroutine(WallSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else if (skillName == "void_implosion")
        {{
            var co = StartCoroutine(ImplosionSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else if (skillName == "death_circle")
        {{
            var co = StartCoroutine(ExpandingRingSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else if (skillName == "tornado_alley" || skillName == "petal_cyclone")
        {{
            var co = StartCoroutine(CycloneSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else if (skillName == "star_rain" || skillName == "spear_rain" || skillName == "thunder_storm")
        {{
            var co = StartCoroutine(FallingSequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
        else
        {{
            var co = StartCoroutine(StandardAoESequence(cfg, brandTint, skillName, center, finalRadius));
            activeRoutines.Add(co);
        }}
    }}

    // ---- Standard ground AoE ----
    private IEnumerator StandardAoESequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Initial burst
        burstPS.transform.position = center;
        BurstPS(burstPS, Mathf.Min(cfg.rate * 2, 1000), tintedGlow,
                0.6f, cfg.height * 0.05f, cfg.height * 0.15f, 2f, 8f);
        var burstShape = burstPS.shape;
        burstShape.shapeType = ParticleSystemShapeType.Circle;
        burstShape.radius = radius * 0.5f;
        burstPS.Play();
        DoScreenShake(0.25f, 0.2f);

        // Ground particles (circle fill)
        groundPS.transform.position = center;
        ConfigPS(groundPS, tintedColor, cfg.rate, cfg.duration * 0.8f, radius * 0.08f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        var groundMain = groundPS.main;
        groundMain.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.5f);
        var groundVel = groundPS.velocityOverLifetime;
        groundVel.enabled = true;
        groundVel.y = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);
        SetNoise(groundPS, 1.5f, radius * 0.05f);
        groundPS.Play();

        // Ground edge ring
        groundEdgePS.transform.position = center;
        ConfigPS(groundEdgePS, tintedGlow, cfg.rate * 0.4f, cfg.duration, radius * 0.05f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        var edgeMain = groundEdgePS.main;
        edgeMain.startSpeed = 0f;
        groundEdgePS.Play();

        // Height particles (column / mist / rising)
        heightPS.transform.position = center;
        ConfigPS(heightPS, tintedGlow * 0.8f, cfg.rate * 0.5f, cfg.duration * 0.6f, radius * 0.06f,
                 ParticleSystemShapeType.Circle, 0f, radius * 0.7f);
        var heightMain = heightPS.main;
        heightMain.startSpeed = new ParticleSystem.MinMaxCurve(1f, cfg.height * 0.5f);
        var heightVel = heightPS.velocityOverLifetime;
        heightVel.enabled = true;
        heightVel.y = new ParticleSystem.MinMaxCurve(cfg.height * 0.3f, cfg.height * 0.8f);
        SetNoise(heightPS, 2f, radius * 0.1f, 3);
        heightPS.Play();

        // Debris
        debrisPS.transform.position = center;
        BurstPS(debrisPS, 50, tintedColor * 0.5f, cfg.duration * 0.5f,
                0.05f, 0.15f, 1f, 5f);
        var debrisShape = debrisPS.shape;
        debrisShape.shapeType = ParticleSystemShapeType.Circle;
        debrisShape.radius = radius * 0.8f;
        debrisPS.Play();

        // AoE light
        FlashLight(aoeLight, center + Vector3.up * 2f, tintedGlow, 5f, radius * 2f, cfg.duration * 0.7f);

        // Wait for main duration
        yield return new WaitForSeconds(cfg.duration);

        groundPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        groundEdgePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        // Linger phase
        if (cfg.lingerTime > 0f)
        {{
            lingerPS.transform.position = center;
            ConfigPS(lingerPS, tintedColor * 0.5f, cfg.rate * 0.2f, cfg.lingerTime * 0.7f,
                     radius * 0.06f, ParticleSystemShapeType.Circle, 0f, radius);
            var lingerMain = lingerPS.main;
            lingerMain.startSpeed = new ParticleSystem.MinMaxCurve(0.05f, 0.3f);
            SetNoise(lingerPS, 1f, radius * 0.03f);
            lingerPS.Play();
            yield return new WaitForSeconds(cfg.lingerTime);
            lingerPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }}
    }}

    // ---- Meteor strike (falling rock from above) ----
    private IEnumerator MeteorSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Warning circle on ground
        groundEdgePS.transform.position = center;
        ConfigPS(groundEdgePS, tintedGlow * 0.5f, 100f, 1.5f, 0.1f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        groundEdgePS.Play();
        yield return new WaitForSeconds(0.8f);

        // Meteor descending
        var startPos = center + Vector3.up * cfg.height;
        heightPS.transform.position = startPos;
        ConfigPS(heightPS, tintedColor, cfg.rate, 0.3f, radius * 0.3f,
                 ParticleSystemShapeType.Sphere, 0f, radius * 0.2f);
        heightPS.Play();

        float fallTime = 0.5f;
        float elapsed = 0f;
        while (elapsed < fallTime)
        {{
            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / fallTime);
            t = t * t; // Accelerate
            heightPS.transform.position = Vector3.Lerp(startPos, center, t);
            yield return null;
        }}
        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        groundEdgePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        // Impact explosion
        burstPS.transform.position = center;
        BurstPS(burstPS, 800, tintedGlow, 1.0f, 0.1f, 0.5f, 5f, 15f);
        var burstShape = burstPS.shape;
        burstShape.shapeType = ParticleSystemShapeType.Sphere;
        burstShape.radius = 0.5f;
        burstPS.Play();
        DoScreenShake(0.5f, 0.4f);
        FlashLight(aoeLight, center + Vector3.up, tintedGlow, 8f, radius * 3f, 0.6f);

        // Debris shower
        debrisPS.transform.position = center;
        BurstPS(debrisPS, 200, tintedColor * 0.6f, 1.5f, 0.05f, 0.2f, 3f, 10f);
        debrisPS.Play();

        // Crater linger
        yield return new WaitForSeconds(0.5f);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Fire wall (line of flames) ----
    private IEnumerator WallSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Spread flames along a line
        int segments = 10;
        Vector3 lineDir = transform.forward;
        float halfLen = radius;

        for (int i = 0; i < segments; i++)
        {{
            float t = (float)i / (segments - 1);
            var pos = center + lineDir * Mathf.Lerp(-halfLen, halfLen, t);

            groundPS.transform.position = pos;
            BurstPS(groundPS, cfg.rate / segments, tintedColor, cfg.duration,
                    0.3f, 0.8f, 0.5f, 2f);
            groundPS.Play();
            yield return new WaitForSeconds(0.05f);
        }}

        // Sustained wall
        heightPS.transform.position = center;
        ConfigPS(heightPS, tintedGlow, cfg.rate, cfg.duration * 0.8f, 0.4f,
                 ParticleSystemShapeType.Box, 0f, 1f);
        var heightShape = heightPS.shape;
        heightShape.scale = new Vector3(radius * 2f, 0.5f, 0.5f);
        var heightMain = heightPS.main;
        heightMain.startSpeed = new ParticleSystem.MinMaxCurve(1f, cfg.height);
        SetNoise(heightPS, 2f, 0.3f);
        heightPS.Play();

        FlashLight(aoeLight, center + Vector3.up * 2f, tintedGlow, 4f, radius * 2f, cfg.duration);

        yield return new WaitForSeconds(cfg.duration);
        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Void implosion (inward collapse then outward explosion) ----
    private IEnumerator ImplosionSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Phase 1: Implosion (particles rush inward)
        groundPS.transform.position = center;
        ConfigPS(groundPS, tintedColor, cfg.rate, 0.8f, radius * 0.05f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        var groundMain = groundPS.main;
        groundMain.startSpeed = new ParticleSystem.MinMaxCurve(-8f, -3f);
        groundPS.Play();

        heightPS.transform.position = center;
        ConfigPS(heightPS, tintedGlow * 0.6f, cfg.rate * 0.5f, 0.8f, 0.15f,
                 ParticleSystemShapeType.Sphere, 0f, radius);
        var heightMain = heightPS.main;
        heightMain.startSpeed = new ParticleSystem.MinMaxCurve(-6f, -2f);
        heightPS.Play();

        yield return new WaitForSeconds(1.0f);
        groundPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);

        // Phase 2: Explosion outward
        burstPS.transform.position = center;
        BurstPS(burstPS, 800, tintedGlow, 1.0f, 0.1f, 0.4f, 5f, 15f);
        burstPS.Play();
        DoScreenShake(0.5f, 0.3f);
        FlashLight(aoeLight, center + Vector3.up, tintedGlow, 8f, radius * 2.5f, 0.5f);

        yield return new WaitForSeconds(0.5f);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Expanding ring (death_circle) ----
    private IEnumerator ExpandingRingSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        float expandTime = cfg.duration;
        float elapsed = 0f;
        float currentRadius = 0.5f;

        groundEdgePS.transform.position = center;
        ConfigPS(groundEdgePS, tintedGlow, cfg.rate, 0.5f, 0.15f,
                 ParticleSystemShapeType.Circle, 0f, currentRadius);
        groundEdgePS.Play();

        while (elapsed < expandTime)
        {{
            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / expandTime);
            currentRadius = Mathf.Lerp(0.5f, radius, t);
            var shape = groundEdgePS.shape;
            shape.radius = currentRadius;

            // Edge glow pulsing
            var main = groundEdgePS.main;
            float pulse = 0.7f + 0.3f * Mathf.Sin(elapsed * 8f);
            main.startColor = tintedGlow * pulse;
            yield return null;
        }}

        groundEdgePS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        // Final edge burst
        burstPS.transform.position = center;
        BurstPS(burstPS, 500, tintedGlow, 0.8f, 0.05f, 0.2f, 3f, 8f);
        var burstShape = burstPS.shape;
        burstShape.shapeType = ParticleSystemShapeType.Circle;
        burstShape.radius = radius;
        burstPS.Play();
        DoScreenShake(0.3f, 0.2f);

        yield return new WaitForSeconds(0.5f);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Cyclone (tornado_alley, petal_cyclone) ----
    private IEnumerator CycloneSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Spawn multiple cyclone points
        int cycloneCount = 3;
        var cyclonePositions = new Vector3[cycloneCount];
        for (int i = 0; i < cycloneCount; i++)
        {{
            float angle = (360f / cycloneCount) * i;
            var offset = Quaternion.Euler(0f, angle, 0f) * Vector3.forward * radius * 0.5f;
            cyclonePositions[i] = center + offset;
        }}

        heightPS.transform.position = center;
        ConfigPS(heightPS, tintedColor, cfg.rate, cfg.duration * 0.7f, 0.2f,
                 ParticleSystemShapeType.Circle, 0f, radius * 0.3f);
        var heightMain = heightPS.main;
        heightMain.startSpeed = new ParticleSystem.MinMaxCurve(2f, cfg.height * 0.6f);
        SetNoise(heightPS, 4f, radius * 0.15f, 3);
        var heightVel = heightPS.velocityOverLifetime;
        heightVel.enabled = true;
        heightVel.orbitalY = new ParticleSystem.MinMaxCurve(3f, 6f);
        heightPS.Play();

        groundPS.transform.position = center;
        ConfigPS(groundPS, tintedGlow * 0.5f, cfg.rate * 0.3f, cfg.duration, 0.1f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        groundPS.Play();

        FlashLight(aoeLight, center + Vector3.up * 3f, tintedGlow, 3f, radius * 2f, cfg.duration);

        // Animate cyclone positions
        float elapsed = 0f;
        while (elapsed < cfg.duration)
        {{
            elapsed += Time.deltaTime;
            float rotAngle = elapsed * 45f;
            for (int i = 0; i < cycloneCount; i++)
            {{
                float baseAngle = (360f / cycloneCount) * i + rotAngle;
                var offset = Quaternion.Euler(0f, baseAngle, 0f) * Vector3.forward * radius * 0.4f;
                cyclonePositions[i] = center + offset;
            }}
            // Move height PS through cyclone positions
            int idx = Mathf.FloorToInt(elapsed * 2f) % cycloneCount;
            heightPS.transform.position = cyclonePositions[idx];
            yield return null;
        }}

        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        groundPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Falling sequence (star_rain, spear_rain, thunder_storm) ----
    private IEnumerator FallingSequence(AoEConfig cfg, Color brandTint,
        string skillName, Vector3 center, float radius)
    {{
        var tintedColor = Color.Lerp(cfg.color, brandTint, 0.3f);
        var tintedGlow = Color.Lerp(cfg.glow, brandTint, 0.3f);

        OnAoETriggered?.Invoke(skillName, center, radius);

        // Overhead cloud / dark area
        heightPS.transform.position = center + Vector3.up * cfg.height;
        ConfigPS(heightPS, tintedColor * 0.4f, cfg.rate * 0.3f, cfg.duration, radius * 0.1f,
                 ParticleSystemShapeType.Circle, 0f, radius);
        var heightMain = heightPS.main;
        heightMain.startSpeed = 0.2f;
        SetNoise(heightPS, 1f, radius * 0.05f);
        heightPS.Play();

        // Individual impacts
        int totalStrikes = Mathf.CeilToInt(cfg.duration * 8f);
        float interval = cfg.duration / totalStrikes;
        for (int i = 0; i < totalStrikes; i++)
        {{
            var offset = UnityEngine.Random.insideUnitSphere * radius;
            offset.y = 0f;
            var strikePos = center + offset;

            burstPS.transform.position = strikePos;
            BurstPS(burstPS, 50, tintedGlow, 0.4f, 0.05f, 0.15f, 1f, 5f);
            burstPS.Play();

            // Small ground mark
            groundPS.transform.position = strikePos;
            BurstPS(groundPS, 20, tintedColor * 0.6f, 1.0f, 0.02f, 0.08f, 0.5f, 2f);
            groundPS.Play();

            if (i % 5 == 0)
                FlashLight(aoeLight, strikePos + Vector3.up, tintedGlow, 4f, radius, 0.2f);
            if (i % 3 == 0)
                DoScreenShake(0.1f, 0.1f);

            yield return new WaitForSeconds(interval);
        }}

        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        yield return StartCoroutine(LingerPhase(cfg, tintedColor, center, radius));
    }}

    // ---- Shared linger phase ----
    private IEnumerator LingerPhase(AoEConfig cfg, Color tintedColor, Vector3 center, float radius)
    {{
        if (cfg.lingerTime <= 0f) yield break;

        lingerPS.transform.position = center;
        ConfigPS(lingerPS, tintedColor * 0.4f, cfg.rate * 0.15f, cfg.lingerTime * 0.6f,
                 radius * 0.04f, ParticleSystemShapeType.Circle, 0f, radius);
        var lingerMain = lingerPS.main;
        lingerMain.startSpeed = new ParticleSystem.MinMaxCurve(0.05f, 0.2f);
        SetNoise(lingerPS, 0.8f, radius * 0.02f);
        lingerPS.Play();

        yield return new WaitForSeconds(cfg.lingerTime);
        lingerPS.Stop(true, ParticleSystemStopBehavior.StopEmitting);
    }}

    /// <summary>Stop all active AoE routines.</summary>
    public void StopAll()
    {{
        foreach (var co in activeRoutines)
            if (co != null) StopCoroutine(co);
        activeRoutines.Clear();
        groundPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        groundEdgePS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        heightPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        burstPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        lingerPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        debrisPS.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        aoeLight.enabled = false;
    }}

    /// <summary>Get list of all available AoE skill names.</summary>
    public static List<string> GetAllSkillNames()
    {{
        return new List<string>(AoEConfigs.Keys);
    }}

#if UNITY_EDITOR
    [MenuItem("VeilBreakers/VFX/Ground AoE Skill VFX Controller")]
    private static void CreateInScene()
    {{
        var go = new GameObject("GroundAoESkillVFXController");
        go.AddComponent<GroundAoESkillVFXController>();
        Selection.activeGameObject = go;
        EditorUtility.SetDirty(go);
        WriteResult("GroundAoESkillVFXController created in scene");
    }}

    private static void WriteResult(string msg)
    {{
        var json = JsonUtility.ToJson(new VBResult {{ success = true, message = msg }});
        System.IO.File.WriteAllText(
            System.IO.Path.Combine(Application.dataPath, "../Temp/vb_result.json"), json);
    }}

    [System.Serializable]
    private class VBResult {{ public bool success; public string message; }}
#endif
}}
'''

    script_path = "Assets/Editor/Generated/VFX/GroundAoESkillVFXController.cs"
    return {
        "script_path": script_path,
        "script_content": script,
        "next_steps": STANDARD_NEXT_STEPS,
    }
