"""Destruction state system for VeilBreakers mesh assets.

Applies procedural damage to mesh geometry across four damage levels:
pristine, worn, damaged, and destroyed. All functions are pure Python/math
-- no ``bpy`` dependency -- for testability.

Provides:
  - DAMAGE_LEVELS: damage state definitions with vertex displacement,
    face removal, and rubble parameters
  - apply_destruction(): Apply structural damage to a mesh
  - generate_rubble_pile(): Generate angular debris chunks around a center
  - get_damage_level(): Retrieve a damage level definition by name
  - interpolate_damage_levels(): Blend between two damage levels
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Mesh result type
# ---------------------------------------------------------------------------
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# Damage level definitions
# ---------------------------------------------------------------------------

DAMAGE_LEVELS: dict[str, dict[str, Any]] = {
    "pristine": {
        "vertex_displacement": 0.0,
        "missing_faces_pct": 0.0,
        "rubble": False,
    },
    "worn": {
        "vertex_displacement": 0.005,
        "missing_faces_pct": 0.0,
        "rubble": False,
    },
    "damaged": {
        "vertex_displacement": 0.02,
        "missing_faces_pct": 0.1,
        "rubble": True,
        "rubble_amount": 0.3,
    },
    "destroyed": {
        "vertex_displacement": 0.05,
        "missing_faces_pct": 0.4,
        "rubble": True,
        "rubble_amount": 1.0,
    },
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _compute_dimensions(
    verts: list[tuple[float, float, float]],
) -> dict[str, float]:
    if not verts:
        return {"width": 0.0, "height": 0.0, "depth": 0.0}
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "depth": max(zs) - min(zs),
    }


def _noise_3d(x: float, y: float, z: float, seed: int) -> float:
    """Simple deterministic pseudo-noise for vertex displacement."""
    # Hash-based noise: consistent output for same inputs
    h = seed
    h ^= int(x * 73856093) & 0xFFFFFFFF
    h ^= int(y * 19349663) & 0xFFFFFFFF
    h ^= int(z * 83492791) & 0xFFFFFFFF
    h = ((h * 2654435761) & 0xFFFFFFFF)
    return (h / 0xFFFFFFFF) * 2.0 - 1.0  # range [-1, 1]


def _compute_vertex_normal_approx(
    vertex_index: int,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
) -> tuple[float, float, float]:
    """Approximate vertex normal by averaging adjacent face normals."""
    nx, ny, nz = 0.0, 0.0, 0.0
    count = 0
    for face in faces:
        if vertex_index in face:
            # Compute face normal from first 3 vertices
            if len(face) >= 3:
                v0 = vertices[face[0]]
                v1 = vertices[face[1]]
                v2 = vertices[face[2]]
                e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
                e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
                fn = (
                    e1[1] * e2[2] - e1[2] * e2[1],
                    e1[2] * e2[0] - e1[0] * e2[2],
                    e1[0] * e2[1] - e1[1] * e2[0],
                )
                nx += fn[0]
                ny += fn[1]
                nz += fn[2]
                count += 1
    if count == 0:
        return (0.0, 1.0, 0.0)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-9:
        return (0.0, 1.0, 0.0)
    return (nx / length, ny / length, nz / length)


# ---------------------------------------------------------------------------
# Core destruction functions
# ---------------------------------------------------------------------------

def get_damage_level(level: str) -> dict[str, Any]:
    """Retrieve a damage level definition by name.

    Args:
        level: One of 'pristine', 'worn', 'damaged', 'destroyed'.

    Returns:
        Copy of the damage level parameter dict.

    Raises:
        ValueError: If the level name is unknown.
    """
    if level not in DAMAGE_LEVELS:
        raise ValueError(
            f"Unknown damage level '{level}'. "
            f"Valid levels: {list(DAMAGE_LEVELS.keys())}"
        )
    return dict(DAMAGE_LEVELS[level])


def interpolate_damage_levels(
    level_a: str,
    level_b: str,
    t: float,
) -> dict[str, Any]:
    """Interpolate between two damage levels.

    Args:
        level_a: Starting damage level name.
        level_b: Ending damage level name.
        t: Interpolation factor in [0, 1]. 0 = level_a, 1 = level_b.

    Returns:
        Interpolated damage parameter dict.
    """
    a = get_damage_level(level_a)
    b = get_damage_level(level_b)
    t = max(0.0, min(1.0, t))

    result: dict[str, Any] = {
        "vertex_displacement": a["vertex_displacement"] * (1 - t) + b["vertex_displacement"] * t,
        "missing_faces_pct": a["missing_faces_pct"] * (1 - t) + b["missing_faces_pct"] * t,
    }

    # Rubble: active if either level has rubble and t > 0 from rubble side
    a_rubble = a.get("rubble", False)
    b_rubble = b.get("rubble", False)
    if a_rubble or b_rubble:
        a_amount = a.get("rubble_amount", 0.0) if a_rubble else 0.0
        b_amount = b.get("rubble_amount", 0.0) if b_rubble else 0.0
        interp_amount = a_amount * (1 - t) + b_amount * t
        result["rubble"] = interp_amount > 0.0
        result["rubble_amount"] = interp_amount
    else:
        result["rubble"] = False

    return result


def apply_destruction(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    level: str = "damaged",
    seed: int = 42,
) -> dict[str, Any]:
    """Apply destruction to mesh geometry.

    Displaces vertices with noise (simulates structural damage), removes
    random faces (creates holes in walls/roofs), and optionally generates
    a rubble pile mesh at the base.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.
        level: Damage level name ('pristine', 'worn', 'damaged', 'destroyed').
        seed: Random seed for reproducible destruction.

    Returns:
        Dict with keys:
        - 'damaged_vertices': displaced vertex list
        - 'damaged_faces': remaining face list (some removed)
        - 'rubble_mesh': rubble MeshSpec dict or None
        - 'metadata': destruction statistics
    """
    params = get_damage_level(level)
    rng = random.Random(seed)

    displacement = params["vertex_displacement"]
    missing_pct = params["missing_faces_pct"]
    has_rubble = params.get("rubble", False)
    rubble_amount = params.get("rubble_amount", 0.0)

    # --- Vertex displacement ---
    damaged_vertices: list[tuple[float, float, float]] = []
    for i, (vx, vy, vz) in enumerate(vertices):
        if displacement > 0.0:
            noise_val = _noise_3d(vx, vy, vz, seed)
            # Bias displacement downward slightly (gravity effect)
            # and outward along approximate normal
            normal = _compute_vertex_normal_approx(i, vertices, faces)
            disp_scale = displacement * noise_val
            # Add some vertical sag for realism
            gravity_factor = 0.3 * displacement * abs(noise_val)
            new_v = (
                vx + normal[0] * disp_scale,
                vy + normal[1] * disp_scale - gravity_factor,
                vz + normal[2] * disp_scale,
            )
            damaged_vertices.append(new_v)
        else:
            damaged_vertices.append((vx, vy, vz))

    # --- Face removal (holes in structure) ---
    damaged_faces: list[tuple[int, ...]] = []
    removed_faces: list[tuple[int, ...]] = []
    if missing_pct > 0.0 and faces:
        # Preferentially remove upper faces (roofs/tops collapse first)
        face_heights: list[tuple[float, int]] = []
        for fi, face in enumerate(faces):
            avg_y = sum(vertices[vi][1] for vi in face) / len(face)
            face_heights.append((avg_y, fi))
        face_heights.sort(reverse=True)  # highest first

        num_to_remove = max(1, int(len(faces) * missing_pct))
        # Weighted random: higher faces more likely to be removed
        remove_indices: set[int] = set()
        candidate_pool = list(range(len(faces)))
        rng.shuffle(candidate_pool)

        # Weight toward upper faces: first half of candidates from top,
        # second half random
        top_half = [fi for _, fi in face_heights[:len(faces) // 2]]
        weighted_pool = top_half + candidate_pool
        rng.shuffle(weighted_pool)

        for fi in weighted_pool:
            if len(remove_indices) >= num_to_remove:
                break
            remove_indices.add(fi)

        for fi, face in enumerate(faces):
            if fi in remove_indices:
                removed_faces.append(face)
            else:
                damaged_faces.append(face)
    else:
        damaged_faces = list(faces)

    # --- Rubble generation ---
    rubble_mesh = None
    if has_rubble and rubble_amount > 0.0 and vertices:
        # Compute mesh center at ground level
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        zs = [v[2] for v in vertices]
        center = (
            (min(xs) + max(xs)) / 2.0,
            min(ys),  # ground level
            (min(zs) + max(zs)) / 2.0,
        )
        # Rubble radius proportional to mesh size
        mesh_radius = max(max(xs) - min(xs), max(zs) - min(zs)) / 2.0
        rubble_mesh = generate_rubble_pile(
            center=center,
            radius=mesh_radius * 0.5,
            amount=rubble_amount,
            seed=seed,
        )

    return {
        "damaged_vertices": damaged_vertices,
        "damaged_faces": damaged_faces,
        "rubble_mesh": rubble_mesh,
        "metadata": {
            "level": level,
            "vertices_displaced": sum(
                1 for i in range(len(vertices))
                if vertices[i] != damaged_vertices[i]
            ) if displacement > 0 else 0,
            "faces_removed": len(removed_faces),
            "faces_remaining": len(damaged_faces),
            "total_faces_original": len(faces),
            "rubble_generated": rubble_mesh is not None,
            "seed": seed,
        },
    }


def generate_rubble_pile(
    center: tuple[float, float, float],
    radius: float,
    amount: float,
    seed: int = 42,
) -> MeshSpec:
    """Generate a pile of angular debris chunks.

    Creates a collection of irregular polyhedra scattered around the center
    point, simulating structural debris.

    Args:
        center: (x, y, z) center of the rubble pile.
        radius: Spread radius for debris placement.
        amount: Rubble density factor in [0, 1]. 1.0 = maximum debris.
        seed: Random seed for reproducible generation.

    Returns:
        MeshSpec dict with vertices, faces, uvs, and metadata.
    """
    rng = random.Random(seed)
    amount = max(0.0, min(1.0, amount))

    # Number of chunks scales with amount
    num_chunks = max(1, int(5 + amount * 20))
    chunk_size_base = radius * 0.08

    all_vertices: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []

    for _ in range(num_chunks):
        # Random position within radius, on ground plane
        angle = rng.uniform(0, math.tau)
        dist = rng.uniform(0, radius) * math.sqrt(rng.random())
        cx = center[0] + math.cos(angle) * dist
        cy = center[1]  # on ground
        cz = center[2] + math.sin(angle) * dist

        # Chunk size with variation
        size = chunk_size_base * rng.uniform(0.3, 1.5)

        # Generate irregular tetrahedron-like chunk (4-6 vertices)
        offset = len(all_vertices)
        chunk_verts: list[tuple[float, float, float]] = []
        num_verts = rng.randint(4, 6)
        for _ in range(num_verts):
            dx = rng.uniform(-size, size)
            dy = rng.uniform(0, size * 0.7)  # mostly above ground
            dz = rng.uniform(-size, size)
            chunk_verts.append((cx + dx, cy + dy, cz + dz))
        all_vertices.extend(chunk_verts)

        # Simple face generation: connect as triangle fan from first vert
        if num_verts >= 3:
            for i in range(1, num_verts - 1):
                all_faces.append((
                    offset,
                    offset + i,
                    offset + i + 1,
                ))
            # Close bottom
            if num_verts >= 4:
                all_faces.append((
                    offset + 1,
                    offset + num_verts - 1,
                    offset + num_verts - 2,
                ))

    dims = _compute_dimensions(all_vertices)
    return {
        "vertices": all_vertices,
        "faces": all_faces,
        "uvs": [],
        "metadata": {
            "name": "rubble_pile",
            "poly_count": len(all_faces),
            "vertex_count": len(all_vertices),
            "dimensions": dims,
            "chunk_count": num_chunks,
            "radius": radius,
            "amount": amount,
            "seed": seed,
        },
    }
