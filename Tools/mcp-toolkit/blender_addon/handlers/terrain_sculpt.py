"""Terrain sculpting handler for precise vertex-level terrain editing (GAP-09).

Provides:
- handle_sculpt_terrain: Sculpt terrain mesh at specific world coordinates.
- Pure-logic brush/falloff math (testable without Blender).

Operations:
  raise   -- displace vertices upward within radius with falloff
  lower   -- displace vertices downward
  smooth  -- average vertex heights within radius (Laplacian smooth on Z)
  flatten -- set vertices to average height within radius
  stamp   -- apply a heightmap pattern at position

All brush math is in pure functions for testability.
"""

from __future__ import annotations

import math

import bmesh
import bpy


# ---------------------------------------------------------------------------
# Pure-logic brush helpers (testable without Blender)
# ---------------------------------------------------------------------------

# Falloff functions: distance [0..1] -> strength [0..1]
_FALLOFF_FUNCTIONS = {
    "smooth": lambda d: 0.5 * (1.0 + math.cos(math.pi * d)) if d < 1.0 else 0.0,
    "sharp": lambda d: max(0.0, 1.0 - d * d) if d < 1.0 else 0.0,
    "linear": lambda d: max(0.0, 1.0 - d) if d < 1.0 else 0.0,
    "constant": lambda d: 1.0 if d < 1.0 else 0.0,
}


def get_falloff_value(distance_normalized: float, falloff: str = "smooth") -> float:
    """Compute falloff strength for a normalized distance [0..1].

    Args:
        distance_normalized: Distance from brush center divided by radius (0=center, 1=edge).
        falloff: One of "smooth", "sharp", "linear", "constant".

    Returns:
        Falloff strength in [0..1].
    """
    fn = _FALLOFF_FUNCTIONS.get(falloff)
    if fn is None:
        raise ValueError(
            f"Unknown falloff: {falloff!r}. Valid: {sorted(_FALLOFF_FUNCTIONS)}"
        )
    return fn(min(max(distance_normalized, 0.0), 1.5))


def compute_brush_weights(
    vert_positions_2d: list[tuple[float, float]],
    brush_center: tuple[float, float],
    brush_radius: float,
    falloff: str = "smooth",
) -> list[tuple[int, float]]:
    """Compute per-vertex brush weights for terrain sculpting.

    Only considers XY distance (terrain is sculpted vertically).

    Args:
        vert_positions_2d: List of (x, y) positions for each vertex.
        brush_center: (bx, by) center of the brush in world XY.
        brush_radius: Brush radius.
        falloff: Falloff curve name.

    Returns:
        List of (vertex_index, weight) tuples for affected vertices.
        Only vertices within the radius are included.
    """
    if brush_radius <= 0:
        return []

    result: list[tuple[int, float]] = []
    bx, by = brush_center
    r_sq = brush_radius * brush_radius

    for i, (vx, vy) in enumerate(vert_positions_2d):
        dx = vx - bx
        dy = vy - by
        dist_sq = dx * dx + dy * dy
        if dist_sq <= r_sq:
            dist = math.sqrt(dist_sq)
            norm_dist = dist / brush_radius
            weight = get_falloff_value(norm_dist, falloff)
            if weight > 0:
                result.append((i, weight))

    return result


def compute_raise_displacements(
    vert_heights: list[float],
    weights: list[tuple[int, float]],
    strength: float,
) -> dict[int, float]:
    """Compute Z displacements for 'raise' operation.

    Args:
        vert_heights: Current Z values for all vertices.
        weights: (index, weight) tuples from compute_brush_weights.
        strength: Displacement amount.

    Returns:
        Dict mapping vertex index -> new Z value.
    """
    result: dict[int, float] = {}
    for idx, w in weights:
        result[idx] = vert_heights[idx] + strength * w
    return result


def compute_lower_displacements(
    vert_heights: list[float],
    weights: list[tuple[int, float]],
    strength: float,
) -> dict[int, float]:
    """Compute Z displacements for 'lower' operation."""
    result: dict[int, float] = {}
    for idx, w in weights:
        result[idx] = vert_heights[idx] - strength * w
    return result


def compute_smooth_displacements(
    vert_positions: list[tuple[float, float, float]],
    adjacency: dict[int, list[int]],
    weights: list[tuple[int, float]],
) -> dict[int, float]:
    """Compute Z displacements for 'smooth' operation (Laplacian smooth on Z).

    Args:
        vert_positions: Full (x, y, z) positions for all vertices.
        adjacency: Dict mapping vertex index to list of neighbor vertex indices.
        weights: (index, weight) tuples from compute_brush_weights.

    Returns:
        Dict mapping vertex index -> new Z value.
    """
    result: dict[int, float] = {}
    affected = {idx for idx, _ in weights}
    weight_map = dict(weights)

    for idx in affected:
        neighbors = adjacency.get(idx, [])
        if not neighbors:
            continue
        avg_z = sum(vert_positions[n][2] for n in neighbors) / len(neighbors)
        current_z = vert_positions[idx][2]
        w = weight_map[idx]
        result[idx] = current_z + (avg_z - current_z) * w
    return result


def compute_flatten_displacements(
    vert_heights: list[float],
    weights: list[tuple[int, float]],
) -> dict[int, float]:
    """Compute Z displacements for 'flatten' operation.

    Sets all affected vertices to the average height within the brush.
    """
    if not weights:
        return {}

    indices = [idx for idx, _ in weights]
    avg_height = sum(vert_heights[idx] for idx in indices) / len(indices)

    result: dict[int, float] = {}
    for idx, w in weights:
        current = vert_heights[idx]
        result[idx] = current + (avg_height - current) * w
    return result


def compute_stamp_displacements(
    vert_positions_2d: list[tuple[float, float]],
    vert_heights: list[float],
    weights: list[tuple[int, float]],
    brush_center: tuple[float, float],
    brush_radius: float,
    heightmap: list[list[float]],
    stamp_strength: float = 1.0,
) -> dict[int, float]:
    """Compute Z displacements for 'stamp' operation.

    Samples a 2D heightmap grid and applies it to the terrain.

    Args:
        vert_positions_2d: (x, y) for each vertex.
        vert_heights: Current Z values.
        weights: Brush weights.
        brush_center: Center of the stamp.
        brush_radius: Radius of the stamp area.
        heightmap: 2D grid of height values [row][col], normalized [0..1].
        stamp_strength: Scale factor for the heightmap values.

    Returns:
        Dict mapping vertex index -> new Z value.
    """
    if not weights or not heightmap:
        return {}

    rows = len(heightmap)
    cols = len(heightmap[0]) if rows > 0 else 0
    if rows == 0 or cols == 0:
        return {}

    bx, by = brush_center
    result: dict[int, float] = {}

    for idx, w in weights:
        vx, vy = vert_positions_2d[idx]
        # Map vertex position to heightmap UV [0..1]
        u = (vx - bx + brush_radius) / (2 * brush_radius)
        v = (vy - by + brush_radius) / (2 * brush_radius)
        u = max(0.0, min(u, 1.0))
        v = max(0.0, min(v, 1.0))

        # Sample heightmap (nearest neighbor)
        col = min(int(u * (cols - 1) + 0.5), cols - 1)
        row = min(int(v * (rows - 1) + 0.5), rows - 1)
        h_val = heightmap[row][col]

        result[idx] = vert_heights[idx] + h_val * stamp_strength * w

    return result


# ---------------------------------------------------------------------------
# Blender handler (requires bpy + bmesh at runtime)
# ---------------------------------------------------------------------------


def _build_adjacency(bm_obj) -> dict[int, list[int]]:
    """Build vertex adjacency map from a bmesh object."""
    adj: dict[int, list[int]] = {}
    for v in bm_obj.verts:
        adj[v.index] = [e.other_vert(v).index for e in v.link_edges]
    return adj


def handle_sculpt_terrain(params: dict) -> dict:
    """Sculpt terrain at specific coordinates (GAP-09).

    Params:
        terrain_name: str -- Name of the terrain mesh object.
        position: [x, y] -- Center of brush in world XY.
        radius: float -- Brush radius.
        strength: float -- Displacement amount.
        operation: str -- "raise" | "lower" | "smooth" | "flatten" | "stamp".
        falloff: str -- "smooth" | "sharp" | "linear" | "constant" (default "smooth").
        heightmap: list[list[float]] -- 2D height grid for stamp operation.

    Returns dict with operation details and affected vertex count.
    """
    terrain_name = params.get("terrain_name")
    obj = bpy.data.objects.get(terrain_name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Terrain mesh object not found: {terrain_name}")

    position = params.get("position", [0, 0])
    radius = params.get("radius", 5.0)
    strength = params.get("strength", 1.0)
    operation = params.get("operation", "raise")
    falloff = params.get("falloff", "smooth")
    heightmap = params.get("heightmap")

    valid_ops = ("raise", "lower", "smooth", "flatten", "stamp")
    if operation not in valid_ops:
        raise ValueError(
            f"Unknown terrain sculpt operation: {operation!r}. Valid: {valid_ops}"
        )

    brush_center = (float(position[0]), float(position[1]))

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        # Extract vertex data
        positions_2d = [(v.co.x, v.co.y) for v in bm.verts]
        positions_3d = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
        heights = [v.co.z for v in bm.verts]

        # Compute brush weights
        weights = compute_brush_weights(positions_2d, brush_center, radius, falloff)

        if not weights:
            return {
                "terrain_name": terrain_name,
                "operation": operation,
                "affected_vertices": 0,
                "detail": "No vertices within brush radius",
            }

        # Compute new heights based on operation
        if operation == "raise":
            new_heights = compute_raise_displacements(heights, weights, strength)
        elif operation == "lower":
            new_heights = compute_lower_displacements(heights, weights, strength)
        elif operation == "smooth":
            adjacency = _build_adjacency(bm)
            new_heights = compute_smooth_displacements(positions_3d, adjacency, weights)
        elif operation == "flatten":
            new_heights = compute_flatten_displacements(heights, weights)
        elif operation == "stamp":
            if not heightmap:
                raise ValueError("heightmap parameter required for stamp operation")
            new_heights = compute_stamp_displacements(
                positions_2d, heights, weights, brush_center, radius, heightmap, strength
            )
        else:
            new_heights = {}

        # Apply displacements
        for idx, new_z in new_heights.items():
            bm.verts[idx].co.z = new_z

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "terrain_name": terrain_name,
        "operation": operation,
        "affected_vertices": len(new_heights),
        "brush_center": list(brush_center),
        "brush_radius": radius,
        "strength": strength,
        "falloff": falloff,
    }
