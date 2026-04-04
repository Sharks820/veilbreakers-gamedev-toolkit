"""Shared placement and interpolation utilities for Blender handlers.

Provides terrain-height-aware placement so objects are never placed at a
hardcoded Z=0 regardless of underlying terrain topology.

NO direct bpy usage at module level; bpy is imported lazily inside functions
that need it so this module can be imported by tests without Blender.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interpolation helpers
# ---------------------------------------------------------------------------

def smoothstep(t: float) -> float:
    """Hermite smoothstep for S-curve interpolation.

    Returns 0 for *t* <= 0, 1 for *t* >= 1, and a smooth cubic curve
    in between: ``3t^2 - 2t^3``.
    """
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------------------
# Terrain height sampling
# ---------------------------------------------------------------------------

def _find_terrain_object(terrain_name: str | None = None) -> Any:
    """Resolve a Blender terrain mesh object by name or auto-detect.

    Returns a ``bpy.types.Object`` or ``None``.
    """
    try:
        import bpy
    except ImportError:
        return None

    if terrain_name:
        obj = bpy.data.objects.get(terrain_name)
        if obj is not None and obj.type == "MESH":
            return obj

    # Auto-detect: look for common terrain naming patterns
    for name_pattern in ("Terrain", "terrain", "Ground", "ground"):
        for obj in bpy.data.objects:
            if obj.type == "MESH" and name_pattern in obj.name:
                return obj

    return None


def _sample_terrain_height(terrain_obj: Any, x: float, y: float) -> float | None:
    """Sample terrain height at world (x, y) via closest-point projection.

    Uses ``closest_point_on_mesh`` for accuracy.  Falls back to vertex
    scan when the method is unavailable.

    Returns the Z coordinate on the terrain surface, or ``None`` if
    sampling fails.
    """
    try:
        import bpy  # noqa: F811
        from mathutils import Vector
    except ImportError:
        return None

    if terrain_obj is None or terrain_obj.type != "MESH" or terrain_obj.data is None:
        return None

    # Transform world coords to object-local space
    local_point = terrain_obj.matrix_world.inverted() @ Vector((x, y, 1000.0))

    # closest_point_on_mesh returns (result, location, normal, face_index)
    try:
        result, location, _normal, _face_idx = terrain_obj.closest_point_on_mesh(local_point)
        if result:
            world_loc = terrain_obj.matrix_world @ location
            return float(world_loc.z)
    except (RuntimeError, AttributeError):
        pass

    # Fallback: brute-force nearest vertex
    try:
        import bmesh

        bm = bmesh.new()
        bm.from_mesh(terrain_obj.data)
        bm.verts.ensure_lookup_table()

        best_z = None
        best_dist2 = float("inf")
        for v in bm.verts:
            wv = terrain_obj.matrix_world @ v.co
            d2 = (wv.x - x) ** 2 + (wv.y - y) ** 2
            if d2 < best_dist2:
                best_dist2 = d2
                best_z = float(wv.z)
        bm.free()
        return best_z
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Safe placement
# ---------------------------------------------------------------------------

def safe_place_object(
    x: float,
    y: float,
    terrain_name: str | None = None,
    water_level: float | None = None,
    bounds: tuple[float, float, float, float] | None = None,
    offset_z: float = 0.02,
) -> tuple[float, float, float] | None:
    """Sample terrain height at *(x, y)* and return a valid placement coordinate.

    Parameters
    ----------
    x, y : float
        World-space horizontal coordinates.
    terrain_name : str or None
        Name of the Blender terrain mesh object.  If ``None``, attempts
        auto-detection.
    water_level : float or None
        If set, positions below this Z level are rejected (returns ``None``).
        Useful for scatter passes that should not place vegetation underwater.
    bounds : tuple or None
        ``(min_x, min_y, max_x, max_y)`` placement boundary.  Returns
        ``None`` if *(x, y)* is outside.
    offset_z : float
        Small upward offset to prevent z-fighting with the terrain surface.
        Default 0.02 m.

    Returns
    -------
    tuple[float, float, float] or None
        ``(x, y, z)`` placement coordinate, or ``None`` if placement is
        invalid (out of bounds, underwater, or terrain sampling failed with
        no fallback).
    """
    # Bounds check
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return None

    # Try to sample terrain height
    terrain_obj = _find_terrain_object(terrain_name)
    z = _sample_terrain_height(terrain_obj, x, y)

    if z is None:
        # No terrain found -- fall back to ground plane + offset
        z = offset_z
    else:
        z = z + offset_z

    # Water exclusion
    if water_level is not None and z < water_level:
        return None

    return (x, y, z)
