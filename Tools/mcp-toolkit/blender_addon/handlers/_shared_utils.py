"""Shared utility functions for handlers.

Provides common interpolation helpers used across all animation modules,
and terrain-aware placement used by worldbuilding/layout handlers.
Uses bpy-guarded import pattern so pure-logic tests still work.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import bpy
    from mathutils import Vector

    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False


def smoothstep(t: float) -> float:
    """Hermite smoothstep: 3t^2 - 2t^3. Clamps t to [0,1].

    Provides ease-in-ease-out interpolation for natural animation blending.
    smoothstep(0) = 0, smoothstep(0.5) = 0.5, smoothstep(1) = 1.
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def safe_place_object(
    x: float,
    y: float,
    *,
    terrain_name: Optional[str] = None,
    offset_z: float = 0.02,
    bounds: Optional[Tuple[float, float, float, float]] = None,
    water_level: Optional[float] = None,
    ray_height: float = 500.0,
) -> Optional[Tuple[float, float, float]]:
    """Place an object at (x, y) with terrain-aware Z snapping.

    Pure-logic fallback: returns ``(x, y, offset_z)`` when bpy is unavailable.
    With bpy: attempts downward ray cast onto terrain for accurate Z.

    Returns ``(x, y, z)`` on success, or ``None`` if placement is rejected
    (out of bounds, underwater).  All call sites fall back to a default
    position on ``None``.

    Parameters
    ----------
    x, y:
        World-space horizontal coordinates.
    terrain_name:
        Optional name of a specific terrain object to ray-cast against.
        If ``None`` and bpy is available, uses scene-level ray cast.
    offset_z:
        Default Z height when no terrain hit is found (default 0.02).
    bounds:
        Optional ``(min_x, min_y, max_x, max_y)`` rectangle.  Placement
        is rejected (returns ``None``) if (x, y) lies outside.
    water_level:
        If set, reject placements where the resolved Z is below this level.
    ray_height:
        Height from which the downward ray is cast (default 500 m).
    """
    # --- Bounds check (pure logic, no bpy needed) ---
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return None

    # --- Resolve Z coordinate ---
    z = offset_z

    if _HAS_BPY:
        origin = Vector((float(x), float(y), ray_height))
        direction = Vector((0.0, 0.0, -1.0))
        try:
            if terrain_name:
                terrain_obj = bpy.data.objects.get(terrain_name)
                if terrain_obj is not None:
                    inv = terrain_obj.matrix_world.inverted()
                    local_origin = inv @ origin
                    local_dir = (inv.to_3x3() @ direction).normalized()
                    success, hit_loc, _normal, _idx = terrain_obj.ray_cast(
                        local_origin, local_dir
                    )
                    if success:
                        world_loc = terrain_obj.matrix_world @ hit_loc
                        z = world_loc.z

            if z == offset_z:
                # Scene-level ray cast fallback
                depsgraph = bpy.context.evaluated_depsgraph_get()
                hit, location, _normal, _idx, _obj, _mat = bpy.context.scene.ray_cast(
                    depsgraph, origin, direction
                )
                if hit:
                    z = location.z
        except Exception as exc:
            logger.debug(
                "safe_place_object ray cast failed at (%.1f, %.1f): %s",
                x, y, exc,
            )

    # --- Water level check ---
    if water_level is not None and z < water_level:
        return None

    return (x, y, z)
