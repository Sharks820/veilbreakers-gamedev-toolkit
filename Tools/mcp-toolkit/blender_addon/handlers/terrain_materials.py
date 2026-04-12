"""Terrain biome material system with per-biome palettes.

Builds on the procedural_materials.py MATERIAL_LIBRARY to provide:
  - BIOME_PALETTES: 14 named biome definitions mapping terrain zones to materials
  - TERRAIN_MATERIALS: Additional terrain-specific materials not in MATERIAL_LIBRARY
  - Pure-logic slope/height analysis functions (no bpy dependency)
  - Vertex color splatmap blending (R=grass, G=rock, B=dirt, A=special)
  - Corruption tint overlay system
  - Biome transition zone blending (compute_biome_transition)

Biomes: thornwood_forest, corrupted_swamp, mountain_pass, ruined_fortress,
        abandoned_village, veil_crack_zone, cemetery, battlefield,
        desert, coastal, grasslands, mushroom_forest, crystal_cavern,
        deep_forest

All colors follow VeilBreakers dark fantasy palette rules:
  - Environment saturation NEVER exceeds 40%
  - Value range for environments: 10-50% (dark world)
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]

from .procedural_materials import (
    GENERATORS,
    MATERIAL_LIBRARY,
    _add_node,
    _get_bsdf_input,
)
from ._terrain_noise import compute_slope_map

# ---------------------------------------------------------------------------
# V2 bridge — unified weight computation (kills the split-brain)
# ---------------------------------------------------------------------------
from .terrain_materials_v2 import (
    MaterialChannel,
    MaterialRuleSet,
    compute_slope_material_weights,
    default_dark_fantasy_rules,
    _smoothstep_band,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default biome -- used when biome param is missing or unknown
# ---------------------------------------------------------------------------

DEFAULT_BIOME = "thornwood_forest"


def get_default_biome() -> str:
    """Return the default biome name for terrain without explicit biome."""
    return DEFAULT_BIOME


# ---------------------------------------------------------------------------
# Required palette keys -- every biome must define these terrain zones
# ---------------------------------------------------------------------------

REQUIRED_PALETTE_KEYS = frozenset({"ground", "slopes", "cliffs", "water_edges"})


# ---------------------------------------------------------------------------
# Terrain-specific materials not in the base MATERIAL_LIBRARY
# ---------------------------------------------------------------------------
# Same format: base_color, roughness, roughness_variation, metallic,
#   normal_strength, detail_scale, wear_intensity, node_recipe

TERRAIN_MATERIALS: dict[str, dict[str, Any]] = {
    # -- Thornwood Forest --
    "dark_leaf_litter": {
        "base_color": (0.07, 0.06, 0.04, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 10.0,
        "wear_intensity": 0.15,
        "node_recipe": "terrain",
    },
    "exposed_roots": {
        "base_color": (0.10, 0.08, 0.05, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 5.0,
        "wear_intensity": 0.30,
        "node_recipe": "wood",
    },
    "forest_soil": {
        "base_color": (0.09, 0.07, 0.05, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 8.0,
        "wear_intensity": 0.20,
        "node_recipe": "terrain",
    },
    "mossy_rock": {
        "base_color": (0.10, 0.12, 0.07, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 6.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "fern_patches": {
        "base_color": (0.06, 0.08, 0.05, 1.0),
        "roughness": 0.75,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 14.0,
        "wear_intensity": 0.05,
        "node_recipe": "organic",
    },
    "gray_stone_vine": {
        "base_color": (0.13, 0.12, 0.10, 1.0),
        "roughness": 0.86,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.6,
        "detail_scale": 5.0,
        "wear_intensity": 0.40,
        "node_recipe": "stone",
    },
    "reeds": {
        "base_color": (0.12, 0.11, 0.07, 1.0),
        "roughness": 0.78,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 12.0,
        "wear_intensity": 0.10,
        "node_recipe": "organic",
    },

    # -- Corrupted Swamp --
    "black_mud": {
        "base_color": (0.04, 0.03, 0.03, 1.0),
        "roughness": 0.45,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 0.7,
        "detail_scale": 6.0,
        "wear_intensity": 0.35,
        "node_recipe": "terrain",
    },
    "toxic_pool": {
        "base_color": (0.06, 0.07, 0.04, 1.0),
        "roughness": 0.15,
        "roughness_variation": 0.05,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 4.0,
        "wear_intensity": 0.10,
        "node_recipe": "terrain",
    },
    "slick_dark_rock": {
        "base_color": (0.06, 0.05, 0.05, 1.0),
        "roughness": 0.35,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 7.0,
        "wear_intensity": 0.30,
        "node_recipe": "stone",
    },
    "slime_trail": {
        "base_color": (0.06, 0.07, 0.04, 1.0),
        "roughness": 0.10,
        "roughness_variation": 0.05,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 8.0,
        "wear_intensity": 0.15,
        "node_recipe": "organic",
    },
    "corroded_stone_purple": {
        "base_color": (0.10, 0.06, 0.11, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 6.0,
        "wear_intensity": 0.50,
        "node_recipe": "stone",
    },
    "murky_green": {
        "base_color": (0.04, 0.06, 0.03, 1.0),
        "roughness": 0.12,
        "roughness_variation": 0.04,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },

    # -- Mountain Pass --
    "gravel": {
        "base_color": (0.18, 0.17, 0.15, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 14.0,
        "wear_intensity": 0.20,
        "node_recipe": "terrain",
    },
    "sparse_grass": {
        "base_color": (0.08, 0.10, 0.05, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 12.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "snow_patches": {
        "base_color": (0.42, 0.42, 0.45, 1.0),
        "roughness": 0.68,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 10.0,
        "wear_intensity": 0.02,
        "node_recipe": "terrain",
    },
    "exposed_rock": {
        "base_color": (0.16, 0.14, 0.12, 1.0),
        "roughness": 0.86,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 5.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "ice": {
        "base_color": (0.30, 0.38, 0.48, 1.0),
        "roughness": 0.08,
        "roughness_variation": 0.04,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 8.0,
        "wear_intensity": 0.02,
        "node_recipe": "stone",
    },
    "layered_sedimentary": {
        "base_color": (0.17, 0.15, 0.12, 1.0),
        "roughness": 0.84,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 4.0,
        "wear_intensity": 0.30,
        "node_recipe": "stone",
    },
    "frozen_edge": {
        "base_color": (0.35, 0.40, 0.50, 1.0),
        "roughness": 0.12,
        "roughness_variation": 0.06,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 6.0,
        "wear_intensity": 0.03,
        "node_recipe": "terrain",
    },

    # -- Ruined Fortress --
    "broken_cobblestone": {
        "base_color": (0.14, 0.12, 0.10, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.6,
        "detail_scale": 6.0,
        "wear_intensity": 0.55,
        "node_recipe": "stone",
    },
    "rubble_dirt": {
        "base_color": (0.13, 0.10, 0.07, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 0.9,
        "detail_scale": 7.0,
        "wear_intensity": 0.40,
        "node_recipe": "terrain",
    },
    "crumbling_wall_foundation": {
        "base_color": (0.15, 0.13, 0.11, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 1.8,
        "detail_scale": 5.0,
        "wear_intensity": 0.65,
        "node_recipe": "stone",
    },
    "damaged_stone": {
        "base_color": (0.12, 0.11, 0.09, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.7,
        "detail_scale": 5.0,
        "wear_intensity": 0.50,
        "node_recipe": "stone",
    },
    "stagnant_water": {
        "base_color": (0.04, 0.05, 0.04, 1.0),
        "roughness": 0.08,
        "roughness_variation": 0.03,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 3.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },

    # -- Abandoned Village --
    "dirt_paths": {
        "base_color": (0.14, 0.11, 0.07, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 8.0,
        "wear_intensity": 0.25,
        "node_recipe": "terrain",
    },
    "overgrown_grass": {
        "base_color": (0.07, 0.10, 0.06, 1.0),
        "roughness": 0.84,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 14.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "rotten_wood_base": {
        "base_color": (0.08, 0.06, 0.04, 1.0),
        "roughness": 0.94,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 5.0,
        "wear_intensity": 0.70,
        "node_recipe": "wood",
    },
    "exposed_earth": {
        "base_color": (0.13, 0.10, 0.07, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 0.7,
        "detail_scale": 7.0,
        "wear_intensity": 0.25,
        "node_recipe": "terrain",
    },
    "dried_mud": {
        "base_color": (0.16, 0.12, 0.08, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.30,
        "node_recipe": "terrain",
    },

    # -- Veil Crack Zone --
    "fractured_earth_glow": {
        "base_color": (0.10, 0.07, 0.12, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 1.6,
        "detail_scale": 5.0,
        "wear_intensity": 0.50,
        "node_recipe": "terrain",
    },
    "void_touched_stone": {
        "base_color": (0.08, 0.06, 0.10, 1.0),
        "roughness": 0.75,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.3,
        "detail_scale": 6.0,
        "wear_intensity": 0.45,
        "node_recipe": "stone",
    },
    "crystal_surface": {
        "base_color": (0.14, 0.10, 0.18, 1.0),
        "roughness": 0.15,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 10.0,
        "wear_intensity": 0.10,
        "node_recipe": "stone",
    },
    "reality_torn_rock": {
        "base_color": (0.06, 0.04, 0.08, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.22,
        "metallic": 0.0,
        "normal_strength": 2.0,
        "detail_scale": 4.0,
        "wear_intensity": 0.60,
        "node_recipe": "stone",
    },
    "void_energy_pool": {
        "base_color": (0.09, 0.06, 0.12, 1.0),
        "roughness": 0.05,
        "roughness_variation": 0.03,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 3.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },

    # -- Cemetery --
    "dark_soil": {
        "base_color": (0.06, 0.05, 0.04, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 8.0,
        "wear_intensity": 0.20,
        "node_recipe": "terrain",
    },
    "dead_grass": {
        "base_color": (0.12, 0.10, 0.06, 1.0),
        "roughness": 0.86,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 12.0,
        "wear_intensity": 0.15,
        "node_recipe": "terrain",
    },
    "fog_ground": {
        "base_color": (0.18, 0.17, 0.16, 1.0),
        "roughness": 0.70,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.2,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },
    "worn_stone_path": {
        "base_color": (0.15, 0.14, 0.12, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 6.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "old_masonry": {
        "base_color": (0.14, 0.13, 0.11, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 5.0,
        "wear_intensity": 0.45,
        "node_recipe": "stone",
    },
    "bog_edge": {
        "base_color": (0.06, 0.05, 0.03, 1.0),
        "roughness": 0.40,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 5.0,
        "wear_intensity": 0.20,
        "node_recipe": "terrain",
    },

    # -- Battlefield --
    "churned_mud": {
        "base_color": (0.08, 0.06, 0.04, 1.0),
        "roughness": 0.55,
        "roughness_variation": 0.22,
        "metallic": 0.0,
        "normal_strength": 0.9,
        "detail_scale": 6.0,
        "wear_intensity": 0.40,
        "node_recipe": "terrain",
    },
    "bloodstained_earth": {
        "base_color": (0.12, 0.07, 0.06, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 0.7,
        "detail_scale": 7.0,
        "wear_intensity": 0.35,
        "node_recipe": "terrain",
    },
    "scorched_ground": {
        "base_color": (0.05, 0.04, 0.03, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 6.0,
        "wear_intensity": 0.55,
        "node_recipe": "terrain",
    },
    "shattered_rock": {
        "base_color": (0.13, 0.12, 0.10, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.8,
        "detail_scale": 4.0,
        "wear_intensity": 0.60,
        "node_recipe": "stone",
    },
    "polluted_water": {
        "base_color": (0.05, 0.04, 0.03, 1.0),
        "roughness": 0.10,
        "roughness_variation": 0.04,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 3.0,
        "wear_intensity": 0.10,
        "node_recipe": "terrain",
    },

    # -- Desert/Arid --
    "sand": {
        "base_color": (0.22, 0.18, 0.12, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 12.0,
        "wear_intensity": 0.10,
        "node_recipe": "terrain",
    },
    "cracked_clay": {
        "base_color": (0.18, 0.14, 0.09, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 6.0,
        "wear_intensity": 0.40,
        "node_recipe": "terrain",
    },
    "sandstone": {
        "base_color": (0.20, 0.16, 0.10, 1.0),
        "roughness": 0.86,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 5.0,
        "wear_intensity": 0.30,
        "node_recipe": "stone",
    },
    "exposed_rock_warm": {
        "base_color": (0.19, 0.15, 0.11, 1.0),
        "roughness": 0.84,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 5.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "layered_sandstone": {
        "base_color": (0.21, 0.17, 0.11, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.6,
        "detail_scale": 4.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "salt_flat": {
        "base_color": (0.30, 0.28, 0.25, 1.0),
        "roughness": 0.75,
        "roughness_variation": 0.06,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 10.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },

    # -- Coastal/Maritime --
    "wet_sand": {
        "base_color": (0.16, 0.14, 0.10, 1.0),
        "roughness": 0.45,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 10.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "beach_pebbles": {
        "base_color": (0.18, 0.16, 0.14, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 14.0,
        "wear_intensity": 0.15,
        "node_recipe": "terrain",
    },
    "sea_weathered_rock": {
        "base_color": (0.14, 0.13, 0.12, 1.0),
        "roughness": 0.70,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.3,
        "detail_scale": 6.0,
        "wear_intensity": 0.45,
        "node_recipe": "stone",
    },
    "coastal_grass": {
        "base_color": (0.08, 0.10, 0.06, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 12.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "sea_cliff_stone": {
        "base_color": (0.12, 0.11, 0.10, 1.0),
        "roughness": 0.78,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 5.0,
        "wear_intensity": 0.50,
        "node_recipe": "stone",
    },
    "tidal_pool": {
        "base_color": (0.06, 0.08, 0.10, 1.0),
        "roughness": 0.12,
        "roughness_variation": 0.04,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },
    "sea_foam_edge": {
        "base_color": (0.22, 0.22, 0.24, 1.0),
        "roughness": 0.30,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.2,
        "detail_scale": 8.0,
        "wear_intensity": 0.03,
        "node_recipe": "terrain",
    },

    # -- Grasslands/Plains --
    "tall_grass_ground": {
        "base_color": (0.08, 0.10, 0.05, 1.0),
        "roughness": 0.84,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 14.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "wildflower_soil": {
        "base_color": (0.10, 0.09, 0.06, 1.0),
        "roughness": 0.86,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 10.0,
        "wear_intensity": 0.12,
        "node_recipe": "terrain",
    },
    "grass_covered_rock": {
        "base_color": (0.10, 0.11, 0.07, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.25,
        "node_recipe": "stone",
    },
    "exposed_earth_green": {
        "base_color": (0.12, 0.10, 0.07, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 0.8,
        "detail_scale": 7.0,
        "wear_intensity": 0.30,
        "node_recipe": "terrain",
    },
    "riverbank_grass": {
        "base_color": (0.06, 0.08, 0.04, 1.0),
        "roughness": 0.78,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 12.0,
        "wear_intensity": 0.06,
        "node_recipe": "terrain",
    },

    # -- Mushroom Forest --
    "mycelium_soil": {
        "base_color": (0.10, 0.08, 0.12, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 8.0,
        "wear_intensity": 0.20,
        "node_recipe": "organic",
    },
    "spore_dust": {
        "base_color": (0.12, 0.10, 0.14, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 10.0,
        "wear_intensity": 0.10,
        "node_recipe": "terrain",
    },
    "fungal_rock": {
        "base_color": (0.11, 0.09, 0.13, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 6.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
    },
    "bioluminescent_stone": {
        "base_color": (0.08, 0.06, 0.12, 1.0),
        "roughness": 0.72,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 5.0,
        "wear_intensity": 0.30,
        "node_recipe": "stone",
    },
    "luminous_pool_edge": {
        "base_color": (0.07, 0.08, 0.14, 1.0),
        "roughness": 0.18,
        "roughness_variation": 0.06,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
    },

    # -- Crystal Cavern --
    "geode_floor": {
        "base_color": (0.12, 0.10, 0.14, 1.0),
        "roughness": 0.75,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.8,
        "detail_scale": 8.0,
        "wear_intensity": 0.20,
        "node_recipe": "stone",
    },
    "crystal_dust": {
        "base_color": (0.18, 0.16, 0.22, 1.0),
        "roughness": 0.60,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 12.0,
        "wear_intensity": 0.08,
        "node_recipe": "terrain",
    },
    "prismatic_rock": {
        "base_color": (0.14, 0.12, 0.18, 1.0),
        "roughness": 0.40,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.25,
        "node_recipe": "stone",
    },
    "crystal_wall": {
        "base_color": (0.16, 0.14, 0.22, 1.0),
        "roughness": 0.15,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 10.0,
        "wear_intensity": 0.10,
        "node_recipe": "stone",
    },
    "mineral_pool": {
        "base_color": (0.10, 0.12, 0.18, 1.0),
        "roughness": 0.08,
        "roughness_variation": 0.04,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 4.0,
        "wear_intensity": 0.03,
        "node_recipe": "terrain",
    },

    # -- Deep Ancient Forest --
    "thick_leaf_litter": {
        "base_color": (0.06, 0.05, 0.03, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 0.7,
        "detail_scale": 8.0,
        "wear_intensity": 0.18,
        "node_recipe": "terrain",
    },
    "ancient_root_soil": {
        "base_color": (0.08, 0.06, 0.04, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.9,
        "detail_scale": 6.0,
        "wear_intensity": 0.28,
        "node_recipe": "wood",
    },
    "moss_blanket_rock": {
        "base_color": (0.08, 0.10, 0.06, 1.0),
        "roughness": 0.78,
        "roughness_variation": 0.14,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.30,
        "node_recipe": "stone",
    },
    "root_covered_cliff": {
        "base_color": (0.09, 0.07, 0.05, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.16,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 5.0,
        "wear_intensity": 0.40,
        "node_recipe": "stone",
    },
    "forest_stream_bed": {
        "base_color": (0.07, 0.06, 0.05, 1.0),
        "roughness": 0.35,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 8.0,
        "wear_intensity": 0.12,
        "node_recipe": "terrain",
    },
}


# ---------------------------------------------------------------------------
# Biome Palettes -- 8 named biomes mapping terrain zones to material keys
# ---------------------------------------------------------------------------

BIOME_PALETTES: dict[str, dict[str, list[str]]] = {
    "thornwood_forest": {
        "ground": ["dark_leaf_litter", "exposed_roots", "forest_soil"],
        "slopes": ["mossy_rock", "fern_patches"],
        "cliffs": ["gray_stone_vine"],
        "water_edges": ["mud", "reeds"],
    },
    "corrupted_swamp": {
        "ground": ["black_mud", "toxic_pool"],
        "slopes": ["slick_dark_rock", "slime_trail"],
        "cliffs": ["corroded_stone_purple"],
        "water_edges": ["murky_green"],
    },
    "mountain_pass": {
        "ground": ["gravel", "sparse_grass", "snow_patches"],
        "slopes": ["exposed_rock", "ice"],
        "cliffs": ["layered_sedimentary"],
        "water_edges": ["frozen_edge"],
    },
    "mountain_pass_summer": {
        "ground": ["gravel", "sparse_grass"],
        "slopes": ["exposed_rock", "mossy_rock"],
        "cliffs": ["layered_sedimentary"],
        "water_edges": ["riverbank_grass"],
    },
    "mountain_pass_winter": {
        "ground": ["gravel", "sparse_grass", "snow_patches"],
        "slopes": ["exposed_rock", "ice"],
        "cliffs": ["layered_sedimentary"],
        "water_edges": ["frozen_edge"],
    },
    "ruined_fortress": {
        "ground": ["broken_cobblestone", "rubble_dirt"],
        "slopes": ["crumbling_wall_foundation", "moss"],
        "cliffs": ["damaged_stone"],
        "water_edges": ["stagnant_water"],
    },
    "abandoned_village": {
        "ground": ["dirt_paths", "overgrown_grass"],
        "slopes": ["rotten_wood_base"],
        "cliffs": ["exposed_earth"],
        "water_edges": ["dried_mud"],
    },
    "veil_crack_zone": {
        "ground": ["fractured_earth_glow", "void_touched_stone"],
        "slopes": ["crystal_surface"],
        "cliffs": ["reality_torn_rock"],
        "water_edges": ["void_energy_pool"],
    },
    "cemetery": {
        "ground": ["dark_soil", "dead_grass", "fog_ground"],
        "slopes": ["worn_stone_path"],
        "cliffs": ["old_masonry"],
        "water_edges": ["bog_edge"],
    },
    "battlefield": {
        "ground": ["churned_mud", "bloodstained_earth"],
        "slopes": ["scorched_ground"],
        "cliffs": ["shattered_rock"],
        "water_edges": ["polluted_water"],
    },
    "desert": {
        "ground": ["sand", "cracked_clay"],
        "slopes": ["sandstone", "exposed_rock_warm"],
        "cliffs": ["layered_sandstone"],
        "water_edges": ["dried_mud", "salt_flat"],
    },
    "coastal": {
        "ground": ["wet_sand", "beach_pebbles"],
        "slopes": ["sea_weathered_rock", "coastal_grass"],
        "cliffs": ["sea_cliff_stone"],
        "water_edges": ["tidal_pool", "sea_foam_edge"],
    },
    "grasslands": {
        "ground": ["tall_grass_ground", "wildflower_soil"],
        "slopes": ["grass_covered_rock"],
        "cliffs": ["exposed_earth_green"],
        "water_edges": ["riverbank_grass"],
    },
    "mushroom_forest": {
        "ground": ["mycelium_soil", "spore_dust"],
        "slopes": ["fungal_rock"],
        "cliffs": ["bioluminescent_stone"],
        "water_edges": ["luminous_pool_edge"],
    },
    "crystal_cavern": {
        "ground": ["geode_floor", "crystal_dust"],
        "slopes": ["prismatic_rock"],
        "cliffs": ["crystal_wall"],
        "water_edges": ["mineral_pool"],
    },
    "deep_forest": {
        "ground": ["thick_leaf_litter", "ancient_root_soil"],
        "slopes": ["moss_blanket_rock"],
        "cliffs": ["root_covered_cliff"],
        "water_edges": ["forest_stream_bed"],
    },
}


# ---------------------------------------------------------------------------
# Combined material lookup -- check TERRAIN_MATERIALS first, then MATERIAL_LIBRARY
# ---------------------------------------------------------------------------

def _get_material_def(key: str) -> dict[str, Any] | None:
    """Look up a material definition from TERRAIN_MATERIALS or MATERIAL_LIBRARY."""
    return TERRAIN_MATERIALS.get(key) or MATERIAL_LIBRARY.get(key)


def get_all_terrain_material_keys() -> set[str]:
    """Return all material keys referenced by any biome palette."""
    keys: set[str] = set()
    for palette in BIOME_PALETTES.values():
        for mat_list in palette.values():
            keys.update(mat_list)
    return keys


# ---------------------------------------------------------------------------
# Pure-logic: get_biome_palette
# ---------------------------------------------------------------------------

def get_biome_palette(biome_name: str) -> dict[str, list[str]]:
    """Return the palette dict for a named biome.

    Args:
        biome_name: One of the 8 biome names (e.g. "thornwood_forest").

    Returns:
        Dict mapping zone names ("ground", "slopes", "cliffs", "water_edges")
        to lists of material keys.

    Raises:
        ValueError: If biome_name is not recognized.
    """
    palette = BIOME_PALETTES.get(biome_name)
    if palette is None:
        available = sorted(BIOME_PALETTES.keys())
        raise ValueError(
            f"Unknown biome '{biome_name}'. Available: {available}"
        )
    return palette


# ---------------------------------------------------------------------------
# Pure-logic: slope classification
# ---------------------------------------------------------------------------

_FLAT_MAX_ANGLE = 30.0     # degrees -- 0-30 is ground
_SLOPE_MAX_ANGLE = 60.0    # degrees -- 30-60 is slope
# 60-90 is cliff


def _face_slope_angle(normal: tuple[float, float, float]) -> float:
    """Compute the slope angle (degrees) of a face from its normal.

    A perfectly flat horizontal face has normal (0,0,1) -> angle 0.
    A vertical cliff face has normal (1,0,0) -> angle 90.

    Args:
        normal: Face normal as (nx, ny, nz).

    Returns:
        Slope angle in degrees [0, 180].
    """
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-9:
        return 0.0
    cos_angle = abs(nz) / length
    # Clamp for floating-point safety
    cos_angle = max(0.0, min(1.0, cos_angle))
    return math.degrees(math.acos(cos_angle))


def _classify_face(
    normal: tuple[float, float, float],
    face_center_z: float,
    water_level: float,
) -> str:
    """Classify a face into a terrain zone based on slope and height.

    Uses smoothstep-based weight computation (via v2 engine) and returns
    the dominant zone. The underlying weights are continuous, but this
    function returns the zone with the highest weight for legacy callers
    that need a single category.

    Args:
        normal: Face normal as (nx, ny, nz).
        face_center_z: Average Z height of the face's vertices.
        water_level: Z height of the water surface.

    Returns:
        One of "ground", "slopes", "cliffs", or "water_edges".
    """
    # Water edge check takes priority
    if face_center_z < water_level + 0.5:
        return "water_edges"

    angle = _face_slope_angle(normal)
    if angle <= _FLAT_MAX_ANGLE:
        return "ground"
    elif angle <= _SLOPE_MAX_ANGLE:
        return "slopes"
    else:
        return "cliffs"


def assign_terrain_materials_by_slope(
    mesh_data: dict[str, Any],
    biome_name: str,
) -> list[int]:
    """Assign material indices to faces based on slope angle and height.

    Pure-logic function -- no bpy dependency.

    Args:
        mesh_data: Dict with:
            - "vertices": list of (x, y, z) vertex positions
            - "faces": list of vertex index tuples
            - "normals": list of (nx, ny, nz) face normals (one per face)
            - "water_level": float (optional, default 0.0)
        biome_name: Name of the biome to use for material assignment.

    Returns:
        List of material indices, one per face. The index maps into the
        combined material list built from the palette zones in order:
        [ground..., slopes..., cliffs..., water_edges...].
    """
    vertices = mesh_data.get("vertices", [])
    faces = mesh_data.get("faces", [])
    normals = mesh_data.get("normals", [])
    water_level = mesh_data.get("water_level", 0.0)

    palette = get_biome_palette(biome_name)

    # Build ordered material list and zone-to-index-range mapping
    # Order: ground, slopes, cliffs, water_edges
    zone_order = ["ground", "slopes", "cliffs", "water_edges"]
    mat_list: list[str] = []
    zone_start: dict[str, int] = {}
    for zone in zone_order:
        zone_start[zone] = len(mat_list)
        mat_list.extend(palette[zone])

    if not faces or not normals:
        return []

    material_indices: list[int] = []
    for fi, face in enumerate(faces):
        normal = normals[fi] if fi < len(normals) else (0.0, 0.0, 1.0)

        # Compute face center Z
        if face and vertices:
            z_values = [
                vertices[vi][2]
                for vi in face
                if vi < len(vertices)
            ]
            face_center_z = sum(z_values) / len(z_values) if z_values else 0.0
        else:
            face_center_z = 0.0

        zone = _classify_face(normal, face_center_z, water_level)

        # Pick material within the zone (cycle through available materials)
        zone_materials = palette[zone]
        zone_idx = zone_start[zone]
        # Distribute faces across materials in the zone by face index
        mat_offset = fi % len(zone_materials)
        material_indices.append(zone_idx + mat_offset)

    return material_indices


# ---------------------------------------------------------------------------
# Pure-logic: vertex color splatmap blending
# ---------------------------------------------------------------------------

def blend_terrain_vertex_colors(
    mesh_data: dict[str, Any],
    biome_name: str,
) -> list[tuple[float, float, float, float]]:
    """Paint vertex colors for splatmap blending using 4-channel approach.

    Channel mapping:
        R = grass/vegetation weight
        G = rock/stone weight
        B = dirt/soil weight
        A = special (corruption, snow, water, etc.)

    Each vertex gets weights based on its terrain zone classification.
    The weights are normalized so R+G+B+A = 1.0.

    Pure-logic function -- no bpy dependency.

    Args:
        mesh_data: Dict with:
            - "vertices": list of (x, y, z) vertex positions
            - "faces": list of vertex index tuples
            - "normals": list of (nx, ny, nz) face normals (one per face)
            - "water_level": float (optional, default 0.0)
        biome_name: Name of the biome to use.

    Returns:
        List of (R, G, B, A) tuples, one per vertex. Values in [0, 1].
    """
    vertices = mesh_data.get("vertices", [])
    faces = mesh_data.get("faces", [])
    normals = mesh_data.get("normals", [])
    water_level = mesh_data.get("water_level", 0.0)

    if not vertices:
        return []

    # Ensure palette is valid
    get_biome_palette(biome_name)

    num_verts = len(vertices)

    # Build vertex-to-face adjacency
    vert_faces: list[list[int]] = [[] for _ in range(num_verts)]
    for fi, face in enumerate(faces):
        for vi in face:
            if 0 <= vi < num_verts:
                vert_faces[vi].append(fi)

    # Zone-to-splatmap-channel weights
    # Each zone contributes different channel weights
    zone_weights: dict[str, tuple[float, float, float, float]] = {
        "ground": (0.6, 0.0, 0.4, 0.0),     # Mostly grass + some dirt
        "slopes": (0.1, 0.6, 0.2, 0.1),      # Mostly rock + some dirt
        "cliffs": (0.0, 0.9, 0.0, 0.1),      # Almost all rock
        "water_edges": (0.1, 0.0, 0.3, 0.6), # Mostly special + dirt
    }

    vertex_colors: list[tuple[float, float, float, float]] = []

    for vi in range(num_verts):
        adj = vert_faces[vi]
        if not adj:
            # Isolated vertex -- default to dirt
            vertex_colors.append((0.0, 0.0, 1.0, 0.0))
            continue

        # Average zone weights across adjacent faces
        r_sum, g_sum, b_sum, a_sum = 0.0, 0.0, 0.0, 0.0
        for fi in adj:
            normal = normals[fi] if fi < len(normals) else (0.0, 0.0, 1.0)
            # Compute face center Z for this face
            face = faces[fi] if fi < len(faces) else ()
            if face:
                z_values = [
                    vertices[fvi][2]
                    for fvi in face
                    if fvi < len(vertices)
                ]
                face_z = sum(z_values) / len(z_values) if z_values else 0.0
            else:
                face_z = 0.0

            zone = _classify_face(normal, face_z, water_level)
            w = zone_weights[zone]
            r_sum += w[0]
            g_sum += w[1]
            b_sum += w[2]
            a_sum += w[3]

        # Normalize
        total = r_sum + g_sum + b_sum + a_sum
        if total > 1e-9:
            r_sum /= total
            g_sum /= total
            b_sum /= total
            a_sum /= total
        else:
            r_sum, g_sum, b_sum, a_sum = 0.0, 0.0, 1.0, 0.0

        vertex_colors.append((r_sum, g_sum, b_sum, a_sum))

    return vertex_colors


# ---------------------------------------------------------------------------
# Pure-logic: corruption tint overlay
# ---------------------------------------------------------------------------

# Corruption purple in linear sRGB
_CORRUPTION_R = 0.12
_CORRUPTION_G = 0.04
_CORRUPTION_B = 0.14


def apply_corruption_tint(
    vertex_colors: list[tuple[float, float, float, float]],
    corruption_level: float,
) -> list[tuple[float, float, float, float]]:
    """Overlay purple corruption tint on existing vertex colors.

    Higher corruption_level pushes the A (special) channel toward 1.0
    and tints R/G/B toward corruption purple.

    Pure-logic function -- no bpy dependency.

    Args:
        vertex_colors: List of (R, G, B, A) vertex color tuples.
        corruption_level: Float in [0, 1]. 0 = no corruption, 1 = fully corrupted.

    Returns:
        New list of (R, G, B, A) tuples with corruption applied.
    """
    corruption_level = max(0.0, min(1.0, corruption_level))

    if corruption_level < 1e-6:
        return list(vertex_colors)

    result: list[tuple[float, float, float, float]] = []
    for r, g, b, a in vertex_colors:
        # Lerp RGB channels toward corruption purple
        new_r = r * (1.0 - corruption_level) + _CORRUPTION_R * corruption_level
        new_g = g * (1.0 - corruption_level) + _CORRUPTION_G * corruption_level
        new_b = b * (1.0 - corruption_level) + _CORRUPTION_B * corruption_level

        # Push A channel toward 1.0 (special/corruption mask)
        new_a = a + (1.0 - a) * corruption_level

        result.append((new_r, new_g, new_b, new_a))

    return result


# ---------------------------------------------------------------------------
# Pure-logic: biome transition zone blending
# ---------------------------------------------------------------------------

def _simple_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """Deterministic pseudo-noise for transition edge irregularity.

    Uses a hash-based approach (no external dependency) to produce values
    in [-1, 1] that vary smoothly with position. Not true Perlin noise
    but sufficient for organic-looking biome boundaries.

    Pure-logic function -- no bpy dependency.
    """
    # Integer grid corners
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy

    # Smooth interpolation (Hermite)
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)

    def _hash(xi: int, yi: int) -> float:
        # Simple hash producing a float in [-1, 1]
        h = ((xi * 374761393 + yi * 668265263 + seed * 1274126177) ^ 0x5DEECE66D) & 0x7FFFFFFF
        return (h % 10000) / 5000.0 - 1.0

    n00 = _hash(ix, iy)
    n10 = _hash(ix + 1, iy)
    n01 = _hash(ix, iy + 1)
    n11 = _hash(ix + 1, iy + 1)

    nx0 = n00 * (1.0 - ux) + n10 * ux
    nx1 = n01 * (1.0 - ux) + n11 * ux

    return nx0 * (1.0 - uy) + nx1 * uy


def compute_biome_transition(
    vertices: list[tuple[float, float, float]],
    face_normals: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    biome_a: str,
    biome_b: str,
    transition_width: float = 20.0,
    boundary_axis: str = "x",
    boundary_position: float = 0.0,
    noise_scale: float = 0.1,
    noise_amplitude: float = 5.0,
    noise_seed: int = 42,
) -> list[tuple[float, float, float, float]]:
    """Compute per-vertex splatmap weights for a transition zone between two biomes.

    Produces blended RGBA weights where:
    - Near biome_a (before boundary): weights from biome_a's terrain layers
    - Near biome_b (past boundary): weights from biome_b's terrain layers
    - In transition zone: smooth blend between both, with noise-based
      edge for organic (not straight line) transition

    The transition is computed along a single axis. Noise displaces the
    boundary position per-vertex to create an organic, non-linear edge.

    Pure-logic function -- no bpy dependency.

    Parameters
    ----------
    vertices : list of (x, y, z)
        Mesh vertex positions.
    face_normals : list of (nx, ny, nz)
        Per-face normals (one per face in ``faces``).
    faces : list of index tuples
        Face index lists.
    biome_a : str
        Name of the first biome (near negative side of axis).
    biome_b : str
        Name of the second biome (near positive side of axis).
    transition_width : float
        Width of the blending zone in world units (default 20.0).
    boundary_axis : str
        Axis along which the boundary runs: "x" or "y" (default "x").
    boundary_position : float
        Position along the axis where the boundary center is (default 0.0).
    noise_scale : float
        Scale of the noise function (smaller = larger features). Default 0.1.
    noise_amplitude : float
        Maximum displacement of the boundary in world units. Default 5.0.
    noise_seed : int
        Seed for the noise function. Default 42.

    Returns
    -------
    list of (R, G, B, A)
        Per-vertex splatmap weights blended between the two biomes.
        Values are normalised so R + G + B + A = 1.0.

    Raises
    ------
    ValueError
        If biome_a or biome_b is not found in BIOME_PALETTES_V2,
        or if boundary_axis is not "x" or "y".
    """
    if biome_a not in BIOME_PALETTES_V2:
        raise ValueError(
            f"Unknown biome_a '{biome_a}'. "
            f"Available: {sorted(BIOME_PALETTES_V2.keys())}"
        )
    if biome_b not in BIOME_PALETTES_V2:
        raise ValueError(
            f"Unknown biome_b '{biome_b}'. "
            f"Available: {sorted(BIOME_PALETTES_V2.keys())}"
        )
    if boundary_axis not in ("x", "y"):
        raise ValueError(
            f"boundary_axis must be 'x' or 'y', got '{boundary_axis}'"
        )

    if not vertices:
        return []

    # Get terrain layer weights for each biome
    weights_a = auto_assign_terrain_layers(
        vertices, face_normals, faces, biome_a,
    )
    weights_b = auto_assign_terrain_layers(
        vertices, face_normals, faces, biome_b,
    )

    half_width = max(transition_width / 2.0, 0.001)

    result: list[tuple[float, float, float, float]] = []

    for vi, (vx, vy, vz) in enumerate(vertices):
        # Position along boundary axis
        if boundary_axis == "x":
            pos = vx
            # Noise input from the perpendicular axis
            noise_x = vy * noise_scale
            noise_y = vz * noise_scale
        else:
            pos = vy
            noise_x = vx * noise_scale
            noise_y = vz * noise_scale

        # Noise-displaced boundary
        noise_val = _simple_noise_2d(noise_x, noise_y, seed=noise_seed)
        displaced_boundary = boundary_position + noise_val * noise_amplitude

        # Compute blend factor: 0 = fully biome_a, 1 = fully biome_b
        dist_from_boundary = pos - displaced_boundary
        t = (dist_from_boundary + half_width) / (2.0 * half_width)
        t = max(0.0, min(1.0, t))

        # Smooth step for nicer transitions
        t = t * t * (3.0 - 2.0 * t)

        # Blend weights
        wa = weights_a[vi]
        wb = weights_b[vi]

        r = wa[0] * (1.0 - t) + wb[0] * t
        g = wa[1] * (1.0 - t) + wb[1] * t
        b = wa[2] * (1.0 - t) + wb[2] * t
        a = wa[3] * (1.0 - t) + wb[3] * t

        # Normalise (should already be ~1.0 but ensure precision)
        total = r + g + b + a
        if total > 1e-9:
            r /= total
            g /= total
            b /= total
            a /= total
        else:
            r, g, b, a = 0.0, 0.0, 1.0, 0.0

        result.append((
            max(0.0, min(1.0, r)),
            max(0.0, min(1.0, g)),
            max(0.0, min(1.0, b)),
            max(0.0, min(1.0, a)),
        ))

    return result


# ---------------------------------------------------------------------------
# Height-Based Terrain Texture Blending (AAA quality)
# ---------------------------------------------------------------------------

def height_blend(
    height_a: float,
    height_b: float,
    mask: float,
    blend_contrast: float = 0.5,
    height_offset: float = 0.0,
) -> float:
    """Compute height-based terrain texture blend weight.

    Instead of simple linear interpolation, this function uses per-texel
    height data to create physically-motivated blending: grass fills cracks
    in rock, snow sits on peaks, dirt accumulates in valleys.

    Pure-logic function -- no bpy dependency.

    Args:
        height_a: Height value for layer A (e.g. from height map).
        height_b: Height value for layer B.
        mask: Blend mask (0.0 = layer A, 1.0 = layer B).
        blend_contrast: Controls sharpness of height transition (0.0-1.0).
            Higher values = sharper, more physical blending. Default 0.5.
        height_offset: Bias toward one layer. Positive favors A, negative
            favors B. Default 0.0.

    Returns:
        Blend factor in [0.0, 1.0]. 0.0 = use layer A, 1.0 = use layer B.
    """
    # Scale contrast to useful range (0.0-1.0 maps to 1x-20x multiplier)
    contrast = 1.0 + max(0.0, min(1.0, blend_contrast)) * 19.0

    # Height difference drives blend direction
    height_diff = (height_a - height_b + height_offset) * contrast + 0.5

    # Apply mask influence
    result = height_diff * mask

    # Clamp to valid range
    return max(0.0, min(1.0, result))


def _create_height_blend_group(name: str = "HeightBlend") -> Any:
    """Create a Blender node group implementing height-based texture blending.

    Creates a reusable node group with:
        Inputs:
          - Height_A (float): Height value from texture A
          - Height_B (float): Height value from texture B
          - Mask (float): Blend mask (0=A, 1=B)
          - Blend_Contrast (float): Transition sharpness
        Outputs:
          - Result (float): Blended weight

    Logic: result = clamp((Height_A - Height_B) * Blend_Contrast + 0.5) * Mask

    This makes grass fill cracks in rock, snow sit on peaks, dirt in valleys.

    Args:
        name: Name for the node group. Default "HeightBlend".

    Returns:
        The created bpy.types.NodeGroup.

    Raises:
        RuntimeError: If bpy is not available.
    """
    if bpy is None:
        raise RuntimeError("_create_height_blend_group requires bpy.")

    # Reuse if already exists
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing

    group = bpy.data.node_groups.new(name, "ShaderNodeTree")

    # -- Group Inputs --
    group_in = group.nodes.new("NodeGroupInput")
    group_in.location = (-600, 0)

    # Create input sockets (Blender 4.0+ interface API)
    def _new_input(name: str, socket_type: str = "NodeSocketFloat", **kwargs):
        if hasattr(group, "interface"):
            item = group.interface.new_socket(name=name, in_out='INPUT', socket_type=socket_type)
            for k, v in kwargs.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            return item
        else:  # Blender < 4.0 fallback
            sock = group.inputs.new(socket_type, name)
            for k, v in kwargs.items():
                if hasattr(sock, k):
                    setattr(sock, k, v)
            return sock

    _new_input("Height_A", default_value=0.5)
    _new_input("Height_B", default_value=0.5)
    _new_input("Mask", default_value=0.5, min_value=0.0, max_value=1.0)
    _new_input("Blend_Contrast", default_value=0.5, min_value=0.0, max_value=1.0)

    # -- Group Outputs --
    group_out = group.nodes.new("NodeGroupOutput")
    group_out.location = (400, 0)
    if hasattr(group, "interface"):
        group.interface.new_socket(name="Result", in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:  # Blender < 4.0 fallback
        group.outputs.new("NodeSocketFloat", "Result")

    # -- Math: Height_A - Height_B --
    subtract = group.nodes.new("ShaderNodeMath")
    subtract.operation = "SUBTRACT"
    subtract.location = (-400, 100)
    subtract.label = "Height Diff"
    group.links.new(group_in.outputs["Height_A"], subtract.inputs[0])
    group.links.new(group_in.outputs["Height_B"], subtract.inputs[1])

    # -- Math: * Blend_Contrast (scaled to 1-20 range via multiply_add) --
    # First scale contrast: contrast * 19 + 1
    scale_contrast = group.nodes.new("ShaderNodeMath")
    scale_contrast.operation = "MULTIPLY_ADD"
    scale_contrast.location = (-400, -100)
    scale_contrast.label = "Scale Contrast"
    scale_contrast.inputs[1].default_value = 19.0  # multiplier
    scale_contrast.inputs[2].default_value = 1.0   # offset
    group.links.new(group_in.outputs["Blend_Contrast"], scale_contrast.inputs[0])

    # -- Math: diff * scaled_contrast --
    multiply = group.nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    multiply.location = (-200, 50)
    multiply.label = "Contrast Apply"
    group.links.new(subtract.outputs["Value"], multiply.inputs[0])
    group.links.new(scale_contrast.outputs["Value"], multiply.inputs[1])

    # -- Math: + 0.5 (center the blend) --
    add_half = group.nodes.new("ShaderNodeMath")
    add_half.operation = "ADD"
    add_half.location = (0, 50)
    add_half.label = "Center Blend"
    add_half.inputs[1].default_value = 0.5
    group.links.new(multiply.outputs["Value"], add_half.inputs[0])

    # -- Clamp (0..1) --
    clamp_node = group.nodes.new("ShaderNodeClamp")
    clamp_node.location = (100, 50)
    clamp_node.label = "Clamp 0-1"
    group.links.new(add_half.outputs["Value"], clamp_node.inputs["Value"])

    # -- Math: * Mask --
    mask_mult = group.nodes.new("ShaderNodeMath")
    mask_mult.operation = "MULTIPLY"
    mask_mult.location = (200, 0)
    mask_mult.label = "Apply Mask"
    group.links.new(clamp_node.outputs["Result"], mask_mult.inputs[0])
    group.links.new(group_in.outputs["Mask"], mask_mult.inputs[1])

    # Connect to output
    group.links.new(mask_mult.outputs["Value"], group_out.inputs["Result"])

    return group


# ---------------------------------------------------------------------------
# Blender handler: handle_setup_terrain_biome
# ---------------------------------------------------------------------------

def handle_setup_terrain_biome(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for terrain biome material setup.

    Combines slope-based material assignment, vertex color splatmap
    painting, and optional corruption tint.

    Params:
        object_name (str): Name of the terrain mesh object in Blender.
        biome_name (str): One of the 8 biome palette names.
        corruption_level (float): Optional, 0-1. Default 0.0.
        water_level (float): Optional Z height for water. Default 0.0.
        list_biomes (bool): If True, just return available biome names.

    Returns:
        dict with status, assigned materials, vertex color stats.
    """
    # List mode
    if params.get("list_biomes", False):
        return {
            "available_biomes": sorted(BIOME_PALETTES.keys()),
            "count": len(BIOME_PALETTES),
            "palette_zones": list(REQUIRED_PALETTE_KEYS),
        }

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("'object_name' is required.")

    biome_name = params.get("biome_name")
    if not biome_name:
        raise ValueError(
            "'biome_name' is required. Use list_biomes=True to see options."
        )

    corruption_level = float(params.get("corruption_level", 0.0))
    water_level = float(params.get("water_level", 0.0))

    if bpy is None:
        raise RuntimeError("This handler requires Blender (bpy).")

    # Get the mesh object
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found in scene.")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is not a mesh (type={obj.type})."
        )

    mesh = obj.data

    # Extract mesh data for pure-logic functions
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]
    normals = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]

    mesh_data = {
        "vertices": vertices,
        "faces": faces,
        "normals": normals,
        "water_level": water_level,
    }

    # Get palette and build material list
    palette = get_biome_palette(biome_name)
    zone_order = ["ground", "slopes", "cliffs", "water_edges"]
    mat_keys: list[str] = []
    for zone in zone_order:
        mat_keys.extend(palette[zone])

    # Create or reuse Blender materials for each key
    created_materials: list[str] = []
    for key in mat_keys:
        mat_name = f"Terrain_{biome_name}_{key}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat_def = _get_material_def(key)
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            if mat_def:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    base_input = bsdf.inputs.get("Base Color")
                    if base_input:
                        base_input.default_value = mat_def["base_color"]
                    rough_input = bsdf.inputs.get("Roughness")
                    if rough_input:
                        rough_input.default_value = mat_def["roughness"]
                    metal_input = bsdf.inputs.get("Metallic")
                    if metal_input:
                        metal_input.default_value = mat_def["metallic"]
            created_materials.append(mat_name)

        # Add material slot to object if not present
        if mat_name not in [
            s.material.name for s in obj.material_slots if s.material
        ]:
            obj.data.materials.append(mat)

    # Assign material indices to faces (offset by pre-existing slots)
    slot_offset = len(obj.material_slots) - len(mat_keys)
    if slot_offset < 0:
        slot_offset = 0
    material_indices = assign_terrain_materials_by_slope(mesh_data, biome_name)
    for fi, mat_idx in enumerate(material_indices):
        if fi < len(mesh.polygons):
            mesh.polygons[fi].material_index = mat_idx + slot_offset

    # Paint vertex colors — MISC-013: use color_attributes API (Blender 3.4+)
    # mesh.vertex_colors is deprecated; color_attributes is the modern replacement.
    vc_layer_name = f"TerrainSplatmap_{biome_name}"
    if vc_layer_name not in mesh.color_attributes:
        mesh.color_attributes.new(
            name=vc_layer_name, type="FLOAT_COLOR", domain="CORNER"
        )
    vc_layer = mesh.color_attributes[vc_layer_name]

    raw_colors = blend_terrain_vertex_colors(mesh_data, biome_name)

    # Apply corruption if requested
    if corruption_level > 0.0:
        raw_colors = apply_corruption_tint(raw_colors, corruption_level)

    # Write vertex colors per-loop (CORNER domain stores one value per loop)
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            if vi < len(raw_colors):
                vc_layer.data[li].color = raw_colors[vi]

    mesh.update()

    # Count faces per zone for reporting
    zone_counts: dict[str, int] = {
        "ground": 0,
        "slopes": 0,
        "cliffs": 0,
        "water_edges": 0,
    }
    for fi, face in enumerate(faces):
        if fi < len(normals):
            normal = normals[fi]
            z_vals = [vertices[vi][2] for vi in face if vi < len(vertices)]
            face_z = sum(z_vals) / len(z_vals) if z_vals else 0.0
            zone = _classify_face(normal, face_z, water_level)
            zone_counts[zone] += 1

    return {
        "status": "success",
        "object_name": object_name,
        "biome_name": biome_name,
        "materials_assigned": len(mat_keys),
        "materials_created": created_materials,
        "vertex_color_layer": vc_layer_name,
        "corruption_level": corruption_level,
        "water_level": water_level,
        "zone_face_counts": zone_counts,
        "total_faces": len(faces),
        "total_vertices": len(vertices),
    }


# ===========================================================================
# V2 API: Per-layer material palettes with vertex color splatmap blending
# ===========================================================================

REQUIRED_LAYER_KEYS = frozenset({
    "base_color", "roughness", "roughness_variation", "metallic",
    "normal_strength", "detail_scale", "wear_intensity", "node_recipe",
    "description",
})

VALID_LAYER_NAMES = frozenset({"ground", "slope", "cliff", "special"})

# V2 biome palettes: each biome has 4 layers with full material params.
BIOME_PALETTES_V2: dict[str, dict[str, dict[str, Any]]] = {
    "thornwood_forest": {
        "ground": {"base_color": (0.08, 0.06, 0.04, 1.0), "roughness": 0.92, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 8.0, "wear_intensity": 0.3, "node_recipe": "terrain", "description": "Dark leaf litter + exposed roots + soil"},
        "slope": {"base_color": (0.10, 0.12, 0.08, 1.0), "roughness": 0.75, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.25, "node_recipe": "terrain", "description": "Moss-covered rock (green-gray)"},
        "cliff": {"base_color": (0.14, 0.13, 0.11, 1.0), "roughness": 0.85, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.4, "detail_scale": 5.0, "wear_intensity": 0.35, "node_recipe": "stone", "description": "Gray stone with vine growth overlay"},
        "special": {"base_color": (0.10, 0.06, 0.11, 1.0), "roughness": 0.80, "roughness_variation": 0.18, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 7.0, "wear_intensity": 0.4, "node_recipe": "organic", "description": "Corrupted ground patches (purple-tinted dark)"},
    },
    "corrupted_swamp": {
        "ground": {"base_color": (0.04, 0.03, 0.03, 1.0), "roughness": 0.35, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 0.6, "detail_scale": 6.0, "wear_intensity": 0.3, "node_recipe": "terrain", "description": "Black mud + toxic pools (very dark, wet)"},
        "slope": {"base_color": (0.05, 0.04, 0.04, 1.0), "roughness": 0.25, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.5, "detail_scale": 8.0, "wear_intensity": 0.2, "node_recipe": "terrain", "description": "Slick dark rock + slime trails (very low roughness)"},
        "cliff": {"base_color": (0.12, 0.08, 0.13, 1.0), "roughness": 0.70, "roughness_variation": 0.20, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 5.0, "wear_intensity": 0.5, "node_recipe": "stone", "description": "Corroded stone with purple corruption veins", "emission_color": (0.15, 0.02, 0.20, 1.0), "emission_strength": 0.3},
        "special": {"base_color": (0.04, 0.08, 0.04, 1.0), "roughness": 0.15, "roughness_variation": 0.05, "metallic": 0.0, "normal_strength": 0.3, "detail_scale": 4.0, "wear_intensity": 0.1, "node_recipe": "terrain", "description": "Toxic pool surface (green emission, translucent)", "emission_color": (0.05, 0.25, 0.05, 1.0), "emission_strength": 0.8, "alpha": 0.6},
    },
    "mountain_pass": {
        "ground": {"base_color": (0.11, 0.14, 0.08, 1.0), "roughness": 0.82, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 11.0, "wear_intensity": 0.24, "node_recipe": "terrain", "description": "Alpine grass + gravel + damp earth pockets"},
        "slope": {"base_color": (0.13, 0.15, 0.11, 1.0), "roughness": 0.74, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 7.0, "wear_intensity": 0.28, "node_recipe": "stone", "description": "Mossed rock + lichen + exposed stone"},
        "cliff": {"base_color": (0.18, 0.16, 0.14, 1.0), "roughness": 0.88, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.6, "detail_scale": 4.0, "wear_intensity": 0.4, "node_recipe": "stone", "description": "Layered sedimentary rock with cracks (warm gray)"},
        "special": {"base_color": (0.34, 0.37, 0.33, 1.0), "roughness": 0.68, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.35, "detail_scale": 9.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Snow remnants + wet alpine patches", "subsurface_color": (0.28, 0.34, 0.30, 1.0), "subsurface_weight": 0.04},
    },
    "mountain_pass_summer": {
        "ground": {"base_color": (0.10, 0.15, 0.08, 1.0), "roughness": 0.84, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.75, "detail_scale": 12.0, "wear_intensity": 0.22, "node_recipe": "terrain", "description": "July alpine grass + gravel + damp dark soil"},
        "slope": {"base_color": (0.12, 0.16, 0.11, 1.0), "roughness": 0.76, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.05, "detail_scale": 7.0, "wear_intensity": 0.28, "node_recipe": "stone", "description": "Lichen-heavy rock + mossed switchback slopes"},
        "cliff": {"base_color": (0.19, 0.17, 0.14, 1.0), "roughness": 0.89, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.7, "detail_scale": 4.0, "wear_intensity": 0.42, "node_recipe": "stone", "description": "Layered cliff stone with warm sediment bands"},
        "special": {"base_color": (0.09, 0.12, 0.07, 1.0), "roughness": 0.58, "roughness_variation": 0.08, "metallic": 0.0, "normal_strength": 0.42, "detail_scale": 10.0, "wear_intensity": 0.08, "node_recipe": "terrain", "description": "Wet riverbank grass + saturated alpine patches", "subsurface_color": (0.16, 0.20, 0.12, 1.0), "subsurface_weight": 0.03},
    },
    "mountain_pass_winter": {
        "ground": {"base_color": (0.10, 0.12, 0.08, 1.0), "roughness": 0.84, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 11.0, "wear_intensity": 0.24, "node_recipe": "terrain", "description": "Frozen gravel + sparse alpine grass"},
        "slope": {"base_color": (0.14, 0.15, 0.13, 1.0), "roughness": 0.72, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 7.0, "wear_intensity": 0.28, "node_recipe": "stone", "description": "Cold exposed rock + thin ice sheets"},
        "cliff": {"base_color": (0.18, 0.17, 0.16, 1.0), "roughness": 0.88, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.6, "detail_scale": 4.0, "wear_intensity": 0.4, "node_recipe": "stone", "description": "Layered cliff stone dusted with frost"},
        "special": {"base_color": (0.36, 0.39, 0.40, 1.0), "roughness": 0.66, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.35, "detail_scale": 9.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Snow shelves + slushy runoff pockets", "subsurface_color": (0.33, 0.37, 0.39, 1.0), "subsurface_weight": 0.05},
    },
    "ruined_fortress": {
        "ground": {"base_color": (0.13, 0.11, 0.09, 1.0), "roughness": 0.90, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 6.0, "wear_intensity": 0.45, "node_recipe": "stone", "description": "Broken cobblestone + dirt + rubble"},
        "slope": {"base_color": (0.12, 0.13, 0.10, 1.0), "roughness": 0.78, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 7.0, "wear_intensity": 0.35, "node_recipe": "stone", "description": "Crumbling wall foundation + moss (gray-green)"},
        "cliff": {"base_color": (0.15, 0.14, 0.12, 1.0), "roughness": 0.85, "roughness_variation": 0.18, "metallic": 0.0, "normal_strength": 1.5, "detail_scale": 5.0, "wear_intensity": 0.5, "node_recipe": "stone", "description": "Damaged stone with crack patterns"},
        "special": {"base_color": (0.10, 0.06, 0.11, 1.0), "roughness": 0.65, "roughness_variation": 0.20, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.5, "node_recipe": "organic", "description": "Corruption overlay (purple veins)", "emission_color": (0.12, 0.02, 0.18, 1.0), "emission_strength": 0.2},
    },
    "abandoned_village": {
        "ground": {"base_color": (0.12, 0.10, 0.06, 1.0), "roughness": 0.80, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.7, "detail_scale": 8.0, "wear_intensity": 0.25, "node_recipe": "terrain", "description": "Dirt paths + overgrown grass (brown-green)"},
        "slope": {"base_color": (0.16, 0.15, 0.13, 1.0), "roughness": 0.75, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.9, "detail_scale": 7.0, "wear_intensity": 0.3, "node_recipe": "stone", "description": "Old stone walls (warm gray)"},
        "cliff": {"base_color": (0.14, 0.10, 0.07, 1.0), "roughness": 0.88, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.35, "node_recipe": "terrain", "description": "Exposed earth (brown, high roughness)"},
        "special": {"base_color": (0.14, 0.12, 0.08, 1.0), "roughness": 0.85, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.5, "detail_scale": 12.0, "wear_intensity": 0.15, "node_recipe": "organic", "description": "Dead/wilted vegetation (brown-yellow)"},
    },
    "veil_crack_zone": {
        "ground": {"base_color": (0.06, 0.05, 0.05, 1.0), "roughness": 0.80, "roughness_variation": 0.18, "metallic": 0.0, "normal_strength": 1.4, "detail_scale": 5.0, "wear_intensity": 0.5, "node_recipe": "terrain", "description": "Fractured earth with glowing cracks", "emission_color": (0.40, 0.10, 0.50, 1.0), "emission_strength": 0.6},
        "slope": {"base_color": (0.20, 0.18, 0.22, 1.0), "roughness": 0.20, "roughness_variation": 0.08, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 10.0, "wear_intensity": 0.1, "node_recipe": "stone", "description": "Crystal surfaces (high metallic, low roughness)"},
        "cliff": {"base_color": (0.08, 0.05, 0.10, 1.0), "roughness": 0.75, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 6.0, "wear_intensity": 0.4, "node_recipe": "stone", "description": "Void-touched stone (dark purple)"},
        "special": {"base_color": (0.15, 0.10, 0.20, 1.0), "roughness": 0.10, "roughness_variation": 0.05, "metallic": 0.0, "normal_strength": 0.3, "detail_scale": 8.0, "wear_intensity": 0.05, "node_recipe": "stone", "description": "Floating crystal surface (translucent + emission)", "emission_color": (0.30, 0.15, 0.45, 1.0), "emission_strength": 1.0, "alpha": 0.5},
    },
    "cemetery": {
        "ground": {"base_color": (0.05, 0.04, 0.04, 1.0), "roughness": 0.90, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.7, "detail_scale": 8.0, "wear_intensity": 0.2, "node_recipe": "terrain", "description": "Dark soil + dead grass + fog (near-black)"},
        "slope": {"base_color": (0.14, 0.13, 0.12, 1.0), "roughness": 0.72, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 6.0, "wear_intensity": 0.3, "node_recipe": "stone", "description": "Worn stone walkways (gray, medium roughness)"},
        "cliff": {"base_color": (0.12, 0.12, 0.10, 1.0), "roughness": 0.82, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 7.0, "wear_intensity": 0.35, "node_recipe": "stone", "description": "Old stone walls (gray, mossy)"},
        "special": {"base_color": (0.30, 0.30, 0.32, 1.0), "roughness": 0.50, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.2, "detail_scale": 4.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Fog/mist ground (alpha, white)", "alpha": 0.3},
    },
    "battlefield": {
        "ground": {"base_color": (0.09, 0.06, 0.05, 1.0), "roughness": 0.45, "roughness_variation": 0.18, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 6.0, "wear_intensity": 0.4, "node_recipe": "terrain", "description": "Churned mud + blood-stained earth (dark brown-red, wet)"},
        "slope": {"base_color": (0.12, 0.12, 0.06, 1.0), "roughness": 0.85, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.6, "detail_scale": 10.0, "wear_intensity": 0.2, "node_recipe": "terrain", "description": "Trampled grass (yellow-green, high roughness)"},
        "cliff": {"base_color": (0.14, 0.10, 0.07, 1.0), "roughness": 0.88, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 5.0, "wear_intensity": 0.35, "node_recipe": "terrain", "description": "Earthen embankment (brown, high roughness)"},
        "special": {"base_color": (0.04, 0.03, 0.03, 1.0), "roughness": 0.95, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 8.0, "wear_intensity": 0.6, "node_recipe": "terrain", "description": "Scorched ground (black, very high roughness)"},
    },
    "desert": {
        "ground": {"base_color": (0.22, 0.18, 0.12, 1.0), "roughness": 0.88, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 12.0, "wear_intensity": 0.1, "node_recipe": "terrain", "description": "Wind-swept sand + cracked clay (warm tan, high roughness)"},
        "slope": {"base_color": (0.20, 0.16, 0.10, 1.0), "roughness": 0.86, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 5.0, "wear_intensity": 0.3, "node_recipe": "stone", "description": "Sandstone + exposed warm rock (layered, eroded)"},
        "cliff": {"base_color": (0.21, 0.17, 0.11, 1.0), "roughness": 0.82, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.6, "detail_scale": 4.0, "wear_intensity": 0.35, "node_recipe": "stone", "description": "Layered sandstone cliff (horizontal strata, warm gray)"},
        "special": {"base_color": (0.30, 0.28, 0.25, 1.0), "roughness": 0.75, "roughness_variation": 0.06, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 10.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Salt flat / dried oasis (pale, cracked)"},
    },
    "coastal": {
        "ground": {"base_color": (0.16, 0.14, 0.10, 1.0), "roughness": 0.50, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 10.0, "wear_intensity": 0.1, "node_recipe": "terrain", "description": "Wet sand + beach pebbles (damp, low roughness)"},
        "slope": {"base_color": (0.14, 0.13, 0.12, 1.0), "roughness": 0.72, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 6.0, "wear_intensity": 0.4, "node_recipe": "stone", "description": "Sea-weathered rock + coastal grass (gray-green, eroded)"},
        "cliff": {"base_color": (0.12, 0.11, 0.10, 1.0), "roughness": 0.78, "roughness_variation": 0.16, "metallic": 0.0, "normal_strength": 1.5, "detail_scale": 5.0, "wear_intensity": 0.5, "node_recipe": "stone", "description": "Sea cliff stone (dark gray, salt-worn, dramatic)"},
        "special": {"base_color": (0.06, 0.08, 0.10, 1.0), "roughness": 0.12, "roughness_variation": 0.04, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 4.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Tidal pool surface (dark reflective, translucent)", "alpha": 0.5},
    },
    "grasslands": {
        "ground": {"base_color": (0.08, 0.10, 0.05, 1.0), "roughness": 0.84, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.5, "detail_scale": 14.0, "wear_intensity": 0.08, "node_recipe": "terrain", "description": "Tall grass + wildflower soil (muted green, soft)"},
        "slope": {"base_color": (0.10, 0.11, 0.07, 1.0), "roughness": 0.80, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.25, "node_recipe": "stone", "description": "Grass-covered rock (gray-green, mossy)"},
        "cliff": {"base_color": (0.12, 0.10, 0.07, 1.0), "roughness": 0.88, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 7.0, "wear_intensity": 0.3, "node_recipe": "terrain", "description": "Exposed earth with green patches (brown, high roughness)"},
        "special": {"base_color": (0.06, 0.08, 0.04, 1.0), "roughness": 0.78, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.3, "detail_scale": 12.0, "wear_intensity": 0.06, "node_recipe": "organic", "description": "Riverbank grass (dark green, damp)"},
    },
    "mushroom_forest": {
        "ground": {"base_color": (0.10, 0.08, 0.12, 1.0), "roughness": 0.88, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.6, "detail_scale": 8.0, "wear_intensity": 0.2, "node_recipe": "organic", "description": "Mycelium soil + spore dust (purple-tinted dark earth)"},
        "slope": {"base_color": (0.11, 0.09, 0.13, 1.0), "roughness": 0.80, "roughness_variation": 0.16, "metallic": 0.0, "normal_strength": 1.2, "detail_scale": 6.0, "wear_intensity": 0.35, "node_recipe": "stone", "description": "Fungal rock (purple-gray, spongy texture)"},
        "cliff": {"base_color": (0.08, 0.06, 0.12, 1.0), "roughness": 0.72, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 1.4, "detail_scale": 5.0, "wear_intensity": 0.3, "node_recipe": "stone", "description": "Bioluminescent stone (deep purple, faint glow)", "emission_color": (0.10, 0.05, 0.18, 1.0), "emission_strength": 0.3},
        "special": {"base_color": (0.07, 0.08, 0.14, 1.0), "roughness": 0.18, "roughness_variation": 0.06, "metallic": 0.0, "normal_strength": 0.4, "detail_scale": 4.0, "wear_intensity": 0.05, "node_recipe": "terrain", "description": "Luminous pool edge (blue-purple, wet, glowing)", "emission_color": (0.08, 0.06, 0.20, 1.0), "emission_strength": 0.6},
    },
    "crystal_cavern": {
        "ground": {"base_color": (0.12, 0.10, 0.14, 1.0), "roughness": 0.75, "roughness_variation": 0.12, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 8.0, "wear_intensity": 0.2, "node_recipe": "stone", "description": "Geode floor + crystal dust (purple-gray, slightly metallic)"},
        "slope": {"base_color": (0.14, 0.12, 0.18, 1.0), "roughness": 0.40, "roughness_variation": 0.15, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.25, "node_recipe": "stone", "description": "Prismatic rock (faceted, high metallic, refractive)"},
        "cliff": {"base_color": (0.16, 0.14, 0.22, 1.0), "roughness": 0.15, "roughness_variation": 0.08, "metallic": 0.0, "normal_strength": 0.6, "detail_scale": 10.0, "wear_intensity": 0.1, "node_recipe": "stone", "description": "Crystal wall (low roughness, high metallic, translucent)", "emission_color": (0.12, 0.08, 0.25, 1.0), "emission_strength": 0.4, "alpha": 0.7},
        "special": {"base_color": (0.10, 0.12, 0.18, 1.0), "roughness": 0.08, "roughness_variation": 0.04, "metallic": 0.0, "normal_strength": 0.3, "detail_scale": 4.0, "wear_intensity": 0.03, "node_recipe": "terrain", "description": "Mineral pool (dark reflective, mineral-rich)", "emission_color": (0.06, 0.08, 0.15, 1.0), "emission_strength": 0.3},
    },
    "deep_forest": {
        "ground": {"base_color": (0.06, 0.05, 0.03, 1.0), "roughness": 0.92, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 0.8, "detail_scale": 8.0, "wear_intensity": 0.2, "node_recipe": "terrain", "description": "Thick leaf litter + ancient root soil (near-black, very dark)"},
        "slope": {"base_color": (0.08, 0.10, 0.06, 1.0), "roughness": 0.78, "roughness_variation": 0.14, "metallic": 0.0, "normal_strength": 1.0, "detail_scale": 6.0, "wear_intensity": 0.3, "node_recipe": "stone", "description": "Moss-blanketed rock (deep green over gray stone)"},
        "cliff": {"base_color": (0.09, 0.07, 0.05, 1.0), "roughness": 0.85, "roughness_variation": 0.16, "metallic": 0.0, "normal_strength": 1.5, "detail_scale": 5.0, "wear_intensity": 0.4, "node_recipe": "stone", "description": "Root-covered cliff (exposed earth with gnarled roots)"},
        "special": {"base_color": (0.07, 0.06, 0.05, 1.0), "roughness": 0.35, "roughness_variation": 0.10, "metallic": 0.0, "normal_strength": 0.5, "detail_scale": 8.0, "wear_intensity": 0.12, "node_recipe": "terrain", "description": "Forest stream bed (wet, dark, smooth pebbles)"},
    },
}


def auto_assign_terrain_layers(
    vertices: list[tuple[float, float, float]],
    face_normals: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    biome_name: str = "thornwood_forest",
    *,
    slope_flat_deg: float = 30.0,
    slope_cliff_deg: float = 60.0,
    special_low_pct: float = 0.15,
    special_high_pct: float = 0.85,
    moisture_map: Any = None,
    terrain_resolution: int = 0,
) -> list[tuple[float, float, float, float]]:
    """Compute per-vertex RGBA splatmap weights from slope, height, and moisture.

    **V2 unified engine** — delegates to ``terrain_materials_v2.compute_slope_material_weights``
    for smoothstep-based weight computation, then maps the 5-channel v2 output
    back to 4-channel RGBA for backward compatibility:

        R = ground weight
        G = scree + cliff partial (slope proxy)
        B = cliff weight
        A = wet_rock + snow (special proxy) + height-extreme bands

    Pure-logic function -- no bpy dependency.
    R=ground, G=slope, B=cliff, A=special. Normalised to sum=1.

    When moisture_map is provided (2D numpy array, values in [0, 1]),
    the ground layer (R channel) is modulated by moisture level:
      - High moisture (> 0.7) + low slope -> mud/wetland (boosted R)
      - Medium moisture (0.3-0.7) + low slope -> grass (standard R)
      - Low moisture (< 0.3) + low slope -> dry earth (reduced R, boosted A)
    Slope and altitude rules still override: steep = cliff, high = snow.

    Args:
        vertices: List of (x, y, z) vertex positions.
        face_normals: List of (nx, ny, nz) per-face normal vectors.
        faces: List of face tuples (vertex indices).
        biome_name: Biome palette name (for future per-biome rules).
        slope_flat_deg: Maximum slope angle for flat ground.
        slope_cliff_deg: Minimum slope angle for cliff surfaces.
        special_low_pct: Height percentile below which A channel activates.
        special_high_pct: Height percentile above which A channel activates.
        moisture_map: Optional 2D numpy array of moisture values in [0, 1].
            Shape should match terrain resolution. If None, no moisture
            modulation is applied (backward compatible).
        terrain_resolution: Grid resolution for mapping vertices to moisture
            cells. If 0, inferred from moisture_map shape.
    """
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # --- Build per-vertex slope (radians) via face-normal averaging ---
    vert_faces: list[list[int]] = [[] for _ in range(num_verts)]
    for fi, face in enumerate(faces):
        for vi in face:
            if 0 <= vi < num_verts:
                vert_faces[vi].append(fi)

    vert_slopes = np.zeros(num_verts, dtype=np.float64)
    for vi in range(num_verts):
        adj = vert_faces[vi]
        if not adj:
            continue
        nx, ny, nz = 0.0, 0.0, 0.0
        for fi in adj:
            fn = face_normals[fi]
            nx += fn[0]
            ny += fn[1]
            nz += fn[2]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        nz_n = nz / length if length > 1e-9 else 1.0
        dot = max(-1.0, min(1.0, nz_n))
        vert_slopes[vi] = math.acos(dot)

    # --- Build height arrays ---
    z_values = np.array([v[2] for v in vertices], dtype=np.float64)
    z_min, z_max = float(z_values.min()), float(z_values.max())
    z_range = z_max - z_min
    if z_range < 1e-9:
        height_pcts = np.full(num_verts, 0.5, dtype=np.float64)
    else:
        height_pcts = (z_values - z_min) / z_range

    # --- Use v2 smoothstep engine for slope-based weights ---
    # Build a v2-compatible MaterialRuleSet that maps to RGBA:
    #   channel 0 = ground (R), channel 1 = scree/slope (G),
    #   channel 2 = cliff (B), channel 3 = special (A)
    slope_flat_rad = math.radians(slope_flat_deg)
    slope_cliff_rad = math.radians(slope_cliff_deg)
    mid_rad = (slope_flat_rad + slope_cliff_rad) / 2.0
    falloff_low = math.radians(8.0)
    falloff_high = math.radians(10.0)

    # Compute smoothstep weights per channel using v2 primitives
    ground_w = _smoothstep_band(vert_slopes, 0.0, slope_flat_rad, falloff_low)
    slope_w = _smoothstep_band(vert_slopes, slope_flat_rad, slope_cliff_rad, falloff_low)
    cliff_w = _smoothstep_band(vert_slopes, slope_cliff_rad, math.pi / 2.0, falloff_high)

    # Normalize slope weights
    total_slope = ground_w + slope_w + cliff_w
    total_slope = np.where(total_slope < 1e-9, 1.0, total_slope)
    r = (ground_w / total_slope).astype(np.float64)
    g = (slope_w / total_slope).astype(np.float64)
    b = (cliff_w / total_slope).astype(np.float64)

    # --- Moisture modulation (same logic, vectorized) ---
    has_moisture = moisture_map is not None
    a_moisture = np.zeros(num_verts, dtype=np.float64)
    if has_moisture:
        mmap = np.asarray(moisture_map, dtype=np.float64)
        m_rows, m_cols = mmap.shape
        x_vals = np.array([v[0] for v in vertices], dtype=np.float64)
        y_vals = np.array([v[1] for v in vertices], dtype=np.float64)
        x_min_t, x_max_t = float(x_vals.min()), float(x_vals.max())
        y_min_t, y_max_t = float(y_vals.min()), float(y_vals.max())
        x_range_t = x_max_t - x_min_t
        y_range_t = y_max_t - y_min_t

        is_flat = vert_slopes < slope_flat_rad
        if x_range_t > 1e-9 and y_range_t > 1e-9:
            u = (x_vals - x_min_t) / x_range_t
            v_coord = (y_vals - y_min_t) / y_range_t
            mi = np.clip((v_coord * (m_rows - 1)).astype(int), 0, m_rows - 1)
            mj = np.clip((u * (m_cols - 1)).astype(int), 0, m_cols - 1)
            moisture = mmap[mi, mj]
        else:
            moisture = np.full(num_verts, 0.5, dtype=np.float64)

        wet_mask = (moisture > 0.7) & is_flat
        dry_mask = (moisture < 0.3) & is_flat
        r = np.where(wet_mask, r * 1.2, r)
        r = np.where(dry_mask, r * 0.7, r)
        a_moisture = np.where(wet_mask, 0.15 * (moisture - 0.7) / 0.3, a_moisture)
        a_moisture = np.where(dry_mask, 0.1 * (0.3 - moisture) / 0.3, a_moisture)

    # --- Alpha channel: special at height extremes ---
    a = np.zeros(num_verts, dtype=np.float64)
    if special_low_pct > 1e-9:
        low_mask = height_pcts < special_low_pct
        a = np.where(low_mask, 1.0 - (height_pcts / max(special_low_pct, 1e-9)), a)
    if special_high_pct < 1.0:
        high_mask = height_pcts > special_high_pct
        a = np.where(high_mask, (height_pcts - special_high_pct) / max(1.0 - special_high_pct, 1e-9), a)
    a = np.clip(a + a_moisture, 0.0, 1.0)

    # --- Renormalize RGB to (1 - alpha) ---
    rgb_sum = r + g + b
    remaining = 1.0 - a
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(rgb_sum > 0.0, remaining / rgb_sum, 0.0)
    r_n = np.where(rgb_sum > 0.0, r * scale, 0.0)
    g_n = np.where(rgb_sum > 0.0, g * scale, 0.0)
    b_n = np.where(rgb_sum > 0.0, b * scale, remaining)

    r_n = np.clip(r_n, 0.0, 1.0)
    g_n = np.clip(g_n, 0.0, 1.0)
    b_n = np.clip(b_n, 0.0, 1.0)

    return [
        (float(r_n[i]), float(g_n[i]), float(b_n[i]), float(a[i]))
        for i in range(num_verts)
    ]


def _resolve_biome_palette_name(
    biome_name: str,
    season: str | None = None,
) -> str:
    """Resolve biome aliases and season-specific palette variants."""
    resolved = biome_name or DEFAULT_BIOME
    if resolved in BIOME_PALETTES_V2:
        return resolved
    if resolved == "mountain_pass":
        if season == "summer":
            return "mountain_pass_summer"
        if season == "winter":
            return "mountain_pass_winter"
    return resolved


def compute_world_splatmap_weights(
    heightmap: list[list[float]] | np.ndarray,
    biome_name: str = DEFAULT_BIOME,
    *,
    cell_size: float = 1.0,
    slope_flat_deg: float = 30.0,
    slope_cliff_deg: float = 60.0,
    special_low_pct: float = 0.15,
    special_high_pct: float = 0.85,
    moisture_map: Any = None,
    height_range: tuple[float, float] | None = None,
) -> np.ndarray:
    """Compute a world-consistent RGBA splatmap from a full heightfield.

    This is the tiled-world version of ``auto_assign_terrain_layers``. The
    entire world region is evaluated in one pass so height and slope thresholds
    stay consistent across tile boundaries.
    """
    hmap = np.asarray(heightmap, dtype=np.float64)
    if hmap.ndim != 2:
        raise ValueError("heightmap must be 2D")
    if hmap.size == 0:
        return np.zeros((*hmap.shape, 4), dtype=np.float64)

    # Preserve biome validation for callers that pass an explicit biome name,
    # but keep the weights generation itself biome-agnostic.
    if biome_name:
        try:
            get_biome_palette(biome_name)
        except ValueError:
            logger.warning("Unknown biome '%s' passed to compute_world_splatmap_weights", biome_name)

    slope_map = compute_slope_map(hmap, cell_size=cell_size)
    if height_range is not None:
        z_min, z_max = float(height_range[0]), float(height_range[1])
        if z_max < z_min:
            z_min, z_max = z_max, z_min
    else:
        z_min = float(hmap.min())
        z_max = float(hmap.max())
    z_range = z_max - z_min
    if z_range < 1e-9:
        height_pcts = np.full(hmap.shape, 0.5, dtype=np.float64)
    else:
        height_pcts = (hmap - z_min) / z_range

    if moisture_map is not None:
        mmap = np.asarray(moisture_map, dtype=np.float64)
        if mmap.shape != hmap.shape:
            raise ValueError("moisture_map must match heightmap shape")
    else:
        mmap = None

    # --- V2 unified smoothstep engine (replaces hard-threshold linear ramps) ---
    # Uses v2 _smoothstep_band primitives for smooth slope transitions instead
    # of the previous hard if/else banding. Performance is identical (vectorized
    # numpy), but transitions are now smooth Hermite ramps with configurable
    # falloff widths instead of hard edges at flat_deg and cliff_deg.
    slope = np.asarray(slope_map, dtype=np.float64)
    hp = np.asarray(height_pcts, dtype=np.float64)

    flat_deg = float(slope_flat_deg)
    cliff_deg = float(slope_cliff_deg)
    falloff_low = 8.0   # degrees of smooth transition
    falloff_high = 10.0  # degrees of smooth transition

    # Smoothstep-based slope weights (ground / slope / cliff)
    red = _smoothstep_band(slope, 0.0, flat_deg, falloff_low)
    green = _smoothstep_band(slope, flat_deg, cliff_deg, falloff_low)
    blue = _smoothstep_band(slope, cliff_deg, 90.0, falloff_high)

    # Normalize slope weights so they sum to 1 per cell
    slope_total = red + green + blue
    slope_total = np.where(slope_total < 1e-9, 1.0, slope_total)
    red = red / slope_total
    green = green / slope_total
    blue = blue / slope_total

    # Moisture modulation — only applies on ground-dominant cells and only if
    # a moisture map was provided.
    is_ground_dominant = red > 0.5
    if mmap is not None:
        moisture = mmap
        wet_mask = (moisture > 0.7) & is_ground_dominant
        dry_mask = (moisture < 0.3) & is_ground_dominant
        red = np.where(wet_mask, red * 1.2, red)
        red = np.where(dry_mask, red * 0.7, red)
        a_moisture = np.zeros_like(hp)
        a_moisture = np.where(
            wet_mask,
            0.15 * (moisture - 0.7) / 0.3,
            a_moisture,
        )
        a_moisture = np.where(
            dry_mask,
            0.1 * (0.3 - moisture) / 0.3,
            a_moisture,
        )
    else:
        a_moisture = np.zeros_like(hp)

    # Alpha channel: special material at the lowest and highest altitude bands,
    # fading linearly toward the midrange.
    alpha = np.zeros_like(hp)
    if special_low_pct > 1e-9:
        low_mask = hp < special_low_pct
        alpha = np.where(low_mask, 1.0 - (hp / max(special_low_pct, 1e-9)), alpha)
    if special_high_pct < 1.0:
        high_mask = hp > special_high_pct
        alpha = np.where(
            high_mask,
            (hp - special_high_pct) / max(1.0 - special_high_pct, 1e-9),
            alpha,
        )
    alpha = np.clip(alpha + a_moisture, 0.0, 1.0)

    # Renormalize RGB to (1 - alpha). Preserve legacy fallback where all RGB
    # cells are zero — they inherit the "special" category via blue.
    rgb_sum = red + green + blue
    remaining = 1.0 - alpha
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(rgb_sum > 0.0, remaining / rgb_sum, 0.0)
    red_n = np.where(rgb_sum > 0.0, red * scale, 0.0)
    green_n = np.where(rgb_sum > 0.0, green * scale, 0.0)
    blue_n = np.where(rgb_sum > 0.0, blue * scale, remaining)

    result = np.zeros((*hmap.shape, 4), dtype=np.float64)
    result[..., 0] = np.clip(red_n, 0.0, 1.0)
    result[..., 1] = np.clip(green_n, 0.0, 1.0)
    result[..., 2] = np.clip(blue_n, 0.0, 1.0)
    result[..., 3] = alpha
    return result


def _build_pbr_layer_nodes(
    tree: Any,
    links: Any,
    layer_params: dict[str, Any],
    layer_name: str,
    y_offset: int,
    *,
    pbr_textures: dict[str, str] | None = None,
) -> tuple[Any, Any]:
    """Build a full PBR node chain for one terrain layer.

    Creates:
      - Principled BSDF with all palette params
      - Noise texture for procedural detail/height
      - Roughness variation overlay (noise modulates base roughness)
      - Bump node for micro-detail normals
      - Optional PBR image texture inputs (albedo, roughness, normal, height)
        when ``pbr_textures`` provides paths

    Returns:
        (bsdf_node, height_output_node) — the height output feeds HeightBlend.
    """
    lp = layer_params
    x_base = -900

    # -- Coordinate input for texture mapping --
    tex_coord = _add_node(tree, "ShaderNodeTexCoord", x_base - 200, y_offset, f"TexCoord {layer_name}")

    # -- Noise for procedural detail + height blend source --
    noise = _add_node(tree, "ShaderNodeTexNoise", x_base, y_offset - 100, f"Noise {layer_name}")
    noise.inputs["Scale"].default_value = lp["detail_scale"]
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.6
    noise.inputs["Distortion"].default_value = 0.2
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    # -- Second noise octave for roughness variation --
    rough_noise = _add_node(tree, "ShaderNodeTexNoise", x_base, y_offset - 250, f"RoughNoise {layer_name}")
    rough_noise.inputs["Scale"].default_value = lp["detail_scale"] * 2.5
    rough_noise.inputs["Detail"].default_value = 4.0
    links.new(tex_coord.outputs["Object"], rough_noise.inputs["Vector"])

    # -- Roughness = base_roughness +/- variation via noise --
    rough_var = lp.get("roughness_variation", 0.1)
    rough_remap = _add_node(tree, "ShaderNodeMapRange", x_base + 200, y_offset - 250, f"RoughRemap {layer_name}")
    rough_remap.inputs["From Min"].default_value = 0.0
    rough_remap.inputs["From Max"].default_value = 1.0
    rough_remap.inputs["To Min"].default_value = max(0.0, lp["roughness"] - rough_var)
    rough_remap.inputs["To Max"].default_value = min(1.0, lp["roughness"] + rough_var)
    links.new(rough_noise.outputs["Fac"], rough_remap.inputs["Value"])

    # -- Principled BSDF --
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", x_base + 500, y_offset, f"Layer: {layer_name}")
    bsdf.inputs["Base Color"].default_value = lp["base_color"]
    bsdf.inputs["Metallic"].default_value = lp["metallic"]

    # Connect roughness variation
    links.new(rough_remap.outputs["Result"], bsdf.inputs["Roughness"])

    # Emission
    ec = lp.get("emission_color")
    es = lp.get("emission_strength", 0.0)
    if ec and es > 0:
        ei = _get_bsdf_input(bsdf, "Emission Color")
        if ei is not None:
            ei.default_value = ec
        esi = bsdf.inputs.get("Emission Strength")
        if esi is not None:
            esi.default_value = es

    # Subsurface
    sw = lp.get("subsurface_weight")
    sc = lp.get("subsurface_color")
    if sw and sw > 0:
        si = _get_bsdf_input(bsdf, "Subsurface Weight")
        if si is not None:
            si.default_value = sw
        if sc:
            sci = bsdf.inputs.get("Subsurface Color")
            if sci is not None:
                sci.default_value = sc

    # Alpha
    alpha_val = lp.get("alpha")
    if alpha_val is not None and alpha_val < 1.0:
        ai = bsdf.inputs.get("Alpha")
        if ai is not None:
            ai.default_value = alpha_val

    # -- Bump from noise height --
    bump = _add_node(tree, "ShaderNodeBump", x_base + 350, y_offset - 100, f"Bump {layer_name}")
    bump.inputs["Strength"].default_value = lp["normal_strength"]
    bump.inputs["Distance"].default_value = 0.02
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    # -- PBR image texture overrides (when available) --
    height_source = noise  # Default: noise Fac output for HeightBlend
    if pbr_textures:
        _wire_pbr_image(tree, links, bsdf, bump, tex_coord,
                        pbr_textures, layer_name, y_offset, x_base)
        # If a height texture was provided, use it as height source
        ht_path = pbr_textures.get("height")
        if ht_path:
            ht_img = bpy.data.images.get(ht_path) or bpy.data.images.load(ht_path)
            ht_node = _add_node(tree, "ShaderNodeTexImage", x_base + 100, y_offset - 400, f"HeightTex {layer_name}")
            ht_node.image = ht_img
            ht_node.projection = "FLAT"
            links.new(tex_coord.outputs["UV"], ht_node.inputs["Vector"])
            height_source = ht_node

    return bsdf, height_source


def _wire_pbr_image(
    tree: Any,
    links: Any,
    bsdf: Any,
    bump: Any,
    tex_coord: Any,
    pbr_textures: dict[str, str],
    layer_name: str,
    y_offset: int,
    x_base: int,
) -> None:
    """Wire PBR image textures (albedo, roughness, normal) into an existing layer.

    Only wires textures whose paths exist in ``pbr_textures``.
    """
    # Albedo
    albedo_path = pbr_textures.get("albedo")
    if albedo_path:
        img = bpy.data.images.get(albedo_path) or bpy.data.images.load(albedo_path)
        tex = _add_node(tree, "ShaderNodeTexImage", x_base - 100, y_offset + 100, f"Albedo {layer_name}")
        tex.image = img
        tex.projection = "FLAT"
        links.new(tex_coord.outputs["UV"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    # Roughness map
    rough_path = pbr_textures.get("roughness")
    if rough_path:
        img = bpy.data.images.get(rough_path) or bpy.data.images.load(rough_path)
        img.colorspace_settings.name = "Non-Color"
        tex = _add_node(tree, "ShaderNodeTexImage", x_base - 100, y_offset - 150, f"RoughTex {layer_name}")
        tex.image = img
        tex.projection = "FLAT"
        links.new(tex_coord.outputs["UV"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])

    # Normal map
    normal_path = pbr_textures.get("normal")
    if normal_path:
        img = bpy.data.images.get(normal_path) or bpy.data.images.load(normal_path)
        img.colorspace_settings.name = "Non-Color"
        tex = _add_node(tree, "ShaderNodeTexImage", x_base - 100, y_offset - 350, f"NormTex {layer_name}")
        tex.image = img
        tex.projection = "FLAT"
        links.new(tex_coord.outputs["UV"], tex.inputs["Vector"])
        nmap = _add_node(tree, "ShaderNodeNormalMap", x_base + 100, y_offset - 350, f"NormMap {layer_name}")
        links.new(tex.outputs["Color"], nmap.inputs["Color"])
        # Chain: normal map -> bump (bump uses normal map as base)
        links.new(nmap.outputs["Normal"], bump.inputs["Normal"])


def create_biome_terrain_material(
    biome_name: str,
    object_name: str | None = None,
    season: str | None = None,
    *,
    pbr_textures: dict[str, dict[str, str]] | None = None,
    enable_displacement: bool = False,
) -> Any:
    """Create a multi-layer PBR terrain material with splatmap blending.

    Uses BIOME_PALETTES_V2 for per-layer material definitions. Each layer
    gets a full PBR node chain (Base Color, Roughness with variation overlay,
    Normal/Bump, optional image textures). Layers are blended via HeightBlend
    groups driven by the vertex-color splatmap.

    Args:
        biome_name: Biome palette key from BIOME_PALETTES_V2.
        object_name: Optional Blender object to assign and paint splatmap on.
        season: Optional season variant (e.g. "summer", "winter").
        pbr_textures: Optional dict mapping layer name -> dict of texture paths:
            {"ground": {"albedo": "path.png", "roughness": "path.png",
                        "normal": "path.png", "height": "path.png"}, ...}
        enable_displacement: If True, add a displacement output node.

    Returns:
        The created/updated bpy.types.Material.
    """
    if bpy is None:
        raise RuntimeError("create_biome_terrain_material() requires bpy")
    biome_name = _resolve_biome_palette_name(biome_name, season)
    if biome_name not in BIOME_PALETTES_V2:
        logger.warning(
            "Unknown biome '%s'. Available: %s",
            biome_name,
            sorted(BIOME_PALETTES_V2.keys()),
        )
        raise ValueError(f"Unknown biome '{biome_name}'")
    palette = BIOME_PALETTES_V2[biome_name]

    # Reuse the canonical material slot, but always rebuild it so palette updates
    # propagate to existing terrains instead of leaving stale node graphs behind.
    mat_name = f"VB_Terrain_{biome_name}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 1400, 0, "Output")

    # -- Splatmap vertex color input --
    vcol_node = _add_node(tree, "ShaderNodeVertexColor", -1100, -600, "Splatmap")
    vcol_node.layer_name = "VB_TerrainSplatmap"
    separate = _add_node(tree, "ShaderNodeSeparateColor", -900, -600, "Split")
    separate.mode = "RGB"
    links.new(vcol_node.outputs["Color"], separate.inputs["Color"])

    # -- Build PBR layer chains --
    layer_names = ["ground", "slope", "cliff", "special"]
    layer_bsdfs: list[Any] = []
    height_sources: list[Any] = []

    for i, ln in enumerate(layer_names):
        lp = palette[ln]
        y = 500 - i * 400
        layer_pbr = (pbr_textures or {}).get(ln)
        bsdf_node, height_node = _build_pbr_layer_nodes(
            tree, links, lp, ln, y, pbr_textures=layer_pbr,
        )
        layer_bsdfs.append(bsdf_node)
        height_sources.append(height_node)

    # -- HeightBlend: height-based texture transitions between layers --
    height_blend_group = _create_height_blend_group()

    # Ground/Slope blend via HeightBlend
    mix_01 = _add_node(tree, "ShaderNodeMixShader", 400, 300, "Ground/Slope")
    links.new(layer_bsdfs[0].outputs["BSDF"], mix_01.inputs[1])
    links.new(layer_bsdfs[1].outputs["BSDF"], mix_01.inputs[2])

    hb_01 = _add_node(tree, "ShaderNodeGroup", 200, 300, "HB Ground/Slope")
    hb_01.node_tree = height_blend_group
    links.new(height_sources[0].outputs["Fac"], hb_01.inputs["Height_A"])
    links.new(height_sources[1].outputs["Fac"], hb_01.inputs["Height_B"])
    links.new(separate.outputs["Green"], hb_01.inputs["Mask"])
    hb_01.inputs["Blend_Contrast"].default_value = 0.6
    links.new(hb_01.outputs["Result"], mix_01.inputs["Fac"])

    # Ground-Slope / Cliff blend via HeightBlend
    mix_02 = _add_node(tree, "ShaderNodeMixShader", 700, 200, "Add Cliff")
    links.new(mix_01.outputs["Shader"], mix_02.inputs[1])
    links.new(layer_bsdfs[2].outputs["BSDF"], mix_02.inputs[2])

    hb_02 = _add_node(tree, "ShaderNodeGroup", 500, 200, "HB Mix/Cliff")
    hb_02.node_tree = height_blend_group
    links.new(height_sources[1].outputs["Fac"], hb_02.inputs["Height_A"])
    links.new(height_sources[2].outputs["Fac"], hb_02.inputs["Height_B"])
    links.new(separate.outputs["Blue"], hb_02.inputs["Mask"])
    hb_02.inputs["Blend_Contrast"].default_value = 0.5
    links.new(hb_02.outputs["Result"], mix_02.inputs["Fac"])

    # Previous / Special blend via HeightBlend
    mix_03 = _add_node(tree, "ShaderNodeMixShader", 1000, 100, "Add Special")
    links.new(mix_02.outputs["Shader"], mix_03.inputs[1])
    links.new(layer_bsdfs[3].outputs["BSDF"], mix_03.inputs[2])

    hb_03 = _add_node(tree, "ShaderNodeGroup", 800, 100, "HB Mix/Special")
    hb_03.node_tree = height_blend_group
    links.new(height_sources[2].outputs["Fac"], hb_03.inputs["Height_A"])
    links.new(height_sources[3].outputs["Fac"], hb_03.inputs["Height_B"])
    links.new(vcol_node.outputs["Alpha"], hb_03.inputs["Mask"])
    hb_03.inputs["Blend_Contrast"].default_value = 0.5
    links.new(hb_03.outputs["Result"], mix_03.inputs["Fac"])

    # Connect final shader to output
    links.new(mix_03.outputs["Shader"], output.inputs["Surface"])

    # -- Displacement output (optional) --
    if enable_displacement:
        mat.cycles.displacement_method = "BOTH"
        disp_node = _add_node(tree, "ShaderNodeDisplacement", 1200, -200, "Displacement")
        disp_node.inputs["Scale"].default_value = 0.1
        disp_node.inputs["Midlevel"].default_value = 0.5
        # Blend height sources using splatmap weights for displacement
        disp_mix_01 = _add_node(tree, "ShaderNodeMixRGB", 900, -200, "DispMix01")
        disp_mix_01.blend_type = "MIX"
        links.new(separate.outputs["Green"], disp_mix_01.inputs["Fac"])
        links.new(height_sources[0].outputs["Fac"], disp_mix_01.inputs["Color1"])
        links.new(height_sources[1].outputs["Fac"], disp_mix_01.inputs["Color2"])
        disp_mix_02 = _add_node(tree, "ShaderNodeMixRGB", 1000, -300, "DispMix02")
        disp_mix_02.blend_type = "MIX"
        links.new(separate.outputs["Blue"], disp_mix_02.inputs["Fac"])
        links.new(disp_mix_01.outputs["Color"], disp_mix_02.inputs["Color1"])
        links.new(height_sources[2].outputs["Fac"], disp_mix_02.inputs["Color2"])
        disp_mix_03 = _add_node(tree, "ShaderNodeMixRGB", 1100, -400, "DispMix03")
        disp_mix_03.blend_type = "MIX"
        links.new(vcol_node.outputs["Alpha"], disp_mix_03.inputs["Fac"])
        links.new(disp_mix_02.outputs["Color"], disp_mix_03.inputs["Color1"])
        links.new(height_sources[3].outputs["Fac"], disp_mix_03.inputs["Color2"])
        links.new(disp_mix_03.outputs["Color"], disp_node.inputs["Height"])
        links.new(disp_node.outputs["Displacement"], output.inputs["Displacement"])

    # -- Assign to object and paint splatmap --
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is not None and obj.type == "MESH":
            if mat.name not in [s.name for s in obj.data.materials if s is not None]:
                obj.data.materials.append(mat)
            mesh = obj.data
            vcn = "VB_TerrainSplatmap"
            if vcn not in mesh.color_attributes:
                mesh.color_attributes.new(name=vcn, type="FLOAT_COLOR", domain="CORNER")
            vcol = mesh.color_attributes[vcn]
            if hasattr(mesh, "calc_normals_split"):
                mesh.calc_normals_split()
            elif hasattr(mesh, "calc_normals"):
                mesh.calc_normals()
            vl = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
            nl = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]
            fl = [tuple(p.vertices) for p in mesh.polygons]
            weights = auto_assign_terrain_layers(vl, nl, fl, biome_name)
            for poly in mesh.polygons:
                for li in poly.loop_indices:
                    vi_idx = mesh.loops[li].vertex_index
                    w = weights[vi_idx]
                    vcol.data[li].color = (w[0], w[1], w[2], w[3])
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is not None and hasattr(obj.data, "materials"):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

    return mat


def handle_create_biome_terrain(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for the terrain_create_biome_material command."""
    if params.get("list_biomes", False):
        info: dict[str, list[str]] = {}
        for bn, pal in BIOME_PALETTES_V2.items():
            info[bn] = [
                f"{ln}: {ld.get('description', '')}" for ln, ld in pal.items()
            ]
        return {
            "status": "success",
            "result": {
                "available_biomes": sorted(BIOME_PALETTES_V2.keys()),
                "count": len(BIOME_PALETTES_V2),
                "biome_layers": info,
            },
        }
    biome_name = params.get("biome_name")
    if not biome_name:
        return {"status": "error", "error": "'biome_name' is required."}
    season = params.get("season")
    resolved_biome_name = _resolve_biome_palette_name(biome_name, season)
    if resolved_biome_name not in BIOME_PALETTES_V2:
        return {
            "status": "error",
            "error": f"Unknown biome: '{biome_name}'. "
                     f"Available: {sorted(BIOME_PALETTES_V2.keys())}",
        }
    object_name = params.get("object_name")
    mat = create_biome_terrain_material(biome_name, object_name, season=season)
    palette = BIOME_PALETTES_V2[resolved_biome_name]
    layer_info = {ln: ld.get("description", "") for ln, ld in palette.items()}
    rd: dict[str, Any] = {
        "material_name": mat.name,
        "biome": biome_name,
        "resolved_biome": resolved_biome_name,
        "layers": layer_info,
        "node_count": len(mat.node_tree.nodes),
        "splatmap_layer": "VB_TerrainSplatmap",
    }
    if season:
        rd["season"] = season
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is not None:
            rd["object_assigned"] = object_name
            rd["vertex_count"] = len(obj.data.vertices)
        else:
            rd["object_warning"] = f"Object '{object_name}' not found"
    return {"status": "success", "result": rd}
