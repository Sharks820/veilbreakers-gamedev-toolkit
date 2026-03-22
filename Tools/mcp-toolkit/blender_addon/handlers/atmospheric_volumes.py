"""Atmospheric volume props system for biome-appropriate ambient effects.

NO bpy/bmesh imports. Fully testable without Blender.

Computes placement positions and parameters for volumetric effects
(fog, dust, fireflies, god rays, smoke, spore clouds, void shimmer)
based on biome type, area bounds, and density rules.

Provides:
  - ATMOSPHERIC_VOLUMES: 7 volume type definitions
  - BIOME_ATMOSPHERE_RULES: Per-biome volume assignments
  - compute_atmospheric_placements: Generate volume placements for a biome
  - compute_volume_mesh_spec: Generate mesh spec for a volume shape
  - estimate_atmosphere_performance: Estimate GPU cost of volumes
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Volume Type Definitions -- 7 types
# ---------------------------------------------------------------------------

ATMOSPHERIC_VOLUMES: dict[str, dict[str, Any]] = {
    "ground_fog": {
        "shape": "box",
        "density": 0.3,
        "height": 1.5,
        "color": (0.7, 0.7, 0.8),
        "opacity": 0.4,
        "animation": "drift",
        "animation_speed": 0.3,
        "particle_type": None,
    },
    "dust_motes": {
        "shape": "box",
        "density": 0.1,
        "height": 3.0,
        "color": (0.8, 0.75, 0.6),
        "opacity": 0.15,
        "animation": "float",
        "animation_speed": 0.02,
        "particle_type": "point",
    },
    "fireflies": {
        "shape": "sphere",
        "density": 0.05,
        "height": 2.5,
        "color": (0.8, 1.0, 0.5),
        "opacity": 0.8,
        "animation": "wander",
        "animation_speed": 0.5,
        "particle_type": "emissive",
        "emission_strength": 5.0,
    },
    "god_rays": {
        "shape": "cone",
        "density": 0.2,
        "height": 15.0,
        "color": (1.0, 0.95, 0.8),
        "opacity": 0.25,
        "animation": "pulse",
        "animation_speed": 0.1,
        "particle_type": None,
        "direction": "down",
    },
    "smoke_plume": {
        "shape": "cone",
        "density": 0.4,
        "height": 10.0,
        "color": (0.3, 0.3, 0.3),
        "opacity": 0.5,
        "animation": "rise",
        "animation_speed": 1.0,
        "particle_type": None,
        "direction": "up",
    },
    "spore_cloud": {
        "shape": "sphere",
        "density": 0.15,
        "height": 3.0,
        "color": (0.5, 0.7, 0.3),
        "opacity": 0.3,
        "animation": "float",
        "animation_speed": 0.1,
        "particle_type": "point",
    },
    "void_shimmer": {
        "shape": "sphere",
        "density": 0.1,
        "height": 4.0,
        "color": (0.3, 0.1, 0.5),
        "opacity": 0.35,
        "animation": "distortion",
        "animation_speed": 0.5,
        "particle_type": None,
        "distortion": True,
    },
}


# ---------------------------------------------------------------------------
# Biome -> Atmosphere Rules
# ---------------------------------------------------------------------------

BIOME_ATMOSPHERE_RULES: dict[str, list[dict[str, Any]]] = {
    "dark_forest": [
        {"volume": "ground_fog", "coverage": 0.6, "min_count": 3},
        {"volume": "dust_motes", "coverage": 0.3, "min_count": 2},
        {"volume": "god_rays", "coverage": 0.1, "min_count": 1},
        {"volume": "fireflies", "coverage": 0.2, "min_count": 1},
    ],
    "corrupted_swamp": [
        {"volume": "ground_fog", "coverage": 0.8, "min_count": 4},
        {"volume": "spore_cloud", "coverage": 0.4, "min_count": 2},
        {"volume": "void_shimmer", "coverage": 0.1, "min_count": 1},
    ],
    "volcanic_wastes": [
        {"volume": "smoke_plume", "coverage": 0.5, "min_count": 3},
        {"volume": "dust_motes", "coverage": 0.3, "min_count": 2},
    ],
    "frozen_peaks": [
        {"volume": "ground_fog", "coverage": 0.4, "min_count": 2},
        {"volume": "dust_motes", "coverage": 0.2, "min_count": 1},
    ],
    "ancient_ruins": [
        {"volume": "dust_motes", "coverage": 0.5, "min_count": 3},
        {"volume": "god_rays", "coverage": 0.2, "min_count": 1},
        {"volume": "ground_fog", "coverage": 0.2, "min_count": 1},
    ],
    "haunted_moor": [
        {"volume": "ground_fog", "coverage": 0.7, "min_count": 4},
        {"volume": "void_shimmer", "coverage": 0.2, "min_count": 1},
        {"volume": "fireflies", "coverage": 0.1, "min_count": 1},
    ],
    "enchanted_glade": [
        {"volume": "fireflies", "coverage": 0.5, "min_count": 3},
        {"volume": "god_rays", "coverage": 0.3, "min_count": 2},
        {"volume": "dust_motes", "coverage": 0.2, "min_count": 1},
    ],
    "bone_desert": [
        {"volume": "dust_motes", "coverage": 0.6, "min_count": 3},
        {"volume": "smoke_plume", "coverage": 0.1, "min_count": 1},
    ],
    "crystal_caverns": [
        {"volume": "void_shimmer", "coverage": 0.3, "min_count": 2},
        {"volume": "dust_motes", "coverage": 0.4, "min_count": 2},
        {"volume": "spore_cloud", "coverage": 0.1, "min_count": 1},
    ],
    "blood_marsh": [
        {"volume": "ground_fog", "coverage": 0.7, "min_count": 4},
        {"volume": "smoke_plume", "coverage": 0.2, "min_count": 1},
        {"volume": "spore_cloud", "coverage": 0.3, "min_count": 2},
    ],
}

# Default fallback for unknown biomes
_DEFAULT_ATMOSPHERE: list[dict[str, Any]] = [
    {"volume": "ground_fog", "coverage": 0.3, "min_count": 2},
    {"volume": "dust_motes", "coverage": 0.2, "min_count": 1},
]


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_atmospheric_placements(
    biome_name: str,
    area_bounds: tuple[float, float, float, float],
    seed: int = 42,
    density_scale: float = 1.0,
) -> list[dict[str, Any]]:
    """Generate atmospheric volume placements appropriate for a biome.

    Parameters
    ----------
    biome_name : str
        Name of the biome (key in BIOME_ATMOSPHERE_RULES).
    area_bounds : tuple
        (min_x, min_y, max_x, max_y) defining the placement area.
    seed : int
        Random seed for deterministic generation.
    density_scale : float
        Multiplier for volume counts (default 1.0).

    Returns
    -------
    list of dict
        Volume placements, each with: ``volume_type``, ``position`` (x, y, z),
        ``size`` (x, y, z), ``shape``, ``color``, ``density``, ``opacity``,
        ``animation``, ``animation_speed``, and optional ``particle_type``,
        ``emission_strength``, ``distortion``.
    """
    rng = random.Random(seed)
    rules = BIOME_ATMOSPHERE_RULES.get(biome_name, _DEFAULT_ATMOSPHERE)

    min_x, min_y, max_x, max_y = area_bounds
    area_w = max_x - min_x
    area_h = max_y - min_y
    area_total = area_w * area_h

    placements: list[dict[str, Any]] = []

    for rule in rules:
        vol_name = rule["volume"]
        vol_def = ATMOSPHERIC_VOLUMES[vol_name]
        coverage = rule["coverage"]
        min_count = max(1, int(rule["min_count"] * density_scale))

        # Compute how many volumes to place based on coverage and area
        vol_height = vol_def["height"]

        # Each volume covers a certain area depending on shape
        if vol_def["shape"] == "sphere":
            vol_area = math.pi * (vol_height * 2) ** 2
        elif vol_def["shape"] == "cone":
            vol_area = math.pi * (vol_height * 0.5) ** 2
        else:  # box
            vol_area = (vol_height * 4) ** 2

        target_coverage_area = area_total * coverage
        count = max(min_count, int(target_coverage_area / max(1.0, vol_area)))
        # Cap to reasonable maximum
        count = min(count, 50)

        for _ in range(count):
            px = rng.uniform(min_x, max_x)
            py = rng.uniform(min_y, max_y)
            pz = 0.0  # Ground level

            # Size varies per shape
            if vol_def["shape"] == "box":
                sx = rng.uniform(vol_height * 2, vol_height * 6)
                sy = rng.uniform(vol_height * 2, vol_height * 6)
                sz = vol_height * rng.uniform(0.8, 1.2)
            elif vol_def["shape"] == "sphere":
                r = vol_height * rng.uniform(0.8, 1.5)
                sx = sy = sz = r * 2
                pz = r * 0.5  # Center sphere above ground
            elif vol_def["shape"] == "cone":
                base_r = vol_height * rng.uniform(0.3, 0.6)
                sx = sy = base_r * 2
                sz = vol_height * rng.uniform(0.8, 1.2)
                if vol_def.get("direction") == "up":
                    pz = 0.0
                else:  # down (god_rays)
                    pz = sz
            else:
                sx = sy = sz = vol_height * 2

            placement: dict[str, Any] = {
                "volume_type": vol_name,
                "position": (round(px, 2), round(py, 2), round(pz, 2)),
                "size": (round(sx, 2), round(sy, 2), round(sz, 2)),
                "shape": vol_def["shape"],
                "color": vol_def["color"],
                "density": vol_def["density"],
                "opacity": vol_def["opacity"],
                "animation": vol_def["animation"],
                "animation_speed": vol_def["animation_speed"],
            }

            if vol_def.get("particle_type"):
                placement["particle_type"] = vol_def["particle_type"]
            if vol_def.get("emission_strength"):
                placement["emission_strength"] = vol_def["emission_strength"]
            if vol_def.get("distortion"):
                placement["distortion"] = True
            if vol_def.get("direction"):
                placement["direction"] = vol_def["direction"]

            placements.append(placement)

    return placements


def compute_volume_mesh_spec(
    volume_type: str,
    position: tuple[float, float, float] = (0, 0, 0),
    scale: float = 1.0,
) -> dict[str, Any]:
    """Generate a mesh specification for a volume shape.

    Parameters
    ----------
    volume_type : str
        Key in ATMOSPHERIC_VOLUMES.
    position : tuple
        (x, y, z) center position.
    scale : float
        Scale multiplier.

    Returns
    -------
    dict
        Mesh spec with ``vertices``, ``faces``, ``shape``, ``transform``.

    Raises
    ------
    ValueError
        If volume_type is unknown.
    """
    if volume_type not in ATMOSPHERIC_VOLUMES:
        raise ValueError(
            f"Unknown volume type '{volume_type}'. "
            f"Valid types: {sorted(ATMOSPHERIC_VOLUMES.keys())}"
        )

    vol_def = ATMOSPHERIC_VOLUMES[volume_type]
    shape = vol_def["shape"]
    h = vol_def["height"] * scale

    if shape == "box":
        # Simple box vertices
        hw = h * 2  # half-width
        hd = h * 2  # half-depth
        vertices = [
            (position[0] - hw, position[1] - hd, position[2]),
            (position[0] + hw, position[1] - hd, position[2]),
            (position[0] + hw, position[1] + hd, position[2]),
            (position[0] - hw, position[1] + hd, position[2]),
            (position[0] - hw, position[1] - hd, position[2] + h),
            (position[0] + hw, position[1] - hd, position[2] + h),
            (position[0] + hw, position[1] + hd, position[2] + h),
            (position[0] - hw, position[1] + hd, position[2] + h),
        ]
        faces = [
            (0, 1, 2, 3), (4, 5, 6, 7),
            (0, 1, 5, 4), (2, 3, 7, 6),
            (0, 3, 7, 4), (1, 2, 6, 5),
        ]
    elif shape == "sphere":
        # Simplified sphere: icosphere-like with 12 vertices
        r = h
        phi = (1 + math.sqrt(5)) / 2
        s = r / math.sqrt(1 + phi * phi)
        vertices = [
            (position[0] + v[0] * s, position[1] + v[1] * s, position[2] + v[2] * s + r)
            for v in [
                (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
                (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
                (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
            ]
        ]
        faces = [
            (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
            (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
            (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
            (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
        ]
    else:  # cone
        # Cone approximation: 8-sided base + apex
        segments = 8
        base_r = h * 0.4
        vertices = [(position[0], position[1], position[2] + h)]  # apex
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            vx = position[0] + math.cos(angle) * base_r
            vy = position[1] + math.sin(angle) * base_r
            vz = position[2]
            vertices.append((vx, vy, vz))
        faces = []
        for i in range(segments):
            next_i = (i % segments) + 1
            next_next = (next_i % segments) + 1
            faces.append((0, i + 1, next_next if next_next <= segments else 1))
        # Base face
        faces.append(tuple(range(1, segments + 1)))

    return {
        "vertices": [(round(v[0], 3), round(v[1], 3), round(v[2], 3)) for v in vertices],
        "faces": faces,
        "shape": shape,
        "transform": {
            "position": position,
            "scale": scale,
        },
        "volume_type": volume_type,
        "color": vol_def["color"],
        "density": vol_def["density"],
    }


def estimate_atmosphere_performance(
    placements: list[dict[str, Any]],
    particle_cost: float = 2.0,
    distortion_cost: float = 5.0,
) -> dict[str, Any]:
    """Estimate GPU cost of atmospheric volume placements.

    Parameters
    ----------
    placements : list of dict
        Volume placements from ``compute_atmospheric_placements``.
    particle_cost : float
        Relative cost multiplier for particle volumes.
    distortion_cost : float
        Relative cost multiplier for distortion volumes.

    Returns
    -------
    dict
        Performance summary: total_volumes, particle_volumes, distortion_volumes,
        estimated_cost, recommendation.
    """
    total = len(placements)
    particle_count = sum(1 for p in placements if p.get("particle_type"))
    distortion_count = sum(1 for p in placements if p.get("distortion"))

    cost = total + particle_count * particle_cost + distortion_count * distortion_cost

    if cost <= 15:
        recommendation = "excellent"
    elif cost <= 30:
        recommendation = "good"
    elif cost <= 60:
        recommendation = "acceptable"
    elif cost <= 100:
        recommendation = "heavy - reduce particle counts"
    else:
        recommendation = "excessive - reduce volumes and disable distortion"

    return {
        "total_volumes": total,
        "particle_volumes": particle_count,
        "distortion_volumes": distortion_count,
        "estimated_cost": round(cost, 2),
        "recommendation": recommendation,
        "volume_type_counts": _count_by_type(placements),
    }


def _count_by_type(placements: list[dict[str, Any]]) -> dict[str, int]:
    """Count placements by volume_type."""
    counts: dict[str, int] = {}
    for p in placements:
        vt = p.get("volume_type", "unknown")
        counts[vt] = counts.get(vt, 0) + 1
    return counts
