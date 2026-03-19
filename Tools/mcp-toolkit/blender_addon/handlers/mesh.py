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
})

# Valid edit operations for handle_edit_mesh.
_EDIT_OPERATIONS = frozenset({"extrude", "inset", "mirror", "separate", "join"})

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
    """Select geometry by material, vertex group, face normal, or loose parts (MESH-03).

    Params:
        object_name: Name of the Blender mesh object.
        material_index: Select faces with this material slot index.
        material_name: Select faces with this material name (resolved to index).
        vertex_group: Select vertices in this vertex group (and their linked faces).
        face_normal_direction: [x, y, z] direction vector for face normal selection.
        normal_threshold: Dot-product threshold for normal selection (default 0.7).
        loose_parts: If True, select vertices with no linked faces.

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
    """Surgical mesh editing: extrude, inset, mirror, separate, join (MESH-06).

    Params:
        object_name: Name of the Blender mesh object.
        operation: One of "extrude", "inset", "mirror", "separate", "join".
        offset: [x, y, z] translation for extrude (default [0, 0, 0.5]).
        thickness: Inset thickness (default 0.1).
        depth: Inset depth (default 0.0).
        axis: Mirror axis -- "X", "Y", or "Z" (default "X").
        separate_type: "SELECTED", "MATERIAL", or "LOOSE" (default "SELECTED").
        object_names: List of object names to join into the target.

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
