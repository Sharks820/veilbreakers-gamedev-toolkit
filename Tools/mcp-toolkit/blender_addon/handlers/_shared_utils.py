"""Shared utilities for Blender addon handlers.

Provides reusable helper functions used across multiple handler modules.
This module must ONLY import from: bpy, bmesh, mathutils, math, logging,
and the Python standard library. It must NOT import from other handler
modules at the top level to avoid circular imports.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Interpolation utilities
# ---------------------------------------------------------------------------


def smoothstep(t: float) -> float:
    """Hermite smoothstep for S-curve interpolation in [0, 1].

    Returns 0 for t<=0, 1 for t>=1, smooth ease-in-ease-out transition
    between. Use instead of linear ``t`` for all terrain transitions and
    animation blending.

    Formula: 3t^2 - 2t^3
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def inverse_smoothstep(t: float) -> float:
    """Inverse of Hermite smoothstep -- convert smoothed value back to linear.

    Uses the arcsine-based analytical inverse.  Returns 0 for t<=0,
    1 for t>=1.
    """
    t = max(0.0, min(1.0, t))
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 0.5 - math.sin(math.asin(1.0 - 2.0 * t) / 3.0)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from *a* to *b* by factor *t* (clamped 0..1)."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def smooth_lerp(a: float, b: float, t: float) -> float:
    """Smoothstep-interpolation from *a* to *b* by factor *t*.

    Equivalent to ``lerp(a, b, smoothstep(t))``.
    """
    return lerp(a, b, smoothstep(t))


# ---------------------------------------------------------------------------
# Terrain placement utilities
# ---------------------------------------------------------------------------


def _get_sample_scene_height():
    """Lazy-import ``_sample_scene_height`` from worldbuilding to avoid circular imports."""
    from .worldbuilding import _sample_scene_height  # noqa: F811

    return _sample_scene_height


def safe_place_object(
    x: float,
    y: float,
    terrain_name: str | None,
    *,
    water_level: float | None = None,
    bounds: tuple[float, float, float, float] | None = None,
    offset_z: float = 0.02,
) -> tuple[float, float, float] | None:
    """Sample terrain height and validate placement.

    Returns ``(x, y, z)`` if placement is valid, ``None`` if rejected.

    Rejection reasons:
    - Below *water_level* (when provided)
    - Outside *bounds* rectangle ``(min_x, min_y, max_x, max_y)``
    - No terrain hit (height sampling returns default 0.0 and no terrain_name)

    The underlying ``_sample_scene_height`` is imported lazily from the
    worldbuilding module to avoid circular imports at addon load time.

    Parameters
    ----------
    x, y : float
        World-space XY coordinates for placement.
    terrain_name : str | None
        Blender object name of the terrain mesh (passed to
        ``_sample_scene_height`` for ARCH-028 terrain-only filtering).
    water_level : float | None
        If provided, placements below this Z are rejected.
    bounds : tuple | None
        ``(min_x, min_y, max_x, max_y)`` bounding rectangle.
    offset_z : float
        Small upward offset to prevent Z-fighting (default 0.02).
    """
    try:
        _sample_height = _get_sample_scene_height()
        z = _sample_height(x, y, terrain_name)
    except Exception as exc:
        logger.debug(
            "safe_place_object: height sampling failed at (%.3f, %.3f): %s",
            x,
            y,
            exc,
        )
        return None

    if water_level is not None and z < water_level:
        return None

    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        if not (min_x <= x <= max_x and min_y <= y <= max_y):
            return None

    return (x, y, z + offset_z)
