"""LOD chain generation handler using Blender's Decimate modifier.

Generates LOD0-LOD3 objects with decreasing face counts from a source mesh.
"""

from __future__ import annotations

import bpy

from ._context import get_3d_context_override


# ---------------------------------------------------------------------------
# Pure-logic helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_lod_ratios(ratios: list[float]) -> bool:
    """Validate that LOD ratios are in descending order and within [0, 1].

    Args:
        ratios: List of decimation ratios (1.0 = full detail, 0.1 = 10%).

    Returns:
        True if valid.

    Raises:
        ValueError: If ratios are not descending or out of range.
    """
    if not ratios:
        raise ValueError("At least one LOD ratio is required")

    for r in ratios:
        if not (0.0 < r <= 1.0):
            raise ValueError(
                f"LOD ratio must be in (0, 1.0], got {r}"
            )

    for i in range(1, len(ratios)):
        if ratios[i] >= ratios[i - 1]:
            raise ValueError(
                f"LOD ratios must be strictly descending: "
                f"ratio[{i}]={ratios[i]} >= ratio[{i-1}]={ratios[i-1]}"
            )

    return True


def _build_lod_name(base_name: str, lod_level: int) -> str:
    """Build LOD object name following {name}_LOD{i} convention.

    Args:
        base_name: Original object name.
        lod_level: LOD level index (0, 1, 2, ...).

    Returns:
        Name string like "Barrel_LOD0".
    """
    return f"{base_name}_LOD{lod_level}"


# ---------------------------------------------------------------------------
# Blender handler
# ---------------------------------------------------------------------------


def handle_generate_lods(params: dict) -> dict:
    """Generate LOD chain using Decimate modifier.

    Params:
        object_name (str): Name of the source mesh object.
        ratios (list[float]): Decimation ratios per LOD level.
            Default: [1.0, 0.5, 0.25, 0.1] for LOD0-LOD3.

    Returns:
        Dict with source, lod_count, and lods list containing per-LOD info.
    """
    object_name = params["object_name"]
    ratios = params.get("ratios", [1.0, 0.5, 0.25, 0.1])

    _validate_lod_ratios(ratios)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object not found: {object_name}")
    if obj.type != "MESH":
        raise ValueError(
            f"Object '{object_name}' is type '{obj.type}', expected 'MESH'"
        )

    lods: list[dict] = []
    source_faces = len(obj.data.polygons)

    for i, ratio in enumerate(ratios):
        lod_name = _build_lod_name(object_name, i)

        if i == 0:
            # LOD0: rename original, record face count
            obj.name = lod_name
            obj.data.name = lod_name
            lods.append({
                "name": lod_name,
                "lod_level": i,
                "ratio": ratio,
                "face_count": source_faces,
                "reduction_pct": 0.0,
            })
        else:
            # Duplicate the LOD0 object for decimation
            lod0 = bpy.data.objects.get(_build_lod_name(object_name, 0))
            new_mesh = lod0.data.copy()
            new_obj = lod0.copy()
            new_obj.data = new_mesh
            new_obj.name = lod_name
            new_obj.data.name = lod_name

            # Link to same collection as source
            for col in lod0.users_collection:
                col.objects.link(new_obj)

            # Add Decimate modifier
            mod = new_obj.modifiers.new(name="Decimate_LOD", type="DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = ratio

            # Apply modifier via operator with context override
            ctx = get_3d_context_override()
            if ctx:
                with bpy.context.temp_override(**ctx, object=new_obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
            else:
                # Fallback: try without override
                with bpy.context.temp_override(object=new_obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)

            face_count = len(new_obj.data.polygons)
            reduction = (
                round((1.0 - face_count / source_faces) * 100, 1)
                if source_faces > 0
                else 0.0
            )

            lods.append({
                "name": lod_name,
                "lod_level": i,
                "ratio": ratio,
                "face_count": face_count,
                "reduction_pct": reduction,
            })

    return {
        "source": object_name,
        "lod_count": len(lods),
        "lods": lods,
    }
