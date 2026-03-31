"""Silhouette-preserving LOD pipeline with per-asset-type presets.

Provides:
- LOD_PRESETS: Per-asset-type LOD configuration (ratios, screen %, preserve regions)
- compute_silhouette_importance: Per-vertex silhouette importance from edge analysis
- compute_region_importance: Per-vertex importance boost for named regions
- decimate_preserving_silhouette: Edge-collapse decimation weighted by importance
- generate_collision_mesh: Convex hull collision mesh generation
- generate_lod_chain: Full LOD chain from preset lookup
- handle_generate_lods: bpy handler for Blender integration

All compute functions are pure logic (no bpy). Only handle_generate_lods uses bpy.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Per-asset-type LOD presets
# ---------------------------------------------------------------------------

LOD_PRESETS: dict[str, dict[str, Any]] = {
    "hero_character": {
        "ratios": [1.0, 0.5, 0.25, 0.1],
        "screen_percentages": [1.0, 0.5, 0.25, 0.05],
        "preserve_regions": ["face", "hands"],
        "min_tris": [30000, 15000, 7500, 3000],
    },
    "standard_mob": {
        "ratios": [1.0, 0.5, 0.25, 0.08],
        "screen_percentages": [1.0, 0.4, 0.15, 0.03],
        "min_tris": [8000, 4000, 2000, 800],
    },
    "building": {
        "ratios": [1.0, 0.5, 0.2, 0.07],
        "screen_percentages": [1.0, 0.4, 0.15, 0.02],
        "preserve_regions": ["roofline", "silhouette"],
        "min_tris": [5000, 2500, 1000, 500],
    },
    "prop_small": {
        "ratios": [1.0, 0.5, 0.15],
        "screen_percentages": [1.0, 0.3, 0.05],
        "min_tris": [500, 250, 100],
    },
    "prop_medium": {
        "ratios": [1.0, 0.5, 0.2],
        "screen_percentages": [1.0, 0.3, 0.08],
        "min_tris": [1000, 500, 200],
    },
    "weapon": {
        "ratios": [1.0, 0.5, 0.2],
        "screen_percentages": [1.0, 0.3, 0.08],
        "min_tris": [3000, 1500, 500],
    },
    "vegetation": {
        "ratios": [1.0, 0.5, 0.15, 0.0],  # 0.0 = billboard
        "screen_percentages": [1.0, 0.3, 0.08, 0.02],
        "min_tris": [5000, 2500, 800, 4],  # 4 = billboard quad
    },
    "furniture": {
        "ratios": [1.0, 0.5, 0.25],
        "screen_percentages": [1.0, 0.3, 0.1],
        "min_tris": [200, 100, 50],
    },
}

# Type alias matching the project convention
MeshData = dict[str, Any]


# ---------------------------------------------------------------------------
# Pure-logic: vector math helpers
# ---------------------------------------------------------------------------


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Cross product of two 3D vectors."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(
    a: tuple[float, float, float], b: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Subtract vector b from a."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(
    a: tuple[float, float, float], b: tuple[float, float, float],
) -> float:
    """Dot product of two 3D vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Normalize a 3D vector. Returns zero vector if length is near zero."""
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _face_normal(
    vertices: list[tuple[float, float, float]],
    face: tuple[int, ...],
) -> tuple[float, float, float]:
    """Compute face normal from first three vertices."""
    if len(face) < 3:
        return (0.0, 0.0, 0.0)
    v0 = vertices[face[0]]
    v1 = vertices[face[1]]
    v2 = vertices[face[2]]
    edge1 = _sub(v1, v0)
    edge2 = _sub(v2, v0)
    return _normalize(_cross(edge1, edge2))


# ---------------------------------------------------------------------------
# Pure-logic: silhouette importance
# ---------------------------------------------------------------------------


def compute_silhouette_importance(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    view_directions: list[tuple[float, float, float]] | None = None,
) -> list[float]:
    """Compute per-vertex silhouette importance weights.

    Vertices on the outline (shared by front-facing and back-facing triangles)
    receive HIGH importance. Interior vertices receive LOW importance.

    Multiple view directions are sampled to produce a robust importance score.

    Args:
        vertices: List of vertex positions (x, y, z).
        faces: List of face tuples (vertex indices).
        view_directions: Optional list of view vectors to evaluate.
            Defaults to 6 cardinal + 8 corner directions (14 total).

    Returns:
        List of importance weights, one per vertex, in range [0.0, 1.0].
    """
    if not vertices or not faces:
        return [0.0] * len(vertices)

    num_verts = len(vertices)

    if view_directions is None:
        # 6 cardinal + 8 corner directions for robust coverage
        view_directions = [
            (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0), (0.0, 0.0, -1.0),
            (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
            (1.0, -1.0, 1.0), (1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0), (-1.0, 1.0, -1.0),
            (1.0, -1.0, -1.0), (-1.0, -1.0, -1.0),
        ]
        view_directions = [_normalize(v) for v in view_directions]

    # Precompute face normals
    face_normals = [_face_normal(vertices, f) for f in faces]

    # Build edge-to-face adjacency: edge -> list of face indices
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(faces):
        n = len(face)
        for j in range(n):
            v_a = face[j]
            v_b = face[(j + 1) % n]
            edge_key = (min(v_a, v_b), max(v_a, v_b))
            if edge_key not in edge_faces:
                edge_faces[edge_key] = []
            edge_faces[edge_key].append(fi)

    # Accumulate silhouette score per vertex across all view directions
    silhouette_scores = [0.0] * num_verts

    for view_dir in view_directions:
        # Classify faces as front or back for this view direction
        face_front = [_dot(fn, view_dir) > 0.0 for fn in face_normals]

        # An edge is a silhouette edge if its two adjacent faces disagree
        for (v_a, v_b), adj_faces in edge_faces.items():
            if len(adj_faces) == 1:
                # Boundary edge: always a silhouette edge
                silhouette_scores[v_a] += 1.0
                silhouette_scores[v_b] += 1.0
            elif len(adj_faces) >= 2:
                has_front = any(face_front[fi] for fi in adj_faces)
                has_back = any(not face_front[fi] for fi in adj_faces)
                if has_front and has_back:
                    silhouette_scores[v_a] += 1.0
                    silhouette_scores[v_b] += 1.0

    # Normalize to [0, 1]
    max_score = max(silhouette_scores) if silhouette_scores else 1.0
    if max_score < 1e-12:
        return [0.0] * num_verts

    return [min(1.0, s / max_score) for s in silhouette_scores]


# ---------------------------------------------------------------------------
# Pure-logic: region importance
# ---------------------------------------------------------------------------


def compute_region_importance(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    regions: dict[str, set[int]],
) -> list[float]:
    """Compute per-vertex importance boost from named preserve regions.

    Args:
        vertices: List of vertex positions.
        faces: List of face tuples (unused but kept for API consistency).
        regions: Maps region names to sets of vertex indices.
            e.g., {"face": {0, 1, 2, ...}, "hands": {50, 51, ...}}

    Returns:
        List of importance weights, one per vertex, in range [0.0, 1.0].
        Vertices in named regions get 1.0; others get 0.0.
    """
    num_verts = len(vertices)
    if not vertices:
        return []

    importance = [0.0] * num_verts

    for _region_name, vertex_indices in regions.items():
        for vi in vertex_indices:
            if 0 <= vi < num_verts:
                importance[vi] = 1.0

    return importance


# ---------------------------------------------------------------------------
# Pure-logic: edge-collapse decimation
# ---------------------------------------------------------------------------


def _edge_collapse_cost(
    vertices: list[tuple[float, float, float]],
    v_a: int,
    v_b: int,
    importance_weights: list[float],
) -> float:
    """Compute cost of collapsing edge (v_a, v_b).

    Cost = edge_length * (1.0 + avg_importance * 5.0).
    High importance edges cost more to collapse, so they survive longer.
    """
    pos_a = vertices[v_a]
    pos_b = vertices[v_b]
    dx = pos_a[0] - pos_b[0]
    dy = pos_a[1] - pos_b[1]
    dz = pos_a[2] - pos_b[2]
    edge_length = math.sqrt(dx * dx + dy * dy + dz * dz)

    avg_importance = (importance_weights[v_a] + importance_weights[v_b]) / 2.0
    return edge_length * (1.0 + avg_importance * 5.0)


def decimate_preserving_silhouette(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    target_ratio: float,
    importance_weights: list[float],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Edge-collapse decimation that preserves important vertices.

    Collapses the cheapest (lowest importance) edges first until the target
    vertex ratio is reached.

    Args:
        vertices: List of vertex positions.
        faces: List of face tuples (vertex indices).
        target_ratio: Target ratio of vertices to keep (0.0 to 1.0).
        importance_weights: Per-vertex importance (0.0 = expendable, 1.0 = preserve).

    Returns:
        Tuple of (simplified_vertices, simplified_faces).
    """
    if target_ratio >= 1.0:
        return list(vertices), list(faces)

    if not vertices or not faces:
        return list(vertices), list(faces)

    num_verts = len(vertices)
    target_verts = max(4, int(math.ceil(num_verts * target_ratio)))

    if target_verts >= num_verts:
        return list(vertices), list(faces)

    # Working copies
    verts = list(vertices)
    weights = list(importance_weights)
    # Track which vertex each original vertex maps to (union-find style)
    remap = list(range(num_verts))

    def find_root(v: int) -> int:
        """Find the root representative for vertex v."""
        while remap[v] != v:
            remap[v] = remap[remap[v]]  # path compression
            v = remap[v]
        return v

    # Collect unique edges
    edge_set: set[tuple[int, int]] = set()
    for face in faces:
        n = len(face)
        for j in range(n):
            v_a = face[j]
            v_b = face[(j + 1) % n]
            edge_key = (min(v_a, v_b), max(v_a, v_b))
            edge_set.add(edge_key)

    # Build priority list: (cost, v_a, v_b)
    edge_costs: list[tuple[float, int, int]] = []
    for v_a, v_b in edge_set:
        cost = _edge_collapse_cost(verts, v_a, v_b, weights)
        edge_costs.append((cost, v_a, v_b))

    # Sort by cost ascending -- cheapest collapses first
    edge_costs.sort()

    # Track active vertex count
    active_verts = set(range(num_verts))
    collapses_needed = num_verts - target_verts

    for cost, v_a, v_b in edge_costs:
        if collapses_needed <= 0:
            break

        root_a = find_root(v_a)
        root_b = find_root(v_b)

        if root_a == root_b:
            continue  # Already merged

        # Keep the higher-importance vertex
        if weights[root_a] >= weights[root_b]:
            keep, remove = root_a, root_b
        else:
            keep, remove = root_b, root_a

        remap[remove] = keep
        # Midpoint position weighted by importance
        w_keep = weights[keep]
        w_remove = weights[remove]
        total_w = w_keep + w_remove
        if total_w > 1e-12:
            t = w_keep / total_w
        else:
            t = 0.5
        verts[keep] = (
            verts[keep][0] * t + verts[remove][0] * (1.0 - t),
            verts[keep][1] * t + verts[remove][1] * (1.0 - t),
            verts[keep][2] * t + verts[remove][2] * (1.0 - t),
        )
        # Propagate max importance
        weights[keep] = max(weights[keep], weights[remove])

        active_verts.discard(remove)
        collapses_needed -= 1

    # Remap faces
    new_faces: list[tuple[int, ...]] = []
    for face in faces:
        remapped = tuple(find_root(v) for v in face)
        # Remove degenerate faces (collapsed vertices)
        unique: list[int] = []
        seen: set[int] = set()
        for v in remapped:
            if v not in seen:
                unique.append(v)
                seen.add(v)
        if len(unique) >= 3:
            new_faces.append(tuple(unique))

    # Compact: only keep active vertices
    active_sorted = sorted(active_verts)
    vert_compact_map = {old: new for new, old in enumerate(active_sorted)}
    compact_verts = [verts[v] for v in active_sorted]
    compact_faces: list[tuple[int, ...]] = []
    for face in new_faces:
        try:
            compact_faces.append(tuple(vert_compact_map[v] for v in face))
        except KeyError:
            continue  # Skip faces referencing removed vertices

    return compact_verts, compact_faces


# ---------------------------------------------------------------------------
# Pure-logic: collision mesh (convex hull)
# ---------------------------------------------------------------------------


def generate_collision_mesh(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    max_tris: int = 50,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a simplified convex hull for physics collision.

    Uses an incremental convex hull algorithm. The result has at most
    ``max_tris`` triangles.

    Args:
        vertices: Source mesh vertices.
        faces: Source mesh faces (used only for reference; hull is from vertices).
        max_tris: Maximum triangle count for the collision mesh.

    Returns:
        Tuple of (hull_vertices, hull_faces) where all faces are triangles
        with outward-pointing normals.
    """
    if len(vertices) < 4:
        return list(vertices), list(faces)

    pts = list(vertices)
    n = len(pts)

    # Find initial tetrahedron
    min_x_idx = min(range(n), key=lambda i: pts[i][0])
    max_x_idx = max(range(n), key=lambda i: pts[i][0])
    if min_x_idx == max_x_idx:
        max_x_idx = max(range(n), key=lambda i: pts[i][1])
        if min_x_idx == max_x_idx:
            return list(vertices[:4]), list(faces)

    # Find point farthest from line (min_x, max_x)
    line_dir = _sub(pts[max_x_idx], pts[min_x_idx])
    line_len_sq = _dot(line_dir, line_dir)
    if line_len_sq < 1e-12:
        return list(vertices[:4]), list(faces)

    best_dist = -1.0
    third_idx = -1
    for i in range(n):
        if i == min_x_idx or i == max_x_idx:
            continue
        to_point = _sub(pts[i], pts[min_x_idx])
        proj = _dot(to_point, line_dir) / line_len_sq
        closest = (
            pts[min_x_idx][0] + proj * line_dir[0],
            pts[min_x_idx][1] + proj * line_dir[1],
            pts[min_x_idx][2] + proj * line_dir[2],
        )
        diff = _sub(pts[i], closest)
        dist = _dot(diff, diff)
        if dist > best_dist:
            best_dist = dist
            third_idx = i

    if third_idx < 0:
        return list(vertices[:4]), list(faces)

    # Find point farthest from the plane of the first three
    plane_normal = _normalize(_cross(
        _sub(pts[max_x_idx], pts[min_x_idx]),
        _sub(pts[third_idx], pts[min_x_idx]),
    ))

    best_dist = -1.0
    fourth_idx = -1
    for i in range(n):
        if i in (min_x_idx, max_x_idx, third_idx):
            continue
        dist = abs(_dot(_sub(pts[i], pts[min_x_idx]), plane_normal))
        if dist > best_dist:
            best_dist = dist
            fourth_idx = i

    if fourth_idx < 0:
        return list(vertices[:4]), list(faces)

    # Build initial tetrahedron
    tet_indices = [min_x_idx, max_x_idx, third_idx, fourth_idx]

    # Orient so fourth point is above the first triangle
    tri_normal = _cross(
        _sub(pts[tet_indices[1]], pts[tet_indices[0]]),
        _sub(pts[tet_indices[2]], pts[tet_indices[0]]),
    )
    if _dot(tri_normal, _sub(pts[tet_indices[3]], pts[tet_indices[0]])) > 0:
        tet_indices[1], tet_indices[2] = tet_indices[2], tet_indices[1]

    # Initial faces of the tetrahedron (CCW winding, outward normals)
    hull_faces: list[tuple[int, int, int]] = [
        (tet_indices[0], tet_indices[1], tet_indices[2]),
        (tet_indices[0], tet_indices[3], tet_indices[1]),
        (tet_indices[1], tet_indices[3], tet_indices[2]),
        (tet_indices[0], tet_indices[2], tet_indices[3]),
    ]
    hull_vert_set = set(tet_indices)

    # Incrementally add remaining points
    for pi in range(n):
        if pi in hull_vert_set:
            continue

        p = pts[pi]

        # Find faces visible from this point
        visible: list[int] = []
        for fi, (a, b, c) in enumerate(hull_faces):
            fn = _cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a]))
            if _dot(fn, _sub(p, pts[a])) > 1e-10:
                visible.append(fi)

        if not visible:
            continue  # Point is inside the hull

        # Find horizon edges (edges shared by exactly one visible face)
        edge_count: dict[tuple[int, int], int] = {}
        for fi in visible:
            a, b, c = hull_faces[fi]
            for edge in [(a, b), (b, c), (c, a)]:
                sorted_edge = (min(edge), max(edge))
                edge_count[sorted_edge] = edge_count.get(sorted_edge, 0) + 1

        horizon_edges: list[tuple[int, int]] = []
        for fi in visible:
            a, b, c = hull_faces[fi]
            for edge in [(a, b), (b, c), (c, a)]:
                sorted_edge = (min(edge), max(edge))
                if edge_count[sorted_edge] == 1:
                    horizon_edges.append(edge)

        # Remove visible faces
        for fi in sorted(visible, reverse=True):
            hull_faces.pop(fi)

        # Add new faces from horizon edges to the new point
        for e0, e1 in horizon_edges:
            new_face = (e0, e1, pi)
            fn = _cross(_sub(pts[e1], pts[e0]), _sub(p, pts[e0]))
            centroid = (
                sum(pts[i][0] for i in hull_vert_set) / max(len(hull_vert_set), 1),
                sum(pts[i][1] for i in hull_vert_set) / max(len(hull_vert_set), 1),
                sum(pts[i][2] for i in hull_vert_set) / max(len(hull_vert_set), 1),
            )
            if _dot(fn, _sub(centroid, pts[e0])) > 0:
                new_face = (e1, e0, pi)
            hull_faces.append(new_face)

        hull_vert_set.add(pi)

    # Compact to only used vertices
    used_indices = sorted(set(v for f in hull_faces for v in f))
    index_map = {old: new for new, old in enumerate(used_indices)}
    hull_verts = [pts[i] for i in used_indices]
    remapped_faces: list[tuple[int, ...]] = [
        (index_map[a], index_map[b], index_map[c]) for a, b, c in hull_faces
    ]

    # If too many triangles, simplify by decimating with uniform importance
    if len(remapped_faces) > max_tris:
        ratio = max_tris / len(remapped_faces)
        uniform_weights = [0.5] * len(hull_verts)
        hull_verts, remapped_faces = decimate_preserving_silhouette(
            hull_verts, remapped_faces, ratio, uniform_weights,
        )

    return hull_verts, remapped_faces


# ---------------------------------------------------------------------------
# Pure-logic: billboard quad generation
# ---------------------------------------------------------------------------


def _generate_billboard_quad(
    vertices: list[tuple[float, float, float]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Generate a billboard quad from the bounding box of the input mesh.

    The quad faces +Z, centered on the mesh centroid, sized to the
    bounding box width and height.

    Returns:
        Tuple of (4 vertices, 1 quad face).
    """
    if not vertices:
        return [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)]

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0

    half_w = (max(xs) - min(xs)) / 2.0
    half_h = (max(ys) - min(ys)) / 2.0

    half_w = max(half_w, 0.01)
    half_h = max(half_h, 0.01)

    quad_verts: list[tuple[float, float, float]] = [
        (cx - half_w, cy - half_h, cz),
        (cx + half_w, cy - half_h, cz),
        (cx + half_w, cy + half_h, cz),
        (cx - half_w, cy + half_h, cz),
    ]
    quad_faces: list[tuple[int, ...]] = [(0, 1, 2, 3)]

    return quad_verts, quad_faces


# ---------------------------------------------------------------------------
# Pure-logic: auto-detect vertex regions from bounding box heuristics
# ---------------------------------------------------------------------------


def _auto_detect_regions(
    vertices: list[tuple[float, float, float]],
    region_names: list[str],
) -> dict[str, set[int]]:
    """Auto-detect vertex regions by bounding box position heuristics.

    Region detection rules:
    - "face": top 13% of bounding box height
    - "hands": vertices at Y 35-50% and X beyond 70% from center
    - "roofline": top 20% of bounding box height
    - "silhouette": vertices near the XZ bounding box perimeter
    """
    if not vertices:
        return {}

    ys = [v[1] for v in vertices]
    xs = [v[0] for v in vertices]
    zs = [v[2] for v in vertices]

    min_y, max_y = min(ys), max(ys)
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    height = max_y - min_y
    width = max_x - min_x
    depth = max_z - min_z

    x_mid = (min_x + max_x) / 2.0

    regions: dict[str, set[int]] = {}

    for name in region_names:
        region_verts: set[int] = set()

        if name == "face":
            threshold_y = max_y - 0.13 * max(height, 0.001)
            for i, v in enumerate(vertices):
                if v[1] >= threshold_y:
                    region_verts.add(i)

        elif name == "hands":
            y_low = min_y + 0.35 * max(height, 0.001)
            y_high = min_y + 0.50 * max(height, 0.001)
            x_threshold = 0.70 * max(width / 2.0, 0.001)
            for i, v in enumerate(vertices):
                if y_low <= v[1] <= y_high and abs(v[0] - x_mid) >= x_threshold:
                    region_verts.add(i)

        elif name == "roofline":
            threshold_y = max_y - 0.20 * max(height, 0.001)
            for i, v in enumerate(vertices):
                if v[1] >= threshold_y:
                    region_verts.add(i)

        elif name == "silhouette":
            margin_x = 0.15 * max(width, 0.001)
            margin_z = 0.15 * max(depth, 0.001)
            for i, v in enumerate(vertices):
                near_x = (v[0] - min_x < margin_x) or (max_x - v[0] < margin_x)
                near_z = (v[2] - min_z < margin_z) or (max_z - v[2] < margin_z)
                if near_x or near_z:
                    region_verts.add(i)

        regions[name] = region_verts

    return regions


# ---------------------------------------------------------------------------
# Pure-logic: LOD chain generation
# ---------------------------------------------------------------------------


def generate_lod_chain(
    mesh_data: MeshData,
    asset_type: str = "prop_medium",
) -> list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]], int]]:
    """Generate a full LOD chain from a mesh spec using asset-type presets.

    Args:
        mesh_data: Dict with "vertices" and "faces" keys.
        asset_type: One of the LOD_PRESETS keys. Defaults to "prop_medium".

    Returns:
        List of (vertices, faces, lod_level) tuples, one per LOD level.

    Raises:
        ValueError: If asset_type is not in LOD_PRESETS.
    """
    preset = LOD_PRESETS.get(asset_type)
    if preset is None:
        raise ValueError(
            f"Unknown asset type '{asset_type}'. "
            f"Available: {', '.join(sorted(LOD_PRESETS.keys()))}"
        )

    vertices = mesh_data.get("vertices", [])
    faces = mesh_data.get("faces", [])

    if not vertices or not faces:
        return []

    ratios = preset["ratios"]

    # Compute silhouette importance for the source mesh
    silhouette_importance = compute_silhouette_importance(vertices, faces)

    # Compute region importance if preserve_regions exist
    preserve_regions = preset.get("preserve_regions", [])
    if preserve_regions:
        regions = _auto_detect_regions(vertices, preserve_regions)
        region_importance = compute_region_importance(vertices, faces, regions)
        combined_importance = [
            max(s, r) for s, r in zip(silhouette_importance, region_importance)
        ]
    else:
        combined_importance = silhouette_importance

    lod_chain: list[tuple[list[tuple[float, float, float]], list[tuple[int, ...]], int]] = []

    for level, ratio in enumerate(ratios):
        if ratio <= 0.0:
            # Billboard LOD
            billboard_verts, billboard_faces = _generate_billboard_quad(vertices)
            lod_chain.append((billboard_verts, billboard_faces, level))
        elif ratio >= 1.0:
            # LOD0: full detail
            lod_chain.append((list(vertices), list(faces), level))
        else:
            # Copy importance weights since decimation mutates them
            weights_copy = list(combined_importance)
            lod_verts, lod_faces = decimate_preserving_silhouette(
                vertices, faces, ratio, weights_copy,
            )
            lod_chain.append((lod_verts, lod_faces, level))

    return lod_chain


# ---------------------------------------------------------------------------
# Pure-logic: Scene Budget Validator
# ---------------------------------------------------------------------------

# Budget thresholds for different spatial scopes
SCENE_BUDGETS: dict[str, dict[str, int]] = {
    "per_room": {
        "min_tris": 50_000,
        "max_tris": 150_000,
        "label": "Per-Room Budget (50K-150K tris)",
    },
    "per_block": {
        "min_tris": 200_000,
        "max_tris": 500_000,
        "label": "Per-Block Budget (200K-500K tris)",
    },
    "per_frame": {
        "min_tris": 2_000_000,
        "max_tris": 6_000_000,
        "label": "Per-Frame Budget (2M-6M tris @ 60fps)",
    },
}


class SceneBudgetValidator:
    """Validate scene polygon budgets at room, block, and frame levels.

    Pure-logic validator (no bpy). Accepts a list of object triangle counts
    and evaluates against configurable budgets.

    Usage:
        validator = SceneBudgetValidator()
        report = validator.validate(
            object_tris=[1200, 3400, 800, 2100],
            scope="per_room",
        )
    """

    def validate(
        self,
        object_tris: list[int],
        scope: str = "per_room",
    ) -> dict[str, Any]:
        """Validate total triangle count against a budget scope.

        Args:
            object_tris: List of triangle counts per visible object.
            scope: Budget scope key ("per_room", "per_block", "per_frame").

        Returns:
            Dict with total_tris, budget info, utilization, over_budget flag,
            and recommendations list.

        Raises:
            ValueError: If scope is not a valid budget key.
        """
        budget = SCENE_BUDGETS.get(scope)
        if budget is None:
            raise ValueError(
                f"Unknown scope '{scope}'. "
                f"Available: {', '.join(sorted(SCENE_BUDGETS.keys()))}"
            )

        total_tris = sum(object_tris)
        max_tris = budget["max_tris"]
        min_tris = budget["min_tris"]
        over_budget = total_tris > max_tris
        utilization_pct = (total_tris / max_tris * 100.0) if max_tris > 0 else 0.0

        recommendations: list[str] = []

        if over_budget:
            excess = total_tris - max_tris
            recommendations.append(
                f"Over budget by {excess:,} tris. "
                f"Need to reduce by {excess / total_tris * 100:.1f}%."
            )
            # Find objects consuming most of the budget
            if object_tris:
                sorted_tris = sorted(enumerate(object_tris), key=lambda x: x[1], reverse=True)
                top_3 = sorted_tris[:3]
                for idx, tris in top_3:
                    pct = tris / total_tris * 100.0
                    if pct > 15.0:
                        recommendations.append(
                            f"Object #{idx} uses {tris:,} tris ({pct:.1f}%) "
                            f"-- consider LOD culling or simplification."
                        )
            recommendations.append(
                "Consider enabling LOD distance culling for distant objects."
            )
            recommendations.append(
                "Consider material consolidation to reduce draw calls."
            )
        elif utilization_pct < 30.0 and total_tris > 0:
            recommendations.append(
                f"Only {utilization_pct:.1f}% of budget used. "
                f"Room for more detail or higher LOD distances."
            )

        return {
            "scope": scope,
            "label": budget["label"],
            "total_tris": total_tris,
            "object_count": len(object_tris),
            "budget_min": min_tris,
            "budget_max": max_tris,
            "utilization_pct": round(utilization_pct, 1),
            "over_budget": over_budget,
            "recommendations": recommendations,
        }

    def validate_all_scopes(
        self,
        object_tris: list[int],
    ) -> list[dict[str, Any]]:
        """Validate against all budget scopes at once.

        Args:
            object_tris: List of triangle counts per visible object.

        Returns:
            List of validation reports, one per scope.
        """
        return [
            self.validate(object_tris, scope)
            for scope in SCENE_BUDGETS
        ]


# ---------------------------------------------------------------------------
# bpy handler: Blender integration
# ---------------------------------------------------------------------------


def handle_generate_lods(params: dict) -> dict:
    """Generate LOD chain with silhouette-preserving decimation in Blender.

    Params:
        object_name (str): Name of the source mesh object.
        asset_type (str): LOD preset key. Default "prop_medium".
        export_dir (str, optional): Directory to export LOD FBX files.

    Returns:
        Dict with source info, LOD objects created, and collision mesh info.
    """
    import bpy

    object_name = params["object_name"]
    asset_type = params.get("asset_type", "prop_medium")

    preset = LOD_PRESETS.get(asset_type)
    if preset is None:
        raise ValueError(
            f"Unknown asset type '{asset_type}'. "
            f"Available: {', '.join(sorted(LOD_PRESETS.keys()))}"
        )

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type '{obj.type}', expected 'MESH'"
        )

    # Extract mesh data from the Blender object
    mesh = obj.data
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]

    mesh_data: MeshData = {"vertices": vertices, "faces": faces}
    source_face_count = len(faces)

    # Generate LOD chain
    lod_chain = generate_lod_chain(mesh_data, asset_type)

    # Generate collision mesh
    col_verts, col_faces = generate_collision_mesh(vertices, faces)

    lod_results: list[dict] = []

    for lod_verts, lod_faces, lod_level in lod_chain:
        lod_name = f"{object_name}_LOD{lod_level}"

        if lod_level == 0:
            # LOD0: rename original
            obj.name = lod_name
            obj.data.name = lod_name
            lod_results.append({
                "name": lod_name,
                "level": lod_level,
                "faces": source_face_count,
                "vertices": len(vertices),
                "ratio": preset["ratios"][lod_level],
                "screen_pct": preset["screen_percentages"][lod_level],
            })
        else:
            # Create new mesh from decimated data
            new_mesh = bpy.data.meshes.new(lod_name)
            new_mesh.from_pydata(lod_verts, [], lod_faces)
            new_mesh.update()

            new_obj = bpy.data.objects.new(lod_name, new_mesh)
            bpy.context.collection.objects.link(new_obj)
            new_obj.location = obj.location
            new_obj.rotation_euler = obj.rotation_euler
            new_obj.scale = obj.scale

            lod_results.append({
                "name": lod_name,
                "level": lod_level,
                "faces": len(lod_faces),
                "vertices": len(lod_verts),
                "ratio": preset["ratios"][lod_level],
                "screen_pct": preset["screen_percentages"][lod_level],
            })

    # Create collision mesh object
    col_name = f"{object_name}_COL"
    col_mesh = bpy.data.meshes.new(col_name)
    col_mesh.from_pydata(col_verts, [], col_faces)
    col_mesh.update()

    col_obj = bpy.data.objects.new(col_name, col_mesh)
    bpy.context.collection.objects.link(col_obj)
    col_obj.location = obj.location
    col_obj.rotation_euler = obj.rotation_euler
    col_obj.scale = obj.scale
    col_obj.display_type = "WIRE"

    return {
        "status": "success",
        "source": object_name,
        "asset_type": asset_type,
        "source_faces": source_face_count,
        "lod_count": len(lod_results),
        "lods": lod_results,
        "collision_mesh": {
            "name": col_name,
            "faces": len(col_faces),
            "vertices": len(col_verts),
        },
        "preset": {
            "ratios": preset["ratios"],
            "screen_percentages": preset["screen_percentages"],
            "min_tris": preset["min_tris"],
            "preserve_regions": preset.get("preserve_regions", []),
        },
    }
