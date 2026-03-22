"""Curve creation and conversion handlers.

Provides:
- handle_create_curve: Create Bezier or NURBS curves from control points (CURVE-01)
- handle_curve_to_mesh: Convert a curve to mesh with a profile shape (CURVE-02)
- handle_extrude_along_curve: Extrude a profile mesh/curve along a path curve (CURVE-03)

Pure-logic validation functions are testable without Blender.
"""

from __future__ import annotations

import bpy
import mathutils


# ---------------------------------------------------------------------------
# Pure-logic validation helpers (testable without Blender)
# ---------------------------------------------------------------------------

# Valid curve types.
_CURVE_TYPES = frozenset({"BEZIER", "NURBS"})

# Valid profile shapes for curve-to-mesh conversion.
_PROFILE_SHAPES = frozenset({"CIRCLE", "SQUARE", "CUSTOM"})


def _validate_create_curve_params(params: dict) -> dict:
    """Validate and normalise create_curve parameters.

    Returns dict with validated ``name``, ``curve_type``, ``points``,
    ``closed``, ``resolution``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name", "Curve")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name must be a non-empty string, got {name!r}")
    curve_type = params.get("curve_type", "BEZIER")
    if curve_type not in _CURVE_TYPES:
        raise ValueError(
            f"Unknown curve_type: {curve_type!r}. Valid: {sorted(_CURVE_TYPES)}"
        )
    points = params.get("points")
    if not points or not isinstance(points, (list, tuple)):
        raise ValueError("points must be a non-empty list of [x, y, z] coordinates")
    if len(points) < 2:
        raise ValueError(f"At least 2 points are required, got {len(points)}")
    for i, pt in enumerate(points):
        if not isinstance(pt, (list, tuple)) or len(pt) < 3:
            raise ValueError(
                f"Point {i} must be a list of at least 3 floats [x, y, z], got {pt!r}"
            )
    closed = params.get("closed", False)
    if not isinstance(closed, bool):
        raise ValueError(f"closed must be a boolean, got {type(closed).__name__}")
    resolution = params.get("resolution", 12)
    if not isinstance(resolution, int) or resolution < 1:
        raise ValueError(f"resolution must be a positive integer, got {resolution!r}")
    return {
        "name": name.strip(),
        "curve_type": curve_type,
        "points": [[float(c) for c in pt[:3]] for pt in points],
        "closed": closed,
        "resolution": resolution,
    }


def _validate_curve_to_mesh_params(params: dict) -> dict:
    """Validate and normalise curve_to_mesh parameters.

    Returns dict with validated ``name``, ``profile_shape``, ``profile_size``.
    Raises ``ValueError`` for invalid values.
    """
    name = params.get("name")
    if not name:
        raise ValueError("name is required for curve_to_mesh")
    profile_shape = params.get("profile_shape", "CIRCLE")
    if profile_shape not in _PROFILE_SHAPES:
        raise ValueError(
            f"Unknown profile_shape: {profile_shape!r}. "
            f"Valid: {sorted(_PROFILE_SHAPES)}"
        )
    profile_size = params.get("profile_size", 0.1)
    if not isinstance(profile_size, (int, float)) or profile_size <= 0:
        raise ValueError(f"profile_size must be a positive number, got {profile_size!r}")
    return {
        "name": name,
        "profile_shape": profile_shape,
        "profile_size": float(profile_size),
    }


def _validate_extrude_along_curve_params(params: dict) -> dict:
    """Validate and normalise extrude_along_curve parameters.

    Returns dict with validated ``curve_name`` and ``profile_name``.
    Raises ``ValueError`` for invalid values.
    """
    curve_name = params.get("curve_name")
    if not curve_name:
        raise ValueError("curve_name is required for extrude_along_curve")
    profile_name = params.get("profile_name")
    if not profile_name:
        raise ValueError("profile_name is required for extrude_along_curve")
    return {
        "curve_name": curve_name,
        "profile_name": profile_name,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy at runtime)
# ---------------------------------------------------------------------------


def _get_curve_object(name: str | None) -> object:
    """Validate and return a curve object by name."""
    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "CURVE":
        raise ValueError(f"Curve object not found: {name}")
    return obj


def handle_create_curve(params: dict) -> dict:
    """Create a Bezier or NURBS curve from control points (CURVE-01).

    Params:
        name: Curve object name (default "Curve").
        curve_type: "BEZIER" or "NURBS" (default "BEZIER").
        points: List of [x, y, z] control point positions (min 2).
        closed: Whether the curve is cyclic (default False).
        resolution: Curve resolution / preview U (default 12).

    Returns dict with object name, point count, curve type, and closed status.
    """
    validated = _validate_create_curve_params(params)
    name = validated["name"]
    curve_type = validated["curve_type"]
    points = validated["points"]
    closed = validated["closed"]
    resolution = validated["resolution"]

    # Create the curve data
    curve_data = bpy.data.curves.new(name=name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = resolution

    # Create and configure the spline
    if curve_type == "BEZIER":
        spline = curve_data.splines.new("BEZIER")
        spline.bezier_points.add(len(points) - 1)  # first point already exists
        for i, pt in enumerate(points):
            bp = spline.bezier_points[i]
            bp.co = mathutils.Vector(pt)
            bp.handle_left_type = "AUTO"
            bp.handle_right_type = "AUTO"
    else:
        # NURBS
        spline = curve_data.splines.new("NURBS")
        spline.points.add(len(points) - 1)  # first point already exists
        for i, pt in enumerate(points):
            spline.points[i].co = (pt[0], pt[1], pt[2], 1.0)  # NURBS uses 4D (w=1)
        spline.use_endpoint_u = True
        spline.order_u = min(4, len(points))

    spline.use_cyclic_u = closed

    # Create the object and link to scene
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    return {
        "object_name": obj.name,
        "curve_type": curve_type,
        "point_count": len(points),
        "closed": closed,
        "resolution": resolution,
    }


def handle_curve_to_mesh(params: dict) -> dict:
    """Convert a curve object to mesh with a profile shape (CURVE-02).

    Params:
        name: Curve object name (required).
        profile_shape: "CIRCLE", "SQUARE", or "CUSTOM" (default "CIRCLE").
        profile_size: Profile bevel radius/size (default 0.1).

    For CIRCLE/SQUARE: sets bevel_depth and bevel_resolution on the curve,
    then converts to mesh. For CUSTOM: converts the curve as-is (user must
    have set up a bevel object).

    Returns dict with object name and post-conversion vertex/face counts.
    """
    validated = _validate_curve_to_mesh_params(params)
    name = validated["name"]
    profile_shape = validated["profile_shape"]
    profile_size = validated["profile_size"]

    obj = _get_curve_object(name)

    if profile_shape == "CIRCLE":
        obj.data.bevel_depth = profile_size
        obj.data.bevel_resolution = 4
        obj.data.fill_mode = "FULL"
    elif profile_shape == "SQUARE":
        # Create a square bevel profile curve
        profile_data = bpy.data.curves.new(name=f"{name}_profile", type="CURVE")
        profile_data.dimensions = "2D"
        spline = profile_data.splines.new("POLY")
        half = profile_size
        coords = [(-half, -half, 0), (half, -half, 0),
                  (half, half, 0), (-half, half, 0)]
        spline.points.add(len(coords) - 1)
        for i, co in enumerate(coords):
            spline.points[i].co = (co[0], co[1], co[2], 1.0)
        spline.use_cyclic_u = True

        profile_obj = bpy.data.objects.new(f"{name}_profile", profile_data)
        bpy.context.collection.objects.link(profile_obj)
        obj.data.bevel_object = profile_obj
        obj.data.fill_mode = "FULL"
    # CUSTOM: assume bevel object is already assigned

    # Convert curve to mesh -- isolate selection first
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")

    return {
        "object_name": obj.name,
        "profile_shape": profile_shape,
        "profile_size": profile_size,
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }


def handle_extrude_along_curve(params: dict) -> dict:
    """Extrude a profile mesh/curve along a path curve (CURVE-03).

    Params:
        curve_name: Path curve object name (required).
        profile_name: Profile mesh or curve object name (required).

    Sets the profile object as the bevel_object of the curve, then
    converts the result to mesh.

    Returns dict with object name and post-conversion vertex/face counts.
    """
    validated = _validate_extrude_along_curve_params(params)
    curve_name = validated["curve_name"]
    profile_name = validated["profile_name"]

    curve_obj = _get_curve_object(curve_name)
    profile_obj = bpy.data.objects.get(profile_name)
    if profile_obj is None:
        raise ValueError(f"Profile object not found: {profile_name}")

    # If the profile is a mesh, convert it to a curve first
    if profile_obj.type == "MESH":
        bpy.ops.object.select_all(action='DESELECT')
        profile_obj.select_set(True)
        bpy.context.view_layer.objects.active = profile_obj
        bpy.ops.object.convert(target="CURVE")
        # Re-fetch after conversion
        profile_obj = bpy.data.objects.get(profile_name)

    # Set the profile as the bevel object on the curve
    curve_obj.data.bevel_object = profile_obj
    curve_obj.data.use_fill_caps = True

    # Convert the result to mesh -- isolate selection first
    bpy.ops.object.select_all(action='DESELECT')
    curve_obj.select_set(True)
    bpy.context.view_layer.objects.active = curve_obj
    bpy.ops.object.convert(target="MESH")

    return {
        "object_name": curve_obj.name,
        "curve_name": curve_name,
        "profile_name": profile_name,
        "vertex_count": len(curve_obj.data.vertices),
        "face_count": len(curve_obj.data.polygons),
    }
