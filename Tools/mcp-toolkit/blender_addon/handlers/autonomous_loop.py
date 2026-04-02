"""Autonomous generate-evaluate-fix loop for mesh quality improvement.

Provides an iterative refinement pipeline that evaluates mesh quality against
configurable AAA targets, selects the most impactful repair action, and
repeats until all targets are met or iteration budget is exhausted.

Pure-logic helpers (no bpy dependency) are separated for testability:
  - evaluate_mesh_quality: Mesh quality metrics from raw geometry
  - select_fix_action: Choose the best repair action for a given quality gap
  - _compute_face_area: Triangle/polygon area from vertex positions
  - _check_manifold_edge: Non-manifold edge detection

Handler function (requires bpy):
  - handle_autonomous_refine: Iterative quality refinement loop in Blender
"""

from __future__ import annotations

import math
from typing import Any

try:
    import bpy
    import bmesh
except ImportError:
    bpy = None  # type: ignore[assignment]
    bmesh = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure-logic quality evaluator (testable without Blender)
# ---------------------------------------------------------------------------


def _compute_face_area(
    vertices: list[tuple[float, float, float]],
    face: tuple[int, ...],
) -> float:
    """Compute the area of a polygon face from vertex positions.

    Uses the cross-product method. Triangulates n-gons by fan triangulation
    from the first vertex.

    Args:
        vertices: Full vertex position list.
        face: Tuple of vertex indices forming the face.

    Returns:
        Face area (non-negative float).
    """
    if len(face) < 3:
        return 0.0

    total_area = 0.0
    v0 = vertices[face[0]]

    for i in range(1, len(face) - 1):
        v1 = vertices[face[i]]
        v2 = vertices[face[i + 1]]

        # Edge vectors from v0
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # Cross product
        cx = e1[1] * e2[2] - e1[2] * e2[1]
        cy = e1[2] * e2[0] - e1[0] * e2[2]
        cz = e1[0] * e2[1] - e1[1] * e2[0]

        total_area += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)

    return total_area


def _compute_face_normal(
    vertices: list[tuple[float, float, float]],
    face: tuple[int, ...],
) -> tuple[float, float, float]:
    """Compute the unit normal of a polygon face.

    Args:
        vertices: Full vertex position list.
        face: Tuple of vertex indices.

    Returns:
        Normalised (nx, ny, nz) face normal. Falls back to (0, 0, 1)
        for degenerate faces.
    """
    if len(face) < 3:
        return (0.0, 0.0, 1.0)

    v0 = vertices[face[0]]
    v1 = vertices[face[1]]
    v2 = vertices[face[2]]

    e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

    nx = e1[1] * e2[2] - e1[2] * e2[1]
    ny = e1[2] * e2[0] - e1[0] * e2[2]
    nz = e1[0] * e2[1] - e1[1] * e2[0]

    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length > 1e-12:
        return (nx / length, ny / length, nz / length)
    return (0.0, 0.0, 1.0)


def evaluate_mesh_quality(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    uvs: list[tuple[float, float]] | None = None,
    normals: list[tuple[float, float, float]] | None = None,
) -> dict[str, Any]:
    """Evaluate mesh quality metrics from raw geometry data.

    Computes a comprehensive quality report without any Blender dependency.
    All inputs are plain Python lists.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples (each at least 3 indices).
        uvs: Optional per-vertex (u, v) UV coordinates.
        normals: Optional per-face (nx, ny, nz) normals.  If not provided,
            normals are computed from face geometry.

    Returns:
        Dict with keys: ``poly_count``, ``vertex_count``, ``face_count``,
        ``has_non_manifold``, ``has_degenerate_faces``,
        ``degenerate_face_count``, ``topology_grade``, ``avg_face_area``,
        ``uv_coverage``, ``normal_consistency``, ``tri_count``,
        ``quad_count``, ``ngon_count``, ``quad_percentage``.
    """
    num_verts = len(vertices)
    num_faces = len(faces)
    poly_count = num_faces  # Each face = 1 polygon

    # --- Face type counts ---
    tri_count = 0
    quad_count = 0
    ngon_count = 0
    for f in faces:
        n = len(f)
        if n == 3:
            tri_count += 1
        elif n == 4:
            quad_count += 1
        elif n > 4:
            ngon_count += 1

    quad_pct = (quad_count / max(num_faces, 1)) * 100.0

    # --- Face areas and degenerate detection ---
    degenerate_epsilon = 1e-8
    face_areas: list[float] = []
    degenerate_count = 0

    for f in faces:
        area = _compute_face_area(vertices, f)
        face_areas.append(area)
        if area < degenerate_epsilon:
            degenerate_count += 1

    avg_face_area = (sum(face_areas) / len(face_areas)) if face_areas else 0.0

    # --- Non-manifold edge detection ---
    # An edge shared by != 2 faces is non-manifold.
    edge_face_count: dict[tuple[int, int], int] = {}
    for f in faces:
        n = len(f)
        for k in range(n):
            v0, v1 = f[k], f[(k + 1) % n]
            key = (min(v0, v1), max(v0, v1))
            edge_face_count[key] = edge_face_count.get(key, 0) + 1

    non_manifold_count = sum(
        1 for count in edge_face_count.values() if count != 2
    )
    has_non_manifold = non_manifold_count > 0

    # --- Normal consistency ---
    if normals is None:
        computed_normals = [_compute_face_normal(vertices, f) for f in faces]
    else:
        computed_normals = list(normals)

    normal_consistency = _compute_normal_consistency(
        faces, computed_normals, edge_face_count
    )

    # --- UV coverage ---
    uv_coverage = 0.0
    if uvs is not None and len(uvs) > 0:
        u_vals = [uv[0] for uv in uvs]
        v_vals = [uv[1] for uv in uvs]
        u_range = max(u_vals) - min(u_vals)
        v_range = max(v_vals) - min(v_vals)
        uv_coverage = u_range * v_range  # Bounding-box area in UV space

    # --- Topology grade ---
    # Simplified grading: A-F based on quad%, ngon%, non-manifold, degenerate
    topology_grade = _compute_topology_grade(
        num_faces=num_faces,
        quad_count=quad_count,
        tri_count=tri_count,
        ngon_count=ngon_count,
        non_manifold_count=non_manifold_count,
        degenerate_count=degenerate_count,
    )

    return {
        "poly_count": poly_count,
        "vertex_count": num_verts,
        "face_count": num_faces,
        "has_non_manifold": has_non_manifold,
        "non_manifold_edge_count": non_manifold_count,
        "has_degenerate_faces": degenerate_count > 0,
        "degenerate_face_count": degenerate_count,
        "topology_grade": topology_grade,
        "avg_face_area": avg_face_area,
        "uv_coverage": uv_coverage,
        "normal_consistency": normal_consistency,
        "tri_count": tri_count,
        "quad_count": quad_count,
        "ngon_count": ngon_count,
        "quad_percentage": quad_pct,
    }


def _compute_normal_consistency(
    faces: list[tuple[int, ...]],
    normals: list[tuple[float, float, float]],
    edge_face_count: dict[tuple[int, int], int],
) -> float:
    """Compute normal consistency as average dot product of adjacent normals.

    Returns a value in [0, 1] where 1.0 means perfectly consistent normals
    and 0.0 means heavily inconsistent (many flipped faces).
    """
    if len(normals) < 2:
        return 1.0

    # Build edge -> face adjacency (only manifold edges: count == 2)
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, f in enumerate(faces):
        n = len(f)
        for k in range(n):
            v0, v1 = f[k], f[(k + 1) % n]
            key = (min(v0, v1), max(v0, v1))
            edge_faces.setdefault(key, []).append(fi)

    dot_sum = 0.0
    pair_count = 0

    for key, face_list in edge_faces.items():
        if len(face_list) != 2:
            continue
        fi_a, fi_b = face_list[0], face_list[1]
        na = normals[fi_a]
        nb = normals[fi_b]
        dot = na[0] * nb[0] + na[1] * nb[1] + na[2] * nb[2]
        # Map dot from [-1, 1] to [0, 1]
        dot_sum += (dot + 1.0) * 0.5
        pair_count += 1

    if pair_count == 0:
        return 1.0

    return dot_sum / pair_count


def _compute_topology_grade(
    num_faces: int,
    quad_count: int,
    tri_count: int,
    ngon_count: int,
    non_manifold_count: int,
    degenerate_count: int,
) -> str:
    """Compute A-F topology grade from mesh statistics.

    Grading (worst-first):
      F: non_manifold > 20 or ngon% > 25 or degenerate% > 10
      E: non_manifold > 5 or ngon% > 10 or degenerate% > 5
      D: non_manifold > 0 or ngon% > 5 or degenerate > 0 or tri% > 40
      C: ngon% > 2 or tri% > 20
      B: ngon% > 0 or tri% > 10
      A: all clean
    """
    if num_faces == 0:
        return "A"

    ngon_pct = (ngon_count / num_faces) * 100.0
    tri_pct = (tri_count / num_faces) * 100.0
    deg_pct = (degenerate_count / num_faces) * 100.0

    if non_manifold_count > 20 or ngon_pct > 25 or deg_pct > 10:
        return "F"
    if non_manifold_count > 5 or ngon_pct > 10 or deg_pct > 5:
        return "E"
    if non_manifold_count > 0 or ngon_pct > 5 or degenerate_count > 0 or tri_pct > 40:
        return "D"
    if ngon_pct > 2 or tri_pct > 20:
        return "C"
    if ngon_pct > 0 or tri_pct > 10:
        return "B"
    return "A"


# ---------------------------------------------------------------------------
# Fix action selector (pure logic)
# ---------------------------------------------------------------------------


def select_fix_action(
    quality: dict[str, Any],
    targets: dict[str, Any],
    available_actions: list[str],
) -> str | None:
    """Select the best fix action based on the gap between quality and targets.

    Examines each quality metric against its target and picks the first
    applicable action from ``available_actions`` that addresses the most
    critical gap.

    Priority order (highest first):
      1. Non-manifold edges present -> ``'repair'``
      2. Degenerate faces present -> ``'repair'``
      3. Over poly budget -> ``'decimate'``
      4. Under poly budget -> ``'subdivide'``
      5. Bad topology grade -> ``'remesh'``
      6. Poor normal consistency -> ``'repair'``
      7. High UV stretch -> ``'uv_unwrap'``
      8. Rough surface -> ``'smooth'``

    Args:
        quality: Output from :func:`evaluate_mesh_quality`.
        targets: Dict of target thresholds. Keys may include:
            ``min_poly_count``, ``max_poly_count``,
            ``min_topology_grade``, ``no_non_manifold``,
            ``no_degenerate_faces``, ``max_stretch_uv``,
            ``min_normal_consistency``.
        available_actions: Ordered list of allowed repair actions:
            ``'repair'``, ``'remesh'``, ``'smooth'``, ``'uv_unwrap'``,
            ``'decimate'``, ``'subdivide'``.

    Returns:
        Best action name, or ``None`` if all targets are met.
    """
    if not available_actions:
        return None

    # Check each gap in priority order and return the first action that
    # both addresses the gap and is in available_actions.

    # 1. Non-manifold edges
    if targets.get("no_non_manifold", False) and quality.get("has_non_manifold", False):
        if "repair" in available_actions:
            return "repair"

    # 2. Degenerate faces
    if targets.get("no_degenerate_faces", False) and quality.get(
        "has_degenerate_faces", False
    ):
        if "repair" in available_actions:
            return "repair"

    # 3. Over poly budget
    max_polys = targets.get("max_poly_count")
    if max_polys is not None and quality.get("poly_count", 0) > max_polys:
        if "decimate" in available_actions:
            return "decimate"

    # 4. Under poly budget
    min_polys = targets.get("min_poly_count")
    if min_polys is not None and quality.get("poly_count", 0) < min_polys:
        if "subdivide" in available_actions:
            return "subdivide"

    # 5. Bad topology grade
    min_grade = targets.get("min_topology_grade")
    if min_grade is not None:
        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
        current_rank = grade_order.get(quality.get("topology_grade", "F"), 5)
        target_rank = grade_order.get(min_grade, 0)
        if current_rank > target_rank:
            if "remesh" in available_actions:
                return "remesh"

    # 6. Poor normal consistency
    min_consistency = targets.get("min_normal_consistency")
    if min_consistency is not None:
        current = quality.get("normal_consistency", 1.0)
        if current < min_consistency:
            if "repair" in available_actions:
                return "repair"

    # 7. UV stretch (lower is better, but uv_coverage < threshold means
    #    UVs need re-unwrapping)
    max_stretch = targets.get("max_stretch_uv")
    if max_stretch is not None:
        current_coverage = quality.get("uv_coverage", 0.0)
        if current_coverage < max_stretch:
            if "uv_unwrap" in available_actions:
                return "uv_unwrap"

    # 8. Rough surface — if grade is worse than target, try smooth
    if min_grade is not None:
        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
        current_rank = grade_order.get(quality.get("topology_grade", "F"), 5)
        target_rank = grade_order.get(min_grade, 0)
        if current_rank > target_rank:
            if "smooth" in available_actions:
                return "smooth"

    # All targets met
    return None


# ---------------------------------------------------------------------------
# Blender handler (requires bpy)
# ---------------------------------------------------------------------------


def handle_autonomous_refine(params: dict[str, Any]) -> dict[str, Any]:
    """Run autonomous generate-evaluate-fix loop for mesh quality improvement.

    Iteratively evaluates a mesh against quality targets and applies repair
    actions until all targets are met or the iteration budget is exhausted.

    Args (via params dict):
        object_name (str): Mesh object to evaluate/refine.
        max_iterations (int): Safety cap on iterations.  Default ``5``.
        quality_targets (dict): Target metrics.  Keys:
            ``min_poly_count``, ``max_poly_count``,
            ``min_topology_grade`` (``'A'``-``'F'``),
            ``no_non_manifold`` (bool), ``no_degenerate_faces`` (bool),
            ``max_stretch_uv`` (float),
            ``min_normal_consistency`` (float, 0-1).
        fix_actions (list[str]): Ordered repair actions to try:
            ``'repair'``, ``'remesh'``, ``'smooth'``, ``'uv_unwrap'``,
            ``'decimate'``, ``'subdivide'``.

    Returns:
        Dict with ``iterations`` log (before/after per step) and final
        quality summary.
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

    max_iterations = int(params.get("max_iterations", 5))
    max_iterations = min(max_iterations, 20)  # Hard safety cap
    quality_targets = params.get("quality_targets", {})
    fix_actions = params.get(
        "fix_actions",
        ["repair", "remesh", "smooth", "uv_unwrap", "decimate", "subdivide"],
    )

    iteration_log: list[dict[str, Any]] = []

    for iteration in range(max_iterations):
        # Extract current mesh data
        mesh_data = _extract_mesh_data(obj)
        quality = evaluate_mesh_quality(**mesh_data)

        # Select fix action
        action = select_fix_action(quality, quality_targets, fix_actions)

        if action is None:
            # All targets met
            iteration_log.append(
                {
                    "iteration": iteration,
                    "quality_before": quality,
                    "action": None,
                    "result": "all_targets_met",
                }
            )
            break

        # Apply the fix action
        fix_result = _apply_fix_action(obj, action, quality, quality_targets)

        # Re-evaluate after fix
        mesh_data_after = _extract_mesh_data(obj)
        quality_after = evaluate_mesh_quality(**mesh_data_after)

        iteration_log.append(
            {
                "iteration": iteration,
                "quality_before": quality,
                "action": action,
                "fix_result": fix_result,
                "quality_after": quality_after,
            }
        )

    # Final evaluation
    final_data = _extract_mesh_data(obj)
    final_quality = evaluate_mesh_quality(**final_data)
    all_met = select_fix_action(final_quality, quality_targets, fix_actions) is None

    return {
        "status": "success",
        "result": {
            "object": object_name,
            "iterations_run": len(iteration_log),
            "max_iterations": max_iterations,
            "all_targets_met": all_met,
            "final_quality": final_quality,
            "iteration_log": iteration_log,
        },
    }


# ---------------------------------------------------------------------------
# Internal Blender helpers
# ---------------------------------------------------------------------------


def _extract_mesh_data(obj: Any) -> dict[str, Any]:
    """Extract vertex/face/UV/normal data from a Blender mesh object."""
    mesh = obj.data
    vertices = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]

    # Normals
    normals_list = [(p.normal.x, p.normal.y, p.normal.z) for p in mesh.polygons]

    # UVs (per-vertex average)
    uvs = None
    if mesh.uv_layers.active is not None:
        uv_layer = mesh.uv_layers.active
        vert_uvs: dict[int, list[tuple[float, float]]] = {}
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                vi = mesh.loops[loop_idx].vertex_index
                uv = uv_layer.data[loop_idx].uv
                vert_uvs.setdefault(vi, []).append((uv.x, uv.y))

        avg_uvs: list[tuple[float, float]] = []
        for vi in range(len(vertices)):
            if vi in vert_uvs:
                u_avg = sum(u for u, _ in vert_uvs[vi]) / len(vert_uvs[vi])
                v_avg = sum(v for _, v in vert_uvs[vi]) / len(vert_uvs[vi])
                avg_uvs.append((u_avg, v_avg))
            else:
                avg_uvs.append((0.0, 0.0))
        uvs = avg_uvs

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs,
        "normals": normals_list,
    }


def _apply_fix_action(
    obj: Any,
    action: str,
    quality: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    """Apply a single fix action to the Blender mesh object.

    Returns a dict describing what was done.
    """
    result: dict[str, Any] = {"action": action}

    if action == "repair":
        result.update(_do_repair(obj))
    elif action == "remesh":
        result.update(_do_remesh(obj, quality, targets))
    elif action == "smooth":
        result.update(_do_smooth(obj))
    elif action == "uv_unwrap":
        result.update(_do_uv_unwrap(obj))
    elif action == "decimate":
        result.update(_do_decimate(obj, quality, targets))
    elif action == "subdivide":
        result.update(_do_subdivide(obj))
    else:
        result["error"] = f"Unknown action: {action}"

    return result


def _do_repair(obj: Any) -> dict[str, Any]:
    """Remove doubles, recalculate normals, fill small holes."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Remove doubles
    removed = bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    merged_count = len(removed.get("verts", []))  # type: ignore[union-attr]

    # Recalculate normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    return {"merged_vertices": merged_count, "normals_recalculated": True}


def _do_remesh(
    obj: Any, quality: dict[str, Any], targets: dict[str, Any]
) -> dict[str, Any]:
    """Voxel remesh for clean topology."""
    # Estimate voxel size from object dimensions
    dims = obj.dimensions
    max_dim = max(dims.x, dims.y, dims.z, 0.1)
    target_polys = targets.get("max_poly_count", quality.get("poly_count", 5000))
    # Rough estimate: voxel_size ~ max_dim / sqrt(target_polys / 6)
    voxel_size = max_dim / max(math.sqrt(target_polys / 6.0), 1.0)
    voxel_size = max(voxel_size, 0.01)

    mod = obj.modifiers.new(name="VB_Remesh", type="REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel_size
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    return {"voxel_size": voxel_size}


def _do_smooth(obj: Any) -> dict[str, Any]:
    """Laplacian smooth pass."""
    mod = obj.modifiers.new(name="VB_Smooth", type="LAPLACIANSMOOTH")
    mod.iterations = 2
    mod.lambda_factor = 1.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    return {"iterations": 2, "lambda": 1.0}


def _do_uv_unwrap(obj: Any) -> dict[str, Any]:
    """Smart UV project re-unwrap."""
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    finally:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

    return {"method": "smart_project", "angle_limit": 66.0}


def _do_decimate(
    obj: Any, quality: dict[str, Any], targets: dict[str, Any]
) -> dict[str, Any]:
    """Decimate to meet poly budget."""
    current_polys = quality.get("poly_count", len(obj.data.polygons))
    target_polys = targets.get("max_poly_count", current_polys)
    if current_polys > 0:
        ratio = max(0.1, min(1.0, target_polys / current_polys))
    else:
        ratio = 1.0

    mod = obj.modifiers.new(name="VB_Decimate", type="DECIMATE")
    mod.ratio = ratio
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    return {"ratio": ratio, "target_polys": target_polys}


def _do_subdivide(obj: Any) -> dict[str, Any]:
    """Subdivide to increase detail."""
    mod = obj.modifiers.new(name="VB_Subdivide", type="SUBSURF")
    mod.levels = 1
    mod.render_levels = 1
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    return {"levels": 1}
