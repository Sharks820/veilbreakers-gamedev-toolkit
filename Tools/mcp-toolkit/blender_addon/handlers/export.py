import os

import bpy

from ._context import get_3d_context_override


def handle_export_fbx(params: dict) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    if not filepath.lower().endswith(".fbx"):
        filepath += ".fbx"

    selected_only = params.get("selected_only", False)
    apply_modifiers = params.get("apply_modifiers", True)

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    override = get_3d_context_override()
    # Unity-optimized FBX settings
    kwargs = {
        "filepath": filepath,
        "use_selection": selected_only,
        "use_mesh_modifiers": apply_modifiers,
        "apply_unit_scale": True,
        "apply_scale_options": "FBX_SCALE_ALL",
        "bake_space_transform": True,
        "axis_forward": "-Z",
        "axis_up": "Y",
        "add_leaf_bones": False,
        "mesh_smooth_type": "FACE",
    }

    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.export_scene.fbx(**kwargs)
    else:
        bpy.ops.export_scene.fbx(**kwargs)

    return {
        "filepath": filepath,
        "format": "fbx",
        "exported": True,
        "selected_only": selected_only,
    }


def handle_export_gltf(params: dict) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    if not filepath.lower().endswith((".gltf", ".glb")):
        filepath += ".glb"

    selected_only = params.get("selected_only", False)
    apply_modifiers = params.get("apply_modifiers", True)

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    override = get_3d_context_override()
    kwargs = {
        "filepath": filepath,
        "use_selection": selected_only,
        "export_apply": apply_modifiers,
    }

    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.export_scene.gltf(**kwargs)
    else:
        bpy.ops.export_scene.gltf(**kwargs)

    return {
        "filepath": filepath,
        "format": "gltf",
        "exported": True,
        "selected_only": selected_only,
    }
