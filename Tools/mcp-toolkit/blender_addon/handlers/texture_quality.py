"""AAA texture quality pipeline -- smart materials, detail layers, atlas system.

Brings procedural materials from "good" to AAA studio quality by adding the
detail systems that make textures look photorealistic at game distances:

  - Smart Material System:   Multi-layer materials with edge wear, cavity dirt,
                             height masks, and macro variation (Substance Painter
                             equivalent built in pure Blender nodes)
  - Trim Sheet / Atlas:      UV-packed trim sheets for architecture detail
  - Macro Variation:         Large-scale color/roughness shifts to break tiling
  - Detail Texture:          Close-range micro-detail overlays that fade with distance
  - Additional Bake Maps:    Position, bent normal, world normal, flow, gradient

Design principles:
  - All compute/layout functions are **pure logic** (no bpy) for testability
  - Code-generation functions return Blender Python strings for ``blender_execute``
  - Only uses allowed imports: bpy, mathutils, math, random, json
  - All colors follow VeilBreakers dark fantasy palette rules:
      * Environment saturation NEVER exceeds 40%
      * Value range 10-50% (dark world)
      * Edge wear is BRIGHTER than base (physical abrasion reveals lighter surface)
      * Cavity dirt is DARKER than base (grime accumulates in crevices)

Reference quality: FromSoftware / Naughty Dog material fidelity.
"""

from __future__ import annotations

import math
import textwrap
from typing import Any


# ---------------------------------------------------------------------------
# Smart Material Presets -- 22 dark fantasy material types
# ---------------------------------------------------------------------------
# Each preset defines the FULL parameter set for a 5-layer smart material.
#
# Layer architecture (bottom to top):
#   1. BASE:           Principled BSDF base PBR values + micro noise
#   2. EDGE WEAR:      Convex-edge brightening via Pointiness/curvature
#   3. CAVITY DIRT:    Concave-crevice darkening via inverted Pointiness
#   4. HEIGHT MASKS:   Z-position-driven moss/water staining
#   5. MACRO VARIATION: Large-scale noise for hue/value/roughness shifts

SMART_MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    # =======================================================================
    # Architecture -- Stone
    # =======================================================================
    "dungeon_stone": {
        "category": "stone",
        "base_color": (0.14, 0.12, 0.10),
        "metallic": 0.0,
        "roughness": 0.82,
        "edge_wear_color": (0.25, 0.23, 0.20),
        "edge_wear_roughness": 0.65,
        "edge_wear_sharpness": 0.6,
        "cavity_color": (0.06, 0.05, 0.04),
        "cavity_roughness": 0.95,
        "cavity_sharpness": 0.5,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.7,
        "moss_roughness": 0.92,
        "rain_streak_color": (0.08, 0.07, 0.06),
        "rain_streak_scale": 8.0,
        "macro_variation_scale": 1.5,
        "macro_variation_strength": 0.08,
        "macro_roughness_variation": 0.06,
        "micro_normal_scale": 60.0,
        "meso_normal_scale": 15.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.25,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 1.0,
    },
    "castle_stone": {
        "category": "stone",
        "base_color": (0.18, 0.16, 0.14),
        "metallic": 0.0,
        "roughness": 0.72,
        "edge_wear_color": (0.28, 0.26, 0.24),
        "edge_wear_roughness": 0.55,
        "edge_wear_sharpness": 0.65,
        "cavity_color": (0.07, 0.06, 0.05),
        "cavity_roughness": 0.92,
        "cavity_sharpness": 0.5,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.75,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.10, 0.09, 0.08),
        "rain_streak_scale": 6.0,
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.06,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 55.0,
        "meso_normal_scale": 12.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.9,
    },
    "brick": {
        "category": "stone",
        "base_color": (0.18, 0.12, 0.09),
        "metallic": 0.0,
        "roughness": 0.78,
        "edge_wear_color": (0.26, 0.20, 0.16),
        "edge_wear_roughness": 0.60,
        "edge_wear_sharpness": 0.7,
        "cavity_color": (0.06, 0.04, 0.03),
        "cavity_roughness": 0.93,
        "cavity_sharpness": 0.55,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.72,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.10, 0.07, 0.05),
        "rain_streak_scale": 7.0,
        "macro_variation_scale": 1.8,
        "macro_variation_strength": 0.07,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 50.0,
        "meso_normal_scale": 14.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.55,
        "macro_normal_strength": 0.95,
    },
    "rough_plaster": {
        "category": "stone",
        "base_color": (0.22, 0.20, 0.18),
        "metallic": 0.0,
        "roughness": 0.85,
        "edge_wear_color": (0.30, 0.28, 0.25),
        "edge_wear_roughness": 0.70,
        "edge_wear_sharpness": 0.55,
        "cavity_color": (0.10, 0.09, 0.07),
        "cavity_roughness": 0.92,
        "cavity_sharpness": 0.45,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.68,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.14, 0.12, 0.10),
        "rain_streak_scale": 5.0,
        "macro_variation_scale": 1.2,
        "macro_variation_strength": 0.10,
        "macro_roughness_variation": 0.07,
        "micro_normal_scale": 45.0,
        "meso_normal_scale": 10.0,
        "macro_normal_scale": 2.0,
        "micro_normal_strength": 0.3,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.8,
    },
    "sandstone": {
        "category": "stone",
        "base_color": (0.24, 0.19, 0.13),
        "metallic": 0.0,
        "roughness": 0.80,
        "edge_wear_color": (0.32, 0.27, 0.20),
        "edge_wear_roughness": 0.62,
        "edge_wear_sharpness": 0.6,
        "cavity_color": (0.10, 0.08, 0.05),
        "cavity_roughness": 0.93,
        "cavity_sharpness": 0.5,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.75,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.16, 0.12, 0.08),
        "rain_streak_scale": 6.0,
        "macro_variation_scale": 1.6,
        "macro_variation_strength": 0.09,
        "macro_roughness_variation": 0.06,
        "micro_normal_scale": 55.0,
        "meso_normal_scale": 13.0,
        "macro_normal_scale": 2.8,
        "micro_normal_strength": 0.25,
        "meso_normal_strength": 0.55,
        "macro_normal_strength": 0.9,
    },
    "marble": {
        "category": "stone",
        "base_color": (0.30, 0.28, 0.26),
        "metallic": 0.0,
        "roughness": 0.25,
        "edge_wear_color": (0.38, 0.36, 0.34),
        "edge_wear_roughness": 0.15,
        "edge_wear_sharpness": 0.5,
        "cavity_color": (0.16, 0.14, 0.12),
        "cavity_roughness": 0.40,
        "cavity_sharpness": 0.4,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.80,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.20, 0.18, 0.16),
        "rain_streak_scale": 4.0,
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.04,
        "macro_roughness_variation": 0.03,
        "micro_normal_scale": 70.0,
        "meso_normal_scale": 8.0,
        "macro_normal_scale": 2.0,
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.4,
        "macro_normal_strength": 0.6,
    },
    "obsidian": {
        "category": "stone",
        "base_color": (0.04, 0.04, 0.06),
        "metallic": 0.0,  # dielectric stone — no metallic
        "roughness": 0.08,
        "edge_wear_color": (0.12, 0.11, 0.14),
        "edge_wear_roughness": 0.04,
        "edge_wear_sharpness": 0.8,
        "cavity_color": (0.02, 0.02, 0.03),
        "cavity_roughness": 0.15,
        "cavity_sharpness": 0.6,
        "moss_color": (0.04, 0.06, 0.03),
        "moss_threshold": 0.85,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.03, 0.03, 0.04),
        "rain_streak_scale": 5.0,
        "macro_variation_scale": 2.5,
        "macro_variation_strength": 0.03,
        "macro_roughness_variation": 0.02,
        "micro_normal_scale": 80.0,
        "meso_normal_scale": 10.0,
        "macro_normal_scale": 2.0,
        "micro_normal_strength": 0.1,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.5,
    },

    # =======================================================================
    # Architecture -- Wood
    # =======================================================================
    "old_wood": {
        "category": "wood",
        "base_color": (0.14, 0.11, 0.07),
        "metallic": 0.0,
        "roughness": 0.75,
        "edge_wear_color": (0.24, 0.20, 0.15),
        "edge_wear_roughness": 0.55,
        "edge_wear_sharpness": 0.65,
        "cavity_color": (0.05, 0.04, 0.03),
        "cavity_roughness": 0.92,
        "cavity_sharpness": 0.5,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.68,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.08, 0.06, 0.04),
        "rain_streak_scale": 7.0,
        "macro_variation_scale": 1.4,
        "macro_variation_strength": 0.09,
        "macro_roughness_variation": 0.07,
        "micro_normal_scale": 40.0,
        "meso_normal_scale": 10.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.35,
        "meso_normal_strength": 0.7,
        "macro_normal_strength": 0.5,
    },
    "dark_wood": {
        "category": "wood",
        "base_color": (0.08, 0.06, 0.04),
        "metallic": 0.0,
        "roughness": 0.65,
        "edge_wear_color": (0.18, 0.14, 0.10),
        "edge_wear_roughness": 0.45,
        "edge_wear_sharpness": 0.7,
        "cavity_color": (0.03, 0.02, 0.02),
        "cavity_roughness": 0.90,
        "cavity_sharpness": 0.55,
        "moss_color": (0.04, 0.08, 0.03),
        "moss_threshold": 0.72,
        "moss_roughness": 0.92,
        "rain_streak_color": (0.05, 0.04, 0.03),
        "rain_streak_scale": 6.0,
        "macro_variation_scale": 1.6,
        "macro_variation_strength": 0.07,
        "macro_roughness_variation": 0.06,
        "micro_normal_scale": 45.0,
        "meso_normal_scale": 12.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.3,
        "meso_normal_strength": 0.65,
        "macro_normal_strength": 0.55,
    },
    "polished_wood": {
        "category": "wood",
        "base_color": (0.18, 0.13, 0.08),
        "metallic": 0.0,
        "roughness": 0.30,
        "edge_wear_color": (0.26, 0.20, 0.14),
        "edge_wear_roughness": 0.18,
        "edge_wear_sharpness": 0.55,
        "cavity_color": (0.08, 0.06, 0.04),
        "cavity_roughness": 0.50,
        "cavity_sharpness": 0.4,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.82,
        "moss_roughness": 0.90,
        "rain_streak_color": (0.12, 0.09, 0.06),
        "rain_streak_scale": 5.0,
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.05,
        "macro_roughness_variation": 0.04,
        "micro_normal_scale": 50.0,
        "meso_normal_scale": 8.0,
        "macro_normal_scale": 2.0,
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.4,
    },

    # =======================================================================
    # Metals
    # =======================================================================
    "rusted_armor": {
        "category": "metal",
        "base_color": (0.56, 0.57, 0.58),
        "metallic": 0.95,
        "roughness": 0.35,
        "edge_wear_color": (0.65, 0.63, 0.62),
        "edge_wear_roughness": 0.15,
        "edge_wear_sharpness": 0.75,
        "cavity_color": (0.25, 0.12, 0.05),
        "cavity_roughness": 0.90,
        "cavity_sharpness": 0.6,
        "rust_color": (0.35, 0.15, 0.05),
        "rust_spread": 0.4,
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.05,
        "macro_roughness_variation": 0.04,
        "micro_normal_scale": 65.0,
        "meso_normal_scale": 16.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "polished_steel": {
        "category": "metal",
        "base_color": (0.63, 0.62, 0.64),
        "metallic": 1.0,
        "roughness": 0.18,
        "edge_wear_color": (0.72, 0.71, 0.73),
        "edge_wear_roughness": 0.08,
        "edge_wear_sharpness": 0.65,
        "cavity_color": (0.35, 0.33, 0.32),
        "cavity_roughness": 0.45,
        "cavity_sharpness": 0.5,
        "macro_variation_scale": 3.0,
        "macro_variation_strength": 0.03,
        "macro_roughness_variation": 0.03,
        "micro_normal_scale": 80.0,
        "meso_normal_scale": 20.0,
        "macro_normal_scale": 4.0,
        "micro_normal_strength": 0.35,
        "meso_normal_strength": 0.2,
        "macro_normal_strength": 0.2,
    },
    "tarnished_gold": {
        "category": "metal",
        "base_color": (0.75, 0.60, 0.30),
        "metallic": 0.95,
        "roughness": 0.30,
        "edge_wear_color": (0.85, 0.72, 0.42),
        "edge_wear_roughness": 0.12,
        "edge_wear_sharpness": 0.6,
        "cavity_color": (0.40, 0.28, 0.10),
        "cavity_roughness": 0.65,
        "cavity_sharpness": 0.5,
        "macro_variation_scale": 2.5,
        "macro_variation_strength": 0.04,
        "macro_roughness_variation": 0.03,
        "micro_normal_scale": 70.0,
        "meso_normal_scale": 18.0,
        "macro_normal_scale": 3.5,
        "micro_normal_strength": 0.3,
        "meso_normal_strength": 0.25,
        "macro_normal_strength": 0.25,
    },
    "aged_bronze": {
        "category": "metal",
        "base_color": (0.50, 0.38, 0.22),
        "metallic": 0.90,
        "roughness": 0.40,
        "edge_wear_color": (0.62, 0.50, 0.32),
        "edge_wear_roughness": 0.20,
        "edge_wear_sharpness": 0.65,
        "cavity_color": (0.15, 0.22, 0.12),
        "cavity_roughness": 0.80,
        "cavity_sharpness": 0.55,
        "patina_color": (0.18, 0.28, 0.15),
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.06,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 60.0,
        "meso_normal_scale": 14.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.35,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.3,
    },
    "rusted_iron": {
        "category": "metal",
        "base_color": (0.56, 0.57, 0.58),
        "metallic": 0.85,
        "roughness": 0.55,
        "edge_wear_color": (0.64, 0.63, 0.62),
        "edge_wear_roughness": 0.25,
        "edge_wear_sharpness": 0.7,
        "cavity_color": (0.30, 0.14, 0.06),
        "cavity_roughness": 0.92,
        "cavity_sharpness": 0.6,
        "rust_color": (0.40, 0.18, 0.06),
        "rust_spread": 0.5,
        "macro_variation_scale": 1.8,
        "macro_variation_strength": 0.06,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 55.0,
        "meso_normal_scale": 12.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.35,
        "macro_normal_strength": 0.3,
    },

    # =======================================================================
    # Organic
    # =======================================================================
    "worn_leather": {
        "category": "organic",
        "base_color": (0.14, 0.10, 0.07),
        "metallic": 0.0,
        "roughness": 0.58,
        "edge_wear_color": (0.24, 0.18, 0.13),
        "edge_wear_roughness": 0.35,
        "edge_wear_sharpness": 0.65,
        "cavity_color": (0.05, 0.04, 0.03),
        "cavity_roughness": 0.85,
        "cavity_sharpness": 0.5,
        "macro_variation_scale": 1.5,
        "macro_variation_strength": 0.08,
        "macro_roughness_variation": 0.06,
        "micro_normal_scale": 40.0,
        "meso_normal_scale": 10.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.6,
        "macro_normal_strength": 0.4,
    },
    "dark_fabric": {
        "category": "organic",
        "base_color": (0.06, 0.05, 0.05),
        "metallic": 0.0,
        "roughness": 0.82,
        "edge_wear_color": (0.14, 0.12, 0.11),
        "edge_wear_roughness": 0.65,
        "edge_wear_sharpness": 0.55,
        "cavity_color": (0.03, 0.02, 0.02),
        "cavity_roughness": 0.92,
        "cavity_sharpness": 0.45,
        "macro_variation_scale": 1.2,
        "macro_variation_strength": 0.06,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 55.0,
        "meso_normal_scale": 14.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.3,
    },
    "bone": {
        "category": "organic",
        "base_color": (0.35, 0.32, 0.27),
        "metallic": 0.0,
        "roughness": 0.55,
        "edge_wear_color": (0.42, 0.40, 0.35),
        "edge_wear_roughness": 0.35,
        "edge_wear_sharpness": 0.6,
        "cavity_color": (0.15, 0.12, 0.08),
        "cavity_roughness": 0.80,
        "cavity_sharpness": 0.5,
        "macro_variation_scale": 1.8,
        "macro_variation_strength": 0.07,
        "macro_roughness_variation": 0.05,
        "micro_normal_scale": 50.0,
        "meso_normal_scale": 12.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.3,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.4,
    },
    "chitin": {
        "category": "organic",
        "base_color": (0.08, 0.06, 0.04),
        "metallic": 0.0,  # dielectric organic — no metallic
        "roughness": 0.30,
        "edge_wear_color": (0.16, 0.13, 0.10),
        "edge_wear_roughness": 0.15,
        "edge_wear_sharpness": 0.75,
        "cavity_color": (0.03, 0.02, 0.02),
        "cavity_roughness": 0.60,
        "cavity_sharpness": 0.6,
        "macro_variation_scale": 2.0,
        "macro_variation_strength": 0.05,
        "macro_roughness_variation": 0.04,
        "micro_normal_scale": 60.0,
        "meso_normal_scale": 15.0,
        "macro_normal_scale": 3.0,
        "micro_normal_strength": 0.35,
        "meso_normal_strength": 0.4,
        "macro_normal_strength": 0.35,
    },
    "bark": {
        "category": "organic",
        "base_color": (0.12, 0.09, 0.06),
        "metallic": 0.0,
        "roughness": 0.88,
        "edge_wear_color": (0.20, 0.16, 0.12),
        "edge_wear_roughness": 0.70,
        "edge_wear_sharpness": 0.6,
        "cavity_color": (0.04, 0.03, 0.02),
        "cavity_roughness": 0.95,
        "cavity_sharpness": 0.5,
        "moss_color": (0.06, 0.10, 0.04),
        "moss_threshold": 0.65,
        "moss_roughness": 0.92,
        "rain_streak_color": (0.07, 0.05, 0.04),
        "rain_streak_scale": 8.0,
        "macro_variation_scale": 1.3,
        "macro_variation_strength": 0.10,
        "macro_roughness_variation": 0.08,
        "micro_normal_scale": 35.0,
        "meso_normal_scale": 8.0,
        "macro_normal_scale": 2.0,
        "micro_normal_strength": 0.4,
        "meso_normal_strength": 0.7,
        "macro_normal_strength": 0.6,
    },
    "moss": {
        "category": "organic",
        "base_color": (0.06, 0.10, 0.04),
        "metallic": 0.0,
        "roughness": 0.92,
        "edge_wear_color": (0.10, 0.16, 0.08),
        "edge_wear_roughness": 0.80,
        "edge_wear_sharpness": 0.4,
        "cavity_color": (0.03, 0.05, 0.02),
        "cavity_roughness": 0.96,
        "cavity_sharpness": 0.4,
        "macro_variation_scale": 1.0,
        "macro_variation_strength": 0.12,
        "macro_roughness_variation": 0.06,
        "micro_normal_scale": 45.0,
        "meso_normal_scale": 10.0,
        "macro_normal_scale": 2.5,
        "micro_normal_strength": 0.35,
        "meso_normal_strength": 0.5,
        "macro_normal_strength": 0.4,
    },
    "ice": {
        "category": "special",
        "base_color": (0.32, 0.40, 0.48),
        "metallic": 0.0,  # dielectric — no metallic
        "roughness": 0.10,
        "edge_wear_color": (0.42, 0.50, 0.58),
        "edge_wear_roughness": 0.04,
        "edge_wear_sharpness": 0.8,
        "cavity_color": (0.18, 0.22, 0.28),
        "cavity_roughness": 0.20,
        "cavity_sharpness": 0.5,
        "macro_variation_scale": 3.0,
        "macro_variation_strength": 0.04,
        "macro_roughness_variation": 0.03,
        "micro_normal_scale": 75.0,
        "meso_normal_scale": 18.0,
        "macro_normal_scale": 4.0,
        "micro_normal_strength": 0.2,
        "meso_normal_strength": 0.3,
        "macro_normal_strength": 0.4,
    },
    "crystal": {
        "category": "special",
        "base_color": (0.25, 0.15, 0.30),
        "metallic": 0.0,  # dielectric — no metallic
        "roughness": 0.05,
        "edge_wear_color": (0.35, 0.25, 0.40),
        "edge_wear_roughness": 0.02,
        "edge_wear_sharpness": 0.85,
        "cavity_color": (0.12, 0.06, 0.16),
        "cavity_roughness": 0.12,
        "cavity_sharpness": 0.6,
        "macro_variation_scale": 3.5,
        "macro_variation_strength": 0.03,
        "macro_roughness_variation": 0.02,
        "micro_normal_scale": 80.0,
        "meso_normal_scale": 20.0,
        "macro_normal_scale": 5.0,
        "micro_normal_strength": 0.15,
        "meso_normal_strength": 0.25,
        "macro_normal_strength": 0.35,
    },
}

# All valid smart material type names.
VALID_SMART_MATERIAL_TYPES = frozenset(SMART_MATERIAL_PRESETS.keys())

# Required keys every smart material preset must define.
_REQUIRED_PRESET_KEYS = frozenset({
    "category", "base_color", "roughness",
    "edge_wear_color", "edge_wear_roughness", "edge_wear_sharpness",
    "cavity_color", "cavity_roughness", "cavity_sharpness",
    "macro_variation_scale", "macro_variation_strength",
    "macro_roughness_variation",
    "micro_normal_scale", "meso_normal_scale", "macro_normal_scale",
    "micro_normal_strength", "meso_normal_strength", "macro_normal_strength",
})


# ---------------------------------------------------------------------------
# Trim Sheet / Atlas System
# ---------------------------------------------------------------------------

# Default trim sheet elements for medieval architecture.
DEFAULT_TRIM_ELEMENTS: list[str] = [
    "stone_cornice",
    "stone_base",
    "metal_strap",
    "metal_nail_row",
    "wood_plank",
    "wood_beam",
    "carved_rune",
    "chain_link",
    "rope",
]

# PBR hints per trim element type (used in code generation).
TRIM_ELEMENT_PBR: dict[str, dict[str, Any]] = {
    "stone_cornice": {
        "base_color": (0.18, 0.16, 0.14),
        "roughness": 0.75,
        "metallic": 0.0,
    },
    "stone_base": {
        "base_color": (0.14, 0.12, 0.10),
        "roughness": 0.82,
        "metallic": 0.0,
    },
    "metal_strap": {
        "base_color": (0.56, 0.57, 0.58),
        "roughness": 0.50,
        "metallic": 0.90,
    },
    "metal_nail_row": {
        "base_color": (0.50, 0.50, 0.52),
        "roughness": 0.60,
        "metallic": 0.85,
    },
    "wood_plank": {
        "base_color": (0.14, 0.11, 0.07),
        "roughness": 0.78,
        "metallic": 0.0,
    },
    "wood_beam": {
        "base_color": (0.12, 0.09, 0.06),
        "roughness": 0.82,
        "metallic": 0.0,
    },
    "carved_rune": {
        "base_color": (0.16, 0.14, 0.12),
        "roughness": 0.70,
        "metallic": 0.0,
    },
    "chain_link": {
        "base_color": (0.52, 0.53, 0.54),
        "roughness": 0.55,
        "metallic": 0.92,
    },
    "rope": {
        "base_color": (0.18, 0.14, 0.10),
        "roughness": 0.90,
        "metallic": 0.0,
    },
}


# ---------------------------------------------------------------------------
# Detail Texture Types
# ---------------------------------------------------------------------------

DETAIL_TEXTURE_TYPES: dict[str, dict[str, Any]] = {
    "stone_pores": {
        "noise_type": "voronoi",
        "default_scale": 25.0,
        "default_strength": 0.3,
        "roughness_bias": 0.05,
        "description": "Chisel marks, crystal faces, micro-grain on stone surfaces",
    },
    "wood_grain": {
        "noise_type": "wave",
        "default_scale": 18.0,
        "default_strength": 0.35,
        "roughness_bias": 0.04,
        "description": "Fiber strands, knot detail, saw marks on wood surfaces",
    },
    "metal_scratches": {
        "noise_type": "noise",
        "default_scale": 35.0,
        "default_strength": 0.25,
        "roughness_bias": -0.05,
        "description": "Brush marks, grinding lines, forge scale on metal",
    },
    "leather_grain": {
        "noise_type": "voronoi",
        "default_scale": 30.0,
        "default_strength": 0.30,
        "roughness_bias": 0.03,
        "description": "Pore pattern, grain texture on leather surfaces",
    },
    "skin_pores": {
        "noise_type": "voronoi",
        "default_scale": 40.0,
        "default_strength": 0.20,
        "roughness_bias": 0.02,
        "description": "Pore detail, fine wrinkles, vein patterns on skin",
    },
    "fabric_weave": {
        "noise_type": "checker",
        "default_scale": 50.0,
        "default_strength": 0.15,
        "roughness_bias": 0.03,
        "description": "Thread pattern, weave structure on cloth/fabric",
    },
    "bone_micro": {
        "noise_type": "noise",
        "default_scale": 28.0,
        "default_strength": 0.22,
        "roughness_bias": 0.02,
        "description": "Micro-porosity, lamellar lines on bone surfaces",
    },
    "chitin_plates": {
        "noise_type": "voronoi",
        "default_scale": 22.0,
        "default_strength": 0.28,
        "roughness_bias": -0.03,
        "description": "Overlapping plate edges, growth lines on chitin/carapace",
    },
}

VALID_DETAIL_TYPES = frozenset(DETAIL_TEXTURE_TYPES.keys())


# ---------------------------------------------------------------------------
# Additional Bake Map Types
# ---------------------------------------------------------------------------

BAKE_MAP_TYPES: dict[str, dict[str, str]] = {
    "position": {
        "description": "World/object space position encoded to RGB",
        "colorspace": "Non-Color",
        "default_bit_depth": "16",
    },
    "bent_normal": {
        "description": "Averaged surrounding normal for AO-aware lighting",
        "colorspace": "Non-Color",
        "default_bit_depth": "16",
    },
    "world_normal": {
        "description": "World-space normals encoded to RGB",
        "colorspace": "Non-Color",
        "default_bit_depth": "16",
    },
    "flow": {
        "description": "UV flow direction for animated effects",
        "colorspace": "Non-Color",
        "default_bit_depth": "8",
    },
    "gradient": {
        "description": "Height gradient for height-based shader effects",
        "colorspace": "Non-Color",
        "default_bit_depth": "8",
    },
}

VALID_BAKE_MAP_TYPES = frozenset(BAKE_MAP_TYPES.keys())


# ---------------------------------------------------------------------------
# Pure-Logic: Smart Material Parameter Computation
# ---------------------------------------------------------------------------

def compute_smart_material_params(
    material_type: str,
    age: float = 0.5,
    environment: str = "indoor",
) -> dict[str, Any]:
    """Compute all material parameters for a given type, age, and environment.

    Pure logic -- returns a dict of all node values without creating nodes.
    Testable without Blender.

    Args:
        material_type: Key from SMART_MATERIAL_PRESETS.
        age: 0.0 = brand new, 1.0 = ancient.  Affects wear/dirt/moss intensity.
        environment: 'indoor' or 'outdoor'.  Outdoor enables moss + rain streaks.

    Returns:
        Dict with all computed PBR parameters ready for node-tree construction.

    Raises:
        ValueError: If material_type is unknown or age is out of range.
    """
    if material_type not in SMART_MATERIAL_PRESETS:
        raise ValueError(
            f"Unknown smart material type: '{material_type}'. "
            f"Valid types: {sorted(SMART_MATERIAL_PRESETS.keys())}"
        )
    age = max(0.0, min(1.0, float(age)))
    if environment not in ("indoor", "outdoor"):
        raise ValueError(f"environment must be 'indoor' or 'outdoor', got '{environment}'")

    preset = SMART_MATERIAL_PRESETS[material_type]
    result: dict[str, Any] = dict(preset)  # shallow copy

    # --- Age-driven intensity modulation ---
    # Edge wear increases with age (old things are more worn)
    result["edge_wear_intensity"] = 0.1 + 0.8 * age
    # Cavity dirt increases with age (grime accumulates)
    result["cavity_dirt_intensity"] = 0.15 + 0.7 * age
    # Roughness increases slightly with age (surfaces degrade)
    result["roughness_age_offset"] = 0.0 + 0.12 * age
    # Macro variation increases slightly with age (patchy fading)
    result["macro_variation_strength"] = (
        preset["macro_variation_strength"] * (0.8 + 0.4 * age)
    )

    # --- Environment-driven toggles ---
    is_outdoor = (environment == "outdoor")
    # Moss only grows outdoors and on appropriate surfaces
    has_moss = is_outdoor and "moss_color" in preset
    result["enable_moss"] = has_moss
    if has_moss:
        # Moss coverage increases with age
        result["moss_intensity"] = 0.0 + 0.8 * age
    else:
        result["moss_intensity"] = 0.0

    # Rain streaks only on outdoor vertical surfaces
    has_rain = is_outdoor and "rain_streak_color" in preset
    result["enable_rain_streaks"] = has_rain
    if has_rain:
        result["rain_streak_intensity"] = 0.1 + 0.5 * age
    else:
        result["rain_streak_intensity"] = 0.0

    # Computed age string for metadata
    if age < 0.2:
        result["age_label"] = "new"
    elif age < 0.5:
        result["age_label"] = "weathered"
    elif age < 0.8:
        result["age_label"] = "old"
    else:
        result["age_label"] = "ancient"

    result["environment"] = environment
    result["material_type"] = material_type
    return result


# ---------------------------------------------------------------------------
# Pure-Logic: Trim Sheet Layout Computation
# ---------------------------------------------------------------------------

def compute_trim_sheet_layout(
    elements: list[str] | None = None,
    resolution: int = 2048,
) -> dict[str, Any]:
    """Compute UV regions for a trim sheet atlas.

    Each element gets a horizontal strip spanning the full U range (0-1).
    The V range is divided equally among elements with 1px padding.

    Pure logic -- returns dict with element UV regions.

    Args:
        elements: List of trim element names.  Defaults to DEFAULT_TRIM_ELEMENTS.
        resolution: Texture resolution in pixels (for padding calculation).

    Returns:
        Dict with 'elements' mapping name -> (u_min, v_min, u_max, v_max),
        'resolution', and 'element_count'.

    Raises:
        ValueError: If elements list is empty or resolution < 64.
    """
    if elements is None:
        elements = list(DEFAULT_TRIM_ELEMENTS)
    if not elements:
        raise ValueError("elements list must not be empty")
    if resolution < 64:
        raise ValueError(f"resolution must be >= 64, got {resolution}")

    n = len(elements)
    # 1px padding in UV space
    padding = 1.0 / resolution
    # Available V space after padding between strips
    total_padding = padding * (n + 1)  # padding above, between, and below
    usable_v = 1.0 - total_padding
    strip_height = usable_v / n

    regions: dict[str, tuple[float, float, float, float]] = {}
    for i, name in enumerate(elements):
        v_min = padding + i * (strip_height + padding)
        v_max = v_min + strip_height
        # Clamp to [0, 1]
        v_min = max(0.0, min(1.0, v_min))
        v_max = max(0.0, min(1.0, v_max))
        regions[name] = (0.0, round(v_min, 6), 1.0, round(v_max, 6))

    # Verify no overlap: each region's v_max should be <= next region's v_min
    sorted_regions = sorted(regions.values(), key=lambda r: r[1])
    for i in range(len(sorted_regions) - 1):
        if sorted_regions[i][3] > sorted_regions[i + 1][1] + 1e-6:
            raise RuntimeError(
                f"Trim sheet layout overlap detected at element index {i}"
            )

    return {
        "elements": regions,
        "resolution": resolution,
        "element_count": n,
        "strip_height_px": int(strip_height * resolution),
        "padding_px": 1,
    }


# ---------------------------------------------------------------------------
# Pure-Logic: Macro Variation Parameter Computation
# ---------------------------------------------------------------------------

def compute_macro_variation_params(
    surface_area: float,
    material_type: str = "stone",
) -> dict[str, Any]:
    """Compute appropriate variation scale/strength for a surface size.

    Larger surfaces need larger variation patterns to avoid wallpaper look.
    Very small surfaces need minimal variation to avoid being noisy.

    Pure logic -- no bpy dependency.

    Args:
        surface_area: Approximate surface area in square meters.
        material_type: General category ('stone', 'wood', 'metal', 'organic').

    Returns:
        Dict with 'scale', 'hue_shift', 'value_shift', 'roughness_shift'.
    """
    # Clamp to reasonable range
    area = max(0.01, min(10000.0, float(surface_area)))

    # Base scale inversely proportional to surface size (larger = lower frequency)
    # A 1m^2 surface gets scale ~5.0, a 100m^2 surface gets scale ~0.5
    base_scale = 5.0 / math.sqrt(area)
    base_scale = max(0.2, min(20.0, base_scale))

    # Material-type multipliers for variation intensity
    type_multipliers = {
        "stone": {"hue": 1.0, "value": 1.0, "roughness": 1.0},
        "wood": {"hue": 1.2, "value": 0.8, "roughness": 0.9},
        "metal": {"hue": 0.5, "value": 0.6, "roughness": 0.7},
        "organic": {"hue": 1.3, "value": 1.1, "roughness": 0.8},
    }
    mult = type_multipliers.get(material_type, type_multipliers["stone"])

    # Variation strength scales with surface size (larger = more variation needed)
    size_factor = min(1.0, math.log10(max(1.0, area)) / 2.0)

    hue_shift = 0.02 + 0.03 * size_factor * mult["hue"]
    value_shift = 0.04 + 0.06 * size_factor * mult["value"]
    roughness_shift = 0.03 + 0.05 * size_factor * mult["roughness"]

    # Clamp all variations to subtle range (AAA = subtle, not overpowering)
    hue_shift = min(0.05, hue_shift)
    value_shift = min(0.12, value_shift)
    roughness_shift = min(0.10, roughness_shift)

    return {
        "scale": round(base_scale, 3),
        "hue_shift": round(hue_shift, 4),
        "value_shift": round(value_shift, 4),
        "roughness_shift": round(roughness_shift, 4),
        "material_type": material_type,
        "surface_area": area,
    }


# ---------------------------------------------------------------------------
# Code Generation: Smart Material
# ---------------------------------------------------------------------------

def generate_smart_material_code(
    material_type: str = "aged_stone",
    object_name: str = "target",
    wear_intensity: float = 0.5,
    dirt_intensity: float = 0.5,
    moss_intensity: float = 0.3,
    age: float = 0.5,
) -> str:
    """Generate Blender Python code for a multi-layer smart material.

    Builds a full node tree with 5 layers:
      1. BASE: Principled BSDF with detail noise
      2. EDGE WEAR: Pointiness-driven edge brightening
      3. CAVITY DIRT: Inverted Pointiness darkening
      4. HEIGHT MASKS: Z-position moss/rain streaks
      5. MACRO VARIATION: Large-scale noise for hue/value shifts

    Args:
        material_type: Key from SMART_MATERIAL_PRESETS.
            Valid: 'dungeon_stone', 'castle_stone', 'brick', 'rough_plaster',
                   'old_wood', 'dark_wood', 'polished_wood', 'rusted_armor',
                   'polished_steel', 'tarnished_gold', 'aged_bronze',
                   'rusted_iron', 'worn_leather', 'dark_fabric', 'bone',
                   'chitin', 'bark', 'moss', 'ice', 'crystal',
                   'sandstone', 'marble', 'obsidian'
        object_name: Target Blender object name.
        wear_intensity: Edge wear strength 0-1.
        dirt_intensity: Cavity dirt strength 0-1.
        moss_intensity: Moss/height mask strength 0-1.
        age: Overall age 0 (new) to 1 (ancient).

    Returns:
        Blender Python code string for blender_execute.

    Raises:
        ValueError: If material_type is unknown.
    """
    # Resolve preset -- fall back to dungeon_stone for unknown types but
    # also accept the legacy 'aged_stone' alias.
    actual_type = material_type
    if material_type == "aged_stone":
        actual_type = "dungeon_stone"

    if actual_type not in SMART_MATERIAL_PRESETS:
        raise ValueError(
            f"Unknown smart material type: '{material_type}'. "
            f"Valid: {sorted(SMART_MATERIAL_PRESETS.keys())}"
        )

    p = SMART_MATERIAL_PRESETS[actual_type]
    wear = max(0.0, min(1.0, float(wear_intensity)))
    dirt = max(0.0, min(1.0, float(dirt_intensity)))
    moss_i = max(0.0, min(1.0, float(moss_intensity)))
    age_v = max(0.0, min(1.0, float(age)))

    # Modulate intensities by age
    wear_final = wear * (0.2 + 0.8 * age_v)
    dirt_final = dirt * (0.2 + 0.8 * age_v)
    moss_final = moss_i * age_v

    bc = p["base_color"]
    ewc = p["edge_wear_color"]
    cc = p["cavity_color"]
    metallic = p.get("metallic", 0.0)
    roughness = p["roughness"]
    ewr = p["edge_wear_roughness"]
    ews = p["edge_wear_sharpness"]
    cr = p["cavity_roughness"]
    cs = p["cavity_sharpness"]
    mvs = p["macro_variation_scale"]
    mvstr = p["macro_variation_strength"] * (0.8 + 0.4 * age_v)
    mrv = p["macro_roughness_variation"]
    micro_ns = p["micro_normal_scale"]
    meso_ns = p["meso_normal_scale"]
    macro_ns = p["macro_normal_scale"]
    micro_nstr = p["micro_normal_strength"]
    meso_nstr = p["meso_normal_strength"]
    macro_nstr = p["macro_normal_strength"]

    # Moss parameters (may not exist for all presets)
    has_moss = "moss_color" in p and moss_final > 0.01
    mc = p.get("moss_color", (0.06, 0.10, 0.04))
    mt = p.get("moss_threshold", 0.7)
    mr = p.get("moss_roughness", 0.92)

    # Rain streak parameters
    has_rain = "rain_streak_color" in p
    rsc = p.get("rain_streak_color", (0.08, 0.07, 0.06))
    rss = p.get("rain_streak_scale", 6.0)

    code = textwrap.dedent(f"""\
    import bpy
    import math

    # === AAA Smart Material: {actual_type} ===
    # Age: {age_v:.2f}, Wear: {wear_final:.2f}, Dirt: {dirt_final:.2f}, Moss: {moss_final:.2f}

    obj = bpy.data.objects.get("{object_name}")
    if obj is None:
        raise ValueError("Object not found: {object_name}")

    mat_name = "SM_{actual_type}_{object_name}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    # --- Helper: add node ---
    def _n(ntype, x, y, label=""):
        nd = nodes.new(type=ntype)
        nd.location = (x, y)
        if label:
            nd.label = label
        return nd

    # === OUTPUT ===
    output = _n("ShaderNodeOutputMaterial", 1200, 0, "Output")

    # === PRINCIPLED BSDF (Layer 1: BASE) ===
    bsdf = _n("ShaderNodeBsdfPrincipled", 900, 0, "Base BSDF")
    bsdf.inputs["Base Color"].default_value = ({bc[0]}, {bc[1]}, {bc[2]}, 1.0)
    bsdf.inputs["Roughness"].default_value = {roughness}
    bsdf.inputs["Metallic"].default_value = {metallic}
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # === TEXTURE COORDINATE + MAPPING ===
    tex_coord = _n("ShaderNodeTexCoord", -1600, 0, "Tex Coord")
    mapping = _n("ShaderNodeMapping", -1400, 0, "Mapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
    map_out = mapping.outputs["Vector"]

    # === GEOMETRY NODE (for Pointiness) ===
    geom = _n("ShaderNodeNewGeometry", -1600, -400, "Geometry")

    # =====================================================================
    # COLOR CHAIN: base -> edge wear -> cavity -> height -> macro -> BSDF
    # =====================================================================

    # --- Micro detail noise on base color ---
    noise_micro_col = _n("ShaderNodeTexNoise", -1200, 200, "Micro Color Noise")
    noise_micro_col.inputs["Scale"].default_value = {micro_ns}
    noise_micro_col.inputs["Detail"].default_value = 10.0
    noise_micro_col.inputs["Roughness"].default_value = 0.6
    links.new(map_out, noise_micro_col.inputs["Vector"])

    mix_micro_col = _n("ShaderNodeMixRGB", -1000, 200, "Base + Micro")
    mix_micro_col.blend_type = "OVERLAY"
    mix_micro_col.inputs["Fac"].default_value = 0.15
    mix_micro_col.inputs["Color1"].default_value = ({bc[0]}, {bc[1]}, {bc[2]}, 1.0)
    links.new(noise_micro_col.outputs["Fac"], mix_micro_col.inputs["Color2"])

    # --- Layer 2: EDGE WEAR (Pointiness -> ColorRamp -> Mix) ---
    ramp_wear = _n("ShaderNodeValToRGB", -800, -300, "Edge Wear Ramp")
    ramp_wear.color_ramp.elements[0].position = {1.0 - ews}
    ramp_wear.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_wear.color_ramp.elements[1].position = 1.0
    ramp_wear.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(geom.outputs["Pointiness"], ramp_wear.inputs["Fac"])

    mix_wear = _n("ShaderNodeMixRGB", -600, 200, "Edge Wear Color")
    mix_wear.blend_type = "MIX"
    mix_wear.inputs["Color2"].default_value = ({ewc[0]}, {ewc[1]}, {ewc[2]}, 1.0)
    links.new(ramp_wear.outputs["Color"], mix_wear.inputs["Fac"])
    # Modulate by wear intensity
    math_wear = _n("ShaderNodeMath", -700, -350, "Wear Intensity")
    math_wear.operation = "MULTIPLY"
    math_wear.inputs[1].default_value = {wear_final}
    links.new(ramp_wear.outputs["Color"], math_wear.inputs[0])
    links.new(math_wear.outputs["Value"], mix_wear.inputs["Fac"])
    links.new(mix_micro_col.outputs["Color"], mix_wear.inputs["Color1"])

    # --- Layer 3: CAVITY DIRT (inverted Pointiness -> ColorRamp -> Mix) ---
    invert_pt = _n("ShaderNodeMath", -900, -500, "Invert Pointiness")
    invert_pt.operation = "SUBTRACT"
    invert_pt.inputs[0].default_value = 1.0
    links.new(geom.outputs["Pointiness"], invert_pt.inputs[1])

    ramp_cavity = _n("ShaderNodeValToRGB", -800, -500, "Cavity Dirt Ramp")
    ramp_cavity.color_ramp.elements[0].position = {1.0 - cs}
    ramp_cavity.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_cavity.color_ramp.elements[1].position = 1.0
    ramp_cavity.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(invert_pt.outputs["Value"], ramp_cavity.inputs["Fac"])

    mix_cavity = _n("ShaderNodeMixRGB", -400, 200, "Cavity Dirt Color")
    mix_cavity.blend_type = "MIX"
    mix_cavity.inputs["Color2"].default_value = ({cc[0]}, {cc[1]}, {cc[2]}, 1.0)
    math_cavity = _n("ShaderNodeMath", -500, -550, "Cavity Intensity")
    math_cavity.operation = "MULTIPLY"
    math_cavity.inputs[1].default_value = {dirt_final}
    links.new(ramp_cavity.outputs["Color"], math_cavity.inputs[0])
    links.new(math_cavity.outputs["Value"], mix_cavity.inputs["Fac"])
    links.new(mix_wear.outputs["Color"], mix_cavity.inputs["Color1"])
    """)

    # Layer 4: HEIGHT MASKS (conditional)
    if has_moss:
        code += textwrap.dedent(f"""\

    # --- Layer 4: HEIGHT MASKS (Z-position moss on top surfaces) ---
    sep_xyz = _n("ShaderNodeSeparateXYZ", -1200, -700, "Separate Position")
    links.new(geom.outputs["Normal"], sep_xyz.inputs["Vector"])

    ramp_moss = _n("ShaderNodeValToRGB", -1000, -700, "Moss Height Ramp")
    ramp_moss.color_ramp.elements[0].position = {mt}
    ramp_moss.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_moss.color_ramp.elements[1].position = 1.0
    ramp_moss.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(sep_xyz.outputs["Z"], ramp_moss.inputs["Fac"])

    mix_moss = _n("ShaderNodeMixRGB", -200, 200, "Moss Color")
    mix_moss.blend_type = "MIX"
    mix_moss.inputs["Color2"].default_value = ({mc[0]}, {mc[1]}, {mc[2]}, 1.0)
    math_moss = _n("ShaderNodeMath", -300, -750, "Moss Intensity")
    math_moss.operation = "MULTIPLY"
    math_moss.inputs[1].default_value = {moss_final}
    links.new(ramp_moss.outputs["Color"], math_moss.inputs[0])
    links.new(math_moss.outputs["Value"], mix_moss.inputs["Fac"])
    links.new(mix_cavity.outputs["Color"], mix_moss.inputs["Color1"])

    prev_color_out = mix_moss.outputs["Color"]
    """)
    else:
        code += textwrap.dedent("""\

    # --- Layer 4: HEIGHT MASKS skipped (indoor or no moss data) ---
    prev_color_out = mix_cavity.outputs["Color"]
    """)

    # Layer 5: MACRO VARIATION
    code += textwrap.dedent(f"""\

    # --- Layer 5: MACRO VARIATION (large-scale color shift) ---
    noise_macro = _n("ShaderNodeTexNoise", -600, -800, "Macro Variation Noise")
    noise_macro.inputs["Scale"].default_value = {mvs}
    noise_macro.inputs["Detail"].default_value = 3.0
    noise_macro.inputs["Roughness"].default_value = 0.5
    links.new(map_out, noise_macro.inputs["Vector"])

    mix_macro = _n("ShaderNodeMixRGB", 0, 200, "Macro Variation Color")
    mix_macro.blend_type = "OVERLAY"
    mix_macro.inputs["Fac"].default_value = {mvstr:.4f}
    links.new(prev_color_out, mix_macro.inputs["Color1"])
    links.new(noise_macro.outputs["Color"], mix_macro.inputs["Color2"])

    # Final color -> BSDF
    links.new(mix_macro.outputs["Color"], bsdf.inputs["Base Color"])

    # =====================================================================
    # ROUGHNESS CHAIN: base -> edge wear -> cavity -> height -> macro -> BSDF
    # =====================================================================

    # --- Edge wear roughness (smoother at worn edges) ---
    mix_rough_wear = _n("ShaderNodeMath", -600, -100, "Roughness Edge Wear")
    mix_rough_wear.operation = "MULTIPLY"
    mix_rough_wear.use_clamp = True
    links.new(math_wear.outputs["Value"], mix_rough_wear.inputs[0])
    mix_rough_wear.inputs[1].default_value = 1.0

    lerp_rough_wear = _n("ShaderNodeMapRange", -400, -100, "Lerp Rough Wear")
    lerp_rough_wear.inputs["From Min"].default_value = 0.0
    lerp_rough_wear.inputs["From Max"].default_value = 1.0
    lerp_rough_wear.inputs["To Min"].default_value = {roughness}
    lerp_rough_wear.inputs["To Max"].default_value = {ewr}
    links.new(mix_rough_wear.outputs["Value"], lerp_rough_wear.inputs["Value"])

    # --- Cavity roughness (rougher in crevices) ---
    lerp_rough_cav = _n("ShaderNodeMapRange", -200, -100, "Lerp Rough Cavity")
    lerp_rough_cav.inputs["From Min"].default_value = 0.0
    lerp_rough_cav.inputs["From Max"].default_value = 1.0
    lerp_rough_cav.inputs["To Max"].default_value = {cr}
    links.new(math_cavity.outputs["Value"], lerp_rough_cav.inputs["Value"])
    links.new(lerp_rough_wear.outputs["Result"], lerp_rough_cav.inputs["To Min"])

    # --- Macro roughness variation ---
    noise_rough_macro = _n("ShaderNodeTexNoise", -400, -200, "Macro Rough Noise")
    noise_rough_macro.inputs["Scale"].default_value = {mvs * 0.8:.2f}
    noise_rough_macro.inputs["Detail"].default_value = 2.0
    links.new(map_out, noise_rough_macro.inputs["Vector"])

    math_rough_macro = _n("ShaderNodeMapRange", 0, -100, "Macro Rough Shift")
    math_rough_macro.inputs["From Min"].default_value = 0.0
    math_rough_macro.inputs["From Max"].default_value = 1.0
    math_rough_macro.inputs["To Min"].default_value = -{mrv}
    math_rough_macro.inputs["To Max"].default_value = {mrv}
    links.new(noise_rough_macro.outputs["Fac"], math_rough_macro.inputs["Value"])

    add_rough_macro = _n("ShaderNodeMath", 200, -100, "Add Rough Macro")
    add_rough_macro.operation = "ADD"
    add_rough_macro.use_clamp = True
    links.new(lerp_rough_cav.outputs["Result"], add_rough_macro.inputs[0])
    links.new(math_rough_macro.outputs["Result"], add_rough_macro.inputs[1])

    links.new(add_rough_macro.outputs["Value"], bsdf.inputs["Roughness"])

    # =====================================================================
    # NORMAL CHAIN: 3-layer micro/meso/macro bump cascade
    # =====================================================================

    # --- Micro normal: fine pores/scratches ---
    noise_n_micro = _n("ShaderNodeTexNoise", -1200, -900, "Normal Micro Noise")
    noise_n_micro.inputs["Scale"].default_value = {micro_ns}
    noise_n_micro.inputs["Detail"].default_value = 12.0
    noise_n_micro.inputs["Roughness"].default_value = 0.7
    links.new(map_out, noise_n_micro.inputs["Vector"])

    bump_micro = _n("ShaderNodeBump", -1000, -900, "Micro Bump")
    bump_micro.inputs["Strength"].default_value = {micro_nstr}
    bump_micro.inputs["Distance"].default_value = 0.002
    links.new(noise_n_micro.outputs["Fac"], bump_micro.inputs["Height"])

    # --- Meso normal: mid-frequency cracks/veins ---
    voronoi_meso = _n("ShaderNodeTexVoronoi", -1200, -1100, "Normal Meso Voronoi")
    voronoi_meso.inputs["Scale"].default_value = {meso_ns}
    voronoi_meso.voronoi_dimensions = "3D"
    links.new(map_out, voronoi_meso.inputs["Vector"])

    bump_meso = _n("ShaderNodeBump", -1000, -1100, "Meso Bump")
    bump_meso.inputs["Strength"].default_value = {meso_nstr}
    bump_meso.inputs["Distance"].default_value = 0.005
    links.new(voronoi_meso.outputs["Distance"], bump_meso.inputs["Height"])
    links.new(bump_micro.outputs["Normal"], bump_meso.inputs["Normal"])

    # --- Macro normal: large undulation ---
    noise_n_macro = _n("ShaderNodeTexNoise", -1200, -1300, "Normal Macro Noise")
    noise_n_macro.inputs["Scale"].default_value = {macro_ns}
    noise_n_macro.inputs["Detail"].default_value = 4.0
    noise_n_macro.inputs["Roughness"].default_value = 0.5
    links.new(map_out, noise_n_macro.inputs["Vector"])

    bump_macro = _n("ShaderNodeBump", -1000, -1300, "Macro Bump")
    bump_macro.inputs["Strength"].default_value = {macro_nstr}
    bump_macro.inputs["Distance"].default_value = 0.02
    links.new(noise_n_macro.outputs["Fac"], bump_macro.inputs["Height"])
    links.new(bump_meso.outputs["Normal"], bump_macro.inputs["Normal"])

    # Final normal -> BSDF
    links.new(bump_macro.outputs["Normal"], bsdf.inputs["Normal"])

    # === ASSIGN MATERIAL TO OBJECT ===
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    result = {{
        "material": mat_name,
        "object": "{object_name}",
        "type": "{actual_type}",
        "age": {age_v},
        "node_count": len(nodes),
    }}
    """)

    return code


# ---------------------------------------------------------------------------
# Code Generation: Trim Sheet
# ---------------------------------------------------------------------------

def generate_trim_sheet_code(
    sheet_name: str = "medieval_trim",
    resolution: int = 2048,
    elements: list[str] | None = None,
) -> str:
    """Generate Blender Python code to create a trim sheet material with UV regions.

    Creates a single material with a packed UV layout containing multiple
    trim elements (cornices, metal straps, planks, etc.) used for
    architecture detail without unique textures per element.

    Args:
        sheet_name: Name for the trim sheet material.
        resolution: Texture resolution in pixels.
        elements: List of element names.  Defaults to DEFAULT_TRIM_ELEMENTS.

    Returns:
        Blender Python code string for blender_execute.
    """
    layout = compute_trim_sheet_layout(elements, resolution)
    regions = layout["elements"]

    element_blocks = []
    for name, (u_min, v_min, u_max, v_max) in regions.items():
        pbr = TRIM_ELEMENT_PBR.get(name, {
            "base_color": (0.15, 0.13, 0.11),
            "roughness": 0.75,
            "metallic": 0.0,
        })
        bc = pbr["base_color"]
        element_blocks.append(
            f'    "{name}": {{"uv": ({u_min}, {v_min:.6f}, {u_max}, {v_max:.6f}), '
            f'"base_color": ({bc[0]}, {bc[1]}, {bc[2]}), '
            f'"roughness": {pbr["roughness"]}, "metallic": {pbr["metallic"]}}}'
        )

    elements_dict_str = "{\n" + ",\n".join(element_blocks) + "\n}"

    code = f"""\
import bpy

# === Trim Sheet: {sheet_name} ({resolution}x{resolution}) ===
# {layout['element_count']} elements, {layout['strip_height_px']}px per strip

mat = bpy.data.materials.new(name="{sheet_name}")
mat.use_nodes = True
tree = mat.node_tree
nodes = tree.nodes
links = tree.links

# Store UV layout as custom properties for downstream tools
trim_regions = {elements_dict_str}

mat["trim_sheet"] = True
mat["trim_resolution"] = {resolution}
mat["trim_element_count"] = {layout['element_count']}

# Create a basic Principled BSDF -- actual PBR variation is baked later
bsdf = nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.15, 0.13, 0.11, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.75

result = {{
    "material": "{sheet_name}",
    "resolution": {resolution},
    "elements": trim_regions,
    "strip_height_px": {layout['strip_height_px']},
}}
"""

    return code


# ---------------------------------------------------------------------------
# Code Generation: Macro Variation
# ---------------------------------------------------------------------------

def generate_macro_variation_code(
    object_name: str,
    variation_scale: float = 5.0,
    hue_shift: float = 0.03,
    value_shift: float = 0.08,
) -> str:
    """Generate Blender Python code for macro variation overlay.

    On large surfaces (terrain, castle walls), materials look repetitive.
    This adds a large-scale variation layer:
      - Object-space 3D noise for position-dependent color shift
      - Subtle hue warmth variation (0.02-0.05)
      - Value variation (0.05-0.1)
      - Roughness variation (0.05-0.1)

    Result: large flat surfaces don't look like wallpaper.

    Args:
        object_name: Target object name.
        variation_scale: Noise scale (lower = larger pattern).
        hue_shift: Maximum hue shift (keep < 0.05 for subtle).
        value_shift: Maximum value shift (keep < 0.12).

    Returns:
        Blender Python code string for blender_execute.
    """
    vs = max(0.1, min(20.0, float(variation_scale)))
    hs = max(0.0, min(0.05, float(hue_shift)))
    vsh = max(0.0, min(0.12, float(value_shift)))

    code = textwrap.dedent(f"""\
    import bpy

    # === Macro Variation Overlay: {object_name} ===
    # Scale: {vs}, Hue shift: {hs}, Value shift: {vsh}

    obj = bpy.data.objects.get("{object_name}")
    if obj is None:
        raise ValueError("Object not found: {object_name}")

    if not obj.data.materials:
        raise ValueError("Object '{object_name}' has no material to overlay")

    mat = obj.data.materials[0]
    if not mat.use_nodes:
        mat.use_nodes = True

    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    # Find existing Principled BSDF
    bsdf = None
    for nd in nodes:
        if nd.type == "BSDF_PRINCIPLED":
            bsdf = nd
            break
    if bsdf is None:
        raise ValueError("No Principled BSDF found in material")

    def _n(ntype, x, y, label=""):
        nd = nodes.new(type=ntype)
        nd.location = (x, y)
        if label:
            nd.label = label
        return nd

    # Texture Coordinate for object-space noise
    tc = _n("ShaderNodeTexCoord", -800, 400, "Macro Var TC")
    noise = _n("ShaderNodeTexNoise", -600, 400, "Macro Var Noise")
    noise.inputs["Scale"].default_value = {vs}
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.5
    links.new(tc.outputs["Object"], noise.inputs["Vector"])

    # Find what's currently connected to Base Color
    base_color_input = bsdf.inputs["Base Color"]
    existing_link = None
    for lnk in links:
        if lnk.to_socket == base_color_input:
            existing_link = lnk
            break

    # Insert overlay mix between existing color and BSDF
    mix_var = _n("ShaderNodeMixRGB", bsdf.location[0] - 200, bsdf.location[1] + 200,
                 "Macro Variation")
    mix_var.blend_type = "OVERLAY"
    mix_var.inputs["Fac"].default_value = {vsh}

    if existing_link:
        prev_socket = existing_link.from_socket
        links.remove(existing_link)
        links.new(prev_socket, mix_var.inputs["Color1"])
    else:
        mix_var.inputs["Color1"].default_value = base_color_input.default_value[:]

    links.new(noise.outputs["Color"], mix_var.inputs["Color2"])
    links.new(mix_var.outputs["Color"], base_color_input)

    result = {{
        "object": "{object_name}",
        "variation_scale": {vs},
        "hue_shift": {hs},
        "value_shift": {vsh},
    }}
    """)

    return code


# ---------------------------------------------------------------------------
# Code Generation: Detail Texture
# ---------------------------------------------------------------------------

def generate_detail_texture_setup_code(
    object_name: str,
    detail_type: str = "stone_pores",
    detail_scale: float = 20.0,
    detail_strength: float = 0.3,
    blend_distance: float = 5.0,
) -> str:
    """Generate Blender Python code for close-up detail texture overlay.

    At game distances, large-scale noise looks fine. At close range, you need
    micro-detail to avoid blurriness. This adds a camera-distance-dependent
    detail overlay that fades in at close range.

    The #1 thing that makes a material look "real" up close.

    Args:
        object_name: Target object name.
        detail_type: Type of detail (from DETAIL_TEXTURE_TYPES).
        detail_scale: Texture scale for detail pattern.
        detail_strength: Normal/color influence strength 0-1.
        blend_distance: Distance in meters at which detail starts fading in.

    Returns:
        Blender Python code string for blender_execute.

    Raises:
        ValueError: If detail_type is unknown.
    """
    if detail_type not in DETAIL_TEXTURE_TYPES:
        raise ValueError(
            f"Unknown detail type: '{detail_type}'. "
            f"Valid: {sorted(DETAIL_TEXTURE_TYPES.keys())}"
        )

    dt = DETAIL_TEXTURE_TYPES[detail_type]
    ds = max(1.0, min(100.0, float(detail_scale)))
    dstr = max(0.0, min(1.0, float(detail_strength)))
    bd = max(0.5, min(50.0, float(blend_distance)))
    rbias = dt["roughness_bias"]

    # Choose noise node type
    noise_node_type = {
        "voronoi": "ShaderNodeTexVoronoi",
        "wave": "ShaderNodeTexWave",
        "noise": "ShaderNodeTexNoise",
        "checker": "ShaderNodeTexChecker",
    }.get(dt["noise_type"], "ShaderNodeTexNoise")

    code = textwrap.dedent(f"""\
    import bpy
    import math

    # === Detail Texture: {detail_type} on {object_name} ===
    # Scale: {ds}, Strength: {dstr}, Blend dist: {bd}m
    # {dt['description']}

    obj = bpy.data.objects.get("{object_name}")
    if obj is None:
        raise ValueError("Object not found: {object_name}")

    if not obj.data.materials:
        raise ValueError("Object '{object_name}' has no material")

    mat = obj.data.materials[0]
    if not mat.use_nodes:
        mat.use_nodes = True

    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    bsdf = None
    for nd in nodes:
        if nd.type == "BSDF_PRINCIPLED":
            bsdf = nd
            break
    if bsdf is None:
        raise ValueError("No Principled BSDF found in material")

    def _n(ntype, x, y, label=""):
        nd = nodes.new(type=ntype)
        nd.location = (x, y)
        if label:
            nd.label = label
        return nd

    # === Camera Distance Mask ===
    # Object Info -> Camera Data -> distance -> ramp (fade detail at distance)
    cam_data = _n("ShaderNodeCameraData", -1400, -600, "Camera Data")

    # Map camera distance to 0-1 (1 = close = detail visible, 0 = far = no detail)
    dist_ramp = _n("ShaderNodeValToRGB", -1200, -600, "Detail Distance Fade")
    dist_ramp.color_ramp.elements[0].position = 0.0
    dist_ramp.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    dist_ramp.color_ramp.elements[1].position = 1.0
    dist_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    # Normalize by blend distance
    dist_normalize = _n("ShaderNodeMath", -1300, -600, "Normalize Distance")
    dist_normalize.operation = "DIVIDE"
    dist_normalize.inputs[1].default_value = {bd}
    links.new(cam_data.outputs["View Z Depth"], dist_normalize.inputs[0])
    # Clamp 0-1
    dist_clamp = _n("ShaderNodeMath", -1250, -650, "Clamp Distance")
    dist_clamp.operation = "MINIMUM"
    dist_clamp.inputs[1].default_value = 1.0
    links.new(dist_normalize.outputs["Value"], dist_clamp.inputs[0])
    links.new(dist_clamp.outputs["Value"], dist_ramp.inputs["Fac"])

    # === Detail Texture ===
    tc = _n("ShaderNodeTexCoord", -1400, -400, "Detail TC")
    detail_tex = _n("{noise_node_type}", -1200, -400, "Detail Texture")
    """)

    # Configure noise node based on type
    if dt["noise_type"] == "voronoi":
        code += textwrap.dedent(f"""\
    detail_tex.inputs["Scale"].default_value = {ds}
    detail_tex.voronoi_dimensions = "3D"
    links.new(tc.outputs["Object"], detail_tex.inputs["Vector"])
    detail_output = detail_tex.outputs["Distance"]
    """)
    elif dt["noise_type"] == "wave":
        code += textwrap.dedent(f"""\
    detail_tex.inputs["Scale"].default_value = {ds}
    detail_tex.inputs["Distortion"].default_value = 3.0
    detail_tex.inputs["Detail"].default_value = 8.0
    detail_tex.wave_type = "BANDS"
    links.new(tc.outputs["Object"], detail_tex.inputs["Vector"])
    detail_output = detail_tex.outputs["Fac"]
    """)
    elif dt["noise_type"] == "checker":
        code += textwrap.dedent(f"""\
    detail_tex.inputs["Scale"].default_value = {ds}
    links.new(tc.outputs["Object"], detail_tex.inputs["Vector"])
    detail_output = detail_tex.outputs["Fac"]
    """)
    else:  # noise
        code += textwrap.dedent(f"""\
    detail_tex.inputs["Scale"].default_value = {ds}
    detail_tex.inputs["Detail"].default_value = 10.0
    detail_tex.inputs["Roughness"].default_value = 0.6
    links.new(tc.outputs["Object"], detail_tex.inputs["Vector"])
    detail_output = detail_tex.outputs["Fac"]
    """)

    code += textwrap.dedent(f"""\

    # === Detail Bump Node ===
    detail_bump = _n("ShaderNodeBump", -1000, -500, "Detail Bump")
    detail_bump.inputs["Strength"].default_value = {dstr}
    detail_bump.inputs["Distance"].default_value = 0.001
    links.new(detail_output, detail_bump.inputs["Height"])

    # Modulate bump strength by camera distance
    strength_mul = _n("ShaderNodeMath", -1050, -550, "Detail Strength Fade")
    strength_mul.operation = "MULTIPLY"
    links.new(dist_ramp.outputs["Color"], strength_mul.inputs[0])
    strength_mul.inputs[1].default_value = {dstr}
    # We connect via driver concept: use the faded value as bump strength
    # by inserting before existing normal chain

    # Find what currently connects to BSDF Normal
    normal_input = bsdf.inputs["Normal"]
    existing_normal = None
    for lnk in links:
        if lnk.to_socket == normal_input:
            existing_normal = lnk
            break

    if existing_normal:
        # Chain: existing normal -> detail bump -> BSDF
        prev_normal = existing_normal.from_socket
        links.remove(existing_normal)
        links.new(prev_normal, detail_bump.inputs["Normal"])
    links.new(detail_bump.outputs["Normal"], normal_input)

    result = {{
        "object": "{object_name}",
        "detail_type": "{detail_type}",
        "detail_scale": {ds},
        "detail_strength": {dstr},
        "blend_distance": {bd},
    }}
    """)

    return code


# ---------------------------------------------------------------------------
# Code Generation: Bake Maps
# ---------------------------------------------------------------------------

def generate_bake_map_code(
    object_name: str,
    bake_type: str = "position",
    image_size: int = 1024,
) -> str:
    """Generate Blender Python code to bake additional map types.

    Types beyond standard PBR bakes:
      - 'position': World/object space position -> RGB
      - 'bent_normal': Averaged surrounding normal for AO-aware lighting
      - 'world_normal': World-space normals -> RGB
      - 'flow': UV flow direction map for animated effects
      - 'gradient': Height gradient for height-based effects

    Args:
        object_name: Source object name.
        bake_type: Map type from BAKE_MAP_TYPES.
        image_size: Output image resolution.

    Returns:
        Blender Python code string for blender_execute.

    Raises:
        ValueError: If bake_type is unknown.
    """
    if bake_type not in BAKE_MAP_TYPES:
        raise ValueError(
            f"Unknown bake map type: '{bake_type}'. "
            f"Valid: {sorted(BAKE_MAP_TYPES.keys())}"
        )

    bm = BAKE_MAP_TYPES[bake_type]
    size = max(64, min(8192, int(image_size)))

    # Build type-specific shader setup
    if bake_type == "position":
        shader_code = """\
# Position map: world position -> RGB
geom = nodes.new(type="ShaderNodeNewGeometry")
geom.location = (-400, 0)
emission = nodes.new(type="ShaderNodeEmission")
emission.location = (-200, 0)
links.new(geom.outputs["Position"], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])
"""
    elif bake_type == "world_normal":
        shader_code = """\
# World normal: world-space normal -> RGB
geom = nodes.new(type="ShaderNodeNewGeometry")
geom.location = (-600, 0)
# Map [-1,1] -> [0,1]
map_range = nodes.new(type="ShaderNodeMapRange")
map_range.location = (-400, 0)
map_range.data_type = "FLOAT_VECTOR"
map_range.inputs[7].default_value = (-1.0, -1.0, -1.0)
map_range.inputs[8].default_value = (1.0, 1.0, 1.0)
map_range.inputs[9].default_value = (0.0, 0.0, 0.0)
map_range.inputs[10].default_value = (1.0, 1.0, 1.0)
links.new(geom.outputs["Normal"], map_range.inputs[6])
emission = nodes.new(type="ShaderNodeEmission")
emission.location = (-200, 0)
links.new(map_range.outputs[3], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])
"""
    elif bake_type == "bent_normal":
        shader_code = """\
# Bent normal: approximate via AO-weighted normal direction
# Bake AO first, then use it to bias the normal
geom = nodes.new(type="ShaderNodeNewGeometry")
geom.location = (-600, 0)
ao = nodes.new(type="ShaderNodeAmbientOcclusion")
ao.location = (-400, 0)
ao.inputs["Distance"].default_value = 1.0
mix = nodes.new(type="ShaderNodeMixRGB")
mix.location = (-200, 0)
mix.blend_type = "MIX"
mix.inputs["Fac"].default_value = 0.5
links.new(geom.outputs["Normal"], mix.inputs["Color1"])
links.new(ao.outputs["Color"], mix.inputs["Color2"])
emission = nodes.new(type="ShaderNodeEmission")
emission.location = (0, 0)
links.new(mix.outputs["Color"], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])
"""
    elif bake_type == "flow":
        shader_code = """\
# Flow map: UV gradient direction
tc = nodes.new(type="ShaderNodeTexCoord")
tc.location = (-600, 0)
sep = nodes.new(type="ShaderNodeSeparateXYZ")
sep.location = (-400, 0)
links.new(tc.outputs["UV"], sep.inputs["Vector"])
comb = nodes.new(type="ShaderNodeCombineXYZ")
comb.location = (-200, 0)
links.new(sep.outputs["X"], comb.inputs["X"])
links.new(sep.outputs["Y"], comb.inputs["Y"])
comb.inputs["Z"].default_value = 0.0
emission = nodes.new(type="ShaderNodeEmission")
emission.location = (0, 0)
links.new(comb.outputs["Vector"], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])
"""
    elif bake_type == "gradient":
        shader_code = """\
# Height gradient: Z position normalized to object bounds
geom = nodes.new(type="ShaderNodeNewGeometry")
geom.location = (-600, 0)
sep = nodes.new(type="ShaderNodeSeparateXYZ")
sep.location = (-400, 0)
links.new(geom.outputs["Position"], sep.inputs["Vector"])
# Use Z as greyscale height
emission = nodes.new(type="ShaderNodeEmission")
emission.location = (-200, 0)
comb = nodes.new(type="ShaderNodeCombineXYZ")
comb.location = (-300, 0)
links.new(sep.outputs["Z"], comb.inputs["X"])
links.new(sep.outputs["Z"], comb.inputs["Y"])
links.new(sep.outputs["Z"], comb.inputs["Z"])
links.new(comb.outputs["Vector"], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])
"""
    else:
        shader_code = ""

    code = f"""\
import bpy

# === Bake Map: {bake_type} for {object_name} ({size}x{size}) ===

obj = bpy.data.objects.get("{object_name}")
if obj is None:
    raise ValueError("Object not found: {object_name}")

# Create bake image
img_name = "{object_name}_{bake_type}_map"
img = bpy.data.images.new(img_name, width={size}, height={size},
                           alpha=False, float_buffer=True)
img.colorspace_settings.name = "{bm['colorspace']}"

# Create temporary material with emit shader for baking
bake_mat = bpy.data.materials.new(name="__bake_{bake_type}_tmp")
bake_mat.use_nodes = True
tree = bake_mat.node_tree
nodes = tree.nodes
links = tree.links
nodes.clear()

output = nodes.new(type="ShaderNodeOutputMaterial")
output.location = (200, 0)

{shader_code}
# Image texture node (target for bake)
img_node = nodes.new(type="ShaderNodeTexImage")
img_node.location = (200, -300)
img_node.image = img
img_node.select = True
nodes.active = img_node

# Assign temp material
orig_materials = [slot.material for slot in obj.material_slots]
if obj.data.materials:
    obj.data.materials[0] = bake_mat
else:
    obj.data.materials.append(bake_mat)

# Select object
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

# Bake emit pass
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 1
bpy.ops.object.bake(type="EMIT")

# Restore original materials
if orig_materials:
    for i, m in enumerate(orig_materials):
        if i < len(obj.data.materials):
            obj.data.materials[i] = m
else:
    obj.data.materials.clear()

# Cleanup temp material
bpy.data.materials.remove(bake_mat)

result = {{
    "image": img_name,
    "bake_type": "{bake_type}",
    "size": {size},
    "colorspace": "{bm['colorspace']}",
}}
"""

    return code


# ---------------------------------------------------------------------------
# Pure-Logic: Seamless Tileable Noise Texture (4D torus mapping)
# ---------------------------------------------------------------------------

def generate_seamless_noise_texture(
    width: int = 256,
    height: int = 256,
    scale: float = 4.0,
    octaves: int = 4,
    persistence: float = 0.5,
    seed: int = 0,
) -> "np.ndarray":
    """Generate a perfectly tileable 2D noise texture using 4D torus mapping.

    Maps 2D texture coordinates onto a 4D torus (two pairs of sin/cos) and
    evaluates noise in 4D space.  Because the torus surface wraps seamlessly
    in both U and V directions, the resulting 2D texture tiles perfectly in
    both axes with **zero visible seams**.

    Since the noise backend is 2D only, the 4D mapping is approximated by
    evaluating two independent 2D noise lookups at torus-mapped coordinates
    and blending them.  This produces visually seamless results that are
    indistinguishable from true 4D noise for texture generation purposes.

    Pure numpy -- no bpy dependency.

    Parameters
    ----------
    width, height : int
        Output texture dimensions in pixels.
    scale : float
        Noise frequency.  Higher values produce finer detail.
    octaves : int
        Number of fBm octaves.
    persistence : float
        Amplitude decay per octave.
    seed : int
        Random seed for deterministic generation.

    Returns
    -------
    np.ndarray
        2D array of shape (height, width) with values in [0, 1].
    """
    import numpy as np

    gen_a = _make_noise_gen(seed)
    gen_b = _make_noise_gen(seed + 31337)  # offset seed for second lookup

    # Parametric angles for the torus
    u = np.linspace(0, 2 * math.pi, width, endpoint=False)   # shape (width,)
    v = np.linspace(0, 2 * math.pi, height, endpoint=False)  # shape (height,)
    uu, vv = np.meshgrid(u, v)  # both (height, width)

    # Map onto a 4D torus: (cos(u), sin(u), cos(v), sin(v)) * scale
    # We split into two 2D noise evaluations:
    #   noise_a( cos(u)*scale, cos(v)*scale )
    #   noise_b( sin(u)*scale, sin(v)*scale )
    # and average them.  This produces seamless tiling because each
    # trig pair wraps around 2*pi identically.
    cos_u = np.cos(uu) * scale
    sin_u = np.sin(uu) * scale
    cos_v = np.cos(vv) * scale
    sin_v = np.sin(vv) * scale

    # Accumulate fBm octaves
    result = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    for _ in range(octaves):
        noise_a = gen_a.noise2_array(cos_u * frequency, cos_v * frequency)
        noise_b = gen_b.noise2_array(sin_u * frequency, sin_v * frequency)
        result += (noise_a + noise_b) * 0.5 * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= 2.0

    if max_val > 0:
        result /= max_val

    # Normalize to [0, 1]
    rmin, rmax = result.min(), result.max()
    if rmax - rmin > 1e-10:
        result = (result - rmin) / (rmax - rmin)
    else:
        result = np.full_like(result, 0.5)

    return result


def _make_noise_gen(seed: int):
    """Thin wrapper to import the terrain noise generator.

    Defers the import so that texture_quality.py doesn't have a hard
    dependency on _terrain_noise at module load time.
    """
    from . import _terrain_noise
    return _terrain_noise._make_noise_generator(seed)


# ---------------------------------------------------------------------------
# Pure-Logic: Curvature Map Computation
# ---------------------------------------------------------------------------

def compute_curvature_map(
    verts: list[tuple[float, float, float]],
    edges: list[tuple[int, int]],
    faces: list[list[int]],
) -> list[float]:
    """Compute per-vertex curvature from mesh topology using dihedral angles.

    Calculates the mean curvature at each vertex by averaging the signed
    dihedral angles of all edges connected to that vertex.  The dihedral
    angle of an edge is the angle between the normals of its two adjacent
    faces.

    The output is normalized to [0, 1] where:
      - 0.0 = strongly concave (deep cavities, crevices)
      - 0.5 = flat (zero curvature)
      - 1.0 = strongly convex (sharp edges, ridges)

    This data can be used to drive:
      - Edge wear maps (convex = brighter = more worn)
      - Cavity dirt maps (concave = darker = more dirt)
      - Ambient occlusion approximation

    Pure logic -- uses only basic math on vertex/edge/face data.  No bpy
    or bmesh dependency.

    Parameters
    ----------
    verts : list of (x, y, z) tuples
        Vertex positions.
    edges : list of (v0, v1) tuples
        Edge connectivity (vertex index pairs).
    faces : list of list[int]
        Face vertex index lists (triangles or quads).

    Returns
    -------
    list of float
        Per-vertex curvature values in [0, 1], same length as *verts*.
        0.5 = flat, >0.5 = convex, <0.5 = concave.
    """
    import numpy as np

    n_verts = len(verts)
    if n_verts == 0:
        return []

    v = np.array(verts, dtype=np.float64)

    # Build face normals and edge-to-face adjacency
    face_normals = []
    for face in faces:
        if len(face) < 3:
            face_normals.append(np.array([0.0, 0.0, 1.0]))
            continue
        v0 = v[face[0]]
        v1 = v[face[1]]
        v2 = v[face[2]]
        e1 = v1 - v0
        e2 = v2 - v0
        normal = np.cross(e1, e2)
        length = np.linalg.norm(normal)
        if length > 1e-10:
            normal /= length
        else:
            normal = np.array([0.0, 0.0, 1.0])
        face_normals.append(normal)

    # Build edge -> adjacent face indices mapping
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        n = len(face)
        for i in range(n):
            a = face[i]
            b = face[(i + 1) % n]
            key = (min(a, b), max(a, b))
            if key not in edge_faces:
                edge_faces[key] = []
            edge_faces[key].append(fi)

    # Compute dihedral angles per edge and accumulate per vertex
    curvature_sum = np.zeros(n_verts, dtype=np.float64)
    curvature_count = np.zeros(n_verts, dtype=np.int32)

    for (a, b), face_list in edge_faces.items():
        if len(face_list) != 2:
            # Boundary edge or non-manifold: skip
            continue

        n0 = face_normals[face_list[0]]
        n1 = face_normals[face_list[1]]

        # Dihedral angle: angle between the two face normals
        dot = np.clip(np.dot(n0, n1), -1.0, 1.0)
        angle = math.acos(dot)  # [0, pi]

        # Determine sign: convex vs concave
        # Use the edge direction cross product to determine
        # if the surface bends outward (convex) or inward (concave)
        edge_vec = v[b] - v[a]

        # Cross product of face normals with edge direction gives
        # the signed curvature direction
        cross = np.cross(n0, n1)
        sign = 1.0 if np.dot(cross, edge_vec) >= 0 else -1.0

        signed_angle = sign * angle

        # Accumulate to both edge vertices
        curvature_sum[a] += signed_angle
        curvature_count[a] += 1
        curvature_sum[b] += signed_angle
        curvature_count[b] += 1

    # Average curvature per vertex
    mask = curvature_count > 0
    mean_curvature = np.zeros(n_verts, dtype=np.float64)
    mean_curvature[mask] = curvature_sum[mask] / curvature_count[mask]

    # Normalize to [0, 1]:  map [-pi, pi] -> [0, 1]
    # In practice values rarely reach pi; use a softer mapping
    # with tanh-like scaling for better visual contrast
    # Map: 0.5 + 0.5 * tanh(curvature * 2)
    normalized = 0.5 + 0.5 * np.tanh(mean_curvature * 2.0)

    return normalized.tolist()
