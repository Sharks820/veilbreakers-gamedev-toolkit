"""Post-processing for assembled primitive geometry.

Eliminates the "assembled primitives" look (visible cylinder+sphere+box
junctions) by applying Laplacian mesh smoothing and subtle organic noise
displacement. Both functions are pure Python -- no bpy/bmesh imports.

Usage:
    from .mesh_smoothing import smooth_assembled_mesh, add_organic_noise

    verts = smooth_assembled_mesh(verts, faces, smooth_iterations=3)
    verts = add_organic_noise(verts, strength=0.003)
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
VertList = list[Vec3]
FaceList = list[tuple[int, ...]]


# ---------------------------------------------------------------------------
# Adjacency helpers
# ---------------------------------------------------------------------------


def _build_adjacency(
    num_verts: int,
    faces: FaceList,
) -> list[set[int]]:
    """Build per-vertex adjacency sets from the face list.

    Two vertices are adjacent if they share an edge in any face.
    """
    adj: list[set[int]] = [set() for _ in range(num_verts)]
    for face in faces:
        n = len(face)
        for i in range(n):
            a = face[i]
            b = face[(i + 1) % n]
            adj[a].add(b)
            adj[b].add(a)
    return adj


# ---------------------------------------------------------------------------
# Laplacian mesh smoothing
# ---------------------------------------------------------------------------


def smooth_assembled_mesh(
    vertices: VertList,
    faces: FaceList,
    smooth_iterations: int = 3,
    blend_factor: float = 0.4,
    preserve_boundary: bool = True,
) -> VertList:
    """Post-process assembled primitive geometry to eliminate hard junctions.

    Uses iterative Laplacian smoothing to blend cylinder-sphere-box junctions
    into organic-looking continuous surfaces.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face tuples (indices into vertices).
        smooth_iterations: Number of smoothing passes (1-10).
        blend_factor: How much each vertex moves toward neighbor average
                      per iteration (0.0 = no change, 1.0 = full average).
                      Values 0.3-0.5 preserve overall shape while smoothing
                      junctions. Default 0.4.
        preserve_boundary: If True, vertices with <= 2 neighbors (tips of
                          horns, tails, fingers) are moved less to preserve
                          extremity shape.

    Returns:
        New list of smoothed vertex positions (same length as input).
    """
    if not vertices or not faces:
        return list(vertices)

    smooth_iterations = max(1, min(smooth_iterations, 10))
    blend_factor = max(0.0, min(blend_factor, 1.0))

    num_verts = len(vertices)
    adj = _build_adjacency(num_verts, faces)

    # Work with mutable lists of [x, y, z]
    current = [[v[0], v[1], v[2]] for v in vertices]

    for _iteration in range(smooth_iterations):
        new_pos = [list(v) for v in current]

        for vi in range(num_verts):
            neighbors = adj[vi]
            num_neighbors = len(neighbors)

            if num_neighbors == 0:
                continue

            # Compute average of neighbor positions
            avg_x = 0.0
            avg_y = 0.0
            avg_z = 0.0
            for ni in neighbors:
                avg_x += current[ni][0]
                avg_y += current[ni][1]
                avg_z += current[ni][2]
            avg_x /= num_neighbors
            avg_y /= num_neighbors
            avg_z /= num_neighbors

            # Determine effective blend: reduce for extremities
            effective_blend = blend_factor
            if preserve_boundary and num_neighbors <= 2:
                # Tips of horns, fingers, tails -- preserve shape
                effective_blend *= 0.15
            elif preserve_boundary and num_neighbors <= 3:
                # Near-boundary vertices -- reduce smoothing
                effective_blend *= 0.4

            # Laplacian blend: move vertex toward neighbor average
            new_pos[vi][0] = current[vi][0] + effective_blend * (avg_x - current[vi][0])
            new_pos[vi][1] = current[vi][1] + effective_blend * (avg_y - current[vi][1])
            new_pos[vi][2] = current[vi][2] + effective_blend * (avg_z - current[vi][2])

        current = new_pos

    return [(v[0], v[1], v[2]) for v in current]


# ---------------------------------------------------------------------------
# Organic noise displacement
# ---------------------------------------------------------------------------


def _hash_float(x: float, y: float, z: float, seed: int) -> float:
    """Deterministic pseudo-random float in [-1, 1] from position + seed.

    Uses a simple hash based on large prime multiplications to avoid
    importing random (keeps the function deterministic and stateless).
    """
    # Quantize to avoid floating-point instability
    ix = int(x * 10000) & 0xFFFFFFFF
    iy = int(y * 10000) & 0xFFFFFFFF
    iz = int(z * 10000) & 0xFFFFFFFF

    h = seed
    h = ((h ^ ix) * 2654435761) & 0xFFFFFFFF
    h = ((h ^ iy) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ iz) * 3266489917) & 0xFFFFFFFF
    h = ((h ^ (h >> 16)) * 2246822519) & 0xFFFFFFFF

    # Map to [-1, 1]
    return (h / 2147483647.0) - 1.0


def _estimate_vertex_normal(
    vi: int,
    vertices: VertList,
    adj: list[set[int]],
) -> tuple[float, float, float]:
    """Estimate a vertex normal from its neighbors (centroid-based).

    Points outward from the local surface by computing the vector from
    the neighbor centroid to the vertex, then normalizing.
    """
    neighbors = adj[vi]
    if not neighbors:
        return (0.0, 1.0, 0.0)  # Default up

    # Centroid of neighbors
    cx, cy, cz = 0.0, 0.0, 0.0
    for ni in neighbors:
        cx += vertices[ni][0]
        cy += vertices[ni][1]
        cz += vertices[ni][2]
    n = len(neighbors)
    cx /= n
    cy /= n
    cz /= n

    # Vector from centroid to vertex (outward direction)
    dx = vertices[vi][0] - cx
    dy = vertices[vi][1] - cy
    dz = vertices[vi][2] - cz

    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-10:
        return (0.0, 1.0, 0.0)

    return (dx / length, dy / length, dz / length)


def add_organic_noise(
    vertices: VertList,
    faces: FaceList | None = None,
    strength: float = 0.005,
    seed: int = 42,
) -> VertList:
    """Add subtle per-vertex noise displacement for organic imperfection.

    Each vertex gets a small deterministic displacement along its estimated
    normal direction, producing natural-looking surface variation without
    visible repeating patterns.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: Optional face list for normal estimation. If None, displaces
               along a randomized direction instead of surface normal.
        strength: Maximum displacement magnitude in scene units.
                  0.003-0.005 is subtle; 0.01+ is noticeable.
        seed: Random seed for reproducible noise.

    Returns:
        New list of displaced vertex positions.
    """
    if not vertices:
        return list(vertices)

    strength = abs(strength)
    num_verts = len(vertices)

    # Compute mesh center for distance-based strength scaling
    cx, cy, cz = 0.0, 0.0, 0.0
    for v in vertices:
        cx += v[0]
        cy += v[1]
        cz += v[2]
    cx /= num_verts
    cy /= num_verts
    cz /= num_verts

    # Compute max distance from center for normalization
    max_dist = 0.0
    for v in vertices:
        d = math.sqrt(
            (v[0] - cx) ** 2 + (v[1] - cy) ** 2 + (v[2] - cz) ** 2
        )
        if d > max_dist:
            max_dist = d

    if max_dist < 1e-10:
        max_dist = 1.0

    # Build adjacency if faces provided (for normal estimation)
    adj: list[set[int]] | None = None
    if faces:
        adj = _build_adjacency(num_verts, faces)

    result: VertList = []
    for vi in range(num_verts):
        vx, vy, vz = vertices[vi]

        # Per-vertex noise value (3 channels for x/y/z variation)
        n1 = _hash_float(vx, vy, vz, seed)
        n2 = _hash_float(vx, vy, vz, seed + 7919)
        n3 = _hash_float(vx, vy, vz, seed + 15731)

        # Distance-based strength scaling: extremities get slightly more
        dist = math.sqrt(
            (vx - cx) ** 2 + (vy - cy) ** 2 + (vz - cz) ** 2
        )
        dist_factor = 0.7 + 0.3 * (dist / max_dist)

        effective_strength = strength * dist_factor

        if adj is not None:
            # Displace along estimated surface normal
            nx, ny, nz = _estimate_vertex_normal(vi, vertices, adj)
            # Use primary noise channel for magnitude, add tangential scatter
            mag = n1 * effective_strength
            # Small tangential component for variety
            tang = effective_strength * 0.3
            new_x = vx + nx * mag + n2 * tang * (1.0 - abs(nx))
            new_y = vy + ny * mag + n3 * tang * (1.0 - abs(ny))
            new_z = vz + nz * mag + n1 * tang * (1.0 - abs(nz)) * 0.5
        else:
            # No faces: displace in randomized direction
            new_x = vx + n1 * effective_strength
            new_y = vy + n2 * effective_strength
            new_z = vz + n3 * effective_strength

        result.append((new_x, new_y, new_z))

    return result
