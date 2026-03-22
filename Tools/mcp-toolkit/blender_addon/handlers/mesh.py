"""Mesh topology analysis, auto-repair, game-readiness, and editing handlers.

Provides:
- handle_analyze_topology: Full topology analysis with A-F grading (MESH-01)
- handle_auto_repair: Chained repair pipeline via bmesh.ops (MESH-02)
- handle_check_game_ready: Composite game-readiness validation (MESH-08)
- handle_select_geometry: Selection engine by material/vertex group/normal/loose (MESH-03)
- handle_edit_mesh: Surgical edits -- extrude, inset, mirror, separate, join (MESH-06)
- handle_boolean_op: Boolean operations -- union, difference, intersect (MESH-05)
- handle_retopologize: Retopology via quadriflow with target face count (MESH-07)
- handle_sculpt: Sculpt operations -- smooth, inflate, flatten, crease (MESH-04)

Analysis uses bmesh for direct geometry access. Editing uses bmesh where possible,
falls back to bpy.ops with temp_override for boolean, retopology, and sculpt filters.
"""

from __future__ import annotations

import math
import re

import bmesh
import bpy
import mathutils

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------

# Default Blender object names that indicate the asset hasn't been renamed.
_DEFAULT_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Cube(\.\d+)?$"),
    re.compile(r"^Sphere(\.\d+)?$"),
    re.compile(r"^Cylinder(\.\d+)?$"),
    re.compile(r"^Plane(\.\d+)?$"),
    re.compile(r"^Cone(\.\d+)?$"),
    re.compile(r"^Torus(\.\d+)?$"),
    re.compile(r"^Circle(\.\d+)?$"),
    re.compile(r"^Icosphere(\.\d+)?$"),
    re.compile(r"^Monkey(\.\d+)?$"),
    re.compile(r"^Grid(\.\d+)?$"),
]

# Transform tolerance for "applied" check.
_LOC_TOLERANCE = 0.001
_ROT_TOLERANCE = 0.001
_SCALE_TOLERANCE = 0.01


def _compute_grade(metrics: dict) -> str:
    """Compute A-F topology grade from analysis metrics.

    Grading thresholds from 02-RESEARCH.md (worst-first evaluation):
      F: nm>20 or ngon%>25 or pole%>50 or loose>50
      E: nm>5  or ngon%>10 or pole%>30 or loose>10
      D: nm>0  or ngon%>5  or pole%>20 or loose>0 or tri%>40
      C: ngon%>2 or pole%>10 or tri%>20
      B: ngon%>0 or pole%>5  or tri%>10
      A: everything else
    """
    total_faces = max(metrics["face_count"], 1)
    total_verts = max(metrics["vertex_count"], 1)
    ngon_pct = metrics["ngon_percentage"]
    nm = metrics["non_manifold_edges"]
    pole_pct = metrics["pole_count"] / total_verts * 100
    loose = metrics["loose_vertices"] + metrics["loose_edges"]
    tri_pct = metrics["tri_count"] / total_faces * 100

    # Grade from worst to best -- first failing threshold sets grade.
    if nm > 20 or ngon_pct > 25 or pole_pct > 50 or loose > 50:
        return "F"
    if nm > 5 or ngon_pct > 10 or pole_pct > 30 or loose > 10:
        return "E"
    if nm > 0 or ngon_pct > 5 or pole_pct > 20 or loose > 0 or tri_pct > 40:
        return "D"
    if ngon_pct > 2 or pole_pct > 10 or tri_pct > 20:
        return "C"
    if ngon_pct > 0 or pole_pct > 5 or tri_pct > 10:
        return "B"
    return "A"


def _list_issues(m: dict) -> list[str]:
    """Generate human-readable issue list from topology metrics."""
    issues: list[str] = []
    if m["non_manifold_edges"] > 0:
        issues.append(
            f"{m['non_manifold_edges']} non-manifold edges "
            "(will cause rendering artifacts)"
        )
    if m["ngon_count"] > 0:
        issues.append(
            f"{m['ngon_count']} n-gons ({m['ngon_percentage']}% of faces)"
        )
    if m["loose_vertices"] > 0:
        issues.append(f"{m['loose_vertices']} loose vertices")
    if m["loose_edges"] > 0:
        issues.append(f"{m['loose_edges']} loose edges (wire geometry)")
    if m["pole_count"] > m["vertex_count"] * 0.1:
        issues.append(
            f"{m['pole_count']} poles "
            f"({m['e_poles']} E-poles, {m['n_poles']} N-poles)"
        )
    return issues


def _is_default_name(name: str) -> bool:
    """Return True if *name* matches a default Blender object name."""
    return any(pat.match(name) for pat in _DEFAULT_NAME_PATTERNS)


# ---------------------------------------------------------------------------
# Pure-logic helpers for mesh editing (testable without Blender)
# ---------------------------------------------------------------------------

# Selection criteria keys recognised by handle_select_geometry.
_SELECTION_KEYS = frozenset({
    "material_index",
    "material_name",
    "vertex_group",
    "face_normal_direction",
    "normal_threshold",
    "loose_parts",
    "position_box",
    "position_sphere",
    "position_plane",
})

# Valid edit operations for handle_edit_mesh.
_EDIT_OPERATIONS = frozenset({
    "extrude", "inset", "mirror", "separate", "join",
    "move", "rotate", "scale",
    "loop_cut",
    "bevel",
    "merge_vertices", "dissolve_edges", "dissolve_faces",
})

# Valid sculpt operations for handle_sculpt.
_SCULPT_OPERATIONS = {
    "smooth": None,           # uses bmesh, no sculpt filter
    "inflate": "INFLATE",
    "flatten": "SURFACE_SMOOTH",
    "crease": "SHARPEN",
}

_AXIS_MAP = {"X": 0, "Y": 1, "Z": 2}


def _parse_selection_criteria(params: dict) -> dict:
    """Extract selection criteria from params, ignoring non-criteria keys.

    Returns dict with only the recognised selection keys that are present
    in *params*.  For ``face_normal_direction`` without an explicit
    ``normal_threshold``, the default 0.7 is injected.
    """
    criteria: dict = {}
    for key in _SELECTION_KEYS:
        if key in params:
            criteria[key] = params[key]
    # Inject default threshold when direction given without one.
    if "face_normal_direction" in criteria and "normal_threshold" not in criteria:
        criteria["normal_threshold"] = 0.7
    return criteria


def _validate_edit_operation(operation: str) -> None:
    """Raise ``ValueError`` if *operation* is not a known edit operation."""
    if operation not in _EDIT_OPERATIONS:
        raise ValueError(
            f"Unknown edit operation: {operation!r}. "
            f"Valid: {sorted(_EDIT_OPERATIONS)}"
        )


def _axis_to_index(axis: str) -> int:
    """Convert axis letter (X/Y/Z, case-insensitive) to integer index (0/1/2)."""
    idx = _AXIS_MAP.get(axis.upper())
    if idx is None:
        raise ValueError(f"Invalid axis: {axis!r}. Valid: X, Y, Z")
    return idx


def _sculpt_operation_to_filter_type(operation: str) -> str | None:
    """Map sculpt operation name to Blender mesh_filter type.

    Returns ``None`` for ``"smooth"`` (handled via bmesh, not sculpt mode).
    Raises ``ValueError`` for unknown operations.
    """
    if operation not in _SCULPT_OPERATIONS:
        raise ValueError(
            f"Unknown sculpt operation: {operation!r}. "
            f"Valid: {sorted(_SCULPT_OPERATIONS)}"
        )
    return _SCULPT_OPERATIONS[operation]


# ---------------------------------------------------------------------------
# Pure-logic helpers for position-based selection (testable without Blender)
# ---------------------------------------------------------------------------


def _select_by_box(verts_coords: list[tuple[float, float, float]],
                   box_min: tuple[float, float, float],
                   box_max: tuple[float, float, float]) -> list[int]:
    """Return indices of vertices inside an axis-aligned bounding box.

    Args:
        verts_coords: List of (x, y, z) tuples for each vertex.
        box_min: (min_x, min_y, min_z) corner.
        box_max: (max_x, max_y, max_z) corner.

    Returns:
        List of vertex indices inside the box.
    """
    selected: list[int] = []
    for i, co in enumerate(verts_coords):
        if (box_min[0] <= co[0] <= box_max[0]
                and box_min[1] <= co[1] <= box_max[1]
                and box_min[2] <= co[2] <= box_max[2]):
            selected.append(i)
    return selected


def _select_by_sphere(verts_coords: list[tuple[float, float, float]],
                      center: tuple[float, float, float],
                      radius: float) -> list[int]:
    """Return indices of vertices within a sphere.

    Args:
        verts_coords: List of (x, y, z) tuples for each vertex.
        center: (cx, cy, cz) sphere center.
        radius: Sphere radius.

    Returns:
        List of vertex indices within the sphere.
    """
    r_sq = radius * radius
    selected: list[int] = []
    for i, co in enumerate(verts_coords):
        dx = co[0] - center[0]
        dy = co[1] - center[1]
        dz = co[2] - center[2]
        if dx * dx + dy * dy + dz * dz <= r_sq:
            selected.append(i)
    return selected


def _select_by_plane(verts_coords: list[tuple[float, float, float]],
                     plane_point: tuple[float, float, float],
                     plane_normal: tuple[float, float, float],
                     side: str = "above") -> list[int]:
    """Return indices of vertices on one side of a plane.

    The plane is defined by a point and a normal vector. "above" means
    vertices on the side the normal points to (dot product >= 0).

    Args:
        verts_coords: List of (x, y, z) tuples for each vertex.
        plane_point: A point on the plane.
        plane_normal: The plane normal direction (does not need to be normalized).
        side: "above" (default) or "below".

    Returns:
        List of vertex indices on the specified side.
    """
    # Normalize the normal
    nx, ny, nz = plane_normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-10:
        return []
    nx /= length
    ny /= length
    nz /= length

    selected: list[int] = []
    for i, co in enumerate(verts_coords):
        # Signed distance from plane
        dist = ((co[0] - plane_point[0]) * nx
                + (co[1] - plane_point[1]) * ny
                + (co[2] - plane_point[2]) * nz)
        if side == "above" and dist >= 0:
            selected.append(i)
        elif side == "below" and dist < 0:
            selected.append(i)
    return selected


def _evaluate_game_readiness(
    *,
    topology_result: dict,
    object_name: str,
    poly_budget: int,
    has_uv: bool,
    has_material: bool,
    location: tuple[float, float, float],
    rotation: tuple[float, float, float],
    scale: tuple[float, float, float],
) -> dict:
    """Evaluate game-readiness from pre-computed data (testable without Blender).

    Returns structured dict with per-check pass/fail and overall game_ready bool.
    """
    grade = topology_result["grade"]
    tri_count = topology_result["tri_count"]
    quad_count = topology_result["quad_count"]
    ngon_count = topology_result["ngon_count"]

    # Estimated triangle count for the game engine (quads split, ngons fan-triangulated).
    estimated_tris = tri_count + quad_count * 2 + ngon_count * 3

    # --- Sub-checks ---
    topology_pass = grade in ("A", "B", "C")
    budget_pass = estimated_tris <= poly_budget
    uv_pass = has_uv
    material_pass = has_material
    naming_pass = not _is_default_name(object_name)

    loc_ok = all(abs(v) < _LOC_TOLERANCE for v in location)
    rot_ok = all(abs(v) < _ROT_TOLERANCE for v in rotation)
    scale_ok = all(abs(v - 1.0) < _SCALE_TOLERANCE for v in scale)
    transform_pass = loc_ok and rot_ok and scale_ok

    game_ready = all([
        topology_pass, budget_pass, uv_pass,
        material_pass, naming_pass, transform_pass,
    ])

    checks = {
        "topology": {
            "passed": topology_pass,
            "grade": grade,
            "detail": f"Grade {grade}" + ("" if topology_pass else " (need C or better)"),
        },
        "poly_budget": {
            "passed": budget_pass,
            "estimated_tris": estimated_tris,
            "budget": poly_budget,
            "detail": f"{estimated_tris:,} / {poly_budget:,} tris",
        },
        "uv": {
            "passed": uv_pass,
            "detail": "UV layer present" if uv_pass else "No UV layer found",
        },
        "materials": {
            "passed": material_pass,
            "detail": "Material assigned" if material_pass else "No material slots",
        },
        "naming": {
            "passed": naming_pass,
            "detail": object_name if naming_pass else f"'{object_name}' is a default Blender name",
        },
        "transform": {
            "passed": transform_pass,
            "detail": "Transforms applied" if transform_pass else "Unapplied transforms detected",
        },
    }

    failed = [k for k, v in checks.items() if not v["passed"]]
    if game_ready:
        summary = "All checks passed -- asset is game-ready"
    else:
        summary = f"Failed checks: {', '.join(failed)}"

    return {
        "object_name": object_name,
        "game_ready": game_ready,
        "checks": checks,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy + bmesh at runtime)
# ---------------------------------------------------------------------------


def _analyze_mesh(obj: object) -> dict:
    """Run full topology analysis on a Blender mesh object.

    Returns raw metrics dict (used by handle_analyze_topology and _quick_grade).
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        total_verts = len(bm.verts)
        total_edges = len(bm.edges)
        total_faces = len(bm.faces)

        # Non-manifold edges
        non_manifold_edges = [e for e in bm.edges if not e.is_manifold]

        # Face type counts
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        tris = [f for f in bm.faces if len(f.verts) == 3]
        quads = [f for f in bm.faces if len(f.verts) == 4]

        # Poles (non-4-valence interior vertices)
        e_poles = [v for v in bm.verts if len(v.link_edges) == 3 and not v.is_boundary]
        n_poles = [v for v in bm.verts if len(v.link_edges) >= 5 and not v.is_boundary]

        # Loose geometry
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]

        # Boundary edges
        boundary_edges = [e for e in bm.edges if e.is_boundary]

        # Edge flow: average face angle at edges with 2 linked faces
        edge_angles: list[float] = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                angle = e.link_faces[0].normal.angle(e.link_faces[1].normal)
                edge_angles.append(math.degrees(angle))

    finally:
        bm.free()

    metrics = {
        "object_name": obj.name,
        "vertex_count": total_verts,
        "edge_count": total_edges,
        "face_count": total_faces,
        "tri_count": len(tris),
        "quad_count": len(quads),
        "ngon_count": len(ngons),
        "ngon_percentage": round(len(ngons) / max(total_faces, 1) * 100, 1),
        "non_manifold_edges": len(non_manifold_edges),
        "boundary_edges": len(boundary_edges),
        "e_poles": len(e_poles),
        "n_poles": len(n_poles),
        "pole_count": len(e_poles) + len(n_poles),
        "loose_vertices": len(loose_verts),
        "loose_edges": len(loose_edges),
        "avg_edge_angle": round(
            sum(edge_angles) / max(len(edge_angles), 1), 1
        ),
        "max_edge_angle": round(max(edge_angles) if edge_angles else 0, 1),
    }
    metrics["grade"] = _compute_grade(metrics)
    metrics["issues"] = _list_issues(metrics)
    return metrics


def _quick_grade(obj: object) -> str:
    """Return just the topology grade for an object (used after repair)."""
    return _analyze_mesh(obj)["grade"]


def handle_analyze_topology(params: dict) -> dict:
    """Full topology analysis with A-F grading (MESH-01).

    Params:
        object_name: Name of the Blender mesh object to analyze.

    Returns dict with all topology metrics, grade, and issues list.
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    return _analyze_mesh(obj)


def handle_auto_repair(params: dict) -> dict:
    """Auto-repair pipeline: chained bmesh.ops in optimal order (MESH-02).

    Params:
        object_name: Name of the Blender mesh object to repair.
        merge_distance: Distance threshold for remove_doubles (default 0.0001).
        max_hole_sides: Maximum sides for hole filling (default 8).

    Repair order (matters -- see 02-RESEARCH.md):
      1. Remove loose verts
      2. Remove loose edges
      3. Dissolve degenerate
      4. Remove doubles
      5. Recalculate normals
      6. Fill holes
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    merge_distance = params.get("merge_distance", 0.0001)
    max_hole_sides = params.get("max_hole_sides", 8)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        report: dict = {}

        # 1. Remove loose vertices (no edges)
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
            report["removed_loose_verts"] = len(loose_verts)
        else:
            report["removed_loose_verts"] = 0

        # 2. Remove loose edges (no faces)
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
            report["removed_loose_edges"] = len(loose_edges)
        else:
            report["removed_loose_edges"] = 0

        # 3. Dissolve degenerate (zero-area faces, zero-length edges)
        result = bmesh.ops.dissolve_degenerate(
            bm, dist=0.0001, edges=bm.edges[:]
        )
        report["dissolved_degenerate"] = len(result.get("region", []))

        # 4. Remove doubles (merge by distance)
        result = bmesh.ops.remove_doubles(
            bm, verts=bm.verts[:], dist=merge_distance
        )
        report["merged_vertices"] = len(result.get("targetmap", {}))

        # 5. Recalculate normals (make consistent outward)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        report["normals_recalculated"] = True

        # 6. Fill holes (boundary edges)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        if boundary_edges:
            result = bmesh.ops.holes_fill(
                bm, edges=boundary_edges, sides=max_hole_sides
            )
            report["holes_filled"] = len(result.get("faces", []))
        else:
            report["holes_filled"] = 0

        # Write back to mesh
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    # Re-analyze to confirm repair effectiveness
    report["post_repair_grade"] = _quick_grade(obj)
    report["object_name"] = name
    return report


def handle_check_game_ready(params: dict) -> dict:
    """Composite game-readiness validation (MESH-08).

    Params:
        object_name: Name of the Blender mesh object to check.
        poly_budget: Maximum triangle count allowed (default 50000).
        platform: Target platform -- "pc", "mobile", or "console" (default "pc").

    Checks: topology grade, poly budget, UV presence, materials, naming, transforms.
    """
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    poly_budget = params.get("poly_budget", 50000)
    # platform is accepted for future budget presets but not used yet
    # params.get("platform", "pc")

    # Run topology analysis
    topology_result = _analyze_mesh(obj)

    # Check UV layer
    has_uv = bool(obj.data.uv_layers)

    # Check materials
    has_material = len(obj.data.materials) > 0

    # Extract transforms
    location = tuple(obj.location)
    rotation = tuple(obj.rotation_euler)
    scale = tuple(obj.scale)

    return _evaluate_game_readiness(
        topology_result=topology_result,
        object_name=obj.name,
        poly_budget=poly_budget,
        has_uv=has_uv,
        has_material=has_material,
        location=location,
        rotation=rotation,
        scale=scale,
    )


# ---------------------------------------------------------------------------
# Mesh editing handlers (Plan 02-03)
# ---------------------------------------------------------------------------


def _get_mesh_object(name: str | None) -> object:
    """Validate and return a mesh object by name."""
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")
    return obj


def handle_select_geometry(params: dict) -> dict:
    """Select geometry by material, vertex group, face normal, position, or loose parts (MESH-03, GAP-01).

    Params:
        object_name: Name of the Blender mesh object.
        material_index: Select faces with this material slot index.
        material_name: Select faces with this material name (resolved to index).
        vertex_group: Select vertices in this vertex group (and their linked faces).
        face_normal_direction: [x, y, z] direction vector for face normal selection.
        normal_threshold: Dot-product threshold for normal selection (default 0.7).
        loose_parts: If True, select vertices with no linked faces.
        position_box: {"min": [x,y,z], "max": [x,y,z]} -- select verts in bounding box.
        position_sphere: {"center": [x,y,z], "radius": r} -- select verts in sphere.
        position_plane: {"point": [x,y,z], "normal": [x,y,z], "side": "above"|"below"}.

    Returns dict with selection counts and criteria used.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    criteria = _parse_selection_criteria(params)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Deselect all
        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for f in bm.faces:
            f.select = False

        # --- Material selection ---
        mat_idx = criteria.get("material_index")
        mat_name = criteria.get("material_name")
        if mat_name is not None and mat_idx is None:
            # Resolve material name to index
            idx = obj.data.materials.find(mat_name)
            if idx >= 0:
                mat_idx = idx
        if mat_idx is not None:
            for f in bm.faces:
                if f.material_index == mat_idx:
                    f.select = True
                    for v in f.verts:
                        v.select = True
                    for e in f.edges:
                        e.select = True

        # --- Vertex group selection ---
        vg_name = criteria.get("vertex_group")
        if vg_name is not None:
            vg = obj.vertex_groups.get(vg_name)
            if vg is not None:
                deform_layer = bm.verts.layers.deform.active
                if deform_layer is not None:
                    group_idx = vg.index
                    for v in bm.verts:
                        weights = v[deform_layer]
                        if group_idx in weights and weights[group_idx] > 0.0:
                            v.select = True
                    # Select faces where all verts are selected
                    for f in bm.faces:
                        if all(v.select for v in f.verts):
                            f.select = True
                            for e in f.edges:
                                e.select = True

        # --- Face normal direction selection ---
        normal_dir = criteria.get("face_normal_direction")
        if normal_dir is not None:
            threshold = criteria.get("normal_threshold", 0.7)
            direction = mathutils.Vector(normal_dir).normalized()
            for f in bm.faces:
                if f.normal.dot(direction) > threshold:
                    f.select = True
                    for v in f.verts:
                        v.select = True
                    for e in f.edges:
                        e.select = True

        # --- Loose parts selection ---
        if criteria.get("loose_parts"):
            for v in bm.verts:
                if len(v.link_faces) == 0:
                    v.select = True

        # --- Position-based selection: bounding box ---
        pos_box = criteria.get("position_box")
        if pos_box is not None:
            box_min = tuple(pos_box["min"])
            box_max = tuple(pos_box["max"])
            coords = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            for idx in _select_by_box(coords, box_min, box_max):
                bm.verts[idx].select = True
            # Select edges/faces where all verts are selected
            for e in bm.edges:
                if all(v.select for v in e.verts):
                    e.select = True
            for f in bm.faces:
                if all(v.select for v in f.verts):
                    f.select = True

        # --- Position-based selection: sphere ---
        pos_sphere = criteria.get("position_sphere")
        if pos_sphere is not None:
            center = tuple(pos_sphere["center"])
            radius = float(pos_sphere["radius"])
            coords = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            for idx in _select_by_sphere(coords, center, radius):
                bm.verts[idx].select = True
            for e in bm.edges:
                if all(v.select for v in e.verts):
                    e.select = True
            for f in bm.faces:
                if all(v.select for v in f.verts):
                    f.select = True

        # --- Position-based selection: plane ---
        pos_plane = criteria.get("position_plane")
        if pos_plane is not None:
            plane_point = tuple(pos_plane["point"])
            plane_normal = tuple(pos_plane["normal"])
            side = pos_plane.get("side", "above")
            coords = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            for idx in _select_by_plane(coords, plane_point, plane_normal, side):
                bm.verts[idx].select = True
            for e in bm.edges:
                if all(v.select for v in e.verts):
                    e.select = True
            for f in bm.faces:
                if all(v.select for v in f.verts):
                    f.select = True

        # Count selections
        selected_verts = sum(1 for v in bm.verts if v.select)
        selected_edges = sum(1 for e in bm.edges if e.select)
        selected_faces = sum(1 for f in bm.faces if f.select)

        # Write selection state back
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    return {
        "object_name": name,
        "selected_verts": selected_verts,
        "selected_edges": selected_edges,
        "selected_faces": selected_faces,
        "criteria_used": criteria,
    }


def handle_edit_mesh(params: dict) -> dict:
    """Surgical mesh editing with extended operations (MESH-06, GAP-02/03/04/05).

    Params:
        object_name: Name of the Blender mesh object.
        operation: One of "extrude", "inset", "mirror", "separate", "join",
            "move", "rotate", "scale", "loop_cut", "bevel",
            "merge_vertices", "dissolve_edges", "dissolve_faces".
        offset: [x, y, z] for extrude or move.
        thickness: Inset thickness (default 0.1).
        depth: Inset depth (default 0.0).
        axis: Mirror/rotate axis -- "X", "Y", or "Z" (default "X").
        separate_type: "SELECTED", "MATERIAL", or "LOOSE" (default "SELECTED").
        object_names: List of object names to join into the target.
        angle: Rotation angle in degrees (for rotate).
        center: [x,y,z] rotation/scale center (default: selection center).
        factor: Scale factor -- float or [x,y,z] (for scale).
        edge_index: Edge index for loop_cut (optional).
        cuts: Number of cuts for loop_cut (default 1).
        width: Bevel width (default 0.1).
        segments: Bevel segments 1-10 (default 1).
        profile: Bevel profile 0.0-1.0 (default 0.5).
        merge_type: "CENTER", "FIRST", "LAST", "COLLAPSE" (for merge_vertices).

    Returns dict with post-operation vertex/face counts.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    operation = params.get("operation")
    _validate_edit_operation(operation)

    if operation == "extrude":
        offset = params.get("offset", [0, 0, 0.5])
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            selected_faces = [f for f in bm.faces if f.select]
            if not selected_faces:
                raise ValueError("No faces selected for extrude. Run 'select' first.")

            result = bmesh.ops.extrude_face_region(bm, geom=selected_faces)
            # Find extruded verts and translate
            extruded_verts = [
                g for g in result["geom"]
                if isinstance(g, bmesh.types.BMVert)
            ]
            bmesh.ops.translate(
                bm,
                verts=extruded_verts,
                vec=mathutils.Vector(offset),
            )

            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "inset":
        thickness = params.get("thickness", 0.1)
        depth = params.get("depth", 0.0)
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            selected_faces = [f for f in bm.faces if f.select]
            if not selected_faces:
                raise ValueError("No faces selected for inset. Run 'select' first.")

            bmesh.ops.inset_region(
                bm,
                faces=selected_faces,
                thickness=thickness,
                depth=depth,
            )

            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "mirror":
        axis = params.get("axis", "X")
        axis_idx = _axis_to_index(axis)
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            all_geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.mirror(
                bm,
                geom=all_geom,
                axis=axis_idx,
                mirror_u=True,
                mirror_v=True,
            )

            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "separate":
        separate_type = params.get("separate_type", "SELECTED")
        ctx = get_3d_context_override()
        if ctx is None:
            raise RuntimeError("No 3D Viewport available for separate operation")

        # Ensure object mode first, then switch to edit mode
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.separate(type=separate_type)
            bpy.ops.object.mode_set(mode="OBJECT")

        vert_count = len(obj.data.vertices)
        face_count = len(obj.data.polygons)

    elif operation == "join":
        object_names = params.get("object_names", [])
        if not object_names:
            raise ValueError("No object_names provided for join operation")

        ctx = get_3d_context_override()
        if ctx is None:
            raise RuntimeError("No 3D Viewport available for join operation")

        # Deselect all first
        for o in bpy.data.objects:
            o.select_set(False)

        # Select all objects to join
        for join_name in object_names:
            join_obj = bpy.data.objects.get(join_name)
            if join_obj and join_obj.type == "MESH":
                join_obj.select_set(True)

        # Set target as active and selected
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        with bpy.context.temp_override(**ctx):
            bpy.ops.object.join()

        vert_count = len(obj.data.vertices)
        face_count = len(obj.data.polygons)

    # --- GAP-02: Transform selected geometry ---

    elif operation == "move":
        move_offset = params.get("offset", [0, 0, 0])
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if not selected:
                raise ValueError("No vertices selected for move. Run 'select' first.")
            bmesh.ops.translate(bm, verts=selected, vec=mathutils.Vector(move_offset))
            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "rotate":
        angle_deg = params.get("angle", 0.0)
        rot_axis = params.get("axis", "Z")
        center = params.get("center")
        angle_rad = math.radians(angle_deg)

        # Build rotation matrix around the specified axis
        axis_vectors = {
            "X": mathutils.Vector((1, 0, 0)),
            "Y": mathutils.Vector((0, 1, 0)),
            "Z": mathutils.Vector((0, 0, 1)),
        }
        rot_vec = axis_vectors.get(rot_axis.upper())
        if rot_vec is None:
            raise ValueError(f"Invalid axis: {rot_axis!r}. Valid: X, Y, Z")

        rot_matrix = mathutils.Matrix.Rotation(angle_rad, 4, rot_vec)

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if not selected:
                raise ValueError("No vertices selected for rotate. Run 'select' first.")

            # Determine rotation center
            if center is not None:
                cent = mathutils.Vector(center)
            else:
                # Average position of selected verts
                cent = mathutils.Vector((0, 0, 0))
                for v in selected:
                    cent += v.co
                cent /= len(selected)

            bmesh.ops.rotate(
                bm,
                verts=selected,
                cent=cent,
                matrix=rot_matrix,
            )
            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "scale":
        scale_factor = params.get("factor", [1, 1, 1])
        center = params.get("center")
        if isinstance(scale_factor, (int, float)):
            scale_factor = [scale_factor, scale_factor, scale_factor]

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if not selected:
                raise ValueError("No vertices selected for scale. Run 'select' first.")

            # Determine scale center
            if center is not None:
                cent = mathutils.Vector(center)
            else:
                cent = mathutils.Vector((0, 0, 0))
                for v in selected:
                    cent += v.co
                cent /= len(selected)

            # bmesh.ops.scale expects vec= and space= matrix
            # We translate to origin, scale, translate back
            bmesh.ops.scale(
                bm,
                vec=mathutils.Vector(scale_factor),
                verts=selected,
                space=mathutils.Matrix.Translation(-cent),
            )
            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    # --- GAP-03: Edge Loop Insertion ---

    elif operation == "loop_cut":
        cuts = params.get("cuts", 1)
        edge_index = params.get("edge_index")
        loop_axis = params.get("axis", "X").upper()

        ctx = get_3d_context_override()
        if ctx is None:
            raise RuntimeError("No 3D Viewport available for loop_cut operation")

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        if edge_index is not None:
            # Use operator with specific edge
            with bpy.context.temp_override(**ctx):
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.loopcut_slide(
                    MESH_OT_loopcut={
                        "number_cuts": cuts,
                        "edge_index": edge_index,
                    },
                    TRANSFORM_OT_edge_slide={"value": 0.0},
                )
                bpy.ops.object.mode_set(mode="OBJECT")
        else:
            # Fallback: subdivide selected edges
            bm = bmesh.new()
            try:
                bm.from_mesh(obj.data)
                bm.edges.ensure_lookup_table()
                selected_edges = [e for e in bm.edges if e.select]
                if not selected_edges:
                    # Select edges aligned with the given axis
                    axis_idx = _axis_to_index(loop_axis)
                    for e in bm.edges:
                        v0 = e.verts[0].co
                        v1 = e.verts[1].co
                        diff = [abs(v1[i] - v0[i]) for i in range(3)]
                        # Edge is primarily along this axis
                        if diff[axis_idx] > max(
                            d for i, d in enumerate(diff) if i != axis_idx
                        ) * 0.5:
                            selected_edges.append(e)
                if selected_edges:
                    bmesh.ops.subdivide_edges(
                        bm, edges=selected_edges, cuts=cuts,
                    )
                bm.to_mesh(obj.data)
                obj.data.update()
                vert_count = len(bm.verts)
                face_count = len(bm.faces)
            finally:
                bm.free()
            return {
                "object_name": name,
                "operation": operation,
                "vertex_count": vert_count,
                "face_count": face_count,
            }

        vert_count = len(obj.data.vertices)
        face_count = len(obj.data.polygons)

    # --- GAP-04: Bevel ---

    elif operation == "bevel":
        width = params.get("width", 0.1)
        segments = max(1, min(params.get("segments", 1), 10))
        profile = max(0.0, min(params.get("profile", 0.5), 1.0))
        clamp_overlap = params.get("clamp_overlap", True)

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            selected_verts = [v for v in bm.verts if v.select]
            selected_edges = [e for e in bm.edges if e.select]

            if not selected_verts and not selected_edges:
                raise ValueError(
                    "No geometry selected for bevel. Run 'select' first."
                )

            # Prefer edge bevel, fall back to vertex bevel
            if selected_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=selected_edges,
                    offset=width,
                    offset_type="OFFSET",
                    segments=segments,
                    profile=profile,
                    affect="EDGES",
                    clamp_overlap=clamp_overlap,
                )
            else:
                bmesh.ops.bevel(
                    bm,
                    geom=selected_verts,
                    offset=width,
                    offset_type="OFFSET",
                    segments=segments,
                    profile=profile,
                    affect="VERTICES",
                    clamp_overlap=clamp_overlap,
                )

            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    # --- GAP-05: Vertex Merge / Edge Dissolve / Face Dissolve ---

    elif operation == "merge_vertices":
        merge_type = params.get("merge_type", "CENTER").upper()
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if len(selected) < 2:
                raise ValueError(
                    "Need at least 2 selected vertices for merge."
                )

            if merge_type == "CENTER":
                # Calculate center
                center = mathutils.Vector((0, 0, 0))
                for v in selected:
                    center += v.co
                center /= len(selected)
                # Move all to center, then remove doubles
                for v in selected:
                    v.co = center
                bmesh.ops.remove_doubles(bm, verts=selected, dist=0.0001)
            elif merge_type == "FIRST":
                target_co = selected[0].co.copy()
                for v in selected[1:]:
                    v.co = target_co
                bmesh.ops.remove_doubles(bm, verts=selected, dist=0.0001)
            elif merge_type == "LAST":
                target_co = selected[-1].co.copy()
                for v in selected[:-1]:
                    v.co = target_co
                bmesh.ops.remove_doubles(bm, verts=selected, dist=0.0001)
            elif merge_type == "COLLAPSE":
                bmesh.ops.collapse(bm, edges=[
                    e for e in bm.edges
                    if e.verts[0].select and e.verts[1].select
                ])
            else:
                raise ValueError(
                    f"Unknown merge_type: {merge_type!r}. "
                    "Valid: CENTER, FIRST, LAST, COLLAPSE"
                )

            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "dissolve_edges":
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            selected_edges = [e for e in bm.edges if e.select]
            if not selected_edges:
                raise ValueError(
                    "No edges selected for dissolve. Run 'select' first."
                )
            bmesh.ops.dissolve_edges(bm, edges=selected_edges)
            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    elif operation == "dissolve_faces":
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            selected_faces = [f for f in bm.faces if f.select]
            if not selected_faces:
                raise ValueError(
                    "No faces selected for dissolve. Run 'select' first."
                )
            bmesh.ops.dissolve_faces(bm, faces=selected_faces)
            bm.to_mesh(obj.data)
            obj.data.update()
            vert_count = len(bm.verts)
            face_count = len(bm.faces)
        finally:
            bm.free()

    else:
        raise ValueError(f"Unhandled operation: {operation}")

    return {
        "object_name": name,
        "operation": operation,
        "vertex_count": vert_count,
        "face_count": face_count,
    }


def handle_boolean_op(params: dict) -> dict:
    """Boolean operations: union, difference, intersect (MESH-05).

    Params:
        object_name: Target mesh object name.
        cutter_name: Cutter mesh object name.
        operation: "UNION", "DIFFERENCE", or "INTERSECT" (default "DIFFERENCE").
        remove_cutter: Remove cutter object after operation (default True).

    Returns dict with post-operation vertex/face counts.
    """
    name = params.get("object_name")
    target = _get_mesh_object(name)
    cutter_name = params.get("cutter_name")
    cutter = _get_mesh_object(cutter_name)
    operation = params.get("operation", "DIFFERENCE").upper()

    if operation not in ("UNION", "DIFFERENCE", "INTERSECT"):
        raise ValueError(
            f"Invalid boolean operation: {operation!r}. "
            "Valid: UNION, DIFFERENCE, INTERSECT"
        )

    remove_cutter = params.get("remove_cutter", True)

    # Add boolean modifier to target
    mod = target.modifiers.new(name="Boolean", type="BOOLEAN")
    mod.operation = operation
    mod.object = cutter
    mod.solver = "EXACT"

    # Apply modifier
    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for boolean operation")

    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    # Optionally remove cutter
    if remove_cutter:
        bpy.data.objects.remove(cutter, do_unlink=True)

    return {
        "object_name": name,
        "operation": operation,
        "vertex_count": len(target.data.vertices),
        "face_count": len(target.data.polygons),
    }


def handle_retopologize(params: dict) -> dict:
    """Retopology via Quadriflow with target face count (MESH-07).

    Params:
        object_name: Name of the mesh object to retopologize.
        target_faces: Target face count (default 4000).
        preserve_sharp: Preserve sharp edges (default True).
        preserve_boundary: Preserve boundary edges (default True).
        smooth_normals: Smooth normals after retopology (default True).
        use_symmetry: Use symmetry detection (default False).
        seed: Random seed for Quadriflow (default 0).

    Returns dict with before/after vertex/face counts and reduction ratio.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    target_faces = params.get("target_faces", 4000)
    preserve_sharp = params.get("preserve_sharp", True)
    preserve_boundary = params.get("preserve_boundary", True)
    smooth_normals = params.get("smooth_normals", True)
    use_symmetry = params.get("use_symmetry", False)
    seed = params.get("seed", 0)

    # Store before counts
    before_verts = len(obj.data.vertices)
    before_faces = len(obj.data.polygons)

    # Set object as active and selected, ensure object mode
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for retopology")

    try:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.quadriflow_remesh(
                target_faces=target_faces,
                preserve_sharp=preserve_sharp,
                preserve_boundary=preserve_boundary,
                smooth_normals=smooth_normals,
                use_mesh_symmetry=use_symmetry,
                seed=seed,
            )
    except RuntimeError as exc:
        if "canceled" in str(exc).lower():
            raise RuntimeError(
                f"Quadriflow retopology was canceled for '{name}'. "
                "The mesh may have issues -- try running auto_repair first."
            ) from exc
        raise

    after_verts = len(obj.data.vertices)
    after_faces = len(obj.data.polygons)
    reduction = round(after_faces / max(before_faces, 1), 3)

    return {
        "object_name": name,
        "before": {"vertices": before_verts, "faces": before_faces},
        "after": {"vertices": after_verts, "faces": after_faces},
        "target_faces": target_faces,
        "reduction_ratio": reduction,
        "preserve_sharp": preserve_sharp,
    }


def handle_sculpt(params: dict) -> dict:
    """Sculpt operations: smooth, inflate, flatten, crease (MESH-04).

    Params:
        object_name: Name of the mesh object to sculpt.
        operation: One of "smooth", "inflate", "flatten", "crease".
        strength: Operation strength (default 0.5).
        iterations: Number of iterations (default 3).

    Smooth uses bmesh (no mode switch). Inflate/flatten/crease use sculpt
    mode mesh_filter operators.

    Returns dict with operation details.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    operation = params.get("operation", "smooth")
    strength = params.get("strength", 0.5)
    iterations = params.get("iterations", 3)

    filter_type = _sculpt_operation_to_filter_type(operation)

    if filter_type is None:
        # "smooth" -- use bmesh directly, no mode switch needed
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()

            # Select all or use current selection
            verts = [v for v in bm.verts if v.select] or bm.verts[:]

            for _ in range(iterations):
                bmesh.ops.smooth_vert(
                    bm,
                    verts=verts,
                    factor=strength,
                    use_axis_x=True,
                    use_axis_y=True,
                    use_axis_z=True,
                )

            bm.to_mesh(obj.data)
            obj.data.update()
        finally:
            bm.free()
    else:
        # Inflate, flatten, crease -- require sculpt mode
        ctx = get_3d_context_override()
        if ctx is None:
            raise RuntimeError("No 3D Viewport available for sculpt operation")

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="SCULPT")

            filter_kwargs = {
                "type": filter_type,
                "strength": strength,
                "iteration_count": iterations,
            }

            # Operation-specific params from plan
            if operation == "flatten":
                filter_kwargs["surface_smooth_shape_preservation"] = 0.5
            elif operation == "crease":
                filter_kwargs["sharpen_smooth_ratio"] = 0.35

            bpy.ops.sculpt.mesh_filter(**filter_kwargs)
            bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "operation": operation,
        "strength": strength,
        "iterations": iterations,
    }
