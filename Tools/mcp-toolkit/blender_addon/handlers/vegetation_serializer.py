"""Vegetation instance serializer for Unity terrain import.

Converts Blender scatter object data to Unity TreeInstance JSON format
with Z-up to Y-up axis swap and position normalization.

Exports:
    serialize_vegetation_instances -- Pure-logic serialization.
    handle_serialize_vegetation    -- bpy-dependent handler.
"""

from __future__ import annotations

import json
import os


# ---------------------------------------------------------------------------
# Pure-logic function (testable without bpy)
# ---------------------------------------------------------------------------


def serialize_vegetation_instances(
    vegetation_objects: list[dict],
    terrain_bounds: dict,
) -> dict:
    """Serialize vegetation scatter data to Unity TreeInstance JSON format.

    Parameters
    ----------
    vegetation_objects : list of dict
        Each dict has keys:
            name (str), location (tuple x,y,z in Blender Z-up),
            rotation_z (float, radians), scale (tuple x,y,z),
            veg_type (str, e.g. "Oak_Tree").
    terrain_bounds : dict
        Keys: min_x, max_x, min_y, max_y (Blender XY plane),
        and optionally terrain_name.

    Returns
    -------
    dict with terrain_name, tree_prototypes, instances.
    """
    terrain_name = terrain_bounds.get("terrain_name", "Terrain")
    min_x = float(terrain_bounds.get("min_x", 0.0))
    max_x = float(terrain_bounds.get("max_x", 1.0))
    min_y = float(terrain_bounds.get("min_y", 0.0))
    max_y = float(terrain_bounds.get("max_y", 1.0))

    range_x = max_x - min_x
    range_y = max_y - min_y
    if range_x <= 0:
        range_x = 1.0
    if range_y <= 0:
        range_y = 1.0

    # Build prototype mapping (unique veg_type -> index)
    type_to_index: dict[str, int] = {}
    prototypes: list[dict] = []
    for vobj in vegetation_objects:
        veg_type = vobj.get("veg_type", "Unknown")
        if veg_type not in type_to_index:
            idx = len(prototypes)
            type_to_index[veg_type] = idx
            prototypes.append({
                "prefab_name": veg_type,
                "prototype_index": idx,
            })

    # Build instances with coordinate conversion
    instances: list[dict] = []
    for vobj in vegetation_objects:
        loc = vobj.get("location", (0.0, 0.0, 0.0))
        rot_z = float(vobj.get("rotation_z", 0.0))
        scale = vobj.get("scale", (1.0, 1.0, 1.0))
        veg_type = vobj.get("veg_type", "Unknown")

        # Normalize position to [0,1] on terrain XY plane
        nx = (float(loc[0]) - min_x) / range_x
        ny = (float(loc[1]) - min_y) / range_y
        # Clamp to [0,1]
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        # Unity TreeInstance format:
        # position: [nx, 0.0, ny] (Y=0 because height from terrain)
        # Blender Z-up -> Unity Y-up: X stays, Y->Z, Z->Y
        # But for normalized terrain positions, we use XZ plane in Unity
        instances.append({
            "position": [round(nx, 6), 0.0, round(ny, 6)],
            "rotation": round(rot_z, 6),
            "width_scale": round((float(scale[0]) + float(scale[1])) / 2.0, 4),
            "height_scale": round(float(scale[2]), 4),
            "prototype_index": type_to_index[veg_type],
        })

    return {
        "terrain_name": terrain_name,
        "tree_prototypes": prototypes,
        "instances": instances,
    }


# ---------------------------------------------------------------------------
# bpy-dependent handler
# ---------------------------------------------------------------------------


def handle_serialize_vegetation(params: dict) -> dict:
    """Handler: serialize vegetation instances from Blender to JSON.

    Params
    ------
    output_path : str
        Path to write the JSON file.
    terrain_name : str
        Name of the terrain object for bounds extraction.

    Returns
    -------
    dict with output_path, instance_count, prototype_count.
    """
    import bpy

    output_path = params.get("output_path", "vegetation_instances.json")
    terrain_name = params.get("terrain_name", "Terrain")

    # Extract terrain bounds
    terrain_obj = bpy.data.objects.get(terrain_name)
    if terrain_obj is None:
        return {
            "error": f"Terrain object '{terrain_name}' not found",
            "output_path": output_path,
            "instance_count": 0,
            "prototype_count": 0,
        }

    # Get terrain bounding box in world space
    bbox = [terrain_obj.matrix_world @ bpy.mathutils.Vector(corner) for corner in terrain_obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    terrain_bounds = {
        "terrain_name": terrain_name,
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
    }

    # Collect vegetation objects from "Vegetation" collection
    veg_objects: list[dict] = []
    veg_collection = bpy.data.collections.get("Vegetation")
    if veg_collection:
        for obj in veg_collection.objects:
            if obj.type != "MESH":
                continue
            veg_objects.append({
                "name": obj.name,
                "location": tuple(obj.location),
                "rotation_z": obj.rotation_euler.z,
                "scale": tuple(obj.scale),
                "veg_type": obj.get("veg_type", obj.name.split(".")[0]),
            })

    result = serialize_vegetation_instances(veg_objects, terrain_bounds)

    # Write JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    return {
        "output_path": output_path,
        "instance_count": len(result["instances"]),
        "prototype_count": len(result["tree_prototypes"]),
    }
