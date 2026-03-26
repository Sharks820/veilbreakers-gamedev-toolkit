"""Mesh topology analysis, auto-repair, game-readiness, editing, and sculpting handlers.

Provides:
- handle_analyze_topology: Full topology analysis with A-F grading (MESH-01)
- handle_auto_repair: Chained repair pipeline via bmesh.ops (MESH-02)
- handle_check_game_ready: Composite game-readiness validation (MESH-08)
- handle_select_geometry: Selection engine by material/vertex group/normal/loose (MESH-03)
- handle_edit_mesh: Surgical edits -- extrude, inset, mirror, separate, join (MESH-06)
- handle_boolean_op: Boolean operations -- union, difference, intersect (MESH-05)
- handle_retopologize: Retopology via quadriflow with target face count (MESH-07)
- handle_sculpt: 11 mesh filter sculpt operations (MESH-04)
- handle_sculpt_brush: 32 sculpt brush types with stroke support (MESH-04b)
- handle_dyntopo: Dynamic topology enable/disable/status (MESH-04c)
- handle_voxel_remesh: Voxel-based remesh for uniform topology (MESH-04d)
- handle_face_sets: Face set creation and management (MESH-04e)
- handle_multires: Multiresolution modifier management (MESH-04f)

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

# Valid sculpt operations for handle_sculpt (mesh_filter types).
# None means "handled via bmesh, not sculpt mode".
_SCULPT_OPERATIONS = {
    "smooth": None,                     # bmesh smooth_vert
    "inflate": "INFLATE",               # inflate/deflate vertices
    "flatten": "SURFACE_SMOOTH",        # smooth while preserving volume
    "crease": "SHARPEN",                # sharpen edges/creases
    "relax": "RELAX",                   # relax mesh topology
    "enhance_details": "ENHANCE_DETAILS",  # sharpen fine detail
    "random": "RANDOM",                 # randomize vertex positions
    "scale": "SCALE",                   # scale from center
    "sphere": "SPHERE",                 # push vertices toward sphere
    "surface_smooth": "SURFACE_SMOOTH", # explicit alias
    "sharpen": "SHARPEN",              # explicit alias
}

# Valid sculpt brush types (bpy.types.Brush.sculpt_tool enumeration).
# These are used by handle_sculpt_brush for direct brush stroke operations.
_SCULPT_BRUSH_TYPES = frozenset({
    "DRAW", "DRAW_SHARP", "CLAY", "CLAY_STRIPS", "CLAY_THUMB",
    "LAYER", "INFLATE", "BLOB", "CREASE", "SMOOTH", "FLATTEN",
    "FILL", "SCRAPE", "MULTIPLANE_SCRAPE", "PINCH", "GRAB",
    "ELASTIC_DEFORM", "SNAKE_HOOK", "THUMB", "POSE", "NUDGE",
    "ROTATE", "TOPOLOGY", "BOUNDARY", "CLOTH", "SIMPLIFY",
    "MASK", "DRAW_FACE_SETS", "DISPLACEMENT_ERASER",
    "DISPLACEMENT_SMEAR", "PAINT", "SMEAR",
})

# Valid dynamic topology detail modes.
_DYNTOPO_DETAIL_MODES = frozenset({
    "RELATIVE_DETAIL", "CONSTANT_DETAIL", "BRUSH_DETAIL", "MANUAL_DETAIL",
})

# Valid dynamic topology actions.
_DYNTOPO_ACTIONS = frozenset({"enable", "disable", "status"})

# Valid face set actions.
_FACE_SET_ACTIONS = frozenset({
    "create_from_visible", "create_from_loose_parts",
    "create_from_materials", "create_from_normals",
    "randomize", "init",
})

# Valid multires actions.
_MULTIRES_ACTIONS = frozenset({
    "add", "subdivide", "reshape", "delete_higher", "delete_lower",
    "apply_base",
})

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


def _validate_brush_type(brush_type: str) -> str:
    """Validate and normalize a sculpt brush type string.

    Accepts case-insensitive input, returns upper-cased canonical name.
    Raises ``ValueError`` for unknown brush types.
    """
    normalized = brush_type.upper()
    if normalized not in _SCULPT_BRUSH_TYPES:
        raise ValueError(
            f"Unknown sculpt brush type: {brush_type!r}. "
            f"Valid: {sorted(_SCULPT_BRUSH_TYPES)}"
        )
    return normalized


def _validate_brush_direction(direction: str) -> str:
    """Validate sculpt brush direction (ADD or SUBTRACT).

    Returns normalized upper-case direction string.
    """
    normalized = direction.upper()
    if normalized not in ("ADD", "SUBTRACT"):
        raise ValueError(
            f"Invalid brush direction: {direction!r}. Valid: 'ADD', 'SUBTRACT'"
        )
    return normalized


def _validate_dyntopo_action(action: str) -> str:
    """Validate dynamic topology action.

    Raises ``ValueError`` for unknown actions.
    """
    if action not in _DYNTOPO_ACTIONS:
        raise ValueError(
            f"Unknown dyntopo action: {action!r}. "
            f"Valid: {sorted(_DYNTOPO_ACTIONS)}"
        )
    return action


def _validate_dyntopo_detail_mode(mode: str) -> str:
    """Validate dynamic topology detail mode.

    Raises ``ValueError`` for unknown modes.
    """
    if mode not in _DYNTOPO_DETAIL_MODES:
        raise ValueError(
            f"Unknown dyntopo detail mode: {mode!r}. "
            f"Valid: {sorted(_DYNTOPO_DETAIL_MODES)}"
        )
    return mode


def _validate_voxel_remesh_params(voxel_size: float, adaptivity: float) -> None:
    """Validate voxel remesh parameters.

    Raises ``ValueError`` for out-of-range values.
    """
    if voxel_size <= 0:
        raise ValueError(
            f"voxel_size must be > 0, got {voxel_size}"
        )
    if not (0.0 <= adaptivity <= 1.0):
        raise ValueError(
            f"adaptivity must be in [0.0, 1.0], got {adaptivity}"
        )


def _validate_face_set_action(action: str) -> str:
    """Validate face set action.

    Raises ``ValueError`` for unknown actions.
    """
    if action not in _FACE_SET_ACTIONS:
        raise ValueError(
            f"Unknown face set action: {action!r}. "
            f"Valid: {sorted(_FACE_SET_ACTIONS)}"
        )
    return action


def _validate_multires_action(action: str) -> str:
    """Validate multires modifier action.

    Raises ``ValueError`` for unknown actions.
    """
    if action not in _MULTIRES_ACTIONS:
        raise ValueError(
            f"Unknown multires action: {action!r}. "
            f"Valid: {sorted(_MULTIRES_ACTIONS)}"
        )
    return action


def _validate_multires_subdivisions(subdivisions: int) -> None:
    """Validate multires subdivision count.

    Raises ``ValueError`` for out-of-range values.
    """
    if subdivisions < 1:
        raise ValueError(
            f"subdivisions must be >= 1, got {subdivisions}"
        )
    if subdivisions > 10:
        raise ValueError(
            f"subdivisions must be <= 10, got {subdivisions} "
            "(higher values risk memory exhaustion)"
        )


def _validate_brush_strength(strength: float) -> float:
    """Validate and clamp brush strength to [0.0, 1.0]."""
    return max(0.0, min(1.0, float(strength)))


def _validate_brush_radius(radius: float) -> float:
    """Validate brush radius (must be positive)."""
    if radius <= 0:
        raise ValueError(f"Brush radius must be > 0, got {radius}")
    return float(radius)


def _validate_sculpt_brush_params(params: dict) -> list[str]:
    """Validate sculpt brush stroke parameters. Returns list of error strings.

    Validates: name (required, non-empty), brush_type (must be in
    _SCULPT_BRUSH_TYPES), strength (0.0-1.0), radius (> 0),
    stroke_points (list of 3-element numeric lists), detail_size (> 0).
    """
    errors: list[str] = []

    name = params.get("name")
    if not name:
        errors.append("name is required and must be a non-empty string")

    brush_type = params.get("brush_type")
    if brush_type is None:
        errors.append("brush_type is required")
    elif brush_type.upper() not in _SCULPT_BRUSH_TYPES:
        errors.append(
            f"Invalid brush_type: {brush_type!r}. "
            f"Valid: {sorted(_SCULPT_BRUSH_TYPES)}"
        )

    strength = params.get("strength")
    if strength is not None:
        if not isinstance(strength, (int, float)):
            errors.append(f"strength must be a number, got {type(strength).__name__}")
        elif not (0.0 <= float(strength) <= 1.0):
            errors.append(f"strength must be between 0.0 and 1.0, got {strength}")

    radius = params.get("radius")
    if radius is not None:
        if not isinstance(radius, (int, float)):
            errors.append(f"radius must be a number, got {type(radius).__name__}")
        elif float(radius) <= 0:
            errors.append(f"radius must be > 0, got {radius}")

    stroke_points = params.get("stroke_points")
    if stroke_points is not None:
        if not isinstance(stroke_points, list):
            errors.append("stroke_points must be a list of [x, y, z] triples")
        else:
            for i, pt in enumerate(stroke_points):
                if not isinstance(pt, (list, tuple)) or len(pt) != 3:
                    errors.append(
                        f"stroke_points[{i}] must be a 3-element list, got {pt!r}"
                    )
                    break
                if not all(isinstance(c, (int, float)) for c in pt):
                    errors.append(
                        f"stroke_points[{i}] must contain numeric values, got {pt!r}"
                    )
                    break

    detail_size = params.get("detail_size")
    if detail_size is not None:
        if not isinstance(detail_size, (int, float)):
            errors.append(f"detail_size must be a number, got {type(detail_size).__name__}")
        elif float(detail_size) <= 0:
            errors.append(f"detail_size must be > 0, got {detail_size}")

    return errors


def _validate_loop_cut_params(params: dict) -> dict:
    """Validate loop cut parameters. Returns validated dict with defaults.

    Required: name (non-empty string).
    Optional: cuts (positive int, default 1), edge_index (non-negative int,
    default None), offset (float in [-1, 1], default 0.0).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    cuts = params.get("cuts", 1)
    if not isinstance(cuts, int) or isinstance(cuts, bool) or cuts < 1:
        raise ValueError("cuts must be a positive integer")

    edge_index = params.get("edge_index", None)
    if edge_index is not None:
        if not isinstance(edge_index, int) or isinstance(edge_index, bool) or edge_index < 0:
            raise ValueError("edge_index must be a non-negative integer")

    raw_offset = params.get("offset", 0.0)
    if isinstance(raw_offset, bool):
        raise ValueError("offset must be a number")
    if not isinstance(raw_offset, (int, float)):
        raise ValueError("offset must be a number")
    offset = float(raw_offset)
    if not (-1.0 <= offset <= 1.0):
        raise ValueError("offset must be between -1 and 1")

    return {
        "name": name,
        "cuts": cuts,
        "edge_index": edge_index,
        "offset": offset,
    }


def _validate_bevel_params(params: dict) -> dict:
    """Validate bevel edge parameters. Returns validated dict with defaults.

    Required: name (non-empty string), width (positive float).
    Optional: segments (positive int, default 1), selection_mode
    (all/sharp/boundary/angle, default "sharp"), angle_threshold
    (0-180 float, default 30.0).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    raw_width = params.get("width")
    if raw_width is None:
        raise ValueError("width is required")
    if isinstance(raw_width, bool) or not isinstance(raw_width, (int, float)):
        raise ValueError("width must be a positive number")
    width = float(raw_width)
    if width <= 0:
        raise ValueError("width must be a positive number")

    segments = params.get("segments", 1)
    if not isinstance(segments, int) or isinstance(segments, bool) or segments < 1:
        raise ValueError("segments must be a positive integer")

    selection_mode = params.get("selection_mode", "sharp")
    if selection_mode not in _BEVEL_SELECTION_MODES:
        raise ValueError(
            f"Unknown selection_mode: {selection_mode!r}. "
            f"Valid: {sorted(_BEVEL_SELECTION_MODES)}"
        )

    raw_angle = params.get("angle_threshold", 30.0)
    if isinstance(raw_angle, bool) or not isinstance(raw_angle, (int, float)):
        raise ValueError("angle_threshold must be a number")
    angle_threshold = float(raw_angle)
    if not (0.0 <= angle_threshold <= 180.0):
        raise ValueError("angle_threshold must be between 0 and 180")

    return {
        "name": name,
        "width": width,
        "segments": segments,
        "selection_mode": selection_mode,
        "angle_threshold": angle_threshold,
    }


def _validate_knife_params(params: dict) -> dict:
    """Validate knife/bisect parameters. Returns validated dict with defaults.

    Required: name (non-empty string).
    Optional: cut_type (bisect/loop, default "bisect"), plane_point
    (3-element list, default [0,0,0]), plane_normal (3-element non-zero
    list, default [0,0,1]).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    cut_type = params.get("cut_type", "bisect")
    if cut_type not in _KNIFE_CUT_TYPES:
        raise ValueError(
            f"Unknown cut_type: {cut_type!r}. Valid: {sorted(_KNIFE_CUT_TYPES)}"
        )

    raw_point = params.get("plane_point", [0.0, 0.0, 0.0])
    if not isinstance(raw_point, (list, tuple)) or len(raw_point) != 3:
        raise ValueError("plane_point must be a 3-element list of numbers")
    try:
        plane_point = [float(c) for c in raw_point]
    except (TypeError, ValueError):
        raise ValueError("plane_point must be a 3-element list of numbers")

    raw_normal = params.get("plane_normal", [0.0, 0.0, 1.0])
    if not isinstance(raw_normal, (list, tuple)) or len(raw_normal) != 3:
        raise ValueError("plane_normal must be a 3-element list of numbers")
    try:
        plane_normal = [float(c) for c in raw_normal]
    except (TypeError, ValueError):
        raise ValueError("plane_normal must be a 3-element list of numbers")

    if plane_normal[0] == 0.0 and plane_normal[1] == 0.0 and plane_normal[2] == 0.0:
        raise ValueError("plane_normal must not be a zero vector")

    return {
        "name": name,
        "cut_type": cut_type,
        "plane_point": plane_point,
        "plane_normal": plane_normal,
    }


def _validate_proportional_edit_params(params: dict) -> dict:
    """Validate proportional edit parameters. Returns validated dict.

    Required: name (non-empty string), vertex_indices (non-empty list of
    non-negative ints), offset (3-element numeric list), radius (positive
    float).
    Optional: falloff_type (default "SMOOTH").

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    vertex_indices = params.get("vertex_indices")
    if not vertex_indices or not isinstance(vertex_indices, list):
        raise ValueError("vertex_indices must be a non-empty list of non-negative integers")
    for idx in vertex_indices:
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
            raise ValueError(
                "vertex_indices must contain non-negative integers"
            )

    raw_offset = params.get("offset")
    if not isinstance(raw_offset, (list, tuple)) or len(raw_offset) != 3:
        raise ValueError("offset must be a 3-element list of numbers")
    offset = [float(c) for c in raw_offset]

    radius = params.get("radius")
    if radius is None:
        raise ValueError("radius is required")
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise ValueError("radius must be a positive number")
    radius = float(radius)
    if radius <= 0:
        raise ValueError("radius must be a positive number")

    falloff_type = params.get("falloff_type", "SMOOTH")
    if falloff_type not in _PROPORTIONAL_FALLOFF_TYPES:
        raise ValueError(
            f"Unknown falloff_type: {falloff_type!r}. "
            f"Valid: {sorted(_PROPORTIONAL_FALLOFF_TYPES)}"
        )

    return {
        "name": name,
        "vertex_indices": vertex_indices,
        "offset": offset,
        "radius": radius,
        "falloff_type": falloff_type,
    }


def _validate_vertex_color_params(params: dict) -> dict:
    """Validate vertex color operation parameters. Returns validated dict.

    Required: name (non-empty string).
    Optional: operation (CREATE_LAYER/PAINT/FILL, default "CREATE_LAYER"),
    layer_name (non-empty str, default "Col"), color (4-element RGBA list
    in [0,1], default [1,1,1,1]), vertex_indices (list of non-negative
    ints, default None).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    operation = params.get("operation", "CREATE_LAYER")
    if operation not in _VERTEX_COLOR_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_VERTEX_COLOR_OPERATIONS)}"
        )

    layer_name = params.get("layer_name", "Col")
    if not layer_name:
        raise ValueError("layer_name must be a non-empty string")

    color = params.get("color", [1.0, 1.0, 1.0, 1.0])
    if not isinstance(color, (list, tuple)) or len(color) != 4:
        raise ValueError("color must be a 4-element RGBA list")
    for c in color:
        if not isinstance(c, (int, float)) or not (0.0 <= float(c) <= 1.0):
            raise ValueError("color values must be between 0.0 and 1.0")
    color = [float(c) for c in color]

    vertex_indices = params.get("vertex_indices", None)
    if vertex_indices is not None:
        if not isinstance(vertex_indices, list):
            raise ValueError("vertex_indices must be a list of non-negative integers")
        for idx in vertex_indices:
            if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
                raise ValueError("vertex_indices must contain non-negative integers")

    return {
        "name": name,
        "operation": operation,
        "layer_name": layer_name,
        "color": color,
        "vertex_indices": vertex_indices,
    }


def _validate_custom_normals_params(params: dict) -> dict:
    """Validate custom normals operation parameters. Returns validated dict.

    Required: name (non-empty string).
    Optional: operation (CALCULATE/TRANSFER/CLEAR, default "CALCULATE"),
    split_angle (0-180 float, default 30.0), source_object (str, required
    when operation is TRANSFER).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    operation = params.get("operation", "CALCULATE")
    if operation not in _CUSTOM_NORMAL_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_CUSTOM_NORMAL_OPERATIONS)}"
        )

    split_angle = params.get("split_angle", 30.0)
    if isinstance(split_angle, bool) or not isinstance(split_angle, (int, float)):
        raise ValueError("split_angle must be a number")
    split_angle = float(split_angle)
    if not (0.0 <= split_angle <= 180.0):
        raise ValueError("split_angle must be between 0 and 180")

    source_object = params.get("source_object", None)
    if operation == "TRANSFER" and not source_object:
        raise ValueError("source_object is required when operation is TRANSFER")

    return {
        "name": name,
        "operation": operation,
        "split_angle": split_angle,
        "source_object": source_object,
    }


def _validate_edge_data_params(params: dict) -> dict:
    """Validate edge data operation parameters. Returns validated dict.

    Required: name (non-empty string).
    Optional: operation (SET_CREASE/SET_BEVEL_WEIGHT/SET_SHARP, default
    "SET_CREASE"), edge_indices (list of non-negative ints, default None),
    value (float in [0, 1], default 1.0).

    Raises ValueError for invalid parameters.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required")

    operation = params.get("operation", "SET_CREASE")
    if operation not in _EDGE_DATA_OPERATIONS:
        raise ValueError(
            f"Invalid operation: {operation!r}. "
            f"Valid: {sorted(_EDGE_DATA_OPERATIONS)}"
        )

    edge_indices = params.get("edge_indices", None)
    if edge_indices is not None:
        if not isinstance(edge_indices, list):
            raise ValueError("edge_indices must be a list of non-negative integers")
        for idx in edge_indices:
            if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
                raise ValueError("edge_indices must contain non-negative integers")

    value = params.get("value", 1.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("value must be a number")
    value = float(value)
    if not (0.0 <= value <= 1.0):
        raise ValueError("value must be between 0.0 and 1.0")

    return {
        "name": name,
        "operation": operation,
        "edge_indices": edge_indices,
        "value": value,
    }


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
                space=mathutils.Matrix.Translation(cent),
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
                    vertex_only=False,
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
                    vertex_only=True,
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
                use_preserve_sharp=preserve_sharp,
                use_preserve_boundary=preserve_boundary,
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
    """Sculpt mesh filter operations (MESH-04).

    Params:
        object_name: Name of the mesh object to sculpt.
        operation: One of: smooth, inflate, flatten, crease, relax,
            enhance_details, random, scale, sphere, surface_smooth, sharpen.
        strength: Operation strength (default 0.5).
        iterations: Number of iterations (default 3).

    Smooth uses bmesh (no mode switch). All others use sculpt mode mesh_filter
    operators via bpy.ops.sculpt.mesh_filter().

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
# Sculpt brush stroke handler (MESH-04b)
# ---------------------------------------------------------------------------


def handle_sculpt_brush(params: dict) -> dict:
    """Apply a sculpt brush stroke on a mesh object.

    Switches to sculpt mode, configures the active brush, and optionally
    applies brush strokes at specified screen-space coordinates.

    Params:
        object_name: Name of the mesh object (required).
        brush_type: Sculpt brush tool enum (required). One of DRAW, DRAW_SHARP,
            CLAY, CLAY_STRIPS, CLAY_THUMB, LAYER, INFLATE, BLOB, CREASE,
            SMOOTH, FLATTEN, FILL, SCRAPE, MULTIPLANE_SCRAPE, PINCH, GRAB,
            ELASTIC_DEFORM, SNAKE_HOOK, THUMB, POSE, NUDGE, ROTATE, TOPOLOGY,
            BOUNDARY, CLOTH, SIMPLIFY, MASK, DRAW_FACE_SETS,
            DISPLACEMENT_ERASER, DISPLACEMENT_SMEAR, PAINT, SMEAR.
        strength: Brush strength 0.0-1.0 (default 0.5).
        radius: Brush radius in pixels (default 50).
        stroke_points: List of [x, y, pressure] screen-space coords (optional).
            If omitted, configures the brush but does not apply a stroke.
        use_front_faces_only: Only affect front-facing geometry (default False).
        direction: "ADD" or "SUBTRACT" (default "ADD").

    Returns dict with brush configuration applied.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)

    brush_type = _validate_brush_type(params.get("brush_type", "DRAW"))
    strength = _validate_brush_strength(params.get("strength", 0.5))
    radius = _validate_brush_radius(params.get("radius", 50))
    stroke_points = params.get("stroke_points")
    use_front_faces_only = bool(params.get("use_front_faces_only", False))
    direction = _validate_brush_direction(params.get("direction", "ADD"))

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for sculpt brush operation")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="SCULPT")

        # Configure brush
        brush = bpy.context.tool_settings.sculpt.brush
        brush.sculpt_tool = brush_type
        brush.strength = strength
        brush.use_front_faces_only = use_front_faces_only

        # Set brush direction via unified paint settings
        scene = bpy.context.scene
        scene.tool_settings.unified_paint_settings.size = int(radius)

        # Set brush direction
        if direction == "SUBTRACT":
            brush.direction = "SUBTRACT"
        else:
            brush.direction = "ADD"

        stroke_applied = False
        if stroke_points:
            # Build stroke data from screen-space coords
            stroke = []
            for pt in stroke_points:
                x = float(pt[0]) if len(pt) > 0 else 0.0
                y = float(pt[1]) if len(pt) > 1 else 0.0
                pressure = float(pt[2]) if len(pt) > 2 else 1.0
                stroke.append({
                    "name": "",
                    "mouse": (x, y),
                    "mouse_event": (x, y),
                    "pen_flip": False,
                    "is_start": len(stroke) == 0,
                    "location": (0, 0, 0),
                    "pressure": pressure,
                    "size": int(radius),
                    "time": 0.0,
                    "x_tilt": 0.0,
                    "y_tilt": 0.0,
                })
            bpy.ops.sculpt.brush_stroke(stroke=stroke)
            stroke_applied = True

        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "brush_type": brush_type,
        "strength": strength,
        "radius": radius,
        "direction": direction,
        "use_front_faces_only": use_front_faces_only,
        "stroke_applied": stroke_applied,
        "stroke_points_count": len(stroke_points) if stroke_points else 0,
    }


# ---------------------------------------------------------------------------
# Dynamic topology toggle handler (MESH-04c)
# ---------------------------------------------------------------------------


def handle_dyntopo(params: dict) -> dict:
    """Enable, disable, or query dynamic topology (dyntopo) for sculpting.

    Params:
        object_name: Name of the mesh object (required).
        action: "enable" | "disable" | "status" (required).
        detail_size: Voxel detail size in screen pixels (default 12.0).
        detail_mode: Detail mode -- RELATIVE_DETAIL, CONSTANT_DETAIL,
            BRUSH_DETAIL, or MANUAL_DETAIL (default RELATIVE_DETAIL).

    Returns dict with dyntopo state after the operation.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    action = _validate_dyntopo_action(params.get("action", "status"))
    detail_size = float(params.get("detail_size", 12.0))
    detail_mode = _validate_dyntopo_detail_mode(
        params.get("detail_mode", "RELATIVE_DETAIL")
    )

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for dyntopo operation")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="SCULPT")

        sculpt = bpy.context.sculpt_object
        is_enabled = sculpt and sculpt.use_dynamic_topology_sculpting if hasattr(
            sculpt, "use_dynamic_topology_sculpting"
        ) else False

        if action == "enable" and not is_enabled:
            bpy.ops.sculpt.dynamic_topology_toggle()
            is_enabled = True
        elif action == "disable" and is_enabled:
            bpy.ops.sculpt.dynamic_topology_toggle()
            is_enabled = False

        # Configure detail settings when enabled
        if is_enabled:
            scene = bpy.context.scene
            scene.tool_settings.sculpt.detail_size = detail_size
            scene.tool_settings.sculpt.detail_type_method = detail_mode

        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "action": action,
        "enabled": is_enabled,
        "detail_size": detail_size,
        "detail_mode": detail_mode,
    }


# ---------------------------------------------------------------------------
# Voxel remesh handler (MESH-04d)
# ---------------------------------------------------------------------------


def handle_voxel_remesh(params: dict) -> dict:
    """Apply voxel remesh to a mesh object for uniform topology.

    Params:
        object_name: Name of the mesh object (required).
        voxel_size: Voxel size -- smaller = more detail (default 0.05).
        adaptivity: Adaptivity 0.0-1.0 -- higher = fewer polys in flat
            areas (default 0.0).

    Returns dict with before/after vertex and face counts.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    voxel_size = float(params.get("voxel_size", 0.05))
    adaptivity = float(params.get("adaptivity", 0.0))

    _validate_voxel_remesh_params(voxel_size, adaptivity)

    before_verts = len(obj.data.vertices)
    before_faces = len(obj.data.polygons)

    # Set remesh properties on the mesh data
    obj.data.remesh_voxel_size = voxel_size
    obj.data.remesh_voxel_adaptivity = adaptivity

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for voxel remesh")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.voxel_remesh()

    after_verts = len(obj.data.vertices)
    after_faces = len(obj.data.polygons)

    return {
        "object_name": name,
        "voxel_size": voxel_size,
        "adaptivity": adaptivity,
        "before": {"vertices": before_verts, "faces": before_faces},
        "after": {"vertices": after_verts, "faces": after_faces},
    }


# ---------------------------------------------------------------------------
# Face sets handler (MESH-04e)
# ---------------------------------------------------------------------------


def handle_face_sets(params: dict) -> dict:
    """Create or manipulate face sets on a sculpt mesh.

    Face sets partition mesh faces into groups for isolated sculpting.

    Params:
        object_name: Name of the mesh object (required).
        action: One of: create_from_visible, create_from_loose_parts,
            create_from_materials, create_from_normals, randomize, init.

    Returns dict with action result.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    action = _validate_face_set_action(params.get("action", "init"))

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for face set operation")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="SCULPT")

        if action == "init":
            bpy.ops.sculpt.face_sets_init(mode="NONE")
        elif action == "create_from_visible":
            bpy.ops.sculpt.face_set_change_visibility(mode="TOGGLE")
        elif action == "create_from_loose_parts":
            bpy.ops.sculpt.face_sets_init(mode="LOOSE_PARTS")
        elif action == "create_from_materials":
            bpy.ops.sculpt.face_sets_init(mode="MATERIALS")
        elif action == "create_from_normals":
            bpy.ops.sculpt.face_sets_init(mode="NORMALS")
        elif action == "randomize":
            bpy.ops.sculpt.face_sets_randomize_colors()

        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": name,
        "action": action,
        "face_count": len(obj.data.polygons),
    }


# ---------------------------------------------------------------------------
# Multires modifier handler (MESH-04f)
# ---------------------------------------------------------------------------


def handle_multires(params: dict) -> dict:
    """Manage a Multiresolution modifier for multi-level sculpting.

    Params:
        object_name: Name of the mesh object (required).
        action: One of: add, subdivide, reshape, delete_higher,
            delete_lower, apply_base.
        subdivisions: Number of subdivision levels for 'subdivide' (default 1).

    Returns dict with action result and current modifier state.
    """
    name = params.get("object_name")
    obj = _get_mesh_object(name)
    action = _validate_multires_action(params.get("action", "add"))
    subdivisions = int(params.get("subdivisions", 1))

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for multires operation")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Find existing multires modifier
    multires_mod = None
    for mod in obj.modifiers:
        if mod.type == "MULTIRES":
            multires_mod = mod
            break

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="OBJECT")

        if action == "add":
            if multires_mod is None:
                bpy.ops.object.modifier_add(type="MULTIRES")
                multires_mod = obj.modifiers[-1]

        elif action == "subdivide":
            if multires_mod is None:
                bpy.ops.object.modifier_add(type="MULTIRES")
                multires_mod = obj.modifiers[-1]
            _validate_multires_subdivisions(subdivisions)
            for _ in range(subdivisions):
                bpy.ops.object.multires_subdivide(
                    modifier=multires_mod.name, mode="CATMULL_CLARK"
                )

        elif action == "reshape":
            if multires_mod is None:
                raise RuntimeError(
                    f"No Multires modifier found on '{name}'"
                )
            bpy.ops.object.multires_reshape(modifier=multires_mod.name)

        elif action == "delete_higher":
            if multires_mod is None:
                raise RuntimeError(
                    f"No Multires modifier found on '{name}'"
                )
            bpy.ops.object.multires_higher_levels_delete(
                modifier=multires_mod.name
            )

        elif action == "delete_lower":
            if multires_mod is None:
                raise RuntimeError(
                    f"No Multires modifier found on '{name}'"
                )
            bpy.ops.object.multires_lower_levels_delete(
                modifier=multires_mod.name
            )

        elif action == "apply_base":
            if multires_mod is None:
                raise RuntimeError(
                    f"No Multires modifier found on '{name}'"
                )
            bpy.ops.object.multires_base_apply(modifier=multires_mod.name)

    # Gather current state
    mod_info = {}
    if multires_mod is not None:
        mod_info = {
            "modifier_name": multires_mod.name,
            "total_levels": multires_mod.total_levels,
            "sculpt_levels": multires_mod.sculpt_levels,
            "render_levels": multires_mod.render_levels,
            "levels": multires_mod.levels,
        }

    return {
        "object_name": name,
        "action": action,
        "modifier": mod_info,
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


# ---------------------------------------------------------------------------
# Modifier stack operations (from master)
# ---------------------------------------------------------------------------

MODIFIER_DEFAULTS: dict[str, dict] = {
    "SUBSURF": {"levels": 2, "render_levels": 3, "quality": 3},
    "BEVEL": {"width": 0.02, "segments": 3, "limit_method": "ANGLE", "angle_limit": 0.524},
    "MIRROR": {"use_axis": [True, False, False], "use_bisect_axis": [False, False, False]},
    "ARRAY": {"count": 3, "relative_offset_displace": [1.0, 0.0, 0.0]},
    "SOLIDIFY": {"thickness": 0.1, "offset": -1.0},
    "DECIMATE": {"ratio": 0.5, "decimate_type": "COLLAPSE", "use_collapse_triangulate": True},
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


# ---------------------------------------------------------------------------
# Vertex colors, custom normals, edge data, shape keys
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
