"""Advanced modeling operations for AAA studio-quality workflows.

Implements Gemini/Codex gaps 34-43, Opus gaps 67-78 -- the advanced modeling
operations that close the gap with ZBrush/Maya/ProBuilder.

Provides:
- handle_symmetry_edit: Toggle symmetry editing on a mesh (gap #39)
- handle_loop_select: Select edge loop or ring (gap #40)
- handle_selection_modify: Grow/shrink selection (gap #40)
- handle_bridge_edges: Bridge edge loops + fill + grid fill (gap #41, #76)
- handle_modifier: Non-destructive modifier stack management (gap #42)
- handle_circularize: Circularize edge loop via LoopTools or fallback (gap #77)
- handle_insert_mesh: Insert detail meshes at surface points (gap #38)
- handle_alpha_stamp: Stamp alpha patterns onto surfaces (gap #37)
- handle_proportional_edit: Proportional editing with falloff (gap #25/GAP-06)
- handle_bisect: Bisect mesh with a plane (gap #26/GAP-07, #71)
- handle_mesh_checkpoint: Save/restore mesh state snapshots (gap #27/GAP-08)

Pure-logic helpers are exported for testing without Blender.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

try:
    import bmesh
    import bpy
    import mathutils
except ImportError:
    # Allow import for testing without Blender runtime
    bpy = None  # type: ignore[assignment]
    bmesh = None  # type: ignore[assignment]
    mathutils = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants & validation sets (pure-logic, testable without Blender)
# ---------------------------------------------------------------------------

VALID_SYMMETRY_AXES = frozenset({"X", "Y", "Z"})

VALID_LOOP_MODES = frozenset({"LOOP", "RING"})

VALID_SELECTION_ACTIONS = frozenset({"GROW", "SHRINK"})

VALID_BRIDGE_INTERPOLATIONS = frozenset({"LINEAR", "PATH", "SURFACE"})

VALID_MODIFIER_ACTIONS = frozenset({
    "add", "configure", "apply", "remove", "list", "reorder",
})

VALID_MODIFIER_TYPES = frozenset({
    "SUBSURF", "MIRROR", "ARRAY", "SOLIDIFY", "BEVEL",
    "BOOLEAN", "SHRINKWRAP", "SKIN", "REMESH", "DECIMATE",
    "SMOOTH", "CORRECTIVE_SMOOTH", "LAPLACIANSMOOTH", "WEIGHTED_NORMAL",
    "DISPLACE", "CURVE", "LATTICE", "MESH_DEFORM", "SURFACE_DEFORM",
    "CAST", "WAVE", "WARP", "CLOTH", "PARTICLE_SYSTEM",
    "SIMPLE_DEFORM", "WIREFRAME", "SCREW", "BUILD", "TRIANGULATE",
    "MULTIRES", "EDGE_SPLIT", "DATA_TRANSFER", "NORMAL_EDIT",
})

VALID_FALLOFF_TYPES = frozenset({
    "SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR", "CONSTANT", "RANDOM",
})

VALID_ALPHA_PATTERNS = frozenset({
    "scales", "scars", "rivets", "cracks", "bark", "custom",
})

VALID_CHECKPOINT_ACTIONS = frozenset({"save", "restore", "list", "clear"})

VALID_PROPORTIONAL_TRANSFORMS = frozenset({"TRANSLATE", "ROTATE", "SCALE"})


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def validate_symmetry_params(params: dict) -> tuple[str, str, bool]:
    """Validate and extract symmetry edit parameters.

    Returns (object_name, axis, enable).
    Raises ValueError for invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    axis = params.get("axis", "X").upper()
    if axis not in VALID_SYMMETRY_AXES:
        raise ValueError(
            f"Invalid axis: {axis!r}. Valid: {sorted(VALID_SYMMETRY_AXES)}"
        )
    enable = params.get("enable", True)
    return object_name, axis, bool(enable)


def validate_loop_select_params(params: dict) -> tuple[str, int, str, bool]:
    """Validate and extract loop select parameters.

    Returns (object_name, edge_index, mode, extend).
    Raises ValueError for invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    edge_index = params.get("edge_index")
    if edge_index is None:
        raise ValueError("edge_index is required for loop selection")
    edge_index = int(edge_index)
    if edge_index < 0:
        raise ValueError(f"edge_index must be non-negative, got {edge_index}")
    mode = params.get("mode", "LOOP").upper()
    if mode not in VALID_LOOP_MODES:
        raise ValueError(
            f"Invalid loop mode: {mode!r}. Valid: {sorted(VALID_LOOP_MODES)}"
        )
    extend = bool(params.get("extend", False))
    return object_name, edge_index, mode, extend


def validate_selection_modify_params(params: dict) -> tuple[str, str, int]:
    """Validate and extract selection modify parameters.

    Returns (object_name, action, steps).
    Raises ValueError for invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    action = params.get("action", "GROW").upper()
    if action not in VALID_SELECTION_ACTIONS:
        raise ValueError(
            f"Invalid selection action: {action!r}. "
            f"Valid: {sorted(VALID_SELECTION_ACTIONS)}"
        )
    steps = int(params.get("steps", 1))
    if steps < 1:
        raise ValueError(f"steps must be >= 1, got {steps}")
    return object_name, action, steps


def validate_bridge_params(params: dict) -> tuple[str, int, int, str]:
    """Validate and extract bridge edge loop parameters.

    Returns (object_name, segments, twist, interpolation).
    Raises ValueError for invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    segments = int(params.get("segments", 1))
    if segments < 1:
        raise ValueError(f"segments must be >= 1, got {segments}")
    twist = int(params.get("twist", 0))
    interpolation = params.get("interpolation", "LINEAR").upper()
    if interpolation not in VALID_BRIDGE_INTERPOLATIONS:
        raise ValueError(
            f"Invalid interpolation: {interpolation!r}. "
            f"Valid: {sorted(VALID_BRIDGE_INTERPOLATIONS)}"
        )
    return object_name, segments, twist, interpolation


def validate_modifier_params(params: dict) -> dict:
    """Validate modifier parameters and return cleaned param dict.

    Returns dict with validated keys.
    Raises ValueError for invalid params.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    action = params.get("action", "").lower()
    if action not in VALID_MODIFIER_ACTIONS:
        raise ValueError(
            f"Invalid modifier action: {action!r}. "
            f"Valid: {sorted(VALID_MODIFIER_ACTIONS)}"
        )

    result = {"object_name": object_name, "action": action}

    if action == "add":
        modifier_type = params.get("modifier_type", "").upper()
        if modifier_type not in VALID_MODIFIER_TYPES:
            raise ValueError(
                f"Invalid modifier_type: {modifier_type!r}. "
                f"Valid: {sorted(VALID_MODIFIER_TYPES)}"
            )
        result["modifier_type"] = modifier_type
        result["modifier_name"] = params.get("modifier_name", "")
        result["settings"] = params.get("settings", {})

    elif action in ("configure", "apply", "remove"):
        modifier_name = params.get("modifier_name")
        if not modifier_name:
            raise ValueError(f"modifier_name is required for '{action}' action")
        result["modifier_name"] = modifier_name
        if action == "configure":
            result["settings"] = params.get("settings", {})

    elif action == "reorder":
        modifier_name = params.get("modifier_name")
        if not modifier_name:
            raise ValueError("modifier_name is required for 'reorder' action")
        index = params.get("index")
        if index is None:
            raise ValueError("index is required for 'reorder' action")
        result["modifier_name"] = modifier_name
        result["index"] = int(index)

    return result


def validate_circularize_params(params: dict) -> tuple[str, bool]:
    """Validate and extract circularize parameters.

    Returns (object_name, flatten).
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    flatten = bool(params.get("flatten", True))
    return object_name, flatten


def validate_insert_mesh_params(params: dict) -> tuple[str, str, list[dict], bool]:
    """Validate and extract insert mesh parameters.

    Returns (object_name, insert_mesh_name, points, align_to_normal).
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    insert_mesh_name = params.get("insert_mesh_name")
    if not insert_mesh_name:
        raise ValueError("insert_mesh_name is required")
    points = params.get("points", [])
    if not points:
        raise ValueError("At least one point is required in 'points'")
    for i, pt in enumerate(points):
        if "position" not in pt:
            raise ValueError(f"Point {i} missing 'position'")
    align_to_normal = bool(params.get("align_to_normal", True))
    return object_name, insert_mesh_name, points, align_to_normal


def validate_alpha_stamp_params(params: dict) -> dict:
    """Validate and extract alpha stamp parameters.

    Returns cleaned param dict.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    pattern = params.get("pattern", "scales").lower()
    if pattern not in VALID_ALPHA_PATTERNS:
        raise ValueError(
            f"Invalid pattern: {pattern!r}. "
            f"Valid: {sorted(VALID_ALPHA_PATTERNS)}"
        )
    if pattern == "custom" and not params.get("custom_image_path"):
        raise ValueError("custom_image_path is required when pattern='custom'")
    position = params.get("position", [0, 0, 0])
    if len(position) != 3:
        raise ValueError("position must be [x, y, z]")
    radius = float(params.get("radius", 1.0))
    if radius <= 0:
        raise ValueError(f"radius must be positive, got {radius}")
    depth = float(params.get("depth", 0.1))
    return {
        "object_name": object_name,
        "pattern": pattern,
        "position": position,
        "radius": radius,
        "depth": depth,
        "custom_image_path": params.get("custom_image_path"),
    }


def validate_proportional_edit_params(params: dict) -> dict:
    """Validate and extract proportional edit parameters.

    Returns cleaned param dict.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    vertex_indices = params.get("vertex_indices", [])
    if not vertex_indices:
        raise ValueError("vertex_indices list is required and must not be empty")
    transform_type = params.get("transform_type", "TRANSLATE").upper()
    if transform_type not in VALID_PROPORTIONAL_TRANSFORMS:
        raise ValueError(
            f"Invalid transform_type: {transform_type!r}. "
            f"Valid: {sorted(VALID_PROPORTIONAL_TRANSFORMS)}"
        )
    value = params.get("value", [0, 0, 0])
    falloff_type = params.get("falloff_type", "SMOOTH").upper()
    if falloff_type not in VALID_FALLOFF_TYPES:
        raise ValueError(
            f"Invalid falloff_type: {falloff_type!r}. "
            f"Valid: {sorted(VALID_FALLOFF_TYPES)}"
        )
    falloff_radius = float(params.get("falloff_radius", 2.0))
    if falloff_radius <= 0:
        raise ValueError(f"falloff_radius must be positive, got {falloff_radius}")
    connected_only = bool(params.get("connected_only", False))
    return {
        "object_name": object_name,
        "vertex_indices": vertex_indices,
        "transform_type": transform_type,
        "value": value,
        "falloff_type": falloff_type,
        "falloff_radius": falloff_radius,
        "connected_only": connected_only,
    }


def validate_bisect_params(params: dict) -> dict:
    """Validate and extract bisect parameters.

    Returns cleaned param dict with normalized plane_normal.
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    plane_point = params.get("plane_point", [0, 0, 0])
    if len(plane_point) != 3:
        raise ValueError("plane_point must be [x, y, z]")
    plane_normal = list(params.get("plane_normal", [0, 0, 1]))
    if len(plane_normal) != 3:
        raise ValueError("plane_normal must be [x, y, z]")
    # Normalize the normal vector
    length = math.sqrt(sum(c * c for c in plane_normal))
    if length < 1e-10:
        raise ValueError("plane_normal must not be a zero vector")
    plane_normal = [c / length for c in plane_normal]
    return {
        "object_name": object_name,
        "plane_point": plane_point,
        "plane_normal": plane_normal,
        "clear_inner": bool(params.get("clear_inner", False)),
        "clear_outer": bool(params.get("clear_outer", False)),
        "fill": bool(params.get("fill", False)),
    }


def validate_checkpoint_params(params: dict) -> tuple[str, str, str]:
    """Validate and extract checkpoint parameters.

    Returns (object_name, action, checkpoint_name).
    """
    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")
    action = params.get("action", "save").lower()
    if action not in VALID_CHECKPOINT_ACTIONS:
        raise ValueError(
            f"Invalid checkpoint action: {action!r}. "
            f"Valid: {sorted(VALID_CHECKPOINT_ACTIONS)}"
        )
    checkpoint_name = params.get(
        "checkpoint_name",
        f"checkpoint_{int(time.time())}",
    )
    return object_name, action, checkpoint_name


def normalize_vector(v: list[float] | tuple[float, ...]) -> list[float]:
    """Normalize a 3D vector. Returns [0,0,0] for zero-length vectors."""
    length = math.sqrt(sum(c * c for c in v))
    if length < 1e-10:
        return [0.0, 0.0, 0.0]
    return [c / length for c in v]


def compute_falloff_weight(
    distance: float,
    radius: float,
    falloff_type: str,
) -> float:
    """Compute proportional editing falloff weight for a given distance.

    Args:
        distance: Distance from the affected vertex to the center vertex.
        radius: The falloff radius.
        falloff_type: One of SMOOTH, SPHERE, ROOT, SHARP, LINEAR, CONSTANT, RANDOM.

    Returns:
        Weight in [0.0, 1.0] range. 0.0 means no influence.
    """
    if distance >= radius or radius <= 0:
        return 0.0

    t = distance / radius  # Normalized distance [0, 1)

    if falloff_type == "CONSTANT":
        return 1.0
    elif falloff_type == "LINEAR":
        return 1.0 - t
    elif falloff_type == "SHARP":
        return (1.0 - t) ** 2
    elif falloff_type == "ROOT":
        return math.sqrt(1.0 - t)
    elif falloff_type == "SPHERE":
        return math.sqrt(1.0 - t * t)
    elif falloff_type == "SMOOTH":
        # Smooth falloff using cosine interpolation
        return 0.5 * (1.0 + math.cos(math.pi * t))
    elif falloff_type == "RANDOM":
        # Deterministic pseudo-random based on distance for reproducibility
        # Uses a simple hash-like approach
        seed_val = int(distance * 10000) % 997
        return (1.0 - t) * ((seed_val % 100) / 100.0)
    else:
        return 0.0


def compute_proportional_weights(
    vertex_positions: list[tuple[float, float, float]],
    center_indices: list[int],
    falloff_radius: float,
    falloff_type: str,
) -> dict[int, float]:
    """Compute proportional editing weights for all vertices.

    Args:
        vertex_positions: List of (x, y, z) for every vertex.
        center_indices: Indices of the selected/center vertices (weight=1.0).
        falloff_radius: The influence radius.
        falloff_type: Falloff curve type.

    Returns:
        Dict mapping vertex index to weight (only non-zero entries).
    """
    weights: dict[int, float] = {}
    center_set = set(center_indices)

    # Pre-compute center positions
    center_positions = [vertex_positions[i] for i in center_indices]

    for vi, pos in enumerate(vertex_positions):
        if vi in center_set:
            weights[vi] = 1.0
            continue

        # Find minimum distance to any center vertex
        min_dist = float("inf")
        for cp in center_positions:
            dx = pos[0] - cp[0]
            dy = pos[1] - cp[1]
            dz = pos[2] - cp[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < min_dist:
                min_dist = dist

        w = compute_falloff_weight(min_dist, falloff_radius, falloff_type)
        if w > 0.0:
            weights[vi] = w

    return weights


def compute_bisect_side(
    vertex_position: tuple[float, float, float],
    plane_point: list[float],
    plane_normal: list[float],
) -> str:
    """Determine which side of a bisect plane a vertex is on.

    Returns 'inner' (negative side), 'outer' (positive side), or 'on_plane'.
    """
    dx = vertex_position[0] - plane_point[0]
    dy = vertex_position[1] - plane_point[1]
    dz = vertex_position[2] - plane_point[2]
    dot = dx * plane_normal[0] + dy * plane_normal[1] + dz * plane_normal[2]
    if abs(dot) < 1e-6:
        return "on_plane"
    return "outer" if dot > 0 else "inner"


# ---------------------------------------------------------------------------
# Alpha stamp pattern generators (pure-logic, returns displacement maps)
# ---------------------------------------------------------------------------

_PATTERN_GENERATORS: dict[str, Any] = {}


def _generate_pattern_image(
    pattern: str,
    resolution: int = 64,
) -> list[list[float]]:
    """Generate a 2D displacement pattern as a resolution x resolution grid.

    Values in [0.0, 1.0] where 1.0 = full depth displacement.
    Pure-logic, testable without Blender.
    """
    grid: list[list[float]] = []
    center = resolution / 2.0

    if pattern == "scales":
        for y in range(resolution):
            row: list[float] = []
            for x in range(resolution):
                # Overlapping semicircles creating fish-scale pattern
                nx = (x / resolution) * 4.0
                ny = (y / resolution) * 4.0
                # Offset every other row
                offset = 0.5 if int(ny) % 2 else 0.0
                fx = (nx + offset) % 1.0 - 0.5
                fy = ny % 1.0 - 0.5
                d = math.sqrt(fx * fx + fy * fy)
                val = max(0.0, 1.0 - d * 2.5) if fy > -0.1 else 0.0
                row.append(val)
            grid.append(row)

    elif pattern == "scars":
        for y in range(resolution):
            row = []
            for x in range(resolution):
                dx = x - center
                dy = y - center
                # Elongated along X axis with noise-like variation
                dist = abs(dy) / max(resolution * 0.05, 1.0)
                val = max(0.0, 1.0 - dist) * (0.8 + 0.2 * math.sin(dx * 0.3))
                # Taper at edges
                edge_fade = 1.0 - (abs(dx) / center) ** 2
                val *= max(0.0, edge_fade)
                row.append(max(0.0, min(1.0, val)))
            grid.append(row)

    elif pattern == "rivets":
        rivet_spacing = resolution / 4.0
        for y in range(resolution):
            row = []
            for x in range(resolution):
                min_d = float("inf")
                for ry in range(5):
                    for rx in range(5):
                        cx = rx * rivet_spacing
                        cy = ry * rivet_spacing
                        d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                        if d < min_d:
                            min_d = d
                rivet_r = rivet_spacing * 0.2
                val = max(0.0, 1.0 - min_d / rivet_r) if min_d < rivet_r else 0.0
                row.append(val)
            grid.append(row)

    elif pattern == "cracks":
        for y in range(resolution):
            row = []
            for x in range(resolution):
                dx = x - center
                dy = y - center
                # Radial cracks from center
                angle = math.atan2(dy, dx)
                dist = math.sqrt(dx * dx + dy * dy) / center
                # Create crack lines at regular angular intervals
                crack_val = abs(math.sin(angle * 5.0))
                crack_val = max(0.0, 1.0 - crack_val * 8.0)
                # Fade with distance
                crack_val *= min(1.0, dist * 1.5)
                crack_val *= max(0.0, 1.0 - dist)
                row.append(max(0.0, min(1.0, crack_val)))
            grid.append(row)

    elif pattern == "bark":
        for y in range(resolution):
            row = []
            for x in range(resolution):
                ny = (y / resolution) * 8.0
                nx = (x / resolution) * 2.0
                # Vertical ridges with horizontal variation
                ridge = abs(math.sin(nx * math.pi))
                grain = 0.5 + 0.5 * math.sin(ny * math.pi * 0.7 + nx * 2.0)
                val = ridge * 0.7 + grain * 0.3
                row.append(max(0.0, min(1.0, val)))
            grid.append(row)

    else:
        # Default: flat (no displacement)
        grid = [[0.0] * resolution for _ in range(resolution)]

    return grid


# ---------------------------------------------------------------------------
# Checkpoint storage (module-level, persists during Blender session)
# ---------------------------------------------------------------------------

_MESH_CHECKPOINTS: dict[str, list[dict[str, Any]]] = {}


def get_checkpoint_storage() -> dict[str, list[dict[str, Any]]]:
    """Return the checkpoint storage dict (for testing)."""
    return _MESH_CHECKPOINTS


def clear_all_checkpoints() -> None:
    """Clear all checkpoint data (for testing)."""
    _MESH_CHECKPOINTS.clear()


def _serialize_mesh_data_pure(
    verts: list[tuple[float, float, float]],
    edges: list[tuple[int, int]],
    faces: list[tuple[int, ...]],
    checkpoint_name: str,
) -> dict[str, Any]:
    """Create a serialized mesh checkpoint from raw geometry data.

    Pure-logic helper for testing.
    """
    return {
        "name": checkpoint_name,
        "timestamp": time.time(),
        "vertex_count": len(verts),
        "edge_count": len(edges),
        "face_count": len(faces),
        "vertices": list(verts),
        "edges": list(edges),
        "faces": list(faces),
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy + bmesh at runtime)
# ---------------------------------------------------------------------------


def _get_mesh_object(name: str | None) -> Any:
    """Validate and return a mesh object by name."""
    if bpy is None:
        raise RuntimeError("Blender (bpy) not available")
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")
    return obj


def _get_3d_context() -> dict:
    """Get 3D viewport context override or raise."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return {"area": area, "region": region}
    raise RuntimeError("No 3D Viewport available for this operation")


def handle_symmetry_edit(params: dict) -> dict:
    """Toggle symmetry editing on a mesh object (gap #39).

    Params:
        object_name: Name of the Blender mesh object.
        axis: 'X', 'Y', or 'Z' (default 'X').
        enable: bool (default True).

    Returns dict with current symmetry state for all axes.
    """
    object_name, axis, enable = validate_symmetry_params(params)
    obj = _get_mesh_object(object_name)

    # Set the mesh mirror flag for the requested axis
    mesh = obj.data
    if axis == "X":
        mesh.use_mirror_x = enable
    elif axis == "Y":
        mesh.use_mirror_y = enable
    elif axis == "Z":
        mesh.use_mirror_topology = enable  # Z uses mirror_topology in some contexts

    # Also set the object-level symmetry flags (used in sculpt/edit modes)
    if hasattr(obj, "use_mesh_mirror_x"):
        if axis == "X":
            obj.use_mesh_mirror_x = enable
        elif axis == "Y":
            obj.use_mesh_mirror_y = enable
        elif axis == "Z":
            obj.use_mesh_mirror_z = enable

    return {
        "object_name": object_name,
        "axis": axis,
        "enabled": enable,
        "symmetry_state": {
            "X": getattr(mesh, "use_mirror_x", False),
            "Y": getattr(mesh, "use_mirror_y", False),
            "Z": getattr(mesh, "use_mirror_topology", False),
        },
    }


def handle_loop_select(params: dict) -> dict:
    """Select edge loop or ring (gap #40).

    Params:
        object_name: Name of the Blender mesh object.
        edge_index: Starting edge index.
        mode: 'LOOP' or 'RING' (default 'LOOP').
        extend: Whether to extend existing selection (default False).

    Returns dict with selected edge/vertex/face counts.
    """
    object_name, edge_index, mode, extend = validate_loop_select_params(params)
    obj = _get_mesh_object(object_name)

    bm_local = bmesh.new()
    try:
        bm_local.from_mesh(obj.data)
        bm_local.edges.ensure_lookup_table()
        bm_local.verts.ensure_lookup_table()
        bm_local.faces.ensure_lookup_table()

        if edge_index >= len(bm_local.edges):
            raise ValueError(
                f"edge_index {edge_index} out of range "
                f"(mesh has {len(bm_local.edges)} edges)"
            )

        # Clear selection unless extending
        if not extend:
            for v in bm_local.verts:
                v.select = False
            for e in bm_local.edges:
                e.select = False
            for f in bm_local.faces:
                f.select = False

        start_edge = bm_local.edges[edge_index]

        if mode == "LOOP":
            # Walk edge loop: follow edges through quads
            loop_edges = _walk_edge_loop(bm_local, start_edge)
            for e in loop_edges:
                e.select = True
                for v in e.verts:
                    v.select = True
        else:
            # Edge ring: edges parallel to the start edge in a loop
            ring_edges = _walk_edge_ring(bm_local, start_edge)
            for e in ring_edges:
                e.select = True
                for v in e.verts:
                    v.select = True

        # Select faces where all edges are selected
        for f in bm_local.faces:
            if all(e.select for e in f.edges):
                f.select = True

        selected_verts = sum(1 for v in bm_local.verts if v.select)
        selected_edges = sum(1 for e in bm_local.edges if e.select)
        selected_faces = sum(1 for f in bm_local.faces if f.select)

        bm_local.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm_local.free()

    return {
        "object_name": object_name,
        "mode": mode,
        "edge_index": edge_index,
        "selected_verts": selected_verts,
        "selected_edges": selected_edges,
        "selected_faces": selected_faces,
    }


def _walk_edge_loop(bm_local: Any, start_edge: Any) -> list:
    """Walk an edge loop through quad faces starting from an edge.

    An edge loop follows edges that cross quad faces: from one edge, find
    the opposite edge in each connected quad face.
    """
    visited: set[int] = set()
    loop_edges = []
    queue = [start_edge]

    while queue:
        edge = queue.pop()
        if edge.index in visited:
            continue
        visited.add(edge.index)
        loop_edges.append(edge)

        # For each linked face that is a quad, find the opposite edge
        for face in edge.link_faces:
            if len(face.verts) != 4:
                continue
            face_edges = list(face.edges)
            idx = face_edges.index(edge)
            # Opposite edge in a quad is at index + 2
            opposite = face_edges[(idx + 2) % 4]
            if opposite.index not in visited:
                queue.append(opposite)

    return loop_edges


def _walk_edge_ring(bm_local: Any, start_edge: Any) -> list:
    """Walk an edge ring: edges that share faces with the start edge
    and are perpendicular to it within quad topology.

    An edge ring follows adjacent edges in quad faces that are parallel
    to the starting edge.
    """
    visited: set[int] = set()
    ring_edges = []
    queue = [start_edge]

    while queue:
        edge = queue.pop()
        if edge.index in visited:
            continue
        visited.add(edge.index)
        ring_edges.append(edge)

        # For each vertex of this edge, look for continuation through quads
        for vert in edge.verts:
            for face in vert.link_faces:
                if len(face.verts) != 4:
                    continue
                if edge not in face.edges:
                    continue
                # Find the edge in this face that shares the vertex but is not
                # the current edge and is not adjacent (i.e., opposite vertex)
                face_edges = list(face.edges)
                for fe in face_edges:
                    if fe.index == edge.index:
                        continue
                    if vert not in fe.verts:
                        continue
                    # This is an adjacent edge sharing the vertex
                    # The ring continues through the other adjacent edge
                    pass
                # Find the edge that does NOT share any vertex with current edge
                for fe in face_edges:
                    if fe.index in visited:
                        continue
                    shared_verts = set(fe.verts) & set(edge.verts)
                    if len(shared_verts) == 0:
                        # This is the parallel edge (ring continuation)
                        queue.append(fe)

    return ring_edges


def handle_selection_modify(params: dict) -> dict:
    """Grow or shrink mesh selection (gap #40).

    Params:
        object_name: Name of the Blender mesh object.
        action: 'GROW' or 'SHRINK' (default 'GROW').
        steps: Number of grow/shrink iterations (default 1).

    Returns dict with updated selection counts.
    """
    object_name, action, steps = validate_selection_modify_params(params)
    obj = _get_mesh_object(object_name)

    ctx = _get_3d_context()
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="EDIT")
        for _ in range(steps):
            if action == "GROW":
                bpy.ops.mesh.select_more()
            else:
                bpy.ops.mesh.select_less()
        bpy.ops.object.mode_set(mode="OBJECT")

    # Count final selection
    bm_local = bmesh.new()
    try:
        bm_local.from_mesh(obj.data)
        selected_verts = sum(1 for v in bm_local.verts if v.select)
        selected_edges = sum(1 for e in bm_local.edges if e.select)
        selected_faces = sum(1 for f in bm_local.faces if f.select)
    finally:
        bm_local.free()

    return {
        "object_name": object_name,
        "action": action,
        "steps": steps,
        "selected_verts": selected_verts,
        "selected_edges": selected_edges,
        "selected_faces": selected_faces,
    }


def handle_bridge_edges(params: dict) -> dict:
    """Bridge two edge loops, fill holes, or grid fill (gap #41, #76).

    Params:
        object_name: Name of the Blender mesh object.
        segments: Number of bridge segments (default 1).
        twist: Twist offset (default 0).
        interpolation: 'LINEAR', 'PATH', or 'SURFACE' (default 'LINEAR').
        fill_mode: Optional -- 'bridge' (default), 'fill', or 'grid_fill'.

    Returns dict with vertex/face counts after operation.
    """
    object_name, segments, twist, interpolation = validate_bridge_params(params)
    fill_mode = params.get("fill_mode", "bridge").lower()
    obj = _get_mesh_object(object_name)

    ctx = _get_3d_context()
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    with bpy.context.temp_override(**ctx):
        bpy.ops.object.mode_set(mode="EDIT")

        if fill_mode == "fill":
            bpy.ops.mesh.fill()
        elif fill_mode == "grid_fill":
            bpy.ops.mesh.fill_grid(
                span=segments,
                offset=twist,
            )
        else:
            bpy.ops.mesh.bridge_edge_loops(
                type=interpolation,
                number_cuts=segments - 1,
                twist=twist,
                interpolation=interpolation,
            )

        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": object_name,
        "fill_mode": fill_mode,
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


def handle_modifier(params: dict) -> dict:
    """Non-destructive modifier stack management (gap #42).

    Params:
        object_name: Name of the Blender mesh object.
        action: 'add', 'configure', 'apply', 'remove', 'list', 'reorder'.
        modifier_type: Blender modifier type for 'add' (e.g. SUBSURF, MIRROR).
        modifier_name: Name of modifier for configure/apply/remove/reorder.
        settings: Dict of property name -> value for add/configure.
        index: Target position for 'reorder'.

    Returns dict with modifier info and current stack state.
    """
    validated = validate_modifier_params(params)
    object_name = validated["object_name"]
    action = validated["action"]
    obj = _get_mesh_object(object_name)

    if action == "list":
        mods = []
        for mod in obj.modifiers:
            mods.append({
                "name": mod.name,
                "type": mod.type,
                "show_viewport": mod.show_viewport,
                "show_render": mod.show_render,
            })
        return {
            "object_name": object_name,
            "action": "list",
            "modifiers": mods,
            "count": len(mods),
        }

    elif action == "add":
        modifier_type = validated["modifier_type"]
        modifier_name = validated.get("modifier_name") or modifier_type.title()
        settings = validated.get("settings", {})

        mod = obj.modifiers.new(name=modifier_name, type=modifier_type)

        # Apply settings
        applied_settings: list[str] = []
        failed_settings: list[str] = []
        for key, value in settings.items():
            if hasattr(mod, key):
                try:
                    setattr(mod, key, value)
                    applied_settings.append(key)
                except (TypeError, AttributeError) as exc:
                    failed_settings.append(key)
                    logger.warning(
                        "Failed to set modifier %s.%s on %s: %s",
                        modifier_name,
                        key,
                        object_name,
                        exc,
                    )
            else:
                failed_settings.append(key)
                logger.warning(
                    "Modifier %s on %s does not support setting '%s'",
                    modifier_name,
                    object_name,
                    key,
                )

        return {
            "object_name": object_name,
            "action": "add",
            "modifier_name": mod.name,
            "modifier_type": modifier_type,
            "settings_applied": applied_settings,
            "failed_settings": failed_settings,
        }

    elif action == "configure":
        modifier_name = validated["modifier_name"]
        settings = validated.get("settings", {})
        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            raise ValueError(
                f"Modifier '{modifier_name}' not found on '{object_name}'. "
                f"Available: {[m.name for m in obj.modifiers]}"
            )

        applied_settings: list[str] = []
        failed_settings: list[str] = []
        for key, value in settings.items():
            if hasattr(mod, key):
                try:
                    setattr(mod, key, value)
                    applied_settings.append(key)
                except (TypeError, AttributeError) as exc:
                    failed_settings.append(key)
                    logger.warning(
                        "Failed to configure modifier %s.%s on %s: %s",
                        modifier_name,
                        key,
                        object_name,
                        exc,
                    )
            else:
                failed_settings.append(key)
                logger.warning(
                    "Modifier %s on %s does not support setting '%s'",
                    modifier_name,
                    object_name,
                    key,
                )

        return {
            "object_name": object_name,
            "action": "configure",
            "modifier_name": modifier_name,
            "applied_settings": applied_settings,
            "failed_settings": failed_settings,
        }

    elif action == "apply":
        modifier_name = validated["modifier_name"]
        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            raise ValueError(
                f"Modifier '{modifier_name}' not found on '{object_name}'"
            )

        ctx = _get_3d_context()
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.modifier_apply(modifier=modifier_name)

        return {
            "object_name": object_name,
            "action": "apply",
            "modifier_name": modifier_name,
            "vertex_count": len(obj.data.vertices),
            "face_count": len(obj.data.polygons),
        }

    elif action == "remove":
        modifier_name = validated["modifier_name"]
        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            raise ValueError(
                f"Modifier '{modifier_name}' not found on '{object_name}'"
            )
        obj.modifiers.remove(mod)

        return {
            "object_name": object_name,
            "action": "remove",
            "modifier_name": modifier_name,
            "remaining_modifiers": [m.name for m in obj.modifiers],
        }

    elif action == "reorder":
        modifier_name = validated["modifier_name"]
        target_index = validated["index"]
        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            raise ValueError(
                f"Modifier '{modifier_name}' not found on '{object_name}'"
            )

        # Move modifier to target position
        current_idx = list(obj.modifiers).index(mod)
        ctx = _get_3d_context()
        bpy.context.view_layer.objects.active = obj
        with bpy.context.temp_override(**ctx):
            # Move up or down to reach target index
            if target_index < current_idx:
                for _ in range(current_idx - target_index):
                    bpy.ops.object.modifier_move_up(modifier=modifier_name)
            elif target_index > current_idx:
                for _ in range(target_index - current_idx):
                    bpy.ops.object.modifier_move_down(modifier=modifier_name)

        return {
            "object_name": object_name,
            "action": "reorder",
            "modifier_name": modifier_name,
            "new_index": target_index,
            "modifier_stack": [m.name for m in obj.modifiers],
        }

    raise ValueError(f"Unhandled modifier action: {action}")


def handle_circularize(params: dict) -> dict:
    """Make selected edge loop perfectly circular (gap #77).

    Params:
        object_name: Name of the Blender mesh object.
        flatten: Whether to project onto best-fit plane (default True).

    Uses LoopTools addon if available, otherwise computes centroid + radius
    and projects selected vertices to a best-fit circle.

    Returns dict with vertex count and circularize method used.
    """
    object_name, flatten = validate_circularize_params(params)
    obj = _get_mesh_object(object_name)

    # Try LoopTools first
    looptools_available = False
    try:
        # Check if LoopTools addon is enabled
        if hasattr(bpy.ops, "mesh") and hasattr(bpy.ops.mesh, "looptools_circle"):
            looptools_available = True
    except (AttributeError, RuntimeError):
        pass

    if looptools_available:
        ctx = _get_3d_context()
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.looptools_circle(
                fit="best",
                flatten=flatten,
                influence=100,
            )
            bpy.ops.object.mode_set(mode="OBJECT")
        method = "looptools"
    else:
        # Fallback: manual circularize via bmesh
        bm_local = bmesh.new()
        try:
            bm_local.from_mesh(obj.data)
            bm_local.verts.ensure_lookup_table()

            selected = [v for v in bm_local.verts if v.select]
            if len(selected) < 3:
                raise ValueError(
                    "Need at least 3 selected vertices to circularize"
                )

            # Compute centroid
            centroid = mathutils.Vector((0, 0, 0))
            for v in selected:
                centroid += v.co
            centroid /= len(selected)

            # Compute average radius
            avg_radius = sum(
                (v.co - centroid).length for v in selected
            ) / len(selected)

            # Compute best-fit normal (average of cross products)
            normal = mathutils.Vector((0, 0, 0))
            for i in range(len(selected)):
                v0 = selected[i].co - centroid
                v1 = selected[(i + 1) % len(selected)].co - centroid
                normal += v0.cross(v1)
            if normal.length > 1e-8:
                normal.normalize()
            else:
                normal = mathutils.Vector((0, 0, 1))

            # Project each vertex to the circle
            for v in selected:
                # Project to plane if flatten
                if flatten:
                    offset = v.co - centroid
                    offset -= normal * offset.dot(normal)
                else:
                    offset = v.co - centroid

                if offset.length > 1e-8:
                    offset.normalize()
                    v.co = centroid + offset * avg_radius
                    if flatten:
                        # Ensure on plane
                        plane_offset = v.co - centroid
                        v.co -= normal * plane_offset.dot(normal)

            bm_local.to_mesh(obj.data)
            obj.data.update()
        finally:
            bm_local.free()
        method = "fallback_bmesh"

    return {
        "object_name": object_name,
        "method": method,
        "flatten": flatten,
        "vertex_count": len(obj.data.vertices),
    }


def handle_insert_mesh(params: dict) -> dict:
    """Place detail meshes at specified surface points (gap #38).

    Params:
        object_name: Target surface object name.
        insert_mesh_name: Source mesh to insert (must exist in scene).
        points: List of {position: [x,y,z], normal: [x,y,z], scale: float}.
        align_to_normal: Align instances to surface normal (default True).

    Returns dict with instance count and names.
    """
    object_name, insert_mesh_name, points, align_to_normal = (
        validate_insert_mesh_params(params)
    )
    # Validate target exists
    _get_mesh_object(object_name)

    source = bpy.data.objects.get(insert_mesh_name)
    if source is None:
        raise ValueError(f"Insert mesh not found: {insert_mesh_name}")

    instance_names: list[str] = []

    for i, pt in enumerate(points):
        position = mathutils.Vector(pt["position"])
        normal = mathutils.Vector(pt.get("normal", [0, 0, 1]))
        scale_val = float(pt.get("scale", 1.0))

        # Duplicate the source mesh
        new_obj = source.copy()
        new_obj.data = source.data.copy()
        new_obj.name = f"{insert_mesh_name}_insert_{i:03d}"
        bpy.context.collection.objects.link(new_obj)

        # Position
        new_obj.location = position

        # Scale
        new_obj.scale = (scale_val, scale_val, scale_val)

        # Align to normal if requested
        if align_to_normal and normal.length > 1e-8:
            normal.normalize()
            up = mathutils.Vector((0, 0, 1))
            if abs(normal.dot(up)) > 0.999:
                up = mathutils.Vector((0, 1, 0))
            rot_quat = up.rotation_difference(normal)
            new_obj.rotation_euler = rot_quat.to_euler()

        instance_names.append(new_obj.name)

    return {
        "object_name": object_name,
        "insert_mesh_name": insert_mesh_name,
        "instances_created": len(instance_names),
        "instance_names": instance_names,
    }


def handle_alpha_stamp(params: dict) -> dict:
    """Stamp custom patterns onto surfaces using displacement (gap #37).

    Params:
        object_name: Name of the Blender mesh object.
        pattern: 'scales', 'scars', 'rivets', 'cracks', 'bark', or 'custom'.
        position: [x, y, z] world coordinates for stamp center.
        radius: Stamp radius (default 1.0).
        depth: Displacement depth (default 0.1).
        custom_image_path: Path to custom image (required if pattern='custom').

    Returns dict with affected vertex count and modifier info.
    """
    validated = validate_alpha_stamp_params(params)
    object_name = validated["object_name"]
    obj = _get_mesh_object(object_name)

    pattern = validated["pattern"]
    position = mathutils.Vector(validated["position"])
    radius = validated["radius"]
    depth = validated["depth"]

    if pattern == "custom" and validated["custom_image_path"]:
        # Load custom image
        img = bpy.data.images.load(validated["custom_image_path"])
        img_name = img.name
    else:
        # Generate procedural pattern image
        resolution = 128
        grid = _generate_pattern_image(pattern, resolution)

        # Create Blender image from grid
        img_name = f"alpha_stamp_{pattern}"
        if img_name in bpy.data.images:
            img = bpy.data.images[img_name]
        else:
            img = bpy.data.images.new(img_name, resolution, resolution)

        # Fill image pixel data (RGBA)
        pixels = []
        for row in grid:
            for val in row:
                pixels.extend([val, val, val, 1.0])
        img.pixels[:] = pixels

    # Apply via displace modifier with vertex group for localization
    # First, create vertex group for affected area
    vg_name = f"stamp_{pattern}_{int(time.time())}"
    vg = obj.vertex_groups.new(name=vg_name)

    # Weight vertices by distance from stamp position
    for i, vert in enumerate(obj.data.vertices):
        world_co = obj.matrix_world @ mathutils.Vector(vert.co)
        dist = (world_co - position).length
        if dist < radius:
            weight = 1.0 - (dist / radius)
            vg.add([i], weight, "REPLACE")

    # Add displace modifier
    mod = obj.modifiers.new(name=f"AlphaStamp_{pattern}", type="DISPLACE")
    mod.texture_coords = "LOCAL"
    mod.vertex_group = vg_name
    mod.strength = depth
    mod.mid_level = 0.5

    # Create texture and assign the image
    tex_name = f"stamp_tex_{pattern}"
    if tex_name in bpy.data.textures:
        tex = bpy.data.textures[tex_name]
    else:
        tex = bpy.data.textures.new(tex_name, type="IMAGE")
    tex.image = img
    mod.texture = tex

    # Count affected vertices
    affected_verts = sum(
        1 for i in range(len(obj.data.vertices))
        if any(
            g.group == vg.index
            for g in obj.data.vertices[i].groups
        )
    )

    return {
        "object_name": object_name,
        "pattern": pattern,
        "affected_vertices": affected_verts,
        "modifier_name": mod.name,
        "vertex_group": vg_name,
        "image_name": img_name,
    }


def handle_proportional_edit(params: dict) -> dict:
    """Move/rotate/scale with proportional falloff (gap #25/GAP-06).

    Params:
        object_name: Name of the Blender mesh object.
        vertex_indices: List of center vertex indices.
        transform_type: 'TRANSLATE', 'ROTATE', or 'SCALE'.
        value: [x,y,z] for translate/scale, [angle_deg, axis_x, axis_y, axis_z] for rotate.
        falloff_type: 'SMOOTH', 'SPHERE', 'ROOT', 'SHARP', 'LINEAR', 'CONSTANT', 'RANDOM'.
        falloff_radius: Influence radius (default 2.0).
        connected_only: Only affect topologically connected verts (default False).

    Returns dict with affected vertex count and transform info.
    """
    validated = validate_proportional_edit_params(params)
    object_name = validated["object_name"]
    obj = _get_mesh_object(object_name)
    vertex_indices = validated["vertex_indices"]
    transform_type = validated["transform_type"]
    value = validated["value"]
    falloff_type = validated["falloff_type"]
    falloff_radius = validated["falloff_radius"]
    connected_only = validated["connected_only"]

    bm_local = bmesh.new()
    try:
        bm_local.from_mesh(obj.data)
        bm_local.verts.ensure_lookup_table()

        # Validate vertex indices
        max_idx = len(bm_local.verts) - 1
        for idx in vertex_indices:
            if idx < 0 or idx > max_idx:
                raise ValueError(
                    f"vertex_index {idx} out of range [0, {max_idx}]"
                )

        # Get all vertex positions
        positions = [(v.co.x, v.co.y, v.co.z) for v in bm_local.verts]

        # Compute weights
        if connected_only:
            # BFS from center vertices, only traverse edges
            weights = _compute_connected_weights(
                bm_local, vertex_indices, falloff_radius, falloff_type,
            )
        else:
            weights = compute_proportional_weights(
                positions, vertex_indices, falloff_radius, falloff_type,
            )

        # Apply transform weighted by proportional falloff
        affected = 0
        if transform_type == "TRANSLATE":
            offset = mathutils.Vector(value)
            for vi, w in weights.items():
                bm_local.verts[vi].co += offset * w
                affected += 1

        elif transform_type == "ROTATE":
            # value = [angle_degrees, axis_x, axis_y, axis_z] or just [angle_degrees]
            if len(value) >= 4:
                angle_deg = value[0]
                rot_axis = mathutils.Vector(value[1:4]).normalized()
            else:
                angle_deg = value[0] if len(value) >= 1 else 0.0
                rot_axis = mathutils.Vector((0, 0, 1))

            # Compute center of selected vertices
            center = mathutils.Vector((0, 0, 0))
            for idx in vertex_indices:
                center += bm_local.verts[idx].co
            center /= len(vertex_indices)

            for vi, w in weights.items():
                v = bm_local.verts[vi]
                angle_rad = math.radians(angle_deg * w)
                rot_mat = mathutils.Matrix.Rotation(angle_rad, 4, rot_axis)
                v.co = center + rot_mat @ (v.co - center)
                affected += 1

        elif transform_type == "SCALE":
            scale_vec = mathutils.Vector(value)
            # Compute center of selected vertices
            center = mathutils.Vector((0, 0, 0))
            for idx in vertex_indices:
                center += bm_local.verts[idx].co
            center /= len(vertex_indices)

            for vi, w in weights.items():
                v = bm_local.verts[vi]
                offset = v.co - center
                # Interpolate between identity scale and target scale
                lerp_scale = mathutils.Vector((
                    1.0 + (scale_vec.x - 1.0) * w,
                    1.0 + (scale_vec.y - 1.0) * w,
                    1.0 + (scale_vec.z - 1.0) * w,
                ))
                v.co = center + mathutils.Vector((
                    offset.x * lerp_scale.x,
                    offset.y * lerp_scale.y,
                    offset.z * lerp_scale.z,
                ))
                affected += 1

        bm_local.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm_local.free()

    return {
        "object_name": object_name,
        "transform_type": transform_type,
        "falloff_type": falloff_type,
        "falloff_radius": falloff_radius,
        "affected_vertices": affected,
        "vertex_count": len(obj.data.vertices),
    }


def _compute_connected_weights(
    bm_local: Any,
    center_indices: list[int],
    falloff_radius: float,
    falloff_type: str,
) -> dict[int, float]:
    """Compute proportional weights using topological BFS distance."""
    from collections import deque

    weights: dict[int, float] = {}
    distances: dict[int, float] = {}

    # Initialize center vertices
    queue: deque[int] = deque()
    for idx in center_indices:
        distances[idx] = 0.0
        weights[idx] = 1.0
        queue.append(idx)

    # BFS traversal along edges
    while queue:
        vi = queue.popleft()
        v = bm_local.verts[vi]
        current_dist = distances[vi]

        for edge in v.link_edges:
            other = edge.other_vert(v)
            edge_len = edge.calc_length()
            new_dist = current_dist + edge_len

            if new_dist >= falloff_radius:
                continue

            if other.index not in distances or new_dist < distances[other.index]:
                distances[other.index] = new_dist
                w = compute_falloff_weight(new_dist, falloff_radius, falloff_type)
                weights[other.index] = w
                queue.append(other.index)

    return weights


def handle_bisect(params: dict) -> dict:
    """Cut mesh with a plane (gap #26/GAP-07, #71).

    Params:
        object_name: Name of the Blender mesh object.
        plane_point: [x, y, z] point on the cutting plane.
        plane_normal: [x, y, z] normal of the cutting plane.
        clear_inner: Remove geometry on the inner (negative) side (default False).
        clear_outer: Remove geometry on the outer (positive) side (default False).
        fill: Fill the cut with a face (default False).

    Returns dict with vertex/face counts after bisect.
    """
    validated = validate_bisect_params(params)
    object_name = validated["object_name"]
    obj = _get_mesh_object(object_name)

    plane_co = mathutils.Vector(validated["plane_point"])
    plane_no = mathutils.Vector(validated["plane_normal"])
    clear_inner = validated["clear_inner"]
    clear_outer = validated["clear_outer"]
    fill = validated["fill"]

    bm_local = bmesh.new()
    try:
        bm_local.from_mesh(obj.data)
        bm_local.verts.ensure_lookup_table()
        bm_local.edges.ensure_lookup_table()
        bm_local.faces.ensure_lookup_table()

        geom = bm_local.verts[:] + bm_local.edges[:] + bm_local.faces[:]

        result = bmesh.ops.bisect_plane(
            bm_local,
            geom=geom,
            plane_co=plane_co,
            plane_no=plane_no,
            clear_inner=clear_inner,
            clear_outer=clear_outer,
        )

        # Fill the cut if requested
        if fill:
            # Select the cut edges (newly created geometry on the plane)
            cut_edges = [
                e for e in result.get("geom_cut", [])
                if isinstance(e, bmesh.types.BMEdge)
            ]
            if cut_edges:
                bmesh.ops.holes_fill(bm_local, edges=cut_edges, sides=100)

        bm_local.to_mesh(obj.data)
        obj.data.update()

        vert_count = len(bm_local.verts)
        face_count = len(bm_local.faces)
    finally:
        bm_local.free()

    return {
        "object_name": object_name,
        "plane_point": validated["plane_point"],
        "plane_normal": validated["plane_normal"],
        "clear_inner": clear_inner,
        "clear_outer": clear_outer,
        "fill": fill,
        "vertex_count": vert_count,
        "face_count": face_count,
    }


def handle_mesh_checkpoint(params: dict) -> dict:
    """Save/restore mesh state snapshots (gap #27/GAP-08).

    Params:
        object_name: Name of the Blender mesh object.
        action: 'save', 'restore', 'list', or 'clear'.
        checkpoint_name: Name for the checkpoint (defaults to timestamp).

    Returns dict with checkpoint info.
    """
    object_name, action, checkpoint_name = validate_checkpoint_params(params)
    obj = _get_mesh_object(object_name)

    if action == "save":
        bm_local = bmesh.new()
        try:
            bm_local.from_mesh(obj.data)
            bm_local.verts.ensure_lookup_table()
            bm_local.edges.ensure_lookup_table()
            bm_local.faces.ensure_lookup_table()

            verts = [(v.co.x, v.co.y, v.co.z) for v in bm_local.verts]
            edges = [(e.verts[0].index, e.verts[1].index) for e in bm_local.edges]
            faces = [tuple(v.index for v in f.verts) for f in bm_local.faces]
        finally:
            bm_local.free()

        checkpoint = _serialize_mesh_data_pure(
            verts, edges, faces, checkpoint_name,
        )

        if object_name not in _MESH_CHECKPOINTS:
            _MESH_CHECKPOINTS[object_name] = []
        _MESH_CHECKPOINTS[object_name].append(checkpoint)

        return {
            "object_name": object_name,
            "action": "save",
            "checkpoint_name": checkpoint_name,
            "vertex_count": checkpoint["vertex_count"],
            "edge_count": checkpoint["edge_count"],
            "face_count": checkpoint["face_count"],
            "total_checkpoints": len(_MESH_CHECKPOINTS[object_name]),
        }

    elif action == "restore":
        checkpoints = _MESH_CHECKPOINTS.get(object_name, [])
        if not checkpoints:
            raise ValueError(f"No checkpoints found for '{object_name}'")

        # Find checkpoint by name, or use the latest
        target = None
        for cp in reversed(checkpoints):
            if cp["name"] == checkpoint_name:
                target = cp
                break
        if target is None:
            # Use the most recent checkpoint
            target = checkpoints[-1]

        # Rebuild mesh from checkpoint
        mesh = obj.data
        mesh.clear_geometry()

        verts = target["vertices"]
        edges = target["edges"]
        faces = target["faces"]

        mesh.from_pydata(verts, edges, faces)
        mesh.update()

        return {
            "object_name": object_name,
            "action": "restore",
            "checkpoint_name": target["name"],
            "vertex_count": len(verts),
            "edge_count": len(edges),
            "face_count": len(faces),
        }

    elif action == "list":
        checkpoints = _MESH_CHECKPOINTS.get(object_name, [])
        return {
            "object_name": object_name,
            "action": "list",
            "checkpoints": [
                {
                    "name": cp["name"],
                    "timestamp": cp["timestamp"],
                    "vertex_count": cp["vertex_count"],
                    "face_count": cp["face_count"],
                }
                for cp in checkpoints
            ],
            "count": len(checkpoints),
        }

    elif action == "clear":
        removed = len(_MESH_CHECKPOINTS.get(object_name, []))
        _MESH_CHECKPOINTS.pop(object_name, None)
        return {
            "object_name": object_name,
            "action": "clear",
            "removed_checkpoints": removed,
        }

    raise ValueError(f"Unhandled checkpoint action: {action}")
