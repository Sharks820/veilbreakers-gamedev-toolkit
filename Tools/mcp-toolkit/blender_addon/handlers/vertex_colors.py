"""Vertex color auto-painting system for material weathering effects.

Paints 4 channels of vertex color data that shaders can read:
  - R: Ambient Occlusion (cavity darkness from surrounding geometry)
  - G: Curvature / Edge Wear (convexity mask for edge wear effects)
  - B: Height Gradient (vertical position mask for moss/dirt accumulation)
  - A: Wetness/Damage (reserved mask, default 0.0)

Provides:
  - handle_auto_paint_vertex_colors: Blender command handler
  - compute_vertex_ao: Pure-logic AO computation (no bpy)
  - compute_vertex_curvature: Pure-logic curvature computation (no bpy)
  - compute_height_gradient: Pure-logic height gradient computation (no bpy)
"""

from __future__ import annotations

import math
from typing import Any

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure-logic compute functions (testable without Blender)
# ---------------------------------------------------------------------------


def compute_vertex_ao(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    normals: list[tuple[float, float, float]],
) -> list[float]:
    """Compute per-vertex ambient occlusion from mesh geometry.

    For each vertex, calculates how "enclosed" it is by averaging the
    dot products of adjacent face normals with the vertex normal.
    Concave areas (crevices, corners) produce lower values.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples (each tuple is vertex indices).
        normals: List of (nx, ny, nz) face normals, one per face.

    Returns:
        Per-vertex AO values in [0, 1]. 1.0 = fully exposed, 0.0 = fully occluded.
    """
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Build vertex-to-face adjacency
    vert_faces: list[list[int]] = [[] for _ in range(num_verts)]
    for fi, face in enumerate(faces):
        for vi in face:
            if 0 <= vi < num_verts:
                vert_faces[vi].append(fi)

    # Compute per-vertex normal (average of adjacent face normals)
    vert_normals: list[tuple[float, float, float]] = []
    for vi in range(num_verts):
        adj = vert_faces[vi]
        if not adj:
            vert_normals.append((0.0, 0.0, 1.0))
            continue
        nx, ny, nz = 0.0, 0.0, 0.0
        for fi in adj:
            fn = normals[fi]
            nx += fn[0]
            ny += fn[1]
            nz += fn[2]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-9:
            nx /= length
            ny /= length
            nz /= length
        else:
            nx, ny, nz = 0.0, 0.0, 1.0
        vert_normals.append((nx, ny, nz))

    # Compute AO: for each vertex, average dot products of adjacent
    # face normals with the vertex normal. High agreement = exposed,
    # low agreement = occluded.
    ao_values: list[float] = []
    for vi in range(num_verts):
        adj = vert_faces[vi]
        if len(adj) < 2:
            # Isolated vertex or single-face vertex -- fully exposed
            ao_values.append(1.0)
            continue

        vn = vert_normals[vi]
        dot_sum = 0.0
        pair_count = 0

        # Compare adjacent face normals pairwise
        for i in range(len(adj)):
            for j in range(i + 1, len(adj)):
                fn_a = normals[adj[i]]
                fn_b = normals[adj[j]]
                # Dot product between face normals
                dot = fn_a[0] * fn_b[0] + fn_a[1] * fn_b[1] + fn_a[2] * fn_b[2]
                dot_sum += dot
                pair_count += 1

        if pair_count > 0:
            avg_dot = dot_sum / pair_count
            # Map from [-1, 1] to [0, 1]
            # dot = 1.0 means faces are coplanar (flat, exposed)
            # dot = -1.0 means faces face opposite directions (deep crevice)
            ao = (avg_dot + 1.0) * 0.5
        else:
            ao = 1.0

        ao_values.append(max(0.0, min(1.0, ao)))

    return ao_values


def compute_vertex_curvature(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    edges: list[tuple[int, int]],
) -> list[float]:
    """Compute per-vertex curvature (convexity mask) from mesh geometry.

    For each edge, calculates the angle between the two adjacent face
    normals. Convex edges (outward angle) produce bright values,
    concave edges (inward angle) produce dark values.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.
        edges: List of (v0, v1) edge vertex index pairs.

    Returns:
        Per-vertex curvature values in [0, 1].
        0.0 = concave, 0.5 = flat, 1.0 = convex.
    """
    num_verts = len(vertices)
    if num_verts == 0:
        return []

    # Compute face normals
    face_normals = _compute_face_normals(vertices, faces)

    # Build edge-to-face adjacency
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        n = len(face)
        for k in range(n):
            v0, v1 = face[k], face[(k + 1) % n]
            key = (min(v0, v1), max(v0, v1))
            if key not in edge_faces:
                edge_faces[key] = []
            edge_faces[key].append(fi)

    # Accumulate curvature per vertex from edges
    vert_curvature_sum: list[float] = [0.0] * num_verts
    vert_curvature_count: list[int] = [0] * num_verts

    # Pre-compute face centers
    face_centers: list[tuple[float, float, float]] = []
    for face in faces:
        cx = sum(vertices[vi][0] for vi in face) / len(face)
        cy = sum(vertices[vi][1] for vi in face) / len(face)
        cz = sum(vertices[vi][2] for vi in face) / len(face)
        face_centers.append((cx, cy, cz))

    for v0, v1 in edges:
        key = (min(v0, v1), max(v0, v1))
        adj_faces = edge_faces.get(key, [])
        if len(adj_faces) != 2:
            # Boundary edge or non-manifold -- skip
            continue

        fi_a, fi_b = adj_faces[0], adj_faces[1]
        fn_a = face_normals[fi_a]
        fn_b = face_normals[fi_b]

        # Dot product between face normals
        dot = fn_a[0] * fn_b[0] + fn_a[1] * fn_b[1] + fn_a[2] * fn_b[2]
        dot = max(-1.0, min(1.0, dot))

        # Angle between normals (0 = coplanar, pi = opposite)
        angle = math.acos(dot)

        # Determine convexity: check if face B's center is on the
        # opposite side of face A's plane from face A's normal direction.
        # Use face A's center as the reference point on the plane.
        fc_a = face_centers[fi_a]
        fc_b = face_centers[fi_b]

        # Vector from face A center to face B center
        a_to_b = (
            fc_b[0] - fc_a[0],
            fc_b[1] - fc_a[1],
            fc_b[2] - fc_a[2],
        )

        # Dot with face A's normal: negative means B is "behind" A's plane
        # (convex if normals face outward, concave if inward).
        dot_ab = (
            fn_a[0] * a_to_b[0]
            + fn_a[1] * a_to_b[1]
            + fn_a[2] * a_to_b[2]
        )

        # Also check B->A with face B's normal for consistency
        b_to_a = (-a_to_b[0], -a_to_b[1], -a_to_b[2])
        dot_ba = (
            fn_b[0] * b_to_a[0]
            + fn_b[1] * b_to_a[1]
            + fn_b[2] * b_to_a[2]
        )

        # For convex edges: both face centers are "behind" each other's
        # planes, so both dots have the same sign (both negative if
        # normals face outward, both positive if inward).
        # For concave edges: the dots have opposite signs.
        # Convex: dot_ab * dot_ba > 0 (same sign)
        # Concave: dot_ab * dot_ba < 0 (opposite signs)
        # Edge case: if either is zero, treat as flat.
        product = dot_ab * dot_ba

        if product > 0:
            # Convex
            signed_curvature = angle
        elif product < 0:
            # Concave
            signed_curvature = -angle
        else:
            # Flat / coplanar
            signed_curvature = 0.0

        # Map from [-pi, pi] to [0, 1]
        # -pi (deep concave) -> 0.0
        # 0 (flat) -> 0.5
        # +pi (sharp convex) -> 1.0
        curvature_01 = (signed_curvature / math.pi + 1.0) * 0.5
        curvature_01 = max(0.0, min(1.0, curvature_01))

        vert_curvature_sum[v0] += curvature_01
        vert_curvature_count[v0] += 1
        vert_curvature_sum[v1] += curvature_01
        vert_curvature_count[v1] += 1

    # Average per vertex
    result: list[float] = []
    for vi in range(num_verts):
        if vert_curvature_count[vi] > 0:
            result.append(vert_curvature_sum[vi] / vert_curvature_count[vi])
        else:
            result.append(0.5)  # No edge data -- assume flat

    return result


def compute_height_gradient(
    vertices: list[tuple[float, float, float]],
    invert: bool = False,
) -> list[float]:
    """Compute per-vertex height gradient from mesh geometry.

    Maps vertex Z positions to [0, 1] relative to the object bounding box.
    By default, bottom = 1.0 (high B value for moss/dirt) and top = 0.0.

    Args:
        vertices: List of (x, y, z) vertex positions.
        invert: If True, flip so top = 1.0 and bottom = 0.0.

    Returns:
        Per-vertex height values in [0, 1].
    """
    if not vertices:
        return []

    z_values = [v[2] for v in vertices]
    z_min = min(z_values)
    z_max = max(z_values)
    z_range = z_max - z_min

    if z_range < 1e-9:
        # Flat object -- all same height
        return [0.5] * len(vertices)

    result: list[float] = []
    for z in z_values:
        # Normalized: 0.0 at bottom, 1.0 at top
        normalized = (z - z_min) / z_range
        if invert:
            # invert: top = 1.0, bottom = 0.0
            result.append(normalized)
        else:
            # default: bottom = 1.0 (moss/dirt), top = 0.0
            result.append(1.0 - normalized)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_face_normals(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
) -> list[tuple[float, float, float]]:
    """Compute face normals from vertex positions and face indices."""
    normals: list[tuple[float, float, float]] = []
    for face in faces:
        if len(face) < 3:
            normals.append((0.0, 0.0, 1.0))
            continue
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]
        # Edge vectors
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        # Cross product
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-9:
            normals.append((nx / length, ny / length, nz / length))
        else:
            normals.append((0.0, 0.0, 1.0))
    return normals


# ---------------------------------------------------------------------------
# Blender handler (requires bpy)
# ---------------------------------------------------------------------------


def handle_auto_paint_vertex_colors(params: dict[str, Any]) -> dict[str, Any]:
    """Auto-paint vertex colors on a mesh for material weathering effects.

    Paints 4 channels into a FLOAT_COLOR vertex color layer named
    'VB_VertexColors':
      R = Ambient Occlusion (cavity darkness)
      G = Curvature / Edge Wear (convexity mask)
      B = Height Gradient (vertical position for moss/dirt)
      A = Wetness/Damage (reserved, default 0.0)

    Args (via params dict):
        object_name (str): Target mesh object name.
        channels (list[str]): Which channels to paint.
            Default: ["ao", "curvature", "height", "wetness"]
        ao_strength (float): AO intensity multiplier. Default 1.0.
        curvature_strength (float): Curvature intensity multiplier. Default 1.0.
        height_invert (bool): Flip height gradient. Default False.

    Returns:
        Dict with channel statistics (min/max/avg per channel) and status.
    """
    object_name = params.get("object_name")
    if not object_name:
        return {"status": "error", "error": "object_name is required"}

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return {"status": "error", "error": f"Object '{object_name}' not found"}
    if obj.type != "MESH":
        return {"status": "error", "error": f"Object '{object_name}' is not a mesh (type: {obj.type})"}

    channels = params.get("channels", ["ao", "curvature", "height", "wetness"])
    ao_strength = float(params.get("ao_strength", 1.0))
    curvature_strength = float(params.get("curvature_strength", 1.0))
    height_invert = bool(params.get("height_invert", False))

    mesh = obj.data

    # Ensure mesh data is up to date
    mesh.calc_normals_split()

    # Extract geometry data for pure-logic functions
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]
    face_normals = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]

    # Build edge list
    edges = [(e.vertices[0], e.vertices[1]) for e in mesh.edges]

    num_verts = len(vertices)

    # Compute channels using pure-logic functions
    ao_values = [1.0] * num_verts
    curvature_values = [0.5] * num_verts
    height_values = [0.5] * num_verts
    wetness_values = [0.0] * num_verts

    if "ao" in channels:
        ao_raw = compute_vertex_ao(vertices, faces, face_normals)
        ao_values = [max(0.0, min(1.0, v * ao_strength)) for v in ao_raw]

    if "curvature" in channels:
        curv_raw = compute_vertex_curvature(vertices, faces, edges)
        # Apply strength: push values away from 0.5
        curvature_values = []
        for v in curv_raw:
            offset = (v - 0.5) * curvature_strength
            curvature_values.append(max(0.0, min(1.0, 0.5 + offset)))

    if "height" in channels:
        height_values = compute_height_gradient(vertices, invert=height_invert)

    # Wetness stays at 0.0 unless explicitly set (reserved channel)

    # Get or create vertex color layer
    vcol_name = "VB_VertexColors"
    if vcol_name not in mesh.color_attributes:
        mesh.color_attributes.new(name=vcol_name, type='FLOAT_COLOR', domain='CORNER')
    vcol = mesh.color_attributes[vcol_name]

    # Paint per-loop (corner) colors
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            vert_idx = mesh.loops[loop_idx].vertex_index
            r = ao_values[vert_idx]
            g = curvature_values[vert_idx]
            b = height_values[vert_idx]
            a = wetness_values[vert_idx]
            vcol.data[loop_idx].color = (r, g, b, a)

    # Compute statistics
    stats: dict[str, dict[str, float]] = {}
    channel_data = {
        "ao": ao_values,
        "curvature": curvature_values,
        "height": height_values,
        "wetness": wetness_values,
    }
    for ch_name, values in channel_data.items():
        if values:
            stats[ch_name] = {
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "avg": round(sum(values) / len(values), 4),
            }
        else:
            stats[ch_name] = {"min": 0.0, "max": 0.0, "avg": 0.0}

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "vertex_count": num_verts,
            "layer_name": vcol_name,
            "channels_painted": channels,
            "channel_stats": stats,
        },
    }
