"""Prop quality validation for compose_interior and general prop generation.

Pure-logic functions (no bpy imports at module level) for testability without
a running Blender instance. The Blender-side handler imports bpy lazily.

Functions:
    validate_ground_contact    -- Check prop Z position is near floor level.
    validate_prop_orientation  -- Check prop faces toward room center.
    enforce_triangle_budget    -- Enforce per-type triangle count limits.
    validate_prop              -- Run all checks, return combined report.
    handle_validate_prop_quality -- Blender handler: queries bpy, runs checks.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Per-prop-type triangle budgets (game-ready targets)
# ---------------------------------------------------------------------------

TRIANGLE_BUDGETS: dict[str, int] = {
    # Small / simple props
    "candle":        500,
    "bottle":        600,
    "cup":           400,
    "bowl":          600,
    "torch":         800,
    "lantern":      1200,
    "gravestone":   1000,
    "signpost":      800,
    "barrel":       1500,
    "crate":        1000,
    "bucket":        600,
    "shelf":        1200,
    # Furniture
    "chair":        2000,
    "stool":        1000,
    "bench":        1500,
    "table":        2000,
    "bed":          2500,
    "bookshelf":    2500,
    "wardrobe":     2500,
    "chest":        2000,
    "workbench":    2000,
    "fireplace":    2500,
    "candelabra":   1500,
    "chandelier":   2000,
    "anvil":        1500,
    "cauldron":     1500,
    "altar":        2500,
    "throne":       3000,
    # Hero / large props
    "forge":        3500,
    "well":         2000,
    "cart":         2500,
    "market_stall": 3000,
    "brazier":      1500,
    "campfire":     1200,
    # Dungeon props
    "sarcophagus":  3000,
    "prison_door":  2000,
    "torture_rack": 2500,
    "skull_pile":   2000,
    # Vegetation / organic
    "tree_oak":     5000,
    "tree_dead":    3000,
    "tree_pine":    4000,
    "tree_willow":  5000,
    "tree_corrupted": 5000,
    "bush":         2000,
    "fallen_log":   1500,
    "tree_stump":   1000,
    "mushroom_cluster": 1500,
    "rock_formation": 2000,
    # Default for unknown types
    "_default":     3000,
}


# ---------------------------------------------------------------------------
# Pure-logic validators (no bpy)
# ---------------------------------------------------------------------------

def validate_ground_contact(
    obj_z: float,
    obj_height: float = 0.0,
    floor_z: float = 0.0,
    tolerance: float = 0.05,
) -> dict:
    """Check whether a prop is resting on the floor within tolerance.

    Args:
        obj_z: World-space Z of the object origin.
        obj_height: Height (Z dimension) of the object bounding box.
        floor_z: Expected floor Z level (default 0.0).
        tolerance: Acceptable deviation in metres (default 5 cm).

    Returns:
        Dict with keys: passed (bool), deviation (float), message (str).
    """
    # Bottom of the bounding box (assuming origin at centre)
    bottom_z = obj_z - obj_height / 2.0
    deviation = abs(bottom_z - floor_z)
    passed = deviation <= tolerance
    return {
        "passed": passed,
        "deviation": round(deviation, 4),
        "bottom_z": round(bottom_z, 4),
        "floor_z": floor_z,
        "tolerance": tolerance,
        "message": (
            "Ground contact OK"
            if passed
            else f"Prop bottom {bottom_z:.3f} m deviates {deviation:.3f} m from floor {floor_z:.3f} m"
        ),
    }


def validate_prop_orientation(
    obj_forward: tuple[float, float],
    room_center: tuple[float, float],
    obj_position: tuple[float, float],
    tolerance_deg: float = 90.0,
) -> dict:
    """Check that a prop's forward vector points roughly toward the room center.

    Args:
        obj_forward: (fx, fy) normalised 2-D forward vector of the prop.
        room_center: (cx, cy) 2-D room center in world space.
        obj_position: (px, py) 2-D prop position in world space.
        tolerance_deg: Acceptable angular deviation (default ±90°).

    Returns:
        Dict with keys: passed (bool), angle_deg (float), message (str).
    """
    dx = room_center[0] - obj_position[0]
    dy = room_center[1] - obj_position[1]
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 0.01:
        # Prop is at room center — orientation irrelevant
        return {
            "passed": True,
            "angle_deg": 0.0,
            "message": "Prop at room center — orientation check skipped",
        }

    to_center = (dx / dist, dy / dist)
    fx, fy = obj_forward
    fwd_len = math.sqrt(fx * fx + fy * fy)
    if fwd_len < 0.001:
        return {
            "passed": False,
            "angle_deg": 180.0,
            "message": "Forward vector is zero-length",
        }
    fx /= fwd_len
    fy /= fwd_len

    dot = max(-1.0, min(1.0, fx * to_center[0] + fy * to_center[1]))
    angle_deg = math.degrees(math.acos(dot))
    passed = angle_deg <= tolerance_deg
    return {
        "passed": passed,
        "angle_deg": round(angle_deg, 2),
        "tolerance_deg": tolerance_deg,
        "message": (
            f"Orientation OK ({angle_deg:.1f}° from room center)"
            if passed
            else f"Prop faces {angle_deg:.1f}° away from room center (tolerance {tolerance_deg}°)"
        ),
    }


def enforce_triangle_budget(
    face_count: int,
    prop_type: str,
    budget_override: int | None = None,
) -> dict:
    """Check prop triangle count against per-type budget.

    Args:
        face_count: Number of triangulated faces in the mesh.
        prop_type: Prop category key (e.g. "barrel", "tree_oak").
        budget_override: Optional explicit budget; overrides lookup table.

    Returns:
        Dict with keys: passed (bool), face_count (int), budget (int),
        over_by (int), utilisation (float 0-1), message (str).
    """
    budget = budget_override if budget_override is not None else TRIANGLE_BUDGETS.get(
        prop_type, TRIANGLE_BUDGETS["_default"]
    )
    over_by = max(0, face_count - budget)
    passed = face_count <= budget
    utilisation = face_count / budget if budget > 0 else 1.0
    return {
        "passed": passed,
        "face_count": face_count,
        "budget": budget,
        "over_by": over_by,
        "utilisation": round(utilisation, 4),
        "message": (
            f"Triangle budget OK ({face_count}/{budget})"
            if passed
            else f"Exceeds triangle budget by {over_by} ({face_count}/{budget})"
        ),
    }


def validate_prop(
    obj_z: float,
    obj_height: float,
    face_count: int,
    prop_type: str,
    obj_forward: tuple[float, float] | None = None,
    room_center: tuple[float, float] | None = None,
    obj_position: tuple[float, float] | None = None,
    floor_z: float = 0.0,
    ground_tolerance: float = 0.05,
    orientation_tolerance_deg: float = 90.0,
) -> dict:
    """Run all prop quality checks and return a combined report.

    Returns:
        Dict with keys: passed (bool), checks (dict of sub-results), issues (list[str]).
    """
    checks: dict[str, dict] = {}
    issues: list[str] = []

    ground = validate_ground_contact(obj_z, obj_height, floor_z, ground_tolerance)
    checks["ground_contact"] = ground
    if not ground["passed"]:
        issues.append(ground["message"])

    tri = enforce_triangle_budget(face_count, prop_type)
    checks["triangle_budget"] = tri
    if not tri["passed"]:
        issues.append(tri["message"])

    if obj_forward is not None and room_center is not None and obj_position is not None:
        orient = validate_prop_orientation(
            obj_forward, room_center, obj_position, orientation_tolerance_deg
        )
        checks["orientation"] = orient
        if not orient["passed"]:
            issues.append(orient["message"])

    return {
        "passed": len(issues) == 0,
        "checks": checks,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Blender handler (bpy imported lazily)
# ---------------------------------------------------------------------------

def handle_validate_prop_quality(params: dict) -> dict:
    """Blender-side handler: fetch object data from bpy and run quality checks.

    Params:
        object_name (str): Object to validate (required).
        prop_type (str): Prop category for triangle budget lookup (default "_default").
        floor_z (float): Expected floor Z level (default 0.0).
        room_center (list[float,float], optional): [cx, cy] for orientation check.
        ground_tolerance (float): Ground contact tolerance in metres (default 0.05).

    Returns:
        Combined validation report dict.
    """
    import bpy  # noqa: PLC0415 — intentionally deferred for testability
    import bmesh  # noqa: PLC0415

    object_name = params.get("object_name")
    if not object_name:
        raise ValueError("object_name is required")

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")

    prop_type = params.get("prop_type", "_default")
    floor_z = float(params.get("floor_z", 0.0))
    ground_tolerance = float(params.get("ground_tolerance", 0.05))
    room_center_raw = params.get("room_center")

    # Get triangle count via bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    face_count = len(bm.faces)
    bm.free()

    obj_z = float(obj.location.z)
    obj_height = float(obj.dimensions.z)

    # Forward vector: -Y in local space, transformed to world XY
    from mathutils import Vector
    local_fwd = Vector((0.0, -1.0, 0.0))
    world_fwd = (obj.matrix_world.to_3x3() @ local_fwd).normalized()
    obj_forward: tuple[float, float] = (world_fwd.x, world_fwd.y)
    obj_position: tuple[float, float] = (float(obj.location.x), float(obj.location.y))

    room_center: tuple[float, float] | None = None
    if room_center_raw and len(room_center_raw) >= 2:
        room_center = (float(room_center_raw[0]), float(room_center_raw[1]))

    return validate_prop(
        obj_z=obj_z,
        obj_height=obj_height,
        face_count=face_count,
        prop_type=prop_type,
        obj_forward=obj_forward,
        room_center=room_center,
        obj_position=obj_position,
        floor_z=floor_z,
        ground_tolerance=ground_tolerance,
    )
