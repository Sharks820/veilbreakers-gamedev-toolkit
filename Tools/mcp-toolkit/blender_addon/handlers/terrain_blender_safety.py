"""Bundle R — Blender-specific runtime stability guards.

Consolidates every "thing that can crash Blender" rule from the feedback
memory files into enforceable callable guards:
  - Z-up enforcement (feedback_blender_z_up.md)
  - Screenshot size cap (feedback_screenshot_max_size.md): HARD CAP 507
  - Boolean op dense mesh guard (feedback_blender_crash_avoidance.md): 60k vert
  - Tripo GLB batch serialization (feedback_tripo_import_one_at_a_time.md)

See Addendum 1.A.6 for the authoritative spec.
"""

from __future__ import annotations

import functools
import threading
from pathlib import Path
from typing import Callable, List, Sequence, Tuple


class CoordinateSystemError(RuntimeError):
    """Raised when a non-Z-up coordinate is used for terrain heights."""


class BlenderBooleanUnsafe(RuntimeError):
    """Raised when a boolean op would operate on a too-dense mesh."""


# ---------------------------------------------------------------------------
# Z-up enforcement
# ---------------------------------------------------------------------------


def assert_z_is_up(obj_up_axis: str) -> None:
    """Raise ``CoordinateSystemError`` if the up axis is not 'Z'.

    Takes a string ('X'/'Y'/'Z' or '-X'/'-Y'/'-Z') so this works in
    headless mode without a live ``bpy.types.Object`` reference.
    """
    normalized = obj_up_axis.strip().upper().lstrip("+")
    if normalized.lstrip("-") != "Z":
        raise CoordinateSystemError(
            f"object up axis is {obj_up_axis!r}; VeilBreakers is Z-up only. "
            "Call convert_y_up_to_z_up() at the import boundary."
        )


def convert_y_up_to_z_up(
    position: Tuple[float, float, float],
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Convert a Y-up coordinate (x, y, z) to Z-up (x, -z, y).

    Blender is right-handed Z-up. FBX/GLTF importers commonly deliver
    Y-up; use this at every import boundary.
    """
    x, y, z = position
    zup_position = (x, -z, y)
    rx, ry, rz = orientation
    # Rotate Euler: swap Y and Z, flip sign to match axis swap.
    zup_orientation = (rx, -rz, ry)
    return zup_position, zup_orientation


def guard_z_up(fn: Callable) -> Callable:
    """Decorator that checks any ``up`` kwarg before the wrapped function runs."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        up_axis = kwargs.get("up_axis")
        if up_axis is not None:
            assert_z_is_up(str(up_axis))
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Screenshot size cap
# ---------------------------------------------------------------------------

# HARD CAP — feedback memory feedback_screenshot_max_size.md. NEVER 1024.
BLENDER_SCREENSHOT_MAX_SIZE: int = 507
BLENDER_SCREENSHOT_MIN_SIZE: int = 64


def clamp_screenshot_size(requested: int) -> int:
    """Clamp a requested screenshot dimension to the safe band [64, 507]."""
    try:
        r = int(requested)
    except Exception:
        return BLENDER_SCREENSHOT_MAX_SIZE
    if r < BLENDER_SCREENSHOT_MIN_SIZE:
        return BLENDER_SCREENSHOT_MIN_SIZE
    if r > BLENDER_SCREENSHOT_MAX_SIZE:
        return BLENDER_SCREENSHOT_MAX_SIZE
    return r


# ---------------------------------------------------------------------------
# Boolean dense-mesh guard
# ---------------------------------------------------------------------------

BOOLEAN_DENSE_MESH_VERT_LIMIT: int = 60000
BOOLEAN_DENSE_MESH_DECIMATE_TARGET: int = 30000


def assert_boolean_safe(
    cutter_vert_count: int,
    target_vert_count: int,
    *,
    limit: int = BOOLEAN_DENSE_MESH_VERT_LIMIT,
) -> None:
    """Raise if either operand exceeds the boolean safety limit."""
    if cutter_vert_count > limit:
        raise BlenderBooleanUnsafe(
            f"boolean cutter has {cutter_vert_count} verts (limit {limit}). "
            "Decimate first or use a simpler cutter."
        )
    if target_vert_count > limit:
        raise BlenderBooleanUnsafe(
            f"boolean target has {target_vert_count} verts (limit {limit}). "
            "Decimate first."
        )


def decimate_to_safe_count(
    current_vert_count: int,
    target_count: int = BOOLEAN_DENSE_MESH_DECIMATE_TARGET,
) -> float:
    """Return the decimation ratio required to reach ``target_count``.

    The caller is responsible for applying the ratio (real Blender
    would call ``bpy.ops.object.modifier_add(type='DECIMATE')``).
    """
    if current_vert_count <= 0:
        return 1.0
    if current_vert_count <= target_count:
        return 1.0
    return max(0.01, float(target_count) / float(current_vert_count))


def recommend_boolean_solver(cutter_vert_count: int, target_vert_count: int) -> str:
    """Return 'FAST' for dense meshes, 'EXACT' otherwise."""
    dense = max(cutter_vert_count, target_vert_count)
    return "FAST" if dense > 20000 else "EXACT"


# ---------------------------------------------------------------------------
# Tripo GLB import serialization
# ---------------------------------------------------------------------------

_TRIPO_IMPORT_LOCK = threading.Lock()
_TRIPO_IMPORT_LOG: List[Path] = []


def import_tripo_glb_serialized(
    glb_paths: Sequence[Path],
    *,
    require_exists: bool = True,
) -> List[Path]:
    """Return ``glb_paths`` in order, holding a global lock for each.

    Enforces two contracts (Addendum 1.A.6):
      1. Path must exist on disk when ``require_exists=True`` (default).
      2. Path must end in ``.glb`` or ``.gltf`` — anything else is rejected.
      3. Exactly one import is in flight at any time, via a process-wide
         lock (``_TRIPO_IMPORT_LOCK``).

    Real Blender would call ``bpy.ops.import_scene.gltf(filepath=...)``
    inside the with-block. Headless mode records the serialization order
    and validated paths so tests can assert the contract.
    """
    out: List[Path] = []
    for p in glb_paths:
        path = Path(p)
        suffix = path.suffix.lower()
        if suffix not in (".glb", ".gltf"):
            raise ValueError(
                f"import_tripo_glb_serialized: unsupported suffix {suffix!r} "
                f"for {path!r}; expected .glb or .gltf"
            )
        if require_exists and not path.exists():
            raise FileNotFoundError(
                f"import_tripo_glb_serialized: missing file {path!r}"
            )
        with _TRIPO_IMPORT_LOCK:
            out.append(path)
            _TRIPO_IMPORT_LOG.append(path)
    return out


def get_tripo_import_log() -> List[Path]:
    """Test helper — returns a copy of the serialization log."""
    return list(_TRIPO_IMPORT_LOG)


def clear_tripo_import_log() -> None:
    _TRIPO_IMPORT_LOG.clear()


__all__ = [
    "CoordinateSystemError",
    "BlenderBooleanUnsafe",
    "assert_z_is_up",
    "convert_y_up_to_z_up",
    "guard_z_up",
    "BLENDER_SCREENSHOT_MAX_SIZE",
    "BLENDER_SCREENSHOT_MIN_SIZE",
    "clamp_screenshot_size",
    "BOOLEAN_DENSE_MESH_VERT_LIMIT",
    "BOOLEAN_DENSE_MESH_DECIMATE_TARGET",
    "assert_boolean_safe",
    "decimate_to_safe_count",
    "recommend_boolean_solver",
    "import_tripo_glb_serialized",
    "get_tripo_import_log",
    "clear_tripo_import_log",
]
