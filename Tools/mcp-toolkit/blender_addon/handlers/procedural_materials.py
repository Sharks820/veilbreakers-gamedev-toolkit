"""Procedural material node graph system for AAA dark fantasy materials.

Replaces flat single-color Principled BSDF with real Blender shader node
trees using Noise, Voronoi, Wave, Brick, and Bump nodes.

Provides:
  - MATERIAL_LIBRARY: 45+ named material presets (dark fantasy palette)
  - Builder functions per category (stone, wood, metal, organic, terrain, fabric, special)
  - create_procedural_material(): main entry point
  - handle_create_procedural_material(): Blender addon command handler

All colors follow VeilBreakers dark fantasy palette rules:
  - Environment saturation NEVER exceeds 40%
  - Value range for environments: 10-50% (dark world)
  - Primary palette: Dark Stone (#2A2520-#5C5347), Aged Wood (#3B2E1F-#6B5438),
    Rusted Iron (#4A3525-#7A5840)
"""

from __future__ import annotations

from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# VeilBreakers Dark Fantasy Color Palette
# ---------------------------------------------------------------------------

# All colors are linear sRGB [R, G, B, A] tuples.
# Saturation capped at 40% for environments, value range 10-50%.

_DARK_STONE_BASE = (0.12, 0.10, 0.08, 1.0)
_DARK_STONE_LIGHT = (0.20, 0.18, 0.16, 1.0)
_AGED_WOOD_BASE = (0.14, 0.11, 0.08, 1.0)
_AGED_WOOD_LIGHT = (0.22, 0.18, 0.14, 1.0)
_RUSTED_IRON_BASE = (0.17, 0.12, 0.08, 1.0)
_RUSTED_IRON_LIGHT = (0.28, 0.20, 0.14, 1.0)
_BONE_WHITE = (0.35, 0.32, 0.27, 1.0)
_MOSS_GREEN = (0.08, 0.12, 0.06, 1.0)
_BLOOD_RED = (0.25, 0.03, 0.02, 1.0)
_CORRUPTION_PURPLE = (0.12, 0.04, 0.14, 1.0)
_EMBER_ORANGE = (0.6, 0.15, 0.02, 1.0)
_ICE_BLUE = (0.35, 0.45, 0.55, 1.0)
_GOLD_METAL = (1.0, 0.86, 0.57, 1.0)       # Physically-based gold reflectance
_SILVER_METAL = (0.95, 0.93, 0.88, 1.0)    # Physically-based silver reflectance
_BRONZE_METAL = (0.73, 0.55, 0.36, 1.0)    # Physically-based bronze reflectance
_IRON_METAL = (0.56, 0.57, 0.58, 1.0)      # Physically-based iron reflectance
_COPPER_METAL = (0.97, 0.74, 0.62, 1.0)    # Physically-based copper reflectance
_STEEL_METAL = (0.63, 0.62, 0.64, 1.0)     # Physically-based steel reflectance


# ---------------------------------------------------------------------------
# Material Library -- 45+ named material presets
# ---------------------------------------------------------------------------

MATERIAL_LIBRARY: dict[str, dict[str, Any]] = {
    # =======================================================================
    # Architecture -- Stone (7)
    # =======================================================================
    "rough_stone_wall": {
        "base_color": (0.14, 0.12, 0.10, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 8.0,
        "wear_intensity": 0.3,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "smooth_stone": {
        "base_color": (0.18, 0.17, 0.15, 1.0),
        "roughness": 0.55,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 12.0,
        "wear_intensity": 0.1,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "cobblestone_floor": {
        "base_color": (0.15, 0.13, 0.11, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 6.0,
        "wear_intensity": 0.4,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "brick_wall": {
        "base_color": (0.18, 0.13, 0.12, 1.0),  # desaturated: sat 44%->35%
        "roughness": 0.78,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 5.0,
        "wear_intensity": 0.25,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "crumbling_stone": {
        "base_color": (0.16, 0.14, 0.12, 1.0),
        "roughness": 0.92,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 1.8,
        "detail_scale": 7.0,
        "wear_intensity": 0.7,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "mossy_stone": {
        "base_color": (0.12, 0.13, 0.09, 1.0),
        "roughness": 0.82,
        "roughness_variation": 0.18,
        "metallic": 0.0,
        "normal_strength": 1.3,
        "detail_scale": 8.0,
        "wear_intensity": 0.35,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "marble": {
        "base_color": (0.30, 0.28, 0.26, 1.0),
        "roughness": 0.25,
        "roughness_variation": 0.05,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },

    # =======================================================================
    # Architecture -- Wood (5)
    # =======================================================================
    "rough_timber": {
        "base_color": (0.14, 0.12, 0.09, 1.0),  # desaturated: was _AGED_WOOD_BASE (0.14,0.11,0.08) sat 43%->35%
        "roughness": 0.80,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.8,
        "detail_scale": 3.0,
        "wear_intensity": 0.4,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },
    "polished_wood": {
        "base_color": (0.18, 0.15, 0.12, 1.0),  # desaturated: sat 50%->35%
        "roughness": 0.30,
        "roughness_variation": 0.05,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 4.0,
        "wear_intensity": 0.05,
        "node_recipe": "wood",
        "coat_weight": 0.3,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },
    "rotten_wood": {
        "base_color": (0.10, 0.09, 0.07, 1.0),  # desaturated: sat 50%->35%
        "roughness": 0.95,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 1.5,
        "detail_scale": 5.0,
        "wear_intensity": 0.8,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },
    "charred_wood": {
        "base_color": (0.12, 0.09, 0.09, 1.0),  # raised value 4%->12% (min dark range)
        "roughness": 0.90,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 6.0,
        "wear_intensity": 0.6,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },
    "plank_floor": {
        "base_color": _AGED_WOOD_LIGHT,
        "roughness": 0.65,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 2.5,
        "wear_intensity": 0.3,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },

    # =======================================================================
    # Architecture -- Roofing (3)
    # =======================================================================
    "slate_tiles": {
        "base_color": (0.10, 0.10, 0.12, 1.0),
        "roughness": 0.70,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.2,
        "node_recipe": "stone",
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "thatch_roof": {
        "base_color": (0.20, 0.17, 0.13, 1.0),  # desaturated: sat 45%->35%
        "roughness": 0.95,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 10.0,
        "wear_intensity": 0.3,
        "node_recipe": "fabric",
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "wooden_shingles": {
        "base_color": (0.16, 0.13, 0.10, 1.0),  # desaturated: sat 50%->35%
        "roughness": 0.82,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.9,
        "detail_scale": 5.0,
        "wear_intensity": 0.35,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },

    # =======================================================================
    # Metals (5)
    # =======================================================================
    "rusted_iron": {
        "base_color": _IRON_METAL,
        "roughness": 0.65,
        "roughness_variation": 0.25,
        "metallic": 1.0,  # PBR: metals must be 1.0; rust shown via high roughness
        "normal_strength": 0.8,
        "detail_scale": 10.0,
        "wear_intensity": 0.6,
        "node_recipe": "metal",
        "micro_normal_strength": 0.7,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "polished_steel": {
        "base_color": _STEEL_METAL,
        "roughness": 0.20,
        "roughness_variation": 0.05,
        "metallic": 1.0,
        "normal_strength": 0.3,
        "detail_scale": 20.0,
        "wear_intensity": 0.05,
        "node_recipe": "metal",
        "anisotropic": 0.5,
        "micro_normal_strength": 0.7,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "tarnished_bronze": {
        "base_color": _BRONZE_METAL,
        "roughness": 0.50,
        "roughness_variation": 0.15,
        "metallic": 1.0,  # PBR: metals must be 1.0; tarnish shown via roughness/patina
        "normal_strength": 0.5,
        "detail_scale": 12.0,
        "wear_intensity": 0.4,
        "node_recipe": "metal",
        "patina_color": (0.25, 0.45, 0.30, 1.0),
        "micro_normal_strength": 0.7,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "chain_metal": {
        "base_color": _IRON_METAL,
        "roughness": 0.55,
        "roughness_variation": 0.10,
        "metallic": 1.0,  # PBR: metals must be 1.0; use roughness/texture for wear variation
        "normal_strength": 0.6,
        "detail_scale": 15.0,
        "wear_intensity": 0.3,
        "node_recipe": "metal",
        "anisotropic": 0.3,
        "micro_normal_strength": 0.7,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "gold_ornament": {
        "base_color": _GOLD_METAL,
        "roughness": 0.20,
        "roughness_variation": 0.08,
        "metallic": 1.0,
        "normal_strength": 0.4,
        "detail_scale": 18.0,
        "wear_intensity": 0.1,
        "node_recipe": "metal",
        "coat_weight": 0.5,
        "micro_normal_strength": 0.7,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },

    # =======================================================================
    # Organic -- Creature (6)
    # =======================================================================
    "monster_skin": {
        "base_color": (0.18, 0.13, 0.12, 1.0),  # desaturated: sat 44%->35%
        "roughness": 0.65,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 0.8,
        "detail_scale": 12.0,
        "wear_intensity": 0.2,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "sss_color": (0.8, 0.3, 0.2, 1.0),
        "rim_color": (0.05, 0.05, 0.08, 1.0),
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "scales": {
        "base_color": (0.10, 0.12, 0.08, 1.0),
        "roughness": 0.40,
        "roughness_variation": 0.15,
        "metallic": 0.1,
        "normal_strength": 1.2,
        "detail_scale": 15.0,
        "wear_intensity": 0.15,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "chitin_carapace": {
        "base_color": (0.12, 0.10, 0.08, 1.0),  # raised val 8%->12%, desaturated sat 50%->35%
        "roughness": 0.30,
        "roughness_variation": 0.10,
        "metallic": 0.15,
        "normal_strength": 1.0,
        "detail_scale": 10.0,
        "wear_intensity": 0.2,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.002,
        "subsurface_radius": [0.8, 0.3, 0.15],
        "coat_weight": 0.7,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "fur_base": {
        "base_color": (0.15, 0.12, 0.10, 1.0),  # desaturated: sat 47%->33%
        "roughness": 0.90,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 20.0,
        "wear_intensity": 0.1,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "anisotropic": 0.7,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "bone": {
        "base_color": _BONE_WHITE,
        "roughness": 0.60,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 8.0,
        "wear_intensity": 0.15,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "sss_color": (0.9, 0.8, 0.7, 1.0),
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "membrane": {
        "base_color": (0.18, 0.13, 0.12, 1.0),  # desaturated: sat 56%->33%
        "roughness": 0.35,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 6.0,
        "wear_intensity": 0.1,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "transmission": 0.4,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },

    # =======================================================================
    # Organic -- Vegetation (4)
    # =======================================================================
    "bark": {
        "base_color": (0.12, 0.10, 0.08, 1.0),  # desaturated: sat 50%->33%
        "roughness": 0.88,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 1.4,
        "detail_scale": 5.0,
        "wear_intensity": 0.3,
        "node_recipe": "wood",
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.8,
        "macro_normal_strength": 0.6,
    },
    "leaf": {
        "base_color": (0.08, 0.10, 0.07, 1.0),  # desaturated: sat 60%->30%
        "roughness": 0.55,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 15.0,
        "wear_intensity": 0.05,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.003,
        "subsurface_radius": [0.5, 0.4, 0.35],
        "transmission": 0.3,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "moss": {
        "base_color": (0.09, 0.12, 0.08, 1.0),  # desaturated: was _MOSS_GREEN (0.08,0.12,0.06) sat 50%->33%
        "roughness": 0.92,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 18.0,
        "wear_intensity": 0.05,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.003,
        "subsurface_radius": [0.5, 0.4, 0.35],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "mushroom_cap": {
        "base_color": (0.18, 0.15, 0.12, 1.0),  # desaturated: sat 50%->33%
        "roughness": 0.45,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 10.0,
        "wear_intensity": 0.1,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "sss_color": (0.6, 0.5, 0.3, 1.0),
        "transmission": 0.1,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },

    # =======================================================================
    # Terrain (6)
    # =======================================================================
    "grass": {
        "base_color": (0.08, 0.10, 0.07, 1.0),  # desaturated: sat 60%->30%
        "roughness": 0.85,
        "roughness_variation": 0.10,
        "metallic": 0.0,
        "normal_strength": 0.4,
        "detail_scale": 12.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "dirt": {
        "base_color": (0.12, 0.10, 0.08, 1.0),  # desaturated: sat 50%->33%
        "roughness": 0.90,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.6,
        "detail_scale": 8.0,
        "wear_intensity": 0.2,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "mud": {
        "base_color": (0.10, 0.08, 0.07, 1.0),  # desaturated: sat 60%->30%
        "roughness": 0.50,
        "roughness_variation": 0.20,
        "metallic": 0.0,
        "normal_strength": 0.8,
        "detail_scale": 6.0,
        "wear_intensity": 0.3,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "snow": {
        "base_color": (0.45, 0.45, 0.48, 1.0),
        "roughness": 0.70,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 10.0,
        "wear_intensity": 0.02,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "sand": {
        "base_color": (0.28, 0.25, 0.18, 1.0),  # desaturated: sat 43%->36%
        "roughness": 0.82,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 15.0,
        "wear_intensity": 0.05,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "cliff_rock": {
        "base_color": (0.14, 0.13, 0.11, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.6,
        "detail_scale": 4.0,
        "wear_intensity": 0.4,
        "node_recipe": "terrain",
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },

    # =======================================================================
    # Fabric (3)
    # =======================================================================
    "burlap_cloth": {
        "base_color": (0.20, 0.17, 0.13, 1.0),  # desaturated: sat 50%->35%
        "roughness": 0.92,
        "roughness_variation": 0.05,
        "metallic": 0.0,
        "normal_strength": 0.7,
        "detail_scale": 20.0,
        "wear_intensity": 0.2,
        "node_recipe": "fabric",
        "subsurface": 1.0,
        "subsurface_scale": 0.003,
        "subsurface_radius": [0.5, 0.4, 0.35],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "leather": {
        "base_color": (0.14, 0.11, 0.09, 1.0),  # desaturated: sat 50%->36%
        "roughness": 0.60,
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 12.0,
        "wear_intensity": 0.25,
        "node_recipe": "fabric",
        "subsurface": 1.0,
        "subsurface_scale": 0.002,
        "subsurface_radius": [0.8, 0.3, 0.15],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "silk": {
        "base_color": (0.22, 0.18, 0.20, 1.0),
        "roughness": 0.25,
        "roughness_variation": 0.08,
        "metallic": 0.0,
        "normal_strength": 0.2,
        "detail_scale": 25.0,
        "wear_intensity": 0.05,
        "node_recipe": "fabric",
        "subsurface": 1.0,
        "subsurface_scale": 0.003,
        "subsurface_radius": [0.5, 0.4, 0.35],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },

    # =======================================================================
    # Special (6)
    # =======================================================================
    "corruption_overlay": {
        "base_color": _CORRUPTION_PURPLE,
        "roughness": 0.55,
        "roughness_variation": 0.20,
        "metallic": 0.1,
        "normal_strength": 1.0,
        "detail_scale": 6.0,
        "wear_intensity": 0.5,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "emission_color": (0.12, 0.04, 0.14, 1.0),
        "emission_strength": 0.3,
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
    "lava_ember": {
        "base_color": _EMBER_ORANGE,
        "roughness": 0.70,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 1.2,
        "detail_scale": 4.0,
        "wear_intensity": 0.4,
        "node_recipe": "terrain",
        "emission_color": (1.0, 0.4, 0.1, 1.0),
        "emission_strength": 2.0,
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 1.2,
    },
    "ice_crystal": {
        "base_color": (0.32, 0.40, 0.50, 1.0),
        "roughness": 0.10,
        "roughness_variation": 0.05,
        "metallic": 0.0,  # PBR: ice is dielectric, not metallic
        "normal_strength": 0.4,
        "detail_scale": 8.0,
        "wear_intensity": 0.02,
        "node_recipe": "stone",
        "emission_color": (0.6, 0.8, 1.0, 1.0),
        "emission_strength": 0.1,
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "glass": {
        "base_color": (0.40, 0.42, 0.44, 1.0),
        "roughness": 0.05,
        "roughness_variation": 0.02,
        "metallic": 0.0,  # PBR: glass is dielectric, not metallic
        "normal_strength": 0.1,
        "detail_scale": 4.0,
        "wear_intensity": 0.0,
        "node_recipe": "organic",
        "transmission": 0.9,
        "ior": 1.45,
        "micro_normal_strength": 0.05,
        "meso_normal_strength": 0.1,
        "macro_normal_strength": 0.05,
    },
    "water_surface": {
        "base_color": (0.032, 0.056, 0.08, 1.0),
        "roughness": 0.05,
        "roughness_variation": 0.02,
        "metallic": 0.0,
        "normal_strength": 0.5,
        "detail_scale": 3.0,
        "wear_intensity": 0.0,
        "node_recipe": "organic",
        "transmission": 0.7,
        "ior": 1.333,
        "micro_normal_strength": 0.3,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.2,
    },
    "blood_splatter": {
        "base_color": (0.25, 0.17, 0.16, 1.0),  # desaturated: was _BLOOD_RED (0.25,0.03,0.02) sat 92%->36%
        "roughness": 0.40,
        "roughness_variation": 0.15,
        "metallic": 0.0,
        "normal_strength": 0.3,
        "detail_scale": 5.0,
        "wear_intensity": 0.1,
        "node_recipe": "organic",
        "subsurface": 1.0,
        "subsurface_scale": 0.005,
        "subsurface_radius": [1.0, 0.2, 0.1],
        "micro_normal_strength": 0.5,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.5,
    },
}

# Required keys every material entry must have.
REQUIRED_MATERIAL_KEYS = frozenset({
    "base_color",
    "roughness",
    "roughness_variation",
    "metallic",
    "normal_strength",
    "detail_scale",
    "wear_intensity",
    "node_recipe",
})

# Valid node_recipe values -- each must have a matching builder function.
VALID_RECIPES = frozenset({"stone", "wood", "metal", "organic", "terrain", "fabric"})


# ---------------------------------------------------------------------------
# Node positioning helpers
# ---------------------------------------------------------------------------

def _place(node: Any, x: float, y: float) -> None:
    """Set node location for readable graph layout."""
    node.location = (x, y)


def _add_node(tree: Any, node_type: str, x: float, y: float,
              label: str = "") -> Any:
    """Create a shader node, position it, and optionally label it."""
    node = tree.nodes.new(type=node_type)
    _place(node, x, y)
    if label:
        node.label = label
    return node


# ---------------------------------------------------------------------------
# Version-aware Principled BSDF socket access
# ---------------------------------------------------------------------------

# Blender 4.0+ renamed several Principled BSDF sockets.
_BSDF_SOCKET_FALLBACKS: dict[str, str] = {
    "Subsurface Weight": "Subsurface",
    "Specular IOR Level": "Specular",
    "Transmission Weight": "Transmission",
    "Coat Weight": "Clearcoat",
    "Sheen Weight": "Sheen",
    "Emission Color": "Emission",
}


def _get_bsdf_input(bsdf: Any, name: str) -> Any:
    """Get a Principled BSDF input by name, with Blender 3.x fallback."""
    sock = bsdf.inputs.get(name)
    if sock is not None:
        return sock
    fallback = _BSDF_SOCKET_FALLBACKS.get(name)
    if fallback:
        sock = bsdf.inputs.get(fallback)
        if sock is not None:
            return sock
    # Last resort: return the original name lookup (will be None)
    return bsdf.inputs.get(name)


# ---------------------------------------------------------------------------
# 3-Layer Micro-Normal Chain Builder (AAA quality)
# ---------------------------------------------------------------------------

def _build_normal_chain(
    nodes: Any,
    links: Any,
    tree: Any,
    bsdf: Any,
    mapping_output: Any,
    params: dict[str, Any],
) -> None:
    """Build a 3-layer micro/meso/macro normal chain for AAA surface detail.

    Creates three cascading Bump nodes:
      - Micro layer: Noise (scale 40-80) for fine pores/scratches
      - Meso layer: Voronoi (scale 10-20) for mid-frequency detail
      - Macro layer: Noise (scale 2-5) for large-scale surface undulation

    Each layer's Bump Normal output feeds into the next layer's Normal input,
    producing a cascaded normal chain that the BSDF reads from the final
    (macro) layer.

    Args:
        nodes: Node tree nodes collection.
        links: Node tree links collection.
        tree: The node tree (for _add_node).
        bsdf: Principled BSDF node (final normal connects here).
        mapping_output: The mapping node Vector output socket.
        params: Material params dict with optional micro/meso/macro_normal_strength.
    """
    detail_scale = params.get("detail_scale", 8.0)

    # -- Micro layer: fine-grain detail (pores, scratches, grain) --
    noise_micro = _add_node(tree, "ShaderNodeTexNoise", -900, -800, "Micro Noise")
    noise_micro.inputs["Scale"].default_value = max(40.0, detail_scale * 6.0)
    noise_micro.inputs["Detail"].default_value = 12.0
    noise_micro.inputs["Roughness"].default_value = 0.7
    links.new(mapping_output, noise_micro.inputs["Vector"])

    bump_micro = _add_node(tree, "ShaderNodeBump", -700, -800, "Micro Bump")
    bump_micro.inputs["Strength"].default_value = params.get(
        "micro_normal_strength", 0.3
    )
    bump_micro.inputs["Distance"].default_value = 0.002
    links.new(noise_micro.outputs["Fac"], bump_micro.inputs["Height"])

    # -- Meso layer: mid-frequency detail (cracks, veins, cell patterns) --
    voronoi_meso = _add_node(tree, "ShaderNodeTexVoronoi", -900, -1000, "Meso Voronoi")
    voronoi_meso.inputs["Scale"].default_value = max(10.0, detail_scale * 1.5)
    voronoi_meso.voronoi_dimensions = "3D"
    links.new(mapping_output, voronoi_meso.inputs["Vector"])

    bump_meso = _add_node(tree, "ShaderNodeBump", -700, -1000, "Meso Bump")
    bump_meso.inputs["Strength"].default_value = params.get(
        "meso_normal_strength", 0.5
    )
    bump_meso.inputs["Distance"].default_value = 0.005
    links.new(voronoi_meso.outputs["Distance"], bump_meso.inputs["Height"])
    # Chain: micro -> meso
    links.new(bump_micro.outputs["Normal"], bump_meso.inputs["Normal"])

    # -- Macro layer: large-scale undulation (worn edges, warping) --
    noise_macro = _add_node(tree, "ShaderNodeTexNoise", -900, -1200, "Macro Noise")
    noise_macro.inputs["Scale"].default_value = max(2.0, detail_scale * 0.3)
    noise_macro.inputs["Detail"].default_value = 4.0
    noise_macro.inputs["Roughness"].default_value = 0.5
    links.new(mapping_output, noise_macro.inputs["Vector"])

    bump_macro = _add_node(tree, "ShaderNodeBump", -700, -1200, "Macro Bump")
    bump_macro.inputs["Strength"].default_value = params.get(
        "macro_normal_strength", 0.8
    )
    bump_macro.inputs["Distance"].default_value = 0.02
    links.new(noise_macro.outputs["Fac"], bump_macro.inputs["Height"])
    # Chain: meso -> macro
    links.new(bump_meso.outputs["Normal"], bump_macro.inputs["Normal"])

    # Connect final macro normal output -> BSDF Normal
    links.new(bump_macro.outputs["Normal"], bsdf.inputs["Normal"])


# ---------------------------------------------------------------------------
# Builder: Stone / Masonry
# ---------------------------------------------------------------------------

def build_stone_material(mat: Any, params: dict[str, Any]) -> None:
    """Build stone/masonry node graph.

    Node graph structure:
      - Voronoi Texture (scale from detail_scale) -> ColorRamp -> block pattern
      - Noise Texture (scale 15) -> ColorRamp -> mortar / surface detail
      - Noise Texture (surface variation) -> MixRGB with base color -> surface color variation
      - Combined Noise -> Bump Node -> Normal input on Principled BSDF
      - Secondary Noise -> Multiply with roughness -> roughness variation
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    # Clear default nodes
    nodes.clear()

    # -- Output --
    output = _add_node(tree, "ShaderNodeOutputMaterial", 400, 0, "Output")

    # -- Principled BSDF --
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 0, "Principled BSDF")
    bsdf.inputs["Base Color"].default_value = params["base_color"]
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    bsdf.inputs["Metallic"].default_value = params["metallic"]

    # Emission for glowing stone/crystal materials (ice crystal, etc.)
    emission_strength_val = params.get("emission_strength", 0.0)
    if emission_strength_val > 0.0:
        emission_input = _get_bsdf_input(bsdf, "Emission Color")
        if emission_input is not None:
            emission_input.default_value = params.get(
                "emission_color", (0.0, 0.0, 0.0, 1.0)
            )
        emission_str_input = bsdf.inputs.get("Emission Strength")
        if emission_str_input is not None:
            emission_str_input.default_value = emission_strength_val

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # -- Texture Coordinate + Mapping --
    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1200, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1000, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 8.0)

    # -- Voronoi Texture: Block pattern --
    voronoi = _add_node(tree, "ShaderNodeTexVoronoi", -800, 200, "Block Pattern")
    voronoi.inputs["Scale"].default_value = detail_scale
    voronoi.voronoi_dimensions = "3D"
    links.new(mapping.outputs["Vector"], voronoi.inputs["Vector"])

    # -- ColorRamp for block edges --
    ramp_blocks = _add_node(tree, "ShaderNodeValToRGB", -600, 200, "Block Edges")
    ramp_blocks.color_ramp.elements[0].position = 0.4
    ramp_blocks.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_blocks.color_ramp.elements[1].position = 0.6
    ramp_blocks.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(voronoi.outputs["Distance"], ramp_blocks.inputs["Fac"])

    # -- Noise Texture: Mortar lines / surface detail --
    noise_mortar = _add_node(tree, "ShaderNodeTexNoise", -800, -100, "Mortar Detail")
    noise_mortar.inputs["Scale"].default_value = 15.0
    noise_mortar.inputs["Detail"].default_value = 6.0
    noise_mortar.inputs["Roughness"].default_value = 0.7
    links.new(mapping.outputs["Vector"], noise_mortar.inputs["Vector"])

    # -- ColorRamp for mortar --
    ramp_mortar = _add_node(tree, "ShaderNodeValToRGB", -600, -100, "Mortar Lines")
    ramp_mortar.color_ramp.elements[0].position = 0.3
    ramp_mortar.color_ramp.elements[0].color = (0.05, 0.04, 0.03, 1.0)
    ramp_mortar.color_ramp.elements[1].position = 0.7
    ramp_mortar.color_ramp.elements[1].color = (0.15, 0.13, 0.11, 1.0)
    links.new(noise_mortar.outputs["Fac"], ramp_mortar.inputs["Fac"])

    # -- Noise Texture: Surface variation (replaces deprecated Musgrave) --
    surface_var = _add_node(tree, "ShaderNodeTexNoise", -800, -400,
                            "Surface Variation")
    surface_var.inputs["Scale"].default_value = detail_scale * 2.0
    surface_var.inputs["Detail"].default_value = 8.0
    surface_var.inputs["Roughness"].default_value = 0.7
    links.new(mapping.outputs["Vector"], surface_var.inputs["Vector"])

    # -- MixRGB: Blend base color with surface variation --
    mix_color = _add_node(tree, "ShaderNodeMixRGB", -400, 100,
                          "Color Variation")
    mix_color.blend_type = "OVERLAY"
    links.new(surface_var.outputs["Fac"], mix_color.inputs["Fac"])
    links.new(ramp_blocks.outputs["Color"], mix_color.inputs["Color1"])
    links.new(ramp_mortar.outputs["Color"], mix_color.inputs["Color2"])

    # -- MixRGB: Apply base color tint --
    mix_base = _add_node(tree, "ShaderNodeMixRGB", -200, 100, "Base Color Mix")
    mix_base.blend_type = "MULTIPLY"
    mix_base.inputs["Fac"].default_value = 1.0
    bc = params["base_color"]
    # Scale the base color for multiply blending -- clamped to avoid clipping
    mix_base.inputs["Color1"].default_value = (
        min(1.0, bc[0] * 2.5),
        min(1.0, bc[1] * 2.5),
        min(1.0, bc[2] * 2.5),
        1.0,
    )
    links.new(mix_color.outputs["Color"], mix_base.inputs["Color2"])
    links.new(mix_base.outputs["Color"], bsdf.inputs["Base Color"])

    # -- Roughness variation --
    noise_rough = _add_node(tree, "ShaderNodeTexNoise", -600, -400,
                            "Roughness Noise")
    noise_rough.inputs["Scale"].default_value = detail_scale * 3.0
    noise_rough.inputs["Detail"].default_value = 4.0
    links.new(mapping.outputs["Vector"], noise_rough.inputs["Vector"])

    math_rough = _add_node(tree, "ShaderNodeMath", -400, -400, "Roughness Map")
    math_rough.operation = "MULTIPLY_ADD"
    math_rough.inputs[1].default_value = params.get("roughness_variation", 0.15)
    math_rough.inputs[2].default_value = params["roughness"]
    links.new(noise_rough.outputs["Fac"], math_rough.inputs[0])
    links.new(math_rough.outputs["Value"], bsdf.inputs["Roughness"])

    # -- 3-Layer Normal Chain (AAA quality) --
    _build_normal_chain(nodes, links, tree, bsdf,
                        mapping.outputs["Vector"], params)


# ---------------------------------------------------------------------------
# Builder: Wood
# ---------------------------------------------------------------------------

def build_wood_material(mat: Any, params: dict[str, Any]) -> None:
    """Build wood grain node graph.

    Node graph structure:
      - Wave Texture (bands type) -> ColorRamp -> grain pattern
      - Noise Texture (fine detail, high scale) -> MixRGB overlay -> wood knots
      - Bump from wave pattern -> Normal input
      - Noise -> roughness variation
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 400, 0, "Output")
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 0, "Principled BSDF")
    bsdf.inputs["Base Color"].default_value = params["base_color"]
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    bsdf.inputs["Metallic"].default_value = params["metallic"]

    # Coat weight for lacquered / polished wood surfaces
    coat_val = params.get("coat_weight", 0.0)
    if coat_val > 0.0:
        coat_input = _get_bsdf_input(bsdf, "Coat Weight")
        if coat_input is not None:
            coat_input.default_value = coat_val

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1200, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1000, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 3.0)

    # -- Wave Texture: Wood grain --
    wave = _add_node(tree, "ShaderNodeTexWave", -800, 200, "Wood Grain")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = detail_scale
    wave.inputs["Distortion"].default_value = 4.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 1.5
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])

    # -- ColorRamp: Grain color variation --
    ramp_grain = _add_node(tree, "ShaderNodeValToRGB", -600, 200, "Grain Color")
    bc = params["base_color"]
    # Darker grain lines
    ramp_grain.color_ramp.elements[0].position = 0.3
    ramp_grain.color_ramp.elements[0].color = (bc[0] * 0.5, bc[1] * 0.5,
                                                bc[2] * 0.5, 1.0)
    # Lighter wood between
    ramp_grain.color_ramp.elements[1].position = 0.7
    ramp_grain.color_ramp.elements[1].color = (bc[0] * 1.5, bc[1] * 1.5,
                                                bc[2] * 1.5, 1.0)
    links.new(wave.outputs["Fac"], ramp_grain.inputs["Fac"])

    # -- Noise Texture: Knots and imperfections --
    noise_knots = _add_node(tree, "ShaderNodeTexNoise", -800, -100, "Knots")
    noise_knots.inputs["Scale"].default_value = detail_scale * 0.5
    noise_knots.inputs["Detail"].default_value = 8.0
    noise_knots.inputs["Roughness"].default_value = 0.8
    noise_knots.inputs["Distortion"].default_value = 1.5
    links.new(mapping.outputs["Vector"], noise_knots.inputs["Vector"])

    # -- MixRGB: Overlay knots onto grain --
    mix_knots = _add_node(tree, "ShaderNodeMixRGB", -400, 100, "Knot Overlay")
    mix_knots.blend_type = "OVERLAY"
    mix_knots.inputs["Fac"].default_value = params.get("wear_intensity", 0.3)
    links.new(ramp_grain.outputs["Color"], mix_knots.inputs["Color1"])
    links.new(noise_knots.outputs["Color"], mix_knots.inputs["Color2"])
    links.new(mix_knots.outputs["Color"], bsdf.inputs["Base Color"])

    # -- Roughness variation --
    noise_rough = _add_node(tree, "ShaderNodeTexNoise", -600, -300,
                            "Roughness Noise")
    noise_rough.inputs["Scale"].default_value = detail_scale * 5.0
    noise_rough.inputs["Detail"].default_value = 3.0
    links.new(mapping.outputs["Vector"], noise_rough.inputs["Vector"])

    math_rough = _add_node(tree, "ShaderNodeMath", -400, -300, "Roughness Map")
    math_rough.operation = "MULTIPLY_ADD"
    math_rough.inputs[1].default_value = params.get("roughness_variation", 0.12)
    math_rough.inputs[2].default_value = params["roughness"]
    links.new(noise_rough.outputs["Fac"], math_rough.inputs[0])
    links.new(math_rough.outputs["Value"], bsdf.inputs["Roughness"])

    # -- 3-Layer Normal Chain (AAA quality) --
    _build_normal_chain(nodes, links, tree, bsdf,
                        mapping.outputs["Vector"], params)


# ---------------------------------------------------------------------------
# Builder: Metal (rusted / clean)
# ---------------------------------------------------------------------------

def build_metal_material(mat: Any, params: dict[str, Any]) -> None:
    """Build metal node graph with rust/patina variation.

    Node graph structure:
      - Noise Texture (large scale) -> ColorRamp -> rust mask
      - Mix Shader: clean metal (low rough, high metallic) + rust (high rough, low metallic)
      - Fine Noise -> roughness detail for scratches
      - Bump from noise -> surface imperfections
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 600, 0, "Output")

    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1200, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1000, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 10.0)
    wear = params.get("wear_intensity", 0.5)
    bc = params["base_color"]

    # -- Clean metal BSDF --
    bsdf_clean = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 200,
                           "Clean Metal")
    bsdf_clean.inputs["Base Color"].default_value = bc
    bsdf_clean.inputs["Roughness"].default_value = max(0.05, params["roughness"] * 0.3)
    bsdf_clean.inputs["Metallic"].default_value = params["metallic"]

    # Anisotropic roughness for brushed metal / hair highlights
    aniso_val = params.get("anisotropic", 0.0)
    if aniso_val > 0.0:
        aniso_input = _get_bsdf_input(bsdf_clean, "Anisotropic")
        if aniso_input is not None:
            aniso_input.default_value = aniso_val

    # Coat weight for lacquered / polished metal surfaces
    coat_val = params.get("coat_weight", 0.0)
    if coat_val > 0.0:
        coat_input = _get_bsdf_input(bsdf_clean, "Coat Weight")
        if coat_input is not None:
            coat_input.default_value = coat_val

    # -- Rusted/worn BSDF --
    bsdf_rust = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, -200,
                          "Rust/Wear")
    patina_color = params.get("patina_color")
    if patina_color:
        rust_color = (patina_color[0], patina_color[1], patina_color[2], 1.0)
    else:
        rust_color = (bc[0] * 0.6, bc[1] * 0.4, bc[2] * 0.3, 1.0)
    bsdf_rust.inputs["Base Color"].default_value = rust_color
    bsdf_rust.inputs["Roughness"].default_value = min(1.0, params["roughness"] + 0.3)
    bsdf_rust.inputs["Metallic"].default_value = max(0.0, params["metallic"] - 0.5)

    # -- Noise: Rust pattern mask --
    noise_rust = _add_node(tree, "ShaderNodeTexNoise", -800, 0, "Rust Pattern")
    noise_rust.inputs["Scale"].default_value = detail_scale * 0.5
    noise_rust.inputs["Detail"].default_value = 10.0
    noise_rust.inputs["Roughness"].default_value = 0.6
    noise_rust.inputs["Distortion"].default_value = 0.5
    links.new(mapping.outputs["Vector"], noise_rust.inputs["Vector"])

    # -- ColorRamp: Rust threshold --
    ramp_rust = _add_node(tree, "ShaderNodeValToRGB", -600, 0, "Rust Mask")
    ramp_rust.color_ramp.elements[0].position = 0.5 - wear * 0.3
    ramp_rust.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_rust.color_ramp.elements[1].position = 0.5 + wear * 0.3
    ramp_rust.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(noise_rust.outputs["Fac"], ramp_rust.inputs["Fac"])

    # -- Mix Shader: Clean + Rust --
    mix_shader = _add_node(tree, "ShaderNodeMixShader", 350, 0, "Clean/Rust Mix")
    links.new(ramp_rust.outputs["Color"], mix_shader.inputs["Fac"])
    links.new(bsdf_clean.outputs["BSDF"], mix_shader.inputs[1])
    links.new(bsdf_rust.outputs["BSDF"], mix_shader.inputs[2])
    links.new(mix_shader.outputs["Shader"], output.inputs["Surface"])

    # -- 3-Layer Normal Chain (AAA quality) --
    # Build chain connected to clean BSDF, also link to rust BSDF
    _build_normal_chain(nodes, links, tree, bsdf_clean,
                        mapping.outputs["Vector"], params)
    # Find the Macro Bump node (last in chain) to also feed rust BSDF
    macro_bump = None
    for node in nodes:
        if hasattr(node, 'label') and node.label == "Macro Bump":
            macro_bump = node
            break
    if macro_bump is not None:
        links.new(macro_bump.outputs["Normal"], bsdf_rust.inputs["Normal"])


# ---------------------------------------------------------------------------
# Builder: Organic (creature surfaces)
# ---------------------------------------------------------------------------

def build_organic_material(mat: Any, params: dict[str, Any]) -> None:
    """Build organic creature surface node graph.

    Node graph structure:
      - Subsurface scattering setup for fleshy appearance
      - Voronoi Texture -> cell/scale/pore detail
      - Noise Texture -> roughness variation (wet/dry areas)
      - Bump from combined textures -> surface detail
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 400, 0, "Output")
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 0, "Principled BSDF")
    bc = params["base_color"]
    bsdf.inputs["Base Color"].default_value = bc
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    bsdf.inputs["Metallic"].default_value = params["metallic"]

    # Subsurface scattering for organic look (parameterized per-material)
    # Weight=1.0 enables SSS; actual scatter distance controlled by Scale
    sss_input = _get_bsdf_input(bsdf, "Subsurface Weight")
    if sss_input is not None:
        sss_input.default_value = params.get("subsurface", 1.0)
    # Subsurface Scale controls scatter distance (physically-based)
    sss_scale_input = bsdf.inputs.get("Subsurface Scale")
    if sss_scale_input is not None:
        sss_scale_input.default_value = params.get("subsurface_scale", 0.005)
    # Subsurface Radius for chromatic SSS (R, G, B scatter distances)
    sss_radius_input = bsdf.inputs.get("Subsurface Radius")
    if sss_radius_input is not None:
        radius = params.get("subsurface_radius", [1.0, 0.2, 0.1])
        sss_radius_input.default_value = radius
    # Subsurface color -- per-material or derived from base color
    sss_color_input = bsdf.inputs.get("Subsurface Color")
    if sss_color_input is not None:
        sss_color_input.default_value = params.get(
            "sss_color", (bc[0] * 1.5, bc[1] * 0.5, bc[2] * 0.4, 1.0)
        )

    # Transmission for translucent organic materials (membrane, leaf, mushroom)
    transmission_input = _get_bsdf_input(bsdf, "Transmission Weight")
    if transmission_input is not None:
        transmission_input.default_value = params.get("transmission", 0.0)

    # IOR for refractive materials (glass, water)
    ior_val = params.get("ior")
    if ior_val is not None:
        ior_input = bsdf.inputs.get("IOR")
        if ior_input is not None:
            ior_input.default_value = ior_val

    # Coat weight for glossy organic surfaces (chitin carapace, polished wood)
    coat_input = _get_bsdf_input(bsdf, "Coat Weight")
    if coat_input is not None:
        coat_input.default_value = params.get("coat_weight", 0.0)

    # Anisotropic roughness for hair/fur highlights
    aniso_val = params.get("anisotropic", 0.0)
    if aniso_val > 0.0:
        aniso_input = _get_bsdf_input(bsdf, "Anisotropic")
        if aniso_input is not None:
            aniso_input.default_value = aniso_val

    # Emission for magic/glowing organic materials
    emission_strength_val = params.get("emission_strength", 0.0)
    if emission_strength_val > 0.0:
        emission_input = _get_bsdf_input(bsdf, "Emission Color")
        if emission_input is not None:
            emission_input.default_value = params.get(
                "emission_color", (0.0, 0.0, 0.0, 1.0)
            )
        emission_str_input = bsdf.inputs.get("Emission Strength")
        if emission_str_input is not None:
            emission_str_input.default_value = emission_strength_val

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1200, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1000, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 12.0)

    # -- Voronoi: Pore / scale / cell pattern --
    voronoi = _add_node(tree, "ShaderNodeTexVoronoi", -800, 200, "Pore/Scale")
    voronoi.inputs["Scale"].default_value = detail_scale
    voronoi.voronoi_dimensions = "3D"
    voronoi.feature = "F1"
    links.new(mapping.outputs["Vector"], voronoi.inputs["Vector"])

    # -- Noise: Skin/surface variation --
    noise_skin = _add_node(tree, "ShaderNodeTexNoise", -800, -100, "Skin Detail")
    noise_skin.inputs["Scale"].default_value = detail_scale * 2.0
    noise_skin.inputs["Detail"].default_value = 10.0
    noise_skin.inputs["Roughness"].default_value = 0.65
    links.new(mapping.outputs["Vector"], noise_skin.inputs["Vector"])

    # -- MixRGB: Color variation using voronoi and noise --
    mix_color = _add_node(tree, "ShaderNodeMixRGB", -400, 100, "Color Variation")
    mix_color.blend_type = "OVERLAY"
    mix_color.inputs["Fac"].default_value = 0.25
    mix_color.inputs["Color1"].default_value = bc
    links.new(noise_skin.outputs["Color"], mix_color.inputs["Color2"])
    links.new(mix_color.outputs["Color"], bsdf.inputs["Base Color"])

    # -- Roughness variation: Wet / dry areas --
    noise_rough = _add_node(tree, "ShaderNodeTexNoise", -600, -300,
                            "Wet/Dry Areas")
    noise_rough.inputs["Scale"].default_value = detail_scale * 0.5
    noise_rough.inputs["Detail"].default_value = 4.0
    links.new(mapping.outputs["Vector"], noise_rough.inputs["Vector"])

    math_rough = _add_node(tree, "ShaderNodeMath", -400, -300, "Roughness Map")
    math_rough.operation = "MULTIPLY_ADD"
    math_rough.inputs[1].default_value = params.get("roughness_variation", 0.15)
    math_rough.inputs[2].default_value = params["roughness"]
    links.new(noise_rough.outputs["Fac"], math_rough.inputs[0])
    links.new(math_rough.outputs["Value"], bsdf.inputs["Roughness"])

    # -- 3-Layer Normal Chain (AAA quality) --
    _build_normal_chain(nodes, links, tree, bsdf,
                        mapping.outputs["Vector"], params)

    # -- Fresnel / rim lighting for creature silhouette readability --
    rim_color = params.get("rim_color")
    if rim_color is not None:
        layer_weight = _add_node(tree, "ShaderNodeLayerWeight", -600, -700,
                                 "Rim Fresnel")
        layer_weight.inputs["Blend"].default_value = 0.3

        mix_rim = _add_node(tree, "ShaderNodeMixRGB", -400, -700, "Rim Mix")
        mix_rim.inputs[1].default_value = (0.0, 0.0, 0.0, 1.0)
        mix_rim.inputs[2].default_value = rim_color
        links.new(layer_weight.outputs["Facing"], mix_rim.inputs["Fac"])

        emission_rim = _get_bsdf_input(bsdf, "Emission Color")
        if emission_rim is not None:
            links.new(mix_rim.outputs[0], emission_rim)


# ---------------------------------------------------------------------------
# Builder: Terrain (ground surfaces)
# ---------------------------------------------------------------------------

def build_terrain_material(mat: Any, params: dict[str, Any]) -> None:
    """Build terrain/ground surface node graph.

    Node graph structure:
      - Multi-scale noise blending (large + medium + fine)
      - Geometry node -> Normal -> slope-based mixing
      - Combined noise -> color variation
      - Bump from multi-scale noise
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 400, 0, "Output")
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 0, "Principled BSDF")
    bc = params["base_color"]
    bsdf.inputs["Base Color"].default_value = bc
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    bsdf.inputs["Metallic"].default_value = params["metallic"]

    # Transmission for translucent terrain materials (leaf ground cover, etc.)
    transmission_input = _get_bsdf_input(bsdf, "Transmission Weight")
    if transmission_input is not None:
        transmission_input.default_value = params.get("transmission", 0.0)

    # Emission for glowing terrain (lava, magic ground effects)
    emission_strength_val = params.get("emission_strength", 0.0)
    if emission_strength_val > 0.0:
        emission_input = _get_bsdf_input(bsdf, "Emission Color")
        if emission_input is not None:
            emission_input.default_value = params.get(
                "emission_color", (0.0, 0.0, 0.0, 1.0)
            )
        emission_str_input = bsdf.inputs.get("Emission Strength")
        if emission_str_input is not None:
            emission_str_input.default_value = emission_strength_val

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1400, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1200, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 8.0)

    # -- Large-scale Noise: Terrain macro variation --
    noise_large = _add_node(tree, "ShaderNodeTexNoise", -1000, 300,
                            "Macro Noise")
    noise_large.inputs["Scale"].default_value = detail_scale * 0.3
    noise_large.inputs["Detail"].default_value = 6.0
    noise_large.inputs["Roughness"].default_value = 0.5
    links.new(mapping.outputs["Vector"], noise_large.inputs["Vector"])

    # -- Medium-scale Noise: Mid-frequency detail --
    noise_med = _add_node(tree, "ShaderNodeTexNoise", -1000, 0, "Mid Noise")
    noise_med.inputs["Scale"].default_value = detail_scale
    noise_med.inputs["Detail"].default_value = 8.0
    noise_med.inputs["Roughness"].default_value = 0.6
    links.new(mapping.outputs["Vector"], noise_med.inputs["Vector"])

    # -- Fine-scale Noise: Micro detail --
    noise_fine = _add_node(tree, "ShaderNodeTexNoise", -1000, -300,
                           "Fine Noise")
    noise_fine.inputs["Scale"].default_value = detail_scale * 4.0
    noise_fine.inputs["Detail"].default_value = 12.0
    noise_fine.inputs["Roughness"].default_value = 0.7
    links.new(mapping.outputs["Vector"], noise_fine.inputs["Vector"])

    # -- Mix large + medium --
    mix_lm = _add_node(tree, "ShaderNodeMixRGB", -700, 150, "Large+Med Mix")
    mix_lm.blend_type = "OVERLAY"
    mix_lm.inputs["Fac"].default_value = 0.5
    links.new(noise_large.outputs["Color"], mix_lm.inputs["Color1"])
    links.new(noise_med.outputs["Color"], mix_lm.inputs["Color2"])

    # -- Mix result + fine --
    mix_all = _add_node(tree, "ShaderNodeMixRGB", -500, 100, "All Noise Mix")
    mix_all.blend_type = "OVERLAY"
    mix_all.inputs["Fac"].default_value = 0.3
    links.new(mix_lm.outputs["Color"], mix_all.inputs["Color1"])
    links.new(noise_fine.outputs["Color"], mix_all.inputs["Color2"])

    # -- Geometry node for slope-based mixing --
    geometry = _add_node(tree, "ShaderNodeNewGeometry", -800, -500, "Geometry")

    # Separate the normal Z component for slope
    separate = _add_node(tree, "ShaderNodeSeparateXYZ", -600, -500,
                         "Separate Normal")
    links.new(geometry.outputs["Normal"], separate.inputs["Vector"])

    # -- ColorRamp: Slope mask (Z component: 1 = flat, 0 = vertical) --
    ramp_slope = _add_node(tree, "ShaderNodeValToRGB", -400, -500, "Slope Mask")
    ramp_slope.color_ramp.elements[0].position = 0.3
    ramp_slope.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_slope.color_ramp.elements[1].position = 0.7
    ramp_slope.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(separate.outputs["Z"], ramp_slope.inputs["Fac"])

    # -- Apply base color tint to noise mix --
    # Bug 11 fix: use min(1.0, ...) clamping instead of raw * 4.0 which clips
    # any base_color component > 0.25 to white. Use * 2.0 with clamping for
    # proper range without blowing out terrain colors.
    mix_base = _add_node(tree, "ShaderNodeMixRGB", -300, 100, "Base Tint")
    mix_base.blend_type = "MULTIPLY"
    mix_base.inputs["Fac"].default_value = 1.0
    mix_base.inputs["Color1"].default_value = (
        min(1.0, bc[0] * 2.0),
        min(1.0, bc[1] * 2.0),
        min(1.0, bc[2] * 2.0),
        1.0,
    )
    links.new(mix_all.outputs["Color"], mix_base.inputs["Color2"])
    links.new(mix_base.outputs["Color"], bsdf.inputs["Base Color"])

    # -- Roughness: Slope-influenced --
    math_rough = _add_node(tree, "ShaderNodeMath", -200, -300, "Roughness Map")
    math_rough.operation = "MULTIPLY_ADD"
    math_rough.inputs[1].default_value = params.get("roughness_variation", 0.12)
    math_rough.inputs[2].default_value = params["roughness"]
    links.new(ramp_slope.outputs["Color"], math_rough.inputs[0])
    links.new(math_rough.outputs["Value"], bsdf.inputs["Roughness"])

    # -- 3-Layer Normal Chain (AAA quality) --
    _build_normal_chain(nodes, links, tree, bsdf,
                        mapping.outputs["Vector"], params)


# ---------------------------------------------------------------------------
# Builder: Fabric (cloth / leather)
# ---------------------------------------------------------------------------

def build_fabric_material(mat: Any, params: dict[str, Any]) -> None:
    """Build fabric / cloth / leather node graph.

    Node graph structure:
      - Brick Texture -> weave pattern (cloth) or grain (leather)
      - Noise Texture -> subtle color variation + roughness
      - High roughness base with variation
      - Bump from brick pattern
    """
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = _add_node(tree, "ShaderNodeOutputMaterial", 400, 0, "Output")
    bsdf = _add_node(tree, "ShaderNodeBsdfPrincipled", 100, 0, "Principled BSDF")
    bc = params["base_color"]
    bsdf.inputs["Base Color"].default_value = bc
    bsdf.inputs["Roughness"].default_value = params["roughness"]
    bsdf.inputs["Metallic"].default_value = params["metallic"]

    # Slight sheen for fabric
    sheen_input = _get_bsdf_input(bsdf, "Sheen Weight")
    if sheen_input is not None:
        sheen_input.default_value = 0.3

    # Subsurface scattering for leather/cloth (soft light penetration)
    sss_val = params.get("subsurface", 0.0)
    if sss_val > 0.0:
        sss_input = _get_bsdf_input(bsdf, "Subsurface Weight")
        if sss_input is not None:
            sss_input.default_value = sss_val
        sss_scale_input = bsdf.inputs.get("Subsurface Scale")
        if sss_scale_input is not None:
            sss_scale_input.default_value = params.get("subsurface_scale", 0.003)
        sss_radius_input = bsdf.inputs.get("Subsurface Radius")
        if sss_radius_input is not None:
            sss_radius_input.default_value = params.get(
                "subsurface_radius", [0.5, 0.4, 0.35]
            )

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = _add_node(tree, "ShaderNodeTexCoord", -1200, 0, "Tex Coord")
    mapping = _add_node(tree, "ShaderNodeMapping", -1000, 0, "Mapping")
    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    detail_scale = params.get("detail_scale", 20.0)

    # -- Brick Texture: Weave pattern --
    brick = _add_node(tree, "ShaderNodeTexBrick", -800, 200, "Weave Pattern")
    brick.inputs["Scale"].default_value = detail_scale
    brick.inputs["Mortar Size"].default_value = 0.01
    brick.inputs["Mortar Smooth"].default_value = 0.1
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Brick Width"].default_value = 0.5
    brick.inputs["Row Height"].default_value = 0.25
    # Set brick colors to subtle variations of base color
    brick.inputs["Color1"].default_value = (bc[0] * 0.9, bc[1] * 0.9,
                                             bc[2] * 0.9, 1.0)
    brick.inputs["Color2"].default_value = (bc[0] * 1.1, bc[1] * 1.1,
                                             bc[2] * 1.1, 1.0)
    brick.inputs["Mortar"].default_value = (bc[0] * 0.6, bc[1] * 0.6,
                                             bc[2] * 0.6, 1.0)
    links.new(mapping.outputs["Vector"], brick.inputs["Vector"])

    # -- Noise: Subtle color / roughness variation --
    noise_var = _add_node(tree, "ShaderNodeTexNoise", -800, -100,
                          "Color Variation")
    noise_var.inputs["Scale"].default_value = detail_scale * 0.3
    noise_var.inputs["Detail"].default_value = 5.0
    noise_var.inputs["Roughness"].default_value = 0.5
    links.new(mapping.outputs["Vector"], noise_var.inputs["Vector"])

    # -- MixRGB: Blend weave with variation --
    mix_color = _add_node(tree, "ShaderNodeMixRGB", -400, 100, "Fabric Color")
    mix_color.blend_type = "OVERLAY"
    mix_color.inputs["Fac"].default_value = 0.15
    links.new(brick.outputs["Color"], mix_color.inputs["Color1"])
    links.new(noise_var.outputs["Color"], mix_color.inputs["Color2"])
    links.new(mix_color.outputs["Color"], bsdf.inputs["Base Color"])

    # -- Roughness variation --
    math_rough = _add_node(tree, "ShaderNodeMath", -400, -300, "Roughness Map")
    math_rough.operation = "MULTIPLY_ADD"
    math_rough.inputs[1].default_value = params.get("roughness_variation", 0.08)
    math_rough.inputs[2].default_value = params["roughness"]
    links.new(noise_var.outputs["Fac"], math_rough.inputs[0])
    links.new(math_rough.outputs["Value"], bsdf.inputs["Roughness"])

    # -- 3-Layer Normal Chain (AAA quality) --
    _build_normal_chain(nodes, links, tree, bsdf,
                        mapping.outputs["Vector"], params)


# ---------------------------------------------------------------------------
# Generator dispatch table
# ---------------------------------------------------------------------------

GENERATORS: dict[str, Any] = {
    "stone": build_stone_material,
    "wood": build_wood_material,
    "metal": build_metal_material,
    "organic": build_organic_material,
    "terrain": build_terrain_material,
    "fabric": build_fabric_material,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_procedural_material(name: str, material_key: str) -> Any:
    """Create a procedural material from the library.

    Args:
        name: Name for the new Blender material.
        material_key: Key into MATERIAL_LIBRARY (e.g. 'rough_stone_wall').

    Returns:
        The created bpy.types.Material.

    Raises:
        ValueError: If material_key is not in MATERIAL_LIBRARY.
        ValueError: If the node_recipe has no matching generator.
        RuntimeError: If bpy is not available (not running inside Blender).
    """
    if bpy is None:
        raise RuntimeError(
            "create_procedural_material() requires bpy -- "
            "must run inside Blender"
        )

    if material_key not in MATERIAL_LIBRARY:
        raise ValueError(
            f"Unknown material_key: '{material_key}'. "
            f"Available: {sorted(MATERIAL_LIBRARY.keys())}"
        )

    entry = dict(MATERIAL_LIBRARY[material_key])  # copy to avoid mutating library
    recipe = entry["node_recipe"]

    # Bug 10 fix: ensure base_color has at least 4 elements (RGBA)
    bc_raw = entry.get("base_color", (0.15, 0.13, 0.11, 1.0))
    if not bc_raw or not hasattr(bc_raw, '__len__'):
        bc_raw = (0.15, 0.13, 0.11, 1.0)
    bc_list = list(bc_raw)
    while len(bc_list) < 4:
        bc_list.append(1.0 if len(bc_list) == 3 else 0.0)
    entry["base_color"] = tuple(bc_list[:4])

    builder = GENERATORS.get(recipe)
    if builder is None:
        raise ValueError(
            f"No generator for node_recipe '{recipe}'. "
            f"Available: {sorted(GENERATORS.keys())}"
        )

    # Create the Blender material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    # Build the procedural node graph
    builder(mat, entry)

    return mat


def get_library_keys() -> list[str]:
    """Return all available material library keys, sorted."""
    return sorted(MATERIAL_LIBRARY.keys())


def get_library_info(material_key: str) -> dict[str, Any]:
    """Return the library entry for a given material key."""
    if material_key not in MATERIAL_LIBRARY:
        raise ValueError(
            f"Unknown material_key: '{material_key}'. "
            f"Available: {sorted(MATERIAL_LIBRARY.keys())}"
        )
    return dict(MATERIAL_LIBRARY[material_key])


# ---------------------------------------------------------------------------
# Blender addon command handler
# ---------------------------------------------------------------------------

def handle_create_procedural_material(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for the 'material_create_procedural' command.

    Params:
        name (str): Name for the material. Defaults to the material_key.
        material_key (str): Key from MATERIAL_LIBRARY.
        list_available (bool): If True, just return available keys.

    Returns:
        dict with material name, recipe used, and node count.
    """
    # List mode: return all available material keys
    if params.get("list_available", False):
        keys = get_library_keys()
        categories: dict[str, list[str]] = {}
        for key in keys:
            recipe = MATERIAL_LIBRARY[key]["node_recipe"]
            categories.setdefault(recipe, []).append(key)
        return {
            "available_materials": keys,
            "count": len(keys),
            "categories": categories,
        }

    material_key = params.get("material_key")
    if not material_key:
        raise ValueError(
            "'material_key' is required. Use list_available=True to see options."
        )

    name = params.get("name", material_key)
    mat = create_procedural_material(name, material_key)

    # Assign material to object if object_name is provided
    object_name = params.get("object_name")
    if object_name and bpy is not None:
        obj = bpy.data.objects.get(object_name)
        if obj and hasattr(obj, "data") and hasattr(obj.data, "materials"):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

    node_count = len(mat.node_tree.nodes)
    recipe = MATERIAL_LIBRARY[material_key]["node_recipe"]

    return {
        "name": mat.name,
        "material_key": material_key,
        "node_recipe": recipe,
        "node_count": node_count,
        "use_nodes": True,
        "created": True,
    }
