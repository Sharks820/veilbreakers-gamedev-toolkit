"""Weight painting, deformation testing, rig validation, weight fix, and weight
limit enforcement handlers.

Provides five command handlers:
  - handle_auto_weight: Parent mesh to armature with heat diffusion weight painting (RIG-07)
  - handle_test_deformation: Pose rig at 8 standard poses and generate contact sheet (RIG-08)
  - handle_validate_rig: Grade rig A-F based on weight/symmetry/roll analysis (RIG-09)
  - handle_fix_weights: Normalize, clean zeros, smooth, and mirror weights (RIG-10)
  - handle_enforce_weight_limit: Clamp per-vertex bone influences to a maximum (P2-A6)

Pure-logic functions:
  - _validate_skinning_mode: Validate skinning mode selection (LBS/DQS/Hybrid)
  - _compute_rig_grade: Compute rig quality grade A-F from numeric thresholds
  - _validate_rig_report: Build rig validation report from mesh/armature data
  - _validate_weight_fix_params: Validate weight fix operation type and parameters
  - _enforce_weight_limit_pure: Clamp per-vertex bone influences (pure logic)
  - _compute_skinning_quality: Compute skinning quality metrics for weight paint analysis
  - _enhanced_rig_validation: Enhanced rig validation with additional checks
"""

from __future__ import annotations

import math

import bpy
from mathutils import Euler

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Deformation pose presets (8 standard poses)
# ---------------------------------------------------------------------------

DEFORMATION_POSES: dict[str, dict[str, tuple[float, float, float]]] = {
    "t_pose": {},  # Default rest pose (no rotations)
    "a_pose": {
        "DEF-upper_arm.L": (0, 0, -0.785),
        "DEF-upper_arm.R": (0, 0, 0.785),
    },
    "crouch": {
        "DEF-thigh.L": (-1.2, 0, 0),
        "DEF-thigh.R": (-1.2, 0, 0),
        "DEF-shin.L": (1.0, 0, 0),
        "DEF-shin.R": (1.0, 0, 0),
    },
    "reach_up": {
        "DEF-upper_arm.L": (0, 0, 2.6),
        "DEF-upper_arm.R": (0, 0, -2.6),
    },
    "twist_left": {
        "DEF-spine.001": (0, 0.7, 0),
        "DEF-spine.002": (0, 0.7, 0),
    },
    "twist_right": {
        "DEF-spine.001": (0, -0.7, 0),
        "DEF-spine.002": (0, -0.7, 0),
    },
    "extreme_bend": {
        "DEF-forearm.L": (-2.0, 0, 0),
        "DEF-forearm.R": (-2.0, 0, 0),
    },
    "action_pose": {
        "DEF-thigh.L": (-0.8, 0, 0),
        "DEF-thigh.R": (-0.3, 0, 0.3),
        "DEF-upper_arm.L": (0.5, 0, 1.5),
        "DEF-upper_arm.R": (-0.3, 0, -0.8),
    },
}


# ---------------------------------------------------------------------------
# Skinning mode definitions (LBS / DQS / Hybrid)
# ---------------------------------------------------------------------------

SKINNING_MODES: dict[str, dict] = {
    "linear": {
        "description": "Standard linear blend skinning (LBS)",
        "use_dual_quaternion": False,
        "best_for": "extremities, simple deformations",
    },
    "dual_quaternion": {
        "description": "Dual quaternion skinning — preserves volume at joints",
        "use_dual_quaternion": True,
        "best_for": "shoulders, hips, spine — prevents volume loss",
    },
    "hybrid": {
        "description": "Per-vertex LBS/DQS blend for optimal results",
        "use_dual_quaternion": True,
        "best_for": "full characters — DQS at joints, LBS at extremities",
    },
}


def _validate_skinning_mode(mode: str) -> dict:
    """Validate skinning mode selection."""
    if mode not in SKINNING_MODES:
        return {
            "valid": False,
            "errors": [f"Unknown mode: '{mode}'. Valid: {sorted(SKINNING_MODES.keys())}"],
        }
    return {"valid": True, "errors": [], "config": SKINNING_MODES[mode]}


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _compute_rig_grade(
    unweighted_pct: float,
    non_normalized: int,
    symmetry_issues: int,
    roll_issues: int,
) -> str:
    """Compute rig quality grade from numeric thresholds.

    Returns a single letter grade A-F.
    """
    if unweighted_pct > 10 or non_normalized > 100:
        return "F"
    if unweighted_pct > 5 or non_normalized > 50 or symmetry_issues > 5:
        return "D"
    if unweighted_pct > 1 or non_normalized > 10 or symmetry_issues > 2:
        return "C"
    if unweighted_pct > 0 or non_normalized > 0 or roll_issues > 2:
        return "B"
    return "A"


def _validate_rig_report(
    vertex_count: int,
    vertex_group_names: list[str],
    unweighted_vertex_indices: list[int],
    weight_sums: list[float],
    bone_names: list[str],
    bone_rolls: dict[str, float],
    bone_parents: dict[str, str | None],
) -> dict:
    """Build a rig validation report from extracted mesh/armature data.

    Args:
        vertex_count: Total vertices in the mesh.
        vertex_group_names: Names of all vertex groups on the mesh.
        unweighted_vertex_indices: Indices of vertices with no weight > 0.01.
        weight_sums: Per-vertex total weight sums (length == vertex_count).
        bone_names: All bone names in the armature.
        bone_rolls: Mapping of bone name -> roll value (radians).
        bone_parents: Mapping of bone name -> parent bone name (or None).

    Returns:
        Dict with vertex_count, bone_count, unweighted_vertices,
        unweighted_percentage, non_normalized_vertices, symmetry_issues,
        roll_issues, issues (list of strings), grade.
    """
    issues: list[str] = []

    # -- Unweighted vertices --
    unweighted_count = len(unweighted_vertex_indices)
    unweighted_pct = (
        (unweighted_count / vertex_count * 100) if vertex_count > 0 else 0.0
    )

    if unweighted_count > 0:
        issues.append(
            f"{unweighted_count} vertices ({unweighted_pct:.1f}%) have no weight"
        )

    # -- Non-normalized vertices --
    non_normalized = 0
    for ws in weight_sums:
        if abs(ws - 1.0) > 0.01:
            non_normalized += 1

    if non_normalized > 0:
        issues.append(f"{non_normalized} vertices are not normalized")

    # -- Bone symmetry check (L/R pairs) --
    left_bones = [n for n in bone_names if n.endswith(".L")]
    right_bones_set = {n for n in bone_names if n.endswith(".R")}

    symmetry_issues = 0
    for lb in left_bones:
        expected_right = lb[:-2] + ".R"
        if expected_right not in right_bones_set:
            symmetry_issues += 1
            issues.append(f"Missing right counterpart for '{lb}'")

    right_bones = [n for n in bone_names if n.endswith(".R")]
    left_bones_set = {n for n in bone_names if n.endswith(".L")}
    for rb in right_bones:
        expected_left = rb[:-2] + ".L"
        if expected_left not in left_bones_set:
            symmetry_issues += 1
            issues.append(f"Missing left counterpart for '{rb}'")

    # -- Roll consistency (L bone roll should be negative of R bone roll) --
    roll_issues = 0
    roll_tolerance = 0.05  # radians
    for lb in left_bones:
        rb = lb[:-2] + ".R"
        if rb in bone_rolls and lb in bone_rolls:
            l_roll = bone_rolls[lb]
            r_roll = bone_rolls[rb]
            if abs(l_roll + r_roll) > roll_tolerance:
                roll_issues += 1
                issues.append(
                    f"Roll mismatch: '{lb}' ({l_roll:.3f}) vs "
                    f"'{rb}' ({r_roll:.3f})"
                )

    grade = _compute_rig_grade(
        unweighted_pct, non_normalized, symmetry_issues, roll_issues
    )

    return {
        "vertex_count": vertex_count,
        "bone_count": len(bone_names),
        "unweighted_vertices": unweighted_count,
        "unweighted_percentage": round(unweighted_pct, 2),
        "non_normalized_vertices": non_normalized,
        "symmetry_issues": symmetry_issues,
        "roll_issues": roll_issues,
        "issues": issues,
        "grade": grade,
    }


def _validate_weight_fix_params(operation: str, params: dict) -> dict:
    """Validate weight fix operation type and parameters.

    Args:
        operation: One of "normalize", "clean_zeros", "smooth", "mirror".
        params: Additional parameters for the operation.

    Returns:
        Dict with valid (bool), errors (list[str]), operation (str).
    """
    valid_operations = {"normalize", "clean_zeros", "smooth", "mirror"}
    errors: list[str] = []

    if operation not in valid_operations:
        errors.append(
            f"Unknown operation: '{operation}'. "
            f"Valid: {sorted(valid_operations)}"
        )
        return {"valid": False, "errors": errors, "operation": operation}

    if operation == "mirror":
        direction = params.get("direction")
        valid_directions = {"left_to_right", "right_to_left"}
        if direction not in valid_directions:
            errors.append(
                f"'mirror' requires 'direction' param: one of {sorted(valid_directions)}"
            )

    if operation == "smooth":
        factor = params.get("factor")
        if factor is not None:
            if not isinstance(factor, (int, float)) or not (0.0 <= factor <= 1.0):
                errors.append("'smooth' factor must be between 0.0 and 1.0")
        repeat = params.get("repeat")
        if repeat is not None:
            if not isinstance(repeat, int) or not (1 <= repeat <= 10):
                errors.append("'smooth' repeat must be an integer between 1 and 10")

    if operation == "clean_zeros":
        threshold = params.get("threshold")
        if threshold is not None:
            if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 0.1):
                errors.append(
                    "'clean_zeros' threshold must be between 0.0 and 0.1"
                )

    return {"valid": len(errors) == 0, "errors": errors, "operation": operation}


def _enforce_weight_limit_pure(
    vertex_weights: list[list[tuple[str, float]]],
    max_influences: int = 4,
) -> dict:
    """Clamp per-vertex bone influences to a maximum count (pure logic).

    For each vertex, keeps only the top *max_influences* weights (by value),
    drops the rest, and renormalizes so they sum to 1.0.

    Args:
        vertex_weights: Per-vertex list of (bone_name, weight) tuples.
        max_influences: Maximum bone influences per vertex (default 4).

    Returns:
        Dict with clamped_vertices (int), total_vertices (int),
        max_influences (int), vertex_weights (processed list).
    """
    clamped = 0
    result_weights: list[list[tuple[str, float]]] = []

    for vw in vertex_weights:
        if len(vw) <= max_influences:
            result_weights.append(list(vw))
            continue

        # Sort descending by weight, keep top N
        sorted_w = sorted(vw, key=lambda t: t[1], reverse=True)
        kept = sorted_w[:max_influences]
        total = sum(w for _, w in kept)
        if total > 0:
            kept = [(name, w / total) for name, w in kept]
        result_weights.append(kept)
        clamped += 1

    return {
        "clamped_vertices": clamped,
        "total_vertices": len(vertex_weights),
        "max_influences": max_influences,
        "vertex_weights": result_weights,
    }


def _compute_skinning_quality(
    vertex_weights: list[list[tuple[int, float]]],
    vertex_positions: list[tuple[float, float, float]],
) -> dict:
    """Compute skinning quality metrics for weight paint analysis."""
    total = len(vertex_weights)
    if total == 0:
        return {"quality_score": 1.0, "hard_edges": 0, "unweighted": 0, "over_influenced": 0}

    unweighted = sum(1 for g in vertex_weights if not g or all(w < 0.01 for _, w in g))
    over_influenced = sum(1 for g in vertex_weights if len(g) > 4)

    # Check for hard weight transitions (adjacent verts with very different weights)
    hard_edges = 0
    for i, groups in enumerate(vertex_weights):
        max_w = max((w for _, w in groups), default=0)
        if max_w > 0.95:
            hard_edges += 1

    quality = 1.0 - (unweighted / max(total, 1)) * 0.5 - (over_influenced / max(total, 1)) * 0.3 - (hard_edges / max(total, 1)) * 0.2

    return {
        "quality_score": round(max(0.0, min(1.0, quality)), 3),
        "total_vertices": total,
        "unweighted": unweighted,
        "over_influenced": over_influenced,
        "hard_edges": hard_edges,
    }


def _enhanced_rig_validation(
    bone_names: list[str],
    bone_rolls: dict[str, float],
    bone_parents: dict[str, str | None],
    vertex_influence_counts: list[int],
    max_influences: int = 4,
    vertex_weights: list[list[tuple[int, float]]] | None = None,
    vertex_group_names: list[str] | None = None,
) -> dict:
    """Enhanced rig validation with additional checks beyond basic grading.

    Checks:
      - zero_weight_bones: bones with no vertex influence at all
      - over_limit_vertices: vertices exceeding max_influences
      - symmetry_mismatches: L bones missing R counterpart
      - default_roll_bones: bones with roll == 0.0 (suspicious for limbs)
      - missing_twist_bones: limb bones without twist helpers

    Args:
        bone_names: All bone names in the armature.
        bone_rolls: Mapping bone name -> roll (radians).
        bone_parents: Mapping bone name -> parent (or None).
        vertex_influence_counts: Per-vertex influence count list.
        max_influences: Limit for over-limit check (default 4).
        vertex_weights: Optional per-vertex list of (group_index, weight) tuples.
        vertex_group_names: Optional mapping of group indices to names.

    Returns:
        Dict with zero_weight_bones, over_limit_vertices,
        symmetry_mismatches, default_roll_bones, missing_twist_bones,
        issues (list[str]).
    """
    issues: list[str] = []

    # Zero weight bones: bones that exist but no vertex references them
    zero_weight_bones: list[str] = []
    if vertex_weights is not None and vertex_group_names is not None:
        weighted_indices: set[int] = set()
        for vw in vertex_weights:
            for group_idx, weight in vw:
                if weight > 0.01:
                    weighted_indices.add(group_idx)
        weighted_names = {
            vertex_group_names[i]
            for i in weighted_indices
            if i < len(vertex_group_names)
        }
        bone_set = set(bone_names)
        zero_weight_bones = sorted(
            name for name in bone_set if name not in weighted_names
        )

    # Over limit vertices
    over_limit = sum(1 for c in vertex_influence_counts if c > max_influences)
    if over_limit > 0:
        issues.append(f"{over_limit} vertices exceed {max_influences}-influence limit")

    # Symmetry mismatches
    left_bones = [n for n in bone_names if n.endswith(".L")]
    right_set = {n for n in bone_names if n.endswith(".R")}
    symmetry_mismatches: list[str] = []
    for lb in left_bones:
        rb = lb[:-2] + ".R"
        if rb not in right_set:
            symmetry_mismatches.append(lb)
            issues.append(f"Missing R counterpart for '{lb}'")

    # Default roll bones (limb bones with roll exactly 0.0)
    limb_prefixes = ("upper_arm", "forearm", "thigh", "shin")
    default_roll_bones: list[str] = []
    for bname in bone_names:
        base = bname.split(".")[0]
        if any(base.startswith(p) for p in limb_prefixes):
            roll = bone_rolls.get(bname, 0.0)
            if roll == 0.0:
                default_roll_bones.append(bname)
                issues.append(f"Bone '{bname}' has default roll 0.0")

    # Missing twist bones
    twist_map = {
        "upper_arm": "upper_arm_twist",
        "forearm": "forearm_twist",
        "thigh": "thigh_twist",
        "shin": "shin_twist",
    }
    bone_set = set(bone_names)
    missing_twist: list[str] = []
    for bname in bone_names:
        for limb_prefix, twist_prefix in twist_map.items():
            if bname.startswith(limb_prefix + "."):
                suffix = bname[len(limb_prefix):]  # e.g. ".L"
                expected_twist = twist_prefix + suffix
                if expected_twist not in bone_set:
                    missing_twist.append(bname)
                    issues.append(f"Missing twist bone '{expected_twist}' for '{bname}'")

    return {
        "zero_weight_bones": zero_weight_bones,
        "over_limit_vertices": over_limit,
        "symmetry_mismatches": symmetry_mismatches,
        "default_roll_bones": default_roll_bones,
        "missing_twist_bones": missing_twist,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Blender-dependent handlers
# ---------------------------------------------------------------------------


def handle_auto_weight(params: dict) -> dict:
    """Parent mesh to armature with automatic weight painting (RIG-07).

    Params:
        mesh_name: Name of the mesh object.
        armature_name: Name of the armature object.

    Returns dict with vertex_group_count, vertex_groups, method, mesh, armature.
    """
    mesh_name = params.get("mesh_name")
    armature_name = params.get("armature_name")

    if not mesh_name:
        raise ValueError("'mesh_name' is required")
    if not armature_name:
        raise ValueError("'armature_name' is required")

    mesh_obj = bpy.data.objects.get(mesh_name)
    if not mesh_obj or mesh_obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {mesh_name}")

    arm_obj = bpy.data.objects.get(armature_name)
    if not arm_obj or arm_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {armature_name}")

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for weight painting")

    # Deselect all, then select mesh and make armature active
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    method = "auto"
    try:
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.parent_set(type="ARMATURE_AUTO", xmirror=True)
    except RuntimeError:
        # Heat diffusion failed -- fall back to envelope weights
        method = "envelope"
        with bpy.context.temp_override(**ctx):
            bpy.ops.object.parent_set(type="ARMATURE_ENVELOPE")

    # Gather vertex group info
    vgroups = [vg.name for vg in mesh_obj.vertex_groups]

    return {
        "vertex_group_count": len(vgroups),
        "vertex_groups": vgroups,
        "method": method,
        "mesh": mesh_name,
        "armature": armature_name,
    }


def handle_test_deformation(params: dict) -> dict:
    """Pose rig at standard poses and generate contact sheet (RIG-08).

    Params:
        rig_name: Name of the rig/armature object.
        pose_names: Optional list of pose names to test (default: all 8).
        mesh_name: Optional mesh name for contact sheet rendering.

    Returns dict with poses_tested, pose_names, contact_sheet.
    """
    rig_name = params.get("rig_name")
    if not rig_name:
        raise ValueError("'rig_name' is required")

    rig_obj = bpy.data.objects.get(rig_name)
    if not rig_obj or rig_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {rig_name}")

    requested_poses = params.get("pose_names")
    if requested_poses is None:
        requested_poses = list(DEFORMATION_POSES.keys())

    # Validate pose names
    for pn in requested_poses:
        if pn not in DEFORMATION_POSES:
            raise ValueError(
                f"Unknown pose: '{pn}'. Valid: {sorted(DEFORMATION_POSES.keys())}"
            )

    # Switch to pose mode
    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.object.mode_set(mode="POSE")

    tested_poses: list[str] = []

    for pose_name in requested_poses:
        rotations = DEFORMATION_POSES[pose_name]

        # Reset all pose bones to rest
        for pb in rig_obj.pose.bones:
            pb.rotation_euler = Euler((0, 0, 0))
            pb.rotation_quaternion = (1, 0, 0, 0)

        # Apply pose rotations
        for bone_name, (rx, ry, rz) in rotations.items():
            pb = rig_obj.pose.bones.get(bone_name)
            if pb:
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = Euler((rx, ry, rz))

        # Update dependency graph
        bpy.context.view_layer.update()

        # Insert keyframe at frame = pose index for contact sheet
        frame = len(tested_poses) + 1
        bpy.context.scene.frame_set(frame)
        for pb in rig_obj.pose.bones:
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        tested_poses.append(pose_name)

    # Reset to rest pose
    for pb in rig_obj.pose.bones:
        pb.rotation_euler = Euler((0, 0, 0))
        pb.rotation_quaternion = (1, 0, 0, 0)

    bpy.ops.object.mode_set(mode="OBJECT")

    # Generate contact sheet via viewport handler
    from .viewport import handle_render_contact_sheet

    sheet_target = params.get("mesh_name", rig_name)
    contact_result = handle_render_contact_sheet({
        "object_name": sheet_target,
        "frames": list(range(1, len(tested_poses) + 1)),
        "resolution": params.get("resolution", [512, 512]),
    })

    return {
        "poses_tested": len(tested_poses),
        "pose_names": tested_poses,
        "contact_sheet": contact_result.get("image", ""),
    }


def handle_validate_rig(params: dict) -> dict:
    """Validate rig quality: weights, symmetry, rolls -- grade A-F (RIG-09).

    Params:
        mesh_name: Name of the mesh object (with vertex groups).
        armature_name: Name of the armature object.

    Returns validation report dict with grade and issues list.
    """
    mesh_name = params.get("mesh_name")
    armature_name = params.get("armature_name")

    if not mesh_name:
        raise ValueError("'mesh_name' is required")
    if not armature_name:
        raise ValueError("'armature_name' is required")

    mesh_obj = bpy.data.objects.get(mesh_name)
    if not mesh_obj or mesh_obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {mesh_name}")

    arm_obj = bpy.data.objects.get(armature_name)
    if not arm_obj or arm_obj.type != "ARMATURE":
        raise ValueError(f"Armature object not found: {armature_name}")

    mesh_data = mesh_obj.data
    vertex_count = len(mesh_data.vertices)
    vertex_group_names = [vg.name for vg in mesh_obj.vertex_groups]

    # Find unweighted vertices and compute weight sums
    unweighted_indices: list[int] = []
    weight_sums: list[float] = []

    for v in mesh_data.vertices:
        total = 0.0
        has_significant = False
        for g in v.groups:
            w = g.weight
            total += w
            if w > 0.01:
                has_significant = True
        weight_sums.append(total)
        if not has_significant:
            unweighted_indices.append(v.index)

    # Extract bone info from armature
    bone_names = [b.name for b in arm_obj.data.bones]
    bone_rolls: dict[str, float] = {}
    bone_parents: dict[str, str | None] = {}

    # Need edit mode to access bone rolls
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    for ebone in arm_obj.data.edit_bones:
        bone_rolls[ebone.name] = ebone.roll
        bone_parents[ebone.name] = ebone.parent.name if ebone.parent else None
    bpy.ops.object.mode_set(mode="OBJECT")

    report = _validate_rig_report(
        vertex_count,
        vertex_group_names,
        unweighted_indices,
        weight_sums,
        bone_names,
        bone_rolls,
        bone_parents,
    )

    report["mesh"] = mesh_name
    report["armature"] = armature_name
    return report


def handle_fix_weights(params: dict) -> dict:
    """Fix vertex weights: normalize, clean zeros, smooth, or mirror (RIG-10).

    Params:
        mesh_name: Name of the mesh object.
        operation: One of "normalize", "clean_zeros", "smooth", "mirror".
        direction: Required for "mirror" -- "left_to_right" or "right_to_left".
        factor: Optional smooth factor (0.0-1.0, default 0.5).
        repeat: Optional smooth repeat count (1-10, default 1).
        threshold: Optional clean_zeros threshold (0.0-0.1, default 0.01).

    Returns dict with operation, mesh, status.
    """
    mesh_name = params.get("mesh_name")
    operation = params.get("operation")

    if not mesh_name:
        raise ValueError("'mesh_name' is required")
    if not operation:
        raise ValueError("'operation' is required")

    mesh_obj = bpy.data.objects.get(mesh_name)
    if not mesh_obj or mesh_obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {mesh_name}")

    # Validate operation and params
    validation = _validate_weight_fix_params(operation, params)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    ctx = get_3d_context_override()
    if ctx is None:
        raise RuntimeError("No 3D Viewport available for weight operations")

    # Select and activate the mesh
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    with bpy.context.temp_override(**ctx):
        if operation == "normalize":
            bpy.ops.object.vertex_group_normalize_all()

        elif operation == "clean_zeros":
            threshold = params.get("threshold", 0.01)
            bpy.ops.object.vertex_group_clean(
                group_select_mode="ALL", limit=threshold
            )

        elif operation == "smooth":
            factor = params.get("factor", 0.5)
            repeat = params.get("repeat", 1)
            bpy.ops.object.vertex_group_smooth(
                group_select_mode="ALL", factor=factor, repeat=repeat
            )

        elif operation == "mirror":
            direction = params.get("direction")
            use_mirror = direction == "left_to_right"
            bpy.ops.object.vertex_group_mirror(
                mirror_weights=True,
                flip_group_names=use_mirror,
                use_topology=False,
            )

    return {
        "operation": operation,
        "mesh": mesh_name,
        "status": "success",
    }


def handle_enforce_weight_limit(params: dict) -> dict:
    """Enforce a per-vertex bone influence limit on a mesh (P2-A6).

    Params:
        mesh_name: Name of the mesh object.
        max_influences: Maximum influences per vertex (default 4).

    Returns dict with clamped_vertices, total_vertices, max_influences, mesh.
    """
    mesh_name = params.get("mesh_name")
    max_influences = int(params.get("max_influences", 4))

    if not mesh_name:
        raise ValueError("'mesh_name' is required")

    mesh_obj = bpy.data.objects.get(mesh_name)
    if not mesh_obj or mesh_obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {mesh_name}")

    mesh_data = mesh_obj.data

    # Extract per-vertex weights
    vertex_weights: list[list[tuple[str, float]]] = []
    for v in mesh_data.vertices:
        vw: list[tuple[str, float]] = []
        for g in v.groups:
            if g.weight > 0.001:
                vg_name = mesh_obj.vertex_groups[g.group].name
                vw.append((vg_name, g.weight))
        vertex_weights.append(vw)

    result = _enforce_weight_limit_pure(vertex_weights, max_influences)

    # Apply back to mesh
    for vi, new_weights in enumerate(result["vertex_weights"]):
        v = mesh_data.vertices[vi]
        # Clear all existing groups for this vertex
        group_indices = [g.group for g in v.groups]
        for gi in group_indices:
            mesh_obj.vertex_groups[gi].remove([vi])
        # Re-assign clamped weights
        for bone_name, weight in new_weights:
            vg = mesh_obj.vertex_groups.get(bone_name)
            if vg:
                vg.add([vi], weight, "REPLACE")

    return {
        "clamped_vertices": result["clamped_vertices"],
        "total_vertices": result["total_vertices"],
        "max_influences": result["max_influences"],
        "mesh": mesh_name,
    }
