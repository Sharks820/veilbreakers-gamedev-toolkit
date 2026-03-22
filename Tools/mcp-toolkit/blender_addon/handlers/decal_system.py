"""Pure-logic decal placement system for environmental storytelling.

NO bpy/bmesh imports. Fully testable without Blender.

Generates flat quad meshes for decal projection (blood splatters, cracks,
moss, scorch marks, runes, etc.) and computes placement positions on
surfaces with proper UV mapping.

Provides:
  - DECAL_TYPES: 10 decal type definitions with size, material, and rendering hints
  - generate_decal_mesh: Create a flat quad mesh spec for decal projection
  - compute_decal_placements: Scatter decals on surfaces with collision avoidance
  - project_decal_to_surface: Compute decal transform for a target surface normal
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Decal Type Definitions -- 10 types
# ---------------------------------------------------------------------------

DECAL_TYPES: dict[str, dict[str, Any]] = {
    "blood_splatter": {
        "size_range": (0.3, 1.5),
        "alpha": True,
        "material": "blood_decal",
        "color": (0.4, 0.02, 0.02, 0.9),
        "roughness": 0.6,
        "category": "violence",
    },
    "water_stain": {
        "size_range": (0.5, 2.0),
        "alpha": True,
        "material": "water_stain_decal",
        "color": (0.3, 0.35, 0.4, 0.5),
        "roughness": 0.3,
        "category": "environmental",
    },
    "crack": {
        "size_range": (0.2, 1.0),
        "alpha": True,
        "normal_only": True,
        "material": "crack_decal",
        "color": (0.15, 0.13, 0.1, 1.0),
        "roughness": 0.9,
        "category": "structural",
    },
    "moss_patch": {
        "size_range": (0.3, 1.5),
        "alpha": True,
        "material": "moss_decal",
        "color": (0.15, 0.3, 0.1, 0.85),
        "roughness": 0.8,
        "category": "environmental",
    },
    "dirt_accumulation": {
        "size_range": (0.5, 3.0),
        "alpha": True,
        "vertex_color": True,
        "material": "dirt_decal",
        "color": (0.25, 0.2, 0.12, 0.7),
        "roughness": 0.9,
        "category": "environmental",
    },
    "footprint_trail": {
        "size_range": (0.25, 0.35),
        "alpha": True,
        "material": "footprint_decal",
        "color": (0.2, 0.18, 0.12, 0.6),
        "roughness": 0.85,
        "category": "narrative",
    },
    "scorch_mark": {
        "size_range": (0.5, 2.0),
        "alpha": True,
        "material": "scorch_decal",
        "color": (0.05, 0.03, 0.02, 0.9),
        "roughness": 0.4,
        "category": "violence",
    },
    "rune_marking": {
        "size_range": (0.3, 0.8),
        "alpha": True,
        "emission": True,
        "material": "rune_decal",
        "color": (0.6, 0.1, 0.8, 0.95),
        "roughness": 0.3,
        "emission_strength": 2.0,
        "category": "magical",
    },
    "rust_streak": {
        "size_range": (0.2, 1.2),
        "alpha": True,
        "material": "rust_decal",
        "color": (0.45, 0.2, 0.05, 0.75),
        "roughness": 0.85,
        "category": "environmental",
    },
    "oil_spill": {
        "size_range": (0.4, 1.8),
        "alpha": True,
        "material": "oil_decal",
        "color": (0.08, 0.06, 0.05, 0.8),
        "roughness": 0.15,
        "category": "environmental",
    },
}


# ---------------------------------------------------------------------------
# Decal Mesh Generation
# ---------------------------------------------------------------------------

def generate_decal_mesh(
    decal_type: str,
    size: float = 1.0,
    subdivisions: int = 0,
) -> dict[str, Any]:
    """Generate a flat quad mesh for decal projection.

    Parameters
    ----------
    decal_type : str
        One of the DECAL_TYPES keys.
    size : float
        Scale factor applied to the decal.
    subdivisions : int
        Number of subdivisions (0 = single quad, 1 = 4 quads, etc.).

    Returns
    -------
    dict with:
        "vertices": list of (x, y, z) tuples
        "faces": list of vertex index tuples (quads or tris)
        "uvs": list of (u, v) tuples per vertex
        "decal_type": str
        "material": str
        "properties": dict of rendering hints (alpha, emission, etc.)
    """
    if decal_type not in DECAL_TYPES:
        raise ValueError(
            f"Unknown decal type '{decal_type}'. "
            f"Valid types: {sorted(DECAL_TYPES.keys())}"
        )

    config = DECAL_TYPES[decal_type]
    half = size / 2.0

    if subdivisions <= 0:
        # Simple quad
        vertices = [
            (-half, -half, 0.0),
            (half, -half, 0.0),
            (half, half, 0.0),
            (-half, half, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        uvs = [
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
        ]
    else:
        vertices, faces, uvs = _subdivided_quad(half, subdivisions)

    properties: dict[str, Any] = {
        "alpha": config.get("alpha", False),
        "normal_only": config.get("normal_only", False),
        "vertex_color": config.get("vertex_color", False),
        "emission": config.get("emission", False),
        "color": config.get("color", (1, 1, 1, 1)),
        "roughness": config.get("roughness", 0.5),
    }
    if config.get("emission"):
        properties["emission_strength"] = config.get("emission_strength", 1.0)

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs,
        "decal_type": decal_type,
        "material": config["material"],
        "properties": properties,
    }


def _subdivided_quad(
    half: float,
    subdivisions: int,
) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Generate a subdivided quad with proper UV mapping."""
    n = 2 ** subdivisions + 1  # vertices per edge
    step = (2.0 * half) / (n - 1)
    uv_step = 1.0 / (n - 1)

    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []

    for j in range(n):
        for i in range(n):
            x = -half + i * step
            y = -half + j * step
            vertices.append((x, y, 0.0))
            uvs.append((i * uv_step, j * uv_step))

    faces: list[tuple[int, ...]] = []
    for j in range(n - 1):
        for i in range(n - 1):
            v0 = j * n + i
            v1 = v0 + 1
            v2 = v1 + n
            v3 = v0 + n
            faces.append((v0, v1, v2, v3))

    return vertices, faces, uvs


# ---------------------------------------------------------------------------
# Decal Placement Engine
# ---------------------------------------------------------------------------

def compute_decal_placements(
    surface_bounds: tuple,
    decal_types: list[str],
    density: float = 0.1,
    seed: int = 42,
    exclude_regions: list[dict[str, Any]] | None = None,
    surface_normal: tuple[float, float, float] = (0, 0, 1),
) -> list[dict[str, Any]]:
    """Scatter decals on a surface with collision avoidance.

    Parameters
    ----------
    surface_bounds : tuple
        ((min_x, min_y), (max_x, max_y)) defining the 2D surface area.
    decal_types : list of str
        Which decal types to scatter (from DECAL_TYPES keys).
    density : float
        Decals per square meter (approximate).
    seed : int
        Random seed.
    exclude_regions : list of dict, optional
        Regions to avoid. Each dict has "center" (x, y) and "radius" (float).
    surface_normal : tuple
        Normal direction of the target surface for orientation.

    Returns
    -------
    list of dict
        Each dict has: "decal_type", "position" (x, y), "rotation" (degrees),
        "size" (float), "surface_normal" (tuple).
    """
    if exclude_regions is None:
        exclude_regions = []

    # Validate decal types
    valid_types = []
    for dt in decal_types:
        if dt in DECAL_TYPES:
            valid_types.append(dt)
    if not valid_types:
        raise ValueError(
            f"No valid decal types provided. "
            f"Valid types: {sorted(DECAL_TYPES.keys())}"
        )

    rng = random.Random(seed)
    (min_x, min_y), (max_x, max_y) = surface_bounds
    area_w = max(max_x - min_x, 0.01)
    area_h = max(max_y - min_y, 0.01)
    total_area = area_w * area_h

    target_count = max(1, int(density * total_area + 0.5))

    placements: list[dict[str, Any]] = []
    placed_positions: list[tuple[float, float, float]] = []  # (x, y, radius)

    max_attempts = target_count * 5  # avoid infinite loops
    attempts = 0

    while len(placements) < target_count and attempts < max_attempts:
        attempts += 1

        # Pick a random decal type
        decal_type = rng.choice(valid_types)
        config = DECAL_TYPES[decal_type]
        size_min, size_max = config["size_range"]
        size = rng.uniform(size_min, size_max)

        # Random position
        x = rng.uniform(min_x, max_x)
        y = rng.uniform(min_y, max_y)

        # Check exclusion zones
        excluded = False
        for region in exclude_regions:
            cx, cy = region["center"]
            r = region["radius"]
            if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                excluded = True
                break
        if excluded:
            continue

        # Overlap check with already placed decals
        half_size = size / 2.0
        overlapping = False
        for px, py, pr in placed_positions:
            dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            if dist < (half_size + pr) * 0.7:  # allow slight overlap for realism
                overlapping = True
                break
        if overlapping:
            continue

        rotation = rng.uniform(0, 360)

        placements.append({
            "decal_type": decal_type,
            "position": (x, y),
            "rotation": rotation,
            "size": size,
            "surface_normal": surface_normal,
        })
        placed_positions.append((x, y, half_size))

    return placements


def project_decal_to_surface(
    decal_position: tuple[float, float],
    surface_normal: tuple[float, float, float],
    surface_point: tuple[float, float, float],
    decal_size: float,
    offset: float = 0.001,
) -> dict[str, Any]:
    """Compute the full 3D transform for projecting a decal onto a surface.

    Parameters
    ----------
    decal_position : tuple
        2D position (u, v) on the surface parameterization.
    surface_normal : tuple
        Normal vector of the target surface.
    surface_point : tuple
        3D world position of the surface at decal_position.
    decal_size : float
        Size of the decal quad.
    offset : float
        Small offset along normal to prevent z-fighting.

    Returns
    -------
    dict with:
        "position": (x, y, z) world position (offset from surface)
        "normal": (nx, ny, nz) surface normal
        "scale": (sx, sy, sz) scale factor
        "tangent": (tx, ty, tz) tangent vector for orientation
        "bitangent": (bx, by, bz) bitangent vector
    """
    nx, ny, nz = surface_normal
    n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
    if n_len < 1e-8:
        nx, ny, nz = 0, 0, 1
        n_len = 1.0
    nx /= n_len
    ny /= n_len
    nz /= n_len

    # Offset position along normal
    pos = (
        surface_point[0] + nx * offset,
        surface_point[1] + ny * offset,
        surface_point[2] + nz * offset,
    )

    # Compute tangent and bitangent
    # Choose an up vector that isn't parallel to the normal
    if abs(nz) < 0.9:
        up = (0, 0, 1)
    else:
        up = (0, 1, 0)

    # tangent = normalize(up x normal)
    tx = up[1] * nz - up[2] * ny
    ty = up[2] * nx - up[0] * nz
    tz = up[0] * ny - up[1] * nx
    t_len = math.sqrt(tx * tx + ty * ty + tz * tz)
    if t_len < 1e-8:
        tx, ty, tz = 1, 0, 0
    else:
        tx /= t_len
        ty /= t_len
        tz /= t_len

    # bitangent = normal x tangent
    bx = ny * tz - nz * ty
    by = nz * tx - nx * tz
    bz = nx * ty - ny * tx

    return {
        "position": pos,
        "normal": (nx, ny, nz),
        "scale": (decal_size, decal_size, 1.0),
        "tangent": (tx, ty, tz),
        "bitangent": (bx, by, bz),
    }


def get_decal_categories() -> dict[str, list[str]]:
    """Group decal types by category."""
    categories: dict[str, list[str]] = {}
    for name, config in DECAL_TYPES.items():
        cat = config.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)
    return categories


def get_available_decal_types() -> list[str]:
    """Return sorted list of all supported decal types."""
    return sorted(DECAL_TYPES.keys())
