"""Bundle R — user viewport anchoring + "observe before calculate" helpers.

Headless-compatible: real Blender would read ``bpy.context.region_data`` to
populate the vantage; in unit tests we allow a synthetic default so the
contract can be exercised without a live scene.

See Addendum 1.A.3 of the implementation plan for the authoritative contract.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Tuple

from .terrain_semantics import BBox


class ViewportStale(RuntimeError):
    """Raised when a vantage has aged past its freshness window."""


@dataclass(frozen=True)
class ViewportVantage:
    """Snapshot of the user's active Blender 3D viewport."""

    camera_position: Tuple[float, float, float]
    camera_direction: Tuple[float, float, float]
    camera_up: Tuple[float, float, float]
    focal_point: Tuple[float, float, float]
    fov: float
    visible_bounds: BBox
    captured_timestamp: float
    view_matrix_hash: str


def _unit(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = v
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 1.0)
    return (x / n, y / n, z / n)


def _matrix_hash(
    pos: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    up: Tuple[float, float, float],
    fov: float,
) -> str:
    blob = f"{pos}|{direction}|{up}|{fov:.6f}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def read_user_vantage(
    *,
    camera_position: Tuple[float, float, float] = (0.0, -20.0, 12.0),
    focal_point: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    up: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    fov: float = 0.9,
    visible_bounds: BBox = None,
) -> ViewportVantage:
    """Return a ``ViewportVantage`` — real Blender reads region_data.

    In headless mode the caller supplies a synthetic vantage that still
    satisfies the contract. Z-up convention: ``up=(0,0,1)``.
    """
    direction = _unit(
        (
            focal_point[0] - camera_position[0],
            focal_point[1] - camera_position[1],
            focal_point[2] - camera_position[2],
        )
    )
    if visible_bounds is None:
        r = 40.0
        visible_bounds = BBox(
            min_x=focal_point[0] - r,
            min_y=focal_point[1] - r,
            max_x=focal_point[0] + r,
            max_y=focal_point[1] + r,
        )
    return ViewportVantage(
        camera_position=tuple(float(x) for x in camera_position),
        camera_direction=direction,
        camera_up=_unit(up),
        focal_point=tuple(float(x) for x in focal_point),
        fov=float(fov),
        visible_bounds=visible_bounds,
        captured_timestamp=time.time(),
        view_matrix_hash=_matrix_hash(camera_position, direction, up, fov),
    )


def assert_vantage_fresh(
    vantage: ViewportVantage,
    max_age_seconds: float = 300.0,
    *,
    now: float | None = None,
) -> None:
    current = time.time() if now is None else now
    age = current - float(vantage.captured_timestamp)
    if age > max_age_seconds:
        raise ViewportStale(
            f"vantage is {age:.0f}s old (max {max_age_seconds:.0f}s). "
            "Recapture via read_user_vantage()."
        )


def transform_world_to_vantage(
    world_position: Tuple[float, float, float],
    vantage: ViewportVantage,
) -> Tuple[float, float, float]:
    """Project a world point into camera-relative coordinates (view space).

    Minimal orthonormal basis projection. Not a full perspective matrix —
    Bundle H's composition passes use this for vantage-relative scoring,
    not final rendering.
    """
    cx, cy, cz = vantage.camera_position
    dx, dy, dz = world_position[0] - cx, world_position[1] - cy, world_position[2] - cz
    fx, fy, fz = vantage.camera_direction
    ux, uy, uz = vantage.camera_up
    # Right = up × forward (Z-up, right-handed)
    rx = uy * fz - uz * fy
    ry = uz * fx - ux * fz
    rz = ux * fy - uy * fx
    rn = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
    rx, ry, rz = rx / rn, ry / rn, rz / rn
    right = rx * dx + ry * dy + rz * dz
    up = ux * dx + uy * dy + uz * dz
    forward = fx * dx + fy * dy + fz * dz
    return (right, up, forward)


def is_in_frustum(
    world_position: Tuple[float, float, float],
    vantage: ViewportVantage,
) -> bool:
    """True when ``world_position`` is in front of the camera AND inside
    the horizontal+vertical half-angles implied by ``vantage.fov`` (radians).

    This is a real frustum test (not just an XY AABB): points behind the
    camera are rejected via the forward-axis sign, and points outside
    the FOV cone are rejected via right/up angular bounds. The XY AABB
    is kept as an outer conservative gate so very distant points still
    fail fast.
    """
    x, y, _z = world_position
    if not vantage.visible_bounds.contains_point(x, y):
        return False
    # Build an orthonormal view basis from the (possibly non-orthogonal)
    # stored camera_up: right = world_up × forward, view_up = forward × right.
    cx, cy, cz = vantage.camera_position
    dx = world_position[0] - cx
    dy = world_position[1] - cy
    dz = world_position[2] - cz
    fx, fy, fz = _unit(vantage.camera_direction)
    wux, wuy, wuz = _unit(vantage.camera_up)
    # Forward-sign rejection is independent of the basis construction —
    # compute it first so the degenerate (camera_up || forward) fallback
    # still filters behind-camera points.
    forward_precheck = fx * dx + fy * dy + fz * dz
    if forward_precheck <= 1e-6:
        return False
    # right = world_up × forward
    rx = wuy * fz - wuz * fy
    ry = wuz * fx - wux * fz
    rz = wux * fy - wuy * fx
    rn = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rn < 1e-9:
        # camera_up is parallel to forward — we already rejected behind-camera
        # points above; fall back to the AABB gate for in-front points.
        return True
    rx, ry, rz = rx / rn, ry / rn, rz / rn
    # view_up = forward × right  (orthonormal, right-handed)
    ux = fy * rz - fz * ry
    uy = fz * rx - fx * rz
    uz = fx * ry - fy * rx
    forward = forward_precheck
    right = rx * dx + ry * dy + rz * dz
    up = ux * dx + uy * dy + uz * dz
    half_fov = 0.5 * float(vantage.fov)
    tan_h = math.tan(half_fov)
    if abs(right) > forward * tan_h:
        return False
    if abs(up) > forward * tan_h:
        return False
    return True


__all__ = [
    "ViewportVantage",
    "ViewportStale",
    "read_user_vantage",
    "assert_vantage_fresh",
    "transform_world_to_vantage",
    "is_in_frustum",
]
