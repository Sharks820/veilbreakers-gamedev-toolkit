"""Live vertex color painting at world/UV/index coordinates.

Provides targeted vertex color painting with brush falloff, blend modes,
and multiple paint modes (world-space, UV-space, vertex-index).

Pure-logic helpers (no bpy dependency) are separated for testability:
  - compute_paint_weights: Per-vertex brush weights from distance + falloff
  - blend_colors: RGBA color blending with MIX/ADD/SUBTRACT/MULTIPLY modes

Handler function (requires bpy):
  - handle_vertex_paint: Paint vertex colors on a mesh at specified coords
"""

from __future__ import annotations

import math
from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def compute_paint_weights(
    vertex_positions: list[tuple[float, float, float]],
    brush_center: tuple[float, float, float],
    brush_radius: float,
    falloff_type: str = "SMOOTH",
) -> list[tuple[int, float]]:
    """Compute per-vertex paint weights based on distance from brush center.

    For each vertex within ``brush_radius`` of ``brush_center``, computes a
    weight in [0, 1] using the specified falloff curve.

    Args:
        vertex_positions: List of (x, y, z) vertex positions.
        brush_center: (x, y, z) world-space brush center.
        brush_radius: Brush influence radius.  Must be > 0.
        falloff_type: One of ``'SMOOTH'``, ``'LINEAR'``, ``'SHARP'``,
            ``'CONSTANT'``.

    Returns:
        List of ``(vertex_index, weight)`` for all vertices within the brush
        radius.  Weight is 1.0 at the center and falls off to 0.0 at the
        edge (except for ``CONSTANT`` which is 1.0 throughout).
    """
    if brush_radius <= 0.0:
        return []

    results: list[tuple[int, float]] = []
    cx, cy, cz = brush_center

    for idx, (vx, vy, vz) in enumerate(vertex_positions):
        dx = vx - cx
        dy = vy - cy
        dz = vz - cz
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)

        if dist > brush_radius:
            continue

        t = dist / brush_radius  # 0.0 at center, 1.0 at edge

        weight = _apply_falloff(t, falloff_type)
        results.append((idx, weight))

    return results


def compute_paint_weights_uv(
    uv_coords: list[tuple[float, float]],
    brush_center_uv: tuple[float, float],
    brush_radius_uv: float,
    falloff_type: str = "SMOOTH",
) -> list[tuple[int, float]]:
    """Compute per-vertex paint weights in UV space.

    Same logic as :func:`compute_paint_weights` but operates in 2D UV space.

    Args:
        uv_coords: List of (u, v) coordinates per vertex.
        brush_center_uv: (u, v) brush center in UV space.
        brush_radius_uv: Brush radius in UV units.
        falloff_type: Falloff curve type.

    Returns:
        List of ``(vertex_index, weight)`` for vertices within radius.
    """
    if brush_radius_uv <= 0.0:
        return []

    results: list[tuple[int, float]] = []
    cu, cv = brush_center_uv

    for idx, (vu, vv) in enumerate(uv_coords):
        du = vu - cu
        dv = vv - cv
        dist = math.sqrt(du * du + dv * dv)

        if dist > brush_radius_uv:
            continue

        t = dist / brush_radius_uv
        weight = _apply_falloff(t, falloff_type)
        results.append((idx, weight))

    return results


def blend_colors(
    existing: tuple[float, float, float, float],
    new_color: tuple[float, float, float, float],
    strength: float,
    mode: str = "MIX",
) -> tuple[float, float, float, float]:
    """Blend two RGBA colors with given strength and blend mode.

    All channel values are clamped to [0, 1] after blending.

    Args:
        existing: Current RGBA color (each in [0, 1]).
        new_color: Brush RGBA color (each in [0, 1]).
        strength: Paint opacity in [0, 1].
        mode: Blend mode — ``'MIX'``, ``'ADD'``, ``'SUBTRACT'``, or
            ``'MULTIPLY'``.

    Returns:
        Blended RGBA tuple (clamped to [0, 1]).
    """
    result: list[float] = []

    for i in range(4):
        e = existing[i]
        n = new_color[i]

        if mode == "MIX":
            # Linear interpolation: lerp(existing, new, strength)
            val = e + (n - e) * strength
        elif mode == "ADD":
            val = e + n * strength
        elif mode == "SUBTRACT":
            val = e - n * strength
        elif mode == "MULTIPLY":
            # Multiply: existing * lerp(1.0, new, strength)
            factor = 1.0 + (n - 1.0) * strength
            val = e * factor
        else:
            # Unknown mode — fall back to MIX
            val = e + (n - e) * strength

        result.append(max(0.0, min(1.0, val)))

    return (result[0], result[1], result[2], result[3])


# ---------------------------------------------------------------------------
# Internal falloff helper
# ---------------------------------------------------------------------------


def _apply_falloff(t: float, falloff_type: str) -> float:
    """Map normalised distance ``t`` (0=center, 1=edge) to a weight.

    Args:
        t: Normalised distance in [0, 1].
        falloff_type: ``'SMOOTH'``, ``'LINEAR'``, ``'SHARP'``, or
            ``'CONSTANT'``.

    Returns:
        Weight in [0, 1].  1.0 at center, 0.0 at edge (except CONSTANT).
    """
    t = max(0.0, min(1.0, t))

    if falloff_type == "CONSTANT":
        return 1.0
    elif falloff_type == "LINEAR":
        return 1.0 - t
    elif falloff_type == "SHARP":
        # Quadratic drop — strong near center, sharp cutoff
        return (1.0 - t) ** 2
    else:
        # SMOOTH: cubic Hermite (smoothstep-like)
        # Weight = 1 - smoothstep(0, 1, t)
        # smoothstep(t) = 3t^2 - 2t^3
        s = t * t * (3.0 - 2.0 * t)
        return 1.0 - s


# ---------------------------------------------------------------------------
# Blender handler (requires bpy)
# ---------------------------------------------------------------------------


def handle_vertex_paint(params: dict[str, Any]) -> dict[str, Any]:
    """Paint vertex colors at specific world/UV/vertex-index coordinates.

    Supports three paint modes, four blend modes, and four falloff types.
    Operates on Blender's ``color_attributes`` (FLOAT_COLOR, CORNER domain).

    Args (via params dict):
        object_name (str): Target mesh object name.
        paint_mode (str): ``'world'`` | ``'uv'`` | ``'vertex_index'``.

        For ``'world'`` mode:
            position (list): ``[x, y, z]`` world-space brush center.
            radius (float): Brush radius in world units.
            falloff (str): ``'SMOOTH'`` | ``'LINEAR'`` | ``'SHARP'`` |
                ``'CONSTANT'``.  Default ``'SMOOTH'``.

        For ``'uv'`` mode:
            uv_coord (list): ``[u, v]`` brush center in UV space.
            radius (float): Brush radius in UV units.
            falloff (str): Falloff type.  Default ``'SMOOTH'``.

        For ``'vertex_index'`` mode:
            vertex_indices (list[int]): Direct vertex indices to paint.

        Common:
            color (list): ``[r, g, b, a]`` brush color (0-1).
            blend_mode (str): ``'MIX'`` | ``'ADD'`` | ``'SUBTRACT'`` |
                ``'MULTIPLY'``.  Default ``'MIX'``.
            strength (float): Paint opacity (0-1).  Default ``1.0``.
            layer_name (str): Vertex color layer name.  Default ``'Col'``.

    Returns:
        Dict with status, affected vertex count, and per-channel statistics.
    """
    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}
    if obj.type != "MESH":
        return {
            "status": "error",
            "error": f"Object '{object_name}' is not a mesh (type: {obj.type})",
        }

    paint_mode = params.get("paint_mode", "world")
    color = tuple(params.get("color", [1.0, 1.0, 1.0, 1.0]))
    blend_mode = params.get("blend_mode", "MIX")
    strength = float(params.get("strength", 1.0))
    layer_name = params.get("layer_name", "Col")
    falloff = params.get("falloff", "SMOOTH")

    mesh = obj.data

    # Ensure vertex color layer exists
    if layer_name not in mesh.color_attributes:
        mesh.color_attributes.new(
            name=layer_name, type="FLOAT_COLOR", domain="CORNER"
        )
    vcol = mesh.color_attributes[layer_name]

    # Build vertex-to-loop mapping
    vert_to_loops: dict[int, list[int]] = {}
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            vi = mesh.loops[loop_idx].vertex_index
            vert_to_loops.setdefault(vi, []).append(loop_idx)

    # Compute affected vertices + weights based on paint mode
    affected: list[tuple[int, float]] = []

    if paint_mode == "world":
        position = params.get("position")
        radius = float(params.get("radius", 1.0))
        if not position:
            return {"status": "error", "error": "position is required for world mode"}

        # Transform vertices to world space
        world_matrix = obj.matrix_world
        vert_positions = []
        for v in mesh.vertices:
            world_co = world_matrix @ v.co
            vert_positions.append((world_co.x, world_co.y, world_co.z))

        affected = compute_paint_weights(
            vert_positions, tuple(position), radius, falloff
        )

    elif paint_mode == "uv":
        uv_coord = params.get("uv_coord")
        radius = float(params.get("radius", 0.1))
        if not uv_coord:
            return {"status": "error", "error": "uv_coord is required for uv mode"}

        # Get active UV layer
        uv_layer = mesh.uv_layers.active
        if uv_layer is None:
            return {"status": "error", "error": "No active UV layer found"}

        # Build per-vertex average UV (since UVs are per-loop)
        vert_uvs: dict[int, list[tuple[float, float]]] = {}
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                vi = mesh.loops[loop_idx].vertex_index
                uv = uv_layer.data[loop_idx].uv
                vert_uvs.setdefault(vi, []).append((uv.x, uv.y))

        avg_uvs: list[tuple[float, float]] = []
        uv_index_map: list[int] = []
        for vi in sorted(vert_uvs.keys()):
            uvlist = vert_uvs[vi]
            avg_u = sum(u for u, _ in uvlist) / len(uvlist)
            avg_v = sum(v for _, v in uvlist) / len(uvlist)
            avg_uvs.append((avg_u, avg_v))
            uv_index_map.append(vi)

        raw_weights = compute_paint_weights_uv(
            avg_uvs, tuple(uv_coord), radius, falloff
        )
        # Re-map indices back to real vertex indices
        affected = [(uv_index_map[idx], w) for idx, w in raw_weights]

    elif paint_mode == "vertex_index":
        vertex_indices = params.get("vertex_indices", [])
        if not vertex_indices:
            return {
                "status": "error",
                "error": "vertex_indices is required for vertex_index mode",
            }
        num_verts = len(mesh.vertices)
        for vi in vertex_indices:
            if 0 <= vi < num_verts:
                affected.append((vi, 1.0))

    else:
        return {
            "status": "error",
            "error": f"Unknown paint_mode '{paint_mode}'. "
            "Use 'world', 'uv', or 'vertex_index'.",
        }

    # Apply paint to affected vertices
    painted_count = 0
    for vi, weight in affected:
        loops = vert_to_loops.get(vi, [])
        if not loops:
            continue

        effective_strength = strength * weight

        for loop_idx in loops:
            existing = tuple(vcol.data[loop_idx].color)
            blended = blend_colors(existing, color, effective_strength, blend_mode)
            vcol.data[loop_idx].color = blended

        painted_count += 1

    # Gather statistics on the painted layer
    all_r, all_g, all_b, all_a = [], [], [], []
    for loop_data in vcol.data:
        c = loop_data.color
        all_r.append(c[0])
        all_g.append(c[1])
        all_b.append(c[2])
        all_a.append(c[3])

    def _channel_stats(values: list[float]) -> dict[str, float]:
        if not values:
            return {"min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "avg": round(sum(values) / len(values), 4),
        }

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "paint_mode": paint_mode,
            "blend_mode": blend_mode,
            "painted_vertices": painted_count,
            "total_vertices": len(mesh.vertices),
            "layer_name": layer_name,
            "channel_stats": {
                "r": _channel_stats(all_r),
                "g": _channel_stats(all_g),
                "b": _channel_stats(all_b),
                "a": _channel_stats(all_a),
            },
        },
    }
