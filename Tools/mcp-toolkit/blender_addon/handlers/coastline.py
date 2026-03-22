"""Coastline terrain generator -- pure logic, no bpy/bmesh.

Generates coastline terrain strips with varying styles (rocky, sandy, cliffs,
harbor). Returns mesh spec dicts for terrain geometry, material zones, and
feature placements (sea stacks, tide pools, docks, caves).

All functions are pure and operate on plain Python data structures.
Fully testable without Blender.
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Style configuration
# ---------------------------------------------------------------------------

COASTLINE_STYLES: dict[str, dict[str, Any]] = {
    "rocky": {
        "description": "Irregular shoreline with rock formations and tide pools",
        "shore_noise_amp": 3.0,
        "shore_noise_freq": 0.15,
        "base_elevation": 0.5,
        "slope_gradient": 0.8,
        "features": ["sea_stack", "tide_pool", "rock_outcrop"],
        "material_zones": ["rock", "wet_rock", "gravel", "water_edge"],
    },
    "sandy": {
        "description": "Smooth beach gradient with dune mounds",
        "shore_noise_amp": 1.0,
        "shore_noise_freq": 0.05,
        "base_elevation": 0.2,
        "slope_gradient": 0.3,
        "features": ["dune_mound", "driftwood", "shell_cluster"],
        "material_zones": ["dry_sand", "wet_sand", "water_edge"],
    },
    "cliffs": {
        "description": "Vertical drop with overhang and cave entrances",
        "shore_noise_amp": 1.5,
        "shore_noise_freq": 0.1,
        "base_elevation": 8.0,
        "slope_gradient": 5.0,
        "features": ["cave_entrance", "overhang", "rock_pillar"],
        "material_zones": ["cliff_face", "cliff_top", "rock_base", "water_edge"],
    },
    "harbor": {
        "description": "Curved cove with flat dock area and breakwater",
        "shore_noise_amp": 0.5,
        "shore_noise_freq": 0.03,
        "base_elevation": 1.0,
        "slope_gradient": 0.4,
        "features": ["dock", "breakwater", "mooring_post", "crate_stack"],
        "material_zones": ["stone_quay", "wood_dock", "gravel", "water_edge"],
    },
}


# ---------------------------------------------------------------------------
# Noise utility (deterministic hash-based, no external dependency)
# ---------------------------------------------------------------------------

def _hash_noise(x: float, y: float, seed: int) -> float:
    """Simple deterministic pseudo-noise in [-1, 1]."""
    # Mix coordinates with seed for deterministic results
    val = math.sin(x * 12.9898 + y * 78.233 + seed * 43.1234) * 43758.5453
    return (val - math.floor(val)) * 2.0 - 1.0


def _fbm_noise(x: float, y: float, seed: int, octaves: int = 4) -> float:
    """Fractal Brownian motion noise via hash-based value noise."""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        total += _hash_noise(x * frequency, y * frequency, seed) * amplitude
        max_val += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return total / max_val if max_val > 0 else 0.0


# ---------------------------------------------------------------------------
# Shoreline profile generation
# ---------------------------------------------------------------------------

def _generate_shoreline_profile(
    length: float,
    style: str,
    resolution: int,
    seed: int,
) -> list[float]:
    """Generate a 1D shoreline offset profile (lateral displacement from center).

    Returns a list of offset values along the coastline length.
    Positive = land protrusion, negative = water indentation.
    """
    config = COASTLINE_STYLES[style]
    amp = config["shore_noise_amp"]
    freq = config["shore_noise_freq"]

    rng = random.Random(seed)
    profile: list[float] = []

    for i in range(resolution):
        t = i / max(resolution - 1, 1)
        x = t * length

        # Base noise
        noise = _fbm_noise(x * freq, seed * 0.1, seed, octaves=4)
        offset = noise * amp

        # Style-specific modifiers
        if style == "harbor":
            # Curved cove shape: parabolic indent
            cove_t = (t - 0.5) * 2  # [-1, 1]
            cove_offset = -(1 - cove_t * cove_t) * amp * 3
            offset += cove_offset
        elif style == "cliffs":
            # More irregular, sharper features
            offset += _hash_noise(x * freq * 2, 0, seed + 1) * amp * 0.5
        elif style == "rocky":
            # Jagged shoreline
            offset += _hash_noise(x * freq * 3, 0, seed + 2) * amp * 0.8

        profile.append(offset)

    return profile


# ---------------------------------------------------------------------------
# Terrain mesh generation
# ---------------------------------------------------------------------------

def _generate_coastline_mesh(
    length: float,
    width: float,
    style: str,
    resolution_along: int,
    resolution_across: int,
    shoreline_profile: list[float],
    seed: int,
) -> dict[str, Any]:
    """Generate coastline terrain mesh vertices and faces.

    The mesh is a strip running along X, with Y going from water to land.
    The shoreline runs roughly along the center.
    """
    config = COASTLINE_STYLES[style]
    base_elev = config["base_elevation"]
    slope = config["slope_gradient"]

    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int, int]] = []

    half_width = width / 2.0
    shore_y = 0.0  # Shoreline at Y=0

    for i in range(resolution_along):
        t_along = i / max(resolution_along - 1, 1)
        x = t_along * length
        shore_offset = shoreline_profile[min(i, len(shoreline_profile) - 1)]

        for j in range(resolution_across):
            t_across = j / max(resolution_across - 1, 1)
            y = -half_width + t_across * width + shore_offset

            # Elevation: water side is low, land side ramps up
            land_factor = max(0.0, (y - shore_y) / half_width)

            if style == "cliffs":
                # Steep cliff face with slight overhang
                if land_factor > 0.3:
                    z = base_elev * min(1.0, (land_factor - 0.3) / 0.1)
                    # Add noise to cliff face
                    z += _hash_noise(x * 0.1, y * 0.2, seed + 3) * 0.5
                else:
                    z = land_factor * 0.5
            elif style == "sandy":
                # Gentle gradient
                z = land_factor * base_elev
                # Dune bumps on land side
                if land_factor > 0.6:
                    dune = _fbm_noise(x * 0.05, y * 0.05, seed + 4, octaves=3)
                    z += max(0, dune) * base_elev * 0.5
            elif style == "harbor":
                # Flat dock area in center, rising edges
                center_t = abs(t_along - 0.5) * 2  # [0, 1] from center
                z = land_factor * base_elev * (0.3 + 0.7 * center_t)
            else:
                # Rocky: varied elevation
                z = land_factor * base_elev
                z += _hash_noise(x * 0.08, y * 0.08, seed + 5) * slope * 0.3

            # Add micro-noise for natural look
            z += _hash_noise(x * 0.5, y * 0.5, seed + 6) * 0.1

            # Water side stays flat/low
            if land_factor <= 0:
                z = min(z, -0.1)

            vertices.append((x, y, z))

    # Generate quad faces
    for i in range(resolution_along - 1):
        for j in range(resolution_across - 1):
            v0 = i * resolution_across + j
            v1 = v0 + 1
            v2 = (i + 1) * resolution_across + j + 1
            v3 = (i + 1) * resolution_across + j
            faces.append((v0, v1, v2, v3))

    return {
        "vertices": vertices,
        "faces": faces,
        "resolution_along": resolution_along,
        "resolution_across": resolution_across,
    }


# ---------------------------------------------------------------------------
# Feature placement
# ---------------------------------------------------------------------------

def _place_features(
    length: float,
    width: float,
    style: str,
    shoreline_profile: list[float],
    resolution_along: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Place coastline features (sea stacks, tide pools, docks, etc.)."""
    config = COASTLINE_STYLES[style]
    feature_types = config["features"]
    rng = random.Random(seed + 100)

    features: list[dict[str, Any]] = []
    half_width = width / 2.0

    # Number of features scales with coastline length
    num_features = max(3, int(length / 20.0))

    for _ in range(num_features):
        ftype = rng.choice(feature_types)
        t = rng.random()
        x = t * length
        idx = min(int(t * resolution_along), len(shoreline_profile) - 1)
        shore_offset = shoreline_profile[idx]

        if ftype in ("sea_stack", "rock_pillar"):
            # Place in water, near shore
            y = shore_offset - rng.uniform(2, half_width * 0.5)
            z = rng.uniform(1, 4)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
                "height": z,
                "radius": rng.uniform(0.5, 2.0),
            })
        elif ftype in ("tide_pool",):
            # Place at shoreline
            y = shore_offset + rng.uniform(-1, 1)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
                "radius": rng.uniform(0.5, 2.0),
                "depth": rng.uniform(0.1, 0.4),
            })
        elif ftype in ("rock_outcrop",):
            # Place on shore/land
            y = shore_offset + rng.uniform(0, half_width * 0.3)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
                "size": rng.uniform(1.0, 4.0),
            })
        elif ftype in ("cave_entrance",):
            # Place in cliff face
            y = shore_offset + rng.uniform(1, 3)
            z = rng.uniform(0, config["base_elevation"] * 0.5)
            features.append({
                "type": ftype,
                "position": (x, y, z),
                "width": rng.uniform(2, 5),
                "height": rng.uniform(2, 4),
            })
        elif ftype in ("overhang",):
            y = shore_offset + rng.uniform(2, 5)
            z = config["base_elevation"] * rng.uniform(0.7, 1.0)
            features.append({
                "type": ftype,
                "position": (x, y, z),
                "depth": rng.uniform(1, 3),
                "width": rng.uniform(3, 8),
            })
        elif ftype in ("dock",):
            y = shore_offset - rng.uniform(1, 5)
            features.append({
                "type": ftype,
                "position": (x, y, 0.2),
                "length": rng.uniform(5, 15),
                "width": rng.uniform(2, 4),
            })
        elif ftype in ("breakwater",):
            y = shore_offset - rng.uniform(5, 15)
            features.append({
                "type": ftype,
                "position": (x, y, -0.5),
                "length": rng.uniform(10, 30),
                "height": rng.uniform(0.5, 2.0),
            })
        elif ftype in ("mooring_post",):
            y = shore_offset - rng.uniform(0, 3)
            features.append({
                "type": ftype,
                "position": (x, y, 0.1),
                "height": rng.uniform(0.5, 1.5),
            })
        elif ftype in ("dune_mound",):
            y = shore_offset + rng.uniform(3, half_width * 0.6)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
                "height": rng.uniform(0.5, 2.0),
                "radius": rng.uniform(2, 6),
            })
        elif ftype in ("driftwood",):
            y = shore_offset + rng.uniform(-1, 2)
            features.append({
                "type": ftype,
                "position": (x, y, 0.05),
                "length": rng.uniform(1, 4),
                "angle": rng.uniform(0, 360),
            })
        elif ftype in ("shell_cluster",):
            y = shore_offset + rng.uniform(-1, 1)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
                "count": rng.randint(3, 12),
                "spread": rng.uniform(0.3, 1.5),
            })
        elif ftype in ("crate_stack",):
            y = shore_offset + rng.uniform(0, 3)
            features.append({
                "type": ftype,
                "position": (x, y, 0.2),
                "count": rng.randint(2, 6),
            })
        else:
            # Generic feature
            y = shore_offset + rng.uniform(-2, 2)
            features.append({
                "type": ftype,
                "position": (x, y, 0.0),
            })

    return features


# ---------------------------------------------------------------------------
# Material zone computation
# ---------------------------------------------------------------------------

def _compute_material_zones(
    vertices: list[Vec3],
    resolution_along: int,
    resolution_across: int,
    shoreline_profile: list[float],
    width: float,
    style: str,
) -> list[int]:
    """Assign material zone index to each face.

    Returns a list of material indices, one per face.
    """
    config = COASTLINE_STYLES[style]
    zones = config["material_zones"]
    num_zones = len(zones)
    half_width = width / 2.0

    face_materials: list[int] = []

    for i in range(resolution_along - 1):
        for j in range(resolution_across - 1):
            # Compute face center Y position
            v0 = i * resolution_across + j
            v3 = (i + 1) * resolution_across + j
            y_avg = (vertices[v0][1] + vertices[v3][1]) / 2.0
            z_avg = (vertices[v0][2] + vertices[v3][2]) / 2.0

            t_along = i / max(resolution_along - 1, 1)
            idx = min(int(t_along * len(shoreline_profile)), len(shoreline_profile) - 1)
            shore_y = shoreline_profile[idx]

            # Distance from shoreline
            dist_from_shore = y_avg - shore_y

            if dist_from_shore < -1.0:
                # Water side
                mat_idx = num_zones - 1  # water_edge
            elif dist_from_shore < 1.0:
                # Transition zone
                mat_idx = max(0, num_zones - 2)
            elif dist_from_shore < half_width * 0.5:
                # Mid-ground
                mat_idx = min(1, num_zones - 1)
            else:
                # Inland
                mat_idx = 0

            face_materials.append(mat_idx)

    return face_materials


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def generate_coastline(
    length: float = 200.0,
    width: float = 50.0,
    style: str = "rocky",
    resolution: int = 64,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate coastline terrain and features.

    Parameters
    ----------
    length : float
        Length of the coastline strip along X axis.
    width : float
        Width of the terrain strip (water to land).
    style : str
        One of "rocky", "sandy", "cliffs", "harbor".
    resolution : int
        Mesh resolution along the coastline. Across resolution is
        derived as resolution // 2.
    seed : int
        Random seed for deterministic generation.

    Returns
    -------
    dict with:
        - "mesh": dict with vertices, faces, resolution info
        - "features": list of feature placement dicts
        - "material_zones": list of material indices per face
        - "material_names": list of zone material names
        - "shoreline_profile": list of shoreline offset values
        - "style": str
        - "length": float
        - "width": float

    Raises
    ------
    ValueError
        If style is not a known coastline style.
    """
    if style not in COASTLINE_STYLES:
        raise ValueError(
            f"Unknown coastline style '{style}'. "
            f"Valid styles: {sorted(COASTLINE_STYLES.keys())}"
        )

    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")
    if resolution < 4:
        raise ValueError(f"resolution must be >= 4, got {resolution}")

    resolution_along = resolution
    resolution_across = max(4, resolution // 2)

    # Generate shoreline profile
    shoreline_profile = _generate_shoreline_profile(
        length, style, resolution_along, seed
    )

    # Generate terrain mesh
    mesh = _generate_coastline_mesh(
        length=length,
        width=width,
        style=style,
        resolution_along=resolution_along,
        resolution_across=resolution_across,
        shoreline_profile=shoreline_profile,
        seed=seed,
    )

    # Place features
    features = _place_features(
        length=length,
        width=width,
        style=style,
        shoreline_profile=shoreline_profile,
        resolution_along=resolution_along,
        seed=seed,
    )

    # Compute material zones
    material_zones = _compute_material_zones(
        vertices=mesh["vertices"],
        resolution_along=resolution_along,
        resolution_across=resolution_across,
        shoreline_profile=shoreline_profile,
        width=width,
        style=style,
    )

    config = COASTLINE_STYLES[style]

    return {
        "mesh": mesh,
        "features": features,
        "material_zones": material_zones,
        "material_names": config["material_zones"],
        "shoreline_profile": shoreline_profile,
        "style": style,
        "length": length,
        "width": width,
        "vertex_count": len(mesh["vertices"]),
        "face_count": len(mesh["faces"]),
        "feature_count": len(features),
    }
