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
- handle_loop_cut: Add loop cuts to a mesh edge (MESH-09)
- handle_bevel_edges: Bevel edges with configurable selection modes (MESH-10)
- handle_knife_project: Bisect or loop-cut a mesh with a cutting plane (MESH-11)
- handle_proportional_edit: Move vertices with proportional falloff (MESH-12)

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

# Valid brush types for real sculpt mode (handle_sculpt_brush).
_SCULPT_BRUSH_TYPES = frozenset({
    "DRAW", "CLAY_STRIPS", "CREASE", "GRAB", "INFLATE", "SMOOTH",
    "FLATTEN", "PINCH", "SNAKE_HOOK", "LAYER", "BLOB", "SCRAPE",
})


def _validate_sculpt_brush_params(params: dict) -> list[str]:
    """Validate sculpt brush parameters. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name is required and must be a non-empty string")

    brush_type = params.get("brush_type")
    if not brush_type:
        errors.append("brush_type is required")
    elif brush_type not in _SCULPT_BRUSH_TYPES:
        errors.append(
            f"Invalid brush_type: {brush_type!r}. "
            f"Valid: {sorted(_SCULPT_BRUSH_TYPES)}"
        )

    strength = params.get("strength", 0.5)
    if not isinstance(strength, (int, float)) or strength < 0 or strength > 1:
        errors.append(f"strength must be a float between 0 and 1, got {strength!r}")

    radius = params.get("radius", 50.0)
    if not isinstance(radius, (int, float)) or radius <= 0:
        errors.append(f"radius must be a positive number, got {radius!r}")

    stroke_points = params.get("stroke_points")
    if stroke_points is not None:
        if not isinstance(stroke_points, list):
            errors.append("stroke_points must be a list of [x,y,z] coordinates")
        else:
            for i, pt in enumerate(stroke_points):
                if not isinstance(pt, (list, tuple)) or len(pt) != 3:
                    errors.append(
                        f"stroke_points[{i}] must be [x,y,z], got {pt!r}"
                    )
                    break
                if not all(isinstance(c, (int, float)) for c in pt):
                    errors.append(
                        f"stroke_points[{i}] coordinates must be numeric"
                    )
                    break

    detail_size = params.get("detail_size", 12.0)
    if not isinstance(detail_size, (int, float)) or detail_size <= 0:
        errors.append(f"detail_size must be a positive number, got {detail_size!r}")

    return errors

_AXIS_MAP = {"X": 0, "Y": 1, "Z": 2}

# Valid bevel selection modes for handle_bevel_edges.
_BEVEL_SELECTION_MODES = frozenset({"all", "sharp", "boundary", "angle"})

# Valid proportional edit falloff types.
_PROPORTIONAL_FALLOFF_TYPES = frozenset({
    "SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR",
})

# Valid knife/bisect cut types.
_KNIFE_CUT_TYPES = frozenset({"bisect", "loop"})

# Valid shape key operations.
_SHAPE_KEY_OPERATIONS = frozenset({"CREATE", "SET_VALUE", "EDIT", "DELETE", "LIST", "ADD_DRIVER"})

# Valid vertex color operations.
_VERTEX_COLOR_OPERATIONS = frozenset({"CREATE_LAYER", "PAINT", "FILL"})

# Valid custom normal operations.
_CUSTOM_NORMAL_OPERATIONS = frozenset({"CALCULATE", "TRANSFER", "CLEAR"})

# Valid edge data operations.
_EDGE_DATA_OPERATIONS = frozenset({"SET_CREASE", "SET_BEVEL_WEIGHT", "SET_SHARP"})


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


def _validate_loop_cut_params(params: dict) -> dict:
    """Validate and normalise loop cut parameters.

    Returns dict with validated ``name``, ``cuts``, ``edge_index``, ``offset``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required for loop_cut")
    cuts = params.get("cuts", 1)
    if not isinstance(cuts, int) or cuts < 1:
        raise ValueError(f"cuts must be a positive integer, got {cuts!r}")
    edge_index = params.get("edge_index")
    if edge_index is not None and (not isinstance(edge_index, int) or edge_index < 0):
        raise ValueError(f"edge_index must be a non-negative integer, got {edge_index!r}")
    offset = params.get("offset", 0.0)
    if not isinstance(offset, (int, float)):
        raise ValueError(f"offset must be a number, got {type(offset).__name__}")
    if offset < -1.0 or offset > 1.0:
        raise ValueError(f"offset must be between -1 and 1, got {offset}")
    return {"name": name, "cuts": cuts, "edge_index": edge_index, "offset": float(offset)}


def _validate_bevel_params(params: dict) -> dict:
    """Validate and normalise bevel edge parameters.

    Returns dict with validated ``name``, ``width``, ``segments``,
    ``selection_mode``, ``angle_threshold``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required for bevel_edges")
    width = params.get("width")
    if width is None:
        raise ValueError("width is required for bevel_edges")
    if not isinstance(width, (int, float)) or width <= 0:
        raise ValueError(f"width must be a positive number, got {width!r}")
    segments = params.get("segments", 1)
    if not isinstance(segments, int) or segments < 1:
        raise ValueError(f"segments must be a positive integer, got {segments!r}")
    selection_mode = params.get("selection_mode", "sharp")
    if selection_mode not in _BEVEL_SELECTION_MODES:
        raise ValueError(
            f"Unknown selection_mode: {selection_mode!r}. "
            f"Valid: {sorted(_BEVEL_SELECTION_MODES)}"
        )
    angle_threshold = params.get("angle_threshold", 30.0)
    if not isinstance(angle_threshold, (int, float)):
        raise ValueError(f"angle_threshold must be a number, got {type(angle_threshold).__name__}")
    if angle_threshold < 0 or angle_threshold > 180:
        raise ValueError(f"angle_threshold must be between 0 and 180, got {angle_threshold}")
    return {
        "name": name,
        "width": float(width),
        "segments": segments,
        "selection_mode": selection_mode,
        "angle_threshold": float(angle_threshold),
    }


def _validate_knife_params(params: dict) -> dict:
    """Validate and normalise knife project parameters.

    Returns dict with validated ``name``, ``cut_type``, ``plane_point``,
    ``plane_normal``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required for knife_project")
    cut_type = params.get("cut_type", "bisect")
    if cut_type not in _KNIFE_CUT_TYPES:
        raise ValueError(
            f"Unknown cut_type: {cut_type!r}. Valid: {sorted(_KNIFE_CUT_TYPES)}"
        )
    plane_point = params.get("plane_point", [0.0, 0.0, 0.0])
    plane_normal = params.get("plane_normal", [0.0, 0.0, 1.0])
    if not isinstance(plane_point, (list, tuple)) or len(plane_point) != 3:
        raise ValueError(f"plane_point must be a 3-element list, got {plane_point!r}")
    if not isinstance(plane_normal, (list, tuple)) or len(plane_normal) != 3:
        raise ValueError(f"plane_normal must be a 3-element list, got {plane_normal!r}")
    # Check normal is not zero-length
    mag_sq = sum(c * c for c in plane_normal)
    if mag_sq < 1e-10:
        raise ValueError("plane_normal must not be a zero vector")
    return {
        "name": name,
        "cut_type": cut_type,
        "plane_point": [float(c) for c in plane_point],
        "plane_normal": [float(c) for c in plane_normal],
    }


def _validate_proportional_edit_params(params: dict) -> dict:
    """Validate and normalise proportional edit parameters.

    Returns dict with validated ``name``, ``vertex_indices``, ``offset``,
    ``radius``, ``falloff_type``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required for proportional_edit")
    vertex_indices = params.get("vertex_indices")
    if not vertex_indices or not isinstance(vertex_indices, (list, tuple)):
        raise ValueError("vertex_indices must be a non-empty list of integers")
    for idx in vertex_indices:
        if not isinstance(idx, int) or idx < 0:
            raise ValueError(f"vertex_indices must contain non-negative integers, got {idx!r}")
    offset = params.get("offset")
    if not isinstance(offset, (list, tuple)) or len(offset) != 3:
        raise ValueError(f"offset must be a 3-element list, got {offset!r}")
    radius = params.get("radius")
    if radius is None:
        raise ValueError("radius is required for proportional_edit")
    if not isinstance(radius, (int, float)) or radius <= 0:
        raise ValueError(f"radius must be a positive number, got {radius!r}")
    falloff_type = params.get("falloff_type", "SMOOTH")
    if falloff_type not in _PROPORTIONAL_FALLOFF_TYPES:
        raise ValueError(
            f"Unknown falloff_type: {falloff_type!r}. "
            f"Valid: {sorted(_PROPORTIONAL_FALLOFF_TYPES)}"
        )
    return {
        "name": name,
        "vertex_indices": list(vertex_indices),
        "offset": [float(c) for c in offset],
        "radius": float(radius),
        "falloff_type": falloff_type,
    }


def _validate_vertex_color_params(params: dict) -> dict:
    """Validate and normalise vertex color parameters.

    Returns dict with validated ``name``, ``operation``, ``layer_name``,
    ``color``, ``vertex_indices``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    operation = params.get("operation", "CREATE_LAYER")
    if operation not in _VERTEX_COLOR_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_VERTEX_COLOR_OPERATIONS)}"
        )

    layer_name = params.get("layer_name", "Col")
    if not isinstance(layer_name, str) or not layer_name:
        raise ValueError(f"layer_name must be a non-empty string, got {layer_name!r}")

    color = params.get("color", [1.0, 1.0, 1.0, 1.0])
    if not isinstance(color, (list, tuple)) or len(color) != 4:
        raise ValueError(f"color must be a 4-element [r,g,b,a] list, got {color!r}")
    for i, c in enumerate(color):
        if not isinstance(c, (int, float)):
            raise ValueError(f"color[{i}] must be numeric, got {type(c).__name__}")
        if c < 0.0 or c > 1.0:
            raise ValueError(f"color[{i}] must be between 0 and 1, got {c}")

    vertex_indices = params.get("vertex_indices")
    if vertex_indices is not None:
        if not isinstance(vertex_indices, (list, tuple)):
            raise ValueError("vertex_indices must be a list of integers")
        for idx in vertex_indices:
            if not isinstance(idx, int) or idx < 0:
                raise ValueError(
                    f"vertex_indices must contain non-negative integers, got {idx!r}"
                )

    return {
        "name": name,
        "operation": operation,
        "layer_name": layer_name,
        "color": [float(c) for c in color],
        "vertex_indices": list(vertex_indices) if vertex_indices is not None else None,
    }


def _validate_custom_normals_params(params: dict) -> dict:
    """Validate and normalise custom normals parameters.

    Returns dict with validated ``name``, ``operation``, ``source_object``,
    ``split_angle``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    operation = params.get("operation", "CALCULATE")
    if operation not in _CUSTOM_NORMAL_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_CUSTOM_NORMAL_OPERATIONS)}"
        )

    source_object = params.get("source_object")
    if operation == "TRANSFER" and (not source_object or not isinstance(source_object, str)):
        raise ValueError("source_object is required for TRANSFER operation")

    split_angle = params.get("split_angle", 30.0)
    if not isinstance(split_angle, (int, float)):
        raise ValueError(f"split_angle must be a number, got {type(split_angle).__name__}")
    if split_angle < 0.0 or split_angle > 180.0:
        raise ValueError(f"split_angle must be between 0 and 180, got {split_angle}")

    return {
        "name": name,
        "operation": operation,
        "source_object": source_object,
        "split_angle": float(split_angle),
    }


def _validate_edge_data_params(params: dict) -> dict:
    """Validate and normalise edge data parameters.

    Returns dict with validated ``name``, ``operation``, ``edge_indices``,
    ``value``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    operation = params.get("operation", "SET_CREASE")
    if operation not in _EDGE_DATA_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_EDGE_DATA_OPERATIONS)}"
        )

    edge_indices = params.get("edge_indices")
    if edge_indices is not None:
        if not isinstance(edge_indices, (list, tuple)):
            raise ValueError("edge_indices must be a list of integers")
        for idx in edge_indices:
            if not isinstance(idx, int) or idx < 0:
                raise ValueError(
                    f"edge_indices must contain non-negative integers, got {idx!r}"
                )

    value = params.get("value", 1.0)
    if not isinstance(value, (int, float)):
        raise ValueError(f"value must be a number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"value must be between 0 and 1, got {value}")

    return {
        "name": name,
        "operation": operation,
        "edge_indices": list(edge_indices) if edge_indices is not None else None,
        "value": float(value),
    }


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


# ---------------------------------------------------------------------------
# Modifier stack operations
# ---------------------------------------------------------------------------

# Supported modifier types and their default settings.
MODIFIER_DEFAULTS: dict[str, dict] = {
    "SUBSURF": {"levels": 2, "render_levels": 3, "quality": 3},
    "BEVEL": {"width": 0.02, "segments": 3, "limit_method": "ANGLE", "angle_limit": 0.524},
    "MIRROR": {"use_axis": [True, False, False], "use_bisect_axis": [False, False, False]},
    "ARRAY": {"count": 3, "relative_offset_displace": [1.0, 0.0, 0.0]},
    "SOLIDIFY": {"thickness": 0.1, "offset": -1.0},
    "DECIMATE": {"ratio": 0.5, "decimate_type": "COLLAPSE"},
    "REMESH": {"mode": "VOXEL", "voxel_size": 0.1},
    "SMOOTH": {"factor": 0.5, "iterations": 5},
    "BOOLEAN": {"operation": "DIFFERENCE", "object": ""},
    "WIREFRAME": {"thickness": 0.02},
    "SKIN": {},
    "LATTICE": {},
    "SHRINKWRAP": {},
}

VALID_MODIFIER_TYPES: frozenset[str] = frozenset(MODIFIER_DEFAULTS.keys())


def _validate_modifier_params(params: dict) -> list[str]:
    """Validate modifier params. Returns list of error strings (empty = valid).

    Checks:
    - ``modifier_type`` is present and in ``VALID_MODIFIER_TYPES``.
    - If ``settings`` is provided, all keys are valid for the modifier type.
    """
    errors: list[str] = []

    modifier_type = params.get("modifier_type")
    if modifier_type is None:
        errors.append("modifier_type is required")
        return errors

    if modifier_type not in VALID_MODIFIER_TYPES:
        errors.append(
            f"Invalid modifier_type: {modifier_type!r}. "
            f"Valid: {sorted(VALID_MODIFIER_TYPES)}"
        )
        return errors

    settings = params.get("settings")
    if settings:
        allowed_keys = set(MODIFIER_DEFAULTS.get(modifier_type, {}).keys())
        bad_keys = set(settings.keys()) - allowed_keys
        if bad_keys:
            errors.append(
                f"Invalid settings keys for {modifier_type}: {sorted(bad_keys)}. "
                f"Allowed: {sorted(allowed_keys)}"
            )

    return errors


def _apply_modifier_settings(mod: object, settings: dict, modifier_type: str) -> None:
    """Apply settings dict to a Blender modifier object.

    Handles special cases like ``use_axis`` (list -> per-axis booleans) and
    ``relative_offset_displace`` (list -> Vector assignment).
    """
    for key, value in settings.items():
        if key == "use_axis" and isinstance(value, list):
            for i, v in enumerate(value[:3]):
                mod.use_axis[i] = v
        elif key == "use_bisect_axis" and isinstance(value, list):
            for i, v in enumerate(value[:3]):
                mod.use_bisect_axis[i] = v
        elif key == "relative_offset_displace" and isinstance(value, list):
            for i, v in enumerate(value[:3]):
                mod.relative_offset_displace[i] = v
        elif key == "object" and modifier_type == "BOOLEAN":
            # Resolve object reference by name
            obj_ref = bpy.data.objects.get(value) if value else None
            mod.object = obj_ref
        else:
            setattr(mod, key, value)


def handle_add_modifier(params: dict) -> dict:
    """Add a modifier to an object.

    Params:
        name: Object name (required).
        modifier_type: Modifier type string (required).
        modifier_name: Display name for the modifier (optional, auto-generated).
        settings: Dict of modifier-specific settings (optional).

    Returns dict with object name, modifier name, type, and applied settings.
    """
    obj_name = params.get("name")
    obj = _get_mesh_object(obj_name)

    modifier_type = params.get("modifier_type")
    errors = _validate_modifier_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    modifier_name = params.get("modifier_name") or modifier_type.title()

    # Merge defaults with user settings
    defaults = dict(MODIFIER_DEFAULTS.get(modifier_type, {}))
    user_settings = params.get("settings") or {}
    merged = {**defaults, **user_settings}

    mod = obj.modifiers.new(name=modifier_name, type=modifier_type)
    _apply_modifier_settings(mod, merged, modifier_type)

    return {
        "object_name": obj_name,
        "modifier_name": mod.name,
        "modifier_type": modifier_type,
        "settings_applied": merged,
    }


def handle_apply_modifier(params: dict) -> dict:
    """Apply (bake) a modifier on an object.

    Params:
        name: Object name (required).
        modifier_name: Name of modifier to apply, or ``"ALL"`` to apply all.

    Returns dict with object name and list of applied modifier names.
    """
    obj_name = params.get("name")
    obj = _get_mesh_object(obj_name)
    modifier_name = params.get("modifier_name")
    if not modifier_name:
        raise ValueError("modifier_name is required")

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for modifier apply")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    applied: list[str] = []

    if modifier_name == "ALL":
        # Apply all modifiers in stack order (top-down)
        while obj.modifiers:
            mod_name = obj.modifiers[0].name
            with bpy.context.temp_override(**ctx):
                bpy.ops.object.modifier_apply(modifier=mod_name)
            applied.append(mod_name)
    else:
        if modifier_name not in [m.name for m in obj.modifiers]:
            raise ValueError(
                f"Modifier '{modifier_name}' not found on '{obj_name}'. "
                f"Existing: {[m.name for m in obj.modifiers]}"
            )
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.modifier_apply(modifier=modifier_name)
        applied.append(modifier_name)

    return {
        "object_name": obj_name,
        "applied": applied,
        "remaining_modifiers": [m.name for m in obj.modifiers],
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


def handle_remove_modifier(params: dict) -> dict:
    """Remove a modifier without applying it.

    Params:
        name: Object name (required).
        modifier_name: Name of modifier to remove (required).

    Returns dict with object name and remaining modifier names.
    """
    obj_name = params.get("name")
    obj = _get_mesh_object(obj_name)
    modifier_name = params.get("modifier_name")
    if not modifier_name:
        raise ValueError("modifier_name is required")

    mod = obj.modifiers.get(modifier_name)
    if mod is None:
        raise ValueError(
            f"Modifier '{modifier_name}' not found on '{obj_name}'. "
            f"Existing: {[m.name for m in obj.modifiers]}"
        )

    obj.modifiers.remove(mod)

    return {
        "object_name": obj_name,
        "removed": modifier_name,
        "remaining_modifiers": [m.name for m in obj.modifiers],
    }


def handle_list_modifiers(params: dict) -> dict:
    """List all modifiers on an object with their settings.

    Params:
        name: Object name (required).

    Returns dict with object name and list of modifier info dicts.
    """
    obj_name = params.get("name")
    obj = _get_mesh_object(obj_name)

    modifiers: list[dict] = []
    for mod in obj.modifiers:
        mod_info: dict = {
            "name": mod.name,
            "type": mod.type,
            "show_viewport": mod.show_viewport,
            "show_render": mod.show_render,
        }

        # Extract known settings for recognised modifier types
        defaults = MODIFIER_DEFAULTS.get(mod.type, {})
        if defaults:
            settings: dict = {}
            for key in defaults:
                if key == "use_axis":
                    settings[key] = [mod.use_axis[i] for i in range(3)]
                elif key == "use_bisect_axis":
                    settings[key] = [mod.use_bisect_axis[i] for i in range(3)]
                elif key == "relative_offset_displace":
                    settings[key] = [
                        mod.relative_offset_displace[i] for i in range(3)
                    ]
                elif key == "object" and mod.type == "BOOLEAN":
                    settings[key] = mod.object.name if mod.object else ""
                else:
                    settings[key] = getattr(mod, key, None)
            mod_info["settings"] = settings

        modifiers.append(mod_info)

    return {
        "object_name": obj_name,
        "modifier_count": len(modifiers),
        "modifiers": modifiers,
    }


# ---------------------------------------------------------------------------
# Topology editing handlers (MESH-09 through MESH-12)
# ---------------------------------------------------------------------------


def handle_loop_cut(params: dict) -> dict:
    """Add loop cuts to a mesh edge (MESH-09).

    Params:
        name: Object name (required).
        cuts: Number of loop cuts (default 1).
        edge_index: Edge index to cut along (optional; if omitted, uses
                    the first edge).
        offset: Slide offset from -1 to 1 (default 0.0).

    Returns dict with object name, cuts added, and post-op vertex/face counts.
    """
    validated = _validate_loop_cut_params(params)
    name = validated["name"]
    cuts = validated["cuts"]
    edge_index = validated["edge_index"]
    offset = validated["offset"]

    obj = _get_mesh_object(name)

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for loop cut operation")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Determine edge index -- default to 0 if not provided
    if edge_index is None:
        if len(obj.data.edges) == 0:
            raise ValueError(f"Object '{name}' has no edges for loop cut")
        edge_index = 0
    elif edge_index >= len(obj.data.edges):
        raise ValueError(
            f"edge_index {edge_index} out of range "
            f"(object has {len(obj.data.edges)} edges)"
        )

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.loopcut_slide(
            MESH_OT_loopcut={
                "number_cuts": cuts,
                "smoothness": 0.0,
                "falloff": "INVERSE_SQUARE",
                "object_index": 0,
                "edge_index": edge_index,
            },
            TRANSFORM_OT_edge_slide={
                "value": offset,
            },
        )
        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "cuts": cuts,
        "edge_index": edge_index,
        "offset": offset,
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


def handle_bevel_edges(params: dict) -> dict:
    """Bevel edges with configurable selection modes (MESH-10).

    Params:
        name: Object name (required).
        width: Bevel width (required, positive float).
        segments: Smoothness / segment count (default 1).
        selection_mode: Edge selection strategy -- "all", "sharp",
                        "boundary", or "angle" (default "sharp").
        angle_threshold: For angle mode, max angle in degrees between
                         adjacent faces (default 30).

    Returns dict with object name, bevel settings, and post-op counts.
    """
    validated = _validate_bevel_params(params)
    name = validated["name"]
    width = validated["width"]
    segments = validated["segments"]
    selection_mode = validated["selection_mode"]
    angle_threshold = validated["angle_threshold"]

    obj = _get_mesh_object(name)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Select edges based on selection_mode
        if selection_mode == "all":
            target_edges = bm.edges[:]
        elif selection_mode == "sharp":
            target_edges = [e for e in bm.edges if not e.smooth]
        elif selection_mode == "boundary":
            target_edges = [e for e in bm.edges if e.is_boundary]
        elif selection_mode == "angle":
            angle_rad = math.radians(angle_threshold)
            target_edges = []
            for e in bm.edges:
                if len(e.link_faces) == 2:
                    face_angle = e.link_faces[0].normal.angle(e.link_faces[1].normal)
                    if face_angle >= angle_rad:
                        target_edges.append(e)
        else:
            target_edges = []

        if not target_edges:
            bm.free()
            return {
                "object_name": name,
                "beveled_edges": 0,
                "selection_mode": selection_mode,
                "vertex_count": len(obj.data.vertices),
                "face_count": len(obj.data.polygons),
            }

        bmesh.ops.bevel(
            bm,
            geom=target_edges,
            offset=width,
            offset_type="OFFSET",
            segments=segments,
            affect="EDGES",
        )

        bm.to_mesh(obj.data)
        obj.data.update()
        vert_count = len(bm.verts)
        face_count = len(bm.faces)
        edge_count = len(target_edges)
    finally:
        bm.free()

    return {
        "object_name": name,
        "beveled_edges": edge_count,
        "width": width,
        "segments": segments,
        "selection_mode": selection_mode,
        "vertex_count": vert_count,
        "face_count": face_count,
    }


def handle_knife_project(params: dict) -> dict:
    """Bisect or loop-cut a mesh with a cutting plane (MESH-11).

    Params:
        name: Object name (required).
        cut_type: "bisect" (plane cut) or "loop" (edge loop) (default "bisect").
        plane_point: [x, y, z] point on the cutting plane (default [0,0,0]).
        plane_normal: [x, y, z] normal of the cutting plane (default [0,0,1]).

    For bisect: uses bmesh.ops.bisect_plane to slice the mesh.
    For loop: selects edges intersecting the plane and subdivides them.

    Returns dict with object name, cut type, and post-op counts.
    """
    validated = _validate_knife_params(params)
    name = validated["name"]
    cut_type = validated["cut_type"]
    plane_point = validated["plane_point"]
    plane_normal = validated["plane_normal"]

    obj = _get_mesh_object(name)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if cut_type == "bisect":
            all_geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            result = bmesh.ops.bisect_plane(
                bm,
                geom=all_geom,
                plane_co=mathutils.Vector(plane_point),
                plane_no=mathutils.Vector(plane_normal),
                clear_inner=False,
                clear_outer=False,
            )
            new_geom_count = len(result.get("geom_cut", []))
        elif cut_type == "loop":
            # Find edges that cross the plane and subdivide them
            plane_co = mathutils.Vector(plane_point)
            plane_no = mathutils.Vector(plane_normal).normalized()
            crossing_edges = []
            for e in bm.edges:
                v0 = e.verts[0].co
                v1 = e.verts[1].co
                d0 = (v0 - plane_co).dot(plane_no)
                d1 = (v1 - plane_co).dot(plane_no)
                if d0 * d1 < 0:  # opposite sides of the plane
                    crossing_edges.append(e)

            if crossing_edges:
                bmesh.ops.subdivide_edges(
                    bm,
                    edges=crossing_edges,
                    cuts=1,
                )
            new_geom_count = len(crossing_edges)
        else:
            new_geom_count = 0

        bm.to_mesh(obj.data)
        obj.data.update()
        vert_count = len(bm.verts)
        face_count = len(bm.faces)
    finally:
        bm.free()

    return {
        "object_name": name,
        "cut_type": cut_type,
        "new_geometry_count": new_geom_count,
        "vertex_count": vert_count,
        "face_count": face_count,
    }


def handle_proportional_edit(params: dict) -> dict:
    """Move vertices with proportional falloff (MESH-12).

    Params:
        name: Object name (required).
        vertex_indices: List of vertex indices to move (required).
        offset: [x, y, z] movement vector (required).
        radius: Falloff radius (required, positive float).
        falloff_type: Falloff curve -- "SMOOTH", "SPHERE", "ROOT",
                      "SHARP", "LINEAR" (default "SMOOTH").

    Selected vertices get full offset. Nearby vertices within *radius*
    get proportional offset based on the falloff function.

    Returns dict with object name, vertices affected, and post-op counts.
    """
    validated = _validate_proportional_edit_params(params)
    name = validated["name"]
    vertex_indices = validated["vertex_indices"]
    offset_vec = validated["offset"]
    radius = validated["radius"]
    falloff_type = validated["falloff_type"]

    obj = _get_mesh_object(name)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        total_verts = len(bm.verts)
        # Validate indices are in range
        for idx in vertex_indices:
            if idx >= total_verts:
                raise ValueError(
                    f"vertex index {idx} out of range "
                    f"(mesh has {total_verts} vertices)"
                )

        # Collect the selected vertex positions for distance calculations
        selected_positions = [
            mathutils.Vector(bm.verts[i].co) for i in vertex_indices
        ]
        offset_v = mathutils.Vector(offset_vec)

        # Apply full offset to selected vertices
        for idx in vertex_indices:
            bm.verts[idx].co += offset_v

        # Apply proportional falloff to nearby vertices
        affected_count = len(vertex_indices)
        index_set = set(vertex_indices)
        for v in bm.verts:
            if v.index in index_set:
                continue
            # Find minimum distance to any selected vertex (from original pos)
            min_dist = min(
                (v.co - pos).length for pos in selected_positions
            )
            if min_dist >= radius:
                continue
            # Compute falloff factor
            t = min_dist / radius  # 0 at vertex, 1 at radius edge
            if falloff_type == "SMOOTH":
                factor = (1.0 - t * t) ** 2  # smooth hermite-like
            elif falloff_type == "SPHERE":
                factor = math.sqrt(max(1.0 - t * t, 0.0))
            elif falloff_type == "ROOT":
                factor = math.sqrt(max(1.0 - t, 0.0))
            elif falloff_type == "SHARP":
                factor = (1.0 - t) ** 2
            elif falloff_type == "LINEAR":
                factor = 1.0 - t
            else:
                factor = 0.0

            if factor > 0.0:
                v.co += offset_v * factor
                affected_count += 1

        bm.to_mesh(obj.data)
        obj.data.update()
        vert_count = len(bm.verts)
        face_count = len(bm.faces)
    finally:
        bm.free()

    return {
        "object_name": name,
        "vertices_selected": len(vertex_indices),
        "vertices_affected": affected_count,
        "offset": offset_vec,
        "radius": radius,
        "falloff_type": falloff_type,
        "vertex_count": vert_count,
        "face_count": face_count,
    }


# ---------------------------------------------------------------------------
# Real sculpt mode handlers (brush strokes, enter/exit sculpt mode)
# ---------------------------------------------------------------------------


def handle_enter_sculpt_mode(params: dict) -> dict:
    """Enter sculpt mode for the specified mesh object.

    Params:
        name: Object name (required).
        use_dyntopo: Enable dynamic topology (default False).
        detail_size: Dyntopo detail size (default 12.0).

    Returns dict with mode status.
    """
    name = params.get("name")
    obj = _get_mesh_object(name)

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for sculpt mode")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="SCULPT")

    use_dyntopo = params.get("use_dyntopo", False)
    detail_size = params.get("detail_size", 12.0)

    if use_dyntopo:
        with bpy.context.temp_override(**ctx):
            bpy.ops.sculpt.dynamic_topology_toggle()
            bpy.context.scene.tool_settings.sculpt.detail_size = detail_size

    return {
        "object_name": name,
        "mode": "SCULPT",
        "dyntopo_enabled": use_dyntopo,
        "detail_size": detail_size if use_dyntopo else None,
    }


def handle_exit_sculpt_mode(params: dict) -> dict:
    """Exit sculpt mode back to object mode.

    Params:
        name: Object name (required).

    Returns dict with mode status.
    """
    name = params.get("name")
    obj = _get_mesh_object(name)

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for mode switch")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        # Disable dyntopo if active before exiting
        if (hasattr(bpy.context, "sculpt_object")
                and bpy.context.sculpt_object
                and obj.data.is_editmode is False):
            try:
                if bpy.context.scene.tool_settings.sculpt.detail_type_method:
                    bpy.ops.sculpt.dynamic_topology_toggle()
            except (AttributeError, RuntimeError):
                pass
        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "mode": "OBJECT",
    }


def handle_sculpt_brush(params: dict) -> dict:
    """Apply a sculpt brush stroke along a path of 3D points.

    Params:
        name: Object name (required).
        brush_type: Brush type string (required). One of DRAW, CLAY_STRIPS,
            CREASE, GRAB, INFLATE, SMOOTH, FLATTEN, PINCH, SNAKE_HOOK,
            LAYER, BLOB, SCRAPE.
        strength: Brush strength 0-1 (default 0.5).
        radius: Brush radius in pixels (default 50.0).
        stroke_points: List of [x,y,z] coordinates defining the stroke path.
            If not provided, applies a single dab at object origin.
        use_dyntopo: Enable dynamic topology (default False).
        detail_size: Dyntopo detail size (default 12.0).

    Returns dict with operation details.
    """
    errors = _validate_sculpt_brush_params(params)
    if errors:
        raise ValueError("; ".join(errors))

    name = params["name"]
    obj = _get_mesh_object(name)
    brush_type = params["brush_type"]
    strength = params.get("strength", 0.5)
    radius = params.get("radius", 50.0)
    stroke_points = params.get("stroke_points")
    use_dyntopo = params.get("use_dyntopo", False)
    detail_size = params.get("detail_size", 12.0)

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for sculpt brush")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="SCULPT")
        try:
            # Enable dyntopo if requested
            if use_dyntopo:
                try:
                    if not obj.data.use_paint_symmetry_x:
                        pass  # Just check we're in sculpt context
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    bpy.context.scene.tool_settings.sculpt.detail_size = detail_size
                except RuntimeError:
                    pass

            # Set the active brush
            sculpt = bpy.context.scene.tool_settings.sculpt
            brush = bpy.data.brushes.get(brush_type)
            if brush is None:
                brush = bpy.data.brushes.new(name=brush_type, mode="SCULPT")
            brush.sculpt_tool = brush_type
            brush.strength = strength
            brush.size = int(radius)
            sculpt.brush = brush

            # Build stroke data
            stroke = []
            if stroke_points:
                for pt in stroke_points:
                    stroke.append({
                        "name": "stroke",
                        "is_start": len(stroke) == 0,
                        "location": (pt[0], pt[1], pt[2]),
                        "mouse": (0, 0),
                        "mouse_event": (0, 0),
                        "pen_flip": False,
                        "pressure": 1.0,
                        "size": int(radius),
                        "time": 0.0,
                        "x_tilt": 0.0,
                        "y_tilt": 0.0,
                    })
            else:
                # Single dab at object center
                loc = obj.location
                stroke.append({
                    "name": "stroke",
                    "is_start": True,
                    "location": (loc.x, loc.y, loc.z),
                    "mouse": (0, 0),
                    "mouse_event": (0, 0),
                    "pen_flip": False,
                    "pressure": 1.0,
                    "size": int(radius),
                    "time": 0.0,
                    "x_tilt": 0.0,
                    "y_tilt": 0.0,
                })

            bpy.ops.sculpt.brush_stroke(stroke=stroke)

            # Disable dyntopo before exiting if we enabled it
            if use_dyntopo:
                try:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                except RuntimeError:
                    pass
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "brush_type": brush_type,
        "strength": strength,
        "radius": radius,
        "stroke_points_count": len(stroke_points) if stroke_points else 1,
        "use_dyntopo": use_dyntopo,
    }


# ---------------------------------------------------------------------------
# Vertex colors, custom normals, and edge data handlers
# ---------------------------------------------------------------------------


def handle_vertex_color(params: dict) -> dict:
    """Vertex color operations: create layer, paint, fill.

    Params:
        name: Object name (required).
        operation: "CREATE_LAYER", "PAINT", or "FILL" (default "CREATE_LAYER").
        layer_name: Vertex color layer name (default "Col").
        color: [r, g, b, a] color to paint/fill (default [1, 1, 1, 1]).
        vertex_indices: List of vertex indices for selective paint (optional).

    Returns dict with layer info and operation details.
    """
    validated = _validate_vertex_color_params(params)
    name = validated["name"]
    operation = validated["operation"]
    layer_name = validated["layer_name"]
    color = validated["color"]
    vertex_indices = validated["vertex_indices"]

    obj = _get_mesh_object(name)
    mesh = obj.data

    if operation == "CREATE_LAYER":
        # Check if layer already exists
        existing = mesh.color_attributes.get(layer_name)
        if existing is not None:
            return {
                "object_name": name,
                "operation": operation,
                "layer_name": layer_name,
                "created": False,
                "message": f"Layer '{layer_name}' already exists",
            }
        mesh.color_attributes.new(
            name=layer_name,
            type="FLOAT_COLOR",
            domain="POINT",
        )
        return {
            "object_name": name,
            "operation": operation,
            "layer_name": layer_name,
            "created": True,
        }

    elif operation == "FILL":
        layer = mesh.color_attributes.get(layer_name)
        if layer is None:
            raise ValueError(
                f"Vertex color layer '{layer_name}' not found on '{name}'. "
                f"Create it first with operation='CREATE_LAYER'."
            )
        # Fill all vertices with the color
        for i in range(len(layer.data)):
            layer.data[i].color = tuple(color)
        mesh.update()
        return {
            "object_name": name,
            "operation": operation,
            "layer_name": layer_name,
            "color": color,
            "vertices_painted": len(layer.data),
        }

    elif operation == "PAINT":
        layer = mesh.color_attributes.get(layer_name)
        if layer is None:
            raise ValueError(
                f"Vertex color layer '{layer_name}' not found on '{name}'. "
                f"Create it first with operation='CREATE_LAYER'."
            )
        if vertex_indices is not None:
            # Validate indices
            total = len(layer.data)
            for idx in vertex_indices:
                if idx >= total:
                    raise ValueError(
                        f"vertex index {idx} out of range "
                        f"(layer has {total} data points)"
                    )
            for idx in vertex_indices:
                layer.data[idx].color = tuple(color)
            painted = len(vertex_indices)
        else:
            # Paint all
            for i in range(len(layer.data)):
                layer.data[i].color = tuple(color)
            painted = len(layer.data)
        mesh.update()
        return {
            "object_name": name,
            "operation": operation,
            "layer_name": layer_name,
            "color": color,
            "vertices_painted": painted,
        }

    raise ValueError(f"Unhandled operation: {operation}")


def handle_custom_normals(params: dict) -> dict:
    """Custom normals operations: calculate, transfer, clear.

    Params:
        name: Object name (required).
        operation: "CALCULATE", "TRANSFER", or "CLEAR" (default "CALCULATE").
        source_object: Source object name for TRANSFER (required for TRANSFER).
        split_angle: Auto-smooth split angle in degrees for CALCULATE (default 30).

    Returns dict with operation details.
    """
    validated = _validate_custom_normals_params(params)
    name = validated["name"]
    operation = validated["operation"]
    source_object = validated["source_object"]
    split_angle = validated["split_angle"]

    obj = _get_mesh_object(name)
    mesh = obj.data

    if operation == "CALCULATE":
        # Enable auto smooth and set angle
        split_angle_rad = math.radians(split_angle)
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = True
            mesh.auto_smooth_angle = split_angle_rad
        # Calculate split normals
        mesh.calc_normals_split()
        return {
            "object_name": name,
            "operation": operation,
            "split_angle": split_angle,
            "has_custom_normals": mesh.has_custom_normals,
        }

    elif operation == "TRANSFER":
        source = bpy.data.objects.get(source_object)
        if source is None:
            raise ValueError(f"Source object not found: {source_object!r}")
        if source.type != "MESH":
            raise ValueError(f"Source object '{source_object}' is not a mesh")

        # Add data transfer modifier
        mod = obj.modifiers.new(name="NormalTransfer", type="DATA_TRANSFER")
        mod.object = source
        mod.use_loop_data = True
        mod.data_types_loops = {"CUSTOM_NORMAL"}
        mod.loop_mapping = "POLYINTERP_NEAREST"

        ctx = get_3d_context_override()
        if ctx is None:
            raise RuntimeError("No 3D Viewport available for normal transfer")

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        return {
            "object_name": name,
            "operation": operation,
            "source_object": source_object,
            "has_custom_normals": mesh.has_custom_normals,
        }

    elif operation == "CLEAR":
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = False
        mesh.free_normals_split()
        return {
            "object_name": name,
            "operation": operation,
            "has_custom_normals": mesh.has_custom_normals,
        }

    raise ValueError(f"Unhandled operation: {operation}")


def handle_edge_data(params: dict) -> dict:
    """Edge data operations: set crease, bevel weight, sharp.

    Params:
        name: Object name (required).
        operation: "SET_CREASE", "SET_BEVEL_WEIGHT", or "SET_SHARP"
                   (default "SET_CREASE").
        edge_indices: List of edge indices to affect (optional, all edges if None).
        value: Value to set, 0.0-1.0 for crease/bevel_weight,
               1.0 = sharp for SET_SHARP (default 1.0).

    Returns dict with operation details and edges affected.
    """
    validated = _validate_edge_data_params(params)
    name = validated["name"]
    operation = validated["operation"]
    edge_indices = validated["edge_indices"]
    value = validated["value"]

    obj = _get_mesh_object(name)

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        total_edges = len(bm.edges)

        # Determine which edges to affect
        if edge_indices is not None:
            for idx in edge_indices:
                if idx >= total_edges:
                    raise ValueError(
                        f"edge index {idx} out of range "
                        f"(mesh has {total_edges} edges)"
                    )
            target_edges = [bm.edges[i] for i in edge_indices]
        else:
            target_edges = bm.edges[:]

        if operation == "SET_CREASE":
            crease_layer = bm.edges.layers.float.get("crease_edge")
            if crease_layer is None:
                crease_layer = bm.edges.layers.float.new("crease_edge")
            for e in target_edges:
                e[crease_layer] = value

        elif operation == "SET_BEVEL_WEIGHT":
            bevel_layer = bm.edges.layers.float.get("bevel_weight_edge")
            if bevel_layer is None:
                bevel_layer = bm.edges.layers.float.new("bevel_weight_edge")
            for e in target_edges:
                e[bevel_layer] = value

        elif operation == "SET_SHARP":
            is_sharp = value >= 0.5
            for e in target_edges:
                e.smooth = not is_sharp

        bm.to_mesh(obj.data)
        obj.data.update()
        affected = len(target_edges)
    finally:
        bm.free()

    return {
        "object_name": name,
        "operation": operation,
        "edges_affected": affected,
        "value": value,
    }


# ---------------------------------------------------------------------------
# Shape Key workflow (SHAPEKEY-01)
# ---------------------------------------------------------------------------


def _validate_shape_key_operation(params: dict) -> list[str]:
    """Validate shape key operation parameters. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    name = params.get("name")
    if not name or not isinstance(name, str):
        errors.append("name (object name) is required and must be a non-empty string")

    operation = params.get("operation")
    if not operation:
        errors.append("operation is required")
    elif operation not in _SHAPE_KEY_OPERATIONS:
        errors.append(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_SHAPE_KEY_OPERATIONS)}"
        )

    if operation == "CREATE":
        key_name = params.get("key_name")
        if not key_name or not isinstance(key_name, str):
            errors.append("key_name is required for CREATE operation")

    elif operation == "SET_VALUE":
        key_name = params.get("key_name")
        if not key_name or not isinstance(key_name, str):
            errors.append("key_name is required for SET_VALUE operation")
        value = params.get("value")
        if value is not None:
            if not isinstance(value, (int, float)):
                errors.append(f"value must be a number, got {type(value).__name__}")
            elif value < 0 or value > 1:
                errors.append(f"value must be between 0 and 1, got {value}")

    elif operation == "EDIT":
        key_name = params.get("key_name")
        if not key_name or not isinstance(key_name, str):
            errors.append("key_name is required for EDIT operation")
        vertex_offsets = params.get("vertex_offsets")
        if not isinstance(vertex_offsets, dict):
            errors.append("vertex_offsets must be a dict for EDIT operation")
        elif len(vertex_offsets) == 0:
            errors.append("vertex_offsets must not be empty for EDIT operation")
        else:
            for idx, offset in vertex_offsets.items():
                # Keys may arrive as strings from JSON
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError):
                    errors.append(f"vertex index must be an integer, got {idx!r}")
                    continue
                if int_idx < 0:
                    errors.append(f"vertex index must be non-negative, got {int_idx}")
                if not isinstance(offset, (list, tuple)) or len(offset) != 3:
                    errors.append(
                        f"vertex {idx}: offset must be [dx, dy, dz], got {offset!r}"
                    )

    elif operation == "DELETE":
        key_name = params.get("key_name")
        if not key_name or not isinstance(key_name, str):
            errors.append("key_name is required for DELETE operation")

    elif operation == "ADD_DRIVER":
        key_name = params.get("key_name")
        if not key_name or not isinstance(key_name, str):
            errors.append("key_name is required for ADD_DRIVER operation")
        driver_expression = params.get("driver_expression")
        if not driver_expression or not isinstance(driver_expression, str):
            errors.append("driver_expression is required for ADD_DRIVER operation")

    # LIST requires no extra params beyond name

    return errors


def handle_shape_key(params: dict) -> dict:
    """Shape key workflow: create, set value, edit, delete, list, add driver (SHAPEKEY-01).

    Params:
        name: Object name (required).
        operation: CREATE | SET_VALUE | EDIT | DELETE | LIST | ADD_DRIVER
        key_name: Shape key name (required for most operations).
        from_mix: For CREATE, create from current mix (default False).
        value: For SET_VALUE, float 0-1.
        vertex_offsets: For EDIT, dict of vertex_index -> [dx, dy, dz].
        driver_expression: For ADD_DRIVER, Python expression string.
        variable_bone: For ADD_DRIVER, bone name to drive from.

    Returns dict with operation results.
    """
    errors = _validate_shape_key_operation(params)
    if errors:
        raise ValueError(f"Invalid shape key params: {'; '.join(errors)}")

    obj_name = params["name"]
    operation = params["operation"]

    obj = bpy.data.objects.get(obj_name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {obj_name}")

    if operation == "LIST":
        keys = []
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                keys.append({
                    "name": kb.name,
                    "value": kb.value,
                    "mute": kb.mute,
                    "relative_key": kb.relative_key.name if kb.relative_key else None,
                })
        return {
            "object_name": obj_name,
            "shape_keys": keys,
            "count": len(keys),
        }

    elif operation == "CREATE":
        key_name = params["key_name"]
        from_mix = params.get("from_mix", False)

        # Ensure Basis exists
        if not obj.data.shape_keys:
            obj.shape_key_add(name="Basis")

        sk = obj.shape_key_add(name=key_name, from_mix=from_mix)
        total = len(obj.data.shape_keys.key_blocks)
        return {
            "object_name": obj_name,
            "key_name": sk.name,
            "from_mix": from_mix,
            "total_shape_keys": total,
        }

    elif operation == "SET_VALUE":
        key_name = params["key_name"]
        value = float(params.get("value", 0.0))

        if not obj.data.shape_keys:
            raise ValueError(f"Object '{obj_name}' has no shape keys")

        kb = obj.data.shape_keys.key_blocks.get(key_name)
        if not kb:
            raise ValueError(
                f"Shape key '{key_name}' not found on '{obj_name}'"
            )

        kb.value = value
        return {
            "object_name": obj_name,
            "key_name": key_name,
            "value": value,
        }

    elif operation == "EDIT":
        key_name = params["key_name"]
        vertex_offsets = params["vertex_offsets"]

        if not obj.data.shape_keys:
            raise ValueError(f"Object '{obj_name}' has no shape keys")

        kb = obj.data.shape_keys.key_blocks.get(key_name)
        if not kb:
            raise ValueError(
                f"Shape key '{key_name}' not found on '{obj_name}'"
            )

        vertices_modified = 0
        for idx_str, offset in vertex_offsets.items():
            idx = int(idx_str)
            if 0 <= idx < len(kb.data):
                kb.data[idx].co.x += offset[0]
                kb.data[idx].co.y += offset[1]
                kb.data[idx].co.z += offset[2]
                vertices_modified += 1

        return {
            "object_name": obj_name,
            "key_name": key_name,
            "vertices_modified": vertices_modified,
        }

    elif operation == "DELETE":
        key_name = params["key_name"]

        if not obj.data.shape_keys:
            raise ValueError(f"Object '{obj_name}' has no shape keys")

        kb = obj.data.shape_keys.key_blocks.get(key_name)
        if not kb:
            raise ValueError(
                f"Shape key '{key_name}' not found on '{obj_name}'"
            )

        obj.shape_key_remove(kb)
        remaining = (
            len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
        )
        return {
            "object_name": obj_name,
            "deleted_key": key_name,
            "remaining_shape_keys": remaining,
        }

    elif operation == "ADD_DRIVER":
        key_name = params["key_name"]
        driver_expression = params["driver_expression"]
        variable_bone = params.get("variable_bone")

        if not obj.data.shape_keys:
            raise ValueError(f"Object '{obj_name}' has no shape keys")

        kb = obj.data.shape_keys.key_blocks.get(key_name)
        if not kb:
            raise ValueError(
                f"Shape key '{key_name}' not found on '{obj_name}'"
            )

        # Add driver to shape key value
        fcurve = kb.driver_add("value")
        driver = fcurve.driver
        driver.type = "SCRIPTED"
        driver.expression = driver_expression

        # If a bone name is provided, set up a transform variable
        if variable_bone:
            var = driver.variables.new()
            var.name = "bone_val"
            var.type = "TRANSFORMS"
            target = var.targets[0]
            target.id = obj
            target.bone_target = variable_bone
            target.transform_type = "LOC_Z"
            target.transform_space = "LOCAL_SPACE"

        return {
            "object_name": obj_name,
            "key_name": key_name,
            "driver_expression": driver_expression,
            "variable_bone": variable_bone,
        }

    raise ValueError(f"Unhandled operation: {operation}")
