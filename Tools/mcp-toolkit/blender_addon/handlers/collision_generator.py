"""Collision mesh generator for Unity export.

Provides pure-logic convex hull computation and a bpy-dependent
handler for generating collision meshes with UCX_-compatible naming.

Exports:
    compute_convex_hull_vertices -- Pure-logic convex hull from vertices.
    decimate_hull_faces          -- Limit face count via uniform sampling.
    generate_collision_mesh      -- bpy-dependent collision mesh creation.
    handle_generate_collision_meshes -- Handler for addon command dispatch.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Pure-logic functions (testable without bpy)
# ---------------------------------------------------------------------------


def compute_convex_hull_vertices(
    vertices: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Compute convex hull vertices from a list of 3D points.

    Uses scipy.spatial.ConvexHull if available, falls back to a simple
    bounding-box approach (8 corner vertices) when scipy is not installed.

    Parameters
    ----------
    vertices : list of (x, y, z) tuples
        Input vertices.

    Returns
    -------
    list of (x, y, z) tuples
        Vertices forming the convex hull.

    Raises
    ------
    ValueError
        If vertices list is empty or has fewer than 4 points.
    """
    if not vertices:
        raise ValueError("Cannot compute convex hull from empty vertex list")
    if len(vertices) < 4:
        raise ValueError(
            f"Need at least 4 vertices for convex hull, got {len(vertices)}"
        )

    try:
        import numpy as np
        from scipy.spatial import ConvexHull

        points = np.array(vertices, dtype=np.float64)
        hull = ConvexHull(points)
        hull_verts = points[hull.vertices].tolist()
        return [tuple(v) for v in hull_verts]
    except ImportError:
        # Fallback: bounding box vertices
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        zs = [v[2] for v in vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        return [
            (min_x, min_y, min_z),
            (max_x, min_y, min_z),
            (min_x, max_y, min_z),
            (max_x, max_y, min_z),
            (min_x, min_y, max_z),
            (max_x, min_y, max_z),
            (min_x, max_y, max_z),
            (max_x, max_y, max_z),
        ]


def decimate_hull_faces(
    faces: list,
    max_faces: int = 128,
) -> list:
    """Reduce face count via uniform sampling if exceeding max_faces.

    Parameters
    ----------
    faces : list
        List of face definitions (e.g., vertex index tuples).
    max_faces : int
        Maximum allowed face count.

    Returns
    -------
    list
        Subset of faces with at most max_faces entries.
    """
    if len(faces) <= max_faces:
        return list(faces)

    # Uniform sampling to reduce face count
    step = len(faces) / max_faces
    result = []
    idx = 0.0
    while len(result) < max_faces and int(idx) < len(faces):
        result.append(faces[int(idx)])
        idx += step
    return result


def collision_mesh_name(original_name: str) -> str:
    """Generate collision mesh name with _COL suffix.

    Parameters
    ----------
    original_name : str
        Original object name.

    Returns
    -------
    str
        Name with _COL suffix (export.py will rename to UCX_ for Unity).
    """
    return f"{original_name}_COL"


# ---------------------------------------------------------------------------
# bpy-dependent functions
# ---------------------------------------------------------------------------


def generate_collision_mesh(
    object_name: str,
    max_faces: int = 128,
) -> dict[str, Any]:
    """Generate a convex hull collision mesh for a Blender object.

    Requires bpy (Blender Python). Creates a new object named
    ``{object_name}_COL`` linked to the same collection.

    Parameters
    ----------
    object_name : str
        Name of the source Blender object.
    max_faces : int
        Maximum face count for the collision mesh.

    Returns
    -------
    dict with collision_object, face_count, original_object keys.
    """
    import bpy
    import bmesh

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is type '{obj.type}', not MESH")

    col_name = collision_mesh_name(object_name)

    # Build convex hull via bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    result = bmesh.ops.convex_hull(bm, input=bm.verts)

    # Create collision mesh
    col_mesh = bpy.data.meshes.new(col_name)
    bm.to_mesh(col_mesh)
    bm.free()

    col_obj = bpy.data.objects.new(col_name, col_mesh)

    # Link to same collection as source
    for col in obj.users_collection:
        col.objects.link(col_obj)
        break
    else:
        bpy.context.scene.collection.objects.link(col_obj)

    # Decimate if too many faces
    face_count = len(col_mesh.polygons)
    if face_count > max_faces:
        mod = col_obj.modifiers.new("Decimate_COL", "DECIMATE")
        mod.ratio = max_faces / face_count
        bpy.context.view_layer.objects.active = col_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        face_count = len(col_obj.data.polygons)

    return {
        "collision_object": col_name,
        "face_count": face_count,
        "original_object": object_name,
    }


def handle_generate_collision_meshes(params: dict) -> dict:
    """Handler: generate collision meshes for multiple objects.

    Params
    ------
    object_names : list of str
        Object names to generate collision meshes for.
    max_faces : int, optional
        Maximum face count per collision mesh (default 128).

    Returns
    -------
    dict with collisions list.
    """
    object_names = params.get("object_names", [])
    max_faces = int(params.get("max_faces", 128))

    collisions = []
    for name in object_names:
        try:
            result = generate_collision_mesh(name, max_faces=max_faces)
            collisions.append(result)
        except (ValueError, RuntimeError) as exc:
            collisions.append({
                "collision_object": None,
                "face_count": 0,
                "original_object": name,
                "error": str(exc),
            })

    return {"collisions": collisions}
