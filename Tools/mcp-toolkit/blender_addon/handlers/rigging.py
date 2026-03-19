"""Rigging handlers for mesh analysis, template application, and custom rig building.

Provides three command handlers:
  - handle_analyze_for_rigging: Mesh proportion analysis and rig template recommendation (RIG-01)
  - handle_apply_rig_template: Apply a Rigify creature rig template to a mesh (RIG-02)
  - handle_build_custom_rig: Mix limb types from LIMB_LIBRARY into a custom rig (RIG-03)

Pure-logic functions (_analyze_proportions, _validate_custom_rig_config) are
separated for testability without Blender.
"""

from __future__ import annotations

import math

import bmesh
import bpy

from ._context import get_3d_context_override
from .rigging_templates import (
    LIMB_LIBRARY,
    TEMPLATE_CATALOG,
    _create_template_bones,
    _fix_deform_hierarchy,
    _generate_rig,
)


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _analyze_proportions(
    bbox_dims: tuple[float, float, float],
    vertex_count: int,
    has_symmetry: bool,
) -> dict:
    """Analyze mesh proportions for rig template recommendation.

    Args:
        bbox_dims: (width, depth, height) bounding box dimensions.
        vertex_count: Total vertex count.
        has_symmetry: Whether mesh has X-axis symmetry.

    Returns:
        Dict with aspect_ratio, recommended_template, confidence,
        has_symmetry, vertex_count, all_candidates.
    """
    w, d, h = bbox_dims
    aspect = h / max(w, 0.001)

    candidates: list[dict] = []

    # Tall narrow mesh -> humanoid
    if aspect > 2.5 and has_symmetry:
        candidates.append({"template": "humanoid", "confidence": 0.8})
    elif aspect > 2.5:
        candidates.append({"template": "humanoid", "confidence": 0.6})

    # Flat wide mesh -> serpent
    if aspect < 0.5 and w > h:
        candidates.append({"template": "serpent", "confidence": 0.7})

    # Medium aspect with significant depth -> quadruped
    if 0.3 < aspect < 0.8 and d > w * 0.8:
        candidates.append({"template": "quadruped", "confidence": 0.7})
    elif 0.8 <= aspect <= 2.5 and d > w * 0.8 and has_symmetry:
        candidates.append({"template": "quadruped", "confidence": 0.6})

    # Wide with medium height and symmetry -> possible dragon/bird
    if 0.5 < aspect < 2.0 and w > d * 1.2 and has_symmetry:
        candidates.append({"template": "dragon", "confidence": 0.5})

    # Low profile with lots of width -> possible insect/arachnid
    if 0.3 < aspect < 1.2 and has_symmetry and w > d:
        candidates.append({"template": "insect", "confidence": 0.45})

    # Roughly spherical -> floating
    if 0.7 < aspect < 1.5 and abs(w - d) < max(w, d) * 0.3:
        candidates.append({"template": "floating", "confidence": 0.45})

    # Fallback -> amorphous
    if not candidates:
        candidates.append({"template": "amorphous", "confidence": 0.4})

    # Sort by confidence descending
    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    best = candidates[0]
    return {
        "aspect_ratio": round(aspect, 2),
        "recommended_template": best["template"],
        "confidence": round(best["confidence"], 2),
        "has_symmetry": has_symmetry,
        "vertex_count": vertex_count,
        "all_candidates": candidates,
    }


def _validate_custom_rig_config(limb_types: list[str]) -> dict:
    """Validate a custom rig configuration against LIMB_LIBRARY.

    Args:
        limb_types: List of limb type strings to include in the rig.

    Returns:
        Dict with valid (bool), errors (list), limb_count (int),
        bone_estimate (int).
    """
    errors: list[str] = []
    bone_estimate = 0

    if not limb_types:
        errors.append("No limb types provided -- at least one required")
        return {
            "valid": False,
            "errors": errors,
            "limb_count": 0,
            "bone_estimate": 0,
        }

    # Validate each limb type exists
    for lt in limb_types:
        if lt not in LIMB_LIBRARY:
            errors.append(
                f"Unknown limb type: '{lt}'. "
                f"Valid types: {sorted(LIMB_LIBRARY.keys())}"
            )
        else:
            # Estimate bone count from the limb function
            try:
                bones = LIMB_LIBRARY[lt]()
                bone_estimate += len(bones)
            except TypeError:
                # Function might need arguments, estimate 6 bones per limb
                bone_estimate += 6

    # Check for conflicts: multiple spine-connected limbs of the same type
    # (not a hard error, just a warning -- multi_armed is valid)

    # Add spine bones to estimate (always included as root)
    bone_estimate += 4  # base spine chain

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "limb_count": len(limb_types),
        "bone_estimate": bone_estimate,
    }


# ---------------------------------------------------------------------------
# Blender-dependent handlers
# ---------------------------------------------------------------------------


def handle_analyze_for_rigging(params: dict) -> dict:
    """Analyze a mesh for rigging: proportions, symmetry, template recommendation (RIG-01).

    Params:
        object_name: Name of the Blender mesh object to analyze.

    Returns dict with proportion analysis and recommended creature template.
    """
    name = params.get("object_name")
    if not name:
        raise ValueError("'object_name' is required")

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    # Extract mesh data via bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        vertex_count = len(bm.verts)

        # Compute bounding box dimensions
        if vertex_count == 0:
            bbox_dims = (0.0, 0.0, 0.0)
            has_symmetry = False
        else:
            xs = [v.co.x for v in bm.verts]
            ys = [v.co.y for v in bm.verts]
            zs = [v.co.z for v in bm.verts]
            bbox_dims = (
                max(xs) - min(xs),  # width (X)
                max(ys) - min(ys),  # depth (Y)
                max(zs) - min(zs),  # height (Z)
            )

            # Check X-axis symmetry: compare mirrored vertex positions
            tolerance = max(bbox_dims) * 0.02  # 2% of largest dim
            sym_matches = 0
            for v in bm.verts:
                mirror_x = -v.co.x
                for v2 in bm.verts:
                    if (
                        abs(v2.co.x - mirror_x) < tolerance
                        and abs(v2.co.y - v.co.y) < tolerance
                        and abs(v2.co.z - v.co.z) < tolerance
                    ):
                        sym_matches += 1
                        break
            has_symmetry = sym_matches > vertex_count * 0.7
    finally:
        bm.free()

    analysis = _analyze_proportions(bbox_dims, vertex_count, has_symmetry)
    analysis["object_name"] = name
    analysis["bbox_dims"] = {
        "width": round(bbox_dims[0], 4),
        "depth": round(bbox_dims[1], 4),
        "height": round(bbox_dims[2], 4),
    }
    return analysis


def handle_apply_rig_template(params: dict) -> dict:
    """Apply a Rigify creature rig template to a mesh object (RIG-02).

    Params:
        object_name: Name of the mesh object to rig.
        template: Template name from TEMPLATE_CATALOG.
        generate: Whether to generate the control rig (default True).

    Returns dict with rig_name, bone_count, template, def_bone_count.
    """
    name = params.get("object_name")
    template_name = params.get("template")

    if not name:
        raise ValueError("'object_name' is required")
    if not template_name:
        raise ValueError("'template' is required")

    obj = bpy.data.objects.get(name)
    if not obj or obj.type != "MESH":
        raise ValueError(f"Mesh object not found: {name}")

    template_bones = TEMPLATE_CATALOG.get(template_name)
    if template_bones is None:
        raise ValueError(
            f"Unknown template: '{template_name}'. "
            f"Valid: {sorted(TEMPLATE_CATALOG.keys())}"
        )

    should_generate = params.get("generate", True)

    # Create armature object
    arm_data = bpy.data.armatures.new(f"{name}_metarig")
    arm_obj = bpy.data.objects.new(f"{name}_metarig", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    arm_obj.location = obj.location

    # Apply template bones
    _create_template_bones(arm_obj, template_bones)
    bone_count = len(arm_data.bones)

    result = {
        "metarig_name": arm_obj.name,
        "bone_count": bone_count,
        "template": template_name,
    }

    if should_generate:
        rig_obj = _generate_rig(arm_obj)
        reparented = _fix_deform_hierarchy(rig_obj)
        def_bone_count = sum(
            1 for b in rig_obj.data.bones if b.name.startswith("DEF-")
        )
        result["rig_name"] = rig_obj.name
        result["def_bone_count"] = def_bone_count
        result["def_reparented"] = reparented
    else:
        result["rig_name"] = arm_obj.name
        result["def_bone_count"] = 0
        result["def_reparented"] = 0

    return result


def handle_build_custom_rig(params: dict) -> dict:
    """Build a custom rig by mixing limb types from LIMB_LIBRARY (RIG-03).

    Params:
        object_name: Name of the mesh object to rig (optional, for positioning).
        limb_types: List of limb type strings from LIMB_LIBRARY.
        generate: Whether to generate the control rig (default True).

    Returns dict with rig_name, bone_count, limbs_used, def_bone_count.
    """
    name = params.get("object_name")
    limb_types = params.get("limb_types", [])
    should_generate = params.get("generate", True)

    # Validate configuration
    validation = _validate_custom_rig_config(limb_types)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid custom rig config: {'; '.join(validation['errors'])}"
        )

    # Always include a spine as root
    merged_bones: dict[str, dict] = {
        "spine": {
            "head": (0.0, 0.0, 0.95),
            "tail": (0.0, 0.0, 1.1),
            "roll": 0.0,
            "parent": None,
            "rigify_type": "spines.super_spine",
        },
        "spine.001": {
            "head": (0.0, 0.0, 1.1),
            "tail": (0.0, 0.0, 1.25),
            "roll": 0.0,
            "parent": "spine",
            "rigify_type": "",
        },
        "spine.002": {
            "head": (0.0, 0.0, 1.25),
            "tail": (0.0, 0.0, 1.4),
            "roll": 0.0,
            "parent": "spine.001",
            "rigify_type": "",
        },
        "spine.003": {
            "head": (0.0, 0.0, 1.4),
            "tail": (0.0, 0.0, 1.55),
            "roll": 0.0,
            "parent": "spine.002",
            "rigify_type": "",
        },
    }

    # Merge limb bones from library
    for lt in limb_types:
        limb_fn = LIMB_LIBRARY[lt]
        limb_bones = limb_fn()
        merged_bones.update(limb_bones)

    # Create armature
    rig_name = "custom_rig"
    if name:
        obj = bpy.data.objects.get(name)
        if obj:
            rig_name = f"{name}_custom_rig"

    arm_data = bpy.data.armatures.new(rig_name)
    arm_obj = bpy.data.objects.new(rig_name, arm_data)
    bpy.context.collection.objects.link(arm_obj)

    if name:
        obj = bpy.data.objects.get(name)
        if obj:
            arm_obj.location = obj.location

    # Apply merged bones
    _create_template_bones(arm_obj, merged_bones)
    bone_count = len(arm_data.bones)

    result = {
        "metarig_name": arm_obj.name,
        "bone_count": bone_count,
        "limbs_used": limb_types,
    }

    if should_generate:
        rig_obj = _generate_rig(arm_obj)
        reparented = _fix_deform_hierarchy(rig_obj)
        def_bone_count = sum(
            1 for b in rig_obj.data.bones if b.name.startswith("DEF-")
        )
        result["rig_name"] = rig_obj.name
        result["def_bone_count"] = def_bone_count
        result["def_reparented"] = reparented
    else:
        result["rig_name"] = arm_obj.name
        result["def_bone_count"] = 0
        result["def_reparented"] = 0

    return result
